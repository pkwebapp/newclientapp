"""MSG91 Flow API OTP + custom HS256 JWT for phone-based authentication.

Flow:
  1.  POST /api/auth/phone/send-otp   → generate OTP, store hash, dispatch via MSG91
  2.  POST /api/auth/phone/verify-otp → verify hash, delete record, issue phone JWT
  3.  Bearer phone JWT verified here  → user row returned to auth_utils
"""
import hashlib
import hmac as _hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import httpx
import jwt

from config import db, OTP_DEV_MODE

# ---------------------------------------------------------------------------
# MSG91 credentials (read from env only — never hardcoded)
# ---------------------------------------------------------------------------
MSG91_AUTHKEY = os.environ.get("MSG91_AUTHKEY", "")
MSG91_TEMPLATE_ID = os.environ.get("MSG91_TEMPLATE_ID", "")

# ---------------------------------------------------------------------------
# JWT configuration
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ.get("JWT_SECRET", "")
JWT_EXPIRE_DAYS = 30
JWT_ISSUER = "pik-connect"


# ---------------------------------------------------------------------------
# OTP helpers
# ---------------------------------------------------------------------------

def _otp_digest(otp: str, salt: str) -> str:
    """Salted SHA-256 hash so the DB never stores a plaintext code."""
    return hashlib.sha256(f"{salt}:{otp}".encode()).hexdigest()


async def store_and_send_otp(phone: str) -> dict:
    """
    Generate a 6-digit OTP, store a salted hash in `phone_otps`, and send via
    MSG91 Flow API.  In OTP_DEV_MODE the code is returned in the response.

    ``phone`` must be in E.164 form (e.g. ``+919876543210``).
    """
    otp = f"{secrets.randbelow(1_000_000):06d}"
    salt = secrets.token_hex(16)
    now = datetime.now(timezone.utc)

    # Invalidate any pending OTP for this number
    await db.phone_otps.delete_many({"phone": phone})

    # Production: send before storing so a provider failure leaves nothing in DB
    if not OTP_DEV_MODE:
        await _dispatch_msg91(phone, otp)

    await db.phone_otps.insert_one({
        "phone": phone,
        "otp_hash": _otp_digest(otp, salt),
        "salt": salt,
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=10)).isoformat(),
        "attempts": 0,
    })

    result: dict = {"message": "OTP sent"}
    if OTP_DEV_MODE:
        result["dev_code"] = otp
    return result


async def _dispatch_msg91(phone: str, otp: str) -> None:
    """Call MSG91 Flow API.  Raises ``ValueError`` on any failure."""
    # MSG91 expects numeric mobile without leading '+', e.g. 919876543210
    mobile = phone.lstrip("+")
    payload = {
        "template_id": MSG91_TEMPLATE_ID,
        "recipients": [{"mobiles": mobile, "var1": otp}],
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authkey": MSG91_AUTHKEY,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.post(
                "https://control.msg91.com/api/v5/flow",
                json=payload,
                headers=headers,
            )
        body = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ValueError("SMS provider unavailable. Please try again.") from exc

    if resp.status_code >= 400 or body.get("type") == "error":
        # Never expose provider internals or auth keys to callers
        raise ValueError("Unable to send verification SMS. Please try again.")


async def verify_otp_and_consume(phone: str, code: str) -> None:
    """
    Verify the OTP for ``phone``.

    - On success: deletes the record (single-use) and returns.
    - On failure: increments the attempt counter and raises ``ValueError``.
    """
    record = await db.phone_otps.find_one({"phone": phone})
    now = datetime.now(timezone.utc)

    if not record:
        raise ValueError("Invalid or expired code. Please request a new one.")

    # Parse stored expiry (ISO string)
    expires_at = record["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < now:
        await db.phone_otps.delete_one({"_id": record["_id"]})
        raise ValueError("Code has expired. Please request a new one.")

    if record.get("attempts", 0) >= 5:
        raise ValueError("Too many failed attempts. Please request a new code.")

    if not _hmac.compare_digest(
        _otp_digest(code.strip(), record["salt"]), record["otp_hash"]
    ):
        await db.phone_otps.update_one(
            {"_id": record["_id"]}, {"$inc": {"attempts": 1}}
        )
        raise ValueError("Incorrect code. Please try again.")

    # ✅ Verified — delete so the code cannot be reused
    await db.phone_otps.delete_one({"_id": record["_id"]})


# ---------------------------------------------------------------------------
# Phone JWT helpers
# ---------------------------------------------------------------------------

def create_phone_jwt(user_id: str, role: str, phone: str) -> str:
    """Issue a signed HS256 bearer JWT for phone-authenticated sessions."""
    if not JWT_SECRET:
        raise RuntimeError("JWT_SECRET is not configured in the backend environment")
    now = datetime.now(timezone.utc)
    payload = {
        "iss": JWT_ISSUER,
        "sub": user_id,
        "role": role,
        "phone": phone,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=JWT_EXPIRE_DAYS)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_phone_jwt(token: str) -> dict | None:
    """Verify a pik-connect phone JWT.  Returns the claims dict or ``None``."""
    if not JWT_SECRET:
        return None
    try:
        claims = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            options={"require": ["sub", "exp", "iss"]},
        )
        if claims.get("iss") != JWT_ISSUER:
            return None
        return claims
    except Exception:  # noqa: BLE001
        return None


def is_phone_jwt(token: str) -> bool:
    """Quick unverified issuer check — avoids hitting Supabase JWKS for our tokens."""
    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
        return unverified.get("iss") == JWT_ISSUER
    except Exception:  # noqa: BLE001
        return False
