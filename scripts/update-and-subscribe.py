"""
Update Meta token in Secrets Manager and subscribe all webhook fields for WABA1.
"""
import urllib.request, urllib.error, json, boto3

TOKEN = "EAAf0L77jdagBQgLC9Gq7baWr1jNL7zsX8mrfkTa0MvzdSd7HrOPTsCYO4N4CJWZClHJ7HMuMZCAd88PzRtSgRxtCnjUTTL08RFaVi579bvITGxCq23v7WtLEeGMfZCYN2KMRoshRxBaM7HKrgxh5x6SZBWp1VBvpRlOaRsRXmHQhDtB5WHJfh6PVt4fbSAZDZD"
WABA_ID = "1912405516040025"
SECRET_ID = "wecare/meta-system-user-token"
REGION = "us-east-1"

ALL_FIELDS = [
    "account_alerts", "account_review_update", "account_settings_update",
    "account_update", "automatic_events", "business_capability_update",
    "business_status_update", "calls", "flows",
    "group_lifecycle_update", "group_participants_update", "group_settings_update",
    "group_status_update", "history", "message_echoes",
    "message_template_components_update", "message_template_quality_update",
    "message_template_status_update", "messages", "messaging_handovers",
    "partner_solutions", "payment_configuration_update",
    "phone_number_name_update", "phone_number_quality_update", "security",
    "smb_app_state_sync", "smb_message_echoes", "template_category_update",
    "template_correct_category_detection", "tracking_events", "user_preferences",
]

# Step 1: Update token in Secrets Manager
print("=== Step 1: Update token in Secrets Manager ===")
sm = boto3.client("secretsmanager", region_name=REGION)
secret_json = json.dumps({"access_token": TOKEN, "access_token_waba2": ""})
resp = sm.put_secret_value(SecretId=SECRET_ID, SecretString=secret_json)
print(f"  Updated version: {resp['VersionId']}")
# Verify
v = json.loads(sm.get_secret_value(SecretId=SECRET_ID)["SecretString"])
print(f"  Verified: access_token length={len(v['access_token'])}, prefix={v['access_token'][:15]}...")

# Step 2: Check current subscriptions
print("\n=== Step 2: Check current subscriptions ===")
url = f"https://graph.facebook.com/v20.0/{WABA_ID}/subscribed_apps?access_token={TOKEN}"
try:
    r = urllib.request.urlopen(url, timeout=10)
    data = json.loads(r.read())
    current_fields = []
    for app in data.get("data", []):
        app_name = app.get("whatsapp_business_api_data", {}).get("link_message", app.get("id", "unknown"))
        fields = [f.get("field", "") for f in app.get("subscribed_fields", [])]
        current_fields.extend(fields)
        print(f"  App: {app_name} -> {len(fields)} fields subscribed")
    missing = [f for f in ALL_FIELDS if f not in current_fields]
    print(f"  Currently subscribed: {len(current_fields)} fields")
    print(f"  Missing: {len(missing)} -> {missing}")
except urllib.error.HTTPError as e:
    print(f"  Error checking: {e.code}: {e.read().decode()[:300]}")
    missing = ALL_FIELDS

# Step 3: Subscribe all fields
print("\n=== Step 3: Subscribe ALL 31 fields ===")
fields_str = ",".join(ALL_FIELDS)
sub_url = f"https://graph.facebook.com/v20.0/{WABA_ID}/subscribed_apps"
payload = f"subscribed_fields={fields_str}".encode("utf-8")
req = urllib.request.Request(sub_url, data=payload, headers={
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/x-www-form-urlencoded",
}, method="POST")
try:
    r = urllib.request.urlopen(req, timeout=15)
    result = json.loads(r.read())
    print(f"  Subscribe result: {result}")
except urllib.error.HTTPError as e:
    print(f"  Subscribe error {e.code}: {e.read().decode()[:500]}")

# Step 4: Verify subscriptions after
print("\n=== Step 4: Verify subscriptions ===")
try:
    r = urllib.request.urlopen(url, timeout=10)
    data = json.loads(r.read())
    for app in data.get("data", []):
        fields = [f.get("field", "") for f in app.get("subscribed_fields", [])]
        app_id = app.get("id", "?")
        app_link = app.get("whatsapp_business_api_data", {}).get("link_message", "")
        print(f"  App {app_id}: {len(fields)} fields")
        for f in sorted(fields):
            status = "OK" if f in ALL_FIELDS else "EXTRA"
            print(f"    [{status}] {f}")
    still_missing = [f for f in ALL_FIELDS if f not in [ff.get("field","") for a in data.get("data",[]) for ff in a.get("subscribed_fields",[])]]
    if still_missing:
        print(f"\n  STILL MISSING: {still_missing}")
    else:
        print(f"\n  ALL 31 fields subscribed!")
except urllib.error.HTTPError as e:
    print(f"  Verify error: {e.read().decode()[:300]}")

# Step 5: Force Lambda cold start to pick up new token
print("\n=== Step 5: Force Lambda cold start ===")
lam = boto3.client("lambda", region_name=REGION)
try:
    lam.update_function_configuration(
        FunctionName="wecare-whatsapp-calling",
        Environment={"Variables": {
            "VERIFY_TOKEN": "wecare_calling_verify_2026",
            "CALL_LOG_TABLE": "base-wecare-digital-WhatsAppCallingTable",
            "META_TOKEN_SECRET": SECRET_ID,
            "META_API_VERSION": "v20.0",
            "LOG_LEVEL": "INFO",
            "AUTO_PICKUP_ENABLED": "true",
            "AUTO_PICKUP_IVR_URL": "https://app.wecare.digital/stream/media/ivr/ivr-greeting.mp3",
            "SYSTEM_CONFIG_TABLE": "base-wecare-digital-SystemConfigTable",
            "TOKEN_REFRESH": "v3",
        }},
    )
    print("  Lambda config updated (will cold start on next invoke)")
except Exception as e:
    print(f"  Lambda update error: {e}")

print("\n=== DONE ===")
print(f"Token updated, {len(ALL_FIELDS)} fields subscribed for WABA {WABA_ID}")
print("Make a test call to +91 9330994400 now")
