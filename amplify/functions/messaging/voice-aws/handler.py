"""
AWS Voice Lambda Function

Purpose: Make and manage voice calls via AWS Connect in us-east-1
Supports: TTS, Audio playback, IVR, Outbound campaigns

AWS Services:
- Amazon Connect: Contact center with IVR
- Amazon Polly: Text-to-Speech
- Amazon Pinpoint Voice: Voice campaigns
"""

import os
import json
import uuid
import time
import logging
import boto3
from typing import Dict, Any
from decimal import Decimal

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients - us-east-1
REGION = 'us-east-1'
dynamodb = boto3.resource('dynamodb', region_name=REGION)
connect = boto3.client('connect', region_name=REGION)
polly = boto3.client('polly', region_name=REGION)

# Environment variables
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'base-wecare-digital-ContactsTable')
VOICE_CALLS_TABLE = os.environ.get('VOICE_CALLS_TABLE', 'base-wecare-digital-VoiceCalls')
CONNECT_INSTANCE_ID = os.environ.get('CONNECT_INSTANCE_ID', '')
CONNECT_CONTACT_FLOW_ID = os.environ.get('CONNECT_CONTACT_FLOW_ID', '')
CONNECT_QUEUE_ID = os.environ.get('CONNECT_QUEUE_ID', '')
SOURCE_PHONE_NUMBER = os.environ.get('SOURCE_PHONE_NUMBER', '')
CALL_TTL_SECONDS = 90 * 24 * 60 * 60  # 90 days


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle AWS voice call operations."""
    request_id = context.aws_request_id if context else 'local'
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'POST')
    path_params = event.get('pathParameters') or {}
    query_params = event.get('queryStringParameters') or {}
    
    logger.info(json.dumps({
        'event': 'aws_voice_handler',
        'method': http_method,
        'requestId': request_id
    }))
    
    try:
        # GET /voice-aws/calls - List calls
        if http_method == 'GET' and not path_params.get('callId'):
            return _list_calls(query_params, request_id)
        
        # GET /voice-aws/calls/{callId} - Get single call
        if http_method == 'GET' and path_params.get('callId'):
            return _get_call(path_params['callId'], request_id)
        
        # POST /voice-aws/call - Make a call
        if http_method == 'POST':
            body = json.loads(event.get('body', '{}'))
            return _make_call(body, request_id)
        
        return _response(405, {'error': 'Method not allowed'})
        
    except json.JSONDecodeError:
        return _response(400, {'error': 'Invalid JSON in request body'})
    except Exception as e:
        logger.error(json.dumps({
            'event': 'aws_voice_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _response(500, {'error': 'Internal server error'})


def _list_calls(params: Dict, request_id: str) -> Dict[str, Any]:
    """List AWS voice calls with optional filters."""
    try:
        table = dynamodb.Table(VOICE_CALLS_TABLE)
        
        from boto3.dynamodb.conditions import Attr
        
        scan_kwargs = {'Limit': int(params.get('limit', 100))}
        filter_expressions = [Attr('provider').eq('aws')]
        
        if params.get('contactId'):
            filter_expressions.append(Attr('contactId').eq(params['contactId']))
        if params.get('status'):
            filter_expressions.append(Attr('status').eq(params['status']))
        
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
        
        if call and call.get('provider') == 'aws':
            return _response(200, {'call': _normalize_call(call)})
        return _response(404, {'error': 'Call not found'})
        
    except Exception as e:
        logger.error(f"Get call error: {str(e)}")
        return _response(500, {'error': str(e)})


def _make_call(body: Dict, request_id: str) -> Dict[str, Any]:
    """Initiate an AWS voice call via Amazon Connect."""
    phone_number = body.get('phoneNumber')
    contact_id = body.get('contactId')
    call_type = body.get('callType', 'tts')  # tts, audio
    message_text = body.get('messageText', '')
    voice_id = body.get('voiceId', 'Joanna')  # AWS Polly voice
    audio_url = body.get('audioUrl')
    
    if not phone_number:
        # Try to get phone from contact
        if contact_id:
            contact = _get_contact(contact_id)
            phone_number = contact.get('phone') if contact else None
        
        if not phone_number:
            return _response(400, {'error': 'phoneNumber is required'})
    
    # Validate phone format
    phone_clean = _clean_phone_number(phone_number)
    if not phone_clean:
        return _response(400, {'error': 'Invalid phone number format'})
    
    # Generate call ID
    call_id = str(uuid.uuid4())
    
    # Make call via AWS Connect
    result = _make_aws_connect_call(
        phone=phone_clean,
        call_type=call_type,
        message=message_text,
        voice_id=voice_id,
        audio_url=audio_url,
        request_id=request_id
    )
    
    # Store call record
    _store_call(
        call_id=call_id,
        contact_id=contact_id or '',
        phone=phone_clean,
        call_type=call_type,
        status=result.get('status', 'failed'),
        provider_call_id=result.get('providerCallId'),
        extra_data={
            'voiceId': voice_id,
            'messageText': message_text[:500] if message_text else ''
        }
    )
    
    if not result.get('success'):
        return _response(500, {
            'error': result.get('error', 'Failed to initiate call'),
            'callId': call_id
        })
    
    logger.info(json.dumps({
        'event': 'aws_call_initiated',
        'callId': call_id,
        'phoneNumber': phone_clean[-4:],
        'callType': call_type,
        'requestId': request_id
    }))
    
    return _response(200, {
        'callId': call_id,
        'status': 'initiated',
        'providerCallId': result.get('providerCallId'),
        'message': 'AWS Connect call initiated'
    })


def _make_aws_connect_call(phone: str, call_type: str, message: str,
                           voice_id: str, audio_url: str, request_id: str) -> Dict[str, Any]:
    """Make call via AWS Connect."""
    try:
        if not CONNECT_INSTANCE_ID or not CONNECT_CONTACT_FLOW_ID:
            return {'success': False, 'error': 'AWS Connect not configured. Set CONNECT_INSTANCE_ID and CONNECT_CONTACT_FLOW_ID.'}
        
        # Build attributes for contact flow
        attributes = {
            'callType': call_type,
            'voiceId': voice_id,
            'source': 'wecare-digital'
        }
        
        if call_type == 'tts' and message:
            # Generate SSML for better TTS
            ssml_message = f'<speak>{message}</speak>'
            attributes['messageText'] = message
            attributes['ssmlMessage'] = ssml_message
        elif call_type == 'audio' and audio_url:
            attributes['audioUrl'] = audio_url
        
        # Format phone number for Connect (E.164)
        formatted_phone = _format_e164(phone)
        
        # Start outbound call
        call_params = {
            'DestinationPhoneNumber': formatted_phone,
            'ContactFlowId': CONNECT_CONTACT_FLOW_ID,
            'InstanceId': CONNECT_INSTANCE_ID,
            'Attributes': attributes,
        }
        
        if SOURCE_PHONE_NUMBER:
            call_params['SourcePhoneNumber'] = SOURCE_PHONE_NUMBER
        
        if CONNECT_QUEUE_ID:
            call_params['QueueId'] = CONNECT_QUEUE_ID
        
        response = connect.start_outbound_voice_contact(**call_params)
        
        return {
            'success': True,
            'status': 'initiated',
            'providerCallId': response.get('ContactId')
        }
        
    except connect.exceptions.InvalidParameterException as e:
        logger.error(f"AWS Connect invalid param: {str(e)}")
        return {'success': False, 'error': f'Invalid parameter: {str(e)}'}
    except connect.exceptions.DestinationNotAllowedException as e:
        logger.error(f"AWS Connect destination not allowed: {str(e)}")
        return {'success': False, 'error': 'Destination phone number not allowed'}
    except connect.exceptions.OutboundContactNotPermittedException as e:
        logger.error(f"AWS Connect outbound not permitted: {str(e)}")
        return {'success': False, 'error': 'Outbound calls not permitted for this instance'}
    except Exception as e:
        logger.error(f"AWS Connect error: {str(e)}")
        return {'success': False, 'error': str(e)}


def _synthesize_speech(text: str, voice_id: str) -> Dict[str, Any]:
    """Synthesize speech using Amazon Polly."""
    try:
        response = polly.synthesize_speech(
            Text=text,
            OutputFormat='mp3',
            VoiceId=voice_id,
            Engine='neural'  # Use neural engine for better quality
        )
        return {
            'success': True,
            'audioStream': response.get('AudioStream')
        }
    except Exception as e:
        logger.error(f"Polly error: {str(e)}")
        return {'success': False, 'error': str(e)}


def _clean_phone_number(phone: str) -> str:
    """Clean phone number to digits only."""
    if not phone:
        return ''
    return ''.join(c for c in phone if c.isdigit())


def _format_e164(phone: str) -> str:
    """Format phone number to E.164 format."""
    digits = _clean_phone_number(phone)
    
    # If already has country code
    if len(digits) >= 11:
        return f'+{digits}'
    
    # Assume US/Canada if 10 digits
    if len(digits) == 10:
        return f'+1{digits}'
    
    return f'+{digits}'


def _get_contact(contact_id: str) -> Dict[str, Any]:
    """Get contact from DynamoDB."""
    try:
        table = dynamodb.Table(CONTACTS_TABLE)
        response = table.get_item(Key={'contactId': contact_id})
        return response.get('Item', {})
    except Exception:
        return {}


def _store_call(call_id: str, contact_id: str, phone: str, call_type: str,
                status: str, provider_call_id: str = None, extra_data: Dict = None) -> None:
    """Store call record in DynamoDB."""
    try:
        now = int(time.time())
        table = dynamodb.Table(VOICE_CALLS_TABLE)
        
        item = {
            'id': call_id,
            'callId': call_id,
            'contactId': contact_id,
            'phoneNumber': phone,
            'provider': 'aws',
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
            item['connectContactId'] = provider_call_id
        
        if extra_data:
            for key, value in extra_data.items():
                if value:
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
        'provider': 'aws',
        'callType': item.get('callType', ''),
        'status': item.get('status', ''),
        'direction': item.get('direction', 'OUTBOUND'),
        'duration': int(item.get('duration', 0)),
        'recordingUrl': item.get('recordingUrl', ''),
        'connectContactId': item.get('connectContactId', ''),
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
