import cv2, numpy as np, sys
v = cv2.VideoCapture(sys.argv[1]); out = sys.argv[2]
ROIS = {  # x0,y0,x1,y1 in full-res pixels
 'belt': (935, 0, 1125, 365),     # sachet riding the blue belt
 'drop': (900, 370, 1140, 720),   # guide + landing spot
 'lane': (770, 600, 1100, 1080),  # tray sets entering the bag
}
rows=[]; prev=None
while True:
    ok, f = v.read()
    if not ok: break
    hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
    white = (hsv[...,1] < 50) & (hsv[...,2] > 190)
    meat = ((hsv[...,0] < 12) | (hsv[...,0] > 165)) & (hsv[...,1] > 70) & (hsv[...,2] > 90)
    g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
    r = {}
    for k,(x0,y0,x1,y1) in ROIS.items():
        r[k+'_white'] = white[y0:y1,x0:x1].mean()
        r[k+'_meat'] = meat[y0:y1,x0:x1].mean()
        r[k+'_motion'] = 0.0 if prev is None else (cv2.absdiff(g,prev)[y0:y1,x0:x1] > 25).mean()
    prev = g; rows.append(r)
keys = list(rows[0]); a = np.array([[r[k] for k in keys] for r in rows])
np.savez(out, a=a, keys=keys, fps=v.get(cv2.CAP_PROP_FPS))
print(a.shape)
