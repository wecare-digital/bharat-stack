"""
Invoice Engine Lambda Function

Purpose: Unified invoice service for all 3 payment entry points
- Create invoices from payments
- Generate invoice image (PNG) and PDF
- Internal GST-compliant invoice sequencing
- Admin CRUD operations

DynamoDB Tables:
- stack-wecare-digital-InvoicesTable
- stack-wecare-digital-InvoiceItemsTable
- stack-wecare-digital-InvoiceSequenceTable
- stack-wecare-digital-InvoiceAssetsTable
- stack-wecare-digital-InvoiceDeliveryLogTable

S3 Bucket: app.wecare.digital
Prefix: stack/invoices/
"""

import os
import json
import uuid
import time
import logging
import boto3
import io
from typing import Dict, Any, Optional, List
from decimal import Decimal

from lambda_utils.response import cors_response, cors_headers, options_response, extract_origin
from lambda_utils.logging import get_logger

logger = get_logger(__name__)

IST_OFFSET = 5 * 3600 + 30 * 60  # UTC+5:30

def _ist_strftime(fmt: str, epoch) -> str:
    """Format epoch timestamp in IST (UTC+5:30)."""
    return time.strftime(fmt, time.gmtime(int(epoch) + IST_OFFSET))

dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
s3 = boto3.client('s3', region_name='us-east-1')
lambda_client = boto3.client('lambda', region_name='us-east-1')

INVOICES_TABLE = os.environ.get('INVOICES_TABLE', 'stack-wecare-digital-InvoicesTable')
INVOICE_ITEMS_TABLE = os.environ.get('INVOICE_ITEMS_TABLE', 'stack-wecare-digital-InvoiceItemsTable')
INVOICE_SEQ_TABLE = os.environ.get('INVOICE_SEQ_TABLE', 'stack-wecare-digital-InvoiceSequenceTable')
INVOICE_ASSETS_TABLE = os.environ.get('INVOICE_ASSETS_TABLE', 'stack-wecare-digital-InvoiceAssetsTable')
INVOICE_DELIVERY_TABLE = os.environ.get('INVOICE_DELIVERY_TABLE', 'stack-wecare-digital-InvoiceDeliveryLogTable')
PAYMENTS_TABLE = os.environ.get('PAYMENTS_TABLE', 'stack-wecare-digital-PaymentsTable')
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'stack-wecare-digital-ContactsTable')
SYSTEM_CONFIG_TABLE = os.environ.get('SYSTEM_CONFIG_TABLE', 'stack-wecare-digital-SystemConfigTable')
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')
INVOICE_PREFIX = 'stack/invoices/'
CDN_DOMAIN = os.environ.get('CDN_DOMAIN', 'app.wecare.digital')

# Module-level origin for CORS (set per-invocation in handler)
origin = ''

# Company details for invoice
COMPANY = {
    'name': 'WECARE.DIGITAL',
    'gstin': '19AADFW7431N1ZK',
    'pan': 'AADFW7431N',
    'address': 'The W.B.S.I.D.C. Building, Unit 1/20, 81/2/7, Phears Ln, Kolkata, WB 700012',
    'email': 'one@wecare.digital',
    'phone': '+91 93309 94400',
    'website': 'https://wecare.digital',
    'logo_s3_key': 'stream/media/m/wecare-digital.png',
    'paid_icon_s3_key': 'stream/media/m/paid.png',
}


def _load_logo_bytes() -> Optional[bytes]:
    """Load company logo from S3 with /tmp cache for Lambda warm starts."""
    cache_path = '/tmp/_logo_cache.png'
    try:
        with open(cache_path, 'rb') as f:
            return f.read()
    except FileNotFoundError:
        pass
    try:
        obj = s3.get_object(Bucket=MEDIA_BUCKET, Key=COMPANY['logo_s3_key'])
        data = obj['Body'].read()
        try:
            with open(cache_path, 'wb') as f:
                f.write(data)
        except Exception as _e:
            logger.debug(f"Logo cache write failed: {_e}")
        return data
    except Exception as e:
        logger.warning(f"Logo load error: {e}")
        return None


def _load_s3_image(key: str):
    """Load an image from S3 as PIL Image (RGBA) with /tmp cache."""
    import hashlib
    cache_path = f"/tmp/_s3img_{hashlib.md5(key.encode()).hexdigest()}.png"
    try:
        from PIL import Image as PILImage
        return PILImage.open(cache_path).convert('RGBA')
    except Exception as _e:
        logger.debug(f"S3 image cache miss: {_e}")
    try:
        from PIL import Image as PILImage
        obj = s3.get_object(Bucket=MEDIA_BUCKET, Key=key)
        data = obj['Body'].read()
        img = PILImage.open(io.BytesIO(data)).convert('RGBA')
        try:
            img.save(cache_path, 'PNG')
        except Exception as _e:
            logger.debug(f"S3 image cache write failed: {_e}")
        return img
    except Exception as e:
        logger.warning(f"S3 image load error ({key}): {e}")
        return None


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Route invoice engine requests."""
    request_id = context.aws_request_id if context else 'local'
    global origin
    origin = extract_origin(event)
    method = event.get('requestContext', {}).get('http', {}).get('method', 'GET')

    path = event.get('rawPath', event.get('path', ''))
    params = event.get('queryStringParameters') or {}
    path_params = event.get('pathParameters') or {}

    logger.info(json.dumps({'event': 'invoice_engine', 'method': method, 'path': path, 'requestId': request_id}))

    try:
        body = json.loads(event.get('body', '{}')) if event.get('body') else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        body = {}

    try:
        # POST /invoices with _action=clear-all — body-based trigger for cleanup via existing route
        if method == 'POST' and body.get('_action') == 'clear-all':
            return clear_all_invoice_data(request_id)

        # POST /invoices/from-payment — create from payment ID (check BEFORE generic POST)
        if method == 'POST' and 'from-payment' in path:
            return create_invoice_from_payment(body, request_id)

        # POST /invoices/send-pending-by-phone — find & send all pending invoices for a phone
        if method == 'POST' and 'send-pending-by-phone' in path:
            return send_pending_by_phone(body, request_id)

        # POST /invoices/next-sequence — get next invoice number (admin)
        if method == 'POST' and 'next-sequence' in path:
            return get_next_sequence_preview(body, request_id)

        # POST /invoices/{id}/generate-image
        if method == 'POST' and 'generate-image' in path:
            inv_id = path_params.get('invoiceId') or body.get('invoiceId')
            return generate_invoice_image(inv_id, request_id)

        # POST /invoices/{id}/generate-pdf
        if method == 'POST' and 'generate-pdf' in path:
            inv_id = path_params.get('invoiceId') or body.get('invoiceId')
            return generate_invoice_pdf(inv_id, request_id)

        # POST /invoices/{id}/send-whatsapp
        if method == 'POST' and 'send-whatsapp' in path:
            inv_id = path_params.get('invoiceId') or body.get('invoiceId')
            phone = body.get('toWhatsAppNumber')
            phone_number_id = body.get('phoneNumberId')
            return send_invoice_whatsapp(inv_id, phone, phone_number_id, request_id)

        # POST /invoices/{id}/send-payment-link — send WhatsApp interactive payment message
        if method == 'POST' and 'send-payment-link' in path:
            inv_id = path_params.get('invoiceId') or body.get('invoiceId')
            phone_number_id = body.get('phoneNumberId')
            payment_configuration = body.get('paymentConfiguration', '')
            return send_payment_link(inv_id, phone_number_id, payment_configuration, request_id)

        # POST /invoices/{id}/cancel — cancel/void an invoice
        if method == 'POST' and 'cancel' in path:
            inv_id = path_params.get('invoiceId') or body.get('invoiceId')
            reason = body.get('reason', '')
            return cancel_invoice(inv_id, reason, request_id)

        # POST /invoices/{id}/remark — add remark/refund/credit note
        if method == 'POST' and 'remark' in path:
            inv_id = path_params.get('invoiceId') or body.get('invoiceId')
            return add_remark(inv_id, body, request_id)

        # DELETE /invoices/clear-all — wipe all invoice-related tables (admin cleanup)
        if method == 'DELETE' and 'clear-all' in path:
            return clear_all_invoice_data(request_id)

        # POST /invoices/clear-all — alternative POST route for clear-all (when DELETE not in API GW)
        if method == 'POST' and 'clear-all' in path:
            return clear_all_invoice_data(request_id)

        # DELETE /invoices/{id} — hard delete invoice + adjust sequence
        if method == 'DELETE' and path_params.get('invoiceId'):
            return delete_invoice(path_params['invoiceId'], body, request_id)

        # POST /invoices — create invoice (generic, must be LAST POST check)
        if method == 'POST':
            return create_invoice(body, request_id)

        # PUT /invoices/{id} — update invoice
        if method == 'PUT' and path_params.get('invoiceId'):
            return update_invoice(path_params['invoiceId'], body, request_id)

        # GET /invoices/{id}/delivery-log
        if method == 'GET' and 'delivery-log' in path:
            inv_id = path_params.get('invoiceId')
            return get_delivery_log(inv_id, request_id)

        # GET /invoices — list
        if method == 'GET' and not path_params.get('invoiceId'):
            return list_invoices(params, request_id)

        # GET /invoices/{id} — get single
        if method == 'GET' and path_params.get('invoiceId'):
            return get_invoice(path_params['invoiceId'], request_id)

        return _resp(405, {'error': 'Method not allowed'})

    except Exception as e:
        logger.error(json.dumps({'event': 'invoice_engine_error', 'error': str(e), 'requestId': request_id}))
        return _resp(500, {'error': str(e)})


# ─── Invoice Sequencing (GST-compliant, internal only) ───

def _get_next_invoice_number(fy: str = None) -> str:
    """Generate next sequential invoice number. Format: WD/FY/NNNNN"""
    if not fy:
        now = time.localtime()
        year = now.tm_year
        month = now.tm_mon
        fy = f"{year}-{year+1}" if month >= 4 else f"{year-1}-{year}"

    table = dynamodb.Table(INVOICE_SEQ_TABLE)
    try:
        resp = table.update_item(
            Key={'fy': fy},
            UpdateExpression='SET last_seq = if_not_exists(last_seq, :zero) + :inc, prefix = if_not_exists(prefix, :pfx), updated_at = :now',
            ExpressionAttributeValues={':zero': 0, ':inc': 1, ':pfx': 'WD', ':now': int(time.time())},
            ReturnValues='UPDATED_NEW',
        )
        seq = int(resp['Attributes']['last_seq'])
        prefix = resp['Attributes'].get('prefix', 'WD')
        fy_short = fy.replace('20', '').replace('-', '')
        return f"{prefix}/{fy_short}/{seq:05d}"
    except Exception as e:
        logger.error(f"Sequence error: {e}")
        return f"WD-PAY-TEMP-{uuid.uuid4().hex[:8].upper()}"


def get_next_sequence_preview(body: Dict, request_id: str) -> Dict:
    """Preview next invoice number without incrementing."""
    fy = body.get('fy')
    if not fy:
        now = time.localtime()
        year = now.tm_year
        month = now.tm_mon
        fy = f"{year}-{year+1}" if month >= 4 else f"{year-1}-{year}"

    table = dynamodb.Table(INVOICE_SEQ_TABLE)
    try:
        resp = table.get_item(Key={'fy': fy})
        item = resp.get('Item', {})
        last = int(item.get('last_seq', 0))
        prefix = item.get('prefix', 'WD')
        fy_short = fy.replace('20', '').replace('-', '')
        next_num = f"{prefix}/{fy_short}/{last+1:05d}"
        return _resp(200, {'nextInvoiceNumber': next_num, 'fy': fy, 'lastSeq': last})
    except Exception as e:
        return _resp(500, {'error': str(e)})


# ─── Create Invoice ───

def create_invoice(body: Dict, request_id: str) -> Dict:
    """Create a new invoice from direct input. Includes deduplication by referenceId/paymentId."""
    now = int(time.time())

    # ── Deduplication: check if invoice already exists for this referenceId or paymentId ──
    reference_id = body.get('referenceId', '')
    payment_id = body.get('paymentId', '')
    table = dynamodb.Table(INVOICES_TABLE)

    if reference_id or payment_id:
        try:
            filter_parts = []
            expr_values = {}
            if reference_id:
                filter_parts.append('referenceId = :ref')
                expr_values[':ref'] = reference_id
            if payment_id:
                filter_parts.append('paymentId = :pid')
                expr_values[':pid'] = payment_id

            filter_expr = ' OR '.join(filter_parts)
            # Full pagination to avoid DynamoDB Limit bug (Limit = items evaluated, not returned)
            existing = []
            scan_kwargs = {'FilterExpression': filter_expr, 'ExpressionAttributeValues': expr_values}
            while True:
                result = table.scan(**scan_kwargs)
                existing.extend(result.get('Items', []))
                if existing or 'LastEvaluatedKey' not in result:
                    break
                scan_kwargs['ExclusiveStartKey'] = result['LastEvaluatedKey']

            if existing:
                inv = existing[0]
                existing_id = inv.get('invoiceId', '')

                # If caller says this is now paid, update the existing invoice status
                incoming_status = body.get('status', '')
                incoming_ps = body.get('paymentStatus', '')
                if incoming_status == 'paid' and incoming_ps == 'captured' and inv.get('status') != 'paid':
                    try:
                        table.update_item(
                            Key={'invoiceId': existing_id},
                            UpdateExpression='SET #st = :st, #ps = :ps, #pa = :pa, #ua = :now',
                            ExpressionAttributeNames={'#st': 'status', '#ps': 'paymentStatus', '#pa': 'paidAt', '#ua': 'updatedAt'},
                            ExpressionAttributeValues={
                                ':st': 'paid', ':ps': 'captured',
                                ':pa': body.get('paidAt', now), ':now': now,
                            },
                        )
                        logger.info(json.dumps({
                            'event': 'invoice_dedup_status_updated',
                            'invoiceId': existing_id,
                            'newStatus': 'paid',
                            'requestId': request_id,
                        }))
                    except Exception as upd_err:
                        logger.warning(json.dumps({
                            'event': 'invoice_dedup_status_update_error',
                            'invoiceId': existing_id,
                            'error': str(upd_err),
                            'requestId': request_id,
                        }))

                logger.info(json.dumps({
                    'event': 'invoice_dedup_hit',
                    'existingInvoiceId': existing_id,
                    'referenceId': reference_id,
                    'paymentId': payment_id,
                    'requestId': request_id,
                }))
                return _resp(200, {
                    'invoiceId': existing_id,
                    'invoiceNumber': inv.get('invoiceNumber', ''),
                    'total': float(inv.get('total', 0)),
                    'referenceId': inv.get('referenceId', ''),
                    'deduplicated': True,
                })
        except Exception as dedup_err:
            logger.warning(json.dumps({
                'event': 'invoice_dedup_check_error',
                'error': str(dedup_err),
                'requestId': request_id,
            }))

    invoice_id = str(uuid.uuid4())

    # Auto-generate referenceId if not provided (WD-PAY- + 8-char hex)
    if not reference_id:
        reference_id = f"WD-PAY-{uuid.uuid4().hex[:8].upper()}"

    # Validate mandatory fields (relaxed for webhook-originated invoices)
    customer_phone = body.get('customerPhone', '')
    paid_by_phone = body.get('paidByPhone', customer_phone)
    customer_email = body.get('customerEmail', '')
    shipping_address = body.get('shippingAddress', '')
    billing_address = body.get('billingAddress', '')
    entry_point = body.get('entryPoint', 'manual')

    if not customer_phone:
        return _resp(400, {'error': 'Missing mandatory field: customerPhone'})

    invoice_number = _get_next_invoice_number(body.get('fy'))

    items = body.get('items', [])
    subtotal = sum(float(i.get('amount', 0)) * int(i.get('quantity', 1)) for i in items)
    discount = float(body.get('discount', 0))
    green_packing = float(body.get('greenPacking', 0))
    notification_fee = float(body.get('notificationFee', 0))

    # Detect if Green Packing / Notification Fee are already in items (new frontend sends them inline)
    gp_in_items = 0.0
    nf_in_items = 0.0
    for it in items:
        nm = (it.get('name', '') or '').lower()
        it_total = float(it.get('amount', 0)) * int(it.get('quantity', 1))
        if 'green' in nm and 'pack' in nm:
            gp_in_items = it_total
        elif 'notification' in nm or 'alert' in nm:
            nf_in_items = it_total

    # If charge items are in the items array, they're already in subtotal — don't add again
    # If sent as separate fields (legacy), add them to total
    effective_gp = green_packing if gp_in_items == 0 else 0.0
    effective_nf = notification_fee if nf_in_items == 0 else 0.0

    # shipping field = express only (greenPacking + notificationFee stored as line items)
    shipping = float(body.get('shipping', 0)) - green_packing - notification_fee
    if shipping < 0: shipping = 0.0
    handling = float(body.get('handling', 0))
    gst_rate = float(body.get('gstRate', 18))

    # ── Validate: no negative amounts ──
    if subtotal < 0:
        return _resp(400, {'error': 'Subtotal cannot be negative'})
    if discount < 0:
        return _resp(400, {'error': 'Discount cannot be negative'})
    if gst_rate < 0 or gst_rate > 100:
        return _resp(400, {'error': 'GST rate must be between 0 and 100'})
    for idx_v, it_v in enumerate(items):
        if float(it_v.get('amount', 0)) < 0:
            return _resp(400, {'error': f'Item {idx_v+1} amount cannot be negative'})
        if int(it_v.get('quantity', 1)) < 1:
            return _resp(400, {'error': f'Item {idx_v+1} quantity must be at least 1'})

    tax = sum(
        float(i.get('amount', 0)) * int(i.get('quantity', 1)) * float(i.get('gstRate', gst_rate)) / 100
        for i in items
    )
    tax = round(tax, 2)

    # Convenience fee: 2% of total collection + 18% GST on that 2%
    # "Total collection" = subtotal - discount + shipping + handling + tax + GP + NF
    convenience_fee = float(body.get('convenienceFee', 0))
    if convenience_fee == 0 and entry_point in ('pay_flow', 'manual', 'whatsapp_payment'):
        collection = subtotal - discount + shipping + effective_gp + effective_nf + handling + tax
        conv_base = round(collection * 0.02, 2)
        conv_gst = round(conv_base * 0.18, 2)
        convenience_fee = round(conv_base + conv_gst, 2)

    total = subtotal - discount + shipping + effective_gp + effective_nf + handling + tax + convenience_fee

    # Determine initial status
    status = body.get('status', 'created')
    payment_status = body.get('paymentStatus', 'pending')

    invoice = {
        'invoiceId': invoice_id,
        'invoiceNumber': invoice_number,
        'paymentId': payment_id,
        'orderId': body.get('orderId', ''),
        'referenceId': reference_id,
        'entryPoint': entry_point,
        'status': status,
        'paymentStatus': payment_status,
        # Customer
        'contactId': body.get('contactId', ''),
        'customerName': body.get('customerName', ''),
        'customerPhone': customer_phone,
        'paidByPhone': paid_by_phone,
        'customerEmail': customer_email,
        'shippingAddress': shipping_address,
        'billingAddress': billing_address,
        # Amounts (stored in rupees)
        'subtotal': _dec(subtotal),
        'discount': _dec(discount),
        'shipping': _dec(shipping),
        'handling': _dec(handling),
        'gstRate': _dec(gst_rate),
        'tax': _dec(tax),
        'convenienceFee': _dec(convenience_fee),
        'total': _dec(total),
        'currency': body.get('currency', 'INR'),
        'gstin': body.get('gstin', COMPANY['gstin']),
        'purpose': body.get('purpose', ''),
        'notes': body.get('notes', ''),
        # Timestamps
        'createdAt': now,
        'updatedAt': now,
        'paidAt': body.get('paidAt', 0),
    }

    table.put_item(
        Item={k: v for k, v in invoice.items() if v is not None and v != ''},
        ConditionExpression='attribute_not_exists(invoiceId)',
    )

    # Store invoice items (including greenPacking + notificationFee as line items)
    items_table = dynamodb.Table(INVOICE_ITEMS_TABLE)
    all_items = list(items)

    # Check if Green Packing / Notification Fee already exist as items (new frontend sends them inline)
    existing_names = {(it.get('name', '') or '').lower() for it in all_items}
    has_green = any('green' in n and 'pack' in n for n in existing_names)
    has_notif = any('notification' in n or 'alert' in n for n in existing_names)

    # Legacy support: if sent as separate fields and NOT already in items, append them
    green_packing = float(body.get('greenPacking', 0))
    notification_fee = float(body.get('notificationFee', 0))
    if green_packing > 0 and not has_green:
        all_items.append({'name': 'Green Packing', 'amount': green_packing, 'quantity': 1, 'isCharge': True})
    if notification_fee > 0 and not has_notif:
        all_items.append({'name': 'Notification Fee', 'amount': notification_fee, 'quantity': 1, 'isCharge': True})
    if all_items:
        for idx, item in enumerate(all_items):
            items_table.put_item(Item={
                'invoiceId': invoice_id,
                'itemIndex': idx,
                'name': item.get('name', 'Item'),
                'amount': _dec(float(item.get('amount', 0))),
                'quantity': int(item.get('quantity', 1)),
                'gstRate': _dec(float(item.get('gstRate', gst_rate))),
                'productId': item.get('productId', ''),
                'isCharge': item.get('isCharge', False),
            })

    logger.info(json.dumps({'event': 'invoice_created', 'invoiceId': invoice_id, 'invoiceNumber': invoice_number, 'referenceId': reference_id, 'total': float(total), 'requestId': request_id}))
    return _resp(201, {'invoiceId': invoice_id, 'invoiceNumber': invoice_number, 'referenceId': reference_id, 'total': float(total), 'convenienceFee': float(convenience_fee)})



def create_invoice_from_payment(body: Dict, request_id: str) -> Dict:
    """Create invoice from a Razorpay payment ID. Called by PostPaymentHandler."""
    payment_id = body.get('paymentId')
    if not payment_id:
        return _resp(400, {'error': 'paymentId required'})

    # Fetch payment record (full pagination to avoid DynamoDB Limit bug)
    payments_table = dynamodb.Table(PAYMENTS_TABLE)
    try:
        items = []
        scan_kwargs = {
            'FilterExpression': boto3.dynamodb.conditions.Attr('paymentId').eq(payment_id),
        }
        while True:
            result = payments_table.scan(**scan_kwargs)
            items.extend(result.get('Items', []))
            if items or 'LastEvaluatedKey' not in result:
                break
            scan_kwargs['ExclusiveStartKey'] = result['LastEvaluatedKey']
        if not items:
            return _resp(404, {'error': f'Payment {payment_id} not found'})
        payment = items[0]
    except Exception as e:
        return _resp(500, {'error': f'Payment lookup failed: {e}'})

    # Fetch contact if available
    contact_phone = payment.get('contact', '')
    contact = _lookup_contact_by_phone(contact_phone)

    # Build invoice body from payment + contact
    inv_body = {
        'paymentId': payment_id,
        'orderId': payment.get('orderId', ''),
        'referenceId': payment.get('referenceId', ''),
        'entryPoint': body.get('entryPoint', 'webhook'),
        'status': 'paid',
        'paymentStatus': 'captured',
        'paidAt': int(float(payment.get('createdAt', time.time()))),
        'contactId': contact.get('contactId', '') if contact else '',
        'customerName': contact.get('name', '') if contact else '',
        'customerPhone': contact_phone,
        'paidByPhone': contact_phone,
        'customerEmail': contact.get('email', payment.get('email', '')) if contact else payment.get('email', ''),
        'shippingAddress': contact.get('shippingAddress', '') if contact else '',
        'billingAddress': contact.get('billingAddress', '') if contact else '',
        'items': body.get('items', [{'name': body.get('itemName', 'Payment'), 'amount': float(payment.get('amountInRupees', 0)), 'quantity': 1}]),
        'discount': float(body.get('discount', 0)),
        'shipping': float(body.get('shipping', 0)),
        'gstRate': float(body.get('gstRate', 18)),
        'convenienceFee': float(body.get('convenienceFee', 0)),
        'gstin': body.get('gstin', COMPANY['gstin']),
        'purpose': body.get('purpose', ''),
        'currency': payment.get('currency', 'INR'),
    }

    return create_invoice(inv_body, request_id)


# ─── Update / Read / List ───

def update_invoice(invoice_id: str, body: Dict, request_id: str) -> Dict:
    """Update an existing invoice (admin). Blocks amount changes on paid/cancelled invoices."""
    table = dynamodb.Table(INVOICES_TABLE)

    # Status guard: block amount changes on paid/cancelled invoices
    amount_fields = {'subtotal', 'discount', 'shipping', 'handling', 'gstRate', 'tax', 'convenienceFee', 'total'}
    if amount_fields & set(body.keys()):
        try:
            existing = table.get_item(Key={'invoiceId': invoice_id}).get('Item', {})
            ex_status = existing.get('status', '')
            ex_ps = existing.get('paymentStatus', '')
            if ex_status in ('paid', 'cancelled') or ex_ps in ('captured', 'refunded'):
                return _resp(400, {'error': f'Cannot modify amounts on {ex_status} invoice (paymentStatus={ex_ps})'})
        except Exception as e:
            logger.warning(f'Invoice status guard check failed for {invoice_id}: {e}')

    update_parts = []
    values = {}
    names = {}

    allowed = ['customerName', 'customerPhone', 'paidByPhone', 'customerEmail',
               'shippingAddress', 'billingAddress', 'status', 'paymentStatus',
               'discount', 'shipping', 'handling', 'gstRate', 'tax', 'convenienceFee', 'total',
               'gstin', 'purpose', 'notes', 'subtotal', 'orderId', 'referenceId']

    for key in allowed:
        if key in body:
            attr = f"#{key}"
            val = f":{key}"
            update_parts.append(f"{attr} = {val}")
            names[attr] = key
            v = body[key]
            values[val] = _dec(v) if isinstance(v, (int, float)) else v

    if not update_parts:
        return _resp(400, {'error': 'No fields to update'})

    values[':now'] = int(time.time())
    update_parts.append('#updatedAt = :now')
    names['#updatedAt'] = 'updatedAt'

    try:
        table.update_item(
            Key={'invoiceId': invoice_id},
            UpdateExpression='SET ' + ', '.join(update_parts),
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
        )

        # Regenerate image if amount/customer fields changed
        regen_fields = {'subtotal', 'discount', 'shipping', 'tax', 'total', 'convenienceFee',
                        'customerName', 'customerPhone', 'paymentStatus', 'gstRate',
                        'shippingAddress', 'billingAddress', 'purpose'}
        if regen_fields & set(body.keys()):
            try:
                generate_invoice_image(invoice_id, request_id)
                logger.info(json.dumps({'event': 'invoice_image_regenerated', 'invoiceId': invoice_id, 'requestId': request_id}))
            except Exception as regen_err:
                logger.warning(f"Image regen after update failed: {regen_err}")

        return _resp(200, {'invoiceId': invoice_id, 'updated': True})
    except Exception as e:
        return _resp(500, {'error': str(e)})


def get_invoice(invoice_id: str, request_id: str) -> Dict:
    """Get a single invoice with items and assets."""
    table = dynamodb.Table(INVOICES_TABLE)
    resp = table.get_item(Key={'invoiceId': invoice_id})
    invoice = resp.get('Item')
    if not invoice:
        return _resp(404, {'error': 'Invoice not found'})

    # Get items
    items_table = dynamodb.Table(INVOICE_ITEMS_TABLE)
    items_resp = items_table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key('invoiceId').eq(invoice_id)
    )
    items = sorted(items_resp.get('Items', []), key=lambda x: int(x.get('itemIndex', 0)))

    # Get assets
    assets_table = dynamodb.Table(INVOICE_ASSETS_TABLE)
    assets_resp = assets_table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key('invoiceId').eq(invoice_id)
    )
    assets = assets_resp.get('Items', [])

    result = _normalize_invoice(invoice)
    result['items'] = [_normalize_item(i) for i in items]
    result['assets'] = [_normalize_asset(a) for a in assets]

    return _resp(200, {'invoice': result})


def list_invoices(params: Dict, request_id: str) -> Dict:
    """List invoices with optional filters. Full pagination to avoid DynamoDB Limit bug."""
    table = dynamodb.Table(INVOICES_TABLE)
    scan_kwargs = {}

    filters = []
    if params.get('status'):
        filters.append(boto3.dynamodb.conditions.Attr('status').eq(params['status']))
    if params.get('contactId'):
        filters.append(boto3.dynamodb.conditions.Attr('contactId').eq(params['contactId']))
    if params.get('paymentId'):
        filters.append(boto3.dynamodb.conditions.Attr('paymentId').eq(params['paymentId']))

    if filters:
        combined = filters[0]
        for f in filters[1:]:
            combined = combined & f
        scan_kwargs['FilterExpression'] = combined

    invoices = []
    while True:
        result = table.scan(**scan_kwargs)
        invoices.extend(result.get('Items', []))
        if 'LastEvaluatedKey' in result:
            scan_kwargs['ExclusiveStartKey'] = result['LastEvaluatedKey']
        else:
            break

    invoices.sort(key=lambda x: int(x.get('createdAt', 0)), reverse=True)

    return _resp(200, {'invoices': [_normalize_invoice(i) for i in invoices], 'count': len(invoices)})


# ─── Invoice Rendering (POS Receipt Style Image + PDF) ───


def _build_invoice_html(invoice: Dict, items: List[Dict]) -> str:
    """Build POS receipt style HTML with logo for invoice rendering."""
    inv_num = invoice.get('invoiceNumber', '')
    cust_name = invoice.get('customerName', 'Customer')
    cust_phone = invoice.get('customerPhone', '')
    cust_email = invoice.get('customerEmail', '')
    ship_addr = invoice.get('shippingAddress', '')
    bill_addr = invoice.get('billingAddress', '')
    subtotal = float(invoice.get('subtotal', 0))
    discount = float(invoice.get('discount', 0))
    shipping_amt = float(invoice.get('shipping', 0))
    handling_amt = float(invoice.get('handling', 0))
    tax = float(invoice.get('tax', 0))
    gst_rate = float(invoice.get('gstRate', 0))
    conv_fee = float(invoice.get('convenienceFee', 0))
    total = float(invoice.get('total', 0))
    gstin = invoice.get('gstin', COMPANY['gstin'])
    purpose = invoice.get('purpose', '') or ''
    if purpose.lower().startswith('menu_'):
        purpose = ''
    payment_id = invoice.get('paymentId', '')
    order_id = invoice.get('orderId', '')
    paid_at = invoice.get('paidAt', 0)
    created_at = invoice.get('createdAt', 0)
    payment_status = invoice.get('paymentStatus', 'pending')

    date_str = _ist_strftime('%d-%m-%Y', int(created_at)) if created_at else ''
    time_str = _ist_strftime('%H:%M IST', int(created_at)) if created_at else ''
    if paid_at and int(paid_at) > 0:
        paid_str = _ist_strftime('%d-%m-%Y %H:%M IST', int(paid_at))
    elif payment_status == 'captured':
        paid_str = _ist_strftime('%d-%m-%Y %H:%M IST', int(time.time()))
    else:
        paid_str = ''

    cgst = tax / 2
    sgst = tax / 2

    # Logo as base64 data URI
    logo_html = ''
    try:
        logo_bytes = _load_logo_bytes()
        if logo_bytes:
            import base64
            b64 = base64.b64encode(logo_bytes).decode('ascii')
            logo_html = f'<img src="data:image/png;base64,{b64}" style="width:60px;height:60px;object-fit:contain;margin-bottom:6px" alt="Logo">'
    except Exception as _e:
        logger.debug(f"HTML logo embed failed: {_e}")

    # Extract Green Packing and Notification Fee from items (stored as charge line items)
    green_packing_amt = 0.0
    notification_fee_amt = 0.0
    for it in items:
        if it.get('isCharge'):
            nm = (it.get('name', '') or '').lower()
            amt_val = float(it.get('amount', 0)) * int(it.get('quantity', 1))
            if 'green' in nm and 'pack' in nm:
                green_packing_amt = amt_val
            elif 'notification' in nm or 'alert' in nm:
                notification_fee_amt = amt_val

    # Items rows
    items_html = ''
    total_qty = 0
    for i, item in enumerate(items):
        name = item.get('name', 'Item')
        amt = float(item.get('amount', 0))
        qty = int(item.get('quantity', 1))
        total_qty += qty
        line_total = amt * qty
        items_html += f'<tr><td>{i+1}</td><td>{name}</td><td class="r">{qty}</td><td class="r">{amt:,.2f}</td><td class="r">{line_total:,.2f}</td></tr>'

    # GST breakdown
    gst_html = ''
    if gst_rate > 0:
        half_rate = gst_rate / 2
        taxable = subtotal - discount
        gst_html = f'''<div class="divider"></div>
        <div class="section-title">GST Summary</div>
        <div class="total-row"><span>Taxable Amount</span><span>{taxable:,.2f}</span></div>
        <div class="total-row"><span>CGST @{half_rate:.1f}%</span><span>{cgst:,.2f}</span></div>
        <div class="total-row"><span>SGST @{half_rate:.1f}%</span><span>{sgst:,.2f}</span></div>
        <div class="total-row b"><span>Total Tax</span><span>{tax:,.2f}</span></div>'''

    reference_id = invoice.get('referenceId', '')

    # Customer-facing fields only (no internal invoice number, no payment ID)
    ref_id_html = f'<div class="info-row"><span>Ref: {reference_id}</span></div>' if reference_id else ''

    # Status badge color
    status_upper = payment_status.upper()
    badge_color = '#059669' if status_upper == 'CAPTURED' else '#d97706' if status_upper == 'PENDING' else '#dc2626'
    badge_bg = '#D1FAE5' if status_upper == 'CAPTURED' else '#FEF3C7' if status_upper == 'PENDING' else '#FEE2E2'

    return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Courier New',Courier,monospace;color:#1a1a1a;background:#fff;width:420px;padding:18px;font-size:12px;line-height:1.4}}
.center{{text-align:center}}
.r{{text-align:right}}
.b{{font-weight:bold}}
h1{{font-size:17px;margin:2px 0;letter-spacing:1px}}
.subtitle{{font-size:10px;color:#555;margin:1px 0}}
.divider{{border-top:1px dashed #999;margin:8px 0}}
.divider2{{border-top:2px solid #333;margin:8px 0}}
.section-title{{font-size:11px;font-weight:bold;color:#333;margin:4px 0 2px;text-transform:uppercase;letter-spacing:0.5px}}
table{{width:100%;border-collapse:collapse;font-size:11px;margin:4px 0}}
th{{text-align:left;padding:3px 2px;border-bottom:1px solid #333;font-size:10px;text-transform:uppercase;color:#555}}
th.r{{text-align:right}}
td{{padding:3px 2px;vertical-align:top}}
.info-row{{display:flex;justify-content:space-between;font-size:11px;margin:2px 0}}
.addr{{font-size:10px;color:#444;margin:2px 0 4px;line-height:1.3}}
.total-row{{display:flex;justify-content:space-between;font-size:12px;margin:2px 0}}
.grand{{font-size:15px;font-weight:bold;background:#f0fdf4;padding:6px 4px;margin:4px -4px;border-top:2px solid #333;border-bottom:2px solid #333}}
.badge{{display:inline-block;padding:2px 10px;font-size:10px;font-weight:bold;border-radius:3px;color:{badge_color};background:{badge_bg};border:1px solid {badge_color}}}
.footer{{margin-top:10px;text-align:center;font-size:10px;color:#777}}
.paid-stamp{{font-size:18px;font-weight:bold;color:#059669;text-align:center;margin:6px 0;letter-spacing:2px}}
</style></head><body>
<div class="center">
    {logo_html}
    <h1>{COMPANY['name']}</h1>
    <div class="subtitle">GSTIN: {COMPANY['gstin']}</div>
    <div class="subtitle">{COMPANY['address']}</div>
    <div class="subtitle">{COMPANY['phone']} | {COMPANY['email']}</div>
</div>
<div class="divider2"></div>
<div class="center" style="margin:4px 0"><span style="font-size:13px;font-weight:bold;letter-spacing:1px">Invoice</span></div>
<div class="divider"></div>
<div class="info-row"><span>Date: {date_str}</span><span>{time_str}</span></div>
{ref_id_html}
{f'<div class="info-row"><span>Brand: {purpose}</span></div>' if purpose else ''}
<div class="info-row"><span>Order: {order_id or 'Offline'}</span></div>
<div class="divider"></div>
<div class="section-title">Bill To</div>
<div style="font-size:11px;font-weight:bold">{cust_name}</div>
<div class="addr">{cust_phone}{(' | ' + cust_email) if cust_email else ''}</div>
<div class="addr">{bill_addr if bill_addr else '-'}</div>
<div class="section-title">Ship To</div>
<div class="addr">{ship_addr if ship_addr else '-'}</div>
<div class="divider"></div>
<table>
    <thead><tr><th>#</th><th>Item</th><th class="r">Qty</th><th class="r">Rate</th><th class="r">Amount</th></tr></thead>
    <tbody>{items_html}</tbody>
</table>
<div class="divider"></div>
<div class="total-row"><span>Subtotal</span><span>{subtotal:,.2f}</span></div>
{'<div class="total-row"><span>Promo</span><span>-' + f'{discount:,.2f}' + '</span></div>' if discount else ''}
{'<div class="total-row"><span>Express</span><span>' + f'{shipping_amt:,.2f}' + '</span></div>' if shipping_amt else ''}
{'<div class="total-row"><span>Green Packing</span><span>' + f'{green_packing_amt:,.2f}' + '</span></div>' if green_packing_amt else ''}
{'<div class="total-row"><span>Notification Fee</span><span>' + f'{notification_fee_amt:,.2f}' + '</span></div>' if notification_fee_amt else ''}
{'<div class="total-row"><span>Handling</span><span>' + f'{handling_amt:,.2f}' + '</span></div>' if handling_amt else ''}
<div class="total-row"><span>CGST @{gst_rate/2:.1f}%</span><span>{cgst:,.2f}</span></div>
<div class="total-row"><span>SGST @{gst_rate/2:.1f}%</span><span>{sgst:,.2f}</span></div>
{'<div class="total-row"><span>Conv Fee</span><span>' + f'{conv_fee:,.2f}' + '</span></div>' if conv_fee else ''}
<div class="total-row grand"><span>Total ({total_qty} items)</span><span>&#8377; {total:,.2f}</span></div>
{gst_html}
<div class="divider2"></div>
{'<div class="paid-stamp">PAID</div>' if status_upper == 'CAPTURED' else ''}
<div class="info-row"><span>Status: <span class="badge">{status_upper}</span></span></div>
{f'<div class="info-row"><span>Paid: {paid_str}</span></div>' if paid_str else ''}
<div class="divider2"></div>
<div class="footer">
    <div style="font-size:12px;font-weight:bold;margin:6px 0">Thank You!</div>
    <div>Visit Again!</div>
    <div style="margin-top:2px">Support: wecare.digital/selfservice</div>
</div>
</body></html>'''




# ─── Generate Invoice Image (PNG) ───

def generate_invoice_image(invoice_id: str, request_id: str) -> Dict:
    """Render invoice as POS receipt PNG using PIL, upload to S3."""
    if not invoice_id:
        return _resp(400, {'error': 'invoiceId required'})

    # Fetch invoice + items
    table = dynamodb.Table(INVOICES_TABLE)
    resp = table.get_item(Key={'invoiceId': invoice_id})
    invoice = resp.get('Item')
    if not invoice:
        return _resp(404, {'error': 'Invoice not found'})

    items_table = dynamodb.Table(INVOICE_ITEMS_TABLE)
    items_resp = items_table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key('invoiceId').eq(invoice_id)
    )
    items = sorted(items_resp.get('Items', []), key=lambda x: int(x.get('itemIndex', 0)))

    # Render to PNG using pure-Python bitmap font (zero dependencies, proven working)
    png_bytes = _generate_receipt_png(invoice, items)

    # S3 key uses WhatsApp payment reference ID (unguessable, unique)
    ref_id = invoice.get('referenceId', invoice_id)
    s3_key = f"{INVOICE_PREFIX}wecare-digital-{ref_id}.png"

    s3.put_object(
        Bucket=MEDIA_BUCKET,
        Key=s3_key,
        Body=png_bytes,
        ContentType='image/png',
        CacheControl='max-age=86400',
    )

    image_url = f"https://{CDN_DOMAIN}/{s3_key}"

    # Store asset record
    assets_table = dynamodb.Table(INVOICE_ASSETS_TABLE)
    assets_table.put_item(Item={
        'invoiceId': invoice_id,
        'assetType': 'image',
        's3Key': s3_key,
        'url': image_url,
        'contentType': 'image/png',
        'version': int(time.time()),
        'generatedAt': int(time.time()),
    })

    logger.info(json.dumps({'event': 'invoice_image_generated', 'invoiceId': invoice_id, 'url': image_url, 'requestId': request_id}))
    return _resp(200, {'invoiceId': invoice_id, 'imageUrl': image_url, 's3Key': s3_key})


# ─── Receipt PNG Rendering ───
# Uses monospace font, logo + PAID icon from S3, WD reference format.
# Compact POS thermal receipt style for WhatsApp chat visibility.


def _generate_receipt_png(invoice: Dict, items: List[Dict]) -> bytes:
    """Generate POS thermal receipt as PNG image.

    Layout: Logo left + company header, invoice meta, bill/ship to,
    items table, totals, GST summary, PAID icon, footer.
    Monospace font, 2x scaled for WhatsApp readability.
    """
    from PIL import Image, ImageDraw, ImageFont

    # ── Font setup (monospace — download DejaVu Sans Mono from S3 on Lambda) ──
    _font_cache = getattr(_generate_receipt_png, '_font_cache', {})
    _generate_receipt_png._font_cache = _font_cache

    def _get_font_bytes(bold=False):
        key = 'bold' if bold else 'regular'
        if key not in _font_cache:
            s3_key = f"stream/media/fonts/DejaVuSansMono{'-Bold' if bold else ''}.ttf"
            try:
                obj = s3.get_object(Bucket=MEDIA_BUCKET, Key=s3_key)
                _font_cache[key] = obj['Body'].read()
            except Exception as _e:
                logger.debug(f"Font S3 load failed ({s3_key}): {_e}")
                _font_cache[key] = None
        return _font_cache[key]

    def _mono(size, bold=False):
        # 1. Try S3-hosted DejaVu Sans Mono
        fb = _get_font_bytes(bold)
        if fb:
            try:
                return ImageFont.truetype(io.BytesIO(fb), size)
            except Exception as _e:
                logger.debug(f"Font truetype from S3 bytes failed: {_e}")
        # 2. Try system fonts (Windows dev)
        names = ['consolab.ttf', 'courbd.ttf'] if bold else ['consola.ttf', 'cour.ttf']
        for n in names:
            try:
                return ImageFont.truetype(n, size)
            except Exception as _e:
                logger.debug(f"System font {n} not available: {_e}")
                continue
        # 3. Pillow 10.1+ built-in default at requested size
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()

    FONT_SZ = 14
    F    = _mono(FONT_SZ)
    FB   = _mono(FONT_SZ, True)
    FLG  = _mono(FONT_SZ + 3, True)
    FSM  = _mono(FONT_SZ - 2)
    FXS  = _mono(FONT_SZ - 4)

    CHARS  = 48
    LINE_H = 18
    PX     = 14
    PY     = 10

    def _tw(draw, text, font):
        try:
            bb = draw.textbbox((0, 0), text, font=font)
            return bb[2] - bb[0]
        except Exception as _e:
            logger.debug(f"textbbox fallback: {_e}")
            return len(text) * 8

    # ── Build receipt lines ──
    # Each: (content, font, align)  align: L/C/LR/LOGO/PAID_ICON
    lines = []

    def L(t, f=F):    lines.append((t, f, 'L'))
    def C(t, f=F):    lines.append((t, f, 'C'))
    def LR(l, r, f=F): lines.append(((l, r), f, 'LR'))
    def SEP():         lines.append(('-' * CHARS, F, 'C'))
    def DSEP():        lines.append(('=' * CHARS, F, 'C'))
    def BL():          lines.append(('', F, 'L'))

    # ── Extract invoice data ──
    created_at = invoice.get('createdAt', 0)
    date_str = _ist_strftime('%d-%m-%Y', int(created_at)) if created_at else ''
    time_str = _ist_strftime('%H:%M IST', int(created_at)) if created_at else ''
    order_id = invoice.get('orderId', '')
    reference_id = invoice.get('referenceId', '')
    payment_id = invoice.get('paymentId', '')
    purpose = invoice.get('purpose', '') or ''
    # Clean up raw menu action IDs stored as purpose (e.g. "Menu_Pay")
    if purpose.lower().startswith('menu_'):
        purpose = ''
    cust_name = invoice.get('customerName', 'Customer')
    cust_phone = invoice.get('customerPhone', '')
    cust_email = invoice.get('customerEmail', '')
    bill_addr = invoice.get('billingAddress', '')
    ship_addr = invoice.get('shippingAddress', '')
    subtotal = float(invoice.get('subtotal', 0))
    discount_val = float(invoice.get('discount', 0))
    shipping_amt = float(invoice.get('shipping', 0))
    tax = float(invoice.get('tax', 0))
    gst_rate = float(invoice.get('gstRate', 0))
    conv_fee = float(invoice.get('convenienceFee', 0))
    total = float(invoice.get('total', 0))
    cgst = tax / 2
    sgst = tax / 2
    payment_status = invoice.get('paymentStatus', 'pending').upper()
    paid_at = invoice.get('paidAt', 0)

    # Extract Green Packing and Notification Fee from items (stored as charge line items)
    green_packing_amt = 0.0
    notification_fee_amt = 0.0
    for it in items:
        if it.get('isCharge'):
            nm = (it.get('name', '') or '').lower()
            amt_val = float(it.get('amount', 0)) * int(it.get('quantity', 1))
            if 'green' in nm and 'pack' in nm:
                green_packing_amt = amt_val
            elif 'notification' in nm or 'alert' in nm:
                notification_fee_amt = amt_val

    # ═══ HEADER (logo left, company info right) ═══
    lines.append(('__LOGO__', FLG, 'LOGO'))

    # ═══ INVOICE META ═══
    DSEP()
    C("Invoice", FLG)
    SEP()
    LR(f"Date: {date_str}", time_str)
    if reference_id:
        L(f"Ref: {reference_id}")
    if purpose:
        L(f"Brand: {purpose}")
    L(f"Order: {order_id or 'Offline'}")
    # ═══ PAID STATUS (text-based, real-time IST) ═══
    if payment_status == 'CAPTURED':
        if paid_at and int(paid_at) > 0:
            paid_str = _ist_strftime('%d-%m-%Y %H:%M IST', int(paid_at))
        else:
            # Fallback: use current IST time
            paid_str = _ist_strftime('%d-%m-%Y %H:%M IST', int(time.time()))
        L(f"PAID: {paid_str}", FB)
    elif payment_status not in ('PENDING', ''):
        L(f"Status: {payment_status}", FB)
    SEP()

    # ═══ BILL TO / SHIP TO ═══
    L(f"Bill To: {cust_name}", FB)
    contact_line = f"  {cust_phone}"
    if cust_email:
        contact_line += f" | {cust_email}"
    L(contact_line[:CHARS + 2], FSM)
    if bill_addr:
        for addr_line in _wrap_text(bill_addr, CHARS - 2):
            L(f"  {addr_line}", FSM)
    if ship_addr:
        L("Ship To:", FB)
        for addr_line in _wrap_text(ship_addr, CHARS - 2):
            L(f"  {addr_line}", FSM)
    SEP()

    # ═══ ITEMS TABLE ═══
    L(f"{'Sl':<3}{'Description':<22}{'Qty':>4}{'Rate':>10}{'Amount':>9}", FB)
    SEP()
    total_qty = 0
    for idx, item in enumerate(items):
        name = item.get('name', 'Item')[:20]
        amt = float(item.get('amount', 0))
        qty = int(item.get('quantity', 1))
        total_qty += qty
        line_total = amt * qty
        L(f"{idx+1:<3}{name:<22}{qty:>4}{amt:>10,.2f}{line_total:>9,.2f}")
    SEP()

    # ═══ TOTALS ═══
    LR("Subtotal", f"{subtotal:,.2f}")
    if discount_val:
        LR("Promo", f"-{discount_val:,.2f}")
    if shipping_amt:
        LR("Express", f"{shipping_amt:,.2f}")
    if green_packing_amt:
        LR("Green Packing", f"{green_packing_amt:,.2f}")
    if notification_fee_amt:
        LR("Notification Fee", f"{notification_fee_amt:,.2f}")
    if gst_rate > 0:
        LR(f"CGST @{gst_rate/2:.0f}%", f"{cgst:,.2f}")
        LR(f"SGST @{gst_rate/2:.0f}%", f"{sgst:,.2f}")
    if conv_fee:
        LR("Conv Fee", f"{conv_fee:,.2f}")
    DSEP()
    LR(f"Total  {total_qty} Items", f"\u20b9 {total:,.2f}", FB)
    DSEP()

    # ═══ GST SUMMARY ═══
    if gst_rate > 0:
        taxable = subtotal - discount_val
        LR(f"CGST @{gst_rate/2:.1f}% on {taxable:,.2f}", f"{cgst:,.2f}", FSM)
        LR(f"SGST @{gst_rate/2:.1f}% on {taxable:,.2f}", f"{sgst:,.2f}", FSM)
        LR("Total Tax", f"{tax:,.2f}", FB)
        SEP()

    SEP()
    C("Thank You! Visit Again!", FB)
    C("wecare.digital/selfservice", FSM)
    DSEP()

    # ══════════════════════════════════
    # ── RENDER TO IMAGE ──
    # ══════════════════════════════════

    # Calculate char width
    tmp_draw = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    try:
        bb = tmp_draw.textbbox((0, 0), 'M', font=F)
        CW = bb[2] - bb[0]
    except Exception as _e:
        logger.debug(f"Char width measurement fallback: {_e}")
        CW = 9

    W = CHARS * CW + PX * 2
    est_h = len(lines) * LINE_H + PY * 2 + 200  # extra for logo + paid icon
    img = Image.new('RGB', (W, est_h), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Load assets from S3
    logo_bytes = _load_logo_bytes()

    y = PY

    for content, font, align in lines:
        if align == 'LOGO':
            # Logo on left, company info to the right
            ls = 38
            if logo_bytes:
                try:
                    logo_img = Image.open(io.BytesIO(logo_bytes)).convert('RGBA')
                    logo_img = logo_img.resize((ls, ls), Image.LANCZOS)
                    img.paste(logo_img, (PX, y), logo_img)
                except Exception as _e:
                    logger.debug(f"Receipt logo paste failed: {_e}")
            hdr_lines = [
                (COMPANY['name'], FLG),
                (f"GSTIN: {COMPANY['gstin']}", FXS),
            ]
            for addr_part in _wrap_text(COMPANY['address'], 40):
                hdr_lines.append((addr_part, FXS))
            hdr_lines.append((f"{COMPANY['phone']} | {COMPANY['email']}", FXS))

            tx = PX + ls + 8
            avail = W - tx - PX
            hy = y
            for txt, hf in hdr_lines:
                tw = _tw(draw, txt, hf)
                hx = tx + (avail - tw) // 2
                draw.text((max(tx, hx), hy), txt, fill=(0, 0, 0), font=hf)
                hy += LINE_H - 2 if hf == FLG else LINE_H - 5
            y += max(ls + 2, hy - y + 2)
            continue

        if align == 'LR':
            lt, rt = content
            draw.text((PX, y), lt, fill=(0, 0, 0), font=font)
            rw = _tw(draw, rt, font)
            draw.text((W - PX - rw, y), rt, fill=(0, 0, 0), font=font)
        elif align == 'C':
            tw = _tw(draw, content, font)
            draw.text(((W - tw) // 2, y), content, fill=(0, 0, 0), font=font)
        else:
            draw.text((PX, y), content, fill=(0, 0, 0), font=font)
        y += LINE_H

    # Crop to content
    y += PY
    img = img.crop((0, 0, W, y))

    # Scale 2x for WhatsApp readability
    final_w = W * 2
    final_h = img.height * 2
    img = img.resize((final_w, final_h), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _wrap_text(text, max_chars):
    """Wrap text to max characters per line."""
    words = text.split()
    lines = []
    current = ''
    for word in words:
        if len(current) + len(word) + 1 <= max_chars:
            current = current + ' ' + word if current else word
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text[:max_chars]]


# ─── Generate Invoice PDF ───

def generate_invoice_pdf(invoice_id: str, request_id: str) -> Dict:
    """Generate invoice PDF and upload to S3."""
    if not invoice_id:
        return _resp(400, {'error': 'invoiceId required'})

    table = dynamodb.Table(INVOICES_TABLE)
    resp = table.get_item(Key={'invoiceId': invoice_id})
    invoice = resp.get('Item')
    if not invoice:
        return _resp(404, {'error': 'Invoice not found'})

    items_table = dynamodb.Table(INVOICE_ITEMS_TABLE)
    items_resp = items_table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key('invoiceId').eq(invoice_id)
    )
    items = sorted(items_resp.get('Items', []), key=lambda x: int(x.get('itemIndex', 0)))

    html = _build_invoice_html(invoice, items)

    # Primary: render receipt PNG and convert to PDF via PIL
    try:
        from PIL import Image as PILImage
        png_bytes = _generate_receipt_png(invoice, items)
        png_img = PILImage.open(io.BytesIO(png_bytes)).convert('RGB')
        pdf_buf = io.BytesIO()
        png_img.save(pdf_buf, format='PDF', resolution=150)
        pdf_bytes = pdf_buf.getvalue()
    except Exception as e:
        logger.warning(f"PIL PDF render failed: {e}, using fallback")
        try:
            pdf_bytes = _render_html_to_pdf(html)
        except Exception:
            pdf_bytes = _generate_html_pdf_fallback(html)

    ref_id = invoice.get('referenceId', invoice_id)
    s3_key = f"{INVOICE_PREFIX}wecare-digital-{ref_id}.pdf"

    s3.put_object(
        Bucket=MEDIA_BUCKET,
        Key=s3_key,
        Body=pdf_bytes,
        ContentType='application/pdf',
        CacheControl='max-age=86400',
    )

    pdf_url = f"https://{CDN_DOMAIN}/{s3_key}"

    # Store asset record
    assets_table = dynamodb.Table(INVOICE_ASSETS_TABLE)
    assets_table.put_item(Item={
        'invoiceId': invoice_id,
        'assetType': 'pdf',
        's3Key': s3_key,
        'url': pdf_url,
        'contentType': 'application/pdf',
        'version': int(time.time()),
        'generatedAt': int(time.time()),
    })

    logger.info(json.dumps({'event': 'invoice_pdf_generated', 'invoiceId': invoice_id, 'url': pdf_url, 'requestId': request_id}))
    return _resp(200, {'invoiceId': invoice_id, 'pdfUrl': pdf_url, 's3Key': s3_key})


def _render_html_to_pdf(html: str) -> bytes:
    """Render HTML to PDF. Uses PIL image-to-PDF as primary approach."""
    raise ImportError("Use image-based PDF approach")


def _generate_html_pdf_fallback(html: str) -> bytes:
    """Generate a minimal placeholder PDF. Real PDF uses image-based approach."""
    html_bytes = html.encode('utf-8')

    # Minimal PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj

2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj

3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842]
   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj

5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj

4 0 obj
<< /Length """ + str(len(b"BT /F1 14 Tf 50 780 Td (INVOICE) Tj ET BT /F1 10 Tf 50 750 Td (Please view the HTML version for full invoice details.) Tj ET BT /F1 10 Tf 50 730 Td (Download the image version for a formatted view.) Tj ET")).encode() + b""" >>
stream
BT /F1 14 Tf 50 780 Td (INVOICE) Tj ET BT /F1 10 Tf 50 750 Td (Please view the HTML version for full invoice details.) Tj ET BT /F1 10 Tf 50 730 Td (Download the image version for a formatted view.) Tj ET
endstream
endobj

xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000266 00000 n 
0000000206 00000 n 

trailer
<< /Size 6 /Root 1 0 R >>
startxref
0
%%EOF"""

    return pdf_content


# ─── Send Pending Invoices by Phone (instant pay flow) ───

def send_pending_by_phone(body: Dict, request_id: str) -> Dict:
    """Find all pending invoices for a customer phone.
    Sequential pay: sends payment link for the FIRST (oldest) invoice only.
    Returns the full list so the inbound handler can show a summary.
    After each payment is captured, _check_and_notify_balance_due auto-sends the next one.
    """
    customer_phone = body.get('customerPhone', '')
    phone_number_id = body.get('phoneNumberId', '')
    if not customer_phone:
        return _resp(400, {'error': 'customerPhone required'})

    # Normalize phone for matching
    clean = customer_phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
    last10 = clean[-10:] if len(clean) >= 10 else clean

    # Scan InvoicesTable for pending invoices matching this phone
    table = dynamodb.Table(INVOICES_TABLE)
    pending_statuses = ('created', 'pending_payment', 'sent')
    all_pending = []

    try:
        scan_kwargs = {
            'FilterExpression': (
                boto3.dynamodb.conditions.Attr('status').is_in(list(pending_statuses))
            ),
        }
        while True:
            resp = table.scan(**scan_kwargs)
            for item in resp.get('Items', []):
                inv_phone = (item.get('customerPhone', '') or '').replace(' ', '').replace('-', '')
                if inv_phone.endswith(last10):
                    all_pending.append(item)
            if 'LastEvaluatedKey' in resp:
                scan_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
            else:
                break
    except Exception as e:
        logger.error(json.dumps({'event': 'send_pending_scan_error', 'error': str(e), 'requestId': request_id}))
        return _resp(500, {'error': f'Failed to query invoices: {e}'})

    if not all_pending:
        return _resp(200, {'sent': 0, 'total': 0, 'message': 'No pending invoices', 'invoices': []})

    # Sort by createdAt ascending (oldest first)
    all_pending.sort(key=lambda x: int(x.get('createdAt', 0)))

    # Build invoice list for summary
    invoice_list = []
    for inv in all_pending:
        purpose = inv.get('purpose', '') or ''
        # Clean up raw menu action IDs stored as purpose
        if purpose.lower().startswith('menu_'):
            purpose = ''
        invoice_list.append({
            'invoiceId': inv.get('invoiceId', ''),
            'referenceId': inv.get('referenceId', ''),
            'total': float(inv.get('total', 0)),
            'purpose': purpose,
            'orderId': inv.get('orderId', ''),
            'status': 'pending',
        })

    # Send payment link for FIRST invoice only (sequential pay)
    first = all_pending[0]
    first_id = first.get('invoiceId', '')
    send_error = ''
    try:
        result = send_payment_link(first_id, phone_number_id, request_id)
        result_code = result.get('statusCode', 0)
        if result_code == 200:
            invoice_list[0]['status'] = 'sent'
        else:
            invoice_list[0]['status'] = 'failed'
            # Extract error from response body for debugging
            try:
                err_body = json.loads(result.get('body', '{}'))
                send_error = err_body.get('error', f'statusCode={result_code}')
            except Exception:
                send_error = f'statusCode={result_code}'
            logger.error(json.dumps({'event': 'send_first_link_failed', 'invoiceId': first_id, 'statusCode': result_code, 'error': send_error, 'requestId': request_id}))
    except Exception as e:
        logger.error(json.dumps({'event': 'send_first_link_error', 'invoiceId': first_id, 'error': str(e), 'requestId': request_id}))
        invoice_list[0]['status'] = 'failed'
        send_error = str(e)

    logger.info(json.dumps({'event': 'send_pending_complete', 'phone': customer_phone, 'total': len(all_pending), 'firstSent': first_id, 'sendError': send_error, 'requestId': request_id}))

    return _resp(200, {
        'sent': 1 if invoice_list[0]['status'] == 'sent' else 0,
        'total': len(invoice_list),
        'invoices': invoice_list,
        'error': send_error,
    })


# ─── Send Payment Link (WhatsApp Interactive Payment Message) ───

def send_payment_link(invoice_id: str, phone_number_id: str, payment_configuration: str, request_id: str) -> Dict:
    """Send WhatsApp interactive payment message for a pending invoice.
    Creates the order_details message with review_and_pay action.
    payment_configuration: optional PG config name (e.g. 'PayU_ManishAgarwal', 'WECARE-PAYU').
    If empty, outbound handler uses the phone's default Razorpay config.
    """
    if not invoice_id:
        return _resp(400, {'error': 'invoiceId required'})

    table = dynamodb.Table(INVOICES_TABLE)
    resp = table.get_item(Key={'invoiceId': invoice_id})
    invoice = resp.get('Item')
    if not invoice:
        return _resp(404, {'error': 'Invoice not found'})

    # Don't send payment link for already paid/cancelled invoices
    status = invoice.get('status', '')
    if status in ('paid', 'cancelled'):
        return _resp(400, {'error': f'Invoice is {status}, cannot send payment link'})

    customer_phone = invoice.get('customerPhone', '')
    if not customer_phone:
        return _resp(400, {'error': 'No customer phone on invoice'})

    # ── Phone whitelist: read from SystemConfig (id=payment_allowed_phones) ──
    # Fallback to allow-all if config not found (remove whitelist friction once testing done)
    try:
        cfg_table = dynamodb.Table(SYSTEM_CONFIG_TABLE)
        cfg_resp = cfg_table.get_item(Key={'id': 'payment_allowed_phones'})
        cfg_item = cfg_resp.get('Item')
        if cfg_item:
            import json as _json
            raw_val = cfg_item.get('configValue', '[]')
            allowed_raw = _json.loads(raw_val) if isinstance(raw_val, str) else raw_val
            # Build normalized set (strip +, spaces, dashes)
            allowed_set = set()
            for p in allowed_raw:
                clean = str(p).replace('+', '').replace(' ', '').replace('-', '')
                allowed_set.add(clean)
                allowed_set.add(f'+{clean}')
                if len(clean) > 10:
                    allowed_set.add(clean[-10:])
            clean_cust = customer_phone.replace('+', '').replace(' ', '').replace('-', '')
            if clean_cust not in allowed_set and customer_phone not in allowed_set and clean_cust[-10:] not in allowed_set:
                logger.warning(json.dumps({'event': 'payment_phone_blocked', 'phone': customer_phone, 'clean': clean_cust, 'requestId': request_id}))
                return _resp(403, {'error': f'Payment flow restricted: {customer_phone} is not in the allowed list'})
        # If no config entry exists → allow all phones (whitelist disabled)
    except Exception as wl_err:
        logger.warning(json.dumps({'event': 'whitelist_check_error', 'error': str(wl_err), 'requestId': request_id}))
        # On error, allow through (don't block payments due to config issue)

    reference_id = invoice.get('referenceId', '')
    if not reference_id:
        return _resp(400, {'error': 'No referenceId on invoice'})

    # Get invoice items
    items_table = dynamodb.Table(INVOICE_ITEMS_TABLE)
    items_resp = items_table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key('invoiceId').eq(invoice_id)
    )
    items = sorted(items_resp.get('Items', []), key=lambda x: int(x.get('itemIndex', 0)))

    # Build order items for WhatsApp interactive message (amounts in paise)
    # NOTE: Do NOT add convenience fee here — the outbound-whatsapp handler
    # auto-calculates and adds it as a line item (2% + 18% GST).
    # Green Packing & Notification Fee are pushed to the end of the items list.
    CHARGE_ITEM_NAMES = {'green packing', 'notification fee', 'notification/alert fee'}
    regular_items = []
    charge_items = []
    gst_rate = float(invoice.get('gstRate', 18))
    for item in items:
        amt_rupees = float(item.get('amount', 0))
        qty = int(item.get('quantity', 1))
        amt_paise = int(amt_rupees * 100)
        item_gst = float(item.get('gstRate', gst_rate))
        entry = {
            'name': item.get('name', 'Item'),
            'amount': {'value': amt_paise, 'offset': 100},
            'quantity': qty,
            'gstRate': item_gst,
        }
        if item.get('name', '').strip().lower() in CHARGE_ITEM_NAMES:
            charge_items.append(entry)
        else:
            regular_items.append(entry)
    # Merge: regular items first, then charge items (Green Packing, Notification Fee) last
    merged_items = regular_items + charge_items
    order_items = []
    subtotal_paise = 0
    for i, entry in enumerate(merged_items):
        entry['retailer_id'] = f'ITEM_{i+1}'
        line_paise = entry['amount']['value'] * entry['quantity']
        subtotal_paise += line_paise
        order_items.append(entry)

    discount_paise = int(float(invoice.get('discount', 0)) * 100)
    shipping_paise = int(float(invoice.get('shipping', 0)) * 100)
    # Don't pass tax here — outbound handler recalculates GST from per-item gstRate
    # Don't calculate total here — outbound handler computes it from components
    gst_paise = 0  # Let outbound handler calculate from item gstRate

    order_id = invoice.get('orderId', 'Offline')

    # Look up contact
    contact = _lookup_contact_by_phone(customer_phone)
    contact_id = (contact.get('contactId') or contact.get('id', '')) if contact else ''

    # ── Payment messages go from the SAME phone the customer is chatting with ──
    # If no phoneNumberId passed, default to Phone 1 (+919330994400)
    if not phone_number_id:
        phone_number_id = 'phone-number-id-waba3-direct-1016149501586345'

    # Build payload for outbound-whatsapp Lambda
    wa_payload = {
        'body': json.dumps({
            'contactId': contact_id,
            'recipientPhone': customer_phone,
            'phoneNumberId': phone_number_id,
            'isInteractivePayment': True,
            'orderDetails': {
                'reference_id': reference_id,
                'type': 'digital-goods',
                'payment_configuration': payment_configuration or '',
                'currency': 'INR',
                'itemName': order_items[0]['name'] if order_items else 'Payment',
                'quantity': 1,
                'gstRate': gst_rate,
                'gstin': invoice.get('gstin', COMPANY['gstin']),
                'orderId': order_id,
                'order': {
                    'status': 'pending',
                    'items': order_items,
                    'subtotal': {'value': subtotal_paise, 'offset': 100},
                    'discount': {'value': discount_paise, 'offset': 100, 'description': 'Promo'},
                    'shipping': {'value': shipping_paise, 'offset': 100, 'description': 'Express'},
                    'tax': {'value': gst_paise, 'offset': 100, 'description': f'GSTIN: {COMPANY["gstin"]}'},
                },
            }
        })
    }

    try:
        wa_response = lambda_client.invoke(
            FunctionName='wecare-outbound-whatsapp',
            InvocationType='RequestResponse',
            Payload=json.dumps(wa_payload),
        )
        wa_result = json.loads(wa_response['Payload'].read())
        wa_status_code = wa_result.get('statusCode', wa_response.get('StatusCode', 0))
        if wa_status_code >= 400:
            logger.error(json.dumps({'event': 'payment_link_outbound_error', 'invoiceId': invoice_id, 'statusCode': wa_status_code, 'body': wa_result.get('body', ''), 'requestId': request_id}))
    except Exception as e:
        logger.error(f"Payment link send error: {e}")
        return _resp(500, {'error': f'Failed to send payment link: {e}'})

    # Update invoice status to pending_payment
    try:
        table.update_item(
            Key={'invoiceId': invoice_id},
            UpdateExpression='SET #st = :st, #ua = :now',
            ExpressionAttributeNames={'#st': 'status', '#ua': 'updatedAt'},
            ExpressionAttributeValues={':st': 'pending_payment', ':now': int(time.time())},
        )
    except Exception as e:
        logger.error(f'Failed to update invoice {invoice_id} status to pending_payment: {e}')

    # NOTE: Do NOT send invoice image here — receipt with PAID stamp
    # is generated and sent AFTER payment is captured (in inbound handler).

    # Log delivery
    delivery_table = dynamodb.Table(INVOICE_DELIVERY_TABLE)
    delivery_table.put_item(Item={
        'invoiceId': invoice_id,
        'timestamp': int(time.time()),
        'channel': 'whatsapp_payment',
        'toNumber': customer_phone,
        'waMessageId': '',
        'status': 'sent' if wa_status_code in (200, 202) else 'failed',
        'imageUrl': '',
        'phoneNumberId': phone_number_id,
        'contactId': contact_id,
        'error': '',
    })

    logger.info(json.dumps({
        'event': 'payment_link_sent', 'invoiceId': invoice_id,
        'referenceId': reference_id, 'toPhone': customer_phone,
        'total': float(invoice.get('total', 0)), 'requestId': request_id,
    }))

    return _resp(200, {
        'invoiceId': invoice_id,
        'referenceId': reference_id,
        'status': 'payment_link_sent',
        'toPhone': customer_phone,
        'total': float(invoice.get('total', 0)),
    })


# ─── Cancel Invoice ───

def cancel_invoice(invoice_id: str, reason: str, request_id: str) -> Dict:
    """Cancel/void an invoice. Cannot cancel already-paid invoices."""
    if not invoice_id:
        return _resp(400, {'error': 'invoiceId required'})

    table = dynamodb.Table(INVOICES_TABLE)
    resp = table.get_item(Key={'invoiceId': invoice_id})
    invoice = resp.get('Item')
    if not invoice:
        return _resp(404, {'error': 'Invoice not found'})

    current_status = invoice.get('paymentStatus', '')
    if current_status == 'captured':
        return _resp(400, {'error': 'Cannot cancel a paid invoice. Use refund instead.'})

    try:
        # Preserve existing notes, append cancellation reason
        existing_notes = invoice.get('notes', '')
        cancel_note = f"Cancelled: {reason}" if reason else 'Cancelled by admin'
        new_notes = f"{existing_notes}\n{cancel_note}".strip() if existing_notes else cancel_note

        table.update_item(
            Key={'invoiceId': invoice_id},
            UpdateExpression='SET #st = :st, #ps = :ps, #ua = :now, #notes = :notes',
            ExpressionAttributeNames={
                '#st': 'status', '#ps': 'paymentStatus',
                '#ua': 'updatedAt', '#notes': 'notes',
            },
            ExpressionAttributeValues={
                ':st': 'cancelled',
                ':ps': 'cancelled',
                ':now': int(time.time()),
                ':notes': new_notes,
            },
        )
    except Exception as e:
        return _resp(500, {'error': str(e)})

    logger.info(json.dumps({
        'event': 'invoice_cancelled', 'invoiceId': invoice_id,
        'reason': reason, 'requestId': request_id,
    }))

    return _resp(200, {'invoiceId': invoice_id, 'status': 'cancelled'})


# ─── Delete Invoice (hard delete + sequence adjustment) ───

def delete_invoice(invoice_id: str, body: Dict, request_id: str) -> Dict:
    """Hard delete an invoice and optionally adjust the sequence counter."""
    if not invoice_id:
        return _resp(400, {'error': 'invoiceId required'})

    table = dynamodb.Table(INVOICES_TABLE)
    resp = table.get_item(Key={'invoiceId': invoice_id})
    invoice = resp.get('Item')
    if not invoice:
        return _resp(404, {'error': 'Invoice not found'})

    inv_number = invoice.get('invoiceNumber', '')
    ref_id = invoice.get('referenceId', '')

    # Delete associated S3 assets (images, PDFs)
    try:
        assets_resp = table.query(
            IndexName='invoiceId-index',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('invoiceId').eq(invoice_id),
        ) if False else {'Items': []}  # Assets are in same table as nested or separate
    except Exception as e:
        logger.warning(f'Invoice asset query failed for {invoice_id}: {e}')

    # Try to delete S3 files for this invoice
    try:
        prefix = f'stack/invoices/wecare-digital-{ref_id or invoice_id}'
        s3_resp = s3.list_objects_v2(Bucket=MEDIA_BUCKET, Prefix=prefix, MaxKeys=20)
        for obj in s3_resp.get('Contents', []):
            s3.delete_object(Bucket=MEDIA_BUCKET, Key=obj['Key'])
            logger.info(json.dumps({'event': 'invoice_s3_deleted', 'key': obj['Key']}))
    except Exception as s3_err:
        logger.warning(json.dumps({'event': 'invoice_s3_delete_error', 'error': str(s3_err)}))

    # Delete the invoice record
    try:
        table.delete_item(Key={'invoiceId': invoice_id})
    except Exception as e:
        return _resp(500, {'error': str(e)})

    # Adjust sequence counter if requested
    adjust_seq = body.get('adjustSequence', False)
    if adjust_seq and inv_number:
        try:
            # Extract FY and sequence from invoice number (format: WD/25-26/000042)
            parts = inv_number.split('/')
            if len(parts) == 3:
                fy = parts[1]
                seq_table = dynamodb.Table(INVOICES_TABLE.replace('InvoicesTable', 'SystemConfigTable'))
                seq_table.update_item(
                    Key={'id': f'invoice_seq_{fy}'},
                    UpdateExpression='SET lastSeq = lastSeq - :one',
                    ConditionExpression='lastSeq > :zero',
                    ExpressionAttributeValues={':one': 1, ':zero': 0},
                )
        except Exception as seq_err:
            logger.warning(json.dumps({'event': 'seq_adjust_error', 'error': str(seq_err)}))

    logger.info(json.dumps({
        'event': 'invoice_deleted', 'invoiceId': invoice_id,
        'invoiceNumber': inv_number, 'requestId': request_id,
    }))

    return _resp(200, {'invoiceId': invoice_id, 'deleted': True, 'invoiceNumber': inv_number})


# ─── Clear All Invoice Data (admin cleanup) ───

def clear_all_invoice_data(request_id: str) -> Dict:
    """Wipe all invoice-related tables: Invoices, InvoiceItems, InvoiceAssets, InvoiceDeliveryLog, InvoiceSequence, Payments, RazorpayWebhookLog. Also clears S3 invoices/ prefix."""
    tables_to_clear = {
        'invoices': (INVOICES_TABLE, 'invoiceId'),
        'invoice_items': (INVOICE_ITEMS_TABLE, None),
        'invoice_assets': (INVOICE_ASSETS_TABLE, None),
        'invoice_delivery_log': (INVOICE_DELIVERY_TABLE, None),
        'invoice_sequence': (INVOICE_SEQ_TABLE, None),
        'payments': (PAYMENTS_TABLE, 'id'),
        'razorpay_webhook_log': ('stack-wecare-digital-RazorpayWebhookLogTable', 'id'),
    }
    results = {}
    total = 0
    ddb_client = boto3.client('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

    for key, (table_name, known_pk) in tables_to_clear.items():
        try:
            # Discover key schema
            desc = ddb_client.describe_table(TableName=table_name)
            key_names = [k['AttributeName'] for k in desc['Table']['KeySchema']]
            table = dynamodb.Table(table_name)
            deleted = 0
            scan_kwargs = {'ProjectionExpression': ', '.join([f'#{chr(97+i)}' for i in range(len(key_names))]),
                           'ExpressionAttributeNames': {f'#{chr(97+i)}': n for i, n in enumerate(key_names)}}
            while True:
                resp = table.scan(**scan_kwargs)
                items = resp.get('Items', [])
                if not items:
                    break
                with table.batch_writer() as batch:
                    for item in items:
                        batch.delete_item(Key={k: item[k] for k in key_names})
                        deleted += 1
                if 'LastEvaluatedKey' not in resp:
                    break
                scan_kwargs['ExclusiveStartKey'] = resp['LastEvaluatedKey']
            results[key] = deleted
            total += deleted
        except Exception as e:
            logger.warning(f"Clear {key} error: {e}")
            results[key] = 0

    # Clear S3 invoices/ prefix
    s3_deleted = 0
    try:
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=MEDIA_BUCKET, Prefix='stack/invoices/'):
            objects = page.get('Contents', [])
            if objects:
                s3.delete_objects(Bucket=MEDIA_BUCKET, Delete={'Objects': [{'Key': o['Key']} for o in objects]})
                s3_deleted += len(objects)
        results['s3_invoices'] = s3_deleted
        total += s3_deleted
    except Exception as e:
        logger.warning(f"Clear S3 invoices error: {e}")
        results['s3_invoices'] = 0

    logger.info(json.dumps({'event': 'clear_all_invoice_data', 'results': results, 'total': total, 'requestId': request_id}))
    return _resp(200, {'success': True, 'results': results, 'totalDeleted': total})


# ─── Add Remark / Refund / Credit Note ───

def add_remark(invoice_id: str, body: Dict, request_id: str) -> Dict:
    """Add a remark, refund note, or credit note to an invoice."""
    if not invoice_id:
        return _resp(400, {'error': 'invoiceId required'})

    remark_type = body.get('type', 'remark')  # remark | refund | credit_note
    text = body.get('text', '')
    amount = float(body.get('amount', 0))
    author = body.get('author', 'admin')

    if not text and remark_type == 'remark':
        return _resp(400, {'error': 'text required for remarks'})

    table = dynamodb.Table(INVOICES_TABLE)
    resp = table.get_item(Key={'invoiceId': invoice_id})
    invoice = resp.get('Item')
    if not invoice:
        return _resp(404, {'error': 'Invoice not found'})

    now = int(time.time())
    remark_entry = {
        'id': str(uuid.uuid4())[:8],
        'type': remark_type,
        'text': text,
        'amount': amount,
        'author': author,
        'createdAt': now,
    }

    # Append to remarks list
    existing_remarks = invoice.get('remarks', [])
    if isinstance(existing_remarks, str):
        existing_remarks = json.loads(existing_remarks) if existing_remarks else []
    existing_remarks.append(remark_entry)

    update_expr = 'SET remarks = :r, updatedAt = :now'
    expr_values = {
        ':r': json.dumps(existing_remarks),
        ':now': now,
    }

    # For refund/credit note, also update status
    if remark_type == 'refund':
        update_expr += ', refundAmount = :ra, refundAt = :rat, paymentStatus = :ps'
        expr_values[':ra'] = _dec(amount)
        expr_values[':rat'] = now
        expr_values[':ps'] = 'refunded'
    elif remark_type == 'credit_note':
        update_expr += ', creditNoteAmount = :cna, creditNoteAt = :cnt'
        expr_values[':cna'] = _dec(amount)
        expr_values[':cnt'] = now

    try:
        table.update_item(
            Key={'invoiceId': invoice_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
        )
    except Exception as e:
        return _resp(500, {'error': str(e)})

    logger.info(json.dumps({
        'event': f'invoice_{remark_type}_added', 'invoiceId': invoice_id,
        'remarkType': remark_type, 'amount': amount, 'requestId': request_id,
    }))

    return _resp(200, {
        'invoiceId': invoice_id,
        'remark': remark_entry,
        'totalRemarks': len(existing_remarks),
    })


# ─── Send Invoice on WhatsApp ───

def send_invoice_whatsapp(invoice_id: str, to_phone: str, phone_number_id: str, request_id: str) -> Dict:
    """Send invoice image via WhatsApp. Calls outbound-whatsapp Lambda."""
    if not invoice_id:
        return _resp(400, {'error': 'invoiceId required'})
    if not to_phone:
        return _resp(400, {'error': 'toWhatsAppNumber required'})

    # Ensure image exists, generate if not
    assets_table = dynamodb.Table(INVOICE_ASSETS_TABLE)
    try:
        asset_resp = assets_table.get_item(Key={'invoiceId': invoice_id, 'assetType': 'image'})
        asset = asset_resp.get('Item')
    except Exception:
        asset = None

    if not asset or not asset.get('url'):
        # Generate image first
        gen_result = generate_invoice_image(invoice_id, request_id)
        gen_body = json.loads(gen_result.get('body', '{}'))
        if gen_result.get('statusCode') != 200:
            return _resp(500, {'error': 'Failed to generate invoice image', 'detail': gen_body})
        image_url = gen_body.get('imageUrl', '')
        s3_key = gen_body.get('s3Key', '')
    else:
        image_url = asset.get('url', '')
        s3_key = asset.get('s3Key', '')

    if not image_url:
        return _resp(500, {'error': 'No invoice image available'})

    # Fetch invoice for caption
    table = dynamodb.Table(INVOICES_TABLE)
    inv_resp = table.get_item(Key={'invoiceId': invoice_id})
    invoice = inv_resp.get('Item', {})
    total = float(invoice.get('total', 0))
    order_id = invoice.get('orderId', '')
    reference_id = invoice.get('referenceId', '')
    order_line = f"\nOrder: {order_id}" if order_id and order_id != 'Offline' else ''
    ref_line = f"\nRef: {reference_id}" if reference_id else ''
    caption = f"Invoice \u20b9{total:,.2f}{order_line}{ref_line}\nThank you for your payment!"

    # Look up contact by phone
    contact = _lookup_contact_by_phone(to_phone)
    contact_id = (contact.get('contactId') or contact.get('id', '')) if contact else ''

    # Default phone number ID
    if not phone_number_id:
        phone_number_id = 'phone-number-id-waba3-direct-1016149501586345'

    # Call outbound-whatsapp Lambda to send image
    wa_payload = {
        'body': json.dumps({
            'contactId': contact_id,
            'recipientPhone': to_phone,
            'content': caption,
            'phoneNumberId': phone_number_id,
            'mediaFile': s3_key,
            'mediaType': 'image',
        })
    }

    try:
        wa_response = lambda_client.invoke(
            FunctionName='wecare-outbound-whatsapp',
            InvocationType='RequestResponse',
            Payload=json.dumps(wa_payload),
        )
        wa_result = json.loads(wa_response['Payload'].read())
        wa_body = json.loads(wa_result.get('body', '{}'))
        wa_message_id = wa_body.get('whatsappMessageId', wa_body.get('messageId', ''))
        wa_status = wa_body.get('status', 'unknown')
    except Exception as e:
        logger.error(f"WhatsApp send error: {e}")
        wa_message_id = ''
        wa_status = 'failed'

    # Log delivery
    delivery_table = dynamodb.Table(INVOICE_DELIVERY_TABLE)
    delivery_table.put_item(Item={
        'invoiceId': invoice_id,
        'timestamp': int(time.time()),
        'channel': 'whatsapp',
        'toNumber': to_phone,
        'waMessageId': wa_message_id,
        'status': wa_status,
        'imageUrl': image_url,
        'phoneNumberId': phone_number_id,
        'contactId': contact_id,
        'error': '' if wa_status != 'failed' else 'WhatsApp send failed',
    })

    # Update invoice status
    if wa_status in ('sent', 'delivered'):
        table.update_item(
            Key={'invoiceId': invoice_id},
            UpdateExpression='SET #st = :st, #ua = :now',
            ExpressionAttributeNames={'#st': 'status', '#ua': 'updatedAt'},
            ExpressionAttributeValues={':st': 'sent', ':now': int(time.time())},
        )

    logger.info(json.dumps({
        'event': 'invoice_whatsapp_sent', 'invoiceId': invoice_id,
        'waMessageId': wa_message_id, 'status': wa_status,
        'toNumber': to_phone, 'requestId': request_id,
    }))

    return _resp(200, {
        'invoiceId': invoice_id,
        'waMessageId': wa_message_id,
        'status': wa_status,
        'imageUrl': image_url,
    })


# ─── Delivery Log ───

def get_delivery_log(invoice_id: str, request_id: str) -> Dict:
    """Get delivery log for an invoice."""
    if not invoice_id:
        return _resp(400, {'error': 'invoiceId required'})

    table = dynamodb.Table(INVOICE_DELIVERY_TABLE)
    resp = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key('invoiceId').eq(invoice_id)
    )
    logs = resp.get('Items', [])
    logs.sort(key=lambda x: int(x.get('timestamp', 0)), reverse=True)

    return _resp(200, {
        'invoiceId': invoice_id,
        'deliveryLogs': [{
            'timestamp': int(l.get('timestamp', 0)),
            'channel': l.get('channel', ''),
            'toNumber': l.get('toNumber', ''),
            'waMessageId': l.get('waMessageId', ''),
            'status': l.get('status', ''),
            'error': l.get('error', ''),
            'imageUrl': l.get('imageUrl', ''),
        } for l in logs],
        'count': len(logs),
    })


# ─── Helper Functions ───

def _lookup_contact_by_phone(phone: str) -> Optional[Dict]:
    """Look up a contact by phone number."""
    if not phone:
        return None
    try:
        table = dynamodb.Table(CONTACTS_TABLE)
        # Normalize phone
        clean = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        if not clean.startswith('+'):
            clean = '+' + clean

        result = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('phone').contains(clean[-10:]),
        )
        items = result.get('Items', [])
        return items[0] if items else None
    except Exception as e:
        logger.warning(f"Contact lookup error: {e}")
        return None


def _normalize_invoice(item: Dict) -> Dict:
    """Normalize invoice record for API response."""
    return {
        'invoiceId': item.get('invoiceId', ''),
        'invoiceNumber': item.get('invoiceNumber', ''),
        'paymentId': item.get('paymentId', ''),
        'orderId': item.get('orderId', ''),
        'referenceId': item.get('referenceId', ''),
        'entryPoint': item.get('entryPoint', ''),
        'status': item.get('status', ''),
        'paymentStatus': item.get('paymentStatus', ''),
        'contactId': item.get('contactId', ''),
        'customerName': item.get('customerName', ''),
        'customerPhone': item.get('customerPhone', ''),
        'paidByPhone': item.get('paidByPhone', ''),
        'customerEmail': item.get('customerEmail', ''),
        'shippingAddress': item.get('shippingAddress', ''),
        'billingAddress': item.get('billingAddress', ''),
        'subtotal': float(item.get('subtotal', 0)),
        'discount': float(item.get('discount', 0)),
        'shipping': float(item.get('shipping', 0)),
        'handling': float(item.get('handling', 0)),
        'gstRate': float(item.get('gstRate', 0)),
        'tax': float(item.get('tax', 0)),
        'convenienceFee': float(item.get('convenienceFee', 0)),
        'total': float(item.get('total', 0)),
        'currency': item.get('currency', 'INR'),
        'gstin': item.get('gstin', ''),
        'purpose': item.get('purpose', ''),
        'notes': item.get('notes', ''),
        'createdAt': int(item.get('createdAt', 0)),
        'updatedAt': int(item.get('updatedAt', 0)),
        'paidAt': int(item.get('paidAt', 0)),
    }


def _normalize_item(item: Dict) -> Dict:
    """Normalize invoice item for API response."""
    return {
        'invoiceId': item.get('invoiceId', ''),
        'itemIndex': int(item.get('itemIndex', 0)),
        'name': item.get('name', ''),
        'amount': float(item.get('amount', 0)),
        'quantity': int(item.get('quantity', 1)),
        'productId': item.get('productId', ''),
    }


def _normalize_asset(item: Dict) -> Dict:
    """Normalize invoice asset for API response."""
    return {
        'invoiceId': item.get('invoiceId', ''),
        'assetType': item.get('assetType', ''),
        's3Key': item.get('s3Key', ''),
        'url': item.get('url', ''),
        'contentType': item.get('contentType', ''),
        'version': int(item.get('version', 0)),
        'generatedAt': int(item.get('generatedAt', 0)),
    }


def _dec(value) -> Decimal:
    """Convert to Decimal for DynamoDB storage."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(round(float(value), 2)))


def _resp(status_code: int, body: Dict) -> Dict[str, Any]:
    """Return HTTP response with CORS headers."""
    return {
        'statusCode': status_code,
        'headers': cors_headers(origin),
        'body': json.dumps(body, default=str),
    }
