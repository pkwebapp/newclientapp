"""
Backend API tests for Lumiere Gallery - Public Shareable Galleries Feature
Tests the new public share endpoints, visitor management, and access control
"""
import requests
import json
import sys
import time

# Configuration
BASE_URL = "https://new-client-hub.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

# Test results tracking
tests_passed = 0
tests_failed = 0
test_results = []

def log_test(test_name, passed, details=""):
    global tests_passed, tests_failed
    status = "✅ PASS" if passed else "❌ FAIL"
    result = f"{status} - {test_name}"
    if details:
        result += f"\n    {details}"
    test_results.append(result)
    print(result)
    if passed:
        tests_passed += 1
    else:
        tests_failed += 1

def test_admin_login():
    """Test 0: Admin login to get token"""
    print("\n=== Test 0: Admin Login ===")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("session_token")
            if token:
                log_test("Admin login", True, f"Token received: {token[:20]}...")
                return token
            else:
                log_test("Admin login", False, "No session_token in response")
                return None
        else:
            log_test("Admin login", False, f"Status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        log_test("Admin login", False, f"Exception: {str(e)}")
        return None

def test_1_create_event(admin_token):
    """Test 1: POST /api/events - create event with share_enabled=true by default"""
    print("\n=== Test 1: Create Event (share_enabled default) ===")
    try:
        event_data = {
            "name": f"Public Share Test Event {int(time.time())}",
            "date": "2026-02-15",
            "category": "wedding",
            "photographer": "Test Photographer"
        }
        response = requests.post(
            f"{BASE_URL}/events",
            json=event_data,
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code in [200, 201]:
            data = response.json()
            event_id = data.get("event_id")
            share_enabled = data.get("share_enabled")
            
            if not event_id:
                log_test("Test 1: Create event", False, "No event_id in response")
                return None
            
            if share_enabled != True:
                log_test("Test 1: Create event", False, f"Expected share_enabled=True, got {share_enabled}")
                return None
            
            log_test("Test 1: Create event", True, f"event_id={event_id}, share_enabled={share_enabled}")
            return event_id
        else:
            log_test("Test 1: Create event", False, f"Status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        log_test("Test 1: Create event", False, f"Exception: {str(e)}")
        return None

def test_2_get_share_info(admin_token, event_id):
    """Test 2: GET /api/events/{event_id}/share - confirm share_url, share_enabled, qr_base64"""
    print(f"\n=== Test 2: Get Share Info (event {event_id}) ===")
    try:
        response = requests.get(
            f"{BASE_URL}/events/{event_id}/share",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            share_url = data.get("share_url")
            share_enabled = data.get("share_enabled")
            qr_base64 = data.get("qr_base64")
            
            issues = []
            if not share_url:
                issues.append("Missing share_url")
            elif not share_url.endswith(f"/g/{event_id}"):
                issues.append(f"share_url doesn't end with /g/{event_id}: {share_url}")
            
            if share_enabled != True:
                issues.append(f"Expected share_enabled=True, got {share_enabled}")
            
            if not qr_base64:
                issues.append("Missing qr_base64")
            elif not qr_base64.startswith("data:image/png;base64,"):
                issues.append(f"qr_base64 doesn't start with 'data:image/png;base64,': {qr_base64[:50]}")
            
            if issues:
                log_test("Test 2: Get share info", False, "; ".join(issues))
                return False
            
            log_test("Test 2: Get share info", True, f"share_url={share_url}, share_enabled={share_enabled}, qr_base64 length={len(qr_base64)}")
            return True
        else:
            log_test("Test 2: Get share info", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 2: Get share info", False, f"Exception: {str(e)}")
        return False

def test_3_public_event_info(event_id):
    """Test 3: GET /api/public/events/{event_id} - NO AUTH, confirm event info"""
    print(f"\n=== Test 3: Public Event Info (NO AUTH) ===")
    try:
        response = requests.get(
            f"{BASE_URL}/public/events/{event_id}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            required_fields = ["event_id", "name", "category", "photo_count"]
            missing = [f for f in required_fields if f not in data]
            
            if missing:
                log_test("Test 3: Public event info", False, f"Missing fields: {missing}")
                return False
            
            if data.get("event_id") != event_id:
                log_test("Test 3: Public event info", False, f"event_id mismatch: expected {event_id}, got {data.get('event_id')}")
                return False
            
            log_test("Test 3: Public event info", True, f"name={data.get('name')}, category={data.get('category')}, photo_count={data.get('photo_count')}")
            return True
        else:
            log_test("Test 3: Public event info", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 3: Public event info", False, f"Exception: {str(e)}")
        return False

def test_4_public_access(event_id, name, phone):
    """Test 4: POST /api/public/events/{event_id}/access - NO AUTH, get session_token"""
    print(f"\n=== Test 4: Public Access (NO AUTH, name={name}, phone={phone}) ===")
    try:
        response = requests.post(
            f"{BASE_URL}/public/events/{event_id}/access",
            json={"name": name, "phone": phone},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            session_token = data.get("session_token")
            user = data.get("user", {})
            event = data.get("event", {})
            
            issues = []
            if not session_token:
                issues.append("Missing session_token")
            
            if not user.get("user_id"):
                issues.append("Missing user.user_id")
            if user.get("role") != "client":
                issues.append(f"Expected user.role=client, got {user.get('role')}")
            if user.get("name") != name:
                issues.append(f"Expected user.name={name}, got {user.get('name')}")
            if user.get("phone") != phone:
                issues.append(f"Expected user.phone={phone}, got {user.get('phone')}")
            
            if not event.get("event_id"):
                issues.append("Missing event.event_id")
            
            if issues:
                log_test("Test 4: Public access", False, "; ".join(issues))
                return None, None
            
            log_test("Test 4: Public access", True, f"session_token={session_token[:20]}..., user_id={user.get('user_id')}, role={user.get('role')}")
            return session_token, user.get("user_id")
        else:
            log_test("Test 4: Public access", False, f"Status {response.status_code}: {response.text}")
            return None, None
    except Exception as e:
        log_test("Test 4: Public access", False, f"Exception: {str(e)}")
        return None, None

def test_4b_public_access_validation(event_id):
    """Test 4b: Public access validation - empty name and short phone"""
    print(f"\n=== Test 4b: Public Access Validation ===")
    
    # Test empty name
    try:
        response = requests.post(
            f"{BASE_URL}/public/events/{event_id}/access",
            json={"name": "", "phone": "+91 90000 00002"},
            timeout=10
        )
        if response.status_code == 400:
            log_test("Test 4b.1: Empty name validation", True, f"Got 400 as expected: {response.json().get('detail', '')}")
        else:
            log_test("Test 4b.1: Empty name validation", False, f"Expected 400, got {response.status_code}")
    except Exception as e:
        log_test("Test 4b.1: Empty name validation", False, f"Exception: {str(e)}")
    
    # Test short phone (<6 chars)
    try:
        response = requests.post(
            f"{BASE_URL}/public/events/{event_id}/access",
            json={"name": "Test User", "phone": "123"},
            timeout=10
        )
        if response.status_code == 400:
            log_test("Test 4b.2: Short phone validation", True, f"Got 400 as expected: {response.json().get('detail', '')}")
        else:
            log_test("Test 4b.2: Short phone validation", False, f"Expected 400, got {response.status_code}")
    except Exception as e:
        log_test("Test 4b.2: Short phone validation", False, f"Exception: {str(e)}")

def test_5_visitor_access_photos(visitor_token, event_id):
    """Test 5: GET /api/client/events/{event_id}/photos - using visitor token"""
    print(f"\n=== Test 5: Visitor Access Photos (visitor token) ===")
    try:
        response = requests.get(
            f"{BASE_URL}/client/events/{event_id}/photos",
            headers={"Authorization": f"Bearer {visitor_token}"},
            timeout=10
        )
        if response.status_code == 200:
            photos = response.json()
            log_test("Test 5: Visitor access photos", True, f"Got {len(photos)} photos (empty is OK, just confirming authorized)")
            return True
        elif response.status_code == 403:
            log_test("Test 5: Visitor access photos", False, f"Got 403 - visitor not authorized: {response.text}")
            return False
        else:
            log_test("Test 5: Visitor access photos", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 5: Visitor access photos", False, f"Exception: {str(e)}")
        return False

def test_6_list_visitors(admin_token, event_id, expected_visitor_name, expected_phone):
    """Test 6: GET /api/events/{event_id}/visitors - confirm visitor appears"""
    print(f"\n=== Test 6: List Visitors (admin) ===")
    try:
        response = requests.get(
            f"{BASE_URL}/events/{event_id}/visitors",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 200:
            visitors = response.json()
            
            if not visitors:
                log_test("Test 6: List visitors", False, "No visitors returned")
                return None
            
            # Find the visitor we just created
            visitor = next((v for v in visitors if v.get("phone") == expected_phone), None)
            if not visitor:
                log_test("Test 6: List visitors", False, f"Visitor with phone {expected_phone} not found")
                return None
            
            # Check required fields
            required_fields = ["visitor_id", "name", "phone", "status", "matched_count", "liked_count"]
            missing = [f for f in required_fields if f not in visitor]
            if missing:
                log_test("Test 6: List visitors", False, f"Missing fields: {missing}")
                return None
            
            if visitor.get("name") != expected_visitor_name:
                log_test("Test 6: List visitors", False, f"Expected name={expected_visitor_name}, got {visitor.get('name')}")
                return None
            
            if visitor.get("status") != "active":
                log_test("Test 6: List visitors", False, f"Expected status=active, got {visitor.get('status')}")
                return None
            
            log_test("Test 6: List visitors", True, f"visitor_id={visitor.get('visitor_id')}, name={visitor.get('name')}, phone={visitor.get('phone')}, status={visitor.get('status')}, matched={visitor.get('matched_count')}, liked={visitor.get('liked_count')}")
            return visitor.get("visitor_id")
        else:
            log_test("Test 6: List visitors", False, f"Status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        log_test("Test 6: List visitors", False, f"Exception: {str(e)}")
        return None

def test_7_export_visitors(admin_token, event_id, expected_visitor_name):
    """Test 7: GET /api/events/{event_id}/visitors/export - confirm CSV"""
    print(f"\n=== Test 7: Export Visitors CSV (admin) ===")
    try:
        response = requests.get(
            f"{BASE_URL}/events/{event_id}/visitors/export",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            csv_content = response.text
            
            issues = []
            if "text/csv" not in content_type:
                issues.append(f"Expected Content-Type text/csv, got {content_type}")
            
            if not csv_content:
                issues.append("Empty CSV content")
            else:
                lines = csv_content.strip().split("\n")
                if len(lines) < 2:
                    issues.append(f"Expected at least 2 lines (header + data), got {len(lines)}")
                else:
                    header = lines[0]
                    if "Name" not in header or "Mobile" not in header or "Status" not in header:
                        issues.append(f"CSV header missing expected columns: {header}")
                    
                    # Check if visitor appears in CSV
                    if expected_visitor_name not in csv_content:
                        issues.append(f"Visitor name '{expected_visitor_name}' not found in CSV")
            
            if issues:
                log_test("Test 7: Export visitors CSV", False, "; ".join(issues))
                return False
            
            log_test("Test 7: Export visitors CSV", True, f"Content-Type={content_type}, lines={len(lines)}, contains visitor '{expected_visitor_name}'")
            return True
        else:
            log_test("Test 7: Export visitors CSV", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 7: Export visitors CSV", False, f"Exception: {str(e)}")
        return False

def test_8_block_visitor(admin_token, event_id, visitor_id):
    """Test 8: PATCH /api/events/{event_id}/visitors/{visitor_id} - block visitor"""
    print(f"\n=== Test 8: Block Visitor (admin) ===")
    try:
        response = requests.patch(
            f"{BASE_URL}/events/{event_id}/visitors/{visitor_id}",
            json={"status": "blocked"},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("status") != "blocked":
                log_test("Test 8: Block visitor", False, f"Expected status=blocked, got {data.get('status')}")
                return False
            
            log_test("Test 8: Block visitor", True, f"status={data.get('status')}")
            return True
        else:
            log_test("Test 8: Block visitor", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 8: Block visitor", False, f"Exception: {str(e)}")
        return False

def test_9_blocked_access(event_id, blocked_phone):
    """Test 9: POST /api/public/events/{event_id}/access - blocked phone should get 403"""
    print(f"\n=== Test 9: Blocked Visitor Access (blocked phone) ===")
    try:
        response = requests.post(
            f"{BASE_URL}/public/events/{event_id}/access",
            json={"name": "Blocked User", "phone": blocked_phone},
            timeout=10
        )
        if response.status_code == 403:
            log_test("Test 9: Blocked visitor access", True, f"Got 403 as expected: {response.json().get('detail', '')}")
            return True
        else:
            log_test("Test 9: Blocked visitor access", False, f"Expected 403, got {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 9: Blocked visitor access", False, f"Exception: {str(e)}")
        return False

def test_10_blocked_visitor_photos(blocked_visitor_token, event_id):
    """Test 10: GET /api/client/events/{event_id}/photos - blocked visitor token should get 401/403"""
    print(f"\n=== Test 10: Blocked Visitor Photos Access ===")
    try:
        response = requests.get(
            f"{BASE_URL}/client/events/{event_id}/photos",
            headers={"Authorization": f"Bearer {blocked_visitor_token}"},
            timeout=10
        )
        if response.status_code in [401, 403]:
            log_test("Test 10: Blocked visitor photos", True, f"Got {response.status_code} as expected (grant revoked + sessions deleted)")
            return True
        else:
            log_test("Test 10: Blocked visitor photos", False, f"Expected 401 or 403, got {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 10: Blocked visitor photos", False, f"Exception: {str(e)}")
        return False

def test_11_unblock_visitor(admin_token, event_id, visitor_id):
    """Test 11: PATCH /api/events/{event_id}/visitors/{visitor_id} - unblock visitor"""
    print(f"\n=== Test 11: Unblock Visitor (admin) ===")
    try:
        response = requests.patch(
            f"{BASE_URL}/events/{event_id}/visitors/{visitor_id}",
            json={"status": "active"},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("status") != "active":
                log_test("Test 11: Unblock visitor", False, f"Expected status=active, got {data.get('status')}")
                return False
            
            log_test("Test 11: Unblock visitor", True, f"status={data.get('status')}")
            return True
        else:
            log_test("Test 11: Unblock visitor", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 11: Unblock visitor", False, f"Exception: {str(e)}")
        return False

def test_12_unblocked_access(event_id, unblocked_phone):
    """Test 12: POST /api/public/events/{event_id}/access - unblocked phone should get 200"""
    print(f"\n=== Test 12: Unblocked Visitor Access ===")
    try:
        response = requests.post(
            f"{BASE_URL}/public/events/{event_id}/access",
            json={"name": "Unblocked User", "phone": unblocked_phone},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if not data.get("session_token"):
                log_test("Test 12: Unblocked visitor access", False, "Missing session_token")
                return False
            
            log_test("Test 12: Unblocked visitor access", True, f"Got 200 with session_token")
            return True
        else:
            log_test("Test 12: Unblocked visitor access", False, f"Expected 200, got {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 12: Unblocked visitor access", False, f"Exception: {str(e)}")
        return False

def test_13_disable_sharing(admin_token, event_id):
    """Test 13: PATCH /api/events/{event_id} - disable sharing"""
    print(f"\n=== Test 13: Disable Sharing (admin) ===")
    try:
        response = requests.patch(
            f"{BASE_URL}/events/{event_id}",
            json={"share_enabled": False},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("share_enabled") != False:
                log_test("Test 13: Disable sharing", False, f"Expected share_enabled=False, got {data.get('share_enabled')}")
                return False
            
            log_test("Test 13: Disable sharing", True, f"share_enabled={data.get('share_enabled')}")
            return True
        else:
            log_test("Test 13: Disable sharing", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 13: Disable sharing", False, f"Exception: {str(e)}")
        return False

def test_14_disabled_public_endpoints(event_id):
    """Test 14: Public endpoints should return 403 when sharing is disabled"""
    print(f"\n=== Test 14: Disabled Public Endpoints ===")
    
    # Test 14a: GET /api/public/events/{event_id}
    try:
        response = requests.get(
            f"{BASE_URL}/public/events/{event_id}",
            timeout=10
        )
        if response.status_code == 403:
            log_test("Test 14a: Public event info (disabled)", True, f"Got 403 as expected")
        else:
            log_test("Test 14a: Public event info (disabled)", False, f"Expected 403, got {response.status_code}")
    except Exception as e:
        log_test("Test 14a: Public event info (disabled)", False, f"Exception: {str(e)}")
    
    # Test 14b: POST /api/public/events/{event_id}/access
    try:
        response = requests.post(
            f"{BASE_URL}/public/events/{event_id}/access",
            json={"name": "Test User", "phone": "+91 90000 00003"},
            timeout=10
        )
        if response.status_code == 403:
            log_test("Test 14b: Public access (disabled)", True, f"Got 403 as expected")
        else:
            log_test("Test 14b: Public access (disabled)", False, f"Expected 403, got {response.status_code}")
    except Exception as e:
        log_test("Test 14b: Public access (disabled)", False, f"Exception: {str(e)}")

def test_15_enable_sharing(admin_token, event_id):
    """Test 15: PATCH /api/events/{event_id} - re-enable sharing"""
    print(f"\n=== Test 15: Re-enable Sharing (admin) ===")
    try:
        response = requests.patch(
            f"{BASE_URL}/events/{event_id}",
            json={"share_enabled": True},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("share_enabled") != True:
                log_test("Test 15: Re-enable sharing", False, f"Expected share_enabled=True, got {data.get('share_enabled')}")
                return False
            
            log_test("Test 15: Re-enable sharing", True, f"share_enabled={data.get('share_enabled')}")
            return True
        else:
            log_test("Test 15: Re-enable sharing", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 15: Re-enable sharing", False, f"Exception: {str(e)}")
        return False

def test_16_auth_checks(event_id, visitor_token):
    """Test 16: Auth checks - 401/403 on protected endpoints"""
    print(f"\n=== Test 16: Auth Checks ===")
    
    # Test 16a: GET /api/events/{event_id}/share without token -> 401
    try:
        response = requests.get(
            f"{BASE_URL}/events/{event_id}/share",
            timeout=10
        )
        if response.status_code == 401:
            log_test("Test 16a: Share info without token", True, f"Got 401 as expected")
        else:
            log_test("Test 16a: Share info without token", False, f"Expected 401, got {response.status_code}")
    except Exception as e:
        log_test("Test 16a: Share info without token", False, f"Exception: {str(e)}")
    
    # Test 16b: GET /api/events/{event_id}/visitors without token -> 401
    try:
        response = requests.get(
            f"{BASE_URL}/events/{event_id}/visitors",
            timeout=10
        )
        if response.status_code == 401:
            log_test("Test 16b: Visitors list without token", True, f"Got 401 as expected")
        else:
            log_test("Test 16b: Visitors list without token", False, f"Expected 401, got {response.status_code}")
    except Exception as e:
        log_test("Test 16b: Visitors list without token", False, f"Exception: {str(e)}")
    
    # Test 16c: GET /api/events/{event_id}/visitors/export without token -> 401
    try:
        response = requests.get(
            f"{BASE_URL}/events/{event_id}/visitors/export",
            timeout=10
        )
        if response.status_code == 401:
            log_test("Test 16c: Visitors export without token", True, f"Got 401 as expected")
        else:
            log_test("Test 16c: Visitors export without token", False, f"Expected 401, got {response.status_code}")
    except Exception as e:
        log_test("Test 16c: Visitors export without token", False, f"Exception: {str(e)}")
    
    # Test 16d: GET /api/events/{event_id}/share with CLIENT token -> 403
    try:
        response = requests.get(
            f"{BASE_URL}/events/{event_id}/share",
            headers={"Authorization": f"Bearer {visitor_token}"},
            timeout=10
        )
        if response.status_code == 403:
            log_test("Test 16d: Share info with client token", True, f"Got 403 as expected")
        else:
            log_test("Test 16d: Share info with client token", False, f"Expected 403, got {response.status_code}")
    except Exception as e:
        log_test("Test 16d: Share info with client token", False, f"Exception: {str(e)}")
    
    # Test 16e: GET /api/events/{event_id}/visitors with CLIENT token -> 403
    try:
        response = requests.get(
            f"{BASE_URL}/events/{event_id}/visitors",
            headers={"Authorization": f"Bearer {visitor_token}"},
            timeout=10
        )
        if response.status_code == 403:
            log_test("Test 16e: Visitors list with client token", True, f"Got 403 as expected")
        else:
            log_test("Test 16e: Visitors list with client token", False, f"Expected 403, got {response.status_code}")
    except Exception as e:
        log_test("Test 16e: Visitors list with client token", False, f"Exception: {str(e)}")
    
    # Test 16f: GET /api/events/{event_id}/visitors/export with CLIENT token -> 403
    try:
        response = requests.get(
            f"{BASE_URL}/events/{event_id}/visitors/export",
            headers={"Authorization": f"Bearer {visitor_token}"},
            timeout=10
        )
        if response.status_code == 403:
            log_test("Test 16f: Visitors export with client token", True, f"Got 403 as expected")
        else:
            log_test("Test 16f: Visitors export with client token", False, f"Expected 403, got {response.status_code}")
    except Exception as e:
        log_test("Test 16f: Visitors export with client token", False, f"Exception: {str(e)}")

def main():
    print("=" * 80)
    print("LUMIERE GALLERY - BACKEND API TESTS (Public Shareable Galleries)")
    print("=" * 80)
    
    # Setup: Admin login
    admin_token = test_admin_login()
    if not admin_token:
        print("\n❌ CRITICAL: Admin login failed. Cannot continue tests.")
        sys.exit(1)
    
    # Test 1: Create event
    event_id = test_1_create_event(admin_token)
    if not event_id:
        print("\n❌ CRITICAL: Failed to create event. Cannot continue tests.")
        sys.exit(1)
    
    print(f"\n📋 Using event_id: {event_id}")
    
    # Test 2: Get share info
    test_2_get_share_info(admin_token, event_id)
    
    # Test 3: Public event info (no auth)
    test_3_public_event_info(event_id)
    
    # Test 4: Public access (no auth)
    visitor_token, visitor_user_id = test_4_public_access(event_id, "Test Guest", "+91 90000 00001")
    if not visitor_token:
        print("\n❌ CRITICAL: Failed to get visitor token. Cannot continue tests.")
        sys.exit(1)
    
    # Test 4b: Public access validation
    test_4b_public_access_validation(event_id)
    
    # Test 5: Visitor access photos
    test_5_visitor_access_photos(visitor_token, event_id)
    
    # Test 6: List visitors
    visitor_id = test_6_list_visitors(admin_token, event_id, "Test Guest", "+91 90000 00001")
    if not visitor_id:
        print("\n❌ CRITICAL: Failed to get visitor_id. Cannot continue tests.")
        sys.exit(1)
    
    # Test 7: Export visitors CSV
    test_7_export_visitors(admin_token, event_id, "Test Guest")
    
    # Test 8: Block visitor
    test_8_block_visitor(admin_token, event_id, visitor_id)
    
    # Test 9: Blocked visitor access
    test_9_blocked_access(event_id, "+91 90000 00001")
    
    # Test 10: Blocked visitor photos access
    test_10_blocked_visitor_photos(visitor_token, event_id)
    
    # Test 11: Unblock visitor
    test_11_unblock_visitor(admin_token, event_id, visitor_id)
    
    # Test 12: Unblocked visitor access
    test_12_unblocked_access(event_id, "+91 90000 00001")
    
    # Test 13: Disable sharing
    test_13_disable_sharing(admin_token, event_id)
    
    # Test 14: Disabled public endpoints
    test_14_disabled_public_endpoints(event_id)
    
    # Test 15: Re-enable sharing
    test_15_enable_sharing(admin_token, event_id)
    
    # Test 16: Auth checks
    # Get a fresh visitor token for auth checks
    fresh_visitor_token, _ = test_4_public_access(event_id, "Auth Test Guest", "+91 90000 00004")
    if fresh_visitor_token:
        test_16_auth_checks(event_id, fresh_visitor_token)
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"✅ Passed: {tests_passed}")
    print(f"❌ Failed: {tests_failed}")
    print(f"📊 Total: {tests_passed + tests_failed}")
    print("=" * 80)
    
    print("\nDETAILED RESULTS:")
    for result in test_results:
        print(result)
    
    print("\n" + "=" * 80)
    print(f"EVENT_ID used: {event_id}")
    print("=" * 80)
    
    if tests_failed > 0:
        sys.exit(1)
    else:
        print("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)

if __name__ == "__main__":
    main()
