"""
Audit logging helper — writes to the existing AuditLog model
(table `stack-wecare-digital-AuditLogsTable`).

Usage:
    from lambda_utils.audit import record_audit
    record_audit(action='template.create', actor=user_id, resource_type='template',
                 resource_id=name, details={'category': cat})

Fails open (never raises) so auditing can't break a request. Details are secret-masked.
"""
import os
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import boto3

from lambda_utils.logging import get_logger
from lambda_utils.masking import mask_secrets

logger = get_logger(__name__)

AUDIT_TABLE = os.environ.get('AUDIT_LOG_TABLE', 'stack-wecare-digital-AuditLogsTable')
TTL_DAYS = int(os.environ.get('AUDIT_TTL_DAYS', '180'))

_dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

# Canonical auditable actions (extend as needed)
ACTIONS = {
    'waba.sync', 'assigned_user.add', 'assigned_user.remove', 'webhook.subscribe',
    'webhook.unsubscribe', 'phone_setting.update', 'template.create', 'template.edit',
    'template.delete', 'template.send_test', 'flow.create', 'flow.update', 'flow.upload',
    'flow.publish', 'flow.deprecate', 'flow.clone', 'flow.migrate', 'qr.delete',
    'commerce.update', 'group.create', 'group.update', 'group.delete', 'payment.lookup',
    'payment.refund', 'dlq.replay', 'secret.update', 'feature_flag.update', 'username.claim',
    'username.delete', 'ai_policy.update',
}


def record_audit(action: str, actor: Optional[str] = None, resource_type: Optional[str] = None,
                 resource_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Write an audit record. Returns logId on success, None on failure (never raises)."""
    log_id = str(uuid.uuid4())
    now = int(time.time())
    try:
        item = {
            'logId': log_id,
            'action': action,
            'userId': actor or 'system',
            'resourceType': resource_type or '',
            'resourceId': resource_id or '',
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'details': json.dumps(mask_secrets(details or {}), default=str)[:8000],
            'expiresAt': now + TTL_DAYS * 24 * 60 * 60,
        }
        _dynamodb.Table(AUDIT_TABLE).put_item(Item={k: v for k, v in item.items() if v != ''})
        return log_id
    except Exception as e:  # noqa: BLE001
        logger.warning('{"event":"audit_write_failed","action":"%s","error":"%s"}' % (action, str(e)[:160]))
        return None
