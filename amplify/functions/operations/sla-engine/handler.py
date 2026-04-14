"""
SLA Engine — Scheduled Lambda for auto-assignment and escalation.

Runs on a schedule (e.g. every 15 minutes via EventBridge).
Checks for:
1. Unassigned requests older than SLA threshold → auto-assign
2. Overdue requests → escalate priority / notify admin
3. Stale appointments → mark as no_show

Environment variables:
  SLA_ASSIGN_MINUTES: Minutes before unassigned request gets auto-assigned (default: 30)
  SLA_ESCALATE_MINUTES: Minutes before open request gets escalated (default: 240 = 4 hours)
  SLA_APPOINTMENT_MINUTES: Minutes past appointment time before marking no_show (default: 60)
  DEFAULT_ASSIGNEE: Default admin to assign to (default: 'admin')
  NOTIFY_PHONE: Phone number to send WhatsApp alerts to
"""
import os
import json
import time
import logging
from typing import Dict, Any, List
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

TABLE_PREFIX = os.environ.get('TABLE_PREFIX', 'stack-wecare-digital')
SUBMISSIONS_TABLE = f'{TABLE_PREFIX}-FlowSubmissionTable'
APPOINTMENTS_TABLE = f'{TABLE_PREFIX}-AppointmentTable'
ENTERPRISE_TABLE = f'{TABLE_PREFIX}-EnterpriseAssistTable'
STATUS_HISTORY_TABLE = f'{TABLE_PREFIX}-RequestStatusHistoryTable'

SLA_ASSIGN_MINUTES = int(os.environ.get('SLA_ASSIGN_MINUTES', '30'))
SLA_ESCALATE_MINUTES = int(os.environ.get('SLA_ESCALATE_MINUTES', '240'))
SLA_APPOINTMENT_MINUTES = int(os.environ.get('SLA_APPOINTMENT_MINUTES', '60'))
DEFAULT_ASSIGNEE = os.environ.get('DEFAULT_ASSIGNEE', 'admin')


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    request_id = context.aws_request_id if context else 'local'
    now = int(time.time())
    results = {
        'auto_assigned': 0,
        'escalated': 0,
        'no_show_marked': 0,
        'errors': [],
    }

    logger.info(json.dumps({'event': 'sla_engine_start', 'requestId': request_id}))

    # 1. Auto-assign unassigned open requests
    try:
        results['auto_assigned'] = _auto_assign_requests(now)
    except Exception as e:
        results['errors'].append(f'auto_assign: {e}')
        logger.error(f'Auto-assign failed: {e}')

    # 2. Escalate overdue requests
    try:
        results['escalated'] = _escalate_overdue(now)
    except Exception as e:
        results['errors'].append(f'escalate: {e}')
        logger.error(f'Escalate failed: {e}')

    # 3. Mark stale appointments as no_show
    try:
        results['no_show_marked'] = _mark_no_show_appointments(now)
    except Exception as e:
        results['errors'].append(f'no_show: {e}')
        logger.error(f'No-show marking failed: {e}')

    logger.info(json.dumps({'event': 'sla_engine_complete', **results, 'requestId': request_id}))
    return results


def _auto_assign_requests(now: int) -> int:
    """Auto-assign open requests that have no assignee and are older than SLA threshold."""
    table = dynamodb.Table(SUBMISSIONS_TABLE)
    threshold = now - (SLA_ASSIGN_MINUTES * 60)
    count = 0

    resp = table.query(
        IndexName='status',
        KeyConditionExpression=Key('status').eq('open'),
    )
    for item in resp.get('Items', []):
        created = int(item.get('createdAt', now))
        if created < threshold and not item.get('assignedTo'):
            try:
                table.update_item(
                    Key={'submissionId': item['submissionId']},
                    UpdateExpression='SET assignedTo = :a, updatedAt = :u',
                    ExpressionAttributeValues={
                        ':a': DEFAULT_ASSIGNEE,
                        ':u': Decimal(str(now)),
                    },
                )
                _log_history(item['submissionId'], item.get('orderId', ''),
                             'open', 'open', 'sla_engine',
                             f'Auto-assigned to {DEFAULT_ASSIGNEE} (SLA: {SLA_ASSIGN_MINUTES}min)')
                count += 1
            except Exception as e:
                logger.warning(f'Auto-assign failed for {item["submissionId"]}: {e}')

    return count


def _escalate_overdue(now: int) -> int:
    """Escalate requests that have been open/in_progress beyond the escalation threshold."""
    table = dynamodb.Table(SUBMISSIONS_TABLE)
    threshold = now - (SLA_ESCALATE_MINUTES * 60)
    count = 0

    for status in ['open', 'in_progress']:
        resp = table.query(
            IndexName='status',
            KeyConditionExpression=Key('status').eq(status),
        )
        for item in resp.get('Items', []):
            created = int(item.get('createdAt', now))
            notes = item.get('notes', '') or ''
            if created < threshold and '[ESCALATED]' not in notes:
                try:
                    new_notes = f'{notes}\n[ESCALATED {time.strftime("%d %b %H:%M", time.gmtime(now + 19800))}] SLA breach — {SLA_ESCALATE_MINUTES}min exceeded'.strip()
                    table.update_item(
                        Key={'submissionId': item['submissionId']},
                        UpdateExpression='SET notes = :n, updatedAt = :u',
                        ExpressionAttributeValues={
                            ':n': new_notes[:2000],
                            ':u': Decimal(str(now)),
                        },
                    )
                    _log_history(item['submissionId'], item.get('orderId', ''),
                                 status, status, 'sla_engine',
                                 f'SLA escalation — open for >{SLA_ESCALATE_MINUTES}min')
                    count += 1
                except Exception as e:
                    logger.warning(f'Escalation failed for {item["submissionId"]}: {e}')

    return count


def _mark_no_show_appointments(now: int) -> int:
    """Mark appointments as no_show if they're past the slot time + buffer."""
    table = dynamodb.Table(APPOINTMENTS_TABLE)
    count = 0

    for status in ['scheduled', 'confirmed']:
        resp = table.query(
            IndexName='status',
            KeyConditionExpression=Key('status').eq(status),
        )
        for item in resp.get('Items', []):
            slot_date = item.get('slotDate', '')
            slot_time = item.get('slotTime', '23:59')
            if not slot_date:
                continue
            try:
                from datetime import datetime
                dt_str = f'{slot_date} {slot_time}'
                for fmt in ['%Y-%m-%d %I:%M %p', '%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S']:
                    try:
                        dt = datetime.strptime(dt_str, fmt)
                        slot_ts = int(dt.timestamp())
                        break
                    except ValueError:
                        slot_ts = 0
                if slot_ts and (now - slot_ts) > (SLA_APPOINTMENT_MINUTES * 60):
                    table.update_item(
                        Key={'appointmentId': item['appointmentId']},
                        UpdateExpression='SET #s = :s, updatedAt = :u',
                        ExpressionAttributeNames={'#s': 'status'},
                        ExpressionAttributeValues={
                            ':s': 'no_show',
                            ':u': Decimal(str(now)),
                        },
                    )
                    count += 1
            except Exception as e:
                logger.warning(f'No-show check failed for {item.get("appointmentId")}: {e}')

    return count


def _log_history(sub_id: str, order_id: str, old_status: str, new_status: str, changed_by: str, notes: str):
    import uuid
    try:
        table = dynamodb.Table(STATUS_HISTORY_TABLE)
        table.put_item(Item={
            'historyId': str(uuid.uuid4()),
            'submissionId': sub_id,
            'orderId': order_id,
            'oldStatus': old_status,
            'newStatus': new_status,
            'changedBy': changed_by,
            'notes': notes,
            'changedAt': int(time.time()),
        })
    except Exception:
        pass
