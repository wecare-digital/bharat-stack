"""Tests for WhatsApp Business API Lambda handler."""
import json
import hmac
import hashlib
import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'whatsapp-business-api'))


class TestWebhookSignatureVerification:
    """Test X-Hub-Signature-256 on business API handler."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'whatsapp-business-api'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}):
            with patch('boto3.resource'), patch('boto3.client'):
                from handler import _verify_webhook_signature
                self.verify = _verify_webhook_signature

    def test_missing_signature_returns_false(self):
        event = {'headers': {}, 'body': '{}'}
        assert self.verify(event, 'req-1') is False

    def test_valid_signature(self):
        secret = 'app_secret_123'
        body = '{"encrypted_flow_data":"abc"}'
        sig = 'sha256=' + hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        event = {'headers': {'x-hub-signature-256': sig}, 'body': body}
        with patch('handler._get_app_secret', return_value=secret):
            assert self.verify(event, 'req-2') is True

    def test_invalid_signature(self):
        event = {'headers': {'x-hub-signature-256': 'sha256=wrong'}, 'body': '{"test":1}'}
        with patch('handler._get_app_secret', return_value='real_secret'):
            assert self.verify(event, 'req-3') is False

    def test_no_secret_fails_open(self):
        event = {'headers': {'x-hub-signature-256': 'sha256=anything'}, 'body': '{}'}
        with patch('handler._get_app_secret', return_value=''):
            assert self.verify(event, 'req-4') is True


class TestBusinessProfile:
    """Test business profile CRUD."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'whatsapp-business-api'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}):
            with patch('boto3.resource'), patch('boto3.client'):
                from handler import _get_business_profile, _update_business_profile
                self.get_profile = _get_business_profile
                self.update_profile = _update_business_profile

    def test_get_profile(self):
        with patch('handler._graph_api', return_value={'data': [{'about': 'Test', 'description': 'Desc'}]}):
            result = self.get_profile('1016149501586345')
            body = json.loads(result['body'])
            assert body['profile']['about'] == 'Test'

    def test_update_profile_empty_payload(self):
        result = self.update_profile('1016149501586345', {})
        assert result['statusCode'] == 400

    def test_update_profile_valid(self):
        with patch('handler._graph_api', return_value={'success': True}):
            result = self.update_profile('1016149501586345', {'about': 'Updated'})
            assert result['statusCode'] == 200


class TestFlows:
    """Test WhatsApp Flows CRUD."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'whatsapp-business-api'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}):
            with patch('boto3.resource'), patch('boto3.client'):
                from handler import _list_flows, _create_flow, _publish_flow, _delete_flow
                self.list_flows = _list_flows
                self.create_flow = _create_flow
                self.publish_flow = _publish_flow
                self.delete_flow = _delete_flow

    def test_list_flows_requires_waba(self):
        result = self.list_flows('')
        assert result['statusCode'] == 400

    def test_list_flows_success(self):
        with patch('handler._graph_api', return_value={'data': [{'id': 'f1', 'name': 'Flow 1'}]}):
            result = self.list_flows('2094615664435155')
            body = json.loads(result['body'])
            assert len(body['flows']) == 1

    def test_create_flow_requires_name(self):
        result = self.create_flow('2094615664435155', {})
        assert result['statusCode'] == 400

    def test_publish_flow_requires_id(self):
        result = self.publish_flow('')
        assert result['statusCode'] == 400

    def test_delete_flow_requires_id(self):
        result = self.delete_flow('')
        assert result['statusCode'] == 400


class TestGroups:
    """Test WhatsApp Groups CRUD."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'whatsapp-business-api'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}):
            with patch('boto3.resource'), patch('boto3.client'):
                from handler import _create_group, _send_group_message
                self.create_group = _create_group
                self.send_group = _send_group_message

    def test_create_group_requires_phone(self):
        result = self.create_group('', {'subject': 'Test'})
        assert result['statusCode'] == 400

    def test_create_group_requires_subject(self):
        result = self.create_group('1016149501586345', {})
        assert result['statusCode'] == 400

    def test_send_group_message_requires_content(self):
        result = self.send_group('1016149501586345', 'group-1', {})
        assert result['statusCode'] == 400


class TestPaymentConfig:
    """Test payment configuration endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'whatsapp-business-api'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}):
            with patch('boto3.resource'), patch('boto3.client'):
                from handler import _get_payment_config, _check_payment_gateway
                self.get_config = _get_payment_config
                self.check_gateway = _check_payment_gateway

    def test_get_payment_config_phone1(self):
        result = self.get_config('1016149501586345')
        body = json.loads(result['body'])
        assert body['paymentConfig'] is not None
        assert body['paymentConfig']['mcc'] == '4722'

    def test_get_payment_config_unknown_phone(self):
        with patch('handler._graph_api', return_value={'error': 'not found'}):
            result = self.get_config('unknown-phone')
            assert result['statusCode'] == 200

    def test_check_gateway(self):
        with patch('handler._graph_api', return_value={'data': []}):
            result = self.check_gateway('2094615664435155')
            body = json.loads(result['body'])
            assert 'gatewayChecks' in body


class TestAssignedUsers:
    """Test WABA assigned users CRUD (GET/POST/DELETE /{WABA-ID}/assigned_users)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'whatsapp-business-api'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}):
            with patch('boto3.resource'), patch('boto3.client'):
                from handler import _list_assigned_users, _add_assigned_user, _remove_assigned_user
                self.list_users = _list_assigned_users
                self.add_user = _add_assigned_user
                self.remove_user = _remove_assigned_user

    def test_list_requires_business_param(self):
        result = self.list_users('2094615664435155', {})
        assert result['statusCode'] == 400
        assert 'business' in json.loads(result['body'])['error']

    def test_list_success(self):
        with patch('handler._graph_api', return_value={
            'data': [{'id': '123', 'name': 'Test User'}],
            'paging': {'cursors': {'after': 'abc'}},
            'summary': {'total_count': 1},
        }):
            result = self.list_users('2094615664435155', {'business': '999'})
            body = json.loads(result['body'])
            assert len(body['users']) == 1
            assert body['users'][0]['name'] == 'Test User'
            assert body['summary']['total_count'] == 1

    def test_add_requires_user(self):
        result = self.add_user('2094615664435155', {'tasks': ['MANAGE']})
        assert result['statusCode'] == 400

    def test_add_requires_tasks(self):
        result = self.add_user('2094615664435155', {'user': '123'})
        assert result['statusCode'] == 400

    def test_add_success(self):
        with patch('handler._graph_api', return_value={'success': True}):
            result = self.add_user('2094615664435155', {'user': '123', 'tasks': ['MANAGE', 'DEVELOP']})
            body = json.loads(result['body'])
            assert body['success'] is True

    def test_remove_requires_user(self):
        result = self.remove_user('2094615664435155', {})
        assert result['statusCode'] == 400

    def test_remove_success(self):
        with patch('handler._graph_api', return_value={'success': True}):
            result = self.remove_user('2094615664435155', {'user': '123'})
            body = json.loads(result['body'])
            assert body['success'] is True


class TestBotDetails:
    """Test WABA Bot details endpoint (GET /{WABA-Bot-ID})."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'whatsapp-business-api'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}):
            with patch('boto3.resource'), patch('boto3.client'):
                from handler import _get_bot_details
                self.get_bot = _get_bot_details

    def test_requires_bot_id(self):
        result = self.get_bot('', {})
        assert result['statusCode'] == 400

    def test_success(self):
        with patch('handler._graph_api', return_value={
            'id': 'bot-123',
            'prompts': ['Hello!', 'How can I help?'],
            'commands': [{'command_name': '/help', 'command_description': 'Get help'}],
            'enable_welcome_message': True,
        }):
            result = self.get_bot('bot-123', {})
            body = json.loads(result['body'])
            assert body['bot']['id'] == 'bot-123'
            assert len(body['bot']['prompts']) == 2
            assert body['bot']['enable_welcome_message'] is True

    def test_custom_fields(self):
        with patch('handler._graph_api', return_value={'id': 'bot-123', 'commands': []}) as mock_api:
            self.get_bot('bot-123', {'fields': 'id,commands'})
            call_args = mock_api.call_args
            assert 'id,commands' in str(call_args)


class TestWebhookSubscribeOverride:
    """Test webhook subscribe with override_callback_uri and verify_token."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'whatsapp-business-api'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}):
            with patch('boto3.resource'), patch('boto3.client'):
                from handler import _subscribe_webhook
                self.subscribe = _subscribe_webhook

    def test_subscribe_with_override(self):
        with patch('handler._graph_api', return_value={'success': True}) as mock_api:
            result = self.subscribe('2094615664435155', {
                'override_callback_uri': 'https://example.com/webhook',
                'verify_token': 'my_token',
            })
            body = json.loads(result['body'])
            assert body['success'] is True
            payload = mock_api.call_args[1].get('payload') or mock_api.call_args[0][2] if len(mock_api.call_args[0]) > 2 else mock_api.call_args[1].get('payload')
            assert payload['override_callback_uri'] == 'https://example.com/webhook'
            assert payload['verify_token'] == 'my_token'

    def test_subscribe_without_override(self):
        with patch('handler._graph_api', return_value={'success': True}) as mock_api:
            self.subscribe('2094615664435155', {})
            # Should pass None payload when no overrides
            call_kwargs = mock_api.call_args
            payload = call_kwargs[1].get('payload') if call_kwargs[1] else None
            assert payload is None
