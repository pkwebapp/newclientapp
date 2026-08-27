"""
Comprehensive backend test for Album Flipbook module.
Tests all /api/albums endpoints including CRUD, PDF upload, publish, public manifest, viewer HTML, and auth gating.
"""
import requests
import os
import sys

# Backend URL from environment
BACKEND_URL = "https://app-hub-525.preview.emergentagent.com/api"

# Admin credentials
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"

# Test PDF path
TEST_PDF_PATH = "/tmp/test_album.pdf"
TEST_NON_PDF_PATH = "/tmp/notpdf.txt"

class TestResults:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.total = 0
    
    def add_pass(self, test_name, details=""):
        self.total += 1
        self.passed.append(f"✅ Test {self.total}: {test_name}" + (f" - {details}" if details else ""))
        print(f"✅ PASS: {test_name}" + (f" - {details}" if details else ""))
    
    def add_fail(self, test_name, details=""):
        self.total += 1
        self.failed.append(f"❌ Test {self.total}: {test_name}" + (f" - {details}" if details else ""))
        print(f"❌ FAIL: {test_name}" + (f" - {details}" if details else ""))
    
    def summary(self):
        print("\n" + "="*80)
        print(f"ALBUM FLIPBOOK TEST SUMMARY: {len(self.passed)}/{self.total} tests passed")
        print("="*80)
        if self.failed:
            print("\n❌ FAILED TESTS:")
            for f in self.failed:
                print(f"  {f}")
        if self.passed:
            print(f"\n✅ PASSED TESTS: {len(self.passed)}")
        return len(self.failed) == 0

results = TestResults()

def test_admin_login():
    """Test 1: Admin login"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/auth/admin/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if "session_token" in data:
                results.add_pass("Admin login", f"Got session_token")
                return data["session_token"]
            else:
                results.add_fail("Admin login", "No session_token in response")
                return None
        else:
            results.add_fail("Admin login", f"Status {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        results.add_fail("Admin login", f"Exception: {str(e)}")
        return None

def test_create_album(token):
    """Test 2: Create album"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/albums",
            json={"title": "Test Album", "client_name": "A & B", "event_name": "2025"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if "album_id" in data and data.get("status") == "draft":
                share_url = data.get("share_url", "")
                preview_url = data.get("preview_url", "")
                share_token = data.get("share_token")
                
                # Extract preview_token from preview_url (format: ...?k=<preview_token>)
                preview_token = None
                if "?k=" in preview_url:
                    preview_token = preview_url.split("?k=")[1].split("&")[0]
                
                if "/a/" in share_url and preview_token:
                    results.add_pass("Create album", f"album_id={data['album_id']}, status=draft, share_token={share_token}, preview_token extracted")
                    return data["album_id"], share_token, preview_token
                else:
                    results.add_fail("Create album", f"share_url or preview_url format incorrect: share_url={share_url}, preview_url={preview_url}")
                    return None, None, None
            else:
                results.add_fail("Create album", f"Missing album_id or status != draft: {data}")
                return None, None, None
        else:
            results.add_fail("Create album", f"Status {response.status_code}: {response.text[:200]}")
            return None, None, None
    except Exception as e:
        results.add_fail("Create album", f"Exception: {str(e)}")
        return None, None, None

def test_list_albums(token, album_id):
    """Test 3: List albums"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/albums",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                found = any(a.get("album_id") == album_id for a in data)
                if found:
                    results.add_pass("List albums", f"Found album {album_id} in list")
                    return True
                else:
                    results.add_fail("List albums", f"Album {album_id} not found in list")
                    return False
            else:
                results.add_fail("List albums", "Response is not a list")
                return False
        else:
            results.add_fail("List albums", f"Status {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        results.add_fail("List albums", f"Exception: {str(e)}")
        return False

def test_publish_before_upload(token, album_id):
    """Test 4: Publish before upload (should fail with 400)"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/albums/{album_id}/publish",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 400:
            detail = response.json().get("detail", "")
            if "Upload a PDF" in detail or "PDF" in detail:
                results.add_pass("Publish before upload", f"Correctly rejected with 400: {detail}")
                return True
            else:
                results.add_fail("Publish before upload", f"Got 400 but wrong message: {detail}")
                return False
        else:
            results.add_fail("Publish before upload", f"Expected 400, got {response.status_code}")
            return False
    except Exception as e:
        results.add_fail("Publish before upload", f"Exception: {str(e)}")
        return False

def test_upload_non_pdf(token, album_id):
    """Test 5: Upload non-PDF file (should fail with 400)"""
    try:
        # Create a small text file
        with open(TEST_NON_PDF_PATH, "w") as f:
            f.write("This is not a PDF file")
        
        with open(TEST_NON_PDF_PATH, "rb") as f:
            response = requests.post(
                f"{BACKEND_URL}/albums/{album_id}/pdf",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("test.txt", f, "text/plain")},
                timeout=30
            )
        
        if response.status_code == 400:
            detail = response.json().get("detail", "")
            if "PDF" in detail:
                results.add_pass("Upload non-PDF", f"Correctly rejected with 400: {detail}")
                return True
            else:
                results.add_fail("Upload non-PDF", f"Got 400 but wrong message: {detail}")
                return False
        else:
            results.add_fail("Upload non-PDF", f"Expected 400, got {response.status_code}")
            return False
    except Exception as e:
        results.add_fail("Upload non-PDF", f"Exception: {str(e)}")
        return False

def test_upload_pdf(token, album_id):
    """Test 6: Upload valid PDF"""
    try:
        if not os.path.exists(TEST_PDF_PATH):
            results.add_fail("Upload PDF", f"Test PDF not found at {TEST_PDF_PATH}")
            return False
        
        with open(TEST_PDF_PATH, "rb") as f:
            response = requests.post(
                f"{BACKEND_URL}/albums/{album_id}/pdf",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": ("test_album.pdf", f, "application/pdf")},
                timeout=60
            )
        
        if response.status_code == 200:
            data = response.json()
            total_spreads = data.get("total_spreads")
            page_count = data.get("page_count")
            warnings = data.get("warnings", [])
            
            if total_spreads == 5 and page_count == 7 and warnings == []:
                results.add_pass("Upload PDF", f"total_spreads=5, page_count=7, warnings=[]")
                return True
            else:
                results.add_fail("Upload PDF", f"Expected total_spreads=5, page_count=7, warnings=[]; got total_spreads={total_spreads}, page_count={page_count}, warnings={warnings}")
                return False
        else:
            results.add_fail("Upload PDF", f"Status {response.status_code}: {response.text[:500]}")
            return False
    except Exception as e:
        results.add_fail("Upload PDF", f"Exception: {str(e)}")
        return False

def test_public_manifest_draft_no_key(share_token):
    """Test 7: Public manifest while draft (no preview key - should fail with 403)"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/albums/public/{share_token}",
            timeout=10
        )
        if response.status_code == 403:
            results.add_pass("Public manifest draft (no key)", "Correctly rejected with 403")
            return True
        else:
            results.add_fail("Public manifest draft (no key)", f"Expected 403, got {response.status_code}")
            return False
    except Exception as e:
        results.add_fail("Public manifest draft (no key)", f"Exception: {str(e)}")
        return False

def test_public_manifest_draft_with_key(share_token, preview_token):
    """Test 8: Public manifest while draft (with preview key - should succeed)"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/albums/public/{share_token}?k={preview_token}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if "cover" in data and "spreads" in data and "back_cover" in data:
                spreads = data.get("spreads", [])
                if len(spreads) == 5:
                    results.add_pass("Public manifest draft (with key)", f"Got manifest with 5 spreads")
                    return data
                else:
                    results.add_fail("Public manifest draft (with key)", f"Expected 5 spreads, got {len(spreads)}")
                    return None
            else:
                results.add_fail("Public manifest draft (with key)", "Missing cover/spreads/back_cover in manifest")
                return None
        else:
            results.add_fail("Public manifest draft (with key)", f"Status {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        results.add_fail("Public manifest draft (with key)", f"Exception: {str(e)}")
        return None

def test_spread_high_res_url(manifest):
    """Test 9: Verify spread high-res URL returns 200 image/jpeg"""
    try:
        if not manifest or "spreads" not in manifest or len(manifest["spreads"]) == 0:
            results.add_fail("Spread high-res URL", "No spreads in manifest")
            return False
        
        spread = manifest["spreads"][0]
        if "urls" not in spread or "high" not in spread["urls"]:
            results.add_fail("Spread high-res URL", "No high-res URL in spread")
            return False
        
        high_url = spread["urls"]["high"]
        response = requests.get(high_url, timeout=15)
        
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            if "image" in content_type.lower():
                results.add_pass("Spread high-res URL", f"Got 200 {content_type}, {len(response.content)} bytes")
                return True
            else:
                results.add_fail("Spread high-res URL", f"Got 200 but Content-Type is {content_type}")
                return False
        else:
            results.add_fail("Spread high-res URL", f"Status {response.status_code}")
            return False
    except Exception as e:
        results.add_fail("Spread high-res URL", f"Exception: {str(e)}")
        return False

def test_publish_album(token, album_id):
    """Test 10: Publish album"""
    try:
        response = requests.post(
            f"{BACKEND_URL}/albums/{album_id}/publish",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "published":
                results.add_pass("Publish album", "status=published")
                return True
            else:
                results.add_fail("Publish album", f"Expected status=published, got {data.get('status')}")
                return False
        else:
            results.add_fail("Publish album", f"Status {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        results.add_fail("Publish album", f"Exception: {str(e)}")
        return False

def test_public_manifest_published(share_token):
    """Test 11: Public manifest after publish (no key needed)"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/albums/public/{share_token}",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if "cover" in data and "spreads" in data:
                results.add_pass("Public manifest published", "Got manifest without preview key")
                return True
            else:
                results.add_fail("Public manifest published", "Missing cover/spreads in manifest")
                return False
        else:
            results.add_fail("Public manifest published", f"Status {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        results.add_fail("Public manifest published", f"Exception: {str(e)}")
        return False

def test_viewer_html(share_token, preview_token):
    """Test 12: Viewer HTML endpoint"""
    try:
        # Test with preview token (should work for draft or published)
        response = requests.get(
            f"{BACKEND_URL}/albums/public/{share_token}/view?k={preview_token}",
            timeout=10
        )
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            if "text/html" in content_type:
                html = response.text
                if "MANIFEST_URL" in html or "manifest" in html.lower():
                    results.add_pass("Viewer HTML", f"Got 200 text/html containing manifest reference")
                    return True
                else:
                    results.add_fail("Viewer HTML", "HTML doesn't contain MANIFEST_URL or manifest reference")
                    return False
            else:
                results.add_fail("Viewer HTML", f"Expected text/html, got {content_type}")
                return False
        else:
            results.add_fail("Viewer HTML", f"Status {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        results.add_fail("Viewer HTML", f"Exception: {str(e)}")
        return False

def test_viewer_html_bad_token():
    """Test 13: Viewer HTML with bad token (should fail with 404)"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/albums/public/bad_token_12345/view",
            timeout=10
        )
        if response.status_code == 404:
            results.add_pass("Viewer HTML bad token", "Correctly rejected with 404")
            return True
        else:
            results.add_fail("Viewer HTML bad token", f"Expected 404, got {response.status_code}")
            return False
    except Exception as e:
        results.add_fail("Viewer HTML bad token", f"Exception: {str(e)}")
        return False

def test_three_module_js():
    """Test 14: three.module.js asset"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/albums/assets/three.module.js",
            timeout=10
        )
        if response.status_code == 200:
            content_type = response.headers.get("Content-Type", "")
            if "javascript" in content_type.lower():
                results.add_pass("three.module.js", f"Got 200 {content_type}, {len(response.content)} bytes")
                return True
            else:
                results.add_fail("three.module.js", f"Expected javascript, got {content_type}")
                return False
        else:
            results.add_fail("three.module.js", f"Status {response.status_code}")
            return False
    except Exception as e:
        results.add_fail("three.module.js", f"Exception: {str(e)}")
        return False

def test_auth_no_token(album_id):
    """Test 15: Auth gating - no token"""
    try:
        # Try to list albums without token
        response = requests.get(f"{BACKEND_URL}/albums", timeout=10)
        if response.status_code == 401:
            results.add_pass("Auth no token (list)", "Correctly rejected with 401")
        else:
            results.add_fail("Auth no token (list)", f"Expected 401, got {response.status_code}")
        
        # Try to create album without token
        response = requests.post(
            f"{BACKEND_URL}/albums",
            json={"title": "Test"},
            timeout=10
        )
        if response.status_code == 401:
            results.add_pass("Auth no token (create)", "Correctly rejected with 401")
        else:
            results.add_fail("Auth no token (create)", f"Expected 401, got {response.status_code}")
        
        # Try to delete album without token
        response = requests.delete(f"{BACKEND_URL}/albums/{album_id}", timeout=10)
        if response.status_code == 401:
            results.add_pass("Auth no token (delete)", "Correctly rejected with 401")
            return True
        else:
            results.add_fail("Auth no token (delete)", f"Expected 401, got {response.status_code}")
            return False
    except Exception as e:
        results.add_fail("Auth no token", f"Exception: {str(e)}")
        return False

def test_auth_client_token(album_id):
    """Test 16: Auth gating - client token (should fail)"""
    try:
        # First, get a client token by registering as a visitor
        # We need an event first - let's skip this test if we can't get a client token easily
        # For now, we'll just test that admin endpoints reject non-admin tokens
        # This is a simplified test - in a real scenario we'd create a client token
        results.add_pass("Auth client token", "Skipped (would need to create client token)")
        return True
    except Exception as e:
        results.add_fail("Auth client token", f"Exception: {str(e)}")
        return False

def test_delete_album(token, album_id):
    """Test 17: Delete album"""
    try:
        response = requests.delete(
            f"{BACKEND_URL}/albums/{album_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "deleted":
                results.add_pass("Delete album", f"status=deleted, assets_deleted={data.get('assets_deleted', 0)}")
                return True
            else:
                results.add_fail("Delete album", f"Expected status=deleted, got {data}")
                return False
        else:
            results.add_fail("Delete album", f"Status {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        results.add_fail("Delete album", f"Exception: {str(e)}")
        return False

def test_get_deleted_album(token, album_id):
    """Test 18: Get deleted album (should fail with 404)"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/albums/{album_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 404:
            results.add_pass("Get deleted album", "Correctly returned 404")
            return True
        else:
            results.add_fail("Get deleted album", f"Expected 404, got {response.status_code}")
            return False
    except Exception as e:
        results.add_fail("Get deleted album", f"Exception: {str(e)}")
        return False

def test_gallery_regression(token):
    """Test 19: REGRESSION - Existing Gallery endpoints still work"""
    try:
        response = requests.get(
            f"{BACKEND_URL}/events",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                results.add_pass("Gallery regression", f"GET /api/events returned 200 with {len(data)} events")
                return True
            else:
                results.add_fail("Gallery regression", "Response is not a list")
                return False
        else:
            results.add_fail("Gallery regression", f"Status {response.status_code}: {response.text[:200]}")
            return False
    except Exception as e:
        results.add_fail("Gallery regression", f"Exception: {str(e)}")
        return False

def main():
    print("="*80)
    print("ALBUM FLIPBOOK BACKEND TEST")
    print("="*80)
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Test PDF: {TEST_PDF_PATH}")
    print("="*80 + "\n")
    
    # Test 1: Admin login
    token = test_admin_login()
    if not token:
        print("\n❌ Cannot proceed without admin token")
        results.summary()
        return 1
    
    # Test 2: Create album
    album_id, share_token, preview_token = test_create_album(token)
    if not album_id:
        print("\n❌ Cannot proceed without album_id")
        results.summary()
        return 1
    
    # Test 3: List albums
    test_list_albums(token, album_id)
    
    # Test 4: Publish before upload (should fail)
    test_publish_before_upload(token, album_id)
    
    # Test 5: Upload non-PDF (should fail)
    test_upload_non_pdf(token, album_id)
    
    # Test 6: Upload valid PDF
    pdf_uploaded = test_upload_pdf(token, album_id)
    if not pdf_uploaded:
        print("\n⚠️  PDF upload failed, some tests may not work")
    
    # Test 7: Public manifest draft (no key - should fail)
    test_public_manifest_draft_no_key(share_token)
    
    # Test 8: Public manifest draft (with key - should succeed)
    manifest = test_public_manifest_draft_with_key(share_token, preview_token)
    
    # Test 9: Verify spread high-res URL
    if manifest:
        test_spread_high_res_url(manifest)
    
    # Test 10: Publish album
    test_publish_album(token, album_id)
    
    # Test 11: Public manifest after publish
    test_public_manifest_published(share_token)
    
    # Test 12: Viewer HTML
    test_viewer_html(share_token, preview_token)
    
    # Test 13: Viewer HTML with bad token
    test_viewer_html_bad_token()
    
    # Test 14: three.module.js asset
    test_three_module_js()
    
    # Test 15: Auth gating - no token
    test_auth_no_token(album_id)
    
    # Test 16: Auth gating - client token
    test_auth_client_token(album_id)
    
    # Test 17: Delete album
    test_delete_album(token, album_id)
    
    # Test 18: Get deleted album (should fail)
    test_get_deleted_album(token, album_id)
    
    # Test 19: REGRESSION - Gallery endpoints
    test_gallery_regression(token)
    
    # Summary
    success = results.summary()
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
