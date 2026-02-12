import boto3, json

ddb = boto3.resource('dynamodb', region_name='us-east-1')
t = ddb.Table('base-wecare-digital-WhatsAppOutboundTable')

r = t.scan(
    FilterExpression='attribute_exists(paymentReferenceId)',
    ProjectionExpression='id,content,awsPhoneNumberId,paymentReferenceId,createdAt'
)

items = sorted(r.get('Items', []), key=lambda x: float(x.get('createdAt', 0)), reverse=True)

print(f'Found {len(items)} payment messages')
for item in items[:10]:
    phone = item.get('awsPhoneNumberId', 'MISSING')
    ref = item.get('paymentReferenceId', '?')
    content = item.get('content', '')[:60]
    phone_short = 'PHONE1(9330)' if '5e020' in str(phone) else ('PHONE2(9903)' if 'abdd81' in str(phone) else str(phone))
    print(f'  {ref} | {phone_short} | {content}')
