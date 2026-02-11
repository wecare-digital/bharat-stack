"""
Razorpay Webhook Handler Lambda Function

Purpose: Process Razorpay payment webhooks
Webhook URL: https://api.wecare.digital/razorpay-webhook
Webhook Secret: b@c4mk9t9Z8qLq3
"""

import os
import json
import hmac
import hashlib
import logging
import boto3
from typing import Dict, Any
from decimal import Decimal

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Environment variables
WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET', 'b@c4mk9t9Z8qLq3')
PAYMENTS_TABLE = os.environ.get('PAYMENTS_TABLE', 'base-wecare-digital-PaymentsTable')
MESSAGES_TABLE = os.environ.get('MESSAGES_TABLE', 'base-wecare-digital-WhatsAppInboundTable')


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process Razorpay webhook events.
    
    Supported events:
    - payment.captured - Payment successful
    - payment.failed - Payment failed
    - payment.authorized - Payment authorized
    - refund.created - Refund initiated
    - refund.processed - Refund completed
    - order.paid - Order paid
    """
    request_id = context.aws_request_id if context else 'local'
    
    logger.info(json.dumps({
        'event': 'razorpay_webhook_received',
        'requestId': request_id
    }))
    
    try:
        # Get headers and body
        headers = event.get('headers', {})
        body = event.get('body', '')
        
        # Verify webhook signature
        signature = headers.get('x-razorpay-signature') or headers.get('X-Razorpay-Signature', '')
        
        if not _verify_signature(body, signature):
            logger.warning(json.dumps({
                'event': 'webhook_signature_invalid',
                'requestId': request_id
            }))
            return _response(401, {'error': 'Invalid signature'})
        
        # Parse webhook payload
        payload = json.loads(body) if isinstance(body, str) else body
        
        event_type = payload.get('event', '')
        event_data = payload.get('payload', {})
        
        logger.info(json.dumps({
            'event': 'razorpay_event_received',
            'eventType': event_type,
            'requestId': request_id
        }))
        
        # Route to appropriate handler
        if event_type == 'payment.captured':
            _handle_payment_captured(event_data, request_id)
        elif event_type == 'payment.failed':
            _handle_payment_failed(event_data, request_id)
        elif event_type == 'payment.authorized':
            _handle_payment_authorized(event_data, request_id)
        elif event_type == 'refund.created':
            _handle_refund_created(event_data, request_id)
        elif event_type == 'refund.processed':
            _handle_refund_processed(event_data, request_id)
        elif event_type == 'order.paid':
            _handle_order_paid(event_data, request_id)
        elif event_type == 'payment_link.paid':
            _handle_payment_link_paid(event_data, request_id)
        elif event_type.startswith('payment.dispute'):
            _handle_dispute(event_type, event_data, request_id)
        elif event_type.startswith('settlement'):
            _handle_settlement(event_type, event_data, request_id)
        else:
            logger.info(json.dumps({
                'event': 'razorpay_event_unhandled',
                'eventType': event_type,
                'requestId': request_id
            }))
        
        return _response(200, {'status': 'ok', 'event': event_type})
        
    except json.JSONDecodeError as e:
        logger.error(json.dumps({
            'event': 'webhook_parse_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _response(400, {'error': 'Invalid JSON'})
    except Exception as e:
        logger.error(json.dumps({
            'event': 'webhook_error',
            'error': str(e),
            'requestId': request_id
        }))
        return _response(500, {'error': 'Internal server error'})


def _verify_signature(body: str, signature: str) -> bool:
    """Verify Razorpay webhook signature using HMAC SHA256."""
    if not signature or not WEBHOOK_SECRET:
        return False
    
    try:
        expected = hmac.new(
            WEBHOOK_SECRET.encode('utf-8'),
            body.encode('utf-8') if isinstance(body, str) else body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)
    except Exception as e:
        logger.error(f"Signature verification error: {str(e)}")
        return False


def _handle_payment_captured(data: Dict, request_id: str) -> None:
    """Handle payment.captured event - Payment successful."""
    payment = data.get('payment', {}).get('entity', {})
    
    payment_id = payment.get('id', '')
    order_id = payment.get('order_id', '')
    amount = payment.get('amount', 0)  # In paise
    currency = payment.get('currency', 'INR')
    method = payment.get('method', '')  # upi, card, netbanking, wallet
    email = payment.get('email', '')
    contact = payment.get('contact', '')
    notes = payment.get('notes', {})
    
    # Extract reference_id from notes if available
    reference_id = notes.get('reference_id', order_id)
    
    logger.info(json.dumps({
        'event': 'payment_captured',
        'paymentId': payment_id,
        'orderId': order_id,
        'referenceId': reference_id,
        'amount': amount / 100,  # Convert to rupees
        'currency': currency,
        'method': method,
        'contact': contact,
        'requestId': request_id
    }))
    
    # Store payment record
    _store_payment_record(
        payment_id=payment_id,
        order_id=order_id,
        reference_id=reference_id,
        status='captured',
        amount=amount,
        currency=currency,
        method=method,
        contact=contact,
        email=email,
        notes=notes,
        request_id=request_id
    )


def _handle_payment_failed(data: Dict, request_id: str) -> None:
    """Handle payment.failed event."""
    payment = data.get('payment', {}).get('entity', {})
    
    payment_id = payment.get('id', '')
    order_id = payment.get('order_id', '')
    amount = payment.get('amount', 0)
    error_code = payment.get('error_code', '')
    error_description = payment.get('error_description', '')
    error_reason = payment.get('error_reason', '')
    
    logger.info(json.dumps({
        'event': 'payment_failed',
        'paymentId': payment_id,
        'orderId': order_id,
        'amount': amount / 100,
        'errorCode': error_code,
        'errorDescription': error_description,
        'errorReason': error_reason,
        'requestId': request_id
    }))
    
    _store_payment_record(
        payment_id=payment_id,
        order_id=order_id,
        reference_id=order_id,
        status='failed',
        amount=amount,
        currency='INR',
        method='',
        contact='',
        email='',
        notes={'error_code': error_code, 'error_description': error_description},
        request_id=request_id
    )


def _handle_payment_authorized(data: Dict, request_id: str) -> None:
    """Handle payment.authorized event."""
    payment = data.get('payment', {}).get('entity', {})
    
    logger.info(json.dumps({
        'event': 'payment_authorized',
        'paymentId': payment.get('id', ''),
        'orderId': payment.get('order_id', ''),
        'amount': payment.get('amount', 0) / 100,
        'requestId': request_id
    }))


def _handle_refund_created(data: Dict, request_id: str) -> None:
    """Handle refund.created event."""
    refund = data.get('refund', {}).get('entity', {})
    
    logger.info(json.dumps({
        'event': 'refund_created',
        'refundId': refund.get('id', ''),
        'paymentId': refund.get('payment_id', ''),
        'amount': refund.get('amount', 0) / 100,
        'status': refund.get('status', ''),
        'requestId': request_id
    }))


def _handle_refund_processed(data: Dict, request_id: str) -> None:
    """Handle refund.processed event."""
    refund = data.get('refund', {}).get('entity', {})
    
    logger.info(json.dumps({
        'event': 'refund_processed',
        'refundId': refund.get('id', ''),
        'paymentId': refund.get('payment_id', ''),
        'amount': refund.get('amount', 0) / 100,
        'status': refund.get('status', ''),
        'requestId': request_id
    }))


def _handle_order_paid(data: Dict, request_id: str) -> None:
    """Handle order.paid event."""
    order = data.get('order', {}).get('entity', {})
    
    logger.info(json.dumps({
        'event': 'order_paid',
        'orderId': order.get('id', ''),
        'amount': order.get('amount', 0) / 100,
        'status': order.get('status', ''),
        'requestId': request_id
    }))


def _handle_payment_link_paid(data: Dict, request_id: str) -> None:
    """Handle payment_link.paid event."""
    payment_link = data.get('payment_link', {}).get('entity', {})
    
    logger.info(json.dumps({
        'event': 'payment_link_paid',
        'paymentLinkId': payment_link.get('id', ''),
        'amount': payment_link.get('amount', 0) / 100,
        'status': payment_link.get('status', ''),
        'requestId': request_id
    }))


def _handle_dispute(event_type: str, data: Dict, request_id: str) -> None:
    """Handle payment.dispute.* events."""
    dispute = data.get('dispute', {}).get('entity', {})
    
    logger.info(json.dumps({
        'event': event_type,
        'disputeId': dispute.get('id', ''),
        'paymentId': dispute.get('payment_id', ''),
        'amount': dispute.get('amount', 0) / 100,
        'status': dispute.get('status', ''),
        'reason_code': dispute.get('reason_code', ''),
        'requestId': request_id
    }))


def _handle_settlement(event_type: str, data: Dict, request_id: str) -> None:
    """Handle settlement.* events."""
    settlement = data.get('settlement', {}).get('entity', {})
    
    logger.info(json.dumps({
        'event': event_type,
        'settlementId': settlement.get('id', ''),
        'amount': settlement.get('amount', 0) / 100,
        'status': settlement.get('status', ''),
        'requestId': request_id
    }))


def _store_payment_record(payment_id: str, order_id: str, reference_id: str,
                          status: str, amount: int, currency: str, method: str,
                          contact: str, email: str, notes: Dict, request_id: str) -> None:
    """Store payment record in DynamoDB."""
    import time
    import uuid
    
    try:
        record = {
            'id': str(uuid.uuid4()),
            'paymentId': payment_id,
            'orderId': order_id,
            'referenceId': reference_id,
            'status': status,
            'amount': Decimal(str(amount)),
            'amountInRupees': Decimal(str(amount / 100)),
            'currency': currency,
            'method': method,
            'contact': contact,
            'email': email,
            'notes': json.dumps(notes) if notes else None,
            'source': 'razorpay_webhook',
            'createdAt': Decimal(str(int(time.time()))),
        }
        
        # Try to store in payments table (may not exist)
        try:
            payments_table = dynamodb.Table(PAYMENTS_TABLE)
            payments_table.put_item(Item={k: v for k, v in record.items() if v is not None})
            
            logger.info(json.dumps({
                'event': 'payment_record_stored',
                'paymentId': payment_id,
                'status': status,
                'requestId': request_id
            }))
        except Exception as e:
            # Table may not exist, log and continue
            logger.warning(json.dumps({
                'event': 'payment_record_store_skipped',
                'paymentId': payment_id,
                'error': str(e),
                'requestId': request_id
            }))
            
    except Exception as e:
        logger.error(json.dumps({
            'event': 'payment_record_error',
            'paymentId': payment_id,
            'error': str(e),
            'requestId': request_id
        }))


def _response(status_code: int, body: Dict) -> Dict[str, Any]:
    """Return HTTP response with CORS headers."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Razorpay-Signature',
            'Access-Control-Allow-Methods': 'POST,OPTIONS'
        },
        'body': json.dumps(body)
    }
