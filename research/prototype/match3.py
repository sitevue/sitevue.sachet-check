# v3: tray-set stretches (meat moving in drop zone) vs sachet drops (sharp falls in belt white), counted per stretch
import numpy as np, sys, json
z=np.load(sys.argv[1]); a=z['a']; keys=list(z['keys']); fps=float(z['fps']); N=len(a)
s=lambda k:a[:,keys.index(k)]; sm=lambda x,w:np.convolve(x,np.ones(w)/w,'same')
L=2.05            # time one set occupies the drop zone (s)
def segs(mask,gap,minlen):
    out=[];st=None
    for i,v in enumerate(list(mask)+[False]):
        if v and st is None: st=i
        if not v and st is not None: out.append([st,i]); st=None
    m=[]
    for x in out:
        if m and x[0]-m[-1][1]<=gap: m[-1][1]=x[1]
        else: m.append(x)
    return [x for x in m if x[1]-x[0]>=minlen]
# sachet drops
bw=s('belt_white'); LAG=3; d=np.r_[np.zeros(LAG),bw[LAG:]-bw[:-LAG]]
drops=[]
for i in range(1,N-1):
    if d[i]<-0.15 and d[i]<=d[i-1] and d[i]<=d[i+1]:
        if drops and i-drops[-1]<int(1.0*fps):
            if d[i]<d[drops[-1]]: drops[-1]=i
        else: drops.append(i)
dt=np.array(drops)/fps
# sachet size on the belt just before each drop (top-5 median over the preceding 1.3 s).
# A joined double strip covers ~0.66-0.74 of the belt box vs ~0.38 for a single (p99 0.55).
DBL_ABS, DBL_REL = 0.60, 1.5
size=np.array([np.median(np.sort(bw[max(0,i-15):max(1,i-2)])[-5:]) for i in drops]) if drops else np.array([])
local=np.array([np.median(size[max(0,k-20):k+21]) for k in range(len(size))])
strip=(size>=DBL_ABS)&(size>=DBL_REL*local)
# tray-set stretches: meat present AND drop zone moving (excludes a tray parked during a stop)
moving=sm(s('drop_motion'),5)>0.06
st=segs((s('drop_meat')>0.02)&moving,3,5)
res=[];used=set()
for a0,a1 in st:
    t0,t1=a0/fps,a1/fps
    near=dt[(dt>t0-30)&(dt<t1+30)]; P=np.median(np.diff(near)) if len(near)>3 else 2.5
    P=float(np.clip(P,2.0,4.0))
    n=1+max(0,int(round((t1-t0-L)/P)))
    idx=[k for k,x in enumerate(dt) if t0+0.15<=x<=t1+0.3 and k not in used]
    used.update(idx)
    edge=a0<=2 or a1>=N-2
    st_=('partial' if edge else 'ok') if len(idx)==n else ('partial' if edge else ('MISSING' if len(idx)<n else 'EXTRA'))
    dbl=[k for k in idx if strip[k]]       # only counted when it lands on a moving tray set (occlusions had no tray)
    if dbl and st_ in ('ok','EXTRA'): st_='DOUBLE'
    res.append({'t0':round(t0,1),'t1':round(t1,1),'sets':n,'drops':len(idx),'period':round(P,2),'status':st_,'drop_times':[round(float(dt[k]),1) for k in idx],
                'double_strip_times':[round(float(dt[k]),1) for k in dbl],'sachet_size':[round(float(size[k]),2) for k in idx]})
orph=[round(float(x),1) for k,x in enumerate(dt) if k not in used]
tot=sum(r['sets'] for r in res if r['status']!='partial')
summ={'sets_est':tot,'drops':len(drops),'stretches':len(res),'missing_sets':sum(r['sets']-r['drops'] for r in res if r['status']=='MISSING'),
      'extra_drops':sum(r['drops']-r['sets'] for r in res if r['status']=='EXTRA'),'double_sets':sum(len(r['double_strip_times']) for r in res if r['status']=='DOUBLE'),
      'flagged_stretches':sum(r['status'] in('MISSING','EXTRA','DOUBLE') for r in res),'orphan_drops':len(orph),
      'oversized_orphans_ignored':[round(float(dt[k]),1) for k in range(len(dt)) if strip[k] and k not in used]}
print(json.dumps(summ))
for r in res:
    if r['status'] in ('MISSING','EXTRA','DOUBLE'): print('  %s %.1f-%.1f sets=%d drops=%d P=%.2f %s size=%s'%(r['status'],r['t0'],r['t1'],r['sets'],r['drops'],r['period'],r['drop_times'],r['sachet_size']))
print('  orphans:',orph[:40])
json.dump({'summary':summ,'stretches':res,'orphans':orph,'drops':[round(float(x),2) for x in dt]},open(sys.argv[2],'w'),indent=1)
