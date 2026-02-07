import boto3
import json

client = boto3.client('secretsmanager', region_name='us-east-1')

# SMS Secret
sms_secret = json.dumps({
    'customer_id': 'WECAREDIG_v6J1SyLLI2auy7Lw9JrW',
    'auth_token': 'V0VDQVJFRElHX3Y2SjFTeUxMSTJhdXk3THc5SnJXOnNOJH58KElAMTEy',
    'sender_id': 'WDBEEP',
    'entity_id': '1201161991108627443',
    'dlt_template_id': '1007974344269130859'
})
print(f'Setting SMS secret...')
client.put_secret_value(SecretId='wecare/airtel/sms', SecretString=sms_secret)
print('SMS secret set!')

# OBD Secret
obd_secret = json.dumps({
    'customer_id': 'WECAREDIG_v6J1SyLLI2auy7Lw9JrW',
    'auth': 'RElHSVRBTF9WSV9MS2lwdFBzTTZqWHBtQ0NtNWduSDpec3g3OzF5fUReciQ7X20/S2p5VlZW',
    'campaign_auth': 'TUVFU0hPX1RFQ181bjVid2RMdnpjOXdSMlhqd29ySjpxLGRpdWotbFUwTiEjRzY5VWs=',
    'app_id': 'IRONMAN',
    'call_flow_id': 'dfbeda76-f641-420f-95e7-b78d562a941f',
    'caller_id': '8040761117',
    'template_id': '69818654d9e8e260e60b16a7'
})
print(f'Setting OBD secret...')
client.put_secret_value(SecretId='wecare/airtel/obd', SecretString=obd_secret)
print('OBD secret set!')

# C2C Secret
c2c_secret = json.dumps({
    'app_id': 'WECAREDIG_fD4BKqUbC8k90jNrPR0n',
    'api_key': 'u^5KLtH@11',
    'caller_id': '8047311032'
})
print(f'Setting C2C secret...')
client.put_secret_value(SecretId='wecare/airtel/c2c', SecretString=c2c_secret)
print('C2C secret set!')

print('All secrets configured!')