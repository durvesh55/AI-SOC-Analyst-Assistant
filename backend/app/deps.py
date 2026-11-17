"""Reusable FastAPI dependencies: current user, role checks, client IP."""
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from pymongo.database import Database

from .database import get_db
from .security import decode_token
from .utils import to_object_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


def _unauthorized(detail: str = "Not authenticated") -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(token: str | None = Depends(oauth2_scheme), db: Database = Depends(get_db)) -> dict:
    """Verify the JWT, make sure it was not revoked, and load the (still active) user."""
    if not token:
        raise _unauthorized()
    try:
        payload = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Token expired")
    except jwt.PyJWTError:
        raise _unauthorized("Invalid token")

    jti, sub = payload.get("jti"), payload.get("sub")
    if not jti or not sub:
        raise _unauthorized("Invalid token")
    if db.revoked_tokens.find_one({"jti": jti}):
        raise _unauthorized("Token has been revoked")

    user = db.users.find_one({"_id": to_object_id(sub)})
    if not user or not user.get("is_active", False):
        raise _unauthorized("User not found or disabled")
    # The role always comes from the database, never from the (client-held) token.
    user["_token"] = {"jti": jti, "exp": payload.get("exp")}
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "Admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator privileges required")
    return user


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None
