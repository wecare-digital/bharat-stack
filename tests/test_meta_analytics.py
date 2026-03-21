"""
Tests for Meta Analytics Lambda handler.
Covers: messaging analytics, conversation analytics, template analytics, phone quality.
"""
import json
import sys
import os
import importlib
from unittest.mock import patch, MagicMock
import pytest

# Module isolation for handler imports
MODULE_NAME = 'meta_analytics_handler'
if MODULE_NAME in sys.modules:
    del sys.modules[MODULE_NAME]


@pytest.fixture(autouse=True)
def mock_aws():
    """Mock AWS services for all tests."""
    with patch.dict(os.environ, {
        'AWS_REGION': 'us-east-1',
        'META_TOKEN_SECRET': 'wecare/meta-system-user-token',
        'META_API_VERSION': 'v20.0',
    }):
        with patch('boto3.client') as mock_client:
            mock_secrets = MagicMock()
            mock_secrets.get_secret_value.return_value = {
                'SecretString': json.dumps({
                    'access_token': 'test-token-1',
                    'access_token_waba2': 'test-token-2',
                    'app_secret': 'test-secret',
                })
            }
            mock_client.return_value = mock_secrets
            yield mock_client


@pytest.fixture
def handler_module():
    """Import handler with mocked dependencies."""
    spec = importlib.util.spec_from_file_location(
        MODULE_NAME,
        os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'meta-analytics', 'handler.py')
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


def _make_event(path='/meta-analytics/messaging', method='GET', query=None):
    return {
        'requestContext': {'http': {'method': method, 'path': path}},
        'queryStringParameters': query or {},
        'headers': {},
    }


class TestMessagingAnalytics:
    def test_default_route_returns_messaging(self, handler_module):
        with patch.object(handler_module, '_graph_api', return_value={'analytics': {'data': []}}):
            result = handler_module.handler(_make_event(), MagicMock())
            assert result['statusCode'] == 200
            body = json.loads(result['body'])
            assert 'analytics' in body

    def test_messaging_with_date_range(self, handler_module):
        with patch.object(handler_module, '_graph_api', return_value={'analytics': {'sent': 100}}) as mock_api:
            handler_module.handler(
                _make_event(query={'start': '1700000000', 'end': '1700100000', 'granularity': 'DAY'}),
                MagicMock()
            )
            mock_api.assert_called_once()

    def test_messaging_api_error(self, handler_module):
        with patch.object(handler_module, '_graph_api', return_value={'error': {'message': 'Invalid token'}}):
            result = handler_module.handler(_make_event(), MagicMock())
            assert result['statusCode'] == 400


class TestConversationAnalytics:
    def test_conversation_route(self, handler_module):
        with patch.object(handler_module, '_graph_api', return_value={'conversation_analytics': {'data': []}}):
            result = handler_module.handler(_make_event(path='/meta-analytics/conversation'), MagicMock())
            assert result['statusCode'] == 200
            body = json.loads(result['body'])
            assert 'conversationAnalytics' in body

    def test_conversation_with_dimensions(self, handler_module):
        with patch.object(handler_module, '_graph_api', return_value={'conversation_analytics': {}}) as mock_api:
            handler_module.handler(
                _make_event(path='/meta-analytics/conversation', query={'dimensions': 'CONVERSATION_TYPE,COUNTRY'}),
                MagicMock()
            )
            mock_api.assert_called_once()


class TestTemplateAnalytics:
    def test_template_route(self, handler_module):
        with patch.object(handler_module, '_graph_api', return_value={'template_analytics': {'data': []}}):
            result = handler_module.handler(_make_event(path='/meta-analytics/template'), MagicMock())
            assert result['statusCode'] == 200
            body = json.loads(result['body'])
            assert 'templateAnalytics' in body

    def test_template_with_ids(self, handler_module):
        with patch.object(handler_module, '_graph_api', return_value={'template_analytics': {}}) as mock_api:
            handler_module.handler(
                _make_event(path='/meta-analytics/template', query={'templateIds': '123,456'}),
                MagicMock()
            )
            mock_api.assert_called_once()


class TestPhoneQuality:
    def test_phone_quality_route(self, handler_module):
        with patch.object(handler_module, '_graph_api', return_value={
            'quality_rating': 'GREEN', 'messaging_limit_tier': 'TIER_100K'
        }):
            result = handler_module.handler(_make_event(path='/meta-analytics/phone-quality'), MagicMock())
            assert result['statusCode'] == 200
            body = json.loads(result['body'])
            assert 'phoneQuality' in body

    def test_phone_quality_waba2(self, handler_module):
        with patch.object(handler_module, '_graph_api', return_value={'quality_rating': 'GREEN'}) as mock_api:
            handler_module.handler(
                _make_event(path='/meta-analytics/phone-quality', query={'phoneId': '997428863451102'}),
                MagicMock()
            )
            mock_api.assert_called_once()


class TestOptions:
    def test_options_returns_200(self, handler_module):
        result = handler_module.handler(_make_event(method='OPTIONS'), MagicMock())
        assert result['statusCode'] == 200
