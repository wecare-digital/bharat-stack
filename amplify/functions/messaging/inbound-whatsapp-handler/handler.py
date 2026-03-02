"""
Inbound WhatsApp Handler Lambda Function

Purpose: Process SNS notifications for WhatsApp messages
Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 5.12, 15.4, 15.7

Parses AWS EUM Social event format, stores messages, downloads media,
updates contact timestamps for 24-hour customer service window.
Tracks which WABA/phone number received the message.
Integrates with AI automation when enabled in SystemConfig.
"""

import os
import json
import uuid
import time
import logging
import boto3
from typing import Dict, Any, Optional
from decimal import Decimal

# Configure logging
from lambda_utils.logging import get_logger
from lambda_utils.response import extract_origin

# Sub-modules (monolith decomposition)
from modules.content import extract_content as _extract_content_v2
from modules.content import extract_unsupported_content as _extract_unsupported_content_v2

logger = get_logger(__name__)

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
sqs = boto3.client('sqs', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
social_messaging = boto3.client('socialmessaging', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
lambda_client = boto3.client('lambda', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Environment variables - use actual table names
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'base-wecare-digital-ContactsTable')
MESSAGES_TABLE = os.environ.get('MESSAGES_TABLE', 'base-wecare-digital-WhatsAppInboundTable')
MEDIA_FILES_TABLE = os.environ.get('MEDIA_FILES_TABLE', 'base-wecare-digital-MediaFilesTable')
SYSTEM_CONFIG_TABLE = os.environ.get('SYSTEM_CONFIG_TABLE', 'base-wecare-digital-SystemConfigTable')
AI_INTERACTIONS_TABLE = os.environ.get('AI_INTERACTIONS_TABLE', 'base-wecare-digital-AIInteractionsTable')
INVOICES_TABLE = os.environ.get('INVOICES_TABLE', 'base-wecare-digital-InvoicesTable')
INBOUND_DLQ_URL = os.environ.get('INBOUND_DLQ_URL', '')
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')
MEDIA_PREFIX = os.environ.get('MEDIA_INBOUND_PREFIX', 'whatsapp-media/whatsapp-media-incoming/')
SEND_MODE = os.environ.get('SEND_MODE', 'LIVE')
SUBMIT_REQUESTS_TABLE = os.environ.get('SUBMIT_REQUESTS_TABLE', 'base-wecare-digital-SubmitRequestsTable')

# AI Lambda function names
AI_QUERY_KB_FUNCTION = os.environ.get('AI_QUERY_KB_FUNCTION', 'wecare-ai-query-kb')
AI_GENERATE_RESPONSE_FUNCTION = os.environ.get('AI_GENERATE_RESPONSE_FUNCTION', 'wecare-ai-generate-response')

# Outbound WhatsApp Lambda function name
OUTBOUND_WHATSAPP_FUNCTION = os.environ.get('OUTBOUND_WHATSAPP_FUNCTION', 'wecare-outbound-whatsapp')

# WhatsApp Voice Lambda function name (TTS via Amazon Polly)
WHATSAPP_VOICE_FUNCTION = os.environ.get('WHATSAPP_VOICE_FUNCTION', 'wecare-whatsapp-voice')

# Fix #6: Circuit breaker for AI failures — skip AI if too many consecutive failures
_ai_fail_count = 0
_ai_fail_reset_time = 0
AI_CIRCUIT_BREAKER_THRESHOLD = 5   # failures before tripping
AI_CIRCUIT_BREAKER_COOLDOWN = 300  # seconds (5 min) before retrying

# WhatsApp Phone Number IDs - Map Meta phone number IDs to AWS phone number IDs
# Format: Meta phone number ID -> AWS EUM phone-number-id
PHONE_NUMBER_ID_1 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_1', 'phone-number-id-5e020cecd221429996f6ae721cc42206')
PHONE_NUMBER_ID_2 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_2', 'phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c')

# Map display phone numbers to AWS phone number IDs for reference
PHONE_NUMBER_MAP = {
    '919330994400': PHONE_NUMBER_ID_1,  # +91 93309 94400
    '919903300044': PHONE_NUMBER_ID_2,  # +91 99033 00044
}

# TTL: 30 days in seconds
MESSAGE_TTL_SECONDS = 30 * 24 * 60 * 60

# ── Payment flow messages (hardcoded, LLM-independent, edit here to change) ──
PAY_MSG = {
    'pulling':      '\U0001f440 Pulling your pending invoice...',
    'no_dues':      '\u2705 No pending dues!',
    'paid':         '\u2705 Paid successfully.',
    'pay_failed':   '\u274c Payment failed. Please try again.',
    'all_clear':    '\u2705 No pending dues!',
    'next_due':     '\u26a0\ufe0f You have unpaid invoice of \u20b9{total}.',
    'send_failed':  '\u274c Could not send payment link. Please try again.',
    'error':        '\u26a0\ufe0f Something went wrong. Please try again.',
    'wa_body':      'Your payment is ready \u2014 tap below to complete it \U0001f4b3',
    'redirect':     '\U0001f4b3 To make a payment, please send *pay* to +91 9330994400',
}

# Phone number ID that handles payments (Phone 1: +919330994400 / WECARE.DIGITAL)
PAYMENT_PHONE_NUMBER_ID = 'phone-number-id-5e020cecd221429996f6ae721cc42206'

# WhatsApp Flow IDs
SUBMIT_REQUEST_FLOW_ID = os.environ.get('SUBMIT_REQUEST_FLOW_ID', '1235100738173254')


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process inbound WhatsApp messages from SNS.
    
    AWS EUM Social Event Format:
    {
        "context": { "MetaWabaIds": [...], "MetaPhoneNumberIds": [...] },
        "whatsAppWebhookEntry": "{...JSON STRING...}",
        "aws_account_id": "775261844268",
        "message_timestamp": "2026-01-17T12:00:00.000Z",
        "messageId": "uuid"
    }
    """
    request_id = context.aws_request_id if context else 'local'
    origin = extract_origin(event)
    processed_count = 0
    error_count = 0

    # ── Direct invoke: create_invoice from dashboard ──
    if event.get('action') == 'create_invoice':
        return _handle_dashboard_invoice(event, request_id)
    
    logger.info(json.dumps({
        'event': 'inbound_processing_start',
        'recordCount': len(event.get('Records', [])),
        'requestId': request_id
    }))
    
    for record in event.get('Records', []):
        try:
            # Parse SNS message
            sns_message = json.loads(record.get('Sns', {}).get('Message', '{}'))
            
            # Extract WABA context - which WABA received this message
            context_data = sns_message.get('context', {})
            meta_waba_ids = context_data.get('MetaWabaIds', [])
            meta_phone_number_ids = context_data.get('MetaPhoneNumberIds', [])
            
            webhook_entry_str = sns_message.get('whatsAppWebhookEntry', '{}')
            aws_message_id = sns_message.get('messageId', str(uuid.uuid4()))
            
            # Decode whatsAppWebhookEntry JSON string
            webhook_entry = json.loads(webhook_entry_str)
            
            # Process each change in the webhook entry
            for change in webhook_entry.get('changes', []):
                value = change.get('value', {})
                metadata = value.get('metadata', {})
                
                # Extract receiving phone number info from metadata
                display_phone_number = metadata.get('display_phone_number', '')
                phone_number_id = metadata.get('phone_number_id', '')
                
                # Determine AWS phone number ID for this WABA
                aws_phone_number_id = _get_aws_phone_number_id(display_phone_number, phone_number_id)
                
                # Extract contacts info (contains profile names)
                # WhatsApp webhook format: contacts array has wa_id and profile.name
                contacts_info = value.get('contacts', [])
                contacts_map = {}
                for contact_info in contacts_info:
                    wa_id = contact_info.get('wa_id', '')
                    profile_name = contact_info.get('profile', {}).get('name', '')
                    if wa_id:
                        contacts_map[wa_id] = profile_name
                
                # Process incoming messages
                for message in value.get('messages', []):
                    try:
                        # Get sender's profile name from contacts array
                        sender_phone = message.get('from', '')
                        sender_profile_name = contacts_map.get(sender_phone, '')
                        
                        _process_message(
                            message=message,
                            metadata=metadata,
                            request_id=request_id,
                            receiving_phone=display_phone_number,
                            aws_phone_number_id=aws_phone_number_id,
                            meta_waba_ids=meta_waba_ids,
                            sender_profile_name=sender_profile_name
                        )
                        processed_count += 1
                    except Exception as e:
                        logger.error(json.dumps({
                            'event': 'message_processing_error',
                            'messageId': message.get('id'),
                            'error': str(e),
                            'requestId': request_id
                        }))
                        error_count += 1
                
                # Process status updates
                for status in value.get('statuses', []):
                    try:
                        _process_status(status, request_id)
                    except Exception as e:
                        logger.error(json.dumps({
                            'event': 'status_processing_error',
                            'statusId': status.get('id'),
                            'error': str(e),
                            'requestId': request_id
                        }))
                
                # Process template status updates (APPROVED, REJECTED, PAUSED, etc.)
                field = change.get('field', '')
                if field == 'message_template_status_update':
                    try:
                        _process_template_status(value, request_id)
                    except Exception as e:
                        logger.error(json.dumps({
                            'event': 'template_status_processing_error',
                            'error': str(e),
                            'requestId': request_id
                        }))
                
                # Process phone number quality updates
                if field == 'phone_number_quality_update':
                    try:
                        _process_phone_quality_update(value, request_id)
                    except Exception as e:
                        logger.error(json.dumps({
                            'event': 'phone_quality_processing_error',
                            'error': str(e),
                            'requestId': request_id
                        }))
                
                # Process account updates (messaging limits, etc.)
                if field == 'account_update':
                    try:
                        _process_account_update(value, request_id)
                    except Exception as e:
                        logger.error(json.dumps({
                            'event': 'account_update_processing_error',
                            'error': str(e),
                            'requestId': request_id
                        }))
                        
        except Exception as e:
            logger.error(json.dumps({
                'event': 'record_processing_error',
                'error': str(e),
                'requestId': request_id
            }))
            _send_to_dlq(record, str(e), request_id)
            error_count += 1
    
    logger.info(json.dumps({
        'event': 'inbound_processing_complete',
        'processedCount': processed_count,
        'errorCount': error_count,
        'requestId': request_id
    }))
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'processed': processed_count,
            'errors': error_count
        })
    }


def _get_aws_phone_number_id(display_phone: str, meta_phone_id: str) -> str:
    """
    Map display phone number or Meta phone ID to AWS EUM phone number ID.
    Returns the appropriate AWS phone number ID for sending reactions.
    """
    # Clean display phone number (remove + and spaces)
    clean_phone = display_phone.replace('+', '').replace(' ', '').replace('-', '')
    
    # Check if we have a mapping for this phone number
    if clean_phone in PHONE_NUMBER_MAP:
        return PHONE_NUMBER_MAP[clean_phone]
    
    # Default to first phone number ID if no mapping found
    logger.warning(json.dumps({
        'event': 'phone_number_mapping_not_found',
        'displayPhone': display_phone,
        'metaPhoneId': meta_phone_id,
        'usingDefault': PHONE_NUMBER_ID_1
    }))
    return PHONE_NUMBER_ID_1


def _process_message(
    message: Dict,
    metadata: Dict,
    request_id: str,
    receiving_phone: str,
    aws_phone_number_id: str,
    meta_waba_ids: list,
    sender_profile_name: str = ''
) -> None:
    """
    Process a single inbound message.
    Stores which WABA/phone number received the message.
    """
    whatsapp_message_id = message.get('id')
    sender_phone = message.get('from')
    msg_type = message.get('type', 'text')
    timestamp = int(message.get('timestamp', time.time()))
    
    # Log full message for unsupported or unrecognized types to help debug
    if msg_type in ('unsupported', 'unknown') or msg_type not in (
        'text', 'image', 'video', 'audio', 'document', 'sticker',
        'location', 'contacts', 'reaction', 'interactive', 'button',
        'order', 'system', 'request_welcome', 'ephemeral',
        'referral', 'ad_click', 'product', 'product_inquiry', 'poll'
    ):
        logger.warning(json.dumps({
            'event': 'unsupported_or_new_message_type',
            'senderPhone': sender_phone,
            'whatsappMessageId': whatsapp_message_id,
            'messageType': msg_type,
            'messageKeys': list(message.keys()),
            'fullMessage': message,
            'requestId': request_id
        }))
    
    # Use sender profile name from contacts array (passed in)
    # Fall back to checking message.profile if not provided
    sender_name = sender_profile_name
    if not sender_name and 'profile' in message:
        sender_name = message.get('profile', {}).get('name', '')
    
    # Deduplicate using whatsappMessageId
    if _message_exists(whatsapp_message_id):
        logger.info(json.dumps({
            'event': 'message_duplicate_skipped',
            'whatsappMessageId': whatsapp_message_id,
            'requestId': request_id
        }))
        return
    
    # Lookup or create contact with sender name
    contact = _get_or_create_contact(sender_phone, sender_name)
    contact_id = contact.get('contactId') or contact.get('id')
    
    # Extract message content based on type
    content = _extract_content(message, msg_type)
    
    # Generate message ID and calculate TTL
    message_id = str(uuid.uuid4())
    now = int(time.time())
    expires_at = now + MESSAGE_TTL_SECONDS
    
    # Handle media messages (including stickers)
    media_id = None
    s3_key = None
    if msg_type in ['image', 'video', 'audio', 'document', 'sticker']:
        media_data = message.get(msg_type, {})
        whatsapp_media_id = media_data.get('id')
        mime_type_hint = media_data.get('mime_type', '')
        if whatsapp_media_id:
            s3_key = _download_media(whatsapp_media_id, message_id, msg_type, aws_phone_number_id, request_id, mime_type_hint)
            if s3_key:
                media_id = _store_media_record(message_id, s3_key, media_data, whatsapp_media_id)
    
    # Store message in DynamoDB with WABA info and sender name
    message_record = {
        'id': message_id,
        'messageId': message_id,
        'contactId': contact_id,
        'channel': 'whatsapp',
        'direction': 'inbound',
        'content': content,
        'messageType': msg_type,
        'timestamp': Decimal(str(timestamp)),
        'status': 'received',
        'whatsappMessageId': whatsapp_message_id,
        'mediaId': media_id,
        's3Key': s3_key,
        'senderPhone': sender_phone,
        'senderName': sender_name,  # Sender's WhatsApp profile name
        # WABA tracking - which number received this message
        'receivingPhone': receiving_phone,
        'awsPhoneNumberId': aws_phone_number_id,
        'metaWabaIds': meta_waba_ids if meta_waba_ids else None,
        'createdAt': Decimal(str(now)),
        'expiresAt': Decimal(str(expires_at)),
    }
    
    # Capture referral context (click-to-WhatsApp ads, product catalogs, social posts)
    # Referral can be attached to ANY message type, not just 'referral' type
    referral = message.get('referral')
    if referral:
        message_record['referralSource'] = referral.get('source_type', '')
        message_record['referralSourceId'] = referral.get('source_id', '')
        message_record['referralSourceUrl'] = referral.get('source_url', '')
        message_record['referralHeadline'] = referral.get('headline', '')
        message_record['referralBody'] = referral.get('body', '')
        logger.info(json.dumps({
            'event': 'referral_context',
            'senderPhone': sender_phone,
            'sourceType': referral.get('source_type', ''),
            'sourceUrl': referral.get('source_url', ''),
            'requestId': request_id
        }))
    
    # Capture message context (reply-to, forwarded)
    msg_context = message.get('context')
    if msg_context:
        message_record['replyToMessageId'] = msg_context.get('id', '')
        if msg_context.get('forwarded'):
            message_record['isForwarded'] = True
        if msg_context.get('frequently_forwarded'):
            message_record['isFrequentlyForwarded'] = True
        if msg_context.get('referred_product'):
            message_record['referredProduct'] = msg_context['referred_product']
    
    messages_table = dynamodb.Table(MESSAGES_TABLE)
    messages_table.put_item(Item={k: v for k, v in message_record.items() if v is not None})
    
    # Forward call_permission_reply to the WhatsApp Calling table
    # so the frontend knows permission was granted/denied for outbound calls
    if msg_type == 'interactive':
        interactive = message.get('interactive', {})
        interactive_type = interactive.get('type', '')
        if interactive_type == 'call_permission_reply':
            _forward_call_permission_to_calling_table(
                sender_phone=sender_phone,
                receiving_phone=receiving_phone,
                aws_phone_number_id=aws_phone_number_id,
                interactive=interactive,
            )
    
    # Update Contact.lastInboundMessageAt for 24-hour window
    _update_contact_timestamp(contact_id, now)
    
    logger.info(json.dumps({
        'event': 'message_stored',
        'messageId': message_id,
        'contactId': contact_id,
        'senderPhone': sender_phone,
        'senderName': sender_name,
        'whatsappMessageId': whatsapp_message_id,
        'type': msg_type,
        'hasMedia': bool(media_id),
        'receivingPhone': receiving_phone,
        'awsPhoneNumberId': aws_phone_number_id,
        'requestId': request_id
    }))
    
    # Auto-react with thumbs up (skip reactions to avoid loops)
    # Use the same phone number that received the message
    if msg_type != 'reaction':
        _send_auto_reaction(
            contact_id=contact_id,
            whatsapp_message_id=whatsapp_message_id,
            phone_number_id=aws_phone_number_id,
            request_id=request_id
        )
        
        # Send read receipt to show message was received
        _send_read_receipt(
            whatsapp_message_id=whatsapp_message_id,
            phone_number_id=aws_phone_number_id,
            request_id=request_id
        )
    
    # ── Keyword triggers (before AI automation) ──
    if msg_type == 'text' and content:
        content_lower = content.strip().lower()
        # Load flow triggers from SystemConfigTable (dashboard-configurable)
        flow_triggers = _get_flow_triggers_config()
        for flow_key, trigger in flow_triggers.items():
            if not trigger.get('enabled', True):
                continue
            keywords = [k.lower() for k in trigger.get('keywords', [])]
            if content_lower in keywords:
                if flow_key == 'submit_request':
                    _send_submit_request_flow(
                        contact_id=contact_id,
                        phone_number_id=aws_phone_number_id,
                        sender_phone=sender_phone,
                        request_id=request_id,
                        flow_config=trigger,
                    )
                    return  # Skip AI automation — flow handles the rest

    # Process AI automation for supported message types
    # Now includes media types (image, audio, video, document) for multimodal AI
    ai_eligible_types = ['text', 'interactive', 'button', 'location', 'image', 'video', 'audio', 'document']
    if msg_type in ai_eligible_types and (content or s3_key):
        _process_ai_automation(
            message_id=message_id,
            contact_id=contact_id,
            content=content,
            message_type=msg_type,
            phone_number_id=aws_phone_number_id,
            sender_phone=sender_phone,
            s3_key=s3_key,
            mime_type=message.get(msg_type, {}).get('mime_type', '') if msg_type in ('image', 'video', 'audio', 'document') else '',
            request_id=request_id
        )


def _extract_content(message: Dict, msg_type: str) -> str:
    """Extract message content based on type. Delegates to modules.content."""
    return _extract_content_v2(message, msg_type)


def _extract_unsupported_content(message: Dict) -> str:
    """Extract info from unsupported message types. Delegates to modules.content."""
    return _extract_unsupported_content_v2(message)


def _message_exists(whatsapp_message_id: str) -> bool:
    """Check if message already exists (deduplication) using GSI query."""
    if not whatsapp_message_id:
        return False
    try:
        messages_table = dynamodb.Table(MESSAGES_TABLE)
        response = messages_table.query(
            IndexName='whatsappMessageId-index',
            KeyConditionExpression='whatsappMessageId = :wmid',
            ExpressionAttributeValues={':wmid': whatsapp_message_id},
            Limit=1
        )
        return len(response.get('Items', [])) > 0
    except Exception as e:
        # Fallback to scan if GSI not ready yet
        logger.warning(f"GSI query failed, falling back to scan: {str(e)}")
        try:
            response = messages_table.scan(
                FilterExpression='whatsappMessageId = :wmid',
                ExpressionAttributeValues={':wmid': whatsapp_message_id},
                Limit=1
            )
            return len(response.get('Items', [])) > 0
        except Exception:
            return False


def _get_or_create_contact(phone: str, sender_name: str = '') -> Dict[str, Any]:
    """Get existing contact or create new one."""
    contacts_table = dynamodb.Table(CONTACTS_TABLE)
    
    # Clean phone for search - remove + prefix if present
    clean_phone = phone.lstrip('+')
    phone_with_plus = f'+{clean_phone}'
    
    # Use GSI query on phone-index for O(1) lookup (try both formats)
    items = []
    for phone_variant in [phone_with_plus, clean_phone]:
        try:
            response = contacts_table.query(
                IndexName='phone-index',
                KeyConditionExpression='phone = :phone',
                ExpressionAttributeValues={':phone': phone_variant},
                Limit=10
            )
            variant_items = response.get('Items', [])
            # Filter out deleted contacts
            variant_items = [i for i in variant_items if not i.get('deletedAt')]
            items.extend(variant_items)
        except Exception as e:
            logger.warning(f"GSI phone-index query failed for {phone_variant}: {str(e)}")
    
    # Fallback to scan if GSI not ready
    if not items:
        try:
            response = contacts_table.scan(
                FilterExpression='(phone = :phone1 OR phone = :phone2) AND (attribute_not_exists(deletedAt) OR deletedAt = :null)',
                ExpressionAttributeValues={
                    ':phone1': clean_phone,
                    ':phone2': phone_with_plus,
                    ':null': None
                },
                Limit=100
            )
            items = response.get('Items', [])
        except Exception:
            items = []
    
    if items:
        # Deduplicate by id in case both phone formats matched the same contact
        seen_ids = set()
        unique_items = []
        for item in items:
            item_id = item.get('id', '')
            if item_id not in seen_ids:
                seen_ids.add(item_id)
                unique_items.append(item)
        items = unique_items
        
        # Return the first (oldest) contact to avoid duplicates
        contact = sorted(items, key=lambda x: x.get('createdAt', 0))[0]
        # Update name if sender provided a name and contact doesn't have one or has placeholder
        current_name = contact.get('name', '')
        if sender_name and (not current_name or current_name in ['', '~', 'Unknown']):
            try:
                contacts_table.update_item(
                    Key={'id': contact.get('id')},
                    UpdateExpression='SET #name = :name, updatedAt = :now',
                    ExpressionAttributeNames={'#name': 'name'},
                    ExpressionAttributeValues={':name': sender_name, ':now': Decimal(str(int(time.time())))}
                )
                contact['name'] = sender_name
            except Exception as e:
                logger.warning(f"Failed to update contact name: {str(e)}")
        return contact
    
    # Create new contact
    contact_id = str(uuid.uuid4())
    now = int(time.time())
    
    # Ensure phone has + prefix for international format (easier for SMS)
    formatted_phone = phone if phone.startswith('+') else f'+{phone}'
    
    contact = {
        'id': contact_id,
        'contactId': contact_id,
        'name': sender_name or '',
        'phone': formatted_phone,
        'email': None,
        'optInWhatsApp': True,
        'optInSms': True,
        'optInEmail': True,
        'allowlistWhatsApp': True,
        'allowlistSms': True,
        'allowlistEmail': True,
        'lastInboundMessageAt': Decimal(str(now)),
        'createdAt': Decimal(str(now)),
        'updatedAt': Decimal(str(now)),
    }
    
    contacts_table.put_item(Item=contact)
    
    logger.info(json.dumps({
        'event': 'contact_auto_created',
        'contactId': contact_id,
        'phone': phone,
        'name': sender_name
    }))
    
    return contact


def _update_contact_timestamp(contact_id: str, timestamp: int) -> None:
    """Update contact's lastInboundMessageAt for 24-hour window tracking."""
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        contacts_table.update_item(
            Key={'id': contact_id},
            UpdateExpression='SET lastInboundMessageAt = :ts, updatedAt = :ts',
            ExpressionAttributeValues={':ts': Decimal(str(timestamp))}
        )
    except Exception as e:
        logger.error(f"Failed to update contact timestamp: {str(e)}")


def _download_media(whatsapp_media_id: str, message_id: str, media_type: str, 
                    phone_number_id: str, request_id: str,
                    mime_type_hint: str = '') -> Optional[str]:
    """
    Download media file from WhatsApp using AWS EUM Social API.
    
    Per AWS docs (S3File.key): The key is a PREFIX — AWS appends the WhatsApp
    mediaId to create the final file path. For example:
      key = "audio/"             → final = "audio/{mediaId}.ogg"
    
    Strategy: Use MEDIA_PREFIX directly (ending with "/") so files land flat
    under whatsapp-media/whatsapp-media-incoming/{mediaId}.{ext}
    
    Returns the actual S3 key of the downloaded file.
    """
    try:
        # Use MEDIA_PREFIX directly — files land flat, no subfolders
        s3_key_prefix = MEDIA_PREFIX  # e.g. "whatsapp-media/whatsapp-media-incoming/"
        
        logger.info(json.dumps({
            'event': 'media_download_start',
            'mediaId': whatsapp_media_id,
            's3KeyPrefix': s3_key_prefix,
            'mediaType': media_type,
            'mimeTypeHint': mime_type_hint,
            'phoneNumberId': phone_number_id,
            'requestId': request_id
        }))
        
        # Call AWS Social Messaging API to download media to S3
        response = social_messaging.get_whatsapp_message_media(
            mediaId=whatsapp_media_id,
            originationPhoneNumberId=phone_number_id,
            destinationS3File={
                'bucketName': MEDIA_BUCKET,
                'key': s3_key_prefix
            }
        )
        
        # Response contains mimeType and fileSize
        mime_type = response.get('mimeType', '')
        file_size = response.get('fileSize', 0)
        
        logger.info(json.dumps({
            'event': 'media_download_response',
            'mediaId': whatsapp_media_id,
            'mimeType': mime_type,
            'fileSize': file_size,
            'requestId': request_id
        }))
        
        # Find the actual file that AWS created in S3
        # Search using MEDIA_PREFIX + whatsapp_media_id to find the exact file
        search_prefix = f"{MEDIA_PREFIX}{whatsapp_media_id}"
        actual_s3_key = None
        try:
            s3_response = s3.list_objects_v2(
                Bucket=MEDIA_BUCKET,
                Prefix=search_prefix,
                MaxKeys=5
            )
            contents = s3_response.get('Contents', [])
            # Filter out zero-byte folder markers
            real_files = [c for c in contents if c.get('Size', 0) > 0]
            if real_files:
                actual_s3_key = real_files[0]['Key']
                logger.info(json.dumps({
                    'event': 'media_s3_key_found',
                    'prefix': search_prefix,
                    'actualS3Key': actual_s3_key,
                    'fileSize': real_files[0].get('Size', 0),
                    'requestId': request_id
                }))
        except Exception as list_err:
            logger.warning(json.dumps({
                'event': 'media_s3_list_failed',
                'prefix': search_prefix,
                'error': str(list_err),
                'requestId': request_id
            }))
        
        # Fallback: construct expected key from mimeType if list failed
        if not actual_s3_key:
            ext = _get_extension_from_mime(mime_type) if mime_type else _get_extension_from_type(media_type)
            actual_s3_key = f"{MEDIA_PREFIX}{whatsapp_media_id}{ext}"
            logger.warning(json.dumps({
                'event': 'media_using_constructed_key',
                'constructedKey': actual_s3_key,
                'requestId': request_id
            }))
        
        logger.info(json.dumps({
            'event': 'media_downloaded',
            'mediaId': whatsapp_media_id,
            's3KeyPrefix': s3_key_prefix,
            'actualS3Key': actual_s3_key,
            'mimeType': mime_type,
            'fileSize': file_size,
            'phoneNumberId': phone_number_id,
            'requestId': request_id
        }))
        
        return actual_s3_key
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'media_download_error',
            'mediaId': whatsapp_media_id,
            'error': str(e),
            'requestId': request_id
        }))
        return None


def _get_extension_from_type(media_type: str) -> str:
    """
    Get file extension based on WhatsApp message type.
    Used as fallback when mime_type is not available.
    
    Supported types per WhatsApp Business Platform Cloud API:
    - image: JPEG (5MB), PNG (5MB)
    - video: MP4 (16MB), 3GPP (16MB)
    - audio: AAC (16MB), AMR (16MB), MP3 (16MB), M4A (16MB), OGG (16MB)
    - document: PDF, TXT, DOC/DOCX, XLS/XLSX, PPT/PPTX (100MB)
    - sticker: WEBP (500KB animated, 100KB static)
    """
    type_extensions = {
        'image': '.jpeg',
        'video': '.mp4',
        'audio': '.ogg',
        'document': '.pdf',
        'sticker': '.webp'
    }
    return type_extensions.get(media_type, '.bin')


def _get_extension_from_mime(mime_type: str) -> str:
    """
    Get file extension based on MIME type.
    Complete mapping per WhatsApp Business Platform supported media types.
    """
    mime_extensions = {
        # Image formats (max 5MB)
        'image/jpeg': '.jpeg',
        'image/png': '.png',
        
        # Sticker formats (max 500KB animated, 100KB static)
        'image/webp': '.webp',
        
        # Video formats (max 16MB)
        'video/mp4': '.mp4',
        'video/3gpp': '.3gp',
        
        # Audio formats (max 16MB)
        'audio/aac': '.aac',
        'audio/amr': '.amr',
        'audio/mpeg': '.mp3',
        'audio/mp4': '.m4a',
        'audio/ogg': '.ogg',
        'audio/opus': '.opus',
        
        # Document formats (max 100MB)
        'application/pdf': '.pdf',
        'text/plain': '.txt',
        'application/msword': '.doc',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
        'application/vnd.ms-excel': '.xls',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
        'application/vnd.ms-powerpoint': '.ppt',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
    }
    return mime_extensions.get(mime_type, '.bin')


def _store_media_record(message_id: str, s3_key: str, media_data: Dict, whatsapp_media_id: str) -> Optional[str]:
    """
    Store media file record in MediaFiles table.
    Returns file_id if successful, None if table doesn't exist or write fails.
    This is optional - the s3Key is stored directly in the message record.
    """
    try:
        file_id = str(uuid.uuid4())
        now = int(time.time())
        
        media_record = {
            'fileId': file_id,
            'messageId': message_id,
            's3Key': s3_key,
            'contentType': media_data.get('mime_type', ''),
            'size': Decimal(str(media_data.get('file_size', 0))) if media_data.get('file_size') else None,
            'whatsappMediaId': whatsapp_media_id,
            'uploadedAt': Decimal(str(now)),
        }
        
        media_table = dynamodb.Table(MEDIA_FILES_TABLE)
        media_table.put_item(Item={k: v for k, v in media_record.items() if v is not None})
        
        logger.info(json.dumps({
            'event': 'media_record_stored',
            'fileId': file_id,
            'messageId': message_id,
            's3Key': s3_key
        }))
        
        return file_id
    except Exception as e:
        # MediaFile table may not exist - this is OK, s3Key is stored in message record
        logger.warning(json.dumps({
            'event': 'media_record_store_skipped',
            'messageId': message_id,
            's3Key': s3_key,
            'error': str(e),
            'note': 'MediaFile table write failed, but s3Key is stored in message record'
        }))
        return None


def _process_status(status: Dict, request_id: str) -> None:
    """
    Process message status update (sent|delivered|read|failed|payment).
    Checks BOTH InboundTable and OutboundTable using GSI for O(1) lookup.
    
    Payment status webhooks have type='payment' with payment object containing:
    - reference_id: Order/invoice reference
    - amount: {value, offset}
    - currency: INR
    - status: pending|captured|failed
    """
    whatsapp_message_id = status.get('id')
    status_value = status.get('status')
    status_type = status.get('type', '')  # 'payment' for payment webhooks
    timestamp = int(status.get('timestamp', time.time()))
    recipient_id = status.get('recipient_id', '')
    
    # Log all status updates for debugging
    logger.info(json.dumps({
        'event': 'status_update_received',
        'statusType': status_type,
        'statusValue': status_value,
        'whatsappMessageId': whatsapp_message_id,
        'recipientId': recipient_id,
        'hasPaymentData': 'payment' in status,
        'fullStatus': status,
        'requestId': request_id
    }))
    
    # Handle payment status webhooks FIRST (before other checks)
    if status_type == 'payment' or 'payment' in status:
        _process_payment_status(status, request_id)
        return
    
    if not whatsapp_message_id or not status_value:
        return
    
    # Search BOTH tables for the message using GSI
    OUTBOUND_TABLE = os.environ.get('OUTBOUND_TABLE', 'base-wecare-digital-WhatsAppOutboundTable')
    tables_to_check = [
        ('inbound', MESSAGES_TABLE),
        ('outbound', OUTBOUND_TABLE),
    ]
    
    updated = False
    for direction, table_name in tables_to_check:
        try:
            table = dynamodb.Table(table_name)
            
            # Use GSI query for O(1) lookup
            try:
                response = table.query(
                    IndexName='whatsappMessageId-index',
                    KeyConditionExpression='whatsappMessageId = :wmid',
                    ExpressionAttributeValues={':wmid': whatsapp_message_id},
                    Limit=1
                )
            except Exception:
                # Fallback to scan if GSI not ready
                response = table.scan(
                    FilterExpression='whatsappMessageId = :wmid',
                    ExpressionAttributeValues={':wmid': whatsapp_message_id},
                    Limit=1
                )
            
            items = response.get('Items', [])
            if items:
                message_id = items[0].get('id') or items[0].get('messageId')
                table.update_item(
                    Key={'id': message_id},
                    UpdateExpression='SET #status = :status, statusUpdatedAt = :ts',
                    ExpressionAttributeNames={'#status': 'status'},
                    ExpressionAttributeValues={
                        ':status': status_value,
                        ':ts': Decimal(str(timestamp))
                    }
                )
                
                logger.info(json.dumps({
                    'event': 'status_updated',
                    'messageId': message_id,
                    'whatsappMessageId': whatsapp_message_id,
                    'status': status_value,
                    'table': direction,
                    'requestId': request_id
                }))
                updated = True
                break  # Found and updated, no need to check other table
                
        except Exception as e:
            logger.error(json.dumps({
                'event': 'status_update_error',
                'whatsappMessageId': whatsapp_message_id,
                'table': direction,
                'error': str(e),
                'requestId': request_id
            }))
    
    if not updated:
        logger.warning(json.dumps({
            'event': 'status_update_message_not_found',
            'whatsappMessageId': whatsapp_message_id,
            'status': status_value,
            'requestId': request_id
        }))


def _sanitize_reference_id(reference_id: str) -> str:
    """
    Sanitize reference_id - remove duplicate prefixes and underscores.
    
    WhatsApp/Razorpay may return reference_id with extra prefixes or underscores.
    This ensures clean WD-PAY-<ID> format for display.
    
    Examples:
    - "WD-PAY-ABC12345" -> "WD-PAY-ABC12345" (keep as-is)
    - "WD-PAY-WD-PAY-ABC" -> "WD-PAY-ABC" (remove duplicate prefix)
    - "WD_41BA3534" -> "WD-PAY-41BA3534" (upgrade old format)
    - "WDABC12345" -> "WD-PAY-ABC12345" (upgrade old format)
    - "WD+41BA3534" -> "WD-PAY-41BA3534" (remove plus sign)
    """
    import re
    
    if not reference_id:
        return reference_id
    
    stripped = reference_id.strip().upper()
    
    # Remove duplicate WD-PAY- prefixes
    while 'WD-PAY-WD-PAY-' in stripped:
        stripped = stripped.replace('WD-PAY-WD-PAY-', 'WD-PAY-')
    
    # Already in new format
    if stripped.startswith('WD-PAY-'):
        return stripped
    if stripped.startswith('WD-ORD-'):
        return stripped
    
    # Old format: strip non-alnum, remove legacy WD prefix(es), add WD-PAY-
    cleaned = re.sub(r'[^A-Za-z0-9]', '', stripped)
    while cleaned.startswith('WD'):
        cleaned = cleaned[2:]
    if not cleaned:
        return stripped  # Return original if nothing left
    
    return f'WD-PAY-{cleaned}'


def _process_payment_status(status: Dict, request_id: str) -> None:
    """
    Process payment status webhook from WhatsApp.
    
    Payment webhook format:
    {
        "id": "wamid.xxx",
        "recipient_id": "919876543210",
        "type": "payment",
        "status": "captured",  // pending, captured, failed
        "payment": {
            "reference_id": "ORDER_12345",
            "amount": {"value": 10000, "offset": 100},
            "currency": "INR",
            "transaction": {
                "id": "txn_xxx",
                "type": "upi",
                "status": "success"
            }
        },
        "timestamp": "1706140800"
    }
    """
    # Log full status for debugging
    logger.info(json.dumps({
        'event': 'payment_status_processing',
        'fullStatus': status,
        'requestId': request_id
    }))
    
    payment_data = status.get('payment', {})
    raw_reference_id = payment_data.get('reference_id', '')
    # Sanitize reference_id - remove duplicate WD prefix and underscores
    reference_id = _sanitize_reference_id(raw_reference_id)
    payment_status = status.get('status', '')
    recipient_id = status.get('recipient_id', '')
    timestamp = int(status.get('timestamp', time.time()))
    
    # Log payment data extraction
    logger.info(json.dumps({
        'event': 'payment_data_extracted',
        'paymentData': payment_data,
        'referenceId': reference_id,
        'paymentStatus': payment_status,
        'recipientId': recipient_id,
        'requestId': request_id
    }))
    
    amount = payment_data.get('amount', {})
    amount_value = amount.get('value', 0)
    amount_offset = amount.get('offset', 100)
    currency = payment_data.get('currency', 'INR')
    
    # Log amount extraction with full details
    logger.info(json.dumps({
        'event': 'payment_amount_extracted',
        'amountObject': amount,
        'amountValue': amount_value,
        'amountOffset': amount_offset,
        'paymentDataKeys': list(payment_data.keys()) if payment_data else [],
        'requestId': request_id
    }))
    
    # Calculate actual amount (value / offset)
    actual_amount = amount_value / amount_offset if amount_offset else amount_value
    
    # If amount is 0, try to look up from original payment request in DynamoDB
    if actual_amount == 0 and reference_id:
        logger.info(json.dumps({
            'event': 'payment_amount_zero_lookup',
            'referenceId': reference_id,
            'requestId': request_id
        }))
        actual_amount = _lookup_payment_amount(reference_id, request_id)
    
    transaction = payment_data.get('transaction', {})
    transaction_id = transaction.get('id', '')
    transaction_type = transaction.get('type', '')
    
    logger.info(json.dumps({
        'event': 'payment_status_received',
        'referenceId': reference_id,
        'paymentStatus': payment_status,
        'recipientId': recipient_id,
        'amount': actual_amount,
        'currency': currency,
        'transactionId': transaction_id,
        'transactionType': transaction_type,
        'requestId': request_id
    }))
    
    # Store payment record in DynamoDB
    _store_payment_record(
        reference_id=reference_id,
        recipient_id=recipient_id,
        payment_status=payment_status,
        amount_value=amount_value,
        amount_offset=amount_offset,
        currency=currency,
        transaction_id=transaction_id,
        transaction_type=transaction_type,
        timestamp=timestamp,
        request_id=request_id
    )
    
    # Look up the phone_number_id from the original outbound payment request
    # so the confirmation goes back from the same business number
    originating_phone_id = None
    if reference_id:
        try:
            OUTBOUND_TABLE = os.environ.get('OUTBOUND_TABLE', 'base-wecare-digital-WhatsAppOutboundTable')
            outbound_table = dynamodb.Table(OUTBOUND_TABLE)
            # Query GSI paymentReferenceId-index (falls back to scan if GSI missing)
            found = False
            try:
                resp = outbound_table.query(
                    IndexName='paymentReferenceId-index',
                    KeyConditionExpression='paymentReferenceId = :ref',
                    Limit=1,
                )
                items = resp.get('Items', [])
                if items:
                    originating_phone_id = items[0].get('awsPhoneNumberId') or items[0].get('phoneNumberId')
                    found = True
            except Exception:
                # Fallback to paginated scan if GSI not yet active
                scan_kwargs = {
                    'FilterExpression': 'paymentReferenceId = :ref',
                    'ExpressionAttributeValues': {':ref': reference_id},
                    'ProjectionExpression': 'awsPhoneNumberId, phoneNumberId',
                }
                while not found:
                    resp = outbound_table.scan(**scan_kwargs)
                    items = resp.get('Items', [])
                    if items:
                        originating_phone_id = items[0].get('awsPhoneNumberId') or items[0].get('phoneNumberId')
                        found = True
                    elif 'LastEvaluatedKey' in resp:
                        scan_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
                    else:
                        break
            
            logger.info(json.dumps({
                'event': 'payment_phone_id_resolved',
                'referenceId': reference_id,
                'phoneNumberId': originating_phone_id,
                'found': found,
                'requestId': request_id
            }))
        except Exception as e:
            logger.warning(json.dumps({
                'event': 'payment_phone_id_lookup_failed',
                'referenceId': reference_id,
                'error': str(e),
                'requestId': request_id
            }))

    # Detect effective failure: WhatsApp may send status="pending" but
    # transaction.status="failed" (e.g. insufficient funds / gateway error).
    transaction_status = transaction.get('status', '')
    effective_failed = (
        payment_status == 'failed'
        or (payment_status == 'pending' and transaction_status in ('failed', 'error'))
    )

    # Send order_status message based on payment status
    if payment_status == 'captured':
        # ── Direct invoice status update in InvoicesTable ──
        # Ensures the invoice is marked paid even if the dedup path in
        # create_invoice is skipped (e.g. invoice was created from dashboard).
        _mark_invoice_paid_by_reference(reference_id, request_id)

        _send_order_status_message(
            recipient_id=recipient_id,
            reference_id=reference_id,
            order_status='completed',
            amount=actual_amount,
            description=PAY_MSG['paid'],
            request_id=request_id,
            phone_number_id=originating_phone_id
        )
        # Generate and send invoice after successful payment
        _generate_invoice_for_captured_payment(
            reference_id=reference_id,
            recipient_id=recipient_id,
            actual_amount=actual_amount,
            phone_number_id=originating_phone_id,
            request_id=request_id,
        )
        # Check for remaining pending dues and notify
        _check_and_notify_balance_due(
            recipient_id=recipient_id,
            paid_reference_id=reference_id,
            phone_number_id=originating_phone_id,
            request_id=request_id,
        )
    elif effective_failed:
        logger.info(json.dumps({
            'event': 'payment_effective_failure',
            'paymentStatus': payment_status,
            'transactionStatus': transaction_status,
            'referenceId': reference_id,
            'requestId': request_id,
        }))
        _send_order_status_message(
            recipient_id=recipient_id,
            reference_id=reference_id,
            order_status='canceled',
            amount=0,
            description=PAY_MSG['pay_failed'],
            request_id=request_id,
            phone_number_id=originating_phone_id
        )
    elif payment_status == 'pending':
        # Genuine pending (transaction still in progress) — log and wait
        logger.info(json.dumps({
            'event': 'payment_pending_waiting',
            'referenceId': reference_id,
            'transactionStatus': transaction_status,
            'requestId': request_id,
        }))


def _mark_invoice_paid_by_reference(reference_id: str, request_id: str) -> None:
    """Directly update InvoicesTable: set status=paid for the given referenceId.
    This is a safety net so the invoice is always marked paid on capture,
    regardless of whether the dedup path in create_invoice runs later."""
    if not reference_id:
        return
    try:
        import datetime
        table = dynamodb.Table(INVOICES_TABLE)
        now = int(time.time())
        now_ist = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
        paid_at_ts = int(now_ist.timestamp())

        # Scan for invoice with this referenceId
        scan_kwargs = {
            'FilterExpression': 'referenceId = :ref',
            'ExpressionAttributeValues': {':ref': reference_id},
        }
        found = []
        while True:
            resp = table.scan(**scan_kwargs)
            found.extend(resp.get('Items', []))
            if found or 'LastEvaluatedKey' not in resp:
                break
            scan_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']

        for inv in found:
            if inv.get('status') != 'paid':
                table.update_item(
                    Key={'invoiceId': inv['invoiceId']},
                    UpdateExpression='SET #st = :st, #ps = :ps, #pa = :pa, #ua = :now',
                    ExpressionAttributeNames={
                        '#st': 'status', '#ps': 'paymentStatus',
                        '#pa': 'paidAt', '#ua': 'updatedAt',
                    },
                    ExpressionAttributeValues={
                        ':st': 'paid', ':ps': 'captured',
                        ':pa': paid_at_ts, ':now': now,
                    },
                )
                logger.info(json.dumps({
                    'event': 'invoice_marked_paid_direct',
                    'invoiceId': inv['invoiceId'],
                    'referenceId': reference_id,
                    'requestId': request_id,
                }))
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'mark_invoice_paid_error',
            'referenceId': reference_id,
            'error': str(e),
            'requestId': request_id,
        }))


def _generate_invoice_for_captured_payment(reference_id: str, recipient_id: str,
                                           actual_amount: float, phone_number_id: str,
                                           request_id: str) -> None:
    """
    After WhatsApp payment captured: create invoice via unified invoice engine.
    Uses wecare-invoice-engine Lambda for proper GST sequencing (WD/FY/NNNNN).
    Also sends the invoice image on WhatsApp automatically.
    """
    import datetime
    try:
        messages_table = dynamodb.Table(MESSAGES_TABLE)
        items = []

        # Try GSI query first, fall back to scan if index doesn't exist
        try:
            resp = messages_table.query(
                IndexName='messageId-index',
                KeyConditionExpression='messageId = :mid',
                ExpressionAttributeValues={':mid': reference_id},
                Limit=1,
            )
            items = resp.get('Items', [])
        except Exception as gsi_err:
            logger.info(json.dumps({
                'event': 'invoice_gsi_fallback',
                'referenceId': reference_id,
                'gsiError': str(gsi_err)[:100],
                'requestId': request_id,
            }))

        # Fallback: scan for paymentReferenceId (paginate to find it)
        if not items:
            scan_kwargs = {
                'FilterExpression': 'paymentReferenceId = :ref AND messageType = :mt',
                'ExpressionAttributeValues': {':ref': reference_id, ':mt': 'payment_request'},
            }
            while not items:
                resp = messages_table.scan(**scan_kwargs)
                items = resp.get('Items', [])
                if items:
                    break
                if 'LastEvaluatedKey' in resp:
                    scan_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
                else:
                    break

        if not items:
            logger.warning(json.dumps({
                'event': 'invoice_no_payment_request_found',
                'referenceId': reference_id,
                'requestId': request_id,
            }))
            return

        pr = items[0]
        contact_id = pr.get('contactId', '')
        sender_phone = pr.get('senderPhone', recipient_id)

        # Extract fields from payment_request record
        unit_price = float(pr.get('paymentAmount', 0)) / 100  # stored in paise
        quantity = int(pr.get('paymentQuantity', 1))
        item_name = pr.get('paymentItemName', 'Services/Goods')
        gst_rate = float(pr.get('paymentGstRate', 18))
        shipping = float(pr.get('paymentShipping', 0)) / 100  # stored in paise
        handling = float(pr.get('paymentHandling', 0)) / 100  # stored in paise
        discount = float(pr.get('paymentDiscount', 0)) / 100  # stored in paise
        purpose = pr.get('paymentPurpose', '')
        order_id = pr.get('paymentOrderId', 'Offline')
        customer_name = pr.get('paymentCustomerName', '')
        customer_phone = pr.get('paymentCustomerPhone', sender_phone)
        customer_email = pr.get('paymentCustomerEmail', '')
        shipping_address = pr.get('paymentShippingAddress', '')
        billing_address = pr.get('paymentBillingAddress', '')

        now_ist = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
        paid_at_ts = int(now_ist.timestamp())

        # ── Step 1: Create invoice via unified invoice engine ──
        invoice_payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'customerName': customer_name,
                'customerPhone': customer_phone,
                'paidByPhone': customer_phone,
                'customerEmail': customer_email,
                'shippingAddress': shipping_address,
                'billingAddress': billing_address,
                'items': [{'name': item_name, 'amount': unit_price, 'quantity': quantity}],
                'gstRate': gst_rate,
                'shipping': shipping,
                'handling': handling,
                'discount': discount,
                'purpose': purpose,
                'orderId': order_id,
                'referenceId': reference_id,
                'entryPoint': 'whatsapp_payment',
                'status': 'paid',
                'paymentStatus': 'captured',
                'paidAt': paid_at_ts,
            }),
            'rawPath': '/invoices',
            'requestContext': {'http': {'method': 'POST'}},
        }

        inv_response = lambda_client.invoke(
            FunctionName='wecare-invoice-engine',
            InvocationType='RequestResponse',
            Payload=json.dumps(invoice_payload),
        )
        inv_result = json.loads(inv_response['Payload'].read())
        inv_body = json.loads(inv_result.get('body', '{}'))
        invoice_id = inv_body.get('invoiceId', '')
        invoice_number = inv_body.get('invoiceNumber', '')

        logger.info(json.dumps({
            'event': 'invoice_created_via_engine',
            'invoiceId': invoice_id,
            'invoiceNumber': invoice_number,
            'referenceId': reference_id,
            'entryPoint': 'whatsapp_payment',
            'requestId': request_id,
        }))

        if not invoice_id:
            logger.error(json.dumps({
                'event': 'invoice_engine_empty_response',
                'referenceId': reference_id,
                'response': str(inv_body),
                'requestId': request_id,
            }))
            return

        # ── Step 2: Generate invoice image ──
        try:
            img_payload = {
                'rawPath': f'/invoices/{invoice_id}/generate-image',
                'requestContext': {'http': {'method': 'POST'}},
                'pathParameters': {'invoiceId': invoice_id},
                'body': json.dumps({'invoiceId': invoice_id}),
            }
            img_response = lambda_client.invoke(
                FunctionName='wecare-invoice-engine',
                InvocationType='RequestResponse',
                Payload=json.dumps(img_payload),
            )
            img_result = json.loads(img_response['Payload'].read())
            img_body = json.loads(img_result.get('body', '{}'))
            image_url = img_body.get('imageUrl', '')
            logger.info(json.dumps({
                'event': 'invoice_image_generated',
                'invoiceId': invoice_id,
                'imageUrl': image_url,
                'requestId': request_id,
            }))
        except Exception as img_err:
            logger.error(json.dumps({
                'event': 'invoice_image_error',
                'invoiceId': invoice_id,
                'error': str(img_err),
                'requestId': request_id,
            }))

        # ── Step 3: Send invoice on WhatsApp ──
        if invoice_id and customer_phone:
            try:
                send_phone_id = phone_number_id or PHONE_NUMBER_ID_1
                send_payload = {
                    'rawPath': f'/invoices/{invoice_id}/send-whatsapp',
                    'requestContext': {'http': {'method': 'POST'}},
                    'pathParameters': {'invoiceId': invoice_id},
                    'body': json.dumps({
                        'invoiceId': invoice_id,
                        'toWhatsAppNumber': customer_phone,
                        'phoneNumberId': send_phone_id,
                    }),
                }
                lambda_client.invoke(
                    FunctionName='wecare-invoice-engine',
                    InvocationType='Event',  # Async
                    Payload=json.dumps(send_payload),
                )
                logger.info(json.dumps({
                    'event': 'invoice_whatsapp_triggered',
                    'invoiceId': invoice_id,
                    'toPhone': customer_phone,
                    'requestId': request_id,
                }))
            except Exception as send_err:
                logger.error(json.dumps({
                    'event': 'invoice_whatsapp_error',
                    'invoiceId': invoice_id,
                    'error': str(send_err),
                    'requestId': request_id,
                }))

        # ── Step 4: Generate PDF (async) ──
        try:
            pdf_payload = {
                'rawPath': f'/invoices/{invoice_id}/generate-pdf',
                'requestContext': {'http': {'method': 'POST'}},
                'pathParameters': {'invoiceId': invoice_id},
                'body': json.dumps({'invoiceId': invoice_id}),
            }
            lambda_client.invoke(
                FunctionName='wecare-invoice-engine',
                InvocationType='Event',
                Payload=json.dumps(pdf_payload),
            )
        except Exception as pdf_err:
            logger.error(json.dumps({
                'event': 'invoice_pdf_error',
                'invoiceId': invoice_id,
                'error': str(pdf_err),
                'requestId': request_id,
            }))

    except Exception as e:
        logger.error(json.dumps({
            'event': 'invoice_for_captured_error',
            'referenceId': reference_id,
            'error': str(e),
            'requestId': request_id,
        }))


def _check_and_notify_balance_due(recipient_id: str, paid_reference_id: str,
                                  phone_number_id: str, request_id: str) -> None:
    """After a payment is captured, check InvoicesTable for remaining pending dues.
    If found, auto-send the next payment link (sequential pay) and notify user.
    """
    try:
        clean_phone = recipient_id.replace('+', '').replace(' ', '').replace('-', '')
        last10 = clean_phone[-10:] if len(clean_phone) >= 10 else clean_phone

        # Query InvoicesTable for remaining pending invoices (source of truth)
        invoices_table = dynamodb.Table(INVOICES_TABLE)
        pending_statuses = ['created', 'pending_payment', 'sent']
        remaining = []

        scan_kwargs = {
            'FilterExpression': boto3.dynamodb.conditions.Attr('status').is_in(pending_statuses),
            'ConsistentRead': True,
        }
        while True:
            resp = invoices_table.scan(**scan_kwargs)
            for item in resp.get('Items', []):
                inv_phone = (item.get('customerPhone', '') or '').replace('+', '').replace(' ', '').replace('-', '')
                inv_ref = item.get('referenceId', '')
                inv_ps = item.get('paymentStatus', '')
                # Skip the just-paid invoice AND any invoice already captured/paid
                if inv_phone.endswith(last10) and inv_ref != paid_reference_id and inv_ps not in ('captured', 'paid', 'refunded'):
                    remaining.append(item)
            if 'LastEvaluatedKey' in resp:
                scan_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
            else:
                break

        if not remaining:
            # All clear — send congratulations
            contact = _get_contact_by_phone(recipient_id)
            contact_id = contact.get('id', '') if contact else ''
            contact_phone = contact.get('phone', f'+{clean_phone}') if contact else f'+{clean_phone}'
            payload = {
                'body': json.dumps({
                    'contactId': contact_id if contact_id else None,
                    'recipientPhone': contact_phone,
                    'content': PAY_MSG['all_clear'],
                    'phoneNumberId': phone_number_id or PHONE_NUMBER_ID_1,
                })
            }
            lambda_client.invoke(
                FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
                InvocationType='Event',
                Payload=json.dumps(payload)
            )
            return

        # Sort oldest first
        remaining.sort(key=lambda x: int(x.get('createdAt', 0)))

        # Build summary
        total_bal = sum(float(inv.get('total', 0)) for inv in remaining)
        summary_msg = PAY_MSG['next_due'].format(total=f'{total_bal:,.2f}')

        # Send summary text
        contact = _get_contact_by_phone(recipient_id)
        contact_id = contact.get('id', '') if contact else ''
        contact_phone = contact.get('phone', f'+{clean_phone}') if contact else f'+{clean_phone}'
        sending_phone_id = phone_number_id or PHONE_NUMBER_ID_1

        payload = {
            'body': json.dumps({
                'contactId': contact_id if contact_id else None,
                'recipientPhone': contact_phone,
                'content': summary_msg,
                'phoneNumberId': sending_phone_id,
            })
        }
        lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )

        # Auto-send payment link for the next (oldest) pending invoice
        next_inv = remaining[0]
        next_id = next_inv.get('invoiceId', '')
        try:
            inv_payload = {
                'rawPath': f'/invoices/{next_id}/send-payment-link',
                'requestContext': {'http': {'method': 'POST'}},
                'pathParameters': {'invoiceId': next_id},
                'body': json.dumps({
                    'invoiceId': next_id,
                    'phoneNumberId': sending_phone_id,
                }),
            }
            lambda_client.invoke(
                FunctionName='wecare-invoice-engine',
                InvocationType='Event',
                Payload=json.dumps(inv_payload),
            )
            logger.info(json.dumps({
                'event': 'next_payment_auto_sent',
                'invoiceId': next_id,
                'remainingCount': len(remaining),
                'requestId': request_id,
            }))
        except Exception as link_err:
            logger.warning(json.dumps({
                'event': 'next_payment_auto_send_error',
                'invoiceId': next_id,
                'error': str(link_err),
                'requestId': request_id,
            }))

        logger.info(json.dumps({
            'event': 'balance_due_notification_sent',
            'recipientId': recipient_id,
            'remainingDues': len(remaining),
            'totalBalance': total_bal,
            'requestId': request_id,
        }))
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'balance_due_check_error',
            'error': str(e),
            'requestId': request_id,
        }))


def _store_payment_record(reference_id: str, recipient_id: str, payment_status: str,
                          amount_value: int, amount_offset: int, currency: str,
                          transaction_id: str, transaction_type: str,
                          timestamp: int, request_id: str) -> None:
    """Store payment record in Messages table for tracking."""
    try:
        # Find contact by phone number
        contact = _get_contact_by_phone(recipient_id)
        contact_id = contact.get('id', '') if contact else ''
        
        payment_id = str(uuid.uuid4())
        now = int(time.time())
        expires_at = now + MESSAGE_TTL_SECONDS
        
        # Calculate actual amount
        actual_amount = amount_value / amount_offset if amount_offset else amount_value
        
        payment_record = {
            'id': payment_id,
            'messageId': payment_id,
            'contactId': contact_id,
            'channel': 'whatsapp',
            'direction': 'inbound',
            'messageType': 'payment',
            'content': f'Payment {payment_status}: ₹{actual_amount:.2f} ({currency})',
            'status': payment_status,
            'senderPhone': recipient_id,
            # Payment-specific fields
            'paymentReferenceId': reference_id,
            'paymentStatus': payment_status,
            'paymentAmount': Decimal(str(amount_value)),
            'paymentOffset': Decimal(str(amount_offset)),
            'paymentCurrency': currency,
            'transactionId': transaction_id,
            'transactionType': transaction_type,
            'timestamp': Decimal(str(timestamp)),
            'createdAt': Decimal(str(now)),
            'expiresAt': Decimal(str(expires_at)),
        }
        
        messages_table = dynamodb.Table(MESSAGES_TABLE)
        messages_table.put_item(Item={k: v for k, v in payment_record.items() if v is not None and v != ''})
        
        # Link payment to SubmitRequest if reference_id starts with WD-PAY- or SR- (legacy)
        if reference_id and (reference_id.startswith('WD-PAY-') or reference_id.startswith('SR-')):
            _update_submit_request_payment(reference_id, payment_status, transaction_id, request_id)
        
        logger.info(json.dumps({
            'event': 'payment_record_stored',
            'paymentId': payment_id,
            'referenceId': reference_id,
            'contactId': contact_id,
            'paymentStatus': payment_status,
            'amount': actual_amount,
            'requestId': request_id
        }))
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'payment_record_store_error',
            'referenceId': reference_id,
            'error': str(e),
            'requestId': request_id
        }))


def _update_submit_request_payment(reference_id: str, payment_status: str,
                                    transaction_id: str, request_id: str) -> None:
    """Update SubmitRequest record with payment status when payment webhook arrives."""
    try:
        table = dynamodb.Table(SUBMIT_REQUESTS_TABLE)
        now = int(time.time())
        # Query by paymentReferenceId GSI
        resp = table.query(
            IndexName='paymentReferenceId',
            KeyConditionExpression='paymentReferenceId = :ref',
            ExpressionAttributeValues={':ref': reference_id},
            Limit=1,
        )
        items = resp.get('Items', [])
        if items:
            submission_id = items[0]['id']
            table.update_item(
                Key={'id': submission_id},
                UpdateExpression='SET paymentStatus = :s, transactionId = :t, updatedAt = :u',
                ExpressionAttributeValues={
                    ':s': payment_status,
                    ':t': transaction_id,
                    ':u': Decimal(str(now)),
                },
            )
            logger.info(json.dumps({
                'event': 'submit_request_payment_linked',
                'submissionId': submission_id,
                'referenceId': reference_id,
                'paymentStatus': payment_status,
                'requestId': request_id,
            }))
        else:
            logger.warning(json.dumps({
                'event': 'submit_request_not_found_for_payment',
                'referenceId': reference_id,
                'requestId': request_id,
            }))
    except Exception as e:
        logger.error(json.dumps({
            'event': 'submit_request_payment_link_error',
            'referenceId': reference_id,
            'error': str(e),
            'requestId': request_id,
        }))


def _get_contact_by_phone(phone: str) -> Optional[Dict]:
    """Get contact by phone number using GSI for O(1) lookup."""
    try:
        contacts_table = dynamodb.Table(CONTACTS_TABLE)
        
        # Clean phone number - handle various formats
        clean_phone = phone.lstrip('+')
        phone_with_plus = f'+{clean_phone}'
        
        logger.info(json.dumps({
            'event': 'contact_lookup_by_phone',
            'originalPhone': phone,
            'cleanPhone': clean_phone,
            'phoneWithPlus': phone_with_plus
        }))
        
        # Use GSI query on phone-index for O(1) lookup
        for phone_variant in [phone_with_plus, clean_phone, phone]:
            try:
                response = contacts_table.query(
                    IndexName='phone-index',
                    KeyConditionExpression='phone = :phone',
                    ExpressionAttributeValues={':phone': phone_variant},
                    Limit=5
                )
                items = response.get('Items', [])
                # Filter out deleted contacts
                items = [i for i in items if not i.get('deletedAt')]
                if items:
                    logger.info(json.dumps({
                        'event': 'contact_lookup_result',
                        'phone': phone,
                        'foundCount': len(items),
                        'contactId': items[0].get('id', ''),
                        'method': 'gsi'
                    }))
                    return items[0]
            except Exception:
                pass  # GSI not ready, will fallback below
        
        # Fallback to scan if GSI not ready
        response = contacts_table.scan(
            FilterExpression='(phone = :phone1 OR phone = :phone2 OR phone = :phone3) AND (attribute_not_exists(deletedAt) OR deletedAt = :null)',
            ExpressionAttributeValues={
                ':phone1': clean_phone,
                ':phone2': phone_with_plus,
                ':phone3': phone,
                ':null': None
            },
            Limit=10
        )
        
        items = response.get('Items', [])
        
        logger.info(json.dumps({
            'event': 'contact_lookup_result',
            'phone': phone,
            'foundCount': len(items),
            'contactId': items[0].get('id', '') if items else None,
            'method': 'scan_fallback'
        }))
        
        return items[0] if items else None
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'contact_lookup_error',
            'phone': phone,
            'error': str(e)
        }))
        return None


def _lookup_payment_amount(reference_id: str, request_id: str) -> float:
    """
    Look up payment amount from original payment request in Messages table.
    This is a fallback when WhatsApp webhook doesn't include the amount.
    
    The original payment request message stores the amount in the content field
    or in a dedicated paymentAmount field.
    """
    try:
        messages_table = dynamodb.Table(MESSAGES_TABLE)
        
        # Sanitize reference_id for lookup
        sanitized_ref = _sanitize_reference_id(reference_id)
        
        # Extract just the ID part (without WD-PAY- or legacy WD prefix) for broader search
        id_part = sanitized_ref
        for pfx in ('WD-PAY-', 'WD-ORD-', 'WD'):
            if id_part.startswith(pfx):
                id_part = id_part[len(pfx):]
                break
        
        # Look for the original payment request message by reference_id
        # Search with multiple variations to handle format differences
        response = messages_table.scan(
            FilterExpression='paymentReferenceId = :ref1 OR paymentReferenceId = :ref2 OR contains(content, :id_part)',
            ExpressionAttributeValues={
                ':ref1': sanitized_ref,
                ':ref2': reference_id,  # Also try original format
                ':id_part': id_part
            },
            Limit=10
        )
        
        items = response.get('Items', [])
        
        logger.info(json.dumps({
            'event': 'payment_amount_lookup_result',
            'referenceId': reference_id,
            'sanitizedRef': sanitized_ref,
            'idPart': id_part,
            'foundCount': len(items),
            'requestId': request_id
        }))
        
        # Look for amount in the found records
        for item in items:
            # Check for paymentAmount field (stored in paise)
            payment_amount = item.get('paymentAmount')
            if payment_amount:
                offset = item.get('paymentOffset', 100)
                amount = float(payment_amount) / float(offset)
                logger.info(json.dumps({
                    'event': 'payment_amount_found_in_record',
                    'referenceId': reference_id,
                    'amount': amount,
                    'requestId': request_id
                }))
                return amount
            
            # Try to extract from content (e.g., "Payment request: ₹500.00")
            content = item.get('content', '')
            if '₹' in content:
                import re
                match = re.search(r'₹([\d,]+\.?\d*)', content)
                if match:
                    amount_str = match.group(1).replace(',', '')
                    amount = float(amount_str)
                    logger.info(json.dumps({
                        'event': 'payment_amount_extracted_from_content',
                        'referenceId': reference_id,
                        'amount': amount,
                        'content': content[:100],
                        'requestId': request_id
                    }))
                    return amount
        
        logger.warning(json.dumps({
            'event': 'payment_amount_not_found',
            'referenceId': reference_id,
            'requestId': request_id
        }))
        return 0.0
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'payment_amount_lookup_error',
            'referenceId': reference_id,
            'error': str(e),
            'requestId': request_id
        }))
        return 0.0


def _send_order_status_message(recipient_id: str, reference_id: str, 
                                order_status: str, amount: float, description: str,
                                request_id: str, phone_number_id: str = None) -> None:
    """
    Send order_status interactive message to confirm payment status.
    Uses the phone_number_id that received the original payment if available,
    otherwise falls back to PHONE_NUMBER_ID_1.
    """
    try:
        # Find contact by phone number
        contact = _get_contact_by_phone(recipient_id)
        
        if not contact:
            logger.warning(json.dumps({
                'event': 'order_status_no_contact',
                'recipientId': recipient_id,
                'referenceId': reference_id,
                'requestId': request_id,
                'note': 'Will try to send using phone number directly'
            }))
            # Create a minimal contact object with phone number
            # Format phone for WhatsApp: +918100330063
            formatted_phone = f'+{recipient_id}' if not recipient_id.startswith('+') else recipient_id
            contact = {'id': '', 'phone': formatted_phone}
        
        contact_id = contact.get('id', '')
        contact_phone = contact.get('phone', f'+{recipient_id}')
        
        # Build order_status payload - send directly to outbound Lambda
        # Use the phone number that received the original message, or fall back to default
        sending_phone_id = phone_number_id or PHONE_NUMBER_ID_1
        order_status_payload = {
            'body': json.dumps({
                'contactId': contact_id if contact_id else None,
                'recipientPhone': contact_phone,  # Fallback to phone if no contactId
                'phoneNumberId': sending_phone_id,
                'isOrderStatus': True,
                'orderStatusDetails': {
                    'reference_id': reference_id,
                    'order_status': order_status,
                    'amount': amount,  # Amount in rupees for display
                    'description': description
                }
            })
        }
        
        logger.info(json.dumps({
            'event': 'order_status_message_sending',
            'contactId': contact_id,
            'contactPhone': contact_phone,
            'referenceId': reference_id,
            'orderStatus': order_status,
            'amount': amount,
            'sendingPhoneId': sending_phone_id,
            'requestId': request_id
        }))
        
        # Invoke outbound Lambda to send order_status message
        response = lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',  # Async
            Payload=json.dumps(order_status_payload)
        )
        
        logger.info(json.dumps({
            'event': 'order_status_message_triggered',
            'contactId': contact_id,
            'contactPhone': contact_phone,
            'referenceId': reference_id,
            'orderStatus': order_status,
            'statusCode': response.get('StatusCode'),
            'requestId': request_id
        }))
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'order_status_message_error',
            'recipientId': recipient_id,
            'referenceId': reference_id,
            'error': str(e),
            'requestId': request_id
        }))


def _send_to_dlq(record: Dict, error: str, request_id: str) -> None:
    """Send failed message to inbound-dlq."""
    if not INBOUND_DLQ_URL:
        return
    
    try:
        sqs.send_message(
            QueueUrl=INBOUND_DLQ_URL,
            MessageBody=json.dumps({
                'originalRecord': record,
                'error': error,
                'timestamp': int(time.time()),
                'requestId': request_id
            }, default=str)
        )
    except Exception as e:
        logger.error(json.dumps({
            'event': 'dlq_send_error',
            'error': str(e),
            'requestId': request_id
        }))


CALLING_TABLE = os.environ.get('CALL_LOG_TABLE', 'base-wecare-digital-WhatsAppCallingTable')


def _forward_call_permission_to_calling_table(sender_phone: str, receiving_phone: str,
                                               aws_phone_number_id: str,
                                               interactive: Dict) -> None:
    """
    Forward a call_permission_reply interactive message to the WhatsApp Calling table.
    This lets the frontend/calling handler know that the user granted or denied
    permission for outbound calls.
    """
    try:
        cpr = interactive.get('call_permission_reply', {})
        permission = cpr.get('permission', cpr.get('status', ''))
        if not permission:
            permission = interactive.get('permission', 'unknown')

        now = int(time.time())
        table = dynamodb.Table(CALLING_TABLE)
        table.put_item(Item={
            'id': f"perm_{sender_phone}_{now}",
            'callId': f"perm_{sender_phone}_{now}",
            'phoneNumberId': aws_phone_number_id,
            'fromNumber': sender_phone,
            'toNumber': receiving_phone,
            'direction': 'USER_INITIATED',
            'eventType': 'permission_response',
            'status': f'permission_{permission}',
            'permission': permission,
            'createdAt': Decimal(str(now)),
            'ttl': Decimal(str(now + 90 * 24 * 60 * 60)),
        })
        logger.info(json.dumps({
            'event': 'call_permission_forwarded',
            'senderPhone': sender_phone,
            'permission': permission,
        }))
    except Exception as e:
        logger.error(f"Failed to forward call permission: {e}")


def _send_auto_reaction(contact_id: str, whatsapp_message_id: str, 
                        phone_number_id: str, request_id: str) -> None:
    """
    Send automatic thumbs up reaction to inbound message.
    Uses the same phone number that received the message.
    """
    if not whatsapp_message_id:
        return
    
    try:
        reaction_payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'isReaction': True,
                'reactionMessageId': whatsapp_message_id,
                'reactionEmoji': '\U0001F44D',  # Thumbs up
                'phoneNumberId': phone_number_id  # Use same phone that received
            })
        }
        
        response = lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(reaction_payload)
        )
        
        logger.info(json.dumps({
            'event': 'auto_reaction_triggered',
            'contactId': contact_id,
            'whatsappMessageId': whatsapp_message_id,
            'phoneNumberId': phone_number_id,
            'statusCode': response.get('StatusCode'),
            'requestId': request_id
        }))
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'auto_reaction_error',
            'contactId': contact_id,
            'error': str(e),
            'requestId': request_id
        }))


def _send_ai_auto_reply(contact_id: str, content: str, phone_number_id: str, request_id: str) -> None:
    """
    Send AI-generated auto-reply to WhatsApp.
    Uses the same phone number that received the message.
    """
    if not content or not content.strip() or not contact_id:
        return
    
    try:
        reply_payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'content': content,
                'phoneNumberId': phone_number_id
            })
        }
        
        response = lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',  # Async - don't wait for response
            Payload=json.dumps(reply_payload)
        )
        
        logger.info(json.dumps({
            'event': 'ai_auto_reply_triggered',
            'contactId': contact_id,
            'contentLength': len(content),
            'phoneNumberId': phone_number_id,
            'statusCode': response.get('StatusCode'),
            'requestId': request_id
        }))
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'ai_auto_reply_error',
            'contactId': contact_id,
            'error': str(e),
            'requestId': request_id
        }))


def _send_submit_request_flow(contact_id: str, phone_number_id: str, sender_phone: str, request_id: str, flow_config: Dict = None) -> None:
    """
    Send the Submit Request WhatsApp Flow to the user.
    Passes sender's phone number so the endpoint can fetch their orders.
    Message content is configurable via flow_config (from SystemConfigTable).
    """
    try:
        # Resolve flow ID: config override > env var
        flow_id = (flow_config or {}).get('flowId', '') or SUBMIT_REQUEST_FLOW_ID
        msg = (flow_config or {}).get('message', {})

        # Encode phone in flow_token so the flow-data endpoint can extract it
        # during INIT (data_exchange mode doesn't pass custom data in the message)
        flow_token = f'sr-{uuid.uuid4()}-ph-{sender_phone}'
        interactive_data = {
            'body': msg.get('body', '\U0001f447Please use the self-service option below. Once we receive it, we\u2019ll review it and follow up if needed.'),
            'footer': msg.get('footer', 'WECARE.DIGITAL'),
            'flowId': flow_id,
            'flowCta': msg.get('flowCta', 'Submit Request'),
            'flowAction': 'data_exchange',
            'flowToken': flow_token,
        }
        # Only include header if explicitly set in config
        header_val = msg.get('header', '')
        if header_val:
            interactive_data['header'] = header_val

        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'phoneNumberId': phone_number_id,
                'isInteractive': True,
                'interactiveType': 'flow',
                'interactiveData': interactive_data,
            })
        }

        response = lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )

        logger.info(json.dumps({
            'event': 'submit_request_flow_sent',
            'contactId': contact_id,
            'senderPhone': sender_phone,
            'flowId': flow_id,
            'flowToken': flow_token,
            'statusCode': response.get('StatusCode'),
            'requestId': request_id
        }))

    except Exception as e:
        logger.error(json.dumps({
            'event': 'submit_request_flow_error',
            'contactId': contact_id,
            'error': str(e),
            'requestId': request_id
        }))


def _send_interactive_list(contact_id: str, phone_number_id: str, list_config: Dict, request_id: str) -> None:
    """
    Send a WhatsApp interactive list message.
    list_config should have: header, body, footer, buttonText, sections.
    """
    if not contact_id or not list_config.get('sections'):
        return

    try:
        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'phoneNumberId': phone_number_id,
                'isInteractive': True,
                'interactiveType': 'list',
                'interactiveData': {
                    'header': list_config.get('header', ''),
                    'body': list_config.get('body', 'Please select an option'),
                    'footer': list_config.get('footer', ''),
                    'buttonText': list_config.get('buttonText', 'Menu'),
                    'sections': list_config.get('sections', []),
                }
            })
        }

        response = lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )

        logger.info(json.dumps({
            'event': 'interactive_list_sent',
            'contactId': contact_id,
            'buttonText': list_config.get('buttonText', 'Menu'),
            'sectionsCount': len(list_config.get('sections', [])),
            'statusCode': response.get('StatusCode'),
            'requestId': request_id
        }))

    except Exception as e:
        logger.error(json.dumps({
            'event': 'interactive_list_error',
            'contactId': contact_id,
            'error': str(e),
            'requestId': request_id
        }))


def _send_cta_button(contact_id: str, phone_number_id: str, cta_text: str, cta_url: str, request_id: str) -> None:
    """Send a WhatsApp CTA URL button message."""
    if not contact_id or not cta_url:
        return

    try:
        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'phoneNumberId': phone_number_id,
                'isInteractive': True,
                'interactiveType': 'cta_url',
                'interactiveData': {
                    'body': cta_text,
                    'buttons': [{'type': 'url', 'title': cta_text, 'url': cta_url}],
                }
            })
        }

        response = lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )

        logger.info(json.dumps({
            'event': 'cta_button_sent',
            'contactId': contact_id,
            'ctaText': cta_text,
            'ctaUrl': cta_url,
            'statusCode': response.get('StatusCode'),
            'requestId': request_id
        }))

    except Exception as e:
        logger.error(json.dumps({
            'event': 'cta_button_error',
            'contactId': contact_id,
            'error': str(e),
            'requestId': request_id
        }))


def _send_reply_buttons(contact_id: str, phone_number_id: str, button_config: Dict, request_id: str) -> None:
    """
    Send WhatsApp interactive reply buttons (max 3 buttons).
    button_config: {header, body, footer, buttons: [{id, title}]}
    """
    if not contact_id or not button_config.get('buttons'):
        return

    try:
        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'phoneNumberId': phone_number_id,
                'isInteractive': True,
                'interactiveType': 'button',
                'interactiveData': {
                    'header': button_config.get('header', ''),
                    'body': button_config.get('body', 'Please select an option'),
                    'footer': button_config.get('footer', ''),
                    'buttons': button_config.get('buttons', []),
                }
            })
        }

        response = lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )

        logger.info(json.dumps({
            'event': 'reply_buttons_sent',
            'contactId': contact_id,
            'buttonCount': len(button_config.get('buttons', [])),
            'statusCode': response.get('StatusCode'),
            'requestId': request_id
        }))

    except Exception as e:
        logger.error(json.dumps({
            'event': 'reply_buttons_error',
            'contactId': contact_id,
            'error': str(e),
            'requestId': request_id
        }))


def _send_audio_response(contact_id: str, phone_number_id: str, text: str, language: str, request_id: str) -> None:
    """
    Invoke the whatsapp-voice Lambda to generate TTS audio and send it.
    Called when user has audioEnabled=True.
    """
    if not contact_id or not text or len(text.strip()) < 5:
        return

    # Map language preference to Polly voice/language code
    # Languages with native Polly voices use them; others use best fallback
    LANG_TO_POLLY = {
        # ── Popular (Indian + English) ──
        'english': ('Kajal', 'en-IN'),
        'hindi': ('Kajal', 'hi-IN'),
        'hinglish': ('Kajal', 'hi-IN'),
        'bengali': ('Kajal', 'hi-IN'),       # No native voice → Hindi fallback
        'tamil': ('Kajal', 'en-IN'),         # No native voice → English fallback
        'telugu': ('Kajal', 'en-IN'),        # No native voice
        'gujarati': ('Kajal', 'hi-IN'),      # No native voice → Hindi fallback
        'marathi': ('Kajal', 'hi-IN'),       # No native voice → Hindi fallback
        'kannada': ('Kajal', 'en-IN'),       # No native voice
        'malayalam': ('Kajal', 'en-IN'),     # No native voice
        # ── Asian ──
        'chinese': ('Zhiyu', 'cmn-CN'),
        'japanese': ('Kazuha', 'ja-JP'),
        'korean': ('Seoyeon', 'ko-KR'),
        'thai': ('Kajal', 'en-IN'),          # No native voice
        'vietnamese': ('Kajal', 'en-IN'),    # No native voice
        'indonesian': ('Kajal', 'en-IN'),    # No native voice
        'sinhala': ('Kajal', 'en-IN'),       # No native voice
        # ── Middle East ──
        'arabic': ('Hala', 'arb'),
        'turkish': ('Burcu', 'tr-TR'),
        'russian': ('Tatyana', 'ru-RU'),
        'urdu': ('Kajal', 'hi-IN'),          # No native voice → Hindi fallback
        'punjabi': ('Kajal', 'hi-IN'),       # No native voice → Hindi fallback
        # ── European ──
        'french': ('Lea', 'fr-FR'),
        'spanish': ('Lupe', 'es-US'),
        'portuguese': ('Camila', 'pt-BR'),
    }
    voice_id, lang_code = LANG_TO_POLLY.get(language.lower(), ('Kajal', 'en-IN'))

    try:
        # The voice Lambda expects an HTTP-style event with POST /whatsapp-voice/tts
        tts_payload = {
            'requestContext': {'http': {'method': 'POST'}},
            'rawPath': '/whatsapp-voice/tts',
            'body': json.dumps({
                'contactId': contact_id,
                'messageText': text[:500],  # Polly limit
                'voiceId': voice_id,
                'languageCode': lang_code,
                'engine': 'neural',
                'phoneNumberId': phone_number_id,
            })
        }

        response = lambda_client.invoke(
            FunctionName=WHATSAPP_VOICE_FUNCTION,
            InvocationType='Event',  # Async — don't block
            Payload=json.dumps(tts_payload)
        )

        logger.info(json.dumps({
            'event': 'audio_response_triggered',
            'contactId': contact_id,
            'voiceId': voice_id,
            'langCode': lang_code,
            'textLength': len(text),
            'statusCode': response.get('StatusCode'),
            'requestId': request_id
        }))

    except Exception as e:
        logger.error(json.dumps({
            'event': 'audio_response_error',
            'contactId': contact_id,
            'error': str(e),
            'requestId': request_id
        }))


def _send_payment_request(contact_id: str, phone_number_id: str, amount: float, request_id: str,
                          item_name: str = 'Services/Goods', gst_rate: float = 18,
                          shipping: float = 49, sender_phone: str = '',
                          quantity: int = 1, discount: float = 0,
                          handling: float = 0,
                          items: list = None,
                          payment_purpose: str = '', due_ref: str = '',
                          order_id: str = 'Offline', customer_name: str = '',
                          customer_phone: str = '', customer_email: str = '',
                          shipping_address: str = '', billing_address: str = '',
                          pay_for: str = 'self') -> None:
    """Send WhatsApp Pay order_details message with per-item GST and payment log.
    
    Supports multi-item via `items` list of dicts:
      [{'name': str, 'amount_paise': int, 'quantity': int, 'gst_rate': float}]
    Falls back to single item_name/amount/quantity/gst_rate if items not provided.
    """
    if not contact_id or amount <= 0:
        return

    try:
        reference_id = f"WD-PAY-{uuid.uuid4().hex[:8].upper()}"
        qty = max(1, int(quantity))
        
        # Build items array for order_details with per-item GST
        if items and len(items) > 0:
            order_items = []
            subtotal_paise = 0
            gst_paise = 0
            for i, item in enumerate(items):
                i_amount = int(item.get('amount_paise', int(amount * 100)))
                i_qty = int(item.get('quantity', 1))
                i_name = item.get('name', item_name)
                i_gst_rate = float(item.get('gst_rate', gst_rate))
                i_line_total = i_amount * i_qty
                subtotal_paise += i_line_total
                gst_paise += int(round(i_line_total * i_gst_rate / 100 / 100, 2) * 100)
                order_items.append({
                    'retailer_id': f'ITEM_{i+1}',
                    'name': i_name,
                    'amount': {'value': i_amount, 'offset': 100},
                    'quantity': i_qty,
                    'gstRate': i_gst_rate,
                })
        else:
            amount_in_paise = int(amount * 100)
            subtotal_paise = amount_in_paise * qty
            gst_paise = int(round(subtotal_paise * gst_rate / 100 / 100, 2) * 100)
            order_items = [{
                'retailer_id': 'ITEM_MAIN',
                'name': item_name,
                'amount': {'value': amount_in_paise, 'offset': 100},
                'quantity': qty,
                'gstRate': gst_rate,
            }]
        
        discount_paise = int(discount * 100)
        shipping_paise = int(shipping * 100)
        handling_paise = int(handling * 100)

        # Build payload matching outbound handler's isInteractivePayment format
        payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'phoneNumberId': phone_number_id,
                'isInteractivePayment': True,
                'orderDetails': {
                    'reference_id': reference_id,
                    'type': 'digital-goods',
                    'currency': 'INR',
                    'itemName': order_items[0]['name'] if order_items else item_name,
                    'quantity': qty,
                    'gstRate': gst_rate,
                    'gstin': '19AADFW7431N1ZK',
                    'orderId': order_id or 'Offline',
                    'order': {
                        'status': 'pending',
                        'items': order_items,
                        'subtotal': {'value': subtotal_paise, 'offset': 100},
                        'discount': {'value': discount_paise, 'offset': 100, 'description': 'Promo'},
                        'shipping': {'value': shipping_paise, 'offset': 100, 'description': 'Express'},
                        'handling': {'value': handling_paise, 'offset': 100, 'description': 'Handling'},
                        'tax': {'value': gst_paise, 'offset': 100, 'description': f'GSTIN: 19AADFW7431N1ZK'},
                    },
                }
            })
        }

        response = lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(payload)
        )

        # Calculate totals for logging
        conv_base_paise = int(round(subtotal_paise * 0.02 / 100, 2) * 100)
        conv_gst_paise = int(round(conv_base_paise * 0.18 / 100, 2) * 100)
        conv_total_paise = conv_base_paise + conv_gst_paise
        total_paise = subtotal_paise - discount_paise + gst_paise + shipping_paise + handling_paise + conv_total_paise

        # Store payment request with full GST breakdown for accounting
        try:
            messages_table = dynamodb.Table(MESSAGES_TABLE)
            now = int(time.time())
            # Build item summary for content field
            item_summary = ' | '.join([f"{it['name']} x{it['quantity']} @₹{it['amount']['value']/100:.2f}" for it in order_items])
            messages_table.put_item(Item={k: v for k, v in {
                'id': str(uuid.uuid4()),
                'messageId': reference_id,
                'contactId': contact_id,
                'channel': 'whatsapp',
                'direction': 'outbound',
                'messageType': 'payment_request',
                'content': f'Payment: {item_summary} | GST {gst_rate}%: ₹{gst_paise/100:.2f} | Promo: -₹{discount:.2f} | Ship: ₹{shipping:.2f} | Handling: ₹{handling:.2f} | Total: ₹{total_paise/100:.2f}',
                'paymentReferenceId': reference_id,
                'paymentAmount': Decimal(str(subtotal_paise)),
                'paymentOffset': Decimal('100'),
                'paymentCurrency': 'INR',
                'paymentItemName': order_items[0]['name'] if order_items else item_name,
                'paymentItemCount': len(order_items),
                'paymentQuantity': qty,
                'paymentSubtotal': Decimal(str(subtotal_paise)),
                'paymentDiscount': Decimal(str(discount_paise)),
                'paymentGstRate': Decimal(str(gst_rate)),
                'paymentGstAmount': Decimal(str(gst_paise)),
                'paymentShipping': Decimal(str(shipping_paise)),
                'paymentHandling': Decimal(str(handling_paise)),
                'paymentConvFee': Decimal(str(conv_total_paise)),
                'paymentTotal': Decimal(str(total_paise)),
                'paymentGstin': '19AADFW7431N1ZK',
                'paymentSource': 'whatsapp_bot',
                'paymentPurpose': payment_purpose or '',
                'paymentDueRef': due_ref or '',
                'paymentOrderId': order_id or 'Offline',
                'paymentCustomerName': customer_name or '',
                'paymentCustomerPhone': customer_phone or sender_phone,
                'paymentCustomerEmail': customer_email or '',
                'paymentShippingAddress': shipping_address or '',
                'paymentBillingAddress': billing_address or '',
                'paymentPayFor': pay_for or 'self',
                'status': 'pending',
                'senderPhone': sender_phone,
                'createdAt': Decimal(str(now)),
                'expiresAt': Decimal(str(now + 86400 * 30)),
            }.items() if v is not None and v != ''})
        except Exception as store_err:
            logger.warning(json.dumps({
                'event': 'payment_request_store_error',
                'error': str(store_err),
                'referenceId': reference_id,
                'requestId': request_id
            }))

        # Save pending payment ref to ConversationHistoryTable for due check
        if sender_phone:
            try:
                from hashlib import sha256
                clean_phone = sender_phone.replace('+', '').replace(' ', '').replace('-', '')
                ph = sha256(clean_phone.encode()).hexdigest()[:32]
                conv_table = dynamodb.Table(os.environ.get('CONVERSATION_HISTORY_TABLE', 'base-wecare-digital-ConversationHistoryTable'))
                conv_table.update_item(
                    Key={'phoneHash': ph},
                    UpdateExpression='SET lastPaymentRef = :ref, lastPaymentAmount = :amt, lastPaymentStatus = :s, lastPaymentAt = :t',
                    ExpressionAttributeValues={
                        ':ref': reference_id,
                        ':amt': Decimal(str(subtotal_paise / 100)),
                        ':s': 'pending',
                        ':t': Decimal(str(int(time.time()))),
                    }
                )
            except Exception as conv_err:
                logger.warning(json.dumps({
                    'event': 'payment_conv_update_error',
                    'error': str(conv_err),
                    'requestId': request_id
                }))

        logger.info(json.dumps({
            'event': 'payment_request_sent',
            'contactId': contact_id,
            'referenceId': reference_id,
            'itemCount': len(order_items),
            'subtotal': subtotal_paise / 100,
            'discount': discount,
            'gstRate': gst_rate,
            'gstAmount': gst_paise / 100,
            'shipping': shipping,
            'handling': handling,
            'convFee': conv_total_paise / 100,
            'total': total_paise / 100,
            'orderId': order_id or 'Offline',
            'source': 'whatsapp_bot',
            'statusCode': response.get('StatusCode'),
            'requestId': request_id
        }))

    except Exception as e:
        logger.error(json.dumps({
            'event': 'payment_request_error',
            'contactId': contact_id,
            'amount': amount,
            'error': str(e),
            'requestId': request_id
        }))


# ============================================================================
# POS INVOICE IMAGE GENERATOR (pure Python PNG — zero external dependencies)
# ============================================================================

# Minimal 5x7 bitmap font for ASCII 32-126 (space to ~)
# Each char is 5 pixels wide, 7 pixels tall, stored as 7 bytes (each byte = 5-bit row)
_FONT_5x7 = {
    32: [0,0,0,0,0,0,0], 33: [4,4,4,4,0,0,4], 34: [10,10,0,0,0,0,0],
    35: [10,31,10,10,31,10,0], 36: [4,15,20,14,5,30,4], 37: [24,25,2,4,8,19,3],
    38: [8,20,20,8,21,18,13], 39: [4,4,0,0,0,0,0], 40: [2,4,8,8,8,4,2],
    41: [8,4,2,2,2,4,8], 42: [0,4,21,14,21,4,0], 43: [0,4,4,31,4,4,0],
    44: [0,0,0,0,0,4,8], 45: [0,0,0,31,0,0,0], 46: [0,0,0,0,0,0,4],
    47: [0,1,2,4,8,16,0], 48: [14,17,19,21,25,17,14], 49: [4,12,4,4,4,4,14],
    50: [14,17,1,2,4,8,31], 51: [14,17,1,6,1,17,14], 52: [2,6,10,18,31,2,2],
    53: [31,16,30,1,1,17,14], 54: [6,8,16,30,17,17,14], 55: [31,1,2,4,8,8,8],
    56: [14,17,17,14,17,17,14], 57: [14,17,17,15,1,2,12], 58: [0,0,4,0,0,4,0],
    59: [0,0,4,0,0,4,8], 60: [1,2,4,8,4,2,1], 61: [0,0,31,0,31,0,0],
    62: [16,8,4,2,4,8,16], 63: [14,17,1,2,4,0,4], 64: [14,17,23,21,23,16,14],
    65: [14,17,17,31,17,17,17], 66: [30,17,17,30,17,17,30], 67: [14,17,16,16,16,17,14],
    68: [30,17,17,17,17,17,30], 69: [31,16,16,30,16,16,31], 70: [31,16,16,30,16,16,16],
    71: [14,17,16,23,17,17,14], 72: [17,17,17,31,17,17,17], 73: [14,4,4,4,4,4,14],
    74: [7,2,2,2,2,18,12], 75: [17,18,20,24,20,18,17], 76: [16,16,16,16,16,16,31],
    77: [17,27,21,21,17,17,17], 78: [17,25,21,21,21,19,17], 79: [14,17,17,17,17,17,14],
    80: [30,17,17,30,16,16,16], 81: [14,17,17,17,21,18,13], 82: [30,17,17,30,20,18,17],
    83: [14,17,16,14,1,17,14], 84: [31,4,4,4,4,4,4], 85: [17,17,17,17,17,17,14],
    86: [17,17,17,17,10,10,4], 87: [17,17,17,21,21,21,10], 88: [17,17,10,4,10,17,17],
    89: [17,17,10,4,4,4,4], 90: [31,1,2,4,8,16,31],
    91: [14,8,8,8,8,8,14], 92: [0,16,8,4,2,1,0], 93: [14,2,2,2,2,2,14],
    94: [4,10,17,0,0,0,0], 95: [0,0,0,0,0,0,31], 96: [8,4,0,0,0,0,0],
    97: [0,0,14,1,15,17,15], 98: [16,16,30,17,17,17,30], 99: [0,0,14,17,16,17,14],
    100: [1,1,15,17,17,17,15], 101: [0,0,14,17,31,16,14], 102: [6,9,8,28,8,8,8],
    103: [0,0,15,17,15,1,14], 104: [16,16,30,17,17,17,17], 105: [4,0,12,4,4,4,14],
    106: [2,0,6,2,2,18,12], 107: [16,16,18,20,24,20,18], 108: [12,4,4,4,4,4,14],
    109: [0,0,26,21,21,21,17], 110: [0,0,30,17,17,17,17], 111: [0,0,14,17,17,17,14],
    112: [0,0,30,17,30,16,16], 113: [0,0,15,17,15,1,1], 114: [0,0,22,25,16,16,16],
    115: [0,0,15,16,14,1,30], 116: [8,8,28,8,8,9,6], 117: [0,0,17,17,17,17,15],
    118: [0,0,17,17,17,10,4], 119: [0,0,17,17,21,21,10], 120: [0,0,17,10,4,10,17],
    121: [0,0,17,17,15,1,14], 122: [0,0,31,2,4,8,31],
    123: [3,4,4,8,4,4,3], 124: [4,4,4,4,4,4,4], 125: [24,4,4,2,4,4,24],
    126: [0,0,8,21,2,0,0],
}
# Special chars mapped to ASCII equivalents
_CHAR_MAP = {0x20B9: ord('R'), 0x2500: ord('-'), 0x2502: ord('|'), 0x2714: ord('*'),
             0x274C: ord('x'), 0x2705: ord('*')}


def _decode_png_pixels(png_bytes: bytes):
    """Minimal pure-Python PNG decoder. Returns (width, height, rows) where rows is list of lists of (R,G,B,A)."""
    import struct as _struct
    import zlib as _zlib

    if png_bytes[:8] != b'\x89PNG\r\n\x1a\n':
        return None, None, None

    pos = 8
    width = height = bit_depth = color_type = 0
    idat_chunks = []
    palette = []

    while pos < len(png_bytes):
        length = _struct.unpack('>I', png_bytes[pos:pos+4])[0]
        chunk_type = png_bytes[pos+4:pos+8]
        chunk_data = png_bytes[pos+8:pos+8+length]
        pos += 12 + length

        if chunk_type == b'IHDR':
            width, height, bit_depth, color_type = _struct.unpack('>IIBB', chunk_data[:10])
        elif chunk_type == b'PLTE':
            for i in range(0, len(chunk_data), 3):
                palette.append((chunk_data[i], chunk_data[i+1], chunk_data[i+2]))
        elif chunk_type == b'IDAT':
            idat_chunks.append(chunk_data)
        elif chunk_type == b'IEND':
            break

    raw = _zlib.decompress(b''.join(idat_chunks))

    # Determine bytes per pixel
    if color_type == 0:
        bpp = 1  # grayscale
    elif color_type == 2:
        bpp = 3  # RGB
    elif color_type == 3:
        bpp = 1  # indexed
    elif color_type == 4:
        bpp = 2  # grayscale + alpha
    elif color_type == 6:
        bpp = 4  # RGBA
    else:
        return None, None, None

    stride = width * bpp
    rows = []
    prev_row = bytearray(stride)

    offset = 0
    for y in range(height):
        filter_type = raw[offset]
        offset += 1
        cur_row = bytearray(raw[offset:offset + stride])
        offset += stride

        # Reconstruct filtered row
        for i in range(stride):
            a = cur_row[i - bpp] if i >= bpp else 0
            b = prev_row[i]
            c = prev_row[i - bpp] if i >= bpp else 0
            if filter_type == 1:
                cur_row[i] = (cur_row[i] + a) & 0xFF
            elif filter_type == 2:
                cur_row[i] = (cur_row[i] + b) & 0xFF
            elif filter_type == 3:
                cur_row[i] = (cur_row[i] + (a + b) // 2) & 0xFF
            elif filter_type == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                cur_row[i] = (cur_row[i] + pr) & 0xFF

        # Convert to RGBA tuples
        pixel_row = []
        for x in range(width):
            idx = x * bpp
            if color_type == 0:
                v = cur_row[idx]
                pixel_row.append((v, v, v, 255))
            elif color_type == 2:
                pixel_row.append((cur_row[idx], cur_row[idx+1], cur_row[idx+2], 255))
            elif color_type == 3:
                ci = cur_row[idx]
                if ci < len(palette):
                    r, g, b = palette[ci]
                    pixel_row.append((r, g, b, 255))
                else:
                    pixel_row.append((0, 0, 0, 255))
            elif color_type == 4:
                v, a = cur_row[idx], cur_row[idx+1]
                pixel_row.append((v, v, v, a))
            elif color_type == 6:
                pixel_row.append((cur_row[idx], cur_row[idx+1], cur_row[idx+2], cur_row[idx+3]))

        rows.append(pixel_row)
        prev_row = cur_row

    return width, height, rows


def _render_text_to_png(lines: list, scale: int = 2, logo_pixels=None, logo_w: int = 0, logo_h: int = 0) -> bytes:
    """Render lines of text to a PNG image using a 5x7 bitmap font. Optionally composites a logo at top center. Returns PNG bytes."""
    import struct as _struct
    import zlib as _zlib
    import io as _io

    char_w, char_h = 6 * scale, 9 * scale
    pad_x, pad_y = 12 * scale, 8 * scale
    max_cols = max((len(l) for l in lines), default=1)
    img_w = max_cols * char_w + pad_x * 2
    img_h = len(lines) * char_h + pad_y * 2

    # If logo, add space at top
    logo_offset_y = 0
    if logo_pixels and logo_h > 0:
        # Scale logo to fit ~60% of receipt width, max 80px tall
        target_w = int(img_w * 0.4)
        logo_scale = min(target_w / max(logo_w, 1), 80 / max(logo_h, 1), 1.0)
        scaled_lw = int(logo_w * logo_scale)
        scaled_lh = int(logo_h * logo_scale)
        logo_offset_y = scaled_lh + pad_y
        img_h += logo_offset_y

    # Create RGBA pixel buffer (white background)
    pixels = bytearray([255, 255, 255, 255] * (img_w * img_h))

    # Composite logo at top center
    if logo_pixels and logo_h > 0 and logo_offset_y > 0:
        logo_x_start = (img_w - scaled_lw) // 2
        for ly in range(scaled_lh):
            src_y = int(ly / logo_scale)
            if src_y >= logo_h:
                src_y = logo_h - 1
            for lx in range(scaled_lw):
                src_x = int(lx / logo_scale)
                if src_x >= logo_w:
                    src_x = logo_w - 1
                r, g, b, a = logo_pixels[src_y][src_x]
                px = logo_x_start + lx
                py = pad_y + ly
                if 0 <= px < img_w and 0 <= py < img_h and a > 0:
                    idx = (py * img_w + px) * 4
                    if a == 255:
                        pixels[idx] = r
                        pixels[idx+1] = g
                        pixels[idx+2] = b
                        pixels[idx+3] = 255
                    else:
                        # Alpha blend
                        af = a / 255.0
                        pixels[idx] = int(r * af + pixels[idx] * (1 - af))
                        pixels[idx+1] = int(g * af + pixels[idx+1] * (1 - af))
                        pixels[idx+2] = int(b * af + pixels[idx+2] * (1 - af))
                        pixels[idx+3] = 255

    # Render text
    for row_idx, line in enumerate(lines):
        for col_idx, ch in enumerate(line):
            code = ord(ch)
            code = _CHAR_MAP.get(code, code)
            glyph = _FONT_5x7.get(code, _FONT_5x7.get(63))
            if not glyph:
                continue
            bx = pad_x + col_idx * char_w
            by = pad_y + logo_offset_y + row_idx * char_h
            for gy, row_bits in enumerate(glyph):
                for gx in range(5):
                    if row_bits & (1 << (4 - gx)):
                        for sy in range(scale):
                            for sx in range(scale):
                                px = bx + gx * scale + sx
                                py = by + gy * scale + sy
                                if 0 <= px < img_w and 0 <= py < img_h:
                                    idx = (py * img_w + px) * 4
                                    pixels[idx] = 0
                                    pixels[idx+1] = 0
                                    pixels[idx+2] = 0
                                    pixels[idx+3] = 255

    # Encode as PNG (RGBA, 8-bit)
    def _png_chunk(chunk_type, data):
        c = chunk_type + data
        return _struct.pack('>I', len(data)) + c + _struct.pack('>I', _zlib.crc32(c) & 0xFFFFFFFF)

    raw_rows = b''
    for y in range(img_h):
        raw_rows += b'\x00' + bytes(pixels[y * img_w * 4:(y + 1) * img_w * 4])

    buf = _io.BytesIO()
    buf.write(b'\x89PNG\r\n\x1a\n')
    # color_type=6 = RGBA
    buf.write(_png_chunk(b'IHDR', _struct.pack('>IIBBBBB', img_w, img_h, 8, 6, 0, 0, 0)))
    buf.write(_png_chunk(b'IDAT', _zlib.compress(raw_rows, 9)))
    buf.write(_png_chunk(b'IEND', b''))
    return buf.getvalue()


def _build_invoice_lines(ref_id: str, pay_ref: str, item_name: str, unit_price: float, qty: int,
                         gst_rate: float, shipping: float, discount: float,
                         sender_phone: str, purpose: str, due_ref: str,
                         paid_at: str = '', order_id: str = 'Offline',
                         customer_name: str = '', customer_phone: str = '',
                         customer_email: str = '', shipping_address: str = '',
                         billing_address: str = '', pay_for: str = 'self') -> list:
    """Build POS receipt text lines for the invoice."""
    import datetime
    if paid_at:
        date_str = paid_at.split(' ')[0] if ' ' in paid_at else paid_at
        time_str = paid_at.split(' ')[1] if ' ' in paid_at else ''
    else:
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
        date_str = now.strftime('%d-%m-%Y')
        time_str = now.strftime('%H:%M:%S')

    subtotal = unit_price * qty
    after_promo = subtotal - discount
    gst_amt = round(after_promo * gst_rate / 100, 2)
    half_rate = gst_rate / 2
    cgst = round(gst_amt / 2, 2)
    sgst = round(gst_amt / 2, 2)
    conv_base = round(after_promo * 0.02, 2)
    conv_gst = round(conv_base * 0.18, 2)
    conv_fee = round(conv_base + conv_gst, 2)
    total = round(after_promo + gst_amt + shipping + conv_fee, 2)

    W = 42  # receipt width in chars
    sep = '-' * W
    dsep = '=' * W

    def center(t):
        return t.center(W)

    def lr(left, right):
        space = W - len(left) - len(right)
        return left + ' ' * max(space, 1) + right

    def fmt(v):
        return f'{v:,.2f}'

    lines = []
    # Header — logo will be composited above this
    lines.append('')
    lines.append('')
    lines.append('')  # space for logo
    lines.append(center('WECARE.DIGITAL'))
    lines.append(center('GSTIN: 19AADFW7431N1ZK'))
    lines.append(center('The W.B.S.I.D.C. Building'))
    lines.append(center('Unit 1/20, 81/2/7 Phears Ln'))
    lines.append(center('Kolkata, WB 700012'))
    lines.append(center('Email: one@wecare.digital'))
    lines.append(center('Phone: +919330994400'))
    lines.append(dsep)
    lines.append(center('TAX INVOICE'))
    lines.append(sep)
    lines.append(lr(f'Inv: {ref_id}', f'Date: {date_str}'))
    lines.append(lr(f'Pay Ref: {pay_ref}', f'Time: {time_str}'))
    lines.append(f'Order: {order_id}')
    lines.append(sep)
    # Customer details
    lines.append(center('BILL TO'))
    if customer_name:
        lines.append(f'Name: {customer_name[:30]}')
    cust_ph = customer_phone or sender_phone
    cust_ph_display = cust_ph[-10:] if len(cust_ph) > 10 else cust_ph
    lines.append(f'Phone: {cust_ph_display}')
    if customer_email:
        lines.append(f'Email: {customer_email[:30]}')
    if billing_address:
        # Wrap long address
        addr = billing_address[:60]
        lines.append(f'Addr: {addr}')
    if pay_for == 'other':
        paid_by = sender_phone[-10:] if len(sender_phone) > 10 else sender_phone
        lines.append(f'Paid By: {paid_by}')
    lines.append(sep)
    lines.append(center('SHIP TO'))
    if shipping_address:
        lines.append(f'{shipping_address[:42]}')
    else:
        lines.append('Same as billing')
    if purpose:
        lines.append(f'Purpose: {purpose[:30]}')
    if due_ref:
        lines.append(f'Due Ref: {due_ref}')
    lines.append(sep)
    lines.append(lr('ITEM', 'AMOUNT'))
    lines.append(sep)
    item_display = item_name[:24]
    lines.append(f'{item_display}')
    lines.append(lr(f'  Rs.{fmt(unit_price)} x {qty}', f'Rs.{fmt(subtotal)}'))
    lines.append(sep)
    lines.append(lr('Subtotal:', f'Rs.{fmt(subtotal)}'))
    if discount > 0:
        lines.append(lr('Promo Discount:', f'-Rs.{fmt(discount)}'))
    lines.append(lr(f'CGST @{half_rate:.1f}%:', f'Rs.{fmt(cgst)}'))
    lines.append(lr(f'SGST @{half_rate:.1f}%:', f'Rs.{fmt(sgst)}'))
    lines.append(lr('Shipping:', f'Rs.{fmt(shipping)}'))
    lines.append(lr('Conv. Fee (2%+GST):', f'Rs.{fmt(conv_fee)}'))
    lines.append(dsep)
    lines.append(lr('TOTAL PAID:', f'Rs.{fmt(total)}'))
    lines.append(dsep)
    lines.append(center('GST SUMMARY'))
    lines.append(sep)
    lines.append(lr('Tax', 'Taxable    Amount'))
    lines.append(lr(f'CGST @{half_rate:.1f}%', f'{fmt(after_promo)}  {fmt(cgst)}'))
    lines.append(lr(f'SGST @{half_rate:.1f}%', f'{fmt(after_promo)}  {fmt(sgst)}'))
    lines.append(lr('Total Tax:', f'Rs.{fmt(gst_amt)}'))
    lines.append(sep)
    lines.append('')
    lines.append(center('** PAID **'))
    lines.append(center(f'{date_str} {time_str} IST'))
    lines.append('')
    lines.append(center('Thank You for your payment!'))
    lines.append(center('wecare.digital'))
    lines.append(dsep)

    return lines


def _handle_dashboard_invoice(event, request_id):
    """Handle direct invoke from dashboard to create and send an invoice."""
    try:
        contact_id = event['contactId']
        phone_number_id = event.get('phoneNumberId', '919330994400')
        item_name = event['itemName']
        unit_price = float(event['unitPrice'])
        quantity = int(event.get('quantity', 1))
        gst_rate = float(event.get('gstRate', 18))
        shipping = float(event.get('shipping', 49))
        discount = float(event.get('discount', 15))
        purpose = event.get('purpose', '')
        order_id = event.get('orderId', 'Offline')
        customer_name = event.get('customerName', '')
        customer_phone = event.get('customerPhone', '')
        customer_email = event.get('customerEmail', '')
        shipping_address = event.get('shippingAddress', '')
        billing_address = event.get('billingAddress', '')
        sender_phone = event.get('senderPhone', customer_phone or contact_id)

        # Cap promo so it never exceeds subtotal
        subtotal = unit_price * quantity
        discount = min(discount, subtotal)

        _generate_and_send_invoice(
            contact_id=contact_id,
            phone_number_id=phone_number_id,
            amount=unit_price,
            quantity=quantity,
            item_name=item_name,
            gst_rate=gst_rate,
            shipping=shipping,
            discount=discount,
            purpose=purpose,
            due_ref='',
            sender_phone=sender_phone,
            request_id=request_id,
            order_id=order_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            shipping_address=shipping_address,
            billing_address=billing_address,
            pay_for='self',
        )

        return {'statusCode': 200, 'success': True, 'message': 'Invoice created and sent'}
    except Exception as e:
        logger.error(json.dumps({'event': 'dashboard_invoice_error', 'error': str(e), 'requestId': request_id}))
        return {'statusCode': 500, 'success': False, 'error': str(e)}


def _generate_and_send_invoice(contact_id: str, phone_number_id: str, amount: float,
                               quantity: int, item_name: str, gst_rate: float,
                               shipping: float, discount: float, purpose: str,
                               due_ref: str, sender_phone: str, request_id: str,
                               pay_ref: str = '', paid_at: str = '',
                               order_id: str = 'Offline', customer_name: str = '',
                               customer_phone: str = '', customer_email: str = '',
                               shipping_address: str = '', billing_address: str = '',
                               pay_for: str = 'self') -> None:
    """Generate POS invoice image with logo, upload to S3, send via WhatsApp."""
    try:
        inv_ref = f"WD-PAY-{uuid.uuid4().hex[:8].upper()}"

        if not paid_at:
            import datetime
            now_ist = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
            paid_at = now_ist.strftime('%d-%m-%Y %H:%M:%S')

        # Load logo from S3
        logo_pixels = None
        logo_w = logo_h = 0
        try:
            logo_obj = s3.get_object(Bucket=MEDIA_BUCKET, Key='stream/media/m/wecare-digital.png')
            logo_bytes = logo_obj['Body'].read()
            logo_w, logo_h, logo_pixels = _decode_png_pixels(logo_bytes)
            if logo_w is None:
                logo_pixels = None
                logo_w = logo_h = 0
            logger.info(json.dumps({'event': 'logo_loaded', 'width': logo_w, 'height': logo_h}))
        except Exception as logo_err:
            logger.warning(json.dumps({'event': 'logo_load_error', 'error': str(logo_err)}))

        lines = _build_invoice_lines(
            ref_id=inv_ref, pay_ref=pay_ref or '-', item_name=item_name,
            unit_price=amount, qty=quantity, gst_rate=gst_rate,
            shipping=shipping, discount=discount, sender_phone=sender_phone,
            purpose=purpose, due_ref=due_ref, paid_at=paid_at,
            order_id=order_id, customer_name=customer_name,
            customer_phone=customer_phone, customer_email=customer_email,
            shipping_address=shipping_address, billing_address=billing_address,
            pay_for=pay_for,
        )

        png_bytes = _render_text_to_png(lines, scale=3, logo_pixels=logo_pixels, logo_w=logo_w, logo_h=logo_h)

        s3_key = f'invoices/{inv_ref}.png'
        s3.put_object(
            Bucket=MEDIA_BUCKET,
            Key=s3_key,
            Body=png_bytes,
            ContentType='image/png',
            CacheControl='public, max-age=31536000',
        )

        logger.info(json.dumps({
            'event': 'invoice_uploaded',
            'invoiceRef': inv_ref,
            'payRef': pay_ref,
            's3Key': s3_key,
            'sizeBytes': len(png_bytes),
            'requestId': request_id,
        }))

        invoice_payload = {
            'body': json.dumps({
                'contactId': contact_id,
                'phoneNumberId': phone_number_id,
                'content': f'Here is your invoice {inv_ref}',
                'mediaFile': f's3://{MEDIA_BUCKET}/{s3_key}',
                'mediaType': 'image',
                'mediaFileName': f'{inv_ref}.png',
            })
        }
        lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps(invoice_payload),
        )

        # Store invoice record in Messages table
        try:
            messages_table = dynamodb.Table(MESSAGES_TABLE)
            now = int(time.time())
            subtotal = amount * quantity
            after_promo = subtotal - discount
            gst_amt = round(after_promo * gst_rate / 100, 2)
            cgst = round(gst_amt / 2, 2)
            sgst = round(gst_amt / 2, 2)
            conv_base = round(after_promo * 0.02, 2)
            conv_gst = round(conv_base * 0.18, 2)
            conv_fee = round(conv_base + conv_gst, 2)
            total = round(after_promo + gst_amt + shipping + conv_fee, 2)

            messages_table.put_item(Item={
                'id': str(uuid.uuid4()),
                'messageId': inv_ref,
                'contactId': contact_id,
                'channel': 'whatsapp',
                'direction': 'outbound',
                'messageType': 'invoice',
                'content': f'Invoice {inv_ref} (Paid)',
                'invoiceRef': inv_ref,
                'invoiceS3Key': s3_key,
                'paymentReferenceId': pay_ref or '',
                'paymentItemName': item_name,
                'paymentQuantity': quantity,
                'paymentAmount': Decimal(str(int(amount * 100))),
                'paymentSubtotal': Decimal(str(int(subtotal * 100))),
                'paymentDiscount': Decimal(str(int(discount * 100))),
                'paymentGstRate': Decimal(str(gst_rate)),
                'paymentGstAmount': Decimal(str(int(gst_amt * 100))),
                'paymentCgst': Decimal(str(int(cgst * 100))),
                'paymentSgst': Decimal(str(int(sgst * 100))),
                'paymentShipping': Decimal(str(int(shipping * 100))),
                'paymentConvFee': Decimal(str(int(conv_fee * 100))),
                'paymentTotal': Decimal(str(int(total * 100))),
                'paymentPurpose': purpose or '',
                'paymentDueRef': due_ref or '',
                'senderPhone': sender_phone,
                'paidAt': paid_at,
                'status': 'paid',
                'createdAt': Decimal(str(now)),
                'expiresAt': Decimal(str(now + 86400 * 365)),
            })
        except Exception as store_err:
            logger.warning(json.dumps({
                'event': 'invoice_store_error',
                'error': str(store_err),
                'invoiceRef': inv_ref,
                'requestId': request_id,
            }))

        logger.info(json.dumps({
            'event': 'invoice_sent',
            'invoiceRef': inv_ref,
            'payRef': pay_ref,
            'contactId': contact_id,
            'requestId': request_id,
        }))

    except Exception as e:
        logger.error(json.dumps({
            'event': 'invoice_generation_error',
            'error': str(e),
            'contactId': contact_id,
            'requestId': request_id,
        }))


# ============================================================================
# BOT FLOW CONFIGS (loaded from SystemConfigTable, dashboard-manageable)
# ============================================================================

# Default flow triggers config — keyword-to-flow mapping
DEFAULT_FLOW_TRIGGERS = {
    'submit_request': {
        'keywords': ['submit request', 'sr', 'raise request'],
        'flowId': '2126971738077819',
        'message': {
            'body': '\U0001f447Please use the self-service option below. Once we receive it, we\u2019ll review it and follow up if needed.',
            'footer': 'WECARE.DIGITAL',
            'flowCta': 'Submit Request',
        },
        'enabled': True,
    }
}


def _get_flow_triggers_config() -> Dict:
    """Load flow triggers config from SystemConfigTable (id: 'flow_triggers_config')."""
    try:
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        response = config_table.get_item(Key={'id': 'flow_triggers_config'})
        if 'Item' in response:
            config_value = response['Item'].get('configValue', '{}')
            config = json.loads(config_value) if isinstance(config_value, str) else config_value
            # Merge with defaults — config overrides per flow key
            merged = {}
            for key, default in DEFAULT_FLOW_TRIGGERS.items():
                if key in config:
                    entry = default.copy()
                    entry.update(config[key])
                    if 'message' in config[key]:
                        entry['message'] = {**default.get('message', {}), **config[key]['message']}
                    merged[key] = entry
                else:
                    merged[key] = default.copy()
            # Also include any new flows defined in config but not in defaults
            for key, val in config.items():
                if key not in merged:
                    merged[key] = val
            return merged
        return {k: v.copy() for k, v in DEFAULT_FLOW_TRIGGERS.items()}
    except Exception:
        return {k: v.copy() for k, v in DEFAULT_FLOW_TRIGGERS.items()}

DEFAULT_MAIN_MENU = {
    'header': 'WECARE.DIGITAL',
    'body': "Pick what you need \U0001f447",
    'footer': 'wecare.digital',
    'buttonText': 'Menu',
    'sections': [
        {
            'title': 'Explore',
            'rows': [
                {'id': 'menu_store', 'title': '\U0001f6d2 Store', 'description': 'Shop our brand marketplaces'},
                {'id': 'menu_self_service', 'title': '\U0001f680 Self Service', 'description': 'Submit, track & manage requests'},
                {'id': 'menu_pay', 'title': '\U0001f4b3 Pay', 'description': 'Make a payment via WhatsApp'},
                {'id': 'menu_subscribe', 'title': '\U0001f4dd Subscribe', 'description': 'Sign up with name, email & phone'},
            ]
        },
        {
            'title': 'More',
            'rows': [
                {'id': 'menu_app', 'title': '\U0001f4f1 Download App', 'description': 'Get the WECARE.DIGITAL app'},
                {'id': 'menu_about', 'title': '\U0001f49b About Us', 'description': 'Our mission & brands'},
                {'id': 'menu_audio', 'title': '\U0001f3a7 Audio Response', 'description': 'Get replies as voice messages'},
                {'id': 'menu_language', 'title': '\U0001f310 Change Language', 'description': 'Choose your response language'},
                {'id': 'menu_notifications', 'title': '\U0001f514 Notifications', 'description': 'Manage your alert preferences'},
                {'id': 'menu_human', 'title': '\U0001f4ac Talk to Human', 'description': 'Connect with a live agent'},
            ]
        }
    ]
}

DEFAULT_LANGUAGE_PICKER = {
    'header': '\U0001f310 Choose Region',
    'body': 'Please select a language group.\n\n\u0915\u0943\u092a\u092f\u093e \u092d\u093e\u0937\u093e \u0938\u092e\u0942\u0939 \u091a\u0941\u0928\u0947\u0902\u0964',
    'footer': 'You can change anytime by typing "language <name>"',
    'buttonText': 'Regions',
    'sections': [
        {
            'title': 'Select Region',
            'rows': [
                {'id': 'region_popular', 'title': '\u2b50 Popular', 'description': 'English, Hindi, Bengali, Tamil & more'},
                {'id': 'region_asian', 'title': '\U0001f30f Asian', 'description': '\u4e2d\u6587, \u65e5\u672c\u8a9e, \ud55c\uad6d\uc5b4, \u0e44\u0e17\u0e22 & more'},
                {'id': 'region_middle_east', 'title': '\U0001f30d Middle East', 'description': '\u0627\u0644\u0639\u0631\u0628\u064a\u0629, T\u00fcrk\u00e7e, \u0420\u0443\u0441\u0441\u043a\u0438\u0439, \u0627\u0631\u062f\u0648'},
                {'id': 'region_european', 'title': '\U0001f1ea\U0001f1fa European', 'description': 'Fran\u00e7ais, Espa\u00f1ol, Portugu\u00eas'},
            ]
        }
    ]
}

# Step 2: Language lists per region (used when ai-generate-response returns regionLanguages)
REGION_LANGUAGE_LISTS = {
    'region_popular': {
        'header': '\u2b50 Popular Languages',
        'body': 'Choose your language \U0001f447',
        'footer': 'wecare.digital',
        'buttonText': 'Languages',
        'sections': [{'title': 'Languages', 'rows': [
            {'id': 'lang_english', 'title': 'English', 'description': 'Respond in English'},
            {'id': 'lang_hindi', 'title': '\u0939\u093f\u0928\u094d\u0926\u0940 / Hindi', 'description': '\u0939\u093f\u0902\u0926\u0940 \u092e\u0947\u0902 \u091c\u0935\u093e\u092c \u0926\u0947\u0902'},
            {'id': 'lang_hinglish', 'title': 'Hinglish', 'description': 'Hindi + English mix'},
            {'id': 'lang_bengali', 'title': '\u09ac\u09be\u0982\u09b2\u09be / Bengali', 'description': '\u09ac\u09be\u0982\u09b2\u09be\u09af\u09bc \u0989\u09a4\u09cd\u09a4\u09b0 \u09a6\u09bf\u09a8'},
            {'id': 'lang_tamil', 'title': '\u0ba4\u0bae\u0bbf\u0bb4\u0bcd / Tamil', 'description': '\u0ba4\u0bae\u0bbf\u0bb4\u0bbf\u0bb2\u0bcd \u0baa\u0ba4\u0bbf\u0bb2\u0bb3\u0bbf\u0b95\u0bcd\u0b95\u0bb5\u0bc1\u0bae\u0bcd'},
            {'id': 'lang_telugu', 'title': '\u0c24\u0c46\u0c32\u0c41\u0c17\u0c41 / Telugu', 'description': '\u0c24\u0c46\u0c32\u0c41\u0c17\u0c41\u0c32\u0c4b \u0c38\u0c2e\u0c3e\u0c27\u0c3e\u0c28\u0c02'},
            {'id': 'lang_gujarati', 'title': '\u0a97\u0ac1\u0a9c\u0ab0\u0abe\u0aa4\u0ac0 / Gujarati', 'description': '\u0a97\u0ac1\u0a9c\u0ab0\u0abe\u0aa4\u0ac0\u0aae\u0abe\u0a82 \u0a9c\u0ab5\u0abe\u0aac'},
            {'id': 'lang_marathi', 'title': '\u092e\u0930\u093e\u0920\u0940 / Marathi', 'description': '\u092e\u0930\u093e\u0920\u0940\u0924 \u0909\u0924\u094d\u0924\u0930 \u0926\u094d\u092f\u093e'},
            {'id': 'lang_kannada', 'title': '\u0c95\u0ca8\u0ccd\u0ca8\u0ca1 / Kannada', 'description': '\u0c95\u0ca8\u0ccd\u0ca8\u0ca1\u0ca6\u0cb2\u0ccd\u0cb2\u0cbf \u0c89\u0ca4\u0ccd\u0ca4\u0cb0'},
            {'id': 'lang_malayalam', 'title': '\u0d2e\u0d32\u0d2f\u0d3e\u0d33\u0d02 / Malayalam', 'description': '\u0d2e\u0d32\u0d2f\u0d3e\u0d33\u0d24\u0d4d\u0d24\u0d3f\u0d7d \u0d2e\u0d31\u0d41\u0d2a\u0d1f\u0d3f'},
        ]}]
    },
    'region_asian': {
        'header': '\U0001f30f Asian Languages',
        'body': 'Choose your language \U0001f447',
        'footer': 'wecare.digital',
        'buttonText': 'Languages',
        'sections': [{'title': 'Languages', 'rows': [
            {'id': 'lang_chinese', 'title': '\u7b80\u4f53\u4e2d\u6587 / Chinese', 'description': '\u7528\u4e2d\u6587\u56de\u590d'},
            {'id': 'lang_japanese', 'title': '\u65e5\u672c\u8a9e / Japanese', 'description': '\u65e5\u672c\u8a9e\u3067\u5fdc\u7b54'},
            {'id': 'lang_korean', 'title': '\ud55c\uad6d\uc5b4 / Korean', 'description': '\ud55c\uad6d\uc5b4\ub85c \ub2f5\ubcc0'},
            {'id': 'lang_thai', 'title': '\u0e44\u0e17\u0e22 / Thai', 'description': '\u0e15\u0e2d\u0e1a\u0e40\u0e1b\u0e47\u0e19\u0e20\u0e32\u0e29\u0e32\u0e44\u0e17\u0e22'},
            {'id': 'lang_vietnamese', 'title': 'Ti\u1ebfng Vi\u1ec7t / Vietnamese', 'description': 'Tr\u1ea3 l\u1eddi b\u1eb1ng ti\u1ebfng Vi\u1ec7t'},
            {'id': 'lang_indonesian', 'title': 'Indonesia / Indonesian', 'description': 'Balas dalam Bahasa Indonesia'},
            {'id': 'lang_sinhala', 'title': '\u0dc3\u0dd2\u0d82\u0dc4\u0dbd / Sinhala', 'description': '\u0dc3\u0dd2\u0d82\u0dc4\u0dbd\u0dd9\u0db1\u0dca \u0db4\u0dd2\u0dc5\u0dd2\u0dad\u0dd4\u0dbb\u0dd4'},
        ]}]
    },
    'region_middle_east': {
        'header': '\U0001f30d Middle East Languages',
        'body': 'Choose your language \U0001f447',
        'footer': 'wecare.digital',
        'buttonText': 'Languages',
        'sections': [{'title': 'Languages', 'rows': [
            {'id': 'lang_arabic', 'title': '\u0627\u0644\u0639\u0631\u0628\u064a\u0629 / Arabic', 'description': '\u0627\u0644\u0631\u062f \u0628\u0627\u0644\u0639\u0631\u0628\u064a\u0629'},
            {'id': 'lang_turkish', 'title': 'T\u00fcrk\u00e7e / Turkish', 'description': 'T\u00fcrk\u00e7e yan\u0131t verin'},
            {'id': 'lang_russian', 'title': '\u0420\u0443\u0441\u0441\u043a\u0438\u0439 / Russian', 'description': '\u041e\u0442\u0432\u0435\u0442 \u043d\u0430 \u0440\u0443\u0441\u0441\u043a\u043e\u043c'},
            {'id': 'lang_urdu', 'title': '\u0627\u0631\u062f\u0648 / Urdu', 'description': '\u0627\u0631\u062f\u0648 \u0645\u06cc\u06ba \u062c\u0648\u0627\u0628 \u062f\u06cc\u06ba'},
            {'id': 'lang_punjabi', 'title': '\u0a2a\u0a70\u0a1c\u0a3e\u0a2c\u0a40 / Punjabi', 'description': '\u0a2a\u0a70\u0a1c\u0a3e\u0a2c\u0a40 \u0a35\u0a3f\u0a71\u0a1a \u0a1c\u0a35\u0a3e\u0a2c'},
        ]}]
    },
    'region_european': {
        'header': '\U0001f1ea\U0001f1fa European Languages',
        'body': 'Choose your language \U0001f447',
        'footer': 'wecare.digital',
        'buttonText': 'Languages',
        'sections': [{'title': 'Languages', 'rows': [
            {'id': 'lang_french', 'title': 'Fran\u00e7ais / French', 'description': 'R\u00e9pondre en fran\u00e7ais'},
            {'id': 'lang_spanish', 'title': 'Espa\u00f1ol / Spanish', 'description': 'Responder en espa\u00f1ol'},
            {'id': 'lang_portuguese', 'title': 'Portugu\u00eas / Portuguese', 'description': 'Responder em portugu\u00eas'},
        ]}]
    },
}


def _get_welcome_config() -> Dict:
    """Load main menu config from SystemConfigTable (id: 'welcome_message_config')."""
    try:
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        response = config_table.get_item(Key={'id': 'welcome_message_config'})
        if 'Item' in response:
            config_value = response['Item'].get('configValue', '{}')
            config = json.loads(config_value) if isinstance(config_value, str) else config_value
            merged = DEFAULT_MAIN_MENU.copy()
            merged.update(config)
            return merged
        return DEFAULT_MAIN_MENU.copy()
    except Exception:
        return DEFAULT_MAIN_MENU.copy()


def _get_language_picker_config() -> Dict:
    """Load language picker config from SystemConfigTable (id: 'bot_language_picker_config')."""
    try:
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        response = config_table.get_item(Key={'id': 'bot_language_picker_config'})
        if 'Item' in response:
            config_value = response['Item'].get('configValue', '{}')
            config = json.loads(config_value) if isinstance(config_value, str) else config_value
            # Region picker (Step 1) — override rows if provided
            if 'regionPicker' in config:
                region_rows = config['regionPicker']
                return {
                    'header': config.get('regionHeader', DEFAULT_LANGUAGE_PICKER['header']),
                    'body': config.get('regionBody', DEFAULT_LANGUAGE_PICKER['body']),
                    'footer': config.get('regionFooter', DEFAULT_LANGUAGE_PICKER['footer']),
                    'buttonText': config.get('regionButtonText', DEFAULT_LANGUAGE_PICKER['buttonText']),
                    'sections': [{'title': 'Select Region', 'rows': region_rows}]
                }
            merged = DEFAULT_LANGUAGE_PICKER.copy()
            merged.update(config)
            return merged
        return DEFAULT_LANGUAGE_PICKER.copy()
    except Exception:
        return DEFAULT_LANGUAGE_PICKER.copy()


def _get_region_language_list(region_id: str) -> Optional[Dict]:
    """
    Get the language list for a specific region.
    Checks SystemConfigTable first (dashboard-manageable), falls back to REGION_LANGUAGE_LISTS.
    """
    try:
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        response = config_table.get_item(Key={'id': 'bot_language_picker_config'})
        if 'Item' in response:
            config_value = response['Item'].get('configValue', '{}')
            config = json.loads(config_value) if isinstance(config_value, str) else config_value
            db_region_lists = config.get('regionLanguageLists', {})
            if region_id in db_region_lists:
                return db_region_lists[region_id]
    except Exception:
        pass
    return REGION_LANGUAGE_LISTS.get(region_id)


def _send_read_receipt(whatsapp_message_id: str, phone_number_id: str, request_id: str) -> None:
    """
    Send read receipt to WhatsApp per AWS docs.
    Per AWS: send-whatsapp-message with status='read' shows two blue check marks.
    """
    if not whatsapp_message_id:
        return
    
    try:
        # Build read receipt payload per AWS Social Messaging docs
        read_receipt_payload = {
            'messaging_product': 'whatsapp',
            'message_id': whatsapp_message_id,
            'status': 'read'
        }
        
        logger.info(json.dumps({
            'event': 'read_receipt_payload',
            'messageId': whatsapp_message_id,
            'status': 'read',
            'requestId': request_id
        }))
        
        # Call SendWhatsAppMessage API with read status
        response = social_messaging.send_whatsapp_message(
            originationPhoneNumberId=phone_number_id,
            message=json.dumps(read_receipt_payload).encode('utf-8'),
            metaApiVersion='v20.0'
        )
        
        logger.info(json.dumps({
            'event': 'read_receipt_sent',
            'messageId': whatsapp_message_id,
            'phoneNumberId': phone_number_id,
            'statusCode': response.get('StatusCode', 200),
            'requestId': request_id
        }))
        
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'read_receipt_error',
            'messageId': whatsapp_message_id,
            'error': str(e),
            'requestId': request_id
        }))


# ============================================================================
# AI AUTOMATION INTEGRATION
# ============================================================================

# Default AI configuration
DEFAULT_AI_CONFIG = {
    'enabled': False,
    'autoReplyEnabled': False,
    'respondToInteractive': True,
    'respondToText': True,
    'respondToMedia': True,  # Now enabled — multimodal AI via Converse API
    'respondToLocation': True,
    'maxResponseLength': 500,
    'responseDelay': 0,
    'supportedLanguages': ['en', 'hi', 'hi-Latn', 'bn', 'ta', 'te', 'gu', 'mr'],
    'defaultLanguage': 'en',
    'agentId': 'Z4YAK0ZLBO',
    'agentAlias': 'WANPKHQGIB',
    'knowledgeBaseId': 'static-faq',
    'modelId': 'amazon.nova-lite-v1:0',
}


def _get_ai_config() -> Dict[str, Any]:
    """
    Get AI configuration from SystemConfig table.
    Returns default config if not found or on error.
    """
    try:
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        # SystemConfigTable PK is 'id', we use id=configKey for compatibility
        response = config_table.get_item(Key={'id': 'ai_config'})
        
        if 'Item' in response:
            config_value = response['Item'].get('configValue', '{}')
            config = json.loads(config_value) if isinstance(config_value, str) else config_value
            # Merge with defaults to ensure all keys exist
            merged = DEFAULT_AI_CONFIG.copy()
            merged.update(config)
            return merged
        
        return DEFAULT_AI_CONFIG.copy()
    except Exception as e:
        logger.warning(f"Failed to get AI config: {str(e)}")
        return DEFAULT_AI_CONFIG.copy()


def _is_ai_enabled() -> bool:
    """
    Check if AI automation is enabled in SystemConfig.
    Returns False silently if table doesn't exist (AI not configured).
    """
    config = _get_ai_config()
    return config.get('enabled', False) and config.get('autoReplyEnabled', False)


def _process_ai_automation(message_id: str, contact_id: str, content: str, message_type: str, phone_number_id: str, sender_phone: str, s3_key: str, mime_type: str, request_id: str) -> Optional[Dict]:
    """
    Process AI automation for inbound message and send auto-reply.
    
    Supports all message types including multimodal:
    - text: Regular text messages
    - interactive: Button/list replies
    - button: Quick reply buttons
    - location: Location sharing
    - image: Photos with optional caption
    - audio: Voice notes
    - video: Video messages
    - document: PDF, DOC, etc.
    
    Uses AI config from SystemConfigTable to determine behavior.
    Sends typing indicator before AI processing.
    Handles processing lock (locked response from AI function).
    """
    # Get AI config from SystemConfig table
    ai_config = _get_ai_config()
    ai_enabled = ai_config.get('enabled', False) and ai_config.get('autoReplyEnabled', False)
    
    # Check if this message type should trigger AI
    type_config_map = {
        'text': 'respondToText',
        'interactive': 'respondToInteractive',
        'button': 'respondToInteractive',
        'location': 'respondToLocation',
        'image': 'respondToMedia',
        'audio': 'respondToMedia',
        'video': 'respondToMedia',
        'document': 'respondToMedia',
    }
    config_key = type_config_map.get(message_type, 'respondToText')
    should_respond = ai_config.get(config_key, True)
    
    logger.info(json.dumps({
        'event': 'ai_automation_check',
        'aiEnabled': ai_enabled,
        'messageType': message_type,
        'shouldRespond': should_respond,
        'hasMedia': bool(s3_key),
        'messageId': message_id,
        'contentLength': len(content) if content else 0,
        'requestId': request_id
    }))
    
    if not ai_enabled or not should_respond:
        return None

    # Fix #6: Circuit breaker — skip AI if too many recent failures
    global _ai_fail_count, _ai_fail_reset_time
    if _ai_fail_count >= AI_CIRCUIT_BREAKER_THRESHOLD:
        if time.time() < _ai_fail_reset_time:
            logger.warning(json.dumps({
                'event': 'ai_circuit_breaker_open',
                'failCount': _ai_fail_count,
                'resetAt': _ai_fail_reset_time,
                'requestId': request_id
            }))
            return None
        # Cooldown expired — reset and retry
        _ai_fail_count = 0
    
    try:
        # Send typing indicator before AI processing
        _send_typing_indicator(
            sender_phone=sender_phone,
            phone_number_id=phone_number_id,
            request_id=request_id
        )
        
        # Skip separate KB query — the ai-generate-response function now handles
        # KB retrieval internally via the Converse API path
        
        # Invoke AI generate response with multimodal payload
        ai_response = _invoke_ai_generate_response_v2(
            content=content,
            message_id=message_id,
            contact_id=contact_id,
            sender_phone=sender_phone,
            message_type=message_type,
            s3_key=s3_key,
            mime_type=mime_type,
            request_id=request_id
        )
        
        # Check if processing was locked (another message being processed)
        # Fix #6: Reset circuit breaker on success
        if ai_response and not ai_response.get('locked'):
            _ai_fail_count = 0
        if ai_response and ai_response.get('locked'):
            _send_ai_auto_reply(
                contact_id=contact_id,
                content="I'm still working on your previous message, one moment... ⏳",
                phone_number_id=phone_number_id,
                request_id=request_id
            )
            return ai_response
        
        # Check if AI flagged for human escalation (from intent classification, NOT from menu handoff)
        if ai_response and ai_response.get('escalate') and not ai_response.get('humanHandoff'):
            escalation_text = ai_response.get('suggestion', '') or ai_response.get('suggestedResponse', '')
            if escalation_text and len(escalation_text) > 5:
                _send_ai_auto_reply(
                    contact_id=contact_id,
                    content=escalation_text,
                    phone_number_id=phone_number_id,
                    request_id=request_id
                )
            logger.info(json.dumps({
                'event': 'ai_escalation_triggered',
                'intent': ai_response.get('intent', 'unknown'),
                'confidence': ai_response.get('confidence', 0),
                'messageId': message_id,
                'contactId': contact_id,
                'escalationTextSent': bool(escalation_text),
                'requestId': request_id
            }))
            return ai_response
        
        # ── Bot flow handling ──
        flow_action = ai_response.get('flowAction', '') if ai_response else ''
        flow_config = ai_response.get('flowConfig', {}) if ai_response else {}

        # Welcome: send welcome text + main menu
        if ai_response and ai_response.get('sendWelcomeMenu'):
            welcome_text = ai_response.get('suggestion', '') or ai_response.get('suggestedResponse', '')
            if welcome_text:
                _send_ai_auto_reply(
                    contact_id=contact_id,
                    content=welcome_text,
                    phone_number_id=phone_number_id,
                    request_id=request_id
                )
            # Send the main menu interactive list
            main_menu = flow_config.get('mainMenu') or _get_welcome_config()
            _send_interactive_list(
                contact_id=contact_id,
                phone_number_id=phone_number_id,
                list_config=main_menu,
                request_id=request_id
            )
            return ai_response

        # Language picker requested (two-step: region → languages)
        if ai_response and ai_response.get('showLanguagePicker'):
            picker_step = ai_response.get('languagePickerStep', 'region')

            if picker_step == 'languages':
                # Step 2: Show languages for the selected region
                region_id = ai_response.get('regionId', '')
                region_list = _get_region_language_list(region_id)
                if region_list:
                    _send_interactive_list(
                        contact_id=contact_id,
                        phone_number_id=phone_number_id,
                        list_config=region_list,
                        request_id=request_id
                    )
                else:
                    # Fallback: show region picker again
                    _send_interactive_list(
                        contact_id=contact_id,
                        phone_number_id=phone_number_id,
                        list_config=_get_language_picker_config(),
                        request_id=request_id
                    )
            else:
                # Step 1: Show region picker
                _send_interactive_list(
                    contact_id=contact_id,
                    phone_number_id=phone_number_id,
                    list_config=_get_language_picker_config(),
                    request_id=request_id
                )
            return ai_response

        # Send text response first (menu item response, language confirmation, etc.)
        if ai_response and (ai_response.get('suggestion') or ai_response.get('suggestedResponse')):
            suggestion = ai_response.get('suggestion', '') or ai_response.get('suggestedResponse', '')
            max_length = ai_config.get('maxResponseLength', 1000)
            if suggestion and len(suggestion) > 5:
                if len(suggestion) > max_length:
                    suggestion = suggestion[:max_length] + '...'
                
                response_delay = ai_config.get('responseDelay', 0)
                if response_delay > 0:
                    time.sleep(min(response_delay, 5))
                
                _send_ai_auto_reply(
                    contact_id=contact_id,
                    content=suggestion,
                    phone_number_id=phone_number_id,
                    request_id=request_id
                )

        # Send CTA button if present
        if ai_response and ai_response.get('cta'):
            cta = ai_response['cta']
            _send_cta_button(
                contact_id=contact_id,
                phone_number_id=phone_number_id,
                cta_text=cta.get('text', 'Start Now'),
                cta_url=cta.get('url', 'https://wecare.digital/selfservice'),
                request_id=request_id
            )

        # Follow-up flow actions
        if flow_action == 'showOptions':
            _send_reply_buttons(
                contact_id=contact_id,
                phone_number_id=phone_number_id,
                button_config={
                    'body': "What\u2019s next?",
                    'footer': 'wecare.digital',
                    'buttons': [
                        {'id': 'opt_do_more', 'title': '\U0001f9ed Do more'},
                        {'id': 'opt_done', 'title': '\u270c\ufe0f Done here'},
                    ],
                },
                request_id=request_id
            )
        elif flow_action == 'showMainMenu':
            main_menu = _get_welcome_config()
            _send_interactive_list(
                contact_id=contact_id,
                phone_number_id=phone_number_id,
                list_config=main_menu,
                request_id=request_id
            )
        elif flow_action == 'showSubMenu':
            sub_menu_config = ai_response.get('subMenuConfig', {}) if ai_response else {}
            if sub_menu_config:
                _send_interactive_list(
                    contact_id=contact_id,
                    phone_number_id=phone_number_id,
                    list_config=sub_menu_config,
                    request_id=request_id
                )
        elif flow_action == 'showRating':
            _send_reply_buttons(
                contact_id=contact_id,
                phone_number_id=phone_number_id,
                button_config={
                    'body': "How was your experience? \U0001faf6",
                    'footer': 'wecare.digital',
                    'buttons': [
                        {'id': 'rate_good', 'title': '\U0001f64c Great'},
                        {'id': 'rate_ok', 'title': '\U0001f610 Just okay'},
                        {'id': 'rate_mid', 'title': '\U0001fae4 Could be better'},
                    ],
                },
                request_id=request_id
            )
        elif flow_action == 'sendPayment':
            # Send WhatsApp Pay order_details message with GST breakdown
            payment_amount = ai_response.get('paymentAmount', 0) if ai_response else 0
            if payment_amount > 0:
                _send_payment_request(
                    contact_id=contact_id,
                    phone_number_id=phone_number_id,
                    amount=payment_amount,
                    request_id=request_id,
                    item_name=ai_response.get('paymentItemName', 'Services/Goods'),
                    gst_rate=ai_response.get('paymentGstRate', 18),
                    shipping=ai_response.get('paymentShipping', 49),
                    sender_phone=sender_phone,
                    quantity=ai_response.get('paymentQuantity', 1),
                    discount=ai_response.get('paymentDiscount', 0),
                    payment_purpose=ai_response.get('paymentPurpose', ''),
                    due_ref=ai_response.get('paymentDueRef', ''),
                    order_id=ai_response.get('paymentOrderId', 'Offline'),
                    customer_name=ai_response.get('paymentCustomerName', ''),
                    customer_phone=ai_response.get('paymentCustomerPhone', sender_phone),
                    customer_email=ai_response.get('paymentCustomerEmail', ''),
                    shipping_address=ai_response.get('paymentShippingAddress', ''),
                    billing_address=ai_response.get('paymentBillingAddress', ''),
                    pay_for=ai_response.get('paymentPayFor', 'self'),
                )
        elif flow_action == 'sendPendingPayments':
            # ── Payment flow (hardcoded, LLM-independent — edit PAY_MSG at top of file) ──
            customer_phone = ai_response.get('paymentCustomerPhone', sender_phone) if ai_response else sender_phone

            # If customer messaged Phone 2, redirect them to Phone 1 for payments
            if phone_number_id != PAYMENT_PHONE_NUMBER_ID:
                _send_ai_auto_reply(contact_id, PAY_MSG['redirect'], phone_number_id, request_id)
                logger.info(json.dumps({
                    'event': 'payment_redirected_to_phone1',
                    'phone': customer_phone,
                    'fromPhoneId': phone_number_id,
                    'requestId': request_id,
                }))
            else:
                # Step 1: Send "pulling" message immediately
                _send_ai_auto_reply(contact_id, PAY_MSG['pulling'], phone_number_id, request_id)

                try:
                    inv_payload = {
                        'rawPath': '/invoices/send-pending-by-phone',
                        'requestContext': {'http': {'method': 'POST'}},
                        'body': json.dumps({
                            'customerPhone': customer_phone,
                            'phoneNumberId': phone_number_id,
                        }),
                    }
                    inv_response = lambda_client.invoke(
                        FunctionName='wecare-invoice-engine',
                        InvocationType='RequestResponse',
                        Payload=json.dumps(inv_payload),
                    )
                    inv_result = json.loads(inv_response['Payload'].read())
                    inv_body = json.loads(inv_result.get('body', '{}'))
                    sent_count = inv_body.get('sent', 0)
                    total_count = inv_body.get('total', 0)
                    invoices_sent = inv_body.get('invoices', [])
                    send_error = inv_body.get('error', '')

                    if total_count == 0:
                        _send_ai_auto_reply(contact_id, PAY_MSG['no_dues'], phone_number_id, request_id)
                    elif sent_count == 0:
                        _send_ai_auto_reply(contact_id, PAY_MSG['send_failed'], phone_number_id, request_id)
                        logger.warning(json.dumps({
                            'event': 'send_pending_payment_link_failed',
                            'sent': 0, 'total': total_count,
                            'error': send_error, 'phone': customer_phone,
                            'requestId': request_id,
                        }))

                    logger.info(json.dumps({
                        'event': 'send_pending_payments_complete',
                        'sent': sent_count, 'total': total_count,
                        'phone': customer_phone, 'requestId': request_id,
                    }))
                except Exception as e:
                    logger.error(json.dumps({
                        'event': 'send_pending_payments_error',
                        'error': str(e), 'requestId': request_id,
                    }))
                    _send_ai_auto_reply(contact_id, PAY_MSG['error'], phone_number_id, request_id)

        elif flow_action == 'humanHandoff':
            # Flag conversation for human agent in CRM
            try:
                contacts_table = dynamodb.Table(CONTACTS_TABLE)
                contacts_table.update_item(
                    Key={'id': contact_id},
                    UpdateExpression='SET humanHandoff = :h, handoffAt = :t',
                    ExpressionAttributeValues={
                        ':h': True,
                        ':t': Decimal(str(int(time.time()))),
                    }
                )
            except Exception as hh_err:
                logger.warning(json.dumps({
                    'event': 'human_handoff_flag_error',
                    'contactId': contact_id,
                    'error': str(hh_err),
                    'requestId': request_id
                }))
            logger.info(json.dumps({
                'event': 'human_handoff_requested',
                'contactId': contact_id,
                'requestId': request_id
            }))
        elif flow_action == 'end':
            # Rating submitted — nothing more to do, message already sent
            pass

        # ── Safety net: if AI returned but nothing was sent to user, send fallback ──
        if ai_response and not ai_response.get('locked') and not ai_response.get('showLanguagePicker'):
            suggestion_sent = ai_response.get('suggestion', '') or ai_response.get('suggestedResponse', '')
            has_flow_action = flow_action in ('showMainMenu', 'showSubMenu', 'showOptions', 'showRating', 'sendPayment', 'sendPendingPayments', 'humanHandoff', 'end')
            if not suggestion_sent and not has_flow_action and not ai_response.get('sendWelcomeMenu'):
                fallback_msg = "Hi! 👋 I'm here to help. Type *menu* to see options, or just ask me anything. 😊"
                logger.warning(json.dumps({
                    'event': 'ai_blank_response_fallback',
                    'contactId': contact_id,
                    'messageId': message_id,
                    'aiResponseKeys': list(ai_response.keys()) if ai_response else [],
                    'requestId': request_id
                }))
                _send_ai_auto_reply(
                    contact_id=contact_id,
                    content=fallback_msg,
                    phone_number_id=phone_number_id,
                    request_id=request_id
                )

        # ── Audio response: if user has audioEnabled, send TTS version ──
        if ai_response and not ai_response.get('locked') and not ai_response.get('escalate'):
            suggestion_text = ai_response.get('suggestion', '') or ai_response.get('suggestedResponse', '')
            if suggestion_text and len(suggestion_text) > 10:
                try:
                    # Load user preferences to check audioEnabled
                    # Fix #2: Use same hash as AI handler — sha256(clean_phone)[:32]
                    from hashlib import sha256
                    clean_phone = sender_phone.replace('+', '').replace(' ', '').replace('-', '') if sender_phone else ''
                    ph = sha256(clean_phone.encode()).hexdigest()[:32] if clean_phone else ''
                    if ph:
                        conv_table = dynamodb.Table(os.environ.get('CONVERSATION_HISTORY_TABLE', 'base-wecare-digital-ConversationHistoryTable'))
                        pref_resp = conv_table.get_item(Key={'phoneHash': ph})
                        pref_item = pref_resp.get('Item', {})
                        audio_enabled = pref_item.get('audioEnabled', False)
                        user_lang = pref_item.get('preferredLanguage', 'English')
                        if audio_enabled:
                            _send_audio_response(
                                contact_id=contact_id,
                                phone_number_id=phone_number_id,
                                text=suggestion_text,
                                language=user_lang,
                                request_id=request_id
                            )
                except Exception as audio_err:
                    logger.warning(json.dumps({
                        'event': 'audio_check_error',
                        'contactId': contact_id,
                        'error': str(audio_err),
                        'requestId': request_id
                    }))
        
        return ai_response
    except Exception as e:
        logger.error(json.dumps({
            'event': 'ai_automation_error',
            'messageId': message_id,
            'messageType': message_type,
            'error': str(e),
            'requestId': request_id
        }))
        # Fix #5: Send fallback message so customer doesn't get silence
        # Fix #6: Increment circuit breaker
        _ai_fail_count += 1
        _ai_fail_reset_time = time.time() + AI_CIRCUIT_BREAKER_COOLDOWN
        try:
            _send_ai_auto_reply(
                contact_id=contact_id,
                content="Thanks for your message! 🙏 We're experiencing a brief delay. Please try again in a moment, or call us at +91 9330994400.",
                phone_number_id=phone_number_id,
                request_id=request_id
            )
        except Exception:
            pass
        return None


def _invoke_ai_query_kb(query: str, message_id: str, request_id: str) -> Optional[Dict]:
    """Invoke ai-query-kb Lambda function."""
    try:
        logger.info(json.dumps({
            'event': 'invoking_ai_query_kb',
            'functionName': AI_QUERY_KB_FUNCTION,
            'messageId': message_id,
            'requestId': request_id
        }))
        response = lambda_client.invoke(
            FunctionName=AI_QUERY_KB_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps({'query': query, 'messageId': message_id, 'requestId': request_id})
        )
        status_code = response.get('StatusCode')
        logger.info(json.dumps({
            'event': 'ai_query_kb_response',
            'statusCode': status_code,
            'messageId': message_id,
            'requestId': request_id
        }))
        if status_code == 200:
            payload = response['Payload'].read().decode('utf-8')
            return json.loads(json.loads(payload).get('body', '{}'))
        return None
    except Exception as e:
        logger.error(json.dumps({
            'event': 'ai_query_kb_error',
            'error': str(e),
            'messageId': message_id,
            'requestId': request_id
        }))
        return None


def _invoke_ai_generate_response(content: str, kb_context: Optional[Dict], 
                                  message_id: str, contact_id: str, request_id: str) -> Optional[Dict]:
    """Invoke ai-generate-response Lambda function (legacy, used for internal)."""
    try:
        response = lambda_client.invoke(
            FunctionName=AI_GENERATE_RESPONSE_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'messageContent': content,
                'kbContext': kb_context,
                'messageId': message_id,
                'contactId': contact_id,
                'requestId': request_id
            })
        )
        if response.get('StatusCode') == 200:
            body = json.loads(json.loads(response['Payload'].read().decode('utf-8')).get('body', '{}'))
            _store_ai_interaction(message_id, content, body.get('suggestion', '') or body.get('suggestedResponse', ''), request_id)
            return body
        return None
    except Exception:
        return None


def _invoke_ai_generate_response_v2(
    content: str, message_id: str, contact_id: str, sender_phone: str,
    message_type: str, s3_key: str, mime_type: str, request_id: str
) -> Optional[Dict]:
    """
    Invoke ai-generate-response Lambda with multimodal payload.
    Passes sender phone, message type, S3 key, and mime type for
    the Converse API path to handle images, audio, video, documents.
    """
    try:
        payload = {
            'messageContent': content,
            'messageId': message_id,
            'contactId': contact_id,
            'senderPhone': sender_phone,
            'context': 'external',
            'messageType': message_type,
            's3Key': s3_key,
            'mediaType': message_type if message_type in ('image', 'audio', 'video', 'document') else '',
            'mimeType': mime_type,
            'requestId': request_id,
        }

        logger.info(json.dumps({
            'event': 'ai_generate_v2_invoke',
            'messageType': message_type,
            'hasMedia': bool(s3_key),
            'messageId': message_id,
            'requestId': request_id
        }))

        response = lambda_client.invoke(
            FunctionName=AI_GENERATE_RESPONSE_FUNCTION,
            InvocationType='RequestResponse',
            Payload=json.dumps(payload)
        )

        if response.get('StatusCode') == 200:
            raw = response['Payload'].read().decode('utf-8')
            parsed = json.loads(raw)
            body = json.loads(parsed.get('body', '{}'))

            # Store AI interaction for audit
            suggestion = body.get('suggestion', '') or body.get('suggestedResponse', '')
            if suggestion and not body.get('locked'):
                _store_ai_interaction(message_id, content or f'[{message_type}]', suggestion, request_id)

            return body
        return None
    except Exception as e:
        logger.error(json.dumps({
            'event': 'ai_generate_v2_error',
            'error': str(e),
            'messageId': message_id,
            'requestId': request_id
        }))
        return None


def _send_typing_indicator(sender_phone: str, phone_number_id: str, request_id: str) -> None:
    """
    Send WhatsApp typing indicator so the customer sees engagement while AI processes.
    
    AWS EUM Social API does not expose a native typing indicator endpoint.
    We send a read receipt (blue ticks) as the closest proxy — this signals
    to the customer that their message was seen and a response is coming.
    """
    if not sender_phone or not phone_number_id:
        return

    try:
        # Clean phone number — ensure + prefix for WhatsApp recipient
        clean_phone = sender_phone.lstrip('+')
        formatted_phone = f'+{clean_phone}'

        # Send read receipt as typing proxy
        read_payload = {
            'messaging_product': 'whatsapp',
            'status': 'read',
            'recipient_type': 'individual',
            'to': formatted_phone,
        }

        social_messaging.send_whatsapp_message(
            originationPhoneNumberId=phone_number_id,
            message=json.dumps(read_payload).encode('utf-8'),
            metaApiVersion='v20.0'
        )

        logger.info(json.dumps({
            'event': 'typing_indicator_sent',
            'senderPhone': sender_phone,
            'phoneNumberId': phone_number_id,
            'note': 'Sent read receipt as typing proxy (EUM has no native typing API)',
            'requestId': request_id
        }))

    except Exception as e:
        # Non-critical — don't fail the AI flow for typing indicator
        logger.warning(json.dumps({
            'event': 'typing_indicator_error',
            'error': str(e),
            'requestId': request_id
        }))


def _store_ai_interaction(message_id: str, query: str, response: str, request_id: str) -> None:
    """Store AI interaction record."""
    try:
        ai_table = dynamodb.Table(AI_INTERACTIONS_TABLE)
        ai_table.put_item(Item={
            'id': str(uuid.uuid4()),
            'interactionId': str(uuid.uuid4()),
            'messageId': message_id,
            'query': query,
            'response': response,
            'approved': False,
            'timestamp': Decimal(str(int(time.time()))),
        })
    except Exception as e:
        logger.error(f"Failed to store AI interaction: {str(e)}")


# ============================================================================
# WHATSAPP BUSINESS ACCOUNT WEBHOOKS
# Template Status, Phone Quality, Messaging Limits
# ============================================================================

def _process_template_status(value: Dict, request_id: str) -> None:
    """
    Process template status update webhook.
    
    Webhook format:
    {
        "event": "APPROVED" | "REJECTED" | "PENDING" | "PAUSED" | "DISABLED" | "FLAGGED",
        "message_template_id": 123456789,
        "message_template_name": "template_name",
        "message_template_language": "en_US",
        "reason": "NONE" | "ABUSIVE_CONTENT" | "INVALID_FORMAT" | ...
    }
    
    Events:
    - APPROVED: Template approved and ready to use
    - REJECTED: Template rejected (check reason)
    - PENDING: Template submitted for review
    - PAUSED: Template paused due to quality issues
    - DISABLED: Template disabled
    - FLAGGED: Template flagged for review
    """
    event = value.get('event', '')
    template_id = value.get('message_template_id', '')
    template_name = value.get('message_template_name', '')
    template_language = value.get('message_template_language', '')
    reason = value.get('reason', 'NONE')
    
    logger.info(json.dumps({
        'event': 'template_status_update',
        'templateEvent': event,
        'templateId': template_id,
        'templateName': template_name,
        'templateLanguage': template_language,
        'reason': reason,
        'requestId': request_id
    }))
    
    # Store template status in SystemConfig table for dashboard display
    _store_system_event(
        event_type='template_status',
        event_data={
            'event': event,
            'templateId': str(template_id),
            'templateName': template_name,
            'templateLanguage': template_language,
            'reason': reason
        },
        request_id=request_id
    )
    
    # Log warning for rejected/paused templates
    if event in ['REJECTED', 'PAUSED', 'DISABLED', 'FLAGGED']:
        logger.warning(json.dumps({
            'event': 'template_status_alert',
            'templateEvent': event,
            'templateName': template_name,
            'reason': reason,
            'action': 'Review template in Meta Business Manager',
            'requestId': request_id
        }))


def _process_phone_quality_update(value: Dict, request_id: str) -> None:
    """
    Process phone number quality update webhook.
    
    Webhook format:
    {
        "display_phone_number": "+1234567890",
        "current_limit": "TIER_1K" | "TIER_10K" | "TIER_100K" | "TIER_UNLIMITED",
        "event": "FLAGGED" | "UNFLAGGED",
        "quality_score": "GREEN" | "YELLOW" | "RED"
    }
    
    Quality scores:
    - GREEN: High quality, no issues
    - YELLOW: Medium quality, some issues
    - RED: Low quality, at risk of being blocked
    
    Events:
    - FLAGGED: Phone number flagged due to quality issues
    - UNFLAGGED: Phone number quality restored
    """
    display_phone = value.get('display_phone_number', '')
    current_limit = value.get('current_limit', '')
    event = value.get('event', '')
    quality_score = value.get('quality_score', '')
    
    logger.info(json.dumps({
        'event': 'phone_quality_update',
        'displayPhone': display_phone,
        'currentLimit': current_limit,
        'qualityEvent': event,
        'qualityScore': quality_score,
        'requestId': request_id
    }))
    
    # Store phone quality in SystemConfig table
    _store_system_event(
        event_type='phone_quality',
        event_data={
            'displayPhone': display_phone,
            'currentLimit': current_limit,
            'event': event,
            'qualityScore': quality_score
        },
        request_id=request_id
    )
    
    # Log warning for quality issues
    if quality_score in ['YELLOW', 'RED'] or event == 'FLAGGED':
        logger.warning(json.dumps({
            'event': 'phone_quality_alert',
            'displayPhone': display_phone,
            'qualityScore': quality_score,
            'qualityEvent': event,
            'action': 'Review message quality and reduce spam complaints',
            'requestId': request_id
        }))


def _process_account_update(value: Dict, request_id: str) -> None:
    """
    Process account update webhook (messaging limits, restrictions, etc.).
    
    Webhook format for messaging limit changes:
    {
        "phone_number": "+1234567890",
        "event": "PHONE_NUMBER_MESSAGING_LIMIT_CHANGED",
        "current_limit": "TIER_1K" | "TIER_10K" | "TIER_100K" | "TIER_UNLIMITED"
    }
    
    Webhook format for account restrictions:
    {
        "event": "ACCOUNT_RESTRICTION",
        "restriction_type": "RESTRICTED_ADD_PHONE_NUMBER_ACTION" | ...
    }
    
    Messaging limit tiers:
    - TIER_1K: 1,000 business-initiated conversations per 24 hours
    - TIER_10K: 10,000 business-initiated conversations per 24 hours
    - TIER_100K: 100,000 business-initiated conversations per 24 hours
    - TIER_UNLIMITED: Unlimited business-initiated conversations
    """
    event = value.get('event', '')
    phone_number = value.get('phone_number', '')
    current_limit = value.get('current_limit', '')
    restriction_type = value.get('restriction_type', '')
    ban_info = value.get('ban_info', {})
    
    logger.info(json.dumps({
        'event': 'account_update',
        'accountEvent': event,
        'phoneNumber': phone_number,
        'currentLimit': current_limit,
        'restrictionType': restriction_type,
        'banInfo': ban_info,
        'requestId': request_id
    }))
    
    # Store account update in SystemConfig table
    _store_system_event(
        event_type='account_update',
        event_data={
            'event': event,
            'phoneNumber': phone_number,
            'currentLimit': current_limit,
            'restrictionType': restriction_type,
            'banInfo': ban_info
        },
        request_id=request_id
    )
    
    # Log messaging limit changes
    if event == 'PHONE_NUMBER_MESSAGING_LIMIT_CHANGED':
        logger.info(json.dumps({
            'event': 'messaging_limit_changed',
            'phoneNumber': phone_number,
            'newLimit': current_limit,
            'requestId': request_id
        }))
    
    # Log warnings for restrictions
    if event == 'ACCOUNT_RESTRICTION' or restriction_type:
        logger.warning(json.dumps({
            'event': 'account_restriction_alert',
            'restrictionType': restriction_type,
            'action': 'Review account in Meta Business Manager',
            'requestId': request_id
        }))
    
    # Log ban info if present
    if ban_info:
        logger.error(json.dumps({
            'event': 'account_ban_alert',
            'banInfo': ban_info,
            'action': 'Contact Meta support immediately',
            'requestId': request_id
        }))


def _store_system_event(event_type: str, event_data: Dict, request_id: str) -> None:
    """
    Store system event in SystemConfig table for dashboard display.
    Uses a composite key: whatsapp_events_{event_type}
    Stores last 10 events of each type.
    
    Note: SystemConfigTable PK is 'id', we use id=configKey for compatibility.
    """
    try:
        config_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        config_key = f'whatsapp_events_{event_type}'
        now = int(time.time())
        
        # Get existing events (PK is 'id')
        try:
            response = config_table.get_item(Key={'id': config_key})
            existing = response.get('Item', {})
            events_list = json.loads(existing.get('configValue', '[]'))
        except Exception:
            events_list = []
        
        # Add new event with timestamp
        new_event = {
            'timestamp': now,
            'data': event_data
        }
        events_list.insert(0, new_event)
        
        # Keep only last 10 events
        events_list = events_list[:10]
        
        # Store updated events (PK is 'id')
        config_table.put_item(Item={
            'id': config_key,
            'configKey': config_key,
            'configValue': json.dumps(events_list),
            'updatedAt': Decimal(str(now))
        })
        
        logger.info(json.dumps({
            'event': 'system_event_stored',
            'eventType': event_type,
            'configKey': config_key,
            'eventsCount': len(events_list),
            'requestId': request_id
        }))
        
    except dynamodb.meta.client.exceptions.ResourceNotFoundException:
        # SystemConfig table doesn't exist - skip silently
        logger.warning(json.dumps({
            'event': 'system_event_store_skipped',
            'eventType': event_type,
            'reason': 'SystemConfig table not found',
            'requestId': request_id
        }))
    except Exception as e:
        logger.error(json.dumps({
            'event': 'system_event_store_error',
            'eventType': event_type,
            'error': str(e),
            'requestId': request_id
        }))
