# Output: two kinds of result

`sachet run` writes one JSON object per line (`SachetPipeline.run` yields the same dicts).
Every object has a `kind`:

- **`sets`**: one per stretch of tray sets passing under the chute. Did every set get exactly one sachet?
- **`sachet`**: one per sachet that fell off the belt. Where did it end up?

Each object has an `alert` of `none`, `warn` or `alarm`, mapped in the config under `alerts:`. Anything
downstream can act on `alert` alone, without knowing the statuses.

Times: `t`, `t0` and `t1` are seconds since the stream started (for a file, seconds into the file).
`timestamp` is Unix time for a live camera, and the same as `t`/`t0` for a file.

## `kind: "sets"`: did every tray set get a sachet?

Comes out about 1.5 s after the stretch leaves the drop box. Most stretches are one set. When the line
runs fast, 2 to 4 sets can pass back to back as one stretch.

| Field | Type | Meaning |
|---|---|---|
| `set_group_id` | int | Running number of the stretch since the stream started |
| `t0`, `t1` | float | When the stretch entered and left the drop box |
| `timestamp` | float | Time of `t0` (Unix time when live) |
| `sets` | int | Tray sets in the stretch, estimated from its length and the current cycle time |
| `sachets` | int | Sachets that fell onto it |
| `status` | str | `ok`, `MISSING`, `EXTRA`, `DOUBLE` or `partial` (see below) |
| `alert` | str | `none` / `warn` / `alarm` |
| `missing` | int | Sets without a sachet (only when `MISSING`) |
| `extra` | int | Sachets more than sets (only when `EXTRA`) |
| `double_strips` | int | Sachets that were two joined sachets (only when `DOUBLE`) |
| `sachet_ids` | list[int] | The `sachet` results that belong to this stretch |
| `drop_times`, `double_strip_times` | list[float] | When those sachets fell |
| `period_s` | float | Cycle time used for the set count |
| `frame_start`, `frame_end` | int | Frame numbers (diagnostics) |

| `status` | Meaning | Default alert |
|---|---|---|
| `ok` | One sachet per set | none |
| `MISSING` | Fewer sachets than sets: **a set went into the bag without a sachet** | alarm |
| `EXTRA` | More sachets than sets. Usually the set count is off by one on a long stretch, so check it | warn |
| `DOUBLE` | A sachet was two joined sachets (the cutter missed a cut) | warn |
| `partial` | The stream started or ended in the middle of the stretch, so it is not judged | none |

## `kind: "sachet"`: where did each sachet go?

Comes out about 4.5 s after the drop, because the landing check watches the side conveyors for 3 s plus
a 1.5 s hold. It can take longer (up to 20 s) only when the chute slot stays occupied.

| Field | Type | Meaning |
|---|---|---|
| `sachet_id` | int | Running number since the stream started |
| `t`, `timestamp` | float | When it fell off the belt |
| `verdict` | str | See below |
| `in_bag` | bool | `verdict == "IN BAG"` |
| `alert` | str | `none` / `warn` / `alarm` |
| `no_tray` | bool | No tray set was moving under the chute when it fell |
| `set_group_id` | int \| null | The `sets` result it belongs to (null when `no_tray`) |
| `double_strip` | bool | Two joined sachets |
| `hung_in_chute_before_falling` | bool | It hung in the chute for a moment, then fell into the bag |
| `outside_side` | `"left"` \| `"right"` \| null | Which side conveyor it landed on (`OUTSIDE BAG`) |
| `outside_t` | float \| null | When it appeared there |
| `size`, `passed_slot`, `rejected_outside`, `frame_index` | | Diagnostics |

| `verdict` | Meaning | Default alert |
|---|---|---|
| `IN BAG` | Went through the chute slot onto a tray set, and nothing landed outside | none |
| `EMPTY BAG` | Went through the chute but no tray set was under it, so it fell into an empty bag | warn |
| `OUTSIDE BAG` | A sachet-shaped object appeared on a side conveyor and stayed | alarm |
| `STUCK IN CHUTE` | The chute slot stayed occupied for 1.5 s or more after the drop | alarm |
| `NOT SEEN` | Left the belt but was never seen in the chute slot | warn |

## Summary

`sachet run` prints counts at the end (`sachet_check.summary.summarize`): sets checked, sets missing a
sachet, double strips, `sachet_on_every_set_pct`, landing verdict counts, alarms and warnings.

## Example

From 5 Nov 2026, recording 4313d69a, at 48:13: a set went into its bag with no sachet, and the sachet then fell into an empty bag:

```json
{"kind": "sets", "set_group_id": 370, "frame_start": 28933, "frame_end": 28951, "t0": 2893.3, "t1": 2895.1, "timestamp": 2893.3, "sets": 1, "sachets": 0, "missing": 1, "extra": 0, "double_strips": 0, "status": "MISSING", "alert": "alarm", "period_s": 2.3, "sachet_ids": [], "drop_times": [], "double_strip_times": []}
{"kind": "sachet", "sachet_id": 583, "frame_index": 29032, "t": 2903.2, "timestamp": 2903.2, "verdict": "EMPTY BAG", "in_bag": false, "alert": "warn", "no_tray": true, "set_group_id": null, "double_strip": false, "size": 0.431, "passed_slot": true, "outside_side": null, "outside_t": null, "hung_in_chute_before_falling": false, "rejected_outside": []}
```
