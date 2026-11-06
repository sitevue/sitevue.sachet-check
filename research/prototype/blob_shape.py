# Shape of the new white blob in a side region: compares a frame just after the event with one 1.5 s before.
import cv2, numpy as np
REG = {'L': (380, 700, 670, 1010), 'R': (1150, 720, 1500, 1010)}
def grab(v, t):
    v.set(cv2.CAP_PROP_POS_FRAMES, int(round(t * 10))); ok, f = v.read(); return f
def shape(video, side, t_event, before=1.5, after=0.6):
    v = cv2.VideoCapture(video); x0, y0, x1, y1 = REG[side]
    a = grab(v, t_event - before)[y0:y1, x0:x1]; b = grab(v, t_event + after)[y0:y1, x0:x1]
    hb = cv2.cvtColor(b, cv2.COLOR_BGR2HSV)
    diff = np.abs(hb[..., 2].astype(int) - cv2.cvtColor(a, cv2.COLOR_BGR2HSV)[..., 2].astype(int))
    m = ((diff > 30) & (hb[..., 1] < 70) & (hb[..., 2] > 150)).astype(np.uint8)
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)); m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    if n < 2: return {'area': 0, 'rect': 0, 'aspect': 0, 'touches_edge': False}
    j = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA])); area = int(st[j, cv2.CC_STAT_AREA])
    cnt, _ = cv2.findContours((lab == j).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    (cx, cy), (w, h), ang = cv2.minAreaRect(max(cnt, key=cv2.contourArea))
    bx, by, bw_, bh = st[j, 0], st[j, 1], st[j, 2], st[j, 3]; H_, W_ = m.shape
    edge = bx <= 2 or by <= 2 or bx + bw_ >= W_ - 2 or by + bh >= H_ - 2
    return {'area': area, 'rect': round(area / max(1, w * h), 2), 'aspect': round(max(w, h) / max(1, min(w, h)), 2), 'touches_edge': bool(edge)}

def sachet_like(sh):
    return 8000 <= sh['area'] <= 35000 and sh['rect'] >= 0.72 and 1.1 <= sh['aspect'] <= 2.5 and not sh.get('touches_edge', True)
