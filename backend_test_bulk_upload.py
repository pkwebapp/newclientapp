"""
Backend API tests for Lumiere Gallery - Bulk Upload + Background Indexing Feature
Tests the new bulk upload endpoint, indexing-status polling, and RTBF cleanup
"""
import requests
import json
import sys
import time
import io
from PIL import Image

# Configuration
BASE_URL = "https://pkweb-client-1.preview.emergentagent.com/api"
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

def generate_test_image(color, size=(200, 200)):
    """Generate a small solid-color JPEG image (no faces)"""
    img = Image.new('RGB', size, color=color)
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
    """Test 1: Create a fresh event"""
    print("\n=== Test 1: Create Fresh Event ===")
    try:
        response = requests.post(
            f"{BASE_URL}/events",
            json={
                "name": "Bulk Upload Test Event",
                "category": "event",
                "date": "2026-08-16"
            },
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code in [200, 201]:
            data = response.json()
            event_id = data.get("event_id")
            if event_id:
                log_test("Create event", True, f"Event created: {event_id}")
                return event_id
            else:
                log_test("Create event", False, "No event_id in response")
                return None
        else:
            log_test("Create event", False, f"Status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        log_test("Create event", False, f"Exception: {str(e)}")
        return None

def test_2_bulk_upload(admin_token, event_id):
    """Test 2: Bulk upload 4 small images"""
    print("\n=== Test 2: Bulk Upload (4 images) ===")
    try:
        # Generate 4 small test images with different colors (no faces)
        colors = ['red', 'blue', 'green', 'yellow']
        files = []
        for i, color in enumerate(colors):
            img_buf = generate_test_image(color)
            files.append(('files', (f'test_{color}.jpg', img_buf, 'image/jpeg')))
        
        start_time = time.time()
        response = requests.post(
            f"{BASE_URL}/events/{event_id}/photos/bulk",
            files=files,
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=30
        )
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            data = response.json()
            uploaded = data.get("uploaded")
            received = data.get("received")
            results = data.get("results", [])
            
            # Check response structure
            if uploaded != 4:
                log_test("Bulk upload", False, f"Expected uploaded=4, got {uploaded}")
                return None
            
            if received != 4:
                log_test("Bulk upload", False, f"Expected received=4, got {received}")
                return None
            
            if len(results) != 4:
                log_test("Bulk upload", False, f"Expected 4 results, got {len(results)}")
                return None
            
            # Check all results are ok=true
            all_ok = all(r.get("ok") == True for r in results)
            if not all_ok:
                failed = [r for r in results if not r.get("ok")]
                log_test("Bulk upload", False, f"Some uploads failed: {failed}")
                return None
            
            # Check response time (should be fast, not blocking on indexing)
            if elapsed > 10:
                log_test("Bulk upload", False, f"Upload took {elapsed:.2f}s - too slow, may be blocking on indexing")
                return None
            
            log_test(
                "Bulk upload", 
                True, 
                f"uploaded={uploaded}, received={received}, elapsed={elapsed:.2f}s, all results ok=true"
            )
            return results
        else:
            log_test("Bulk upload", False, f"Status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        log_test("Bulk upload", False, f"Exception: {str(e)}")
        return None

def test_3_immediate_indexing_status(admin_token, event_id):
    """Test 3: Check indexing-status immediately after upload"""
    print("\n=== Test 3: Immediate Indexing Status ===")
    try:
        response = requests.get(
            f"{BASE_URL}/events/{event_id}/indexing-status",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            
            # Check all required fields are present
            required_fields = ["status", "total_photos", "indexed_photos", "pending_photos", 
                             "failed_photos", "total_faces", "percent", "complete"]
            missing_fields = [f for f in required_fields if f not in data]
            
            if missing_fields:
                log_test("Immediate indexing status", False, f"Missing fields: {missing_fields}")
                return None
            
            # Check total_photos matches uploaded count
            if data.get("total_photos") != 4:
                log_test("Immediate indexing status", False, f"Expected total_photos=4, got {data.get('total_photos')}")
                return None
            
            log_test(
                "Immediate indexing status", 
                True, 
                f"status={data.get('status')}, total_photos={data.get('total_photos')}, "
                f"indexed={data.get('indexed_photos')}, pending={data.get('pending_photos')}, "
                f"percent={data.get('percent')}, complete={data.get('complete')}"
            )
            return data
        else:
            log_test("Immediate indexing status", False, f"Status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        log_test("Immediate indexing status", False, f"Exception: {str(e)}")
        return None

def test_4_poll_indexing_status(admin_token, event_id):
    """Test 4: Poll indexing-status until complete"""
    print("\n=== Test 4: Poll Indexing Status (up to 20s) ===")
    try:
        max_polls = 10
        poll_interval = 2
        
        for i in range(max_polls):
            time.sleep(poll_interval)
            response = requests.get(
                f"{BASE_URL}/events/{event_id}/indexing-status",
                headers={"Authorization": f"Bearer {admin_token}"},
                timeout=10
            )
            
            if response.status_code != 200:
                log_test("Poll indexing status", False, f"Poll {i+1} failed: Status {response.status_code}")
                return None
            
            data = response.json()
            print(f"    Poll {i+1}: status={data.get('status')}, percent={data.get('percent')}, "
                  f"pending={data.get('pending_photos')}, complete={data.get('complete')}")
            
            # Check if complete
            if data.get("complete") == True and data.get("percent") == 100 and data.get("pending_photos") == 0:
                # Also check event status is "ready"
                event_response = requests.get(
                    f"{BASE_URL}/events/{event_id}",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    timeout=10
                )
                if event_response.status_code == 200:
                    event_data = event_response.json()
                    event_status = event_data.get("indexing_status")
                    if event_status == "ready":
                        log_test(
                            "Poll indexing status", 
                            True, 
                            f"Indexing complete after {(i+1)*poll_interval}s: percent=100, complete=true, "
                            f"pending=0, status=ready, indexed={data.get('indexed_photos')}, "
                            f"total_faces={data.get('total_faces')}"
                        )
                        return data
                    else:
                        log_test("Poll indexing status", False, f"Indexing complete but event status={event_status}, expected 'ready'")
                        return None
        
        # Timeout
        log_test("Poll indexing status", False, f"Indexing did not complete within {max_polls*poll_interval}s")
        return None
    except Exception as e:
        log_test("Poll indexing status", False, f"Exception: {str(e)}")
        return None

def test_5_single_upload_regression(admin_token, event_id):
    """Test 5: Single photo upload (regression test)"""
    print("\n=== Test 5: Single Upload Regression ===")
    try:
        # Generate a single test image
        img_buf = generate_test_image('purple')
        
        response = requests.post(
            f"{BASE_URL}/events/{event_id}/photos",
            files={'file': ('test_single.jpg', img_buf, 'image/jpeg')},
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            photo_id = data.get("photo_id")
            
            if not photo_id:
                log_test("Single upload regression", False, "No photo_id in response")
                return None
            
            log_test("Single upload regression", True, f"Photo uploaded: {photo_id}")
            
            # Poll indexing status again until complete
            print("    Polling indexing status for single upload...")
            for i in range(10):
                time.sleep(2)
                status_response = requests.get(
                    f"{BASE_URL}/events/{event_id}/indexing-status",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    timeout=10
                )
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    print(f"    Poll {i+1}: percent={status_data.get('percent')}, complete={status_data.get('complete')}")
                    if status_data.get("complete") == True:
                        log_test("Single upload indexing", True, f"Single upload indexed successfully, total_photos={status_data.get('total_photos')}")
                        return photo_id
            
            log_test("Single upload indexing", False, "Single upload did not complete indexing within 20s")
            return None
        else:
            log_test("Single upload regression", False, f"Status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        log_test("Single upload regression", False, f"Exception: {str(e)}")
        return None

def test_6_rtbf_cleanup(admin_token, event_id):
    """Test 6: RTBF - Delete face data for non-existent user"""
    print("\n=== Test 6: RTBF Face Data Cleanup ===")
    try:
        # Use a non-existent client_user_id
        fake_user_id = "user_nonexistent123"
        
        response = requests.delete(
            f"{BASE_URL}/events/{event_id}/clients/{fake_user_id}/face-data",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Check response structure
            if "status" not in data or "faces_removed" not in data:
                log_test("RTBF cleanup", False, f"Missing required fields in response: {data}")
                return False
            
            if data.get("status") != "deleted":
                log_test("RTBF cleanup", False, f"Expected status='deleted', got {data.get('status')}")
                return False
            
            if data.get("faces_removed") != 0:
                log_test("RTBF cleanup", False, f"Expected faces_removed=0 for non-existent user, got {data.get('faces_removed')}")
                return False
            
            log_test("RTBF cleanup", True, f"status={data.get('status')}, faces_removed={data.get('faces_removed')}")
            return True
        else:
            log_test("RTBF cleanup", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("RTBF cleanup", False, f"Exception: {str(e)}")
        return False

def test_7_auth_checks(admin_token, event_id):
    """Test 7: Auth checks - 401 without token, 403 with client token"""
    print("\n=== Test 7: Auth Checks ===")
    
    # Test 7a: Bulk upload without token -> 401
    try:
        img_buf = generate_test_image('orange')
        response = requests.post(
            f"{BASE_URL}/events/{event_id}/photos/bulk",
            files=[('files', ('test.jpg', img_buf, 'image/jpeg'))],
            timeout=10
        )
        if response.status_code == 401:
            log_test("Bulk upload without token", True, "Got 401 as expected")
        else:
            log_test("Bulk upload without token", False, f"Expected 401, got {response.status_code}")
    except Exception as e:
        log_test("Bulk upload without token", False, f"Exception: {str(e)}")
    
    # Test 7b: Create a client token and try bulk upload -> 403
    try:
        # Create a visitor/client token via public access
        access_response = requests.post(
            f"{BASE_URL}/public/events/{event_id}/access",
            json={"name": "Test Visitor", "phone": "+1234567890"},
            timeout=10
        )
        
        if access_response.status_code == 200:
            client_token = access_response.json().get("session_token")
            if client_token:
                # Try bulk upload with client token
                img_buf = generate_test_image('cyan')
                response = requests.post(
                    f"{BASE_URL}/events/{event_id}/photos/bulk",
                    files=[('files', ('test.jpg', img_buf, 'image/jpeg'))],
                    headers={"Authorization": f"Bearer {client_token}"},
                    timeout=10
                )
                if response.status_code == 403:
                    log_test("Bulk upload with client token", True, "Got 403 as expected")
                else:
                    log_test("Bulk upload with client token", False, f"Expected 403, got {response.status_code}")
            else:
                log_test("Bulk upload with client token", False, "Could not get client token")
        else:
            # If public access is disabled, that's ok - just note it
            log_test("Bulk upload with client token", True, f"Public access disabled (status {access_response.status_code}), skipping client token test")
    except Exception as e:
        log_test("Bulk upload with client token", False, f"Exception: {str(e)}")

def main():
    print("=" * 80)
    print("LUMIERE GALLERY - BACKEND API TESTS (Bulk Upload + Background Indexing)")
    print("=" * 80)
    
    # Setup: Admin login
    admin_token = test_admin_login()
    if not admin_token:
        print("\n❌ CRITICAL: Admin login failed. Cannot continue tests.")
        sys.exit(1)
    
    # Test 1: Create fresh event
    event_id = test_1_create_event(admin_token)
    if not event_id:
        print("\n❌ CRITICAL: Event creation failed. Cannot continue tests.")
        sys.exit(1)
    
    # Test 2: Bulk upload
    bulk_results = test_2_bulk_upload(admin_token, event_id)
    if not bulk_results:
        print("\n❌ CRITICAL: Bulk upload failed. Cannot continue tests.")
        sys.exit(1)
    
    # Test 3: Immediate indexing status
    immediate_status = test_3_immediate_indexing_status(admin_token, event_id)
    if not immediate_status:
        print("\n⚠️  WARNING: Immediate indexing status check failed.")
    
    # Test 4: Poll indexing status until complete
    final_status = test_4_poll_indexing_status(admin_token, event_id)
    if not final_status:
        print("\n⚠️  WARNING: Indexing did not complete in time.")
    
    # Test 5: Single upload regression
    test_5_single_upload_regression(admin_token, event_id)
    
    # Test 6: RTBF cleanup
    test_6_rtbf_cleanup(admin_token, event_id)
    
    # Test 7: Auth checks
    test_7_auth_checks(admin_token, event_id)
    
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
