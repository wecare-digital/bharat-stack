"""
Leave Review Flow — Customer feedback and ratings.
Screens: REVIEW_FORM → CONFIRM (terminal)
Saves to ReviewTable + FlowSubmissionTable.
"""
import json, time, uuid, logging
from decimal import Decimal
from typing import Dict
from flows.common import (
    dynamodb, get_phone_from_token, find_contact_by_phone,
    get_contact_name, record_completion,
)

logger = logging.getLogger(__name__)
REVIEWS_TABLE = 'stack-wecare-digital-ReviewTable'
FLOW_CODE = 'WD_REV'


def handle_init(data: Dict, flow_token: str, request_id: str) -> Dict:
    return {
        'screen': 'REVIEW_FORM',
        'data': {
            'ratings': [
                {'id': '5', 'title': '⭐⭐⭐⭐⭐ Excellent'},
                {'id': '4', 'title': '⭐⭐⭐⭐ Good'},
                {'id': '3', 'title': '⭐⭐⭐ Average'},
                {'id': '2', 'title': '⭐⭐ Below Average'},
                {'id': '1', 'title': '⭐ Poor'},
            ],
            'categories': [
                {'id': 'service', 'title': 'Service'},
                {'id': 'product', 'title': 'Product'},
                {'id': 'delivery', 'title': 'Delivery'},
                {'id': 'support', 'title': 'Support'},
                {'id': 'other', 'title': 'Other'},
            ],
        }
    }


def handle_review_form(data: Dict, flow_token: str, request_id: str) -> Dict:
    phone = get_phone_from_token(flow_token)
    contact_id = find_contact_by_phone(phone)
    name = get_contact_name(contact_id)
    # Derived from the completion key rather than random. A Meta retry of
    # this data_exchange recomputes the same id, so the domain write below
    # overwrites an identical row instead of creating a second one, and the
    # conditional put inside record_completion refuses the duplicate.
    from lambda_utils import flow_completion as _fc
    review_id = _fc.reference_for(
        _fc.completion_key(flow_token, 'REVIEW_FORM', data)[0], 'WD-REV')
    now = int(time.time())

    rating = 0
    try:
        rating = int(data.get('rating', '0'))
    except (ValueError, TypeError):
        pass

    try:
        table = dynamodb.Table(REVIEWS_TABLE)
        table.put_item(Item={k: v for k, v in {
            'reviewId': review_id,
            'customerPhone': phone,
            'customerName': name,
            'contactId': contact_id,
            'rating': rating,
            'reviewText': data.get('review_text', ''),
            'category': data.get('category', 'other'),
            'status': 'submitted',
            'createdAt': Decimal(str(now)),
            'updatedAt': Decimal(str(now)),
        }.items() if v is not None and v != ''})
    except Exception as e:
        logger.warning(f'Review save failed: {e}')

    try:
        result = record_completion(
            flow_code=FLOW_CODE, flow_type='feedback', phone=phone,
            contact_id=contact_id, sender_name=name,
            form_data=data, flow_token=flow_token, request_id=request_id,
            screen='REVIEW_FORM', submission_number=review_id, requires_payment=False, status='submitted',
        )
    except Exception as e:
        logger.warning(f'Review submission save failed: {e}')

    # Only a fresh claim may message the customer. Without this guard a Meta
    # retry of the same completion sent a second confirmation for one submission.
    if result.should_fire_side_effects:
        try:
            from flows.common import send_simple_confirmation
            send_simple_confirmation(phone, flow_token, 'Review Submitted', review_id,
                f'*Rating:* {"⭐" * rating}\n*Category:* {data.get("category", "")}')
        except Exception:
            pass

    stars = '⭐' * rating if rating else ''
    return {
        'screen': 'CONFIRM',
        'data': {
            'review_id': review_id,
            'message': f'Thank you for your {stars} feedback! Your review has been submitted.',
        }
    }
