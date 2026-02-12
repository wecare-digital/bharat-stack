"""
Subscribe all webhook fields for App 2 (Manish Agarwal / WABA2 +919903300044)
App ID: 1224334845952721
"""
import json, urllib.request, urllib.error, urllib.parse, boto3, hashlib, hmac

APP_ID = '1224334845952721'
APP_SECRET = 'c661642ea55355d9abd84105f6ffb236'
CALLBACK_URL = 'https://api.wecare.digital/whatsapp-calling'
VERIFY_TOKEN = 'wecare_calling_verify_2026'
WABA2_ID = '1633959101297902'

FIELDS = 'account_alerts,account_review_update,account_settings_update,account_update,automatic_events,business_capability_update,business_status_update,calls,flows,group_lifecycle_update,group_participants_update,group_settings_update,group_status_update,history,message_template_components_update,message_template_quality_update,message_template_status_update,messages,partner_solutions,payment_configuration_update,phone_number_name_update,phone_number_quality_update,security,smb_app_state_sync,smb_message_echoes,template_category_update,template_correct_category_detection,tracking_events,user_preferences'

# Get WABA2 system user token
secrets = boto3.client('secretsmanager', region_name='us-east-1')
raw = secrets.get_secret_value(SecretId='wecare/meta-system-user-token')['SecretString']
try:
    secret_data = json.loads(raw)
except json.JSONDecodeError:
    secret_data = {}
    for part in raw.strip().strip('{}').split(','):
        if ':' in part:
            k, v = part.strip().split(':', 1)
            secret_data[k.strip().strip('"').strip("'")] = v.strip().strip('"').strip("'")
SYS_TOKEN = secret_data.get('access_token_waba2', '').strip()


def make_proof(token):
    return hmac.new(APP_SECRET.encode(), token.encode(), hashlib.sha256).hexdigest()


def api_call(url, token, method='GET', data=None):
    proof = make_proof(token)
    sep = '&' if '?' in url else '?'
    url = f'{url}{sep}appsecret_proof={proof}'
    headers = {'Authorization': f'Bearer {token}'}
    encoded = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=encoded, headers=headers, method=method)
    if data:
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ''
        return {'error': True, 'status': e.code, 'detail': body}


# Step 1: Get app access token
print('--- GET APP TOKEN ---')
try:
    url = f'https://graph.facebook.com/oauth/access_token?client_id={APP_ID}&client_secret={APP_SECRET}&grant_type=client_credentials'
    with urllib.request.urlopen(url, timeout=15) as r:
        app_token = json.loads(r.read())['access_token']
    print(f'  App token: {app_token[:25]}... ({len(app_token)} chars)')
except urllib.error.HTTPError as e:
    print(f'  Failed ({e.code}): {e.read().decode()[:300]}')
    app_token = None

if not app_token:
    print('  Cannot get app token, exiting')
    exit(1)

# Step 2: Check current subscriptions with app token
print('\n--- CHECK CURRENT ---')
result = api_call(f'https://graph.facebook.com/v20.0/{APP_ID}/subscriptions', app_token)
if result.get('error'):
    print(f'  Error: {json.dumps(result)[:500]}')
else:
    subs = result.get('data', [])
    if subs:
        for s in subs:
            flds = [f.get('name', '') for f in s.get('fields', [])]
            print(f"  Object: {s.get('object', '')} | Active: {s.get('active', False)} | Fields ({len(flds)})")
            for f in sorted(flds):
                print(f"    - {f}")
    else:
        print('  No subscriptions yet')

# Step 3: Subscribe with app token
print(f'\n--- SUBSCRIBE APP-LEVEL ({len(FIELDS.split(","))} fields) ---')
result = api_call(f'https://graph.facebook.com/v20.0/{APP_ID}/subscriptions', app_token, 'POST', {
    'object': 'whatsapp_business_account',
    'callback_url': CALLBACK_URL,
    'verify_token': VERIFY_TOKEN,
    'fields': FIELDS,
    'include_values': 'true',
})
if result.get('success'):
    print(f'  ✅ SUCCESS — {len(FIELDS.split(","))} fields subscribed!')
else:
    print(f'  Result: {json.dumps(result)[:600]}')

# Step 4: Also WABA-level with system user token
print(f'\n--- SUBSCRIBE WABA-LEVEL ({WABA2_ID}) ---')
result = api_call(f'https://graph.facebook.com/v20.0/{WABA2_ID}/subscribed_apps', SYS_TOKEN, 'POST', {
    'subscribed_fields': FIELDS,
})
if result.get('success'):
    print(f'  ✅ WABA-level SUCCESS!')
else:
    print(f'  Result: {json.dumps(result)[:600]}')

# Step 5: Verify
print('\n--- VERIFY APP-LEVEL ---')
result = api_call(f'https://graph.facebook.com/v20.0/{APP_ID}/subscriptions', app_token)
if not result.get('error'):
    subs = result.get('data', [])
    for s in subs:
        flds = [f.get('name', '') for f in s.get('fields', [])]
        print(f"  Object: {s.get('object', '')} | Active: {s.get('active', False)} | Fields ({len(flds)})")
        for f in sorted(flds):
            print(f"    ✅ {f}")
else:
    print(f'  Error: {json.dumps(result)[:300]}')

print('\nDONE')
