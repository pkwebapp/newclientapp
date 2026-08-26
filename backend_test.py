#!/usr/bin/env python3
"""
Backend Re-verification Test Suite
Tests Cloudinary + AWS Rekognition integration after credential configuration
"""

import requests
import json
import time
import io
from PIL import Image

# Configuration
BASE_URL = "http://localhost:8001/api"
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"
S3_BUCKET = "faceser"

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

def create_test_jpeg():
    """Create a small valid JPEG with a simple face-like pattern"""
    # Create a 200x200 RGB image with a simple pattern
    img = Image.new('RGB', (200, 200), color='white')
    pixels = img.load()
    
    # Draw a simple face-like pattern (circle for face, dots for eyes, line for mouth)
    for x in range(200):
        for y in range(200):
            # Face circle (centered at 100,100, radius 80)
            dx, dy = x - 100, y - 100
            dist = (dx*dx + dy*dy) ** 0.5
            if 75 < dist < 85:
                pixels[x, y] = (0, 0, 0)  # Black circle
            # Left eye
            elif (x-70)**2 + (y-80)**2 < 100:
                pixels[x, y] = (0, 0, 0)
            # Right eye
            elif (x-130)**2 + (y-80)**2 < 100:
                pixels[x, y] = (0, 0, 0)
            # Mouth (simple arc)
            elif 60 < x < 140 and 130 < y < 135:
                pixels[x, y] = (0, 0, 0)
    
    # Save to bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG', quality=85)
    img_bytes.seek(0)
    return img_bytes.getvalue()

def test_health():
    """Test 1: Health check"""
    try:
        resp = requests.get(f"{BASE_URL}/", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            log_test("Health check", True, f"Status: {data.get('status')}")
            return True
        else:
            log_test("Health check", False, f"Status code: {resp.status_code}")
            return False
    except Exception as e:
        log_test("Health check", False, f"Error: {str(e)}")
        return False

def test_admin_login():
    """Test 2: Admin login"""
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("session_token")
            if token:
                log_test("Admin login", True, f"Token received: {token[:20]}...")
                return token
            else:
                log_test("Admin login", False, "No session_token in response")
                return None
        else:
            log_test("Admin login", False, f"Status: {resp.status_code}, Body: {resp.text}")
            return None
    except Exception as e:
        log_test("Admin login", False, f"Error: {str(e)}")
        return None

def test_create_event(token):
    """Test 3: Create throwaway event"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.post(
            f"{BASE_URL}/events",
            headers=headers,
            json={
                "name": "QA Cloudinary Retest",
                "category": "wedding",
                "date": "2026-08-26"
            },
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            event_id = data.get("event_id")
            log_test("Create event", True, f"Event ID: {event_id}")
            return event_id
        else:
            log_test("Create event", False, f"Status: {resp.status_code}, Body: {resp.text}")
            return None
    except Exception as e:
        log_test("Create event", False, f"Error: {str(e)}")
        return None

def test_upload_photo(token, event_id):
    """Test 4: Upload photo and verify Cloudinary CDN URLs"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        # Create test JPEG
        jpeg_data = create_test_jpeg()
        
        files = {
            'file': ('test_photo.jpg', jpeg_data, 'image/jpeg')
        }
        
        resp = requests.post(
            f"{BASE_URL}/events/{event_id}/photos",
            headers=headers,
            files=files,
            timeout=30
        )
        
        if resp.status_code == 200:
            data = resp.json()
            photo_id = data.get("photo_id")
            url = data.get("url")
            thumb_url = data.get("thumb_url")
            
            # Verify Cloudinary CDN URLs
            cloudinary_check = (
                url and url.startswith("https://res.cloudinary.com/") and
                thumb_url and thumb_url.startswith("https://res.cloudinary.com/")
            )
            
            if cloudinary_check:
                log_test("Upload photo with Cloudinary CDN", True, 
                        f"Photo ID: {photo_id}\n   URL: {url[:80]}...\n   Thumb: {thumb_url[:80]}...")
                return photo_id, url, thumb_url
            else:
                log_test("Upload photo with Cloudinary CDN", False, 
                        f"URLs don't start with Cloudinary CDN\n   URL: {url}\n   Thumb: {thumb_url}")
                return photo_id, url, thumb_url
        else:
            log_test("Upload photo with Cloudinary CDN", False, 
                    f"Status: {resp.status_code}, Body: {resp.text}")
            return None, None, None
    except Exception as e:
        log_test("Upload photo with Cloudinary CDN", False, f"Error: {str(e)}")
        return None, None, None

def test_indexing_status(token, event_id):
    """Test 5: Poll indexing status until ready or failed"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        max_attempts = 20
        attempt = 0
        
        while attempt < max_attempts:
            resp = requests.get(
                f"{BASE_URL}/events/{event_id}/indexing-status",
                headers=headers,
                timeout=10
            )
            
            if resp.status_code != 200:
                log_test("Indexing status polling", False, 
                        f"Status: {resp.status_code}, Body: {resp.text}")
                return None
            
            data = resp.json()
            status = data.get("status")
            indexed = data.get("indexed", 0)
            total = data.get("total", 0)
            faces = data.get("faces", 0)
            complete = data.get("complete", False)
            
            print(f"   Polling attempt {attempt + 1}: status={status}, indexed={indexed}/{total}, faces={faces}, complete={complete}")
            
            if complete or status == "ready":
                log_test("Indexing status polling", True, 
                        f"Status: {status}, Indexed: {indexed}/{total}, Faces detected: {faces}")
                return {"status": status, "indexed": indexed, "total": total, "faces": faces}
            elif status == "failed":
                log_test("Indexing status polling", False, f"Indexing failed")
                return {"status": status, "indexed": indexed, "total": total, "faces": faces}
            
            attempt += 1
            time.sleep(1)
        
        log_test("Indexing status polling", False, f"Timeout after {max_attempts} attempts")
        return None
    except Exception as e:
        log_test("Indexing status polling", False, f"Error: {str(e)}")
        return None

def test_list_photos(token, event_id):
    """Test 6: List photos"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(
            f"{BASE_URL}/events/{event_id}/photos",
            headers=headers,
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            photos = data.get("photos", [])
            log_test("List photos", True, f"Found {len(photos)} photo(s)")
            return photos
        else:
            log_test("List photos", False, f"Status: {resp.status_code}, Body: {resp.text}")
            return None
    except Exception as e:
        log_test("List photos", False, f"Error: {str(e)}")
        return None

def test_s3_import(token, event_id):
    """Test 7: S3 import from faceser bucket"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.post(
            f"{BASE_URL}/events/{event_id}/import-s3",
            headers=headers,
            json={"bucket": S3_BUCKET},
            timeout=30
        )
        
        if resp.status_code == 200:
            data = resp.json()
            imported = data.get("imported", 0)
            queued = data.get("queued_for_indexing", 0)
            skipped = data.get("skipped", 0)
            log_test("S3 import", True, 
                    f"Bucket: {S3_BUCKET}, Imported: {imported}, Queued: {queued}, Skipped: {skipped}")
            return data
        else:
            log_test("S3 import", False, f"Status: {resp.status_code}, Body: {resp.text}")
            return None
    except Exception as e:
        log_test("S3 import", False, f"Error: {str(e)}")
        return None

def test_delete_event(token, event_id):
    """Test 8: Delete event and verify cleanup"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.delete(
            f"{BASE_URL}/events/{event_id}",
            headers=headers,
            timeout=30
        )
        
        if resp.status_code == 200:
            data = resp.json()
            photos_removed = data.get("photos_removed", 0)
            cloudinary_deleted = data.get("cloudinary_objects_deleted", 0)
            faces_deleted = data.get("faces_collection_deleted", False)
            log_test("Delete event", True, 
                    f"Photos removed: {photos_removed}, Cloudinary objects: {cloudinary_deleted}, Faces collection: {faces_deleted}")
            return True
        else:
            log_test("Delete event", False, f"Status: {resp.status_code}, Body: {resp.text}")
            return False
    except Exception as e:
        log_test("Delete event", False, f"Error: {str(e)}")
        return False

def test_verify_deletion(token, event_id):
    """Test 9: Verify event is deleted"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.get(
            f"{BASE_URL}/events/{event_id}",
            headers=headers,
            timeout=10
        )
        
        if resp.status_code == 404:
            log_test("Verify deletion", True, "Event not found (correctly deleted)")
            return True
        else:
            log_test("Verify deletion", False, f"Event still exists: {resp.status_code}")
            return False
    except Exception as e:
        log_test("Verify deletion", False, f"Error: {str(e)}")
        return False

def main():
    print("=" * 80)
    print("BACKEND RE-VERIFICATION TEST SUITE")
    print("Testing Cloudinary + AWS Rekognition integration")
    print("=" * 80)
    print()
    
    # Test 1: Health
    if not test_health():
        print("\n❌ Health check failed. Aborting tests.")
        return
    
    # Test 2: Admin login
    token = test_admin_login()
    if not token:
        print("\n❌ Admin login failed. Aborting tests.")
        return
    
    # Test 3: Create event
    event_id = test_create_event(token)
    if not event_id:
        print("\n❌ Event creation failed. Aborting tests.")
        return
    
    # Test 4: Upload photo
    photo_id, url, thumb_url = test_upload_photo(token, event_id)
    if not photo_id:
        print("\n❌ Photo upload failed. Continuing with remaining tests...")
    
    # Test 5: Indexing status
    indexing_result = test_indexing_status(token, event_id)
    
    # Test 6: List photos
    photos = test_list_photos(token, event_id)
    
    # Test 7: S3 import
    s3_result = test_s3_import(token, event_id)
    
    # Test 8: Delete event
    delete_success = test_delete_event(token, event_id)
    
    # Test 9: Verify deletion
    if delete_success:
        test_verify_deletion(token, event_id)
    
    # Summary
    print()
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
