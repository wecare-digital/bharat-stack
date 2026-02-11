import urllib.request, urllib.error, json

TOKEN = "EAAf0L77jdagBQgLC9Gq7baWr1jNL7zsX8mrfkTa0MvzdSd7HrOPTsCYO4N4CJWZClHJ7HMuMZCAd88PzRtSgRxtCnjUTTL08RFaVi579bvITGxCq23v7WtLEeGMfZCYN2KMRoshRxBaM7HKrgxh5x6SZBWp1VBvpRlOaRsRXmHQhDtB5WHJfh6PVt4fbSAZDZD"
WABA_ID = "1912405516040025"

# Get subscribed apps with full details
url = f"https://graph.facebook.com/v20.0/{WABA_ID}/subscribed_apps?access_token={TOKEN}"
try:
    r = urllib.request.urlopen(url, timeout=10)
    raw = r.read().decode()
    print(f"Raw response:\n{raw[:2000]}")
    data = json.loads(raw)
    for app in data.get("data", []):
        print(f"\nApp: {json.dumps(app, indent=2)[:500]}")
except urllib.error.HTTPError as e:
    print(f"Error {e.code}: {e.read().decode()[:500]}")

# Also check the app's WABA subscriptions from the app side
print("\n\n--- Checking from App side ---")
APP_ID = "2238810740192680"
url2 = f"https://graph.facebook.com/v20.0/{APP_ID}/subscriptions?access_token={TOKEN}"
try:
    r2 = urllib.request.urlopen(url2, timeout=10)
    raw2 = r2.read().decode()
    print(f"App subscriptions:\n{raw2[:2000]}")
except urllib.error.HTTPError as e:
    print(f"App sub error {e.code}: {e.read().decode()[:500]}")
