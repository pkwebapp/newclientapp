#!/usr/bin/env python3
"""
Comprehensive backend test for PIK Connect Invoicing + Revenue Engine module.
Tests invoice settings, CRUD, GST math, payments, PDF, shareable links, and revenue de-duplication.
"""
import requests
import json
import sys
from typing import Optional

# Configuration
BASE_URL = "https://client-hub-439.preview.emergentagent.com/api"
ADMIN_TOKEN = "st_faa06ce423414bb3882b631d6a220a01fa97728ccbdb41c88887d81b47025775"

# Test tracking
test_count = 0
pass_count = 0
fail_count = 0
created_invoices = []
created_events = []

def headers():
    """Return auth headers for admin requests."""
    return {"Authorization": f"Bearer {ADMIN_TOKEN}"}

def test(name: str, condition: bool, details: str = ""):
    """Record test result."""
    global test_count, pass_count, fail_count
    test_count += 1
    if condition:
        pass_count += 1
        print(f"✅ Test {test_count}: {name}")
        if details:
            print(f"   {details}")
    else:
        fail_count += 1
        print(f"❌ Test {test_count}: {name}")
        if details:
            print(f"   {details}")
    return condition

def cleanup():
    """Delete all created test data."""
    print("\n" + "="*80)
    print("CLEANUP: Deleting test data...")
    print("="*80)
    
    # Delete invoices
    for inv_id in created_invoices:
        try:
            r = requests.delete(f"{BASE_URL}/invoices/{inv_id}", headers=headers())
            if r.status_code == 200:
                print(f"✅ Deleted invoice {inv_id}")
            else:
                print(f"⚠️  Failed to delete invoice {inv_id}: {r.status_code}")
        except Exception as e:
            print(f"⚠️  Error deleting invoice {inv_id}: {e}")
    
    # Delete events
    for evt_id in created_events:
        try:
            r = requests.delete(f"{BASE_URL}/events/{evt_id}", headers=headers())
            if r.status_code == 200:
                print(f"✅ Deleted event {evt_id}")
            else:
                print(f"⚠️  Failed to delete event {evt_id}: {r.status_code}")
        except Exception as e:
            print(f"⚠️  Error deleting event {evt_id}: {e}")

def main():
    print("="*80)
    print("PIK CONNECT - INVOICING + REVENUE ENGINE BACKEND TESTS")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print(f"Admin Token: {ADMIN_TOKEN[:20]}...")
    print("="*80)
    
    # Sanity check: verify admin auth
    print("\n🔍 SANITY CHECK: Verify admin authentication")
    r = requests.get(f"{BASE_URL}/auth/me", headers=headers())
    if not test("Auth sanity check", r.status_code == 200, 
                f"Status: {r.status_code}, Role: {r.json().get('user', {}).get('role')}"):
        print("❌ FATAL: Admin authentication failed. Aborting tests.")
        return
    
    user_role = r.json().get('user', {}).get('role')
    if not test("Admin role verification", user_role == "admin", f"Role: {user_role}"):
        print("❌ FATAL: User is not admin. Aborting tests.")
        return
    
    # =========================================================================
    # A. INVOICE SETTINGS
    # =========================================================================
    print("\n" + "="*80)
    print("A. INVOICE SETTINGS")
    print("="*80)
    
    # Test 1: GET invoice-settings (auto-creates defaults)
    print("\n📋 Test 1: GET /api/invoice-settings (auto-creates defaults)")
    r = requests.get(f"{BASE_URL}/invoice-settings", headers=headers())
    test("GET invoice-settings returns 200", r.status_code == 200, f"Status: {r.status_code}")
    
    if r.status_code == 200:
        settings = r.json()
        test("Default invoice_prefix is 'INV-'", 
             settings.get('invoice_prefix') == 'INV-',
             f"invoice_prefix: {settings.get('invoice_prefix')}")
        test("Default default_gst_mode is 'cgst_sgst'",
             settings.get('default_gst_mode') == 'cgst_sgst',
             f"default_gst_mode: {settings.get('default_gst_mode')}")
        test("next_number_preview starts with 'INV-'",
             settings.get('next_number_preview', '').startswith('INV-'),
             f"next_number_preview: {settings.get('next_number_preview')}")
    
    # Test 2: PUT invoice-settings (persists values)
    print("\n📋 Test 2: PUT /api/invoice-settings (persists values)")
    update_data = {
        "gstin": "29ABCDE1234F1Z5",
        "state": "Karnataka",
        "default_gst_rate": 18
    }
    r = requests.put(f"{BASE_URL}/invoice-settings", headers=headers(), json=update_data)
    test("PUT invoice-settings returns 200", r.status_code == 200, f"Status: {r.status_code}")
    
    if r.status_code == 200:
        settings = r.json()
        test("GSTIN persisted", settings.get('gstin') == '29ABCDE1234F1Z5',
             f"gstin: {settings.get('gstin')}")
        test("State persisted", settings.get('state') == 'Karnataka',
             f"state: {settings.get('state')}")
        test("Default GST rate persisted", settings.get('default_gst_rate') == 18,
             f"default_gst_rate: {settings.get('default_gst_rate')}")
    
    # =========================================================================
    # B. INVOICE CRUD + GST MATH
    # =========================================================================
    print("\n" + "="*80)
    print("B. INVOICE CRUD + GST MATH")
    print("="*80)
    
    # Test 3: POST invoice with CGST/SGST
    print("\n📋 Test 3: POST /api/invoices (CGST/SGST mode)")
    invoice_data = {
        "client": {
            "name": "Divik Sharma",
            "state": "Karnataka",
            "phone": "+919000000000"
        },
        "gst_mode": "cgst_sgst",
        "line_items": [
            {
                "description": "Wedding Photography",
                "hsn_sac": "998383",
                "qty": 1,
                "rate": 50000,
                "gst_rate": 18
            }
        ],
        "place_of_supply": "Karnataka (29)"
    }
    r = requests.post(f"{BASE_URL}/invoices", headers=headers(), json=invoice_data)
    test("POST invoice returns 200", r.status_code == 200, f"Status: {r.status_code}")
    
    invoice1 = None
    if r.status_code == 200:
        invoice1 = r.json()
        created_invoices.append(invoice1.get('invoice_id'))
        
        test("Invoice number is INV-0001 format", 
             invoice1.get('invoice_number', '').startswith('INV-'),
             f"invoice_number: {invoice1.get('invoice_number')}")
        test("Subtotal is 50000", invoice1.get('subtotal') == 50000,
             f"subtotal: {invoice1.get('subtotal')}")
        test("CGST total is 4500", invoice1.get('cgst_total') == 4500,
             f"cgst_total: {invoice1.get('cgst_total')}")
        test("SGST total is 4500", invoice1.get('sgst_total') == 4500,
             f"sgst_total: {invoice1.get('sgst_total')}")
        test("Tax total is 9000", invoice1.get('tax_total') == 9000,
             f"tax_total: {invoice1.get('tax_total')}")
        test("Total is 59000", invoice1.get('total') == 59000,
             f"total: {invoice1.get('total')}")
        test("Status is 'sent'", invoice1.get('status') == 'sent',
             f"status: {invoice1.get('status')}")
        test("Balance due is 59000", invoice1.get('balance_due') == 59000,
             f"balance_due: {invoice1.get('balance_due')}")
        test("Amount in words is present", 
             invoice1.get('amount_in_words') is not None and len(invoice1.get('amount_in_words', '')) > 0,
             f"amount_in_words: {invoice1.get('amount_in_words', '')[:50]}...")
    
    # Test 4: POST invoice with IGST
    print("\n📋 Test 4: POST /api/invoices (IGST mode)")
    invoice_data_igst = {
        "client": {"name": "OutState"},
        "gst_mode": "igst",
        "line_items": [
            {
                "description": "Shoot",
                "qty": 1,
                "rate": 10000,
                "gst_rate": 18
            }
        ]
    }
    r = requests.post(f"{BASE_URL}/invoices", headers=headers(), json=invoice_data_igst)
    test("POST invoice (IGST) returns 200", r.status_code == 200, f"Status: {r.status_code}")
    
    invoice2 = None
    if r.status_code == 200:
        invoice2 = r.json()
        created_invoices.append(invoice2.get('invoice_id'))
        
        test("IGST total is 1800", invoice2.get('igst_total') == 1800,
             f"igst_total: {invoice2.get('igst_total')}")
        test("CGST total is 0", invoice2.get('cgst_total') == 0,
             f"cgst_total: {invoice2.get('cgst_total')}")
        test("SGST total is 0", invoice2.get('sgst_total') == 0,
             f"sgst_total: {invoice2.get('sgst_total')}")
        test("Total is 11800", invoice2.get('total') == 11800,
             f"total: {invoice2.get('total')}")
    
    # Test 5: GET invoice by ID
    if invoice1:
        print(f"\n📋 Test 5: GET /api/invoices/{invoice1.get('invoice_id')}")
        r = requests.get(f"{BASE_URL}/invoices/{invoice1.get('invoice_id')}", headers=headers())
        test("GET invoice by ID returns 200", r.status_code == 200, f"Status: {r.status_code}")
        if r.status_code == 200:
            inv = r.json()
            test("Invoice ID matches", inv.get('invoice_id') == invoice1.get('invoice_id'),
                 f"invoice_id: {inv.get('invoice_id')}")
    
    # Test 5b: GET invoices list
    print("\n📋 Test 5b: GET /api/invoices (list)")
    r = requests.get(f"{BASE_URL}/invoices", headers=headers())
    test("GET invoices list returns 200", r.status_code == 200, f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        test("Response has 'items' field", 'items' in data, f"Keys: {list(data.keys())}")
        test("Response has 'count' field", 'count' in data, f"count: {data.get('count')}")
        test("Response has 'booked' field", 'booked' in data, f"booked: {data.get('booked')}")
        test("Response has 'received' field", 'received' in data, f"received: {data.get('received')}")
    
    # Test 5c: Filter by status
    print("\n📋 Test 5c: GET /api/invoices?status=sent")
    r = requests.get(f"{BASE_URL}/invoices?status=sent", headers=headers())
    test("GET invoices with status filter returns 200", r.status_code == 200, f"Status: {r.status_code}")
    
    # Test 5d: Filter by date range
    print("\n📋 Test 5d: GET /api/invoices?from=2020-01-01&to=2020-12-31")
    r = requests.get(f"{BASE_URL}/invoices?from=2020-01-01&to=2020-12-31", headers=headers())
    test("GET invoices with date filter returns 200", r.status_code == 200, f"Status: {r.status_code}")
    
    # Test 6: PATCH invoice (change line_items rate)
    if invoice1:
        print(f"\n📋 Test 6: PATCH /api/invoices/{invoice1.get('invoice_id')} (change rate to 60000)")
        patch_data = {
            "line_items": [
                {
                    "description": "Wedding Photography",
                    "hsn_sac": "998383",
                    "qty": 1,
                    "rate": 60000,
                    "gst_rate": 18
                }
            ]
        }
        r = requests.patch(f"{BASE_URL}/invoices/{invoice1.get('invoice_id')}", headers=headers(), json=patch_data)
        test("PATCH invoice returns 200", r.status_code == 200, f"Status: {r.status_code}")
        
        if r.status_code == 200:
            updated = r.json()
            # New total: 60000 + 18% = 60000 + 10800 = 70800
            test("Total recomputed to 70800", updated.get('total') == 70800,
                 f"total: {updated.get('total')}")
            test("CGST recomputed to 5400", updated.get('cgst_total') == 5400,
                 f"cgst_total: {updated.get('cgst_total')}")
            test("SGST recomputed to 5400", updated.get('sgst_total') == 5400,
                 f"sgst_total: {updated.get('sgst_total')}")
    
    # Test 7: PATCH invoice (cancel)
    if invoice2:
        print(f"\n📋 Test 7: PATCH /api/invoices/{invoice2.get('invoice_id')} (status=cancelled)")
        r = requests.patch(f"{BASE_URL}/invoices/{invoice2.get('invoice_id')}", 
                          headers=headers(), json={"status": "cancelled"})
        test("PATCH invoice to cancelled returns 200", r.status_code == 200, f"Status: {r.status_code}")
        
        if r.status_code == 200:
            cancelled = r.json()
            test("Status is 'cancelled'", cancelled.get('status') == 'cancelled',
                 f"status: {cancelled.get('status')}")
    
    # =========================================================================
    # C. PAYMENTS
    # =========================================================================
    print("\n" + "="*80)
    print("C. PAYMENTS")
    print("="*80)
    
    if invoice1:
        # Test 8: Add partial payment
        print(f"\n📋 Test 8: POST /api/invoices/{invoice1.get('invoice_id')}/payments (partial)")
        payment_data = {
            "amount": 30000,
            "method": "upi"
        }
        r = requests.post(f"{BASE_URL}/invoices/{invoice1.get('invoice_id')}/payments", 
                         headers=headers(), json=payment_data)
        test("POST payment returns 200", r.status_code == 200, f"Status: {r.status_code}")
        
        if r.status_code == 200:
            inv = r.json()
            test("Status is 'partial'", inv.get('status') == 'partial',
                 f"status: {inv.get('status')}")
            test("Amount received is 30000", inv.get('amount_received') == 30000,
                 f"amount_received: {inv.get('amount_received')}")
            # Balance due should be 70800 - 30000 = 40800
            test("Balance due is 40800", inv.get('balance_due') == 40800,
                 f"balance_due: {inv.get('balance_due')}")
        
        # Test 9: Add second payment (full payment)
        print(f"\n📋 Test 9: POST /api/invoices/{invoice1.get('invoice_id')}/payments (full)")
        payment_data2 = {
            "amount": 40800,
            "method": "bank_transfer"
        }
        r = requests.post(f"{BASE_URL}/invoices/{invoice1.get('invoice_id')}/payments", 
                         headers=headers(), json=payment_data2)
        test("POST second payment returns 200", r.status_code == 200, f"Status: {r.status_code}")
        
        payment_id = None
        if r.status_code == 200:
            inv = r.json()
            test("Status is 'paid'", inv.get('status') == 'paid',
                 f"status: {inv.get('status')}")
            test("Balance due is 0", inv.get('balance_due') == 0,
                 f"balance_due: {inv.get('balance_due')}")
            test("Amount received is 70800", inv.get('amount_received') == 70800,
                 f"amount_received: {inv.get('amount_received')}")
            
            # Get payment ID for deletion test
            if inv.get('payments') and len(inv.get('payments')) > 0:
                payment_id = inv.get('payments')[0].get('payment_id')
        
        # Test 10: Delete payment
        if payment_id:
            print(f"\n📋 Test 10: DELETE /api/invoices/{invoice1.get('invoice_id')}/payments/{payment_id}")
            r = requests.delete(f"{BASE_URL}/invoices/{invoice1.get('invoice_id')}/payments/{payment_id}", 
                               headers=headers())
            test("DELETE payment returns 200", r.status_code == 200, f"Status: {r.status_code}")
            
            if r.status_code == 200:
                inv = r.json()
                test("Amount received recalculated", inv.get('amount_received') < 70800,
                     f"amount_received: {inv.get('amount_received')}")
                test("Balance due recalculated", inv.get('balance_due') > 0,
                     f"balance_due: {inv.get('balance_due')}")
                test("Status recalculated", inv.get('status') in ['partial', 'sent'],
                     f"status: {inv.get('status')}")
    
    # =========================================================================
    # D. PDF + SHARE
    # =========================================================================
    print("\n" + "="*80)
    print("D. PDF + SHARE (shareable link)")
    print("="*80)
    
    if invoice1:
        # Test 11: Get PDF
        print(f"\n📋 Test 11: GET /api/invoices/{invoice1.get('invoice_id')}/pdf")
        r = requests.get(f"{BASE_URL}/invoices/{invoice1.get('invoice_id')}/pdf", headers=headers())
        test("GET invoice PDF returns 200", r.status_code == 200, f"Status: {r.status_code}")
        test("Content-Type is application/pdf", 
             r.headers.get('Content-Type', '').startswith('application/pdf'),
             f"Content-Type: {r.headers.get('Content-Type')}")
        test("PDF body length > 1000 bytes", len(r.content) > 1000,
             f"PDF size: {len(r.content)} bytes")
        
        # Test 12: Share invoice
        print(f"\n📋 Test 12: POST /api/invoices/{invoice1.get('invoice_id')}/share")
        r = requests.post(f"{BASE_URL}/invoices/{invoice1.get('invoice_id')}/share", 
                         headers=headers(), json={"enabled": True})
        test("POST share returns 200", r.status_code == 200, f"Status: {r.status_code}")
        
        share_token = None
        if r.status_code == 200:
            inv = r.json()
            share_url = inv.get('share_url', '')
            test("share_url is present", len(share_url) > 0, f"share_url: {share_url}")
            test("share_url ends with /i/<token>", '/i/' in share_url,
                 f"share_url: {share_url}")
            
            # Extract token from share_url
            if '/i/' in share_url:
                share_token = share_url.split('/i/')[-1]
        
        # Test 13: Public invoice view
        if share_token:
            print(f"\n📋 Test 13: GET /api/public/invoices/{share_token} (NO auth)")
            r = requests.get(f"{BASE_URL}/public/invoices/{share_token}")
            test("GET public invoice returns 200", r.status_code == 200, f"Status: {r.status_code}")
            
            if r.status_code == 200:
                pub_inv = r.json()
                test("Public invoice has invoice_number", 'invoice_number' in pub_inv,
                     f"invoice_number: {pub_inv.get('invoice_number')}")
                test("Public invoice has total", 'total' in pub_inv,
                     f"total: {pub_inv.get('total')}")
        
        # Test 14: Public invoice PDF
        if share_token:
            print(f"\n📋 Test 14: GET /api/public/invoices/{share_token}/pdf (NO auth)")
            r = requests.get(f"{BASE_URL}/public/invoices/{share_token}/pdf")
            test("GET public invoice PDF returns 200", r.status_code == 200, f"Status: {r.status_code}")
            test("Content-Type is application/pdf", 
                 r.headers.get('Content-Type', '').startswith('application/pdf'),
                 f"Content-Type: {r.headers.get('Content-Type')}")
        
        # Test 15: Invalid token and disabled share
        print("\n📋 Test 15: GET /api/public/invoices/deadbeef-invalid-token (NO auth)")
        r = requests.get(f"{BASE_URL}/public/invoices/deadbeef-invalid-token")
        test("GET public invoice with invalid token returns 404", r.status_code == 404,
             f"Status: {r.status_code}")
        
        # Disable share
        print(f"\n📋 Test 15b: POST /api/invoices/{invoice1.get('invoice_id')}/share (enabled=false)")
        r = requests.post(f"{BASE_URL}/invoices/{invoice1.get('invoice_id')}/share", 
                         headers=headers(), json={"enabled": False})
        test("POST share disabled returns 200", r.status_code == 200, f"Status: {r.status_code}")
        
        if share_token:
            print(f"\n📋 Test 15c: GET /api/public/invoices/{share_token} (after disabled)")
            r = requests.get(f"{BASE_URL}/public/invoices/{share_token}")
            test("GET public invoice after disabled returns 404", r.status_code == 404,
                 f"Status: {r.status_code}")
    
    # =========================================================================
    # E. REVENUE ENGINE + DE-DUPLICATION (CRITICAL)
    # =========================================================================
    print("\n" + "="*80)
    print("E. REVENUE ENGINE + DE-DUPLICATION (CRITICAL)")
    print("="*80)
    
    # Test 16: Create a gallery with value
    print("\n📋 Test 16: POST /api/events (create gallery with value)")
    event_data = {
        "name": "Portrait Shoot",
        "category": "event",
        "value": 20000
    }
    r = requests.post(f"{BASE_URL}/events", headers=headers(), json=event_data)
    test("POST event returns 200", r.status_code == 200, f"Status: {r.status_code}")
    
    event_id = None
    if r.status_code == 200:
        event = r.json()
        event_id = event.get('event_id')
        created_events.append(event_id)
        test("Event ID is present", event_id is not None, f"event_id: {event_id}")
    
    # Test 17: Revenue summary (gallery should appear)
    print("\n📋 Test 17: GET /api/revenue/summary?period=all (before invoice)")
    r = requests.get(f"{BASE_URL}/revenue/summary?period=all", headers=headers())
    test("GET revenue summary returns 200", r.status_code == 200, f"Status: {r.status_code}")
    
    revenue_before = None
    if r.status_code == 200:
        revenue_before = r.json()
        test("Response has 'booked' field", 'booked' in revenue_before,
             f"booked: {revenue_before.get('booked')}")
        test("Response has 'collected' field", 'collected' in revenue_before,
             f"collected: {revenue_before.get('collected')}")
        test("Response has 'pending' field", 'pending' in revenue_before,
             f"pending: {revenue_before.get('pending')}")
        test("Response has 'invoice_count' field", 'invoice_count' in revenue_before,
             f"invoice_count: {revenue_before.get('invoice_count')}")
        test("Response has 'gallery_count' field", 'gallery_count' in revenue_before,
             f"gallery_count: {revenue_before.get('gallery_count')}")
        test("Response has 'by_source' field", 'by_source' in revenue_before,
             f"by_source keys: {list(revenue_before.get('by_source', {}).keys())}")
        test("Response has 'monthly' field (12 months)", 
             'monthly' in revenue_before and len(revenue_before.get('monthly', [])) == 12,
             f"monthly length: {len(revenue_before.get('monthly', []))}")
        test("Response has 'all_time' field", 'all_time' in revenue_before,
             f"all_time: {revenue_before.get('all_time')}")
        test("Response has 'period' field", 'period' in revenue_before,
             f"period: {revenue_before.get('period')}")
        test("Response has 'from' field", 'from' in revenue_before,
             f"from: {revenue_before.get('from')}")
        test("Response has 'to' field", 'to' in revenue_before,
             f"to: {revenue_before.get('to')}")
        
        # Check gallery appears in by_source
        by_source = revenue_before.get('by_source', {})
        galleries = by_source.get('galleries', {})
        test("Gallery appears in by_source.galleries", galleries.get('count', 0) > 0,
             f"galleries.count: {galleries.get('count')}, booked: {galleries.get('booked')}, collected: {galleries.get('collected')}")
        
        # Gallery value should be in booked and collected (uninvoiced galleries are treated as received)
        print(f"   📊 Before invoice: booked={revenue_before.get('booked')}, collected={revenue_before.get('collected')}")
        print(f"   📊 Galleries: count={galleries.get('count')}, booked={galleries.get('booked')}, collected={galleries.get('collected')}")
    
    # Test 18: Create invoice linked to gallery
    if event_id:
        print(f"\n📋 Test 18: POST /api/invoices (linked to event_id={event_id})")
        invoice_data_linked = {
            "client": {"name": "Portrait Client"},
            "event_id": event_id,
            "gst_mode": "none",
            "line_items": [
                {
                    "description": "Portrait",
                    "qty": 1,
                    "rate": 20000,
                    "gst_rate": 0
                }
            ]
        }
        r = requests.post(f"{BASE_URL}/invoices", headers=headers(), json=invoice_data_linked)
        test("POST invoice with event_id returns 200", r.status_code == 200, f"Status: {r.status_code}")
        
        invoice_linked = None
        if r.status_code == 200:
            invoice_linked = r.json()
            created_invoices.append(invoice_linked.get('invoice_id'))
            test("Invoice total is 20000", invoice_linked.get('total') == 20000,
                 f"total: {invoice_linked.get('total')}")
            test("Invoice event_id is set", invoice_linked.get('event_id') == event_id,
                 f"event_id: {invoice_linked.get('event_id')}")
    
    # Test 19: Revenue summary (gallery should be superseded - CRITICAL DE-DUP TEST)
    print("\n📋 Test 19: GET /api/revenue/summary?period=all (after invoice - DE-DUP CHECK)")
    r = requests.get(f"{BASE_URL}/revenue/summary?period=all", headers=headers())
    test("GET revenue summary returns 200", r.status_code == 200, f"Status: {r.status_code}")
    
    if r.status_code == 200 and revenue_before:
        revenue_after = r.json()
        by_source_after = revenue_after.get('by_source', {})
        galleries_after = by_source_after.get('galleries', {})
        invoices_after = by_source_after.get('invoices', {})
        
        print(f"   📊 After invoice: booked={revenue_after.get('booked')}, collected={revenue_after.get('collected')}")
        print(f"   📊 Galleries: count={galleries_after.get('count')}, booked={galleries_after.get('booked')}, collected={galleries_after.get('collected')}")
        print(f"   📊 Invoices: count={invoices_after.get('count')}, booked={invoices_after.get('booked')}, collected={invoices_after.get('collected')}")
        
        # CRITICAL: Gallery must be superseded (count should drop)
        test("Gallery is SUPERSEDED (count drops to 0 or decreases)", 
             galleries_after.get('count', 0) < revenue_before.get('by_source', {}).get('galleries', {}).get('count', 0),
             f"Before: {revenue_before.get('by_source', {}).get('galleries', {}).get('count')}, After: {galleries_after.get('count')}")
        
        # CRITICAL: No double counting - total booked should NOT increase by another 20000
        booked_before = revenue_before.get('booked', 0)
        booked_after = revenue_after.get('booked', 0)
        booked_diff = booked_after - booked_before
        test("NO DOUBLE COUNTING - booked did not increase by 20000", 
             abs(booked_diff) < 20000,
             f"Booked before: {booked_before}, after: {booked_after}, diff: {booked_diff}")
        
        # Since the linked invoice is unpaid, collected should DROP (gallery was treated as received, invoice is not)
        collected_before = revenue_before.get('collected', 0)
        collected_after = revenue_after.get('collected', 0)
        collected_diff = collected_after - collected_before
        test("Collected DROPPED (unpaid invoice replaces paid gallery)", 
             collected_diff < 0,
             f"Collected before: {collected_before}, after: {collected_after}, diff: {collected_diff}")
    
    # Test 20: Revenue records
    print("\n📋 Test 20: GET /api/revenue/records?period=all")
    r = requests.get(f"{BASE_URL}/revenue/records?period=all", headers=headers())
    test("GET revenue records returns 200", r.status_code == 200, f"Status: {r.status_code}")
    
    if r.status_code == 200:
        records = r.json()
        test("Response has 'items' field", 'items' in records,
             f"items count: {len(records.get('items', []))}")
        test("Response has 'booked' field", 'booked' in records,
             f"booked: {records.get('booked')}")
        test("Response has 'collected' field", 'collected' in records,
             f"collected: {records.get('collected')}")
        test("Response has 'pending' field", 'pending' in records,
             f"pending: {records.get('pending')}")
        
        # Check record structure
        items = records.get('items', [])
        if items:
            first = items[0]
            test("Record has 'type' field", 'type' in first,
                 f"type: {first.get('type')}")
            test("Record has 'ref_id' field", 'ref_id' in first,
                 f"ref_id: {first.get('ref_id')}")
            test("Record has 'title' field", 'title' in first,
                 f"title: {first.get('title')}")
            test("Record has 'date' field", 'date' in first,
                 f"date: {first.get('date')}")
            test("Record has 'booked' field", 'booked' in first,
                 f"booked: {first.get('booked')}")
            test("Record has 'collected' field", 'collected' in first,
                 f"collected: {first.get('collected')}")
            test("Record has 'status' field", 'status' in first,
                 f"status: {first.get('status')}")
    
    # Test 21: Period filters
    print("\n📋 Test 21a: GET /api/revenue/summary?period=this_month")
    r = requests.get(f"{BASE_URL}/revenue/summary?period=this_month", headers=headers())
    test("GET revenue summary (this_month) returns 200", r.status_code == 200, f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        test("Period is 'this_month'", data.get('period') == 'this_month',
             f"period: {data.get('period')}")
    
    print("\n📋 Test 21b: GET /api/revenue/summary?period=this_year")
    r = requests.get(f"{BASE_URL}/revenue/summary?period=this_year", headers=headers())
    test("GET revenue summary (this_year) returns 200", r.status_code == 200, f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        test("Period is 'this_year'", data.get('period') == 'this_year',
             f"period: {data.get('period')}")
    
    print("\n📋 Test 21c: GET /api/revenue/summary?period=custom&from=2020-01-01&to=2020-12-31")
    r = requests.get(f"{BASE_URL}/revenue/summary?period=custom&from=2020-01-01&to=2020-12-31", headers=headers())
    test("GET revenue summary (custom range) returns 200", r.status_code == 200, f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        test("Period is 'custom'", data.get('period') == 'custom',
             f"period: {data.get('period')}")
        test("No data in 2020 range (near-zero)", 
             data.get('booked', 0) == 0 or data.get('booked', 0) < 100,
             f"booked: {data.get('booked')}")
    
    # =========================================================================
    # F. REGRESSION
    # =========================================================================
    print("\n" + "="*80)
    print("F. REGRESSION")
    print("="*80)
    
    # Test 22: Existing gallery flow unaffected
    print("\n📋 Test 22: POST /api/events (regression - existing gallery flow)")
    event_data_regression = {
        "name": "Regression Event",
        "category": "event"
    }
    r = requests.post(f"{BASE_URL}/events", headers=headers(), json=event_data_regression)
    test("POST event (regression) returns 200", r.status_code == 200, f"Status: {r.status_code}")
    
    if r.status_code == 200:
        event = r.json()
        created_events.append(event.get('event_id'))
        test("Event created successfully", event.get('event_id') is not None,
             f"event_id: {event.get('event_id')}")
    
    # =========================================================================
    # CLEANUP
    # =========================================================================
    cleanup()
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total tests: {test_count}")
    print(f"✅ Passed: {pass_count}")
    print(f"❌ Failed: {fail_count}")
    print(f"Success rate: {(pass_count/test_count*100):.1f}%")
    print("="*80)
    
    if fail_count == 0:
        print("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {fail_count} TEST(S) FAILED")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        cleanup()
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        cleanup()
        sys.exit(1)
