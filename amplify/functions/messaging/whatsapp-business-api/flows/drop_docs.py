"""
Drop Docs Flow — Document management for customer-uploaded documents.
Screens: DOC_FORM → REVIEW → CONFIRM (terminal)

How it works:
1. Customer fills the flow form (doc type, order link, description)
2. System creates a Document record with status='uploaded' and sourceType='flow'
3. Customer sends the actual file as a WhatsApp message after the flow
4. Inbound handler detects the pending doc ref and links the media to the Document record
5. Admin reviews, approves/rejects from the dashboard

Saves to DocumentTable + FlowSubmissionTable.
"""
import json
import time
import uuid
import logging
from decimal import Decimal
from typing import Dict

from flows.orders import fetch_orders_for_flow, extract_short_id
from flows.common import (
    dynamodb, get_phone_from_token, find_contact_by_phone,
    get_contact_name, save_flow_submission,
)

logger = logging.getLogger(__name__)

DOCUMENTS_TABLE = 'stack-wecare-digital-DocumentTable'
FLOW_CODE = 'WD_DOCS'


def handle_init(data: Dict, flow_token: str, request_id: str) -> Dict:
    """INIT → show DOC_FORM with doc types and order list."""
    phone = get_phone_from_token(flow_token)
    orders = fetch_orders_for_flow(phone, data.get('email', ''))
    # Add "not linked" option at the top
    order_options = [{'id': 'none', 'title': 'Not linked to an order'}]
    order_options.extend(orders)

    return {
        'screen': 'DOC_FORM',
        'data': {
            'doc_types': [
                {'id': 'id_proof', 'title': 'ID Proof (Aadhaar, PAN, Passport)'},
                {'id': 'address_proof', 'title': 'Address Proof'},
                {'id': 'prescription', 'title': 'Prescription'},
                {'id': 'invoice', 'title': 'Invoice / Receipt'},
                {'id': 'photo', 'title': 'Photo / Screenshot'},
                {'id': 'other', 'title': 'Other Document'},
            ],
            'orders': order_options,
        }
    }


def handle_doc_form(data: Dict, flow_token: str, request_id: str) -> Dict:
    """DOC_FORM → REVIEW with collected data."""
    order_id = data.get('order_id', 'none')
    order_display = 'None'
    if order_id and order_id != 'none':
        short = extract_short_id(order_id)
        order_display = short if short else order_id[:20]

    return {
        'screen': 'REVIEW',
        'data': {
            'doc_type': data.get('doc_type', ''),
            'order_id': order_id,
            'description': data.get('description', '') or '—',
        }
    }


def handle_review(data: Dict, flow_token: str, request_id: str) -> Dict:
    """REVIEW → save document record, return CONFIRM."""
    phone = get_phone_from_token(flow_token)
    contact_id = find_contact_by_phone(phone)
    name = get_contact_name(contact_id)
    doc_id = f'WD-DOC-{uuid.uuid4().hex[:8].upper()}'
    now = int(time.time())
    order_id = data.get('order_id', '')
    if order_id == 'none':
        order_id = ''

    # Save to DocumentTable — awaiting actual file upload
    try:
        table = dynamodb.Table(DOCUMENTS_TABLE)
        table.put_item(Item={k: v for k, v in {
            'documentId': doc_id,
            'customerPhone': phone,
            'customerName': name,
            'contactId': contact_id,
            'orderId': order_id,
            'sourceType': 'flow',
            'documentType': data.get('doc_type', 'other'),
            'verificationStatus': 'uploaded',
            'remarks': data.get('description', ''),
            'uploadedAt': Decimal(str(now)),
            'createdAt': Decimal(str(now)),
            'updatedAt': Decimal(str(now)),
        }.items() if v is not None and v != ''})
    except Exception as e:
        logger.warning(f'Document record save failed: {e}')

    # Save to FlowSubmissionTable
    try:
        save_flow_submission(
            flow_code=FLOW_CODE, flow_type='document', phone=phone,
            contact_id=contact_id, sender_name=name,
            form_data={**data, 'doc_id': doc_id},
            flow_token=flow_token, request_id=request_id,
            submission_number=doc_id, requires_payment=False, status='awaiting_upload',
        )
    except Exception as e:
        logger.warning(f'Document submission save failed: {e}')

    return {
        'screen': 'CONFIRM',
        'data': {
            'doc_id': doc_id,
            'message': f'Your {data.get("doc_type", "document")} request has been registered. Please send the document as a WhatsApp message now.',
        }
    }
