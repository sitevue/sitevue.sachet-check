# sitevue.sachet-check

Scavenger sachet check for the FPL grind line (camera grind-04). Every tray set should get exactly one
oxygen-scavenger sachet before it goes into the bag. For every set and every sachet this tells you:

| Question | Result | Alarm when |
|---|---|---|
| Did the dispenser drop a sachet on every tray set? | `sets` result: `ok` / `MISSING` (shown as "No sachet from dispenser") / `EXTRA` / `DOUBLE` | the dispenser dropped no sachet on a set |
| Did the sachet land in the bag? | `sachet` result: `IN BAG` / `EMPTY BAG` / `OUTSIDE BAG` / `STUCK IN CHUTE` / `NOT SEEN` | it landed outside the bag or jammed in the chute |

It works from fixed boxes in the camera image: a white sachet on the belt, red meat moving under the
chute, and new white objects in the chute slot and on the side conveyors. There is no learned model and
no GPU. One CPU core keeps up with the 10 fps camera with room to spare (about 2.3x real time on a 6-core laptop). Results stream out about
1.5 s (sets) and 4.5 s (sachets) after the event.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# results as JSON lines, alerts printed as they happen, summary at the end
sachet run path/to/video.mp4 --out results.jsonl          # also takes an RTSP URL or camera index

# how fast is it on this machine?
sachet bench path/to/video.mp4
```

All commands take `--config` (default `configs/fpl-grind-04.yaml`, or `$SACHET_CONFIG`).
Every field of the results is described in **[docs/output.md](docs/output.md)**.

## Use from Python

```python
from sachet_check import Config, SachetPipeline

for r in SachetPipeline(Config.load()).run("video.mp4"):     # or "rtsp://camera/stream"
    print(r["kind"], r.get("status") or r.get("verdict"), r["alert"])
```

`SachetChecker` (engine.py) takes per-frame signals directly, if you already decode frames elsewhere:
`checker.push(FrameSignals(cfg).compute(frame), crops)` returns any results that became final.

## Layout

```
configs/fpl-grind-04.yaml   everything line-specific: image boxes, colour thresholds, timings, alert mapping
src/sachet_check/
  signals.py                per-frame pixel fractions in the boxes (+ running background for "new" objects)
  engine.py                 SachetChecker: signals in, `sets` and `sachet` results out as soon as they are certain
  shape.py                  is a new object on a side conveyor shaped like a sachet?
  tray.py                   sachets riding into the bag on the trays (added by hand when nothing fell)
  pipeline.py               SachetPipeline: video file / RTSP / camera -> results
  summary.py                counts over a list of results
  cli.py                    `sachet run | bench`
docs/                       method.md (how it works, validation, weak points), output.md, calibration.md
tests/                      fast tests on synthetic signals, no video needed: `pytest`
tools/compare_with_batch.py check the streaming checker against the batch prototype on saved signals
research/                   batch prototype the method was built with, and its results on the recordings so far
```

## Status

- **Validated on 3 h 54 min of grind-04 footage** (29 Oct and 5 Nov, ~3,170 sets, 3,187 sachets) against
  the batch prototype. Every drop, stretch, no-tray drop and landing verdict is the same. 5 set statuses
  differ, all borderline set-count cases ([docs/method.md](docs/method.md)).
- **Missing sachet:** caught on a fault clip, plus one likely real miss on 5 Nov at 48:13. That one is not
  yet confirmed with the line.
- **Landing outside the bag:** proven only on a synthetic test (3/3). No real case exists in the footage yet.
- **Short stretches around line stops** used to be counted as sets with no sachet (FPL's 11-09 hand count:
  0 of 8 `MISSING` real). A set that stops under the chute is now one set, and blips under ~1 s with no
  sachet are `fragment`s, not sets. On our recordings this took `MISSING` from 14 to 4
  ([docs/method.md](docs/method.md)). Stretches where a worker moved trays under the chute by hand (white
  sleeve beside the chute) and no sachet fell are `by_hand` (`warn`), not `MISSING`.
- **Main false alarms:** false `EXTRA` where the set count on long back-to-back stretches is off by one
  (about 5 per hour on 5 Nov), and `EMPTY BAG` from hard hats or bag film over the belt. Treat `warn` as
  "review", not "fault".
- **Sachets added by hand:** when nothing falls from the belt, a sachet seen riding into the bag on the trays
  (flat on top, or tucked at the seam between trays, and moving down with them) makes the set `hand_added`
  ("Sachet added by hand", no alert) instead of `MISSING`. On the 11-10 dispenser stop: 70 of 70 hand-added
  sets caught, 24 of 24 real misses left `MISSING`. A sachet fully hidden under a tray is not seen. Tuned on
  that one export, then corrected after a full-day shadow review on the sandbox (overwrap glare and a white
  product label had been taken for sachets) ([docs/method.md](docs/method.md)).
- **720p exports** are resized to 1920x1080 before measuring, so the boxes still fit.
- Not yet run against the live camera stream. Validated only on exported recordings.
