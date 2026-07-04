"""
Conversation Meta Lambda — shared-team-inbox collaboration metadata per conversation.

Stores, per conversation (keyed by contactId), the team-inbox fields that don't belong on
individual messages: status (open/pending/resolved), assignee, labels/tags, and internal
notes (team-only, never sent to the customer).

Endpoints (HTTP API):
  GET    /inbox/meta/{conversationId}        - get meta (status, assignee, tags, notes)
  PUT    /inbox/meta/{conversationId}        - update status / assignee / tags
  POST   /inbox/meta/{conversationId}/note   - append an internal note
  GET    /inbox/meta                         - list all meta (for board/filters)
"""
import os
import json
import time
import boto3

from lambda_utils.response import cors_response, options_response, extract_origin
from lambda_utils.logging import get_logger

logger = get_logger(__name__)
dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))
META_TABLE = os.environ.get('CONVERSATION_META_TABLE', 'stack-wecare-digital-ConversationMetaTable')

VALID_STATUS = ('open', 'pending', 'resolved')


def _table():
    return dynamodb.Table(META_TABLE)


def _get(cid):
    item = _table().get_item(Key={'conversationId': cid}).get('Item')
    return item or {'conversationId': cid, 'status': 'open', 'assignee': '', 'tags': [], 'notes': []}


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

    pp = event.get('pathParameters') or {}
    cid = pp.get('conversationId')
    path = event.get('rawPath', event.get('path', ''))
    is_note = path.endswith('/note')

    try:
        if method == 'GET' and not cid:
            resp = _table().scan()
            return cors_response(200, {'meta': resp.get('Items', []), 'count': resp.get('Count', 0)}, origin)

        if method == 'GET' and cid:
            return cors_response(200, {'meta': _get(cid)}, origin)

        if method == 'POST' and cid and is_note:
            body = json.loads(event.get('body', '{}'))
            text = str(body.get('text', '')).strip()[:2000]
            if not text:
                return cors_response(400, {'error': 'note text required'}, origin)
            item = _get(cid)
            notes = item.get('notes', []) or []
            notes.append({'text': text, 'by': str(body.get('by', 'agent'))[:80], 'at': int(time.time())})
            item['notes'] = notes[-100:]
            item['updatedAt'] = int(time.time())
            _table().put_item(Item=item)
            return cors_response(200, {'meta': item}, origin)

        if method == 'PUT' and cid:
            body = json.loads(event.get('body', '{}'))
            item = _get(cid)
            if 'status' in body and body['status'] in VALID_STATUS:
                item['status'] = body['status']
            if 'assignee' in body:
                item['assignee'] = str(body['assignee'])[:120]
            if 'tags' in body and isinstance(body['tags'], list):
                item['tags'] = [str(t)[:40] for t in body['tags']][:20]
            item['updatedAt'] = int(time.time())
            _table().put_item(Item=item)
            return cors_response(200, {'meta': item}, origin)

        return cors_response(405, {'error': 'method not allowed'}, origin)
    except json.JSONDecodeError:
        return cors_response(400, {'error': 'invalid JSON'}, origin)
    except Exception as e:
        logger.error(f'conversation-meta error: {e}')
        return cors_response(500, {'error': 'internal error'}, origin)
