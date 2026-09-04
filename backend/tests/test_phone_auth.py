"""Backend tests for Phone OTP Authentication endpoints."""
import pytest
import requests
import os

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/")
TEST_PHONE = "+919876543210"

@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# --- Send OTP ---

class TestSendOtp:
    """POST /api/auth/phone/send-otp"""

    def test_send_otp_returns_200_and_dev_code(self, session):
        resp = session.post(f"{BASE_URL}/api/auth/phone/send-otp", json={"phone": TEST_PHONE, "role": "client"})
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "message" in data
        assert "dev_code" in data, f"dev_code missing (OTP_DEV_MODE should be true). Response: {data}"
        assert len(data["dev_code"]) == 6, f"dev_code should be 6 digits: {data['dev_code']}"

    def test_send_otp_invalid_phone(self, session):
        resp = session.post(f"{BASE_URL}/api/auth/phone/send-otp", json={"phone": "12345", "role": "client"})
        assert resp.status_code == 400


# --- Verify OTP ---

class TestVerifyOtp:
    """POST /api/auth/phone/verify-otp"""

    def _get_dev_code(self, session, phone="+919876540001"):
        resp = session.post(f"{BASE_URL}/api/auth/phone/send-otp", json={"phone": phone, "role": "client"})
        assert resp.status_code == 200
        return resp.json()["dev_code"]

    def test_verify_otp_client_success(self, session):
        phone = "+919876540001"
        dev_code = self._get_dev_code(session, phone)
        resp = session.post(f"{BASE_URL}/api/auth/phone/verify-otp", json={
            "phone": phone, "code": dev_code, "role": "client"
        })
        assert resp.status_code == 200, f"Expected 200: {resp.text}"
        data = resp.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["role"] == "client"
        assert data["user"]["phone"] == phone

    def test_verify_otp_wrong_code(self, session):
        phone = "+919876540002"
        # First send OTP to get a pending one
        session.post(f"{BASE_URL}/api/auth/phone/send-otp", json={"phone": phone, "role": "client"})
        resp = session.post(f"{BASE_URL}/api/auth/phone/verify-otp", json={
            "phone": phone, "code": "000000", "role": "client"
        })
        assert resp.status_code == 400

    def test_verify_otp_admin_role(self, session):
        resp = session.post(f"{BASE_URL}/api/auth/phone/send-otp", json={"phone": "+919876543211", "role": "admin"})
        assert resp.status_code == 200
        dev_code = resp.json()["dev_code"]
        resp2 = session.post(f"{BASE_URL}/api/auth/phone/verify-otp", json={
            "phone": "+919876543211", "code": dev_code, "role": "admin"
        })
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["user"]["role"] == "admin"


# --- /auth/me with phone JWT ---

class TestAuthMe:
    """GET /api/auth/me with phone JWT"""

    def test_auth_me_with_phone_jwt(self, session):
        phone = "+919876540003"
        # Get token
        resp = session.post(f"{BASE_URL}/api/auth/phone/send-otp", json={"phone": phone, "role": "client"})
        dev_code = resp.json()["dev_code"]
        v = session.post(f"{BASE_URL}/api/auth/phone/verify-otp", json={
            "phone": phone, "code": dev_code, "role": "client"
        })
        token = v.json()["token"]

        me = session.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200, f"Expected 200: {me.text}"
        data = me.json()
        assert "user" in data
        assert data["user"]["phone"] == phone

    def test_auth_me_no_token_returns_401(self, session):
        resp = session.get(f"{BASE_URL}/api/auth/me")
        assert resp.status_code == 401


# --- Set Password ---

class TestSetPassword:
    """POST /api/auth/phone/set-password"""

    def _get_token(self, session, phone="+919876543212"):
        session.post(f"{BASE_URL}/api/auth/phone/send-otp", json={"phone": phone, "role": "client"})
        resp = session.post(f"{BASE_URL}/api/auth/phone/send-otp", json={"phone": phone, "role": "client"})
        dev_code = resp.json()["dev_code"]
        v = session.post(f"{BASE_URL}/api/auth/phone/verify-otp", json={
            "phone": phone, "code": dev_code, "role": "client"
        })
        return v.json()["token"], phone

    def test_set_password_success(self, session):
        token, phone = self._get_token(session)
        resp = session.post(
            f"{BASE_URL}/api/auth/phone/set-password",
            json={"password": "TestPass123!"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200, f"Expected 200: {resp.text}"
        assert resp.json()["message"] == "Password set successfully"

    def test_set_password_too_short(self, session):
        token, _ = self._get_token(session, "+919876543213")
        resp = session.post(
            f"{BASE_URL}/api/auth/phone/set-password",
            json={"password": "short"},
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 400


# --- Phone + Password Login ---

class TestPhonePasswordLogin:
    """POST /api/auth/phone/login"""

    def test_phone_login_success(self, session):
        phone = "+919876543214"
        # Create user via OTP and set password
        resp = session.post(f"{BASE_URL}/api/auth/phone/send-otp", json={"phone": phone, "role": "client"})
        dev_code = resp.json()["dev_code"]
        v = session.post(f"{BASE_URL}/api/auth/phone/verify-otp", json={
            "phone": phone, "code": dev_code, "role": "client"
        })
        token = v.json()["token"]
        session.post(
            f"{BASE_URL}/api/auth/phone/set-password",
            json={"password": "MyPassword9!"},
            headers={"Authorization": f"Bearer {token}"}
        )
        # Now login with password
        login = session.post(f"{BASE_URL}/api/auth/phone/login", json={"phone": phone, "password": "MyPassword9!"})
        assert login.status_code == 200, f"Expected 200: {login.text}"
        data = login.json()
        assert "token" in data
        assert data["user"]["phone"] == phone

    def test_phone_login_wrong_password(self, session):
        phone = "+919876543214"
        login = session.post(f"{BASE_URL}/api/auth/phone/login", json={"phone": phone, "password": "WrongPass!"})
        assert login.status_code == 401
