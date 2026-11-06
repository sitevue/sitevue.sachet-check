# Research (reference only)

`prototype/` is the batch prototype the method was built and validated with, kept as it was:

| Script | |
|---|---|
| `signals.py VIDEO out.npz` | belt / drop / lane pixel fractions per frame |
| `match3.py signals.npz out.json` | sachet drops, tray-set stretches, per-stretch status, double strips |
| `landing_signals.py VIDEO out.npz` | new-white fractions on the side conveyors and the chute slot |
| `landing_verdict.py land.npz match3.json out.json [VIDEO]` | landing verdict per drop (VIDEO enables the shape check) |
| `blob_shape.py` | sachet-shape test for new objects on the side conveyors |
| `annotate.py spec.json out.mp4` | review videos with the verdicts drawn on (not for clients) |
| `make_missbag_test.py` | synthetic test video: a real sachet pasted onto each side conveyor and into the chute |
| `NOTES.md` | the prototype's own notes |

`results/` holds the batch output for the four recordings checked so far (fpl-grind grind-04,
2026-10-29 rec1-3 and 2026-11-05 4313d69a). `tools/compare_with_batch.py` replays the saved signals
through the streaming checker and compares against these; see `docs/method.md` ("Streaming vs batch").
The videos are in `s3://sitevue-ml-results-prod/exports/fpl-grind/` and are not in git.
