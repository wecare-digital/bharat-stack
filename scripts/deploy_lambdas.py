"""Deploy updated Lambda handlers."""
import boto3
import zipfile
import io
import os

def deploy_lambda(function_name, handler_path):
    with open(handler_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('handler.py', code)
    zip_buffer.seek(0)
    
    client = boto3.client('lambda', region_name='us-east-1')
    response = client.update_function_code(
        FunctionName=function_name,
        ZipFile=zip_buffer.read()
    )
    print(f"  Deployed: {response['FunctionName']} | {response['LastModified']} | {response['CodeSize']} bytes")

lambdas = [
    ('wecare-inbound-whatsapp', 'amplify/functions/messaging/inbound-whatsapp-handler/handler.py'),
    ('wecare-outbound-whatsapp', 'amplify/functions/messaging/outbound-whatsapp/handler.py'),
]

for name, path in lambdas:
    print(f"Deploying {name}...")
    deploy_lambda(name, path)

print("\nDone!")
