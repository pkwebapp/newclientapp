#!/usr/bin/env python3
"""
Backend regression test for likes/activity visibility bug fix.

Bug: Liked photos and user activity were invisible to admins until face scan,
including galleries with face search disabled.

Fix: Admin event client aggregation now includes all users found in client albums,
gallery visitors, or photo likes. Admin rows show matched count, liked count,
activity count, and last activity, and liked-photo drill-down remains available
even without a face scan or when face search is disabled.

Test scenarios:
1. Gallery with face_search_enabled=true, client does NOT complete face scan, likes photo
2. Gallery with face_search_enabled=false, client likes photo
3. Verify admin GET /api/events/{event_id}/clients shows clients with liked_count > 0
4. Verify admin GET /api/events/{event_id}/clients/{client_user_id}/photos returns liked photos
5. Verify list_visitors still reports liked_count
"""

import requests
import json
import time
from io import BytesIO
from PIL import Image

# Backend URL from frontend/.env
BACKEND_URL = "https://app-hub-525.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

# Test data
TEST_CLIENT_1_PHONE = "+919876540001"
TEST_CLIENT_1_NAME = "Test Client Alpha"
TEST_CLIENT_2_PHONE = "+919876540002"
TEST_CLIENT_2_NAME = "Test Client Beta"


def create_test_image(width=400, height=400):
    """Create a small test JPEG image."""
    img = Image.new('RGB', (width, height), color='lightblue')
    buf = BytesIO()
    img.save(buf, format='JPEG', quality=85)
    buf.seek(0)
    return buf


def log_test(test_num, description):
    """Log test step."""
    print(f"\n{'='*80}")
    print(f"TEST {test_num}: {description}")
    print('='*80)


def log_result(status, message):
    """Log test result."""
    symbol = "✅" if status == "PASS" else "❌"
    print(f"{symbol} {status}: {message}")


def main():
    print("\n" + "="*80)
    print("BACKEND REGRESSION TEST: Likes/Activity Visibility Bug Fix")
    print("="*80)
    
    admin_token = None
    event1_id = None  # face_search_enabled=true
    event2_id = None  # face_search_enabled=false
    photo1_id = None
    photo2_id = None
    client1_token = None
    client1_user_id = None
    client2_token = None
    client2_user_id = None
    
    try:
        # =====================================================================
        # SETUP: Admin login
        # =====================================================================
        log_test(1, "Admin login")
        resp = requests.post(
            f"{BACKEND_URL}/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
        admin_token = resp.json()["session_token"]
        log_result("PASS", f"Admin logged in, token length: {len(admin_token)}")
        
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        
        # =====================================================================
        # SETUP: Create event 1 with face_search_enabled=true
        # =====================================================================
        log_test(2, "Create event 1 (face_search_enabled=true)")
        resp = requests.post(
            f"{BACKEND_URL}/events",
            headers=admin_headers,
            json={
                "name": "QA Test Event 1 - Face Search ON",
                "category": "wedding",
                "face_search_enabled": True
            }
        )
        assert resp.status_code == 200, f"Create event 1 failed: {resp.status_code} {resp.text}"
        event1_id = resp.json()["event_id"]
        face_search_1 = resp.json().get("face_search_enabled")
        log_result("PASS", f"Event 1 created: {event1_id}, face_search_enabled={face_search_1}")
        
        # =====================================================================
        # SETUP: Create event 2 with face_search_enabled=false
        # =====================================================================
        log_test(3, "Create event 2 (face_search_enabled=false)")
        resp = requests.post(
            f"{BACKEND_URL}/events",
            headers=admin_headers,
            json={
                "name": "QA Test Event 2 - Face Search OFF",
                "category": "event",
                "face_search_enabled": False
            }
        )
        assert resp.status_code == 200, f"Create event 2 failed: {resp.status_code} {resp.text}"
        event2_id = resp.json()["event_id"]
        face_search_2 = resp.json().get("face_search_enabled")
        log_result("PASS", f"Event 2 created: {event2_id}, face_search_enabled={face_search_2}")
        
        # =====================================================================
        # SETUP: Upload photo to event 1
        # =====================================================================
        log_test(4, "Upload photo to event 1")
        img_buf = create_test_image()
        resp = requests.post(
            f"{BACKEND_URL}/events/{event1_id}/photos",
            headers=admin_headers,
            files={"file": ("test_photo_1.jpg", img_buf, "image/jpeg")}
        )
        assert resp.status_code == 200, f"Upload photo 1 failed: {resp.status_code} {resp.text}"
        photo1_id = resp.json()["photo_id"]
        log_result("PASS", f"Photo 1 uploaded: {photo1_id}")
        
        # =====================================================================
        # SETUP: Upload photo to event 2
        # =====================================================================
        log_test(5, "Upload photo to event 2")
        img_buf = create_test_image()
        resp = requests.post(
            f"{BACKEND_URL}/events/{event2_id}/photos",
            headers=admin_headers,
            files={"file": ("test_photo_2.jpg", img_buf, "image/jpeg")}
        )
        assert resp.status_code == 200, f"Upload photo 2 failed: {resp.status_code} {resp.text}"
        photo2_id = resp.json()["photo_id"]
        log_result("PASS", f"Photo 2 uploaded: {photo2_id}")
        
        # Wait for indexing to complete
        print("\nWaiting for background indexing to complete...")
        time.sleep(2)
        
        # =====================================================================
        # SETUP: Client 1 - Request OTP
        # =====================================================================
        log_test(6, "Client 1 - Request OTP (for event 1)")
        resp = requests.post(
            f"{BACKEND_URL}/auth/client/request-otp",
            json={"channel": "phone", "phone": TEST_CLIENT_1_PHONE}
        )
        assert resp.status_code == 200, f"Client 1 OTP request failed: {resp.status_code} {resp.text}"
        dev_code_1 = resp.json().get("dev_code")
        assert dev_code_1, "OTP_DEV_MODE should return dev_code"
        log_result("PASS", f"Client 1 OTP requested, dev_code: {dev_code_1}")
        
        # =====================================================================
        # SETUP: Client 1 - Verify OTP
        # =====================================================================
        log_test(7, "Client 1 - Verify OTP")
        resp = requests.post(
            f"{BACKEND_URL}/auth/client/verify-otp",
            json={"channel": "phone", "phone": TEST_CLIENT_1_PHONE, "code": dev_code_1}
        )
        assert resp.status_code == 200, f"Client 1 OTP verify failed: {resp.status_code} {resp.text}"
        client1_token = resp.json()["session_token"]
        client1_user_id = resp.json()["user"]["user_id"]
        log_result("PASS", f"Client 1 logged in, user_id: {client1_user_id}")
        
        client1_headers = {"Authorization": f"Bearer {client1_token}"}
        
        # =====================================================================
        # SETUP: Client 1 - Register as visitor for event 1 (NO face scan)
        # =====================================================================
        log_test(8, "Client 1 - Register as visitor for event 1 (NO face scan)")
        resp = requests.post(
            f"{BACKEND_URL}/public/events/{event1_id}/access",
            json={"name": TEST_CLIENT_1_NAME, "phone": TEST_CLIENT_1_PHONE}
        )
        assert resp.status_code == 200, f"Client 1 visitor registration failed: {resp.status_code} {resp.text}"
        log_result("PASS", f"Client 1 registered as visitor for event 1 (NO face scan performed)")
        
        # =====================================================================
        # TEST: Client 1 - Like photo in event 1 (face_search_enabled=true, NO face scan)
        # =====================================================================
        log_test(9, "Client 1 - Like photo in event 1 (NO face scan completed)")
        resp = requests.post(
            f"{BACKEND_URL}/client/events/{event1_id}/photos/{photo1_id}/like",
            headers=client1_headers
        )
        assert resp.status_code == 200, f"Client 1 like photo failed: {resp.status_code} {resp.text}"
        liked_status = resp.json().get("liked")
        assert liked_status == True, f"Expected liked=True, got {liked_status}"
        log_result("PASS", f"Client 1 liked photo in event 1 (face_search_enabled=true, NO face scan)")
        
        # =====================================================================
        # SETUP: Client 2 - Request OTP
        # =====================================================================
        log_test(10, "Client 2 - Request OTP (for event 2)")
        resp = requests.post(
            f"{BACKEND_URL}/auth/client/request-otp",
            json={"channel": "phone", "phone": TEST_CLIENT_2_PHONE}
        )
        assert resp.status_code == 200, f"Client 2 OTP request failed: {resp.status_code} {resp.text}"
        dev_code_2 = resp.json().get("dev_code")
        assert dev_code_2, "OTP_DEV_MODE should return dev_code"
        log_result("PASS", f"Client 2 OTP requested, dev_code: {dev_code_2}")
        
        # =====================================================================
        # SETUP: Client 2 - Verify OTP
        # =====================================================================
        log_test(11, "Client 2 - Verify OTP")
        resp = requests.post(
            f"{BACKEND_URL}/auth/client/verify-otp",
            json={"channel": "phone", "phone": TEST_CLIENT_2_PHONE, "code": dev_code_2}
        )
        assert resp.status_code == 200, f"Client 2 OTP verify failed: {resp.status_code} {resp.text}"
        client2_token = resp.json()["session_token"]
        client2_user_id = resp.json()["user"]["user_id"]
        log_result("PASS", f"Client 2 logged in, user_id: {client2_user_id}")
        
        client2_headers = {"Authorization": f"Bearer {client2_token}"}
        
        # =====================================================================
        # SETUP: Client 2 - Register as visitor for event 2
        # =====================================================================
        log_test(12, "Client 2 - Register as visitor for event 2 (face_search_enabled=false)")
        resp = requests.post(
            f"{BACKEND_URL}/public/events/{event2_id}/access",
            json={"name": TEST_CLIENT_2_NAME, "phone": TEST_CLIENT_2_PHONE}
        )
        assert resp.status_code == 200, f"Client 2 visitor registration failed: {resp.status_code} {resp.text}"
        log_result("PASS", f"Client 2 registered as visitor for event 2 (face search disabled)")
        
        # =====================================================================
        # TEST: Client 2 - Like photo in event 2 (face_search_enabled=false)
        # =====================================================================
        log_test(13, "Client 2 - Like photo in event 2 (face_search_enabled=false)")
        resp = requests.post(
            f"{BACKEND_URL}/client/events/{event2_id}/photos/{photo2_id}/like",
            headers=client2_headers
        )
        assert resp.status_code == 200, f"Client 2 like photo failed: {resp.status_code} {resp.text}"
        liked_status = resp.json().get("liked")
        assert liked_status == True, f"Expected liked=True, got {liked_status}"
        log_result("PASS", f"Client 2 liked photo in event 2 (face_search_enabled=false)")
        
        # =====================================================================
        # CRITICAL TEST: Admin GET /api/events/{event1_id}/clients
        # Should show client 1 with liked_count > 0, activity_count > 0, last_activity_at
        # =====================================================================
        log_test(14, "Admin GET /api/events/{event1_id}/clients (face_search_enabled=true, NO face scan)")
        resp = requests.get(
            f"{BACKEND_URL}/events/{event1_id}/clients",
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Admin get clients failed: {resp.status_code} {resp.text}"
        clients_list = resp.json()
        log_result("PASS", f"Admin GET /api/events/{event1_id}/clients returned {len(clients_list)} client(s)")
        
        # Find client 1 in the list
        client1_data = None
        for client in clients_list:
            if client.get("client_user_id") == client1_user_id:
                client1_data = client
                break
        
        assert client1_data is not None, f"Client 1 ({client1_user_id}) NOT FOUND in clients list! Bug not fixed."
        log_result("PASS", f"✅ BUG FIX VERIFIED: Client 1 appears in clients list even without face scan")
        
        # Verify client 1 data
        liked_count = client1_data.get("liked_count", 0)
        activity_count = client1_data.get("activity_count", 0)
        last_activity_at = client1_data.get("last_activity_at")
        matched_count = client1_data.get("matched_count", 0)
        
        print(f"\nClient 1 data:")
        print(f"  - name: {client1_data.get('name')}")
        print(f"  - phone: {client1_data.get('phone')}")
        print(f"  - matched_count: {matched_count}")
        print(f"  - liked_count: {liked_count}")
        print(f"  - activity_count: {activity_count}")
        print(f"  - last_activity_at: {last_activity_at}")
        
        assert liked_count > 0, f"Expected liked_count > 0, got {liked_count}"
        log_result("PASS", f"liked_count = {liked_count} (> 0) ✓")
        
        assert activity_count > 0, f"Expected activity_count > 0, got {activity_count}"
        log_result("PASS", f"activity_count = {activity_count} (> 0) ✓")
        
        assert last_activity_at is not None, f"Expected last_activity_at to be set, got None"
        log_result("PASS", f"last_activity_at = {last_activity_at} (not None) ✓")
        
        assert matched_count == 0, f"Expected matched_count = 0 (no face scan), got {matched_count}"
        log_result("PASS", f"matched_count = {matched_count} (0, no face scan) ✓")
        
        # =====================================================================
        # CRITICAL TEST: Admin GET /api/events/{event2_id}/clients
        # Should show client 2 with liked_count > 0 (face_search_enabled=false)
        # =====================================================================
        log_test(15, "Admin GET /api/events/{event2_id}/clients (face_search_enabled=false)")
        resp = requests.get(
            f"{BACKEND_URL}/events/{event2_id}/clients",
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Admin get clients failed: {resp.status_code} {resp.text}"
        clients_list = resp.json()
        log_result("PASS", f"Admin GET /api/events/{event2_id}/clients returned {len(clients_list)} client(s)")
        
        # Find client 2 in the list
        client2_data = None
        for client in clients_list:
            if client.get("client_user_id") == client2_user_id:
                client2_data = client
                break
        
        assert client2_data is not None, f"Client 2 ({client2_user_id}) NOT FOUND in clients list! Bug not fixed."
        log_result("PASS", f"✅ BUG FIX VERIFIED: Client 2 appears in clients list (face_search_enabled=false)")
        
        # Verify client 2 data
        liked_count = client2_data.get("liked_count", 0)
        activity_count = client2_data.get("activity_count", 0)
        last_activity_at = client2_data.get("last_activity_at")
        matched_count = client2_data.get("matched_count", 0)
        
        print(f"\nClient 2 data:")
        print(f"  - name: {client2_data.get('name')}")
        print(f"  - phone: {client2_data.get('phone')}")
        print(f"  - matched_count: {matched_count}")
        print(f"  - liked_count: {liked_count}")
        print(f"  - activity_count: {activity_count}")
        print(f"  - last_activity_at: {last_activity_at}")
        
        assert liked_count > 0, f"Expected liked_count > 0, got {liked_count}"
        log_result("PASS", f"liked_count = {liked_count} (> 0) ✓")
        
        assert activity_count > 0, f"Expected activity_count > 0, got {activity_count}"
        log_result("PASS", f"activity_count = {activity_count} (> 0) ✓")
        
        assert last_activity_at is not None, f"Expected last_activity_at to be set, got None"
        log_result("PASS", f"last_activity_at = {last_activity_at} (not None) ✓")
        
        # =====================================================================
        # CRITICAL TEST: Admin GET /api/events/{event1_id}/clients/{client1_user_id}/photos
        # Should return liked photo in `liked` list and empty/independent `matched` list
        # =====================================================================
        log_test(16, "Admin GET /api/events/{event1_id}/clients/{client1_user_id}/photos")
        resp = requests.get(
            f"{BACKEND_URL}/events/{event1_id}/clients/{client1_user_id}/photos",
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Admin get client photos failed: {resp.status_code} {resp.text}"
        photos_data = resp.json()
        log_result("PASS", f"Admin GET client photos returned 200")
        
        matched_photos = photos_data.get("matched", [])
        liked_photos = photos_data.get("liked", [])
        
        print(f"\nClient 1 photos:")
        print(f"  - matched: {len(matched_photos)} photo(s)")
        print(f"  - liked: {len(liked_photos)} photo(s)")
        
        assert len(matched_photos) == 0, f"Expected matched list to be empty (no face scan), got {len(matched_photos)}"
        log_result("PASS", f"matched list is empty (0 photos, no face scan) ✓")
        
        assert len(liked_photos) > 0, f"Expected liked list to have photos, got {len(liked_photos)}"
        log_result("PASS", f"liked list has {len(liked_photos)} photo(s) ✓")
        
        # Verify the liked photo is the one we liked
        liked_photo_ids = [p.get("photo_id") for p in liked_photos]
        assert photo1_id in liked_photo_ids, f"Expected photo {photo1_id} in liked list, got {liked_photo_ids}"
        log_result("PASS", f"✅ BUG FIX VERIFIED: Liked photo {photo1_id} appears in liked list")
        
        # =====================================================================
        # CRITICAL TEST: Admin GET /api/events/{event2_id}/clients/{client2_user_id}/photos
        # Should return liked photo in `liked` list (face_search_enabled=false)
        # =====================================================================
        log_test(17, "Admin GET /api/events/{event2_id}/clients/{client2_user_id}/photos")
        resp = requests.get(
            f"{BACKEND_URL}/events/{event2_id}/clients/{client2_user_id}/photos",
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Admin get client photos failed: {resp.status_code} {resp.text}"
        photos_data = resp.json()
        log_result("PASS", f"Admin GET client photos returned 200")
        
        matched_photos = photos_data.get("matched", [])
        liked_photos = photos_data.get("liked", [])
        
        print(f"\nClient 2 photos:")
        print(f"  - matched: {len(matched_photos)} photo(s)")
        print(f"  - liked: {len(liked_photos)} photo(s)")
        
        assert len(liked_photos) > 0, f"Expected liked list to have photos, got {len(liked_photos)}"
        log_result("PASS", f"liked list has {len(liked_photos)} photo(s) ✓")
        
        # Verify the liked photo is the one we liked
        liked_photo_ids = [p.get("photo_id") for p in liked_photos]
        assert photo2_id in liked_photo_ids, f"Expected photo {photo2_id} in liked list, got {liked_photo_ids}"
        log_result("PASS", f"✅ BUG FIX VERIFIED: Liked photo {photo2_id} appears in liked list (face_search_enabled=false)")
        
        # =====================================================================
        # CRITICAL TEST: Admin GET /api/events/{event1_id}/visitors
        # Should report liked_count for client 1
        # =====================================================================
        log_test(18, "Admin GET /api/events/{event1_id}/visitors (verify liked_count)")
        resp = requests.get(
            f"{BACKEND_URL}/events/{event1_id}/visitors",
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Admin get visitors failed: {resp.status_code} {resp.text}"
        visitors_list = resp.json()
        log_result("PASS", f"Admin GET /api/events/{event1_id}/visitors returned {len(visitors_list)} visitor(s)")
        
        # Find client 1 in visitors list
        client1_visitor = None
        for visitor in visitors_list:
            if visitor.get("phone") == TEST_CLIENT_1_PHONE:
                client1_visitor = visitor
                break
        
        assert client1_visitor is not None, f"Client 1 NOT FOUND in visitors list"
        log_result("PASS", f"Client 1 found in visitors list")
        
        visitor_liked_count = client1_visitor.get("liked_count", 0)
        visitor_matched_count = client1_visitor.get("matched_count", 0)
        
        print(f"\nClient 1 visitor data:")
        print(f"  - name: {client1_visitor.get('name')}")
        print(f"  - phone: {client1_visitor.get('phone')}")
        print(f"  - matched_count: {visitor_matched_count}")
        print(f"  - liked_count: {visitor_liked_count}")
        
        assert visitor_liked_count > 0, f"Expected liked_count > 0 in visitors list, got {visitor_liked_count}"
        log_result("PASS", f"✅ BUG FIX VERIFIED: list_visitors reports liked_count = {visitor_liked_count} (> 0)")
        
        # =====================================================================
        # CRITICAL TEST: Admin GET /api/events/{event2_id}/visitors
        # Should report liked_count for client 2 (face_search_enabled=false)
        # =====================================================================
        log_test(19, "Admin GET /api/events/{event2_id}/visitors (face_search_enabled=false)")
        resp = requests.get(
            f"{BACKEND_URL}/events/{event2_id}/visitors",
            headers=admin_headers
        )
        assert resp.status_code == 200, f"Admin get visitors failed: {resp.status_code} {resp.text}"
        visitors_list = resp.json()
        log_result("PASS", f"Admin GET /api/events/{event2_id}/visitors returned {len(visitors_list)} visitor(s)")
        
        # Find client 2 in visitors list
        client2_visitor = None
        for visitor in visitors_list:
            if visitor.get("phone") == TEST_CLIENT_2_PHONE:
                client2_visitor = visitor
                break
        
        assert client2_visitor is not None, f"Client 2 NOT FOUND in visitors list"
        log_result("PASS", f"Client 2 found in visitors list")
        
        visitor_liked_count = client2_visitor.get("liked_count", 0)
        
        print(f"\nClient 2 visitor data:")
        print(f"  - name: {client2_visitor.get('name')}")
        print(f"  - phone: {client2_visitor.get('phone')}")
        print(f"  - liked_count: {visitor_liked_count}")
        
        assert visitor_liked_count > 0, f"Expected liked_count > 0 in visitors list, got {visitor_liked_count}"
        log_result("PASS", f"✅ BUG FIX VERIFIED: list_visitors reports liked_count = {visitor_liked_count} (face_search_enabled=false)")
        
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED - BUG FIX VERIFIED")
        print("="*80)
        print("\nSUMMARY:")
        print("✅ Clients appear in admin clients list even without face scan")
        print("✅ Clients appear in admin clients list when face_search_enabled=false")
        print("✅ liked_count > 0 reported correctly")
        print("✅ activity_count > 0 reported correctly")
        print("✅ last_activity_at is set correctly")
        print("✅ Admin can view liked photos even without face scan")
        print("✅ Admin can view liked photos when face_search_enabled=false")
        print("✅ matched list is empty/independent when no face scan")
        print("✅ list_visitors reports liked_count correctly")
        print("✅ No 500 errors detected")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # =====================================================================
        # CLEANUP
        # =====================================================================
        if admin_token:
            print("\n" + "="*80)
            print("CLEANUP: Deleting test data")
            print("="*80)
            
            if event1_id:
                try:
                    resp = requests.delete(
                        f"{BACKEND_URL}/events/{event1_id}",
                        headers=admin_headers
                    )
                    if resp.status_code == 200:
                        print(f"✅ Deleted event 1: {event1_id}")
                    else:
                        print(f"⚠️  Failed to delete event 1: {resp.status_code}")
                except Exception as e:
                    print(f"⚠️  Error deleting event 1: {e}")
            
            if event2_id:
                try:
                    resp = requests.delete(
                        f"{BACKEND_URL}/events/{event2_id}",
                        headers=admin_headers
                    )
                    if resp.status_code == 200:
                        print(f"✅ Deleted event 2: {event2_id}")
                    else:
                        print(f"⚠️  Failed to delete event 2: {resp.status_code}")
                except Exception as e:
                    print(f"⚠️  Error deleting event 2: {e}")
    
    return 0


if __name__ == "__main__":
    exit(main())
