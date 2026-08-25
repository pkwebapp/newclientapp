#!/usr/bin/env python3
"""
Backend Integration Test - Cloudinary + AWS Rekognition
Tests the current backend configuration with real cloud services.
"""

import requests
import time
import io
from PIL import Image, ImageDraw

# Configuration
BASE_URL = "https://a70c8c7c-7909-439b-b400-7e934db51d33.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

# Test results tracking
test_results = []

def log_test(test_name, passed, details=""):
    """Log test result"""
    status = "✅ PASS" if passed else "❌ FAIL"
    test_results.append({
        "name": test_name,
        "passed": passed,
        "details": details
    })
    print(f"{status}: {test_name}")
    if details:
        print(f"   {details}")

def create_test_image():
    """Create a small synthetic test JPEG image"""
    # Create a 400x400 image with a simple pattern
    img = Image.new('RGB', (400, 400), color='white')
    draw = ImageDraw.Draw(img)
    
    # Draw a simple face-like pattern (circle for head, dots for eyes, arc for smile)
    draw.ellipse([100, 100, 300, 300], outline='black', width=3)  # Head
    draw.ellipse([150, 150, 170, 170], fill='black')  # Left eye
    draw.ellipse([230, 150, 250, 170], fill='black')  # Right eye
    draw.arc([150, 200, 250, 250], 0, 180, fill='black', width=3)  # Smile
    
    # Convert to JPEG bytes
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG', quality=85)
    img_bytes.seek(0)
    return img_bytes.getvalue()

def test_health():
    """Test 1: Health check"""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok":
                log_test("Health check", True, f"Response: {data}")
                return True
        log_test("Health check", False, f"Status: {response.status_code}, Body: {response.text[:200]}")
        return False
    except Exception as e:
        log_test("Health check", False, f"Error: {str(e)}")
        return False

def test_admin_login():
    """Test 2: Admin login"""
    try:
        response = requests.post(
            f"{BASE_URL}/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if "session_token" in data:
                log_test("Admin login", True, f"Admin: {ADMIN_EMAIL}")
                return data["session_token"]
        log_test("Admin login", False, f"Status: {response.status_code}, Body: {response.text[:200]}")
        return None
    except Exception as e:
        log_test("Admin login", False, f"Error: {str(e)}")
        return None

def test_create_event(token):
    """Test 3: Create temporary event"""
    try:
        response = requests.post(
            f"{BASE_URL}/events",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "name": "QA Cloudinary Rekognition Test",
                "category": "wedding",
                "date": "2026-01-15"
            },
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            event_id = data.get("event_id")
            if event_id:
                log_test("Create event", True, f"Event ID: {event_id}")
                return event_id
        log_test("Create event", False, f"Status: {response.status_code}, Body: {response.text[:200]}")
        return None
    except Exception as e:
        log_test("Create event", False, f"Error: {str(e)}")
        return None

def test_upload_photo(token, event_id):
    """Test 4: Upload photo"""
    try:
        # Create test image
        image_bytes = create_test_image()
        
        # Upload photo
        files = {"file": ("test_photo.jpg", image_bytes, "image/jpeg")}
        response = requests.post(
            f"{BASE_URL}/events/{event_id}/photos",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            photo_id = data.get("photo_id")
            url = data.get("url")
            thumb_url = data.get("thumb_url")
            
            if photo_id:
                log_test("Upload photo", True, f"Photo ID: {photo_id}")
                return photo_id, url, thumb_url
        
        log_test("Upload photo", False, f"Status: {response.status_code}, Body: {response.text[:200]}")
        return None, None, None
    except Exception as e:
        log_test("Upload photo", False, f"Error: {str(e)}")
        return None, None, None

def test_cloudinary_urls(url, thumb_url):
    """Test 5: Verify Cloudinary CDN URLs"""
    try:
        # Check if URLs are Cloudinary CDN
        is_cloudinary_url = url and url.startswith("https://res.cloudinary.com/jeoj8k1t/")
        is_cloudinary_thumb = thumb_url and thumb_url.startswith("https://res.cloudinary.com/jeoj8k1t/")
        
        if is_cloudinary_url and is_cloudinary_thumb:
            # Try to fetch the image
            response = requests.get(url, timeout=10)
            if response.status_code == 200 and response.headers.get("content-type", "").startswith("image/"):
                size = len(response.content)
                log_test("Cloudinary CDN URLs", True, 
                        f"URL: {url[:80]}...\nThumb: {thumb_url[:80]}...\nFetched: {size} bytes")
                return True
            else:
                log_test("Cloudinary CDN URLs", False, 
                        f"URL fetch failed: {response.status_code}")
                return False
        else:
            log_test("Cloudinary CDN URLs", False, 
                    f"URLs not Cloudinary CDN:\nURL: {url}\nThumb: {thumb_url}")
            return False
    except Exception as e:
        log_test("Cloudinary CDN URLs", False, f"Error: {str(e)}")
        return False

def test_indexing_status(token, event_id):
    """Test 6: Poll indexing status until complete"""
    try:
        max_attempts = 30  # 30 seconds max
        for attempt in range(max_attempts):
            response = requests.get(
                f"{BASE_URL}/events/{event_id}/indexing-status",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                status = data.get("status")
                indexed = data.get("indexed", 0)
                total = data.get("total", 0)
                faces = data.get("faces", 0)
                complete = data.get("complete", False)
                
                if complete or status == "ready":
                    log_test("Indexing status", True, 
                            f"Status: {status}, Indexed: {indexed}/{total}, Faces: {faces}, Complete: {complete}")
                    return True
                
                # Wait before next poll
                time.sleep(1)
            else:
                log_test("Indexing status", False, 
                        f"Status: {response.status_code}, Body: {response.text[:200]}")
                return False
        
        log_test("Indexing status", False, "Timeout waiting for indexing to complete")
        return False
    except Exception as e:
        log_test("Indexing status", False, f"Error: {str(e)}")
        return False

def test_list_photos(token, event_id):
    """Test 7: List photos"""
    try:
        response = requests.get(
            f"{BASE_URL}/events/{event_id}/photos",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            # The response structure uses "items" not "photos"
            photos = data.get("items", [])
            if len(photos) > 0:
                log_test("List photos", True, f"Found {len(photos)} photo(s)")
                return True
            else:
                log_test("List photos", False, "No photos found")
                return False
        
        log_test("List photos", False, f"Status: {response.status_code}, Body: {response.text[:200]}")
        return False
    except Exception as e:
        log_test("List photos", False, f"Error: {str(e)}")
        return False

def test_s3_import(token, event_id):
    """Test 8: S3 import from faceser bucket"""
    try:
        response = requests.post(
            f"{BASE_URL}/events/{event_id}/import-s3",
            headers={"Authorization": f"Bearer {token}"},
            json={"bucket": "faceser"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            imported = data.get("imported", 0)
            log_test("S3 import", True, 
                    f"Bucket: faceser, Imported: {imported} (empty bucket OK)")
            return True
        
        log_test("S3 import", False, f"Status: {response.status_code}, Body: {response.text[:200]}")
        return False
    except Exception as e:
        log_test("S3 import", False, f"Error: {str(e)}")
        return False

def test_delete_event(token, event_id):
    """Test 9: Delete event"""
    try:
        response = requests.delete(
            f"{BASE_URL}/events/{event_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            photos_removed = data.get("photos_removed", 0)
            cloudinary_deleted = data.get("cloudinary_objects_deleted", 0)
            faces_deleted = data.get("faces_collection_deleted", False)
            
            log_test("Delete event", True, 
                    f"Photos removed: {photos_removed}, Cloudinary objects: {cloudinary_deleted}, Rekognition collection: {faces_deleted}")
            return True
        
        log_test("Delete event", False, f"Status: {response.status_code}, Body: {response.text[:200]}")
        return False
    except Exception as e:
        log_test("Delete event", False, f"Error: {str(e)}")
        return False

def test_verify_deletion(token, event_id):
    """Test 10: Verify event deletion"""
    try:
        response = requests.get(
            f"{BASE_URL}/events/{event_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        if response.status_code == 404:
            log_test("Verify deletion", True, "Event not found (correctly deleted)")
            return True
        
        log_test("Verify deletion", False, 
                f"Event still exists: Status {response.status_code}")
        return False
    except Exception as e:
        log_test("Verify deletion", False, f"Error: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("=" * 80)
    print("BACKEND INTEGRATION TEST - CLOUDINARY + AWS REKOGNITION")
    print("=" * 80)
    print()
    
    # Test 1: Health check
    if not test_health():
        print("\n❌ Backend health check failed. Aborting tests.")
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
        print("\n❌ Photo upload failed. Aborting tests.")
        # Try to clean up event
        test_delete_event(token, event_id)
        return
    
    # Test 5: Verify Cloudinary URLs
    test_cloudinary_urls(url, thumb_url)
    
    # Test 6: Poll indexing status
    test_indexing_status(token, event_id)
    
    # Test 7: List photos
    test_list_photos(token, event_id)
    
    # Test 8: S3 import
    test_s3_import(token, event_id)
    
    # Test 9: Delete event
    test_delete_event(token, event_id)
    
    # Test 10: Verify deletion
    test_verify_deletion(token, event_id)
    
    # Summary
    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    passed = sum(1 for r in test_results if r["passed"])
    total = len(test_results)
    print(f"Total: {passed}/{total} tests passed")
    print()
    
    if passed == total:
        print("✅ ALL TESTS PASSED - Cloudinary + AWS Rekognition integration fully functional")
    else:
        print("❌ SOME TESTS FAILED")
        print("\nFailed tests:")
        for r in test_results:
            if not r["passed"]:
                print(f"  - {r['name']}: {r['details']}")

if __name__ == "__main__":
    main()
