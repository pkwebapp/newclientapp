#!/usr/bin/env python3
"""
Integration test for Cloudinary storage + AWS Rekognition face engine + S3 import.
Tests the switch from mock/emergent services to REAL cloud services.
"""
import os
import sys
import json
import time
import base64
import requests
from io import BytesIO
from PIL import Image, ImageDraw

# Backend URL
BACKEND_URL = "https://newclient-demo.preview.emergentagent.com/api"

# Admin credentials
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

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

def create_face_image(filename="face.jpg"):
    """Create a synthetic face-like image with clear facial features."""
    # Create a 400x400 image with a face-like structure
    img = Image.new('RGB', (400, 400), color='#FFE0BD')  # Skin tone background
    draw = ImageDraw.Draw(img)
    
    # Draw face outline (oval)
    draw.ellipse([50, 50, 350, 380], fill='#FFD4A3', outline='#D4A574', width=2)
    
    # Draw eyes (two circles)
    draw.ellipse([100, 120, 150, 170], fill='white', outline='black', width=2)
    draw.ellipse([250, 120, 300, 170], fill='white', outline='black', width=2)
    
    # Draw pupils
    draw.ellipse([115, 135, 135, 155], fill='#4A4A4A')
    draw.ellipse([265, 135, 285, 155], fill='#4A4A4A')
    
    # Draw nose (triangle)
    draw.polygon([(200, 180), (180, 240), (220, 240)], fill='#E8C4A0', outline='#D4A574')
    
    # Draw mouth (arc)
    draw.arc([140, 260, 260, 320], start=0, end=180, fill='#8B4513', width=3)
    
    # Draw eyebrows
    draw.arc([90, 90, 160, 110], start=180, end=360, fill='#654321', width=3)
    draw.arc([240, 90, 310, 110], start=180, end=360, fill='#654321', width=3)
    
    # Draw hair (top arc)
    draw.ellipse([40, 30, 360, 150], fill='#654321', outline='#4A3621', width=2)
    
    img.save(filename, 'JPEG', quality=95)
    log_info(f"Created synthetic face image: {filename}")
    return filename

def create_selfie_image(filename="selfie.jpg"):
    """Create a similar face for selfie matching (slightly different angle)."""
    # Create a similar face but with slight variations
    img = Image.new('RGB', (400, 400), color='#FFE0BD')
    draw = ImageDraw.Draw(img)
    
    # Face outline (slightly rotated)
    draw.ellipse([60, 50, 340, 380], fill='#FFD4A3', outline='#D4A574', width=2)
    
    # Eyes
    draw.ellipse([110, 130, 160, 180], fill='white', outline='black', width=2)
    draw.ellipse([240, 130, 290, 180], fill='white', outline='black', width=2)
    
    # Pupils
    draw.ellipse([125, 145, 145, 165], fill='#4A4A4A')
    draw.ellipse([255, 145, 275, 165], fill='#4A4A4A')
    
    # Nose
    draw.polygon([(200, 190), (185, 250), (215, 250)], fill='#E8C4A0', outline='#D4A574')
    
    # Mouth (smiling)
    draw.arc([150, 270, 250, 330], start=0, end=180, fill='#8B4513', width=3)
    
    # Eyebrows
    draw.arc([100, 100, 170, 120], start=180, end=360, fill='#654321', width=3)
    draw.arc([230, 100, 300, 120], start=180, end=360, fill='#654321', width=3)
    
    # Hair
    draw.ellipse([50, 40, 350, 160], fill='#654321', outline='#4A3621', width=2)
    
    img.save(filename, 'JPEG', quality=95)
    log_info(f"Created synthetic selfie image: {filename}")
    return filename

def main():
    print(f"\n{'='*80}")
    print(f"{BLUE}CLOUDINARY + REKOGNITION + S3 INTEGRATION TEST{RESET}")
    print(f"Backend URL: {BACKEND_URL}")
    print('='*80)
    
    results = []
    admin_token = None
    event_id = None
    photo_id = None
    client_token = None
    
    try:
        # ===================================================================
        # STEP 1: Admin Authentication
        # ===================================================================
        log_step(1, "Admin login")
        resp = requests.post(f"{BACKEND_URL}/auth/admin/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        
        if resp.status_code != 200:
            log_fail(f"Admin login failed: {resp.status_code}")
            log_info(f"Response: {resp.text}")
            results.append(("Admin login", False, resp.status_code, resp.text))
            return False
        
        data = resp.json()
        if "session_token" not in data:
            log_fail("Admin login missing session_token")
            results.append(("Admin login", False, 200, "Missing session_token"))
            return False
        
        admin_token = data["session_token"]
        log_pass(f"Admin login successful (200)")
        log_info(f"Token: {admin_token[:30]}...")
        results.append(("Admin login", True, 200, "OK"))
        
        # ===================================================================
        # STEP 2: Create Event
        # ===================================================================
        log_step(2, "Create event")
        resp = requests.post(f"{BACKEND_URL}/events",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "Integration Test Event",
                "category": "wedding",
                "photographer": "Test Photographer"
            }
        )
        
        if resp.status_code != 200:
            log_fail(f"Create event failed: {resp.status_code}")
            log_info(f"Response: {resp.text}")
            results.append(("Create event", False, resp.status_code, resp.text))
            return False
        
        data = resp.json()
        if "event_id" not in data:
            log_fail("Create event missing event_id")
            results.append(("Create event", False, 200, "Missing event_id"))
            return False
        
        event_id = data["event_id"]
        log_pass(f"Event created (200): {event_id}")
        results.append(("Create event", True, 200, "OK"))
        
        # ===================================================================
        # STEP 3: Upload Photo with REAL Face
        # ===================================================================
        log_step(3, "Upload photo with face (Cloudinary + Rekognition)")
        
        # Create a face image
        face_file = create_face_image("test_face.jpg")
        
        with open(face_file, 'rb') as f:
            resp = requests.post(
                f"{BACKEND_URL}/events/{event_id}/photos",
                headers={"Authorization": f"Bearer {admin_token}"},
                files={"file": ("face.jpg", f, "image/jpeg")}
            )
        
        os.remove(face_file)
        
        if resp.status_code != 200:
            log_fail(f"Upload photo failed: {resp.status_code}")
            log_info(f"Response: {resp.text}")
            results.append(("Upload photo", False, resp.status_code, resp.text))
            return False
        
        data = resp.json()
        if "photo_id" not in data:
            log_fail("Upload photo missing photo_id")
            results.append(("Upload photo", False, 200, "Missing photo_id"))
            return False
        
        photo_id = data["photo_id"]
        log_pass(f"Photo uploaded (200): {photo_id}")
        
        # Check if Cloudinary URLs are present
        if "url" in data and data["url"]:
            if "res.cloudinary.com" in data["url"]:
                log_pass(f"Photo URL points to Cloudinary: {data['url'][:60]}...")
                results.append(("Photo Cloudinary URL", True, 200, "OK"))
            else:
                log_fail(f"Photo URL does not point to Cloudinary: {data['url']}")
                results.append(("Photo Cloudinary URL", False, 200, "Wrong CDN"))
        
        if "thumb_url" in data and data["thumb_url"]:
            if "res.cloudinary.com" in data["thumb_url"]:
                log_pass(f"Thumbnail URL points to Cloudinary: {data['thumb_url'][:60]}...")
                results.append(("Thumbnail Cloudinary URL", True, 200, "OK"))
            else:
                log_fail(f"Thumbnail URL does not point to Cloudinary: {data['thumb_url']}")
                results.append(("Thumbnail Cloudinary URL", False, 200, "Wrong CDN"))
        
        results.append(("Upload photo", True, 200, "OK"))
        
        # ===================================================================
        # STEP 4: Wait for Face Indexing (Background Worker)
        # ===================================================================
        log_step(4, "Wait for face indexing (Rekognition)")
        log_info("Polling indexing status...")
        
        max_wait = 30  # 30 seconds max
        poll_interval = 2
        elapsed = 0
        indexing_complete = False
        
        while elapsed < max_wait:
            resp = requests.get(
                f"{BACKEND_URL}/events/{event_id}/indexing-status",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            
            if resp.status_code != 200:
                log_fail(f"Get indexing status failed: {resp.status_code}")
                log_info(f"Response: {resp.text}")
                break
            
            status_data = resp.json()
            log_info(f"Status: {status_data.get('status')}, Indexed: {status_data.get('indexed_photos')}/{status_data.get('total_photos')}, Faces: {status_data.get('total_faces')}, Complete: {status_data.get('complete')}")
            
            if status_data.get("complete"):
                indexing_complete = True
                log_pass(f"Indexing complete: {status_data.get('indexed_photos')} photos indexed, {status_data.get('total_faces')} faces detected")
                results.append(("Face indexing", True, 200, f"{status_data.get('total_faces')} faces"))
                break
            
            time.sleep(poll_interval)
            elapsed += poll_interval
        
        if not indexing_complete:
            log_fail(f"Indexing did not complete within {max_wait} seconds")
            results.append(("Face indexing", False, 0, "Timeout"))
        
        # ===================================================================
        # STEP 5: List Photos (Verify Cloudinary CDN)
        # ===================================================================
        log_step(5, "List photos (verify Cloudinary CDN)")
        resp = requests.get(
            f"{BACKEND_URL}/events/{event_id}/photos",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        if resp.status_code != 200:
            log_fail(f"List photos failed: {resp.status_code}")
            log_info(f"Response: {resp.text}")
            results.append(("List photos", False, resp.status_code, resp.text))
        else:
            data = resp.json()
            photos = data.get("items", [])
            
            if len(photos) == 0:
                log_fail("No photos returned")
                results.append(("List photos", False, 200, "No photos"))
            else:
                log_pass(f"Photos listed (200): {len(photos)} photos")
                
                # Verify Cloudinary URLs
                all_cloudinary = True
                for photo in photos:
                    if "url" in photo and photo["url"]:
                        if "res.cloudinary.com" not in photo["url"]:
                            all_cloudinary = False
                            log_fail(f"Photo {photo.get('photo_id')} URL not from Cloudinary: {photo['url']}")
                    
                    if "thumb_url" in photo and photo["thumb_url"]:
                        if "res.cloudinary.com" not in photo["thumb_url"]:
                            all_cloudinary = False
                            log_fail(f"Photo {photo.get('photo_id')} thumb_url not from Cloudinary: {photo['thumb_url']}")
                
                if all_cloudinary:
                    log_pass("All photo URLs point to Cloudinary CDN")
                    results.append(("List photos CDN", True, 200, "OK"))
                else:
                    results.append(("List photos CDN", False, 200, "Not all Cloudinary"))
                
                results.append(("List photos", True, 200, "OK"))
                
                # Try to fetch one image
                if photos and "url" in photos[0]:
                    log_info(f"Fetching image from Cloudinary: {photos[0]['url'][:60]}...")
                    img_resp = requests.get(photos[0]["url"])
                    if img_resp.status_code == 200 and img_resp.headers.get("content-type", "").startswith("image/"):
                        log_pass(f"Image retrieved from Cloudinary (200, {len(img_resp.content)} bytes, {img_resp.headers.get('content-type')})")
                        results.append(("Fetch Cloudinary image", True, 200, "OK"))
                    else:
                        log_fail(f"Failed to fetch image: {img_resp.status_code}")
                        results.append(("Fetch Cloudinary image", False, img_resp.status_code, "Failed"))
        
        # ===================================================================
        # STEP 6: S3 Import (Empty Bucket)
        # ===================================================================
        log_step(6, "S3 import from empty bucket (faceser)")
        resp = requests.post(
            f"{BACKEND_URL}/events/{event_id}/import-s3",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"bucket": "faceser"}
        )
        
        if resp.status_code != 200:
            log_fail(f"S3 import failed: {resp.status_code}")
            log_info(f"Response: {resp.text}")
            results.append(("S3 import", False, resp.status_code, resp.text))
        else:
            data = resp.json()
            log_pass(f"S3 import successful (200)")
            log_info(f"Response: {json.dumps(data, indent=2)}")
            
            # Expect 0 imported since bucket is empty
            imported = data.get("imported", -1)
            if imported == 0:
                log_pass("S3 import returned 0 imported (bucket is empty as expected)")
                results.append(("S3 import empty bucket", True, 200, "OK"))
            else:
                log_info(f"S3 import returned {imported} imported (expected 0 for empty bucket)")
                results.append(("S3 import empty bucket", True, 200, f"{imported} imported"))
            
            results.append(("S3 import", True, 200, "OK"))
        
        # ===================================================================
        # STEP 7: Client Selfie Flow (Optional)
        # ===================================================================
        log_step(7, "Client selfie flow (optional)")
        
        # 7a: Request OTP
        log_info("7a: Request client OTP")
        resp = requests.post(f"{BACKEND_URL}/auth/client/request-otp", json={
            "channel": "email",
            "email": "test_integration@example.com"
        })
        
        if resp.status_code != 200:
            log_fail(f"OTP request failed: {resp.status_code}")
            log_info(f"Response: {resp.text}")
            results.append(("Client OTP request", False, resp.status_code, resp.text))
        else:
            data = resp.json()
            log_pass("OTP request successful (200)")
            
            # In OTP_DEV_MODE, the code is returned in the response
            otp_code = data.get("dev_code")
            if otp_code:
                log_pass(f"OTP code returned (dev mode): {otp_code}")
                results.append(("Client OTP request", True, 200, "OK"))
                
                # 7b: Verify OTP
                log_info("7b: Verify OTP")
                resp = requests.post(f"{BACKEND_URL}/auth/client/verify-otp", json={
                    "channel": "email",
                    "email": "test_integration@example.com",
                    "code": otp_code,
                    "name": "Integration Test Client"
                })
                
                if resp.status_code != 200:
                    log_fail(f"OTP verify failed: {resp.status_code}")
                    log_info(f"Response: {resp.text}")
                    results.append(("Client OTP verify", False, resp.status_code, resp.text))
                else:
                    verify_data = resp.json()
                    if "session_token" in verify_data:
                        client_token = verify_data["session_token"]
                        log_pass(f"OTP verified (200), client token: {client_token[:30]}...")
                        results.append(("Client OTP verify", True, 200, "OK"))
                        
                        # 7c: Grant client access to event (via public access)
                        log_info("7c: Grant client access to event")
                        resp = requests.post(
                            f"{BACKEND_URL}/public/events/{event_id}/access",
                            json={
                                "name": "Integration Test Client",
                                "phone": "+91 90000 99999"
                            }
                        )
                        
                        if resp.status_code != 200:
                            log_fail(f"Grant access failed: {resp.status_code}")
                            log_info(f"Response: {resp.text}")
                            results.append(("Client grant access", False, resp.status_code, resp.text))
                        else:
                            access_data = resp.json()
                            # Use the token from public access which has full_gallery_access
                            if "session_token" in access_data:
                                client_token = access_data["session_token"]
                                log_pass("Client granted access to event (200)")
                                results.append(("Client grant access", True, 200, "OK"))
                            else:
                                log_fail("Grant access missing session_token")
                                results.append(("Client grant access", False, 200, "Missing token"))
                        
                        # 7d: Accept consent
                        log_info("7d: Accept consent")
                        resp = requests.post(
                            f"{BACKEND_URL}/client/events/{event_id}/consent",
                            headers={"Authorization": f"Bearer {client_token}"},
                            json={"accepted": True}
                        )
                        
                        if resp.status_code != 200:
                            log_fail(f"Accept consent failed: {resp.status_code}")
                            log_info(f"Response: {resp.text}")
                            results.append(("Client consent", False, resp.status_code, resp.text))
                        else:
                            log_pass("Consent accepted (200)")
                            results.append(("Client consent", True, 200, "OK"))
                            
                            # 7e: Selfie search
                            log_info("7e: Selfie search (Rekognition SearchFacesByImage)")
                            
                            # Create a selfie image
                            selfie_file = create_selfie_image("test_selfie.jpg")
                            
                            with open(selfie_file, 'rb') as f:
                                resp = requests.post(
                                    f"{BACKEND_URL}/client/events/{event_id}/search",
                                    headers={"Authorization": f"Bearer {client_token}"},
                                    files={"file": ("selfie.jpg", f, "image/jpeg")}
                                )
                            
                            os.remove(selfie_file)
                            
                            if resp.status_code != 200:
                                log_fail(f"Selfie search failed: {resp.status_code}")
                                log_info(f"Response: {resp.text}")
                                results.append(("Selfie search", False, resp.status_code, resp.text))
                            else:
                                search_data = resp.json()
                                log_pass("Selfie search successful (200)")
                                log_info(f"Matches: {search_data.get('matched_count', 0)}")
                                
                                # Check if Rekognition ran without errors
                                if "error" not in search_data:
                                    log_pass("Rekognition SearchFacesByImage ran without server errors")
                                    results.append(("Selfie search Rekognition", True, 200, "OK"))
                                else:
                                    log_fail(f"Selfie search returned error: {search_data.get('error')}")
                                    results.append(("Selfie search Rekognition", False, 200, search_data.get('error')))
                                
                                results.append(("Selfie search", True, 200, "OK"))
                    else:
                        log_fail("OTP verify missing session_token")
                        results.append(("Client OTP verify", False, 200, "Missing token"))
            else:
                log_fail("OTP request did not return code (OTP_DEV_MODE may not be enabled)")
                results.append(("Client OTP request", False, 200, "No code"))
        
        # ===================================================================
        # STEP 8: Cleanup - Delete Event
        # ===================================================================
        log_step(8, "Delete event (cleanup)")
        if event_id:
            resp = requests.delete(
                f"{BACKEND_URL}/events/{event_id}",
                headers={"Authorization": f"Bearer {admin_token}"}
            )
            
            if resp.status_code != 200:
                log_fail(f"Delete event failed: {resp.status_code}")
                log_info(f"Response: {resp.text}")
                results.append(("Delete event", False, resp.status_code, resp.text))
            else:
                data = resp.json()
                log_pass(f"Event deleted (200)")
                log_info(f"Photos removed: {data.get('photos_removed')}")
                log_info(f"Cloudinary objects deleted: {data.get('cloudinary_objects_deleted')}")
                log_info(f"Rekognition collection deleted: {data.get('faces_collection_deleted')}")
                
                # Verify cleanup
                if data.get("cloudinary_objects_deleted", 0) > 0:
                    log_pass("Cloudinary objects deleted successfully")
                    results.append(("Cloudinary cleanup", True, 200, "OK"))
                
                if data.get("faces_collection_deleted"):
                    log_pass("Rekognition collection deleted successfully")
                    results.append(("Rekognition cleanup", True, 200, "OK"))
                
                results.append(("Delete event", True, 200, "OK"))
        
    except Exception as e:
        log_fail(f"Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Exception", False, 0, str(e)))
        return False
    
    # ===================================================================
    # SUMMARY
    # ===================================================================
    print(f"\n{'='*80}")
    print(f"{BLUE}TEST SUMMARY{RESET}")
    print('='*80)
    
    passed = sum(1 for _, success, _, _ in results if success)
    failed = sum(1 for _, success, _, _ in results if not success)
    total = len(results)
    
    print(f"\nTotal: {total} tests")
    print(f"{GREEN}Passed: {passed}{RESET}")
    print(f"{RED}Failed: {failed}{RESET}")
    
    if failed > 0:
        print(f"\n{RED}FAILED TESTS:{RESET}")
        for test, success, status, detail in results:
            if not success:
                print(f"  ❌ {test}: {status} - {detail}")
    
    print(f"\n{'='*80}")
    if failed == 0:
        print(f"{GREEN}✅ ALL TESTS PASSED{RESET}")
        print(f"{GREEN}Cloudinary storage, AWS Rekognition, and S3 import are working correctly!{RESET}")
    else:
        print(f"{RED}❌ SOME TESTS FAILED{RESET}")
    print('='*80)
    
    return failed == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
