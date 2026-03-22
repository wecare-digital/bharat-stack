"""Tests for WhatsApp Calling webhook handler."""
import json
import pytest
import hmac
import hashlib
import time
from unittest.mock import patch, MagicMock
from decimal import Decimal
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'whatsapp-calling'))


class TestWebhookSignatureVerification:
    """Test X-Hub-Signature-256 verification on calling webhooks."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'whatsapp-calling'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1', 'VERIFY_TOKEN': 'test_token'}):
            with patch('boto3.resource'), patch('boto3.client'):
                from handler import _verify_webhook_signature
                self.verify = _verify_webhook_signature

    def test_missing_signature_returns_false(self):
        event = {'headers': {}, 'body': '{}'}
        assert self.verify(event, 'req-1') is False

    def test_valid_signature_returns_true(self):
        secret = 'test_secret'
        body = '{"test": true}'
        sig = 'sha256=' + hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        event = {'headers': {'x-hub-signature-256': sig}, 'body': body}
        with patch('handler._token_cache', {'loaded': True, 'app_secret1': secret, 'app_secret2': ''}):
            assert self.verify(event, 'req-2') is True

    def test_invalid_signature_returns_false(self):
        event = {'headers': {'x-hub-signature-256': 'sha256=invalid'}, 'body': '{}'}
        with patch('handler._token_cache', {'loaded': True, 'app_secret1': 'real_secret', 'app_secret2': ''}):
            assert self.verify(event, 'req-3') is False

    def test_no_app_secret_fails_closed(self):
        """P0 Security: No app secrets configured → reject (never fail open)."""
        event = {'headers': {'x-hub-signature-256': 'sha256=anything'}, 'body': '{}'}
        with patch('handler._token_cache', {'loaded': True, 'app_secret1': '', 'app_secret2': ''}):
            assert self.verify(event, 'req-4') is False


class TestWebhookTimestampValidation:
    """Test replay protection via timestamp validation."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'whatsapp-calling'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}):
            with patch('boto3.resource'), patch('boto3.client'):
                from handler import _validate_webhook_timestamp
                self.validate = _validate_webhook_timestamp

    def test_recent_timestamp_valid(self):
        now = int(time.time())
        body = {'entry': [{'time': str(now - 10)}]}
        assert self.validate(body, 'req-1') is True

    def test_stale_timestamp_rejected(self):
        old = int(time.time()) - 600  # 10 minutes ago
        body = {'entry': [{'time': str(old)}]}
        assert self.validate(body, 'req-2') is False

    def test_no_timestamp_passes(self):
        body = {'entry': [{'changes': [{'value': {}}]}]}
        assert self.validate(body, 'req-3') is True

    def test_stale_call_timestamp_rejected(self):
        old = int(time.time()) - 400
        body = {'entry': [{'changes': [{'value': {'calls': [{'timestamp': str(old)}]}}]}]}
        assert self.validate(body, 'req-4') is False


class TestWebhookVerification:
    """Test GET webhook verification (hub.challenge)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'whatsapp-calling'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1', 'VERIFY_TOKEN': 'test_verify'}):
            with patch('boto3.resource'), patch('boto3.client'):
                # Force reload to pick up env var
                import importlib
                if 'handler' in sys.modules:
                    del sys.modules['handler']
                from handler import _verify_webhook
                self.verify_webhook = _verify_webhook

    def test_valid_verification(self):
        with patch('handler.VERIFY_TOKEN', 'test_verify'):
            params = {'hub.mode': 'subscribe', 'hub.verify_token': 'test_verify', 'hub.challenge': '12345'}
            result = self.verify_webhook(params, 'req-1')
            assert result['statusCode'] == 200
            assert result['body'] == '12345'

    def test_invalid_token(self):
        with patch('handler.VERIFY_TOKEN', 'test_verify'):
            params = {'hub.mode': 'subscribe', 'hub.verify_token': 'wrong', 'hub.challenge': '12345'}
            result = self.verify_webhook(params, 'req-2')
            assert result['statusCode'] == 403


class TestCallEventHandling:
    """Test call event processing."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'whatsapp-calling'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1', 'VERIFY_TOKEN': 'test'}):
            with patch('boto3.resource') as mock_res, patch('boto3.client'):
                self.mock_table = MagicMock()
                mock_res.return_value.Table.return_value = self.mock_table
                if 'handler' in sys.modules:
                    del sys.modules['handler']
                from handler import _handle_call_event
                self.handle_event = _handle_call_event

    def test_connect_event_stores_log(self):
        call = {
            'event': 'connect',
            'id': 'call-123',
            'from': '+919330994400',
            'to': '+919903300044',
            'direction': 'USER_INITIATED',
            'session': {'sdp': 'v=0\r\n...', 'sdp_type': 'offer'},
            'timestamp': str(int(time.time())),
        }
        metadata = {'phone_number_id': '960395407161423', 'display_phone_number': '919330994400'}
        with patch('handler._store_call_log') as mock_store:
            self.handle_event('waba-1', call, metadata, [], 'req-1')
            mock_store.assert_called_once()
            stored = mock_store.call_args[0][0]
            assert stored['callId'] == 'call-123'
            assert stored['status'] == 'ringing'

    def test_terminate_event_stores_log(self):
        call = {
            'event': 'terminate',
            'id': 'call-456',
            'from': '+919330994400',
            'reason': 'caller_hangup',
            'duration': 45,
            'timestamp': str(int(time.time())),
        }
        metadata = {'phone_number_id': '960395407161423'}
        with patch('handler._store_call_log') as mock_store, \
             patch('handler._send_post_call_reaction'):
            self.handle_event('waba-1', call, metadata, [], 'req-2')
            mock_store.assert_called_once()
            stored = mock_store.call_args[0][0]
            assert stored['status'] == 'ended'
            assert stored['duration'] == 45

    def test_permission_event(self):
        call = {
            'event': 'call_permission_status',
            'status': 'GRANTED',
            'from': '+919330994400',
            'timestamp': str(int(time.time())),
        }
        metadata = {'phone_number_id': '960395407161423'}
        with patch('handler._store_call_log') as mock_store:
            self.handle_event('waba-1', call, metadata, [], 'req-3')
            mock_store.assert_called_once()
            stored = mock_store.call_args[0][0]
            assert stored['permission'] == 'GRANTED'

    def test_bsuid_extraction_from_contacts(self):
        call = {
            'event': 'connect',
            'id': 'call-789',
            'from': '+919330994400',
            'direction': 'USER_INITIATED',
            'session': {'sdp': 'v=0\r\n'},
            'timestamp': str(int(time.time())),
        }
        contacts = [{'profile': {'name': 'Test User', 'username': '@testuser'}, 'user_id': 'IN.123456'}]
        metadata = {'phone_number_id': '960395407161423'}
        with patch('handler._store_call_log') as mock_store:
            self.handle_event('waba-1', call, metadata, contacts, 'req-4')
            stored = mock_store.call_args[0][0]
            assert stored['callerName'] == 'Test User'
            assert stored.get('callerUsername') == '@testuser'


class TestCredentialRouting:
    """Test that credentials are resolved correctly per phone_number_id."""

    @pytest.fixture(autouse=True)
    def setup(self):
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1', 'VERIFY_TOKEN': 'test'}):
            with patch('boto3.resource'), patch('boto3.client'):
                if 'handler' in sys.modules:
                    del sys.modules['handler']
                import handler
                self.handler = handler

    def test_waba1_uses_token1(self):
        """WABA1 phone (960395407161423) should resolve to token1."""
        with patch.object(self.handler, '_token_cache', {
            'loaded': True, 'token1': 'tok_waba1', 'token2': 'tok_waba2',
            'app_secret1': 'sec1', 'app_secret2': 'sec2',
        }):
            assert self.handler._get_meta_token('960395407161423') == 'tok_waba1'
            assert self.handler._get_app_secret('960395407161423') == 'sec1'

    def test_waba2_uses_token2(self):
        """WABA2 phone (997428863451102) should resolve to token2."""
        with patch.object(self.handler, '_token_cache', {
            'loaded': True, 'token1': 'tok_waba1', 'token2': 'tok_waba2',
            'app_secret1': 'sec1', 'app_secret2': 'sec2',
        }):
            assert self.handler._get_meta_token('997428863451102') == 'tok_waba2'
            assert self.handler._get_app_secret('997428863451102') == 'sec2'

    def test_waba2_id_uses_token2(self):
        """WABA2 ID (1633959101297902) should also resolve to token2."""
        with patch.object(self.handler, '_token_cache', {
            'loaded': True, 'token1': 'tok_waba1', 'token2': 'tok_waba2',
            'app_secret1': 'sec1', 'app_secret2': 'sec2',
        }):
            assert self.handler._get_meta_token('1633959101297902') == 'tok_waba2'

    def test_waba3_uses_token1(self):
        """WABA3 phone (945798751960485) should resolve to token1."""
        with patch.object(self.handler, '_token_cache', {
            'loaded': True, 'token1': 'tok_waba1', 'token2': 'tok_waba2',
            'app_secret1': 'sec1', 'app_secret2': 'sec2',
        }):
            assert self.handler._get_meta_token('945798751960485') == 'tok_waba1'
            assert self.handler._get_app_secret('945798751960485') == 'sec1'

    def test_unknown_phone_defaults_to_token1(self):
        """Unknown phone_number_id should default to token1."""
        with patch.object(self.handler, '_token_cache', {
            'loaded': True, 'token1': 'tok_waba1', 'token2': 'tok_waba2',
            'app_secret1': 'sec1', 'app_secret2': 'sec2',
        }):
            assert self.handler._get_meta_token('999999999') == 'tok_waba1'

    def test_none_phone_defaults_to_token1(self):
        """None phone_number_id should default to token1."""
        with patch.object(self.handler, '_token_cache', {
            'loaded': True, 'token1': 'tok_waba1', 'token2': 'tok_waba2',
            'app_secret1': 'sec1', 'app_secret2': 'sec2',
        }):
            assert self.handler._get_meta_token(None) == 'tok_waba1'


class TestMultiSecretWebhookVerification:
    """Test webhook signature verification with multiple app secrets."""

    @pytest.fixture(autouse=True)
    def setup(self):
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1', 'VERIFY_TOKEN': 'test'}):
            with patch('boto3.resource'), patch('boto3.client'):
                if 'handler' in sys.modules:
                    del sys.modules['handler']
                from handler import _verify_webhook_signature
                self.verify = _verify_webhook_signature

    def _sign(self, body: str, secret: str) -> str:
        return 'sha256=' + hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()

    def test_signature_matches_secret1(self):
        body = '{"object":"whatsapp_business_account"}'
        sig = self._sign(body, 'secret_app1')
        event = {'headers': {'x-hub-signature-256': sig}, 'body': body}
        with patch('handler._token_cache', {'loaded': True, 'app_secret1': 'secret_app1', 'app_secret2': 'secret_app2'}):
            assert self.verify(event, 'req-1') is True

    def test_signature_matches_secret2(self):
        body = '{"object":"whatsapp_business_account"}'
        sig = self._sign(body, 'secret_app2')
        event = {'headers': {'x-hub-signature-256': sig}, 'body': body}
        with patch('handler._token_cache', {'loaded': True, 'app_secret1': 'secret_app1', 'app_secret2': 'secret_app2'}):
            assert self.verify(event, 'req-2') is True

    def test_signature_matches_neither_secret(self):
        body = '{"object":"whatsapp_business_account"}'
        sig = self._sign(body, 'wrong_secret')
        event = {'headers': {'x-hub-signature-256': sig}, 'body': body}
        with patch('handler._token_cache', {'loaded': True, 'app_secret1': 'secret_app1', 'app_secret2': 'secret_app2'}):
            assert self.verify(event, 'req-3') is False

    def test_only_secret2_configured(self):
        body = '{"test": true}'
        sig = self._sign(body, 'only_secret2')
        event = {'headers': {'x-hub-signature-256': sig}, 'body': body}
        with patch('handler._token_cache', {'loaded': True, 'app_secret1': '', 'app_secret2': 'only_secret2'}):
            assert self.verify(event, 'req-4') is True

    def test_base64_encoded_body(self):
        import base64
        body = '{"object":"whatsapp_business_account"}'
        encoded = base64.b64encode(body.encode()).decode()
        sig = self._sign(body, 'test_secret')
        event = {'headers': {'x-hub-signature-256': sig}, 'body': encoded, 'isBase64Encoded': True}
        with patch('handler._token_cache', {'loaded': True, 'app_secret1': 'test_secret', 'app_secret2': ''}):
            assert self.verify(event, 'req-5') is True


class TestIVRAutoPickup:
    """Test IVR auto-pickup flow including EUM vs Direct API paths."""

    @pytest.fixture(autouse=True)
    def setup(self):
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1', 'VERIFY_TOKEN': 'test'}):
            with patch('boto3.resource'), patch('boto3.client'):
                if 'handler' in sys.modules:
                    del sys.modules['handler']
                import handler
                self.handler = handler

    def test_eum_phone_skips_pre_accept(self):
        """EUM-managed phones (WABA1/WABA2) should skip pre_accept and send IVR menu via EUM SDK."""
        with patch.object(self.handler, '_update_call_status') as mock_status, \
             patch.object(self.handler, '_send_ivr_menu') as mock_menu, \
             patch.object(self.handler, '_meta_api_call') as mock_api:
            self.handler._auto_pickup_and_play('call-1', '960395407161423', '+919876543210', 'sdp')
            # Should NOT call Meta API (pre_accept/terminate)
            mock_api.assert_not_called()
            # Should send IVR menu
            mock_menu.assert_called_once_with('960395407161423', '+919876543210', 'call-1')
            # Should set ivr_eum_mode then ivr_completed
            statuses = [c[0][1] for c in mock_status.call_args_list]
            assert 'ivr_eum_mode' in statuses
            assert 'ivr_completed' in statuses

    def test_direct_api_phone_full_flow(self):
        """Direct API phones (WABA3) should do pre_accept → IVR menu → terminate."""
        with patch.object(self.handler, '_update_call_status') as mock_status, \
             patch.object(self.handler, '_send_ivr_menu') as mock_menu, \
             patch.object(self.handler, '_meta_api_call', return_value={'success': True}) as mock_api, \
             patch('time.sleep'):
            self.handler._auto_pickup_and_play('call-2', '945798751960485', '+919876543210', 'sdp')
            # Should call Meta API for pre_accept and terminate
            api_calls = mock_api.call_args_list
            assert len(api_calls) == 2
            assert api_calls[0][0][0] == '945798751960485/calls'
            assert api_calls[0][1].get('payload', api_calls[0][0][2])['action'] == 'pre_accept'
            assert api_calls[1][0][0] == '945798751960485/calls'
            assert api_calls[1][1].get('payload', api_calls[1][0][2])['action'] == 'terminate'
            # Should send IVR menu
            mock_menu.assert_called_once()
            # Should set ivr_active then ivr_completed
            statuses = [c[0][1] for c in mock_status.call_args_list]
            assert 'ivr_active' in statuses
            assert 'ivr_completed' in statuses

    def test_waba2_eum_phone_skips_pre_accept(self):
        """WABA2 EUM phone should also skip pre_accept."""
        with patch.object(self.handler, '_update_call_status') as mock_status, \
             patch.object(self.handler, '_send_ivr_menu') as mock_menu, \
             patch.object(self.handler, '_meta_api_call') as mock_api:
            self.handler._auto_pickup_and_play('call-3', '997428863451102', '+919876543210', 'sdp')
            mock_api.assert_not_called()
            mock_menu.assert_called_once()

    def test_ivr_mode_triggers_auto_pickup(self):
        """When pickup_mode is 'ivr', _handle_call_event should call _auto_pickup_and_play."""
        call = {
            'event': 'connect', 'id': 'call-ivr-1', 'from': '+919876543210',
            'direction': 'USER_INITIATED', 'session': {'sdp': 'v=0\r\n'},
            'timestamp': str(int(time.time())),
        }
        metadata = {'phone_number_id': '945798751960485', 'display_phone_number': '918100330063'}
        with patch.object(self.handler, '_store_call_log'), \
             patch.object(self.handler, '_is_auto_pickup_enabled', return_value=True), \
             patch.object(self.handler, '_get_auto_pickup_mode', return_value='ivr'), \
             patch.object(self.handler, '_auto_pickup_and_play') as mock_ivr:
            self.handler._handle_call_event('waba-3', call, metadata, [], 'req-1')
            mock_ivr.assert_called_once_with('call-ivr-1', '945798751960485', '+919876543210', 'v=0\r\n')

    def test_manual_mode_does_not_trigger_ivr(self):
        """When pickup_mode is 'manual', _handle_call_event should NOT call _auto_pickup_and_play."""
        call = {
            'event': 'connect', 'id': 'call-man-1', 'from': '+919876543210',
            'direction': 'USER_INITIATED', 'session': {'sdp': 'v=0\r\n'},
            'timestamp': str(int(time.time())),
        }
        metadata = {'phone_number_id': '945798751960485', 'display_phone_number': '918100330063'}
        with patch.object(self.handler, '_store_call_log'), \
             patch.object(self.handler, '_is_auto_pickup_enabled', return_value=True), \
             patch.object(self.handler, '_get_auto_pickup_mode', return_value='manual'), \
             patch.object(self.handler, '_auto_pickup_and_play') as mock_ivr, \
             patch.object(self.handler, '_meta_api_call', return_value={'success': True}), \
             patch.object(self.handler, '_update_call_status'):
            self.handler._handle_call_event('waba-3', call, metadata, [], 'req-2')
            mock_ivr.assert_not_called()


class TestIVRMenuParity:
    """Test that IVR menus for affected WABAs match WABA3 baseline."""

    @pytest.fixture(autouse=True)
    def setup(self):
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1', 'VERIFY_TOKEN': 'test'}):
            with patch('boto3.resource'), patch('boto3.client'):
                if 'handler' in sys.modules:
                    del sys.modules['handler']
                import handler
                self.handler = handler

    def test_waba1_ivr_menu_matches_waba3(self):
        """WABA1 IVR menu should have same buttons as WABA3."""
        waba1_menu = self.handler.IVR_MENUS.get(self.handler.PHONE1_META_ID, {})
        waba3_menu = self.handler.IVR_MENUS.get(self.handler.WABA3_PHONE_META_ID, {})
        waba1_buttons = [b['id'] for b in waba1_menu.get('buttons', [])]
        waba3_buttons = [b['id'] for b in waba3_menu.get('buttons', [])]
        assert waba1_buttons == waba3_buttons, (
            f"WABA1 buttons {waba1_buttons} differ from WABA3 {waba3_buttons}"
        )

    def test_waba3_ivr_menu_has_required_buttons(self):
        """WABA3 IVR menu should have sales, support, and AI buttons."""
        waba3_menu = self.handler.IVR_MENUS.get(self.handler.WABA3_PHONE_META_ID, {})
        button_ids = [b['id'] for b in waba3_menu.get('buttons', [])]
        assert 'ivr_sales' in button_ids
        assert 'ivr_support' in button_ids
        assert 'ivr_ai' in button_ids

    def test_eum_phones_set_correctly(self):
        """EUM_MANAGED_META_PHONE_IDS should contain WABA1 and WABA2 phones only."""
        assert self.handler.PHONE1_META_ID in self.handler.EUM_MANAGED_META_PHONE_IDS
        assert self.handler.PHONE2_META_ID in self.handler.EUM_MANAGED_META_PHONE_IDS
        assert self.handler.WABA3_PHONE_META_ID not in self.handler.EUM_MANAGED_META_PHONE_IDS

    def test_default_ivr_menu_has_buttons(self):
        """Default IVR menu should have at least 2 buttons."""
        default = self.handler.IVR_DEFAULT_MENU
        assert len(default.get('buttons', [])) >= 2

    def test_all_ivr_response_handlers_exist(self):
        """Every button ID in IVR menus should have a response handler."""
        all_button_ids = set()
        for menu in self.handler.IVR_MENUS.values():
            for btn in menu.get('buttons', []):
                all_button_ids.add(btn['id'])
        for btn_id in all_button_ids:
            assert btn_id in self.handler.IVR_RESPONSES, f"Missing IVR response for {btn_id}"
