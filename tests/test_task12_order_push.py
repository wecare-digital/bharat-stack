"""Focused Task 12 regression tests for order retries and push devices."""
import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / 'amplify' / 'functions' / 'shared'
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

from lambda_utils.comms import notify as notify_mod  # noqa: E402


def _sms_outcome(*, ok, provider_message_id='', error=''):
    """A comms.notify.NotificationResult, for patching the SMS seam.

    The order-notification SMS path goes through
    lambda_utils.comms.notify.send_notification_sms rather than a raw Lambda
    invoke, so these tests patch that function on its own module. It is imported
    inside the handler function body, so the patch resolves at call time.
    """
    return notify_mod.NotificationResult(
        queued=ok, provider_message_id=provider_message_id, error=error)


def load_handler(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    with patch('boto3.client'), patch('boto3.resource'):
        spec.loader.exec_module(module)
    return module


@pytest.fixture
def wix_handler():
    return load_handler(
        'task12_wix_store_handler',
        'amplify/functions/ecommerce/wix-store/handler.py',
    )


@pytest.fixture
def push_handler():
    return load_handler(
        'task12_push_handler',
        'amplify/functions/messaging/push-notifications/handler.py',
    )


def test_invoke_json_detects_outer_function_error(wix_handler):
    wix_handler.lambda_client = MagicMock()
    wix_handler.lambda_client.invoke.return_value = {
        'FunctionError': 'Unhandled',
        'Payload': io.BytesIO(b'{"errorMessage":"failed"}'),
    }
    with pytest.raises(RuntimeError, match='invocation failed'):
        wix_handler._invoke_json('provider-function', {'body': '{}'})


def test_order_retry_fails_closed_when_claim_storage_fails(wix_handler):
    event = {
        'body': json.dumps({'orderId': 'order-1', 'channel': 'sms'}),
        '_auth': {'username': 'admin-user'},
    }
    with patch.object(wix_handler, '_velo_request', return_value={
        'notifications': [{'orderId': 'order-1', 'phone': '919999999999'}],
    }), patch.object(wix_handler, 'claim_admin_action', side_effect=RuntimeError('storage down')), \
            patch.object(wix_handler, '_invoke_json') as invoke:
        response = wix_handler._retry_order_notification(event, 'req-1')
    assert response['statusCode'] == 503
    invoke.assert_not_called()


def test_order_retry_duplicate_does_not_send(wix_handler):
    event = {
        'body': json.dumps({'orderId': 'order-1', 'channel': 'whatsapp'}),
        '_auth': {'username': 'admin-user'},
    }
    with patch.object(wix_handler, '_velo_request', return_value={
        'notifications': [{'orderId': 'order-1', 'phone': '919999999999'}],
    }), patch.object(wix_handler, 'claim_admin_action', return_value=False), \
            patch.object(wix_handler, '_invoke_json') as invoke:
        response = wix_handler._retry_order_notification(event, 'req-2')
    assert response['statusCode'] == 409
    invoke.assert_not_called()


def test_order_retry_persists_provider_failure(wix_handler):
    event = {
        'body': json.dumps({'orderId': 'order-1', 'channel': 'sms'}),
        '_auth': {'username': 'admin-user'},
    }
    calls = []

    def velo(endpoint, params=None, method='GET', body=None):
        calls.append((endpoint, method, body))
        if endpoint == 'orderNotifications':
            return {'notifications': [{'orderId': 'order-1', 'phone': '919999999999'}]}
        return {'ok': True}

    with patch.object(wix_handler, '_velo_request', side_effect=velo), \
            patch.object(wix_handler, 'claim_admin_action', return_value=True), \
            patch.object(notify_mod, 'send_notification_sms',
                         return_value=_sms_outcome(ok=False, error='provider unavailable')):
        response = wix_handler._retry_order_notification(event, 'req-3')
    assert response['statusCode'] == 502
    status_updates = [body for endpoint, method, body in calls if endpoint == 'orderNotificationStatus']
    assert status_updates and status_updates[0]['status'] == 'failed'
    assert status_updates[0]['actor'] == 'admin-user'


def test_sms_retry_uses_approved_dlt_contract(wix_handler):
    """The order retry names an APPROVED DLT template key, and nothing more.

    Rewritten 2026-09-19. This test previously asserted that the handler itself
    built the DLT payload - a raw dltTemplateId, entityId and sourceAddress -
    which is the duplication the shared DLT module removed. The contract is now
    stronger, not weaker: the caller may name a template KEY, and must NOT be
    able to assert a raw template id, entity or sender, because that would let it
    send unregistered content under our registered entity.
    """
    from lambda_utils.comms import dlt as dlt_mod

    event = {
        'body': json.dumps({'orderId': 'order-1', 'channel': 'sms'}),
        '_auth': {'username': 'admin-user'},
    }
    captured = {}

    def fake_send(phone, content, **kwargs):
        captured['phone'] = phone
        captured['content'] = content
        captured.update(kwargs)
        return _sms_outcome(ok=True, provider_message_id='message-1')

    with patch.object(wix_handler, '_velo_request', side_effect=[
        {'notifications': [{'orderId': 'order-1', 'wdOrderId': 'WD-1', 'phone': '919999999999'}]},
        {'ok': True},
    ]), patch.object(wix_handler, 'claim_admin_action', return_value=True), \
            patch.object(notify_mod, 'send_notification_sms', side_effect=fake_send):
        response = wix_handler._retry_order_notification(event, 'req-4')

    assert response['statusCode'] == 200
    # a template KEY, and one that is actually approved
    assert captured['dlt_template_key'] == 'wd_order'
    assert captured['dlt_template_key'] in dlt_mod.known_keys()
    # the regulatory identity is resolved centrally, never asserted by the caller
    for forbidden in ('dlt_template_id', 'entity_id', 'source_address', 'api_version'):
        assert forbidden not in captured
    # the retry is synchronous, because the provider message id is persisted
    assert captured['wait'] is True


def test_push_registration_uses_live_id_key(push_handler):
    push_handler.SNS_ANDROID_ARN = 'android-platform'
    push_handler.sns = MagicMock()
    push_handler.sns.create_platform_endpoint.return_value = {'EndpointArn': 'endpoint-1'}
    push_handler.table = MagicMock()
    response = push_handler.register_token(
        {'deviceToken': 'device-token', 'platform': 'android', 'userId': 'user-1'},
        {},
    )
    assert response['statusCode'] == 200
    item = push_handler.table.put_item.call_args.kwargs['Item']
    assert item['id'] != 'device-token'
    assert item['deviceToken'] == 'device-token'
    assert item['userId'] == 'user-1'


def test_push_user_target_uses_scan_not_missing_gsi(push_handler):
    push_handler.table = MagicMock()
    push_handler.table.scan.return_value = {'Items': []}
    response = push_handler.send_push(
        {'userId': 'user-1', 'title': 'Title', 'body': 'Body'},
        {},
    )
    assert response['statusCode'] == 404
    push_handler.table.scan.assert_called_once()
    push_handler.table.query.assert_not_called()


def test_push_devices_require_admin(push_handler):
    denied = {'statusCode': 403, 'body': '{}'}
    event = {
        'requestContext': {
            'apiId': 'api-1',
            'http': {'method': 'GET', 'path': '/push/devices', 'sourceIp': '127.0.0.1'},
        },
        'rawPath': '/push/devices',
    }
    with patch.object(push_handler, 'require_auth', return_value=denied) as require_auth:
        response = push_handler.handler(event, None)
    assert response is denied
    require_auth.assert_called_once_with(event, required_role='Admin')


def test_order_retry_reports_provider_success_when_status_persistence_fails(wix_handler):
    event = {
        'body': json.dumps({'orderId': 'order-1', 'channel': 'sms'}),
        '_auth': {'username': 'admin-user'},
    }
    with patch.object(wix_handler, '_velo_request', return_value={
        'notifications': [{'orderId': 'order-1', 'phone': '919999999999'}],
    }), patch.object(wix_handler, 'claim_admin_action', return_value=True), \
            patch.object(notify_mod, 'send_notification_sms',
                         return_value=_sms_outcome(
                             ok=True, provider_message_id='provider-message-1')), \
            patch.object(wix_handler, '_persist_order_retry',
                         side_effect=RuntimeError('storage down')):
        response = wix_handler._retry_order_notification(event, 'req-5')
    body = json.loads(response['body'])
    assert response['statusCode'] == 502
    assert body['messageSent'] is True
    assert body['providerMessageId'] == 'provider-message-1'
    assert 'do not retry yet' in body['error']
