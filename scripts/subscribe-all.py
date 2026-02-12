"""
Subscribe all webhook fields for both WABAs using APP access tokens.
App-level subscriptions require: app_id|app_secret (not system user token)
WABA-level subscriptions require: system user token
"""
import urllib.request, urllib.error, urllib.parse, json, hmac, hashlib

# ── WABA1: +919330994400 (WECARE.DIGITAL) ──
APP1_ID = "2238810740192680"
APP1_SECRET = "9c146c26b6adc338472ac205b158b3d5"
TOKEN1 = "EAAf0L77jdagBQppO7QZCuPoaiL4G76snYzvw0e8PlTjiSsKrdXKQhXcZA34xJCkFasl2LqMGkCIwru4ThtxXqOUcmYUlkmicUTsnHFg1wWbDqp0xfEuYdr92BGSB0d07iRZBY17ZCCHPwIhl19C3buqpQXxkxHEcpReI9T63xT2KF61SXrgyZCJLVPggsmwZDZD"
WABA1_ID = "1912405516040025"

# ── WABA2: +919903300044 (Manish Agarwal) ──
APP2_ID = "1224334845952721"
APP2_SECRET = "c661642ea55355d9abd84105f6ffb236"
TOKEN2 = "EAARZAhquUQtEBQj7NHW8lgOctP2Icg4xSmIe7HcEnOwJyLZBWRh1R5veiJzupis4kZCKGyPDUYszGFhIDPAWwoOoPuOT1mPexvwXItE633wjer2ZCM7sw1AZBCVDpMljCJZCbSytUzoH6SKARgLajHkOlDxzoV7CP91QLCCZBzjCvZA6J187AwoiN96St1SZBPQZDZD"
WABA2_ID = "1633959101297902"

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

def post(url, token, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(url, data=body, headers={'Authorization': f'Bearer {token}'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {'error': e.code, 'detail': e.read().decode()[:200]}

def subscribe_app(app_id, app_secret, label):
    """Subscribe app-level webhooks using app access token (app_id|app_secret)."""
    app_token = f"{app_id}|{app_secret}"
    print(f"\n--- {label}: App-level subscriptions ---")
    ok, fail = 0, 0
    for field in ALL_FIELDS:
        r = post(
            f"https://graph.facebook.com/v20.0/{app_id}/subscriptions",
            app_token,
            {
                'object': 'whatsapp_business_account',
                'callback_url': CALLBACK_URL,
                'verify_token': VERIFY_TOKEN,
                'fields': field,
            }
        )
        if r.get('success'):
            ok += 1
        else:
            fail += 1
            detail = r.get('detail', str(r))[:120]
            print(f"  FAIL [{field}]: {detail}")
    print(f"  Result: {ok} OK, {fail} failed (out of {len(ALL_FIELDS)})")
    return ok, fail

def subscribe_waba(waba_id, su_token, app_secret, label):
    """Subscribe WABA-level using system user token."""
    print(f"\n--- {label}: WABA-level subscription ---")
    proof = hmac.new(app_secret.encode(), su_token.encode(), hashlib.sha256).hexdigest()
    r = post(
        f"https://graph.facebook.com/v20.0/{waba_id}/subscribed_apps?appsecret_proof={proof}",
        su_token,
        {}
    )
    print(f"  Result: {r}")
    return r

# ═══ WABA1 ═══
ok1, fail1 = subscribe_app(APP1_ID, APP1_SECRET, "WABA1 (+919330994400)")
subscribe_waba(WABA1_ID, TOKEN1, APP1_SECRET, "WABA1 (+919330994400)")

# ═══ WABA2 ═══
ok2, fail2 = subscribe_app(APP2_ID, APP2_SECRET, "WABA2 (+919903300044)")
subscribe_waba(WABA2_ID, TOKEN2, APP2_SECRET, "WABA2 (+919903300044)")

print(f"\n{'='*60}")
print(f"SUMMARY:")
print(f"  WABA1: {ok1}/{len(ALL_FIELDS)} subscribed")
print(f"  WABA2: {ok2}/{len(ALL_FIELDS)} subscribed")
print(f"{'='*60}")
