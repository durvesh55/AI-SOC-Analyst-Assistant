"""Registration, login, logout, profile and password change."""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from ..config import get_settings
from ..database import get_db
from ..deps import client_ip, get_current_user
from ..schemas import ChangePassword, LoginRequest, ProfileUpdate, RegisterRequest
from ..security import create_access_token, hash_password, verify_password
from ..services.audit import log_event
from ..utils import serialize, utcnow

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Pre-computed hash used to burn the same CPU time when the user does not exist (timing attacks).
_DUMMY_HASH = hash_password("dummy-password-1")
MAX_FAILED_ATTEMPTS = 10  # per identifier, per window
LOCKOUT_WINDOW = timedelta(minutes=15)


def public_user(user: dict) -> dict:
    """Never return the password hash or internal token data."""
    return serialize(
        {k: v for k, v in user.items() if k not in ("password_hash", "_token")}
    )


def _authenticate(db: Database, identifier: str, password: str, request: Request) -> dict:
    ident = identifier.strip().lower()
    ip = client_ip(request)

    recent_failures = db.audit_logs.count_documents(
        {"action": "LOGIN_FAILED", "details.identifier": ident,
         "timestamp": {"$gte": utcnow() - LOCKOUT_WINDOW}}
    )
    if recent_failures >= MAX_FAILED_ATTEMPTS:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many failed attempts. Try again later.")

    user = db.users.find_one({"$or": [{"email": ident}, {"username": ident}]})
    ok = verify_password(password, user["password_hash"] if user else _DUMMY_HASH)
    if not user or not ok:
        log_event(db, "LOGIN_FAILED", actor_username=ident[:60], ip=ip,
                  details={"identifier": ident[:254]})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials",
                            headers={"WWW-Authenticate": "Bearer"})
    if not user.get("is_active", False):
        log_event(db, "LOGIN_FAILED", actor=user, ip=ip, details={"identifier": ident[:254], "reason": "disabled"})
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")

    db.users.update_one({"_id": user["_id"]}, {"$set": {"last_login": utcnow()}})
    log_event(db, "LOGIN", actor=user, resource_type="user", resource_id=str(user["_id"]), ip=ip)
    return user


def _token_response(user: dict) -> dict:
    token, expires_in = create_access_token(str(user["_id"]), user["role"])
    return {"access_token": token, "token_type": "bearer", "expires_in": expires_in, "user": public_user(user)}


@router.post("/register", status_code=201, summary="Register a new Analyst account")
def register(body: RegisterRequest, request: Request, db: Database = Depends(get_db)):
    """Self-registration always creates an **Analyst**. Only an Admin can grant the Admin role.

    If REGISTRATION_INVITE_CODE is configured, the correct `invite_code` must be supplied."""
    required = get_settings().registration_invite_code
    if required and not secrets.compare_digest((body.invite_code or "").encode(), required.encode()):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "A valid invite code is required to register")
    now = utcnow()
    doc = {
        "username": body.username,
        "email": body.email.lower(),
        "full_name": body.full_name.strip(),
        "password_hash": hash_password(body.password),
        "role": "Analyst",
        "is_active": True,
        "created_at": now,
        "updated_at": now,
        "last_login": None,
    }
    try:
        result = db.users.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username or email is already in use")
    doc["_id"] = result.inserted_id
    log_event(db, "REGISTER", actor=doc, resource_type="user", resource_id=str(doc["_id"]),
              ip=client_ip(request))
    return public_user(doc)


@router.post("/login", summary="Log in with username/email + password (JSON)")
def login(body: LoginRequest, request: Request, db: Database = Depends(get_db)):
    user = _authenticate(db, body.identifier, body.password, request)
    return _token_response(user)


@router.post("/token", summary="OAuth2 form login (used by the Swagger 'Authorize' button)")
def login_form(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Database = Depends(get_db)):
    user = _authenticate(db, form.username, form.password, request)
    return _token_response(user)


@router.post("/logout", summary="Revoke the current token")
def logout(request: Request, user: dict = Depends(get_current_user), db: Database = Depends(get_db)):
    tok = user["_token"]
    expires_at = datetime.fromtimestamp(tok["exp"], tz=timezone.utc).replace(tzinfo=None)
    db.revoked_tokens.update_one({"jti": tok["jti"]}, {"$set": {"jti": tok["jti"], "expires_at": expires_at}},
                                 upsert=True)
    log_event(db, "LOGOUT", actor=user, resource_type="user", resource_id=str(user["_id"]), ip=client_ip(request))
    return {"detail": "Logged out"}


@router.get("/me", summary="Current user")
def me(user: dict = Depends(get_current_user)):
    return public_user(user)


@router.patch("/me", summary="Update own profile")
def update_me(body: ProfileUpdate, request: Request, user: dict = Depends(get_current_user),
              db: Database = Depends(get_db)):
    changes = {}
    if body.full_name is not None:
        changes["full_name"] = body.full_name.strip()
    if body.email is not None:
        changes["email"] = body.email.lower()
    if not changes:
        return public_user(user)
    changes["updated_at"] = utcnow()
    try:
        db.users.update_one({"_id": user["_id"]}, {"$set": changes})
    except DuplicateKeyError:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email is already in use")
    log_event(db, "PROFILE_UPDATED", actor=user, resource_type="user", resource_id=str(user["_id"]),
              ip=client_ip(request), details={"fields": [k for k in changes if k != "updated_at"]})
    return public_user(db.users.find_one({"_id": user["_id"]}))


@router.post("/change-password", summary="Change own password (revokes the current token)")
def change_password(body: ChangePassword, request: Request, user: dict = Depends(get_current_user),
                    db: Database = Depends(get_db)):
    if not verify_password(body.current_password, user["password_hash"]):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Current password is incorrect")
    db.users.update_one({"_id": user["_id"]},
                        {"$set": {"password_hash": hash_password(body.new_password), "updated_at": utcnow()}})
    tok = user["_token"]
    db.revoked_tokens.update_one(
        {"jti": tok["jti"]},
        {"$set": {"jti": tok["jti"],
                  "expires_at": datetime.fromtimestamp(tok["exp"], tz=timezone.utc).replace(tzinfo=None)}},
        upsert=True)
    log_event(db, "PASSWORD_CHANGED", actor=user, resource_type="user", resource_id=str(user["_id"]),
              ip=client_ip(request))
    return {"detail": "Password changed. Please log in again."}
