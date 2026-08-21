#!/usr/bin/env python3
"""
Backend Recovery Test - PIK Connect / Lumiere Gallery
Tests the recovered backend with EMERGENT storage + MOCK face engine
"""

import requests
import time
import io
from PIL import Image

# Base URL from frontend/.env
BASE_URL = "https://ee967415-f047-4a40-8d67-74f8dbe106f0.preview.emergentagent.com/api"

# Admin credentials
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

# Test results
results = []

def log_test(step, status, details=""):
    """Log test result"""
    symbol = "✅" if status == "PASS" else "❌"
    results.append({"step": step, "status": status, "details": details})
    print(f"{symbol} Step {step}: {status}")
    if details:
        print(f"   {details}")

def create_test_image():
    """Create a small test JPEG image"""
    img = Image.new('RGB', (100, 100), color='red')
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return buf

# Test execution
print("=" * 80)
print("BACKEND RECOVERY TEST - PIK Connect / Lumiere Gallery")
print("Testing: EMERGENT storage + MOCK face engine")
print("=" * 80)
print()

try:
    # Step 1: Health check
    print("Step 1: GET /api/ (health check)")
    resp = requests.get(f"{BASE_URL}/", timeout=10)
    if resp.status_code == 200 and resp.json().get("status") == "ok":
        log_test(1, "PASS", f"Status: {resp.status_code}, Response: {resp.json()}")
    else:
        log_test(1, "FAIL", f"Status: {resp.status_code}, Response: {resp.text}")
        raise Exception("Health check failed")

    # Step 2: Admin login
    print("\nStep 2: POST /api/auth/admin/login")
    resp = requests.post(
        f"{BASE_URL}/auth/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=10
    )
    if resp.status_code == 200 and "session_token" in resp.json():
        admin_token = resp.json()["session_token"]
        log_test(2, "PASS", f"Status: {resp.status_code}, Got session_token")
    else:
        log_test(2, "FAIL", f"Status: {resp.status_code}, Response: {resp.text}")
        raise Exception("Admin login failed")

    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Step 3: Create event
    print("\nStep 3: POST /api/events (create event)")
    resp = requests.post(
        f"{BASE_URL}/events",
        json={"name": "QA Recovery", "category": "event"},
        headers=admin_headers,
        timeout=10
    )
    if resp.status_code == 200 and "event_id" in resp.json():
        event_id = resp.json()["event_id"]
        log_test(3, "PASS", f"Status: {resp.status_code}, event_id: {event_id}")
    else:
        log_test(3, "FAIL", f"Status: {resp.status_code}, Response: {resp.text}")
        raise Exception("Create event failed")

    # Step 4: Upload photo
    print("\nStep 4: POST /api/events/{event_id}/photos (upload photo)")
    test_image = create_test_image()
    files = {"file": ("test.jpg", test_image, "image/jpeg")}
    resp = requests.post(
        f"{BASE_URL}/events/{event_id}/photos",
        files=files,
        headers=admin_headers,
        timeout=30
    )
    if resp.status_code == 200 and "photo_id" in resp.json():
        photo_data = resp.json()
        photo_id = photo_data["photo_id"]
        storage_path = photo_data.get("storage_path", "")
        thumb_path = photo_data.get("thumb_path", "")
        photo_url = photo_data.get("url", "")
        thumb_url = photo_data.get("thumb_url", "")
        log_test(4, "PASS", f"Status: {resp.status_code}, photo_id: {photo_id}")
        print(f"   Storage path: {storage_path}")
        print(f"   Thumb path: {thumb_path}")
        print(f"   Photo URL: {photo_url} (None = uses /api/files proxy)")
        print(f"   Thumb URL: {thumb_url} (None = uses /api/files proxy)")
        
        # Validate Emergent storage serving via /api/files proxy
        if storage_path:
            print(f"   Validating Emergent storage via /api/files/{storage_path}...")
            photo_resp = requests.get(f"{BASE_URL}/files/{storage_path}", headers=admin_headers, timeout=10)
            if photo_resp.status_code == 200 and photo_resp.headers.get('content-type', '').startswith('image'):
                log_test("4a", "PASS", f"Emergent storage serving: {photo_resp.status_code}, {len(photo_resp.content)} bytes, {photo_resp.headers.get('content-type')}")
            else:
                log_test("4a", "FAIL", f"Emergent storage serving failed: {photo_resp.status_code}")
        else:
            log_test("4a", "FAIL", "No storage_path in photo response")
    else:
        log_test(4, "FAIL", f"Status: {resp.status_code}, Response: {resp.text}")
        raise Exception("Upload photo failed")

    # Step 5: Check indexing status (poll until complete)
    print("\nStep 5: GET /api/events/{event_id}/indexing-status (poll until complete)")
    max_polls = 10
    poll_count = 0
    indexing_complete = False
    
    while poll_count < max_polls:
        resp = requests.get(
            f"{BASE_URL}/events/{event_id}/indexing-status",
            headers=admin_headers,
            timeout=10
        )
        if resp.status_code == 200:
            status_data = resp.json()
            complete = status_data.get("complete", False)
            status = status_data.get("status", "")
            indexed = status_data.get("indexed_photos", 0)
            total = status_data.get("total_photos", 0)
            faces = status_data.get("total_faces", 0)
            
            print(f"   Poll {poll_count + 1}: status={status}, indexed={indexed}/{total}, faces={faces}, complete={complete}")
            
            if complete:
                indexing_complete = True
                log_test(5, "PASS", f"Indexing complete: {indexed}/{total} indexed, {faces} faces detected (mock engine)")
                break
        else:
            print(f"   Poll {poll_count + 1} failed: {resp.status_code}")
        
        poll_count += 1
        time.sleep(1)
    
    if not indexing_complete:
        log_test(5, "FAIL", f"Indexing did not complete after {max_polls} polls")

    # Step 6: List photos
    print("\nStep 6: GET /api/events/{event_id}/photos (list photos)")
    resp = requests.get(
        f"{BASE_URL}/events/{event_id}/photos",
        headers=admin_headers,
        timeout=10
    )
    if resp.status_code == 200:
        photos_data = resp.json()
        # Handle both envelope format and direct array
        if isinstance(photos_data, dict) and "items" in photos_data:
            photos = photos_data["items"]
            total = photos_data.get("total", len(photos))
        else:
            photos = photos_data if isinstance(photos_data, list) else []
            total = len(photos)
        
        log_test(6, "PASS", f"Status: {resp.status_code}, {total} photo(s) listed")
        if photos:
            print(f"   First photo: {photos[0].get('photo_id', 'N/A')}")
    else:
        log_test(6, "FAIL", f"Status: {resp.status_code}, Response: {resp.text}")

    # Step 7: Client OTP flow
    print("\nStep 7a: POST /api/auth/client/request-otp (request OTP)")
    test_phone = "+919000000001"
    resp = requests.post(
        f"{BASE_URL}/auth/client/request-otp",
        json={"channel": "phone", "phone": test_phone},
        timeout=10
    )
    if resp.status_code == 200:
        otp_data = resp.json()
        dev_code = otp_data.get("dev_code", "")
        if dev_code:
            log_test("7a", "PASS", f"Status: {resp.status_code}, dev_code: {dev_code}")
            
            # Step 7b: Verify OTP
            print("\nStep 7b: POST /api/auth/client/verify-otp (verify OTP)")
            resp = requests.post(
                f"{BASE_URL}/auth/client/verify-otp",
                json={"channel": "phone", "phone": test_phone, "code": dev_code},
                timeout=10
            )
            if resp.status_code == 200 and "session_token" in resp.json():
                client_token = resp.json()["session_token"]
                log_test("7b", "PASS", f"Status: {resp.status_code}, Got client session_token")
            else:
                log_test("7b", "FAIL", f"Status: {resp.status_code}, Response: {resp.text}")
        else:
            log_test("7a", "FAIL", f"Status: {resp.status_code}, No dev_code in response")
    else:
        log_test("7a", "FAIL", f"Status: {resp.status_code}, Response: {resp.text}")

    # Step 8: Public access flow
    print("\nStep 8a: POST /api/public/events/{event_id}/access (public access)")
    resp = requests.post(
        f"{BASE_URL}/public/events/{event_id}/access",
        json={"name": "QA Guest", "phone": "+919000000002"},
        timeout=10
    )
    if resp.status_code == 200 and "session_token" in resp.json():
        public_token = resp.json()["session_token"]
        log_test("8a", "PASS", f"Status: {resp.status_code}, Got public session_token")
        
        # Step 8b: Get photos with public token
        print("\nStep 8b: GET /api/client/events/{event_id}/photos (with public token)")
        public_headers = {"Authorization": f"Bearer {public_token}"}
        resp = requests.get(
            f"{BASE_URL}/client/events/{event_id}/photos",
            headers=public_headers,
            timeout=10
        )
        if resp.status_code == 200:
            photos_data = resp.json()
            # Handle both envelope format and direct array
            if isinstance(photos_data, dict) and "items" in photos_data:
                photos = photos_data["items"]
                total = photos_data.get("total", len(photos))
            else:
                photos = photos_data if isinstance(photos_data, list) else []
                total = len(photos)
            
            log_test("8b", "PASS", f"Status: {resp.status_code}, {total} photo(s) accessible")
        else:
            log_test("8b", "FAIL", f"Status: {resp.status_code}, Response: {resp.text}")
    else:
        log_test("8a", "FAIL", f"Status: {resp.status_code}, Response: {resp.text}")

    # Step 9: Delete event (cleanup)
    print("\nStep 9: DELETE /api/events/{event_id} (cleanup)")
    resp = requests.delete(
        f"{BASE_URL}/events/{event_id}",
        headers=admin_headers,
        timeout=10
    )
    if resp.status_code == 200:
        cleanup_data = resp.json()
        log_test(9, "PASS", f"Status: {resp.status_code}, Cleanup: {cleanup_data}")
        
        # Verify deletion
        print("\nStep 9b: GET /api/events/{event_id} (verify deletion)")
        resp = requests.get(
            f"{BASE_URL}/events/{event_id}",
            headers=admin_headers,
            timeout=10
        )
        if resp.status_code == 404:
            log_test("9b", "PASS", f"Status: {resp.status_code}, Event deleted successfully")
        else:
            log_test("9b", "FAIL", f"Status: {resp.status_code}, Event still exists")
    else:
        log_test(9, "FAIL", f"Status: {resp.status_code}, Response: {resp.text}")

except Exception as e:
    print(f"\n❌ Test execution failed: {e}")
    import traceback
    traceback.print_exc()

# Summary
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)

passed = sum(1 for r in results if r["status"] == "PASS")
failed = sum(1 for r in results if r["status"] == "FAIL")
total = len(results)

print(f"\nTotal: {total} tests")
print(f"✅ Passed: {passed}")
print(f"❌ Failed: {failed}")

if failed == 0:
    print("\n🎉 ALL TESTS PASSED - Backend recovery successful!")
else:
    print(f"\n⚠️  {failed} test(s) failed - see details above")

print("\nDetailed Results:")
for r in results:
    symbol = "✅" if r["status"] == "PASS" else "❌"
    print(f"{symbol} Step {r['step']}: {r['status']}")
    if r["details"]:
        print(f"   {r['details']}")
