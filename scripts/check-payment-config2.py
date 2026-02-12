"""Deep check payment config - try multiple endpoints"""
import json, hashlib, hmac, requests

TOKEN1 = 'EAAf0L77jdagBQppO7QZCuPoaiL4G76snYzvw0e8PlTjiSsKrdXKQhXcZA34xJCkFasl2LqMGkCIwru4ThtxXqOUcmYUlkmicUTsnHFg1wWbDqp0xfEuYdr92BGSB0d07iRZBY17ZCCHPwIhl19C3buqpQXxkxHEcpReI9T63xT2KF61SXrgyZCJLVPggsmwZDZD'
APP_SECRET1 = '9c146c26b6adc338472ac205b158b3d5'
PROOF1 = hmac.new(APP_SECRET1.encode(), TOKEN1.encode(), hashlib.sha256).hexdigest()

BASE = 'https://graph.facebook.com/v21.0'

def get(path, fields=None):
    params = {'access_token': TOKEN1, 'appsecret_proof': PROOF1}
    if fields: params['fields'] = fields
    r = requests.get(f'{BASE}/{path}', params=params, timeout=15)
    return r.status_code, r.json()

# WABA1 (AWS EUM) - the one that sends messages
WABA1 = '1912405516040025'
# WABA1 (Meta Payment) - the one with payment config
PAY_WABA1 = '1728153881476046'
# Phone1
PHONE1 = '960395407161423'

print("=" * 60)
print("WABA1 AWS EUM:", WABA1)
print("=" * 60)

# Try various payment-related endpoints
endpoints = [
    (f'{WABA1}', 'id,name,currency,account_review_status,on_behalf_of_business_info,ownership_type'),
    (f'{WABA1}/phone_numbers', 'id,display_phone_number,verified_name,quality_rating'),
    (f'{WABA1}/payment_configuration', None),
]

for path, fields in endpoints:
    code, data = get(path, fields)
    print(f"\n  GET {path}: {code}")
    print(f"  {json.dumps(data, indent=2)[:500]}")

print("\n" + "=" * 60)
print("META PAY WABA1:", PAY_WABA1)
print("=" * 60)

endpoints2 = [
    (f'{PAY_WABA1}', 'id,name,currency,account_review_status,on_behalf_of_business_info,ownership_type'),
    (f'{PAY_WABA1}/phone_numbers', 'id,display_phone_number,verified_name'),
    (f'{PAY_WABA1}/payment_configuration', None),
]

for path, fields in endpoints2:
    code, data = get(path, fields)
    print(f"\n  GET {path}: {code}")
    print(f"  {json.dumps(data, indent=2)[:500]}")

print("\n" + "=" * 60)
print("PHONE1:", PHONE1)
print("=" * 60)

phone_endpoints = [
    (f'{PHONE1}', 'id,display_phone_number,verified_name,quality_rating,platform_type,is_official_business_account'),
    (f'{PHONE1}/whatsapp_commerce_settings', None),
]

for path, fields in phone_endpoints:
    code, data = get(path, fields)
    print(f"\n  GET {path}: {code}")
    print(f"  {json.dumps(data, indent=2)[:500]}")
