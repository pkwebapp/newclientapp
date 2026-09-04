"""Quotation domain logic: numbering, totals, premium letterhead PDF.

Reuses the shared primitives from invoice_service (FY numbering, counters,
share tokens, money/amount-in-words, PDF story renderer) so quotations stay
consistent with invoices and we don't duplicate battle-tested code.
"""
from __future__ import annotations

import io
import re
import uuid

import pymupdf  # type: ignore

import invoice_service as inv_svc
from invoice_service import _esc, _round2, amount_in_words, money, now_iso, new_share_token  # noqa: F401

CURRENCY = "INR"


def new_quotation_id() -> str:
    return f"quo_{uuid.uuid4().hex[:12]}"


def compute_quote_totals(items: list[dict], gst_mode: str = "none",
                         discount: float = 0.0) -> dict:
    """Optional pricing table math. Mirrors the invoice GST logic but simpler
    (a quotation is an estimate, not a statutory tax document)."""
    subtotal = 0.0
    rows = []
    for it in items or []:
        qty = float(it.get("qty") or 0)
        rate = float(it.get("rate") or 0)
        amount = _round2(qty * rate)
        subtotal += amount
        rows.append({
            "description": (it.get("description") or "").strip(),
            "qty": qty,
            "rate": _round2(rate),
            "gst_rate": 0 if gst_mode == "none" else float(it.get("gst_rate") or 0),
            "amount": amount,
        })
    subtotal = _round2(subtotal)
    disc = _round2(min(max(discount or 0, 0), subtotal))
    taxable = 0.0
    cgst = sgst = igst = 0.0
    for r in rows:
        share = (r["amount"] / subtotal) if subtotal > 0 else 0
        t = _round2(r["amount"] - disc * share)
        r["taxable"] = t
        taxable += t
        tax = 0.0 if gst_mode == "none" else _round2(t * (r["gst_rate"] or 0) / 100)
        r["tax"] = tax
        if gst_mode == "cgst_sgst":
            cgst += _round2(tax / 2)
            sgst += _round2(tax / 2)
        elif gst_mode == "igst":
            igst += tax
    taxable = _round2(taxable)
    cgst, sgst, igst = _round2(cgst), _round2(sgst), _round2(igst)
    tax_total = _round2(cgst + sgst + igst)
    total = _round2(taxable + tax_total)
    return {
        "line_items": rows,
        "subtotal": subtotal,
        "discount_amount": disc,
        "taxable_total": taxable,
        "cgst_total": cgst,
        "sgst_total": sgst,
        "igst_total": igst,
        "tax_total": tax_total,
        "total": total,
        "amount_in_words": amount_in_words(total) if total else "",
    }


def public_quotation(doc: dict) -> dict:
    out = {k: v for k, v in doc.items() if k != "_id"}
    out["body_html"] = render_body_html(doc)
    return out


# --------------------------------------------------------------------------
# Rich-text body (HTML) — sanitize on save, render with merge fields
# --------------------------------------------------------------------------
_HTML_TAG_RE = re.compile(r"<\s*/?\s*[a-zA-Z][^>]*>")
_TEXT_ALIGN_RE = re.compile(r"text-align\s*:\s*(left|center|right|justify)", re.I)
_MERGE_RE = re.compile(r"\{\{\s*([a-zA-Z_]+)\s*\}\}")

_ALLOWED_TAGS = {
    "p", "br", "b", "strong", "i", "em", "u", "s", "strike", "del", "mark", "sup", "sub",
    "h1", "h2", "h3", "h4", "ul", "ol", "li", "blockquote", "hr", "a", "span", "div",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td", "colgroup", "col",
}
_ALLOWED_ATTRS = {
    "a": {"href"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan"},
    "ol": {"start"},
    "*": {"style"},
}


def _style_filter(_tag: str, attr: str, value: str):
    if attr != "style":
        return value
    m = _TEXT_ALIGN_RE.search(value or "")
    return f"text-align: {m.group(1).lower()}" if m else None


def is_html(text: str | None) -> bool:
    return bool(text) and bool(_HTML_TAG_RE.search(text))


def sanitize_html(html: str) -> str:
    import nh3  # type: ignore

    return nh3.clean(
        html or "",
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        attribute_filter=_style_filter,
        strip_comments=True,
        link_rel="noopener noreferrer",
    ).strip()


def clean_body(text: str | None) -> str:
    """Normalise a body coming from the client: HTML is sanitised, plain text is kept as-is."""
    if not text:
        return ""
    return sanitize_html(text) if is_html(text) else text


def plain_to_html(text: str) -> str:
    paras = re.split(r"\n\s*\n", (text or "").replace("\r\n", "\n").strip())
    return "".join(f"<p>{_esc(p).replace(chr(10), '<br/>')}</p>" for p in paras if p.strip())


def merge_fields(q: dict) -> dict:
    client = q.get("client") or {}
    studio = q.get("studio") or {}
    total = q.get("total") or 0
    return {
        "client_name": client.get("name") or "",
        "client_phone": client.get("phone") or "",
        "client_email": client.get("email") or "",
        "studio_name": studio.get("name") or "",
        "quotation_number": q.get("quotation_number") or "",
        "issue_date": q.get("issue_date") or "",
        "valid_until": q.get("valid_until") or "",
        "subject": q.get("subject") or "",
        "total": f"Rs {money(total)}" if q.get("show_pricing") and total else "",
        "total_in_words": q.get("amount_in_words") or "",
    }


def render_body_html(q: dict) -> str:
    body = q.get("body") or ""
    if not body:
        return ""
    html = sanitize_html(body) if is_html(body) else plain_to_html(body)
    fields = merge_fields(q)
    return _MERGE_RE.sub(lambda m: _esc(fields[m.group(1)]) if m.group(1) in fields else m.group(0), html)


# --------------------------------------------------------------------------
# PDF (premium letterhead)
# --------------------------------------------------------------------------
def _nl2br(text: str) -> str:
    return _esc(text or "").replace("\n", "<br/>")


def build_quotation_html(q: dict) -> str:
    studio = q.get("studio") or {}
    client = q.get("client") or {}
    show_pricing = bool(q.get("show_pricing")) and (q.get("line_items"))
    gst_mode = q.get("gst_mode") or "none"

    logo = studio.get("logo_base64") or ""
    logo_img = (
        f"<img class='logo' src='{logo}' />" if isinstance(logo, str) and logo.startswith("data:image") else ""
    )

    def sline(label, val):
        return f"<div class='sl'>{(('<b>' + _esc(label) + '</b> ') if label else '')}{_esc(val)}</div>" if val else ""

    contact_bits = []
    for label, key in [("", "address"), ("Ph:", "phone"), ("", "email"), ("", "website"), ("GSTIN:", "gstin")]:
        v = studio.get(key)
        if v:
            contact_bits.append(f"{(label + ' ') if label else ''}{_esc(v)}")
    contact_line = "  &middot;  ".join(contact_bits)

    # Pricing table (optional)
    pricing_html = ""
    if show_pricing:
        tax_head = ""
        if gst_mode == "cgst_sgst":
            tax_head = "<th class='num'>GST%</th>"
        elif gst_mode == "igst":
            tax_head = "<th class='num'>GST%</th>"
        rows = ""
        for i, r in enumerate(q.get("line_items") or []):
            gst_cell = f"<td class='num'>{_esc(str(r.get('gst_rate') or 0))}%</td>" if gst_mode != "none" else ""
            rows += (
                f"<tr><td class='num'>{i + 1}</td>"
                f"<td>{_esc(r.get('description'))}</td>"
                f"<td class='num'>{_esc(str(r.get('qty')))}</td>"
                f"<td class='num'>{money(r.get('rate'))}</td>"
                f"{gst_cell}"
                f"<td class='num'>{money(r.get('amount'))}</td></tr>"
            )
        totals_rows = ""
        if q.get("discount_amount"):
            totals_rows += f"<tr><td>Discount</td><td class='num'>- {money(q.get('discount_amount'))}</td></tr>"
        totals_rows += f"<tr><td>Sub Total</td><td class='num'>{money(q.get('taxable_total'))}</td></tr>"
        if gst_mode == "cgst_sgst":
            totals_rows += f"<tr><td>CGST</td><td class='num'>{money(q.get('cgst_total'))}</td></tr>"
            totals_rows += f"<tr><td>SGST</td><td class='num'>{money(q.get('sgst_total'))}</td></tr>"
        elif gst_mode == "igst":
            totals_rows += f"<tr><td>IGST</td><td class='num'>{money(q.get('igst_total'))}</td></tr>"
        totals_rows += f"<tr class='grand'><td>Estimated Total (INR)</td><td class='num'>Rs {money(q.get('total'))}</td></tr>"
        words_cell = ""
        if q.get("amount_in_words"):
            words_cell = "<div class='lbl'>Amount in Words</div><div>" + _esc(q.get("amount_in_words")) + "</div>"
        pricing_html = f"""
        <table class="items">
          <tr class="ihead"><th class="num">#</th><th>Description</th><th class="num">Qty</th><th class="num">Rate</th>{tax_head}<th class="num">Amount</th></tr>
          {rows}
        </table>
        <table class="foot"><tr>
          <td class="words">{words_cell}</td>
          <td class="totals"><table>{totals_rows}</table></td>
        </tr></table>
        """

    valid_line = f"<div><b>Valid Until: </b>{_esc(q.get('valid_until'))}</div>" if q.get("valid_until") else ""
    status = (q.get("status") or "draft").replace("_", " ").upper()

    html = f"""
    <div class="doc">
      <table class="lh"><tr>
        <td class="lhlogo">{logo_img}</td>
        <td class="lhname">
          <div class="studio">{_esc(studio.get('name') or 'Studio')}</div>
          <div class="contact">{contact_line}</div>
        </td>
      </tr></table>
      <div class="rule"></div>

      <table class="head"><tr>
        <td class="qmeta">
          <div class="qtitle">QUOTATION</div>
          <div class="badge">{_esc(status)}</div>
        </td>
        <td class="qright">
          <div><b># </b>{_esc(q.get('quotation_number'))}</div>
          <div><b>Date: </b>{_esc(q.get('issue_date'))}</div>
          {valid_line}
        </td>
      </tr></table>

      <table class="parties"><tr>
        <td>
          <div class="lbl">PREPARED FOR</div>
          <div class="cname">{_esc(client.get('name') or '-')}</div>
          {sline('', client.get('address'))}
          {sline('GSTIN:', client.get('gstin'))}
          {sline('Ph:', client.get('phone'))}
          {sline('', client.get('email'))}
        </td>
      </tr></table>

      {('<div class="subject">' + _esc(q.get('subject')) + '</div>') if q.get('subject') else ''}
      {('<div class="body">' + render_body_html(q) + '</div>') if q.get('body') else ''}

      {pricing_html}

      {('<div class="block"><div class="lbl">TERMS &amp; CONDITIONS</div><div class="btext">' + _nl2br(q.get('terms')) + '</div></div>') if q.get('terms') else ''}
      {('<div class="block"><div class="lbl">NOTES</div><div class="btext">' + _nl2br(q.get('notes')) + '</div></div>') if q.get('notes') else ''}

      <div class="footer">Powered by www.pikconnect.com</div>
    </div>
    """
    return html


_QUOTATION_CSS = """
* { font-family: sans-serif; font-size: 9.5pt; color: #1a1a1a; }
.doc { }
table { width: 100%; border-collapse: collapse; }
table.lh td { vertical-align: middle; padding: 0; }
td.lhlogo { width: 90px; }
img.logo { width: 78px; height: 78px; object-fit: contain; }
.studio { font-size: 19pt; font-weight: bold; color: #0f172a; letter-spacing: 0.3px; }
.contact { color: #6b7280; font-size: 8.5pt; margin-top: 3px; line-height: 1.4; }
.rule { height: 3px; background: #E2623C; margin: 10px 0 4px 0; }
table.head td { vertical-align: top; padding: 6px 0; }
.qtitle { font-size: 20pt; font-weight: bold; color: #E2623C; letter-spacing: 3px; }
td.qright { text-align: right; }
.badge { display: inline-block; margin-top: 6px; padding: 2px 8px; background: #F6E5DC; color: #C8532F; font-weight: bold; font-size: 8pt; }
table.parties { margin-top: 8px; border-top: 1px solid #e5e7eb; }
table.parties td { vertical-align: top; padding: 10px 4px; }
.lbl { color: #6b7280; font-size: 7.5pt; font-weight: bold; letter-spacing: 1px; }
.cname { font-weight: bold; font-size: 12pt; margin-top: 2px; }
.sl { color: #374151; margin-top: 1px; }
.subject { font-size: 13pt; font-weight: bold; color: #0f172a; margin: 14px 0 6px 0; }
.body { color: #374151; line-height: 1.55; margin-bottom: 8px; }
.body p { margin: 0 0 6px 0; }
.body h1, .body h2, .body h3, .body h4 { color: #0f172a; font-weight: bold; line-height: 1.3; margin: 12px 0 4px 0; }
.body h1 { font-size: 15pt; }
.body h2 { font-size: 13pt; }
.body h3 { font-size: 11.5pt; }
.body h4 { font-size: 10.5pt; }
.body ul, .body ol { margin: 4px 0 8px 18px; padding: 0; }
.body li { margin: 2px 0; }
.body li p { margin: 0; }
.body table { width: 100%; border-collapse: collapse; margin: 8px 0 10px 0; }
.body th { background: #F6E5DC; color: #0f172a; font-weight: bold; text-align: left; padding: 5px 6px; border: 1px solid #e5e7eb; }
.body td { padding: 5px 6px; border: 1px solid #e5e7eb; vertical-align: top; }
.body td p, .body th p { margin: 0; }
.body blockquote { border-left: 3px solid #E2623C; margin: 6px 0; padding: 2px 10px; color: #4b5563; }
.body hr { border: none; border-top: 1px solid #e5e7eb; margin: 10px 0; }
.body a { color: #C8532F; }
table.items { margin-top: 12px; }
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
.block { margin-top: 14px; }
.btext { color: #374151; line-height: 1.5; margin-top: 3px; }
.footer { margin-top: 26px; padding-top: 10px; border-top: 1px solid #e5e7eb; text-align: center; color: #9aa0a6; font-size: 8pt; letter-spacing: 0.5px; }
"""


def render_quotation_pdf(q: dict) -> bytes:
    html = build_quotation_html(q)
    for candidate in (html, re.sub(r"<img[^>]*>", "", html)):
        try:
            buf = io.BytesIO()
            story = pymupdf.Story(html=candidate, user_css=_QUOTATION_CSS)
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
        except Exception:
            continue
    raise RuntimeError("Could not render quotation PDF")
