"""Durable DynamoDB persistence for SEO audits and AI request logs."""
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

TABLE_NAME = os.environ.get('SEO_TOOLS_TABLE', 'stack-wecare-digital-SeoToolsTable')
_table = None


def table():
    global _table
    if _table is None:
        _table = boto3.resource(
            'dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1')
        ).Table(TABLE_NAME)
    return _table


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _clean(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean(item) for item in value]
    return value


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def put_record(record: Dict[str, Any]) -> Dict[str, Any]:
    required = {'id', 'recordType', 'createdAt', 'slug'}
    missing = required - set(record)
    if missing:
        raise ValueError(f"Missing storage fields: {', '.join(sorted(missing))}")
    table().put_item(Item=_clean(record))
    return record


def get_audit(audit_id: str) -> Optional[Dict[str, Any]]:
    item = table().get_item(Key={'id': audit_id}).get('Item')
    if not item or item.get('recordType') != 'audit':
        return None
    return _json_safe(item)


def list_records(record_type: str, scope: str = '', limit: int = 200) -> List[Dict[str, Any]]:
    limit = min(max(limit, 1), 500)
    kwargs: Dict[str, Any] = {
        'IndexName': 'recordType-createdAt-index',
        'KeyConditionExpression': Key('recordType').eq(record_type),
        'ScanIndexForward': False,
    }
    items: List[Dict[str, Any]] = []
    while len(items) < limit:
        response = table().query(**kwargs)
        page = response.get('Items', [])
        if scope == 'pages':
            page = [item for item in page if item.get('pageType') != 'blog']
        elif scope == 'blog':
            page = [item for item in page if item.get('pageType') == 'blog']
        items.extend(page)
        if 'LastEvaluatedKey' not in response:
            break
        kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
    return [_json_safe(item) for item in items[:limit]]


def list_slug_records(slug: str) -> List[Dict[str, Any]]:
    kwargs: Dict[str, Any] = {
        'IndexName': 'slug-createdAt-index',
        'KeyConditionExpression': Key('slug').eq(slug),
        'ScanIndexForward': False,
    }
    items: List[Dict[str, Any]] = []
    while True:
        response = table().query(**kwargs)
        items.extend(response.get('Items', []))
        if 'LastEvaluatedKey' not in response:
            break
        kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
    return [_json_safe(item) for item in items]


def transition_audit(
    audit_id: str,
    expected_statuses: Iterable[str],
    new_status: str,
    actor: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    expected = list(expected_statuses)
    if not expected:
        raise ValueError('At least one expected status is required')
    names = {'#status': 'status'}
    values: Dict[str, Any] = {
        ':newStatus': new_status, ':actor': actor, ':updatedAt': now_iso(),
        ':auditType': 'audit',
    }
    assignments = ['#status = :newStatus', 'reviewedBy = :actor', 'updatedAt = :updatedAt']
    for index, status in enumerate(expected):
        values[f':expected{index}'] = status
    for index, (key, value) in enumerate((extra or {}).items()):
        name, token = f'#extra{index}', f':extra{index}'
        names[name], values[token] = key, _clean(value)
        assignments.append(f'{name} = {token}')
    condition = 'recordType = :auditType AND #status IN (' + ', '.join(
        f':expected{index}' for index in range(len(expected))
    ) + ')'
    try:
        response = table().update_item(
            Key={'id': audit_id}, UpdateExpression='SET ' + ', '.join(assignments),
            ConditionExpression=condition, ExpressionAttributeNames=names,
            ExpressionAttributeValues=values, ReturnValues='ALL_NEW',
        )
        return _json_safe(response.get('Attributes', {}))
    except ClientError as error:
        if error.response.get('Error', {}).get('Code') == 'ConditionalCheckFailedException':
            return None
        raise


def delete_slug_audits(slug: str) -> int:
    audits = [item for item in list_slug_records(slug) if item.get('recordType') == 'audit']
    for item in audits:
        table().delete_item(Key={'id': item['id']})
    return len(audits)
