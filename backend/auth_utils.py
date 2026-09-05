"""Auth utilities: password hashing, session tokens, current-user dependency.

Two-path authentication:
- Phone JWT (HS256, iss=pik-connect) — phone OTP / password login.
- Opaque session token (user_sessions) — Google sign-in (Emergent Auth) and the
  platform super admin login.

All existing `Depends(...)` signatures are preserved so the ~200 protected
routes in server.py did not need to change.
"""
import uuid
import bcrypt
from datetime import datetime, timezone, timedelta

from fastapi import Header, HTTPException, Query

from config import db

SESSION_TTL_DAYS = 7


def looks_like_jwt(token: str) -> bool:
    """Quick shape check — real JWTs are three dot-separated base64 segments."""
    if not token:
        return False
    parts = token.split(".")
    return len(parts) == 3 and all(parts)


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
    """Opaque session token — used by Google sign-in and the super admin login."""
    token = f"st_{uuid.uuid4().hex}{uuid.uuid4().hex}"
    now = datetime.now(timezone.utc)
    await db.user_sessions.insert_one({
        "session_token": token,
        "user_id": user_id,
        "created_at": now.isoformat(),
        "expires_at": now + timedelta(days=SESSION_TTL_DAYS),
    })
    return token


async def _user_from_legacy_token(token: str | None):
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
    return await db.users.find_one(
        {"user_id": session["user_id"]}, {"_id": 0, "password_hash": 0}
    )


async def _user_from_token(token: str | None):
    """Resolve a phone JWT or an opaque session token."""
    if not token:
        return None
    if looks_like_jwt(token):
        # Phone-auth JWT (iss=pik-connect, HS256)
        from phone_auth_service import is_phone_jwt, verify_phone_jwt
        if not is_phone_jwt(token):
            return None
        claims = verify_phone_jwt(token)
        if not claims:
            return None
        user = await db.users.find_one(
            {"user_id": claims["sub"]}, {"_id": 0, "password_hash": 0}
        )
        if user:
            await db.users.update_one(
                {"user_id": user["user_id"]},
                {"$set": {"last_seen_at": datetime.now(timezone.utc).isoformat()}},
            )
        return user
    # Opaque session — Google sign-in / super admin
    return await _user_from_legacy_token(token)


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
    if user.get("status") == "suspended":
        raise HTTPException(status_code=403, detail="Account suspended")
    return user


async def require_admin_uploads(authorization: str | None = Header(default=None)):
    user = await require_admin(authorization)
    if user.get("uploads_disabled"):
        raise HTTPException(status_code=403, detail="Your upload feature is disabled. Upgrade to continue or contact admin.")
    return user


async def require_superadmin(authorization: str | None = Header(default=None)):
    user = await get_current_user(authorization)
    if user.get("role") != "superadmin":
        raise HTTPException(status_code=403, detail="Super admin access required")
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
    raw = _extract_bearer(authorization) or token
    user = await _user_from_token(raw)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
