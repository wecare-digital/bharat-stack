"""Tests for the shared Meta Graph client (lambda_utils.meta_client)."""
import io
import json
import os
import sys
import urllib.error
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))

from lambda_utils.meta_client import MetaClient  # noqa: E402


def _client():
    """MetaClient with creds pre-seeded (no Secrets Manager call)."""
    c = MetaClient(waba2_ids={'2513394156072604', '1055232054343117'})
    MetaClient._cache.clear()
    MetaClient._cache.update({
        'token1': 'TOKEN_ONE_AAAA', 'token2': 'TOKEN_TWO_BBBB',
        'app_secret': 'secret1', 'app_secret_waba2': 'secret2', 'loaded': True,
    })
    return c


def _http_ok(payload: dict):
    resp = MagicMock()
    resp.read.return_value = json.dumps(payload).encode()
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


class TestErrorNormalization:
    def test_normalize_meta_error_dict(self):
        out = MetaClient.normalize_error({'error': {'message': 'bad', 'type': 'OAuthException', 'code': 190, 'fbtrace_id': 'X'}})
        assert out['error']['message'] == 'bad'
        assert out['error']['code'] == 190
        assert out['error']['fbtrace_id'] == 'X'

    def test_normalize_from_string(self):
        out = MetaClient.normalize_error('{"error":{"message":"oops","code":100}}', 400)
        assert out['error']['code'] == 100

    def test_normalize_transient_from_status(self):
        out = MetaClient.normalize_error({}, 503)
        assert out['error']['is_transient'] is True

    def test_is_error(self):
        assert MetaClient.is_error({'error': {'message': 'x'}}) is True
        assert MetaClient.is_error({'data': []}) is False


class TestTokenRouting:
    def test_waba2_uses_second_token(self):
        c = _client()
        t, s = c._creds(waba_id='2513394156072604', phone_id=None)
        assert t == 'TOKEN_TWO_BBBB' and s == 'secret2'

    def test_default_uses_first_token(self):
        c = _client()
        t, s = c._creds(waba_id='2094615664435155', phone_id=None)
        assert t == 'TOKEN_ONE_AAAA' and s == 'secret1'


class TestGraphRequest:
    def test_get_success(self):
        c = _client()
        with patch('urllib.request.urlopen', return_value=_http_ok({'id': '123', 'name': 'WABA'})):
            res = c.graph('123', params={'fields': 'id,name'}, waba_id='2094615664435155')
        assert res['id'] == '123'
        assert not MetaClient.is_error(res)

    def test_appsecret_proof_added(self):
        c = _client()
        captured = {}

        def fake_urlopen(req, timeout=15):
            captured['url'] = req.full_url
            return _http_ok({'ok': True})

        with patch('urllib.request.urlopen', side_effect=fake_urlopen):
            c.graph('123', waba_id='2094615664435155')
        assert 'appsecret_proof=' in captured['url']

    def test_non_transient_error_no_retry(self):
        c = _client()
        err = urllib.error.HTTPError('u', 400, 'Bad', {}, io.BytesIO(json.dumps({'error': {'message': 'bad', 'code': 100}}).encode()))
        with patch('urllib.request.urlopen', side_effect=err) as m, patch('lambda_utils.meta_client.time.sleep'):
            res = c.graph('123', method='POST', payload={'x': 1}, waba_id='2094615664435155')
        assert MetaClient.is_error(res)
        assert res['error']['code'] == 100
        assert m.call_count == 1  # no retry on 400

    def test_transient_error_retries_then_fails(self):
        c = _client()
        err = urllib.error.HTTPError('u', 503, 'Unavailable', {}, io.BytesIO(b'{"error":{"message":"try later"}}'))
        with patch('urllib.request.urlopen', side_effect=err) as m, patch('lambda_utils.meta_client.time.sleep'):
            res = c.graph('123', waba_id='2094615664435155')
        assert MetaClient.is_error(res)
        assert m.call_count == 3  # _MAX_RETRIES

    def test_transient_then_success(self):
        c = _client()
        err = urllib.error.HTTPError('u', 500, 'err', {}, io.BytesIO(b'{"error":{"message":"x"}}'))
        seq = [err, _http_ok({'ok': True})]

        def fake(req, timeout=15):
            item = seq.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        with patch('urllib.request.urlopen', side_effect=fake), patch('lambda_utils.meta_client.time.sleep'):
            res = c.graph('123', waba_id='2094615664435155')
        assert res == {'ok': True}


class TestPagination:
    def test_paginate_follows_cursor(self):
        c = _client()
        pages = [
            {'data': [{'id': 1}, {'id': 2}], 'paging': {'cursors': {'after': 'CUR1'}}},
            {'data': [{'id': 3}], 'paging': {'cursors': {}}},
        ]
        with patch.object(c, 'graph', side_effect=pages):
            items = list(c.paginate('waba/message_templates', waba_id='2094615664435155'))
        assert [i['id'] for i in items] == [1, 2, 3]

    def test_paginate_stops_on_error(self):
        c = _client()
        with patch.object(c, 'graph', return_value={'error': {'message': 'nope'}}):
            items = list(c.paginate('waba/x', waba_id='2094615664435155'))
        assert items == []
