#!/usr/bin/env python3
"""
Backend test for Super Admin authentication bug fix verification.
Tests the reported bug: Super Admin password SuperAdmin@3214 was not working.
"""

import requests
import sys

# Backend URL from frontend/.env
BACKEND_URL = "https://a70c8c7c-7909-439b-b400-7e934db51d33.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
SUPERADMIN_EMAIL = "prabhakar@pkphotography.in"
SUPERADMIN_PASSWORD = "SuperAdmin@3214"
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

def test_superadmin_login_correct_password():
    """Test 1: POST /api/superadmin/login with correct credentials"""
    print("\n" + "="*80)
    print("TEST 1: Super Admin login with CORRECT password")
    print("="*80)
    
    url = f"{BACKEND_URL}/superadmin/login"
    payload = {
        "email": SUPERADMIN_EMAIL,
        "password": SUPERADMIN_PASSWORD
    }
    
    print(f"POST {url}")
    print(f"Payload: {{'email': '{SUPERADMIN_EMAIL}', 'password': '***'}}")
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ PASS: Login successful")
            print(f"Response keys: {list(data.keys())}")
            
            # Verify session_token exists
            if "session_token" in data:
                print(f"✅ session_token present")
                token = data["session_token"]
            else:
                print(f"❌ FAIL: session_token missing from response")
                return None
            
            # Verify role=superadmin
            if "user" in data and data["user"].get("role") == "superadmin":
                print(f"✅ role=superadmin verified")
            else:
                print(f"❌ FAIL: role is not 'superadmin' (got: {data.get('user', {}).get('role')})")
                return None
            
            return token
        else:
            print(f"❌ FAIL: Expected 200, got {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return None


def test_superadmin_overview(token):
    """Test 2: GET /api/superadmin/overview with Super Admin token"""
    print("\n" + "="*80)
    print("TEST 2: Super Admin overview with valid token")
    print("="*80)
    
    url = f"{BACKEND_URL}/superadmin/overview"
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"GET {url}")
    print(f"Authorization: Bearer ***")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ PASS: Overview accessible")
            print(f"Response keys: {list(data.keys())}")
            
            # Check for expected structure
            if "stats" in data:
                print(f"✅ 'stats' present in response")
            if "attention" in data:
                print(f"✅ 'attention' present in response")
            if "recent_activity" in data:
                print(f"✅ 'recent_activity' present in response")
            
            return True
        else:
            print(f"❌ FAIL: Expected 200, got {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def test_superadmin_login_wrong_password():
    """Test 3: POST /api/superadmin/login with WRONG password"""
    print("\n" + "="*80)
    print("TEST 3: Super Admin login with WRONG password")
    print("="*80)
    
    url = f"{BACKEND_URL}/superadmin/login"
    payload = {
        "email": SUPERADMIN_EMAIL,
        "password": "WrongPassword123"
    }
    
    print(f"POST {url}")
    print(f"Payload: {{'email': '{SUPERADMIN_EMAIL}', 'password': 'WrongPassword123'}}")
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 401:
            print(f"✅ PASS: Wrong password correctly rejected with 401")
            return True
        else:
            print(f"❌ FAIL: Expected 401, got {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def test_admin_login_and_superadmin_access():
    """Test 4: Normal admin login works and cannot access Super Admin overview"""
    print("\n" + "="*80)
    print("TEST 4: Normal admin login and Super Admin overview access (should be 403)")
    print("="*80)
    
    # Step 4a: Normal admin login
    print("\nStep 4a: Normal admin login")
    url = f"{BACKEND_URL}/auth/admin/login"
    payload = {
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    }
    
    print(f"POST {url}")
    print(f"Payload: {{'email': '{ADMIN_EMAIL}', 'password': '***'}}")
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ PASS: Normal admin login successful")
            
            if "session_token" in data:
                print(f"✅ session_token present")
                admin_token = data["session_token"]
            else:
                print(f"❌ FAIL: session_token missing from response")
                return False
            
            # Verify role=admin (not superadmin)
            if "user" in data and data["user"].get("role") == "admin":
                print(f"✅ role=admin verified (not superadmin)")
            else:
                print(f"❌ FAIL: role is not 'admin' (got: {data.get('user', {}).get('role')})")
                return False
        else:
            print(f"❌ FAIL: Expected 200, got {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False
    
    # Step 4b: Try to access Super Admin overview with normal admin token
    print("\nStep 4b: Try to access Super Admin overview with normal admin token")
    url = f"{BACKEND_URL}/superadmin/overview"
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    print(f"GET {url}")
    print(f"Authorization: Bearer *** (admin token)")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 403:
            print(f"✅ PASS: Normal admin correctly blocked from Super Admin overview with 403")
            return True
        else:
            print(f"❌ FAIL: Expected 403, got {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def main():
    """Run all Super Admin authentication tests"""
    print("\n" + "="*80)
    print("SUPER ADMIN AUTHENTICATION BUG FIX VERIFICATION")
    print("Testing credentials from /app/memory/test_credentials.md")
    print("="*80)
    
    results = []
    
    # Test 1: Super Admin login with correct password
    superadmin_token = test_superadmin_login_correct_password()
    results.append(("Super Admin login (correct password)", superadmin_token is not None))
    
    # Test 2: Super Admin overview access (only if login succeeded)
    if superadmin_token:
        overview_success = test_superadmin_overview(superadmin_token)
        results.append(("Super Admin overview access", overview_success))
    else:
        results.append(("Super Admin overview access", False))
        print("\n⚠️  Skipping Test 2 (overview) because login failed")
    
    # Test 3: Super Admin login with wrong password
    wrong_password_success = test_superadmin_login_wrong_password()
    results.append(("Super Admin login (wrong password rejected)", wrong_password_success))
    
    # Test 4: Normal admin login and Super Admin access denial
    admin_blocked_success = test_admin_login_and_superadmin_access()
    results.append(("Normal admin blocked from Super Admin", admin_blocked_success))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    total_tests = len(results)
    passed_tests = sum(1 for _, passed in results if passed)
    
    print(f"\nTotal: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 ALL TESTS PASSED - Super Admin authentication bug is FIXED")
        return 0
    else:
        print(f"\n❌ {total_tests - passed_tests} test(s) FAILED - Bug NOT fully fixed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
