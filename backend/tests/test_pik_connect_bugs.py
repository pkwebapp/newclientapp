"""PIK Connect - focused tests for BUG1/BUG2/BUG3, cover thumbnail, and S3 import.
Also covers Rekognition-backed 'Beach Wedding (Demo)' regression."""
import io
import os
import uuid
import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get(
    "EXPO_PUBLIC_BACKEND_URL",
    "https://pkweb-client.preview.emergentagent.com",
).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"
DEMO_CLIENT_EMAIL = "datapkp23@gmail.com"
DEMO_EVENT_NAME = "Beach Wedding (Demo)"


def _jpeg(w=600, h=600, color=(200, 180, 160)):
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


# ----- Fixtures -----
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/admin/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["user"]["role"] == "admin"
    return d["session_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def client_token():
    r = requests.post(f"{API}/auth/client/request-otp",
                      json={"channel": "email", "email": DEMO_CLIENT_EMAIL})
    assert r.status_code == 200, r.text
    body = r.json()
    code = body.get("dev_code")
    assert code, f"expected dev_code in {body}"
    r2 = requests.post(f"{API}/auth/client/verify-otp",
                       json={"channel": "email", "email": DEMO_CLIENT_EMAIL, "code": code})
    assert r2.status_code == 200, r2.text
    d = r2.json()
    assert d["user"]["role"] == "client"
    return d["session_token"]


@pytest.fixture(scope="module")
def client_headers(client_token):
    return {"Authorization": f"Bearer {client_token}"}


@pytest.fixture(scope="module")
def demo_event(client_headers):
    r = requests.get(f"{API}/client/events", headers=client_headers)
    assert r.status_code == 200, r.text
    events = r.json()
    match = next((e for e in events if e.get("name") == DEMO_EVENT_NAME), None)
    assert match is not None, f"Demo event '{DEMO_EVENT_NAME}' not shared with {DEMO_CLIENT_EMAIL}. events={events}"
    return match


# ----- BUG1: Admin login -----
class TestBug1AdminLogin:
    def test_admin_login_success(self, admin_token):
        assert admin_token.startswith("st_")

    def test_admin_login_wrong_password(self):
        r = requests.post(f"{API}/auth/admin/login",
                          json={"email": ADMIN_EMAIL, "password": "wrongpass"})
        assert r.status_code == 401

    def test_admin_me(self, admin_headers):
        r = requests.get(f"{API}/auth/me", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "admin"


# ----- BUG2: Client has shared "Beach Wedding (Demo)" gallery -----
class TestBug2ClientDemoGallery:
    def test_client_sees_demo_gallery(self, demo_event):
        assert demo_event["name"] == DEMO_EVENT_NAME
        assert demo_event.get("event_id", "").startswith("evt_")

    def test_client_can_open_event_detail(self, client_headers, demo_event):
        r = requests.get(f"{API}/client/events/{demo_event['event_id']}",
                         headers=client_headers)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["event_id"] == demo_event["event_id"]
        assert "consent_given" in d
        assert "my_photos_count" in d

    def test_demo_event_has_6_indexed_photos(self, admin_headers, demo_event):
        r = requests.get(f"{API}/events/{demo_event['event_id']}/indexing-status",
                         headers=admin_headers)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["total_photos"] >= 6, f"expected >=6 photos, got {d}"
        assert d["indexed_photos"] >= 6, f"expected >=6 indexed, got {d}"
        assert d["status"] == "ready"


# ----- NEW: Cover thumbnail loads for granted client (no full access) via ?token= -----
class TestCoverThumbnailForClient:
    def test_client_can_fetch_cover_thumbnail(self, client_token, client_headers, demo_event):
        # get admin's view of event to know cover_path
        r_ev = requests.get(f"{API}/client/events/{demo_event['event_id']}",
                            headers=client_headers)
        assert r_ev.status_code == 200
        cover_path = r_ev.json().get("cover_path")
        # Fallback: some responses may put cover on list view
        if not cover_path:
            cover_path = demo_event.get("cover_path")
        assert cover_path, f"no cover_path found in event detail: {r_ev.json()}"

        # via ?token=
        r = requests.get(f"{API}/files/{cover_path}?token={client_token}")
        assert r.status_code == 200, f"expected 200 cover fetch, got {r.status_code} body={r.text[:200]}"
        assert r.headers.get("content-type", "").startswith("image/")

    def test_cover_unauth_still_blocked(self, demo_event, client_headers):
        r_ev = requests.get(f"{API}/client/events/{demo_event['event_id']}",
                            headers=client_headers)
        cover_path = r_ev.json().get("cover_path")
        if not cover_path:
            pytest.skip("no cover_path")
        r = requests.get(f"{API}/files/{cover_path}")
        assert r.status_code in (401, 403)


# ----- NEW: S3 import endpoint returns 200 status=imported (empty bucket ok) -----
class TestS3Import:
    def test_import_s3_empty_bucket(self, admin_headers, demo_event):
        r = requests.post(f"{API}/events/{demo_event['event_id']}/import-s3",
                          headers=admin_headers, json={})
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        d = r.json()
        assert d.get("status") == "imported", f"unexpected: {d}"
        # bucket may be empty
        assert "imported" in d


# ----- Regression: consent gate + selfie search + my-photos -----
class TestConsentAndSearch:
    def test_search_blocked_without_consent(self, client_headers, demo_event):
        # Need a fresh client to be sure consent not yet given for this event
        email = f"consent_probe_{uuid.uuid4().hex[:6]}@example.com"
        # grant access first (as admin)
        r_a = requests.post(f"{API}/auth/admin/login",
                            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        ah = {"Authorization": f"Bearer {r_a.json()['session_token']}"}
        gr = requests.post(f"{API}/events/{demo_event['event_id']}/access",
                           headers=ah,
                           json={"channel": "email", "email": email,
                                 "full_gallery_access": False})
        assert gr.status_code == 200
        # login client
        code = requests.post(f"{API}/auth/client/request-otp",
                             json={"channel": "email", "email": email}
                             ).json()["dev_code"]
        tok = requests.post(f"{API}/auth/client/verify-otp",
                            json={"channel": "email", "email": email, "code": code}
                            ).json()["session_token"]
        # attempt search without consent
        files = {"file": ("s.jpg", _jpeg(500, 500), "image/jpeg")}
        r = requests.post(f"{API}/client/events/{demo_event['event_id']}/search",
                          headers={"Authorization": f"Bearer {tok}"},
                          files=files)
        assert r.status_code == 403

    def test_consent_then_search_returns_matched_or_retake(self, client_headers, demo_event):
        r = requests.post(f"{API}/client/events/{demo_event['event_id']}/consent",
                          headers=client_headers, json={"accepted": True})
        assert r.status_code == 200
        # send a synthetic JPEG. Rekognition likely returns retake (no face) - both accepted.
        files = {"file": ("s.jpg", _jpeg(500, 500, (210, 180, 170)), "image/jpeg")}
        r2 = requests.post(f"{API}/client/events/{demo_event['event_id']}/search",
                           headers=client_headers, files=files)
        assert r2.status_code == 200, r2.text
        assert r2.json()["status"] in ("matched", "retake")

    def test_my_photos_endpoint(self, client_headers, demo_event):
        r = requests.get(f"{API}/client/events/{demo_event['event_id']}/my-photos",
                         headers=client_headers)
        assert r.status_code == 200
        d = r.json()
        assert "photos" in d and "count" in d


# ----- Regression: client without any grant cannot open unrelated event -----
class TestAccessControl:
    def test_client_without_grant_403_on_event(self, admin_headers):
        # create a private event as admin
        r = requests.post(f"{API}/events", headers=admin_headers,
                          json={"name": f"TEST_Private_{uuid.uuid4().hex[:6]}",
                                "category": "wedding", "similarity_threshold": 80})
        assert r.status_code == 200
        ev_id = r.json()["event_id"]
        # login unrelated client
        email = f"no_grant_{uuid.uuid4().hex[:6]}@example.com"
        code = requests.post(f"{API}/auth/client/request-otp",
                             json={"channel": "email", "email": email}
                             ).json()["dev_code"]
        tok = requests.post(f"{API}/auth/client/verify-otp",
                            json={"channel": "email", "email": email, "code": code}
                            ).json()["session_token"]
        r2 = requests.get(f"{API}/client/events/{ev_id}",
                          headers={"Authorization": f"Bearer {tok}"})
        assert r2.status_code == 403
