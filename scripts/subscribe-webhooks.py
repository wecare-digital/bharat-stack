"""
Subscribe all 31 WhatsApp webhook fields for both WABAs.
Uses WABA-level /subscribed_apps endpoint (system user token).

WABA1 ID: 1912405516040025 (+919330994400 WECARE.DIGITAL) - App 2238810740192680
WABA2 ID: 1633959101297902 (+919903300044 Manish Agarwal) - App 1224334845952721
"""
import json
import urllib.request
import urllib.error
import urllib.parse
import boto3

# Get tokens from Secrets Manager
secrets = boto3.client('secretsmanager', region_name='us-east-1')
raw = secrets.get_secret_value(SecretId='wecare/meta-system-user-token')['SecretString']
raw = raw.strip().strip('{}')
parts = raw.split(',')
tokens = {}
for p in parts:
    key, val = p.strip().split(':', 1)
    tokens[key.strip()] = val.strip()

TOKEN1 = tokens.get('access_token', '')
TOKEN2 = tokens.get('access_token_waba2', '')
print(f"Token1: {TOKEN1[:15]}... ({len(TOKEN1)} chars)")
print(f"Token2: {TOKEN2[:15]}... ({len(TOKEN2)} chars)")

# WABA IDs (not App IDs)
WABA1_ID = "1912405516040025"
WABA2_ID = "1633959101297902"
API_VERSION = "v20.0"

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


def check_waba_subscriptions(waba_id, token, label):
    """Check current subscribed_apps for a WABA."""
    print(f"\n{'='*60}")
    print(f"CHECK: {label} (WABA {waba_id})")
    print(f"{'='*60}")
    url = f"https://graph.facebook.com/{API_VERSION}/{waba_id}/subscribed_apps"
    result = meta_api(url, token)
    if result.get('error'):
        print(f"  ERROR: {json.dumps(result)[:500]}")
        return []
    data = result.get('data', [])
    if not data:
        print("  No apps subscribed yet!")
        return []
    for app in data:
        link = app.get('whatsapp_business_api_data', {}).get('link', 'N/A')
        fields = app.get('subscribed_fields', [])
        print(f"  App link: {link}")
        print(f"  Subscribed fields ({len(fields)}): {', '.join(sorted(fields))}")
        return fields
    return []


def subscribe_waba(waba_id, token, label):
    """Subscribe app to WABA with all fields using POST /{waba_id}/subscribed_apps."""
    print(f"\n{'='*60}")
    print(f"SUBSCRIBE: {label} (WABA {waba_id}) → {len(ALL_FIELDS)} fields")
    print(f"{'='*60}")

    # The subscribed_apps endpoint takes override_callback_uri and subscribed_fields
    url = f"https://graph.facebook.com/{API_VERSION}/{waba_id}/subscribed_apps"
    data = {
        'subscribed_fields': ','.join(ALL_FIELDS),
    }
    result = meta_api(url, token, method='POST', data=data)

    if result.get('success'):
        print(f"  ✅ SUCCESS — All {len(ALL_FIELDS)} fields subscribed!")
    else:
        print(f"  RESULT: {json.dumps(result, indent=2)[:1000]}")
    return result


def verify_waba(waba_id, token, label):
    """Verify all fields are subscribed."""
    print(f"\n--- VERIFY: {label} ---")
    url = f"https://graph.facebook.com/{API_VERSION}/{waba_id}/subscribed_apps"
    result = meta_api(url, token)
    if result.get('error'):
        print(f"  ERROR: {json.dumps(result)[:500]}")
        return
    data = result.get('data', [])
    if not data:
        print("  ❌ No subscriptions found!")
        return
    for app in data:
        fields = set(app.get('subscribed_fields', []))
        missing = set(ALL_FIELDS) - fields
        print(f"  Subscribed: {len(fields)}/{len(ALL_FIELDS)}")
        if missing:
            print(f"  ❌ MISSING ({len(missing)}): {', '.join(sorted(missing))}")
        else:
            print(f"  ✅ ALL {len(ALL_FIELDS)} FIELDS CONFIRMED")
        # List all
        for i, f in enumerate(sorted(fields)):
            status = "✅" if f in ALL_FIELDS else "❓"
            print(f"    {i+1:2d}. {status} {f}")


# ─── Main ───
print(f"\nFields to subscribe ({len(ALL_FIELDS)}):")
for i, f in enumerate(ALL_FIELDS):
    print(f"  {i+1:2d}. {f}")

# WABA1
check_waba_subscriptions(WABA1_ID, TOKEN1, "WABA1 +919330994400")
subscribe_waba(WABA1_ID, TOKEN1, "WABA1 +919330994400")
verify_waba(WABA1_ID, TOKEN1, "WABA1 +919330994400")

# WABA2
check_waba_subscriptions(WABA2_ID, TOKEN2, "WABA2 +919903300044")
subscribe_waba(WABA2_ID, TOKEN2, "WABA2 +919903300044")
verify_waba(WABA2_ID, TOKEN2, "WABA2 +919903300044")

print(f"\n{'='*60}")
print("DONE — Both WABAs processed")
print(f"{'='*60}")
