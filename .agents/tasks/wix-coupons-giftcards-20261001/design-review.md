# Design review — Wix coupons + gift cards (revision 3)

Reviewed 2026-10-02, fresh, without the context that produced the documents.

Documents:

- `.agents/tasks/wix-coupons-giftcards-20261001/coupons-20261001.md` (revision 3)
- `.agents/tasks/wix-coupons-giftcards-20261001/gift-cards-service-plugin-20261001.md` (revision 3)

Method: every repository claim cited by either document was opened and read. Every
`dev.wix.com` URL load-bearing for an API shape was fetched live and the embedded OpenAPI
document grepped for the schema the design transcribes — so the Wix claims below are
independently re-measured, not taken on the documents' word. Builds and test suites were not
run; this is a document review.

**Verdict: CHANGES_REQUESTED — 6 HIGH, 8 MEDIUM, 6 NIT.**

Both documents have improved markedly. The Wix transcriptions are, on re-measurement, unusually
accurate — I could not find a single misquoted schema field or a single fabricated method name.
The findings below are almost all *internal*: places where a correct Wix measurement and a
correct repository measurement have not been reconciled with each other, or where a decision
taken in one section is contradicted by the table a coder would actually implement from.

---

## HIGH

### HIGH-1 — Decision 1 (option (a) alone) cannot make the Wix order total net of the coupon; the discount has no specified route onto the order

`coupons-20261001.md` §2 chooses option (a) — mirror the coupon into the Wix cart with
`Add Coupon` — and **rejects option (b)**, "recording the discount on the Wix order through
`appliedDiscounts`", on the grounds that (b) "creates a second discount arithmetic".

But the Wix order in this architecture is **not placed from the cart**. §1.3 and §10 both state
that `Place Order` is never called; the order is created by `wix_writeback.create_wix_order` from
`attempt['wixOrderPayload']`, a payload we compose. Nothing carries the cart's coupon across that
boundary. So under option (a) as written, the Wix order is built from line items at full price
with no discount term, and `wixOrder.priceSummary.total` exceeds `verifiedCapturedPaise` by the
discount — the exact mismatch Decision 1 exists to close.

§2.3's own identity 1 gives this away: it requires
`Money.from_wix(order["priceSummary"]["discount"]["amount"]).paise ==
Money.from_wix(cart["priceSummary"]["discount"]["amount"]).paise`, i.e. it requires a discount
**on the order**. That is option (b)'s mechanism, used as transport. Yet SEAM-C2 (§8) asks the
payload builder only for `additionalFees[]` and never mentions the discount at all, so the
producer would satisfy SEAM-C2 in full and still emit an order that does not reconcile.

Measured, the mechanism is available and writable:

```
com.wix.ecom.orders.v1.CreateOrderRequest.order.appliedDiscounts
  "Applied discounts.", maxItems 320, items -> com.wix.ecom.orders.v1.AppliedDiscount
  (no readOnly flag)
```
https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/orders/orders/create-order

**Concrete fix.** Restate Decision 1 as "(a) for the arithmetic, (b) for transport", which is
what the identity already assumes, and say so in one sentence so it cannot be read as a
rejection of `appliedDiscounts`:

> The discount is **computed** by Wix `Calculate Cart` (option (a)) and **transported** onto the
> Wix order as `appliedDiscounts[]` (option (b)'s field), with every value copied verbatim from
> the cart's `priceSummary.discount` / `cartSummary.discounts`. We never compute a discount; we
> relay the one Wix computed. The §2's objection to (b) was to (b) as an *independent
> computation*, not to its field.

Then extend SEAM-C2 to both terms:

| SEAM-C2 must make the payload carry | Source |
|---|---|
| `additionalFees[]` = convenience fee + GST | `quote.convenience_fee_paise`, `quote.convenience_gst_paise` |
| `appliedDiscounts[]` = `{discountType: "GLOBAL", coupon: {id, code, name, amount}}` | `cart["coupons"][0]` and `cart["priceSummary"]["discount"]["amount"]`, copied verbatim |

and add to test 48 an assertion that `appliedDiscounts[0].coupon.amount.amount` is byte-identical
to the cart's `priceSummary.discount.amount` — one arithmetic, relayed, not recomputed.

### HIGH-2 — `Order.priceSummary` is documented `readOnly: true`, so two of §2.3's three identities compare a field Wix ignores

§2.3 flags as "unverified, and it is the assumption the whole invariant rests on" that "Wix
accepts and preserves a supplied `priceSummary.total` and `additionalFees[]` on `Create Order`
without recomputing them."

The page the document already cites answers it, in the direction that invalidates half the
premise. Measured from the Create Order OpenAPI document:

```
"priceSummary": {"description":"Order price summary.", "readOnly": true,
                 "$ref":"#/components/schemas/com.wix.ecom.orders.v1.PriceSummary", ...}
"additionalFees": {"description":"Additional fees applied to the order.", maxItems 100, ...}
                 (no readOnly)
```

So `additionalFees` is an input and `priceSummary` is **not** — Wix computes it. Identity 1 and
identity 2 in §2.3 are written against `order = wixOrderPayload` ("what we POST to Create
Order"), which means identity 1 asserts a property of a field Wix discards, and identity 3's
`order["priceSummary"]["total"]` is only meaningful on the response.

**Concrete fix.** Split the identity block by direction, and state the dependency the read-only
flag creates:

```python
sent      = wixOrderPayload            # additionalFees[], appliedDiscounts[], lineItems
returned  = createOrderResponse["order"]   # priceSummary is Wix's own computation
cart      = wixCartSummary

# INPUTS we control
sent["additionalFees"] == [{"code": "WD-CONVENIENCE", "name": "Convenience fee",
                            "price":          {"amount": Money(fee + gst).to_wix()},
                            "priceBeforeTax": {"amount": Money(fee).to_wix()},
                            "priceAfterTax":  {"amount": Money(fee + gst).to_wix()}}]
Money.from_wix(sent["appliedDiscounts"][0]["coupon"]["amount"]["amount"]).paise \
    == Money.from_wix(cart["priceSummary"]["discount"]["amount"]).paise

# OUTPUT Wix computed, which is the only place a total may be asserted
Money.from_wix(returned["priceSummary"]["total"]["amount"]).paise \
    == quote.total_payable_paise == verifiedCapturedPaise + giftCardRedeemedPaise
```

and add the sentence the read-only flag forces: *"Because `priceSummary` is read-only, the
invariant holds only if the line items, `appliedDiscounts` and `additionalFees` we send
reproduce the Wix cart exactly. Test 48 therefore asserts the response, and a second assertion
pins `returned.priceSummary.subtotal == cart.priceSummary.subtotal`, because a line-item
mismatch is the one way Wix's computed total can disagree with ours."*

The "unverified" note should become a measurement with its citation, since it now is one.

### HIGH-3 — the key schema cannot answer the existence checks both designs' refusal rules depend on

Both tables are declared as a **single partition attribute with no sort key**, with
`dynamodb:Scan` explicitly denied in both IAM specs, and with a sparse `status-index` whose hash
key is `status` (card/definition rows only).

Several load-bearing rules require finding rows by **key prefix**, which that schema cannot do:

| Rule | Where | Needs |
|---|---|---|
| `/v1/redeem` refuses "whenever any `GCHOLD#<codeHash>#*` or `GCORDER#<codeHash>#*` row exists for that card" | gift cards §3.4, §7.4, §7.6 | prefix scan over `giftCardKey` |
| "hold expiry handles the abandoned case" / `test_a_hold_past_its_expiry_does_not_block_another_purchase` | gift cards §3.4, test 58 | finding a hold without knowing its `paymentAttemptId` |
| `validate` verdict `HELD_BY_ANOTHER_CART` | coupons §5.1, §4.3 | finding `COUPONHOLD#<codeUpper>#*` for a *different* `cartId` |
| `test_a_hold_past_its_expiry_does_not_block_another_cart` | coupons test 18 | the same |

A DynamoDB `Query` needs partition-key equality, and these are different partition keys. With no
sort key and no `Scan`, there is no implementation. The documents justify the shape as "the same
shape `order_keys` uses" — but `order_keys` contains **zero** `query` calls and reads only by
exact key (verified: no `.query(`, no `KeyConditionExpression`, no `begins_with` anywhere in
`order_keys.py`), which is precisely why that shape works there and not here.

This also removes the safety argument in §3.4 for keying the claim on `paymentAttemptId`: "the
hold refuses it" is what makes a *retry* safe, and the hold cannot be found.

**Concrete fix — pick one and name it.** The cheapest consistent option keeps the schema and
moves the existence fact onto the row that already has a known key:

```
GIFTCARD#<codeHash>   +=  activeHoldAttemptId (S), activeHoldPaise (N), activeHoldExpiresAtMs (N)
COUPON#<codeUpper>    +=  activeHoldCartId (S),    activeHoldExpiresAtMs (N)
```

`hold()` becomes one conditional `UpdateItem` on the card/definition row:

```
ConditionExpression = "attribute_not_exists(activeHoldAttemptId)
                       OR activeHoldAttemptId = :me
                       OR activeHoldExpiresAtMs < :now"
```

which makes "is this card held" a single `GetItem` by exact key, makes expiry evaluable, and
keeps one writer serialising on the database. The `GCHOLD#`/`COUPONHOLD#` rows may stay as the
audit record. The alternative — adding a sort key, or a GSI on `codeHash` — is also fine but is a
different table definition and must be written into §6 / §4 rather than left implicit.

### HIGH-4 — `redeemCap` is defined twice, differently, and the second definition reintroduces the exact defect HIGH-4 of the previous review raised

`gift-cards-service-plugin-20261001.md` §4.1 resolves the previous review's HIGH-4 by capping
against the **Wix collection total**:

```
redeemCap = min(balancePaise, wixCollectionPaise - RAZORPAY_MIN_LEG_PAISE)
```

§7.5 — the validation table a coder implements input checking from — says:

> `requestedRedeemPaise` | integer paise, `0 < v ≤ redeemCap` where
> `redeemCap = min(balance, payable - 100)`

`payable` is `quote.total_payable_paise`, which exceeds `wixCollectionPaise` by the convenience
fee and its GST. So §7.5 admits a redemption above what Wix can apply, §4.2 identity 1 then
fails, and the checkout refuses after the request has already reached Wix — the failure mode
§4.1 says it removed. §12.2 item 4 and the §7.6 invariant table both agree with §4.1, so §7.5 is
the single stale copy, and it is the one in the validation table.

**Concrete fix.** In §7.5 replace the parenthetical with the §4.1 definition verbatim, and
define it once in the module rather than twice in prose:

```python
# gift_card_store.py -- ONE definition, imported by both the validator and the split
def redeem_cap(*, balance_paise: int, wix_collection_paise: int) -> int:
    """The gift card funds the SUPPLY only (section 4.1). Never the convenience fee."""
    return min(balance_paise, wix_collection_paise - RAZORPAY_MIN_LEG_PAISE)
```

and add a test asserting the validator and the split call the same function, so the two cannot
drift again.

### HIGH-5 — SEAM-C3b / SEAM-G9's `_SIMULATED_ACTIONS` change makes `provision_checkout.py --verify` fail, and test 52b asserts a verdict the script cannot express

Both documents instruct extending `scripts/provision_checkout.py`'s `_SIMULATED_ACTIONS` with
`dynamodb:DeleteItem`, and the coupon document calls the resulting deny on the existing tables "a
feature", pinned by test 52b.

Measured, the script cannot carry that:

```python
scripts/provision_checkout.py:812   for item in result.get("EvaluationResults", []):
                                        verdicts.setdefault(item["EvalActionName"], set()).add(
                                            item["EvalDecision"])
...
        decision = "allowed" if decisions == {"allowed"} else "/".join(sorted(decisions))
        ...
        elif decision != "allowed":
            note = "  <-- GRANTED BY THE INLINE POLICY BUT DENIED IN SIMULATION"
            problems.append(...)
```

Two consequences:

1. Verdicts are aggregated **per action across every resource ARN**, so a `DeleteItem` that is
   allowed on `CouponsTable` and implicitly denied on `PaymentAttemptsTable` collapses to
   `{"allowed","implicitDeny"}` → `decision != "allowed"` → a problem is appended → `verify()`
   returns non-zero. The provisioner's own gate would fail on a correctly provisioned role.
2. Test 52b ("`DeleteItem` is still **denied** on `PaymentAttemptsTable` and `WixOrderIds`")
   asserts a **per-resource** verdict the script never retains.

The script's docstring is explicit that this matters: *"An unmeasured verdict is a problem too,
not a pass."*

**Concrete fix.** Make the seam three parts, not two, and specify the expectation table:

```python
# scripts/provision_checkout.py
_SIMULATED_ACTIONS = ("dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem",
                      "dynamodb:ConditionCheckItem", "dynamodb:DeleteItem")

#: (action, table) pairs whose EXPECTED verdict is denied. A deny here is the policy working.
_EXPECTED_DENY = {("dynamodb:DeleteItem", PAYMENT_ATTEMPTS_TABLE),
                  ("dynamodb:DeleteItem", COMMERCE_KEYS_TABLE)}
```

and change the verdict loop to key on `(EvalActionName, EvalResourceName)` rather than on the
action alone, reporting a problem only when a pair is denied and *not* in `_EXPECTED_DENY`, or
allowed and *in* it. Tests 52a/52b/107a then assert against a structure that exists.

### HIGH-6 — the `GC_VOIDED` write has no path from a `transactionId` to a `paymentAttemptId`

§8.4 assigns the `GC_VOIDED` stage write to `wecare-wix-giftcard-spi`, §10.1 grants that role
`dynamodb:UpdateItem` on `PaymentAttemptsTable` for exactly that purpose, and `advance()`'s
signature is `advance(attempts, *, attempt_id, stage, **evidence)`.

But `VoidRequest` carries only `transactionId` (verified against the live schema:
`{appInstanceId, transactionId, locationId}` — no `code`, no `orderId`), and the rows that
resolve it do not reach an attempt id:

- §6.3: `GCTXNID#<transactionId>` → **`codeHash`** only.
- §6.5: `GCTXN#<codeHash>#<transactionId>` carries `transactionId, kind, amountPaise,
  balanceAfterPaise, **referenceId**, wixOrderId, voidedBy, createdAt, source` — `referenceId`
  is revision 2's key, left in place after §3.4 re-keyed everything to `paymentAttemptId`, and
  there is no `paymentAttemptId` attribute anywhere on the transaction path.

So the void handler can decrement/restore a balance but cannot write the stage the design says
it writes, and the IAM grant is for an unreachable call. Reaching it by prefix-scanning
`GCORDER#<codeHash>#*` is barred by HIGH-3.

**Concrete fix.** Add the attempt id to both the transaction row and the pointer row, which costs
one attribute each and removes the join:

```
GCTXN#<codeHash>#<transactionId>   += paymentAttemptId (S)      # the purchase it belongs to
GCTXNID#<transactionId>             -> {codeHash, paymentAttemptId}
```

and replace `referenceId` on `GCTXN#` with "`referenceId` (correlation only, never a key)" so the
re-key of §3.4 is complete rather than partial. Add a test: a void that arrives with only a
`transactionId` resolves both the card and the attempt, and writes `GC_VOIDED` through
`advance()`.

---

## MEDIUM

### MEDIUM-1 — SEAM-G13's added parameter has no specified source at the only call site

SEAM-G13 changes `finalization.record_paid` to take `captured_paise` and write
`verifiedCapturedPaise`. Measured, `record_paid` has exactly one caller:

```python
finalization.py:50   provider_id = outcome.get('providerPaymentId') or attempt.get('verifiedProviderPaymentId')
finalization.py:53   record_paid(attempts, attempt, provider_id)
```

`accept_paid(*, attempts, orders, keys, attempt, outcome)` has no captured-amount field
documented anywhere, in either design document or in `finalization.py`. The entire HIGH-3
resolution of revision 3 — the verified figure that both legs close against — therefore has no
named producer at the point it enters the row.

**Concrete fix.** Name the field and its origin in SEAM-G13:

> `accept_paid`'s `outcome` gains `verifiedCapturedPaise`, written by the caller from the same
> `razorpay_verify` readback that produced `outcome['providerPaymentId']`
> (`website_checkout.py:430`'s `amount_paise`, or the webhook's `provider_paise`). `record_paid`
> refuses a call where `outcome['providerPaymentId']` is present and `verifiedCapturedPaise` is
> absent, because a provider id without its amount is exactly the half-evidenced row §3.2 fails
> closed on.

Add this to §11's fallback table too: if the payment-integrity workstream names it differently,
the accessor is one constant.

### MEDIUM-2 — the website split table covers 5 of 18 `amount_paise` sites in `website_checkout.py`

§8.1's table is the right instrument and is five rows: `create_order`, `bind_gateway_order`, the
request-key `extra`, `payment_attempt.build`, `razorpayChargedPaise`. Measured, `amount_paise`
appears **18** times in that module, and three unlisted consumers are load-bearing:

```
website_checkout.py:289   _browser_options(..., amount_paise=amount_paise, ...)   -> line 145 "amountPaise" to the BROWSER
website_checkout.py:239   _recover_ambiguous_create(..., amount_paise=amount_paise, ...)
website_checkout.py:344   (inside _recover_ambiguous_create) reserve/bind on the recovered order
website_checkout.py:302   _ready_from_binding(..., amount_paise=int(binding.get("amountPaise") or 0))
```

A coder who implements the split by reassigning the local `amount_paise` satisfies the five rows
and silently changes the other three; a coder who introduces `pay_now_paise` alongside has to
decide each of the three unaided. Both resolutions are exactly the class §8.1 exists to
foreclose.

**Concrete fix.** Add three rows:

| Site | Carries | Why |
|---|---|---|
| `_browser_options` (289 → 145) | `payNowPaise` | it is what the browser presents and what must match the gateway order |
| `_recover_ambiguous_create` (239, 344) | `payNowPaise` | it reconciles against an order created for the charged figure |
| `_ready_from_binding` (302) | reads the binding, so `payNowPaise` by construction — **no change** | stated so its absence is deliberate |

and extend test 112 to assert `options["amountPaise"] == payNowPaise`.

### MEDIUM-3 — there is a fourth attempt producer, and the document says there are three "measured"

§8 opens: "**There are THREE attempt producers in this tree, not one (closes HIGH-1).**"
Measured, there are four:

```
amplify/functions/ecommerce/checkout/handler.py:519                  payment_attempt.build(
amplify/functions/shared/lambda_utils/ecommerce/website_checkout.py:279  payment_attempt.build(
amplify/functions/shared/lambda_utils/ecommerce/initiation.py:63         payment_attempt.build(
amplify/functions/shared/lambda_utils/ecommerce/blog_contribution.py:355 payment_attempt.build(
```

`blog_contribution.py`'s own docstring says it "mirrors `website_checkout.prepare_checkout`" and
is "a sibling of website_checkout". Given that revision 3's largest finding was a missed
producer, an enumeration that is still short by one — and labelled "Measured" — is the same
defect one instance smaller.

**Concrete fix.** Add a fourth row to §8's table and a short §8.5 in the shape of §8.3: declare
`blog_contribution.prepare_contribution` **out of scope** (it is a contribution flow with no Wix
cart, so no `wixCollectionPaise` exists to cap a redemption against), and extend test 113 to
assert it writes no gift-card attribute either — the same pin, for the same reason.

### MEDIUM-4 — the `Content-Type` allowlist is a fail-closed gate on an undocumented value, and its citation points at a different endpoint

§5 requires: "Reject unless `Content-Type` is one of `application/jwt`, `text/plain`,
`plain/text`", and §7.4/§7.5 make that a 401 with an empty body.

The evidence offered is the introduction article's `curl` with `Content-Type: plain/text`.
Measured on that page, that example is the **app-install instance-id callback**
(`POST https://ext-server.com/wix-spi/account-ids`, "Wix will send a JSON Web Token (JWT) with an
instance ID to your deployment URI"), not a `Get Balance` / `Redeem` / `Void` call — and
`plain/text` occurs exactly once on the page, in that one example. The self-managed REST guide,
re-fetched and read in full, documents the envelope and the five claim checks and says **nothing**
about `Content-Type`.

So the token-is-the-body conclusion is well supported ("the request payload is a signed JWT",
"The payload that your endpoint receives is in JSON web token (JWT) format"), but the header
allowlist is an inference from an unrelated endpoint. If Wix sends `application/json` — plausible,
given the envelope is JSON — the verifier 401s every live call. Fail-closed, but feature-dead on
an undocumented value, and §5's own framing ("Wix documents exactly one model, and it is
implemented verbatim") would be false.

**Concrete fix.** Drop the rejection and keep the parse:

> The `Content-Type` header is **not** a gate. The body is parsed as a JWT regardless of the
> declared type; a body that is not three base64url segments is rejected at step 1, which is the
> check that actually discriminates. `isBase64Encoded` is still honoured first. An
> `Authorization` header is still ignored entirely (test 4).

and move the header question to owner item 12.1.4, beside the `alg`: *"while you have a real
token, record the request's `Content-Type`"*. Correct the citation to say the `plain/text`
example is the install callback, which is honest about how strong the evidence is.

### MEDIUM-5 — two hold producers, and the IAM permits only one

§7.2 exposes `POST /gift-cards/hold` ("customer session", "Takes `GCHOLD#`, returns a hold
token") on `wecare-gift-cards`. §8.4 attributes every `GC_HELD` write to the *checkout* function,
and §10.1 gives `wecare-gift-cards-role` **no** `UpdateItem` on `PaymentAttemptsTable`.

So either the customer route takes a hold without writing the `GC_HELD` stage — in which case
`giftCardRequiredPaise` and `giftCardCodeHash` are never written and `is_fully_settled` reads
`required == 0` on a gift-card order, marking it fully settled on the Razorpay leg alone, the one
failure DECISION 3 exists to prevent — or it writes the stage and is denied by IAM. There is a
third problem underneath: a customer session has no `paymentAttemptId` before checkout mints one,
and `GCHOLD#` is keyed on it (§3.4).

**Concrete fix.** Choose one and delete the other. The coherent choice:

> `POST /gift-cards/hold` and `POST /gift-cards/release` are **removed**. The hold is taken only
> by the checkout producer, inside the request that mints the `paymentAttemptId` (SEAM-G4 /
> SEAM-G14), because the hold key does not exist before then. The customer-facing surface is
> `POST /gift-cards/balance` only, which reads and reserves nothing.

Then §7.2 is five routes, `wecare-gift-cards-role` keeps no `PaymentAttemptsTable` access, and
test 45's route enumeration pins it.

### MEDIUM-6 — `commit_redemption`'s signature cannot delete the hold it is specified to delete

`coupons-20261001.md` §5.2: "`coupon_store.commit_redemption(table, *, code, order_id,
customer_id)` ... performs the conditional `COUPONREDEEM#` put, then the two atomic `ADD`s ...
**then deletes the hold**."

The hold key is `COUPONHOLD#<codeUpper>#<cartId>` (§4.1) and `cart_id` is not a parameter. §6
grants `DeleteItem` "solely for releasing a `COUPONHOLD#` row", so the permission exists for a
call that cannot be composed.

**Concrete fix.** Either add the parameter:

```python
commit_redemption(table, *, code, order_id, customer_id, cart_id)
```

(the finalizer has it — `attempt['purchasedSnapshot']['cart']` is asserted present in
`accept_paid` before this point), or record the cart id on the `COUPONREDEEM#` claim at hold time
and read it back. Say which; the first is one argument and no extra read.

### MEDIUM-7 — test 80 asserts an ordering §3.4 proves impossible

Test 80 is `test_the_hold_is_taken_after_the_reference_is_minted_and_before_the_gateway`. §3.4
establishes that on the website path `attempt["referenceId"]` **is** the Razorpay gateway order
id, so "after the reference is minted and before the gateway" is unsatisfiable there — it is
revision 2's ordering, left in the test list after the re-key. Tests 49, 50 and 53 carry the same
stale vocabulary ("for the same reference", "two different references") for a claim now keyed on
`paymentAttemptId`.

**Concrete fix.** Rename to the property that is actually true on both producers:

- 80 → `test_the_hold_is_taken_after_the_attempt_id_is_minted_and_before_the_gateway`
- 49 → `test_a_second_redeem_for_the_same_payment_attempt_returns_the_same_transaction_id`
- 50 → `test_a_second_redeem_for_the_same_payment_attempt_does_not_move_the_balance`
- 53 → `test_two_different_payment_attempts_each_deduct_once`

### MEDIUM-8 — `AdditionalFee.price` is a documented field and the fee payload omits it

§2.3 and SEAM-G6 build the convenience fee as `{"code", "name", "priceBeforeTax",
"priceAfterTax"}`. Measured, the schema's own field list leads with

```
"price": {"description":"Additional fee's price.", "$ref": ".../platform_common.api.Price"}
```

and `PriceSummary.totalAdditionalFees` is what Wix sums into its (read-only, per HIGH-2) total.
Whether Wix derives `totalAdditionalFees` from `price` or from `priceAfterTax` is not documented
on the page, and omitting `price` is therefore the most likely way for the HIGH-2 identity to
come back short by exactly the fee.

**Concrete fix.** Send all three, state the values, and assert the readback:

```python
{"code": "WD-CONVENIENCE", "name": "Convenience fee",
 "price":          {"amount": Money(fee + gst).to_wix()},
 "priceBeforeTax": {"amount": Money(fee).to_wix()},
 "priceAfterTax":  {"amount": Money(fee + gst).to_wix()}}
```

and add to test 48: `Money.from_wix(returned["priceSummary"]["totalAdditionalFees"]["amount"]).paise
== quote.convenience_fee_paise + quote.convenience_gst_paise`. Note `name` is `maxLength 50` and
`code` `maxLength 100`, both satisfied.

---

## NIT

### NIT-1 — the HEAD both documents measure against is stale

Both §3.1 / §11 say "Re-measured at HEAD `ae1e11b5`". Actual HEAD is `c6fd53dc`
(2026-10-02 08:08 +0530). The `git status --short` output quoted in both documents still matches
the tree exactly, and `cart_v2.py` / `customer_cart.py` / `checkout/handler.py` are still clean,
so every conclusion survives — only the commit id is wrong. Update it, or cite the date instead
of the id.

### NIT-2 — line-number drift in otherwise exact citations

Measured against the tree: `wix_ecom.py` HTTPError raise is **108** (cited 106);
`_SIMULATED_ACTIONS` is **662** (cited 661); `wix_writeback` `existing = ...resolve` is **256**
and the raise **259** (cited 255/258); the cart-test body literal is **91** and `set(body)` is
**160** (cited 90/148); `website_checkout`'s `attempt_id` mint is **199** (cited 198). Also
`razorpay-webhook/handler.py`'s `provider_paise != intent_paise` is at **952**, not 947, and it
is the **partner wallet top-up** path rather than a checkout path — worth saying, since §3.2
offers it as one of the only two amount verifications in the tree.

### NIT-3 — `wecare-gift-cards`' `provisioned_by` omits its route provisioner

The registry entry quoted in `coupons-20261001.md` §8 lists
`provision_gift_cards_table.py && provision_gift_cards_roles.py`, while §12.3 step 3 says
`provision_gift_card_spi_routes.py` creates "the three SPI routes plus our own seven". The coupon
entry does include its route script. Align the two, and consider renaming the script, since a
file called `provision_gift_card_spi_routes.py` creating seven non-SPI routes is a name that will
mislead.

### NIT-4 — `CreateCartRequest.giftCards` is `maxItems: 5` in the live schema

Both documents quote the Cart V2 introduction's "a single coupon and a single gift card at a
time". Measured on the Add Coupon page's embedded schema, `CreateCartRequest.coupons` is
`maxItems: 1` but `CreateCartRequest.giftCards` is **`maxItems: 5`**. Enforcing one is still the
right call and §4.3 is not wrong about the payment summary — but recording the discrepancy stops
a later reader concluding the document misread the page.

### NIT-5 — the per-customer condition expression is undefined when there is no per-customer limit

§4.3 gives `ConditionExpression: attribute_not_exists(uses) OR uses < :limitPerCustomer`, and
§4.2 marks `limitPerCustomer` optional. Say what happens when it is absent — the natural answer
is "no `COUPONUSE#` condition is applied, and the row is still incremented for audit" — so the
expression is not built from a missing value.

### NIT-6 — finding ids are reused across revisions with different meanings

`MEDIUM-10`, `MEDIUM-11`, `MEDIUM-13`, `MEDIUM-17` and `HIGH-1`…`HIGH-6` each denote one thing in
the revision-2 response table and a different thing in the revision-3 table, within the same
section of the same file. It is already hard to audit at three revisions. Prefix them (`R2-H1`,
`R3-H1`) from here.

---

## Verified assumptions

Confirmed by direct measurement. These are no longer assumptions.

**Wix contracts (fetched live 2026-10-02; the docs host 404s on a bogus slug, so a 200 means the
page exists):**

1. `Add Coupon`'s request body really is `{"coupon": {"code": ...}}` — the page's own documented
   `curl` sends `{"coupon": {"code": "FREESHIP"}}`, and the schema's `required` array is
   `["cartId","coupon","coupon.code"]`. The repo's `cart_v2.py:333` sends `{"couponCode": ...}`.
   SEAM-C1 is real and is correctly listed first.
2. `CouponInput.code` is `minLength 1, maxLength 50`; the live adapter refuses only above 100
   (`cart_v2.py:329`). NIT-20's fold into SEAM-C1 is correct.
3. `RemoveCouponRequest.required` is `["cartId","couponId"]`; `GiftCardInput.code` is
   `minLength 8, maxLength 20`; `AddGiftCardRequest.required` is
   `["cartId","giftCard","giftCard.code"]`.
4. `Create Coupon` lives at `/stores/v2/coupons`, declares `"responses": {"200": ...}` and
   `"errors": []` — **no documented failure of any kind**. §5.3.1's withdrawal of
   `WIX_CODE_CONFLICT` as a create-failure outcome is correctly reasoned.
5. `moneyOffAmount`, `percentOffRate` and `fixedPriceAmount` are JSON `number` with no wrapper;
   `minimumSubtotal` is `number`/`double` via `google.protobuf.DoubleValue`; `startTime` is
   `type: string, format: int64, minimum: 1000000000000`. The whole-rupee-`int` resolution in §4.2
   is sound, and the string/number asymmetry is real.
6. SPI: `GetBalanceResponse.balance`, `RedeemRequest.amount`, `RedeemResponse.remainingBalance`
   and `VoidResponse.remainingBalance` are all `type: number, minimum 0, maximum 999999999.99`;
   `code` is 8–20; `transactionId` is 1–100; `VoidRequest` carries **no** `code`;
   `GiftCardProviderConfig` has exactly one property, `deploymentUri`, with the documented
   example `https://my-gift-cards.com/`. The `99_999_999_999` paise ceiling (MEDIUM-14) is right.
7. All three SPI methods declare **only** a `200` response and no error schema; `ALREADY_VOIDED`
   appears only as an `x-wix-docs.errors[]` annotation. §1.1.1's "there is nothing to cite" is a
   correct measurement, not an evasion.
8. The SPI auth model is Wix's own, verbatim: *"Verify the JWT signature using your public key
   from your app's dashboard. Verify that the `aud` claim matches your application ID. Verify that
   the `iss` claim is set to `wix.com`. Verify that the `iat` claim is set to a timestamp before
   the current timestamp... `exp`... after..."* plus *"use a standard library"*. Nothing in §5 is
   invented. (The `Content-Type` gate is the one exception — MEDIUM-4.)
9. `Create Order` accepts `additionalFees` (maxItems 100) and `appliedDiscounts` (maxItems 320) as
   inputs; `AdditionalFee` has `code` (≤100), `name` (≤50), `price`, `priceBeforeTax`,
   `priceAfterTax`, `lineItemIds`, `providerAppId`.

**Repository facts:**

10. `Money.from_wix` requires a `str` matching `[0-9]{1,14}(?:\.[0-9]{1,2})?` and `to_wix`
    renders `paise//100 . paise%100`; the `9007199254740991` ceiling is `money.py`'s.
11. `cart_v2.calculate` enforces `subtotal - discount + delivery + additionalFees + tax == total`
    and returns `"cart": deepcopy(cart)` plus `"summary"`, so coupon/gift-card ids *are* in the
    return value but not on the payable projection — NIT-19's correction is right.
12. `cart_v2.calculate` refuses `giftCards`, `memberships` and `subscriptionCharges` in one
    `any(...)` check and then requires `payNow == totalAfterGiftCards == total`; its comment names
    the three conditions §2/§3/§4.4 answer, including the GSTIN `19AAFFW7196L1Z8`. SEAM-G1's
    required change is stated accurately.
13. `checkout_pricing`: `CONVENIENCE_FEE_BPS = 250`, `CONVENIENCE_GST_BPS = 1800`,
    `RATE_DENOMINATOR = 10000`, `SELLER_GSTIN = "19AAFFW7196L1Z8"`, `round_half_up` over
    `Decimal`. §2's worked example (100000 → 2500 → 450 → 102950) is arithmetically correct, and
    the "wrong version" (1574/283) is correctly computed too.
14. `payment_status`: string values plus a separate `STATUS_RANK` with `AUTHORIZED: 30`,
    `CAPTURED: 50`, `REFUNDED: 60`, and `rank()` returning `.get(..., 0)`. §3.1's ladder mirrors it
    faithfully, and `GC_VOIDED > GC_REDEEMED` has the precedent claimed.
15. `payment_attempt.ORDER_ELIGIBLE_STATES == frozenset({PAYMENT_PAID})`, so
    `may_create_order` is exactly what §3.2 says.
16. `finalization.record_paid` writes `verifiedProviderPaymentId` in one conditional
    `UpdateExpression` (lines 19–26) — SEAM-G13's insertion point is real. `accept_paid` passes
    `amount_paise=int(attempt['amountPaise'])` to `record_external_payment` (lines 89–91), so
    MEDIUM-15's "overstated payment" direction is correct.
17. `accept_paid` has **zero** callers in `amplify/` (one in a `.scratch` backup only);
    `finalization.py` and `initiation.py` are untracked; `website_checkout.prepare_checkout` has
    no caller outside tests. All three claims hold.
18. `website_checkout.py` lines 192/193/203/231/265/281/407/430/434/436 are as quoted;
    `intent_fingerprint` (line 108) hashes `total_payable_paise`, so §8.1's "unaffected" is right.
19. `side_effect_guard.KNOWN_EFFECTS` is a 5-member `frozenset` validated by `claim`, and
    `wix_writeback` lines 253/256/259/283/287 are as described, including the hard-coded
    `paymentMethodName: "Razorpay via WhatsApp"`. SEAM-G7's three-part shape is correct.
20. `scripts/check_data_model_drift.py` has `UNDECLARED_ALLOWED` (line 152) and
    `undeclared_tables_unexpected`; `amplify/data/resource.ts` declares `PaymentAttempt` (line
    1044) and no `Coupon`/`GiftCard`. MEDIUM-12's correction is right.
21. `deploy_all_lambdas.Spec(name, source, *, standalone, extra_dirs, extra_files,
    provisioned_by)` — the three quoted entries are syntactically valid, and the
    `provisioned_by` rationale quoted from the file ("A counter that is never zero is not a
    signal") is verbatim.
22. `tests/test_payment_vocabulary_at_decision_points.py`: `CONSULTING_FILES` has 6 entries,
    `FORBIDDEN_RAW == {"captured"}`, and `test_no_decision_compares_a_payment_word_raw` never
    uses its `alias` parameter — so the `RAW_SCAN_ONLY_FILES` split in §9 works as written,
    including the `(path, None)` tuples.
23. `order_keys` contains no `query`, no `KeyConditionExpression` and no `begins_with` — it is
    exact-key-only, which is why its shape is cited and why HIGH-3 matters.
24. `arn:aws:lambda:us-east-1:775261844268:layer:cryptography-python312:1` exists, is at version
    1, is `python3.12`-compatible, and is attached to `wecare-whatsapp-business-api`. The account
    has exactly one HTTP API, `zllr9lrg7j` (`wecare-digital-api`).
25. `lambda_utils/rate_limit.py`, `identifiers.new_uuid7`, `customer_auth` and `response` all
    exist as referenced; `purchase_intent.apply_coupon` exists (line 86) and `build_intent`
    defaults `quote_fn=compute_quote` (line 124); `checkout/handler.py` mints `attempt_id` at 496
    **before** `allocate_payment_reference` at 512, so §8.2's ordering claim holds.

## Unverified or wrong assumptions

1. **WRONG — `Order.priceSummary` is read-only.** §2.3 lists this as "unverified"; the cited page
   documents `"readOnly": true`. See HIGH-2.
2. **WRONG — "option (b) is rejected" while identity 1 requires option (b)'s field.** See HIGH-1.
3. **WRONG — "THREE attempt producers... Measured".** There are four. See MEDIUM-3.
4. **WRONG — `redeemCap` in §7.5.** Contradicts §4.1. See HIGH-4.
5. **WRONG — the existence checks are implementable on the stated key schema.** They are not. See
   HIGH-3.
6. **WRONG — extending `_SIMULATED_ACTIONS` is safe and test 52b is writable.** Neither. See
   HIGH-5.
7. **MISATTRIBUTED — the `Content-Type: plain/text` curl.** It is the app-install instance-id
   callback, not an SPI method call. See MEDIUM-4.
8. **UNVERIFIED (correctly flagged, still open) — whether Wix attributes `limitPerCustomer` for a
   cart created under an admin identity.** Nothing on any fetched page says. The local-enforcement
   decision is the right response.
9. **UNVERIFIED (correctly flagged) — the whole SPI is Developer Preview.** `maturity: BETA`
   appears 15 times on each of the Redeem and Void pages; the contract must be re-measured before
   registration.
10. **UNVERIFIED — which signing algorithm Wix uses.** Not named on any fetched page. The
    RS256/384/512 allowlist with `alg: none` and HMAC refused is the correct fail-closed position,
    and owner item 12.1.4 is the right place to narrow it.
11. **UNVERIFIED — the introduction's "Required: Yes" handler table.** Rendered client-side; not
    present in the fetched HTML. Plausible and not safety-critical, but it is a quotation from a
    table I could not read.
12. **UNVERIFIED — whether Wix's computed `totalAdditionalFees` derives from `price` or
    `priceAfterTax`.** See MEDIUM-8; the fix is to send all three and assert the readback.
13. **UNVERIFIED — Razorpay's 100-paise minimum.** `https://razorpay.com/docs/api/orders/create/`
    returns 200 and the quotation is plausible, but the page renders its error table
    client-side, so I confirmed the citation resolves rather than the sentence. §12.2.3's
    "re-confirm before go-live" is the right posture.
14. **UNVERIFIED — the Wix API key's scopes include `Manage Coupons` (`COUPONS.MANAGE`).**
    Correctly raised as owner item 2; nothing in the repo records the key's scopes, and I did not
    read the secret.
