# Render clips with per-tray-set sachet verdicts burned in.
# usage: annotate.py out.mp4 spec.json   spec: [{"video":..,"result":..,"t0":..,"t1":..,"title":..,"note":..}, ...]
import cv2, json, sys, subprocess, numpy as np, os
out, spec = sys.argv[1], json.load(open(sys.argv[2]))
X0, X1 = spec[0].get('crop', (560, 1360)); H = 810; W = int(round((X1 - X0) * H / 1080 / 2)) * 2; PAN = 300   # crop (same for all clips in a file)
GREEN, RED, ORANGE, GREY, WHITE = (60,190,60), (40,40,230), (0,150,255), (150,150,150), (255,255,255)
tmp = out + '.raw.mp4'; vw = cv2.VideoWriter(tmp, cv2.VideoWriter_fourcc(*'mp4v'), 10, (W + PAN, H))
def txt(img, s, y, c=WHITE, sc=.6, th=1, x=12): cv2.putText(img, s, (x, y), 0, sc, c, th, cv2.LINE_AA)
def wrap(s, n=34):
    out, line = [], ''
    for w in s.split():
        if len(line) + len(w) + 1 > n: out.append(line); line = w
        else: line = (line + ' ' + w).strip()
    return out + ([line] if line else [])
for clip in spec:
    r = json.load(open(clip['result'])); st = r['stretches']; orph = r['orphans']
    land = json.load(open(clip['landing']))['drops'] if clip.get('landing') else []
    sets = []                                   # flatten stretches into per-set verdict boxes
    for s in st:
        good = s['status'] in ('ok', 'partial') or (s['status'] == 'EXTRA')
        sets.append((s['t0'], s['t1'], s['status'], s['sets'], s['drops'], s['drop_times'], s.get('double_strip_times', [])))
    clip['_sets'] = sets
    v = cv2.VideoCapture(clip['video']); fps = 10
    v.set(cv2.CAP_PROP_POS_FRAMES, int(clip['t0'] * fps)); i = int(clip['t0'] * fps)
    # title card 1.5 s
    card = np.zeros((H, W + PAN, 3), np.uint8); txt(card, clip['title'], 120, WHITE, .9, 2, 30)
    for k, l in enumerate(wrap(clip.get('note', ''), 60)): txt(card, l, 180 + 32 * k, (200,200,200), .6, 1, 30)
    for _ in range(15): vw.write(card)
    while i < clip['t1'] * fps:
        ok, f = v.read()
        if not ok: break
        t = i / fps; i += 1
        img = cv2.resize(f[:, X0:X1], (W, H)); sx = W / (X1 - X0); sy = H / 1080
        cv2.rectangle(img, (int((935-X0)*sx), 0), (int((1125-X0)*sx), int(365*sy)), (255,255,0), 1)      # belt ROI
        cv2.rectangle(img, (int((900-X0)*sx), int(370*sy)), (int((1140-X0)*sx), int(720*sy)), (255,0,255), 1)  # drop ROI
        cur = next((s for s in sets if s[0] - 0.2 <= t <= s[1] + 1.5), None)
        recent_drop = [d for d in r['drops'] if 0 <= t - d <= 1.0]
        recent_orph = [d for d in orph if 0 <= t - d <= 2.0]
        pan = np.full((H, PAN, 3), 30, np.uint8)
        m, s_ = divmod(int(t), 60); txt(pan, '%s  %d:%02d.%d' % (clip.get('tag', ''), m, s_, int(t * 10) % 10), 30, WHITE, .55)
        if cur:
            t0, t1, status, n, nd, dts, dbl = cur
            seen = sum(1 for d in dts if d <= t)
            bad = [x for x in land if x['verdict'] in ('OUTSIDE BAG', 'STUCK IN CHUTE') and any(abs(x['t'] - d) < 0.15 for d in dts) and t - x['t'] >= 0.4]
            if bad:
                col, verdict = RED, 'SACHET: MISSED BAG' if bad[-1]['verdict'] == 'OUTSIDE BAG' else 'SACHET: STUCK'
            elif any(0 <= t - d <= 2.5 for d in dbl):
                col, verdict = (200,60,200), 'SACHET: DOUBLE'
            elif status in ('ok', 'partial', 'EXTRA', 'DOUBLE') and seen >= 1:
                col, verdict = GREEN, 'SACHET: YES'
            elif status == 'MISSING' and t > t1:
                col, verdict = RED, 'SACHET: NO'
            else:
                col, verdict = (0,190,230), 'WATCHING...'
            nd = seen
            if status == 'partial': col, verdict = GREY, 'PARTIAL (clip edge)'
            cv2.rectangle(pan, (8, 60), (PAN - 8, 150), col, -1); txt(pan, verdict, 115, WHITE, .85, 2, 20)
            txt(pan, 'tray set(s) in drop zone: %d' % n, 180); txt(pan, 'sachet drops seen: %d' % nd, 205)
            txt(pan, '%.1f-%.1fs' % (t0, t1), 230, (180,180,180), .5)
            cv2.rectangle(img, (0, 0), (W - 1, H - 1), col, 6)
        else:
            txt(pan, 'no tray set moving', 115, (160,160,160), .65)
        if recent_drop:
            cv2.rectangle(pan, (8, 260), (PAN - 8, 300), (200,120,0), -1); txt(pan, 'SACHET DROP', 288, WHITE, .7, 2, 20)
        if recent_orph:
            cv2.rectangle(pan, (8, 360), (PAN - 8, 400), ORANGE, -1); txt(pan, 'SACHET, NO TRAY', 388, WHITE, .7, 2, 20)
        lv = [x for x in land if 0.3 <= t - x['t'] <= (3.5 if x['verdict'] == 'IN BAG' else 6.0)]
        if lv:
            if lv[-1].get('hung_in_chute_before_falling'): txt(pan, '(hung in chute ~2 s, then fell)', 420, (0,200,255), .45)
            lc = {'IN BAG': (60,160,60), 'EMPTY BAG': (0,150,255), 'OUTSIDE BAG': (40,40,230), 'STUCK IN CHUTE': (40,40,230), 'NOT SEEN': (0,170,230)}[lv[-1]['verdict']]
            lab = {'IN BAG': 'SACHET IN BAG', 'EMPTY BAG': 'IN EMPTY BAG (NO TRAY)', 'OUTSIDE BAG': 'SACHET OUTSIDE BAG', 'STUCK IN CHUTE': 'STUCK IN CHUTE', 'NOT SEEN': 'SACHET NOT SEEN'}[lv[-1]['verdict']]
            cv2.rectangle(pan, (8, 310), (PAN - 8, 350), lc, -1); txt(pan, lab, 338, WHITE, .7 if len(lab) <= 18 else .62, 2, 20)
        if clip.get('show_regions'):
            for (x0, y0, x1, y1) in [(380, 700, 670, 1010), (1150, 720, 1500, 1010), (905, 375, 1135, 470)]:
                a0, a1 = max(x0, X0), min(x1, X1)
                if a1 > a0: cv2.rectangle(img, (int((a0-X0)*sx), int(y0*sy)), (int((a1-X0)*sx), int(y1*sy)), (0,200,255), 1)
        if clip.get('note'):
            txt(pan, 'review:', 450, (0,220,255), .55)
            for k, l in enumerate(wrap(clip['note'])): txt(pan, l, 475 + 22 * k, (220,220,220), .5)
        cap = [c for c in clip.get('captions', []) if c[0] <= t <= c[1]]
        if cap:
            ls = wrap(cap[-1][2], 32); y0 = H - 60 - 22 * len(ls)
            cv2.rectangle(pan, (8, y0 - 26), (PAN - 8, H - 50), (0, 90, 140), -1)
            for k, l in enumerate(ls): txt(pan, l, y0 + 22 * k, WHITE, .5)
        if clip.get('running_count'):
            done = [x for x in clip['_sets'] if clip['t0'] <= x[0] and x[1] < t]   # only sets inside this clip
            txt(pan, 'sets so far: %d   flagged: %d' % (sum(x[3] for x in done), sum(x[3] for x in done if x[2] not in ('ok', 'partial', 'EXTRA'))), H - 36, (200,200,200), .45)
        txt(pan, 'cyan box = belt   magenta = drop zone', H - 15, (150,150,150), .42)
        vw.write(np.hstack([img, pan]))
vw.release()
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', tmp, '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '26', '-preset', 'veryfast', '-movflags', '+faststart', out], check=True)
os.remove(tmp); print('wrote', out)
