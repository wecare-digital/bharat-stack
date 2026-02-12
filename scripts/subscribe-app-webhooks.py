"""
Subscribe all WhatsApp webhook fields at the APP level.
Uses App-level /{app_id}/subscriptions endpoint with app access token.

App 1 (WECARE.DIGITAL): 2238810740192680 → WABA1 +919330994400
App 2 (Manish Agarwal):  1224334845952721 → WABA2 +919903300044

Callback URL: https://api.wecare.digital/whatsapp-calling
Verify Token: wecare_calling_verify_2026
"""
import json
import urllib.request
import urllib.error
import urllib.parse

API_VERSION = "v20.0"
CALLBACK_URL = "https://api.wecare.digital/whatsapp-calling"
VERIFY_TOKEN = "wecare_calling_verify_2026"

# App credentials
APPS = [
    {
        "label": "WECARE.DIGITAL (+919330994400)",
        "app_id": "2238810740192680",
        "app_secret": "9c146c26b6adc338472ac205b158b3d5",
    },
]

# All 31 WhatsApp Business Account webhook fields
ALL_FIELDS = [
    "account_alerts", "account_review_update", "account_settings_update", "account_update",
    "automatic_events", "business_capability_update", "business_status_update", "calls",
    "flows", "group_lifecycle_update", "group_participants_update", "group_settings_update",
    "group_status_update", "history", "message_echoes", "message_template_components_update",
    "message_template_quality_update", "message_template_status_update", "messages",
    "messaging_handovers", "partner_solutions", "payment_configuration_update",
    "phone_number_name_update", "phone_number_quality_update", "security",
    "smb_app_state_sync", "smb_message_echoes", "template_category_update",
    "template_correct_category_detection", "tracking_events", "user_preferences",
]


def get_app_token(app_id, app_secret):
    """Get app access token using client_credentials grant."""
    url = f"https://graph.facebook.com/oauth/access_token?client_id={app_id}&client_secret={app_secret}&grant_type=client_credentials"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('access_token', '')
    except Exception as e:
        print(f"  ERROR getting app token: {e}")
        return ''


def meta_api(url, token, method='GET', data=None):
    headers = {'Authorization': f'Bearer {token}'}
    encoded_data = urllib.parse.urlencode(data).encode('utf-8') if data else None
    req = urllib.request.Request(url, data=encoded_data, headers=headers, method=method)
    if data:
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        return {'error': True, 'status': e.code, 'detail': error_body}
    except Exception as e:
        return {'error': True, 'detail': str(e)}


def check_subscriptions(app_id, token, label):
    """Check current app-level webhook subscriptions."""
    print(f"\n{'='*60}")
    print(f"CHECK: {label} (App {app_id})")
    print(f"{'='*60}")
    url = f"https://graph.facebook.com/{API_VERSION}/{app_id}/subscriptions"
    result = meta_api(url, token)
    if result.get('error'):
        print(f"  ERROR: {json.dumps(result)[:500]}")
        return
    data = result.get('data', [])
    if not data:
        print("  No subscriptions found!")
        return
    for sub in data:
        obj = sub.get('object', '')
        callback = sub.get('callback_url', '')
        fields = [f.get('name', '') for f in sub.get('fields', [])]
        active = sub.get('active', False)
        print(f"  Object: {obj} | Active: {active}")
        print(f"  Callback: {callback}")
        print(f"  Fields ({len(fields)}): {', '.join(sorted(fields))}")


def subscribe_all(app_id, app_secret, token, label):
    """Subscribe to whatsapp_business_account object with all 31 fields."""
    print(f"\n{'='*60}")
    print(f"SUBSCRIBE: {label} → {len(ALL_FIELDS)} fields")
    print(f"Callback: {CALLBACK_URL}")
    print(f"{'='*60}")

    url = f"https://graph.facebook.com/{API_VERSION}/{app_id}/subscriptions"
    data = {
        'object': 'whatsapp_business_account',
        'callback_url': CALLBACK_URL,
        'verify_token': VERIFY_TOKEN,
        'fields': ','.join(ALL_FIELDS),
        'include_values': 'true',
    }
    result = meta_api(url, token, method='POST', data=data)

    if result.get('success'):
        print(f"  ✅ SUCCESS — All {len(ALL_FIELDS)} fields subscribed!")
    else:
        print(f"  RESULT: {json.dumps(result, indent=2)[:1000]}")
    return result


# ─── Main ───
print(f"Fields to subscribe ({len(ALL_FIELDS)}):")
for i, f in enumerate(ALL_FIELDS):
    print(f"  {i+1:2d}. {f}")

for app in APPS:
    label = app['label']
    app_id = app['app_id']
    app_secret = app['app_secret']

    print(f"\n>>> Getting app token for {label}...")
    token = get_app_token(app_id, app_secret)
    if not token:
        print(f"  ❌ Failed to get app token, skipping")
        continue
    print(f"  Token: {token[:20]}... ({len(token)} chars)")

    check_subscriptions(app_id, token, label)
    subscribe_all(app_id, app_secret, token, label)
    check_subscriptions(app_id, token, label)

print(f"\n{'='*60}")
print("DONE")
print(f"{'='*60}")
