"""Backend tests for NEW Album module features:
- Access grants (email/phone) + list + revoke
- GET /api/albums/client/mine (client sees granted published albums)
- Music upload/delete + presence in public manifest, PDF-replace preserves music
- Archive/unarchive + preview-token bypass
- PATCH new settings fields + autoplay_interval clamping
- Regression: PDF re-upload (rendered assets survive under /pages/, music kept)
"""
import io
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://client-portal-453.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SEED_ADMIN_EMAIL = "admin@lumiere.studio"
SEED_ADMIN_PASSWORD = "Admin@12345"

TEST_PDF = "/app/tmp/test_album.pdf"
TEST_WAV = "/app/tmp/test_music.wav"


# ---- Fixtures --------------------------------------------------------------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/admin/login", json={
        "email": SEED_ADMIN_EMAIL, "password": SEED_ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["session_token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def scratch_album(admin_headers):
    """Create a dedicated album for destructive tests + upload the sample PDF."""
    r = requests.post(f"{API}/albums", headers=admin_headers, json={
        "title": f"TEST_Album_{uuid.uuid4().hex[:6]}",
        "client_name": "TEST_Client",
        "event_name": "TEST_Event",
    })
    assert r.status_code == 200, r.text
    aid = r.json()["album_id"]
    with open(TEST_PDF, "rb") as f:
        rp = requests.post(f"{API}/albums/{aid}/pdf", headers=admin_headers,
                           files={"file": ("t.pdf", f.read(), "application/pdf")})
    assert rp.status_code == 200, rp.text
    body = rp.json()
    assert body["total_spreads"] >= 1
    # publish
    rr = requests.post(f"{API}/albums/{aid}/publish", headers=admin_headers)
    assert rr.status_code == 200
    yield rr.json()
    # cleanup
    requests.delete(f"{API}/albums/{aid}", headers=admin_headers)


# ---- Access grants ---------------------------------------------------------
class TestAlbumAccess:
    def test_grant_email(self, admin_headers, scratch_album):
        email = f"TEST_grantee_{uuid.uuid4().hex[:6]}@example.com"
        r = requests.post(f"{API}/albums/{scratch_album['album_id']}/access",
                          headers=admin_headers,
                          json={"channel": "email", "email": email})
        assert r.status_code == 200, r.text
        g = r.json()
        assert g["status"] == "active"
        assert g["client_email"] == email.lower()
        assert g["grant_id"].startswith("agrant_")

    def test_grant_phone(self, admin_headers, scratch_album):
        r = requests.post(f"{API}/albums/{scratch_album['album_id']}/access",
                          headers=admin_headers,
                          json={"channel": "phone", "phone": "+15551110000"})
        assert r.status_code == 200
        g = r.json()
        assert g["client_phone"] == "+15551110000"
        assert g["status"] == "active"

    def test_grant_bad_channel(self, admin_headers, scratch_album):
        r = requests.post(f"{API}/albums/{scratch_album['album_id']}/access",
                          headers=admin_headers, json={"channel": "sms"})
        assert r.status_code == 400

    def test_list_access(self, admin_headers, scratch_album):
        r = requests.get(f"{API}/albums/{scratch_album['album_id']}/access",
                         headers=admin_headers)
        assert r.status_code == 200
        grants = r.json()
        assert isinstance(grants, list)
        assert len(grants) >= 2

    def test_revoke_grant(self, admin_headers, scratch_album):
        # create fresh grant, then revoke
        r = requests.post(f"{API}/albums/{scratch_album['album_id']}/access",
                          headers=admin_headers,
                          json={"channel": "email", "email": "TEST_revoke@example.com"})
        assert r.status_code == 200
        gid = r.json()["grant_id"]
        rd = requests.delete(f"{API}/albums/{scratch_album['album_id']}/access/{gid}",
                             headers=admin_headers)
        assert rd.status_code == 200
        assert rd.json()["status"] == "revoked"
        # verify in list
        grants = requests.get(f"{API}/albums/{scratch_album['album_id']}/access",
                              headers=admin_headers).json()
        found = next(x for x in grants if x["grant_id"] == gid)
        assert found["status"] == "revoked"


# ---- Client /mine ----------------------------------------------------------
class TestClientMine:
    def test_client_mine_shows_granted_published_album(self, admin_headers, scratch_album):
        # Fresh client with grant on our scratch album
        email = f"TEST_mine_{uuid.uuid4().hex[:6]}@example.com"
        requests.post(f"{API}/albums/{scratch_album['album_id']}/access",
                      headers=admin_headers,
                      json={"channel": "email", "email": email})
        # OTP login
        r = requests.post(f"{API}/auth/client/request-otp",
                          json={"channel": "email", "email": email})
        assert r.status_code == 200
        code = r.json()["dev_code"]
        r2 = requests.post(f"{API}/auth/client/verify-otp",
                           json={"channel": "email", "email": email, "code": code})
        tok = r2.json()["session_token"]
        # mine
        r3 = requests.get(f"{API}/albums/client/mine",
                          headers={"Authorization": f"Bearer {tok}"})
        assert r3.status_code == 200, r3.text
        items = r3.json()
        assert isinstance(items, list)
        found = next((a for a in items if a["album_id"] == scratch_album["album_id"]), None)
        assert found, f"Expected album in mine, got {items}"
        # expected fields
        assert "share_token" in found and found["share_token"]
        assert "cover_url" in found
        assert "has_music" in found  # bool

    def test_client_mine_excludes_draft(self, admin_headers, scratch_album):
        """Unpublish and confirm album disappears for the client."""
        aid = scratch_album["album_id"]
        email = f"TEST_draft_{uuid.uuid4().hex[:6]}@example.com"
        requests.post(f"{API}/albums/{aid}/access", headers=admin_headers,
                      json={"channel": "email", "email": email})
        code = requests.post(f"{API}/auth/client/request-otp",
                             json={"channel": "email", "email": email}).json()["dev_code"]
        tok = requests.post(f"{API}/auth/client/verify-otp",
                            json={"channel": "email", "email": email, "code": code}
                            ).json()["session_token"]
        # unpublish
        requests.post(f"{API}/albums/{aid}/unpublish", headers=admin_headers)
        r = requests.get(f"{API}/albums/client/mine",
                         headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        assert not any(a["album_id"] == aid for a in r.json())
        # restore
        requests.post(f"{API}/albums/{aid}/publish", headers=admin_headers)

    def test_client_mine_excludes_revoked(self, admin_headers, scratch_album):
        aid = scratch_album["album_id"]
        email = f"TEST_rev_{uuid.uuid4().hex[:6]}@example.com"
        gr = requests.post(f"{API}/albums/{aid}/access", headers=admin_headers,
                           json={"channel": "email", "email": email}).json()
        gid = gr["grant_id"]
        code = requests.post(f"{API}/auth/client/request-otp",
                             json={"channel": "email", "email": email}).json()["dev_code"]
        tok = requests.post(f"{API}/auth/client/verify-otp",
                            json={"channel": "email", "email": email, "code": code}
                            ).json()["session_token"]
        # Revoke
        requests.delete(f"{API}/albums/{aid}/access/{gid}", headers=admin_headers)
        r = requests.get(f"{API}/albums/client/mine",
                         headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        assert not any(a["album_id"] == aid for a in r.json())


# ---- Music --------------------------------------------------------------
class TestAlbumMusic:
    def test_upload_and_delete_music(self, admin_headers, scratch_album):
        aid = scratch_album["album_id"]
        with open(TEST_WAV, "rb") as f:
            r = requests.post(f"{API}/albums/{aid}/music", headers=admin_headers,
                              files={"file": ("test_music.wav", f.read(), "audio/wav")})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["music"] and body["music"]["url"]
        assert body["music"]["filename"] == "test_music.wav"
        # public manifest should have music_url
        rm = requests.get(f"{API}/albums/public/{body['share_token']}")
        assert rm.status_code == 200
        mani = rm.json()
        assert mani.get("music_url"), f"music_url missing in public manifest: {mani}"

        # delete
        rd = requests.delete(f"{API}/albums/{aid}/music", headers=admin_headers)
        assert rd.status_code == 200
        assert rd.json()["music"] is None
        rm2 = requests.get(f"{API}/albums/public/{body['share_token']}").json()
        assert rm2.get("music_url") in (None, "")

    def test_upload_bad_ext_rejected(self, admin_headers, scratch_album):
        aid = scratch_album["album_id"]
        r = requests.post(f"{API}/albums/{aid}/music", headers=admin_headers,
                          files={"file": ("not.txt", b"hello", "text/plain")})
        assert r.status_code == 400

    def test_music_survives_pdf_replace(self, admin_headers, scratch_album):
        aid = scratch_album["album_id"]
        # upload music again
        with open(TEST_WAV, "rb") as f:
            r = requests.post(f"{API}/albums/{aid}/music", headers=admin_headers,
                              files={"file": ("t.wav", f.read(), "audio/wav")})
        assert r.status_code == 200
        # replace pdf
        with open(TEST_PDF, "rb") as f:
            rp = requests.post(f"{API}/albums/{aid}/pdf", headers=admin_headers,
                               files={"file": ("t.pdf", f.read(), "application/pdf")})
        assert rp.status_code == 200
        body = rp.json()
        assert body["music"] and body["music"]["url"], "music should survive PDF replace"
        # Rendered assets under /pages/ prefix (check cover_url contains '/pages/')
        assert body["cover_url"] and "/pages/" in body["cover_url"]


# ---- Archive / Unarchive ---------------------------------------------------
class TestArchive:
    def test_archive_blocks_public_but_preview_bypasses(self, admin_headers, scratch_album):
        aid = scratch_album["album_id"]
        # fetch preview token
        r0 = requests.get(f"{API}/albums/{aid}", headers=admin_headers)
        assert r0.status_code == 200
        preview_url = r0.json()["preview_url"]
        # preview_url includes ?k=<preview_token>
        preview_token = preview_url.split("k=")[-1]
        share_token = r0.json()["share_token"]

        # archive
        r = requests.post(f"{API}/albums/{aid}/archive", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["archived"] is True

        # public manifest -> 403 archived
        rm = requests.get(f"{API}/albums/public/{share_token}")
        assert rm.status_code == 403
        assert "archived" in rm.text.lower()

        # preview key bypasses
        rp = requests.get(f"{API}/albums/public/{share_token}?k={preview_token}")
        assert rp.status_code == 200, rp.text

        # unarchive
        ru = requests.post(f"{API}/albums/{aid}/unarchive", headers=admin_headers)
        assert ru.status_code == 200
        assert ru.json()["archived"] is False
        rm2 = requests.get(f"{API}/albums/public/{share_token}")
        assert rm2.status_code == 200


# ---- PATCH new settings ----------------------------------------------------
class TestPatchSettings:
    def test_patch_settings_and_clamp(self, admin_headers, scratch_album):
        aid = scratch_album["album_id"]
        r = requests.patch(f"{API}/albums/{aid}", headers=admin_headers, json={
            "autoplay": False,
            "autoplay_interval": 2.0,
            "auto_open": True,
            "page_turn_sound": True,
        })
        assert r.status_code == 200
        body = r.json()
        assert body["autoplay"] is False
        assert body["auto_open"] is True
        assert body["page_turn_sound"] is True
        assert abs(body["autoplay_interval"] - 2.0) < 0.001

        # Public manifest reflects settings
        mani = requests.get(f"{API}/albums/public/{body['share_token']}").json()
        s = mani["settings"]
        assert s["autoplay"] is False
        assert s["auto_open"] is True
        assert s["page_turn_sound"] is True
        assert abs(s["autoplay_interval"] - 2.0) < 0.001

        # Clamp low
        r2 = requests.patch(f"{API}/albums/{aid}", headers=admin_headers,
                            json={"autoplay_interval": 0.5})
        assert r2.status_code == 200
        assert r2.json()["autoplay_interval"] == 1.5

        # Clamp high
        r3 = requests.patch(f"{API}/albums/{aid}", headers=admin_headers,
                            json={"autoplay_interval": 999})
        assert r3.status_code == 200
        assert r3.json()["autoplay_interval"] == 8.0

        # Restore defaults for other tests
        requests.patch(f"{API}/albums/{aid}", headers=admin_headers, json={
            "autoplay": True, "autoplay_interval": 3.5,
            "auto_open": False, "page_turn_sound": False,
        })


# ---- Regression: existing gallery /events ---------------------------------
class TestGalleryRegression:
    def test_events_list_still_works(self, admin_headers):
        r = requests.get(f"{API}/events", headers=admin_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_meta_still_works(self):
        r = requests.get(f"{API}/meta")
        assert r.status_code == 200
        assert "wedding" in r.json()["categories"]

    def test_album_lifecycle_create_publish_delete(self, admin_headers):
        c = requests.post(f"{API}/albums", headers=admin_headers, json={"title": "TEST_lifecycle"})
        assert c.status_code == 200
        aid = c.json()["album_id"]
        # cannot publish empty
        r = requests.post(f"{API}/albums/{aid}/publish", headers=admin_headers)
        assert r.status_code == 400
        # upload pdf
        with open(TEST_PDF, "rb") as f:
            rp = requests.post(f"{API}/albums/{aid}/pdf", headers=admin_headers,
                               files={"file": ("t.pdf", f.read(), "application/pdf")})
        assert rp.status_code == 200
        # now publish
        r2 = requests.post(f"{API}/albums/{aid}/publish", headers=admin_headers)
        assert r2.status_code == 200
        assert r2.json()["status"] == "published"
        # delete
        rd = requests.delete(f"{API}/albums/{aid}", headers=admin_headers)
        assert rd.status_code == 200
        assert rd.json()["status"] == "deleted"
