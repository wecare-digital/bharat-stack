import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from botocore.exceptions import ClientError
from lambda_utils import customer_auth as _customer_auth
from lambda_utils.customer_auth import CustomerIdentity
from tests.test_customer_session import FakeSessionStore

#: Captured at import time, before any fixture can patch it. The `app` fixture replaces
#: `authenticate` with a stub returning a hardcoded identity, so a test that wants the REAL
#: derivation has to be able to put the real one back.
REAL_AUTHENTICATE = _customer_auth.authenticate

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


def test_exchange_succeeds_with_the_real_derivation_and_the_real_pool_attributes(app, monkeypatch):
    """THE ENDPOINT-LEVEL REGRESSION TEST FOR THE 2026-10-02 OUTAGE.

    Every other case in this file monkeypatches `customer_auth.authenticate` away and returns a
    hardcoded `CustomerIdentity`, which is exactly why they all passed while this endpoint
    answered 401 to every real customer. This one stubs ONLY Cognito `get_user` - with the
    attribute set the live pool actually returns, which carries no `custom:customer_id` - and
    lets the real `authenticate`, the real issuer pin and the real derivation run.

    Before the fix this returned 401 VERIFICATION_REQUIRED and logged
    `customer_auth_no_customer_id`, which is the WARNING CloudWatch recorded four times during
    the owner's confirm attempts.
    """
    from tests.test_customer_auth_and_throttle import (
        CUSTOMER_TOKEN, REAL_POOL_ATTRIBUTES, FakeCognito,
    )

    store, cognito = app
    # Put the REAL authenticate back: the `app` fixture replaced it with a stub.
    monkeypatch.setattr(endpoint.customer_auth, 'authenticate', REAL_AUTHENTICATE)
    monkeypatch.setattr(endpoint.customer_auth, '_client',
                        lambda: FakeCognito(attributes=REAL_POOL_ATTRIBUTES))
    # The handler authenticates TWICE on exchange - once for the request's access token and once
    # for the one the refresh token buys - to prove both belong to the same customer. So the
    # renewed token has to be a customer-pool JWT as well, or the issuer pin refuses it.
    monkeypatch.setattr(cognito, 'initiate_auth', lambda **kwargs: {
        'AuthenticationResult': {'AccessToken': CUSTOMER_TOKEN, 'ExpiresIn': 3600,
                                 'RefreshToken': 'qa-refresh-rotated'}})

    # A token whose `iss` is the customer pool, so the issuer pin is genuinely exercised.
    event = {'headers': {'origin': 'https://wecare.digital',
                         'authorization': f'Bearer {CUSTOMER_TOKEN}'},
             'cookies': [],
             'body': json.dumps({'action': 'exchange', 'refreshToken': 'qa-refresh'})}
    result = endpoint.handler(event, None)

    assert result['statusCode'] == 200, result['body']
    hint = json.loads(result['body'])
    assert hint['csrfToken']
    assert 'refreshToken' not in hint and 'accessToken' not in hint
    cookie = result['cookies'][0]
    assert 'HttpOnly' in cookie and 'Secure' in cookie
    # The session is filed under the Cognito `sub`, the single documented authority.
    row = next(iter(store.rows.values()))
    assert row['customerId'] == 'sub-1234'
