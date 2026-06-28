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


class TestTemplateTTL:
    """Test template TTL routes (rules / validate / update)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'whatsapp-business-api'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}):
            with patch('boto3.resource'), patch('boto3.client'):
                from handler import _get_ttl_rules, _validate_template_ttl_route, _update_template_ttl
                self.get_rules = _get_ttl_rules
                self.validate_route = _validate_template_ttl_route
                self.update_ttl = _update_template_ttl

    def test_rules_returns_categories(self):
        result = self.get_rules()
        assert result['statusCode'] == 200
        body = json.loads(result['body'])
        assert 'AUTHENTICATION' in body['rules']['categories']

    def test_validate_requires_category(self):
        result = self.validate_route({'ttl': 600})
        assert result['statusCode'] == 400

    def test_validate_ok(self):
        result = self.validate_route({'category': 'AUTHENTICATION', 'ttl': 600})
        body = json.loads(result['body'])
        assert result['statusCode'] == 200
        assert body['ok'] is True

    def test_validate_out_of_range(self):
        result = self.validate_route({'category': 'AUTHENTICATION', 'ttl': 5000})
        body = json.loads(result['body'])
        assert body['ok'] is False

    def test_update_ttl_requires_id(self):
        result = self.update_ttl('', {'ttl': 600})
        assert result['statusCode'] == 400

    def test_update_ttl_requires_ttl(self):
        result = self.update_ttl('tmpl-1', {})
        assert result['statusCode'] == 400

    def test_update_ttl_validates_against_live_category(self):
        # Live template is AUTHENTICATION; 5000 is out of range -> 400, no POST attempted
        with patch('handler._graph_api', return_value={'name': 't', 'category': 'AUTHENTICATION'}):
            result = self.update_ttl('tmpl-1', {'ttl': 5000})
            assert result['statusCode'] == 400

    def test_update_ttl_success(self):
        calls = []

        def fake_graph(endpoint, method='GET', payload=None, params=None, **kw):
            calls.append(method)
            if method == 'GET':
                return {'name': 't', 'category': 'UTILITY'}
            return {'success': True}

        with patch('handler._graph_api', side_effect=fake_graph):
            result = self.update_ttl('tmpl-1', {'ttl': 600})
            body = json.loads(result['body'])
            assert result['statusCode'] == 200
            assert body['success'] is True
            assert body['ttl'] == 600
            assert 'POST' in calls


class TestMedia:
    """Test /wa-business/media routes (upload / get / delete / resumable)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'whatsapp-business-api'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}):
            with patch('boto3.resource'), patch('boto3.client'):
                import handler as h
                self.h = h

    def test_validate_media_rejects_bad_mime(self):
        assert self.h._validate_media('application/x-evil', 10) is not None

    def test_validate_media_size_limit(self):
        # image limit is 5MB
        assert self.h._validate_media('image/png', 6 * 1024 * 1024) is not None
        assert self.h._validate_media('image/png', 1024) is None

    def test_mask_media_url(self):
        masked = self.h._mask_media_url('https://lookaside.fbsbx.com/abc?token=secret')
        assert 'secret' not in masked
        assert masked.startswith('https://lookaside.fbsbx.com/abc')

    def test_upload_media_requires_source(self):
        res = self.h._upload_media({'phoneId': '123'})
        assert res['statusCode'] == 400

    def test_upload_media_success(self):
        import base64 as b64
        data = b64.b64encode(b'hello').decode()
        with patch.object(self.h, '_graph_media_multipart', return_value={'id': 'media-1'}):
            res = self.h._upload_media({'phoneId': '123', 'fileData': data, 'contentType': 'image/png', 'filename': 'a.png'})
            body = json.loads(res['body'])
            assert res['statusCode'] == 200
            assert body['mediaId'] == 'media-1'

    def test_get_media_masks_url_and_sets_expiry(self):
        with patch.object(self.h, '_graph_api', return_value={'url': 'https://x/y?token=abc', 'mime_type': 'image/png', 'file_size': 10}):
            res = self.h._get_media('media-1', '123', {})
            body = json.loads(res['body'])
            assert res['statusCode'] == 200
            assert 'token=abc' not in body['url']
            assert body['urlExpiresInSeconds'] == self.h.MEDIA_URL_TTL_SECONDS

    def test_delete_media_requires_id(self):
        res = self.h._delete_media('', '123')
        assert res['statusCode'] == 400

    def test_resumable_session_requires_length(self):
        res = self.h._resumable_session({'fileType': 'image/png'})
        assert res['statusCode'] == 400

    def test_resumable_session_validates_mime(self):
        res = self.h._resumable_session({'fileType': 'application/x-evil', 'fileLength': 100})
        assert res['statusCode'] == 400

    def test_resumable_session_ok(self):
        with patch.object(self.h.s3_client, 'put_object', return_value={}):
            res = self.h._resumable_session({'fileType': 'image/png', 'fileLength': 100, 'fileName': 'a.png'})
            body = json.loads(res['body'])
            assert res['statusCode'] == 200
            assert 'sessionId' in body

    def test_resumable_chunk_unknown_session(self):
        with patch.object(self.h, '_resumable_load_manifest', return_value=None):
            res = self.h._resumable_chunk('nope', {'data': 'AA=='})
            assert res['statusCode'] == 404

    def test_resumable_finish_incomplete(self):
        manifest = {'sessionId': 's1', 'fileName': 'a.png', 'fileType': 'image/png', 'fileLength': 100, 'received': 50}
        with patch.object(self.h, '_resumable_load_manifest', return_value=manifest):
            res = self.h._resumable_finish('s1', {})
            assert res['statusCode'] == 400


class TestFlowAdmin:
    """Test flow assets / migrate / sync (Part 4 A)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'whatsapp-business-api'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}):
            with patch('boto3.resource'), patch('boto3.client'):
                import handler as h
                self.h = h

    def test_asset_requires_flow_id(self):
        assert self.h._upload_flow_asset('', {'flowJson': {'version': '7.0', 'screens': []}})['statusCode'] == 400

    def test_asset_rejects_bad_json(self):
        res = self.h._upload_flow_asset('f1', {'flowJson': '{not json'})
        assert res['statusCode'] == 400

    def test_asset_requires_flow_keys(self):
        res = self.h._upload_flow_asset('f1', {'flowJson': {'foo': 'bar'}})
        assert res['statusCode'] == 400

    def test_migrate_requires_wabas(self):
        assert self.h._migrate_flows({'sourceWabaId': 'a'})['statusCode'] == 400

    def test_migrate_success(self):
        with patch.object(self.h, '_graph_api', return_value={'migrated_flows': [{'id': '1'}], 'failed_flows': []}):
            res = self.h._migrate_flows({'sourceWabaId': 'a', 'destWabaId': 'b'})
            body = json.loads(res['body'])
            assert res['statusCode'] == 200
            assert len(body['migratedFlows']) == 1

    def test_sync_requires_waba(self):
        assert self.h._sync_flows({}, {})['statusCode'] == 400

    def test_sync_upserts(self):
        flows = {'data': [{'id': 'f1', 'name': 'Flow 1', 'status': 'PUBLISHED', 'categories': ['SIGN_UP']}]}
        fake_table = MagicMock()
        fake_table.get_item.return_value = {'Item': {}}
        with patch.object(self.h, '_graph_api', return_value=flows):
            with patch.object(self.h.dynamodb, 'Table', return_value=fake_table):
                res = self.h._sync_flows({'wabaId': 'w1'}, {})
                body = json.loads(res['body'])
                assert res['statusCode'] == 200
                assert body['synced'] == 1
                assert fake_table.put_item.called


class TestSendMessages:
    """Test /messages/send/* routes."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'whatsapp-business-api'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}):
            with patch('boto3.resource'), patch('boto3.client'):
                import handler as h
                self.h = h

    def _ok_send(self):
        return patch.object(self.h, '_graph_api', return_value={'messages': [{'id': 'wamid.1'}]})

    def test_text_requires_fields(self):
        assert self.h._send_text({'to': '919900000000'})['statusCode'] == 400

    def test_text_success(self):
        with self._ok_send():
            res = self.h._send_text({'to': '919900000000', 'text': 'hi'})
            assert json.loads(res['body'])['messageId'] == 'wamid.1'

    def test_template_requires_name(self):
        assert self.h._send_template_msg({'to': '919900000000'})['statusCode'] == 400

    def test_template_success(self):
        with self._ok_send():
            res = self.h._send_template_msg({'to': '919900000000', 'templateName': 'hello', 'language': 'en'})
            assert res['statusCode'] == 200

    def test_media_requires_valid_type(self):
        assert self.h._send_media_msg({'to': '919900000000', 'mediaType': 'bogus', 'mediaId': 'm1'})['statusCode'] == 400

    def test_media_requires_source(self):
        assert self.h._send_media_msg({'to': '919900000000', 'mediaType': 'image'})['statusCode'] == 400

    def test_media_success(self):
        with self._ok_send():
            res = self.h._send_media_msg({'to': '919900000000', 'mediaType': 'image', 'mediaId': 'm1', 'caption': 'c'})
            assert res['statusCode'] == 200

    def test_interactive_requires_object(self):
        assert self.h._send_interactive_msg({'to': '919900000000'})['statusCode'] == 400

    def test_flow_requires_flow_ref(self):
        assert self.h._send_flow_msg({'to': '919900000000'})['statusCode'] == 400

    def test_flow_by_id_success(self):
        with self._ok_send():
            res = self.h._send_flow_msg({'to': '919900000000', 'flowId': 'f1', 'screen': 'WELCOME'})
            assert res['statusCode'] == 200

    def test_flow_draft_mode(self):
        captured = {}

        def fake(endpoint, method='GET', payload=None, params=None, **kw):
            captured['payload'] = payload
            return {'messages': [{'id': 'x'}]}

        with patch.object(self.h, '_graph_api', side_effect=fake):
            self.h._send_flow_msg({'to': '919900000000', 'flowName': 'f', 'mode': 'draft'})
            params = captured['payload']['interactive']['action']['parameters']
            assert params['mode'] == 'draft'
            assert params['flow_name'] == 'f'

    def test_route_send_dispatch(self):
        with self._ok_send():
            res = self.h._route_send_message('/messages/send/text', {'to': '919900000000', 'text': 'hi'})
            assert res['statusCode'] == 200
        assert self.h._route_send_message('/messages/send/unknown', {})['statusCode'] == 404


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
        # Pilot uses the shared MetaGraphClient: MetaGraphClient().get(...)
        with patch('handler.MetaGraphClient') as MockClient:
            MockClient.return_value.get.return_value = {
                'id': 'bot-123',
                'prompts': ['Hello!', 'How can I help?'],
                'commands': [{'command_name': '/help', 'command_description': 'Get help'}],
                'enable_welcome_message': True,
            }
            MockClient.is_error.return_value = False
            result = self.get_bot('bot-123', {})
            body = json.loads(result['body'])
            assert body['bot']['id'] == 'bot-123'
            assert len(body['bot']['prompts']) == 2
            assert body['bot']['enable_welcome_message'] is True

    def test_custom_fields(self):
        with patch('handler.MetaGraphClient') as MockClient:
            MockClient.return_value.get.return_value = {'id': 'bot-123', 'commands': []}
            MockClient.is_error.return_value = False
            self.get_bot('bot-123', {'fields': 'id,commands'})
            call_args = MockClient.return_value.get.call_args
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
