"""User management (Admin only) and the assignable-users list (any signed-in user)."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from ..database import get_db
from ..deps import client_ip, get_current_user, require_admin
from ..schemas import AdminCreateUser, AdminUserUpdate
from ..security import hash_password
from ..services.audit import log_event
from ..utils import to_object_id, utcnow
from .auth import public_user

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/assignable", summary="Active users that work can be assigned to")
def assignable(user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    users = db.users.find({"is_active": True}, {"username": 1, "full_name": 1, "role": 1}).sort("username", 1)
    return [{"id": str(u["_id"]), "username": u["username"], "full_name": u.get("full_name", ""),
             "role": u["role"]} for u in users]


@router.get("", summary="List all users (Admin)")
def list_users(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
               admin: dict = Depends(require_admin), db: Database = Depends(get_db)):
    total = db.users.count_documents({})
    cursor = db.users.find({}).sort("created_at", 1).skip((page - 1) * page_size).limit(page_size)
    return {"items": [public_user(u) for u in cursor], "total": total, "page": page, "page_size": page_size}


@router.post("", status_code=201, summary="Create a user with any role (Admin)")
def create_user(body: AdminCreateUser, request: Request, admin: dict = Depends(require_admin),
                db: Database = Depends(get_db)):
    now = utcnow()
    doc = {
        "username": body.username, "email": body.email.lower(), "full_name": body.full_name.strip(),
        "password_hash": hash_password(body.password), "role": body.role, "is_active": True,
        "created_at": now, "updated_at": now, "last_login": None,
    }
    try:
        doc["_id"] = db.users.insert_one(doc).inserted_id
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username or email is already in use")
    log_event(db, "USER_CREATED", actor=admin, resource_type="user", resource_id=str(doc["_id"]),
              ip=client_ip(request), details={"username": doc["username"], "role": doc["role"]})
    return public_user(doc)


@router.patch("/{user_id}", summary="Change role / active flag / name (Admin)")
def update_user(user_id: str, body: AdminUserUpdate, request: Request,
                admin: dict = Depends(require_admin), db: Database = Depends(get_db)):
    oid = to_object_id(user_id, "User")
    target = db.users.find_one({"_id": oid})
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if oid == admin["_id"] and (body.role == "Analyst" or body.is_active is False):
        # Prevents the last administrator from locking themselves out.
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "You cannot demote or deactivate your own account")
    changes = body.model_dump(exclude_none=True)
    if not changes:
        return public_user(target)
    changes["updated_at"] = utcnow()
    db.users.update_one({"_id": oid}, {"$set": changes})
    log_event(db, "USER_UPDATED", actor=admin, resource_type="user", resource_id=user_id,
              ip=client_ip(request),
              details={"target": target["username"], "changes": {k: v for k, v in changes.items() if k != "updated_at"}})
    return public_user(db.users.find_one({"_id": oid}))
