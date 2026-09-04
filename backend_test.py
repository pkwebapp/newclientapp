#!/usr/bin/env python3
"""
PIK Connect Backend Testing - Cloudinary + AWS Rekognition Integration
Tests the complete photo-upload and face-search pipeline with REAL external services.
"""
import io
import sys
import time
import requests
from PIL import Image, ImageDraw

# Base URL from frontend/.env
BASE_URL = "https://pkweb-app.preview.emergentagent.com/api"

# Test counters
tests_passed = 0
tests_failed = 0
test_results = []


def log_test(name, passed, details=""):
    """Log test result"""
    global tests_passed, tests_failed
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status}: {name}")
    if details:
        print(f"   {details}")
    test_results.append({"name": name, "passed": passed, "details": details})
    if passed:
        tests_passed += 1
    else:
        tests_failed += 1


def create_test_image_with_face(width=400, height=400):
    """Create a simple test JPEG image with a synthetic face pattern"""
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Draw a simple face-like pattern
    # Face oval
    draw.ellipse([100, 80, 300, 320], fill='#FFE0BD', outline='black', width=2)
    # Eyes
    draw.ellipse([140, 150, 180, 190], fill='white', outline='black', width=2)
    draw.ellipse([220, 150, 260, 190], fill='white', outline='black', width=2)
    # Pupils
    draw.ellipse([155, 165, 165, 175], fill='black')
    draw.ellipse([235, 165, 245, 175], fill='black')
    # Nose
    draw.line([200, 190, 200, 240], fill='black', width=2)
    # Mouth
    draw.arc([160, 240, 240, 280], 0, 180, fill='black', width=2)
    
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    return buf.getvalue()


def create_test_image_no_face(width=400, height=400):
    """Create a test JPEG image with NO detectable face (landscape/abstract)"""
    img = Image.new('RGB', (width, height), color='skyblue')
    draw = ImageDraw.Draw(img)
    
    # Draw abstract landscape (no face)
    # Sky gradient
    for y in range(0, 200):
        color = (135, 206, 235 - y // 4)
        draw.line([(0, y), (width, y)], fill=color)
    
    # Ground
    draw.rectangle([0, 200, width, height], fill='#90EE90')
    
    # Sun
    draw.ellipse([300, 50, 350, 100], fill='yellow', outline='orange', width=2)
    
    # Tree
    draw.rectangle([50, 150, 80, 250], fill='brown')
    draw.ellipse([20, 100, 110, 180], fill='green')
    
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    return buf.getvalue()


def test_health_check():
    """Test 1: Health check endpoint"""
    try:
        resp = requests.get(f"{BASE_URL}/", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "ok":
                log_test("Health check GET /api/", True, f"Response: {data}")
                return True
            else:
                log_test("Health check GET /api/", False, f"Unexpected response: {data}")
                return False
        else:
            log_test("Health check GET /api/", False, f"Status: {resp.status_code}, Body: {resp.text[:200]}")
            return False
    except Exception as e:
        log_test("Health check GET /api/", False, f"Exception: {e}")
        return False


def test_auth():
    """Test 2: Dev mock login for admin"""
    try:
        resp = requests.post(
            f"{BASE_URL}/auth/dev/mock-login",
            json={"role": "admin"},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("session_token") or data.get("token")
            if token:
                log_test("Admin auth POST /api/auth/dev/mock-login", True, f"Token received (length: {len(token)})")
                return token
            else:
                log_test("Admin auth POST /api/auth/dev/mock-login", False, f"No token in response: {data}")
                return None
        else:
            log_test("Admin auth POST /api/auth/dev/mock-login", False, f"Status: {resp.status_code}, Body: {resp.text[:200]}")
            return None
    except Exception as e:
        log_test("Admin auth POST /api/auth/dev/mock-login", False, f"Exception: {e}")
        return None


def test_create_event(token):
    """Test 3: Create event/gallery"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.post(
            f"{BASE_URL}/events",
            json={
                "name": "QA Cloudinary Rekognition Test",
                "date": "2026-09-01",
                "category": "event"
            },
            headers=headers,
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            event_id = data.get("event_id")
            if event_id:
                log_test("Create event POST /api/events", True, f"Event ID: {event_id}")
                return event_id
            else:
                log_test("Create event POST /api/events", False, f"No event_id in response: {data}")
                return None
        else:
            log_test("Create event POST /api/events", False, f"Status: {resp.status_code}, Body: {resp.text[:200]}")
            return None
    except Exception as e:
        log_test("Create event POST /api/events", False, f"Exception: {e}")
        return None


def test_upload_photo(token, event_id, image_bytes, filename="test_photo.jpg"):
    """Test 4: Upload photo to event"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        files = {"file": (filename, image_bytes, "image/jpeg")}
        resp = requests.post(
            f"{BASE_URL}/events/{event_id}/photos",
            files=files,
            headers=headers,
            timeout=30
        )
        if resp.status_code == 200:
            data = resp.json()
            photo_id = data.get("photo_id")
            url = data.get("url")
            thumb_url = data.get("thumb_url")
            
            # Verify Cloudinary URLs
            cloudinary_check = False
            if url and "res.cloudinary.com" in url:
                cloudinary_check = True
            
            if photo_id:
                details = f"Photo ID: {photo_id}, URL: {url[:80] if url else 'None'}, Cloudinary: {cloudinary_check}"
                log_test(f"Upload photo {filename}", True, details)
                return {"photo_id": photo_id, "url": url, "thumb_url": thumb_url, "cloudinary": cloudinary_check}
            else:
                log_test(f"Upload photo {filename}", False, f"No photo_id in response: {data}")
                return None
        else:
            log_test(f"Upload photo {filename}", False, f"Status: {resp.status_code}, Body: {resp.text[:200]}")
            return None
    except Exception as e:
        log_test(f"Upload photo {filename}", False, f"Exception: {e}")
        return None


def test_cloudinary_url_access(url):
    """Test 5: Verify Cloudinary URL is accessible"""
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            content_type = resp.headers.get("content-type", "")
            size = len(resp.content)
            if "image" in content_type:
                log_test("Cloudinary URL access", True, f"Retrieved {size} bytes, content-type: {content_type}")
                return True
            else:
                log_test("Cloudinary URL access", False, f"Unexpected content-type: {content_type}")
                return False
        else:
            log_test("Cloudinary URL access", False, f"Status: {resp.status_code}")
            return False
    except Exception as e:
        log_test("Cloudinary URL access", False, f"Exception: {e}")
        return False


def test_indexing_status(token, event_id, max_wait=30):
    """Test 6: Check Rekognition indexing status"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            resp = requests.get(
                f"{BASE_URL}/events/{event_id}/indexing-status",
                headers=headers,
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status")
                indexed = data.get("indexed")
                total = data.get("total")
                faces = data.get("faces")
                complete = data.get("complete")
                
                if complete or status == "ready":
                    details = f"Status: {status}, Indexed: {indexed}/{total}, Faces: {faces}, Complete: {complete}"
                    log_test("Rekognition indexing status", True, details)
                    return {"status": status, "indexed": indexed, "total": total, "faces": faces, "complete": complete}
                
                # Still indexing, wait and retry
                time.sleep(2)
            else:
                log_test("Rekognition indexing status", False, f"Status: {resp.status_code}, Body: {resp.text[:200]}")
                return None
        
        # Timeout
        log_test("Rekognition indexing status", False, f"Indexing did not complete within {max_wait}s")
        return None
    except Exception as e:
        log_test("Rekognition indexing status", False, f"Exception: {e}")
        return None


def test_manual_reindex(token, event_id):
    """Test 7: Manual re-index endpoint (if exists)"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.post(
            f"{BASE_URL}/events/{event_id}/reindex",
            headers=headers,
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            log_test("Manual re-index endpoint", True, f"Response: {data}")
            return True
        elif resp.status_code == 404:
            log_test("Manual re-index endpoint", True, "Endpoint not found (optional feature)")
            return True
        else:
            log_test("Manual re-index endpoint", False, f"Status: {resp.status_code}, Body: {resp.text[:200]}")
            return False
    except Exception as e:
        log_test("Manual re-index endpoint", False, f"Exception: {e}")
        return False


def test_selfie_search_with_face(token, event_id):
    """Test 8: Selfie search with face image"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        # First, register as a visitor to get client access
        visitor_resp = requests.post(
            f"{BASE_URL}/public/events/{event_id}/access",
            json={"name": "QA Tester", "phone": "+919876543210"},
            timeout=10
        )
        
        if visitor_resp.status_code != 200:
            log_test("Selfie search (with face) - visitor registration", False, f"Status: {visitor_resp.status_code}")
            return False
        
        visitor_data = visitor_resp.json()
        visitor_token = visitor_data.get("session_token") or visitor_data.get("token")
        
        if not visitor_token:
            log_test("Selfie search (with face) - visitor registration", False, "No visitor token received")
            return False
        
        # Give biometric consent
        consent_headers = {"Authorization": f"Bearer {visitor_token}"}
        consent_resp = requests.post(
            f"{BASE_URL}/client/events/{event_id}/consent",
            json={"accepted": True},
            headers=consent_headers,
            timeout=10
        )
        
        if consent_resp.status_code != 200:
            log_test("Selfie search (with face) - consent", False, f"Status: {consent_resp.status_code}")
            return False
        
        # Now do selfie search
        selfie_image = create_test_image_with_face()
        files = {"file": ("selfie.jpg", selfie_image, "image/jpeg")}
        search_headers = {"Authorization": f"Bearer {visitor_token}"}
        
        search_resp = requests.post(
            f"{BASE_URL}/client/events/{event_id}/search",
            files=files,
            headers=search_headers,
            timeout=30
        )
        
        if search_resp.status_code == 200:
            data = search_resp.json()
            matches = data.get("matches", [])
            log_test("Selfie search (with face)", True, f"Response: 200, Matches: {len(matches)}")
            return True
        else:
            log_test("Selfie search (with face)", False, f"Status: {search_resp.status_code}, Body: {search_resp.text[:200]}")
            return False
    except Exception as e:
        log_test("Selfie search (with face)", False, f"Exception: {e}")
        return False


def test_selfie_search_no_face(token, event_id):
    """Test 9: Selfie search with NO face (should handle gracefully)"""
    try:
        # Register as a different visitor
        visitor_resp = requests.post(
            f"{BASE_URL}/public/events/{event_id}/access",
            json={"name": "QA Tester 2", "phone": "+919876543211"},
            timeout=10
        )
        
        if visitor_resp.status_code != 200:
            log_test("Selfie search (no face) - visitor registration", False, f"Status: {visitor_resp.status_code}")
            return False
        
        visitor_data = visitor_resp.json()
        visitor_token = visitor_data.get("session_token") or visitor_data.get("token")
        
        if not visitor_token:
            log_test("Selfie search (no face) - visitor registration", False, "No visitor token received")
            return False
        
        # Give biometric consent
        consent_headers = {"Authorization": f"Bearer {visitor_token}"}
        consent_resp = requests.post(
            f"{BASE_URL}/client/events/{event_id}/consent",
            json={"accepted": True},
            headers=consent_headers,
            timeout=10
        )
        
        if consent_resp.status_code != 200:
            log_test("Selfie search (no face) - consent", False, f"Status: {consent_resp.status_code}")
            return False
        
        # Upload image with no face
        no_face_image = create_test_image_no_face()
        files = {"file": ("landscape.jpg", no_face_image, "image/jpeg")}
        search_headers = {"Authorization": f"Bearer {visitor_token}"}
        
        search_resp = requests.post(
            f"{BASE_URL}/client/events/{event_id}/search",
            files=files,
            headers=search_headers,
            timeout=30
        )
        
        # Should return 200 with empty matches OR a clean 4xx (not 500)
        if search_resp.status_code == 200:
            data = search_resp.json()
            log_test("Selfie search (no face) - graceful handling", True, f"Response: 200, Data: {data}")
            return True
        elif 400 <= search_resp.status_code < 500:
            log_test("Selfie search (no face) - graceful handling", True, f"Clean 4xx response: {search_resp.status_code}")
            return True
        else:
            log_test("Selfie search (no face) - graceful handling", False, f"Status: {search_resp.status_code}, Body: {search_resp.text[:200]}")
            return False
    except Exception as e:
        log_test("Selfie search (no face) - graceful handling", False, f"Exception: {e}")
        return False


def test_delete_photo(token, event_id, photo_id):
    """Test 10: Delete a photo"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.delete(
            f"{BASE_URL}/events/{event_id}/photos/{photo_id}",
            headers=headers,
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            log_test(f"Delete photo {photo_id}", True, f"Response: {data}")
            return True
        else:
            log_test(f"Delete photo {photo_id}", False, f"Status: {resp.status_code}, Body: {resp.text[:200]}")
            return False
    except Exception as e:
        log_test(f"Delete photo {photo_id}", False, f"Exception: {e}")
        return False


def test_delete_event(token, event_id):
    """Test 11: Delete event/gallery (cleanup)"""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        resp = requests.delete(
            f"{BASE_URL}/events/{event_id}",
            headers=headers,
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            photos_removed = data.get("photos_removed", 0)
            cloudinary_deleted = data.get("cloudinary_objects_deleted", 0)
            collection_deleted = data.get("faces_collection_deleted", False)
            details = f"Photos: {photos_removed}, Cloudinary: {cloudinary_deleted}, Collection: {collection_deleted}"
            log_test("Delete event (cleanup)", True, details)
            return True
        else:
            log_test("Delete event (cleanup)", False, f"Status: {resp.status_code}, Body: {resp.text[:200]}")
            return False
    except Exception as e:
        log_test("Delete event (cleanup)", False, f"Exception: {e}")
        return False


def check_backend_logs():
    """Test 12: Check backend logs for Cloudinary/Rekognition errors"""
    try:
        import subprocess
        result = subprocess.run(
            ["tail", "-n", "100", "/var/log/supervisor/backend.err.log"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        logs = result.stdout
        
        # Check for credential/permission errors
        error_keywords = [
            "cloudinary.*error",
            "rekognition.*error",
            "credential",
            "permission denied",
            "unauthorized",
            "invalid.*key",
            "access.*denied"
        ]
        
        import re
        errors_found = []
        for keyword in error_keywords:
            matches = re.findall(keyword, logs, re.IGNORECASE)
            if matches:
                errors_found.extend(matches)
        
        if errors_found:
            log_test("Backend logs check", False, f"Found errors: {errors_found[:5]}")
            return False
        else:
            log_test("Backend logs check", True, "No Cloudinary/Rekognition errors in recent logs")
            return True
    except Exception as e:
        log_test("Backend logs check", False, f"Exception: {e}")
        return False


def main():
    """Run all tests"""
    print("=" * 80)
    print("PIK CONNECT BACKEND TESTING - CLOUDINARY + AWS REKOGNITION")
    print("=" * 80)
    print()
    
    # Test 1: Health check
    if not test_health_check():
        print("\n❌ Health check failed. Aborting tests.")
        return
    
    # Test 2: Auth
    token = test_auth()
    if not token:
        print("\n❌ Authentication failed. Aborting tests.")
        return
    
    # Test 3: Create event
    event_id = test_create_event(token)
    if not event_id:
        print("\n❌ Event creation failed. Aborting tests.")
        return
    
    # Test 4: Upload photos
    print("\n--- STORAGE UPLOAD TESTS ---")
    photo1_image = create_test_image_with_face()
    photo1 = test_upload_photo(token, event_id, photo1_image, "photo1_with_face.jpg")
    
    photo2_image = create_test_image_with_face(500, 500)
    photo2 = test_upload_photo(token, event_id, photo2_image, "photo2_with_face.jpg")
    
    if not photo1 or not photo2:
        print("\n❌ Photo upload failed. Continuing with cleanup...")
        test_delete_event(token, event_id)
        return
    
    # Test 5: Verify Cloudinary URLs
    if photo1 and photo1.get("cloudinary") and photo1.get("url"):
        test_cloudinary_url_access(photo1["url"])
    
    # Test 6: Check indexing status
    print("\n--- REKOGNITION INDEXING TESTS ---")
    test_indexing_status(token, event_id, max_wait=30)
    
    # Test 7: Manual re-index (optional)
    test_manual_reindex(token, event_id)
    
    # Test 8 & 9: Selfie search
    print("\n--- SELFIE SEARCH TESTS ---")
    test_selfie_search_with_face(token, event_id)
    test_selfie_search_no_face(token, event_id)
    
    # Test 10: Delete photo
    print("\n--- CLEANUP TESTS ---")
    # Note: We'll delete the event which will cascade delete photos
    # Individual photo deletion is tested separately if needed
    
    # Test 11: Delete event
    test_delete_event(token, event_id)
    
    # Test 12: Check backend logs
    print("\n--- BACKEND LOGS CHECK ---")
    check_backend_logs()
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"Total tests: {tests_passed + tests_failed}")
    print(f"✅ Passed: {tests_passed}")
    print(f"❌ Failed: {tests_failed}")
    print()
    
    if tests_failed > 0:
        print("FAILED TESTS:")
        for result in test_results:
            if not result["passed"]:
                print(f"  ❌ {result['name']}")
                if result["details"]:
                    print(f"     {result['details']}")
    
    print("=" * 80)
    
    return tests_failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
