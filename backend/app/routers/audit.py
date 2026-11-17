"""Read-only audit log API. There are intentionally NO create/update/delete endpoints."""
import re
from datetime import date

from fastapi import APIRouter, Depends, Query
from pymongo.database import Database

from ..database import get_db
from ..deps import get_current_user
from ..services.audit import AUDIT_ACTIONS
from ..services.common import date_range
from ..utils import serialize

router = APIRouter(prefix="/api/audit-logs", tags=["Audit Logs"])


@router.get("/actions", summary="All audit action names (for filter dropdowns)")
def actions(user: dict = Depends(get_current_user)):
    return AUDIT_ACTIONS


@router.get("", summary="List audit entries (Admins see all; Analysts see only their own)")
def list_audit(
    action: str | None = Query(None, max_length=40),
    actor: str | None = Query(None, max_length=60, description="Username contains"),
    q: str | None = Query(None, max_length=100, description="Resource id contains"),
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: Database = Depends(get_db),
):
    query: dict = {}
    if user["role"] != "Admin":
        query["actor_id"] = user["_id"]  # enforced server-side, whatever the client asks for
    if action:
        query["action"] = action
    if actor and user["role"] == "Admin":
        query["actor_username"] = {"$regex": re.escape(actor.strip().lower()), "$options": "i"}
    if q:
        query["resource_id"] = {"$regex": re.escape(q.strip()), "$options": "i"}
    rng = date_range(date_from, date_to)
    if rng:
        query["timestamp"] = rng
    total = db.audit_logs.count_documents(query)
    items = list(db.audit_logs.find(query).sort("timestamp", -1).skip((page - 1) * page_size).limit(page_size))
    return {"items": serialize(items), "total": total, "page": page, "page_size": page_size}
