"""Checker logic on synthetic signals (no video needed)."""
from sachet_check import Config, SachetChecker

CFG = Config.load().with_fps(10)
QUIET = dict(belt_white=0.0, drop_meat=0.0, drop_motion=0.0, L_fg=0.0, R_fg=0.0, CH_fg=0.0)


class Line:
    """Builds a 10 fps signal timeline: sachets on the belt, tray sets under the chute, landing signals."""

    def __init__(self, seconds):
        self.rows = [dict(QUIET) for _ in range(int(seconds * 10))]

    def _set(self, key, t0, t1, v):
        for i in range(int(round(t0 * 10)), min(len(self.rows), int(round(t1 * 10)))):
            self.rows[i][key] = v

    def tray_set(self, t):
        """A set enters the drop box at t and leaves 2.05 s later."""
        self._set("drop_meat", t, t + 2.05, 0.2)
        self._set("drop_motion", t, t + 2.05, 0.3)

    def sachet(self, t, size=0.38, slot=True):
        """A sachet sits on the belt for 1.5 s and falls off at t."""
        self._set("belt_white", t - 1.5, t, size)
        if slot:
            self._set("CH_fg", t, t + 0.3, 0.6)

    def run(self):
        eng = SachetChecker(CFG)
        out = []
        for r in self.rows:
            out += eng.push(r)
        return out + eng.finish()


def kinds(res, kind):
    return [r for r in res if r["kind"] == kind]


def normal_line(n=12, period=3.0, start=5.0):
    line = Line(start + n * period + 10)
    for k in range(n):
        t = start + k * period
        line.tray_set(t)
        line.sachet(t + 0.8)
    return line


def test_every_set_gets_one_sachet():
    res = normal_line().run()
    sets, sach = kinds(res, "sets"), kinds(res, "sachet")
    assert len(sets) == 12 and all(s["status"] == "ok" and s["alert"] == "none" for s in sets)
    assert len(sach) == 12 and all(s["verdict"] == "IN BAG" and not s["no_tray"] for s in sach)
    assert [s["set_group_id"] for s in sach] == [s["set_group_id"] for s in sets]


def test_missing_sachet_raises_alarm():
    line = normal_line()
    line._set("belt_white", 5 + 4 * 3.0 - 1, 5 + 4 * 3.0 + 1.5, 0.0)     # no sachet for the 5th set
    res = line.run()
    bad = [s for s in kinds(res, "sets") if s["status"] != "ok"]
    assert len(bad) == 1 and bad[0]["status"] == "MISSING" and bad[0]["missing"] == 1 and bad[0]["alert"] == "alarm"
    assert abs(bad[0]["t0"] - 17.0) < 0.2


def test_sachet_without_tray_is_empty_bag():
    line = normal_line()
    line.sachet(5 + 12 * 3.0 + 1.0)                                     # one more sachet, no set under it
    res = line.run()
    last = kinds(res, "sachet")[-1]
    assert last["verdict"] == "EMPTY BAG" and last["no_tray"] and last["alert"] == "warn"
    assert all(s["status"] == "ok" for s in kinds(res, "sets"))


def test_sachet_on_side_conveyor_is_outside_bag():
    line = normal_line()
    t = 5 + 6 * 3.0 + 0.8
    line._set("CH_fg", t, t + 0.3, 0.0)
    line._set("L_fg", t + 0.6, t + 3.0, 0.2)                            # new white object stays on the left conveyor
    res = line.run()
    s = next(r for r in kinds(res, "sachet") if abs(r["t"] - t) < 0.15)
    assert s["verdict"] == "OUTSIDE BAG" and s["outside_side"] == "left" and s["alert"] == "alarm"


def test_sachet_stuck_in_chute():
    line = normal_line(n=6, period=6.0)                                  # long gap: the next drop is far away
    t = 5 + 2 * 6.0 + 0.8
    line._set("CH_fg", t, t + 4.0, 0.5)
    res = line.run()
    s = next(r for r in kinds(res, "sachet") if abs(r["t"] - t) < 0.15)
    assert s["verdict"] == "STUCK IN CHUTE" and s["alert"] == "alarm"


def test_double_strip():
    line = normal_line(n=30)
    t = 5 + 25 * 3.0 + 0.8
    line.sachet(t, size=0.72)
    res = line.run()
    s = next(r for r in kinds(res, "sachet") if abs(r["t"] - t) < 0.15)
    assert s["double_strip"]
    st = next(r for r in kinds(res, "sets") if s["sachet_id"] in r["sachet_ids"])
    assert st["status"] == "DOUBLE" and st["double_strips"] == 1 and st["alert"] == "warn"


def test_parked_tray_is_not_a_set():
    line = Line(30)
    line._set("drop_meat", 5, 25, 0.2)                                   # meat present but nothing moves (line stop)
    assert kinds(line.run(), "sets") == []


def test_results_are_streamed_not_held_to_the_end():
    line = normal_line(n=20)
    eng = SachetChecker(CFG)
    when = {}
    for i, r in enumerate(line.rows):
        for out in eng.push(r):
            key = (out["kind"], out.get("sachet_id", out.get("set_group_id")))
            when[key] = i / 10 - (out["t"] if out["kind"] == "sachet" else out["t1"])
    lat_s = [v for (k, _), v in when.items() if k == "sachet"]
    lat_set = [v for (k, _), v in when.items() if k == "sets"]
    assert len(lat_s) >= 18 and max(lat_s) <= 5.0          # landing verdict ~4.5 s after the drop
    assert len(lat_set) >= 18 and max(lat_set) <= 2.0      # set verdict ~1.5 s after the set leaves
