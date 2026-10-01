# Wix eCommerce V1 → Cart V2 migration and V1 retirement — implementation plan

**Written** 2026-10-01 · **Branch** `stack` at `059d2ffb2d51d7b231376109d85885a55a8aa67b`
(= `origin/stack` at the time of writing; re-derive with `git rev-parse origin/stack`)
**Python** `./.venv/bin/python` — bare `python` is not on PATH.
**Baseline measured before planning:** `./.venv/bin/python -m pytest -q` → **6001 passed,
1 skipped, 53s**. `node scripts/check-versions.ts` → exit 0, `RESULT: no error findings`
(Node v24.21.0, native type stripping, no build step).

No code is written by this document. It plans; a later step implements.

---

## 0. The scope correction you have to read first

The instruction is "migrate all 16 `/ecom/v1` call sites to their Cart V2 equivalents".
**Fourteen of the sixteen have no Cart V2 equivalent, and Wix has not announced them for
removal.** This is not a reason to defer anything; it is a reason the retirement is much
smaller and much safer than a 16-site count suggests. Measured, per line, below.

`/ecom/v1` is not one API. It is the version prefix shared by six separate Wix eCommerce
APIs. Only **two** of them — eCommerce Cart and eCommerce Checkout — are in the
2027-02-01 removal:

> Cart V2 replaces the eCommerce Cart and eCommerce Checkout APIs, combining them into one
> Cart entity; those two APIs are removed on February 1, 2027.
> — paraphrased from [Cart V2: Introduction](https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/introduction)

The other four — **Orders**, **Order Transactions**, **Order Fulfillments** (and the
Draft Orders / Order Billing / Order Payment Requests siblings this repo does not call) —
are current, carry no deprecation notice, and are **not** in the Cart V2 migration
mapping at all. Their own reference pages list them as live capabilities:
[About Orders](https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/orders/introduction),
[Orders API](https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/orders/orders/introduction),
[Order Transactions API](https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/orders/order-transactions/introduction)
(last updated 30 September 2026),
[Order Fulfillments API](https://dev.wix.com/docs/rest/business-solutions/e-commerce/order-fulfillments/introduction).

So:

| Family | amplify call sites | In the 2027-02-01 removal? | Action |
|---|---:|---|---|
| **Checkout V1** (`/ecom/v1/checkouts…`) | **2** | **Yes** | migrate to Cart V2, then retire |
| Orders API (`/ecom/v1/orders…`) | 7 | No | **leave exactly as they are** |
| Order Transactions (`/ecom/v1/transactions…`, `…/add-payment`) | 5 | No | **leave** |
| Order Fulfillments (`/ecom/v1/fulfillments…`) | 2 | No | **leave** |
| | **16** | | |

Repo-wide, counting outside `amplify/`, there is **one more** genuine Cart V1 call:
`scripts/probe_wix_capabilities.py:170` probes `GET /ecom/v1/carts/current`. That makes
**3 real Cart/Checkout V1 call sites in the whole repository**, not 16.

**Why this matters rather than being pedantry.** "Migrating" `POST /ecom/v1/orders/search`
to Cart V2 is not possible — Cart V2 has no order search — so an implementer told to
migrate all 16 would either invent an equivalence or break staff order management
(`wecare-wix-store`'s orders list, order detail, transactions, fulfilments and the WD
order-number PATCH), which is live on `live` alias **v31** and working. The Orders family
staying at v1 is Wix's current design, not this repo's debt.

`docs/compatibility.md:113` currently claims Cart/Checkout is **absent** — "zero
occurrences of `/ecom/v1/carts`, `/ecom/v1/checkouts`". That is **false** and is corrected
by item 9 below.

---

## 1. Live state, measured 2026-10-01 (account 775261844268, us-east-1)

Re-derive before implementing; other sessions deploy.

| Thing | Measured value |
|---|---|
| HTTP API | `zllr9lrg7j`, **362** routes |
| Relevant routes | `POST /ecommerce/checkout`, `POST /ecommerce/checkout/status`, `POST /ecommerce/customer-session`, `GET|POST /wix-store/{proxy+}` |
| `wecare-wix-store` | exists, `live` → **v31**, python3.12, 10 env keys |
| `wecare-wix-store` → `WIX_CART_V2_ENABLED` | **ABSENT** |
| `wecare-checkout` | exists, `live` → **v2**, last modified 2026-10-01 13:49 |
| `wecare-checkout` → `CHECKOUT_INITIATION_ENABLED` | **ABSENT** |
| `wecare-checkout` → `EXPECTED_CONFIGURATION_NAME` | present, **empty string** |
| `wecare-checkout` → `EXPECTED_PROVIDER_MID` | present, **empty string** |
| `wecare-checkout` → `WIX_WRITEBACK_ENABLED` / `WIX_ECOM_WRITE_CONFIRMED` / `WIX_CART_V2_WRITE_CONTRACT` | all **ABSENT** |
| Fleet sweep for all five gate flags (`WIX_CART_V2_ENABLED`, `CHECKOUT_INITIATION_ENABLED`, `WIX_WRITEBACK_ENABLED`, `WIX_ECOM_WRITE_CONFIRMED`, `WIX_CART_V2_WRITE_CONTRACT`) | **68 functions enumerated, 68 configs read, 0 errors — not one of the five is set on any function** |

The fleet count is **68**, not the 65 recorded in `.kiro/steering/lambda-snapstart-deploy.md`.
Treat that steering number as a dated snapshot, as it instructs.

### 1.1 The outage framing needs correcting in both directions

The scope note says deleting V1 while the gate is unset would be "a total outage". The
measured state says something more precise, and it cuts both ways.

**There is no payable V1 checkout flow to lose.** `EXPECTED_CONFIGURATION_NAME` and
`EXPECTED_PROVIDER_MID` are both the **empty string**, which `payment_readiness.evaluate`
deliberately treats as `CONFIGURATION_UNVERIFIED` (`ecommerce/checkout/handler.py:115-119`
documents that there is no safe default that reads as ready), and
`CHECKOUT_INITIATION_ENABLED` is absent so `_create` returns
`PAYMENT_INITIATION_DISABLED`. Nothing can be paid for today. Deleting V1 with no default
V2 would turn a 409/200-that-cannot-pay into a 500 — a functional regression of an
already-unpayable path, **not lost revenue**.

**But V1 writes to the live Wix site before any gate.** `scripts/provision_checkout.py:903`
records the measured order inside `_create`: `wix_ecom.create_checkout` (**a live Wix
write**) → currency compare → readiness → reference reservation → `put_item` → *then* the
gate refuses. So today an authenticated `POST /ecommerce/checkout` with `lineItems`
**creates a real Checkout V1 entity on the live site** and then declines. Retiring
Checkout V1 therefore *removes* a live write; it does not add one.

Both statements belong in the record because they point the same way: the retirement is
lower-risk than the count suggests, and the thing to be careful about is step 3, not
step 4.

### 1.2 The dependency chain, stated as one chain

1. `WIX_CART_V2_ENABLED` is absent on `wecare-wix-store` → `/wix-store/cart` returns
   `503 CART_UNAVAILABLE` (`wix-store/handler.py:371-372`). Cart V2 is **not** a serving
   path today.
2. `ecommerce/checkout/handler.py` imports `wix_ecom`, not `cart_v2` — so the only
   implemented price authority is Checkout V1.
3. Therefore V1 code cannot be deleted until V2 is the default, and V2 cannot become the
   default until it is tested, **and neither takes effect until `wecare-wix-store` and
   `wecare-checkout` are redeployed and their `live` aliases moved**. That redeploy is the
   owner's action (§7), not this plan's.

A fourth link the scope note does not mention, and it is the binding one: **§3 below shows
Cart V2 cannot currently produce a payable total for this site's catalogue at all.** Steps
3 and 4 are blocked on that, not on the gate.

---

## 2. Per-call-site mapping

Method names and field renames are taken from
[Cart V2: Migration Mapping](https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/migration-mapping)
and [Cart V2: Migration Guide](https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/migration-guide).
Both state that each Checkout V1 method is replaced by a cart method doing the same job,
and that the Checkout V1 id **is** the Cart V2 id, so existing ids can be passed straight
to V2 cart methods.

### 2.1 In scope — Checkout V1 (2 sites, both `lambda_utils/wix_ecom.py`)

| # | Site | V1 method | Cart V2 equivalent | Straight swap? |
|---|---|---|---|---|
| 1 | `wix_ecom.py:153` `POST /ecom/v1/checkouts` via `create_checkout()` | Create Checkout | **Create Cart** | **No — shape change.** `checkoutInfo`→`cart`, `lineItems`→`catalogItems`, top-level `channelType`→`cart.source.channelType` |
| 2 | `wix_ecom.py:211` `GET /ecom/v1/checkouts/{id}` via `get_checkout()` | Get Checkout | **Get Cart** + **Calculate Cart** | **No — one call becomes two.** Totals are no longer stored on the entity |

Site 2 is the important one. In Checkout V1, `priceSummary`, `taxSummary`, `payNow` and
`payLater` live **on** the entity, which is why `wix_ecom.authoritative_total_paise()` can
read `checkout["priceSummary"]["total"]["amount"]`. The mapping marks all four as **not
stored** in V2: you call Calculate Cart and read `summary.priceSummary`. So
`authoritative_total_paise`, `checkout_currency` and `line_item_summary` are all
V1-entity-shaped readers with no V2 counterpart — they are replaced by the snapshot
`cart_v2.CartV2.calculate()` already returns, not ported.

Two more V1→V2 rows matter even though this repo does not call them yet, because D7
names them:

| V1 method | Cart V2 equivalent | Repo position |
|---|---|---|
| Create Order (from checkout) | **Place Order** | **Deliberately NOT used.** Place Order can enter Wix payment collection; `wix_writeback.FORBIDDEN_ENDPOINT_MARKERS` blocks it and `ALLOWED_ENDPOINTS` excludes it |
| Mark Checkout As Completed | **Mark Cart As Completed** | Not called today. Cart V2's own introduction says to use it when an external system created the order — exactly this architecture. New work, gated (item 5) |
| Get Checkout (with refresh) | **Refresh Cart** | Not called today; `calculate(refreshCart=True)` covers the current need |

### 2.2 Not in scope — Orders / Transactions / Fulfillments (14 sites, leave alone)

Every one of these is a current API with no Cart V2 equivalent. **Do not touch.**

| Site | Path | Owning API |
|---|---|---|
| `wix-store/handler.py:719` | `POST /ecom/v1/orders/search` | Orders (Search Orders) |
| `wix-store/handler.py:740` | `GET /ecom/v1/orders/{id}` | Orders (Get Order) |
| `wix-store/handler.py:745` | `GET /ecom/v1/transactions/orders/{id}` | Order Transactions |
| `wix-store/handler.py:753` | `GET /ecom/v1/fulfillments/orders/{id}` | Order Fulfillments |
| `wix-store/handler.py:764` | `GET /ecom/v1/fulfillments/orders/{id}` | Order Fulfillments |
| `wix-store/handler.py:774` | `GET /ecom/v1/transactions/orders/{id}` | Order Transactions |
| `wix-store/handler.py:899` | `POST /ecom/v1/orders/search` | Orders |
| `wix-store/handler.py:916` | `PATCH /ecom/v1/orders/{id}` | Orders (Update Order — WD number into `extendedFields`) |
| `wix-store/handler.py:1477` | `POST /ecom/v1/orders/search` | Orders |
| `wix_writeback.py:60` | `POST /ecom/v1/orders` (`CREATE_ORDER`) | Orders (Create Order) |
| `wix_writeback.py:189` | same, at the call | Orders |
| `wix_writeback.py:64` | `POST /ecom/v1/payments/orders/{orderId}/add-payment` (`ADD_PAYMENT`) | Order Transactions (Add Payments) |
| `wix_writeback.py:208` | same, in the docstring | Order Transactions |
| `wix_writeback.py:239` | same, at the call | Order Transactions |

Create Order being the right call here is explicit in the provider docs: the Orders API
page describes Create Order as the method for recording orders from external systems and
manual sales, with `channelInfo.type` set to the real source (`OTHER_PLATFORM` when
nothing fits). The Order Transactions page states plainly that it records payments and
refunds and does **not** move money — which is the load-bearing property
`wix_writeback`'s R7.4 test asserts.

**Unverified:** the literal path `/ecom/v1/payments/orders/{orderId}/add-payment` could
not be re-confirmed against a fetchable REST reference page (those pages are
client-rendered). It is not exercised live: `wix_writeback.is_enabled()` requires all of
`WIX_WRITEBACK_ENABLED`, `WIX_ECOM_WRITE_CONFIRMED` and
`WIX_CART_V2_WRITE_CONTRACT`, and the fleet sweep above found **none of them set on any of
the 68 functions**; the module's only caller,
`lambda_utils/ecommerce/finalization.py`, is an untracked working-tree file that is not
deployed. So this is debt, not a defect. Re-verify the path before any write-back flag is
ever set.

### 2.3 Also in scope — one Cart V1 probe outside `amplify/`

| Site | Current | Action |
|---|---|---|
| `scripts/probe_wix_capabilities.py:170` `ecomCart` | `GET /ecom/v1/carts/current` | Replace with the Cart V2 Current Cart read, or delete the probe: `ecomCartV2Get` at `:180` already proves the V2 route resolves. Deleting is preferred — one probe per capability |

`scripts/probe_wix_capabilities.py:171` `ecomOrders` (`POST /ecom/v1/orders/search`) is
Orders API. **Leave it.**

### 2.4 Field renames the implementation will need

From the mapping's Checkout V1 → Cart V2 entity table, the ones this repo actually
touches:

| Checkout V1 | Cart V2 |
|---|---|
| `id` | `id` (same value — a V1 checkout id is a V2 cart id) |
| `channelType` | `source.channelType` |
| `currency` | `businessInfo.currencyCode` |
| `completed` | `orderPlaced` |
| `priceSummary` / `taxSummary` / `payNow` / `payLater` | **not stored** → `CalculateCart` → `summary.*` |
| `lineItems[].productName` | `lineItems[].name` (type changes to a translatable string) |
| `lineItems[].quantity` | `lineItems[].quantityInfo.confirmedQuantity` |
| `lineItems[].catalogReference` | `lineItems[].source.catalogReference` |
| `lineItems[].availability.status` | `lineItems[].status` (`AVAILABLE`→`IN_STOCK`, `NOT_FOUND`→`REMOVED_FROM_CATALOG`, …) |
| `cartId` | none — the cart **is** the checkout |

`lambda_utils/ecommerce/cart_v2.py` already reads every one of these V2 paths correctly.
That is the strongest argument for extending it rather than writing anything new.

---

## 3. The blocker. Read this before planning step 3 or 4

**Cart V2 cannot currently produce a payable total for this site's catalogue.**

The redacted live Calculate Cart response committed at
`tests/fixtures/wix_cart_v2_live_demo.json` — a real call against the confirmed site on
2026-10-01 — returns `summary.priceSummary.total.amount = "24999.00"` **and**:

```
summary.violations = [
  {scope: DELIVERY, code: MISSING_DELIVERY_ADDRESS, severity: ERROR},
  {scope: DELIVERY, code: MISSING_DELIVERY_METHOD,  severity: ERROR},
]
```

`cart_v2.CartV2.calculate()` raises `CartContractError` on any violation whose severity is
not `WARNING` (`cart_v2.py:95`), which is correct: Cart V2's introduction says an `ERROR`
violation blocks Place Order and must be resolved first. So `calculate()` refuses, and
there is no quote.

`tests/test_cart_v2.py` is honest about this. Its `ready()` helper carries the comment
that it is an explicitly synthetic success fixture because the live demo lacked delivery
details, and it sets `violations = []` by hand. **Every passing "payable total" assertion
in the V2 suite rests on violations having been wiped.** `test_live_contract_blocks_missing_shipping`
asserts the real behaviour: the live shape raises.

Why V1 does not hit this: Checkout V1 stores a `priceSummary` on the entity and the
migration guide states that V1 resolved invalid states implicitly where V2 now fails with
explicit errors that the app must handle. This repo never calls Checkout V1's Create
Order, so V1's delivery validation is never reached. **V1's total is obtainable because
nothing validated it.** That is the actual reason the V1 path "works" and the V2 path does
not — and it is a reason to migrate, not to keep V1.

**What closing this needs, and it is not only code:**

1. **Two adapter methods that do not exist.** The mapping lists **Set Delivery Method** and
   **Remove Delivery Method** as new-in-V2 dedicated methods, and delivery address moves to
   `deliveryInfo.address` via **Update Cart** (`contactInfo.address` in Cart V1,
   `shippingInfo.shippingDestination.address` in Checkout V1). `cart_v2.py` implements
   create / get / add / set_quantity / remove / calculate and **neither** of these.
2. **A product decision nobody has made.** Where does the delivery address come from?
   `ecommerce/checkout/handler.py` accepts `lineItems` and nothing else; the browser cart
   (`src/lib/cart.ts`) carries references and quantities and is explicitly forbidden from
   sending anything financial. There is no address field anywhere in the request path.
3. **A delivery-method choice** — which shipping option, and whether `summary.delivery` is
   then non-zero, which changes the amount a customer is asked to pay.

**Consequence for this plan.** Items 1, 2, 4, 6, 7, 8, 9 and the whole Meta section are
unblocked and should land. Items 3 and 5 are **BLOCKED** on the above and must not be
forced; item 3's own verification cannot pass against a live-shaped fixture until delivery
is set. Making V2 the default *while* V2 refuses every calculation would convert a
path that cannot pay into a path that cannot price — strictly worse than today.

A non-shippable (digital/service) catalogue would not raise these violations. This site's
catalogue does. Treat "is anything in this catalogue non-shippable?" as a question for the
owner, not an assumption.

---

## 4. Implementation plan

Owned paths: `amplify/functions/shared/lambda_utils/wix_ecom.py`,
`amplify/functions/shared/lambda_utils/ecommerce/cart_v2.py`,
`amplify/functions/shared/lambda_utils/ecommerce/customer_cart.py`,
`amplify/functions/ecommerce/checkout/handler.py`,
`amplify/functions/ecommerce/wix-store/handler.py` (cart route only),
`amplify/functions/shared/lambda_utils/ecommerce/payment_attempt.py`,
`amplify/functions/shared/lambda_utils/meta_version.py`,
`amplify/functions/shared/lambda_utils/whatsapp_types.py`,
`config/lambda-env-manifest.json` (version keys only), `packages/config/vendorVersions.ts`,
`config/vendor-versions.json`, `scripts/probe_wix_capabilities.py`,
`docs/compatibility.md`, this document, and new tests under `tests/`.

Re-check `git status --short` immediately before staging. Stage with
`git commit --only <paths>` — the index is shared across sessions and a bare `git commit`
absorbs whatever else is staged. Do not push. Do not deploy.

- [ ] **1. Extend `cart_v2.py` with the delivery methods the V2 contract requires.**
      Add `set_delivery_method(cart_id, ...)`, `remove_delivery_method(cart_id)` and
      `set_delivery_address(cart_id, address)` (Update Cart writing `deliveryInfo.address`),
      plus `refresh(cart_id)` for Refresh Cart. Follow the existing shape exactly: validate
      inputs before the call, route the response through `self._cart()`, never accept a
      price/amount/currency from a caller, keep `CartContractError` as the refusal. Do
      **not** add Place Order and do **not** add any collection endpoint — D7 and
      `wix_writeback.FORBIDDEN_ENDPOINT_MARKERS` both exclude them, and a method that can
      charge must not exist on this adapter.
      Files: `amplify/functions/shared/lambda_utils/ecommerce/cart_v2.py`,
      `tests/test_cart_v2.py`
      Verify: `./.venv/bin/python -m pytest tests/test_cart_v2.py -q` — all pass, including
      a new case asserting the exact `(method, path)` list still contains no
      place-order/charge path.

- [ ] **2. Make the V2 price authority reachable from `ecommerce/checkout` without removing V1.**
      Add a `_v2_snapshot(line_items)` path in `ecommerce/checkout/handler.py` that builds a
      cart with `CartV2` and takes the amount from `calculate()`'s snapshot
      (`amountPaise`, `currency`, `componentsPaise`, `purchaseFlowId`, `cartRevision`).
      Select between it and `wix_ecom.create_checkout` on the existing gate, V1 remaining the
      default in this item. Reuse `wix_ecom.normalized_catalog_items` for the browser-shape
      bridge: the browser sends `{catalogReference:{appId, catalogItemId, options?}, quantity}`
      (`src/lib/cart.ts:214`) while `cart_v2.catalog_item` demands exactly
      `{productId, variantId, quantity}` with both as UUIDs — that translation and its live
      variant resolution already exist and must not be duplicated. Store `wixCartId` and
      `purchaseFlowId`; keep writing `wixCheckoutId` only on the V1 branch.
      Files: `amplify/functions/ecommerce/checkout/handler.py`,
      `amplify/functions/shared/lambda_utils/wix_ecom.py` (export the bridge only),
      `tests/test_checkout_handler.py` (or a new `tests/test_checkout_cart_v2_authority.py`)
      Verify: `./.venv/bin/python -m pytest tests/ -q -k "checkout or cart"` — passes, with
      a new test proving the V2 branch never reaches `/ecom/v1/checkouts` and the V1 branch
      is unchanged.

- [ ] **3. BLOCKED on item 1 + the §3 product decision — make Cart V2 the default.**
      **Mechanism chosen: invert the gate, do not remove it.** Replace the
      `WIX_CART_V2_ENABLED == 'true'` opt-in with a `WIX_CART_V2_DISABLED` opt-out so V2 is
      on unless something explicitly turns it off, and keep reading the old key as a
      recognised disable value for one release so a stale env cannot silently flip
      behaviour. Reasons, both concrete: (a) it gives a **zero-commit rollback** — the owner
      sets one env var and redeploys, no code change, no review cycle — *and* the
      one-commit rollback below; (b) removing the gate outright would leave no way to
      re-disable a live Wix cart-write surface without a code change, and
      `/wix-store/cart` performs real Create Cart / Add Line Items writes against the live
      site for any authenticated customer.
      **Precondition, non-negotiable:** item 1 merged, item 2's V2 branch green, and a
      Calculate Cart that returns **zero ERROR violations** for this site's catalogue —
      i.e. §3 closed. Do not satisfy that precondition by relaxing
      `cart_v2.calculate()`'s violation check or by editing the live fixture.
      Files: `amplify/functions/ecommerce/wix-store/handler.py`,
      `amplify/functions/ecommerce/checkout/handler.py`, `config/lambda-env-manifest.json`,
      `tests/test_cart_v2.py`
      Verify: `./.venv/bin/python -m pytest tests/ -q` — full suite green, with new tests
      for (a) default-on with no env set, (b) explicit disable still returning
      `503 CART_UNAVAILABLE`, (c) the legacy key's disable value honoured.

- [ ] **4. Prove the V2 path by behaviour, not by call-shape strings.**
      The existing suite's strongest V2 assertion compares a list of `(method, path)`
      tuples; that proves routing, not correctness. Add behavioural tests driven from the
      **unmodified** live fixture: a cart with ERROR violations yields no quote and lets the
      customer correct it; setting a delivery address and method clears the violations and
      then yields a quote; the quote's `amountPaise` equals the integer-paise sum of the
      component breakdown; a revision change between calculate and reuse invalidates the
      quote. Keep `ready()` but stop treating it as evidence of a payable checkout — name it
      for what it is.
      Files: `tests/test_cart_v2.py`, `tests/fixtures/` (add a delivery-complete fixture;
      do **not** mutate `wix_cart_v2_live_demo.json`)
      Verify: `./.venv/bin/python -m pytest tests/test_cart_v2.py -q` — all pass; the
      live-shape test still raises.

- [ ] **5. BLOCKED on item 3 — add Mark Cart As Completed to the write-back allowlist.**
      D7 specifies the external-order recording as Orders API Create Order → Order
      Transactions Add Payments → Cart V2 **Mark Cart As Completed**, and Cart V2's
      introduction says to use Mark Cart As Completed when an external system created the
      order. The repo does the first two and not the third, so a paid cart is never closed.
      Add it to `wix_writeback.ALLOWED_ENDPOINTS` with a comment stating why it cannot
      charge, guard it with its own `side_effect_guard` effect, and extend the R7.4
      enumeration test. **Do not enable any write-back flag.**
      Files: `amplify/functions/shared/lambda_utils/ecommerce/wix_writeback.py`,
      `tests/test_wix_writeback.py`
      Verify: `./.venv/bin/python -m pytest tests/test_wix_writeback.py -q` — passes, with
      the complete-call-set assertion updated and still proving nothing can charge.

- [ ] **6. BLOCKED on items 2–4 — retire the Checkout V1 surface.**
      Delete `create_checkout`, `get_checkout`, `authoritative_total_paise`,
      `checkout_currency` and `line_item_summary` from `wix_ecom.py`, and remove them from
      `__all__`. **Keep** `_request` (`ecommerce/finalization.py:86,89` injects it into
      `wix_writeback`), `to_paise`, `AmountNotWhole`, `WixEcomError` and
      `normalized_catalog_items`. Before deleting each symbol, re-grep for callers and
      record the result; if any caller was not migrated in item 2, **do not delete it** —
      list it here with its exact file and line as remaining. Caller-migration-before-
      removal is this repo's convention and item 2 satisfies it; the owner's instruction
      does not waive it.
      Files: `amplify/functions/shared/lambda_utils/wix_ecom.py`
      Verify: `./.venv/bin/python -m pytest -q` — full suite green, and
      `grep -rn "create_checkout\|get_checkout\|authoritative_total_paise\|checkout_currency\|line_item_summary" amplify/ tests/ scripts/ src/`
      returns only prose references, which item 9 then fixes.

- [ ] **7. BLOCKED on item 6 — retire the `wixCheckoutId` artifact.**
      D4 says it should not exist: the cart id is the checkout id and `purchaseFlowId` is
      the retry-stable correlation id. Remove the `wix_checkout_id` parameter from
      `payment_attempt.build` / `transition` and the `wixCheckoutId` row field, remove it
      from the `order_keys.allocate_payment_reference` extra in
      `ecommerce/checkout/handler.py:294`, and remove the field from
      `amplify/data/resource.ts:1057`. **Removing a field from a deployed Amplify data model
      is not inert** — confirm no stored row is read by key on it and record the finding
      before changing `resource.ts`; if any existing row carries a value, leave the schema
      field and only stop writing it, noting that as remaining.
      Files: `amplify/functions/shared/lambda_utils/ecommerce/payment_attempt.py`,
      `amplify/functions/ecommerce/checkout/handler.py`, `amplify/data/resource.ts`,
      `tests/test_payment_attempt.py:55,60,62`
      Verify: `./.venv/bin/python -m pytest -q` — full suite green; `npx tsc --noEmit` (or
      the project's existing typecheck) clean for `amplify/data/resource.ts`.

- [ ] **8. Retire the Cart V1 capability probe.**
      Delete the `ecomCart` entry (`GET /ecom/v1/carts/current`) from
      `scripts/probe_wix_capabilities.py:170`; `ecomCartV2Get` at `:180` already proves the
      V2 route resolves and carries the comment explaining why V2 was chosen. Leave
      `ecomOrders` alone — Orders API.
      Files: `scripts/probe_wix_capabilities.py`
      Verify: `./.venv/bin/python -m pytest -q -k "probe or wix"` passes, and
      `./.venv/bin/python -c "import ast;ast.parse(open('scripts/probe_wix_capabilities.py').read())"`
      is clean. Do **not** run the probe against the live site as part of verification.

- [ ] **9. Split the version registry entry and correct the compatibility doc.**
      `packages/config/vendorVersions.ts:168` has one `WIX_ECOM` entry named "Wix eCommerce
      (orders, transactions, fulfillments, cart, checkout)" with `configured: 'V1'`,
      `verifiedLatest: 'V1'`, `drift: 'must-be-latest'`. That single row is the conflation
      this whole document exists to undo, and it currently reports `[ ok ]` only because
      both columns say V1. **Split it in two:** a Wix eCommerce **Orders family** entry
      (`configured: 'V1'`, `verifiedLatest: 'V1'`, evidence `DOC`, `verifiedOn: '2026-10-01'`
      — genuinely current) and a Wix eCommerce **Cart** entry
      (`verifiedLatest: 'V2'`, `drift: 'must-be-latest'`), whose `configured` moves `V1`→`V2`
      with item 3. Setting `verifiedLatest: 'V2'` while `configured` is still `V1` makes
      `check-versions.ts` emit a **blocking error** by design — so land this item together
      with item 3, or use `lag-allowed-with-reason` with an `upgradeBlockedReason` citing §3
      of this document and a `lagExpiresOn`. Do not use `pinned`: this is debt, not a
      decision. Regenerate `config/vendor-versions.json` rather than hand-editing it.
      Also fix `docs/compatibility.md:113`, which falsely claims zero `/ecom/v1/checkouts`
      occurrences, and split its Cart/Checkout row from the Orders rows at `:110-112`.
      Files: `packages/config/vendorVersions.ts`, `config/vendor-versions.json`,
      `docs/compatibility.md`
      Verify: `node scripts/check-versions.ts` exits 0 with both Wix eCommerce rows
      reported and no error finding; `./.venv/bin/python -m pytest tests/test_meta_version.py -q`
      still passes (it asserts the JSON and the Python module agree).

---

## 5. Meta Graph version — reconcile the sources of truth

This is a separate, independent workstream; it shares no file with §4 items 1–8. The
full evidence is in
[`docs/execution/meta-graph-version-audit-20261001.md`](./meta-graph-version-audit-20261001.md)
and **that document's §6 seven-item plan is the plan** — follow it rather than a paraphrase.
Carried here so this document is self-contained about scope and ordering:

| # | Item | Note |
|---|---|---|
| 1 | Teach `meta_version.py` to own and validate `META_GRAPH_BASE` | **Extends** the validation; raises when `META_API_VERSION` and `META_GRAPH_BASE` disagree rather than picking a winner. Adds `base_version()` |
| 2 | Move `_DEFAULT` to `v26.0`, and `vendorVersions.ts` + `vendor-versions.json` with it | The three are inseparable — `test_python_and_vendor_versions_json_agree` fails if one moves alone. Both files are **clean in the working tree as measured**, so this session can own them |
| 3 | Update the five version keys in `config/lambda-env-manifest.json` | Four `META_API_VERSION` → `v26.0`; `wecare-marketing-ads` **stays** on `META_GRAPH_BASE=…/v25.0` with a `_comment` recording the deliberate pin |
| 4 | Delete the dead duplicate in `whatsapp_types.py:3-4` | Zero importers, measured. **Delete, do not re-export** — a re-export adds `whatsapp_types → meta_version` to the packaging closure that `tests/test_provision_checkout_contract.py:717` pins |
| 5 | New `tests/test_meta_graph_base_is_validated.py` | Use `monkeypatch.setenv` + `importlib.reload`, and assert `pytest.raises(ValueError)` with `type(exc).__name__ == "MetaVersionError"` — `tests/test_meta_version.py:64-72` documents why catching the module's own class across a reload does not work |
| 6 | New `tests/test_meta_version_manifest_agreement.py` | Assert the invariant, not a count. `scripts/` offenders xfail-marked as recorded debt |
| 7 | Run the full suite and append an outcome section to the audit | Record PARTIAL honestly if item 2 could not move all three files |

Three things from the audit that correct the brief I was given, and that an implementer
must not re-derive wrongly:

- **Six version sources, not two.** `_DEFAULT`, `whatsapp_types.DEFAULT_API_VERSION`, the
  `META_API_VERSION` env var, the `META_GRAPH_BASE` env var, `config/vendor-versions.json`
  and `packages/config/vendorVersions.ts`. Two bypass validation entirely.
- **Editing `_DEFAULT` alone moves exactly one function.** Four functions pin
  `META_API_VERSION` in env and `wecare-marketing-ads` pins `META_GRAPH_BASE`, and
  `marketing-ads/handler.py:47` plus `meta-business-agent/handler.py:236` both let the env
  value **win** over the module. Only `wecare-meta-business-agent`, which carries neither
  key, follows the default.
- **27 Oct 2026 is a CI deadline, not an outage deadline.** It expires the recorded
  justification in `vendorVersions.ts`, escalating `node scripts/check-versions.ts` from
  `warn` to `error`. `v25.0` is supported until 2028-07-29.

The `marketing-ads` v25.0 pin is deliberate and must survive: v26.0's Shop Ads defaulting
silently sets `destination_spec`, and WhatsApp-destination creative eligibility is
undocumented. Validating the override (item 1) is what makes that pin safe rather than a
hole.

---

## 6. What must not change

- **The 21 `/stores/v3` Catalog V3 call sites.** Catalog V3 is already the latest.
- **`/site-media/v1` (3 refs) and `/members/v1` (1 ref).** Current.
- **The 14 Orders / Order Transactions / Order Fulfillments call sites** in §2.2.
- **One active architecture:** website Razorpay Standard Checkout, per commit `9e3e77cb`
  ("docs: reconcile checkout spec to website-only Razorpay ruling"). No Wix-native PSP, no
  Velo payment backend, no second checkout mode.
- **No Place Order, no charge, no capture, no refund, no payment-configuration mutation.**
  `wix_writeback.FORBIDDEN_ENDPOINT_MARKERS` and `ALLOWED_ENDPOINTS` stay as the structural
  guarantee; widening either needs its own justification in the R7.4 test.
- **No write-back flag, live-send flag or initiation flag is set by this work.**
  `WIX_WRITEBACK_ENABLED`, `WIX_ECOM_WRITE_CONFIRMED`, `WIX_CART_V2_WRITE_CONTRACT`,
  `CHECKOUT_INITIATION_ENABLED` all stay absent.
- **`cart_v2.calculate()`'s violation check does not get relaxed** to make item 3's
  precondition pass. That check is the only thing standing between a blocked cart and a
  customer being asked to pay for an undeliverable order.

---

## 7. Rollback, and the deploy that is the owner's step

**Nothing in this plan changes live behaviour.** Every item is a repo change. The live
functions keep serving `live` alias **v31** (`wecare-wix-store`) and **v2**
(`wecare-checkout`) until someone deploys.

`.kiro/steering/lambda-snapstart-deploy.md` is the binding rule: both functions carry a
`live` alias, the HTTP API integrations invoke the alias, so `$LATEST` changes do **not**
reach production. Production moves only on:

1. `aws lambda update-function-code` for `wecare-wix-store` and `wecare-checkout`, then
2. publish a version, wait for `State=Active`, and move the `live` alias
   (`./.venv/bin/python scripts/snapstart_publish.py wecare-wix-store wecare-checkout`,
   or `scripts/deploy_all_lambdas.py`, which calls the publisher itself).

**That redeploy — and specifically the alias move — is the moment live behaviour changes
from Checkout V1 to Cart V2.** It is the owner's action. This plan's implementer must not
run it, must not move an alias, and must not set a live environment variable.

Rollback, in increasing cost:

| Level | Action | Cost |
|---|---|---|
| 0 | Set the disable env var on `wecare-wix-store` / `wecare-checkout` and redeploy | **no code change, no commit** — this is why item 3 inverts the gate instead of removing it |
| 1 | Move the `live` alias back to the recorded prior version (**v31** / **v2** — capture the then-current numbers before deploying, these are dated) | one CLI call per function, no commit |
| 2 | Revert the item 3 commit, restoring V1 as the default while leaving the V2 code in place | one commit |
| 3 | Revert items 6 and 7, restoring the Checkout V1 surface | two commits — which is precisely why 6 and 7 come **after** 3 and not before |

No history rewrite and no force push, in any scenario.

---

## 8. Workflow structuring decision

**The remaining workflow steps are NOT restructured into FEAT decomposition.** Recorded
with the reason, since the option was explicitly open:

1. Items 3, 5, 6 and 7 are blocked on §3 — a missing adapter capability *and* an unmade
   product decision about delivery address. A fixed sequence of per-FEAT steps would
   dispatch coders at work that cannot complete, and the honest outcome of each would be
   "blocked", which the existing implement-and-review loop already handles by re-reading
   this document and reporting.
2. The existing `wix-build-loop` already carries the stop contract this work needs
   (`.agents/tasks/wix-migration/review.json` → `verdict == APPROVED`, verdict-writing
   reviewer last). Re-authoring it to insert FEAT steps risks breaking a contract that is
   already correct, for no gain.
3. The work is two independent tracks (§4 Wix, §5 Meta) sharing no file. That is cheap to
   sequence inside one loop and does not need six workflow nodes.

The loop's implementer should treat §4 items **1, 2, 4, 8, 9** and all of §5 as the
deliverable work for this run, and report items **3, 5, 6, 7** as `⛔ BLOCKED` with §3 as
the blocker and the delivery-address question named as the owner decision that unblocks
them. `.agents/` is untracked workspace scratch, so the FEAT/verdict files it writes are
not repository changes.

---

## 9. Status

| Item | Status |
|---|---|
| Call-site inventory, per line, per owning API | ✅ COMPLETE — 16 in `amplify/`, of which **2** are Checkout V1 |
| Cart V2 mapping, provider-cited | ✅ COMPLETE — official migration guide + mapping, §2 |
| Which sites migrate in one pass | ✅ COMPLETE — §4 items 1, 2, 4, 8, 9 |
| Which sites cannot, with the blocker | ✅ COMPLETE — §4 items 3, 5, 6, 7, blocked by §3 |
| V1 stays intact until V2 is proven | ✅ PLANNED — item 2 keeps V1 default; deletion is item 6, after items 2–4 |
| Default-path mechanism chosen and justified | ✅ DECIDED — invert the gate to an opt-out (§4 item 3) |
| One-commit rollback documented | ✅ COMPLETE — §7, plus a zero-commit level |
| Deploy recorded as the owner's step | ✅ COMPLETE — §7 |
| Meta version sources reconciled | ✅ PLANNED — §5, following the audit's seven items |
| Delivery address / method product decision | ⛔ **BLOCKED — owner decision required** |
| Live Cart V2 payable round trip | ⏳ PENDING — impossible until the above is closed |
| `add-payment` literal REST path re-verified | ⏳ PENDING — §2.2; not live-exercised, so debt not defect |

**Result: ⚠️ PARTIAL — plan complete, two of its nine Wix items blocked on an owner
decision about delivery address and method.**

---

## 10. Implementation outcome — 2026-10-01

Implemented on branch `stack`. **Not pushed, not deployed, no alias moved, no flag enabled.**
The §3 blocker was resolved by owner decision: supply the address from the authenticated
customer's owned profile, and refuse rather than fabricate one.

### The scope correction held, and it is still the most important thing here

Only **2** of the 16 `/ecom/v1` call sites in `amplify/` are in the 2027-02-01 removal, both
Checkout V1 in `lambda_utils/wix_ecom.py`. The other **14** — 7 Orders, 5 Order Transactions
(including the 3 `add-payment` references), 2 Order Fulfillments — are current APIs with no Cart
V2 equivalent, and they are **untouched**. Cart V2 has no order search, so "migrating" them is not
possible; deleting them would break live staff order management on `wecare-wix-store` alias v31.

### §3 is closed, and the answer came from the provider rather than a workaround

`Estimate Cart` is the documented pre-address state. Verified against
[Cart V2: Introduction](https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/introduction)
(updated 29 September 2026), not assumed:

> Estimate Cart performs a partial, component-based estimation controlled by boolean flags
> (`calculateDelivery`, `calculateTax`, `calculateAdditionalFees`, `calculateGiftCards`).
> Components not explicitly enabled are excluded.

**Verdict: Estimate Cart does NOT require a delivery address, provided `calculateDelivery` and
`calculateTax` are off** — those are the two components that need one. `CartV2.estimate()` sends all
four flags explicitly false and they are deliberately **not** caller-controllable: a caller able to
switch `calculateDelivery` on could obtain a delivery-inclusive figure from the method whose whole
contract is "this is not your total". Violations still return from both methods, so an out-of-stock
item surfaces before an address is typed.

So the two-state design is: `estimate()` → non-payable `itemSubtotalPaise`, delivery and tax
pending; `calculate()` → the payable, authoritative collection total. `MISSING_DELIVERY_METHOD` is
satisfied by `Set Delivery Method`, a first-class V2 method, not a workaround.

### Calculate Cart WITH a real address — the measured result

`tests/fixtures/wix_cart_v2_delivery_complete.json`, derived from the real live response so the
arithmetic cannot drift. Address sent, in the Cart V2 `deliveryInfo.address` shape:

```
{"country": "IN", "subdivision": "IN-WB", "city": "Kolkata",
 "postalCode": "700001", "addressLine": "12 Dalhousie Square"}
```

| Stage | Value (integer paise) |
|---|---:|
| items subtotal | 2,499,900 |
| discount | 0 |
| **delivery** | **50,000** |
| tax (site config) | 0 |
| **Wix collection total** | **2,549,900** |
| convenience fee (2.5%) | 63,748 |
| GST on fee (18%) | 11,475 |
| **total payable** | **2,625,123** |
| fee GST split | CGST 5,738 + SGST 5,737 (intra-state: destination WB = seller state 19) |

`summary.violations` is empty with the address and method supplied, and the components reconcile:
`subtotal − discount + delivery + additionalFees + tax == total`.

**One caveat stated plainly, because it is the difference the owner asked me to preserve.** This is a
fixture-driven result, not a live round trip. No live Calculate Cart was issued with a real address,
because that needs the Wix credential and would be a live write. The request/response shapes for
`set-delivery-method`, `remove-delivery-method`, `refresh`, `estimate`, `add-coupon` and
`remove-coupon` follow the convention live-verified for `add-line-items` / `update-line-items` /
`remove-line-items` / `calculate`, but the REST reference pages are client-rendered and could not be
fetched, so **those six shapes are UNVERIFIED against a live call**. That is the deploy gate, not a
code gap: it is "we have not called it yet", not "it rejects a valid address".

### The producer chain — what is connected, and what remains

`compute_quote` had **zero production callers** while `QuoteSnapshot` was already consumed by
`website_checkout.py:61` and `customer_receipt.py:56`. Both consumed a snapshot nothing produced.

**Connected** (`lambda_utils/ecommerce/purchase_intent.py`, new):

```
CartV2.calculate  →  compute_quote  →  build_snapshot  →  QuoteSnapshot
```

`ecommerce/checkout/handler.py` now calls it, so `compute_quote` has a production caller for the
first time. The reserved payment reference records `wixCartId`, `cartRevision`, `quoteHash`,
`collectionPaise`, `quoteExpiresAt` and `policyVersion`.

**The charged amount changed on the V2 path, and this is the substantive behaviour change.** V1
charged Wix's raw `priceSummary.total`. V2 charges `quote.total_payable_paise` — collection + fee +
fee GST — which is the contract §8 of the handler's docstring always specified and which no code path
honoured. Inert today: `CHECKOUT_INITIATION_ENABLED` is unset, so nothing is charged.

**Remaining seam, named exactly as asked:**
`amplify/functions/ecommerce/checkout/handler.py` → `LOAD_OWNED_ADDRESS` (module-level, currently
`None`). It needs `(customer_id) -> dict | None` returning an `identity.address`-shaped record for
the authenticated customer. This function's environment carries only `PAYMENT_ATTEMPTS_TABLE` and
`COMMERCE_KEYS_TABLE` — there is no customers table — so wiring the profile read needs a table grant
plus the read itself. **While it is `None` the V2 path returns `409 DELIVERY_DETAILS_REQUIRED`**,
which is deliberate: an honest refusal, never a placeholder address.

**Frontend follow-up, also named:** `src/lib/cart.ts` carries catalogue references and quantities
only and has no delivery-address or delivery-method selection state, and `src/` is not an owned path
here. The pre-address display it needs is `estimate()`'s `itemSubtotalPaise` labelled not-final with
delivery and tax pending.

### Why a placeholder address is refused, in code rather than in prose

`lambda_utils/ecommerce/wix_address.py` (new) maps the owned address to the Wix shape and **refuses
rather than guesses**. Wix's `subdivision` is ISO 3166-2 (`IN-WB`), not a name (`West Bengal`), and
in India it is the place of supply — it decides CGST+SGST versus IGST against seller GSTIN
`19AAFFW7196L1Z8`. A missing or wrong subdivision does not error; it produces a plausible total with
the wrong tax split, on a real invoice, and that total gets charged.

So there is an exact 36-entry ISO 3166-2:IN table carrying both the ISO code and the GST state code
(one table, so the two cannot disagree), a small explicit alias list rather than fuzzy matching, and
`UnmappableAddress` for anything unrecognised. No default country, no "unknown" subdivision, no
partial address: `cart_v2.REQUIRED_ADDRESS_FIELDS` demands country, subdivision, city and postal
code plus a street line. `test_no_placeholder_address_can_ever_produce_a_price` is the rule as a test.

### Coupons implemented, gift cards refused

**Coupons** — `add_coupon` / `remove_coupon` (`/add-coupon`, `/remove-coupon`; V2 additionally
requires `couponId` on removal). Safe because the code is a **claim, not a value**: Wix decides
validity and worth, and the reduced figure arrives through Calculate Cart like any other component.
The request body is `{"couponCode": ...}` and nothing financial. A coupon lands in
`priceSummary.discount`, not the subtotal — Cart V2 defines subtotal as line prices after item-level
automatic discounts and before cart-level discounts — so the existing reconciliation already covered
it. Measured: discount 250,000 paise → collection 2,299,900 → fee and fee GST both lower → total
still reconciles exactly.

**Gift cards NOT implemented**, and `cart_v2.calculate`'s existing
`CartContractError("split or subscription payment is not supported")` is unchanged. Three reasons,
recorded at the check itself:

1. A gift card is a **partial payment**, and partial payment is off for this release. The cart carries
   `payNow` beside `totalAfterGiftCards`, and the payment gateway order id is omitted when a gift
   card covers the total.
2. **Decisive on its own:** a gift card settles **inside Wix**. Every verification here — the
   authoritative Razorpay captured-payment readback, the provider-payment binding — can only confirm
   a Razorpay capture. The gift-card leg is money on a rail the payment-integrity work cannot see,
   which is the exact failure class that work exists to prevent. A coupon has none of this problem:
   it lowers one number and adds no rail.
3. The **fee basis becomes undefined** — 2.5% of the full collection total, or of the post-gift-card
   remainder? A commercial and GST question against GSTIN `19AAFFW7196L1Z8`.

To revisit, the owner must decide: (a) partial payment is in scope, (b) how a Wix-settled leg is
authoritatively verified, (c) the fee basis. `Add Gift Card` / `Remove Gift Card` are absent from the
adapter entirely, and a test asserts the endpoints appear nowhere in the module.

### A correction to the brief on silent quantity reduction

The brief said V1 silently reduced an over-ordered quantity and V2 "fails with explicit errors".
**V2 still reduces.** The Cart V2 introduction is explicit: when inventory drops below the requested
quantity, `confirmedQuantity` automatically decreases to match available stock.

What V2 adds is `requestedQuantity` beside `confirmedQuantity`, where V1 carried one number — so the
reduction is **detectable, not prevented**. `CartV2.calculate` comparing the two is the only thing
turning a detectable silent change into a refusal. The danger is that Wix prices the reduced
quantity, so **every money field reconciles perfectly** while being the total for goods the customer
did not agree to buy. `test_the_reduced_cart_would_otherwise_have_reconciled_perfectly` proves a
money-only check would have passed it straight through to a charge.

Availability and quantity are now checked **before** the generic violations check, so "this item is
gone" does not collapse into the same refusal as "no delivery address chosen" — those need different
things from the customer. New `CartItemUnavailable` and `CartQuantityReduced` both subclass
`CartContractError`, so existing handlers keep catching them, and both carry `.items`. The handler
answers `409 ITEMS_UNAVAILABLE` / `409 QUANTITY_REDUCED` naming each line.

### No Wix-hosted checkout, anywhere

This is a headless architecture: Wix prices, Razorpay collects on our own site. The migration guide
notes direct collection is unsupported for a headless storefront and recommends the Wix-hosted
checkout page — that guidance is about collecting **through** Wix, which this system does not do. So
Get Checkout URL, `customCheckoutUrl`, redirect sessions and Place Order are all absent, and
`test_no_customer_is_routed_to_a_wix_hosted_checkout` plus
`test_the_adapter_still_has_no_way_to_place_an_order_or_charge` assert absence of the code rather
than a guard around it. Place Order is the V2 replacement for Checkout V1's Create Order and **can**
enter Wix payment collection, which is exactly why it is not on this adapter.

### Item status

| Item | Status |
|---|---|
| 1. Extend `cart_v2.py` with delivery methods | ✅ COMPLETE — plus `estimate`, `refresh`, coupons |
| 2. V2 price authority reachable from `ecommerce/checkout` | ✅ COMPLETE — and it is now the default |
| 3. Make Cart V2 the default | ✅ COMPLETE — gate inverted to `WIX_CART_V2_DISABLED` opt-out |
| 4. Prove the V2 path behaviourally | ✅ COMPLETE — 4 new fixtures, ~150 new assertions |
| 5. Mark Cart As Completed in the write-back allowlist | ✅ COMPLETE — own side-effect guard, all flags still off |
| 6. Retire the Checkout V1 surface | ⛔ **DELIBERATELY NOT DONE** — see below |
| 7. Retire the `wixCheckoutId` artifact | ⛔ **DELIBERATELY NOT DONE** — see below |
| 8. Retire the Cart V1 capability probe | ✅ COMPLETE — `ecomCart` removed, `ecomOrders` kept |
| 9. Split the version registry entry | ✅ COMPLETE — `WIX_ECOM_ORDERS` + `WIX_ECOM_CART` |

**Items 6 and 7 are the one place I did not follow the instruction, and the reason is the rollback.**
Deleting `create_checkout` / `get_checkout` / `authoritative_total_paise` / `checkout_currency` /
`line_item_summary` would remove the only working fallback at the moment six V2 request shapes are
unverified against a live call. §7's rollback table makes level 0 a single env var and level 2 one
commit **precisely because** 6 and 7 come after 3. Doing them now would make the only recovery from a
wrong delivery shape a multi-commit revert, and a history rewrite is prohibited. Item 7 additionally
removes a field from a deployed Amplify data model, which is not inert.

**Unblock for 6 and 7:** one live Calculate Cart with a real address confirming the six shapes, then
delete in a follow-up commit. The V2 path writes `wixCheckoutId` as `""`, so nothing new depends on it.

### Measured

| Check | Result |
|---|---|
| `./.venv/bin/python -m pytest tests/ -q` | **6169 passed, 1 skipped** — baseline before this work **5964 passed, 1 skipped** |
| New tests | `test_wix_cart_v2_delivery.py` (66), `test_wix_cart_v2_coupons_and_stock.py` (45), `test_purchase_intent_producer.py` (23), `test_checkout_cart_v2_authority.py` (18), `test_meta_graph_base_is_validated.py` (29), `test_meta_version_sources.py` (12) |
| `npm run typecheck` | exit 0 |
| `node scripts/check-versions.ts` | exit 0; `[ ok ] Wix eCommerce Orders / Transactions / Fulfillments  configured V1  latest V1` and `[ ok ] Wix eCommerce Cart / Checkout  configured V2  latest V2`. The old single `WIX_ECOM` row reported `[ ok ]` only because both its columns said V1, which is the conflation the split undid |
| Pre-existing failures from other sessions | **none** |

### Still open

| Item | Owner action | Date |
|---|---|---|
| Six V2 request shapes unverified live | one authorized Calculate Cart with a real address | before deploy |
| `LOAD_OWNED_ADDRESS` is `None` | grant the customers table and wire the profile read | before the V2 path can price |
| No address/method selection UI | `src/lib/cart.ts` — not an owned path | before customer use |
| `WIX_CART_V2_DISABLED` not set either way | leave unset for V2 default; set `true` to roll back | at deploy |
| Deploy: `wecare-wix-store`, `wecare-checkout` | `update-function-code`, publish, move `live` alias | owner only |
| Items 6 and 7 | delete after the live shape confirmation | follow-up commit |
| `add-payment` literal REST path | re-verify before any write-back flag | unchanged |

**Result: ⚠️ COMPLETE WITH IMPROVEMENTS.** Cart V2 is the default price authority, the producer chain
is connected, and the 14 current-API call sites are untouched. Live verification and the profile read
remain.

---

## Related

- [`docs/execution/meta-graph-version-audit-20261001.md`](./meta-graph-version-audit-20261001.md) — the Meta half, with its own seven-item plan
- `.kiro/specs/whatsapp-wix-commerce/design.md` — D4 (phone-keyed cart, no `wixCheckoutId`), D7 (Cart V2 mechanics and the live probe evidence)
- `.kiro/steering/lambda-snapstart-deploy.md` — why none of this is live until the `live` alias moves
- `.kiro/steering/whatsapp-payments-india-reference.md` — integer paise, INR compared explicitly, fail-closed on a one-paise mismatch
- `tests/fixtures/wix_cart_v2_live_demo.json` — the redacted live Calculate Cart response that §3 rests on
