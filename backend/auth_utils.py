"""Auth utilities: password hashing, session tokens, current-user dependency."""
import uuid
import bcrypt
from datetime import datetime, timezone, timedelta

from fastapi import Header, HTTPException, Query

from config import db

SESSION_TTL_DAYS = 7


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def new_user_id() -> str:
    return f"user_{uuid.uuid4().hex[:12]}"


async def create_session(user_id: str) -> str:
    token = f"st_{uuid.uuid4().hex}{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)
    await db.user_sessions.insert_one({
        "session_token": token,
        "user_id": user_id,
        "created_at": now.isoformat(),
        "expires_at": now + timedelta(days=SESSION_TTL_DAYS),
    })
    return token


async def _user_from_token(token: str | None):
    if not token:
        return None
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        return None
    expires_at = session["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        return None
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0, "password_hash": 0})
    return user


def _extract_bearer(authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None


async def get_current_user(authorization: str | None = Header(default=None)):
    user = await _user_from_token(_extract_bearer(authorization))
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


async def require_admin(authorization: str | None = Header(default=None)):
    user = await get_current_user(authorization)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def require_client(authorization: str | None = Header(default=None)):
    user = await get_current_user(authorization)
    if user.get("role") != "client":
        raise HTTPException(status_code=403, detail="Client access required")
    return user


async def user_from_token_or_header(
    authorization: str | None = Header(default=None),
    token: str | None = Query(default=None),
):
    """For image reads: web <img> can't send headers, so accept ?token= too."""
    user = await _user_from_token(_extract_bearer(authorization) or token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
