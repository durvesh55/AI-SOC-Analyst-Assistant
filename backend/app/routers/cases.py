"""Incident cases: create from alerts, assign, notes, findings, close/reopen, PDF report."""
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pymongo.database import Database

from ..database import get_db
from ..deps import client_ip, get_current_user, require_admin
from ..schemas import AssignRequest, CaseClose, CaseCreate, CaseReopen, CaseUpdate, NoteCreate
from ..services.audit import log_event
from ..services.common import highest_severity, history_entry
from ..services.lookup import attach_users, resolve_assignee
from ..services.pdf import build_case_report
from ..utils import next_sequence, serialize, to_object_id, utcnow

router = APIRouter(prefix="/api/cases", tags=["Cases"])


def can_modify_case(user: dict, case: dict) -> bool:
    """Admins can change any case; analysts only cases assigned to them."""
    return user["role"] == "Admin" or case.get("assigned_to") == user["_id"]


def get_case_or_404(db: Database, case_id: str) -> dict:
    case = db.cases.find_one({"_id": to_object_id(case_id, "Case")})
    if not case:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Case not found")
    return case


def require_writable(user: dict, case: dict) -> None:
    if not can_modify_case(user, case):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This case is not assigned to you")
    if case["status"] == "Closed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Case is closed; an administrator must reopen it first")


def present(db: Database, case: dict) -> dict:
    attach_users(db, [case], ("assigned_to", "created_by", "closed_by"))
    out = serialize(case)
    alerts = list(db.alerts.find({"_id": {"$in": case.get("alert_object_ids", [])}},
                                 {"history": 0, "mitre_suggestions": 0}))
    out["alerts"] = serialize(alerts)
    out.pop("alert_object_ids", None)
    return out


def _push(db: Database, case: dict, user: dict, action: str, detail: str, extra_set: dict | None = None):
    db.cases.update_one(
        {"_id": case["_id"]},
        {"$set": {"updated_at": utcnow(), **(extra_set or {})},
         "$push": {"timeline": history_entry(user, action, detail)}},
    )


@router.post("", status_code=201, summary="Create an investigation case from one or more alerts")
def create_case(body: CaseCreate, request: Request, user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)):
    oids = [to_object_id(a, "Alert") for a in dict.fromkeys(body.alert_ids)]
    alerts = list(db.alerts.find({"_id": {"$in": oids}}))
    if len(alerts) != len(oids):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "One or more alerts were not found")
    for a in alerts:
        if a.get("case_id"):
            raise HTTPException(status.HTTP_409_CONFLICT, f"{a['alert_id']} already belongs to a case")
        if user["role"] != "Admin" and a.get("assigned_to") not in (None, user["_id"]):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"{a['alert_id']} is assigned to another analyst")

    assignee = resolve_assignee(db, user, body.assignee_id) if body.assignee_id else user["_id"]
    now = utcnow()
    mitre, seen = [], set()
    for a in alerts:
        for m in a.get("mitre_suggestions", []):
            if m["technique_id"] not in seen:
                seen.add(m["technique_id"])
                mitre.append(m)

    case = {
        "case_id": f"CASE-{next_sequence(db, 'case'):06d}",
        "title": body.title or f"Investigation: {alerts[0]['title']}"[:200],
        "status": "Open",
        "severity": highest_severity([a["severity"] for a in alerts]),
        "alert_object_ids": [a["_id"] for a in alerts],
        "alert_ids": [a["alert_id"] for a in alerts],
        "assigned_to": assignee,
        "notes": [],
        "findings": "",
        "conclusion": "",
        "outcome": None,
        "mitre_suggestions": mitre,
        "timeline": [history_entry(user, "Case created", "Created from " + ", ".join(a["alert_id"] for a in alerts))],
        "created_by": user["_id"],
        "created_at": now,
        "updated_at": now,
        "closed_at": None,
        "closed_by": None,
    }
    case["_id"] = db.cases.insert_one(case).inserted_id

    for a in alerts:  # link alerts + move them to "Under Investigation"
        db.alerts.update_one(
            {"_id": a["_id"]},
            {"$set": {"case_id": case["_id"], "status": "Under Investigation",
                      "assigned_to": a.get("assigned_to") or assignee, "updated_at": now},
             "$push": {"history": history_entry(user, "Case created", f"Linked to {case['case_id']}")}},
        )
    log_event(db, "CASE_CREATED", actor=user, resource_type="case", resource_id=case["case_id"],
              ip=client_ip(request), details={"alerts": case["alert_ids"], "severity": case["severity"]})
    return present(db, case)


@router.get("", summary="List / filter cases")
def list_cases(
    q: str | None = Query(None, max_length=100),
    status_: str | None = Query(None, alias="status", pattern="^(Open|In Progress|Closed)$"),
    severity: str | None = Query(None, pattern="^(Critical|High|Medium|Low)$"),
    assigned_to: str | None = Query(None, description="User id, 'me' or 'unassigned'"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    query: dict = {}
    if status_:
        query["status"] = status_
    if severity:
        query["severity"] = severity
    if assigned_to == "me":
        query["assigned_to"] = user["_id"]
    elif assigned_to == "unassigned":
        query["assigned_to"] = None
    elif assigned_to:
        query["assigned_to"] = to_object_id(assigned_to, "Assignee")
    if q:
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        query["$or"] = [{"title": rx}, {"case_id": rx}, {"alert_ids": rx}]
    total = db.cases.count_documents(query)
    items = list(db.cases.find(query, {"notes": 0, "timeline": 0, "alert_object_ids": 0})
                 .sort("created_at", -1).skip((page - 1) * page_size).limit(page_size))
    attach_users(db, items, ("assigned_to",))
    return {"items": serialize(items), "total": total, "page": page, "page_size": page_size}


@router.get("/{case_id}", summary="Full case: alerts, notes, timeline, MITRE")
def get_case(case_id: str, user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    return present(db, get_case_or_404(db, case_id))


@router.patch("/{case_id}", summary="Update title / severity / status / findings / conclusion")
def update_case(case_id: str, body: CaseUpdate, request: Request, user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)):
    case = get_case_or_404(db, case_id)
    require_writable(user, case)
    updates = body.model_dump(exclude_unset=True)
    changes = {k: v for k, v in updates.items() if v is not None and v != case.get(k)}
    if not changes:
        return present(db, case)
    parts = []
    for k, v in changes.items():
        parts.append(f"{k} updated" if k in ("findings", "conclusion") else f"{k}: {case.get(k)} -> {v}")
    _push(db, case, user, "Case updated", "; ".join(parts), changes)
    if "status" in changes:
        log_event(db, "CASE_STATUS_CHANGED", actor=user, resource_type="case", resource_id=case["case_id"],
                  ip=client_ip(request), details={"from": case["status"], "to": changes["status"]})
    if set(changes) - {"status"}:
        log_event(db, "CASE_UPDATED", actor=user, resource_type="case", resource_id=case["case_id"],
                  ip=client_ip(request), details={"fields": [k for k in changes if k != "status"]})
    return present(db, db.cases.find_one({"_id": case["_id"]}))


@router.post("/{case_id}/assign", summary="Assign / unassign a case")
def assign_case(case_id: str, body: AssignRequest, request: Request, user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)):
    case = get_case_or_404(db, case_id)
    # Analysts may claim an unassigned case; otherwise only the assignee/Admin may reassign it.
    if not (can_modify_case(user, case) or case.get("assigned_to") is None):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This case is not assigned to you")
    if case["status"] == "Closed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Case is closed")
    new_assignee = resolve_assignee(db, user, body.assignee_id)
    label = db.users.find_one({"_id": new_assignee})["username"] if new_assignee else "unassigned"
    _push(db, case, user, "Assigned", f"Assigned to {label}", {"assigned_to": new_assignee})
    log_event(db, "CASE_ASSIGNED", actor=user, resource_type="case", resource_id=case["case_id"],
              ip=client_ip(request), details={"assignee": label})
    return present(db, db.cases.find_one({"_id": case["_id"]}))


@router.post("/{case_id}/notes", status_code=201, summary="Add an investigation note")
def add_note(case_id: str, body: NoteCreate, request: Request, user: dict = Depends(get_current_user),
             db: Database = Depends(get_db)):
    case = get_case_or_404(db, case_id)
    require_writable(user, case)
    note = {"id": uuid.uuid4().hex, "author_id": user["_id"], "author_username": user["username"],
            "text": body.text.strip(), "created_at": utcnow()}
    db.cases.update_one(
        {"_id": case["_id"]},
        {"$push": {"notes": note,
                   "timeline": history_entry(user, "Note added", body.text.strip()[:140])},
         "$set": {"updated_at": utcnow()}},
    )
    log_event(db, "NOTE_ADDED", actor=user, resource_type="case", resource_id=case["case_id"],
              ip=client_ip(request), details={"note_id": note["id"], "length": len(note["text"])})
    return present(db, db.cases.find_one({"_id": case["_id"]}))


@router.post("/{case_id}/close", summary="Close a case with a conclusion and outcome")
def close_case(case_id: str, body: CaseClose, request: Request, user: dict = Depends(get_current_user),
               db: Database = Depends(get_db)):
    case = get_case_or_404(db, case_id)
    require_writable(user, case)
    now = utcnow()
    _push(db, case, user, "Case closed", f"Outcome: {body.outcome}",
          {"status": "Closed", "conclusion": body.conclusion.strip(), "outcome": body.outcome,
           "closed_at": now, "closed_by": user["_id"]})
    for aid in case.get("alert_object_ids", []):
        db.alerts.update_one(
            {"_id": aid},
            {"$set": {"status": body.outcome, "updated_at": now},
             "$push": {"history": history_entry(user, "Status changed",
                                                f"Case {case['case_id']} closed: {body.outcome}")}},
        )
    log_event(db, "CASE_CLOSED", actor=user, resource_type="case", resource_id=case["case_id"],
              ip=client_ip(request), details={"outcome": body.outcome})
    return present(db, db.cases.find_one({"_id": case["_id"]}))


@router.post("/{case_id}/reopen", summary="Reopen a closed case (Admin only)")
def reopen_case(case_id: str, body: CaseReopen, request: Request, admin: dict = Depends(require_admin),
                db: Database = Depends(get_db)):
    case = get_case_or_404(db, case_id)
    if case["status"] != "Closed":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only closed cases can be reopened")
    now = utcnow()
    _push(db, case, admin, "Case reopened", body.reason.strip(),
          {"status": "In Progress", "closed_at": None, "closed_by": None, "outcome": None})
    for aid in case.get("alert_object_ids", []):
        db.alerts.update_one(
            {"_id": aid},
            {"$set": {"status": "Under Investigation", "updated_at": now},
             "$push": {"history": history_entry(admin, "Status changed", f"Case {case['case_id']} reopened")}},
        )
    log_event(db, "CASE_REOPENED", actor=admin, resource_type="case", resource_id=case["case_id"],
              ip=client_ip(request), details={"reason": body.reason.strip()[:200]})
    return present(db, db.cases.find_one({"_id": case["_id"]}))


@router.get("/{case_id}/report", summary="Download the investigation report as a PDF")
def case_report(case_id: str, request: Request, user: dict = Depends(get_current_user),
                db: Database = Depends(get_db)):
    case = get_case_or_404(db, case_id)
    alerts = list(db.alerts.find({"_id": {"$in": case.get("alert_object_ids", [])}}))
    assignee = "Unassigned"
    if case.get("assigned_to"):
        u = db.users.find_one({"_id": case["assigned_to"]})
        if u:
            assignee = f"{u.get('full_name') or u['username']} ({u['username']})"
    now = utcnow()
    pdf = build_case_report(case, alerts, assignee, user["username"], now)
    log_event(db, "REPORT_GENERATED", actor=user, resource_type="case", resource_id=case["case_id"],
              ip=client_ip(request), details={"bytes": len(pdf)})
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{case["case_id"]}-report.pdf"'})
