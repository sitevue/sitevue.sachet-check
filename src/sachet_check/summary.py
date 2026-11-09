"""Counts over a list of results (what `sachet run` prints at the end)."""
from __future__ import annotations

from collections import Counter

SET_STATUSES = ("ok", "MISSING", "EXTRA", "DOUBLE", "partial", "fragment")
VERDICTS = ("IN BAG", "EMPTY BAG", "OUTSIDE BAG", "STUCK IN CHUTE", "NOT SEEN")


def summarize(results, since: float | None = None) -> dict:
    """Counts over results with timestamp >= since (all when None)."""
    rs = [r for r in results if since is None or r["timestamp"] >= since]
    sets = [r for r in rs if r["kind"] == "sets"]
    sach = [r for r in rs if r["kind"] == "sachet"]
    judged = [r for r in sets if r["status"] not in ("partial", "fragment")]
    st, vd = Counter(r["status"] for r in sets), Counter(r["verdict"] for r in sach)
    n_sets = sum(r["sets"] for r in judged)
    missing = sum(r["missing"] for r in judged)
    alerts = [r for r in rs if r.get("alert") not in (None, "none")]
    return dict(
        sets_checked=n_sets,
        sets_missing_sachet=missing,
        sets_with_double_sachet=sum(r["double_strips"] for r in judged),
        extra_sachets=sum(r["extra"] for r in judged),
        sachet_on_every_set_pct=round(100.0 * (n_sets - missing) / n_sets, 2) if n_sets else None,
        set_status_counts={s: st.get(s, 0) for s in SET_STATUSES},
        sachets_dropped=len(sach),
        landing_counts={v: vd.get(v, 0) for v in VERDICTS},
        alarms=sum(r["alert"] == "alarm" for r in alerts),
        warnings=sum(r["alert"] == "warn" for r in alerts),
        last_alert=alerts[-1] if alerts else None,
    )
