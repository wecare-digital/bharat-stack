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
import urllib.parse
from typing import Dict, Any
from decimal import Decimal

from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin

# Configure logging
from lambda_utils.logging import get_logger
from lambda_utils.message_store import put_message  # canonical MessagesTable writer

logger = get_logger(__name__)

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
sns = boto3.client('sns', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
pinpoint = boto3.client('pinpoint', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Environment variables
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'stack-wecare-digital-ContactsTable')
MESSAGES_TABLE = os.environ.get('MESSAGES_TABLE', 'stack-wecare-digital-MessagesTable')
PINPOINT_APP_ID = os.environ.get('PINPOINT_APP_ID', '')
ORIGINATION_NUMBER = os.environ.get('ORIGINATION_NUMBER', '')
SENDER_ID = os.environ.get('SENDER_ID', 'WECARE')
MESSAGE_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days

# Airtel IQ SMS Configuration
AIRTEL_IQ_HOST = os.environ.get('AIRTEL_IQ_HOST', 'iqmessaging.airtel.in')
# Static IP proxy for Airtel (Lightsail 52.3.44.165) — Airtel whitelists this IP
SMS_PROXY_URL = os.environ.get('SMS_PROXY_URL', 'http://52.3.44.165:8899')
# DLT Registration - WECARE.DIGITAL
AIRTEL_IQ_ENTITY_ID = os.environ.get('AIRTEL_IQ_ENTITY_ID', '1201161991108627443')  # PE ID
AIRTEL_IQ_SOURCE_ADDRESS = os.environ.get('AIRTEL_IQ_SOURCE_ADDRESS', 'WDBEEP')  # Header

# Airtel IQ SMS credentials — loaded from Secrets Manager (wecare/airtel-iq),
# with env fallback during migration. Secret is JSON: {username, password, customerId}.
_sms_secrets_client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
AIRTEL_IQ_SECRET = os.environ.get('AIRTEL_IQ_SECRET', 'wecare/airtel-iq')


def _load_airtel_iq_creds():
    u = os.environ.get('AIRTEL_IQ_USERNAME', '')
    p = os.environ.get('AIRTEL_IQ_PASSWORD', '')
    c = os.environ.get('AIRTEL_IQ_CUSTOMER_ID', '')
    try:
        raw = _sms_secrets_client.get_secret_value(SecretId=AIRTEL_IQ_SECRET).get('SecretString', '') or ''
        data = json.loads(raw)
        u = (data.get('username') or u or '').strip()
        p = (data.get('password') or p or '').strip()
        c = (data.get('customerId') or data.get('customer_id') or c or '').strip()
    except Exception as e:
        logger.warning(f'Airtel IQ creds: Secrets Manager load failed, using env fallback: {e}')
    return u, p, c


AIRTEL_IQ_USERNAME, AIRTEL_IQ_PASSWORD, AIRTEL_IQ_CUSTOMER_ID = _load_airtel_iq_creds()


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
        api_version = body.get('apiVersion', 'v5')  # v5 (content moderation, auto-DLT), v4, v6
        
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
        # Indian +91: Try Airtel first, fallback to Sinch, then Pinpoint
        # International: AWS Pinpoint/SNS
        # provider=sinch forces Sinch directly
        clean = phone.lstrip('+')
        is_indian = clean.startswith('91') and len(clean) == 12
        if body.get('provider') == 'sinch':
            provider = 'sinch'
        elif is_indian:
            provider = 'airtel'
        else:
            provider = 'aws'

        if provider == 'sinch':
            result = _send_sinch_sms(phone, content, source_address, request_id)
        elif provider == 'airtel':
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
            # If Airtel fails (any error: HTTP, timeout, auth, connection), try Sinch as fallback
            if not result.get('success'):
                logger.warning(f"Airtel failed, trying Sinch fallback: {result.get('error', '')[:100]}")
                sinch_result = _send_sinch_sms(phone, content, source_address, request_id)
                if sinch_result.get('success'):
                    result = sinch_result
                    provider = 'sinch'
                else:
                    # Both failed — include both errors in response
                    result['error'] = f"Airtel: {result.get('error', '?')[:80]} | Sinch: {sinch_result.get('error', '?')[:80]}"
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
        response = table.get_item(Key={'id': contact_id})
        return response.get('Item', {})
    except Exception as e:
        logger.error(f"Get contact error: {str(e)}")
        return {}


# ── Sinch (ACL) SMS Provider ──
# Enterprise: WECARE DIGITAL ALERT (WECAREALT)
# ── Sinch SMS Configuration ──────────────────────────────────────────
# OAuth API ONLY: https://jumbo.aclgateway.com/v12/enterprises/messages.json
# Auth: OAuth token (lifetime validity, NO IP whitelist needed)
# Sender: WDBEEP | AppID: wecarealt
# DLR Webhook: POST https://api.wecare.digital/webhook/sinch-dlr
# Credentials loaded from Secrets Manager: wecare/sinch/sms
_sinch_sms_cache = {}

def _load_sinch_sms_creds() -> dict:
    """Load Sinch SMS credentials from Secrets Manager (cached)."""
    if _sinch_sms_cache.get('loaded'):
        return _sinch_sms_cache
    try:
        sm = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
        resp = sm.get_secret_value(SecretId='wecare/sinch/sms')
        data = json.loads(resp['SecretString'])
        _sinch_sms_cache.update({
            'oauth_host': data.get('oauth_host', 'jumbo.aclgateway.com'),
            'oauth_token': data.get('oauth_token', ''),
            'app_id': data.get('app_id', 'wecarealt'),
            'user_id': data.get('user_id', 'wecarealt'),
            'password': data.get('password', ''),
            'loaded': True,
        })
        return _sinch_sms_cache
    except Exception as e:
        logger.warning(f'Sinch SMS secret not available: {e}')
        return {
            'oauth_host': 'jumbo.aclgateway.com',
            'oauth_token': '',
            'app_id': 'wecarealt',
            'user_id': 'wecarealt',
            'password': '',
            'loaded': False,
        }


def _send_sinch_sms(phone: str, content: str, source_address: str, request_id: str) -> Dict[str, Any]:
    """
    Send SMS via Sinch India OAuth endpoint.
    
    Endpoint: POST https://jumbo.aclgateway.com/v12/enterprises/messages.json
    Auth: OAuth token in Authorization header (lifetime validity, no IP whitelist)
    DLR: POST https://api.wecare.digital/webhook/sinch-dlr
    """
    try:
        creds = _load_sinch_sms_creds()
        oauth_host = creds.get('oauth_host', 'jumbo.aclgateway.com')
        oauth_token = creds.get('oauth_token', '')
        app_id = creds.get('app_id', 'wecarealt')
        user_id = creds.get('user_id', 'wecarealt')
        password = creds.get('password', '')

        if not oauth_token:
            return {'success': False, 'error': 'Sinch OAuth token not configured in wecare/sinch/sms'}

        # Clean phone number to 91XXXXXXXXXX format
        clean = phone.replace('+', '').replace(' ', '').replace('-', '')
        if not clean.startswith('91'):
            clean = '91' + clean[-10:]

        # Build JSON payload — v12 multi-message format
        # (v12 uses "messages" array, not single "to"/"text" fields)
        payload = json.dumps({
            "appid": app_id,
            "contenttype": "1",
            "selfid": "true",
            "alert": "1",
            "messages": [
                {
                    "id": "1",
                    "to": clean,
                    "from": source_address or 'WDBEEP',
                    "msg": content,
                }
            ]
        })

        logger.info(json.dumps({
            'event': 'sinch_sms_request',
            'phone': clean[-4:],
            'endpoint': 'oauth',
            'requestId': request_id,
        }))

        # POST to OAuth endpoint (no IP whitelist required)
        # Authorization header format: "Bearer <token>"
        url = f'https://{oauth_host}/v12/enterprises/messages.json'
        auth_header = oauth_token if oauth_token.startswith('Bearer ') else f'Bearer {oauth_token}'
        req = urllib.request.Request(url, data=payload.encode(), headers={
            'Content-Type': 'application/json',
            'Authorization': auth_header,
        }, method='POST')

        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read().decode()
            logger.info(json.dumps({
                'event': 'sinch_sms_response',
                'status': resp.status,
                'body': body[:200],
                'requestId': request_id,
            }))
            try:
                result = json.loads(body)
                accepted = result.get('accepted', '') in (True, 'true')
                resp_id = result.get('respid', result.get('responseid', ''))
                if accepted or resp_id:
                    return {'success': True, 'providerMessageId': resp_id or body[:50], 'provider': 'sinch'}
                else:
                    error = result.get('error', '')
                    logger.warning(f"Sinch rejected: error={error}, body={body[:200]}")
                    return {'success': False, 'error': f'Sinch rejected: {error}', 'provider': 'sinch'}
            except json.JSONDecodeError:
                # Non-JSON response — treat as success if HTTP 200
                return {'success': True, 'providerMessageId': body[:50], 'provider': 'sinch'}

    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')[:200] if e.fp else ''
        logger.error(f"Sinch HTTP error: {e.code} - {error_body}")
        return {'success': False, 'error': f'Sinch HTTP {e.code}: {error_body[:100]}'}
    except Exception as e:
        logger.error(f"Sinch SMS error: {e}")
        return {'success': False, 'error': str(e)}


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
            # Content Moderation API - include DLT fields for explicit matching
            url = f"https://{AIRTEL_IQ_HOST}/api/v5/send-sms-cm"
            payload = {
                "customerId": AIRTEL_IQ_CUSTOMER_ID,
                "destinationAddress": [phone_clean],
                "message": content,
                "sourceAddress": source_address
            }
            # Pass DLT fields when provided — v5 auto-matches but explicit is more reliable
            if dlt_template_id:
                payload["dltTemplateId"] = dlt_template_id
            if entity_id:
                payload["entityId"] = entity_id
            if message_type:
                payload["messageType"] = message_type
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
        
        # Route through Lightsail proxy (static IP whitelisted by Airtel)
        # Retry up to 3 times on 502/503 proxy errors
        from urllib.parse import urlparse
        parsed = urlparse(url)
        proxy_payload = {
            "path": parsed.path,
            "headers": headers,
            "body": payload
        }
        proxy_url = f"{SMS_PROXY_URL}/"
        proxy_data = json.dumps(proxy_payload).encode('utf-8')
        
        logger.info(json.dumps({
            'event': 'airtel_iq_sms_request',
            'url': url,
            'apiVersion': api_version,
            'messageType': message_type,
            'phone': phone_clean[-4:],
            'requestId': request_id
        }))
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                req = urllib.request.Request(
                    proxy_url,
                    data=proxy_data,
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                
                with urllib.request.urlopen(req, timeout=30) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    
                    logger.info(json.dumps({
                        'event': 'airtel_iq_sms_response',
                        'messageRequestId': result.get('messageRequestId'),
                        'attempt': attempt + 1,
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
                if e.code in (502, 503) and attempt < max_retries - 1:
                    wait = (attempt + 1) * 2
                    logger.warning(f"Proxy {e.code}, retry {attempt + 1}/{max_retries} in {wait}s")
                    time.sleep(wait)
                    continue
                raise
            except (urllib.error.URLError, ConnectionError, OSError) as e:
                if attempt < max_retries - 1:
                    wait = (attempt + 1) * 2
                    logger.warning(f"Proxy connection error, retry {attempt + 1}/{max_retries} in {wait}s: {e}")
                    time.sleep(wait)
                    continue
                raise
            
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
    """Store SMS record in the canonical MessagesTable via the shared writer.
    Fixes prior issues: ensures the `id` PK, lowercase channel, and sparse contactId
    (the GSI key) so the row actually persists."""
    extras = {}
    if extra_data:
        for key, value in extra_data.items():
            if value:
                extras[key] = value
    put_message(
        channel='sms',
        direction='outbound',
        contact_id=contact_id or '',
        content=content or '',
        status=(status or 'sent').lower(),
        message_id=message_id,
        message_type=extras.pop('messageType', 'text'),
        provider_message_id=provider_message_id or None,
        error_details=error or None,
        **extras,
    )


def _response(status_code: int, body: Dict, resp_origin: str = '') -> Dict[str, Any]:
    """Return HTTP response with CORS headers."""
    return {
        'statusCode': status_code,
        'headers': cors_headers(resp_origin or origin),
        'body': json.dumps(body)
    }
