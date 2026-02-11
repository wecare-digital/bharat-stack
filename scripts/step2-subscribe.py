import urllib.request, urllib.error, json

TOKEN = "EAAf0L77jdagBQgLC9Gq7baWr1jNL7zsX8mrfkTa0MvzdSd7HrOPTsCYO4N4CJWZClHJ7HMuMZCAd88PzRtSgRxtCnjUTTL08RFaVi579bvITGxCq23v7WtLEeGMfZCYN2KMRoshRxBaM7HKrgxh5x6SZBWp1VBvpRlOaRsRXmHQhDtB5WHJfh6PVt4fbSAZDZD"
WABA_ID = "1912405516040025"

ALL_FIELDS = "account_alerts,account_review_update,account_settings_update,account_update,automatic_events,business_capability_update,business_status_update,calls,flows,group_lifecycle_update,group_participants_update,group_settings_update,group_status_update,history,message_echoes,message_template_components_update,message_template_quality_update,message_template_status_update,messages,messaging_handovers,partner_solutions,payment_configuration_update,phone_number_name_update,phone_number_quality_update,security,smb_app_state_sync,smb_message_echoes,template_category_update,template_correct_category_detection,tracking_events,user_preferences"

print(f"Subscribing {len(ALL_FIELDS.split(','))} fields to WABA {WABA_ID}...")
url = f"https://graph.facebook.com/v24.0/{WABA_ID}/subscribed_apps?access_token={TOKEN}"
data = f"subscribed_fields={ALL_FIELDS}".encode()
req = urllib.request.Request(url, data=data, method="POST")
req.add_header("Content-Type", "application/x-www-form-urlencoded")
try:
    resp = urllib.request.urlopen(req, timeout=15)
    print(f"Result: {json.loads(resp.read())}")
except urllib.error.HTTPError as e:
    print(f"Error {e.code}: {e.read().decode()}")

# Verify
print("\nVerifying subscribed apps...")
url2 = f"https://graph.facebook.com/v24.0/{WABA_ID}/subscribed_apps?access_token={TOKEN}"
resp2 = urllib.request.urlopen(url2, timeout=10)
apps = json.loads(resp2.read())
for app in apps.get("data", []):
    info = app.get("whatsapp_business_api_data", {})
    print(f"  {info.get('name')} (ID: {info.get('id')})")
