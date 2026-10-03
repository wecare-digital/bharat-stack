# Verification — direct-razorpay-graft-20261002

Everything below was measured in the worktree
`/Users/wecaredigital/wecare-store/.worktrees/direct-razorpay-graft-20261002` on branch
`direct-razorpay-graft-20261002`. No rebase, no fast-forward, no push, no deploy.

Merge base against `origin/stack`: **`e3c01440`** — the commit the baseline was measured at.

Read this instead of re-running anything.

> **ITERATION 2, 2026-10-03.** `code-review.json` returned `CHANGES_REQUESTED` with seven
> actionable findings (3 MEDIUM, 4 LOW) and one INFORMATIONAL marked "no change required".
> All seven are addressed; §8 below is the finding-by-finding record and §1/§2 carry the
> re-measured counts. Nothing from iteration 1 was removed or weakened.

---

## 1. Python — `.venv/bin/python -m pytest`

Run with `pytest.ini`'s own `testpaths = tests, amplify/functions`, i.e. the bare invocation.

```
5 failed, 6946 passed, 1 skipped, 3 xfailed in 64.21s
```

**failed = 5 · passed = 6946 · skipped = 1 · xfailed = 3**

Baseline (`baseline-rederived.md`): `13 failed, 6829 passed, 1 skipped, 2 xfailed`.
Iteration 1: `5 failed, 6910 passed, 1 skipped, 3 xfailed`. **Iteration 2 adds 36 passing rows
and no failing id.**

### The 5 failing ids, in full

```
tests/test_blog_ledger.py::test_the_committed_ledger_if_present_reconciles
tests/test_email_verification_handler.py::test_verify_returns_email_bound_proof_and_never_stamps_body_selected_customer
tests/test_gift_card_amounts_and_gst.py::test_the_convenience_fee_is_computed_on_the_full_collection_total
tests/test_gift_card_amounts_and_gst.py::test_only_one_gift_card_is_accepted
tests/test_gift_cards_iam_and_table.py::test_the_gift_card_tender_claims_a_different_effect_key_from_the_razorpay_payment
```

Every one of them is in the baseline's 13. **Zero new failing ids.**

### Against the baseline's three sets

**Set A — MUST GO GREEN (7 ids). All 7 green.**

| id | now |
|---|---|
| `test_checkout_website_handler.py::test_verified_callback_requires_owned_attempt_and_authoritative_capture` | PASS |
| `test_coupons_iam_and_table.py::test_the_checkout_role_gains_only_the_coupons_table` | PASS |
| `test_coupons_iam_and_table.py::test_the_iam_simulation_covers_every_action_the_policy_grants` | PASS |
| `test_coupons_iam_and_table.py::test_delete_item_is_still_denied_on_the_payment_attempt_and_keys_tables` | PASS |
| `test_gift_cards_iam_and_table.py::test_the_checkout_role_gains_only_the_gift_cards_table` | PASS |
| `test_gift_cards_iam_and_table.py::test_the_gift_card_grant_and_its_simulation_cannot_drift_apart` | PASS |
| `test_provision_checkout_contract.py::test_the_template_matches_the_route_arns_the_script_grants` | PASS |

**Set B — MUST STAY RED (4 `XPASS(strict)` ids). 3 of 4 still red; the fourth moved, and this is the one deviation in the whole run.**

| id | now |
|---|---|
| `test_gift_card_amounts_and_gst.py::test_the_convenience_fee_is_computed_on_the_full_collection_total` | still red ✓ |
| `test_gift_card_amounts_and_gst.py::test_only_one_gift_card_is_accepted` | still red ✓ |
| `test_gift_cards_iam_and_table.py::test_the_gift_card_tender_claims_a_different_effect_key_from_the_razorpay_payment` | still red ✓ |
| `test_gift_cards_iam_and_table.py::test_the_website_checkout_split_binds_the_charged_amount_and_the_payable_separately` | **now xfails** — see below |

**The deviation, stated precisely.** That fourth row (SEAM-G14) asserts the split by requiring
`_browser_options` and `payment_attempt.build` to appear **in the same function** with different
`amount_paise` expressions. The approved design's iteration-7 HIGH-1 fix deliberately separates
them: there is now exactly **one** `_browser_options` call site and it is inside
`_emit_payable_modal`, not inside `_bind_and_ready` where the attempt is built. The assertion's
*scoping* therefore no longer matches the module's structure, so the underlying test fails, which
satisfies its `xfail(strict=True)` marker and removes the id from the failing set. Hence
`3 xfailed` where the baseline had `2`.

What was and was not done about it:

- **No marker was removed and no bar was lowered.** That file belongs to the gift-card workstream
  and is on this build's do-not-touch list for its markers; it was left untouched.
  `git diff e3c01440..HEAD -- tests/test_gift_cards_iam_and_table.py | grep '^[-+].*xfail'` is
  empty.
- **The property it protects is re-pinned**, so the detector is replaced rather than lost:
  `tests/test_graft_money_correctness.py::test_the_browser_amount_and_the_attempt_amount_are_different_expressions`
  asserts, over `_bind_and_ready`'s AST, that the expression handed to `_emit_payable_modal` is
  the pay-now leg, the expression handed to `payment_attempt.build` is the full payable, and the
  two sets do not intersect.

**Set C — KNOWN RED, OUT OF SCOPE (2 ids). Both still red, which the baseline permits.**
`test_blog_ledger` and `test_email_verification_handler`; neither file is touched by this change.

### Net delta

`13 → 5` failing. `6829 → 6946` passing: **+117**, of which **109** are the rows in
`tests/test_graft_money_correctness.py` (73 from iteration 1 plus **36** added in iteration 2),
8 are set A going green, and the rest is arithmetic on the migrated handler rows.

### Targeted runs, as they were made during the build

```
tests/test_graft_money_correctness.py                             109 passed  (iteration 2)
tests/test_graft_money_correctness.py                              73 passed  (iteration 1)
tests/test_provision_checkout_contract.py                          58 passed
tests/test_provision_checkout_contract.py
  tests/test_coupons_iam_and_table.py
  tests/test_gift_cards_iam_and_table.py                           1 failed, 100 passed, 2 xfailed
tests/test_checkout_website_handler.py
  tests/test_checkout_cart_v2_authority.py
  tests/test_checkout_package_completeness.py
  tests/test_razorpay_binding.py
  tests/test_graft_money_correctness.py                            80 passed
tests/test_gift_card_two_leg_finalization.py
  tests/test_wix_writeback.py
  tests/test_purchase_intent_producer.py
  tests/test_checkout_pricing.py                                   201 passed
```

The `1 failed` in the IAM trio is SEAM-G7(b), which must stay red.

---

## 2. Client — build FIRST, then vitest

`npm run build` is mandatory before `npx vitest run`: `src/test/PillButtonBuildScope.test.ts`
reads built HTML under `out/` and fails spuriously without it.

```
npm run build        -> exit 0   (next build + sitemap 1411 URLs + blog index + llms.txt)
npx vitest run       -> Test Files  3 failed | 66 passed (69)
                        Tests  6 failed | 836 passed | 1 skipped (843)
npx tsc --noEmit     -> exit 0
```

**failed = 6 · passed = 836 · skipped = 1**

Baseline: `6 failed, 827 passed, 1 skipped`. **+9 passing, zero new failing ids.**

Re-measured unchanged in iteration 2 (`6 failed | 836 passed | 1 skipped (843)`, files
`3 failed | 66 passed (69)`, `tsc --noEmit` exit 0). No finding in `code-review.json` touched
`src/`, so no client file changed and the client numbers are identical to iteration 1 rather
than merely similar.

### The 6 failing ids, in full

```
src/test/AccountSignIn.test.tsx > the error copy is the owner's table and nothing else > never infers India for bare digits - the selected code decides
src/test/AccountSignIn.test.tsx > the error copy is the owner's table and nothing else > shows the default country code rather than inferring one
src/test/BlogSubscribe.test.tsx > BlogSubscribe > renders the four requested fields and keeps Subscribe locked until both verifications
src/test/PublicPageTopBand.test.tsx > the country code is a segment of the one divided field, on owner instruction > is one divided field: a code segment and a number segment, with no native validation
src/test/PublicPageTopBand.test.tsx > the country code is a segment of the one divided field, on owner instruction > uses the SELECTED code for bare national digits, never the inferred one
src/test/PublicPageTopBand.test.tsx > the country code is a segment of the one divided field, on owner instruction > associates the error with the field so a correction is possible
```

All six are the baseline's six, all the same cause (`Unable to find a label with the text of:
Country code`), all owned by the phone-field / country-code workstream. None of those files is
touched by this change.

`src/test/CartCheckout.test.tsx` alone: **32 passed** (24 pre-existing + 8 new).

---

## 3. The stubbed full-stack flow — recorded, not asserted

There is no Playwright or Puppeteer in this repo (only `vitest`), and
`POST /ecommerce/verify-callback` does not exist on the live API, so a real-browser pass against a
deployed stack is impossible and is deferred to the owner checklist. The exercise was run in two
halves, both with the **Razorpay SDK fully stubbed** — no provider call, no charge.

### Server half

`tests/test_graft_money_correctness.py::test_the_stubbed_browser_flow_yields_one_order`, driving
the real `handler.handler` through `prepare` then `verify`, with a verified CRM profile, a Cart V2
snapshot, an owned address and a delivery method, and `INITIATION_ENABLED` injected as a **module
attribute** — `CHECKOUT_INITIATION_ENABLED` stays absent from the environment, so this is not a
flag enable.

Recorded output (the fixture's public key id is redacted here because it is assembled at runtime
precisely so no issuer-shaped literal is committed; the secret half is a non-credential sentinel
that appears nowhere):

```
prepare -> 200
{
  "status": "CHECKOUT_OPTIONS_READY",
  "paymentAttemptId": "01a10098-73ea-7f1d-82a8-5666d63d22bf",
  "options": {
    "keyId":   "<fixture PUBLIC key id, assembled at runtime>",
    "orderId": "order_GRAFT_1",
    "amountPaise": 2625123,
    "currency": "INR",
    "prefill": { "name": "...", "email": "...", "contact": "..." },
    "paymentAttemptId": "01a10098-73ea-7f1d-82a8-5666d63d22bf"
  }
}
```

Asserted on that payload:

| claim | evidence |
|---|---|
| the key set is EXACTLY the allow-list | `set(options) == {keyId, orderId, amountPaise, currency, prefill, paymentAttemptId}` — an allow-list, so a new field cannot leak by omission |
| integer paise | `isinstance(options["amountPaise"], int)` and not a `bool` |
| NO float anywhere | a recursive walk of the whole payload raises on any `float` |
| INR, compared explicitly | `options["currency"] == "INR"`, never inferred from the amount |
| the CALCULATOR total, not the raw Wix total | `2625123 == 2549900 + 63748 + 11475`, and `!= 2549900` |
| the PUBLIC key id only | `options["keyId"] == FIXTURE_PUBLIC_KEY_ID`; the secret sentinel, `key_secret` and `keySecret` all absent from `json.dumps(response)` and from every captured log record |

`create_order` was called **once**, with:

```
amount_paise = 2625123
receipt      = "WD-PAY-XJR5P5SA0Q0V0H"        (the reference, so recovery correlates on it)
notes        = { paymentAttemptId, customerId, snapshotHash, referenceId }
```

`referenceId` in `notes` is the field the webhook reads to resolve an attempt — without it a
direct capture reconciles against nothing and quarantines.

```
verify -> 200
{ "status": "VERIFIED_PAID",
  "paymentAttemptId": "01a10098-...",
  "orderNumber": "WD-ORD-52ZACPE5" }
```

**Exactly one order.** `OrderTable` row count **1**, `ORDERNO#` row count **1**, one distinct
`orderNumber`, and it satisfies `order_keys.is_current_public_order_number`. A **replayed** verify
with the same payment id returns 200 and leaves both counts at 1.

The attempt row after the flow:

```
status                   PAYMENT_PAID
amountPaise              2625123     (the frozen payable)
razorpayChargedPaise     2625123     (the leg; equal here because no gift card)
wixGiftCardRedeemPaise   0
verifiedCapturedPaise    2625123     (the PROVIDER's confirmed figure)
currency                 INR
checkoutMode             WEBSITE_RAZORPAY_STANDARD
finalizationStage        NEEDS_RECONCILIATION
finalizationReason       WIX_WRITE_CONTRACT_REQUIRED
```

That last pair is the **expected dormancy**, not a failure: all four
`wix_writeback.is_enabled()` conditions are false, so grafts 3 and 5 are correct and unreachable.
The internal order record is written and staged `INTERNAL_ORDER_CREATED` first, which is why the
shopper gets an order number for a row `service-api` can list.

Key prefixes written across the flow:

```
CARTBASKET#  CARTNARROW#  CARTPAYMENT#  CUSTOMERCART#  GATEWAYORDER#
ORDERNO#  PAYMENTATTEMPT#  PAYREF#  PROVIDERPAYMENT#  REQUESTKEY#
```

All three cart rows present, exactly one `GATEWAYORDER#`, exactly one `PAYREF#`.

### Server half, iteration 2 — the SAME flow run past the write-back gate

Iteration 1's run stopped at `WIX_WRITE_CONTRACT_REQUIRED`, which is correct dormancy and also
meant every line after that gate was unexecuted. The new rows run it to the end by setting
`wix_writeback.is_enabled()`'s four conditions **as per-test `monkeypatch.setenv` values**, which
pytest reverts. That is not a flag enable: nothing in `amplify/infra/` or
`scripts/provision_checkout.py` sets any of the four, `tests/test_wix_writeback.py` has used the
same keys since before this change, and the Wix transport is the same stub as everywhere else —
no Wix call, no provider call, no charge.

Re-dumped with `.scratch/flow_evidence.py`, which drives the same rig the suite uses so the two
cannot disagree (public key id and prefill redacted at the dump, not at the assertion):

```json
{
  "prepare": { "options": {
      "keyId": "<fixture PUBLIC key id, assembled at runtime>",
      "orderId": "order_GRAFT_1",
      "amountPaise": 2625123,
      "currency": "INR",
      "prefill": { "name": "<redacted PII>", "email": "<redacted PII>",
                   "contact": "<redacted PII>" },
      "paymentAttemptId": "01a100bd-8261-7916-9198-8a89eaed252f" } },
  "create_order_calls": [ { "amount_paise": 2625123,
      "receipt": "WD-PAY-E49C7MBJ953P6K",
      "notes_keys": ["customerId", "paymentAttemptId", "referenceId", "snapshotHash"] } ],
  "verify": { "statusCode": 200, "status": "VERIFIED_PAID",
              "orderNumber": "WD-ORD-7BXWQRD8" },
  "attempt_row": {
      "status": "PAYMENT_PAID",
      "amountPaise": 2625123,
      "razorpayChargedPaise": 2625123,
      "wixGiftCardRedeemPaise": 0,
      "verifiedCapturedPaise": 2625123,
      "currency": "INR",
      "checkoutMode": "WEBSITE_RAZORPAY_STANDARD",
      "finalizationStage": "WIX_CART_COMPLETED",
      "finalizationReason": "",
      "providerPaymentId": "pay_evidence_1",
      "providerOrderId": "order_GRAFT_1" },
  "orders_table_rows": 1,
  "wix_calls": { "create_order": 1,
                 "add_payment_amounts": ["26251.23"],
                 "cart_completions": ["de4d6a89-e575-4c51-b930-aec2adbd8b80"] },
  "key_prefixes_written": ["CARTBASKET#", "CARTNARROW#", "CARTOP#", "CARTPAYMENT#",
      "CUSTOMERCART#", "GATEWAYORDER#", "ORDERNO#", "PAYMENTATTEMPT#", "PAYREF#",
      "PROVIDERPAYMENT#", "REQUESTKEY#", "SIDEEFFECT#"]
}
```

`26251.23` is `2625123` paise through `Money.to_wix` — integer division, no float, and it is the
**Razorpay leg**. On the split-tender row the same figure is the leg and provably not the payable:
`test_only_the_verified_razorpay_leg_reaches_wix` asserts `recorded == leg` and
`recorded != payable` with `leg != payable` anchored first, so the row cannot pass against the
pre-graft code that sent `attempt['amountPaise']`.

Three Wix calls, and only three — create the order, record the already-collected payment, close
the cart. The stub answers no fourth endpoint, which is the enumeration R7.4 asks for; the
allowlist in `wix_writeback._guarded_call` has already refused anything else before a call
reaches the stub.

### Client half

`src/test/CartCheckout.test.tsx > the payment rail latches once it has returned a result > the
full stubbed rail: cart -> profile -> prepare -> modal -> verify -> one order`, a real React
render in jsdom with `fetch` and `window.Razorpay` stubbed. `FakeRazorpay.open()` performs **no
network I/O**.

Asserted on the object handed to `new window.Razorpay(...)`:

```
amount     2625123        Number.isInteger(...) === true
currency   'INR'
key        the PUBLIC key id
order_id   non-empty
```

plus: no key whose **name** matches `/secret/i`, and `JSON.stringify(options)` does not match
`/secret/i`. Then the handler runs: exactly **one** POST to `/ecommerce/verify-callback`, the
latch set, and navigation to `/checkout/status/?a=att-latch-1`.

### What was NOT exercised in a real browser, stated rather than implied

No Chrome/CDP pass and no screenshots. The route the browser would post to does not exist on
`zllr9lrg7j`, and there is no browser-automation dependency in this repo to drive it with. The two
halves above cover the same path — the real handler for the server contract, a real React render
for the client contract — and the gap is the network between them, plus the real Razorpay modal,
both of which require the deployment steps in
`docs/execution/direct-razorpay-graft-20261002-deploy-checklist.md`.

---

## 4. The three proving tests the brief names

| # | test | non-vacuity anchor |
|---|---|---|
| (a) | `test_a_revision_bump_does_not_unblock_a_paid_basket` | asserts the two prepares produce **different** `snapshot_hash` values and the **same** `basket_hash`. Without that anchor the row would pass against a guard keyed on `snapshot_hash` and prove nothing |
| (b) | `test_a_paid_basket_survives_both_a_pointer_overwrite_and_a_moved_wix_field` | asserts `basket_hash` **differs** and `narrow_basket_hash` is **equal** before the refusal is checked. Stage (b) of the four-stage sequence must be **ALLOWED** — the legitimate repeat purchase — and `create_order` is called exactly **twice** across the whole run, never three times |
| (c) | `test_a_resumed_request_key_after_a_lost_pointer_write_still_guards_the_basket` | asserts `gatewayOrderId` is **present** on the `REQUESTKEY#` row after prepare #1, which is what makes `_resume_lost_request_key`'s `gatewayOrderId` branch reachable at all. Parametrised over all three cart-row writers. Prepare #3 with a fresh key after payment is `409 CART_ALREADY_PAID` with `create_order` still at **1** |

(c) is the new one. It is run against a **fixed-revision** stub, because `intent_fingerprint`
carries `cart_revision`: with a bumping revision, prepare #2 answers `INTENT_CHANGED` at step 3
and the resume exit is never entered. Both revision worlds are covered —
`test_a_same_key_prepare_in_the_bumping_world_is_an_intent_change` holds the other side.

---

## 5. Standing constraints, re-asserted

```
$ git diff --numstat e3c01440..HEAD -- amplify/functions/payments/
(empty)
```

The webhook HMAC path is byte-identical. The **property** is additionally tested by
`test_an_unsigned_webhook_body_is_still_401`, which posts an unsigned body to the real webhook
handler and asserts 401. The byte-identity check stays a per-commit review command rather than a
test, because as a test it would be a permanent false alarm on the first unrelated change there.

```
$ git diff --name-only e3c01440..HEAD
amplify/functions/ecommerce/checkout/handler.py
amplify/functions/shared/lambda_utils/ecommerce/checkout_pricing.py
amplify/functions/shared/lambda_utils/ecommerce/finalization.py
amplify/functions/shared/lambda_utils/ecommerce/order_keys.py
amplify/functions/shared/lambda_utils/ecommerce/purchase_intent.py
amplify/functions/shared/lambda_utils/ecommerce/website_checkout.py
amplify/functions/shared/lambda_utils/ecommerce/wix_writeback.py
amplify/infra/checkout.json
scripts/provision_checkout.py
src/pages/cart.tsx
src/test/CartCheckout.test.tsx
tests/crm_fake_dynamo.py
tests/test_checkout_website_handler.py
tests/test_coupons_iam_and_table.py
tests/test_gift_cards_iam_and_table.py
tests/test_graft_money_correctness.py
tests/test_provision_checkout_contract.py
```

17 files, every one named in the plan, plus the two documentation files in the final commit.

| constraint | how it was checked | result |
|---|---|---|
| `CHECKOUT_INITIATION_ENABLED` absent as a set value | `grep` over `scripts/provision_checkout.py` and `amplify/infra/checkout.json` | every hit is a comment, a docstring, or the `--verify` check that reports it being ON as a problem. Never set |
| no `get-secret-value` / `batch-get-secret-value` in any changed file | `grep` over every changed file | the only hits are inside the gate test that **asserts their absence** |
| `key_secret` never to browser, log, response or fixture | `test_no_changed_file_reads_a_secret_value`, `test_no_response_or_log_can_carry_the_key_secret` | pass |
| no issuer-shaped literal committed | the fixture public key id is assembled at runtime from parts, the same technique `scripts/verify_secret_hook.py` uses | `block-inline-secrets` blocked one earlier attempt and was right to |
| no raw `captured` comparison | AST walk over all 7 changed Python files; `FORBIDDEN_RAW == {'captured'}` unchanged | pass |
| no PII in a logging expression | AST walk over every `logger.*` call in all 7 files, checking the **expression** rather than the output | pass |
| every logged exception is `type(exc).__name__` | AST walk | pass |
| integer paise, no float, `Decimal(str())` | `test_a_float_amount_is_refused_at_every_money_boundary` — the real row, parametrised over `0.1+0.2`, `100.0`, `True`, `Decimal('1.5')`, `'abc'` and `None` across `integer_paise`, `record_paid`, `accept_paid`, `payment_attempt.build` and `wix_writeback._paise_money`; plus `test_an_exact_integer_amount_is_still_accepted_everywhere` and `_no_floats` over the browser payload | pass |
| INR compared explicitly | `build_wix_order_payload` raises on a non-INR quote; the status leg compares `currency != "INR"`; the modal payload asserted `== "INR"` | pass |
| `reference_id` resolve-before-generate | `_resume_lost_request_key` never calls `allocate_reference`; `_reference_and_create_right` returns the reference read back off the row | pass |
| the four `xfail(strict=True)` markers | `git diff ... -- tests/test_gift_card_amounts_and_gst.py` empty; no `xfail` line changed in `tests/test_gift_cards_iam_and_table.py` | untouched |
| nothing deployed | no `update-function-code`, no publish, no alias move, no `--apply`, no `--verify`, no flag set, no IAM or Cognito mutation | none attempted |
| no destructive git | every commit used `git commit --only <explicit paths>`; no force push, no rebase, no history rewrite, no `git add -A`/`.`/`-u`, no bare `stash`, no `clean`, no push | — |

`git status --short` is clean at the end of the run.

---

## 6. Two corrections to the approved design, both forced by measurement

Recorded here because both are behaviour the design specified differently, and both move in the
direction of the design's own named tests rather than away from them.

**1. The same-request-key resume exemption had to extend to the per-basket arms.** The design puts
the exemption only on the cart-pointer path (its arm 8). But the three cart rows are written by the
choke point on *every* successful prepare, so the row a second click on the same key finds is the
row its own first click wrote — and without an exemption, every legitimate double-click or reload
of an **unpaid** attempt becomes `CART_PAYMENT_IN_FLIGHT`, and
`_resume_lost_request_key`'s `gatewayOrderId` branch becomes unreachable, which would make the
entire iteration-7 fix inert. Two **existing** tests proved it:
`test_concurrent_same_intent_clicks_coordinate_on_one_order` and
`test_changed_intent_on_resumed_request_key_is_rejected`. The exemption was added to the in-flight
and dangling arms and **deliberately not to the paid arm** —
`test_a_reload_in_the_paying_tab_is_refused_not_resumed` holds that line.

**2. The step-4b claim row stores `requestKey`.** Same cause: without it the claimer's own later
click reads its own claim as a foreign in-flight attempt. It changes no horizon — the
discrimination between the 120s create window and the 1200s settling window is the **absence of
`recordedAt`**, not this field.

One design prediction was also measured to be wrong in a harmless direction, and the test was
corrected to the measurement rather than the other way round:
`test_two_overlapping_prepares_on_one_basket_open_one_payable_order`. The design expected the
second prepare to lose at step 4b. Measured, it is refused earlier — at step 2a, by the claim row
the winner wrote *before* `create_order` — so it writes nothing at all and names the holder's
attempt. That is strictly better; the invariant asserted is one create, one gateway order, one
reference, one modal, not which arm produced it. The step-4b loser path (which deliberately names
**no** attempt) is exercised directly by
`test_a_held_basket_claim_refuses_without_naming_an_attempt`.

---

## 8. Iteration 2 — the seven review findings, one by one

`code-review.json` verdict `CHANGES_REQUESTED`. Four files changed in this iteration:

```
amplify/functions/shared/lambda_utils/ecommerce/website_checkout.py   source  (LOW-1, LOW-2 comment)
tests/test_graft_money_correctness.py                                 +36 rows
tests/test_gift_cards_iam_and_table.py                                handoff note only
docs/execution/direct-razorpay-graft-20261002-deploy-checklist.md      handoff section
```

### MEDIUM-1 — finalization and the §7 handler wiring had no behavioural test

All twenty named rows added, every one driven through `_website_verify` or `_status` and **none**
by calling `accept_paid` directly. The plan's reason is the operative one: a test that calls
`accept_paid` itself cannot detect that its only production caller refuses to reach it.

| row | what makes it non-vacuous |
|---|---|
| `test_a_website_attempt_can_be_finalized_at_all` | the ladder reaches `WIX_CART_COMPLETED`, so every line after the write-back gate executes |
| `test_only_the_verified_razorpay_leg_reaches_wix` | `leg != payable` asserted **first**; the recorded amount equals the leg and differs from the payable |
| `test_a_one_paise_tender_disagreement_fails_closed` | the order record still exists (money moved) while `wix_orders == []` — "fails closed" means nothing external, not nothing at all |
| `test_a_wix_funded_split_tender_order_reaches_accept_paid` | leg B of the split gate must PASS a readable tender, or the graft is unreachable from its only caller |
| `test_an_ordinary_card_free_order_with_a_zero_leg_is_not_refused` | asserts the attribute is PRESENT and `0`, so the row tests value-not-presence rather than assuming it |
| `test_an_unreadable_tender_leg_is_refused` | no order record at all, because the gate is above `accept_paid` — and the capture is still recorded, because that is step 1 |
| `test_an_unsettled_wecare_gift_card_is_refused` | leg A, the ladder `accept_paid` does not consult |
| `test_a_settled_wecare_gift_card_is_not_refused_by_the_ladder_gate` | the other side of leg A; the Wix-recorded figure is the Razorpay leg, not the card's and not the payable |
| `test_webhook_and_browser_return_converge_on_one_order` | the browser must return the number the **webhook** reserved; one order row, one `ORDERNO#` |
| `test_the_reconcile_verifier_resolves_a_payref_reference` | both identifier kinds resolve onto the **same** projection, and the projection's key set is exactly the webhook's six |
| `test_a_lost_provider_order_link_still_verifies` | asserts the link is genuinely absent first, then that the server-stored fallback supplies it |
| `test_a_binding_with_no_reference_still_verifies_and_alarms` | 200 with `orderNumber: null`, capture recorded, `PAID_BUT_NO_ORDER` alarm — never a 503 and never a failure verdict |
| `test_a_verified_capture_is_recorded_even_when_reconciliation_fails` | driven through the real `IDENTITY_UNAVAILABLE` (the claim's durable write fails), not by stubbing the outcome |
| `test_a_finalization_fault_is_still_a_200` | the reserved number still reaches the shopper, and the exception TEXT is asserted absent from the log |
| `test_two_readbacks_disagreeing_on_the_capture_write_nothing` | the two stored authorities are made to disagree by one paise so BOTH comparisons pass and two different provider figures result — the only way to reach the check |
| `test_the_closed_tab_poll_writes_exactly_one_order_record` | the webhook leaves the attempt at `PAYMENT_PENDING`, which is why the gate is the CLAIM; a second poll writes nothing more |
| `test_the_status_leg_refuses_rather_than_substituting_the_payable` | two halves: an unavailable provider writes nothing, an available one stores the LEG, with `leg != payable` anchored |
| `test_a_claim_without_a_reference_alarms_once_instead_of_polling_forever` | the capture verifier is replaced with one that FAILS the test if called |
| `test_claim_outcome_satisfies_accept_paid` | the three keys `accept_paid` reads by name, plus the unnumbered-claim arm |
| `test_a_float_amount_is_refused_at_every_money_boundary` | see MEDIUM-2 |

### MEDIUM-2 — the money-boundary table did not exist

`test_a_float_amount_is_refused_at_every_money_boundary` added, parametrised over the six values
the review names, across all five boundaries. Two assertions beyond "it raises": `record_paid`
leaves the row at `PAYMENT_PENDING` after refusing, and `accept_paid` leaves no
`finalizationStage` — so a refusal cannot have half-written first.

`test_an_exact_integer_amount_is_still_accepted_everywhere` is the must-still-work half
(`100`, `Decimal('100')`, `'100'` → `100`, stored as an `int`). It also executes `record_paid`'s
new fourth argument and its **nested** condition group: a redelivery agreeing on the provider id
AND the amount is idempotent, one agreeing on the id but **not** the amount is refused by the
database with a `ConditionalCheckFailedException` and the stored evidence is unchanged. That is
the subtlety two sibling OR groups would get wrong, and it now has an executing test.

### MEDIUM-3 — the joint blob budget was untested

`test_the_attempt_row_fits_one_dynamodb_item` reproduces the production ordering verbatim
(snapshot measured first, payload measured against the remainder with the floor) and asserts the
joint sum is within `ceiling + floor` and within DynamoDB's 400 KB item limit — plus
`ceiling + floor < 2 * ceiling`, which is the off-by-one the joint split exists to prevent. It
also pins that a money field is never what gets trimmed (`priceSummary` and `additionalFees`
byte-equal at any size) and that `cart` is retained, because `accept_paid`'s own guard is
`snapshot.get('cart')` and dropping it would refuse the order rather than shrink it.

`test_an_ordinary_prepare_stores_a_row_far_inside_the_item_limit` measures the same property on
the row production actually writes. `test_a_reduced_wix_payload_is_refused_rather_than_sent`
drives `accept_paid`'s `WIX_PAYLOAD_REDUCED` refusal through `_website_verify`.

### LOW-1 — `_record_cart_pointer` passed silently on a missing identity

**Source change.** `if not customer_id or not wix_cart_id: return None` is now a
`CHECKOUT_AMBIGUOUS` / `CART_POINTER_SAVE_FAILED` refusal with the same vocabulary, the same
200-not-409 handler mapping and the same consequence as the write-failure arm: no `options`, so
the modal never opens and the unused Razorpay order expires. The docstring's "`None` means
written, carry on" claim is corrected to name the one path that returns it.

No user-visible change, and the reason is measured rather than assumed: the arm is unreachable
from a prepare on three independent counts — `QuoteSnapshot.__post_init__` raises
`PricingError('snapshot requires a cart id')` so an identity-less snapshot cannot be constructed
at all, `build_snapshot` derives `frozen_data['cart']['id']` from the same `cart_id`, and step 2a
converts a cartless payload into `CheckoutRejected(BASKET_IDENTITY_REQUIRED)` before anything is
created. `test_a_pointer_with_no_cart_identity_refuses_rather_than_passing` asserts both arms at
the choke point with a stand-in, and records that third layer as the reason a stand-in is the
only honest way to reach it.

### LOW-2 — orphan `PAYREF#` row on a lost create right

Taken as **documented behaviour plus the named test**, not as a reordering. The mint cannot move
below the create right: `_reference_and_create_right` claims the right and writes the reference in
ONE conditional round trip — which is what makes the two agree — so it has to be handed a value
before the right is known. A comment at the mint site now states that, names the consequence, and
points at the test.

`test_a_lost_create_right_correlates_on_the_stored_reference` drives the race with a table that
refuses the create-right claim exactly once and then stores the holder's reference, and asserts:
200 `CHECKOUT_AMBIGUOUS` / `CREATE_IN_FLIGHT` with no `options`, `create_order` never called, the
receipt correlation performed against the **holder's** reference (anchored by asserting the
minted reference differs from it), exactly one orphan `PAYREF#` row carrying no
`providerOrderId`, and no cart rows because the loser never reached the choke point.

### LOW-3 — the dormant prepare gained a new 503

`test_a_guard_read_failure_is_a_503_and_never_a_pass` is now parametrised over
`initiation_enabled` as well as the three resolvers (6 cases), so the gate-off answer is a
decision rather than a side effect. Both worlds answer 503 `TEMPORARILY_UNAVAILABLE`, and both
assert nothing was written — zero `REQUESTKEY#` rows and an empty attempts table — because the
refusal sits above step 3's reservation. The direction is deliberate: "we could not check" must
not be reported as "nothing is live".

### LOW-4 — SEAM-G14 handed over satisfied by failure

Recorded in the two places that workstream will actually read: a `HANDOFF` block in the xfail
row's own docstring in `tests/test_gift_cards_iam_and_table.py`, and a section in
`docs/execution/direct-razorpay-graft-20261002-deploy-checklist.md`. Both name the replacement
row (`test_the_browser_amount_and_the_attempt_amount_are_different_expressions`), state that the
fix is to **rescope** the assertion rather than flip the marker, and suggest the two ways to do
it. **The marker itself was not touched** and the row is still red.

### INFO-1 — `razorpay_verify.CAPTURED`

No change, as the review states. The file is not in this diff and not in the gate's
`TOUCHED_PYTHON` list; `FORBIDDEN_RAW == {'captured'}` is unchanged and
`test_the_vocabulary_gate_itself_is_unchanged` still pins it.

### What iteration 2 did NOT do

No deploy, publish, alias move, live route, live env set, IAM or Cognito mutation, flag enable, no
capture/refund/config mutation, no live send, no `secretsmanager get-secret-value` in any
spelling, no PayU, no new S3 bucket. No force push, no history rewrite, no `git add -A`/`.`/`-u`,
no bare `stash`, no `clean`; every commit used `git commit --only <explicit paths>`. The
wix-coupon-giftcard worktree and the main checkout's dirty files were not touched.

---

## 7. Commits on `direct-razorpay-graft-20261002`

```
90a5f3b6  fix: reconcile checkout.json with the provisioner, and gate what must not regress
e4bbcb2d  feat: latch the cart's payment rail once it has returned a result
2db80956  feat: one payable modal per basket, split-tender finalization, and the PAYREF# join
43eb4118  feat: durable per-basket paid memory, two basket identities, and the Wix order payload
68c82f50  test: teach the CRM fake OR and ordered comparison, and name the IAM eval constants
```

Iteration 2 adds, in order:

```
<pending>  fix: refuse a cart pointer with no identity, and document the create-right orphan
<pending>  test: drive finalization and the split-tender wiring through the handler, not around it
<pending>  docs: hand SEAM-G14 over with its replacement row named
```

Nothing pushed. Raw logs (untracked, inside the worktree): `.scratch/final-pytest.log`,
`.scratch/final-build.log`, `.scratch/final-vitest.log`, `.scratch/flow-evidence.json`,
and for iteration 2 `.scratch/pytest-iter2.txt`, `.scratch/build-iter2.txt`,
`.scratch/vitest-iter2.txt`, `.scratch/tsc-iter2.txt`, `.scratch/flow-evidence-iter2.json`.
