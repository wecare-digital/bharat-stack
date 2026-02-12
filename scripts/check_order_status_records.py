import boto3, json

ddb = boto3.resource('dynamodb', region_name='us-east-1')
t = ddb.Table('base-wecare-digital-WhatsAppOutboundTable')

# Scan for order_status messages
r = t.scan(
    FilterExpression='contains(content, :os)',
    ExpressionAttributeValues={':os': 'Order Status:'},
    ProjectionExpression='id,content,awsPhoneNumberId,createdAt'
)

items = sorted(r.get('Items', []), key=lambda x: float(x.get('createdAt', 0)), reverse=True)

print(f'Found {len(items)} order_status messages')
for item in items[:10]:
    phone = item.get('awsPhoneNumberId', 'MISSING')
    content = item.get('content', '')[:80]
    ts = item.get('createdAt', 0)
    phone_short = 'PHONE1(9330)' if '5e020' in str(phone) else ('PHONE2(9903)' if 'abdd81' in str(phone) else str(phone))
    print(f'  {phone_short} | {content} | ts={ts}')
