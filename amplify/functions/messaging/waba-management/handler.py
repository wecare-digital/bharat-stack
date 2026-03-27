"""
WABA Management Lambda Function

Purpose: Manage WhatsApp Business Accounts via AWS EUM Social API
Implements:
- GetLinkedWhatsAppBusinessAccount - Get WABA details (phone quality, limits)
- GetLinkedWhatsAppBusinessAccountPhoneNumber - Get phone details
- ListLinkedWhatsAppBusinessAccounts - List all WABAs
- DeleteWhatsAppMessageMedia - Delete uploaded media
- GetWhatsAppMessageMedia - Download media from WhatsApp
- PostWhatsAppMessageMedia - Upload media to WhatsApp for sending
- PutWhatsAppBusinessAccountEventDestinations - Configure SNS event destinations
- ListTagsForResource - List tags on WABA/phone
- TagResource - Add tags to resources
- UntagResource - Remove tags from resources

AWS EUM Social API Reference:
https://docs.aws.amazon.com/social-messaging/latest/APIReference/Welcome.html
"""

import os
import json
import logging
import boto3
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime

from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin

# Configure logging
from lambda_utils.logging import get_logger

logger = get_logger(__name__)

# AWS clients
social_messaging = boto3.client('socialmessaging', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
sns_client = boto3.client('sns', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Environment variables
SYSTEM_CONFIG_TABLE = os.environ.get('SYSTEM_CONFIG_TABLE', 'stack-wecare-digital-SystemConfigTable')
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:775261844268:stack-wecare-digital')

# CORS headers
# CORS headers provided by lambda_utils.response.cors_headers(origin)


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
    API: ListLinkedWhatsAppBusinessAccounts
    """
    try:
        wabas = []
        next_token = None
        
        while True:
            params = {}
            if next_token:
                params['nextToken'] = next_token
            
            response = social_messaging.list_linked_whatsapp_business_accounts(**params)
            
            for account in response.get('linkedAccounts', []):
                link_date = account.get('linkDate')
                wabas.append({
                    'id': account.get('id', ''),
                    'wabaId': account.get('wabaId', ''),
                    'wabaName': account.get('wabaName', ''),
                    'arn': account.get('arn', ''),
                    'registrationStatus': account.get('registrationStatus', ''),
                    'linkDate': link_date.isoformat() if isinstance(link_date, datetime) else link_date,
                    'enableSending': account.get('enableSending', False),
                    'enableReceiving': account.get('enableReceiving', False),
                    'eventDestinations': account.get('eventDestinations', [])
                })
            
            next_token = response.get('nextToken')
            if not next_token:
                break
        
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
    API: GetLinkedWhatsAppBusinessAccount
    
    Returns:
    - WABA info (name, status, event destinations)
    - Phone numbers with quality ratings (GREEN/YELLOW/RED)
    - Messaging limits
    """
    try:
        # Ensure waba_id has correct format
        if not waba_id.startswith('waba-'):
            waba_id = f'waba-{waba_id}'
        
        response = social_messaging.get_linked_whatsapp_business_account(id=waba_id)
        account = response.get('account', {})
        
        # Process phone numbers with quality info
        phone_numbers = []
        for phone in account.get('phoneNumbers', []):
            phone_numbers.append({
                'phoneNumberId': phone.get('phoneNumberId', ''),
                'phoneNumber': phone.get('phoneNumber', ''),
                'displayPhoneNumber': phone.get('displayPhoneNumber', ''),
                'displayPhoneNumberName': phone.get('displayPhoneNumberName', ''),
                'qualityRating': phone.get('qualityRating', 'UNKNOWN'),
                'metaPhoneNumberId': phone.get('metaPhoneNumberId', ''),
                'dataLocalizationRegion': phone.get('dataLocalizationRegion', ''),
                'arn': phone.get('arn', '')
            })
        
        link_date = account.get('linkDate')
        waba_details = {
            'id': account.get('id', ''),
            'wabaId': account.get('wabaId', ''),
            'wabaName': account.get('wabaName', ''),
            'arn': account.get('arn', ''),
            'registrationStatus': account.get('registrationStatus', ''),
            'linkDate': link_date.isoformat() if isinstance(link_date, datetime) else link_date,
            'enableSending': account.get('enableSending', False),
            'enableReceiving': account.get('enableReceiving', False),
            'eventDestinations': account.get('eventDestinations', []),
            'phoneNumbers': phone_numbers
        }
        
        logger.info(json.dumps({
            'event': 'waba_details_fetched',
            'wabaId': waba_id,
            'phoneCount': len(phone_numbers),
            'requestId': request_id
        }))
        
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps(waba_details)
        }
        
    except social_messaging.exceptions.ResourceNotFoundException:
        return _error_response(404, f'WABA not found: {waba_id}')
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
    API: GetLinkedWhatsAppBusinessAccountPhoneNumber
    
    Returns:
    - Phone number info
    - Quality rating (GREEN/YELLOW/RED)
    - Display name
    - Data localization region
    """
    try:
        # Ensure phone_id has correct format
        if not phone_id.startswith('phone-number-id-'):
            phone_id = f'phone-number-id-{phone_id}'
        
        response = social_messaging.get_linked_whatsapp_business_account_phone_number(id=phone_id)
        
        phone = response.get('phoneNumber', {})
        linked_waba_id = response.get('linkedWhatsAppBusinessAccountId', '')
        
        phone_details = {
            'phoneNumberId': phone.get('phoneNumberId', ''),
            'phoneNumber': phone.get('phoneNumber', ''),
            'displayPhoneNumber': phone.get('displayPhoneNumber', ''),
            'displayPhoneNumberName': phone.get('displayPhoneNumberName', ''),
            'qualityRating': phone.get('qualityRating', 'UNKNOWN'),
            'metaPhoneNumberId': phone.get('metaPhoneNumberId', ''),
            'dataLocalizationRegion': phone.get('dataLocalizationRegion', ''),
            'arn': phone.get('arn', ''),
            'linkedWabaId': linked_waba_id
        }
        
        logger.info(json.dumps({
            'event': 'phone_details_fetched',
            'phoneNumberId': phone_id,
            'qualityRating': phone_details['qualityRating'],
            'requestId': request_id
        }))
        
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps(phone_details)
        }
        
    except social_messaging.exceptions.ResourceNotFoundException:
        return _error_response(404, f'Phone number not found: {phone_id}')
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
    API: DeleteWhatsAppMessageMedia
    
    Note: This only deletes from WhatsApp servers.
    S3 cleanup should be done separately.
    """
    try:
        if not media_id:
            return _error_response(400, 'mediaId is required')
        
        if not phone_number_id:
            return _error_response(400, 'phoneNumberId is required')
        
        # Ensure phone_number_id has correct format
        if not phone_number_id.startswith('phone-number-id-'):
            phone_number_id = f'phone-number-id-{phone_number_id}'
        
        response = social_messaging.delete_whatsapp_message_media(
            mediaId=media_id,
            originationPhoneNumberId=phone_number_id
        )
        
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
        
    except social_messaging.exceptions.ResourceNotFoundException:
        return _error_response(404, f'Media not found: {media_id}')
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
    API: GetWhatsAppMessageMedia
    
    Can either:
    - Return metadata only (metadataOnly=true)
    - Download to S3 (destinationS3File)
    - Return presigned URL (destinationS3PresignedUrl)
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
        
        params = {
            'mediaId': media_id,
            'originationPhoneNumberId': phone_number_id,
            'metadataOnly': metadata_only
        }
        
        # If not metadata only, specify S3 destination
        if not metadata_only:
            s3_key = f'stack/whatsapp-media/downloads/wecare-digital-{media_id}'
            params['destinationS3File'] = {
                'bucketName': MEDIA_BUCKET,
                'key': s3_key
            }
        
        response = social_messaging.get_whatsapp_message_media(**params)
        
        result = {
            'mediaId': media_id,
            'mimeType': response.get('mimeType', ''),
            'fileSize': response.get('fileSize', 0),
        }
        
        if not metadata_only:
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
        
    except social_messaging.exceptions.ResourceNotFoundException:
        return _error_response(404, f'Media not found: {media_id}')
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
    API: PostWhatsAppMessageMedia
    
    Uploads from S3 to WhatsApp servers for use in messages.
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
        
        response = social_messaging.post_whatsapp_message_media(
            originationPhoneNumberId=phone_number_id,
            sourceS3File={
                'bucketName': MEDIA_BUCKET,
                'key': s3_key
            }
        )
        
        result = {
            'mediaId': response.get('mediaId', ''),
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
    API: PutWhatsAppBusinessAccountEventDestinations
    
    Sets up SNS topics to receive WhatsApp events (message status, quality updates, etc.)
    """
    try:
        if not waba_id:
            return _error_response(400, 'wabaId is required')
        
        event_destinations = body.get('eventDestinations', [])
        if not event_destinations:
            return _error_response(400, 'eventDestinations is required')
        
        # Ensure waba_id has correct format
        if not waba_id.startswith('waba-'):
            waba_id = f'waba-{waba_id}'
        
        # Format event destinations for API
        formatted_destinations = []
        for dest in event_destinations:
            formatted_destinations.append({
                'eventDestinationArn': dest.get('eventDestinationArn', ''),
                'roleArn': dest.get('roleArn', '')
            })
        
        social_messaging.put_whatsapp_business_account_event_destinations(
            id=waba_id,
            eventDestinations=formatted_destinations
        )
        
        logger.info(json.dumps({
            'event': 'event_destinations_updated',
            'wabaId': waba_id,
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
    API: ListTagsForResource
    """
    try:
        if not resource_arn:
            return _error_response(400, 'resourceArn is required')
        
        response = social_messaging.list_tags_for_resource(resourceArn=resource_arn)
        
        tags = response.get('tags', [])
        
        logger.info(json.dumps({
            'event': 'tags_listed',
            'resourceArn': resource_arn,
            'tagCount': len(tags),
            'requestId': request_id
        }))
        
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'resourceArn': resource_arn,
                'tags': tags
            })
        }
        
    except social_messaging.exceptions.ResourceNotFoundException:
        return _error_response(404, f'Resource not found: {resource_arn}')
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
    API: TagResource
    """
    try:
        resource_arn = body.get('resourceArn', '')
        tags = body.get('tags', [])
        
        if not resource_arn:
            return _error_response(400, 'resourceArn is required')
        if not tags:
            return _error_response(400, 'tags is required')
        
        # Format tags for API
        formatted_tags = []
        for tag in tags:
            formatted_tags.append({
                'key': tag.get('key', ''),
                'value': tag.get('value', '')
            })
        
        social_messaging.tag_resource(
            resourceArn=resource_arn,
            tags=formatted_tags
        )
        
        logger.info(json.dumps({
            'event': 'resource_tagged',
            'resourceArn': resource_arn,
            'tagCount': len(formatted_tags),
            'requestId': request_id
        }))
        
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'success': True,
                'resourceArn': resource_arn,
                'tags': formatted_tags
            })
        }
        
    except social_messaging.exceptions.ResourceNotFoundException:
        return _error_response(404, f'Resource not found: {resource_arn}')
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
    API: UntagResource
    """
    try:
        resource_arn = body.get('resourceArn', '')
        tag_keys = body.get('tagKeys', [])
        
        if not resource_arn:
            return _error_response(400, 'resourceArn is required')
        if not tag_keys:
            return _error_response(400, 'tagKeys is required')
        
        social_messaging.untag_resource(
            resourceArn=resource_arn,
            tagKeys=tag_keys
        )
        
        logger.info(json.dumps({
            'event': 'resource_untagged',
            'resourceArn': resource_arn,
            'tagKeysRemoved': tag_keys,
            'requestId': request_id
        }))
        
        return {
            'statusCode': 200,
            'headers': cors_headers(origin),
            'body': json.dumps({
                'success': True,
                'resourceArn': resource_arn,
                'tagKeysRemoved': tag_keys
            })
        }
        
    except social_messaging.exceptions.ResourceNotFoundException:
        return _error_response(404, f'Resource not found: {resource_arn}')
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
    Subscribe a WABA to SNS topic for receiving WhatsApp events.
    
    Calls PutWhatsAppBusinessAccountEventDestinations to set the SNS topic
    as the event destination for the WABA (so AWS EUM sends events to SNS).
    Stores the subscription config in SystemConfig for tracking.
    
    Body params:
    - snsTopicArn (optional): SNS topic ARN, defaults to stack-wecare-digital topic
    - roleArn (optional): IAM role ARN for SNS publish permissions
    """
    try:
        if not waba_id:
            return _error_response(400, 'wabaId is required')
        
        if not waba_id.startswith('waba-'):
            waba_id = f'waba-{waba_id}'
        
        topic_arn = body.get('snsTopicArn', SNS_TOPIC_ARN)
        role_arn = body.get('roleArn', '')
        
        # Build event destination
        event_destination = {'eventDestinationArn': topic_arn}
        if role_arn:
            event_destination['roleArn'] = role_arn
        
        # Call AWS EUM API to set event destinations
        social_messaging.put_whatsapp_business_account_event_destinations(
            id=waba_id,
            eventDestinations=[event_destination]
        )
        
        # Store subscription in SystemConfig for tracking
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        config_table.put_item(Item={
            'id': f'waba_sns_subscription_{waba_id}',
            'configValue': json.dumps({
                'wabaId': waba_id,
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
    Unsubscribe a WABA from SNS by clearing event destinations.
    """
    try:
        if not waba_id:
            return _error_response(400, 'wabaId is required')
        
        if not waba_id.startswith('waba-'):
            waba_id = f'waba-{waba_id}'
        
        # Clear event destinations by setting empty list
        social_messaging.put_whatsapp_business_account_event_destinations(
            id=waba_id,
            eventDestinations=[]
        )
        
        # Update SystemConfig
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        config_table.put_item(Item={
            'id': f'waba_sns_subscription_{waba_id}',
            'configValue': json.dumps({
                'wabaId': waba_id,
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
    Checks both the SystemConfig record and the live WABA event destinations.
    """
    try:
        if not waba_id:
            return _error_response(400, 'wabaId is required')
        
        if not waba_id.startswith('waba-'):
            waba_id = f'waba-{waba_id}'
        
        # Get stored subscription config
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        stored_config = {}
        try:
            response = config_table.get_item(Key={'id': f'waba_sns_subscription_{waba_id}'})
            if 'Item' in response:
                stored_config = json.loads(response['Item'].get('configValue', '{}'))
        except Exception:
            pass
        
        # Get live event destinations from WABA
        live_destinations = []
        try:
            waba_response = social_messaging.get_linked_whatsapp_business_account(id=waba_id)
            account = waba_response.get('account', {})
            live_destinations = account.get('eventDestinations', [])
        except Exception:
            pass
        
        # Serialize any datetime objects in live_destinations
        serialized_destinations = []
        for dest in live_destinations:
            serialized_destinations.append(_serialize_dict(dest) if isinstance(dest, dict) else dest)
        
        result = {
            'wabaId': waba_id,
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
    Sends a verification code via SMS or voice call.
    
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
        
        # Request verification code
        params = {
            'originationPhoneNumberId': phone_number_id,
            'codeVerificationMethod': method,
            'languageCode': language,
        }
        
        response = social_messaging.send_whatsapp_phone_number_verification_code(**params)
        
        logger.info(json.dumps({
            'event': 'otp_requested',
            'phoneNumberId': phone_number_id,
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
        
        response = social_messaging.verify_whatsapp_phone_number(
            originationPhoneNumberId=phone_number_id,
            verificationCode=str(code),
        )
        
        verified = response.get('verified', False)
        
        logger.info(json.dumps({
            'event': 'otp_verified',
            'phoneNumberId': phone_number_id,
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
        
        # Build registration params
        # Note: The actual registration is done via Meta Graph API
        # AWS EUM doesn't have a direct register endpoint
        # This stores the registration intent and PIN in SystemConfig
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        config_table.put_item(Item={
            'id': f'phone_registration_{phone_number_id}',
            'configValue': json.dumps({
                'phoneNumberId': phone_number_id,
                'pin': pin,
                'registeredAt': datetime.utcnow().isoformat(),
                'status': 'REGISTERED'
            }),
            'updatedAt': datetime.utcnow().isoformat()
        })
        
        logger.info(json.dumps({
            'event': 'phone_registered',
            'phoneNumberId': phone_number_id,
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
        
        # Step 1: Optionally send PIN before migration
        if send_pin:
            try:
                social_messaging.send_whatsapp_phone_number_verification_code(
                    originationPhoneNumberId=phone_number_id,
                    codeVerificationMethod=pin_method,
                    languageCode='en_US',
                )
                logger.info(json.dumps({
                    'event': 'migration_pin_sent',
                    'phoneNumberId': phone_number_id,
                    'method': pin_method,
                    'requestId': request_id
                }))
            except Exception as pin_err:
                logger.warning(f"Failed to send migration PIN: {pin_err}")
                return _error_response(500, f'Failed to send PIN: {str(pin_err)}')
        
        # Step 2: Store migration record
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        migration_record = {
            'id': f'phone_migration_{phone_number_id}_{int(datetime.utcnow().timestamp())}',
            'configValue': json.dumps({
                'phoneNumberId': phone_number_id,
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
