# Wix-native gift cards, coupon Option B, and the concurrent double-debit — second pass

Second review of `wix-coupon-giftcard-sample-20261002` (two commits on top of `32b632e3`:
`2ec1b7f1` the feature, `d7ef5583` the review-fix iteration). The change adds a pure Wix Gift
Cards adapter that no handler imports, converts the gift-card store's redeem and void paths onto
a two-item `TransactWriteItems` so the balance move and the flag that records it commit together,
and ships a three-leg offline demo plus a 58-test contract harness. The retirement gate did not
clear, so nothing was deleted and the STOP note is present with its three named live-failure
modes.

All five findings from the first pass are fixed and re-verified: the AWS refusal hook is now armed
in `_install_containment()` before leg 1 with `_count_aws_calls()` reduced to a read (M1),
`urlopen`/`boto3`/`_key_cache` and both botocore hooks are restored in `main()`'s `finally` with a
`_MISSING` sentinel distinguishing absent from `None` (M2, M3), the idempotency key is masked
because it exposes the same unkeyed digest as `demo_code` (L1), the fetch count reads five (L2),
and `credit()`'s docstring now names where a top-up caller's guard belongs (L3).

**Watch for:** one new blocker — the demo cites
`test_the_aws_refusal_hook_is_armed_before_the_first_leg` as the measurement of its
containment-time arming, and that test exists nowhere in the tree (confirmed). The property it
claims is true — I resolved both hook targets after a bare module import and `_arm_aws_refusal`
returned 2 — but nothing in the suite pins it, and the two legs that do not re-arm depend on it
entirely. One stale rationale in a test docstring contradicts the change's own measured contract
transcript (confirmed, non-blocking).

**Verdict**: NEEDS_CHANGES

## High-level view

`wix_gift_cards.py` holds no client, reads no secret, imports nothing that leaves the process and
has no logger at all, so the clear bearer code — which Wix returns unobfuscated on create, and
only there — cannot reach a log line even reduced to a bool. `codeLast4` reads Wix's own
`codeSuffix` and refuses with `CODE_SUFFIX_MISSING` rather than slicing the obfuscated code, which
is the right direction for a parse of bearer value. The four-call surface is
create/query/get/disable because Wix has no delete and no redeem endpoint: redemption moves the
balance Wix-side and the demo states that boundary rather than implying a redeem call exists.

The transaction fix's gate is live in the suite, not only in prose. The defect found during
implementation is the one worth carrying forward — the committer returned a bare balance on the
lost-race branch, so both racing callers answered `committed: True`, and a self-consistent ledger
stating something false is harder to detect than a crash. It now returns `(balance, committed)` and
the loser takes the replay branch, writing no second `GCTXN#`.

Coupon Option B is implemented as described, and the replay test drives `handler.handler` rather
than `_create`, so it measures the status a caller gets rather than the raise. Note what
convergence means here: the replay answers 409 `CODE_ALREADY_EXISTS` and the row keeps the first
attempt's `wixCouponId`, with one create on the wire and one definition row. That is "no second
coupon", not "the replay returns the existing one".

No float touches a path carrying an amount. `_marshal` gates by exact type, so a `Decimal`, a
`float` and a `bool`-as-amount are all refused where `TypeSerializer` would have converted two of
them. `_transact_with_retry`'s backoff jitter is float arithmetic, correctly — a sleep interval is
not an amount, and the suite's `float`-construction guard cannot see float literals anyway, so
that guard proves nothing about the jitter and does not need to.

Demo containment is enforced rather than tallied, and the enforcement is mutation-tested: with
`_arm_aws_refusal` neutralised the mutant reports exit 0 and count 0 where the test asserts 1. The
remaining gap is about *when* the arming happens, not whether it works.

The disclosure posture holds. The transcript in `findings.md` carries the credential only as the
secret name `wecare/wix/headless-api-key`, the gift-card code masked in the summary line, the
create body and the query filter, and now the idempotency key masked too — the fix that matters,
since `demo_code` and `idempotency_key` expose the same sha256 digest of the same reference and a
clear key handed over the masked code by stripping decoration and upper-casing.

<details>
<summary>Issues (2)</summary>

1. **Fabricated test citation for the containment-time arming** — `scripts/demo_coupon_giftcard_sample.py:149` says the "both clients exist before leg 1" property is "Measured by `test_the_aws_refusal_hook_is_armed_before_the_first_leg`, not assumed"; no such test exists anywhere in the tree. Either add it (assert `_arm_aws_refusal([])` returns two targets before any leg runs, or that the hook is live during a `--leg wix-giftcard` run, which never re-arms) or drop the citation and state the property as unpinned.
2. **Stale "no read-by-code" rationale contradicts the change's own transcript** — `tests/test_wix_coupon_giftcard_sample.py:330`'s docstring justifies keeping `coupon_store` with "Wix's `Create Coupon` has no `idempotencyKey` and no read-by-code", but V2b in `docs/execution/wix-contract-verification-20261002.md` measured `specification.code` supporting `$eq` and concluded coupons **can** be filtered by code. Narrow the docstring to the `idempotencyKey` absence, which is the fact that actually carries verdict (B).

</details>

<details>
<summary>Details</summary>

### The arming moment is unpinned, and two legs depend on it

What is not measured is that the arming happens at containment time at all. Both hook paths are
resolved out of `sys.modules`, and `_arm_aws_refusal` swallows the miss:

```python
module = sys.modules.get(module_name)
if module is None:
    continue
```

So if `lambda_utils.middleware` and `lambda_utils.rate_limit` ever stop arriving transitively
through the demo's own imports, arming silently becomes a no-op and the only hook left is
`_leg_coupon`'s re-arm after the handler import. `_leg_wix_giftcard` and `_leg_our_giftcard` do
not re-arm, so `--leg wix-giftcard` and `--leg our-giftcard` would run with no hook while
`_render` still prints "the refusing before-send hook was ARMED BEFORE leg 1".

The property is true today. I resolved both `_HOOK_PATHS` entries after importing the demo module
and nothing else: `middleware in sys.modules: True`, `rate_limit in sys.modules: True`,
`armed at containment time: 2`. The defect is that the source claims this is measured by a named
test and it is not — the same class of defect the first pass raised about `_committer_of`, where
the resolution was to implement the named symbol. `test_an_aws_call_during_a_leg_...` cannot
substitute: it emits `before-send` from inside leg 3, by which point `_leg_coupon` has already
re-armed, so it passes whether or not containment-time arming did anything.

`test_each_leg_runs_on_its_own` is the test that would catch the leg-scoped version of this, and it
asserts exit 0 and `mismatchCount == 0` only — nothing about an armed hook.

### Where the coupon docstring parts company with the transcript

The contract transcript records V2b deliberately, as a clause of the design that did *not*
survive measurement:

```
$ curl -sSL "$CP/filter-and-sort.md" | grep 'specification.code'
| specification.code |$eq,$ne,$hasSome,$contains,$startsWith|Allowed|
```

and draws the right conclusion — "`coupon_store` is kept for **idempotency**, not for
read-by-code". The replay test's docstring then re-asserts the retired version. It changes no
behaviour: the test's assertions are about the conditional put, the single create on the wire and
the preserved `wixCouponId`, all of which stand on the `idempotencyKey` absence alone. It matters
because the next reader deciding whether `coupon_store` can be dropped will read the docstring
beside the code rather than the transcript.

### The lost-race branch, and why its key set is the right one

`_commit_redemption` returning `(balance, committed)` makes the losing caller indistinguishable
from an ordinary settled replay, which is what the answer should be — the money moved once and not
by us. The returned dict carries `codeLast4` and omits `amountPaise`/`source`, matching the
pre-existing settled-replay branch rather than the committed branch. That asymmetry between replay
and commit answers predates this change, so it is out of scope here, and copying the replay shape
is the consistent choice. The one consumer under `amplify/` reads only keys present on all three.

Worth keeping in view for whoever wires this: `balancePaise` on the adapter and
`remainingBalancePaise` on the store both mean "as at a read that followed the commit", not "the
result of this transaction" — `TransactWriteItems` returns no `ALL_NEW`. Both docstrings say so,
and the exact figure is `amountPaise`.

### The retirement gate, and what the demo can and cannot carry

The gate's condition 3 is unreachable from here and the note says so without hedging: the
documented contract is proven, the live site is not, and the three ways it could still fail —
scope on the gift-card service, the premium-plan dependency against a rendition that renders no
`Errors` section on any of the five pages, and the response shape for a 20-character unhyphenated
code on an India/INR site — each state what would and would not follow. Nothing was deleted, so
the concurrency fix lands rather than being retired by deletion.

I confirmed the unwiring independently: nothing under `amplify/` imports `wix_gift_cards` or
references `demo_code` outside the defining module. `demo_code` does live in a module that would
ship the moment some handler imports it, so the fence is the structural test rather than the
module boundary — drift requires deleting a test, which is the stated posture but worth knowing
when the adapter is wired.

### Test mechanisms, spot-checked where the recorded evidence left a question

The three MEDIUMs hold up under inspection rather than on the commit message's word.
`arm_failure(operation, exc, *, times=1)` decrements in `_fail_if_armed`, popping only at
`remaining <= 1`, so "armed twice" produces two failures and the second `pytest.raises` is no
longer asserting against correct code. `_committer_of` and `_is_balance_move` exist with real
signatures in `tests/test_gift_card_store.py` and are imported by name from the concurrency file,
and `_committer_of` raises for a transaction that moves no balance rather than returning a
sentinel a set comparison would absorb. The six-row caller table is followed: six `seen >= n`
sites, `grep -nE 'seen == [0-9]'` empty across `tests/`. Every other test name cited in
`verification.md` resolves to a real definition — checking them is how the one dangling citation
surfaced.

The concurrency test's latch is what makes it durable across the fix. `_InterleaveAtBalanceMove`
overrides both `update_item` and `transact_write_items` and latches on "a call carrying
`ADD balancePaise`", so one forced schedule drives the pre-fix and post-fix code unedited.
Latching on a helper name would have left thread A unblocked post-fix and degraded the test into
an unsynchronised race that can pass for the wrong reason.

Not re-run here, per instruction: the full pytest and vitest suites. `verification.md` records
5 failed / 6881 passed with the five failures in the two known baseline files, the §7 focused set
at 456 passed, `npm run build` before `npx vitest run` at 65 files / 812 passed, and the pre-fix
measurement (200000 paise where post-fix asserts 350000, two balance moves landed,
`committed=True` twice). The only commands I ran were an in-process resolution of the two hook
targets and name-existence greps.

</details>

<details>
<summary>File map</summary>

Production source (2):

- `amplify/functions/shared/lambda_utils/ecommerce/wix_gift_cards.py` — new B1 adapter, four calls, injected request callable, no logger, deliberately unwired
- `amplify/functions/shared/lambda_utils/ecommerce/gift_card_store.py` — redeem/void onto two-item `TransactWriteItems`; `_marshal`, `_transact_with_retry`, `_commit_redemption`, `_commit_void`, `_record_balance_after` added; `_decrement`, `_mark_settled`, `_mark_credited`, `_drop_applied_marker`, both `APPLIED_*` prefixes and `credit()`'s `once_key` removed

Demo and stubs (3):

- `scripts/demo_coupon_giftcard_sample.py` — three legs, enforced zero AWS, Wix stubbed at `urlopen`, all globals restored
- `tests/wix_transport_stub.py` — typed queue, `Authorization` redacted at capture, `UnexpectedWixCall` as a `BaseException`
- `tests/coupon_fake_dynamo.py` — `RLock`, `applied` outcome log, real low-level `transact_write_items`, `arm_failure(times=)`

Tests (6 files) and fixtures (9 JSON), plus `docs/execution/wix-contract-verification-20261002.md`
and the four task documents. Nothing deleted.

Full diff: `git -C /Users/wecaredigital/wecare-store/.worktrees/wix-coupon-giftcard-sample-20261002 diff 32b632e3`

</details>
