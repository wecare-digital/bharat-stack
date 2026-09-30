"""One-time codes: hashed with a pepper, single use, throttled, and not an oracle.

What these tests are defending
------------------------------
The WhatsApp OTP already in production is sound on the parts it covers - CSPRNG code,
constant-time compare, plaintext only inside Cognito's encrypted session - but it has no
server-side record, so it has no resend limit, no cooldown, and no send throttle at all for a
*registered* number. Its "3 attempts" is really 3 codes, because Cognito re-invokes
CreateAuthChallenge per challenge.

This store exists to close those, and email verification needs it regardless. So the tests below
lean hardest on the limits and on the properties that stop the endpoint being used to discover
which addresses are enrolled.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..',
                                                'amplify', 'functions', 'shared')))
sys.path.insert(0, os.path.dirname(__file__))

from crm_fake_dynamo import FakeClientError, FakeDynamo  # noqa: E402
from lambda_utils import otp_challenge as otp  # noqa: E402

TABLE = 'stack-wecare-digital-DownloadGrantsTable'
PEPPER = 'test-pepper-not-a-real-secret'
SUBJECT = 'asha@example.com'
PURPOSE = 'email_verification'
NOW = 1_700_000_000


@pytest.fixture
def table():
    # DownloadGrantsTable: key `grantId`, TTL enabled on `expiresAt`, measured live. Already the
    # precedent for OTP counters, which is why it is the default rather than a new table.
    return FakeDynamo(keys={TABLE: 'grantId'}).Table(TABLE)


def _issue(table, **kw):
    params = dict(purpose=PURPOSE, subject=SUBJECT, pepper=PEPPER, now=NOW)
    params.update(kw)
    return otp.issue(table, **params)


def _verify(table, code, **kw):
    params = dict(purpose=PURPOSE, subject=SUBJECT, pepper=PEPPER, code=code, now=NOW)
    params.update(kw)
    return otp.verify(table, **params)


# ── the code itself ────────────────────────────────────────────────────────────

def test_a_code_is_six_digits_with_no_leading_zero_problem():
    for _ in range(2000):
        code = otp.generate_code()
        assert len(code) == 6
        assert code.isdigit()
        assert code[0] != '0', 'a leading zero would make the code look 5 digits long'


def test_codes_are_uniformly_distributed_enough_to_not_repeat():
    codes = [otp.generate_code() for _ in range(5000)]
    assert len(set(codes)) > 4400, 'suspiciously many repeats for a 900k keyspace'


def test_a_short_code_is_refused():
    with pytest.raises(ValueError):
        otp.generate_code(digits=3)


def test_code_generation_does_not_use_the_random_module():
    import inspect
    source = inspect.getsource(otp)
    assert 'import secrets' in source
    assert 'import random' not in source


# ── nothing plaintext at rest ──────────────────────────────────────────────────

def test_the_table_holds_neither_the_code_nor_the_subject(table):
    issued = _issue(table)
    rows = table.parent.all_rows(TABLE)
    assert len(rows) == 1
    blob = repr(rows[0])

    assert issued.code not in blob, 'the plaintext code reached the table'
    assert SUBJECT not in blob, 'the plaintext email reached the table'
    assert 'asha' not in blob and 'example.com' not in blob
    assert PEPPER not in blob, 'the pepper reached the table'


def test_the_key_does_not_contain_the_subject(table):
    key = otp.challenge_key(PEPPER, PURPOSE, SUBJECT)
    assert SUBJECT not in key
    assert key.startswith(otp.KEY_PREFIX)


def test_hashing_without_a_pepper_is_refused():
    """An unsalted digest of a six-digit code is brute-forceable in milliseconds."""
    with pytest.raises(ValueError):
        otp.challenge_key('', PURPOSE, SUBJECT)


def test_the_digest_is_bound_to_purpose_and_subject(table):
    """A digest captured for one purpose must not verify against another."""
    issued = _issue(table)
    other = _verify(table, issued.code, purpose='phone_verification')
    assert other.outcome == otp.NO_CHALLENGE


def test_rotating_the_pepper_invalidates_outstanding_challenges(table):
    issued = _issue(table)
    assert _verify(table, issued.code, pepper='a-different-pepper').outcome == otp.NO_CHALLENGE


def test_two_subjects_do_not_collide(table):
    first = _issue(table)
    second = _issue(table, subject='other@example.com')
    assert table.parent.count(TABLE) == 2
    assert _verify(table, second.code).outcome == otp.CODE_INCORRECT
    assert _verify(table, first.code).ok


def test_a_separator_inside_the_subject_cannot_forge_a_collision():
    """The separator must not occur in any part, or two inputs produce one digest."""
    a = otp.challenge_key(PEPPER, 'email', 'a@b.com')
    b = otp.challenge_key(PEPPER, 'email\x1fa', '@b.com')
    assert a != b


# ── the happy path ─────────────────────────────────────────────────────────────

def test_a_correct_code_verifies(table):
    issued = _issue(table)
    result = _verify(table, issued.code)
    assert result.ok and result.outcome == otp.VERIFIED
    assert result.public_outcome() == otp.VERIFIED


def test_the_issued_payload_never_exposes_the_code(table):
    issued = _issue(table)
    assert 'code' not in issued.as_public_dict()
    assert issued.code not in repr(issued.as_public_dict())
    assert issued.as_public_dict()['expiresInSeconds'] == otp.DEFAULT_TTL_SECONDS


# ── single use ─────────────────────────────────────────────────────────────────

def test_a_code_works_exactly_once(table):
    issued = _issue(table)
    assert _verify(table, issued.code).ok
    second = _verify(table, issued.code)
    assert not second.ok and second.outcome == otp.ALREADY_USED


def test_a_concurrent_second_consumption_loses(table):
    """Single use is a conditional update, not read-then-write: success is what marks an email
    verified, so two simultaneous correct submissions must not both succeed."""
    issued = _issue(table)
    table.parent.arm_failure(
        TABLE, 'update_item', FakeClientError('ConditionalCheckFailedException'))
    result = _verify(table, issued.code)
    assert result.outcome == otp.ALREADY_USED
    assert not result.ok


# ── expiry ─────────────────────────────────────────────────────────────────────

def test_a_code_expires(table):
    issued = _issue(table, ttl_seconds=600)
    assert _verify(table, issued.code, now=NOW + 599).ok


def test_a_code_past_its_ttl_is_refused(table):
    issued = _issue(table, ttl_seconds=600)
    result = _verify(table, issued.code, now=NOW + 601)
    assert result.outcome == otp.EXPIRED
    assert not result.ok


def test_expiry_is_checked_before_the_code_is_compared(table):
    """An expired challenge must not let an attacker burn attempts to learn anything."""
    _issue(table, ttl_seconds=600)
    assert _verify(table, '000000', now=NOW + 601).outcome == otp.EXPIRED


# ── attempt limit ──────────────────────────────────────────────────────────────

def test_wrong_codes_count_down_and_then_lock(table):
    issued = _issue(table, max_attempts=3)
    wrong = '111111' if issued.code != '111111' else '222222'

    first = _verify(table, wrong)
    assert first.outcome == otp.CODE_INCORRECT and first.attempts_remaining == 2
    assert _verify(table, wrong).attempts_remaining == 1
    assert _verify(table, wrong).attempts_remaining == 0

    locked = _verify(table, wrong)
    assert locked.outcome == otp.ATTEMPTS_EXHAUSTED


def test_a_locked_challenge_refuses_even_the_correct_code(table):
    """Otherwise the attempt limit is decorative."""
    issued = _issue(table, max_attempts=2)
    wrong = '111111' if issued.code != '111111' else '222222'
    _verify(table, wrong)
    _verify(table, wrong)
    assert _verify(table, issued.code).outcome == otp.ATTEMPTS_EXHAUSTED


def test_the_attempt_limit_is_per_code_not_per_session(table):
    """The gap in the Cognito flow: there, three attempts meant three separate codes sent."""
    issued = _issue(table, max_attempts=5)
    wrong = '111111' if issued.code != '111111' else '222222'
    for _ in range(4):
        _verify(table, wrong)
    assert _verify(table, issued.code).ok, 'the correct code should still work on attempt 5'


# ── resend cooldown and window ─────────────────────────────────────────────────

def test_a_resend_inside_the_cooldown_is_refused(table):
    _issue(table, resend_cooldown=60)
    with pytest.raises(otp.ResendTooSoon) as caught:
        _issue(table, resend_cooldown=60, now=NOW + 30)
    assert caught.value.retry_after_seconds == 30


def test_a_resend_after_the_cooldown_succeeds_and_replaces_the_code(table):
    first = _issue(table, resend_cooldown=60)
    second = _issue(table, resend_cooldown=60, now=NOW + 61)
    assert second.send_count == 2
    assert _verify(table, first.code, now=NOW + 61).outcome == otp.CODE_INCORRECT
    assert _verify(table, second.code, now=NOW + 61).ok


def test_the_send_limit_stops_unbounded_messaging(table):
    """The gap this closes: today a registered number has no send throttle at all, so an
    attacker can loop the sign-in call and spam a real handset."""
    moment = NOW
    for expected in range(1, 6):
        issued = _issue(table, max_sends=5, resend_cooldown=60, now=moment)
        assert issued.send_count == expected
        moment += 61

    with pytest.raises(otp.ResendLimitReached):
        _issue(table, max_sends=5, resend_cooldown=60, now=moment)


def test_the_send_window_rolls_over_so_a_customer_is_not_locked_out_forever(table):
    moment = NOW
    for _ in range(5):
        _issue(table, max_sends=5, resend_cooldown=60, send_window=3600, now=moment)
        moment += 61

    with pytest.raises(otp.ResendLimitReached):
        _issue(table, max_sends=5, resend_cooldown=60, send_window=3600, now=moment)

    rolled = _issue(table, max_sends=5, resend_cooldown=60, send_window=3600,
                    now=NOW + 3601)
    assert rolled.send_count == 1


def test_the_limits_are_enforced_before_a_new_code_replaces_the_old(table):
    """Otherwise resends could be used to reset somebody else's attempt budget."""
    issued = _issue(table, max_sends=1, resend_cooldown=0)
    with pytest.raises(otp.ResendLimitReached):
        _issue(table, max_sends=1, resend_cooldown=0, now=NOW + 1)
    assert _verify(table, issued.code, now=NOW + 1).ok, 'the original code was destroyed'


def test_the_ttl_outlives_the_window_so_rate_limit_state_is_not_deleted_early(table):
    """If TTL removed the row with the challenge, an attacker would get a fresh send budget."""
    _issue(table, ttl_seconds=600, send_window=3600, now=NOW)
    row = table.parent.all_rows(TABLE)[0]
    assert row['expiresAt'] > row['expiresAtEpoch']
    assert row['expiresAt'] >= NOW + 3600


# ── not an oracle ──────────────────────────────────────────────────────────────

def test_every_failure_looks_identical_from_outside(table):
    """§ no account enumeration. 'No challenge' reveals an address was never enrolled;
    'already used' reveals that it was."""
    outcomes = []

    outcomes.append(_verify(table, '123456'))                     # NO_CHALLENGE

    issued = _issue(table)
    wrong = '111111' if issued.code != '111111' else '222222'
    outcomes.append(_verify(table, wrong))                        # CODE_INCORRECT

    _verify(table, issued.code)
    outcomes.append(_verify(table, issued.code))                  # ALREADY_USED

    fresh = FakeDynamo(keys={TABLE: 'grantId'}).Table(TABLE)
    expired = _issue(fresh, ttl_seconds=60)
    outcomes.append(_verify(fresh, expired.code, now=NOW + 61))   # EXPIRED

    assert len({o.outcome for o in outcomes}) == 4, 'the server should distinguish these'
    assert len({o.public_outcome() for o in outcomes}) == 1, \
        'the wire must not distinguish them'
    assert all(not o.ok for o in outcomes)
    assert all(otp.is_indistinguishable(o.outcome) for o in outcomes)


def test_verified_is_not_in_the_indistinguishable_set():
    assert not otp.is_indistinguishable(otp.VERIFIED)


# ── storage failures never cost the customer an attempt ────────────────────────

def test_a_read_failure_raises_rather_than_looking_like_a_wrong_code(table):
    """Returning a failure here would burn the customer's attempt budget for our outage."""
    _issue(table)
    table.parent.arm_failure(TABLE, 'get_item', FakeClientError('ThrottlingException'))
    with pytest.raises(otp.OtpStorageUnavailable):
        _verify(table, '123456')


def test_a_write_failure_on_issue_raises(table):
    table.parent.arm_failure(TABLE, 'put_item', FakeClientError('InternalServerError'))
    with pytest.raises(otp.OtpStorageUnavailable):
        _issue(table)


def test_a_failure_recording_an_attempt_raises_rather_than_silently_not_counting(table):
    """If the attempt counter cannot be written, the limit is not being enforced - so the
    request must fail rather than proceed with an uncounted guess."""
    issued = _issue(table)
    wrong = '111111' if issued.code != '111111' else '222222'
    table.parent.arm_failure(TABLE, 'update_item', FakeClientError('ThrottlingException'))
    with pytest.raises(otp.OtpStorageUnavailable):
        _verify(table, wrong)


def test_a_non_conditional_consume_failure_raises(table):
    issued = _issue(table)
    table.parent.arm_failure(TABLE, 'update_item', FakeClientError('InternalServerError'))
    with pytest.raises(otp.OtpStorageUnavailable):
        _verify(table, issued.code)


# ── nothing sensitive in a log expression ──────────────────────────────────────

def test_no_log_line_mentions_the_code_the_pepper_or_the_subject():
    """CodeQL tracks taint across function boundaries and has failed this repo's build twice
    over a ternary on a secret's truthiness. Reducing a secret to a bool does not launder it."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(otp))
    forbidden = {'code', 'pepper', 'subject', 'codeDigest', 'expected', 'supplied'}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = ast.unparse(node.func)
        if not target.startswith('logger.'):
            continue
        rendered = ast.unparse(node)
        for name in forbidden:
            assert f'{name}' not in rendered.replace('purpose', ''), \
                f'log call references {name!r}: {rendered}'
