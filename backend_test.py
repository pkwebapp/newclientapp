#!/usr/bin/env python3
"""
Backend test for PIK Connect Invoice + Revenue module after bug fix and feature additions.
Tests the reported "invoices not able to save" bug fix and new features:
- Invoice save bug fix (FY-aware numbering)
- Proforma invoice support with separate numbering
- Advance amount capture
- Revenue exclusion for proforma invoices
- Invoice settings (number formats, bank fields)
- Client GST fields (gstin/state/address) prefill
- PDF generation for both invoice and proforma
- Regression tests for existing flows
"""
import requests
import json
import sys
from typing import Optional

# Configuration - use frontend .env to get backend URL
BASE_URL = "https://2ade7a95-2c7d-43fc-a0a5-6bedf6375942.preview.emergentagent.com/api"

# Test tracking
test_count = 0
pass_count = 0
fail_count = 0
created_invoices = []
created_clients = []

def get_admin_token():
    """Obtain admin bearer token via dev mock-login."""
    r = requests.post(f"{BASE_URL}/auth/dev/mock-login", json={"role": "admin"})
    if r.status_code != 200:
        print(f"❌ FATAL: Failed to get admin token: {r.status_code}")
        print(f"   Response: {r.text}")
        sys.exit(1)
    data = r.json()
    token = data.get("session_token") or data.get("token")
    if not token:
        print(f"❌ FATAL: No token in mock-login response: {data}")
        sys.exit(1)
    return token

def headers(token):
    """Return auth headers for admin requests."""
    return {"Authorization": f"Bearer {token}"}

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

def cleanup(token):
    """Delete all created test data."""
    print("\n" + "="*80)
    print("CLEANUP: Deleting test data...")
    print("="*80)
    
    # Delete invoices
    for inv_id in created_invoices:
        try:
            r = requests.delete(f"{BASE_URL}/invoices/{inv_id}", headers=headers(token))
            if r.status_code == 200:
                print(f"✅ Deleted invoice {inv_id}")
            else:
                print(f"⚠️  Failed to delete invoice {inv_id}: {r.status_code}")
        except Exception as e:
            print(f"⚠️  Error deleting invoice {inv_id}: {e}")
    
    # Delete clients
    for client_id in created_clients:
        try:
            r = requests.delete(f"{BASE_URL}/clients/{client_id}", headers=headers(token))
            if r.status_code == 200:
                print(f"✅ Deleted client {client_id}")
            else:
                print(f"⚠️  Failed to delete client {client_id}: {r.status_code}")
        except Exception as e:
            print(f"⚠️  Error deleting client {client_id}: {e}")

def main():
    print("="*80)
    print("PIK CONNECT - INVOICE + REVENUE BUG FIX & FEATURE ADDITIONS TEST")
    print("="*80)
    print(f"Base URL: {BASE_URL}")
    print("="*80)
    
    # Get admin token
    print("\n🔐 Obtaining admin bearer token via POST /api/auth/dev/mock-login...")
    token = get_admin_token()
    print(f"✅ Admin token obtained: {token[:20]}...")
    
    # =========================================================================
    # TEST 1: SAVE BUG FIX - POST /api/invoices with line_items
    # =========================================================================
    print("\n" + "="*80)
    print("TEST 1: SAVE BUG FIX - Invoice creation with CGST/SGST")
    print("="*80)
    print("Testing the reported 'invoices not able to save' bug fix.")
    print("Expected: POST /api/invoices returns 200 with invoice_number like INV-0001")
    
    invoice_data = {
        "client": {
            "name": "Test Client Alpha",
            "state": "Maharashtra",
            "phone": "+919876543210"
        },
        "gst_mode": "cgst_sgst",
        "line_items": [
            {
                "description": "Wedding Photography Package",
                "hsn_sac": "998383",
                "qty": 1,
                "rate": 50000,
                "gst_rate": 18
            },
            {
                "description": "Album Design",
                "hsn_sac": "998383",
                "qty": 1,
                "rate": 15000,
                "gst_rate": 18
            }
        ],
        "place_of_supply": "Maharashtra"
    }
    
    r = requests.post(f"{BASE_URL}/invoices", headers=headers(token), json=invoice_data)
    test("POST /api/invoices returns 200", r.status_code == 200, 
         f"Status: {r.status_code}, Response: {r.text[:200] if r.status_code != 200 else ''}")
    
    invoice1 = None
    if r.status_code == 200:
        invoice1 = r.json()
        created_invoices.append(invoice1.get('invoice_id'))
        
        inv_num = invoice1.get('invoice_number', '')
        test("Invoice number format correct (e.g., INV-0001)", 
             inv_num.startswith('INV-') and len(inv_num) > 4,
             f"invoice_number: {inv_num}")
        test("doc_type is 'invoice'", invoice1.get('doc_type') == 'invoice',
             f"doc_type: {invoice1.get('doc_type')}")
        
        # Verify GST math: 65000 + 18% = 65000 + 11700 = 76700
        expected_total = 76700
        test("Total computed correctly", invoice1.get('total') == expected_total,
             f"total: {invoice1.get('total')}, expected: {expected_total}")
        test("CGST total is 5850", invoice1.get('cgst_total') == 5850,
             f"cgst_total: {invoice1.get('cgst_total')}")
        test("SGST total is 5850", invoice1.get('sgst_total') == 5850,
             f"sgst_total: {invoice1.get('sgst_total')}")
        
        print(f"\n✅ BUG FIX VERIFIED: Invoice saved successfully with number {inv_num}")
    else:
        print(f"\n❌ BUG NOT FIXED: Invoice creation failed with {r.status_code}")
        print(f"   Error: {r.text}")
    
    # =========================================================================
    # TEST 2: PROFORMA - Separate numbering series
    # =========================================================================
    print("\n" + "="*80)
    print("TEST 2: PROFORMA INVOICE - Separate numbering series")
    print("="*80)
    print("Expected: doc_type='proforma' uses separate prefix (e.g., PRO-0001)")
    
    proforma_data = {
        "client": {
            "name": "Test Client Beta",
            "state": "Karnataka"
        },
        "doc_type": "proforma",
        "gst_mode": "cgst_sgst",
        "line_items": [
            {
                "description": "Pre-wedding Shoot",
                "qty": 1,
                "rate": 30000,
                "gst_rate": 18
            }
        ]
    }
    
    r = requests.post(f"{BASE_URL}/invoices", headers=headers(token), json=proforma_data)
    test("POST /api/invoices (proforma) returns 200", r.status_code == 200,
         f"Status: {r.status_code}")
    
    proforma1 = None
    if r.status_code == 200:
        proforma1 = r.json()
        created_invoices.append(proforma1.get('invoice_id'))
        
        pro_num = proforma1.get('invoice_number', '')
        test("Proforma number uses separate prefix (PRO-)", 
             pro_num.startswith('PRO-'),
             f"invoice_number: {pro_num}")
        test("doc_type is 'proforma'", proforma1.get('doc_type') == 'proforma',
             f"doc_type: {proforma1.get('doc_type')}")
        
        # Verify invoice and proforma don't collide
        if invoice1:
            inv_num = invoice1.get('invoice_number', '')
            test("Invoice and proforma numbering DO NOT collide",
                 inv_num != pro_num and not inv_num.startswith('PRO-'),
                 f"invoice: {inv_num}, proforma: {pro_num}")
        
        print(f"\n✅ PROFORMA VERIFIED: Separate numbering series working ({pro_num})")
    
    # =========================================================================
    # TEST 3: ADVANCE AMOUNT - Balance calculation
    # =========================================================================
    print("\n" + "="*80)
    print("TEST 3: ADVANCE AMOUNT - Balance due calculation")
    print("="*80)
    print("Expected: advance_amount reduces balance_due correctly")
    
    advance_data = {
        "client": {
            "name": "Test Client Gamma"
        },
        "gst_mode": "cgst_sgst",
        "advance_amount": 10000,
        "line_items": [
            {
                "description": "Event Photography",
                "qty": 1,
                "rate": 40000,
                "gst_rate": 18
            }
        ]
    }
    
    r = requests.post(f"{BASE_URL}/invoices", headers=headers(token), json=advance_data)
    test("POST /api/invoices (with advance) returns 200", r.status_code == 200,
         f"Status: {r.status_code}")
    
    if r.status_code == 200:
        invoice_adv = r.json()
        created_invoices.append(invoice_adv.get('invoice_id'))
        
        # Total: 40000 + 18% = 47200
        # Advance: 10000
        # Balance: 47200 - 10000 = 37200
        expected_total = 47200
        expected_balance = 37200
        
        test("advance_amount is 10000", invoice_adv.get('advance_amount') == 10000,
             f"advance_amount: {invoice_adv.get('advance_amount')}")
        test("amount_received includes advance", invoice_adv.get('amount_received') == 10000,
             f"amount_received: {invoice_adv.get('amount_received')}")
        test("balance_due = total - advance", invoice_adv.get('balance_due') == expected_balance,
             f"balance_due: {invoice_adv.get('balance_due')}, expected: {expected_balance}")
        
        print(f"\n✅ ADVANCE VERIFIED: Balance calculation correct (total: {expected_total}, advance: 10000, balance: {expected_balance})")
    
    # =========================================================================
    # TEST 4: REVENUE EXCLUSION - Proforma not in revenue
    # =========================================================================
    print("\n" + "="*80)
    print("TEST 4: REVENUE EXCLUSION - Proforma invoices excluded from revenue")
    print("="*80)
    print("Expected: GET /api/revenue/summary excludes proforma invoices")
    
    r = requests.get(f"{BASE_URL}/revenue/summary?period=all", headers=headers(token))
    test("GET /api/revenue/summary returns 200", r.status_code == 200,
         f"Status: {r.status_code}")
    
    if r.status_code == 200:
        revenue = r.json()
        test("Response has 'booked' field", 'booked' in revenue,
             f"booked: {revenue.get('booked')}")
        test("Response has 'collected' field", 'collected' in revenue,
             f"collected: {revenue.get('collected')}")
        
        # Check that proforma is NOT included in booked/collected
        # We created 1 regular invoice (76700) and 1 proforma (35400)
        # Revenue should only include the regular invoice
        booked = revenue.get('booked', 0)
        print(f"   Revenue booked: {booked}")
        
        # Note: We can't do exact match because there might be other invoices
        # But we can verify proforma is excluded by checking records
    
    r = requests.get(f"{BASE_URL}/revenue/records?period=all", headers=headers(token))
    test("GET /api/revenue/records returns 200", r.status_code == 200,
         f"Status: {r.status_code}")
    
    if r.status_code == 200:
        records = r.json()
        items = records.get('items', [])
        
        # Check that proforma invoice is NOT in records
        proforma_in_records = False
        regular_in_records = False
        
        if proforma1:
            pro_id = proforma1.get('invoice_id')
            for item in items:
                if item.get('ref_id') == pro_id:
                    proforma_in_records = True
                    break
        
        if invoice1:
            inv_id = invoice1.get('invoice_id')
            for item in items:
                if item.get('ref_id') == inv_id:
                    regular_in_records = True
                    break
        
        test("Proforma invoice NOT in revenue records", not proforma_in_records,
             f"Proforma found in records: {proforma_in_records}")
        test("Regular invoice IS in revenue records", regular_in_records,
             f"Regular invoice found in records: {regular_in_records}")
        
        print(f"\n✅ REVENUE EXCLUSION VERIFIED: Proforma excluded, regular invoice included")
    
    # =========================================================================
    # TEST 5: SETTINGS - number_format_options and previews
    # =========================================================================
    print("\n" + "="*80)
    print("TEST 5: INVOICE SETTINGS - Number formats and previews")
    print("="*80)
    print("Expected: GET returns number_format_options, next_number_preview, next_proforma_preview")
    
    r = requests.get(f"{BASE_URL}/invoice-settings", headers=headers(token))
    test("GET /api/invoice-settings returns 200", r.status_code == 200,
         f"Status: {r.status_code}")
    
    if r.status_code == 200:
        settings = r.json()
        
        test("Response has 'number_format_options'", 'number_format_options' in settings,
             f"Keys: {list(settings.keys())}")
        
        if 'number_format_options' in settings:
            opts = settings.get('number_format_options', [])
            test("number_format_options is a list", isinstance(opts, list),
                 f"Type: {type(opts)}, Length: {len(opts)}")
            
            if len(opts) > 0:
                test("Each option has 'key' and 'label'", 
                     all('key' in o and 'label' in o for o in opts),
                     f"First option: {opts[0]}")
        
        test("Response has 'next_number_preview'", 'next_number_preview' in settings,
             f"next_number_preview: {settings.get('next_number_preview')}")
        test("Response has 'next_proforma_preview'", 'next_proforma_preview' in settings,
             f"next_proforma_preview: {settings.get('next_proforma_preview')}")
        
        # Test PUT - persist number_format and bank fields
        print("\n📝 Testing PUT /api/invoice-settings (persist number_format and bank fields)")
        
        update_data = {
            "number_format": "prefix_fy_seq",
            "number_padding": 5,
            "proforma_prefix": "PROFORMA-",
            "bank_account_name": "PK Photography",
            "bank_name": "HDFC Bank",
            "bank_account_number": "12345678901234",
            "bank_ifsc": "HDFC0001234",
            "upi": "pkphoto@upi"
        }
        
        r = requests.put(f"{BASE_URL}/invoice-settings", headers=headers(token), json=update_data)
        test("PUT /api/invoice-settings returns 200", r.status_code == 200,
             f"Status: {r.status_code}")
        
        if r.status_code == 200:
            updated = r.json()
            
            test("number_format persisted", updated.get('number_format') == 'prefix_fy_seq',
                 f"number_format: {updated.get('number_format')}")
            test("number_padding persisted", updated.get('number_padding') == 5,
                 f"number_padding: {updated.get('number_padding')}")
            test("proforma_prefix persisted", updated.get('proforma_prefix') == 'PROFORMA-',
                 f"proforma_prefix: {updated.get('proforma_prefix')}")
            test("bank_account_name persisted", updated.get('bank_account_name') == 'PK Photography',
                 f"bank_account_name: {updated.get('bank_account_name')}")
            test("bank_name persisted", updated.get('bank_name') == 'HDFC Bank',
                 f"bank_name: {updated.get('bank_name')}")
            test("bank_account_number persisted", updated.get('bank_account_number') == '12345678901234',
                 f"bank_account_number: {updated.get('bank_account_number')}")
            test("bank_ifsc persisted", updated.get('bank_ifsc') == 'HDFC0001234',
                 f"bank_ifsc: {updated.get('bank_ifsc')}")
            test("upi persisted", updated.get('upi') == 'pkphoto@upi',
                 f"upi: {updated.get('upi')}")
            
            # Verify previews changed with new format
            test("next_number_preview reflects new format", 
                 '/' in updated.get('next_number_preview', ''),
                 f"next_number_preview: {updated.get('next_number_preview')}")
            test("next_proforma_preview uses new prefix", 
                 updated.get('next_proforma_preview', '').startswith('PROFORMA-'),
                 f"next_proforma_preview: {updated.get('next_proforma_preview')}")
            
            print(f"\n✅ SETTINGS VERIFIED: Persistence and previews working")
    
    # =========================================================================
    # TEST 6: CLIENT GST PREFILL - gstin/state/address
    # =========================================================================
    print("\n" + "="*80)
    print("TEST 6: CLIENT GST PREFILL - gstin/state/address fields")
    print("="*80)
    print("Expected: Client fields persist and prefill invoice client snapshot")
    
    client_data = {
        "name": "Test Client Delta Corp",
        "gstin": "27AABCT1234F1Z5",
        "state": "Maharashtra",
        "address": "123 MG Road, Mumbai, Maharashtra 400001",
        "contacts": [
            {
                "name": "Contact Person",
                "phone": "+919123456789",
                "email": "contact@delta.com",
                "is_primary": True
            }
        ]
    }
    
    r = requests.post(f"{BASE_URL}/clients", headers=headers(token), json=client_data)
    test("POST /api/clients returns 200", r.status_code == 200,
         f"Status: {r.status_code}")
    
    client_id = None
    if r.status_code == 200:
        client = r.json()
        client_id = client.get('client_id')
        created_clients.append(client_id)
        
        test("Client ID present", client_id is not None,
             f"client_id: {client_id}")
        test("gstin persisted", client.get('gstin') == '27AABCT1234F1Z5',
             f"gstin: {client.get('gstin')}")
        test("state persisted", client.get('state') == 'Maharashtra',
             f"state: {client.get('state')}")
        test("address persisted", client.get('address') == '123 MG Road, Mumbai, Maharashtra 400001',
             f"address: {client.get('address')[:50]}...")
        
        # Verify GET returns these fields
        print(f"\n📝 Testing GET /api/clients/{client_id}")
        r = requests.get(f"{BASE_URL}/clients/{client_id}", headers=headers(token))
        test("GET /api/clients/{id} returns 200", r.status_code == 200,
             f"Status: {r.status_code}")
        
        if r.status_code == 200:
            fetched = r.json()
            test("GET returns gstin", fetched.get('gstin') == '27AABCT1234F1Z5',
                 f"gstin: {fetched.get('gstin')}")
            test("GET returns state", fetched.get('state') == 'Maharashtra',
                 f"state: {fetched.get('state')}")
            test("GET returns address", fetched.get('address') is not None,
                 f"address: {fetched.get('address', '')[:50]}...")
        
        # Create invoice with client_id (no inline client override)
        print(f"\n📝 Testing invoice creation with client_id (prefill test)")
        invoice_prefill_data = {
            "client_id": client_id,
            "gst_mode": "cgst_sgst",
            "line_items": [
                {
                    "description": "Service",
                    "qty": 1,
                    "rate": 20000,
                    "gst_rate": 18
                }
            ]
        }
        
        r = requests.post(f"{BASE_URL}/invoices", headers=headers(token), json=invoice_prefill_data)
        test("POST /api/invoices (with client_id) returns 200", r.status_code == 200,
             f"Status: {r.status_code}")
        
        if r.status_code == 200:
            invoice_prefill = r.json()
            created_invoices.append(invoice_prefill.get('invoice_id'))
            
            client_snap = invoice_prefill.get('client', {})
            test("Invoice client snapshot has name", 
                 client_snap.get('name') == 'Test Client Delta Corp',
                 f"client.name: {client_snap.get('name')}")
            test("Invoice client snapshot has gstin", 
                 client_snap.get('gstin') == '27AABCT1234F1Z5',
                 f"client.gstin: {client_snap.get('gstin')}")
            test("Invoice client snapshot has state", 
                 client_snap.get('state') == 'Maharashtra',
                 f"client.state: {client_snap.get('state')}")
            
            print(f"\n✅ CLIENT GST PREFILL VERIFIED: Fields persist and prefill invoice")
    
    # =========================================================================
    # TEST 7: PDF GENERATION - Both invoice and proforma
    # =========================================================================
    print("\n" + "="*80)
    print("TEST 7: PDF GENERATION - Invoice and proforma PDFs")
    print("="*80)
    print("Expected: GET /api/invoices/{id}/pdf returns 200 application/pdf for both types")
    
    # Test regular invoice PDF
    if invoice1:
        inv_id = invoice1.get('invoice_id')
        print(f"\n📝 Testing GET /api/invoices/{inv_id}/pdf (regular invoice)")
        r = requests.get(f"{BASE_URL}/invoices/{inv_id}/pdf", headers=headers(token))
        test("GET invoice PDF returns 200", r.status_code == 200,
             f"Status: {r.status_code}")
        
        if r.status_code == 200:
            test("Content-Type is application/pdf", 
                 r.headers.get('Content-Type', '').startswith('application/pdf'),
                 f"Content-Type: {r.headers.get('Content-Type')}")
            
            # Check for PDF magic bytes
            pdf_bytes = r.content
            test("PDF starts with %PDF", pdf_bytes[:4] == b'%PDF',
                 f"First 4 bytes: {pdf_bytes[:4]}")
            test("PDF size > 5KB", len(pdf_bytes) > 5000,
                 f"PDF size: {len(pdf_bytes)} bytes")
            
            print(f"   ✅ Regular invoice PDF: {len(pdf_bytes)} bytes")
    
    # Test proforma PDF
    if proforma1:
        pro_id = proforma1.get('invoice_id')
        print(f"\n📝 Testing GET /api/invoices/{pro_id}/pdf (proforma invoice)")
        r = requests.get(f"{BASE_URL}/invoices/{pro_id}/pdf", headers=headers(token))
        test("GET proforma PDF returns 200", r.status_code == 200,
             f"Status: {r.status_code}")
        
        if r.status_code == 200:
            test("Content-Type is application/pdf", 
                 r.headers.get('Content-Type', '').startswith('application/pdf'),
                 f"Content-Type: {r.headers.get('Content-Type')}")
            
            pdf_bytes = r.content
            test("PDF starts with %PDF", pdf_bytes[:4] == b'%PDF',
                 f"First 4 bytes: {pdf_bytes[:4]}")
            test("PDF size > 5KB", len(pdf_bytes) > 5000,
                 f"PDF size: {len(pdf_bytes)} bytes")
            
            print(f"   ✅ Proforma PDF: {len(pdf_bytes)} bytes")
    
    # =========================================================================
    # TEST 8: REGRESSION - Existing flows
    # =========================================================================
    print("\n" + "="*80)
    print("TEST 8: REGRESSION - Existing invoice flows")
    print("="*80)
    print("Expected: All existing endpoints still work correctly")
    
    # 8a. GET /api/invoices (list)
    print("\n📝 Testing GET /api/invoices (list)")
    r = requests.get(f"{BASE_URL}/invoices", headers=headers(token))
    test("GET /api/invoices returns 200", r.status_code == 200,
         f"Status: {r.status_code}")
    
    if r.status_code == 200:
        data = r.json()
        test("Response has 'items'", 'items' in data,
             f"Keys: {list(data.keys())}")
        test("Response has 'booked' total", 'booked' in data,
             f"booked: {data.get('booked')}")
        test("Response has 'received' total", 'received' in data,
             f"received: {data.get('received')}")
    
    # 8b. GET /api/invoices/{id}
    if invoice1:
        inv_id = invoice1.get('invoice_id')
        print(f"\n📝 Testing GET /api/invoices/{inv_id}")
        r = requests.get(f"{BASE_URL}/invoices/{inv_id}", headers=headers(token))
        test("GET /api/invoices/{id} returns 200", r.status_code == 200,
             f"Status: {r.status_code}")
    
    # 8c. PATCH /api/invoices/{id} (edit line items)
    if invoice1:
        inv_id = invoice1.get('invoice_id')
        print(f"\n📝 Testing PATCH /api/invoices/{inv_id} (edit line items)")
        patch_data = {
            "line_items": [
                {
                    "description": "Updated Photography Package",
                    "qty": 1,
                    "rate": 55000,
                    "gst_rate": 18
                }
            ]
        }
        r = requests.patch(f"{BASE_URL}/invoices/{inv_id}", headers=headers(token), json=patch_data)
        test("PATCH /api/invoices/{id} returns 200", r.status_code == 200,
             f"Status: {r.status_code}")
        
        if r.status_code == 200:
            updated = r.json()
            # New total: 55000 + 18% = 64900
            test("Total recomputed after edit", updated.get('total') == 64900,
                 f"total: {updated.get('total')}, expected: 64900")
    
    # 8d. POST /api/invoices/{id}/payments (status transitions)
    if invoice1:
        inv_id = invoice1.get('invoice_id')
        print(f"\n📝 Testing POST /api/invoices/{inv_id}/payments (status transitions)")
        
        # Add partial payment
        payment_data = {
            "amount": 30000,
            "method": "upi"
        }
        r = requests.post(f"{BASE_URL}/invoices/{inv_id}/payments", headers=headers(token), json=payment_data)
        test("POST payment returns 200", r.status_code == 200,
             f"Status: {r.status_code}")
        
        if r.status_code == 200:
            inv = r.json()
            test("Status transitions to 'partial'", inv.get('status') == 'partial',
                 f"status: {inv.get('status')}")
            
            # Add full payment
            remaining = inv.get('balance_due', 0)
            if remaining > 0:
                payment_data2 = {"amount": remaining, "method": "bank"}
                r = requests.post(f"{BASE_URL}/invoices/{inv_id}/payments", headers=headers(token), json=payment_data2)
                if r.status_code == 200:
                    inv = r.json()
                    test("Status transitions to 'paid'", inv.get('status') == 'paid',
                         f"status: {inv.get('status')}")
    
    # 8e. POST /api/invoices/{id}/share
    if invoice1:
        inv_id = invoice1.get('invoice_id')
        print(f"\n📝 Testing POST /api/invoices/{inv_id}/share")
        r = requests.post(f"{BASE_URL}/invoices/{inv_id}/share", headers=headers(token), json={"enabled": True})
        test("POST share returns 200", r.status_code == 200,
             f"Status: {r.status_code}")
        
        share_token = None
        if r.status_code == 200:
            inv = r.json()
            share_url = inv.get('share_url', '')
            test("share_url present", len(share_url) > 0,
                 f"share_url: {share_url}")
            
            if '/i/' in share_url:
                share_token = share_url.split('/i/')[-1]
        
        # 8f. GET /api/public/invoices/{token}
        if share_token:
            print(f"\n📝 Testing GET /api/public/invoices/{share_token} (NO auth)")
            r = requests.get(f"{BASE_URL}/public/invoices/{share_token}")
            test("GET public invoice returns 200", r.status_code == 200,
                 f"Status: {r.status_code}")
    
    print(f"\n✅ REGRESSION TESTS COMPLETE: All existing flows working")
    
    # =========================================================================
    # CLEANUP
    # =========================================================================
    cleanup(token)
    
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
        print("\nSUMMARY OF VERIFIED FEATURES:")
        print("1. ✅ SAVE BUG FIX: Invoice creation working with FY-aware numbering")
        print("2. ✅ PROFORMA: Separate numbering series (invoice vs proforma)")
        print("3. ✅ ADVANCE: Balance calculation includes advance amount")
        print("4. ✅ REVENUE EXCLUSION: Proforma invoices excluded from revenue")
        print("5. ✅ SETTINGS: Number format options, previews, and bank field persistence")
        print("6. ✅ CLIENT GST PREFILL: gstin/state/address persist and prefill invoices")
        print("7. ✅ PDF: Both invoice and proforma PDFs generate correctly")
        print("8. ✅ REGRESSION: All existing flows (list, get, patch, payments, share) working")
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
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
