"""
Update Billing Lambda Function

Deploys the billing Lambda with Cost Explorer permissions.
"""

import boto3
import zipfile
import io
import os
import json

REGION = 'us-east-1'

def get_account_id():
    """Get AWS account ID dynamically."""
    sts = boto3.client('sts', region_name=REGION)
    return sts.get_caller_identity()['Account']

ACCOUNT_ID = get_account_id()
ROLE_ARN = f'arn:aws:iam::{ACCOUNT_ID}:role/wecare-digital-lambda-role'
FUNCTION_NAME = 'wecare-billing'

# Cost Explorer IAM policy
COST_EXPLORER_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ce:GetCostAndUsage",
                "ce:GetCostForecast",
                "ce:GetDimensionValues",
                "ce:GetTags"
            ],
            "Resource": "*"
        }
    ]
}

def create_zip(source_file):
    """Create a zip file from a Python source file."""
    if not os.path.exists(source_file):
        raise FileNotFoundError(f"Source file not found: {source_file}")
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        with open(source_file, 'r') as f:
            content = f.read()
        zf.writestr('handler.py', content)
        
        # Include shared utils
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
    iam_client = boto3.client('iam', region_name=REGION)
    
    print("=" * 60)
    print("Updating Billing Lambda Function")
    print("=" * 60)
    
    source_file = 'amplify/functions/operations/billing/handler.py'
    
    # Check if source file exists
    if not os.path.exists(source_file):
        print(f"❌ Source file not found: {source_file}")
        return
    
    print(f"\n📄 Source: {source_file}")
    
    # Check if function exists
    try:
        lambda_client.get_function(FunctionName=FUNCTION_NAME)
        print(f"✅ Function {FUNCTION_NAME} exists, updating code...")
        
        # Update function code
        zip_bytes = create_zip(source_file)
        lambda_client.update_function_code(
            FunctionName=FUNCTION_NAME,
            ZipFile=zip_bytes,
        )
        print(f"✅ Code updated")
        
        # Wait for function to be ready
        print(f"⏳ Waiting for function to be ready...")
        waiter = lambda_client.get_waiter('function_updated')
        waiter.wait(FunctionName=FUNCTION_NAME)
        
        # Update function configuration
        lambda_client.update_function_configuration(
            FunctionName=FUNCTION_NAME,
            Timeout=30,
            MemorySize=256,
            Environment={
                'Variables': {
                    'LOG_LEVEL': 'INFO',
                }
            }
        )
        print(f"✅ Configuration updated")
        
    except lambda_client.exceptions.ResourceNotFoundException:
        print(f"⚠️  Function doesn't exist, creating...")
        
        zip_bytes = create_zip(source_file)
        try:
            lambda_client.create_function(
                FunctionName=FUNCTION_NAME,
                Runtime='python3.12',
                Role=ROLE_ARN,
                Handler='handler.handler',
                Code={'ZipFile': zip_bytes},
                Timeout=30,
                MemorySize=256,
                Environment={
                    'Variables': {
                        'LOG_LEVEL': 'INFO',
                    }
                },
                Tags={
                    'Project': 'WECARE.DIGITAL',
                    'Environment': 'prod',
                }
            )
            print(f"⏳ Waiting for function to be active...")
            waiter = lambda_client.get_waiter('function_active')
            waiter.wait(FunctionName=FUNCTION_NAME)
            print(f"✅ Function created and active")
        except Exception as e:
            print(f"❌ Error creating function: {e}")
            return
    
    # Add API Gateway permission
    try:
        lambda_client.add_permission(
            FunctionName=FUNCTION_NAME,
            StatementId=f'apigateway-invoke-{FUNCTION_NAME}',
            Action='lambda:InvokeFunction',
            Principal='apigateway.amazonaws.com',
            SourceArn=f'arn:aws:execute-api:{REGION}:{ACCOUNT_ID}:k4vqzmi07b/*/*',
        )
        print(f"✅ API Gateway permission added")
    except lambda_client.exceptions.ResourceConflictException:
        print(f"⏭️  API Gateway permission already exists")
    except Exception as e:
        print(f"⚠️  Permission error: {e}")
    
    # Update IAM role with Cost Explorer permissions
    print(f"\n📋 Updating IAM role with Cost Explorer permissions...")
    policy_name = 'wecare-billing-cost-explorer'
    
    try:
        # Check if policy exists
        try:
            iam_client.get_role_policy(
                RoleName='wecare-digital-lambda-role',
                PolicyName=policy_name
            )
            print(f"⏭️  Cost Explorer policy already attached")
        except iam_client.exceptions.NoSuchEntityException:
            # Attach inline policy
            iam_client.put_role_policy(
                RoleName='wecare-digital-lambda-role',
                PolicyName=policy_name,
                PolicyDocument=json.dumps(COST_EXPLORER_POLICY)
            )
            print(f"✅ Cost Explorer policy attached to role")
    except Exception as e:
        print(f"⚠️  IAM policy error: {e}")
        print("   You may need to manually add Cost Explorer permissions to the Lambda role")
    
    print("\n" + "=" * 60)
    print("✅ Billing Lambda deployment complete!")
    print("=" * 60)
    print(f"\nTest the API:")
    print(f"  curl https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod/billing")

if __name__ == '__main__':
    main()
