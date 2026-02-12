"""Full setup: update secret, subscribe webhooks, test tokens for both WABAs"""
import json, hmac, hashlib, time, urllib.request, urllib.error, urllib.parse, boto3

TOKEN1 = "EAAf0L77jdagBQgLC9Gq7baWr1jNL7zsX8mrfkTa0MvzdSd7HrOPTsCYO4N4CJWZClHJ7HMuMZCAd88PzRtSgRxtCnjUTTL08RFaVi579bvITGxCq23v7WtLEeGMfZCYN2KMRoshRxBaM7HKrgxh5x6SZBWp1VBvpRlOaRsRXmHQhDtB5WHJfh6PVt4fbSAZDZD"
TOKEN2 = "EAARZAhquUQtEBQryKXjwfmazTqjiysqrwLStdZAj57DYIe5ZCUd2yN75cauNmcnTXEOu28qvjaOGNdh7kIjx1bi7emQH0o7GRgEULkDoQql3ZCZBYIeU5V3t8Th0aTkS8UKm947jIIYHKhacZBCQxrAZAgZBiANxDnRTKuZAoJp7vhD3uIe6skmKp8vqbhSCZAgAZDZD"

APP1_ID = "2238810740192680"
APP1_SECRET = "9c146c26b6adc338472ac205b158b3d5"
APP2_ID = "1224334845952721"
APP2_SECRET = "c661642ea55355d9abd84105f6ffb236"

WABA1_ID = "1912405516040025"
WABA2_ID = "1633959101297902"
PHONE1_ID = "960395407161423"
PHONE2_ID = "997428863451102"

CALLBACK = "https://api.wecare.digital/whatsapp-calling"
VERIFY = "wecare_calling_verify_2026"

FIELDS = [
    "account_alerts","account_review_update","account_settings_update",
    "account_update","automatic_events","business_capability_update",
    "business_status_update","calls","flows","group_lifecycle_update",
    "group_participants_update","group_settings_update","group_status_update",
    "history","message_echoes","message_template_components_update",
    "message_template_quality_update","message_template_status_update",
    "messages","messaging_handovers","partner_solutions",
    "payment_configuration_update","phone_number_name_update",
    "phone_number_quality_update","security","smb_app_state_sync",
    "smb_message_echoes","template_category_update",
    "template_correct_category_detection","tracking_events","user_preferences",
]

# ── Step 1: Update Secrets Manager ──
print("=" * 50)
print("STEP 1: Update Secrets Manager")
print("=" * 50)
secrets = boto3.client('secretsmanager', region_name='us-east-1')
secrets.update_secret(SecretId='wecare/meta-system-user-token', SecretString=json.dumps({
    "access_token": TOKEN1, "access_token_waba2": TOKEN2,
    "app_secret": APP1_SECRET, "app_secret_waba2": APP2_SECRET,
}))
print("OK secret updated")

# ── Step 2: Test tokens ──
print("\n" + "=" * 50)
print("STEP 2: Test tokens")
print("=" * 50)

def api(url, token, secret, method='GET', payload=None):
    proof = hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()
    sep = '&' if '?' in url else '?'
    full = f"{url}{sep}appsecret_proof={proof}"
    h = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    d = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(full, data=d, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {'ok': True, 'data': json.loads(resp.read().decode())}
    except urllib.error.HTTPError as e:
        return {'ok': False, 'status': e.code, 'err': e.read().decode()[:300]}

r1 = api(f"https://graph.facebook.com/v20.0/{PHONE1_ID}?fields=display_phone_number,verified_name", TOKEN1, APP1_SECRET)
print(f"Token1 phone access: {r1}")
r2 = api(f"https://graph.facebook.com/v20.0/{PHONE2_ID}?fields=display_phone_number,verified_name", TOKEN2, APP2_SECRET)
print(f"Token2 phone access: {r2}")

# Test pre_accept
r1c = api(f"https://graph.facebook.com/v20.0/{PHONE1_ID}/calls", TOKEN1, APP1_SECRET, 'POST',
    {'messaging_product':'whatsapp','call_id':'test','action':'pre_accept'})
print(f"Token1 pre_accept: {r1c}")
r2c = api(f"https://graph.facebook.com/v20.0/{PHONE2_ID}/calls", TOKEN2, APP2_SECRET, 'POST',
    {'messaging_product':'whatsapp','call_id':'test','action':'pre_accept'})
print(f"Token2 pre_accept: {r2c}")


# ── Step 3: WABA-level subscriptions ──
print("\n" + "=" * 50)
print("STEP 3: WABA-level subscriptions")
print("=" * 50)
r = api(f"https://graph.facebook.com/v20.0/{WABA1_ID}/subscribed_apps", TOKEN1, APP1_SECRET, 'POST')
print(f"WABA1: {r}")
r = api(f"https://graph.facebook.com/v20.0/{WABA2_ID}/subscribed_apps", TOKEN2, APP2_SECRET, 'POST')
print(f"WABA2: {r}")

# ── Step 4: App-level subscriptions ──
print("\n" + "=" * 50)
print("STEP 4: App-level webhook subscriptions")
print("=" * 50)

def sub_app(app_id, app_secret, label):
    # Get app token
    url = f"https://graph.facebook.com/oauth/access_token?client_id={app_id}&client_secret={app_secret}&grant_type=client_credentials"
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=15) as resp:
            app_token = json.loads(resp.read().decode()).get('access_token', '')
    except:
        print(f"  {label}: could not get app token")
        return
    
    ok, fail = [], []
    for field in FIELDS:
        data = urllib.parse.urlencode({
            'object': 'whatsapp_business_account',
            'callback_url': CALLBACK, 'verify_token': VERIFY, 'fields': field,
        }).encode()
        req = urllib.request.Request(
            f"https://graph.facebook.com/v20.0/{app_id}/subscriptions",
            data=data,
            headers={'Authorization': f'Bearer {app_token}', 'Content-Type': 'application/x-www-form-urlencoded'},
            method='POST')
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                r = json.loads(resp.read().decode())
                (ok if r.get('success') else fail).append(field)
        except urllib.error.HTTPError as e:
            fail.append(field)
        time.sleep(0.2)
    print(f"{label}: {len(ok)}/{len(FIELDS)} subscribed")
    if fail:
        print(f"  Failed: {', '.join(fail)}")

sub_app(APP1_ID, APP1_SECRET, "App1 (WECARE.DIGITAL)")
sub_app(APP2_ID, APP2_SECRET, "App2 (Manish Agarwal)")

print("\nDONE")
