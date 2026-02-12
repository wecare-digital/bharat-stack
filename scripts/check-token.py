import json, boto3
secrets = boto3.client('secretsmanager', region_name='us-east-1')
raw = secrets.get_secret_value(SecretId='wecare/meta-system-user-token')['SecretString']
print(f"Raw ({len(raw)} chars): {raw[:80]}...")

# Try json.loads
try:
    data = json.loads(raw)
    print(f"JSON OK: token1={data.get('access_token','')[:20]}... token2={data.get('access_token_waba2','')[:20]}...")
except (json.JSONDecodeError, TypeError) as e:
    print(f"JSON FAILED: {e}")
    # This is what the Lambda does on failure — treats whole string as token
    print(f"Fallback: token1 = raw.strip() = '{raw.strip()[:40]}...'")
    print("THIS IS THE BUG — the whole {access_token: ...} string is used as the Bearer token!")

# Fix: store as proper JSON
print("\n--- FIX: Re-store as proper JSON ---")
# Parse the non-standard format
tokens = {}
for part in raw.strip().strip('{}').split(','):
    if ':' in part:
        k, v = part.strip().split(':', 1)
        tokens[k.strip()] = v.strip()

t1 = tokens.get('access_token', '')
t2 = tokens.get('access_token_waba2', '')
print(f"Parsed token1: {t1[:20]}... ({len(t1)} chars)")
print(f"Parsed token2: {t2[:20]}... ({len(t2)} chars)")

# Store as proper JSON
proper_json = json.dumps({"access_token": t1, "access_token_waba2": t2})
print(f"\nProper JSON: {proper_json[:80]}...")
print(f"Length: {len(proper_json)}")

# Update secret
secrets.update_secret(SecretId='wecare/meta-system-user-token', SecretString=proper_json)
print("\n✅ Secret updated with proper JSON format!")

# Verify
raw2 = secrets.get_secret_value(SecretId='wecare/meta-system-user-token')['SecretString']
data2 = json.loads(raw2)
print(f"Verify: token1={data2['access_token'][:20]}... token2={data2['access_token_waba2'][:20]}...")
