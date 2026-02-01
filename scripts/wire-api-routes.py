"""
Wire API Gateway Routes to Lambda Functions

This script creates the missing API Gateway routes and integrations
for the WECARE.DIGITAL platform.

API Gateway ID: k4vqzmi07b
Region: us-east-1
Account: 809904170947
"""

import boto3
import json

# Configuration
API_ID = 'k4vqzmi07b'
REGION = 'us-east-1'
ACCOUNT_ID = '809904170947'
STAGE = 'prod'

# Routes to create
ROUTES = [
    # SMS
    {'path': '/sms/send', 'method': 'POST', 'lambda': 'wecare-outbound-sms'},
    
    # Email
    {'path': '/email/send', 'method': 'POST', 'lambda': 'wecare-outbound-email'},
    
    # Voice Calls
    {'path': '/voice/calls', 'method': 'GET', 'lambda': 'wecare-voice-calls'},
    {'path': '/voice/calls/{callId}', 'method': 'GET', 'lambda': 'wecare-voice-calls'},
    {'path': '/voice/call', 'method': 'POST', 'lambda': 'wecare-voice-calls'},
    
    # Voice CDR (Airtel)
    {'path': '/voice-cdr-webhook', 'method': 'POST', 'lambda': 'wecare-voice-cdr-webhook'},
    {'path': '/voice-cdr-read', 'method': 'GET', 'lambda': 'wecare-voice-cdr-read'},
    
    # Bulk Jobs
    {'path': '/bulk/jobs', 'method': 'GET', 'lambda': 'wecare-bulk-job-create'},
    {'path': '/bulk/jobs', 'method': 'POST', 'lambda': 'wecare-bulk-job-create'},
    {'path': '/bulk/jobs/{jobId}', 'method': 'GET', 'lambda': 'wecare-bulk-job-create'},
    
    # Payments
    {'path': '/payments', 'method': 'GET', 'lambda': 'wecare-payments-read'},
    {'path': '/payments/{paymentId}', 'method': 'GET', 'lambda': 'wecare-payments-read'},
]

def get_lambda_arn(lambda_name):
    """Get Lambda function ARN."""
    return f'arn:aws:lambda:{REGION}:{ACCOUNT_ID}:function:{lambda_name}'

def get_integration_uri(lambda_name):
    """Get Lambda integration URI for API Gateway."""
    return f'arn:aws:apigateway:{REGION}:lambda:path/2015-03-31/functions/{get_lambda_arn(lambda_name)}/invocations'

def main():
    # Initialize clients
    apigateway = boto3.client('apigatewayv2', region_name=REGION)
    lambda_client = boto3.client('lambda', region_name=REGION)
    
    print(f"Wiring API Gateway routes for API: {API_ID}")
    print("=" * 60)
    
    # Get existing routes
    existing_routes = {}
    try:
        response = apigateway.get_routes(ApiId=API_ID, MaxResults='100')
        for route in response.get('Items', []):
            existing_routes[route['RouteKey']] = route['RouteId']
        print(f"Found {len(existing_routes)} existing routes")
    except Exception as e:
        print(f"Error getting existing routes: {e}")
        return
    
    # Get existing integrations
    existing_integrations = {}
    try:
        response = apigateway.get_integrations(ApiId=API_ID, MaxResults='100')
        for integration in response.get('Items', []):
            existing_integrations[integration.get('IntegrationId')] = integration
        print(f"Found {len(existing_integrations)} existing integrations")
    except Exception as e:
        print(f"Error getting existing integrations: {e}")
    
    print("=" * 60)
    
    created_count = 0
    skipped_count = 0
    error_count = 0
    
    for route_config in ROUTES:
        route_key = f"{route_config['method']} {route_config['path']}"
        lambda_name = route_config['lambda']
        
        # Check if route already exists
        if route_key in existing_routes:
            print(f"⏭️  SKIP: {route_key} (already exists)")
            skipped_count += 1
            continue
        
        try:
            # Create integration
            print(f"🔧 Creating integration for {lambda_name}...")
            integration_response = apigateway.create_integration(
                ApiId=API_ID,
                IntegrationType='AWS_PROXY',
                IntegrationUri=get_integration_uri(lambda_name),
                IntegrationMethod='POST',
                PayloadFormatVersion='2.0',
                TimeoutInMillis=30000,
            )
            integration_id = integration_response['IntegrationId']
            print(f"   Integration created: {integration_id}")
            
            # Create route
            print(f"🛣️  Creating route: {route_key}...")
            route_response = apigateway.create_route(
                ApiId=API_ID,
                RouteKey=route_key,
                Target=f'integrations/{integration_id}',
                AuthorizationType='NONE',  # Adjust as needed
            )
            route_id = route_response['RouteId']
            print(f"   Route created: {route_id}")
            
            # Add Lambda permission for API Gateway to invoke
            try:
                statement_id = f'apigateway-{API_ID}-{route_config["method"]}-{route_config["path"].replace("/", "-").replace("{", "").replace("}", "")}'
                lambda_client.add_permission(
                    FunctionName=lambda_name,
                    StatementId=statement_id[:100],  # Max 100 chars
                    Action='lambda:InvokeFunction',
                    Principal='apigateway.amazonaws.com',
                    SourceArn=f'arn:aws:execute-api:{REGION}:{ACCOUNT_ID}:{API_ID}/*/{route_config["method"]}{route_config["path"]}',
                )
                print(f"   Lambda permission added")
            except lambda_client.exceptions.ResourceConflictException:
                print(f"   Lambda permission already exists")
            except Exception as e:
                print(f"   ⚠️  Lambda permission error: {e}")
            
            print(f"✅ SUCCESS: {route_key} -> {lambda_name}")
            created_count += 1
            
        except Exception as e:
            print(f"❌ ERROR: {route_key} - {e}")
            error_count += 1
    
    print("=" * 60)
    print(f"Summary:")
    print(f"  Created: {created_count}")
    print(f"  Skipped: {skipped_count}")
    print(f"  Errors:  {error_count}")
    
    if created_count > 0:
        print("\n⚠️  Note: You may need to deploy the API for changes to take effect:")
        print(f"   aws apigatewayv2 create-deployment --api-id {API_ID} --stage-name {STAGE}")

if __name__ == '__main__':
    main()
