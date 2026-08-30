#!/usr/bin/env python3
"""
Comprehensive Supabase Auth Integration Test Suite
Tests the newly wired Supabase Auth on PIK Connect backend.
"""
import os
import sys
import time
import json
import requests
from datetime import datetime

# Configuration
BACKEND_URL = "https://44463a86-6b40-4901-9582-b0d2a229f044.preview.emergentagent.com/api"
SUPABASE_URL = "https://idnrpxtapkkryhlordlt.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_K2VFAYgV_LsrT74yAm-LBw_4dZdljnP"
SUPABASE_SECRET_KEY = os.environ["SUPABASE_KEY"]

# Super Admin credentials (legacy)
SUPER_ADMIN_EMAIL = "prabhakar@pkphotography.in"
SUPER_ADMIN_PASSWORD = "Super@12345"

# Test results tracking
test_results = []
suite_results = {}


def log_test(suite, test_name, method, url, status, expected_status, passed, response_snippet="", notes=""):
    """Log a test result."""
    result = {
        "suite": suite,
        "test": test_name,
        "method": method,
        "url": url,
        "status": status,
        "expected": expected_status,
        "passed": passed,
        "response": response_snippet,
        "notes": notes
    }
    test_results.append(result)
    
    if suite not in suite_results:
        suite_results[suite] = {"passed": 0, "failed": 0, "tests": []}
    
    if passed:
        suite_results[suite]["passed"] += 1
    else:
        suite_results[suite]["failed"] += 1
    
    suite_results[suite]["tests"].append(result)
    
    status_icon = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status_icon} | {suite} | {test_name}")
    print(f"   {method} {url}")
    print(f"   Status: {status} (expected {expected_status})")
    if response_snippet:
        print(f"   Response: {response_snippet[:200]}")
    if notes:
        print(f"   Notes: {notes}")
    print()


def create_supabase_user(email, password, role, name):
    """Create a Supabase user via Admin API with email confirmation."""
    url = f"{SUPABASE_URL}/auth/v1/admin/users"
    headers = {
        "apikey": SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "email": email,
        "password": password,
        "email_confirm": True,
        "user_metadata": {
            "role": role,
            "name": name
        }
    }
    
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=15)
        if resp.status_code in [200, 201]:
            print(f"✅ Created Supabase user: {email} (role={role})")
            return True
        elif resp.status_code == 422 and "already been registered" in resp.text:
            print(f"ℹ️  Supabase user already exists: {email}")
            return True
        else:
            print(f"⚠️  Failed to create Supabase user {email}: {resp.status_code} {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"⚠️  Exception creating Supabase user {email}: {e}")
        return False


def sign_in_supabase(email, password):
    """Sign in to Supabase and get JWT access token."""
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": SUPABASE_PUBLISHABLE_KEY,
        "Content-Type": "application/json"
    }
    body = {
        "email": email,
        "password": password
    }
    
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            access_token = data.get("access_token")
            print(f"✅ Signed in to Supabase: {email}")
            return access_token
        else:
            print(f"❌ Failed to sign in {email}: {resp.status_code} {resp.text[:200]}")
            return None
    except Exception as e:
        print(f"❌ Exception signing in {email}: {e}")
        return None


def test_suite_1_jwt_verification():
    """Suite 1 — Supabase JWT verification (HAPPY PATH)"""
    print("\n" + "="*80)
    print("SUITE 1 — Supabase JWT verification (HAPPY PATH)")
    print("="*80 + "\n")
    
    ts = int(time.time())
    admin_email = f"pikconnect.qa+admin_{ts}@gmail.com"
    client_email = f"pikconnect.qa+client_{ts}@gmail.com"
    password = "Test@1234pass"
    
    # Create admin user
    if not create_supabase_user(admin_email, password, "admin", "QA Admin"):
        print("❌ Failed to create admin user, skipping suite 1")
        return
    
    # Create client user
    if not create_supabase_user(client_email, password, "client", "QA Client"):
        print("❌ Failed to create client user, skipping suite 1")
        return
    
    time.sleep(2)  # Give Supabase a moment
    
    # Sign in admin
    admin_jwt = sign_in_supabase(admin_email, password)
    if not admin_jwt:
        print("❌ Failed to get admin JWT, skipping suite 1")
        return
    
    # Sign in client
    client_jwt = sign_in_supabase(client_email, password)
    if not client_jwt:
        print("❌ Failed to get client JWT, skipping suite 1")
        return
    
    # Test 1.1: Admin JWT → /auth/me (first time, auto-provision)
    url = f"{BACKEND_URL}/auth/me"
    headers = {"Authorization": f"Bearer {admin_jwt}"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        user = data.get("user", {})
        
        notes = ""
        if passed:
            if user.get("role") != "admin":
                passed = False
                notes = f"Expected role=admin, got {user.get('role')}"
            elif not user.get("user_id"):
                passed = False
                notes = "Missing auto-provisioned user_id"
            elif user.get("plan") != "trial":
                passed = False
                notes = f"Expected plan=trial, got {user.get('plan')}"
            elif not user.get("plan_expires_at"):
                passed = False
                notes = "Missing plan_expires_at"
            elif user.get("profile_complete") != False:
                passed = False
                notes = f"Expected profile_complete=false, got {user.get('profile_complete')}"
            else:
                notes = f"Admin auto-provisioned: user_id={user.get('user_id')}, role=admin, plan=trial"
        
        log_test("Suite 1", "1.1 Admin JWT → /auth/me (first time)", "GET", url, 
                resp.status_code, 200, passed, json.dumps(user)[:200], notes)
        
        admin_user_id = user.get("user_id")
    except Exception as e:
        log_test("Suite 1", "1.1 Admin JWT → /auth/me (first time)", "GET", url, 
                "ERROR", 200, False, str(e))
        return
    
    # Test 1.2: Same admin JWT → /auth/me (second time, no duplicate)
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        user = data.get("user", {})
        
        notes = ""
        if passed:
            if user.get("user_id") != admin_user_id:
                passed = False
                notes = f"User ID changed! First: {admin_user_id}, Second: {user.get('user_id')}"
            else:
                notes = f"Same user_id returned: {admin_user_id} (no duplicate insert)"
        
        log_test("Suite 1", "1.2 Same admin JWT → /auth/me (second time)", "GET", url,
                resp.status_code, 200, passed, json.dumps(user)[:200], notes)
    except Exception as e:
        log_test("Suite 1", "1.2 Same admin JWT → /auth/me (second time)", "GET", url,
                "ERROR", 200, False, str(e))
    
    # Test 1.3: Client JWT → /auth/me (first time)
    headers = {"Authorization": f"Bearer {client_jwt}"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        user = data.get("user", {})
        
        notes = ""
        if passed:
            if user.get("role") != "client":
                passed = False
                notes = f"Expected role=client, got {user.get('role')}"
            elif not user.get("user_id"):
                passed = False
                notes = "Missing auto-provisioned user_id"
            elif user.get("plan") is not None:
                passed = False
                notes = f"Client should have plan=None, got {user.get('plan')}"
            else:
                notes = f"Client auto-provisioned: user_id={user.get('user_id')}, role=client, plan=None (no plan)"
        
        log_test("Suite 1", "1.3 Client JWT → /auth/me (first time)", "GET", url,
                resp.status_code, 200, passed, json.dumps(user)[:200], notes)
    except Exception as e:
        log_test("Suite 1", "1.3 Client JWT → /auth/me (first time)", "GET", url,
                "ERROR", 200, False, str(e))
    
    # Test 1.4: Admin JWT → /events (should work)
    url = f"{BACKEND_URL}/events"
    headers = {"Authorization": f"Bearer {admin_jwt}"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        passed = resp.status_code == 200
        data = resp.json() if passed else []
        
        notes = f"Returned {len(data)} events (empty array expected for new admin)"
        
        log_test("Suite 1", "1.4 Admin JWT → /events", "GET", url,
                resp.status_code, 200, passed, json.dumps(data)[:200], notes)
    except Exception as e:
        log_test("Suite 1", "1.4 Admin JWT → /events", "GET", url,
                "ERROR", 200, False, str(e))


def test_suite_2_deprecated_routes():
    """Suite 2 — Deprecated routes return 410 Gone"""
    print("\n" + "="*80)
    print("SUITE 2 — Deprecated routes return 410 Gone")
    print("="*80 + "\n")
    
    deprecated_routes = [
        ("POST", "/auth/admin/register", {"name": "Test", "email": "test@test.com", "password": "Test@1234"}),
        ("POST", "/auth/admin/login", {"email": "test@test.com", "password": "Test@1234"}),
        ("POST", "/auth/admin/forgot-password", {"email": "test@test.com"}),
        ("POST", "/auth/admin/reset-password", {"email": "test@test.com", "code": "123456", "new_password": "New@1234"}),
        ("POST", "/auth/session", {"session_id": "test_session"}),
        ("POST", "/auth/client/request-otp", {"channel": "email", "email": "test@test.com"}),
        ("POST", "/auth/client/verify-otp", {"channel": "email", "email": "test@test.com", "code": "123456"}),
    ]
    
    for i, (method, path, body) in enumerate(deprecated_routes, 1):
        url = f"{BACKEND_URL}{path}"
        try:
            resp = requests.post(url, json=body, timeout=15)
            passed = resp.status_code == 410
            data = resp.json() if resp.status_code in [410, 400, 422] else {}
            detail = data.get("detail", "")
            
            notes = ""
            if passed:
                if "Deprecated" not in detail:
                    notes = f"Missing 'Deprecated' in detail message: {detail}"
                else:
                    notes = f"Correct 410 with detail: {detail}"
            else:
                notes = f"Expected 410, got {resp.status_code}"
            
            log_test("Suite 2", f"2.{i} {method} {path}", method, url,
                    resp.status_code, 410, passed, json.dumps(data)[:200], notes)
        except Exception as e:
            log_test("Suite 2", f"2.{i} {method} {path}", method, url,
                    "ERROR", 410, False, str(e))


def test_suite_3_super_admin_legacy():
    """Suite 3 — Super Admin legacy flow (unchanged)"""
    print("\n" + "="*80)
    print("SUITE 3 — Super Admin legacy flow (unchanged)")
    print("="*80 + "\n")
    
    # Test 3.1: Super Admin login
    url = f"{BACKEND_URL}/superadmin/login"
    body = {"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
    try:
        resp = requests.post(url, json=body, timeout=15)
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        session_token = data.get("session_token")
        
        notes = ""
        if passed:
            if not session_token:
                passed = False
                notes = "Missing session_token in response"
            elif not session_token.startswith("st_"):
                passed = False
                notes = f"Invalid session_token format: {session_token[:20]}"
            else:
                notes = f"Legacy session token received: {session_token[:20]}..."
        
        log_test("Suite 3", "3.1 Super Admin login", "POST", url,
                resp.status_code, 200, passed, json.dumps(data)[:200], notes)
        
        if not passed or not session_token:
            print("❌ Super Admin login failed, skipping rest of suite 3")
            return
    except Exception as e:
        log_test("Suite 3", "3.1 Super Admin login", "POST", url,
                "ERROR", 200, False, str(e))
        return
    
    # Test 3.2: /auth/me with legacy token
    url = f"{BACKEND_URL}/auth/me"
    headers = {"Authorization": f"Bearer {session_token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        user = data.get("user", {})
        
        notes = ""
        if passed:
            if user.get("role") != "superadmin":
                passed = False
                notes = f"Expected role=superadmin, got {user.get('role')}"
            else:
                notes = f"Super admin authenticated: role=superadmin"
        
        log_test("Suite 3", "3.2 /auth/me with legacy token", "GET", url,
                resp.status_code, 200, passed, json.dumps(user)[:200], notes)
    except Exception as e:
        log_test("Suite 3", "3.2 /auth/me with legacy token", "GET", url,
                "ERROR", 200, False, str(e))
    
    # Test 3.3: /superadmin/overview with legacy token
    url = f"{BACKEND_URL}/superadmin/overview"
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        stats = data.get("stats", {})
        
        notes = f"Stats returned: {list(stats.keys())[:5]}"
        
        log_test("Suite 3", "3.3 /superadmin/overview with legacy token", "GET", url,
                resp.status_code, 200, passed, json.dumps(stats)[:200], notes)
    except Exception as e:
        log_test("Suite 3", "3.3 /superadmin/overview with legacy token", "GET", url,
                "ERROR", 200, False, str(e))


def test_suite_4_rbac_enforcement():
    """Suite 4 — RBAC enforcement"""
    print("\n" + "="*80)
    print("SUITE 4 — RBAC enforcement")
    print("="*80 + "\n")
    
    # Create test users
    ts = int(time.time())
    admin_email = f"pikconnect.qa+rbac_admin_{ts}@gmail.com"
    client_email = f"pikconnect.qa+rbac_client_{ts}@gmail.com"
    password = "Test@1234pass"
    
    create_supabase_user(admin_email, password, "admin", "RBAC Admin")
    create_supabase_user(client_email, password, "client", "RBAC Client")
    time.sleep(2)
    
    admin_jwt = sign_in_supabase(admin_email, password)
    client_jwt = sign_in_supabase(client_email, password)
    
    if not admin_jwt or not client_jwt:
        print("❌ Failed to get JWTs for RBAC tests, skipping suite 4")
        return
    
    # Get super admin token
    url = f"{BACKEND_URL}/superadmin/login"
    body = {"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD}
    try:
        resp = requests.post(url, json=body, timeout=15)
        super_token = resp.json().get("session_token") if resp.status_code == 200 else None
    except:
        super_token = None
    
    # Test 4.1: Client JWT → /events (should be 403)
    url = f"{BACKEND_URL}/events"
    headers = {"Authorization": f"Bearer {client_jwt}"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        passed = resp.status_code == 403
        data = resp.json() if resp.status_code in [403, 401] else {}
        detail = data.get("detail", "")
        
        notes = ""
        if passed:
            if "Admin access required" not in detail:
                notes = f"Expected 'Admin access required', got: {detail}"
            else:
                notes = f"Correct 403: {detail}"
        else:
            notes = f"Expected 403, got {resp.status_code}"
        
        log_test("Suite 4", "4.1 Client JWT → /events (expect 403)", "GET", url,
                resp.status_code, 403, passed, json.dumps(data)[:200], notes)
    except Exception as e:
        log_test("Suite 4", "4.1 Client JWT → /events (expect 403)", "GET", url,
                "ERROR", 403, False, str(e))
    
    # Test 4.2: Admin JWT → /superadmin/overview (should be 403)
    url = f"{BACKEND_URL}/superadmin/overview"
    headers = {"Authorization": f"Bearer {admin_jwt}"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        passed = resp.status_code == 403
        data = resp.json() if resp.status_code in [403, 401] else {}
        detail = data.get("detail", "")
        
        notes = ""
        if passed:
            if "Super admin access required" not in detail:
                notes = f"Expected 'Super admin access required', got: {detail}"
            else:
                notes = f"Correct 403: {detail}"
        else:
            notes = f"Expected 403, got {resp.status_code}"
        
        log_test("Suite 4", "4.2 Admin JWT → /superadmin/overview (expect 403)", "GET", url,
                resp.status_code, 403, passed, json.dumps(data)[:200], notes)
    except Exception as e:
        log_test("Suite 4", "4.2 Admin JWT → /superadmin/overview (expect 403)", "GET", url,
                "ERROR", 403, False, str(e))
    
    # Test 4.3: Super admin legacy token → /events (should be 403)
    if super_token:
        url = f"{BACKEND_URL}/events"
        headers = {"Authorization": f"Bearer {super_token}"}
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            passed = resp.status_code == 403
            data = resp.json() if resp.status_code in [403, 401] else {}
            detail = data.get("detail", "")
            
            notes = ""
            if passed:
                notes = f"Correct 403: super admin is not admin - {detail}"
            else:
                notes = f"Expected 403, got {resp.status_code}"
            
            log_test("Suite 4", "4.3 Super admin token → /events (expect 403)", "GET", url,
                    resp.status_code, 403, passed, json.dumps(data)[:200], notes)
        except Exception as e:
            log_test("Suite 4", "4.3 Super admin token → /events (expect 403)", "GET", url,
                    "ERROR", 403, False, str(e))


def test_suite_5_studio_onboarding():
    """Suite 5 — Studio onboarding after Supabase login"""
    print("\n" + "="*80)
    print("SUITE 5 — Studio onboarding after Supabase login")
    print("="*80 + "\n")
    
    # Create admin user
    ts = int(time.time())
    admin_email = f"pikconnect.qa+onboard_{ts}@gmail.com"
    password = "Test@1234pass"
    
    if not create_supabase_user(admin_email, password, "admin", "Onboarding Admin"):
        print("❌ Failed to create admin user, skipping suite 5")
        return
    
    time.sleep(2)
    admin_jwt = sign_in_supabase(admin_email, password)
    
    if not admin_jwt:
        print("❌ Failed to get admin JWT, skipping suite 5")
        return
    
    # Test 5.1: POST /auth/admin/profile
    url = f"{BACKEND_URL}/auth/admin/profile"
    headers = {"Authorization": f"Bearer {admin_jwt}"}
    body = {
        "contact_name": "QA Owner",
        "studio_name": "QA Studio Bengaluru",
        "phone": "+919845012345",
        "purposes": ["wedding"],
        "city": "Bengaluru",
        "country": "India"
    }
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=15)
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        user = data.get("user", {})
        studio_profile = user.get("studio_profile", {})
        
        notes = ""
        if passed:
            if user.get("profile_complete") != True:
                passed = False
                notes = f"Expected profile_complete=true, got {user.get('profile_complete')}"
            elif studio_profile.get("studio_name") != "QA Studio Bengaluru":
                passed = False
                notes = f"Studio name mismatch: {studio_profile.get('studio_name')}"
            elif studio_profile.get("phone") != "+919845012345":
                passed = False
                notes = f"Phone mismatch: {studio_profile.get('phone')}"
            else:
                notes = f"Profile completed: studio_name={studio_profile.get('studio_name')}, profile_complete=true"
        
        log_test("Suite 5", "5.1 POST /auth/admin/profile", "POST", url,
                resp.status_code, 200, passed, json.dumps(user)[:200], notes)
    except Exception as e:
        log_test("Suite 5", "5.1 POST /auth/admin/profile", "POST", url,
                "ERROR", 200, False, str(e))
        return
    
    # Test 5.2: GET /auth/me again (verify profile_complete=true)
    url = f"{BACKEND_URL}/auth/me"
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        passed = resp.status_code == 200
        data = resp.json() if passed else {}
        user = data.get("user", {})
        
        notes = ""
        if passed:
            if user.get("profile_complete") != True:
                passed = False
                notes = f"Expected profile_complete=true, got {user.get('profile_complete')}"
            else:
                notes = f"Profile complete confirmed: profile_complete=true"
        
        log_test("Suite 5", "5.2 GET /auth/me (verify profile_complete)", "GET", url,
                resp.status_code, 200, passed, json.dumps(user)[:200], notes)
    except Exception as e:
        log_test("Suite 5", "5.2 GET /auth/me (verify profile_complete)", "GET", url,
                "ERROR", 200, False, str(e))


def test_suite_6_negative_cases():
    """Suite 6 — Negative / auth failure cases (must return 401, NEVER 500)"""
    print("\n" + "="*80)
    print("SUITE 6 — Negative / auth failure cases (must return 401, NEVER 500)")
    print("="*80 + "\n")
    
    url = f"{BACKEND_URL}/auth/me"
    
    # Test 6.1: No Authorization header
    try:
        resp = requests.get(url, timeout=15)
        passed = resp.status_code == 401
        data = resp.json() if resp.status_code in [401, 403] else {}
        
        notes = f"No auth header → {resp.status_code}"
        
        log_test("Suite 6", "6.1 No Authorization header", "GET", url,
                resp.status_code, 401, passed, json.dumps(data)[:200], notes)
    except Exception as e:
        log_test("Suite 6", "6.1 No Authorization header", "GET", url,
                "ERROR", 401, False, str(e))
    
    # Test 6.2: Malformed bearer token
    headers = {"Authorization": "Bearer garbage_not_jwt"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        passed = resp.status_code == 401
        data = resp.json() if resp.status_code in [401, 403] else {}
        
        notes = f"Malformed token → {resp.status_code}"
        
        log_test("Suite 6", "6.2 Malformed bearer token", "GET", url,
                resp.status_code, 401, passed, json.dumps(data)[:200], notes)
    except Exception as e:
        log_test("Suite 6", "6.2 Malformed bearer token", "GET", url,
                "ERROR", 401, False, str(e))
    
    # Test 6.3: JWT-shaped but invalid signature
    # Create a fake JWT by taking a real one and flipping a byte in the signature
    ts = int(time.time())
    temp_email = f"pikconnect.qa+temp_{ts}@gmail.com"
    create_supabase_user(temp_email, "Test@1234pass", "client", "Temp")
    time.sleep(2)
    valid_jwt = sign_in_supabase(temp_email, "Test@1234pass")
    
    if valid_jwt:
        parts = valid_jwt.split(".")
        if len(parts) == 3:
            # Flip last character of signature
            sig = parts[2]
            if sig:
                flipped_sig = sig[:-1] + ("A" if sig[-1] != "A" else "B")
                invalid_jwt = f"{parts[0]}.{parts[1]}.{flipped_sig}"
                
                headers = {"Authorization": f"Bearer {invalid_jwt}"}
                try:
                    resp = requests.get(url, headers=headers, timeout=15)
                    passed = resp.status_code == 401
                    data = resp.json() if resp.status_code in [401, 403] else {}
                    
                    notes = f"Invalid signature → {resp.status_code}"
                    
                    log_test("Suite 6", "6.3 JWT with invalid signature", "GET", url,
                            resp.status_code, 401, passed, json.dumps(data)[:200], notes)
                except Exception as e:
                    log_test("Suite 6", "6.3 JWT with invalid signature", "GET", url,
                            "ERROR", 401, False, str(e))
    
    # Test 6.4: Empty bearer
    headers = {"Authorization": "Bearer "}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        passed = resp.status_code == 401
        data = resp.json() if resp.status_code in [401, 403] else {}
        
        notes = f"Empty bearer → {resp.status_code}"
        
        log_test("Suite 6", "6.4 Empty bearer", "GET", url,
                resp.status_code, 401, passed, json.dumps(data)[:200], notes)
    except Exception as e:
        log_test("Suite 6", "6.4 Empty bearer", "GET", url,
                "ERROR", 401, False, str(e))
    
    # Test 6.5: Random opaque token (not in DB)
    headers = {"Authorization": "Bearer st_deadbeef12345678"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        passed = resp.status_code == 401
        data = resp.json() if resp.status_code in [401, 403] else {}
        
        notes = f"Random opaque token → {resp.status_code}"
        
        log_test("Suite 6", "6.5 Random opaque token", "GET", url,
                resp.status_code, 401, passed, json.dumps(data)[:200], notes)
    except Exception as e:
        log_test("Suite 6", "6.5 Random opaque token", "GET", url,
                "ERROR", 401, False, str(e))


def print_summary():
    """Print final summary report."""
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80 + "\n")
    
    total_passed = 0
    total_failed = 0
    
    for suite_name in sorted(suite_results.keys()):
        suite = suite_results[suite_name]
        total_passed += suite["passed"]
        total_failed += suite["failed"]
        
        status = "✅ ALL PASSED" if suite["failed"] == 0 else f"❌ {suite['failed']} FAILED"
        print(f"{suite_name}: {suite['passed']}/{suite['passed'] + suite['failed']} tests passed {status}")
    
    print(f"\nOVERALL: {total_passed}/{total_passed + total_failed} tests passed")
    
    if total_failed > 0:
        print("\n" + "="*80)
        print("FAILED TESTS DETAIL")
        print("="*80 + "\n")
        
        for suite_name in sorted(suite_results.keys()):
            suite = suite_results[suite_name]
            failed_tests = [t for t in suite["tests"] if not t["passed"]]
            
            if failed_tests:
                print(f"\n{suite_name}:")
                for test in failed_tests:
                    print(f"  ❌ {test['test']}")
                    print(f"     {test['method']} {test['url']}")
                    print(f"     Status: {test['status']} (expected {test['expected']})")
                    if test['response']:
                        print(f"     Response: {test['response'][:200]}")
                    if test['notes']:
                        print(f"     Notes: {test['notes']}")
    
    return total_failed == 0


def main():
    """Run all test suites."""
    print("\n" + "="*80)
    print("PIK CONNECT - SUPABASE AUTH INTEGRATION TEST SUITE")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Supabase URL: {SUPABASE_URL}")
    print(f"Started: {datetime.now().isoformat()}")
    print("="*80 + "\n")
    
    try:
        test_suite_1_jwt_verification()
        test_suite_2_deprecated_routes()
        test_suite_3_super_admin_legacy()
        test_suite_4_rbac_enforcement()
        test_suite_5_studio_onboarding()
        test_suite_6_negative_cases()
        
        success = print_summary()
        
        print(f"\nCompleted: {datetime.now().isoformat()}")
        
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n\n⚠️  Test suite interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n❌ Test suite failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
