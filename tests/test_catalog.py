"""Tests for Catalog Management Lambda handler."""
import json
import pytest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'ecommerce', 'catalog-management'))


class TestCatalogHandler:
    """Test catalog management routing and operations."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'ecommerce', 'catalog-management'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}):
            with patch('boto3.resource') as mock_res, patch('boto3.client') as mock_client:
                self.mock_table = MagicMock()
                mock_res.return_value.Table.return_value = self.mock_table
                self.mock_secrets = MagicMock()
                self.mock_secrets.get_secret_value.return_value = {
                    'SecretString': json.dumps({
                        'access_token': 'test_token',
                        'app_secret': 'test_secret',
                    })
                }
                mock_client.return_value = self.mock_secrets
                from handler import handler
                self.handler = handler

    def _make_event(self, method='GET', path='/catalog', params=None, body=None):
        event = {
            'requestContext': {'http': {'method': method, 'path': path}},
            'queryStringParameters': params or {},
            'headers': {'origin': 'https://app.wecare.digital'},
        }
        if body:
            event['body'] = json.dumps(body)
        return event

    def _ctx(self):
        ctx = MagicMock()
        ctx.aws_request_id = 'test-req'
        return ctx

    def test_list_catalogs_route(self):
        with patch('handler._graph_api', return_value={'data': [{'id': 'cat-1', 'name': 'Test'}]}):
            result = self.handler(self._make_event('GET', '/catalog'), self._ctx())
            assert result['statusCode'] == 200
            body = json.loads(result['body'])
            assert 'catalogs' in body

    def test_list_products_route(self):
        with patch('handler._graph_api', return_value={'data': [{'id': 'prod-1', 'name': 'Widget'}]}):
            result = self.handler(
                self._make_event('GET', '/catalog/products', params={'catalogId': 'cat-1'}),
                self._ctx()
            )
            assert result['statusCode'] == 200

    def test_add_product_requires_name(self):
        with patch('handler._graph_api'):
            result = self.handler(
                self._make_event('POST', '/catalog/products', body={'catalogId': 'cat-1'}),
                self._ctx()
            )
            assert result['statusCode'] == 400

    def test_sync_catalog(self):
        with patch('handler._graph_api', return_value={
            'data': [{'id': 'p1', 'name': 'Product 1', 'price': '100'}],
            'paging': {},
        }):
            result = self.handler(
                self._make_event('POST', '/catalog/sync', body={'catalogId': 'cat-1'}),
                self._ctx()
            )
            assert result['statusCode'] == 200
            body = json.loads(result['body'])
            assert body['synced'] == 1

    def test_options_returns_200(self):
        result = self.handler(self._make_event('OPTIONS', '/catalog'), self._ctx())
        assert result['statusCode'] == 200


class TestAdAttribution:
    """Test Ad Attribution Lambda handler."""

    @pytest.fixture(autouse=True)
    def setup(self):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'ecommerce', 'catalog-management'))
        # Reset module path for ad-attribution
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'ad-attribution'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}):
            with patch('boto3.resource') as mock_res, patch('boto3.client'):
                self.mock_table = MagicMock()
                mock_res.return_value.Table.return_value = self.mock_table
                # Need to reimport since path changed
                import importlib
                if 'handler' in sys.modules:
                    del sys.modules['handler']
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'ad-attribution'))

    def test_record_attribution(self):
        sys_path_backup = list(sys.path)
        try:
            # Isolate import
            if 'handler' in sys.modules:
                del sys.modules['handler']
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'ad-attribution'))
            with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}):
                with patch('boto3.resource') as mock_res, patch('boto3.client'):
                    mock_table = MagicMock()
                    mock_res.return_value.Table.return_value = mock_table
                    from handler import _record_attribution
                    result = _record_attribution({
                        'phone': '+919330994400',
                        'contactId': 'c-1',
                        'referral': {
                            'source_type': 'ad',
                            'source_id': 'ad-123',
                            'ctwa_clid': 'click-456',
                            'headline': 'Test Ad',
                        },
                    }, 'req-1')
                    assert result['statusCode'] == 200
                    mock_table.put_item.assert_called_once()
        finally:
            sys.path = sys_path_backup

    def test_record_attribution_requires_referral(self):
        if 'handler' in sys.modules:
            del sys.modules['handler']
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'messaging', 'ad-attribution'))
        with patch.dict(os.environ, {'AWS_REGION': 'us-east-1'}):
            with patch('boto3.resource'), patch('boto3.client'):
                from handler import _record_attribution
                result = _record_attribution({'phone': '+919330994400'}, 'req-2')
                assert result['statusCode'] == 400
