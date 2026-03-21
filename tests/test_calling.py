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

    def test_no_app_secret_fails_open(self):
        event = {'headers': {'x-hub-signature-256': 'sha256=anything'}, 'body': '{}'}
        with patch('handler._token_cache', {'loaded': True, 'app_secret1': '', 'app_secret2': ''}):
            assert self.verify(event, 'req-4') is True


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
