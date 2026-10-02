# Wix-native gift-card adapter, coupon Option B, and the concurrent double-debit fix

Code review of `2ec1b7f1` on `wix-coupon-giftcard-sample-20261002`, against design revision 8 and
`plan.md`. Design is frozen and out of scope; this reviews the code, the tests and the demo
evidence.

The change adds a pure Wix gift-card adapter (`wix_gift_cards.py`, deliberately unwired), closes a
concurrent double-debit in `gift_card_store.redeem`/`void` by collapsing each money move and its
guard flag into one `TransactWriteItems`, and ships a three-leg offline demo plus 78 new tests. The
gift-card backend retirement did **not** land, correctly: the gate's condition 3 needs one
owner-run live Wix call, which is a standing refusal here, so a STOP note is present and the
backend is whole. All three open MEDIUMs are genuinely fixed in code, not narrated. Coupon Option B
holds: `coupon_store` is the issuance ledger only, Wix does the arithmetic, and a replay consumes
one Wix create.

**Watch for:** the demo's `AWS API calls attempted = 0` line is structurally tautological —
`_count_aws_calls()` registers the `before-send` hooks *after* all three legs have run and reads
its counter in the same breath, so the number can only ever be `0` and no leg call could have been
refused (**confirmed**; also a deviation from design §4.3, which requires the call to "fail the
demo rather than being tallied afterwards"). Secondly, the demo replaces
`urllib.request.urlopen` and registers permanent botocore hooks and never restores either, and a
test runs it in-process, so the pollution outlives the test for the rest of the pytest session
(**confirmed**).

**Verdict**: NEEDS_CHANGES

## High-level view

The adapter is the strongest part of the change. Four calls over an injected request callable, no
boto3, no logger, no `print`, no `float`, every money field crossing the boundary as a decimal
string through `Money.to_wix()`/`from_wix()`, currency compared explicitly against the `INR`
constant before anything else runs. `create` resolves before it generates and carries
`idempotencyKey` as the in-Wix backstop for the query-then-create window, and a resolve hit onto a
disabled or expired card is returned with both facts on it rather than refused, because minting a
second card for one reference is the worse failure. `codeLast4` reads Wix's own `codeSuffix` and
refuses with `CODE_SUFFIX_MISSING` rather than slicing the obfuscated bearer code.

Code derivation is keyed where it must be. `card_code` is `hmac(pepper, CODE_DOMAIN_TAG +
reference_id)`, domain-tagged on the message so it cannot collide with `gift_card_store.code_hash`
under the same pepper, pepper keyword-only with no default and pinned that way by an AST test.
`idempotency_key` is deliberately unkeyed and therefore rotation-invariant, and a test asserts in
both directions that the production code is not recoverable from it. `demo_code` is unkeyed and
fenced by a structural test that walks `ast.Name`/`ast.Attribute`/`ast.ImportFrom` under
`amplify/` — references, not definitions, so the adapter needs no exemption.

The concurrency fix is right and its gate is not vacuous. The balance move and the `settled` flag
commit as two `Update` items in one transaction, with the card gated on `balancePaise >= :amount`
and the claim on `settled = :false`, so the overdraw guard and the per-attempt idempotency guard
stay distinguishable. `_commit_redemption` returns `(balance, committed)` — the implementation
found its own defect here, where the losing thread answered `committed: True` for money it did not
move. The pre-fix store was loaded from git at `32b632e3` and driven through the identical forced
schedule, reporting 200000 paise where post-fix asserts 350000 and two `committed=True`.

Test harness quality is high and the stubbing choices are deliberate: the boundary is cut at
`urlopen` so header composition and `json.loads` without `parse_float` all execute for real, the
response queue is typed by method and path so a second create cannot silently consume a queued
query response, `Authorization` is redacted at capture rather than at render, and the refusal is a
`BaseException` precisely because `wix_ecom._request` and `coupons/handler._create` would otherwise
launder an `AssertionError` into a 202.

Two defects sit in the demo's containment, both in the same function and both about evidence
integrity rather than production behaviour: the AWS-call count proves nothing, and the globals it
mutates are never put back.

One thing the transcript cannot claim as strongly as it reads: the full `idempotencyKey` is
printed, and `demo_code` is derivable from it — the suite asserts exactly that (`assert demo in
key`). Production is unaffected, since `card_code` is HMAC-keyed, but "no clear bearer-value code
in the transcript" is true of the literal string and not of the information.

<details>
<summary>Issues (6)</summary>

1. **The demo's AWS-call count is tautological** — `_count_aws_calls()` is called after all legs
   complete, registers the `before-send` hooks, then returns a counter that was initialised in the
   same call. Move the hook installation into `_install_containment()` (before leg 1) and keep the
   counter where both can reach it, so `AWS API calls attempted` reflects the run. Design §4.3
   requires a leg call to fail the demo, not be tallied afterwards.
2. **`urllib.request.urlopen` is never restored** — `_install_containment()` assigns the stub
   globally and nothing puts the original back, and `tests/test_demo_coupon_giftcard_sample.py`
   runs `main()` in-process, so every later test file in the session sees a drained
   `WixTransport` that raises `BaseException`. Save and restore in `main()`, or patch it in the
   test's fixture instead of inside the script.
3. **The leaked botocore hooks outlive the test** — the `before-send` handler is registered on
   long-lived clients (`lambda_utils.middleware.cognito`, `lambda_utils.rate_limit.dynamodb`) and
   never unregistered, so any later test that exercises those clients for real gets an
   uncatchable `UnexpectedAwsCall`. Unregister on the way out, or register inside a context the
   test controls.
4. **The printed idempotency key discloses the demo code** — mask it in the transcript, or state
   the reconstructability at the point where verification.md claims "zero occurrences of the clear
   20-character code", so the claim is not read as stronger than it is.
5. **Five fetches or six** — `findings.md` says "Six fetches of the live `dev.wix.com` markdown
   rendition"; `docs/execution/wix-contract-verification-20261002.md` tabulates five and says so
   twice. Reconcile the count in `findings.md`.
6. **`credit()` lost its `once_key` with no replacement** — correct today (no production caller),
   but a top-up route added later inherits a non-idempotent money function. Worth a line in the
   docstring naming where idempotency has to be provided instead.

</details>

<details>
<summary>Details</summary>

## The AWS containment proves less than it prints

`main()` runs the legs and only then calls `_count_aws_calls()`:

```python
transport = _install_containment()     # key cache, boto3 sabotage, urlopen
try:
    ... three legs ...
    transport.assert_drained()
except BaseException as error:
    ...
aws_calls = _count_aws_calls()         # registers the hooks, THEN returns the count
```

`_count_aws_calls` creates `attempted = {"count": 0}`, walks two client paths, calls
`target.register("before-send", refuse)` and returns `attempted["count"]`. Nothing can increment
that counter between its creation and its return, so `aws_calls` is `0` by construction. The
consequence is that `return 1 if mismatches or aws_calls else 0` has a dead second clause, the
rendered line `AWS API calls attempted = 0` is a statement about an empty dict, and the line
beneath it — "a before-send hook would fail the run" — is false for the run just printed, because
the hook did not exist while the legs executed.

The hook targets do resolve, measured in a throwaway process after `main(['--json'])` returned
exit 0: `middleware.cognito.meta.events` and `rate_limit.dynamodb.meta.client.meta.events` both
resolve to an `EventAliaser`. So the mechanism works; it is installed at the wrong moment. The
`sys.modules["boto3"]` sabotage *is* installed before leg 1 and does real work — it would catch a
lazily-imported client construction — but the clients that matter here are built at handler import
and reached through live objects the sabotage cannot see.

This is the one artifact the retirement gate hangs on, and `findings.md` makes the case itself:
"a false structural claim in the one artifact whose purpose is to be trusted is worse than no
claim." It then repeats the claim in the transcript table ("`AWS API calls attempted = 0` |
enforced by a `before-send` hook raising a `BaseException`, not observed"). Design §4.3 is explicit
that "a call that would leave the process **fails the demo** rather than being tallied
afterwards", so this is a deviation rather than a judgement call.

The fix is small: install the hooks in `_install_containment()`, hold the counter where both
functions can read it, and have `_count_aws_calls()` only read. Then the printed `0` means
something and `verification.md` §10 can keep its wording.

## The demo's globals are not put back

`_install_containment()` mutates three process-global things and registers event hooks:

```python
wix_ecom._key_cache["key"] = PLACEHOLDER_API_KEY
sys.modules["boto3"] = _ExplodesOnAttributeAccess()
urllib.request.urlopen = transport
```

Under pytest the first two are covered, because the `demo` fixture wraps them in
`monkeypatch.setitem` and teardown restores the real values. `urlopen` is not: the fixture never
touches it, the script assigns it directly, and after `main()` returns the global is still the
`WixTransport` — confirmed by inspection after an in-process run. Its queue is drained, so any
subsequent `urlopen` call raises `UnexpectedWixCall`, which is a `BaseException` and therefore
escapes every `except Exception` in the tree.

Nine other test modules reference `urlopen`, and all of them sort after `test_demo_*`
alphabetically. They pass today because each patches `urlopen` itself, which overwrites the
polluted global for the duration. That is luck of construction, not isolation: a test that calls
`urlopen` without its own patch would fail in a way that names the wrong module, and a test
asserting "no network call happens" could pass because the stub refused rather than because the
code abstained.

The registered `before-send` hooks have the same shape and no restore at all. They live on
module-level clients that persist for the whole session, and `main()` is called five times across
the demo test file, so the handlers accumulate. `test_rate_limit.py` patches
`lambda_utils.rate_limit.dynamodb` wholesale with a `MagicMock`, so the real client carrying the
hooks is bypassed and nothing breaks today — again latent rather than active.

## The transcript's bearer-value claim, stated precisely

`demo_code(reference_id)` is `"WDGC" + sha256(reference_id).hexdigest()[:16]` upper-cased, and
`idempotency_key(reference_id)` is `"wd-gc-" + sha256(reference_id).hexdigest()`. The demo masks
the code everywhere — summary line, create body, query filter, both directions — and prints the
idempotency key in full. The two expose the same digest, so the masked code is recoverable from the
printed key by stripping decoration and upper-casing.

This is not hidden. The `demo_code` docstring states it as the "true and dangerous property",
names the shared fragment, and the harness asserts it positively:

```python
assert demo in key, (
    "demo_code and idempotency_key expose the same unkeyed sha256 digest of the same "
    "input, so either value yields the other - that is why demo_code is fenced from "
    "amplify/ by a structural guard")
```

Production is unaffected, and that asymmetry is the point: `card_code` is HMAC-keyed, so the same
test asserts `keyed not in key` and `key not in keyed`. The only thing to correct is wording.
`verification.md` §10 reports `grep -c "$(the clear 20-char demo code)"` returning `0` for both
renderers and concludes "**no clear bearer-value code**". Literally true, informationally not, and
a reader who skips the docstring will take the stronger reading.

## The transaction fix — the parts that are not obvious

The card item gates on `balancePaise >= :amount`, the claim item on `settled = :false`, and the
card deliberately does *not* gate on the claim, so a genuinely different second purchase of the
same card still deducts. `test_two_different_payment_attempts_still_debit_twice_under_concurrency`
is the guard against the fix turning a customer's second purchase into a refusal — the property
most likely to be silently traded away in a change like this.

`_cancellation_reason_codes` reads `CancellationReasons` at the response top level, with the
docstring recording that reading it from `response["Error"]` yields `[]` on every real
cancellation and would convert the fix's main path into a 5xx. `_transact_with_retry` re-raises a
non-retryable cancellation unchanged and converts only exhausted contention into
`GiftCardStoreUnavailable`, so a condition outcome is never reported as an outage.

`_commit_void`'s explicit `attribute_exists(credited)` is the subtle one: a bare `credited =
:false` accepts the same set but is not diagnosable, so a void predating the flag would fall
through to `GiftCardStoreUnavailable` and the card would become permanently un-voidable.
`test_a_transaction_row_with_no_credited_attribute_is_refused_and_the_balance_is_untouched` pins
the three-valued reading.

`_record_balance_after` is a best-effort follow-up `UpdateItem`, because `TransactWriteItems`
returns no `ALL_NEW`. `redeem`'s docstring carries the consequence: `remainingBalancePaise` is an
observation that may already include a later interleaved move, and only `amountPaise` is exact.
That figure is customer-visible through the SPI's `remainingBalance`, so the caveat belongs at the
function and is there.

IAM was left alone and the reasoning is now pinned rather than assumed: `TransactWriteItems` is
authorized through its items' actions, two `Update` items need `dynamodb:UpdateItem` which both
roles already grant, and `dynamodb:ConditionCheckItem` is unnecessary because the transaction
carries no `ConditionCheck` item — which `assert_transaction_items_are_exact_key_updates` keeps
true by asserting each item's key set is exactly `{"Update"}`.

Removed symbols leave nothing dangling: `_decrement`, `_mark_settled`, `_mark_credited`,
`_drop_applied_marker`, both `APPLIED_*` prefixes and `credit()`'s `once_key` have no remaining
reference under `amplify/`, `tests/` or `scripts/`. `credit()` has no production caller at all,
which is what makes dropping its idempotency safe today; the docstring argues a genuine top-up must
not be idempotent, but does not say where idempotency has to live instead. One stale test name
still reads `..._settled_by_the_decrement...` for a path that no longer has a `_decrement`.

## The three MEDIUMs are fixed in mechanism, not in prose

`arm_failure(operation, exc, *, times=1)` stores `(exc, times)` and `_fail_if_armed` decrements,
popping only at the last use — a real re-arm, where the previous `pop`-on-first-use produced one
failure and made the second `pytest.raises` fail against correct code. The default keeps every
existing call site unaffected.

`_is_balance_move`, `_committer_of` and `_committers` exist in `tests/test_gift_card_store.py` with
real signatures and are imported by name from the concurrency module. `_committer_of` distinguishes
`:neg` from `:amount` and **raises** for a transaction that moves no balance, so a third kind of
transaction cannot be absorbed into a set comparison. "Neither committer silently missing" is also
measured structurally: `test_the_transaction_has_exactly_one_call_site_and_two_callers` asserts one
`transact_write_items` call, its owning `FunctionDef` is `_transact_with_retry`, and that wrapper's
callers are exactly `{_commit_redemption, _commit_void}` — the last via its own `ast.Name`
predicate, since the existing gate finds only attribute calls.

§5.5's six-row table is followed, verified mechanically: six `assert seen >= n` sites across the two
files, each paired with a committer-set assertion, and `grep -nE 'seen == [0-9]'` across `tests/`
returns nothing.

The concurrency barrier latches on "a balance-moving call" rather than on a helper name, so one
subclass forces the identical schedule pre- and post-fix; latching on a helper the fix deletes
would have degraded the test into an unsynchronised race that passes for the wrong reason. Both
counts are asserted — 2 attempts in `calls`, 1 landed in `applied` — and each latch waits before
delegating to `super()`, so the fake's `RLock` is never held across a wait.

## Verification evidence

Sufficient to review without re-running. The baseline was measured in this worktree at `32b632e3`
before any edit, the full suite's 5 failures reconcile exactly against the two known baseline
files, build runs before vitest because vitest depends on `out/`, the concurrency file was run five
times to show the schedule is forced rather than timed, and the pre-fix store was loaded from git
and driven through the identical schedule (200000 where post-fix asserts 350000, two
`committed=True`). The triage table applies the right rule: a behaviour assertion had to pass
untouched, and only the one mechanism assertion — a fault-injection point moving from `update_item`
to `transact_write_items` — was rewritten, with every assertion in that test unchanged.

NITs 4 and 5 were dropped because both ask for edits to a frozen design document and change no
code. NIT 7's two deleted fault injectors are mapped to their five call sites.

The contract transcript records URL form per fetch (the pre-revision-5 URL set now returns a
schema-free shell, so a re-run against the old form reads *absent* when the fact is *present*),
byte sizes, and V1 as a count with `grep`'s own exit status so an absence reads as a search that
found nothing. It states its own limitation: the markdown rendition renders no `Errors` section for
any method, so `SITE_IS_NOT_PREMIUM` is neither confirmed nor contradicted and is not carried as a
measured fact.

## The retirement gate

Correctly not taken. Nothing was deleted, and the STOP note names three specific ways the live call
could still fail rather than hedging: API-key scope over `/gift-cards/v1/`, the premium-plan
dependency on the create path, and the response shape for a 20-character unhyphenated code where
the obfuscated `code` is documented only through a hyphen-grouped example. The sequencing is stated
the safe way round — wire the adapter in before deleting the store, never after.

The adapter being unwired is enforced rather than intended:
`test_no_handler_imports_the_wix_native_adapter` walks every Python file under `amplify/` and
asserts no `wix_gift_cards` import exists, so the module cannot reach production by drift, and it
ships in no Lambda package until a handler imports it.

Coupon Option B holds. `test_a_replayed_coupon_issue_converges_on_one_coupon` drives
`handler.handler` rather than `_create`, so it measures the answer a caller gets rather than the
raise, queues nothing for the replay so a second Wix create would raise an uncatchable
`UnexpectedWixCall`, and asserts one create call, one definition row and the preserved
`wixCouponId`. The replay answers 409 `CODE_ALREADY_EXISTS` rather than echoing the first coupon,
which is convergence on one coupon in the ledger sense the design asks for.

</details>

<details>
<summary>File map</summary>

| File | Change |
|---|---|
| `amplify/.../ecommerce/wix_gift_cards.py` | new — the four-call Wix gift-card adapter, injected request callable, deliberately unwired |
| `amplify/.../ecommerce/gift_card_store.py` | the two committers collapsed into one `TransactWriteItems` each, `_marshal`, cancellation-reason reading, bounded retry; four helpers and both `APPLIED_*` prefixes removed |
| `scripts/demo_coupon_giftcard_sample.py` | new — three legs, offline, Wix stubbed at `urlopen`; the containment defects above live in `_install_containment`/`_count_aws_calls` |
| `tests/wix_transport_stub.py` | new — typed response queue, `Authorization` redacted at capture, refusal is a `BaseException` |
| `tests/coupon_fake_dynamo.py` | `RLock`, an `applied` outcome log, `transact_write_items` in the real low-level shape, `FakeClientError(cancellation_reasons=)`, `arm_failure(times=)` |
| `tests/test_wix_coupon_giftcard_sample.py` | new — 58 tests, groups A–D, including the keying, fencing and no-logger structural gates |
| `tests/test_gift_card_redeem_concurrency.py` | new — four forced-schedule tests plus the must-not-regress second-purchase case |
| `tests/test_demo_coupon_giftcard_sample.py` | new — the demo's anti-rot enforcer, runs `main()` in-process |
| `tests/test_gift_card_store.py` | two retire-and-replace, three rewrites, three structural tests, three new helpers |
| `tests/test_gift_card_two_leg_finalization.py` | one line: the fault injection point moved to the transaction |
| `tests/test_gift_cards_iam_and_table.py` | both ledger statements pinned to an exact action set |
| `tests/fixtures/wix_*.json` | 9 response fixtures built from the documented examples |
| `docs/execution/wix-contract-verification-20261002.md` | new — the four verdict rows re-measured, with URL form, status and byte size per fetch |
| `.agents/tasks/.../{findings,verification,wix-native-decision-memo}.md` | the STOP note, the run record, the owner page |

Full diff: `git -C /Users/wecaredigital/wecare-store/.worktrees/wix-coupon-giftcard-sample-20261002 show 2ec1b7f1`

</details>
