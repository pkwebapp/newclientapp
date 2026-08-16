"""
Backend API tests for Lumiere Gallery - Gallery Lifecycle Feature
Tests Archive / Unarchive / Delete endpoints with Cloudinary + Rekognition cleanup
"""
import requests
import json
import sys
import io
from PIL import Image

# Configuration
BASE_URL = "https://3c9dba23-7af3-4206-b248-56c35ce521c7.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"
ARCHIVED_MESSAGE = "This gallery has been archived. Please contact your photographer for access."

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

def create_test_image(width=100, height=100, color=(255, 0, 0)):
    """Create a small test JPEG image in memory"""
    img = Image.new('RGB', (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    buf.seek(0)
    return buf

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
    """Test 1: Create a throwaway event"""
    print("\n=== Test 1: Create Throwaway Event ===")
    try:
        response = requests.post(
            f"{BASE_URL}/events",
            json={"name": "QA Lifecycle", "category": "wedding"},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            event_id = data.get("event_id")
            status = data.get("status")
            
            if not event_id:
                log_test("Test 1: Create event", False, "No event_id in response")
                return None
            
            if status != "active":
                log_test("Test 1: Create event", False, f"Expected status='active', got '{status}'")
                return None
            
            log_test("Test 1: Create event", True, f"event_id={event_id}, status={status}")
            return event_id
        else:
            log_test("Test 1: Create event", False, f"Status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        log_test("Test 1: Create event", False, f"Exception: {str(e)}")
        return None

def test_2_upload_photos(admin_token, event_id):
    """Test 2: Upload 2 small JPEG images"""
    print(f"\n=== Test 2: Upload 2 Photos to Event {event_id} ===")
    photo_ids = []
    
    for i in range(2):
        try:
            # Create a small test image with different colors
            color = (255, 0, 0) if i == 0 else (0, 255, 0)
            img_buf = create_test_image(color=color)
            
            files = {'file': (f'test_photo_{i+1}.jpg', img_buf, 'image/jpeg')}
            response = requests.post(
                f"{BASE_URL}/events/{event_id}/photos",
                files=files,
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                photo_id = data.get("photo_id")
                storage_path = data.get("storage_path")
                thumb_path = data.get("thumb_path")
                url = data.get("url")
                thumb_url = data.get("thumb_url")
                
                if not photo_id:
                    log_test(f"Test 2.{i+1}: Upload photo {i+1}", False, "No photo_id in response")
                    continue
                
                # Verify CDN URLs
                if not url or not url.startswith("https://res.cloudinary.com/"):
                    log_test(f"Test 2.{i+1}: Upload photo {i+1}", False, f"Invalid url: {url}")
                    continue
                
                if not thumb_url or not thumb_url.startswith("https://res.cloudinary.com/"):
                    log_test(f"Test 2.{i+1}: Upload photo {i+1}", False, f"Invalid thumb_url: {thumb_url}")
                    continue
                
                log_test(
                    f"Test 2.{i+1}: Upload photo {i+1}", 
                    True, 
                    f"photo_id={photo_id}, url={url[:50]}..., thumb_url={thumb_url[:50]}..."
                )
                photo_ids.append(photo_id)
            else:
                log_test(f"Test 2.{i+1}: Upload photo {i+1}", False, f"Status {response.status_code}: {response.text}")
        except Exception as e:
            log_test(f"Test 2.{i+1}: Upload photo {i+1}", False, f"Exception: {str(e)}")
    
    return photo_ids

def test_3_verify_cover_url(admin_token, event_id):
    """Test 3: Verify event has cover_url with Cloudinary CDN"""
    print(f"\n=== Test 3: Verify Cover URL for Event {event_id} ===")
    try:
        response = requests.get(
            f"{BASE_URL}/events/{event_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            cover_url = data.get("cover_url")
            
            if not cover_url:
                log_test("Test 3: Verify cover_url", False, "No cover_url in response")
                return False
            
            if not cover_url.startswith("https://res.cloudinary.com/"):
                log_test("Test 3: Verify cover_url", False, f"Invalid cover_url: {cover_url}")
                return False
            
            log_test("Test 3: Verify cover_url", True, f"cover_url={cover_url[:60]}...")
            return True
        else:
            log_test("Test 3: Verify cover_url", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 3: Verify cover_url", False, f"Exception: {str(e)}")
        return False

def test_4_verify_photos_cdn_urls(admin_token, event_id):
    """Test 4: Verify all photos have CDN URLs"""
    print(f"\n=== Test 4: Verify Photos CDN URLs ===")
    try:
        response = requests.get(
            f"{BASE_URL}/events/{event_id}/photos",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])
            
            if len(items) < 2:
                log_test("Test 4: Verify photos CDN URLs", False, f"Expected at least 2 photos, got {len(items)}")
                return False
            
            all_valid = True
            for photo in items:
                url = photo.get("url")
                thumb_url = photo.get("thumb_url")
                
                if not url or not url.startswith("https://res.cloudinary.com/"):
                    log_test("Test 4: Verify photos CDN URLs", False, f"Invalid url for photo {photo.get('photo_id')}: {url}")
                    all_valid = False
                    break
                
                if not thumb_url or not thumb_url.startswith("https://res.cloudinary.com/"):
                    log_test("Test 4: Verify photos CDN URLs", False, f"Invalid thumb_url for photo {photo.get('photo_id')}: {thumb_url}")
                    all_valid = False
                    break
            
            if all_valid:
                log_test("Test 4: Verify photos CDN URLs", True, f"All {len(items)} photos have valid Cloudinary CDN URLs")
                return True
            return False
        else:
            log_test("Test 4: Verify photos CDN URLs", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 4: Verify photos CDN URLs", False, f"Exception: {str(e)}")
        return False

def test_5_archive_event(admin_token, event_id):
    """Test 5: Archive event"""
    print(f"\n=== Test 5: Archive Event {event_id} ===")
    try:
        response = requests.post(
            f"{BASE_URL}/events/{event_id}/archive",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            
            if status != "archived":
                log_test("Test 5: Archive event", False, f"Expected status='archived', got '{status}'")
                return False
            
            log_test("Test 5: Archive event", True, f"status={status}")
            return True
        else:
            log_test("Test 5: Archive event", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 5: Archive event", False, f"Exception: {str(e)}")
        return False

def test_6_public_event_archived(event_id):
    """Test 6: GET /api/public/events/{id} should return 403 with archived message"""
    print(f"\n=== Test 6: Public Event Info (Archived) ===")
    try:
        response = requests.get(
            f"{BASE_URL}/public/events/{event_id}",
            timeout=10
        )
        if response.status_code == 403:
            data = response.json()
            detail = data.get("detail", "")
            
            if detail != ARCHIVED_MESSAGE:
                log_test("Test 6: Public event (archived)", False, f"Expected message: '{ARCHIVED_MESSAGE}', got: '{detail}'")
                return False
            
            log_test("Test 6: Public event (archived)", True, f"Got 403 with correct message")
            return True
        else:
            log_test("Test 6: Public event (archived)", False, f"Expected 403, got {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 6: Public event (archived)", False, f"Exception: {str(e)}")
        return False

def test_7_public_access_archived(event_id):
    """Test 7: POST /api/public/events/{id}/access should return 403 with archived message"""
    print(f"\n=== Test 7: Public Access (Archived) ===")
    try:
        response = requests.post(
            f"{BASE_URL}/public/events/{event_id}/access",
            json={"name": "Guest", "phone": "+91 90000 00002"},
            timeout=10
        )
        if response.status_code == 403:
            data = response.json()
            detail = data.get("detail", "")
            
            if detail != ARCHIVED_MESSAGE:
                log_test("Test 7: Public access (archived)", False, f"Expected message: '{ARCHIVED_MESSAGE}', got: '{detail}'")
                return False
            
            log_test("Test 7: Public access (archived)", True, f"Got 403 with correct message")
            return True
        else:
            log_test("Test 7: Public access (archived)", False, f"Expected 403, got {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 7: Public access (archived)", False, f"Exception: {str(e)}")
        return False

def test_8_unarchive_event(admin_token, event_id):
    """Test 8: Unarchive event"""
    print(f"\n=== Test 8: Unarchive Event {event_id} ===")
    try:
        response = requests.post(
            f"{BASE_URL}/events/{event_id}/unarchive",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            
            if status != "active":
                log_test("Test 8: Unarchive event", False, f"Expected status='active', got '{status}'")
                return False
            
            log_test("Test 8: Unarchive event", True, f"status={status}")
            return True
        else:
            log_test("Test 8: Unarchive event", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 8: Unarchive event", False, f"Exception: {str(e)}")
        return False

def test_9_public_event_active(event_id):
    """Test 9: GET /api/public/events/{id} should return 200 after unarchive"""
    print(f"\n=== Test 9: Public Event Info (Active) ===")
    try:
        response = requests.get(
            f"{BASE_URL}/public/events/{event_id}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            event_name = data.get("name")
            log_test("Test 9: Public event (active)", True, f"Got 200, event_name={event_name}")
            return True
        else:
            log_test("Test 9: Public event (active)", False, f"Expected 200, got {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 9: Public event (active)", False, f"Exception: {str(e)}")
        return False

def test_10_delete_event(admin_token, event_id, expected_photos=2):
    """Test 10: DELETE event - permanent deletion"""
    print(f"\n=== Test 10: Delete Event {event_id} (PERMANENT) ===")
    try:
        response = requests.delete(
            f"{BASE_URL}/events/{event_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            photos_removed = data.get("photos_removed")
            cloudinary_objects_deleted = data.get("cloudinary_objects_deleted")
            faces_collection_deleted = data.get("faces_collection_deleted")
            
            issues = []
            
            if status != "deleted":
                issues.append(f"Expected status='deleted', got '{status}'")
            
            if photos_removed != expected_photos:
                issues.append(f"Expected photos_removed={expected_photos}, got {photos_removed}")
            
            # Should be at least 2 photos * 2 (original + thumb) = 4
            if cloudinary_objects_deleted < expected_photos * 2:
                issues.append(f"Expected cloudinary_objects_deleted>={expected_photos * 2}, got {cloudinary_objects_deleted}")
            
            if faces_collection_deleted != True:
                issues.append(f"Expected faces_collection_deleted=True, got {faces_collection_deleted}")
            
            if issues:
                log_test("Test 10: Delete event", False, "; ".join(issues))
                return False
            
            log_test(
                "Test 10: Delete event", 
                True, 
                f"status={status}, photos_removed={photos_removed}, cloudinary_objects_deleted={cloudinary_objects_deleted}, faces_collection_deleted={faces_collection_deleted}"
            )
            return True
        else:
            log_test("Test 10: Delete event", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 10: Delete event", False, f"Exception: {str(e)}")
        return False

def test_11_get_deleted_event(admin_token, event_id):
    """Test 11: GET deleted event should return 404"""
    print(f"\n=== Test 11: GET Deleted Event (404) ===")
    try:
        response = requests.get(
            f"{BASE_URL}/events/{event_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 404:
            log_test("Test 11: GET deleted event", True, "Got 404 as expected")
            return True
        else:
            log_test("Test 11: GET deleted event", False, f"Expected 404, got {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 11: GET deleted event", False, f"Exception: {str(e)}")
        return False

def test_12_delete_again_idempotency(admin_token, event_id):
    """Test 12: DELETE again (idempotency) should return 404"""
    print(f"\n=== Test 12: DELETE Again (Idempotency - 404) ===")
    try:
        response = requests.delete(
            f"{BASE_URL}/events/{event_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 404:
            log_test("Test 12: DELETE again (idempotency)", True, "Got 404 as expected")
            return True
        else:
            log_test("Test 12: DELETE again (idempotency)", False, f"Expected 404, got {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 12: DELETE again (idempotency)", False, f"Exception: {str(e)}")
        return False

def test_13_auth_edge_cases(admin_token):
    """Test 13: Auth/permission edge cases"""
    print("\n=== Test 13: Auth/Permission Edge Cases ===")
    
    # Create another throwaway event for edge case testing
    print("\n  Creating another event for edge case tests...")
    event_id = test_1_create_event(admin_token)
    if not event_id:
        log_test("Test 13: Setup event for edge cases", False, "Failed to create event")
        return None
    
    # Test 13a: Archive without Authorization header -> 401
    try:
        response = requests.post(
            f"{BASE_URL}/events/{event_id}/archive",
            timeout=10
        )
        if response.status_code == 401:
            log_test("Test 13a: Archive without auth", True, "Got 401 as expected")
        else:
            log_test("Test 13a: Archive without auth", False, f"Expected 401, got {response.status_code}")
    except Exception as e:
        log_test("Test 13a: Archive without auth", False, f"Exception: {str(e)}")
    
    # Test 13b: Archive with CLIENT token -> 403
    # First, create a client token via public access
    try:
        response = requests.post(
            f"{BASE_URL}/public/events/{event_id}/access",
            json={"name": "C", "phone": "+91 90000 00003"},
            timeout=10
        )
        if response.status_code == 200:
            client_token = response.json().get("session_token")
            if client_token:
                # Try to archive with client token
                response2 = requests.post(
                    f"{BASE_URL}/events/{event_id}/archive",
                    headers={"Authorization": f"Bearer {client_token}"},
                    timeout=10
                )
                if response2.status_code == 403:
                    log_test("Test 13b: Archive with client token", True, "Got 403 as expected")
                else:
                    log_test("Test 13b: Archive with client token", False, f"Expected 403, got {response2.status_code}")
            else:
                log_test("Test 13b: Archive with client token", False, "Failed to get client token")
        else:
            log_test("Test 13b: Archive with client token", False, f"Failed to create client: {response.status_code}")
    except Exception as e:
        log_test("Test 13b: Archive with client token", False, f"Exception: {str(e)}")
    
    # Test 13c: DELETE non-existent event -> 404
    try:
        response = requests.delete(
            f"{BASE_URL}/events/evt_nonexistent123",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 404:
            log_test("Test 13c: DELETE non-existent event", True, "Got 404 as expected")
        else:
            log_test("Test 13c: DELETE non-existent event", False, f"Expected 404, got {response.status_code}")
    except Exception as e:
        log_test("Test 13c: DELETE non-existent event", False, f"Exception: {str(e)}")
    
    # Clean up: delete the edge case test event
    print(f"\n  Cleaning up edge case test event {event_id}...")
    requests.delete(
        f"{BASE_URL}/events/{event_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=30
    )
    
    return event_id

def test_14_regression_client_access(admin_token):
    """Test 14: Regression - normal active event allows client access"""
    print("\n=== Test 14: Regression - Client Access to Active Event ===")
    
    # Create a normal active event
    event_id = test_1_create_event(admin_token)
    if not event_id:
        log_test("Test 14: Setup regression event", False, "Failed to create event")
        return False
    
    try:
        # Create a client via public access
        response = requests.post(
            f"{BASE_URL}/public/events/{event_id}/access",
            json={"name": "Regression Tester", "phone": "+91 90000 00004"},
            timeout=10
        )
        if response.status_code != 200:
            log_test("Test 14: Regression client access", False, f"Failed to create client: {response.status_code}")
            return False
        
        client_token = response.json().get("session_token")
        if not client_token:
            log_test("Test 14: Regression client access", False, "No client token received")
            return False
        
        # Try to access photos with client token
        response2 = requests.get(
            f"{BASE_URL}/client/events/{event_id}/photos",
            headers={"Authorization": f"Bearer {client_token}"},
            timeout=10
        )
        
        if response2.status_code == 200:
            log_test("Test 14: Regression client access", True, "Client can access active event photos")
            success = True
        else:
            log_test("Test 14: Regression client access", False, f"Expected 200, got {response2.status_code}: {response2.text}")
            success = False
        
        # Clean up
        print(f"\n  Cleaning up regression test event {event_id}...")
        requests.delete(
            f"{BASE_URL}/events/{event_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=30
        )
        
        return success
        
    except Exception as e:
        log_test("Test 14: Regression client access", False, f"Exception: {str(e)}")
        return False

def main():
    print("=" * 80)
    print("LUMIERE GALLERY - BACKEND API TESTS (Gallery Lifecycle Feature)")
    print("Archive / Unarchive / Delete with Cloudinary + Rekognition Cleanup")
    print("=" * 80)
    
    # Setup: Admin login
    admin_token = test_admin_login()
    if not admin_token:
        print("\n❌ CRITICAL: Admin login failed. Cannot continue tests.")
        sys.exit(1)
    
    # Test 1: Create throwaway event
    event_id = test_1_create_event(admin_token)
    if not event_id:
        print("\n❌ CRITICAL: Failed to create event. Cannot continue tests.")
        sys.exit(1)
    
    # Test 2: Upload 2 photos
    photo_ids = test_2_upload_photos(admin_token, event_id)
    if len(photo_ids) < 2:
        print(f"\n⚠️  WARNING: Only uploaded {len(photo_ids)} photos. Expected 2.")
    
    # Test 3: Verify cover_url
    test_3_verify_cover_url(admin_token, event_id)
    
    # Test 4: Verify photos CDN URLs
    test_4_verify_photos_cdn_urls(admin_token, event_id)
    
    # Test 5: Archive event
    test_5_archive_event(admin_token, event_id)
    
    # Test 6: Public event info (archived) -> 403
    test_6_public_event_archived(event_id)
    
    # Test 7: Public access (archived) -> 403
    test_7_public_access_archived(event_id)
    
    # Test 8: Unarchive event
    test_8_unarchive_event(admin_token, event_id)
    
    # Test 9: Public event info (active) -> 200
    test_9_public_event_active(event_id)
    
    # Test 10: Delete event (permanent)
    test_10_delete_event(admin_token, event_id, expected_photos=len(photo_ids))
    
    # Test 11: GET deleted event -> 404
    test_11_get_deleted_event(admin_token, event_id)
    
    # Test 12: DELETE again (idempotency) -> 404
    test_12_delete_again_idempotency(admin_token, event_id)
    
    # Test 13: Auth/permission edge cases
    test_13_auth_edge_cases(admin_token)
    
    # Test 14: Regression - client access to active event
    test_14_regression_client_access(admin_token)
    
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
    
    if tests_failed > 0:
        print(f"\n❌ {tests_failed} TEST(S) FAILED")
        sys.exit(1)
    else:
        print("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)

if __name__ == "__main__":
    main()
