"""Deploy the fixed inbound WhatsApp handler to Lambda."""
import boto3
import zipfile
import io
import os

def deploy():
    handler_path = os.path.join('amplify', 'functions', 'messaging', 'inbound-whatsapp-handler', 'handler.py')
    
    with open(handler_path, 'r', encoding='utf-8') as f:
        code = f.read()
    
    # Create zip
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('handler.py', code)
    zip_buffer.seek(0)
    
    client = boto3.client('lambda', region_name='us-east-1')
    response = client.update_function_code(
        FunctionName='wecare-inbound-whatsapp',
        ZipFile=zip_buffer.read()
    )
    
    print(f"Deployed: {response['FunctionName']}")
    print(f"Last Modified: {response['LastModified']}")
    print(f"Code Size: {response['CodeSize']} bytes")

if __name__ == '__main__':
    deploy()
