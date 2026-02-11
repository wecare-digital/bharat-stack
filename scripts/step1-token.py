import boto3, json
TOKEN = "EAAf0L77jdagBQgLC9Gq7baWr1jNL7zsX8mrfkTa0MvzdSd7HrOPTsCYO4N4CJWZClHJ7HMuMZCAd88PzRtSgRxtCnjUTTL08RFaVi579bvITGxCq23v7WtLEeGMfZCYN2KMRoshRxBaM7HKrgxh5x6SZBWp1VBvpRlOaRsRXmHQhDtB5WHJfh6PVt4fbSAZDZD"
sm = boto3.client("secretsmanager", region_name="us-east-1")
secret = json.dumps({"access_token": TOKEN, "access_token_waba2": ""})
r = sm.put_secret_value(SecretId="wecare/meta-system-user-token", SecretString=secret)
print(f"OK version={r['VersionId']}")
