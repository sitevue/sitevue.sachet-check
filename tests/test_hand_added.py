"""Sachets added by hand: nothing falls from the belt, but a sachet rides into the bag on the trays."""
from test_engine import CFG, Line, kinds

from sachet_check.tray import TraySachets

# blob = (area, x, y, w, h, rectangularity, aspect, meat_ring), full-res px
SLAB = (17000, 800, 0, 200, 120, 0.75, 1.9, 0.15)        # flat on the meat
STRIP = (7000, 800, 0, 190, 40, 0.72, 4.8, 0.0)          # tucked at the seam between two trays
FILM = (20000, 1030, 0, 120, 230, 0.6, 2.0, 0.0)         # bag film glare: tall, no meat
GLOSS = (3500, 810, 0, 120, 64, 0.55, 2.0, 0.05)         # glare on glossy tray overwrap (11-10 sandbox)
LABEL = (15300, 930, 0, 118, 160, 0.83, 1.4, 0.10)       # white product label on every tray (11-10 sandbox)
UPRIGHT = (16000, 960, 0, 115, 210, 0.78, 1.9, 0.12)     # sachet standing upright on the tray


def _at(b, y):
    return b[:2] + (y,) + b[3:]


def ride(line, t, blob, y0=500, step=57, frames=7):
    """A blob moving down with the trays from y0, `step` px per frame, starting at time t."""
    i0 = int(round(t * 10))
    for k in range(frames):
        row = line.rows[i0 + k]
        row.setdefault("tray_blobs", []).append(_at(blob, y0 + k * step))


def still(line, t0, t1, blob, y=600):
    for i in range(int(round(t0 * 10)), int(round(t1 * 10))):
        line.rows[i].setdefault("tray_blobs", []).append(_at(blob, y))


def _line():
    """Four normal sets (5-17 s), then a set at 20 s with nothing from the belt."""
    line = Line(40)
    for k in range(4):
        line.tray_set(5 + 3 * k)
        line.sachet(5.8 + 3 * k)
    line.tray_set(20.0)
    return line


def _last_set(res):
    return [r for r in kinds(res, "sets") if r["t0"] >= 19.5][0]


def test_slab_riding_on_the_tray_is_hand_added():
    line = _line()
    ride(line, 20.5, SLAB)
    s = _last_set(line.run())
    assert s["status"] == "hand_added" and s["hand_added"] == 1 and s["missing"] == 0
    assert s["alert"] == "none" and s["label"] == "Added by hand" and s["hand_added_kinds"] == ["slab"]


def test_strip_tucked_between_trays_is_hand_added():
    line = _line()
    ride(line, 20.5, STRIP)
    s = _last_set(line.run())
    assert s["status"] == "hand_added" and s["hand_added_kinds"] == ["strip"]


def test_no_sachet_on_the_tray_is_still_missing():
    s = _last_set(_line().run())
    assert s["status"] == "MISSING" and s["hand_added"] == 0 and s["alert"] == "alarm"


def test_white_thing_that_does_not_move_is_not_a_sachet():
    """Steel or a label lit white: sachet-shaped, meat around it, but it stays put."""
    line = _line()
    still(line, 19.0, 23.0, SLAB)
    assert _last_set(line.run())["status"] == "MISSING"


def test_moving_film_glare_is_not_a_sachet():
    """Bag film pulled down with the trays: it moves, but it is tall and has no meat around it."""
    line = _line()
    ride(line, 20.5, FILM)
    assert _last_set(line.run())["status"] == "MISSING"


def test_glare_on_tray_overwrap_is_not_a_sachet():
    """Glossy overwrap catches the light in a small flat patch that rides down with the tray for a few
    frames: strip-shaped but far narrower than a sachet tucked across the tray (sandbox, 11-10)."""
    line = _line()
    ride(line, 20.5, GLOSS, frames=8)
    assert _last_set(line.run())["status"] == "MISSING"


def test_white_product_label_is_not_a_sachet():
    """A white label on every tray: sachet-sized, on the meat, rides down with the tray, but it is
    neither lying across the tray nor standing upright like a sachet (sandbox, 11-10 17:00-19:07)."""
    line = _line()
    ride(line, 20.5, LABEL, frames=9)
    assert _last_set(line.run())["status"] == "MISSING"


def test_upright_sachet_is_hand_added():
    line = _line()
    ride(line, 20.5, UPRIGHT)
    s = _last_set(line.run())
    assert s["status"] == "hand_added" and s["hand_added_kinds"] == ["slab"]


def test_only_checked_when_nothing_fell_from_the_belt():
    """A dispenser sachet that lands on top of the tray is seen riding too: the set is just ok."""
    line = _line()
    line.sachet(20.8)
    ride(line, 21.0, SLAB)
    s = _last_set(line.run())
    assert s["status"] == "ok" and s["sachets"] == 1 and s["hand_added"] == 0


def test_tracker_needs_downward_motion():
    tr = TraySachets(CFG)
    for i in range(6):
        tr.push(i, [_at(SLAB, 500 + 57 * i), _at(SLAB, 300)])      # one riding, one parked above
    kinds_seen = [k for k, _ in tr.seen(0, 5)]
    assert kinds_seen == ["slab"]
