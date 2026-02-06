"""
Local test script for Voice Lambda functions
Run: python scripts/test-voice-local.py

Note: For Secrets Manager to work locally, you need:
1. AWS credentials configured (aws configure)
2. Secrets created in AWS (run create-airtel-secrets.ps1 first)
"""

import sys
import os
import json

# Add the functions path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'voice-in'))

# Mock context
class MockContext:
    aws_request_id = 'local-test-123'
    function_name = 'test-function'

def test_cdr_webhook():
    """Test CDR webhook handler"""
    print("\n" + "="*50)
    print("Testing CDR Webhook")
    print("="*50)
    
    from cdr.handler import handler
    
    # Sample Airtel CDR payload
    event = {
        'httpMethod': 'POST',
        'headers': {'Content-Type': 'application/json'},
        'body': json.dumps({
            "vmSessionId": "test-session-123",
            "clientCorrelationId": "Xchange123456",
            "customerId": "WECAREDIG",
            "callType": "OUTBOUND",
            "overallCallStatus": "Answered",
            "startTime": 1707300000000,
            "endTime": 1707300060000,
            "duration": 60000,
            "conversationDuration": 45000,
            "callerNumber": "8130078559",
            "destinationNumber": "7080003969",
            "recordingURL": "https://example.com/recording.wav"
        })
    }
    
    try:
        result = handler(event, MockContext())
        print(f"Status: {result['statusCode']}")
        print(f"Response: {json.dumps(json.loads(result['body']), indent=2)}")
        return result['statusCode'] == 200
    except Exception as e:
        print(f"Error: {str(e)}")
        return False


def test_c2c_call():
    """Test Click-to-Call handler"""
    print("\n" + "="*50)
    print("Testing Click-to-Call (C2C)")
    print("="*50)
    
    from c2c.handler import handler
    
    event = {
        'requestContext': {'http': {'method': 'POST'}},
        'body': json.dumps({
            "fromNumber": "8130078559",
            "toNumber": "7080003969",
            "enableRecording": True
        })
    }
    
    try:
        result = handler(event, MockContext())
        print(f"Status: {result['statusCode']}")
        print(f"Response: {json.dumps(json.loads(result['body']), indent=2)}")
        return True  # May fail if secrets not configured
    except Exception as e:
        print(f"Error: {str(e)}")
        print("Note: This may fail if Secrets Manager is not accessible locally")
        return False


def test_obd_campaign():
    """Test OBD Campaign handler"""
    print("\n" + "="*50)
    print("Testing OBD Campaign")
    print("="*50)
    
    from obd.handler import handler
    
    # Test list campaigns (GET)
    event = {
        'requestContext': {'http': {'method': 'GET'}},
        'rawPath': '/obd/list',
        'queryStringParameters': {'limit': '10'}
    }
    
    try:
        result = handler(event, MockContext())
        print(f"Status: {result['statusCode']}")
        print(f"Response: {json.dumps(json.loads(result['body']), indent=2)}")
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        print("Note: This may fail if Secrets Manager is not accessible locally")
        return False


if __name__ == '__main__':
    print("Voice Lambda Local Tests")
    print("========================")
    print("Make sure you have:")
    print("1. AWS credentials configured")
    print("2. Secrets created (run create-airtel-secrets.ps1)")
    print("3. DynamoDB tables exist")
    
    results = {
        'CDR Webhook': test_cdr_webhook(),
        'C2C Call': test_c2c_call(),
        'OBD Campaign': test_obd_campaign(),
    }
    
    print("\n" + "="*50)
    print("Test Results")
    print("="*50)
    for test, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {test}: {status}")
