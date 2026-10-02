# Implementation Plan — Wix coupons + gift cards (Service Plugin)

Written 2026-10-02 against the working tree at `HEAD c6fd53dc` (`origin/stack` is behind at
`887466a5`; 10 local commits unpushed — the orchestrator owns that, not this plan).

The spec is, in priority order:

1. `.agents/tasks/wix-coupons-giftcards-20261001/coupons-20261001.md`
2. `.agents/tasks/wix-coupons-giftcards-20261001/gift-cards-service-plugin-20261001.md`
3. `.agents/tasks/wix-coupons-giftcards-20261001/design-review.json` — 6 HIGH / 8 MEDIUM / 6 NIT
   OPEN findings, every one resolved in code below and pinned by a named test.

This is a build plan, not a design loop. Where the review requires a design decision to be made
rather than merely recorded, the decision is taken here in one or two sentences and is not to be
relitigated.

---

## 0. Measured facts the plan rests on

Each verified in this tree, not assumed:

| Fact | Evidence |
|---|---|
| Python is `/Users/wecaredigital/wecare-store/.venv/bin/python`; bare `python` is not on PATH | `conftest.py` raises a `UsageError` below 3.12 |
| Test runner is pytest with `--import-mode=importlib`, `testpaths = tests, amplify/functions` | `pytest.ini` |
| Focused run works: `98 passed in 0.46s` on the two cart/vocabulary files | measured |
| `cart_v2.add_coupon` posts `body={"couponCode": code.strip()}` at line 333 and guards `len(code.strip()) > 100` at line 329 | read |
| `cart_v2.calculate` refuses `giftCards`/`memberships`/`subscriptionCharges` in one check at line 515, then pins `payNow`/`totalAfterGiftCards` at 517 | read |
| `provision_checkout.py`: `_SIMULATED_ACTIONS` at **662**, `tables` at **785**, verdict loop keys on `EvalActionName` alone at **807**, iterates `_SIMULATED_ACTIONS` at **812** | read — HIGH-5 confirmed exactly |
| `Money.from_wix` requires a `str` matching `[0-9]{1,14}(\.[0-9]{1,2})?`; `Money.to_wix` emits that string; ceiling `9007199254740991` | `ecommerce/money.py` |
| `side_effect_guard.KNOWN_EFFECTS` is a 5-member `frozenset` validated in `claim()` | line 74, 101 |
| `payment_status` separates string values (`CAPTURED = "captured"`, 104) from `STATUS_RANK` (108) read through `rank()` (203) | read — the construction `gift_card_settlement` must mirror |
| `payment_attempt.RANK_ATTRIBUTE = "attemptRank"`, `condition_expression()` at 120, `may_create_order` at 227 | read |
| `Spec(name, source, *, standalone, extra_dirs, extra_files, provisioned_by)` | `deploy_all_lambdas.py:95` |
| No `SSESpecification` on any DynamoDB provisioner script; no CMK is created anywhere in `scripts/` | grepped — see DECISION 6 |

### Three pieces of collateral damage the design docs do NOT enumerate

Found by reading the existing suite. All three are existing tests that become **wrong by
construction**, and none appears in SEAM-C1c or SEAM-G12:

| Existing test | File:line | Why it breaks | Handled in |
|---|---|---|---|
| `test_exactly_one_spec_is_awaiting_provisioning` | `tests/test_deploy_map_provisioning.py:59` | asserts `waiting == [5 exact names]`; the three new `Spec`s all carry `provisioned_by` | item 19 |
| `test_the_role_cannot_delete_a_payment_attempt` | `tests/test_provision_checkout_contract.py:256` | asserts `"dynamodb:DeleteItem" not in actions` over **all** statements; SEAM-C3b/G9 add it scoped to the new tables | item 21 |
| `test_the_role_names_only_the_two_known_tables` | `tests/test_provision_checkout_contract.py:263` | asserts exactly two table ARNs | item 21 |

### CI WARNING — flag to the orchestrator before any push

`.github/workflows/seo-tools-deploy.yml` has a **push trigger on `stack`** whose paths include
`amplify/functions/shared/lambda_utils/**` (verified, lines 20-27). Every new module in this plan
lands there, so a push to `stack` will **deploy `wecare-seo-tools` and invoke it live**. Capture a
rollback version of `wecare-seo-tools` before pushing. Nothing in this plan pushes, deploys,
publishes, moves an alias, or enables a flag.

---

## Decisions taken here (settled; do not relitigate)

**DECISION 1 — module names follow the design, not the brief's two-file shorthand.** The brief's
owned-paths line names `ecommerce/coupons.py` and `ecommerce/gift_cards.py`; the design specifies
five modules and every test in the spec imports those names. The design is the spec, so the files
are `coupon_store.py`, `wix_coupons.py`, `gift_card_store.py`, `gift_card_settlement.py`,
`gift_card_spi_auth.py`. Same directory, same scope.

**DECISION 2 — three new Lambdas, not two.** `wecare-coupons`, `wecare-gift-cards` and
`wecare-wix-giftcard-spi`. Gift-card **issuance** must not sit behind a route reachable by anyone
who can reach Wix's caller (gift-cards §7), which is the whole reason the SPI is its own function.

**DECISION 3 (resolves HIGH-2) — the discounted total is read authoritatively from Calculate
Cart's own fields; the order-side total is asserted only on the Create Order RESPONSE.** Of the
two options the brief offers, this is the second. Reason: `Create Order`'s `priceSummary` is
documented `readOnly: true` (the review's own measurement), so a `priceSummary.total` we *send* is
discarded and an identity asserted against the sent payload asserts a property of a discarded
field. Therefore:

- **Sent payload** carries `appliedDiscounts[]` and `additionalFees[]` only — both writable.
- **Response readback** is where `priceSummary.total` and `priceSummary.subtotal` are asserted.
- The discount amount itself is copied verbatim from `summary.priceSummary.discount`, whose field
  description Wix states in full (quoted in coupons §1.3): *"Cart subtotal discount amount,
  deducted from the subtotal… Currently, only a single coupon is supported."* No echo assumption
  is needed, which is what makes this option the one with no unverified dependency.

**DECISION 4 (resolves HIGH-1) — Decision 1 is restated as "(a) for the arithmetic, (b) for
transport".** Wix computes the discount (option a); we relay it onto the order verbatim as
`appliedDiscounts[0] = {discountType: "GLOBAL", coupon: {id, code, name, amount}}` (option b's
field) because Place Order is never called and nothing else transports a cart coupon onto an order.
SEAM-C2 extends to **both** terms.

**DECISION 5 (resolves HIGH-3) — the existence fact moves onto the row whose key is known.** No
`Scan`, no prefix query, no new GSI. `GIFTCARD#<codeHash>` gains `activeHoldAttemptId`,
`activeHoldPaise`, `activeHoldExpiresAtMs`; `COUPON#<codeUpper>` gains `activeHoldCartId`,
`activeHoldExpiresAtMs`. `hold()` becomes ONE conditional `UpdateItem`:

```
ConditionExpression = "attribute_not_exists(activeHoldAttemptId) "
                      "OR activeHoldAttemptId = :me "
                      "OR activeHoldExpiresAtMs < :now"
```

`GCHOLD#` / `COUPONHOLD#` rows remain as audit records, written in the same request, never read to
make a decision. Rejected: a sort key (changes the table shape for every row type) and a GSI on
`codeHash` (eventually consistent, so it cannot gate a money decision). Every access pattern in
both stores is then a `GetItem`/`UpdateItem`/`PutItem` on an exact partition key, plus the staff
`Query` on `status-index`. Item 6 and item 12 each carry a test that enumerates the access
patterns.

**DECISION 6 (brief constraint not in either design doc) — the gift-card table is encrypted with a
customer-managed KMS key, created under an alias.** Neither design doc mentions `SSESpecification`
and no provisioner in this repo creates a CMK, so this is new ground. `provision_gift_cards_table.py`
creates `alias/wecare-gift-cards` and the table with
`SSESpecification={"Enabled": True, "SSEType": "KMS", "KMSMasterKeyId": "alias/wecare-gift-cards"}`,
and both roles get `kms:Decrypt` + `kms:GenerateDataKey` on the key ARN conditioned on
`kms:ViaService = dynamodb.us-east-1.amazonaws.com`. **KMS key creation requires pointwise owner
confirmation** (`maintenance-reporting.md`), so it is behind `--apply` and is recorded as an owner
item; nothing in this plan applies it. The alias indirection is deliberate: the ARN is not known
until creation, so the provisioner and the policy must agree on a name rather than a dated ARN.

**DECISION 7 — `scripts/provision_checkout.py` and its contract test are owned by this work, in
one visit.** It is deliberately **absent** from the brief's do-not-touch list while
`checkout/handler.py` is present, and the brief assigns HIGH-5 ("keep the `--verify` gate
working") here. Doing only HIGH-5's part 3 would leave tests 52/52a/52b/107/107a red; doing only
parts 1-2 would break the gate. So all three parts land together, covering **both** new table
ARNs at once (the design says whichever seam lands second adds only its ARN — landing both at once
removes the ordering hazard entirely). **Guard:** item 21 re-checks `git status --short
scripts/provision_checkout.py` immediately before editing. If another session has touched it, fall
back to leaving it a seam and marking tests 52/52a/52b/107/107a `xfail(strict=True)`; record the
fallback in the handoff doc.

**DECISION 8 — seam-dependent assertions are `xfail(strict=True)`, never weakened.** The design
already establishes this for tests 43 and 48. Applied identically to every test whose subject is a
do-not-touch file: 43, 48, 87 (SEAM-G1), 99/100 (SEAM-G1), 112 (SEAM-G14), 113 (SEAM-G8/initiation),
114/115 (SEAM-G7). `strict=True` so each converts from "pending" to "passing" the moment its
producer lands, and fails loudly if someone satisfies it by lowering the bar.

**DECISION 9 — `GC_VOIDED` reachability (resolves HIGH-6).** `GCTXN#<codeHash>#<transactionId>`
gains `paymentAttemptId`; `GCTXNID#<transactionId>` points to `{codeHash, paymentAttemptId}`;
`referenceId` on `GCTXN#` is demoted to "correlation only, never a key". A void carrying only a
`transactionId` then resolves both the card and the attempt in two exact-key `GetItem`s, so the
`UpdateItem` grant on `PaymentAttemptsTable` in `wecare-wix-giftcard-spi-role` is for a call that
can actually be composed.

**DECISION 10 — `redeem_cap` is defined exactly once (resolves HIGH-4).**

```python
# gift_card_store.py
RAZORPAY_MIN_LEG_PAISE = 100

def redeem_cap(*, balance_paise: int, wix_collection_paise: int) -> int:
    return min(balance_paise, wix_collection_paise - RAZORPAY_MIN_LEG_PAISE)
```

The §7.5 validation table and the §4.1 split both call it. The gift card funds the **supply only**;
the convenience fee and its GST are always on the Razorpay leg.

---

## Verification commands used throughout

```
.venv/bin/python -m pytest tests/<file>.py -q          # per-item focused run
.venv/bin/python -m pytest tests/ -q                   # owned-suite regression
.venv/bin/python -m pytest -q                          # full tree (tests/ + amplify/functions/)
.venv/bin/python scripts/deploy_all_lambdas.py --list   # registry resolves the three names
```

`deploy_all_lambdas.py --dry-run` validates imports against each function's **live** layer list and
so needs AWS and an already-created function; it cannot pass for a never-created function and is
**not** a gate here. Test 110 reproduces that check offline against a declared layer set instead —
that is the point of it.

Provisioner scripts are verified by offline **contract tests** that parse their AST and policy
documents, modelled on `tests/test_provision_checkout_contract.py`. No provisioner is run with
`--apply`.

---

# Ordered items

## Phase A — coupons

- [ ] 1. Create `amplify/functions/shared/lambda_utils/ecommerce/coupon_store.py`: the issuance
      store. Namespaced rows on `couponKey` per coupons §4.1, injected table resource and injected
      clock, no boto3 client, no ambient AWS. Includes the §4.2 attribute set (integer paise,
      integer basis points, `currency` compared explicitly against `"INR"`), the §5.4 validation
      table including `v % 100 == 0` → `SUB_RUPEE_DISCOUNT_NOT_SUPPORTED`, and the
      **`activeHoldCartId` / `activeHoldExpiresAtMs` attributes of DECISION 5**. Reuse
      `money.positive_paise` and `identifiers.new_uuid7`; invent no parallel helper.
      Files: `amplify/functions/shared/lambda_utils/ecommerce/coupon_store.py`
      Verify: `.venv/bin/python -c "import sys; sys.path.insert(0,'amplify/functions/shared'); import lambda_utils.ecommerce.coupon_store"` imports clean; item 3 adds the real tests.

- [ ] 2. Add the conditional-write surface to `coupon_store.py`: `claim()` (conditional put on
      `COUPON#<codeUpper>`), `hold()` / `release()` as the DECISION 5 single conditional
      `UpdateItem`, and `commit_redemption(table, *, code, cart_id, order_id, customer_id)` —
      **`cart_id` added, resolving MEDIUM-6**, since `accept_paid` already asserts
      `attempt['purchasedSnapshot']['cart']` is present before this point and one argument costs
      nothing where an extra read would. Order is claim → counters → hold delete (coupons §5.2).
      `limitPerCustomer` absent ⇒ **no `COUPONUSE#` condition is applied and the row is still
      incremented for audit** (resolves NIT-5). No read-modify-write anywhere.
      Files: `amplify/functions/shared/lambda_utils/ecommerce/coupon_store.py`
      Verify: item 3.

- [ ] 3. Write `tests/test_coupon_store.py` — spec tests 1-21, plus a test that enumerates the
      module's DynamoDB access patterns and asserts every one is an exact-key operation or the
      `status-index` `Query`, with zero `scan` call sites (**pins HIGH-3 / DECISION 5**), plus a
      test that `hold()` is one `UpdateItem` carrying the DECISION 5 `ConditionExpression` with no
      preceding `get_item`, plus the NIT-5 no-limit branch.
      Files: `tests/test_coupon_store.py`
      Verify: `.venv/bin/python -m pytest tests/test_coupon_store.py -q` — all pass.

- [ ] 4. Create `amplify/functions/shared/lambda_utils/ecommerce/wix_coupons.py`: the Wix mirror
      adapter, constructed exactly like `cart_v2.py` — **injected request callable**, no boto3, no
      secret read. `POST /stores/v2/coupons`, `GET /stores/v2/coupons/{id}`,
      `PATCH /stores/v2/coupons/{id}` with body exactly `{"specification": {"active": False}}`.
      Every Wix-bound amount is a whole-rupee `int` via `//` (coupons §4.2); times are epoch-ms
      strings. Reads **only** `coupon.id`, `specification.active`, `specification.type` from any
      response — never a numeric field. Never parses a status out of an exception message.
      Files: `amplify/functions/shared/lambda_utils/ecommerce/wix_coupons.py`
      Verify: item 5.

- [ ] 5. Write `tests/test_wix_coupons_contract.py` — spec tests 22-41 including 24a/24b, 37a/37b/37c
      (37c is the AST ban on parsing a status out of exception prose), and 25/26 which serialise the
      outgoing body with the same `json.dumps` call `wix_ecom._request` uses and assert
      `type(...) is int`. Add `tests/fixtures/wix_coupon_get_response.json`.
      Files: `tests/test_wix_coupons_contract.py`, `tests/fixtures/wix_coupon_get_response.json`
      Verify: `.venv/bin/python -m pytest tests/test_wix_coupons_contract.py -q` — all pass.

- [ ] 6. Create `amplify/functions/ecommerce/coupons/handler.py`: the `wecare-coupons` function,
      **five staff routes + two customer routes** per coupons §5.1. Staff routes call
      `middleware.require_auth` before any table access; the two customer routes resolve a
      `customer_session` and `POST /coupons/validate` additionally goes through
      `lambda_utils.rate_limit.check_rate_limit`. `validate` returns a verdict from the closed
      vocabulary and **never an amount**. Secret `wecare/wix/headless-api-key` referenced by id and
      read **lazily at request time** — never at module scope, never via a shell
      `get-secret-value`. No logging expression touches the key, not even reduced to a bool.
      Files: `amplify/functions/ecommerce/coupons/handler.py`
      Verify: item 7.

- [ ] 7. Write `tests/test_coupon_logging_and_vocabulary.py` (tests 59-61) and
      `tests/test_coupons_routes_and_registry.py` (tests 62-64; test 65 is deferred to item 19
      because it asserts the registry). Test 59 is an AST walk of every `logger.*` argument,
      transitively through local helpers, asserting the Wix key never appears in a logging
      expression. Test 60 pins that a coupon code **may** be logged in full, so the deliberate
      asymmetry against gift cards is not "harmonised" away later.
      Files: `tests/test_coupon_logging_and_vocabulary.py`, `tests/test_coupons_routes_and_registry.py`
      Verify: `.venv/bin/python -m pytest tests/test_coupon_logging_and_vocabulary.py tests/test_coupons_routes_and_registry.py -q` — all pass except test 65, which is not yet written.

- [ ] 8. Write `tests/test_coupon_reconciliation.py` — spec tests 42-51, carrying **DECISION 3 and
      DECISION 4**. Test 48 asserts, against a mocked `Create Order` **response readback**:
      `Money.from_wix(returned["priceSummary"]["total"]["amount"]).paise == quote.total_payable_paise
      == verifiedCapturedPaise + giftCardRedeemedPaise` (gift-card term `0` here), **plus**
      `returned["priceSummary"]["subtotal"] == cart["priceSummary"]["subtotal"]` (HIGH-2's added
      dependency), **plus**
      `Money.from_wix(returned["priceSummary"]["totalAdditionalFees"]["amount"]).paise ==
      quote.convenience_fee_paise + quote.convenience_gst_paise` (**resolves MEDIUM-8**), **plus**
      `appliedDiscounts[0]["coupon"]["amount"]["amount"]` byte-identical to
      `cart["priceSummary"]["discount"]["amount"]` (**resolves HIGH-1**). The `additionalFees[]`
      entry sends **all three** of `price`, `priceBeforeTax`, `priceAfterTax` — `price` and
      `priceAfterTax` = fee + GST, `priceBeforeTax` = fee — because `PriceSummary.totalAdditionalFees`
      is what Wix sums and nothing documents which field it derives from (MEDIUM-8). Tests 43 and 48
      are `xfail(strict=True)` against SEAM-C1 / SEAM-C2 per DECISION 8; the endpoint and the
      option-(a) claim are asserted **unconditionally**.
      Files: `tests/test_coupon_reconciliation.py`, `tests/fixtures/wix_cart_v2_coupon_applied_v2_shape.json`
      Verify: `.venv/bin/python -m pytest tests/test_coupon_reconciliation.py -q` — passes with the two declared xfails and no xpass.

- [ ] 9. Create `scripts/provision_coupons_table.py` — `stack-wecare-digital-CouponsTable`,
      partition key `couponKey`, `status-index` (HASH `status`, RANGE `createdAt`),
      PAY_PER_REQUEST, PITR **enabled**, TTL **disabled and asserted in `--verify`**. Model on
      `scripts/provision_payment_attempts_table.py` (same `--apply` / `--verify` / dry-run-default
      shape, same `describe_time_to_live` + `PointInTimeRecoveryDescription` assertions).
      Files: `scripts/provision_coupons_table.py`
      Verify: item 11.

- [ ] 10. Create `scripts/provision_coupons_role.py` (`wecare-coupons-role`, coupons §6: five
      DynamoDB actions on the table + index, `secretsmanager:GetSecretValue` on
      `secret:wecare/wix/headless-api-key-*` only, own log group, trust with
      `aws:SourceAccount 775261844268`, no `Scan`, no wildcard) and
      `scripts/provision_coupons_routes.py` (the seven route keys, `AWS_PROXY` payload 2.0 onto
      `...:function:wecare-coupons:live`, one `lambda:InvokeFunction` statement per route with
      `SourceArn` scoped to `.../zllr9lrg7j/*/*/coupons*`, existing routes reported never
      recreated, `--apply` required).
      Files: `scripts/provision_coupons_role.py`, `scripts/provision_coupons_routes.py`
      Verify: item 11.

- [ ] 11. Write `tests/test_coupons_iam_and_table.py` — spec tests 52-58 as offline contract tests
      over the provisioner ASTs and policy documents, modelled on
      `tests/test_provision_checkout_contract.py`. Tests 52/52a/52b target
      `provision_checkout.py` and are written here but **only pass after item 21**, so they are
      `xfail(strict=True)` until item 21 flips them (the fixer step in the convergence loop removes
      the marks). Test 57 is deferred to item 18 (it asserts the drift allowance). Test 56 asserts
      the provisioner asserts TTL disabled and PITR enabled.
      Files: `tests/test_coupons_iam_and_table.py`
      Verify: `.venv/bin/python -m pytest tests/test_coupons_iam_and_table.py -q` — passes with declared xfails.

## Phase B — gift cards

- [ ] 12. Create `amplify/functions/shared/lambda_utils/ecommerce/gift_card_store.py`: the liability
      ledger. Partition key is `HMAC-SHA256(pepper, NFKC(code).upper()).hexdigest()` — **never the
      code**. Pepper from `wecare/wix/giftcard-spi` → `code_pepper`, by id, lazily, at request time.
      Row types per gift-cards §6.3 **with DECISION 9 applied**: `GCTXN#` gains
      `paymentAttemptId`, `GCTXNID#` points to `{codeHash, paymentAttemptId}`, `referenceId` on
      `GCTXN#` is correlation only. Card row gains the **DECISION 5** `activeHoldAttemptId` /
      `activeHoldPaise` / `activeHoldExpiresAtMs`. Ceiling is the SPI's `99_999_999_999` paise
      asserted on issuance **and every credit**. `redeem_cap()` exactly as **DECISION 10**, defined
      once. Balance moves are `ADD balancePaise :neg` under `ConditionExpression balancePaise >=
      :amount`; the `GCORDER#<codeHash>#<paymentAttemptId>` claim is a conditional put written
      **before** the decrement. Codes are 16 chars from a Crockford-style alphabet generated with
      `secrets`, never `random`. Constant-time PIN compare (`hmac.compare_digest`). Logs carry
      `codeLast4` only.
      Files: `amplify/functions/shared/lambda_utils/ecommerce/gift_card_store.py`
      Verify: item 14.

- [ ] 13. Create `amplify/functions/shared/lambda_utils/ecommerce/gift_card_settlement.py` — the §3
      ladder, mirroring `payment_status.py`'s construction exactly: five **string** stage values, a
      separate `STAGE_RANK: Dict[str, int]` with `GC_UNKNOWN` **deliberately absent** so
      `stage_rank` returns 0 through `.get`, `condition_expression()`, and
      `advance(attempts, *, attempt_id, stage, **evidence)` as ONE conditional `UpdateItem` whose
      evidence keys are the **closed** four-key set (`giftCardRequiredPaise`, `giftCardCodeHash`,
      `giftCardRedeemedPaise`, `giftCardTransactionId`) — anything else raises, and
      `verifiedCapturedPaise` is excluded on purpose. `RAZORPAY_EVIDENCE_ATTR` and
      `RAZORPAY_VERIFIED_PAISE_ATTR` are module constants so a rename decided elsewhere is one line
      (gift-cards §11). `is_fully_settled(attempt)` per §3.2 verbatim, including: the
      `required == 0` membership test over `(GC_NOT_REQUIRED, GC_UNKNOWN)`, the closure against
      `verifiedCapturedPaise`, and **never raising** on a missing attribute. Reads the Razorpay leg
      only through `payment_attempt.may_create_order`. Decisions never compare a raw `'captured'`.
      Files: `amplify/functions/shared/lambda_utils/ecommerce/gift_card_settlement.py`
      Verify: item 16.

- [ ] 14. Write `tests/test_gift_card_store.py` — spec tests 42-64, with **MEDIUM-7's renames
      applied**: 49 → `test_a_second_redeem_for_the_same_payment_attempt_returns_the_same_transaction_id`,
      50 → `..._for_the_same_payment_attempt_does_not_move_the_balance`,
      53 → `test_two_different_payment_attempts_each_deduct_once`. Add a test that enumerates every
      DynamoDB access pattern and asserts exact-key-or-`status-index` only, zero `scan` (**pins
      HIGH-3**), and a test that a void carrying **only** a `transactionId` resolves both the card
      and the attempt (**pins HIGH-6 / DECISION 9**). Test 46 pins the gift-card/coupon logging
      asymmetry from this side.
      Files: `tests/test_gift_card_store.py`
      Verify: `.venv/bin/python -m pytest tests/test_gift_card_store.py -q` — all pass.

- [ ] 15. Create `amplify/functions/shared/lambda_utils/ecommerce/gift_card_spi_auth.py`:
      `verify(raw_body, *, headers, now) -> Context`. **The raw body IS the JWT.** Honour
      `isBase64Encoded` first, then the **three-segment base64url check is the real discriminator**
      — **MEDIUM-4: the `Content-Type` rejection is dropped**, because the only documented
      `plain/text` example is the app-install instance-id callback, not a gift-card call, and
      401-ing every live request on an undocumented header value is feature-dead rather than
      fail-closed. `Authorization` is ignored entirely. Then: signature via
      `cryptography` (`load_pem_public_key` + `public_key.verify` with PKCS1v15 and the hash the
      `alg` names), algorithm allowlist `{RS256, RS384, RS512}` with `alg: none` and every HMAC alg
      refused, `aud` == configured app id (absent or multi-valued rejected), `iss == "wix.com"`
      exact, `iat <= now + 60` and `exp > now - 60` with a missing claim **rejected not defaulted**,
      then `data.metadata` as a `Context` and `metadata.instanceId` against the installed instance,
      then `data.request` returned. Claims parsed with `json.loads(..., parse_float=Decimal)`.
      Public key read from `wecare/wix/giftcard-spi` → `public_key`, by id, **lazily per request**.
      Every failure is **401 with an empty body**. No secret in any logging expression.
      Files: `amplify/functions/shared/lambda_utils/ecommerce/gift_card_spi_auth.py`
      Verify: item 17.

- [ ] 16. Write `tests/test_gift_card_two_leg_finalization.py` — spec tests 65-86 including
      83a/83b/83c/83d, with **MEDIUM-7's rename**: 80 →
      `test_the_hold_is_taken_after_the_attempt_id_is_minted_and_before_the_gateway`. Test 69 is the
      one that would have caught HIGH-1 of the previous round: an attempt carrying only the Razorpay
      attributes and **no gift-card key at all** is fully settled. Tests 85 and 83d are AST walks.
      Files: `tests/test_gift_card_two_leg_finalization.py`
      Verify: `.venv/bin/python -m pytest tests/test_gift_card_two_leg_finalization.py -q` — all pass.

- [ ] 17. Write `tests/test_gift_card_spi_auth.py` — spec tests 1-21, generating an RSA keypair in
      the fixture. Test 2 is **re-pointed by MEDIUM-4**: renamed to
      `test_a_body_that_is_not_three_segments_is_refused_whatever_the_content_type` and parametrised
      over `application/json`, `application/jwt`, `text/plain`, `plain/text` and a missing header,
      asserting the declared type never decides the outcome. Test 4 keeps the
      `Authorization`-header-with-a-non-JWT-body rejection. Tests 13 are prefixed to avoid colliding
      with `tests/test_customer_auth_and_throttle.py:92`.
      Files: `tests/test_gift_card_spi_auth.py`, `tests/fixtures/wix_spi_get_balance_jwt_payload.json`, `tests/fixtures/wix_spi_redeem_jwt_payload.json`, `tests/fixtures/wix_spi_void_jwt_payload.json`
      Verify: `.venv/bin/python -m pytest tests/test_gift_card_spi_auth.py -q` — all pass.

- [ ] 18. Create the two gift-card handlers.
      `amplify/functions/ecommerce/wix-giftcard-spi/handler.py`: exactly three paths
      (`v1/balance`, `v1/redeem`, `v1/void`), verification **first**, before the body is interpreted
      and before any table access. Responses are exactly the documented fields and nothing more.
      Error bodies are exactly `{"name", "applicationCode"}` at the documented status. A `/v1/redeem`
      for a card holding any hold or claim returns `AlreadyRedeemed` 409 and deducts nothing — and
      under DECISION 5 that check is a single exact-key `GetItem` on `GIFTCARD#<codeHash>` reading
      `activeHoldAttemptId`, not a prefix scan. `GC_VOIDED` is written through `advance()` using the
      `paymentAttemptId` DECISION 9 made reachable.
      `amplify/functions/ecommerce/gift-cards/handler.py`: **five routes, not seven — MEDIUM-5
      removes `POST /gift-cards/hold` and `POST /gift-cards/release`**, because a customer session
      has no `paymentAttemptId` before checkout mints one, and a hold taken outside the request that
      mints it either skips the `GC_HELD` stage (leaving `giftCardRequiredPaise` unwritten, so
      `is_fully_settled` reads `required == 0` and settles a gift-card order on the Razorpay leg
      alone) or is denied by IAM. The hold is taken **only** by the checkout producer (SEAM-G4 /
      SEAM-G14). The customer surface is `POST /gift-cards/balance` only, which reserves nothing.
      Files: `amplify/functions/ecommerce/wix-giftcard-spi/handler.py`, `amplify/functions/ecommerce/gift-cards/handler.py`
      Verify: item 20.

- [ ] 19. Write `tests/test_gift_card_spi_contract.py` (tests 22-41, including 28a/28b) and
      `tests/test_gift_card_amounts_and_gst.py` (tests 87-100 including 95, 96, 97, 97a, 97b, 97c,
      98). The amounts file carries the §2 worked example (`2500` / `450`, never `1574` / `283`),
      the six §4.2 identities each through `Money.from_wix`, and the DECISION 10 boundaries with the
      Wix adapter as a spy asserting **zero calls** on 97a/97b. Tests 87/99/100 are
      `xfail(strict=True)` against SEAM-G1 per DECISION 8.
      Files: `tests/test_gift_card_spi_contract.py`, `tests/test_gift_card_amounts_and_gst.py`, `tests/fixtures/wix_cart_v2_gift_card_partial.json`
      Verify: `.venv/bin/python -m pytest tests/test_gift_card_spi_contract.py tests/test_gift_card_amounts_and_gst.py -q` — passes with declared xfails, no xpass.

- [ ] 20. Create `scripts/provision_gift_cards_table.py` (**DECISION 6**: the CMK alias
      `alias/wecare-gift-cards` plus the table with `SSEType: KMS`; PITR on; **TTL disabled and
      asserted** — a liability must not expire silently),
      `scripts/provision_gift_cards_roles.py` (the two least-privilege roles of gift-cards §10.1
      with the asymmetries intact — `DeleteItem` on `wecare-gift-cards-role` only, `UpdateItem` on
      `PaymentAttemptsTable` on `wecare-wix-giftcard-spi-role` only — plus the DECISION 6 `kms:`
      grants, plus `--alarms` creating `wecare-gift-card-wix-spi-redemption` and
      `wecare-gift-card-charge-mismatch` at `Sum >= 1`, plus attaching the **version-pinned** layer
      `arn:aws:lambda:us-east-1:775261844268:layer:cryptography-python312:1`) and
      `scripts/provision_gift_card_routes.py` — **renamed from `provision_gift_card_spi_routes.py`
      per NIT-3**, because a file named `..._spi_routes.py` that creates five non-SPI routes
      alongside three SPI ones misleads; the registry `provisioned_by` strings in item 22 use the
      new name.
      Files: `scripts/provision_gift_cards_table.py`, `scripts/provision_gift_cards_roles.py`, `scripts/provision_gift_card_routes.py`
      Verify: item 21.

- [ ] 21. Write `tests/test_gift_cards_iam_and_table.py` — spec tests 101-115. Test 110 resolves
      every top-level import in the SPI handler and `gift_card_spi_auth.py` against the package plus
      the **declared** layer set the way `deploy_all_lambdas.py` does, so a missing `cryptography`
      layer is caught offline rather than at the deploy gate (line 570). Test 111 asserts the exact
      version-pinned ARN. Tests 107/107a target `provision_checkout.py` and pass only after item 23;
      tests 112/113/114/115 target do-not-touch files; all are `xfail(strict=True)` per DECISION 8.
      Add a test asserting the DECISION 6 `SSESpecification` and the `kms:ViaService` condition.
      Files: `tests/test_gift_cards_iam_and_table.py`
      Verify: `.venv/bin/python -m pytest tests/test_gift_cards_iam_and_table.py -q` — passes with declared xfails.

## Phase C — the shared gates (these touch files other work also reads; land them together)

- [ ] 22. Add the **two** `UNDECLARED_ALLOWED` entries (`CouponsTable`, `GiftCardsTable`) to
      `scripts/check_data_model_drift.py`, verbatim from coupons §4, and the **three-entry**
      `RAW_SCAN_ONLY_FILES` list plus its parametrisation to
      `tests/test_payment_vocabulary_at_decision_points.py`, verbatim from coupons §9.
      `test_the_handler_imports_the_vocabulary_module` stays parametrised on `CONSULTING_FILES`
      alone and `FORBIDDEN_RAW == {"captured"}` is unchanged. Then add spec test 57 to
      `tests/test_coupons_iam_and_table.py` (both tables allowed, each with a non-empty reason).
      Files: `scripts/check_data_model_drift.py`, `tests/test_payment_vocabulary_at_decision_points.py`, `tests/test_coupons_iam_and_table.py`
      Verify: `.venv/bin/python -m pytest tests/test_payment_vocabulary_at_decision_points.py tests/test_coupons_iam_and_table.py -q` — all pass, including the three new raw-scan parametrisations.

- [ ] 23. Add the **three** `Spec(...)` entries to `scripts/deploy_all_lambdas.py` verbatim from
      coupons §8, each with a non-empty `provisioned_by` (using `provision_gift_card_routes.py` per
      NIT-3), **and extend `tests/test_deploy_map_provisioning.py::test_exactly_one_spec_is_awaiting_provisioning`
      to the new eight-name list** — the collateral-damage finding above; the existing test asserts
      an exact ordered list of five and would otherwise fail. Add a comment in that test naming each
      new function and why it is legitimately awaiting first provisioning, matching the three
      comments already there. Then add spec test 65 to
      `tests/test_coupons_routes_and_registry.py`.
      Files: `scripts/deploy_all_lambdas.py`, `tests/test_deploy_map_provisioning.py`, `tests/test_coupons_routes_and_registry.py`
      Verify: `.venv/bin/python -m pytest tests/test_deploy_map_provisioning.py tests/test_coupons_routes_and_registry.py -q` — all pass; `.venv/bin/python scripts/deploy_all_lambdas.py --list` lists the three new names.

- [ ] 24. **The HIGH-5 edit.** First run `git status --short scripts/provision_checkout.py
      tests/test_provision_checkout_contract.py`; if either is modified by another session, stop,
      leave it a seam, and record the fallback (DECISION 7). Otherwise make all three parts in one
      edit:
      (a) add the inline-policy statement granting `dynamodb:GetItem, PutItem, UpdateItem,
      DeleteItem` on `table/stack-wecare-digital-CouponsTable` **and**
      `table/stack-wecare-digital-GiftCardsTable` — additively, on this per-function role, never on
      `wecare-digital-lambda-role`;
      (b) `_SIMULATED_ACTIONS` (line 662) gains `dynamodb:DeleteItem` and the simulated `tables`
      list (line 785) gains both new ARNs;
      (c) add `_EXPECTED_DENY = {("dynamodb:DeleteItem", PAYMENT_ATTEMPTS_TABLE),
      ("dynamodb:DeleteItem", COMMERCE_KEYS_TABLE)}` and **re-key the verdict loop (line 807) on
      `(EvalActionName, EvalResourceName)`**, reporting a problem only when a pair is denied and not
      expected, or allowed and expected-denied. Without (c) a correctly provisioned role fails
      `verify()`, because `DeleteItem` allowed on `CouponsTable` and implicitly denied on
      `PaymentAttemptsTable` aggregates to a non-`{"allowed"}` set under the current per-action key.
      Then update the two existing contract tests: `test_the_role_cannot_delete_a_payment_attempt`
      asserts per **statement** that no statement granting `DeleteItem` names
      `PaymentAttemptsTable` or `WixOrderIds` (a strengthening, not a weakening), and
      `test_the_role_names_only_the_two_known_tables` becomes the four known tables.
      Files: `scripts/provision_checkout.py`, `tests/test_provision_checkout_contract.py`
      Verify: `.venv/bin/python -m pytest tests/test_provision_checkout_contract.py -q` — all pass.

- [ ] 25. Remove the `xfail(strict=True)` marks from tests 52, 52a, 52b, 107 and 107a, which item 24
      has just made genuinely passing. Leave every other xfail in place — their producers are
      do-not-touch files.
      Files: `tests/test_coupons_iam_and_table.py`, `tests/test_gift_cards_iam_and_table.py`
      Verify: `.venv/bin/python -m pytest tests/test_coupons_iam_and_table.py tests/test_gift_cards_iam_and_table.py -q` — all pass with no xpass.

## Phase D — documentation and the seam register

- [ ] 26. Promote both design docs to `docs/execution/coupons-20261001.md` and
      `docs/execution/gift-cards-service-plugin-20261001.md`, applying every review resolution so
      the promoted copy is the current truth rather than the reviewed draft. Specifically:
      NIT-1 — replace `HEAD ae1e11b5` with the date (`re-measured 2026-10-02`) rather than another
      commit id that will drift; NIT-2 — correct the drifted line references (`wix_ecom.py` HTTPError
      **108**, `_SIMULATED_ACTIONS` **662**, `wix_writeback` resolve/raise **256/259**, the cart test
      body literal **91** and `set(body)` **160**, `website_checkout` attempt-id mint **199**,
      razorpay-webhook `provider_paise != intent_paise` **952** with the note that it sits on the
      **partner wallet top-up** path, not a checkout path); NIT-3 — align the gift-card registry
      entry's `provisioned_by` with §12.3 and adopt the renamed route script; NIT-4 — record that
      `CreateCartRequest.coupons` is `maxItems 1` while `giftCards` is `maxItems 5`, so a later
      reader does not conclude the quotation was misread (enforcing one stays correct); NIT-6 —
      prefix finding ids by revision (`R2-H1`, `R3-H1`, `R4-H1`) from here on. Also fold in
      DECISIONS 3-6 and 9-10, MEDIUM-1's `outcome.verifiedCapturedPaise` producer statement,
      MEDIUM-2's three extra split rows, MEDIUM-3's fourth producer and the new §8.5, MEDIUM-4's
      Content-Type move to owner item 12.1.4, MEDIUM-5's five-route surface, MEDIUM-6's `cart_id`,
      MEDIUM-7's renames and MEDIUM-8's three price fields.
      Files: `docs/execution/coupons-20261001.md`, `docs/execution/gift-cards-service-plugin-20261001.md`
      Verify: `.venv/bin/python -m pytest tests/ -q` — unchanged pass count (docs carry no code), and every finding id in `design-review.json` appears in a response table in one of the two promoted docs.

- [ ] 27. Write `docs/execution/coupons-giftcards-build-20261001.md`, the handoff. It must carry, as
      tables rather than prose: every item in this plan with its status; the **complete seam
      register** with each seam's owner, its exact anchor and the test that is `xfail(strict=True)`
      against it; the **MEDIUM-1** statement that `outcome` gains `verifiedCapturedPaise` written by
      the caller from the same `razorpay_verify` readback that produced
      `outcome['providerPaymentId']` (`website_checkout.py:430`'s `amount_paise`, or the webhook's
      `provider_paise`) and that `record_paid` refuses a call carrying a provider id without an
      amount; the **MEDIUM-2** three additional `website_checkout.py` split rows (`_browser_options`
      carries `payNowPaise` → `options['amountPaise']`; `_recover_ambiguous_create` carries
      `payNowPaise`; `_ready_from_binding` reads the binding so **needs no change**, stated so its
      absence is deliberate); the **MEDIUM-3** fourth attempt producer
      (`blog_contribution.prepare_contribution:355`, declared out of scope — a contribution flow has
      no Wix cart, so no `wixCollectionPaise` exists to cap a redemption against — with test 113b
      asserting it writes no gift-card attribute); the **SEAM-G7** three-part edit including
      `WIX_GIFT_CARD_TENDER` in `side_effect_guard.KNOWN_EFFECTS` and the `record_gift_card_tender`
      sibling; the owner-action list from both docs plus **DECISION 6's KMS key creation** as a
      pointwise confirmation; and the **CI warning** about `seo-tools-deploy.yml`.
      Files: `docs/execution/coupons-giftcards-build-20261001.md`
      Verify: the file names every one of HIGH-1..6, MEDIUM-1..8, NIT-1..6 with its resolution and its test; `.venv/bin/python -m pytest -q` is green.

- [ ] 28. Full-tree regression and finding audit. Run the whole suite and confirm no pre-existing
      test regressed and no xfail turned into an xpass. Then walk `design-review.json` and confirm
      each of the 20 findings maps to at least one named test in the owned suite.
      Files: none
      Verify: `.venv/bin/python -m pytest -q` — pass count ≥ the pre-change baseline plus the new
      tests, `0 failed`, `0 xpassed`; the declared xfail count equals the DECISION 8 list exactly.

---

## Finding → item → test map

| Finding | Resolved in | Pinned by |
|---|---|---|
| HIGH-1 (appliedDiscounts transport) | DECISION 4, item 8 | test 48 `appliedDiscounts[0].coupon.amount.amount` byte-identical to the cart discount |
| HIGH-2 (Calculate-Cart echo / readOnly priceSummary) | DECISION 3, item 8 | test 48 against the Create Order **response**, plus `subtotal` equality |
| HIGH-3 (no key-prefix lookup) | DECISION 5, items 1-3, 12, 14 | access-pattern enumeration tests in both store suites; `hold()` one-conditional-UpdateItem test |
| HIGH-4 (`redeemCap` defined twice) | DECISION 10, item 12 | tests 96, 97, 97a, 97b, 97c + a test that validator and split call the one function |
| HIGH-5 (`--verify` gate) | DECISION 7, item 24 | tests 52, 52a, 52b, 107, 107a + `test_provision_checkout_contract.py` |
| HIGH-6 (`GC_VOIDED` unreachable) | DECISION 9, items 12, 18 | item 14's void-by-transaction-id-alone test |
| MEDIUM-1 (`verifiedCapturedPaise` producer) | item 27 (seam statement) | tests 83, 83a, 83c read it through `RAZORPAY_VERIFIED_PAISE_ATTR` |
| MEDIUM-2 (3 unlisted `amount_paise` consumers) | item 27 | test 112 extended with `options['amountPaise'] == payNowPaise` (xfail) |
| MEDIUM-3 (fourth attempt producer) | item 27 | test 113b (xfail) |
| MEDIUM-4 (Content-Type 401) | item 15 | item 17's parametrised three-segment test |
| MEDIUM-5 (customer hold route) | item 18 | test 45 route enumeration = five routes |
| MEDIUM-6 (`commit_redemption` cart_id) | item 2 | item 3's hold-release test |
| MEDIUM-7 (stale `reference` test names) | items 14, 16 | the renamed tests themselves |
| MEDIUM-8 (`AdditionalFee.price`) | item 8 | test 48's `totalAdditionalFees` assertion |
| NIT-1..NIT-6 | item 26 | item 26's verification: every finding id appears in a promoted response table |

---

## Hard constraints this plan is bound by

Integer INR paise only, no float on any path, `Decimal` only at boundaries, Wix amounts parsed
`parse_float=Decimal`. A gift-card code is **bearer value** (HMAC-with-pepper key, `codeLast4` in
logs, constant-time compare, never in a log or a URL); a coupon code is **not** and may be logged in
full — the asymmetry is pinned from both sides. Money idempotency via `ConditionExpression`, never
read-modify-write; one redemption per `(code, order)` / `(codeHash, paymentAttemptId)`; a concurrent
redeem race must not double-succeed. Fail **closed** on every ambiguous verification. Stages are
monotonic and forward-only. Payment-status decisions go through `lambda_utils/payment_status.py`; a
raw `'captured'` at a decision point is AST-banned. Injected store, injected clock, no ambient AWS in
logic; reuse the existing `Money`/paise and conditional-write helpers rather than inventing parallels.
Each new Lambda gets its **own** least-privilege role scoped to its **own** table; no statement is
added to `wecare-digital-lambda-role`. The gift-card balance table is CMK-encrypted (DECISION 6). No
TTL on a money table. `secretsmanager get-secret-value` / `batch-get-secret-value` are never called
in any spelling — secrets are referenced by id and read lazily at request time. No credential value
in any command, argv, log, or logging **expression** (CodeQL `py/clear-text-logging-sensitive-data`
tracks taint across functions; log `type(exc).__name__`). Nothing here deploys, publishes, moves an
alias, pushes, or enables a flag.
