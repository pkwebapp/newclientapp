#!/usr/bin/env python3
"""
Backend test for same-event cover photo feature.
Tests that client dashboard event covers are sourced from the same event only.
"""
import requests
import io
from PIL import Image

BASE_URL = "https://newclient-app-1.preview.emergentagent.com/api"

# Admin credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

def create_test_image(width=400, height=400, color=(255, 0, 0)):
    """Create a small test JPEG image."""
    img = Image.new('RGB', (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    buf.seek(0)
    return buf

def test_same_event_cover():
    """Test same-event cover photo backend behavior."""
    print("=" * 80)
    print("BACKEND TEST: Same-Event Cover Photo")
    print("=" * 80)
    
    admin_token = None
    client_token = None
    event1_id = None
    event2_id = None
    event3_id = None
    photo1_id = None
    photo2_id = None
    photo3_id = None
    client_phone = "+919876540001"
    
    try:
        # ===== TEST 1: Admin login =====
        print("\n[TEST 1] Admin login...")
        resp = requests.post(f"{BASE_URL}/auth/admin/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
        admin_token = resp.json()["session_token"]
        print(f"✅ Admin login successful")
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # ===== TEST 2: Create event WITH explicit cover_path =====
        print("\n[TEST 2] Create event with explicit cover_path...")
        resp = requests.post(f"{BASE_URL}/events", headers=headers, json={
            "name": "QA Event With Cover",
            "category": "wedding",
            "date": "2026-03-15"
        })
        assert resp.status_code == 200, f"Create event failed: {resp.status_code} {resp.text}"
        event1_id = resp.json()["event_id"]
        print(f"✅ Created event1: {event1_id}")
        
        # Upload a photo to event1 and set it as cover
        print("   Uploading photo to event1...")
        img_buf = create_test_image(color=(255, 0, 0))  # Red image
        resp = requests.post(
            f"{BASE_URL}/events/{event1_id}/photos",
            headers=headers,
            files={"file": ("test1.jpg", img_buf, "image/jpeg")}
        )
        assert resp.status_code == 200, f"Upload photo failed: {resp.status_code} {resp.text}"
        photo1_id = resp.json()["photo_id"]
        photo1_storage_path = resp.json().get("storage_path")
        photo1_thumb_path = resp.json().get("thumb_path")
        print(f"✅ Uploaded photo1: {photo1_id}")
        print(f"   storage_path: {photo1_storage_path}")
        print(f"   thumb_path: {photo1_thumb_path}")
        
        # Set explicit cover_path for event1
        print("   Setting explicit cover_path for event1...")
        cover_path_to_set = photo1_thumb_path or photo1_storage_path
        resp = requests.patch(f"{BASE_URL}/events/{event1_id}", headers=headers, json={
            "cover_path": cover_path_to_set
        })
        assert resp.status_code == 200, f"Set cover_path failed: {resp.status_code} {resp.text}"
        print(f"✅ Set cover_path: {cover_path_to_set}")
        
        # ===== TEST 3: Create event WITHOUT cover_path but WITH photos =====
        print("\n[TEST 3] Create event without cover_path but with photos...")
        resp = requests.post(f"{BASE_URL}/events", headers=headers, json={
            "name": "QA Event No Cover",
            "category": "portrait",
            "date": "2026-04-20"
        })
        assert resp.status_code == 200, f"Create event failed: {resp.status_code} {resp.text}"
        event2_id = resp.json()["event_id"]
        print(f"✅ Created event2: {event2_id}")
        
        # Upload two photos to event2 (no explicit cover)
        print("   Uploading photo 2a to event2...")
        img_buf = create_test_image(color=(0, 255, 0))  # Green image
        resp = requests.post(
            f"{BASE_URL}/events/{event2_id}/photos",
            headers=headers,
            files={"file": ("test2a.jpg", img_buf, "image/jpeg")}
        )
        assert resp.status_code == 200, f"Upload photo failed: {resp.status_code} {resp.text}"
        photo2_id = resp.json()["photo_id"]
        photo2_storage_path = resp.json().get("storage_path")
        photo2_thumb_path = resp.json().get("thumb_path")
        print(f"✅ Uploaded photo2a: {photo2_id}")
        print(f"   storage_path: {photo2_storage_path}")
        print(f"   thumb_path: {photo2_thumb_path}")
        
        print("   Uploading photo 2b to event2...")
        img_buf = create_test_image(color=(0, 0, 255))  # Blue image
        resp = requests.post(
            f"{BASE_URL}/events/{event2_id}/photos",
            headers=headers,
            files={"file": ("test2b.jpg", img_buf, "image/jpeg")}
        )
        assert resp.status_code == 200, f"Upload photo failed: {resp.status_code} {resp.text}"
        photo3_id = resp.json()["photo_id"]
        print(f"✅ Uploaded photo2b: {photo3_id}")
        
        # ===== TEST 4: Create event WITHOUT cover_path and WITHOUT photos =====
        print("\n[TEST 4] Create event without cover_path and without photos...")
        resp = requests.post(f"{BASE_URL}/events", headers=headers, json={
            "name": "QA Event Empty",
            "category": "event",
            "date": "2026-05-10"
        })
        assert resp.status_code == 200, f"Create event failed: {resp.status_code} {resp.text}"
        event3_id = resp.json()["event_id"]
        print(f"✅ Created event3 (empty): {event3_id}")
        
        # ===== TEST 5: Grant client access to all three events =====
        print("\n[TEST 5] Grant client access to all three events...")
        for event_id in [event1_id, event2_id, event3_id]:
            resp = requests.post(
                f"{BASE_URL}/events/{event_id}/access",
                headers=headers,
                json={
                    "channel": "phone",
                    "phone": client_phone,
                    "full_gallery_access": True
                }
            )
            assert resp.status_code == 200, f"Grant access failed: {resp.status_code} {resp.text}"
            print(f"✅ Granted access to {event_id}")
        
        # ===== TEST 6: Client OTP login =====
        print("\n[TEST 6] Client OTP login...")
        resp = requests.post(f"{BASE_URL}/auth/client/request-otp", json={
            "channel": "phone",
            "phone": client_phone
        })
        assert resp.status_code == 200, f"Request OTP failed: {resp.status_code} {resp.text}"
        dev_code = resp.json().get("dev_code")
        print(f"✅ OTP requested, dev_code: {dev_code}")
        
        resp = requests.post(f"{BASE_URL}/auth/client/verify-otp", json={
            "channel": "phone",
            "phone": client_phone,
            "code": dev_code
        })
        assert resp.status_code == 200, f"Verify OTP failed: {resp.status_code} {resp.text}"
        client_token = resp.json()["session_token"]
        print(f"✅ Client logged in successfully")
        
        client_headers = {"Authorization": f"Bearer {client_token}"}
        
        # ===== TEST 7: GET /api/me/dashboard and validate cover fields =====
        print("\n[TEST 7] GET /api/me/dashboard and validate cover fields...")
        resp = requests.get(f"{BASE_URL}/me/dashboard", headers=client_headers)
        assert resp.status_code == 200, f"Dashboard failed: {resp.status_code} {resp.text}"
        dashboard = resp.json()
        print(f"✅ Dashboard retrieved successfully")
        
        memories = dashboard.get("memories", [])
        print(f"   Found {len(memories)} memories")
        
        # Find our test events in memories
        event1_memory = None
        event2_memory = None
        event3_memory = None
        
        for mem in memories:
            if mem.get("event_id") == event1_id:
                event1_memory = mem
            elif mem.get("event_id") == event2_id:
                event2_memory = mem
            elif mem.get("event_id") == event3_id:
                event3_memory = mem
        
        # ===== TEST 8: Validate event1 (WITH explicit cover_path) =====
        print("\n[TEST 8] Validate event1 cover (explicit cover_path)...")
        assert event1_memory is not None, "Event1 not found in memories"
        print(f"   Event1 memory: {event1_memory}")
        
        event1_cover_path = event1_memory.get("cover_path")
        event1_cover_url = event1_memory.get("cover_url")
        event1_cover_drive_id = event1_memory.get("cover_drive_id")
        
        print(f"   cover_path: {event1_cover_path}")
        print(f"   cover_url: {event1_cover_url}")
        print(f"   cover_drive_id: {event1_cover_drive_id}")
        
        assert event1_cover_path == cover_path_to_set, \
            f"Event1 cover_path mismatch: expected {cover_path_to_set}, got {event1_cover_path}"
        print(f"✅ Event1 cover_path matches explicit cover: {event1_cover_path}")
        
        # ===== TEST 9: Validate event2 (NO cover_path, fallback to first photo) =====
        print("\n[TEST 9] Validate event2 cover (fallback to first photo)...")
        assert event2_memory is not None, "Event2 not found in memories"
        print(f"   Event2 memory: {event2_memory}")
        
        event2_cover_path = event2_memory.get("cover_path")
        event2_cover_url = event2_memory.get("cover_url")
        event2_cover_drive_id = event2_memory.get("cover_drive_id")
        
        print(f"   cover_path: {event2_cover_path}")
        print(f"   cover_url: {event2_cover_url}")
        print(f"   cover_drive_id: {event2_cover_drive_id}")
        
        # Should fallback to first photo's thumb_path or storage_path
        expected_cover = photo2_thumb_path or photo2_storage_path
        assert event2_cover_path == expected_cover, \
            f"Event2 cover_path mismatch: expected {expected_cover}, got {event2_cover_path}"
        print(f"✅ Event2 cover_path correctly falls back to first photo: {event2_cover_path}")
        
        # Verify it's from event2, not event1 or event3
        assert event1_id not in (event2_cover_path or ""), \
            f"Event2 cover_path incorrectly references event1"
        assert event3_id not in (event2_cover_path or ""), \
            f"Event2 cover_path incorrectly references event3"
        assert event2_id in (event2_cover_path or ""), \
            f"Event2 cover_path does not reference event2"
        print(f"✅ Event2 cover is from same event (event2_id in path)")
        
        # ===== TEST 10: Validate event3 (NO cover_path, NO photos) =====
        print("\n[TEST 10] Validate event3 cover (no cover, no photos)...")
        assert event3_memory is not None, "Event3 not found in memories"
        print(f"   Event3 memory: {event3_memory}")
        
        event3_cover_path = event3_memory.get("cover_path")
        event3_cover_url = event3_memory.get("cover_url")
        event3_cover_drive_id = event3_memory.get("cover_drive_id")
        
        print(f"   cover_path: {event3_cover_path}")
        print(f"   cover_url: {event3_cover_url}")
        print(f"   cover_drive_id: {event3_cover_drive_id}")
        
        assert event3_cover_path is None, \
            f"Event3 cover_path should be None, got {event3_cover_path}"
        assert event3_cover_drive_id is None, \
            f"Event3 cover_drive_id should be None, got {event3_cover_drive_id}"
        assert event3_cover_url is None, \
            f"Event3 cover_url should be None, got {event3_cover_url}"
        print(f"✅ Event3 correctly has no cover (all fields None)")
        
        # ===== TEST 11: Verify existing auth and event APIs remain 200 =====
        print("\n[TEST 11] Verify existing auth and event APIs remain 200...")
        
        # Health check
        resp = requests.get(f"{BASE_URL}/")
        assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
        print(f"✅ GET /api/ → 200")
        
        # List events (admin)
        resp = requests.get(f"{BASE_URL}/events", headers=headers)
        assert resp.status_code == 200, f"List events failed: {resp.status_code}"
        print(f"✅ GET /api/events (admin) → 200")
        
        # Get event detail (admin)
        resp = requests.get(f"{BASE_URL}/events/{event1_id}", headers=headers)
        assert resp.status_code == 200, f"Get event failed: {resp.status_code}"
        print(f"✅ GET /api/events/{event1_id} (admin) → 200")
        
        # List client events
        resp = requests.get(f"{BASE_URL}/client/events", headers=client_headers)
        assert resp.status_code == 200, f"List client events failed: {resp.status_code}"
        print(f"✅ GET /api/client/events (client) → 200")
        
        # Get client event photos
        resp = requests.get(f"{BASE_URL}/client/events/{event1_id}/photos", headers=client_headers)
        assert resp.status_code == 200, f"Get client photos failed: {resp.status_code}"
        print(f"✅ GET /api/client/events/{event1_id}/photos (client) → 200")
        
        print("\n" + "=" * 80)
        print("ALL TESTS PASSED ✅")
        print("=" * 80)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        raise
    finally:
        # ===== CLEANUP =====
        print("\n" + "=" * 80)
        print("CLEANUP: Deleting throwaway resources...")
        print("=" * 80)
        
        if admin_token:
            headers = {"Authorization": f"Bearer {admin_token}"}
            
            # Delete events (this also deletes photos and grants)
            for event_id in [event1_id, event2_id, event3_id]:
                if event_id:
                    try:
                        resp = requests.delete(f"{BASE_URL}/events/{event_id}", headers=headers)
                        if resp.status_code == 200:
                            print(f"✅ Deleted event: {event_id}")
                        else:
                            print(f"⚠️  Failed to delete event {event_id}: {resp.status_code}")
                    except Exception as e:
                        print(f"⚠️  Error deleting event {event_id}: {e}")
            
            # Delete client user (created via OTP)
            if client_phone:
                try:
                    # Find and delete the client user
                    # Note: There's no direct API to delete client users, but deleting events
                    # should clean up access grants. The user record may remain but that's OK.
                    print(f"ℹ️  Client user for {client_phone} may remain (no delete API)")
                except Exception as e:
                    print(f"⚠️  Error with client cleanup: {e}")
        
        print("\n" + "=" * 80)
        print("CLEANUP COMPLETE")
        print("=" * 80)

if __name__ == "__main__":
    test_same_event_cover()
