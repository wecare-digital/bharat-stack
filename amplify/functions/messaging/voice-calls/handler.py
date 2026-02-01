"""
Voice Calls Lambda Function

Purpose: Make and manage voice calls via AWS Connect or Airtel CCP
Supports: TTS, Audio playback, IVR, Click-to-call (C2C)

Airtel CCP Click-to-Call API:
- Connects two users on a call with recording
- Initiates call to first participant, then patches second participant
- Real-time events and CDR with recording URL
"""

import os
import json
import uuid
import time
import logging
import boto3
import base64
import urllib.request
import urllib.error
from typing import Dict, Any
from decimal import Decimal

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
connect = boto3.client('connect', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
polly = boto3.client('polly', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Environment variables
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'base-wecare-digital-ContactsTable')
VOICE_CALLS_TABLE = os.environ.get('VOICE_CALLS_TABLE', 'base-wecare-digital-VoiceCalls')
CONNECT_INSTANCE_ID = os.environ.get('CONNECT_INSTANCE_ID', '')
CONNECT_CONTACT_FLOW_ID = os.environ.get('CONNECT_CONTACT_FLOW_ID', '')
CONNECT_QUEUE_ID = os.environ.get('CONNECT_QUEUE_ID', '')
SOURCE_PHONE_NUMBER = os.environ.get('SOURCE_PHONE_NUMBER', '')
CALL_TTL_SECONDS = 90 * 24 * 60 * 60  # 90 days

# Airtel CCP Configuration
AIRTEL_CCP_HOST = os.environ.get('AIRTEL_CCP_HOST', 'cpaas.airtel.in')
AIRTEL_CCP_USERNAME = os.environ.get('AIRTEL_CCP_USERNAME', '')
AIRTEL_CCP_PASSWORD = os.environ.get('AIRTEL_CCP_PASSWORD', '')
AIRTEL_CCP_CALL_FLOW_ID = os.environ.get('AIRTEL_CCP_CALL_FLOW_ID', '')
AIRTEL_CCP_CUSTOMER_ID = os.environ.get('AIRTEL_CCP_CUSTOMER_ID', '')
AIRTEL_CCP_CALLER_ID = os.environ.get('AIRTEL_CCP_CALLER_ID', '9319767034')  # Virtual number
AIRTEL_CDR_WEBHOOK_URL = os.environ.get('AIRTEL_CDR_WEBHOOK_URL', 'https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod/voice-cdr-webhook')
AIRTEL_EVENTS_WEBHOOK_URL = os.environ.get('AIRTEL_EVENTS_WEBHOOK_URL', 'https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod/voice-cdr-webhook')


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle voice call operations."""
    request_id = context.aws_request_id if context else 'local'
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'POST')
    path_params = event.get('pathParameters') or {}
    query_params = event.get('queryStringParameters') or {}
    
    logger.info(json.dumps({
        'event': 'voice_calls_handler',
        'method': http_method,
        'requestId': request_id
    }))
    
    try:
        # GET /voice/calls - List calls
        if http_method == 'GET' and not path_params.get('callId'):
            return _list_calls(query_params, request_id)
        
        # GET /voice/calls/{callId} - Get single call
        if http_method == 'GET' and path_params.get('callId'):
            return _get_call(path_params['callId'], request_id)
        
        # POST /voice/call - Make a call
        if http_method == 'POST':
            body = json.loads(event.get('body', '{}'))
            return _make_call(body, request_id)
        
        return _response(405, {'error': 'Method not allowed'})
        
    except json.JSONDecodeError:
        return _response(400, {'error': 'Invalid JSON in request body'})
    except Exception as e:
        logger.error(json.dumps({
            'event': 'voice_calls_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _response(500, {'error': 'Internal server error'})


def _list_calls(params: Dict, request_id: str) -> Dict[str, Any]:
    """List voice calls with optional filters."""
    try:
        table = dynamodb.Table(VOICE_CALLS_TABLE)
        
        scan_kwargs = {'Limit': int(params.get('limit', 100))}
        filter_expressions = []
        
        from boto3.dynamodb.conditions import Attr
        
        if params.get('contactId'):
            filter_expressions.append(Attr('contactId').eq(params['contactId']))
        if params.get('provider'):
            filter_expressions.append(Attr('provider').eq(params['provider']))
        if params.get('status'):
            filter_expressions.append(Attr('status').eq(params['status']))
        
        if filter_expressions:
            combined = filter_expressions[0]
            for expr in filter_expressions[1:]:
                combined = combined & expr
            scan_kwargs['FilterExpression'] = combined
        
        result = table.scan(**scan_kwargs)
        calls = result.get('Items', [])
        
        # Sort by createdAt descending
        calls.sort(key=lambda x: float(x.get('createdAt', 0)), reverse=True)
        
        return _response(200, {
            'calls': [_normalize_call(c) for c in calls],
            'count': len(calls)
        })
        
    except Exception as e:
        logger.error(f"List calls error: {str(e)}")
        return _response(500, {'error': str(e)})


def _get_call(call_id: str, request_id: str) -> Dict[str, Any]:
    """Get a single voice call."""
    try:
        table = dynamodb.Table(VOICE_CALLS_TABLE)
        result = table.get_item(Key={'id': call_id})
        call = result.get('Item')
        
        if call:
            return _response(200, {'call': _normalize_call(call)})
        return _response(404, {'error': 'Call not found'})
        
    except Exception as e:
        logger.error(f"Get call error: {str(e)}")
        return _response(500, {'error': str(e)})


def _make_call(body: Dict, request_id: str) -> Dict[str, Any]:
    """Initiate a voice call."""
    phone_number = body.get('phoneNumber')
    contact_id = body.get('contactId')
    provider = body.get('provider', 'aws')
    call_type = body.get('callType', 'tts')  # tts, audio, c2c (click-to-call)
    message_text = body.get('messageText', '')
    voice_id = body.get('voiceId', 'Aditi')  # Indian English voice
    audio_url = body.get('audioUrl')
    
    # Click-to-Call specific params
    from_number = body.get('fromNumber')  # First participant (agent/caller)
    to_number = body.get('toNumber')  # Second participant (customer)
    enable_recording = body.get('enableRecording', True)
    
    # Handle C2C call type
    if call_type == 'c2c':
        if not from_number or not to_number:
            return _response(400, {'error': 'fromNumber and toNumber are required for click-to-call'})
        
        # Generate call ID
        call_id = str(uuid.uuid4())
        
        # Make C2C call via Airtel CCP
        result = _make_airtel_c2c_call(from_number, to_number, enable_recording, request_id)
        
        # Store call record
        _store_call(
            call_id=call_id,
            contact_id=contact_id or '',
            phone=to_number,
            provider='airtel_ccp',
            call_type='c2c',
            status=result.get('status', 'failed'),
            provider_call_id=result.get('providerCallId'),
            extra_data={
                'fromNumber': from_number,
                'toNumber': to_number,
                'enableRecording': enable_recording
            }
        )
        
        if not result.get('success'):
            return _response(500, {
                'error': result.get('error', 'Failed to initiate click-to-call'),
                'errorCode': result.get('errorCode'),
                'callId': call_id
            })
        
        logger.info(json.dumps({
            'event': 'c2c_call_initiated',
            'callId': call_id,
            'fromNumber': from_number,
            'toNumber': to_number,
            'correlationId': result.get('providerCallId'),
            'requestId': request_id
        }))
        
        return _response(200, {
            'callId': call_id,
            'status': 'initiated',
            'correlationId': result.get('providerCallId'),
            'message': 'Click-to-call initiated. First participant will be called, then connected to second participant.'
        })
    
    # Standard outbound call (TTS/Audio)
    if not phone_number:
        # Try to get phone from contact
        if contact_id:
            contact = _get_contact(contact_id)
            phone_number = contact.get('phone') if contact else None
        
        if not phone_number:
            return _response(400, {'error': 'phoneNumber is required'})
    
    # Generate call ID
    call_id = str(uuid.uuid4())
    now = int(time.time())
    
    # Make call based on provider
    if provider == 'airtel':
        result = _make_airtel_call(phone_number, call_type, message_text, audio_url, request_id)
    else:
        result = _make_aws_call(phone_number, call_type, message_text, voice_id, audio_url, request_id)
    
    # Store call record
    _store_call(call_id, contact_id, phone_number, provider, call_type, 
                result.get('status', 'initiated'), result.get('providerCallId'))
    
    if not result.get('success'):
        return _response(500, {
            'error': result.get('error', 'Failed to initiate call'),
            'callId': call_id
        })
    
    logger.info(json.dumps({
        'event': 'call_initiated',
        'callId': call_id,
        'phoneNumber': phone_number,
        'provider': provider,
        'callType': call_type,
        'requestId': request_id
    }))
    
    return _response(200, {
        'callId': call_id,
        'status': 'initiated',
        'providerCallId': result.get('providerCallId')
    })


def _make_aws_call(phone: str, call_type: str, message: str, 
                   voice_id: str, audio_url: str, request_id: str) -> Dict[str, Any]:
    """Make call via AWS Connect."""
    try:
        if not CONNECT_INSTANCE_ID or not CONNECT_CONTACT_FLOW_ID:
            return {'success': False, 'error': 'AWS Connect not configured'}
        
        # Build attributes for contact flow
        attributes = {
            'callType': call_type,
            'voiceId': voice_id,
        }
        
        if call_type == 'tts' and message:
            attributes['messageText'] = message
        elif call_type == 'audio' and audio_url:
            attributes['audioUrl'] = audio_url
        
        # Start outbound call
        response = connect.start_outbound_voice_contact(
            DestinationPhoneNumber=phone,
            ContactFlowId=CONNECT_CONTACT_FLOW_ID,
            InstanceId=CONNECT_INSTANCE_ID,
            SourcePhoneNumber=SOURCE_PHONE_NUMBER,
            Attributes=attributes,
            QueueId=CONNECT_QUEUE_ID if CONNECT_QUEUE_ID else None,
        )
        
        return {
            'success': True,
            'status': 'initiated',
            'providerCallId': response.get('ContactId')
        }
        
    except Exception as e:
        logger.error(f"AWS Connect error: {str(e)}")
        return {'success': False, 'error': str(e)}


def _make_airtel_call(phone: str, call_type: str, message: str, 
                      audio_url: str, request_id: str) -> Dict[str, Any]:
    """Make call via Airtel IQ Voice API (legacy)."""
    try:
        airtel_api_key = os.environ.get('AIRTEL_API_KEY', '')
        airtel_caller_id = os.environ.get('AIRTEL_CALLER_ID', '')
        
        if not airtel_api_key:
            return {'success': False, 'error': 'Airtel API key not configured'}
        
        # Airtel IQ Voice API endpoint
        url = 'https://iqvoice.airtel.in/api/v1/outbound-call'
        
        payload = {
            'apiKey': airtel_api_key,
            'callerId': airtel_caller_id,
            'to': phone,
            'callType': call_type,
        }
        
        if call_type == 'tts':
            payload['text'] = message
            payload['language'] = 'en-IN'
        elif call_type == 'audio':
            payload['audioUrl'] = audio_url
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            if result.get('status') == 'success':
                return {
                    'success': True,
                    'status': 'initiated',
                    'providerCallId': result.get('callId')
                }
            return {'success': False, 'error': result.get('message', 'Airtel API error')}
            
    except Exception as e:
        logger.error(f"Airtel Voice error: {str(e)}")
        return {'success': False, 'error': str(e)}


def _make_airtel_c2c_call(from_number: str, to_number: str, 
                          enable_recording: bool, request_id: str) -> Dict[str, Any]:
    """
    Make Click-to-Call via Airtel CCP API.
    
    This connects two participants:
    - First participant (from_number) is called first
    - Once answered, second participant (to_number) is called
    - Both are patched together with optional recording
    
    API: POST /v2/execute/workflow
    """
    try:
        if not AIRTEL_CCP_USERNAME or not AIRTEL_CCP_PASSWORD:
            return {'success': False, 'error': 'Airtel CCP credentials not configured'}
        
        if not AIRTEL_CCP_CALL_FLOW_ID or not AIRTEL_CCP_CUSTOMER_ID:
            return {'success': False, 'error': 'Airtel CCP call flow not configured'}
        
        # Clean phone numbers (ensure 10 digits)
        from_clean = _clean_phone_number(from_number)
        to_clean = _clean_phone_number(to_number)
        
        if not from_clean or not to_clean:
            return {'success': False, 'error': 'Invalid phone number format'}
        
        # Build Basic Auth header
        credentials = f"{AIRTEL_CCP_USERNAME}:{AIRTEL_CCP_PASSWORD}"
        auth_header = base64.b64encode(credentials.encode()).decode()
        
        # Build Click-to-Call payload per Airtel CCP spec
        payload = {
            "callFlowId": AIRTEL_CCP_CALL_FLOW_ID,
            "customerId": AIRTEL_CCP_CUSTOMER_ID,
            "callType": "OUTBOUND",
            "callFlowConfiguration": {
                "initiateCall_1": {
                    "callerId": AIRTEL_CCP_CALLER_ID,
                    "mergingStrategy": "SEQUENTIAL",
                    "maxTime": 0,
                    "participants": [
                        {
                            "participantAddress": from_clean,
                            "callerId": AIRTEL_CCP_CALLER_ID,
                            "participantName": "A",
                            "maxRetries": 1,
                            "maxTime": 0
                        }
                    ],
                    "callBackURLs": [
                        {
                            "eventType": "CDR",
                            "notifyURL": AIRTEL_CDR_WEBHOOK_URL,
                            "method": "POST",
                            "headers": {}
                        },
                        {
                            "eventType": "ALL",
                            "notifyURL": AIRTEL_EVENTS_WEBHOOK_URL,
                            "method": "POST",
                            "headers": {}
                        }
                    ]
                },
                "addParticipant_1": {
                    "mergingStrategy": "SEQUENTIAL",
                    "maxTime": 0,
                    "participants": [
                        {
                            "participantAddress": to_clean,
                            "callerId": AIRTEL_CCP_CALLER_ID,
                            "participantName": "B",
                            "maxRetries": 1,
                            "maxTime": 0,
                            "enableEarlyMedia": True
                        }
                    ]
                },
                "record": {
                    "enabled": enable_recording
                }
            }
        }
        
        url = f"https://{AIRTEL_CCP_HOST}/v2/execute/workflow"
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {auth_header}'
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        
        logger.info(json.dumps({
            'event': 'airtel_c2c_request',
            'url': url,
            'from': from_clean,
            'to': to_clean,
            'requestId': request_id
        }))
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            logger.info(json.dumps({
                'event': 'airtel_c2c_response',
                'status': result.get('status'),
                'correlationId': result.get('correlationId'),
                'requestId': request_id
            }))
            
            if result.get('status') == 'success':
                return {
                    'success': True,
                    'status': 'initiated',
                    'providerCallId': result.get('correlationId')
                }
            
            return {
                'success': False, 
                'error': result.get('errorMessage', 'Airtel CCP API error'),
                'errorCode': result.get('errorCode')
            }
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(json.dumps({
            'event': 'airtel_c2c_http_error',
            'status': e.code,
            'error': error_body,
            'requestId': request_id
        }))
        
        # Parse error response
        try:
            error_data = json.loads(error_body)
            error_msg = error_data.get('errorMessage', f'HTTP {e.code}')
        except:
            error_msg = f'HTTP {e.code}: {error_body[:200]}'
        
        return {'success': False, 'error': error_msg}
        
    except Exception as e:
        logger.error(f"Airtel C2C error: {str(e)}")
        return {'success': False, 'error': str(e)}


def _clean_phone_number(phone: str) -> str:
    """Clean phone number to 10 digits for Airtel CCP."""
    if not phone:
        return ''
    
    # Remove all non-digits
    digits = ''.join(c for c in phone if c.isdigit())
    
    # Handle +91 prefix
    if digits.startswith('91') and len(digits) == 12:
        digits = digits[2:]
    
    # Handle 0 prefix
    if digits.startswith('0') and len(digits) == 11:
        digits = digits[1:]
    
    # Validate 10 digits
    if len(digits) == 10:
        return digits
    
    return ''


def _get_contact(contact_id: str) -> Dict[str, Any]:
    """Get contact from DynamoDB."""
    try:
        table = dynamodb.Table(CONTACTS_TABLE)
        response = table.get_item(Key={'contactId': contact_id})
        return response.get('Item', {})
    except Exception:
        return {}


def _store_call(call_id: str, contact_id: str, phone: str, provider: str,
                call_type: str, status: str, provider_call_id: str = None,
                extra_data: Dict = None) -> None:
    """Store call record in DynamoDB."""
    try:
        now = int(time.time())
        table = dynamodb.Table(VOICE_CALLS_TABLE)
        
        item = {
            'id': call_id,
            'callId': call_id,
            'contactId': contact_id or '',
            'phoneNumber': phone,
            'provider': provider,
            'callType': call_type,
            'status': status,
            'direction': 'OUTBOUND',
            'duration': 0,
            'createdAt': Decimal(str(now)),
            'updatedAt': Decimal(str(now)),
            'ttl': Decimal(str(now + CALL_TTL_SECONDS)),
        }
        
        if provider_call_id:
            item['providerCallId'] = provider_call_id
            item['correlationId'] = provider_call_id
        
        # Add extra data for C2C calls
        if extra_data:
            for key, value in extra_data.items():
                item[key] = value
        
        table.put_item(Item=item)
        
    except Exception as e:
        logger.error(f"Store call error: {str(e)}")


def _normalize_call(item: Dict) -> Dict:
    """Normalize call record for API response."""
    return {
        'id': item.get('id', ''),
        'callId': item.get('callId', ''),
        'contactId': item.get('contactId', ''),
        'phoneNumber': item.get('phoneNumber', ''),
        'provider': item.get('provider', ''),
        'callType': item.get('callType', ''),
        'status': item.get('status', ''),
        'direction': item.get('direction', 'OUTBOUND'),
        'duration': int(item.get('duration', 0)),
        'recordingUrl': item.get('recordingUrl', ''),
        'createdAt': int(float(item.get('createdAt', 0))),
        'updatedAt': int(float(item.get('updatedAt', 0))),
    }


def _response(status_code: int, body: Dict) -> Dict[str, Any]:
    """Return HTTP response with CORS headers."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS'
        },
        'body': json.dumps(body, default=str)
    }
