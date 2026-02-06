"""
Airtel OBD (Outbound Dialer) Campaign Lambda Function

Purpose: Manage bulk voice campaigns via Airtel IQ Telephony API
Features:
- Upload audio prompts
- Upload CSV contact lists
- Create and manage OBD campaigns

API Endpoints:
- Upload Audio: POST https://openapi.airtel.in/gateway/airtel-xchange/uploadPrompts
- Upload CSV: POST https://openapi.airtel.in/gateway/airtel-xchange/campaign-manager-v3/file/s3/upload
- Create Campaign: POST https://iqtelephony.airtel.in/gateway/airtel-xchange/campaign-manager/v2/createCampaign

Secrets: wecare/airtel/obd
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
from typing import Dict, Any, List
from decimal import Decimal

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
s3 = boto3.client('s3', region_name=AWS_REGION)
secrets_client = boto3.client('secretsmanager', region_name=AWS_REGION)

# Environment variables
OBD_CAMPAIGNS_TABLE = os.environ.get('OBD_CAMPAIGNS_TABLE', 'base-wecare-digital-OBDCampaigns')
S3_BUCKET = os.environ.get('S3_BUCKET', 'wecare-digital-assets')
AIRTEL_OBD_SECRET_NAME = os.environ.get('AIRTEL_OBD_SECRET_NAME', 'wecare/airtel/obd')
TTL_DAYS = 90

# API Hosts
AIRTEL_OPENAPI_HOST = 'openapi.airtel.in'
AIRTEL_IQTELEPHONY_HOST = 'iqtelephony.airtel.in'
AIRTEL_DEFAULT_AUDIO_URL = 'https://openapi.airtel.in/gateway/airtel-xchange/assets/audios/global/Default_Airtel_Jingle.wav'

# Cached secrets
_secrets_cache = None


def _get_secrets() -> Dict[str, str]:
    """Fetch Airtel OBD credentials from Secrets Manager (cached)."""
    global _secrets_cache
    if _secrets_cache is not None:
        return _secrets_cache
    
    try:
        response = secrets_client.get_secret_value(SecretId=AIRTEL_OBD_SECRET_NAME)
        _secrets_cache = json.loads(response['SecretString'])
        logger.info(f"Loaded secrets from {AIRTEL_OBD_SECRET_NAME}")
        return _secrets_cache
    except Exception as e:
        logger.error(f"Failed to load secrets: {str(e)}")
        return {}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle OBD campaign operations."""
    request_id = context.aws_request_id if context else str(uuid.uuid4())
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'POST')
    path = event.get('rawPath', event.get('path', ''))
    
    try:
        body = {}
        if event.get('body'):
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        
        if '/upload-audio' in path:
            return _upload_audio(body, request_id)
        elif '/upload-csv' in path:
            return _upload_csv(body, request_id)
        elif '/create' in path:
            return _create_campaign(body, request_id)
        elif '/status' in path:
            campaign_id = event.get('pathParameters', {}).get('campaignId') or body.get('campaignId')
            return _get_campaign_status(campaign_id, request_id)
        elif '/list' in path or http_method == 'GET':
            return _list_campaigns(event.get('queryStringParameters', {}), request_id)
        else:
            if http_method == 'POST':
                return _create_campaign(body, request_id)
            return _response(404, {'error': 'Endpoint not found'})
        
    except json.JSONDecodeError:
        return _response(400, {'error': 'Invalid JSON'})
    except Exception as e:
        logger.error(f"OBD error: {str(e)}")
        return _response(500, {'error': 'Internal server error'})


def _upload_audio(body: Dict, request_id: str) -> Dict[str, Any]:
    """Upload audio file to Airtel for OBD campaigns."""
    try:
        secrets = _get_secrets()
        customer_id = secrets.get('customer_id')
        auth_token = secrets.get('auth')
        
        if not customer_id or not auth_token:
            return _response(500, {'error': 'Airtel OBD credentials not configured'})
        
        audio_url = body.get('audioUrl')
        file_name = body.get('fileName', f'audio_{int(time.time())}.wav')
        
        if not audio_url:
            return _response(400, {'error': 'audioUrl is required'})
        
        # Download audio
        if audio_url.startswith('s3://'):
            parts = audio_url.replace('s3://', '').split('/', 1)
            response = s3.get_object(Bucket=parts[0], Key=parts[1] if len(parts) > 1 else '')
            audio_data = response['Body'].read()
        elif audio_url.startswith('data:'):
            audio_data = base64.b64decode(audio_url.split(',')[1])
        else:
            req = urllib.request.Request(audio_url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                audio_data = resp.read()
        
        # Upload to Airtel
        url = f"https://{AIRTEL_OPENAPI_HOST}/gateway/airtel-xchange/uploadPrompts?customerId={customer_id}"
        boundary = f'----WebKitFormBoundary{uuid.uuid4().hex[:16]}'
        
        body_parts = [
            f'--{boundary}'.encode(),
            f'Content-Disposition: form-data; name="files"; filename="{file_name}"'.encode(),
            b'Content-Type: audio/wav', b'',
            audio_data,
            f'--{boundary}--'.encode()
        ]
        
        headers = {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Authorization': f'Basic {auth_token}',
            'requester-id': 'ironman'
        }
        
        req = urllib.request.Request(url, data=b'\r\n'.join(body_parts), headers=headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            return _response(200, {
                'success': True,
                'fileName': file_name,
                'audioUrl': result.get('url') or result.get('audioUrl'),
                'result': result
            })
            
    except Exception as e:
        logger.error(f"Audio upload error: {str(e)}")
        return _response(500, {'error': str(e)})


def _upload_csv(body: Dict, request_id: str) -> Dict[str, Any]:
    """Upload CSV contact list to Airtel."""
    try:
        secrets = _get_secrets()
        customer_id = secrets.get('customer_id')
        auth_token = secrets.get('auth')
        app_id = secrets.get('app_id', 'IRONMAN')
        
        if not customer_id or not auth_token:
            return _response(500, {'error': 'Airtel OBD credentials not configured'})
        
        contacts = body.get('contacts', [])
        csv_url = body.get('csvUrl')
        csv_data = body.get('csvData')
        
        if contacts:
            csv_content = "Number\n" + "\n".join([_clean_phone(c) for c in contacts if _clean_phone(c)])
            csv_bytes = csv_content.encode('utf-8')
        elif csv_url and csv_url.startswith('s3://'):
            parts = csv_url.replace('s3://', '').split('/', 1)
            response = s3.get_object(Bucket=parts[0], Key=parts[1] if len(parts) > 1 else '')
            csv_bytes = response['Body'].read()
        elif csv_data:
            csv_bytes = base64.b64decode(csv_data)
        else:
            return _response(400, {'error': 'contacts, csvUrl, or csvData is required'})
        
        file_name = f'obd_contacts_{int(time.time())}.csv'
        url = f"https://{AIRTEL_OPENAPI_HOST}/gateway/airtel-xchange/campaign-manager-v3/file/s3/upload?customerId={customer_id}&campaignType=OBD_CALL"
        
        boundary = f'----WebKitFormBoundary{uuid.uuid4().hex[:16]}'
        body_parts = [
            f'--{boundary}'.encode(),
            f'Content-Disposition: form-data; name="file"; filename="{file_name}"'.encode(),
            b'Content-Type: text/csv', b'',
            csv_bytes,
            f'--{boundary}--'.encode()
        ]
        
        headers = {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Authorization': f'Basic {auth_token}',
            'app-id': app_id
        }
        
        req = urllib.request.Request(url, data=b'\r\n'.join(body_parts), headers=headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            uploaded_name = result.get('fileName') or result.get('sheetFileName') or file_name
            return _response(200, {
                'success': True,
                'fileName': uploaded_name,
                'contactCount': len(contacts) if contacts else None,
                'result': result
            })
            
    except Exception as e:
        logger.error(f"CSV upload error: {str(e)}")
        return _response(500, {'error': str(e)})



def _create_campaign(body: Dict, request_id: str) -> Dict[str, Any]:
    """Create OBD campaign via Airtel API."""
    try:
        secrets = _get_secrets()
        customer_id = secrets.get('customer_id')
        campaign_auth = secrets.get('campaign_auth')
        app_id = secrets.get('app_id', 'IRONMAN')
        call_flow_id = secrets.get('call_flow_id', '')
        caller_id = secrets.get('caller_id', '')
        template_id = secrets.get('template_id', '')
        
        if not customer_id or not campaign_auth:
            return _response(500, {'error': 'Airtel OBD credentials not configured'})
        
        campaign_name = body.get('campaignName', f'OBD_Campaign_{int(time.time())}')
        contacts = body.get('contacts', [])
        sheet_file_names = body.get('sheetFileNames', [])
        audio_url = body.get('audioUrl', AIRTEL_DEFAULT_AUDIO_URL)
        caller_id = body.get('callerId', caller_id)
        retry_count = body.get('retryCount', 2)
        message_type = body.get('messageType', 'TRANSACTIONAL')
        
        # Upload CSV if contacts provided
        if contacts and not sheet_file_names:
            csv_result = _upload_csv_internal(contacts, secrets, request_id)
            if not csv_result.get('success'):
                return _response(500, {'error': csv_result.get('error', 'Failed to upload contacts')})
            sheet_file_names = [csv_result.get('fileName')]
        
        if not sheet_file_names:
            return _response(400, {'error': 'contacts or sheetFileNames is required'})
        
        campaign_id = str(uuid.uuid4())
        
        payload = {
            "customerId": customer_id,
            "templateId": template_id,
            "campaignName": campaign_name,
            "sheetFileNames": sheet_file_names,
            "campaignData": {
                "customerId": customer_id,
                "messageType": message_type,
                "callBackQueueActive": True,
                "callType": "OUTBOUND",
                "additionalObjectsForRequestBody": {
                    "metaData": {
                        "Channel": "OBD",
                        "campaignId": "${campaignId}",
                        "campaignName": "${campaignName}",
                        "highPriority": "${highPriority}",
                        "campaignEndTime": "${campaignEndTime}",
                        "dsrId": "${dsrId}",
                        "isV2": True
                    },
                    "callFlowConfigV2": {
                        "callFlowId": call_flow_id,
                        "inputVariables": [
                            {"name": "participantAddress", "value": "${Number}", "type": "phoneNumber"},
                            {"name": "callerId", "value": caller_id, "type": "phoneNumber"},
                            {"name": "audioURL", "value": audio_url, "type": "string"}
                        ],
                        "callBackURLs": [{"notifyURL": "queue", "eventType": "CALL"}]
                    }
                }
            },
            "inputCsvMappings": {"participantAddress": "Number"},
            "campaignType": "OBD_CALL",
            "retryDetail": {
                "maxRetryCount": retry_count,
                "retryConfig": {"retryType": "FIXED_INTERVAL", "retryIntervalList": [100, 200]},
                "retryCountToEventMap": {"1": ["default"], "2": ["busy"]}
            }
        }
        
        url = f"https://{AIRTEL_IQTELEPHONY_HOST}/gateway/airtel-xchange/campaign-manager/v2/createCampaign"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Basic {campaign_auth}',
            'app-id': app_id
        }
        
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            airtel_campaign_id = result.get('campaignId') or result.get('id')
            
            _store_campaign(campaign_id, campaign_name, airtel_campaign_id, sheet_file_names, audio_url)
            
            return _response(200, {
                'success': True,
                'campaignId': campaign_id,
                'airtelCampaignId': airtel_campaign_id,
                'campaignName': campaign_name,
                'status': 'created'
            })
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(f"Campaign create error: {e.code} - {error_body}")
        return _response(e.code, {'error': f'Airtel API error: {error_body[:200]}'})
    except Exception as e:
        logger.error(f"Campaign create error: {str(e)}")
        return _response(500, {'error': str(e)})


def _upload_csv_internal(contacts: List[str], secrets: Dict, request_id: str) -> Dict[str, Any]:
    """Internal CSV upload helper."""
    try:
        customer_id = secrets.get('customer_id')
        auth_token = secrets.get('auth')
        app_id = secrets.get('app_id', 'IRONMAN')
        
        csv_content = "Number\n" + "\n".join([_clean_phone(c) for c in contacts if _clean_phone(c)])
        csv_bytes = csv_content.encode('utf-8')
        file_name = f'obd_contacts_{int(time.time())}.csv'
        
        url = f"https://{AIRTEL_OPENAPI_HOST}/gateway/airtel-xchange/campaign-manager-v3/file/s3/upload?customerId={customer_id}&campaignType=OBD_CALL"
        boundary = f'----WebKitFormBoundary{uuid.uuid4().hex[:16]}'
        
        body_parts = [
            f'--{boundary}'.encode(),
            f'Content-Disposition: form-data; name="file"; filename="{file_name}"'.encode(),
            b'Content-Type: text/csv', b'', csv_bytes, f'--{boundary}--'.encode()
        ]
        
        headers = {
            'Content-Type': f'multipart/form-data; boundary={boundary}',
            'Authorization': f'Basic {auth_token}',
            'app-id': app_id
        }
        
        req = urllib.request.Request(url, data=b'\r\n'.join(body_parts), headers=headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            return {'success': True, 'fileName': result.get('fileName') or result.get('sheetFileName') or file_name}
    except Exception as e:
        return {'success': False, 'error': str(e)}


def _get_campaign_status(campaign_id: str, request_id: str) -> Dict[str, Any]:
    """Get campaign status."""
    try:
        if not campaign_id:
            return _response(400, {'error': 'campaignId is required'})
        
        table = dynamodb.Table(OBD_CAMPAIGNS_TABLE)
        result = table.get_item(Key={'id': campaign_id})
        campaign = result.get('Item')
        
        if campaign:
            return _response(200, {'campaign': _normalize_campaign(campaign)})
        return _response(404, {'error': 'Campaign not found'})
    except Exception as e:
        return _response(500, {'error': str(e)})


def _list_campaigns(params: Dict, request_id: str) -> Dict[str, Any]:
    """List OBD campaigns."""
    try:
        table = dynamodb.Table(OBD_CAMPAIGNS_TABLE)
        result = table.scan(Limit=int(params.get('limit', 50)))
        campaigns = result.get('Items', [])
        campaigns.sort(key=lambda x: float(x.get('createdAt', 0)), reverse=True)
        
        return _response(200, {'campaigns': [_normalize_campaign(c) for c in campaigns], 'count': len(campaigns)})
    except Exception as e:
        return _response(500, {'error': str(e)})


def _store_campaign(campaign_id: str, name: str, airtel_id: str, sheets: List[str], audio_url: str) -> None:
    """Store campaign record."""
    try:
        now = int(time.time())
        table = dynamodb.Table(OBD_CAMPAIGNS_TABLE)
        table.put_item(Item={
            'id': campaign_id,
            'campaignId': campaign_id,
            'airtelCampaignId': airtel_id or '',
            'campaignName': name,
            'sheetFileNames': sheets,
            'audioUrl': audio_url,
            'status': 'created',
            'createdAt': Decimal(str(now)),
            'updatedAt': Decimal(str(now)),
            'ttl': Decimal(str(now + (TTL_DAYS * 24 * 60 * 60)))
        })
    except Exception as e:
        logger.error(f"Store campaign error: {str(e)}")


def _normalize_campaign(item: Dict) -> Dict:
    """Normalize campaign for response."""
    return {
        'id': item.get('id', ''),
        'airtelCampaignId': item.get('airtelCampaignId', ''),
        'campaignName': item.get('campaignName', ''),
        'status': item.get('status', ''),
        'audioUrl': item.get('audioUrl', ''),
        'createdAt': int(float(item.get('createdAt', 0))),
    }


def _clean_phone(phone: str) -> str:
    """Clean phone number to 10 digits."""
    if not phone:
        return ''
    digits = ''.join(c for c in str(phone) if c.isdigit())
    if digits.startswith('91') and len(digits) == 12:
        digits = digits[2:]
    if digits.startswith('0') and len(digits) == 11:
        digits = digits[1:]
    return digits if len(digits) == 10 else ''


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
