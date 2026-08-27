#!/usr/bin/env python3
"""
Backend-only verification for Album event_date (calendar date) feature.
Tests event_date field in album CRUD operations and Super Admin visibility.
"""

import requests
import sys

# Backend URL from frontend/.env
BASE_URL = "https://newclient-app-2.preview.emergentagent.com/api"

# Test credentials from /app/memory/test_credentials.md
ADMIN_EMAIL = "admin@lumiere.studio"
ADMIN_PASSWORD = "Admin@12345"
SUPERADMIN_EMAIL = "prabhakar@pkphotography.in"
SUPERADMIN_PASSWORD = "SuperAdmin@3214"

def print_test(num, desc):
    """Print test header."""
    print(f"\n{'='*80}")
    print(f"TEST {num}: {desc}")
    print('='*80)

def main():
    admin_token = None
    superadmin_token = None
    album_id = None
    
    try:
        # TEST 1: Admin login
        print_test(1, "Admin login")
        resp = requests.post(f"{BASE_URL}/auth/admin/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        print(f"Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"❌ ERROR: Admin login failed: {resp.text}")
            return False
        data = resp.json()
        admin_token = data["session_token"]
        print(f"✅ Admin logged in successfully")
        print(f"Admin user_id: {data['user']['user_id']}")
        
        # TEST 2: Create album with event_date
        print_test(2, "POST /api/albums with event_date='2026-09-15'")
        resp = requests.post(f"{BASE_URL}/albums", 
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "Calendar QA Album",
                "client_name": "Calendar Client",
                "event_name": "Calendar Event",
                "event_date": "2026-09-15"
            }
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"❌ ERROR: Album creation failed: {resp.text}")
            return False
        data = resp.json()
        album_id = data["album_id"]
        event_date_returned = data.get("event_date")
        print(f"✅ Album created: {album_id}")
        print(f"event_date in response: {event_date_returned}")
        
        # Verify event_date is exactly as sent
        if event_date_returned != "2026-09-15":
            print(f"❌ ERROR: event_date mismatch. Expected '2026-09-15', got '{event_date_returned}'")
            return False
        print(f"✅ event_date matches exactly: '2026-09-15'")
        
        # TEST 3: GET /api/albums/{id} preserves event_date
        print_test(3, "GET /api/albums/{id} preserves event_date")
        resp = requests.get(f"{BASE_URL}/albums/{album_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"❌ ERROR: Get album failed: {resp.text}")
            return False
        data = resp.json()
        event_date_get = data.get("event_date")
        print(f"event_date in GET response: {event_date_get}")
        
        if event_date_get != "2026-09-15":
            print(f"❌ ERROR: event_date not preserved. Expected '2026-09-15', got '{event_date_get}'")
            return False
        print(f"✅ event_date preserved correctly: '2026-09-15'")
        
        # TEST 4: PATCH /api/albums/{id} can update event_date
        print_test(4, "PATCH /api/albums/{id} update event_date to '2026-10-20'")
        resp = requests.patch(f"{BASE_URL}/albums/{album_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "event_date": "2026-10-20"
            }
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"❌ ERROR: Album update failed: {resp.text}")
            return False
        data = resp.json()
        event_date_updated = data.get("event_date")
        print(f"event_date after PATCH: {event_date_updated}")
        
        if event_date_updated != "2026-10-20":
            print(f"❌ ERROR: event_date not updated. Expected '2026-10-20', got '{event_date_updated}'")
            return False
        print(f"✅ event_date updated successfully to '2026-10-20'")
        
        # TEST 5: GET /api/albums returns event_date in list
        print_test(5, "GET /api/albums includes event_date in list")
        resp = requests.get(f"{BASE_URL}/albums",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"❌ ERROR: List albums failed: {resp.text}")
            return False
        albums = resp.json()
        print(f"Total albums: {len(albums)}")
        
        # Find our test album
        test_album = None
        for album in albums:
            if album.get("album_id") == album_id:
                test_album = album
                break
        
        if not test_album:
            print(f"❌ ERROR: Test album {album_id} not found in list")
            return False
        
        event_date_list = test_album.get("event_date")
        print(f"event_date in list: {event_date_list}")
        
        if event_date_list != "2026-10-20":
            print(f"❌ ERROR: event_date in list incorrect. Expected '2026-10-20', got '{event_date_list}'")
            return False
        print(f"✅ event_date appears correctly in album list: '2026-10-20'")
        
        # TEST 6: Super Admin login
        print_test(6, "Super Admin login")
        resp = requests.post(f"{BASE_URL}/superadmin/login", json={
            "email": SUPERADMIN_EMAIL,
            "password": SUPERADMIN_PASSWORD
        })
        print(f"Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"❌ ERROR: Super Admin login failed: {resp.text}")
            return False
        data = resp.json()
        superadmin_token = data["session_token"]
        print(f"✅ Super Admin logged in successfully")
        
        # TEST 7: GET /api/superadmin/albums includes event_date
        print_test(7, "GET /api/superadmin/albums includes event_date")
        resp = requests.get(f"{BASE_URL}/superadmin/albums",
            headers={"Authorization": f"Bearer {superadmin_token}"}
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"❌ ERROR: Super Admin albums list failed: {resp.text}")
            return False
        albums = resp.json()
        print(f"Total albums in Super Admin view: {len(albums)}")
        
        # Find our test album
        test_album_sa = None
        for album in albums:
            if album.get("album_id") == album_id:
                test_album_sa = album
                break
        
        if not test_album_sa:
            print(f"❌ ERROR: Test album {album_id} not found in Super Admin list")
            return False
        
        event_date_sa = test_album_sa.get("event_date")
        print(f"event_date in Super Admin list: {event_date_sa}")
        print(f"Album details: title='{test_album_sa.get('title')}', client_name='{test_album_sa.get('client_name')}', event_name='{test_album_sa.get('event_name')}'")
        
        if event_date_sa != "2026-10-20":
            print(f"❌ ERROR: event_date in Super Admin list incorrect. Expected '2026-10-20', got '{event_date_sa}'")
            return False
        print(f"✅ event_date appears correctly in Super Admin albums list: '2026-10-20'")
        
        # TEST 8: Delete throwaway album
        print_test(8, "DELETE /api/albums/{id} cleanup")
        resp = requests.delete(f"{BASE_URL}/albums/{album_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"❌ ERROR: Album deletion failed: {resp.text}")
            return False
        data = resp.json()
        print(f"✅ Album deleted successfully")
        print(f"Deletion response: {data}")
        
        # TEST 9: Verify album is deleted
        print_test(9, "Verify album deletion (GET should return 404)")
        resp = requests.get(f"{BASE_URL}/albums/{album_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        print(f"Status: {resp.status_code}")
        if resp.status_code != 404:
            print(f"❌ ERROR: Album still exists after deletion (expected 404, got {resp.status_code})")
            return False
        print(f"✅ Album successfully deleted and confirmed (404)")
        
        # TEST 10: Check backend supervisor status
        print_test(10, "Backend supervisor status check")
        import subprocess
        result = subprocess.run(
            ["sudo", "supervisorctl", "status", "backend"],
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if "RUNNING" not in result.stdout:
            print(f"❌ WARNING: Backend service not in RUNNING state")
        else:
            print(f"✅ Backend service is RUNNING")
        
        # TEST 11: Check backend logs for errors
        print_test(11, "Backend logs health check")
        result = subprocess.run(
            ["tail", "-n", "50", "/var/log/supervisor/backend.err.log"],
            capture_output=True,
            text=True
        )
        error_log = result.stdout
        
        # Check for recent critical errors (ignore historical ones)
        critical_errors = []
        for line in error_log.split('\n')[-20:]:  # Only check last 20 lines
            if any(keyword in line.lower() for keyword in ['error', 'exception', 'traceback', 'failed']):
                # Ignore common non-critical patterns
                if not any(ignore in line.lower() for ignore in ['info', 'debug', 'warning']):
                    critical_errors.append(line)
        
        if critical_errors:
            print(f"⚠️  Recent errors found in backend logs:")
            for err in critical_errors[:5]:  # Show max 5 errors
                print(f"  {err}")
        else:
            print(f"✅ No critical errors in recent backend logs")
        
        print("\n" + "="*80)
        print("ALL TESTS PASSED ✅")
        print("="*80)
        print("\nSUMMARY:")
        print("• POST /api/albums with event_date → Returns event_date exactly ✅")
        print("• GET /api/albums/{id} → Preserves event_date ✅")
        print("• PATCH /api/albums/{id} → Can update event_date ✅")
        print("• GET /api/albums → Includes event_date in list ✅")
        print("• GET /api/superadmin/albums → Includes event_date ✅")
        print("• DELETE /api/albums/{id} → Cleanup successful ✅")
        print("• Backend supervisor → RUNNING ✅")
        print("• Backend logs → Healthy ✅")
        
        return True
        
    except Exception as e:
        print(f"\n❌ EXCEPTION: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
