"""Google sign-in via Emergent Auth.

Flow:
  1. Frontend sends the user to https://auth.emergentagent.com/?redirect=<app url>
  2. Google returns to the app with ``#session_id=<one-time id>``
  3. Frontend POSTs ``{session_id, role}`` to ``/api/auth/session`` (below)
  4. We exchange the id ONCE with Emergent, upsert the user by email and mint an
     opaque session token (``user_sessions``) that works as a normal bearer.
"""
import logging
import uuid
from datetime import datetime, timezone

import httpx

from config import db
import plans

logger = logging.getLogger(__name__)

EMERGENT_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"


class GoogleAuthError(Exception):
    pass


async def fetch_google_identity(session_id: str) -> dict:
    """Exchange the one-time ``session_id`` for the Google profile. Raises on failure."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            resp = await http.get(EMERGENT_SESSION_URL, headers={"X-Session-ID": session_id})
    except httpx.HTTPError as exc:
        logger.warning("google-auth: emergent session-data unreachable: %s", exc)
        raise GoogleAuthError("Google sign-in is temporarily unavailable. Please try again.") from exc
    if resp.status_code != 200:
        logger.info("google-auth: session-data rejected (%s)", resp.status_code)
        raise GoogleAuthError("Google sign-in expired. Please try again.")
    data = resp.json()
    email = (data.get("email") or "").strip().lower()
    if not email:
        raise GoogleAuthError("Google did not return an email address.")
    return {
        "email": email,
        "name": (data.get("name") or "").strip() or email.split("@")[0],
        "picture": data.get("picture"),
    }


async def upsert_google_user(identity: dict, role: str) -> dict:
    """Return the local users row for this Google email, creating one on first sight.

    Existing accounts keep their role — ``role`` only applies to brand-new users.
    """
    now = datetime.now(timezone.utc).isoformat()
    user = await db.users.find_one({"email": identity["email"]}, {"_id": 0, "password_hash": 0})
    if user:
        patch = {"last_seen_at": now, "verified_email": True}
        if identity.get("picture") and not user.get("picture"):
            patch["picture"] = identity["picture"]
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": patch})
        user.update(patch)
        return user

    role = role if role in ("admin", "client") else "client"
    user = {
        "user_id": f"user_{uuid.uuid4().hex[:12]}",
        "role": role,
        "name": identity["name"],
        "email": identity["email"],
        "picture": identity.get("picture"),
        "auth_provider": "google",
        "verified_email": True,
        "created_at": now,
        "last_seen_at": now,
    }
    if role == "admin":
        user.update(plans.new_studio_plan_fields())
        user["profile_complete"] = False
    else:
        user["client_profile"] = {"full_name": identity["name"]}
    await db.users.insert_one(user)
    user.pop("_id", None)

    if role == "admin":
        try:
            from notifications_service import notify_superadmins
            await notify_superadmins(
                type_key="sa_new_studio",
                title="New photographer joined",
                body=f'{user["name"]} ({user["email"]}) just created a studio account.',
                action_url=f"/superadmin/studio/{user['user_id']}",
                meta={"studio_id": user["user_id"], "name": user["name"], "email": user["email"]},
                dedupe_key=f"sa_new_studio:{user['user_id']}",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("sa_new_studio notify failed: %s", e)
    return user
