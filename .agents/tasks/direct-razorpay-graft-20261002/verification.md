# Verification — direct-razorpay-graft-20261002

Everything below was measured in the worktree
`/Users/wecaredigital/wecare-store/.worktrees/direct-razorpay-graft-20261002` on branch
`direct-razorpay-graft-20261002`. No rebase, no fast-forward, no push, no deploy.

Merge base against `origin/stack`: **`e3c01440`** — the commit the baseline was measured at.

Read this instead of re-running anything.

---

## 1. Python — `.venv/bin/python -m pytest`

Run with `pytest.ini`'s own `testpaths = tests, amplify/functions`, i.e. the bare invocation.

```
5 failed, 6910 passed, 1 skipped, 3 xfailed in 97.55s
```

**failed = 5 · passed = 6910 · skipped = 1 · xfailed = 3**

Baseline (`baseline-rederived.md`): `13 failed, 6829 passed, 1 skipped, 2 xfailed`.

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

`13 → 5` failing. `6829 → 6910` passing: **+81**, of which **73** are the new rows in
`tests/test_graft_money_correctness.py`, 8 are set A going green, and the rest is arithmetic on
the migrated handler rows.

### Targeted runs, as they were made during the build

```
tests/test_graft_money_correctness.py                              73 passed
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
| integer paise, no float, `Decimal(str())` | `test_a_float_amount_is_refused_at_every_money_boundary`-class rows plus `_no_floats` over the browser payload | pass |
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

## 7. Commits on `direct-razorpay-graft-20261002`

```
90a5f3b6  fix: reconcile checkout.json with the provisioner, and gate what must not regress
e4bbcb2d  feat: latch the cart's payment rail once it has returned a result
2db80956  feat: one payable modal per basket, split-tender finalization, and the PAYREF# join
43eb4118  feat: durable per-basket paid memory, two basket identities, and the Wix order payload
68c82f50  test: teach the CRM fake OR and ordered comparison, and name the IAM eval constants
```

Nothing pushed. Raw logs (untracked, inside the worktree): `.scratch/final-pytest.log`,
`.scratch/final-build.log`, `.scratch/final-vitest.log`, `.scratch/flow-evidence.json`.
