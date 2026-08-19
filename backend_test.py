#!/usr/bin/env python3
"""
Backend test for client-generated share links feature.
Tests all 24 steps from the review request.
"""
import os
import sys
import json
import time
import requests
from pathlib import Path

# Backend URL from environment
BACKEND_URL = os.getenv("BACKEND_URL", "https://newclient-dev.preview.emergentagent.com/api")

# Admin credentials
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

# Test data
SHARER_NAME = "Sharer Sam"
SHARER_PHONE = "+91 90000 55501"
RECIPIENT_NAME = "Recipient Rita"
RECIPIENT_PHONE = "+91 90000 55502"

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"

def log_step(step_num, description):
    print(f"\n{'='*80}")
    print(f"STEP {step_num}: {description}")
    print('='*80)

def log_pass(message):
    print(f"{GREEN}✅ PASS{RESET}: {message}")

def log_fail(message):
    print(f"{RED}❌ FAIL{RESET}: {message}")

def log_info(message):
    print(f"{YELLOW}ℹ️  INFO{RESET}: {message}")

def create_test_image(filename="test.jpg"):
    """Create a small test JPEG image."""
    from PIL import Image
    img = Image.new('RGB', (100, 100), color='red')
    img.save(filename)
    return filename

def main():
    print(f"\n{'='*80}")
    print("CLIENT-GENERATED SHARE LINKS BACKEND TEST")
    print(f"Backend URL: {BACKEND_URL}")
    print('='*80)
    
    # Track test results
    results = []
    
    try:
        # ===================================================================
        # SETUP
        # ===================================================================
        
        # Step 1: Admin login
        log_step(1, "Admin login")
        resp = requests.post(f"{BACKEND_URL}/auth/admin/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if resp.status_code != 200:
            log_fail(f"Admin login failed: {resp.status_code} - {resp.text}")
            results.append(("Step 1: Admin login", False, resp.status_code, "Expected 200"))
            return
        admin_token = resp.json()["session_token"]
        log_pass(f"Admin login successful (200), token: {admin_token[:20]}...")
        results.append(("Step 1: Admin login", True, 200, "200"))
        
        # Step 2: Create event
        log_step(2, "Create throwaway event")
        resp = requests.post(f"{BACKEND_URL}/events", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "QA Share", "category": "wedding"}
        )
        if resp.status_code != 200:
            log_fail(f"Create event failed: {resp.status_code} - {resp.text}")
            results.append(("Step 2: Create event", False, resp.status_code, "Expected 200"))
            return
        event_data = resp.json()
        event_id = event_data["event_id"]
        log_pass(f"Event created (200): {event_id}")
        results.append(("Step 2: Create event", True, 200, "200"))
        
        # Step 3: Upload 3 photos
        log_step(3, "Upload 3 small JPEGs")
        photo_ids = []
        for i in range(3):
            img_file = create_test_image(f"test_{i}.jpg")
            with open(img_file, 'rb') as f:
                resp = requests.post(
                    f"{BACKEND_URL}/events/{event_id}/photos",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    files={"file": (f"test_{i}.jpg", f, "image/jpeg")}
                )
            os.remove(img_file)
            if resp.status_code != 200:
                log_fail(f"Upload photo {i+1} failed: {resp.status_code} - {resp.text}")
                results.append((f"Step 3: Upload photo {i+1}", False, resp.status_code, "Expected 200"))
            else:
                photo_data = resp.json()
                photo_ids.append(photo_data["photo_id"])
                log_pass(f"Photo {i+1} uploaded (200): {photo_data['photo_id']}")
                results.append((f"Step 3: Upload photo {i+1}", True, 200, "200"))
        
        if len(photo_ids) < 3:
            log_fail("Not all photos uploaded successfully")
            return
        
        # Wait for indexing to complete
        log_info("Waiting for background indexing to complete...")
        time.sleep(3)
        
        # Step 4: Sharer registers as visitor
        log_step(4, "Sharer registers as visitor")
        resp = requests.post(f"{BACKEND_URL}/public/events/{event_id}/access", json={
            "name": SHARER_NAME,
            "phone": SHARER_PHONE
        })
        if resp.status_code != 200:
            log_fail(f"Sharer registration failed: {resp.status_code} - {resp.text}")
            results.append(("Step 4: Sharer registration", False, resp.status_code, "Expected 200"))
            return
        sharer_data = resp.json()
        if "session_token" not in sharer_data:
            log_fail("Sharer registration missing session_token")
            results.append(("Step 4: Sharer registration", False, 200, "Missing session_token"))
            return
        if "user" not in sharer_data or "event" not in sharer_data:
            log_fail("Sharer registration missing user or event")
            results.append(("Step 4: Sharer registration", False, 200, "Missing user/event"))
            return
        sharer_token = sharer_data["session_token"]
        log_pass(f"Sharer registered (200), token: {sharer_token[:20]}...")
        log_info(f"Response includes: session_token, user, event ✓")
        results.append(("Step 4: Sharer registration", True, 200, "200"))
        
        # Step 5: Sharer likes one photo
        log_step(5, "Sharer likes one photo")
        # First get photos
        resp = requests.get(
            f"{BACKEND_URL}/client/events/{event_id}/photos?limit=1",
            headers={"Authorization": f"Bearer {sharer_token}"}
        )
        if resp.status_code != 200:
            log_fail(f"Get photos failed: {resp.status_code} - {resp.text}")
            results.append(("Step 5: Get photos", False, resp.status_code, "Expected 200"))
            return
        photos_data = resp.json()
        if not photos_data.get("items"):
            log_fail("No photos returned")
            results.append(("Step 5: Get photos", False, 200, "No photos"))
            return
        photo_id = photos_data["items"][0]["photo_id"]
        log_pass(f"Got photo (200): {photo_id}")
        
        # Like the photo
        resp = requests.post(
            f"{BACKEND_URL}/client/events/{event_id}/photos/{photo_id}/like",
            headers={"Authorization": f"Bearer {sharer_token}"}
        )
        if resp.status_code != 200:
            log_fail(f"Like photo failed: {resp.status_code} - {resp.text}")
            results.append(("Step 5: Like photo", False, resp.status_code, "Expected 200"))
            return
        log_pass(f"Photo liked (200)")
        results.append(("Step 5: Like photo", True, 200, "200"))
        
        # ===================================================================
        # SHARE CREATION (as SHARER_TOKEN)
        # ===================================================================
        
        # Step 6: Create share with scope="all"
        log_step(6, "Create share with scope='all'")
        resp = requests.post(
            f"{BACKEND_URL}/client/events/{event_id}/share",
            headers={"Authorization": f"Bearer {sharer_token}"},
            json={"scope": "all"}
        )
        if resp.status_code != 200:
            log_fail(f"Create share 'all' failed: {resp.status_code} - {resp.text}")
            results.append(("Step 6: Create share 'all'", False, resp.status_code, "Expected 200"))
            return
        share_all_data = resp.json()
        if "share_id" not in share_all_data or "scope" not in share_all_data or "share_url" not in share_all_data:
            log_fail("Share 'all' response missing required fields")
            results.append(("Step 6: Create share 'all'", False, 200, "Missing fields"))
            return
        share_all_id = share_all_data["share_id"]
        if share_all_data["scope"] != "all":
            log_fail(f"Share 'all' scope mismatch: {share_all_data['scope']}")
            results.append(("Step 6: Create share 'all'", False, 200, "Scope mismatch"))
            return
        if not share_all_data["share_url"].endswith(f"/s/{share_all_id}"):
            log_fail(f"Share 'all' URL doesn't end with /s/{share_all_id}")
            results.append(("Step 6: Create share 'all'", False, 200, "URL format wrong"))
            return
        log_pass(f"Share 'all' created (200): {share_all_id}, URL: {share_all_data['share_url']}")
        results.append(("Step 6: Create share 'all'", True, 200, "200"))
        
        # Step 7: Create share with scope="liked" (twice to test reuse)
        log_step(7, "Create share with scope='liked' (test reuse)")
        resp = requests.post(
            f"{BACKEND_URL}/client/events/{event_id}/share",
            headers={"Authorization": f"Bearer {sharer_token}"},
            json={"scope": "liked"}
        )
        if resp.status_code != 200:
            log_fail(f"Create share 'liked' failed: {resp.status_code} - {resp.text}")
            results.append(("Step 7: Create share 'liked' (1st)", False, resp.status_code, "Expected 200"))
            return
        share_liked_data = resp.json()
        share_liked_id = share_liked_data["share_id"]
        log_pass(f"Share 'liked' created (200): {share_liked_id}")
        results.append(("Step 7: Create share 'liked' (1st)", True, 200, "200"))
        
        # Call again to test reuse
        resp = requests.post(
            f"{BACKEND_URL}/client/events/{event_id}/share",
            headers={"Authorization": f"Bearer {sharer_token}"},
            json={"scope": "liked"}
        )
        if resp.status_code != 200:
            log_fail(f"Create share 'liked' (2nd) failed: {resp.status_code} - {resp.text}")
            results.append(("Step 7: Create share 'liked' (2nd)", False, resp.status_code, "Expected 200"))
            return
        share_liked_data_2 = resp.json()
        if share_liked_data_2["share_id"] != share_liked_id:
            log_fail(f"Share 'liked' not reused: {share_liked_data_2['share_id']} != {share_liked_id}")
            results.append(("Step 7: Create share 'liked' (2nd)", False, 200, "Not reused"))
            return
        log_pass(f"Share 'liked' reused (200): SAME share_id {share_liked_id}")
        results.append(("Step 7: Create share 'liked' (2nd)", True, 200, "200"))
        
        # Step 8: Create share with scope="matched"
        log_step(8, "Create share with scope='matched'")
        resp = requests.post(
            f"{BACKEND_URL}/client/events/{event_id}/share",
            headers={"Authorization": f"Bearer {sharer_token}"},
            json={"scope": "matched"}
        )
        if resp.status_code != 200:
            log_fail(f"Create share 'matched' failed: {resp.status_code} - {resp.text}")
            results.append(("Step 8: Create share 'matched'", False, resp.status_code, "Expected 200"))
            return
        share_matched_data = resp.json()
        share_matched_id = share_matched_data["share_id"]
        log_pass(f"Share 'matched' created (200): {share_matched_id}")
        results.append(("Step 8: Create share 'matched'", True, 200, "200"))
        
        # Step 9: Create share with invalid scope
        log_step(9, "Create share with scope='bogus' (expect 400)")
        resp = requests.post(
            f"{BACKEND_URL}/client/events/{event_id}/share",
            headers={"Authorization": f"Bearer {sharer_token}"},
            json={"scope": "bogus"}
        )
        if resp.status_code != 400:
            log_fail(f"Create share 'bogus' should return 400, got: {resp.status_code}")
            results.append(("Step 9: Create share 'bogus'", False, resp.status_code, "Expected 400"))
        else:
            log_pass(f"Share 'bogus' rejected (400)")
            results.append(("Step 9: Create share 'bogus'", True, 400, "400"))
        
        # ===================================================================
        # PUBLIC META (no auth)
        # ===================================================================
        
        # Step 10: Get public share meta
        log_step(10, "Get public share meta (no auth)")
        resp = requests.get(f"{BACKEND_URL}/public/shares/{share_liked_id}")
        if resp.status_code != 200:
            log_fail(f"Get share meta failed: {resp.status_code} - {resp.text}")
            results.append(("Step 10: Get share meta", False, resp.status_code, "Expected 200"))
            return
        meta_data = resp.json()
        if meta_data.get("scope") != "liked":
            log_fail(f"Share meta scope mismatch: {meta_data.get('scope')}")
            results.append(("Step 10: Get share meta", False, 200, "Scope mismatch"))
            return
        if meta_data.get("sharer_name") != SHARER_NAME:
            log_fail(f"Share meta sharer_name mismatch: {meta_data.get('sharer_name')}")
            results.append(("Step 10: Get share meta", False, 200, "Sharer name mismatch"))
            return
        if "event" not in meta_data:
            log_fail("Share meta missing event")
            results.append(("Step 10: Get share meta", False, 200, "Missing event"))
            return
        event_info = meta_data["event"]
        if "name" not in event_info or "cover_url" not in event_info:
            log_fail("Share meta event missing name or cover_url")
            results.append(("Step 10: Get share meta", False, 200, "Missing event fields"))
            return
        if not event_info["cover_url"].startswith("https://res.cloudinary.com/"):
            log_fail(f"Share meta cover_url doesn't start with https://res.cloudinary.com/: {event_info['cover_url']}")
            results.append(("Step 10: Get share meta", False, 200, "Cover URL wrong"))
            return
        log_pass(f"Share meta retrieved (200): scope={meta_data['scope']}, sharer_name={meta_data['sharer_name']}")
        log_info(f"Event: name={event_info['name']}, cover_url starts with https://res.cloudinary.com/ ✓")
        results.append(("Step 10: Get share meta", True, 200, "200"))
        
        # Step 11: Get nonexistent share
        log_step(11, "Get nonexistent share (expect 404)")
        resp = requests.get(f"{BACKEND_URL}/public/shares/shr_nonexistent")
        if resp.status_code != 404:
            log_fail(f"Get nonexistent share should return 404, got: {resp.status_code}")
            results.append(("Step 11: Get nonexistent share", False, resp.status_code, "Expected 404"))
        else:
            log_pass(f"Nonexistent share rejected (404)")
            results.append(("Step 11: Get nonexistent share", True, 404, "404"))
        
        # ===================================================================
        # RECIPIENT GATE + ANALYTICS
        # ===================================================================
        
        # Step 12: Recipient accesses share (liked)
        log_step(12, "Recipient accesses share (liked)")
        resp = requests.post(f"{BACKEND_URL}/public/shares/{share_liked_id}/access", json={
            "name": RECIPIENT_NAME,
            "phone": RECIPIENT_PHONE
        })
        if resp.status_code != 200:
            log_fail(f"Recipient access failed: {resp.status_code} - {resp.text}")
            results.append(("Step 12: Recipient access (liked)", False, resp.status_code, "Expected 200"))
            return
        recipient_data = resp.json()
        if "session_token" not in recipient_data:
            log_fail("Recipient access missing session_token")
            results.append(("Step 12: Recipient access (liked)", False, 200, "Missing session_token"))
            return
        recipient_token = recipient_data["session_token"]
        if recipient_data.get("scope") != "liked":
            log_fail(f"Recipient access scope mismatch: {recipient_data.get('scope')}")
            results.append(("Step 12: Recipient access (liked)", False, 200, "Scope mismatch"))
            return
        if recipient_data.get("count") != 1:
            log_fail(f"Recipient access count mismatch: {recipient_data.get('count')} (expected 1)")
            results.append(("Step 12: Recipient access (liked)", False, 200, "Count mismatch"))
            return
        if "photos" not in recipient_data or len(recipient_data["photos"]) != 1:
            log_fail("Recipient access photos mismatch")
            results.append(("Step 12: Recipient access (liked)", False, 200, "Photos mismatch"))
            return
        photo = recipient_data["photos"][0]
        if "url" not in photo or "thumb_url" not in photo:
            log_fail("Recipient access photo missing url or thumb_url")
            results.append(("Step 12: Recipient access (liked)", False, 200, "Missing photo URLs"))
            return
        if not photo["url"].startswith("https://res.cloudinary.com/"):
            log_fail(f"Recipient access photo url doesn't start with https://res.cloudinary.com/: {photo['url']}")
            results.append(("Step 12: Recipient access (liked)", False, 200, "Photo URL wrong"))
            return
        if not photo["thumb_url"].startswith("https://res.cloudinary.com/"):
            log_fail(f"Recipient access photo thumb_url doesn't start with https://res.cloudinary.com/: {photo['thumb_url']}")
            results.append(("Step 12: Recipient access (liked)", False, 200, "Thumb URL wrong"))
            return
        log_pass(f"Recipient accessed share (200): scope=liked, count=1, token: {recipient_token[:20]}...")
        log_info(f"Photo URLs start with https://res.cloudinary.com/ ✓")
        results.append(("Step 12: Recipient access (liked)", True, 200, "200"))
        
        # Step 13: Recipient accesses share (all)
        log_step(13, "Recipient accesses share (all)")
        resp = requests.post(f"{BACKEND_URL}/public/shares/{share_all_id}/access", json={
            "name": RECIPIENT_NAME,
            "phone": RECIPIENT_PHONE
        })
        if resp.status_code != 200:
            log_fail(f"Recipient access (all) failed: {resp.status_code} - {resp.text}")
            results.append(("Step 13: Recipient access (all)", False, resp.status_code, "Expected 200"))
            return
        recipient_all_data = resp.json()
        if recipient_all_data.get("scope") != "all":
            log_fail(f"Recipient access (all) scope mismatch: {recipient_all_data.get('scope')}")
            results.append(("Step 13: Recipient access (all)", False, 200, "Scope mismatch"))
            return
        if recipient_all_data.get("count") != 3:
            log_fail(f"Recipient access (all) count mismatch: {recipient_all_data.get('count')} (expected 3)")
            results.append(("Step 13: Recipient access (all)", False, 200, "Count mismatch"))
            return
        log_pass(f"Recipient accessed share (all) (200): scope=all, count=3")
        results.append(("Step 13: Recipient access (all)", True, 200, "200"))
        
        # Step 14: Check admin analytics (both visitors appear)
        log_step(14, "Check admin analytics (both visitors appear)")
        resp = requests.get(
            f"{BACKEND_URL}/events/{event_id}/visitors",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if resp.status_code != 200:
            log_fail(f"Get visitors failed: {resp.status_code} - {resp.text}")
            results.append(("Step 14: Get visitors", False, resp.status_code, "Expected 200"))
            return
        visitors_data = resp.json()
        visitor_names = [v.get("name") for v in visitors_data]
        if SHARER_NAME not in visitor_names:
            log_fail(f"Sharer '{SHARER_NAME}' not in visitors list")
            results.append(("Step 14: Get visitors", False, 200, "Sharer missing"))
            return
        if RECIPIENT_NAME not in visitor_names:
            log_fail(f"Recipient '{RECIPIENT_NAME}' not in visitors list")
            results.append(("Step 14: Get visitors", False, 200, "Recipient missing"))
            return
        log_pass(f"Both visitors appear in analytics (200): {SHARER_NAME}, {RECIPIENT_NAME}")
        results.append(("Step 14: Get visitors", True, 200, "200"))
        
        # Step 15: Empty name validation
        log_step(15, "Empty name validation (expect 400)")
        resp = requests.post(f"{BACKEND_URL}/public/shares/{share_liked_id}/access", json={
            "name": "",
            "phone": RECIPIENT_PHONE
        })
        if resp.status_code != 400:
            log_fail(f"Empty name should return 400, got: {resp.status_code}")
            results.append(("Step 15: Empty name", False, resp.status_code, "Expected 400"))
        else:
            log_pass(f"Empty name rejected (400)")
            results.append(("Step 15: Empty name", True, 400, "400"))
        
        # ===================================================================
        # REFRESH
        # ===================================================================
        
        # Step 16: Refresh photos with recipient token
        log_step(16, "Refresh photos with recipient token")
        resp = requests.get(
            f"{BACKEND_URL}/public/shares/{share_liked_id}/photos",
            headers={"Authorization": f"Bearer {recipient_token}"}
        )
        if resp.status_code != 200:
            log_fail(f"Refresh photos failed: {resp.status_code} - {resp.text}")
            results.append(("Step 16: Refresh photos", False, resp.status_code, "Expected 200"))
            return
        refresh_data = resp.json()
        if refresh_data.get("scope") != "liked":
            log_fail(f"Refresh photos scope mismatch: {refresh_data.get('scope')}")
            results.append(("Step 16: Refresh photos", False, 200, "Scope mismatch"))
            return
        if refresh_data.get("count") != 1:
            log_fail(f"Refresh photos count mismatch: {refresh_data.get('count')}")
            results.append(("Step 16: Refresh photos", False, 200, "Count mismatch"))
            return
        log_pass(f"Refresh photos successful (200): scope=liked, count=1")
        results.append(("Step 16: Refresh photos", True, 200, "200"))
        
        # Step 17: Refresh photos without token (expect 401)
        log_step(17, "Refresh photos without token (expect 401)")
        resp = requests.get(f"{BACKEND_URL}/public/shares/{share_liked_id}/photos")
        if resp.status_code != 401:
            log_fail(f"Refresh without token should return 401, got: {resp.status_code}")
            results.append(("Step 17: Refresh without token", False, resp.status_code, "Expected 401"))
        else:
            log_pass(f"Refresh without token rejected (401)")
            results.append(("Step 17: Refresh without token", True, 401, "401"))
        
        # ===================================================================
        # PERMISSION EDGE
        # ===================================================================
        
        # Step 18: Recipient with full access can create share
        log_step(18, "Recipient with full access can create share")
        resp = requests.post(
            f"{BACKEND_URL}/client/events/{event_id}/share",
            headers={"Authorization": f"Bearer {recipient_token}"},
            json={"scope": "all"}
        )
        if resp.status_code != 200:
            log_fail(f"Recipient create share failed: {resp.status_code} - {resp.text}")
            results.append(("Step 18: Recipient create share", False, resp.status_code, "Expected 200"))
        else:
            log_pass(f"Recipient with full access can create share (200)")
            log_info("Recipients get full access via public gate, so they can create shares")
            results.append(("Step 18: Recipient create share", True, 200, "200"))
        
        # ===================================================================
        # ARCHIVED GATING
        # ===================================================================
        
        # Step 19: Archive event
        log_step(19, "Archive event")
        resp = requests.post(
            f"{BACKEND_URL}/events/{event_id}/archive",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if resp.status_code != 200:
            log_fail(f"Archive event failed: {resp.status_code} - {resp.text}")
            results.append(("Step 19: Archive event", False, resp.status_code, "Expected 200"))
            return
        archive_data = resp.json()
        if archive_data.get("status") != "archived":
            log_fail(f"Archive event status mismatch: {archive_data.get('status')}")
            results.append(("Step 19: Archive event", False, 200, "Status mismatch"))
            return
        log_pass(f"Event archived (200): status=archived")
        results.append(("Step 19: Archive event", True, 200, "200"))
        
        # Step 20: Get share meta (archived) - expect 403
        log_step(20, "Get share meta (archived) - expect 403")
        resp = requests.get(f"{BACKEND_URL}/public/shares/{share_all_id}")
        if resp.status_code != 403:
            log_fail(f"Get share meta (archived) should return 403, got: {resp.status_code}")
            results.append(("Step 20: Get share meta (archived)", False, resp.status_code, "Expected 403"))
        else:
            detail = resp.json().get("detail", "")
            expected_msg = "This gallery has been archived. Please contact your photographer for access."
            if detail != expected_msg:
                log_fail(f"Archived message mismatch:\nGot: '{detail}'\nExpected: '{expected_msg}'")
                results.append(("Step 20: Get share meta (archived)", False, 403, "Message mismatch"))
            else:
                log_pass(f"Share meta (archived) rejected (403) with correct message")
                results.append(("Step 20: Get share meta (archived)", True, 403, "403"))
        
        # Step 21: Access share (archived) - expect 403
        log_step(21, "Access share (archived) - expect 403")
        resp = requests.post(f"{BACKEND_URL}/public/shares/{share_all_id}/access", json={
            "name": "X",
            "phone": "+91 90000 55503"
        })
        if resp.status_code != 403:
            log_fail(f"Access share (archived) should return 403, got: {resp.status_code}")
            results.append(("Step 21: Access share (archived)", False, resp.status_code, "Expected 403"))
        else:
            detail = resp.json().get("detail", "")
            expected_msg = "This gallery has been archived. Please contact your photographer for access."
            if detail != expected_msg:
                log_fail(f"Archived message mismatch:\nGot: '{detail}'\nExpected: '{expected_msg}'")
                results.append(("Step 21: Access share (archived)", False, 403, "Message mismatch"))
            else:
                log_pass(f"Access share (archived) rejected (403) with SAME archived message")
                results.append(("Step 21: Access share (archived)", True, 403, "403"))
        
        # Step 22: Unarchive event
        log_step(22, "Unarchive event")
        resp = requests.post(
            f"{BACKEND_URL}/events/{event_id}/unarchive",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if resp.status_code != 200:
            log_fail(f"Unarchive event failed: {resp.status_code} - {resp.text}")
            results.append(("Step 22: Unarchive event", False, resp.status_code, "Expected 200"))
            return
        unarchive_data = resp.json()
        if unarchive_data.get("status") != "active":
            log_fail(f"Unarchive event status mismatch: {unarchive_data.get('status')}")
            results.append(("Step 22: Unarchive event", False, 200, "Status mismatch"))
            return
        log_pass(f"Event unarchived (200): status=active")
        results.append(("Step 22: Unarchive event", True, 200, "200"))
        
        # Step 23: Get share meta (active again) - expect 200
        log_step(23, "Get share meta (active again) - expect 200")
        resp = requests.get(f"{BACKEND_URL}/public/shares/{share_all_id}")
        if resp.status_code != 200:
            log_fail(f"Get share meta (active) failed: {resp.status_code} - {resp.text}")
            results.append(("Step 23: Get share meta (active)", False, resp.status_code, "Expected 200"))
        else:
            log_pass(f"Share meta (active) retrieved (200)")
            results.append(("Step 23: Get share meta (active)", True, 200, "200"))
        
        # ===================================================================
        # BLOCKED VISITOR
        # ===================================================================
        
        # Step 24: Get recipient visitor_id
        log_step(24, "Block recipient visitor")
        resp = requests.get(
            f"{BACKEND_URL}/events/{event_id}/visitors",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if resp.status_code != 200:
            log_fail(f"Get visitors failed: {resp.status_code} - {resp.text}")
            results.append(("Step 24: Get visitors", False, resp.status_code, "Expected 200"))
            return
        visitors_data = resp.json()
        recipient_visitor = None
        for v in visitors_data:
            if v.get("name") == RECIPIENT_NAME:
                recipient_visitor = v
                break
        if not recipient_visitor:
            log_fail(f"Recipient visitor not found")
            results.append(("Step 24: Get visitors", False, 200, "Recipient not found"))
            return
        recipient_visitor_id = recipient_visitor["visitor_id"]
        log_pass(f"Found recipient visitor: {recipient_visitor_id}")
        
        # Block the visitor
        resp = requests.patch(
            f"{BACKEND_URL}/events/{event_id}/visitors/{recipient_visitor_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"status": "blocked"}
        )
        if resp.status_code != 200:
            log_fail(f"Block visitor failed: {resp.status_code} - {resp.text}")
            results.append(("Step 24: Block visitor", False, resp.status_code, "Expected 200"))
            return
        log_pass(f"Visitor blocked (200)")
        results.append(("Step 24: Block visitor", True, 200, "200"))
        
        # Step 25: Blocked visitor tries to access share - expect 403
        log_step(25, "Blocked visitor tries to access share (expect 403)")
        resp = requests.post(f"{BACKEND_URL}/public/shares/{share_all_id}/access", json={
            "name": RECIPIENT_NAME,
            "phone": RECIPIENT_PHONE
        })
        if resp.status_code != 403:
            log_fail(f"Blocked visitor access should return 403, got: {resp.status_code}")
            results.append(("Step 25: Blocked visitor access", False, resp.status_code, "Expected 403"))
        else:
            detail = resp.json().get("detail", "")
            expected_msg = "Your access to this gallery has been blocked"
            if expected_msg not in detail:
                log_fail(f"Blocked message mismatch:\nGot: '{detail}'\nExpected to contain: '{expected_msg}'")
                results.append(("Step 25: Blocked visitor access", False, 403, "Message mismatch"))
            else:
                log_pass(f"Blocked visitor access rejected (403) with blocked message")
                results.append(("Step 25: Blocked visitor access", True, 403, "403"))
        
        # ===================================================================
        # CLEANUP
        # ===================================================================
        
        # Step 26: Delete event
        log_step(26, "Delete event (cleanup)")
        resp = requests.delete(
            f"{BACKEND_URL}/events/{event_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if resp.status_code != 200:
            log_fail(f"Delete event failed: {resp.status_code} - {resp.text}")
            results.append(("Step 26: Delete event", False, resp.status_code, "Expected 200"))
            return
        delete_data = resp.json()
        if delete_data.get("status") != "deleted":
            log_fail(f"Delete event status mismatch: {delete_data.get('status')}")
            results.append(("Step 26: Delete event", False, 200, "Status mismatch"))
            return
        log_pass(f"Event deleted (200): status=deleted")
        log_info(f"Cleanup: photos_removed={delete_data.get('photos_removed')}, cloudinary_objects_deleted={delete_data.get('cloudinary_objects_deleted')}, faces_collection_deleted={delete_data.get('faces_collection_deleted')}")
        results.append(("Step 26: Delete event", True, 200, "200"))
        
        # Step 27: Get share after event deleted - expect 404
        log_step(27, "Get share after event deleted (expect 404)")
        resp = requests.get(f"{BACKEND_URL}/public/shares/{share_all_id}")
        if resp.status_code != 404:
            log_fail(f"Get share (deleted event) should return 404, got: {resp.status_code}")
            results.append(("Step 27: Get share (deleted)", False, resp.status_code, "Expected 404"))
        else:
            log_pass(f"Share gone with event (404)")
            results.append(("Step 27: Get share (deleted)", True, 404, "404"))
        
    except Exception as e:
        log_fail(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Exception", False, 0, str(e)))
    
    # ===================================================================
    # SUMMARY
    # ===================================================================
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print('='*80)
    
    passed = sum(1 for _, success, _, _ in results if success)
    failed = sum(1 for _, success, _, _ in results if not success)
    total = len(results)
    
    print(f"\nTotal: {total} tests")
    print(f"{GREEN}Passed: {passed}{RESET}")
    print(f"{RED}Failed: {failed}{RESET}")
    
    if failed > 0:
        print(f"\n{RED}FAILED TESTS:{RESET}")
        for test, success, actual, expected in results:
            if not success:
                print(f"  ❌ {test}: {actual} (expected {expected})")
    
    print(f"\n{'='*80}")
    if failed == 0:
        print(f"{GREEN}✅ ALL TESTS PASSED{RESET}")
    else:
        print(f"{RED}❌ SOME TESTS FAILED{RESET}")
    print('='*80)
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
