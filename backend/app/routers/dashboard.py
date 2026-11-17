"""Dashboard statistics - every number is computed from the database on each request."""
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from pymongo.database import Database

from ..database import ALERT_STATUSES, SEVERITIES, CASE_STATUSES, CATEGORIES, get_db
from ..deps import get_current_user
from ..services.mitre import technique_catalog
from ..utils import serialize, utcnow

router = APIRouter(prefix="/api", tags=["Dashboard"])


def _group(db: Database, collection: str, field: str, match: dict | None = None) -> dict:
    pipeline = ([{"$match": match}] if match else []) + [{"$group": {"_id": f"${field}", "n": {"$sum": 1}}}]
    return {r["_id"]: r["n"] for r in getattr(db, collection).aggregate(pipeline)}


@router.get("/dashboard", summary="Dashboard statistics")
def dashboard(days: int = Query(14, ge=3, le=90), user: dict = Depends(get_current_user),
              db: Database = Depends(get_db)):
    by_sev = _group(db, "alerts", "severity")
    by_status = _group(db, "alerts", "status")
    case_status = _group(db, "cases", "status")

    # --- analyst workload: open alerts + open cases per assignee ---
    open_alerts = _group(db, "alerts", "assigned_to", {"status": {"$in": ["New", "Under Investigation"]}})
    open_cases = _group(db, "cases", "assigned_to", {"status": {"$in": ["Open", "In Progress"]}})
    workload = []
    for u in db.users.find({"is_active": True}, {"username": 1, "full_name": 1}).sort("username", 1):
        workload.append({"user_id": str(u["_id"]), "username": u["username"], "full_name": u.get("full_name", ""),
                         "open_alerts": open_alerts.get(u["_id"], 0), "open_cases": open_cases.get(u["_id"], 0)})

    # --- alert trend: alerts created per day for the last N days (zero-filled) ---
    today = utcnow().date()
    start = today - timedelta(days=days - 1)
    counts = {}
    for a in db.alerts.find({"created_at": {"$gte": utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                                             - timedelta(days=days - 1)}}, {"created_at": 1}):
        d = a["created_at"].date().isoformat()
        counts[d] = counts.get(d, 0) + 1
    trend = [{"date": (start + timedelta(days=i)).isoformat(),
              "count": counts.get((start + timedelta(days=i)).isoformat(), 0)} for i in range(days)]

    # --- recent activity: admins see everything, analysts only their own ---
    act_query = {} if user["role"] == "Admin" else {"actor_id": user["_id"]}
    recent = list(db.audit_logs.find(act_query).sort("timestamp", -1).limit(10))

    return {
        "total_alerts": sum(by_sev.values()),
        "alerts_by_severity": {s: by_sev.get(s, 0) for s in SEVERITIES},
        "alerts_by_status": {s: by_status.get(s, 0) for s in ALERT_STATUSES},
        "false_positives": by_status.get("False Positive", 0),
        "total_cases": sum(case_status.values()),
        "cases_by_status": {s: case_status.get(s, 0) for s in CASE_STATUSES},
        "open_cases": case_status.get("Open", 0) + case_status.get("In Progress", 0),
        "resolved_cases": case_status.get("Closed", 0),
        "analyst_workload": workload,
        "alert_trend": trend,
        "recent_activities": serialize(recent),
    }


@router.get("/meta", tags=["Meta"], summary="Enumerations used by the UI (severities, statuses, categories)")
def meta():
    return {"severities": SEVERITIES, "alert_statuses": ALERT_STATUSES, "case_statuses": CASE_STATUSES,
            "categories": CATEGORIES, "roles": ["Admin", "Analyst"]}


@router.get("/mitre/techniques", tags=["MITRE ATT&CK"], summary="Techniques the rule engine can suggest")
def mitre_catalog(user: dict = Depends(get_current_user)):
    return technique_catalog()
