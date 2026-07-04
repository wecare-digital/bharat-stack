"""
Automation Rules Lambda — CRUD for cross-channel automation rules.

A rule: when an inbound message matches a trigger (keyword/any) on a channel, run an
action (auto-reply text / AI). Rules live in AutomationRulesTable; the shared
lambda_utils/automation.py evaluator (called by inbound handlers) reads them.

Endpoints (HTTP API):
  GET    /automation/rules          - list rules
  POST   /automation/rules          - create rule
  PUT    /automation/rules/{id}     - update rule
  DELETE /automation/rules/{id}     - delete rule
"""
import os
import json
import time
import uuid
import boto3

from lambda_utils.response import cors_response, options_response, extract_origin
from lambda_utils.logging import get_logger

logger = get_logger(__name__)
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
RULES_TABLE = os.environ.get('AUTOMATION_RULES_TABLE', 'stack-wecare-digital-AutomationRulesTable')

VALID_CHANNELS = ('any', 'whatsapp', 'sms', 'rcs', 'email')
VALID_TRIGGERS = ('keyword', 'any')
VALID_ACTIONS = ('reply', 'ai')


def _table():
    return dynamodb.Table(RULES_TABLE)


def handler(event, context):
    origin = extract_origin(event)
    rc = event.get('requestContext', {})
    method = rc.get('http', {}).get('method', event.get('httpMethod', 'GET')).upper()
    if method == 'OPTIONS':
        return options_response(origin)

    from lambda_utils.middleware import require_auth
    _auth = require_auth(event)
    if _auth is not None:
        return _auth

    path_params = event.get('pathParameters') or {}
    rule_id = path_params.get('id') or path_params.get('ruleId')

    try:
        if method == 'GET':
            resp = _table().scan()
            items = sorted(resp.get('Items', []), key=lambda x: int(x.get('priority', 100)))
            return cors_response(200, {'rules': items, 'count': len(items)}, origin)

        if method == 'POST':
            body = json.loads(event.get('body', '{}'))
            now = int(time.time())
            rid = str(uuid.uuid4())
            item = {
                'id': rid,
                'name': str(body.get('name', 'Untitled rule'))[:120],
                'enabled': bool(body.get('enabled', True)),
                'channel': body.get('channel', 'any') if body.get('channel') in VALID_CHANNELS else 'any',
                'triggerType': body.get('triggerType', 'keyword') if body.get('triggerType') in VALID_TRIGGERS else 'keyword',
                'triggerValue': str(body.get('triggerValue', ''))[:200],
                'actionType': body.get('actionType', 'reply') if body.get('actionType') in VALID_ACTIONS else 'reply',
                'actionValue': str(body.get('actionValue', ''))[:2000],
                'priority': int(body.get('priority', 100)),
                'createdAt': now,
                'updatedAt': now,
            }
            _table().put_item(Item=item)
            return cors_response(200, {'rule': item}, origin)

        if method == 'PUT':
            if not rule_id:
                return cors_response(400, {'error': 'rule id required'}, origin)
            body = json.loads(event.get('body', '{}'))
            existing = _table().get_item(Key={'id': rule_id}).get('Item')
            if not existing:
                return cors_response(404, {'error': 'rule not found'}, origin)
            for f in ('name', 'enabled', 'channel', 'triggerType', 'triggerValue', 'actionType', 'actionValue', 'priority'):
                if f in body:
                    existing[f] = body[f]
            existing['updatedAt'] = int(time.time())
            _table().put_item(Item=existing)
            return cors_response(200, {'rule': existing}, origin)

        if method == 'DELETE':
            if not rule_id:
                return cors_response(400, {'error': 'rule id required'}, origin)
            _table().delete_item(Key={'id': rule_id})
            return cors_response(200, {'success': True, 'deleted': rule_id}, origin)

        return cors_response(405, {'error': 'method not allowed'}, origin)
    except json.JSONDecodeError:
        return cors_response(400, {'error': 'invalid JSON'}, origin)
    except Exception as e:
        logger.error(f'automation-rules error: {e}')
        return cors_response(500, {'error': 'internal error'}, origin)
