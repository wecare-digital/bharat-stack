"""The concurrent double-debit window in `gift_card_store`, forced rather than timed.

Design reference: `.agents/tasks/wix-coupon-giftcard-sample-20261002/design.md` revision 8, §5.1
(the window), §5.3 / §5.3.1 (the fix) and §5.4 (this file).

These tests FAIL before the fix and PASS after, and they are genuinely concurrent rather than a
sequenced simulation - a sequenced simulation is what the existing suite already had, and it is
what missed this.

Pre-fix schedule, walked: A puts the claim and wins -> main starts B -> A reaches the balance
move and waits -> B's claim put loses, B reads the claim, `settled: False`, sets `claim_read` ->
A applies the decrement, settles, drops its marker, returns -> main sets `a_returned` -> B's
decrement proceeds: the marker is gone and the balance is still sufficient, so it DEBITS A SECOND
TIME. Two moves, 200000 paise left instead of 350000.

Post-fix: A's transaction waits the same way, commits the balance AND `settled` together, and
returns; B's transaction then fails `settled = :false`, is cancelled, moves nothing, and B takes
the replay branch. One move, 350000.

THE BARRIER LATCHES ON A PROPERTY, NOT ON A HELPER NAME
------------------------------------------------------
Latching inside a helper the fix deletes would mean nothing blocks thread A post-fix, and the
test would degrade from a forced interleaving into an unsynchronised race that can pass for the
wrong reason - B completing its entire `redeem` before A even issues its transaction. So the
latch is on "a balance-moving call", and `_InterleaveAtBalanceMove` overrides BOTH `update_item`
AND `transact_write_items`: one per representation, so the same subclass works unchanged across
the fix. The two existing subclasses in this suite each overrode `update_item` alone, which is
the shape a reader copies, and copying it here is exactly the degradation above.

Each latch is awaited BEFORE delegating to `super()`, so the table's `RLock` is never held across
a wait. Holding it would deadlock the other thread's `get_item` into the 5 s join bound. Awaiting
outside and then running the operation indivisibly is still exactly the interleaving the real
database has: interleaving between calls, atomicity within one.
"""

from __future__ import annotations

import pathlib
import sys
import threading

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "amplify/functions/shared"))
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from coupon_fake_dynamo import FakeTable  # noqa: E402
from lambda_utils.ecommerce import gift_card_store as gc  # noqa: E402
from test_gift_card_store import (  # noqa: E402
    PEPPER,
    _committer_of,
    _is_balance_move,
    assert_transaction_items_are_exact_key_updates,
    clock,
    digest_of,
)

JOIN_SECONDS = 5


class _InterleaveAtBalanceMove(FakeTable):
    """Forces the §5.1 schedule by latching on balance MOVES, not on a helper name.

    A balance move is `update_item` carrying `ADD balancePaise` (pre-fix) or
    `transact_write_items` whose items carry the same fragment (post-fix). One mechanism, both
    code versions, forced on every run rather than raced for.

    Which latch applies is decided from `threading.current_thread().name`, so the identity comes
    from the test rather than from the shape of the production code.
    """

    def __init__(self, *args, claim_key: str = "", claim_written=None, claim_read=None,
                 a_returned=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.claim_key = claim_key
        self.claim_written = claim_written
        self.claim_read = claim_read
        self.a_returned = a_returned
        self._a_moves = 0

    # -- the latches, awaited OUTSIDE the locked body ----------------------
    def _await_before_move(self) -> None:
        name = threading.current_thread().name
        if name == "A":
            self._a_moves += 1
            if self._a_moves == 1 and self.claim_read is not None:
                # t3 before t4: A does not move until B has seen `settled: False`.
                self.claim_read.wait(JOIN_SECONDS)
        elif name == "B" and self.a_returned is not None:
            # t7 after t6: B does not move until A's whole redeem has returned, which is what
            # makes the pre-fix double debit certain rather than likely.
            self.a_returned.wait(JOIN_SECONDS)

    def update_item(self, **kwargs):
        if _is_balance_move(("update_item", kwargs)):
            self._await_before_move()
        return super().update_item(**kwargs)

    def transact_write_items(self, **kwargs):
        if _is_balance_move(("transact_write_items", kwargs)):
            self._await_before_move()
        return super().transact_write_items(**kwargs)

    # -- the two signals the fake raises ----------------------------------
    def put_item(self, **kwargs):
        result = super().put_item(**kwargs)
        # Applied, not merely attempted: `super()` raises on a lost condition.
        if (self.claim_written is not None
                and str((kwargs.get("Item") or {}).get(gc.KEY_ATTRIBUTE)) == self.claim_key):
            self.claim_written.set()
        return result

    def get_item(self, **kwargs):
        result = super().get_item(**kwargs)
        if (self.claim_read is not None
                and str((kwargs.get("Key") or {}).get(gc.KEY_ATTRIBUTE)) == self.claim_key
                and threading.current_thread().name == "B"):
            self.claim_read.set()
        return result


def _store(**latches) -> _InterleaveAtBalanceMove:
    return _InterleaveAtBalanceMove(
        key_attr=gc.KEY_ATTRIBUTE,
        indexes={gc.STATUS_INDEX: (gc.STATUS_ATTRIBUTE, "createdAt")},
        **latches)


def _issue(store: FakeTable, *, value_paise: int) -> None:
    gc.issue(store, initial_value_paise=value_paise, pepper=PEPPER, code="WDGC0000TEST0001",
             clock=clock())
    store.calls.clear()
    store.applied.clear()


def _run(target) -> tuple:
    """Start A, let it own the claim, then start B. Join both with a bound.

    The main thread cannot learn "A specifically has returned" from an event both threads set,
    so it joins A. Each join carries its bound and `is_alive()` is asserted after it, so a
    deadlock fails as a deadlock rather than as a confusing assertion about a balance.
    """
    results, errors = {}, {}

    def wrapped(name):
        try:
            results[name] = target(name)
        except BaseException as error:  # noqa: BLE001 - reported, then re-raised by the assert
            errors[name] = error

    a = threading.Thread(target=wrapped, args=("A",), name="A")
    b = threading.Thread(target=wrapped, args=("B",), name="B")
    return a, b, results, errors


def test_two_concurrent_redeems_for_one_payment_attempt_debit_once():
    """Value 500000, both threads redeem 150000 under ONE `paymentAttemptId`.

    The amounts are load-bearing: the face value must exceed twice the redemption, or
    `balancePaise >= :amount` would refuse B's second debit and the bug would be masked by an
    unrelated guard. A sibling test asserts the floor still refuses a genuine overdraw, so the
    two guards stay distinguishable.

    BOTH counts are asserted, and that is not redundant. `calls` is appended BEFORE the
    condition is evaluated, so it counts ATTEMPTS: pre-fix 2 tried / 2 landed / 200000, post-fix
    2 tried / 1 landed / 350000. Asserting `calls == 1` would therefore report `2` on correct
    code and go red for the worst possible reason - and loosening it to `<= 2` or deleting it
    would remove the only assertion that distinguishes one debit from two at the call level.
    "B tried and was refused" is a stronger statement than "B did not try".
    """
    claim_key = gc.PREFIX_CLAIM + digest_of() + "#attempt-1"
    claim_written, claim_read, a_returned = (threading.Event() for _ in range(3))
    store = _store(claim_key=claim_key, claim_written=claim_written, claim_read=claim_read,
                   a_returned=a_returned)
    _issue(store, value_paise=500000)

    def redeem(_name):
        return gc.redeem(store, code_hash=digest_of(), attempt_id="attempt-1",
                         amount_paise=150000, clock=clock())

    a, b, results, errors = _run(redeem)
    a.start()
    assert claim_written.wait(JOIN_SECONDS), "A never wrote the claim"
    b.start()
    a.join(JOIN_SECONDS)
    assert not a.is_alive(), "A deadlocked"
    a_returned.set()
    b.join(JOIN_SECONDS)
    assert not b.is_alive(), "B deadlocked"
    assert not errors, errors

    card = store.rows[gc.PREFIX_CARD + digest_of()]
    assert card["balancePaise"] == 350000, "the card was debited twice for one payment attempt"
    assert len([call for call in store.calls if _is_balance_move(call)]) == 2, "both tried"
    assert len([call for call in store.applied if _is_balance_move(call)]) == 1, "one landed"

    assert {result["transactionId"] for result in results.values()} == {
        store.rows[claim_key]["transactionId"]}
    assert sum(1 for result in results.values() if result["committed"]) == 1
    assert sum(1 for result in results.values() if not result["committed"]) == 1
    assert store.rows[claim_key]["settled"] is True
    assert not [key for key in card if str(key).startswith("appliedClaim#")]

    # The one caller that exercises the attempt-log-not-outcome-log choice: this recording
    # includes B's CANCELLED transaction, and the shape helper reads `calls` so it still checks
    # it. A helper reading `applied` would silently skip the attempt a shape regression hides in.
    seen = assert_transaction_items_are_exact_key_updates(store)
    assert seen >= 2
    assert {_committer_of(kwargs) for name, kwargs in store.calls
            if name == "transact_write_items"} == {"redeem"}


def test_two_concurrent_voids_of_one_transaction_credit_once():
    """The void side of the same window, both counts asserted the same way."""
    setup = _store()
    _issue(setup, value_paise=500000)
    redeemed = gc.redeem(setup, code_hash=digest_of(), attempt_id="attempt-1",
                         amount_paise=150000, clock=clock())
    transaction_id = redeemed["transactionId"]
    original_key = gc.PREFIX_TRANSACTION + digest_of() + "#" + transaction_id

    # Rehome the rows onto a latching store, so the latch is live for the void only.
    a_returned = threading.Event()
    store = _store(a_returned=a_returned)
    store.rows.update({key: dict(row) for key, row in setup.rows.items()})
    assert store.rows[gc.PREFIX_CARD + digest_of()]["balancePaise"] == 350000

    def void(_name):
        return gc.void(store, transaction_id=transaction_id, clock=clock())

    a, b, results, errors = _run(void)
    a.start()
    a.join(JOIN_SECONDS)
    assert not a.is_alive(), "A deadlocked"
    a_returned.set()
    b.start()
    b.join(JOIN_SECONDS)
    assert not b.is_alive(), "B deadlocked"

    assert "A" in results and "A" not in errors, errors
    # B must be REFUSED, not silently absorbed: the ordinary duplicate is answered by the
    # pre-read with no transaction opened at all.
    assert isinstance(errors.get("B"), gc.AlreadyVoided), errors

    card = store.rows[gc.PREFIX_CARD + digest_of()]
    assert card["balancePaise"] == 500000, "the card was credited twice for one void"
    assert len([call for call in store.applied if _is_balance_move(call)]) == 1
    assert store.rows[original_key]["credited"] is True
    assert len([key for key in store.rows
                if key.startswith(gc.PREFIX_TRANSACTION)
                and store.rows[key].get("kind") == gc.KIND_VOID]) == 1
    assert not [key for key in card if str(key).startswith("appliedVoid#")]


def test_two_different_payment_attempts_still_debit_twice_under_concurrency():
    """The property that must NOT regress.

    The claim row makes a REPLAY idempotent; it does not make two genuine purchases one. If this
    went green at 350000 the fix would have turned a customer's second purchase into a refusal.
    """
    claim_written = threading.Event()
    store = _store(claim_key=gc.PREFIX_CLAIM + digest_of() + "#attempt-1",
                   claim_written=claim_written)
    _issue(store, value_paise=500000)

    def redeem(name):
        attempt = "attempt-1" if name == "A" else "attempt-2"
        return gc.redeem(store, code_hash=digest_of(), attempt_id=attempt,
                         amount_paise=150000, clock=clock())

    a, b, results, errors = _run(redeem)
    a.start()
    assert claim_written.wait(JOIN_SECONDS)
    b.start()
    a.join(JOIN_SECONDS)
    b.join(JOIN_SECONDS)
    assert not a.is_alive() and not b.is_alive()
    assert not errors, errors

    assert store.rows[gc.PREFIX_CARD + digest_of()]["balancePaise"] == 200000
    assert len([call for call in store.applied if _is_balance_move(call)]) == 2
    assert len({result["transactionId"] for result in results.values()}) == 2
    assert all(result["committed"] for result in results.values())


def test_a_transaction_row_with_no_credited_attribute_is_refused_and_the_balance_is_untouched():
    """§5.3.1's three-valued `credited`. ABSENT must read as COMPLETE, not as pending.

    A latch written by code that predates the flag cannot be distinguished from one whose credit
    landed, and treating absence as pending would hand the balance back a second time. Only an
    explicit `False` - which only `void` itself writes - re-drives.

    `attribute_exists(credited)` on the transaction item is what keeps this DIAGNOSABLE on the
    racing path too: without it, absent matches no branch, falls through to
    `GiftCardStoreUnavailable`, and every retry cancels again - so a card whose void predates the
    flag becomes permanently un-voidable, which is the mirror image of the irreversibility the
    uncredited-latch retry exists to prevent.
    """
    store = _store()
    _issue(store, value_paise=500000)
    redeemed = gc.redeem(store, code_hash=digest_of(), attempt_id="attempt-1",
                         amount_paise=150000, clock=clock())
    original_key = gc.PREFIX_TRANSACTION + digest_of() + "#" + redeemed["transactionId"]

    legacy = dict(store.rows[original_key])
    legacy["voidedBy"] = "legacy-void-id"
    legacy["voidedAt"] = 1_700_000_000
    legacy.pop("credited", None)
    store.seed(legacy)
    store.applied.clear()
    store.calls.clear()

    with pytest.raises(gc.AlreadyVoided):
        gc.void(store, transaction_id=redeemed["transactionId"], clock=clock())
    assert store.rows[gc.PREFIX_CARD + digest_of()]["balancePaise"] == 350000
    assert not [call for call in store.applied if _is_balance_move(call)]
    # No transaction was opened at all: the pre-read answered it.
    assert not [name for name, _ in store.calls if name == "transact_write_items"]
