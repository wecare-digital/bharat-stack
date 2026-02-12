"""
Subscribe all 31 webhook fields for BOTH WABAs — field by field.
App 1: 2238810740192680 (WECARE.DIGITAL / +919330994400)
App 2: 1224334845952721 (Manish Agarwal / +919903300044)
"""
import json, urllib.request, urllib.error, urllib.parse, hashlib, hmac

CALLBACK_URL = 'https://api.wecare.digital/whatsapp-calling'
VERIFY_TOKEN = 'wecare_calling_verify_2026'
API_VER = 'v20.0'

APPS = [
    {'label': 'WECARE.DIGITAL (+919330994400)', 'app_id': '2238810740192680', 'app_secret': '9c146c26b6adc338472ac205b158b3d5'},
    {'label': 'Manish Agarwal (+919903300044)', 'app_id': '1224334845952721', 'app_secret': 'c661642ea55355d9abd84105f6ffb236'},
]

ALL_FIELDS = [
    'account_alerts', 'account_review_update', 'account_settings_update', 'account_update',
    'automatic_events', 'business_capability_update', 'business_status_update', 'calls',
    'flows', 'group_lifecycle_update', 'group_participants_update', 'group_settings_update',
    'group_status_update', 'history', 'message_echoes', 'message_template_components_update',
    'message_template_quality_update', 'message_template_status_update', 'messages',
    'messaging_handovers', 'partner_solutions', 'payment_configuration_update',
    'phone_number_name_update', 'phone_number_quality_update', 'security',
    'smb_app_state_sync', 'smb_message_echoes', 'template_category_update',
    'template_correct_category_detection', 'tracking_events', 'user_preferences',
]


def get_app_token(app_id, app_secret):
    url = f'https://graph.facebook.com/oauth/access_token?client_id={app_id}&client_secret={app_secret}&grant_type=client_credentials'
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read())['access_token']


def make_proof(token, secret):
    return hmac.new(secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def api_post(url, token, secret, data):
    proof = make_proof(token, secret)
    sep = '&' if '?' in url else '?'
    full_url = f'{url}{sep}appsecret_proof={proof}'
    encoded = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(full_url, data=encoded, headers={'Authorization': f'Bearer {token}'}, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {'error': True, 'status': e.code, 'detail': e.read().decode()[:300]}


def api_get(url, token, secret):
    proof = make_proof(token, secret)
    sep = '&' if '?' in url else '?'
    full_url = f'{url}{sep}appsecret_proof={proof}'
    req = urllib.request.Request(full_url, headers={'Authorization': f'Bearer {token}'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {'error': True, 'status': e.code, 'detail': e.read().decode()[:300]}


for app in APPS:
    label = app['label']
    app_id = app['app_id']
    app_secret = app['app_secret']

    print(f'\n{"="*60}')
    print(f'  {label} (App {app_id})')
    print(f'{"="*60}')

    # Get app token
    try:
        token = get_app_token(app_id, app_secret)
        print(f'  Token: {token[:25]}...')
    except Exception as e:
        print(f'  ❌ Failed to get token: {e}')
        continue

    # Try all 31 fields at once first
    print(f'\n  [1] Subscribe all {len(ALL_FIELDS)} fields at once...')
    result = api_post(f'https://graph.facebook.com/{API_VER}/{app_id}/subscriptions', token, app_secret, {
        'object': 'whatsapp_business_account',
        'callback_url': CALLBACK_URL,
        'verify_token': VERIFY_TOKEN,
        'fields': ','.join(ALL_FIELDS),
        'include_values': 'true',
    })

    if result.get('success'):
        print(f'  ✅ All {len(ALL_FIELDS)} fields subscribed in one shot!')
    else:
        # Some fields failed — subscribe field by field
        print(f'  Bulk failed (permissions). Subscribing field by field...')
        # First subscribe the ones that work (29 known good)
        good_fields = [f for f in ALL_FIELDS if f not in ('message_echoes', 'messaging_handovers')]
        result = api_post(f'https://graph.facebook.com/{API_VER}/{app_id}/subscriptions', token, app_secret, {
            'object': 'whatsapp_business_account',
            'callback_url': CALLBACK_URL,
            'verify_token': VERIFY_TOKEN,
            'fields': ','.join(good_fields),
            'include_values': 'true',
        })
        if result.get('success'):
            print(f'  ✅ {len(good_fields)} fields subscribed')
        else:
            print(f'  Error: {json.dumps(result)[:300]}')

        # Try the 2 problematic ones individually
        for field in ('message_echoes', 'messaging_handovers'):
            result = api_post(f'https://graph.facebook.com/{API_VER}/{app_id}/subscriptions', token, app_secret, {
                'object': 'whatsapp_business_account',
                'callback_url': CALLBACK_URL,
                'verify_token': VERIFY_TOKEN,
                'fields': field,
                'include_values': 'true',
            })
            if result.get('success'):
                print(f'  ✅ {field}')
            else:
                try:
                    err = json.loads(result.get('detail', '{}')).get('error', {}).get('error_user_title', 'Permission denied')
                except Exception:
                    err = result.get('detail', 'unknown error')[:200]
                print(f'  ❌ {field} — {err}')

    # Verify
    print(f'\n  [2] Verify subscriptions...')
    result = api_get(f'https://graph.facebook.com/{API_VER}/{app_id}/subscriptions', token, app_secret)
    if not result.get('error'):
        for s in result.get('data', []):
            flds = sorted([f.get('name', '') for f in s.get('fields', [])])
            print(f'  Active: {s.get("active", False)} | Fields: {len(flds)}/{len(ALL_FIELDS)}')
            missing = sorted(set(ALL_FIELDS) - set(flds))
            if missing:
                print(f'  Missing ({len(missing)}): {", ".join(missing)}')
            else:
                print(f'  ✅ ALL {len(ALL_FIELDS)} FIELDS SUBSCRIBED')
            for f in flds:
                print(f'    ✅ {f}')
    else:
        print(f'  Verify error: {json.dumps(result)[:300]}')

print(f'\n{"="*60}')
print('DONE — Both apps processed')
print(f'{"="*60}')
