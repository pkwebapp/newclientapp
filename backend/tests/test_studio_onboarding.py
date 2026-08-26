"""Backend contract tests for the Studio onboarding gate (Jan 2026).

Covers:
  - POST /api/auth/admin/register -> user.profile_complete == False
  - POST /api/auth/admin/profile with valid bearer -> saves, sets True, updates name/phone
  - POST /api/auth/admin/profile with missing required fields -> 400
  - POST /api/auth/admin/profile without auth -> 401
  - GET /api/auth/me reflects the new profile_complete
  - POST /api/superadmin/login is unaffected by the new profile gate
"""

import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("EXPO_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "EXPO_BACKEND_URL must be set for tests"


def _fresh_email() -> str:
    return f"TEST_studio_{uuid.uuid4().hex[:10]}@test.com"


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def new_admin(api):
    """Register a fresh studio admin and return (token, user, email, password)."""
    email = _fresh_email()
    password = "Sup3rSecret!"
    r = api.post(
        f"{BASE_URL}/api/auth/admin/register",
        json={"name": "TEST Studio", "email": email, "password": password},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    return {
        "token": data["session_token"],
        "user": data["user"],
        "email": email,
        "password": password,
    }


# --- Register ---------------------------------------------------------------
class TestAdminRegister:
    def test_register_returns_profile_incomplete(self, new_admin):
        u = new_admin["user"]
        assert u["role"] == "admin"
        assert u["email"] == new_admin["email"].lower()
        assert u["profile_complete"] is False
        assert u.get("studio_profile") in (None, {})
        assert new_admin["token"].startswith("st_")


# --- Profile completion -----------------------------------------------------
class TestAdminProfile:
    def _auth(self, token):
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def test_profile_without_auth_returns_401(self, api):
        r = api.post(
            f"{BASE_URL}/api/auth/admin/profile",
            json={
                "contact_name": "x",
                "studio_name": "y",
                "phone": "123456",
                "purpose": "Weddings",
                "city": "Mumbai",
                "country": "India",
            },
            headers={"Content-Type": "application/json"},  # no Authorization
        )
        assert r.status_code == 401, r.text

    def test_profile_missing_required_returns_400(self, api, new_admin):
        # Send all required keys present per Pydantic, but one is empty/whitespace
        r = api.post(
            f"{BASE_URL}/api/auth/admin/profile",
            json={
                "contact_name": "Prabhakar",
                "studio_name": "  ",  # blank -> should be treated as missing
                "phone": "9876543210",
                "purpose": "Weddings",
                "city": "Mumbai",
                "country": "India",
            },
            headers=self._auth(new_admin["token"]),
        )
        assert r.status_code == 400, r.text
        assert "required" in r.text.lower() or "complete" in r.text.lower()

    def test_profile_pydantic_missing_field_rejected(self, api, new_admin):
        # Missing required key entirely -> FastAPI 422 (still not 200)
        r = api.post(
            f"{BASE_URL}/api/auth/admin/profile",
            json={
                "contact_name": "Prabhakar",
                "studio_name": "PK Studio",
                "phone": "9876543210",
                # purpose missing
                "city": "Mumbai",
                "country": "India",
            },
            headers=self._auth(new_admin["token"]),
        )
        assert r.status_code in (400, 422), r.text

    def test_profile_save_marks_complete_and_updates_name_phone(self, api, new_admin):
        token = new_admin["token"]
        payload = {
            "contact_name": "Prabhakar Kumar",
            "studio_name": "PK Photography TEST",
            "phone": "+91 98765 43210",
            "purpose": "Weddings",
            "city": "Mumbai",
            "country": "India",
            "website": "instagram.com/pkphotography",
            "team_size": "2–5",
            "galleries_per_month": "5–20",
            "referral_source": "Instagram",
        }
        r = api.post(
            f"{BASE_URL}/api/auth/admin/profile",
            json=payload,
            headers=self._auth(token),
        )
        assert r.status_code == 200, r.text
        u = r.json()["user"]
        assert u["profile_complete"] is True
        # name and phone updated to studio_name / phone
        assert u["name"] == payload["studio_name"]
        assert u["phone"] == payload["phone"]
        sp = u["studio_profile"]
        assert sp is not None
        for k in [
            "contact_name",
            "studio_name",
            "phone",
            "purpose",
            "city",
            "country",
            "website",
            "team_size",
            "galleries_per_month",
            "referral_source",
        ]:
            assert k in sp, f"missing key {k} in studio_profile"
        assert sp["contact_name"] == "Prabhakar Kumar"
        assert sp["studio_name"] == "PK Photography TEST"

    def test_me_reflects_profile_complete_after_save(self, api, new_admin):
        r = api.get(
            f"{BASE_URL}/api/auth/me",
            headers={"Authorization": f"Bearer {new_admin['token']}"},
        )
        assert r.status_code == 200, r.text
        u = r.json()["user"]
        assert u["profile_complete"] is True
        assert u["name"] == "PK Photography TEST"
        assert u["studio_profile"]["city"] == "Mumbai"


# --- Superadmin unaffected ---------------------------------------------------
class TestSuperadminUnaffected:
    def test_superadmin_login_still_works(self, api):
        r = api.post(
            f"{BASE_URL}/api/superadmin/login",
            json={
                "email": "prabhakar@pkphotography.in",
                "password": "SuperAdmin@3214",
            },
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["user"]["role"] == "superadmin"
        assert "session_token" in data

    def test_superadmin_can_access_protected_endpoint(self, api):
        r = api.post(
            f"{BASE_URL}/api/superadmin/login",
            json={
                "email": "prabhakar@pkphotography.in",
                "password": "SuperAdmin@3214",
            },
        )
        token = r.json()["session_token"]
        r2 = api.get(
            f"{BASE_URL}/api/superadmin/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.status_code == 200, r2.text
