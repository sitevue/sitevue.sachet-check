"""Check the streaming checker against the batch prototype (research/prototype) on saved signals.

  python tools/compare_with_batch.py SIGNALS.npz LAND.npz BATCH_v3.json BATCH_landing.json [VIDEO]

SIGNALS.npz / LAND.npz are what research/prototype/signals.py and landing_signals.py write;
the JSONs are match3.py and landing_verdict.py output. VIDEO enables the sachet-shape check (slow seeks).
"""
import json
import sys
from collections import Counter

import cv2
import numpy as np

from sachet_check import Config, SachetChecker


def main(sig, land, v3, lv, video=None):
    z, zl = np.load(sig), np.load(land)
    a, ka, b, kb = z["a"], list(z["keys"]), zl["a"], list(zl["keys"])
    cfg = Config.load().with_fps(float(z["fps"]))
    eng = SachetChecker(cfg)
    if video:                                    # serve side-conveyor crops on demand instead of a ring
        cap, (x0, y0, x1, y1), (u0, v0, u1, v1) = cv2.VideoCapture(video), cfg["regions"]["left"], cfg["regions"]["right"]

        class Lazy(dict):
            def get(self, i, default=None):
                cap.set(cv2.CAP_PROP_POS_FRAMES, i)
                ok, f = cap.read()
                return (f[y0:y1, x0:x1], f[v0:v1, u0:u1]) if ok else default
        eng.crops = Lazy()
        eng.crop_keep = 10 ** 9
    res = []
    for i in range(len(a)):
        s = {k: float(a[i, ka.index(k)]) for k in ("belt_white", "drop_meat", "drop_motion")}
        s.update({k: float(b[i, kb.index(k)]) for k in ("L_fg", "R_fg", "CH_fg")})
        res += eng.push(s)
    res += eng.finish()
    B, BL = json.load(open(v3)), json.load(open(lv))

    sach = [r for r in res if r["kind"] == "sachet"]
    bd = [round(x, 1) for x in B["drops"]]
    sd = [round(r["t"], 1) for r in sach]
    print(f"drops: stream {len(sd)}  batch {len(bd)}  identical times: {sd == bd}")
    bs = {(s["t0"], s["t1"]): s for s in B["stretches"]}
    ss = {(r["t0"], r["t1"]): r for r in res if r["kind"] == "sets"}
    print(f"stretches: stream {len(ss)}  batch {len(bs)}  same boundaries: {set(round(k[0],1) for k in ss) == set(k[0] for k in bs)}")
    diff = [(k, bs[k]["status"], ss[(k[0], k[1])]["status"]) for k in bs if (k[0], k[1]) in ss and bs[k]["status"] != ss[(k[0], k[1])]["status"]]
    print(f"stretch status: batch {dict(Counter(s['status'] for s in B['stretches']))}")
    print(f"                stream {dict(Counter(r['status'] for r in ss.values()))}")
    for k, x, y in diff:
        print(f"   differs at {k[0]:.1f}-{k[1]:.1f} s: batch {x}, stream {y}")
    bo, so = set(B["orphans"]), set(round(r["t"], 1) for r in sach if r["no_tray"])
    print(f"no-tray drops: stream {len(so)}  batch {len(bo)}  same: {so == bo}")
    bv = {round(r["t"], 1): r["verdict"] for r in BL["drops"]}
    sv = {round(r["t"], 1): r["verdict"] for r in sach}
    print(f"landing batch  {dict(Counter(bv.values()))}")
    print(f"landing stream {dict(Counter(sv.values()))}")
    for t in sorted(set(bv) | set(sv)):
        if bv.get(t) != sv.get(t):
            print(f"   differs at {t:.1f} s: batch {bv.get(t)}, stream {sv.get(t)}")
    lat = [(r["frame_end"] if r["kind"] == "sets" else r["frame_index"]) for r in res]
    return res


if __name__ == "__main__":
    main(*sys.argv[1:])
