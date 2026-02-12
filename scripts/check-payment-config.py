"""Check payment configuration on all WABAs via Meta Graph API with appsecret_proof"""
import json, hashlib, hmac, requests

# Tokens + app secrets
TOKEN1 = 'EAAf0L77jdagBQppO7QZCuPoaiL4G76snYzvw0e8PlTjiSsKrdXKQhXcZA34xJCkFasl2LqMGkCIwru4ThtxXqOUcmYUlkmicUTsnHFg1wWbDqp0xfEuYdr92BGSB0d07iRZBY17ZCCHPwIhl19C3buqpQXxkxHEcpReI9T63xT2KF61SXrgyZCJLVPggsmwZDZD'
APP_SECRET1 = '9c146c26b6adc338472ac205b158b3d5'

TOKEN2 = 'EAARZAhquUQtEBQj7NHW8lgOctP2Icg4xSmIe7HcEnOwJyLZBWRh1R5veiJzupis4kZCKGyPDUYszGFhIDPAWwoOoPuOT1mPexvwXItE633wjer2ZCM7sw1AZBCVDpMljCJZCbSytUzoH6SKARgLajHkOlDxzoV7CP91QLCCZBzjCvZA6J187AwoiN96St1SZBPQZDZd'
APP_SECRET2 = 'c661642ea55355d9abd84105f6ffb236'

def proof(token, secret):
    return hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()

TOKENS = [
    ('T1', TOKEN1, APP_SECRET1, proof(TOKEN1, APP_SECRET1)),
    ('T2', TOKEN2, APP_SECRET2, proof(TOKEN2, APP_SECRET2)),
]

WABAS = {
    'AWS_EUM_WABA1 (9330)': '1912405516040025',
    'AWS_EUM_WABA2 (9903)': '1633959101297902',
    'META_PAY_WABA1 (9330)': '1728153881476046',
    'META_PAY_WABA2 (9903)': '761651636983279',
}

PHONES = {
    'PHONE1 (9330)': '960395407161423',
    'PHONE2 (9903)': '997428863451102',
}

BASE = 'https://graph.facebook.com/v21.0'

def api(url, token, secret_proof):
    return requests.get(url, params={'access_token': token, 'appsecret_proof': secret_proof}, timeout=15)

print("=" * 60)
print("1. WABA DETAILS")
print("=" * 60)
for label, waba_id in WABAS.items():
    for tname, token, asec, aproof in TOKENS:
        try:
            r = requests.get(f'{BASE}/{waba_id}', params={
                'access_token': token, 'appsecret_proof': aproof,
                'fields': 'id,name,currency,account_review_status'
            }, timeout=15)
            if r.status_code == 200:
                d = r.json()
                print(f"  {label}: {d.get('name','?')} | {d.get('account_review_status','?')}")
                break
            elif 'Malformed' not in r.json().get('error',{}).get('message',''):
                continue
        except: pass
    else:
        print(f"  {label}: FAILED")

print("\n" + "=" * 60)
print("2. PAYMENT CONFIGURATIONS ON EACH WABA")
print("=" * 60)
for label, waba_id in WABAS.items():
    found = False
    for tname, token, asec, aproof in TOKENS:
        try:
            r = api(f'{BASE}/{waba_id}/payment_configuration', token, aproof)
            if r.status_code == 200:
                d = r.json()
                configs = d.get('data', [])
                if configs:
                    print(f"\n  {label}: {len(configs)} config(s)")
                    for c in configs:
                        print(f"    - {json.dumps(c)}")
                else:
                    print(f"\n  {label}: NO payment configs (empty)")
                found = True
                break
            else:
                err = r.json().get('error',{}).get('message','?')[:80]
                if 'does not exist' in err or 'Unsupported' in err:
                    print(f"\n  {label}: endpoint not supported ({err})")
                    found = True
                    break
        except Exception as e:
            pass
    if not found:
        print(f"\n  {label}: FAILED with both tokens")

print("\n" + "=" * 60)
print("3. PHONE WHATSAPP_COMMERCE_SETTINGS")
print("=" * 60)
for label, phone_id in PHONES.items():
    for tname, token, asec, aproof in TOKENS:
        try:
            r = api(f'{BASE}/{phone_id}/whatsapp_commerce_settings', token, aproof)
            if r.status_code == 200:
                print(f"\n  {label}: {json.dumps(r.json(), indent=4)}")
                break
            else:
                err = r.json().get('error',{}).get('message','?')[:80]
                if tname == 'T2':
                    print(f"\n  {label}: {err}")
        except: pass
