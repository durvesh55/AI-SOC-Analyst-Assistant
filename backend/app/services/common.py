"""Small pieces shared by the alert and case routers."""
from datetime import date, datetime, time, timedelta

from ..utils import utcnow

SEVERITY_ORDER = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}


def history_entry(user: dict, action: str, detail: str = "") -> dict:
    """One row of an alert's history / a case's timeline."""
    return {"at": utcnow(), "by_id": user["_id"], "by_username": user["username"],
            "action": action, "detail": detail}


def date_range(date_from: date | None, date_to: date | None) -> dict | None:
    """Inclusive [date_from, date_to] range as a Mongo comparison dict (None if no bounds)."""
    rng = {}
    if date_from:
        rng["$gte"] = datetime.combine(date_from, time.min)
    if date_to:
        rng["$lt"] = datetime.combine(date_to, time.min) + timedelta(days=1)
    return rng or None


def highest_severity(severities: list[str]) -> str:
    return max(severities, key=lambda s: SEVERITY_ORDER.get(s, 0)) if severities else "Low"
