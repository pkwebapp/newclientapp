#!/usr/bin/env python3
"""
Backend test for CRM client-group assignments for galleries and albums.
Tests the new multi-client assignment feature where every contact in an assigned
CRM client/family receives the same access as a direct person grant.
"""
import io
import sys
import requests
from PIL import Image
import fitz  # PyMuPDF

# Backend URL from frontend/.env
BASE_URL = "https://newclient-app-1.preview.emergentagent.com/api"

# Admin credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

# Test data
TEST_CLIENT_1_NAME = "Test Family Alpha"
TEST_CLIENT_2_NAME = "Test Family Beta"
TEST_CONTACT_1A_NAME = "Alice Alpha"
TEST_CONTACT_1A_PHONE = "+919000000101"
TEST_CONTACT_1A_EMAIL = "alice.alpha@test.example"
TEST_CONTACT_1B_NAME = "Bob Alpha"
TEST_CONTACT_1B_PHONE = "+919000000102"
TEST_CONTACT_2A_NAME = "Charlie Beta"
TEST_CONTACT_2A_PHONE = "+919000000201"
TEST_CONTACT_2A_EMAIL = "charlie.beta@test.example"
TEST_EVENT_NAME = "QA CRM Assignment Test Event"
TEST_ALBUM_TITLE = "QA CRM Assignment Test Album"

# Global state
admin_token = None
client1_id = None
client2_id = None
contact1a_id = None
contact1b_id = None
contact2a_id = None
event_id = None
album_id = None
new_contact_id = None

# Tracking for cleanup
created_resources = {
    "events": [],
    "albums": [],
    "clients": [],
    "otp_codes": [],
}

def log(msg):
    print(f"  {msg}")

def fail(msg):
    print(f"❌ FAIL: {msg}")
    sys.exit(1)

def create_test_image(width=400, height=400):
    """Create a simple test JPEG image."""
    img = Image.new('RGB', (width, height), color='white')
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    return buf.getvalue()

def create_test_pdf():
    """Create a simple 7-page test PDF (cover + 5 spreads + back)."""
    doc = fitz.open()
    # Cover (12x18)
    page = doc.new_page(width=12*72, height=18*72)
    page.insert_text((100, 100), "Cover", fontsize=24)
    # 5 spreads (12x36 each)
    for i in range(5):
        page = doc.new_page(width=12*72, height=36*72)
        page.insert_text((100, 100), f"Spread {i+1}", fontsize=24)
    # Back cover (12x18)
    page = doc.new_page(width=12*72, height=18*72)
    page.insert_text((100, 100), "Back Cover", fontsize=24)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()

def test_admin_login():
    global admin_token
    log("Admin login...")
    resp = requests.post(f"{BASE_URL}/auth/admin/login", json={
        "email": ADMIN_EMAIL,
        "password": ADMIN_PASSWORD,
    })
    if resp.status_code != 200:
        fail(f"Admin login failed: {resp.status_code} {resp.text}")
    data = resp.json()
    admin_token = data.get("session_token")
    if not admin_token:
        fail("No session_token in admin login response")
    log(f"✅ Admin logged in")

def test_create_crm_clients():
    global client1_id, client2_id, contact1a_id, contact1b_id, contact2a_id
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Create Client 1 with 2 contacts
    log(f"Creating CRM client 1: {TEST_CLIENT_1_NAME} with 2 contacts...")
    resp = requests.post(f"{BASE_URL}/clients", headers=headers, json={
        "name": TEST_CLIENT_1_NAME,
        "type": "family",
        "status": "active",
        "contacts": [
            {
                "name": TEST_CONTACT_1A_NAME,
                "phone": TEST_CONTACT_1A_PHONE,
                "email": TEST_CONTACT_1A_EMAIL,
                "role": "primary",
                "is_primary": True,
            },
            {
                "name": TEST_CONTACT_1B_NAME,
                "phone": TEST_CONTACT_1B_PHONE,
                "role": "spouse",
            }
        ]
    })
    if resp.status_code != 200:
        fail(f"Create client 1 failed: {resp.status_code} {resp.text}")
    data = resp.json()
    client1_id = data.get("client_id")
    created_resources["clients"].append(client1_id)
    contacts = data.get("contacts", [])
    if len(contacts) < 2:
        fail(f"Expected 2 contacts for client 1, got {len(contacts)}")
    contact1a_id = contacts[0]["contact_id"]
    contact1b_id = contacts[1]["contact_id"]
    log(f"✅ Client 1 created: {client1_id} with contacts {contact1a_id}, {contact1b_id}")
    
    # Create Client 2 with 1 contact
    log(f"Creating CRM client 2: {TEST_CLIENT_2_NAME} with 1 contact...")
    resp = requests.post(f"{BASE_URL}/clients", headers=headers, json={
        "name": TEST_CLIENT_2_NAME,
        "type": "family",
        "status": "active",
        "contacts": [
            {
                "name": TEST_CONTACT_2A_NAME,
                "phone": TEST_CONTACT_2A_PHONE,
                "email": TEST_CONTACT_2A_EMAIL,
                "role": "primary",
                "is_primary": True,
            }
        ]
    })
    if resp.status_code != 200:
        fail(f"Create client 2 failed: {resp.status_code} {resp.text}")
    data = resp.json()
    client2_id = data.get("client_id")
    created_resources["clients"].append(client2_id)
    contacts = data.get("contacts", [])
    if len(contacts) < 1:
        fail(f"Expected 1 contact for client 2, got {len(contacts)}")
    contact2a_id = contacts[0]["contact_id"]
    log(f"✅ Client 2 created: {client2_id} with contact {contact2a_id}")

def test_create_event():
    global event_id
    headers = {"Authorization": f"Bearer {admin_token}"}
    log(f"Creating event: {TEST_EVENT_NAME}...")
    resp = requests.post(f"{BASE_URL}/events", headers=headers, json={
        "name": TEST_EVENT_NAME,
        "category": "event",
        "date": "2026-01-15",
    })
    if resp.status_code != 200:
        fail(f"Create event failed: {resp.status_code} {resp.text}")
    data = resp.json()
    event_id = data.get("event_id")
    created_resources["events"].append(event_id)
    log(f"✅ Event created: {event_id}")

def test_create_album():
    global album_id
    headers = {"Authorization": f"Bearer {admin_token}"}
    log(f"Creating album: {TEST_ALBUM_TITLE}...")
    resp = requests.post(f"{BASE_URL}/albums", headers=headers, json={
        "title": TEST_ALBUM_TITLE,
        "client_name": "Test Client",
        "event_name": TEST_EVENT_NAME,
    })
    if resp.status_code != 200:
        fail(f"Create album failed: {resp.status_code} {resp.text}")
    data = resp.json()
    album_id = data.get("album_id")
    created_resources["albums"].append(album_id)
    log(f"✅ Album created: {album_id}")

def test_upload_album_pdf():
    headers = {"Authorization": f"Bearer {admin_token}"}
    log("Uploading test PDF to album...")
    pdf_bytes = create_test_pdf()
    files = {"file": ("test_album.pdf", pdf_bytes, "application/pdf")}
    resp = requests.post(f"{BASE_URL}/albums/{album_id}/pdf", headers=headers, files=files)
    if resp.status_code != 200:
        fail(f"Upload PDF failed: {resp.status_code} {resp.text}")
    data = resp.json()
    if data.get("page_count") != 7:
        fail(f"Expected 7 pages, got {data.get('page_count')}")
    if data.get("total_spreads") != 5:
        fail(f"Expected 5 spreads, got {data.get('total_spreads')}")
    log(f"✅ PDF uploaded: {data.get('page_count')} pages, {data.get('total_spreads')} spreads")

def test_assign_event_clients():
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Assign client 1 with full_gallery_access=true
    log(f"Assigning client 1 ({client1_id}) to event with full_gallery_access=true...")
    resp = requests.post(f"{BASE_URL}/events/{event_id}/client-assignments", headers=headers, json={
        "client_id": client1_id,
        "full_gallery_access": True,
    })
    if resp.status_code != 200:
        fail(f"Assign client 1 failed: {resp.status_code} {resp.text}")
    data = resp.json()
    if data.get("status") != "assigned":
        fail(f"Expected status 'assigned', got {data.get('status')}")
    assignments = data.get("assignments", [])
    if len(assignments) != 1:
        fail(f"Expected 1 assignment, got {len(assignments)}")
    if assignments[0].get("client_id") != client1_id:
        fail(f"Expected client_id {client1_id}, got {assignments[0].get('client_id')}")
    if assignments[0].get("client_name") != TEST_CLIENT_1_NAME:
        fail(f"Expected client_name {TEST_CLIENT_1_NAME}, got {assignments[0].get('client_name')}")
    if assignments[0].get("contact_count") != 2:
        fail(f"Expected contact_count 2, got {assignments[0].get('contact_count')}")
    if not assignments[0].get("full_gallery_access"):
        fail("Expected full_gallery_access=true")
    log(f"✅ Client 1 assigned with full_gallery_access=true")
    
    # Assign client 2 with full_gallery_access=false
    log(f"Assigning client 2 ({client2_id}) to event with full_gallery_access=false...")
    resp = requests.post(f"{BASE_URL}/events/{event_id}/client-assignments", headers=headers, json={
        "client_id": client2_id,
        "full_gallery_access": False,
    })
    if resp.status_code != 200:
        fail(f"Assign client 2 failed: {resp.status_code} {resp.text}")
    data = resp.json()
    assignments = data.get("assignments", [])
    if len(assignments) != 2:
        fail(f"Expected 2 assignments, got {len(assignments)}")
    # Find client 2 assignment
    client2_assignment = next((a for a in assignments if a.get("client_id") == client2_id), None)
    if not client2_assignment:
        fail("Client 2 assignment not found")
    if client2_assignment.get("full_gallery_access"):
        fail("Expected full_gallery_access=false for client 2")
    log(f"✅ Client 2 assigned with full_gallery_access=false")
    
    # Verify GET assignments returns both
    log("Verifying GET /api/events/{event_id}/client-assignments...")
    resp = requests.get(f"{BASE_URL}/events/{event_id}/client-assignments", headers=headers)
    if resp.status_code != 200:
        fail(f"GET assignments failed: {resp.status_code} {resp.text}")
    assignments = resp.json()
    if len(assignments) != 2:
        fail(f"Expected 2 assignments, got {len(assignments)}")
    log(f"✅ GET assignments returned 2 assignments")
    
    # Update client 1 assignment (assign again with different full_gallery_access)
    log("Updating client 1 assignment (assign again with full_gallery_access=false)...")
    resp = requests.post(f"{BASE_URL}/events/{event_id}/client-assignments", headers=headers, json={
        "client_id": client1_id,
        "full_gallery_access": False,
    })
    if resp.status_code != 200:
        fail(f"Update client 1 assignment failed: {resp.status_code} {resp.text}")
    data = resp.json()
    assignments = data.get("assignments", [])
    if len(assignments) != 2:
        fail(f"Expected 2 assignments (no duplicate), got {len(assignments)}")
    client1_assignment = next((a for a in assignments if a.get("client_id") == client1_id), None)
    if not client1_assignment:
        fail("Client 1 assignment not found after update")
    if client1_assignment.get("full_gallery_access"):
        fail("Expected full_gallery_access=false after update")
    log(f"✅ Client 1 assignment updated (no duplicate)")
    
    # Restore client 1 to full_gallery_access=true for later tests
    resp = requests.post(f"{BASE_URL}/events/{event_id}/client-assignments", headers=headers, json={
        "client_id": client1_id,
        "full_gallery_access": True,
    })
    if resp.status_code != 200:
        fail(f"Restore client 1 assignment failed: {resp.status_code} {resp.text}")

def test_client_login_and_event_access():
    # Test contact 1A (from client 1, full_gallery_access=true)
    log(f"Testing contact 1A ({TEST_CONTACT_1A_NAME}) login via OTP...")
    resp = requests.post(f"{BASE_URL}/auth/client/request-otp", json={
        "channel": "phone",
        "phone": TEST_CONTACT_1A_PHONE,
    })
    if resp.status_code != 200:
        fail(f"Request OTP for contact 1A failed: {resp.status_code} {resp.text}")
    data = resp.json()
    dev_code = data.get("dev_code")
    if not dev_code:
        fail("No dev_code in OTP response (OTP_DEV_MODE should be true)")
    log(f"  OTP dev_code: {dev_code}")
    
    resp = requests.post(f"{BASE_URL}/auth/client/verify-otp", json={
        "channel": "phone",
        "phone": TEST_CONTACT_1A_PHONE,
        "code": dev_code,
        "name": TEST_CONTACT_1A_NAME,
    })
    if resp.status_code != 200:
        fail(f"Verify OTP for contact 1A failed: {resp.status_code} {resp.text}")
    data = resp.json()
    contact1a_token = data.get("session_token")
    if not contact1a_token:
        fail("No session_token for contact 1A")
    log(f"✅ Contact 1A logged in")
    
    # Verify contact 1A can see the event in GET /api/client/events
    log("Verifying contact 1A can see the event in GET /api/client/events...")
    headers = {"Authorization": f"Bearer {contact1a_token}"}
    resp = requests.get(f"{BASE_URL}/client/events", headers=headers)
    if resp.status_code != 200:
        fail(f"GET /api/client/events for contact 1A failed: {resp.status_code} {resp.text}")
    events = resp.json()
    event_ids = [e.get("event_id") for e in events]
    if event_id not in event_ids:
        fail(f"Event {event_id} not found in contact 1A's events")
    event_data = next((e for e in events if e.get("event_id") == event_id), None)
    if not event_data.get("full_gallery_access"):
        fail("Expected full_gallery_access=true for contact 1A")
    log(f"✅ Contact 1A can see the event with full_gallery_access=true")
    
    # Verify contact 1A can call GET /api/client/events/{id}/photos (full access)
    log("Verifying contact 1A can call GET /api/client/events/{id}/photos...")
    resp = requests.get(f"{BASE_URL}/client/events/{event_id}/photos", headers=headers)
    if resp.status_code != 200:
        fail(f"GET /api/client/events/{event_id}/photos for contact 1A failed: {resp.status_code} {resp.text}")
    log(f"✅ Contact 1A can access full gallery photos")
    
    # Test contact 2A (from client 2, full_gallery_access=false)
    log(f"Testing contact 2A ({TEST_CONTACT_2A_NAME}) login via OTP...")
    resp = requests.post(f"{BASE_URL}/auth/client/request-otp", json={
        "channel": "phone",
        "phone": TEST_CONTACT_2A_PHONE,
    })
    if resp.status_code != 200:
        fail(f"Request OTP for contact 2A failed: {resp.status_code} {resp.text}")
    data = resp.json()
    dev_code = data.get("dev_code")
    if not dev_code:
        fail("No dev_code in OTP response")
    
    resp = requests.post(f"{BASE_URL}/auth/client/verify-otp", json={
        "channel": "phone",
        "phone": TEST_CONTACT_2A_PHONE,
        "code": dev_code,
        "name": TEST_CONTACT_2A_NAME,
    })
    if resp.status_code != 200:
        fail(f"Verify OTP for contact 2A failed: {resp.status_code} {resp.text}")
    data = resp.json()
    contact2a_token = data.get("session_token")
    if not contact2a_token:
        fail("No session_token for contact 2A")
    log(f"✅ Contact 2A logged in")
    
    # Verify contact 2A can see the event
    log("Verifying contact 2A can see the event in GET /api/client/events...")
    headers = {"Authorization": f"Bearer {contact2a_token}"}
    resp = requests.get(f"{BASE_URL}/client/events", headers=headers)
    if resp.status_code != 200:
        fail(f"GET /api/client/events for contact 2A failed: {resp.status_code} {resp.text}")
    events = resp.json()
    event_ids = [e.get("event_id") for e in events]
    if event_id not in event_ids:
        fail(f"Event {event_id} not found in contact 2A's events")
    event_data = next((e for e in events if e.get("event_id") == event_id), None)
    if event_data.get("full_gallery_access"):
        fail("Expected full_gallery_access=false for contact 2A")
    log(f"✅ Contact 2A can see the event with full_gallery_access=false")
    
    # Verify contact 2A cannot call GET /api/client/events/{id}/photos (matched-only)
    log("Verifying contact 2A cannot call GET /api/client/events/{id}/photos (matched-only)...")
    resp = requests.get(f"{BASE_URL}/client/events/{event_id}/photos", headers=headers)
    if resp.status_code == 200:
        fail("Expected 403 for contact 2A trying to access full gallery photos")
    if resp.status_code != 403:
        fail(f"Expected 403, got {resp.status_code} {resp.text}")
    log(f"✅ Contact 2A correctly blocked from full gallery access (403)")

def test_add_new_contact_inherits_access():
    global new_contact_id
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Add a new contact to client 1 (already assigned to event)
    log(f"Adding new contact to client 1 (already assigned)...")
    new_contact_name = "Diana Alpha"
    new_contact_phone = "+919000000103"
    resp = requests.post(f"{BASE_URL}/clients/{client1_id}/contacts", headers=headers, json={
        "name": new_contact_name,
        "phone": new_contact_phone,
        "role": "child",
    })
    if resp.status_code != 200:
        fail(f"Add new contact failed: {resp.status_code} {resp.text}")
    data = resp.json()
    new_contact_id = data.get("contact_id")
    log(f"✅ New contact added: {new_contact_id}")
    
    # Log in as the new contact
    log(f"Logging in as new contact ({new_contact_name})...")
    resp = requests.post(f"{BASE_URL}/auth/client/request-otp", json={
        "channel": "phone",
        "phone": new_contact_phone,
    })
    if resp.status_code != 200:
        fail(f"Request OTP for new contact failed: {resp.status_code} {resp.text}")
    data = resp.json()
    dev_code = data.get("dev_code")
    
    resp = requests.post(f"{BASE_URL}/auth/client/verify-otp", json={
        "channel": "phone",
        "phone": new_contact_phone,
        "code": dev_code,
        "name": new_contact_name,
    })
    if resp.status_code != 200:
        fail(f"Verify OTP for new contact failed: {resp.status_code} {resp.text}")
    data = resp.json()
    new_contact_token = data.get("session_token")
    log(f"✅ New contact logged in")
    
    # Verify new contact can see the event (inherits access from client 1 assignment)
    log("Verifying new contact inherits event access from client 1 assignment...")
    headers_new = {"Authorization": f"Bearer {new_contact_token}"}
    resp = requests.get(f"{BASE_URL}/client/events", headers=headers_new)
    if resp.status_code != 200:
        fail(f"GET /api/client/events for new contact failed: {resp.status_code} {resp.text}")
    events = resp.json()
    event_ids = [e.get("event_id") for e in events]
    if event_id not in event_ids:
        fail(f"Event {event_id} not found in new contact's events (should inherit from client 1)")
    log(f"✅ New contact inherits event access without individual grant")
    
    # Remove client 1 assignment
    log("Removing client 1 assignment from event...")
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = requests.delete(f"{BASE_URL}/events/{event_id}/client-assignments/{client1_id}", headers=headers)
    if resp.status_code != 200:
        fail(f"Remove client 1 assignment failed: {resp.status_code} {resp.text}")
    log(f"✅ Client 1 assignment removed")
    
    # Verify new contact loses access
    log("Verifying new contact loses access after assignment removal...")
    resp = requests.get(f"{BASE_URL}/client/events", headers=headers_new)
    if resp.status_code != 200:
        fail(f"GET /api/client/events for new contact failed: {resp.status_code} {resp.text}")
    events = resp.json()
    event_ids = [e.get("event_id") for e in events]
    if event_id in event_ids:
        fail(f"Event {event_id} still in new contact's events after assignment removal")
    log(f"✅ New contact correctly loses access after assignment removal")
    
    # Verify trying to access photos returns 403
    log("Verifying new contact gets 403 when trying to access event photos...")
    resp = requests.get(f"{BASE_URL}/client/events/{event_id}/photos", headers=headers_new)
    if resp.status_code != 403:
        fail(f"Expected 403 for new contact after assignment removal, got {resp.status_code}")
    log(f"✅ New contact correctly gets 403 after assignment removal")
    
    # Restore client 1 assignment for later tests
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = requests.post(f"{BASE_URL}/events/{event_id}/client-assignments", headers=headers, json={
        "client_id": client1_id,
        "full_gallery_access": True,
    })
    if resp.status_code != 200:
        fail(f"Restore client 1 assignment failed: {resp.status_code} {resp.text}")

def test_assign_album_clients():
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Assign client 1 to album
    log(f"Assigning client 1 ({client1_id}) to album...")
    resp = requests.post(f"{BASE_URL}/albums/{album_id}/client-assignments", headers=headers, json={
        "client_id": client1_id,
    })
    if resp.status_code != 200:
        fail(f"Assign client 1 to album failed: {resp.status_code} {resp.text}")
    data = resp.json()
    if data.get("status") != "assigned":
        fail(f"Expected status 'assigned', got {data.get('status')}")
    assignments = data.get("assignments", [])
    if len(assignments) != 1:
        fail(f"Expected 1 assignment, got {len(assignments)}")
    log(f"✅ Client 1 assigned to album")
    
    # Assign client 2 to album
    log(f"Assigning client 2 ({client2_id}) to album...")
    resp = requests.post(f"{BASE_URL}/albums/{album_id}/client-assignments", headers=headers, json={
        "client_id": client2_id,
    })
    if resp.status_code != 200:
        fail(f"Assign client 2 to album failed: {resp.status_code} {resp.text}")
    data = resp.json()
    assignments = data.get("assignments", [])
    if len(assignments) != 2:
        fail(f"Expected 2 assignments, got {len(assignments)}")
    log(f"✅ Client 2 assigned to album")
    
    # Verify GET assignments returns both
    log("Verifying GET /api/albums/{album_id}/client-assignments...")
    resp = requests.get(f"{BASE_URL}/albums/{album_id}/client-assignments", headers=headers)
    if resp.status_code != 200:
        fail(f"GET album assignments failed: {resp.status_code} {resp.text}")
    assignments = resp.json()
    if len(assignments) != 2:
        fail(f"Expected 2 assignments, got {len(assignments)}")
    log(f"✅ GET album assignments returned 2 assignments")
    
    # Publish the album
    log("Publishing album...")
    resp = requests.post(f"{BASE_URL}/albums/{album_id}/publish", headers=headers)
    if resp.status_code != 200:
        fail(f"Publish album failed: {resp.status_code} {resp.text}")
    data = resp.json()
    if data.get("status") != "published":
        fail(f"Expected status 'published', got {data.get('status')}")
    log(f"✅ Album published")
    
    # Verify contact 1A can see the album in GET /api/albums/client/mine
    log("Verifying contact 1A can see the album...")
    resp = requests.post(f"{BASE_URL}/auth/client/request-otp", json={
        "channel": "phone",
        "phone": TEST_CONTACT_1A_PHONE,
    })
    if resp.status_code != 200:
        fail(f"Request OTP for contact 1A failed: {resp.status_code} {resp.text}")
    dev_code = resp.json().get("dev_code")
    
    resp = requests.post(f"{BASE_URL}/auth/client/verify-otp", json={
        "channel": "phone",
        "phone": TEST_CONTACT_1A_PHONE,
        "code": dev_code,
    })
    if resp.status_code != 200:
        fail(f"Verify OTP for contact 1A failed: {resp.status_code} {resp.text}")
    contact1a_token = resp.json().get("session_token")
    
    headers_1a = {"Authorization": f"Bearer {contact1a_token}"}
    resp = requests.get(f"{BASE_URL}/albums/client/mine", headers=headers_1a)
    if resp.status_code != 200:
        fail(f"GET /api/albums/client/mine for contact 1A failed: {resp.status_code} {resp.text}")
    albums = resp.json()
    album_ids = [a.get("album_id") for a in albums]
    if album_id not in album_ids:
        fail(f"Album {album_id} not found in contact 1A's albums")
    log(f"✅ Contact 1A can see the album")
    
    # Verify contact 2A can see the album
    log("Verifying contact 2A can see the album...")
    resp = requests.post(f"{BASE_URL}/auth/client/request-otp", json={
        "channel": "phone",
        "phone": TEST_CONTACT_2A_PHONE,
    })
    if resp.status_code != 200:
        fail(f"Request OTP for contact 2A failed: {resp.status_code} {resp.text}")
    dev_code = resp.json().get("dev_code")
    
    resp = requests.post(f"{BASE_URL}/auth/client/verify-otp", json={
        "channel": "phone",
        "phone": TEST_CONTACT_2A_PHONE,
        "code": dev_code,
    })
    if resp.status_code != 200:
        fail(f"Verify OTP for contact 2A failed: {resp.status_code} {resp.text}")
    contact2a_token = resp.json().get("session_token")
    
    headers_2a = {"Authorization": f"Bearer {contact2a_token}"}
    resp = requests.get(f"{BASE_URL}/albums/client/mine", headers=headers_2a)
    if resp.status_code != 200:
        fail(f"GET /api/albums/client/mine for contact 2A failed: {resp.status_code} {resp.text}")
    albums = resp.json()
    album_ids = [a.get("album_id") for a in albums]
    if album_id not in album_ids:
        fail(f"Album {album_id} not found in contact 2A's albums")
    log(f"✅ Contact 2A can see the album")
    
    # Remove client 2 assignment
    log("Removing client 2 assignment from album...")
    headers = {"Authorization": f"Bearer {admin_token}"}
    resp = requests.delete(f"{BASE_URL}/albums/{album_id}/client-assignments/{client2_id}", headers=headers)
    if resp.status_code != 200:
        fail(f"Remove client 2 assignment failed: {resp.status_code} {resp.text}")
    log(f"✅ Client 2 assignment removed from album")
    
    # Verify contact 2A no longer sees the album
    log("Verifying contact 2A no longer sees the album...")
    resp = requests.get(f"{BASE_URL}/albums/client/mine", headers=headers_2a)
    if resp.status_code != 200:
        fail(f"GET /api/albums/client/mine for contact 2A failed: {resp.status_code} {resp.text}")
    albums = resp.json()
    album_ids = [a.get("album_id") for a in albums]
    if album_id in album_ids:
        fail(f"Album {album_id} still in contact 2A's albums after assignment removal")
    log(f"✅ Contact 2A no longer sees the album")
    
    # Verify contact 1A still sees the album
    log("Verifying contact 1A still sees the album...")
    resp = requests.get(f"{BASE_URL}/albums/client/mine", headers=headers_1a)
    if resp.status_code != 200:
        fail(f"GET /api/albums/client/mine for contact 1A failed: {resp.status_code} {resp.text}")
    albums = resp.json()
    album_ids = [a.get("album_id") for a in albums]
    if album_id not in album_ids:
        fail(f"Album {album_id} not found in contact 1A's albums (should still have access)")
    log(f"✅ Contact 1A still sees the album")

def test_admin_authorization():
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Test missing token returns 401
    log("Testing missing token returns 401...")
    resp = requests.get(f"{BASE_URL}/events/{event_id}/client-assignments")
    if resp.status_code != 401:
        fail(f"Expected 401 for missing token, got {resp.status_code}")
    log(f"✅ Missing token returns 401")
    
    # Test invalid client_id returns 404
    log("Testing invalid client_id returns 404...")
    resp = requests.post(f"{BASE_URL}/events/{event_id}/client-assignments", headers=headers, json={
        "client_id": "cli_nonexistent",
        "full_gallery_access": True,
    })
    if resp.status_code != 404:
        fail(f"Expected 404 for invalid client_id, got {resp.status_code}")
    log(f"✅ Invalid client_id returns 404")

def cleanup():
    log("Cleaning up test data...")
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Delete event
    if event_id:
        log(f"Deleting event {event_id}...")
        resp = requests.delete(f"{BASE_URL}/events/{event_id}", headers=headers)
        if resp.status_code == 200:
            log(f"  ✅ Event deleted")
        else:
            log(f"  ⚠️  Event deletion failed: {resp.status_code}")
    
    # Delete album
    if album_id:
        log(f"Deleting album {album_id}...")
        resp = requests.delete(f"{BASE_URL}/albums/{album_id}", headers=headers)
        if resp.status_code == 200:
            log(f"  ✅ Album deleted")
        else:
            log(f"  ⚠️  Album deletion failed: {resp.status_code}")
    
    # Delete CRM clients
    for client_id in created_resources["clients"]:
        log(f"Deleting client {client_id}...")
        resp = requests.delete(f"{BASE_URL}/clients/{client_id}", headers=headers)
        if resp.status_code == 200:
            log(f"  ✅ Client deleted")
        else:
            log(f"  ⚠️  Client deletion failed: {resp.status_code}")
    
    log("✅ Cleanup complete")

def main():
    print("\n" + "="*80)
    print("CRM CLIENT-GROUP ASSIGNMENT BACKEND TESTS")
    print("="*80 + "\n")
    
    try:
        print("SETUP:")
        test_admin_login()
        test_create_crm_clients()
        test_create_event()
        test_create_album()
        test_upload_album_pdf()
        
        print("\nGALLERY CLIENT-GROUP ASSIGNMENTS:")
        test_assign_event_clients()
        
        print("\nCLIENT LOGIN & EVENT ACCESS:")
        test_client_login_and_event_access()
        
        print("\nNEW CONTACT INHERITANCE:")
        test_add_new_contact_inherits_access()
        
        print("\nALBUM CLIENT-GROUP ASSIGNMENTS:")
        test_assign_album_clients()
        
        print("\nADMIN AUTHORIZATION:")
        test_admin_authorization()
        
        print("\nCLEANUP:")
        cleanup()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS PASSED")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED WITH EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        print("\nAttempting cleanup...")
        try:
            cleanup()
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
