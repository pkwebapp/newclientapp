#!/usr/bin/env python3
"""
Backend test for user-reported booking verification.
Tests booking for client phone 7506811017 with name Prabhat.
Verifies fallback routing to DEFAULT_BOOKING_ADMIN_PHONE=8888766739.
"""
import requests
import json
import sys
from typing import Optional

# Backend URL from frontend/.env
BACKEND_URL = "https://ab1b5b53-cd84-4df4-bf72-9cc6253f1656.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

# User-reported booking details
CLIENT_PHONE = "7506811017"
CLIENT_NAME = "Prabhat"
DEFAULT_BOOKING_ADMIN_PHONE = "8888766739"

def log(msg: str):
    """Print test log message."""
    print(f"[TEST] {msg}")

def log_error(msg: str):
    """Print error message."""
    print(f"[ERROR] {msg}", file=sys.stderr)

def log_success(msg: str):
    """Print success message."""
    print(f"[✅ PASS] {msg}")

def log_fail(msg: str):
    """Print failure message."""
    print(f"[❌ FAIL] {msg}")

def admin_login() -> Optional[str]:
    """Login as admin and return session token."""
    log(f"Logging in as admin: {ADMIN_EMAIL}")
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("session_token")
            if token:
                log_success(f"Admin login successful → 200 with session_token")
                return token
            else:
                log_fail("Admin login returned 200 but no session_token")
                return None
        else:
            log_fail(f"Admin login failed → {resp.status_code}")
            log_error(f"Response: {resp.text}")
            return None
    except Exception as e:
        log_error(f"Admin login exception: {e}")
        return None

def get_bookings(admin_token: str) -> list:
    """Get all bookings for the admin."""
    log("Fetching admin bookings: GET /api/bookings")
    try:
        resp = requests.get(
            f"{BACKEND_URL}/bookings",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            bookings = data if isinstance(data, list) else []
            log_success(f"GET /api/bookings → 200 with {len(bookings)} booking(s)")
            return bookings
        else:
            log_fail(f"GET /api/bookings → {resp.status_code}")
            log_error(f"Response: {resp.text}")
            return []
    except Exception as e:
        log_error(f"GET /api/bookings exception: {e}")
        return []

def normalize_phone(phone: str) -> str:
    """Normalize phone number for comparison (remove +91 prefix if present)."""
    phone = phone.strip()
    if phone.startswith("+91"):
        return phone[3:]
    if phone.startswith("91") and len(phone) == 12:
        return phone[2:]
    return phone

def find_booking_for_client(bookings: list, phone: str, name: str) -> Optional[dict]:
    """Find booking matching the client phone and/or name."""
    log(f"Searching for booking with phone={phone} or name={name}")
    normalized_target = normalize_phone(phone)
    
    for booking in bookings:
        contact_phone = booking.get("contact_phone", "")
        contact_name = booking.get("contact_name", "")
        
        # Normalize the booking phone for comparison
        normalized_booking_phone = normalize_phone(contact_phone)
        
        # Check if phone matches (with or without +91 prefix)
        phone_match = (
            normalized_booking_phone == normalized_target or
            contact_phone == phone or
            contact_phone == f"+91{phone}"
        )
        
        # Check if name matches (case-insensitive)
        name_match = contact_name.lower() == name.lower()
        
        if phone_match or name_match:
            log_success(f"Found matching booking: request_id={booking.get('request_id')}")
            log(f"  - contact_name: {contact_name}")
            log(f"  - contact_phone: {contact_phone}")
            log(f"  - routing_source: {booking.get('routing_source')}")
            log(f"  - studio_id: {booking.get('studio_id')}")
            return booking
    
    log_fail(f"No booking found for phone={phone} or name={name}")
    return None

def verify_booking_routing(booking: dict, admin_token: str) -> bool:
    """Verify the booking has correct fallback routing."""
    log("Verifying booking routing details...")
    
    request_id = booking.get("request_id")
    routing_source = booking.get("routing_source")
    studio_id = booking.get("studio_id")
    
    all_checks_passed = True
    
    # Check 1: routing_source should be "default_admin_phone"
    if routing_source == "default_admin_phone":
        log_success(f"✓ routing_source = 'default_admin_phone' (correct)")
    else:
        log_fail(f"✗ routing_source = '{routing_source}' (expected 'default_admin_phone')")
        all_checks_passed = False
    
    # Check 2: studio_id should not be null
    if studio_id:
        log_success(f"✓ studio_id = {studio_id} (not null)")
    else:
        log_fail(f"✗ studio_id is null (should be resolved to fallback admin)")
        all_checks_passed = False
    
    # Check 3: Verify notification exists for this booking
    log(f"Checking for notification for booking {request_id}...")
    try:
        resp = requests.get(
            f"{BACKEND_URL}/notifications",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            # Handle both list and {"items": [...]} response formats
            if isinstance(data, dict) and "items" in data:
                notifications = data["items"]
            elif isinstance(data, list):
                notifications = data
            else:
                notifications = []
            
            booking_notification = None
            for notif in notifications:
                if isinstance(notif, dict) and notif.get("booking_request_id") == request_id:
                    booking_notification = notif
                    break
            
            if booking_notification:
                log_success(f"✓ Notification found for booking {request_id}")
                log(f"  - notification_id: {booking_notification.get('notification_id')}")
                log(f"  - type: {booking_notification.get('type')}")
                log(f"  - title: {booking_notification.get('title')}")
                log(f"  - studio_id: {booking_notification.get('studio_id')}")
                
                # Verify notification studio_id matches booking studio_id
                if booking_notification.get("studio_id") == studio_id:
                    log_success(f"✓ Notification studio_id matches booking studio_id")
                else:
                    log_fail(f"✗ Notification studio_id mismatch")
                    all_checks_passed = False
            else:
                log_fail(f"✗ No notification found for booking {request_id}")
                all_checks_passed = False
        else:
            log_fail(f"GET /api/notifications → {resp.status_code}")
            all_checks_passed = False
    except Exception as e:
        log_error(f"GET /api/notifications exception: {e}")
        all_checks_passed = False
    
    return all_checks_passed

def client_otp_login(phone: str) -> Optional[str]:
    """Login as client using OTP flow and return session token."""
    log(f"Client OTP login for phone: {phone}")
    
    # Normalize phone to +91 format
    if not phone.startswith("+"):
        phone = f"+91{phone}"
    
    # Step 1: Request OTP
    log(f"Step 1: Requesting OTP for {phone}")
    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/client/request-otp",
            json={"channel": "phone", "phone": phone},
            timeout=10
        )
        if resp.status_code != 200:
            log_fail(f"OTP request failed → {resp.status_code}")
            log_error(f"Response: {resp.text}")
            return None
        
        data = resp.json()
        dev_code = data.get("dev_code")
        if not dev_code:
            log_fail("OTP request returned 200 but no dev_code (OTP_DEV_MODE may be disabled)")
            return None
        
        log_success(f"OTP requested → 200 with dev_code: {dev_code}")
        
        # Step 2: Verify OTP
        log(f"Step 2: Verifying OTP with dev_code: {dev_code}")
        resp = requests.post(
            f"{BACKEND_URL}/auth/client/verify-otp",
            json={"channel": "phone", "phone": phone, "code": dev_code},
            timeout=10
        )
        if resp.status_code != 200:
            log_fail(f"OTP verification failed → {resp.status_code}")
            log_error(f"Response: {resp.text}")
            return None
        
        data = resp.json()
        token = data.get("session_token")
        if not token:
            log_fail("OTP verification returned 200 but no session_token")
            return None
        
        log_success(f"OTP verified → 200 with session_token")
        return token
        
    except Exception as e:
        log_error(f"Client OTP login exception: {e}")
        return None

def create_test_booking(client_token: str, name: str) -> Optional[str]:
    """Create a test booking and return request_id."""
    log(f"Creating test booking for client: {name}")
    
    booking_data = {
        "service_type": "Wedding Photography",
        "event_name": "Test Booking - Fallback Routing Verification",
        "preferred_date": "2026-12-20",
        "location": "Mumbai",
        "expected_budget": 75000,
        "message": "Test booking enquiry to verify fallback routing to DEFAULT_BOOKING_ADMIN_PHONE"
    }
    
    try:
        resp = requests.post(
            f"{BACKEND_URL}/me/booking-requests",
            headers={"Authorization": f"Bearer {client_token}"},
            json=booking_data,
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            request_id = data.get("request_id")
            if request_id:
                log_success(f"Booking created → 200 with request_id: {request_id}")
                return request_id
            else:
                log_fail("Booking creation returned 200 but no request_id")
                return None
        else:
            log_fail(f"Booking creation failed → {resp.status_code}")
            log_error(f"Response: {resp.text}")
            return None
    except Exception as e:
        log_error(f"Booking creation exception: {e}")
        return None

def get_client_bookings(client_token: str) -> list:
    """Get bookings for the client."""
    log("Fetching client bookings: GET /api/me/bookings")
    try:
        resp = requests.get(
            f"{BACKEND_URL}/me/bookings",
            headers={"Authorization": f"Bearer {client_token}"},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            bookings = data if isinstance(data, list) else []
            log_success(f"GET /api/me/bookings → 200 with {len(bookings)} booking(s)")
            return bookings
        else:
            log_fail(f"GET /api/me/bookings → {resp.status_code}")
            log_error(f"Response: {resp.text}")
            return []
    except Exception as e:
        log_error(f"GET /api/me/bookings exception: {e}")
        return []

def check_backend_logs():
    """Check backend logs for errors."""
    log("Checking backend logs for errors...")
    import subprocess
    try:
        result = subprocess.run(
            ["tail", "-n", "50", "/var/log/supervisor/backend.err.log"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            errors = result.stdout.strip()
            if errors:
                # Filter out expected OTP email errors
                lines = errors.split("\n")
                critical_errors = [line for line in lines if "Traceback" in line or "ERROR" in line]
                critical_errors = [line for line in critical_errors if "OTP email" not in line and "Email send failed" not in line]
                
                if critical_errors:
                    log_fail(f"Found {len(critical_errors)} critical error(s) in backend logs")
                    for err in critical_errors[:5]:  # Show first 5
                        log_error(err)
                else:
                    log_success("No critical errors in backend logs (only expected OTP email warnings)")
            else:
                log_success("Backend error log is empty")
        else:
            log("Could not read backend error log")
    except Exception as e:
        log(f"Could not check backend logs: {e}")

def main():
    """Main test execution."""
    print("=" * 80)
    print("BOOKING FALLBACK ROUTING VERIFICATION TEST")
    print("=" * 80)
    print(f"Client Phone: {CLIENT_PHONE}")
    print(f"Client Name: {CLIENT_NAME}")
    print(f"Expected Fallback Admin Phone: {DEFAULT_BOOKING_ADMIN_PHONE}")
    print("=" * 80)
    print()
    
    # Step 1: Admin login
    admin_token = admin_login()
    if not admin_token:
        log_error("Cannot proceed without admin token")
        sys.exit(1)
    print()
    
    # Step 2: Get all bookings
    bookings = get_bookings(admin_token)
    print()
    
    # Step 3: Search for existing booking
    existing_booking = find_booking_for_client(bookings, CLIENT_PHONE, CLIENT_NAME)
    print()
    
    if existing_booking:
        # Verify the existing booking
        log("PART A: EXISTING BOOKING VERIFICATION")
        print("-" * 80)
        verification_passed = verify_booking_routing(existing_booking, admin_token)
        print()
        
        if verification_passed:
            log_success("✅ ALL CHECKS PASSED - Existing booking verified successfully")
        else:
            log_fail("❌ SOME CHECKS FAILED - Existing booking has issues")
        print()
    else:
        # Reproduce the booking
        log("PART B: BOOKING REPRODUCTION (Existing booking not found)")
        print("-" * 80)
        
        # Step 4: Client OTP login
        client_token = client_otp_login(CLIENT_PHONE)
        if not client_token:
            log_error("Cannot proceed without client token")
            sys.exit(1)
        print()
        
        # Step 5: Create test booking
        request_id = create_test_booking(client_token, CLIENT_NAME)
        if not request_id:
            log_error("Failed to create test booking")
            sys.exit(1)
        print()
        
        # Step 6: Verify booking appears in client's list
        client_bookings = get_client_bookings(client_token)
        client_booking = next((b for b in client_bookings if b.get("request_id") == request_id), None)
        if client_booking:
            log_success(f"✓ Booking {request_id} found in client's booking list")
        else:
            log_fail(f"✗ Booking {request_id} NOT found in client's booking list")
        print()
        
        # Step 7: Verify booking appears in admin's list
        bookings = get_bookings(admin_token)
        admin_booking = next((b for b in bookings if b.get("request_id") == request_id), None)
        if admin_booking:
            log_success(f"✓ Booking {request_id} found in admin's booking list")
            print()
            
            # Step 8: Verify routing
            verification_passed = verify_booking_routing(admin_booking, admin_token)
            print()
            
            if verification_passed:
                log_success("✅ ALL CHECKS PASSED - Reproduced booking verified successfully")
            else:
                log_fail("❌ SOME CHECKS FAILED - Reproduced booking has issues")
        else:
            log_fail(f"✗ Booking {request_id} NOT found in admin's booking list")
        print()
    
    # Step 9: Check backend logs
    check_backend_logs()
    print()
    
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
