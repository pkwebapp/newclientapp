#!/usr/bin/env python3
"""
Backend-only verification after switching to Cloudinary + AWS Rekognition credentials.
Tests: supervisor/backend startup, health, admin login, event creation, photo upload with Cloudinary CDN,
AWS Rekognition indexing, photo listing, S3 import, and cleanup.
"""

import requests
import time
import io
from PIL import Image

# Configuration
BASE_URL = "https://ab1b5b53-cd84-4df4-bf72-9cc6253f1656.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

# Test state
session_token = None
event_id = None
photo_id = None

def log_test(step, description):
    """Log test step"""
    print(f"\n{'='*80}")
    print(f"TEST {step}: {description}")
    print('='*80)

def log_result(status, message, details=None):
    """Log test result"""
    symbol = "✅" if status == "PASS" else "❌"
    print(f"{symbol} {status}: {message}")
    if details:
        for key, value in details.items():
            print(f"   • {key}: {value}")

def create_test_image():
    """Create a small valid JPEG with a synthetic face pattern"""
    img = Image.new('RGB', (200, 200), color='white')
    pixels = img.load()
    
    # Draw a simple face pattern (circle for head, dots for eyes, line for mouth)
    for x in range(200):
        for y in range(200):
            # Head circle
            if 50 <= x <= 150 and 50 <= y <= 150:
                dist = ((x-100)**2 + (y-100)**2)**0.5
                if 40 <= dist <= 50:
                    pixels[x, y] = (0, 0, 0)
            # Left eye
            if 70 <= x <= 80 and 80 <= y <= 90:
                pixels[x, y] = (0, 0, 0)
            # Right eye
            if 120 <= x <= 130 and 80 <= y <= 90:
                pixels[x, y] = (0, 0, 0)
            # Mouth
            if 80 <= x <= 120 and 120 <= y <= 125:
                pixels[x, y] = (0, 0, 0)
    
    # Save to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG', quality=85)
    img_bytes.seek(0)
    return img_bytes.getvalue()

def test_health_check():
    """Test 1: GET /api/ health check"""
    log_test(1, "Health Check")
    try:
        response = requests.get(f"{BASE_URL}/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            log_result("PASS", f"Health check returned 200", {
                "status": data.get("status"),
                "service": data.get("service")
            })
            return True
        else:
            log_result("FAIL", f"Health check returned {response.status_code}", {
                "response": response.text[:200]
            })
            return False
    except Exception as e:
        log_result("FAIL", f"Health check failed with exception", {"error": str(e)})
        return False

def test_admin_login():
    """Test 2: POST /api/auth/admin/login"""
    global session_token
    log_test(2, "Admin Login")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            session_token = data.get("session_token")
            if session_token:
                log_result("PASS", "Admin login successful", {
                    "email": ADMIN_EMAIL,
                    "token_length": len(session_token),
                    "user_role": data.get("user", {}).get("role")
                })
                return True
            else:
                log_result("FAIL", "No session_token in response", {"response": data})
                return False
        else:
            log_result("FAIL", f"Admin login returned {response.status_code}", {
                "response": response.text[:200]
            })
            return False
    except Exception as e:
        log_result("FAIL", f"Admin login failed with exception", {"error": str(e)})
        return False

def test_create_event():
    """Test 3: POST /api/events (create throwaway event)"""
    global event_id
    log_test(3, "Create Throwaway Event")
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.post(
            f"{BASE_URL}/events",
            json={
                "name": "QA Cloudinary AWS Verification",
                "date": "2027-03-15",
                "location": "Test Location"
            },
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            event_id = data.get("event_id")
            if event_id:
                log_result("PASS", "Event created successfully", {
                    "event_id": event_id,
                    "name": data.get("name"),
                    "status": data.get("status")
                })
                return True
            else:
                log_result("FAIL", "No event_id in response", {"response": data})
                return False
        else:
            log_result("FAIL", f"Create event returned {response.status_code}", {
                "response": response.text[:200]
            })
            return False
    except Exception as e:
        log_result("FAIL", f"Create event failed with exception", {"error": str(e)})
        return False

def test_upload_photo():
    """Test 4: POST /api/events/{id}/photos (upload valid small JPEG)"""
    global photo_id
    log_test(4, "Upload Photo with Cloudinary Storage")
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        img_bytes = create_test_image()
        files = {"file": ("test_photo.jpg", img_bytes, "image/jpeg")}
        
        response = requests.post(
            f"{BASE_URL}/events/{event_id}/photos",
            files=files,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            photo_id = data.get("photo_id")
            url = data.get("url")
            thumb_url = data.get("thumb_url")
            
            # Verify Cloudinary CDN URLs
            cloudinary_cdn = "res.cloudinary.com"
            url_valid = url and cloudinary_cdn in url
            thumb_valid = thumb_url and cloudinary_cdn in thumb_url
            
            if photo_id and url_valid and thumb_valid:
                log_result("PASS", "Photo uploaded with Cloudinary CDN URLs", {
                    "photo_id": photo_id,
                    "url_starts_with": url[:60] + "..." if len(url) > 60 else url,
                    "thumb_url_starts_with": thumb_url[:60] + "..." if len(thumb_url) > 60 else thumb_url,
                    "cloudinary_cdn_verified": "✓"
                })
                return True
            else:
                log_result("FAIL", "Photo uploaded but missing Cloudinary CDN URLs", {
                    "photo_id": photo_id,
                    "url": url,
                    "thumb_url": thumb_url,
                    "url_has_cloudinary": url_valid,
                    "thumb_has_cloudinary": thumb_valid
                })
                return False
        else:
            log_result("FAIL", f"Upload photo returned {response.status_code}", {
                "response": response.text[:200]
            })
            return False
    except Exception as e:
        log_result("FAIL", f"Upload photo failed with exception", {"error": str(e)})
        return False

def test_poll_indexing():
    """Test 5: GET /api/events/{id}/indexing-status (poll until ready)"""
    log_test(5, "Poll Indexing Status (AWS Rekognition)")
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        max_attempts = 20
        poll_interval = 2
        
        for attempt in range(1, max_attempts + 1):
            response = requests.get(
                f"{BASE_URL}/events/{event_id}/indexing-status",
                headers=headers,
                timeout=10
            )
            
            if response.status_code != 200:
                log_result("FAIL", f"Indexing status returned {response.status_code}", {
                    "attempt": attempt,
                    "response": response.text[:200]
                })
                return False
            
            data = response.json()
            status = data.get("status")
            indexed = data.get("indexed", 0)
            total = data.get("total", 0)
            faces = data.get("faces", 0)
            complete = data.get("complete", False)
            
            print(f"   Attempt {attempt}/{max_attempts}: status={status}, indexed={indexed}/{total}, faces={faces}, complete={complete}")
            
            if status == "ready" and complete:
                log_result("PASS", "AWS Rekognition indexing completed successfully", {
                    "status": status,
                    "indexed": f"{indexed}/{total}",
                    "faces_detected": faces,
                    "complete": complete,
                    "attempts": attempt
                })
                return True
            
            if status == "error":
                log_result("FAIL", "Indexing failed with error status", {
                    "status": status,
                    "data": data
                })
                return False
            
            if attempt < max_attempts:
                time.sleep(poll_interval)
        
        log_result("FAIL", f"Indexing did not complete after {max_attempts} attempts", {
            "last_status": status,
            "indexed": f"{indexed}/{total}"
        })
        return False
        
    except Exception as e:
        log_result("FAIL", f"Poll indexing failed with exception", {"error": str(e)})
        return False

def test_list_photos():
    """Test 6: GET /api/events/{id}/photos (list photos)"""
    log_test(6, "List Photos")
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.get(
            f"{BASE_URL}/events/{event_id}/photos",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            photos = data if isinstance(data, list) else data.get("items", [])
            
            # Find our uploaded photo
            uploaded_photo = None
            for photo in photos:
                if photo.get("photo_id") == photo_id:
                    uploaded_photo = photo
                    break
            
            if uploaded_photo:
                log_result("PASS", "Uploaded photo found in list", {
                    "total_photos": len(photos),
                    "photo_id": photo_id,
                    "filename": uploaded_photo.get("filename"),
                    "status": uploaded_photo.get("status")
                })
                return True
            else:
                log_result("FAIL", "Uploaded photo NOT found in list", {
                    "total_photos": len(photos),
                    "looking_for": photo_id,
                    "photo_ids_in_list": [p.get("photo_id") for p in photos]
                })
                return False
        else:
            log_result("FAIL", f"List photos returned {response.status_code}", {
                "response": response.text[:200]
            })
            return False
    except Exception as e:
        log_result("FAIL", f"List photos failed with exception", {"error": str(e)})
        return False

def test_s3_import():
    """Test 7: POST /api/events/{id}/import-s3 (bucket faceser)"""
    log_test(7, "S3 Import (bucket: faceser)")
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.post(
            f"{BASE_URL}/events/{event_id}/import-s3",
            json={"bucket": "faceser"},
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status")
            bucket = data.get("bucket")
            imported = data.get("imported", 0)
            
            log_result("PASS", "S3 import returned controlled success", {
                "status": status,
                "bucket": bucket,
                "imported": imported,
                "queued_for_indexing": data.get("queued_for_indexing", 0),
                "skipped": data.get("skipped", 0)
            })
            return True
        else:
            log_result("FAIL", f"S3 import returned {response.status_code}", {
                "response": response.text[:200]
            })
            return False
    except Exception as e:
        log_result("FAIL", f"S3 import failed with exception", {"error": str(e)})
        return False

def test_delete_event():
    """Test 8: DELETE /api/events/{id} (cleanup)"""
    log_test(8, "Delete Throwaway Event (Cleanup)")
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.delete(
            f"{BASE_URL}/events/{event_id}",
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            log_result("PASS", "Event deleted successfully", {
                "status": data.get("status"),
                "event_id": data.get("event_id"),
                "photos_removed": data.get("photos_removed"),
                "cloudinary_objects_deleted": data.get("cloudinary_objects_deleted"),
                "faces_collection_deleted": data.get("faces_collection_deleted")
            })
            return True
        else:
            log_result("FAIL", f"Delete event returned {response.status_code}", {
                "response": response.text[:200]
            })
            return False
    except Exception as e:
        log_result("FAIL", f"Delete event failed with exception", {"error": str(e)})
        return False

def test_verify_deletion():
    """Test 9: GET /api/events/{id} (verify deletion)"""
    log_test(9, "Verify Event Deletion")
    try:
        headers = {"Authorization": f"Bearer {session_token}"}
        response = requests.get(
            f"{BASE_URL}/events/{event_id}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 404:
            log_result("PASS", "Event correctly deleted (404 returned)", {
                "event_id": event_id
            })
            return True
        else:
            log_result("FAIL", f"Event still exists (expected 404, got {response.status_code})", {
                "response": response.text[:200]
            })
            return False
    except Exception as e:
        log_result("FAIL", f"Verify deletion failed with exception", {"error": str(e)})
        return False

def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("BACKEND VERIFICATION: Cloudinary + AWS Rekognition Configuration")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"Admin: {ADMIN_EMAIL}")
    print("="*80)
    
    tests = [
        ("Health Check", test_health_check),
        ("Admin Login", test_admin_login),
        ("Create Event", test_create_event),
        ("Upload Photo (Cloudinary)", test_upload_photo),
        ("Poll Indexing (AWS Rekognition)", test_poll_indexing),
        ("List Photos", test_list_photos),
        ("S3 Import (faceser)", test_s3_import),
        ("Delete Event", test_delete_event),
        ("Verify Deletion", test_verify_deletion)
    ]
    
    results = []
    for name, test_func in tests:
        result = test_func()
        results.append((name, result))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        symbol = "✅" if result else "❌"
        status = "PASS" if result else "FAIL"
        print(f"{symbol} {status}: {name}")
    
    print("="*80)
    print(f"TOTAL: {passed}/{total} tests passed")
    print("="*80)
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED - Backend verification successful!")
        return 0
    else:
        print(f"\n❌ {total - passed} TEST(S) FAILED - Backend verification incomplete")
        return 1

if __name__ == "__main__":
    exit(main())
