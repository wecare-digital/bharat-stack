"""
Airtel OBD (Outbound Dialer) Campaign Lambda Function

Purpose: Manage bulk voice campaigns via Airtel IQ Telephony API
Features:
- Create OBD campaigns with default audio (Info-Only)
- Upload CSV contact lists with variables
- Store recordings in S3

API Endpoints:
- Upload CSV: POST https://openapi.airtel.in/gateway/airtel-xchange/campaign-manager-v3/file/s3/upload
- Create Campaign: POST https://iqtelephony.airtel.in/gateway/airtel-xchange/campaign-manager/v2/createCampaign

Airtel OBD Requirements:
- Call Flow: Voice (Info-Only)
- Audio: 16bits 8000Hz Mono WAV only
- Campaign Type: TRANSACTIONAL always
- CSV Column: participantNumber (not Number)

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
S3_BUCKET = os.environ.get('S3_BUCKET', 'app.wecare.digital')
S3_RECORDING_PREFIX = 'voice/voice-in/'
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
    query_params = event.get('queryStringParameters') or {}
    
    try:
        body = {}
        if event.get('body'):
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        
        if '/upload-csv' in path:
            return _upload_csv(body, request_id)
        elif '/create' in path:
            return _create_campaign(body, request_id)
        elif '/status' in path:
            campaign_id = event.get('pathParameters', {}).get('campaignId') or body.get('campaignId')
            return _get_campaign_status(campaign_id, request_id)
        elif '/list' in path or http_method == 'GET':
            return _list_campaigns(query_params, request_id)
        elif '/clear-logs' in path:
            return _clear_logs(body, request_id)
        elif '/delete' in path or http_method == 'DELETE':
            campaign_id = query_params.get('campaignId') or body.get('campaignId')
            hard_delete = query_params.get('hard') == 'true' or body.get('hardDelete', False)
            if body.get('clearAll'):
                return _clear_logs(body, request_id)
            return _delete_campaign(campaign_id, hard_delete, request_id)
        else:
            if http_method == 'POST':
                # Support clear-logs via POST body action
                if body.get('clearAll') or body.get('_action') == 'clear-logs':
                    return _clear_logs(body, request_id)
                return _create_campaign(body, request_id)
            if http_method == 'DELETE':
                campaign_id = query_params.get('campaignId')
                return _delete_campaign(campaign_id, False, request_id)
            return _response(404, {'error': 'Endpoint not found'})
        
    except json.JSONDecodeError:
        return _response(400, {'error': 'Invalid JSON'})
    except Exception as e:
        logger.error(f"OBD error: {str(e)}")
        return _response(500, {'error': 'Internal server error'})


def _upload_csv(body: Dict, request_id: str) -> Dict[str, Any]:
    """Upload CSV contact list to Airtel with variable support."""
    try:
        secrets = _get_secrets()
        customer_id = secrets.get('customer_id')
        auth_token = secrets.get('auth')
        app_id = secrets.get('app_id', 'IRONMAN')
        
        if not customer_id or not auth_token:
            return _response(500, {'error': 'Airtel OBD credentials not configured'})
        
        contacts = body.get('contacts', [])
        variables = body.get('variables', {})  # {phone: {var1: val1, var2: val2}}
        csv_url = body.get('csvUrl')
        csv_data = body.get('csvData')
        
        if contacts:
            # Build CSV with participantNumber column (Airtel requirement)
            # If variables provided, add variable columns
            var_names = []
            if variables:
                # Get all unique variable names
                for phone, vars_dict in variables.items():
                    var_names.extend(vars_dict.keys())
                var_names = list(set(var_names))
            
            if var_names:
                header = "participantNumber," + ",".join(var_names)
                rows = []
                for contact in contacts:
                    clean_phone = _clean_phone(contact)
                    if not clean_phone:
                        continue
                    phone_vars = variables.get(contact, variables.get(clean_phone, {}))
                    var_values = [str(phone_vars.get(v, '')) for v in var_names]
                    rows.append(f"{clean_phone},{','.join(var_values)}")
                csv_content = header + "\n" + "\n".join(rows)
            else:
                csv_content = "participantNumber\n" + "\n".join([_clean_phone(c) for c in contacts if _clean_phone(c)])
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
                'variableColumns': var_names if var_names else None,
                'result': result
            })
            
    except Exception as e:
        logger.error(f"CSV upload error: {str(e)}")
        return _response(500, {'error': str(e)})



def _create_campaign(body: Dict, request_id: str) -> Dict[str, Any]:
    """Create OBD campaign via Airtel API.
    
    Airtel OBD Requirements:
    - Call Flow: Voice (Info-Only) - plays audio and disconnects
    - Audio: 16bits 8000Hz Mono WAV only
    - Campaign Type: TRANSACTIONAL always
    - CSV Column: participantNumber (not Number)
    """
    try:
        secrets = _get_secrets()
        customer_id = secrets.get('customer_id')
        campaign_auth = secrets.get('campaign_auth')
        app_id = secrets.get('app_id', 'IRONMAN')
        call_flow_id = secrets.get('call_flow_id', 'dfbeda76-f641-420f-95e7-b78d562a941f')
        caller_id = secrets.get('caller_id', '8040761117')
        template_id = secrets.get('template_id', '69818654d9e8e260e60b16a7')
        
        if not customer_id or not campaign_auth:
            return _response(500, {'error': 'Airtel OBD credentials not configured'})
        
        campaign_name = body.get('campaignName', f'OBD_Campaign_{int(time.time())}')
        contacts = body.get('contacts', [])
        variables = body.get('variables', {})  # {phone: {var1: val1, var2: val2}}
        sheet_file_names = body.get('sheetFileNames', [])
        caller_id = body.get('callerId', caller_id)
        retry_count = body.get('retryCount', 2)
        
        # Always use default audio (Airtel only supports 16bits 8000Hz Mono WAV)
        audio_url = AIRTEL_DEFAULT_AUDIO_URL
        
        # Upload CSV if contacts provided (with participantNumber column)
        if contacts and not sheet_file_names:
            csv_result = _upload_csv_internal(contacts, variables, secrets, request_id)
            if not csv_result.get('success'):
                return _response(500, {'error': csv_result.get('error', 'Failed to upload contacts')})
            sheet_file_names = [csv_result.get('fileName')]
        
        if not sheet_file_names:
            return _response(400, {'error': 'contacts or sheetFileNames is required'})
        
        campaign_id = str(uuid.uuid4())
        
        # Build input variables for call flow
        input_variables = [
            {"name": "participantAddress", "value": "${participantNumber}", "type": "phoneNumber"},
            {"name": "callerId", "value": caller_id, "type": "phoneNumber"},
            {"name": "audioURL", "value": audio_url, "type": "string"}
        ]
        
        # Add custom variables if provided
        if variables:
            var_names = set()
            for phone_vars in variables.values():
                var_names.update(phone_vars.keys())
            for var_name in var_names:
                input_variables.append({
                    "name": var_name,
                    "value": f"${{{var_name}}}",
                    "type": "string"
                })
        
        payload = {
            "customerId": customer_id,
            "templateId": template_id,
            "campaignName": campaign_name,
            "sheetFileNames": sheet_file_names,
            "campaignData": {
                "customerId": customer_id,
                "messageType": "TRANSACTIONAL",  # Always TRANSACTIONAL for OBD
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
                        "inputVariables": input_variables,
                        "callBackURLs": [{"notifyURL": "queue", "eventType": "CALL"}]
                    }
                }
            },
            "inputCsvMappings": {"participantAddress": "participantNumber"},
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
        
        logger.info(json.dumps({
            'event': 'obd_create_campaign',
            'campaignName': campaign_name,
            'contactCount': len(contacts),
            'sheetFileNames': sheet_file_names,
            'requestId': request_id
        }))
        
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode('utf-8'))
            airtel_campaign_id = result.get('campaignId') or result.get('id')
            
            _store_campaign(campaign_id, campaign_name, airtel_campaign_id, sheet_file_names, audio_url, len(contacts))
            
            return _response(200, {
                'success': True,
                'campaignId': campaign_id,
                'airtelCampaignId': airtel_campaign_id,
                'campaignName': campaign_name,
                'contactCount': len(contacts),
                'status': 'created'
            })
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8') if e.fp else ''
        logger.error(f"Campaign create error: {e.code} - {error_body}")
        return _response(e.code, {'error': f'Airtel API error: {error_body[:200]}'})
    except Exception as e:
        logger.error(f"Campaign create error: {str(e)}")
        return _response(500, {'error': str(e)})


def _upload_csv_internal(contacts: List[str], variables: Dict, secrets: Dict, request_id: str) -> Dict[str, Any]:
    """Internal CSV upload helper with variable support."""
    try:
        customer_id = secrets.get('customer_id')
        auth_token = secrets.get('auth')
        app_id = secrets.get('app_id', 'IRONMAN')
        
        # Get variable names
        var_names = []
        if variables:
            for phone_vars in variables.values():
                var_names.extend(phone_vars.keys())
            var_names = list(set(var_names))
        
        # Build CSV with participantNumber column (Airtel requirement)
        if var_names:
            header = "participantNumber," + ",".join(var_names)
            rows = []
            for contact in contacts:
                clean_phone = _clean_phone(contact)
                if not clean_phone:
                    continue
                phone_vars = variables.get(contact, variables.get(clean_phone, {}))
                var_values = [str(phone_vars.get(v, '')) for v in var_names]
                rows.append(f"{clean_phone},{','.join(var_values)}")
            csv_content = header + "\n" + "\n".join(rows)
        else:
            csv_content = "participantNumber\n" + "\n".join([_clean_phone(c) for c in contacts if _clean_phone(c)])
        
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


def _store_campaign(campaign_id: str, name: str, airtel_id: str, sheets: List[str], audio_url: str, contact_count: int = 0) -> None:
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
            'contactCount': contact_count,
            'status': 'created',
            'createdAt': Decimal(str(now)),
            'updatedAt': Decimal(str(now)),
            'ttl': Decimal(str(now + (TTL_DAYS * 24 * 60 * 60)))
        })
    except Exception as e:
        logger.error(f"Store campaign error: {str(e)}")


def _delete_campaign(campaign_id: str, hard_delete: bool, request_id: str) -> Dict[str, Any]:
    """Delete a campaign (soft or hard delete)."""
    if not campaign_id:
        return _response(400, {'error': 'campaignId is required'})
    
    try:
        table = dynamodb.Table(OBD_CAMPAIGNS_TABLE)
        
        if hard_delete:
            # Hard delete - remove from DynamoDB
            table.delete_item(Key={'id': campaign_id})
            return _response(200, {'success': True, 'deleted': campaign_id, 'type': 'hard'})
        else:
            # Soft delete - mark as deleted
            now = int(time.time())
            table.update_item(
                Key={'id': campaign_id},
                UpdateExpression='SET #status = :status, deletedAt = :deletedAt, updatedAt = :updatedAt',
                ExpressionAttributeNames={'#status': 'status'},
                ExpressionAttributeValues={
                    ':status': 'DELETED',
                    ':deletedAt': Decimal(str(now)),
                    ':updatedAt': Decimal(str(now))
                }
            )
            return _response(200, {'success': True, 'deleted': campaign_id, 'type': 'soft'})
    except Exception as e:
        logger.error(f"Delete campaign error: {str(e)}")
        return _response(500, {'error': str(e)})


def _clear_logs(body: Dict, request_id: str) -> Dict[str, Any]:
    """Clear campaign logs (hard delete multiple campaigns)."""
    try:
        campaign_ids = body.get('campaignIds', [])
        clear_all = body.get('clearAll', False)
        
        table = dynamodb.Table(OBD_CAMPAIGNS_TABLE)
        deleted_count = 0
        
        if clear_all:
            # Scan and delete all campaigns
            result = table.scan(ProjectionExpression='id')
            for item in result.get('Items', []):
                table.delete_item(Key={'id': item['id']})
                deleted_count += 1
        elif campaign_ids:
            # Delete specific campaigns
            for cid in campaign_ids:
                try:
                    table.delete_item(Key={'id': cid})
                    deleted_count += 1
                except Exception:
                    pass
        else:
            return _response(400, {'error': 'campaignIds or clearAll is required'})
        
        return _response(200, {
            'success': True,
            'deletedCount': deleted_count,
            'message': f'Cleared {deleted_count} campaign logs'
        })
    except Exception as e:
        logger.error(f"Clear logs error: {str(e)}")
        return _response(500, {'error': str(e)})


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
            'Access-Control-Allow-Methods': 'GET,POST,DELETE,OPTIONS'
        },
        'body': json.dumps(body, default=str)
    }
