"""A customer's country code must survive normalisation, or the OTP reaches a stranger.

The defect
----------
`identity/customer.py::normalize_phone` strips every non-digit *before* it looks for a country
code, so a ten-digit foreign E.164 number arrives at `_INDIAN_MOBILE_RE` (`^[6-9]\\d{9}$`)
looking exactly like an Indian mobile and `DEFAULT_COUNTRY_CODE` is prepended to a number that
was already complete. Measured against the real module: `+6591234567 -> +916591234567`,
`+6421234567 -> +916421234567`, `+9715012345 -> +919715012345`, and through the `00` branch
`0065 9123 4567 -> +916591234567`.

Three distinct harms, which is why this is a priority rather than a tidy-up:

1. The one-time code is delivered to an unrelated Indian subscriber.
2. The real customer can never sign in, because the number they own was never challenged.
3. The WRONG identity is reserved, permanently, because uniqueness is enforced on the
   normalised value and `Username` is written from it.

It is reachable from the shipped UI: `src/lib/dialCodes.ts` offers +65 Singapore, among others.

What these tests pin
--------------------
- the strict normaliser's output for every row of the reproduction table, inverted;
- that `normalize_phone` is still byte-for-byte the lenient function it was, corrupting
  outputs included, because eight non-entry-point callers depend on it;
- that no country code is ever *inferred* at a customer entry point;
- that the strict path provably never routes through the lenient one - by monkeypatch at
  runtime and by AST inspection of the source, because a wrapper looks correct and cannot work;
- that the second, independently written copy of the same bug in the standalone Cognito
  trigger agrees with the canonical implementation on every row.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'amplify' / 'functions' / 'shared'))
sys.path.insert(0, os.path.dirname(__file__))

from crm_fake_dynamo import FakeDynamo  # noqa: E402
from lambda_utils import otp_throttle  # noqa: E402
from lambda_utils.identity import customer  # noqa: E402
from lambda_utils.identity import registration as reg  # noqa: E402

TRIGGER_PATH = ROOT / 'amplify/functions/auth/customer-whatsapp-auth/handler.py'
EMAIL_HANDLER_PATH = ROOT / 'amplify/functions/auth/email-verification/handler.py'
REGISTRATION_HANDLER_PATH = ROOT / 'amplify/functions/auth/customer-registration/handler.py'

TABLE = 'stack-wecare-digital-DownloadGrantsTable'
PEPPER = 'test-pepper-not-a-real-secret'
NOW = 1_700_000_000

#: The reproduction table, inverted: what the strict normaliser must return.
#:
#: `0065 9123 4567` is the decisive row. The `00` international prefix is consumed by the
#: lenient function before `_INDIAN_MOBILE_RE` runs, so a fix that branches on `+` alone still
#: corrupts it - which is why the marker branch has to handle both markers.
PRESERVED = [
    ('+6591234567', '+6591234567'),
    ('+65 9123 4567', '+6591234567'),
    ('+65(9123)4567', '+6591234567'),
    ('  +65-9123-4567  ', '+6591234567'),
    ('0065 9123 4567', '+6591234567'),
    ('+6421234567', '+6421234567'),
    ('+6689123456', '+6689123456'),
    ('+9715012345', '+9715012345'),
    ('+971501234567', '+971501234567'),
    ('+14155552671', '+14155552671'),
    ('+447911123456', '+447911123456'),
    ('+919330994400', '+919330994400'),
    ('0091 9330994400', '+919330994400'),
    ('+91 93309-94400', '+919330994400'),
    # The trunk-zero rule, which applies to 91 and to nothing else.
    ('+91 09330994400', '+919330994400'),
    # Non-breaking spaces (U+00A0), which a paste from a formatted document carries. These pin
    # that a non-ASCII separator is tolerated at all, on both implementations.
    #
    # Read what they do NOT prove, so nobody mistakes them for the drift guard they look like:
    # a row in this table cannot see a separator-predicate divergence. The canonical function
    # compacts with `[\s\-().]`; the standalone trigger cannot import it and spells the same
    # test as `not ch.isspace()` (identical on every one of the 0x110000 codepoints). An
    # explicit `" \t"` set - which the trigger carried first - is NOT identical, yet it still
    # produces `6591234567` for both rows below, because the trailing `isdigit()` filter
    # discards whatever the compaction left behind. The divergence only becomes visible when
    # the surviving character changes a BRANCH decision, which is the leading-zero check, so it
    # is pinned by `test_the_two_implementations_agree_on_refusal_too` instead.
    ('+65\u00a09123\u00a04567', '+6591234567'),
    ('00\u00a065 9123 4567', '+6591234567'),
    # Numeric-but-not-DECIMAL characters, which are the rows the comment above says this table
    # could not previously see. U+00B2 SUPERSCRIPT TWO is `str.isdigit()`-true and category No,
    # not Nd, so it is NOT matched by `\d` - the two predicates the two implementations used to
    # carry disagreed on it and on 127 other codepoints. Measured before the fix:
    # `+65\u00b291234567` gave the canonical function `+6591234567` and the trigger
    # `65\u00b291234567`, a non-digit in the OTP destination and in the throttle key. Both now
    # filter to ASCII `0`-`9`, so these rows fail the drift test the moment the predicates
    # separate again.
    ('+65\u00b291234567', '+6591234567'),
    ('+919330994400\u00b2', '+919330994400'),
    # The superscript sits between `91` and the trunk `0`, so this also pins that the strip
    # runs before the India trunk rule reads `digits[2:3]`.
    ('+91\u00b209330994400', '+919330994400'),
    # NOT an oversight. We do not know the United Kingdom's trunk convention and will not
    # invent one, so the stray national `0` is carried through and the provider rejects the
    # number. A visible failure the customer can correct beats a silent misdelivery.
    ('+44 07911 123456', '+4407911123456'),
    # `00` is the international prefix per E.123/E.164 even when what follows looks like a
    # bare Indian mobile. Country code 93, deliberately, NOT +91 9330994400.
    ('009330994400', '+9330994400'),
]


@pytest.fixture
def table():
    return FakeDynamo(keys={TABLE: 'grantId'}).Table(TABLE)


@pytest.fixture(scope='module')
def trigger():
    """The standalone Cognito trigger, pinned by path.

    `spec_from_file_location` rather than `import handler`, because every Lambda in this repo
    has a `handler.py` and a bare import resolves to whichever one loaded first.
    """
    os.environ.setdefault('META_WABA_ID', '2094615664435155')
    os.environ.setdefault('META_PHONE_NUMBER_ID', '1016149501586345')
    spec = importlib.util.spec_from_file_location(
        'customer_whatsapp_auth_for_phone_preservation', TRIGGER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ══════════════════════════════════════════════════════════════════════════════
# 3.1 the country code the customer wrote is the country code that is used
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize('raw,expected', PRESERVED)
def test_the_written_country_code_is_preserved(raw, expected):
    assert customer.normalize_phone_preserving_country(raw) == expected


def test_a_singapore_number_never_becomes_an_indian_one():
    """The headline case, stated on its own so a regression names itself in the failure."""
    assert customer.normalize_phone_preserving_country('+6591234567') == '+6591234567'
    assert customer.normalize_phone_preserving_country('0065 9123 4567') == '+6591234567'


def test_the_double_zero_prefix_is_read_as_an_international_prefix():
    """`009330994400` is country code 93, not a bare Indian mobile with noise in front.

    Reading `00` as "maybe a country code, maybe not" is the exact ambiguity that produced the
    defect, so this function resolves it one way and records the divergence from the lenient
    reading here.
    """
    assert customer.normalize_phone_preserving_country('009330994400') == '+9330994400'
    assert customer.normalize_phone('009330994400') == '+919330994400'


def test_the_trunk_zero_rule_applies_to_india_and_nothing_else():
    assert customer.normalize_phone_preserving_country('+91 09330994400') == '+919330994400'
    assert customer.normalize_phone_preserving_country('+44 07911 123456') == '+4407911123456'


@pytest.mark.parametrize('raw', [
    '+91933099440\u0660',                                      # Arabic-Indic zero, trailing
    '+9193309\u066094400',                                     # Arabic-Indic zero, interior
    '+\u0669\u0663\u0663\u0660\u0669\u0669\u0664\u0664\u0660\u0660\u0660\u0660',
    '+\u1369\u136a\u136b\u136c\u136d\u136e\u136f\u1370',        # Ethiopic digits
    '+65\u00b291234567',                                       # superscript two
])
def test_no_non_ascii_digit_survives_into_the_reserved_identity(raw):
    """A returned E.164 must contain ASCII digits and nothing else.

    This is the headline defect reached through a different door. Arabic-Indic digits are
    Unicode category Nd, so `re.sub(r'\\D', '', ...)` left them in place and the 8..15 bound
    counted them - measured, `+91933099440\\u0660` was returned verbatim. `registration.complete`
    writes `normalizedPhone` and the Cognito `Username` from this value and enforces uniqueness
    on it, so that string and `+919330994400` were two distinct identities that read identically
    to a human. Permanent, and no later correction undoes it.

    The assertion is on the shape of the OUTPUT rather than on a specific value, because the
    defect is "a non-digit reached the identity", not "this one codepoint did".
    """
    try:
        result = customer.normalize_phone_preserving_country(raw)
    except customer.InvalidPhoneNumber:
        return  # refused outright is the other acceptable outcome
    assert result.startswith('+')
    assert result[1:].isascii() and result[1:].isdigit(), result


# ══════════════════════════════════════════════════════════════════════════════
# 3.2 the lenient function is frozen, corrupting outputs and all
# ══════════════════════════════════════════════════════════════════════════════

#: Measured against the real module. The first block is the contract `normalize_phone` was
#: written for and still honours; the second block is its CORRUPTING behaviour, recorded here
#: deliberately rather than fixed.
#:
#: Why the corruption is retained: `normalize_phone` has eight importing callers in `amplify/`,
#: and only two of them are customer entry points. The rest are fed from already-stored CRM
#: records and from provider webhooks, where a bare ten-digit Indian number is the normal
#: input and prefixing it is correct. Changing it under them is a different, larger change than
#: this one. The four customer-facing doors moved to the strict function instead; this snapshot
#: exists so that if anybody later edits the lenient function, the edit is deliberate.
LEGACY_SNAPSHOT = [
    # the intended contract
    ('9330994400', '+919330994400'),
    ('09330994400', '+919330994400'),
    ('0093309 94400', '+919330994400'),
    ('0919330994400', '+919330994400'),
    ('+91 93309-94400', '+919330994400'),
    ('919330994400', '+919330994400'),
    ('+971501234567', '+971501234567'),
    ('+14155552671', '+14155552671'),
    ('+447911123456', '+447911123456'),
    ('+60123456789', '+60123456789'),
    ('+81312345678', '+81312345678'),
    ('+966512345678', '+966512345678'),
    # documented LEGACY CORRUPTION - this is why the strict function exists
    ('+6591234567', '+916591234567'),
    ('0065 9123 4567', '+916591234567'),
    ('+6421234567', '+916421234567'),
    ('+6689123456', '+916689123456'),
    ('+9715012345', '+919715012345'),
    ('+91 09330994400', '+9109330994400'),
]


@pytest.mark.parametrize('raw,expected', LEGACY_SNAPSHOT)
def test_the_lenient_function_is_unchanged(raw, expected):
    """A frozen snapshot. If this fails, `normalize_phone` was edited - which this change
    deliberately did not do, because its eight callers were not audited for it."""
    assert customer.normalize_phone(raw) == expected


def test_the_two_functions_disagree_on_exactly_the_cases_that_matter():
    """Stated as a property so the relationship between the two is explicit rather than
    inferred from two separate tables."""
    for raw in ('+6591234567', '0065 9123 4567', '+6421234567', '+6689123456', '+9715012345'):
        assert customer.normalize_phone(raw) != customer.normalize_phone_preserving_country(raw)
    for raw in ('+919330994400', '+971501234567', '+14155552671', '+447911123456'):
        assert customer.normalize_phone(raw) == customer.normalize_phone_preserving_country(raw)


# ══════════════════════════════════════════════════════════════════════════════
# 3.3 a missing country code is refused, not guessed
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize('raw', ['9330994400', '09330994400', '93309 94400', '9000000001'])
def test_bare_national_digits_are_refused(raw):
    """Guessing +91 here is the defect wearing a wrapper: it leaves the inference live for
    every caller that is not `PhoneField`, which always emits a dial code."""
    with pytest.raises(customer.MissingCountryCode):
        customer.normalize_phone_preserving_country(raw)


def test_the_rejection_flows_into_the_existing_handler_except_clauses():
    """Load-bearing, not tidiness. `registration.begin` and `.complete` already catch
    `InvalidPhoneNumber`, and the trigger's callers already catch `ValueError`, so the new
    rejection needs no control-flow change anywhere."""
    with pytest.raises(customer.MissingCountryCode) as caught:
        customer.normalize_phone_preserving_country('9330994400')
    assert isinstance(caught.value, customer.MissingCountryCode)
    assert isinstance(caught.value, customer.InvalidPhoneNumber)
    assert isinstance(caught.value, ValueError)


@pytest.mark.parametrize('raw', ['', '   ', None, '12', 'abc', '+', '+12', '+' + '9' * 20])
def test_unusable_input_is_refused(raw):
    with pytest.raises(customer.InvalidPhoneNumber):
        customer.normalize_phone_preserving_country(raw)


def test_a_country_code_beginning_with_zero_is_refused():
    """No country code starts with zero, so a leading zero after the marker is a mis-keyed
    number rather than a trunk prefix that could be stripped."""
    with pytest.raises(customer.InvalidPhoneNumber):
        customer.normalize_phone_preserving_country('+09330994400')


# ══════════════════════════════════════════════════════════════════════════════
# 3.4 the strict path must never route through the lenient one
# ══════════════════════════════════════════════════════════════════════════════

def test_the_strict_function_never_routes_through_the_inferring_one(monkeypatch):
    """A wrapper that calls `normalize_phone` and inspects the result CANNOT fix this.

    By the time it sees `+916591234567` the `+65` is gone, and `+6591234567` is
    indistinguishable from a genuine Indian `6591234567` that the lenient function was right
    to prefix. Both inputs are exercised because the `+` branch and the `00` branch are the two
    a careless wrapper would collapse into one.
    """
    def tripwire(*_args, **_kwargs):
        raise AssertionError('normalize_phone must not be reachable from the strict path')

    monkeypatch.setattr(customer, 'normalize_phone', tripwire)
    assert customer.normalize_phone_preserving_country('+6591234567') == '+6591234567'
    assert customer.normalize_phone_preserving_country('0065 9123 4567') == '+6591234567'


def _strict_function_def() -> ast.FunctionDef:
    tree = ast.parse(Path(inspect.getsourcefile(customer)).read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if (isinstance(node, ast.FunctionDef)
                and node.name == 'normalize_phone_preserving_country'):
            return node
    raise AssertionError('normalize_phone_preserving_country not found in customer.py')


def test_the_strict_function_body_cannot_reach_the_india_default():
    """The structural half of the guard, mirroring
    tests/test_payment_vocabulary_at_decision_points.py: walk the AST, not the text, because
    the docstring necessarily names all three forbidden symbols to explain the rule.
    """
    node = _strict_function_def()
    body = [child for child in node.body
            if not (isinstance(child, ast.Expr) and isinstance(child.value, ast.Constant))]

    called = set()
    referenced = set()
    for statement in body:
        for inner in ast.walk(statement):
            if isinstance(inner, ast.Call):
                called.add(ast.unparse(inner.func))
            if isinstance(inner, ast.Name):
                referenced.add(inner.id)
            if isinstance(inner, ast.Attribute):
                referenced.add(inner.attr)

    assert not any('normalize_phone' in name for name in called), \
        f'the strict function delegates to {called}'
    assert 'DEFAULT_COUNTRY_CODE' not in referenced
    assert '_INDIAN_MOBILE_RE' not in referenced


def test_the_marker_branch_precedes_every_digit_strip():
    """Ordering is the whole fix. A digit strip reached before the branch destroys the marker,
    and the function is back to guessing a country code.

    Compared at STATEMENT level, and with the docstring excluded: the docstring explains the
    rule and therefore necessarily contains the very call it forbids, which is the same reason
    `tests/test_payment_vocabulary_at_decision_points.py` walks the AST instead of grepping.
    """
    node = _strict_function_def()
    statements = [child for child in node.body
                  if not (isinstance(child, ast.Expr) and isinstance(child.value, ast.Constant))]
    rendered = [ast.unparse(statement) for statement in statements]

    marker_branch = next(i for i, text in enumerate(rendered)
                         if 'MissingCountryCode' in text and 'raise' in text)
    # Both recognised spellings, deliberately enumerated rather than matched as "any re.sub".
    # The function is `[^0-9]` today and was `\D` before the Unicode-digit tightening; naming
    # both keeps this test honest across that change, while a looser match on `re.sub` alone
    # would also catch the separator compaction - which runs BEFORE the marker branch by
    # design, so it would invert the assertion and pass on a broken function.
    digit_strips = [i for i, text in enumerate(rendered)
                    if '\\D' in text or '[^0-9]' in text]

    assert digit_strips, 'expected a digit strip somewhere in the function'
    assert min(digit_strips) > marker_branch, \
        'a digit strip runs before the country-code marker is read'


# ══════════════════════════════════════════════════════════════════════════════
# 3.5 the entry points, wired
# ══════════════════════════════════════════════════════════════════════════════

class _Sender:
    def __init__(self):
        self.sent = []

    def __call__(self, e164, code):
        self.sent.append((e164, code))


class _Store:
    def __init__(self):
        self.customers = {}
        self.provisioned = []

    def resolve(self, e164):
        return self.customers.get(e164)

    def create(self, e164):
        record = customer.build_customer(
            first_name='Pending', last_name='Customer', phone=e164,
            email='pending@wecare.digital', now=NOW)
        record['phoneVerifiedAt'] = NOW
        record['normalizedPhone'] = e164
        record['phone'] = e164
        self.customers[e164] = record
        return record

    def provision(self, e164, customer_id):
        self.provisioned.append((e164, customer_id))


def _event(ip='203.0.113.5'):
    return {'requestContext': {'http': {'method': 'POST', 'sourceIp': ip}}, 'headers': {}}


def _begin(table, phone, sender=None, now=NOW):
    return reg.begin(raw_phone=phone, event=_event(), throttle_table=table,
                     challenge_table=table, pepper=PEPPER,
                     send_code=sender or _Sender(), now=now)


def test_begin_sends_to_the_number_the_customer_actually_wrote(table):
    sender = _Sender()
    result = _begin(table, '+6591234567', sender)

    assert result.outcome == reg.CHALLENGE_SENT
    assert sender.sent[0][0] == '+6591234567'
    assert '+916591234567' not in repr(sender.sent), \
        'the OTP would have gone to an unrelated Indian subscriber'


def test_complete_reserves_the_identity_under_the_written_country_code(table):
    """The identity-reservation proof. `normalizedPhone` and the Cognito `Username` are both
    written from this value, and uniqueness is enforced on it - so a corrupted value locks the
    wrong number into the identity store, which no later correction undoes."""
    sender = _Sender()
    _begin(table, '+6591234567', sender)
    store = _Store()

    result = reg.complete(
        raw_phone='+6591234567', code=sender.sent[0][1], challenge_table=table,
        pepper=PEPPER, resolve_customer=store.resolve, create_customer=store.create,
        provision_login=store.provision, now=NOW)

    assert result.outcome == reg.VERIFIED
    assert '+6591234567' in store.customers
    assert store.customers['+6591234567']['normalizedPhone'] == '+6591234567'
    assert store.provisioned == [('+6591234567', result.customer_id)]
    assert '+916591234567' not in repr(store.customers)
    assert '+916591234567' not in repr(store.provisioned)


def test_a_code_issued_for_one_spelling_verifies_against_another(table):
    """`begin` and `complete` must normalise identically, or the challenge subject and the
    verification subject are two different strings and no code ever works."""
    sender = _Sender()
    _begin(table, '+65 9123 4567', sender)
    store = _Store()

    result = reg.complete(
        raw_phone='+6591234567', code=sender.sent[0][1], challenge_table=table,
        pepper=PEPPER, resolve_customer=store.resolve, create_customer=store.create,
        provision_login=store.provision, now=NOW)
    assert result.outcome == reg.VERIFIED


@pytest.mark.parametrize('bare', ['9330994400', '09330994400'])
def test_a_bare_national_number_is_refused_at_the_door_without_cost(table, bare):
    """The replacement for the two bare spellings removed from
    test_registration.test_every_spelling_reaches_one_counter."""
    sender = _Sender()
    result = _begin(table, bare, sender)

    assert result.outcome == reg.INVALID_PHONE
    assert result.http_status() == 400
    assert sender.sent == []
    assert table.parent.count(TABLE) == 0, 'a refused number must not consume a counter'


# ── the standalone trigger ────────────────────────────────────────────────────

def test_the_trigger_preserves_the_country_code(trigger):
    assert trigger._normalise_phone('+6591234567') == '6591234567'
    assert trigger._normalise_phone('+919330994400') == '919330994400'


def test_the_masked_destination_carries_no_invented_country_code(trigger):
    masked = trigger._mask_phone('+6591234567')
    assert masked.endswith('4567')
    assert not masked.lstrip('*').startswith('91')
    # The length is the load-bearing assertion, because the mask hides the digits that would
    # otherwise reveal the corruption. `+6591234567` is 10 digits, so 6 stars and 4 visible.
    # The defect produced `916591234567` - 12 digits, 8 stars - so a wrong country code shows
    # up here as two extra characters and nothing else. Asserting on the unmasked prefix
    # cannot work: `masked.replace('*', '')` is the last four by construction.
    assert len(masked) == 10, masked
    assert masked == '******4567'


@pytest.mark.parametrize('raw,expected', PRESERVED)
def test_the_two_implementations_do_not_drift(trigger, raw, expected):
    """The trigger is packaged `standalone=True` with `Layers: null`, so it cannot import
    `lambda_utils` and the duplication is forced. This is the only thing keeping the two
    copies in step: one shared case table, asserted on both.
    """
    assert trigger._normalise_phone(raw) == \
        customer.normalize_phone_preserving_country(raw).lstrip('+')


@pytest.mark.parametrize('raw', [
    '+\u00a00065 9123 4567',
    '+\u00a009330994400',
    '\u00a0+65\u00a0(9123)\u00a04567\u00a0',
    # The digit-predicate class, on inputs that reduce to NO ascii digits at all. Arabic-Indic
    # digits are category Nd, so `\d` and `str.isdigit()` both accept them and neither
    # implementation used to refuse this - the canonical function returned
    # `+\u0669\u0663\u0663\u0660\u0669\u0669\u0664\u0664\u0660\u0660\u0660\u0660` verbatim as
    # an E.164, at the door that reserves the identity. Superscripts are `isdigit()`-true but
    # not `\d`-true, so they split the two predicates instead. Both are now refused by both.
    '+\u0669\u0663\u0663\u0660\u0669\u0669\u0664\u0664\u0660\u0660\u0660\u0660',
    '+\u00b2\u00b2\u00b2\u00b2\u00b2\u00b2\u00b2\u00b2',
])
def test_the_two_implementations_agree_on_refusal_too(trigger, raw):
    """Agreeing on the accepted rows is not enough: they have to agree on the refused ones.

    These inputs are the ones that exposed the divergence. A non-breaking space sitting between
    the marker and the first digit survives an ASCII-only separator filter, so the leading zeros
    stay attached and the trigger would accept a number the canonical door refuses - and the
    value it accepted would be the OTP destination. Parametrised on refusal rather than folded
    into `PRESERVED`, because the third row is accepted by both and the first two by neither.
    """
    try:
        expected = customer.normalize_phone_preserving_country(raw).lstrip('+')
    except ValueError:
        with pytest.raises(ValueError):
            trigger._normalise_phone(raw)
    else:
        assert trigger._normalise_phone(raw) == expected


def test_the_trigger_still_imports_nothing_from_lambda_utils():
    """Adding an import would break its live package - the deployed function has no layers."""
    tree = ast.parse(TRIGGER_PATH.read_text(encoding='utf-8'))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(node.module or '')
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    assert not any(name.startswith('lambda_utils') for name in imported), imported


# ── the email-verification throttle axis ──────────────────────────────────────

@pytest.fixture
def email_handler(monkeypatch):
    monkeypatch.setenv('OTP_TABLE', TABLE)
    monkeypatch.setenv('CUSTOMERS_TABLE', 'stack-wecare-digital-CustomersTable')
    monkeypatch.setenv('APP_ENV', 'development')

    spec = importlib.util.spec_from_file_location(
        'email_verification_for_phone_preservation', EMAIL_HANDLER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    fake = FakeDynamo(keys={TABLE: 'grantId',
                            'stack-wecare-digital-CustomersTable': 'customerId'})

    class _Ses:
        def __init__(self):
            self.sent = []

        def send_email(self, **kwargs):
            self.sent.append(kwargs)
            return {'MessageId': 'ses-msg-1'}

    ses = _Ses()
    monkeypatch.setattr(module, '_dynamodb', fake)
    monkeypatch.setattr(module, '_pepper', lambda: PEPPER)
    monkeypatch.setattr(module, '_ses_client', lambda: ses)
    return module, fake, ses


def _email_event(**body):
    return {
        'requestContext': {'http': {'method': 'POST', 'sourceIp': '203.0.113.5',
                                    'apiId': 'zllr9lrg7j'}},
        'headers': {'origin': 'http://localhost:3000'},
        'body': json.dumps({'action': 'request', **body}),
    }


def _phone_axis_rows(fake):
    return [key for key in fake.Table(TABLE).rows
            if str(key).startswith(otp_throttle.PHONE_PREFIX)]


def test_respacing_a_number_does_not_buy_a_fresh_throttle_budget(email_handler):
    """The raw phone was the throttle key, so `+65 9123 4567` and `+6591234567` were two
    buckets and respacing one number was a free evasion."""
    module, fake, _ses = email_handler
    module.handler(_email_event(email='a@example.com', phone='+65 9123 4567'), None)
    module.handler(_email_event(email='b@example.com', phone='+6591234567'), None)

    assert len(_phone_axis_rows(fake)) == 1, 'two spellings of one number must share a counter'


def test_an_unparseable_phone_falls_back_and_never_400s(email_handler):
    """The phone is optional on this endpoint, so refusing the request over its shape would
    break email-only verification."""
    module, fake, _ses = email_handler
    for phone in (None, '', 'not-a-number', '9330994400'):
        response = module.handler(
            _email_event(email=f'x{abs(hash(str(phone)))}@example.com', phone=phone), None)
        assert response['statusCode'] in (200, 429), response


def test_the_email_subject_is_the_fallback_axis(email_handler):
    """An email-only request is still bounded per-address rather than unbounded."""
    module, fake, _ses = email_handler
    module.handler(_email_event(email='only@example.com'), None)
    assert len(_phone_axis_rows(fake)) == 1


# ══════════════════════════════════════════════════════════════════════════════
# 3.6 nothing sensitive reaches a log or a response body
# ══════════════════════════════════════════════════════════════════════════════

#: Every source this task changed, not just the ones the phone fix changed. The no-store work
#: landed separately and touched `customer-registration/handler.py` and `customer_session.py`
#: after this list was written, so the two files were edited inside the same task while sitting
#: outside the guard that is supposed to cover the task's edits. Both already pass; the point of
#: listing them is that the NEXT edit to either is checked rather than trusted. A log-safety guard
#: that enumerates files by hand is only as good as the enumeration.
TOUCHED_SOURCES = [
    ROOT / 'amplify/functions/shared/lambda_utils/identity/customer.py',
    ROOT / 'amplify/functions/shared/lambda_utils/identity/registration.py',
    ROOT / 'amplify/functions/shared/lambda_utils/customer_session.py',
    TRIGGER_PATH,
    EMAIL_HANDLER_PATH,
    REGISTRATION_HANDLER_PATH,
]

#: Names that carry a phone number, a code or a secret. A logging expression must not reference
#: one at all - not reduced to a bool, not behind a ternary. CodeQL
#: (py/clear-text-logging-sensitive-data) tracks taint across function boundaries and has failed
#: this build twice, including on a ternary that provably could not leak.
FORBIDDEN_IN_LOGS = ('e164', 'raw_phone', 'phone_number', 'pepper', 'otp',
                     'secret', 'password', 'answer', 'throttle_subject')


def _source_id(path: Path) -> str:
    """`auth/email-verification/handler.py` rather than `handler.py`. Three of the six sources
    are named `handler.py`, so the bare filename gave pytest ids `handler.py0/1/2` and an
    assertion message that did not say which file had failed."""
    return '/'.join(path.parts[-3:])


@pytest.mark.parametrize('path', TOUCHED_SOURCES, ids=_source_id)
def test_no_logging_expression_references_a_phone_or_a_code(path):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = ast.unparse(node.func)
        if not (target.startswith('logger.') or target == 'print'):
            continue
        rendered = ast.unparse(node)
        for forbidden in FORBIDDEN_IN_LOGS:
            assert not re.search(rf'\b{forbidden}\b', rendered), \
                f'{_source_id(path)}: log call references {forbidden!r}: {rendered}'
        # A bare `phone`/`code`/`digits` name is just as leaky as the fuller spellings.
        for forbidden in ('phone', 'code', 'digits'):
            assert not re.search(rf'\b{forbidden}\b', rendered), \
                f'{_source_id(path)}: log call references {forbidden!r}: {rendered}'


@pytest.mark.parametrize('path', TOUCHED_SOURCES, ids=_source_id)
def test_exception_logging_uses_the_type_name_only(path):
    """An exception message can echo the number or the code, so only the class name is logged."""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.ExceptHandler,)):
            continue
        if not node.name:
            continue
        bound = node.name
        for inner in ast.walk(node):
            if not isinstance(inner, ast.Call):
                continue
            target = ast.unparse(inner.func)
            if not (target.startswith('logger.') or target == 'print'):
                continue
            rendered = ast.unparse(inner)
            if re.search(rf'\b{bound}\b', rendered):
                assert f'type({bound}).__name__' in rendered, \
                    f'{_source_id(path)}: logs the exception itself: {rendered}'


def test_no_full_phone_number_reaches_a_registration_response_body(table):
    sender = _Sender()
    begun = _begin(table, '+6591234567', sender)
    store = _Store()
    verified = reg.complete(
        raw_phone='+6591234567', code=sender.sent[0][1], challenge_table=table,
        pepper=PEPPER, resolve_customer=store.resolve, create_customer=store.create,
        provision_login=store.provision, now=NOW)

    for result in (begun, verified):
        rendered = repr(result.public_body())
        assert '6591234567' not in rendered
        assert '9123' not in rendered


def test_the_masked_destination_is_the_only_phone_shape_the_trigger_publishes(
        trigger, monkeypatch):
    """The browser is shown a masked destination so a mistyped number is correctable, and
    nothing more. Last four only - do not widen it; a full number in a response is a
    disclosure.

    `monkeypatch`, not direct attribute assignment. The `trigger` fixture is `scope='module'`,
    so a bare `trigger._send_otp = ...` is never undone and leaks into every later test that
    takes the fixture. This happens to be the last test in the file today, which makes the
    leak invisible rather than absent - under `pytest-randomly` or any reordering it would
    silently stub out the send path for the drift-agreement tests above and they would still
    pass.
    """
    monkeypatch.setattr(trigger, '_consume_send_budget', lambda *_a, **_k: None)
    monkeypatch.setattr(trigger, '_send_otp', lambda *_a, **_k: None)
    event = {
        'triggerSource': 'CreateAuthChallenge_Authentication',
        'request': {'userAttributes': {'phone_number': '+6591234567',
                                       'custom:partner_waba_id': trigger.META_WABA_ID},
                    'session': []},
        'response': {},
    }
    result = trigger.handler(event, None)
    destination = result['response']['publicChallengeParameters']['destination']

    assert destination.endswith('4567')
    assert '6591234567' not in destination
    assert 'answer' not in result['response']['publicChallengeParameters']
