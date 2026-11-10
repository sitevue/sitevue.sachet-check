# Output: two kinds of result

`sachet run` writes one JSON object per line (`SachetPipeline.run` yields the same dicts).
Every object has a `kind`:

- **`sets`**: one per stretch of tray sets passing under the chute. Did every set get exactly one sachet?
- **`sachet`**: one per sachet that fell off the belt. Where did it end up?

Each object has an `alert` of `none`, `warn` or `alarm`, mapped in the config under `alerts:`. Anything
downstream can act on `alert` alone, without knowing the statuses.

Each object also has a `label`: the wording to show people, mapped in the config under `labels:`. Show
`label`, and use `status` / `verdict` in code: the codes never change, the wording can.

Times: `t`, `t0` and `t1` are seconds since the stream started (for a file, seconds into the file).
`timestamp` is Unix time for a live camera, and the same as `t`/`t0` for a file.

## `kind: "sets"`: did every tray set get a sachet?

Comes out about 1.5 s after the stretch leaves the drop box. Most stretches are one set. When the line
runs fast, 2 to 4 sets can pass back to back as one stretch. When the line stops with a set under the
chute, the result waits until the set has moved on and left the drop box (at most `hold_max_s`, 120 s).

| Field | Type | Meaning |
|---|---|---|
| `set_group_id` | int | Running number of the stretch since the stream started |
| `t0`, `t1` | float | When the stretch entered and left the drop box |
| `moving_s` | float | Time it was moving under the chute. The set count uses this, not `t1 - t0` |
| `paused_s` | float | Time it stood still under the chute during a line stop (0 normally) |
| `timestamp` | float | Time of `t0` (Unix time when live) |
| `sets` | int | Tray sets in the stretch, estimated from `moving_s` and the current cycle time (0 for a `fragment`) |
| `sachets` | int | Sachets that fell onto it |
| `status` | str | `ok`, `hand_added`, `MISSING`, `EXTRA`, `DOUBLE`, `partial`, `fragment` or `by_hand` (see below) |
| `label` | str | Wording to show for `status` (see below) |
| `alert` | str | `none` / `warn` / `alarm` |
| `missing` | int | Sets the dispenser dropped no sachet on (only when `MISSING`) |
| `extra` | int | Sachets more than sets (only when `EXTRA`) |
| `double_strips` | int | Sachets that were two joined sachets (only when `DOUBLE`) |
| `sachet_ids` | list[int] | The `sachet` results that belong to this stretch |
| `drop_times`, `double_strip_times` | list[float] | When those sachets fell |
| `period_s` | float | Cycle time used for the set count |
| `hand` | float | Largest white blob (a worker's sleeve) in the reach box beside the chute during the stretch, as a share of the box (diagnostics; over `hand_min` 0.25 with no sachet gives `by_hand`) |
| `hand_added` | int | Sachets seen riding into the bag on the trays when nothing fell from the belt (sachets added by hand; 0 when a sachet fell) |
| `hand_added_kinds` | list[str] | How each was seen: `slab` (flat on the meat) or `strip` (tucked at the seam between two trays) |
| `frame_start`, `frame_end` | int | Frame numbers (diagnostics) |

| `status` | Default `label` | Meaning | Default alert |
|---|---|---|---|
| `ok` | OK | One sachet per set | none |
| `hand_added` | Sachet added by hand | Nothing fell from the belt, but a sachet rode into the bag on the trays, one per set: the sachets were added by hand. Counted as sets with a sachet | none |
| `MISSING` | No sachet from dispenser | Fewer sachets dropped than sets, and no sachet seen riding on the trays to make up the difference: **the set went in without a sachet** as far as the camera can tell | alarm |
| `EXTRA` | Extra sachet | More sachets than sets. Usually the set count is off by one on a long stretch, so check it | warn |
| `DOUBLE` | Double sachet | A sachet was two joined sachets (the cutter missed a cut) | warn |
| `partial` | Not judged | The stream started or ended in the middle of the stretch, so it is not judged | none |
| `fragment` | Not a set | Moved under the chute for less than half a set's time (`fragment_frac` x `set_len_s`, about 1 s) and no sachet fell on it: a tray nudged or handled, not a set passing. Not counted as a set | none |
| `by_hand` | Trays moved by hand | No sachet fell, and a worker's arm (white sleeve) reached in beside the chute during the stretch: trays moved or placed by hand, e.g. a set built by hand during a stop. Not counted as a set. A stretch that got a sachet is judged as usual | warn |

**When nothing falls from the belt**, the check looks for sachets riding on the trays (added by hand): a
white sachet-shaped object that moves down into the bag with them. If it sees one per set the stretch is
`hand_added`; if not, it stays `MISSING`. Only when nothing fell from the belt: a stretch with a dispenser
drop is judged on the drops alone. A sachet completely hidden under or between trays is not seen, so that
set still reads `MISSING`.

## `kind: "sachet"`: where did each sachet go?

Comes out about 4.5 s after the drop, because the landing check watches the side conveyors for 3 s plus
a 1.5 s hold. It can take longer (up to 20 s) only when the chute slot stays occupied.

| Field | Type | Meaning |
|---|---|---|
| `sachet_id` | int | Running number since the stream started |
| `t`, `timestamp` | float | When it fell off the belt |
| `verdict` | str | See below |
| `label` | str | Wording to show for `verdict`: `In bag`, `Empty bag`, `Outside bag`, `Stuck in chute`, `Not seen` |
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

`sachet run` prints counts at the end (`sachet_check.summary.summarize`): sets checked, sets with no sachet
from the dispenser and none seen added by hand (`sets_missing_sachet`), sets whose sachet was added by hand
(`sets_sachet_added_by_hand`), double strips, `sachet_on_every_set_pct` (sets with a sachet, dispensed or
added by hand), landing verdict counts, alarms and warnings.

## Example

From 5 Nov 2026, recording 4313d69a, at 48:13: the dispenser dropped no sachet on a set, and the sachet then fell into an empty bag:

```json
{"kind": "sets", "set_group_id": 370, "frame_start": 28933, "frame_end": 28951, "t0": 2893.3, "t1": 2895.1, "timestamp": 2893.3, "sets": 1, "sachets": 0, "missing": 1, "extra": 0, "double_strips": 0, "status": "MISSING", "label": "No sachet from dispenser", "alert": "alarm", "period_s": 2.3, "sachet_ids": [], "drop_times": [], "double_strip_times": []}
{"kind": "sachet", "sachet_id": 583, "frame_index": 29032, "t": 2903.2, "timestamp": 2903.2, "verdict": "EMPTY BAG", "label": "Empty bag", "in_bag": false, "alert": "warn", "no_tray": true, "set_group_id": null, "double_strip": false, "size": 0.431, "passed_slot": true, "outside_side": null, "outside_t": null, "hung_in_chute_before_falling": false, "rejected_outside": []}
```
