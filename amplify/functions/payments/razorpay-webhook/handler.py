"""
Razorpay Webhook Handler Lambda Function

Purpose: Process ALL Razorpay webhook events
Webhook URL: https://api.wecare.digital/razorpay-webhook

Supported Event Categories:
- payment.* (authorized, pending, failed, captured, dispute.*, downtime.*)
- order.* (paid, notification.delivered, notification.failed)
- invoice.* (paid, partially_paid, expired)
- subscription.* (authenticated, paused, resumed, activated, pending, halted, charged, cancelled, completed, updated)
- settlement.* (processed)
- fund_account.* (validation.completed, validation.failed)
- payout.* (processed, reversed, initiated, updated, rejected, pending)
- refund.* (speed_changed, processed, failed, created)
- account.* (instantly_activated, activated_kyc_pending)
- payment_link.* (paid, partially_paid, expired, cancelled)
- token.* (service_provider.activated, service_provider.failed, service_provider.cancelled, service_provider.deactivated)
"""

import os
import json
import hmac
import hashlib
import logging
import boto3
from typing import Dict, Any
from decimal import Decimal

from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin
from lambda_utils.logging import get_logger

logger = get_logger(__name__)

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
lambda_client = boto3.client('lambda', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

WEBHOOK_SECRET = os.environ.get('RAZORPAY_WEBHOOK_SECRET', '')
PAYMENTS_TABLE = os.environ.get('PAYMENTS_TABLE', 'base-wecare-digital-PaymentsTable')
INVOICES_TABLE = os.environ.get('INVOICES_TABLE', 'base-wecare-digital-InvoicesTable')
MESSAGES_TABLE = os.environ.get('MESSAGES_TABLE', 'base-wecare-digital-WhatsAppInboundTable')
WEBHOOK_LOG_TABLE = os.environ.get('WEBHOOK_LOG_TABLE', 'base-wecare-digital-RazorpayWebhookLogTable')


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process ALL Razorpay webhook events."""
    request_id = context.aws_request_id if context else 'local'
    origin = extract_origin(event)
    logger.info(json.dumps({'event': 'razorpay_webhook_received', 'requestId': request_id}))

    try:
        headers = event.get('headers', {})
        body = event.get('body', '')
        
        # API Gateway / Function URL may base64-encode the body
        import base64 as _b64
        if event.get('isBase64Encoded') and body:
            try:
                body = _b64.b64decode(body).decode('utf-8')
            except Exception:
                pass  # keep original if decode fails
        
        signature = headers.get('x-razorpay-signature') or headers.get('X-Razorpay-Signature', '')
        
        logger.info(json.dumps({
            'event': 'webhook_debug',
            'hasBody': bool(body),
            'bodyLen': len(body) if body else 0,
            'bodyFirst100': (body or '')[:100],
            'hasSignature': bool(signature),
            'signatureFirst20': (signature or '')[:20],
            'isBase64Encoded': event.get('isBase64Encoded', False),
            'headerKeys': list(headers.keys()) if headers else [],
            'requestId': request_id,
        }))

        if not _verify_signature(body, signature):
            logger.warning(json.dumps({'event': 'webhook_signature_invalid', 'requestId': request_id}))
            return _response(401, {'error': 'Invalid signature'})

        payload = json.loads(body) if isinstance(body, str) else body
        event_type = payload.get('event', '')
        event_data = payload.get('payload', {})

        # Extract Razorpay event ID for idempotency
        razorpay_event_id = payload.get('account_id', '') + ':' + payload.get('event', '') + ':' + str(payload.get('created_at', ''))
        # Use payment entity ID if available (more reliable)
        _entity = event_data.get('payment', {}).get('entity', {})
        if _entity.get('id'):
            razorpay_event_id = _entity['id'] + ':' + event_type

        logger.info(json.dumps({'event': 'razorpay_event_received', 'eventType': event_type, 'razorpayEventId': razorpay_event_id, 'requestId': request_id}))

        # Idempotency check — skip if this event was already processed
        if _is_duplicate_event(razorpay_event_id, request_id):
            logger.info(json.dumps({'event': 'webhook_duplicate_skipped', 'razorpayEventId': razorpay_event_id, 'requestId': request_id}))
            return _response(200, {'status': 'already_processed'})

        # Log every webhook event to DynamoDB for audit trail
        _log_webhook_event(event_type, event_data, request_id, razorpay_event_id)

        # ═══════════════════════════════════════════════════════════
        # PAYMENT EVENTS
        # ═══════════════════════════════════════════════════════════
        if event_type == 'payment.captured':
            _handle_payment_captured(event_data, request_id)
        elif event_type == 'payment.authorized':
            _handle_payment_authorized(event_data, request_id)
        elif event_type == 'payment.pending':
            _handle_payment_pending(event_data, request_id)
        elif event_type == 'payment.failed':
            _handle_payment_failed(event_data, request_id)

        # Payment Dispute Events
        elif event_type == 'payment.dispute.created':
            _handle_dispute(event_type, event_data, request_id)
        elif event_type == 'payment.dispute.won':
            _handle_dispute(event_type, event_data, request_id)
        elif event_type == 'payment.dispute.lost':
            _handle_dispute(event_type, event_data, request_id)
        elif event_type == 'payment.dispute.closed':
            _handle_dispute(event_type, event_data, request_id)
        elif event_type == 'payment.dispute.under_review':
            _handle_dispute(event_type, event_data, request_id)
        elif event_type == 'payment.dispute.action_required':
            _handle_dispute(event_type, event_data, request_id)

        # Payment Downtime Events
        elif event_type == 'payment.downtime.started':
            _handle_downtime(event_type, event_data, request_id)
        elif event_type == 'payment.downtime.updated':
            _handle_downtime(event_type, event_data, request_id)
        elif event_type == 'payment.downtime.resolved':
            _handle_downtime(event_type, event_data, request_id)

        # ═══════════════════════════════════════════════════════════
        # ORDER EVENTS
        # ═══════════════════════════════════════════════════════════
        elif event_type == 'order.paid':
            _handle_order_paid(event_data, request_id)
        elif event_type == 'order.notification.delivered':
            _handle_order_notification(event_type, event_data, request_id)
        elif event_type == 'order.notification.failed':
            _handle_order_notification(event_type, event_data, request_id)

        # ═══════════════════════════════════════════════════════════
        # INVOICE EVENTS
        # ═══════════════════════════════════════════════════════════
        elif event_type == 'invoice.paid':
            _handle_invoice_event(event_type, event_data, request_id)
        elif event_type == 'invoice.partially_paid':
            _handle_invoice_event(event_type, event_data, request_id)
        elif event_type == 'invoice.expired':
            _handle_invoice_event(event_type, event_data, request_id)

        # ═══════════════════════════════════════════════════════════
        # SUBSCRIPTION EVENTS
        # ═══════════════════════════════════════════════════════════
        elif event_type.startswith('subscription.'):
            _handle_subscription_event(event_type, event_data, request_id)

        # ═══════════════════════════════════════════════════════════
        # SETTLEMENT EVENTS
        # ═══════════════════════════════════════════════════════════
        elif event_type == 'settlement.processed':
            _handle_settlement(event_type, event_data, request_id)

        # ═══════════════════════════════════════════════════════════
        # FUND ACCOUNT EVENTS
        # ═══════════════════════════════════════════════════════════
        elif event_type == 'fund_account.validation.completed':
            _handle_fund_account(event_type, event_data, request_id)
        elif event_type == 'fund_account.validation.failed':
            _handle_fund_account(event_type, event_data, request_id)

        # ═══════════════════════════════════════════════════════════
        # PAYOUT EVENTS
        # ═══════════════════════════════════════════════════════════
        elif event_type.startswith('payout.'):
            _handle_payout_event(event_type, event_data, request_id)

        # ═══════════════════════════════════════════════════════════
        # REFUND EVENTS
        # ═══════════════════════════════════════════════════════════
        elif event_type == 'refund.created':
            _handle_refund(event_type, event_data, request_id)
        elif event_type == 'refund.processed':
            _handle_refund(event_type, event_data, request_id)
        elif event_type == 'refund.failed':
            _handle_refund(event_type, event_data, request_id)
        elif event_type == 'refund.speed_changed':
            _handle_refund(event_type, event_data, request_id)

        # ═══════════════════════════════════════════════════════════
        # ACCOUNT EVENTS
        # ═══════════════════════════════════════════════════════════
        elif event_type == 'account.instantly_activated':
            _handle_account_event(event_type, event_data, request_id)
        elif event_type == 'account.activated_kyc_pending':
            _handle_account_event(event_type, event_data, request_id)

        # ═══════════════════════════════════════════════════════════
        # PAYMENT LINK EVENTS
        # ═══════════════════════════════════════════════════════════
        elif event_type == 'payment_link.paid':
            _handle_payment_link(event_type, event_data, request_id)
        elif event_type == 'payment_link.partially_paid':
            _handle_payment_link(event_type, event_data, request_id)
        elif event_type == 'payment_link.expired':
            _handle_payment_link(event_type, event_data, request_id)
        elif event_type == 'payment_link.cancelled':
            _handle_payment_link(event_type, event_data, request_id)

        # ═══════════════════════════════════════════════════════════
        # TOKEN EVENTS
        # ═══════════════════════════════════════════════════════════
        elif event_type.startswith('token.'):
            _handle_token_event(event_type, event_data, request_id)

        else:
            logger.info(json.dumps({'event': 'razorpay_event_unhandled', 'eventType': event_type, 'requestId': request_id}))

        return _response(200, {'status': 'ok', 'event': event_type})

    except json.JSONDecodeError as e:
        logger.error(json.dumps({'event': 'webhook_parse_error', 'error': str(e), 'requestId': request_id}))
        return _response(400, {'error': 'Invalid JSON'})
    except Exception as e:
        logger.error(json.dumps({'event': 'webhook_error', 'error': str(e), 'requestId': request_id}))
        return _response(500, {'error': 'Internal server error'})


# ═══════════════════════════════════════════════════════════════════
# SIGNATURE VERIFICATION
# ═══════════════════════════════════════════════════════════════════

def _verify_signature(body: str, signature: str) -> bool:
    if not WEBHOOK_SECRET:
        logger.error('RAZORPAY_WEBHOOK_SECRET not set — rejecting webhook (fail closed)')
        return False
    if not signature:
        logger.warning('No signature header received')
        return False
    try:
        body_bytes = body.encode('utf-8') if isinstance(body, str) else body
        expected = hmac.new(
            WEBHOOK_SECRET.encode('utf-8'),
            body_bytes,
            hashlib.sha256
        ).hexdigest()
        match = hmac.compare_digest(expected, signature)
        if not match:
            logger.warning(json.dumps({
                'event': 'signature_mismatch_debug',
                'expectedFirst20': expected[:20],
                'receivedFirst20': signature[:20],
                'secretLen': len(WEBHOOK_SECRET),
                'bodyLen': len(body_bytes),
            }))
        return match
    except Exception as e:
        logger.error(f"Signature verification error: {str(e)}")
        return False


# ═══════════════════════════════════════════════════════════════════
# WEBHOOK AUDIT LOG
# ═══════════════════════════════════════════════════════════════════

def _log_webhook_event(event_type: str, event_data: Dict, request_id: str, razorpay_event_id: str = '') -> None:
    """Log every webhook event to DynamoDB for audit trail with idempotency key."""
    import time, uuid
    try:
        table = dynamodb.Table(WEBHOOK_LOG_TABLE)
        item = {
            'id': str(uuid.uuid4()),
            'eventType': event_type,
            'requestId': request_id,
            'payload': json.dumps(event_data, default=str)[:4000],  # Truncate large payloads
            'createdAt': Decimal(str(int(time.time()))),
        }
        if razorpay_event_id:
            item['razorpayEventId'] = razorpay_event_id
        table.put_item(Item=item)
    except Exception as e:
        # Don't fail the webhook if logging fails
        logger.warning(json.dumps({'event': 'webhook_log_failed', 'error': str(e), 'requestId': request_id}))


def _is_duplicate_event(razorpay_event_id: str, request_id: str) -> bool:
    """Check if a Razorpay webhook event was already processed (idempotency)."""
    if not razorpay_event_id:
        return False
    try:
        from boto3.dynamodb.conditions import Attr
        table = dynamodb.Table(WEBHOOK_LOG_TABLE)
        response = table.scan(
            FilterExpression=Attr('razorpayEventId').eq(razorpay_event_id),
            Limit=1,
            ProjectionExpression='id',
        )
        return len(response.get('Items', [])) > 0
    except Exception as e:
        logger.warning(json.dumps({'event': 'idempotency_check_failed', 'error': str(e), 'requestId': request_id}))
        return False  # Fail open on check errors — better to process twice than miss




# ═══════════════════════════════════════════════════════════════════
# PAYMENT EVENT HANDLERS
# ═══════════════════════════════════════════════════════════════════

def _handle_payment_captured(event_data: Dict, request_id: str) -> None:
    """Handle payment.captured — the main success event. Store payment + mark invoice paid + trigger invoice."""
    payment = event_data.get('payment', {}).get('entity', {})
    payment_id = payment.get('id', '')
    amount_paise = int(payment.get('amount', 0))
    amount_rupees = amount_paise / 100
    currency = payment.get('currency', 'INR')
    order_id = payment.get('order_id', '')
    method = payment.get('method', '')
    contact = payment.get('contact', '')
    email = payment.get('email', '')
    description = payment.get('description', '')
    notes = payment.get('notes', {})

    # Try to find referenceId from multiple locations
    reference_id = (
        notes.get('referenceId', '')
        or notes.get('reference_id', '')
        or payment.get('description', '')
        or ''
    )
    # If description looks like a WD reference, use it
    if reference_id and not reference_id.startswith('WD'):
        # Also accept legacy WD prefix without dash
        if not reference_id.upper().startswith('WD'):
            reference_id = ''

    logger.info(json.dumps({
        'event': 'payment_captured', 'paymentId': payment_id,
        'amount': amount_rupees, 'contact': contact,
        'referenceId': reference_id, 'notes': notes,
        'orderId': order_id, 'description': description,
        'requestId': request_id,
    }))

    # Store payment record in DynamoDB
    _store_payment_record(payment, 'captured', request_id)

    # ── Direct invoice status update by referenceId ──
    if reference_id:
        _mark_invoice_paid_by_reference(reference_id, request_id)
    else:
        # Fallback: try to find invoice by customer phone
        clean_phone = (contact or '').replace('+', '').replace(' ', '').replace('-', '')
        if clean_phone:
            _mark_invoice_paid_by_phone_and_amount(clean_phone, amount_rupees, request_id)

    # Post-payment: create invoice, generate image, send on WhatsApp
    _post_payment_handler(payment_id, amount_rupees, currency, contact, email, description, notes, request_id)


def _handle_payment_authorized(event_data: Dict, request_id: str) -> None:
    """Handle payment.authorized — payment authorized but not yet captured."""
    payment = event_data.get('payment', {}).get('entity', {})
    payment_id = payment.get('id', '')
    logger.info(json.dumps({'event': 'payment_authorized', 'paymentId': payment_id, 'requestId': request_id}))
    _store_payment_record(payment, 'authorized', request_id)


def _handle_payment_pending(event_data: Dict, request_id: str) -> None:
    """Handle payment.pending — UPI/bank transfer pending."""
    payment = event_data.get('payment', {}).get('entity', {})
    payment_id = payment.get('id', '')
    logger.info(json.dumps({'event': 'payment_pending', 'paymentId': payment_id, 'requestId': request_id}))
    _store_payment_record(payment, 'pending', request_id)


def _handle_payment_failed(event_data: Dict, request_id: str) -> None:
    """Handle payment.failed — payment attempt failed. Update linked invoice status."""
    payment = event_data.get('payment', {}).get('entity', {})
    payment_id = payment.get('id', '')
    error_code = payment.get('error_code', '')
    error_desc = payment.get('error_description', '')
    notes = payment.get('notes', {})
    logger.warning(json.dumps({
        'event': 'payment_failed', 'paymentId': payment_id,
        'errorCode': error_code, 'errorDesc': error_desc, 'requestId': request_id,
    }))
    _store_payment_record(payment, 'failed', request_id)

    # Update linked invoice status to payment_failed (if referenceId exists)
    reference_id = notes.get('referenceId', '')
    if reference_id:
        try:
            import time as _time
            # Full pagination to avoid DynamoDB Limit bug
            inv_table = dynamodb.Table(os.environ.get('INVOICES_TABLE', 'base-wecare-digital-InvoicesTable'))
            matched = []
            scan_kwargs = {
                'FilterExpression': 'referenceId = :ref AND (paymentStatus = :ps1 OR paymentStatus = :ps2)',
                'ExpressionAttributeValues': {':ref': reference_id, ':ps1': 'pending', ':ps2': 'pending_payment'},
            }
            while True:
                result = inv_table.scan(**scan_kwargs)
                matched.extend(result.get('Items', []))
                if 'LastEvaluatedKey' in result:
                    scan_kwargs['ExclusiveStartKey'] = result['LastEvaluatedKey']
                else:
                    break
            for inv in matched:
                inv_table.update_item(
                    Key={'invoiceId': inv['invoiceId']},
                    UpdateExpression='SET paymentStatus = :ps, updatedAt = :now, notes = if_not_exists(notes, :empty)',
                    ExpressionAttributeValues={
                        ':ps': 'failed',
                        ':now': Decimal(str(int(_time.time()))),
                        ':empty': '',
                    },
                )
                logger.info(json.dumps({'event': 'invoice_payment_failed', 'invoiceId': inv['invoiceId'], 'referenceId': reference_id, 'requestId': request_id}))
        except Exception as e:
            logger.error(json.dumps({'event': 'invoice_fail_update_error', 'referenceId': reference_id, 'error': str(e), 'requestId': request_id}))


# ═══════════════════════════════════════════════════════════════════
# STORE PAYMENT RECORD
# ═══════════════════════════════════════════════════════════════════

def _store_payment_record(payment: Dict, status: str, request_id: str) -> None:
    """Store/update payment record in PaymentsTable."""
    import time as _time
    payment_id = payment.get('id', '')
    if not payment_id:
        return

    amount_paise = int(payment.get('amount') or 0)
    amount_rupees = amount_paise / 100

    def _safe_int(val):
        """Safely convert to int, handling None."""
        if val is None:
            return 0
        try:
            return int(val)
        except (ValueError, TypeError):
            return 0

    record = {
        'id': payment_id,
        'paymentId': payment_id,
        'orderId': payment.get('order_id') or '',
        'referenceId': (payment.get('notes') or {}).get('referenceId', ''),
        'status': status,
        'amount': Decimal(str(amount_paise)),
        'amountInRupees': Decimal(str(amount_rupees)),
        'currency': payment.get('currency') or 'INR',
        'method': payment.get('method') or '',
        'contact': payment.get('contact') or '',
        'email': payment.get('email') or '',
        'description': payment.get('description') or '',
        'notes': json.dumps(payment.get('notes') or {}, default=str),
        'vpa': payment.get('vpa') or '',
        'bank': payment.get('bank') or '',
        'wallet': payment.get('wallet') or '',
        'cardId': payment.get('card_id') or '',
        'fee': Decimal(str(_safe_int(payment.get('fee')))),
        'tax': Decimal(str(_safe_int(payment.get('tax')))),
        'errorCode': payment.get('error_code') or '',
        'errorDescription': payment.get('error_description') or '',
        'errorSource': payment.get('error_source') or '',
        'errorStep': payment.get('error_step') or '',
        'errorReason': payment.get('error_reason') or '',
        'international': payment.get('international', False),
        'captured': payment.get('captured', False),
        'razorpayCreatedAt': Decimal(str(_safe_int(payment.get('created_at')))),
        'createdAt': Decimal(str(int(_time.time()))),
        'updatedAt': Decimal(str(int(_time.time()))),
        'requestId': request_id,
    }

    # Remove empty string values (DynamoDB doesn't allow empty strings in some cases)
    clean = {k: v for k, v in record.items() if v is not None and v != ''}

    try:
        table = dynamodb.Table(PAYMENTS_TABLE)
        table.put_item(Item=clean)
        logger.info(json.dumps({'event': 'payment_stored', 'paymentId': payment_id, 'status': status, 'requestId': request_id}))
    except Exception as e:
        logger.error(json.dumps({'event': 'payment_store_error', 'paymentId': payment_id, 'error': str(e), 'requestId': request_id}))

def _mark_invoice_paid_by_reference(reference_id: str, request_id: str) -> None:
    """Directly update InvoicesTable: set status=paid for the given referenceId."""
    if not reference_id:
        return
    try:
        import time as _time
        import datetime
        table = dynamodb.Table(INVOICES_TABLE)
        now = int(_time.time())
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
                    'event': 'invoice_marked_paid_by_webhook',
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

def _mark_invoice_paid_by_phone_and_amount(phone: str, amount_rupees: float, request_id: str) -> None:
    """Fallback: find pending invoice by customer phone + amount and mark paid."""
    if not phone:
        return
    try:
        import time as _time
        import datetime
        table = dynamodb.Table(INVOICES_TABLE)
        last10 = phone[-10:] if len(phone) >= 10 else phone
        now = int(_time.time())
        now_ist = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5, minutes=30)))
        paid_at_ts = int(now_ist.timestamp())

        pending_statuses = ['created', 'pending_payment', 'sent']
        scan_kwargs = {
            'FilterExpression': 'attribute_exists(customerPhone) AND #st IN (:s1, :s2, :s3)',
            'ExpressionAttributeNames': {'#st': 'status'},
            'ExpressionAttributeValues': {':s1': 'created', ':s2': 'pending_payment', ':s3': 'sent'},
        }
        candidates = []
        while True:
            resp = table.scan(**scan_kwargs)
            for item in resp.get('Items', []):
                inv_phone = (item.get('customerPhone', '') or '').replace('+', '').replace(' ', '').replace('-', '')
                inv_total = float(item.get('total', 0))
                if inv_phone.endswith(last10) and abs(inv_total - amount_rupees) < 0.50:
                    candidates.append(item)
            if 'LastEvaluatedKey' in resp:
                scan_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
            else:
                break

        if len(candidates) == 1:
            inv = candidates[0]
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
                'event': 'invoice_marked_paid_by_phone_amount',
                'invoiceId': inv['invoiceId'],
                'phone': phone,
                'amount': amount_rupees,
                'requestId': request_id,
            }))
        elif len(candidates) > 1:
            logger.warning(json.dumps({
                'event': 'multiple_invoices_match_phone_amount',
                'phone': phone, 'amount': amount_rupees,
                'count': len(candidates),
                'requestId': request_id,
            }))
        else:
            logger.warning(json.dumps({
                'event': 'no_invoice_match_phone_amount',
                'phone': phone, 'amount': amount_rupees,
                'requestId': request_id,
            }))
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'mark_invoice_paid_by_phone_error',
            'phone': phone, 'error': str(e),
            'requestId': request_id,
        }))


# ═══════════════════════════════════════════════════════════════════
# POST-PAYMENT HANDLER (Invoice + WhatsApp)
# ═══════════════════════════════════════════════════════════════════


def _post_payment_handler(payment_id: str, amount: float, currency: str, contact: str,
                          email: str, description: str, notes: Dict, request_id: str) -> None:
    """
    After payment captured (Razorpay webhook path):
    This is the BACKUP path — WhatsApp inbound handler is the primary invoice generator.
    1. Invoke invoice-engine to create invoice from payment (dedup will return existing if WhatsApp path already created it)
    2. Generate invoice image (POS receipt style) — for internal reference
    3. Generate PDF (async) — for internal reference
    4. NO WhatsApp send — WhatsApp path handles customer delivery
    """
    logger.info(json.dumps({'event': 'post_payment_start', 'paymentId': payment_id, 'path': 'webhook_backup', 'requestId': request_id}))

    # ── Step 1: Create invoice from payment (dedup-safe) ──
    try:
        invoice_payload = {
            'body': json.dumps({
                'paymentId': payment_id,
                'entryPoint': 'webhook',
                'itemName': description or notes.get('itemName', 'Payment'),
                'gstRate': float(notes.get('gstRate', 18)),
                'shipping': float(notes.get('shipping', 0)),
                'discount': float(notes.get('discount', 0)),
                'convenienceFee': float(notes.get('convenienceFee', 0)),
                'purpose': notes.get('purpose', description or ''),
            }),
            'rawPath': '/invoices/from-payment',
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
        deduplicated = inv_body.get('deduplicated', False)

        logger.info(json.dumps({
            'event': 'invoice_created_from_payment', 'paymentId': payment_id,
            'invoiceId': invoice_id, 'invoiceNumber': invoice_number,
            'deduplicated': deduplicated, 'requestId': request_id,
        }))
    except Exception as e:
        logger.error(json.dumps({'event': 'invoice_create_error', 'paymentId': payment_id, 'error': str(e), 'requestId': request_id}))
        return

    if not invoice_id:
        logger.error(json.dumps({'event': 'invoice_create_empty', 'paymentId': payment_id, 'response': str(inv_body), 'requestId': request_id}))
        return

    # If deduplicated (WhatsApp path already created it), image/PDF already exist — skip
    if deduplicated:
        logger.info(json.dumps({'event': 'post_payment_dedup_skip', 'paymentId': payment_id, 'invoiceId': invoice_id, 'requestId': request_id}))
        return

    # ── Step 2: Generate invoice image (internal reference only) ──
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

        logger.info(json.dumps({'event': 'invoice_image_generated', 'invoiceId': invoice_id, 'imageUrl': image_url, 'requestId': request_id}))
    except Exception as e:
        logger.error(json.dumps({'event': 'invoice_image_error', 'invoiceId': invoice_id, 'error': str(e), 'requestId': request_id}))

    # ── Step 3: Generate PDF (async, internal reference only) ──
    try:
        pdf_payload = {
            'rawPath': f'/invoices/{invoice_id}/generate-pdf',
            'requestContext': {'http': {'method': 'POST'}},
            'pathParameters': {'invoiceId': invoice_id},
            'body': json.dumps({'invoiceId': invoice_id}),
        }
        lambda_client.invoke(
            FunctionName='wecare-invoice-engine',
            InvocationType='Event',  # Async
            Payload=json.dumps(pdf_payload),
        )
        logger.info(json.dumps({'event': 'invoice_pdf_triggered', 'invoiceId': invoice_id, 'requestId': request_id}))
    except Exception as e:
        logger.error(json.dumps({'event': 'invoice_pdf_error', 'invoiceId': invoice_id, 'error': str(e), 'requestId': request_id}))

    # NO WhatsApp send — WhatsApp inbound handler is the primary path for customer delivery
    logger.info(json.dumps({'event': 'post_payment_complete', 'paymentId': payment_id, 'invoiceId': invoice_id, 'path': 'webhook_backup', 'requestId': request_id}))



# ═══════════════════════════════════════════════════════════════════
# ORDER EVENTS
# ═══════════════════════════════════════════════════════════════════

def _handle_order_paid(event_data: Dict, request_id: str) -> None:
    """Handle order.paid — order fully paid."""
    order = event_data.get('order', {}).get('entity', {})
    order_id = order.get('id', '')
    logger.info(json.dumps({'event': 'order_paid', 'orderId': order_id, 'requestId': request_id}))


def _handle_order_notification(event_type: str, event_data: Dict, request_id: str) -> None:
    """Handle order notification events (delivered/failed)."""
    order = event_data.get('order', {}).get('entity', {})
    order_id = order.get('id', '')
    logger.info(json.dumps({'event': event_type, 'orderId': order_id, 'requestId': request_id}))


# ═══════════════════════════════════════════════════════════════════
# PAYMENT LINK EVENTS
# ═══════════════════════════════════════════════════════════════════

def _handle_payment_link(event_type: str, event_data: Dict, request_id: str) -> None:
    """Handle payment_link.* events."""
    link = event_data.get('payment_link', {}).get('entity', {})
    link_id = link.get('id', '')
    status = link.get('status', '')
    logger.info(json.dumps({'event': event_type, 'linkId': link_id, 'status': status, 'requestId': request_id}))

    # If payment link paid, the payment.captured event will also fire
    # and handle invoice creation. Just log here.


# ═══════════════════════════════════════════════════════════════════
# REFUND EVENTS
# ═══════════════════════════════════════════════════════════════════

def _handle_refund(event_type: str, event_data: Dict, request_id: str) -> None:
    """Handle refund.* events."""
    refund = event_data.get('refund', {}).get('entity', {})
    refund_id = refund.get('id', '')
    payment_id = refund.get('payment_id', '')
    amount = int(refund.get('amount', 0)) / 100
    status = refund.get('status', '')
    logger.info(json.dumps({
        'event': event_type, 'refundId': refund_id, 'paymentId': payment_id,
        'amount': amount, 'status': status, 'requestId': request_id,
    }))

    # Update payment record status if refund processed
    if event_type == 'refund.processed' and payment_id:
        try:
            table = dynamodb.Table(PAYMENTS_TABLE)
            import time as _time
            table.update_item(
                Key={'paymentId': payment_id},
                UpdateExpression='SET #st = :st, #refundId = :rid, #refundAmount = :ra, #ua = :now',
                ExpressionAttributeNames={'#st': 'status', '#refundId': 'refundId', '#refundAmount': 'refundAmount', '#ua': 'updatedAt'},
                ExpressionAttributeValues={':st': 'refunded', ':rid': refund_id, ':ra': Decimal(str(amount)), ':now': Decimal(str(int(_time.time())))},
            )
        except Exception as e:
            logger.error(json.dumps({'event': 'refund_update_error', 'error': str(e), 'requestId': request_id}))


# ═══════════════════════════════════════════════════════════════════
# DISPUTE EVENTS
# ═══════════════════════════════════════════════════════════════════

def _handle_dispute(event_type: str, event_data: Dict, request_id: str) -> None:
    """Handle payment.dispute.* events."""
    dispute = event_data.get('dispute', {}).get('entity', {})
    dispute_id = dispute.get('id', '')
    payment_id = dispute.get('payment_id', '')
    amount = int(dispute.get('amount', 0)) / 100
    reason = dispute.get('reason_code', '')
    logger.warning(json.dumps({
        'event': event_type, 'disputeId': dispute_id, 'paymentId': payment_id,
        'amount': amount, 'reason': reason, 'requestId': request_id,
    }))


# ═══════════════════════════════════════════════════════════════════
# DOWNTIME EVENTS
# ═══════════════════════════════════════════════════════════════════

def _handle_downtime(event_type: str, event_data: Dict, request_id: str) -> None:
    """Handle payment.downtime.* events."""
    downtime = event_data.get('downtime', {}).get('entity', event_data.get('payment', {}).get('downtime', {}))
    method = downtime.get('method', '')
    instrument = downtime.get('instrument', {})
    logger.warning(json.dumps({
        'event': event_type, 'method': method, 'instrument': str(instrument)[:200], 'requestId': request_id,
    }))


# ═══════════════════════════════════════════════════════════════════
# SETTLEMENT EVENTS
# ═══════════════════════════════════════════════════════════════════

def _handle_settlement(event_type: str, event_data: Dict, request_id: str) -> None:
    """Handle settlement.processed event."""
    settlement = event_data.get('settlement', {}).get('entity', {})
    settlement_id = settlement.get('id', '')
    amount = int(settlement.get('amount', 0)) / 100
    logger.info(json.dumps({
        'event': event_type, 'settlementId': settlement_id, 'amount': amount, 'requestId': request_id,
    }))


# ═══════════════════════════════════════════════════════════════════
# SUBSCRIPTION EVENTS
# ═══════════════════════════════════════════════════════════════════

def _handle_subscription_event(event_type: str, event_data: Dict, request_id: str) -> None:
    """Handle subscription.* events."""
    sub = event_data.get('subscription', {}).get('entity', {})
    sub_id = sub.get('id', '')
    plan_id = sub.get('plan_id', '')
    status = sub.get('status', '')
    logger.info(json.dumps({
        'event': event_type, 'subscriptionId': sub_id, 'planId': plan_id, 'status': status, 'requestId': request_id,
    }))


# ═══════════════════════════════════════════════════════════════════
# PAYOUT EVENTS
# ═══════════════════════════════════════════════════════════════════

def _handle_payout_event(event_type: str, event_data: Dict, request_id: str) -> None:
    """Handle payout.* events."""
    payout = event_data.get('payout', {}).get('entity', {})
    payout_id = payout.get('id', '')
    amount = int(payout.get('amount', 0)) / 100
    status = payout.get('status', '')
    logger.info(json.dumps({
        'event': event_type, 'payoutId': payout_id, 'amount': amount, 'status': status, 'requestId': request_id,
    }))


# ═══════════════════════════════════════════════════════════════════
# FUND ACCOUNT EVENTS
# ═══════════════════════════════════════════════════════════════════

def _handle_fund_account(event_type: str, event_data: Dict, request_id: str) -> None:
    """Handle fund_account.validation.* events."""
    fa = event_data.get('fund_account', {}).get('entity', event_data.get('fund_account.validation', {}).get('entity', {}))
    fa_id = fa.get('id', '')
    status = fa.get('status', '')
    logger.info(json.dumps({
        'event': event_type, 'fundAccountId': fa_id, 'status': status, 'requestId': request_id,
    }))


# ═══════════════════════════════════════════════════════════════════
# ACCOUNT EVENTS
# ═══════════════════════════════════════════════════════════════════

def _handle_account_event(event_type: str, event_data: Dict, request_id: str) -> None:
    """Handle account.* events (marketplace/route)."""
    account = event_data.get('account', {}).get('entity', {})
    account_id = account.get('id', '')
    logger.info(json.dumps({
        'event': event_type, 'accountId': account_id, 'requestId': request_id,
    }))


# ═══════════════════════════════════════════════════════════════════
# TOKEN EVENTS
# ═══════════════════════════════════════════════════════════════════

def _handle_token_event(event_type: str, event_data: Dict, request_id: str) -> None:
    """Handle token.service_provider.* events."""
    token = event_data.get('token', {}).get('entity', {})
    token_id = token.get('id', '')
    logger.info(json.dumps({
        'event': event_type, 'tokenId': token_id, 'requestId': request_id,
    }))


# ═══════════════════════════════════════════════════════════════════
# INVOICE EVENTS (Razorpay invoices, not our internal invoices)
# ═══════════════════════════════════════════════════════════════════

def _handle_invoice_event(event_type: str, event_data: Dict, request_id: str) -> None:
    """Handle invoice.* events from Razorpay."""
    invoice = event_data.get('invoice', {}).get('entity', {})
    invoice_id = invoice.get('id', '')
    status = invoice.get('status', '')
    logger.info(json.dumps({
        'event': event_type, 'razorpayInvoiceId': invoice_id, 'status': status, 'requestId': request_id,
    }))


# ═══════════════════════════════════════════════════════════════════
# RESPONSE HELPER
# ═══════════════════════════════════════════════════════════════════

def _response(status_code: int, body: Dict) -> Dict[str, Any]:
    """Return HTTP response with CORS headers."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization,X-Razorpay-Signature',
            'Access-Control-Allow-Methods': 'POST,OPTIONS',
        },
        'body': json.dumps(body, default=str),
    }
