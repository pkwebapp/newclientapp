#!/usr/bin/env python3
"""
Backend smoke test for PIK Connect (Lumiere Gallery) after GitHub sync.
Tests basic backend health, admin login, and MongoDB/session wiring.
Configuration: STORAGE_BACKEND=emergent, FACE_ENGINE=mock, OTP_DEV_MODE=true
"""

import requests
import sys
import json

# Backend URL from frontend/.env
BACKEND_URL = "https://da5fd25d-c0c1-451c-8dbc-2f4a3c4ddbaf.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

def test_health_check():
    """Test 1: GET /api/ should return 200"""
    print("\n[TEST 1] GET /api/ (health check)")
    try:
        response = requests.get(f"{BACKEND_URL}/", timeout=10)
        print(f"  Status: {response.status_code}")
        print(f"  Response: {response.json()}")
        
        if response.status_code == 200:
            print("  ✅ PASS - Health check successful")
            return True, response.json()
        else:
            print(f"  ❌ FAIL - Expected 200, got {response.status_code}")
            return False, None
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False, None

def test_admin_login():
    """Test 2: POST /api/auth/admin/login with credentials"""
    print(f"\n[TEST 2] POST /api/auth/admin/login")
    print(f"  Credentials: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Response keys: {list(data.keys())}")
            
            if "session_token" in data:
                print(f"  Session token: {data['session_token'][:20]}... (length: {len(data['session_token'])})")
                print(f"  User: {data.get('user', {})}")
                print("  ✅ PASS - Admin login successful")
                return True, data["session_token"]
            else:
                print(f"  ❌ FAIL - No session_token in response: {data}")
                return False, None
        else:
            print(f"  Response: {response.text}")
            print(f"  ❌ FAIL - Expected 200, got {response.status_code}")
            return False, None
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False, None

def test_events_list(token):
    """Test 3: GET /api/events with admin token (optional MongoDB/session check)"""
    print(f"\n[TEST 3] GET /api/events (with admin token)")
    
    try:
        response = requests.get(
            f"{BACKEND_URL}/events",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  Response type: {type(data)}")
            if isinstance(data, list):
                print(f"  Events count: {len(data)}")
                if len(data) > 0:
                    print(f"  First event: {data[0].get('name', 'N/A')} (id: {data[0].get('event_id', 'N/A')})")
            print("  ✅ PASS - Events list retrieved successfully")
            return True
        else:
            print(f"  Response: {response.text}")
            print(f"  ❌ FAIL - Expected 200, got {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ FAIL - Exception: {e}")
        return False

def main():
    print("=" * 80)
    print("BACKEND SMOKE TEST - PIK Connect (Lumiere Gallery)")
    print("Configuration: STORAGE_BACKEND=emergent, FACE_ENGINE=mock, OTP_DEV_MODE=true")
    print("=" * 80)
    
    results = []
    
    # Test 1: Health check
    success, health_data = test_health_check()
    results.append(("Health Check", success))
    
    if not success:
        print("\n❌ Health check failed - backend may not be running")
        print("\nSUMMARY: 1/3 tests run, 0 passed")
        sys.exit(1)
    
    # Test 2: Admin login
    success, token = test_admin_login()
    results.append(("Admin Login", success))
    
    if not success:
        print("\n❌ Admin login failed - cannot proceed with token-based tests")
        print("\nSUMMARY: 2/3 tests run, 1 passed")
        sys.exit(1)
    
    # Test 3: Events list (optional MongoDB/session check)
    success = test_events_list(token)
    results.append(("Events List", success))
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - Backend is stable and ready")
        sys.exit(0)
    else:
        print(f"\n❌ {total - passed} test(s) failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
