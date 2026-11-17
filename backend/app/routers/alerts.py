"""Alert management: create, list/search/filter, view, update, assign."""
import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pymongo.database import Database

from ..database import get_db
from ..deps import client_ip, get_current_user
from ..schemas import AlertCreate, AlertUpdate, AssignRequest
from ..services.audit import log_event
from ..services.common import date_range, history_entry
from ..services.lookup import attach_users, resolve_assignee
from ..services.mitre import suggest_techniques
from ..utils import next_sequence, serialize, to_object_id, utcnow

router = APIRouter(prefix="/api/alerts", tags=["Alerts"])

EDITABLE = ("title", "description", "severity", "category", "status", "source_ip",
            "destination_ip", "hostname", "affected_user", "indicators")


def can_modify_alert(user: dict, alert: dict) -> bool:
    """Admins can change any alert; analysts only unassigned alerts or their own."""
    return user["role"] == "Admin" or alert.get("assigned_to") in (None, user["_id"])


def get_alert_or_404(db: Database, alert_id: str) -> dict:
    alert = db.alerts.find_one({"_id": to_object_id(alert_id, "Alert")})
    if not alert:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")
    return alert


def present(db: Database, alert: dict) -> dict:
    attach_users(db, [alert], ("assigned_to", "created_by"))
    return serialize(alert)


@router.post("", status_code=201, summary="Create an alert")
def create_alert(body: AlertCreate, request: Request, user: dict = Depends(get_current_user),
                 db: Database = Depends(get_db)):
    now = utcnow()
    assigned = resolve_assignee(db, user, body.assigned_to)
    doc = {
        "alert_id": f"ALT-{next_sequence(db, 'alert'):06d}",
        **body.model_dump(exclude={"assigned_to", "event_time"}),
        "status": "New",
        "assigned_to": assigned,
        "case_id": None,
        "event_time": body.event_time.replace(tzinfo=None) if body.event_time else now,
        "created_by": user["_id"],
        "created_at": now,
        "updated_at": now,
    }
    doc["mitre_suggestions"] = suggest_techniques(doc)
    doc["history"] = [history_entry(user, "Created", f"Alert created with severity {doc['severity']}")]
    doc["_id"] = db.alerts.insert_one(doc).inserted_id
    log_event(db, "ALERT_CREATED", actor=user, resource_type="alert", resource_id=doc["alert_id"],
              ip=client_ip(request), details={"severity": doc["severity"], "category": doc["category"]})
    return present(db, doc)


@router.get("", summary="List / search / filter alerts")
def list_alerts(
    q: str | None = Query(None, max_length=100, description="Search title, description, id, IPs, host"),
    severity: str | None = Query(None, pattern="^(Critical|High|Medium|Low)$"),
    status_: str | None = Query(None, alias="status",
                                pattern="^(New|Under Investigation|Resolved|False Positive)$"),
    category: str | None = Query(None, max_length=50),
    assigned_to: str | None = Query(None, description="User id, 'me' or 'unassigned'"),
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    query: dict = {}
    if severity:
        query["severity"] = severity
    if status_:
        query["status"] = status_
    if category:
        query["category"] = category
    if assigned_to == "me":
        query["assigned_to"] = user["_id"]
    elif assigned_to == "unassigned":
        query["assigned_to"] = None
    elif assigned_to:
        query["assigned_to"] = to_object_id(assigned_to, "Assignee")
    rng = date_range(date_from, date_to)
    if rng:
        query["created_at"] = rng
    if q:
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}  # escaped: no regex injection
        query["$or"] = [{f: rx} for f in ("title", "description", "alert_id", "source_ip",
                                          "destination_ip", "hostname", "affected_user")]

    total = db.alerts.count_documents(query)
    items = list(db.alerts.find(query, {"history": 0}).sort("created_at", -1)
                 .skip((page - 1) * page_size).limit(page_size))
    attach_users(db, items, ("assigned_to",))
    return {"items": serialize(items), "total": total, "page": page, "page_size": page_size}


@router.get("/{alert_id}", summary="Alert details (includes history + MITRE suggestions)")
def get_alert(alert_id: str, user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    alert = get_alert_or_404(db, alert_id)
    result = present(db, alert)
    if alert.get("case_id"):
        case = db.cases.find_one({"_id": alert["case_id"]}, {"case_id": 1, "status": 1})
        result["case"] = serialize(case) if case else None
    return result


@router.patch("/{alert_id}", summary="Update alert fields and/or status")
def update_alert(alert_id: str, body: AlertUpdate, request: Request,
                 user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    alert = get_alert_or_404(db, alert_id)
    if not can_modify_alert(user, alert):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This alert is assigned to another analyst")

    updates = body.model_dump(exclude_unset=True)
    changes, details = {}, []
    for field in EDITABLE:
        if field in updates and updates[field] != alert.get(field):
            changes[field] = updates[field]
            details.append(f"{field}: {alert.get(field)!r} -> {updates[field]!r}"[:300])
    if not changes:
        return present(db, alert)

    merged = {**alert, **changes}
    changes["mitre_suggestions"] = suggest_techniques(merged)
    changes["updated_at"] = utcnow()
    action = "Status changed" if "status" in changes and len(details) == 1 else "Updated"
    db.alerts.update_one(
        {"_id": alert["_id"]},
        {"$set": changes, "$push": {"history": history_entry(user, action, "; ".join(details))}},
    )
    if "status" in changes:
        log_event(db, "ALERT_STATUS_CHANGED", actor=user, resource_type="alert", resource_id=alert["alert_id"],
                  ip=client_ip(request), details={"from": alert["status"], "to": changes["status"]})
    if set(changes) - {"status", "mitre_suggestions", "updated_at"}:
        log_event(db, "ALERT_UPDATED", actor=user, resource_type="alert", resource_id=alert["alert_id"],
                  ip=client_ip(request),
                  details={"fields": [k for k in changes if k not in ("mitre_suggestions", "updated_at", "status")]})
    return present(db, db.alerts.find_one({"_id": alert["_id"]}))


@router.post("/{alert_id}/assign", summary="Assign / unassign an alert")
def assign_alert(alert_id: str, body: AssignRequest, request: Request,
                 user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    alert = get_alert_or_404(db, alert_id)
    if not can_modify_alert(user, alert):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This alert is assigned to another analyst")
    new_assignee = resolve_assignee(db, user, body.assignee_id)
    label = "unassigned"
    if new_assignee:
        label = db.users.find_one({"_id": new_assignee})["username"]
    db.alerts.update_one(
        {"_id": alert["_id"]},
        {"$set": {"assigned_to": new_assignee, "updated_at": utcnow()},
         "$push": {"history": history_entry(user, "Assigned", f"Assigned to {label}")}},
    )
    log_event(db, "ALERT_ASSIGNED", actor=user, resource_type="alert", resource_id=alert["alert_id"],
              ip=client_ip(request), details={"assignee": label})
    return present(db, db.alerts.find_one({"_id": alert["_id"]}))
