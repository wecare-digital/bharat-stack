"""
Airtel 403 Diagnostic Script
=============================
Tests all Airtel API endpoints to identify where 403 errors occur.

Run: python scripts/test-airtel-403.py

This script tests:
1. Direct Airtel API calls (SMS, C2C, OBD) with auth
2. Lambda endpoints via API Gateway
3. CDR webhook endpoint
"""

import json
import time
import base64
import hashlib
import hmac
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ============================================================
# Configuration
# ============================================================
API_BASE = "https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod"

# Airtel API hosts
AIRTEL_SMS_HOST = "iqmessaging.airtel.in"
AIRTEL_VOICE_HOST = "iqvoice.airtel.in"
AIRTEL_TELEPHONY_HOST = "iqtelephony.airtel.in"
AIRTEL_OPENAPI_HOST = "openapi.airtel.in"

# Credentials (from create-airtel-secrets.ps1)
SMS_CUSTOMER_ID = "WECAREDIG_v6J1SyLLI2auy7Lw9JrW"
SMS_AUTH_TOKEN = "V0VDQVJFRElHX3Y2SjFTeUxMSTJhdXk3THc5SnJXOnNOJH58KElAMTEy"

C2C_APP_ID = "WECAREDIG_fD4BKqUbC8k90jNrPR0n"
C2C_API_KEY = "u^5KLtH@11"
C2C_CALLER_ID = "8047311032"

OBD_CUSTOMER_ID = "WECAREDIG_v6J1SyLLI2auy7Lw9JrW"
OBD_AUTH = "RElHSVRBTF9WSV9MS2lwdFBzTTZqWHBtQ0NtNWduSDpec3g3OzF5fUReciQ7X20/S2p5VlZW"
OBD_APP_ID = "IRONMAN"

# Test phone numbers (use your own)
TEST_FROM = "8130078559"
TEST_TO = "7080003969"

# Airtel IPs to note
AIRTEL_IPS = ["125.19.17.212", "125.17.6.54", "122.187.47.153"]

# ============================================================
# Helpers
# ============================================================
PASS = "\033[92m✓ PASS\033[0m"
FAIL = "\033[91m✗ FAIL\033[0m"
WARN = "\033[93m⚠ WARN\033[0m"
INFO = "\033[94mℹ INFO\033[0m"

results = []

def _request(url, method="GET", body=None, headers=None, timeout=15):
    """Make HTTP request and return (status_code, response_body, error)."""
    try:
        data = json.dumps(body).encode('utf-8') if body else None
        req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8')), None
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode('utf-8')
        except:
            pass
        return e.code, error_body, str(e)
    except Exception as e:
        return 0, None, str(e)


def _generate_hmac_headers(body_str, app_id, api_key):
    """Generate HMAC-SHA256 auth headers for Airtel Kong API."""
    x_date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
    body_hash = hashlib.sha256(body_str.encode('utf-8')).digest()
    body_hash_b64 = base64.b64encode(body_hash).decode('utf-8')
    digest = f'SHA-256={body_hash_b64}'
    signature_raw = f'x-date: {x_date}\ndigest: {digest}'
    signature = hmac.new(api_key.encode('utf-8'), signature_raw.encode('utf-8'), hashlib.sha256).digest()
    signature_b64 = base64.b64encode(signature).decode('utf-8')
    authorization = f'hmac username="{app_id}", algorithm="hmac-sha256", headers="x-date digest", signature="{signature_b64}"'
    return {'Authorization': authorization, 'X-Date': x_date, 'Digest': digest, 'Content-Type': 'application/json'}


def test(name, status, response, error, expected_pass=True):
    """Log test result."""
    passed = (status == 200 or status == 201 or status == 202) if expected_pass else True
    icon = PASS if passed else FAIL
    results.append((name, passed, status, error))
    print(f"  {icon} {name}")
    print(f"       Status: {status}")
    if error and not passed:
        print(f"       Error: {error}")
    if response:
        resp_str = json.dumps(response, indent=2) if isinstance(response, dict) else str(response)[:300]
        print(f"       Response: {resp_str[:300]}")
    print()
    return passed


# ============================================================
# TEST 1: Direct Airtel SMS API
# ============================================================
def test_sms_api():
    print("=" * 60)
    print("TEST 1: Direct Airtel SMS API")
    print(f"  Host: {AIRTEL_SMS_HOST}")
    print(f"  Auth: Basic {SMS_AUTH_TOKEN[:20]}...")
    print("=" * 60)
    print()

    # 1a. Test SMS API health/connectivity
    print("  1a. Testing SMS API connectivity...")
    status, resp, err = _request(
        f"https://{AIRTEL_SMS_HOST}/api/v4/send-sms",
        method="POST",
        body={
            "customerId": SMS_CUSTOMER_ID,
            "destinationAddress": [TEST_FROM],
            "message": "Test from WECARE.DIGITAL diagnostic script",
            "sourceAddress": "WDBEEP",
            "messageType": "SERVICE_EXPLICIT",
            "dltTemplateId": "1007974344269130859",
            "entityId": "1201161991108627443"
        },
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Basic {SMS_AUTH_TOKEN}',
            'customerId': SMS_CUSTOMER_ID
        }
    )
    test("SMS API - Send SMS", status, resp, err)

    # 1b. Test with wrong auth to confirm 401 vs 403
    print("  1b. Testing SMS API with bad auth (expect 401/403)...")
    status, resp, err = _request(
        f"https://{AIRTEL_SMS_HOST}/api/v4/send-sms",
        method="POST",
        body={"customerId": "INVALID", "destinationAddress": ["0000000000"], "message": "test"},
        headers={
            'Content-Type': 'application/json',
            'Authorization': 'Basic INVALIDTOKEN',
            'customerId': 'INVALID'
        }
    )
    test("SMS API - Bad Auth (expect error)", status, resp, err, expected_pass=False)


# ============================================================
# TEST 2: Direct Airtel C2C API (HMAC)
# ============================================================
def test_c2c_api():
    print("=" * 60)
    print("TEST 2: Direct Airtel C2C API (HMAC-SHA256)")
    print(f"  Host: {AIRTEL_VOICE_HOST}")
    print(f"  App ID: {C2C_APP_ID}")
    print("=" * 60)
    print()

    payload = {
        "from": TEST_FROM,
        "to": TEST_TO,
        "caller_id": C2C_CALLER_ID,
        "to_caller_id": C2C_CALLER_ID,
        "record": False,
        "early_media": True,
        "retry": {"count": 0}
    }
    body_str = json.dumps(payload)
    headers = _generate_hmac_headers(body_str, C2C_APP_ID, C2C_API_KEY)

    print("  2a. Testing C2C API with HMAC auth...")
    status, resp, err = _request(
        f"https://{AIRTEL_VOICE_HOST}/gateway/airtel-xchange/v2/click-to-call",
        method="POST",
        body=payload,
        headers=headers
    )
    test("C2C API - Click-to-Call", status, resp, err)


# ============================================================
# TEST 3: Direct Airtel OBD API
# ============================================================
def test_obd_api():
    print("=" * 60)
    print("TEST 3: Direct Airtel OBD API")
    print(f"  Host: {AIRTEL_TELEPHONY_HOST}")
    print(f"  Customer ID: {OBD_CUSTOMER_ID}")
    print("=" * 60)
    print()

    # Test OBD CSV upload endpoint (just connectivity)
    print("  3a. Testing OBD CSV upload endpoint connectivity...")
    status, resp, err = _request(
        f"https://{AIRTEL_OPENAPI_HOST}/gateway/airtel-xchange/campaign-manager-v3/file/s3/upload?customerId={OBD_CUSTOMER_ID}&campaignType=OBD_CALL",
        method="POST",
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Basic {OBD_AUTH}',
            'app-id': OBD_APP_ID
        }
    )
    test("OBD API - CSV Upload Endpoint", status, resp, err)


# ============================================================
# TEST 4: Lambda Endpoints via API Gateway
# ============================================================
def test_lambda_endpoints():
    print("=" * 60)
    print("TEST 4: Lambda Endpoints via API Gateway")
    print(f"  Base: {API_BASE}")
    print("=" * 60)
    print()

    # 4a. CDR Webhook - POST test payload
    print("  4a. Testing CDR Webhook (POST)...")
    status, resp, err = _request(
        f"{API_BASE}/voice-cdr-webhook",
        method="POST",
        body={
            "vmSessionId": f"diag-test-{int(time.time())}",
            "clientCorrelationId": "diagnostic-test",
            "customerId": "WECAREDIG_v6J1SyLLI2auy7Lw9JrW",
            "callType": "OUTBOUND",
            "overallCallStatus": "Answered",
            "callerNumber": TEST_FROM,
            "destinationNumber": TEST_TO,
            "startTime": int(time.time() * 1000),
            "endTime": int(time.time() * 1000) + 30000,
            "duration": 30000,
            "conversationDuration": 25000,
            "hangUpStatus": "USER_INITIATED"
        },
        headers={'Content-Type': 'application/json'}
    )
    test("Lambda - CDR Webhook POST", status, resp, err)

    # 4b. CDR Webhook - GET list
    print("  4b. Testing CDR List (GET)...")
    status, resp, err = _request(f"{API_BASE}/voice-cdr-webhook?limit=5")
    test("Lambda - CDR List GET", status, resp, err)

    # 4c. C2C List
    print("  4c. Testing C2C List (GET)...")
    status, resp, err = _request(f"{API_BASE}/voice-in/c2c?limit=5")
    test("Lambda - C2C List GET", status, resp, err)

    # 4d. OBD List
    print("  4d. Testing OBD List (GET)...")
    status, resp, err = _request(f"{API_BASE}/voice-in/obd?limit=5")
    test("Lambda - OBD List GET", status, resp, err)

    # 4e. SMS-IN List
    print("  4e. Testing SMS-IN List (GET)...")
    status, resp, err = _request(f"{API_BASE}/sms-in/airtel?limit=5")
    test("Lambda - SMS-IN List GET", status, resp, err)

    # 4f. SMS-IN Templates List
    print("  4f. Testing SMS-IN Templates (GET)...")
    status, resp, err = _request(f"{API_BASE}/sms-in/airtel/templates?limit=5")
    test("Lambda - SMS-IN Templates GET", status, resp, err)

    # 4g. C2C Call via Lambda (this will call Airtel API internally)
    print("  4g. Testing C2C Call via Lambda (triggers Airtel API)...")
    status, resp, err = _request(
        f"{API_BASE}/voice-in/c2c",
        method="POST",
        body={"fromNumber": TEST_FROM, "toNumber": TEST_TO, "enableRecording": False},
        headers={'Content-Type': 'application/json'}
    )
    test("Lambda - C2C Call POST (Airtel API)", status, resp, err)

    # 4h. SMS Send via Lambda (this will call Airtel API internally)
    print("  4h. Testing SMS Send via Lambda (triggers Airtel API)...")
    status, resp, err = _request(
        f"{API_BASE}/sms-in/airtel",
        method="POST",
        body={
            "phoneNumber": TEST_FROM,
            "content": "WECARE diagnostic test - please ignore",
            "messageType": "SERVICE_EXPLICIT",
            "dltTemplateId": "1007974344269130859"
        },
        headers={'Content-Type': 'application/json'}
    )
    test("Lambda - SMS Send POST (Airtel API)", status, resp, err)

    # 4i. CDR DELETE (clear logs test)
    print("  4i. Testing CDR DELETE (clearAll)...")
    status, resp, err = _request(
        f"{API_BASE}/voice-cdr-webhook",
        method="DELETE",
        body={"clearAll": True, "hardDelete": True},
        headers={'Content-Type': 'application/json'}
    )
    test("Lambda - CDR DELETE", status, resp, err)

    # 4j. C2C DELETE (clear logs test)
    print("  4j. Testing C2C DELETE (clearAll)...")
    status, resp, err = _request(
        f"{API_BASE}/voice-in/c2c",
        method="DELETE",
        body={"clearAll": True, "hardDelete": True},
        headers={'Content-Type': 'application/json'}
    )
    test("Lambda - C2C DELETE", status, resp, err)

    # 4k. OBD DELETE (clear logs test)
    print("  4k. Testing OBD DELETE (clearAll)...")
    status, resp, err = _request(
        f"{API_BASE}/voice-in/obd",
        method="DELETE",
        body={"clearAll": True, "hardDelete": True},
        headers={'Content-Type': 'application/json'}
    )
    test("Lambda - OBD DELETE", status, resp, err)


# ============================================================
# TEST 5: DNS Resolution & Connectivity
# ============================================================
def test_connectivity():
    print("=" * 60)
    print("TEST 5: DNS & Connectivity Check")
    print("=" * 60)
    print()

    import socket
    hosts = [AIRTEL_SMS_HOST, AIRTEL_VOICE_HOST, AIRTEL_TELEPHONY_HOST, AIRTEL_OPENAPI_HOST]
    for host in hosts:
        try:
            ip = socket.gethostbyname(host)
            print(f"  {PASS} {host} -> {ip}")
        except Exception as e:
            print(f"  {FAIL} {host} -> DNS FAILED: {e}")
    print()

    print(f"  {INFO} Airtel IPs to whitelist (for webhook callbacks):")
    for ip in AIRTEL_IPS:
        print(f"       {ip}")
    print()
    print(f"  {INFO} NOTE: These IPs are for Airtel's OUTBOUND webhook callbacks.")
    print(f"       If your Lambda gets 403 calling Airtel APIs, the issue is likely:")
    print(f"       1. Auth credentials are wrong/expired")
    print(f"       2. Airtel has IP restrictions on their API (AWS Lambda IPs not whitelisted)")
    print(f"       3. Customer account is not activated/approved")
    print()


# ============================================================
# MAIN
# ============================================================
if __name__ == '__main__':
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║  AIRTEL 403 DIAGNOSTIC TEST                            ║")
    print("║  WECARE.DIGITAL                                        ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    test_connectivity()
    test_sms_api()
    test_c2c_api()
    test_obd_api()
    test_lambda_endpoints()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, p, _, _ in results if p)
    failed = sum(1 for _, p, _, _ in results if not p)
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print()

    if failed > 0:
        print("  Failed tests:")
        for name, p, status, error in results:
            if not p:
                print(f"    {FAIL} {name} (HTTP {status})")
                if error:
                    print(f"         {error[:100]}")
        print()

    # Diagnosis
    direct_403 = any(s == 403 for n, _, s, _ in results if "API -" in n)
    lambda_403 = any(s == 403 for n, _, s, _ in results if "Lambda -" in n and "Airtel API" in n)
    lambda_ok = all(p for n, p, _, _ in results if "Lambda -" in n and "List" in n)

    print("  DIAGNOSIS:")
    if direct_403:
        print(f"  {FAIL} Direct Airtel API calls return 403")
        print(f"       -> Auth credentials may be wrong or account not activated")
        print(f"       -> Contact Airtel to verify credentials and account status")
        print(f"       -> Check if your IP needs whitelisting on Airtel side")
    if lambda_403:
        print(f"  {FAIL} Lambda -> Airtel API calls return 403")
        print(f"       -> AWS Lambda IPs may not be whitelisted on Airtel side")
        print(f"       -> Consider using a NAT Gateway with a static IP")
        print(f"       -> Or ask Airtel to whitelist AWS us-east-1 IP ranges")
    if lambda_ok and not lambda_403:
        print(f"  {PASS} Lambda endpoints are working (GET/list operations)")
    if not direct_403 and not lambda_403:
        print(f"  {PASS} No 403 errors detected - APIs are accessible")
    print()
