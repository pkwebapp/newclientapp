#!/usr/bin/env python3
"""
Backend-only verification for Studio/Client notification bell APIs.
Tests admin and client notification endpoints, gallery_expiry notifications on archive,
and mark-read functionality.
"""

import requests
import json
import time
from datetime import datetime

# Backend URL from frontend/.env
BASE_URL = "https://newclient-app-2.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

# Test client credentials (will be created via OTP)
CLIENT_PHONE = "+919876543210"
CLIENT_NAME = "Test Notification Client"

def log(msg):
    """Print timestamped log message."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def test_admin_login():
    """Test 1: Admin login and get session token."""
    log("TEST 1: Admin login")
    resp = requests.post(f"{BASE_URL}/auth/admin/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    log(f"  POST /api/auth/admin/login → {resp.status_code}")
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    data = resp.json()
    assert "session_token" in data, "No session_token in response"
    log(f"  ✅ Admin logged in successfully")
    return data["session_token"]

def test_admin_notifications(admin_token):
    """Test 2: GET /api/notifications returns items/unread_count."""
    log("TEST 2: Admin GET /api/notifications")
    resp = requests.get(f"{BASE_URL}/notifications", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    log(f"  GET /api/notifications → {resp.status_code}")
    assert resp.status_code == 200, f"Admin notifications failed: {resp.text}"
    data = resp.json()
    assert "items" in data, "No 'items' field in response"
    assert "unread_count" in data, "No 'unread_count' field in response"
    assert isinstance(data["items"], list), "'items' is not a list"
    assert isinstance(data["unread_count"], int), "'unread_count' is not an int"
    log(f"  ✅ Admin notifications: {len(data['items'])} items, {data['unread_count']} unread")
    return data

def test_client_otp_login():
    """Test 3: Client OTP login (request + verify)."""
    log("TEST 3: Client OTP login")
    
    # Request OTP
    resp = requests.post(f"{BASE_URL}/auth/client/request-otp", json={
        "channel": "phone",
        "phone": CLIENT_PHONE,
        "name": CLIENT_NAME
    })
    log(f"  POST /api/auth/client/request-otp → {resp.status_code}")
    assert resp.status_code == 200, f"OTP request failed: {resp.text}"
    data = resp.json()
    
    # In dev mode, dev_code is returned
    dev_code = data.get("dev_code")
    if not dev_code:
        log("  ⚠️  No dev_code in response (OTP_DEV_MODE may be false)")
        # Try a default dev code
        dev_code = "123456"
    
    log(f"  Dev code: {dev_code}")
    
    # Verify OTP
    resp = requests.post(f"{BASE_URL}/auth/client/verify-otp", json={
        "channel": "phone",
        "phone": CLIENT_PHONE,
        "code": dev_code,
        "name": CLIENT_NAME
    })
    log(f"  POST /api/auth/client/verify-otp → {resp.status_code}")
    assert resp.status_code == 200, f"OTP verify failed: {resp.text}"
    data = resp.json()
    assert "session_token" in data, "No session_token in response"
    log(f"  ✅ Client logged in successfully")
    return data["session_token"], data["user"]["user_id"]

def test_client_notifications(client_token):
    """Test 4: GET /api/me/notifications returns items/unread_count."""
    log("TEST 4: Client GET /api/me/notifications")
    resp = requests.get(f"{BASE_URL}/me/notifications", headers={
        "Authorization": f"Bearer {client_token}"
    })
    log(f"  GET /api/me/notifications → {resp.status_code}")
    assert resp.status_code == 200, f"Client notifications failed: {resp.text}"
    data = resp.json()
    assert "items" in data, "No 'items' field in response"
    assert "unread_count" in data, "No 'unread_count' field in response"
    assert isinstance(data["items"], list), "'items' is not a list"
    assert isinstance(data["unread_count"], int), "'unread_count' is not an int"
    log(f"  ✅ Client notifications: {len(data['items'])} items, {data['unread_count']} unread")
    return data

def test_create_event(admin_token):
    """Test 5: Create a throwaway event."""
    log("TEST 5: Create throwaway event")
    resp = requests.post(f"{BASE_URL}/events", headers={
        "Authorization": f"Bearer {admin_token}"
    }, json={
        "name": "QA Notification Test Event",
        "category": "wedding",
        "event_date": "2026-12-31"
    })
    log(f"  POST /api/events → {resp.status_code}")
    assert resp.status_code == 200, f"Event creation failed: {resp.text}"
    data = resp.json()
    event_id = data["event_id"]
    log(f"  ✅ Event created: {event_id}")
    return event_id

def test_create_access_grant(admin_token, event_id, client_phone):
    """Test 6: Create an active access grant for the client."""
    log("TEST 6: Create access grant for client")
    resp = requests.post(f"{BASE_URL}/events/{event_id}/access", headers={
        "Authorization": f"Bearer {admin_token}"
    }, json={
        "channel": "phone",
        "phone": client_phone,
        "full_gallery_access": True
    })
    log(f"  POST /api/events/{event_id}/access → {resp.status_code}")
    assert resp.status_code == 200, f"Access grant creation failed: {resp.text}"
    data = resp.json()
    log(f"  ✅ Access grant created: {data.get('grant_id')}")
    return data

def test_archive_event(admin_token, event_id):
    """Test 7: Archive the event (should create gallery_expiry notification)."""
    log("TEST 7: Archive event")
    resp = requests.post(f"{BASE_URL}/events/{event_id}/archive", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    log(f"  POST /api/events/{event_id}/archive → {resp.status_code}")
    assert resp.status_code == 200, f"Event archive failed: {resp.text}"
    log(f"  ✅ Event archived successfully")
    
    # Wait a moment for notification to be created
    time.sleep(1)

def test_verify_gallery_expiry_notification(client_token):
    """Test 8: Verify gallery_expiry notification appears in client notifications."""
    log("TEST 8: Verify gallery_expiry notification")
    resp = requests.get(f"{BASE_URL}/me/notifications", headers={
        "Authorization": f"Bearer {client_token}"
    })
    log(f"  GET /api/me/notifications → {resp.status_code}")
    assert resp.status_code == 200, f"Client notifications failed: {resp.text}"
    data = resp.json()
    
    # Find gallery_expiry notification
    gallery_expiry_notifs = [n for n in data["items"] if n.get("type") == "gallery_expiry"]
    assert len(gallery_expiry_notifs) > 0, "No gallery_expiry notification found"
    
    notif = gallery_expiry_notifs[0]
    log(f"  ✅ Found gallery_expiry notification:")
    log(f"     ID: {notif.get('notification_id')}")
    log(f"     Title: {notif.get('title')}")
    log(f"     Body: {notif.get('body')}")
    log(f"     Read: {notif.get('read')}")
    log(f"     Unread count: {data['unread_count']}")
    
    return notif, data["unread_count"]

def test_mark_client_notification_read(client_token, notification_id, initial_unread_count):
    """Test 9: PATCH /api/me/notifications/{id}/read and verify unread count decreases."""
    log("TEST 9: Mark client notification as read")
    resp = requests.patch(f"{BASE_URL}/me/notifications/{notification_id}/read", headers={
        "Authorization": f"Bearer {client_token}"
    })
    log(f"  PATCH /api/me/notifications/{notification_id}/read → {resp.status_code}")
    assert resp.status_code == 200, f"Mark read failed: {resp.text}"
    data = resp.json()
    assert data.get("status") == "read", "Status is not 'read'"
    log(f"  ✅ Notification marked as read")
    
    # Verify unread count decreased
    resp = requests.get(f"{BASE_URL}/me/notifications", headers={
        "Authorization": f"Bearer {client_token}"
    })
    assert resp.status_code == 200
    new_data = resp.json()
    new_unread_count = new_data["unread_count"]
    
    log(f"  Unread count: {initial_unread_count} → {new_unread_count}")
    assert new_unread_count < initial_unread_count, "Unread count did not decrease"
    log(f"  ✅ Unread count decreased correctly")

def test_admin_booking_notification_regression(admin_token):
    """Test 10: Verify admin booking notifications still work."""
    log("TEST 10: Admin booking notification regression")
    
    # Get current notifications
    resp = requests.get(f"{BASE_URL}/notifications", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    log(f"  GET /api/notifications → {resp.status_code}")
    assert resp.status_code == 200, f"Admin notifications failed: {resp.text}"
    data = resp.json()
    
    initial_count = len(data["items"])
    log(f"  Current notification count: {initial_count}")
    
    # Find a booking notification if any exist
    booking_notifs = [n for n in data["items"] if n.get("type") == "booking_request"]
    if booking_notifs:
        log(f"  ✅ Found {len(booking_notifs)} booking notification(s)")
        
        # Test mark-read on a booking notification
        notif = booking_notifs[0]
        if not notif.get("read"):
            notif_id = notif["notification_id"]
            resp = requests.patch(f"{BASE_URL}/notifications/{notif_id}/read", headers={
                "Authorization": f"Bearer {admin_token}"
            })
            log(f"  PATCH /api/notifications/{notif_id}/read → {resp.status_code}")
            assert resp.status_code == 200, f"Mark read failed: {resp.text}"
            log(f"  ✅ Booking notification mark-read works")
        else:
            log(f"  ℹ️  Booking notification already read, skipping mark-read test")
    else:
        log(f"  ℹ️  No booking notifications found (this is OK)")
    
    log(f"  ✅ Admin booking notifications endpoint working")

def test_cleanup_event(admin_token, event_id):
    """Test 11: Delete the throwaway event."""
    log("TEST 11: Cleanup - delete event")
    resp = requests.delete(f"{BASE_URL}/events/{event_id}", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    log(f"  DELETE /api/events/{event_id} → {resp.status_code}")
    assert resp.status_code == 200, f"Event deletion failed: {resp.text}"
    data = resp.json()
    log(f"  ✅ Event deleted: {data.get('status')}")

def main():
    """Run all notification bell API tests."""
    log("=" * 80)
    log("BACKEND NOTIFICATION BELL API VERIFICATION")
    log("=" * 80)
    
    try:
        # Test 1: Admin login
        admin_token = test_admin_login()
        
        # Test 2: Admin notifications endpoint
        test_admin_notifications(admin_token)
        
        # Test 3: Client OTP login
        client_token, client_user_id = test_client_otp_login()
        
        # Test 4: Client notifications endpoint (initial state)
        initial_client_notifs = test_client_notifications(client_token)
        
        # Test 5: Create throwaway event
        event_id = test_create_event(admin_token)
        
        # Test 6: Create access grant for client
        test_create_access_grant(admin_token, event_id, CLIENT_PHONE)
        
        # Test 7: Archive event (creates gallery_expiry notification)
        test_archive_event(admin_token, event_id)
        
        # Test 8: Verify gallery_expiry notification appears
        gallery_notif, initial_unread = test_verify_gallery_expiry_notification(client_token)
        
        # Test 9: Mark notification as read and verify unread count decreases
        test_mark_client_notification_read(client_token, gallery_notif["notification_id"], initial_unread)
        
        # Test 10: Verify admin booking notifications still work
        test_admin_booking_notification_regression(admin_token)
        
        # Test 11: Cleanup
        test_cleanup_event(admin_token, event_id)
        
        log("=" * 80)
        log("✅ ALL TESTS PASSED")
        log("=" * 80)
        
    except AssertionError as e:
        log("=" * 80)
        log(f"❌ TEST FAILED: {e}")
        log("=" * 80)
        raise
    except Exception as e:
        log("=" * 80)
        log(f"❌ UNEXPECTED ERROR: {e}")
        log("=" * 80)
        raise

if __name__ == "__main__":
    main()
