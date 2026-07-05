"""
Partner (Embedded Signup) prepaid billing / metering.

Model
-----
Each onboarded tenant (WABA) has a PREPAID WALLET. Usage is metered per tenant
from WhatsApp message-status webhooks (which carry a `pricing.category`), priced
via a configurable rate card, and deducted from the wallet. A ledger records
every top-up and charge. Sending is blocked when the wallet is empty/suspended.

Tables (DynamoDB, created by scripts/_setup_partner_billing.py)
  PartnerWallet  PK wabaId            -> balance, currency, status, threshold, updatedAt
  PartnerLedger  PK wabaId, SK ts     -> type(topup|charge), amount, category, balanceAfter, note, ttl

Who-used-what: every charge row is attributed to a wabaId + category + messageId,
so per-customer usage is fully auditable from the ledger.

Restriction: `is_sufficient()` gates outbound sends; `charge()` auto-suspends a
wallet that drops to/below its low-balance threshold.
"""
import os
import json
import time
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional

import boto3

from lambda_utils.logging import get_logger

logger = get_logger(__name__)

REGION = os.environ.get('AWS_REGION', 'us-east-1')
WALLET_TABLE = os.environ.get('PARTNER_WALLET_TABLE', 'stack-wecare-digital-PartnerWallet')
LEDGER_TABLE = os.environ.get('PARTNER_LEDGER_TABLE', 'stack-wecare-digital-PartnerLedger')
DEFAULT_CURRENCY = os.environ.get('PARTNER_DEFAULT_CURRENCY', 'INR')
LEDGER_TTL_DAYS = int(os.environ.get('PARTNER_LEDGER_TTL_DAYS', '400'))

# Per-message rate card by WhatsApp category, in wallet currency. Includes any
# markup you want over Meta's cost. Override with RATE_CARD env (JSON).
DEFAULT_RATE_CARD = {'MARKETING': 0.90, 'UTILITY': 0.15, 'AUTHENTICATION': 0.12, 'SERVICE': 0.0}
try:
    RATE_CARD = {**DEFAULT_RATE_CARD, **json.loads(os.environ.get('RATE_CARD', '{}') or '{}')}
except json.JSONDecodeError:
    RATE_CARD = DEFAULT_RATE_CARD

_ddb = boto3.resource('dynamodb', region_name=REGION)


def _wallet_tbl():
    return _ddb.Table(WALLET_TABLE)


def _ledger_tbl():
    return _ddb.Table(LEDGER_TABLE)


def _dec(x) -> Decimal:
    return Decimal(str(x))


def rate_for(category: str) -> float:
    return float(RATE_CARD.get((category or '').upper(), 0.0))


def get_wallet(waba_id: str) -> dict:
    if not waba_id:
        return {}
    item = _wallet_tbl().get_item(Key={'wabaId': waba_id}).get('Item') or {}
    if item:
        item['balance'] = float(item.get('balance', 0))
        item['threshold'] = float(item.get('threshold', 0))
    return item


def ensure_wallet(waba_id: str, currency: str = None) -> dict:
    w = get_wallet(waba_id)
    if w:
        return w
    now = datetime.now(timezone.utc).isoformat()
    _wallet_tbl().put_item(Item={
        'wabaId': waba_id, 'balance': _dec(0), 'currency': currency or DEFAULT_CURRENCY,
        'status': 'ACTIVE', 'threshold': _dec(0), 'updatedAt': now,
    })
    return get_wallet(waba_id)


def _ledger(waba_id: str, kind: str, amount: float, balance_after: float,
            category: str = '', note: str = '', message_id: str = '') -> None:
    ts = datetime.now(timezone.utc).isoformat()
    try:
        _ledger_tbl().put_item(Item={
            'wabaId': waba_id, 'ts': ts, 'type': kind, 'amount': _dec(amount),
            'balanceAfter': _dec(balance_after), 'category': category or '',
            'note': note or '', 'messageId': message_id or '',
            'ttl': int(time.time()) + LEDGER_TTL_DAYS * 86400,
        })
    except Exception as e:  # noqa: BLE001
        logger.warning(json.dumps({'event': 'partner_ledger_error', 'wabaId': waba_id, 'error': str(e)}))


def topup(waba_id: str, amount: float, note: str = '', actor: str = 'admin', currency: str = None) -> dict:
    ensure_wallet(waba_id, currency)
    resp = _wallet_tbl().update_item(
        Key={'wabaId': waba_id},
        UpdateExpression='SET balance = balance + :a, #s = :active, updatedAt = :t',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':a': _dec(amount), ':active': 'ACTIVE',
                                   ':t': datetime.now(timezone.utc).isoformat()},
        ReturnValues='UPDATED_NEW')
    bal = float(resp['Attributes']['balance'])
    _ledger(waba_id, 'topup', amount, bal, note=note or f'top-up by {actor}')
    logger.info(json.dumps({'event': 'partner_topup', 'wabaId': waba_id, 'amount': amount, 'balance': bal}))
    return {'wabaId': waba_id, 'balance': bal, 'status': 'ACTIVE'}


def is_sufficient(waba_id: str, estimate: float = 0.0) -> bool:
    """Gate for outbound sends on a partner WABA. Non-partner WABAs (no wallet)
    return True so platform-owned numbers are never blocked."""
    w = get_wallet(waba_id)
    if not w:
        return True  # not a metered partner wallet
    if w.get('status') != 'ACTIVE':
        return False
    return float(w.get('balance', 0)) >= float(estimate)


def charge(waba_id: str, amount: float = None, category: str = '', message_id: str = '', note: str = '') -> dict:
    """Deduct usage from a partner wallet. If amount is None it is derived from
    the category rate card. Auto-suspends when balance hits the threshold."""
    w = get_wallet(waba_id)
    if not w:
        return {'charged': False, 'reason': 'no wallet'}
    amt = amount if amount is not None else rate_for(category)
    if amt <= 0:
        return {'charged': False, 'reason': 'zero cost', 'category': category}
    resp = _wallet_tbl().update_item(
        Key={'wabaId': waba_id},
        UpdateExpression='SET balance = balance - :a, updatedAt = :t',
        ExpressionAttributeValues={':a': _dec(amt), ':t': datetime.now(timezone.utc).isoformat()},
        ReturnValues='UPDATED_NEW')
    bal = float(resp['Attributes']['balance'])
    _ledger(waba_id, 'charge', amt, bal, category=category, note=note, message_id=message_id)
    # auto-suspend at/below threshold
    threshold = float(w.get('threshold', 0))
    if bal <= threshold:
        _wallet_tbl().update_item(
            Key={'wabaId': waba_id}, UpdateExpression='SET #s = :s',
            ExpressionAttributeNames={'#s': 'status'}, ExpressionAttributeValues={':s': 'SUSPENDED'})
        logger.warning(json.dumps({'event': 'partner_wallet_suspended', 'wabaId': waba_id, 'balance': bal}))
    return {'charged': True, 'amount': amt, 'balance': bal, 'category': category}


def list_wallets() -> list:
    wallets = []
    kwargs = {}
    while True:
        resp = _wallet_tbl().scan(**kwargs)
        for it in resp.get('Items', []):
            wallets.append({'wabaId': it.get('wabaId'), 'balance': float(it.get('balance', 0)),
                            'currency': it.get('currency', DEFAULT_CURRENCY), 'status': it.get('status', 'ACTIVE'),
                            'threshold': float(it.get('threshold', 0)), 'updatedAt': it.get('updatedAt', '')})
        lek = resp.get('LastEvaluatedKey')
        if not lek:
            break
        kwargs['ExclusiveStartKey'] = lek
    return wallets


def recent_ledger(waba_id: str, limit: int = 20) -> list:
    resp = _ledger_tbl().query(
        KeyConditionExpression='wabaId = :w', ExpressionAttributeValues={':w': waba_id},
        ScanIndexForward=False, Limit=limit)
    out = []
    for it in resp.get('Items', []):
        out.append({'ts': it.get('ts'), 'type': it.get('type'), 'amount': float(it.get('amount', 0)),
                    'balanceAfter': float(it.get('balanceAfter', 0)), 'category': it.get('category', ''),
                    'note': it.get('note', ''), 'messageId': it.get('messageId', '')})
    return out
