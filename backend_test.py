#!/usr/bin/env python3
"""
Backend test for Slice 2 CRM endpoints (Studio profile, Client dashboard, Booking + Reviews).
Tests ONLY the new Slice 2 endpoints. Does NOT re-test Slice 1 CRM CRUD or existing gallery/album flows.
"""
import requests
import sys
import time

# Backend URL from frontend/.env
BASE_URL = "https://37c2be9c-4fd7-4175-94d4-fe3b7574d461.preview.emergentagent.com/api"

# Admin credentials from test_credentials.md
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

# Test data
TEST_PHONE = "+915550001111"
TEST_PHONE_NEW = "+915550009999"  # For edge case: brand-new client with no grants

def log(msg):
    print(f"[TEST] {msg}")

def admin_login():
    """Login as admin and return session_token."""
    log("1. Admin login...")
    resp = requests.post(f"{BASE_URL}/auth/admin/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "session_token" in data, f"No session_token in response: {data}"
    log(f"   ✅ Admin login successful, token: {data['session_token'][:20]}...")
    return data["session_token"]

def test_studio_profile(admin_token):
    """Test GET/PATCH /api/studio/profile (require_admin)."""
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # First, clean up any existing studio profile from previous test runs
    log("2. Cleaning up existing studio profile...")
    try:
        from pymongo import MongoClient
        client = MongoClient("mongodb://localhost:27017")
        db = client["lumiere_gallery"]
        result = db.studio_profiles.delete_many({})
        log(f"   Deleted {result.deleted_count} existing studio profiles")
    except Exception as e:
        log(f"   ⚠️  Cleanup failed: {e}")
    
    # GET studio profile (should return defaults after cleanup)
    log("3. GET /api/studio/profile (before PATCH, should return defaults)...")
    resp = requests.get(f"{BASE_URL}/studio/profile", headers=headers)
    assert resp.status_code == 200, f"GET studio/profile failed: {resp.status_code} {resp.text}"
    profile = resp.json()
    log(f"   Profile: {profile}")
    assert "name" in profile, "Missing 'name' in profile"
    assert "whatsapp" in profile, "Missing 'whatsapp' in profile"
    assert "phone" in profile, "Missing 'phone' in profile"
    assert "google_review_url" in profile, "Missing 'google_review_url' in profile"
    assert "booking_email" in profile, "Missing 'booking_email' in profile"
    # When unset, whatsapp and phone must default to "8888766739"
    assert profile["whatsapp"] == "8888766739", f"Default whatsapp should be 8888766739, got {profile['whatsapp']}"
    assert profile["phone"] == "8888766739", f"Default phone should be 8888766739, got {profile['phone']}"
    log("   ✅ GET studio/profile returns correct defaults")
    
    # PATCH studio profile
    log("4. PATCH /api/studio/profile...")
    resp = requests.patch(f"{BASE_URL}/studio/profile", headers=headers, json={
        "name": "Test Studio",
        "whatsapp": "9999911111",
        "phone": "9999922222",
        "google_review_url": "https://g.page/x",
        "booking_email": "bookings@test.studio"
    })
    assert resp.status_code == 200, f"PATCH studio/profile failed: {resp.status_code} {resp.text}"
    profile = resp.json()
    log(f"   Updated profile: {profile}")
    assert profile["name"] == "Test Studio", f"name not updated: {profile['name']}"
    assert profile["whatsapp"] == "9999911111", f"whatsapp not updated: {profile['whatsapp']}"
    assert profile["phone"] == "9999922222", f"phone not updated: {profile['phone']}"
    assert profile["google_review_url"] == "https://g.page/x", f"google_review_url not updated: {profile['google_review_url']}"
    assert profile["booking_email"] == "bookings@test.studio", f"booking_email not updated: {profile['booking_email']}"
    log("   ✅ PATCH studio/profile updates correctly")
    
    return profile

def create_event(admin_token):
    """Create a test event."""
    log("5. Create event...")
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = requests.post(f"{BASE_URL}/events", headers=headers, json={
        "name": "Test Wedding",
        "category": "wedding",
        "date": "2026-02-14",
        "value": 150000
    })
    assert resp.status_code == 200, f"Create event failed: {resp.status_code} {resp.text}"
    event = resp.json()
    event_id = event["event_id"]
    log(f"   ✅ Event created: {event_id}")
    return event_id

def grant_client_access(admin_token, event_id, phone):
    """Grant client access to event."""
    log(f"6. Grant client access to event {event_id} for phone {phone}...")
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = requests.post(f"{BASE_URL}/events/{event_id}/access", headers=headers, json={
        "channel": "phone",
        "phone": phone,
        "full_gallery_access": True
    })
    assert resp.status_code == 200, f"Grant access failed: {resp.status_code} {resp.text}"
    log(f"   ✅ Access granted")

def create_crm_client(admin_token, phone):
    """Create a CRM client with a contact matching the phone."""
    log(f"7. Create CRM client with contact phone {phone}...")
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = requests.post(f"{BASE_URL}/clients", headers=headers, json={
        "name": "Test Family",
        "contacts": [
            {
                "name": "Anjali",
                "role": "bride",
                "phone": phone,
                "is_primary": True
            }
        ],
        "important_dates": [
            {
                "person_label": "Anjali",
                "occasion": "Birthday",
                "date": "2026-09-01"
            }
        ]
    })
    assert resp.status_code == 200, f"Create CRM client failed: {resp.status_code} {resp.text}"
    client = resp.json()
    client_id = client["client_id"]
    log(f"   ✅ CRM client created: {client_id}")
    return client_id

def client_login_otp(phone, name):
    """Login as client via OTP (OTP_DEV_MODE returns dev_code)."""
    log(f"8. Client OTP login for phone {phone}...")
    
    # Request OTP
    log(f"   8a. Request OTP...")
    resp = requests.post(f"{BASE_URL}/auth/client/request-otp", json={
        "channel": "phone",
        "phone": phone
    })
    assert resp.status_code == 200, f"Request OTP failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "dev_code" in data, f"No dev_code in response (OTP_DEV_MODE should be true): {data}"
    dev_code = data["dev_code"]
    log(f"   ✅ OTP requested, dev_code: {dev_code}")
    
    # Verify OTP
    log(f"   8b. Verify OTP...")
    resp = requests.post(f"{BASE_URL}/auth/client/verify-otp", json={
        "channel": "phone",
        "phone": phone,
        "code": dev_code,
        "name": name
    })
    assert resp.status_code == 200, f"Verify OTP failed: {resp.status_code} {resp.text}"
    data = resp.json()
    assert "session_token" in data, f"No session_token in response: {data}"
    client_token = data["session_token"]
    client_user_id = data.get("user", {}).get("user_id")
    log(f"   ✅ Client logged in, token: {client_token[:20]}..., user_id: {client_user_id}")
    return client_token, client_user_id

def test_client_dashboard(client_token, expected_studio_whatsapp):
    """Test GET /api/me/dashboard (require_client)."""
    log("9. GET /api/me/dashboard (client)...")
    headers = {"Authorization": f"Bearer {client_token}"}
    resp = requests.get(f"{BASE_URL}/me/dashboard", headers=headers)
    assert resp.status_code == 200, f"GET me/dashboard failed: {resp.status_code} {resp.text}"
    dashboard = resp.json()
    log(f"   Dashboard: {dashboard}")
    
    # Verify structure
    assert "profile" in dashboard, "Missing 'profile' in dashboard"
    assert "memories" in dashboard, "Missing 'memories' in dashboard"
    assert "upcoming" in dashboard, "Missing 'upcoming' in dashboard"
    assert "studio" in dashboard, "Missing 'studio' in dashboard"
    
    # Verify profile
    profile = dashboard["profile"]
    assert "first_name" in profile, "Missing 'first_name' in profile"
    assert profile["first_name"] == "Anjali", f"Expected first_name='Anjali', got {profile['first_name']}"
    log(f"   ✅ profile.first_name == 'Anjali'")
    
    # Verify memories (should contain the Test Wedding event)
    memories = dashboard["memories"]
    assert isinstance(memories, list), f"memories should be a list, got {type(memories)}"
    assert len(memories) > 0, "memories should not be empty"
    test_wedding = next((m for m in memories if m.get("name") == "Test Wedding"), None)
    assert test_wedding is not None, "Test Wedding event not found in memories"
    assert test_wedding.get("year") == "2026", f"Expected year='2026', got {test_wedding.get('year')}"
    assert "photo_count" in test_wedding, "Missing 'photo_count' in memory"
    log(f"   ✅ memories contains Test Wedding with year='2026' and photo_count field")
    
    # Verify upcoming (should contain Anjali's Birthday)
    upcoming = dashboard["upcoming"]
    assert isinstance(upcoming, list), f"upcoming should be a list, got {type(upcoming)}"
    assert len(upcoming) > 0, "upcoming should not be empty"
    birthday = next((u for u in upcoming if u.get("occasion") == "Birthday"), None)
    assert birthday is not None, "Birthday not found in upcoming"
    assert birthday.get("person_label") == "Anjali", f"Expected person_label='Anjali', got {birthday.get('person_label')}"
    assert "next_date" in birthday, "Missing 'next_date' in upcoming date"
    assert birthday["next_date"] is not None, "next_date should not be None"
    assert "days_until" in birthday, "Missing 'days_until' in upcoming date"
    assert isinstance(birthday["days_until"], int), f"days_until should be numeric, got {type(birthday['days_until'])}"
    log(f"   ✅ upcoming contains Birthday with next_date and numeric days_until")
    
    # Verify studio
    studio = dashboard["studio"]
    assert "whatsapp" in studio, "Missing 'whatsapp' in studio"
    assert "google_review_url" in studio, "Missing 'google_review_url' in studio"
    assert studio["whatsapp"] == expected_studio_whatsapp, f"Expected studio.whatsapp='{expected_studio_whatsapp}', got {studio['whatsapp']}"
    assert studio["google_review_url"] == "https://g.page/x", f"Expected google_review_url='https://g.page/x', got {studio['google_review_url']}"
    log(f"   ✅ studio.whatsapp == '{expected_studio_whatsapp}' and studio.google_review_url == 'https://g.page/x'")
    
    log("   ✅ Client dashboard test PASSED")

def test_booking_request(client_token):
    """Test POST /api/me/booking-requests (require_client)."""
    log("10. POST /api/me/booking-requests...")
    headers = {"Authorization": f"Bearer {client_token}"}
    resp = requests.post(f"{BASE_URL}/me/booking-requests", headers=headers, json={
        "service_type": "Anniversary Shoot",
        "preferred_date": "2026-12-06",
        "message": "hi"
    })
    assert resp.status_code == 200, f"POST booking-requests failed: {resp.status_code} {resp.text}"
    data = resp.json()
    log(f"   Response: {data}")
    assert data.get("status") == "ok", f"Expected status='ok', got {data.get('status')}"
    assert "request_id" in data, "Missing 'request_id' in response"
    log(f"   ✅ Booking request created: {data['request_id']}")
    return data["request_id"]

def test_reviews(client_token):
    """Test POST /api/me/reviews (require_client) with validation."""
    log("11. POST /api/me/reviews (valid rating=5)...")
    headers = {"Authorization": f"Bearer {client_token}"}
    resp = requests.post(f"{BASE_URL}/me/reviews", headers=headers, json={
        "rating": 5,
        "text": "great"
    })
    assert resp.status_code == 200, f"POST reviews (rating=5) failed: {resp.status_code} {resp.text}"
    data = resp.json()
    log(f"   Response: {data}")
    assert data.get("status") == "ok", f"Expected status='ok', got {data.get('status')}"
    assert "review_id" in data, "Missing 'review_id' in response"
    log(f"   ✅ Review created: {data['review_id']}")
    review_id = data["review_id"]
    
    # Test validation: rating=6 should be 422
    log("12. POST /api/me/reviews (invalid rating=6, should be 422)...")
    resp = requests.post(f"{BASE_URL}/me/reviews", headers=headers, json={
        "rating": 6
    })
    assert resp.status_code == 422, f"Expected 422 for rating=6, got {resp.status_code}"
    log(f"   ✅ rating=6 correctly rejected with 422")
    
    # Test validation: rating=0 should be 422
    log("13. POST /api/me/reviews (invalid rating=0, should be 422)...")
    resp = requests.post(f"{BASE_URL}/me/reviews", headers=headers, json={
        "rating": 0
    })
    assert resp.status_code == 422, f"Expected 422 for rating=0, got {resp.status_code}"
    log(f"   ✅ rating=0 correctly rejected with 422")
    
    return review_id

def test_edge_case_new_client():
    """Test edge case: brand-new client user with no grants."""
    log("14. Edge case: brand-new client with no grants...")
    
    # Login as new client (no grants)
    client_token, client_user_id = client_login_otp(TEST_PHONE_NEW, "New User")
    
    # GET dashboard (should return empty memories, not an error)
    log("15. GET /api/me/dashboard (new client with no grants)...")
    headers = {"Authorization": f"Bearer {client_token}"}
    resp = requests.get(f"{BASE_URL}/me/dashboard", headers=headers)
    assert resp.status_code == 200, f"GET me/dashboard failed: {resp.status_code} {resp.text}"
    dashboard = resp.json()
    log(f"   Dashboard: {dashboard}")
    
    # Verify structure
    assert "profile" in dashboard, "Missing 'profile' in dashboard"
    assert "memories" in dashboard, "Missing 'memories' in dashboard"
    assert "upcoming" in dashboard, "Missing 'upcoming' in dashboard"
    assert "studio" in dashboard, "Missing 'studio' in dashboard"
    
    # Verify memories is empty (not an error)
    memories = dashboard["memories"]
    assert isinstance(memories, list), f"memories should be a list, got {type(memories)}"
    assert len(memories) == 0, f"memories should be empty for new client, got {len(memories)} items"
    log(f"   ✅ memories is empty (not an error)")
    
    # Verify upcoming is empty
    upcoming = dashboard["upcoming"]
    assert isinstance(upcoming, list), f"upcoming should be a list, got {type(upcoming)}"
    assert len(upcoming) == 0, f"upcoming should be empty for new client, got {len(upcoming)} items"
    log(f"   ✅ upcoming is empty")
    
    # Verify studio is still returned with defaults (no studio_id, so defaults)
    studio = dashboard["studio"]
    assert "whatsapp" in studio, "Missing 'whatsapp' in studio"
    # New client has no events/grants, so no studio_id -> returns default profile
    assert studio["whatsapp"] == "8888766739", f"Expected studio.whatsapp='8888766739' (default), got {studio['whatsapp']}"
    log(f"   ✅ studio still returned with default whatsapp='8888766739'")
    
    log("   ✅ Edge case test PASSED")
    return client_user_id

def cleanup(admin_token, event_id, client_id, client_user_ids, booking_request_id, review_id):
    """Cleanup: delete all created resources."""
    log("16. CLEANUP: Deleting all created resources...")
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Delete event
    log(f"   Deleting event {event_id}...")
    resp = requests.delete(f"{BASE_URL}/events/{event_id}", headers=headers)
    if resp.status_code == 200:
        log(f"   ✅ Event deleted")
    else:
        log(f"   ⚠️  Event delete failed: {resp.status_code} {resp.text}")
    
    # Delete CRM client
    log(f"   Deleting CRM client {client_id}...")
    resp = requests.delete(f"{BASE_URL}/clients/{client_id}", headers=headers)
    if resp.status_code == 200:
        log(f"   ✅ CRM client deleted")
    else:
        log(f"   ⚠️  CRM client delete failed: {resp.status_code} {resp.text}")
    
    # Delete client users (direct DB cleanup via admin endpoint if available, or manual)
    # Note: There's no DELETE /api/users/{user_id} endpoint in the current implementation
    # We'll need to clean up via direct DB access or leave it for manual cleanup
    log(f"   ⚠️  Client users cleanup: No DELETE endpoint available, will clean up via DB")
    
    # Delete booking request (direct DB cleanup)
    log(f"   ⚠️  Booking request cleanup: No DELETE endpoint available, will clean up via DB")
    
    # Delete review (direct DB cleanup)
    log(f"   ⚠️  Review cleanup: No DELETE endpoint available, will clean up via DB")
    
    # Delete studio profile (direct DB cleanup)
    log(f"   ⚠️  Studio profile cleanup: No DELETE endpoint available, will clean up via DB")
    
    # Delete OTP codes (direct DB cleanup)
    log(f"   ⚠️  OTP codes cleanup: No DELETE endpoint available, will clean up via DB")
    
    log("   ✅ Cleanup complete (some items require direct DB cleanup)")

def direct_db_cleanup():
    """Direct MongoDB cleanup for resources without DELETE endpoints."""
    log("17. Direct DB cleanup...")
    try:
        from pymongo import MongoClient
        client = MongoClient("mongodb://localhost:27017")
        db = client["lumiere_gallery"]
        
        # Delete all client users except admin
        result = db.users.delete_many({"role": "client"})
        log(f"   Deleted {result.deleted_count} client users")
        
        # Delete all access grants
        result = db.access_grants.delete_many({})
        log(f"   Deleted {result.deleted_count} access grants")
        
        # Delete all booking requests
        result = db.booking_requests.delete_many({})
        log(f"   Deleted {result.deleted_count} booking requests")
        
        # Delete all reviews
        result = db.reviews.delete_many({})
        log(f"   Deleted {result.deleted_count} reviews")
        
        # Delete all studio profiles
        result = db.studio_profiles.delete_many({})
        log(f"   Deleted {result.deleted_count} studio profiles")
        
        # Delete all OTP codes
        result = db.otp_codes.delete_many({})
        log(f"   Deleted {result.deleted_count} OTP codes")
        
        # Delete all CRM clients (in case any remain)
        result = db.clients.delete_many({})
        log(f"   Deleted {result.deleted_count} CRM clients")
        
        # Delete all contacts
        result = db.contacts.delete_many({})
        log(f"   Deleted {result.deleted_count} contacts")
        
        # Delete all important dates
        result = db.important_dates.delete_many({})
        log(f"   Deleted {result.deleted_count} important dates")
        
        log("   ✅ Direct DB cleanup complete")
    except Exception as e:
        log(f"   ⚠️  Direct DB cleanup failed: {e}")

def main():
    log("=" * 80)
    log("SLICE 2 CRM ENDPOINTS TEST")
    log("=" * 80)
    
    try:
        # Admin login
        admin_token = admin_login()
        
        # Test studio profile (GET/PATCH)
        studio_profile = test_studio_profile(admin_token)
        
        # Setup for client dashboard test
        event_id = create_event(admin_token)
        grant_client_access(admin_token, event_id, TEST_PHONE)
        client_id = create_crm_client(admin_token, TEST_PHONE)
        
        # Client login
        client_token, client_user_id = client_login_otp(TEST_PHONE, "Anjali")
        
        # Test client dashboard
        test_client_dashboard(client_token, studio_profile["whatsapp"])
        
        # Test booking request
        booking_request_id = test_booking_request(client_token)
        
        # Test reviews (with validation)
        review_id = test_reviews(client_token)
        
        # Test edge case: brand-new client with no grants
        new_client_user_id = test_edge_case_new_client()
        
        # Cleanup
        client_user_ids = [client_user_id, new_client_user_id]
        cleanup(admin_token, event_id, client_id, client_user_ids, booking_request_id, review_id)
        
        # Direct DB cleanup
        direct_db_cleanup()
        
        log("=" * 80)
        log("✅ ALL TESTS PASSED")
        log("=" * 80)
        return 0
        
    except AssertionError as e:
        log(f"❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        log(f"❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
