"""End-to-end backend tests for Lumiere Gallery API."""
import io
import os
import uuid
import pytest
import requests
from PIL import Image

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://repo-pull-dev.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SEED_ADMIN_EMAIL = "admin@lumiere.studio"
SEED_ADMIN_PASSWORD = "Admin@12345"


def _jpeg_bytes(w=500, h=500, color=(200, 180, 160)):
    img = Image.new("RGB", (w, h), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/admin/login", json={
        "email": SEED_ADMIN_EMAIL, "password": SEED_ADMIN_PASSWORD
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert "session_token" in data and data["user"]["role"] == "admin"
    return data["session_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def client_email():
    return f"test_client_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture(scope="module")
def client_token(client_email):
    r = requests.post(f"{API}/auth/client/request-otp", json={
        "channel": "email", "email": client_email
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") == "sent"
    dev_code = body.get("dev_code")
    assert dev_code, "OTP_DEV_MODE should return dev_code"

    r2 = requests.post(f"{API}/auth/client/verify-otp", json={
        "channel": "email", "email": client_email, "code": dev_code, "name": "Test Client"
    })
    assert r2.status_code == 200, r2.text
    d = r2.json()
    assert d["user"]["role"] == "client"
    return d["session_token"]


@pytest.fixture(scope="module")
def client_headers(client_token):
    return {"Authorization": f"Bearer {client_token}"}


@pytest.fixture(scope="module")
def event(admin_headers):
    r = requests.post(f"{API}/events", headers=admin_headers, json={
        "name": "TEST_Event", "category": "wedding", "photographer": "TestPhotog",
        "similarity_threshold": 80,
    })
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["event_id"].startswith("evt_")
    assert e["indexing_status"] == "empty"
    assert e["photo_count"] == 0
    return e


# ----- Health -----
class TestHealth:
    def test_root(self):
        r = requests.get(f"{API}/")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_meta(self):
        r = requests.get(f"{API}/meta")
        assert r.status_code == 200
        j = r.json()
        assert "wedding" in j["categories"]


# ----- Admin Auth -----
class TestAdminAuth:
    def test_login_success(self, admin_token):
        assert admin_token

    def test_login_bad_password(self):
        r = requests.post(f"{API}/auth/admin/login", json={
            "email": SEED_ADMIN_EMAIL, "password": "wrong"})
        assert r.status_code == 401

    def test_register_and_login_new_admin(self):
        email = f"test_admin_{uuid.uuid4().hex[:6]}@example.com"
        r = requests.post(f"{API}/auth/admin/register", json={
            "name": "TEST_Admin", "email": email, "password": "SecurePass123"})
        assert r.status_code == 200, r.text
        assert r.json()["user"]["role"] == "admin"
        # duplicate
        r2 = requests.post(f"{API}/auth/admin/register", json={
            "name": "TEST_Admin", "email": email, "password": "SecurePass123"})
        assert r2.status_code == 409

    def test_me_unauthed(self):
        r = requests.get(f"{API}/auth/me")
        assert r.status_code in (401, 403)


# ----- Events CRUD -----
class TestEvents:
    def test_create_and_list(self, admin_headers, event):
        r = requests.get(f"{API}/events", headers=admin_headers)
        assert r.status_code == 200
        ids = [e["event_id"] for e in r.json()]
        assert event["event_id"] in ids

    def test_get_event(self, admin_headers, event):
        r = requests.get(f"{API}/events/{event['event_id']}", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["name"] == "TEST_Event"

    def test_patch_threshold_valid(self, admin_headers, event):
        r = requests.patch(f"{API}/events/{event['event_id']}", headers=admin_headers,
                           json={"similarity_threshold": 75})
        assert r.status_code == 200
        assert r.json()["similarity_threshold"] == 75
        # restore back to 80
        requests.patch(f"{API}/events/{event['event_id']}", headers=admin_headers,
                       json={"similarity_threshold": 80})

    def test_patch_threshold_invalid_low(self, admin_headers, event):
        r = requests.patch(f"{API}/events/{event['event_id']}", headers=admin_headers,
                           json={"similarity_threshold": 40})
        assert r.status_code == 400

    def test_patch_threshold_invalid_high(self, admin_headers, event):
        r = requests.patch(f"{API}/events/{event['event_id']}", headers=admin_headers,
                           json={"similarity_threshold": 120})
        assert r.status_code == 400

    def test_create_bad_category(self, admin_headers):
        r = requests.post(f"{API}/events", headers=admin_headers, json={
            "name": "X", "category": "invalid"})
        assert r.status_code == 400

    def test_events_require_admin(self):
        r = requests.get(f"{API}/events")
        assert r.status_code in (401, 403)


# ----- Photo upload + indexing -----
class TestPhotoUpload:
    def test_upload_photos(self, admin_headers, event):
        for i in range(3):
            files = {"file": (f"p{i}.jpg", _jpeg_bytes(600, 600, (100+i*40, 120, 150)), "image/jpeg")}
            r = requests.post(f"{API}/events/{event['event_id']}/photos",
                              headers=admin_headers, files=files)
            assert r.status_code == 200, r.text
            p = r.json()
            assert p["photo_id"].startswith("pho_")
            assert p["indexing_status"] == "indexed"
            assert p["thumb_path"]

    def test_indexing_status(self, admin_headers, event):
        r = requests.get(f"{API}/events/{event['event_id']}/indexing-status",
                         headers=admin_headers)
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "ready"
        assert d["total_photos"] >= 3
        assert d["indexed_photos"] >= 3

    def test_event_photo_count(self, admin_headers, event):
        r = requests.get(f"{API}/events/{event['event_id']}", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["photo_count"] >= 3
        assert r.json()["indexing_status"] == "ready"

    def test_upload_empty(self, admin_headers, event):
        files = {"file": ("e.jpg", b"", "image/jpeg")}
        r = requests.post(f"{API}/events/{event['event_id']}/photos",
                          headers=admin_headers, files=files)
        assert r.status_code == 400


# ----- Access grants -----
class TestAccess:
    def test_grant_access_email(self, admin_headers, event, client_email):
        r = requests.post(f"{API}/events/{event['event_id']}/access",
                          headers=admin_headers,
                          json={"channel": "email", "email": client_email,
                                "full_gallery_access": False})
        assert r.status_code == 200, r.text
        g = r.json()
        assert g["client_email"] == client_email.lower()
        assert g["status"] == "active"
        assert g["full_gallery_access"] is False

    def test_grant_phone(self, admin_headers, event):
        r = requests.post(f"{API}/events/{event['event_id']}/access",
                          headers=admin_headers,
                          json={"channel": "phone", "phone": "+15551234567"})
        assert r.status_code == 200

    def test_list_access(self, admin_headers, event):
        r = requests.get(f"{API}/events/{event['event_id']}/access",
                         headers=admin_headers)
        assert r.status_code == 200
        assert len(r.json()) >= 2

    def test_patch_full_access(self, admin_headers, event, client_email):
        grants = requests.get(f"{API}/events/{event['event_id']}/access",
                              headers=admin_headers).json()
        g = next(x for x in grants if x.get("client_email") == client_email.lower())
        # form data
        r = requests.patch(f"{API}/events/{event['event_id']}/access/{g['grant_id']}",
                           headers=admin_headers,
                           data={"full_gallery_access": "true"})
        assert r.status_code == 200
        # verify
        grants2 = requests.get(f"{API}/events/{event['event_id']}/access",
                               headers=admin_headers).json()
        g2 = next(x for x in grants2 if x["grant_id"] == g["grant_id"])
        assert g2["full_gallery_access"] is True

    def test_revoke(self, admin_headers, event):
        # grant then revoke a throwaway
        r = requests.post(f"{API}/events/{event['event_id']}/access",
                          headers=admin_headers,
                          json={"channel": "email", "email": "revoke_me@example.com"})
        gid = r.json()["grant_id"]
        r2 = requests.delete(f"{API}/events/{event['event_id']}/access/{gid}",
                             headers=admin_headers)
        assert r2.status_code == 200
        assert r2.json()["status"] == "revoked"


# ----- Client OTP + events -----
class TestClient:
    def test_client_no_grant_gets_empty_events(self):
        # brand-new client with no grants
        email = f"lonely_{uuid.uuid4().hex[:6]}@example.com"
        r = requests.post(f"{API}/auth/client/request-otp",
                          json={"channel": "email", "email": email})
        code = r.json()["dev_code"]
        r2 = requests.post(f"{API}/auth/client/verify-otp",
                           json={"channel": "email", "email": email, "code": code})
        tok = r2.json()["session_token"]
        r3 = requests.get(f"{API}/client/events",
                          headers={"Authorization": f"Bearer {tok}"})
        assert r3.status_code == 200
        assert r3.json() == []

    def test_client_events_lists_shared(self, client_headers, event):
        r = requests.get(f"{API}/client/events", headers=client_headers)
        assert r.status_code == 200
        ids = [e["event_id"] for e in r.json()]
        assert event["event_id"] in ids

    def test_client_event_detail(self, client_headers, event):
        r = requests.get(f"{API}/client/events/{event['event_id']}",
                         headers=client_headers)
        assert r.status_code == 200
        d = r.json()
        assert "consent_given" in d
        assert "my_photos_count" in d

    def test_verify_wrong_otp(self):
        email = f"badcode_{uuid.uuid4().hex[:6]}@example.com"
        requests.post(f"{API}/auth/client/request-otp",
                      json={"channel": "email", "email": email})
        r = requests.post(f"{API}/auth/client/verify-otp",
                          json={"channel": "email", "email": email, "code": "000000"})
        assert r.status_code == 401


# ----- Consent + selfie search -----
class TestSelfieFlow:
    def test_search_blocked_without_consent(self, client_headers, event):
        files = {"file": ("selfie.jpg", _jpeg_bytes(500, 500), "image/jpeg")}
        r = requests.post(f"{API}/client/events/{event['event_id']}/search",
                          headers=client_headers, files=files)
        assert r.status_code == 403

    def test_give_consent(self, client_headers, event):
        r = requests.post(f"{API}/client/events/{event['event_id']}/consent",
                         headers=client_headers, json={"accepted": True})
        assert r.status_code == 200

    def test_consent_reject(self, client_headers, event):
        r = requests.post(f"{API}/client/events/{event['event_id']}/consent",
                         headers=client_headers, json={"accepted": False})
        assert r.status_code == 400

    def test_selfie_search_matches(self, client_headers, event):
        files = {"file": ("selfie.jpg", _jpeg_bytes(500, 500, (210, 180, 170)), "image/jpeg")}
        r = requests.post(f"{API}/client/events/{event['event_id']}/search",
                          headers=client_headers, files=files)
        assert r.status_code == 200, r.text
        d = r.json()
        # Either matched (photos indexed with faces) or retake for quality
        assert d["status"] in ("matched", "retake")
        if d["status"] == "matched":
            assert isinstance(d["photos"], list)
            assert d["threshold"] >= 50
            # verify photos deduped by photo_id
            pids = [p["photo_id"] for p in d["photos"]]
            assert len(pids) == len(set(pids))

    def test_my_photos_after_search(self, client_headers, event):
        r = requests.get(f"{API}/client/events/{event['event_id']}/my-photos",
                         headers=client_headers)
        assert r.status_code == 200
        d = r.json()
        assert "photos" in d and "count" in d


# ----- Full gallery access enforcement -----
class TestFullGalleryAccess:
    def test_full_photos_403_without_full_access(self, event):
        # New client, no full access
        email = f"nofull_{uuid.uuid4().hex[:6]}@example.com"
        _admin = requests.post(f"{API}/auth/admin/login", json={
            "email": SEED_ADMIN_EMAIL, "password": SEED_ADMIN_PASSWORD}).json()["session_token"]
        ah = {"Authorization": f"Bearer {_admin}"}
        requests.post(f"{API}/events/{event['event_id']}/access", headers=ah,
                      json={"channel": "email", "email": email,
                            "full_gallery_access": False})
        code = requests.post(f"{API}/auth/client/request-otp",
                             json={"channel": "email", "email": email}).json()["dev_code"]
        tok = requests.post(f"{API}/auth/client/verify-otp",
                            json={"channel": "email", "email": email, "code": code}
                            ).json()["session_token"]
        r = requests.get(f"{API}/client/events/{event['event_id']}/photos",
                         headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 403

    def test_full_photos_200_with_full_access(self, client_headers, event, admin_headers, client_email):
        # Ensure grant is upgraded to full access (may race with TestAccess under xdist)
        grants = requests.get(f"{API}/events/{event['event_id']}/access",
                              headers=admin_headers).json()
        g = next((x for x in grants if x.get("client_email") == client_email.lower()), None)
        if g is None:
            requests.post(f"{API}/events/{event['event_id']}/access",
                          headers=admin_headers,
                          json={"channel": "email", "email": client_email,
                                "full_gallery_access": True})
        else:
            requests.patch(f"{API}/events/{event['event_id']}/access/{g['grant_id']}",
                           headers=admin_headers,
                           data={"full_gallery_access": "true"})
        r = requests.get(f"{API}/client/events/{event['event_id']}/photos",
                         headers=client_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ----- File serving auth -----
@pytest.fixture(scope="module")
def uploaded_photo_path(admin_headers, event):
    """Own upload so this test class doesn't race with TestPhotoUpload under xdist."""
    files = {"file": ("fs.jpg", _jpeg_bytes(500, 500, (180, 190, 200)), "image/jpeg")}
    r = requests.post(f"{API}/events/{event['event_id']}/photos",
                      headers=admin_headers, files=files)
    assert r.status_code == 200, r.text
    return r.json()["thumb_path"]


class TestFileServing:
    def test_admin_can_fetch_photo(self, admin_headers, uploaded_photo_path):
        r = requests.get(f"{API}/files/{uploaded_photo_path}", headers=admin_headers)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/")

    def test_files_unauth(self, uploaded_photo_path):
        r = requests.get(f"{API}/files/{uploaded_photo_path}")
        assert r.status_code in (401, 403)

    def test_files_token_query(self, admin_token, uploaded_photo_path):
        r = requests.get(f"{API}/files/{uploaded_photo_path}?token={admin_token}")
        assert r.status_code == 200


# ----- Face data deletion -----
class TestFaceDataDelete:
    def test_list_clients_and_delete_face_data(self, admin_headers, event):
        clients = requests.get(f"{API}/events/{event['event_id']}/clients",
                               headers=admin_headers).json()
        assert isinstance(clients, list)
        if clients:
            cid = clients[0]["client_user_id"]
            r = requests.delete(
                f"{API}/events/{event['event_id']}/clients/{cid}/face-data",
                headers=admin_headers)
            assert r.status_code == 200
            assert r.json()["status"] == "deleted"
