import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError
from lambda_utils.customer_auth import CustomerIdentity
from tests.test_customer_session import FakeSessionStore

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('customer_session_endpoint',
    ROOT / 'amplify/functions/ecommerce/customer-session/handler.py')
endpoint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(endpoint)


@pytest.fixture
def app(monkeypatch):
    store = FakeSessionStore()
    class Cognito:
        fail = False
        def describe_user_pool_client(self, **kwargs):
            return {'UserPoolClient': {}}
        def initiate_auth(self, **kwargs):
            if self.fail:
                raise RuntimeError('provider unavailable')
            assert kwargs['AuthFlow'] == 'REFRESH_TOKEN_AUTH'
            return {'AuthenticationResult': {'AccessToken': 'qa-access', 'ExpiresIn': 3600}}
    class Kms:
        def encrypt(self, **kwargs):
            return {'CiphertextBlob': b'encrypted:' + kwargs['Plaintext']}
        def decrypt(self, **kwargs):
            return {'Plaintext': kwargs['CiphertextBlob'].removeprefix(b'encrypted:')}
    cognito = Cognito()
    monkeypatch.setenv('CUSTOMER_SESSIONS_TABLE', 'qa-session-table')
    monkeypatch.setenv('CUSTOMER_SESSION_KMS_KEY_ID', 'qa-key')
    monkeypatch.setattr(endpoint.boto3, 'client', lambda service: cognito if service == 'cognito-idp' else Kms())
    monkeypatch.setattr(endpoint.boto3, 'resource', lambda service: SimpleNamespace(Table=lambda name: None))
    monkeypatch.setattr(endpoint, 'SessionStore', lambda table: store)
    monkeypatch.setattr(endpoint.customer_auth, 'authenticate', lambda event: CustomerIdentity(
        customer_id='CUS_QA', phone='+910000000000', subject='qa-subject'))
    return store, cognito


def call(action, *, cookie='', csrf='', **body):
    return endpoint.handler({'headers': {'origin': 'https://wecare.digital',
        'x-customer-csrf': csrf, 'authorization': 'Bearer qa-access'},
        'cookies': [cookie] if cookie else [], 'body': json.dumps({'action': action, **body})}, None)


def test_remember_return_refresh_then_logout_rejects_cookie(app):
    store, _ = app
    exchanged = call('exchange', refreshToken='qa-refresh')
    assert exchanged['statusCode'] == 200
    cookie = exchanged['cookies'][0].split(';')[0]
    assert 'HttpOnly' in exchanged['cookies'][0] and 'Secure' in exchanged['cookies'][0]
    assert 'Max-Age=' in exchanged['cookies'][0]
    hint = json.loads(exchanged['body'])
    assert 'refreshToken' not in hint and 'accessToken' not in hint
    row = next(iter(store.rows.values()))
    assert row['refreshRef'] != 'qa-refresh'
    absolute = row['absoluteExpiresAt']
    renewed = call('refresh', cookie=cookie, csrf=hint['csrfToken'])
    assert renewed['statusCode'] == 200
    assert json.loads(renewed['body'])['accessToken'] == 'qa-access'
    assert row['absoluteExpiresAt'] == absolute
    assert call('logout', cookie=cookie, csrf=hint['csrfToken'])['statusCode'] == 200
    assert call('refresh', cookie=cookie, csrf=hint['csrfToken'])['statusCode'] == 401


def test_transient_refresh_preserves_session_and_csrf_required(app):
    store, cognito = app
    exchanged = call('exchange', refreshToken='qa-refresh')
    cookie = exchanged['cookies'][0].split(';')[0]
    csrf = json.loads(exchanged['body'])['csrfToken']
    assert call('refresh', cookie=cookie)['statusCode'] == 403
    cognito.fail = True
    assert call('refresh', cookie=cookie, csrf=csrf)['statusCode'] == 503
    assert not next(iter(store.rows.values())).get('revokedAt')
    cognito.fail = False
    assert call('refresh', cookie=cookie, csrf=csrf)['statusCode'] == 200


def test_shared_device_has_no_persistent_cookie(app):
    exchanged = call('exchange', refreshToken='qa-refresh', persistent=False)
    assert exchanged['statusCode'] == 200
    assert 'Max-Age' not in exchanged['cookies'][0]


def test_cross_origin_request_does_not_touch_tokens():
    response = endpoint.handler({'headers': {'origin': 'https://unused.wecare.digital'},
                                 'body': '{}'}, None)
    assert response['statusCode'] == 403
    assert response['headers']['Cache-Control'] == 'no-store'


def test_client_lookup_outage_preserves_cookie_and_is_not_cached(app, monkeypatch):
    _, cognito = app
    def unavailable(**kwargs):
        raise RuntimeError('provider unavailable')
    monkeypatch.setattr(cognito, 'describe_user_pool_client', unavailable)
    result = call('refresh', cookie='wd_csid=fixture-cookie')
    assert result['statusCode'] == 503
    assert result['headers']['Cache-Control'] == 'no-store'
    assert 'cookies' not in result


def test_revoked_refresh_on_exchange_requires_verification(app, monkeypatch):
    _, cognito = app
    def revoked(**kwargs):
        raise ClientError({'Error': {'Code': 'NotAuthorizedException'}}, 'InitiateAuth')
    monkeypatch.setattr(cognito, 'initiate_auth', revoked)
    result = call('exchange', refreshToken='qa-revoked')
    assert result['statusCode'] == 401
    assert json.loads(result['body'])['error'] == 'VERIFICATION_REQUIRED'
