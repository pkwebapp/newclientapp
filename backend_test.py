"""
Backend API tests for Lumiere Gallery - Photo Likes Feature
Tests the new like endpoints and filename field additions
"""
import requests
import json
import sys

# Configuration
BASE_URL = "https://client-builds.preview.emergentagent.com/api"
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"
CLIENT_EMAIL = "tester_like@example.com"
CLIENT_NAME = "Like Tester"
EVENT_ID = "evt_9a54b15846be"

# Test results tracking
tests_passed = 0
tests_failed = 0
test_results = []

def log_test(test_name, passed, details=""):
    global tests_passed, tests_failed
    status = "✅ PASS" if passed else "❌ FAIL"
    result = f"{status} - {test_name}"
    if details:
        result += f"\n    {details}"
    test_results.append(result)
    print(result)
    if passed:
        tests_passed += 1
    else:
        tests_failed += 1

def test_admin_login():
    """Test 0: Admin login to get token"""
    print("\n=== Test 0: Admin Login ===")
    try:
        response = requests.post(
            f"{BASE_URL}/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("session_token")
            if token:
                log_test("Admin login", True, f"Token received: {token[:20]}...")
                return token
            else:
                log_test("Admin login", False, "No session_token in response")
                return None
        else:
            log_test("Admin login", False, f"Status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        log_test("Admin login", False, f"Exception: {str(e)}")
        return None

def test_client_otp_flow():
    """Test 0b: Client OTP flow to get token"""
    print("\n=== Test 0b: Client OTP Flow ===")
    try:
        # Step 1: Request OTP
        response = requests.post(
            f"{BASE_URL}/auth/client/request-otp",
            json={"channel": "email", "email": CLIENT_EMAIL},
            timeout=10
        )
        if response.status_code != 200:
            log_test("Client OTP request", False, f"Status {response.status_code}: {response.text}")
            return None
        
        data = response.json()
        dev_code = data.get("dev_code")
        if not dev_code:
            log_test("Client OTP request", False, "No dev_code in response")
            return None
        
        log_test("Client OTP request", True, f"OTP code: {dev_code}")
        
        # Step 2: Verify OTP
        response = requests.post(
            f"{BASE_URL}/auth/client/verify-otp",
            json={
                "channel": "email",
                "email": CLIENT_EMAIL,
                "code": dev_code,
                "name": CLIENT_NAME
            },
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("session_token")
            user = data.get("user", {})
            client_user_id = user.get("user_id")
            if token and client_user_id:
                log_test("Client OTP verify", True, f"Token received, user_id: {client_user_id}")
                return token, client_user_id
            else:
                log_test("Client OTP verify", False, "No session_token or user_id in response")
                return None, None
        else:
            log_test("Client OTP verify", False, f"Status {response.status_code}: {response.text}")
            return None, None
    except Exception as e:
        log_test("Client OTP flow", False, f"Exception: {str(e)}")
        return None, None

def test_grant_access(admin_token):
    """Grant full gallery access to client"""
    print("\n=== Test 0c: Grant Full Gallery Access ===")
    try:
        response = requests.post(
            f"{BASE_URL}/events/{EVENT_ID}/access",
            json={
                "channel": "email",
                "email": CLIENT_EMAIL,
                "full_gallery_access": True
            },
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code in [200, 201]:
            log_test("Grant full gallery access", True, f"Status {response.status_code}")
            return True
        else:
            log_test("Grant full gallery access", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Grant full gallery access", False, f"Exception: {str(e)}")
        return False

def test_1_admin_photos_filename(admin_token):
    """Test 1: GET /api/events/{event_id}/photos as ADMIN - confirm filename field"""
    print("\n=== Test 1: Admin Photos List (filename field) ===")
    try:
        response = requests.get(
            f"{BASE_URL}/events/{EVENT_ID}/photos",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 200:
            photos = response.json()
            if not photos:
                log_test("Test 1: Admin photos list", False, "No photos returned")
                return None
            
            # Check if all photos have filename field
            all_have_filename = all("filename" in photo for photo in photos)
            sample_photo = photos[0]
            
            if all_have_filename:
                log_test(
                    "Test 1: Admin photos list", 
                    True, 
                    f"Got {len(photos)} photos, all have 'filename' field. Sample: {sample_photo.get('filename')}"
                )
                return photos
            else:
                missing = [p.get("photo_id") for p in photos if "filename" not in p]
                log_test("Test 1: Admin photos list", False, f"Some photos missing 'filename': {missing[:3]}")
                return photos
        else:
            log_test("Test 1: Admin photos list", False, f"Status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        log_test("Test 1: Admin photos list", False, f"Exception: {str(e)}")
        return None

def test_2_client_photos_filename_liked(client_token):
    """Test 2: GET /api/client/events/{event_id}/photos as CLIENT - confirm filename and liked fields"""
    print("\n=== Test 2: Client Photos List (filename & liked fields) ===")
    try:
        response = requests.get(
            f"{BASE_URL}/client/events/{EVENT_ID}/photos",
            headers={"Authorization": f"Bearer {client_token}"},
            timeout=10
        )
        if response.status_code == 200:
            photos = response.json()
            if not photos:
                log_test("Test 2: Client photos list", False, "No photos returned")
                return None
            
            # Check if all photos have filename and liked fields
            all_have_filename = all("filename" in photo for photo in photos)
            all_have_liked = all("liked" in photo for photo in photos)
            sample_photo = photos[0]
            
            if all_have_filename and all_have_liked:
                log_test(
                    "Test 2: Client photos list", 
                    True, 
                    f"Got {len(photos)} photos. Sample: filename='{sample_photo.get('filename')}', liked={sample_photo.get('liked')}"
                )
                return photos
            else:
                issues = []
                if not all_have_filename:
                    issues.append("missing 'filename'")
                if not all_have_liked:
                    issues.append("missing 'liked'")
                log_test("Test 2: Client photos list", False, f"Issues: {', '.join(issues)}")
                return photos
        else:
            log_test("Test 2: Client photos list", False, f"Status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        log_test("Test 2: Client photos list", False, f"Exception: {str(e)}")
        return None

def test_3_like_toggle(client_token, photo_id):
    """Test 3: POST /api/client/events/{event_id}/photos/{photo_id}/like - toggle functionality"""
    print(f"\n=== Test 3: Like Toggle (photo {photo_id}) ===")
    try:
        # First toggle - should like
        response1 = requests.post(
            f"{BASE_URL}/client/events/{EVENT_ID}/photos/{photo_id}/like",
            headers={"Authorization": f"Bearer {client_token}"},
            timeout=10
        )
        if response1.status_code != 200:
            log_test("Test 3a: First like toggle", False, f"Status {response1.status_code}: {response1.text}")
            return False
        
        data1 = response1.json()
        liked1 = data1.get("liked")
        count1 = data1.get("liked_count")
        
        if liked1 != True or count1 != 1:
            log_test("Test 3a: First like toggle", False, f"Expected liked=True, count=1, got liked={liked1}, count={count1}")
            return False
        
        log_test("Test 3a: First like toggle", True, f"liked={liked1}, liked_count={count1}")
        
        # Second toggle - should unlike
        response2 = requests.post(
            f"{BASE_URL}/client/events/{EVENT_ID}/photos/{photo_id}/like",
            headers={"Authorization": f"Bearer {client_token}"},
            timeout=10
        )
        if response2.status_code != 200:
            log_test("Test 3b: Second like toggle", False, f"Status {response2.status_code}: {response2.text}")
            return False
        
        data2 = response2.json()
        liked2 = data2.get("liked")
        count2 = data2.get("liked_count")
        
        if liked2 != False or count2 != 0:
            log_test("Test 3b: Second like toggle", False, f"Expected liked=False, count=0, got liked={liked2}, count={count2}")
            return False
        
        log_test("Test 3b: Second like toggle", True, f"liked={liked2}, liked_count={count2}")
        
        # Third toggle - like again to leave it liked
        response3 = requests.post(
            f"{BASE_URL}/client/events/{EVENT_ID}/photos/{photo_id}/like",
            headers={"Authorization": f"Bearer {client_token}"},
            timeout=10
        )
        if response3.status_code != 200:
            log_test("Test 3c: Third like toggle", False, f"Status {response3.status_code}: {response3.text}")
            return False
        
        data3 = response3.json()
        liked3 = data3.get("liked")
        count3 = data3.get("liked_count")
        
        if liked3 != True or count3 != 1:
            log_test("Test 3c: Third like toggle", False, f"Expected liked=True, count=1, got liked={liked3}, count={count3}")
            return False
        
        log_test("Test 3c: Third like toggle", True, f"liked={liked3}, liked_count={count3} (left liked)")
        return True
        
    except Exception as e:
        log_test("Test 3: Like toggle", False, f"Exception: {str(e)}")
        return False

def test_4_get_liked(client_token, expected_photo_id):
    """Test 4: GET /api/client/events/{event_id}/liked - get liked photos"""
    print("\n=== Test 4: Get Liked Photos ===")
    try:
        response = requests.get(
            f"{BASE_URL}/client/events/{EVENT_ID}/liked",
            headers={"Authorization": f"Bearer {client_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            count = data.get("count")
            photos = data.get("photos", [])
            
            if count != 1:
                log_test("Test 4: Get liked photos", False, f"Expected count=1, got count={count}")
                return False
            
            if len(photos) != 1:
                log_test("Test 4: Get liked photos", False, f"Expected 1 photo, got {len(photos)}")
                return False
            
            photo = photos[0]
            if photo.get("photo_id") != expected_photo_id:
                log_test("Test 4: Get liked photos", False, f"Expected photo_id={expected_photo_id}, got {photo.get('photo_id')}")
                return False
            
            if photo.get("liked") != True:
                log_test("Test 4: Get liked photos", False, f"Expected liked=True, got {photo.get('liked')}")
                return False
            
            if "filename" not in photo:
                log_test("Test 4: Get liked photos", False, "Photo missing 'filename' field")
                return False
            
            log_test(
                "Test 4: Get liked photos", 
                True, 
                f"count={count}, photo_id={photo.get('photo_id')}, filename={photo.get('filename')}, liked={photo.get('liked')}"
            )
            return True
        else:
            log_test("Test 4: Get liked photos", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 4: Get liked photos", False, f"Exception: {str(e)}")
        return False

def test_5_refetch_photos_liked_annotation(client_token, liked_photo_id):
    """Test 5: Re-fetch photos to confirm liked annotation works"""
    print("\n=== Test 5: Re-fetch Photos (liked annotation) ===")
    try:
        response = requests.get(
            f"{BASE_URL}/client/events/{EVENT_ID}/photos",
            headers={"Authorization": f"Bearer {client_token}"},
            timeout=10
        )
        if response.status_code == 200:
            photos = response.json()
            liked_photo = next((p for p in photos if p.get("photo_id") == liked_photo_id), None)
            
            if not liked_photo:
                log_test("Test 5: Re-fetch photos", False, f"Photo {liked_photo_id} not found in list")
                return False
            
            if liked_photo.get("liked") != True:
                log_test("Test 5: Re-fetch photos", False, f"Expected liked=True for {liked_photo_id}, got {liked_photo.get('liked')}")
                return False
            
            log_test(
                "Test 5: Re-fetch photos", 
                True, 
                f"Photo {liked_photo_id} correctly shows liked=True"
            )
            return True
        else:
            log_test("Test 5: Re-fetch photos", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 5: Re-fetch photos", False, f"Exception: {str(e)}")
        return False

def test_6_admin_client_photos(admin_token, client_user_id, expected_liked_photo_id):
    """Test 6: GET /api/events/{event_id}/clients/{client_user_id}/photos as ADMIN"""
    print(f"\n=== Test 6: Admin View Client Photos (client_user_id={client_user_id}) ===")
    try:
        response = requests.get(
            f"{BASE_URL}/events/{EVENT_ID}/clients/{client_user_id}/photos",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            client_info = data.get("client", {})
            matched = data.get("matched", [])
            liked = data.get("liked", [])
            
            # Check client info
            if not client_info.get("client_user_id"):
                log_test("Test 6: Admin client photos", False, "Missing client info")
                return False
            
            # Check liked array contains expected photo
            liked_ids = [p.get("photo_id") for p in liked]
            if expected_liked_photo_id not in liked_ids:
                log_test(
                    "Test 6: Admin client photos", 
                    False, 
                    f"Expected photo {expected_liked_photo_id} in liked array, got {liked_ids}"
                )
                return False
            
            log_test(
                "Test 6: Admin client photos", 
                True, 
                f"client_user_id={client_info.get('client_user_id')}, matched={len(matched)}, liked={len(liked)}, contains photo {expected_liked_photo_id}"
            )
            return True
        else:
            log_test("Test 6: Admin client photos", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 6: Admin client photos", False, f"Exception: {str(e)}")
        return False

def test_7_auth_permission_checks(client_token, admin_token, client_user_id, valid_photo_id):
    """Test 7: Auth and permission checks (401, 403, 404)"""
    print("\n=== Test 7: Auth & Permission Checks ===")
    
    # Test 7a: Like without token -> 401
    try:
        response = requests.post(
            f"{BASE_URL}/client/events/{EVENT_ID}/photos/{valid_photo_id}/like",
            timeout=10
        )
        if response.status_code == 401:
            log_test("Test 7a: Like without token", True, f"Got 401 as expected")
        else:
            log_test("Test 7a: Like without token", False, f"Expected 401, got {response.status_code}")
    except Exception as e:
        log_test("Test 7a: Like without token", False, f"Exception: {str(e)}")
    
    # Test 7b: Admin client photos with CLIENT token -> 403
    try:
        response = requests.get(
            f"{BASE_URL}/events/{EVENT_ID}/clients/{client_user_id}/photos",
            headers={"Authorization": f"Bearer {client_token}"},
            timeout=10
        )
        if response.status_code == 403:
            log_test("Test 7b: Admin endpoint with client token", True, f"Got 403 as expected")
        else:
            log_test("Test 7b: Admin endpoint with client token", False, f"Expected 403, got {response.status_code}")
    except Exception as e:
        log_test("Test 7b: Admin endpoint with client token", False, f"Exception: {str(e)}")
    
    # Test 7c: Like non-existent photo -> 404
    try:
        response = requests.post(
            f"{BASE_URL}/client/events/{EVENT_ID}/photos/pho_doesnotexist/like",
            headers={"Authorization": f"Bearer {client_token}"},
            timeout=10
        )
        if response.status_code == 404:
            log_test("Test 7c: Like non-existent photo", True, f"Got 404 as expected")
        else:
            log_test("Test 7c: Like non-existent photo", False, f"Expected 404, got {response.status_code}")
    except Exception as e:
        log_test("Test 7c: Like non-existent photo", False, f"Exception: {str(e)}")

def test_8_regression_my_photos(client_token):
    """Test 8: Regression - GET /api/client/events/{event_id}/my-photos"""
    print("\n=== Test 8: Regression - My Photos Endpoint ===")
    try:
        response = requests.get(
            f"{BASE_URL}/client/events/{EVENT_ID}/my-photos",
            headers={"Authorization": f"Bearer {client_token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            # Check structure
            if "searched" not in data or "count" not in data or "photos" not in data:
                log_test("Test 8: My photos regression", False, f"Missing required fields in response: {data.keys()}")
                return False
            
            log_test(
                "Test 8: My photos regression", 
                True, 
                f"searched={data.get('searched')}, count={data.get('count')}, photos={len(data.get('photos', []))}"
            )
            return True
        else:
            log_test("Test 8: My photos regression", False, f"Status {response.status_code}: {response.text}")
            return False
    except Exception as e:
        log_test("Test 8: My photos regression", False, f"Exception: {str(e)}")
        return False

def main():
    print("=" * 80)
    print("LUMIERE GALLERY - BACKEND API TESTS (Photo Likes Feature)")
    print("=" * 80)
    
    # Setup: Admin login
    admin_token = test_admin_login()
    if not admin_token:
        print("\n❌ CRITICAL: Admin login failed. Cannot continue tests.")
        sys.exit(1)
    
    # Setup: Client OTP flow
    result = test_client_otp_flow()
    if not result or result[0] is None:
        print("\n❌ CRITICAL: Client OTP flow failed. Cannot continue tests.")
        sys.exit(1)
    client_token, client_user_id = result
    
    # Setup: Grant access
    if not test_grant_access(admin_token):
        print("\n⚠️  WARNING: Failed to grant access. Tests may fail.")
    
    # Test 1: Admin photos list with filename
    admin_photos = test_1_admin_photos_filename(admin_token)
    if not admin_photos:
        print("\n❌ CRITICAL: Cannot get admin photos. Stopping tests.")
        sys.exit(1)
    
    # Test 2: Client photos list with filename and liked
    client_photos = test_2_client_photos_filename_liked(client_token)
    if not client_photos:
        print("\n❌ CRITICAL: Cannot get client photos. Stopping tests.")
        sys.exit(1)
    
    # Pick a photo for like tests
    test_photo_id = client_photos[0].get("photo_id")
    print(f"\n📸 Using photo {test_photo_id} for like tests")
    
    # Test 3: Like toggle
    test_3_like_toggle(client_token, test_photo_id)
    
    # Test 4: Get liked photos
    test_4_get_liked(client_token, test_photo_id)
    
    # Test 5: Re-fetch photos to confirm annotation
    test_5_refetch_photos_liked_annotation(client_token, test_photo_id)
    
    # Test 6: Admin view of client photos
    test_6_admin_client_photos(admin_token, client_user_id, test_photo_id)
    
    # Test 7: Auth and permission checks
    test_7_auth_permission_checks(client_token, admin_token, client_user_id, test_photo_id)
    
    # Test 8: Regression - my-photos endpoint
    test_8_regression_my_photos(client_token)
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print(f"✅ Passed: {tests_passed}")
    print(f"❌ Failed: {tests_failed}")
    print(f"📊 Total: {tests_passed + tests_failed}")
    print("=" * 80)
    
    print("\nDETAILED RESULTS:")
    for result in test_results:
        print(result)
    
    print("\n" + "=" * 80)
    print(f"CLIENT_USER_ID used: {client_user_id}")
    print("=" * 80)
    
    if tests_failed > 0:
        sys.exit(1)
    else:
        print("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)

if __name__ == "__main__":
    main()
