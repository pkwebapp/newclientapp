"""Supabase Auth: JWT verification (JWKS) + local user upsert.

Any request carrying a Supabase-issued access token in `Authorization: Bearer <jwt>`
is verified here. On the first successful verification for a given Supabase user
we create a matching row in our `users` collection so the rest of the codebase
continues to work with our existing `user_id`, `role`, `studio_profile`, etc.
"""
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import jwt
from jwt import PyJWKClient, InvalidTokenError

from config import db
import plans

logger = logging.getLogger(__name__)

SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
_ISSUER = f"{SUPABASE_URL}/auth/v1" if SUPABASE_URL else None
_JWKS_URL = f"{_ISSUER}/.well-known/jwks.json" if _ISSUER else None
_ALLOWED_ALGS = {"RS256", "ES256"}

_jwks: Optional[PyJWKClient] = None
if _JWKS_URL:
    try:
        _jwks = PyJWKClient(_JWKS_URL, cache_jwk_set=True, lifespan=600)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"JWKS client init failed: {e}")


def looks_like_jwt(token: str) -> bool:
    """Quick shape check — real JWTs are three dot-separated base64 segments."""
    if not token:
        return False
    parts = token.split(".")
    return len(parts) == 3 and all(parts)


def verify_supabase_jwt(token: str) -> Optional[dict[str, Any]]:
    """Verify a Supabase access token and return its claims, or None if invalid.

    Returns None (never raises) so callers can fall back to the legacy session
    lookup without a 500.
    """
    if not (_jwks and _ISSUER and looks_like_jwt(token)):
        return None
    try:
        header = jwt.get_unverified_header(token)
        alg = header.get("alg")
        if alg not in _ALLOWED_ALGS:
            return None
        key = _jwks.get_signing_key_from_jwt(token).key
        claims = jwt.decode(
            token,
            key,
            algorithms=[alg],
            audience="authenticated",
            issuer=_ISSUER,
            options={"require": ["exp", "iat", "sub"]},
        )
        if not isinstance(claims.get("sub"), str) or not claims["sub"]:
            return None
        return claims
    except InvalidTokenError:
        return None
    except Exception as e:  # noqa: BLE001
        logger.debug(f"JWT verify unexpected: {type(e).__name__}: {e}")
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def upsert_user_from_claims(claims: dict[str, Any]) -> dict[str, Any]:
    """Return the local users row for a Supabase user, creating one on first sight.

    Role source (in priority):
      1. `app_metadata.role`  — server-controlled (we set this via admin SDK later)
      2. `user_metadata.role` — the frontend sets this during signUp so we
         can distinguish admin vs client at first login.
      3. Default: client.
    """
    supabase_id: str = claims["sub"]
    email = (claims.get("email") or "").lower() or None
    phone = claims.get("phone") or None
    app_meta = claims.get("app_metadata") or {}
    user_meta = claims.get("user_metadata") or {}
    role = (
        app_meta.get("role")
        or user_meta.get("role")
        or "client"
    )
    if role not in ("admin", "client"):
        role = "client"

    # 1) Already linked?
    user = await db.users.find_one({"supabase_id": supabase_id}, {"_id": 0})
    if user:
        # Refresh email/phone in case the user changed them in Supabase.
        patch = {"last_seen_at": _now_iso()}
        if email and user.get("email") != email:
            patch["email"] = email
        if phone and user.get("phone") != phone:
            patch["phone"] = phone
        if patch:
            await db.users.update_one({"user_id": user["user_id"]}, {"$set": patch})
            user.update(patch)
        return user

    # 2) Fresh Supabase user — create local row.
    # Full DB was wiped for Q3a, so no legacy email match to worry about.
    name = (
        user_meta.get("name")
        or user_meta.get("full_name")
        or (email.split("@")[0] if email else None)
        or "PIK user"
    )
    picture = user_meta.get("picture") or user_meta.get("avatar_url")
    user = {
        "user_id": f"user_{uuid.uuid4().hex[:12]}",
        "supabase_id": supabase_id,
        "role": role,
        "name": name,
        "email": email,
        "phone": phone,
        "picture": picture,
        "auth_provider": user_meta.get("provider") or app_meta.get("provider") or "supabase",
        "created_at": _now_iso(),
        "last_seen_at": _now_iso(),
    }
    if role == "admin":
        user.update(plans.new_studio_plan_fields())
        # New admins go through the studio-profile onboarding gate.
        user["profile_complete"] = False
    else:
        user["verified_email"] = bool(email)
        user["verified_phone"] = bool(phone)
    await db.users.insert_one(user)

    # Best-effort: notify superadmins about new studio (parity with old flow).
    if role == "admin":
        try:
            from notifications_service import notify_superadmins
            await notify_superadmins(
                type_key="sa_new_studio",
                title="New photographer joined",
                body=f'{name} ({email}) just created a studio account.',
                action_url=f"/superadmin/studio/{user['user_id']}",
                meta={"studio_id": user["user_id"], "name": name, "email": email},
                dedupe_key=f"sa_new_studio:{user['user_id']}",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"sa_new_studio notify failed: {e}")

    return user


async def user_from_supabase_bearer(token: str) -> Optional[dict[str, Any]]:
    """Verify + upsert in one call. Returns the local users row or None."""
    claims = verify_supabase_jwt(token)
    if not claims:
        return None
    return await upsert_user_from_claims(claims)
