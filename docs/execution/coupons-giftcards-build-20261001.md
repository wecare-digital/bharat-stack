# Wix coupons + gift cards — build handoff, 2026-10-02

**Read this before `coupons-20261001.md` or `gift-cards-service-plugin-20261001.md`.** Those two are
the *design*, promoted to revision 4 with every review finding applied. **This** is what actually
landed, what did not, who owns each remaining seam, and which `xfail(strict=True)` test is holding
each seam's place until its producer arrives.

It exists so a later session does not have to re-derive the seams from the code. Everything here was
measured in this tree, not inferred. Where a fact could not be measured it says so.

---

## 0. Status at a glance

| | |
|---|---|
| Branch | `stack` (single-branch workflow; nothing was pushed) |
| Test result | **6781 passed · 1 skipped · 7 xfailed · 0 failed · 0 xpassed** (`.venv/bin/python -m pytest -q`, whole tree) |
| `tests/` alone | 6744 passed · 1 skipped · 7 xfailed |
| The owned suite | **508 passed · 7 xfailed · 0 failed · 0 xpassed** |
| Baseline before this work | 6334 passed / 1 failed in `tests/` (a pre-existing failure another session fixed mid-run) |
| ⚠️ A later re-run | 5 failures appeared in **`tests/test_url_host_routing_rules.py`** — a **concurrent session's** URL-routing convergence, provably not this work's, and deliberately left alone. **§12 has the evidence and the reasoning** |
| New Lambdas | **3 authored, 0 deployed** — `wecare-coupons`, `wecare-gift-cards`, `wecare-wix-giftcard-spi` |
| New provisioner scripts | **6 authored, 0 run.** Every one defaults to a dry run and requires `--apply` |
| AWS resources created | **none.** No table, role, route, alarm, KMS key, alias or function version |
| Flags changed | **none** |
| Wix calls made | **none.** The SPI is not registered; no coupon was created in Wix |
| Open seams | **12** (down from 23 — SEAM-C3b and SEAM-G9 landed) |
| `xfail(strict=True)` marks | **7**, every producer a do-not-touch file. Enumerated in §6 |
| Interpreter | `/Users/wecaredigital/wecare-store/.venv/bin/python` — bare `python` is not on PATH |

**Nothing in this build charges, captures, refunds, deploys, publishes, moves an alias, enables a
flag, or pushes.** The one production-shaped change is an IAM *script* edit that has not been
applied (§3).

---

## 1. Plan items, final status

`.agents/tasks/wix-coupons-giftcards-20261001/plan.md`, items 1-28.

| # | Item | Status |
|---|---|---|
| 1 | `coupon_store.py` — rows, attributes, §5.4 validation, DECISION 5 attributes | ✅ COMPLETE |
| 2 | `coupon_store.py` conditional-write surface: `claim`, `hold`/`release`, `commit_redemption(…, cart_id, …)` | ✅ COMPLETE |
| 3 | `tests/test_coupon_store.py` (1-21) + access-pattern enumeration + one-UpdateItem hold + NIT-5 branch | ✅ COMPLETE |
| 4 | `wix_coupons.py` — injected request callable, three methods, whole-rupee ints | ✅ COMPLETE |
| 5 | `tests/test_wix_coupons_contract.py` (22-41) + `wix_coupon_get_response.json` | ✅ COMPLETE |
| 6 | `ecommerce/coupons/handler.py` — 5 staff + 2 customer routes, lazy secret read | ✅ COMPLETE |
| 7 | `tests/test_coupon_logging_and_vocabulary.py` (59-61), `tests/test_coupons_routes_and_registry.py` (62-64) | ✅ COMPLETE |
| 8 | `tests/test_coupon_reconciliation.py` (42-51), DECISIONS 3 + 4, MEDIUM-8 | ✅ COMPLETE |
| 9 | `scripts/provision_coupons_table.py` | ✅ COMPLETE (authored; **not run**) |
| 10 | `scripts/provision_coupons_role.py`, `scripts/provision_coupons_routes.py` | ✅ COMPLETE (authored; **not run**) |
| 11 | `tests/test_coupons_iam_and_table.py` (52-56, 58) | ✅ COMPLETE |
| 12 | `gift_card_store.py` — HMAC key, DECISION 9 rows, DECISION 5 attributes, `redeem_cap` | ✅ COMPLETE |
| 13 | `gift_card_settlement.py` — the ladder, `advance`, two-leg `is_fully_settled` | ✅ COMPLETE |
| 14 | `tests/test_gift_card_store.py` (42-64) with MEDIUM-7 renames | ✅ COMPLETE |
| 15 | `gift_card_spi_auth.py` — JWT verify, MEDIUM-4 applied | ✅ COMPLETE |
| 16 | `tests/test_gift_card_two_leg_finalization.py` (65-86) | ✅ COMPLETE |
| 17 | `tests/test_gift_card_spi_auth.py` (1-21) + three JWT fixtures | ✅ COMPLETE |
| 18 | The two handlers — SPI (3 paths) and gift-cards (**5** routes, MEDIUM-5) | ✅ COMPLETE |
| 19 | `tests/test_gift_card_spi_contract.py` (22-41), `tests/test_gift_card_amounts_and_gst.py` (87-100) | ✅ COMPLETE |
| 20 | `provision_gift_cards_table.py` (DECISION 6 CMK), `provision_gift_cards_roles.py`, `provision_gift_card_routes.py` (renamed, NIT-3) | ✅ COMPLETE (authored; **not run**) |
| 21 | `tests/test_gift_cards_iam_and_table.py` (101-115) | ✅ COMPLETE |
| 22 | `check_data_model_drift.py` UNDECLARED_ALLOWED ×2; `RAW_SCAN_ONLY_FILES` ×3 + parametrisation; spec test 57 | ✅ COMPLETE |
| 23 | `deploy_all_lambdas.py` ×3 `Spec`; `test_exactly_one_spec_is_awaiting_provisioning` → 8 names; spec test 65 (landed as **two** parametrised tests, §7) | ✅ COMPLETE |
| 24 | **The HIGH-5 edit** — all three parts of `provision_checkout.py` + the two invalidated contract tests | ✅ COMPLETE — **landed, no fallback** (§3) |
| 25 | Remove the xfail marks from tests 52, 52a, 52b, 107, 107a | ✅ COMPLETE — **four** marks removed, not five (§6) |
| 26 | Promote both design docs to `docs/execution/` with every review resolution applied | ✅ COMPLETE |
| 27 | This handoff document | ✅ COMPLETE |
| 28 | Full-tree regression + finding audit | ✅ COMPLETE — 0 failed, 0 xpassed; audit in §7 |

### `tests/test_gift_card_settlement.py` was deliberately NOT created

It appears in FEAT-002's acceptance-criteria command line and in **none** of its steps. The design
puts the whole ladder (tests 65-86) in `tests/test_gift_card_two_leg_finalization.py`, which is where
every `advance` / `stage` / `STAGE_RANK` / `condition_expression` / `is_fully_settled` assertion lives.
A second file would have split one subject across two reports. The criterion says "omit any file not
created".

---

## 2. Files created and edited

### Created — 5 shared modules, 3 handlers, 6 provisioners, 13 test files, 6 fixtures

```
amplify/functions/shared/lambda_utils/ecommerce/coupon_store.py
amplify/functions/shared/lambda_utils/ecommerce/wix_coupons.py
amplify/functions/shared/lambda_utils/ecommerce/gift_card_store.py
amplify/functions/shared/lambda_utils/ecommerce/gift_card_settlement.py
amplify/functions/shared/lambda_utils/ecommerce/gift_card_spi_auth.py
amplify/functions/ecommerce/coupons/handler.py
amplify/functions/ecommerce/gift-cards/handler.py
amplify/functions/ecommerce/wix-giftcard-spi/handler.py
scripts/provision_coupons_table.py
scripts/provision_coupons_role.py
scripts/provision_coupons_routes.py
scripts/provision_gift_cards_table.py
scripts/provision_gift_cards_roles.py
scripts/provision_gift_card_routes.py          # renamed from ..._gift_card_spi_routes.py (NIT-3)
tests/coupon_fake_dynamo.py                    # a new test helper, not a spec test - see below
tests/test_coupon_store.py
tests/test_wix_coupons_contract.py
tests/test_coupon_reconciliation.py
tests/test_coupon_logging_and_vocabulary.py
tests/test_coupons_routes_and_registry.py
tests/test_coupons_iam_and_table.py
tests/test_gift_card_store.py
tests/test_gift_card_two_leg_finalization.py
tests/test_gift_card_spi_auth.py
tests/test_gift_card_spi_contract.py
tests/test_gift_card_amounts_and_gst.py
tests/test_gift_cards_iam_and_table.py
tests/fixtures/wix_coupon_get_response.json
tests/fixtures/wix_cart_v2_coupon_applied_v2_shape.json
tests/fixtures/wix_cart_v2_gift_card_partial.json
tests/fixtures/wix_spi_get_balance_jwt_payload.json
tests/fixtures/wix_spi_redeem_jwt_payload.json
tests/fixtures/wix_spi_void_jwt_payload.json
docs/execution/coupons-20261001.md                       # promoted, revision 4
docs/execution/gift-cards-service-plugin-20261001.md     # promoted, revision 4
docs/execution/coupons-giftcards-build-20261001.md       # this file
```

**`tests/coupon_fake_dynamo.py` is a new helper rather than an extension of
`tests/crm_fake_dynamo.py`**, and the reason is worth keeping: the shared fake raises `AssertionError`
on `OR` and reads a boto3 `Key().eq()` object for queries. `coupon_store` needs a **three-way `OR`**
(the DECISION 5 hold gate) and a **string** `KeyConditionExpression`, because it holds no boto3 client
at all. Teaching the shared fake would have meant editing a helper **eleven** other test files depend
on, from a session owning none of them. The new fake keeps the same discipline: an unrecognised
expression form **raises** rather than being assumed to succeed, and `.scan()` raises outright.

### Edited — 6 existing files, all deliberately

| File | Change | Why it had to be this file |
|---|---|---|
| `scripts/check_data_model_drift.py` | 2 `UNDECLARED_ALLOWED` entries (`CouponsTable`, `GiftCardsTable`) | `amplify/data/resource.ts` declares neither model, so both would land in `undeclared_tables_unexpected` and `--gate` would exit non-zero once the tables exist |
| `tests/test_payment_vocabulary_at_decision_points.py` | 3-entry `RAW_SCAN_ONLY_FILES` + parametrisation of `test_no_decision_compares_a_payment_word_raw` | The three new handlers must be AST-scanned for a raw `'captured'`; none imports `payment_status`, so forcing them into `CONSULTING_FILES` would **weaken** the import assertion |
| `scripts/deploy_all_lambdas.py` | 3 `Spec(...)` entries | A name absent from `SPECS` is **not deployable at all** |
| `tests/test_deploy_map_provisioning.py` | `test_exactly_one_spec_is_awaiting_provisioning` → the 8-name list, with a comment per new name | The existing test asserted an exact ordered list of **five** and would otherwise fail. The count is a deliberate guard, so the addition has to read as deliberate |
| `scripts/provision_checkout.py` | **The three-part HIGH-5 edit** (§3) | Parts 1-2 without part 3 break the script's own `--verify` gate |
| `tests/test_provision_checkout_contract.py` | One assertion **strengthened**, one **widened**, three new tests, and the IAM fake re-shaped (§3) | Both existing assertions became wrong by construction |

**`.kiro/steering/META-BETA-REQUEST-EMAIL.md` shows as ` M` and was NOT touched by this work.** It was
already dirty at baseline; all three implementing features recorded the same thing. `--only` excluded
it from every commit.

---

## 3. The HIGH-5 edit landed — `provision_checkout.py`, no fallback

DECISION 7 required a guard before editing: run
`git status --short scripts/provision_checkout.py tests/test_provision_checkout_contract.py`, and if
either was held by another session, **leave it a seam** and mark tests 52/52a/52b/107/107a
`xfail(strict=True)`.

**The guard returned EMPTY. Neither file was held. The fallback did NOT fire.** All three parts landed
in one visit, covering **both** new table ARNs together, which removes the ordering hazard SEAM-C3b and
SEAM-G9 each warned about ("whichever lands second adds only its ARN").

| Part | What | Current anchor |
|---|---|---|
| — | `COUPONS_TABLE` / `GIFT_CARDS_TABLE` module constants | `:132-133` |
| (a) | A **second** DynamoDB statement, `Sid: CouponAndGiftCardRedemption`, granting `GetItem, PutItem, UpdateItem, DeleteItem` on both new table ARNs | `:407`, ARNs at `:418-419` |
| (b) | `_SIMULATED_ACTIONS` gains `dynamodb:DeleteItem` (now 5 actions); the simulated `tables` list gains both ARNs (now 4) | `:683`; `:821-824` |
| (c) | `_EXPECTED_DENY` + the verdict loop re-keyed on `(EvalActionName, EvalResourceName)` | `:696-698`; `:848` |

**Re-derive these anchors rather than trusting them.** The revision-3 documents quoted 661 and 785;
those were one off at review time (R4-N2 corrects them to 662 / 785) and the edit has since moved them
outright. That is exactly why the promoted docs cite a date rather than a commit id.

**Two statements, not one widened statement**, because the two grants genuinely differ: `DeleteItem` is
granted on the two redemption tables and deliberately **withheld** on `PaymentAttemptsTable` and
`WixOrderIds`. Nothing was added to `wecare-digital-lambda-role`; the existing AST test
`test_the_shared_fleet_role_is_never_touched` still passes.

### Why part (c) was not optional

The verdict loop aggregated decisions **per action across every resource**. With part (a) alone,
`dynamodb:DeleteItem` is *allowed* on two tables and *implicitly denied* on two — by design — so its
aggregate is `{"allowed", "implicitDeny"}`, which falls into the *"granted by the inline policy but
denied in simulation"* branch and makes `--verify` exit non-zero. **A correctly provisioned role would
fail its own verifier.**

`_EXPECTED_DENY` is a **measured expectation, not a suppression**, and that is pinned in both
directions: a role widened until `DeleteItem` is allowed everywhere **fails**, naming
`PaymentAttemptsTable` and `WixOrderIds` and not naming the two redemption tables.

### One structural change part (c) forced that the review did not name

`dynamodb:ConditionCheckItem` is granted on **no** table, and its judgement was never per-table — it
asks *"does the handler's import closure open a transaction at all"*. Folding it into a per-pair loop
would emit the same finding up to four times. Its decisions are therefore aggregated across all four
tables **inside** the loop and judged **once** after it, preserving all three existing outcomes
(`NOT JUDGED` / `REQUIRED GRANT` / not required) and the exact problem strings the four existing
grant-report tests assert on. The per-pair loop handles only the actions the policy actually grants.

### Two test-support edits that were not optional

1. **`_FakeIam.simulate_principal_policy` returned one result per ACTION with no `EvalResourceName`.**
   That was indistinguishable from the real API only while every action had the same answer on every
   table — which `DeleteItem` no longer does, so re-keying the loop would have raised `KeyError`
   against the old fake. It now returns one result per `(action, resource)` pair carrying
   `EvalResourceName`, defaulting to "allowed unless the pair is one `_EXPECTED_DENY` withholds", so the
   baseline fake models a **correctly** provisioned role. `expected_deny=None` means "fill in from the
   script"; an explicit `frozenset()` models a role that was widened, which is what the new negative
   test uses.
2. **`_checkout_policy` / `_checkout_simulated_tables` in `tests/test_coupons_iam_and_table.py`** eval
   the policy literal against a fixed namespace that had `COUPONS_TABLE` but not `GIFT_CARDS_TABLE`, so
   all three of its checkout tests raised `NameError` the moment the new constant was referenced. Both
   namespaces now supply it through the same `getattr(checkout, …, default)` idiom already used for
   `COUPONS_TABLE`. `tests/test_gift_cards_iam_and_table.py` already supplied both.

### The two existing contract tests: one strengthened, one widened

| Test | Before | After |
|---|---|---|
| `test_the_role_cannot_delete_a_payment_attempt` | `dynamodb:DeleteItem` appears in **NO** statement | **Per statement:** no statement granting `DeleteItem` names the `PaymentAttemptsTable` or `WixOrderIds` ARN. **Narrower, not looser** — it survives any number of future tables and fails the moment one of these two is folded into a `DeleteItem` statement. The `actions >= {GetItem, PutItem, UpdateItem}` floor is kept |
| `test_the_role_names_only_the_two_known_tables` → `…_the_four_known_tables` | exactly 2 table ARNs | exactly 4, still an **exact sorted list** (the interesting failure is a table nobody decided to add), with the no-trailing-wildcard assertion kept on each |

### Three new tests pin part (c), so the acceptance criterion is asserted rather than inspected

- `test_the_verdict_is_keyed_on_the_action_and_the_resource`
- `test_a_correctly_provisioned_role_passes_with_delete_item_split_two_ways` — **the regression part (c)
  exists to prevent.** Without (c) this fails.
- `test_delete_item_becoming_allowed_on_an_evidence_table_is_reported` — the other direction.

### `--verify` has NOT been run

It needs AWS and a live role, and the new grant is not on the live role until someone runs
`provision_checkout.py --apply`. Everything above is verified **offline**, over the policy document and
the script AST. **When it is run, expect four `DeleteItem` lines:** allowed on `CouponsTable` and
`GiftCardsTable`, "correctly withheld" on `PaymentAttemptsTable` and `WixOrderIds`.

---

## 4. The cross-workstream seam register — complete

Every seam, its owner, its exact anchor, and the test holding its place. **A blank xfail cell means the
seam is real but has no strict mark**, either because its property is asserted unconditionally
elsewhere or because it is a configuration item with nothing to assert; the "Pinned by" column says
which.

**Re-derive every line number before editing.** They were measured 2026-10-02 and other sessions commit
to this tree.

### Coupons

| Seam | What the producer must do | Exact anchor | Owner | `xfail(strict=True)` holding its place |
|---|---|---|---|---|
| **SEAM-C1** | **Two changes, one visit.** (a) `add_coupon` posts the V1 field; V2 needs `{"coupon": {"code": …}}`, with `coupon` **and** `coupon.code` both in the schema's `required` array — **until this lands no coupon applies at all.** (b) tighten the length guard from 100 to **50** (`CouponInput.code` is `maxLength 50`) | `cart_v2.py:333` — the `body={"couponCode": code.strip()}` argument; `cart_v2.py:329` — the `len(code.strip()) > 100` guard | cart_v2 owner | `tests/test_coupon_reconciliation.py::test_add_coupon_sends_the_v2_nested_coupon_body` |
| **SEAM-C1b** | Surface `coupons[0].id` on the **payable projection** so a removal can be offered. `calculate` *does* return the ids (`"cart": deepcopy(cart)` at `:535`, and `cart["coupons"]` holds `{id, code}`); they are not on the projection the cart view is built from | `cart_v2.CartV2.calculate`'s payable projection, around `cart_v2.py:535` | cart_v2 owner | — · **Pinned by:** nothing here; it is a UX gap, not a money gap. `Remove Coupon` requires `couponId`, so the design records the dependency |
| **SEAM-C1c** | Update the **two** existing cart tests SEAM-C1 makes wrong by construction | `tests/test_wix_cart_v2_coupons_and_stock.py:91` (the body literal) and `:160` (`set(body) == {"couponCode"}`) | cart_v2 owner | — · **Pinned by:** `test_a_browser_cannot_supply_a_discount_amount_only_a_code_to_validate` must keep its **property**, not just its shape: asserting only `set(body) == {"coupon"}` would let `{"coupon": {"code": …, "discountPaise": 500}}` through. Test 44 asserts the same property from our own routes, so the guarantee does not rest on one file another session owns |
| **SEAM-C2** | **BOTH writable terms** (widened by HIGH-1). (a) `additionalFees[]` with **all three** price fields; (b) `appliedDiscounts[]` relayed **byte-identically** from `cart.priceSummary.discount.amount` | the builder of `attempt['wixOrderPayload']`. Looked up by the name **`build_wix_order_payload`** in `website_checkout` / `wix_writeback` / `initiation` / `order_creation` / `finalization`, called as `producer(cart=…, quote=…, coupon=…)`. **If it lands under another name, update `SEAM_C2_PRODUCER` / `SEAM_C2_HOMES` at the top of `tests/test_coupon_reconciliation.py` — do not weaken the assertions** | checkout workstream | `tests/test_coupon_reconciliation.py::test_the_wix_order_total_equals_the_razorpay_charged_total` |
| **SEAM-C3** | Call `coupon_store.commit_redemption(table, *, code, cart_id, order_id, customer_id)` **once**, after capture is verified | `finalization.accept_paid` (`finalization.py:42`), after `_stage(…, 'INTERNAL_ORDER_CREATED')` at `:76`. **That function is untracked and has zero callers**, so the seam is any point that runs once after `order_keys` mints an `orderId` | finalization owner | — · **Pinned by:** `commit_redemption` is idempotent on `(code, order_id)` and returns `{"committed": False}` on replay, asserted in `tests/test_coupon_store.py`. There is no call site to assert against yet |
| **SEAM-C3b** | ✅ **LANDED** — see §3 | `scripts/provision_checkout.py` | **this work** | marks removed; tests 52 / 52a / 52b now pass |
| **SEAM-C4** | Release the hold on cart abandonment and on definite payment failure: `coupon_store.release(table, code=…, cart_id=…)` | the retry/expiry path around `payment_attempt.RETRYABLE_STATES` | checkout workstream | — · **Pinned by:** `release` is safe when no hold exists (the condition tolerates absence) and refuses only when another live cart holds it — `tests/test_coupon_store.py::test_another_cart_cannot_release_a_live_hold` |
| **SEAM-C6** | Add `COUPONS_TABLE` for `wecare-coupons` | `config/lambda-env-manifest.json` (**do-not-touch**; currently holds neither new table) | manifest owner | — · **Pinned by:** nothing, deliberately. The handler falls back to `coupon_store.DEFAULT_TABLE_NAME`, so it works without the manifest entry; the manifest should still say so |
| **SEAM-C7** | Release the hold when `_create` refuses the checkout — the `DELIVERY_DETAILS_REQUIRED` / `ITEMS_UNAVAILABLE` / `QUANTITY_REDUCED` / `CART_RECONCILIATION_REQUIRED` / `CART_NOT_PAYABLE` / `AMOUNT_NOT_SETTLED` early returns, each of which returns **before** a reference is minted | `amplify/functions/ecommerce/checkout/handler.py::_create` (do-not-touch) | checkout workstream | — · **Pinned by:** same as SEAM-C4. The file is **clean** in git; it is a seam because it is assigned to another session, not because of its git state |

**SEAM-C5 is deleted, not open.** It claimed `compute_quote` has no production caller; the caller
exists at `checkout/handler.py::_v2_snapshot` → `purchase_intent.build_intent`.

### Gift cards

| Seam | What the producer must do | Exact anchor | Owner | `xfail(strict=True)` holding its place |
|---|---|---|---|---|
| **SEAM-G1** | Narrow the partial-payment refusal to `memberships` + `subscriptionCharges`; **permit `giftCards`**; replace the `payNow == totalAfterGiftCards == total` equality with the §4.2 identities, treating an absent `requiresPaymentAfterGiftCard` as `False`. **Do not open the other two rails.** | `cart_v2.py:515` — the `if any(payment.get(key) for key in ("giftCards", "memberships", "subscriptionCharges"))` check; `cart_v2.py:517` — the `for field in ("payNow", "totalAfterGiftCards")` loop | cart_v2 owner | `tests/test_gift_card_amounts_and_gst.py::test_the_convenience_fee_is_computed_on_the_full_collection_total` **and** `::test_only_one_gift_card_is_accepted` |
| **SEAM-G2** | Add `add_gift_card` / `remove_gift_card`: `{"giftCard": {"code": …, "redeemAmount": {"amount": Money.to_wix()}}}` and `{"giftCardId": …}` on removal. The adapter has neither today | `cart_v2.CartV2` | cart_v2 owner | — · **Pinned by:** `tests/test_gift_card_amounts_and_gst.py` drives the arithmetic through a spy adapter, so the identities are asserted without the methods existing |
| **SEAM-G3** | Surface `coupons[0].id` **and** `giftCards[0].id` on the payable projection — both removals require the id | `cart_v2.CartV2.calculate`'s payable projection | cart_v2 owner | — · same basis as SEAM-C1b |
| **SEAM-G4** | Take the hold **after** `attempt_id` is minted and **before** the attempt is stored, then write `GC_HELD` through `advance()`. Call: `gift_card_store.hold(table, code_hash=…, attempt_id=…, amount_paise=…, ttl_seconds=900, clock=…)`, then `gift_card_settlement.advance(attempts, attempt_id=…, stage=GC_HELD, giftCardRequiredPaise=…, giftCardCodeHash=…)` | `checkout/handler.py::_create`, between `attempt_id = payment_attempt.new_payment_attempt_id()` (**`:496`**) and `_attempts_table().put_item`; the split goes in at `amount_paise = snapshot.quote.total_payable_paise` (**`:411`**), and `order_keys.allocate_payment_reference` is at `:512` | checkout workstream | — · **Pinned by:** `hold` raises `GiftCardHeldByAnotherPurchase` (409 `HELD_BY_ANOTHER_PURCHASE`), `InsufficientFunds` (428) or `GiftCardDisabled`/`GiftCardExpired` (428), and re-taking your own hold is idempotent — all asserted in `tests/test_gift_card_store.py` |
| **SEAM-G5** | After capture is verified: `gift_card_store.redeem(table, code_hash=…, attempt_id=…, amount_paise=…, source='OURS')`, then `advance(…, stage=GC_REDEEMED, giftCardRedeemedPaise=…, giftCardTransactionId=outcome['transactionId'])`. **Gate order completion on `gift_card_settlement.is_fully_settled(attempt)`, never on the Razorpay leg alone.** `redeem` returns `{'committed', 'transactionId', 'remainingBalancePaise', 'paymentAttemptId', 'amountPaise', 'source'}`; `committed` is `False` on a replay, with the **original** id | `finalization.accept_paid`, between `record_paid` (`:16`) and `_stage(…, 'INTERNAL_ORDER_CREATED')` (`:76`). Untracked, zero callers | finalization owner | — · **Pinned by:** the whole of `tests/test_gift_card_two_leg_finalization.py`, including `test_a_second_redeem_for_the_same_payment_attempt_does_not_move_the_balance` |
| **SEAM-G6** | The Wix order payload carries the gift card as a **tender record** and the fee as `additionalFees[]`, so `Money.from_wix(order["priceSummary"]["total"]["amount"]).paise == quote.total_payable_paise == verifiedCapturedPaise + giftCardRedeemedPaise` — **the verified figures**. This is the *same single invariant* as the coupon document's §2.3, with the gift-card term zero when no card is applied | the builder of `attempt['wixOrderPayload']` — the same producer as SEAM-C2 | checkout workstream | shares SEAM-C2's mark: `tests/test_coupon_reconciliation.py::test_the_wix_order_total_equals_the_razorpay_charged_total` |
| **SEAM-G7(a)** | `record_external_payment` must receive **`verifiedCapturedPaise`**, not `attempt['amountPaise']` | `finalization.py:89-91` — `wix_writeback.record_external_payment(keys, wix_ecom._request, provider_transaction_id=provider_id, amount_paise=int(attempt['amountPaise']))` | wix_writeback / finalization owner | `tests/test_gift_cards_iam_and_table.py::test_no_recorded_payment_exceeds_the_verified_capture_for_its_transaction_id` |
| **SEAM-G7(b)** | **Three edits — see §5.4.** `WIX_GIFT_CARD_TENDER`, adding it to `KNOWN_EFFECTS`, and a `record_gift_card_tender` **sibling** of `record_external_payment` | `side_effect_guard.py:74` (`KNOWN_EFFECTS`, a 5-member `frozenset` validated in `claim()` at `:101`); `wix_writeback.py:253-259` | side_effect_guard / wix_writeback owner | `tests/test_gift_cards_iam_and_table.py::test_the_gift_card_tender_claims_a_different_effect_key_from_the_razorpay_payment` |
| **SEAM-G8** | Insert the §4.1 split at `amount_paise = snapshot.quote.total_payable_paise`, keeping `attempt["amountPaise"]` the **full payable** and storing the gateway figure as `razorpayChargedPaise`. Four numbered steps in the design's §8.2 | `checkout/handler.py::_create`, `:411` | checkout workstream | — · **Pinned by:** `tests/test_gift_card_amounts_and_gst.py`'s split and reconciliation assertions, which run against the store rather than the handler |
| **SEAM-G9** | ✅ **LANDED** — see §3 | `scripts/provision_checkout.py` | **this work** | mark removed; test 107 passes. Test 107a was never marked (§6) |
| **SEAM-G10** | Write `GCWIXORDER#<wixOrderId> → paymentAttemptId` when `wixOrderId` first exists: `gift_card_store.bind_wix_order(table, wix_order_id=…, attempt_id=…)`. It **reports** a second binding (`{'bound': False, …}`) rather than overwriting the first | `finalization.py:88` — the `_stage(…, 'WIX_ORDER_CREATED', wixOrderId=wix['wixOrderId'])` call | finalization owner | — · **Pinned by:** `tests/test_gift_card_store.py`'s pointer-row tests, including the second-binding refusal |
| **SEAM-G11** | Add `GIFT_CARDS_TABLE`, `WIX_GIFTCARD_SPI_SECRET`, `WIX_GIFTCARD_APP_ID`, `WIX_GIFTCARD_INSTANCE_ID` | `config/lambda-env-manifest.json` (do-not-touch) | manifest owner | — · **Pinned by:** nothing, deliberately. Both handlers fall back to `gift_card_store.DEFAULT_TABLE_NAME` / `SECRET_ID`, and `app_id` / `instance_id` are read from the **secret** rather than the environment, so only the table and secret names are manifest concerns |
| **SEAM-G12** | Update **three** existing cart tests. `test_the_adapter_has_no_gift_card_methods_at_all` (`:215`) → **deleted** (it states the old decision); `test_a_gift_card_on_the_cart_is_refused_rather_than_part_paid` (`:228`) → **inverted**; `test_a_gift_card_that_covers_the_whole_total_is_still_refused` (`:242`) → **re-fixtured, already passing**. `test_memberships_and_subscription_charges_are_refused_on_the_same_grounds` (`:262`) must **keep passing unchanged** | `tests/test_wix_cart_v2_coupons_and_stock.py` | cart_v2 owner | — · **Pinned by:** `tests/test_gift_card_amounts_and_gst.py::test_memberships_and_subscription_charges_are_still_refused`, deliberately **unmarked**, which is the detector for SEAM-G1 opening all three rails instead of one |
| **SEAM-G13** | `record_paid` writes **`verifiedCapturedPaise`** beside `verifiedProviderPaymentId` in the **same** conditional `UpdateExpression`, and `outcome` gains the field. **See §5.1 for the producer and the refusal.** | `finalization.py:16` (`def record_paid(attempts, attempt, provider_payment_id)`), `:21` (the `UpdateExpression` already carrying `verifiedProviderPaymentId`), `:23` (its `ConditionExpression`); and `accept_paid`'s `outcome` dict at `:42`/`:50` | finalization owner | — · **Pinned by:** `is_fully_settled` reads it through `RAZORPAY_VERIFIED_PAISE_ATTR` and **returns `False`, never raises**, when it is absent (`tests/test_gift_card_two_leg_finalization.py`, test 83a). **This is the seam the settlement decision cannot work without**: until it lands, every gift-card order reads as not-settled |
| **SEAM-G14** | Apply the split table — **eight rows, not five. See §5.2.** | `website_checkout.py::prepare_checkout` and `_bind_and_ready`; `:193`, `:199` (the `attempt_id` mint), `:203`, `:231`, `:265`, `:281`, `:288-289`; plus `_browser_options` (`:128`, value reaching `options["amountPaise"]` at `:145`), `_recover_ambiguous_create` (`:328`, called at `:236`/`:239`, forwards at `:344`) and `_ready_from_binding` (`:295`, reads the binding at `:302`) | website-checkout owner | `tests/test_gift_cards_iam_and_table.py::test_the_website_checkout_split_binds_the_charged_amount_and_the_payable_separately` |

---

## 5. The four statements a later session will need and cannot re-derive cheaply

### 5.1 SEAM-G13 — who produces `verifiedCapturedPaise` (MEDIUM-1)

Revision 3 added a `captured_paise` parameter to `finalization.record_paid` and **named no producer**.
`record_paid`'s only caller is `accept_paid(*, attempts, orders, keys, attempt, outcome)`, and no
captured-amount field on `outcome` existed anywhere. So the entire HIGH-3 resolution — the verified
figure both legs close against — had no source at the point it enters the row.

> **`outcome` gains `verifiedCapturedPaise`, written by the caller from the SAME `razorpay_verify`
> readback that produced `outcome['providerPaymentId']`.** Concretely: `website_checkout.py:430`'s
> `amount_paise` on the website path, or the webhook's `provider_paise`. The two are **one fact read at
> one instant**, which is why they travel together and why neither is re-derived later.
>
> **`record_paid` REFUSES a call carrying a provider id without an amount.** Not a default, not a zero,
> not a `None` written through — a raise. The failure being closed is specific: a caller that passes the
> id and omits the amount writes `verifiedProviderPaymentId`, leaves `verifiedCapturedPaise` absent, and
> `is_fully_settled` then returns `False` **forever** on a genuinely paid order. A silently stuck order
> is worse than a loud one, so it fails at the write.

Read both through `gift_card_settlement.RAZORPAY_EVIDENCE_ATTR` and `RAZORPAY_VERIFIED_PAISE_ATTR`, so
a rename decided in another session is **one line**. A parallel design
(`payment-integrity-closure-2026-10-01`) is deciding whether `verifiedProviderPaymentId` keeps its name,
which is why the indirection exists.

### 5.2 SEAM-G14 — the three `website_checkout.py` consumers revision 3 did not list (MEDIUM-2)

`amount_paise` appears **18 times** in `website_checkout.py`; the split table named **five**.

| Consumer | Carries | Why |
|---|---|---|
| `_browser_options(amount_paise=…)` — defined `:128`, called `:288-289` | **`payNowPaise`** | It becomes `options["amountPaise"]` at `:145` — **the figure Razorpay Standard Checkout presents to the browser.** The payable here shows the customer a price they are not being charged |
| `_recover_ambiguous_create(amount_paise=…)` — defined `:328`, called `:236`/`:239`, forwards `:344` | **`payNowPaise`** | It is the recovery path for a `create_order` whose outcome is unknown: it re-finds the order by receipt and re-binds it. Re-binding at the payable writes a binding `:434` will refuse, so **the one path that exists to rescue a payment would break it** |
| `_ready_from_binding` — `:295`, reads `binding["amountPaise"]` at `:302` | **NOTHING — NEEDS NO CHANGE** | It reads the amount back **off the binding**, which the existing table already sets to `payNowPaise`. Changing it would either double-apply the split or reintroduce the payable on the resume path. **The correct edit is no edit, and saying so is the point** — an unlisted consumer reads as an oversight |

Both implementation strategies fail without this list, in **opposite** directions: reassigning the local
`amount_paise` satisfies the five original rows and **silently changes these three** (including
`payment_attempt.build` at `:281`, which must stay the payable or `is_fully_settled` loses its closure);
adding a second variable leaves thirteen occurrences to decide unaided.

**Test 112 is to be extended with `options["amountPaise"] == payNowPaise`.** See §9 — that extension is
not yet in the test.

### 5.3 There are FOUR attempt producers, and the fourth is out of scope (MEDIUM-3)

Revision 3 said **three** and labelled it measured. Derived from every `payment_attempt.build(` call
site:

| # | Producer | `build(` at | Status |
|---|---|---|---|
| 1 | `checkout/handler.py::_create` | **`:519`** | in scope — SEAM-G8 |
| 2 | `website_checkout.py::prepare_checkout` | **`:279`** (the `amount_paise=` kwarg at `:281`) | in scope — SEAM-G14 |
| 3 | `initiation.py::reserve` | **`:63`** | **out of scope** — untracked, no caller in `amplify/`, consumes a pre-computed `snapshot['amountPaise']` rather than a `CheckoutQuote`, gated on `CHECKOUT_INITIATION_ENABLED` |
| 4 | `blog_contribution.py::prepare_contribution` (function at `:213`) | **`:355`** | **out of scope** — new §8.5 of the gift-card design |

> **Why #4 is out of scope, decisively: a contribution flow has no Wix cart, so there is no
> `wixCollectionPaise` to cap a redemption against.** `redeem_cap` is
> `min(balance_paise, wix_collection_paise - 100)`, and HIGH-4 exists precisely to stop that cap being
> taken against anything other than the Wix collection total. A contribution has a contribution amount
> and **no Wix supply line at all**. Capping against the contribution amount would invent a rule for a
> flow nobody designed gift cards into — and **a gift card is a liability**, so an undefined cap spends
> real money on an unspecified path. Secondarily: §4.2's six reconciliation identities are all stated
> against a Wix cart summary, so with no summary the refusal that protects every other path would not
> run. And whether a contribution is a purchase at all is an owner question.
>
> **Why the off-by-one is not a nit.** Revision 3's single largest finding was a **missed producer** —
> the website path, the active architecture. An enumeration still short by one is the same defect one
> instance smaller, presented with the same word: "measured". Producer #4's own docstring calls itself a
> **sibling of `website_checkout`**, which is the strongest available hint that an enumeration stopping
> at three was not an enumeration.

A gift card cannot reach producer #4 today, because nothing in the contribution path reads a gift-card
code. **Test 113b is what keeps that true, and it is not yet written** — §9.

### 5.4 SEAM-G7(b) needs THREE edits, not one

```python
# side_effect_guard.py  (currently line 74)
WIX_GIFT_CARD_TENDER = "wix_gift_card_tender"                      # 1. the constant
KNOWN_EFFECTS = frozenset({WIX_ORDER, WIX_PAYMENT, WIX_CART_COMPLETED, RECEIPT, CONFIRMATION,
                           WIX_GIFT_CARD_TENDER})                   # 2. and it must go IN here
```

**The constant alone is not enough.** `KNOWN_EFFECTS` is a `frozenset` validated inside `claim()` at
`side_effect_guard.py:101` — an effect absent from it makes the claim **refuse**. The precedent is the
file's own comment on `WIX_CART_COMPLETED`: *"Its own effect rather than folded into `WIX_ORDER` because
it is a separate remote call"* — exactly this situation, a second `add-payment` call with a different
tender.

**3. `record_gift_card_tender`, a SIBLING of `record_external_payment` — not a parameter on it.**

Why a sibling: `record_external_payment` hard-codes
`"paymentMethodName": {"buyerLanguageName": "Razorpay via WhatsApp"}`, and its
`providerTransactionId` / `offlinePayment: False` shape **describes a gateway payment**. A gift card is
not one. Bending one function to mean both is how `paymentMethodName` came to be hard-coded in the first
place.

And a reminder of why a second record cannot simply reuse the existing key: `wix_writeback.py:253-259`
holds one `WIX_PAYMENT` claim per `order_id`, bound to four fields, and a later call presenting a
**different** binding **raises** `WixWritebackPending`. A gift-card tender under `WIX_PAYMENT` would be
read as a contradicting retry of the Razorpay payment and refused.

`test_the_existing_five_known_effects_are_unchanged` is the unconditional companion to the xfail, so the
seam must **add** an effect rather than repurpose one.

---

## 6. The `xfail(strict=True)` inventory — exactly 7, and why each

Every one has a **do-not-touch file** as its producer, so none of them is clearable by editing a gate.
`strict=True` throughout: each converts from "pending" to "passing" the moment its producer lands, **and
fails loudly if somebody satisfies it by lowering the bar**.

| # | Test | Seam | Producer (all do-not-touch) |
|---|---|---|---|
| 1 | `test_coupon_reconciliation.py::test_add_coupon_sends_the_v2_nested_coupon_body` | SEAM-C1 | `cart_v2.py:333` |
| 2 | `test_coupon_reconciliation.py::test_the_wix_order_total_equals_the_razorpay_charged_total` | SEAM-C2 / G6 | the Wix order payload producer |
| 3 | `test_gift_card_amounts_and_gst.py::test_the_convenience_fee_is_computed_on_the_full_collection_total` | SEAM-G1 | `cart_v2.calculate` refuses `giftCards` |
| 4 | `test_gift_card_amounts_and_gst.py::test_only_one_gift_card_is_accepted` | SEAM-G1 | same |
| 5 | `test_gift_cards_iam_and_table.py::test_the_website_checkout_split_binds_the_charged_amount_and_the_payable_separately` | SEAM-G14 | `website_checkout.py` |
| 6 | `test_gift_cards_iam_and_table.py::test_no_recorded_payment_exceeds_the_verified_capture_for_its_transaction_id` | SEAM-G7(a) | `finalization.py` |
| 7 | `test_gift_cards_iam_and_table.py::test_the_gift_card_tender_claims_a_different_effect_key_from_the_razorpay_payment` | SEAM-G7(b) | `side_effect_guard.KNOWN_EFFECTS` |

**This equals DECISION 8's list exactly**, once the five marks item 25 removed are taken out and the
four tests DECISION 8 named that must **not** be marked are accounted for.

### Every seam-dependent test is SPLIT, so nothing is merely deferred

Each xfail above has an unconditional companion asserting the part that is true today:

| xfail | Unconditional companion |
|---|---|
| 1 | `test_add_coupon_is_the_method_that_makes_the_wix_total_net` — asserts the **endpoint** and the option-(a) claim |
| 2 | `test_the_order_total_identity_is_arithmetically_reachable_today` — proves the identity is already reachable, so SEAM-C2 only has to **transport** the fee |
| 3 | `test_the_fee_basis_is_the_full_collection_and_the_worked_example_is_exact` — the arithmetic (2500 / 450, with the wrong 1574 / 283 computed explicitly beside it) |
| 4 | `test_a_second_gift_card_is_refused_by_our_own_reconciliation` — the refusal half, in our own code, before anything is charged |
| 7 | `test_the_existing_five_known_effects_are_unchanged` — so the seam must add an effect, not repurpose one |

### Four tests DECISION 8 named that are deliberately NOT marked

Marking any of these `strict=True` would **xpass immediately** — a hard failure under this build's own
"0 xpassed" criterion — and, worse, would switch off the only assertion that fires when the hazard
arrives. The reason is written into each test's docstring.

| Test | Why unmarked |
|---|---|
| `test_coupons_iam_and_table.py::test_the_iam_simulation_covers_every_action_the_policy_grants` (52a) | A **subset relation** that held vacuously. It is the detector for a **half-done** SEAM-C3b — a grant added without extending the two hard-coded lists. It passed before the edit and passes after, now **non-vacuously**, which is the first time it has measured anything |
| `test_gift_cards_iam_and_table.py::test_the_gift_card_grant_and_its_simulation_cannot_drift_apart` (107a) | The gift-card-specific **implication**: *if* the policy names the `GiftCardsTable` *then* that ARN is in the simulated `tables` list and `DeleteItem` is in `_SIMULATED_ACTIONS`. Written as an implication rather than duplicating the coupon suite's general subset test, so no file another session owns had to be edited |
| `test_gift_card_amounts_and_gst.py::test_memberships_and_subscription_charges_are_still_refused` (100) | The design itself says the equivalent `cart_v2` test *"must KEEP PASSING unchanged… it is the test that proves SEAM-G1 narrowed the gate rather than opening it"*. Marking it removes the detector for SEAM-G1 opening all three rails |
| `test_gift_cards_iam_and_table.py::test_the_initiation_reserve_path_writes_no_gift_card_attribute` (113) | §8.3 declares that producer out of scope; the test exists so the omission stays **deliberate and visible**. There is nothing pending about it — it is a **gate**. It `skip`s if `initiation.py` is absent, because that module is untracked |

### Item 25 removed FOUR marks, not five

Tests 52 and 52b (coupons) and 107 (gift cards) had marks, now removed and passing. **52a and 107a
never carried one**, for the reason above. A **fifth** removal item 25 does not list was also required:
`tests/test_coupon_logging_and_vocabulary.py::test_the_new_handlers_are_in_the_raw_scan_list` xpassed the
moment item 22 landed — its producer was item 22's own edit, so removing the mark completes item 22
rather than changing scope. While removing it, the assertion was extended from the coupons tuple alone to
**all three** tuples, because nothing anywhere else pinned the two gift-card entries and the test's own
name says "handlers" plural — the SPI handler matters most, being the one new file touching money on an
externally-triggered path.

---

## 7. Finding audit — all 20, with resolution and test

`design-review.json`: 6 HIGH / 8 MEDIUM / 6 NIT, reviewed 2026-10-02. **Revision-prefixed `R4-` per
NIT-6**; the original spelling is kept so an old cross-reference resolves.

| id | Resolution | Applied in | Named test in the owned suite |
|---|---|---|---|
| **HIGH-1** (R4-H1) | DECISION 1 restated **"(a) for the arithmetic, (b) for transport"**; the discount is relayed as `appliedDiscounts[]`; SEAM-C2 widened to both terms | `coupons-20261001.md` §2, §2.3, §8 | `test_coupon_reconciliation.py::test_the_wix_order_total_equals_the_razorpay_charged_total` (test 48 — asserts `appliedDiscounts[0].coupon.amount.amount` **byte-identical** to the cart discount) |
| **HIGH-2** (R4-H2) | Identity block **split by direction**; `priceSummary` is documented `readOnly`, so total and subtotal are asserted on the **response**; the "unverified" note replaced by the measurement | `coupons-20261001.md` §2.3 | same test 48 — also pins `returned.priceSummary.subtotal == cart.priceSummary.subtotal` |
| **HIGH-3** (R4-H3) | **DECISION 5** — the hold existence fact moves onto the row whose key is known; `hold()` is one conditional `UpdateItem`; `GCHOLD#`/`COUPONHOLD#` become audit-only; `GCID#` added | `coupons` §4.1-§4.3; `gift-cards` §6.3, §6.4, §7.4 | `test_coupon_store.py::test_every_dynamodb_access_is_an_exact_key_operation_or_the_status_index_query` · `::test_hold_is_one_conditional_update_with_no_preceding_read` · `test_gift_card_store.py::test_every_dynamodb_access_is_an_exact_key_operation_or_the_status_index_query` · `::test_the_hold_is_one_conditional_update_with_no_preceding_read` |
| **HIGH-4** (R4-H4) | **DECISION 10** — `redeem_cap` defined **once** in `gift_card_store`, capped against the Wix collection total; §7.5's `payable - 100` replaced by a reference | `gift-cards` §4.1, §7.5 | `test_gift_card_amounts_and_gst.py::test_redeem_cap_is_defined_exactly_once_and_both_callers_use_it` · `::test_a_redeem_at_the_cap_is_accepted` · `::test_a_redeem_above_the_cap_is_refused_not_clamped` |
| **HIGH-5** (R4-H5) | **Three parts**, all landed: the grant, the simulation lists, and `_EXPECTED_DENY` + the re-keyed verdict loop | `scripts/provision_checkout.py`; `coupons` §5.2.1 | `test_provision_checkout_contract.py::test_the_verdict_is_keyed_on_the_action_and_the_resource` · `::test_a_correctly_provisioned_role_passes_with_delete_item_split_two_ways` · `::test_delete_item_becoming_allowed_on_an_evidence_table_is_reported` · `test_coupons_iam_and_table.py` 52/52a/52b · `test_gift_cards_iam_and_table.py` 107/107a |
| **HIGH-6** (R4-H6) | **DECISION 9** — `GCTXN#` gains `paymentAttemptId`; `GCTXNID#` → `{codeHash, paymentAttemptId}`; `referenceId` demoted to correlation only | `gift-cards` §6.3, §6.5 | `test_gift_card_store.py::test_a_void_carrying_only_a_transaction_id_resolves_both_the_card_and_the_attempt` · `::test_a_void_resolves_the_card_from_the_transaction_id_alone` |
| **MEDIUM-1** (R4-M1) | `outcome` gains `verifiedCapturedPaise` from the same readback as `providerPaymentId`; `record_paid` refuses a provider id without an amount | `gift-cards` SEAM-G13; **§5.1 of this file** | `test_gift_card_two_leg_finalization.py` tests 83 / 83a / 83c — all read through `RAZORPAY_VERIFIED_PAISE_ATTR`; 83a asserts `False` rather than a raise when it is absent |
| **MEDIUM-2** (R4-M2) | Three rows added to the split table, including `_ready_from_binding` as **NEEDS NO CHANGE** | `gift-cards` §8.1, SEAM-G14; **§5.2 of this file** | `test_gift_cards_iam_and_table.py::test_the_website_checkout_split_binds_the_charged_amount_and_the_payable_separately` (xfail) — **the `options["amountPaise"]` clause is not yet in it; see §9** |
| **MEDIUM-3** (R4-M3) | Corrected to **FOUR** producers from the call sites; new §8.5 declares `blog_contribution` out of scope | `gift-cards` §8, §8.5; **§5.3 of this file** | `test_gift_cards_iam_and_table.py::test_the_initiation_reserve_path_writes_no_gift_card_attribute` covers producer #3. **Test 113b for producer #4 is not yet written; see §9** |
| **MEDIUM-4** (R4-M4) | The `Content-Type` rejection **dropped**; the three-segment check is the discriminator; the header question moved to owner item 12.1.4; the citation corrected to the install callback | `gift-cards` §5, §5.1, §7.4, §7.5, §12.1.4 | `test_gift_card_spi_auth.py::test_a_body_that_is_not_three_segments_is_refused_whatever_the_content_type` (parametrised over five header values) · `::test_the_verifier_never_reads_the_content_type_header_at_all` |
| **MEDIUM-5** (R4-M5) | Hold and release routes **removed**; §7.2 is **five** routes | `gift-cards` §7.2; `ecommerce/gift-cards/handler.py` | `test_gift_card_store.py::test_no_route_accepts_a_code_in_a_path_or_query` — asserts the exact five-route set, `len(routes) == 5`, and that neither `POST /gift-cards/hold` nor `/release` is present |
| **MEDIUM-6** (R4-M6) | `cart_id` added to `commit_redemption`'s signature | `coupons` §5.2; `coupon_store.py` | `test_coupon_store.py::test_release_clears_the_hold_and_deletes_the_audit_row` · `::test_another_cart_cannot_release_a_live_hold` — plus every `commit_redemption` call in that file passes `cart_id` |
| **MEDIUM-7** (R4-M7) | Four test names renamed off the stale `reference` vocabulary; 80's old form was **unsatisfiable**, not merely stale | `gift-cards` §9.1 | the renamed tests themselves: `test_gift_card_store.py::test_a_second_redeem_for_the_same_payment_attempt_returns_the_same_transaction_id` · `::…_does_not_move_the_balance` · `::test_two_different_payment_attempts_each_deduct_once` · `test_gift_card_two_leg_finalization.py::test_the_hold_is_taken_after_the_attempt_id_is_minted_and_before_the_gateway` |
| **MEDIUM-8** (R4-M8) | **All three** price fields sent: `price` and `priceAfterTax` = fee + GST, `priceBeforeTax` = fee | `coupons` §2.3; `gift-cards` SEAM-G6 | test 48's `totalAdditionalFees` assertion (`priceBeforeTax` is referenced in `test_coupon_reconciliation.py`) |
| **NIT-1** (R4-N1) | The commit id is replaced by the **date**; **no commit id is reproduced in either promoted document** | both, §3.1 / §11 and the §12 / §13 headers | — (documentation only; no test asserts prose) |
| **NIT-2** (R4-N2) | All six citations corrected and each correction annotated; the webhook comparison identified as the **partner wallet top-up** path | `coupons` §5.2.1, §8, §12.1; `gift-cards` §3.2, §8.1, §10.4 | — (documentation only). The anchors themselves are re-measured in §3 and §4 of this file |
| **NIT-3** (R4-N3) | Registry entry gains its route script; the script is **renamed** to `provision_gift_card_routes.py` and the new name used throughout | `coupons` §8, §11; `gift-cards` §12.3; `scripts/deploy_all_lambdas.py` | **spec test 65, written as two parametrised tests** over all three names: `test_coupons_routes_and_registry.py::test_the_new_function_is_deployable_at_all` and `::test_the_new_function_declares_what_must_create_it_first` — the second asserts `provisioned_by` is non-empty **and that every `.py` it names exists**, which is what catches the stale `provision_gift_card_spi_routes.py`. Plus `test_gift_cards_iam_and_table.py::test_the_route_provisioner_creates_eight_routes_across_two_integrations` |
| **NIT-4** (R4-N4) | The `maxItems 1` / `maxItems 5` asymmetry recorded beside the quotation; enforcing one stays correct, on our own grounds | `coupons` §1.2 | `test_gift_card_amounts_and_gst.py::test_a_second_gift_card_is_refused_by_our_own_reconciliation` (unconditional) · `::test_only_one_gift_card_is_accepted` (xfail, SEAM-G1) |
| **NIT-5** (R4-N5) | No `COUPONUSE#` condition when `limitPerCustomer` is absent, **and the row is still incremented for audit** | `coupons` §4.3 | `test_coupon_store.py::test_a_coupon_with_no_per_customer_limit_still_counts_the_use` |
| **NIT-6** (R4-N6) | Every finding id revision-prefixed (`R2-`, `R3-`, `R4-`), original spelling in brackets, scheme stated in a table | both, §12 / §13 | — (documentation only) |

**Four findings have no test, and all four are documentation-only** (NIT-1, NIT-2, NIT-6, and the prose
half of NIT-3): they concern what a document *says*, not what the code *does*. Asserting prose with a
test would pin the wording rather than the behaviour.

---

## 8. Owner actions — consolidated, both documents

Nothing below was done, and none of it can be done by an agent.

### 8.1 Blocking — the gift-card SPI cannot answer anything until these land

| # | Action | Why it blocks |
|---|---|---|
| 1 | **Register the Gift Cards Provider extension** in the Wix Studio workspace and set `deploymentUri` to `https://zllr9lrg7j.execute-api.us-east-1.amazonaws.com/prod/wix-giftcards/` — the **base** URI; Wix appends `v1/balance`, `v1/redeem`, `v1/void` | Until this, `Add Gift Card` cannot value a card and no gift card can affect any total. The route must be **reachable before** Wix's save-time validation runs |
| 2 | **Populate `wecare/wix/giftcard-spi`** with `public_key`, `app_id`, `instance_id` and a freshly generated `code_pepper` | Until this, the verifier refuses **every** request — the correct fail-closed posture for an unconfigured verifier. Values must be entered by a mechanism that never puts them on a command line (`secret-handling.md`; the 2026-09-19 incident is why) |
| 3 | **Read a real token's header and record (a) its `alg` and (b) the request's `Content-Type`** | (a) narrows the three-member allowlist to one; (b) is the MEDIUM-4 question — the check was dropped because the allowlist came from an example of a different endpoint |
| 4 | **Decide the SPI error-response BODY with Wix** | Wix publishes **none** — the OpenAPI `responses` object declares only `200` on all three methods. `{name, applicationCode}` is our minimal reasoned choice and is labelled as such |
| 5 | **Confirm the site has the app installed** | There is no way to block installation on sites lacking it, so installation must be verified rather than assumed |
| 6 | **Confirm the Wix API key's scope includes `Manage Coupons`** | `Create`/`Get`/`Update Coupon` all need `COUPONS.MANAGE`; the current key's scopes are recorded nowhere in this repo. A key without it leaves every coupon `PENDING_WIX` — fails closed |

### 8.2 ⚠️ POINTWISE CONFIRMATION — the customer-managed KMS key (DECISION 6)

`maintenance-reporting.md` lists **KMS create/delete** among the operations requiring **per-item**
confirmation, so this is **not** covered by the standing grant and must not be bundled with the rest of
the deploy.

| | |
|---|---|
| **What** | Create a customer-managed KMS key in `us-east-1` plus the alias **`alias/wecare-gift-cards`**, and create `stack-wecare-digital-GiftCardsTable` with `SSESpecification={"Enabled": True, "SSEType": "KMS", "KMSMasterKeyId": "alias/wecare-gift-cards"}` |
| **Also grants** | `kms:Decrypt` + `kms:GenerateDataKey` on the key to **both** gift-card roles, **conditioned on `kms:ViaService = dynamodb.us-east-1.amazonaws.com`** — so DynamoDB can decrypt rows on their behalf and neither function can use the key for anything else |
| **Cost** | A standing monthly KMS key charge. That is part of what is being approved |
| **Why it cannot be deferred** | A DynamoDB table **cannot be moved from the AWS-owned default key to a CMK after creation** without a restore, and this table is the only place a customer's gift-card balance of record exists. `provision_gift_cards_table.py` therefore **refuses to create the table before the alias resolves** |
| **Why it is new ground** | Measured across `scripts/`: **no `SSESpecification` on any `provision_*.py` and no `CreateKey` call anywhere.** There is no precedent to inherit, which is why it is its own item rather than a line in the deploy block |
| **Reversibility** | Creating a key is reversible only as a **scheduled deletion** with a mandatory waiting period. Treat it as effectively one-way |
| **State** | Behind `--apply`. **Not run.** Asserted offline by a test over the provisioner's literal and both role policies' `kms:ViaService` condition |

### 8.3 Decisions that gate first real use

| # | Decision | Current design answer |
|---|---|---|
| 1 | Coupon catalogue scope — site-wide `stores`, or per `product` / `collection` | the Lambda accepts all three |
| 2 | Accept or reject the **whole-rupee restriction** on coupon money | a ₹99.50-off coupon is **refused** this release. Lifting it needs either a live probe confirming Wix accepts a non-integer JSON `number`, or a `Decimal`-aware serialiser in a module we own |
| 3 | The `WIX_CODE_CONFLICT` policy — adopt the existing Wix coupon, or rename ours | reachable **only** from a coupon created in the Wix dashboard outside this system. If dashboard creation is disallowed, the state never occurs |
| 4 | **Gift-card expiry policy** | optional; default **no expiry** (the conservative choice under Indian prepaid-voucher law). A non-null default is an owner decision |
| 5 | May a gift card cover **100%** of the payable | **refused** — such an order has no Razorpay readback and therefore no authoritative verification |
| 6 | **Refuse** vs round-down when a split would leave 1-99 paise on the Razorpay leg | **refuse.** Rounding changes what the customer asked for by up to 99 paise without telling them |
| 7 | May a gift card fund the **convenience fee** | **no.** The card funds the **supply only**; the fee and its GST are always on the Razorpay leg. The customer-visible cost is stated: someone holding a card worth more than the cart cannot spend the surplus on the fee |
| 8 | **PIN policy** | supported and optional. Mandatory is an owner decision |
| 9 | **GST treatment, with the accountant** | a voucher is consideration, so the taxable supply stays at full value. Standard treatment, but it is the assumption the whole fee basis rests on |

### 8.4 Questions the tree cannot answer

| # | Question | What depends on it |
|---|---|---|
| 1 | **Which function finalizes** — `wecare-checkout` or `wecare-razorpay-webhook`? `finalization.accept_paid` has **zero callers** | SEAM-C3, SEAM-C3b's role choice, SEAM-G5, SEAM-G10, SEAM-G13. The landed grant assumes `wecare-checkout-role`; if it is the webhook, the same two-statement shape applies to its role and only the ARN list in test 52 changes. `--apply` has not run, so this is still cheap to redirect |
| 2 | **Which function hosts `website_checkout.prepare_checkout`?** The module is handler-free and nothing in `amplify/functions/` calls it | SEAM-G14, and the IAM grant for the website path's hold. May have the same answer as #1 |
| 3 | **Enable `WIX_CART_V2_ENABLED`** | Nothing in either design reaches production without it: both the coupon fee-basis chain and the entire gift-card split live on the Cart V2 branch of `checkout/handler.py`. The V1 branch prices through `wix_ecom.authoritative_total_paise`, which neither touches |
| 4 | **Resolve SEAM-C1 with the cart_v2 owner** | No coupon can be applied at checkout until it lands |

---

## 9. Open test items — two, both named and specified, both now CLOSED (§9.1)

Neither was a failing test; both were tests **not yet written**, recorded here so the gap was visible
rather than inferred from a missing name. The specification below is kept as written; §9.1 records how
each landed and the one place the specification turned out to be wrong.

| Item | What is missing | Exact specification |
|---|---|---|
| **Test 112's MEDIUM-2 clause** | Test 112 asserts `binding["amountPaise"]`, `attempt["amountPaise"]` and `attempt["razorpayChargedPaise"]`. It does **not** yet assert `options["amountPaise"] == payNowPaise` | Add that clause to `tests/test_gift_cards_iam_and_table.py::test_the_website_checkout_split_binds_the_charged_amount_and_the_payable_separately`. It stays `xfail(strict=True)` against SEAM-G14 — the clause is part of the same pending seam, so it changes nothing about the mark |
| **Test 113b** | `test_the_blog_contribution_path_writes_no_gift_card_attribute` does not exist. Producer #4 (§5.3) is declared out of scope with nothing asserting it stays that way | Add it to `tests/test_gift_cards_iam_and_table.py`, in the shape of test 113: read `blog_contribution.py` and assert none of `giftCardStageRank`, `giftCardRequiredPaise`, `giftCardCodeHash`, `giftCardRedeemedPaise`, `giftCardTransactionId`, `razorpayChargedPaise` appears. **It must be UNMARKED, not `xfail(strict=True)`** — the property holds today, so a strict mark would **xpass immediately** (a hard failure under this build's own criterion) and would switch off the only detector for a gift card later reaching a flow with no `wixCollectionPaise` to cap against. It is a **gate**, exactly like test 113 |

Both belong to `tests/test_gift_cards_iam_and_table.py`, which the gift-card workstream owns. They were
not added here because this step's scope is the three documents, and a test edit outside that scope
would have landed in a docs-only commit.

### 9.1 Both CLOSED by the integration step, 2026-10-02

| Item | Landed as | Mark |
|---|---|---|
| Test 112's MEDIUM-2 clause | Four assertions appended to test 112 | `xfail(strict=True)` against SEAM-G14, unchanged |
| Test 113b | `test_the_blog_contribution_path_writes_no_gift_card_attribute` | **UNMARKED**, passes today, as specified |

File now reports **26 passed / 3 xfailed**, and the whole tree **6784 passed / 7 xfailed / 0 xpassed**.

**The MEDIUM-2 clause is not the one-line string check §9 implied, and the difference is the whole
point of writing it.** `_browser_options` has **two** call sites, and §5.2 lists the second
(`_ready_from_binding`, `:300`) as **NEEDS NO CHANGE** because it reads the amount back off the
binding. A clause asserting "every browser amount comes from the pay-now figure" would therefore
**never be satisfiable**, and because test 112 is `xfail(strict=True)` it would have failed for that
reason forever while reading as a correctly pending seam — a mark that can never clear, which is
precisely the defect DECISION 8's audit exists to catch. It was written and then found by exercising
the clause against both the current source and a patched post-seam source before committing.

What landed instead:

1. The clause is scoped to the function that calls `payment_attempt.build`, and asserts the
   `_browser_options` and `build` amount expressions are **not the same expression**. Today both are
   the single `amount_paise` local, so it fails; §8 mandates `build` keep the payable, so the only
   way to satisfy it is the divergence SEAM-G14 is.
2. It additionally requires the browser argument to name a pay-now figure, so the divergence cannot
   be satisfied by passing some third unrelated expression.
3. `_ready_from_binding` is asserted **separately** to still read its amount off the `binding` —
   MEDIUM-2's "the correct edit is no edit", now pinned rather than merely stated, so the resume path
   cannot acquire the split and double-apply it.

Asserted over the AST rather than as source text, because the string `payNowPaise` could be satisfied
by naming the variable without routing it to the browser. Verified as clearable: against the current
`website_checkout.py` the clause fails on the shared-expression assertion; against the same file with
`amount_paise=pay_now_paise` substituted at the `prepare_checkout` call site, it passes.

---

## 10. Deploy order — unrun, in dependency order

**None of this has been run. Every provisioner defaults to a dry run and requires `--apply`.** The KMS
step needs §8.2's pointwise confirmation first.

```
# ── coupons ───────────────────────────────────────────────────────────────────
python scripts/provision_coupons_table.py      --apply   # table + status-index, PITR on, TTL off
python scripts/provision_coupons_role.py       --apply   # wecare-coupons-role
python scripts/provision_coupons_routes.py     --apply   # the seven routes
python scripts/deploy_all_lambdas.py wecare-coupons
python scripts/provision_live_alias.py         --apply
python scripts/snapstart_publish.py wecare-coupons

# ── gift cards ────────────────────────────────────────────────────────────────
#    STEP 1 NEEDS THE POINTWISE KMS CONFIRMATION (section 8.2). It creates the CMK and
#    the alias FIRST and refuses to create the table before the alias resolves.
python scripts/provision_gift_cards_table.py   --apply
python scripts/provision_gift_cards_roles.py   --apply --alarms
#      creates wecare-gift-cards-role and wecare-wix-giftcard-spi-role
#      attaches arn:aws:lambda:us-east-1:775261844268:layer:cryptography-python312:1
#               to wecare-wix-giftcard-spi          <- VERSION-PINNED, deliberately
#      creates wecare-gift-card-wix-spi-redemption and wecare-gift-card-charge-mismatch
python scripts/provision_gift_card_routes.py   --apply   # EIGHT routes across two integrations
python scripts/deploy_all_lambdas.py wecare-gift-cards wecare-wix-giftcard-spi
python scripts/provision_live_alias.py         --apply
python scripts/snapstart_publish.py wecare-gift-cards wecare-wix-giftcard-spi

# ── then, and only then ───────────────────────────────────────────────────────
#    register the SPI with Wix (section 8.1 item 1) - the route must be reachable first
```

Four ordering constraints, each with a reason rather than a convention:

1. **The `cryptography` layer must be attached BEFORE the code deploy.** `deploy_all_lambdas.py`
   validates every top-level import against the package **plus the function's live layer list** and
   refuses an import it cannot resolve. The SPI handler imports `cryptography`, so a deploy against a
   layer-less function fails the gate — which is the gate working, but only if this order is followed.
2. **The `live` alias must exist before `snapstart_publish.py`.** The publisher discovers its targets
   **by looking for the alias**, so without it the function is simply not seen and the API keeps serving
   nothing. `provision_live_alias.py` is what creates it. `deploy_all_lambdas.py` calls the publisher
   itself at the end, so the explicit `snapstart_publish.py` line is only needed for a hand deploy.
3. **Neither function is live until a version is published and the alias moves** —
   `lambda-snapstart-deploy.md`. Route integrations target `:live`, never `$LATEST`.
4. **The registry edit is a hard prerequisite** for every `deploy_all_lambdas.py` line. ✅ It has landed:
   all three names resolve under `--list` and each carries a non-empty `provisioned_by`.

`provision_checkout.py --apply` is **not** in this list and is a separate decision, because it modifies
an **existing live role** rather than creating a new resource. The grant is additive and tightens
nothing, but it should land with whichever function turns out to be the finalizer (§8.4 item 1).

---

## 11. ⚠️ CI WARNING — read before any push

**`.github/workflows/seo-tools-deploy.yml` has a `push` trigger on `stack` whose paths include
`amplify/functions/shared/lambda_utils/**`.**

This build adds **five** modules there (`coupon_store.py`, `wix_coupons.py`, `gift_card_store.py`,
`gift_card_settlement.py`, `gift_card_spi_auth.py`). Every one matches that path filter. So:

> **A push of this work to `stack` will DEPLOY and LIVE-INVOKE `wecare-seo-tools`.**

That function is one of the two deliberately outside `deploy_all_lambdas.py` — it has a different in-zip
layout and `scripts/deploy_seo_tools.py` owns it along with its table and IAM policy — so the workflow is
the only thing that deploys it, and it will fire on a commit that has nothing to do with it.

**Before pushing: capture a rollback version of `wecare-seo-tools`.** `wecare-seo-tools` is one of the
seven functions with **no `live` alias**, which means `update-function-code` takes effect **immediately**
— there is no publish-and-move step to pause at and no alias to move back. The rollback is a code
re-upload, so the artifact has to exist beforehand.

**Nothing in this build pushed.** The warning is for whoever does.

---

## 12. Verification record

| Check | Result |
|---|---|
| `.venv/bin/python -m pytest -q` (whole tree) at the end of the build work | **6781 passed · 1 skipped · 7 xfailed · 0 failed · 0 xpassed** |
| `.venv/bin/python -m pytest tests/ -q` at the same point | 6744 passed · 1 skipped · 7 xfailed |
| **The owned suite** — the 12 new test files plus the 3 gate files this work edited | **508 passed · 7 xfailed · 0 failed · 0 xpassed** |
| Whole tree re-run **after** the documentation step | 6783 passed · 1 skipped · 7 xfailed · **5 failed — all 5 in one unrelated file, belonging to a concurrent session.** See the note below |
| Declared xfail count == DECISION 8's list | ✅ 7, enumerated in §6 |
| `0 xpassed` | ✅ — the criterion that catches a seam landing or an assertion being weakened |
| `.venv/bin/python scripts/deploy_all_lambdas.py --list` | resolves `wecare-coupons`, `wecare-gift-cards`, `wecare-wix-giftcard-spi` |
| Every one of HIGH-1..6 / MEDIUM-1..8 / NIT-1..6 appears by id with its resolution | ✅ §7 here, plus `coupons` §12.0 and `gift-cards` §13.0 |
| No document says `HEAD <commit id>` | ✅ no commit id appears in either promoted document |
| The six NIT-2 line references corrected | ✅ and each correction annotated with its finding id |
| Finding ids revision-prefixed | ✅ `R2-` / `R3-` / `R4-`, with the original spelling in brackets |
| Do-not-touch files modified | **none.** `.kiro/steering/META-BETA-REQUEST-EMAIL.md` shows ` M` but was dirty at baseline and was excluded by `--only` |
| Provisioner run with `--apply` | **never** |
| `deploy_all_lambdas.py` run without `--list` | **never** |
| Alias moved / version published / flag enabled / pushed | **never** |
| `secretsmanager get-secret-value` called | **never**, in any spelling |

### The 5 late failures are a concurrent session's, not this work's — and they were left alone

A re-run after the documentation step reported **5 failed**, all inside
**`tests/test_url_host_routing_rules.py`** and none anywhere else:

```
tests/test_url_host_routing_rules.py   5 FAILED   (the only file with any failure)
```

They are about `[retired public path ef531503]` redirects, `www` canonicalisation and Amplify rewrite rules, asserted against
`scripts/provision_legacy_redirects.py` — a URL-routing convergence that a **different session** is
mid-way through. `HEAD` moved during this step (a commit landed between the two runs), which is the
normal condition in this workspace.

**This work cannot have caused them, and that is provable rather than asserted:** the only tracked
modification in the tree is `.kiro/steering/META-BETA-REQUEST-EMAIL.md`, which was dirty at baseline and
belongs to nobody here; this step's own output is **three untracked Markdown files**. A Markdown file
cannot change the result of a Python test. The owned suite re-run at the same moment is **508 passed, 7
xfailed, 0 failed, 0 xpassed**.

**They were deliberately not fixed.** `multi-session-parallel-agents.md` rule 1 is one file, one
session: `tests/test_url_host_routing_rules.py` and `scripts/provision_legacy_redirects.py` belong to
whoever is converging them, and the test file's own helper (`_require_converged_provisioner`) says it
skips rather than fails *"against the PRE-convergence provisioner"* — so the owning session already has
a mechanism for this state and is the only one who can tell which side is behind. Editing either file
from here would overwrite live work and could not be checkpointed back.

**For whoever reads this later:** if those 5 are still red, they are that session's to close. Re-measure
with `.venv/bin/python -m pytest tests/test_url_host_routing_rules.py -q` and with the owned-suite
command above, and judge the two independently.

### What is explicitly NOT verified

- **`provision_checkout.py --verify`** — needs AWS and a live role, and the grant is not on the live role
  until `--apply` runs. Everything about it is verified offline over the policy document and the AST.
- **Every provisioner's `--verify`** — same reason: there is nothing live to read back.
- **Any Wix API behaviour.** Every API-shape claim is read from the fetched OpenAPI documents; no call
  was made. The SPI contract is in **Developer Preview** (`maturity: BETA` on all three methods) and must
  be re-measured before registration.
- **`check_data_model_drift.py --gate`** against the live account — the two tables do not exist yet. The
  allowance is asserted offline by test 57.

---

## 13. Related

- `docs/execution/coupons-20261001.md` — coupon design, revision 4
- `docs/execution/gift-cards-service-plugin-20261001.md` — gift-card design, revision 4
- `.agents/tasks/wix-coupons-giftcards-20261001/` — the plan, the review and the per-feature records
  (untracked; never staged)
- `.kiro/steering/whatsapp-payments-india-reference.md` — integer paise, fail-closed amount comparison,
  resolve-before-generate, and why only `captured` is AST-banned as a raw literal
- `.kiro/steering/lambda-snapstart-deploy.md` — why nothing is live until the `live` alias moves, and why
  a secret must be read lazily
- `.kiro/steering/maintenance-reporting.md` — the pointwise-confirmation list the KMS item sits on
- `.kiro/steering/multi-session-parallel-agents.md` — why every commit here used
  `git commit --only <paths>`
