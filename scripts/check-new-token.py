"""Check new token — identity, permissions, granular scopes, send message, pre_accept"""
import json, hmac, hashlib, urllib.request, urllib.error

TOKEN = "EAARZAhquUQtEBQtPozeJDVRgjIPWdqw3ZClrRqFXOrOtndzQaJ2YYFWHrpvdjgtiR39UfnCKfm279eo8qqR3oFab0wuB55Cl7JixzN9KOjUTnuQZAt73PKx0GZCmWCNBhtIBEeuhi9ePVSZA8Eo0ZAKAZARksv2eoQHEYf7LXlzDFZCpbxZAJ05ukoHxngJOx0gZDZD"
APP2_SECRET = "c661642ea55355d9abd84105f6ffb236"
APP2_ID = "1224334845952721"
PHONE2_ID = "997428863451102"

def api(url, method='GET', payload=None):
    proof = hmac.new(APP2_SECRET.encode(), TOKEN.encode(), hashlib.sha256).hexdigest()
    sep = '&' if '?' in url else '?'
    full = f"{url}{sep}appsecret_proof={proof}"
    headers = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(full, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {'error': e.code, 'detail': e.read().decode()[:500]}

# 1. Identity
print("1. Token identity:")
print(f"   {api('https://graph.facebook.com/v20.0/me?fields=id,name')}")

# 2. Permissions
print("\n2. Permissions:")
r = api('https://graph.facebook.com/v20.0/me/permissions')
if 'data' in r:
    for p in r['data']:
        print(f"   {p['permission']}: {p['status']}")

# 3. Granular scopes via debug_token
print("\n3. Granular scopes:")
url = f"https://graph.facebook.com/v20.0/debug_token?input_token={TOKEN}&access_token={APP2_ID}|{APP2_SECRET}"
req = urllib.request.Request(url)
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
        for gs in data.get('data', {}).get('granular_scopes', []):
            scope = gs.get('scope', '')
            targets = gs.get('target_ids', [])
            print(f"   {scope}: targets={targets if targets else 'ALL'}")
except urllib.error.HTTPError as e:
    print(f"   FAIL: {e.read().decode()[:300]}")

# 4. Phone number access
print("\n4. Phone number access:")
print(f"   {api(f'https://graph.facebook.com/v20.0/{PHONE2_ID}?fields=display_phone_number,verified_name')}")

# 5. Send message test
print("\n5. Send message test:")
r = api(f'https://graph.facebook.com/v20.0/{PHONE2_ID}/messages', 'POST', {
    'messaging_product': 'whatsapp', 'to': '919903300044',
    'type': 'text', 'text': {'body': 'token test'}
})
print(f"   {r}")

# 6. pre_accept test (fake call_id — expect "call not found" if perms OK)
print("\n6. pre_accept test:")
r = api(f'https://graph.facebook.com/v20.0/{PHONE2_ID}/calls', 'POST', {
    'messaging_product': 'whatsapp', 'call_id': 'test_fake_123', 'action': 'pre_accept',
})
print(f"   {r}")
if r.get('error') == 403 and 'permissions' in str(r.get('detail', '')).lower():
    print("   ❌ STILL 403 PERMISSION ERROR")
else:
    print("   ✅ PERMISSIONS OK (any non-403 means token has access)")
