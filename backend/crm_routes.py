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
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from config import db, PUBLIC_BASE_URL
from auth_utils import require_admin, require_client
from phone_utils import validate_phone, PhoneValidationError
import plans

crm_router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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
                  events=None, stats=None) -> dict:
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
    )


@crm_router.patch("/clients/{client_id}")
async def update_client(client_id: str, body: ClientUpdate, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    await _client_or_404(client_id, studio_id)
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
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
        "studio": studio,
    }


class BookingRequestBody(BaseModel):
    service_type: str = Field(min_length=1)
    preferred_date: Optional[str] = None
    location: Optional[str] = None
    message: Optional[str] = None


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
    doc = {
        "request_id": _new_id("bkg"),
        "client_user_id": user["user_id"],
        "studio_id": studio_id,
        "service_type": body.service_type.strip(),
        "preferred_date": (body.preferred_date or "").strip() or None,
        "location": (body.location or "").strip() or None,
        "message": (body.message or "").strip() or None,
        "contact_name": user.get("name"),
        "contact_email": user.get("email"),
        "contact_phone": user.get("phone"),
        "status": "new",
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
    return {"status": "ok", "request_id": doc["request_id"]}


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
    return {"status": "ok", "review_id": doc["review_id"]}
