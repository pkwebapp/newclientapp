"""Quotation API for PIK Connect (studio-admin scoped).

Endpoints:
  Admin   POST   /api/quotations
          GET    /api/quotations
          GET    /api/quotations/{id}
          PATCH  /api/quotations/{id}
          DELETE /api/quotations/{id}
          POST   /api/quotations/{id}/share
          GET    /api/quotations/{id}/pdf
          POST   /api/quotations/{id}/convert   {target: invoice|proforma}
  Public  GET    /api/public/quotations/{token}
          GET    /api/public/quotations/{token}/pdf
          POST   /api/public/quotations/{token}/respond  {action: accept|revision, note}

Letterhead (studio name/logo/address/phone/email/website/GSTIN) is pulled from
the shared invoice-settings profile so studios configure it in one place.
"""
from __future__ import annotations

import io
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import db, PUBLIC_BASE_URL
from auth_utils import require_admin
import invoice_service as svc
import quotation_service as qsvc
import invoice_routes as inv_routes
from notifications_service import notify

quotation_router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# models
# ---------------------------------------------------------------------------
class QuoteItemIn(BaseModel):
    description: str = Field(min_length=1)
    qty: float = Field(default=1, ge=0)
    rate: float = Field(default=0, ge=0)
    gst_rate: float = Field(default=0, ge=0, le=28)


class QuotationIn(BaseModel):
    client_id: Optional[str] = None
    client: Optional[inv_routes.PartyIn] = None
    event_id: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    show_pricing: bool = False
    gst_mode: str = "none"  # none | cgst_sgst | igst
    discount_amount: float = 0.0
    line_items: list[QuoteItemIn] = Field(default_factory=list)
    issue_date: Optional[str] = None
    valid_until: Optional[str] = None
    terms: Optional[str] = None
    notes: Optional[str] = None
    status: str = "sent"  # draft | sent


class QuotationUpdate(BaseModel):
    client_id: Optional[str] = None
    client: Optional[inv_routes.PartyIn] = None
    event_id: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    show_pricing: Optional[bool] = None
    gst_mode: Optional[str] = None
    discount_amount: Optional[float] = None
    line_items: Optional[list[QuoteItemIn]] = None
    issue_date: Optional[str] = None
    valid_until: Optional[str] = None
    terms: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class ShareIn(BaseModel):
    enabled: bool = True


class RespondIn(BaseModel):
    action: str  # accept | revision
    note: Optional[str] = Field(default=None, max_length=2000)


class ConvertIn(BaseModel):
    target: str = "invoice"  # invoice | proforma


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    subject: Optional[str] = None
    body: Optional[str] = None
    show_pricing: bool = False
    gst_mode: str = "none"
    discount_amount: float = 0.0
    line_items: list[QuoteItemIn] = Field(default_factory=list)
    terms: Optional[str] = None
    notes: Optional[str] = None


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    show_pricing: Optional[bool] = None
    gst_mode: Optional[str] = None
    discount_amount: Optional[float] = None
    line_items: Optional[list[QuoteItemIn]] = None
    terms: Optional[str] = None
    notes: Optional[str] = None


class SaveTemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _share_url(token: str) -> str:
    base = (PUBLIC_BASE_URL or "").rstrip("/")
    return f"{base}/q/{token}"


async def _quotation_or_404(quotation_id: str, studio_id: str) -> dict:
    doc = await db.quotations.find_one({"quotation_id": quotation_id, "studio_id": studio_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return doc


def _out(doc: dict) -> dict:
    out = qsvc.public_quotation(doc)
    if doc.get("share_enabled") and doc.get("share_token"):
        out["share_url"] = _share_url(doc["share_token"])
    return out


async def _compute_and_pack(data: dict, studio_id: str, admin: dict, existing: Optional[dict] = None) -> dict:
    settings = await inv_routes._settings_doc(studio_id, admin)
    client_override = data.get("client")
    if client_override is not None and not hasattr(client_override, "model_dump"):
        client_override = inv_routes.PartyIn(**client_override)
    if existing and client_override is None and not data.get("client_id"):
        client_id, client = existing.get("client_id"), existing.get("client") or {}
    else:
        client_id, client = await inv_routes._client_snapshot(
            studio_id, data.get("client_id"), client_override
        )
    event_id = data.get("event_id") or (existing or {}).get("event_id")

    show_pricing = data.get("show_pricing")
    if show_pricing is None:
        show_pricing = (existing or {}).get("show_pricing", False)
    gst_mode = data.get("gst_mode") or (existing or {}).get("gst_mode") or "none"
    discount = data.get("discount_amount")
    if discount is None:
        discount = (existing or {}).get("discount_amount", 0)

    raw_items = data.get("line_items")
    if raw_items is None:
        raw_items = (existing or {}).get("line_items", [])
    items = [
        {"description": it.get("description"), "qty": it.get("qty"), "rate": it.get("rate"), "gst_rate": it.get("gst_rate")}
        for it in raw_items
    ]

    pricing = qsvc.compute_quote_totals(items, gst_mode if show_pricing else "none", float(discount or 0)) if show_pricing else {
        "line_items": items, "subtotal": 0, "discount_amount": 0, "taxable_total": 0,
        "cgst_total": 0, "sgst_total": 0, "igst_total": 0, "tax_total": 0, "total": 0, "amount_in_words": "",
    }

    payload = {
        "studio_id": studio_id,
        "client_id": client_id,
        "client": client,
        "event_id": event_id,
        "studio": inv_routes._studio_snapshot(settings),
        "subject": (data.get("subject") if data.get("subject") is not None else (existing or {}).get("subject")) or "",
        "body": qsvc.clean_body(data.get("body") if data.get("body") is not None else (existing or {}).get("body")),
        "show_pricing": bool(show_pricing),
        "gst_mode": gst_mode,
        "issue_date": inv_routes._clean_date(data.get("issue_date"), "issue_date") or (existing or {}).get("issue_date") or inv_routes._today(),
        "valid_until": inv_routes._clean_date(data.get("valid_until"), "valid_until") or (existing or {}).get("valid_until"),
        "terms": (data.get("terms") if data.get("terms") is not None else (existing or {}).get("terms")) or "",
        "notes": (data.get("notes") if data.get("notes") is not None else (existing or {}).get("notes")) or "",
        **pricing,
    }
    return payload


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
@quotation_router.post("/quotations")
async def create_quotation(body: QuotationIn, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    settings = await inv_routes._settings_doc(studio_id, admin)
    payload = await _compute_and_pack(body.model_dump(), studio_id, admin)

    fy = svc.financial_year(payload["issue_date"])
    prefix = settings.get("quotation_prefix", "QUO-") or "QUO-"
    fmt_key = settings.get("number_format") or "prefix_seq"
    padding = int(settings.get("number_padding", 4) or 4)
    start_at = int(settings.get("number_start", 1) or 1)
    seq = await svc.next_seq(studio_id, "quotation", fy, start_at)
    number = svc.build_invoice_number(fmt_key, prefix, fy, seq, padding)

    now = svc.now_iso()
    qid = qsvc.new_quotation_id()
    doc = {
        "quotation_id": qid,
        "quotation_number": number,
        "seq": seq,
        "fy": fy,
        "status": "draft" if body.status == "draft" else "sent",
        "client_response": None,
        "converted_invoice_id": None,
        "share_enabled": False,
        "share_token": None,
        "revision_number": 1,
        "revision_of": None,
        "root_id": qid,
        "revision_note": None,
        "created_at": now,
        "updated_at": now,
        **payload,
    }
    await db.quotations.insert_one({**doc})
    return _out(doc)


@quotation_router.get("/quotations")
async def list_quotations(admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    docs = await db.quotations.find({"studio_id": studio_id}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return {"items": [_out(d) for d in docs], "count": len(docs)}


async def _thread_docs(root_id: str, studio_id: str) -> list[dict]:
    docs = await db.quotations.find(
        {"studio_id": studio_id, "$or": [{"root_id": root_id}, {"quotation_id": root_id}]},
        {"_id": 0, "quotation_id": 1, "quotation_number": 1, "revision_number": 1, "status": 1, "created_at": 1, "total": 1, "show_pricing": 1},
    ).to_list(500)
    docs.sort(key=lambda d: int(d.get("revision_number") or 1))
    return docs


@quotation_router.get("/quotations/{quotation_id}")
async def get_quotation(quotation_id: str, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    doc = await _quotation_or_404(quotation_id, studio_id)
    out = _out(doc)
    root_id = doc.get("root_id") or doc["quotation_id"]
    thread = await _thread_docs(root_id, studio_id)
    if len(thread) > 1:
        out["revisions"] = thread
    return out


@quotation_router.patch("/quotations/{quotation_id}")
async def update_quotation(quotation_id: str, body: QuotationUpdate, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    doc = await _quotation_or_404(quotation_id, studio_id)
    data = body.model_dump(exclude_unset=True)
    payload = await _compute_and_pack(data, studio_id, admin, existing=doc)
    updates = {**payload, "updated_at": svc.now_iso()}
    if "status" in data and data["status"] in ("draft", "sent"):
        updates["status"] = data["status"]
    await db.quotations.update_one({"quotation_id": quotation_id, "studio_id": studio_id}, {"$set": updates})
    return _out(await _quotation_or_404(quotation_id, studio_id))


@quotation_router.delete("/quotations/{quotation_id}")
async def delete_quotation(quotation_id: str, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    await _quotation_or_404(quotation_id, studio_id)
    await db.quotations.delete_one({"quotation_id": quotation_id, "studio_id": studio_id})
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# share + pdf
# ---------------------------------------------------------------------------
@quotation_router.post("/quotations/{quotation_id}/share")
async def share_quotation(quotation_id: str, body: ShareIn, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    doc = await _quotation_or_404(quotation_id, studio_id)
    token = doc.get("share_token") or svc.new_share_token()
    await db.quotations.update_one(
        {"quotation_id": quotation_id, "studio_id": studio_id},
        {"$set": {"share_enabled": bool(body.enabled), "share_token": token, "updated_at": svc.now_iso()}},
    )
    return _out(await _quotation_or_404(quotation_id, studio_id))


@quotation_router.get("/quotations/{quotation_id}/pdf")
async def quotation_pdf(quotation_id: str, admin: dict = Depends(require_admin)):
    doc = await _quotation_or_404(quotation_id, admin["user_id"])
    pdf = qsvc.render_quotation_pdf(doc)
    filename = f"{(doc.get('quotation_number') or 'quotation')}.pdf".replace("/", "-")
    return StreamingResponse(
        io.BytesIO(pdf), media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


# ---------------------------------------------------------------------------
# convert -> invoice / proforma
# ---------------------------------------------------------------------------
@quotation_router.post("/quotations/{quotation_id}/convert")
async def convert_quotation(quotation_id: str, body: ConvertIn, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    doc = await _quotation_or_404(quotation_id, studio_id)
    target = "proforma" if body.target == "proforma" else "invoice"

    items = doc.get("line_items") or []
    gst_mode = doc.get("gst_mode") or "none"
    if doc.get("show_pricing") and items:
        line_items = [
            inv_routes.LineItemIn(
                description=(it.get("description") or "Item"),
                qty=float(it.get("qty") or 1),
                rate=float(it.get("rate") or 0),
                gst_rate=(0 if gst_mode == "none" else float(it.get("gst_rate") or 0)),
            )
            for it in items
        ]
    else:
        # free-form quotation with no pricing table -> seed one line from the subject
        line_items = [inv_routes.LineItemIn(
            description=(doc.get("subject") or "Professional services"), qty=1, rate=0, gst_rate=0
        )]
        gst_mode = "none"

    client_party = inv_routes.PartyIn(**(doc.get("client") or {}))
    inv_body = inv_routes.InvoiceIn(
        client_id=doc.get("client_id"),
        client=client_party,
        event_id=doc.get("event_id"),
        doc_type=target,
        gst_mode=gst_mode,
        line_items=line_items,
        notes=doc.get("notes") or None,
        terms=doc.get("terms") or None,
        status="draft",
    )
    invoice = await inv_routes.create_invoice(inv_body, admin)

    await db.quotations.update_one(
        {"quotation_id": quotation_id, "studio_id": studio_id},
        {"$set": {"converted_invoice_id": invoice.get("invoice_id"), "converted_target": target, "updated_at": svc.now_iso()}},
    )
    return {"status": "converted", "target": target, "invoice": invoice}


# ---------------------------------------------------------------------------
# revision auto-draft
# ---------------------------------------------------------------------------
@quotation_router.post("/quotations/{quotation_id}/revise")
async def revise_quotation(quotation_id: str, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    src = await _quotation_or_404(quotation_id, studio_id)
    root_id = src.get("root_id") or src["quotation_id"]

    thread = await db.quotations.find(
        {"studio_id": studio_id, "$or": [{"root_id": root_id}, {"quotation_id": root_id}]},
        {"_id": 0, "revision_number": 1},
    ).to_list(500)
    max_rev = max([int(d.get("revision_number") or 1) for d in thread] + [1])
    new_rev = max_rev + 1

    note = ""
    if src.get("status") == "revision_requested":
        note = ((src.get("client_response") or {}).get("note") or "").strip()

    # migrate older source docs so the thread stays connected
    if not src.get("root_id"):
        await db.quotations.update_one(
            {"quotation_id": src["quotation_id"], "studio_id": studio_id},
            {"$set": {"root_id": root_id, "revision_number": int(src.get("revision_number") or 1)}},
        )

    now = svc.now_iso()
    new_id = qsvc.new_quotation_id()
    doc = {k: v for k, v in src.items() if k != "_id"}
    doc.update({
        "quotation_id": new_id,
        "status": "draft",
        "revision_number": new_rev,
        "revision_of": src["quotation_id"],
        "root_id": root_id,
        "revision_note": note or None,
        "client_response": None,
        "converted_invoice_id": None,
        "converted_target": None,
        "share_enabled": False,
        "share_token": None,
        "created_at": now,
        "updated_at": now,
    })
    await db.quotations.insert_one({**doc})
    return _out(doc)


# ---------------------------------------------------------------------------
# reusable templates
# ---------------------------------------------------------------------------
def _new_template_id() -> str:
    return f"qtpl_{uuid.uuid4().hex[:12]}"


def _template_out(doc: dict) -> dict:
    return {k: v for k, v in doc.items() if k not in ("_id", "name_lower")}


async def _create_template(data: TemplateIn, studio_id: str) -> dict:
    now = svc.now_iso()
    name = data.name.strip()
    items = [
        {"description": it.description, "qty": it.qty, "rate": it.rate, "gst_rate": it.gst_rate}
        for it in data.line_items if (it.description or "").strip()
    ]
    existing = await db.quotation_templates.find_one({"studio_id": studio_id, "name_lower": name.lower()})
    doc = {
        "template_id": existing["template_id"] if existing else _new_template_id(),
        "studio_id": studio_id,
        "name": name,
        "name_lower": name.lower(),
        "subject": data.subject or "",
        "body": qsvc.clean_body(data.body),
        "show_pricing": bool(data.show_pricing),
        "gst_mode": data.gst_mode or "none",
        "discount_amount": float(data.discount_amount or 0),
        "line_items": items,
        "terms": data.terms or "",
        "notes": data.notes or "",
        "created_at": existing["created_at"] if existing else now,
        "updated_at": now,
    }
    await db.quotation_templates.update_one(
        {"template_id": doc["template_id"], "studio_id": studio_id}, {"$set": doc}, upsert=True
    )
    return _template_out(doc)


@quotation_router.post("/quotation-templates")
async def create_template(body: TemplateIn, admin: dict = Depends(require_admin)):
    return await _create_template(body, admin["user_id"])


@quotation_router.get("/quotation-templates")
async def list_templates(admin: dict = Depends(require_admin)):
    docs = await db.quotation_templates.find({"studio_id": admin["user_id"]}, {"_id": 0}).sort("updated_at", -1).to_list(500)
    return {"items": [_template_out(d) for d in docs], "count": len(docs)}


@quotation_router.get("/quotation-templates/{template_id}")
async def get_template(template_id: str, admin: dict = Depends(require_admin)):
    doc = await db.quotation_templates.find_one({"template_id": template_id, "studio_id": admin["user_id"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Template not found")
    return _template_out(doc)


@quotation_router.patch("/quotation-templates/{template_id}")
async def update_template(template_id: str, body: TemplateUpdate, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    doc = await db.quotation_templates.find_one({"template_id": template_id, "studio_id": studio_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Template not found")
    data = body.model_dump(exclude_unset=True)
    updates: dict = {"updated_at": svc.now_iso()}
    if "name" in data and data["name"]:
        updates["name"] = data["name"].strip()
        updates["name_lower"] = data["name"].strip().lower()
    for key in ("subject", "body", "gst_mode", "terms", "notes"):
        if key in data:
            updates[key] = qsvc.clean_body(data[key]) if key == "body" else (data[key] or "")
    if "show_pricing" in data:
        updates["show_pricing"] = bool(data["show_pricing"])
    if "discount_amount" in data:
        updates["discount_amount"] = float(data["discount_amount"] or 0)
    if "line_items" in data and data["line_items"] is not None:
        updates["line_items"] = [
            {"description": it.get("description"), "qty": it.get("qty"), "rate": it.get("rate"), "gst_rate": it.get("gst_rate")}
            for it in data["line_items"] if (it.get("description") or "").strip()
        ]
    await db.quotation_templates.update_one({"template_id": template_id, "studio_id": studio_id}, {"$set": updates})
    fresh = await db.quotation_templates.find_one({"template_id": template_id, "studio_id": studio_id}, {"_id": 0})
    return _template_out(fresh)


@quotation_router.delete("/quotation-templates/{template_id}")
async def delete_template(template_id: str, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    res = await db.quotation_templates.delete_one({"template_id": template_id, "studio_id": studio_id})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"status": "deleted"}


@quotation_router.post("/quotations/{quotation_id}/save-as-template")
async def save_quotation_as_template(quotation_id: str, body: SaveTemplateIn, admin: dict = Depends(require_admin)):
    studio_id = admin["user_id"]
    src = await _quotation_or_404(quotation_id, studio_id)
    items = [
        QuoteItemIn(
            description=(it.get("description") or "Item"),
            qty=float(it.get("qty") or 1),
            rate=float(it.get("rate") or 0),
            gst_rate=float(it.get("gst_rate") or 0),
        )
        for it in (src.get("line_items") or []) if (it.get("description") or "").strip()
    ]
    tin = TemplateIn(
        name=body.name,
        subject=src.get("subject") or None,
        body=src.get("body") or None,
        show_pricing=bool(src.get("show_pricing")),
        gst_mode=src.get("gst_mode") or "none",
        discount_amount=float(src.get("discount_amount") or 0),
        line_items=items,
        terms=src.get("terms") or None,
        notes=src.get("notes") or None,
    )
    return await _create_template(tin, studio_id)


# ---------------------------------------------------------------------------
# public (shareable link)
# ---------------------------------------------------------------------------
@quotation_router.get("/public/quotations/{token}")
async def public_quotation_view(token: str):
    doc = await db.quotations.find_one({"share_token": token, "share_enabled": True}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Quotation not available")
    out = qsvc.public_quotation(doc)
    out.pop("share_url", None)
    return out


@quotation_router.get("/public/quotations/{token}/pdf")
async def public_quotation_pdf(token: str):
    doc = await db.quotations.find_one({"share_token": token, "share_enabled": True}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Quotation not available")
    pdf = qsvc.render_quotation_pdf(doc)
    filename = f"{(doc.get('quotation_number') or 'quotation')}.pdf".replace("/", "-")
    return StreamingResponse(
        io.BytesIO(pdf), media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@quotation_router.post("/public/quotations/{token}/respond")
async def public_quotation_respond(token: str, body: RespondIn):
    doc = await db.quotations.find_one({"share_token": token, "share_enabled": True}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Quotation not available")
    action = body.action if body.action in ("accept", "revision") else None
    if not action:
        raise HTTPException(status_code=400, detail="action must be 'accept' or 'revision'")
    status = "accepted" if action == "accept" else "revision_requested"
    response = {"action": action, "note": (body.note or "").strip(), "at": svc.now_iso()}
    await db.quotations.update_one(
        {"share_token": token},
        {"$set": {"status": status, "client_response": response, "updated_at": svc.now_iso()}},
    )
    client_name = (doc.get("client") or {}).get("name") or "A client"
    number = doc.get("quotation_number") or "quotation"
    if action == "accept":
        await notify(
            user_id=doc["studio_id"], type_key="quotation_accepted",
            title="Quotation accepted", body=f"{client_name} accepted {number}.",
            action_url=f"/admin/quotation/{doc['quotation_id']}",
        )
    else:
        note = response["note"]
        await notify(
            user_id=doc["studio_id"], type_key="quotation_changes",
            title="Quotation changes requested",
            body=f"{client_name} asked for changes to {number}." + (f" “{note}”" if note else ""),
            action_url=f"/admin/quotation/{doc['quotation_id']}",
        )
    return {"status": status, "client_response": response}
