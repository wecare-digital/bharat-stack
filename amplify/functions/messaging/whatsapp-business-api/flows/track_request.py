"""
Track Request Flow — ORDER-CENTRIC status lookup.
Shows all activity (requests, payments, statuses) against an order.
Screens: ORDER_SELECT → STATUS (terminal)
"""
import json
import logging
from typing import Dict

from flows.orders import (
    fetch_orders_for_flow, get_order, get_submissions_for_order,
    extract_short_id, format_order_dropdown,
)
from flows.common import get_phone_from_token, save_draft, restore_draft

logger = logging.getLogger(__name__)

FLOW_CODE = '02.WD_TR'


def handle_init(data: Dict, flow_token: str, request_id: str) -> Dict:
    """INIT → fetch orders, navigate to ORDER_SELECT."""
    phone = get_phone_from_token(flow_token)
    email = data.get('email', '')
    orders = fetch_orders_for_flow(phone, email)
    if not orders:
        orders = [{'id': 'none', 'title': 'No orders found'}]
    return {'screen': 'ORDER_SELECT', 'data': {'orders': orders}}


def handle_order_select(data: Dict, flow_token: str, request_id: str) -> Dict:
    """ORDER_SELECT → look up order + all submissions → return STATUS screen data."""
    order_id = data.get('order_id', '')
    if not order_id or order_id == 'none':
        return {
            'screen': 'STATUS',
            'data': _empty_status('No order selected'),
        }

    # Fetch order details from OrdersTable
    order = get_order(order_id)
    short = extract_short_id(order_id)

    # Order details
    if order:
        order_line = f'{short} — {order.get("orderDateIST", "")}'
        items_text = order.get('itemsSummary', '') or 'No items'
        total = order.get('totalAmount', 0)
        total_text = f'₹{float(total):.0f}' if total else '—'
        order_status = (order.get('orderStatus', '') or 'active').replace('_', ' ').title()
        payment_status = (order.get('paymentStatus', '') or 'pending').replace('_', ' ').title()
        fulfillment = (order.get('fulfillmentStatus', '') or '').replace('_', ' ').title()
    else:
        # Order not in OrdersTable — show basic info from the ID
        order_line = short or order_id[:20]
        items_text = '—'
        total_text = '—'
        order_status = '—'
        payment_status = '—'
        fulfillment = ''

    # Fetch all submissions (service requests) for this order
    submissions = get_submissions_for_order(order_id)

    # Build requests summary text
    if submissions:
        req_lines = []
        for sub in submissions[:5]:  # max 5 to fit screen
            sub_num = sub.get('submissionNumber', sub.get('submissionId', ''))[:16]
            subject = sub.get('subject', sub.get('requestType', ''))[:25]
            status = (sub.get('status', 'open') or 'open').replace('_', ' ').title()
            pay = sub.get('paymentStatus', 'none')
            pay_icon = '✓' if pay == 'captured' else '⏳' if pay == 'pending' else ''
            line = f'{sub_num} — {subject} — {status}'
            if pay_icon:
                line += f' {pay_icon}'
            req_lines.append(line)
        requests_text = '\n'.join(req_lines)
        requests_count = f'{len(submissions)} request(s)'
    else:
        requests_text = 'No service requests for this order.'
        requests_count = '0 requests'

    # Build status line
    status_parts = [order_status]
    if fulfillment:
        status_parts.append(fulfillment)
    status_line = ' · '.join(status_parts)

    return {
        'screen': 'STATUS',
        'data': {
            'order_ref': order_line,
            'order_status': status_line,
            'payment_info': f'{payment_status} — {total_text}',
            'items_info': items_text[:80],
            'requests_summary': requests_text[:500],
            'requests_count': requests_count,
        }
    }


def _empty_status(msg: str) -> Dict:
    return {
        'order_ref': '—',
        'order_status': msg,
        'payment_info': '—',
        'items_info': '—',
        'requests_summary': msg,
        'requests_count': '0 requests',
    }
