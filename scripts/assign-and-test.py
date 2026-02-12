"""Assign WABA2 to new system user 903073549258893 and test"""
import json, hmac, hashlib, urllib.request, urllib.error, urllib.parse

TOKEN = "EAARZAhquUQtEBQtPozeJDVRgjIPWdqw3ZClrRqFXOrOtndzQaJ2YYFWHrpvdjgtiR39UfnCKfm279eo8qqR3oFab0wuB55Cl7JixzN9KOjUTnuQZAt73PKx0GZCmWCNBhtIBEeuhi9ePVSZA8Eo0ZAKAZARksv2eoQHEYf7LXlzDFZCpbxZAJ05ukoHxngJOx0gZDZD"
APP2_SECRET = "c661642ea55355d9abd84105f6ffb236"
WABA2_ID = "1633959101297902"
SU_ID = "903073549258893"
PHONE2_ID = "997428863451102"

def api(url, method='GET', payload=None, form=None):
    proof = hmac.new(APP2_SECRET.encode(), TOKEN.encode(), hashlib.sha256).hexdigest()
    sep = '&' if '?' in url else '?'
    full = f"{url}{sep}appsecret_proof={proof}"
    headers = {'Authorization': f'Bearer {TOKEN}'}
    data = None
    if payload:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(payload).encode()
    elif form:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(full, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {'error': e.code, 'detail': e.read().decode()[:500]}

# 1. Check current assigned users on WABA2
print("1. Current WABA2 assigned users:")
r = api(f"https://graph.facebook.com/v20.0/{WABA2_ID}/assigned_users?business=561498473710474")
print(f"   {json.dumps(r, indent=2)[:500]}")

# 2. Assign system user to WABA2
print("\n2. Assign system user to WABA2:")
r = api(f"https://graph.facebook.com/v20.0/{WABA2_ID}/assigned_users", 'POST',
    form={'user': SU_ID, 'tasks': '["MANAGE"]'})
print(f"   {r}")

# 3. Test send message
print("\n3. Send message test after assignment:")
r = api(f"https://graph.facebook.com/v20.0/{PHONE2_ID}/messages", 'POST', {
    'messaging_product': 'whatsapp', 'to': '919903300044',
    'type': 'text', 'text': {'body': 'token test after assign'}
})
print(f"   {r}")

# 4. Test pre_accept
print("\n4. pre_accept test after assignment:")
r = api(f"https://graph.facebook.com/v20.0/{PHONE2_ID}/calls", 'POST', {
    'messaging_product': 'whatsapp', 'call_id': 'test_fake_123', 'action': 'pre_accept',
})
print(f"   {r}")
if r.get('error') == 403 and 'permissions' in str(r.get('detail', '')).lower():
    print("   ❌ STILL 403")
else:
    print("   ✅ PERMISSIONS OK")
