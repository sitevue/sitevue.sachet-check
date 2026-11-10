from sachet_check.summary import summarize


def test_summary_counts():
    rs = [dict(kind="sets", timestamp=0, sets=1, missing=0, extra=0, double_strips=0, status="ok", alert="none"),
          dict(kind="sets", timestamp=3, sets=1, missing=1, extra=0, double_strips=0, status="MISSING", alert="alarm"),
          dict(kind="sachet", timestamp=1, verdict="IN BAG", alert="none"),
          dict(kind="sachet", timestamp=5, verdict="EMPTY BAG", alert="warn")]
    s = summarize(rs)
    assert s["sets_checked"] == 2 and s["sets_missing_sachet"] == 1 and s["sachet_on_every_set_pct"] == 50.0
    assert s["landing_counts"]["EMPTY BAG"] == 1 and s["alarms"] == 1 and s["warnings"] == 1


def test_by_hand_is_not_counted_as_a_set():
    rs = [dict(kind="sets", timestamp=0, sets=1, missing=0, extra=0, double_strips=0, status="ok", alert="none"),
          dict(kind="sets", timestamp=3, sets=0, missing=0, extra=0, double_strips=0, status="by_hand", alert="warn")]
    s = summarize(rs)
    assert s["sets_checked"] == 1 and s["set_status_counts"]["by_hand"] == 1 and s["alarms"] == 0
