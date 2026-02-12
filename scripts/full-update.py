"""
Full update: 
1. Update Secrets Manager with latest tokens + app secrets + client tokens
2. Force Lambda cold start
3. Subscribe all webhook fields for both WABAs
4. Test tokens
"""
import boto3, json, urllib.request, urllib.error, hmac, hashlib, time

secrets = boto3.client('secretsmanager', region_name='us-east-1')
lambda_client = boto3.client('lambda', region_name='us-east-1')

# ── WABA1: +919330994400 (WECARE.DIGITAL) ──
APP1_ID = "2238810740192680"
APP1_SECRET = "9c146c26b6adc338472ac205b158b3d5"
APP1_CLIENT_TOKEN = "23ce76f16e08cd91fd5991ee737263b9"
TOKEN1 = "EAAf0L77jdagBQppO7QZCuPoaiL4G76snYzvw0e8PlTjiSsKrdXKQhXcZA34xJCkFasl2LqMGkCIwru4ThtxXqOUcmYUlkmicUTsnHFg1wWbDqp0xfEuYdr92BGSB0d07iRZBY17ZCCHPwIhl19C3buqpQXxkxHEcpReI9T63xT2KF61SXrgyZCJLVPggsmwZDZD"
WABA1_ID = "1912405516040025"
PHONE1_META_ID = "960395407161423"

# ── WABA2: +919903300044 (Manish Agarwal) ──
APP2_ID = "1224334845952721"
APP2_SECRET = "c661642ea55355d9abd84105f6ffb236"
APP2_CLIENT_TOKEN = "df12799ca982a68d16b5ff6da9baf557"
TOKEN2 = "EAARZAhquUQtEBQj7NHW8lgOctP2Icg4xSmIe7HcEnOwJyLZBWRh1R5veiJzupis4kZCKGyPDUYszGFhIDPAWwoOoPuOT1mPexvwXItE633wjer2ZCM7sw1AZBCVDpMljCJZCbSytUzoH6SKARgLajHkOlDxzoV7CP91QLCCZBzjCvZA6J187AwoiN96St1SZBPQZDZD"
WABA2_ID = "1633959101297902"
PHONE2_META_ID = "997428863451102"

CALLBACK_URL = "https://api.wecare.digital/whatsapp-calling"
VERIFY_TOKEN = "wecare_calling_verify_2026"

ALL_FIELDS = [
    "account_alerts", "account_review_update", "account_settings_update",
    "account_update", "automatic_events", "business_capability_update",
    "business_status_update", "calls", "flows", "group_lifecycle_update",
    "group_participants_update", "group_settings_update", "group_status_update",
    "history", "message_echoes", "message_template_components_update",
    "message_template_quality_update", "message_template_status_update",
    "messages", "messaging_handovers", "partner_solutions",
    "payment_configuration_update", "phone_number_name_update",
    "phone_number_quality_update", "security", "smb_app_state_sync",
    "smb_message_echoes", "template_category_update",
    "template_correct_category_detection", "tracking_events", "user_preferences",
]

def meta_get(url, token, app_secret):
    proof = hmac.new(app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
    sep = '&' if '?' in url else '?'
    full = f"{url}{sep}appsecret_proof={proof}"
    req = urllib.request.Request(full, headers={'Authorization': f'Bearer {token}'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {'error': e.code, 'detail': e.read().decode()[:300]}

def meta_post(url, token, app_secret, data=None):
    proof = hmac.new(app_secret.encode(), token.encode(), hashlib.sha256).hexdigest()
    sep = '&' if '?' in url else '?'
    full = f"{url}{sep}appsecret_proof={proof}"
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(full, data=body, headers={'Authorization': f'Bearer {token}'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {'error': e.code, 'detail': e.read().decode()[:300]}

import urllib.parse

# ═══════════════════════════════════════════════════
# STEP 1: Update Secrets Manager
# ═══════════════════════════════════════════════════
print("=" * 60)
print("STEP 1: Updating Secrets Manager")
print("=" * 60)

new_secret = json.dumps({
    "access_token": TOKEN1,
    "access_token_waba2": TOKEN2,
    "app_secret": APP1_SECRET,
    "app_secret_waba2": APP2_SECRET,
    "client_token": APP1_CLIENT_TOKEN,
    "client_token_waba2": APP2_CLIENT_TOKEN,
})
secrets.update_secret(SecretId='wecare/meta-system-user-token', SecretString=new_secret)
print("Secret updated with both tokens + app secrets + client tokens")

# Verify
v = json.loads(secrets.get_secret_value(SecretId='wecare/meta-system-user-token')['SecretString'])
print(f"  Token1: {v['access_token'][:40]}... ({len(v['access_token'])} chars)")
print(f"  Token2: {v['access_token_waba2'][:40]}... ({len(v['access_token_waba2'])} chars)")
print(f"  AppSecret1: {v['app_secret'][:10]}...")
print(f"  AppSecret2: {v['app_secret_waba2'][:10]}...")
print(f"  ClientToken1: {v.get('client_token','N/A')}")
print(f"  ClientToken2: {v.get('client_token_waba2','N/A')}")

# ═══════════════════════════════════════════════════
# STEP 2: Test both tokens
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 2: Testing tokens")
print("=" * 60)

# Test Token1 on Phone1
r1 = meta_get(f"https://graph.facebook.com/v20.0/{PHONE1_META_ID}", TOKEN1, APP1_SECRET)
if 'error' not in r1:
    print(f"  Token1 -> Phone1: OK ({r1.get('display_phone_number', r1.get('id'))})")
else:
    print(f"  Token1 -> Phone1: FAIL {r1}")

# Test Token2 on Phone2
r2 = meta_get(f"https://graph.facebook.com/v20.0/{PHONE2_META_ID}", TOKEN2, APP2_SECRET)
if 'error' not in r2:
    print(f"  Token2 -> Phone2: OK ({r2.get('display_phone_number', r2.get('id'))})")
else:
    print(f"  Token2 -> Phone2: FAIL {r2}")

# ═══════════════════════════════════════════════════
# STEP 3: Subscribe webhooks for WABA1 (App1)
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 3: Subscribe webhooks — WABA1 (App1: WECARE.DIGITAL)")
print("=" * 60)

# App-level webhook subscription
ok1 = 0
fail1 = 0
for field in ALL_FIELDS:
    data = {
        'object': 'whatsapp_business_account',
        'callback_url': CALLBACK_URL,
        'verify_token': VERIFY_TOKEN,
        'fields': field,
    }
    url = f"https://graph.facebook.com/v20.0/{APP1_ID}/subscriptions"
    r = meta_post(url, TOKEN1, APP1_SECRET, data)
    if r.get('success'):
        ok1 += 1
    else:
        fail1 += 1
        print(f"  FAIL [{field}]: {r.get('detail', r)[:120]}")

print(f"  App1 subscriptions: {ok1} OK, {fail1} failed")

# WABA-level subscription
waba1_sub = meta_post(
    f"https://graph.facebook.com/v20.0/{WABA1_ID}/subscribed_apps",
    TOKEN1, APP1_SECRET
)
print(f"  WABA1 subscribed_apps: {waba1_sub}")

# ═══════════════════════════════════════════════════
# STEP 4: Subscribe webhooks for WABA2 (App2)
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 4: Subscribe webhooks — WABA2 (App2: Manish Agarwal)")
print("=" * 60)

ok2 = 0
fail2 = 0
for field in ALL_FIELDS:
    data = {
        'object': 'whatsapp_business_account',
        'callback_url': CALLBACK_URL,
        'verify_token': VERIFY_TOKEN,
        'fields': field,
    }
    url = f"https://graph.facebook.com/v20.0/{APP2_ID}/subscriptions"
    r = meta_post(url, TOKEN2, APP2_SECRET, data)
    if r.get('success'):
        ok2 += 1
    else:
        fail2 += 1
        print(f"  FAIL [{field}]: {r.get('detail', r)[:120]}")

print(f"  App2 subscriptions: {ok2} OK, {fail2} failed")

# WABA-level subscription
waba2_sub = meta_post(
    f"https://graph.facebook.com/v20.0/{WABA2_ID}/subscribed_apps",
    TOKEN2, APP2_SECRET
)
print(f"  WABA2 subscribed_apps: {waba2_sub}")

# ═══════════════════════════════════════════════════
# STEP 5: Force Lambda cold start
# ═══════════════════════════════════════════════════
print("\n" + "=" * 60)
print("STEP 5: Force Lambda cold start")
print("=" * 60)

try:
    lambda_client.update_function_configuration(
        FunctionName='wecare-whatsapp-calling',
        Description=f'Token refresh {int(time.time())}'
    )
    print("  Lambda config updated — next invocation will cold start and load new tokens")
except Exception as e:
    print(f"  Lambda update failed: {e}")

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
