"""Test SMS send to +91 9903300044 - Direct and via Lambda."""
import urllib.request, urllib.error, json

TARGET = "9903300044"
API_BASE = "https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod"
AIRTEL_HOST = "iqmessaging.airtel.in"
CUSTOMER_ID = "WECAREDIG_v6J1SyLLI2auy7Lw9JrW"
AUTH_TOKEN = "V0VDQVJFRElHX3Y2SjFTeUxMSTJhdXk3THc5SnJXOnNOJH58KElAMTEy"

# DLT Template: wecare selfservice ivr template
DLT_TEMPLATE_ID = "1007974344269130859"
DLT_CONTENT = "Thanks for reaching out, WECARE.DIGITAL! Please submit your request through our online Self Service Portal at https://wecare.digital/selfservice. Once we receive it, we'll review it and contact you if anything else is needed."

def send_direct():
    """Send SMS directly to Airtel API from local machine."""
    print("=" * 50)
    print("TEST 1: Direct SMS to Airtel API (local)")
    print("=" * 50)
    payload = {
        "customerId": CUSTOMER_ID,
        "destinationAddress": [TARGET],
        "message": DLT_CONTENT,
        "sourceAddress": "WDBEEP",
        "messageType": "SERVICE_IMPLICIT",
        "dltTemplateId": DLT_TEMPLATE_ID,
        "entityId": "1201161991108627443"
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Basic {AUTH_TOKEN}",
        "customerId": CUSTOMER_ID
    }
    try:
        req = urllib.request.Request(
            f"https://{AIRTEL_HOST}/api/v4/send-sms",
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            print(f"  Status: {resp.status}")
            print(f"  Response: {json.dumps(result, indent=2)}")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        print(f"  FAILED: {e.code} - {body}")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

def send_via_lambda():
    """Send SMS via Lambda endpoint."""
    print()
    print("=" * 50)
    print("TEST 2: SMS via Lambda (API Gateway)")
    print("=" * 50)
    payload = {
        "phoneNumber": TARGET,
        "content": DLT_CONTENT,
        "messageType": "SERVICE_IMPLICIT",
        "dltTemplateId": DLT_TEMPLATE_ID
    }
    try:
        req = urllib.request.Request(
            f"{API_BASE}/sms-in/airtel",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            print(f"  Status: {resp.status}")
            print(f"  Response: {json.dumps(result, indent=2)}")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        print(f"  FAILED: {e.code} - {body}")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False

if __name__ == "__main__":
    print(f"Sending test SMS to +91 {TARGET}")
    print()
    r1 = send_direct()
    r2 = send_via_lambda()
    print()
    print("=" * 50)
    print("RESULTS")
    print("=" * 50)
    print(f"  Direct (local):  {'PASS' if r1 else 'FAIL'}")
    print(f"  Via Lambda:      {'PASS' if r2 else 'FAIL (403 - Airtel blocking AWS IPs)'}")
