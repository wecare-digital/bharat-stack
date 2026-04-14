"""
Order Notes Flow — Add special instructions or notes to an order.
Screens: ORDER_SELECT → NOTES_FORM → CONFIRM (terminal)
Saves notes to OrdersTable (adminNotes) + FlowSubmissionTable.
"""
import json, time, uuid, logging
from decimal import Decimal
from typing import Dict
from flows.orders import (
    fetch_orders_for_flow, get_order, extract_short_id,
    dynamodb, ORDERS_TABLE,
)
from flows.common import (
    get_phone_from_token, find_contact_by_phone,
    get_contact_name, save_flow_submission,
)

logger = logging.getLogger(__name__)
FLOW_CODE = 'WD_NOTE'


def handle_init(data: Dict, flow_token: str, request_id: str) -> Dict:
    phone = get_phone_from_token(flow_token)
    orders = fetch_orders_for_flow(phone, data.get('email', ''))
    if not orders:
        orders = [{'id': 'none', 'title': 'No orders found'}]
    return {'screen': 'ORDER_SELECT', 'data': {'orders': orders}}


def handle_order_select(data: Dict, flow_token: str, request_id: str) -> Dict:
    order_id = data.get('order_id', '')
    short = extract_short_id(order_id) if order_id and order_id != 'none' else '—'
    return {
        'screen': 'NOTES_FORM',
        'data': {
            'order_id': order_id,
            'order_label': short,
        }
    }


def handle_notes_form(data: Dict, flow_token: str, request_id: str) -> Dict:
    phone = get_phone_from_token(flow_token)
    contact_id = find_contact_by_phone(phone)
    name = get_contact_name(contact_id)
    note_id = f'WD-NOTE-{uuid.uuid4().hex[:8].upper()}'
    now = int(time.time())
    order_id = data.get('order_id', '')
    notes = data.get('notes', '')

    # Append notes to OrdersTable.adminNotes
    if order_id and order_id != 'none':
        try:
            table = dynamodb.Table(ORDERS_TABLE)
            order = get_order(order_id)
            old_notes = order.get('adminNotes', '') or ''
            ts = time.strftime('%d %b %Y %H:%M', time.gmtime(now + 19800))
            new_notes = f'{old_notes}\n[{ts} by {name or phone}] {notes}'.strip()
            table.update_item(
                Key={'orderId': order_id},
                UpdateExpression='SET adminNotes = :n, updatedAt = :u',
                ExpressionAttributeValues={
                    ':n': new_notes[:2000],
                    ':u': Decimal(str(now)),
                },
            )
        except Exception as e:
            logger.warning(f'Order notes update failed: {e}')

    # Save to FlowSubmissionTable
    try:
        save_flow_submission(
            flow_code=FLOW_CODE, flow_type='order_notes', phone=phone,
            contact_id=contact_id, sender_name=name,
            form_data={'order_id': order_id, 'notes': notes},
            flow_token=flow_token, request_id=request_id,
            submission_number=note_id, requires_payment=False, status='completed',
        )
    except Exception as e:
        logger.warning(f'Order notes submission save failed: {e}')

    try:
        from flows.common import send_simple_confirmation
        send_simple_confirmation(phone, flow_token, 'Order Notes Saved', note_id)
    except Exception:
        pass

    return {
        'screen': 'CONFIRM',
        'data': {
            'note_id': note_id,
            'message': 'Your notes have been saved to the order. Our team will see them when processing your order.',
        }
    }
