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
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

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
INBOUND_DLQ_URL = os.environ.get('INBOUND_DLQ_URL', '')
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')
MEDIA_PREFIX = os.environ.get('MEDIA_INBOUND_PREFIX', 'whatsapp-media/whatsapp-media-incoming/')
SEND_MODE = os.environ.get('SEND_MODE', 'LIVE')

# AI Lambda function names
AI_QUERY_KB_FUNCTION = os.environ.get('AI_QUERY_KB_FUNCTION', 'wecare-ai-query-kb')
AI_GENERATE_RESPONSE_FUNCTION = os.environ.get('AI_GENERATE_RESPONSE_FUNCTION', 'wecare-ai-generate-response')

# Outbound WhatsApp Lambda function name
OUTBOUND_WHATSAPP_FUNCTION = os.environ.get('OUTBOUND_WHATSAPP_FUNCTION', 'wecare-outbound-whatsapp')

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
    processed_count = 0
    error_count = 0
    
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
    
    # Process AI automation for supported message types
    # Text messages, interactive replies (button/list), and location
    ai_eligible_types = ['text', 'interactive', 'button', 'location']
    if msg_type in ai_eligible_types and content:
        _process_ai_automation(
            message_id=message_id,
            contact_id=contact_id,
            content=content,
            message_type=msg_type,
            phone_number_id=aws_phone_number_id,
            request_id=request_id
        )


def _extract_content(message: Dict, msg_type: str) -> str:
    """Extract message content based on type."""
    if msg_type == 'text':
        return message.get('text', {}).get('body', '')
    elif msg_type == 'image':
        return message.get('image', {}).get('caption', '[Image]')
    elif msg_type == 'video':
        return message.get('video', {}).get('caption', '[Video]')
    elif msg_type == 'audio':
        return '[Audio]'
    elif msg_type == 'document':
        doc = message.get('document', {})
        return doc.get('filename', '[Document]')
    elif msg_type == 'location':
        loc = message.get('location', {})
        return f"[Location: {loc.get('latitude')}, {loc.get('longitude')}]"
    elif msg_type == 'contacts':
        return '[Contact Card]'
    elif msg_type == 'sticker':
        return '[Sticker]'
    elif msg_type == 'reaction':
        return message.get('reaction', {}).get('emoji', '[Reaction]')
    elif msg_type == 'interactive':
        # Interactive messages (buttons, lists, etc.)
        interactive = message.get('interactive', {})
        interactive_type = interactive.get('type', '')
        if interactive_type == 'button_reply':
            return interactive.get('button_reply', {}).get('title', '[Button Reply]')
        elif interactive_type == 'list_reply':
            return interactive.get('list_reply', {}).get('title', '[List Reply]')
        elif interactive_type == 'nfm_reply':
            # Flow reply (WhatsApp Flows)
            nfm_reply = interactive.get('nfm_reply', {})
            response_json = nfm_reply.get('response_json', '')
            return f'[Flow Response: {response_json[:50]}...]' if len(response_json) > 50 else f'[Flow Response: {response_json}]'
        return f'[Interactive: {interactive_type}]'
    elif msg_type == 'button':
        # Quick reply button
        return message.get('button', {}).get('text', '[Button]')
    elif msg_type == 'order':
        return '[Order]'
    elif msg_type == 'system':
        # System messages (group changes, etc.)
        return message.get('system', {}).get('body', '[System Message]')
    elif msg_type == 'unsupported':
        # WhatsApp marks some messages as unsupported - try to extract info
        return _extract_unsupported_content(message)
    elif msg_type == 'request_welcome':
        # User clicked "Message" button on business profile
        return '[User requested to start conversation]'
    elif msg_type == 'ephemeral':
        # Disappearing message
        return '[Disappearing Message]'
    elif msg_type == 'referral':
        # Click-to-WhatsApp ads, social posts, product catalog referrals
        ref = message.get('referral', {})
        source = ref.get('source_type', 'unknown')
        headline = ref.get('headline', '')
        return f'[Referral: {source}] {headline}'.strip() if headline else f'[Referral: {source}]'
    elif msg_type == 'ad_click':
        # Click-to-WhatsApp ad click events
        ref = message.get('referral', {})
        return f'[Ad Click: {ref.get("source_url", "")}]' if ref.get('source_url') else '[Ad Click]'
    elif msg_type in ('product', 'product_inquiry'):
        # Catalog product messages
        prod = message.get(msg_type, message.get('product', {}))
        catalog_id = prod.get('catalog_id', '')
        product_id = prod.get('product_retailer_id', '')
        return f'[Product: {catalog_id}/{product_id}]' if catalog_id else f'[{msg_type.replace("_", " ").title()}]'
    elif msg_type == 'poll':
        # WhatsApp poll messages
        poll = message.get('poll', {})
        question = poll.get('question', '')
        return f'[Poll: {question[:60]}]' if question else '[Poll]'
    else:
        logger.warning(json.dumps({
            'event': 'unknown_message_type',
            'messageType': msg_type,
            'messageKeys': list(message.keys()),
            'fullMessage': message
        }))
        return f'[{msg_type}]'


def _extract_unsupported_content(message: Dict) -> str:
    """
    Extract any available information from unsupported message types.
    WhatsApp marks certain features as 'unsupported' including:
    - Live location sharing
    - Polls
    - Channels content
    - View-once messages (after viewed)
    - Certain sticker types
    - Product messages from catalogs
    
    The 'errors' array may contain hints about what type it was.
    """
    # Log the full message for debugging
    logger.info(json.dumps({
        'event': 'unsupported_message_received',
        'messageKeys': list(message.keys()),
        'fullMessage': message
    }))
    
    # Check for errors array which may contain type hints
    errors = message.get('errors', [])
    if errors:
        for error in errors:
            error_code = error.get('code', 0)
            error_title = error.get('title', '')
            error_details = error.get('details', '')
            
            logger.info(json.dumps({
                'event': 'unsupported_message_error',
                'errorCode': error_code,
                'errorTitle': error_title,
                'errorDetails': error_details
            }))
            
            # Map known error codes to message types
            # Error code 131051 = "Unsupported message type"
            if error_details:
                return f'[Unsupported: {error_details}]'
            if error_title:
                return f'[Unsupported: {error_title}]'
    
    # Check for referral (from ads, product catalogs)
    if 'referral' in message:
        referral = message.get('referral', {})
        source_type = referral.get('source_type', '')
        source_id = referral.get('source_id', '')
        if source_type:
            return f'[Referral from {source_type}]'
    
    # Check for context (reply to another message)
    if 'context' in message:
        context = message.get('context', {})
        if context.get('referred_product'):
            return '[Product Inquiry]'
    
    # Check if there's any text content hidden in the message
    for key in ['text', 'caption', 'body']:
        if key in message:
            text_content = message.get(key, {})
            if isinstance(text_content, dict):
                body = text_content.get('body', '')
                if body:
                    return body
            elif isinstance(text_content, str) and text_content:
                return text_content
    
    # Default - show that we received something but can't display it
    return '[Message type not supported by WhatsApp Business API]'


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
      key = "audio/example.ogg"  → final = "audio/example.ogg123.ogg"
      key = "audio/"             → final = "audio/123.ogg"
    
    Strategy: Use key ending with "/" so the WhatsApp mediaId (which already
    contains the correct extension) becomes the clean filename.
    Final path: {MEDIA_PREFIX}wecare-digital-{8chars}/{whatsappMediaId}.{ext}
    
    Returns the actual S3 key of the downloaded file.
    """
    try:
        # Build S3 key as a FOLDER prefix — AWS will append the mediaId as filename
        # Per AWS docs: key ending with "/" means mediaId becomes the filename
        short_id = message_id[:8]
        s3_key_prefix = f"{MEDIA_PREFIX}wecare-digital-{short_id}/"
        
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
        actual_s3_key = None
        try:
            s3_response = s3.list_objects_v2(
                Bucket=MEDIA_BUCKET,
                Prefix=s3_key_prefix,
                MaxKeys=5
            )
            contents = s3_response.get('Contents', [])
            # Filter out zero-byte folder markers
            real_files = [c for c in contents if c.get('Size', 0) > 0]
            if real_files:
                actual_s3_key = real_files[0]['Key']
                logger.info(json.dumps({
                    'event': 'media_s3_key_found',
                    'prefix': s3_key_prefix,
                    'actualS3Key': actual_s3_key,
                    'fileSize': real_files[0].get('Size', 0),
                    'requestId': request_id
                }))
        except Exception as list_err:
            logger.warning(json.dumps({
                'event': 'media_s3_list_failed',
                'prefix': s3_key_prefix,
                'error': str(list_err),
                'requestId': request_id
            }))
        
        # Fallback: construct expected key from mimeType if list failed
        if not actual_s3_key:
            ext = _get_extension_from_mime(mime_type) if mime_type else _get_extension_from_type(media_type)
            actual_s3_key = f"{s3_key_prefix}{whatsapp_media_id}{ext}"
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
    Sanitize reference_id - remove duplicate WDSR prefix and underscores.
    
    WhatsApp/Razorpay may return reference_id with extra prefixes or underscores.
    This ensures clean WDSR<ID> format for display.
    
    Examples:
    - "WDSR_WDSR41BA3534" -> "WDSR41BA3534" (remove duplicate prefix)
    - "WDSR_41BA3534" -> "WDSR41BA3534" (remove underscore)
    - "WDSR41BA3534" -> "WDSR41BA3534" (keep as-is)
    - "WDSR+41BA3534" -> "WDSR41BA3534" (remove plus sign)
    """
    import re
    
    if not reference_id:
        return reference_id
    
    # Remove all underscores and non-alphanumeric characters
    cleaned = re.sub(r'[^A-Za-z0-9]', '', reference_id).upper()
    
    # Remove ALL duplicate WDSR prefixes (handle WDSRWDSRWDSR... cases)
    while 'WDSRWDSR' in cleaned:
        cleaned = cleaned.replace('WDSRWDSR', 'WDSR')
    
    # Ensure single WDSR prefix
    if not cleaned.startswith('WDSR'):
        cleaned = f'WDSR{cleaned}'
    
    return cleaned


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
    # Sanitize reference_id - remove duplicate WDSR prefix and underscores
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
            resp = outbound_table.scan(
                FilterExpression='paymentReferenceId = :ref',
                ExpressionAttributeValues={':ref': reference_id},
                Limit=1
            )
            items = resp.get('Items', [])
            if items:
                originating_phone_id = items[0].get('phoneNumberId')
                logger.info(json.dumps({
                    'event': 'payment_phone_id_resolved',
                    'referenceId': reference_id,
                    'phoneNumberId': originating_phone_id,
                    'requestId': request_id
                }))
        except Exception as e:
            logger.warning(json.dumps({
                'event': 'payment_phone_id_lookup_failed',
                'referenceId': reference_id,
                'error': str(e),
                'requestId': request_id
            }))

    # Send order_status message based on payment status
    if payment_status == 'captured':
        _send_order_status_message(
            recipient_id=recipient_id,
            reference_id=reference_id,
            order_status='completed',
            amount=actual_amount,  # Pass amount in rupees
            description=f'Payment of ₹{actual_amount:.2f} received successfully! Thank you ✅',
            request_id=request_id,
            phone_number_id=originating_phone_id
        )
    elif payment_status == 'failed':
        _send_order_status_message(
            recipient_id=recipient_id,
            reference_id=reference_id,
            order_status='canceled',
            amount=0,
            description='Payment failed. Please try again ❌',
            request_id=request_id,
            phone_number_id=originating_phone_id
        )


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
        
        # Extract just the ID part (without WDSR prefix) for broader search
        id_part = sanitized_ref.replace('WDSR', '') if sanitized_ref.startswith('WDSR') else sanitized_ref
        
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
    if not content or not contact_id:
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
    'respondToMedia': False,
    'respondToLocation': True,
    'maxResponseLength': 500,
    'responseDelay': 0,
    'supportedLanguages': ['en', 'hi', 'hi-Latn', 'bn', 'ta', 'te', 'gu', 'mr'],
    'defaultLanguage': 'en',
    'agentId': 'Z4YAK0ZLBO',
    'agentAlias': 'WANPKHQGIB',
    'knowledgeBaseId': 'LYMQLKZNY7',
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


def _process_ai_automation(message_id: str, contact_id: str, content: str, message_type: str, phone_number_id: str, request_id: str) -> Optional[Dict]:
    """
    Process AI automation for inbound message and send auto-reply.
    
    Supports multiple message types:
    - text: Regular text messages
    - interactive: Button/list replies
    - button: Quick reply buttons
    - location: Location sharing
    
    Uses AI config from SystemConfigTable to determine behavior.
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
    }
    config_key = type_config_map.get(message_type, 'respondToText')
    should_respond = ai_config.get(config_key, True)
    
    logger.info(json.dumps({
        'event': 'ai_automation_check',
        'aiEnabled': ai_enabled,
        'messageType': message_type,
        'shouldRespond': should_respond,
        'messageId': message_id,
        'contentLength': len(content) if content else 0,
        'requestId': request_id
    }))
    
    if not ai_enabled or not should_respond:
        return None
    
    try:
        logger.info(json.dumps({
            'event': 'ai_query_kb_start',
            'messageId': message_id,
            'messageType': message_type,
            'query': content[:100] if content else '',
            'requestId': request_id
        }))
        kb_result = _invoke_ai_query_kb(content, message_id, request_id)
        logger.info(json.dumps({
            'event': 'ai_query_kb_result',
            'messageId': message_id,
            'hasResult': kb_result is not None,
            'requestId': request_id
        }))
        
        ai_response = _invoke_ai_generate_response(content, kb_result, message_id, contact_id, request_id)
        
        # Send auto-reply if we got a valid AI response
        if ai_response and ai_response.get('suggestion'):
            suggestion = ai_response.get('suggestion', '')
            max_length = ai_config.get('maxResponseLength', 500)
            if suggestion and len(suggestion) > 5:  # Only send if meaningful response
                # Truncate if needed
                if len(suggestion) > max_length:
                    suggestion = suggestion[:max_length] + '...'
                
                # Apply response delay if configured
                response_delay = ai_config.get('responseDelay', 0)
                if response_delay > 0:
                    time.sleep(min(response_delay, 5))  # Max 5 second delay
                
                _send_ai_auto_reply(
                    contact_id=contact_id,
                    content=suggestion,
                    phone_number_id=phone_number_id,
                    request_id=request_id
                )
        
        return ai_response
    except Exception as e:
        logger.error(json.dumps({
            'event': 'ai_automation_error',
            'messageId': message_id,
            'messageType': message_type,
            'error': str(e),
            'requestId': request_id
        }))
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
    """Invoke ai-generate-response Lambda function."""
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
            _store_ai_interaction(message_id, content, body.get('suggestion', ''), request_id)
            return body
        return None
    except Exception:
        return None


def _store_ai_interaction(message_id: str, query: str, response: str, request_id: str) -> None:
    """Store AI interaction record."""
    try:
        ai_table = dynamodb.Table(AI_INTERACTIONS_TABLE)
        ai_table.put_item(Item={
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
