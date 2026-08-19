#!/usr/bin/env python3
"""
Backend test for PIK Connect (Lumiere Gallery) - Full lifecycle test
Tests REAL cloud integrations: Cloudinary + AWS Rekognition + S3 import
"""
import os
import sys
import json
import time
import requests
from pathlib import Path
from PIL import Image
import io

# Backend URL from environment
BACKEND_URL = os.getenv("BACKEND_URL", "https://81a87a21-4359-4696-8115-b7e2de54b0f2.preview.emergentagent.com/api")

# Admin credentials
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

# Test data
CLIENT_NAME = "Test Client"
CLIENT_PHONE = "+61 400 000 001"

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def log_step(step_num, description):
    print(f"\n{'='*80}")
    print(f"{BLUE}STEP {step_num}: {description}{RESET}")
    print('='*80)

def log_pass(message):
    print(f"{GREEN}✅ PASS{RESET}: {message}")

def log_fail(message):
    print(f"{RED}❌ FAIL{RESET}: {message}")

def log_info(message):
    print(f"{YELLOW}ℹ️  INFO{RESET}: {message}")

def create_test_image(filename="test.jpg", size=(400, 400), color='blue'):
    """Create a test JPEG image with a simple face-like pattern."""
    img = Image.new('RGB', size, color=color)
    # Add a simple pattern (not a real face, but good for testing)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    # Draw a circle (face outline)
    draw.ellipse([100, 100, 300, 300], fill='white', outline='black')
    # Draw eyes
    draw.ellipse([150, 150, 180, 180], fill='black')
    draw.ellipse([220, 150, 250, 180], fill='black')
    # Draw mouth
    draw.arc([150, 200, 250, 250], 0, 180, fill='black', width=3)
    img.save(filename)
    return filename

def main():
    print(f"\n{'='*80}")
    print("PIK CONNECT (LUMIERE GALLERY) - BACKEND INTEGRATION TEST")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Testing: Cloudinary + AWS Rekognition + S3 import")
    print('='*80)
    
    # Track test results
    results = []
    admin_token = None
    event_id = None
    photo_id = None
    client_token = None
    
    try:
        # ===================================================================
        # 1. ADMIN AUTH
        # ===================================================================
        
        log_step(1, "Admin login")
        resp = requests.post(f"{BACKEND_URL}/auth/admin/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if resp.status_code != 200:
            log_fail(f"Admin login failed: {resp.status_code} - {resp.text}")
            results.append(("Admin login", False, f"{resp.status_code}"))
            return
        data = resp.json()
        if "session_token" not in data:
            log_fail("Admin login missing session_token")
            results.append(("Admin login", False, "Missing session_token"))
            return
        admin_token = data["session_token"]
        log_pass(f"Admin login successful (200), token: {admin_token[:20]}...")
        results.append(("Admin login", True, "200"))
        
        # ===================================================================
        # 2. EVENT CRUD
        # ===================================================================
        
        log_step(2, "Create event")
        resp = requests.post(f"{BACKEND_URL}/events", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "QA Integration Test", "category": "event"}
        )
        if resp.status_code != 200:
            log_fail(f"Create event failed: {resp.status_code} - {resp.text}")
            results.append(("Create event", False, f"{resp.status_code}"))
            return
        event_data = resp.json()
        event_id = event_data["event_id"]
        log_pass(f"Event created (200): {event_id}")
        results.append(("Create event", True, "200"))
        
        log_step(3, "List events")
        resp = requests.get(f"{BACKEND_URL}/events",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if resp.status_code != 200:
            log_fail(f"List events failed: {resp.status_code} - {resp.text}")
            results.append(("List events", False, f"{resp.status_code}"))
        else:
            events = resp.json()
            event_ids = [e["event_id"] for e in events]
            if event_id not in event_ids:
                log_fail(f"Created event {event_id} not in list")
                results.append(("List events", False, "Event not found"))
            else:
                log_pass(f"List events successful (200), found {len(events)} events")
                results.append(("List events", True, "200"))
        
        log_step(4, "Get event")
        resp = requests.get(f"{BACKEND_URL}/events/{event_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if resp.status_code != 200:
            log_fail(f"Get event failed: {resp.status_code} - {resp.text}")
            results.append(("Get event", False, f"{resp.status_code}"))
        else:
            event = resp.json()
            if event["event_id"] != event_id:
                log_fail(f"Event ID mismatch: {event['event_id']} != {event_id}")
                results.append(("Get event", False, "ID mismatch"))
            else:
                log_pass(f"Get event successful (200): {event['name']}")
                results.append(("Get event", True, "200"))
        
        # ===================================================================
        # 3. PHOTO UPLOAD → CLOUDINARY STORAGE
        # ===================================================================
        
        log_step(5, "Upload photo to event")
        img_file = create_test_image("test_photo.jpg", size=(600, 600), color='lightblue')
        with open(img_file, 'rb') as f:
            resp = requests.post(
                f"{BACKEND_URL}/events/{event_id}/photos",
                headers={"Authorization": f"Bearer {admin_token}"},
                files={"file": ("test_photo.jpg", f, "image/jpeg")}
            )
        os.remove(img_file)
        
        if resp.status_code != 200:
            log_fail(f"Upload photo failed: {resp.status_code} - {resp.text}")
            results.append(("Upload photo", False, f"{resp.status_code}"))
            return
        photo_data = resp.json()
        photo_id = photo_data["photo_id"]
        
        # Verify Cloudinary URLs
        if "url" not in photo_data or "thumb_url" not in photo_data:
            log_fail("Photo response missing url or thumb_url")
            results.append(("Upload photo", False, "Missing URLs"))
            return
        
        if not photo_data["url"].startswith("https://res.cloudinary.com/jeoj8k1t/"):
            log_fail(f"Photo URL doesn't start with Cloudinary CDN: {photo_data['url']}")
            results.append(("Upload photo", False, "Wrong URL"))
            return
        
        if not photo_data["thumb_url"].startswith("https://res.cloudinary.com/jeoj8k1t/"):
            log_fail(f"Thumb URL doesn't start with Cloudinary CDN: {photo_data['thumb_url']}")
            results.append(("Upload photo", False, "Wrong thumb URL"))
            return
        
        log_pass(f"Photo uploaded (200): {photo_id}")
        log_info(f"Photo URL: {photo_data['url'][:60]}...")
        log_info(f"Thumb URL: {photo_data['thumb_url'][:60]}...")
        results.append(("Upload photo", True, "200"))
        
        # Verify photo is accessible from Cloudinary CDN
        log_step(6, "Verify photo accessible from Cloudinary CDN")
        resp = requests.get(photo_data["url"], timeout=10)
        if resp.status_code != 200:
            log_fail(f"Photo URL not accessible: {resp.status_code}")
            results.append(("Photo CDN access", False, f"{resp.status_code}"))
        else:
            log_pass(f"Photo accessible from CDN (200), size: {len(resp.content)} bytes")
            results.append(("Photo CDN access", True, "200"))
        
        # ===================================================================
        # 4. AWS REKOGNITION FACE INDEXING (BACKGROUND WORKER)
        # ===================================================================
        
        log_step(7, "Check indexing status (initial)")
        resp = requests.get(f"{BACKEND_URL}/events/{event_id}/indexing-status",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if resp.status_code != 200:
            log_fail(f"Get indexing status failed: {resp.status_code} - {resp.text}")
            results.append(("Indexing status (initial)", False, f"{resp.status_code}"))
        else:
            status = resp.json()
            log_pass(f"Indexing status (200): {status['status']}, {status['indexed_photos']}/{status['total_photos']} indexed")
            log_info(f"Pending: {status['pending_photos']}, Failed: {status['failed_photos']}, Faces: {status['total_faces']}")
            results.append(("Indexing status (initial)", True, "200"))
        
        log_step(8, "Wait for background indexing to complete")
        max_wait = 30  # seconds
        start_time = time.time()
        indexing_complete = False
        
        while time.time() - start_time < max_wait:
            resp = requests.get(f"{BACKEND_URL}/events/{event_id}/indexing-status",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            if resp.status_code == 200:
                status = resp.json()
                if status.get("complete"):
                    indexing_complete = True
                    log_pass(f"Indexing complete after {int(time.time() - start_time)}s")
                    log_info(f"Status: {status['status']}, Indexed: {status['indexed_photos']}, Faces: {status['total_faces']}")
                    results.append(("Background indexing", True, "Complete"))
                    break
                else:
                    log_info(f"Indexing in progress... {status['percent']}% ({status['indexed_photos']}/{status['total_photos']})")
            time.sleep(2)
        
        if not indexing_complete:
            log_fail(f"Indexing did not complete within {max_wait}s")
            results.append(("Background indexing", False, "Timeout"))
        
        # ===================================================================
        # 5. CLIENT OTP FLOW
        # ===================================================================
        
        log_step(9, "Client OTP flow - Request OTP")
        resp = requests.post(f"{BACKEND_URL}/auth/client/request-otp", json={
            "channel": "phone",
            "phone": CLIENT_PHONE
        })
        if resp.status_code != 200:
            log_fail(f"Request OTP failed: {resp.status_code} - {resp.text}")
            results.append(("Request OTP", False, f"{resp.status_code}"))
            return
        otp_data = resp.json()
        if "dev_code" not in otp_data:
            log_fail("OTP response missing dev_code (OTP_DEV_MODE=true)")
            results.append(("Request OTP", False, "Missing dev_code"))
            return
        dev_code = otp_data["dev_code"]
        log_pass(f"OTP requested (200), dev_code: {dev_code}")
        results.append(("Request OTP", True, "200"))
        
        log_step(10, "Client OTP flow - Verify OTP")
        resp = requests.post(f"{BACKEND_URL}/auth/client/verify-otp", json={
            "channel": "phone",
            "phone": CLIENT_PHONE,
            "code": dev_code,
            "name": CLIENT_NAME
        })
        if resp.status_code != 200:
            log_fail(f"Verify OTP failed: {resp.status_code} - {resp.text}")
            results.append(("Verify OTP", False, f"{resp.status_code}"))
            return
        verify_data = resp.json()
        if "session_token" not in verify_data:
            log_fail("Verify OTP missing session_token")
            results.append(("Verify OTP", False, "Missing session_token"))
            return
        client_token = verify_data["session_token"]
        log_pass(f"OTP verified (200), client token: {client_token[:20]}...")
        results.append(("Verify OTP", True, "200"))
        
        log_step(11, "Client registers for event access")
        resp = requests.post(f"{BACKEND_URL}/public/events/{event_id}/access", json={
            "name": CLIENT_NAME,
            "phone": CLIENT_PHONE
        })
        if resp.status_code != 200:
            log_fail(f"Public access failed: {resp.status_code} - {resp.text}")
            results.append(("Public access", False, f"{resp.status_code}"))
            return
        access_data = resp.json()
        if "session_token" not in access_data:
            log_fail("Public access missing session_token")
            results.append(("Public access", False, "Missing session_token"))
            return
        client_token = access_data["session_token"]  # Update with visitor token
        log_pass(f"Client registered for event access (200)")
        results.append(("Public access", True, "200"))
        
        log_step(12, "Client gives consent")
        resp = requests.post(f"{BACKEND_URL}/client/events/{event_id}/consent",
            headers={"Authorization": f"Bearer {client_token}"},
            json={"accepted": True}
        )
        if resp.status_code != 200:
            log_fail(f"Give consent failed: {resp.status_code} - {resp.text}")
            results.append(("Give consent", False, f"{resp.status_code}"))
        else:
            log_pass(f"Consent given (200)")
            results.append(("Give consent", True, "200"))
        
        log_step(13, "Client selfie search")
        # Create a synthetic selfie image
        selfie_file = create_test_image("selfie.jpg", size=(400, 400), color='pink')
        with open(selfie_file, 'rb') as f:
            resp = requests.post(
                f"{BACKEND_URL}/client/events/{event_id}/search",
                headers={"Authorization": f"Bearer {client_token}"},
                files={"file": ("selfie.jpg", f, "image/jpeg")}
            )
        os.remove(selfie_file)
        
        if resp.status_code != 200:
            log_fail(f"Selfie search failed: {resp.status_code} - {resp.text}")
            results.append(("Selfie search", False, f"{resp.status_code}"))
        else:
            search_data = resp.json()
            log_pass(f"Selfie search successful (200)")
            log_info(f"Status: {search_data.get('status')}, Matches: {search_data.get('count', 0)}")
            log_info("Note: Synthetic test images don't contain real faces, so 0 matches is expected")
            results.append(("Selfie search", True, "200"))
        
        # ===================================================================
        # 6. S3 IMPORT ENDPOINT
        # ===================================================================
        
        log_step(14, "S3 import from bucket 'faceser'")
        resp = requests.post(f"{BACKEND_URL}/events/{event_id}/import-s3",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"bucket": "faceser"}
        )
        if resp.status_code != 200:
            log_fail(f"S3 import failed: {resp.status_code} - {resp.text}")
            results.append(("S3 import", False, f"{resp.status_code}"))
        else:
            import_data = resp.json()
            log_pass(f"S3 import successful (200)")
            log_info(f"Bucket: {import_data.get('bucket')}, Imported: {import_data.get('imported')}, Skipped: {import_data.get('skipped')}")
            log_info("Note: Empty bucket returns 0 imported (expected)")
            results.append(("S3 import", True, "200"))
        
        # ===================================================================
        # 7. PHOTO/EVENT DELETE → CLOUDINARY CLEANUP
        # ===================================================================
        
        log_step(15, "Delete event (with Cloudinary cleanup)")
        resp = requests.delete(f"{BACKEND_URL}/events/{event_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if resp.status_code != 200:
            log_fail(f"Delete event failed: {resp.status_code} - {resp.text}")
            results.append(("Delete event", False, f"{resp.status_code}"))
        else:
            delete_data = resp.json()
            if delete_data.get("status") != "deleted":
                log_fail(f"Delete status mismatch: {delete_data.get('status')}")
                results.append(("Delete event", False, "Status mismatch"))
            else:
                log_pass(f"Event deleted (200)")
                log_info(f"Photos removed: {delete_data.get('photos_removed')}")
                log_info(f"Cloudinary objects deleted: {delete_data.get('cloudinary_objects_deleted')}")
                log_info(f"Rekognition collection deleted: {delete_data.get('faces_collection_deleted')}")
                results.append(("Delete event", True, "200"))
        
        log_step(16, "Verify event is deleted")
        resp = requests.get(f"{BACKEND_URL}/events/{event_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        if resp.status_code != 404:
            log_fail(f"Deleted event should return 404, got: {resp.status_code}")
            results.append(("Verify deletion", False, f"{resp.status_code}"))
        else:
            log_pass(f"Event not found (404) - deletion confirmed")
            results.append(("Verify deletion", True, "404"))
        
    except Exception as e:
        log_fail(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Exception", False, str(e)))
    
    # ===================================================================
    # SUMMARY
    # ===================================================================
    print(f"\n{'='*80}")
    print("TEST SUMMARY")
    print('='*80)
    
    passed = sum(1 for _, success, _ in results if success)
    failed = sum(1 for _, success, _ in results if not success)
    total = len(results)
    
    print(f"\nTotal: {total} tests")
    print(f"{GREEN}Passed: {passed}{RESET}")
    print(f"{RED}Failed: {failed}{RESET}")
    
    if failed > 0:
        print(f"\n{RED}FAILED TESTS:{RESET}")
        for test, success, detail in results:
            if not success:
                print(f"  ❌ {test}: {detail}")
    
    print(f"\n{'='*80}")
    if failed == 0:
        print(f"{GREEN}✅ ALL TESTS PASSED - BACKEND INTEGRATION WORKING{RESET}")
        print(f"{GREEN}Cloudinary + AWS Rekognition + S3 import verified{RESET}")
    else:
        print(f"{RED}❌ SOME TESTS FAILED{RESET}")
    print('='*80)
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
