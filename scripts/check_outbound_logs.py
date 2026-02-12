import boto3, json, time

c = boto3.client('logs', region_name='us-east-1')
st = int(time.time() - 43200) * 1000

r = c.filter_log_events(
    logGroupName='/aws/lambda/wecare-outbound-whatsapp',
    startTime=st,
    filterPattern='order_status_details_received',
    limit=5
)
for e in r.get('events', []):
    print(e['message'][:500])
    print('---')
