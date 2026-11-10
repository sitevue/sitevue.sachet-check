# Setting up a camera or line

Everything line-specific is in `configs/<line>.yaml`. Copy `configs/fpl-grind-04.yaml` and set:

1. **Regions.** Take a frame from the camera (`ffmpeg -i STREAM -frames:v 1 frame.jpg`) and draw
   these boxes in full-resolution pixels:
   - **belt**: the stretch of belt the sachet rides on just before it falls. It must hold one whole
     sachet and nothing else white.
   - **drop**: where the tray set passes under the chute. It needs to see the meat.
   - **chute**: the slot directly below the belt end that every sachet falls through.
   - **left / right**: the conveyors or plates beside the bag where a missed sachet would come to rest.
     Keep them clear of places where operators stand.
   - **tray**: below the chute, the trays on their way into the bag, from just under the chute to the
     bottom of the bag. Sachets added by hand are looked for here.
2. **Check the curves.** Run `sachet run VIDEO --out out.jsonl -v` on 10 minutes of normal running and
   compare it with the video. Every sachet should come out `IN BAG` and every set `ok`. If the drop count
   is short, lower `drop.fall`. If parked trays count as sets, raise `sets.motion_min`.
3. **Sachet size.** `size` in the `sachet` results should sit around one value for single sachets. Set
   `double.size_abs` to about halfway between that value and twice it, and no lower than the
   99th percentile of the singles.
4. **Set length.** `sets.set_len_s` is how long one set takes to cross the drop box at normal speed.
   It is the median `moving_s` of single-set stretches.

**Camera shifted?** Compare a new frame with `docs/regions.jpg`. On 5 Nov the grind-04 camera had moved
2.8 px right and 4.4 px down since 29 Oct. That is well within tolerance, and the same boxes worked.
