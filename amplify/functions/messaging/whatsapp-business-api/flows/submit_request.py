"""
Submit Request Flow — PAID (amount from FlowRegistry).
Collects: order, request type, subject, description.
Saves submission, creates invoice, sends payment link + confirmation.
"""
import json
import uuid
import logging
from typing import Dict

from flows.common import (
    lambda_client, PHONE1_ID,
    get_phone_from_token, get_phone_number_id_for_flow,
    find_contact_by_phone, get_contact_name,
    save_flow_submission, send_payment, send_confirmation,
)

logger = logging.getLogger(__name__)

# ── Flow config (defaults — overridden by FlowRegistry at runtime) ──
FLOW_CODE = '01.WD_SR'
FLOW_NAME = 'Submit Request'
SUBMISSION_PREFIX = 'WD-SR'
# Payment config comes from FlowRegistry — these are just safe defaults
DEFAULT_REQUIRES_PAYMENT = False
DEFAULT_PAYMENT_AMOUNT = 0


def handle_init(data: Dict, flow_token: str, request_id: str,
                fetch_orders_fn=None) -> Dict:
    """INIT → fetch orders, navigate to ORDER_SELECT."""
    from flows.orders import fetch_orders_for_flow
    phone = get_phone_from_token(flow_token)
    email = data.get('email', '')
    orders = []
    try:
        orders = fetch_orders_for_flow(phone, email)
    except Exception as e:
        logger.warning(f'Order fetch failed: {e}')
    if not orders:
        orders = [{'id': 'none', 'title': 'No orders found'}]
    return {'screen': 'ORDER_SELECT', 'data': {'orders': orders}}


def handle_order_select(data: Dict, flow_token: str, request_id: str) -> Dict:
    """ORDER_SELECT → show SUBMIT_REQUEST_FORM with order context."""
    return {
        'screen': 'SUBMIT_REQUEST_FORM',
        'data': {
            'order_id': data.get('order_id', ''),
        }
    }


def handle_request_form(data: Dict, flow_token: str, request_id: str) -> Dict:
    """SUBMIT_REQUEST_FORM → show TERMS with collected form data.
    Passes order_id, subject, description forward to TERMS screen.
    """
    return {
        'screen': 'TERMS',
        'data': {
            'order_id': data.get('order_id', ''),
            'subject': data.get('subject', ''),
            'description': data.get('description', ''),
        }
    }


def handle_review(data: Dict, flow_token: str, request_id: str,
                  flow_config: Dict = None) -> Dict:
    """REVIEW screen → save, pay (if required), confirm, return SUCCESS.
    response_payload is set FIRST, saves happen after.
    Payment config comes from flow_config (FlowRegistry).
    """
    phone = get_phone_from_token(flow_token)
    phone_number_id = get_phone_number_id_for_flow(flow_token)

    order_id = data.get('order_id', '')
    subject = data.get('subject', '')
    description = data.get('description', '')
    request_type = data.get('request_type', '')

    # Payment config from FlowRegistry — NOT hardcoded
    # Fallback: if FlowRegistry has no config, check client-side payload flags
    cfg = flow_config or {}
    requires_payment = bool(cfg.get('requiresPayment', DEFAULT_REQUIRES_PAYMENT))
    payment_amount = int(cfg.get('paymentAmount', DEFAULT_PAYMENT_AMOUNT)) if requires_payment else 0

    # Client-side fallback: REVIEW screen sends payment_required + service_fee_amount
    # This ensures payment works even if FlowRegistry is not yet seeded
    if not requires_payment and data.get('payment_required') == 'true':
        requires_payment = True
        try:
            client_fee = int(data.get('service_fee_amount', '0'))
            payment_amount = client_fee * 100 if client_fee > 0 else 0  # convert rupees to paise
        except (ValueError, TypeError):
            payment_amount = 0

    flow_name = cfg.get('flowName', FLOW_NAME)
    prefix = cfg.get('submissionPrefix', SUBMISSION_PREFIX)

    request_number = f'{prefix}-{uuid.uuid4().hex[:8].upper()}'
    payment_ref_id = f'WD-PAY-{uuid.uuid4().hex[:8].upper()}' if requires_payment else ''

    logger.info(json.dumps({
        'event': 'sr_review_submit', 'order_id': order_id, 'subject': subject,
        'requiresPayment': requires_payment, 'paymentAmount': payment_amount,
        'phoneNumberId': phone_number_id, 'requestId': request_id,
    }))

    # ── SET SUCCESS RESPONSE FIRST ──
    # v3 flow: return THANK_YOU screen with order_id, request_number, payment_ref_id
    response_payload = {
        'screen': 'THANK_YOU',
        'data': {
            'order_id': order_id,
            'request_number': request_number,
            'payment_ref_id': payment_ref_id or 'N/A',
        }
    }

    # ── Saves (non-blocking) ──
    contact_id = find_contact_by_phone(phone)
    sender_name = get_contact_name(contact_id)

    try:
        save_flow_submission(
            flow_code=cfg.get('flowCode', FLOW_CODE), flow_type='form_submit',
            phone=phone, contact_id=contact_id, sender_name=sender_name,
            form_data={'order_id': order_id, 'subject': subject,
                       'description': description, 'request_type': request_type},
            flow_token=flow_token, request_id=request_id,
            submission_number=request_number,
            requires_payment=requires_payment, payment_amount=payment_amount,
            payment_ref_id=payment_ref_id,
        )
    except Exception as e:
        logger.error(f'SR submission save failed: {e}')

    # ── Payment + confirmation (async) ──
    try:
        _gw = cfg.get('preferredGateway', '')
        _pg = cfg.get('paymentConfigName', '')
        lambda_client.invoke(
            FunctionName=lambda_client._endpoint.host.split('/')[-1] if hasattr(lambda_client, '_endpoint') else 'wecare-whatsapp-business-api',
            InvocationType='Event',
            Payload=json.dumps({
                '_async_action': 'flow_post_submit',
                'phone': phone, 'phone_number_id': phone_number_id,
                'order_id': order_id, 'subject': subject,
                'request_id': request_id, 'request_number': request_number,
                'payment_ref_id': payment_ref_id,
                'requires_payment': requires_payment,
                'payment_amount': payment_amount,
                'flow_name': flow_name,
                'flow_code': cfg.get('flowCode', FLOW_CODE),
                'preferred_gateway': _gw, 'payment_config_name': _pg,
            })
        )
    except Exception as e:
        logger.error(f'Async post-submit invoke failed: {e}')
        # Fallback: sync
        try:
            invoice_number = ''
            if requires_payment and payment_amount:
                invoice_number = send_payment(
                    phone=phone, phone_number_id=phone_number_id,
                    order_id=order_id, subject=subject, request_id=request_id,
                    request_number=request_number, payment_ref_id=payment_ref_id,
                    payment_amount_paise=payment_amount, flow_name=flow_name,
                    preferred_gateway=_gw, payment_config_name=_pg,
                )
            send_confirmation(
                phone=phone, phone_number_id=phone_number_id, request_id=request_id,
                flow_name=flow_name, request_number=request_number,
                requires_payment=requires_payment, payment_amount=payment_amount,
                payment_ref_id=payment_ref_id, invoice_number=invoice_number,
                order_id=order_id, subject=subject,
            )
        except Exception as e2:
            logger.error(f'Sync fallback failed: {e2}')

    return response_payload
