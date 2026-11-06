# How it works

The camera is fixed, so each part of the process always happens in the same box of the image. The
check measures a few pixel fractions in those boxes on every frame and reads events off the curves.
There is no learned model and no GPU.

![regions](regions.jpg)

| Box | What it measures |
|---|---|
| **belt** (935,0)-(1125,365) | White fraction: a sachet riding the blue belt |
| **drop** (900,370)-(1140,720) | Meat fraction and motion: a tray set passing under the chute |
| **chute** (905,375)-(1135,470) | New-white fraction: a sachet falling through the slot |
| **left / right** conveyors | New-white fraction: a sachet that missed the bag and landed beside it |

"White" means saturation < 50 and brightness > 190 in HSV. "Meat" means a red hue with saturation > 70.
"New white" means white AND more than 30 grey levels different from a slow running background. That
way the steel, the conveyors and the bag film do not count, but an object that arrives and stays does.

## 1. Sachet drops

The belt-white curve rises while a sachet rides into the belt box, then falls sharply when it drops.
A **drop** is a fall of more than 0.15 within 0.3 s, at the bottom of the fall. Falls less than 1 s
apart count as one drop.

**Sachet size** is the top-5 median of belt-white over the 1.5 s before the drop. A single sachet is
about 0.38 of the box (99th percentile 0.55). A **double strip** (two sachets still joined because the
cutter missed) is 0.66 to 0.74. A drop is a double strip when its size is at least 0.60 **and** at least
1.5 times the median of the last 40 drops.

## 2. Tray sets

A **stretch** is a run of frames where the drop box holds meat (> 2%) **and** is moving (> 6% of pixels
changed, smoothed over 0.5 s). Gaps of 0.3 s or less are merged, and stretches shorter than 0.5 s are
ignored. The motion condition matters: during a line stop a tray parked under the chute is not a new set.

One set takes about 2.05 s to pass. When the line runs fast, sets come back to back and form one longer
stretch. The number of sets in a stretch is

    sets = 1 + round((length - 2.05 s) / cycle time)

where the cycle time is the median gap between drops over the last 30 s, clipped to 2 to 4 s.

The drops that fall between the stretch start + 0.15 s and its end + 0.3 s belong to it. Comparing the
two counts gives `ok`, `MISSING` (fewer drops) or `EXTRA` (more drops). A double strip on an `ok` or
`EXTRA` stretch gives `DOUBLE`. A drop that belongs to no stretch fell with no tray under it (`no_tray`).

## 3. Landing: did the sachet end up in the bag?

The bag itself cannot be seen: a sachet that lands correctly slides down beside the trays and
disappears into it. So the check proves the sachet went through and that nothing ended up anywhere
else:

- **Passed the chute slot.** The new-white fraction in the slot spikes above 0.30 between 0.3 s before
  and 0.9 s after the drop.
- **OUTSIDE BAG.** A new white object appears on a side conveyor within 3 s of the drop, stays at least
  1 s, **and** is shaped like a sachet. That means 8k to 35k px, at least 72% rectangular, aspect ratio
  1.1 to 2.5, and not touching the box edge. The shape rule is what rejects bag film, exposure changes,
  arms, sleeves and hard hats; on 29 Oct it threw out 76 such alarms.
- **STUCK IN CHUTE.** The slot stays occupied for 1.5 s or more after a drop that had a tray. If the
  *next* drop happens before the slot clears, the hanging sachet was the next one, and it then fell: that
  next sachet is marked `hung_in_chute_before_falling` and this one is `IN BAG`.
- Otherwise the verdict is `IN BAG`. If the sachet passed but had no tray under it, the verdict is
  `EMPTY BAG`. If it never passed the slot, the verdict is `NOT SEEN`.

## Streaming vs batch

The method was built as a batch prototype over whole recordings (`research/prototype/`). The package
runs the same steps online and sends each result as soon as no later frame can change it. Two places
in the batch version looked into the future. The streaming version uses only the past:

| | Batch prototype | Streaming (this package) |
|---|---|---|
| Cycle time for the set count | Drops within ±30 s | Drops in the last 30 s, up to the end of the stretch |
| Typical sachet size for double strips | 20 drops each side | Last 40 drops |

`tools/compare_with_batch.py` replays the saved signals of all four recordings through the streaming
checker and compares the results with the batch output:

| Recording | Drops | Stretches | No-tray drops | Landing verdicts | Stretch status differences |
|---|---|---|---|---|---|
| 29 Oct rec1 (60 min) | 854 = | 729 = | 9 = | 854 = | none |
| 29 Oct rec2 (60 min) | 791 = | 720 = | 5 = | 791 = | none |
| 29 Oct rec3 (54 min) | 780 = | 516 = | 3 = | 780 = | 1: a batch false `EXTRA` is now `ok` |
| 5 Nov 4313d69a (60 min) | 762 = | 496 = | 7 = | 762 = | 4 (below) |

The 4 differences on 5 Nov are all borderline cases:

- **Set count on long stretches (9 s, 4 s and 9 s).** The streaming cycle time differs by 0.3 to 0.8 s,
  so the estimated set count moves by one. Two `ok` stretches become false `EXTRA`, and one batch false
  `EXTRA` becomes `ok`.
- **The 59:30 drop (size 0.64).** It was only just over the line in batch, because it came near the end
  of the recording where the window was one-sided. Streaming does not flag it as a double.

Running the whole package on the 5 Nov video gives exactly the same results as the replay. Here
`sachet run` decoded the video and computed the signals itself, so this run checks the signal code too.
It took 7 min 53 s for the 60 min recording on a laptop (about 7.6× real time).

## Results so far

- **29 Oct (2.9 h, ~2,413 sets):** no confirmed set without a sachet; 4 double strips; 0 sachets outside the bag.
- **5 Nov recording 4313d69a (1 h, ~757 sets):** one likely real miss at 48:13. A set slid into its bag
  with no drop, and the sachets then came in a burst into the next empty bags. This needs confirmation
  from the line.
- **Synthetic test** (a real sachet pasted onto each side conveyor and into the chute): 3 of 3 caught.
- **Fault clip** (sachet held on the belt): the set is flagged `MISSING`.

## Known weak points

- **Set count on long stretches.** This is the main source of false `EXTRA`: about 5 per hour on
  5 Nov. Each false `EXTRA` usually comes with a false `MISSING` next to it when a stop/restart splits
  sets oddly.
- **Occlusion.** An operator's hard hat or bag film over the belt box can look like a drop with no tray.
  This gives a false `EMPTY BAG` (5 of the 9 on 29 Oct rec1).
- **Two sachets stacked exactly on top of each other** look like one.
- **Hands at the chute.** An operator clearing a jam by hand can produce drops and alerts that are real
  events but not machine faults.
- **OUTSIDE BAG** has only been proven on the synthetic test. No real missed-bag case exists in the
  footage so far.
- **Camera movement.** The boxes are fixed pixels. A camera bump of more than ~15 px needs new boxes
  ([calibration.md](calibration.md)).
