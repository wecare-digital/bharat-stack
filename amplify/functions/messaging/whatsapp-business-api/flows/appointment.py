"""
Appointment Flow — Book consultations and service visits.
Screens: BOOKING_FORM → REVIEW → CONFIRM (terminal)
Saves to AppointmentsTable + FlowSubmissionTable.
"""
import json
import time
import uuid
import logging
from decimal import Decimal
from typing import Dict

from flows.common import (
    dynamodb, get_phone_from_token, find_contact_by_phone,
    get_contact_name, record_completion,
)

logger = logging.getLogger(__name__)

APPOINTMENTS_TABLE = 'stack-wecare-digital-AppointmentTable'
FLOW_CODE = 'WD_APPT'


def handle_init(data: Dict, flow_token: str, request_id: str) -> Dict:
    """INIT → show BOOKING_FORM with type/location options."""
    return {
        'screen': 'BOOKING_FORM',
        'data': {
            'appointment_types': [
                {'id': 'consultation', 'title': 'Consultation'},
                {'id': 'service_visit', 'title': 'Service Visit'},
                {'id': 'follow_up', 'title': 'Follow-up'},
                {'id': 'other', 'title': 'Other'},
            ],
            'locations': [
                {'id': 'office', 'title': 'Office'},
                {'id': 'virtual', 'title': 'Virtual (Online)'},
                {'id': 'home_visit', 'title': 'Home Visit'},
            ],
        }
    }


def handle_booking_form(data: Dict, flow_token: str, request_id: str) -> Dict:
    """BOOKING_FORM → REVIEW with collected data."""
    return {
        'screen': 'REVIEW',
        'data': {
            'appointment_type': data.get('appointment_type', ''),
            'location': data.get('location', ''),
            'slot_date': data.get('slot_date', ''),
            'slot_time': data.get('slot_time', ''),
            'notes': data.get('notes', '') or '—',
        }
    }


def handle_review(data: Dict, flow_token: str, request_id: str) -> Dict:
    """REVIEW → save appointment, return CONFIRM."""
    phone = get_phone_from_token(flow_token)
    contact_id = find_contact_by_phone(phone)
    name = get_contact_name(contact_id)
    # Derived from the completion key rather than random. A Meta retry of
    # this data_exchange recomputes the same id, so the domain write below
    # overwrites an identical row instead of creating a second one, and the
    # conditional put inside record_completion refuses the duplicate.
    from lambda_utils import flow_completion as _fc
    apt_id = _fc.reference_for(
        _fc.completion_key(flow_token, 'REVIEW', data)[0], 'WD-APT')
    now = int(time.time())

    # Save to AppointmentsTable
    try:
        table = dynamodb.Table(APPOINTMENTS_TABLE)
        table.put_item(Item={k: v for k, v in {
            'appointmentId': apt_id,
            'customerPhone': phone,
            'customerName': name,
            'contactId': contact_id,
            'appointmentType': data.get('appointment_type', ''),
            'location': data.get('location', ''),
            'slotDate': data.get('slot_date', ''),
            'slotTime': data.get('slot_time', ''),
            'notes': data.get('notes', ''),
            'status': 'booked',
            'createdAt': Decimal(str(now)),
            'updatedAt': Decimal(str(now)),
        }.items() if v is not None and v != ''})
    except Exception as e:
        logger.warning(f'Appointment save failed: {e}')

    # Save to FlowSubmissionTable
    try:
        result = record_completion(
            flow_code=FLOW_CODE, flow_type='booking', phone=phone,
            contact_id=contact_id, sender_name=name,
            form_data=data, flow_token=flow_token, request_id=request_id,
            screen='REVIEW', submission_number=apt_id, requires_payment=False, status='booked',
        )
    except Exception as e:
        logger.warning(f'Appointment submission save failed: {e}')

    # Send WhatsApp confirmation
    # Only a fresh claim may message the customer. Without this guard a Meta
    # retry of the same completion sent a second confirmation for one submission.
    if result.should_fire_side_effects:
        try:
            from flows.common import send_simple_confirmation
            send_simple_confirmation(phone, flow_token, 'Appointment Booking', apt_id,
                f'*Type:* {data.get("appointment_type", "")}\n*Date:* {data.get("slot_date", "")} at {data.get("slot_time", "")}')
        except Exception:
            pass

    return {
        'screen': 'CONFIRM',
        'data': {
            'appointment_id': apt_id,
            'message': f'Your {data.get("appointment_type", "appointment")} on {data.get("slot_date", "")} at {data.get("slot_time", "")} has been booked. We will confirm shortly.',
        }
    }
