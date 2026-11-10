"""Video source -> results. One CPU core keeps up with the 10 fps camera several times over."""
from __future__ import annotations

import os
import time
from typing import Iterator

import cv2

from .config import Config
from .engine import SachetChecker
from .signals import FrameSignals


def open_source(source):
    src = int(source) if isinstance(source, str) and source.isdigit() else source
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video source {source!r}")
    return cap


class SachetPipeline:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.stats = dict(frames=0, signal_ms=0.0, engine_ms=0.0)

    def run(self, source, realtime: bool = False, start_s: float = 0.0, duration_s: float | None = None,
            with_signals: bool = False) -> Iterator[dict]:
        """Yields result dicts (see docs/output.md). For a file, times are seconds into the file and
        `timestamp` = `t`; for a live camera `timestamp` is Unix time. `with_signals` also yields one
        {"kind": "frame", ...} per frame with the raw measurements (for review overlays)."""
        cap = open_source(source)
        live = not (isinstance(source, str) and os.path.isfile(source))
        cfg = self.cfg.with_fps(cap.get(cv2.CAP_PROP_FPS))
        if start_s and not live:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(start_s * cfg.fps)))
        sig, eng = FrameSignals(cfg), SachetChecker(cfg)
        offset = 0.0 if live else start_s
        last_n = None if duration_s is None else int(round(duration_s * cfg.fps))
        t_start, n = time.time(), 0
        try:
            while last_n is None or n < last_n:
                ok, frame = cap.read()
                if not ok:
                    break
                if realtime and not live:
                    lag = t_start + n / cfg.fps - time.time()
                    if lag > 0:
                        time.sleep(lag)
                t0 = time.perf_counter()
                frame = sig.fit(frame)
                s = sig.compute(frame)
                crops = sig.side_crops(frame)
                t1 = time.perf_counter()
                res = eng.push(s, crops, wall=time.time() if live else None)
                t2 = time.perf_counter()
                self.stats["frames"] += 1
                self.stats["signal_ms"] += 1000 * (t1 - t0)
                self.stats["engine_ms"] += 1000 * (t2 - t1)
                if with_signals:
                    yield dict(kind="frame", frame_index=n, t=round(offset + n / cfg.fps, 2), **{k: round(v, 4) for k, v in s.items() if k != "tray_blobs"})
                for r in res:
                    yield _shift(r, offset)
                n += 1
            for r in eng.finish():
                yield _shift(r, offset)
        finally:
            cap.release()


def _shift(r, offset):
    """Results from a file started at start_s report times in the file, not in the cut."""
    if not offset:
        return r
    r = dict(r)
    for k in ("t", "t0", "t1", "timestamp", "outside_t"):
        if r.get(k) is not None:
            r[k] = round(r[k] + offset, 2)
    for k in ("drop_times", "double_strip_times"):
        if k in r:
            r[k] = [round(x + offset, 2) for x in r[k]]
    return r
