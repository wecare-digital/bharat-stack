"""Bedrock Agent action group handler — READ tools only.

Purpose: answer questions for an internal Bedrock agent. It cannot send, write or
delete anything.

What changed on 2026-09-23
--------------------------
This handler exposed twelve tools, and eight of them were things a language model
should not be able to choose on its own. All eight are now refused by
`lambda_utils.agent.governance`, and their implementations are DELETED rather than
left behind an `if` - dead code that still works is how a power comes back.

  * SEND - sendWhatsApp / sendSms / sendEmail invoked wecare-outbound-* directly
    with a phone number and a body, so a model's tool choice was the only
    authorisation between it and a real customer under our registered sender.
  * SCAN - searchContacts paginated the WHOLE ContactsTable to exhaustion then
    filtered in Python; getStats did three exhaustive scans; getMessages scanned
    both message tables. Every one was a `while True` on LastEvaluatedKey.
  * DELETE - deleteMessage hard-deleted from the message store; deleteContact
    wrote a deletedAt marker.
  * FABRICATE - createInvoice returned success with an INV-<random> id and wrote
    nothing, so the agent told people an invoice existed when it did not.

Three bugs were hiding inside the removed powers, each only reachable because the
power existed at all:

  * deleteMessage reported success for ANY id. `delete_item` succeeds on a key that
    does not exist, and the inbound attempt was wrapped in `try/except: pass`, so
    the outbound branch was unreachable and every call claimed a deletion.
  * deleteContact used an unconditional `update_item`, which DynamoDB treats as an
    upsert - deleting an unknown id CREATED a row holding only {id, deletedAt}.
  * _find_contact_by_phone scanned with `contains(phone, last10)` and `Limit=1`.
    Limit applies BEFORE the FilterExpression, so it examined one arbitrary item
    and filtered it away, normally matching nobody; and `contains` on ten digits
    could match a different number. ContactsTable has phone-index and email-index,
    both ALL-projected, so the scan was never needed.

The four surviving tools are READ, and every read is bounded: one page, an explicit
Limit sent to DynamoDB rather than a Python slice, and a `truncated` flag so a
partial answer cannot be presented as a total. "Found 25 contacts" and "found at
least 25" are different claims and the agent repeats whichever it is handed.

Live agent state
----------------
An older docstring here named agent QIEEHEBTZO / alias ASCBD7YPUT. Neither exists.
Measured 2026-09-23: the account holds exactly one agent, 4UUQYFWX64
(wecare-digital-agent), status NOT_PREPARED - so nothing can currently invoke this
through Bedrock at all. It IS reachable over HTTP at POST /ai/agent, which is why
require_auth below is load-bearing. Reconciling the agent/alias/prepared state is
tracked separately.
"""

import json
import os
from typing import Any, Dict, List, Optional

import boto3

from lambda_utils import contact_key  # `id` is physical; `contactId` is its alias
from lambda_utils.agent import governance as gov
from lambda_utils.agent import plans, receipts
from lambda_utils.logging import get_logger, log_event
from lambda_utils.response import extract_origin

logger = get_logger(__name__)

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'stack-wecare-digital-ContactsTable')
MESSAGES_INBOUND_TABLE = os.environ.get(
    'MESSAGES_INBOUND_TABLE', 'stack-wecare-digital-WhatsAppInboundTable')
MESSAGES_OUTBOUND_TABLE = os.environ.get(
    'MESSAGES_OUTBOUND_TABLE', 'stack-wecare-digital-WhatsAppOutboundTable')

# There is deliberately no lambda client and no OUTBOUND_*_FUNCTION here. Removing
# the capability means removing the means, not guarding the call: an outbound
# function name left in the environment is an invitation, and the IAM role already
# permits lambda:InvokeFunction on wecare-*.

# Contact lookups go through these, never a scan.
PHONE_INDEX = os.environ.get('CONTACTS_PHONE_INDEX', 'phone-index')
EMAIL_INDEX = os.environ.get('CONTACTS_EMAIL_INDEX', 'email-index')

# Maps the two calling conventions onto one catalog. Bedrock can present an action
# group either as named functions or as API paths, and the previous code had two
# independent routing tables - so a tool could be reachable by one spelling and not
# the other. One table now, and a test asserts it matches the catalog exactly.
_API_PATH_TO_TOOL = {
    '/send-whatsapp': 'sendWhatsApp',
    '/send-sms': 'sendSms',
    '/send-email': 'sendEmail',
    '/create-contact': 'createContact',
    '/update-contact': 'updateContact',
    '/delete-contact': 'deleteContact',
    '/search-contacts': 'searchContacts',
    '/get-contact': 'getContact',
    '/delete-message': 'deleteMessage',
    '/get-messages': 'getMessages',
    '/create-invoice': 'createInvoice',
    '/get-stats': 'getStats',
    '/list-tools': 'listTools',
}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle a Bedrock action group request, or an authenticated HTTP call.

    Bedrock invokes this DIRECTLY as a Lambda, so its events carry actionGroup /
    function / parameters and no API Gateway request context. POST /ai/agent also
    exposes it over HTTP, and that route had NO authentication at either layer -
    anyone could drive the action group, and its actions included sending WhatsApp.
    require_auth exempts the direct invoke (it tests for an API Gateway context:
    apiId / domainName / http.sourceIp, all injected by the gateway and not
    settable by a caller) while making the HTTP route require a signed-in user.
    """
    request_id = getattr(context, 'aws_request_id', 'local') if context else 'local'
    _origin = extract_origin(event)

    from lambda_utils.middleware import require_auth
    auth_failure = require_auth(event)
    if auth_failure is not None:
        return auth_failure

    function_name = event.get('function') or ''
    api_path = event.get('apiPath') or ''
    tool_name = function_name or _API_PATH_TO_TOOL.get(api_path, '')

    log_event(logger, 'agent_action_received',
              actionGroup=event.get('actionGroup'),
              function=function_name or None, apiPath=api_path or None,
              tool=tool_name or None, requestId=request_id)

    try:
        tool = gov.assert_executable(tool_name)
    except gov.ToolRefused as refused:
        # Audit the ATTEMPT. An agent reaching for a removed power is a signal about
        # its prompt, and the previous code had no way to see it happening at all.
        log_event(logger, 'agent_tool_refused', level='warning',
                  alert='AGENT_APPLY_ATTEMPTED',
                  tool=refused.tool, toolClass=refused.tool_class,
                  requestId=request_id)
        return _build_response(
            _refusal_with_plan(refused, _extract_parameters(event), request_id),
            tool_name)
    except gov.ToolUnknown:
        log_event(logger, 'agent_tool_unknown', level='warning',
                  function=function_name or None, apiPath=api_path or None,
                  requestId=request_id)
        return _build_response({
            'success': False,
            'refused': True,
            'error': 'Unknown tool. Only the listed read tools are available.',
            'available': sorted(gov.catalog_summary()['enabled']),
        }, tool_name)

    try:
        params = _extract_parameters(event)
        result = _READS[tool.name](params, request_id)
    except Exception as exc:  # noqa: BLE001
        # No detail to the caller: an exception string here can carry a table name
        # or a key, and this response is read by a model and then by a person.
        log_event(logger, 'agent_action_error', level='error',
                  tool=tool.name, errorType=type(exc).__name__,
                  error=str(exc)[:200], requestId=request_id)
        result = {'success': False, 'error': f'{tool.name} failed. See the logs.'}

    return _build_response(result, tool.name)


def _refusal_with_plan(refused: gov.ToolRefused, params: Dict[str, Any],
                       request_id: str) -> Dict[str, Any]:
    """The refusal, plus a dry-run plan of what the call WOULD have done.

    A bare "no" tells an agent nothing it can act on, and leaves it free to invent a
    narration. A plan gives it something concrete to hand to a person: an identified,
    hashed description of the exact intent, which a human can approve out of band.

    The plan is built for APPLY tools only. A refused READ - which can only mean the
    kill switch - has nothing to plan, and manufacturing one would imply the read is
    a side effect awaiting approval.
    """
    result = refused.as_result()
    if refused.tool_class != gov.CLASS_APPLY:
        return result

    try:
        plan = plans.build_plan(refused.tool, params)
    except (gov.ToolUnknown, plans.PlanNotApplicable):
        return result

    # The receipt is the audit trail for the attempt. Fails open, which is right
    # here: nothing happened, so the record is evidence rather than a safeguard.
    # See lambda_utils/agent/receipts.py for why that is NOT sufficient once an
    # apply can actually run.
    receipts.record_receipt(plan, result=receipts.RESULT_REFUSED,
                            detail=f'refused at {request_id}')

    result['plan'] = plans.describe_plan(plan)
    result['nextStep'] = (
        'Show this plan to a person and ask them to carry it out. Do not state '
        'that it has been done.')
    return result


def _list_tools(params: Dict, request_id: str) -> Dict:
    """What this agent can and cannot do, from the catalog rather than a prompt.

    A model that has to guess tool names guesses wrong and then explains the failure
    creatively. Reading the catalog is cheaper than that, and the refused entries
    carry their reasons so the model can say something true about why.
    """
    summary = gov.catalog_summary()
    return {
        'success': True,
        'catalogVersion': gov.CATALOG_VERSION,
        'enabled': summary['enabled'],
        'refused': summary['refused'],
        'message': (f'{len(summary["enabled"])} tools available, '
                    f'{len(summary["refused"])} refused. Refused tools cannot be '
                    f'made to work by retrying or rewording.'),
    }


def _extract_parameters(event: Dict) -> Dict[str, str]:
    """Pull parameters from either Bedrock convention."""
    params: Dict[str, str] = {}
    for param in event.get('parameters') or []:
        if param.get('name'):
            params[param['name']] = param.get('value')

    body = event.get('requestBody') or {}
    properties = ((body.get('content') or {})
                  .get('application/json') or {}).get('properties') or []
    for prop in properties:
        if prop.get('name'):
            params[prop['name']] = prop.get('value')

    return params


# ============== READ TOOLS ==============

def _get_contact(params: Dict, request_id: str) -> Dict:
    """One contact, by id, phone or email. Index lookups only."""
    contact_id = params.get('contactId') or params.get('contact_id')
    phone = params.get('phone')
    email = params.get('email')

    contact: Optional[Dict[str, Any]] = None
    if contact_id:
        response = _contacts().get_item(Key=contact_key.key(contact_id))
        contact = response.get('Item')
    elif phone:
        contact = _first(gov.query_index(_contacts(), index_name=PHONE_INDEX,
                                        key_name='phone', value=phone))
    elif email:
        contact = _first(gov.query_index(_contacts(), index_name=EMAIL_INDEX,
                                        key_name='email', value=str(email).lower()))
    else:
        return {'success': False, 'error': 'A contact id, phone or email is required'}

    if not contact or contact.get('deletedAt'):
        return {'success': False, 'error': 'Contact not found'}

    return {'success': True, 'contact': _contact_view(contact)}


def _search_contacts(params: Dict, request_id: str) -> Dict:
    """Contacts matching a query. Bounded, and honest about being bounded.

    An exact phone or email is answered from an index. Otherwise this is a bounded
    single-page scan filtered in Python, because there is no name index - and it
    says `truncated` rather than implying it saw everything, which the exhaustive
    version did while also reading the whole table.
    """
    query = str(params.get('query') or '').strip()
    if not query:
        return {'success': False, 'error': 'A search query is required'}

    limit = gov.bounded_limit(params.get('limit'))

    # An exact identifier does not need a scan at all.
    digits = ''.join(c for c in query if c.isdigit())
    if len(digits) >= 10:
        for candidate in _phone_candidates(query, digits):
            found = gov.query_index(_contacts(), index_name=PHONE_INDEX,
                                    key_name='phone', value=candidate, limit=limit)
            if found:
                return _search_result([c for c in found if not c.get('deletedAt')],
                                      truncated=False, query=query, via='phone-index')
    if '@' in query:
        found = gov.query_index(_contacts(), index_name=EMAIL_INDEX,
                                key_name='email', value=query.lower(), limit=limit)
        if found:
            return _search_result([c for c in found if not c.get('deletedAt')],
                                  truncated=False, query=query, via='email-index')

    items, truncated = gov.read_page(
        _contacts(), limit=limit,
        FilterExpression='attribute_not_exists(deletedAt)')

    needle = query.lower()
    matches = [item for item in items
               if needle in str(item.get('name') or '').lower()
               or needle in str(item.get('phone') or '').lower()
               or needle in str(item.get('email') or '').lower()]
    return _search_result(matches, truncated=truncated, query=query,
                          via='bounded-scan')


def _get_messages(params: Dict, request_id: str) -> Dict:
    """Recent messages for one contact. One bounded page per table.

    Neither message table has a contactId index, so this is a filtered scan. It is
    bounded to a single page rather than paginated to exhaustion, and reports
    `truncated` when either table had more.
    """
    contact_id = params.get('contactId') or params.get('contact_id')
    if not contact_id:
        return {'success': False, 'error': 'A contact id is required'}

    limit = gov.bounded_limit(params.get('limit'))
    messages: List[Dict[str, Any]] = []
    truncated = False

    for table_name, direction in ((MESSAGES_INBOUND_TABLE, 'inbound'),
                                  (MESSAGES_OUTBOUND_TABLE, 'outbound')):
        items, more = gov.read_page(
            dynamodb.Table(table_name), limit=limit,
            FilterExpression='contactId = :cid',
            ExpressionAttributeValues={':cid': contact_id})
        truncated = truncated or more
        for item in items:
            messages.append({
                'id': item.get('id'),
                'direction': direction,
                'content': item.get('content'),
                'timestamp': str(item.get('timestamp') or ''),
                'status': item.get('status'),
            })

    messages.sort(key=lambda m: m.get('timestamp') or '', reverse=True)
    return {
        'success': True,
        'contactId': contact_id,
        'returned': len(messages[:limit]),
        'truncated': truncated or len(messages) > limit,
        'messages': messages[:limit],
        'message': (f'{len(messages[:limit])} recent messages'
                    + (' (more exist)' if truncated or len(messages) > limit else '')),
    }


def _get_stats(params: Dict, request_id: str) -> Dict:
    """Approximate counts, from table metadata rather than three full scans.

    `DescribeTable`'s ItemCount updates roughly every six hours, which is a real
    limitation and is stated in the response instead of being hidden. The previous
    version got an exact number by scanning three tables to exhaustion on every
    call - an unbounded, per-read-billed operation triggered by a model asking how
    things are going. An approximate count labelled approximate is the better
    trade; an exact one needs a maintained counter, not a scan.
    """
    client = dynamodb.meta.client
    counts: Dict[str, int] = {}
    for label, table_name in (('contacts', CONTACTS_TABLE),
                              ('inboundMessages', MESSAGES_INBOUND_TABLE),
                              ('outboundMessages', MESSAGES_OUTBOUND_TABLE)):
        described = client.describe_table(TableName=table_name)
        counts[label] = int(described['Table'].get('ItemCount') or 0)

    total_messages = counts['inboundMessages'] + counts['outboundMessages']
    return {
        'success': True,
        'approximate': True,
        'stats': {
            'totalContacts': counts['contacts'],
            'totalInboundMessages': counts['inboundMessages'],
            'totalOutboundMessages': counts['outboundMessages'],
            'totalMessages': total_messages,
        },
        'message': (f'Approximately {counts["contacts"]} contacts and '
                    f'{total_messages} messages. These counts come from table '
                    f'metadata and can lag by several hours. Deleted contacts are '
                    f'included.'),
    }


_READS = {
    'getContact': _get_contact,
    'searchContacts': _search_contacts,
    'getMessages': _get_messages,
    'getStats': _get_stats,
    'listTools': _list_tools,
}


# ============== HELPERS ==============

def _contacts():
    return dynamodb.Table(CONTACTS_TABLE)


def _first(items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return items[0] if items else None


def _phone_candidates(raw: str, digits: str) -> List[str]:
    """The stored forms an exact index lookup should try.

    An index Query is exact, so the shape has to match what was written. Measured:
    every ContactsTable row holds a +91 E.164 string. The bare and 91-prefixed
    forms are tried too, because a caller may type either - but each attempt is an
    exact match, never `contains`, which is what let the old lookup return the
    wrong person.
    """
    tail = digits[-10:]
    ordered = [raw.strip(), f'+{digits}', digits, f'+91{tail}', f'91{tail}', tail]
    seen, out = set(), []
    for candidate in ordered:
        if candidate and candidate not in seen:
            seen.add(candidate)
            out.append(candidate)
    return out


def _contact_view(contact: Dict[str, Any]) -> Dict[str, Any]:
    """The fields an agent may see. An allowlist, not the whole row.

    Returning the row would hand a model every field the contact record has ever
    accumulated, including provenance and any future internal flag, and from there
    into a prompt and a transcript.

    `id` is resolved through the helper rather than read directly, because a row may
    carry either spelling: `contact.get('contactId', '')` yields `''` for an
    `id`-only row, and `''` looks like a valid contact id to everything downstream.
    A divergence is reported rather than swallowed - `resolve` still returns a usable
    key so the read is not blocked, but the row is evidence that some writer is
    broken, and that has to reach CloudWatch to be found.
    """
    try:
        contact_key.assert_consistent(contact)
    except contact_key.ContactKeyMismatch as mismatch:
        log_event(logger, 'contact_key_mismatch', level='error',
                  alert='CONTACT_KEY_MISMATCH',
                  detail=str(mismatch)[:200], source='agent-action-group')

    return {
        'id': contact_key.resolve(contact),
        'name': contact.get('name'),
        'phone': contact.get('phone'),
        'email': contact.get('email'),
        'createdAt': contact.get('createdAt'),
    }


def _search_result(contacts: List[Dict[str, Any]], *, truncated: bool,
                   query: str, via: str) -> Dict[str, Any]:
    view = [_contact_view(c) for c in contacts]
    return {
        'success': True,
        'returned': len(view),
        'truncated': truncated,
        'via': via,
        'contacts': view,
        # Phrased so a bounded answer cannot be repeated as a complete one.
        'message': (f'{len(view)} contact(s) matching "{query}"'
                    + (', and more may exist beyond the page that was read'
                       if truncated else '')),
    }


def _build_response(result: Dict, tool_name: str = '') -> Dict:
    """Bedrock action group response envelope."""
    return {
        'messageVersion': '1.0',
        'response': {
            'actionGroup': 'wecare-actions',
            'function': tool_name,
            'functionResponse': {
                'responseBody': {
                    'TEXT': {'body': json.dumps(result)},
                },
            },
        },
    }
