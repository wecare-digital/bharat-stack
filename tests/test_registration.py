"""The registration front door: the only way a walk-up customer comes into existence.

Two properties carry most of the weight, and both are things the Cognito trigger cannot do:

The **throttle runs before the send**, because a WhatsApp message is billable and lands on a real
person's handset, and a Cognito trigger receives no client IP so per-IP limiting is structurally
impossible there.

The **response never reveals whether a number is known**. The trigger deliberately returns
`registered: true/false` as a considered trade for a hand-provisioned pool; once anyone can reach a
public checkout endpoint that trade is void.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                                'amplify', 'functions', 'shared')))
sys.path.insert(0, os.path.dirname(__file__))

from crm_fake_dynamo import FakeClientError, FakeDynamo  # noqa: E402
from lambda_utils import otp_challenge, otp_throttle  # noqa: E402
from lambda_utils.identity import customer as ci  # noqa: E402
from lambda_utils.identity import registration as reg  # noqa: E402

TABLE = 'stack-wecare-digital-DownloadGrantsTable'
PEPPER = 'test-pepper-not-a-real-secret'
# Explicit E.164, because this door now refuses to guess a country code. Bare national digits
# used to be normalised to +91 by inference, and that inference is the defect: a ten-digit
# foreign number matched the Indian mobile pattern and was prefixed, so the OTP went to an
# unrelated Indian subscriber and the wrong identity was reserved. See
# tests/test_phone_country_code_preservation.py.
PHONE = '+919330994400'
E164 = '+919330994400'
NOW = 1_700_000_000


@pytest.fixture
def table():
    return FakeDynamo(keys={TABLE: 'grantId'}).Table(TABLE)


class Sender:
    def __init__(self, *, fail=False):
        self.sent = []
        self._fail = fail

    def __call__(self, e164, code):
        if self._fail:
            raise RuntimeError('internal WhatsApp sender returned HTTP 500')
        self.sent.append((e164, code))


class Store:
    """Stands in for the customer table and the Cognito admin calls."""

    def __init__(self, *, existing=None, provision_fails=False):
        self.customers = dict(existing or {})
        self.provisioned = []
        self._provision_fails = provision_fails

    def resolve(self, e164):
        return self.customers.get(e164)

    def create(self, e164):
        record = ci.build_customer(
            first_name='Pending', last_name='Customer',
            phone=e164, email='pending@wecare.digital', now=NOW)
        record['phoneVerifiedAt'] = NOW
        self.customers[e164] = record
        return record

    def provision(self, e164, customer_id):
        if self._provision_fails:
            raise RuntimeError('AccessDeniedException')
        self.provisioned.append((e164, customer_id))


def _event(ip='203.0.113.5'):
    return {'requestContext': {'http': {'method': 'POST', 'sourceIp': ip}}, 'headers': {}}


def _begin(table, *, phone=PHONE, sender=None, event=None, now=NOW):
    return reg.begin(
        raw_phone=phone, event=event or _event(), throttle_table=table,
        challenge_table=table, pepper=PEPPER,
        send_code=sender or Sender(), now=now)


def _complete(table, store, *, code, phone=PHONE, now=NOW):
    return reg.complete(
        raw_phone=phone, code=code, challenge_table=table, pepper=PEPPER,
        resolve_customer=store.resolve, create_customer=store.create,
        provision_login=store.provision, now=now)


# ══════════════════════════════════════════════════════════════════════════════
# begin
# ══════════════════════════════════════════════════════════════════════════════

def test_a_code_is_sent_to_the_normalised_number(table):
    sender = Sender()
    result = _begin(table, sender=sender)

    assert result.outcome == reg.CHALLENGE_SENT
    assert result.ok
    assert sender.sent[0][0] == E164, 'the sender must receive E.164'
    assert len(sender.sent[0][1]) == 6


def test_beginning_creates_no_customer_and_no_login(table):
    """An unverified number is a claim. If a claim created a record, an attacker enumerating
    numbers would populate the customer table for us."""
    store = Store()
    _begin(table)
    assert store.customers == {}
    assert store.provisioned == []


@pytest.mark.parametrize('raw', ['', '   ', 'abc', '12345', None, '9' * 20])
def test_an_invalid_number_is_refused_without_consuming_budget(table, raw):
    result = _begin(table, phone=raw)
    assert result.outcome == reg.INVALID_PHONE
    assert result.http_status() == 400
    assert table.parent.count(TABLE) == 0, 'a malformed number must not consume a counter'


@pytest.mark.parametrize('spelling', ['+919330994400', '0091 9330994400', '+91 93309 94400'])
def test_every_spelling_reaches_one_counter(table, spelling):
    """Uniqueness and the throttle both key on the normalised value, so a trunk zero must not
    buy a fresh budget.

    The two bare spellings this used to carry ('9330994400' and '09330994400') moved to
    `test_a_bare_national_number_is_refused_rather_than_assumed_indian` below: they are now
    rejections, not alternative spellings. '0091 9330994400' stays, because `00` is read as the
    international prefix and still resolves to this number.
    """
    sender = Sender()
    moment = NOW
    for _ in range(5):
        _begin(table, phone=spelling, sender=sender, now=moment)
        moment += 61

    result = _begin(table, phone=spelling, sender=sender, now=moment)
    assert result.outcome == reg.THROTTLED


@pytest.mark.parametrize('bare', ['9330994400', '09330994400'])
def test_a_bare_national_number_is_refused_rather_than_assumed_indian(table, bare):
    """Replaces the two bare spellings removed from the parametrize above, so the coverage is
    moved rather than dropped.

    Inferring +91 is what sent a Singapore customer's code to an Indian stranger: a ten-digit
    foreign number is indistinguishable from an Indian mobile once the '+65' has been stripped.
    This door therefore refuses to guess, and `PhoneField` always emits a dial code so no real
    UI state reaches here without one.
    """
    sender = Sender()
    result = _begin(table, phone=bare, sender=sender)

    assert result.outcome == reg.INVALID_PHONE
    assert result.http_status() == 400
    assert sender.sent == [], 'a refused number must not send'
    assert table.parent.count(TABLE) == 0, 'a refused number must not consume a counter'


def test_the_throttle_runs_before_the_send(table):
    """The ordering that matters: a message is billable and reaches a real handset, so the
    counter has to refuse before the send, not after."""
    sender = Sender()
    moment = NOW
    for _ in range(5):
        _begin(table, sender=sender, now=moment)
        moment += 61
    before = len(sender.sent)

    result = _begin(table, sender=sender, now=moment)
    assert result.outcome == reg.THROTTLED
    assert len(sender.sent) == before, 'a throttled request must not send'
    assert result.retry_after_seconds > 0
    assert result.http_status() == 429


def test_the_per_ip_axis_is_enforced_here_because_the_trigger_cannot(table):
    """A Cognito trigger event carries no client IP, and both web ACLs were deleted."""
    sender = Sender()
    moment = NOW
    for n in range(20):
        _begin(table, phone=f'+9193309944{n:02d}', sender=sender,
               event=_event('203.0.113.5'), now=moment)
        moment += 61

    result = _begin(table, phone='+919000000001', sender=sender,
                    event=_event('203.0.113.5'), now=moment)
    assert result.outcome == reg.THROTTLED


def test_a_different_ip_is_not_penalised(table):
    sender = Sender()
    moment = NOW
    for n in range(20):
        _begin(table, phone=f'+9193309944{n:02d}', sender=sender,
               event=_event('203.0.113.5'), now=moment)
        moment += 61

    result = _begin(table, phone='+919000000001', sender=sender,
                    event=_event('198.51.100.9'), now=moment)
    assert result.outcome == reg.CHALLENGE_SENT


def test_a_resend_inside_the_cooldown_is_throttled(table):
    _begin(table)
    result = _begin(table, now=NOW + 5)
    assert result.outcome == reg.THROTTLED
    assert result.retry_after_seconds > 0


def test_a_throttle_store_outage_fails_closed(table):
    """An unreadable counter means the limit is not enforced, and this route spends money."""
    table.parent.arm_failure(TABLE, 'update_item', FakeClientError('ThrottlingException'))
    sender = Sender()
    result = _begin(table, sender=sender)

    assert result.outcome == reg.STORE_UNAVAILABLE
    assert result.http_status() == 503
    assert sender.sent == []


def test_a_send_failure_leaves_the_challenge_usable(table):
    """The order is deliberate: a stored code with no message is a resend away from working,
    whereas a sent code with no stored challenge can never be verified."""
    result = _begin(table, sender=Sender(fail=True))
    assert result.outcome == reg.SEND_FAILED

    stored = [k for k in table.rows if str(k).startswith(otp_challenge.KEY_PREFIX)]
    assert len(stored) == 1


# ══════════════════════════════════════════════════════════════════════════════
# complete
# ══════════════════════════════════════════════════════════════════════════════

def test_a_correct_code_creates_a_customer_and_provisions_the_login(table):
    sender = Sender()
    _begin(table, sender=sender)
    code = sender.sent[0][1]
    store = Store()

    result = _complete(table, store, code=code)

    assert result.outcome == reg.VERIFIED
    assert result.created is True
    assert ci.is_customer_id(result.customer_id)
    assert store.customers[E164]['phoneVerifiedAt'] == NOW
    assert store.provisioned == [(E164, result.customer_id)]


def test_an_existing_customer_is_resolved_not_duplicated(table):
    sender = Sender()
    _begin(table, sender=sender)
    code = sender.sent[0][1]

    prior = ci.build_customer(first_name='Asha', last_name='Verma',
                              phone=E164, email='asha@example.com', now=NOW - 100)
    store = Store(existing={E164: prior})

    result = _complete(table, store, code=code)

    assert result.outcome == reg.VERIFIED
    assert result.created is False
    assert result.customer_id == prior['customerId'], 'identity is immutable'
    assert len(store.customers) == 1


def test_provisioning_runs_for_an_existing_customer_too(table):
    """It repairs the case sign-in cannot: a customer record with no CONFIRMED Cognito user
    behind it can never sign in, and that is invisible until someone tries.

    It used to be described as repairing a missing `custom:customer_id`. That attribute is not in
    the customer pool's schema and is no longer written at all; session identity comes from the
    Cognito `sub`. The provisioning call still matters, for the reason above.
    """
    sender = Sender()
    _begin(table, sender=sender)
    prior = ci.build_customer(first_name='A', last_name='B', phone=E164,
                              email='a@b.com', now=NOW - 100)
    store = Store(existing={E164: prior})

    _complete(table, store, code=sender.sent[0][1])
    assert store.provisioned == [(E164, prior['customerId'])]


@pytest.mark.parametrize('wrong', ['000000', '999999', '12345', ''])
def test_a_wrong_code_creates_nothing(table, wrong):
    sender = Sender()
    _begin(table, sender=sender)
    real = sender.sent[0][1]
    store = Store()

    result = _complete(table, store, code=wrong if wrong != real else '111111')

    assert result.outcome == reg.CODE_REJECTED
    assert result.http_status() == 401
    assert store.customers == {}
    assert store.provisioned == []


def test_a_code_works_once(table):
    sender = Sender()
    _begin(table, sender=sender)
    code = sender.sent[0][1]
    store = Store()

    assert _complete(table, store, code=code).outcome == reg.VERIFIED
    assert _complete(table, store, code=code).outcome == reg.CODE_REJECTED


def test_an_expired_code_creates_nothing(table):
    sender = Sender()
    _begin(table, sender=sender)
    store = Store()
    result = _complete(table, store, code=sender.sent[0][1],
                       now=NOW + otp_challenge.DEFAULT_TTL_SECONDS + 1)
    assert result.outcome == reg.CODE_REJECTED
    assert store.customers == {}


def test_a_code_for_a_number_never_challenged_is_rejected(table):
    store = Store()
    result = _complete(table, store, code='123456')
    assert result.outcome == reg.CODE_REJECTED
    assert store.customers == {}


def test_a_provisioning_failure_does_not_report_success(table):
    """A customer that exists without a usable login is worse than no customer, because the
    failure is invisible until they try to sign in."""
    sender = Sender()
    _begin(table, sender=sender)
    store = Store(provision_fails=True)

    result = _complete(table, store, code=sender.sent[0][1])
    assert result.outcome == reg.PROVISION_FAILED
    assert not result.ok
    assert result.http_status() == 503


def test_a_challenge_store_outage_does_not_burn_an_attempt(table):
    sender = Sender()
    _begin(table, sender=sender)
    table.parent.arm_failure(TABLE, 'get_item', FakeClientError('ThrottlingException'))
    result = _complete(table, Store(), code=sender.sent[0][1])
    assert result.outcome == reg.STORE_UNAVAILABLE


# ══════════════════════════════════════════════════════════════════════════════
# the endpoint is not an oracle
# ══════════════════════════════════════════════════════════════════════════════

def test_beginning_looks_identical_for_a_known_and_an_unknown_number(table):
    """The trigger returns `registered: true/false` as a considered trade for a hand-provisioned
    pool. Once anyone can reach a public checkout endpoint, that trade is void."""
    known = _begin(table, phone='+919330994400')
    unknown = _begin(table, phone='+919000000001')

    assert known.public_body() == unknown.public_body()
    assert known.http_status() == unknown.http_status()


def test_no_response_body_mentions_registration_or_existence(table):
    sender = Sender()
    begun = _begin(table, sender=sender)
    store = Store()
    verified = _complete(table, store, code=sender.sent[0][1])

    for result in (begun, verified):
        rendered = repr(result.public_body()).lower()
        for leak in ('registered', 'exists', 'unknown', 'new', 'found'):
            assert leak not in rendered


def test_every_code_failure_produces_one_public_answer(table):
    """Wrong, expired, already-used and never-issued must be indistinguishable on the wire."""
    bodies = set()

    sender = Sender()
    _begin(table, sender=sender)
    code = sender.sent[0][1]
    store = Store()

    bodies.add(repr(_complete(table, store, code='111111').public_body()))       # wrong
    _complete(table, store, code=code)                                          # consume
    bodies.add(repr(_complete(table, store, code=code).public_body()))           # used

    fresh = FakeDynamo(keys={TABLE: 'grantId'}).Table(TABLE)
    bodies.add(repr(_complete(fresh, Store(), code='123456').public_body()))     # never issued

    assert len(bodies) == 1


def test_the_customer_id_is_not_returned_to_the_browser(table):
    """Handing it over invites it back as an authorisation claim, which customer_auth refuses."""
    sender = Sender()
    _begin(table, sender=sender)
    store = Store()
    result = _complete(table, store, code=sender.sent[0][1])

    assert result.customer_id
    assert result.customer_id not in repr(result.public_body())


def test_the_verified_body_carries_no_phone_number(table):
    sender = Sender()
    _begin(table, sender=sender)
    result = _complete(table, Store(), code=sender.sent[0][1])
    assert '9330994400' not in repr(result.public_body())


# ══════════════════════════════════════════════════════════════════════════════
# the browser never provisions anything
# ══════════════════════════════════════════════════════════════════════════════

def test_the_module_performs_no_aws_call_of_its_own():
    """Everything that writes is injected, which is what keeps the browser out of Cognito."""
    import inspect
    source = inspect.getsource(reg)
    assert 'boto3' not in source

    for name in ('begin', 'complete'):
        parameters = set(inspect.signature(getattr(reg, name)).parameters)
        assert parameters & {'send_code', 'provision_login', 'create_customer',
                             'resolve_customer', 'throttle_table', 'challenge_table'}


def test_no_signup_call_is_reachable():
    """Public Cognito self-signup stays off. The pool is AllowAdminCreateUserOnly and that is
    deliberate architecture, not a gap to fix."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(reg))
    called = {ast.unparse(node.func) for node in ast.walk(tree)
              if isinstance(node, ast.Call)}
    for forbidden in ('sign_up', 'signUp', 'SignUp', 'confirm_sign_up'):
        assert not any(forbidden in name for name in called)


def test_nothing_sensitive_reaches_a_log():
    import ast
    import inspect
    import re

    tree = ast.parse(inspect.getsource(reg))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not ast.unparse(node.func).startswith('logger.'):
            continue
        rendered = ast.unparse(node)
        for forbidden in ('e164', 'code', 'pepper', 'raw_phone', 'customer_id'):
            assert not re.search(rf'\b{forbidden}\b', rendered), \
                f'log call references {forbidden!r}: {rendered}'
