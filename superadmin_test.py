#!/usr/bin/env python3
"""
Super Admin Authentication Test Suite
Tests Super Admin login and protected endpoint access after environment fix
"""

import requests
import json

# Configuration - Use public URL from frontend/.env
BASE_URL = "https://qa-testing-hub-13.preview.emergentagent.com/api"

# Super Admin credentials from /app/memory/test_credentials.md
SUPERADMIN_EMAIL = "prabhakar@pkphotography.in"
SUPERADMIN_PASSWORD = "SuperAdmin@3214"
WRONG_PASSWORD = "WrongPassword123"

# Test results tracking
tests_passed = 0
tests_failed = 0
test_results = []

def log_test(test_name, passed, details=""):
    global tests_passed, tests_failed
    if passed:
        tests_passed += 1
        status = "✅ PASS"
    else:
        tests_failed += 1
        status = "❌ FAIL"
    
    result = f"{status}: {test_name}"
    if details:
        result += f"\n   {details}"
    test_results.append(result)
    print(result)

def test_superadmin_login_correct():
    """Test 1: Super Admin login with correct credentials"""
    try:
        resp = requests.post(
            f"{BASE_URL}/superadmin/login",
            json={"email": SUPERADMIN_EMAIL, "password": SUPERADMIN_PASSWORD},
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("session_token")
            user = data.get("user", {})
            role = user.get("role")
            
            if token and role == "superadmin":
                log_test("Super Admin login (correct password)", True, 
                        f"Status: 200, Role: {role}, Token received (length: {len(token)})")
                return token
            else:
                log_test("Super Admin login (correct password)", False, 
                        f"Missing token or incorrect role. Token: {bool(token)}, Role: {role}")
                return None
        else:
            log_test("Super Admin login (correct password)", False, 
                    f"Status: {resp.status_code}, Body: {resp.text[:200]}")
            return None
    except Exception as e:
        log_test("Super Admin login (correct password)", False, f"Error: {str(e)}")
        return None

def test_superadmin_overview(token):
    """Test 2: Access protected Super Admin overview endpoint"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(
            f"{BASE_URL}/superadmin/overview",
            headers=headers,
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            # Check for expected structure
            has_stats = "stats" in data
            has_attention = "attention" in data
            has_activity = "recent_activity" in data
            
            if has_stats and has_attention and has_activity:
                log_test("Super Admin overview access", True, 
                        f"Status: 200, Response contains stats, attention, and recent_activity")
                return True
            else:
                log_test("Super Admin overview access", False, 
                        f"Missing expected fields. Stats: {has_stats}, Attention: {has_attention}, Activity: {has_activity}")
                return False
        else:
            log_test("Super Admin overview access", False, 
                    f"Status: {resp.status_code}, Body: {resp.text[:200]}")
            return False
    except Exception as e:
        log_test("Super Admin overview access", False, f"Error: {str(e)}")
        return False

def test_superadmin_login_wrong_password():
    """Test 3: Super Admin login with wrong password (should return 401)"""
    try:
        resp = requests.post(
            f"{BASE_URL}/superadmin/login",
            json={"email": SUPERADMIN_EMAIL, "password": WRONG_PASSWORD},
            timeout=10
        )
        
        if resp.status_code == 401:
            log_test("Super Admin login (wrong password)", True, 
                    f"Status: 401 (correctly rejected)")
            return True
        else:
            log_test("Super Admin login (wrong password)", False, 
                    f"Expected 401, got {resp.status_code}. Body: {resp.text[:200]}")
            return False
    except Exception as e:
        log_test("Super Admin login (wrong password)", False, f"Error: {str(e)}")
        return False

def test_backend_running():
    """Test 0: Verify backend is running"""
    try:
        resp = requests.get(f"{BASE_URL}/", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            log_test("Backend health check", True, f"Status: {data.get('status', 'unknown')}")
            return True
        else:
            log_test("Backend health check", False, f"Status code: {resp.status_code}")
            return False
    except Exception as e:
        log_test("Backend health check", False, f"Error: {str(e)}")
        return False

def main():
    print("=" * 80)
    print("SUPER ADMIN AUTHENTICATION TEST SUITE")
    print("Verifying Super Admin login after environment fix")
    print("=" * 80)
    print()
    
    # Test 0: Backend health
    print("Step 1: Checking if backend is running...")
    if not test_backend_running():
        print("\n❌ Backend is not running. Aborting tests.")
        return
    print()
    
    # Test 1: Super Admin login with correct credentials
    print("Step 2: Testing Super Admin login with correct credentials...")
    token = test_superadmin_login_correct()
    if not token:
        print("\n❌ Super Admin login failed. Continuing with remaining tests...")
    print()
    
    # Test 2: Access protected endpoint
    if token:
        print("Step 3: Testing protected Super Admin overview endpoint...")
        test_superadmin_overview(token)
        print()
    else:
        print("Step 3: Skipping protected endpoint test (no token available)")
        print()
    
    # Test 3: Wrong password should return 401
    print("Step 4: Testing Super Admin login with wrong password...")
    test_superadmin_login_wrong_password()
    print()
    
    # Summary
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total tests: {tests_passed + tests_failed}")
    print(f"Passed: {tests_passed}")
    print(f"Failed: {tests_failed}")
    print()
    
    if tests_failed > 0:
        print("❌ SOME TESTS FAILED")
        print("\nFailed tests:")
        for result in test_results:
            if "❌ FAIL" in result:
                print(result)
    else:
        print("✅ ALL TESTS PASSED")
    
    print("=" * 80)

if __name__ == "__main__":
    main()
