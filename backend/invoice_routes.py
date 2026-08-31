"""Invoice + Revenue API for PIK Connect (studio-admin scoped).

Endpoints (all require an admin/photographer, scoped to ``studio_id``):
  Settings   GET/PUT   /api/invoice-settings
  Invoices   POST      /api/invoices
             GET       /api/invoices
             GET       /api/invoices/{id}
             PATCH     /api/invoices/{id}
             DELETE    /api/invoices/{id}
             POST      /api/invoices/{id}/payments
             DELETE    /api/invoices/{id}/payments/{payment_id}
             POST      /api/invoices/{id}/share
             GET       /api/invoices/{id}/pdf
  Public     GET       /api/public/invoices/{token}
             GET       /api/public/invoices/{token}/pdf
  Revenue    GET       /api/revenue/summary
             GET       /api/revenue/records

Revenue de-dup: a gallery's shoot value is skipped when a (non-cancelled)
invoice links to that gallery via ``event_id`` — counted once.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import db
from auth_utils import require_admin
import invoice_service as svc

invoice_router = APIRouter(prefix="/api")

GST_RATES = {0, 3, 5, 12, 18, 28}


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------
class LineItemIn(BaseModel):
    description: str = Field(min_length=1)
    hsn_sac: Optional[str] = ""
    qty: float = Field(default=1, ge=0)
    rate: float = Field(default=0, ge=0)
    gst_rate: float = Field(default=18, ge=0, le=28)


class PartyIn(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    gstin: Optional[str] = None
    state: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class InvoiceIn(BaseModel):
    client_id: Optional[str] = None
    client: Optional[PartyIn] = None
    event_id: Optional[str] = None
    issue_date: Optional[str] = None
    due_date: Optional[str] = None
    place_of_supply: Optional[str] = None
    reference: Optional[str] = None
    gst_mode: str = "cgst_sgst"
    discount_amount: float = 0.0
    round_off_enabled: bool = True
    line_items: list[LineItemIn] = Field(default_factory=list)
    notes: Optional[str] = None
    terms: Optional[str] = None
    status: str = "sent"  # draft | sent


class InvoiceUpdate(BaseModel):
    client_id: Optional[str] = None
    client: Optional[PartyIn] = None
    event_id: Optional[str] = None
    issue_date: Optional[str] = None
    due_date: Optional[str] = None
    place_of_supply: Optional[str] = None
    reference: Optional[str] = None
    gst_mode: Optional[str] = None
    discount_amount: Optional[float] = None
    round_off_enabled: Optional[bool] = None
    line_items: Optional[list[LineItemIn]] = None
    notes: Optional[str] = None
    terms: Optional[str] = None
    status: Optional[str] = None  # draft | sent | cancelled


class PaymentIn(BaseModel):
    amount: float = Field(gt=0)
    method: Optional[str] = "cash"
    date: Optional[str] = None
    note: Optional[str] = None


class ShareIn(BaseModel):
    enabled: bool = True


class SettingsIn(BaseModel):
    legal_name: Optional[str] = None
    address: Optional[str] = None
    gstin: Optional[str] = None
    state: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    logo_base64: Optional[str] = None
    invoice_prefix: Optional[str] = None
    number_start: Optional[int] = None
    default_gst_rate: Optional[float] = None
    default_gst_mode: Optional[str] = None
    default_terms: Optional[str] = None
    place_of_supply_default: Optional[str] = None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _clean_date(v: Optional[str], field: str) -> Optional[str]:
    if v is None or not str(v).strip():
        return None
    try:
        return datetime.strptime(str(v).strip()[:10], "%Y-%m-%d").date().isoformat()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{field} must be YYYY-MM-DD") from exc


async def _settings_doc(studio_id: str, admin: dict) -> dict:
    doc = await db.invoice_settings.find_one({"studio_id": studio_id}, {"_id": 0})
    if doc:
        return doc
    sp = admin.get("studio_profile") or {}
    doc = {
        "studio_id": studio_id,
        "legal_name": sp.get("studio_name") or admin.get("name") or "My Studio",
        "address": sp.get("address") or "",
        "gstin": "",
        "state": sp.get("state") or "",
        "phone": sp.get("phone") or admin.get("phone") or "",
        "email": sp.get("booking_email") or admin.get("email") or "",
        "logo_base64": "",
        "invoice_prefix": "INV-",
        "number_start": 1,
        "default_gst_rate": 18,
        "default_gst_mode": "cgst_sgst",
        "default_terms": "Thank you for your business.",
        "place_of_supply_default": sp.get("state") or "",
    }
    await db.invoice_settings.insert_one({**doc})
    return doc


def _studio_snapshot(s: dict) -> dict:
    return {
        "name": s.get("legal_name"),
        "address": s.get("address"),
        "gstin": s.get("gstin"),
        "state": s.get("state"),
        "phone": s.get("phone"),
        "email": s.get("email"),
        "logo_base64": s.get("logo_base64") or "",
    }


async def _client_snapshot(studio_id: str, client_id: Optional[str], override: Optional[PartyIn]) -> tuple[Optional[str], dict]:
    snap = {"name": None, "address": None, "gstin": None, "state": None, "phone": None, "email": None}
    if client_id:
        c = await db.clients.find_one({"client_id": client_id, "studio_id": studio_id}, {"_id": 0})
        if not c:
            raise HTTPException(status_code=404, detail="Client not found")
        snap["name"] = c.get("name")
        snap["address"] = c.get("address")
        snap["gstin"] = c.get("gstin")
        snap["state"] = c.get("state")
        primary = await db.contacts.find_one({"client_id": client_id, "is_primary": True}, {"_id": 0}) \
            or await db.contacts.find_one({"client_id": client_id}, {"_id": 0})
        if primary:
            snap["phone"] = primary.get("phone")
            snap["email"] = primary.get("email")
    if override:
        for k, v in override.model_dump(exclude_unset=True).items():
            if v is not None and str(v).strip() != "":
                snap[k] = v
    if not snap["name"]:
        snap["name"] = "Client"
    return client_id, snap


async def _compute_and_pack(body: InvoiceIn | dict, studio_id: str, admin: dict, existing: Optional[dict] = None) -> dict:
    """Build the computed invoice payload (without number) from input."""
    data = body if isinstance(body, dict) else body.model_dump()
    settings = await _settings_doc(studio_id, admin)

    gst_mode = data.get("gst_mode") or "cgst_sgst"
    if gst_mode not in svc.GST_MODES:
        raise HTTPException(status_code=400, detail="gst_mode must be none, cgst_sgst or igst")

    items = data.get("line_items") or []
    items = [i.model_dump() if isinstance(i, LineItemIn) else i for i in items]
    if not items:
        raise HTTPException(status_code=400, detail="Add at least one line item")

    totals = svc.compute_totals(
        items, gst_mode,
        discount_amount=float(data.get("discount_amount") or 0),
        round_off_enabled=bool(data.get("round_off_enabled", True)),
    )

    client_id, client = await _client_snapshot(studio_id, data.get("client_id"), data.get("client") if isinstance(data.get("client"), PartyIn) else (PartyIn(**data["client"]) if data.get("client") else None))

    event_id = data.get("event_id")
    event_name = None
    if event_id:
        ev = await db.events.find_one({"event_id": event_id, "created_by": studio_id}, {"_id": 0, "name": 1})
        if not ev:
            raise HTTPException(status_code=404, detail="Gallery not found")
        event_name = ev.get("name")

    payload = {
        **totals,
        "studio_id": studio_id,
        "client_id": client_id,
        "client": client,
        "event_id": event_id,
        "event_name": event_name,
        "studio": _studio_snapshot(settings),
        "issue_date": _clean_date(data.get("issue_date"), "issue_date") or (existing or {}).get("issue_date") or _today(),
        "due_date": _clean_date(data.get("due_date"), "due_date"),
        "place_of_supply": data.get("place_of_supply") or settings.get("place_of_supply_default") or "",
        "reference": data.get("reference"),
        "notes": data.get("notes"),
        "terms": data.get("terms") if data.get("terms") is not None else settings.get("default_terms"),
        "currency": "INR",
        "amount_in_words": svc.amount_in_words(totals["total"]),
    }
    return payload


# ---------------------------------------------------------------------------
# settings
# ---------------------------------------------------------------------------
@invoice_router.get("/invoice-settings")
async def get_invoice_settings(admin: dict = Depends(require_admin)):
    settings = await _settings_doc(admin["user_id"], admin)
    counter = await db.invoice_counters.find_one({"studio_id": admin["user_id"]}, {"_id": 0})
    next_seq = (int(counter.get("base", settings.get("number_start", 1))) if counter else settings.get("number_start", 1))
    if counter:
        next_seq = int(counter.get("base", 1)) - 1 + int(counter.get("seq", 0)) + 1
    return {**settings, "next_number_preview": f"{settings.get('invoice_prefix', 'INV-')}{next_seq:04d}"}


@invoice_router.put("/invoice-settings")
async def update_invoice_settings(body: SettingsIn, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    await _settings_doc(studio_id, admin)
    updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if "default_gst_mode" in updates and updates["default_gst_mode"] not in svc.GST_MODES:
        raise HTTPException(status_code=400, detail="Invalid default_gst_mode")
    if updates:
        await db.invoice_settings.update_one({"studio_id": studio_id}, {"$set": updates})
    return await get_invoice_settings(admin)


# ---------------------------------------------------------------------------
# invoices CRUD
# ---------------------------------------------------------------------------
@invoice_router.post("/invoices")
async def create_invoice(body: InvoiceIn, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    settings = await _settings_doc(studio_id, admin)
    payload = await _compute_and_pack(body, studio_id, admin)

    number, seq = await svc.next_invoice_number(
        studio_id, settings.get("invoice_prefix", "INV-"), int(settings.get("number_start", 1))
    )
    now = svc.now_iso()
    doc = {
        "invoice_id": svc.new_invoice_id(),
        "invoice_number": number,
        "seq": seq,
        "status": "draft" if body.status == "draft" else "sent",
        "payments": [],
        "share_enabled": False,
        "share_token": None,
        "created_at": now,
        "updated_at": now,
        **payload,
    }
    await db.invoices.insert_one({**doc})
    return svc.public_invoice(doc)


@invoice_router.get("/invoices")
async def list_invoices(
    admin: dict = Depends(require_admin),
    status: Optional[str] = None,
    client_id: Optional[str] = None,
    event_id: Optional[str] = None,
    q: Optional[str] = None,
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
):
    studio_id = admin["user_id"]
    query: dict = {"studio_id": studio_id}
    if status:
        query["status"] = status
    if client_id:
        query["client_id"] = client_id
    if event_id:
        query["event_id"] = event_id
    df = _clean_date(date_from, "from")
    dt = _clean_date(date_to, "to")
    if df or dt:
        rng: dict = {}
        if df:
            rng["$gte"] = df
        if dt:
            rng["$lte"] = dt
        query["issue_date"] = rng

    docs = await db.invoices.find(query, {"_id": 0}).sort("created_at", -1).to_list(2000)
    out = [svc.public_invoice(d) for d in docs]
    if q:
        ql = q.strip().lower()
        out = [d for d in out if ql in (d.get("invoice_number") or "").lower()
               or ql in ((d.get("client") or {}).get("name") or "").lower()]
    # lightweight aggregate for the list header
    booked = sum(d.get("total") or 0 for d in out if d.get("status") != "cancelled")
    received = sum(d.get("amount_received") or 0 for d in out if d.get("status") != "cancelled")
    return {"items": out, "count": len(out), "booked": round(booked, 2), "received": round(received, 2)}


async def _invoice_or_404(invoice_id: str, studio_id: str) -> dict:
    doc = await db.invoices.find_one({"invoice_id": invoice_id, "studio_id": studio_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return doc


@invoice_router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: str, admin: dict = Depends(require_admin)):
    doc = await _invoice_or_404(invoice_id, admin["user_id"])
    return svc.public_invoice(doc)


@invoice_router.patch("/invoices/{invoice_id}")
async def update_invoice(invoice_id: str, body: InvoiceUpdate, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    doc = await _invoice_or_404(invoice_id, studio_id)

    if body.status == "cancelled":
        await db.invoices.update_one({"invoice_id": invoice_id}, {"$set": {"status": "cancelled", "updated_at": svc.now_iso()}})
        return svc.public_invoice(await _invoice_or_404(invoice_id, studio_id))

    # Merge existing + patch, then recompute if anything money-related changed.
    data = body.model_dump(exclude_unset=True)
    merged = {
        "client_id": data.get("client_id", doc.get("client_id")),
        "client": PartyIn(**data["client"]) if isinstance(data.get("client"), dict) else (doc.get("client")),
        "event_id": data.get("event_id", doc.get("event_id")),
        "issue_date": data.get("issue_date", doc.get("issue_date")),
        "due_date": data.get("due_date", doc.get("due_date")),
        "place_of_supply": data.get("place_of_supply", doc.get("place_of_supply")),
        "reference": data.get("reference", doc.get("reference")),
        "gst_mode": data.get("gst_mode", doc.get("gst_mode")),
        "discount_amount": data.get("discount_amount", doc.get("discount_amount")),
        "round_off_enabled": data.get("round_off_enabled", doc.get("round_off_enabled", True)),
        "line_items": data.get("line_items", doc.get("line_items")),
        "notes": data.get("notes", doc.get("notes")),
        "terms": data.get("terms", doc.get("terms")),
    }
    # client snapshot: if a raw dict already stored, keep it when no override
    if isinstance(merged["client"], dict):
        # convert stored snapshot to override only when client_id unchanged & no new client
        merged["client"] = PartyIn(**{k: merged["client"].get(k) for k in ("name", "address", "gstin", "state", "phone", "email")}) if not data.get("client_id") else None
    payload = await _compute_and_pack(merged, studio_id, admin, existing=doc)

    updates = {**payload, "updated_at": svc.now_iso()}
    if data.get("status") in ("draft", "sent"):
        updates["status"] = data["status"]
    await db.invoices.update_one({"invoice_id": invoice_id}, {"$set": updates})
    return svc.public_invoice(await _invoice_or_404(invoice_id, studio_id))


@invoice_router.delete("/invoices/{invoice_id}")
async def delete_invoice(invoice_id: str, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    await _invoice_or_404(invoice_id, studio_id)
    await db.invoices.delete_one({"invoice_id": invoice_id, "studio_id": studio_id})
    return {"ok": True}


# ---------------------------------------------------------------------------
# payments
# ---------------------------------------------------------------------------
@invoice_router.post("/invoices/{invoice_id}/payments")
async def add_payment(invoice_id: str, body: PaymentIn, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    doc = await _invoice_or_404(invoice_id, studio_id)
    payment = {
        "payment_id": f"pay_{svc.uuid.uuid4().hex[:10]}",
        "amount": svc._round2(body.amount),
        "method": body.method or "cash",
        "date": _clean_date(body.date, "date") or _today(),
        "note": body.note,
        "created_at": svc.now_iso(),
    }
    await db.invoices.update_one(
        {"invoice_id": invoice_id, "studio_id": studio_id},
        {"$push": {"payments": payment}, "$set": {"updated_at": svc.now_iso()}},
    )
    fresh = await _invoice_or_404(invoice_id, studio_id)
    new_status = svc.derive_status(fresh)
    if new_status != fresh.get("status") and fresh.get("status") not in ("cancelled", "draft"):
        await db.invoices.update_one({"invoice_id": invoice_id}, {"$set": {"status": new_status}})
        fresh["status"] = new_status
    return svc.public_invoice(fresh)


@invoice_router.delete("/invoices/{invoice_id}/payments/{payment_id}")
async def delete_payment(invoice_id: str, payment_id: str, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    await _invoice_or_404(invoice_id, studio_id)
    await db.invoices.update_one(
        {"invoice_id": invoice_id, "studio_id": studio_id},
        {"$pull": {"payments": {"payment_id": payment_id}}, "$set": {"updated_at": svc.now_iso()}},
    )
    return svc.public_invoice(await _invoice_or_404(invoice_id, studio_id))


# ---------------------------------------------------------------------------
# share + pdf
# ---------------------------------------------------------------------------
@invoice_router.post("/invoices/{invoice_id}/share")
async def share_invoice(invoice_id: str, body: ShareIn, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    doc = await _invoice_or_404(invoice_id, studio_id)
    token = doc.get("share_token") or svc.new_share_token()
    await db.invoices.update_one(
        {"invoice_id": invoice_id, "studio_id": studio_id},
        {"$set": {"share_enabled": bool(body.enabled), "share_token": token, "updated_at": svc.now_iso()}},
    )
    fresh = await _invoice_or_404(invoice_id, studio_id)
    return svc.public_invoice(fresh)


@invoice_router.get("/invoices/{invoice_id}/pdf")
async def invoice_pdf(invoice_id: str, admin: dict = Depends(require_admin)):
    doc = await _invoice_or_404(invoice_id, admin["user_id"])
    pdf = svc.render_invoice_pdf(doc)
    filename = f"{doc.get('invoice_number', 'invoice')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf), media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# public (shareable link)
# ---------------------------------------------------------------------------
@invoice_router.get("/public/invoices/{token}")
async def public_invoice_view(token: str):
    doc = await db.invoices.find_one({"share_token": token, "share_enabled": True}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Invoice not available")
    out = svc.public_invoice(doc)
    out.pop("share_url", None)  # keep public payload clean
    return out


@invoice_router.get("/public/invoices/{token}/pdf")
async def public_invoice_pdf(token: str):
    doc = await db.invoices.find_one({"share_token": token, "share_enabled": True}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Invoice not available")
    pdf = svc.render_invoice_pdf(doc)
    filename = f"{doc.get('invoice_number', 'invoice')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf), media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# revenue engine
# ---------------------------------------------------------------------------
def _pick_date(iso_or_none: Optional[str], fallback: Optional[str]) -> Optional[str]:
    v = iso_or_none or fallback or ""
    return v[:10] if v else None


def _period_range(period: str, dfrom: Optional[str], dto: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    today = datetime.now(timezone.utc).date()
    if period == "this_month":
        return today.replace(day=1).isoformat(), today.isoformat()
    if period == "this_year":
        return today.replace(month=1, day=1).isoformat(), today.isoformat()
    if period == "custom":
        return (dfrom or None), (dto or None)
    return None, None  # all


def _in_range(d: Optional[str], start: Optional[str], end: Optional[str]) -> bool:
    if not d:
        return start is None and end is None
    if start and d < start:
        return False
    if end and d > end:
        return False
    return True


async def compute_revenue(studio_id: str, start: Optional[str], end: Optional[str]) -> dict:
    invoices = await db.invoices.find(
        {"studio_id": studio_id, "status": {"$ne": "cancelled"}}, {"_id": 0}
    ).to_list(5000)
    events = await db.events.find(
        {"created_by": studio_id, "status": {"$ne": "deleted"}}, {"_id": 0}
    ).to_list(5000)

    invoiced_event_ids = {i.get("event_id") for i in invoices if i.get("event_id")}

    inv_booked = inv_collected = 0.0
    inv_count = 0
    records = []
    for i in invoices:
        d = _pick_date(i.get("issue_date"), i.get("created_at"))
        if not _in_range(d, start, end):
            continue
        roll = svc.payment_rollup(i)
        inv_booked += float(i.get("total") or 0)
        inv_collected += roll["amount_received"]
        inv_count += 1
        records.append({
            "type": "invoice",
            "ref_id": i.get("invoice_id"),
            "number": i.get("invoice_number"),
            "title": (i.get("client") or {}).get("name") or "Invoice",
            "date": d,
            "booked": round(float(i.get("total") or 0), 2),
            "collected": roll["amount_received"],
            "status": svc.derive_status(i),
            "event_id": i.get("event_id"),
        })

    gal_booked = gal_collected = 0.0
    gal_count = 0
    for e in events:
        if e.get("event_id") in invoiced_event_ids:
            continue  # superseded by an invoice — avoid double count
        val = float(e.get("value") or 0)
        if val <= 0:
            continue
        d = _pick_date(e.get("date"), e.get("created_at"))
        if not _in_range(d, start, end):
            continue
        gal_booked += val
        gal_collected += val  # uninvoiced galleries: shoot value treated as received
        gal_count += 1
        records.append({
            "type": "gallery",
            "ref_id": e.get("event_id"),
            "number": None,
            "title": e.get("name") or "Gallery",
            "date": d,
            "booked": round(val, 2),
            "collected": round(val, 2),
            "status": "received",
            "event_id": e.get("event_id"),
        })

    booked = round(inv_booked + gal_booked, 2)
    collected = round(inv_collected + gal_collected, 2)
    records.sort(key=lambda r: (r.get("date") or ""), reverse=True)

    return {
        "booked": booked,
        "collected": collected,
        "pending": round(max(booked - collected, 0), 2),
        "invoice_count": inv_count,
        "gallery_count": gal_count,
        "by_source": {
            "invoices": {"booked": round(inv_booked, 2), "collected": round(inv_collected, 2), "count": inv_count},
            "galleries": {"booked": round(gal_booked, 2), "collected": round(gal_collected, 2), "count": gal_count},
        },
        "records": records,
        "gallery_collected_assumed": True,
    }


def _last_12_months() -> list[str]:
    today = datetime.now(timezone.utc).date()
    out = []
    y, m = today.year, today.month
    for _ in range(12):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    return list(reversed(out))


@invoice_router.get("/revenue/summary")
async def revenue_summary(
    admin: dict = Depends(require_admin),
    period: str = "this_month",
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
):
    studio_id = admin["user_id"]
    start, end = _period_range(period, _clean_date(date_from, "from"), _clean_date(date_to, "to"))
    data = await compute_revenue(studio_id, start, end)

    # Monthly trend (rolling 12 months, independent of the period filter)
    full = await compute_revenue(studio_id, None, None)
    months = _last_12_months()
    buckets = {mo: {"month": mo, "booked": 0.0, "collected": 0.0} for mo in months}
    for r in full["records"]:
        d = r.get("date") or ""
        key = d[:7]
        if key in buckets:
            buckets[key]["booked"] = round(buckets[key]["booked"] + r["booked"], 2)
            buckets[key]["collected"] = round(buckets[key]["collected"] + r["collected"], 2)
    monthly = [buckets[mo] for mo in months]

    summary = {k: v for k, v in data.items() if k != "records"}
    summary["period"] = period
    summary["from"] = start
    summary["to"] = end
    summary["monthly"] = monthly
    summary["all_time"] = {"booked": full["booked"], "collected": full["collected"], "pending": full["pending"]}
    return summary


@invoice_router.get("/revenue/records")
async def revenue_records(
    admin: dict = Depends(require_admin),
    period: str = "this_month",
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
):
    studio_id = admin["user_id"]
    start, end = _period_range(period, _clean_date(date_from, "from"), _clean_date(date_to, "to"))
    data = await compute_revenue(studio_id, start, end)
    return {"items": data["records"], "count": len(data["records"]),
            "booked": data["booked"], "collected": data["collected"], "pending": data["pending"]}
