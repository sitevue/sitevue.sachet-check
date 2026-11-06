# Per-frame "new white object" area in the regions OUTSIDE the bag (side conveyors) and in the chute slot.
# Background = slow running average; a sachet that lands and stays shows up as new white pixels vs background.
import cv2, numpy as np, sys
video, out = sys.argv[1], sys.argv[2]
REG = {'L': (380, 700, 670, 1010), 'R': (1150, 720, 1500, 1010), 'CHUTE': (905, 375, 1135, 470)}
v = cv2.VideoCapture(video); n = int(v.get(cv2.CAP_PROP_FRAME_COUNT)); bg = {}; rows = []; i = 0
while True:
    ok, f = v.read()
    if not ok: break
    r = []
    for k, (x0, y0, x1, y1) in REG.items():
        c = cv2.resize(f[y0:y1, x0:x1], ((x1 - x0) // 2, (y1 - y0) // 2), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(c, cv2.COLOR_BGR2HSV); g = hsv[..., 2].astype(np.float32)
        white = (hsv[..., 1] < 70) & (hsv[..., 2] > 150)
        if k not in bg: bg[k] = g.copy()
        fg = (np.abs(g - bg[k]) > 30) & white
        a = np.where(fg, 0.004, 0.04).astype(np.float32)      # foreground absorbed slowly (~25 s), rest quickly
        bg[k] += a * (g - bg[k])
        r += [fg.mean(), white.mean()]
    rows.append(r); i += 1
    if i % 3000 == 0: print(f'{i}/{n}', flush=True)
np.savez(out, a=np.array(rows, np.float32), keys=['L_fg', 'L_white', 'R_fg', 'R_white', 'CH_fg', 'CH_white'], fps=v.get(cv2.CAP_PROP_FPS))
print('done', len(rows))
