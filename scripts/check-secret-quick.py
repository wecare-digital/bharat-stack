import boto3, json

secrets = boto3.client('secretsmanager', region_name='us-east-1')
result = secrets.get_secret_value(SecretId='wecare/meta-system-user-token')
raw = result['SecretString']
print(f"Raw length: {len(raw)}")
print(f"First 100: {raw[:100]}")
print(f"Last 50: {raw[-50:]}")

try:
    data = json.loads(raw)
    print(f"\nKeys: {list(data.keys())}")
    for k, v in data.items():
        if isinstance(v, str) and len(v) > 50:
            print(f"  {k}: len={len(v)}, starts={v[:40]}...")
        else:
            print(f"  {k}: {v}")
except json.JSONDecodeError as e:
    print(f"\nJSON ERROR: {e}")
