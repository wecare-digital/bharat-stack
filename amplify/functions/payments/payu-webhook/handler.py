"""
PayU Webhook Handler Lambda Function

Purpose: Process PayU payment webhook events (via WhatsApp Payments / Meta)
Webhook URL: https://api.wecare.digital/payu-webhook

PayU sends webhooks for:
- payment.success — Payment captured successfully
- payment.failed — Payment attempt failed
- payment.pending — Payment pending (bank redirect)
- refund.success — Refund processed
- refund.failed — Refund failed

PayU MID: 8629516
MCC: 4722 (Travel agencies and tour operators)
Purpose Code: 03 (Travel)

WABA Configurations:
- +91 9330994400 → WABA 2094615664435155 → WECARE-PAYU (pending migration)
- +91 9903300044 → WABA 2513394156072604 → PayU_ManishAgarwal
"""

import os
import json
import hashlib
import logging
import time
import boto3
from typing import Dict, Any
from decimal import Decimal

from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin
from lambda_utils.logging import get_logger

logger = get_logger(__name__)

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
lambda_client = boto3.client('lambda', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

PAYU_MERCHANT_KEY = os.environ.get('PAYU_MERCHANT_KEY', 'Ghgoh6')
PAYU_MERCHANT_SALT = os.environ.get('PAYU_MERCHANT_SALT', 'LtQP3Bo4sXMqJgZFz4cK9DpB8fMt3vzl')
PAYU_CLIENT_ID = os.environ.get('PAYU_CLIENT_ID', 'c066d621f07afd57e1797306a33acd5f51d19400adb0741449784dc36c634d75')
PAYU_CLIENT_SECRET = os.environ.get('PAYU_CLIENT_SECRET', '9b5c14bd86f0d8deabad339837e43ebce4cb039a26897d142ba0b1f91c38287f')
PAYU_MID = os.environ.get('PAYU_MID', '8629516')

# PayU API Endpoints
PAYU_BASE_URL = os.environ.get('PAYU_BASE_URL', 'https://info.payu.in/merchant/postservice.php')  # Production
PAYU_TOKEN_URL = os.environ.get('PAYU_TOKEN_URL', 'https://accounts.payu.in/oauth/token')  # OAuth token
PAYU_PAYMENT_LINKS_URL = os.environ.get('PAYU_PAYMENT_LINKS_URL', 'https://oneapi.payu.in/payment-links')  # Payment Links API
PAYMENTS_TABLE = os.environ.get('PAYMENTS_TABLE', 'stack-wecare-digital-PaymentsTable')
INVOICES_TABLE = os.environ.get('INVOICES_TABLE', 'stack-wecare-digital-InvoicesTable')
WEBHOOK_LOG_TABLE = os.environ.get('PAYU_WEBHOOK_LOG_TABLE', 'stack-wecare-digital-PayUWebhookLogTable')

# Module-level origin for CORS
origin = ''


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process PayU webhook events."""
    request_id = context.aws_request_id if context else 'local'
    global origin
    origin = extract_origin(event)

    rc = event.get('requestContext', {})
    http = rc.get('http', {})
    method = http.get('method', event.get('httpMethod', 'GET'))

    if method == 'OPTIONS':
        return _resp(200, {})

    logger.info(json.dumps({'event': 'payu_webhook_received', 'requestId': request_id}))

    try:
        body_raw = event.get('body', '')

        # Handle base64 encoding
        import base64 as _b64
        if event.get('isBase64Encoded') and body_raw:
            try:
                body_raw = _b64.b64decode(body_raw).decode('utf-8')
            except Exception as e:
                logger.warning(f'Base64 decode failed, using raw body: {e}')

        # PayU sends form-encoded or JSON
        payload = {}
        if body_raw:
            try:
                payload = json.loads(body_raw)
            except (json.JSONDecodeError, TypeError):
                # Try form-encoded (PayU default)
                import urllib.parse
                payload = dict(urllib.parse.parse_qsl(body_raw))

        if not payload:
            return _resp(400, {'error': 'Empty payload'})

        # Verify PayU hash signature
        if not _verify_payu_hash(payload):
            logger.warning(json.dumps({'event': 'payu_hash_invalid', 'requestId': request_id}))
            return _resp(401, {'error': 'Invalid hash'})

        # Extract PayU fields
        status = (payload.get('status') or '').lower()
        txn_id = payload.get('txnid') or payload.get('txnId') or ''
        payu_id = payload.get('mihpayid') or payload.get('payuMoneyId') or ''
        amount = payload.get('amount') or '0'
        product_info = payload.get('productinfo') or payload.get('productInfo') or ''
        firstname = payload.get('firstname') or ''
        email = payload.get('email') or ''
        phone = payload.get('phone') or ''
        mode = payload.get('mode') or ''  # CC, DC, NB, UPI, WALLET
        error_code = payload.get('error') or ''
        error_msg = payload.get('error_Message') or payload.get('unmappedstatus') or ''
        bank_ref = payload.get('bank_ref_num') or ''

        event_id = f'{payu_id}:{txn_id}:{status}'

        logger.info(json.dumps({
            'event': 'payu_event_parsed',
            'status': status, 'txnId': txn_id, 'payuId': payu_id,
            'amount': amount, 'mode': mode, 'phone': phone,
            'requestId': request_id,
        }))

        # Idempotency check
        if _is_duplicate(event_id, request_id):
            return _resp(200, {'status': 'already_processed'})

        # Log webhook event
        _log_webhook(payload, status, txn_id, payu_id, request_id)

        # Process based on status
        if status == 'success' or status == 'captured':
            _handle_success(payload, request_id)
        elif status == 'failure' or status == 'failed':
            _handle_failure(payload, request_id)
        elif status == 'pending':
            _handle_pending(payload, request_id)
        else:
            logger.info(json.dumps({'event': 'payu_status_unhandled', 'status': status, 'requestId': request_id}))

        return _resp(200, {'status': 'ok', 'eventId': event_id})

    except Exception as e:
        logger.exception(f'[{request_id}] PayU webhook error: {e}')
        return _resp(500, {'error': str(e)})


def _verify_payu_hash(payload: Dict) -> bool:
    """Verify PayU reverse hash: sha512(SALT|status||||||udf5|udf4|udf3|udf2|udf1|email|firstname|productinfo|amount|txnid|key)"""
    if not PAYU_MERCHANT_SALT:
        logger.warning('PAYU_MERCHANT_SALT not set — skipping hash verification')
        return True  # Skip if salt not configured yet

    try:
        received_hash = payload.get('hash', '')
        if not received_hash:
            # PayU always sends hash in production S2S callbacks
            logger.warning('PayU payload missing hash field — rejecting')
            return False

        # PayU reverse hash formula
        status = payload.get('status', '')
        udf5 = payload.get('udf5', '')
        udf4 = payload.get('udf4', '')
        udf3 = payload.get('udf3', '')
        udf2 = payload.get('udf2', '')
        udf1 = payload.get('udf1', '')
        email = payload.get('email', '')
        firstname = payload.get('firstname', '')
        productinfo = payload.get('productinfo', '')
        amount = payload.get('amount', '')
        txnid = payload.get('txnid', '')
        key = payload.get('key', PAYU_MERCHANT_KEY)
        additional_charges = payload.get('additionalCharges', '')

        hash_string = f'{PAYU_MERCHANT_SALT}|{status}||||||{udf5}|{udf4}|{udf3}|{udf2}|{udf1}|{email}|{firstname}|{productinfo}|{amount}|{txnid}|{key}'
        if additional_charges:
            hash_string = f'{additional_charges}|{hash_string}'

        computed = hashlib.sha512(hash_string.encode('utf-8')).hexdigest().lower()
        return computed == received_hash.lower()
    except Exception as e:
        logger.warning(json.dumps({'event': 'payu_hash_verify_error', 'error': str(e)}))
        return False  # Fail closed on verification errors


def _is_duplicate(event_id: str, request_id: str) -> bool:
    """Check if this event was already processed."""
    try:
        table = dynamodb.Table(WEBHOOK_LOG_TABLE)
        response = table.get_item(Key={'id': event_id}, ProjectionExpression='id')
        return 'Item' in response
    except Exception:
        return False


def _log_webhook(payload: Dict, status: str, txn_id: str, payu_id: str, request_id: str) -> None:
    """Log webhook event to DynamoDB."""
    try:
        table = dynamodb.Table(WEBHOOK_LOG_TABLE)
        now = int(time.time())
        event_id = f'{payu_id}:{txn_id}:{status}'
        table.put_item(Item={
            'id': event_id,
            'eventType': f'payment.{status}',
            'paymentId': payu_id,
            'txnId': txn_id,
            'amount': Decimal(str(payload.get('amount', '0'))),
            'status': status,
            'mode': payload.get('mode', ''),
            'phone': payload.get('phone', ''),
            'email': payload.get('email', ''),
            'bankRef': payload.get('bank_ref_num', ''),
            'rawPayload': json.dumps(payload, default=str),
            'processedAt': now,
            'createdAt': now,
            'expiresAt': now + 180 * 24 * 60 * 60,  # TTL: 180 days
        })
    except Exception as e:
        logger.error(json.dumps({'event': 'payu_log_error', 'error': str(e), 'requestId': request_id}))


def _handle_success(payload: Dict, request_id: str) -> None:
    """Handle successful PayU payment — store record + mark invoice paid."""
    txn_id = payload.get('txnid') or ''
    payu_id = payload.get('mihpayid') or ''
    amount_str = payload.get('amount') or '0'
    amount_rupees = float(amount_str)
    phone = payload.get('phone') or ''
    email = payload.get('email') or ''
    product_info = payload.get('productinfo') or ''
    mode = payload.get('mode') or ''
    bank_ref = payload.get('bank_ref_num') or ''

    # Extract WD-PAY reference ID from multiple possible locations
    # PayU stores the reference in productinfo, udf1, or txnid depending on integration
    reference_id = ''
    for field in (product_info, payload.get('udf1', ''), txn_id):
        val = (field or '').strip()
        if val.upper().startswith('WD-PAY') or val.upper().startswith('WD'):
            reference_id = val
            break
    # Fallback to txnid if no WD reference found
    if not reference_id:
        reference_id = txn_id

    logger.info(json.dumps({
        'event': 'payu_payment_success',
        'txnId': txn_id, 'payuId': payu_id,
        'amount': amount_rupees, 'phone': phone, 'mode': mode,
        'referenceId': reference_id, 'productInfo': product_info,
        'requestId': request_id,
    }))

    # Store payment record
    _store_payment(payload, 'captured', request_id)

    # Try to mark invoice paid by referenceId
    if reference_id:
        _mark_invoice_paid(reference_id, amount_rupees, phone, request_id)

    # Send order_status message to customer (GAP FIX: PayU webhook was not sending this)
    if phone and reference_id:
        try:
            clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '')
            if not clean_phone.startswith('91') and len(clean_phone) == 10:
                clean_phone = f'91{clean_phone}'

            # Resolve which phone sent the original payment — look up from invoice
            originating_phone_id = ''
            try:
                inv_table = dynamodb.Table(INVOICES_TABLE)
                inv_resp = inv_table.query(
                    IndexName='referenceId-index',
                    KeyConditionExpression='referenceId = :ref',
                    ExpressionAttributeValues={':ref': reference_id},
                    Limit=1,
                )
                inv_items = inv_resp.get('Items', [])
                if inv_items:
                    stored_config = inv_items[0].get('paymentConfiguration', '')
                    # WABA 1 configs have WECARE- prefix
                    if stored_config and ('WECARE-' in stored_config.upper() or 'UPIVPA' in stored_config.upper()):
                        originating_phone_id = 'phone-number-id-waba3-direct-1016149501586345'
                    else:
                        originating_phone_id = 'phone-number-id-waba-t-direct-1055232054343117'
            except Exception:
                pass
            if not originating_phone_id:
                originating_phone_id = 'phone-number-id-waba-t-direct-1055232054343117'

            order_status_payload = {
                'body': json.dumps({
                    'recipientPhone': f'+{clean_phone}',
                    'phoneNumberId': originating_phone_id,
                    'isOrderStatus': True,
                    'orderStatusDetails': {
                        'reference_id': reference_id,
                        'order_status': 'completed',
                        'amount': amount_rupees,
                        'description': f'Payment of \u20b9{amount_rupees:.2f} received via PayU. Thank you!'
                    }
                })
            }
            lambda_client.invoke(
                FunctionName=os.environ.get('OUTBOUND_FUNCTION', 'wecare-outbound-whatsapp'),
                InvocationType='Event',
                Payload=json.dumps(order_status_payload),
            )
            logger.info(json.dumps({'event': 'payu_order_status_sent', 'phone': clean_phone, 'referenceId': reference_id, 'phoneId': originating_phone_id, 'requestId': request_id}))
        except Exception as e:
            logger.warning(json.dumps({'event': 'payu_order_status_error', 'error': str(e), 'requestId': request_id}))


def _handle_failure(payload: Dict, request_id: str) -> None:
    """Handle failed PayU payment."""
    txn_id = payload.get('txnid') or ''
    payu_id = payload.get('mihpayid') or ''
    error_msg = payload.get('error_Message') or payload.get('unmappedstatus') or ''

    logger.warning(json.dumps({
        'event': 'payu_payment_failed',
        'txnId': txn_id, 'payuId': payu_id, 'error': error_msg,
        'requestId': request_id,
    }))

    _store_payment(payload, 'failed', request_id)


def _handle_pending(payload: Dict, request_id: str) -> None:
    """Handle pending PayU payment."""
    txn_id = payload.get('txnid') or ''
    payu_id = payload.get('mihpayid') or ''

    logger.info(json.dumps({
        'event': 'payu_payment_pending',
        'txnId': txn_id, 'payuId': payu_id,
        'requestId': request_id,
    }))

    _store_payment(payload, 'pending', request_id)


def _store_payment(payload: Dict, status: str, request_id: str) -> None:
    """Store/update payment record in PaymentsTable."""
    try:
        table = dynamodb.Table(PAYMENTS_TABLE)
        now = int(time.time())
        txn_id = payload.get('txnid') or ''
        payu_id = payload.get('mihpayid') or ''
        amount_str = payload.get('amount') or '0'
        product_info = payload.get('productinfo') or ''

        payment_id = f'payu_{payu_id}' if payu_id else f'payu_txn_{txn_id}'

        # Extract WD-PAY reference ID from productinfo, udf1, or txnid
        reference_id = ''
        for field in (product_info, payload.get('udf1', ''), txn_id):
            val = (field or '').strip()
            if val.upper().startswith('WD-PAY') or val.upper().startswith('WD'):
                reference_id = val
                break

        table.put_item(Item={
            'id': payment_id,
            'paymentId': payment_id,
            'referenceId': reference_id,
            'gateway': 'payu',
            'gatewayPaymentId': payu_id,
            'txnId': txn_id,
            'amount': int(float(amount_str) * 100),  # Store in paise
            'amountInRupees': Decimal(str(amount_str)),
            'currency': 'INR',
            'status': status,
            'method': payload.get('mode', ''),
            'contact': payload.get('phone', ''),
            'email': payload.get('email', ''),
            'productInfo': payload.get('productinfo', ''),
            'bankRef': payload.get('bank_ref_num', ''),
            'errorCode': payload.get('error', ''),
            'errorDescription': payload.get('error_Message', ''),
            'notes': json.dumps({
                'firstname': payload.get('firstname', ''),
                'udf1': payload.get('udf1', ''),
                'udf2': payload.get('udf2', ''),
                'udf3': payload.get('udf3', ''),
                'udf4': payload.get('udf4', ''),
                'udf5': payload.get('udf5', ''),
            }),
            'createdAt': now,
            'updatedAt': now,
        })

        logger.info(json.dumps({
            'event': 'payu_payment_stored',
            'paymentId': payment_id, 'status': status,
            'requestId': request_id,
        }))
    except Exception as e:
        logger.error(json.dumps({
            'event': 'payu_store_error', 'error': str(e),
            'requestId': request_id,
        }))


def _mark_invoice_paid(reference_id: str, amount_rupees: float, phone: str, request_id: str) -> None:
    """Mark matching invoice as paid."""
    try:
        table = dynamodb.Table(INVOICES_TABLE)
        now = int(time.time())

        # Find invoice by referenceId using GSI (efficient)
        found = []
        query_kwargs = {
            'IndexName': 'referenceId-index',
            'KeyConditionExpression': 'referenceId = :ref',
            'ExpressionAttributeValues': {':ref': reference_id},
        }
        resp = table.query(**query_kwargs)
        found.extend(resp.get('Items', []))
        while 'LastEvaluatedKey' in resp:
            query_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
            resp = table.query(**query_kwargs)
            found.extend(resp.get('Items', []))

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
                        ':pa': now, ':now': now,
                    },
                )
                logger.info(json.dumps({
                    'event': 'invoice_marked_paid_by_payu',
                    'invoiceId': inv['invoiceId'],
                    'referenceId': reference_id,
                    'requestId': request_id,
                }))

        if not found and phone:
            # Fallback: find by phone + amount (strict 10-digit match + exact amount ±₹0.01)
            clean_ph = phone.replace('+', '').replace(' ', '').replace('-', '')
            if clean_ph.startswith('91') and len(clean_ph) == 12:
                local10 = clean_ph[2:]
            elif len(clean_ph) >= 10:
                local10 = clean_ph[-10:]
            else:
                local10 = clean_ph
            scan_kwargs2 = {
                'FilterExpression': '#st IN (:s1, :s2, :s3)',
                'ExpressionAttributeNames': {'#st': 'status'},
                'ExpressionAttributeValues': {':s1': 'created', ':s2': 'pending_payment', ':s3': 'sent'},
            }
            candidates = []
            while True:
                resp = table.scan(**scan_kwargs2)
                for item in resp.get('Items', []):
                    inv_phone_raw = (item.get('customerPhone', '') or '').replace('+', '').replace(' ', '').replace('-', '')
                    if inv_phone_raw.startswith('91') and len(inv_phone_raw) == 12:
                        inv_local = inv_phone_raw[2:]
                    elif len(inv_phone_raw) >= 10:
                        inv_local = inv_phone_raw[-10:]
                    else:
                        inv_local = inv_phone_raw
                    inv_total = float(item.get('total', 0))
                    # STRICT: exact 10-digit match + amount within ₹0.01
                    if inv_local == local10 and len(local10) == 10 and abs(inv_total - amount_rupees) < 0.02:
                        candidates.append(item)
                if 'LastEvaluatedKey' in resp:
                    scan_kwargs2['ExclusiveStartKey'] = resp['LastEvaluatedKey']
                else:
                    break

            if candidates:
                candidates.sort(key=lambda x: int(x.get('createdAt', 0)))
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
                        ':pa': now, ':now': now,
                    },
                )
                logger.info(json.dumps({
                    'event': 'invoice_marked_paid_by_payu_phone',
                    'invoiceId': inv['invoiceId'],
                    'phone': phone, 'amount': amount_rupees,
                    'requestId': request_id,
                }))
    except Exception as e:
        logger.warning(json.dumps({
            'event': 'payu_mark_invoice_error',
            'referenceId': reference_id, 'error': str(e),
            'requestId': request_id,
        }))


def _resp(code: int, body: Dict) -> Dict:
    """Build HTTP response with CORS headers."""
    return {
        'statusCode': code,
        'headers': cors_headers(origin),
        'body': json.dumps(body, default=str),
    }


# ═══════════════════════════════════════════════════════════════════
# PayU API Helpers (OAuth + Payment Links + Verify)
# ═══════════════════════════════════════════════════════════════════

_oauth_token_cache = {'token': None, 'expires_at': 0}


def _get_payu_oauth_token() -> str:
    """Get OAuth Bearer token using client_credentials grant. Cached for TTL."""
    import urllib.request
    import urllib.parse

    now = int(time.time())
    if _oauth_token_cache['token'] and _oauth_token_cache['expires_at'] > now:
        return _oauth_token_cache['token']

    data = urllib.parse.urlencode({
        'grant_type': 'client_credentials',
        'client_id': PAYU_CLIENT_ID,
        'client_secret': PAYU_CLIENT_SECRET,
        'scope': 'create_payment_links read_payment_links',
    }).encode('utf-8')

    req = urllib.request.Request(PAYU_TOKEN_URL, data=data, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            token = result.get('access_token', '')
            expires_in = int(result.get('expires_in', 7200))
            _oauth_token_cache['token'] = token
            _oauth_token_cache['expires_at'] = now + expires_in - 60  # 1 min buffer
            logger.info(json.dumps({'event': 'payu_oauth_token_obtained', 'expiresIn': expires_in}))
            return token
    except Exception as e:
        logger.error(json.dumps({'event': 'payu_oauth_token_error', 'error': str(e)}))
        return ''


def _payu_verify_payment(txn_id: str) -> Dict:
    """Verify a payment using PayU's verify_payment API (key+salt hash auth)."""
    import urllib.request
    import urllib.parse

    command = 'verify_payment'
    hash_str = f'{PAYU_MERCHANT_KEY}|{command}|{txn_id}|{PAYU_MERCHANT_SALT}'
    hash_val = hashlib.sha512(hash_str.encode('utf-8')).hexdigest()

    data = urllib.parse.urlencode({
        'key': PAYU_MERCHANT_KEY,
        'command': command,
        'var1': txn_id,
        'hash': hash_val,
    }).encode('utf-8')

    url = f'{PAYU_BASE_URL}?form=2'
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        logger.error(json.dumps({'event': 'payu_verify_error', 'txnId': txn_id, 'error': str(e)}))
        return {'status': 0, 'msg': str(e)}
