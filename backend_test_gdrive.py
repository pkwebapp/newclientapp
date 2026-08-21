"""
Test Google Drive gallery input validation.

Tests 3 scenarios:
1. Invalid drive link -> 400 with helpful message, no event created
2. Empty folder link -> 400 with "No photos found" message, no event created
3. Valid folder link -> 200, source=="gdrive", sync.total > 0, then cleanup
"""
import httpx
import os

# Backend URL from environment
BACKEND_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "https://pkweb-staging.preview.emergentagent.com")
API_BASE = f"{BACKEND_URL}/api"

# Admin credentials
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"


def test_gdrive_validation():
    """Test Google Drive gallery input validation."""
    print("\n" + "="*80)
    print("GOOGLE DRIVE GALLERY INPUT VALIDATION TEST")
    print("="*80)
    
    with httpx.Client(timeout=60) as client:
        # Step 1: Admin login
        print("\n[1/7] Admin login...")
        resp = client.post(f"{API_BASE}/auth/admin/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
        admin_token = resp.json()["session_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}
        print(f"✅ Admin logged in successfully")
        
        # Get initial event count
        resp = client.get(f"{API_BASE}/events", headers=headers)
        assert resp.status_code == 200
        initial_event_count = len(resp.json())
        print(f"   Initial event count: {initial_event_count}")
        
        # TEST 1: Invalid drive link
        print("\n[2/7] TEST 1: Invalid drive link -> expect 400 with helpful message...")
        resp = client.post(f"{API_BASE}/events/gdrive", headers=headers, json={
            "name": "bad",
            "category": "wedding",
            "drive_link": "not-a-valid-link"
        })
        print(f"   Status: {resp.status_code}")
        print(f"   Response: {resp.json()}")
        
        # Verify 400 status
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        
        # Verify helpful error message
        error_detail = resp.json().get("detail", "")
        assert "Google Drive" in error_detail or "folder link" in error_detail or "link" in error_detail.lower(), \
            f"Expected helpful message about Drive link, got: {error_detail}"
        print(f"✅ TEST 1 PASSED: Got 400 with message: '{error_detail}'")
        
        # Verify no event was created
        resp = client.get(f"{API_BASE}/events", headers=headers)
        assert resp.status_code == 200
        current_event_count = len(resp.json())
        assert current_event_count == initial_event_count, \
            f"Event was created! Expected {initial_event_count}, got {current_event_count}"
        print(f"✅ Confirmed: No event was created (count still {initial_event_count})")
        
        # TEST 2: Empty folder link
        print("\n[3/7] TEST 2: Empty folder link -> expect 400 with 'No photos found' message...")
        # This is a real Google Drive folder ID that exists but is empty
        empty_folder_link = "https://drive.google.com/drive/folders/0B7EVK8r0v71pZjFTYXZWM3FlRnM"
        resp = client.post(f"{API_BASE}/events/gdrive", headers=headers, json={
            "name": "empty",
            "category": "wedding",
            "drive_link": empty_folder_link
        })
        print(f"   Status: {resp.status_code}")
        print(f"   Response: {resp.json()}")
        
        # Verify 400 status
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}"
        
        # Verify "No photos found" message with sharing instructions
        error_detail = resp.json().get("detail", "")
        assert "No photos found" in error_detail or "no photos" in error_detail.lower(), \
            f"Expected 'No photos found' message, got: {error_detail}"
        assert "Anyone with the link" in error_detail or "Viewer" in error_detail or "shared" in error_detail.lower(), \
            f"Expected sharing instructions in message, got: {error_detail}"
        print(f"✅ TEST 2 PASSED: Got 400 with message: '{error_detail}'")
        
        # Verify no event was created
        resp = client.get(f"{API_BASE}/events", headers=headers)
        assert resp.status_code == 200
        current_event_count = len(resp.json())
        assert current_event_count == initial_event_count, \
            f"Event was created! Expected {initial_event_count}, got {current_event_count}"
        print(f"✅ Confirmed: No event was created (count still {initial_event_count})")
        
        # TEST 3: Valid folder link (happy path)
        print("\n[4/7] TEST 3: Valid folder link -> expect 200, source=='gdrive', sync.total > 0...")
        # This is a real public Google Drive folder with images
        valid_folder_link = "https://drive.google.com/drive/folders/1ZXEhzbLRLU1giKKRJkjm8N04cO_JoYE2"
        resp = client.post(f"{API_BASE}/events/gdrive", headers=headers, json={
            "name": "GDrive OK",
            "category": "wedding",
            "drive_link": valid_folder_link
        })
        print(f"   Status: {resp.status_code}")
        
        # Verify 200 status
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        
        data = resp.json()
        print(f"   Response keys: {list(data.keys())}")
        
        # Verify source == "gdrive"
        assert data.get("source") == "gdrive", f"Expected source='gdrive', got: {data.get('source')}"
        print(f"✅ Verified: source == 'gdrive'")
        
        # Verify sync.total > 0
        sync = data.get("sync", {})
        sync_total = sync.get("total", 0)
        assert sync_total > 0, f"Expected sync.total > 0, got: {sync_total}"
        print(f"✅ Verified: sync.total = {sync_total} (> 0)")
        
        # Store event_id for cleanup
        event_id = data.get("event_id")
        assert event_id, "No event_id in response"
        print(f"✅ TEST 3 PASSED: Event created with event_id={event_id}")
        print(f"   Event details: name='{data.get('name')}', photo_count={data.get('photo_count')}, "
              f"indexing_status='{data.get('indexing_status')}'")
        print(f"   Sync details: added={sync.get('added')}, updated={sync.get('updated')}, removed={sync.get('removed')}")
        
        # Verify event was created
        resp = client.get(f"{API_BASE}/events", headers=headers)
        assert resp.status_code == 200
        current_event_count = len(resp.json())
        assert current_event_count == initial_event_count + 1, \
            f"Event count mismatch! Expected {initial_event_count + 1}, got {current_event_count}"
        print(f"✅ Confirmed: Event was created (count now {current_event_count})")
        
        # Step 5: Cleanup - Delete the event
        print(f"\n[5/7] Cleanup: Deleting event {event_id}...")
        resp = client.delete(f"{API_BASE}/events/{event_id}", headers=headers)
        print(f"   Status: {resp.status_code}")
        
        assert resp.status_code == 200, f"Delete failed: {resp.status_code} {resp.text}"
        delete_data = resp.json()
        print(f"✅ Event deleted successfully")
        print(f"   Deletion details: status='{delete_data.get('status')}', "
              f"photos_removed={delete_data.get('photos_removed')}, "
              f"cloudinary_objects_deleted={delete_data.get('cloudinary_objects_deleted')}, "
              f"faces_collection_deleted={delete_data.get('faces_collection_deleted')}")
        
        # Verify event was deleted
        print(f"\n[6/7] Verifying event was deleted...")
        resp = client.get(f"{API_BASE}/events/{event_id}", headers=headers)
        assert resp.status_code == 404, f"Event still exists! Expected 404, got {resp.status_code}"
        print(f"✅ Confirmed: Event no longer exists (404)")
        
        # Verify event count is back to initial
        resp = client.get(f"{API_BASE}/events", headers=headers)
        assert resp.status_code == 200
        final_event_count = len(resp.json())
        assert final_event_count == initial_event_count, \
            f"Event count mismatch after cleanup! Expected {initial_event_count}, got {final_event_count}"
        print(f"✅ Confirmed: Event count back to initial ({initial_event_count})")
        
        print("\n[7/7] SUMMARY")
        print("="*80)
        print("✅ TEST 1 PASSED: Invalid drive link -> 400 with helpful message, no event created")
        print("✅ TEST 2 PASSED: Empty folder link -> 400 with 'No photos found' message, no event created")
        print("✅ TEST 3 PASSED: Valid folder link -> 200, source=='gdrive', sync.total > 0, cleanup successful")
        print("="*80)
        print("🎉 ALL TESTS PASSED - Google Drive validation working correctly!")
        print("="*80)


if __name__ == "__main__":
    test_gdrive_validation()
