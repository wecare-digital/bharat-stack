"""
AWS SMS Lambda Function

Purpose: Send SMS messages via Amazon Pinpoint SMS (us-east-1 + ap-south-1 India)
Supports: Transactional SMS, Promotional SMS, Pinpoint SMS Template Management
Table: stack-wecare-digital-SmsAwsTable (dedicated)

Endpoints:
  GET  /sms-aws/messages          - List SMS messages
  GET  /sms-aws/messages/{id}     - Get single message
  POST /sms-aws/send              - Send SMS
  DELETE /sms-aws/messages/{id}   - Delete message
  DELETE /sms-aws/clear-logs      - Clear all logs
  GET  /sms-aws/templates         - List Pinpoint SMS templates (ap-south-1)
  POST /sms-aws/templates         - Create Pinpoint SMS template
  PUT  /sms-aws/templates         - Update Pinpoint SMS template
  DELETE /sms-aws/templates       - Delete Pinpoint SMS template
"""

import os
import json
import uuid
import time
import logging
import boto3
from typing import Dict, Any
from decimal import Decimal

from lambda_utils.logging import get_logger
from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin
from lambda_utils.validation import normalize_phone
from lambda_utils.message_store import put_message  # unified MessagesTable dual-write

logger = get_logger(__name__)

REGION = 'us-east-1'
INDIA_REGION = 'ap-south-1'
dynamodb = boto3.resource('dynamodb', region_name=REGION)
pinpoint_sms = boto3.client('pinpoint-sms-voice-v2', region_name=REGION)
# Pinpoint (classic) in ap-south-1 for India sender ID / template management
pinpoint_india = boto3.client('pinpoint', region_name=INDIA_REGION)

CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'stack-wecare-digital-ContactsTable')
SMS_TABLE = os.environ.get('SMS_AWS_TABLE', 'stack-wecare-digital-SmsAwsTable')
# Canonical unified table — reads/deletes now target this (channel=sms).
UNIFIED_TABLE = os.environ.get('UNIFIED_MESSAGES_TABLE', 'stack-wecare-digital-MessagesTable')
ORIGINATION_IDENTITY = os.environ.get('ORIGINATION_IDENTITY', '')
SENDER_ID = os.environ.get('SENDER_ID', 'WECARE')
INDIA_SENDER_ID = os.environ.get('INDIA_SENDER_ID', 'WDBEEP')
INDIA_PINPOINT_APP_ID = os.environ.get('INDIA_PINPOINT_APP_ID', '')
MESSAGE_TTL_SECONDS = 90 * 24 * 60 * 60  # 90 days

# --- India DLT (TRAI) -------------------------------------------------------
# Indian A2P SMS must carry the registered entity (PE) id and an APPROVED DLT
# template id, passed through SendTextMessage DestinationCountryParameters.
# These are NOT Pinpoint templates - do not create legacy Pinpoint templates
# to satisfy DLT.
#
# The message body must match the approved DLT template content exactly, or the
# operator rejects it downstream even though the API call succeeds.
INDIA_ENTITY_ID = os.environ.get('INDIA_DLT_ENTITY_ID', '1201161991108627443')

# template key -> approved DLT template id (mirrors the Airtel IQ mapping
# already used by sms-in/airtel, voice-in/c2c, voice-in/obd, whatsapp-calling)
INDIA_DLT_TEMPLATES = {
    'ivr-default': os.environ.get('IVR_SMS_DLT_TEMPLATE_ID', '1007277993798259629'),
    'wa-alert': os.environ.get('WA_ALERT_SMS_DLT_TEMPLATE_ID', '1007284579074821763'),
    'wd_order': os.environ.get('ORDER_SMS_DLT_TEMPLATE_ID', '1007723091207562020'),
}
# Callers that do not name a template fall back to this one.
INDIA_DEFAULT_DLT_TEMPLATE = os.environ.get('DEFAULT_DLT_TEMPLATE_KEY', 'ivr-default')


def _is_indian_msisdn(phone_e164: str) -> bool:
    """True for +91XXXXXXXXXX (12 digits including the 91 country code)."""
    digits = str(phone_e164 or '').lstrip('+')
    return digits.startswith('91') and len(digits) == 12


def _resolve_dlt_template(template_key: str) -> Dict[str, Any]:
    """Map a template key to an approved DLT template id.

    Returns {'templateId': str} on success, or {'error': str} when no approved
    mapping exists. Callers MUST NOT send to an Indian number without one -
    silently sending unregistered content risks operator blocking and DLT
    penalties, so this is a hard failure by design.
    """
    key = (template_key or INDIA_DEFAULT_DLT_TEMPLATE).strip()
    tid = INDIA_DLT_TEMPLATES.get(key)
    if not tid:
        return {'error': (
            f"No approved DLT template mapping for '{key}'. "
            f"Known keys: {', '.join(sorted(INDIA_DLT_TEMPLATES))}. "
            "Register the template on DLT and add it to INDIA_DLT_TEMPLATES "
            "before sending to Indian numbers."
        )}
    return {'templateId': tid, 'templateKey': key}


# Module-level origin for CORS (set per-invocation in handler)
origin = ''


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle AWS SMS operations."""
    request_id = context.aws_request_id if context else 'local'
    global origin
    origin = extract_origin(event)
    http_method = event.get('requestContext', {}).get('http', {}).get('method', 'POST')
    path = event.get('rawPath', event.get('path', ''))
    path_params = event.get('pathParameters') or {}
    query_params = event.get('queryStringParameters') or {}

    logger.info(json.dumps({
        'event': 'sms_aws_handler', 'method': http_method,
        'path': path, 'requestId': request_id
    }))

    try:
        if http_method == 'OPTIONS':
            return _response(200, {'message': 'OK'}, origin)

        # Pinpoint SMS Template management (ap-south-1 India)
        if '/templates' in path:
            if http_method == 'GET':
                return _list_pinpoint_templates(query_params, request_id)
            elif http_method == 'POST':
                body = json.loads(event.get('body', '{}'))
                return _create_pinpoint_template(body, request_id)
            elif http_method == 'PUT':
                body = json.loads(event.get('body', '{}'))
                return _update_pinpoint_template(body, request_id)
            elif http_method == 'DELETE':
                tpl_name = query_params.get('templateName') or path_params.get('templateName')
                return _delete_pinpoint_template(tpl_name, request_id)

        # DELETE /sms-aws/clear-logs
        if http_method == 'DELETE' and 'clear-logs' in path:
            return _clear_logs(request_id)

        # DELETE /sms-aws/messages/{id}
        if http_method == 'DELETE' and path_params.get('messageId'):
            return _delete_message(path_params['messageId'], request_id)

        # GET /sms-aws/messages/{id}
        if http_method == 'GET' and path_params.get('messageId'):
            return _get_message(path_params['messageId'], request_id)

        # GET /sms-aws/messages
        if http_method == 'GET':
            return _list_messages(query_params, request_id)

        # POST /sms-aws/send
        if http_method == 'POST':
            body = json.loads(event.get('body', '{}'))
            return _send_sms(body, request_id)

        return _response(405, {'error': 'Method not allowed'}, origin)

    except json.JSONDecodeError:
        return _response(400, {'error': 'Invalid JSON in request body'}, origin)
    except Exception as e:
        logger.error(f"SMS AWS error: {str(e)}", exc_info=True)
        return _response(500, {'error': 'Internal server error'}, origin)


def _list_messages(params: Dict, request_id: str) -> Dict[str, Any]:
    """List SMS messages from the canonical MessagesTable (channel=sms).
    Reads via channel-index (bounded Query, no scan). Response shape unchanged."""
    try:
        from boto3.dynamodb.conditions import Key
        table = dynamodb.Table(UNIFIED_TABLE)
        limit = int(params.get('limit', 200))
        resp = table.query(
            IndexName='channel-index',
            KeyConditionExpression=Key('channel').eq('sms'),
            ScanIndexForward=False,  # newest first
            Limit=max(limit, 200),
        )
        messages = resp.get('Items', [])
        # In-memory filters (SMS volume is small; keeps the query simple).
        cid = params.get('contactId')
        st = params.get('status')
        dirn = params.get('direction')
        if cid:
            messages = [m for m in messages if m.get('contactId') == cid]
        if st:
            messages = [m for m in messages if str(m.get('status', '')).lower() == st.lower()]
        if dirn:
            messages = [m for m in messages if str(m.get('direction', '')).lower() == dirn.lower()]
        messages.sort(key=lambda x: float(x.get('timestamp', x.get('createdAt', 0)) or 0), reverse=True)
        messages = messages[:limit]
        return _response(200, {
            'messages': [_normalize(m) for m in messages],
            'count': len(messages)
        })
    except Exception as e:
        logger.error(f"List messages error: {str(e)}")
        return _response(500, {'error': str(e)})


def _get_message(message_id: str, request_id: str) -> Dict[str, Any]:
    """Get a single SMS message from the canonical MessagesTable."""
    try:
        table = dynamodb.Table(UNIFIED_TABLE)
        result = table.get_item(Key={'id': message_id})
        item = result.get('Item')
        if item:
            return _response(200, {'message': _normalize(item)})
        return _response(404, {'error': 'Message not found'})
    except Exception as e:
        logger.error(f"Get message error: {str(e)}")
        return _response(500, {'error': str(e)})


def _delete_message(message_id: str, request_id: str) -> Dict[str, Any]:
    """Delete a single SMS message from the canonical table (and legacy, if present)."""
    try:
        dynamodb.Table(UNIFIED_TABLE).delete_item(Key={'id': message_id})
        # Best-effort legacy cleanup during the dual-write window.
        try:
            dynamodb.Table(SMS_TABLE).delete_item(Key={'id': message_id})
        except Exception:
            pass
        return _response(200, {'success': True, 'deleted': message_id})
    except Exception as e:
        logger.error(f"Delete message error: {str(e)}")
        return _response(500, {'error': str(e)})


def _clear_logs(request_id: str) -> Dict[str, Any]:
    """Clear SMS logs — deletes ONLY channel=sms rows from the canonical table
    (scoped via channel-index, so other channels are never touched)."""
    try:
        from boto3.dynamodb.conditions import Key
        table = dynamodb.Table(UNIFIED_TABLE)
        deleted = 0
        last_key = None
        while True:
            q = {
                'IndexName': 'channel-index',
                'KeyConditionExpression': Key('channel').eq('sms'),
                'ProjectionExpression': 'id',
            }
            if last_key:
                q['ExclusiveStartKey'] = last_key
            result = table.query(**q)
            items = result.get('Items', [])
            with table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(Key={'id': item['id']})
                    deleted += 1
            last_key = result.get('LastEvaluatedKey')
            if not last_key:
                break
        return _response(200, {'success': True, 'deletedCount': deleted})
    except Exception as e:
        logger.error(f"Clear logs error: {str(e)}")
        return _response(500, {'error': str(e)})


def _send_sms(body: Dict, request_id: str) -> Dict[str, Any]:
    """Send SMS via Amazon Pinpoint SMS v2."""
    contact_id = body.get('contactId', '')
    phone_number = body.get('phoneNumber') or body.get('phone')
    content = body.get('content', '')
    message_type = body.get('messageType', 'TRANSACTIONAL')
    campaign_id = body.get('campaignId', '')
    campaign_name = body.get('campaignName', '')
    target_region = body.get('region', '')  # Optional: 'ap-south-1' for India fallback

    # Normalize phone input to consistent digits-only format
    if phone_number:
        normalized = normalize_phone(phone_number)
        if normalized:
            phone_number = f'+{normalized}'

    if not phone_number and contact_id:
        contact = _get_contact(contact_id)
        phone_number = contact.get('phone') if contact else None

    if not phone_number:
        return _response(400, {'error': 'phoneNumber is required'})
    if not content:
        return _response(400, {'error': 'content is required'})

    phone_e164 = _format_e164(phone_number)
    if not phone_e164:
        return _response(400, {'error': 'Invalid phone number format'})

    message_id = str(uuid.uuid4())

    # Route by destination country, not by caller opt-in.
    # Previously this block detected an Indian number and then did nothing
    # (literally `pass`), so +91 traffic went out via us-east-1 with no DLT
    # parameters. Indian A2P requires ap-south-1 + WDBEEP + entity/template ids.
    use_india_region = _is_indian_msisdn(phone_e164) or target_region == 'ap-south-1'

    dlt: Dict[str, Any] = {}
    if use_india_region:
        dlt = _resolve_dlt_template(body.get('dltTemplateKey') or body.get('templateKey'))
        if dlt.get('error'):
            # Fail loudly rather than send unregistered content to an Indian number.
            logger.error(json.dumps({
                'event': 'sms_missing_dlt_template',
                'phone': phone_e164[-4:],
                'requestedKey': body.get('dltTemplateKey') or body.get('templateKey') or '(none)',
                'requestId': request_id,
            }))
            return _response(422, {
                'error': 'MISSING_DLT_TEMPLATE',
                'detail': dlt['error'],
                'destination': 'IN',
            })

    # Send via Pinpoint SMS v2
    result = _send_pinpoint_sms(phone_e164, content, message_type, request_id,
                                use_india_region=use_india_region,
                                dlt_template_id=dlt.get('templateId'))

    now = int(time.time())
    _store_message({
        'id': message_id,
        'messageId': message_id,
        'contactId': contact_id,
        'phoneNumber': phone_e164,
        'content': content,
        'direction': 'OUTBOUND',
        'status': 'SENT' if result.get('success') else 'FAILED',
        'messageType': message_type,
        'senderId': SENDER_ID,
        'providerMessageId': result.get('providerMessageId', ''),
        'campaignId': campaign_id,
        'campaignName': campaign_name,
        'errorDetails': result.get('error', ''),
        'createdAt': Decimal(str(now)),
        'expiresAt': Decimal(str(now + MESSAGE_TTL_SECONDS)),
    })

    if not result.get('success'):
        return _response(500, {
            'error': result.get('error', 'Failed to send SMS'),
            'messageId': message_id
        })

    return _response(200, {
        'success': True,
        'messageId': message_id,
        'status': 'sent',
        'providerMessageId': result.get('providerMessageId')
    })


def _send_pinpoint_sms(phone: str, content: str, message_type: str,
                       request_id: str, use_india_region: bool = False,
                       dlt_template_id: str = None,
                       dry_run: bool = False) -> Dict[str, Any]:
    """Send SMS via Pinpoint SMS Voice v2 API.

    Routing is by destination country:
    - ap-south-1 for +91: OriginationIdentity=WDBEEP (registered sender id) plus
      DestinationCountryParameters IN_ENTITY_ID / IN_TEMPLATE_ID, which TRAI DLT
      requires. Without these the operator rejects the message.
    - us-east-1 for everything else: existing international/toll-free origination
      identity, and NO Indian DLT fields (they are invalid outside India).
    """
    try:
        if use_india_region:
            # Use ap-south-1 Pinpoint SMS v2 client for India
            india_sms_client = boto3.client('pinpoint-sms-voice-v2', region_name=INDIA_REGION)
            params: Dict[str, Any] = {
                'DestinationPhoneNumber': phone,
                'MessageBody': content,
                'MessageType': message_type,
            }
            # Use India sender ID if available
            if INDIA_SENDER_ID:
                params['OriginationIdentity'] = INDIA_SENDER_ID

            # --- TRAI DLT: mandatory for Indian A2P traffic ---
            country_params: Dict[str, str] = {}
            if INDIA_ENTITY_ID:
                country_params['IN_ENTITY_ID'] = INDIA_ENTITY_ID
            if dlt_template_id:
                country_params['IN_TEMPLATE_ID'] = dlt_template_id
            if country_params:
                params['DestinationCountryParameters'] = country_params

            if dry_run:
                params['DryRun'] = True

            response = india_sms_client.send_text_message(**params)
            logger.info(json.dumps({
                'event': 'pinpoint_india_sms_sent',
                'phone': phone[-4:],
                'region': INDIA_REGION,
                'senderId': INDIA_SENDER_ID,
                'dltEntityId': INDIA_ENTITY_ID,
                'dltTemplateId': dlt_template_id or '',
                'dryRun': dry_run,
                'messageId': response.get('MessageId', ''),
                'requestId': request_id,
            }))
            return {
                'success': True,
                'providerMessageId': response.get('MessageId', ''),
                'region': INDIA_REGION,
                'dltTemplateId': dlt_template_id or '',
            }
        else:
            params: Dict[str, Any] = {
                'DestinationPhoneNumber': phone,
                'MessageBody': content,
                'MessageType': message_type,
            }

            # Only set origination identity if it's an SMS-capable resource
            if ORIGINATION_IDENTITY:
                params['OriginationIdentity'] = ORIGINATION_IDENTITY

            response = pinpoint_sms.send_text_message(**params)

            return {
                'success': True,
                'providerMessageId': response.get('MessageId', '')
            }

    except pinpoint_sms.exceptions.ConflictException as e:
        logger.error(f"Pinpoint conflict: {str(e)}")
        return {'success': False, 'error': f'Conflict: {str(e)}'}
    except pinpoint_sms.exceptions.ValidationException as e:
        logger.error(f"Pinpoint validation: {str(e)}")
        return {'success': False, 'error': f'Validation: {str(e)}'}
    except pinpoint_sms.exceptions.ThrottlingException as e:
        logger.error(f"Pinpoint throttled: {str(e)}")
        return {'success': False, 'error': 'Rate limited, try again'}
    except Exception as e:
        logger.error(f"Pinpoint SMS error ({INDIA_REGION if use_india_region else REGION}): {str(e)}")
        return {'success': False, 'error': str(e)}


def _format_e164(phone: str) -> str:
    """Format phone number to E.164."""
    if not phone:
        return ''
    digits = ''.join(c for c in str(phone) if c.isdigit())
    if len(digits) == 10:
        return f'+91{digits}'  # India default
    if len(digits) >= 11 and not phone.startswith('+'):
        return f'+{digits}'
    if phone.startswith('+'):
        return phone
    return f'+{digits}' if digits else ''


def _get_contact(contact_id: str) -> Dict[str, Any]:
    """Get contact from DynamoDB."""
    try:
        table = dynamodb.Table(CONTACTS_TABLE)
        response = table.get_item(Key={'id': contact_id})
        return response.get('Item', {})
    except Exception as e:
        logger.error(f"Get contact error: {str(e)}")
        return {}


def _store_message(item: Dict) -> None:
    """Store SMS message in the canonical MessagesTable only.

    Phase 4: legacy SmsAwsTable dual-write STOPPED — canonical is now the sole store
    (all readers already query canonical). SmsAwsTable is retained read-only during the
    soak, then deleted.
    """
    # Ensure 'id' is present for the canonical messageId.
    if 'id' not in item and 'messageId' in item:
        item['id'] = item['messageId']

    # Canonical write (single source of truth for the unified inbox).
    direction = str(item.get('direction', 'OUTBOUND')).lower()
    phone = item.get('phoneNumber', '')
    put_message(
        channel='sms',
        direction=direction if direction in ('inbound', 'outbound') else 'outbound',
        contact_id=item.get('contactId', ''),
        content=item.get('content', ''),
        status=item.get('status', 'sent'),
        message_id=item.get('messageId') or item.get('id'),
        message_type=item.get('messageType') or 'text',
        provider_message_id=item.get('providerMessageId') or None,
        error_details=item.get('errorDetails') or None,
        sender_phone=phone if direction == 'inbound' else None,
        receiving_phone=phone if direction != 'inbound' else None,
    )


def _normalize(item: Dict) -> Dict:
    """Normalize message for API response. Maps canonical fields (receivingPhone/
    senderPhone, timestamp) back to the SMS page's expected shape."""
    ts = item.get('timestamp', item.get('createdAt', 0))
    return {
        'id': item.get('id', item.get('messageId', '')),
        'messageId': item.get('messageId', item.get('id', '')),
        'contactId': item.get('contactId', ''),
        'phoneNumber': item.get('phoneNumber') or item.get('receivingPhone') or item.get('senderPhone') or '',
        'content': item.get('content', ''),
        'direction': str(item.get('direction', 'OUTBOUND')).upper(),
        'status': item.get('status', ''),
        'messageType': item.get('messageType', ''),
        'senderId': item.get('senderId', ''),
        'providerMessageId': item.get('providerMessageId', ''),
        'campaignId': item.get('campaignId', ''),
        'campaignName': item.get('campaignName', ''),
        'channel': 'SMS',
        'provider': 'aws',
        'timestamp': int(float(ts or 0)),
        'createdAt': int(float(item.get('createdAt', ts or 0) or 0)),
    }


def _response(status_code: int, body: Dict, resp_origin: str = '') -> Dict[str, Any]:
    """Return HTTP response with CORS headers."""
    return {
        'statusCode': status_code,
        'headers': cors_headers(resp_origin or origin),
        'body': json.dumps(body, default=str)
    }


# ─── Pinpoint SMS Template Management (ap-south-1 India) ───

def _list_pinpoint_templates(params: Dict, request_id: str) -> Dict[str, Any]:
    """List SMS templates from Pinpoint (ap-south-1)."""
    try:
        # Use Pinpoint list-templates API
        kwargs = {'TemplateType': 'SMS'}
        if params.get('pageSize'):
            kwargs['PageSize'] = params['pageSize']
        response = pinpoint_india.list_templates(**kwargs)
        templates_meta = response.get('TemplatesResponse', {}).get('Item', [])

        templates = []
        for meta in templates_meta:
            if meta.get('TemplateType') != 'SMS':
                continue
            try:
                detail = pinpoint_india.get_sms_template(TemplateName=meta['TemplateName'])
                tpl = detail.get('SMSTemplateResponse', {})
                templates.append({
                    'templateName': tpl.get('TemplateName', ''),
                    'body': tpl.get('Body', ''),
                    'defaultSubstitutions': tpl.get('DefaultSubstitutions', ''),
                    'recommenderId': tpl.get('RecommenderId', ''),
                    'templateDescription': tpl.get('TemplateDescription', ''),
                    'version': tpl.get('Version', ''),
                    'creationDate': tpl.get('CreationDate', ''),
                    'lastModifiedDate': tpl.get('LastModifiedDate', ''),
                    'tags': tpl.get('tags', {}),
                })
            except Exception as e:
                logger.warning(f"Failed to get template {meta.get('TemplateName')}: {e}")
                templates.append({
                    'templateName': meta.get('TemplateName', ''),
                    'body': '',
                    'templateDescription': meta.get('Description', ''),
                    'version': meta.get('Version', ''),
                    'creationDate': meta.get('CreationDate', ''),
                    'lastModifiedDate': meta.get('LastModifiedDate', ''),
                })

        return _response(200, {
            'templates': templates,
            'count': len(templates),
            'region': INDIA_REGION,
        })
    except Exception as e:
        logger.error(f"List Pinpoint templates error: {str(e)}")
        return _response(500, {'error': str(e)})


def _create_pinpoint_template(body: Dict, request_id: str) -> Dict[str, Any]:
    """Create an SMS template in Pinpoint (ap-south-1)."""
    template_name = body.get('templateName', '')
    template_body = body.get('body', '')
    description = body.get('templateDescription', '')

    if not template_name:
        return _response(400, {'error': 'templateName is required'})
    if not template_body:
        return _response(400, {'error': 'body is required'})

    try:
        request_payload = {
            'Body': template_body,
        }
        if description:
            request_payload['TemplateDescription'] = description
        if body.get('defaultSubstitutions'):
            request_payload['DefaultSubstitutions'] = body['defaultSubstitutions']
        if body.get('tags'):
            request_payload['tags'] = body['tags']

        response = pinpoint_india.create_sms_template(
            TemplateName=template_name,
            SMSTemplateRequest=request_payload
        )
        result = response.get('CreateTemplateMessageBody', {})

        return _response(200, {
            'success': True,
            'templateName': template_name,
            'arn': result.get('Arn', ''),
            'requestId': result.get('RequestID', ''),
            'message': result.get('Message', 'Template created'),
        })
    except pinpoint_india.exceptions.BadRequestException as e:
        return _response(400, {'error': f'Bad request: {str(e)}'})
    except Exception as e:
        logger.error(f"Create Pinpoint template error: {str(e)}")
        return _response(500, {'error': str(e)})


def _update_pinpoint_template(body: Dict, request_id: str) -> Dict[str, Any]:
    """Update an SMS template in Pinpoint (ap-south-1)."""
    template_name = body.get('templateName', '')
    template_body = body.get('body', '')

    if not template_name:
        return _response(400, {'error': 'templateName is required'})

    try:
        request_payload = {}
        if template_body:
            request_payload['Body'] = template_body
        if body.get('templateDescription') is not None:
            request_payload['TemplateDescription'] = body['templateDescription']
        if body.get('defaultSubstitutions'):
            request_payload['DefaultSubstitutions'] = body['defaultSubstitutions']
        if body.get('tags'):
            request_payload['tags'] = body['tags']

        kwargs = {
            'TemplateName': template_name,
            'SMSTemplateRequest': request_payload,
            'CreateNewVersion': True,
        }
        if body.get('version'):
            kwargs['Version'] = body['version']

        response = pinpoint_india.update_sms_template(**kwargs)
        result = response.get('MessageBody', {})

        return _response(200, {
            'success': True,
            'templateName': template_name,
            'message': result.get('Message', 'Template updated'),
            'requestId': result.get('RequestID', ''),
        })
    except Exception as e:
        logger.error(f"Update Pinpoint template error: {str(e)}")
        return _response(500, {'error': str(e)})


def _delete_pinpoint_template(template_name: str, request_id: str) -> Dict[str, Any]:
    """Delete an SMS template from Pinpoint (ap-south-1)."""
    if not template_name:
        return _response(400, {'error': 'templateName is required'})

    try:
        response = pinpoint_india.delete_sms_template(TemplateName=template_name)
        result = response.get('MessageBody', {})
        return _response(200, {
            'success': True,
            'deleted': template_name,
            'message': result.get('Message', 'Template deleted'),
        })
    except Exception as e:
        logger.error(f"Delete Pinpoint template error: {str(e)}")
        return _response(500, {'error': str(e)})
