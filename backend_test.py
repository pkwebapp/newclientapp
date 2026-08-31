#!/usr/bin/env python3
"""
Backend test for Synology NAS gallery source feature.
Tests the newly-added /api/events/synology endpoint.
"""

import requests
import json
import sys

# Configuration
BASE_URL = "https://repo-pull-dev.preview.emergentagent.com/api"
TEST_ADMIN_BEARER_TOKEN = "st_01685e4cb2964a91b0c2287e090f31ffebe776c10a734442b2e1b89abe7a0162"
HEADERS = {
    "Authorization": f"Bearer {TEST_ADMIN_BEARER_TOKEN}",
    "Content-Type": "application/json"
}

# Test results tracking
test_results = []
created_event_ids = []

def log_test(test_name, passed, status_code=None, details=None):
    """Log test result"""
    result = {
        "test": test_name,
        "passed": passed,
        "status_code": status_code,
        "details": details
    }
    test_results.append(result)
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} - {test_name}")
    if status_code:
        print(f"  Status: {status_code}")
    if details:
        print(f"  Details: {details}")
    print()

def test_auth_sanity():
    """Test 1: Sanity check - GET /api/auth/me should return 200 with role=admin"""
    print("=" * 80)
    print("TEST 1: Sanity check - Auth token validation")
    print("=" * 80)
    
    try:
        response = requests.get(f"{BASE_URL}/auth/me", headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            user = data.get("user", {})
            role = user.get("role")
            if role == "admin":
                log_test("Auth sanity check - /auth/me returns role=admin", True, 200, 
                        f"user_id: {user.get('user_id')}, role: {role}")
                return True
            else:
                log_test("Auth sanity check - /auth/me returns role=admin", False, 200, 
                        f"Expected role=admin, got role={role}")
                return False
        else:
            log_test("Auth sanity check - /auth/me returns role=admin", False, response.status_code, 
                    response.text[:200])
            return False
    except Exception as e:
        log_test("Auth sanity check - /auth/me returns role=admin", False, None, str(e))
        return False

def test_events_list():
    """Test 2: Sanity check - GET /api/events should return 200"""
    print("=" * 80)
    print("TEST 2: Sanity check - Events list endpoint")
    print("=" * 80)
    
    try:
        response = requests.get(f"{BASE_URL}/events", headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            log_test("Events list endpoint accessible", True, 200, 
                    f"Returned {len(data) if isinstance(data, list) else 'N/A'} events")
            return True
        else:
            log_test("Events list endpoint accessible", False, response.status_code, 
                    response.text[:200])
            return False
    except Exception as e:
        log_test("Events list endpoint accessible", False, None, str(e))
        return False

def test_synology_valid_gallery():
    """Test 3: POST /api/events/synology with valid gallery_url"""
    print("=" * 80)
    print("TEST 3: Create Synology event with valid gallery URL")
    print("=" * 80)
    
    payload = {
        "name": "Divik 27 March",
        "category": "event",
        "gallery_url": "http://localhost:9099/"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/events/synology", 
                                headers=HEADERS, 
                                json=payload, 
                                timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            event_id = data.get("event_id")
            source = data.get("source")
            photo_count = data.get("photo_count")
            indexing_status = data.get("indexing_status")
            cover_url = data.get("cover_url")
            
            # Validate response fields
            checks = []
            checks.append(("source == 'synology'", source == "synology"))
            checks.append(("photo_count == 3", photo_count == 3))
            checks.append(("indexing_status == 'ready'", indexing_status == "ready"))
            checks.append(("cover_url is present", cover_url is not None and cover_url != ""))
            checks.append(("event_id is present", event_id is not None and event_id != ""))
            
            all_passed = all(check[1] for check in checks)
            
            if all_passed and event_id:
                created_event_ids.append(event_id)
                details = f"event_id: {event_id}, source: {source}, photo_count: {photo_count}, " \
                         f"indexing_status: {indexing_status}, cover_url: {cover_url[:50]}..."
                log_test("Create Synology event with valid gallery", True, 200, details)
                return True, event_id
            else:
                failed_checks = [check[0] for check in checks if not check[1]]
                log_test("Create Synology event with valid gallery", False, 200, 
                        f"Failed checks: {', '.join(failed_checks)}")
                return False, None
        else:
            log_test("Create Synology event with valid gallery", False, response.status_code, 
                    response.text[:300])
            return False, None
    except Exception as e:
        log_test("Create Synology event with valid gallery", False, None, str(e))
        return False, None

def test_get_event_photos(event_id):
    """Test 4: GET /api/events/{event_id}/photos"""
    print("=" * 80)
    print("TEST 4: Get photos from Synology event")
    print("=" * 80)
    
    try:
        response = requests.get(f"{BASE_URL}/events/{event_id}/photos", 
                               headers=HEADERS, 
                               timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Check if it's a list or has a 'photos' or 'items' key
            if isinstance(data, list):
                photos = data
                total = len(photos)
            elif isinstance(data, dict) and 'items' in data:
                photos = data['items']
                total = data.get('total', len(photos))
            elif isinstance(data, dict) and 'photos' in data:
                photos = data['photos']
                total = data.get('total', len(photos))
            else:
                log_test("Get photos from Synology event", False, 200, 
                        f"Unexpected response format: {type(data)}, keys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}")
                return False
            
            # Validate we have 3 photos
            if total != 3:
                log_test("Get photos from Synology event", False, 200, 
                        f"Expected 3 photos, got {total}")
                return False
            
            # Validate each photo has source="synology" and URLs
            all_valid = True
            for i, photo in enumerate(photos):
                source = photo.get("source")
                url = photo.get("url")
                thumb_url = photo.get("thumb_url")
                
                if source != "synology":
                    all_valid = False
                    print(f"  Photo {i+1}: source is '{source}', expected 'synology'")
                
                if not url or not url.startswith("http://localhost:9099/"):
                    all_valid = False
                    print(f"  Photo {i+1}: url is '{url}', expected to start with 'http://localhost:9099/'")
            
            if all_valid:
                filenames = [p.get('filename', 'N/A') for p in photos]
                log_test("Get photos from Synology event", True, 200, 
                        f"total={total}, all source='synology', filenames: {filenames}")
                return True
            else:
                log_test("Get photos from Synology event", False, 200, 
                        "Some photos have incorrect source or URL format")
                return False
        else:
            log_test("Get photos from Synology event", False, response.status_code, 
                    response.text[:300])
            return False
    except Exception as e:
        log_test("Get photos from Synology event", False, None, str(e))
        return False

def test_empty_url():
    """Test 5: POST /api/events/synology with empty gallery_url"""
    print("=" * 80)
    print("TEST 5: Negative test - Empty gallery_url")
    print("=" * 80)
    
    payload = {
        "name": "Bad",
        "gallery_url": ""
    }
    
    try:
        response = requests.post(f"{BASE_URL}/events/synology", 
                                headers=HEADERS, 
                                json=payload, 
                                timeout=10)
        
        if response.status_code == 400:
            error_msg = response.json().get("detail", "")
            if "Paste a Synology gallery URL" in error_msg:
                log_test("Empty gallery_url returns 400 with correct message", True, 400, 
                        f"Error: {error_msg}")
                return True
            else:
                log_test("Empty gallery_url returns 400 with correct message", False, 400, 
                        f"Expected 'Paste a Synology gallery URL', got: {error_msg}")
                return False
        else:
            log_test("Empty gallery_url returns 400 with correct message", False, response.status_code, 
                    f"Expected 400, got {response.status_code}")
            return False
    except Exception as e:
        log_test("Empty gallery_url returns 400 with correct message", False, None, str(e))
        return False

def test_non_http_scheme():
    """Test 6: POST /api/events/synology with non-http scheme"""
    print("=" * 80)
    print("TEST 6: Negative test - Non-HTTP scheme (ftp://)")
    print("=" * 80)
    
    payload = {
        "name": "X",
        "gallery_url": "ftp://x"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/events/synology", 
                                headers=HEADERS, 
                                json=payload, 
                                timeout=10)
        
        if response.status_code == 400:
            error_msg = response.json().get("detail", "")
            if "Use a full http:// or https:// gallery URL" in error_msg:
                log_test("Non-HTTP scheme returns 400 with correct message", True, 400, 
                        f"Error: {error_msg}")
                return True
            else:
                log_test("Non-HTTP scheme returns 400 with correct message", False, 400, 
                        f"Expected 'Use a full http:// or https:// gallery URL', got: {error_msg}")
                return False
        else:
            log_test("Non-HTTP scheme returns 400 with correct message", False, response.status_code, 
                    f"Expected 400, got {response.status_code}")
            return False
    except Exception as e:
        log_test("Non-HTTP scheme returns 400 with correct message", False, None, str(e))
        return False

def test_unreachable_url():
    """Test 7: POST /api/events/synology with unreachable URL"""
    print("=" * 80)
    print("TEST 7: Negative test - Unreachable URL")
    print("=" * 80)
    
    payload = {
        "name": "Bad",
        "gallery_url": "http://localhost:1/nope"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/events/synology", 
                                headers=HEADERS, 
                                json=payload, 
                                timeout=10)
        
        if response.status_code == 400:
            error_msg = response.json().get("detail", "")
            if "not reachable" in error_msg.lower():
                log_test("Unreachable URL returns 400 with correct message", True, 400, 
                        f"Error: {error_msg}")
                return True
            else:
                log_test("Unreachable URL returns 400 with correct message", False, 400, 
                        f"Expected 'not reachable', got: {error_msg}")
                return False
        else:
            log_test("Unreachable URL returns 400 with correct message", False, response.status_code, 
                    f"Expected 400, got {response.status_code}")
            return False
    except Exception as e:
        log_test("Unreachable URL returns 400 with correct message", False, None, str(e))
        return False

def test_single_image():
    """Test 8: POST /api/events/synology with single image URL"""
    print("=" * 80)
    print("TEST 8: Create Synology event with single image URL")
    print("=" * 80)
    
    payload = {
        "name": "Single",
        "gallery_url": "http://localhost:9099/a.jpg"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/events/synology", 
                                headers=HEADERS, 
                                json=payload, 
                                timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            event_id = data.get("event_id")
            photo_count = data.get("photo_count")
            
            if photo_count == 1 and event_id:
                created_event_ids.append(event_id)
                log_test("Single image URL creates event with photo_count=1", True, 200, 
                        f"event_id: {event_id}, photo_count: {photo_count}")
                return True, event_id
            else:
                log_test("Single image URL creates event with photo_count=1", False, 200, 
                        f"Expected photo_count=1, got {photo_count}")
                return False, None
        else:
            log_test("Single image URL creates event with photo_count=1", False, response.status_code, 
                    response.text[:300])
            return False, None
    except Exception as e:
        log_test("Single image URL creates event with photo_count=1", False, None, str(e))
        return False, None

def test_delete_event(event_id):
    """Test 9: DELETE /api/events/{event_id}"""
    print("=" * 80)
    print(f"TEST 9: Delete event {event_id}")
    print("=" * 80)
    
    try:
        response = requests.delete(f"{BASE_URL}/events/{event_id}", 
                                  headers=HEADERS, 
                                  timeout=10)
        
        if response.status_code == 200:
            log_test(f"Delete event {event_id}", True, 200, "Event deleted successfully")
            return True
        else:
            log_test(f"Delete event {event_id}", False, response.status_code, 
                    response.text[:300])
            return False
    except Exception as e:
        log_test(f"Delete event {event_id}", False, None, str(e))
        return False

def test_regression_cloudinary():
    """Test 10: Regression - Create normal Cloudinary event"""
    print("=" * 80)
    print("TEST 10: Regression - Create normal Cloudinary event")
    print("=" * 80)
    
    payload = {
        "name": "QA Regression",
        "category": "event"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/events", 
                                headers=HEADERS, 
                                json=payload, 
                                timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            event_id = data.get("event_id")
            source = data.get("source")
            
            if event_id and source != "synology":
                created_event_ids.append(event_id)
                log_test("Regression - Normal event creation still works", True, 200, 
                        f"event_id: {event_id}, source: {source}")
                return True, event_id
            else:
                log_test("Regression - Normal event creation still works", False, 200, 
                        f"event_id: {event_id}, source: {source} (should not be 'synology')")
                return False, None
        else:
            log_test("Regression - Normal event creation still works", False, response.status_code, 
                    response.text[:300])
            return False, None
    except Exception as e:
        log_test("Regression - Normal event creation still works", False, None, str(e))
        return False, None

def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("SYNOLOGY NAS GALLERY SOURCE - BACKEND TESTING")
    print("=" * 80)
    print(f"Base URL: {BASE_URL}")
    print(f"Using pre-seeded admin token: {TEST_ADMIN_BEARER_TOKEN[:20]}...")
    print("=" * 80 + "\n")
    
    # Test 1 & 2: Sanity checks
    if not test_auth_sanity():
        print("\n❌ CRITICAL: Auth sanity check failed. Stopping tests.")
        sys.exit(1)
    
    if not test_events_list():
        print("\n❌ CRITICAL: Events list endpoint failed. Stopping tests.")
        sys.exit(1)
    
    # Test 3 & 4: Valid gallery creation and photo listing
    success, event_id = test_synology_valid_gallery()
    if success and event_id:
        test_get_event_photos(event_id)
    
    # Test 5-7: Negative tests
    test_empty_url()
    test_non_http_scheme()
    test_unreachable_url()
    
    # Test 8: Single image
    test_single_image()
    
    # Test 10: Regression
    test_regression_cloudinary()
    
    # Test 9: Cleanup - delete all created events
    print("\n" + "=" * 80)
    print("CLEANUP: Deleting all created events")
    print("=" * 80)
    for event_id in created_event_ids:
        test_delete_event(event_id)
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for r in test_results if r["passed"])
    total = len(test_results)
    
    print(f"\nTotal tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED")
        print("\nFailed tests:")
        for r in test_results:
            if not r["passed"]:
                print(f"  - {r['test']}")
                if r["details"]:
                    print(f"    {r['details']}")
        sys.exit(1)

if __name__ == "__main__":
    main()
