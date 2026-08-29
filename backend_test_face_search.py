#!/usr/bin/env python3
"""Backend-only verification for per-gallery face-search toggle feature."""
import io
import sys
import time
import requests
from PIL import Image

# Backend URL from frontend/.env
BASE_URL = "https://client-dashboard-207.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

def create_test_jpeg():
    """Create a small valid JPEG for upload testing."""
    img = Image.new('RGB', (200, 200), color='blue')
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return buf

def test_face_search_toggle():
    """Test the per-gallery face-search toggle feature."""
    print("=" * 80)
    print("BACKEND TEST: Per-Gallery Face-Search Toggle")
    print("=" * 80)
    
    # Step 1: Admin login
    print("\n[1/9] Admin login...")
    resp = requests.post(f"{BASE_URL}/auth/admin/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code != 200:
        print(f"❌ FAIL: Admin login failed with {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    admin_data = resp.json()
    admin_token = admin_data["session_token"]
    print(f"✅ PASS: Admin logged in (token: {admin_token[:20]}...)")
    
    # Step 2: Create event with face_search_enabled=false
    print("\n[2/9] Creating event with face_search_enabled=false...")
    resp = requests.post(f"{BASE_URL}/events", 
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Face Search Off QA",
            "category": "event",
            "face_search_enabled": False
        }
    )
    if resp.status_code != 200:
        print(f"❌ FAIL: Event creation failed with {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    event_data = resp.json()
    event_id = event_data["event_id"]
    
    # Verify face_search_enabled=false in response
    if event_data.get("face_search_enabled") != False:
        print(f"❌ FAIL: face_search_enabled should be false, got: {event_data.get('face_search_enabled')}")
        print(f"Response: {event_data}")
        return False
    
    # Verify indexing_status is 'empty' or 'disabled'
    indexing_status = event_data.get("indexing_status")
    if indexing_status not in ["empty", "disabled"]:
        print(f"❌ FAIL: indexing_status should be 'empty' or 'disabled', got: {indexing_status}")
        print(f"Response: {event_data}")
        return False
    
    print(f"✅ PASS: Event created with face_search_enabled=false, indexing_status={indexing_status} (event_id: {event_id})")
    
    # Step 3: Upload a small valid JPEG
    print(f"\n[3/9] Uploading photo to event with face_search_enabled=false...")
    test_image = create_test_jpeg()
    resp = requests.post(f"{BASE_URL}/events/{event_id}/photos",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("test.jpg", test_image, "image/jpeg")}
    )
    if resp.status_code != 200:
        print(f"❌ FAIL: Photo upload failed with {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    photo_data = resp.json()
    photo_id = photo_data["photo_id"]
    
    # Verify photo indexing_status is 'disabled' (not 'pending' or 'indexing')
    photo_indexing_status = photo_data.get("indexing_status")
    if photo_indexing_status != "disabled":
        print(f"❌ FAIL: Photo indexing_status should be 'disabled', got: {photo_indexing_status}")
        print(f"Response: {photo_data}")
        return False
    
    print(f"✅ PASS: Photo uploaded successfully with indexing_status=disabled (photo_id: {photo_id})")
    
    # Step 4: Check indexing-status endpoint
    print(f"\n[4/9] Checking indexing-status endpoint...")
    resp = requests.get(f"{BASE_URL}/events/{event_id}/indexing-status",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    if resp.status_code != 200:
        print(f"❌ FAIL: Indexing status check failed with {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    indexing_data = resp.json()
    
    # Verify status is 'disabled' or 'complete' with zero faces
    status = indexing_data.get("status")
    faces = indexing_data.get("faces", 0)
    
    if status not in ["disabled", "complete"]:
        print(f"❌ FAIL: Indexing status should be 'disabled' or 'complete', got: {status}")
        print(f"Response: {indexing_data}")
        return False
    
    if faces != 0:
        print(f"❌ FAIL: Faces count should be 0, got: {faces}")
        print(f"Response: {indexing_data}")
        return False
    
    print(f"✅ PASS: Indexing status is {status} with {faces} faces")
    
    # Step 5: Verify GET event still exposes face_search_enabled=false
    print(f"\n[5/9] Verifying GET event exposes face_search_enabled=false...")
    resp = requests.get(f"{BASE_URL}/events/{event_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    if resp.status_code != 200:
        print(f"❌ FAIL: GET event failed with {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    event_data = resp.json()
    
    if event_data.get("face_search_enabled") != False:
        print(f"❌ FAIL: face_search_enabled should be false, got: {event_data.get('face_search_enabled')}")
        print(f"Response: {event_data}")
        return False
    
    print(f"✅ PASS: GET event confirms face_search_enabled=false")
    
    # Step 6: Register a throwaway public/client visitor
    print(f"\n[6/9] Registering throwaway public visitor...")
    resp = requests.post(f"{BASE_URL}/public/events/{event_id}/access",
        json={
            "name": "QA Visitor Face Search Test",
            "phone": "+919876543210"
        }
    )
    if resp.status_code != 200:
        print(f"❌ FAIL: Public access registration failed with {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    visitor_data = resp.json()
    visitor_token = visitor_data["session_token"]
    print(f"✅ PASS: Visitor registered (token: {visitor_token[:20]}...)")
    
    # Step 7: Give consent if required
    print(f"\n[7/9] Giving biometric consent...")
    resp = requests.post(f"{BASE_URL}/client/events/{event_id}/consent",
        headers={"Authorization": f"Bearer {visitor_token}"},
        json={"accepted": True}
    )
    if resp.status_code != 200:
        print(f"❌ FAIL: Consent failed with {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    print(f"✅ PASS: Consent given")
    
    # Step 8: Attempt selfie search (should return 403 with face-search-disabled message)
    print(f"\n[8/9] Attempting selfie search (should return 403)...")
    test_selfie = create_test_jpeg()
    resp = requests.post(f"{BASE_URL}/client/events/{event_id}/search",
        headers={"Authorization": f"Bearer {visitor_token}"},
        files={"file": ("selfie.jpg", test_selfie, "image/jpeg")}
    )
    
    if resp.status_code != 403:
        print(f"❌ FAIL: Expected 403, got {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    
    # Verify the error message is about face search being disabled
    error_detail = resp.json().get("detail", "")
    if "face search" not in error_detail.lower() or "disabled" not in error_detail.lower():
        print(f"❌ FAIL: Expected face-search-disabled message, got: {error_detail}")
        return False
    
    print(f"✅ PASS: Selfie search correctly returned 403 with message: '{error_detail}'")
    
    # Step 9: Delete the throwaway event and verify cleanup
    print(f"\n[9/9] Deleting throwaway event...")
    resp = requests.delete(f"{BASE_URL}/events/{event_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    if resp.status_code != 200:
        print(f"❌ FAIL: Event deletion failed with {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    delete_data = resp.json()
    
    # Verify cleanup results
    print(f"   Cleanup results:")
    print(f"   - Status: {delete_data.get('status')}")
    print(f"   - Photos removed: {delete_data.get('photos_removed')}")
    print(f"   - Cloudinary objects deleted: {delete_data.get('cloudinary_objects_deleted')}")
    print(f"   - Faces collection deleted: {delete_data.get('faces_collection_deleted')}")
    
    print(f"✅ PASS: Event deleted successfully")
    
    # Verify event is gone
    resp = requests.get(f"{BASE_URL}/events/{event_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    if resp.status_code != 404:
        print(f"❌ FAIL: Event should be 404 after deletion, got {resp.status_code}")
        return False
    
    print(f"✅ PASS: Event confirmed deleted (404)")
    
    return True

def test_default_face_search_enabled():
    """Test that face_search_enabled defaults to true when not specified."""
    print("\n" + "=" * 80)
    print("BACKEND TEST: Default face_search_enabled=true")
    print("=" * 80)
    
    # Step 1: Admin login
    print("\n[1/3] Admin login...")
    resp = requests.post(f"{BASE_URL}/auth/admin/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    if resp.status_code != 200:
        print(f"❌ FAIL: Admin login failed with {resp.status_code}")
        return False
    admin_token = resp.json()["session_token"]
    print(f"✅ PASS: Admin logged in")
    
    # Step 2: Create event WITHOUT face_search_enabled flag
    print("\n[2/3] Creating event without face_search_enabled flag...")
    resp = requests.post(f"{BASE_URL}/events", 
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Face Search Default QA",
            "category": "event"
        }
    )
    if resp.status_code != 200:
        print(f"❌ FAIL: Event creation failed with {resp.status_code}")
        print(f"Response: {resp.text}")
        return False
    event_data = resp.json()
    event_id = event_data["event_id"]
    
    # Verify face_search_enabled defaults to true
    if event_data.get("face_search_enabled") != True:
        print(f"❌ FAIL: face_search_enabled should default to true, got: {event_data.get('face_search_enabled')}")
        print(f"Response: {event_data}")
        return False
    
    print(f"✅ PASS: Event created with face_search_enabled=true (default) (event_id: {event_id})")
    
    # Step 3: Delete the event
    print(f"\n[3/3] Deleting throwaway event...")
    resp = requests.delete(f"{BASE_URL}/events/{event_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    if resp.status_code != 200:
        print(f"❌ FAIL: Event deletion failed with {resp.status_code}")
        return False
    
    print(f"✅ PASS: Event deleted successfully")
    
    return True

def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("STARTING BACKEND TESTS FOR FACE-SEARCH TOGGLE FEATURE")
    print("=" * 80)
    
    all_passed = True
    
    # Test 1: Face search disabled
    if not test_face_search_toggle():
        print("\n❌ OVERALL: Face search toggle test FAILED")
        all_passed = False
    else:
        print("\n✅ OVERALL: Face search toggle test PASSED")
    
    # Test 2: Default behavior
    if not test_default_face_search_enabled():
        print("\n❌ OVERALL: Default face_search_enabled test FAILED")
        all_passed = False
    else:
        print("\n✅ OVERALL: Default face_search_enabled test PASSED")
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 80)
        return 1

if __name__ == "__main__":
    sys.exit(main())
