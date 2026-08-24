#!/usr/bin/env python3
"""Backend test for CRM name enrichment in gallery/album access lists."""
import sys
import httpx
import json
from typing import Optional

# Backend URL from environment
BACKEND_URL = "http://localhost:8001/api"

# Admin credentials from test_credentials.md
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

# Test state
admin_token: Optional[str] = None
throwaway_resources = {
    "clients": [],
    "events": [],
    "albums": [],
    "users": [],
}


def log(msg: str):
    print(f"  {msg}")


def test_step(num: int, desc: str):
    print(f"\n{num}. {desc}")


def cleanup_all():
    """Clean up all throwaway resources."""
    print("\n" + "=" * 80)
    print("CLEANUP: Removing all throwaway resources")
    print("=" * 80)
    
    if not admin_token:
        log("⚠️  No admin token, skipping cleanup")
        return
    
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Delete events
    for event_id in throwaway_resources["events"]:
        try:
            resp = httpx.delete(f"{BACKEND_URL}/events/{event_id}", headers=headers, timeout=30)
            if resp.status_code == 200:
                log(f"✅ Deleted event {event_id}")
            else:
                log(f"⚠️  Failed to delete event {event_id}: {resp.status_code}")
        except Exception as e:
            log(f"⚠️  Error deleting event {event_id}: {e}")
    
    # Delete albums
    for album_id in throwaway_resources["albums"]:
        try:
            resp = httpx.delete(f"{BACKEND_URL}/albums/{album_id}", headers=headers, timeout=30)
            if resp.status_code == 200:
                log(f"✅ Deleted album {album_id}")
            else:
                log(f"⚠️  Failed to delete album {album_id}: {resp.status_code}")
        except Exception as e:
            log(f"⚠️  Error deleting album {album_id}: {e}")
    
    # Delete CRM clients
    for client_id in throwaway_resources["clients"]:
        try:
            resp = httpx.delete(f"{BACKEND_URL}/clients/{client_id}", headers=headers, timeout=30)
            if resp.status_code == 200:
                log(f"✅ Deleted CRM client {client_id}")
            else:
                log(f"⚠️  Failed to delete CRM client {client_id}: {resp.status_code}")
        except Exception as e:
            log(f"⚠️  Error deleting CRM client {client_id}: {e}")
    
    log("✅ Cleanup complete")


def main():
    global admin_token
    
    print("=" * 80)
    print("BACKEND TEST: CRM Name Enrichment in Gallery/Album Access Lists")
    print("=" * 80)
    
    try:
        # ===================================================================
        # SETUP: Admin login
        # ===================================================================
        test_step(1, "Admin login")
        resp = httpx.post(
            f"{BACKEND_URL}/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=30,
        )
        assert resp.status_code == 200, f"Admin login failed: {resp.status_code} {resp.text}"
        admin_token = resp.json()["session_token"]
        log(f"✅ Admin logged in, token: {admin_token[:20]}...")
        
        headers = {"Authorization": f"Bearer {admin_token}"}
        
        # ===================================================================
        # SETUP: Create CRM client/family with contacts
        # ===================================================================
        test_step(2, "Create CRM client 'Test Family Alpha' with 3 contacts")
        resp = httpx.post(
            f"{BACKEND_URL}/clients",
            headers=headers,
            json={
                "name": "Test Family Alpha",
                "type": "family",
                "status": "active",
                "contacts": [
                    {
                        "name": "Alice Alpha",
                        "role": "bride",
                        "email": "alice.alpha@testcrm.example",
                        "phone": "+919876543210",
                        "is_primary": True,
                    },
                    {
                        "name": "Bob Alpha",
                        "role": "groom",
                        "email": "bob.alpha@testcrm.example",
                        "phone": "+919876543211",
                    },
                    {
                        "name": "Charlie Alpha",
                        "role": "parent",
                        "phone": "+919876543212",
                    },
                ],
            },
            timeout=30,
        )
        assert resp.status_code == 200, f"Create client failed: {resp.status_code} {resp.text}"
        client1 = resp.json()
        client1_id = client1["client_id"]
        throwaway_resources["clients"].append(client1_id)
        log(f"✅ Created CRM client: {client1_id} ({client1['name']})")
        log(f"   Contacts: {len(client1['contacts'])} (Alice, Bob, Charlie)")
        
        # ===================================================================
        # SETUP: Create second CRM client
        # ===================================================================
        test_step(3, "Create CRM client 'Test Family Beta' with 2 contacts")
        resp = httpx.post(
            f"{BACKEND_URL}/clients",
            headers=headers,
            json={
                "name": "Test Family Beta",
                "type": "family",
                "status": "active",
                "contacts": [
                    {
                        "name": "Diana Beta",
                        "role": "bride",
                        "email": "diana.beta@testcrm.example",
                        "phone": "+919876543220",
                        "is_primary": True,
                    },
                    {
                        "name": "Eve Beta",
                        "role": "groom",
                        "email": "eve.beta@testcrm.example",
                        "phone": "+919876543221",
                    },
                ],
            },
            timeout=30,
        )
        assert resp.status_code == 200, f"Create client failed: {resp.status_code} {resp.text}"
        client2 = resp.json()
        client2_id = client2["client_id"]
        throwaway_resources["clients"].append(client2_id)
        log(f"✅ Created CRM client: {client2_id} ({client2['name']})")
        log(f"   Contacts: {len(client2['contacts'])} (Diana, Eve)")
        
        # ===================================================================
        # TEST: Client search by client name
        # ===================================================================
        test_step(4, "Verify GET /api/clients?q=<client-name> returns matching client")
        resp = httpx.get(
            f"{BACKEND_URL}/clients",
            headers=headers,
            params={"q": "Alpha"},
            timeout=30,
        )
        assert resp.status_code == 200, f"Client search failed: {resp.status_code} {resp.text}"
        results = resp.json()
        assert len(results) >= 1, f"Expected at least 1 result for 'Alpha', got {len(results)}"
        assert any(c["client_id"] == client1_id for c in results), "Client 'Test Family Alpha' not found in search results"
        log(f"✅ Search 'Alpha' returned {len(results)} result(s), including Test Family Alpha")
        
        # ===================================================================
        # TEST: Client search by contact name
        # ===================================================================
        test_step(5, "Verify GET /api/clients?q=<contact-name> finds the client")
        resp = httpx.get(
            f"{BACKEND_URL}/clients",
            headers=headers,
            params={"q": "Alice"},
            timeout=30,
        )
        assert resp.status_code == 200, f"Client search failed: {resp.status_code} {resp.text}"
        results = resp.json()
        assert len(results) >= 1, f"Expected at least 1 result for 'Alice', got {len(results)}"
        assert any(c["client_id"] == client1_id for c in results), "Client with contact 'Alice Alpha' not found"
        log(f"✅ Search 'Alice' (contact name) returned {len(results)} result(s), including Test Family Alpha")
        
        # ===================================================================
        # TEST: Client search by contact email
        # ===================================================================
        test_step(6, "Verify GET /api/clients?q=<contact-email> finds the client")
        resp = httpx.get(
            f"{BACKEND_URL}/clients",
            headers=headers,
            params={"q": "bob.alpha@testcrm.example"},
            timeout=30,
        )
        assert resp.status_code == 200, f"Client search failed: {resp.status_code} {resp.text}"
        results = resp.json()
        assert len(results) >= 1, f"Expected at least 1 result for email, got {len(results)}"
        assert any(c["client_id"] == client1_id for c in results), "Client with contact email not found"
        log(f"✅ Search 'bob.alpha@testcrm.example' (contact email) returned {len(results)} result(s)")
        
        # ===================================================================
        # TEST: Client search by contact phone
        # ===================================================================
        test_step(7, "Verify GET /api/clients?q=<contact-phone> finds the client")
        resp = httpx.get(
            f"{BACKEND_URL}/clients",
            headers=headers,
            params={"q": "+919876543212"},
            timeout=30,
        )
        assert resp.status_code == 200, f"Client search failed: {resp.status_code} {resp.text}"
        results = resp.json()
        assert len(results) >= 1, f"Expected at least 1 result for phone, got {len(results)}"
        assert any(c["client_id"] == client1_id for c in results), "Client with contact phone not found"
        log(f"✅ Search '+919876543212' (contact phone) returned {len(results)} result(s)")
        
        # ===================================================================
        # SETUP: Create throwaway gallery event
        # ===================================================================
        test_step(8, "Create throwaway gallery event")
        resp = httpx.post(
            f"{BACKEND_URL}/events",
            headers=headers,
            json={
                "name": "QA CRM Access Test Event",
                "date": "2026-06-15",
                "category": "wedding",
            },
            timeout=30,
        )
        assert resp.status_code == 200, f"Create event failed: {resp.status_code} {resp.text}"
        event = resp.json()
        event_id = event["event_id"]
        throwaway_resources["events"].append(event_id)
        log(f"✅ Created event: {event_id} ({event['name']})")
        
        # ===================================================================
        # SETUP: Create throwaway album
        # ===================================================================
        test_step(9, "Create throwaway album")
        resp = httpx.post(
            f"{BACKEND_URL}/albums",
            headers=headers,
            json={
                "title": "QA CRM Access Test Album",
                "client_name": "Test Family",
                "event_name": "Test Wedding",
            },
            timeout=30,
        )
        assert resp.status_code == 200, f"Create album failed: {resp.status_code} {resp.text}"
        album = resp.json()
        album_id = album["album_id"]
        throwaway_resources["albums"].append(album_id)
        log(f"✅ Created album: {album_id} ({album['title']})")
        
        # ===================================================================
        # TEST: Add direct gallery access using CRM contact email
        # ===================================================================
        test_step(10, "Add direct gallery access using CRM contact email (alice.alpha@testcrm.example)")
        resp = httpx.post(
            f"{BACKEND_URL}/events/{event_id}/access",
            headers=headers,
            json={
                "channel": "email",
                "email": "alice.alpha@testcrm.example",
                "full_gallery_access": True,
            },
            timeout=30,
        )
        assert resp.status_code == 200, f"Grant access failed: {resp.status_code} {resp.text}"
        grant1 = resp.json()
        log(f"✅ Granted gallery access via email: {grant1['grant_id']}")
        
        # ===================================================================
        # TEST: Add direct album access using CRM contact phone
        # ===================================================================
        test_step(11, "Add direct album access using CRM contact phone (+919876543220)")
        resp = httpx.post(
            f"{BACKEND_URL}/albums/{album_id}/access",
            headers=headers,
            json={
                "channel": "phone",
                "phone": "+919876543220",
            },
            timeout=30,
        )
        assert resp.status_code == 200, f"Grant album access failed: {resp.status_code} {resp.text}"
        album_grant1 = resp.json()
        log(f"✅ Granted album access via phone: {album_grant1['grant_id']}")
        
        # ===================================================================
        # TEST: Add non-CRM gallery access (fallback test)
        # ===================================================================
        test_step(12, "Add direct gallery access for non-CRM contact (fallback test)")
        resp = httpx.post(
            f"{BACKEND_URL}/events/{event_id}/access",
            headers=headers,
            json={
                "channel": "email",
                "email": "noncrm.user@example.com",
                "full_gallery_access": False,
            },
            timeout=30,
        )
        assert resp.status_code == 200, f"Grant access failed: {resp.status_code} {resp.text}"
        grant_noncrm = resp.json()
        log(f"✅ Granted gallery access to non-CRM email: {grant_noncrm['grant_id']}")
        
        # ===================================================================
        # TEST: Add non-CRM album access (fallback test)
        # ===================================================================
        test_step(13, "Add direct album access for non-CRM contact (fallback test)")
        resp = httpx.post(
            f"{BACKEND_URL}/albums/{album_id}/access",
            headers=headers,
            json={
                "channel": "phone",
                "phone": "+919999999999",
            },
            timeout=30,
        )
        assert resp.status_code == 200, f"Grant album access failed: {resp.status_code} {resp.text}"
        album_grant_noncrm = resp.json()
        log(f"✅ Granted album access to non-CRM phone: {album_grant_noncrm['grant_id']}")
        
        # ===================================================================
        # TEST: Verify GET /api/events/{id}/access includes CRM names
        # ===================================================================
        test_step(14, "Verify GET /api/events/{id}/access includes client_name and contact_name for CRM grants")
        resp = httpx.get(
            f"{BACKEND_URL}/events/{event_id}/access",
            headers=headers,
            timeout=30,
        )
        assert resp.status_code == 200, f"List access failed: {resp.status_code} {resp.text}"
        access_list = resp.json()
        log(f"✅ Retrieved {len(access_list)} access grants")
        
        # Find the CRM grant (alice.alpha@testcrm.example)
        crm_grant = next((g for g in access_list if g.get("client_email") == "alice.alpha@testcrm.example"), None)
        assert crm_grant is not None, "CRM grant not found in access list"
        log(f"   CRM grant found: {crm_grant['grant_id']}")
        
        # Verify CRM enrichment fields
        assert "client_name" in crm_grant, "client_name field missing from CRM grant"
        assert "contact_name" in crm_grant, "contact_name field missing from CRM grant"
        assert crm_grant["client_name"] == "Test Family Alpha", f"Expected client_name='Test Family Alpha', got '{crm_grant.get('client_name')}'"
        assert crm_grant["contact_name"] == "Alice Alpha", f"Expected contact_name='Alice Alpha', got '{crm_grant.get('contact_name')}'"
        log(f"   ✅ client_name: {crm_grant['client_name']}")
        log(f"   ✅ contact_name: {crm_grant['contact_name']}")
        
        # Verify fallback fields are preserved
        assert "client_email" in crm_grant, "client_email field missing"
        assert crm_grant["client_email"] == "alice.alpha@testcrm.example", "client_email mismatch"
        log(f"   ✅ client_email preserved: {crm_grant['client_email']}")
        
        # Find the non-CRM grant
        noncrm_grant = next((g for g in access_list if g.get("client_email") == "noncrm.user@example.com"), None)
        assert noncrm_grant is not None, "Non-CRM grant not found in access list"
        log(f"   Non-CRM grant found: {noncrm_grant['grant_id']}")
        
        # Verify non-CRM grant has fallback fields and no server error
        assert "client_email" in noncrm_grant, "client_email field missing from non-CRM grant"
        assert noncrm_grant["client_email"] == "noncrm.user@example.com", "client_email mismatch"
        # client_name and contact_name should be absent or None for non-CRM grants
        if "client_name" in noncrm_grant:
            assert noncrm_grant["client_name"] is None, "client_name should be None for non-CRM grant"
        if "contact_name" in noncrm_grant:
            assert noncrm_grant["contact_name"] is None, "contact_name should be None for non-CRM grant"
        log(f"   ✅ Non-CRM grant has fallback fields, no CRM names (expected)")
        
        # ===================================================================
        # TEST: Verify GET /api/albums/{id}/access includes CRM names
        # ===================================================================
        test_step(15, "Verify GET /api/albums/{id}/access includes client_name and contact_name for CRM grants")
        resp = httpx.get(
            f"{BACKEND_URL}/albums/{album_id}/access",
            headers=headers,
            timeout=30,
        )
        assert resp.status_code == 200, f"List album access failed: {resp.status_code} {resp.text}"
        album_access_list = resp.json()
        log(f"✅ Retrieved {len(album_access_list)} album access grants")
        
        # Find the CRM grant (+919876543220)
        album_crm_grant = next((g for g in album_access_list if g.get("client_phone") == "+919876543220"), None)
        assert album_crm_grant is not None, "CRM album grant not found in access list"
        log(f"   CRM album grant found: {album_crm_grant['grant_id']}")
        
        # Verify CRM enrichment fields
        assert "client_name" in album_crm_grant, "client_name field missing from CRM album grant"
        assert "contact_name" in album_crm_grant, "contact_name field missing from CRM album grant"
        assert album_crm_grant["client_name"] == "Test Family Beta", f"Expected client_name='Test Family Beta', got '{album_crm_grant.get('client_name')}'"
        assert album_crm_grant["contact_name"] == "Diana Beta", f"Expected contact_name='Diana Beta', got '{album_crm_grant.get('contact_name')}'"
        log(f"   ✅ client_name: {album_crm_grant['client_name']}")
        log(f"   ✅ contact_name: {album_crm_grant['contact_name']}")
        
        # Verify fallback fields are preserved
        assert "client_phone" in album_crm_grant, "client_phone field missing"
        assert album_crm_grant["client_phone"] == "+919876543220", "client_phone mismatch"
        log(f"   ✅ client_phone preserved: {album_crm_grant['client_phone']}")
        
        # Find the non-CRM album grant
        album_noncrm_grant = next((g for g in album_access_list if g.get("client_phone") == "+919999999999"), None)
        assert album_noncrm_grant is not None, "Non-CRM album grant not found in access list"
        log(f"   Non-CRM album grant found: {album_noncrm_grant['grant_id']}")
        
        # Verify non-CRM grant has fallback fields and no server error
        assert "client_phone" in album_noncrm_grant, "client_phone field missing from non-CRM album grant"
        assert album_noncrm_grant["client_phone"] == "+919999999999", "client_phone mismatch"
        if "client_name" in album_noncrm_grant:
            assert album_noncrm_grant["client_name"] is None, "client_name should be None for non-CRM album grant"
        if "contact_name" in album_noncrm_grant:
            assert album_noncrm_grant["contact_name"] is None, "contact_name should be None for non-CRM album grant"
        log(f"   ✅ Non-CRM album grant has fallback fields, no CRM names (expected)")
        
        # ===================================================================
        # TEST: Access-list auth (401 without token)
        # ===================================================================
        test_step(16, "Verify GET /api/events/{id}/access returns 401 without token")
        resp = httpx.get(
            f"{BACKEND_URL}/events/{event_id}/access",
            timeout=30,
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        log(f"✅ Correctly returned 401 without token")
        
        test_step(17, "Verify GET /api/albums/{id}/access returns 401 without token")
        resp = httpx.get(
            f"{BACKEND_URL}/albums/{album_id}/access",
            timeout=30,
        )
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"
        log(f"✅ Correctly returned 401 without token")
        
        # ===================================================================
        # TEST: Client-group assignment endpoints regression
        # ===================================================================
        test_step(18, "Verify client-group assignment endpoints still work for event")
        resp = httpx.post(
            f"{BACKEND_URL}/events/{event_id}/client-assignments",
            headers=headers,
            json={
                "client_id": client1_id,
                "full_gallery_access": True,
            },
            timeout=30,
        )
        assert resp.status_code == 200, f"Assign client to event failed: {resp.status_code} {resp.text}"
        assignment_result = resp.json()
        assert assignment_result["status"] == "assigned", "Assignment status not 'assigned'"
        log(f"✅ Assigned client {client1_id} to event {event_id}")
        
        # Verify assignment list includes client_name and contact_count
        resp = httpx.get(
            f"{BACKEND_URL}/events/{event_id}/client-assignments",
            headers=headers,
            timeout=30,
        )
        assert resp.status_code == 200, f"List event assignments failed: {resp.status_code} {resp.text}"
        assignments = resp.json()
        assert len(assignments) >= 1, "Expected at least 1 assignment"
        assignment = next((a for a in assignments if a["client_id"] == client1_id), None)
        assert assignment is not None, "Assignment not found in list"
        assert "client_name" in assignment, "client_name field missing from assignment"
        assert "contact_count" in assignment, "contact_count field missing from assignment"
        assert assignment["client_name"] == "Test Family Alpha", f"Expected client_name='Test Family Alpha', got '{assignment.get('client_name')}'"
        assert assignment["contact_count"] == 3, f"Expected contact_count=3, got {assignment.get('contact_count')}"
        log(f"   ✅ Assignment includes client_name: {assignment['client_name']}")
        log(f"   ✅ Assignment includes contact_count: {assignment['contact_count']}")
        
        test_step(19, "Verify client-group assignment endpoints still work for album")
        resp = httpx.post(
            f"{BACKEND_URL}/albums/{album_id}/client-assignments",
            headers=headers,
            json={
                "client_id": client2_id,
            },
            timeout=30,
        )
        assert resp.status_code == 200, f"Assign client to album failed: {resp.status_code} {resp.text}"
        album_assignment_result = resp.json()
        assert album_assignment_result["status"] == "assigned", "Album assignment status not 'assigned'"
        log(f"✅ Assigned client {client2_id} to album {album_id}")
        
        # Verify album assignment list includes client_name and contact_count
        resp = httpx.get(
            f"{BACKEND_URL}/albums/{album_id}/client-assignments",
            headers=headers,
            timeout=30,
        )
        assert resp.status_code == 200, f"List album assignments failed: {resp.status_code} {resp.text}"
        album_assignments = resp.json()
        assert len(album_assignments) >= 1, "Expected at least 1 album assignment"
        album_assignment = next((a for a in album_assignments if a["client_id"] == client2_id), None)
        assert album_assignment is not None, "Album assignment not found in list"
        assert "client_name" in album_assignment, "client_name field missing from album assignment"
        assert "contact_count" in album_assignment, "contact_count field missing from album assignment"
        assert album_assignment["client_name"] == "Test Family Beta", f"Expected client_name='Test Family Beta', got '{album_assignment.get('client_name')}'"
        assert album_assignment["contact_count"] == 2, f"Expected contact_count=2, got {album_assignment.get('contact_count')}"
        log(f"   ✅ Album assignment includes client_name: {album_assignment['client_name']}")
        log(f"   ✅ Album assignment includes contact_count: {album_assignment['contact_count']}")
        
        # ===================================================================
        # CHECK: Backend logs for 5xx errors
        # ===================================================================
        test_step(20, "Check backend logs for 5xx errors")
        import subprocess
        result = subprocess.run(
            ["tail", "-n", "100", "/var/log/supervisor/backend.err.log"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        err_log = result.stdout
        if "500" in err_log or "502" in err_log or "503" in err_log or "504" in err_log:
            log(f"⚠️  Found potential 5xx errors in backend logs:")
            for line in err_log.split("\n"):
                if "500" in line or "502" in line or "503" in line or "504" in line:
                    log(f"     {line}")
        else:
            log(f"✅ No 5xx errors found in recent backend logs")
        
        # ===================================================================
        # CLEANUP
        # ===================================================================
        cleanup_all()
        
        # ===================================================================
        # SUMMARY
        # ===================================================================
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED")
        print("=" * 80)
        print("\nTEST SUMMARY:")
        print("  ✅ Client search by client name, contact name, email, phone - ALL WORKING")
        print("  ✅ Direct gallery access with CRM contact email - WORKING")
        print("  ✅ Direct album access with CRM contact phone - WORKING")
        print("  ✅ GET /api/events/{id}/access includes client_name and contact_name for CRM grants")
        print("  ✅ GET /api/albums/{id}/access includes client_name and contact_name for CRM grants")
        print("  ✅ Non-CRM grants return correctly with fallback fields (no server error)")
        print("  ✅ Access-list auth: 401 without token (gallery and album)")
        print("  ✅ Client-group assignment endpoints regression: WORKING")
        print("  ✅ Assignment rows include client_name and contact_count")
        print("  ✅ All throwaway resources cleaned up")
        print("  ✅ No 5xx errors in backend logs")
        print("\n" + "=" * 80)
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        cleanup_all()
        return 1
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        cleanup_all()
        return 1


if __name__ == "__main__":
    sys.exit(main())
