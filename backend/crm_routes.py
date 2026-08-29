"""CRM / Client-Relationship layer for PIK Connect.

Adds a relationship-centric layer on top of the existing event-centric model:

    Photographer (studio admin)
        └── Client / Family  (clients)
                ├── Contacts            (contacts)      -- multiple people per family
                ├── Important Dates     (important_dates)
                └── Events              (events.client_id links back here)

Everything is scoped to the studio admin (``studio_id == admin.user_id``) so
studios never see each other's clients. Existing gallery / album / face-search
flows are untouched — events simply gain an optional ``client_id`` link.
"""
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from config import db, PUBLIC_BASE_URL, ADMIN_SEED_EMAIL
from auth_utils import require_admin, require_client
from phone_utils import validate_phone, PhoneValidationError, phone_variants
from notifications_service import notify, notify_superadmins
from push_service import push_user
import plans

crm_router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_iso_date(value: Optional[str], field: str = "date") -> Optional[str]:
    if value is None or not str(value).strip():
        return None
    try:
        parsed = datetime.strptime(str(value).strip(), "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{field.capitalize()} must be a valid calendar date (YYYY-MM-DD)") from exc
    return parsed.date().isoformat()


def clean_contact_phone(value: Optional[str]) -> Optional[str]:
    if not value or not value.strip():
        return None
    try:
        return validate_phone(value)
    except PhoneValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


DEFAULT_STUDIO_WHATSAPP = "8888766739"


def studio_profile_public(doc: dict | None) -> dict:
    doc = doc or {}
    return {
        "name": doc.get("name") or "PK Photography",
        "whatsapp": doc.get("whatsapp") or DEFAULT_STUDIO_WHATSAPP,
        "phone": doc.get("phone") or DEFAULT_STUDIO_WHATSAPP,
        "google_review_url": doc.get("google_review_url") or "",
        "booking_email": doc.get("booking_email") or "",
    }


async def get_studio_profile(studio_id: str | None) -> dict:
    doc = None
    if studio_id:
        doc = await db.studio_profiles.find_one({"studio_id": studio_id}, {"_id": 0})
    return studio_profile_public(doc)


def next_occurrence(datestr: str):
    """Return (iso_next_date, days_until) for a recurring important date.

    Accepts 'YYYY-MM-DD' or 'MM-DD'. Falls back gracefully on bad input.
    """
    try:
        s = (datestr or "").strip()
        if len(s) == 10:
            _, mm, dd = s.split("-")
        elif len(s) == 5:
            mm, dd = s.split("-")
        else:
            return (datestr, None)
        month, day = int(mm), int(dd)
        today = datetime.now(timezone.utc).date()
        year = today.year

        def _mk(y):
            d, m = day, month
            try:
                return datetime(y, m, d).date()
            except ValueError:
                return datetime(y, m, 28).date()  # e.g. Feb 29 -> Feb 28

        occ = _mk(year)
        if occ < today:
            occ = _mk(year + 1)
        return (occ.isoformat(), (occ - today).days)
    except Exception:
        return (datestr, None)


CLIENT_TYPES = {"family", "individual", "corporate"}
CLIENT_STATUSES = {"lead", "active", "past"}

# Pipeline lifecycle (finer-grained than status): New Inquiry -> Booked -> Completed -> Past
PIPELINE_STAGES = ["new_inquiry", "booked", "completed", "past"]
_STAGE_FROM_STATUS = {"lead": "new_inquiry", "active": "booked", "past": "past"}
_STATUS_FROM_STAGE = {"new_inquiry": "lead", "booked": "active", "completed": "active", "past": "past"}


def stage_from_status(status: str | None) -> str:
    return _STAGE_FROM_STATUS.get(status or "", "new_inquiry")


def status_from_stage(stage: str) -> str:
    return _STATUS_FROM_STAGE.get(stage, "active")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def public_client(doc: dict, *, contacts=None, important_dates=None,
                  events=None, stats=None, user_profile=None) -> dict:
    out = {
        "client_id": doc["client_id"],
        "name": doc.get("name"),
        "type": doc.get("type", "family"),
        "status": doc.get("status", "active"),
        "pipeline_stage": doc.get("pipeline_stage") or stage_from_status(doc.get("status", "active")),
        "tags": doc.get("tags", []),
        "notes": doc.get("notes"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }
    if contacts is not None:
        out["contacts"] = contacts
    if important_dates is not None:
        out["important_dates"] = important_dates
    if events is not None:
        out["events"] = events
    if stats is not None:
        out["stats"] = stats
    if user_profile is not None:
        out["user_profile"] = user_profile
    return out


def public_contact(doc: dict) -> dict:
    return {
        "contact_id": doc["contact_id"],
        "client_id": doc["client_id"],
        "name": doc.get("name"),
        "role": doc.get("role"),
        "phone": doc.get("phone"),
        "email": doc.get("email"),
        "is_primary": doc.get("is_primary", False),
        "created_at": doc.get("created_at"),
    }


def public_user_profile(doc: dict | None) -> dict | None:
    if not doc or not doc.get("client_profile"):
        return None
    profile = dict(doc["client_profile"])
    profile.update({
        "user_id": doc.get("user_id"),
        "email": doc.get("email"),
        "phone": doc.get("phone"),
        "verified_email": bool(doc.get("email") and doc.get("verified_email", True)),
        "verified_phone": bool(doc.get("phone") and doc.get("verified_phone", True)),
    })
    return profile


async def linked_user_profile(contacts: list[dict]) -> dict | None:
    ors = []
    for contact in contacts:
        if contact.get("email"):
            ors.append({"email": contact["email"].lower()})
        if contact.get("phone"):
            ors.append({"phone": contact["phone"]})
    if not ors:
        return None
    user = await db.users.find_one(
        {"role": "client", "$or": ors},
        {"_id": 0, "password_hash": 0},
    )
    return public_user_profile(user)


def public_date(doc: dict) -> dict:
    return {
        "date_id": doc["date_id"],
        "client_id": doc["client_id"],
        "person_label": doc.get("person_label"),
        "occasion": doc.get("occasion"),
        "date": doc.get("date"),
        "recurring": doc.get("recurring", True),
        "notes": doc.get("notes"),
        "created_at": doc.get("created_at"),
    }


def public_event_lite(doc: dict) -> dict:
    """Minimal event serialization for the client profile (no face/gdrive joins)."""
    return {
        "event_id": doc["event_id"],
        "name": doc.get("name"),
        "date": doc.get("date"),
        "category": doc.get("category"),
        "status": doc.get("status", "active"),
        "photo_count": doc.get("photo_count", 0),
        "value": doc.get("value", 0) or 0,
        "cover_path": doc.get("cover_path"),
        "created_at": doc.get("created_at"),
    }


async def event_cover_for_client(event: dict) -> tuple[str | None, str | None]:
    """Return a cover sourced only from this event, falling back to its first photo."""
    cover_path = event.get("cover_path")
    cover_drive_id = event.get("cover_drive_id")
    if cover_path or cover_drive_id:
        return cover_path, cover_drive_id

    first = await db.photos.find({"event_id": event["event_id"]}, {"_id": 0, "storage_path": 1, "thumb_path": 1, "drive_file_id": 1, "source": 1}) \
        .sort([("uploaded_at", 1), ("photo_id", 1)]).limit(1).to_list(1)
    if not first:
        return None, None
    photo = first[0]
    if photo.get("source") == "gdrive" and photo.get("drive_file_id"):
        return None, photo["drive_file_id"]
    return photo.get("thumb_path") or photo.get("storage_path"), None


def event_cover_url(cover_path: str | None, cover_drive_id: str | None) -> str | None:
    if cover_drive_id:
        return f"{PUBLIC_BASE_URL}/api/gdrive/thumb/{cover_drive_id}?w=1200"
    return None


async def _client_or_404(client_id: str, studio_id: str) -> dict:
    doc = await db.clients.find_one({"client_id": client_id, "studio_id": studio_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Client not found")
    return doc


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class ContactIn(BaseModel):
    name: str = Field(min_length=1)
    role: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_primary: bool = False


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_primary: Optional[bool] = None


class ImportantDateIn(BaseModel):
    person_label: str = Field(min_length=1)
    occasion: str = Field(min_length=1)
    date: str = Field(min_length=1)  # "YYYY-MM-DD" or "MM-DD"
    recurring: bool = True
    notes: Optional[str] = None


class ImportantDateUpdate(BaseModel):
    person_label: Optional[str] = None
    occasion: Optional[str] = None
    date: Optional[str] = None
    recurring: Optional[bool] = None
    notes: Optional[str] = None


class ClientCreate(BaseModel):
    name: str = Field(min_length=1)
    type: str = "family"
    status: str = "active"
    pipeline_stage: Optional[str] = None
    tags: list[str] = []
    notes: Optional[str] = None
    contacts: list[ContactIn] = []
    important_dates: list[ImportantDateIn] = []


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    pipeline_stage: Optional[str] = None
    tags: Optional[list[str]] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Clients (Family accounts)
# ---------------------------------------------------------------------------
@crm_router.post("/clients")
async def create_client(body: ClientCreate, admin: dict = Depends(require_admin)):
    if body.type not in CLIENT_TYPES:
        raise HTTPException(status_code=400, detail=f"type must be one of {sorted(CLIENT_TYPES)}")
    if body.status not in CLIENT_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(CLIENT_STATUSES)}")
    await plans.check_can_add_client(admin, 1)

    studio_id = admin["user_id"]
    client_id = _new_id("cli")
    ts = now_iso()
    stage = body.pipeline_stage if body.pipeline_stage in PIPELINE_STAGES else stage_from_status(body.status)
    doc = {
        "client_id": client_id,
        "studio_id": studio_id,
        "name": body.name.strip(),
        "type": body.type,
        "status": body.status,
        "pipeline_stage": stage,
        "tags": [t.strip() for t in body.tags if t.strip()],
        "notes": body.notes,
        "created_at": ts,
        "updated_at": ts,
    }
    await db.clients.insert_one(doc)

    # Optional inline contacts / dates on creation.
    for c in body.contacts:
        await db.contacts.insert_one({
            "contact_id": _new_id("con"),
            "client_id": client_id,
            "studio_id": studio_id,
            "name": c.name.strip(),
            "role": c.role,
            "phone": clean_contact_phone(c.phone),
            "email": (c.email or None),
            "is_primary": c.is_primary,
            "created_at": now_iso(),
        })
    for d in body.important_dates:
        await db.important_dates.insert_one({
            "date_id": _new_id("idt"),
            "client_id": client_id,
            "studio_id": studio_id,
            "person_label": d.person_label.strip(),
            "occasion": d.occasion.strip(),
            "date": d.date.strip(),
            "recurring": d.recurring,
            "notes": d.notes,
            "created_at": now_iso(),
        })

    return await get_client(client_id, admin)


@crm_router.get("/clients")
async def list_clients(
    q: Optional[str] = None,
    status: Optional[str] = None,
    tag: Optional[str] = None,
    stage: Optional[str] = None,
    admin: dict = Depends(require_admin),
):
    studio_id = admin["user_id"]
    query: dict = {"studio_id": studio_id}
    if status and status in CLIENT_STATUSES:
        query["status"] = status
    if stage and stage in PIPELINE_STAGES:
        query["pipeline_stage"] = stage
    if tag:
        query["tags"] = tag

    docs = await db.clients.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)

    # Optional free-text search across client name + contact name/phone/email.
    if q:
        ql = q.strip().lower()
        matched_ids = set()
        contact_hits = await db.contacts.find(
            {"studio_id": studio_id}, {"_id": 0, "client_id": 1, "name": 1, "phone": 1, "email": 1}
        ).to_list(5000)
        for c in contact_hits:
            hay = " ".join([str(c.get("name") or ""), str(c.get("phone") or ""), str(c.get("email") or "")]).lower()
            if ql in hay:
                matched_ids.add(c["client_id"])
        docs = [d for d in docs if ql in (d.get("name") or "").lower() or d["client_id"] in matched_ids]

    # Attach lightweight stats + a primary contact preview for the list view.
    out = []
    for d in docs:
        cid = d["client_id"]
        contact_count = await db.contacts.count_documents({"client_id": cid})
        event_count = await db.events.count_documents({
            "created_by": studio_id,
            "$or": [{"client_id": cid}, {"client_assignments.client_id": cid}],
        })
        primary = await db.contacts.find_one(
            {"client_id": cid, "is_primary": True}, {"_id": 0}
        ) or await db.contacts.find_one({"client_id": cid}, {"_id": 0})
        out.append(public_client(d, stats={
            "contact_count": contact_count,
            "event_count": event_count,
        }, contacts=[public_contact(primary)] if primary else []))
    return out


@crm_router.get("/clients/{client_id}")
async def get_client(client_id: str, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    doc = await _client_or_404(client_id, studio_id)

    contacts = await db.contacts.find({"client_id": client_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    dates = await db.important_dates.find({"client_id": client_id}, {"_id": 0}).sort("date", 1).to_list(500)
    events = await db.events.find(
        {
            "created_by": studio_id,
            "$or": [{"client_id": client_id}, {"client_assignments.client_id": client_id}],
        },
        {"_id": 0},
    ).sort("created_at", -1).to_list(500)

    lifetime_value = sum((e.get("value") or 0) for e in events)
    stats = {
        "contact_count": len(contacts),
        "event_count": len(events),
        "date_count": len(dates),
        "lifetime_value": lifetime_value,
    }
    return public_client(
        doc,
        contacts=[public_contact(c) for c in contacts],
        important_dates=[public_date(d) for d in dates],
        events=[public_event_lite(e) for e in events],
        stats=stats,
        user_profile=await linked_user_profile(contacts),
    )


@crm_router.patch("/clients/{client_id}")
async def update_client(client_id: str, body: ClientUpdate, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    await _client_or_404(client_id, studio_id)
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "preferred_date" in updates:
        updates["preferred_date"] = clean_iso_date(updates["preferred_date"], "preferred date")
    if "type" in updates and updates["type"] not in CLIENT_TYPES:
        raise HTTPException(status_code=400, detail=f"type must be one of {sorted(CLIENT_TYPES)}")
    if "status" in updates and updates["status"] not in CLIENT_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {sorted(CLIENT_STATUSES)}")
    if "tags" in updates:
        updates["tags"] = [t.strip() for t in updates["tags"] if t.strip()]
    if updates:
        updates["updated_at"] = now_iso()
        await db.clients.update_one({"client_id": client_id}, {"$set": updates})
    return await get_client(client_id, admin)


@crm_router.delete("/clients/{client_id}")
async def delete_client(client_id: str, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    await _client_or_404(client_id, studio_id)
    await db.contacts.delete_many({"client_id": client_id})
    await db.important_dates.delete_many({"client_id": client_id})
    # Unlink events/albums (keep galleries and albums intact).
    await db.events.update_many(
        {"client_id": client_id, "created_by": studio_id}, {"$unset": {"client_id": ""}}
    )
    await db.events.update_many(
        {"created_by": studio_id, "client_assignments.client_id": client_id},
        {"$pull": {"client_assignments": {"client_id": client_id}}},
    )
    await db.albums.update_many(
        {"created_by": studio_id, "client_assignments.client_id": client_id},
        {"$pull": {"client_assignments": {"client_id": client_id}}},
    )
    await db.clients.delete_one({"client_id": client_id})
    return {"status": "deleted", "client_id": client_id}


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------
@crm_router.post("/clients/{client_id}/contacts")
async def add_contact(client_id: str, body: ContactIn, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    await _client_or_404(client_id, studio_id)
    if body.is_primary:
        await db.contacts.update_many({"client_id": client_id}, {"$set": {"is_primary": False}})
    doc = {
        "contact_id": _new_id("con"),
        "client_id": client_id,
        "studio_id": studio_id,
        "name": body.name.strip(),
        "role": body.role,
        "phone": clean_contact_phone(body.phone),
        "email": (body.email or None),
        "is_primary": body.is_primary,
        "created_at": now_iso(),
    }
    await db.contacts.insert_one(doc)
    return public_contact(doc)


@crm_router.patch("/clients/{client_id}/contacts/{contact_id}")
async def update_contact(client_id: str, contact_id: str, body: ContactUpdate,
                         admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    await _client_or_404(client_id, studio_id)
    existing = await db.contacts.find_one({"contact_id": contact_id, "client_id": client_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Contact not found")
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "preferred_date" in updates:
        updates["preferred_date"] = clean_iso_date(updates["preferred_date"], "preferred date")
    if "phone" in updates:
        updates["phone"] = clean_contact_phone(updates["phone"])
    if updates.get("is_primary"):
        await db.contacts.update_many({"client_id": client_id}, {"$set": {"is_primary": False}})
    if updates:
        await db.contacts.update_one({"contact_id": contact_id}, {"$set": updates})
    doc = await db.contacts.find_one({"contact_id": contact_id}, {"_id": 0})
    return public_contact(doc)


@crm_router.delete("/clients/{client_id}/contacts/{contact_id}")
async def delete_contact(client_id: str, contact_id: str, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    await _client_or_404(client_id, studio_id)
    res = await db.contacts.delete_one({"contact_id": contact_id, "client_id": client_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Contact not found")
    return {"status": "deleted", "contact_id": contact_id}


# ---------------------------------------------------------------------------
# Important Dates
# ---------------------------------------------------------------------------
@crm_router.post("/clients/{client_id}/important-dates")
async def add_date(client_id: str, body: ImportantDateIn, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    await _client_or_404(client_id, studio_id)
    doc = {
        "date_id": _new_id("idt"),
        "client_id": client_id,
        "studio_id": studio_id,
        "person_label": body.person_label.strip(),
        "occasion": body.occasion.strip(),
        "date": body.date.strip(),
        "recurring": body.recurring,
        "notes": body.notes,
        "created_at": now_iso(),
    }
    await db.important_dates.insert_one(doc)
    return public_date(doc)


@crm_router.patch("/clients/{client_id}/important-dates/{date_id}")
async def update_date(client_id: str, date_id: str, body: ImportantDateUpdate,
                      admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    await _client_or_404(client_id, studio_id)
    existing = await db.important_dates.find_one({"date_id": date_id, "client_id": client_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Important date not found")
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "preferred_date" in updates:
        updates["preferred_date"] = clean_iso_date(updates["preferred_date"], "preferred date")
    if updates:
        await db.important_dates.update_one({"date_id": date_id}, {"$set": updates})
    doc = await db.important_dates.find_one({"date_id": date_id}, {"_id": 0})
    return public_date(doc)


@crm_router.delete("/clients/{client_id}/important-dates/{date_id}")
async def delete_date(client_id: str, date_id: str, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    await _client_or_404(client_id, studio_id)
    res = await db.important_dates.delete_one({"date_id": date_id, "client_id": client_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Important date not found")
    return {"status": "deleted", "date_id": date_id}


# ---------------------------------------------------------------------------
# Event <-> Client linkage
# ---------------------------------------------------------------------------
@crm_router.post("/clients/{client_id}/events/{event_id}/attach")
async def attach_event(client_id: str, event_id: str, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    await _client_or_404(client_id, studio_id)
    event = await db.events.find_one({"event_id": event_id, "created_by": studio_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    await db.events.update_one(
        {"event_id": event_id},
        {"$set": {"client_id": client_id}, "$addToSet": {
            "client_assignments": {
                "client_id": client_id,
                "full_gallery_access": True,
                "assigned_by": studio_id,
                "assigned_at": now_iso(),
            }
        }},
    )
    return {"status": "attached", "event_id": event_id, "client_id": client_id}


@crm_router.delete("/clients/{client_id}/events/{event_id}/attach")
async def detach_event(client_id: str, event_id: str, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    await _client_or_404(client_id, studio_id)
    await db.events.update_one(
        {"event_id": event_id, "created_by": studio_id},
        {"$unset": {"client_id": ""}, "$pull": {"client_assignments": {"client_id": client_id}}},
    )
    return {"status": "detached", "event_id": event_id, "client_id": client_id}


# ---------------------------------------------------------------------------
# Studio profile (admin) — contact info used by client Quick Actions
# ---------------------------------------------------------------------------
class StudioProfileUpdate(BaseModel):
    name: Optional[str] = None
    whatsapp: Optional[str] = None
    phone: Optional[str] = None
    google_review_url: Optional[str] = None
    booking_email: Optional[str] = None


@crm_router.get("/studio/profile")
async def get_my_studio_profile(admin: dict = Depends(require_admin)):
    return await get_studio_profile(admin["user_id"])


@crm_router.patch("/studio/profile")
async def update_my_studio_profile(body: StudioProfileUpdate, admin: dict = Depends(require_admin)):
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "preferred_date" in updates:
        updates["preferred_date"] = clean_iso_date(updates["preferred_date"], "preferred date")
    updates["studio_id"] = admin["user_id"]
    updates["updated_at"] = now_iso()
    await db.studio_profiles.update_one(
        {"studio_id": admin["user_id"]}, {"$set": updates}, upsert=True
    )
    return await get_studio_profile(admin["user_id"])


# ---------------------------------------------------------------------------
# Client dashboard ("Your Memories") + Quick Actions
# ---------------------------------------------------------------------------
async def _client_grants(user: dict):
    ors = []
    if user.get("email"):
        ors.append({"client_email": user["email"].lower()})
    if user.get("phone"):
        ors.append({"client_phone": user["phone"]})
    if not ors:
        return []
    return await db.access_grants.find({"status": "active", "$or": ors}, {"_id": 0}).to_list(2000)


async def _client_family_ids(user: dict) -> list[str]:
    """CRM clients whose contacts match this signed-in client's email/phone."""
    ors = []
    if user.get("email"):
        ors.append({"email": user["email"].lower()})
        ors.append({"email": user["email"]})
    if user.get("phone"):
        ors.append({"phone": user["phone"]})
    if not ors:
        return []
    contacts = await db.contacts.find({"$or": ors}, {"_id": 0, "client_id": 1}).to_list(2000)
    return list({c["client_id"] for c in contacts})


@crm_router.get("/me/dashboard")
async def client_dashboard(user: dict = Depends(require_client)):
    # ---- Memories: events shared with this client (active, non-archived) ----
    grants = await _client_grants(user)
    memories = []
    studio_ids: list[str] = []
    for g in grants:
        event = await db.events.find_one({"event_id": g["event_id"]}, {"_id": 0})
        if not event or event.get("status") == "archived":
            continue
        album = await db.client_albums.find_one(
            {"event_id": g["event_id"], "client_user_id": user["user_id"]},
            {"_id": 0, "photo_ids": 1},
        )
        date_str = event.get("date") or ""
        year = None
        if len(date_str) >= 4 and date_str[:4].isdigit():
            year = date_str[:4]
        elif event.get("created_at"):
            year = str(event["created_at"])[:4]
        if event.get("created_by"):
            studio_ids.append(event["created_by"])
        cover_path, cover_drive_id = await event_cover_for_client(event)
        memories.append({
            "event_id": event["event_id"],
            "name": event.get("name"),
            "date": event.get("date"),
            "year": year,
            "category": event.get("category"),
            "photo_count": event.get("photo_count", 0),
            "my_photos_count": len(album.get("photo_ids", [])) if album else 0,
            "cover_path": cover_path,
            "cover_drive_id": cover_drive_id,
            "cover_url": event_cover_url(cover_path, cover_drive_id),
            "photographer": event.get("photographer"),
            "created_at": event.get("created_at"),
        })
    memories.sort(key=lambda m: (m.get("date") or m.get("created_at") or ""), reverse=True)

    # ---- Upcoming important dates (from the client's CRM family records) ----
    family_ids = await _client_family_ids(user)
    upcoming = []
    if family_ids:
        dates = await db.important_dates.find(
            {"client_id": {"$in": family_ids}}, {"_id": 0}
        ).to_list(500)
        for d in dates:
            iso, days = next_occurrence(d.get("date", ""))
            upcoming.append({
                "date_id": d.get("date_id"),
                "person_label": d.get("person_label"),
                "occasion": d.get("occasion"),
                "date": d.get("date"),
                "next_date": iso,
                "days_until": days,
            })
        upcoming = [u for u in upcoming if u["days_until"] is not None]
        upcoming.sort(key=lambda u: u["days_until"])

    # ---- Scheduled shoots (from the booking pipeline) ----
    scheduled_bookings = await db.booking_requests.find(
        {"client_user_id": user["user_id"], "status": "scheduled"},
        {"_id": 0},
    ).sort("preferred_date", 1).to_list(20)
    upcoming_shoots = [_booking_view(doc) for doc in scheduled_bookings]

    # ---- Studio contact (for Quick Actions) ----
    studio_id = None
    if studio_ids:
        # most frequent / most recent studio the client has events with
        studio_id = studio_ids[0]
    studio = await get_studio_profile(studio_id)

    name = user.get("name") or "there"
    first_name = name.split(" ")[0] if name else name
    return {
        "profile": {"name": name, "first_name": first_name},
        "memories": memories,
        "upcoming": upcoming[:6],
        "upcoming_shoots": upcoming_shoots,
        "studio": studio,
    }


class BookingRequestBody(BaseModel):
    event_name: Optional[str] = None
    service_type: str = Field(min_length=1)
    preferred_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    requirement: Optional[str] = None
    expected_budget: Optional[float] = None
    message: Optional[str] = None


class BookingUpdateBody(BaseModel):
    event_name: Optional[str] = None
    service_type: Optional[str] = None
    preferred_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    requirement: Optional[str] = None
    expected_budget: Optional[float] = None
    status: Optional[str] = None
    total_amount: Optional[float] = None
    advance_amount: Optional[float] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None


class ClientBookingEditBody(BaseModel):
    event_name: Optional[str] = None
    service_type: Optional[str] = None
    preferred_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    requirement: Optional[str] = None
    expected_budget: Optional[float] = None
    message: Optional[str] = None


class QuoteBody(BaseModel):
    total_amount: float = Field(ge=0)
    advance_amount: float = Field(ge=0)
    payment_terms: Optional[str] = None
    notes: Optional[str] = None
    offerings: list[dict] = Field(default_factory=list)


class PaymentBody(BaseModel):
    label: str = Field(min_length=1)
    amount: float = Field(gt=0)
    method: str = "cash"
    status: str = "paid"
    notes: Optional[str] = None


class BookingStatusBody(BaseModel):
    status: str


class ScheduleBody(BaseModel):
    scheduled_date: str = Field(min_length=1)
    start_time: str = Field(min_length=1)
    end_time: str = Field(min_length=1)
    venue: str = Field(min_length=1)
    assigned_photographer: Optional[str] = None
    team_notes: Optional[str] = None


BOOKING_STATUSES = {"new_request", "quotation", "payment_pending", "confirmed", "scheduled", "completed", "cancelled"}


async def _fallback_booking_studio_id() -> str | None:
    """Route enquiries without an existing gallery to the default studio.

    Prefer an admin/studio profile explicitly using the configured business
    number, then the admin user phone, and finally the seeded admin account so
    the enquiry is never left ownerless when the default studio is onboarding.
    """
    target = os.environ.get("DEFAULT_BOOKING_ADMIN_PHONE", "8888766739")
    try:
        canonical = validate_phone(target)
    except PhoneValidationError:
        canonical = ""
    variants = phone_variants(canonical) if canonical else []
    if variants:
        profile = await db.studio_profiles.find_one(
            {"$or": [
                {"phone": {"$in": variants}},
                {"whatsapp": {"$in": variants}},
            ]},
            {"_id": 0, "studio_id": 1},
        )
        if profile and profile.get("studio_id"):
            return profile["studio_id"]
        admin = await db.users.find_one(
            {"role": "admin", "phone": {"$in": variants}},
            {"_id": 0, "user_id": 1},
        )
        if admin:
            return admin["user_id"]
    seed = await db.users.find_one(
        {"role": "admin", "email": ADMIN_SEED_EMAIL.lower()},
        {"_id": 0, "user_id": 1},
    )
    return seed.get("user_id") if seed else None


async def _ensure_booking_lead(studio_id: str | None, user: dict) -> str | None:
    """Create/link a studio CRM lead for every new enquiry."""
    if not studio_id:
        return None
    ors = []
    if user.get("phone"):
        ors.append({"phone": {"$in": phone_variants(user["phone"])}})
    if user.get("email"):
        ors.append({"email": user["email"].lower()})
    if not ors:
        return None
    contact = await db.contacts.find_one({"studio_id": studio_id, "$or": ors}, {"_id": 0})
    if contact:
        await db.clients.update_one(
            {"client_id": contact["client_id"], "studio_id": studio_id},
            {"$addToSet": {"tags": "Lead"}, "$set": {"updated_at": now_iso()}},
        )
        return contact["client_id"]

    client_id = _new_id("cli")
    ts = now_iso()
    await db.clients.insert_one({
        "client_id": client_id,
        "studio_id": studio_id,
        "name": user.get("name") or "New enquiry",
        "type": "individual",
        "status": "lead",
        "pipeline_stage": "new_inquiry",
        "tags": ["Lead"],
        "notes": "Automatically created from a booking enquiry.",
        "created_at": ts,
        "updated_at": ts,
    })
    await db.contacts.insert_one({
        "contact_id": _new_id("con"),
        "client_id": client_id,
        "studio_id": studio_id,
        "name": user.get("name") or "New enquiry",
        "role": "Lead",
        "phone": clean_contact_phone(user.get("phone")),
        "email": (user.get("email") or None),
        "is_primary": True,
        "created_at": ts,
    })
    return client_id



@crm_router.post("/me/booking-requests")
async def create_booking_request(body: BookingRequestBody, user: dict = Depends(require_client)):
    # Best-effort: attribute to the studio the client already has events with.
    grants = await _client_grants(user)
    studio_id = None
    for g in grants:
        ev = await db.events.find_one({"event_id": g["event_id"]}, {"_id": 0, "created_by": 1})
        if ev and ev.get("created_by"):
            studio_id = ev["created_by"]
            break
    routing_source = "associated_studio" if studio_id else "default_admin_phone"
    if not studio_id:
        studio_id = await _fallback_booking_studio_id()
    crm_client_id = await _ensure_booking_lead(studio_id, user)
    doc = {
        "request_id": _new_id("bkg"),
        "client_user_id": user["user_id"],
        "crm_client_id": crm_client_id,
        "studio_id": studio_id,
        "routing_source": routing_source,
        "status": "new_request",
        "event_name": (body.event_name or body.service_type).strip(),
        "service_type": body.service_type.strip(),
        "preferred_date": clean_iso_date(body.preferred_date, "preferred date"),
        "start_time": (body.start_time or "").strip() or None,
        "end_time": (body.end_time or "").strip() or None,
        "location": (body.location or "").strip() or None,
        "requirement": (body.requirement or "").strip() or None,
        "expected_budget": body.expected_budget,
        "message": (body.message or "").strip() or None,
        "total_amount": None,
        "advance_amount": None,
        "payment_terms": None,
        "quote_revision": 0,
        "quote_history": [],
        "payments": [],
        "booking_id": None,
        "event_id": None,
        "notes": None,
        "contact_name": user.get("name") or "Guest",
        "contact_email": user.get("email"),
        "contact_phone": user.get("phone"),
        "created_at": now_iso(),
    }
    await db.booking_requests.insert_one(doc)
    if studio_id:
        await db.notifications.insert_one({
            "notification_id": _new_id("ntf"),
            "studio_id": studio_id,
            "type": "booking_request",
            "title": "New booking request",
            "body": f"{doc['contact_name'] or 'A client'} requested {doc['service_type']}.",
            "booking_request_id": doc["request_id"],
            "contact_name": doc.get("contact_name"),
            "contact_phone": doc.get("contact_phone"),
            "contact_email": doc.get("contact_email"),
            "service_type": doc["service_type"],
            "preferred_date": doc.get("preferred_date"),
            "location": doc.get("location"),
            "message": doc.get("message"),
            "read": False,
            "created_at": doc["created_at"],
        })
        await push_user(studio_id, "New booking request", f"{doc['contact_name'] or 'A client'} requested {doc['service_type']}.", action_url=f"/admin/booking/{doc['request_id']}")
    return {"status": "ok", "request_id": doc["request_id"]}


def _booking_view(doc: dict) -> dict:
    payments = doc.get("payments") or []
    paid = sum(float(p.get("amount") or 0) for p in payments if p.get("status") == "paid")
    total = doc.get("total_amount")
    return {**{k: v for k, v in doc.items() if k != "_id"}, "paid_amount": paid, "remaining_amount": max(float(total or 0) - paid, 0)}


async def _notify_client(user_id: Optional[str], title: str, body: str, kind: str, booking_id: str):
    if user_id:
        await db.notifications.insert_one({
            "notification_id": _new_id("ntf"), "client_user_id": user_id,
            "type": kind, "title": title, "body": body,
            "booking_request_id": booking_id, "read": False, "created_at": now_iso(),
        })
        await push_user(user_id, title, body, action_url=f"/client/booking/{booking_id}")


@crm_router.get("/me/bookings")
async def list_client_bookings(user: dict = Depends(require_client)):
    docs = await db.booking_requests.find({"client_user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return [_booking_view(doc) for doc in docs]


@crm_router.get("/me/bookings/{booking_id}")
async def get_client_booking(booking_id: str, user: dict = Depends(require_client)):
    doc = await db.booking_requests.find_one({"request_id": booking_id, "client_user_id": user["user_id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Booking not found")
    return _booking_view(doc)


@crm_router.get("/bookings")
async def list_admin_bookings(status: Optional[str] = None, admin: dict = Depends(require_admin)):
    query = {"studio_id": admin["user_id"]}
    if status and status in BOOKING_STATUSES:
        query["status"] = status
    docs = await db.booking_requests.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return [_booking_view(doc) for doc in docs]


@crm_router.get("/bookings/{booking_id}")
async def get_admin_booking(booking_id: str, admin: dict = Depends(require_admin)):
    doc = await db.booking_requests.find_one({"request_id": booking_id, "studio_id": admin["user_id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Booking not found")
    return _booking_view(doc)


@crm_router.patch("/bookings/{booking_id}")
async def update_admin_booking(booking_id: str, body: BookingUpdateBody, admin: dict = Depends(require_admin)):
    doc = await db.booking_requests.find_one({"request_id": booking_id, "studio_id": admin["user_id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Booking not found")
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "preferred_date" in updates:
        updates["preferred_date"] = clean_iso_date(updates["preferred_date"], "preferred date")
    if "status" in updates and updates["status"] not in BOOKING_STATUSES: raise HTTPException(status_code=400, detail="Invalid booking status")
    await db.booking_requests.update_one({"request_id": booking_id}, {"$set": updates})
    return _booking_view(await db.booking_requests.find_one({"request_id": booking_id}, {"_id": 0}))


@crm_router.post("/bookings/{booking_id}/quote")
async def send_booking_quote(booking_id: str, body: QuoteBody, admin: dict = Depends(require_admin)):
    doc = await db.booking_requests.find_one({"request_id": booking_id, "studio_id": admin["user_id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Booking not found")
    if body.advance_amount > body.total_amount: raise HTTPException(status_code=400, detail="Advance cannot exceed total")
    revision = int(doc.get("quote_revision") or 0) + 1
    offerings = [
        {
            "title": str(item.get("title") or "Included service").strip(),
            "description": str(item.get("description") or "").strip(),
            "amount": float(item.get("amount") or 0),
        }
        for item in body.offerings
        if isinstance(item, dict)
    ]
    quote = {"revision": revision, "total_amount": body.total_amount, "advance_amount": body.advance_amount, "payment_terms": body.payment_terms, "notes": body.notes, "offerings": offerings, "created_at": now_iso()}
    await db.booking_requests.update_one({"request_id": booking_id}, {"$set": {"total_amount": body.total_amount, "advance_amount": body.advance_amount, "payment_terms": body.payment_terms, "notes": body.notes, "offerings": offerings, "quote_revision": revision, "status": "quotation"}, "$push": {"quote_history": quote}})
    await _notify_client(doc.get("client_user_id"), "Quotation received", f"Your studio sent quotation revision {revision}.", "quotation", booking_id)
    return _booking_view(await db.booking_requests.find_one({"request_id": booking_id}, {"_id": 0}))


@crm_router.patch("/me/bookings/{booking_id}")
async def edit_client_booking(booking_id: str, body: ClientBookingEditBody, user: dict = Depends(require_client)):
    doc = await db.booking_requests.find_one({"request_id": booking_id, "client_user_id": user["user_id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Booking not found")
    if doc.get("status") not in {"new_request", "quotation", "payment_pending"}:
        raise HTTPException(status_code=400, detail="This booking can no longer be edited")
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "preferred_date" in updates:
        updates["preferred_date"] = clean_iso_date(updates["preferred_date"], "preferred date")
    if not updates: raise HTTPException(status_code=400, detail="Add at least one change")
    if "service_type" in updates and not str(updates["service_type"]).strip():
        raise HTTPException(status_code=400, detail="Service type cannot be empty")
    updates["client_change_request"] = "Client updated booking enquiry"
    updates["status"] = "new_request"
    updates["updated_at"] = now_iso()
    await db.booking_requests.update_one({"request_id": booking_id}, {"$set": updates})
    if doc.get("studio_id"):
        await db.notifications.insert_one({"notification_id": _new_id("ntf"), "studio_id": doc["studio_id"], "type": "booking_update", "title": "Booking enquiry updated", "body": f"{doc.get('contact_name') or 'A client'} updated their enquiry.", "booking_request_id": booking_id, "read": False, "created_at": now_iso()})
        await push_user(doc["studio_id"], "Booking enquiry updated", f"{doc.get('contact_name') or 'A client'} updated their enquiry.", action_url=f"/admin/booking/{booking_id}")
    return _booking_view(await db.booking_requests.find_one({"request_id": booking_id}, {"_id": 0}))


@crm_router.post("/me/bookings/{booking_id}/quote/accept")
async def accept_booking_quote(booking_id: str, user: dict = Depends(require_client)):
    doc = await db.booking_requests.find_one({"request_id": booking_id, "client_user_id": user["user_id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Booking not found")
    if doc.get("status") != "quotation" or not doc.get("quote_revision"):
        raise HTTPException(status_code=400, detail="There is no quotation ready to accept")
    await db.booking_requests.update_one({"request_id": booking_id}, {"$set": {"status": "payment_pending", "client_decision": "accepted", "client_decided_at": now_iso()}})
    if doc.get("studio_id"): 
        await db.notifications.insert_one({"notification_id": _new_id("ntf"), "studio_id": doc["studio_id"], "type": "booking_update", "title": "Quotation accepted", "body": f"{doc.get('contact_name') or 'A client'} accepted the quotation.", "booking_request_id": booking_id, "read": False, "created_at": now_iso()})
        await push_user(doc["studio_id"], "Quotation accepted", f"{doc.get('contact_name') or 'A client'} accepted the quotation.", action_url=f"/admin/booking/{booking_id}")
    return _booking_view(await db.booking_requests.find_one({"request_id": booking_id}, {"_id": 0}))


@crm_router.post("/me/bookings/{booking_id}/quote/changes")
async def request_booking_changes(booking_id: str, body: dict, user: dict = Depends(require_client)):
    doc = await db.booking_requests.find_one({"request_id": booking_id, "client_user_id": user["user_id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Booking not found")
    message = str(body.get("message") or "Client requested quotation changes")
    await db.booking_requests.update_one({"request_id": booking_id}, {"$set": {"status": "quotation", "client_change_request": message}})
    if doc.get("studio_id"): 
        await db.notifications.insert_one({"notification_id": _new_id("ntf"), "studio_id": doc["studio_id"], "type": "booking_update", "title": "Quotation changes requested", "body": message, "booking_request_id": booking_id, "read": False, "created_at": now_iso()})
        await push_user(doc["studio_id"], "Quotation changes requested", message, action_url=f"/admin/booking/{booking_id}")
    return _booking_view(await db.booking_requests.find_one({"request_id": booking_id}, {"_id": 0}))


@crm_router.post("/bookings/{booking_id}/payments")
async def add_booking_payment(booking_id: str, body: PaymentBody, admin: dict = Depends(require_admin)):
    doc = await db.booking_requests.find_one({"request_id": booking_id, "studio_id": admin["user_id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Booking not found")
    payment = {"payment_id": _new_id("pay"), **body.model_dump(), "paid_at": now_iso() if body.status == "paid" else None}
    payments = (doc.get("payments") or []) + [payment]
    paid = sum(float(p.get("amount") or 0) for p in payments if p.get("status") == "paid")
    advance_due = float(doc.get("advance_amount") or doc.get("total_amount") or 0)
    status = "confirmed" if advance_due > 0 and paid >= advance_due else ("payment_pending" if doc.get("status") in {"quotation", "payment_pending"} else doc.get("status", "new_request"))
    updates = {"payments": payments, "status": status}
    if status == "confirmed" and not doc.get("booking_id"):
        count = await db.booking_requests.count_documents({"booking_id": {"$ne": None}})
        updates["booking_id"] = f"PIK-{datetime.now(timezone.utc).year}-{count + 1:05d}"
    await db.booking_requests.update_one({"request_id": booking_id}, {"$set": updates})
    if status == "confirmed": await _notify_client(doc.get("client_user_id"), "Booking confirmed", "Your payment was received and your booking is confirmed.", "booking_confirmed", booking_id)
    return _booking_view(await db.booking_requests.find_one({"request_id": booking_id}, {"_id": 0}))


@crm_router.post("/bookings/{booking_id}/schedule")
async def schedule_booking(booking_id: str, body: ScheduleBody, admin: dict = Depends(require_admin)):
    doc = await db.booking_requests.find_one({"request_id": booking_id, "studio_id": admin["user_id"]}, {"_id": 0})
    if not doc: raise HTTPException(status_code=404, detail="Booking not found")
    if doc.get("status") != "confirmed":
        raise HTTPException(status_code=400, detail="Record the booking payment before scheduling")
    scheduled_date = clean_iso_date(body.scheduled_date, "scheduled date")
    if body.end_time <= body.start_time:
        raise HTTPException(status_code=400, detail="End time must be after start time")
    same_day = await db.booking_requests.find({
        "studio_id": admin["user_id"],
        "request_id": {"$ne": booking_id},
        "status": "scheduled",
        "preferred_date": scheduled_date,
    }, {"_id": 0, "start_time": 1, "end_time": 1}).to_list(100)
    for other in same_day:
        if other.get("start_time") and other.get("end_time") and body.start_time < other["end_time"] and body.end_time > other["start_time"]:
            raise HTTPException(status_code=409, detail="This time overlaps another scheduled booking")
    schedule = {
        "date": scheduled_date,
        "start_time": body.start_time,
        "end_time": body.end_time,
        "venue": body.venue.strip(),
        "assigned_photographer": (body.assigned_photographer or "").strip() or None,
        "team_notes": (body.team_notes or "").strip() or None,
        "scheduled_at": now_iso(),
    }
    await db.booking_requests.update_one({"request_id": booking_id}, {"$set": {"status": "scheduled", "preferred_date": scheduled_date, "start_time": body.start_time, "end_time": body.end_time, "location": body.venue.strip(), "schedule": schedule, "updated_at": now_iso()}})
    await _notify_client(doc.get("client_user_id"), "Shoot scheduled", f"Your shoot is scheduled for {scheduled_date} at {body.start_time}.", "booking_scheduled", booking_id)
    return _booking_view(await db.booking_requests.find_one({"request_id": booking_id}, {"_id": 0}))


@crm_router.get("/bookings-calendar")
async def bookings_calendar(month: Optional[str] = None, admin: dict = Depends(require_admin)):
    query = {"studio_id": admin["user_id"], "status": "scheduled", "preferred_date": {"$ne": None}}
    if month: query["preferred_date"] = {"$regex": f"^{month}"}
    docs = await db.booking_requests.find(query, {"_id": 0}).sort("preferred_date", 1).to_list(500)
    return [_booking_view(doc) for doc in docs]


@crm_router.get("/notifications")
async def list_admin_notifications(admin: dict = Depends(require_admin)):
    items = await db.notifications.find(
        {"studio_id": admin["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return {
        "items": items,
        "unread_count": sum(1 for item in items if not item.get("read")),
    }


@crm_router.patch("/notifications/{notification_id}/read")
async def mark_admin_notification_read(notification_id: str, admin: dict = Depends(require_admin)):
    result = await db.notifications.update_one(
        {"notification_id": notification_id, "studio_id": admin["user_id"]},
        {"$set": {"read": True, "read_at": now_iso()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "read", "notification_id": notification_id}


@crm_router.get("/me/notifications")
async def list_client_notifications(user: dict = Depends(require_client)):
    items = await db.notifications.find(
        {"client_user_id": user["user_id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return {"items": items, "unread_count": sum(1 for item in items if not item.get("read"))}


@crm_router.patch("/me/notifications/{notification_id}/read")
async def mark_client_notification_read(notification_id: str, user: dict = Depends(require_client)):
    result = await db.notifications.update_one(
        {"notification_id": notification_id, "client_user_id": user["user_id"]},
        {"$set": {"read": True, "read_at": now_iso()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "read", "notification_id": notification_id}


class ReviewBody(BaseModel):
    rating: int = Field(ge=1, le=5)
    text: Optional[str] = None
    event_id: Optional[str] = None


@crm_router.post("/me/reviews")
async def create_review(body: ReviewBody, user: dict = Depends(require_client)):
    studio_id = None
    if body.event_id:
        ev = await db.events.find_one({"event_id": body.event_id}, {"_id": 0, "created_by": 1})
        if ev:
            studio_id = ev.get("created_by")
    if not studio_id:
        grants = await _client_grants(user)
        for g in grants:
            ev = await db.events.find_one({"event_id": g["event_id"]}, {"_id": 0, "created_by": 1})
            if ev and ev.get("created_by"):
                studio_id = ev["created_by"]
                break
    doc = {
        "review_id": _new_id("rev"),
        "client_user_id": user["user_id"],
        "studio_id": studio_id,
        "event_id": body.event_id,
        "rating": body.rating,
        "text": (body.text or "").strip() or None,
        "contact_name": user.get("name"),
        "created_at": now_iso(),
    }
    await db.reviews.insert_one(doc)

    # Notify the studio and (for low ratings only) flag the platform team.
    try:
        client_name = user.get("name") or "A client"
        stars = "★" * body.rating + "☆" * (5 - body.rating)
        if studio_id:
            await notify(
                user_id=studio_id,
                type_key="review_received",
                title=f"New review · {stars}",
                body=f'{client_name} rated you {body.rating}/5' + (f': "{doc["text"][:120]}"' if doc.get("text") else "."),
                action_url="/admin/reviews",
                meta={"review_id": doc["review_id"], "rating": body.rating, "client_user_id": user["user_id"]},
            )
        if body.rating <= 2:
            await notify_superadmins(
                type_key="sa_review_flag",
                title=f"Low rating: {stars}",
                body=f'{client_name} rated their studio {body.rating}/5' + (f': "{doc["text"][:120]}"' if doc.get("text") else "."),
                action_url=f"/superadmin/studio/{studio_id}" if studio_id else None,
                meta={"review_id": doc["review_id"], "rating": body.rating, "studio_id": studio_id},
                dedupe_key=f"sa_review_flag:{doc['review_id']}",
            )
    except Exception as e:  # noqa: BLE001
        # Never fail review creation because of a notification hiccup.
        import logging  # local import — cheap and keeps top of file lean
        logging.getLogger(__name__).warning(f"review notify failed: {e}")

    return {"status": "ok", "review_id": doc["review_id"]}
