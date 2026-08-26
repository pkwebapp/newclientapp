"""Subscription plans, quota limits and enforcement for PIK Connect studios.

A studio is on one of three plans:
  - trial     : free, expires 7 days after start; small quotas
  - standard  : Rs 499 / month
  - pro       : Rs 999 / month

Gallery / gdrive-gallery / album counts are TOTAL-EVER counters (deleting does
not free a slot). Storage and client counts are live measures.
"""
from datetime import datetime, timezone, timedelta
from math import ceil

from fastapi import HTTPException

from config import db

MB = 1024 ** 2
GB = 1024 ** 3

PLAN_LIMITS = {
    "trial": {
        "key": "trial", "name": "Trial", "price": 0, "validity_days": 7,
        "galleries": 2, "gdrive_galleries": 1, "albums": 1,
        "images": 1000, "clients": 100, "storage_bytes": 100 * MB,
    },
    "standard": {
        "key": "standard", "name": "Standard", "price": 499, "validity_days": 30,
        "galleries": 20, "gdrive_galleries": 30, "albums": 10,
        "images": None, "clients": 500, "storage_bytes": 5 * GB,
    },
    "pro": {
        "key": "pro", "name": "Pro", "price": 999, "validity_days": 30,
        "galleries": 50, "gdrive_galleries": 100, "albums": 50,
        "images": None, "clients": None, "storage_bytes": 15 * GB,
    },
}

# Grace window: how long expired-trial data is retained before purge.
TRIAL_GRACE_DAYS = 30


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(dtstr):
    if not dtstr:
        return None
    try:
        dt = datetime.fromisoformat(dtstr)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def plan_limits(user: dict) -> dict:
    return PLAN_LIMITS.get((user.get("plan") or "trial").lower(), PLAN_LIMITS["trial"])


def new_studio_plan_fields() -> dict:
    """Plan fields stamped onto a freshly created studio account."""
    now = _now()
    return {
        "plan": "trial",
        "plan_status": "active",
        "plan_started_at": now.isoformat(),
        "plan_expires_at": (now + timedelta(days=PLAN_LIMITS["trial"]["validity_days"])).isoformat(),
        "usage": {"galleries_created": 0, "gdrive_created": 0, "albums_created": 0, "images_uploaded": 0},
    }


async def ensure_plan(user: dict) -> dict:
    """Backfill plan fields for studios created before billing existed. Gives a
    fresh 7-day trial from the moment they are first seen."""
    if user.get("plan"):
        if "usage" not in user:
            usage = {"galleries_created": 0, "gdrive_created": 0, "albums_created": 0, "images_uploaded": 0}
            await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"usage": usage}})
            user["usage"] = usage
        return user
    fields = new_studio_plan_fields()
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": fields})
    user.update(fields)
    return user


def plan_state(user: dict) -> dict:
    limits = plan_limits(user)
    exp = _parse(user.get("plan_expires_at"))
    now = _now()
    days_left = None
    if exp:
        days_left = max(0, ceil((exp - now).total_seconds() / 86400))
    locked = bool(exp and now > exp)
    return {
        "plan": limits["key"],
        "plan_name": limits["name"],
        "price": limits["price"],
        "started_at": user.get("plan_started_at"),
        "expires_at": user.get("plan_expires_at"),
        "days_left": days_left,
        "locked": locked,
        "status": "expired" if locked else "active",
        "limits": {
            "galleries": limits["galleries"],
            "gdrive_galleries": limits["gdrive_galleries"],
            "albums": limits["albums"],
            "images": limits["images"],
            "clients": limits["clients"],
            "storage_bytes": limits["storage_bytes"],
        },
    }


async def storage_bytes_for(studio_id: str) -> int:
    events = await db.events.find({"created_by": studio_id}, {"_id": 0, "event_id": 1}).to_list(10000)
    ids = [e["event_id"] for e in events]
    if not ids:
        return 0
    total = 0
    cursor = db.photos.find(
        {"event_id": {"$in": ids}, "source": {"$ne": "gdrive"}},
        {"_id": 0, "bytes": 1, "width": 1, "height": 1},
    )
    async for p in cursor:
        if p.get("bytes"):
            total += int(p["bytes"])
        elif p.get("width") and p.get("height"):
            total += int(p["width"] * p["height"] * 0.35)
    return total


async def usage_for(user: dict) -> dict:
    await ensure_plan(user)
    u = user.get("usage") or {}
    clients = await db.clients.count_documents({"studio_id": user["user_id"]})
    storage = await storage_bytes_for(user["user_id"])
    return {
        "galleries_created": int(u.get("galleries_created", 0)),
        "gdrive_created": int(u.get("gdrive_created", 0)),
        "albums_created": int(u.get("albums_created", 0)),
        "images_uploaded": int(u.get("images_uploaded", 0)),
        "clients": clients,
        "storage_bytes": storage,
    }


async def billing_status(user: dict) -> dict:
    state = plan_state(user)
    usage = await usage_for(user)
    return {**state, "usage": usage}


async def increment_usage(studio_id: str, field: str, n: int = 1) -> None:
    await db.users.update_one({"user_id": studio_id}, {"$inc": {f"usage.{field}": n}})


async def owner_locked(studio_id: str) -> bool:
    owner = await db.users.find_one({"user_id": studio_id}, {"_id": 0, "plan": 1, "plan_expires_at": 1})
    if not owner:
        return False
    return plan_state(owner)["locked"]


def _assert_active(user: dict):
    if plan_state(user)["locked"]:
        raise HTTPException(status_code=402, detail="Your trial has ended. Subscribe to Standard or Pro to keep creating and sharing galleries.")


def _assert_count(user: dict, field: str, limit_key: str, label: str):
    limits = plan_limits(user)
    lim = limits[limit_key]
    if lim is None:
        return
    used = int((user.get("usage") or {}).get(field, 0))
    if used >= lim:
        raise HTTPException(status_code=402, detail=f"You've reached your {limits['name']} plan limit of {lim} {label}. Upgrade to add more.")


async def check_can_create_gallery(user: dict):
    await ensure_plan(user)
    _assert_active(user)
    _assert_count(user, "galleries_created", "galleries", "galleries")


async def check_can_create_gdrive(user: dict):
    await ensure_plan(user)
    _assert_active(user)
    _assert_count(user, "gdrive_created", "gdrive_galleries", "Google Drive galleries")


async def check_can_create_album(user: dict):
    await ensure_plan(user)
    _assert_active(user)
    _assert_count(user, "albums_created", "albums", "albums")


async def check_can_add_client(user: dict, adding: int = 1):
    await ensure_plan(user)
    _assert_active(user)
    limits = plan_limits(user)
    lim = limits["clients"]
    if lim is None:
        return
    current = await db.clients.count_documents({"studio_id": user["user_id"]})
    if current + adding > lim:
        raise HTTPException(status_code=402, detail=f"You've reached your {limits['name']} plan limit of {lim} clients. Upgrade to add more.")


async def check_can_upload_images(user: dict, count: int, added_bytes: int):
    """Enforce trial image cap + storage cap for uploaded (non-Drive) photos."""
    await ensure_plan(user)
    _assert_active(user)
    limits = plan_limits(user)
    img_lim = limits["images"]
    if img_lim is not None:
        used = int((user.get("usage") or {}).get("images_uploaded", 0))
        if used + count > img_lim:
            remaining = max(0, img_lim - used)
            raise HTTPException(status_code=402, detail=f"You've reached your image limit ({img_lim}). {remaining} left — upgrade for more.")
    store_lim = limits["storage_bytes"]
    if store_lim is not None:
        current = await storage_bytes_for(user["user_id"])
        if current + added_bytes > store_lim:
            raise HTTPException(status_code=402, detail="You've reached your plan's storage limit. Upgrade or free up space.")


def apply_subscription_fields(plan_key: str) -> dict:
    """Fields to set when a studio subscribes/upgrades to a paid plan."""
    plan = PLAN_LIMITS.get(plan_key, PLAN_LIMITS["standard"])
    now = _now()
    return {
        "plan": plan["key"],
        "plan_status": "active",
        "plan_started_at": now.isoformat(),
        "plan_expires_at": (now + timedelta(days=plan["validity_days"])).isoformat(),
    }
