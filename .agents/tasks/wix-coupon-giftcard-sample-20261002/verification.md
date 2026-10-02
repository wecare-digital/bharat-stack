# Verification — what was run, and what it reported

Worktree `wix-coupon-giftcard-sample-20261002`, branch `wix-coupon-giftcard-sample-20261002`,
based on `stack` at `32b632e3`. Written so a reviewer does not have to re-run anything.

Interpreter throughout: `/Users/wecaredigital/wecare-store/.venv/bin/python` (3.12.14). The
worktree has no `.venv` of its own; the one that satisfies `conftest.py` lives in the parent
checkout. A bare `python3` is not a valid baseline.

## 0a. Review iteration — the five findings from `code-review.json`, and where each is answered

Every number below was re-measured after the fixes; nothing in this document is carried over from
the first pass without being re-run.

| # | Severity | Finding | Fix | Evidence |
|---|---|---|---|---|
| M1 | MEDIUM | the AWS-call count was tautological — `_count_aws_calls()` created the counter and registered the hook in the same call, after every leg | hook armed in `_install_containment()` before leg 1, counter at module level, `_count_aws_calls()` reduced to a read, re-armed once after the handler import (idempotent by target identity) | §10, including the mutation run that shows the assertion fails on the pre-fix shape; `test_an_aws_call_during_a_leg_fails_the_run_rather_than_being_counted_afterwards` |
| M2 | MEDIUM | `urllib.request.urlopen` replaced globally and never restored | `_install_containment()` returns a `restore` closure; `main()` calls it in a `finally`. `sys.modules["boto3"]` and `wix_ecom._key_cache["key"]` restored the same way, with a `_MISSING` sentinel so "was absent" and "was `None`" stay distinct | §10; `test_the_demo_puts_back_every_global_it_touched`, asserted over two consecutive runs |
| M3 | MEDIUM | the botocore `before-send` hooks outlived the test session on module-level clients | `_disarm_aws_refusal()` unregisters every hook the run installed, from the same `finally` | §10; the same test emits `before-send` on both event systems after the run and nothing raises |
| L1 | LOW | the printed idempotency key disclosed the demo code, so "no clear bearer-value code" was stronger than the fact | the key is masked in the summary line **and** in the rendered create body; the length is still printed; the reason is stated at the point the grep result is reported | §10's "informational, not merely literal" paragraph; `test_the_transcript_carries_no_clear_idempotency_key_either`, which measures the shared digest fragment in both casings |
| L2 | LOW | `findings.md` said six documentation fetches; the transcript tabulates five | corrected to five, with the page numbers named | `findings.md` "What IS proven" |
| L3 | LOW | `credit()` lost its `once_key` with no statement of where idempotency must live; one stale test name | docstring now names the required shape and home for a top-up caller's guard, and says why a pre-read check is not a substitute; test renamed to `test_the_claim_row_is_settled_in_the_same_transaction_...` with the rename's reason in its docstring | `gift_card_store.credit` docstring; `tests/test_gift_card_store.py` module docstring and the test |

No LOCKED decision moved: coupons stay Option B, gift cards stay Wix-native-by-design and
unwired, the retirement stays **not taken**, and loyalty/referral stays out of scope. Nothing in
this iteration changes behaviour a user could observe — the only runtime change is to a
development-only script and to a docstring.

## 0b. Second review iteration — the two findings from the `d7ef5583` pass

| # | Severity | Finding | Fix | Evidence |
|---|---|---|---|---|
| M4 | MEDIUM (blocking) | the demo cited `test_the_aws_refusal_hook_is_armed_before_the_first_leg` as the measurement of its containment-time arming, and that test existed nowhere in the tree | the cited test is now **implemented**, under exactly that name, in `tests/test_demo_coupon_giftcard_sample.py`. It measures the property both ways the review named: both `_HOOK_PATHS` targets resolve on a bare import (so `_arm_aws_refusal([])` returns 2 at containment time), and the hook is live inside `--leg wix-giftcard`, per path — the leg that re-arms nothing | the mutation run below; `+1` on the suite total |
| L4 | LOW | the coupon idempotency test's docstring justified `coupon_store` with "no `idempotencyKey` **and no read-by-code**", contradicting row V2b of this change's own contract transcript | the docstring now rests on the `idempotencyKey` absence alone, which is the fact carrying verdict (B), and states explicitly that read-by-code is NOT part of the rationale, citing V2b | `tests/test_wix_coupon_giftcard_sample.py::test_a_replayed_coupon_issue_converges_on_one_coupon` docstring |

### M4 — the mutant, so the new test is not vacuous

The review's own words were that the property is true today but unpinned, and that the existing
`test_an_aws_call_during_a_leg_...` cannot substitute because it emits from leg 3, after
`_leg_coupon` has re-armed. That is exactly what the mutation shows. Arming was deferred out of
containment time, one line, leaving the re-arm inside `_leg_coupon` intact:

```
-    armed: list = _arm_aws_refusal([])
+    armed: list = []   # MUTANT - arming deferred out of containment time

$ .venv/bin/python -m pytest tests/test_demo_coupon_giftcard_sample.py -q \
      -k "armed_before_the_first_leg or during_a_leg"
FAILED tests/test_demo_coupon_giftcard_sample.py::test_the_aws_refusal_hook_is_armed_before_the_first_leg
  assert 0 == 1            # the wix-giftcard leg ran UNHOOKED and returned a clean transcript
1 failed, 1 passed, 18 deselected in 0.20s
```

The `1 passed` is the point as much as the failure: the pre-existing containment test passes on
the mutant, so before this iteration nothing in the suite could tell an armed run from an
unarmed one for the two legs that never re-arm. The mutant was reverted and the revert confirmed
by `git diff --stat scripts/demo_coupon_giftcard_sample.py` being empty before the comment edit.

Also narrowed, since the citation is the thing under repair: the `_HOOK_PATHS` comment now says
what the test asserts rather than only that a test exists.

### L4 — one place the same stale clause survives, named rather than quietly edited

`grep -n 'read-by-code' .agents/tasks/.../*.md` finds it twice more, at `plan.md:27` and
`plan.md:631`. Those are **not** edited, deliberately: the plan is the dated artefact the build
was run from, V2b of `docs/execution/wix-contract-verification-20261002.md` is the correction of
record and already says the clause did not survive measurement, and rewriting a planning document
after the fact would erase the evidence that the measurement changed the reasoning. The finding's
concern was the text a reader finds **beside the code** when deciding whether `coupon_store` can
be dropped, and that text is the docstring, which is fixed. Nothing in either `plan.md` line is
load-bearing for verdict (B), which rests on V1 alone.

## 0. The baseline, measured in this worktree at `32b632e3` BEFORE any edit

```
$ .venv/bin/python -m pytest tests/test_gift_card_store.py tests/test_coupon_store.py \
    tests/test_wix_coupons_contract.py tests/test_coupon_reconciliation.py \
    tests/test_gift_card_two_leg_finalization.py tests/test_gift_card_spi_contract.py \
    tests/test_gift_card_amounts_and_gst.py tests/test_gift_cards_iam_and_table.py -q
315 passed, 7 xfailed in 0.69s
```

## 1. Known test baseline — NOT this change's regressions

Five pre-existing pytest failures, confirmed present both before and after:

| File | Failures |
|---|---:|
| `tests/test_url_host_routing_rules.py` | 4 |
| `tests/test_legacy_redirect_rollback_snapshot.py` | 1 |

`wecare/google-maps-server:api_key` is an expired, unrelated secret and is ignored.

## 2. Full pytest — the whole suite

```
$ .venv/bin/python -m pytest -q
5 failed, 6882 passed, 1 skipped, 7 xfailed in 60.40s

FAILED tests/test_legacy_redirect_rollback_snapshot.py::test_owner_policy_preserves_rewrites_without_restoring_legacy_destinations
FAILED tests/test_url_host_routing_rules.py::test_only_host_canonicalisation_is_an_explicit_redirect
FAILED tests/test_url_host_routing_rules.py::test_converged_configuration_is_not_rewritten
FAILED tests/test_url_host_routing_rules.py::test_unknown_redirect_removed_without_touching_proxy_rules
FAILED tests/test_url_host_routing_rules.py::test_saved_pre_removal_configuration_reconciles_to_post_removal_snapshot
```

**Against the baseline: exactly the 5 known failures, in exactly the 2 known files. No sixth
failure, so this change introduced no regression.** 6,882 passed — re-run after the second review
iteration, `+1` on the 6,881 of the first fix pass, which is exactly M4's one added test (6,878
at the original pass, `+3` for the first iteration's three, `+1` for this one). The two baseline
files hold the same 5 failures in all three runs.

## 3. The design §7 focused set

```
$ .venv/bin/python -m pytest tests/test_wix_coupon_giftcard_sample.py \
    tests/test_demo_coupon_giftcard_sample.py tests/test_gift_card_redeem_concurrency.py \
    tests/test_gift_card_store.py tests/test_gift_card_two_leg_finalization.py \
    tests/test_gift_card_spi_contract.py tests/test_gift_card_amounts_and_gst.py \
    tests/test_gift_cards_iam_and_table.py tests/test_wix_coupons_contract.py \
    tests/test_coupon_store.py tests/test_coupon_reconciliation.py \
    tests/test_payment_vocabulary_at_decision_points.py -q
457 passed, 7 xfailed in 2.12s
```

Reconciled against the baseline: 315 + 7 xfailed over 8 files → 457 + 7 xfailed over 12 files.
The 142 additional passes are this change's new tests (58 harness + **20** demo + 4 concurrency)
plus the 3 structural tests and 1 IAM test added to existing files, and the 7 xfailed are unmoved.
The demo file carried 16 tests at the first review and 19 after the first fix pass — the three
then added were the AWS-enforcement mutation test, the global-restoration test and the
idempotency-key disclosure test; the 20th is M4's
`test_the_aws_refusal_hook_is_armed_before_the_first_leg`.

## 4. Build before vitest — the `out/` artifact dependency

`npm ci` was run first: this worktree had no `node_modules` at all, so the build and vitest were
unrunnable here until it was. That is a worktree-environment gap rather than a regression, and it
is recorded because "vitest was not run" and "vitest could not be run" are different statements.

```
$ npm ci                                        # worktree had no node_modules
$ npm run build
  ... Public sitemap: 1411 URLs (1323 blog posts) -> out/sitemap.xml
      Blog search index: 1323 posts, 462 kB -> out/blog/search-index.json
      llms.txt: 26 pages, 1323 articles -> llms.txt (7 kB), llms-full.txt (310 kB)
  exit 0

$ npx vitest run
 Test Files  65 passed (65)
      Tests  812 passed | 1 skipped (813)
   Duration  6.68s
```

Build **before** vitest, in that order, because vitest depends on the `out/` artifact.

Re-run unchanged in the second review iteration — `npm run build` exit 0 (same 1,411-URL sitemap
and 1,323-post index), then `npx vitest run` at 65 files / 812 passed / 1 skipped in 6.65s. Both
numbers are identical because nothing in this iteration touches TypeScript; the gate is re-run
rather than cited so the record is of this tree and not the previous one.

**No `.ts`/`.tsx`/`.js`/`src/**` file is in this change's footprint** —
`git status --short -- src '*.ts' '*.tsx' '*.js'` is empty — so this is a whole-repo gate rather
than a test of anything changed here.

## 5. The concurrency fix, gated at RUNTIME and not vacuously

The requirement is that the concurrent-redeem test **fails pre-fix and passes post-fix**. Both
halves were measured rather than asserted.

**Post-fix**, run five times in a row to confirm the schedule is forced rather than timed:

```
$ for i in 1 2 3 4 5; do .venv/bin/python -m pytest tests/test_gift_card_redeem_concurrency.py -q; done
4 passed in 0.12s
4 passed in 0.11s
4 passed in 0.11s
4 passed in 0.11s
4 passed in 0.11s
```

**Pre-fix.** The original store was loaded straight out of git
(`git show 32b632e3:...gift_card_store.py`) into a separate module and driven through the
identical forced schedule — same three `threading.Event`s, same two-override latching subclass,
same amounts:

```
PRE-FIX store (32b632e3):
  balancePaise         = 200000   (post-fix asserts 350000)
  balance moves tried  = 2
  balance moves landed = 2        (post-fix asserts 1)
  committed=True count = 2        (post-fix asserts 1)
  errors               = {}
VERDICT: FAILS pre-fix as required
```

So the gate is live: a card worth 500000 paise, redeemed 150000 twice under **one**
`paymentAttemptId`, ended at 200000 instead of 350000, and both callers reported
`committed: True`. That is the double debit, and the test catches it.

**One real defect was found by this test during implementation and fixed.** The first version of
`_commit_redemption` returned a bare balance on the lost-race branch, so thread B — whose
transaction was correctly cancelled on `settled = :false` — still answered `committed: True`. The
money moved once, but two callers each claimed to have moved it: a self-consistent ledger saying
something false, which is the failure class this section exists to remove. The committer now
returns `(balance, committed)` and `redeem()` takes the replay branch, writing no second `GCTXN#`
row.

## 6. The three open MEDIUMs

**(1) `FakeTable.arm_failure` re-arm count mismatch — fixed with a real mechanism.**
`_fail_if_armed` consumed the arm with `self.fail_on.pop(operation, None)`, so two
`arm_failure` calls before two operations produced **one** failure and the second
`pytest.raises` then failed against **correct** code. `arm_failure(operation, exc, *, times=1)`
now holds a decrementing counter. `times=` was chosen over re-arming between the two `void()`
calls because it keeps the arming visible at the arming site instead of hiding a re-arm in the
middle of a test body, and it makes the test's own narrative ("armed twice") literally true. The
default keeps all seven importers unaffected — proved by §0's 315 passes staying 315 immediately
after the fake was edited and before anything else changed.

The citation the design got wrong is recorded in the docstring: the `pop` is in
**`_fail_if_armed`**, not in `arm_failure`.

Exercised by `test_a_void_credit_that_fails_twice_still_returns_the_balance_exactly_once`, which
arms `times=2` and asserts the balance is untouched after **each** of the two failures.

**(2) `_committer_of` / `_is_balance_move` — implemented, with real signatures and a real home.**
Both were named in the design and absent from the tree. They now live in
`tests/test_gift_card_store.py` beside `assert_transaction_items_are_exact_key_updates`, and are
imported **by name** from `tests/test_gift_card_redeem_concurrency.py`:

```python
def _is_balance_move(call: tuple) -> bool      # matches update_item OR transact_write_items
def _committer_of(kwargs: dict) -> str         # "redeem" | "void", RAISES otherwise
def _committers(store: FakeTable) -> set
```

`_committer_of` **raises `AssertionError`** for a transaction that moves no balance rather than
returning a sentinel — a sentinel would be absorbed silently into a set comparison, so a third
kind of transaction appearing on this path would pass unnoticed.

The "neither committer silently missing" property is measured **two** independent ways, so it
does not rest on the helper alone:

- **structurally**, by `test_the_transaction_has_exactly_one_call_site_and_two_callers`: exactly
  one `transact_write_items` call in the module, its owning `FunctionDef` is
  `_transact_with_retry`, and `_transact_with_retry`'s callers are exactly
  `{_commit_redemption, _commit_void}`. Fact 3 needs its own `ast.Name` predicate, because the
  existing gate finds only attribute calls;
- **at runtime**, by the committer-set assertions on all six callers.

**(3) §5.5's stale "one definition, four callers" — the authoritative six-row table is followed.**
Taking the sentence literally would leave two transaction-driving tests unchecked. The six
callers, each asserting `seen >= 1` or `seen >= 2` plus a committer set and **no literal
transaction total**:

| Caller | Assertion | Committers |
|---|---|---|
| `test_a_second_redeem_for_the_same_payment_attempt_does_not_move_the_balance` | `seen >= 1` | `{"redeem"}` |
| `test_the_settle_and_the_balance_move_are_one_commit` | `seen >= 1` | `{"redeem"}` |
| `test_the_credit_and_the_credited_flag_are_one_commit` | `seen >= 2` | `{"redeem","void"}` |
| `test_a_void_whose_credit_failed_is_completed_by_a_retry_not_refused` | `seen >= 2` | `{"redeem","void"}` |
| `test_a_void_credit_that_fails_twice_still_returns_the_balance_exactly_once` | `seen >= 2` | `{"redeem","void"}` |
| `test_two_concurrent_redeems_for_one_payment_attempt_debit_once` | `seen >= 2` | `{"redeem"}` |

Checked mechanically:

```
$ grep -nE 'seen == [0-9]' tests/test_gift_card_store.py
(no output — no literal transaction total survived)

$ grep -c 'assert_transaction_items_are_exact_key_updates' tests/test_gift_card_store.py
7            # the definition + 5 in-file callers + 1 docstring reference
```

The helper reads `calls` (the **attempt** log), not `applied` (the **outcome** log), so a
**cancelled** attempt is still shape-checked — and the concurrency test is the one caller that
exercises that choice, since its recording contains thread B's cancelled transaction. It also
**refuses an empty recording first**, so it can never pass vacuously; that is why the shape check
in `..._does_not_move_the_balance` runs before `store.calls.clear()` rather than after.

## 7. The four NITs

| NIT | Disposition |
|---|---|
| 4 — §16's stale "four transaction-driving tests" lacks a superseded annotation | **dropped**, design frozen at rev 8; superseded in effect by following the six-row table |
| 5 — §8's Modified row dates its own previous count to the wrong revision | **dropped**, design frozen; a changelog dating error changes no code |
| 6 — three line citations off by two or three | **applied**: re-measured at `32b632e3` as `:289`, `:276-294` and `:295`. Both substantive claims underneath were correct |
| 7 — `_CreditThrottles` / `_MarkerWriteFails` caller fates unstated | **applied**: both classes deleted, call sites mapped below |

**NIT 7's call-site map, so no reader has to rediscover it.** `_CreditThrottles` (`:631`) was used
only at `:675` and `:714`, both rewritten to arm the transaction, so it lost **both** callers.
`_MarkerWriteFails` (`:394`) was used at `:440` and `:745` (both retired-and-replaced) and `:478`
(rewritten to be driven by a settled claim), so it lost **all three**. A fault injector with no
caller misleads the next reader exactly as a constant with no caller does, so both are gone.

## 8. The retired-and-replaced tests, and the stronger property each now asserts

Retiring a test is the step most likely to be mistaken for making a build green, so both
replacements assert something **stronger** rather than nothing.

| Retired | Replaced by | The stronger property |
|---|---|---|
| `test_a_redemption_whose_settle_write_failed_debits_the_balance_exactly_once` | `test_the_settle_and_the_balance_move_are_one_commit` | not "the recovery works" but **there is no interleaving in which the balance has moved and the claim is unsettled** — one transaction carries both, and neither half survives as a separate `update_item` |
| `test_a_void_whose_credited_write_failed_returns_the_balance_exactly_once` | `test_the_credit_and_the_credited_flag_are_one_commit` | the same, for the void side, **plus** the rehoused property that a second `void()` of the same transaction credits nothing — 50000, not 90000 |

Rewritten in place, same names, same answers:
`test_a_stalled_redemption_still_debits_once_when_another_purchase_lands_between` (now driven by a
settled claim plus an intervening different purchase, which is the post-fix route to that state),
`test_a_void_whose_credit_failed_is_completed_by_a_retry_not_refused` and
`test_a_void_credit_that_fails_twice_still_returns_the_balance_exactly_once` (fault aimed at the
transaction; a bare throughput `FakeClientError` is **not** a cancellation, so
`_transact_with_retry` re-raises without looping and the test's own next `void()` call **is** the
retry). Every answer in those three is identical to the pre-fix answer, which is the check that
the rewrite preserved the property rather than replacing it.

`test_an_applied_move_marker_does_not_outlive_the_move_it_guards` keeps its name and asserts the
stronger fact: **no** `appliedClaim#`/`appliedVoid#` attribute is written anywhere, on any row,
or in any recorded call — so item size is bounded by construction rather than by a cleanup step.

Re-run **without edit** and still green, as required:
`test_a_void_latched_before_the_credited_flag_existed_is_never_re_credited`,
`test_the_store_holds_no_boto3_client_and_reads_no_secret_itself` and
`test_no_float_is_constructed_anywhere_on_the_store_money_path`. The last is *affected* — it drives
a full redeem/void cycle through the new path — and an affected test nobody ran is
indistinguishable from an unaffected one, so it was run deliberately:

```
$ .venv/bin/python -m pytest tests/test_gift_card_store.py -q -k "holds_no_boto3 or no_float_is_constructed"
2 passed, 59 deselected
```

## 9. Triage of the affected consumers — one edit, and it was a mechanism assertion

Rule applied: an assertion about **behaviour** must pass unchanged, and a failure there is a
defect in the fix rather than a test to update; only an assertion naming the **mechanism** may be
rewritten, and the rewrite must preserve the property in the same breath.

| File | Outcome |
|---|---|
| `tests/test_gift_card_two_leg_finalization.py` | **one line changed.** `arm_failure("update_item", ...)` → `arm_failure("transact_write_items", ...)` in `test_a_redemption_failure_after_capture_lands_in_needs_reconciliation`. Only the **injection point** moved; every assertion is untouched, which is what shows the property was preserved. 110 other passes unchanged |
| `tests/test_gift_card_spi_contract.py` | no change needed — green |
| `tests/test_gift_card_amounts_and_gst.py` | no change needed — green |
| `tests/test_coupon_store.py` | no change needed — green |
| `tests/test_coupon_reconciliation.py` | no change needed — green |
| `tests/test_wix_coupons_contract.py` | no change needed — green |
| `tests/test_payment_vocabulary_at_decision_points.py` | no change needed — green |

The three coupon files were listed for one reason: a surprise there would be a **defect in the
fake**, not noise. There was none.

Two production callers of the changed signatures, both unaffected because the parameters are
defaulted or removed-with-their-only-caller: `wix-giftcard-spi/handler.py:310` (`store.redeem`)
and `:341` (`store.void`). Neither passes `sleep`; neither passed `once_key`.

## 10. The demo

```
$ .venv/bin/python scripts/demo_coupon_giftcard_sample.py --no-colour
... 3 legs, 0 contract mismatches
exit 0

$ .venv/bin/python scripts/demo_coupon_giftcard_sample.py --json > /dev/null
exit 0

$ .venv/bin/python scripts/demo_coupon_giftcard_sample.py --value-paise 100 --redeem-paise 200
exit 2

$ .venv/bin/python scripts/demo_coupon_giftcard_sample.py --coupon-money-off-paise 12345
exit 2            # not a whole number of rupees
```

The full transcript is in `findings.md`. The disclosure checks on its output, re-measured after the
review. Counted **in-process** rather than through a shell pipeline, deliberately: the values being
searched for are derived at runtime and putting any of them on a command line is what
`secret-handling.md` forbids, so the probe computes them, captures stdout and counts, printing only
counts.

```
$ .venv/bin/python   # derive code/key/digest, run main(), count occurrences in the captured stdout
--json       exit=0 clear_code=0 clear_key=0 shared_digest_lower=0 shared_digest_upper=0 issuer_hits=0 chars=4084
--no-colour  exit=0 clear_code=0 clear_key=0 shared_digest_lower=0 shared_digest_upper=0 issuer_hits=0 chars=4617
```

`issuer_hits` covers `rzp_live_ sk- AIza ghp_ xoxb- AKIA ASIA sk_live_ ksk_ "PRIVATE KEY"
PLACEHOLDER`. Masking is `****` + last four, applied in both directions — the summary line, the
create body and the query filter.

**And the claim is now informational, not merely literal.** The earlier run reported
`clear_code=0` and concluded "no clear bearer-value code", which was true of the string and false
of the information: `demo_code` and `idempotency_key` expose the **same** sha256 digest of the same
reference, and the key was printed in full, so the masked code was recoverable by stripping
decoration and upper-casing. The key is now masked too, and the three columns above measure the
shared 16-hex digest fragment directly, in both casings, at **0**. The `(70 ch)` length is still
printed, because the length is the fact a reviewer needs about Wix's 100-character ceiling and it
discloses nothing. Pinned by
`test_the_transcript_carries_no_clear_idempotency_key_either`.

Production is unaffected either way: `card_code` is HMAC-keyed and shares nothing with the key,
which `test_the_keyed_code_is_not_recoverable_from_a_logged_reference_id` asserts in both
directions.

### The zero AWS calls are enforced, and the enforcement is itself measured

The hook is armed in `_install_containment()` **before leg 1** and unregistered in `main()`'s
`finally`. `_count_aws_calls()` is now a read. A mutation run proves the assertion is not vacuous —
`_arm_aws_refusal` neutralised, one leg emitting the `before-send` event botocore emits as a
request leaves:

```
$ .venv/bin/python   # mutant: _arm_aws_refusal = lambda armed: armed
MUTANT exit code: 0 (the test asserts 1)
MUTANT aws count: 0 (the test asserts 1)
```

Unmutated, the same leg yields exit `1`, `CONTRACT FAILURE: UnexpectedAwsCall` on stdout, a count
of `1`, and **no transcript**, so a refused run cannot be mistaken for a clean one. Pinned by
`test_an_aws_call_during_a_leg_fails_the_run_rather_than_being_counted_afterwards`.
### And the MOMENT of arming is pinned too, which the test above cannot see
That test emits from leg 3, after `_leg_coupon` has re-armed, so it passes whether or not
`_install_containment` armed anything — measured, not argued: the §0b mutant leaves it green.
`test_the_aws_refusal_hook_is_armed_before_the_first_leg` closes that gap from both sides. It
asserts both `_HOOK_PATHS` modules are in `sys.modules` on a bare import and that
`_arm_aws_refusal([])` resolves **2** targets, then drives `--leg wix-giftcard` once per path —
the leg that imports no handler and re-arms nothing — and requires exit `1`, the named contract
failure, a count of `1` and no transcript. It disarms in a `finally`, because the clients are
session-lifetime and a handler left registered raises a `BaseException` in some later test.
This matters because `_arm_aws_refusal` swallows a module missing from `sys.modules` with
`continue`: without this test, losing either transitive import would silently reduce arming to a
no-op for `--leg wix-giftcard` and `--leg our-giftcard` while the renderer still printed
"ARMED BEFORE leg 1".

### Every process-global is put back

`urlopen`, `sys.modules["boto3"]`, `wix_ecom._key_cache["key"]` and both event-system hooks are
restored in `main()`'s `finally`. Asserted over **two** consecutive runs by
`test_the_demo_puts_back_every_global_it_touched`, because the hook-accumulation defect only shows
on a repeat: the clients are module-level and session-lifetime, and `grep -c 'demo\.main('`
reports **11** call sites in that file — more executions than that, since one sits in a
two-iteration loop and two are parametrised.

## 11. IAM — no provisioner was edited, and that is the finding

```
$ git status --short scripts/
(empty apart from the new demo script)
```

`TransactWriteItems` is authorized through its **items'** actions, so two `Update` items need
`dynamodb:UpdateItem`, which both roles already grant. `dynamodb:ConditionCheckItem` is required
only for a `ConditionCheck` item and this transaction has none — which
`assert_transaction_items_are_exact_key_updates` is what keeps true. There is no
`dynamodb:TransactWriteItems` action to grant; the API is not its own permission.

`test_the_ledger_statements_grant_exactly_what_the_store_needs_and_no_more` now pins both ledger
statements to an exact action set. Before this, the ledger was pinned by **nothing**: the existing
exact-action assertion covers `AdvanceGiftCardStageOnAPaymentAttempt` on **PaymentAttemptsTable**.

## 12. Prohibitions — each one checked, not assumed

| Prohibition | Evidence |
|---|---|
| no deploy | no `update-function-code`, no `publish-version`, no alias move; nothing was run against AWS at all |
| no provisioning | `git status --short scripts/` clean apart from the new demo; no `--apply` on anything |
| no live Wix write | the only network calls in this change are **five `curl` GETs** of `dev.wix.com` documentation pages, recorded in `docs/execution/wix-contract-verification-20261002.md`. No coupon created, no gift card created, no app install, no config change |
| no `secretsmanager get-secret-value` in any spelling | not invoked. Secrets appear only as **names** (`wecare/wix/headless-api-key`, `wecare/wix/giftcard-spi`, field `code_pepper`) |
| integer paise / explicit INR / no floats in money | `Decimal(str())` where a DynamoDB number re-enters arithmetic; `//` and `Money` elsewhere; `currency == "INR"` compared **explicitly and first**; `float` absent by AST from both `wix_gift_cards.py` and the demo; `_marshal` refuses a `float` and a `Decimal` by exact type and is pinned byte-for-byte against `TypeSerializer` |
| bearer-value code never logged in clear | `wix_gift_cards.py` has no `logger`, no `logging` import and no `print(` — asserted by **AST**, not text, because the paragraph explaining the rule necessarily contains the word; `create` never returns a clear code; the demo masks in both directions, **and masks the idempotency key as well**, because this demo's `demo_code` is the unkeyed digest of the same reference and a clear key would otherwise yield it (§10) |
| no live sends | no messaging, no SMS, no WhatsApp, no email. `notificationInfo` is deliberately never sent precisely because it would be one |
| stayed inside this worktree | every path absolute under the worktree; `.worktrees/direct-razorpay-20261002` untouched; `ecommerce/checkout/handler.py`, `payment_readiness.py`, `payments/razorpay-webhook/handler.py` and everything under `amplify/functions/messaging/` untouched; `amplify/functions/ecommerce/coupons/handler.py` **driven, not modified** |
| no destructive git | staged by explicit path with `git commit --only`; no `git add .`/`-A`/`-u`, no bare `stash`, no `clean`, no force push, no history rewrite; **not** rebased onto or fast-forwarded to `stack` |

## 13. Footprint

Modified (5):

```
amplify/functions/shared/lambda_utils/ecommerce/gift_card_store.py   (1513 -> 1646 lines)
tests/coupon_fake_dynamo.py
tests/test_gift_card_store.py
tests/test_gift_card_two_leg_finalization.py        (one line: the injection point)
tests/test_gift_cards_iam_and_table.py              (one added test)
```

New (16):

```
amplify/functions/shared/lambda_utils/ecommerce/wix_gift_cards.py
scripts/demo_coupon_giftcard_sample.py
tests/wix_transport_stub.py
tests/test_wix_coupon_giftcard_sample.py
tests/test_gift_card_redeem_concurrency.py
tests/test_demo_coupon_giftcard_sample.py
tests/fixtures/wix_giftcard_create_response.json
tests/fixtures/wix_giftcard_query_by_code_response.json
tests/fixtures/wix_giftcard_balance_after_redeem.json
tests/fixtures/wix_giftcard_query_miss_response.json
tests/fixtures/wix_giftcard_query_miss_no_key_response.json
tests/fixtures/wix_giftcard_query_two_matches_response.json
tests/fixtures/wix_giftcard_query_disabled_response.json
tests/fixtures/wix_coupon_create_response.json
tests/fixtures/wix_coupon_get_response_float_amounts.json
docs/execution/wix-contract-verification-20261002.md
```

Plus the three task documents: `findings.md`, `verification.md`,
`wix-native-decision-memo.md`.

**Deleted: nothing.** The retirement gate did not clear — see `findings.md`.

### The review iteration's own footprint

Four files, all in the second commit on this branch:

```
scripts/demo_coupon_giftcard_sample.py          M1 M2 M3 L1 — containment armed early,
                                                restored in a finally, key masked
tests/test_demo_coupon_giftcard_sample.py       three added tests (16 -> 19)
amplify/.../ecommerce/gift_card_store.py        L3 — credit() docstring only, no code change
tests/test_gift_card_store.py                   L3 — one test renamed, module docstring
```

Plus `findings.md` (L2, the corrected fetch count, the fresh transcript and the three reading
notes) and this file. No production code path changed: the only `amplify/` edit is a docstring,
which `git show --stat` and a diff of the function body both confirm.
