"""Lumiere Gallery — client photo gallery with face-recognition search."""
import io
import os
import csv
import uuid
import base64
import random
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import qrcode
import httpx
from fastapi import FastAPI, APIRouter, UploadFile, File, Form, Depends, HTTPException, Response
from starlette.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, EmailStr, Field
from PIL import Image, ImageOps

from config import (
    db, client, APP_NAME, DEFAULT_SIMILARITY_THRESHOLD, OTP_DEV_MODE, SMS_PROVIDER,
    ADMIN_SEED_EMAIL, ADMIN_SEED_PASSWORD, PUBLIC_BASE_URL,
)
from storage_service import get_storage
from face_engine import get_face_engine, NotIndexedError
import gdrive_service
from gdrive_service import DriveError
from email_service import send_otp_email
from auth_utils import (
    hash_password, verify_password, new_user_id, create_session,
    get_current_user, require_admin, require_client, user_from_token_or_header,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()
api_router = APIRouter(prefix="/api")

CATEGORIES = ["wedding", "corporate", "school", "studio", "nightlife", "event"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def gen_otp() -> str:
    return f"{random.randint(0, 999999):06d}"


# Shown to clients/visitors when a gallery has been taken offline (archived).
ARCHIVED_MESSAGE = (
    "This gallery has been archived. Please contact your photographer for access."
)


async def get_event_or_404(event_id: str) -> dict:
    event = await db.events.find_one({"event_id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


def ensure_event_available(event: dict) -> None:
    """Block client/public access to archived (offline) galleries."""
    if event.get("status") == "archived":
        raise HTTPException(status_code=403, detail=ARCHIVED_MESSAGE)


async def admin_event_or_404(event_id: str, admin: dict) -> dict:
    event = await get_event_or_404(event_id)
    if event["created_by"] != admin["user_id"]:
        raise HTTPException(status_code=403, detail="Not your event")
    return event


async def client_grant_or_403(event_id: str, client_user: dict) -> dict:
    """Return the active access grant for this client on the event, else 403."""
    ensure_event_available(await get_event_or_404(event_id))
    ors = []
    if client_user.get("email"):
        ors.append({"client_email": client_user["email"].lower()})
    if client_user.get("phone"):
        ors.append({"client_phone": client_user["phone"]})
    if not ors:
        raise HTTPException(status_code=403, detail="No access to this gallery")
    grant = await db.access_grants.find_one(
        {"event_id": event_id, "status": "active", "$or": ors}, {"_id": 0}
    )
    if not grant:
        raise HTTPException(status_code=403, detail="No access to this gallery")
    return grant


def make_thumbnail(image_bytes: bytes, max_side: int = 480) -> tuple[bytes, int, int]:
    img = Image.open(io.BytesIO(image_bytes))
    img = ImageOps.exif_transpose(img).convert("RGB")
    w, h = img.size
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=72)
    return buf.getvalue(), w, h


def public_event(event: dict) -> dict:
    cover_url = _public_url(event.get("cover_path"))
    if event.get("source") == "gdrive" and event.get("cover_drive_id"):
        cover_url = _gdrive_proxy_url(event["cover_drive_id"], 600)
    return {
        "event_id": event["event_id"],
        "name": event["name"],
        "date": event.get("date"),
        "category": event.get("category"),
        "photographer": event.get("photographer"),
        "similarity_threshold": event.get("similarity_threshold", DEFAULT_SIMILARITY_THRESHOLD),
        "indexing_status": event.get("indexing_status", "empty"),
        "photo_count": event.get("photo_count", 0),
        "cover_path": event.get("cover_path"),
        "cover_url": cover_url,
        "status": event.get("status", "active"),
        "share_enabled": event.get("share_enabled", True),
        "source": event.get("source", "upload"),
        "drive_folder_id": event.get("drive_folder_id"),
        "drive_folder_link": event.get("drive_folder_link"),
        "last_synced_at": event.get("last_synced_at"),
        "created_at": event.get("created_at"),
    }


def share_url_for(event_id: str) -> str:
    base = PUBLIC_BASE_URL or ""
    return f"{base}/g/{event_id}"


def normalize_phone(phone: str) -> str:
    return (phone or "").strip()


# ---------------------------------------------------------------------------
# Auth — admin (email+password & Google) + client (OTP)
# ---------------------------------------------------------------------------
class AdminRegister(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)


class AdminLogin(BaseModel):
    email: EmailStr
    password: str


class SessionExchange(BaseModel):
    session_id: str


class OtpRequest(BaseModel):
    channel: str  # "email" | "phone"
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class OtpVerify(BaseModel):
    channel: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    code: str
    name: Optional[str] = None


@api_router.post("/auth/admin/register")
async def admin_register(body: AdminRegister):
    email = body.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = {
        "user_id": new_user_id(),
        "role": "admin",
        "name": body.name,
        "email": email,
        "phone": None,
        "password_hash": hash_password(body.password),
        "auth_provider": "password",
        "created_at": now_iso(),
    }
    await db.users.insert_one(user)
    token = await create_session(user["user_id"])
    return {"session_token": token, "user": _public_user(user)}


@api_router.post("/auth/admin/login")
async def admin_login(body: AdminLogin):
    email = body.email.lower()
    user = await db.users.find_one({"email": email, "role": "admin"})
    if not user or not user.get("password_hash") or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = await create_session(user["user_id"])
    return {"session_token": token, "user": _public_user(user)}


@api_router.post("/auth/session")
async def google_session(body: SessionExchange):
    """Exchange an Emergent Google OAuth session_id for a session token.
    Google sign-in creates/logs in a studio admin."""
    async with httpx.AsyncClient(timeout=30) as hc:
        resp = await hc.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": body.session_id},
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    data = resp.json()
    email = (data.get("email") or "").lower()
    if not email:
        raise HTTPException(status_code=401, detail="No email from provider")
    user = await db.users.find_one({"email": email})
    if not user:
        user = {
            "user_id": new_user_id(),
            "role": "admin",
            "name": data.get("name") or email.split("@")[0],
            "email": email,
            "phone": None,
            "password_hash": None,
            "picture": data.get("picture"),
            "auth_provider": "google",
            "created_at": now_iso(),
        }
        await db.users.insert_one(user)
    token = await create_session(user["user_id"])
    return {"session_token": token, "user": _public_user(user)}


@api_router.post("/auth/client/request-otp")
async def request_otp(body: OtpRequest):
    if body.channel == "email":
        if not body.email:
            raise HTTPException(status_code=400, detail="Email is required")
        identifier = body.email.lower()
    elif body.channel == "phone":
        if not body.phone:
            raise HTTPException(status_code=400, detail="Phone number is required")
        identifier = body.phone.strip()
    else:
        raise HTTPException(status_code=400, detail="Invalid channel")

    code = gen_otp()
    await db.otp_codes.update_one(
        {"identifier": identifier},
        {"$set": {
            "identifier": identifier,
            "channel": body.channel,
            "code": code,
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
            "attempts": 0,
            "created_at": now_iso(),
        }},
        upsert=True,
    )

    delivered = False
    if body.channel == "email":
        try:
            await send_otp_email(identifier, code)
            delivered = True
        except Exception as e:
            logger.error(f"OTP email send failed: {e}")
    else:
        # SMS provider not configured -> code returned in dev mode only.
        logger.info(f"[SMS:{SMS_PROVIDER}] OTP for {identifier}: {code}")

    resp = {"status": "sent", "channel": body.channel, "delivered": delivered}
    if OTP_DEV_MODE:
        resp["dev_code"] = code
    return resp


@api_router.post("/auth/client/verify-otp")
async def verify_otp(body: OtpVerify):
    if body.channel == "email":
        identifier = (body.email or "").lower()
    else:
        identifier = (body.phone or "").strip()
    if not identifier:
        raise HTTPException(status_code=400, detail="Missing identifier")

    record = await db.otp_codes.find_one({"identifier": identifier})
    if not record:
        raise HTTPException(status_code=400, detail="Request a code first")
    expires_at = record["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Code expired. Request a new one.")
    if record.get("attempts", 0) >= 5:
        raise HTTPException(status_code=429, detail="Too many attempts. Request a new code.")
    if body.code != record["code"]:
        await db.otp_codes.update_one({"identifier": identifier}, {"$inc": {"attempts": 1}})
        raise HTTPException(status_code=401, detail="Incorrect code")

    await db.otp_codes.delete_one({"identifier": identifier})

    query = {"email": identifier} if body.channel == "email" else {"phone": identifier}
    user = await db.users.find_one(query)
    if not user:
        user = {
            "user_id": new_user_id(),
            "role": "client",
            "name": body.name or (identifier.split("@")[0] if body.channel == "email" else "Guest"),
            "email": identifier if body.channel == "email" else None,
            "phone": identifier if body.channel == "phone" else None,
            "password_hash": None,
            "auth_provider": f"otp_{body.channel}",
            "created_at": now_iso(),
        }
        await db.users.insert_one(user)
    else:
        if user.get("role") != "client":
            raise HTTPException(status_code=403, detail="This contact belongs to a studio account")

    token = await create_session(user["user_id"])
    return {"session_token": token, "user": _public_user(user)}


@api_router.get("/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return {"user": user}


@api_router.post("/auth/logout")
async def logout(user: dict = Depends(get_current_user)):
    return {"status": "ok"}


def _public_user(user: dict) -> dict:
    return {
        "user_id": user["user_id"],
        "role": user["role"],
        "name": user.get("name"),
        "email": user.get("email"),
        "phone": user.get("phone"),
        "picture": user.get("picture"),
    }


# ---------------------------------------------------------------------------
# Admin — events, photos, indexing, access, face-data
# ---------------------------------------------------------------------------
class EventCreate(BaseModel):
    name: str
    date: Optional[str] = None
    category: str = "event"
    photographer: Optional[str] = None
    similarity_threshold: Optional[float] = None


class EventUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[str] = None
    category: Optional[str] = None
    photographer: Optional[str] = None
    similarity_threshold: Optional[float] = None
    share_enabled: Optional[bool] = None


class AccessGrantCreate(BaseModel):
    channel: str  # email | phone
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    full_gallery_access: bool = False


@api_router.post("/events")
async def create_event(body: EventCreate, admin: dict = Depends(require_admin)):
    if body.category not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Category must be one of {CATEGORIES}")
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    engine = get_face_engine()
    collection_id = engine.create_collection(event_id)
    threshold = body.similarity_threshold or DEFAULT_SIMILARITY_THRESHOLD
    event = {
        "event_id": event_id,
        "name": body.name,
        "date": body.date,
        "category": body.category,
        "photographer": body.photographer,
        "similarity_threshold": threshold,
        "collection_id": collection_id,
        "indexing_status": "empty",
        "photo_count": 0,
        "cover_path": None,
        "share_enabled": True,
        "created_by": admin["user_id"],
        "created_at": now_iso(),
    }
    await db.events.insert_one(event)
    return public_event(event)


class GDriveEventCreate(BaseModel):
    name: str
    date: Optional[str] = None
    category: str = "event"
    photographer: Optional[str] = None
    similarity_threshold: Optional[float] = None
    drive_link: str


async def _sync_gdrive_event(event: dict, images: Optional[list] = None) -> dict:
    """Re-scan the Drive folder: add new images, re-index changed ones, remove
    deleted ones. Only metadata + web previews are used — no originals copied."""
    event_id = event["event_id"]
    folder_id = event["drive_folder_id"]
    if images is None:
        images = await run_in_threadpool(gdrive_service.list_folder_images, folder_id)

    existing = {
        p["drive_file_id"]: p
        for p in await db.photos.find(
            {"event_id": event_id, "source": "gdrive"}, {"_id": 0}
        ).to_list(100000)
    }
    engine = get_face_engine()

    seen: set[str] = set()
    added = updated = 0
    new_docs: list[dict] = []
    for img in images:
        fid = img["drive_file_id"]
        seen.add(fid)
        ex = existing.get(fid)
        if not ex:
            new_docs.append({
                "photo_id": f"pho_{uuid.uuid4().hex[:12]}",
                "event_id": event_id,
                "source": "gdrive",
                "drive_file_id": fid,
                "filename": img.get("name"),
                "folder_path": img.get("folder_path") or "",
                "width": img.get("width"),
                "height": img.get("height"),
                "md5_checksum": img.get("md5_checksum"),
                "modified_time": img.get("modified_time"),
                "face_count": 0,
                "indexing_status": "pending",
                "uploaded_at": now_iso(),
            })
            added += 1
        else:
            changed = (
                ex.get("md5_checksum") != img.get("md5_checksum")
                or ex.get("modified_time") != img.get("modified_time")
            )
            set_fields = {
                "filename": img.get("name"),
                "folder_path": img.get("folder_path") or "",
                "width": img.get("width"),
                "height": img.get("height"),
            }
            if changed:
                # Drop stale faces (ours + Rekognition) and re-queue for indexing.
                old = await db.faces.find({"photo_id": ex["photo_id"]}, {"_id": 0, "face_id": 1}).to_list(1000)
                if old:
                    try:
                        await run_in_threadpool(engine.delete_faces, event["collection_id"], [f["face_id"] for f in old])
                    except Exception as e:  # noqa: BLE001
                        logger.error(f"gdrive sync delete_faces: {e}")
                    await db.faces.delete_many({"photo_id": ex["photo_id"]})
                set_fields.update({
                    "md5_checksum": img.get("md5_checksum"),
                    "modified_time": img.get("modified_time"),
                    "indexing_status": "pending",
                    "face_count": 0,
                })
                updated += 1
            await db.photos.update_one({"photo_id": ex["photo_id"]}, {"$set": set_fields})

    if new_docs:
        await db.photos.insert_many(new_docs)

    # Remove images that disappeared from the Drive folder.
    removed_photos = [p for fid, p in existing.items() if fid not in seen]
    removed = 0
    for p in removed_photos:
        old = await db.faces.find({"photo_id": p["photo_id"]}, {"_id": 0, "face_id": 1}).to_list(1000)
        if old:
            try:
                await run_in_threadpool(engine.delete_faces, event["collection_id"], [f["face_id"] for f in old])
            except Exception as e:  # noqa: BLE001
                logger.error(f"gdrive sync delete_faces(removed): {e}")
        await db.faces.delete_many({"photo_id": p["photo_id"]})
        await db.photos.delete_one({"photo_id": p["photo_id"]})
        removed += 1

    cover_drive_id = event.get("cover_drive_id")
    if (not cover_drive_id or cover_drive_id not in seen) and images:
        cover_drive_id = images[0]["drive_file_id"]

    total = await db.photos.count_documents({"event_id": event_id})
    await db.events.update_one(
        {"event_id": event_id},
        {"$set": {
            "photo_count": total,
            "cover_drive_id": cover_drive_id,
            "last_synced_at": now_iso(),
        }},
    )
    await _refresh_event_index_status(event_id)
    _wake_indexer()
    return {"total": total, "added": added, "updated": updated, "removed": removed}


@api_router.post("/events/gdrive")
async def create_gdrive_event(body: GDriveEventCreate, admin: dict = Depends(require_admin)):
    """Create a gallery from a public Google Drive folder link. Originals stay
    on Drive; we index web previews for face search."""
    if body.category not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Category must be one of {CATEGORIES}")
    try:
        folder_id = gdrive_service.extract_folder_id(body.drive_link)
    except DriveError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Validate the folder is reachable & has images up-front (clean error before we create anything).
    try:
        probe = await run_in_threadpool(gdrive_service.list_folder_images, folder_id)
    except DriveError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not probe:
        raise HTTPException(
            status_code=400,
            detail="No photos found in that folder. Make sure it's shared 'Anyone with the link → Viewer' and contains images.",
        )

    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    engine = get_face_engine()
    collection_id = engine.create_collection(event_id)
    event = {
        "event_id": event_id,
        "name": body.name,
        "date": body.date,
        "category": body.category,
        "photographer": body.photographer,
        "similarity_threshold": body.similarity_threshold or DEFAULT_SIMILARITY_THRESHOLD,
        "collection_id": collection_id,
        "indexing_status": "empty",
        "photo_count": 0,
        "cover_path": None,
        "cover_drive_id": None,
        "share_enabled": True,
        "source": "gdrive",
        "drive_folder_id": folder_id,
        "drive_folder_link": body.drive_link.strip(),
        "last_synced_at": None,
        "created_by": admin["user_id"],
        "created_at": now_iso(),
    }
    await db.events.insert_one(event)
    sync = await _sync_gdrive_event(event, images=probe)
    fresh = await get_event_or_404(event_id)
    return {**public_event(fresh), "sync": sync}


@api_router.post("/events/{event_id}/sync")
async def sync_gdrive_event(event_id: str, admin: dict = Depends(require_admin)):
    event = await admin_event_or_404(event_id, admin)
    if event.get("source") != "gdrive":
        raise HTTPException(status_code=400, detail="This gallery is not a Google Drive gallery")
    try:
        sync = await _sync_gdrive_event(event)
    except DriveError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fresh = await get_event_or_404(event_id)
    return {**public_event(fresh), "sync": sync}


@api_router.get("/events")
async def list_events(admin: dict = Depends(require_admin)):
    events = await db.events.find({"created_by": admin["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [public_event(e) for e in events]


@api_router.get("/events/{event_id}")
async def get_event(event_id: str, admin: dict = Depends(require_admin)):
    event = await admin_event_or_404(event_id, admin)
    return public_event(event)


@api_router.patch("/events/{event_id}")
async def update_event(event_id: str, body: EventUpdate, admin: dict = Depends(require_admin)):
    await admin_event_or_404(event_id, admin)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if "category" in updates and updates["category"] not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Category must be one of {CATEGORIES}")
    if "similarity_threshold" in updates:
        t = updates["similarity_threshold"]
        if t < 50 or t > 100:
            raise HTTPException(status_code=400, detail="Threshold must be between 50 and 100")
    if updates:
        await db.events.update_one({"event_id": event_id}, {"$set": updates})
    event = await get_event_or_404(event_id)
    return public_event(event)


@api_router.post("/events/{event_id}/reindex")
async def reindex_event(event_id: str, admin: dict = Depends(require_admin)):
    """Rebuild the face collection for an event and re-index all its photos.
    Needed after switching the face engine (e.g. mock -> AWS Rekognition)."""
    event = await admin_event_or_404(event_id, admin)
    engine = get_face_engine()
    storage = get_storage()
    cid = event["collection_id"]

    # Fresh collection.
    await run_in_threadpool(engine.delete_collection, cid)
    await run_in_threadpool(engine.ensure_collection, cid)

    photos = await db.photos.find({"event_id": event_id}, {"_id": 0}).to_list(5000)
    await db.faces.delete_many({"event_id": event_id})

    total_faces = 0
    for p in photos:
        try:
            if p.get("source") == "gdrive":
                content, _ = await run_in_threadpool(gdrive_service.preview_bytes, p["drive_file_id"], 1600)
            else:
                content, _ = await run_in_threadpool(storage.get_object, p["storage_path"])
            faces = await run_in_threadpool(engine.index_photo, cid, p["photo_id"], content)
        except Exception as e:
            logger.error(f"reindex photo {p['photo_id']} failed: {e}")
            faces = []
        if faces:
            await db.faces.insert_many([{
                "face_id": f["face_id"],
                "event_id": event_id,
                "photo_id": p["photo_id"],
                "bounding_box": f.get("bounding_box"),
                "indexed_at": now_iso(),
            } for f in faces])
        await db.photos.update_one({"photo_id": p["photo_id"]}, {"$set": {"face_count": len(faces), "indexing_status": "indexed"}})
        total_faces += len(faces)

    # Stale matched albums must be re-computed by clients.
    await db.client_albums.delete_many({"event_id": event_id})
    await db.events.update_one({"event_id": event_id}, {"$set": {"indexing_status": "ready" if photos else "empty"}})
    return {"status": "reindexed", "photos": len(photos), "faces_indexed": total_faces}


@api_router.post("/events/{event_id}/archive")
async def archive_event(event_id: str, admin: dict = Depends(require_admin)):
    """Take a gallery offline. Clients/public can no longer view it (they are
    asked to contact the photographer) until it is restored."""
    await admin_event_or_404(event_id, admin)
    await db.events.update_one({"event_id": event_id}, {"$set": {"status": "archived"}})
    event = await get_event_or_404(event_id)
    return public_event(event)


@api_router.post("/events/{event_id}/unarchive")
async def unarchive_event(event_id: str, admin: dict = Depends(require_admin)):
    """Bring an archived gallery back online."""
    await admin_event_or_404(event_id, admin)
    await db.events.update_one({"event_id": event_id}, {"$set": {"status": "active"}})
    event = await get_event_or_404(event_id)
    return public_event(event)


@api_router.delete("/events/{event_id}")
async def delete_event(event_id: str, admin: dict = Depends(require_admin)):
    """Permanently delete a gallery and everything it owns: images + thumbnails
    from Cloudinary (original source), the AWS Rekognition face collection, and
    all related database records. This cannot be undone."""
    event = await admin_event_or_404(event_id, admin)

    # 1) Delete the face collection from Rekognition (original source).
    faces_collection_deleted = False
    cid = event.get("collection_id")
    if cid:
        try:
            await run_in_threadpool(get_face_engine().delete_collection, cid)
            faces_collection_deleted = True
        except Exception as e:
            logger.error(f"delete_event: rekognition delete_collection failed: {e}")

    # 2) Delete all stored objects (originals + thumbnails) from storage.
    cloudinary_deleted = 0
    try:
        prefix = f"{APP_NAME}/events/{event_id}"
        cloudinary_deleted = await run_in_threadpool(get_storage().delete_prefix, prefix)
    except Exception as e:
        logger.error(f"delete_event: storage delete_prefix failed: {e}")

    # 3) Delete all related database records.
    photos_removed = await db.photos.count_documents({"event_id": event_id})
    await db.photos.delete_many({"event_id": event_id})
    await db.faces.delete_many({"event_id": event_id})
    await db.client_albums.delete_many({"event_id": event_id})
    await db.photo_likes.delete_many({"event_id": event_id})
    await db.gallery_visitors.delete_many({"event_id": event_id})
    await db.gallery_shares.delete_many({"event_id": event_id})
    await db.access_grants.delete_many({"event_id": event_id})
    await db.consent_logs.delete_many({"event_id": event_id})
    await db.events.delete_one({"event_id": event_id})

    return {
        "status": "deleted",
        "event_id": event_id,
        "photos_removed": photos_removed,
        "cloudinary_objects_deleted": cloudinary_deleted,
        "faces_collection_deleted": faces_collection_deleted,
    }



async def _ingest_photo(event: dict, data: bytes, filename: str, content_type: str) -> dict:
    """Store original + thumbnail and queue the photo for background face indexing.
    Indexing (the slow AWS Rekognition step) is handled asynchronously by the
    indexing worker so bulk uploads of hundreds of photos stay fast."""
    event_id = event["event_id"]
    photo_id = f"pho_{uuid.uuid4().hex[:12]}"
    ext = (filename or "photo.jpg").split(".")[-1].lower()
    if ext not in ("jpg", "jpeg", "png", "webp", "heic"):
        ext = "jpg"
    storage = get_storage()
    thumb_bytes, w, h = await run_in_threadpool(make_thumbnail, data)

    orig_path = f"{APP_NAME}/events/{event_id}/{photo_id}.{ext}"
    thumb_path = f"{APP_NAME}/events/{event_id}/{photo_id}_thumb.jpg"
    await run_in_threadpool(storage.put_object, orig_path, data, content_type or "image/jpeg")
    await run_in_threadpool(storage.put_object, thumb_path, thumb_bytes, "image/jpeg")

    photo = {
        "photo_id": photo_id,
        "event_id": event_id,
        "storage_path": orig_path,
        "thumb_path": thumb_path,
        "filename": filename,
        "width": w,
        "height": h,
        "face_count": 0,
        "indexing_status": "pending",
        "uploaded_at": now_iso(),
    }
    await db.photos.insert_one(photo)

    set_fields = {"indexing_status": "indexing"}
    if not event.get("cover_path"):
        set_fields["cover_path"] = thumb_path
        event["cover_path"] = thumb_path  # so subsequent imports in a loop don't reset
    await db.events.update_one({"event_id": event_id}, {"$inc": {"photo_count": 1}, "$set": set_fields})
    _wake_indexer()
    return photo


# ---------------------------------------------------------------------------
# Background face-indexing worker
# ---------------------------------------------------------------------------
INDEX_BATCH = 5
_indexer_event: Optional[asyncio.Event] = None
_indexer_task: Optional[asyncio.Task] = None


def _wake_indexer():
    if _indexer_event is not None:
        try:
            _indexer_event.set()
        except Exception:
            pass


async def _index_one_photo(event: dict, photo: dict) -> None:
    engine = get_face_engine()
    storage = get_storage()
    try:
        if photo.get("source") == "gdrive":
            content, _ = await run_in_threadpool(gdrive_service.preview_bytes, photo["drive_file_id"], 1600)
        else:
            content, _ = await run_in_threadpool(storage.get_object, photo["storage_path"])
        faces = await run_in_threadpool(engine.index_photo, event["collection_id"], photo["photo_id"], content)
        if faces:
            await db.faces.insert_many([{
                "face_id": f["face_id"],
                "event_id": photo["event_id"],
                "photo_id": photo["photo_id"],
                "bounding_box": f.get("bounding_box"),
                "indexed_at": now_iso(),
            } for f in faces])
        await db.photos.update_one(
            {"photo_id": photo["photo_id"]},
            {"$set": {"face_count": len(faces), "indexing_status": "indexed", "indexed_at": now_iso()}},
        )
    except Exception as e:
        logger.error(f"index photo {photo['photo_id']} failed: {e}")
        await db.photos.update_one(
            {"photo_id": photo["photo_id"]},
            {"$set": {"indexing_status": "failed", "index_error": str(e)[:200]}},
        )


async def _refresh_event_index_status(event_id: str) -> None:
    total = await db.photos.count_documents({"event_id": event_id})
    remaining = await db.photos.count_documents(
        {"event_id": event_id, "indexing_status": {"$in": ["pending", "indexing"]}}
    )
    if total == 0:
        status = "empty"
    elif remaining > 0:
        status = "indexing"
    else:
        status = "ready"
    await db.events.update_one({"event_id": event_id}, {"$set": {"indexing_status": status}})


async def _indexing_loop():
    global _indexer_event
    _indexer_event = asyncio.Event()
    logger.info("Face-indexing worker started")
    while True:
        try:
            pending = await db.photos.find(
                {"indexing_status": "pending"}, {"_id": 0}
            ).limit(INDEX_BATCH).to_list(INDEX_BATCH)

            if not pending:
                _indexer_event.clear()
                try:
                    await asyncio.wait_for(_indexer_event.wait(), timeout=15)
                except asyncio.TimeoutError:
                    pass
                continue

            ids = [p["photo_id"] for p in pending]
            await db.photos.update_many(
                {"photo_id": {"$in": ids}}, {"$set": {"indexing_status": "indexing"}}
            )

            events_cache: dict[str, dict] = {}

            async def handle(p):
                ev = events_cache.get(p["event_id"])
                if ev is None:
                    ev = await db.events.find_one({"event_id": p["event_id"]})
                    events_cache[p["event_id"]] = ev
                if ev:
                    await _index_one_photo(ev, p)

            await asyncio.gather(*[handle(p) for p in pending])
            for eid in {p["event_id"] for p in pending}:
                await _refresh_event_index_status(eid)
        except Exception as e:
            logger.error(f"indexing worker error: {e}")
            await asyncio.sleep(3)


@api_router.post("/events/{event_id}/photos")
async def upload_photo(event_id: str, file: UploadFile = File(...), admin: dict = Depends(require_admin)):
    event = await admin_event_or_404(event_id, admin)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        photo = await _ingest_photo(event, data, file.filename or "photo.jpg", file.content_type or "image/jpeg")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Unsupported or corrupt image")
    return public_photo(photo)


@api_router.post("/events/{event_id}/photos/bulk")
async def upload_photos_bulk(event_id: str, files: list[UploadFile] = File(...),
                             admin: dict = Depends(require_admin)):
    """Store many photos in a single request; face indexing is queued in the
    background. Returns per-file results so the client can drive a progress bar."""
    event = await admin_event_or_404(event_id, admin)
    results = []
    uploaded = 0
    for f in files:
        try:
            data = await f.read()
            if not data:
                results.append({"filename": f.filename, "ok": False, "error": "empty"})
                continue
            photo = await _ingest_photo(event, data, f.filename or "photo.jpg", f.content_type or "image/jpeg")
            uploaded += 1
            results.append({"filename": f.filename, "ok": True, "photo_id": photo["photo_id"]})
        except Exception as e:
            logger.error(f"bulk upload {getattr(f, 'filename', '?')} failed: {e}")
            results.append({"filename": getattr(f, "filename", None), "ok": False, "error": "unsupported"})
    return {"uploaded": uploaded, "received": len(files), "results": results}


class S3ImportBody(BaseModel):
    bucket: Optional[str] = None
    prefix: Optional[str] = ""
    max_files: int = 200


@api_router.post("/events/{event_id}/import-s3")
async def import_from_s3(event_id: str, body: S3ImportBody, admin: dict = Depends(require_admin)):
    """Pull image objects from a configured S3-compatible bucket into this event."""
    event = await admin_event_or_404(event_id, admin)
    bucket = body.bucket or os.environ.get("S3_IMPORT_BUCKET")
    if not bucket:
        raise HTTPException(status_code=400, detail="No S3 bucket configured. Set S3_IMPORT_BUCKET or pass a bucket.")

    import boto3

    creds = dict(
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )
    try:
        locator = boto3.client("s3", **creds)
        loc = await run_in_threadpool(lambda: locator.get_bucket_location(Bucket=bucket))
        region = loc.get("LocationConstraint") or "us-east-1"
        s3 = boto3.client("s3", region_name=region, **creds)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot access bucket '{bucket}': {type(e).__name__}")

    IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".heic")
    imported, faces_total, skipped = 0, 0, 0
    token = None
    while imported < body.max_files:
        kwargs = {"Bucket": bucket, "MaxKeys": 100}
        if body.prefix:
            kwargs["Prefix"] = body.prefix
        if token:
            kwargs["ContinuationToken"] = token
        resp = await run_in_threadpool(lambda: s3.list_objects_v2(**kwargs))
        for obj in resp.get("Contents", []):
            if imported >= body.max_files:
                break
            key = obj["Key"]
            if key.endswith("/") or not key.lower().endswith(IMG_EXT):
                continue
            try:
                o = await run_in_threadpool(lambda: s3.get_object(Bucket=bucket, Key=key))
                data = o["Body"].read()
                photo = await _ingest_photo(event, data, key.split("/")[-1], o.get("ContentType", "image/jpeg"))
                imported += 1
                faces_total += photo["face_count"]
            except Exception as e:
                logger.error(f"S3 import {key} failed: {e}")
                skipped += 1
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")

    return {"status": "imported", "bucket": bucket, "imported": imported, "queued_for_indexing": imported, "skipped": skipped}


@api_router.get("/events/{event_id}/photos")
async def admin_list_photos(event_id: str, admin: dict = Depends(require_admin),
                            limit: int = 60, offset: int = 0):
    await admin_event_or_404(event_id, admin)
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    total = await db.photos.count_documents({"event_id": event_id})
    photos = await db.photos.find({"event_id": event_id}, {"_id": 0}) \
        .sort([("uploaded_at", -1), ("photo_id", -1)]).skip(offset).limit(limit).to_list(limit)
    items = [public_photo(p) for p in photos]
    return {"items": items, "total": total, "offset": offset, "limit": limit,
            "has_more": offset + len(items) < total}


@api_router.get("/events/{event_id}/indexing-status")
async def indexing_status(event_id: str, admin: dict = Depends(require_admin)):
    event = await admin_event_or_404(event_id, admin)
    total = await db.photos.count_documents({"event_id": event_id})
    indexed = await db.photos.count_documents({"event_id": event_id, "indexing_status": "indexed"})
    pending = await db.photos.count_documents({"event_id": event_id, "indexing_status": {"$in": ["pending", "indexing"]}})
    failed = await db.photos.count_documents({"event_id": event_id, "indexing_status": "failed"})
    faces = await db.faces.count_documents({"event_id": event_id})
    processed = indexed + failed
    percent = 100 if total == 0 else round(processed / total * 100)
    return {
        "status": event.get("indexing_status", "empty"),
        "total_photos": total,
        "indexed_photos": indexed,
        "pending_photos": pending,
        "failed_photos": failed,
        "total_faces": faces,
        "percent": percent,
        "complete": pending == 0,
    }


@api_router.post("/events/{event_id}/access")
async def grant_access(event_id: str, body: AccessGrantCreate, admin: dict = Depends(require_admin)):
    await admin_event_or_404(event_id, admin)
    if body.channel == "email":
        if not body.email:
            raise HTTPException(status_code=400, detail="Email required")
        key = {"event_id": event_id, "client_email": body.email.lower()}
    elif body.channel == "phone":
        if not body.phone:
            raise HTTPException(status_code=400, detail="Phone required")
        key = {"event_id": event_id, "client_phone": body.phone.strip()}
    else:
        raise HTTPException(status_code=400, detail="Invalid channel")

    grant_id = f"grant_{uuid.uuid4().hex[:12]}"
    doc = {
        **key,
        "grant_id": grant_id,
        "channel": body.channel,
        "full_gallery_access": body.full_gallery_access,
        "status": "active",
        "granted_by": admin["user_id"],
        "created_at": now_iso(),
    }
    await db.access_grants.update_one(
        key, {"$set": doc, "$setOnInsert": {}}, upsert=True
    )
    saved = await db.access_grants.find_one(key, {"_id": 0})
    return saved


@api_router.get("/events/{event_id}/access")
async def list_access(event_id: str, admin: dict = Depends(require_admin)):
    await admin_event_or_404(event_id, admin)
    grants = await db.access_grants.find({"event_id": event_id}, {"_id": 0}).to_list(2000)
    return grants


@api_router.patch("/events/{event_id}/access/{grant_id}")
async def update_access(event_id: str, grant_id: str, full_gallery_access: bool = Form(...),
                        admin: dict = Depends(require_admin)):
    await admin_event_or_404(event_id, admin)
    await db.access_grants.update_one(
        {"event_id": event_id, "grant_id": grant_id},
        {"$set": {"full_gallery_access": full_gallery_access}},
    )
    return {"status": "ok"}


@api_router.delete("/events/{event_id}/access/{grant_id}")
async def revoke_access(event_id: str, grant_id: str, admin: dict = Depends(require_admin)):
    await admin_event_or_404(event_id, admin)
    await db.access_grants.update_one(
        {"event_id": event_id, "grant_id": grant_id},
        {"$set": {"status": "revoked"}},
    )
    return {"status": "revoked"}


@api_router.get("/events/{event_id}/clients")
async def list_event_clients(event_id: str, admin: dict = Depends(require_admin)):
    await admin_event_or_404(event_id, admin)
    albums = await db.client_albums.find({"event_id": event_id}, {"_id": 0}).to_list(2000)
    out = []
    for a in albums:
        u = await db.users.find_one({"user_id": a["client_user_id"]}, {"_id": 0, "password_hash": 0})
        out.append({
            "client_user_id": a["client_user_id"],
            "name": u.get("name") if u else None,
            "email": u.get("email") if u else None,
            "phone": u.get("phone") if u else None,
            "matched_count": len(a.get("photo_ids", [])),
            "last_searched_at": a.get("last_searched_at"),
        })
    return out


@api_router.delete("/events/{event_id}/clients/{client_user_id}/face-data")
async def delete_client_face_data(event_id: str, client_user_id: str, admin: dict = Depends(require_admin)):
    """Right-to-be-forgotten: remove this person's indexed faces from the AWS
    Rekognition collection (DeleteFaces) so they can never be matched again, and
    delete their matched album + consent. (Raw selfies are never stored.)"""
    event = await admin_event_or_404(event_id, admin)
    album = await db.client_albums.find_one(
        {"event_id": event_id, "client_user_id": client_user_id}, {"_id": 0}
    )
    deleted_faces = 0
    if album and album.get("face_ids"):
        face_ids = list({fid for fid in album["face_ids"] if fid})
        if face_ids:
            engine = get_face_engine()
            try:
                # Rekognition DeleteFaces accepts up to 1000 ids per call.
                for i in range(0, len(face_ids), 1000):
                    await run_in_threadpool(engine.delete_faces, event["collection_id"], face_ids[i:i + 1000])
            except Exception as e:
                logger.error(f"Rekognition DeleteFaces failed for {client_user_id}: {e}")
            # Drop the local face records + refresh affected photo face counts.
            await db.faces.delete_many({"event_id": event_id, "face_id": {"$in": face_ids}})
            for pid in {p for p in album.get("photo_ids", [])}:
                remaining = await db.faces.count_documents({"event_id": event_id, "photo_id": pid})
                await db.photos.update_one({"photo_id": pid}, {"$set": {"face_count": remaining}})
            deleted_faces = len(face_ids)

    await db.client_albums.delete_many({"event_id": event_id, "client_user_id": client_user_id})
    await db.consent_logs.delete_many({"event_id": event_id, "client_user_id": client_user_id})
    return {"status": "deleted", "faces_removed": deleted_faces}


# ---------------------------------------------------------------------------
# Admin — shareable link, HD QR & self-service visitor management
# ---------------------------------------------------------------------------
def _gen_qr_png_b64(data: str, box_size: int = 20) -> str:
    """Generate a high-resolution QR PNG (data URI) for the given link."""
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=box_size,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0D0D0D", back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


@api_router.get("/events/{event_id}/share")
async def get_share_info(event_id: str, admin: dict = Depends(require_admin)):
    event = await admin_event_or_404(event_id, admin)
    url = share_url_for(event_id)
    return {
        "share_url": url,
        "share_enabled": event.get("share_enabled", True),
        "qr_base64": _gen_qr_png_b64(url),
    }


async def _visitor_out(v: dict) -> dict:
    matched = await db.client_albums.find_one(
        {"event_id": v["event_id"], "client_user_id": v.get("client_user_id")}, {"_id": 0}
    )
    liked = await db.photo_likes.count_documents(
        {"event_id": v["event_id"], "client_user_id": v.get("client_user_id")}
    )
    return {
        "visitor_id": v["visitor_id"],
        "event_id": v["event_id"],
        "name": v.get("name"),
        "phone": v.get("phone"),
        "status": v.get("status", "active"),
        "matched_count": len(matched.get("photo_ids", [])) if matched else 0,
        "liked_count": liked,
        "created_at": v.get("created_at"),
        "last_seen_at": v.get("last_seen_at"),
    }


@api_router.get("/events/{event_id}/visitors")
async def list_visitors(event_id: str, admin: dict = Depends(require_admin)):
    await admin_event_or_404(event_id, admin)
    visitors = await db.gallery_visitors.find(
        {"event_id": event_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(5000)
    return [await _visitor_out(v) for v in visitors]


class VisitorUpdate(BaseModel):
    status: str  # "active" | "blocked"


@api_router.patch("/events/{event_id}/visitors/{visitor_id}")
async def update_visitor(event_id: str, visitor_id: str, body: VisitorUpdate,
                         admin: dict = Depends(require_admin)):
    await admin_event_or_404(event_id, admin)
    if body.status not in ("active", "blocked"):
        raise HTTPException(status_code=400, detail="status must be active or blocked")
    visitor = await db.gallery_visitors.find_one({"event_id": event_id, "visitor_id": visitor_id})
    if not visitor:
        raise HTTPException(status_code=404, detail="Visitor not found")
    await db.gallery_visitors.update_one(
        {"event_id": event_id, "visitor_id": visitor_id}, {"$set": {"status": body.status}}
    )
    # Reflect on the underlying access grant so they lose/regain gallery access.
    grant_status = "active" if body.status == "active" else "revoked"
    if visitor.get("phone"):
        await db.access_grants.update_one(
            {"event_id": event_id, "client_phone": visitor["phone"]},
            {"$set": {"status": grant_status}},
        )
    if body.status == "blocked" and visitor.get("client_user_id"):
        # Kick out active sessions immediately.
        await db.user_sessions.delete_many({"user_id": visitor["client_user_id"]})
    return {"status": body.status}


@api_router.get("/events/{event_id}/visitors/export")
async def export_visitors(event_id: str, admin: dict = Depends(require_admin)):
    await admin_event_or_404(event_id, admin)
    visitors = await db.gallery_visitors.find(
        {"event_id": event_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(10000)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Name", "Mobile", "Status", "Matched photos", "Liked photos", "First access", "Last seen"])
    for v in visitors:
        row = await _visitor_out(v)
        writer.writerow([
            row["name"] or "", row["phone"] or "", row["status"],
            row["matched_count"], row["liked_count"],
            row["created_at"] or "", row["last_seen_at"] or "",
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="visitors_{event_id}.csv"'},
    )


def _public_url(path: str | None) -> str | None:
    """Direct CDN URL for a stored object (Cloudinary), or None so the client
    falls back to the authenticated /api/files proxy."""
    if not path:
        return None
    try:
        return get_storage().public_url(path)
    except Exception:
        return None


def _gdrive_proxy_url(file_id: str, width: int) -> str:
    base = (PUBLIC_BASE_URL or "").rstrip("/")
    return f"{base}/api/gdrive/thumb/{file_id}?w={width}"


def public_photo(p: dict) -> dict:
    if p.get("source") == "gdrive":
        fid = p.get("drive_file_id")
        return {
            "photo_id": p["photo_id"],
            "event_id": p["event_id"],
            "source": "gdrive",
            "drive_file_id": fid,
            "thumb_path": None,
            "storage_path": None,
            "url": _gdrive_proxy_url(fid, 1600),
            "thumb_url": _gdrive_proxy_url(fid, 600),
            "filename": p.get("filename"),
            "folder": p.get("folder_path") or "",
            "width": p.get("width"),
            "height": p.get("height"),
            "face_count": p.get("face_count", 0),
            "indexing_status": p.get("indexing_status"),
        }
    return {
        "photo_id": p["photo_id"],
        "event_id": p["event_id"],
        "source": p.get("source", "upload"),
        "thumb_path": p.get("thumb_path"),
        "storage_path": p.get("storage_path"),
        "url": _public_url(p.get("storage_path")),
        "thumb_url": _public_url(p.get("thumb_path")),
        "filename": p.get("filename"),
        "width": p.get("width"),
        "height": p.get("height"),
        "face_count": p.get("face_count", 0),
        "indexing_status": p.get("indexing_status"),
    }


async def _liked_ids(event_id: str, user_id: str) -> set:
    docs = await db.photo_likes.find(
        {"event_id": event_id, "client_user_id": user_id}, {"_id": 0, "photo_id": 1}
    ).to_list(20000)
    return {d["photo_id"] for d in docs}


async def _annotate_liked(event_id: str, user_id: str, photos: list[dict]) -> list[dict]:
    liked = await _liked_ids(event_id, user_id)
    for p in photos:
        p["liked"] = p["photo_id"] in liked
    return photos


# ---------------------------------------------------------------------------
# Client — shared events, consent, selfie search, My Photos
# ---------------------------------------------------------------------------
class ConsentBody(BaseModel):
    accepted: bool


@api_router.get("/client/events")
async def client_events(user: dict = Depends(require_client)):
    ors = []
    if user.get("email"):
        ors.append({"client_email": user["email"].lower()})
    if user.get("phone"):
        ors.append({"client_phone": user["phone"]})
    if not ors:
        return []
    grants = await db.access_grants.find({"status": "active", "$or": ors}, {"_id": 0}).to_list(2000)
    out = []
    for g in grants:
        event = await db.events.find_one({"event_id": g["event_id"]}, {"_id": 0})
        if not event:
            continue
        if event.get("status") == "archived":
            continue  # archived galleries are offline for clients
        album = await db.client_albums.find_one(
            {"event_id": g["event_id"], "client_user_id": user["user_id"]}, {"_id": 0}
        )
        pe = public_event(event)
        pe["full_gallery_access"] = g.get("full_gallery_access", False)
        pe["my_photos_count"] = len(album.get("photo_ids", [])) if album else 0
        pe["searched"] = album is not None
        out.append(pe)
    return out


@api_router.get("/client/events/{event_id}")
async def client_event_detail(event_id: str, user: dict = Depends(require_client)):
    grant = await client_grant_or_403(event_id, user)
    event = await get_event_or_404(event_id)
    album = await db.client_albums.find_one(
        {"event_id": event_id, "client_user_id": user["user_id"]}, {"_id": 0}
    )
    consent = await db.consent_logs.find_one(
        {"event_id": event_id, "client_user_id": user["user_id"]}, {"_id": 0}
    )
    pe = public_event(event)
    pe["full_gallery_access"] = grant.get("full_gallery_access", False)
    pe["my_photos_count"] = len(album.get("photo_ids", [])) if album else 0
    pe["searched"] = album is not None
    pe["consent_given"] = consent is not None
    return pe


@api_router.get("/client/events/{event_id}/photos")
async def client_all_photos(event_id: str, user: dict = Depends(require_client),
                            limit: int = 60, offset: int = 0):
    grant = await client_grant_or_403(event_id, user)
    if not grant.get("full_gallery_access", False):
        raise HTTPException(status_code=403, detail="Full gallery access not granted")
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    total = await db.photos.count_documents({"event_id": event_id})
    photos = await db.photos.find({"event_id": event_id}, {"_id": 0}) \
        .sort([("uploaded_at", -1), ("photo_id", -1)]).skip(offset).limit(limit).to_list(limit)
    items = [public_photo(p) for p in photos]
    await _annotate_liked(event_id, user["user_id"], items)
    return {"items": items, "total": total, "offset": offset, "limit": limit,
            "has_more": offset + len(items) < total}


@api_router.post("/client/events/{event_id}/consent")
async def give_consent(event_id: str, body: ConsentBody, user: dict = Depends(require_client)):
    await client_grant_or_403(event_id, user)
    if not body.accepted:
        raise HTTPException(status_code=400, detail="Consent is required to continue")
    await db.consent_logs.update_one(
        {"event_id": event_id, "client_user_id": user["user_id"]},
        {"$set": {
            "event_id": event_id,
            "client_user_id": user["user_id"],
            "accepted": True,
            "accepted_at": now_iso(),
        }},
        upsert=True,
    )
    return {"status": "ok"}


@api_router.post("/client/events/{event_id}/search")
async def selfie_search(event_id: str, file: UploadFile = File(...), user: dict = Depends(require_client)):
    grant = await client_grant_or_403(event_id, user)
    event = await get_event_or_404(event_id)

    consent = await db.consent_logs.find_one({"event_id": event_id, "client_user_id": user["user_id"]})
    if not consent:
        raise HTTPException(status_code=403, detail="Biometric consent required before searching")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty selfie")

    engine = get_face_engine()

    # 1) Quality gate (raw selfie never stored).
    quality = await run_in_threadpool(engine.check_quality, data)
    if not quality.ok:
        return {"status": "retake", "reason": quality.reason}

    # 2) Search collection.
    threshold = float(event.get("similarity_threshold", DEFAULT_SIMILARITY_THRESHOLD))
    faces = await db.faces.find({"event_id": event_id}, {"_id": 0}).to_list(200000)
    seed = f"{user['user_id']}:{event_id}"
    try:
        matches = await run_in_threadpool(
            engine.search, event["collection_id"], data, threshold, faces, seed
        )
    except NotIndexedError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # 3) Dedupe by photo (multi-face photo appears once, keep best similarity).
    best: dict[str, float] = {}
    for m in matches:
        pid = m["photo_id"]
        if pid not in best or m["similarity"] > best[pid]:
            best[pid] = m["similarity"]
    matched_photo_ids = sorted(best.keys(), key=lambda p: best[p], reverse=True)
    matched_face_ids = [m["face_id"] for m in matches]

    # 4) Upsert private "My Photos" album.
    await db.client_albums.update_one(
        {"event_id": event_id, "client_user_id": user["user_id"]},
        {"$set": {
            "event_id": event_id,
            "client_user_id": user["user_id"],
            "photo_ids": matched_photo_ids,
            "face_ids": matched_face_ids,
            "scores": {p: best[p] for p in matched_photo_ids},
            "last_searched_at": now_iso(),
        }},
        upsert=True,
    )

    photos = await _photos_with_scores(matched_photo_ids, best)
    await _annotate_liked(event_id, user["user_id"], photos)
    return {
        "status": "matched",
        "threshold": threshold,
        "count": len(matched_photo_ids),
        "full_gallery_access": grant.get("full_gallery_access", False),
        "photos": photos,
    }


@api_router.get("/client/events/{event_id}/my-photos")
async def my_photos(event_id: str, user: dict = Depends(require_client)):
    await client_grant_or_403(event_id, user)
    album = await db.client_albums.find_one(
        {"event_id": event_id, "client_user_id": user["user_id"]}, {"_id": 0}
    )
    if not album:
        return {"searched": False, "count": 0, "photos": [], "last_searched_at": None}
    scores = album.get("scores", {})
    photos = await _photos_with_scores(album.get("photo_ids", []), scores)
    await _annotate_liked(event_id, user["user_id"], photos)
    return {
        "searched": True,
        "count": len(photos),
        "photos": photos,
        "last_searched_at": album.get("last_searched_at"),
    }


async def _photos_with_scores(photo_ids: list[str], scores: dict) -> list[dict]:
    if not photo_ids:
        return []
    docs = await db.photos.find({"photo_id": {"$in": photo_ids}}, {"_id": 0}).to_list(5000)
    by_id = {d["photo_id"]: d for d in docs}
    out = []
    for pid in photo_ids:
        d = by_id.get(pid)
        if not d:
            continue
        pp = public_photo(d)
        pp["similarity"] = scores.get(pid)
        out.append(pp)
    return out


async def _client_can_see_photo(event_id: str, user: dict, grant: dict, photo_id: str) -> bool:
    """A client may act on a photo they can already view: full-gallery access,
    or the photo is in their matched album."""
    if grant.get("full_gallery_access", False):
        return True
    album = await db.client_albums.find_one(
        {"event_id": event_id, "client_user_id": user["user_id"]}
    )
    return bool(album and photo_id in album.get("photo_ids", []))


@api_router.post("/client/events/{event_id}/photos/{photo_id}/like")
async def toggle_like(event_id: str, photo_id: str, user: dict = Depends(require_client)):
    grant = await client_grant_or_403(event_id, user)
    photo = await db.photos.find_one({"photo_id": photo_id, "event_id": event_id}, {"_id": 0})
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    if not await _client_can_see_photo(event_id, user, grant, photo_id):
        raise HTTPException(status_code=403, detail="Not allowed to like this photo")
    key = {"event_id": event_id, "client_user_id": user["user_id"], "photo_id": photo_id}
    existing = await db.photo_likes.find_one(key)
    if existing:
        await db.photo_likes.delete_one(key)
        liked = False
    else:
        await db.photo_likes.insert_one({**key, "created_at": now_iso()})
        liked = True
    count = await db.photo_likes.count_documents(
        {"event_id": event_id, "client_user_id": user["user_id"]}
    )
    return {"liked": liked, "liked_count": count}


@api_router.get("/client/events/{event_id}/liked")
async def client_liked(event_id: str, user: dict = Depends(require_client)):
    await client_grant_or_403(event_id, user)
    likes = await db.photo_likes.find(
        {"event_id": event_id, "client_user_id": user["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(20000)
    ids = [l["photo_id"] for l in likes]
    album = await db.client_albums.find_one(
        {"event_id": event_id, "client_user_id": user["user_id"]}, {"_id": 0}
    )
    scores = album.get("scores", {}) if album else {}
    photos = await _photos_with_scores(ids, scores)
    for p in photos:
        p["liked"] = True
    return {"count": len(photos), "photos": photos}


@api_router.get("/events/{event_id}/clients/{client_user_id}/photos")
async def admin_client_photos(event_id: str, client_user_id: str, admin: dict = Depends(require_admin)):
    """Admin view of a specific client's Matched (My Photos) + Liked galleries."""
    await admin_event_or_404(event_id, admin)
    u = await db.users.find_one({"user_id": client_user_id}, {"_id": 0, "password_hash": 0})
    album = await db.client_albums.find_one(
        {"event_id": event_id, "client_user_id": client_user_id}, {"_id": 0}
    )
    matched_ids = album.get("photo_ids", []) if album else []
    scores = album.get("scores", {}) if album else {}
    matched = await _photos_with_scores(matched_ids, scores)
    likes = await db.photo_likes.find(
        {"event_id": event_id, "client_user_id": client_user_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(20000)
    liked_ids = [l["photo_id"] for l in likes]
    liked = await _photos_with_scores(liked_ids, scores)
    return {
        "client": {
            "client_user_id": client_user_id,
            "name": u.get("name") if u else None,
            "email": u.get("email") if u else None,
            "phone": u.get("phone") if u else None,
        },
        "matched": matched,
        "liked": liked,
    }


# ---------------------------------------------------------------------------
# Public (no-auth) — self-service shareable gallery access by name + mobile
# ---------------------------------------------------------------------------
class PublicAccessBody(BaseModel):
    name: str
    phone: str


async def _register_visitor(event_id: str, name: str, phone: str, source: str = "public_share") -> tuple[dict, str]:
    """Validate a name+mobile gate, upsert the client user + access grant +
    gallery_visitors record (for admin analytics), and return (user, token)."""
    name = (name or "").strip()
    phone = normalize_phone(phone)
    if not name:
        raise HTTPException(status_code=400, detail="Please enter your name")
    if not phone or len(phone) < 6:
        raise HTTPException(status_code=400, detail="Please enter a valid mobile number")

    existing = await db.gallery_visitors.find_one({"event_id": event_id, "phone": phone})
    if existing and existing.get("status") == "blocked":
        raise HTTPException(status_code=403, detail="Your access to this gallery has been blocked")

    # Find or create a lightweight client user keyed by phone.
    user = await db.users.find_one({"phone": phone, "role": "client"})
    if not user:
        user = {
            "user_id": new_user_id(),
            "role": "client",
            "name": name,
            "email": None,
            "phone": phone,
            "password_hash": None,
            "auth_provider": "public_share",
            "created_at": now_iso(),
        }
        await db.users.insert_one(user)
    elif name and user.get("name") != name:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"name": name}})

    # Ensure an active full-gallery access grant so the whole client stack works.
    key = {"event_id": event_id, "client_phone": phone}
    await db.access_grants.update_one(
        key,
        {"$set": {
            **key,
            "channel": "public",
            "full_gallery_access": True,
            "status": "active",
            "granted_by": source,
        }, "$setOnInsert": {"grant_id": f"grant_{uuid.uuid4().hex[:12]}", "created_at": now_iso()}},
        upsert=True,
    )

    # Upsert the visitor record for admin tracking (analytics).
    if existing:
        await db.gallery_visitors.update_one(
            {"visitor_id": existing["visitor_id"]},
            {"$set": {"name": name, "client_user_id": user["user_id"], "last_seen_at": now_iso()}},
        )
    else:
        await db.gallery_visitors.insert_one({
            "visitor_id": f"vis_{uuid.uuid4().hex[:12]}",
            "event_id": event_id,
            "name": name,
            "phone": phone,
            "client_user_id": user["user_id"],
            "status": "active",
            "source": source,
            "created_at": now_iso(),
            "last_seen_at": now_iso(),
        })

    token = await create_session(user["user_id"])
    return user, token


@api_router.get("/public/events/{event_id}")
async def public_event_info(event_id: str):
    event = await db.events.find_one({"event_id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Gallery not found")
    ensure_event_available(event)
    if not event.get("share_enabled", True):
        raise HTTPException(status_code=403, detail="This gallery is not currently shared")
    return {
        "event_id": event["event_id"],
        "name": event["name"],
        "date": event.get("date"),
        "category": event.get("category"),
        "photographer": event.get("photographer"),
        "photo_count": event.get("photo_count", 0),
    }


@api_router.post("/public/events/{event_id}/access")
async def public_access(event_id: str, body: PublicAccessBody):
    event = await db.events.find_one({"event_id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Gallery not found")
    ensure_event_available(event)
    if not event.get("share_enabled", True):
        raise HTTPException(status_code=403, detail="This gallery is not currently shared")

    user, token = await _register_visitor(event_id, body.name, body.phone)
    return {
        "session_token": token,
        "user": _public_user(user),
        "event": public_event(event),
    }


# ---------------------------------------------------------------------------
# Client-generated share links (share My Photos / Liked / All Photos)
# ---------------------------------------------------------------------------
SHARE_SCOPES = {"all", "matched", "liked"}


class ShareCreate(BaseModel):
    scope: str  # all | matched | liked


def _share_event_info(event: dict) -> dict:
    return {
        "event_id": event["event_id"],
        "name": event["name"],
        "category": event.get("category"),
        "photographer": event.get("photographer"),
        "date": event.get("date"),
        "cover_url": _public_url(event.get("cover_path")),
        "photo_count": event.get("photo_count", 0),
    }


async def _share_photos(share: dict) -> list[dict]:
    """Resolve the photos a share exposes, based on its scope and the sharer."""
    event_id = share["event_id"]
    scope = share.get("scope")
    if scope == "all":
        docs = await db.photos.find({"event_id": event_id}, {"_id": 0}) \
            .sort([("uploaded_at", -1), ("photo_id", -1)]).to_list(5000)
        return [public_photo(p) for p in docs]
    if scope == "matched":
        album = await db.client_albums.find_one(
            {"event_id": event_id, "client_user_id": share["client_user_id"]}, {"_id": 0}
        )
        ids = album.get("photo_ids", []) if album else []
        scores = album.get("scores", {}) if album else {}
        return await _photos_with_scores(ids, scores)
    if scope == "liked":
        likes = await db.photo_likes.find(
            {"event_id": event_id, "client_user_id": share["client_user_id"]}, {"_id": 0}
        ).sort("created_at", -1).to_list(20000)
        return await _photos_with_scores([l["photo_id"] for l in likes], {})
    return []


async def _load_share_or_404(share_id: str) -> tuple[dict, dict]:
    share = await db.gallery_shares.find_one({"share_id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Share link not found")
    event = await db.events.find_one({"event_id": share["event_id"]}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Gallery not found")
    ensure_event_available(event)
    if not event.get("share_enabled", True):
        raise HTTPException(status_code=403, detail="This gallery is not currently shared")
    return share, event


@api_router.post("/client/events/{event_id}/share")
async def create_client_share(event_id: str, body: ShareCreate, user: dict = Depends(require_client)):
    """Create (or reuse) a public share link for one of the viewer's galleries."""
    grant = await client_grant_or_403(event_id, user)  # verifies access + not archived
    scope = (body.scope or "").strip().lower()
    if scope not in SHARE_SCOPES:
        raise HTTPException(status_code=400, detail="Invalid scope")
    if scope == "all" and not grant.get("full_gallery_access", False):
        raise HTTPException(status_code=403, detail="You don't have full gallery access to share")

    existing = await db.gallery_shares.find_one(
        {"event_id": event_id, "client_user_id": user["user_id"], "scope": scope}, {"_id": 0}
    )
    if existing:
        share_id = existing["share_id"]
    else:
        share_id = f"shr_{uuid.uuid4().hex[:12]}"
        await db.gallery_shares.insert_one({
            "share_id": share_id,
            "event_id": event_id,
            "client_user_id": user["user_id"],
            "scope": scope,
            "sharer_name": user.get("name"),
            "created_at": now_iso(),
        })
    return {"share_id": share_id, "scope": scope, "share_url": f"{PUBLIC_BASE_URL}/s/{share_id}"}


@api_router.get("/public/shares/{share_id}")
async def public_share_info(share_id: str):
    """Meta for a share link — shown on the name+mobile gate (no auth)."""
    share, event = await _load_share_or_404(share_id)
    return {
        "share_id": share_id,
        "scope": share["scope"],
        "sharer_name": share.get("sharer_name"),
        "event": _share_event_info(event),
    }


@api_router.post("/public/shares/{share_id}/access")
async def public_share_access(share_id: str, body: PublicAccessBody):
    """Name+mobile gate for a share link. Registers the viewer as a gallery
    visitor (admin analytics) and returns the shared photos + a session token."""
    share, event = await _load_share_or_404(share_id)
    user, token = await _register_visitor(share["event_id"], body.name, body.phone, source="link_share")
    photos = await _share_photos(share)
    return {
        "session_token": token,
        "viewer": _public_user(user),
        "scope": share["scope"],
        "sharer_name": share.get("sharer_name"),
        "event": _share_event_info(event),
        "photos": photos,
        "count": len(photos),
    }


@api_router.get("/public/shares/{share_id}/photos")
async def public_share_photos(share_id: str, user: dict = Depends(require_client)):
    """Re-fetch a share's photos for an already-gated viewer (used on refresh)."""
    share, event = await _load_share_or_404(share_id)
    await client_grant_or_403(share["event_id"], user)  # must be a registered visitor
    photos = await _share_photos(share)
    return {
        "scope": share["scope"],
        "sharer_name": share.get("sharer_name"),
        "event": _share_event_info(event),
        "photos": photos,
        "count": len(photos),
    }


# ---------------------------------------------------------------------------
# Image serving (auth required; ?token= supported for web <img>)
# ---------------------------------------------------------------------------
_gdrive_cache: "dict[str, tuple[bytes, str]]" = {}
_GDRIVE_CACHE_MAX = 400


@api_router.get("/gdrive/thumb/{file_id}")
async def gdrive_thumb(file_id: str, w: int = 600):
    """Public proxy that streams a web-sized preview of a Google Drive image.
    Only serves files that belong to one of our Drive galleries (no open proxy).
    Originals are never served — width is clamped to preview sizes."""
    photo = await db.photos.find_one(
        {"drive_file_id": file_id, "source": "gdrive"}, {"_id": 0, "photo_id": 1}
    )
    if not photo:
        raise HTTPException(status_code=404, detail="Not found")
    width = 600 if w <= 600 else (1200 if w <= 1200 else 1600)
    ckey = f"{file_id}:{width}"
    hit = _gdrive_cache.get(ckey)
    if hit is None:
        try:
            content, ctype = await run_in_threadpool(gdrive_service.preview_bytes, file_id, width)
        except DriveError:
            raise HTTPException(status_code=404, detail="Preview unavailable")
        if len(_gdrive_cache) >= _GDRIVE_CACHE_MAX:
            _gdrive_cache.pop(next(iter(_gdrive_cache)), None)
        _gdrive_cache[ckey] = (content, ctype)
        hit = (content, ctype)
    return Response(content=hit[0], media_type=hit[1], headers={"Cache-Control": "public, max-age=86400"})


@api_router.get("/files/{path:path}")
async def serve_file(path: str, user: dict = Depends(user_from_token_or_header)):
    # Authorization: user must be admin owner OR a client with an active grant on the event.
    photo = await db.photos.find_one({"$or": [{"storage_path": path}, {"thumb_path": path}]}, {"_id": 0})
    if not photo:
        raise HTTPException(status_code=404, detail="Not found")
    event = await db.events.find_one({"event_id": photo["event_id"]}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Not found")

    authorized = False
    if user["role"] == "admin" and event["created_by"] == user["user_id"]:
        authorized = True
    elif user["role"] == "client":
        try:
            grant = await client_grant_or_403(photo["event_id"], user)
            if grant.get("full_gallery_access"):
                authorized = True
            elif path == event.get("cover_path"):
                # Cover thumbnail is visible to any granted client (gallery card).
                authorized = True
            else:
                album = await db.client_albums.find_one(
                    {"event_id": photo["event_id"], "client_user_id": user["user_id"]}
                )
                if album and photo["photo_id"] in album.get("photo_ids", []):
                    authorized = True
                else:
                    like = await db.photo_likes.find_one({
                        "event_id": photo["event_id"],
                        "client_user_id": user["user_id"],
                        "photo_id": photo["photo_id"],
                    })
                    if like:
                        authorized = True
        except HTTPException:
            authorized = False
    if not authorized:
        raise HTTPException(status_code=403, detail="Not authorized")

    storage = get_storage()
    try:
        content, ctype = await run_in_threadpool(storage.get_object, path)
    except Exception:
        raise HTTPException(status_code=404, detail="Not found")
    return Response(content=content, media_type=ctype, headers={"Cache-Control": "private, max-age=86400"})


@api_router.get("/")
async def root():
    return {"service": "Lumiere Gallery API", "status": "ok"}


@api_router.get("/meta")
async def meta():
    return {"categories": CATEGORIES, "default_threshold": DEFAULT_SIMILARITY_THRESHOLD}


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------
app.include_router(api_router)

# Album module (separate product) — mounts its own /api/albums router + viewer.
from album_routes import album_router  # noqa: E402
app.include_router(album_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    # Indexes
    try:
        await db.users.create_index("user_id", unique=True)
        await db.users.create_index("email", sparse=True)
        await db.user_sessions.create_index("session_token", unique=True)
        await db.user_sessions.create_index("expires_at", expireAfterSeconds=0)
        await db.events.create_index("event_id", unique=True)
        await db.events.create_index("created_by")
        await db.photos.create_index("photo_id", unique=True)
        await db.photos.create_index("event_id")
        await db.faces.create_index("event_id")
        await db.access_grants.create_index("event_id")
        await db.client_albums.create_index([("event_id", 1), ("client_user_id", 1)], unique=True)
        await db.photo_likes.create_index([("event_id", 1), ("client_user_id", 1), ("photo_id", 1)], unique=True)
        await db.photo_likes.create_index([("event_id", 1), ("client_user_id", 1)])
    except Exception as e:
        logger.error(f"Index creation issue: {e}")

    # Storage init
    try:
        await run_in_threadpool(get_storage().init)
        logger.info("Object storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")

    # Seed admin (idempotent)
    try:
        existing = await db.users.find_one({"email": ADMIN_SEED_EMAIL.lower()})
        if not existing:
            await db.users.insert_one({
                "user_id": new_user_id(),
                "role": "admin",
                "name": "Studio Admin",
                "email": ADMIN_SEED_EMAIL.lower(),
                "phone": None,
                "password_hash": hash_password(ADMIN_SEED_PASSWORD),
                "auth_provider": "password",
                "created_at": now_iso(),
            })
            logger.info(f"Seeded admin {ADMIN_SEED_EMAIL}")
    except Exception as e:
        logger.error(f"Admin seed failed: {e}")


    # Recover any photos left mid-indexing by a previous restart, then start the worker.
    try:
        await db.photos.update_many({"indexing_status": "indexing"}, {"$set": {"indexing_status": "pending"}})
    except Exception as e:
        logger.error(f"Indexing recovery failed: {e}")
    global _indexer_task
    _indexer_task = asyncio.create_task(_indexing_loop())


@app.on_event("shutdown")
async def on_shutdown():
    if _indexer_task:
        _indexer_task.cancel()
    client.close()
