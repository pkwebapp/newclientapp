#!/usr/bin/env python3
"""
Comprehensive backend test for CRM / Client-Relationship layer.
Tests all CRM endpoints including multi-tenant isolation.
"""
import requests
import sys
import time

# Backend URL from environment
BASE_URL = "https://design-showcase-1848.preview.emergentagent.com/api"

# Test credentials
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

# Test counters
tests_passed = 0
tests_failed = 0
test_results = []

def log_test(name, passed, details=""):
    global tests_passed, tests_failed
    if passed:
        tests_passed += 1
        status = "✅ PASS"
    else:
        tests_failed += 1
        status = "❌ FAIL"
    msg = f"{status}: {name}"
    if details:
        msg += f" - {details}"
    print(msg)
    test_results.append({"name": name, "passed": passed, "details": details})

def admin_login(email, password):
    """Login as admin and return session token."""
    resp = requests.post(f"{BASE_URL}/auth/admin/login", json={
        "email": email,
        "password": password
    })
    if resp.status_code == 200:
        return resp.json().get("session_token")
    return None

def admin_register(email, password, name="Test Admin"):
    """Register a new admin account."""
    resp = requests.post(f"{BASE_URL}/auth/admin/register", json={
        "name": name,
        "email": email,
        "password": password
    })
    return resp

print("=" * 80)
print("CRM BACKEND TESTING - Comprehensive Test Suite")
print("=" * 80)

# Step 1: Admin login
print("\n[1] Admin Authentication")
admin_token = admin_login(ADMIN_EMAIL, ADMIN_PASSWORD)
if admin_token:
    log_test("Admin login", True, f"Token: {admin_token[:20]}...")
else:
    log_test("Admin login", False, "Failed to get session token")
    sys.exit(1)

headers = {"Authorization": f"Bearer {admin_token}"}

# Step 2: Create client with inline contacts and important_dates
print("\n[2] Create Client with Inline Contacts & Important Dates")
client_data = {
    "name": "Smith Family",
    "type": "family",
    "status": "active",
    "tags": ["wedding", "premium"],
    "notes": "High-value client",
    "contacts": [
        {
            "name": "John Smith",
            "role": "groom",
            "phone": "+1234567890",
            "email": "john@smith.com",
            "is_primary": True
        },
        {
            "name": "Jane Smith",
            "role": "bride",
            "phone": "+1234567891",
            "email": "jane@smith.com",
            "is_primary": False
        }
    ],
    "important_dates": [
        {
            "person_label": "John & Jane",
            "occasion": "Wedding Anniversary",
            "date": "2024-06-15",
            "recurring": True,
            "notes": "Send anniversary wishes"
        },
        {
            "person_label": "John",
            "occasion": "Birthday",
            "date": "03-20",
            "recurring": True
        }
    ]
}

resp = requests.post(f"{BASE_URL}/clients", json=client_data, headers=headers)
if resp.status_code == 200:
    client = resp.json()
    client_id = client.get("client_id")
    log_test("Create client", True, f"client_id={client_id}")
    
    # Verify response structure
    has_contacts = "contacts" in client and len(client["contacts"]) == 2
    has_dates = "important_dates" in client and len(client["important_dates"]) == 2
    has_stats = "stats" in client
    
    log_test("Client response has contacts", has_contacts, f"Count: {len(client.get('contacts', []))}")
    log_test("Client response has important_dates", has_dates, f"Count: {len(client.get('important_dates', []))}")
    log_test("Client response has stats", has_stats, f"Stats: {client.get('stats')}")
else:
    log_test("Create client", False, f"Status {resp.status_code}: {resp.text}")
    sys.exit(1)

# Step 3: Test invalid type
print("\n[3] Test Invalid Client Type")
resp = requests.post(f"{BASE_URL}/clients", json={
    "name": "Test Invalid",
    "type": "invalid_type",
    "status": "active"
}, headers=headers)
log_test("Invalid type returns 400", resp.status_code == 400, f"Status: {resp.status_code}")

# Step 4: Test invalid status
print("\n[4] Test Invalid Client Status")
resp = requests.post(f"{BASE_URL}/clients", json={
    "name": "Test Invalid",
    "type": "family",
    "status": "invalid_status"
}, headers=headers)
log_test("Invalid status returns 400", resp.status_code == 400, f"Status: {resp.status_code}")

# Step 5: List clients
print("\n[5] List Clients")
resp = requests.get(f"{BASE_URL}/clients", headers=headers)
if resp.status_code == 200:
    clients = resp.json()
    log_test("List clients", True, f"Count: {len(clients)}")
    
    # Verify stats and primary contact preview
    if clients:
        first = clients[0]
        has_stats = "stats" in first and "contact_count" in first["stats"] and "event_count" in first["stats"]
        has_contacts = "contacts" in first
        log_test("List includes stats", has_stats, f"Stats: {first.get('stats')}")
        log_test("List includes primary contact preview", has_contacts, f"Contacts: {len(first.get('contacts', []))}")
else:
    log_test("List clients", False, f"Status {resp.status_code}: {resp.text}")

# Step 6: Test q= search (contact name)
print("\n[6] Test Free-Text Search (q=)")
resp = requests.get(f"{BASE_URL}/clients?q=John", headers=headers)
if resp.status_code == 200:
    results = resp.json()
    found = any(c["client_id"] == client_id for c in results)
    log_test("Search by contact name", found, f"Found {len(results)} results")
else:
    log_test("Search by contact name", False, f"Status {resp.status_code}")

# Step 7: Test q= search (phone)
resp = requests.get(f"{BASE_URL}/clients?q=1234567890", headers=headers)
if resp.status_code == 200:
    results = resp.json()
    found = any(c["client_id"] == client_id for c in results)
    log_test("Search by contact phone", found, f"Found {len(results)} results")
else:
    log_test("Search by contact phone", False, f"Status {resp.status_code}")

# Step 8: Test q= search (email)
resp = requests.get(f"{BASE_URL}/clients?q=jane@smith.com", headers=headers)
if resp.status_code == 200:
    results = resp.json()
    found = any(c["client_id"] == client_id for c in results)
    log_test("Search by contact email", found, f"Found {len(results)} results")
else:
    log_test("Search by contact email", False, f"Status {resp.status_code}")

# Step 9: Test status filter
print("\n[7] Test Status Filter")
resp = requests.get(f"{BASE_URL}/clients?status=active", headers=headers)
if resp.status_code == 200:
    results = resp.json()
    all_active = all(c.get("status") == "active" for c in results)
    log_test("Status filter", all_active, f"Found {len(results)} active clients")
else:
    log_test("Status filter", False, f"Status {resp.status_code}")

# Step 10: Test tag filter
print("\n[8] Test Tag Filter")
resp = requests.get(f"{BASE_URL}/clients?tag=wedding", headers=headers)
if resp.status_code == 200:
    results = resp.json()
    found = any(c["client_id"] == client_id for c in results)
    log_test("Tag filter", found, f"Found {len(results)} clients with 'wedding' tag")
else:
    log_test("Tag filter", False, f"Status {resp.status_code}")

# Step 11: Get full client profile
print("\n[9] Get Full Client Profile")
resp = requests.get(f"{BASE_URL}/clients/{client_id}", headers=headers)
if resp.status_code == 200:
    profile = resp.json()
    log_test("Get client profile", True, f"client_id={profile.get('client_id')}")
    
    # Verify stats structure
    stats = profile.get("stats", {})
    has_all_stats = all(k in stats for k in ["contact_count", "event_count", "date_count", "lifetime_value"])
    log_test("Profile has all stats", has_all_stats, f"Stats: {stats}")
    
    # Verify counts
    log_test("Contact count correct", stats.get("contact_count") == 2, f"Expected 2, got {stats.get('contact_count')}")
    log_test("Date count correct", stats.get("date_count") == 2, f"Expected 2, got {stats.get('date_count')}")
else:
    log_test("Get client profile", False, f"Status {resp.status_code}: {resp.text}")

# Step 12: Test 404 for unknown client
print("\n[10] Test 404 for Unknown Client")
resp = requests.get(f"{BASE_URL}/clients/cli_nonexistent", headers=headers)
log_test("Unknown client returns 404", resp.status_code == 404, f"Status: {resp.status_code}")

# Step 13: Update client
print("\n[11] Update Client")
resp = requests.patch(f"{BASE_URL}/clients/{client_id}", json={
    "name": "Smith-Johnson Family",
    "status": "active",
    "tags": ["wedding", "premium", "vip"]
}, headers=headers)
if resp.status_code == 200:
    updated = resp.json()
    log_test("Update client", True, f"New name: {updated.get('name')}")
    log_test("Tags updated", len(updated.get("tags", [])) == 3, f"Tags: {updated.get('tags')}")
else:
    log_test("Update client", False, f"Status {resp.status_code}: {resp.text}")

# Step 14: Test invalid type in update
print("\n[12] Test Invalid Type in Update")
resp = requests.patch(f"{BASE_URL}/clients/{client_id}", json={
    "type": "invalid_type"
}, headers=headers)
log_test("Update with invalid type returns 400", resp.status_code == 400, f"Status: {resp.status_code}")

# Step 15: Test invalid status in update
print("\n[13] Test Invalid Status in Update")
resp = requests.patch(f"{BASE_URL}/clients/{client_id}", json={
    "status": "invalid_status"
}, headers=headers)
log_test("Update with invalid status returns 400", resp.status_code == 400, f"Status: {resp.status_code}")

# Step 16: Add a third contact
print("\n[14] Add Contact")
resp = requests.post(f"{BASE_URL}/clients/{client_id}/contacts", json={
    "name": "Bob Smith",
    "role": "father",
    "phone": "+1234567892",
    "email": "bob@smith.com",
    "is_primary": False
}, headers=headers)
if resp.status_code == 200:
    contact = resp.json()
    contact_id_3 = contact.get("contact_id")
    log_test("Add contact", True, f"contact_id={contact_id_3}")
else:
    log_test("Add contact", False, f"Status {resp.status_code}: {resp.text}")

# Step 17: Test is_primary exclusivity
print("\n[15] Test is_primary Exclusivity")
# Get current contacts
resp = requests.get(f"{BASE_URL}/clients/{client_id}", headers=headers)
if resp.status_code == 200:
    profile = resp.json()
    contacts = profile.get("contacts", [])
    primary_count = sum(1 for c in contacts if c.get("is_primary"))
    log_test("Only one primary contact initially", primary_count == 1, f"Primary count: {primary_count}")
    
    # Find a non-primary contact
    non_primary = next((c for c in contacts if not c.get("is_primary")), None)
    if non_primary:
        contact_id_2 = non_primary["contact_id"]
        
        # Set it as primary
        resp = requests.patch(f"{BASE_URL}/clients/{client_id}/contacts/{contact_id_2}", json={
            "is_primary": True
        }, headers=headers)
        
        if resp.status_code == 200:
            # Verify only one is primary now
            resp = requests.get(f"{BASE_URL}/clients/{client_id}", headers=headers)
            if resp.status_code == 200:
                profile = resp.json()
                contacts = profile.get("contacts", [])
                primary_count = sum(1 for c in contacts if c.get("is_primary"))
                log_test("is_primary is exclusive", primary_count == 1, f"Primary count after change: {primary_count}")
            else:
                log_test("is_primary is exclusive", False, "Failed to verify")
        else:
            log_test("is_primary is exclusive", False, f"Failed to update: {resp.status_code}")

# Step 18: Update contact
print("\n[16] Update Contact")
resp = requests.patch(f"{BASE_URL}/clients/{client_id}/contacts/{contact_id_2}", json={
    "role": "mother"
}, headers=headers)
log_test("Update contact", resp.status_code == 200, f"Status: {resp.status_code}")

# Step 19: Test 404 for unknown contact
print("\n[17] Test 404 for Unknown Contact")
resp = requests.patch(f"{BASE_URL}/clients/{client_id}/contacts/con_nonexistent", json={"role": "test"}, headers=headers)
log_test("Unknown contact returns 404", resp.status_code == 404, f"Status: {resp.status_code}")

# Step 20: Delete contact
print("\n[18] Delete Contact")
resp = requests.delete(f"{BASE_URL}/clients/{client_id}/contacts/{contact_id_3}", headers=headers)
if resp.status_code == 200:
    log_test("Delete contact", True, "Contact deleted")
    
    # Verify it's gone
    resp = requests.get(f"{BASE_URL}/clients/{client_id}", headers=headers)
    if resp.status_code == 200:
        profile = resp.json()
        contact_count = profile.get("stats", {}).get("contact_count", 0)
        log_test("Contact count after delete", contact_count == 2, f"Count: {contact_count}")
else:
    log_test("Delete contact", False, f"Status {resp.status_code}")

# Step 21: Add important date
print("\n[19] Add Important Date")
resp = requests.post(f"{BASE_URL}/clients/{client_id}/important-dates", json={
    "person_label": "Jane",
    "occasion": "Birthday",
    "date": "05-10",
    "recurring": True,
    "notes": "Send flowers"
}, headers=headers)
if resp.status_code == 200:
    date = resp.json()
    date_id_3 = date.get("date_id")
    log_test("Add important date", True, f"date_id={date_id_3}")
else:
    log_test("Add important date", False, f"Status {resp.status_code}: {resp.text}")

# Step 22: Update important date
print("\n[20] Update Important Date")
resp = requests.get(f"{BASE_URL}/clients/{client_id}", headers=headers)
if resp.status_code == 200:
    profile = resp.json()
    dates = profile.get("important_dates", [])
    if dates:
        date_id_1 = dates[0]["date_id"]
        resp = requests.patch(f"{BASE_URL}/clients/{client_id}/important-dates/{date_id_1}", json={
            "notes": "Updated notes"
        }, headers=headers)
        log_test("Update important date", resp.status_code == 200, f"Status: {resp.status_code}")

# Step 23: Test 404 for unknown date
print("\n[21] Test 404 for Unknown Important Date")
resp = requests.delete(f"{BASE_URL}/clients/{client_id}/important-dates/idt_nonexistent", headers=headers)
log_test("Unknown date returns 404", resp.status_code == 404, f"Status: {resp.status_code}")

# Step 24: Delete important date
print("\n[22] Delete Important Date")
resp = requests.delete(f"{BASE_URL}/clients/{client_id}/important-dates/{date_id_3}", headers=headers)
if resp.status_code == 200:
    log_test("Delete important date", True, "Date deleted")
    
    # Verify count
    resp = requests.get(f"{BASE_URL}/clients/{client_id}", headers=headers)
    if resp.status_code == 200:
        profile = resp.json()
        date_count = profile.get("stats", {}).get("date_count", 0)
        log_test("Date count after delete", date_count == 2, f"Count: {date_count}")
else:
    log_test("Delete important date", False, f"Status {resp.status_code}")

# Step 25: Create event with client_id and value
print("\n[23] Create Event with client_id and value")
event_data = {
    "name": "Test Wedding",
    "category": "wedding",
    "date": "2025-06-15",
    "client_id": client_id,
    "value": 120000
}
resp = requests.post(f"{BASE_URL}/events", json=event_data, headers=headers)
if resp.status_code == 200:
    event = resp.json()
    event_id = event.get("event_id")
    log_test("Create event with client_id", True, f"event_id={event_id}")
    log_test("Event has client_id", event.get("client_id") == client_id, f"client_id: {event.get('client_id')}")
    log_test("Event has value", event.get("value") == 120000, f"value: {event.get('value')}")
else:
    log_test("Create event with client_id", False, f"Status {resp.status_code}: {resp.text}")
    event_id = None

# Step 26: Verify event appears in client profile
print("\n[24] Verify Event in Client Profile")
resp = requests.get(f"{BASE_URL}/clients/{client_id}", headers=headers)
if resp.status_code == 200:
    profile = resp.json()
    events = profile.get("events", [])
    stats = profile.get("stats", {})
    
    log_test("Event appears in profile", len(events) == 1, f"Event count: {len(events)}")
    log_test("Lifetime value updated", stats.get("lifetime_value") == 120000, f"Lifetime value: {stats.get('lifetime_value')}")
else:
    log_test("Verify event in profile", False, f"Status {resp.status_code}")

# Step 27: Create second event without client_id
print("\n[25] Create Second Event (no client_id)")
event_data_2 = {
    "name": "Test Portrait",
    "category": "portrait",
    "date": "2025-07-01",
    "value": 50000
}
resp = requests.post(f"{BASE_URL}/events", json=event_data_2, headers=headers)
if resp.status_code == 200:
    event_2 = resp.json()
    event_id_2 = event_2.get("event_id")
    log_test("Create second event", True, f"event_id={event_id_2}")
else:
    log_test("Create second event", False, f"Status {resp.status_code}: {resp.text}")
    event_id_2 = None

# Step 28: Attach second event to client
print("\n[26] Attach Event to Client")
if event_id_2:
    resp = requests.post(f"{BASE_URL}/clients/{client_id}/events/{event_id_2}/attach", headers=headers)
    if resp.status_code == 200:
        log_test("Attach event", True, "Event attached")
        
        # Verify lifetime_value updated
        resp = requests.get(f"{BASE_URL}/clients/{client_id}", headers=headers)
        if resp.status_code == 200:
            profile = resp.json()
            stats = profile.get("stats", {})
            expected_value = 120000 + 50000
            log_test("Lifetime value after attach", stats.get("lifetime_value") == expected_value, 
                    f"Expected {expected_value}, got {stats.get('lifetime_value')}")
            log_test("Event count after attach", stats.get("event_count") == 2, 
                    f"Event count: {stats.get('event_count')}")
    else:
        log_test("Attach event", False, f"Status {resp.status_code}: {resp.text}")

# Step 29: Detach event
print("\n[27] Detach Event from Client")
if event_id_2:
    resp = requests.delete(f"{BASE_URL}/clients/{client_id}/events/{event_id_2}/attach", headers=headers)
    if resp.status_code == 200:
        log_test("Detach event", True, "Event detached")
        
        # Verify lifetime_value updated
        resp = requests.get(f"{BASE_URL}/clients/{client_id}", headers=headers)
        if resp.status_code == 200:
            profile = resp.json()
            stats = profile.get("stats", {})
            log_test("Lifetime value after detach", stats.get("lifetime_value") == 120000, 
                    f"Lifetime value: {stats.get('lifetime_value')}")
            log_test("Event count after detach", stats.get("event_count") == 1, 
                    f"Event count: {stats.get('event_count')}")
    else:
        log_test("Detach event", False, f"Status {resp.status_code}: {resp.text}")

# Step 30: Verify event still exists after detach
print("\n[28] Verify Event Still Exists After Detach")
if event_id_2:
    resp = requests.get(f"{BASE_URL}/events", headers=headers)
    if resp.status_code == 200:
        events = resp.json()
        event_exists = any(e["event_id"] == event_id_2 for e in events)
        log_test("Event exists after detach", event_exists, f"Found {len(events)} events")
    else:
        log_test("Event exists after detach", False, f"Status {resp.status_code}")

# Step 31: Multi-tenant isolation - Register second admin
print("\n[29] Multi-Tenant Isolation")
second_admin_email = f"test_admin_{int(time.time())}@example.com"
second_admin_password = "TestAdmin123"

resp = admin_register(second_admin_email, second_admin_password)
if resp.status_code == 200:
    log_test("Register second admin", True, f"Email: {second_admin_email}")
    
    # Login as second admin
    admin_token_2 = admin_login(second_admin_email, second_admin_password)
    if admin_token_2:
        log_test("Login as second admin", True, f"Token: {admin_token_2[:20]}...")
        headers_2 = {"Authorization": f"Bearer {admin_token_2}"}
        
        # Try to list clients - should not see first admin's client
        resp = requests.get(f"{BASE_URL}/clients", headers=headers_2)
        if resp.status_code == 200:
            clients = resp.json()
            has_first_admin_client = any(c["client_id"] == client_id for c in clients)
            log_test("Second admin cannot see first admin's clients", not has_first_admin_client, 
                    f"Found {len(clients)} clients")
        else:
            log_test("Second admin list clients", False, f"Status {resp.status_code}")
        
        # Try to get first admin's client - should return 404
        resp = requests.get(f"{BASE_URL}/clients/{client_id}", headers=headers_2)
        log_test("Second admin cannot get first admin's client", resp.status_code == 404, 
                f"Status: {resp.status_code}")
        
        # Try to update first admin's client - should return 404
        resp = requests.patch(f"{BASE_URL}/clients/{client_id}", json={"name": "Hacked"}, headers=headers_2)
        log_test("Second admin cannot update first admin's client", resp.status_code == 404, 
                f"Status: {resp.status_code}")
        
        # Try to delete first admin's client - should return 404
        resp = requests.delete(f"{BASE_URL}/clients/{client_id}", headers=headers_2)
        log_test("Second admin cannot delete first admin's client", resp.status_code == 404, 
                f"Status: {resp.status_code}")
    else:
        log_test("Login as second admin", False, "Failed to get token")
else:
    log_test("Register second admin", False, f"Status {resp.status_code}: {resp.text}")

# Step 32: Delete client and verify cascade
print("\n[30] Delete Client and Verify Cascade")
resp = requests.delete(f"{BASE_URL}/clients/{client_id}", headers=headers)
if resp.status_code == 200:
    result = resp.json()
    log_test("Delete client", True, f"Status: {result.get('status')}")
    
    # Verify client is gone
    resp = requests.get(f"{BASE_URL}/clients/{client_id}", headers=headers)
    log_test("Client deleted (404)", resp.status_code == 404, f"Status: {resp.status_code}")
    
    # Verify events still exist but are unlinked
    if event_id:
        resp = requests.get(f"{BASE_URL}/events", headers=headers)
        if resp.status_code == 200:
            events = resp.json()
            event = next((e for e in events if e["event_id"] == event_id), None)
            if event:
                log_test("Event unlinked after client delete", event.get("client_id") is None, 
                        f"client_id: {event.get('client_id')}")
            else:
                log_test("Event still exists", False, "Event not found")
        else:
            log_test("Verify events", False, f"Status {resp.status_code}")
else:
    log_test("Delete client", False, f"Status {resp.status_code}: {resp.text}")

# Cleanup: Delete test events
print("\n[31] Cleanup - Delete Test Events")
if event_id:
    resp = requests.delete(f"{BASE_URL}/events/{event_id}", headers=headers)
    log_test("Delete event 1", resp.status_code == 200, f"Status: {resp.status_code}")

if event_id_2:
    resp = requests.delete(f"{BASE_URL}/events/{event_id_2}", headers=headers)
    log_test("Delete event 2", resp.status_code == 200, f"Status: {resp.status_code}")

# Summary
print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)
print(f"Total Tests: {tests_passed + tests_failed}")
print(f"✅ Passed: {tests_passed}")
print(f"❌ Failed: {tests_failed}")
print(f"Success Rate: {tests_passed / (tests_passed + tests_failed) * 100:.1f}%")

if tests_failed > 0:
    print("\nFailed Tests:")
    for result in test_results:
        if not result["passed"]:
            print(f"  - {result['name']}: {result['details']}")

sys.exit(0 if tests_failed == 0 else 1)
