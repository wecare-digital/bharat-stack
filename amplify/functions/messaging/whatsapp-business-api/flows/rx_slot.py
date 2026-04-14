"""
RX Slot Flow — Prescription, lab test, and medical visit booking.
Screens: SLOT_FORM → REVIEW → CONFIRM (terminal)
Saves to RxSlotTable + FlowSubmissionTable.
"""
import json
import time
import uuid
import logging
from decimal import Decimal
from typing import Dict

from flows.common import (
    dynamodb, get_phone_from_token, find_contact_by_phone,
    get_contact_name, save_flow_submission,
)

logger = logging.getLogger(__name__)

RX_SLOT_TABLE = 'stack-wecare-digital-RxSlotTable'
FLOW_CODE = 'WD_RX'


def handle_init(data: Dict, flow_token: str, request_id: str) -> Dict:
    """INIT → show SLOT_FORM with slot type options."""
    return {
        'screen': 'SLOT_FORM',
        'data': {
            'slot_types': [
                {'id': 'prescription', 'title': 'Prescription Pickup'},
                {'id': 'medical_tourism', 'title': 'Medical Tourism'},
                {'id': 'lab_test', 'title': 'Lab Test'},
                {'id': 'pharmacy', 'title': 'Pharmacy Visit'},
            ],
        }
    }


def handle_slot_form(data: Dict, flow_token: str, request_id: str) -> Dict:
    """SLOT_FORM → REVIEW with collected data."""
    return {
        'screen': 'REVIEW',
        'data': {
            'slot_type': data.get('slot_type', ''),
            'slot_date': data.get('slot_date', ''),
            'slot_time': data.get('slot_time', ''),
            'facility_name': data.get('facility_name', '') or '—',
            'prescription_notes': data.get('prescription_notes', '') or '—',
        }
    }


def handle_review(data: Dict, flow_token: str, request_id: str) -> Dict:
    """REVIEW → save RX slot, return CONFIRM."""
    phone = get_phone_from_token(flow_token)
    contact_id = find_contact_by_phone(phone)
    name = get_contact_name(contact_id)
    rx_id = f'WD-RX-{uuid.uuid4().hex[:8].upper()}'
    now = int(time.time())

    # Save to RxSlotTable
    try:
        table = dynamodb.Table(RX_SLOT_TABLE)
        table.put_item(Item={k: v for k, v in {
            'rxSlotId': rx_id,
            'customerPhone': phone,
            'customerName': name,
            'contactId': contact_id,
            'slotType': data.get('slot_type', ''),
            'slotDate': data.get('slot_date', ''),
            'slotTime': data.get('slot_time', ''),
            'facilityName': data.get('facility_name', ''),
            'prescriptionNotes': data.get('prescription_notes', ''),
            'status': 'booked',
            'createdAt': Decimal(str(now)),
            'updatedAt': Decimal(str(now)),
        }.items() if v is not None and v != ''})
    except Exception as e:
        logger.warning(f'RX slot save failed: {e}')

    # Save to FlowSubmissionTable
    try:
        save_flow_submission(
            flow_code=FLOW_CODE, flow_type='rx_booking', phone=phone,
            contact_id=contact_id, sender_name=name,
            form_data=data, flow_token=flow_token, request_id=request_id,
            submission_number=rx_id, requires_payment=False, status='booked',
        )
    except Exception as e:
        logger.warning(f'RX slot submission save failed: {e}')

    return {
        'screen': 'CONFIRM',
        'data': {
            'rx_slot_id': rx_id,
            'message': f'Your {data.get("slot_type", "RX slot")} on {data.get("slot_date", "")} at {data.get("slot_time", "")} has been booked. We will confirm shortly.',
        }
    }
