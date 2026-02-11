import urllib.request, urllib.error, json, sys

TOKEN = "EAAf0L77jdagBQgLC9Gq7baWr1jNL7zsX8mrfkTa0MvzdSd7HrOPTsCYO4N4CJWZClHJ7HMuMZCAd88PzRtSgRxtCnjUTTL08RFaVi579bvITGxCq23v7WtLEeGMfZCYN2KMRoshRxBaM7HKrgxh5x6SZBWp1VBvpRlOaRsRXmHQhDtB5WHJfh6PVt4fbSAZDZD"
WABA_ID = "1912405516040025"

ALL_FIELDS = "account_alerts,account_review_update,account_settings_update,account_update,automatic_events,business_capability_update,business_status_update,calls,flows,group_lifecycle_update,group_participants_update,group_settings_update,group_status_update,history,message_echoes,message_template_components_update,message_template_quality_update,message_template_status_update,messages,messaging_handovers,partner_solutions,payment_configuration_update,phone_number_name_update,phone_number_quality_update,security,smb_app_state_sync,smb_message_echoes,template_category_update,template_correct_category_detection,tracking_events,user_preferences"

# Subscribe all fields
print(f"Subscribing {len(ALL_FIELDS.split(','))} fields to WABA {WABA_ID}...")
sys.stdout.flush()
url = f"https://graph.facebook.com/v20.0/{WABA_ID}/subscribed_apps"
payload = f"subscribed_fields={ALL_FIELDS}".encode("utf-8")
req = urllib.request.Request(url, data=payload, headers={
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/x-www-form-urlencoded",
}, method="POST")
try:
    r = urllib.request.urlopen(req, timeout=15)
    print(f"Result: {json.loads(r.read())}")
except urllib.error.HTTPError as e:
    print(f"Error {e.code}: {e.read().decode()[:500]}")

# Verify
print("\nVerifying subscriptions...")
sys.stdout.flush()
url2 = f"https://graph.facebook.com/v20.0/{WABA_ID}/subscribed_apps?access_token={TOKEN}"
try:
    r2 = urllib.request.urlopen(url2, timeout=10)
    data = json.loads(r2.read())
    all_subscribed = []
    for app in data.get("data", []):
        fields = [f.get("field", "") for f in app.get("subscribed_fields", [])]
        app_id = app.get("id", "?")
        print(f"  App {app_id}: {len(fields)} fields")
        all_subscribed.extend(fields)
    wanted = ALL_FIELDS.split(",")
    missing = [f for f in wanted if f not in all_subscribed]
    if missing:
        print(f"MISSING: {missing}")
    else:
        print(f"ALL {len(wanted)} fields subscribed!")
except urllib.error.HTTPError as e:
    print(f"Verify error: {e.read().decode()[:300]}")
