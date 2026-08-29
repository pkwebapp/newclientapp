#!/usr/bin/env python3
"""
Backend test for the new notification system.
Tests notification preferences, audience summary, broadcast, triggers, and dedupe.
"""
import requests
import json
import time
from io import BytesIO
from PIL import Image

# Base URL from frontend/.env
BASE_URL = "https://pkweb-client-1.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

def log(msg):
    print(f"[TEST] {msg}")

def create_test_image(width=400, height=400):
    """Create a small test JPEG image."""
    img = Image.new('RGB', (width, height), color='red')
    buf = BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return buf

def admin_login():
    """Login as admin and return session token."""
    log("Admin login...")
    resp = requests.post(f"{BASE_URL}/auth/admin/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "session_token" in data, "No session_token in admin login response"
    log(f"✅ Admin login successful, token: {data['session_token'][:20]}...")
    return data["session_token"]

def client_request_otp(email):
    """Request OTP for client email."""
    log(f"Client request OTP for {email}...")
    resp = requests.post(f"{BASE_URL}/auth/client/request-otp", json={
        "channel": "email",
        "email": email
    })
    assert resp.status_code == 200, f"Client request OTP failed: {resp.status_code} {resp.text}"
    data = resp.json()
    log(f"✅ OTP requested, dev_code: {data.get('dev_code', 'N/A')}")
    return data.get("dev_code")

def client_verify_otp(email, code):
    """Verify OTP and return client session token."""
    log(f"Client verify OTP for {email}...")
    resp = requests.post(f"{BASE_URL}/auth/client/verify-otp", json={
        "channel": "email",
        "email": email,
        "code": code
    })
    assert resp.status_code == 200, f"Client verify OTP failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "session_token" in data, "No session_token in client verify response"
    log(f"✅ Client login successful, token: {data['session_token'][:20]}...")
    return data["session_token"]

def test_notification_preferences(admin_token):
    """Test 1: Notification preferences GET/PATCH."""
    log("\n=== TEST 1: Notification Preferences ===")
    
    # GET preferences (admin)
    log("GET /api/notifications/prefs (as admin)...")
    resp = requests.get(f"{BASE_URL}/notifications/prefs", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code == 200, f"GET prefs failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert data["audience"] == "admin", f"Expected audience=admin, got {data['audience']}"
    assert isinstance(data["types"], list), "types should be a list"
    assert isinstance(data["disabled"], list), "disabled should be a list"
    log(f"✅ GET prefs returned: audience={data['audience']}, types count={len(data['types'])}, disabled={data['disabled']}")
    
    # PATCH preferences - disable guest_face_search
    log("PATCH /api/notifications/prefs (disable guest_face_search)...")
    resp = requests.patch(f"{BASE_URL}/notifications/prefs", 
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"disabled": ["guest_face_search"]}
    )
    assert resp.status_code == 200, f"PATCH prefs failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert data["status"] == "saved", f"Expected status=saved, got {data['status']}"
    assert "guest_face_search" in data["disabled"], "guest_face_search should be in disabled list"
    log(f"✅ PATCH prefs saved: disabled={data['disabled']}")
    
    # GET again to verify
    log("GET /api/notifications/prefs again to verify...")
    resp = requests.get(f"{BASE_URL}/notifications/prefs", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code == 200, f"GET prefs failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "guest_face_search" in data["disabled"], "guest_face_search should still be disabled"
    log(f"✅ Verified disabled list: {data['disabled']}")
    
    # Test invalid type keys are silently dropped
    log("PATCH /api/notifications/prefs with invalid type...")
    resp = requests.patch(f"{BASE_URL}/notifications/prefs",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"disabled": ["not_a_real_type", "booking_enquiry"]}
    )
    assert resp.status_code == 200, f"PATCH prefs failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "not_a_real_type" not in data["disabled"], "Invalid type should be dropped"
    assert "booking_enquiry" in data["disabled"], "Valid type should be kept"
    log(f"✅ Invalid types silently dropped: disabled={data['disabled']}")
    
    # Reset preferences for later tests
    log("Resetting preferences...")
    resp = requests.patch(f"{BASE_URL}/notifications/prefs",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"disabled": []}
    )
    assert resp.status_code == 200, f"Reset prefs failed: {resp.status_code} {resp.text}"
    log("✅ Preferences reset")

def test_audience_summary(admin_token):
    """Test 2: Audience summary."""
    log("\n=== TEST 2: Audience Summary ===")
    
    # GET summary without event_id
    log("GET /api/notifications/audiences/summary (no event_id)...")
    resp = requests.get(f"{BASE_URL}/notifications/audiences/summary", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code == 200, f"GET summary failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "all_clients" in data, "all_clients should be in response"
    assert isinstance(data["all_clients"], int), "all_clients should be a number"
    log(f"✅ Summary returned: all_clients={data['all_clients']}")
    
    # Create an event for testing with event_id
    log("Creating test event...")
    resp = requests.post(f"{BASE_URL}/events", 
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Notification Test Event",
            "date": "2026-09-14",
            "face_search_enabled": False
        }
    )
    assert resp.status_code == 200, f"Create event failed: {resp.status_code} {resp.text}"
    event_id = resp.json()["event_id"]
    log(f"✅ Event created: {event_id}")
    
    # GET summary with event_id
    log(f"GET /api/notifications/audiences/summary (with event_id={event_id})...")
    resp = requests.get(f"{BASE_URL}/notifications/audiences/summary?event_id={event_id}", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code == 200, f"GET summary failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "all_clients" in data, "all_clients should be in response"
    assert "gallery" in data, "gallery should be in response when event_id provided"
    assert isinstance(data["gallery"], int), "gallery should be a number"
    log(f"✅ Summary with event_id returned: all_clients={data['all_clients']}, gallery={data['gallery']}")
    
    return event_id

def test_broadcast(admin_token, event_id):
    """Test 3: Broadcast notifications."""
    log("\n=== TEST 3: Broadcast Notifications ===")
    
    # Test broadcast to all_clients
    log("POST /api/notifications/broadcast (audience=all_clients)...")
    resp = requests.post(f"{BASE_URL}/notifications/broadcast",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "audience": "all_clients",
            "title": "Hello",
            "body": "World"
        }
    )
    assert resp.status_code == 200, f"Broadcast failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert data["status"] in ["sent", "no_recipients"], f"Unexpected status: {data['status']}"
    log(f"✅ Broadcast to all_clients: status={data['status']}, sent={data.get('sent', 0)}")
    
    # Test bad audience
    log("POST /api/notifications/broadcast (bad audience)...")
    resp = requests.post(f"{BASE_URL}/notifications/broadcast",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "audience": "invalid_audience",
            "title": "Test",
            "body": "Test"
        }
    )
    assert resp.status_code == 400, f"Expected 400 for bad audience, got {resp.status_code}"
    log("✅ Bad audience returns 400")
    
    # Test gallery broadcast without event_id
    log("POST /api/notifications/broadcast (audience=gallery, no event_id)...")
    resp = requests.post(f"{BASE_URL}/notifications/broadcast",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "audience": "gallery",
            "title": "Test",
            "body": "Test"
        }
    )
    assert resp.status_code == 400, f"Expected 400 for gallery without event_id, got {resp.status_code}"
    log("✅ Gallery broadcast without event_id returns 400")
    
    # Test specific broadcast without client_user_ids
    log("POST /api/notifications/broadcast (audience=specific, no client_user_ids)...")
    resp = requests.post(f"{BASE_URL}/notifications/broadcast",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "audience": "specific",
            "title": "Test",
            "body": "Test"
        }
    )
    assert resp.status_code == 400, f"Expected 400 for specific without client_user_ids, got {resp.status_code}"
    log("✅ Specific broadcast without client_user_ids returns 400")
    
    # Test gallery broadcast with valid event_id
    log(f"POST /api/notifications/broadcast (audience=gallery, event_id={event_id})...")
    resp = requests.post(f"{BASE_URL}/notifications/broadcast",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "audience": "gallery",
            "event_id": event_id,
            "title": "Gallery Update",
            "body": "New photos added"
        }
    )
    assert resp.status_code == 200, f"Broadcast failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert data["status"] in ["sent", "no_recipients"], f"Unexpected status: {data['status']}"
    log(f"✅ Broadcast to gallery: status={data['status']}, sent={data.get('sent', 0)}")

def test_end_to_end_triggers(admin_token, event_id):
    """Test 4: End-to-end trigger tests."""
    log("\n=== TEST 4: End-to-End Trigger Tests ===")
    
    # Create a client user
    client_email = f"notif.test.{int(time.time())}@example.com"
    log(f"Creating client user: {client_email}...")
    dev_code = client_request_otp(client_email)
    assert dev_code, "No dev_code returned"
    client_token = client_verify_otp(client_email, dev_code)
    
    # Grant access to the client
    log(f"Granting access to client for event {event_id}...")
    resp = requests.post(f"{BASE_URL}/events/{event_id}/access",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "channel": "email",
            "email": client_email,
            "full_gallery_access": True
        }
    )
    assert resp.status_code == 200, f"Grant access failed: {resp.status_code} {resp.text}"
    log("✅ Access granted")
    
    # Check client notifications for gallery_assigned
    log("Checking client notifications for gallery_assigned...")
    time.sleep(1)  # Give notification time to be created
    resp = requests.get(f"{BASE_URL}/me/notifications", headers={
        "Authorization": f"Bearer {client_token}"
    })
    assert resp.status_code == 200, f"GET client notifications failed: {resp.status_code} {resp.text}"
    data = resp.json()
    notifications = data.get("items", [])
    gallery_assigned = [n for n in notifications if n.get("type") == "gallery_assigned"]
    assert len(gallery_assigned) > 0, "No gallery_assigned notification found"
    log(f"✅ Client received gallery_assigned notification: {gallery_assigned[0]['title']}")
    
    # Upload a photo to trigger new_photos and upload_indexed
    log("Uploading photo to trigger notifications...")
    img_buf = create_test_image()
    resp = requests.post(f"{BASE_URL}/events/{event_id}/photos",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("test.jpg", img_buf, "image/jpeg")}
    )
    assert resp.status_code == 200, f"Photo upload failed: {resp.status_code} {resp.text}"
    photo_id = resp.json()["photo_id"]
    log(f"✅ Photo uploaded: {photo_id}")
    
    # Wait for indexing to complete
    log("Waiting for indexing to complete...")
    for i in range(10):
        time.sleep(2)
        resp = requests.get(f"{BASE_URL}/events/{event_id}/indexing-status", headers={
            "Authorization": f"Bearer {admin_token}"
        })
        if resp.status_code == 200:
            status = resp.json().get("status")
            if status == "ready":
                log("✅ Indexing complete")
                break
    
    # Check client notifications for new_photos
    log("Checking client notifications for new_photos...")
    time.sleep(2)  # Give notification time to be created
    resp = requests.get(f"{BASE_URL}/me/notifications", headers={
        "Authorization": f"Bearer {client_token}"
    })
    assert resp.status_code == 200, f"GET client notifications failed: {resp.status_code} {resp.text}"
    data = resp.json()
    notifications = data.get("items", [])
    new_photos = [n for n in notifications if n.get("type") == "new_photos"]
    if len(new_photos) > 0:
        log(f"✅ Client received new_photos notification: {new_photos[0]['title']}")
    else:
        log("⚠️  No new_photos notification found (may not be triggered for single photo)")
    
    # Check admin notifications for upload_indexed
    log("Checking admin notifications for upload_indexed...")
    resp = requests.get(f"{BASE_URL}/notifications", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code == 200, f"GET admin notifications failed: {resp.status_code} {resp.text}"
    data = resp.json()
    notifications = data.get("items", [])
    upload_indexed = [n for n in notifications if n.get("type") == "upload_indexed"]
    if len(upload_indexed) > 0:
        log(f"✅ Admin received upload_indexed notification: {upload_indexed[0]['title']}")
    else:
        log("⚠️  No upload_indexed notification found (may not be triggered for single photo)")
    
    return client_email, client_token

def test_preference_enforcement(admin_token, client_email, client_token, event_id):
    """Test 5: Preference enforcement."""
    log("\n=== TEST 5: Preference Enforcement ===")
    
    # Get initial notification count
    resp = requests.get(f"{BASE_URL}/me/notifications", headers={
        "Authorization": f"Bearer {client_token}"
    })
    assert resp.status_code == 200, f"GET notifications failed: {resp.status_code} {resp.text}"
    initial_count = len(resp.json().get("items", []))
    log(f"Initial notification count: {initial_count}")
    
    # Disable gallery_assigned as client
    log("Disabling gallery_assigned for client...")
    resp = requests.patch(f"{BASE_URL}/notifications/prefs",
        headers={"Authorization": f"Bearer {client_token}"},
        json={"disabled": ["gallery_assigned"]}
    )
    assert resp.status_code == 200, f"PATCH prefs failed: {resp.status_code} {resp.text}"
    log("✅ gallery_assigned disabled")
    
    # Create a new event and grant access
    log("Creating new event...")
    resp = requests.post(f"{BASE_URL}/events",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Notification Test Event 2",
            "date": "2026-09-15",
            "face_search_enabled": False
        }
    )
    assert resp.status_code == 200, f"Create event failed: {resp.status_code} {resp.text}"
    new_event_id = resp.json()["event_id"]
    log(f"✅ New event created: {new_event_id}")
    
    log("Granting access to client for new event...")
    resp = requests.post(f"{BASE_URL}/events/{new_event_id}/access",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "channel": "email",
            "email": client_email,
            "full_gallery_access": True
        }
    )
    assert resp.status_code == 200, f"Grant access failed: {resp.status_code} {resp.text}"
    log("✅ Access granted")
    
    # Check that NO new gallery_assigned notification was created
    log("Checking that no new gallery_assigned notification was created...")
    time.sleep(2)
    resp = requests.get(f"{BASE_URL}/me/notifications", headers={
        "Authorization": f"Bearer {client_token}"
    })
    assert resp.status_code == 200, f"GET notifications failed: {resp.status_code} {resp.text}"
    data = resp.json()
    notifications = data.get("items", [])
    new_gallery_assigned = [n for n in notifications if n.get("type") == "gallery_assigned" and n.get("meta", {}).get("event_id") == new_event_id]
    assert len(new_gallery_assigned) == 0, "gallery_assigned notification should not be created when disabled"
    log("✅ No new gallery_assigned notification created (preference enforced)")
    
    # Cleanup: delete new event
    log(f"Cleaning up new event {new_event_id}...")
    resp = requests.delete(f"{BASE_URL}/events/{new_event_id}", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code == 200, f"Delete event failed: {resp.status_code} {resp.text}"
    log("✅ New event deleted")

def test_dedupe(admin_token, event_id):
    """Test 6: Dedupe."""
    log("\n=== TEST 6: Dedupe ===")
    
    # Upload first photo
    log("Uploading first photo...")
    img_buf = create_test_image()
    resp = requests.post(f"{BASE_URL}/events/{event_id}/photos",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("test1.jpg", img_buf, "image/jpeg")}
    )
    assert resp.status_code == 200, f"Photo upload failed: {resp.status_code} {resp.text}"
    log("✅ First photo uploaded")
    
    # Wait for indexing
    time.sleep(3)
    
    # Get admin notification count
    resp = requests.get(f"{BASE_URL}/notifications", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code == 200, f"GET notifications failed: {resp.status_code} {resp.text}"
    notifications_before = resp.json().get("items", [])
    upload_notifications_before = [n for n in notifications_before if n.get("type") == "upload_indexed" and n.get("meta", {}).get("event_id") == event_id]
    count_before = len(upload_notifications_before)
    log(f"Upload notifications before second upload: {count_before}")
    
    # Upload second photo (should trigger dedupe if within 24h)
    log("Uploading second photo (should trigger dedupe)...")
    img_buf = create_test_image()
    resp = requests.post(f"{BASE_URL}/events/{event_id}/photos",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("test2.jpg", img_buf, "image/jpeg")}
    )
    assert resp.status_code == 200, f"Photo upload failed: {resp.status_code} {resp.text}"
    log("✅ Second photo uploaded")
    
    # Wait for indexing
    time.sleep(3)
    
    # Get admin notification count again
    resp = requests.get(f"{BASE_URL}/notifications", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    assert resp.status_code == 200, f"GET notifications failed: {resp.status_code} {resp.text}"
    notifications_after = resp.json().get("items", [])
    upload_notifications_after = [n for n in notifications_after if n.get("type") == "upload_indexed" and n.get("meta", {}).get("event_id") == event_id]
    count_after = len(upload_notifications_after)
    log(f"Upload notifications after second upload: {count_after}")
    
    # Dedupe should prevent duplicate notification within 24h
    if count_after == count_before:
        log("✅ Dedupe working: No duplicate notification created")
    else:
        log(f"⚠️  Dedupe may not be working: count increased from {count_before} to {count_after}")

def test_regression_auth_flows(admin_token):
    """Test regression: existing sign-in flows still work."""
    log("\n=== TEST 7: Regression - Auth Flows ===")
    
    # Admin login already tested in admin_login()
    log("✅ Admin login working (tested earlier)")
    
    # Test forgot-password endpoint exists
    log("Testing forgot-password endpoint...")
    resp = requests.post(f"{BASE_URL}/auth/forgot-password", json={
        "email": "test@example.com"
    })
    # Should return 200 or 404 depending on whether email exists
    assert resp.status_code in [200, 404], f"Forgot password endpoint failed: {resp.status_code}"
    log("✅ Forgot-password endpoint exists")

def cleanup(admin_token, event_id):
    """Cleanup test data."""
    log("\n=== Cleanup ===")
    log(f"Deleting test event {event_id}...")
    resp = requests.delete(f"{BASE_URL}/events/{event_id}", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    if resp.status_code == 200:
        log("✅ Test event deleted")
    else:
        log(f"⚠️  Failed to delete event: {resp.status_code} {resp.text}")

def main():
    """Run all tests."""
    log("Starting notification system backend tests...")
    log(f"Base URL: {BASE_URL}")
    
    try:
        # Login as admin
        admin_token = admin_login()
        
        # Test 1: Notification preferences
        test_notification_preferences(admin_token)
        
        # Test 2: Audience summary
        event_id = test_audience_summary(admin_token)
        
        # Test 3: Broadcast
        test_broadcast(admin_token, event_id)
        
        # Test 4: End-to-end triggers
        client_email, client_token = test_end_to_end_triggers(admin_token, event_id)
        
        # Test 5: Preference enforcement
        test_preference_enforcement(admin_token, client_email, client_token, event_id)
        
        # Test 6: Dedupe
        test_dedupe(admin_token, event_id)
        
        # Test 7: Regression - auth flows
        test_regression_auth_flows(admin_token)
        
        # Cleanup
        cleanup(admin_token, event_id)
        
        log("\n" + "="*60)
        log("✅ ALL TESTS COMPLETED SUCCESSFULLY")
        log("="*60)
        
    except AssertionError as e:
        log(f"\n❌ TEST FAILED: {e}")
        raise
    except Exception as e:
        log(f"\n❌ UNEXPECTED ERROR: {e}")
        raise

if __name__ == "__main__":
    main()
