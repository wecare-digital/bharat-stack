import urllib.request, json

# Call logs
r = urllib.request.urlopen("https://api.wecare.digital/whatsapp-calling/logs?limit=10", timeout=15)
data = json.loads(r.read())
print(f"=== CALL LOGS ({data['count']}) ===")
for log in data.get("logs", []):
    print(f"  event={log.get('eventType')} status={log.get('status')} from={log.get('fromNumber')} to={log.get('toNumber')}")
    print(f"    phoneId={log.get('phoneNumberId')} direction={log.get('direction')} hasSDP={'YES' if log.get('sdpOffer') else 'NO'}")
    ar = log.get('apiResponse', '')
    if ar:
        print(f"    apiResponse={ar[:300]}")
    print()

# CloudWatch logs - last invocation errors
import boto3
client = boto3.client("logs", region_name="us-east-1")
streams = client.describe_log_streams(
    logGroupName="/aws/lambda/wecare-whatsapp-calling",
    orderBy="LastEventTime", descending=True, limit=2
)
print("=== CLOUDWATCH LOGS (recent) ===")
for stream in streams["logStreams"][:2]:
    events = client.get_log_events(
        logGroupName="/aws/lambda/wecare-whatsapp-calling",
        logStreamName=stream["logStreamName"],
        limit=40, startFromHead=False
    )
    for e in events["events"]:
        msg = e["message"].strip()
        if msg and not msg.startswith("INIT_START") and not msg.startswith("END ") and not msg.startswith("REPORT ") and not msg.startswith("START "):
            low = msg.lower()
            if any(k in low for k in ["auto", "pickup", "error", "fail", "token", "pre_accept", "accept", "meta api", "call_event", "inbound call", "loaded dual"]):
                print(msg[:400])
                print()
