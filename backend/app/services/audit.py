"""Append-only audit trail. There is deliberately NO update/delete helper and no API for them."""
import re

from pymongo.database import Database

from ..utils import utcnow

AUDIT_ACTIONS = [
    "LOGIN", "LOGIN_FAILED", "LOGOUT", "REGISTER", "PASSWORD_CHANGED", "PROFILE_UPDATED",
    "ALERT_CREATED", "ALERT_UPDATED", "ALERT_STATUS_CHANGED", "ALERT_ASSIGNED",
    "CASE_CREATED", "CASE_UPDATED", "CASE_ASSIGNED", "CASE_STATUS_CHANGED",
    "NOTE_ADDED", "CASE_CLOSED", "CASE_REOPENED", "REPORT_GENERATED",
    "USER_CREATED", "USER_UPDATED",
]

_SENSITIVE = re.compile(r"pass|token|secret|hash|authorization", re.I)


def _clean(details: dict | None) -> dict:
    """Drop anything that looks like a credential so it can never reach the log."""
    if not details:
        return {}
    return {k: v for k, v in details.items() if not _SENSITIVE.search(k)}


def log_event(
    db: Database,
    action: str,
    actor: dict | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict | None = None,
    ip: str | None = None,
    actor_username: str | None = None,
) -> None:
    db.audit_logs.insert_one(
        {
            "timestamp": utcnow(),
            "action": action,
            "actor_id": actor["_id"] if actor else None,
            "actor_username": actor["username"] if actor else (actor_username or "anonymous"),
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": _clean(details),
            "ip": ip,
        }
    )
