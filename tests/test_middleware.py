"""Tests for lambda_utils.middleware module."""
import json
import pytest
from unittest.mock import patch, MagicMock


class TestRequireAuth:
    """Test auth middleware with mocked Cognito."""

    def _make_event(self, method='POST', path='/test', token='valid-token', origin='https://stack.wecare.digital'):
        event = {
            'requestContext': {'http': {'method': method, 'path': path}},
            'headers': {'origin': origin},
            'body': '{}',
        }
        if token:
            event['headers']['authorization'] = f'Bearer {token}'
        return event

    @patch('lambda_utils.middleware.cognito')
    def test_options_skips_auth(self, mock_cognito):
        from lambda_utils.middleware import require_auth
        event = self._make_event(method='OPTIONS')
        result = require_auth(event)
        assert result is None
        mock_cognito.get_user.assert_not_called()

    @patch('lambda_utils.middleware.cognito')
    def test_lambda_invocation_skips_auth(self, mock_cognito):
        from lambda_utils.middleware import require_auth
        event = {'action': 'process', 'payload': {}}
        result = require_auth(event)
        assert result is None

    @patch('lambda_utils.middleware.cognito')
    def test_missing_token_returns_401(self, mock_cognito):
        from lambda_utils.middleware import require_auth
        event = self._make_event(token=None)
        event['headers'].pop('authorization', None)
        result = require_auth(event)
        assert result is not None
        assert result['statusCode'] == 401

    @patch('lambda_utils.middleware.cognito')
    def test_valid_token_sets_auth(self, mock_cognito):
        from lambda_utils.middleware import require_auth
        mock_cognito.get_user.return_value = {
            'Username': 'testuser',
            'UserAttributes': [{'Name': 'email', 'Value': 'test@example.com'}],
        }
        mock_cognito.admin_list_groups_for_user.return_value = {
            'Groups': [{'GroupName': 'Admin'}],
        }
        event = self._make_event()
        result = require_auth(event)
        assert result is None
        assert event['_auth']['username'] == 'testuser'
        assert event['_auth']['role'] == 'Admin'

    @patch('lambda_utils.middleware.cognito')
    def test_expired_token_returns_401(self, mock_cognito):
        from lambda_utils.middleware import require_auth
        # Create a proper exception class on the mock
        exc_class = type('NotAuthorizedException', (Exception,), {})
        mock_cognito.exceptions.NotAuthorizedException = exc_class
        mock_cognito.get_user.side_effect = exc_class('Token expired')
        event = self._make_event()
        result = require_auth(event)
        assert result is not None
        assert result['statusCode'] == 401

    @patch('lambda_utils.middleware.cognito')
    def test_insufficient_role_returns_403(self, mock_cognito):
        from lambda_utils.middleware import require_auth
        mock_cognito.get_user.return_value = {
            'Username': 'viewer',
            'UserAttributes': [{'Name': 'email', 'Value': 'v@example.com'}],
        }
        mock_cognito.admin_list_groups_for_user.return_value = {
            'Groups': [{'GroupName': 'Viewer'}],
        }
        event = self._make_event()
        result = require_auth(event, required_role='Admin')
        assert result is not None
        assert result['statusCode'] == 403
        body = json.loads(result['body'])
        assert body['requiredRole'] == 'Admin'

    @patch('lambda_utils.middleware.cognito')
    def test_skip_path(self, mock_cognito, monkeypatch):
        monkeypatch.setattr('lambda_utils.middleware.AUTH_SKIP_PATHS', ['/webhook'])
        from lambda_utils.middleware import require_auth
        event = self._make_event(path='/webhook/inbound', token=None)
        event['headers'].pop('authorization', None)
        result = require_auth(event)
        assert result is None


class TestHealthCheck:
    def test_health_path_returns_200(self):
        from lambda_utils.middleware import health_check
        event = {
            'requestContext': {'http': {'method': 'GET', 'path': '/api/health'}},
            'headers': {},
        }
        result = health_check(event)
        assert result is not None
        assert result['statusCode'] == 200

    def test_non_health_path_returns_none(self):
        from lambda_utils.middleware import health_check
        event = {
            'requestContext': {'http': {'method': 'GET', 'path': '/api/contacts'}},
            'headers': {},
        }
        result = health_check(event)
        assert result is None
