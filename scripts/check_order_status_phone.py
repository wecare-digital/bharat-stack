import boto3, json, time

c = boto3.client('logs', region_name='us-east-1')
st = int(time.time() - 43200) * 1000

r = c.filter_log_events(
    logGroupName='/aws/lambda/wecare-outbound-whatsapp',
    startTime=st,
    filterPattern='order_status_payload',
    limit=10
)
print(f'Found {len(r.get("events",[]))} events')
for e in r.get('events', []):
    msg = e['message']
    # Extract the JSON part
    try:
        json_start = msg.index('{')
        data = json.loads(msg[json_start:])
        ref = data.get('referenceId', '?')
        phone = data.get('payload', {}).get('interactive', {}).get('action', {}).get('parameters', {}).get('reference_id', '?')
        print(f"Ref: {ref}")
        # The phone is in the originationPhoneNumberId used in the API call
        # But it's not in this log. Let's check the full payload
        print(json.dumps(data, indent=2)[:600])
    except:
        print(msg[:400])
    print('---')
