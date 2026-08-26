#!/usr/bin/env python3
"""
Backend smoke test after repository bootstrap.
Tests basic API functionality without attempting photo uploads (storage may be unavailable).
"""

import requests
import time
import sys

# Use internal backend URL
BASE_URL = "http://127.0.0.1:8001/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

def log(msg):
    print(f"[TEST] {msg}")

def test_health_check():
    """Test 1: GET /api/ health check should return 200"""
    log("Test 1: Health check GET /api/")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=10)
        log(f"  Status: {response.status_code}")
        log(f"  Response: {response.json()}")
        
        if response.status_code == 200:
            log("  ✅ PASS: Health check returned 200")
            return True
        else:
            log(f"  ❌ FAIL: Expected 200, got {response.status_code}")
            return False
    except Exception as e:
        log(f"  ❌ FAIL: Exception: {e}")
        return False

def test_admin_login():
    """Test 2: Admin login should return session token"""
    log(f"Test 2: Admin login POST /api/auth/admin/login")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        log(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            log(f"  Response keys: {list(data.keys())}")
            
            if "session_token" in data:
                log(f"  Session token: {data['session_token'][:20]}...")
                log("  ✅ PASS: Admin login successful with session_token")
                return True, data["session_token"]
            else:
                log(f"  ❌ FAIL: No session_token in response")
                return False, None
        else:
            log(f"  ❌ FAIL: Expected 200, got {response.status_code}")
            log(f"  Response: {response.text}")
            return False, None
    except Exception as e:
        log(f"  ❌ FAIL: Exception: {e}")
        return False, None

def test_create_event(token):
    """Test 3: Create a throwaway event"""
    log("Test 3: Create throwaway event POST /api/events")
    try:
        response = requests.post(
            f"{BASE_URL}/events",
            json={
                "name": "Smoke Test Event",
                "category": "wedding",
                "date": "2026-08-26"
            },
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        log(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            log(f"  Response keys: {list(data.keys())}")
            
            if "event_id" in data:
                event_id = data["event_id"]
                log(f"  Event ID: {event_id}")
                log("  ✅ PASS: Event created successfully")
                return True, event_id
            else:
                log(f"  ❌ FAIL: No event_id in response")
                return False, None
        else:
            log(f"  ❌ FAIL: Expected 200, got {response.status_code}")
            log(f"  Response: {response.text}")
            return False, None
    except Exception as e:
        log(f"  ❌ FAIL: Exception: {e}")
        return False, None

def test_list_events(token, expected_event_id):
    """Test 4: List events and verify the created event is present"""
    log("Test 4: List events GET /api/events")
    try:
        response = requests.get(
            f"{BASE_URL}/events",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        log(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            log(f"  Total events: {len(data)}")
            
            # Check if our event is in the list
            event_found = False
            for event in data:
                if event.get("event_id") == expected_event_id:
                    event_found = True
                    log(f"  Found event: {event.get('name')} ({event.get('event_id')})")
                    break
            
            if event_found:
                log("  ✅ PASS: Created event found in list")
                return True
            else:
                log(f"  ❌ FAIL: Event {expected_event_id} not found in list")
                return False
        else:
            log(f"  ❌ FAIL: Expected 200, got {response.status_code}")
            log(f"  Response: {response.text}")
            return False
    except Exception as e:
        log(f"  ❌ FAIL: Exception: {e}")
        return False

def test_delete_event(token, event_id):
    """Test 5: Delete the throwaway event (cleanup)"""
    log(f"Test 5: Delete event DELETE /api/events/{event_id}")
    try:
        response = requests.delete(
            f"{BASE_URL}/events/{event_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        log(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            log(f"  Response: {data}")
            log("  ✅ PASS: Event deleted successfully")
            return True
        else:
            log(f"  ❌ FAIL: Expected 200, got {response.status_code}")
            log(f"  Response: {response.text}")
            return False
    except Exception as e:
        log(f"  ❌ FAIL: Exception: {e}")
        return False

def test_service_stability():
    """Test 6: Check that service stays running after several seconds"""
    log("Test 6: Service stability check (waiting 5 seconds)")
    try:
        time.sleep(5)
        
        # Try health check again
        response = requests.get(f"{BASE_URL}/", timeout=10)
        log(f"  Status after 5s: {response.status_code}")
        
        if response.status_code == 200:
            log("  ✅ PASS: Service still running after 5 seconds")
            return True
        else:
            log(f"  ❌ FAIL: Service returned {response.status_code}")
            return False
    except Exception as e:
        log(f"  ❌ FAIL: Service not responding: {e}")
        return False

def main():
    log("=" * 80)
    log("BACKEND SMOKE TEST - Repository Bootstrap Verification")
    log("=" * 80)
    log("")
    log("NOTE: STORAGE_BACKEND=emergent without EMERGENT_LLM_KEY")
    log("      Storage init failure is EXPECTED and not treated as a code failure")
    log("      unless it prevents service startup.")
    log("")
    
    results = []
    
    # Test 1: Health check
    results.append(("Health Check", test_health_check()))
    log("")
    
    # Test 2: Admin login
    login_success, token = test_admin_login()
    results.append(("Admin Login", login_success))
    log("")
    
    if not login_success:
        log("❌ Cannot proceed without admin token. Stopping tests.")
        print_summary(results)
        sys.exit(1)
    
    # Test 3: Create event
    create_success, event_id = test_create_event(token)
    results.append(("Create Event", create_success))
    log("")
    
    if not create_success:
        log("⚠️  Event creation failed. Skipping remaining tests.")
        print_summary(results)
        sys.exit(1)
    
    # Test 4: List events
    results.append(("List Events", test_list_events(token, event_id)))
    log("")
    
    # Test 5: Delete event (cleanup)
    results.append(("Delete Event", test_delete_event(token, event_id)))
    log("")
    
    # Test 6: Service stability
    results.append(("Service Stability", test_service_stability()))
    log("")
    
    print_summary(results)
    
    # Exit with appropriate code
    if all(result[1] for result in results):
        log("✅ ALL TESTS PASSED")
        sys.exit(0)
    else:
        log("❌ SOME TESTS FAILED")
        sys.exit(1)

def print_summary(results):
    log("=" * 80)
    log("TEST SUMMARY")
    log("=" * 80)
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        log(f"  {status}: {test_name}")
    log("=" * 80)

if __name__ == "__main__":
    main()
