import boto3, json

ddb = boto3.resource('dynamodb', region_name='us-east-1')
t = ddb.Table('base-wecare-digital-WhatsAppOutboundTable')

refs = ['WDSR2F3B7CDD', 'WDSRB063C83B', 'WDSR6DC0C460', 'WDSRF973E369']

for ref in refs:
    r = t.scan(
        FilterExpression='paymentReferenceId = :ref',
        ExpressionAttributeValues={':ref': ref},
        ProjectionExpression='id,paymentReferenceId,awsPhoneNumberId'
    )
    items = r.get('Items', [])
    if items:
        phone_id = items[0].get('awsPhoneNumberId', 'MISSING')
        print(f'{ref}: awsPhoneNumberId={phone_id}')
    else:
        print(f'{ref}: NOT FOUND in outbound table')
