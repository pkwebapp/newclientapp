#!/usr/bin/env python3
"""Backend API tests for Google Drive gallery feature - PIK Connect (Lumiere Gallery)"""
import time
import requests
import sys
from io import BytesIO
from PIL import Image

# Backend URL from frontend/.env
BASE_URL = "https://pkweb-staging.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

# Real public Google Drive folder for testing (contains ~12 images)
REAL_DRIVE_FOLDER = "https://drive.google.com/drive/folders/1ZXEhzbLRLU1giKKRJkjm8N04cO_JoYE2"

# Test counters
tests_passed = 0
tests_failed = 0
test_results = []


def log_test(name, passed, details=""):
    global tests_passed, tests_failed
    if passed:
        tests_passed += 1
        status = "✅ PASS"
    else:
        tests_failed += 1
        status = "❌ FAIL"
    message = f"{status}: {name}"
    if details:
        message += f" - {details}"
    print(message)
    test_results.append({"name": name, "passed": passed, "details": details})


def create_test_image():
    """Create a small synthetic test image for upload testing"""
    img = Image.new('RGB', (400, 300), color=(73, 109, 137))
    buf = BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return buf


print("=" * 80)
print("GOOGLE DRIVE GALLERY FEATURE - BACKEND API TESTS")
print("=" * 80)
print(f"Backend URL: {BASE_URL}")
print(f"Admin: {ADMIN_EMAIL}")
print(f"Real Drive folder: {REAL_DRIVE_FOLDER}")
print("=" * 80)
print()

# Store test data
admin_token = None
gdrive_event_id = None
normal_event_id = None
photo_file_id = None

# ============================================================================
# TEST 1: Admin Login
# ============================================================================
print("TEST 1: Admin login")
try:
    resp = requests.post(
        f"{BASE_URL}/auth/admin/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=30
    )
    if resp.status_code == 200:
        data = resp.json()
        admin_token = data.get("session_token")
        if admin_token:
            log_test("Admin login", True, f"Got session_token")
        else:
            log_test("Admin login", False, "No session_token in response")
    else:
        log_test("Admin login", False, f"Status {resp.status_code}: {resp.text[:200]}")
except Exception as e:
    log_test("Admin login", False, f"Exception: {e}")

if not admin_token:
    print("\n❌ CRITICAL: Cannot proceed without admin token")
    sys.exit(1)

headers = {"Authorization": f"Bearer {admin_token}"}

# ============================================================================
# TEST 2: Create Google Drive event with real public folder
# ============================================================================
print("\nTEST 2: Create Google Drive event with real public folder")
try:
    resp = requests.post(
        f"{BASE_URL}/events/gdrive",
        headers=headers,
        json={
            "name": "Drive Test Gallery",
            "category": "wedding",
            "drive_link": REAL_DRIVE_FOLDER
        },
        timeout=60  # May take time to scan folder
    )
    if resp.status_code == 200:
        data = resp.json()
        gdrive_event_id = data.get("event_id")
        source = data.get("source")
        sync = data.get("sync", {})
        total = sync.get("total", 0)
        
        if source == "gdrive" and total > 0:
            log_test("Create GDrive event", True, 
                    f"event_id={gdrive_event_id}, source={source}, sync.total={total}")
        else:
            log_test("Create GDrive event", False, 
                    f"Expected source=gdrive and total>0, got source={source}, total={total}")
    else:
        log_test("Create GDrive event", False, f"Status {resp.status_code}: {resp.text[:300]}")
        gdrive_event_id = None
except Exception as e:
    log_test("Create GDrive event", False, f"Exception: {e}")
    gdrive_event_id = None

if not gdrive_event_id:
    print("\n❌ CRITICAL: Cannot proceed without gdrive event")
    sys.exit(1)

# ============================================================================
# TEST 3: Get event details - verify source and photo_count
# ============================================================================
print("\nTEST 3: Get event details")
try:
    resp = requests.get(
        f"{BASE_URL}/events/{gdrive_event_id}",
        headers=headers,
        timeout=30
    )
    if resp.status_code == 200:
        data = resp.json()
        source = data.get("source")
        photo_count = data.get("photo_count", 0)
        drive_folder_id = data.get("drive_folder_id")
        
        if source == "gdrive" and photo_count > 0:
            log_test("Get event details", True, 
                    f"source={source}, photo_count={photo_count}, drive_folder_id={drive_folder_id}")
        else:
            log_test("Get event details", False, 
                    f"Expected source=gdrive and photo_count>0, got source={source}, photo_count={photo_count}")
    else:
        log_test("Get event details", False, f"Status {resp.status_code}: {resp.text[:200]}")
except Exception as e:
    log_test("Get event details", False, f"Exception: {e}")

# ============================================================================
# TEST 4: Get photos - verify source=gdrive and absolute proxy URLs
# ============================================================================
print("\nTEST 4: Get photos from GDrive event")
try:
    resp = requests.get(
        f"{BASE_URL}/events/{gdrive_event_id}/photos",
        headers=headers,
        timeout=30
    )
    if resp.status_code == 200:
        data = resp.json()
        items = data.get("items", [])
        
        if len(items) > 0:
            photo = items[0]
            source = photo.get("source")
            drive_file_id = photo.get("drive_file_id")
            thumb_url = photo.get("thumb_url", "")
            url = photo.get("url", "")
            
            # Verify URLs contain /api/gdrive/thumb/{fileId}?w=
            thumb_ok = "/api/gdrive/thumb/" in thumb_url and "?w=" in thumb_url
            url_ok = "/api/gdrive/thumb/" in url and "?w=" in url
            
            if source == "gdrive" and drive_file_id and thumb_ok and url_ok:
                log_test("Get photos", True, 
                        f"Found {len(items)} photos, source=gdrive, drive_file_id={drive_file_id}, "
                        f"thumb_url has /api/gdrive/thumb/, url has /api/gdrive/thumb/")
                photo_file_id = drive_file_id  # Save for next test
            else:
                log_test("Get photos", False, 
                        f"source={source}, drive_file_id={drive_file_id}, "
                        f"thumb_url_ok={thumb_ok}, url_ok={url_ok}")
        else:
            log_test("Get photos", False, "No photos returned")
    else:
        log_test("Get photos", False, f"Status {resp.status_code}: {resp.text[:200]}")
except Exception as e:
    log_test("Get photos", False, f"Exception: {e}")

# ============================================================================
# TEST 5: GDrive thumb proxy - w=600
# ============================================================================
print("\nTEST 5: GDrive thumb proxy (w=600)")
if photo_file_id:
    try:
        resp = requests.get(
            f"{BASE_URL}/gdrive/thumb/{photo_file_id}?w=600",
            timeout=30
        )
        if resp.status_code == 200:
            content_type = resp.headers.get("content-type", "")
            content_length = len(resp.content)
            
            if content_type.startswith("image/") and content_length > 0:
                log_test("GDrive thumb proxy w=600", True, 
                        f"Status 200, content-type={content_type}, size={content_length} bytes")
            else:
                log_test("GDrive thumb proxy w=600", False, 
                        f"content-type={content_type}, size={content_length}")
        else:
            log_test("GDrive thumb proxy w=600", False, f"Status {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        log_test("GDrive thumb proxy w=600", False, f"Exception: {e}")
else:
    log_test("GDrive thumb proxy w=600", False, "No photo_file_id available")

# ============================================================================
# TEST 6: GDrive thumb proxy - w=1600
# ============================================================================
print("\nTEST 6: GDrive thumb proxy (w=1600)")
if photo_file_id:
    try:
        resp = requests.get(
            f"{BASE_URL}/gdrive/thumb/{photo_file_id}?w=1600",
            timeout=30
        )
        if resp.status_code == 200:
            content_type = resp.headers.get("content-type", "")
            content_length = len(resp.content)
            
            if content_type.startswith("image/") and content_length > 0:
                log_test("GDrive thumb proxy w=1600", True, 
                        f"Status 200, content-type={content_type}, size={content_length} bytes")
            else:
                log_test("GDrive thumb proxy w=1600", False, 
                        f"content-type={content_type}, size={content_length}")
        else:
            log_test("GDrive thumb proxy w=1600", False, f"Status {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        log_test("GDrive thumb proxy w=1600", False, f"Exception: {e}")
else:
    log_test("GDrive thumb proxy w=1600", False, "No photo_file_id available")

# ============================================================================
# TEST 7: Face indexing status - poll until complete
# ============================================================================
print("\nTEST 7: Face indexing status (polling until complete)")
try:
    max_wait = 60  # seconds
    start_time = time.time()
    complete = False
    last_status = None
    
    while time.time() - start_time < max_wait:
        resp = requests.get(
            f"{BASE_URL}/events/{gdrive_event_id}/indexing-status",
            headers=headers,
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            complete = data.get("complete", False)
            status = data.get("status")
            total_photos = data.get("total_photos", 0)
            indexed_photos = data.get("indexed_photos", 0)
            failed_photos = data.get("failed_photos", 0)
            total_faces = data.get("total_faces", 0)
            percent = data.get("percent", 0)
            
            last_status = data
            
            if complete:
                log_test("Face indexing complete", True, 
                        f"status={status}, total_photos={total_photos}, indexed={indexed_photos}, "
                        f"failed={failed_photos}, total_faces={total_faces}, percent={percent}%")
                break
        else:
            log_test("Face indexing status", False, f"Status {resp.status_code}: {resp.text[:200]}")
            break
        
        time.sleep(3)  # Poll every 3 seconds
    
    if not complete:
        log_test("Face indexing complete", False, 
                f"Timeout after {max_wait}s. Last status: {last_status}")
except Exception as e:
    log_test("Face indexing status", False, f"Exception: {e}")

# ============================================================================
# TEST 8: Sync - re-scan folder (should be idempotent)
# ============================================================================
print("\nTEST 8: Sync GDrive event (first sync)")
try:
    resp = requests.post(
        f"{BASE_URL}/events/{gdrive_event_id}/sync",
        headers=headers,
        timeout=60
    )
    if resp.status_code == 200:
        data = resp.json()
        sync = data.get("sync", {})
        added = sync.get("added", 0)
        updated = sync.get("updated", 0)
        removed = sync.get("removed", 0)
        total = sync.get("total", 0)
        
        log_test("Sync GDrive event", True, 
                f"added={added}, updated={updated}, removed={removed}, total={total}")
    else:
        log_test("Sync GDrive event", False, f"Status {resp.status_code}: {resp.text[:300]}")
except Exception as e:
    log_test("Sync GDrive event", False, f"Exception: {e}")

# ============================================================================
# TEST 9: Sync again immediately (should be idempotent - no changes)
# ============================================================================
print("\nTEST 9: Sync again immediately (idempotency check)")
try:
    resp = requests.post(
        f"{BASE_URL}/events/{gdrive_event_id}/sync",
        headers=headers,
        timeout=60
    )
    if resp.status_code == 200:
        data = resp.json()
        sync = data.get("sync", {})
        added = sync.get("added", 0)
        updated = sync.get("updated", 0)
        removed = sync.get("removed", 0)
        
        if added == 0 and removed == 0:
            log_test("Sync idempotency", True, 
                    f"added={added}, updated={updated}, removed={removed} (no changes as expected)")
        else:
            log_test("Sync idempotency", False, 
                    f"Expected added=0 and removed=0, got added={added}, removed={removed}")
    else:
        log_test("Sync idempotency", False, f"Status {resp.status_code}: {resp.text[:300]}")
except Exception as e:
    log_test("Sync idempotency", False, f"Exception: {e}")

# ============================================================================
# TEST 10: Negative test - invalid drive link
# ============================================================================
print("\nTEST 10: Negative test - invalid drive link")
try:
    resp = requests.post(
        f"{BASE_URL}/events/gdrive",
        headers=headers,
        json={
            "name": "Invalid Link Test",
            "category": "event",
            "drive_link": "not-a-valid-link"
        },
        timeout=30
    )
    if resp.status_code == 400:
        detail = resp.json().get("detail", "")
        log_test("Invalid drive link", True, f"Status 400 with detail: {detail}")
    else:
        log_test("Invalid drive link", False, 
                f"Expected 400, got {resp.status_code}: {resp.text[:200]}")
except Exception as e:
    log_test("Invalid drive link", False, f"Exception: {e}")

# ============================================================================
# TEST 11: Negative test - non-existent/private folder
# ============================================================================
print("\nTEST 11: Negative test - non-existent/private folder")
try:
    resp = requests.post(
        f"{BASE_URL}/events/gdrive",
        headers=headers,
        json={
            "name": "Private Folder Test",
            "category": "event",
            "drive_link": "https://drive.google.com/drive/folders/0B7EVK8r0v71pZjFTYXZWM3FlRnM"
        },
        timeout=30
    )
    if resp.status_code == 400:
        detail = resp.json().get("detail", "")
        log_test("Non-existent/private folder", True, f"Status 400 with detail: {detail}")
    else:
        log_test("Non-existent/private folder", False, 
                f"Expected 400, got {resp.status_code}: {resp.text[:200]}")
except Exception as e:
    log_test("Non-existent/private folder", False, f"Exception: {e}")

# ============================================================================
# TEST 12: Delete GDrive event
# ============================================================================
print("\nTEST 12: Delete GDrive event")
try:
    resp = requests.delete(
        f"{BASE_URL}/events/{gdrive_event_id}",
        headers=headers,
        timeout=30
    )
    if resp.status_code == 200:
        data = resp.json()
        status = data.get("status")
        photos_removed = data.get("photos_removed", 0)
        faces_collection_deleted = data.get("faces_collection_deleted", False)
        
        if status == "deleted":
            log_test("Delete GDrive event", True, 
                    f"status={status}, photos_removed={photos_removed}, "
                    f"faces_collection_deleted={faces_collection_deleted}")
        else:
            log_test("Delete GDrive event", False, f"Expected status=deleted, got {status}")
    else:
        log_test("Delete GDrive event", False, f"Status {resp.status_code}: {resp.text[:200]}")
except Exception as e:
    log_test("Delete GDrive event", False, f"Exception: {e}")

# ============================================================================
# TEST 13: Verify GDrive event is deleted
# ============================================================================
print("\nTEST 13: Verify GDrive event is deleted")
try:
    resp = requests.get(
        f"{BASE_URL}/events/{gdrive_event_id}",
        headers=headers,
        timeout=30
    )
    if resp.status_code == 404:
        log_test("Verify GDrive event deleted", True, "Status 404 (event not found)")
    else:
        log_test("Verify GDrive event deleted", False, 
                f"Expected 404, got {resp.status_code}")
except Exception as e:
    log_test("Verify GDrive event deleted", False, f"Exception: {e}")

# ============================================================================
# REGRESSION TEST: Normal upload flow still works
# ============================================================================
print("\n" + "=" * 80)
print("REGRESSION TEST: Normal upload flow (Cloudinary)")
print("=" * 80)

# ============================================================================
# TEST 14: Create normal event
# ============================================================================
print("\nTEST 14: Create normal event (non-GDrive)")
try:
    resp = requests.post(
        f"{BASE_URL}/events",
        headers=headers,
        json={
            "name": "Normal Upload Test",
            "category": "event"
        },
        timeout=30
    )
    if resp.status_code == 200:
        data = resp.json()
        normal_event_id = data.get("event_id")
        source = data.get("source", "upload")
        
        if source == "upload":
            log_test("Create normal event", True, f"event_id={normal_event_id}, source={source}")
        else:
            log_test("Create normal event", False, f"Expected source=upload, got {source}")
    else:
        log_test("Create normal event", False, f"Status {resp.status_code}: {resp.text[:200]}")
        normal_event_id = None
except Exception as e:
    log_test("Create normal event", False, f"Exception: {e}")
    normal_event_id = None

# ============================================================================
# TEST 15: Upload photo to normal event
# ============================================================================
print("\nTEST 15: Upload photo to normal event")
if normal_event_id:
    try:
        test_image = create_test_image()
        resp = requests.post(
            f"{BASE_URL}/events/{normal_event_id}/photos",
            headers=headers,
            files={"file": ("test.jpg", test_image, "image/jpeg")},
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            photo_id = data.get("photo_id")
            url = data.get("url", "")
            thumb_url = data.get("thumb_url", "")
            
            # Verify Cloudinary URLs
            cloudinary_ok = "cloudinary.com" in url and "cloudinary.com" in thumb_url
            
            if photo_id and cloudinary_ok:
                log_test("Upload photo to normal event", True, 
                        f"photo_id={photo_id}, Cloudinary URLs present")
            else:
                log_test("Upload photo to normal event", False, 
                        f"photo_id={photo_id}, cloudinary_ok={cloudinary_ok}")
        else:
            log_test("Upload photo to normal event", False, 
                    f"Status {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        log_test("Upload photo to normal event", False, f"Exception: {e}")
else:
    log_test("Upload photo to normal event", False, "No normal_event_id available")

# ============================================================================
# TEST 16: Delete normal event (cleanup)
# ============================================================================
print("\nTEST 16: Delete normal event (cleanup)")
if normal_event_id:
    try:
        resp = requests.delete(
            f"{BASE_URL}/events/{normal_event_id}",
            headers=headers,
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status")
            cloudinary_objects_deleted = data.get("cloudinary_objects_deleted", 0)
            
            if status == "deleted" and cloudinary_objects_deleted > 0:
                log_test("Delete normal event", True, 
                        f"status={status}, cloudinary_objects_deleted={cloudinary_objects_deleted}")
            else:
                log_test("Delete normal event", False, 
                        f"status={status}, cloudinary_objects_deleted={cloudinary_objects_deleted}")
        else:
            log_test("Delete normal event", False, f"Status {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        log_test("Delete normal event", False, f"Exception: {e}")
else:
    log_test("Delete normal event", False, "No normal_event_id available")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)
print(f"Total tests: {tests_passed + tests_failed}")
print(f"✅ Passed: {tests_passed}")
print(f"❌ Failed: {tests_failed}")
print("=" * 80)

if tests_failed > 0:
    print("\nFAILED TESTS:")
    for result in test_results:
        if not result["passed"]:
            print(f"  ❌ {result['name']}: {result['details']}")
    print()
    sys.exit(1)
else:
    print("\n🎉 ALL TESTS PASSED!")
    sys.exit(0)
