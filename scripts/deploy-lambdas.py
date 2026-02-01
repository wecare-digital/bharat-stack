"""
Deploy Missing Lambda Functions

Creates Lambda functions that don't exist yet in AWS.
"""

import boto3
import zipfile
import io
import os
import sys

REGION = 'us-east-1'

def get_account_id():
    """Get AWS account ID dynamically."""
    sts = boto3.client('sts', region_name=REGION)
    return sts.get_caller_identity()['Account']

ACCOUNT_ID = get_account_id()
ROLE_ARN = f'arn:aws:iam::{ACCOUNT_ID}:role/wecare-digital-lambda-role'

# Lambda functions to deploy
LAMBDAS = [
    {
        'name': 'wecare-voice-calls',
        'handler': 'handler.handler',
        'runtime': 'python3.12',
        'timeout': 30,
        'memory': 256,
        'source': 'amplify/functions/messaging/voice-calls/handler.py',
        'env': {
            'LOG_LEVEL': 'INFO',
            'CONTACTS_TABLE': 'base-wecare-digital-ContactsTable',
            'VOICE_CALLS_TABLE': 'base-wecare-digital-VoiceCalls',
        }
    },
    {
        'name': 'wecare-payments-read',
        'handler': 'handler.handler',
        'runtime': 'python3.12',
        'timeout': 10,
        'memory': 128,
        'source': 'amplify/functions/payments/payments-read/handler.py',
        'env': {
            'LOG_LEVEL': 'INFO',
            'PAYMENTS_TABLE': 'base-wecare-digital-PaymentsTable',
        }
    },
    {
        'name': 'wecare-voice-cdr-webhook',
        'handler': 'handler.handler',
        'runtime': 'python3.12',
        'timeout': 30,
        'memory': 256,
        'source': 'amplify/functions/messaging/voice-cdr-webhook/handler.py',
        'env': {
            'LOG_LEVEL': 'INFO',
            'VOICE_CDR_TABLE': 'base-wecare-digital-VoiceCDRTable',
        }
    },
    {
        'name': 'wecare-voice-cdr-read',
        'handler': 'handler.handler',
        'runtime': 'python3.12',
        'timeout': 30,
        'memory': 256,
        'source': 'amplify/functions/messaging/voice-cdr-read/handler.py',
        'env': {
            'LOG_LEVEL': 'INFO',
            'VOICE_CDR_TABLE': 'base-wecare-digital-VoiceCDRTable',
        }
    },
]

def create_zip(source_file):
    """Create a zip file from a Python source file with shared dependencies."""
    # Check if source file exists
    if not os.path.exists(source_file):
        raise FileNotFoundError(f"Source file not found: {source_file}")
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Read the source file
        with open(source_file, 'r') as f:
            content = f.read()
        # Add to zip as handler.py
        zf.writestr('handler.py', content)
        
        # Include shared utils if they exist
        shared_utils_dir = 'amplify/functions/shared/utils'
        if os.path.exists(shared_utils_dir):
            for filename in os.listdir(shared_utils_dir):
                if filename.endswith('.py'):
                    filepath = os.path.join(shared_utils_dir, filename)
                    with open(filepath, 'r') as f:
                        zf.writestr(f'utils/{filename}', f.read())
    
    zip_buffer.seek(0)
    return zip_buffer.read()

def main():
    lambda_client = boto3.client('lambda', region_name=REGION)
    
    print("Deploying Lambda Functions")
    print("=" * 60)
    
    for config in LAMBDAS:
        name = config['name']
        print(f"\n🚀 Deploying {name}...")
        
        # Check if source file exists
        if not os.path.exists(config['source']):
            print(f"   ❌ Source file not found: {config['source']}")
            continue
        
        # Check if function exists
        try:
            lambda_client.get_function(FunctionName=name)
            print(f"   Function exists, updating code...")
            
            # Update function code
            zip_bytes = create_zip(config['source'])
            lambda_client.update_function_code(
                FunctionName=name,
                ZipFile=zip_bytes,
            )
            print(f"   ✅ Code updated")
            
        except lambda_client.exceptions.ResourceNotFoundException:
            print(f"   Function doesn't exist, creating...")
            
            # Create function
            zip_bytes = create_zip(config['source'])
            try:
                lambda_client.create_function(
                    FunctionName=name,
                    Runtime=config['runtime'],
                    Role=ROLE_ARN,
                    Handler=config['handler'],
                    Code={'ZipFile': zip_bytes},
                    Timeout=config['timeout'],
                    MemorySize=config['memory'],
                    Environment={'Variables': config['env']},
                    Tags={
                        'Project': 'WECARE.DIGITAL',
                        'Environment': 'prod',
                    }
                )
                print(f"   ⏳ Waiting for function to be active...")
                waiter = lambda_client.get_waiter('function_active')
                waiter.wait(FunctionName=name)
                print(f"   ✅ Function created and active")
            except Exception as e:
                print(f"   ❌ Error creating function: {e}")
                continue
        
        # Add API Gateway permission
        try:
            lambda_client.add_permission(
                FunctionName=name,
                StatementId=f'apigateway-invoke-{name}',
                Action='lambda:InvokeFunction',
                Principal='apigateway.amazonaws.com',
                SourceArn=f'arn:aws:execute-api:{REGION}:{ACCOUNT_ID}:k4vqzmi07b/*/*',
            )
            print(f"   ✅ API Gateway permission added")
        except lambda_client.exceptions.ResourceConflictException:
            print(f"   ⏭️  Permission already exists")
        except Exception as e:
            print(f"   ⚠️  Permission error: {e}")
    
    print("\n" + "=" * 60)
    print("Deployment complete!")

if __name__ == '__main__':
    main()
