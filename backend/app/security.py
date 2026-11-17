"""Password hashing (bcrypt) and JWT creation / verification."""
import uuid
from datetime import timedelta, timezone

import bcrypt
import jwt

from .config import get_settings
from .utils import utcnow

MAX_PASSWORD_BYTES = 72  # bcrypt ignores bytes past 72, so longer passwords are rejected


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: str, role: str) -> tuple[str, int]:
    """Return (token, expires_in_seconds). Each token has a unique `jti` so it can be revoked."""
    s = get_settings()
    now = utcnow().replace(tzinfo=timezone.utc)
    expire = now + timedelta(minutes=s.access_token_expire_minutes)
    payload = {
        "sub": user_id,
        "role": role,
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    token = jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)
    return token, s.access_token_expire_minutes * 60


def decode_token(token: str) -> dict:
    """Raises jwt.PyJWTError on a bad signature, an expired token, or malformed input."""
    s = get_settings()
    return jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
