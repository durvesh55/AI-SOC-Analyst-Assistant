"""Helpers for resolving user references (ObjectId -> display name)."""
from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.database import Database

from ..utils import to_object_id


def user_names(db: Database, ids) -> dict:
    """Map ObjectId -> {id, username, full_name} for the given ids (None values ignored)."""
    wanted = list({i for i in ids if isinstance(i, ObjectId)})
    if not wanted:
        return {}
    return {
        u["_id"]: {"id": str(u["_id"]), "username": u["username"], "full_name": u.get("full_name", "")}
        for u in db.users.find({"_id": {"$in": wanted}}, {"username": 1, "full_name": 1})
    }


def attach_users(db: Database, docs: list[dict], fields: tuple[str, ...]) -> None:
    """For every field (e.g. 'assigned_to') add '<field>_user' with the resolved name."""
    ids = [d.get(f) for d in docs for f in fields]
    names = user_names(db, ids)
    for d in docs:
        for f in fields:
            d[f + "_user"] = names.get(d.get(f))


def resolve_assignee(db: Database, actor: dict, assignee_id: str | None) -> ObjectId | None:
    """Validate who an item may be assigned to.

    Admins can assign to any active user (or unassign). Analysts may only claim an item for
    themselves or release it (assignee_id=None)."""
    if assignee_id is None:
        return None
    oid = to_object_id(assignee_id, "Assignee")
    if actor["role"] != "Admin" and oid != actor["_id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Analysts can only assign items to themselves")
    target = db.users.find_one({"_id": oid, "is_active": True})
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignee not found")
    return oid
