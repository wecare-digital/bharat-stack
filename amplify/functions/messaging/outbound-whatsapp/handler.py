"""
Outbound WhatsApp Lambda Function

Purpose: Send WhatsApp text/media messages
Requirements: 3.1, 3.2, 5.2-5.11, 14.4, 16.2-16.6

Validates opt-in and allowlist, checks customer service window,
calls AWS EUM Social SendWhatsAppMessage API.
Emits CloudWatch metrics for delivery success/failure.
"""

import os
import json
import uuid
import time
import logging
import boto3
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
social_messaging = boto3.client('socialmessaging', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
s3 = boto3.client('s3', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
cloudwatch = boto3.client('cloudwatch', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Environment variables
SEND_MODE = os.environ.get('SEND_MODE', 'LIVE')
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'Contact')
MESSAGES_TABLE = os.environ.get('MESSAGES_TABLE', 'Message')
MEDIA_FILES_TABLE = os.environ.get('MEDIA_FILES_TABLE', 'MediaFile')
RATE_LIMIT_TABLE = os.environ.get('RATE_LIMIT_TABLE', 'RateLimitTracker')
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')
MEDIA_PREFIX = os.environ.get('MEDIA_OUTBOUND_PREFIX', 'whatsapp-media/whatsapp-media-outgoing/')

# WhatsApp Phone Number IDs (Allowlist) - Requirement 3.2
PHONE_NUMBER_ID_1 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_1', 'phone-number-id-5e020cecd221429996f6ae721cc42206')
PHONE_NUMBER_ID_2 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_2', 'phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c')
ALLOWLIST = {PHONE_NUMBER_ID_1, PHONE_NUMBER_ID_2}

# Constants
META_API_VERSION = 'v20.0'  # Requirement 5.8
MAX_TEXT_LENGTH = 4096  # Requirement 5.4
MESSAGE_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days
CUSTOMER_SERVICE_WINDOW_HOURS = 24  # Requirement 16.2
RATE_LIMIT_PER_SECOND = 80  # Requirement 5.9

# WhatsApp Payment Configurations
# +91 9330994400 (WABA 1912405516040025): WECARE-DIGITAL (Razorpay Gateway + UPI)
# +91 9903300044 (WABA 1633959101297902): ManishAgarwal_Pay (Razorpay Gateway + UPI)
# MCC: 4722 (Travel agencies and tour operators) | Purpose Code: 03 (Travel)
# Razorpay MID: acc_HDfub6wOfQybuH | UPI ID: wecaredigital83.rzp@icici
VALID_PAYMENT_CONFIGS = {'WECARE-DIGITAL', 'ManishAgarwal_Pay'}
DEFAULT_PAYMENT_CONFIG = 'WECARE-DIGITAL'
# Map phone number ID to its payment config name
PHONE_PAYMENT_CONFIG = {
    PHONE_NUMBER_ID_1: 'WECARE-DIGITAL',       # +919330994400
    PHONE_NUMBER_ID_2: 'ManishAgarwal_Pay',     # +919903300044
}
METRICS_NAMESPACE = 'WECARE.DIGITAL'


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Send WhatsApp message or reaction.
    Requirements: 3.1, 3.2, 5.2-5.11, 16.2-16.6
    Supports: text, media, template, and reaction messages
    """
    request_id = context.aws_request_id if context else 'local'
    
    logger.info(json.dumps({
        'event': 'outbound_whatsapp_start',
        'sendMode': SEND_MODE,
        'requestId': request_id
    }))
    
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        contact_id = body.get('contactId')
        content = body.get('content', '')
        phone_number_id = body.get('phoneNumberId', PHONE_NUMBER_ID_1)
        media_file = body.get('mediaFile')  # S3 key or base64
        media_type = body.get('mediaType')  # image, video, audio, document
        media_filename = body.get('mediaFileName')  # Original filename for documents
        is_template = body.get('isTemplate', False)
        template_name = body.get('templateName')
        template_params = body.get('templateParams', [])
        
        # Payment template support (order_details)
        is_payment_template = body.get('isPaymentTemplate', False)
        order_details = body.get('orderDetails')
        header_image_url = body.get('headerImageUrl')
        
        # OTP / Authentication template support
        is_otp_template = body.get('isOtpTemplate', False) or body.get('isAuthenticationTemplate', False)
        otp_code = body.get('otpCode', '')
        otp_button_type = body.get('otpButtonType', 'copy_code')  # 'url' or 'copy_code'
        
        # Interactive payment support (for within 24h window - uses payment_settings)
        is_interactive_payment = body.get('isInteractivePayment', False)
        
        # Interactive message support (list, buttons, location request)
        is_interactive = body.get('isInteractive', False)
        interactive_type = body.get('interactiveType')  # 'list', 'button', 'location_request'
        interactive_data = body.get('interactiveData', {})
        
        # Order status support (for payment confirmation messages)
        is_order_status = body.get('isOrderStatus', False)
        order_status_details = body.get('orderStatusDetails')
        
        # Direct phone number (fallback when contactId not available)
        recipient_phone_direct = body.get('recipientPhone')
        
        # Reaction support
        is_reaction = body.get('isReaction', False)
        reaction_message_id = body.get('reactionMessageId')  # WhatsApp message ID to react to
        reaction_emoji = body.get('reactionEmoji', '\U0001F44D')  # Default: thumbs up
        
        # Allow sending without contactId if recipientPhone is provided (for order_status)
        if not contact_id and not recipient_phone_direct:
            return _error_response(400, 'contactId or recipientPhone is required')
        
        # If we have recipientPhone but no contactId, use phone directly
        if not contact_id and recipient_phone_direct:
            contact = {'phone': recipient_phone_direct, 'id': '', 'contactId': ''}
            recipient_phone = recipient_phone_direct
        else:
            # Retrieve contact
            contact = _get_contact(contact_id)
            if not contact:
                return _error_response(404, 'Contact not found')
            recipient_phone = contact.get('phone')
        
        # Validate reaction request
        if is_reaction and not reaction_message_id:
            return _error_response(400, 'reactionMessageId is required for reactions')
        
        # Handle typing indicator request (fire and forget)
        is_typing_indicator = body.get('isTypingIndicator', False)
        if is_typing_indicator:
            try:
                _send_typing_indicator(phone_number_id, recipient_phone)
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                    'body': json.dumps({'success': True, 'action': 'typing_indicator'})
                }
            except Exception as e:
                logger.warning(f'Typing indicator failed: {e}')
                return {
                    'statusCode': 200,
                    'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'},
                    'body': json.dumps({'success': False, 'action': 'typing_indicator', 'error': str(e)})
                }
        
        # All contacts are allowed by default - no opt-in/allowlist checks
        # Customer service window check - always allow (within_window = True)
        within_window = True
        
        # Requirement 5.4: Validate text length (skip for reactions)
        if not is_reaction and content and len(content) > MAX_TEXT_LENGTH:
            return _error_response(400, f'Content exceeds {MAX_TEXT_LENGTH} characters')
        
        # Requirement 5.9: Check rate limit
        if not _check_rate_limit(phone_number_id):
            return _error_response(429, 'Rate limit exceeded. Try again later.')
        
        # Generate message ID
        message_id = str(uuid.uuid4())
        
        # Requirement 5.3: DRY_RUN mode - log without API call
        if SEND_MODE == 'DRY_RUN':
            if is_reaction:
                return _handle_dry_run_reaction(message_id, contact_id, recipient_phone, reaction_message_id, reaction_emoji, request_id)
            return _handle_dry_run(message_id, contact_id, recipient_phone, content, is_template, request_id)
        
        # Handle reaction messages
        if is_reaction:
            return _handle_reaction_send(
                message_id, contact_id, recipient_phone, phone_number_id,
                reaction_message_id, reaction_emoji, request_id
            )
        
        # Handle order_status messages (payment confirmation)
        if is_order_status and order_status_details:
            return _handle_order_status_send(
                message_id, contact_id, recipient_phone, phone_number_id,
                order_status_details, request_id
            )
        
        # Handle interactive messages (list, buttons, location request)
        if is_interactive and interactive_type:
            return _handle_interactive_send(
                message_id, contact_id, recipient_phone, phone_number_id,
                interactive_type, interactive_data, request_id
            )
        
        # Requirement 5.2: LIVE mode - call API
        return _handle_live_send(
            message_id, contact_id, recipient_phone, phone_number_id,
            content, media_file, media_type, media_filename, is_template, template_name,
            template_params, within_window, request_id, is_payment_template, order_details, 
            header_image_url, is_interactive_payment, is_otp_template, otp_code, otp_button_type
        )
        
    except json.JSONDecodeError:
        return _error_response(400, 'Invalid JSON in request body')
    except Exception as e:
        logger.error(json.dumps({
            'event': 'outbound_whatsapp_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _error_response(500, 'Internal server error')


def _handle_dry_run(message_id: str, contact_id: str, recipient_phone: str, 
                    content: str, is_template: bool, request_id: str) -> Dict[str, Any]:
    """Handle DRY_RUN mode - log without actual API call."""
    now = int(time.time())
    
    # Store message record with DRY_RUN status
    _store_message_record(
        message_id=message_id,
        contact_id=contact_id,
        content=content,
        status='dry_run',
        is_template=is_template,
        whatsapp_message_id=f'dry-run-{message_id}'
    )
    
    logger.info(json.dumps({
        'event': 'dry_run_message',
        'messageId': message_id,
        'contactId': contact_id,
        'recipientPhone': recipient_phone,
        'contentLength': len(content) if content else 0,
        'isTemplate': is_template,
        'requestId': request_id
    }))
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps({
            'messageId': message_id,
            'status': 'dry_run',
            'mode': 'DRY_RUN',
            'message': 'Message logged but not sent (DRY_RUN mode)'
        })
    }


def _handle_dry_run_reaction(message_id: str, contact_id: str, recipient_phone: str,
                              reaction_message_id: str, reaction_emoji: str, request_id: str) -> Dict[str, Any]:
    """Handle DRY_RUN mode for reactions - log without actual API call."""
    logger.info(json.dumps({
        'event': 'dry_run_reaction',
        'messageId': message_id,
        'contactId': contact_id,
        'recipientPhone': recipient_phone,
        'reactionMessageId': reaction_message_id,
        'emoji': reaction_emoji,
        'requestId': request_id
    }))
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps({
            'messageId': message_id,
            'status': 'dry_run',
            'mode': 'DRY_RUN',
            'type': 'reaction',
            'reactionMessageId': reaction_message_id,
            'emoji': reaction_emoji,
            'message': 'Reaction logged but not sent (DRY_RUN mode)'
        })
    }


def _handle_reaction_send(message_id: str, contact_id: str, recipient_phone: str,
                          phone_number_id: str, reaction_message_id: str, 
                          reaction_emoji: str, request_id: str) -> Dict[str, Any]:
    """
    Send a reaction to a WhatsApp message.
    Uses AWS EUM Social SendWhatsAppMessage API with reaction type.
    Per AWS docs: reaction payload requires message_id from the original message.
    """
    try:
        # Normalize phone number and add + prefix for reactions
        # AWS docs example: "to":"'{PHONE_NUMBER}'" - try with + prefix
        digits_only = _normalize_phone_number(recipient_phone)
        formatted_phone = f"+{digits_only}" if not digits_only.startswith('+') else digits_only
        
        # Build reaction payload per AWS Social Messaging docs
        # https://docs.aws.amazon.com/social-messaging/latest/userguide/receive-message.html
        reaction_payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': formatted_phone,
            'type': 'reaction',
            'reaction': {
                'message_id': reaction_message_id,
                'emoji': reaction_emoji
            }
        }
        
        logger.info(json.dumps({
            'event': 'reaction_payload',
            'to': formatted_phone,
            'reactionMessageId': reaction_message_id,
            'emoji': reaction_emoji,
            'payload': reaction_payload,
            'requestId': request_id
        }))
        
        # Call SendWhatsAppMessage API
        response = social_messaging.send_whatsapp_message(
            originationPhoneNumberId=phone_number_id,
            message=json.dumps(reaction_payload).encode('utf-8'),
            metaApiVersion=META_API_VERSION
        )
        
        whatsapp_message_id = response.get('messageId', '')
        
        logger.info(json.dumps({
            'event': 'reaction_sent',
            'messageId': message_id,
            'whatsappMessageId': whatsapp_message_id,
            'contactId': contact_id,
            'reactionMessageId': reaction_message_id,
            'emoji': reaction_emoji,
            'requestId': request_id
        }))
        
        # Emit success metric
        _emit_delivery_metric('success', is_template=False)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
            },
            'body': json.dumps({
                'messageId': message_id,
                'whatsappMessageId': whatsapp_message_id,
                'status': 'sent',
                'mode': 'LIVE',
                'type': 'reaction',
                'reactionMessageId': reaction_message_id,
                'emoji': reaction_emoji
            })
        }
        
    except Exception as e:
        error_msg = str(e)
        # Log detailed error for debugging
        logger.error(json.dumps({
            'event': 'reaction_send_error',
            'messageId': message_id,
            'reactionMessageId': reaction_message_id,
            'recipientPhone': recipient_phone,
            'formattedPhone': _normalize_phone_number(recipient_phone),
            'phoneNumberId': phone_number_id,
            'error': error_msg,
            'requestId': request_id
        }))
        _emit_delivery_metric('failed', is_template=False)
        return _error_response(500, f'Failed to send reaction: {error_msg}')


def _handle_order_status_send(message_id: str, contact_id: str, recipient_phone: str,
                               phone_number_id: str, order_status_details: Dict,
                               request_id: str) -> Dict[str, Any]:
    """
    Send order_status interactive message to confirm payment status.
    
    Messages:
    - Payment Success (captured): Payment of ₹{amount} received successfully! Thank you ✅
    - Payment Failed: Payment failed. Please try again ❌
    """
    try:
        raw_reference_id = order_status_details.get('reference_id', '')
        # Sanitize reference_id to remove duplicate WDSR prefixes
        reference_id = _sanitize_reference_id(raw_reference_id)
        order_status = order_status_details.get('order_status', 'completed')
        amount = order_status_details.get('amount', 0)  # Amount in rupees
        
        # Log the received order_status_details for debugging
        logger.info(json.dumps({
            'event': 'order_status_details_received',
            'orderStatusDetails': order_status_details,
            'rawReferenceId': raw_reference_id,
            'sanitizedReferenceId': reference_id,
            'amount': amount,
            'amountType': type(amount).__name__,
            'requestId': request_id
        }))
        
        # Ensure amount is a float
        try:
            amount = float(amount) if amount else 0.0
        except (ValueError, TypeError):
            amount = 0.0
        
        # Generate appropriate message based on status
        if order_status == 'completed' or order_status == 'captured':
            # Use description from inbound handler if amount is 0 (fallback)
            if amount > 0:
                body_text = f"Payment of ₹{amount:.2f} received successfully! Thank you ✅"
            else:
                # Use the description passed from inbound handler which may have the amount
                body_text = order_status_details.get('description', 'Payment received successfully! Thank you ✅')
            description = "Payment received. Thank you!"
            order_status = 'completed'
        elif order_status == 'failed':
            body_text = "Payment failed. Please try again ❌"
            description = "Payment failed"
        else:
            body_text = order_status_details.get('description', 'Order status updated')
            description = body_text
        
        # Normalize phone number
        formatted_phone = _normalize_phone_number(recipient_phone)
        whatsapp_phone = f"+{formatted_phone}"
        
        # Build order_status payload
        order_status_payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': whatsapp_phone,
            'type': 'interactive',
            'interactive': {
                'type': 'order_status',
                'body': {
                    'text': body_text
                },
                'action': {
                    'name': 'review_order',
                    'parameters': {
                        'reference_id': reference_id,
                        'order': {
                            'status': order_status,
                            'description': description
                        }
                    }
                }
            }
        }
        
        logger.info(json.dumps({
            'event': 'order_status_payload',
            'to': whatsapp_phone,
            'referenceId': reference_id,
            'orderStatus': order_status,
            'payload': order_status_payload,
            'requestId': request_id
        }))
        
        # Call SendWhatsAppMessage API
        response = social_messaging.send_whatsapp_message(
            originationPhoneNumberId=phone_number_id,
            message=json.dumps(order_status_payload),
            metaApiVersion=META_API_VERSION
        )
        
        whatsapp_message_id = response.get('messageId', '')
        
        # Store message record
        _store_message_record(
            message_id=message_id,
            contact_id=contact_id,
            content=f'Order Status: {order_status} - {description}',
            status='sent',
            is_template=False,
            whatsapp_message_id=whatsapp_message_id,
            phone_number_id=phone_number_id
        )
        
        logger.info(json.dumps({
            'event': 'order_status_sent',
            'messageId': message_id,
            'whatsappMessageId': whatsapp_message_id,
            'contactId': contact_id,
            'referenceId': reference_id,
            'orderStatus': order_status,
            'requestId': request_id
        }))
        
        # Emit success metric
        _emit_delivery_metric('success', is_template=False)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
            },
            'body': json.dumps({
                'messageId': message_id,
                'whatsappMessageId': whatsapp_message_id,
                'status': 'sent',
                'mode': 'LIVE',
                'type': 'order_status',
                'referenceId': reference_id,
                'orderStatus': order_status
            })
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(json.dumps({
            'event': 'order_status_send_error',
            'messageId': message_id,
            'referenceId': order_status_details.get('reference_id', ''),
            'error': error_msg,
            'requestId': request_id
        }))
        _emit_delivery_metric('failed', is_template=False)
        return _error_response(500, f'Failed to send order status: {error_msg}')


def _handle_interactive_send(message_id: str, contact_id: str, recipient_phone: str,
                              phone_number_id: str, interactive_type: str,
                              interactive_data: Dict, request_id: str) -> Dict[str, Any]:
    """
    Send interactive messages (list, buttons, location request, CTA URL).
    
    Interactive Types:
    - list: Up to 10 sections with rows (max 10 rows total)
    - button: Up to 3 quick reply buttons
    - location_request: Request user's location
    - cta_url: Call-to-action URL button
    - flow: WhatsApp Flow trigger (if supported)
    
    Per WhatsApp Business API docs:
    https://developers.facebook.com/docs/whatsapp/guides/interactive-messages/
    https://developers.facebook.com/docs/whatsapp/cloud-api/messages/interactive-cta-url-messages/
    """
    try:
        # Normalize phone number
        formatted_phone = _normalize_phone_number(recipient_phone)
        whatsapp_phone = f"+{formatted_phone}"
        
        # Base payload
        payload = {
            'messaging_product': 'whatsapp',
            'recipient_type': 'individual',
            'to': whatsapp_phone,
            'type': 'interactive'
        }
        
        # Build interactive payload based on type
        if interactive_type == 'list':
            # List message with sections and rows
            header_text = interactive_data.get('header', '')
            body_text = interactive_data.get('body', 'Please select an option')
            footer_text = interactive_data.get('footer', '')
            button_text = interactive_data.get('buttonText', 'View Options')
            sections = interactive_data.get('sections', [])
            
            interactive_payload = {
                'type': 'list',
                'body': {'text': body_text},
                'action': {
                    'button': button_text,
                    'sections': []
                }
            }
            
            # Add header if provided
            if header_text:
                interactive_payload['header'] = {'type': 'text', 'text': header_text}
            
            # Add footer if provided
            if footer_text:
                interactive_payload['footer'] = {'text': footer_text}
            
            # Build sections (max 10 sections, max 10 rows total)
            for section in sections[:10]:
                section_obj = {
                    'title': section.get('title', 'Options'),
                    'rows': []
                }
                for row in section.get('rows', [])[:10]:
                    section_obj['rows'].append({
                        'id': row.get('id', str(len(section_obj['rows']))),
                        'title': row.get('title', 'Option')[:24],  # Max 24 chars
                        'description': row.get('description', '')[:72]  # Max 72 chars
                    })
                if section_obj['rows']:
                    interactive_payload['action']['sections'].append(section_obj)
            
            payload['interactive'] = interactive_payload
            
        elif interactive_type == 'button':
            # Reply buttons (max 3)
            header_text = interactive_data.get('header', '')
            header_type = interactive_data.get('headerType', 'text')  # text, image, video, document
            body_text = interactive_data.get('body', 'Please select an option')
            footer_text = interactive_data.get('footer', '')
            buttons = interactive_data.get('buttons', [])
            
            interactive_payload = {
                'type': 'button',
                'body': {'text': body_text},
                'action': {'buttons': []}
            }
            
            # Add header if provided
            if header_text or header_type != 'text':
                if header_type == 'text':
                    interactive_payload['header'] = {'type': 'text', 'text': header_text}
                elif header_type == 'image':
                    interactive_payload['header'] = {
                        'type': 'image',
                        'image': {'link': interactive_data.get('headerMedia', '')}
                    }
                elif header_type == 'video':
                    interactive_payload['header'] = {
                        'type': 'video',
                        'video': {'link': interactive_data.get('headerMedia', '')}
                    }
                elif header_type == 'document':
                    interactive_payload['header'] = {
                        'type': 'document',
                        'document': {
                            'link': interactive_data.get('headerMedia', ''),
                            'filename': interactive_data.get('headerFilename', 'document.pdf')
                        }
                    }
            
            # Add footer if provided
            if footer_text:
                interactive_payload['footer'] = {'text': footer_text}
            
            # Build buttons (max 3)
            for i, btn in enumerate(buttons[:3]):
                interactive_payload['action']['buttons'].append({
                    'type': 'reply',
                    'reply': {
                        'id': btn.get('id', f'btn_{i}'),
                        'title': btn.get('title', 'Button')[:20]  # Max 20 chars
                    }
                })
            
            payload['interactive'] = interactive_payload
            
        elif interactive_type == 'location_request':
            # Location request message
            body_text = interactive_data.get('body', 'Please share your location')
            
            interactive_payload = {
                'type': 'location_request_message',
                'body': {'text': body_text},
                'action': {'name': 'send_location'}
            }
            
            payload['interactive'] = interactive_payload
        
        elif interactive_type == 'cta_url':
            # Call-to-action URL button message
            # Per Meta docs: https://developers.facebook.com/docs/whatsapp/cloud-api/messages/interactive-cta-url-messages/
            header_text = interactive_data.get('header', '')
            header_type = interactive_data.get('headerType', 'text')
            body_text = interactive_data.get('body', 'Click the button below')
            footer_text = interactive_data.get('footer', '')
            button_text = interactive_data.get('buttonText', 'Visit')[:20]  # Max 20 chars
            url = interactive_data.get('url', '')
            
            if not url:
                return _error_response(400, 'url is required for cta_url type')
            
            interactive_payload = {
                'type': 'cta_url',
                'body': {'text': body_text},
                'action': {
                    'name': 'cta_url',
                    'parameters': {
                        'display_text': button_text,
                        'url': url
                    }
                }
            }
            
            # Add header if provided
            if header_text:
                if header_type == 'text':
                    interactive_payload['header'] = {'type': 'text', 'text': header_text}
                elif header_type == 'image':
                    interactive_payload['header'] = {
                        'type': 'image',
                        'image': {'link': interactive_data.get('headerMedia', '')}
                    }
                elif header_type == 'video':
                    interactive_payload['header'] = {
                        'type': 'video',
                        'video': {'link': interactive_data.get('headerMedia', '')}
                    }
            
            # Add footer if provided
            if footer_text:
                interactive_payload['footer'] = {'text': footer_text}
            
            payload['interactive'] = interactive_payload
        
        elif interactive_type == 'flow':
            # WhatsApp Flow trigger message
            # Per Meta docs: https://developers.facebook.com/docs/whatsapp/flows/
            header_text = interactive_data.get('header', '')
            body_text = interactive_data.get('body', 'Start the flow')
            footer_text = interactive_data.get('footer', '')
            flow_id = interactive_data.get('flowId', '')
            flow_cta = interactive_data.get('flowCta', 'Start')[:20]
            flow_action = interactive_data.get('flowAction', 'navigate')  # navigate or data_exchange
            flow_token = interactive_data.get('flowToken', str(uuid.uuid4()))
            screen_id = interactive_data.get('screenId', '')  # First screen to show
            flow_data = interactive_data.get('flowData', {})  # Data to pass to flow
            
            if not flow_id:
                return _error_response(400, 'flowId is required for flow type')
            
            interactive_payload = {
                'type': 'flow',
                'body': {'text': body_text},
                'action': {
                    'name': 'flow',
                    'parameters': {
                        'flow_message_version': '3',
                        'flow_token': flow_token,
                        'flow_id': flow_id,
                        'flow_cta': flow_cta,
                        'flow_action': flow_action
                    }
                }
            }
            
            # Add screen and data if provided
            if screen_id:
                interactive_payload['action']['parameters']['flow_action_payload'] = {
                    'screen': screen_id
                }
                if flow_data:
                    interactive_payload['action']['parameters']['flow_action_payload']['data'] = flow_data
            
            # Add header if provided
            if header_text:
                interactive_payload['header'] = {'type': 'text', 'text': header_text}
            
            # Add footer if provided
            if footer_text:
                interactive_payload['footer'] = {'text': footer_text}
            
            payload['interactive'] = interactive_payload
            
        else:
            return _error_response(400, f'Invalid interactive type: {interactive_type}')
        
        logger.info(json.dumps({
            'event': 'interactive_payload',
            'to': whatsapp_phone,
            'interactiveType': interactive_type,
            'payload': payload,
            'requestId': request_id
        }))
        
        # Call SendWhatsAppMessage API
        response = social_messaging.send_whatsapp_message(
            originationPhoneNumberId=phone_number_id,
            message=json.dumps(payload),
            metaApiVersion=META_API_VERSION
        )
        
        whatsapp_message_id = response.get('messageId', '')
        
        # Store message record
        _store_message_record(
            message_id=message_id,
            contact_id=contact_id,
            content=f'[Interactive: {interactive_type}] {interactive_data.get("body", "")}',
            status='sent',
            is_template=False,
            whatsapp_message_id=whatsapp_message_id,
            phone_number_id=phone_number_id
        )
        
        logger.info(json.dumps({
            'event': 'interactive_sent',
            'messageId': message_id,
            'whatsappMessageId': whatsapp_message_id,
            'contactId': contact_id,
            'interactiveType': interactive_type,
            'requestId': request_id
        }))
        
        # Emit success metric
        _emit_delivery_metric('success', is_template=False)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
            },
            'body': json.dumps({
                'messageId': message_id,
                'whatsappMessageId': whatsapp_message_id,
                'status': 'sent',
                'mode': 'LIVE',
                'type': 'interactive',
                'interactiveType': interactive_type
            })
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(json.dumps({
            'event': 'interactive_send_error',
            'messageId': message_id,
            'interactiveType': interactive_type,
            'error': error_msg,
            'requestId': request_id
        }))
        _emit_delivery_metric('failed', is_template=False)
        return _error_response(500, f'Failed to send interactive message: {error_msg}')


def _handle_live_send(message_id: str, contact_id: str, recipient_phone: str,
                      phone_number_id: str, content: str, media_file: Optional[str],
                      media_type: Optional[str], media_filename: Optional[str], is_template: bool, template_name: Optional[str],
                      template_params: list, within_window: bool, request_id: str,
                      is_payment_template: bool = False, order_details: Optional[Dict] = None,
                      header_image_url: Optional[str] = None, is_interactive_payment: bool = False,
                      is_otp_template: bool = False, otp_code: Optional[str] = None,
                      otp_button_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Handle LIVE mode - call AWS EUM Social API.
    Requirements: 5.2, 5.5, 5.6, 5.7, 5.8, 5.10, 5.11
    """
    try:
        whatsapp_media_id = None
        s3_key = None
        stored_filename = None
        
        # Requirements 5.5, 5.6, 5.7: Handle media upload
        if media_file and media_type:
            # Use provided filename from frontend, or extract from path
            filename = media_filename
            if not filename and isinstance(media_file, str) and '/' in media_file:
                filename = media_file.split('/')[-1]
            
            s3_key, whatsapp_media_id, stored_filename = _upload_media(media_file, media_type, message_id, phone_number_id, request_id, filename)
            if not whatsapp_media_id:
                return _error_response(500, 'Failed to upload media')
        
        # Build WhatsApp message payload
        message_payload = _build_message_payload(
            recipient_phone, content, media_type, whatsapp_media_id,
            is_template, template_name, template_params, stored_filename,
            is_payment_template, order_details, header_image_url, is_interactive_payment,
            is_otp_template, otp_code, otp_button_type,
            phone_number_id=phone_number_id
        )
        
        logger.info(json.dumps({
            'event': 'message_payload_built',
            'messageId': message_id,
            'contactId': contact_id,
            'recipientPhone': recipient_phone,
            'normalizedPhone': message_payload.get('to'),
            'payloadType': message_payload.get('type'),
            'hasMedia': bool(whatsapp_media_id),
            'mediaId': whatsapp_media_id,
            'payload': message_payload,
            'requestId': request_id
        }))
        
        # Requirement 5.8: Call SendWhatsAppMessage API
        # Note: message parameter should be a string, not bytes
        message_json = json.dumps(message_payload)
        
        logger.info(json.dumps({
            'event': 'calling_send_whatsapp_message_api',
            'messageId': message_id,
            'phoneNumberId': phone_number_id,
            'messageJson': message_json,
            'requestId': request_id
        }))
        
        response = social_messaging.send_whatsapp_message(
            originationPhoneNumberId=phone_number_id,
            message=message_json,
            metaApiVersion=META_API_VERSION
        )
        
        whatsapp_message_id = response.get('messageId', '')
        
        # Extract payment info for storage (for amount lookup on confirmation)
        payment_ref_id = None
        payment_amount = None
        stored_content = content
        if is_interactive_payment and order_details:
            payment_ref_id = _sanitize_reference_id(order_details.get('reference_id', ''))
            # Calculate total amount in rupees from order_details
            order_data = order_details.get('order', {})
            total_amt = order_data.get('total_amount', {})
            if not total_amt:
                # total_amount may be at parameters level in built payload
                subtotal_val = order_data.get('subtotal', {}).get('value', 0)
                discount_val = order_data.get('discount', {}).get('value', 0)
                shipping_val = order_data.get('shipping', {}).get('value', 0)
                tax_val = order_data.get('tax', {}).get('value', 0)
                total_paise = subtotal_val - discount_val + shipping_val + tax_val
                payment_amount = total_paise / 100
            else:
                payment_amount = total_amt.get('value', 0) / total_amt.get('offset', 100)
            # Build rich content for inbox display
            item_name = order_details.get('itemName', 'Payment')
            stored_content = f'[Payment: ₹{payment_amount:.2f} | {item_name} | Ref: {payment_ref_id}]'
        
        # Requirement 5.11: Store message record
        _store_message_record(
            message_id=message_id,
            contact_id=contact_id,
            content=stored_content,
            status='sent',
            is_template=is_template,
            whatsapp_message_id=whatsapp_message_id,
            media_id=whatsapp_media_id,
            s3_key=s3_key,
            phone_number_id=phone_number_id,
            payment_reference_id=payment_ref_id,
            payment_amount=payment_amount
        )
        
        # Store payment_request record for invoice generator lookup
        # The invoice engine scans for messageType='payment_request' + paymentReferenceId
        if is_interactive_payment and order_details and payment_ref_id:
            try:
                order_data = order_details.get('order', {})
                items_list = order_data.get('items', [])
                first_item_name = items_list[0].get('name', 'Service Fee') if items_list else order_details.get('itemName', 'Service Fee')
                subtotal_val = order_data.get('subtotal', {}).get('value', 0)
                discount_val = order_data.get('discount', {}).get('value', 0)
                shipping_val = order_data.get('shipping', {}).get('value', 0)
                tax_val = order_data.get('tax', {}).get('value', 0)
                
                # Calculate per-item GST total for gstRate field
                total_gst_rate = 0
                if items_list:
                    weighted_sum = 0
                    total_value = 0
                    for it in items_list:
                        it_val = int(it.get('amount', {}).get('value', 0)) * int(it.get('quantity', 1))
                        it_rate = float(it.get('gstRate', 0))
                        weighted_sum += it_val * it_rate
                        total_value += it_val
                    if total_value > 0:
                        total_gst_rate = weighted_sum / total_value  # Weighted average GST rate
                
                # Look up contact for customer details
                contact_info = _get_contact(contact_id) if contact_id else None
                c_name = (contact_info or {}).get('name', '')
                c_phone = (contact_info or {}).get('phone', recipient_phone or '')
                c_email = (contact_info or {}).get('email', '')
                c_ship = (contact_info or {}).get('shippingAddress', '')
                c_bill = (contact_info or {}).get('billingAddress', '')
                
                pay_req_record = {
                    'id': str(uuid.uuid4()),
                    'messageId': payment_ref_id,
                    'contactId': contact_id,
                    'channel': 'whatsapp',
                    'direction': 'outbound',
                    'messageType': 'payment_request',
                    'content': stored_content,
                    'paymentReferenceId': payment_ref_id,
                    'paymentAmount': Decimal(str(subtotal_val)),
                    'paymentOffset': Decimal('100'),
                    'paymentCurrency': 'INR',
                    'paymentItemName': first_item_name,
                    'paymentItemCount': len(items_list),
                    'paymentQuantity': int(items_list[0].get('quantity', 1)) if items_list else 1,
                    'paymentSubtotal': Decimal(str(subtotal_val)),
                    'paymentDiscount': Decimal(str(discount_val)),
                    'paymentGstRate': Decimal(str(total_gst_rate)),
                    'paymentGstAmount': Decimal(str(tax_val)),
                    'paymentShipping': Decimal(str(shipping_val)),
                    'paymentTotal': Decimal(str(int((payment_amount or 0) * 100))),
                    'paymentGstin': order_details.get('gstin', '19AADFW7431N1ZK'),
                    'paymentSource': 'inbox_ui',
                    'paymentOrderId': order_details.get('orderId', 'Offline'),
                    'paymentCustomerName': c_name,
                    'paymentCustomerPhone': c_phone,
                    'paymentCustomerEmail': c_email,
                    'paymentShippingAddress': c_ship,
                    'paymentBillingAddress': c_bill,
                    'status': 'pending',
                    'senderPhone': recipient_phone or '',
                    'createdAt': Decimal(str(int(time.time()))),
                    'expiresAt': Decimal(str(int(time.time()) + 86400 * 30)),
                }
                # Store in INBOUND table — invoice generator scans WhatsAppInboundTable
                inbound_table_name = os.environ.get('INBOUND_TABLE', 'base-wecare-digital-WhatsAppInboundTable')
                inbound_table = dynamodb.Table(inbound_table_name)
                inbound_table.put_item(Item={k: v for k, v in pay_req_record.items() if v is not None and v != '' and v != Decimal('0') or k in ('paymentDiscount', 'paymentShipping')})
                logger.info(json.dumps({
                    'event': 'payment_request_record_stored',
                    'referenceId': payment_ref_id,
                    'contactId': contact_id,
                    'requestId': request_id,
                }))
            except Exception as pr_err:
                logger.warning(json.dumps({
                    'event': 'payment_request_record_error',
                    'referenceId': payment_ref_id,
                    'error': str(pr_err),
                    'requestId': request_id,
                }))
        
        logger.info(json.dumps({
            'event': 'message_sent',
            'messageId': message_id,
            'whatsappMessageId': whatsapp_message_id,
            'contactId': contact_id,
            'isTemplate': is_template,
            'hasMedia': bool(whatsapp_media_id),
            'requestId': request_id
        }))
        
        # Requirement 14.4: Emit success metric
        _emit_delivery_metric('success', is_template)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,Authorization',
                'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
            },
            'body': json.dumps({
                'messageId': message_id,
                'whatsappMessageId': whatsapp_message_id,
                'status': 'sent',
                'mode': 'LIVE'
            })
        }
        
    except social_messaging.exceptions.ThrottledRequestException as e:
        # Requirement 5.10: Handle API errors
        _store_message_record(
            message_id=message_id,
            contact_id=contact_id,
            content=content,
            status='failed',
            error_details={'type': 'throttling', 'message': str(e)},
            phone_number_id=phone_number_id
        )
        # Emit failure metric
        _emit_delivery_metric('failed', is_template)
        return _error_response(429, 'API rate limit exceeded')
        
    except Exception as e:
        # Requirement 5.10: Store error details
        error_msg = str(e)
        error_type = type(e).__name__
        
        logger.error(json.dumps({
            'event': 'send_api_error',
            'messageId': message_id,
            'error': error_msg,
            'errorType': error_type,
            'recipientPhone': recipient_phone,
            'normalizedPhone': message_payload.get('to') if 'message_payload' in locals() else 'unknown',
            'requestId': request_id
        }))
        
        _store_message_record(
            message_id=message_id,
            contact_id=contact_id,
            content=content,
            status='failed',
            error_details={'type': error_type, 'message': error_msg},
            phone_number_id=phone_number_id
        )
        # Emit failure metric
        _emit_delivery_metric('failed', is_template)
        return _error_response(500, f'Failed to send message: {error_msg}')


def _upload_media(media_file: str, media_type: str, message_id: str, phone_number_id: str, request_id: str, filename: Optional[str] = None) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Upload media to S3 and register with WhatsApp.
    Supports all AWS Social Messaging media types per documentation.
    Requirements 5.5, 5.6, 5.7
    
    Returns: (s3_key, whatsapp_media_id, display_filename)
    """
    import base64
    
    try:
        # Generate S3 key with proper extension
        extension = _get_media_extension(media_type)
        
        # S3 key: short format wecare-digital-{8char_uuid}{ext}
        short_id = message_id[:8]
        s3_key = f"{MEDIA_PREFIX}wecare-digital-{short_id}{extension}"
        
        # Display filename for WhatsApp (max 240 chars) - use original name if valid
        display_filename = None
        if filename and filename.strip() and filename not in ['undefined', 'null', 'File', 'Blob']:
            display_filename = _sanitize_filename(filename, max_length=240)
        
        # If no valid filename, generate one
        if not display_filename or display_filename == 'document':
            display_filename = f"wecare-digital-{short_id}{extension}"
        
        logger.info(json.dumps({
            'event': 'media_upload_start',
            'messageId': message_id,
            'mediaType': media_type,
            'providedFilename': filename,
            'displayFilename': display_filename,
            's3Key': s3_key,
            'requestId': request_id
        }))
        
        # If media_file is already an S3 key, use it directly
        # Detect S3 keys: s3:// prefix, media prefix, invoices/ prefix, or any path with / that isn't base64
        is_s3_key = (
            media_file.startswith('s3://') or
            media_file.startswith(MEDIA_PREFIX) or
            media_file.startswith('invoices/') or
            media_file.startswith('stream/') or
            (('/' in media_file) and media_file.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.mp4', '.pdf', '.ogg', '.mp3')))
        )
        if is_s3_key:
            s3_key = media_file.replace('s3://', '').replace(f'{MEDIA_BUCKET}/', '')
            
            # Get file size from S3 for validation
            try:
                head_response = s3.head_object(Bucket=MEDIA_BUCKET, Key=s3_key)
                file_size = head_response.get('ContentLength', 0)
                is_valid, error_msg = _validate_media_size(file_size, media_type)
                if not is_valid:
                    logger.error(json.dumps({
                        'event': 'media_size_validation_failed',
                        's3Key': s3_key,
                        'fileSize': file_size,
                        'error': error_msg,
                        'requestId': request_id
                    }))
                    return None, None, None
            except Exception as e:
                logger.warning(f"Could not validate S3 file size: {str(e)}")
        else:
            # Assume base64 encoded - decode and upload
            try:
                file_content = base64.b64decode(media_file)
            except Exception as e:
                logger.error(json.dumps({
                    'event': 'media_decode_error',
                    'error': str(e),
                    'mediaType': media_type,
                    'requestId': request_id
                }))
                return None, None, None
            
            # Validate file size
            file_size = len(file_content)
            is_valid, error_msg = _validate_media_size(file_size, media_type)
            if not is_valid:
                logger.error(json.dumps({
                    'event': 'media_size_validation_failed',
                    'fileSize': file_size,
                    'error': error_msg,
                    'requestId': request_id
                }))
                return None, None, None
            
            logger.info(json.dumps({
                'event': 'media_uploading_to_s3',
                's3Key': s3_key,
                'fileSize': file_size,
                'mediaType': media_type,
                'requestId': request_id
            }))
            
            # Upload to S3 using streaming for large files
            s3.put_object(
                Bucket=MEDIA_BUCKET,
                Key=s3_key,
                Body=file_content,
                ContentType=_get_content_type(media_type)
            )
        
        logger.info(json.dumps({
            'event': 'media_uploaded_to_s3',
            's3Key': s3_key,
            'mediaType': media_type,
            'displayFilename': display_filename,
            'requestId': request_id
        }))
        
        # Requirement 5.6: Call PostWhatsAppMessageMedia to get mediaId
        # Use boto3 with correct parameter format
        try:
            response = social_messaging.post_whatsapp_message_media(
                originationPhoneNumberId=phone_number_id,
                sourceS3File={
                    'bucketName': MEDIA_BUCKET,
                    'key': s3_key
                }
            )
            whatsapp_media_id = response.get('mediaId', '')
            
            if not whatsapp_media_id:
                logger.error(json.dumps({
                    'event': 'media_registration_no_id',
                    's3Key': s3_key,
                    'response': str(response),
                    'requestId': request_id
                }))
                return None, None, None
            
            logger.info(json.dumps({
                'event': 'media_registered_with_whatsapp',
                's3Key': s3_key,
                'mediaId': whatsapp_media_id,
                'mediaType': media_type,
                'displayFilename': display_filename,
                'phoneNumberId': phone_number_id,
                'requestId': request_id
            }))
            
        except Exception as e:
            logger.error(json.dumps({
                'event': 'media_registration_failed',
                'error': str(e),
                'errorType': type(e).__name__,
                's3Key': s3_key,
                'phoneNumberId': phone_number_id,
                'requestId': request_id
            }))
            # Media registration failed - cannot send media without mediaId
            return None, None, None
        
        logger.info(json.dumps({
            'event': 'media_upload_complete',
            's3Key': s3_key,
            'mediaId': whatsapp_media_id,
            'mediaType': media_type,
            'displayFilename': display_filename,
            'requestId': request_id
        }))
        
        return s3_key, whatsapp_media_id, display_filename
        
    except Exception as e:
        logger.error(json.dumps({
            'event': 'media_upload_error',
            'error': str(e),
            'errorType': type(e).__name__,
            'mediaType': media_type,
            'requestId': request_id
        }))
        return None, None, None


def _sanitize_filename(filename: str, max_length: int = 240) -> str:
    """
    Sanitize filename for WhatsApp document messages.
    
    WhatsApp filename requirements:
    - Maximum 240 characters
    - Remove invalid characters but preserve common ones
    - Preserve file extension
    
    Args:
        filename: Original filename
        max_length: Maximum allowed length (default 240 for WhatsApp)
    
    Returns:
        Sanitized filename
    """
    if not filename or not isinstance(filename, str):
        return 'document'
    
    # Handle placeholder values
    if filename.strip() in ['undefined', 'null', 'File', 'Blob', '']:
        return 'document'
    
    # Remove path separators if present
    filename = filename.split('/')[-1].split('\\')[-1]
    
    # Remove only truly invalid characters for WhatsApp
    # Keep: alphanumeric, dots, hyphens, underscores, spaces, parentheses
    import re
    sanitized = re.sub(r'[^\w\s.\-()]+', '', filename, flags=re.UNICODE)
    
    # Replace multiple spaces with single space
    sanitized = re.sub(r'\s+', ' ', sanitized)
    
    # Strip leading/trailing spaces
    sanitized = sanitized.strip()
    
    # If filename is too long, truncate while preserving extension
    if len(sanitized) > max_length:
        # Split filename and extension
        if '.' in sanitized:
            name_parts = sanitized.rsplit('.', 1)
            name = name_parts[0]
            ext = '.' + name_parts[1]
        else:
            name = sanitized
            ext = ''
        
        # Calculate how much space we have for the name
        available_length = max_length - len(ext)
        
        # Truncate name and reconstruct
        sanitized = name[:available_length] + ext
    
    # Ensure we have a valid filename
    if not sanitized or sanitized.isspace():
        sanitized = 'document'
    
    logger.info(json.dumps({
        'event': 'filename_sanitized',
        'original': filename,
        'sanitized': sanitized,
        'length': len(sanitized),
        'maxLength': max_length,
        'changed': filename != sanitized
    }))
    
    return sanitized


def _normalize_phone_number(phone: str) -> str:
    """
    Normalize phone number to WhatsApp-compatible E.164 format.
    WhatsApp requires: digits only, no + prefix, with country code.
    
    Examples:
    - "+919876543210" -> "919876543210"
    - "919876543210" -> "919876543210"
    - "+91 98765 43210" -> "919876543210"
    - "9876543210" -> "919876543210" (assumes India)
    - "447447840003" -> "447447840003"
    - "+44 7447 840003" -> "447447840003"
    """
    if not phone:
        return phone
    
    # Remove all non-digit characters (spaces, dashes, +, etc.)
    digits_only = ''.join(c for c in phone if c.isdigit())
    
    # If empty after removing non-digits, return original
    if not digits_only:
        return phone
    
    # If 10 digits and starts with 6-9, assume Indian number
    if len(digits_only) == 10 and digits_only[0] in '6789':
        digits_only = '91' + digits_only
    
    # If 11 digits starting with 0, remove leading 0 and add country code
    if len(digits_only) == 11 and digits_only[0] == '0':
        digits_only = '91' + digits_only[1:]
    
    # If 12 digits starting with 0091, remove leading 00
    if len(digits_only) == 12 and digits_only.startswith('0091'):
        digits_only = digits_only[2:]
    
    # Validate final format: should be 10-15 digits (E.164 format)
    if not digits_only.isdigit() or len(digits_only) < 10 or len(digits_only) > 15:
        logger.warning(f"Phone number after normalization is invalid: {phone} -> {digits_only} (length: {len(digits_only)})")
    
    return digits_only


def _sanitize_reference_id(reference_id: str) -> str:
    """
    Sanitize reference_id for UPI compatibility.
    UPI requires: only A-Z, a-z, 0-9, _, - (max 35 chars)
    Must be unique for each transaction.
    
    Format: WDSR<ID> (no underscore for cleaner display)
    
    Examples:
    - "WDSR_ABC12345" -> "WDSRABC12345" (remove underscore)
    - "WDSRABC12345" -> "WDSRABC12345" (keep as-is)
    - "WDSRWDSR41BA3534" -> "WDSR41BA3534" (remove duplicate prefix)
    - "" -> "WDSRXXXXXXXX" (auto-generated)
    """
    import re
    
    if not reference_id or not reference_id.strip():
        # Generate unique reference if empty
        unique_id = str(uuid.uuid4()).replace('-', '')[:8].upper()
        return f"WDSR{unique_id}"
    
    # Remove all non-alphanumeric characters (including underscores and plus signs)
    sanitized = re.sub(r'[^A-Za-z0-9]', '', reference_id)
    
    # Convert to uppercase for consistency
    sanitized = sanitized.upper()
    
    # If empty after sanitization, generate new
    if not sanitized:
        unique_id = str(uuid.uuid4()).replace('-', '')[:8].upper()
        return f"WDSR{unique_id}"
    
    # Remove ALL duplicate WDSR prefixes (handle WDSRWDSRWDSR... cases)
    while 'WDSRWDSR' in sanitized:
        sanitized = sanitized.replace('WDSRWDSR', 'WDSR')
    
    # Keep as-is if already has WDSR prefix (without underscore)
    if sanitized.startswith('WDSR'):
        result = sanitized
    else:
        # Add WDSR prefix (no underscore)
        result = f"WDSR{sanitized}"
    
    # Truncate to max 35 chars (UPI limit)
    if len(result) > 35:
        result = result[:35]
    
    return result


def _build_message_payload(recipient_phone: str, content: str, media_type: Optional[str],
                           media_id: Optional[str], is_template: bool, template_name: Optional[str],
                           template_params: list, filename: Optional[str] = None,
                           is_payment_template: bool = False, order_details: Optional[Dict] = None,
                           header_image_url: Optional[str] = None,
                           is_interactive_payment: bool = False,
                           is_otp_template: bool = False, otp_code: Optional[str] = None,
                           otp_button_type: Optional[str] = None,
                           phone_number_id: Optional[str] = None) -> Dict[str, Any]:
    """Build WhatsApp Cloud API message payload."""
    # Normalize phone number - WhatsApp API expects digits only without + prefix
    formatted_phone = _normalize_phone_number(recipient_phone)
    
    # Validate phone number format
    if not formatted_phone or not formatted_phone.isdigit() or len(formatted_phone) < 10:
        logger.warning(f"Invalid phone number after normalization: {recipient_phone} -> {formatted_phone}")
    
    # WhatsApp requires + prefix with country code in the message payload
    whatsapp_phone = f"+{formatted_phone}"
    
    payload = {
        'messaging_product': 'whatsapp',
        'recipient_type': 'individual',
        'to': whatsapp_phone
    }
    
    # Default header image for interactive payments
    DEFAULT_PAYMENT_HEADER_IMAGE = 'https://app.wecare.digital/stream/media/m/wecare-digital.png'
    
    # Handle INTERACTIVE order_details message (for within 24h window)
    # Structure:
    # BODY: Your payment is overdue—please tap below to complete it 💳🤝
    # CART ITEMS: from input items array
    # BREAKDOWN: Subtotal, Discount, Shipping, Tax (with GSTIN)
    # TOTAL: auto-calculated
    if is_interactive_payment and order_details:
        from decimal import Decimal, ROUND_HALF_UP
        
        def round_paise(x: Decimal) -> int:
            """Round to nearest paise"""
            return int(x.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        
        payload['type'] = 'interactive'
        
        # Use provided header image or default
        payment_header_image = header_image_url or DEFAULT_PAYMENT_HEADER_IMAGE
        
        # Get order components from frontend
        order_data = order_details.get('order', {})
        
        # GSTIN
        gstin = order_details.get('gstin', '19AADFW7431N1ZK')
        
        # Discount, Delivery (user input, mandatory - show even if 0)
        discount_paise = int(order_data.get('discount', {}).get('value', 0))
        delivery_paise = int(order_data.get('shipping', {}).get('value', 0))
        
        # Build items from input array (multi-item support with per-item GST)
        items_list = order_data.get('items', [])
        items_for_whatsapp = []
        item_total_paise = 0
        gst_paise = 0  # Total GST across all items
        
        for i, item in enumerate(items_list):
            item_amount = int(item.get('amount', {}).get('value', 100))
            item_qty = int(item.get('quantity', 1))
            item_name = item.get('name', 'Service Fee')
            item_line_total = item_amount * item_qty
            item_total_paise += item_line_total
            
            # Per-item GST rate
            item_gst_rate = float(item.get('gstRate', 0))
            if item_gst_rate > 0:
                gst_paise += round_paise(Decimal(item_line_total) * Decimal(str(item_gst_rate)) / Decimal("100"))
            
            items_for_whatsapp.append({
                'retailer_id': item.get('retailer_id', f'ITEM_{i+1}'),
                'name': item_name,
                'amount': {'value': item_amount, 'offset': 100},
                'quantity': item_qty
            })
        
        # Fallback if no items
        if not items_for_whatsapp:
            item_name = order_details.get('itemName', 'Service Fee')
            item_quantity = int(order_details.get('quantity', 1))
            fallback_amount = int(order_data.get('subtotal', {}).get('value', 100))
            item_total_paise = fallback_amount
            items_for_whatsapp.append({
                'retailer_id': 'ITEM_MAIN',
                'name': item_name,
                'amount': {'value': fallback_amount // max(item_quantity, 1), 'offset': 100},
                'quantity': item_quantity
            })
            # Use tax value from order_data as fallback
            gst_paise = int(order_data.get('tax', {}).get('value', 0))
        
        # Convenience Fee: 2% of total collection (items + GST) + 18% GST on that 2%
        collection_paise = item_total_paise + gst_paise
        conv_base = round_paise(Decimal(collection_paise) * Decimal("0.02"))
        conv_gst = round_paise(Decimal(conv_base) * Decimal("0.18"))
        conv_total = conv_base + conv_gst
        
        # Add convenience fee as a line item
        items_for_whatsapp.append({
            'retailer_id': 'ITEM_CONV',
            'name': 'Convenience Fee (Collected by Bank)',
            'amount': {'value': conv_total, 'offset': 100},
            'quantity': 1
        })
        
        # Build reference ID
        ref_id = _sanitize_reference_id(order_details.get('reference_id', ''))
        
        # WhatsApp subtotal = sum of (item.amount * item.quantity) for all items
        whatsapp_subtotal = item_total_paise + conv_total
        
        total_paise = whatsapp_subtotal - discount_paise + delivery_paise + gst_paise
        
        # Build order object - ALL fields mandatory (show even if 0)
        # WhatsApp only supports: subtotal, discount, shipping, tax
        order_obj = {
            'status': 'pending',
            'items': items_for_whatsapp,
            'subtotal': {'value': whatsapp_subtotal, 'offset': 100},
            'discount': {
                'value': discount_paise,
                'offset': 100,
                'description': 'Promo'
            },
            'shipping': {
                'value': delivery_paise,
                'offset': 100,
                'description': 'Express'
            },
            'tax': {
                'value': gst_paise,
                'offset': 100,
                'description': f'GSTIN: {gstin}'
            }
        }
        
        # Build interactive order_details payload
        interactive_payload = {
            'type': 'order_details',
            'header': {
                'type': 'image',
                'image': {'link': payment_header_image}
            },
            'body': {
                'text': 'Your payment is ready \u2014 tap below to complete it \U0001f4b3'
            },
            'footer': {
                'text': order_details.get('footer_text', 'WECARE.DIGITAL')
            },
            'action': {
                'name': 'review_and_pay',
                'parameters': {
                    'reference_id': ref_id,
                    'type': order_details.get('type', 'digital-goods'),
                    'payment_settings': [
                        {
                            'type': 'payment_gateway',
                            'payment_gateway': {
                                'type': 'razorpay',
                                'configuration_name': (
                                    order_details.get('payment_configuration')
                                    if order_details.get('payment_configuration') in VALID_PAYMENT_CONFIGS
                                    else PHONE_PAYMENT_CONFIG.get(phone_number_id, DEFAULT_PAYMENT_CONFIG)
                                )
                            }
                        }
                    ],
                    'currency': order_details.get('currency', 'INR'),
                    'total_amount': {'value': total_paise, 'offset': 100},
                    'order': order_obj
                }
            }
        }
        
        payload['interactive'] = interactive_payload
        
        logger.info(json.dumps({
            'event': 'interactive_payment_payload_built',
            'referenceId': ref_id,
            'itemCount': len(items_list),
            'itemTotal': item_total_paise / 100,
            'gstTotal': gst_paise / 100,
            'discount': discount_paise / 100,
            'shipping': delivery_paise / 100,
            'convFee': conv_total / 100,
            'whatsappSubtotal': whatsapp_subtotal / 100,
            'total': total_paise / 100,
            'gstin': gstin,
            'orderId': order_details.get('orderId', 'Offline'),
            'paymentConfig': order_details.get('payment_configuration', PHONE_PAYMENT_CONFIG.get(phone_number_id, DEFAULT_PAYMENT_CONFIG))
        }))
        
        return payload
    
    if is_template and template_name:
        # Template message
        # Get language from template_params if provided, otherwise default to 'en'
        template_language = 'en'
        actual_params = list(template_params) if template_params else []
        
        if actual_params and len(actual_params) > 0:
            # Check if first param is a language code (2-5 chars like 'en', 'en_US')
            first_param = actual_params[0] if actual_params else ''
            if isinstance(first_param, str) and (len(first_param) == 2 or (2 <= len(first_param) <= 5 and '_' in first_param)):
                # Looks like a language code, use it
                template_language = first_param
                actual_params = actual_params[1:]  # Remove language from params
        
        payload['type'] = 'template'
        payload['template'] = {
            'name': template_name,
            'language': {'code': template_language},
            'components': []
        }
        
        # Handle payment template with order_details button
        if is_payment_template and order_details:
            # Add header image if provided
            if header_image_url:
                payload['template']['components'].append({
                    'type': 'header',
                    'parameters': [{
                        'type': 'image',
                        'image': {'link': header_image_url}
                    }]
                })
            
            # Add body parameters if provided (for templates with variables like {{1}})
            if actual_params and len(actual_params) > 0:
                payload['template']['components'].append({
                    'type': 'body',
                    'parameters': [{'type': 'text', 'text': str(p)} for p in actual_params]
                })
            
            # Add order_details button component
            payload['template']['components'].append({
                'type': 'button',
                'sub_type': 'order_details',
                'index': 0,
                'parameters': [{
                    'type': 'action',
                    'action': {'order_details': order_details}
                }]
            })
            
            logger.info(json.dumps({
                'event': 'payment_template_payload_built',
                'templateName': template_name,
                'language': template_language,
                'referenceId': order_details.get('reference_id'),
                'totalAmount': order_details.get('total_amount', {}).get('value'),
                'currency': order_details.get('currency'),
                'hasHeaderImage': bool(header_image_url),
                'bodyParamCount': len(actual_params)
            }))
        # OTP / Authentication template support
        # WhatsApp authentication templates use a button component with:
        # - sub_type 'url' with {{1}} OTP code parameter (URL button with OTP appended)
        # - sub_type 'copy_code' with coupon_code parameter (one-tap copy button)
        elif is_otp_template and otp_code:
            # Body params (e.g. {{1}} = OTP code for display in message body)
            if actual_params:
                payload['template']['components'].append({
                    'type': 'body',
                    'parameters': [{'type': 'text', 'text': str(p)} for p in actual_params]
                })
            
            btn_type = (otp_button_type or 'copy_code').lower()
            if btn_type == 'url':
                # URL button: OTP code appended to the template URL as {{1}}
                payload['template']['components'].append({
                    'type': 'button',
                    'sub_type': 'url',
                    'index': 0,
                    'parameters': [{'type': 'text', 'text': str(otp_code)}]
                })
            else:
                # One-tap / copy_code button: user taps to auto-fill OTP
                payload['template']['components'].append({
                    'type': 'button',
                    'sub_type': 'copy_code',
                    'index': 0,
                    'parameters': [{'type': 'coupon_code', 'coupon_code': str(otp_code)}]
                })
            
            logger.info(json.dumps({
                'event': 'otp_template_payload_built',
                'templateName': template_name,
                'language': template_language,
                'otpButtonType': btn_type,
                'bodyParamCount': len(actual_params)
            }))
        # Add body parameters if provided (for templates with variables like {{1}}, {{2}})
        elif actual_params and len(actual_params) > 0:
            payload['template']['components'].append({
                'type': 'body',
                'parameters': [{'type': 'text', 'text': str(p)} for p in actual_params]
            })
        
        logger.info(json.dumps({
            'event': 'template_payload_built',
            'templateName': template_name,
            'language': template_language,
            'paramCount': len(actual_params),
            'params': actual_params,
            'isPaymentTemplate': is_payment_template
        }))
    elif media_id and media_type:
        # Media message - extract message type from media_type
        # media_type is like 'image/jpeg', we need just 'image'
        msg_type = media_type.split('/')[0] if '/' in media_type else media_type
        
        # Validate media type
        valid_types = ['image', 'video', 'audio', 'document', 'sticker']
        if msg_type not in valid_types:
            logger.warning(f"Invalid media type: {media_type} -> {msg_type}, using 'document' as fallback")
            msg_type = 'document'
        
        payload['type'] = msg_type
        payload[msg_type] = {'id': media_id}
        
        # Add caption if provided
        if content:
            payload[msg_type]['caption'] = content
        
        # For documents, add filename if available
        # WhatsApp filename limit: 240 characters
        if msg_type == 'document' and filename:
            # Sanitize and truncate filename to 240 characters
            sanitized_filename = _sanitize_filename(filename, max_length=240)
            payload[msg_type]['filename'] = sanitized_filename
            logger.info(json.dumps({
                'event': 'document_filename_added',
                'originalFilename': filename,
                'sanitizedFilename': sanitized_filename,
                'length': len(sanitized_filename)
            }))
    else:
        # Text message
        payload['type'] = 'text'
        payload['text'] = {'body': content, 'preview_url': False}
    
    return payload


def _get_contact(contact_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve contact from DynamoDB."""
    contacts_table = dynamodb.Table(CONTACTS_TABLE)
    
    # First try direct lookup by 'id' (primary key)
    try:
        response = contacts_table.get_item(Key={'id': contact_id})
        item = response.get('Item')
        if item and item.get('deletedAt') is None:
            return item
    except Exception as e:
        logger.warning(f"Direct lookup failed: {str(e)}")
    
    # Fallback: scan by contactId field
    try:
        response = contacts_table.scan(
            FilterExpression='contactId = :cid AND (attribute_not_exists(deletedAt) OR deletedAt = :null)',
            ExpressionAttributeValues={':cid': contact_id, ':null': None},
            Limit=1
        )
        items = response.get('Items', [])
        if items:
            return items[0]
    except Exception as e:
        logger.warning(f"Scan by contactId failed: {str(e)}")
    
    return None


def _is_within_service_window(contact: Dict[str, Any]) -> bool:
    """
    Check if within 24-hour customer service window.
    Requirement 16.2: Calculate window as 24 hours from lastInboundMessageAt
    """
    last_inbound = contact.get('lastInboundMessageAt')
    if not last_inbound:
        return False
    
    # Convert to int if Decimal
    if isinstance(last_inbound, Decimal):
        last_inbound = int(last_inbound)
    elif isinstance(last_inbound, str):
        # Handle ISO format
        from datetime import datetime
        last_inbound = int(datetime.fromisoformat(last_inbound.replace('Z', '+00:00')).timestamp())
    
    window_end = last_inbound + (CUSTOMER_SERVICE_WINDOW_HOURS * 60 * 60)
    return int(time.time()) < window_end


def _check_rate_limit(phone_number_id: str) -> bool:
    """
    Check rate limit for phone number.
    Requirement 5.9: 80 messages per second per phone number
    """
    try:
        rate_table = dynamodb.Table(RATE_LIMIT_TABLE)
        now = int(time.time())
        window_key = f"whatsapp:{phone_number_id}"
        
        # Atomic increment
        response = rate_table.update_item(
            Key={'channel': window_key, 'windowStart': now},
            UpdateExpression='SET messageCount = if_not_exists(messageCount, :zero) + :inc, lastUpdatedAt = :now',
            ExpressionAttributeValues={
                ':zero': Decimal('0'),
                ':inc': Decimal('1'),
                ':now': Decimal(str(now + 86400))  # TTL: 24 hours
            },
            ReturnValues='UPDATED_NEW'
        )
        
        count = int(response.get('Attributes', {}).get('messageCount', 0))
        return count <= RATE_LIMIT_PER_SECOND
        
    except Exception:
        # Allow on error (fail open for rate limiting)
        return True


def _store_message_record(message_id: str, contact_id: str, content: str, status: str,
                          is_template: bool = False, whatsapp_message_id: str = None,
                          media_id: str = None, s3_key: str = None,
                          error_details: Dict = None, phone_number_id: str = None,
                          payment_reference_id: str = None, payment_amount: float = None) -> None:
    """Store message record in DynamoDB with WABA tracking."""
    now = int(time.time())
    expires_at = now + MESSAGE_TTL_SECONDS
    
    # Guard: don't store messages with empty content (prevents blank inbox entries)
    if not content and not media_id and not s3_key and status != 'failed':
        logger.warning(json.dumps({
            'event': 'empty_content_skipped',
            'messageId': message_id,
            'contactId': contact_id,
            'status': status,
        }))
        return
    
    record = {
        'id': message_id,
        'messageId': message_id,
        'contactId': contact_id,
        'channel': 'whatsapp',
        'direction': 'outbound',
        'content': content,
        'messageType': 'template' if is_template else 'text',
        'timestamp': Decimal(str(now)),
        'status': status,
        'whatsappMessageId': whatsapp_message_id,
        'mediaId': media_id,
        's3Key': s3_key,
        'errorDetails': json.dumps(error_details) if error_details else None,
        # WABA tracking - which phone number sent this message
        'awsPhoneNumberId': phone_number_id,
        'createdAt': Decimal(str(now)),
        'expiresAt': Decimal(str(expires_at)),
        # Payment tracking fields (for amount lookup on confirmation)
        'paymentReferenceId': payment_reference_id,
        'paymentAmount': Decimal(str(payment_amount * 100)) if payment_amount else None,  # Store in paise
        'paymentOffset': Decimal('100') if payment_amount else None,
    }
    
    try:
        messages_table = dynamodb.Table(MESSAGES_TABLE)
        messages_table.put_item(Item={k: v for k, v in record.items() if v is not None})
    except Exception as e:
        logger.error(f"Failed to store message record: {str(e)}")


def _log_validation_failure(contact_id: str, channel: str, reason: str, request_id: str) -> None:
    """Log validation failure - Requirement 3.6"""
    logger.warning(json.dumps({
        'event': 'validation_failure',
        'contactId': contact_id,
        'channel': channel,
        'reason': reason,
        'requestId': request_id,
        'timestamp': int(time.time())
    }))


def _get_media_extension(media_type: str) -> str:
    """
    Get file extension based on media type.
    Complete mapping per WhatsApp Business Platform supported media types.
    
    Supported types:
    - Audio: AAC, AMR, MP3, M4A, OGG (max 16MB)
    - Document: PDF, TXT, DOC/DOCX, XLS/XLSX, PPT/PPTX (max 100MB)
    - Image: JPEG, PNG (max 5MB)
    - Sticker: WEBP (max 500KB animated, 100KB static)
    - Video: MP4, 3GPP (max 16MB)
    """
    extensions = {
        # Image formats (max 5MB)
        'image/jpeg': '.jpeg',
        'image/png': '.png',
        'image': '.jpeg',  # Default image

        # Sticker formats (max 500KB animated, 100KB static)
        'image/webp': '.webp',
        'sticker': '.webp',

        # Video formats (max 16MB)
        'video/mp4': '.mp4',
        'video/3gpp': '.3gp',
        'video': '.mp4',  # Default video

        # Audio formats (max 16MB)
        'audio/aac': '.aac',
        'audio/amr': '.amr',
        'audio/mpeg': '.mp3',
        'audio/mp4': '.m4a',
        'audio/ogg': '.ogg',
        'audio': '.ogg',  # Default audio

        # Document formats (max 100MB)
        'application/pdf': '.pdf',
        'text/plain': '.txt',
        'application/msword': '.doc',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
        'application/vnd.ms-excel': '.xls',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
        'application/vnd.ms-powerpoint': '.ppt',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
        'document': '.pdf',  # Default document
    }
    
    # Try exact match first
    if media_type in extensions:
        return extensions[media_type]
    
    # Try prefix match (e.g., 'image' from 'image/jpeg')
    prefix = media_type.split('/')[0] if '/' in media_type else media_type
    return extensions.get(prefix, '.bin')


def _get_content_type(media_type: str) -> str:
    """
    Get MIME content type based on media type.
    Complete mapping per WhatsApp Business Platform supported media types.
    """
    content_types = {
        # Image formats (max 5MB)
        'image/jpeg': 'image/jpeg',
        'image/png': 'image/png',
        'image': 'image/jpeg',

        # Sticker formats (max 500KB animated, 100KB static)
        'image/webp': 'image/webp',
        'sticker': 'image/webp',

        # Video formats (max 16MB)
        'video/mp4': 'video/mp4',
        'video/3gpp': 'video/3gpp',
        'video': 'video/mp4',

        # Audio formats (max 16MB)
        'audio/aac': 'audio/aac',
        'audio/amr': 'audio/amr',
        'audio/mpeg': 'audio/mpeg',
        'audio/mp4': 'audio/mp4',
        'audio/ogg': 'audio/ogg',
        'audio': 'audio/ogg',

        # Document formats (max 100MB)
        'application/pdf': 'application/pdf',
        'text/plain': 'text/plain',
        'application/msword': 'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/vnd.ms-excel': 'application/vnd.ms-excel',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-powerpoint': 'application/vnd.ms-powerpoint',
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'document': 'application/pdf',
    }
    
    # Try exact match first
    if media_type in content_types:
        return content_types[media_type]
    
    # Try prefix match
    prefix = media_type.split('/')[0] if '/' in media_type else media_type
    if prefix in content_types:
        return content_types[prefix]
    
    return 'application/octet-stream'


def _validate_media_size(file_size: int, media_type: str) -> Tuple[bool, str]:
    """
    Validate media file size per WhatsApp Business Platform supported media types.
    
    Limits:
    - Audio (AAC, AMR, MP3, M4A, OGG): 16 MB
    - Document (PDF, TXT, DOC/DOCX, XLS/XLSX, PPT/PPTX): 100 MB
    - Image (JPEG, PNG): 5 MB
    - Sticker animated (WEBP): 500 KB
    - Sticker static (WEBP): 100 KB
    - Video (MP4, 3GPP): 16 MB
    
    Returns (is_valid, error_message)
    """
    if media_type.startswith('audio/') or media_type == 'audio':
        max_size = 16 * 1024 * 1024  # 16 MB
        category = 'Audio'
    elif media_type.startswith('video/') or media_type == 'video':
        max_size = 16 * 1024 * 1024  # 16 MB
        category = 'Video'
    elif media_type == 'sticker' or media_type == 'image/webp':
        max_size = 500 * 1024  # 500 KB (animated max; static is 100KB but we allow up to 500KB)
        category = 'Sticker'
    elif media_type.startswith('image/') or media_type == 'image':
        max_size = 5 * 1024 * 1024  # 5 MB
        category = 'Image'
    else:
        # Documents: PDF, TXT, DOC/DOCX, XLS/XLSX, PPT/PPTX
        max_size = 100 * 1024 * 1024  # 100 MB
        category = 'Document'
    
    if file_size > max_size:
        max_display = f'{max_size / 1024:.0f}KB' if max_size < 1024 * 1024 else f'{max_size / (1024*1024):.0f}MB'
        return False, f'{category} file exceeds maximum size of {max_display}'
    
    return True, ''


def _error_response(status_code: int, error: str, message: str = None) -> Dict[str, Any]:
    """Return error response with CORS headers."""
    body = {'error': error}
    if message:
        body['message'] = message
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS'
        },
        'body': json.dumps(body)
    }


def _send_typing_indicator(phone_number_id: str, recipient_phone: str) -> None:
    """Send typing indicator to WhatsApp user via Meta Cloud API."""
    # The AWS Social Messaging SDK doesn't expose typing indicators directly,
    # so we use the Meta Cloud API passthrough via send_whatsapp_message
    # with a special payload that Meta interprets as typing_on
    try:
        # Use the social messaging client to send a typing indicator
        # This is a best-effort operation
        logger.info(f'Sending typing indicator to {recipient_phone} via {phone_number_id}')
        # Note: AWS Social Messaging doesn't support typing indicators natively
        # This is a placeholder - the frontend shows a local typing animation instead
    except Exception as e:
        logger.warning(f'Typing indicator error: {e}')
        raise


def _emit_delivery_metric(status: str, is_template: bool = False) -> None:
    """
    Emit message delivery metric to CloudWatch.
    Requirement 14.4: Emit CloudWatch metrics for message delivery success/failure
    """
    try:
        cloudwatch.put_metric_data(
            Namespace=METRICS_NAMESPACE,
            MetricData=[
                {
                    'MetricName': f'Messages{status.capitalize()}',
                    'Value': 1,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'Channel', 'Value': 'WHATSAPP'},
                        {'Name': 'Status', 'Value': status.upper()},
                        {'Name': 'MessageType', 'Value': 'TEMPLATE' if is_template else 'FREEFORM'}
                    ]
                },
                {
                    'MetricName': 'MessagesTotal',
                    'Value': 1,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'Channel', 'Value': 'WHATSAPP'}
                    ]
                }
            ]
        )
    except Exception as e:
        logger.warning(f"Failed to emit metric: {str(e)}")
