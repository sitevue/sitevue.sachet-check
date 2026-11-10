"""Sachets riding on the trays: a sachet added by hand instead of by the dispenser.

When the dispenser is stopped, workers put sachets on the trays by hand. Those never fall off the blue
belt, so without this the set reads MISSING. A hand-placed sachet is a bright white object on the tray
that travels down into the bag with it. Two shapes are seen from grind-04:

  slab   lying flat on the meat: sachet-sized, roughly rectangular, with meat around it
  strip  tucked at the seam between two trays, partly under the next one: a thin white band, much
         wider than tall, with tray rim (not meat) around it

Either only counts when it MOVES DOWN WITH THE TRAYS over several frames. That is what rejects white
steel, bag film glare and labels: they stay put, or (film) are tall rather than flat.

Per frame, `tray_blobs` lists the white blobs in the `tray` box (full-resolution pixels). `TraySachets`
links them frame to frame into tracks and answers "did a sachet ride through between frames i0 and i1?".
"""
from __future__ import annotations

import cv2
import numpy as np

# blob tuple fields
A, X, Y, W, H, RECT, ASPECT, MEAT = range(8)


def tray_blobs(frame, cfg) -> list[tuple]:
    """White blobs in the tray box: (area, x, y, w, h, rectangularity, aspect, meat_ring), x/y full-res."""
    hc, c = cfg["hand_added"], cfg["colors"]
    x0, y0, x1, y1 = cfg["regions"]["tray"]
    hsv = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
    white = ((hsv[..., 1] < c["white"]["s_max"]) & (hsv[..., 2] > c["white"]["v_min"])).astype(np.uint8)
    k = hc["open_px"]
    white = cv2.morphologyEx(white, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    m, h = c["meat"], hsv[..., 0]
    meat = (((h < m["h_low_max"]) | (h > m["h_high_min"])) & (hsv[..., 1] > m["s_min"])).astype(np.uint8)
    ring_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (hc["ring_px"], hc["ring_px"]))
    pad = hc["ring_px"] + 5
    n, lab, st, _ = cv2.connectedComponentsWithStats(white, connectivity=8)
    out = []
    for j in range(1, n):
        a = int(st[j, cv2.CC_STAT_AREA])
        if a < hc["min_blob_px"]:
            continue
        x, y, w, hh = (int(v) for v in st[j, :4])
        sl = (slice(max(0, y - pad), y + hh + pad), slice(max(0, x - pad), x + w + pad))
        mask = (lab[sl] == j).astype(np.uint8)
        cnt, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        (_, _), (rw, rh), _ = cv2.minAreaRect(max(cnt, key=cv2.contourArea))
        ring = cv2.dilate(mask, ring_k) - mask
        meat_ring = float(meat[sl][ring > 0].mean()) if ring.any() else 0.0
        out.append((a, x + x0, y + y0, w, hh, round(a / max(rw * rh, 1.0), 3),
                    round(max(rw, rh) / max(min(rw, rh), 1.0), 2), round(meat_ring, 3)))
    return out


class TraySachets:
    """Frame-to-frame tracks of white blobs moving down with the trays."""

    def __init__(self, cfg):
        self.cfg = cfg
        hc = cfg["hand_added"]
        self.b, self.t, self.slab_r, self.strip_r = hc["blob"], hc["track"], hc["slab"], hc["strip"]
        self.open: list[list] = []        # tracks still able to grow: [(frame, blob), ...]
        self.closed: list[list] = []      # finished tracks that qualify as a sachet

    # --- shapes
    def _cand(self, b):
        r = self.b
        return (r["area"][0] <= b[A] <= r["area"][1] and r["w"][0] <= b[W] <= r["w"][1]
                and r["h"][0] <= b[H] <= r["h"][1] and b[Y] > r["y_min"])

    def is_slab(self, b):
        r = self.slab_r
        cy = b[Y] + b[H] / 2
        return (r["area"][0] <= b[A] <= r["area"][1] and r["aspect"][0] <= b[ASPECT] <= r["aspect"][1]
                and b[RECT] >= r["rect_min"] and b[MEAT] >= r["meat_ring_min"] and r["y"][0] <= cy <= r["y"][1])

    def is_strip(self, b):
        r = self.strip_r
        return b[W] >= r["w_over_h"] * b[H] and b[H] <= r["h_max"] and r["area"][0] <= b[A] <= r["area"][1]

    def qualifies(self, tr) -> str | None:
        """'slab' / 'strip' if the track is a sachet riding down with the trays, else None."""
        t = self.t
        if len(tr) < t["min_frames"]:
            return None
        cy = lambda b: b[Y] + b[H] / 2
        if cy(tr[-1][1]) - cy(tr[0][1]) < t["min_drop_px"]:
            return None                                       # did not move down: machine, glare, label
        if any(self.is_slab(b) for _, b in tr):
            return "slab"
        if sum(self.is_strip(b) for _, b in tr) >= self.strip_r["frac"] * len(tr):
            return "strip"
        return None

    # --- streaming
    def push(self, i: int, blobs) -> None:
        t = self.t
        fr = [b for b in (blobs or []) if self._cand(b)]
        used, keep = set(), []
        for tr in self.open:
            j, pb = tr[-1]
            if i - j > t["max_gap_frames"]:
                if self.qualifies(tr):
                    self.closed.append(tr)
                continue
            best = None
            for k, b in enumerate(fr):
                if k in used:
                    continue
                dx = abs((b[X] + b[W] / 2) - (pb[X] + pb[W] / 2))
                dy = (b[Y] + b[H] / 2) - (pb[Y] + pb[H] / 2)
                ratio = b[A] / pb[A]
                if (dx <= t["dx_px"] and t["dy_px"][0] * (i - j) <= dy <= t["dy_px"][1] * (i - j)
                        and t["size_ratio"] <= ratio <= 1 / t["size_ratio"]):
                    if best is None or dy < best[1]:
                        best = (k, dy)
            if best:
                used.add(best[0])
                tr.append((i, fr[best[0]]))
            keep.append(tr)
        keep += [[(i, b)] for k, b in enumerate(fr) if k not in used]
        self.open = keep

    def seen(self, i0: int, i1: int) -> list[tuple[str, list]]:
        """Qualifying tracks that ride through frames [i0, i1]: [(kind, track), ...], one per sachet."""
        out = []
        for tr in self.closed + self.open:
            a, b = tr[0][0], tr[-1][0]
            if i0 <= a <= i1 or (a < i0 <= b):
                kind = self.qualifies(tr)
                if kind:
                    out.append((kind, tr))
        return out

    def prune(self, before: int) -> None:
        self.closed = [tr for tr in self.closed if tr[-1][0] >= before]
