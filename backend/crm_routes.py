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

from config import db
from auth_utils import require_admin

crm_router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


CLIENT_TYPES = {"family", "individual", "corporate"}
CLIENT_STATUSES = {"lead", "active", "past"}


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def public_client(doc: dict, *, contacts=None, important_dates=None,
                  events=None, stats=None) -> dict:
    out = {
        "client_id": doc["client_id"],
        "name": doc.get("name"),
        "type": doc.get("type", "family"),
        "status": doc.get("status", "active"),
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
    tags: list[str] = []
    notes: Optional[str] = None
    contacts: list[ContactIn] = []
    important_dates: list[ImportantDateIn] = []


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
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

    studio_id = admin["user_id"]
    client_id = _new_id("cli")
    ts = now_iso()
    doc = {
        "client_id": client_id,
        "studio_id": studio_id,
        "name": body.name.strip(),
        "type": body.type,
        "status": body.status,
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
            "phone": c.phone,
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
    admin: dict = Depends(require_admin),
):
    studio_id = admin["user_id"]
    query: dict = {"studio_id": studio_id}
    if status and status in CLIENT_STATUSES:
        query["status"] = status
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
        event_count = await db.events.count_documents({"client_id": cid, "created_by": studio_id})
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
        {"client_id": client_id, "created_by": studio_id}, {"_id": 0}
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
    # Unlink events (keep the galleries/albums intact).
    await db.events.update_many(
        {"client_id": client_id, "created_by": studio_id}, {"$unset": {"client_id": ""}}
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
        "phone": body.phone,
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
    await db.events.update_one({"event_id": event_id}, {"$set": {"client_id": client_id}})
    return {"status": "attached", "event_id": event_id, "client_id": client_id}


@crm_router.delete("/clients/{client_id}/events/{event_id}/attach")
async def detach_event(client_id: str, event_id: str, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    await _client_or_404(client_id, studio_id)
    await db.events.update_one(
        {"event_id": event_id, "created_by": studio_id, "client_id": client_id},
        {"$unset": {"client_id": ""}},
    )
    return {"status": "detached", "event_id": event_id, "client_id": client_id}
