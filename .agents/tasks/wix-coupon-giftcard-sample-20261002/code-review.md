# Wix-native gift cards, coupon Option B, and the concurrent double-debit — third pass

Third review of `wix-coupon-giftcard-sample-20261002` (three commits on `32b632e3`: `2ec1b7f1`
the feature, `d7ef5583` and `4b4a889b` the review-fix iterations). The change adds a pure Wix
Gift Cards adapter that no handler imports, converts the gift-card store's redeem and void paths
onto two-item `TransactWriteItems` so each balance move and the flag recording it commit
together, and ships a three-leg offline demo with a contract harness. The retirement gate did not
clear, so nothing was deleted and the STOP note is present with its three named live-failure
modes.

Both findings from the second pass are fixed, and the blocking one was fixed the right way round —
by implementing the test the citation claimed existed rather than by deleting the citation.
`test_the_aws_refusal_hook_is_armed_before_the_first_leg` now exists at
`tests/test_demo_coupon_giftcard_sample.py:116` and measures the property in the two directions
the finding named: both `_HOOK_PATHS` targets resolve on a bare import, and the hook is live
inside `--leg wix-giftcard`, the leg that re-arms nothing. The mutation run recorded in
`verification.md` §0b shows the pre-existing containment test staying green on the mutant while
the new one fails `assert 0 == 1`, which is the gap the finding described. The coupon docstring
now rests on the `idempotencyKey` absence alone and says read-by-code is deliberately not part of
the rationale, with `plan.md`'s two stale copies named rather than quietly edited.

**Watch for:** nothing blocking. Two informational observations carried forward for whoever
wires the adapter — the one remaining unrecoverable window in `redeem` is between the committed
transaction and the `GCTXN#` ledger put, which `_record_balance_after` now sits inside
(confirmed; pre-existing in kind and strictly narrowed by this change, not widened in guarantee);
and `demo_code`'s docstring publishes the shared digest fragment for the default demo reference,
so that one demo code is reconstructable from source (confirmed; consistent with `demo_code`
being non-bearer, but the fence is a reference gate, not secrecy).

**Verdict**: APPROVED

## High-level view

The adapter holds no client, reads no secret, imports nothing that leaves the process and has no
logger at all. I checked the transport it is injected with: `wix_ecom.py` has no logger either,
and `_request` reduces an `HTTPError` to method, endpoint and status with no body — so the clear
code travelling in the create body and the query filter has no path to a log line, and no
`WixGiftCardError` message interpolates a code or a pepper. `codeLast4` reads Wix's own
`codeSuffix` and refuses with `CODE_SUFFIX_MISSING` rather than slicing the obfuscated code.

Coupon Option B is implemented as described, and the replay test drives `handler.handler` rather
than `_create`, so it measures the status a caller gets. Convergence here means the replay answers
409 `CODE_ALREADY_EXISTS` with the row keeping the first attempt's `wixCouponId`, one create on
the wire and one definition row. That is "no second coupon", not "the replay returns the existing
one".

The transaction fix retains every pre-existing card-side predicate. Comparing the new card item
against `_decrement` at `32b632e3`, `attribute_exists`, `balancePaise >= :amount` and
`#status = :active` all survive unchanged; only `attribute_not_exists(#applied)` moved, onto the
claim item as `settled = :false`. That is the guarantee getting stronger rather than relocated —
the old marker could only be written after the money had moved, and the new condition commits with
it. The defect found during implementation is the one worth carrying forward: the committer
returned a bare balance on the lost-race branch, so both racing callers answered
`committed: True`. It now returns `(balance, committed)` and the loser takes the replay branch,
writing no second `GCTXN#`.

No float touches a path carrying an amount. I re-scanned by AST across all five new and changed
Python files: the only float literal anywhere is `0.05` in `_transact_with_retry`'s backoff
jitter, the five `float` identifiers are `Callable[[float], None]` annotations on the injected
sleeper, and every `/` in the demo is `pathlib`. `_marshal` gates by exact type, so a `Decimal`, a
`float` and a `bool`-as-amount are all refused where `TypeSerializer` would have converted two of
them.

The disclosure posture holds under direct measurement: the transcript in `findings.md` contains no
`demo_code`, no idempotency key, neither casing of the shared digest fragment, no issuer-shaped
token, and neither the placeholder API key nor the demo pepper literal — the credential appears
only as the name `wecare/wix/headless-api-key`.

<details>
<summary>Issues (2)</summary>

1. **Residual settled-without-ledger window in `redeem`** (informational, non-blocking) — if the
   transaction commits and the `GCTXN#`/`GCTXNID#` puts then fail, the retry takes the settled-replay
   branch and returns without writing them, leaving a moved balance with no row `void()` can resolve
   by transaction id. Pre-existing in kind and narrowed overall by this change; `_record_balance_after`
   is one new operation inside it. No action required now — worth a recovery path when the SPI void
   surface is next touched.
2. **`demo_code`'s docstring publishes its own output for the default reference** (informational,
   non-blocking) — the shared 16-hex fragment for `wd-gc-sample-2026-10-02` is in the module
   docstring under `amplify/`, so that one demo code is reconstructable from source. Consistent with
   `demo_code` being non-bearer; keep the AST reference gate as the fence and do not read the
   docstring as implying the value is withheld.

</details>

<details>
<summary>Details</summary>

### The remaining window, and why the fix narrowed rather than widened it

`redeem`'s sequence is now claim put, one transaction carrying the debit and `settled`, then
`_record_balance_after`, then the `GCTXN#` and `GCTXNID#` puts. At `32b632e3` the sequence was
`_decrement`, `_mark_settled`, `_drop_applied_marker`, then the same two puts — so the base had
two interruption windows and this change removes one of them outright. A crash between the debit
and the settle used to leave the money down and the claim unsettled; the retry's `_decrement`
found its own marker, returned the balance, and completed the ledger. That state is now
unreachable, because the two commit together.

What survives is the second window: claim settled, ledger rows absent. The retry reads a settled
claim, answers from it, and returns before the puts. `void()` resolves exclusively through
`GCTXNID#<transactionId>` and raises `TransactionNotFound` with no row, so the balance cannot be
returned through this layer. The SPI meanwhile answered Wix with that `transactionId`, which is
the part that makes it worth recording rather than ignoring — Wix holds an identifier our ledger
cannot honour.

`_record_balance_after` is a new `UpdateItem` inside that window. It is best-effort and swallows
every exception, so it cannot convert a successful money move into a reported failure; the cost is
one operation of wall-clock width, which is why this is informational rather than a finding.
Nothing in the module or the suite addresses the state, and nothing in the diff made it worse.

### What the unkeyed demo derivation does and does not hide

`demo_code` is deliberately unkeyed, and `test_the_keyed_code_is_not_recoverable_from_a_logged_reference_id`
asserts the positive line (`demo in key`) precisely so the two negative assertions about
`card_code` cannot pass vacuously. The docstring then states the dangerous property concretely,
naming `b4a4841861208fa8` as the fragment shared between `demo_code` and `idempotency_key` for the
default reference.

That also means the full demo code for that reference is `WDGC` plus that fragment upper-cased.
Nothing is spendable — no real card is involved and the transport is stubbed unconditionally. The
point of recording it is that `test_no_file_under_amplify_references_the_demo_only_derivation` is
a *reference* gate: an AST walk over `ast.Attribute`, `ast.Name` and `ast.ImportFrom`,
deliberately not over `FunctionDef.name` so the defining module needs no exemption. It stops
production calling the function. It does not and cannot make the value secret.

### The three MEDIUMs and the citation repair, checked rather than taken on the commit message

`arm_failure(operation, exc, *, times=1)` decrements in `_fail_if_armed`, popping only at
`remaining <= 1`, so "armed twice" produces two genuine failures. `_committer_of` and
`_is_balance_move` exist with real signatures at `tests/test_gift_card_store.py:475` and `:457`
and are imported by name from the concurrency file; `_committer_of` raises for a transaction that
moves no balance rather than returning a sentinel a set comparison would absorb. The six-row
caller table is followed: six `seen >= n` sites, `grep -nE 'seen == [0-9]'` empty across `tests/`.

I also confirmed the removals are clean. None of `APPLIED_CLAIM_PREFIX`, `APPLIED_VOID_PREFIX`,
`_decrement`, `_mark_settled`, `_mark_credited`, `_drop_applied_marker` or `credit`'s `once_key`
has a surviving reference anywhere under `amplify/`, `src/`, `tests/` or `scripts/` outside the
prose that explains why they went.

The one spot-check I ran, because the repairing test landed in the final commit and the recorded
suite total was the only evidence it passes:

```
$ .venv/bin/python -m pytest tests/test_demo_coupon_giftcard_sample.py -q
20 passed in 0.14s
```

### The lost-race branch, its key set, and the deliberate asymmetry with void

The lost-race dict carries `codeLast4` and omits `amountPaise`/`source`, matching the pre-existing
settled-replay branch rather than the committed one, so it is a narrower key set than the happy
path returns. I checked the one consumer under `amplify/` independently —
`wix-giftcard-spi/handler.py:310` reads `outcome["transactionId"]` and
`outcome["remainingBalancePaise"]`, both present on all three branches, so the omission cannot
raise a `KeyError` today.

Redeem's loser returns `committed: False` while void's loser raises `AlreadyVoided`, and both are
pinned by the concurrency tests. The asymmetry is correct per surface rather than an oversight:
the SPI needs a `transactionId` to answer a redeem, and `AlreadyVoided` is the answer Wix expects
for a duplicate void.

Worth keeping in view for whoever wires this: `balancePaise` on the adapter and
`remainingBalancePaise` on the store both mean "as at a read that followed the commit", not "the
result of this transaction" — `TransactWriteItems` returns no `ALL_NEW`. Both docstrings say so,
and the exact figure is `amountPaise`.

### Test mechanisms that make the concurrency claim durable

`_InterleaveAtBalanceMove` latches on "a call carrying `ADD balancePaise`" across both
`update_item` and `transact_write_items`, so one forced schedule drives the pre-fix and post-fix
code unedited; latching on a helper name would have left thread A unblocked post-fix and degraded
the test into an unsynchronised race. Each latch is awaited before delegating to `super()`, so
the fake's `RLock` is never held across a wait — I checked both overrides against `FakeTable`'s
locked bodies, since holding it would deadlock the other thread's `get_item` into the five-second
join bound. `_is_balance_move` reads `UpdateExpression` text, so it does not latch on
`_record_balance_after`'s `SET #observed`.

The fake's `transact_write_items` evaluates every condition before mutating anything and raises
`TransactionCanceledException` with per-item `CancellationReasons[].Code`, which is the shape
`_cancellation_reason_codes` reads out of the response top level rather than out of `["Error"]`.
That detail matters: reading it from `["Error"]` would yield `[]` on every real cancellation and
turn the fix's main path into a 5xx.

### The retirement gate, and what the demo can and cannot carry

Gate condition 3 is unreachable offline and the STOP note says so without hedging: the documented
contract is proven across five recorded fetches, the live site is not, and the three ways it could
still fail — scope on the gift-card service, the premium-plan dependency against a rendition that
renders no `Errors` section on any of the five pages, and the response shape for a 20-character
unhyphenated code on an India/INR site — each state what would and would not follow. Nothing was
deleted, so the concurrency fix lands rather than being retired by deletion, and the pre-fix
measurement (200000 paise where post-fix asserts 350000, two balance moves landed,
`committed=True` twice) is recorded against the store loaded from git at `32b632e3`.

I confirmed the unwiring independently: nothing under `amplify/` imports `wix_gift_cards` or
references `demo_code` outside the defining module.

### Evidence not re-run, per instruction

The full pytest and vitest suites. `verification.md` records 5 failed / 6882 passed with the five
failures in the two known baseline files, the §7 focused set at 457 passed, `npm run build` before
`npx vitest run` at 65 files / 812 passed, and the demo at three legs / zero mismatches / exit 0
with its transcript diffed against `findings.md` at 100 lines versus 100, differing only in the
three per-run ULIDs. Beyond the one test file above, the commands I ran were AST scans for float
usage, a digest-reconstruction check against the transcript, and name-existence greps.

</details>

<details>
<summary>File map</summary>

Production source (2):

- `amplify/functions/shared/lambda_utils/ecommerce/wix_gift_cards.py` — new B1 adapter, four
  calls, injected request callable, no logger, deliberately unwired
- `amplify/functions/shared/lambda_utils/ecommerce/gift_card_store.py` — redeem/void onto
  two-item `TransactWriteItems`; `_marshal`, `_transact_with_retry`, `_commit_redemption`,
  `_commit_void`, `_record_balance_after` added; `_decrement`, `_mark_settled`, `_mark_credited`,
  `_drop_applied_marker`, both `APPLIED_*` prefixes and `credit()`'s `once_key` removed

Demo and stubs (3):

- `scripts/demo_coupon_giftcard_sample.py` — three legs, enforced zero AWS, Wix stubbed at
  `urlopen`, all globals restored through a `_MISSING`-sentinel closure
- `tests/wix_transport_stub.py` — typed queue, `Authorization` redacted at capture,
  `UnexpectedWixCall` as a `BaseException`
- `tests/coupon_fake_dynamo.py` — `RLock`, `applied` outcome log, real low-level
  `transact_write_items`, `arm_failure(times=)`

Tests (6 files) and fixtures (9 JSON), plus `docs/execution/wix-contract-verification-20261002.md`
and the five task documents. Nothing deleted.

Full diff: `git -C /Users/wecaredigital/wecare-store/.worktrees/wix-coupon-giftcard-sample-20261002 diff 32b632e3`

</details>
