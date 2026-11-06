import cv2, numpy as np, sys, json
# args: out.jpg then items "video|t_start|label" ; 16 tiles at 0.3s from t_start
out=sys.argv[1]; rows=[]
for it in sys.argv[2:]:
    vid,t0,lab=it.split('|'); t0=float(t0); v=cv2.VideoCapture(vid); tiles=[]
    for k in range(16):
        t=t0+0.3*k; v.set(cv2.CAP_PROP_POS_FRAMES,int(round(t*10))); ok,f=v.read()
        c=cv2.resize(f[0:1000,760:1180],(105,250)); cv2.putText(c,'%.1f'%t,(2,12),0,.38,(0,255,255),1); tiles.append(c)
    r=np.hstack(tiles); h=np.zeros((22,r.shape[1],3),np.uint8); cv2.putText(h,lab,(4,16),0,.55,(255,255,255),1); rows.append(np.vstack([h,r]))
cv2.imwrite(out,np.vstack(rows))
