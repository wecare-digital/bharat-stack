"""
Inbound WhatsApp Handler — Reference Implementation
Triggered by SNS subscription from AWS EUM Social event destination.

Flow: WhatsApp → Meta → AWS EUM Social → SNS → this Lambda → DynamoDB + S3

Handles:
  - 22 inbound message types (text, image, video, audio, document, sticker,
    location, contacts, reaction, interactive, button, order, system,
    unsupported, request_welcome, ephemeral, referral, ad_click,
    product, product_inquiry, poll, unknown)
  - Delivery/read statuses (sent, delivered, read, failed)
  - Payment statuses (pending, captured, failed)
  - Template status updates (APPROVED, REJECTED, PAUSED, DISABLED)
  - Phone number quality updates (GREEN, YELLOW, RED)
  - Account updates (messaging limits, restrictions)

NO direct Meta Graph API calls — all WhatsApp communication via boto3 socialmessaging.
"""

import os
import json
import uuid
import time
import logging
import boto3
from typing import Dict, Any, Optional
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
sqs = boto3.client('sqs', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
social_messaging = boto3.client('socialmessaging', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
lambda_client = boto3.client('lambda', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Environment
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'base-wecare-digital-ContactsTable')
MESSAGES_TABLE = os.environ.get('MESSAGES_TABLE', 'base-wecare-digital-WhatsAppInboundTable')
MEDIA_FILES_TABLE = os.environ.get('MEDIA_FILES_TABLE', 'base-wecare-digital-MediaFilesTable')
IDEMPOTENCY_TABLE = os.environ.get('IDEMPOTENCY_TABLE', 'base-wecare-digital-IdempotencyTable')
INBOUND_DLQ_URL = os.environ.get('INBOUND_DLQ_URL', '')
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')
MEDIA_PREFIX = os.environ.get('MEDIA_INBOUND_PREFIX', 'whatsapp-media/whatsapp-media-incoming/')
OUTBOUND_FUNCTION = os.environ.get('OUTBOUND_WHATSAPP_FUNCTION', 'wecare-outbound-whatsapp')
SEND_MODE = os.environ.get('SEND_MODE', 'LIVE')

PHONE_NUMBER_ID_1 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_1',
                                    'phone-number-id-5e020cecd221429996f6ae721cc42206')
PHONE_NUMBER_ID_2 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_2',
                                    'phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c')
PHONE_MAP = {
    '919330994400': PHONE_NUMBER_ID_1,
    '919903300044': PHONE_NUMBER_ID_2,
}

MESSAGE_TTL = 30 * 24 * 60 * 60  # 30 days
IDEMPOTENCY_TTL = 30 * 24 * 60 * 60

META_API_VERSION = os.environ.get('META_API_VERSION', 'v20.0')


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process inbound WhatsApp messages from SNS."""
    request_id = context.aws_request_id if context else 'local'
    processed = errors = 0

    logger.info(json.dumps({
        'event': 'inbound_start',
        'records': len(event.get('Records', [])),
        'requestId': request_id,
    }))

    for record in event.get('Records', []):
        try:
            sns_msg = json.loads(record.get('Sns', {}).get('Message', '{}'))
            ctx = sns_msg.get('context', {})
            meta_waba_ids = ctx.get('MetaWabaIds', [])
            webhook_entry = json.loads(sns_msg.get('whatsAppWebhookEntry', '{}'))

            for change in webhook_entry.get('changes', []):
                value = change.get('value', {})
                metadata = value.get('metadata', {})
                display_phone = metadata.get('display_phone_number', '')
                aws_phone_id = _resolve_phone_id(display_phone)

                # Build contacts map (wa_id → profile name)
                contacts_map = {}
                for c in value.get('contacts', []):
                    wa_id = c.get('wa_id', '')
                    if wa_id:
                        contacts_map[wa_id] = c.get('profile', {}).get('name', '')

                # --- Messages ---
                for msg in value.get('messages', []):
                    try:
                        _process_message(msg, metadata, aws_phone_id,
                                         meta_waba_ids, contacts_map, request_id)
                        processed += 1
                    except Exception as e:
                        logger.error(json.dumps({
                            'event': 'msg_error', 'id': msg.get('id'),
                            'error': str(e), 'requestId': request_id}))
                        errors += 1

                # --- Statuses ---
                for status in value.get('statuses', []):
                    try:
                        _process_status(status, request_id)
                    except Exception as e:
                        logger.error(json.dumps({
                            'event': 'status_error', 'error': str(e),
                            'requestId': request_id}))

                # --- Non-message webhook fields ---
                field = change.get('field', '')
                if field == 'message_template_status_update':
                    _process_template_status(value, request_id)
                elif field == 'phone_number_quality_update':
                    _process_phone_quality(value, request_id)
                elif field == 'account_update':
                    _process_account_update(value, request_id)

        except Exception as e:
            logger.error(json.dumps({
                'event': 'record_error', 'error': str(e),
                'requestId': request_id}))
            _send_to_dlq(record, str(e), request_id)
            errors += 1

    logger.info(json.dumps({
        'event': 'inbound_done', 'processed': processed,
        'errors': errors, 'requestId': request_id}))
    return {'statusCode': 200, 'body': json.dumps({'processed': processed, 'errors': errors})}


# ---------------------------------------------------------------------------
# MESSAGE PROCESSING
# ---------------------------------------------------------------------------

def _process_message(msg, metadata, aws_phone_id, meta_waba_ids, contacts_map, request_id):
    wa_msg_id = msg.get('id', '')
    sender = msg.get('from', '')
    msg_type = msg.get('type', 'text')
    ts = int(msg.get('timestamp', time.time()))
    sender_name = contacts_map.get(sender, '')

    # Idempotency
    if _is_duplicate(wa_msg_id):
        logger.info(json.dumps({'event': 'dedup_skip', 'id': wa_msg_id}))
        return

    # Contact upsert
    contact_id = _upsert_contact(sender, sender_name)

    # Content extraction
    content = _extract_content(msg, msg_type)

    # Media download
    s3_key = media_file_id = None
    if msg_type in ('image', 'video', 'audio', 'document', 'sticker'):
        media_data = msg.get(msg_type, {})
        wa_media_id = media_data.get('id')
        if wa_media_id:
            s3_key = _download_media(wa_media_id, aws_phone_id, request_id,
                                     media_data.get('mime_type', ''))
            if s3_key:
                media_file_id = _store_media_ref(wa_msg_id, s3_key, media_data, wa_media_id)

    # Persist
    message_id = str(uuid.uuid4())
    now = int(time.time())
    item = {
        'id': message_id,
        'contactId': contact_id,
        'channel': 'whatsapp',
        'direction': 'inbound',
        'content': content,
        'messageType': msg_type,
        'timestamp': Decimal(str(ts)),
        'status': 'received',
        'whatsappMessageId': wa_msg_id,
        'senderPhone': sender,
        'senderName': sender_name,
        'receivingPhone': metadata.get('display_phone_number', ''),
        'awsPhoneNumberId': aws_phone_id,
        'metaWabaIds': meta_waba_ids or None,
        'createdAt': Decimal(str(now)),
        'expiresAt': Decimal(str(now + MESSAGE_TTL)),
    }
    if s3_key:
        item['s3Key'] = s3_key
    if media_file_id:
        item['mediaId'] = media_file_id
    dynamodb.Table(MESSAGES_TABLE).put_item(
        Item={k: v for k, v in item.items() if v is not None})

    _mark_processed(wa_msg_id)
    _update_contact_ts(contact_id, now)

    logger.info(json.dumps({
        'event': 'msg_stored', 'id': message_id, 'type': msg_type,
        'sender': sender, 'phone': aws_phone_id,
        'content': content[:120] if content else '',
        'requestId': request_id}))

    # Auto-react + read receipt (skip for reactions to avoid loops)
    if msg_type != 'reaction' and SEND_MODE == 'LIVE':
        _send_auto_reaction(wa_msg_id, sender, aws_phone_id, request_id)
        _send_read_receipt(wa_msg_id, sender, aws_phone_id, request_id)


# ---------------------------------------------------------------------------
# CONTENT EXTRACTION — 18 message types
# ---------------------------------------------------------------------------

def _extract_content(msg: Dict, msg_type: str) -> str:
    if msg_type == 'text':
        return msg.get('text', {}).get('body', '')
    if msg_type == 'image':
        return msg.get('image', {}).get('caption', '[Image]')
    if msg_type == 'video':
        return msg.get('video', {}).get('caption', '[Video]')
    if msg_type == 'audio':
        return '[Audio]'
    if msg_type == 'document':
        return msg.get('document', {}).get('filename', '[Document]')
    if msg_type == 'sticker':
        return '[Sticker]'
    if msg_type == 'location':
        loc = msg.get('location', {})
        return f"[Location: {loc.get('latitude')}, {loc.get('longitude')}]"
    if msg_type == 'contacts':
        return '[Contact Card]'
    if msg_type == 'reaction':
        return msg.get('reaction', {}).get('emoji', '')
    if msg_type == 'interactive':
        inter = msg.get('interactive', {})
        itype = inter.get('type', '')
        if itype == 'button_reply':
            return inter.get('button_reply', {}).get('title', '[Button Reply]')
        if itype == 'list_reply':
            return inter.get('list_reply', {}).get('title', '[List Reply]')
        if itype == 'nfm_reply':
            rj = inter.get('nfm_reply', {}).get('response_json', '')
            return f'[Flow: {rj[:80]}]' if rj else '[Flow Response]'
        return f'[Interactive: {itype}]'
    if msg_type == 'button':
        return msg.get('button', {}).get('text', '[Button]')
    if msg_type == 'order':
        return '[Order]'
    if msg_type == 'system':
        return msg.get('system', {}).get('body', '[System Message]')
    if msg_type == 'unsupported':
        errs = msg.get('errors', [])
        if errs:
            detail = errs[0].get('details') or errs[0].get('title', '')
            return f'[Unsupported: {detail}]' if detail else '[Unsupported message]'
        return '[Unsupported message]'
    if msg_type == 'request_welcome':
        return '[User requested to start conversation]'
    if msg_type == 'ephemeral':
        return '[Disappearing Message]'
    if msg_type == 'referral':
        ref = msg.get('referral', {})
        source = ref.get('source_type', 'unknown')
        headline = ref.get('headline', '')
        return f'[Referral: {source}] {headline}'.strip() if headline else f'[Referral: {source}]'
    if msg_type == 'ad_click':
        ref = msg.get('referral', {})
        return f'[Ad Click: {ref.get("source_url", "")}]' if ref.get('source_url') else '[Ad Click]'
    if msg_type in ('product', 'product_inquiry'):
        prod = msg.get(msg_type, msg.get('product', {}))
        catalog_id = prod.get('catalog_id', '')
        product_id = prod.get('product_retailer_id', '')
        return f'[Product: {catalog_id}/{product_id}]' if catalog_id else f'[{msg_type.replace("_", " ").title()}]'
    if msg_type == 'poll':
        poll = msg.get('poll', {})
        question = poll.get('question', '')
        return f'[Poll: {question[:60]}]' if question else '[Poll]'
    return f'[{msg_type}]'


# ---------------------------------------------------------------------------
# STATUS PROCESSING
# ---------------------------------------------------------------------------

def _process_status(status: Dict, request_id: str):
    """Update outbound message status (sent/delivered/read/failed) or payment."""
    wa_msg_id = status.get('id', '')
    new_status = status.get('status', '')
    recipient = status.get('recipient_id', '')
    ts = int(status.get('timestamp', time.time()))

    # Payment status
    if status.get('type') == 'payment':
        _process_payment_status(status, request_id)
        return

    logger.info(json.dumps({
        'event': 'status_update', 'waId': wa_msg_id,
        'status': new_status, 'recipient': recipient,
        'requestId': request_id}))

    # Find and update the outbound message record
    table = dynamodb.Table(MESSAGES_TABLE)
    try:
        resp = table.query(
            IndexName='whatsappMessageId-index',
            KeyConditionExpression='whatsappMessageId = :wid',
            ExpressionAttributeValues={':wid': wa_msg_id},
            Limit=1)
        items = resp.get('Items', [])
        if items:
            table.update_item(
                Key={'id': items[0]['id']},
                UpdateExpression='SET #s = :s, statusUpdatedAt = :ts',
                ExpressionAttributeNames={'#s': 'status'},
                ExpressionAttributeValues={':s': new_status, ':ts': Decimal(str(ts))})
        else:
            logger.warning(json.dumps({
                'event': 'status_no_match', 'waId': wa_msg_id,
                'status': new_status, 'recipient': recipient,
                'requestId': request_id}))
    except Exception as e:
        logger.warning(f"Status update failed for {wa_msg_id}: {e}")


def _process_payment_status(status: Dict, request_id: str):
    payment = status.get('payment', {})
    ref_id = payment.get('reference_id', '')
    pay_status = status.get('status', '')  # pending/captured/failed
    amount_obj = payment.get('amount', {})
    amount = amount_obj.get('value', 0) / max(amount_obj.get('offset', 100), 1)
    currency = payment.get('currency', 'INR')
    recipient = status.get('recipient_id', '')

    logger.info(json.dumps({
        'event': 'payment_status', 'refId': ref_id,
        'status': pay_status, 'amount': amount,
        'currency': currency, 'recipient': recipient,
        'requestId': request_id}))

    # Store payment event
    now = int(time.time())
    dynamodb.Table(MESSAGES_TABLE).put_item(Item={
        'id': str(uuid.uuid4()),
        'messageType': 'payment',
        'content': f'Payment {pay_status}: {currency} {amount}',
        'paymentStatus': pay_status,
        'referenceId': ref_id,
        'recipientId': recipient,
        'amount': Decimal(str(amount)),
        'currency': currency,
        'timestamp': Decimal(str(now)),
        'expiresAt': Decimal(str(now + MESSAGE_TTL)),
        'direction': 'inbound',
        'channel': 'whatsapp',
        'status': 'received',
    })


def _process_template_status(value: Dict, request_id: str):
    logger.info(json.dumps({
        'event': 'template_status',
        'name': value.get('message_template_name', ''),
        'status': value.get('event', ''),
        'requestId': request_id}))


def _process_phone_quality(value: Dict, request_id: str):
    logger.info(json.dumps({
        'event': 'phone_quality',
        'data': value,
        'requestId': request_id}))


def _process_account_update(value: Dict, request_id: str):
    logger.info(json.dumps({
        'event': 'account_update',
        'data': value,
        'requestId': request_id}))


# ---------------------------------------------------------------------------
# HELPERS — Phone mapping, contacts, media, idempotency, DLQ, reactions
# ---------------------------------------------------------------------------

def _resolve_phone_id(display_phone: str) -> str:
    clean = display_phone.replace('+', '').replace(' ', '').replace('-', '')
    return PHONE_MAP.get(clean, PHONE_NUMBER_ID_1)


def _is_duplicate(wa_msg_id: str) -> bool:
    if not wa_msg_id:
        return False
    try:
        resp = dynamodb.Table(IDEMPOTENCY_TABLE).get_item(Key={'eventId': wa_msg_id})
        return 'Item' in resp
    except Exception:
        return False


def _mark_processed(wa_msg_id: str):
    try:
        now = int(time.time())
        dynamodb.Table(IDEMPOTENCY_TABLE).put_item(Item={
            'eventId': wa_msg_id,
            'processedAt': now,
            'expiresAt': now + IDEMPOTENCY_TTL,
        })
    except Exception as e:
        logger.warning(f"Idempotency mark failed: {e}")


def _upsert_contact(phone: str, name: str = '') -> str:
    table = dynamodb.Table(CONTACTS_TABLE)
    clean = phone.lstrip('+')
    variants = [f'+{clean}', clean]
    items = []
    for v in variants:
        try:
            resp = table.query(
                IndexName='phone-index',
                KeyConditionExpression='phone = :p',
                ExpressionAttributeValues={':p': v}, Limit=5)
            items.extend([i for i in resp.get('Items', []) if not i.get('deletedAt')])
        except Exception:
            pass

    if items:
        contact = sorted(items, key=lambda x: x.get('createdAt', 0))[0]
        cid = contact['id']
        if name and not contact.get('name'):
            try:
                table.update_item(
                    Key={'id': cid},
                    UpdateExpression='SET #n = :n, updatedAt = :t',
                    ExpressionAttributeNames={'#n': 'name'},
                    ExpressionAttributeValues={':n': name, ':t': Decimal(str(int(time.time())))})
            except Exception:
                pass
        return cid

    cid = str(uuid.uuid4())
    now = int(time.time())
    table.put_item(Item={
        'id': cid, 'contactId': cid,
        'name': name or '', 'phone': f'+{clean}',
        'optInWhatsApp': True,
        'lastInboundMessageAt': Decimal(str(now)),
        'createdAt': Decimal(str(now)),
        'updatedAt': Decimal(str(now)),
    })
    logger.info(json.dumps({'event': 'contact_created', 'id': cid, 'phone': phone}))
    return cid


def _update_contact_ts(contact_id: str, ts: int):
    try:
        dynamodb.Table(CONTACTS_TABLE).update_item(
            Key={'id': contact_id},
            UpdateExpression='SET lastInboundMessageAt = :t, updatedAt = :t',
            ExpressionAttributeValues={':t': Decimal(str(ts))})
    except Exception as e:
        logger.warning(f"Contact ts update failed: {e}")


def _download_media(wa_media_id: str, phone_id: str, request_id: str,
                    mime_hint: str = '') -> Optional[str]:
    """Download media from WhatsApp to S3 via AWS EUM Social API."""
    try:
        prefix = f"{MEDIA_PREFIX}{wa_media_id[:12]}/"
        social_messaging.get_whatsapp_message_media(
            mediaId=wa_media_id,
            originationPhoneNumberId=phone_id,
            destinationS3File={'bucketName': MEDIA_BUCKET, 'key': prefix})

        # Find actual file AWS created
        try:
            resp = s3.list_objects_v2(Bucket=MEDIA_BUCKET, Prefix=prefix, MaxKeys=5)
            files = [c for c in resp.get('Contents', []) if c.get('Size', 0) > 0]
            if files:
                return files[0]['Key']
        except Exception:
            pass

        # Fallback: construct key
        ext = _ext_from_mime(mime_hint) if mime_hint else '.bin'
        return f"{prefix}{wa_media_id}{ext}"
    except Exception as e:
        logger.error(json.dumps({
            'event': 'media_dl_error', 'mediaId': wa_media_id,
            'error': str(e), 'requestId': request_id}))
        return None


def _ext_from_mime(mime: str) -> str:
    m = {
        'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp',
        'video/mp4': '.mp4', 'video/3gpp': '.3gp',
        'audio/aac': '.aac', 'audio/amr': '.amr', 'audio/mpeg': '.mp3',
        'audio/mp4': '.m4a', 'audio/ogg': '.ogg',
        'application/pdf': '.pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
    }
    return m.get(mime, '.bin')


def _store_media_ref(msg_id: str, s3_key: str, media_data: Dict, wa_media_id: str) -> str:
    fid = str(uuid.uuid4())
    try:
        dynamodb.Table(MEDIA_FILES_TABLE).put_item(Item={
            'fileId': fid,
            'messageId': msg_id,
            's3Key': s3_key,
            'contentType': media_data.get('mime_type', ''),
            'whatsappMediaId': wa_media_id,
            'fileSize': media_data.get('file_size', 0) or 0,
            'createdAt': int(time.time()),
        })
    except Exception as e:
        logger.warning(f"Media ref store failed: {e}")
    return fid


def _send_auto_reaction(wa_msg_id: str, recipient: str, phone_id: str, request_id: str):
    """Send thumbs-up reaction to acknowledge receipt.
    
    NOTE: Calls social_messaging directly (not via shared/social_client.py)
    because auto-reactions are fire-and-forget — retry/backoff is unnecessary
    and would add latency to inbound processing.
    """
    try:
        clean = recipient.lstrip('+')
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': f'+{clean}',
            'type': 'reaction',
            'reaction': {'message_id': wa_msg_id, 'emoji': '\U0001F44D'}
        }
        social_messaging.send_whatsapp_message(
            originationPhoneNumberId=phone_id,
            message=json.dumps(payload).encode('utf-8'),
            metaApiVersion=META_API_VERSION)
        logger.debug(json.dumps({
            'event': 'auto_react_sent', 'waId': wa_msg_id,
            'recipient': recipient, 'requestId': request_id}))
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'auto_react_fail', 'error': str(e),
            'requestId': request_id}))


def _send_read_receipt(wa_msg_id: str, recipient: str, phone_id: str, request_id: str):
    """Send read receipt (blue check marks).
    
    NOTE: Calls social_messaging directly (not via shared/social_client.py)
    because read receipts are fire-and-forget — failure should not block
    inbound message processing.
    """
    try:
        clean = recipient.lstrip('+')
        payload = {
            'messaging_product': 'whatsapp',
            'status': 'read',
            'message_id': wa_msg_id,
            'to': f'+{clean}',
        }
        social_messaging.send_whatsapp_message(
            originationPhoneNumberId=phone_id,
            message=json.dumps(payload).encode('utf-8'),
            metaApiVersion=META_API_VERSION)
        logger.debug(json.dumps({
            'event': 'read_receipt_sent', 'waId': wa_msg_id,
            'recipient': recipient, 'requestId': request_id}))
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'read_receipt_fail', 'error': str(e),
            'requestId': request_id}))


def _send_to_dlq(record: Dict, error: str, request_id: str):
    if not INBOUND_DLQ_URL:
        return
    try:
        sqs.send_message(
            QueueUrl=INBOUND_DLQ_URL,
            MessageBody=json.dumps({
                'originalRecord': record,
                'error': error,
                'requestId': request_id,
                'timestamp': int(time.time()),
            }))
    except Exception as e:
        logger.error(f"DLQ send failed: {e}")
