#!/usr/bin/env python3
"""
Super Admin V1 Backend Test for PIK Connect / Lumiere Gallery
Tests Super Admin authentication, platform overview, photographer controls, and all superadmin endpoints.
"""

import requests
import json
import sys
from io import BytesIO
from PIL import Image

# Backend URL
BASE_URL = "https://client-hub-434.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
SUPERADMIN_EMAIL = "prabhakar@pkphotography.in"
SUPERADMIN_PASSWORD = "SuperAdmin@3214"
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

def log(msg):
    print(f"[TEST] {msg}")

def create_test_image():
    """Create a small test JPEG image"""
    img = Image.new('RGB', (100, 100), color='blue')
    buf = BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return buf

def main():
    log("=== SUPER ADMIN V1 BACKEND TEST ===")
    
    # Track resources for cleanup
    superadmin_token = None
    admin_token = None
    throwaway_photographer_id = None
    throwaway_event_id = None
    
    test_results = []
    
    try:
        # ===== TEST 1: Super Admin Login =====
        log("\n--- TEST 1: Super Admin Login ---")
        resp = requests.post(f"{BASE_URL}/superadmin/login", json={
            "email": SUPERADMIN_EMAIL,
            "password": SUPERADMIN_PASSWORD
        })
        if resp.status_code == 200:
            data = resp.json()
            if "session_token" in data and data.get("user", {}).get("role") == "superadmin":
                superadmin_token = data["session_token"]
                test_results.append("✅ TEST 1: Super Admin login successful with role=superadmin and session_token")
                log(f"✅ Super Admin logged in: {data['user'].get('email')}")
            else:
                test_results.append(f"❌ TEST 1: Super Admin login response missing required fields: {data}")
                log(f"❌ Response: {data}")
        else:
            test_results.append(f"❌ TEST 1: Super Admin login failed: {resp.status_code} {resp.text}")
            log(f"❌ Login failed: {resp.status_code} {resp.text}")
            return  # Cannot continue without token
        
        # ===== TEST 2: Auth Gating - No Token =====
        log("\n--- TEST 2: Auth Gating - No Token (401) ---")
        resp = requests.get(f"{BASE_URL}/superadmin/overview")
        if resp.status_code == 401:
            test_results.append("✅ TEST 2: GET /api/superadmin/overview without token returns 401")
            log("✅ 401 returned correctly")
        else:
            test_results.append(f"❌ TEST 2: Expected 401, got {resp.status_code}")
            log(f"❌ Expected 401, got {resp.status_code}")
        
        # ===== TEST 3: Auth Gating - Normal Admin Token (403) =====
        log("\n--- TEST 3: Auth Gating - Normal Admin Token (403) ---")
        # First login as normal admin
        resp = requests.post(f"{BASE_URL}/auth/admin/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if resp.status_code == 200:
            admin_token = resp.json()["session_token"]
            log(f"✅ Normal admin logged in: {ADMIN_EMAIL}")
            
            # Try to access superadmin endpoint with admin token
            resp = requests.get(f"{BASE_URL}/superadmin/overview",
                headers={"Authorization": f"Bearer {admin_token}"})
            if resp.status_code == 403:
                test_results.append("✅ TEST 3: GET /api/superadmin/overview with admin token returns 403")
                log("✅ 403 returned correctly")
            else:
                test_results.append(f"❌ TEST 3: Expected 403, got {resp.status_code}")
                log(f"❌ Expected 403, got {resp.status_code}")
        else:
            test_results.append(f"❌ TEST 3: Normal admin login failed: {resp.status_code}")
            log(f"❌ Normal admin login failed: {resp.status_code}")
        
        # ===== TEST 4: GET /api/superadmin/overview =====
        log("\n--- TEST 4: GET /api/superadmin/overview ---")
        resp = requests.get(f"{BASE_URL}/superadmin/overview",
            headers={"Authorization": f"Bearer {superadmin_token}"})
        if resp.status_code == 200:
            data = resp.json()
            # Check for required structure
            required_keys = ["stats", "attention", "recent_activity"]
            stats_keys = ["total_photographers", "active_photographers", "total_galleries", "total_images", "storage_bytes", "uploads_today"]
            attention_keys = ["storage_warnings", "expiring_memberships", "uploads_disabled"]
            
            missing_keys = [k for k in required_keys if k not in data]
            missing_stats = [k for k in stats_keys if k not in data.get("stats", {})]
            missing_attention = [k for k in attention_keys if k not in data.get("attention", {})]
            
            if not missing_keys and not missing_stats and not missing_attention:
                test_results.append("✅ TEST 4: GET /api/superadmin/overview returns correct structure with stats, attention, and recent_activity")
                log(f"✅ Overview stats: {data['stats']}")
                log(f"✅ Attention counts: {data['attention']}")
                log(f"✅ Recent activity entries: {len(data['recent_activity'])}")
            else:
                test_results.append(f"❌ TEST 4: Missing keys - top: {missing_keys}, stats: {missing_stats}, attention: {missing_attention}")
                log(f"❌ Missing keys: {missing_keys}, {missing_stats}, {missing_attention}")
        else:
            test_results.append(f"❌ TEST 4: GET /api/superadmin/overview failed: {resp.status_code} {resp.text}")
            log(f"❌ Failed: {resp.status_code} {resp.text}")
        
        # ===== TEST 5: GET /api/superadmin/photographers (no filters) =====
        log("\n--- TEST 5: GET /api/superadmin/photographers (no filters) ---")
        resp = requests.get(f"{BASE_URL}/superadmin/photographers",
            headers={"Authorization": f"Bearer {superadmin_token}"})
        if resp.status_code == 200:
            photographers = resp.json()
            if isinstance(photographers, list):
                # Check that no password hashes are exposed
                has_password_hash = any("password_hash" in p for p in photographers)
                if has_password_hash:
                    test_results.append("❌ TEST 5: Photographers list exposes password_hash")
                    log("❌ Password hashes exposed!")
                else:
                    test_results.append(f"✅ TEST 5: GET /api/superadmin/photographers returns {len(photographers)} photographers, no password hashes")
                    log(f"✅ Found {len(photographers)} photographers, no password hashes")
                    
                    # Verify expected fields
                    if photographers:
                        sample = photographers[0]
                        expected_fields = ["photographer_id", "name", "email", "membership", "status", "galleries", "images", "storage_bytes"]
                        missing = [f for f in expected_fields if f not in sample]
                        if missing:
                            log(f"⚠️  Missing fields in photographer row: {missing}")
            else:
                test_results.append(f"❌ TEST 5: Expected list, got {type(photographers)}")
                log(f"❌ Expected list, got {type(photographers)}")
        else:
            test_results.append(f"❌ TEST 5: GET /api/superadmin/photographers failed: {resp.status_code} {resp.text}")
            log(f"❌ Failed: {resp.status_code} {resp.text}")
        
        # ===== TEST 6: GET /api/superadmin/photographers with search =====
        log("\n--- TEST 6: GET /api/superadmin/photographers with q search ---")
        resp = requests.get(f"{BASE_URL}/superadmin/photographers?q=admin",
            headers={"Authorization": f"Bearer {superadmin_token}"})
        if resp.status_code == 200:
            photographers = resp.json()
            # Should find admin@lumiere.studio
            found_admin = any(p.get("email") == ADMIN_EMAIL for p in photographers)
            if found_admin:
                test_results.append("✅ TEST 6: Search q=admin finds admin@lumiere.studio")
                log(f"✅ Search found {len(photographers)} photographers including admin@lumiere.studio")
            else:
                test_results.append(f"❌ TEST 6: Search q=admin did not find admin@lumiere.studio")
                log(f"❌ Search did not find admin@lumiere.studio")
        else:
            test_results.append(f"❌ TEST 6: Search failed: {resp.status_code} {resp.text}")
            log(f"❌ Failed: {resp.status_code} {resp.text}")
        
        # ===== TEST 7: GET /api/superadmin/photographers with status filter =====
        log("\n--- TEST 7: GET /api/superadmin/photographers with status filter ---")
        resp = requests.get(f"{BASE_URL}/superadmin/photographers?status=active",
            headers={"Authorization": f"Bearer {superadmin_token}"})
        if resp.status_code == 200:
            photographers = resp.json()
            all_active = all(p.get("status") == "active" for p in photographers)
            if all_active:
                test_results.append(f"✅ TEST 7: Status filter status=active returns only active photographers ({len(photographers)} found)")
                log(f"✅ Found {len(photographers)} active photographers")
            else:
                test_results.append(f"❌ TEST 7: Status filter returned non-active photographers")
                log(f"❌ Filter not working correctly")
        else:
            test_results.append(f"❌ TEST 7: Status filter failed: {resp.status_code} {resp.text}")
            log(f"❌ Failed: {resp.status_code} {resp.text}")
        
        # ===== TEST 8: GET /api/superadmin/memberships =====
        log("\n--- TEST 8: GET /api/superadmin/memberships ---")
        resp = requests.get(f"{BASE_URL}/superadmin/memberships",
            headers={"Authorization": f"Bearer {superadmin_token}"})
        if resp.status_code == 200:
            memberships = resp.json()
            if isinstance(memberships, list) and len(memberships) > 0:
                # Check structure
                sample = memberships[0]
                required = ["key", "name", "price", "storage_limit", "photographers"]
                missing = [f for f in required if f not in sample]
                if not missing:
                    test_results.append(f"✅ TEST 8: GET /api/superadmin/memberships returns {len(memberships)} plans with correct structure")
                    log(f"✅ Found {len(memberships)} membership plans")
                else:
                    test_results.append(f"❌ TEST 8: Missing fields: {missing}")
                    log(f"❌ Missing fields: {missing}")
            else:
                test_results.append(f"❌ TEST 8: Expected non-empty list, got {type(memberships)}")
                log(f"❌ Expected non-empty list")
        else:
            test_results.append(f"❌ TEST 8: GET /api/superadmin/memberships failed: {resp.status_code} {resp.text}")
            log(f"❌ Failed: {resp.status_code} {resp.text}")
        
        # ===== TEST 9: GET /api/superadmin/galleries =====
        log("\n--- TEST 9: GET /api/superadmin/galleries ---")
        resp = requests.get(f"{BASE_URL}/superadmin/galleries",
            headers={"Authorization": f"Bearer {superadmin_token}"})
        if resp.status_code == 200:
            galleries = resp.json()
            if isinstance(galleries, list):
                test_results.append(f"✅ TEST 9: GET /api/superadmin/galleries returns {len(galleries)} galleries")
                log(f"✅ Found {len(galleries)} galleries")
                if galleries:
                    sample = galleries[0]
                    expected = ["event_id", "name", "photographer", "images", "created_at", "status"]
                    missing = [f for f in expected if f not in sample]
                    if missing:
                        log(f"⚠️  Missing fields: {missing}")
            else:
                test_results.append(f"❌ TEST 9: Expected list, got {type(galleries)}")
                log(f"❌ Expected list")
        else:
            test_results.append(f"❌ TEST 9: GET /api/superadmin/galleries failed: {resp.status_code} {resp.text}")
            log(f"❌ Failed: {resp.status_code} {resp.text}")
        
        # ===== TEST 10: GET /api/superadmin/storage =====
        log("\n--- TEST 10: GET /api/superadmin/storage ---")
        resp = requests.get(f"{BASE_URL}/superadmin/storage",
            headers={"Authorization": f"Bearer {superadmin_token}"})
        if resp.status_code == 200:
            storage = resp.json()
            required = ["total_bytes", "platform_limit_gb", "photographers"]
            missing = [f for f in required if f not in storage]
            if not missing:
                test_results.append(f"✅ TEST 10: GET /api/superadmin/storage returns correct structure")
                log(f"✅ Total storage: {storage['total_bytes']} bytes, {len(storage['photographers'])} photographers")
            else:
                test_results.append(f"❌ TEST 10: Missing fields: {missing}")
                log(f"❌ Missing fields: {missing}")
        else:
            test_results.append(f"❌ TEST 10: GET /api/superadmin/storage failed: {resp.status_code} {resp.text}")
            log(f"❌ Failed: {resp.status_code} {resp.text}")
        
        # ===== TEST 11: GET /api/superadmin/activity =====
        log("\n--- TEST 11: GET /api/superadmin/activity ---")
        resp = requests.get(f"{BASE_URL}/superadmin/activity",
            headers={"Authorization": f"Bearer {superadmin_token}"})
        if resp.status_code == 200:
            activity = resp.json()
            if isinstance(activity, list):
                test_results.append(f"✅ TEST 11: GET /api/superadmin/activity returns {len(activity)} activity entries")
                log(f"✅ Found {len(activity)} activity entries")
            else:
                test_results.append(f"❌ TEST 11: Expected list, got {type(activity)}")
                log(f"❌ Expected list")
        else:
            test_results.append(f"❌ TEST 11: GET /api/superadmin/activity failed: {resp.status_code} {resp.text}")
            log(f"❌ Failed: {resp.status_code} {resp.text}")
        
        # ===== TEST 12: GET /api/superadmin/settings =====
        log("\n--- TEST 12: GET /api/superadmin/settings ---")
        resp = requests.get(f"{BASE_URL}/superadmin/settings",
            headers={"Authorization": f"Bearer {superadmin_token}"})
        if resp.status_code == 200:
            settings = resp.json()
            if "platform_name" in settings:
                test_results.append(f"✅ TEST 12: GET /api/superadmin/settings returns platform_name: {settings['platform_name']}")
                log(f"✅ Platform name: {settings['platform_name']}")
            else:
                test_results.append(f"❌ TEST 12: Missing platform_name in settings")
                log(f"❌ Missing platform_name")
        else:
            test_results.append(f"❌ TEST 12: GET /api/superadmin/settings failed: {resp.status_code} {resp.text}")
            log(f"❌ Failed: {resp.status_code} {resp.text}")
        
        # ===== TEST 13: Create throwaway photographer for control tests =====
        log("\n--- TEST 13: Create throwaway photographer for control tests ---")
        resp = requests.post(f"{BASE_URL}/auth/admin/register", json={
            "email": "throwaway_photographer@superadmintest.example",
            "password": "ThrowawayPhotographer@12345",
            "name": "Throwaway Photographer"
        })
        if resp.status_code == 200:
            throwaway_photographer_id = resp.json()["user"]["user_id"]
            throwaway_photographer_token = resp.json()["session_token"]
            test_results.append(f"✅ TEST 13: Created throwaway photographer: {throwaway_photographer_id}")
            log(f"✅ Created throwaway photographer: {throwaway_photographer_id}")
            
            # Create an event for this photographer to test uploads_disabled
            resp = requests.post(f"{BASE_URL}/events",
                headers={"Authorization": f"Bearer {throwaway_photographer_token}"},
                json={
                    "name": "Throwaway Test Event",
                    "category": "wedding",
                    "date": "2026-12-15"
                })
            if resp.status_code == 200:
                throwaway_event_id = resp.json()["event_id"]
                log(f"✅ Created throwaway event: {throwaway_event_id}")
            else:
                log(f"⚠️  Failed to create throwaway event: {resp.status_code}")
        else:
            test_results.append(f"❌ TEST 13: Failed to create throwaway photographer: {resp.status_code} {resp.text}")
            log(f"❌ Failed: {resp.status_code} {resp.text}")
            throwaway_photographer_id = None
        
        # ===== TEST 14: PATCH /api/superadmin/photographers/{id} - Disable uploads =====
        if throwaway_photographer_id:
            log("\n--- TEST 14: PATCH /api/superadmin/photographers/{id} - Disable uploads ---")
            resp = requests.patch(f"{BASE_URL}/superadmin/photographers/{throwaway_photographer_id}",
                headers={"Authorization": f"Bearer {superadmin_token}"},
                json={"uploads_disabled": True})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("uploads_disabled") == True:
                    test_results.append("✅ TEST 14: PATCH uploads_disabled=true successful")
                    log(f"✅ Uploads disabled for photographer: {throwaway_photographer_id}")
                    
                    # Verify uploads are actually blocked
                    log("   Verifying uploads are blocked...")
                    img_buf = create_test_image()
                    resp = requests.post(f"{BASE_URL}/events/{throwaway_event_id}/photos",
                        headers={"Authorization": f"Bearer {throwaway_photographer_token}"},
                        files={"file": ("test.jpg", img_buf, "image/jpeg")})
                    if resp.status_code == 403:
                        test_results.append("✅ TEST 14b: Photo upload correctly blocked when uploads_disabled=true")
                        log("   ✅ Photo upload correctly blocked (403)")
                    else:
                        test_results.append(f"❌ TEST 14b: Photo upload not blocked, got {resp.status_code}")
                        log(f"   ❌ Photo upload not blocked, got {resp.status_code}")
                else:
                    test_results.append(f"❌ TEST 14: uploads_disabled not set correctly: {data.get('uploads_disabled')}")
                    log(f"❌ uploads_disabled not set correctly")
            else:
                test_results.append(f"❌ TEST 14: PATCH uploads_disabled failed: {resp.status_code} {resp.text}")
                log(f"❌ Failed: {resp.status_code} {resp.text}")
        
        # ===== TEST 15: PATCH /api/superadmin/photographers/{id} - Enable uploads =====
        if throwaway_photographer_id:
            log("\n--- TEST 15: PATCH /api/superadmin/photographers/{id} - Enable uploads ---")
            resp = requests.patch(f"{BASE_URL}/superadmin/photographers/{throwaway_photographer_id}",
                headers={"Authorization": f"Bearer {superadmin_token}"},
                json={"uploads_disabled": False})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("uploads_disabled") == False:
                    test_results.append("✅ TEST 15: PATCH uploads_disabled=false successful")
                    log(f"✅ Uploads re-enabled for photographer: {throwaway_photographer_id}")
                    
                    # Verify uploads are now allowed
                    log("   Verifying uploads are now allowed...")
                    img_buf = create_test_image()
                    resp = requests.post(f"{BASE_URL}/events/{throwaway_event_id}/photos",
                        headers={"Authorization": f"Bearer {throwaway_photographer_token}"},
                        files={"file": ("test.jpg", img_buf, "image/jpeg")})
                    if resp.status_code == 200:
                        test_results.append("✅ TEST 15b: Photo upload correctly allowed when uploads_disabled=false")
                        log("   ✅ Photo upload correctly allowed (200)")
                    else:
                        test_results.append(f"❌ TEST 15b: Photo upload still blocked, got {resp.status_code}")
                        log(f"   ❌ Photo upload still blocked, got {resp.status_code}")
                else:
                    test_results.append(f"❌ TEST 15: uploads_disabled not set correctly: {data.get('uploads_disabled')}")
                    log(f"❌ uploads_disabled not set correctly")
            else:
                test_results.append(f"❌ TEST 15: PATCH uploads_disabled failed: {resp.status_code} {resp.text}")
                log(f"❌ Failed: {resp.status_code} {resp.text}")
        
        # ===== TEST 16: PATCH /api/superadmin/photographers/{id} - Suspend status =====
        if throwaway_photographer_id:
            log("\n--- TEST 16: PATCH /api/superadmin/photographers/{id} - Suspend status ---")
            resp = requests.patch(f"{BASE_URL}/superadmin/photographers/{throwaway_photographer_id}",
                headers={"Authorization": f"Bearer {superadmin_token}"},
                json={"status": "suspended"})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "suspended":
                    test_results.append("✅ TEST 16: PATCH status=suspended successful")
                    log(f"✅ Status set to suspended for photographer: {throwaway_photographer_id}")
                    
                    # Verify admin access is blocked
                    log("   Verifying admin access is blocked...")
                    resp = requests.get(f"{BASE_URL}/events",
                        headers={"Authorization": f"Bearer {throwaway_photographer_token}"})
                    if resp.status_code == 403:
                        test_results.append("✅ TEST 16b: Admin access correctly blocked when status=suspended")
                        log("   ✅ Admin access correctly blocked (403)")
                    else:
                        test_results.append(f"❌ TEST 16b: Admin access not blocked, got {resp.status_code}")
                        log(f"   ❌ Admin access not blocked, got {resp.status_code}")
                else:
                    test_results.append(f"❌ TEST 16: status not set correctly: {data.get('status')}")
                    log(f"❌ status not set correctly")
            else:
                test_results.append(f"❌ TEST 16: PATCH status failed: {resp.status_code} {resp.text}")
                log(f"❌ Failed: {resp.status_code} {resp.text}")
        
        # ===== TEST 17: PATCH /api/superadmin/photographers/{id} - Restore to active =====
        if throwaway_photographer_id:
            log("\n--- TEST 17: PATCH /api/superadmin/photographers/{id} - Restore to active ---")
            resp = requests.patch(f"{BASE_URL}/superadmin/photographers/{throwaway_photographer_id}",
                headers={"Authorization": f"Bearer {superadmin_token}"},
                json={"status": "active"})
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "active":
                    test_results.append("✅ TEST 17: PATCH status=active successful")
                    log(f"✅ Status restored to active for photographer: {throwaway_photographer_id}")
                    
                    # Verify admin access is restored
                    log("   Verifying admin access is restored...")
                    resp = requests.get(f"{BASE_URL}/events",
                        headers={"Authorization": f"Bearer {throwaway_photographer_token}"})
                    if resp.status_code == 200:
                        test_results.append("✅ TEST 17b: Admin access correctly restored when status=active")
                        log("   ✅ Admin access correctly restored (200)")
                    else:
                        test_results.append(f"❌ TEST 17b: Admin access not restored, got {resp.status_code}")
                        log(f"   ❌ Admin access not restored, got {resp.status_code}")
                else:
                    test_results.append(f"❌ TEST 17: status not set correctly: {data.get('status')}")
                    log(f"❌ status not set correctly")
            else:
                test_results.append(f"❌ TEST 17: PATCH status failed: {resp.status_code} {resp.text}")
                log(f"❌ Failed: {resp.status_code} {resp.text}")
        
        # ===== TEST 18: Verify existing resources not deleted when uploads_disabled =====
        if throwaway_photographer_id and throwaway_event_id:
            log("\n--- TEST 18: Verify existing resources not deleted when uploads_disabled ---")
            # Disable uploads again
            resp = requests.patch(f"{BASE_URL}/superadmin/photographers/{throwaway_photographer_id}",
                headers={"Authorization": f"Bearer {superadmin_token}"},
                json={"uploads_disabled": True})
            
            # Verify event still exists
            resp = requests.get(f"{BASE_URL}/events/{throwaway_event_id}",
                headers={"Authorization": f"Bearer {throwaway_photographer_token}"})
            if resp.status_code == 200:
                test_results.append("✅ TEST 18: Existing event not deleted when uploads_disabled=true")
                log("✅ Existing event still accessible")
            else:
                test_results.append(f"❌ TEST 18: Existing event deleted or inaccessible: {resp.status_code}")
                log(f"❌ Event deleted or inaccessible: {resp.status_code}")
        
        # ===== TEST 19: Verify normal admin routes still work =====
        log("\n--- TEST 19: Verify normal admin routes still work after superadmin addition ---")
        if admin_token:
            # Test a few key admin endpoints
            endpoints_to_test = [
                ("/events", "GET"),
                ("/clients", "GET"),
                ("/albums", "GET"),
            ]
            
            all_working = True
            for endpoint, method in endpoints_to_test:
                resp = requests.request(method, f"{BASE_URL}{endpoint}",
                    headers={"Authorization": f"Bearer {admin_token}"})
                if resp.status_code != 200:
                    all_working = False
                    log(f"   ❌ {method} {endpoint} failed: {resp.status_code}")
            
            if all_working:
                test_results.append("✅ TEST 19: Normal admin routes still work after superadmin addition")
                log("✅ All tested admin routes working")
            else:
                test_results.append("❌ TEST 19: Some normal admin routes broken")
                log("❌ Some admin routes broken")
        
        # ===== TEST 20: Verify seeded admin login still works =====
        log("\n--- TEST 20: Verify seeded admin login still works ---")
        resp = requests.post(f"{BASE_URL}/auth/admin/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if resp.status_code == 200:
            test_results.append("✅ TEST 20: Seeded admin login still works")
            log("✅ Seeded admin login working")
        else:
            test_results.append(f"❌ TEST 20: Seeded admin login broken: {resp.status_code}")
            log(f"❌ Seeded admin login broken: {resp.status_code}")
        
        # ===== SUMMARY =====
        log("\n=== TEST SUMMARY ===")
        passed = sum(1 for r in test_results if r.startswith("✅"))
        failed = sum(1 for r in test_results if r.startswith("❌"))
        log(f"Total tests: {len(test_results)}")
        log(f"Passed: {passed}")
        log(f"Failed: {failed}")
        
        if failed > 0:
            log("\n❌ FAILED TESTS:")
            for r in test_results:
                if r.startswith("❌"):
                    log(f"  {r}")
        
        log("\nAll test results:")
        for r in test_results:
            log(f"  {r}")
        
        # Return exit code based on results
        return 0 if failed == 0 else 1
        
    finally:
        # ===== CLEANUP =====
        log("\n--- CLEANUP: Deleting throwaway resources ---")
        
        if throwaway_event_id and throwaway_photographer_token:
            try:
                resp = requests.delete(f"{BASE_URL}/events/{throwaway_event_id}",
                    headers={"Authorization": f"Bearer {throwaway_photographer_token}"})
                if resp.status_code == 200:
                    log(f"✅ Deleted throwaway event: {throwaway_event_id}")
                else:
                    log(f"⚠️  Failed to delete throwaway event: {resp.status_code}")
            except Exception as e:
                log(f"⚠️  Error deleting throwaway event: {e}")
        
        if throwaway_photographer_id:
            log(f"⚠️  Note: Throwaway photographer account cleanup requires manual DB deletion")
            log(f"   Photographer ID: {throwaway_photographer_id}")
            log(f"   Email: throwaway_photographer@superadmintest.example")
        
        log("\n✅ Test complete")

if __name__ == "__main__":
    sys.exit(main())
