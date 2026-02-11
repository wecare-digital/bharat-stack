import boto3, json, sys
sm = boto3.client("secretsmanager", region_name="us-east-1")
token = "EAAf0L77jdagBQgLC9Gq7baWr1jNL7zsX8mrfkTa0MvzdSd7HrOPTsCYO4N4CJWZClHJ7HMuMZCAd88PzRtSgRxtCnjUTTL08RFaVi579bvITGxCq23v7WtLEeGMfZCYN2KMRoshRxBaM7HKrgxh5x6SZBWp1VBvpRlOaRsRXmHQhDtB5WHJfh6PVt4fbSAZDZD"
secret = json.dumps({"access_token": token, "access_token_waba2": ""})
sys.stdout.write("Updating secret...")
sys.stdout.flush()
r = sm.put_secret_value(SecretId="wecare/meta-system-user-token", SecretString=secret)
print(f" done. Version: {r['VersionId']}")
print(f"Token length: {len(token)} chars, prefix: {token[:20]}...")
