"""
Subscribe Flow — FREE, no payment.
Collects: name, phone, email, company, addresses.
Creates/updates contact, saves subscription, sends welcome message.
"""
import json
import time
import uuid
import logging
from decimal import Decimal
from typing import Dict

from flows.common import (
    dynamodb, lambda_client, CONTACTS_TABLE, FLOW_SUBMISSIONS_TABLE,
    OUTBOUND_WHATSAPP_FUNCTION, PHONE1_ID,
    get_phone_from_token, get_phone_number_id_for_flow,
    find_contact_by_phone, save_flow_submission,
)

logger = logging.getLogger(__name__)

# ── Flow config ──
FLOW_CODE = 'WD_SUBSCRIBE'
FLOW_NAME = 'Subscribe'
REQUIRES_PAYMENT = False  # Subscribe is ALWAYS free
PAYMENT_AMOUNT = 0


def handle_init(data: Dict, flow_token: str, request_id: str) -> Dict:
    """INIT → navigate to PERSONAL_INFO screen."""
    return {
        'screen': 'PERSONAL_INFO',
        'data': {},
    }


def handle_review(data: Dict, flow_token: str, request_id: str) -> Dict:
    """REVIEW screen → save subscription, return SUCCESS.
    response_payload is set FIRST, saves happen after.
    """
    phone = get_phone_from_token(flow_token)
    phone_number_id = get_phone_number_id_for_flow(flow_token)

    # Extract form data
    full_name = data.get('full_name', '')
    phone_number = data.get('phone_number', '')
    email_address = data.get('email_address', '')
    company_name = data.get('company_name', '')
    wa_username = data.get('wa_username', '')
    gstin = data.get('gstin', '')
    designation = data.get('designation', '')
    paid_by = data.get('paid_by', 'self')
    is_pep = data.get('is_pep', False)
    pep_details = data.get('pep_details', '')

    # Addresses
    ship_addr = _extract_shipping(data)
    bill_addr = _extract_billing(data, ship_addr)

    # Generate subscriber ID
    subscriber_uuid = str(uuid.uuid4())
    contact_id = find_contact_by_phone(phone)
    existing_sub_id = _find_existing_subscriber_id(contact_id)
    subscriber_id = existing_sub_id or f'WD-SUB-{subscriber_uuid[:8].upper()}'
    is_resubscribe = bool(existing_sub_id)

    # ── SET SUCCESS RESPONSE FIRST — before any saves ──
    welcome_msg = (
        f'Welcome back to WECARE.DIGITAL! Your details have been updated.\nSubscriber ID: {subscriber_id}'
        if is_resubscribe else
        f'Welcome to WECARE.DIGITAL! Your subscriber ID is {subscriber_id}.'
    )
    response_payload = {
        'screen': 'SUCCESS',
        'data': {
            'subscriber_id': subscriber_id,
            'message': welcome_msg,
        }
    }

    # ── Now do saves (non-blocking) ──
    now_ts = int(time.time())
    try:
        _save_contact(contact_id, subscriber_uuid, phone, full_name, email_address,
                      company_name, wa_username, gstin, designation, paid_by,
                      is_pep, pep_details, ship_addr, bill_addr, now_ts)
        if not contact_id:
            contact_id = subscriber_uuid
    except Exception as e:
        logger.warning(f'Subscribe contact save failed: {e}')

    try:
        save_flow_submission(
            flow_code=FLOW_CODE, flow_type='subscription', phone=phone,
            contact_id=contact_id, sender_name=full_name,
            form_data={'full_name': full_name, 'phone_number': phone_number,
                       'email_address': email_address, 'company_name': company_name},
            flow_token=flow_token, request_id=request_id,
            submission_number=subscriber_id,
            requires_payment=False, payment_amount=0, status='completed',
        )
    except Exception as e:
        logger.warning(f'Subscribe submission save failed: {e}')

    # Send confirmation (async, non-blocking)
    try:
        confirm_text = (
            f'✅ *Subscription {"Updated" if is_resubscribe else "Confirmed"}*\n\n'
            f'👤 *Name:* {full_name}\n📱 *Phone:* {phone_number}\n'
            f'📧 *Email:* {email_address}\n🏢 *Organization:* {company_name}\n'
            f'🆔 *Subscriber ID:* {subscriber_id}\n\n'
            f'Your details have been saved. You will receive order updates, offers, and service news.\n\n'
            f'Type *my id* anytime to retrieve your subscriber ID.\n_WECARE.DIGITAL_'
        )
        lambda_client.invoke(
            FunctionName=OUTBOUND_WHATSAPP_FUNCTION,
            InvocationType='Event',
            Payload=json.dumps({'body': json.dumps({
                'contactId': contact_id, 'recipientPhone': phone,
                'content': confirm_text, 'phoneNumberId': phone_number_id,
            })})
        )
    except Exception as e:
        logger.warning(f'Subscribe confirmation send failed: {e}')

    return response_payload


# ── Private helpers ──

def _find_existing_subscriber_id(contact_id: str) -> str:
    if not contact_id:
        return ''
    try:
        fs_table = dynamodb.Table(FLOW_SUBMISSIONS_TABLE)
        resp = fs_table.query(
            IndexName='phone', KeyConditionExpression='phone = :ph',
            FilterExpression='flowCode = :fc',
            ExpressionAttributeValues={':ph': contact_id, ':fc': FLOW_CODE},
            ScanIndexForward=False, Limit=1,
        )
        items = resp.get('Items', [])
        return items[0].get('submissionId', '') if items else ''
    except Exception:
        return ''


def _extract_shipping(data: Dict) -> Dict:
    return {
        'name': data.get('ship_name', ''), 'phone_number': data.get('ship_phone', ''),
        'address': data.get('ship_street', ''), 'city': data.get('ship_city', ''),
        'state': data.get('ship_state', ''), 'in_pin_code': data.get('ship_pin', ''),
        'house_number': data.get('ship_house', ''), 'building_name': data.get('ship_building', ''),
        'tower_number': data.get('ship_tower', ''), 'floor_number': data.get('ship_floor', ''),
        'landmark_area': data.get('ship_landmark', ''), 'country': data.get('ship_country', 'India'),
    }


def _extract_billing(data: Dict, ship: Dict) -> Dict:
    same = data.get('same_as_ship', False)
    bill = {
        'name': ship['name'], 'phone_number': ship['phone_number'],
        'address': data.get('bill_street', '') or (ship['address'] if same else ''),
        'city': data.get('bill_city', '') or (ship['city'] if same else ''),
        'state': data.get('bill_state', '') or (ship['state'] if same else ''),
        'in_pin_code': data.get('bill_pin', '') or (ship['in_pin_code'] if same else ''),
        'house_number': data.get('bill_house', '') or (ship['house_number'] if same else ''),
        'building_name': data.get('bill_building', '') or (ship['building_name'] if same else ''),
        'tower_number': data.get('bill_tower', '') or (ship['tower_number'] if same else ''),
        'floor_number': data.get('bill_floor', '') or (ship['floor_number'] if same else ''),
        'landmark_area': data.get('bill_landmark', '') or (ship['landmark_area'] if same else ''),
        'country': data.get('bill_country', 'India'),
    }
    return bill


def _addr_str(a: Dict) -> str:
    parts = [a.get(k, '') for k in ['name', 'house_number', 'building_name', 'address',
                                     'landmark_area', 'city', 'state', 'in_pin_code', 'country']]
    return ', '.join(p for p in parts if p)


def _save_contact(contact_id, subscriber_uuid, phone, full_name, email,
                  company, username, gstin, designation, paid_by,
                  is_pep, pep_details, ship_addr, bill_addr, now_ts):
    ct = dynamodb.Table(CONTACTS_TABLE)
    if contact_id:
        ct.update_item(
            Key={'id': contact_id},
            UpdateExpression='SET #nm=:nm, #em=:em, #sa=:sa, #ba=:ba, #ua=:ua, '
                             '#cbn=:cbn, #ow=:ow, #os=:os, #oe=:oe, #cmn=:cmn',
            ExpressionAttributeNames={
                '#nm': 'name', '#em': 'email', '#sa': 'shippingAddress',
                '#ba': 'billingAddress', '#ua': 'updatedAt', '#cbn': 'contactBookName',
                '#ow': 'optInWhatsApp', '#os': 'optInSms', '#oe': 'optInEmail', '#cmn': 'companyName',
            },
            ExpressionAttributeValues={
                ':nm': full_name, ':em': email,
                ':sa': _addr_str(ship_addr), ':ba': _addr_str(bill_addr),
                ':ua': now_ts, ':cbn': company,
                ':ow': True, ':os': True, ':oe': True, ':cmn': company,
            },
        )
    else:
        norm_phone = phone.replace('+', '').replace(' ', '')
        if norm_phone and not norm_phone.startswith('+'):
            norm_phone = f'+{norm_phone}'
        ct.put_item(Item={
            'id': subscriber_uuid, 'contactId': subscriber_uuid,
            'name': full_name, 'phone': norm_phone, 'email': email,
            'contactBookName': company, 'companyName': company,
            'username': username, 'gstin': gstin,
            'shippingAddress': _addr_str(ship_addr), 'billingAddress': _addr_str(bill_addr),
            'optInWhatsApp': True, 'optInSms': True, 'optInEmail': True,
            'tags': ['subscriber'], 'createdAt': now_ts, 'updatedAt': now_ts,
        })
