"""Streaming sachet check: per-frame signals in, results out as soon as they are certain.

Push one frame's signals at a time (`SachetChecker.push`). Two kinds of result come out:

  kind "sachet"  one per sachet that fell off the belt: where it ended up (IN BAG, EMPTY BAG,
                 OUTSIDE BAG, STUCK IN CHUTE, NOT SEEN), whether a tray set was under it, double strip.
                 Ready ~4.5 s after the drop (the landing check watches the conveyors for 3 s + 1.5 s hold).
  kind "sets"    one per stretch of tray sets passing under the chute (usually a single set): how many
                 sets, how many sachets fell on them -> ok / MISSING / EXTRA / DOUBLE / partial.
                 Ready ~1.5 s after the stretch leaves the drop box.

This is the batch method from research/prototype (match3.py + landing_verdict.py) run online. It gives
the same answers except where the batch version looked into the future: the cycle time and the "typical
sachet size" now use only the past (see docs/method.md, "Streaming vs batch").
"""
from __future__ import annotations

from collections import deque
from statistics import median

import numpy as np

from .config import Config
from .shape import blob_shape, sachet_like
from .signals import KEYS


class _Ring:
    """Fixed-size history of per-frame values, addressed by absolute frame index."""

    def __init__(self, names, cap):
        self.cap, self.col = cap, {k: i for i, k in enumerate(names)}
        self.a = np.zeros((cap, len(names)), np.float64)
        self.n = 0

    def push(self, row):
        self.a[self.n % self.cap] = row
        self.n += 1

    def get(self, name, i0, i1):
        i0, i1 = max(i0, 0, self.n - self.cap), min(i1, self.n)
        if i1 <= i0:
            return np.zeros(0)
        return self.a[np.arange(i0, i1) % self.cap, self.col[name]]

    def at(self, name, i):
        return float(self.a[i % self.cap, self.col[name]])


class SachetChecker:
    def __init__(self, cfg: Config, keep_s: float = 300.0):
        self.cfg = cfg
        f = cfg.frames
        self.fps = cfg.fps
        self.h = _Ring(KEYS + ("wall",), int(keep_s * self.fps))
        self.crops: dict[int, tuple] = {}
        dc, sc, lc = cfg["drop"], cfg["sets"], cfg["landing"]
        # sachet drops
        self.lag, self.drop_gap, self.fall = f(dc["over_s"]), f(dc["min_gap_s"]), dc["fall"]
        self.size_back, self.size_skip = f(1.5), f(0.2)   # sachet size = top-5 median of belt-white 1.5-0.2 s before
        self.scan = 1                     # next frame index to test as a drop
        self.cand = None                  # (index, fall) of a drop that a deeper fall could still replace
        self.drops: list[dict] = []       # final drops, oldest first (pruned)
        self.sizes: deque = deque(maxlen=int(cfg["double"]["recent_drops"]))
        self.next_sachet_id = 0
        # tray-set stretches
        self.half = f(sc["motion_smooth_s"]) // 2
        self.win = 2 * self.half + 1
        self.merge_gap, self.min_len = f(sc["merge_gap_s"]), f(sc["min_len_s"])
        self.mask_next = 0
        self.open_start = None
        self.seg = None
        self.stretches: deque = deque()   # closed stretches waiting for their drops to be final
        self.next_set_id = 0
        # landing
        self.watch = f(lc["watch_s"])
        self.crop_keep = self.watch + f(lc["stuck_hold_s"]) + f(lc["shape"]["before_s"]) + 20
        self.emit_q: deque = deque()      # sachets in drop order, emitted strictly in order
        self.finished = False

    # ------------------------------------------------------------------ input
    def push(self, sig: dict, crops=None, wall: float | None = None) -> list[dict]:
        """Add one frame. `crops` = (left, right) full-res side-conveyor crops for the shape check;
        `wall` = Unix time of the frame for live cameras (None for files). Returns new results."""
        i = self.h.n
        self.h.push([sig[k] for k in KEYS] + [np.nan if wall is None else wall])
        if crops is not None:
            self.crops[i] = crops
            self.crops.pop(i - self.crop_keep, None)
        return self._advance()

    def finish(self) -> list[dict]:
        """End of the stream: decide everything still open (stretches cut by the end are `partial`)."""
        self.finished = True
        return self._advance()

    # ------------------------------------------------------------------ helpers
    @property
    def n(self):
        return self.h.n

    def _t(self, i):
        return i / self.fps

    def _wall(self, i):
        w = self.h.at("wall", i) if 0 <= i < self.n else float("nan")
        return round(w, 3) if w == w else round(self._t(i), 2)

    def _d(self, i):
        if i < self.lag:
            return 0.0
        return self.h.at("belt_white", i) - self.h.at("belt_white", i - self.lag)

    def _held(self, name, i0, i1, thr, hold_s):
        """First index in [i0, i1) where `name` stays above thr for hold_s, else None."""
        need, run = self.cfg.frames(hold_s), 0
        x = self.h.get(name, max(0, i0), i1 + need)
        base = max(0, i0)
        for k, v in enumerate(x):
            run = run + 1 if v > thr else 0
            if run >= need and base + k - need + 1 < i1:
                return base + k - need + 1
        return None

    # ------------------------------------------------------------------ main loop
    def _advance(self) -> list[dict]:
        out: list[dict] = []
        self._scan_drops()
        self._scan_stretches()
        out += self._process_stretches()
        self._resolve_orphans()
        self._landing()
        out += self._emit_sachets()
        self._prune()
        return out

    def _scan_drops(self):
        last = self.n - 1 if self.finished else self.n - 2     # index i needs frame i+1
        while self.scan <= min(last, self.n - 2):
            i = self.scan
            d = self._d(i)
            if d < -self.fall and d <= self._d(i - 1) and d <= self._d(i + 1):
                if self.cand and i - self.cand[0] < self.drop_gap:
                    if d < self.cand[1]:
                        self.cand = (i, d)
                else:
                    if self.cand:
                        self._final_drop(self.cand[0])
                    self.cand = (i, d)
            self.scan += 1
        if self.cand and (self.finished or self.scan - self.cand[0] >= self.drop_gap):
            self._final_drop(self.cand[0])
            self.cand = None

    def _final_drop(self, i):
        bw = self.h.get("belt_white", max(0, i - self.size_back), max(1, i - self.size_skip))
        size = float(np.median(np.sort(bw)[-5:])) if len(bw) else 0.0
        self.sizes.append(size)
        dc = self.cfg["double"]
        local = float(np.median(self.sizes))
        d = dict(id=self.next_sachet_id, idx=i, t=self._t(i), size=size,
                 strip=bool(size >= dc["size_abs"] and size >= dc["size_rel"] * local),
                 used=False, orphan=None, set_id=None, landing=None, hung=False, verdict=None)
        self.next_sachet_id += 1
        self.drops.append(d)
        self.emit_q.append(d)

    def _mask(self, i):
        sc = self.cfg["sets"]
        mo = self.h.get("drop_motion", i - self.half, i + self.half + 1).sum() / self.win
        return self.h.at("drop_meat", i) > sc["meat_min"] and mo > sc["motion_min"]

    def _scan_stretches(self):
        last = self.n - 1 if self.finished else self.n - 1 - self.half
        while self.mask_next <= last:
            self._mask_step(self.mask_next, self._mask(self.mask_next))
            self.mask_next += 1
        if self.finished:
            self._mask_step(self.n, False)                 # the stream end closes any open stretch
            if self.seg:
                self._close(self.seg)
                self.seg = None

    def _mask_step(self, i, v):
        if v:
            if self.open_start is None:
                self.open_start = i
            return
        if self.open_start is not None:
            run = (self.open_start, i)
            self.open_start = None
            if self.seg and run[0] - self.seg[1] <= self.merge_gap:
                self.seg = (self.seg[0], run[1])
            else:
                if self.seg:
                    self._close(self.seg)
                self.seg = run
        elif self.seg and i - self.seg[1] >= self.merge_gap:   # nothing can merge into it any more
            self._close(self.seg)
            self.seg = None

    def _close(self, seg):
        a0, a1 = seg
        if a1 - a0 >= self.min_len:
            edge = a0 <= 2 or (self.finished and a1 >= self.n - 2)
            self.stretches.append(dict(a0=a0, a1=a1, edge=edge))

    def _process_stretches(self) -> list[dict]:
        sc = self.cfg["sets"]
        w0, w1 = sc["drop_window_s"]
        out = []
        while self.stretches:
            s = self.stretches[0]
            reach = s["a1"] + self.cfg.frames(w1) + 1
            if not self.finished and (self.scan <= reach or (self.cand and self.cand[0] <= reach)):
                break                                         # a drop belonging to it may not be final yet
            self.stretches.popleft()
            t0, t1 = self._t(s["a0"]), self._t(s["a1"])
            W = sc["period_window_s"]
            near = [d["t"] for d in self.drops if t0 - W < d["t"] < t1 + W]
            P = float(np.median(np.diff(near))) if len(near) > 3 else 2.5
            P = float(np.clip(P, *sc["period_clip_s"]))
            nsets = 1 + max(0, int(round((t1 - t0 - sc["set_len_s"]) / P)))
            mine = [d for d in self.drops if t0 + w0 <= d["t"] <= t1 + w1 and not d["used"]]
            sid = self.next_set_id
            self.next_set_id += 1
            for d in mine:
                d["used"], d["orphan"], d["set_id"] = True, False, sid
            k = len(mine)
            if k == nsets:
                status = "partial" if s["edge"] else "ok"
            else:
                status = "partial" if s["edge"] else ("MISSING" if k < nsets else "EXTRA")
            dbl = [d for d in mine if d["strip"]]
            if dbl and status in ("ok", "EXTRA"):
                status = "DOUBLE"
            out.append(dict(
                kind="sets", set_group_id=sid, frame_start=s["a0"], frame_end=s["a1"],
                t0=round(t0, 2), t1=round(t1, 2), timestamp=self._wall(s["a0"]),
                sets=nsets, sachets=k,
                missing=max(0, nsets - k) if status == "MISSING" else 0,
                extra=max(0, k - nsets) if status == "EXTRA" else 0,
                double_strips=len(dbl) if status == "DOUBLE" else 0,
                status=status, label=self.cfg.get("labels", {}).get("sets", {}).get(status, status),
                alert=self.cfg["alerts"]["sets"][status],
                period_s=round(P, 2), sachet_ids=[d["id"] for d in mine],
                drop_times=[round(d["t"], 2) for d in mine],
                double_strip_times=[round(d["t"], 2) for d in dbl]))
        return out

    def _resolve_orphans(self):
        w0 = self.cfg["sets"]["drop_window_s"][0]
        starts = [s["a0"] for s in self.stretches]
        if self.seg:
            starts.append(self.seg[0])
        if self.open_start is not None:
            starts.append(self.open_start)
        first_open = min(starts) if starts else None
        for d in self.drops:
            if d["used"] or d["orphan"] is not None:
                continue
            if self.finished:
                d["orphan"] = True
                continue
            if self.mask_next <= d["idx"]:
                break                                         # the set under it may not be seen yet
            if first_open is not None and self._t(first_open) + w0 <= d["t"]:
                break                                         # an open stretch may still claim it
            d["orphan"] = True

    def _landing(self):
        lc = self.cfg["landing"]
        f = self.cfg.frames
        need = self.watch + max(f(lc["stuck_hold_s"]), f(lc["outside_hold_s"]))
        p0, p1 = (f(x) for x in lc["passed_window_s"])
        for d in self.drops:
            if d["landing"] is not None:
                continue
            i = d["idx"]
            if not self.finished and self.n - 1 < i + need:
                break
            passed = bool(self.h.get("CH_fg", max(0, i + p0), i + p1).max(initial=0) > lc["passed_min"])
            stuck = self._held("CH_fg", i + f(0.3), i + self.watch, lc["stuck_min"], lc["stuck_hold_s"])
            side, at, rejected = None, None, []
            for name in ("L", "R"):
                j = self._held(f"{name}_fg", i + f(0.2), i + self.watch, lc["outside_min"], lc["outside_hold_s"])
                if j is None:
                    continue
                sh = self._shape(name, j)
                if sh is not None and not sachet_like(sh, lc["shape"]):
                    rejected.append(dict(side=name, t=round(self._t(j), 2), **sh))
                    continue
                if side is None:
                    side, at = name, j
            d["landing"] = dict(passed=passed, stuck=stuck, side=side, at=at, rejected=rejected)

    def _shape(self, name, j):
        sc = self.cfg["landing"]["shape"]
        f = self.cfg.frames
        b = self.crops.get(max(0, j - f(sc["before_s"])))
        a = self.crops.get(min(self.n - 1, j + f(sc["after_s"])))
        if b is None or a is None:
            return None                                       # no frames kept (signal-only replay): trust the signal
        k = 0 if name == "L" else 1
        return blob_shape(b[k], a[k])

    def _verdict(self, d):
        """Returns the verdict, or None while it cannot be decided yet."""
        L = d["landing"]
        if L is None:
            return None
        if L["side"] is not None:
            return "OUTSIDE BAG"
        if d["orphan"] is None and not d["used"]:
            return None
        lc = self.cfg["landing"]
        if L["stuck"] is not None and d["used"]:
            e = L["stuck"]
            while e < self.n and self.h.at("CH_fg", e) > lc["stuck_min"]:
                e += 1
            if e >= self.n and not self.finished:
                if self.n - 1 - L["stuck"] >= self.cfg.frames(lc["stuck_max_wait_s"]):
                    return "STUCK IN CHUTE"
                return None
            limit = self._t(e) + lc["hang_next_s"]
            if not self.finished and (self.scan <= e + self.cfg.frames(lc["hang_next_s"]) + 1 or self.cand):
                return None                                   # the next drop may not be final yet
            nxt = next((x for x in self.drops if x["idx"] > d["idx"]), None)
            if nxt is not None and nxt["t"] <= limit:
                nxt["hung"] = True                            # it was the NEXT sachet hanging; it then fell
                return "IN BAG"
            return "STUCK IN CHUTE"
        if L["passed"]:
            return "EMPTY BAG" if d["orphan"] else "IN BAG"
        return "NOT SEEN"

    def _emit_sachets(self) -> list[dict]:
        out = []
        while self.emit_q:
            d = self.emit_q[0]
            v = self._verdict(d)
            if v is None:
                break
            self.emit_q.popleft()
            d["verdict"] = v
            L = d["landing"]
            out.append(dict(
                kind="sachet", sachet_id=d["id"], frame_index=d["idx"], t=round(d["t"], 2),
                timestamp=self._wall(d["idx"]), verdict=v, label=self.cfg.get("labels", {}).get("sachet", {}).get(v, v),
                in_bag=v == "IN BAG",
                alert=self.cfg["alerts"]["sachet"][v], no_tray=bool(d["orphan"]), set_group_id=d["set_id"],
                double_strip=bool(d["strip"] and d["used"]), size=round(d["size"], 3),
                passed_slot=L["passed"], outside_side={"L": "left", "R": "right"}.get(L["side"]),
                outside_t=round(self._t(L["at"]), 2) if L["at"] is not None else None,
                hung_in_chute_before_falling=d["hung"],
                rejected_outside=L["rejected"]))
        return out

    def _prune(self):
        keep_t = self._t(self.n) - 2 * self.cfg["sets"]["period_window_s"] - 30
        while len(self.drops) > 2 and self.drops[0]["verdict"] is not None and self.drops[0]["t"] < keep_t:
            self.drops.pop(0)
