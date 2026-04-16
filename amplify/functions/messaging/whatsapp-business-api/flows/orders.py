"""
Order-centric helpers — central order lookup, sync, and dropdown formatting.
Used by Submit Request, Track Request, and all order-linked flows.
OrdersTable is the single source of truth for all order sources (Wix, manual, Shopify, etc.).
"""
import os
import json
import time
import uuid
import logging
from decimal import Decimal
from typing import Dict, List

import boto3

logger = logging.getLogger(__name__)

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
lambda_client = boto3.client('lambda', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

ORDERS_TABLE = os.environ.get('ORDERS_TABLE', 'stack-wecare-digital-OrderTable')
FLOW_SUBMISSIONS_TABLE = os.environ.get('FLOW_SUBMISSIONS_TABLE', 'stack-wecare-digital-FlowSubmissionTable')


def extract_short_id(wd_order_number: str) -> str:
    """Extract short ID from WD-ORD number. 'WD-ORD - A1B2C3D4 - ...' → 'A1B2C3D4'"""
    if not wd_order_number:
        return ''
    parts = wd_order_number.split(' - ')
    return parts[1] if len(parts) >= 2 else wd_order_number[:12]


def format_order_dropdown(wd_id: str, created_date: str = '', total: str = '',
                          first_item: str = '', order_date_ist: str = '') -> str:
    """Build readable dropdown title: 'A1B2C3D4 — 22 Feb 2026, 6:00 PM'"""
    short = extract_short_id(wd_id)
    if order_date_ist:
        return f'{short} — {order_date_ist}'
    if created_date:
        try:
            from datetime import datetime, timezone, timedelta
            dt = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
            ist = dt.astimezone(timezone(timedelta(hours=5, minutes=30)))
            return f'{short} — {ist.strftime("%-d %b %Y, %-I:%M %p")}'
        except Exception:
            pass
    # Fallback: parse date/time from the WD-ORD string itself
    parts = wd_id.split(' - ')
    if len(parts) >= 4:
        try:
            date_part = parts[2].strip()  # "22-02-2026"
            time_part = parts[3].strip()  # "17:43:01"
            dd, mm, yyyy = date_part.split('-')
            hh_str, mi_str = time_part.split(':')[:2]
            months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
            month_name = months[int(mm) - 1]
            h = int(hh_str)
            ampm = 'PM' if h >= 12 else 'AM'
            h12 = 12 if h == 0 else (h - 12 if h > 12 else h)
            return f'{short} — {int(dd)} {month_name} {yyyy}, {h12}:{mi_str} {ampm}'
        except Exception:
            pass
    return short


def sync_wix_order_to_orders_table(order: dict, phone: str) -> str:
    """Sync a Wix order into the central OrdersTable. Returns orderId or ''."""
    try:
        summary = order.get('_summary', {})
        wd_id = order.get('customOrderNumber', '') or summary.get('customOrderNumber', '')
        if not wd_id or not wd_id.startswith('WD-ORD'):
            return ''
        short = extract_short_id(wd_id)
        created = summary.get('createdDate', '')
        order_date_ist = ''
        order_date = ''
        order_time = ''
        if created:
            try:
                from datetime import datetime, timezone, timedelta
                dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                ist = dt.astimezone(timezone(timedelta(hours=5, minutes=30)))
                order_date_ist = ist.strftime('%d %b %Y, %I:%M %p')
                order_date = ist.strftime('%Y-%m-%d')
                order_time = ist.strftime('%H:%M:%S')
            except Exception:
                pass
        items = summary.get('lineItems', [])
        items_summary = ', '.join(f"{i.get('name', '')} × {i.get('quantity', 1)}" for i in items[:5])
        total = float(summary.get('totalAmount', 0) or 0)
        table = dynamodb.Table(ORDERS_TABLE)
        now = int(time.time())
        table.put_item(Item={
            k: v for k, v in {
                'orderId': wd_id,
                'shortId': short,
                'source': 'wix',
                'sourceOrderId': order.get('id', ''),
                'sourceOrderNumber': str(summary.get('orderNumber', '')),
                'customerPhone': phone or summary.get('billingPhone', ''),
                'customerName': summary.get('billingName', ''),
                'customerEmail': summary.get('buyerEmail', ''),
                'orderDate': order_date,
                'orderTime': order_time,
                'orderDateIST': order_date_ist,
                'itemsSummary': items_summary,
                'itemsJson': json.dumps(items),
                'itemCount': summary.get('lineItemCount', len(items)),
                'totalAmount': Decimal(str(total)) if total else Decimal('0'),
                'currency': 'INR',
                'orderStatus': (summary.get('status', 'active') or 'active').lower(),
                'paymentStatus': (summary.get('paymentStatus', 'pending') or 'pending').lower(),
                'fulfillmentStatus': summary.get('fulfillmentStatus', ''),
                'createdAt': now,
                'updatedAt': now,
                'syncedAt': now,
            }.items() if v is not None and v != ''
        })

        # Upsert buyer into Contacts table (so WhatsApp Flow can find them)
        buyer_phone = phone or summary.get('billingPhone', '')
        buyer_email = summary.get('buyerEmail', '')
        buyer_name = summary.get('billingName', '')
        if buyer_phone:
            try:
                contacts_table_name = os.environ.get('CONTACTS_TABLE', 'stack-wecare-digital-ContactsTable')
                ct = dynamodb.Table(contacts_table_name)
                clean_phone = buyer_phone.replace(' ', '').replace('-', '')
                if not clean_phone.startswith('+'):
                    clean_phone = f'+{clean_phone}' if clean_phone.startswith('91') else f'+91{clean_phone}'
                # Check if contact exists
                resp = ct.query(
                    IndexName='phone-index',
                    KeyConditionExpression='phone = :p',
                    ExpressionAttributeValues={':p': clean_phone},
                    Limit=1, ProjectionExpression='contactId',
                )
                if not resp.get('Items'):
                    ct.put_item(Item={
                        k: v for k, v in {
                            'contactId': str(uuid.uuid4()),
                            'name': buyer_name,
                            'phone': clean_phone,
                            'email': buyer_email,
                            'country': 'IN',
                            'optInWhatsApp': False,
                            'allowlistWhatsApp': False,
                            'createdAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                            'updatedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                        }.items() if v is not None and v != '' and v is not False
                    })
                    logger.info(f'Contact created for {clean_phone} from Wix order sync')
            except Exception as ce:
                logger.debug(f'Contact upsert skipped: {ce}')

        return wd_id
    except Exception as e:
        logger.debug(f'Order sync to OrdersTable failed: {e}')
        return ''


def create_manual_order(customer_phone: str, customer_name: str = '',
                        items_summary: str = '', total_amount: float = 0,
                        notes: str = '') -> Dict:
    """Create a manual order in OrdersTable. Returns the order dict."""
    from datetime import datetime, timezone, timedelta
    now_utc = datetime.now(timezone.utc)
    ist = now_utc.astimezone(timezone(timedelta(hours=5, minutes=30)))
    short = uuid.uuid4().hex[:8].upper()
    wd_id = f'WD-ORD - {short} - {ist.strftime("%d-%m-%Y")} - {ist.strftime("%H:%M:%S")} - IST'
    order_date_ist = ist.strftime('%d %b %Y, %I:%M %p')
    now_ts = int(time.time())
    item = {
        'orderId': wd_id,
        'shortId': short,
        'source': 'manual',
        'sourceOrderId': '',
        'sourceOrderNumber': '',
        'customerPhone': customer_phone,
        'customerName': customer_name,
        'orderDate': ist.strftime('%Y-%m-%d'),
        'orderTime': ist.strftime('%H:%M:%S'),
        'orderDateIST': order_date_ist,
        'itemsSummary': items_summary or 'Manual order',
        'totalAmount': Decimal(str(total_amount)) if total_amount else Decimal('0'),
        'currency': 'INR',
        'orderStatus': 'active',
        'paymentStatus': 'pending',
        'adminNotes': notes,
        'createdAt': now_ts,
        'updatedAt': now_ts,
    }
    table = dynamodb.Table(ORDERS_TABLE)
    table.put_item(Item={k: v for k, v in item.items() if v is not None and v != ''})
    logger.info(json.dumps({'event': 'manual_order_created', 'orderId': wd_id, 'shortId': short}))
    return item


def get_order(order_id: str) -> Dict:
    """Get a single order from OrdersTable by orderId."""
    try:
        table = dynamodb.Table(ORDERS_TABLE)
        resp = table.get_item(Key={'orderId': order_id})
        return resp.get('Item', {})
    except Exception as e:
        logger.warning(f'Order lookup failed: {e}')
        return {}


def get_submissions_for_order(order_id: str) -> List[Dict]:
    """Get all FlowSubmissions linked to an orderId."""
    try:
        table = dynamodb.Table(FLOW_SUBMISSIONS_TABLE)
        resp = table.query(
            IndexName='orderId',
            KeyConditionExpression='orderId = :oid',
            ExpressionAttributeValues={':oid': order_id},
            ScanIndexForward=False,
        )
        return resp.get('Items', [])
    except Exception as e:
        logger.warning(f'Submissions lookup for order {order_id} failed: {e}')
        return []


def fetch_orders_for_flow(phone: str, email: str) -> list:
    """
    Fetch orders for a user by phone or email.
    ORDER-CENTRIC: queries OrdersTable first (all sources), then Wix as fallback.
    Returns list of {id, title} for WhatsApp Flow dropdown.
    Dropdown format: "A1B2C3D4 — 22 Feb 2026, 6:00 PM"
    Internal id: full "WD-ORD - A1B2C3D4 - 22-02-2026 - 18:00:00 - IST"
    """
    results = []
    seen = set()

    def _add(wd_id: str, title: str):
        if wd_id and wd_id not in seen:
            seen.add(wd_id)
            results.append({'id': wd_id, 'title': title})

    clean_phone = ''
    clean_phone_short = ''
    if phone:
        clean_phone = phone.replace('+', '').replace(' ', '').replace('-', '')
        clean_phone_short = clean_phone[2:] if len(clean_phone) > 10 and clean_phone.startswith('91') else clean_phone

    # ── Source 1: OrdersTable (all sources) ──
    try:
        orders_table = dynamodb.Table(ORDERS_TABLE)
        for pv in [f'+{clean_phone}', clean_phone, f'+91{clean_phone_short}']:
            try:
                resp = orders_table.query(
                    IndexName='customerPhone',
                    KeyConditionExpression='customerPhone = :p',
                    ExpressionAttributeValues={':p': pv},
                    ScanIndexForward=False, Limit=20,
                )
                for item in resp.get('Items', []):
                    wd_id = item.get('orderId', '')
                    if not wd_id.startswith('WD-ORD'):
                        continue
                    title = format_order_dropdown(
                        wd_id, order_date_ist=item.get('orderDateIST', ''),
                        total=str(item.get('totalAmount', '')),
                        first_item=(item.get('itemsSummary', '') or '').split(',')[0].strip(),
                    )
                    _add(wd_id, title)
                if results:
                    break
            except Exception:
                pass
        if results:
            logger.info(json.dumps({'action': 'fetch_orders', 'source': 'orders_table', 'count': len(results)}))
            return results
    except Exception as e:
        logger.debug(f'OrdersTable query skipped: {e}')

    # ── Source 2: Wix Store Lambda (sync to OrdersTable + return) ──
    try:
        params = {'limit': '20'}
        if email:
            params['email'] = email
        wix_resp = lambda_client.invoke(
            FunctionName=os.environ.get('WIX_STORE_FUNCTION', 'wecare-wix-store'),
            InvocationType='RequestResponse',
            Payload=json.dumps({
                'requestContext': {'http': {'method': 'GET'}},
                'rawPath': '/wix-store/orders',
                'queryStringParameters': params,
                'headers': {'origin': 'https://admin.wecare.digital'},
            })
        )
        wix_body = json.loads(json.loads(wix_resp['Payload'].read()).get('body', '{}'))
        for order in wix_body.get('orders', []):
            summary = order.get('_summary', {})
            wd_id = order.get('customOrderNumber', '') or summary.get('customOrderNumber', '')
            if not wd_id or not wd_id.startswith('WD-ORD'):
                continue
            if not email and clean_phone:
                bp = (summary.get('billingPhone', '') or '').replace('+', '').replace(' ', '').replace('-', '')
                if clean_phone_short not in bp and clean_phone not in bp:
                    continue
            sync_wix_order_to_orders_table(order, phone)
            title = format_order_dropdown(
                wd_id, created_date=summary.get('createdDate', ''),
                total=summary.get('totalAmount', '0'),
                first_item=(summary.get('lineItems', [{}])[0].get('name', '') if summary.get('lineItems') else ''),
            )
            _add(wd_id, title)
        if results:
            logger.info(json.dumps({'action': 'fetch_orders', 'source': 'wix_lambda', 'count': len(results)}))
            return results
    except Exception as e:
        logger.warning(json.dumps({'action': 'fetch_orders_wix_failed', 'error': str(e)}))

    # ── Source 3: Wix Velo fallback ──
    try:
        import urllib.request, urllib.parse
        wix_url = os.environ.get('WIX_SITE_URL', 'https://www.wecare.digital')
        api_key = os.environ.get('WIX_API_KEY', '')
        qp = f'email={urllib.parse.quote(email)}' if email else ''
        url = f'{wix_url}/_functions/orders?limit=50&{qp}'
        hdrs = {'x-api-key': api_key} if api_key else {}
        req = urllib.request.Request(url, headers=hdrs, method='GET')
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            for o in data.get('orders', []):
                wd_id = o.get('customOrderNumber', '') or (o.get('customField', {}) or {}).get('value', '')
                if not wd_id or not wd_id.startswith('WD-ORD'):
                    continue
                if not email and clean_phone:
                    op = (o.get('buyerPhone', '') or '').replace('+', '').replace(' ', '').replace('-', '')
                    if clean_phone_short not in op and clean_phone not in op:
                        continue
                _add(wd_id, format_order_dropdown(wd_id))
    except Exception as e:
        logger.error(json.dumps({'action': 'fetch_orders_velo_failed', 'error': str(e)}))

    return results
