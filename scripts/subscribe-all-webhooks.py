"""
Subscribe all 31 webhook fields for both WABAs.
WABA1: 1912405516040025 (+91 9330994400) - App: WECARE.DIGITAL (2238810740192680)
WABA2: 1633959101297902 (+91 9903300044) - App: Manish Agarwal (1224334845952721)
"""
import urllib.request
import urllib.error
import json

WABAS = [
    {
        "name": "WABA1 (+91 9330994400) - WECARE.DIGITAL",
        "waba_id": "1912405516040025",
        "app_id": "2238810740192680",
        "token": "EAAf0L77jdagBQgLC9Gq7baWr1jNL7zsX8mrfkTa0MvzdSd7HrOPTsCYO4N4CJWZClHJ7HMuMZCAd88PzRtSgRxtCnjUTTL08RFaVi579bvITGxCq23v7WtLEeGMfZCYN2KMRoshRxBaM7HKrgxh5x6SZBWp1VBvpRlOaRsRXmHQhDtB5WHJfh6PVt4fbSAZDZD",
    },
    {
        "name": "WABA2 (+91 9903300044) - Manish Agarwal",
        "waba_id": "1633959101297902",
        "app_id": "1224334845952721",
        "token": "EAARZAhquUQtEBQhsTOPFsjCPZAqqnwKKHMFAOIkqdWK6GTra626rIJVeZCdONK2x3HYeS44YKnZCfZCbvBZBy20TUc1DM4oEuqZBNCVqTuPexrbsqjxZCOZAXUMq5wCjgcsiiIn3SEO2kh2b9yCjgzY1A4wKQOpVzrE7aLGJ7a4SJQeOZA7rGwGSlMRBDq9EdGrwZDZD",
    },
]

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

API_VERSION = "v22.0"

def meta_api(url, token, method="POST", data=None):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode() if e.fp else ""
        return {"error": True, "status": e.code, "detail": err}
    except Exception as e:
        return {"error": True, "detail": str(e)}

def check_and_subscribe(waba):
    print(f"\n{'='*60}")
    print(f"  {waba['name']}")
    print(f"  WABA ID: {waba['waba_id']} | App ID: {waba['app_id']}")
    print(f"{'='*60}")

    # Step 1: Check current subscriptions
    print(f"\n[1] Checking current subscriptions...")
    url = f"https://graph.facebook.com/{API_VERSION}/{waba['waba_id']}/subscribed_apps"
    result = meta_api(url, waba["token"], method="GET")
    if result.get("error"):
        print(f"  ERROR: {json.dumps(result)}")
    else:
        apps = result.get("data", [])
        if apps:
            for app in apps:
                print(f"  App: {app.get('whatsapp_business_api_data', {}).get('id', 'unknown')}")
                print(f"  Link: {app.get('whatsapp_business_api_data', {}).get('link', 'N/A')}")
                fields = app.get("whatsapp_business_api_data", {}).get("subscribed_fields", [])
                print(f"  Subscribed fields ({len(fields)}): {', '.join(fields)}")
        else:
            print("  No subscriptions found")

    # Step 2: Subscribe all fields
    print(f"\n[2] Subscribing all {len(ALL_FIELDS)} webhook fields...")
    url = f"https://graph.facebook.com/{API_VERSION}/{waba['waba_id']}/subscribed_apps"
    result = meta_api(url, waba["token"], method="POST", data={
        "subscribed_fields": ALL_FIELDS
    })
    if result.get("error"):
        print(f"  SUBSCRIBE ERROR: {json.dumps(result)}")
        # Try subscribing one by one
        print(f"\n[2b] Bulk failed — trying one by one...")
        success = []
        failed = []
        for field in ALL_FIELDS:
            r = meta_api(url, waba["token"], method="POST", data={"subscribed_fields": [field]})
            if r.get("success") or not r.get("error"):
                success.append(field)
                print(f"  ✓ {field}")
            else:
                failed.append(field)
                print(f"  ✗ {field}: {r.get('detail', '')[:100]}")
        print(f"\n  Subscribed: {len(success)}/{len(ALL_FIELDS)}")
        if failed:
            print(f"  Failed: {', '.join(failed)}")
    else:
        print(f"  Result: {json.dumps(result)}")
        if result.get("success"):
            print(f"  ✓ All {len(ALL_FIELDS)} fields subscribed successfully!")

    # Step 3: Verify subscriptions
    print(f"\n[3] Verifying subscriptions...")
    result = meta_api(
        f"https://graph.facebook.com/{API_VERSION}/{waba['waba_id']}/subscribed_apps",
        waba["token"], method="GET"
    )
    if not result.get("error"):
        apps = result.get("data", [])
        for app in apps:
            fields = app.get("whatsapp_business_api_data", {}).get("subscribed_fields", [])
            print(f"  Verified: {len(fields)} fields subscribed")
            missing = set(ALL_FIELDS) - set(fields)
            if missing:
                print(f"  Missing: {', '.join(missing)}")
            else:
                print(f"  ✓ All {len(ALL_FIELDS)} fields confirmed!")
    else:
        print(f"  Verify error: {json.dumps(result)}")

if __name__ == "__main__":
    for waba in WABAS:
        check_and_subscribe(waba)
    print(f"\n{'='*60}")
    print("  DONE — Both WABAs processed")
    print(f"{'='*60}")
