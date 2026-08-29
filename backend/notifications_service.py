"""Unified notification service.

Every runtime notification (in-app + push) is created through :func:`notify`
so per-user preferences and dedupe rules are enforced in one place. Legacy
inline ``db.notifications.insert_one({...})`` sites should migrate to this
helper over time; new code MUST use it.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from config import db
from push_service import push_user

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Notification catalog — the source of truth for the Settings prefs UI.
# All types are ON by default; disabling stores the key in the user's prefs.
# ---------------------------------------------------------------------------
NOTIFICATION_TYPES: list[dict] = [
    # ---- Studio / Admin ----
    {"key": "booking_enquiry",   "audience": "admin",  "group": "Bookings",  "label": "New booking enquiries",       "desc": "When a lead submits a booking or enquiry form."},
    {"key": "booking_update",    "audience": "admin",  "group": "Bookings",  "label": "Booking status updates",      "desc": "When a client updates or changes a booking."},
    {"key": "quotation_accepted","audience": "admin",  "group": "Bookings",  "label": "Quotations accepted",         "desc": "When a client accepts a quotation you sent."},
    {"key": "quotation_changes", "audience": "admin",  "group": "Bookings",  "label": "Quotation changes requested", "desc": "When a client asks for changes to a quotation."},
    {"key": "guest_face_search", "audience": "admin",  "group": "Gallery",   "label": "Guest completed face search", "desc": "When a guest scans their selfie in your gallery (deduped per guest per day)."},
    {"key": "photo_downloaded",  "audience": "admin",  "group": "Gallery",   "label": "Photos downloaded",           "desc": "When a client downloads photos from your gallery."},
    {"key": "upload_indexed",    "audience": "admin",  "group": "Gallery",   "label": "Bulk upload completed",       "desc": "When a bulk photo upload finishes and is ready to view."},
    {"key": "review_received",   "audience": "admin",  "group": "Feedback",  "label": "Reviews & ratings",           "desc": "When a client leaves a rating or review."},
    {"key": "superadmin_notice", "audience": "admin",  "group": "System",    "label": "Platform announcements",      "desc": "Important product updates from the PIK Connect team."},
    # ---- Client ----
    {"key": "gallery_assigned",  "audience": "client", "group": "Gallery",   "label": "New gallery access",           "desc": "When a photographer shares a gallery with you."},
    {"key": "new_photos",        "audience": "client", "group": "Gallery",   "label": "New photos added",             "desc": "When more photos are added to a gallery you have access to."},
    {"key": "album_ready",       "audience": "client", "group": "Gallery",   "label": "Digital album ready",          "desc": "When your studio publishes your flipbook album."},
    {"key": "payment_reminder",  "audience": "client", "group": "Payments",  "label": "Payment reminders",            "desc": "Reminders for pending payments and invoices."},
    {"key": "booking_confirmed", "audience": "client", "group": "Bookings",  "label": "Booking confirmations",        "desc": "When your studio confirms or updates a booking."},
    # ---- Broadcast from studio to clients (always allow opt-out) ----
    {"key": "custom_message",    "audience": "client", "group": "Studio",    "label": "Messages from your studio",    "desc": "Announcements, offers and personal notes from your photographer."},
]

_TYPE_KEYS = {t["key"] for t in NOTIFICATION_TYPES}
_AUDIENCE_BY_KEY = {t["key"]: t["audience"] for t in NOTIFICATION_TYPES}


def types_for(audience: str) -> list[dict]:
    return [t for t in NOTIFICATION_TYPES if t["audience"] == audience]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Preferences — sparse (only stores disabled keys)
# ---------------------------------------------------------------------------
async def get_disabled_types(user_id: str) -> list[str]:
    doc = await db.notification_prefs.find_one({"user_id": user_id}, {"_id": 0, "disabled": 1})
    return list(doc.get("disabled") or []) if doc else []


async def set_disabled_types(user_id: str, disabled: list[str]) -> list[str]:
    cleaned = sorted({d for d in disabled if d in _TYPE_KEYS})
    await db.notification_prefs.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "disabled": cleaned, "updated_at": _now_iso()}},
        upsert=True,
    )
    return cleaned


async def is_type_enabled(user_id: str, type_key: str) -> bool:
    """True unless the user has explicitly disabled this type."""
    if type_key not in _TYPE_KEYS:
        # Unknown types are always allowed — protects legacy call sites.
        return True
    disabled = await get_disabled_types(user_id)
    return type_key not in disabled


# ---------------------------------------------------------------------------
# Core notify() — every send goes through here
# ---------------------------------------------------------------------------
async def notify(
    *,
    user_id: str,
    type_key: str,
    title: str,
    body: str,
    action_url: Optional[str] = None,
    meta: Optional[dict] = None,
    dedupe_key: Optional[str] = None,
    push: bool = True,
) -> Optional[str]:
    """Create an in-app notification (and optional push) for a single user.

    Never raises — a notification failure must never block the primary
    operation. Returns the created notification_id on success, else None.

    :param dedupe_key: If provided, silently no-ops when a notification with
        the same (user_id, dedupe_key) already exists within the last 24h.
    """
    if not user_id:
        return None
    try:
        if not await is_type_enabled(user_id, type_key):
            return None

        # Dedupe recent duplicates (e.g., a guest re-running face search).
        if dedupe_key:
            existing = await db.notifications.find_one(
                {"dedupe_key": dedupe_key, "created_at": {"$gte": _dedupe_window_iso()}},
                {"_id": 0, "notification_id": 1},
            )
            if existing:
                return existing["notification_id"]

        audience = _AUDIENCE_BY_KEY.get(type_key, "admin")
        doc: dict = {
            "notification_id": f"ntf_{uuid.uuid4().hex[:12]}",
            "type": type_key,
            "audience": audience,
            "title": title[:120] if title else type_key,
            "body": (body or "")[:500],
            "action_url": action_url,
            "meta": meta or {},
            "read": False,
            "created_at": _now_iso(),
        }
        # We store the recipient in the field the existing list-endpoints query on
        # so no route changes are needed.
        if audience == "admin":
            doc["studio_id"] = user_id
        else:
            doc["client_user_id"] = user_id
        if dedupe_key:
            doc["dedupe_key"] = dedupe_key
        await db.notifications.insert_one(doc)

        if push:
            # Fire-and-forget; push_user swallows its own errors.
            await push_user(user_id, title, body, action_url)
        return doc["notification_id"]
    except Exception as e:  # noqa: BLE001 - notifications must not break flows
        logger.warning(f"notify() failed for user={user_id} type={type_key}: {e}")
        return None


def _dedupe_window_iso() -> str:
    return (datetime.now(timezone.utc) - _DEDUPE_WINDOW).isoformat()


# 24h dedupe window keeps things un-spammy without missing genuine repeats.
from datetime import timedelta  # noqa: E402
_DEDUPE_WINDOW = timedelta(hours=24)


# ---------------------------------------------------------------------------
# Audience resolvers used by the broadcast endpoint
# ---------------------------------------------------------------------------
async def resolve_gallery_users(event_id: str, studio_id: str) -> list[str]:
    """All client user_ids who have ever accessed this gallery (matched or
    granted). Returns unique, non-empty user IDs.
    """
    # 1. Anyone with an active access grant on this event.
    grants = await db.access_grants.find(
        {"event_id": event_id, "status": "active"},
        {"_id": 0, "client_email": 1, "client_phone": 1},
    ).to_list(5000)

    emails = [g["client_email"].lower() for g in grants if g.get("client_email")]
    phones = [g["client_phone"] for g in grants if g.get("client_phone")]

    users_by_grant = []
    if emails or phones:
        cursor = db.users.find(
            {"$or": [{"email": {"$in": emails}}, {"phone": {"$in": phones}}], "role": "client"},
            {"_id": 0, "user_id": 1},
        )
        users_by_grant = [d["user_id"] async for d in cursor]

    # 2. Anyone who has a client album (i.e. ran face search on the gallery).
    album_cursor = db.client_albums.find(
        {"event_id": event_id}, {"_id": 0, "client_user_id": 1}
    )
    users_by_album = [d["client_user_id"] async for d in album_cursor]

    return sorted(set(users_by_grant + users_by_album) - {None, ""})


async def resolve_all_clients_for_studio(studio_id: str) -> list[str]:
    """Every client user_id linked to any event created by this studio."""
    events = await db.events.find({"created_by": studio_id}, {"_id": 0, "event_id": 1}).to_list(10000)
    event_ids = [e["event_id"] for e in events]
    if not event_ids:
        return []

    # union of grants + albums across all this studio's events
    grants_cursor = db.access_grants.find(
        {"event_id": {"$in": event_ids}, "status": "active"},
        {"_id": 0, "client_email": 1, "client_phone": 1},
    )
    emails: set[str] = set()
    phones: set[str] = set()
    async for g in grants_cursor:
        if g.get("client_email"):
            emails.add(g["client_email"].lower())
        if g.get("client_phone"):
            phones.add(g["client_phone"])

    users_ids: set[str] = set()
    if emails or phones:
        async for u in db.users.find(
            {"$or": [{"email": {"$in": list(emails)}}, {"phone": {"$in": list(phones)}}], "role": "client"},
            {"_id": 0, "user_id": 1},
        ):
            users_ids.add(u["user_id"])

    async for a in db.client_albums.find(
        {"event_id": {"$in": event_ids}}, {"_id": 0, "client_user_id": 1}
    ):
        if a.get("client_user_id"):
            users_ids.add(a["client_user_id"])

    return sorted(users_ids)
