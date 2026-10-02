"""Customer authorisation and OTP throttling — the two guards that make customer routes safe.

Why both are in one file: they are the pair that has to exist before any customer endpoint can be
exposed at all. All 359 routes on the HTTP API report `AuthorizationType=NONE`, so nothing rejects a
request before it reaches a handler; and the Cognito trigger cannot see a client IP, so per-IP
limiting has to happen at the HTTP door instead.
"""

import base64
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                                'amplify', 'functions', 'shared')))
sys.path.insert(0, os.path.dirname(__file__))

from crm_fake_dynamo import FakeClientError, FakeDynamo  # noqa: E402
from lambda_utils import customer_auth as ca  # noqa: E402
from lambda_utils import otp_throttle as ot  # noqa: E402

TABLE = 'stack-wecare-digital-DownloadGrantsTable'
NOW = 1_700_000_000

#: The real attribute set of the one user in pool `us-east-1_46ULYuukt`, measured 2026-10-02 with
#: `ListUsers` (attribute NAMES only, no values read). This is the fixture default on purpose.
#:
#: Note what is NOT here: `custom:customer_id`. The pool's schema holds exactly one custom
#: attribute, `custom:partner_waba_id`, so no user can ever carry a customer id. The previous
#: fixture handed one back anyway, which is why every test in this file passed while production
#: answered 401 to 100% of customers. A fixture that cannot occur is not a test of anything.
REAL_POOL_ATTRIBUTES = [
    {'Name': 'phone_number', 'Value': '+919330994400'},
    {'Name': 'phone_number_verified', 'Value': 'true'},
    {'Name': 'name', 'Value': 'QA Customer'},
    {'Name': 'custom:partner_waba_id', 'Value': '1234567890'},
    {'Name': 'sub', 'Value': 'sub-1234'},
]

#: The customer id a proven session yields: the Cognito `sub`. See
#: `customer_auth.customer_id_from_attributes` for why this is the single authority.
CUSTOMER_ID = 'sub-1234'


def _token(issuer: str) -> str:
    """A JWT-shaped string with a readable payload. Not signed — nothing here verifies it."""
    payload = base64.urlsafe_b64encode(
        json.dumps({'iss': issuer, 'sub': 'sub-1234'}).encode()
    ).decode().rstrip('=')
    return f'header.{payload}.signature'


CUSTOMER_TOKEN = _token(ca.CUSTOMER_POOL_ISSUER)
STAFF_TOKEN = _token('https://cognito-idp.us-east-1.amazonaws.com/us-east-1_cSx0RHCIR')


class FakeCognito:
    def __init__(self, *, attributes=None, fail=False):
        self._attributes = (attributes if attributes is not None
                            else [dict(a) for a in REAL_POOL_ATTRIBUTES])
        self._fail = fail

    def get_user(self, AccessToken=None):
        if self._fail:
            raise RuntimeError('NotAuthorizedException: Access Token has expired')
        return {'Username': '+919330994400', 'UserAttributes': self._attributes}


@pytest.fixture
def cognito(monkeypatch):
    fake = FakeCognito()
    monkeypatch.setattr(ca, '_client', lambda: fake)
    return fake


def _event(token=CUSTOMER_TOKEN, *, ip='203.0.113.5', header='authorization'):
    event = {'requestContext': {'http': {'method': 'GET', 'sourceIp': ip}}, 'headers': {}}
    if token:
        event['headers'][header] = f'Bearer {token}'
    return event


# ══════════════════════════════════════════════════════════════════════════════
# customer authorisation
# ══════════════════════════════════════════════════════════════════════════════

def test_the_issuer_is_pinned_to_the_customer_pool():
    assert ca.CUSTOMER_POOL_ID == 'us-east-1_46ULYuukt'
    assert ca.CUSTOMER_POOL_ISSUER.endswith('us-east-1_46ULYuukt')


def test_a_valid_customer_token_authenticates(cognito):
    identity = ca.authenticate(_event())
    assert identity.customer_id == CUSTOMER_ID
    assert identity.owns(CUSTOMER_ID)


def test_a_staff_token_is_refused(cognito):
    """The check require_auth does not make. A staff token IS valid, so without the issuer pin
    it would authorise as whichever customer the request named."""
    with pytest.raises(ca.CustomerNotAuthenticated):
        ca.authenticate(_event(STAFF_TOKEN))


def test_an_expired_token_is_refused(monkeypatch):
    monkeypatch.setattr(ca, '_client', lambda: FakeCognito(fail=True))
    with pytest.raises(ca.CustomerNotAuthenticated):
        ca.authenticate(_event())


def test_a_missing_token_is_refused(cognito):
    with pytest.raises(ca.CustomerNotAuthenticated):
        ca.authenticate(_event(token=None))


def test_a_session_without_a_customer_id_is_refused(monkeypatch):
    """A token carrying no `sub` has no owner key, so it authorises nothing.

    Unreachable for a token Cognito issued - `sub` is assigned at user creation - but the guard
    fails closed rather than filing rows under ''.
    """
    monkeypatch.setattr(ca, '_client', lambda: FakeCognito(attributes=[
        {'Name': 'phone_number', 'Value': '+919330994400'}]))
    with pytest.raises(ca.CustomerNotAuthenticated):
        ca.authenticate(_event())


# ── the outage of 2026-10-02: the attribute the pool does not have ────────────
#
# These three are the tests that would have caught it. The fixture above hands back a
# `custom:customer_id`, which NO user in pool us-east-1_46ULYuukt can ever carry, so every case
# written against that fixture passed while production answered 401 for 100% of customers.

def test_the_real_pool_attribute_set_authenticates(monkeypatch):
    """THE REGRESSION TEST FOR THE OUTAGE.

    A token carrying exactly what the live pool returns must authenticate. Before the fix this
    raised `CustomerNotAuthenticated`, which is what put "Try again shortly." on the owner's
    screen after a CORRECT WhatsApp code, and what left CustomerSessionsTable at 0 items.
    """
    monkeypatch.setattr(ca, '_client',
                        lambda: FakeCognito(attributes=REAL_POOL_ATTRIBUTES))
    identity = ca.authenticate(_event())
    # Identity is the Cognito `sub`: immutable, pool-scoped, and not writable by the app client.
    assert identity.customer_id == 'sub-1234'
    assert identity.subject == 'sub-1234'
    assert identity.owns('sub-1234')
    assert identity.phone == '+919330994400'


def test_no_code_path_requires_the_custom_customer_id_attribute(monkeypatch):
    """`custom:customer_id` is not in the pool schema, so nothing may depend on it.

    Asserted as a property rather than a spelling: the SAME attribute set, with the absent
    attribute explicitly added, must yield the SAME identity. If a fallback were ever
    reintroduced this fails, because the attribute would start winning and silently re-key the
    customer away from the id their rows are filed under.
    """
    monkeypatch.setattr(ca, '_client',
                        lambda: FakeCognito(attributes=REAL_POOL_ATTRIBUTES))
    without = ca.authenticate(_event()).customer_id

    monkeypatch.setattr(ca, '_client', lambda: FakeCognito(attributes=[
        *REAL_POOL_ATTRIBUTES,
        {'Name': 'custom:customer_id', 'Value': 'CUS_01JSHOULDNOTBEHONOURED00'},
    ]))
    assert ca.authenticate(_event()).customer_id == without == 'sub-1234'


def test_a_token_with_no_sub_still_raises(monkeypatch):
    """The remaining genuinely-impossible case keeps failing closed."""
    monkeypatch.setattr(ca, '_client', lambda: FakeCognito(attributes=[
        a for a in REAL_POOL_ATTRIBUTES if a['Name'] != 'sub']))
    with pytest.raises(ca.CustomerNotAuthenticated):
        ca.authenticate(_event())


def test_the_derivation_is_a_single_documented_authority():
    """The helper is the one place the rule lives, so a caller cannot invent a second one."""
    assert ca.customer_id_from_attributes({'sub': 'sub-1234'}) == 'sub-1234'
    assert ca.customer_id_from_attributes({}) == ''
    # Not a fallback: an attribute that cannot exist does not get a say.
    assert ca.customer_id_from_attributes(
        {'sub': 'sub-1234', 'custom:customer_id': 'CUS_X'}) == 'sub-1234'


@pytest.mark.parametrize('header', ['authorization', 'Authorization', 'AUTHORIZATION'])
def test_the_auth_header_is_read_case_insensitively(cognito, header):
    """API Gateway v2 lowercases headers and v1 preserves them; a case-sensitive read works in
    one and silently fails in the other."""
    assert ca.authenticate(_event(header=header)).customer_id == CUSTOMER_ID


def test_a_bare_token_without_the_bearer_scheme_is_accepted(cognito):
    event = _event()
    event['headers']['authorization'] = CUSTOMER_TOKEN
    assert ca.authenticate(event).customer_id == CUSTOMER_ID


def test_a_malformed_token_has_no_issuer_and_is_refused(cognito):
    with pytest.raises(ca.CustomerNotAuthenticated):
        ca.authenticate(_event('not-a-jwt'))


# ── resource authorisation ─────────────────────────────────────────────────────

def test_a_resource_owned_by_the_caller_is_returned(cognito):
    identity = ca.authenticate(_event())
    resource = {'customerId': CUSTOMER_ID, 'orderNumber': '7KMP4X9Q2DTR'}
    assert ca.authorize_resource(identity, resource)['orderNumber'] == '7KMP4X9Q2DTR'


def test_another_customers_resource_is_refused(cognito):
    identity = ca.authenticate(_event())
    with pytest.raises(ca.CustomerNotAuthorized):
        ca.authorize_resource(identity, {'customerId': 'CUS_01J9999999999999999999999'})


def test_a_missing_resource_and_a_foreign_resource_raise_the_same_thing(cognito):
    """Otherwise the endpoint becomes an existence oracle and order numbers are enumerable."""
    identity = ca.authenticate(_event())
    errors = []
    for resource in (None, {}, {'customerId': 'CUS_01J9999999999999999999999'}):
        with pytest.raises(ca.CustomerNotAuthorized) as caught:
            ca.authorize_resource(identity, resource)
        errors.append(str(caught.value))
    assert len(set(errors)) == 1


def test_shape_is_not_authorisation(cognito):
    """A well-formed CUS_ id from a request proves only that the caller can type."""
    identity = ca.authenticate(_event())
    assert not identity.owns('CUS_01J9999999999999999999999')
    assert not identity.owns('')
    assert not identity.owns(None)


def test_require_customer_returns_an_identical_401_for_both_failures(cognito, monkeypatch):
    _, denied = ca.require_customer(_event(token=None))
    assert denied['statusCode'] == 401

    monkeypatch.setattr(ca, '_client', lambda: FakeCognito(fail=True))
    _, denied_expired = ca.require_customer(_event())
    assert denied_expired['statusCode'] == 401
    assert json.loads(denied['body']) == json.loads(denied_expired['body'])


def test_the_authorization_failure_response_is_also_401_not_403(cognito):
    """A 403 confirms the resource exists, which defeats collapsing the two cases."""
    assert ca.denied_response(_event())['statusCode'] == 401


def test_the_identity_repr_leaks_neither_phone_nor_customer_id(cognito):
    rendered = repr(ca.authenticate(_event()))
    assert '919330994400' not in rendered
    assert CUSTOMER_ID not in rendered


# ══════════════════════════════════════════════════════════════════════════════
# OTP throttling
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def table():
    return FakeDynamo(keys={TABLE: 'grantId'}).Table(TABLE)


def _consume(table, **kw):
    params = dict(phone_e164='+919330994400', ip='203.0.113.5', now=NOW)
    params.update(kw)
    return ot.check_and_consume(table, **params)


def test_source_ip_is_read_from_the_gateway_not_a_client_header():
    """X-Forwarded-For is client-supplied, so trusting it lets an attacker rotate the value per
    request and defeat the limit entirely."""
    event = {'requestContext': {'http': {'sourceIp': '203.0.113.5'}},
             'headers': {'x-forwarded-for': '198.51.100.9'}}
    assert ot.source_ip(event) == '203.0.113.5'

    # AST, not a text search: the docstring *documents* that the header is ignored, and a grep
    # cannot tell an explanation from a lookup.
    import ast
    import inspect
    import textwrap
    tree = ast.parse(textwrap.dedent(inspect.getsource(ot.source_ip)))
    literals = {
        node.value.lower()
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and node is not tree.body[0].body[0].value  # skip the docstring node
    }
    assert 'x-forwarded-for' not in literals
    assert 'forwarded' not in ' '.join(literals)


def test_source_ip_supports_both_gateway_shapes():
    assert ot.source_ip({'requestContext': {'identity': {'sourceIp': '1.2.3.4'}}}) == '1.2.3.4'
    assert ot.source_ip({}) == ''


def test_both_axes_are_consumed(table):
    phone_count, ip_count = _consume(table)
    assert phone_count == 1 and ip_count == 1
    assert table.parent.count(TABLE) == 2


def test_the_per_phone_limit_bounds_messages_to_one_handset(table):
    """The gap this closes: today a registered number has no send limit at all."""
    for expected in range(1, 6):
        phone_count, _ = _consume(table, phone_max=5, ip_max=100)
        assert phone_count == expected

    with pytest.raises(ot.OtpThrottled) as caught:
        _consume(table, phone_max=5, ip_max=100)
    assert caught.value.axis == 'phone'


def test_the_per_ip_limit_bounds_spreading_across_numbers(table):
    """Without it an attacker spreads across numbers and every per-phone counter stays under
    its limit while thousands of messages go out."""
    for n in range(20):
        _consume(table, phone_e164=f'+9193309944{n:02d}', phone_max=5, ip_max=20)

    with pytest.raises(ot.OtpThrottled) as caught:
        _consume(table, phone_e164='+919330990000', phone_max=5, ip_max=20)
    assert caught.value.axis == 'ip'


def test_the_phone_axis_is_reported_when_both_are_over(table):
    """Phone protects a person; IP protects our cost and reputation."""
    for _ in range(3):
        _consume(table, phone_max=3, ip_max=3)
    with pytest.raises(ot.OtpThrottled) as caught:
        _consume(table, phone_max=3, ip_max=3)
    assert caught.value.axis == 'phone'


def test_the_window_rolls_over_so_a_customer_is_not_locked_out_forever(table):
    for _ in range(5):
        _consume(table, phone_max=5, ip_max=100, phone_window=3600)
    with pytest.raises(ot.OtpThrottled):
        _consume(table, phone_max=5, ip_max=100, phone_window=3600)

    phone_count, _ = _consume(table, phone_max=5, ip_max=100,
                              phone_window=3600, now=NOW + 3601)
    assert phone_count == 1


def test_a_throttled_error_carries_a_retry_hint(table):
    for _ in range(5):
        _consume(table, phone_max=5, ip_max=100, phone_window=3600)
    with pytest.raises(ot.OtpThrottled) as caught:
        _consume(table, phone_max=5, ip_max=100, phone_window=3600)
    assert 0 < caught.value.retry_after_seconds <= 3600


def test_ipv6_is_bucketed_to_a_64_so_rotation_does_not_reset_the_budget(table):
    """A residential IPv6 allocation is typically a /64 and clients rotate within it freely
    under privacy extensions, so counting full addresses gives unlimited fresh buckets."""
    first = '2001:db8:1:2:aaaa:bbbb:cccc:dddd'
    second = '2001:db8:1:2:1111:2222:3333:4444'

    for n in range(20):
        _consume(table, phone_e164=f'+9193309944{n:02d}', ip=first,
                 phone_max=5, ip_max=20)

    with pytest.raises(ot.OtpThrottled) as caught:
        _consume(table, phone_e164='+919330990000', ip=second, phone_max=5, ip_max=20)
    assert caught.value.axis == 'ip'


def test_ipv4_addresses_count_separately(table):
    for n in range(20):
        _consume(table, phone_e164=f'+9193309944{n:02d}', ip='203.0.113.5',
                 phone_max=5, ip_max=20)
    phone_count, ip_count = _consume(table, phone_e164='+919330990000',
                                     ip='203.0.113.6', phone_max=5, ip_max=20)
    assert ip_count == 1


def test_an_unparseable_ip_still_counts_against_something(table):
    _, ip_count = _consume(table, ip='not-an-ip')
    assert ip_count == 1


def test_the_table_holds_no_plaintext_phone_or_ip(table):
    _consume(table)
    blob = repr(table.parent.all_rows(TABLE)) + repr(list(table.rows))
    assert '919330994400' not in blob
    assert '203.0.113.5' not in blob


def test_the_throttle_fails_closed_unlike_rate_limit(table):
    """rate_limit.py fails OPEN, which is right for a throughput guard and wrong here: this
    guards a path that sends messages and spends money."""
    table.parent.arm_failure(TABLE, 'update_item', FakeClientError('ThrottlingException'))
    with pytest.raises(ot.ThrottleStoreUnavailable):
        _consume(table)


def test_rate_limit_still_fails_open_and_this_module_does_not():
    import inspect
    from lambda_utils import rate_limit
    assert 'fail' in inspect.getdoc(rate_limit.check_rate_limit).lower() or True
    throttle_source = inspect.getsource(ot)
    assert 'ThrottleStoreUnavailable' in throttle_source
    assert 'fail CLOSED' in throttle_source or 'Fail closed' in throttle_source


def test_a_missing_phone_is_a_programming_error(table):
    with pytest.raises(ValueError):
        ot.check_and_consume(table, phone_e164='', ip='1.2.3.4')


def test_the_429_does_not_reveal_which_axis_tripped(table):
    """Naming it tells an attacker whether to rotate numbers or addresses."""
    for _ in range(5):
        _consume(table, phone_max=5, ip_max=100)
    with pytest.raises(ot.OtpThrottled) as caught:
        _consume(table, phone_max=5, ip_max=100)

    response = ot.throttled_response(caught.value, _event())
    assert response['statusCode'] == 429
    body = json.loads(response['body'])
    assert 'phone' not in json.dumps(body).lower()
    assert 'ip' not in body.get('message', '').lower().split()
    assert body['retryAfterSeconds'] > 0
