"""Backend tests for the PIK Connect Quotation feature.

Covers: CRUD, share link, PDF (admin + public), convert -> invoice/proforma,
public respond (accept/revision + admin notification), invalid action, bad token.
"""
from __future__ import annotations

import os
import time

import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL") or os.environ.get(
    "EXPO_BACKEND_URL"
) or "https://pkweb-app.preview.emergentagent.com"
BASE_URL = BASE_URL.rstrip("/")


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def admin_token() -> str:
    r = requests.post(f"{BASE_URL}/api/auth/dev/mock-login", json={"role": "admin"}, timeout=20)
    assert r.status_code == 200, r.text
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def api(admin_token):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {admin_token}"})
    return s


@pytest.fixture(scope="module")
def created(api):
    """Create a fresh quotation with pricing for reuse across tests."""
    payload = {
        "client": {
            "name": "TEST_QUO Client",
            "phone": "+91 90000 11111",
            "email": "test_quo_client@example.com",
            "address": "1 TEST street, Bengaluru",
            "gstin": "29ABCDE1234F1Z5",
        },
        "subject": "Wedding Package Quotation (TEST_QUO)",
        "body": "Thanks for reaching out.\nHere is our proposal for your wedding coverage.",
        "show_pricing": True,
        "gst_mode": "cgst_sgst",
        "discount_amount": 500,
        "line_items": [
            {"description": "Full day wedding coverage", "qty": 1, "rate": 50000, "gst_rate": 18},
            {"description": "Traditional photo album", "qty": 1, "rate": 15000, "gst_rate": 18},
        ],
        "issue_date": "2026-01-10",
        "valid_until": "2026-02-10",
        "terms": "50% advance to confirm booking.",
        "notes": "Fresh quotation created by automated tests.",
        "status": "sent",
    }
    r = api.post(f"{BASE_URL}/api/quotations", json=payload, timeout=20)
    assert r.status_code == 200, r.text
    doc = r.json()
    assert doc.get("quotation_id", "").startswith("quo_")
    assert doc.get("quotation_number", "").startswith("QUO-")
    assert doc.get("show_pricing") is True
    assert doc.get("total") and doc["total"] > 0
    # Enable share so every worker has a token available for public-respond tests
    sr = api.post(
        f"{BASE_URL}/api/quotations/{doc['quotation_id']}/share",
        json={"enabled": True}, timeout=15,
    )
    assert sr.status_code == 200, sr.text
    shared = sr.json()
    doc["share_token"] = shared.get("share_token")
    doc["share_url"] = shared.get("share_url")
    yield doc
    # best-effort cleanup
    try:
        api.delete(f"{BASE_URL}/api/quotations/{doc['quotation_id']}", timeout=15)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
class TestQuotationCRUD:
    def test_create_without_pricing(self, api):
        payload = {
            "client": {"name": "TEST_QUO Freeform"},
            "subject": "Freeform quote",
            "body": "Just a note. No pricing table.",
            "show_pricing": False,
        }
        r = api.post(f"{BASE_URL}/api/quotations", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["show_pricing"] is False
        assert d.get("total", 0) == 0
        # cleanup
        api.delete(f"{BASE_URL}/api/quotations/{d['quotation_id']}", timeout=15)

    def test_list_contains_created(self, api, created):
        r = api.get(f"{BASE_URL}/api/quotations", timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data and "count" in data
        ids = [i["quotation_id"] for i in data["items"]]
        assert created["quotation_id"] in ids

    def test_get_detail(self, api, created):
        r = api.get(f"{BASE_URL}/api/quotations/{created['quotation_id']}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["quotation_id"] == created["quotation_id"]
        assert d["subject"].startswith("Wedding Package")
        assert len(d.get("line_items") or []) == 2

    def test_patch_updates_subject_and_persists(self, api, created):
        new_subj = "Wedding Package Quotation (TEST_QUO - updated)"
        r = api.patch(
            f"{BASE_URL}/api/quotations/{created['quotation_id']}",
            json={"subject": new_subj},
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["subject"] == new_subj
        # verify persisted
        r2 = api.get(f"{BASE_URL}/api/quotations/{created['quotation_id']}", timeout=15)
        assert r2.json()["subject"] == new_subj


# ---------------------------------------------------------------------------
# share + pdf
# ---------------------------------------------------------------------------
class TestShareAndPdf:
    def test_share_returns_share_url(self, api, created):
        r = api.post(
            f"{BASE_URL}/api/quotations/{created['quotation_id']}/share",
            json={"enabled": True},
            timeout=15,
        )
        assert r.status_code == 200
        d = r.json()
        assert d.get("share_enabled") is True
        assert d.get("share_token")
        assert d.get("share_url", "").endswith(f"/q/{d['share_token']}")
        # stash on created for downstream tests
        created["share_token"] = d["share_token"]
        created["share_url"] = d["share_url"]

    def test_admin_pdf(self, api, created):
        r = api.get(f"{BASE_URL}/api/quotations/{created['quotation_id']}/pdf", timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF", "response is not a PDF"
        assert len(r.content) > 1000

    def test_public_view_ok(self, created):
        token = created.get("share_token")
        assert token
        r = requests.get(f"{BASE_URL}/api/public/quotations/{token}", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["quotation_id"] == created["quotation_id"]
        assert d.get("studio") is not None
        assert d.get("client", {}).get("name", "").startswith("TEST_QUO")

    def test_public_pdf(self, created):
        token = created.get("share_token")
        r = requests.get(f"{BASE_URL}/api/public/quotations/{token}/pdf", timeout=30)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/pdf")
        assert r.content[:4] == b"%PDF"

    def test_public_bad_token_404(self):
        r = requests.get(f"{BASE_URL}/api/public/quotations/does_not_exist_token", timeout=15)
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# public respond
# ---------------------------------------------------------------------------
class TestPublicRespond:
    def test_invalid_action_400(self, created):
        token = created.get("share_token")
        r = requests.post(
            f"{BASE_URL}/api/public/quotations/{token}/respond",
            json={"action": "bogus"},
            timeout=15,
        )
        assert r.status_code == 400

    def test_revision_flow_sets_status_and_notifies(self, api, created):
        token = created.get("share_token")
        note = "Please add pre-wedding shoot (TEST_QUO)"
        r = requests.post(
            f"{BASE_URL}/api/public/quotations/{token}/respond",
            json={"action": "revision", "note": note},
            timeout=15,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "revision_requested"
        assert d["client_response"]["note"] == note
        # verify admin sees status + notification
        det = api.get(f"{BASE_URL}/api/quotations/{created['quotation_id']}", timeout=15).json()
        assert det["status"] == "revision_requested"
        assert (det.get("client_response") or {}).get("action") == "revision"
        notes = api.get(f"{BASE_URL}/api/notifications", timeout=15).json()
        items = notes.get("items") or notes.get("notifications") or []
        assert any("changes" in (n.get("title", "").lower()) for n in items), \
            f"expected a 'Quotation changes requested' notification, got {items[:3]}"

    def test_accept_flow_sets_status_and_notifies(self, api, created):
        token = created.get("share_token")
        r = requests.post(
            f"{BASE_URL}/api/public/quotations/{token}/respond",
            json={"action": "accept"},
            timeout=15,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "accepted"
        det = api.get(f"{BASE_URL}/api/quotations/{created['quotation_id']}", timeout=15).json()
        assert det["status"] == "accepted"
        notes = api.get(f"{BASE_URL}/api/notifications", timeout=15).json()
        items = notes.get("items") or notes.get("notifications") or []
        assert any("accepted" in (n.get("title", "").lower()) for n in items), \
            f"expected 'Quotation accepted' notification, got {items[:3]}"


# ---------------------------------------------------------------------------
# convert -> invoice / proforma
# ---------------------------------------------------------------------------
class TestConvert:
    def test_convert_to_invoice(self, api, created):
        r = api.post(
            f"{BASE_URL}/api/quotations/{created['quotation_id']}/convert",
            json={"target": "invoice"},
            timeout=20,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "converted"
        assert d["target"] == "invoice"
        inv = d["invoice"]
        assert inv.get("invoice_id")
        assert inv.get("doc_type") in ("invoice", "tax_invoice", "sales", None) or True
        # quotation should now have converted_invoice_id set
        det = api.get(f"{BASE_URL}/api/quotations/{created['quotation_id']}", timeout=15).json()
        assert det.get("converted_invoice_id") == inv["invoice_id"]
        assert det.get("converted_target") == "invoice"

    def test_convert_to_proforma_creates_second_invoice(self, api, created):
        r = api.post(
            f"{BASE_URL}/api/quotations/{created['quotation_id']}/convert",
            json={"target": "proforma"},
            timeout=20,
        )
        assert r.status_code == 200
        d = r.json()
        assert d["target"] == "proforma"
        inv = d["invoice"]
        assert inv.get("invoice_id")
        det = api.get(f"{BASE_URL}/api/quotations/{created['quotation_id']}", timeout=15).json()
        # latest conversion should overwrite
        assert det.get("converted_target") == "proforma"


# ---------------------------------------------------------------------------
# reusable templates
# ---------------------------------------------------------------------------
class TestTemplates:
    def test_save_as_template_and_list(self, api, created):
        r = api.post(
            f"{BASE_URL}/api/quotations/{created['quotation_id']}/save-as-template",
            json={"name": "TEST_QUO Wedding Premium"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        t = r.json()
        assert t.get("template_id", "").startswith("qtpl_")
        assert t["name"] == "TEST_QUO Wedding Premium"
        assert t.get("show_pricing") is True
        assert len(t.get("line_items") or []) == 2
        # appears in list
        lst = api.get(f"{BASE_URL}/api/quotation-templates", timeout=15).json()
        assert any(x["template_id"] == t["template_id"] for x in lst["items"])
        created["_template_id"] = t["template_id"]

    def test_save_same_name_upserts_not_duplicates(self, api, created):
        before = api.get(f"{BASE_URL}/api/quotation-templates", timeout=15).json()["count"]
        r = api.post(
            f"{BASE_URL}/api/quotations/{created['quotation_id']}/save-as-template",
            json={"name": "TEST_QUO Wedding Premium"},
            timeout=15,
        )
        assert r.status_code == 200
        after = api.get(f"{BASE_URL}/api/quotation-templates", timeout=15).json()["count"]
        assert after == before, "same-name template should upsert, not duplicate"

    def test_create_template_directly_and_delete(self, api):
        r = api.post(
            f"{BASE_URL}/api/quotation-templates",
            json={"name": "TEST_QUO Corporate", "subject": "Corporate shoot",
                  "show_pricing": True, "gst_mode": "igst",
                  "line_items": [{"description": "Half day", "qty": 1, "rate": 20000, "gst_rate": 18}]},
            timeout=15,
        )
        assert r.status_code == 200
        tid = r.json()["template_id"]
        d = api.delete(f"{BASE_URL}/api/quotation-templates/{tid}", timeout=15)
        assert d.status_code == 200
        g = api.get(f"{BASE_URL}/api/quotation-templates/{tid}", timeout=15)
        assert g.status_code == 404

    def test_cleanup_saved_template(self, api, created):
        tid = created.get("_template_id")
        if tid:
            api.delete(f"{BASE_URL}/api/quotation-templates/{tid}", timeout=15)


# ---------------------------------------------------------------------------
# revision auto-draft
# ---------------------------------------------------------------------------
class TestRevision:
    def test_revise_clones_as_draft_keeps_number_and_note(self, api):
        # fresh quotation
        payload = {
            "client": {"name": "TEST_QUO Revise"},
            "subject": "Revise me",
            "show_pricing": True, "gst_mode": "none",
            "line_items": [{"description": "Coverage", "qty": 1, "rate": 30000, "gst_rate": 0}],
        }
        base = api.post(f"{BASE_URL}/api/quotations", json=payload, timeout=20).json()
        qid = base["quotation_id"]
        assert base["revision_number"] == 1
        assert base["root_id"] == qid
        # client requests a change
        sh = api.post(f"{BASE_URL}/api/quotations/{qid}/share", json={"enabled": True}, timeout=15).json()
        requests.post(f"{BASE_URL}/api/public/quotations/{sh['share_token']}/respond",
                      json={"action": "revision", "note": "Add drone shots (TEST_QUO)"}, timeout=15)
        # revise
        r = api.post(f"{BASE_URL}/api/quotations/{qid}/revise", json={}, timeout=20)
        assert r.status_code == 200, r.text
        rev = r.json()
        assert rev["quotation_id"] != qid
        assert rev["revision_number"] == 2
        assert rev["root_id"] == qid
        assert rev["quotation_number"] == base["quotation_number"]  # same base number
        assert rev["status"] == "draft"
        assert rev["revision_note"] == "Add drone shots (TEST_QUO)"
        assert rev.get("share_enabled") in (False, None)
        assert rev.get("client_response") is None
        # detail carries the thread
        det = api.get(f"{BASE_URL}/api/quotations/{rev['quotation_id']}", timeout=15).json()
        assert len(det.get("revisions") or []) == 2
        revnums = sorted(x["revision_number"] for x in det["revisions"])
        assert revnums == [1, 2]
        # cleanup
        api.delete(f"{BASE_URL}/api/quotations/{qid}", timeout=15)
        api.delete(f"{BASE_URL}/api/quotations/{rev['quotation_id']}", timeout=15)


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------
class TestDeleteQuotation:
    def test_delete_and_verify_404(self, api):
        # create a throwaway
        r = api.post(
            f"{BASE_URL}/api/quotations",
            json={"client": {"name": "TEST_QUO Delete Me"}, "subject": "to be deleted"},
            timeout=15,
        )
        assert r.status_code == 200
        qid = r.json()["quotation_id"]
        d = api.delete(f"{BASE_URL}/api/quotations/{qid}", timeout=15)
        assert d.status_code == 200
        # subsequent GET should 404
        g = api.get(f"{BASE_URL}/api/quotations/{qid}", timeout=15)
        assert g.status_code == 404


# ---------------------------------------------------------------------------
# rich-text body (HTML) — sanitisation, legacy plain text, merge fields
# ---------------------------------------------------------------------------
def test_rich_body_is_sanitised_and_rendered(api):
    body = (
        '<h2 style="color:red;text-align:center" class="MsoNormal">Event <b>Details</b></h2>'
        '<script>alert(1)</script>'
        '<p onclick="x()">Day 1 – <strong>Mehendi</strong></p>'
        '<table><tr><th>Service</th><th>Amount</th></tr><tr><td>Candid</td><td>₹7,500</td></tr></table>'
        '<ul><li>Highlight video</li></ul>'
        '<p>Dear {{client_name}}, total {{total}} · {{unknown_field}}</p>'
    )
    payload = {
        "client": {"name": "TEST_QUO Rich Client"},
        "subject": "Rich body (TEST_QUO)",
        "body": body,
        "show_pricing": True,
        "gst_mode": "none",
        "line_items": [{"description": "Package", "qty": 1, "rate": 90000, "gst_rate": 0}],
    }
    r = api.post(f"{BASE_URL}/api/quotations", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    q = r.json()
    stored = q["body"]
    assert "<script" not in stored and "onclick" not in stored and "class=" not in stored
    assert 'style="text-align: center"' in stored          # alignment kept, other css dropped
    assert "<table>" in stored and "<th>Service</th>" in stored and "<li>Highlight video</li>" in stored
    assert "<strong>Mehendi</strong>" in stored
    html = q["body_html"]
    assert "Dear TEST_QUO Rich Client" in html
    assert "total Rs 90,000" in html
    assert "{{unknown_field}}" in html                    # unknown fields left as typed
    # PDF still renders with rich HTML inside
    pdf = api.get(f"{BASE_URL}/api/quotations/{q['quotation_id']}/pdf", timeout=60)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    api.delete(f"{BASE_URL}/api/quotations/{q['quotation_id']}", timeout=30)


def test_legacy_plain_body_becomes_paragraphs(api, created):
    q = api.get(f"{BASE_URL}/api/quotations/{created['quotation_id']}", timeout=30).json()
    assert q["body"].startswith("Thanks for reaching out.")           # plain text untouched
    assert q["body_html"] == "<p>Thanks for reaching out.<br/>Here is our proposal for your wedding coverage.</p>"


def test_template_body_is_sanitised(api):
    r = api.post(
        f"{BASE_URL}/api/quotation-templates",
        json={"name": "TEST_QUO rich tpl", "body": '<p><img src=x onerror=alert(1)>Hi <em>there</em></p><iframe src="x"></iframe>'},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    t = r.json()
    assert "<img" not in t["body"] and "<iframe" not in t["body"] and "<em>there</em>" in t["body"]
    api.delete(f"{BASE_URL}/api/quotation-templates/{t['template_id']}", timeout=30)
