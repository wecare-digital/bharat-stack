import boto3
import json
import urllib.request

secrets = boto3.client('secretsmanager', region_name='us-east-1')

# Get current secret
result = secrets.get_secret_value(SecretId='wecare/meta-system-user-token')
raw = result['SecretString']
print(f"Raw secret length: {len(raw)}")
print(f"Raw secret first 80 chars: {raw[:80]}")

try:
    data = json.loads(raw)
    print(f"\nParsed JSON keys: {list(data.keys())}")
    
    token1 = data.get('access_token', data.get('token1', ''))
    token2 = data.get('token2', '')
    app_secret1 = data.get('app_secret1', '')
    app_secret2 = data.get('app_secret2', '')
    
    print(f"token1 length: {len(token1)}, starts: {token1[:30]}...")
    print(f"token2 length: {len(token2)}, starts: {token2[:30]}..." if token2 else "token2: NOT SET")
    print(f"app_secret1: {app_secret1[:10]}..." if app_secret1 else "app_secret1: NOT SET")
    print(f"app_secret2: {app_secret2[:10]}..." if app_secret2 else "app_secret2: NOT SET")
    
    # Test token1 against debug_token
    for label, token in [("Token1", token1), ("Token2", token2)]:
        if not token:
            continue
        print(f"\n--- Testing {label} ---")
        url = f"https://graph.facebook.com/v20.0/debug_token?input_token={token}&access_token={token}"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as resp:
                info = json.loads(resp.read())
                d = info.get('data', {})
                print(f"  app_id: {d.get('app_id')}")
                print(f"  user_id: {d.get('user_id')}")
                print(f"  is_valid: {d.get('is_valid')}")
                print(f"  type: {d.get('type')}")
                scopes = d.get('scopes', [])
                print(f"  scopes: {scopes}")
                granular = d.get('granular_scopes', [])
                for g in granular:
                    print(f"  granular: {g.get('permission')} -> targets: {g.get('target_ids', [])}")
        except Exception as e:
            print(f"  Error: {e}")
            
except json.JSONDecodeError as e:
    print(f"\nJSON parse error: {e}")
    print("Secret is NOT valid JSON — this is the root cause of 401")
