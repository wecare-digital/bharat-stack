"""Subscribe all webhook fields for WABA2 (+91 9903300044) / App2 (1224334845952721)"""
import json, hmac, hashlib, time, urllib.request, urllib.error, urllib.parse

TOKEN2 = "EAARZAhquUQtEBQhsTOPFsjCPZAqqnwKKHMFAOIkqdWK6GTra626rIJVeZCdONK2x3HYeS44YKnZCfZCbvBZBy20TUc1DM4oEuqZBNCVqTuPexrbsqjxZCOZAXUMq5wCjgcsiiIn3SEO2kh2b9yCjgzY1A4wKQOpVzrE7aLGJ7a4SJQeOZA7rGwGSlMRBDq9EdGrwZDZD"
APP2_ID = "1224334845952721"
APP2_SECRET = "c661642ea55355d9abd84105f6ffb236"
WABA2_ID = "1633959101297902"

CALLBACK_URL = "https://api.wecare.digital/whatsapp-calling"
VERIFY_TOKEN = "wecare_calling_verify_2026"

FIELDS = [
    "account_alerts", "account_review_update", "account_settings_update",
    "account_update", "automatic_events", "business_capability_update",
    "business_status_update", "calls", "flows",
    "group_lifecycle_update", "group_participants_update",
    "group_settings_update", "group_status_update", "history",
    "message_echoes", "message_template_components_update",
    "message_template_quality_update", "message_template_status_update",
    "messages", "messaging_handovers", "partner_solutions",
    "payment_configuration_update", "phone_number_name_update",
    "phone_number_quality_update", "security",
    "smb_app_state_sync", "smb_message_echoes",
    "template_category_update", "template_correct_category_detection",
    "tracking_events", "user_preferences",
]

# Step 1: WABA-level subscription
print("=== WABA2 subscribed_apps ===")
proof = hmac.new(APP2_SECRET.encode(), TOKEN2.encode(), hashlib.sha256).hexdigest()
url = f"https://graph.facebook.com/v20.0/{WABA2_ID}/subscribed_apps?appsecret_proof={proof}"
req = urllib.request.Request(url, data=b'', headers={'Authorization': f'Bearer {TOKEN2}'}, method='POST')
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        print(f"  {resp.read().decode()}")
except urllib.error.HTTPError as e:
    print(f"  FAIL {e.code}: {e.read().decode()[:300]}")

# Step 2: Get app token
print("\n=== Get App2 token ===")
url = f"https://graph.facebook.com/oauth/access_token?client_id={APP2_ID}&client_secret={APP2_SECRET}&grant_type=client_credentials"
try:
    with urllib.request.urlopen(urllib.request.Request(url), timeout=15) as resp:
        app_token = json.loads(resp.read().decode()).get('access_token', '')
        print(f"  App token: {app_token[:30]}...")
except urllib.error.HTTPError as e:
    print(f"  FAIL: {e.code} {e.read().decode()[:200]}")
    app_token = None

# Step 3: Subscribe each field
print("\n=== Subscribe App-level fields ===")
ok = []
fail = []
for field in FIELDS:
    url = f"https://graph.facebook.com/v20.0/{APP2_ID}/subscriptions"
    payload = urllib.parse.urlencode({
        'object': 'whatsapp_business_account',
        'callback_url': CALLBACK_URL,
        'verify_token': VERIFY_TOKEN,
        'fields': field,
    }).encode()
    token_to_use = app_token if app_token else TOKEN2
    headers = {'Authorization': f'Bearer {token_to_use}', 'Content-Type': 'application/x-www-form-urlencoded'}
    req = urllib.request.Request(url, data=payload, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            r = json.loads(resp.read().decode())
            if r.get('success'):
                ok.append(field)
            else:
                fail.append((field, str(r)))
    except urllib.error.HTTPError as e:
        fail.append((field, f"{e.code}: {e.read().decode()[:150]}"))
    time.sleep(0.3)

print(f"\n✅ Subscribed: {len(ok)}/{len(FIELDS)}")
if ok:
    print(f"   {', '.join(ok)}")
if fail:
    print(f"\n❌ Failed ({len(fail)}):")
    for f, err in fail:
        print(f"   {f}: {err}")

# Step 4: Verify
print("\n=== Verify subscriptions ===")
if app_token:
    url = f"https://graph.facebook.com/v20.0/{APP2_ID}/subscriptions"
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {app_token}'})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            for sub in data.get('data', []):
                if sub.get('object') == 'whatsapp_business_account':
                    fields = [f['name'] for f in sub.get('fields', [])]
                    print(f"  Subscribed ({len(fields)}): {', '.join(sorted(fields))}")
    except urllib.error.HTTPError as e:
        print(f"  Verify FAIL: {e.code} {e.read().decode()[:200]}")

print("\nDONE")
