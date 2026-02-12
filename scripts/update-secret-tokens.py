"""
Update Secrets Manager with the latest tokens from the user.

WABA1 (+919330994400): App WECARE.DIGITAL (2238810740192680)
  System User: 100087122020710 (Manish Agarwal)
  
WABA2 (+919903300044): App Manish Agarwal (1224334845952721)
  System User: 100086687697377 (Manish Agarwal)
"""
import boto3, json

secrets = boto3.client('secretsmanager', region_name='us-east-1')

# Latest tokens from user
TOKEN1 = "EAAf0L77jdagBQppO7QZCuPoaiL4G76snYzvw0e8PlTjiSsKrdXKQhXcZA34xJCkFasl2LqMGkCIwru4ThtxXqOUcmYUlkmicUTsnHFg1wWbDqp0xfEuYdr92BGSB0d07iRZBY17ZCCHPwIhl19C3buqpQXxkxHEcpReI9T63xT2KF61SXrgyZCJLVPggsmwZDZD"
TOKEN2 = "EAARZAhquUQtEBQryKXjwfmazTqjiysqrwLStdZAj57DYIe5ZCUd2yN75cauNmcnTXEOu28qvjaOGNdh7kIjx1bi7emQH0o7GRgEULkDoQql3ZCZBYIeU5V3t8Th0aTkS8UKm947jIIYHKhacZBCQxrAZAgZBiANxDnRTKuZAoJp7vhD3uIe6skmKp8vqbhSCZAgAZDZD"

APP_SECRET1 = "9c146c26b6adc338472ac205b158b3d5"
APP_SECRET2 = "c661642ea55355d9abd84105f6ffb236"

new_secret = json.dumps({
    "access_token": TOKEN1,
    "access_token_waba2": TOKEN2,
    "app_secret": APP_SECRET1,
    "app_secret_waba2": APP_SECRET2,
})

secrets.update_secret(SecretId='wecare/meta-system-user-token', SecretString=new_secret)
print("Secret updated successfully")

# Verify
result = secrets.get_secret_value(SecretId='wecare/meta-system-user-token')
data = json.loads(result['SecretString'])
print(f"Token1 starts: {data['access_token'][:40]}...")
print(f"Token2 starts: {data['access_token_waba2'][:40]}...")
print(f"App secrets present: {bool(data.get('app_secret'))}, {bool(data.get('app_secret_waba2'))}")
