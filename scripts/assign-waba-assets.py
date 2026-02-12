"""
Assign WABA assets to the system user so the token gets scoped permissions.

The system user (871324399114953) has whatsapp_business_messaging but it's NOT
scoped to any WABA. We need to assign both WABAs to this system user via the
Business Manager API.

Business ID: 382642103987922 (Wecare.Digital)
"""
import json, hmac, hashlib, urllib.request, urllib.error, urllib.parse

TOKEN1 = "EAAf0L77jdagBQgLC9Gq7baWr1jNL7zsX8mrfkTa0MvzdSd7HrOPTsCYO4N4CJWZClHJ7HMuMZCAd88PzRtSgRxtCnjUTTL08RFaVi579bvITGxCq23v7WtLEeGMfZCYN2KMRoshRxBaM7HKrgxh5x6SZBWp1VBvpRlOaRsRXmHQhDtB5WHJfh6PVt4fbSAZDZD"
TOKEN2 = "EAARZAhquUQtEBQhsTOPFsjCPZAqqnwKKHMFAOIkqdWK6GTra626rIJVeZCdONK2x3HYeS44YKnZCfZCbvBZBy20TUc1DM4oEuqZBNCVqTuPexrbsqjxZCOZAXUMq5wCjgcsiiIn3SEO2kh2b9yCjgzY1A4wKQOpVzrE7aLGJ7a4SJQeOZA7rGwGSlMRBDq9EdGrwZDZD"
APP1_SECRET = "9c146c26b6adc338472ac205b158b3d5"
APP2_SECRET = "c661642ea55355d9abd84105f6ffb236"

SYSTEM_USER_ID = "871324399114953"
BUSINESS_ID = "382642103987922"
WABA1_ID = "1912405516040025"
WABA2_ID = "1633959101297902"

def api(url, token, app_secret, method='GET', payload=None, form_data=None):
    proof = hmac.new(app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
    sep = '&' if '?' in url else '?'
    full = f"{url}{sep}appsecret_proof={proof}"
    headers = {'Authorization': f'Bearer {token}'}
    data = None
    if payload:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(payload).encode()
    elif form_data:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        data = urllib.parse.urlencode(form_data).encode()
    req = urllib.request.Request(full, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {'ok': True, 'data': json.loads(resp.read().decode())}
    except urllib.error.HTTPError as e:
        return {'ok': False, 'status': e.code, 'error': e.read().decode()[:500]}

# 1. Check current system user assigned WABAs
print("=== Current assigned WABAs ===")
r = api(f"https://graph.facebook.com/v20.0/{SYSTEM_USER_ID}/assigned_business_asset_groups", TOKEN1, APP1_SECRET)
print(f"Assigned asset groups: {json.dumps(r, indent=2)[:500]}")

# 2. Try to assign WABA1 to system user via Business Manager
print("\n=== Assign WABA1 to system user ===")
# POST /{business_id}/system_users with user, asset, tasks
r = api(
    f"https://graph.facebook.com/v20.0/{WABA1_ID}/assigned_users",
    TOKEN1, APP1_SECRET, 'POST',
    form_data={
        'user': SYSTEM_USER_ID,
        'tasks': '["MANAGE"]',
    }
)
print(f"Assign WABA1: {json.dumps(r, indent=2)[:500]}")

# 3. Try to assign WABA2 to system user
print("\n=== Assign WABA2 to system user ===")
r = api(
    f"https://graph.facebook.com/v20.0/{WABA2_ID}/assigned_users",
    TOKEN2, APP2_SECRET, 'POST',
    form_data={
        'user': SYSTEM_USER_ID,
        'tasks': '["MANAGE"]',
    }
)
print(f"Assign WABA2: {json.dumps(r, indent=2)[:500]}")

# 4. Verify — try sending a message again
print("\n=== Verify: send message on WABA1 ===")
r = api(
    f"https://graph.facebook.com/v20.0/960395407161423/messages",
    TOKEN1, APP1_SECRET, 'POST',
    payload={
        'messaging_product': 'whatsapp',
        'to': '919330994400',
        'type': 'text',
        'text': {'body': 'test asset assignment'}
    }
)
print(f"Send message WABA1: {json.dumps(r, indent=2)[:500]}")

# 5. Verify — try pre_accept
print("\n=== Verify: pre_accept on WABA1 ===")
r = api(
    f"https://graph.facebook.com/v20.0/960395407161423/calls",
    TOKEN1, APP1_SECRET, 'POST',
    payload={
        'messaging_product': 'whatsapp',
        'call_id': 'test_fake_call_id',
        'action': 'pre_accept',
    }
)
print(f"pre_accept WABA1: {json.dumps(r, indent=2)[:500]}")
