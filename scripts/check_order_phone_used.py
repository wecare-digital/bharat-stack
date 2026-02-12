import boto3, json, time

c = boto3.client('logs', region_name='us-east-1')

# Check the specific request IDs for order_status sends
request_ids = [
    '4532fd79-373d-4fbb-ac80-86bcaf734e81',  # WDSR2F3B7CDD
    '2a7f1f88-8b96-4f08-8bd0-9de521fc2840',  # WDSRB063C83B
    'df27f7e7-d7fa-4158-b8f5-775199393a1f',  # WDSR6DC0C460
    '3110c904-0396-4d92-ab0c-ccc390341189',  # WDSRF973E369
    '3e6f1f9a-0d42-4f6e-b989-478c0e24ebc2',  # WDSR43DF0AA1
]

st = int(time.time() - 43200) * 1000

for rid in request_ids:
    r = c.filter_log_events(
        logGroupName='/aws/lambda/wecare-outbound-whatsapp',
        startTime=st,
        filterPattern=rid,
        limit=20
    )
    events = r.get('events', [])
    for e in events:
        msg = e['message']
        if 'phoneNumberId' in msg or 'originationPhoneNumberId' in msg:
            print(f'RequestID: {rid}')
            print(msg[:500])
            print('---')
            break
    else:
        # Check all events for this request
        for e in events:
            msg = e['message']
            if 'calling_send' in msg or 'order_status' in msg:
                print(f'RequestID: {rid}')
                print(msg[:500])
                print('---')
                break
