"""Small helpers shared by routers: time, ObjectId parsing, serialisation."""
from datetime import datetime, timezone

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import HTTPException, status


def utcnow() -> datetime:
    """Current UTC time as a *naive* datetime (MongoDB stores datetimes as UTC)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_object_id(value: str, label: str = "Resource") -> ObjectId:
    """Convert a string to ObjectId or raise a clean 404 (never leak internals)."""
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} not found")


def serialize(value):
    """Recursively convert Mongo values (ObjectId, datetime) to JSON-friendly ones."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat() + "Z"
    if isinstance(value, dict):
        return {("id" if k == "_id" else k): serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serialize(v) for v in value]
    return value


def next_sequence(db, name: str) -> int:
    """Atomic auto-increment counter (used for ALT-000001 / CASE-000001 style IDs)."""
    doc = db.counters.find_one_and_update(
        {"_id": name}, {"$inc": {"seq": 1}}, upsert=True, return_document=True
    )
    return doc["seq"]
