"""Invoicing domain logic for PIK Connect.

Handles GST-compliant invoice math (per-line HSN/SAC + CGST/SGST/IGST split),
Indian amount-in-words, sequential invoice numbering, share tokens and PDF
rendering (via PyMuPDF's HTML Story engine — no system libraries required).

Revenue de-duplication note: an invoice may link to a gallery via ``event_id``.
The revenue engine (see invoice_routes.compute_revenue) counts the invoice and
excludes that gallery's manual shoot value so nothing is counted twice.
"""
from __future__ import annotations

import io
import re
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

import pymupdf  # PyMuPDF (installed) — used for HTML -> PDF rendering

from config import db, PUBLIC_BASE_URL

GST_MODES = {"none", "cgst_sgst", "igst"}


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_invoice_id() -> str:
    return f"inv_{uuid.uuid4().hex[:12]}"


def new_share_token() -> str:
    return secrets.token_urlsafe(24)


def _round2(x: float) -> float:
    return round(float(x or 0) + 1e-9, 2)


def money(x: float) -> str:
    """Indian-grouped currency string, e.g. 1,23,456.00 (no symbol)."""
    x = _round2(x)
    neg = x < 0
    x = abs(x)
    whole = int(x)
    frac = int(round((x - whole) * 100))
    s = str(whole)
    if len(s) > 3:
        head = s[:-3]
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
        s = f"{head},{s[-3:]}"
    out = f"{s}.{frac:02d}"
    return f"-{out}" if neg else out


# --- Indian amount in words -------------------------------------------------
_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
         "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
         "Seventeen", "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two(n: int) -> str:
    if n < 20:
        return _ONES[n]
    return (_TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")).strip()


def _three(n: int) -> str:
    h, rest = divmod(n, 100)
    out = ""
    if h:
        out += _ONES[h] + " Hundred"
        if rest:
            out += " and "
    if rest:
        out += _two(rest)
    return out.strip()


def amount_in_words(amount: float) -> str:
    """Rupees in words (Indian numbering)."""
    amount = _round2(amount)
    rupees = int(amount)
    paise = int(round((amount - rupees) * 100))
    if rupees == 0:
        words = "Zero"
    else:
        crore, rest = divmod(rupees, 10000000)
        lakh, rest = divmod(rest, 100000)
        thousand, rest = divmod(rest, 1000)
        parts = []
        if crore:
            parts.append(_two(crore) + " Crore")
        if lakh:
            parts.append(_two(lakh) + " Lakh")
        if thousand:
            parts.append(_two(thousand) + " Thousand")
        if rest:
            parts.append(_three(rest))
        words = " ".join(parts).strip()
    out = f"Rupees {words}"
    if paise:
        out += f" and {_two(paise)} Paise"
    return out + " Only"


# ---------------------------------------------------------------------------
# invoice math
# ---------------------------------------------------------------------------
def compute_totals(line_items: list[dict], gst_mode: str, discount_amount: float = 0.0,
                   round_off_enabled: bool = True) -> dict:
    """Return computed line rows + tax summary + grand total.

    Each incoming line item: {description, hsn_sac, qty, rate, gst_rate}
    Discount is an invoice-level flat amount, distributed proportionally across
    lines before tax so GST stays correct.
    """
    gst_mode = gst_mode if gst_mode in GST_MODES else "none"
    discount_amount = max(_round2(discount_amount), 0.0)

    rows = []
    subtotal = 0.0
    for li in line_items:
        qty = float(li.get("qty") or 0)
        rate = float(li.get("rate") or 0)
        amount = _round2(qty * rate)
        subtotal += amount
        rows.append({
            "description": (li.get("description") or "").strip(),
            "hsn_sac": (li.get("hsn_sac") or "").strip(),
            "qty": qty,
            "rate": _round2(rate),
            "gst_rate": float(li.get("gst_rate") or 0) if gst_mode != "none" else 0.0,
            "amount": amount,
        })

    subtotal = _round2(subtotal)
    discount_amount = min(discount_amount, subtotal)

    taxable_total = 0.0
    cgst_total = sgst_total = igst_total = 0.0
    by_rate: dict[float, dict] = {}

    for r in rows:
        share = (r["amount"] / subtotal) if subtotal > 0 else 0.0
        taxable = _round2(r["amount"] - discount_amount * share)
        r["taxable"] = taxable
        taxable_total += taxable
        gr = r["gst_rate"]
        tax = _round2(taxable * gr / 100.0) if gst_mode != "none" else 0.0
        if gst_mode == "cgst_sgst":
            r["cgst"] = _round2(tax / 2)
            r["sgst"] = _round2(tax / 2)
            r["igst"] = 0.0
            cgst_total += r["cgst"]
            sgst_total += r["sgst"]
        elif gst_mode == "igst":
            r["igst"] = tax
            r["cgst"] = r["sgst"] = 0.0
            igst_total += tax
        else:
            r["cgst"] = r["sgst"] = r["igst"] = 0.0
        r["tax"] = _round2(tax)

        bucket = by_rate.setdefault(gr, {"gst_rate": gr, "taxable": 0.0, "cgst": 0.0, "sgst": 0.0, "igst": 0.0})
        bucket["taxable"] = _round2(bucket["taxable"] + taxable)
        bucket["cgst"] = _round2(bucket["cgst"] + r["cgst"])
        bucket["sgst"] = _round2(bucket["sgst"] + r["sgst"])
        bucket["igst"] = _round2(bucket["igst"] + r["igst"])

    taxable_total = _round2(taxable_total)
    cgst_total = _round2(cgst_total)
    sgst_total = _round2(sgst_total)
    igst_total = _round2(igst_total)
    tax_total = _round2(cgst_total + sgst_total + igst_total)
    pre_round = _round2(taxable_total + tax_total)
    grand = round(pre_round) if round_off_enabled else pre_round
    round_off = _round2(grand - pre_round)

    return {
        "line_items": rows,
        "subtotal": subtotal,
        "discount_amount": _round2(discount_amount),
        "taxable_total": taxable_total,
        "cgst_total": cgst_total,
        "sgst_total": sgst_total,
        "igst_total": igst_total,
        "tax_total": tax_total,
        "round_off": round_off,
        "total": _round2(grand),
        "tax_summary": sorted(by_rate.values(), key=lambda b: b["gst_rate"]),
        "gst_mode": gst_mode,
    }


def payment_rollup(invoice: dict) -> dict:
    payments = invoice.get("payments") or []
    received = _round2(sum(float(p.get("amount") or 0) for p in payments))
    total = _round2(invoice.get("total") or 0)
    balance = _round2(max(total - received, 0))
    return {"amount_received": received, "balance_due": balance}


def derive_status(invoice: dict) -> str:
    """Auto status from payments unless explicitly cancelled/draft."""
    status = invoice.get("status")
    if status in ("cancelled", "draft"):
        return status
    roll = payment_rollup(invoice)
    total = _round2(invoice.get("total") or 0)
    if roll["amount_received"] <= 0:
        return "sent"
    if roll["amount_received"] >= total and total > 0:
        return "paid"
    return "partial"


# ---------------------------------------------------------------------------
# invoice numbering (per-studio sequence)
# ---------------------------------------------------------------------------
async def next_invoice_number(studio_id: str, prefix: str, start_at: int = 1) -> tuple[str, int]:
    doc = await db.invoice_counters.find_one_and_update(
        {"studio_id": studio_id},
        {"$inc": {"seq": 1}, "$setOnInsert": {"studio_id": studio_id, "base": start_at}},
        upsert=True,
        return_document=True,
    )
    base = int(doc.get("base") or start_at)
    seq = base - 1 + int(doc.get("seq") or 1)
    number = f"{prefix}{seq:04d}"
    return number, seq


# ---------------------------------------------------------------------------
# share link
# ---------------------------------------------------------------------------
def invoice_share_url(token: str) -> str:
    base = (PUBLIC_BASE_URL or "").rstrip("/")
    return f"{base}/i/{token}"


# ---------------------------------------------------------------------------
# serialization for API
# ---------------------------------------------------------------------------
def public_invoice(doc: dict) -> dict:
    if not doc:
        return {}
    out = {k: v for k, v in doc.items() if k != "_id"}
    roll = payment_rollup(doc)
    out["amount_received"] = roll["amount_received"]
    out["balance_due"] = roll["balance_due"]
    out["status"] = derive_status(doc)
    if doc.get("share_enabled") and doc.get("share_token"):
        out["share_url"] = invoice_share_url(doc["share_token"])
    return out


# ---------------------------------------------------------------------------
# PDF rendering (PyMuPDF HTML Story)
# ---------------------------------------------------------------------------
def _esc(s) -> str:
    s = "" if s is None else str(s)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _row_html(idx: int, r: dict, gst_mode: str) -> str:
    tax_cells = ""
    if gst_mode == "cgst_sgst":
        tax_cells = (
            f"<td class='num'>{r['gst_rate']:g}%</td>"
            f"<td class='num'>{money(r['cgst'])}</td>"
            f"<td class='num'>{money(r['sgst'])}</td>"
        )
    elif gst_mode == "igst":
        tax_cells = (
            f"<td class='num'>{r['gst_rate']:g}%</td>"
            f"<td class='num'>{money(r['igst'])}</td>"
        )
    return (
        "<tr>"
        f"<td class='num'>{idx}</td>"
        f"<td>{_esc(r['description'])}</td>"
        f"<td class='num'>{_esc(r['hsn_sac'])}</td>"
        f"<td class='num'>{r['qty']:g}</td>"
        f"<td class='num'>{money(r['rate'])}</td>"
        f"<td class='num'>{money(r['taxable'])}</td>"
        f"{tax_cells}"
        f"<td class='num'>{money(r['amount'] + r['tax'])}</td>"
        "</tr>"
    )


def build_invoice_html(inv: dict) -> str:
    studio = inv.get("studio") or {}
    client = inv.get("client") or {}
    gst_mode = inv.get("gst_mode") or "none"
    items = inv.get("line_items") or []

    if gst_mode == "cgst_sgst":
        tax_head = "<th class='num'>GST%</th><th class='num'>CGST</th><th class='num'>SGST</th>"
    elif gst_mode == "igst":
        tax_head = "<th class='num'>GST%</th><th class='num'>IGST</th>"
    else:
        tax_head = ""

    rows_html = "".join(_row_html(i + 1, r, gst_mode) for i, r in enumerate(items)) or (
        "<tr><td colspan='9'>No items</td></tr>"
    )

    # Totals block
    totals_rows = [f"<tr><td>Taxable Value</td><td class='num'>{money(inv.get('taxable_total'))}</td></tr>"]
    if inv.get("discount_amount"):
        totals_rows.insert(0, f"<tr><td>Discount</td><td class='num'>- {money(inv.get('discount_amount'))}</td></tr>")
    if gst_mode == "cgst_sgst":
        totals_rows.append(f"<tr><td>CGST</td><td class='num'>{money(inv.get('cgst_total'))}</td></tr>")
        totals_rows.append(f"<tr><td>SGST</td><td class='num'>{money(inv.get('sgst_total'))}</td></tr>")
    elif gst_mode == "igst":
        totals_rows.append(f"<tr><td>IGST</td><td class='num'>{money(inv.get('igst_total'))}</td></tr>")
    if inv.get("round_off"):
        totals_rows.append(f"<tr><td>Round Off</td><td class='num'>{money(inv.get('round_off'))}</td></tr>")
    totals_rows.append(f"<tr class='grand'><td>Total (INR)</td><td class='num'>Rs {money(inv.get('total'))}</td></tr>")
    roll = payment_rollup(inv)
    if roll["amount_received"]:
        totals_rows.append(f"<tr><td>Received</td><td class='num'>Rs {money(roll['amount_received'])}</td></tr>")
        totals_rows.append(f"<tr class='grand'><td>Balance Due</td><td class='num'>Rs {money(roll['balance_due'])}</td></tr>")

    def line(label, val):
        return f"<div><b>{_esc(label)}</b> {_esc(val)}</div>" if val else ""

    status = derive_status(inv).upper()

    html = f"""
    <div class="doc">
      <table class="head"><tr>
        <td class="seller">
          <div class="studio">{_esc(studio.get('name') or 'Studio')}</div>
          {line('', studio.get('address'))}
          {line('GSTIN:', studio.get('gstin'))}
          {line('State:', studio.get('state'))}
          {line('Phone:', studio.get('phone'))}
          {line('Email:', studio.get('email'))}
        </td>
        <td class="title">
          <div class="tax-invoice">TAX INVOICE</div>
          <div><b># </b>{_esc(inv.get('invoice_number'))}</div>
          <div><b>Date: </b>{_esc(inv.get('issue_date'))}</div>
          {line('Due:', inv.get('due_date'))}
          <div class="badge">{_esc(status)}</div>
        </td>
      </tr></table>

      <table class="parties"><tr>
        <td>
          <div class="lbl">BILL TO</div>
          <div class="cname">{_esc(client.get('name') or '-')}</div>
          {line('', client.get('address'))}
          {line('GSTIN:', client.get('gstin'))}
          {line('State:', client.get('state'))}
          {line('Phone:', client.get('phone'))}
          {line('Email:', client.get('email'))}
        </td>
        <td>
          {line('Place of Supply:', inv.get('place_of_supply'))}
          {line('Reference:', inv.get('reference'))}
        </td>
      </tr></table>

      <table class="items">
        <tr class="ihead">
          <th class="num">#</th><th>Item &amp; Description</th><th class="num">HSN/SAC</th>
          <th class="num">Qty</th><th class="num">Rate</th><th class="num">Taxable</th>
          {tax_head}<th class="num">Amount</th>
        </tr>
        {rows_html}
      </table>

      <table class="foot"><tr>
        <td class="words">
          <div class="lbl">Amount in Words</div>
          <div>{_esc(inv.get('amount_in_words') or amount_in_words(inv.get('total') or 0))}</div>
          {("<div class='lbl' style='margin-top:10px'>Notes</div><div>" + _esc(inv.get('notes')) + "</div>") if inv.get('notes') else ""}
          {("<div class='lbl' style='margin-top:10px'>Terms</div><div>" + _esc(inv.get('terms')) + "</div>") if inv.get('terms') else ""}
        </td>
        <td class="totals">
          <table>{''.join(totals_rows)}</table>
        </td>
      </tr></table>

      <div class="sign">For {_esc(studio.get('name') or 'Studio')}<br/><br/><br/>Authorised Signatory</div>
    </div>
    """
    return html


_INVOICE_CSS = """
* { font-family: sans-serif; font-size: 9.5pt; color: #1a1a1a; }
.doc { }
.studio { font-size: 15pt; font-weight: bold; color: #0f172a; }
.tax-invoice { font-size: 16pt; font-weight: bold; color: #E2623C; text-align: right; }
table { width: 100%; border-collapse: collapse; }
table.head td { vertical-align: top; padding: 2px 0; }
td.title { text-align: right; }
.badge { display: inline-block; margin-top: 6px; padding: 2px 8px; background: #F6E5DC; color: #C8532F; font-weight: bold; font-size: 8pt; }
table.parties { margin-top: 12px; border-top: 1px solid #e5e7eb; }
table.parties td { vertical-align: top; padding: 8px 6px; width: 50%; }
.lbl { color: #6b7280; font-size: 7.5pt; font-weight: bold; letter-spacing: 1px; }
.cname { font-weight: bold; font-size: 11pt; }
table.items { margin-top: 10px; }
table.items th { background: #E2623C; color: #ffffff; padding: 6px 5px; text-align: left; font-size: 8.5pt; }
table.items td { border-bottom: 1px solid #eee; padding: 6px 5px; vertical-align: top; }
.num { text-align: right; }
table.items th.num { text-align: right; }
table.foot { margin-top: 10px; }
table.foot td { vertical-align: top; padding: 4px; }
td.words { width: 58%; }
td.totals { width: 42%; }
td.totals table td { padding: 3px 6px; border-bottom: 1px solid #f0f0f0; }
tr.grand td { font-weight: bold; font-size: 11pt; color: #0f172a; border-top: 2px solid #E2623C; }
.sign { margin-top: 26px; text-align: right; color: #374151; }
"""


def render_invoice_pdf(inv: dict) -> bytes:
    """Render the invoice dict (already computed) to PDF bytes via PyMuPDF."""
    html = build_invoice_html(inv)
    buf = io.BytesIO()
    story = pymupdf.Story(html=html, user_css=_INVOICE_CSS)
    writer = pymupdf.DocumentWriter(buf)
    mediabox = pymupdf.paper_rect("a4")
    where = mediabox + (40, 40, -40, -50)
    more = 1
    while more:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
    return buf.getvalue()
