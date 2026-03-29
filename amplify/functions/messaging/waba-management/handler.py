"""
WABA Management Lambda Function

Purpose: Manage WhatsApp Business Accounts via Direct Meta Graph API
Implements:
- GetLinkedWhatsAppBusinessAccount - Get WABA details (phone quality, limits)
- GetLinkedWhatsAppBusinessAccountPhoneNumber - Get phone details
- ListLinkedWhatsAppBusinessAccounts - List all WABAs
- DeleteWhatsAppMessageMedia - Delete uploaded media
- GetWhatsAppMessageMedia - Download media from WhatsApp
- PostWhatsAppMessageMedia - Upload media to WhatsApp for sending
- PutWhatsAppBusinessAccountEventDestinations - Subscribe/unsubscribe app to WABA
- ListTagsForResource - (No Meta equivalent, returns empty)
- TagResource - (No Meta equivalent, returns success)
- UntagResource - (No Meta equivalent, returns success)

Meta Graph API Reference:
https://developers.facebook.com/docs/whatsapp/business-management-api
"""

import os
import json
import logging
import hashlib
import hmac
import boto3
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime

from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin

# Configure logging
from lambda_utils.logging import get_logger

logger = get_logger(__name__)

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
sns_client = boto3.client('sns', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
secrets_client = boto3.client('secretsmanager', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Environment variables
SYSTEM_CONFIG_TABLE = os.environ.get('SYSTEM_CONFIG_TABLE', 'stack-wecare-digital-SystemConfigTable')
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:775261844268:stack-wecare-digital')

# Meta Graph API config
META_API_VERSION = 'v20.0'
META_API_BASE = f'https://graph.facebook.com/{META_API_VERSION}'
META_APP_ID = '2238810740192680'

# AWS WABA ID → Meta WABA ID mapping
AWS_TO_META_WABA = {
    'waba-e47d916f3c7a47e1a34a19653893dd4b': '2094615664435155',
    'waba-dbe343f210204752b74c80a0a59631a6': '2513394156072604',
}
META_WABA_DEFAULT = '2094615664435155'

# AWS phone-number-id → Meta phone ID mapping
AWS_PHONE_TO_META = {
    'phone-number-id-waba3-direct-1016149501586345': '1016149501586345',
    'phone-number-id-waba-t-direct-1055232054343117': '1055232054343117',
    'phone-number-id-waba3-direct-945798751960485': '945798751960485',
}

# Cached Meta credentials
_meta_credentials = None


def _get_meta_credentials() -> Dict[str, str]:
    """Load Meta access token and app secret from Secrets Manager (cached)."""
    global _meta_credentials
    if _meta_credentials:
        return _meta_credentials
    try:
        resp = secrets_client.get_secret_value(SecretId='wecare/meta-system-user-token')
        secret = json.loads(resp['SecretString'])
        _meta_credentials = {
            'access_token': secret['access_token'],
            'app_secret': secret['app_secret'],
        }
        return _meta_credentials
    except Exception as e:
        logger.error(f'Failed to load Meta credentials: {e}')
        raise


def _appsecret_proof(access_token: str, app_secret: str) -> str:
    """Generate appsecret_proof HMAC-SHA256."""
    return hmac.new(
        app_secret.encode('utf-8'),
        access_token.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()


def _meta_request(path: str, method: str = 'GET', data: bytes = None,
                  headers: Dict[str, str] = None, content_type: str = None) -> Dict[str, Any]:
    """
    Make an authenticated request to the Meta Graph API.
    Returns parsed JSON response.
    """
    creds = _get_meta_credentials()
    token = creds['access_token']
    proof = _appsecret_proof(token, creds['app_secret'])

    separator = '&' if '?' in path else '?'
    url = f'{META_API_BASE}/{path}{separator}access_token={urllib.parse.quote(token)}&appsecret_proof={proof}'

    req_headers = headers or {}
    if content_type:
        req_headers['Content-Type'] = content_type

    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode('utf-8'))


def _meta_request_raw(url: str) -> bytes:
    """Download raw bytes from a URL with Meta auth."""
    creds = _get_meta_credentials()
    token = creds['access_token']
    req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def _resolve_meta_waba_id(aws_waba_id: str) -> str:
    """Map AWS WABA ID to Meta WABA ID."""
    if not aws_waba_id.startswith('waba-'):
        aws_waba_id = f'waba-{aws_waba_id}'
    return AWS_TO_META_WABA.get(aws_waba_id, META_WABA_DEFAULT)


def _resolve_meta_phone_id(aws_phone_id: str) -> str:
    """
    Map AWS phone-number-id to Meta phone ID.
    For 'direct' format IDs, extract the Meta ID from the suffix.
    For old format, use the mapping dict.
    """
    if not aws_phone_id.startswith('phone-number-id-'):
        aws_phone_id = f'phone-number-id-{aws_phone_id}'

    # Direct format: phone-number-id-waba3-direct-{meta_id}
    if '-direct-' in aws_phone_id:
        return aws_phone_id.split('-direct-')[-1]

    # Lookup in mapping
    if aws_phone_id in AWS_PHONE_TO_META:
        return AWS_PHONE_TO_META[aws_phone_id]

    # Fallback: strip prefix and hope it's a Meta ID
    return aws_phone_id.replace('phone-number-id-', '')


def _serialize_value(val):
    """Convert datetime and other non-JSON-serializable types to strings."""
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    return val


def _serialize_dict(d: Dict) -> Dict:
    """Recursively serialize a dictionary for JSON."""
    result = {}
    for k, v in d.items():
        if isinstance(v, dict):
            result[k] = _serialize_dict(v)
        elif isinstance(v, list):
            result[k] = [_serialize_dict(i) if isinstance(i, dict) else _serialize_value(i) for i in v]
        else:
            result[k] = _serialize_value(v)
    return result


# Module-level origin for CORS (set per-invocation in handler)
origin = ''


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    WABA Management API Handler
    
    Routes:
    - GET /waba - List all linked WABAs
    - GET /waba/{wabaId} - Get WABA details
    - GET /waba/phone/{phoneNumberId} - Get phone number details
    - GET /waba/events - Get system events (template status, phone quality, account updates)
    - GET /waba/media/{mediaId} - Download media from WhatsApp
    - POST /waba/media - Upload media to WhatsApp for sending
    - DELETE /waba/media/{mediaId} - Delete WhatsApp media
    - GET /waba/{wabaId}/tags - List tags for WABA
    - POST /waba/{wabaId}/tags - Add tags to WABA
    - DELETE /waba/{wabaId}/tags - Remove tags from WABA
    - PUT /waba/{wabaId}/events - Configure event destinations
    - POST /waba/{wabaId}/subscribe-sns - Subscribe WABA to SNS topic for events
    - DELETE /waba/{wabaId}/subscribe-sns - Unsubscribe WABA from SNS topic
    - GET /waba/{wabaId}/subscribe-sns - Get current SNS subscription status
    """
    request_id = context.aws_request_id if context else 'local'
    global origin
    origin = extract_origin(event)
    
    # Handle both API Gateway v1 (REST) and v2 (HTTP) event formats
    request_context = event.get('requestContext', {})
    
    # API Gateway v2 (HTTP API) format
    if 'http' in request_context:
        http_method = request_context.get('http', {}).get('method', 'GET')
        path = request_context.get('http', {}).get('path', '')
    else:
        # API Gateway v1 (REST API) format
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '')

    # Also check rawPath for HTTP API
    if not path:
        path = event.get('rawPath', '')
    
    path_params = event.get('pathParameters') or {}
    query_params = event.get('queryStringParameters') or {}
    
    logger.info(json.dumps({
        'event': 'waba_management_request',
        'method': http_method,
        'path': path,
        'pathParams': path_params,
        'queryParams': query_params,
        'requestId': request_id
    }))
    
    # Handle OPTIONS preflight
    if http_method == 'OPTIONS':
        return options_response(origin)
    
    try:
        body = {}
        if event.get('body'):
            body = json.loads(event.get('body', '{}'))
        
        # Route handling
        if http_method == 'GET':
            if '/waba/events' in path:
                return _get_system_events(query_params, request_id)
            elif '/subscribe-sns' in path:
                waba_id = path_params.get('wabaId') or path.split('/waba/')[-1].split('/')[0]
                return _get_sns_subscription_status(waba_id, request_id)
            elif '/waba/media/' in path:
                media_id = path_params.get('mediaId') or path.split('/media/')[-1]
                phone_id = query_params.get('phoneNumberId', '')
                return _get_media(media_id, phone_id, query_params, request_id)
            elif '/waba/phone/' in path:
                phone_id = path_params.get('phoneNumberId') or path.split('/phone/')[-1]
                return _get_phone_number_details(phone_id, request_id)
            elif '/tags' in path:
                resource_arn = query_params.get('resourceArn', '')
                return _list_tags(resource_arn, request_id)
            elif path_params.get('wabaId') or '/waba/' in path:
                waba_id = path_params.get('wabaId') or path.split('/waba/')[-1].split('/')[0]
                if waba_id and waba_id != 'waba':
                    return _get_waba_details(waba_id, request_id)
            # Default: list all WABAs
            return _list_wabas(request_id)
        
        elif http_method == 'POST':
            if '/subscribe-sns' in path:
                waba_id = path_params.get('wabaId') or path.split('/waba/')[-1].split('/')[0]
                return _subscribe_waba_to_sns(waba_id, body, request_id)
            elif '/waba/media' in path:
                return _post_media(body, request_id)
            elif '/tags' in path:
                return _tag_resource(body, request_id)
            elif '/migrate' in path:
                return _migrate_phone(body, request_id)
            elif '/request-otp' in path:
                return _request_otp(body, request_id)
            elif '/verify-otp' in path:
                return _verify_otp(body, request_id)
            elif '/register-phone' in path:
                return _register_phone(body, request_id)
        
        elif http_method == 'PUT':
            if '/events' in path:
                waba_id = path_params.get('wabaId') or body.get('wabaId', '')
                return _put_event_destinations(waba_id, body, request_id)
        
        elif http_method == 'DELETE':
            if '/subscribe-sns' in path:
                waba_id = path_params.get('wabaId') or path.split('/waba/')[-1].split('/')[0]
                return _unsubscribe_waba_from_sns(waba_id, body, request_id)
            elif '/waba/media/' in path:
                media_id = path_params.get('mediaId') or path.split('/media/')[-1]
                phone_id = query_params.get('phoneNumberId', '')
                return _delete_media(media_id, phone_id, request_id)
            elif '/tags' in path:
                return _untag_resource(body, request_id)
        
        return _error_response(400, 'Invalid request')
        
    except json.JSONDecodeError:
        return _error_response(400, 'Invalid JSON in request body')
    except Exception as e:
        logger.error(json.dumps({
            'event': 'waba_management_error',
            'error': str(e),
            'errorType': type(e).__name__,
            'requestId': request_id
        }))
        return _error_response(500, str(e))


def _list_wabas(request_id: str) -> Dict[str, Any]:
    """
    List all linked WhatsApp Business Accounts.
    Meta Graph API: GET /{app_id}/whatsapp_business_accounts
    """
    try:
        fields = 'id,name,currency,timezone_id,message_template_namespace'
        response = _meta_request(
            f'{META_APP_ID}/whatsapp_business_accounts?fields={fields}'
        )

        wabas = []
        for account in response.get('data', []):
            wabas.append({
                'id': account.get('id', ''),
                'wabaId': account.get('id', ''),
                'wabaName': account.get('name', ''),
                'currency': account.get('currency', ''),
                'timezoneId': account.get('timezone_id', ''),
                'messageTemplateNamespace': account.get('message_template_namespace', ''),
                'arn': '',
                'registrationStatus': 'COMPLETE',
                'linkDate': '',
                'enableSending': True,
                'enableReceiving': True,
                'eventDestinations': []
            })

        logger.info(json.dumps({
            'event': 'wabas_listed',
            'count': len(wabas),
            'requestId': request_id
        }))

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'wabas': wabas,
                'count': len(wabas)
            })
        }

    except Exception as e:
        logger.error(json.dumps({
            'event': 'list_wabas_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to list WABAs: {str(e)}')


def _get_waba_details(waba_id: str, request_id: str) -> Dict[str, Any]:
    """
    Get details of a specific WABA including phone numbers with quality ratings.
    Meta Graph API: GET /{meta_waba_id}?fields=...
    """
    try:
        # Ensure waba_id has correct format
        if not waba_id.startswith('waba-'):
            waba_id = f'waba-{waba_id}'

        meta_waba_id = _resolve_meta_waba_id(waba_id)

        fields = 'id,name,currency,timezone_id,message_template_namespace,account_review_status,on_behalf_of_business_info'
        account = _meta_request(f'{meta_waba_id}?fields={fields}')

        # Fetch phone numbers for this WABA
        phone_fields = 'id,display_phone_number,verified_name,quality_rating,platform_type,code_verification_status,is_official_business_account'
        phones_resp = _meta_request(
            f'{meta_waba_id}/phone_numbers?fields={phone_fields}'
        )

        phone_numbers = []
        for phone in phones_resp.get('data', []):
            quality = phone.get('quality_rating', 'UNKNOWN')
            # Meta returns GREEN/YELLOW/RED — keep as-is
            phone_numbers.append({
                'phoneNumberId': phone.get('id', ''),
                'phoneNumber': phone.get('display_phone_number', ''),
                'displayPhoneNumber': phone.get('display_phone_number', ''),
                'displayPhoneNumberName': phone.get('verified_name', ''),
                'qualityRating': quality,
                'metaPhoneNumberId': phone.get('id', ''),
                'dataLocalizationRegion': '',
                'arn': '',
                'platformType': phone.get('platform_type', ''),
                'codeVerificationStatus': phone.get('code_verification_status', ''),
                'isOfficialBusinessAccount': phone.get('is_official_business_account', False),
            })

        on_behalf = account.get('on_behalf_of_business_info', {})
        waba_details = {
            'id': waba_id,
            'wabaId': account.get('id', ''),
            'wabaName': account.get('name', ''),
            'currency': account.get('currency', ''),
            'timezoneId': account.get('timezone_id', ''),
            'messageTemplateNamespace': account.get('message_template_namespace', ''),
            'accountReviewStatus': account.get('account_review_status', ''),
            'onBehalfOfBusinessInfo': on_behalf,
            'arn': '',
            'registrationStatus': 'COMPLETE',
            'linkDate': '',
            'enableSending': True,
            'enableReceiving': True,
            'eventDestinations': [],
            'phoneNumbers': phone_numbers
        }

        logger.info(json.dumps({
            'event': 'waba_details_fetched',
            'wabaId': waba_id,
            'metaWabaId': meta_waba_id,
            'phoneCount': len(phone_numbers),
            'requestId': request_id
        }))

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps(waba_details)
        }

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return _error_response(404, f'WABA not found: {waba_id}')
        logger.error(json.dumps({
            'event': 'get_waba_details_error',
            'wabaId': waba_id,
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to get WABA details: {str(e)}')
    except Exception as e:
        logger.error(json.dumps({
            'event': 'get_waba_details_error',
            'wabaId': waba_id,
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to get WABA details: {str(e)}')


def _get_phone_number_details(phone_id: str, request_id: str) -> Dict[str, Any]:
    """
    Get details of a specific phone number including quality rating.
    Meta Graph API: GET /{meta_phone_id}?fields=...
    """
    try:
        # Ensure phone_id has correct format
        if not phone_id.startswith('phone-number-id-'):
            phone_id = f'phone-number-id-{phone_id}'

        meta_phone_id = _resolve_meta_phone_id(phone_id)

        fields = 'id,display_phone_number,verified_name,quality_rating,platform_type,code_verification_status,is_official_business_account'
        phone = _meta_request(f'{meta_phone_id}?fields={fields}')

        phone_details = {
            'phoneNumberId': phone_id,
            'phoneNumber': phone.get('display_phone_number', ''),
            'displayPhoneNumber': phone.get('display_phone_number', ''),
            'displayPhoneNumberName': phone.get('verified_name', ''),
            'qualityRating': phone.get('quality_rating', 'UNKNOWN'),
            'metaPhoneNumberId': phone.get('id', ''),
            'dataLocalizationRegion': '',
            'arn': '',
            'linkedWabaId': '',
            'platformType': phone.get('platform_type', ''),
            'codeVerificationStatus': phone.get('code_verification_status', ''),
            'isOfficialBusinessAccount': phone.get('is_official_business_account', False),
        }

        logger.info(json.dumps({
            'event': 'phone_details_fetched',
            'phoneNumberId': phone_id,
            'metaPhoneId': meta_phone_id,
            'qualityRating': phone_details['qualityRating'],
            'requestId': request_id
        }))

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps(phone_details)
        }

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return _error_response(404, f'Phone number not found: {phone_id}')
        logger.error(json.dumps({
            'event': 'get_phone_details_error',
            'phoneNumberId': phone_id,
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to get phone details: {str(e)}')
    except Exception as e:
        logger.error(json.dumps({
            'event': 'get_phone_details_error',
            'phoneNumberId': phone_id,
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to get phone details: {str(e)}')


def _get_system_events(query_params: Dict, request_id: str) -> Dict[str, Any]:
    """
    Get system events from SystemConfig table.
    Events stored by inbound webhook handler:
    - template_status: Template approval/rejection events
    - phone_quality: Phone quality rating changes
    - account_update: Messaging limit changes, restrictions
    """
    try:
        event_type = query_params.get('type', 'all')
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        
        events = {
            'templateStatus': [],
            'phoneQuality': [],
            'accountUpdates': []
        }
        
        # Fetch template status events
        if event_type in ['all', 'template_status']:
            try:
                response = config_table.get_item(Key={'id': 'whatsapp_events_template_status'})
                if 'Item' in response:
                    events['templateStatus'] = json.loads(response['Item'].get('configValue', '[]'))
            except Exception as e:
                logger.warning(f'Failed to fetch template status events: {str(e)}')
        
        # Fetch phone quality events
        if event_type in ['all', 'phone_quality']:
            try:
                response = config_table.get_item(Key={'id': 'whatsapp_events_phone_quality'})
                if 'Item' in response:
                    events['phoneQuality'] = json.loads(response['Item'].get('configValue', '[]'))
            except Exception as e:
                logger.warning(f'Failed to fetch phone quality events: {str(e)}')
        
        # Fetch account update events
        if event_type in ['all', 'account_update']:
            try:
                response = config_table.get_item(Key={'id': 'whatsapp_events_account_update'})
                if 'Item' in response:
                    events['accountUpdates'] = json.loads(response['Item'].get('configValue', '[]'))
            except Exception as e:
                logger.warning(f'Failed to fetch account update events: {str(e)}')
        
        logger.info(json.dumps({
            'event': 'system_events_fetched',
            'templateStatusCount': len(events['templateStatus']),
            'phoneQualityCount': len(events['phoneQuality']),
            'accountUpdatesCount': len(events['accountUpdates']),
            'requestId': request_id
        }))
        
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps(events)
        }
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'get_system_events_error',
            'error': str(e),
            'requestId': request_id
        }))
        # Return empty events on error (table may not exist)
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'templateStatus': [],
                'phoneQuality': [],
                'accountUpdates': []
            })
        }


def _delete_media(media_id: str, phone_number_id: str, request_id: str) -> Dict[str, Any]:
    """
    Delete media from WhatsApp.
    Meta Graph API: DELETE /{media_id}
    """
    try:
        if not media_id:
            return _error_response(400, 'mediaId is required')

        if not phone_number_id:
            return _error_response(400, 'phoneNumberId is required')

        # Ensure phone_number_id has correct format
        if not phone_number_id.startswith('phone-number-id-'):
            phone_number_id = f'phone-number-id-{phone_number_id}'

        response = _meta_request(media_id, method='DELETE')
        success = response.get('success', False)

        logger.info(json.dumps({
            'event': 'media_deleted',
            'mediaId': media_id,
            'phoneNumberId': phone_number_id,
            'success': success,
            'requestId': request_id
        }))

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'success': success,
                'mediaId': media_id
            })
        }

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return _error_response(404, f'Media not found: {media_id}')
        logger.error(json.dumps({
            'event': 'delete_media_error',
            'mediaId': media_id,
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to delete media: {str(e)}')
    except Exception as e:
        logger.error(json.dumps({
            'event': 'delete_media_error',
            'mediaId': media_id,
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to delete media: {str(e)}')


def _error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Return error response with CORS headers."""
    return {
        'statusCode': status_code,
        'headers': cors_headers(origin),
        'body': json.dumps({'error': message})
    }


# ============================================================================
# NEW APIs: Media, Tags, Event Destinations
# ============================================================================

def _get_media(media_id: str, phone_number_id: str, query_params: Dict, request_id: str) -> Dict[str, Any]:
    """
    Download media from WhatsApp.
    Meta Graph API: GET /{media_id} to get URL, then download the binary.
    """
    try:
        if not media_id:
            return _error_response(400, 'mediaId is required')
        if not phone_number_id:
            return _error_response(400, 'phoneNumberId is required')

        # Ensure phone_number_id has correct format
        if not phone_number_id.startswith('phone-number-id-'):
            phone_number_id = f'phone-number-id-{phone_number_id}'

        metadata_only = query_params.get('metadataOnly', 'false').lower() == 'true'

        # Get media metadata (URL, mime_type, etc.) from Meta
        media_info = _meta_request(media_id)

        result = {
            'mediaId': media_id,
            'mimeType': media_info.get('mime_type', ''),
            'fileSize': media_info.get('file_size', 0),
        }

        if not metadata_only:
            # Download the actual media binary from the URL Meta returned
            media_url = media_info.get('url', '')
            if media_url:
                media_bytes = _meta_request_raw(media_url)

                # Upload to S3
                s3_key = f'stack/whatsapp-media/downloads/wecare-digital-{media_id}'
                s3.put_object(
                    Bucket=MEDIA_BUCKET,
                    Key=s3_key,
                    Body=media_bytes,
                    ContentType=media_info.get('mime_type', 'application/octet-stream')
                )

                result['s3Key'] = s3_key
                # Generate presigned URL for download
                presigned_url = s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': MEDIA_BUCKET, 'Key': s3_key},
                    ExpiresIn=3600
                )
                result['downloadUrl'] = presigned_url

        logger.info(json.dumps({
            'event': 'media_downloaded',
            'mediaId': media_id,
            'metadataOnly': metadata_only,
            'requestId': request_id
        }))

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps(result)
        }

    except urllib.error.HTTPError as e:
        if e.code == 404:
            return _error_response(404, f'Media not found: {media_id}')
        logger.error(json.dumps({
            'event': 'get_media_error',
            'mediaId': media_id,
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to get media: {str(e)}')
    except Exception as e:
        logger.error(json.dumps({
            'event': 'get_media_error',
            'mediaId': media_id,
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to get media: {str(e)}')


def _post_media(body: Dict, request_id: str) -> Dict[str, Any]:
    """
    Upload media to WhatsApp for sending.
    Meta Graph API: POST /{phone_id}/media (multipart upload)
    
    Downloads from S3, then uploads to Meta via multipart form.
    """
    try:
        phone_number_id = body.get('phoneNumberId', '')
        s3_key = body.get('s3Key', '')

        if not phone_number_id:
            return _error_response(400, 'phoneNumberId is required')
        if not s3_key:
            return _error_response(400, 's3Key is required')

        # Ensure phone_number_id has correct format
        if not phone_number_id.startswith('phone-number-id-'):
            phone_number_id = f'phone-number-id-{phone_number_id}'

        meta_phone_id = _resolve_meta_phone_id(phone_number_id)

        # Download file from S3
        s3_obj = s3.get_object(Bucket=MEDIA_BUCKET, Key=s3_key)
        file_bytes = s3_obj['Body'].read()
        content_type = s3_obj.get('ContentType', 'application/octet-stream')
        filename = s3_key.split('/')[-1]

        # Build multipart form data
        boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
        body_parts = []

        # messaging_product field
        body_parts.append(f'--{boundary}'.encode())
        body_parts.append(b'Content-Disposition: form-data; name="messaging_product"')
        body_parts.append(b'')
        body_parts.append(b'whatsapp')

        # type field
        body_parts.append(f'--{boundary}'.encode())
        body_parts.append(b'Content-Disposition: form-data; name="type"')
        body_parts.append(b'')
        body_parts.append(content_type.encode())

        # file field
        body_parts.append(f'--{boundary}'.encode())
        body_parts.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode())
        body_parts.append(f'Content-Type: {content_type}'.encode())
        body_parts.append(b'')
        body_parts.append(file_bytes)

        body_parts.append(f'--{boundary}--'.encode())

        multipart_body = b'\r\n'.join(body_parts)

        response = _meta_request(
            f'{meta_phone_id}/media',
            method='POST',
            data=multipart_body,
            content_type=f'multipart/form-data; boundary={boundary}'
        )

        result = {
            'mediaId': response.get('id', ''),
            's3Key': s3_key
        }

        logger.info(json.dumps({
            'event': 'media_uploaded',
            'mediaId': result['mediaId'],
            's3Key': s3_key,
            'requestId': request_id
        }))

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps(result)
        }

    except Exception as e:
        logger.error(json.dumps({
            'event': 'post_media_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to upload media: {str(e)}')


def _put_event_destinations(waba_id: str, body: Dict, request_id: str) -> Dict[str, Any]:
    """
    Configure event destinations for WABA.
    Meta Graph API: POST /{meta_waba_id}/subscribed_apps (subscribe app to WABA)
    """
    try:
        if not waba_id:
            return _error_response(400, 'wabaId is required')

        event_destinations = body.get('eventDestinations', [])

        # Ensure waba_id has correct format
        if not waba_id.startswith('waba-'):
            waba_id = f'waba-{waba_id}'

        meta_waba_id = _resolve_meta_waba_id(waba_id)

        # Format event destinations for response
        formatted_destinations = []
        for dest in event_destinations:
            formatted_destinations.append({
                'eventDestinationArn': dest.get('eventDestinationArn', ''),
                'roleArn': dest.get('roleArn', '')
            })

        if event_destinations:
            # Subscribe app to WABA
            _meta_request(f'{meta_waba_id}/subscribed_apps', method='POST')
        else:
            # Unsubscribe (empty destinations = clear)
            _meta_request(f'{meta_waba_id}/subscribed_apps', method='DELETE')

        logger.info(json.dumps({
            'event': 'event_destinations_updated',
            'wabaId': waba_id,
            'metaWabaId': meta_waba_id,
            'destinationCount': len(formatted_destinations),
            'requestId': request_id
        }))

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'success': True,
                'wabaId': waba_id,
                'eventDestinations': formatted_destinations
            })
        }

    except Exception as e:
        logger.error(json.dumps({
            'event': 'put_event_destinations_error',
            'wabaId': waba_id,
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to update event destinations: {str(e)}')


def _list_tags(resource_arn: str, request_id: str) -> Dict[str, Any]:
    """
    List tags for a resource.
    Note: No Meta Graph API equivalent. Returns empty tags.
    """
    try:
        if not resource_arn:
            return _error_response(400, 'resourceArn is required')

        logger.info(json.dumps({
            'event': 'tags_listed',
            'resourceArn': resource_arn,
            'tagCount': 0,
            'note': 'Tags not supported via Meta Graph API',
            'requestId': request_id
        }))

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'resourceArn': resource_arn,
                'tags': [],
                'note': 'Tagging is not supported via Meta Graph API. '
            })
        }

    except Exception as e:
        logger.error(json.dumps({
            'event': 'list_tags_error',
            'resourceArn': resource_arn,
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to list tags: {str(e)}')


def _tag_resource(body: Dict, request_id: str) -> Dict[str, Any]:
    """
    Add tags to a resource.
    Note: No Meta Graph API equivalent. Returns success with note.
    """
    try:
        resource_arn = body.get('resourceArn', '')
        tags = body.get('tags', [])

        if not resource_arn:
            return _error_response(400, 'resourceArn is required')
        if not tags:
            return _error_response(400, 'tags is required')

        formatted_tags = []
        for tag in tags:
            formatted_tags.append({
                'key': tag.get('key', ''),
                'value': tag.get('value', '')
            })

        logger.info(json.dumps({
            'event': 'resource_tagged',
            'resourceArn': resource_arn,
            'tagCount': len(formatted_tags),
            'note': 'Tags not supported via Meta Graph API — no-op',
            'requestId': request_id
        }))

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'success': True,
                'resourceArn': resource_arn,
                'tags': formatted_tags,
                'note': 'Tagging is not supported via Meta Graph API. '
            })
        }

    except Exception as e:
        logger.error(json.dumps({
            'event': 'tag_resource_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to tag resource: {str(e)}')


def _untag_resource(body: Dict, request_id: str) -> Dict[str, Any]:
    """
    Remove tags from a resource.
    Note: No Meta Graph API equivalent. Returns success with note.
    """
    try:
        resource_arn = body.get('resourceArn', '')
        tag_keys = body.get('tagKeys', [])

        if not resource_arn:
            return _error_response(400, 'resourceArn is required')
        if not tag_keys:
            return _error_response(400, 'tagKeys is required')

        logger.info(json.dumps({
            'event': 'resource_untagged',
            'resourceArn': resource_arn,
            'tagKeysRemoved': tag_keys,
            'note': 'Tags not supported via Meta Graph API — no-op',
            'requestId': request_id
        }))

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'success': True,
                'resourceArn': resource_arn,
                'tagKeysRemoved': tag_keys,
                'note': 'Tagging is not supported via Meta Graph API. '
            })
        }

    except Exception as e:
        logger.error(json.dumps({
            'event': 'untag_resource_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to untag resource: {str(e)}')


# ============================================================================
# SNS SUBSCRIPTION FOR WABA EVENTS
# ============================================================================

def _subscribe_waba_to_sns(waba_id: str, body: Dict, request_id: str) -> Dict[str, Any]:
    """
    Subscribe a WABA to receive WhatsApp events.
    
    Meta Graph API: POST /{meta_waba_id}/subscribed_apps
    Also stores the subscription config in SystemConfig for tracking.
    
    Body params:
    - snsTopicArn (optional): SNS topic ARN, defaults to stack-wecare-digital topic
    - roleArn (optional): IAM role ARN for SNS publish permissions
    """
    try:
        if not waba_id:
            return _error_response(400, 'wabaId is required')

        if not waba_id.startswith('waba-'):
            waba_id = f'waba-{waba_id}'

        meta_waba_id = _resolve_meta_waba_id(waba_id)
        topic_arn = body.get('snsTopicArn', SNS_TOPIC_ARN)
        role_arn = body.get('roleArn', '')

        # Subscribe app to WABA via Meta Graph API
        _meta_request(f'{meta_waba_id}/subscribed_apps', method='POST')

        # Store subscription in SystemConfig for tracking
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        config_table.put_item(Item={
            'id': f'waba_sns_subscription_{waba_id}',
            'configValue': json.dumps({
                'wabaId': waba_id,
                'metaWabaId': meta_waba_id,
                'snsTopicArn': topic_arn,
                'roleArn': role_arn,
                'subscribedAt': datetime.utcnow().isoformat(),
                'status': 'ACTIVE'
            }),
            'updatedAt': datetime.utcnow().isoformat()
        })

        logger.info(json.dumps({
            'event': 'waba_subscribed_to_sns',
            'wabaId': waba_id,
            'metaWabaId': meta_waba_id,
            'snsTopicArn': topic_arn,
            'requestId': request_id
        }))

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'success': True,
                'wabaId': waba_id,
                'snsTopicArn': topic_arn,
                'status': 'ACTIVE'
            })
        }

    except Exception as e:
        logger.error(json.dumps({
            'event': 'subscribe_waba_sns_error',
            'wabaId': waba_id,
            'error': str(e),
            'errorType': type(e).__name__,
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to subscribe WABA to SNS: {str(e)}')


def _unsubscribe_waba_from_sns(waba_id: str, body: Dict, request_id: str) -> Dict[str, Any]:
    """
    Unsubscribe a WABA from events.
    Meta Graph API: DELETE /{meta_waba_id}/subscribed_apps
    """
    try:
        if not waba_id:
            return _error_response(400, 'wabaId is required')

        if not waba_id.startswith('waba-'):
            waba_id = f'waba-{waba_id}'

        meta_waba_id = _resolve_meta_waba_id(waba_id)

        # Unsubscribe app from WABA via Meta Graph API
        _meta_request(f'{meta_waba_id}/subscribed_apps', method='DELETE')

        # Update SystemConfig
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        config_table.put_item(Item={
            'id': f'waba_sns_subscription_{waba_id}',
            'configValue': json.dumps({
                'wabaId': waba_id,
                'metaWabaId': meta_waba_id,
                'snsTopicArn': '',
                'roleArn': '',
                'unsubscribedAt': datetime.utcnow().isoformat(),
                'status': 'INACTIVE'
            }),
            'updatedAt': datetime.utcnow().isoformat()
        })

        logger.info(json.dumps({
            'event': 'waba_unsubscribed_from_sns',
            'wabaId': waba_id,
            'metaWabaId': meta_waba_id,
            'requestId': request_id
        }))

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'success': True,
                'wabaId': waba_id,
                'status': 'INACTIVE'
            })
        }

    except Exception as e:
        logger.error(json.dumps({
            'event': 'unsubscribe_waba_sns_error',
            'wabaId': waba_id,
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to unsubscribe WABA from SNS: {str(e)}')


def _get_sns_subscription_status(waba_id: str, request_id: str) -> Dict[str, Any]:
    """
    Get the current SNS subscription status for a WABA.
    Checks both the SystemConfig record and the live WABA subscribed apps.
    """
    try:
        if not waba_id:
            return _error_response(400, 'wabaId is required')

        if not waba_id.startswith('waba-'):
            waba_id = f'waba-{waba_id}'

        meta_waba_id = _resolve_meta_waba_id(waba_id)

        # Get stored subscription config
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        stored_config = {}
        try:
            response = config_table.get_item(Key={'id': f'waba_sns_subscription_{waba_id}'})
            if 'Item' in response:
                stored_config = json.loads(response['Item'].get('configValue', '{}'))
        except Exception:
            pass

        # Get live subscribed apps from Meta
        live_destinations = []
        try:
            subs_resp = _meta_request(f'{meta_waba_id}/subscribed_apps')
            live_destinations = subs_resp.get('data', [])
        except Exception:
            pass

        serialized_destinations = []
        for dest in live_destinations:
            serialized_destinations.append(_serialize_dict(dest) if isinstance(dest, dict) else dest)

        result = {
            'wabaId': waba_id,
            'metaWabaId': meta_waba_id,
            'storedConfig': stored_config,
            'liveEventDestinations': serialized_destinations,
            'isSubscribed': len(serialized_destinations) > 0,
            'defaultTopicArn': SNS_TOPIC_ARN
        }

        logger.info(json.dumps({
            'event': 'sns_subscription_status_fetched',
            'wabaId': waba_id,
            'isSubscribed': result['isSubscribed'],
            'requestId': request_id
        }))

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps(result)
        }

    except Exception as e:
        logger.error(json.dumps({
            'event': 'get_sns_subscription_status_error',
            'wabaId': waba_id,
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to get SNS subscription status: {str(e)}')


# ============================================================================
# PHONE REGISTRATION & MIGRATION
# ============================================================================

def _request_otp(body: Dict, request_id: str) -> Dict[str, Any]:
    """
    Request OTP/PIN for phone number verification.
    Meta Graph API: POST /{meta_phone_id}/request_code
    
    Body params:
    - phoneNumberId: AWS phone number ID
    - method: 'SMS' or 'VOICE' (default: SMS)
    - language: Language code (default: 'en_US')
    """
    try:
        phone_number_id = body.get('phoneNumberId', '')
        method = body.get('method', 'SMS').upper()
        language = body.get('language', 'en_US')

        if not phone_number_id:
            return _error_response(400, 'phoneNumberId is required')

        if not phone_number_id.startswith('phone-number-id-'):
            phone_number_id = f'phone-number-id-{phone_number_id}'

        meta_phone_id = _resolve_meta_phone_id(phone_number_id)

        # Request verification code via Meta Graph API
        payload = json.dumps({
            'code_method': method,
            'language': language,
        }).encode('utf-8')

        _meta_request(
            f'{meta_phone_id}/request_code',
            method='POST',
            data=payload,
            content_type='application/json'
        )

        logger.info(json.dumps({
            'event': 'otp_requested',
            'phoneNumberId': phone_number_id,
            'metaPhoneId': meta_phone_id,
            'method': method,
            'language': language,
            'requestId': request_id
        }))

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'success': True,
                'phoneNumberId': phone_number_id,
                'method': method,
                'message': f'Verification code sent via {method}'
            })
        }

    except Exception as e:
        logger.error(json.dumps({
            'event': 'request_otp_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to request OTP: {str(e)}')


def _verify_otp(body: Dict, request_id: str) -> Dict[str, Any]:
    """
    Verify OTP/PIN code for phone number verification.
    Meta Graph API: POST /{meta_phone_id}/verify_code
    
    Body params:
    - phoneNumberId: AWS phone number ID
    - code: The verification code/PIN received
    """
    try:
        phone_number_id = body.get('phoneNumberId', '')
        code = body.get('code', '')

        if not phone_number_id:
            return _error_response(400, 'phoneNumberId is required')
        if not code:
            return _error_response(400, 'code is required')

        if not phone_number_id.startswith('phone-number-id-'):
            phone_number_id = f'phone-number-id-{phone_number_id}'

        meta_phone_id = _resolve_meta_phone_id(phone_number_id)

        payload = json.dumps({
            'code': str(code),
        }).encode('utf-8')

        response = _meta_request(
            f'{meta_phone_id}/verify_code',
            method='POST',
            data=payload,
            content_type='application/json'
        )

        verified = response.get('success', False)

        logger.info(json.dumps({
            'event': 'otp_verified',
            'phoneNumberId': phone_number_id,
            'metaPhoneId': meta_phone_id,
            'verified': verified,
            'requestId': request_id
        }))

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'success': verified,
                'phoneNumberId': phone_number_id,
                'verified': verified
            })
        }

    except Exception as e:
        logger.error(json.dumps({
            'event': 'verify_otp_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to verify OTP: {str(e)}')


def _register_phone(body: Dict, request_id: str) -> Dict[str, Any]:
    """
    Register a phone number with a WABA.
    Meta Graph API: POST /{meta_phone_id}/register
    
    Body params:
    - phoneNumberId: AWS phone number ID
    - pin: 6-digit PIN for two-step verification (optional)
    """
    try:
        phone_number_id = body.get('phoneNumberId', '')
        pin = body.get('pin', '')

        if not phone_number_id:
            return _error_response(400, 'phoneNumberId is required')

        if not phone_number_id.startswith('phone-number-id-'):
            phone_number_id = f'phone-number-id-{phone_number_id}'

        meta_phone_id = _resolve_meta_phone_id(phone_number_id)

        # Register phone via Meta Graph API
        register_payload = {
            'messaging_product': 'whatsapp',
        }
        if pin:
            register_payload['pin'] = str(pin)

        payload = json.dumps(register_payload).encode('utf-8')

        _meta_request(
            f'{meta_phone_id}/register',
            method='POST',
            data=payload,
            content_type='application/json'
        )

        # Store registration record in SystemConfig
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        config_table.put_item(Item={
            'id': f'phone_registration_{phone_number_id}',
            'configValue': json.dumps({
                'phoneNumberId': phone_number_id,
                'metaPhoneId': meta_phone_id,
                'pin': pin,
                'registeredAt': datetime.utcnow().isoformat(),
                'status': 'REGISTERED'
            }),
            'updatedAt': datetime.utcnow().isoformat()
        })

        logger.info(json.dumps({
            'event': 'phone_registered',
            'phoneNumberId': phone_number_id,
            'metaPhoneId': meta_phone_id,
            'hasPin': bool(pin),
            'requestId': request_id
        }))

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'success': True,
                'phoneNumberId': phone_number_id,
                'status': 'REGISTERED',
                'hasPin': bool(pin)
            })
        }

    except Exception as e:
        logger.error(json.dumps({
            'event': 'register_phone_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to register phone: {str(e)}')


def _migrate_phone(body: Dict, request_id: str) -> Dict[str, Any]:
    """
    Migrate a phone number between WABAs.
    Meta Graph API: POST /{meta_phone_id}/register on target WABA
    
    Body params:
    - phoneNumberId: AWS phone number ID to migrate
    - sourceWabaId: Source WABA ID
    - targetWabaId: Target WABA ID
    - pin: 6-digit PIN for two-step verification (optional, for re-registration)
    - sendPin: If true, sends the PIN via SMS before migration (optional)
    - pinMethod: 'SMS' or 'VOICE' for PIN delivery (default: SMS)
    """
    try:
        phone_number_id = body.get('phoneNumberId', '')
        source_waba_id = body.get('sourceWabaId', '')
        target_waba_id = body.get('targetWabaId', '')
        pin = body.get('pin', '')
        send_pin = body.get('sendPin', False)
        pin_method = body.get('pinMethod', 'SMS').upper()

        if not phone_number_id:
            return _error_response(400, 'phoneNumberId is required')
        if not target_waba_id:
            return _error_response(400, 'targetWabaId is required')

        if not phone_number_id.startswith('phone-number-id-'):
            phone_number_id = f'phone-number-id-{phone_number_id}'

        meta_phone_id = _resolve_meta_phone_id(phone_number_id)

        # Step 1: Optionally send PIN before migration
        if send_pin:
            try:
                otp_payload = json.dumps({
                    'code_method': pin_method,
                    'language': 'en_US',
                }).encode('utf-8')

                _meta_request(
                    f'{meta_phone_id}/request_code',
                    method='POST',
                    data=otp_payload,
                    content_type='application/json'
                )
                logger.info(json.dumps({
                    'event': 'migration_pin_sent',
                    'phoneNumberId': phone_number_id,
                    'metaPhoneId': meta_phone_id,
                    'method': pin_method,
                    'requestId': request_id
                }))
            except Exception as pin_err:
                logger.warning(f"Failed to send migration PIN: {pin_err}")
                return _error_response(500, f'Failed to send PIN: {str(pin_err)}')

        # Step 2: Register phone on target WABA via Meta Graph API
        register_payload = {
            'messaging_product': 'whatsapp',
        }
        if pin:
            register_payload['pin'] = str(pin)

        payload = json.dumps(register_payload).encode('utf-8')

        _meta_request(
            f'{meta_phone_id}/register',
            method='POST',
            data=payload,
            content_type='application/json'
        )

        # Step 3: Store migration record
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        migration_record = {
            'id': f'phone_migration_{phone_number_id}_{int(datetime.utcnow().timestamp())}',
            'configValue': json.dumps({
                'phoneNumberId': phone_number_id,
                'metaPhoneId': meta_phone_id,
                'sourceWabaId': source_waba_id,
                'targetWabaId': target_waba_id,
                'pin': pin,
                'pinSent': send_pin,
                'pinMethod': pin_method,
                'migratedAt': datetime.utcnow().isoformat(),
                'status': 'INITIATED'
            }),
            'updatedAt': datetime.utcnow().isoformat()
        }
        config_table.put_item(Item=migration_record)

        logger.info(json.dumps({
            'event': 'phone_migration_initiated',
            'phoneNumberId': phone_number_id,
            'metaPhoneId': meta_phone_id,
            'sourceWabaId': source_waba_id,
            'targetWabaId': target_waba_id,
            'pinSent': send_pin,
            'requestId': request_id
        }))

        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'success': True,
                'phoneNumberId': phone_number_id,
                'sourceWabaId': source_waba_id,
                'targetWabaId': target_waba_id,
                'pinSent': send_pin,
                'status': 'INITIATED'
            })
        }

    except Exception as e:
        logger.error(json.dumps({
            'event': 'migrate_phone_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, f'Failed to migrate phone: {str(e)}')
