#!/usr/bin/env python3
"""
Multi-tenant isolation audit test for PIK Connect / Lumiere Gallery
Tests cross-admin tenant isolation following the review request playbook.
"""

import requests
import json
import sys
from io import BytesIO
from PIL import Image

# Backend URL
BASE_URL = "https://c0faba68-e5fa-4458-a8e2-55fae2614e16.preview.emergentagent.com/api"

# Test credentials
ADMIN_A_EMAIL = "admin@lumiere.studio"
ADMIN_A_PASSWORD = "Admin@12345"

# Throwaway Admin B credentials
ADMIN_B_EMAIL = "throwaway_admin_b@test.example"
ADMIN_B_PASSWORD = "ThrowawayB@12345"
ADMIN_B_NAME = "Throwaway Admin B"

def log(msg):
    print(f"[TEST] {msg}")

def create_test_image():
    """Create a small test JPEG image"""
    img = Image.new('RGB', (100, 100), color='red')
    buf = BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return buf

def create_test_pdf():
    """Create a minimal test PDF (7 pages for album)"""
    # Minimal PDF with 7 pages
    pdf_content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Count 7/Kids[3 0 R 4 0 R 5 0 R 6 0 R 7 0 R 8 0 R 9 0 R]>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj
4 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj
5 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj
6 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj
7 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj
8 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj
9 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj
xref
0 10
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000145 00000 n 
0000000218 00000 n 
0000000291 00000 n 
0000000364 00000 n 
0000000437 00000 n 
0000000510 00000 n 
0000000583 00000 n 
trailer<</Size 10/Root 1 0 R>>
startxref
656
%%EOF"""
    return BytesIO(pdf_content)

def main():
    log("=== MULTI-TENANT ISOLATION AUDIT TEST ===")
    
    # Track resources for cleanup
    admin_b_token = None
    admin_b_user_id = None
    admin_a_event_id = None
    admin_a_album_id = None
    admin_a_client_id = None
    admin_a_contact_id = None
    admin_a_visitor_id = None
    admin_a_grant_id = None
    
    try:
        # ===== STEP 1: Login as Admin A (existing admin) =====
        log("\n--- STEP 1: Login as Admin A (existing admin) ---")
        resp = requests.post(f"{BASE_URL}/auth/admin/login", json={
            "email": ADMIN_A_EMAIL,
            "password": ADMIN_A_PASSWORD
        })
        assert resp.status_code == 200, f"Admin A login failed: {resp.status_code} {resp.text}"
        admin_a_token = resp.json()["session_token"]
        admin_a_user_id = resp.json()["user"]["user_id"]
        log(f"✅ Admin A logged in: {admin_a_user_id}")
        
        # ===== STEP 2: Register throwaway Admin B =====
        log("\n--- STEP 2: Register throwaway Admin B ---")
        resp = requests.post(f"{BASE_URL}/auth/admin/register", json={
            "email": ADMIN_B_EMAIL,
            "password": ADMIN_B_PASSWORD,
            "name": ADMIN_B_NAME
        })
        assert resp.status_code == 200, f"Admin B registration failed: {resp.status_code} {resp.text}"
        admin_b_token = resp.json()["session_token"]
        admin_b_user_id = resp.json()["user"]["user_id"]
        log(f"✅ Admin B registered: {admin_b_user_id}")
        
        # ===== STEP 3: As Admin A, create resources =====
        log("\n--- STEP 3: As Admin A, create event, album, CRM client ---")
        
        # 3a. Create event
        resp = requests.post(f"{BASE_URL}/events", 
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={
                "name": "Admin A Test Event",
                "category": "wedding",
                "date": "2026-12-01"
            })
        assert resp.status_code == 200, f"Event creation failed: {resp.status_code} {resp.text}"
        admin_a_event_id = resp.json()["event_id"]
        log(f"✅ Admin A created event: {admin_a_event_id}")
        
        # 3b. Upload photo to event
        img_buf = create_test_image()
        resp = requests.post(f"{BASE_URL}/events/{admin_a_event_id}/photos",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            files={"file": ("test.jpg", img_buf, "image/jpeg")})
        assert resp.status_code == 200, f"Photo upload failed: {resp.status_code} {resp.text}"
        admin_a_photo_id = resp.json()["photo_id"]
        log(f"✅ Admin A uploaded photo: {admin_a_photo_id}")
        
        # 3c. Create album
        resp = requests.post(f"{BASE_URL}/albums",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={"title": "Admin A Test Album"})
        assert resp.status_code == 200, f"Album creation failed: {resp.status_code} {resp.text}"
        admin_a_album_id = resp.json()["album_id"]
        log(f"✅ Admin A created album: {admin_a_album_id}")
        
        # 3d. Upload PDF to album
        pdf_buf = create_test_pdf()
        resp = requests.post(f"{BASE_URL}/albums/{admin_a_album_id}/pdf",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            files={"file": ("test.pdf", pdf_buf, "application/pdf")})
        assert resp.status_code == 200, f"Album PDF upload failed: {resp.status_code} {resp.text}"
        log(f"✅ Admin A uploaded PDF to album")
        
        # 3e. Publish album
        resp = requests.post(f"{BASE_URL}/albums/{admin_a_album_id}/publish",
            headers={"Authorization": f"Bearer {admin_a_token}"})
        assert resp.status_code == 200, f"Album publish failed: {resp.status_code} {resp.text}"
        log(f"✅ Admin A published album")
        
        # 3f. Create CRM client with contacts
        resp = requests.post(f"{BASE_URL}/clients",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={
                "name": "Admin A Test Family",
                "contacts": [
                    {
                        "name": "Contact Alpha",
                        "role": "bride",
                        "email": "contact.alpha@adminatest.example",
                        "phone": "+919876543100"
                    }
                ]
            })
        assert resp.status_code == 200, f"CRM client creation failed: {resp.status_code} {resp.text}"
        admin_a_client_id = resp.json()["client_id"]
        admin_a_contact_id = resp.json()["contacts"][0]["contact_id"]
        log(f"✅ Admin A created CRM client: {admin_a_client_id} with contact: {admin_a_contact_id}")
        
        # 3g. Add important date to CRM client
        resp = requests.post(f"{BASE_URL}/clients/{admin_a_client_id}/important-dates",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={
                "person_label": "Contact Alpha",
                "occasion": "Birthday",
                "date": "2026-09-15"
            })
        assert resp.status_code == 200, f"Important date creation failed: {resp.status_code} {resp.text}"
        admin_a_date_id = resp.json()["date_id"]
        log(f"✅ Admin A added important date: {admin_a_date_id}")
        
        # 3h. Assign CRM client to event (client-group assignment)
        resp = requests.post(f"{BASE_URL}/events/{admin_a_event_id}/client-assignments",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={
                "client_id": admin_a_client_id,
                "full_gallery_access": True
            })
        assert resp.status_code == 200, f"Event client assignment failed: {resp.status_code} {resp.text}"
        log(f"✅ Admin A assigned CRM client to event")
        
        # 3i. Assign CRM client to album
        resp = requests.post(f"{BASE_URL}/albums/{admin_a_album_id}/client-assignments",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={"client_id": admin_a_client_id})
        assert resp.status_code == 200, f"Album client assignment failed: {resp.status_code} {resp.text}"
        log(f"✅ Admin A assigned CRM client to album")
        
        # 3j. Create direct grant (via public access endpoint to create visitor)
        resp = requests.post(f"{BASE_URL}/public/events/{admin_a_event_id}/access",
            json={
                "name": "Direct Visitor",
                "phone": "+919876543199"
            })
        assert resp.status_code == 200, f"Direct visitor creation failed: {resp.status_code} {resp.text}"
        visitor_token = resp.json()["session_token"]
        log(f"✅ Admin A created direct visitor via public access")
        
        # Get visitor ID from admin's visitor list
        resp = requests.get(f"{BASE_URL}/events/{admin_a_event_id}/visitors",
            headers={"Authorization": f"Bearer {admin_a_token}"})
        assert resp.status_code == 200, f"Get visitors failed: {resp.status_code} {resp.text}"
        visitors = resp.json()  # Returns list directly
        admin_a_visitor_id = visitors[0]["visitor_id"] if visitors else None
        log(f"✅ Admin A visitor ID: {admin_a_visitor_id}")
        
        # 3k. Create direct album grant
        resp = requests.post(f"{BASE_URL}/albums/{admin_a_album_id}/access",
            headers={"Authorization": f"Bearer {admin_a_token}"},
            json={
                "channel": "email",
                "email": "directgrant@adminatest.example"
            })
        assert resp.status_code == 200, f"Direct album grant failed: {resp.status_code} {resp.text}"
        admin_a_grant_id = resp.json()["grant_id"]
        log(f"✅ Admin A created direct album grant: {admin_a_grant_id}")
        
        log("\n✅ Admin A setup complete with all resources created")
        
        # ===== STEP 4: As Admin B, attempt to access Admin A's resources =====
        log("\n--- STEP 4: As Admin B, verify CANNOT access Admin A's resources ---")
        
        test_results = []
        
        # 4a. Try to list Admin A's event
        log("\n4a. Admin B tries to list events (should only see own, not Admin A's)")
        resp = requests.get(f"{BASE_URL}/events",
            headers={"Authorization": f"Bearer {admin_b_token}"})
        assert resp.status_code == 200, f"List events failed: {resp.status_code} {resp.text}"
        events = resp.json()  # Returns list directly
        admin_a_event_visible = any(e["event_id"] == admin_a_event_id for e in events)
        if admin_a_event_visible:
            test_results.append("❌ FAIL: Admin B can see Admin A's event in list")
            log("❌ FAIL: Admin B can see Admin A's event in list")
        else:
            test_results.append("✅ PASS: Admin B cannot see Admin A's event in list")
            log("✅ PASS: Admin B cannot see Admin A's event in list")
        
        # 4b. Try to GET Admin A's event directly
        log("\n4b. Admin B tries to GET Admin A's event directly")
        resp = requests.get(f"{BASE_URL}/events/{admin_a_event_id}",
            headers={"Authorization": f"Bearer {admin_b_token}"})
        if resp.status_code in [403, 404]:
            test_results.append(f"✅ PASS: Admin B cannot GET Admin A's event ({resp.status_code})")
            log(f"✅ PASS: Admin B cannot GET Admin A's event ({resp.status_code})")
        else:
            test_results.append(f"❌ FAIL: Admin B can GET Admin A's event ({resp.status_code})")
            log(f"❌ FAIL: Admin B can GET Admin A's event ({resp.status_code})")
        
        # 4c. Try to UPDATE Admin A's event
        log("\n4c. Admin B tries to UPDATE Admin A's event")
        resp = requests.patch(f"{BASE_URL}/events/{admin_a_event_id}",
            headers={"Authorization": f"Bearer {admin_b_token}"},
            json={"name": "Hacked by Admin B"})
        if resp.status_code in [403, 404]:
            test_results.append(f"✅ PASS: Admin B cannot UPDATE Admin A's event ({resp.status_code})")
            log(f"✅ PASS: Admin B cannot UPDATE Admin A's event ({resp.status_code})")
        else:
            test_results.append(f"❌ FAIL: Admin B can UPDATE Admin A's event ({resp.status_code})")
            log(f"❌ FAIL: Admin B can UPDATE Admin A's event ({resp.status_code})")
        
        # 4d. Try to DELETE Admin A's event
        log("\n4d. Admin B tries to DELETE Admin A's event")
        resp = requests.delete(f"{BASE_URL}/events/{admin_a_event_id}",
            headers={"Authorization": f"Bearer {admin_b_token}"})
        if resp.status_code in [403, 404]:
            test_results.append(f"✅ PASS: Admin B cannot DELETE Admin A's event ({resp.status_code})")
            log(f"✅ PASS: Admin B cannot DELETE Admin A's event ({resp.status_code})")
        else:
            test_results.append(f"❌ FAIL: Admin B can DELETE Admin A's event ({resp.status_code})")
            log(f"❌ FAIL: Admin B can DELETE Admin A's event ({resp.status_code})")
        
        # 4e. Try to list Admin A's event photos
        log("\n4e. Admin B tries to list Admin A's event photos")
        resp = requests.get(f"{BASE_URL}/events/{admin_a_event_id}/photos",
            headers={"Authorization": f"Bearer {admin_b_token}"})
        if resp.status_code in [403, 404]:
            test_results.append(f"✅ PASS: Admin B cannot list Admin A's photos ({resp.status_code})")
            log(f"✅ PASS: Admin B cannot list Admin A's photos ({resp.status_code})")
        else:
            test_results.append(f"❌ FAIL: Admin B can list Admin A's photos ({resp.status_code})")
            log(f"❌ FAIL: Admin B can list Admin A's photos ({resp.status_code})")
        
        # 4f. Try to upload photo to Admin A's event
        log("\n4f. Admin B tries to upload photo to Admin A's event")
        img_buf = create_test_image()
        resp = requests.post(f"{BASE_URL}/events/{admin_a_event_id}/photos",
            headers={"Authorization": f"Bearer {admin_b_token}"},
            files={"file": ("hack.jpg", img_buf, "image/jpeg")})
        if resp.status_code in [403, 404]:
            test_results.append(f"✅ PASS: Admin B cannot upload to Admin A's event ({resp.status_code})")
            log(f"✅ PASS: Admin B cannot upload to Admin A's event ({resp.status_code})")
        else:
            test_results.append(f"❌ FAIL: Admin B can upload to Admin A's event ({resp.status_code})")
            log(f"❌ FAIL: Admin B can upload to Admin A's event ({resp.status_code})")
        
        # 4g. Try to archive Admin A's event
        log("\n4g. Admin B tries to archive Admin A's event")
        resp = requests.post(f"{BASE_URL}/events/{admin_a_event_id}/archive",
            headers={"Authorization": f"Bearer {admin_b_token}"})
        if resp.status_code in [403, 404]:
            test_results.append(f"✅ PASS: Admin B cannot archive Admin A's event ({resp.status_code})")
            log(f"✅ PASS: Admin B cannot archive Admin A's event ({resp.status_code})")
        else:
            test_results.append(f"❌ FAIL: Admin B can archive Admin A's event ({resp.status_code})")
            log(f"❌ FAIL: Admin B can archive Admin A's event ({resp.status_code})")
        
        # 4h. Try to access Admin A's event visitors
        log("\n4h. Admin B tries to access Admin A's event visitors")
        resp = requests.get(f"{BASE_URL}/events/{admin_a_event_id}/visitors",
            headers={"Authorization": f"Bearer {admin_b_token}"})
        if resp.status_code in [403, 404]:
            test_results.append(f"✅ PASS: Admin B cannot access Admin A's visitors ({resp.status_code})")
            log(f"✅ PASS: Admin B cannot access Admin A's visitors ({resp.status_code})")
        else:
            test_results.append(f"❌ FAIL: Admin B can access Admin A's visitors ({resp.status_code})")
            log(f"❌ FAIL: Admin B can access Admin A's visitors ({resp.status_code})")
        
        # 4i. Try to access Admin A's event access grants
        log("\n4i. Admin B tries to access Admin A's event access grants")
        resp = requests.get(f"{BASE_URL}/events/{admin_a_event_id}/access",
            headers={"Authorization": f"Bearer {admin_b_token}"})
        if resp.status_code in [403, 404]:
            test_results.append(f"✅ PASS: Admin B cannot access Admin A's grants ({resp.status_code})")
            log(f"✅ PASS: Admin B cannot access Admin A's grants ({resp.status_code})")
        else:
            test_results.append(f"❌ FAIL: Admin B can access Admin A's grants ({resp.status_code})")
            log(f"❌ FAIL: Admin B can access Admin A's grants ({resp.status_code})")
        
        # 4j. Try to access Admin A's event client-assignments
        log("\n4j. Admin B tries to access Admin A's event client-assignments")
        resp = requests.get(f"{BASE_URL}/events/{admin_a_event_id}/client-assignments",
            headers={"Authorization": f"Bearer {admin_b_token}"})
        if resp.status_code in [403, 404]:
            test_results.append(f"✅ PASS: Admin B cannot access Admin A's client-assignments ({resp.status_code})")
            log(f"✅ PASS: Admin B cannot access Admin A's client-assignments ({resp.status_code})")
        else:
            test_results.append(f"❌ FAIL: Admin B can access Admin A's client-assignments ({resp.status_code})")
            log(f"❌ FAIL: Admin B can access Admin A's client-assignments ({resp.status_code})")
        
        # 4k. Try to list Admin A's albums
        log("\n4k. Admin B tries to list albums (should only see own, not Admin A's)")
        resp = requests.get(f"{BASE_URL}/albums",
            headers={"Authorization": f"Bearer {admin_b_token}"})
        assert resp.status_code == 200, f"List albums failed: {resp.status_code} {resp.text}"
        albums = resp.json()  # Returns list directly
        admin_a_album_visible = any(a["album_id"] == admin_a_album_id for a in albums)
        if admin_a_album_visible:
            test_results.append("❌ FAIL: Admin B can see Admin A's album in list")
            log("❌ FAIL: Admin B can see Admin A's album in list")
        else:
            test_results.append("✅ PASS: Admin B cannot see Admin A's album in list")
            log("✅ PASS: Admin B cannot see Admin A's album in list")
        
        # 4l. Try to GET Admin A's album directly
        log("\n4l. Admin B tries to GET Admin A's album directly")
        resp = requests.get(f"{BASE_URL}/albums/{admin_a_album_id}",
            headers={"Authorization": f"Bearer {admin_b_token}"})
        if resp.status_code in [403, 404]:
            test_results.append(f"✅ PASS: Admin B cannot GET Admin A's album ({resp.status_code})")
            log(f"✅ PASS: Admin B cannot GET Admin A's album ({resp.status_code})")
        else:
            test_results.append(f"❌ FAIL: Admin B can GET Admin A's album ({resp.status_code})")
            log(f"❌ FAIL: Admin B can GET Admin A's album ({resp.status_code})")
        
        # 4m. Try to UPDATE Admin A's album
        log("\n4m. Admin B tries to UPDATE Admin A's album")
        resp = requests.patch(f"{BASE_URL}/albums/{admin_a_album_id}",
            headers={"Authorization": f"Bearer {admin_b_token}"},
            json={"title": "Hacked by Admin B"})
        if resp.status_code in [403, 404]:
            test_results.append(f"✅ PASS: Admin B cannot UPDATE Admin A's album ({resp.status_code})")
            log(f"✅ PASS: Admin B cannot UPDATE Admin A's album ({resp.status_code})")
        else:
            test_results.append(f"❌ FAIL: Admin B can UPDATE Admin A's album ({resp.status_code})")
            log(f"❌ FAIL: Admin B can UPDATE Admin A's album ({resp.status_code})")
        
        # 4n. Try to DELETE Admin A's album
        log("\n4n. Admin B tries to DELETE Admin A's album")
        resp = requests.delete(f"{BASE_URL}/albums/{admin_a_album_id}",
            headers={"Authorization": f"Bearer {admin_b_token}"})
        if resp.status_code in [403, 404]:
            test_results.append(f"✅ PASS: Admin B cannot DELETE Admin A's album ({resp.status_code})")
            log(f"✅ PASS: Admin B cannot DELETE Admin A's album ({resp.status_code})")
        else:
            test_results.append(f"❌ FAIL: Admin B can DELETE Admin A's album ({resp.status_code})")
            log(f"❌ FAIL: Admin B can DELETE Admin A's album ({resp.status_code})")
        
        # 4o. Try to access Admin A's album access grants
        log("\n4o. Admin B tries to access Admin A's album access grants")
        resp = requests.get(f"{BASE_URL}/albums/{admin_a_album_id}/access",
            headers={"Authorization": f"Bearer {admin_b_token}"})
        if resp.status_code in [403, 404]:
            test_results.append(f"✅ PASS: Admin B cannot access Admin A's album grants ({resp.status_code})")
            log(f"✅ PASS: Admin B cannot access Admin A's album grants ({resp.status_code})")
        else:
            test_results.append(f"❌ FAIL: Admin B can access Admin A's album grants ({resp.status_code})")
            log(f"❌ FAIL: Admin B can access Admin A's album grants ({resp.status_code})")
        
        # 4p. Try to access Admin A's album client-assignments
        log("\n4p. Admin B tries to access Admin A's album client-assignments")
        resp = requests.get(f"{BASE_URL}/albums/{admin_a_album_id}/client-assignments",
            headers={"Authorization": f"Bearer {admin_b_token}"})
        if resp.status_code in [403, 404]:
            test_results.append(f"✅ PASS: Admin B cannot access Admin A's album client-assignments ({resp.status_code})")
            log(f"✅ PASS: Admin B cannot access Admin A's album client-assignments ({resp.status_code})")
        else:
            test_results.append(f"❌ FAIL: Admin B can access Admin A's album client-assignments ({resp.status_code})")
            log(f"❌ FAIL: Admin B can access Admin A's album client-assignments ({resp.status_code})")
        
        # 4q. Try to list Admin A's CRM clients
        log("\n4q. Admin B tries to list CRM clients (should only see own, not Admin A's)")
        resp = requests.get(f"{BASE_URL}/clients",
            headers={"Authorization": f"Bearer {admin_b_token}"})
        assert resp.status_code == 200, f"List clients failed: {resp.status_code} {resp.text}"
        clients = resp.json()  # Returns list directly
        admin_a_client_visible = any(c["client_id"] == admin_a_client_id for c in clients)
        if admin_a_client_visible:
            test_results.append("❌ FAIL: Admin B can see Admin A's CRM client in list")
            log("❌ FAIL: Admin B can see Admin A's CRM client in list")
        else:
            test_results.append("✅ PASS: Admin B cannot see Admin A's CRM client in list")
            log("✅ PASS: Admin B cannot see Admin A's CRM client in list")
        
        # 4r. Try to GET Admin A's CRM client directly
        log("\n4r. Admin B tries to GET Admin A's CRM client directly")
        resp = requests.get(f"{BASE_URL}/clients/{admin_a_client_id}",
            headers={"Authorization": f"Bearer {admin_b_token}"})
        if resp.status_code in [403, 404]:
            test_results.append(f"✅ PASS: Admin B cannot GET Admin A's CRM client ({resp.status_code})")
            log(f"✅ PASS: Admin B cannot GET Admin A's CRM client ({resp.status_code})")
        else:
            test_results.append(f"❌ FAIL: Admin B can GET Admin A's CRM client ({resp.status_code})")
            log(f"❌ FAIL: Admin B can GET Admin A's CRM client ({resp.status_code})")
        
        # 4s. Try to UPDATE Admin A's CRM client
        log("\n4s. Admin B tries to UPDATE Admin A's CRM client")
        resp = requests.patch(f"{BASE_URL}/clients/{admin_a_client_id}",
            headers={"Authorization": f"Bearer {admin_b_token}"},
            json={"client_name": "Hacked by Admin B"})
        if resp.status_code in [403, 404]:
            test_results.append(f"✅ PASS: Admin B cannot UPDATE Admin A's CRM client ({resp.status_code})")
            log(f"✅ PASS: Admin B cannot UPDATE Admin A's CRM client ({resp.status_code})")
        else:
            test_results.append(f"❌ FAIL: Admin B can UPDATE Admin A's CRM client ({resp.status_code})")
            log(f"❌ FAIL: Admin B can UPDATE Admin A's CRM client ({resp.status_code})")
        
        # 4t. Try to DELETE Admin A's CRM client
        log("\n4t. Admin B tries to DELETE Admin A's CRM client")
        resp = requests.delete(f"{BASE_URL}/clients/{admin_a_client_id}",
            headers={"Authorization": f"Bearer {admin_b_token}"})
        if resp.status_code in [403, 404]:
            test_results.append(f"✅ PASS: Admin B cannot DELETE Admin A's CRM client ({resp.status_code})")
            log(f"✅ PASS: Admin B cannot DELETE Admin A's CRM client ({resp.status_code})")
        else:
            test_results.append(f"❌ FAIL: Admin B can DELETE Admin A's CRM client ({resp.status_code})")
            log(f"❌ FAIL: Admin B can DELETE Admin A's CRM client ({resp.status_code})")
        
        # 4u. Try to access Admin A's CRM client contacts
        log("\n4u. Admin B tries to access Admin A's CRM client contacts")
        resp = requests.get(f"{BASE_URL}/clients/{admin_a_client_id}/contacts/{admin_a_contact_id}",
            headers={"Authorization": f"Bearer {admin_b_token}"})
        if resp.status_code in [403, 404, 405]:  # 405 = endpoint doesn't exist
            test_results.append(f"✅ PASS: Admin B cannot access Admin A's contact ({resp.status_code})")
            log(f"✅ PASS: Admin B cannot access Admin A's contact ({resp.status_code})")
        else:
            test_results.append(f"❌ FAIL: Admin B can access Admin A's contact ({resp.status_code})")
            log(f"❌ FAIL: Admin B can access Admin A's contact ({resp.status_code})")
        
        # 4v. Try to access Admin A's CRM client important dates
        log("\n4v. Admin B tries to access Admin A's CRM client important dates")
        resp = requests.get(f"{BASE_URL}/clients/{admin_a_client_id}/important-dates/{admin_a_date_id}",
            headers={"Authorization": f"Bearer {admin_b_token}"})
        if resp.status_code in [403, 404, 405]:  # 405 = endpoint doesn't exist
            test_results.append(f"✅ PASS: Admin B cannot access Admin A's important date ({resp.status_code})")
            log(f"✅ PASS: Admin B cannot access Admin A's important date ({resp.status_code})")
        else:
            test_results.append(f"❌ FAIL: Admin B can access Admin A's important date ({resp.status_code})")
            log(f"❌ FAIL: Admin B can access Admin A's important date ({resp.status_code})")
        
        # ===== STEP 5: Verify public share tokens only reveal own resources =====
        log("\n--- STEP 5: Verify public share tokens isolation ---")
        
        # 5a. Get Admin A's event share token
        resp = requests.get(f"{BASE_URL}/events/{admin_a_event_id}/share",
            headers={"Authorization": f"Bearer {admin_a_token}"})
        assert resp.status_code == 200, f"Get event share failed: {resp.status_code} {resp.text}"
        admin_a_event_share_token = resp.json()["share_url"].split("/g/")[-1]
        log(f"✅ Admin A event share token: {admin_a_event_share_token}")
        
        # 5b. Get Admin A's album share token
        resp = requests.get(f"{BASE_URL}/albums/{admin_a_album_id}/share",
            headers={"Authorization": f"Bearer {admin_a_token}"})
        assert resp.status_code == 200, f"Get album share failed: {resp.status_code} {resp.text}"
        admin_a_album_share_token = resp.json()["share_url"].split("/a/")[-1]
        log(f"✅ Admin A album share token: {admin_a_album_share_token}")
        
        # 5c. Verify public event access (no auth) works for Admin A's event
        log("\n5c. Verify public event access works for Admin A's event")
        resp = requests.get(f"{BASE_URL}/public/events/{admin_a_event_id}")
        if resp.status_code == 200:
            test_results.append("✅ PASS: Public event access works for Admin A's event")
            log("✅ PASS: Public event access works for Admin A's event")
        else:
            test_results.append(f"❌ FAIL: Public event access failed for Admin A's event ({resp.status_code})")
            log(f"❌ FAIL: Public event access failed for Admin A's event ({resp.status_code})")
        
        # 5d. Verify public album manifest (published) works for Admin A's album
        log("\n5d. Verify public album manifest works for Admin A's album")
        resp = requests.get(f"{BASE_URL}/albums/public/{admin_a_album_share_token}")
        if resp.status_code == 200:
            test_results.append("✅ PASS: Public album manifest works for Admin A's album")
            log("✅ PASS: Public album manifest works for Admin A's album")
        else:
            test_results.append(f"❌ FAIL: Public album manifest failed for Admin A's album ({resp.status_code})")
            log(f"❌ FAIL: Public album manifest failed for Admin A's album ({resp.status_code})")
        
        # ===== STEP 6: Check backend logs for 5xx errors =====
        log("\n--- STEP 6: Check backend logs for 5xx errors ---")
        # This will be done via bash command after test
        
        # ===== SUMMARY =====
        log("\n=== TEST SUMMARY ===")
        passed = sum(1 for r in test_results if r.startswith("✅"))
        failed = sum(1 for r in test_results if r.startswith("❌"))
        log(f"Total tests: {len(test_results)}")
        log(f"Passed: {passed}")
        log(f"Failed: {failed}")
        
        if failed > 0:
            log("\n❌ FAILED TESTS:")
            for r in test_results:
                if r.startswith("❌"):
                    log(f"  {r}")
        
        log("\nAll test results:")
        for r in test_results:
            log(f"  {r}")
        
    finally:
        # ===== CLEANUP: Delete all throwaway resources =====
        log("\n--- CLEANUP: Deleting all throwaway resources ---")
        
        # Cleanup Admin A's resources
        if admin_a_event_id:
            try:
                resp = requests.delete(f"{BASE_URL}/events/{admin_a_event_id}",
                    headers={"Authorization": f"Bearer {admin_a_token}"})
                if resp.status_code == 200:
                    log(f"✅ Deleted Admin A's event: {admin_a_event_id}")
                else:
                    log(f"⚠️  Failed to delete Admin A's event: {resp.status_code}")
            except Exception as e:
                log(f"⚠️  Error deleting Admin A's event: {e}")
        
        if admin_a_album_id:
            try:
                resp = requests.delete(f"{BASE_URL}/albums/{admin_a_album_id}",
                    headers={"Authorization": f"Bearer {admin_a_token}"})
                if resp.status_code == 200:
                    log(f"✅ Deleted Admin A's album: {admin_a_album_id}")
                else:
                    log(f"⚠️  Failed to delete Admin A's album: {resp.status_code}")
            except Exception as e:
                log(f"⚠️  Error deleting Admin A's album: {e}")
        
        if admin_a_client_id:
            try:
                resp = requests.delete(f"{BASE_URL}/clients/{admin_a_client_id}",
                    headers={"Authorization": f"Bearer {admin_a_token}"})
                if resp.status_code == 200:
                    log(f"✅ Deleted Admin A's CRM client: {admin_a_client_id}")
                else:
                    log(f"⚠️  Failed to delete Admin A's CRM client: {resp.status_code}")
            except Exception as e:
                log(f"⚠️  Error deleting Admin A's CRM client: {e}")
        
        # Cleanup Admin B account
        if admin_b_user_id:
            try:
                # Delete Admin B's user account directly from DB
                log(f"⚠️  Note: Admin B account cleanup requires manual DB deletion or admin endpoint")
                log(f"   Admin B user_id: {admin_b_user_id}, email: {ADMIN_B_EMAIL}")
            except Exception as e:
                log(f"⚠️  Error noting Admin B cleanup: {e}")
        
        log("\n✅ Cleanup complete (Admin B account may need manual DB cleanup)")

if __name__ == "__main__":
    main()
