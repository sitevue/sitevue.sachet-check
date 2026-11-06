# Scavenger sachet check (prototype)

Checks that every tray set gets exactly one scavenger sachet. Fixed-camera ROI signals, no model.

- `signals.py` — per frame, in three ROIs (belt / drop / lane): white-pixel, meat-pixel and motion fractions.
- `match.py` — tray sets = runs of meat in the drop zone (back-to-back runs split by nominal 2.05 s set length);
  sachet drop = belt goes from holding a white sachet to empty. Each set is matched one-to-one to a drop
  0.2–1.6 s after its leading edge → `ok` / `MISSING` / `double` / `partial` (clip edge).

```
pip install opencv-python-headless numpy matplotlib
python signals.py VIDEO.mp4 signals.npz
python match.py signals.npz output/result "label"
```

Results on scavenger-1000-1002.mp4: 33 ok, 0 missing, 0 double, 1 partial (clip starts mid-set).
Drop offset after set leading edge: 0.7–1.0 s (median 0.8). Fault test (sachet frozen on belt at 64 s) → set at 63.7 s flagged MISSING.

ROIs are hard-coded pixel boxes for this camera at 1920x1080.

## v3 matcher (`match3.py`) — use this one
v1 (`match.py`) broke on long footage: line stoppages with a tray parked under the chute, back-to-back sachets
(belt never looks empty), and fast running where sets merge. v3:
- sachet drop = sharp fall (>0.15 over 0.3 s) in belt white, not "belt empty";
- tray-set stretch = meat in drop zone AND drop zone moving (parked trays ignored);
- per stretch: expected sets = 1 + round((len - 2.05 s) / local cycle), compared with drops inside it.

Results on fpl-grind 2026-10-29, feed M3V7 (3 recordings, 2.9 h, ~2,413 sets): see `output/fpl-grind-2026-10-29/`.

### Double-sachet check (added to `match3.py`)
Sachet size on the belt = top-5 median of belt-white over the 1.3 s before each drop. A drop is a joined
double strip when size >= 0.60 AND >= 1.5x the local median (single ~0.38, p99 0.55; doubles 0.66-0.74).
Counted only when the drop lands on a moving tray-set stretch (oversized drops with no tray were all
hard-hat / bag-film occlusions). Stretch status becomes `DOUBLE`. Found 4 on 2026-10-29:
rec1 26:24.8, rec2 18:12.3, rec2 48:57.1, rec3 35:03.8. Blind spot: two separate sachets stacked exactly
on top of each other look like one.
`annotate.py` shows SACHET: DOUBLE (magenta) for 2.5 s after such a drop.

## Landing check (did the sachet end up in the bag?)
`landing_signals.py VIDEO out.npz` then `landing_verdict.py out.npz result_v3.json landing.json VIDEO`.
A landed sachet slides down the side of the trays and disappears into the bag, so its final position can't be
seen directly. Instead, per drop:
- **passed chute slot**: new-white spike (~0.6) in the slot just below the belt (region 905-1135 x 375-470).
- **OUTSIDE BAG**: a new white object appears on a side conveyor (L 380-670 x 700-1010, R 1150-1500 x 720-1010)
  within 3 s, stays >= 1 s vs a slow running background, AND is sachet-shaped (8k-35k px, >= 72% rectangular,
  aspect 1.1-2.5, not touching the region edge). The shape rule rejects bag film, exposure changes, arms, sleeves.
- **STUCK IN CHUTE**: the slot stays occupied >= 1.5 s after a drop (tray present). If the next drop happens while
  it is still occupied, the hang belongs to that next sachet (it fell after hanging) -> `hung_in_chute_before_falling`.

Validation: synthetic video (`make_missbag_test.py`) with a real sachet pasted onto each conveyor and into the slot:
3/3 caught. Original clip: 33/33 IN BAG.
fpl-grind 2026-10-29 (2,425 drops): 2,425 IN BAG, 0 OUTSIDE, 0 STUCK; 2 sachets hung ~2 s before falling (both the
joined double strips at rec1 26:24.8, rec2 48:57.1); 76 side-conveyor alarms rejected as not sachet-shaped.
No real missed-bag case exists in this footage, so OUTSIDE BAG is proven only on the synthetic test.
