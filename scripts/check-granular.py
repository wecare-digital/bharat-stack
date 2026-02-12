"""Check granular scopes — the system user needs WABA assets assigned"""
import json, hmac, hashlib, urllib.request, urllib.error

TOKEN1 = "EAAf0L77jdagBQgLC9Gq7baWr1jNL7zsX8mrfkTa0MvzdSd7HrOPTsCYO4N4CJWZClHJ7HMuMZCAd88PzRtSgRxtCnjUTTL08RFaVi579bvITGxCq23v7WtLEeGMfZCYN2KMRoshRxBaM7HKrgxh5x6SZBWp1VBvpRlOaRsRXmHQhDtB5WHJfh6PVt4fbSAZDZD"
APP1_SECRET = "9c146c26b6adc338472ac205b158b3d5"
APP1_ID = "2238810740192680"

proof = hmac.new(APP1_SECRET.encode(), f"{APP1_ID}|{APP1_SECRET}".encode(), hashlib.sha256).hexdigest()

# Full debug_token output
url = f"https://graph.facebook.com/v20.0/debug_token?input_token={TOKEN1}&access_token={APP1_ID}|{APP1_SECRET}"
req = urllib.request.Request(url)
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
        print("Full debug_token output:")
        print(json.dumps(data, indent=2))
except urllib.error.HTTPError as e:
    print(f"FAIL: {e.code} {e.read().decode()[:500]}")

# Check system user's assigned assets
print("\n\n=== System user assigned assets ===")
proof1 = hmac.new(APP1_SECRET.encode(), TOKEN1.encode(), hashlib.sha256).hexdigest()

# Get system user ID
url2 = f"https://graph.facebook.com/v20.0/me?fields=id,name&appsecret_proof={proof1}"
req2 = urllib.request.Request(url2, headers={'Authorization': f'Bearer {TOKEN1}'})
try:
    with urllib.request.urlopen(req2, timeout=15) as resp:
        me = json.loads(resp.read().decode())
        print(f"System user: {me}")
        su_id = me['id']
except urllib.error.HTTPError as e:
    print(f"FAIL: {e.read().decode()[:300]}")
    su_id = None

if su_id:
    # Check assigned pages
    url3 = f"https://graph.facebook.com/v20.0/{su_id}/assigned_pages?appsecret_proof={proof1}"
    req3 = urllib.request.Request(url3, headers={'Authorization': f'Bearer {TOKEN1}'})
    try:
        with urllib.request.urlopen(req3, timeout=15) as resp:
            print(f"Assigned pages: {resp.read().decode()}")
    except urllib.error.HTTPError as e:
        print(f"Assigned pages FAIL: {e.code} {e.read().decode()[:300]}")

    # Check business
    url4 = f"https://graph.facebook.com/v20.0/{su_id}?fields=id,name,business&appsecret_proof={proof1}"
    req4 = urllib.request.Request(url4, headers={'Authorization': f'Bearer {TOKEN1}'})
    try:
        with urllib.request.urlopen(req4, timeout=15) as resp:
            print(f"System user details: {resp.read().decode()}")
    except urllib.error.HTTPError as e:
        print(f"Details FAIL: {e.code} {e.read().decode()[:300]}")

    # Check assigned product profiles
    url5 = f"https://graph.facebook.com/v20.0/{su_id}/assigned_product_profiles?appsecret_proof={proof1}"
    req5 = urllib.request.Request(url5, headers={'Authorization': f'Bearer {TOKEN1}'})
    try:
        with urllib.request.urlopen(req5, timeout=15) as resp:
            print(f"Assigned product profiles: {resp.read().decode()}")
    except urllib.error.HTTPError as e:
        print(f"Product profiles FAIL: {e.code} {e.read().decode()[:300]}")
