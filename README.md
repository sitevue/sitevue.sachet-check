# sitevue.sachet-check

Scavenger sachet check for the FPL grind line (camera grind-04). Every tray set should get exactly one
oxygen-scavenger sachet before it goes into the bag. For every set and every sachet this tells you:

| Question | Result | Alarm when |
|---|---|---|
| Did every tray set get a sachet? | `sets` result: `ok` / `MISSING` / `EXTRA` / `DOUBLE` | a set got no sachet |
| Did the sachet land in the bag? | `sachet` result: `IN BAG` / `EMPTY BAG` / `OUTSIDE BAG` / `STUCK IN CHUTE` / `NOT SEEN` | it landed outside the bag or jammed in the chute |

It works from fixed boxes in the camera image: a white sachet on the belt, red meat moving under the
chute, and new white objects in the chute slot and on the side conveyors. There is no learned model and
no GPU. One CPU core runs it several times faster than the 10 fps camera. Results stream out about
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
- **Main false alarms, about 5 to 7 per hour:** `EXTRA`/`MISSING` pairs where the set count on long
  back-to-back stretches is off by one, and `EMPTY BAG` from hard hats or bag film over the belt. Treat
  `warn` as "review", not "fault".
- Not yet run against the live camera stream. Validated only on exported recordings.
