#!/usr/bin/env python3
"""
Final Backend Verification for Booking System MVP
Tests all critical endpoints and runs a complete throwaway booking lifecycle.
"""

import requests
import json
import time
from datetime import datetime, timedelta

# Backend URL from frontend/.env
BASE_URL = "https://newclient-app-2.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"
SUPERADMIN_EMAIL = "prabhakar@pkphotography.in"
SUPERADMIN_PASSWORD = "SuperAdmin@3214"

# Test results
results = []
admin_token = None
superadmin_token = None
client_token = None
test_event_id = None
test_booking_id = None

def log_test(test_name, passed, details=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    results.append(f"{status}: {test_name}")
    if details:
        results.append(f"   {details}")
    print(f"{status}: {test_name}")
    if details:
        print(f"   {details}")

def test_health_check():
    """Test 1: GET /api/ health check"""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            log_test("GET /api/ (health check)", True, f"Response: {data}")
            return True
        else:
            log_test("GET /api/ (health check)", False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("GET /api/ (health check)", False, f"Error: {str(e)}")
        return False

def test_admin_login():
    """Test 2: Admin login"""
    global admin_token
    try:
        response = requests.post(
            f"{BASE_URL}/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            admin_token = data.get("session_token")
            log_test("Admin login", True, f"Token received, role: {data.get('user', {}).get('role')}")
            return True
        else:
            log_test("Admin login", False, f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        log_test("Admin login", False, f"Error: {str(e)}")
        return False

def test_superadmin_login():
    """Test 3: Superadmin login"""
    global superadmin_token
    try:
        response = requests.post(
            f"{BASE_URL}/superadmin/login",
            json={"email": SUPERADMIN_EMAIL, "password": SUPERADMIN_PASSWORD},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            superadmin_token = data.get("session_token")
            log_test("Superadmin login", True, f"Token received, role: {data.get('user', {}).get('role')}")
            return True
        else:
            log_test("Superadmin login", False, f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        log_test("Superadmin login", False, f"Error: {str(e)}")
        return False

def test_admin_get_bookings():
    """Test 4: Admin GET /api/bookings"""
    try:
        response = requests.get(
            f"{BASE_URL}/bookings",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            count = len(data) if isinstance(data, list) else data.get("count", 0)
            log_test("Admin GET /api/bookings", True, f"Retrieved {count} booking(s)")
            return True
        else:
            log_test("Admin GET /api/bookings", False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("Admin GET /api/bookings", False, f"Error: {str(e)}")
        return False

def test_admin_get_bookings_calendar():
    """Test 5: Admin GET /api/bookings-calendar"""
    try:
        response = requests.get(
            f"{BASE_URL}/bookings-calendar",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            count = len(data) if isinstance(data, list) else 0
            log_test("Admin GET /api/bookings-calendar", True, f"Retrieved {count} calendar booking(s)")
            return True
        else:
            log_test("Admin GET /api/bookings-calendar", False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("Admin GET /api/bookings-calendar", False, f"Error: {str(e)}")
        return False

def test_create_throwaway_event():
    """Test 6: Create throwaway event for booking"""
    global test_event_id
    try:
        response = requests.post(
            f"{BASE_URL}/events",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "QA Final Verification Event",
                "category": "wedding",
                "date": "2027-08-15"
            },
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            test_event_id = data.get("event_id")
            log_test("Create throwaway event", True, f"Event ID: {test_event_id}")
            return True
        else:
            log_test("Create throwaway event", False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("Create throwaway event", False, f"Error: {str(e)}")
        return False

def test_client_otp_request():
    """Test 7: Client OTP request"""
    try:
        response = requests.post(
            f"{BASE_URL}/auth/client/request-otp",
            json={"channel": "phone", "phone": "+919876543210"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            dev_code = data.get("dev_code")
            log_test("Client OTP request", True, f"Dev code: {dev_code}")
            return dev_code
        else:
            log_test("Client OTP request", False, f"Status: {response.status_code}")
            return None
    except Exception as e:
        log_test("Client OTP request", False, f"Error: {str(e)}")
        return None

def test_client_otp_verify(dev_code):
    """Test 8: Client OTP verify"""
    global client_token
    try:
        response = requests.post(
            f"{BASE_URL}/auth/client/verify-otp",
            json={"channel": "phone", "phone": "+919876543210", "code": dev_code},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            client_token = data.get("session_token")
            log_test("Client OTP verify", True, f"Client token received")
            return True
        else:
            log_test("Client OTP verify", False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("Client OTP verify", False, f"Error: {str(e)}")
        return False

def test_client_event_access():
    """Test 9: Client event access (visitor registration)"""
    try:
        # Use public endpoint without auth header
        response = requests.post(
            f"{BASE_URL}/public/events/{test_event_id}/access",
            json={"name": "QA Test Client", "phone": "+919876543210"},
            timeout=10
        )
        if response.status_code == 200:
            log_test("Client event access", True, "Visitor registered successfully")
            return True
        else:
            log_test("Client event access", False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("Client event access", False, f"Error: {str(e)}")
        return False

def test_create_booking_request():
    """Test 10: Create client booking request"""
    global test_booking_id
    try:
        # Calculate future date
        future_date = (datetime.now() + timedelta(days=180)).strftime("%Y-%m-%d")
        
        response = requests.post(
            f"{BASE_URL}/me/booking-requests",
            headers={"Authorization": f"Bearer {client_token}"},
            json={
                "service_type": "wedding",
                "event_name": "Summer Wedding 2027",
                "preferred_date": future_date,
                "start_time": "16:00",
                "end_time": "23:00",
                "location": "Grand Hyatt, Mumbai",
                "requirement": "Full day wedding coverage with candid photography, traditional shots, and drone footage",
                "expected_budget": 150000,
                "message": "Looking for premium wedding photography package"
            },
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            # Try different possible field names
            test_booking_id = data.get("booking_id") or data.get("id") or data.get("request_id")
            log_test("Create booking request", True, f"Response: {data}, Booking ID: {test_booking_id}")
            return True
        else:
            log_test("Create booking request", False, f"Status: {response.status_code}, Response: {response.text}")
            return False
    except Exception as e:
        log_test("Create booking request", False, f"Error: {str(e)}")
        return False

def test_admin_sees_booking():
    """Test 11: Admin sees the booking"""
    try:
        response = requests.get(
            f"{BASE_URL}/bookings/{test_booking_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            log_test("Admin sees booking", True, f"Event: {data.get('event_name')}, Status: {data.get('status')}")
            return True
        else:
            log_test("Admin sees booking", False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("Admin sees booking", False, f"Error: {str(e)}")
        return False

def test_admin_send_quotation():
    """Test 12: Admin sends quotation"""
    try:
        response = requests.post(
            f"{BASE_URL}/bookings/{test_booking_id}/quote",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "total_amount": 180000,
                "advance_amount": 60000,
                "payment_terms": "60k advance, balance on delivery",
                "notes": "Premium wedding package with drone coverage"
            },
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            log_test("Admin sends quotation", True, f"Status: {data.get('status')}, Amount: {data.get('total_amount')}")
            return True
        else:
            log_test("Admin sends quotation", False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("Admin sends quotation", False, f"Error: {str(e)}")
        return False

def test_client_get_bookings():
    """Test 13: Client GET /api/me/bookings"""
    try:
        response = requests.get(
            f"{BASE_URL}/me/bookings",
            headers={"Authorization": f"Bearer {client_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            count = len(data) if isinstance(data, list) else 0
            log_test("Client GET /api/me/bookings", True, f"Retrieved {count} booking(s)")
            return True
        else:
            log_test("Client GET /api/me/bookings", False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("Client GET /api/me/bookings", False, f"Error: {str(e)}")
        return False

def test_client_accept_quotation():
    """Test 14: Client accepts quotation"""
    try:
        response = requests.post(
            f"{BASE_URL}/me/bookings/{test_booking_id}/quote/accept",
            headers={"Authorization": f"Bearer {client_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            log_test("Client accepts quotation", True, f"Status: {data.get('status')}")
            return True
        else:
            log_test("Client accepts quotation", False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("Client accepts quotation", False, f"Error: {str(e)}")
        return False

def test_admin_record_partial_payment():
    """Test 15: Admin records partial offline payment"""
    try:
        response = requests.post(
            f"{BASE_URL}/bookings/{test_booking_id}/payments",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "label": "Partial advance payment",
                "amount": 30000,
                "method": "cash",
                "notes": "Received 30k cash as partial advance"
            },
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            log_test("Admin records partial payment", True, 
                    f"Paid: {data.get('paid_amount')}, Remaining: {data.get('remaining_amount')}, Status: {data.get('status')}")
            return True
        else:
            log_test("Admin records partial payment", False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("Admin records partial payment", False, f"Error: {str(e)}")
        return False

def test_verify_payment_pending():
    """Test 16: Verify status remains payment_pending"""
    try:
        response = requests.get(
            f"{BASE_URL}/bookings/{test_booking_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            paid = data.get("paid_amount")
            remaining = data.get("remaining_amount")
            if status == "payment_pending" and remaining > 0:
                log_test("Verify payment_pending status", True, 
                        f"Status: {status}, Paid: {paid}, Remaining: {remaining}")
                return True
            else:
                log_test("Verify payment_pending status", False, 
                        f"Expected payment_pending with remaining > 0, got status={status}, remaining={remaining}")
                return False
        else:
            log_test("Verify payment_pending status", False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("Verify payment_pending status", False, f"Error: {str(e)}")
        return False

def test_client_get_notifications():
    """Test 17: Client GET /api/me/notifications"""
    try:
        response = requests.get(
            f"{BASE_URL}/me/notifications",
            headers={"Authorization": f"Bearer {client_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            count = len(data) if isinstance(data, list) else 0
            log_test("Client GET /api/me/notifications", True, f"Retrieved {count} notification(s)")
            return True
        else:
            log_test("Client GET /api/me/notifications", False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("Client GET /api/me/notifications", False, f"Error: {str(e)}")
        return False

def test_cleanup_booking():
    """Test 18: Cleanup - Delete throwaway event (cascades to booking)"""
    try:
        response = requests.delete(
            f"{BASE_URL}/events/{test_event_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 200:
            log_test("Cleanup throwaway event", True, "Event and associated data deleted")
            return True
        else:
            log_test("Cleanup throwaway event", False, f"Status: {response.status_code}")
            return False
    except Exception as e:
        log_test("Cleanup throwaway event", False, f"Error: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("=" * 80)
    print("FINAL BACKEND VERIFICATION - BOOKING SYSTEM MVP")
    print("=" * 80)
    print()
    
    # Test 1: Health check
    if not test_health_check():
        print("\n❌ Health check failed. Aborting tests.")
        return
    
    # Test 2: Admin login
    if not test_admin_login():
        print("\n❌ Admin login failed. Aborting tests.")
        return
    
    # Test 3: Superadmin login
    test_superadmin_login()
    
    # Test 4-5: Admin booking endpoints
    test_admin_get_bookings()
    test_admin_get_bookings_calendar()
    
    # Test 6: Create throwaway event
    if not test_create_throwaway_event():
        print("\n❌ Event creation failed. Aborting booking tests.")
        return
    
    # Test 7-9: Client authentication and event access
    dev_code = test_client_otp_request()
    if not dev_code:
        print("\n❌ Client OTP request failed. Aborting booking tests.")
        return
    
    if not test_client_otp_verify(dev_code):
        print("\n❌ Client OTP verify failed. Aborting booking tests.")
        return
    
    if not test_client_event_access():
        print("\n❌ Client event access failed. Aborting booking tests.")
        return
    
    # Test 10-17: Complete booking lifecycle
    if not test_create_booking_request():
        print("\n❌ Booking creation failed. Aborting lifecycle tests.")
        return
    
    test_admin_sees_booking()
    test_admin_send_quotation()
    test_client_get_bookings()
    test_client_accept_quotation()
    test_admin_record_partial_payment()
    test_verify_payment_pending()
    test_client_get_notifications()
    
    # Test 18: Cleanup
    test_cleanup_booking()
    
    # Summary
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    passed = sum(1 for r in results if r.startswith("✅"))
    failed = sum(1 for r in results if r.startswith("❌"))
    print(f"Total: {passed + failed} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print()
    
    if failed > 0:
        print("FAILED TESTS:")
        for r in results:
            if r.startswith("❌"):
                print(r)
    else:
        print("✅ ALL TESTS PASSED")
    
    print("=" * 80)

if __name__ == "__main__":
    main()
