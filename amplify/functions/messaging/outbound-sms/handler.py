"""
Outbound SMS Lambda Function

Purpose: Send SMS messages via AWS SNS/Pinpoint or Airtel IQ
Supports: AWS SNS, AWS Pinpoint, Airtel IQ SMS with DLT compliance

Airtel IQ SMS API:
- v4/send-sms: Standard DLT compliant SMS
- v5/send-sms-cm: Content Moderation SMS
- v6/send-sms: Enhanced response with full details
- Requires: customerId, entityId, dltTemplateId, sourceAddress (header)
- Message Types: PROMOTIONAL, TRANSACTIONAL, SERVICE_IMPLICIT, SERVICE_EXPLICIT
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

from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin

# Configure logging
from lambda_utils.logging import get_logger

logger = get_logger(__name__)

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
sns = boto3.client('sns', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
pinpoint = boto3.client('pinpoint', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Environment variables
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'base-wecare-digital-ContactsTable')
MESSAGES_TABLE = os.environ.get('MESSAGES_TABLE', 'base-wecare-digital-MessagesTable')
PINPOINT_APP_ID = os.environ.get('PINPOINT_APP_ID', '')
ORIGINATION_NUMBER = os.environ.get('ORIGINATION_NUMBER', '')
SENDER_ID = os.environ.get('SENDER_ID', 'WECARE')
MESSAGE_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days

# Airtel IQ SMS Configuration
AIRTEL_IQ_HOST = os.environ.get('AIRTEL_IQ_HOST', 'iqmessaging.airtel.in')
AIRTEL_IQ_USERNAME = os.environ.get('AIRTEL_IQ_USERNAME', '')
AIRTEL_IQ_PASSWORD = os.environ.get('AIRTEL_IQ_PASSWORD', '')
AIRTEL_IQ_CUSTOMER_ID = os.environ.get('AIRTEL_IQ_CUSTOMER_ID', '')
# DLT Registration - WECARE.DIGITAL
AIRTEL_IQ_ENTITY_ID = os.environ.get('AIRTEL_IQ_ENTITY_ID', '1201161991108627443')  # PE ID
AIRTEL_IQ_SOURCE_ADDRESS = os.environ.get('AIRTEL_IQ_SOURCE_ADDRESS', 'WDBEEP')  # Header
# Default DLT Template ID for selfservice IVR
DEFAULT_DLT_TEMPLATE_ID = '1007974344269130859'


# Module-level origin for CORS (set per-invocation in handler)
origin = ''


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Send SMS message."""
    request_id = context.aws_request_id if context else 'local'
    global origin
    origin = extract_origin(event)

    logger.info(json.dumps({
        'event': 'outbound_sms_start',
        'requestId': request_id
    }))
    
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        contact_id = body.get('contactId')
        phone_number = body.get('phoneNumber')  # Direct phone number (optional)
        content = body.get('content', '')
        provider = body.get('provider', 'aws')  # aws or airtel
        
        # Airtel IQ specific params
        message_type = body.get('messageType', 'SERVICE_IMPLICIT')  # PROMOTIONAL, TRANSACTIONAL, SERVICE_IMPLICIT, SERVICE_EXPLICIT
        dlt_template_id = body.get('dltTemplateId', '')
        entity_id = body.get('entityId', AIRTEL_IQ_ENTITY_ID)
        source_address = body.get('sourceAddress', AIRTEL_IQ_SOURCE_ADDRESS)
        is_otp = body.get('otp', False)  # For SERVICE_IMPLICIT, indicates OTP traffic
        meta_data = body.get('metaData', {})
        api_version = body.get('apiVersion', 'v4')  # v4, v5 (content moderation), v6 (enhanced)
        
        if not contact_id and not phone_number:
            return _response(400, {'error': 'contactId or phoneNumber is required'})
        
        if not content:
            return _response(400, {'error': 'content is required'})
        
        # Get phone number
        phone = phone_number
        contact = None
        
        if contact_id:
            contact = _get_contact(contact_id)
            if not contact:
                return _response(404, {'error': 'Contact not found'})
            phone = contact.get('phone', '') or phone_number
        
        if not phone:
            return _response(400, {'error': 'No phone number available'})
        
        # Check opt-in status (if contact exists)
        if contact and not contact.get('optInSms', False) and not contact.get('allowlistSms', False):
            return _response(403, {'error': 'Contact has not opted in for SMS'})
        
        # Generate message ID
        message_id = str(uuid.uuid4())
        
        # Send SMS based on provider
        if provider == 'airtel':
            result = _send_airtel_iq_sms(
                phone=phone,
                content=content,
                message_type=message_type,
                dlt_template_id=dlt_template_id,
                entity_id=entity_id,
                source_address=source_address,
                is_otp=is_otp,
                meta_data=meta_data,
                api_version=api_version,
                request_id=request_id
            )
        else:
            result = _send_aws_sms(phone, content, request_id)
        
        if not result.get('success'):
            # Store failed message
            _store_message(message_id, contact_id or '', content, 'FAILED', result.get('error'))
            return _response(500, {
                'error': result.get('error', 'Failed to send SMS'),
                'messageId': message_id
            })
        
        # Store successful message
        _store_message(
            message_id, 
            contact_id or '', 
            content, 
            'SENT', 
            None, 
            result.get('providerMessageId'),
            extra_data={
                'provider': provider,
                'messageType': message_type,
                'dltTemplateId': dlt_template_id,
                'sourceAddress': source_address
            }
        )
        
        logger.info(json.dumps({
            'event': 'sms_sent',
            'messageId': message_id,
            'contactId': contact_id,
            'provider': provider,
            'messageType': message_type,
            'requestId': request_id
        }))
        
        return _response(200, {
            'messageId': message_id,
            'status': 'sent',
            'providerMessageId': result.get('providerMessageId'),
            'messageRequestId': result.get('messageRequestId')
        })
        
    except json.JSONDecodeError:
        return _response(400, {'error': 'Invalid JSON in request body'})
    except Exception as e:
        logger.error(json.dumps({
            'event': 'outbound_sms_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _response(500, {'error': 'Internal server error'})


def _get_contact(contact_id: str) -> Dict[str, Any]:
    """Get contact from DynamoDB."""
    try:
        table = dynamodb.Table(CONTACTS_TABLE)
        response = table.get_item(Key={'contactId': contact_id})
        return response.get('Item', {})
    except Exception as e:
        logger.error(f"Get contact error: {str(e)}")
        return {}


def _send_aws_sms(phone: str, content: str, request_id: str) -> Dict[str, Any]:
    """Send SMS via AWS SNS/Pinpoint."""
    try:
        # Use Pinpoint if configured
        if PINPOINT_APP_ID:
            response = pinpoint.send_messages(
                ApplicationId=PINPOINT_APP_ID,
                MessageRequest={
                    'Addresses': {
                        phone: {'ChannelType': 'SMS'}
                    },
                    'MessageConfiguration': {
                        'SMSMessage': {
                            'Body': content,
                            'MessageType': 'TRANSACTIONAL',
                            'OriginationNumber': ORIGINATION_NUMBER or None,
                            'SenderId': SENDER_ID,
                        }
                    }
                }
            )
            result = response.get('MessageResponse', {}).get('Result', {}).get(phone, {})
            if result.get('StatusCode') == 200:
                return {'success': True, 'providerMessageId': result.get('MessageId')}
            return {'success': False, 'error': result.get('StatusMessage', 'Pinpoint error')}
        
        # Fallback to SNS
        response = sns.publish(
            PhoneNumber=phone,
            Message=content,
            MessageAttributes={
                'AWS.SNS.SMS.SenderID': {
                    'DataType': 'String',
                    'StringValue': SENDER_ID
                },
                'AWS.SNS.SMS.SMSType': {
                    'DataType': 'String',
                    'StringValue': 'Transactional'
                }
            }
        )
        return {'success': True, 'providerMessageId': response.get('MessageId')}
        
    except Exception as e:
        logger.error(f"AWS SMS error: {str(e)}")
        return {'success': False, 'error': str(e)}


def _send_airtel_iq_sms(phone: str, content: str, message_type: str,
                        dlt_template_id: str, entity_id: str, source_address: str,
                        is_otp: bool, meta_data: Dict, api_version: str,
                        request_id: str) -> Dict[str, Any]:
    """
    Send SMS via Airtel IQ API with DLT compliance.
    
    API Versions:
    - v4: Standard DLT compliant SMS
    - v5: Content Moderation SMS (auto DLT)
    - v6: Enhanced response with full details
    
    Message Types:
    - PROMOTIONAL: Marketing messages (DND checked)
    - TRANSACTIONAL: Transaction alerts
    - SERVICE_IMPLICIT: Service messages with implicit consent
    - SERVICE_EXPLICIT: Service messages requiring explicit consent
    """
    try:
        if not AIRTEL_IQ_USERNAME or not AIRTEL_IQ_PASSWORD:
            return {'success': False, 'error': 'Airtel IQ credentials not configured'}
        
        if not AIRTEL_IQ_CUSTOMER_ID:
            return {'success': False, 'error': 'Airtel IQ customer ID not configured'}
        
        # Clean phone number (10 or 12 digits)
        phone_clean = _clean_phone_for_sms(phone)
        if not phone_clean:
            return {'success': False, 'error': 'Invalid phone number format (must be 10 or 12 digits)'}
        
        # Build Basic Auth header
        credentials = f"{AIRTEL_IQ_USERNAME}:{AIRTEL_IQ_PASSWORD}"
        auth_header = base64.b64encode(credentials.encode()).decode()
        
        # Determine API endpoint
        if api_version == 'v5':
            # Content Moderation API - simpler, auto DLT
            url = f"https://{AIRTEL_IQ_HOST}/api/v5/send-sms-cm"
            payload = {
                "customerId": AIRTEL_IQ_CUSTOMER_ID,
                "destinationAddress": [phone_clean],
                "message": content,
                "sourceAddress": source_address
            }
        elif api_version == 'v6':
            # Enhanced API with full response
            url = f"https://{AIRTEL_IQ_HOST}/api/v6/send-sms"
            payload = {
                "customerId": AIRTEL_IQ_CUSTOMER_ID,
                "destinationAddress": [phone_clean],
                "message": content,
                "sourceAddress": source_address,
                "messageType": message_type,
                "dltTemplateId": dlt_template_id,
                "entityId": entity_id
            }
            if message_type == 'SERVICE_IMPLICIT':
                payload["otp"] = is_otp
            if meta_data:
                payload["metaData"] = meta_data
        else:
            # v4 - Standard DLT compliant API
            url = f"https://{AIRTEL_IQ_HOST}/api/v4/send-sms"
            payload = {
                "customerId": AIRTEL_IQ_CUSTOMER_ID,
                "destinationAddress": [phone_clean],
                "message": content,
                "sourceAddress": source_address,
                "messageType": message_type,
                "dltTemplateId": dlt_template_id,
                "entityId": entity_id
            }
            if message_type == 'SERVICE_IMPLICIT':
                payload["otp"] = is_otp
            if meta_data:
                payload["metaData"] = meta_data
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {auth_header}',
            'customerId': AIRTEL_IQ_CUSTOMER_ID
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        
        logger.info(json.dumps({
            'event': 'airtel_iq_sms_request',
            'url': url,
            'apiVersion': api_version,
            'messageType': message_type,
            'phone': phone_clean[-4:],  # Log last 4 digits only
            'requestId': request_id
        }))
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            logger.info(json.dumps({
                'event': 'airtel_iq_sms_response',
                'messageRequestId': result.get('messageRequestId'),
                'requestId': request_id
            }))
            
            return {
                'success': True,
                'providerMessageId': result.get('messageRequestId'),
                'messageRequestId': result.get('messageRequestId'),
                'response': result
            }
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(json.dumps({
            'event': 'airtel_iq_sms_http_error',
            'status': e.code,
            'error': error_body,
            'requestId': request_id
        }))
        
        # Parse error response
        try:
            error_data = json.loads(error_body)
            error_msg = error_data.get('message', f'HTTP {e.code}')
        except (json.JSONDecodeError, TypeError, ValueError):
            error_msg = f'HTTP {e.code}: {error_body[:200]}'
        
        return {'success': False, 'error': error_msg}
        
    except Exception as e:
        logger.error(f"Airtel IQ SMS error: {str(e)}")
        return {'success': False, 'error': str(e)}


def _clean_phone_for_sms(phone: str) -> str:
    """Clean phone number for Airtel IQ SMS (10 or 12 digits)."""
    if not phone:
        return ''
    
    # Remove all non-digits
    digits = ''.join(c for c in phone if c.isdigit())
    
    # Handle +91 prefix
    if digits.startswith('91') and len(digits) == 12:
        return digits  # Keep 12 digits with country code
    
    # Handle 0 prefix
    if digits.startswith('0') and len(digits) == 11:
        digits = digits[1:]
    
    # Validate 10 or 12 digits
    if len(digits) == 10 or len(digits) == 12:
        return digits
    
    return ''


def _send_airtel_sms(phone: str, content: str, request_id: str) -> Dict[str, Any]:
    """Legacy Airtel SMS API (deprecated, use _send_airtel_iq_sms)."""
    # Redirect to new IQ API with defaults
    return _send_airtel_iq_sms(
        phone=phone,
        content=content,
        message_type='SERVICE_IMPLICIT',
        dlt_template_id='',
        entity_id=AIRTEL_IQ_ENTITY_ID,
        source_address=AIRTEL_IQ_SOURCE_ADDRESS,
        is_otp=False,
        meta_data={},
        api_version='v5',  # Use content moderation for legacy
        request_id=request_id
    )


def _store_message(message_id: str, contact_id: str, content: str, status: str, 
                   error: str = None, provider_message_id: str = None,
                   extra_data: Dict = None) -> None:
    """Store message record in DynamoDB."""
    try:
        now = int(time.time())
        table = dynamodb.Table(MESSAGES_TABLE)
        
        item = {
            'messageId': message_id,
            'contactId': contact_id,
            'channel': 'SMS',
            'direction': 'OUTBOUND',
            'content': content,
            'status': status,
            'timestamp': Decimal(str(now)),
            'createdAt': Decimal(str(now)),
            'ttl': Decimal(str(now + MESSAGE_TTL_SECONDS)),
        }
        
        if error:
            item['errorDetails'] = error
        if provider_message_id:
            item['providerMessageId'] = provider_message_id
            item['messageRequestId'] = provider_message_id
        
        # Add extra data (provider, messageType, dltTemplateId, etc.)
        if extra_data:
            for key, value in extra_data.items():
                if value:  # Only add non-empty values
                    item[key] = value
        
        table.put_item(Item=item)
        
    except Exception as e:
        logger.error(f"Store message error: {str(e)}")


def _response(status_code: int, body: Dict, origin: str = '') -> Dict[str, Any]:
    """Return HTTP response with CORS headers."""
    return {
        'statusCode': status_code,
        'headers': cors_headers(origin),
        'body': json.dumps(body)
    }
