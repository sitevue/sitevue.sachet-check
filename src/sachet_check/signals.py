"""Per-frame pixel measurements in fixed boxes of the camera image. No model, CPU only.

Each frame gives seven numbers:

  belt_white   fraction of the belt box that is white (a sachet on the belt)
  drop_meat    fraction of the drop box that is red meat (a tray set under the chute)
  drop_motion  fraction of the drop box that changed since the last frame (the set is moving)
  L_fg, R_fg   fraction of each side-conveyor box covered by a NEW white object
  CH_fg        fraction of the chute slot covered by a NEW white object (a sachet falling through)
  hand         largest white blob in the reach box, as a fraction of the box (a worker's white sleeve
               reaching in beside the chute)

plus `tray_blobs`: the white blobs in the tray box (tray.py), for sachets added by hand.

Frames of another size (e.g. a 1280x720 export) are resized to the configured `frame_size` first, so
the boxes, which are in full-resolution pixels, still fit (`fit`).

"New" = differs from a slow running background, so the conveyors, bag film and steel do not count
but a sachet that lands and stays does.
"""
from __future__ import annotations

import cv2
import numpy as np

from .config import Config
from .tray import tray_blobs

KEYS = ("belt_white", "drop_meat", "drop_motion", "L_fg", "R_fg", "CH_fg", "hand")


def _crop(frame, box):
    x0, y0, x1, y1 = box
    return frame[y0:y1, x0:x1]


class FrameSignals:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        r = cfg["regions"]
        self.boxes = dict(belt=r["belt"], drop=r["drop"], L=r["left"], R=r["right"], CH=r["chute"], reach=r["reach"])
        self.prev_drop_grey = None
        self.bg: dict[str, np.ndarray] = {}

    def fit(self, frame):
        """The frame at the configured frame_size (the boxes are in those pixels)."""
        w, h = self.cfg.get("frame_size", [frame.shape[1], frame.shape[0]])
        if frame.shape[1] != w or frame.shape[0] != h:
            frame = cv2.resize(frame, (int(w), int(h)), interpolation=cv2.INTER_LINEAR)
        return frame

    def side_crops(self, frame):
        """Full-resolution crops of the side conveyors, kept for the sachet-shape check."""
        return _crop(frame, self.boxes["L"]).copy(), _crop(frame, self.boxes["R"]).copy()

    def compute(self, frame) -> dict:
        """Pass frames through `fit` first (the pipeline does)."""
        c = self.cfg["colors"]
        out = {}

        hsv = cv2.cvtColor(_crop(frame, self.boxes["belt"]), cv2.COLOR_BGR2HSV)
        out["belt_white"] = float(((hsv[..., 1] < c["white"]["s_max"]) & (hsv[..., 2] > c["white"]["v_min"])).mean())

        drop = _crop(frame, self.boxes["drop"])
        hsv = cv2.cvtColor(drop, cv2.COLOR_BGR2HSV)
        m = c["meat"]
        h = hsv[..., 0]
        meat = ((h < m["h_low_max"]) | (h > m["h_high_min"])) & (hsv[..., 1] > m["s_min"]) & (hsv[..., 2] > m["v_min"])
        out["drop_meat"] = float(meat.mean())
        grey = cv2.cvtColor(drop, cv2.COLOR_BGR2GRAY)
        if self.prev_drop_grey is None:
            out["drop_motion"] = 0.0
        else:
            out["drop_motion"] = float((cv2.absdiff(grey, self.prev_drop_grey) > c["motion_diff"]).mean())
        self.prev_drop_grey = grey

        hsv = cv2.cvtColor(_crop(frame, self.boxes["reach"]), cv2.COLOR_BGR2HSV)
        white = ((hsv[..., 1] < c["white"]["s_max"]) & (hsv[..., 2] > c["white"]["v_min"])).astype(np.uint8)
        n, _, st, _ = cv2.connectedComponentsWithStats(white, connectivity=8)
        out["hand"] = float(st[1:, cv2.CC_STAT_AREA].max() / white.size) if n > 1 else 0.0

        lc = self.cfg["landing"]
        for k in ("L", "R", "CH"):
            x0, y0, x1, y1 = self.boxes[k]
            small = cv2.resize(_crop(frame, self.boxes[k]), (int((x1 - x0) * lc["scale"]), int((y1 - y0) * lc["scale"])),
                               interpolation=cv2.INTER_AREA)
            hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
            v = hsv[..., 2].astype(np.float32)
            white = (hsv[..., 1] < lc["white"]["s_max"]) & (hsv[..., 2] > lc["white"]["v_min"])
            if k not in self.bg:
                self.bg[k] = v.copy()
            fg = (np.abs(v - self.bg[k]) > lc["diff"]) & white
            rate = np.where(fg, lc["bg_rate_fg"], lc["bg_rate"]).astype(np.float32)   # a new object is absorbed slowly
            self.bg[k] += rate * (v - self.bg[k])
            out[f"{k}_fg"] = float(fg.mean())
        if "hand_added" in self.cfg:
            out["tray_blobs"] = tray_blobs(frame, self.cfg)
        return out
