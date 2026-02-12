"""Debug the /calls 403 — check permissions, try different API versions, try sending a message"""
import json, hmac, hashlib, urllib.request, urllib.error

TOKEN = "EAAf0L77jdagBQgLC9Gq7baWr1jNL7zsX8mrfkTa0MvzdSd7HrOPTsCYO4N4CJWZClHJ7HMuMZCAd88PzRtSgRxtCnjUTTL08RFaVi579bvITGxCq23v7WtLEeGMfZCYN2KMRoshRxBaM7HKrgxh5x6SZBWp1VBvpRlOaRsRXmHQhDtB5WHJfh6PVt4fbSAZDZD"
APP_SECRET = "9c146c26b6adc338472ac205b158b3d5"
PHONE_ID = "960395407161423"

def api(url, method='GET', payload=None):
    proof = hmac.new(APP_SECRET.encode(), TOKEN.encode(), hashlib.sha256).hexdigest()
    sep = '&' if '?' in url else '?'
    full = f"{url}{sep}appsecret_proof={proof}"
    headers = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(full, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {'ok': True, 'data': json.loads(resp.read().decode())}
    except urllib.error.HTTPError as e:
        return {'ok': False, 'status': e.code, 'error': e.read().decode()[:500]}

# 1. Check token identity
print("1. Token identity:")
r = api(f"https://graph.facebook.com/v20.0/me?fields=id,name")
print(f"   {r}")

# 2. Check permissions
print("\n2. Token permissions:")
r = api(f"https://graph.facebook.com/v20.0/me/permissions")
if r['ok']:
    for p in r['data'].get('data', []):
        print(f"   {p['permission']}: {p['status']}")

# 3. Try sending a simple text message (to test whatsapp_business_messaging)
print("\n3. Test send message (text to self):")
r = api(f"https://graph.facebook.com/v20.0/{PHONE_ID}/messages", 'POST', {
    'messaging_product': 'whatsapp',
    'to': '919330994400',
    'type': 'text',
    'text': {'body': 'test from api'}
})
print(f"   {r}")

# 4. Try /calls with different API versions
for ver in ['v20.0', 'v21.0', 'v22.0']:
    print(f"\n4. pre_accept with {ver}:")
    r = api(f"https://graph.facebook.com/{ver}/{PHONE_ID}/calls", 'POST', {
        'messaging_product': 'whatsapp',
        'call_id': 'test_fake',
        'action': 'pre_accept',
    })
    print(f"   {r}")

# 5. Check if calling is enabled on the phone number
print("\n5. Phone number details:")
r = api(f"https://graph.facebook.com/v20.0/{PHONE_ID}?fields=display_phone_number,verified_name,quality_rating,messaging_limit_tier,is_official_business_account,account_mode,platform_type")
print(f"   {r}")

# 6. Try GET on /calls endpoint
print("\n6. GET /calls:")
r = api(f"https://graph.facebook.com/v20.0/{PHONE_ID}/calls")
print(f"   {r}")

# 7. Check WABA details
print("\n7. WABA details:")
r = api(f"https://graph.facebook.com/v20.0/1912405516040025?fields=id,name,account_review_status,on_behalf_of_business_info,owner_business_info,message_template_namespace")
print(f"   {r}")
