"""
CRM read/write surface: leads, pipeline, opportunities, activities, contact 360.

Every route authenticates through `lambda_utils.middleware.require_auth` before any
dispatch, on the same API (`zllr9lrg7j`) as the rest of the fleet. Measured 2026-09-23:
326 routes, 0 gateway-authorized, 300 authenticating in-handler, 5 deliberately public,
0 OPEN. This function joins the 300, so `scripts/audit_route_auth.py` stays at 0 OPEN.

Reads need any authenticated user; writes need `Operator`. A Viewer may look at the funnel
and must not move a deal through it.

Three decisions worth stating
-----------------------------
**The actor is taken from the token, never from the body.** `event['_auth']['username']` is
what lands in an Activity's `actorId`. A client-supplied actor would let any authenticated
user attribute a stage change to somebody else, which makes the timeline useless as the audit
trail for stage movement - its main job.

**No scans.** Every read goes through one of the ten GSIs provisioned in Phase 4b. The
account already holds 75 tables; a scan-per-request habit here becomes the cost line nobody
can explain, and on a board view it would be a scan per column.

**Payment state is normalised on read.** `PaymentsTable`, `InvoicesTable`,
`FlowSubmissionTable` and `OrderTable` spell the same real-world state five different ways -
`paid` in one is `captured` in another - and Phase 4d deliberately left the *stored* values
alone rather than running a migration. `payment_status.canonical()` maps them here, so a
caller of `/crm/contacts/{id}/360` sees one vocabulary without having to know which table a
row came from. Amounts are reported as integer `amountPaise` plus a `amountRupees` string,
never a float.

Routes
------
    GET    /crm/pipelines                          board configuration
    GET    /crm/leads?state=NEW&limit=50           the work queue
    POST   /crm/leads                              capture (Operator)
    GET    /crm/leads/{leadId}
    PATCH  /crm/leads/{leadId}                     transition (Operator)
    POST   /crm/leads/{leadId}/convert             to opportunity (Operator)
    GET    /crm/opportunities?stageId=...          one board column
    GET    /crm/opportunities/{opportunityId}
    PATCH  /crm/opportunities/{opportunityId}      move stage (Operator)
    GET    /crm/activities?contactId=...           one subject's timeline
    POST   /crm/activities                         log an activity (Operator)
    GET    /crm/contacts/{contactId}/360           contact, leads, opps, timeline, payments
"""

import json
import os
from decimal import Decimal
from typing import Any, Dict, List, Optional

import boto3

from lambda_utils.logging import get_logger
from lambda_utils.response import cors_response, extract_origin, options_response
from lambda_utils.middleware import require_auth
from lambda_utils import contact_key, payment_status
from lambda_utils.crm import keys as crm_keys
from lambda_utils.crm import service as crm_service
from lambda_utils.crm import states as crm_states
from lambda_utils.crm import store as crm_store

logger = get_logger(__name__)

dynamodb = boto3.resource('dynamodb', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'stack-wecare-digital-ContactsTable')
PAYMENTS_TABLE = os.environ.get('PAYMENTS_TABLE', 'stack-wecare-digital-PaymentsTable')
INVOICES_TABLE = os.environ.get('INVOICES_TABLE', 'stack-wecare-digital-InvoicesTable')

#: Writes require this role. Reads require only a valid token.
WRITE_ROLE = 'Operator'

#: Caps every list response. A caller asking for 10000 rows on a board column would turn one
#: request into a sustained read burst; the ceiling is here rather than trusting the query
#: string.
MAX_LIMIT = 200
DEFAULT_LIMIT = 50


def _json_safe(value: Any) -> Any:
    """DynamoDB `Decimal` -> int/float, recursively.

    `json.dumps` cannot serialise `Decimal`, and every numeric attribute from DynamoDB is
    one. Integers stay integers so `amountPaise` does not become `25000.0`.
    """
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _limit(params: Dict[str, Any]) -> int:
    try:
        requested = int(params.get('limit') or DEFAULT_LIMIT)
    except (TypeError, ValueError):
        return DEFAULT_LIMIT
    return max(1, min(requested, MAX_LIMIT))


def _actor(event: Dict[str, Any]) -> str:
    """Who is acting, from the verified token.

    Never from the request body. A client-supplied actor would let any authenticated user
    attribute a stage change to a colleague, which destroys the timeline's value as the audit
    trail for stage movement.
    """
    return str((event.get('_auth') or {}).get('username') or '')


def _body(event: Dict[str, Any]) -> Dict[str, Any]:
    raw = event.get('body') or '{}'
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    request_id = getattr(context, 'aws_request_id', 'local')
    origin = extract_origin(event)
    rc = event.get('requestContext', {}) or {}
    method = (rc.get('http', {}).get('method') or event.get('httpMethod') or 'GET').upper()
    path = rc.get('http', {}).get('path') or event.get('rawPath') or ''

    if method == 'OPTIONS':
        return options_response(origin)

    # Auth before dispatch. Nothing below this line runs for an unauthenticated caller.
    auth_failure = require_auth(event)
    if auth_failure is not None:
        return auth_failure

    # Writes need Operator. Re-checking here rather than per-branch so a new write route
    # cannot be added without the gate.
    if method in ('POST', 'PATCH', 'PUT', 'DELETE'):
        role_failure = require_auth(event, required_role=WRITE_ROLE)
        if role_failure is not None:
            return role_failure

    params = event.get('queryStringParameters') or {}
    path_params = event.get('pathParameters') or {}
    body = _body(event)

    logger.info(json.dumps({
        'event': 'crm_request', 'method': method, 'path': path,
        'actor': _actor(event), 'role': (event.get('_auth') or {}).get('role', ''),
        'requestId': request_id,
    }))

    try:
        return _route(method, path, path_params, params, body, event, origin, request_id)
    except ValueError as exc:
        # Domain-level refusals (a bad id shape, an unknown source) are the caller's fault.
        return cors_response(400, {'error': str(exc)}, origin)
    except Exception as exc:  # noqa: BLE001
        logger.error(json.dumps({
            'event': 'crm_error', 'method': method, 'path': path,
            'error': str(exc)[:300], 'requestId': request_id,
        }))
        return cors_response(500, {'error': 'Internal error'}, origin)


def _route(method: str, path: str, path_params: Dict[str, Any],
           params: Dict[str, Any], body: Dict[str, Any],
           event: Dict[str, Any], origin: str, request_id: str) -> Dict[str, Any]:
    actor = _actor(event)

    if '/crm/pipelines' in path:
        if method == 'GET':
            return _pipelines(origin)
        return cors_response(405, {'error': 'GET only'}, origin)

    if '/crm/contacts/' in path and path.rstrip('/').endswith('/360'):
        if method == 'GET':
            return _contact_360(path_params, params, origin)
        return cors_response(405, {'error': 'GET only'}, origin)

    if '/crm/leads' in path:
        lead_id = path_params.get('leadId') or ''
        if path.rstrip('/').endswith('/convert'):
            if method != 'POST':
                return cors_response(405, {'error': 'POST only'}, origin)
            return _convert(lead_id, body, actor, origin)
        if lead_id:
            if method == 'GET':
                return _lead(lead_id, origin)
            if method == 'PATCH':
                return _transition(lead_id, body, actor, origin)
            return cors_response(405, {'error': 'GET or PATCH'}, origin)
        if method == 'GET':
            return _leads(params, origin)
        if method == 'POST':
            return _capture(body, actor, origin, request_id)
        return cors_response(405, {'error': 'GET or POST'}, origin)

    if '/crm/opportunities' in path:
        opportunity_id = path_params.get('opportunityId') or ''
        if opportunity_id:
            if method == 'GET':
                return _opportunity(opportunity_id, origin)
            if method == 'PATCH':
                return _move(opportunity_id, body, actor, origin)
            return cors_response(405, {'error': 'GET or PATCH'}, origin)
        if method == 'GET':
            return _opportunities(params, origin)
        return cors_response(405, {'error': 'GET only'}, origin)

    if '/crm/activities' in path:
        if method == 'GET':
            return _activities(params, origin)
        if method == 'POST':
            return _log_activity(body, actor, origin)
        return cors_response(405, {'error': 'GET or POST'}, origin)

    return cors_response(404, {'error': f'Unknown CRM path: {path}'}, origin)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def _pipelines(origin: str) -> Dict[str, Any]:
    """The board configuration: the default pipeline and its stages, in display order."""
    pipeline = crm_store.default_pipeline()
    if not pipeline:
        # Not a 500: the domain is provisioned by a script, and saying so is more useful than
        # an opaque error.
        return cors_response(503, {
            'error': 'No default pipeline',
            'detail': 'run scripts/provision_crm_domain.py, then '
                      'crm.service.ensure_default_pipeline()',
        }, origin)
    stages = crm_store.list_stages(str(pipeline['pipelineId']))
    return cors_response(200, _json_safe({
        'pipeline': pipeline,
        'stages': stages,
        'stageKinds': list(crm_states.STAGE_KINDS),
        'leadStates': list(crm_states.LEAD_STATES),
        'opportunityOutcomes': list(crm_states.OPPORTUNITY_STATES),
        'activityKinds': [k for k in crm_states.ACTIVITY_KINDS
                          if crm_states.activity_kind_is_user_writable(k)],
    }), origin)


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

def _leads(params: Dict[str, Any], origin: str) -> Dict[str, Any]:
    """The work queue: leads in one state, or one contact's leads.

    A state or a contact is required. Without one the only implementation is a scan, and a
    scan behind a list endpoint is how a read path quietly becomes the largest line on the
    bill.
    """
    state = str(params.get('state') or '').strip().upper()
    contact = str(params.get('contactId') or '').strip()
    limit = _limit(params)

    if contact:
        resolved = contact_key.resolve(contact_id=contact)
        return cors_response(200, _json_safe({
            'leads': crm_store.leads_for_contact(resolved, limit=limit),
            'contactId': resolved,
        }), origin)

    if not state:
        return cors_response(400, {
            'error': 'state or contactId is required',
            'detail': 'listing every lead would require a table scan',
            'leadStates': list(crm_states.LEAD_STATES),
        }, origin)
    if state not in crm_states.LEAD_STATES:
        return cors_response(400, {'error': f'unknown lead state {state}',
                                   'leadStates': list(crm_states.LEAD_STATES)}, origin)
    return cors_response(200, _json_safe({
        'leads': crm_store.leads_by_state(state, limit=limit), 'state': state,
    }), origin)


def _lead(lead_id: str, origin: str) -> Dict[str, Any]:
    if not crm_keys.looks_like(crm_keys.LEAD_PREFIX, lead_id):
        return cors_response(400, {'error': 'not a lead id'}, origin)
    lead = crm_store.get_lead(lead_id)
    if not lead:
        return cors_response(404, {'error': 'Lead not found'}, origin)
    return cors_response(200, _json_safe({
        'lead': lead,
        'timeline': crm_store.timeline(lead_id=lead_id, limit=DEFAULT_LIMIT),
    }), origin)


def _capture(body: Dict[str, Any], actor: str, origin: str,
             request_id: str) -> Dict[str, Any]:
    """Capture a lead from the dashboard.

    The source is forced to `MANUAL`, not taken from the body. Letting a caller declare
    `WHATSAPP_INBOUND` would mint a VERIFIED-trust provenance claim for a hand-typed value -
    see `identity.provenance` - and would also make the lead id deterministic on a
    caller-chosen reference, so two operators could collide.
    """
    contact = str(body.get('contactId') or '').strip()
    if not contact:
        return cors_response(400, {'error': 'contactId is required'}, origin)
    resolved = contact_key.resolve(contact_id=contact)

    result = crm_service.capture_lead(
        contact_id=resolved,
        source=crm_keys.SOURCE_MANUAL,
        pipeline_id=str(body.get('pipelineId') or '') or None,
        attach_to_open_lead=bool(body.get('attachToOpenLead')),
        actor=actor,
        subject=str(body.get('subject') or '') or None,
        detail=str(body.get('detail') or '') or None,
        phone=str(body.get('phone') or '') or None,
        name=str(body.get('name') or '') or None,
        email=str(body.get('email') or '') or None,
        owner=str(body.get('ownerId') or '') or actor,
        channel=str(body.get('channel') or '') or None,
        campaign=str(body.get('campaign') or '') or None,
        amount_paise=_paise_or_none(body.get('amountPaise')),
    )
    status = 201 if result['outcome'] == 'created' else 200
    return cors_response(status, _json_safe(result), origin)


def _transition(lead_id: str, body: Dict[str, Any], actor: str,
                origin: str) -> Dict[str, Any]:
    state = str(body.get('state') or '').strip().upper()
    if not state:
        return cors_response(400, {'error': 'state is required',
                                   'leadStates': list(crm_states.LEAD_STATES)}, origin)
    result = crm_service.transition_lead(
        lead_id=lead_id, new_state=state, actor=actor,
        reason=str(body.get('reason') or '') or None,
        expected_state=str(body.get('expectedState') or '') or None,
    )
    if result['outcome'] == 'refused':
        # 409, not 400: the request was well formed and the state moved underneath it. A
        # client should re-read and retry, which is a different action from fixing a payload.
        return cors_response(409, _json_safe(result), origin)
    return cors_response(200, _json_safe(result), origin)


def _convert(lead_id: str, body: Dict[str, Any], actor: str,
             origin: str) -> Dict[str, Any]:
    result = crm_service.convert_lead(
        lead_id=lead_id,
        title=str(body.get('title') or '') or None,
        amount_paise=_paise_or_none(body.get('amountPaise')),
        stage_id=str(body.get('stageId') or '') or None,
        owner=str(body.get('ownerId') or '') or actor,
        expected_close_at=_int_or_none(body.get('expectedCloseAt')),
        actor=actor,
    )
    outcome = result['outcome']
    if outcome == 'converted':
        return cors_response(201, _json_safe(result), origin)
    if outcome == 'already_converted':
        # 200 with the existing opportunity. A repeated convert is not an error - it is the
        # idempotent answer, and the caller wants the opportunity either way.
        return cors_response(200, _json_safe(result), origin)
    return cors_response(409, _json_safe(result), origin)


# ---------------------------------------------------------------------------
# Opportunities
# ---------------------------------------------------------------------------

def _opportunities(params: Dict[str, Any], origin: str) -> Dict[str, Any]:
    stage_id = str(params.get('stageId') or '').strip()
    contact = str(params.get('contactId') or '').strip()
    limit = _limit(params)

    if contact:
        resolved = contact_key.resolve(contact_id=contact)
        return cors_response(200, _json_safe({
            'opportunities': crm_store.opportunities_for_contact(resolved, limit=limit),
            'contactId': resolved,
        }), origin)
    if not stage_id:
        return cors_response(400, {
            'error': 'stageId or contactId is required',
            'detail': 'a board renders one column per stage; listing every opportunity '
                      'would require a table scan',
        }, origin)
    return cors_response(200, _json_safe({
        'opportunities': crm_store.opportunities_in_stage(stage_id, limit=limit),
        'stageId': stage_id,
    }), origin)


def _opportunity(opportunity_id: str, origin: str) -> Dict[str, Any]:
    if not crm_keys.looks_like(crm_keys.OPPORTUNITY_PREFIX, opportunity_id):
        return cors_response(400, {'error': 'not an opportunity id'}, origin)
    opportunity = crm_store.get_opportunity(opportunity_id)
    if not opportunity:
        return cors_response(404, {'error': 'Opportunity not found'}, origin)
    return cors_response(200, _json_safe({
        'opportunity': opportunity,
        'timeline': crm_store.timeline(opportunity_id=opportunity_id,
                                      limit=DEFAULT_LIMIT),
    }), origin)


def _move(opportunity_id: str, body: Dict[str, Any], actor: str,
          origin: str) -> Dict[str, Any]:
    stage_id = str(body.get('stageId') or '').strip()
    if not stage_id:
        return cors_response(400, {'error': 'stageId is required'}, origin)
    result = crm_service.move_opportunity(
        opportunity_id=opportunity_id, stage_id=stage_id,
        reopen=bool(body.get('reopen')),
        close_reason=str(body.get('closeReason') or '') or None,
        actor=actor,
    )
    if result['outcome'] == 'refused':
        return cors_response(409, _json_safe(result), origin)
    return cors_response(200, _json_safe(result), origin)


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------

def _activities(params: Dict[str, Any], origin: str) -> Dict[str, Any]:
    subjects = {
        'contact_id': str(params.get('contactId') or '').strip() or None,
        'lead_id': str(params.get('leadId') or '').strip() or None,
        'opportunity_id': str(params.get('opportunityId') or '').strip() or None,
    }
    provided = {k: v for k, v in subjects.items() if v}
    if len(provided) != 1:
        return cors_response(400, {
            'error': 'exactly one of contactId, leadId or opportunityId is required',
            'detail': 'a combined timeline needs a merge across three indexes with its own '
                      'ordering rules; answering with one of them would look complete',
        }, origin)
    if 'contact_id' in provided:
        provided['contact_id'] = contact_key.resolve(contact_id=provided['contact_id'])
    return cors_response(200, _json_safe({
        'activities': crm_store.timeline(limit=_limit(params), **provided),
    }), origin)


def _log_activity(body: Dict[str, Any], actor: str, origin: str) -> Dict[str, Any]:
    kind = str(body.get('kind') or '').strip().upper()
    if not crm_states.activity_kind_is_user_writable(kind):
        # STAGE_CHANGE / STATE_CHANGE / SYSTEM are written by the service only. A
        # user-supplied one could claim a transition that never happened.
        return cors_response(400, {
            'error': f'{kind or "kind"} is not a user-writable activity kind',
            'activityKinds': [k for k in crm_states.ACTIVITY_KINDS
                              if crm_states.activity_kind_is_user_writable(k)],
        }, origin)

    contact = str(body.get('contactId') or '').strip()
    result = crm_service.log_activity(
        kind=kind,
        contact_id=contact_key.resolve(contact_id=contact) if contact else None,
        lead_id=str(body.get('leadId') or '') or None,
        opportunity_id=str(body.get('opportunityId') or '') or None,
        actor=actor,
        summary=str(body.get('summary') or '') or None,
        body=str(body.get('body') or '') or None,
        channel=str(body.get('channel') or '') or None,
        reference=str(body.get('reference') or '') or None,
        due_at=_int_or_none(body.get('dueAt')),
    )
    return cors_response(201, _json_safe(result), origin)


# ---------------------------------------------------------------------------
# Contact 360
# ---------------------------------------------------------------------------

def _contact_360(path_params: Dict[str, Any], params: Dict[str, Any],
                 origin: str) -> Dict[str, Any]:
    """Everything the platform knows about one contact, in one vocabulary.

    Five queries, no scan: the contact row, its leads, its opportunities, its timeline, and
    its payments. Payment state is normalised through `payment_status.canonical` because the
    four tables that carry it spell the same state differently and Phase 4d deliberately left
    the stored values alone rather than migrating them.
    """
    raw = str(path_params.get('contactId') or '').strip()
    if not raw:
        return cors_response(400, {'error': 'contactId is required'}, origin)
    resolved = contact_key.resolve(contact_id=raw)
    limit = _limit(params)

    contact = None
    try:
        contact = dynamodb.Table(CONTACTS_TABLE).get_item(
            Key=contact_key.key(resolved)).get('Item')
    except Exception as exc:  # noqa: BLE001 - a missing contact must not fail the whole view
        logger.warning(json.dumps({'event': 'contact_360_contact_read_failed',
                                   'error': str(exc)[:200]}))

    if contact:
        try:
            contact_key.assert_consistent(contact)
        except contact_key.ContactKeyMismatch as exc:
            logger.warning(json.dumps({'event': 'contact_key_mismatch',
                                       'source': 'crm._contact_360',
                                       'reason': str(exc)}))

    crm_view = crm_service.contact_360(contact_id=resolved, limit=limit)

    return cors_response(200, _json_safe({
        'contactId': resolved,
        'contact': contact,
        'leads': crm_view['leads'],
        'opportunities': crm_view['opportunities'],
        'activities': crm_view['activities'],
        'payments': _payments_for_contact(resolved, limit),
        'identity': _identity_summary(contact),
    }), origin)


def _payments_for_contact(contact_id: str, limit: int) -> Dict[str, Any]:
    """Payments and invoices for one contact, in one status vocabulary. No scan.

    Invoices are indexed on `contactId`. Payments are not - `PaymentsTable` carries only
    `orderId-index` and `paymentId-index` - so they are reached by `get_item` on the
    `paymentId` each invoice already stores. Its partition key IS the Razorpay payment id.

    An invoice with no `paymentId` is simply reported without one. The alternative was a
    filtered scan on `referenceId`, which is unindexed: that turns one contact view into a
    full-table read per invoice, and adding a contact index to PaymentsTable would be paying
    to store a second copy of a link the invoice already holds.
    """
    invoices: List[Dict[str, Any]] = []
    try:
        response = dynamodb.Table(INVOICES_TABLE).query(
            IndexName='contactId-index',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('contactId').eq(contact_id),
            Limit=limit,
        )
        invoices = list(response.get('Items', []))
    except Exception as exc:  # noqa: BLE001
        logger.warning(json.dumps({'event': 'contact_360_invoices_failed',
                                   'error': str(exc)[:200]}))

    normalised_invoices = []
    for invoice in invoices:
        normalised_invoices.append({
            'invoiceId': invoice.get('invoiceId', ''),
            'invoiceNumber': invoice.get('invoiceNumber', ''),
            'referenceId': invoice.get('referenceId', ''),
            'documentStatus': invoice.get('status', ''),
            # One vocabulary. `paid` in InvoicesTable and `captured` in PaymentsTable are the
            # same state; `canonical` maps both onto the payment_status ladder.
            'paymentState': payment_status.canonical(invoice.get('paymentStatus')),
            'paymentStateRaw': invoice.get('paymentStatus', ''),
            'totalRupees': str(invoice.get('total', '0')),
            'currency': invoice.get('currency', 'INR'),
            'createdAt': invoice.get('createdAt', 0),
            'paidAt': invoice.get('paidAt', 0),
        })

    payments = []
    payments_table = dynamodb.Table(PAYMENTS_TABLE)
    seen: set = set()
    for invoice in invoices[:limit]:
        payment_id = str(invoice.get('paymentId') or '').strip()
        if not payment_id or payment_id in seen:
            continue
        seen.add(payment_id)
        try:
            # `id` is the partition key and it is the Razorpay payment id - see
            # razorpay-webhook._store_payment_record.
            item = payments_table.get_item(Key={'id': payment_id}).get('Item')
        except Exception as exc:  # noqa: BLE001 - one unreadable payment must not blank the view
            logger.warning(json.dumps({'event': 'contact_360_payment_read_failed',
                                       'error': str(exc)[:200]}))
            continue
        if not item:
            continue
        try:
            amount_paise = payment_status.paise(item.get('amount', 0))
        except ValueError:
            amount_paise = 0
        payments.append({
            'paymentId': item.get('paymentId', '') or payment_id,
            'referenceId': item.get('referenceId', ''),
            'state': payment_status.canonical(item.get('status')),
            'stateRaw': item.get('status', ''),
            'amountPaise': amount_paise,
            'amountRupees': payment_status.rupees_str(amount_paise),
            'method': item.get('method', ''),
            'createdAt': item.get('createdAt', 0),
        })

    captured = [p for p in payments if p['state'] == payment_status.CAPTURED]
    return {
        'invoices': normalised_invoices,
        'payments': payments,
        'capturedTotalPaise': sum(p['amountPaise'] for p in captured),
        'note': ('payment state is normalised through payment_status.canonical; the four '
                 'tables that store it use five different vocabularies'),
    }


def _identity_summary(contact: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Field provenance for the contact, with no field values.

    Answers "which of these fields do we actually have proof of?" - the question the manual
    review surface is built around. See `identity.provenance`.
    """
    try:
        from lambda_utils.identity import provenance
        return provenance.describe(contact)
    except Exception:  # noqa: BLE001
        return {}


# ---------------------------------------------------------------------------
# Coercion
# ---------------------------------------------------------------------------

def _paise_or_none(value: Any) -> Optional[int]:
    """Integer paise, or None. Refuses a float rather than truncating it.

    A caller sending `2500.5` paise means something we cannot represent, and silently
    flooring it would record a different amount than the one they sent.
    """
    if value in (None, ''):
        return None
    if isinstance(value, float) and not value.is_integer():
        raise ValueError('amountPaise must be an integer number of paise')
    return payment_status.paise(value)


def _int_or_none(value: Any) -> Optional[int]:
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError(f'not an integer: {value!r}')
