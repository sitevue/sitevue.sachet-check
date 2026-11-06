# Synthetic test: paste a real sachet (cut from the belt) onto the right conveyor, the left conveyor and the chute slot.
import cv2, numpy as np, sys
src, out = sys.argv[1], sys.argv[2]
v = cv2.VideoCapture(src); v.set(cv2.CAP_PROP_POS_FRAMES, 300); ok, f = v.read()      # t=30.0: sachet on belt
hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV); m = ((hsv[..., 1] < 50) & (hsv[..., 2] > 190)).astype(np.uint8)
m[:, :935] = 0; m[:, 1125:] = 0; m[365:] = 0
ys, xs = np.nonzero(m); y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
patch, pm = f[y0:y1, x0:x1].copy(), m[y0:y1, x0:x1]
def place(fr, p, msk, cx, cy, ang, scale=0.8):
    p = cv2.resize(p, None, fx=scale, fy=scale); msk = cv2.resize(msk, None, fx=scale, fy=scale)
    h, w = msk.shape; M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
    p = cv2.warpAffine(p, M, (w, h)); msk = cv2.warpAffine(msk, M, (w, h)) > 0
    ys, xs = cy - h // 2, cx - w // 2; roi = fr[ys:ys + h, xs:xs + w]; roi[msk] = p[msk]
EVENTS = [(31.0, 37.0, 1320, 860, 25, 0.8), (75.0, 80.0, 520, 860, -30, 0.8), (113.4, 118.0, 1020, 420, 90, 0.45)]
v = cv2.VideoCapture(src); w = cv2.VideoWriter(out, cv2.VideoWriter_fourcc(*'mp4v'), 10, (1920, 1080)); i = 0
while True:
    ok, fr = v.read()
    if not ok: break
    t = i / 10
    for a, b, cx, cy, ang, sc in EVENTS:
        if a <= t < b: place(fr, patch, pm, cx, cy, ang, sc)
    w.write(fr); i += 1
w.release(); print('patch', patch.shape, 'events', EVENTS)
