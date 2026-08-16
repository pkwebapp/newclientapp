"""Lumiere Gallery — client photo gallery with face-recognition search."""
import io
import os
import uuid
import random
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from fastapi import FastAPI, APIRouter, UploadFile, File, Form, Depends, HTTPException, Response
from starlette.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, EmailStr, Field
from PIL import Image, ImageOps

from config import (
    db, client, APP_NAME, DEFAULT_SIMILARITY_THRESHOLD, OTP_DEV_MODE, SMS_PROVIDER,
    ADMIN_SEED_EMAIL, ADMIN_SEED_PASSWORD,
)
from storage_service import get_storage
from face_engine import get_face_engine, NotIndexedError
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


async def get_event_or_404(event_id: str) -> dict:
    event = await db.events.find_one({"event_id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


async def admin_event_or_404(event_id: str, admin: dict) -> dict:
    event = await get_event_or_404(event_id)
    if event["created_by"] != admin["user_id"]:
        raise HTTPException(status_code=403, detail="Not your event")
    return event


async def client_grant_or_403(event_id: str, client_user: dict) -> dict:
    """Return the active access grant for this client on the event, else 403."""
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
        "created_at": event.get("created_at"),
    }


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
        "created_by": admin["user_id"],
        "created_at": now_iso(),
    }
    await db.events.insert_one(event)
    return public_event(event)


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


async def _ingest_photo(event: dict, data: bytes, filename: str, content_type: str) -> dict:
    """Store original + thumbnail, index faces, persist photo + face docs."""
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

    engine = get_face_engine()
    faces = await run_in_threadpool(engine.index_photo, event["collection_id"], photo_id, data)
    if faces:
        await db.faces.insert_many([{
            "face_id": f["face_id"],
            "event_id": event_id,
            "photo_id": photo_id,
            "bounding_box": f.get("bounding_box"),
            "indexed_at": now_iso(),
        } for f in faces])

    photo = {
        "photo_id": photo_id,
        "event_id": event_id,
        "storage_path": orig_path,
        "thumb_path": thumb_path,
        "filename": filename,
        "width": w,
        "height": h,
        "face_count": len(faces),
        "indexing_status": "indexed",
        "uploaded_at": now_iso(),
    }
    await db.photos.insert_one(photo)

    set_fields = {"indexing_status": "ready"}
    if not event.get("cover_path"):
        set_fields["cover_path"] = thumb_path
        event["cover_path"] = thumb_path  # so subsequent imports in a loop don't reset
    await db.events.update_one({"event_id": event_id}, {"$inc": {"photo_count": 1}, "$set": set_fields})
    return photo


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

    return {"status": "imported", "bucket": bucket, "imported": imported, "faces_indexed": faces_total, "skipped": skipped}


@api_router.get("/events/{event_id}/photos")
async def admin_list_photos(event_id: str, admin: dict = Depends(require_admin)):
    await admin_event_or_404(event_id, admin)
    photos = await db.photos.find({"event_id": event_id}, {"_id": 0}).sort("uploaded_at", -1).to_list(5000)
    return [public_photo(p) for p in photos]


@api_router.get("/events/{event_id}/indexing-status")
async def indexing_status(event_id: str, admin: dict = Depends(require_admin)):
    event = await admin_event_or_404(event_id, admin)
    total = await db.photos.count_documents({"event_id": event_id})
    indexed = await db.photos.count_documents({"event_id": event_id, "indexing_status": "indexed"})
    faces = await db.faces.count_documents({"event_id": event_id})
    return {
        "status": event.get("indexing_status", "empty"),
        "total_photos": total,
        "indexed_photos": indexed,
        "total_faces": faces,
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
    """Right-to-be-forgotten: delete the client's matched album for this event.
    (Raw selfies are never stored; only match references exist.)"""
    await admin_event_or_404(event_id, admin)
    await db.client_albums.delete_many({"event_id": event_id, "client_user_id": client_user_id})
    await db.consent_logs.delete_many({"event_id": event_id, "client_user_id": client_user_id})
    return {"status": "deleted"}


def public_photo(p: dict) -> dict:
    return {
        "photo_id": p["photo_id"],
        "event_id": p["event_id"],
        "thumb_path": p.get("thumb_path"),
        "storage_path": p.get("storage_path"),
        "width": p.get("width"),
        "height": p.get("height"),
        "face_count": p.get("face_count", 0),
        "indexing_status": p.get("indexing_status"),
    }


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
async def client_all_photos(event_id: str, user: dict = Depends(require_client)):
    grant = await client_grant_or_403(event_id, user)
    if not grant.get("full_gallery_access", False):
        raise HTTPException(status_code=403, detail="Full gallery access not granted")
    photos = await db.photos.find({"event_id": event_id}, {"_id": 0}).sort("uploaded_at", -1).to_list(5000)
    return [public_photo(p) for p in photos]


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

    # 4) Upsert private "My Photos" album.
    await db.client_albums.update_one(
        {"event_id": event_id, "client_user_id": user["user_id"]},
        {"$set": {
            "event_id": event_id,
            "client_user_id": user["user_id"],
            "photo_ids": matched_photo_ids,
            "scores": {p: best[p] for p in matched_photo_ids},
            "last_searched_at": now_iso(),
        }},
        upsert=True,
    )

    photos = await _photos_with_scores(matched_photo_ids, best)
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


# ---------------------------------------------------------------------------
# Image serving (auth required; ?token= supported for web <img>)
# ---------------------------------------------------------------------------
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


@app.on_event("shutdown")
async def on_shutdown():
    client.close()
