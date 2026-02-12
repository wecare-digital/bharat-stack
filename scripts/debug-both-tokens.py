"""Debug both tokens — check user_id and granular scope targets"""
import json, urllib.request

TOKEN1 = "EAAf0L77jdagBQgLC9Gq7baWr1jNL7zsX8mrfkTa0MvzdSd7HrOPTsCYO4N4CJWZClHJ7HMuMZCAd88PzRtSgRxtCnjUTTL08RFaVi579bvITGxCq23v7WtLEeGMfZCYN2KMRoshRxBaM7HKrgxh5x6SZBWp1VBvpRlOaRsRXmHQhDtB5WHJfh6PVt4fbSAZDZD"
TOKEN2 = "EAARZAhquUQtEBQryKXjwfmazTqjiysqrwLStdZAj57DYIe5ZCUd2yN75cauNmcnTXEOu28qvjaOGNdh7kIjx1bi7emQH0o7GRgEULkDoQql3ZCZBYIeU5V3t8Th0aTkS8UKm947jIIYHKhacZBCQxrAZAgZBiANxDnRTKuZAoJp7vhD3uIe6skmKp8vqbhSCZAgAZDZD"

for label, token, app_id, app_secret in [
    ("Token1 (WABA1)", TOKEN1, "2238810740192680", "9c146c26b6adc338472ac205b158b3d5"),
    ("Token2 (WABA2)", TOKEN2, "1224334845952721", "c661642ea55355d9abd84105f6ffb236"),
]:
    print(f"\n=== {label} ===")
    url = f"https://graph.facebook.com/v20.0/debug_token?input_token={token}&access_token={app_id}|{app_secret}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=15) as resp:
            data = json.loads(resp.read().decode())['data']
            print(f"  user_id: {data.get('user_id')}")
            print(f"  app: {data.get('application')} ({data.get('app_id')})")
            print(f"  type: {data.get('type')}")
            print(f"  valid: {data.get('is_valid')}")
            print(f"  scopes: {data.get('scopes')}")
            print(f"  granular_scopes:")
            for gs in data.get('granular_scopes', []):
                scope = gs.get('scope')
                targets = gs.get('target_ids')
                if targets:
                    print(f"    {scope} -> WABAs: {targets}")
                else:
                    print(f"    {scope} -> ALL (no specific targets)")
            
            # The fix: for whatsapp_business_messaging to work,
            # granular_scopes MUST have target_ids with the WABA ID
            wbm = [gs for gs in data.get('granular_scopes', []) if gs.get('scope') == 'whatsapp_business_messaging']
            if wbm and wbm[0].get('target_ids'):
                print(f"  ✅ whatsapp_business_messaging is scoped to: {wbm[0]['target_ids']}")
            else:
                print(f"  ❌ whatsapp_business_messaging has NO target WABAs — this is why 403 happens!")
                print(f"     The system user needs WABA assets assigned BEFORE generating the token.")
    except Exception as e:
        print(f"  Error: {e}")
