"""Lumiere Gallery — client photo gallery with face-recognition search."""
import io
import os
import csv
import uuid
import hmac
import hashlib
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
    ADMIN_SEED_EMAIL, ADMIN_SEED_PASSWORD, SUPERADMIN_EMAIL, SUPERADMIN_PASSWORD, PUBLIC_BASE_URL,
)
from storage_service import get_storage
from phone_utils import validate_phone, PhoneValidationError, phone_variants
from face_engine import get_face_engine, NotIndexedError
import gdrive_service
from gdrive_service import DriveError
from email_service import send_otp_email
from auth_utils import (
    hash_password, verify_password, new_user_id, create_session,
    get_current_user, require_admin, require_admin_uploads, require_client, user_from_token_or_header,
)
import plans

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()
api_router = APIRouter(prefix="/api")

CATEGORIES = ["portrait", "wedding", "event"]


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


async def _assigned_event_access(event: dict, client_user: dict) -> dict | None:
    """Resolve CRM client/family assignments for any of its current contacts."""
    ors = []
    if client_user.get("email"):
        email = client_user["email"].lower()
        ors.append({"email": {"$in": [email, client_user["email"]]}})
    if client_user.get("phone"):
        ors.append({"phone": client_user["phone"]})
    if not ors:
        return None
    assignments = list(event.get("client_assignments") or [])
    # Keep older events linked with the original single client_id working.
    if event.get("client_id") and not any(a.get("client_id") == event["client_id"] for a in assignments):
        assignments.append({"client_id": event["client_id"], "full_gallery_access": True})
    for assignment in assignments:
        client_id = assignment.get("client_id")
        if not client_id:
            continue
        contact = await db.contacts.find_one(
            {"client_id": client_id, "studio_id": event.get("created_by"), "$or": ors},
            {"_id": 0, "contact_id": 1},
        )
        if contact:
            return {
                "grant_id": f"crm_assignment:{event['event_id']}:{client_id}",
                "event_id": event["event_id"],
                "client_id": client_id,
                "status": "active",
                "full_gallery_access": bool(assignment.get("full_gallery_access", False)),
                "source": "crm_assignment",
            }
    return None


async def client_grant_or_403(event_id: str, client_user: dict) -> dict:
    """Return a direct or CRM-assigned active access grant, else 403."""
    event = await get_event_or_404(event_id)
    ensure_event_available(event)
    ors = []
    if client_user.get("email"):
        ors.append({"client_email": client_user["email"].lower()})
    if client_user.get("phone"):
        ors.append({"client_phone": client_user["phone"]})
    if ors:
        grant = await db.access_grants.find_one(
            {"event_id": event_id, "status": "active", "$or": ors}, {"_id": 0}
        )
        if grant:
            return grant
    assigned = await _assigned_event_access(event, client_user)
    if assigned:
        return assigned
    raise HTTPException(status_code=403, detail="No access to this gallery")


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
        "face_search_enabled": event.get("face_search_enabled", True),
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
        "client_id": event.get("client_id"),
        "value": event.get("value", 0) or 0,
        "created_at": event.get("created_at"),
    }


def share_url_for(event_id: str) -> str:
    base = PUBLIC_BASE_URL or ""
    return f"{base}/g/{event_id}"


def _phone_or_400(value: str) -> str:
    try:
        return validate_phone(value)
    except PhoneValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    role: Optional[str] = "admin"


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
        **plans.new_studio_plan_fields(),
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


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str


@api_router.post("/auth/admin/forgot-password")
async def admin_forgot_password(body: ForgotPasswordRequest):
    """Send a 6-digit reset code to the studio-admin email.

    Behaviour is intentionally identical for known/unknown emails so we never
    leak account existence. The code is stored in `otp_codes` (identifier
    prefixed with `pwreset:` to keep it separate from client OTPs) and expires
    in 15 minutes.
    """
    email = body.email.lower().strip()
    identifier = f"pwreset:{email}"
    code = gen_otp()

    user = await db.users.find_one({"email": email, "role": "admin"})
    delivered = False
    if user:
        await db.otp_codes.update_one(
            {"identifier": identifier},
            {"$set": {
                "identifier": identifier,
                "channel": "email",
                "code": code,
                "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
                "attempts": 0,
                "created_at": now_iso(),
            }},
            upsert=True,
        )
        try:
            await send_otp_email(email, code)
            delivered = True
        except Exception as e:
            logger.error(f"Password-reset email send failed: {e}")

    resp = {"status": "sent", "delivered": delivered}
    # In dev/preview mode we surface the code so it can be tested without inbox
    # access. Never enable OTP_DEV_MODE in production.
    if OTP_DEV_MODE and user:
        resp["dev_code"] = code
    return resp


@api_router.post("/auth/admin/reset-password")
async def admin_reset_password(body: ResetPasswordRequest):
    email = body.email.lower().strip()
    identifier = f"pwreset:{email}"

    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    record = await db.otp_codes.find_one({"identifier": identifier})
    if not record:
        raise HTTPException(status_code=400, detail="Request a reset code first")
    expires_at = record["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Code expired. Request a new one.")
    if record.get("attempts", 0) >= 5:
        raise HTTPException(status_code=429, detail="Too many attempts. Request a new code.")
    if body.code.strip() != record["code"]:
        await db.otp_codes.update_one({"identifier": identifier}, {"$inc": {"attempts": 1}})
        raise HTTPException(status_code=401, detail="Incorrect code")

    user = await db.users.find_one({"email": email, "role": "admin"})
    if not user:
        # code matched but user is gone — clean up
        await db.otp_codes.delete_one({"identifier": identifier})
        raise HTTPException(status_code=404, detail="Account not found")

    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"password_hash": hash_password(body.new_password), "auth_provider": "password"}},
    )
    await db.otp_codes.delete_one({"identifier": identifier})

    # Auto sign-in on successful reset
    token = await create_session(user["user_id"])
    return {"status": "reset", "session_token": token, "user": _public_user(user)}


@api_router.post("/auth/session")
async def google_session(body: SessionExchange):
    """Exchange an Emergent Google OAuth session_id for a session token.
    The `role` intent decides what a NEW account becomes: "client" for the
    guest login, "admin" (default) for the studio login. Existing accounts are
    reused by email regardless of intent."""
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
        name = data.get("name") or email.split("@")[0]
        if body.role == "client":
            user = {
                "user_id": new_user_id(),
                "role": "client",
                "name": name,
                "email": email,
                "phone": None,
                "password_hash": None,
                "picture": data.get("picture"),
                "auth_provider": "google",
                "verified_email": True,
                "verified_phone": False,
                "created_at": now_iso(),
            }
        else:
            user = {
                "user_id": new_user_id(),
                "role": "admin",
                "name": name,
                "email": email,
                "phone": None,
                "password_hash": None,
                "picture": data.get("picture"),
                "auth_provider": "google",
                "created_at": now_iso(),
                **plans.new_studio_plan_fields(),
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
        identifier = _phone_or_400(body.phone)
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
        identifier = _phone_or_400(body.phone or "")
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

    query = {"email": identifier} if body.channel == "email" else {"phone": {"$in": phone_variants(identifier)}}
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
            "verified_email": body.channel == "email",
            "verified_phone": body.channel == "phone",
            "created_at": now_iso(),
        }
        await db.users.insert_one(user)
    else:
        if user.get("role") != "client":
            raise HTTPException(status_code=403, detail="This contact belongs to a studio account")
        verified_field = "verified_email" if body.channel == "email" else "verified_phone"
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {verified_field: True}})
        if body.name and body.name.strip() and body.name.strip() != user.get("name"):
            user["name"] = body.name.strip()
            await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"name": user["name"]}})

    token = await create_session(user["user_id"])
    return {"session_token": token, "user": _public_user(user)}


@api_router.get("/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return {"user": user}


@api_router.post("/auth/logout")
async def logout(user: dict = Depends(get_current_user)):
    return {"status": "ok"}


class StudioProfile(BaseModel):
    contact_name: str
    studio_name: str
    phone: str
    purposes: list[str] = Field(default_factory=list, max_length=3)
    # Legacy clients may still send a single purpose; normalize it below.
    purpose: Optional[str] = None
    city: str
    country: str
    website: Optional[str] = None
    team_size: Optional[str] = None
    galleries_per_month: Optional[str] = None
    referral_source: Optional[str] = None


@api_router.post("/auth/admin/profile")
async def save_studio_profile(body: StudioProfile, user: dict = Depends(get_current_user)):
    """Complete the studio profile before granting access to the dashboard."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="A studio account is required")
    selected_purposes = [p.strip() for p in body.purposes if p and p.strip()]
    if not selected_purposes and body.purpose and body.purpose.strip():
        selected_purposes = [body.purpose.strip()]
    if len(selected_purposes) > 3:
        raise HTTPException(status_code=400, detail="Please select up to 3 photography types")
    if len({p.casefold() for p in selected_purposes}) != len(selected_purposes):
        raise HTTPException(status_code=400, detail="Please select each photography type only once")
    required = {
        "contact name": body.contact_name,
        "studio name": body.studio_name,
        "phone": body.phone,
        "photography type": selected_purposes,
        "city": body.city,
        "country": body.country,
    }
    missing = [
        label for label, value in required.items()
        if not value or (isinstance(value, str) and not value.strip())
    ]
    if missing:
        raise HTTPException(status_code=400, detail="Please complete all required fields")
    phone = _phone_or_400(body.phone)
    profile = {
        "contact_name": body.contact_name.strip(),
        "studio_name": body.studio_name.strip(),
        "phone": phone,
        "purposes": selected_purposes,
        # Keep the first selection for older consumers of studio_profile.purpose.
        "purpose": selected_purposes[0],
        "city": body.city.strip(),
        "country": body.country.strip(),
        "website": (body.website or "").strip() or None,
        "team_size": (body.team_size or "").strip() or None,
        "galleries_per_month": (body.galleries_per_month or "").strip() or None,
        "referral_source": (body.referral_source or "").strip() or None,
        "updated_at": now_iso(),
    }
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {
            "studio_profile": profile,
            "profile_complete": True,
            "name": profile["studio_name"],
            "phone": profile["phone"],
        }},
    )
    updated = await db.users.find_one({"user_id": user["user_id"]})
    return {"user": _public_user(updated)}


def _public_user(user: dict) -> dict:
    return {
        "user_id": user["user_id"],
        "role": user["role"],
        "name": user.get("name"),
        "email": user.get("email"),
        "phone": user.get("phone"),
        "picture": user.get("picture"),
        "profile_complete": bool(user.get("profile_complete")),
        "studio_profile": user.get("studio_profile"),
        "plan": user.get("plan"),
        "plan_expires_at": user.get("plan_expires_at"),
    }


@api_router.get("/billing/status")
async def billing_status_endpoint(admin: dict = Depends(require_admin)):
    """Current plan, quota limits, live usage and days left for the studio."""
    return await plans.billing_status(admin)


# ---------------------------------------------------------------------------
# Payments — Razorpay (mock now, real contract preserved for later)
# ---------------------------------------------------------------------------
PLAN_PRICING = {
    "standard": {"amount": 49900, "name": "Standard"},
    "pro": {"amount": 99900, "name": "Pro"},
}
RAZORPAY_MODE = os.environ.get("RAZORPAY_MODE", "mock")
RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "")


def _is_mock() -> bool:
    return RAZORPAY_MODE == "mock" or not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET


class CreateOrderIn(BaseModel):
    plan: str  # standard | pro


class VerifyIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class MockCompleteIn(BaseModel):
    order_id: str


async def _activate_plan(studio_id: str, plan_key: str, order_id: str, payment_id: str) -> None:
    fields = plans.apply_subscription_fields(plan_key)
    await db.users.update_one({"user_id": studio_id}, {"$set": fields})
    await db.payments.update_one(
        {"order_id": order_id},
        {"$set": {"status": "paid", "payment_id": payment_id, "verified_at": now_iso()}},
    )


@api_router.post("/payments/create-order")
async def create_order(body: CreateOrderIn, admin: dict = Depends(require_admin)):
    if body.plan not in PLAN_PRICING:
        raise HTTPException(status_code=400, detail="Invalid plan")
    plan = PLAN_PRICING[body.plan]
    local_id = uuid.uuid4().hex
    mock = _is_mock()
    if mock:
        order_id = f"mock_order_{local_id}"
        public_key = "mock_key_id"
    else:
        async with httpx.AsyncClient(timeout=15) as hc:
            r = await hc.post(
                "https://api.razorpay.com/v1/orders",
                auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
                json={"amount": plan["amount"], "currency": "INR", "receipt": f"rcpt_{local_id[:24]}",
                      "notes": {"plan": body.plan, "studio_id": admin["user_id"]}, "payment_capture": 1},
            )
        if r.status_code >= 400:
            raise HTTPException(status_code=502, detail="Could not start payment. Please try again.")
        order_id = r.json()["id"]
        public_key = RAZORPAY_KEY_ID
    await db.payments.insert_one({
        "local_id": local_id, "order_id": order_id, "studio_id": admin["user_id"],
        "plan": body.plan, "amount": plan["amount"], "currency": "INR",
        "status": "created", "mock": mock, "created_at": now_iso(),
    })
    return {"local_id": local_id, "order_id": order_id, "amount": plan["amount"],
            "currency": "INR", "plan": body.plan, "key_id": public_key, "mock": mock}


@api_router.post("/payments/mock-complete")
async def mock_complete(body: MockCompleteIn, admin: dict = Depends(require_admin)):
    """Test-only: activate the plan for a mock order (no real Razorpay keys yet)."""
    if not _is_mock():
        raise HTTPException(status_code=400, detail="Mock completion is disabled in live mode")
    record = await db.payments.find_one({"order_id": body.order_id, "studio_id": admin["user_id"]})
    if not record:
        raise HTTPException(status_code=404, detail="Unknown order")
    await _activate_plan(admin["user_id"], record["plan"], body.order_id, f"mock_pay_{uuid.uuid4().hex[:12]}")
    fresh = await db.users.find_one({"user_id": admin["user_id"]}, {"_id": 0, "password_hash": 0})
    return await plans.billing_status(fresh)


@api_router.post("/payments/verify")
async def verify_payment(body: VerifyIn, admin: dict = Depends(require_admin)):
    """Real Razorpay callback verification (used once live keys are configured)."""
    record = await db.payments.find_one({"order_id": body.razorpay_order_id, "studio_id": admin["user_id"]})
    if not record:
        raise HTTPException(status_code=404, detail="Unknown order")
    if _is_mock():
        raise HTTPException(status_code=400, detail="Use mock-complete in mock mode")
    message = f"{body.razorpay_order_id}|{body.razorpay_payment_id}".encode()
    expected = hmac.new(RAZORPAY_KEY_SECRET.encode(), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, body.razorpay_signature):
        raise HTTPException(status_code=400, detail="Invalid payment signature")
    await _activate_plan(admin["user_id"], record["plan"], body.razorpay_order_id, body.razorpay_payment_id)
    fresh = await db.users.find_one({"user_id": admin["user_id"]}, {"_id": 0, "password_hash": 0})
    return await plans.billing_status(fresh)


# ---------------------------------------------------------------------------
# Admin — events, photos, indexing, access, face-data
# ---------------------------------------------------------------------------
class EventCreate(BaseModel):
    name: str
    date: Optional[str] = None
    category: str = "event"
    photographer: Optional[str] = None
    similarity_threshold: Optional[float] = None
    face_search_enabled: bool = True
    client_id: Optional[str] = None  # optional link to a CRM client/family
    value: Optional[float] = None    # booking value (for lifetime-value stats)


class EventUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[str] = None
    category: Optional[str] = None
    photographer: Optional[str] = None
    similarity_threshold: Optional[float] = None
    share_enabled: Optional[bool] = None
    client_id: Optional[str] = None
    value: Optional[float] = None


class AccessGrantCreate(BaseModel):
    channel: str  # email | phone
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    full_gallery_access: bool = False


class EventClientAssignmentCreate(BaseModel):
    client_id: str
    full_gallery_access: bool = True


@api_router.post("/events")
async def create_event(body: EventCreate, admin: dict = Depends(require_admin)):
    if body.category not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Category must be one of {CATEGORIES}")
    await plans.check_can_create_gallery(admin)
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    engine = get_face_engine()
    collection_id = engine.create_collection(event_id) if body.face_search_enabled else None
    threshold = body.similarity_threshold or DEFAULT_SIMILARITY_THRESHOLD
    event = {
        "event_id": event_id,
        "name": body.name,
        "date": body.date,
        "category": body.category,
        "photographer": body.photographer,
        "similarity_threshold": threshold,
        "face_search_enabled": body.face_search_enabled,
        "collection_id": collection_id,
        "indexing_status": "empty",
        "photo_count": 0,
        "cover_path": None,
        "share_enabled": True,
        "client_id": body.client_id,
        "client_assignments": ([{
            "client_id": body.client_id,
            "full_gallery_access": True,
            "assigned_by": admin["user_id"],
            "assigned_at": now_iso(),
        }] if body.client_id else []),
        "value": body.value or 0,
        "created_by": admin["user_id"],
        "created_at": now_iso(),
    }
    await db.events.insert_one(event)
    await plans.increment_usage(admin["user_id"], "galleries_created", 1)
    return public_event(event)


class GDriveEventCreate(BaseModel):
    name: str
    date: Optional[str] = None
    category: str = "event"
    photographer: Optional[str] = None
    similarity_threshold: Optional[float] = None
    face_search_enabled: bool = True
    drive_link: str


async def _sync_gdrive_event(event: dict, images: Optional[list] = None) -> dict:
    """Re-scan the Drive folder: add new images, re-index changed ones, remove
    deleted ones. Only metadata + web previews are used — no originals copied."""
    event_id = event["event_id"]
    folder_id = event["drive_folder_id"]
    if images is None:
        images = await run_in_threadpool(gdrive_service.list_folder_images, folder_id)

    existing: dict[str, dict] = {}
    async for photo in db.photos.find({"event_id": event_id, "source": "gdrive"}, {"_id": 0}).batch_size(500):
        if photo.get("drive_file_id"):
            existing[photo["drive_file_id"]] = photo
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
                "indexing_status": "pending" if event.get("face_search_enabled", True) else "disabled",
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
                    "indexing_status": "pending" if event.get("face_search_enabled", True) else "disabled",
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
async def create_gdrive_event(body: GDriveEventCreate, admin: dict = Depends(require_admin_uploads)):
    """Create a gallery from a public Google Drive folder link. Originals stay
    on Drive; we index web previews for face search."""
    if body.category not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Category must be one of {CATEGORIES}")
    await plans.check_can_create_gdrive(admin)
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
    collection_id = engine.create_collection(event_id) if body.face_search_enabled else None
    event = {
        "event_id": event_id,
        "name": body.name,
        "date": body.date,
        "category": body.category,
        "photographer": body.photographer,
        "similarity_threshold": body.similarity_threshold or DEFAULT_SIMILARITY_THRESHOLD,
        "face_search_enabled": body.face_search_enabled,
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
    await plans.increment_usage(admin["user_id"], "gdrive_created", 1)
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


@api_router.post("/events/{event_id}/cover")
async def upload_event_cover(
    event_id: str,
    file: UploadFile = File(...),
    admin: dict = Depends(require_admin_uploads),
):
    event = await admin_event_or_404(event_id, admin)
    content_type = file.content_type or "image/jpeg"
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Gallery cover must be an image")
    content = await file.read()
    if not content or len(content) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Gallery cover must be between 1 byte and 15 MB")
    try:
        with Image.open(io.BytesIO(content)) as image:
            image.verify()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="The selected gallery cover is not a valid image") from exc

    extension = (file.filename or "cover.jpg").rsplit(".", 1)[-1].lower()
    if extension not in {"jpg", "jpeg", "png", "webp"}:
        extension = "jpg"
    cover_path = f"events/{event_id}/cover/cover_{uuid.uuid4().hex[:10]}.{extension}"
    storage = get_storage()
    await run_in_threadpool(storage.delete_prefix, f"events/{event_id}/cover")
    await run_in_threadpool(storage.put_object, cover_path, content, content_type)
    await db.events.update_one({"event_id": event_id}, {"$set": {"cover_path": cover_path, "cover_custom": True}})
    return public_event(await get_event_or_404(event_id))


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
    if not event.get("face_search_enabled", True):
        return {"status": "disabled", "photos": await db.photos.count_documents({"event_id": event_id}), "faces_indexed": 0}
    engine = get_face_engine()
    storage = get_storage()
    cid = event["collection_id"]

    # Fresh collection.
    await run_in_threadpool(engine.delete_collection, cid)
    await run_in_threadpool(engine.ensure_collection, cid)

    photos_cursor = db.photos.find({"event_id": event_id}, {"_id": 0}).batch_size(500)
    await db.faces.delete_many({"event_id": event_id})

    total_faces = 0
    photo_count = 0
    async for p in photos_cursor:
        photo_count += 1
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
    await db.events.update_one({"event_id": event_id}, {"$set": {"indexing_status": "ready" if photo_count else "empty"}})
    return {"status": "reindexed", "photos": photo_count, "faces_indexed": total_faces}


@api_router.post("/events/{event_id}/archive")
async def archive_event(event_id: str, admin: dict = Depends(require_admin)):
    """Take a gallery offline. Clients/public can no longer view it (they are
    asked to contact the photographer) until it is restored."""
    await admin_event_or_404(event_id, admin)
    await db.events.update_one({"event_id": event_id}, {"$set": {"status": "archived"}})
    grants = await db.access_grants.find({"event_id": event_id, "status": "active"}, {"_id": 0}).to_list(2000)
    for grant in grants:
        lookup = []
        if grant.get("client_email"):
            lookup.append({"email": grant["client_email"].lower()})
        if grant.get("client_phone"):
            lookup.append({"phone": grant["client_phone"]})
        users = await db.users.find({"role": "client", "$or": lookup}, {"_id": 0, "user_id": 1}).to_list(20) if lookup else []
        for client_user in users:
            await db.notifications.insert_one({
                "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
                "client_user_id": client_user["user_id"],
                "type": "gallery_expiry",
                "title": "Gallery notice",
                "body": "This gallery has been archived by the studio.",
                "event_id": event_id,
                "read": False,
                "created_at": now_iso(),
            })
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
        "bytes": len(data),
        "width": w,
        "height": h,
        "face_count": 0,
        "indexing_status": "pending" if event.get("face_search_enabled", True) else "disabled",
        "uploaded_at": now_iso(),
    }
    await db.photos.insert_one(photo)

    set_fields = {"indexing_status": "indexing" if event.get("face_search_enabled", True) else "disabled"}
    if not event.get("cover_path"):
        set_fields["cover_path"] = thumb_path
        event["cover_path"] = thumb_path  # so subsequent imports in a loop don't reset
    await db.events.update_one({"event_id": event_id}, {"$inc": {"photo_count": 1}, "$set": set_fields})
    if event.get("face_search_enabled", True):
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
    event = await db.events.find_one({"event_id": event_id}, {"_id": 0, "face_search_enabled": 1})
    if event and not event.get("face_search_enabled", True):
        await db.events.update_one({"event_id": event_id}, {"$set": {"indexing_status": "disabled"}})
        return
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
async def upload_photo(event_id: str, file: UploadFile = File(...), admin: dict = Depends(require_admin_uploads)):
    event = await admin_event_or_404(event_id, admin)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    await plans.check_can_upload_images(admin, 1, len(data))
    try:
        photo = await _ingest_photo(event, data, file.filename or "photo.jpg", file.content_type or "image/jpeg")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Unsupported or corrupt image")
    await plans.increment_usage(admin["user_id"], "images_uploaded", 1)
    return public_photo(photo)


@api_router.post("/events/{event_id}/photos/bulk")
async def upload_photos_bulk(event_id: str, files: list[UploadFile] = File(...),
                             admin: dict = Depends(require_admin_uploads)):
    """Store many photos in a single request; face indexing is queued in the
    background. Returns per-file results so the client can drive a progress bar."""
    event = await admin_event_or_404(event_id, admin)
    await plans.ensure_plan(admin)
    plans._assert_active(admin)
    limits = plans.plan_limits(admin)
    img_lim = limits["images"]
    store_lim = limits["storage_bytes"]
    images_used = int((admin.get("usage") or {}).get("images_uploaded", 0))
    storage_used = await plans.storage_bytes_for(admin["user_id"])
    results = []
    uploaded = 0
    quota_hit = None
    for f in files:
        try:
            data = await f.read()
            if not data:
                results.append({"filename": f.filename, "ok": False, "error": "empty"})
                continue
            if img_lim is not None and images_used + uploaded + 1 > img_lim:
                quota_hit = f"Image limit reached ({img_lim})"
                results.append({"filename": f.filename, "ok": False, "error": "quota"})
                continue
            if store_lim is not None and storage_used + len(data) > store_lim:
                quota_hit = "Storage limit reached for your plan"
                results.append({"filename": f.filename, "ok": False, "error": "quota"})
                continue
            photo = await _ingest_photo(event, data, f.filename or "photo.jpg", f.content_type or "image/jpeg")
            uploaded += 1
            storage_used += len(data)
            results.append({"filename": f.filename, "ok": True, "photo_id": photo["photo_id"]})
        except Exception as e:
            logger.error(f"bulk upload {getattr(f, 'filename', '?')} failed: {e}")
            results.append({"filename": getattr(f, "filename", None), "ok": False, "error": "unsupported"})
    if uploaded:
        await plans.increment_usage(admin["user_id"], "images_uploaded", uploaded)
    return {"uploaded": uploaded, "received": len(files), "results": results, "quota_hit": quota_hit}


class S3ImportBody(BaseModel):
    bucket: Optional[str] = None
    prefix: Optional[str] = ""
    max_files: int = 200


@api_router.post("/events/{event_id}/import-s3")
async def import_from_s3(event_id: str, body: S3ImportBody, admin: dict = Depends(require_admin_uploads)):
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
        phone = _phone_or_400(body.phone or "")
        key = {"event_id": event_id, "client_phone": phone}
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


async def _access_grants_with_crm_names(grants: list[dict], studio_id: str) -> list[dict]:
    """Enrich direct email/phone grants with the matching CRM client name."""
    out = []
    for grant in grants:
        row = dict(grant)
        ors = []
        if grant.get("client_email"):
            email = grant["client_email"].lower()
            ors.append({"email": {"$in": [email, grant["client_email"]]}})
        if grant.get("client_phone"):
            ors.append({"phone": grant["client_phone"]})
        if ors:
            contact = await db.contacts.find_one(
                {"studio_id": studio_id, "$or": ors},
                {"_id": 0, "client_id": 1, "name": 1},
            )
            if contact:
                client = await db.clients.find_one(
                    {"client_id": contact["client_id"], "studio_id": studio_id},
                    {"_id": 0, "name": 1},
                )
                if client:
                    row["client_id"] = contact["client_id"]
                    row["client_name"] = client.get("name")
                    row["contact_name"] = contact.get("name")
        out.append(row)
    return out

@api_router.get("/events/{event_id}/access")
async def list_access(event_id: str, admin: dict = Depends(require_admin)):
    await admin_event_or_404(event_id, admin)
    grants = await db.access_grants.find({"event_id": event_id}, {"_id": 0}).to_list(2000)
    return await _access_grants_with_crm_names(grants, admin["user_id"])


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


async def _event_assignment_rows(event: dict, admin: dict) -> list[dict]:
    assignments = list(event.get("client_assignments") or [])
    if event.get("client_id") and not any(a.get("client_id") == event["client_id"] for a in assignments):
        assignments.insert(0, {"client_id": event["client_id"], "full_gallery_access": True})
    rows = []
    for assignment in assignments:
        client_id = assignment.get("client_id")
        client = await db.clients.find_one(
            {"client_id": client_id, "studio_id": admin["user_id"]}, {"_id": 0, "name": 1}
        )
        if not client:
            continue
        contact_count = await db.contacts.count_documents({"client_id": client_id, "studio_id": admin["user_id"]})
        rows.append({
            "client_id": client_id,
            "client_name": client.get("name"),
            "contact_count": contact_count,
            "full_gallery_access": bool(assignment.get("full_gallery_access", True)),
            "assigned_at": assignment.get("assigned_at"),
        })
    return rows


@api_router.get("/events/{event_id}/client-assignments")
async def list_event_client_assignments(event_id: str, admin: dict = Depends(require_admin)):
    event = await admin_event_or_404(event_id, admin)
    return await _event_assignment_rows(event, admin)


@api_router.post("/events/{event_id}/client-assignments")
async def assign_event_client(event_id: str, body: EventClientAssignmentCreate,
                              admin: dict = Depends(require_admin)):
    event = await admin_event_or_404(event_id, admin)
    client = await db.clients.find_one(
        {"client_id": body.client_id, "studio_id": admin["user_id"]}, {"_id": 0, "client_id": 1}
    )
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    assignments = [a for a in (event.get("client_assignments") or []) if a.get("client_id") != body.client_id]
    assignments.append({
        "client_id": body.client_id,
        "full_gallery_access": body.full_gallery_access,
        "assigned_by": admin["user_id"],
        "assigned_at": now_iso(),
    })
    updates = {"client_assignments": assignments}
    if not event.get("client_id"):
        updates["client_id"] = body.client_id
    await db.events.update_one({"event_id": event_id}, {"$set": updates})
    fresh = await get_event_or_404(event_id)
    return {"status": "assigned", "event_id": event_id, "assignments": await _event_assignment_rows(fresh, admin)}


@api_router.delete("/events/{event_id}/client-assignments/{client_id}")
async def remove_event_client_assignment(event_id: str, client_id: str,
                                         admin: dict = Depends(require_admin)):
    event = await admin_event_or_404(event_id, admin)
    assignments = [a for a in (event.get("client_assignments") or []) if a.get("client_id") != client_id]
    updates = {"client_assignments": assignments}
    if event.get("client_id") == client_id:
        if assignments:
            updates["client_id"] = assignments[0].get("client_id")
        else:
            await db.events.update_one({"event_id": event_id}, {"$set": updates, "$unset": {"client_id": ""}})
            return {"status": "unassigned", "event_id": event_id, "client_id": client_id}
    await db.events.update_one({"event_id": event_id}, {"$set": updates})
    return {"status": "unassigned", "event_id": event_id, "client_id": client_id}



@api_router.get("/events/{event_id}/clients")
async def list_event_clients(event_id: str, admin: dict = Depends(require_admin)):
    await admin_event_or_404(event_id, admin)
    albums = await db.client_albums.find({"event_id": event_id}, {"_id": 0}).to_list(2000)
    visitors = await db.gallery_visitors.find({"event_id": event_id}, {"_id": 0}).to_list(5000)
    likes = await db.photo_likes.find({"event_id": event_id}, {"_id": 0, "client_user_id": 1, "created_at": 1}).to_list(20000)
    album_by_user = {a["client_user_id"]: a for a in albums if a.get("client_user_id")}
    visitor_by_user: dict[str, list[dict]] = {}
    for visitor in visitors:
        if visitor.get("client_user_id"):
            visitor_by_user.setdefault(visitor["client_user_id"], []).append(visitor)
    likes_by_user: dict[str, list[dict]] = {}
    for like in likes:
        if like.get("client_user_id"):
            likes_by_user.setdefault(like["client_user_id"], []).append(like)
    client_ids = set(album_by_user) | set(visitor_by_user) | set(likes_by_user)
    out = []
    for client_user_id in client_ids:
        u = await db.users.find_one({"user_id": client_user_id}, {"_id": 0, "password_hash": 0})
        user_visitors = visitor_by_user.get(client_user_id, [])
        user_likes = likes_by_user.get(client_user_id, [])
        album = album_by_user.get(client_user_id) or {}
        activity_dates = [v.get("last_seen_at") or v.get("created_at") for v in user_visitors]
        activity_dates.extend(l.get("created_at") for l in user_likes)
        activity_dates = [d for d in activity_dates if d]
        out.append({
            "client_user_id": client_user_id,
            "name": u.get("name") if u else (user_visitors[0].get("name") if user_visitors else None),
            "email": u.get("email") if u else None,
            "phone": u.get("phone") if u else (user_visitors[0].get("phone") if user_visitors else None),
            "matched_count": len(album.get("photo_ids", [])),
            "liked_count": len(user_likes),
            "activity_count": len(user_visitors) + len(user_likes),
            "last_activity_at": max(activity_dates) if activity_dates else None,
            "last_searched_at": album.get("last_searched_at"),
        })
    return sorted(out, key=lambda row: row.get("last_activity_at") or "", reverse=True)


@api_router.delete("/events/{event_id}/clients/{client_user_id}/face-data")
async def delete_client_face_data(event_id: str, client_user_id: str, admin: dict = Depends(require_admin)):
    """Remove all gallery-specific data for this client.

    Face signatures, matched albums, likes, visitors, access grants, consent
    records, and gallery shares are removed. The global client account is not
    deleted because it may be used by another studio or gallery.
    """
    event = await admin_event_or_404(event_id, admin)
    u = await db.users.find_one({"user_id": client_user_id}, {"_id": 0, "email": 1, "phone": 1})
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
    await db.photo_likes.delete_many({"event_id": event_id, "client_user_id": client_user_id})
    await db.gallery_visitors.delete_many({"event_id": event_id, "client_user_id": client_user_id})
    await db.gallery_shares.delete_many({"event_id": event_id, "client_user_id": client_user_id})
    grant_or = [{"client_phone": {"$in": phone_variants(u["phone"])}}] if u and u.get("phone") else []
    if u and u.get("email"):
        grant_or.append({"client_email": u["email"].lower()})
    if grant_or:
        await db.access_grants.delete_many({"event_id": event_id, "$or": grant_or})
    return {"status": "deleted", "faces_removed": deleted_faces, "gallery_data_removed": True}


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



class ClientProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=120)
    gender: Optional[str] = Field(default=None, max_length=40)
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    city: Optional[str] = Field(default=None, max_length=120)
    dob: Optional[str] = Field(default=None, max_length=10)
    profile_photo_base64: Optional[str] = Field(default=None, max_length=4_000_000)
    profession: Optional[str] = Field(default=None, max_length=120)
    company: Optional[str] = Field(default=None, max_length=160)
    about: Optional[str] = Field(default=None, max_length=1000)
    instagram: Optional[str] = Field(default=None, max_length=160)
    website: Optional[str] = Field(default=None, max_length=240)


class ClientContactOtpRequest(BaseModel):
    channel: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None


class ClientContactOtpVerify(BaseModel):
    channel: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    code: str = Field(min_length=4, max_length=8)


def _client_profile_public(user: dict) -> dict:
    profile = dict(user.get("client_profile") or {})
    profile.update({
        "user_id": user.get("user_id"),
        "email": user.get("email"),
        "phone": user.get("phone"),
        "verified_email": bool(user.get("email") and user.get("verified_email", True)),
        "verified_phone": bool(user.get("phone") and user.get("verified_phone", True)),
    })
    return profile


@api_router.get("/client/profile")
async def get_client_profile(user: dict = Depends(require_client)):
    fresh = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password_hash": 0})
    return _client_profile_public(fresh or user)


@api_router.post("/client/profile/request-otp")
async def request_client_profile_otp(body: ClientContactOtpRequest, user: dict = Depends(require_client)):
    if body.channel == "email":
        if not body.email:
            raise HTTPException(status_code=400, detail="Email is required")
        identifier = body.email.lower()
        conflict = await db.users.find_one({"email": identifier, "user_id": {"$ne": user["user_id"]}})
    elif body.channel == "phone":
        if not body.phone:
            raise HTTPException(status_code=400, detail="Phone number is required")
        identifier = _phone_or_400(body.phone)
        conflict = await db.users.find_one({"phone": {"$in": phone_variants(identifier)}, "user_id": {"$ne": user["user_id"]}})
    else:
        raise HTTPException(status_code=400, detail="Invalid channel")
    if conflict:
        raise HTTPException(status_code=409, detail="That contact is already linked to another account")

    code = gen_otp()
    key = f"profile:{user['user_id']}:{body.channel}:{identifier}"
    await db.otp_codes.update_one(
        {"identifier": key},
        {"$set": {
            "identifier": key,
            "channel": body.channel,
            "target": identifier,
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
            logger.error(f"Profile OTP email send failed: {e}")
    else:
        logger.info(f"[SMS:{SMS_PROVIDER}] Profile OTP for {identifier}: {code}")
    response = {"status": "sent", "channel": body.channel, "delivered": delivered}
    if OTP_DEV_MODE:
        response["dev_code"] = code
    return response


@api_router.post("/client/profile/verify-otp")
async def verify_client_profile_otp(body: ClientContactOtpVerify, user: dict = Depends(require_client)):
    if body.channel == "email":
        if not body.email:
            raise HTTPException(status_code=400, detail="Email is required")
        identifier = body.email.lower()
    elif body.channel == "phone":
        identifier = _phone_or_400(body.phone or "")
    else:
        raise HTTPException(status_code=400, detail="Invalid channel")
    key = f"profile:{user['user_id']}:{body.channel}:{identifier}"
    record = await db.otp_codes.find_one({"identifier": key})
    if not record:
        raise HTTPException(status_code=400, detail="Request a code first")
    expires_at = record.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Code expired. Request a new one.")
    if record.get("attempts", 0) >= 5:
        raise HTTPException(status_code=429, detail="Too many attempts. Request a new code.")
    if body.code != record.get("code"):
        await db.otp_codes.update_one({"identifier": key}, {"$inc": {"attempts": 1}})
        raise HTTPException(status_code=401, detail="Incorrect code")

    await db.otp_codes.delete_one({"identifier": key})
    if body.channel == "email":
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"email": identifier, "verified_email": True}},
        )
    else:
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"phone": identifier, "verified_phone": True}},
        )
    fresh = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password_hash": 0})
    return _client_profile_public(fresh or user)


@api_router.patch("/client/profile")
async def update_client_profile(body: ClientProfileUpdate, user: dict = Depends(require_client)):
    fresh = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password_hash": 0}) or user
    existing = fresh.get("client_profile") or {}
    email = (str(body.email).lower() if body.email is not None else fresh.get("email"))
    phone = body.phone if body.phone is not None else fresh.get("phone")
    full_name = (body.full_name if body.full_name is not None else existing.get("full_name")) or ""
    gender = (body.gender if body.gender is not None else existing.get("gender")) or ""
    city = (body.city if body.city is not None else existing.get("city")) or ""
    dob = (body.dob if body.dob is not None else existing.get("dob")) or ""
    if not full_name.strip() or not gender.strip() or not city.strip() or not dob.strip():
        raise HTTPException(status_code=400, detail="Full name, gender, city, and date of birth are required")
    if gender not in {"Male", "Female", "Non-binary", "Prefer not to say"}:
        raise HTTPException(status_code=400, detail="Please select a valid gender")
    try:
        parsed_dob = datetime.strptime(dob.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Date of birth must use YYYY-MM-DD") from exc
    if parsed_dob > datetime.now(timezone.utc).date():
        raise HTTPException(status_code=400, detail="Date of birth cannot be in the future")
    if not email or not fresh.get("verified_email", bool(fresh.get("email"))):
        raise HTTPException(status_code=400, detail="Please verify your email address first")
    if not phone or not fresh.get("verified_phone", bool(fresh.get("phone"))):
        raise HTTPException(status_code=400, detail="Please verify your mobile number first")
    canonical_phone = _phone_or_400(phone)
    if fresh.get("email") != email or fresh.get("phone") != canonical_phone:
        raise HTTPException(status_code=400, detail="Verify the email and mobile number shown in your profile")

    profile = {
        "full_name": full_name.strip(),
        "gender": gender,
        "city": city.strip(),
        "dob": dob.strip(),
        "profile_photo_base64": body.profile_photo_base64 if body.profile_photo_base64 is not None else existing.get("profile_photo_base64"),
        "profession": (body.profession if body.profession is not None else existing.get("profession") or "").strip(),
        "company": (body.company if body.company is not None else existing.get("company") or "").strip(),
        "about": (body.about if body.about is not None else existing.get("about") or "").strip(),
        "instagram": (body.instagram if body.instagram is not None else existing.get("instagram") or "").strip(),
        "website": (body.website if body.website is not None else existing.get("website") or "").strip(),
        "updated_at": now_iso(),
    }
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {
            "name": profile["full_name"],
            "client_profile": profile,
            "profile_complete": True,
        }},
    )
    updated = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "password_hash": 0})
    return _client_profile_public(updated or user)


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
    by_event: dict[str, dict] = {g["event_id"]: g for g in grants}

    # A CRM assignment grants the same gallery access to every matching contact,
    # including contacts added after the assignment was made.
    contact_ors = []
    if user.get("email"):
        contact_ors.append({"email": {"$in": [user["email"].lower(), user["email"]]}})
    if user.get("phone"):
        contact_ors.append({"phone": user["phone"]})
    family_ids = []
    if contact_ors:
        contacts = await db.contacts.find({"$or": contact_ors}, {"_id": 0, "client_id": 1}).to_list(2000)
        family_ids = list({c["client_id"] for c in contacts})
    if family_ids:
        assigned_events = await db.events.find(
            {"$or": [
                {"client_assignments.client_id": {"$in": family_ids}},
                {"client_id": {"$in": family_ids}},
            ]},
            {"_id": 0},
        ).to_list(2000)
        for event in assigned_events:
            assignment = await _assigned_event_access(event, user)
            if assignment:
                current = by_event.get(event["event_id"])
                if not current or assignment.get("full_gallery_access"):
                    by_event[event["event_id"]] = assignment

    out = []
    for event_id, grant in by_event.items():
        event = await db.events.find_one({"event_id": event_id}, {"_id": 0})
        if not event or event.get("status") == "archived":
            continue
        album = await db.client_albums.find_one(
            {"event_id": event_id, "client_user_id": user["user_id"]}, {"_id": 0}
        )
        pe = public_event(event)
        pe["full_gallery_access"] = grant.get("full_gallery_access", False)
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
    if not event.get("face_search_enabled", True):
        raise HTTPException(status_code=403, detail="Face search is disabled for this gallery. Browse All Photos instead.")

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
    try:
        phone = validate_phone(phone)
    except PhoneValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not name:
        raise HTTPException(status_code=400, detail="Please enter your name")

    phone_keys = phone_variants(phone)
    existing = await db.gallery_visitors.find_one({"event_id": event_id, "phone": {"$in": phone_keys}})
    if existing and existing.get("status") == "blocked":
        raise HTTPException(status_code=403, detail="Your access to this gallery has been blocked")

    # Find or create a lightweight client user keyed by canonical phone.
    user = await db.users.find_one({"phone": {"$in": phone_keys}, "role": "client"})
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
    if await plans.owner_locked(event.get("created_by")):
        raise HTTPException(status_code=403, detail="This gallery has expired. Please ask the studio to renew their plan.")
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
    if await plans.owner_locked(event.get("created_by")):
        raise HTTPException(status_code=403, detail="This gallery has expired. Please ask the studio to renew their plan.")
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

# CRM / Client-Relationship layer — /api/clients + contacts + important-dates.
from crm_routes import crm_router  # noqa: E402
app.include_router(crm_router)

from superadmin_routes import superadmin_router  # noqa: E402
app.include_router(superadmin_router)

from push_service import push_router  # noqa: E402
app.include_router(push_router)


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
        # CRM layer
        await db.clients.create_index("client_id", unique=True)
        await db.clients.create_index("studio_id")
        await db.contacts.create_index("contact_id", unique=True)
        await db.contacts.create_index("client_id")
        await db.important_dates.create_index("date_id", unique=True)
        await db.important_dates.create_index("client_id")
        await db.events.create_index("client_id", sparse=True)
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

    # Seed platform super admin (idempotent). Credentials are backend-only.
    if SUPERADMIN_PASSWORD:
        try:
            existing_superadmin = await db.users.find_one({"email": SUPERADMIN_EMAIL})
            if not existing_superadmin:
                await db.users.insert_one({
                    "user_id": new_user_id(),
                    "role": "superadmin",
                    "name": "PIK Connect Super Admin",
                    "email": SUPERADMIN_EMAIL,
                    "phone": None,
                    "password_hash": hash_password(SUPERADMIN_PASSWORD),
                    "auth_provider": "password",
                    "created_at": now_iso(),
                })
                logger.info(f"Seeded superadmin {SUPERADMIN_EMAIL}")
        except Exception as e:
            logger.error(f"Superadmin seed failed: {e}")


    global _indexer_task
    _indexer_task = asyncio.create_task(_indexing_loop())


@app.on_event("shutdown")
async def on_shutdown():
    if _indexer_task:
        _indexer_task.cancel()
    client.close()
