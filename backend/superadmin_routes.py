"""Minimal platform-owner dashboard API for PIK Connect SaaS."""
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from config import db, SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD
from auth_utils import hash_password, verify_password, create_session, require_superadmin, new_user_id
import plans

superadmin_router = APIRouter(prefix="/api/superadmin")

# Public-facing plan catalogue derived from the single source of truth in plans.py.
PLANS = [
    {
        "key": p["key"], "name": p["name"], "price": p["price"],
        "storage_limit_gb": None if p["storage_bytes"] is None else round(p["storage_bytes"] / (1024 ** 3), 2),
        "gallery_limit": p["galleries"], "gdrive_limit": p["gdrive_galleries"],
        "album_limit": p["albums"], "client_limit": p["clients"], "image_limit": p["images"],
    }
    for p in plans.PLAN_LIMITS.values()
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _plan_for(user: dict) -> dict:
    limits = plans.plan_limits(user)
    return {
        "key": limits["key"], "name": limits["name"], "price": limits["price"],
        "storage_limit_gb": None if limits["storage_bytes"] is None else round(limits["storage_bytes"] / (1024 ** 3), 2),
        "gallery_limit": limits["galleries"], "gdrive_limit": limits["gdrive_galleries"],
        "album_limit": limits["albums"], "client_limit": limits["clients"], "image_limit": limits["images"],
    }


def _photo_bytes(photo: dict) -> int:
    if photo.get("bytes") or photo.get("size_bytes"):
        return int(photo.get("bytes") or photo.get("size_bytes"))
    width, height = photo.get("width"), photo.get("height")
    if width and height:
        return int(width * height * 0.35)
    return 0


async def _usage_for(studio_id: str) -> dict:
    events = await db.events.find({"created_by": studio_id}, {"_id": 0, "event_id": 1, "name": 1, "created_at": 1, "status": 1, "source": 1, "photo_count": 1}).to_list(5000)
    event_ids = [e["event_id"] for e in events]
    photos = await db.photos.find({"event_id": {"$in": event_ids}}, {"_id": 0, "bytes": 1, "size_bytes": 1, "width": 1, "height": 1, "source": 1}).to_list(100000) if event_ids else []
    return {
        "galleries": len(events),
        "images": len(photos),
        "storage_bytes": sum(_photo_bytes(p) for p in photos if p.get("source") != "gdrive"),
        "event_ids": event_ids,
        "events": events,
    }


async def _photographer_row(user: dict) -> dict:
    usage = await _usage_for(user["user_id"])
    plan = _plan_for(user)
    state = plans.plan_state(user)
    counters = user.get("usage") or {}
    clients = await db.clients.count_documents({"studio_id": user["user_id"]})
    albums = await db.albums.count_documents({"created_by": user["user_id"]})
    last_event = max((e.get("created_at") or "" for e in usage["events"]), default=None)
    return {
        "photographer_id": user["user_id"],
        "name": user.get("name") or user.get("email", "Photographer").split("@")[0],
        "email": user.get("email"),
        "phone": user.get("phone"),
        "membership": plan["name"],
        "membership_key": plan["key"],
        "plan_status": state["status"],
        "locked": state["locked"],
        "days_left": state["days_left"],
        "plan_expires_at": state["expires_at"],
        "status": user.get("status", "active"),
        "uploads_disabled": bool(user.get("uploads_disabled", False)),
        "galleries": usage["galleries"],
        "galleries_created": int(counters.get("galleries_created", 0)),
        "gdrive_created": int(counters.get("gdrive_created", 0)),
        "albums": albums,
        "albums_created": int(counters.get("albums_created", 0)),
        "images": usage["images"],
        "storage_bytes": usage["storage_bytes"],
        "storage_limit_gb": plan["storage_limit_gb"],
        "gallery_limit": plan["gallery_limit"],
        "clients": clients,
        "client_limit": plan["client_limit"],
        "revenue": plan["price"] if plan["key"] != "trial" and not state["locked"] else 0,
        "last_active": user.get("last_active_at") or last_event,
        "created_at": user.get("created_at"),
    }


class SuperadminLogin(BaseModel):
    email: EmailStr
    password: str


class PhotographerControls(BaseModel):
    uploads_disabled: Optional[bool] = None
    status: Optional[str] = None


class SuperadminSettingsUpdate(BaseModel):
    platform_name: Optional[str] = None


@superadmin_router.post("/login")
async def superadmin_login(body: SuperadminLogin):
    email = body.email.lower()
    user = await db.users.find_one({"email": email, "role": "superadmin"})
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid super admin credentials")
    token = await create_session(user["user_id"])
    return {"session_token": token, "user": {"user_id": user["user_id"], "role": "superadmin", "name": user.get("name"), "email": user.get("email")}}


@superadmin_router.get("/overview")
async def overview(admin: dict = Depends(require_superadmin)):
    photographers = await db.users.find({"role": "admin"}, {"_id": 0}).to_list(1000)
    rows = [await _photographer_row(user) for user in photographers]
    gallery_count = await db.events.count_documents({})
    album_count = await db.albums.count_documents({})
    image_count = await db.photos.count_documents({})
    today = datetime.now(timezone.utc).date().isoformat()
    uploads_today = await db.photos.count_documents({"uploaded_at": {"$regex": f"^{today}"}})
    storage_bytes = sum(row["storage_bytes"] for row in rows)
    mrr = sum(row["revenue"] for row in rows)
    plan_distribution = {}
    for row in rows:
        plan_distribution[row["membership_key"]] = plan_distribution.get(row["membership_key"], 0) + 1
    return {
        "stats": {
            "total_photographers": len(rows),
            "active_photographers": sum(1 for row in rows if row["status"] == "active"),
            "total_galleries": gallery_count,
            "total_albums": album_count,
            "total_images": image_count,
            "storage_bytes": storage_bytes,
            "uploads_today": uploads_today,
            "mrr": mrr,
            "paying_studios": sum(1 for row in rows if row["membership_key"] != "trial" and not row["locked"]),
        },
        "plan_distribution": plan_distribution,
        "attention": {
            "storage_warnings": sum(1 for row in rows if row["storage_limit_gb"] and row["storage_bytes"] / (1024**3) >= row["storage_limit_gb"] * 0.85),
            "expiring_memberships": sum(1 for row in rows if row["days_left"] is not None and not row["locked"] and row["days_left"] <= 3),
            "expired_trials": sum(1 for row in rows if row["membership_key"] == "trial" and row["locked"]),
            "uploads_disabled": sum(1 for row in rows if row["uploads_disabled"]),
        },
        "recent_activity": await _recent_activity(rows),
    }


async def _recent_activity(rows: list[dict]) -> list[dict]:
    logs = await db.superadmin_activity.find({}, {"_id": 0}).sort("created_at", -1).to_list(20)
    out = [{"photographer": log.get("photographer") or "Admin", "action": log.get("action"), "description": log.get("description"), "date": log.get("created_at"), "status": "Success"} for log in logs]
    if len(out) < 20:
        for row in rows:
            if row.get("last_active"):
                out.append({"photographer": row["name"], "action": "Account activity", "description": f"{row['galleries']} galleries · {row['images']} images", "date": row["last_active"], "status": "Success"})
    return out[:20]


@superadmin_router.get("/photographers")
async def photographers(q: Optional[str] = None, status: Optional[str] = None, admin: dict = Depends(require_superadmin)):
    users = await db.users.find({"role": "admin"}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    rows = [await _photographer_row(user) for user in users]
    query = (q or "").strip().lower()
    if query:
        rows = [row for row in rows if query in row["name"].lower() or query in (row["email"] or "").lower()]
    if status == "upload_disabled":
        rows = [row for row in rows if row["uploads_disabled"]]
    elif status:
        rows = [row for row in rows if row["status"] == status]
    return rows


@superadmin_router.get("/photographers/{photographer_id}")
async def photographer_detail(photographer_id: str, admin: dict = Depends(require_superadmin)):
    user = await db.users.find_one({"user_id": photographer_id, "role": "admin"}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Photographer not found")
    row = await _photographer_row(user)
    row["membership_detail"] = _plan_for(user)
    return row


@superadmin_router.patch("/photographers/{photographer_id}")
async def update_photographer(photographer_id: str, body: PhotographerControls, admin: dict = Depends(require_superadmin)):
    user = await db.users.find_one({"user_id": photographer_id, "role": "admin"}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Photographer not found")
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "status" in updates and updates["status"] not in ("active", "suspended", "trial", "expired"):
        raise HTTPException(status_code=400, detail="Invalid photographer status")
    if updates:
        await db.users.update_one({"user_id": photographer_id}, {"$set": updates})
        action = "Enabled uploads" if updates.get("uploads_disabled") is False else "Disabled uploads" if updates.get("uploads_disabled") is True else f"Changed status to {updates.get('status')}"
        await db.superadmin_activity.insert_one({"activity_id": f"act_{uuid.uuid4().hex[:12]}", "photographer": user.get("name") or user.get("email"), "action": action, "description": action, "created_at": now_iso(), "admin_id": admin["user_id"]})
    fresh = await db.users.find_one({"user_id": photographer_id, "role": "admin"}, {"_id": 0, "password_hash": 0})
    return await _photographer_row(fresh)


@superadmin_router.get("/memberships")
async def memberships(admin: dict = Depends(require_superadmin)):
    users = await db.users.find({"role": "admin"}, {"_id": 0}).to_list(1000)
    counts = {}
    for user in users:
        key = _plan_for(user)["key"]
        counts[key] = counts.get(key, 0) + 1
    return [{**plan, "photographers": counts.get(plan["key"], 0)} for plan in PLANS]


@superadmin_router.get("/galleries")
async def galleries(q: Optional[str] = None, admin: dict = Depends(require_superadmin)):
    events = await db.events.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    rows = []
    query = (q or "").strip().lower()
    for event in events:
        photographer = await db.users.find_one({"user_id": event.get("created_by")}, {"_id": 0, "name": 1, "email": 1})
        count = await db.photos.count_documents({"event_id": event["event_id"]})
        row = {"event_id": event["event_id"], "name": event.get("name"), "photographer": (photographer or {}).get("name") or (photographer or {}).get("email"), "images": count, "storage_bytes": 0, "created_at": event.get("created_at"), "status": event.get("status", "active")}
        if not query or query in (row["name"] or "").lower() or query in (row["photographer"] or "").lower():
            rows.append(row)
    return rows


@superadmin_router.get("/albums")
async def albums(q: Optional[str] = None, admin: dict = Depends(require_superadmin)):
    album_docs = await db.albums.find({}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    rows = []
    query = (q or "").strip().lower()
    for album in album_docs:
        photographer = await db.users.find_one({"user_id": album.get("created_by")}, {"_id": 0, "name": 1, "email": 1})
        pages = int(album.get("page_count") or 0)
        row = {
            "album_id": album.get("album_id"),
            "title": album.get("title") or "Untitled album",
            "photographer": (photographer or {}).get("name") or (photographer or {}).get("email") or "Unknown photographer",
            "client_name": album.get("client_name"),
            "event_name": album.get("event_name"),
            "event_date": album.get("event_date"),
            "status": album.get("status", "draft"),
            "archived": bool(album.get("archived", False)),
            "pages": pages,
            "spreads": int(album.get("total_spreads") or 0),
            "created_at": album.get("created_at"),
            "updated_at": album.get("updated_at"),
        }
        haystack = " ".join(str(row.get(key) or "") for key in ("title", "photographer", "client_name", "event_name")).lower()
        if not query or query in haystack:
            rows.append(row)
    return rows


@superadmin_router.get("/storage")
async def storage_overview(admin: dict = Depends(require_superadmin)):
    rows = await photographers(admin=admin)
    total = sum(row["storage_bytes"] for row in rows)
    return {"total_bytes": total, "platform_limit_gb": 20480, "photographers": sorted(rows, key=lambda row: row["storage_bytes"], reverse=True)}


@superadmin_router.get("/activity")
async def activity(admin: dict = Depends(require_superadmin)):
    users = await db.users.find({"role": "admin"}, {"_id": 0}).to_list(1000)
    rows = [await _photographer_row(user) for user in users]
    return await _recent_activity(rows)


@superadmin_router.get("/settings")
async def settings(admin: dict = Depends(require_superadmin)):
    doc = await db.platform_settings.find_one({"key": "main"}, {"_id": 0})
    return {"platform_name": (doc or {}).get("platform_name") or "PIK Connect"}


@superadmin_router.patch("/settings")
async def update_settings(body: SuperadminSettingsUpdate, admin: dict = Depends(require_superadmin)):
    updates = {k: v.strip() for k, v in body.model_dump(exclude_unset=True).items() if isinstance(v, str) and v.strip()}
    if updates:
        await db.platform_settings.update_one({"key": "main"}, {"$set": {**updates, "key": "main", "updated_at": now_iso()}}, upsert=True)
    return await settings(admin=admin)



# ---------------------------------------------------------------------------
# Notifications for the superadmin (platform-operator inbox)
# ---------------------------------------------------------------------------
@superadmin_router.get("/notifications")
async def list_superadmin_notifications(admin: dict = Depends(require_superadmin)):
    items = await db.notifications.find(
        {"superadmin_id": admin["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return {
        "items": items,
        "unread_count": sum(1 for item in items if not item.get("read")),
    }


@superadmin_router.patch("/notifications/{notification_id}/read")
async def mark_superadmin_notification_read(
    notification_id: str, admin: dict = Depends(require_superadmin)
):
    result = await db.notifications.update_one(
        {"notification_id": notification_id, "superadmin_id": admin["user_id"]},
        {"$set": {"read": True, "read_at": now_iso()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "read", "notification_id": notification_id}
