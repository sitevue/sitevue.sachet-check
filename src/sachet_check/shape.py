"""Is the new white thing on a side conveyor shaped like a sachet?

Compares a side-conveyor crop from just after the object appeared with one from before it, and
measures the biggest new white blob. Rejects bag film, exposure changes, arms, sleeves, hard hats.
"""
from __future__ import annotations

import cv2
import numpy as np


def blob_shape(before, after) -> dict:
    hb = cv2.cvtColor(after, cv2.COLOR_BGR2HSV)
    ha = cv2.cvtColor(before, cv2.COLOR_BGR2HSV)
    diff = np.abs(hb[..., 2].astype(int) - ha[..., 2].astype(int))
    m = ((diff > 30) & (hb[..., 1] < 70) & (hb[..., 2] > 150)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    if n < 2:
        return dict(area=0, rect=0.0, aspect=0.0, touches_edge=False)
    j = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    area = int(st[j, cv2.CC_STAT_AREA])
    cnt, _ = cv2.findContours((lab == j).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    (_, _), (w, h), _ = cv2.minAreaRect(max(cnt, key=cv2.contourArea))
    bx, by, bw, bh = st[j, 0], st[j, 1], st[j, 2], st[j, 3]
    H, W = m.shape
    edge = bx <= 2 or by <= 2 or bx + bw >= W - 2 or by + bh >= H - 2
    return dict(area=area, rect=round(area / max(1.0, w * h), 2), aspect=round(max(w, h) / max(1.0, min(w, h)), 2),
                touches_edge=bool(edge))


def sachet_like(sh: dict, rule: dict) -> bool:
    a0, a1 = rule["area"]
    r0, r1 = rule["aspect"]
    return a0 <= sh["area"] <= a1 and sh["rect"] >= rule["rect_min"] and r0 <= sh["aspect"] <= r1 \
        and not sh.get("touches_edge", True)
