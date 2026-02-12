import boto3, json, time

c = boto3.client('logs', region_name='us-east-1')
st = int(time.time() - 43200) * 1000

r = c.filter_log_events(
    logGroupName='/aws/lambda/wecare-outbound-whatsapp',
    startTime=st,
    filterPattern='outbound_whatsapp_start',
    limit=20
)
for e in r.get('events', []):
    msg = e['message']
    if 'order' in msg.lower() or 'WDSR' in msg:
        print(msg[:500])
        print('---')

# Also check the start events that correspond to order_status
print('\n=== Checking all starts ===')
for e in r.get('events', []):
    print(e['message'][:300])
    print('---')
