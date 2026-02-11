import boto3
client = boto3.client("logs", region_name="us-east-1")
streams = client.describe_log_streams(
    logGroupName="/aws/lambda/wecare-whatsapp-calling",
    orderBy="LastEventTime", descending=True, limit=1
)
stream = streams["logStreams"][0]["logStreamName"]
print(f"Stream: {stream}")
events = client.get_log_events(
    logGroupName="/aws/lambda/wecare-whatsapp-calling",
    logStreamName=stream, limit=50, startFromHead=False
)
for e in events["events"]:
    msg = e["message"].strip()
    if msg and not msg.startswith(("INIT_START", "END ", "REPORT ", "START ")):
        print(msg[:500])
