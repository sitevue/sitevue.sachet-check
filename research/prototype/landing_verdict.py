# Per sachet drop: did it pass the chute slot, and did anything land and stay outside the bag / in the chute?
import numpy as np, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from blob_shape import shape, sachet_like
land, res, out = sys.argv[1], sys.argv[2], sys.argv[3]
video = sys.argv[4] if len(sys.argv) > 4 else None   # enables the sachet-shape check on outside candidates
rejected = []
z = np.load(land); a = z['a']; k = list(z['keys']); fps = float(z['fps']); N = len(a)
s = lambda n: a[:, k.index(n)]
L, R, CH = s('L_fg'), s('R_fg'), s('CH_fg')
PASS, OUT_T, OUT_HOLD, STK_T, STK_HOLD = 0.30, 0.06, 1.0, 0.08, 1.5
def held(x, i0, i1, thr, hold):
    """first index in [i0,i1) where x stays > thr for `hold` seconds, else None"""
    need = int(hold * fps); run = 0
    for i in range(max(0, i0), min(N, i1 + need)):
        run = run + 1 if x[i] > thr else 0
        if run >= need and i - need + 1 < i1: return i - need + 1
    return None
d = json.load(open(res)); drops = d['drops']; orph = set(d['orphans'])
rows = []
hang_next = set()
for n_, t in enumerate(drops):
    i = int(round(t * fps))
    passed = CH[max(0, i - 3):min(N, i + 9)].max() > PASS
    stuck = held(CH, i + 3, i + 30, STK_T, STK_HOLD)
    oL = held(L, i + 2, i + 30, OUT_T, OUT_HOLD); oR = held(R, i + 2, i + 30, OUT_T, OUT_HOLD)
    if video:
        for side in ('L', 'R'):
            j = oL if side == 'L' else oR
            if j is None: continue
            sh = shape(video, side, j / fps)
            if not sachet_like(sh):
                rejected.append({'t': t, 'side': side, 'at': round(j / fps, 1), **sh})
                if side == 'L': oL = None
                else: oR = None
    if oL is not None or oR is not None: v = 'OUTSIDE BAG'
    elif stuck is not None and round(t, 1) not in orph:   # no-tray drops are already flagged separately
        e = stuck
        while e < N and CH[e] > STK_T: e += 1                       # end of the chute occupation
        if n_ + 1 < len(drops) and drops[n_ + 1] <= e / fps + 0.5:
            v = 'IN BAG'; hang_next.add(n_ + 1)                     # it was the NEXT sachet hanging; it then fell
        else: v = 'STUCK IN CHUTE'
    elif passed and round(t, 1) in orph: v = 'EMPTY BAG'   # no tray set under it: it fell into an empty bag
    elif passed: v = 'IN BAG'
    else: v = 'NOT SEEN'
    rows.append({'t': t, 'verdict': v, 'hung_in_chute_before_falling': n_ in hang_next, 'passed_slot': bool(passed), 'no_tray': round(t, 1) in orph,
                 'outside_side': 'L' if oL is not None else ('R' if oR is not None else None),
                 'outside_at': round((oL if oL is not None else oR) / fps, 1) if (oL is not None or oR is not None) else None})
# persistent objects outside the bag that no drop explains (operators, film, debris)
other = []
for name, x in (('L', L), ('R', R)):
    i = 0
    while i < N:
        j = held(x, i, N, OUT_T, OUT_HOLD)
        if j is None: break
        e = j
        while e < N and x[e] > OUT_T: e += 1
        if not any(r['outside_at'] is not None and abs(r['outside_at'] - j / fps) < 0.5 for r in rows):
            sh = shape(video, name, j / fps) if video else None
            if sh is None or sachet_like(sh): other.append({'side': name, 't0': round(j / fps, 1), 't1': round(e / fps, 1), 'shape': sh})
            else: rejected.append({'t': None, 'side': name, 'at': round(j / fps, 1), **sh})
        i = e + 1
summ = {v: sum(r['verdict'] == v for r in rows) for v in ('IN BAG', 'EMPTY BAG', 'OUTSIDE BAG', 'STUCK IN CHUTE', 'NOT SEEN')}
summ['hung_then_fell'] = [r['t'] for r in rows if r['hung_in_chute_before_falling']]; summ['drops'] = len(rows); summ['unexplained_outside_objects'] = len(other); summ['rejected_not_sachet_shaped'] = len(rejected)
print(json.dumps(summ))
for r in rows:
    if r['verdict'] != 'IN BAG': print('  ', r)
for o in other[:30]: print('   other:', o)
json.dump({'summary': summ, 'drops': rows, 'other_outside': other, 'rejected': rejected}, open(out, 'w'), indent=1)
