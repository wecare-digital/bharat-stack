"""Tests for lambda_utils.graph_errors normalizer."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'amplify', 'functions', 'shared'))

from lambda_utils import graph_errors as ge  # noqa: E402

META_400 = '{"error":{"message":"Invalid parameter","type":"OAuthException","code":100,"fbtrace_id":"AAA"}}'
META_401 = '{"error":{"message":"Invalid OAuth access token","type":"OAuthException","code":190,"error_subcode":463,"fbtrace_id":"BBB"}}'
META_403 = '{"error":{"message":"perm","type":"OAuthException","code":200,"error_subcode":1349174}}'
META_404 = '{"error":{"message":"not found","type":"GraphMethodException","code":803}}'
META_422 = '{"error":{"message":"unprocessable","type":"GraphMethodException","code":100}}'
META_500 = '{"error":{"message":"server","type":"GraphMethodException","code":2,"is_transient":true,"fbtrace_id":"CCC"}}'


def test_400_not_retryable():
    out = ge.normalize(META_400, 400)['error']
    assert out['code'] == 100 and out['retryable'] is False and out['fbtrace_id'] == 'AAA'


def test_401_not_retryable():
    out = ge.normalize(META_401, 401)['error']
    assert out['code'] == 190 and out['error_subcode'] == 463 and out['retryable'] is False


def test_403_not_retryable():
    assert ge.normalize(META_403, 403)['error']['retryable'] is False


def test_404_not_retryable():
    assert ge.normalize(META_404, 404)['error']['retryable'] is False


def test_422_not_retryable():
    assert ge.normalize(META_422, 422)['error']['retryable'] is False


def test_500_transient_retryable():
    out = ge.normalize(META_500, 500)['error']
    assert out['is_transient'] is True and out['retryable'] is True and out['fbtrace_id'] == 'CCC'


def test_is_transient_flag_without_5xx():
    body = '{"error":{"message":"x","code":1,"is_transient":true}}'
    assert ge.normalize(body, 200)['error']['is_transient'] is True


def test_fbtrace_extraction_and_full_shape():
    out = ge.normalize(META_401, 401)['error']
    for key in ('message', 'type', 'code', 'error_subcode', 'fbtrace_id', 'is_transient',
                'error_user_title', 'error_user_msg', 'http_status', 'retryable', 'raw_masked'):
        assert key in out


def test_raw_masked_hides_tokens():
    body = {'error': {'message': 'x', 'code': 1}, 'access_token': 'SECRET123'}
    out = ge.normalize(body, 400)['error']
    assert 'SECRET123' not in str(out['raw_masked'])


def test_is_retryable_helper():
    assert ge.is_retryable(503) is True
    assert ge.is_retryable(400) is False
    assert ge.is_retryable(200, META_500) is True
