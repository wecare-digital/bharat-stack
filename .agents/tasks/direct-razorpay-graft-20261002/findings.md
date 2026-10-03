# Findings — five money-correctness grafts onto `stack`'s 4-route checkout

**Status: UNDEPLOYED. Flag `CHECKOUT_INITIATION_ENABLED` OFF (absent). NOT rebased, NOT pushed.
Left for orchestrator integration.**

| | |
|---|---|
| Worktree | `/Users/wecaredigital/wecare-store/.worktrees/direct-razorpay-graft-20261002` |
| Branch | `direct-razorpay-graft-20261002` |
| Merge base vs `origin/stack` | `e3c01440` (`Fix/vayulok subscribe inline (#208)`, which contains `d2b1b53f`) |
| HEAD | `cd096bc5` |
| Working tree | clean (`git status --short` empty) |
| Design | iteration 7, APPROVED |
| Code review | iteration 2, **APPROVED** |

Everything below was measured on that worktree at `cd096bc5`. The Python and client suites were
re-run while writing this report, and the counts in §4 are those runs, not quotations.

---

## 1. HOW EACH GRAFT LANDED

Nine functions in `amplify/functions/shared/lambda_utils/ecommerce/` (abbreviated **ECOM/**) and
`amplify/functions/ecommerce/checkout/handler.py` carry the whole change. Citations name
functions, never line numbers.

### Graft 1a — the server-side double-charge guard

**A single choke point, not the enumerated-exits approach.** This is the one place where the
implementation deliberately diverges from how the source branch (`0e55f648`) expressed it, and the
reason is recorded in design §1 / iteration-7 HIGH-1: an earlier iteration stated the invariant as
*"every `CHECKOUT_OPTIONS_READY` return is preceded by a successful `_record_cart_pointer`"* and
then scoped it to the two exits `_bind_and_ready` had. A **third** exit then arrived —
`_resume_lost_request_key`'s `gatewayOrderId` branch, which returns straight out of
`prepare_checkout` — and it wrote none of the three cart rows. One `CART_POINTER_SAVE_FAILED`
followed by a same-key retry therefore handed back a payable modal for a basket with no paid
memory at all, and the next fresh-key prepare charged it again. Adding the write to the third exit
would have left a maintained list that the fourth exit breaks silently.

So the enumeration was replaced by the call graph:

| Element | File · function |
|---|---|
| **The choke point** | `ECOM/website_checkout.py` · `_emit_payable_modal` — the only function in the module that may construct a `CHECKOUT_OPTIONS_READY` `PreparedCheckout`, and the only caller of `_browser_options`. It calls `_record_cart_pointer` **before** constructing the response, and refuses with `CHECKOUT_AMBIGUOUS` / `CART_POINTER_SAVE_FAILED` (200, no `options`) if any of the three writes fails or if either identity is empty |
| The three cart-row writes | `ECOM/website_checkout.py` · `_record_cart_pointer` — asserts all three rows, derived from the live un-truncated `frozen_data`, never from the possibly-trimmed `attempt['purchasedSnapshot']` |
| Exit adapter, constructs nothing | `ECOM/website_checkout.py` · `_ready_from_binding` — demoted to an argument adapter with keyword-only, no-default `keys_table` / `customer_id` / `snapshot` / `request_key` / `fallback_attempt_id`, so a forgetful call site is a `TypeError` at that line rather than an unguarded modal |
| **Step 2a**, the read half | `ECOM/website_checkout.py` · `prepare_checkout` → `_live_cart_payment` → `_paid_basket_refusal`. Placed after the gift-card/payable block and **before** `reserve_checkout_request_key`, so a refusal writes nothing at all. Arm 0 asks both per-basket paid rows **above** the same-request-key resume exemption; the `CARTPAYMENT#` pointer answers "which attempt is live on this cart". Decided on `basketHash` or `narrowBasketHash`, **never** `snapshotHash`. Any `OrderIdentityUnavailable` is 503, never a pass |
| **Step 4b**, the write half | `ECOM/website_checkout.py` · `prepare_checkout`, between the initiation gate and the reference mint — `order_keys.claim_cart_narrow_basket`, falling back to `claim_cart_basket` when the narrow identity is empty, with the guard's own read supplying the CAS basis |
| Row families | `ECOM/order_keys.py` · `CART_PAYMENT_PREFIX` / `CART_BASKET_PREFIX` / `CART_NARROW_BASKET_PREFIX`, with `resolve_cart_payment`, `resolve_cart_basket`, `resolve_cart_narrow_basket`, `record_cart_payment`, `record_cart_basket`, `record_cart_narrow_basket`, `claim_cart_basket`, `claim_cart_narrow_basket` over one private `_claim_basket_slot` (one conditional `put_item` that **replaces** the item), plus `resolve_checkout_request_key` and the promotion of `_is_conditional_failure` to public `is_conditional_failure`. **No `DeleteItem` anywhere** |
| The two basket identities | `ECOM/checkout_pricing.py` · `basket_hash` (subtractive: the frozen payload with exactly `cart.revision` dropped, `cart.id` retained) and `narrow_basket_hash` (positive enumeration over only the terms `cart_v2.calculate` contract-checks). Additive — `_snapshot_payload`, `build_snapshot` and every pre-existing hash are byte-identical |
| Handler side | `amplify/functions/ecommerce/checkout/handler.py` · `_website_prepare` passes `_attempts_table()`; `_website_snapshot` refuses V1 as `CART_V2_REQUIRED` when the gate is on |

Structurally pinned by `tests/test_graft_money_correctness.py::test_only_the_choke_point_can_emit_a_payable_modal`,
an **AST** walk (not a text scan — the module's own comments contain the searched strings)
asserting exactly one `CHECKOUT_OPTIONS_READY` construction, exactly one `_browser_options` call
site, both lexically inside `_emit_payable_modal`, with the `_record_cart_pointer` call at a lower
line number than the construction. All four payable exits — `_bind_and_ready`'s create path,
`_bind_and_ready`'s already-bound path, `_resume_lost_request_key`'s `gatewayOrderId` branch and
`_recover_ambiguous_create`'s landed-order path — route through it.

### Graft 1b — the client terminal latch

`src/pages/cart.tsx`: `railTerminalRef` (a ref, so `proceed` is never a render behind) plus
`railTerminal` state. `proceed`'s first statement is the re-entry guard, ahead of the notice reset;
both latch values are set as the **first** statements of the Razorpay `handler`, before
`await fetch`, which is what makes the latch hold on a lost verify response. The CTA carries
`disabled={ busy || railTerminal }`, and when latched the `cart-pill` is replaced by a
`<Link href="/orders/">Check your orders</Link>` — a link, never a button.
`razorpay.on('payment.failed')` and `modal.ondismiss` deliberately do **not** latch.

### Graft 2 — split-tender per-leg finalization

`ECOM/finalization.py`:

- `integer_paise` — `Decimal(str(value))`, returns `None` for any float, `bool`, fractional
  `Decimal` or unparseable value.
- `other_tender_paise` — reads **both** spellings, `giftCardRedeemedPaise` and
  `wixGiftCardRedeemPaise`.
- `_tenders_reconcile` — **exact integer equality, no tolerance**.
- `record_paid` — gained its fourth argument `verified_captured_paise`; the provider id and the
  verified figure move together, and it raises `ValueError` and writes nothing on a non-integer.
- `accept_paid` — validates the integer **before** `record_paid`, and records only the **verified
  Razorpay leg** to Wix, never the payable total. `ACCEPTED_CHECKOUT_MODES` now admits
  `WEBSITE_RAZORPAY_STANDARD` alongside `WIX_HEADLESS`, which is what makes a website attempt
  finalizable at all.
- `wix_cart_id(attempt, snapshot)` — the single resolver for "which cart is this attempt for".

The mismatch and reduced-payload refusals sit **after** the internal order record, so a shopper
whose money moved still gets exactly one `OrderTable` item staged `INTERNAL_ORDER_CREATED` then
`NEEDS_RECONCILIATION` / `TENDER_SUM_MISMATCH`, with zero `create_wix_order` and zero
`record_external_payment` calls.

### Graft 3 — `build_wix_order_payload` from the frozen snapshot

`ECOM/wix_writeback.py` · `build_wix_order_payload(*, cart, quote, coupon=None)`, with
`_relayed_money`, `_paise_money`, `CONVENIENCE_FEE_CODE`, `CONVENIENCE_FEE_NAME` and
`PAYLOAD_REDUCED_FLAG`. Currency is compared explicitly to `INR` on the first line; `_paise_money`
raises `TypeError` on a non-`int`, which is the money boundary. It builds from the **frozen
snapshot** and never from a recomputation.

The calculation it needs is exposed rather than repeated:
`ECOM/purchase_intent.py` · `build_intent_with_calculation` returns the intent **and** the
`calculate` response, with `build_intent` delegating to it and keeping its exact signature;
`calculate` is still called exactly once per build. The handler threads it through
`_v2_snapshot` / `_website_snapshot` → `_website_prepare` → `prepare_checkout`, and
`_bind_and_ready` writes `purchasedSnapshot` and `wixOrderPayload` onto the attempt under one
**joint** blob budget (`_ATTEMPT_BLOB_BUDGET_BYTES = 180_000`, `_bounded_snapshot` /
`_bounded_wix_order_payload`), trimming line items while `priceSummary`, `additionalFees` and
`cart` survive untrimmed.

### Graft 4 — the `PAYREF#` browser-leg join

`ECOM/website_checkout.py`:

- `_reference_and_create_right` — the conditional create-right claim on the request key with a
  120s staleness horizon, which **returns the reference it read back off the row**
  (`ReturnValues='ALL_NEW'`) rather than a bool, so a loser correlates on the **stored** reference
  and never on a freshly minted one.
- `_receipt_for` — falls back to `wk_<requestKey>` when there is no reference.
- `_link_reference_to_provider_order`, and `_resume_lost_request_key` with its three branches
  (`gatewayOrderId` → resume, `CREATE_IN_FLIGHT`, `CheckoutRejected('CREATE_NOT_STARTED')`).
- `prepare_checkout` gained defaulted `reference_id` and `allocate_reference` parameters, so every
  pre-existing caller and test is byte-identical. The mint lives **after** the initiation gate,
  because `order_keys.allocate_payment_reference` mints and durably reserves on every call.

Handler: `_website_prepare` supplies `_allocate_reference(attempt_id, leg_paise, gift_card_paise)`
— the amounts are arguments because both are computed inside `prepare_checkout`, so a handler
closure cannot capture them. `PAYREF#` carries `amountPaise == pay_now_paise`, the leg, **not** the
payable.

### Graft 5 — `accept_paid` wired into the browser legs

Before this change `accept_paid` had **zero production callers** on `stack`; the webhook's
`order_creation.reconcile_payment` claims an order id and stops. Fixing `finalization.py` alone
would have reproduced the "correct and unconsulted" failure
`.kiro/steering/whatsapp-payments-india-reference.md` records for `payment_status.py`. In
`amplify/functions/ecommerce/checkout/handler.py`:

| Function | Role |
|---|---|
| `_orders_table()` / `ORDERS_TABLE` | lazy table handle at module scope |
| `_load_attempt_via` | **one** loader resolving both identifier kinds — a `PAYREF#` reference and a gateway order id — onto the same six-field projection, with a fallback arm for a `GATEWAYORDER#` row carrying no `referenceId` (the pre-graft row shape) |
| `_record_verified_capture` | the paid-state write, extracted and performed **first**, so a capture is recorded even when reconciliation fails |
| `_finalize` | the **single** `accept_paid` call site, with the **split** two-leg gate: leg A the WECARE gift-card ladder, leg B `other_tender_paise` being readable. A blanket `other_legs > 0` refusal would have made graft 2 unreachable from its only caller |
| `_ClaimOutcome` / `_finalize_from_claim` | the closed-tab convergence, reached from `_status` |
| `_website_verify` | the `VERIFIED_PAID` arm, rebuilt around the above |

Both browser legs are wired: `_website_verify` → `_finalize`, and `_status` → `_finalize_from_claim`
→ `_finalize`. **No file under `amplify/functions/payments/` is modified**, so the webhook HMAC path
is byte-identical — `git diff --numstat e3c01440..HEAD -- amplify/functions/payments/` is empty.

---

## 2. THE DOUBLE-CHARGE FIX WITH ITS THREE PROVING TESTS

All three live in `tests/test_graft_money_correctness.py`. Each carries its own anti-vacuity
anchor, asserted *before* the refusal, so the row cannot pass by never exercising the path.

### (a) `test_a_revision_bump_does_not_unblock_a_paid_basket`

Two real `_website_prepare` calls over one shared keys table against a Cart V2 stub that
**increments** `cartRevision`. The anchor is that the quote hash moved and the basket identity did
not — without it the row would pass against a guard keyed on `snapshot_hash` and prove nothing.

```python
assert second_snapshot.snapshot_hash != first_hash, (
    "the two prepares produced the same snapshot hash, so this row cannot distinguish a "
    "guard keyed on the basket from one keyed on the quote")
assert cp.basket_hash(second_snapshot.frozen_data) == pointer["basketHash"]
assert pointer["basketHash"] == basket_row["basketHash"]
assert code_2 == 409
assert body_2["reason"] == website_checkout.CART_ALREADY_PAID
assert body_2["paymentAttemptId"] == paid_attempt
assert len(r.creates) == 1
assert r.db.count_prefix(order_keys.REQUEST_KEY_PREFIX) == 1, (
    "a step-2a refusal must write NOTHING AT ALL, including its own request key")
```

### (b) `test_a_paid_basket_survives_both_a_pointer_overwrite_and_a_moved_wix_field`

The four-stage durability sequence, with the stub moving a **non-enumerated** `summary.lineItems`
field (`physicalProperties`) from the third `calculate` on. Stage (b) must be **allowed** — that is
the legitimate repeat purchase — and the whole run must contain exactly two creates.

```python
assert cp.basket_hash(presented.frozen_data) != b1_fine, (
    "the moved field did not change the FINE identity, so this row does not exercise the "
    "missed-by-key path the narrow row exists for")
assert cp.narrow_basket_hash(presented.frozen_data) == b1_narrow["narrowBasketHash"], (
    "the narrow identity moved too, so there is nothing left that could refuse the request")
assert code_b == 200 and body_b["status"] == "CHECKOUT_OPTIONS_READY", (
    "a genuinely different basket past the window is the legitimate repeat purchase and must "
    "be ALLOWED; refusing it is the over-block this guard must not have")
assert len(r.creates) == 2, (
    f"a third provider create means B1 was charged twice: ...")
```

### (c) `test_a_resumed_request_key_after_a_lost_pointer_write_still_guards_the_basket`

The row the iteration-7 fix exists for: `_resume_lost_request_key`'s `gatewayOrderId` branch
reached after a `CART_POINTER_SAVE_FAILED`, then a **fresh-key** prepare refused. Parametrised over
all three cart-row writers (`CARTPAYMENT#`, `CARTBASKET#`, `CARTNARROW#`) via
`_PointerHostileTable`, which refuses exactly one named **record** write once. Run against a
**fixed-revision** stub, because `intent_fingerprint` carries `cart_revision` and a bumping
revision answers `INTENT_CHANGED` at step 3 before the resume is reachable; the bumping world is
held by `test_a_same_key_prepare_in_the_bumping_world_is_an_intent_change`.

```python
# prepare #1 — the lost write
assert code_1 == 200, "CART_POINTER_SAVE_FAILED is uncertainty, not refusal"
assert body_1["reason"] == website_checkout.CART_POINTER_SAVE_FAILED
assert "options" not in body_1, "no modal may open with the basket unguarded"
assert len(r.creates) == 1
# ANTI-VACUITY ANCHOR
assert request_rows[0].get("gatewayOrderId"), (
    "without a stored gatewayOrderId prepare #2 cannot reach the resume branch, so this row "
    "would not exercise the exit it exists for")
assert _recorded(refuse_prefix) == []

# prepare #2 — the SAME key, healthy table: the resume exit must write the rows
assert body_2["status"] == "CHECKOUT_OPTIONS_READY", body_2
assert len(r.creates) == 1, "the resume must not create a second payable order"
assert r.db.count_prefix(order_keys.CART_PAYMENT_PREFIX) == 1
assert r.db.count_prefix(order_keys.CART_BASKET_PREFIX) == 1
assert r.db.count_prefix(order_keys.CART_NARROW_BASKET_PREFIX) == 1
assert pointer["paymentAttemptId"] == stored_binding["paymentAttemptId"], (
    "the pointer must name the attempt that OWNS the payable order, not this invocation's")

# prepare #3 — a FRESH key after the payment
assert code_3 == 409, body_3
assert body_3["reason"] == website_checkout.CART_ALREADY_PAID
assert len(r.creates) == 1, (
    "a second provider create here is the double charge this whole graft exists to prevent")
```

One distinction in (c) is load-bearing and asserted explicitly: a step-4b **claim** row carries
`claimedAt` and deliberately **no** `recordedAt`, which is what puts it on the 120s create horizon
rather than the 1200s settling horizon. A paid-memory row is one with `recordedAt`, so the test
counts `_recorded(prefix)` and not bare rows.

---

## 3. THE END-TO-END REPAIR

The IaC declaration of record was two routes behind the provisioner, and the suite already knew —
seven failing ids inside the blast radius. All of it is reconciled in one commit (`90a5f3b6`),
because splitting it fails in opposite directions: a grant held but never measured, versus a
`KeyError` in the verdict loop.

**(i) Four routes in IaC.** `amplify/infra/checkout.json` declared two routes against
`provision_checkout.ROUTE_KEYS`'s four. Added `CheckoutPrepareRoute`
(`POST /ecommerce/prepare-checkout`) and `CheckoutVerifyRoute` (`POST /ecommerce/verify-callback`),
both targeting the **existing** `CheckoutIntegration`, plus `CheckoutPrepareInvokePermission` and
`CheckoutVerifyInvokePermission` — each with `Qualifier: "live"` and an **exact** `SourceArn` with
no wildcard. The existing `WECARE::WhyOneStatementPerRoute` metadata records that a
`prod/POST/ecommerce/*` prefix already matched another function's route; it was left in place.
`ROUTE_KEYS` itself was **not** touched — re-adding a route there is a duplicate-route failure at
provision time.

**(ii) The two absent functions.** `wecare-customer-profile` and `wecare-email-verification` do not
exist live (`ResourceNotFoundException`). Their provisioners (`scripts/provision_customer_profile.py`,
`scripts/provision_email_verification.py`) are on the do-not-touch list and were not modified; both
are named as ordered steps 2 and 3 of the deploy checklist. `provision_email_verification.py` is the
**only** writer of `wecare/otp/pepper`, which is `ResourceNotFoundException` today — generated
in-process with `secrets.token_urlsafe(48)`, never printed, never on a command line.

**(iii) IAM grants.** `scripts/provision_checkout.py` gained `ORDERS_TABLE =
"stack-wecare-digital-OrderTable"` at module scope and the Sid **`InternalOrderRecord`**, granting
exactly `dynamodb:GetItem`, `PutItem`, `UpdateItem` on that table — **no `DeleteItem`, no `Scan`**,
because an order record is evidence that money moved. `"ORDERS_TABLE": ORDERS_TABLE` joined
`expected_environment()`. The template caught up on the same Sid plus three pre-existing drifts:
`ReadRazorpayApiKey`, `ReadVerifiedCheckoutProfile`, `CouponAndGiftCardRedemption`, and env keys
`RAZORPAY_SECRET_ID` and `CONTACTS_TABLE`.

**(iv) OrderTable `DeleteItem`-deny and the sixth-ARN enumeration.** A grant that is never
simulated is a grant nobody checks, so `report_required_grants` widened with it:
`_EXPECTED_DENY` gained `("dynamodb:DeleteItem", ORDERS_TABLE)` — without which `--verify` reports a
false *"GRANTED BY THE INLINE POLICY BUT DENIED IN SIMULATION"* and exits non-zero on a correctly
provisioned role. The OrderTable ARN is inserted **before** the phone index, with
`core_tables = tables[:5]` and `profile_index = tables[5]`, because the list is addressed
positionally and appending after the index would have made `profile_index` the OrderTable and
simulated `Query` against the wrong resource. The same enumeration propagated to **four eval
namespaces** across the two IAM test files — both `_checkout_policy()` helpers and both
`_checkout_simulated_tables()` helpers in `tests/test_coupons_iam_and_table.py` and
`tests/test_gift_cards_iam_and_table.py` — each using that file's own
`getattr(checkout, NAME, default)` idiom, and each supplying `RAZORPAY_API_SECRET`,
`CONTACTS_TABLE` and `ORDERS_TABLE`. The first of those was the `NameError` behind five of the
seven baseline failures; the other two were latent, invisible only because callers died on
`RAZORPAY_API_SECRET` first. `tests/test_provision_checkout_contract.py` keeps its **exact**
table list and now names `prefix + "OrderTable"` as the sixth ARN.

**(v) `amplify/infra/checkout.json` reconciled with the provisioner.**
`test_the_template_matches_the_route_arns_the_script_grants` is green;
`test_the_template_declares_the_same_four_routes` asserts all four and
`test_the_template_qualifies_every_invoke_permission` asserts `len == 4`.
`CHECKOUT_INITIATION_ENABLED` stays **absent** from both the template and
`expected_environment()`, and both readiness keys stay `""`, so
`test_the_template_keeps_the_gate_absent` stays green.

**(vi) The severed `/wa-business/payment-config/raw` dependency.** No severance code was written,
and that is the finding: measured, `_website_prepare` never calls `_readiness()`, so the website leg
has no dependency on the retired Meta readback at all. `_create` and `_readiness()` are left alone —
the in-WhatsApp path is retained — and the severance is pinned by behaviour instead, by
`tests/test_graft_money_correctness.py::test_website_prepare_makes_no_lambda_invoke`, whose rig
installs a `_lambda_client` that raises `AssertionError` on any call and then drives a prepare to
`CHECKOUT_OPTIONS_READY`.

**Not run:** `scripts/provision_checkout.py --verify`. It makes live AWS calls and is
deploy-adjacent. Its one expected problem until the code deploys is recorded in §6 rather than
measured here.

---

## 4. TEST COUNTS vs THE RE-DERIVED BASELINE

Re-measured on `cd096bc5` for this report, not quoted.

### Python — `.venv/bin/python -m pytest -q -p no:randomly`

```
5 failed, 6946 passed, 1 skipped, 3 xfailed in 61.46s
```

| | baseline (`e3c01440`) | now (`cd096bc5`) |
|---|---|---|
| failed | 13 | **5** |
| passed | 6829 | **6946** (+117) |
| skipped | 1 | 1 |
| xfailed | 2 | 3 |

The 5 failing ids, in full:

```
tests/test_blog_ledger.py::test_the_committed_ledger_if_present_reconciles
tests/test_email_verification_handler.py::test_verify_returns_email_bound_proof_and_never_stamps_body_selected_customer
tests/test_gift_card_amounts_and_gst.py::test_the_convenience_fee_is_computed_on_the_full_collection_total
tests/test_gift_card_amounts_and_gst.py::test_only_one_gift_card_is_accepted
tests/test_gift_cards_iam_and_table.py::test_the_gift_card_tender_claims_a_different_effect_key_from_the_razorpay_payment
```

**Every one is in the baseline's 13. Zero NEW failing ids.**

**Set A — the previously-red route-mismatch and namespace failures. All 7 now green:**

| id | now |
|---|---|
| `test_provision_checkout_contract.py::test_the_template_matches_the_route_arns_the_script_grants` | PASS |
| `test_coupons_iam_and_table.py::test_the_checkout_role_gains_only_the_coupons_table` | PASS |
| `test_coupons_iam_and_table.py::test_the_iam_simulation_covers_every_action_the_policy_grants` | PASS |
| `test_coupons_iam_and_table.py::test_delete_item_is_still_denied_on_the_payment_attempt_and_keys_tables` | PASS |
| `test_gift_cards_iam_and_table.py::test_the_checkout_role_gains_only_the_gift_cards_table` | PASS |
| `test_gift_cards_iam_and_table.py::test_the_gift_card_grant_and_its_simulation_cannot_drift_apart` | PASS |
| `test_checkout_website_handler.py::test_verified_callback_requires_owned_attempt_and_authoritative_capture` | PASS |

**Set B — the four `xfail(strict=True)` markers that must stay red.** Three still red. The fourth,
`test_gift_cards_iam_and_table.py::test_the_website_checkout_split_binds_the_charged_amount_and_the_payable_separately`
(SEAM-G14), now **xfails** rather than failing, which is why `xfailed` is 3 where the baseline had
2. This is the single deviation in the run, and it was handled by handover rather than by lowering
a bar: that row asserts the split by requiring `_browser_options` and `payment_attempt.build` to
appear **in the same function**, and the choke point deliberately separates them, so the
assertion's *scoping* no longer matches the module. **The marker was not touched**
(`git diff e3c01440..HEAD -- tests/test_gift_cards_iam_and_table.py | grep '^[-+].*xfail'` is
empty), and the property is re-pinned by
`tests/test_graft_money_correctness.py::test_the_browser_amount_and_the_attempt_amount_are_different_expressions`,
an AST assertion over `_bind_and_ready`'s arguments. The handoff is written into the row's own
docstring and into the deploy checklist, naming the replacement row and stating that clearing
SEAM-G14 means **rescoping** the assertion, not flipping the marker.

**Set C — known red, out of scope.** `test_blog_ledger` and `test_email_verification_handler`,
both permitted by the baseline, neither file touched by this change.

Targeted: `tests/test_graft_money_correctness.py` alone — **109 passed in 1.22s**, with
`CHECKOUT_INITIATION_ENABLED` absent from the environment.

### Client — `npm run build` (exit 0) then `npx vitest run`

```
Test Files  3 failed | 66 passed (69)
      Tests  6 failed | 836 passed | 1 skipped (843)
```

| | baseline | now |
|---|---|---|
| failed | 6 | **6** |
| passed | 827 | **836** (+9) |
| skipped | 1 | 1 |

The 6 failing ids are **exactly** the baseline's six, all one cause (`Unable to find a label with
the text of: Country code`), all owned by the phone-field / country-code workstream, in files this
change does not touch:

```
src/test/AccountSignIn.test.tsx > ... > never infers India for bare digits - the selected code decides
src/test/AccountSignIn.test.tsx > ... > shows the default country code rather than inferring one
src/test/BlogSubscribe.test.tsx > BlogSubscribe > renders the four requested fields and keeps Subscribe locked until both verifications
src/test/PublicPageTopBand.test.tsx > ... > is one divided field: a code segment and a number segment, with no native validation
src/test/PublicPageTopBand.test.tsx > ... > uses the SELECTED code for bare national digits, never the inferred one
src/test/PublicPageTopBand.test.tsx > ... > associates the error with the field so a correction is possible
```

`src/test/CartCheckout.test.tsx` alone: **32 passed** (24 pre-existing + 8 new).
`npx tsc --noEmit` exits **0**.

**No NEW failure on either side, and the previously-red route-mismatch family is green.**

---

## 5. BROWSER EVIDENCE

There is no Playwright or Puppeteer in this repo, and `POST /ecommerce/verify-callback` does not
exist on API `zllr9lrg7j`, so a real-browser pass against a deployed stack is impossible. The flow
was exercised in two halves with the Razorpay SDK **fully stubbed** — no provider call, no charge.

**Server half** —
`tests/test_graft_money_correctness.py::test_the_stubbed_browser_flow_yields_one_order`, driving the
real `handler.handler` through `prepare` then `verify` with a verified CRM profile, a Cart V2
snapshot, an owned address and a delivery method, and initiation injected as a function
argument / module attribute. `CHECKOUT_INITIATION_ENABLED` stays absent from the environment, so
this is not a flag enable.

```
prepare -> 200   status CHECKOUT_OPTIONS_READY
  options = { keyId, orderId: "order_GRAFT_1", amountPaise: 2625123,
              currency: "INR", prefill, paymentAttemptId }
create_order called ONCE: amount_paise 2625123, receipt "WD-PAY-…" (the reference),
              notes { paymentAttemptId, customerId, snapshotHash, referenceId }
verify  -> 200   status VERIFIED_PAID   orderNumber "WD-ORD-…"
```

| claim | evidence |
|---|---|
| **one order** | `OrderTable` rows **1**, `ORDERNO#` rows **1**, one distinct `orderNumber` satisfying `order_keys.is_current_public_order_number`. A replayed verify with the same payment id returns 200 and leaves both at 1 |
| **integer paise** | `isinstance(options["amountPaise"], int)` and not a `bool`; a recursive walk of the whole payload raises on any `float` |
| **INR** | `options["currency"] == "INR"`, compared explicitly, never inferred from the amount |
| **public key id only** | `options["keyId"] == FIXTURE_PUBLIC_KEY_ID`; the fixture's secret sentinel, `key_secret` and `keySecret` are absent from `json.dumps(response)` and from every captured log record. The key set is an **allow-list** — `set(options) == {keyId, orderId, amountPaise, currency, prefill, paymentAttemptId}` — so a new field cannot leak by omission |
| the calculator total, not the raw Wix total | `2625123 == 2549900 + 63748 + 11475`, and `!= 2549900` |

Attempt row after the flow: `PAYMENT_PAID`, `amountPaise 2625123`, `razorpayChargedPaise 2625123`,
`wixGiftCardRedeemPaise 0`, `verifiedCapturedPaise 2625123`, `currency INR`,
`checkoutMode WEBSITE_RAZORPAY_STANDARD`. Key prefixes written: `CARTBASKET#`, `CARTNARROW#`,
`CARTPAYMENT#`, `CUSTOMERCART#`, `GATEWAYORDER#`, `ORDERNO#`, `PAYMENTATTEMPT#`, `PAYREF#`,
`PROVIDERPAYMENT#`, `REQUESTKEY#` — all three cart rows, exactly one `GATEWAYORDER#`, exactly one
`PAYREF#`.

With the write-back gate left closed (the live state) the row stages `INTERNAL_ORDER_CREATED` then
`NEEDS_RECONCILIATION` / `WIX_WRITE_CONTRACT_REQUIRED` — correct dormancy, and the shopper still
gets an order number for a row `service-api` can list. A separate set of rows opens all four
`wix_writeback.is_enabled()` conditions as per-test `monkeypatch.setenv` values (reverted by
pytest; nothing in `amplify/infra/` or `scripts/provision_checkout.py` sets any of them) and runs
the ladder to `WIX_CART_COMPLETED` with exactly three Wix calls — create the order, record the
already-collected payment, close the cart — the figure handed to Wix being `26251.23`, i.e.
`2625123` paise through `Money.to_wix` by integer division, and provably the **leg** rather than the
payable.

**Client half** — `src/test/CartCheckout.test.tsx > … > the full stubbed rail: cart -> profile ->
prepare -> modal -> verify -> one order`, a real React render in jsdom with `fetch` and
`window.Razorpay` stubbed; `FakeRazorpay.open()` performs no network I/O. The object handed to
`new window.Razorpay(...)` carries `amount 2625123` (`Number.isInteger` true), `currency 'INR'`, a
`key` equal to the public key id, a non-empty `order_id`, **no** key whose name matches `/secret/i`
and no `/secret/i` match in `JSON.stringify(options)`. Running the handler produces exactly **one**
POST to `/ecommerce/verify-callback`, the latch set, and navigation to
`/checkout/status/?a=att-latch-1`.

**Not exercised:** no Chrome/CDP pass, no screenshots, no real Razorpay modal. The gap is the
network between the two halves plus the provider's own modal, and closing it requires §6.

---

## 6. DEPLOY CHECKLIST — for the orchestrator, AFTER approval. NONE OF IT EXECUTED.

Nothing below was run. Full prose version with the measured fact behind each step:
`docs/execution/direct-razorpay-graft-20261002-deploy-checklist.md`.

**The fact that matters most, and it is independent of the flag:** `POST /ecommerce/verify-callback`
does not exist on API `zllr9lrg7j`. The browser's payment return posts to a route that is not
there, so none of the five grafts can run in the current deployment regardless of the gate. Step 1
is therefore a provisioner run, not a flag.

### 6.1 Ordered steps

| # | Who | Command / action |
|---|---|---|
| 1 | AGENT | `python scripts/provision_checkout.py` — creates the 2 missing routes + 2 invoke permissions, adds the `InternalOrderRecord` Sid, sets the env keys in §6.3 |
| 2 | AGENT | `python scripts/provision_customer_profile.py` — `wecare-customer-profile` does not exist |
| 3 | AGENT | `python scripts/provision_email_verification.py` — `wecare-email-verification` does not exist, and it is the only writer of `wecare/otp/pepper` (absent today; generated in-process, never printed) |
| 4 | AGENT | `python scripts/deploy_all_lambdas.py wecare-checkout wecare-customer-profile wecare-email-verification` |
| 5 | AGENT | `python scripts/snapstart_publish.py` — publish a version and move the `live` alias off **v5** |
| 6 | OWNER | confirm a shopper can satisfy `PROFILE_REQUIRED` |
| 7 | **OWNER-ONLY** | set `CHECKOUT_INITIATION_ENABLED=true` on `wecare-checkout`. **Standing refusal for the agent** |
| 8 | AGENT | publish a version and move `live` again — an env change does not reach the alias until a version is published |
| 9 | OWNER | first payment |

### 6.2 Functions to update-code + publish + alias-move

Per `.kiro/steering/lambda-snapstart-deploy.md`, the sequence for each is
`aws lambda update-function-code` (which updates `$LATEST` only) → publish a version → wait for
`State=Active` → move the `live` alias. `scripts/snapstart_publish.py` automates steps 2–4 and
`scripts/deploy_all_lambdas.py` calls it at the end; if a function is deployed by hand, run the
publisher explicitly or the API keeps serving old code.

| Function | Why | Alias |
|---|---|---|
| `wecare-checkout` | carries all five grafts; invoked by the HTTP API **through its `live` alias**, so `$LATEST` does not serve. Rollback is `aws lambda update-alias --function-name wecare-checkout --name live --function-version 5` |
| `wecare-customer-profile` | does not exist; created by step 2, then deployed | `live` |
| `wecare-email-verification` | does not exist; created by step 3, then deployed | `live` |

Re-derive the alias inventory rather than trusting a count; the steering file's 58/7 split is a
dated snapshot and drifts as aliases are provisioned.

### 6.3 Routes to create

Both on API `zllr9lrg7j`, stage `prod`, targeting the existing `CheckoutIntegration`, each with its
own invoke permission carrying `Qualifier: live` and an **exact** `SourceArn` (no wildcard — a
shared `prod/POST/ecommerce/*` prefix has already matched another function's route, and the failure
is a silent 500 with no Lambda log line):

```
POST /ecommerce/prepare-checkout      statement id  apigateway-invoke-post-ecommerce-prepare-checkout
POST /ecommerce/verify-callback       statement id  apigateway-invoke-post-ecommerce-verify-callback
```

Already live and unchanged: `POST /ecommerce/checkout`, `POST /ecommerce/checkout/status`.
Do **not** add either key to `provision_checkout.ROUTE_KEYS` — all four are already there, and a
duplicate is a provision-time failure.

### 6.4 Environment variables, by name

On `wecare-checkout`, set by `provision_checkout.expected_environment()`:

| Name | Note |
|---|---|
| `ORDERS_TABLE` | **new**; value `stack-wecare-digital-OrderTable`. Absent live today |
| `CONTACTS_TABLE` | pre-existing drift; absent live today |
| `RAZORPAY_SECRET_ID` | pre-existing drift; absent live today. Names the secret `wecare/razorpay/api` — a **name, not a value**; the function reads `key_id` lazily at request time |
| `PAYMENT_ATTEMPTS_TABLE`, `COMMERCE_KEYS_TABLE`, `WIX_API_KEY_SECRET`, `WIX_SITE_ID`, `SENDER_FUNCTION`, `PAYMENT_WABA_ID` | unchanged |
| `EXPECTED_CONFIGURATION_NAME` | seeded **empty**; `READINESS_KEYS` checks presence only |
| `EXPECTED_PROVIDER_MID` | seeded **empty** by the provisioner. The value of record is `EXPECTED_PROVIDER_MID=acc_TTFSyolquKEZEy` — an identifier, not a secret (it already appears in `payment_readiness.py`'s docstring). Deliberately **not** seeded, because a seeded value makes `--verify` exit non-zero by design and the only way back would be to weaken the readiness check. An owner fills it at step 7's discretion |
| **`CHECKOUT_INITIATION_ENABLED`** | **stays OFF — absent from env, from `expected_environment()` and from `amplify/infra/checkout.json`.** The single flag in this change. Setting it is step 7, OWNER-ONLY, and a standing refusal for the agent |

Not touched, and this is why grafts 3 and 5 stay dormant after step 8:
`WIX_WRITEBACK_ENABLED`, `WIX_ECOM_WRITE_CONFIRMED`, `WIX_CART_V2_WRITE_CONTRACT`. Only
`WIX_SITE_ID` is set live, so all four `wix_writeback.is_enabled()` conditions remain false and
**no Wix order and no Wix payment record exist after the first payment**. Closing that is a
separate change with its own attestation.

### 6.5 IAM changes, by Sid

On the inline policy of the checkout role, written by `provision_checkout.py`:

| Sid | Change | Actions |
|---|---|---|
| **`InternalOrderRecord`** | **NEW** | `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem` on `stack-wecare-digital-OrderTable`. **No `DeleteItem`, no `Scan`** — an order record is evidence that money moved, and `("dynamodb:DeleteItem", ORDERS_TABLE)` is in `_EXPECTED_DENY` so `--verify` asserts the deny rather than reporting it as drift |
| `ReadRazorpayApiKey` | pre-existing drift, now declared in the template too | unchanged |
| `ReadVerifiedCheckoutProfile` | pre-existing drift, now declared in the template too | unchanged |
| `CouponAndGiftCardRedemption` | pre-existing drift, now declared in the template too | unchanged |
| `PaymentAttemptAndCommerceKeys`, `ReadWixApiKey`, `InvokeWhatsAppSender` | unchanged | unchanged |

Lambda resource-policy statements (not role Sids): the two route statement ids in §6.3. New ids let
the narrow statements go on **first** — resource-policy statements are OR'd, so the route is never
left unauthorised, and `add_permission` cannot edit a statement in place.

No Cognito change. No new table. No new bucket. No secret created or read by the agent.

### 6.6 Expected `--verify` output, so a known problem is not read as a regression

`python scripts/provision_checkout.py --verify` reports **exactly one** problem until step 4 lands:

```
env ORDERS_TABLE mismatch on live (v5)
```

That is the declaration being ahead of the deployment, which is the correct state for a change that
ships dormant. It clears at step 4. `--verify` was **not run** during this build: it makes live AWS
calls and is deploy-adjacent.

### 6.7 Known gap, pre-existing and out of scope

Neither `wecare-customer-profile` nor `wecare-email-verification` has an `amplify/infra/*.json`
declaration of record; both are script-provisioned only, so their IAM, environment and routes exist
in one place rather than two. That predates this change. The remedy is one template per function,
modelled on `amplify/infra/checkout.json`, which this change has just reconciled against its own
provisioner and which can serve as the pattern.

---

## FINAL STATE

**UNDEPLOYED.** No `update-function-code`, no publish, no alias move, no live route, no live env
set, no IAM or Cognito mutation, no provisioner run (not even `--verify`), no payment capture,
refund or payment-configuration mutation, no live send, no `secretsmanager get-secret-value` in any
spelling, no PayU, no new S3 bucket.

**Flag `CHECKOUT_INITIATION_ENABLED` is OFF** — absent from the environment, from
`provision_checkout.expected_environment()` and from `amplify/infra/checkout.json`. Every
occurrence of the name in either file is a comment, a docstring, or the `--verify` check that
reports it being ON as a problem.

**NOT rebased, NOT pushed.** The worktree was never rebased onto or fast-forwarded to `stack`; its
merge base is still `e3c01440`. `git ls-remote --heads origin direct-razorpay-graft-20261002` is
empty. No force push, no history rewrite, no `git add -A` / `.` / `-u`, no bare `stash`; every
commit used `git commit --only <explicit paths>`. Working tree clean.

**Left for orchestrator integration.**

### Branch

```
direct-razorpay-graft-20261002
```

### Commits on it (oldest first, `e3c01440..cd096bc5`)

```
68c82f50  test: teach the CRM fake OR and ordered comparison, and name the IAM eval constants
43eb4118  feat: durable per-basket paid memory, two basket identities, and the Wix order payload
2db80956  feat: one payable modal per basket, split-tender finalization, and the PAYREF# join
e4bbcb2d  feat: latch the cart's payment rail once it has returned a result
90a5f3b6  fix: reconcile checkout.json with the provisioner, and gate what must not regress
60e58781  docs: the nine ordered steps to a first payment, and the evidence for this change
3ddcec72  fix: refuse a cart pointer with no identity, and document the create-right orphan
c63179a9  test: drive finalization and the split-tender wiring through the handler, not around it
818d2861  docs: hand SEAM-G14 over with its replacement row named, and record iteration 2
cd096bc5  docs: record iteration 2 in the change-authority matrix
```

`cd096bc5` is the last **implementation** commit: ten commits, 20 files, every one named in the
plan, and the tree the APPROVED code review and the §4 counts were measured against. This report
itself lands on the same branch as one or two subsequent `docs:` commits carrying only
`.agents/tasks/direct-razorpay-graft-20261002/findings.md`, so branch HEAD is ahead of `cd096bc5`
by documentation alone. No source, test, IaC or script file changed after `cd096bc5`.
