# Gift cards (Wix Service Plugin) — design, revision 4 (promoted to `docs/execution` 2026-10-02)

Owner intent, verbatim: *"A CUPPON CREATE CAN MENAIN IN TABLE AND LAMBE AN FIT CARD CREATE SMAME
ALL CREATE CAN BE USED USED IN CHECOUT"* — gift cards are created and held in our own DynamoDB
table by our own Lambda, and are usable at checkout.

**Additive new capability, not a migration.** WECARE remains a self-managed Next.js/AWS
application using Wix headlessly; AWS owns authentication, APIs, payment orchestration and
reconciliation; payment is Razorpay Standard Checkout on our own site; the Wix order is created
only after authoritative payment verification. No customer is routed to a Wix-hosted checkout and
`Get Checkout URL` is not called.

Every API-shape claim carries a `dev.wix.com` URL, fetched live on 2026-10-01. Schemas, quoted
sentences and example bodies were read out of the OpenAPI document and the article markdown the
docs pages embed, because the rendered tables collapse child properties behind "Show Child
Properties" and cannot answer "what are the exact fields".

> **The whole plugin is in Developer Preview.** All three methods report `maturity: BETA` in the
> service schema, and each page carries the banner *"Developer Preview — This API is subject to
> change. Bug fixes and new features will be released based on developer feedback throughout the
> preview period."* The contract transcribed below is a dated snapshot and must be re-measured
> before the SPI is registered.

**REVISION 4 — PROMOTED 2026-10-02, AND THIS IS THE IMPLEMENTED TRUTH.** This copy was promoted from
`.agents/tasks/wix-coupons-giftcards-20261001/gift-cards-service-plugin-20261001.md` into
`docs/execution/` with **every** finding of the revision-3 review **applied to the design**, not
appended as a response table. Where the code that shipped differs from what any revision described,
the code is recorded here and the prose was corrected to match it. §13's tables are the audit trail,
not the design.

**Six changes of revision 4 alter the design**, each resolving a HIGH or a design-level MEDIUM:

1. **The hold existence fact moved onto `GIFTCARD#<codeHash>`** (R4-H3 / DECISION 5, §6.3–§6.4).
   §7.4's "refuse whenever any `GCHOLD#<codeHash>#*` row exists" had **no implementation**: this table
   is one partition attribute with `Scan` denied, and a `Query` needs partition-key equality. It is now
   a single exact-key `GetItem`, `GCHOLD#` rows are audit-only, and `GCID#<giftCardId>` is added
   because §7.2's GET-by-our-id had the same problem.
2. **`GC_VOIDED` is reachable** (R4-H6 / DECISION 9, §6.3, §6.5). `GCTXN#` gains `paymentAttemptId`,
   `GCTXNID#` points to `{codeHash, paymentAttemptId}`, and `referenceId` is demoted to correlation
   only. The IAM grant §10.1 already made was for a call nothing could compose.
3. **`redeem_cap` is defined exactly once** (R4-H4 / DECISION 10, §4.1, §7.5). §7.5 contradicted §4.1
   by capping against the payable, admitting a redemption Wix cannot apply.
4. **§7.2 is FIVE routes** (R4-M5). `POST /gift-cards/hold` and `/release` are removed; a customer
   session has no `paymentAttemptId` and the route could only have skipped the stage or been denied by
   IAM.
5. **`Content-Type` is never branched on** (R4-M4, §5). The allowlist was assembled from one example of
   a different endpoint and would have answered 401 to every live call if Wix sends
   `application/json`.
6. **The gift-card table is encrypted with a customer-managed KMS key** (DECISION 6, §6) — new ground
   in this repo, and a **pointwise owner confirmation** (§12.2 item 11).

Plus three enumerations corrected where the previous count was labelled "measured": **four** attempt
producers, not three (R4-M3, §8, new §8.5); **eight** `website_checkout.py` amount consumers, not five
(R4-M2, §8.1); and SEAM-G13's `verifiedCapturedPaise` now has a **named producer** (R4-M1).

And one file left §10.3's read-only list: **`scripts/provision_checkout.py` was edited** (R4-H5),
because its three parts cannot be split without breaking the script's own `--verify` gate.

> **Build status lives next door, not here.** What landed, what is still a seam, which xfail holds each
> seam's place, the owner actions and the unrun deploy order are all in
> **`docs/execution/coupons-giftcards-build-20261001.md`**. Read that first if you are picking this up
> cold.

**Revision 3** resolved the previous round's findings (6 HIGH, 12 MEDIUM, 4 NIT), itemised in §13.1.
Six changes altered the design rather than correcting a detail, and three of them came from reading
source the previous passes did not reach:

1. **The website producer is in scope.** `ecommerce/website_checkout.py` — not
   `checkout/handler.py` — is the module that implements the architecture both documents declare
   active. It sets the gateway amount, stores the binding a callback is verified against, and
   refuses a capture that disagrees with it. The split is now specified for **both** producers
   (HIGH-1, §8.1, SEAM-G14).
2. **The Razorpay leg now carries verified evidence, not intended evidence.** `is_fully_settled`
   reads `verifiedCapturedPaise` — the amount Razorpay's own readback reported — instead of
   `razorpayChargedPaise`, the figure we wrote at checkout. That dissolves HIGH-2, HIGH-3 and
   MEDIUM-16 together, because the attribute with no permitted writer is no longer read by the
   settlement decision at all (§3.2, SEAM-G13).
3. **The claim and the hold are re-keyed onto `paymentAttemptId`.** Revision 2 keyed them on
   `referenceId` and justified it with "stable across retries of the same basket". **Both halves
   were wrong**, and neither was in the review — see §3.4. `referenceId` is the Razorpay gateway
   order id on the website path, where it does not exist until *after* the gateway call the hold
   must precede.
4. **A gift card funds the supply only; it may not fund the convenience fee** (HIGH-4). That makes
   `redeemCap` and the Wix reconciliation identity agree, which revision 2's pair did not.
5. **The JWT verifier has a named library and a named layer** —
   `arn:aws:lambda:us-east-1:775261844268:layer:cryptography-python312:1`, attached by a named
   provisioner step — because Python's standard library cannot verify an RSA signature and the
   deploy gate would have refused the function (HIGH-6, §5.4).
6. **Both new functions have a written IAM specification** (HIGH-5, §10.1).

Revision 2's changes stand except where listed above: the absent-attribute branch of
`is_fully_settled`, the `data.request` envelope with the body as the JWT, the 100-paise Razorpay
floor, and `/v1/redeem` refusing rather than deducting.

---

## 1. Two Wix models, and which one this uses

Wix offers two routes, and they are not alternatives at the same layer.

**Model A — the Gift Cards Service Plugin (SPI). WIX CALLS YOUR APP.**
https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/payments/gift-cards/gift-cards-service-plugin/introduction

Service name `wix.gift.cards.provider.api.v1.GiftCardProvider`, entity
`wix.interfaces.ecom.v1.gift_card_provider_entity`. Quoted from the introduction article:

> The Wix eCommerce Gift Cards Provider Service Plugin allows you to integrate with Wix as a gift
> card service provider, enabling Wix merchants to utilize your gift card functionalities directly
> on their sites... By integrating your service with Wix, you can facilitate key gift card
> operations such as balance retrieval, redemption, and voiding transactions. These operations are
> seamlessly integrated into the site's checkout page.

Service plugins invert the direction of the call:

> **Don't call us, we'll call you.** Unlike traditional API endpoints where your app initiates a
> call with Wix, service plugins invert the process. Here, Wix calls your service during a
> specific flow, waits for your response, and then continues the flow based on your response.
> — https://dev.wix.com/docs/build-apps/develop-your-app/extensions/backend-extensions/service-plugins/about-service-plugin-extensions

Note the naming wrinkle, recorded so a package search does not mislead, quoted verbatim: *"Due to
npm package naming limitations, the SDK version is named 'Gift Vouchers service plugin'. Both
names refer to the same extension and provide identical functionality."* The SDK namespace is
`giftVouchersProvider` in `@wix/ecom`, and the required handler set is `getBalance()`, `redeem()`,
`_void()` — all three marked **Required: Yes** in the introduction's table. We implement the REST
form, not the SDK form.

**Model B — the Wix-managed route. YOU CALL WIX.** Two distinct APIs, often conflated:

*B1, the Wix Gift Cards app API* — issuance and administration, base
`https://www.wixapis.com/gift-cards/v1/gift-cards`, service `wix.gift_cards.v1.gift_card`, every
method `GA` and scoped **Manage eCommerce - all permissions**. The full method set, read from the
service's own `methods[]` array with each slug under the prefix
`https://dev.wix.com/docs/api-reference/business-solutions/gift-cards/gift-cards/` (closes
NIT-22 — these are now individually enumerated with verb and path from the live schema, not from
an index page):

| Operation | HTTP | Path | Slug |
|---|---|---|---|
| Create Gift Card | POST | `/gift-cards/v1/gift-cards` | `create-gift-card` |
| Get Gift Card | GET | `/gift-cards/v1/gift-cards/{giftCardId}` | `get-gift-card` |
| List Gift Cards By Email | GET | `/gift-cards/v1/gift-cards` | `list-gift-cards-by-email` |
| Query Gift Cards | POST | `/gift-cards/v1/gift-cards/query` | `query-gift-cards` |
| Search Gift Cards | POST | `/gift-cards/v1/gift-cards/search` | `search-gift-cards` |
| Count Gift Cards | POST | `/gift-cards/v1/gift-cards/count` | `count-gift-cards` |
| Disable Gift Card | POST | `/gift-cards/v1/gift-cards/{giftCardId}/disable` | `disable-gift-card` |
| Send Gift Card Email | POST | `/gift-cards/v1/gift-cards/{giftCardId}/send-email` | `send-gift-card-email` |

with transactions at
`https://dev.wix.com/docs/api-reference/business-solutions/gift-cards/transactions/query-gift-card-transactions`.
**None of these is wired.**

*B2, the eCommerce gift-card host API* — the host side of whichever provider is installed, base
`https://www.wixapis.com/ecom/v1/gift-cards`, service
`wix.ecom.gift_cards_spi_host.v1.GiftCardsSpiHostService`, all `GA`:

| Operation | HTTP | Path | Scope | Slug |
|---|---|---|---|---|
| Get Gift Card | POST | `/ecom/v1/gift-cards/{code}` | Read Gift Cards | `get-gift-card` |
| Redeem Gift Card | POST | `/ecom/v1/gift-cards/redeem` | Change Gift Card Balances | `redeem-gift-card` |
| Void Transaction | POST | `/ecom/v1/gift-cards/void` | Change Gift Card Balances | `void-transaction` |

all under
`https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/payments/gift-cards/gift-cards/`.
`RedeemGiftCardRequest` requires `code`, `amount.value`, `amount` and `appId`, where `amount` is
`{value: string DECIMAL_VALUE, currency: string}` — note B2 uses a **string** amount, unlike the
SPI's `number`. **Not wired either**, but recorded because it is the API a *different* provider's
card would be redeemed through, and because `Redeem Gift Card`'s own description — *"Redeems a
gift card. Creates a transaction and lowers the card balance by the transaction amount."* — makes
clear it mutates a balance Wix holds.

**Chosen: Model A, with the balance of record in our own table.** The owner asked for cards
created and held in our own table and Lambda; Model B puts the balance inside Wix, which makes
Wix the authority over money we are responsible for and leaves our own table a cache. Model A is
the documented way to be the provider of record, and the eCommerce Gift Card API introduction
confirms it is the self-build route:

> For these APIs to function, a gift card provider must be integrated into the site. This
> integration can be achieved by any of the following: ... Building your own app that implements
> the Wix eCommerce Gift Cards Service Plugin.
> — https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/payments/gift-cards/gift-cards/introduction

Model B is recorded as the alternative and is not wired. If the owner later prefers Wix to hold
the balance, that is a different design, not a configuration change.

### 1.1 The SPI contract, exactly as measured

Base URI is configured per app; Wix appends the path. The extension config schema
`wix.gift.cards.provider.api.v1.GiftCardProviderConfig` has exactly **one** property:

```
deploymentUri : string
  "Base URI where the endpoints are called. Wix eCommerce appends the endpoint path to the
   base URI. For example, to call the Get Balance endpoint at
   https://my-gift-cards.com/v1/balance, the base URI you provide here is
   https://my-gift-cards.com/."
```
https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/payments/gift-cards/gift-cards-service-plugin/extension-config

The documented config example is literally `{ "deploymentUri": "https://my-gift-cards.com/" }`.
The introduction article's REST tab additionally documents a second parameter in its setup table —
`componentName`, *"Unique name for this component, that appears only in the app dashboard"* — which
does not appear in the config schema. Both are recorded; `componentName` is cosmetic and
`deploymentUri` is the one that routes traffic.

Three methods, three paths, all `POST`, all `maturity: BETA`, all with empty `permissions` and
empty `permissionScopes` (the caller is Wix, authenticated by JWT, not by an OAuth scope):

| Method | operationId | Path | When Wix calls it |
|---|---|---|---|
| Get Balance | `...GiftCardProvider.GetBalance` | `{DEPLOYMENT-URI}v1/balance` | "when a customer applies a gift card as a payment method at checkout" |
| Redeem | `...GiftCardProvider.Redeem` | `{DEPLOYMENT-URI}v1/redeem` | "when a customer completes a purchase that includes a gift card as a payment method at checkout" |
| Void | `...GiftCardProvider.Void` | `{DEPLOYMENT-URI}v1/void` | "when a purchase fails after gift card redemption" |

https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/payments/gift-cards/gift-cards-service-plugin/get-balance
https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/payments/gift-cards/gift-cards-service-plugin/redeem
https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/payments/gift-cards/gift-cards-service-plugin/void

Request and response schemas, namespace `wix.gift.cards.provider.api.v1`, transcribed field by
field with every documented bound:

```
GetBalanceRequest
  code           string   minLength 8, maxLength 20   "Gift card code."
  appInstanceId  string   GUID   "App ID of the Gift Card provider. Deprecated."
  locationId     StringValue     "The physical location ID."
  pin            StringValue     "Gift card PIN."
  extendedFields object          wix.common.data.dataextensions.ExtendedFields

GetBalanceResponse
  balance        number   minimum 0, maximum 999999999.99   "Current balance."
  currencyCode   string   format CURRENCY
  externalId     StringValue
                 "External ID in the gift card provider's system. Used for integration and
                  tracking across different platforms."

RedeemRequest
  code           string   minLength 8, maxLength 20
  appInstanceId  string   GUID   (deprecated)
  amount         number   minimum 0, maximum 999999999.99   "Amount to redeem from the gift card."
  orderId        string   GUID   "Order ID the gift card transaction is applied to. Order details
                                  can be collected from eCommerce Search Orders."
  currencyCode   string   format CURRENCY
  locationId     StringValue
  pin            StringValue

RedeemResponse
  remainingBalance number minimum 0, maximum 999999999.99
  currencyCode     string format CURRENCY
  transactionId    string minLength 1, maxLength 100   "Transaction ID."

VoidRequest
  appInstanceId  string   GUID   (deprecated)
  transactionId  string   minLength 1, maxLength 100   "Transaction ID to void."
  locationId     StringValue

VoidResponse
  remainingBalance number minimum 0, maximum 999999999.99
  currencyCode     string format CURRENCY
```

The sample-flows article gives the exact JSON bodies, which corroborate the schema and settle the
`number` question beyond doubt — `"balance": 50.00`, `"amount": 50.00`,
`"remainingBalance": 0.00`, bare numbers with no quotes:
https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/payments/gift-cards/gift-cards-service-plugin/sample-flows

Three consequences that shape the data model:

> **`VoidRequest` carries no `code`.** It identifies the transaction by `transactionId` alone. So
> a transaction must be resolvable by its id without knowing which card it belongs to, which is
> why §6.3 carries a dedicated `GCTXNID#<transactionId>` reverse-index row. A design that keyed
> transactions only under the card would be unable to serve a documented request.

> **Every amount is `number`, not minor units.** Decimal rupees, max `999999999.99`. R6.1 forbids
> floats on the payment path, and `json.loads` turns `12.34` into a float by default — at the very
> entry point. The mandatory mitigation is in §6.2: `json.loads(body, parse_float=Decimal)`. A
> float must never be constructed, not even transiently.

> **`code` is `minLength 8, maxLength 20`.** That bound is what makes a plain hash unsafe as a
> partition key and drives the HMAC-with-pepper decision in §6.1.

Documented errors, read from each method's own `errors[]` array. The handler must return these
verbatim by name and status:

| `spiErrorData.name` | `applicationCode` | HTTP | `statusCode` | Balance | Redeem | Void |
|---|---|---|---|---|---|---|
| `GiftCardNotFound` | `GIFT_CARD_NOT_FOUND` | 404 | `NOT_FOUND` | ✓ | ✓ | |
| `GiftCardDisabled` | `GIFT_CARD_DISABLED` | 428 | `FAILED_PRECONDITION` | ✓ | ✓ | ✓ |
| `GiftCardExpired` | `GIFT_CARD_EXPIRED` | 428 | `FAILED_PRECONDITION` | ✓ | ✓ | ✓ |
| `MissingCurrency` | `MISSING_CURRENCY` | 428 | `FAILED_PRECONDITION` | ✓ | ✓ | ✓ |
| `InsufficientFunds` | `INSUFFICIENT_FUNDS` | 428 | `FAILED_PRECONDITION` | | ✓ | |
| `AlreadyRedeemed` | `ALREADY_REDEEMED` | 409 | `ALREADY_EXISTS` | | ✓ | |
| `CurrencyNotSupported` | `CURRENCY_NOT_SUPPORTED` | 400 | `INVALID_ARGUMENT` | | ✓ | |
| `TransactionNotFound` | `TRANSACTION_NOT_FOUND` | 404 | `NOT_FOUND` | | | ✓ |
| `AlreadyVoided` | **`ALREADY_VOIDED`** | 409 | `ALREADY_EXISTS` | | | ✓ |

`errorType` is `SPI` on every one. The service-plugin guidance is explicit that this is not
advisory: *"It's important to note before getting started that your implementation must match the
API specification exactly as documented. This ensures that as a service provider, Wix can use your
response in its flow."*

**`AlreadyVoided`'s `applicationCode` transcribed (closes MEDIUM-10's first half).** Revision 2
left that cell `—`, which made test 28 — parametrised on `(name, applicationCode, httpCode)` —
unwritable for that row. Re-fetched 2026-10-02 from the Void page's own `errors[]` array,
verbatim:

```json
{"httpCode": 409, "statusCode": "ALREADY_EXISTS", "applicationCode": "ALREADY_VOIDED",
 "name": "AlreadyVoidedWixError", "description": "Transaction was already voided.",
 "errorType": "SPI",
 "spiErrorData": {"name": "AlreadyVoided", "applicationCode": "ALREADY_VOIDED"},
 "errorSchemaName": "AlreadyVoidedWixError"}
```
https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/payments/gift-cards/gift-cards-service-plugin/void

So every row in the table above now has all four values and test 28 is fully parametrisable. Note
the two `name` fields are different and both are recorded: the outer `name` is the Wix-side error
class (`AlreadyVoidedWixError`), and `spiErrorData.name` is the value **we** return
(`AlreadyVoided`). Confusing them is how a response gets the wrong string in the right place.

#### 1.1.1 Wix documents NO error response body — and that is a measurement, not an omission

MEDIUM-10's second half asked for the error-response envelope with a citation. **There is none to
cite, and the honest answer is more useful than an invented one.** Measured on all three method
pages, the OpenAPI `responses` object declares exactly one status:

```
Get Balance   "responses": {"200": {"$ref": ".../GetBalanceResponse"}}
Redeem        "responses": {"200": {"$ref": ".../RedeemResponse"}}
Void          "responses": {"200": {"$ref": ".../VoidResponse"}}
```

No `4xx`, no `409`, no error schema, and no `$ref` to any error component. The nine rows above
exist **only** as `x-wix-docs.errors[]` annotations hanging off the method — metadata about
failures, not a response contract for them. The self-hosted service-plugin REST guide documents
the *request* envelope and signature validation in full and says nothing about error responses;
the service-plugin overview article says only *"the response must be returned per the
specification exactly as documented or Wix will not handle your response correctly"*, which is
the instruction without the specification.

Searching all three fetched pages plus both guides for `applicationError`, `spiErrorData` as a
response field, or a `details` envelope returns zero occurrences.

**Resolution — fail closed on the status, minimal on the body, and flag it as the blocking
unknown it is:**

1. **The HTTP status is the contract we can honour exactly**, and it is honoured exactly: 404,
   428, 409 or 400 per the table. A status is unambiguous and is what Wix's own annotation
   specifies.
2. **The body carries only the two values Wix names**, and nothing else:
   ```json
   {"name": "AlreadyVoided", "applicationCode": "ALREADY_VOIDED"}
   ```
   Exactly `spiErrorData`'s own two fields, flat, with the status on the HTTP response. Chosen
   over guessing a wrapper (`{"spiErrorData": {...}}`, `{"details": {"applicationError": ...}}`,
   a gRPC-style `{"error": ...}`) because every wrapper is an invention and an invented wrapper
   is strictly worse than a minimal one: a consumer that ignores the body still sees the right
   status, whereas a consumer looking for a documented key finds nothing either way.
3. **This is owner item 12.1 step 7** — a Developer Preview question for Wix, to be settled with
   a real call before registration. §7.4's nine error rows are implementable today on the status;
   the body shape is the one part of this contract that cannot be derived from the published
   docs, and the document says so rather than implying otherwise.

Test 28 asserts the status for all nine rows. Test 28a asserts the body is exactly those two keys
and that no third key has crept in, so if Wix later publishes an envelope the diff is one
function and one test.

### 1.2 The Cart V2 side

    POST https://www.wixapis.com/ecom/v2/carts/{cartId}/add-gift-card
    POST https://www.wixapis.com/ecom/v2/carts/{cartId}/remove-gift-card

https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/add-gift-card
https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/remove-gift-card

| | Add Gift Card | Remove Gift Card |
|---|---|---|
| operationId | `wix.ecom.cart.v2.CartService.AddGiftCard` | `wix.ecom.cart.v2.CartService.RemoveGiftCard` |
| permission | `ecom:v2:cart:add_gift_card` | `ecom:v2:cart:remove_gift_card` |
| scope | **Write Carts V2** | **Write Carts V2** |
| identities | `APP`, `MEMBER`, `VISITOR` | `APP`, `MEMBER`, `VISITOR` |
| maturity | `GA` | `GA` |

Add Gift Card's description, verbatim: *"Adds a gift card to the cart. Once added, the gift card
balance is used as a payment method during checkout, either partially or fully covering the cart
total."*

```
wix.ecom.cart.v2.AddGiftCardRequest
  cartId    string GUID    path parameter
  giftCard  GiftCardInput  REQUIRED
  required: ["giftCard", "giftCard.code"]

wix.ecom.cart.v2.GiftCardInput
  code          string           REQUIRED
  redeemAmount  ConvertedMoney   "The amount requested to redeem from this gift card."
                                 (within AddGiftCardRequest the inline schema reports
                                  code minLength 8, maxLength 20, matching the SPI)

wix.ecom.cart.v2.ConvertedMoney
  amount           string  format DECIMAL_VALUE  "Monetary amount in the original currency, as
                                                  specified in businessInfo.currencyCode."
  convertedAmount  string  format DECIMAL_VALUE  readOnly

wix.ecom.cart.v2.RemoveGiftCardRequest
  cartId      string GUID
  giftCardId  string GUID

wix.ecom.cart.v2.GiftCard
  id                     string GUID  "Unique identifier of the gift card within the cart."
  obfuscatedCode         string maxLength 50  "Partially masked gift card code."
  appId                  string GUID  "App ID of the gift card provider."
  externalId             StringValue  minLength 1, maxLength 50
  requestedRedeemAmount  ConvertedMoney  "Amount to redeem from this gift card."
```

Note the asymmetry that matters for §6.2: **Cart V2's `redeemAmount.amount` is a decimal
*string*, while the SPI's `amount` is a JSON *number*.** So `Money.to_wix()` is the correct
outbound converter on the cart path, and `parse_float=Decimal` plus an exact-two-places renderer
is required on the SPI path. Two different contracts for the same money, measured rather than
assumed.

`GiftCardInput.redeemAmount` is the lever that makes partial redemption a caller choice rather
than a Wix guess — §4.1 depends on it, and `redeemAmount` is **not** in the `required` array, so
omitting it asks Wix to apply what it can.

`GiftCard.obfuscatedCode` is "Partially masked gift card code": **Wix itself masks the code on the
cart entity**, which is independent corroboration that a gift-card code is bearer value and must
not be logged in full.

`wix.ecom.cart.v2.PaymentSummary`, the shape the two-leg model reads, with each description
verbatim:

```
giftCards                    array           "Per-gift card deduction amounts. Only one gift
                                              card is supported today."
memberships                  array           "Memberships charged with the order."
subscriptionCharges          array           "Subscription charge details for checkout."
requiresPaymentAfterGiftCard boolean         "Whether additional payment is required to create
                                              the order after gift cards."
totalAfterGiftCards          ConvertedMoney  "Total due after gift cards."
payNow                       ConvertedMoney  "Amount charged when the order is placed, after
                                              gift cards."
payLater                     ConvertedMoney  "Amount collected later."
payAfterFreeTrial            ConvertedMoney  "Amount charged after a free trial, often for
                                              subscriptions."

wix.ecom.cart.v2.GiftCardSummary
  giftCardId    string GUID     "Gift card ID assigned by the cart."
  redeemAmount  ConvertedMoney  "Amount to redeem from the gift card balance."
```

`requiresPaymentAfterGiftCard` is the field that answers "is there a Razorpay leg at all", and
`payNow` is its amount. Both are read; neither is trusted as the charged figure without the
reconciliation in §4.2.

Gift-card error data on these endpoints, from the methods' own `errors[]`:
`INVALID_GIFT_CARD_CODE` 400 (`InvalidGiftCardCodeErrorData`), `INVALID_GIFT_CARD_STATUS` 428
(`InvalidGiftCardStatusErrorData`, whose `InvalidGiftCardReason` enum is
`UNKNOWN_INVALID_GIFT_CARD_REASON | EXPIRED | DISABLED | EMPTY_BALANCE`),
`MAX_GIFT_CARDS_PER_CART_EXCEEDED` 428, `CART_ALREADY_ORDERED` 428, plus
`GiftCardAlreadyExistsErrorData`, `GiftCardRedeemErrorData {error}`,
`GiftCardNotFoundInCartErrorData` and `GiftCardPaymentNotSupportedOnDemoCartErrorData`.

**One gift card per cart**, quoted from the Cart V2 introduction: *"Carts currently support a
single coupon and a single gift card at a time. Attempting to add a second returns an error."*

`Estimate Cart`'s `calculateGiftCards` flag stays **false** on the pre-address view
(https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/estimate-cart):
that view is explicitly not a total, and surfacing a gift-card-reduced figure there would be a
number a customer could read as their price. `Calculate Cart` — which *"always runs checkout-level
validations"* and includes gift cards among its components — is the only place a gift card affects
a payable figure.

### 1.3 The decisive finding: Wix will never call our `/v1/redeem`

Read the three "when Wix calls it" rows in §1.1 against this architecture:

- **Get Balance** fires when a gift card is applied at checkout. We *do* apply one, with Cart V2
  `Add Gift Card`, and then read the figure from `Calculate Cart`. **So `/v1/balance` is live and
  load-bearing.** Without it registered and answering, Wix cannot value the card and the Wix-side
  total will not reflect it.
- **Redeem** fires "when a customer completes a purchase" — that is `Place Order`. We never call
  `Place Order`; its own description says *"Completes checkout and creates an order. This endpoint
  may charge the customer."* and its scope is `Write Carts V2 (PII)`, and `cart_v2.py` structurally
  omits it. **So Wix will never call `/v1/redeem` in this architecture.**
- **Void** fires "when a purchase fails after gift card redemption". No Wix redemption ever
  happens, so **`/v1/void` is likewise never called by Wix** in the live flow.

This is not a gap to work around; it is the reason the owner's instruction is the right one. The
redemption that moves money is **ours**, performed by our own Lambda against our own table at
finalization, after Razorpay capture is authoritatively verified. `/v1/redeem` and `/v1/void` are
still implemented to the letter, for three reasons:

1. A conforming plugin must implement the documented method set — the introduction marks all three
   handlers **Required: Yes** — and a partial implementation is a plugin Wix may reject at
   registration or call unexpectedly during preview.
2. If `Place Order` is ever adopted, the surface already exists and is correct.
3. **Defence in depth — but by refusal, not by a shared claim.** Revision 1 argued that both
   endpoints are idempotent on `(code, orderId)` against the same ledger our own redemption writes,
   so an unexpected Wix call could not double-spend. **That argument was wrong and is withdrawn**
   (HIGH-4): our `orderId` is a locally minted UUIDv7 (`order_keys.new_order_id` →
   `identifiers.new_uuid7`), while `RedeemRequest.orderId` is a **Wix** order GUID whose own
   description points at eCommerce Search Orders. For one purchase the two values differ, so
   `GCORDER#<codeHash>#<ourId>` and `GCORDER#<codeHash>#<wixId>` would never collide and the
   balance would be deducted twice. §3.4 replaces it with a claim keyed on our `paymentAttemptId`, a
   Wix-order pointer row, and a `/v1/redeem` that **refuses with `AlreadyRedeemed` (409) whenever
   any hold or claim exists for the card** rather than deducting. Since §1.3 predicts Wix never
   calls it, refusing costs nothing and removes the double-spend path entirely.
---

## 2. DECISION 2 — a gift card is a PAYMENT METHOD, not a discount

A coupon reduces the price. A gift card pays the price. The distinction decides the tax, and it
is not a stylistic choice.

**Under GST a voucher is consideration, not a reduction in the value of supply.** The customer
paid real money for the gift card; redeeming it is tendering that money. So the taxable supply
stays at its **full** value, and the 2.5% convenience fee and its 18% GST are computed on the
**full** collection total — never on the post-gift-card remainder. Seller GSTIN
`19AAFFW7196L1Z8`, as held in `checkout_pricing.SELLER_GSTIN`.

Worked example, integer paise throughout, against a ₹1,000.00 collection and a ₹400.00 card.
`CONVENIENCE_FEE_BPS = 250` and `CONVENIENCE_GST_BPS = 1800` over `RATE_DENOMINATOR = 10000`,
with `round_half_up`:

```
collection_before_convenience_paise = 100000        # FULL value, gift card not yet considered
convenience_fee_paise               =   2500        # round_half_up(100000 * 250 / 10000)
convenience_gst_paise               =    450        # round_half_up(  2500 * 1800 / 10000)
total_payable_paise                 = 102950        # 100000 + 2500 + 450

giftCardRedeemPaise                 =  40000        # the payment method
payNowPaise                         =  62950        # 102950 - 40000  -> Razorpay
```

The wrong version, recorded so it is recognisable in review: computing the fee on
`102950 - 40000` would give a fee of `1574` and GST of `283`, understating both and
mis-stating the taxable value of the supply. The fee basis is the collection total, full stop.

This also settles the question `cart_v2.py` left open. Its current refusal comment says the
convenience-fee basis "becomes undefined — is the 2.5% charged on the full collection total or on
the post-gift-card remainder? That is a commercial and GST question against seller GSTIN
19AAFFW7196L1Z8". **It is now answered: the full collection total.** That is the third of the three
conditions that comment requires before a gift card may pass; the other two are answered in §3
(authoritative verification of a non-Razorpay leg) and §4.4 (partial payment in scope for gift
cards only).

Consequences:

- `compute_quote` is called with the **full** collection and is **not changed**. The gift card is
  applied strictly *after* the quote, by splitting `total_payable_paise` into two legs.
- The quote identity `collection + fee + gst == total`, re-checked in
  `CheckoutQuote.__post_init__`, holds untouched, because a gift card never enters the quote.
- A new identity is introduced and must hold exactly:
  `payNowPaise + giftCardRedeemPaise == quote.total_payable_paise`.
- The receipt shows the full taxable value, the fee, the GST, and the gift card as a **tender
  line**, not a discount line. A gift card appearing as a discount would understate the taxable
  value on a document that has to be defensible.

---

## 3. DECISION 3 — two-leg finalization, with the gift-card leg carrying its own evidence

A gift card settles a leg that is **not** a Razorpay capture. The existing verification machinery
— the authoritative Razorpay captured-payment readback, `razorpay_verify`, and the
`PROVIDERPAYMENT#<txn>` one-time claim in `order_keys` — can only verify a Razorpay capture. It
is **left completely untouched**. The gift-card leg gets its own forward-only stage, its own
evidence, and its own idempotency claim.

### 3.1 The gift-card ladder

Its own ladder, in a new module, following the construction `payment_status`, `payment_attempt`,
`wa_status` and `rcs_status` all share: integer ranks, an attribute persisted so the guard is a
`ConditionExpression` rather than a read-then-write race, and unknown values ranking 0 so they
can overwrite nothing.

**The stage names and their ranks are separate objects, exactly as `payment_status` separates
them (closes MEDIUM-12).** Revision 2 presented the ladder as `GC_REDEEMED    50`, which reads as
a constant bound to an integer — and §3.2 then wrote `stage(attempt) != GC_REDEEMED`, comparing a
string against a name the ladder had defined as an int. That comparison is silently always-true,
which is the same shape of defect as the HIGH-1 bug revision 2 had just fixed. The repo convention
is unambiguous: `lambda_utils/payment_status.py` declares string values (`CAPTURED = "captured"`)
and a separate `STATUS_RANK: Dict[str, int]` (line 108) read through `rank()` (line 203), which
returns 0 for an unknown or missing status. This module mirrors it exactly:

```python
# gift_card_settlement.py -- the stage VALUES, which are what is compared
GC_UNKNOWN      = "GC_UNKNOWN"        # the attribute is absent, or a value this build knows not
GC_NOT_REQUIRED = "GC_NOT_REQUIRED"   # no gift card on this purchase; Razorpay is the whole payment
GC_HELD         = "GC_HELD"           # balance reserved against (codeHash, paymentAttemptId)
GC_REDEEMED     = "GC_REDEEMED"       # our redemption exists -- evidence: our own transactionId
GC_VOIDED       = "GC_VOIDED"         # the redemption was reversed

# the RANKS, which are what is persisted and what the ConditionExpression orders
STAGE_RANK: Dict[str, int] = {
    GC_NOT_REQUIRED: 10,
    GC_HELD:         20,
    GC_REDEEMED:     50,
    GC_VOIDED:       60,
}

def stage(attempt) -> str:          # the value, or GC_UNKNOWN
def stage_rank(attempt) -> int:     # STAGE_RANK.get(stage(attempt), 0)
```

`GC_UNKNOWN` is deliberately **absent from `STAGE_RANK`**, so `stage_rank` returns 0 for it
through the `.get` default — the same construction and the same reason as `payment_status.rank`'s
*"0 for unknown, missing, or `none`"*. An unknown stage can therefore overwrite nothing, which is
what makes a forward-only ladder safe across a deploy that adds a stage.

The ranks, and why each sits where it does:

| Stage | Rank | Evidence it carries |
|---|---:|---|
| `GC_UNKNOWN` | 0 | none; cannot overwrite anything |
| `GC_NOT_REQUIRED` | 10 | none needed; there is no second leg |
| `GC_HELD` | 20 | **none, deliberately** — a hold is a reservation, not a receipt |
| `GC_REDEEMED` | 50 | our own `giftCardTransactionId` and `giftCardRedeemedPaise` |
| `GC_VOIDED` | 60 | the void transaction id |

`GC_VOIDED` (60) **outranks** `GC_REDEEMED` (50), for exactly the reason `payment_status` ranks
`refunded` (60) above `captured` (50): a void strictly follows a redemption, so a replayed or
late redeem must not un-void a card. The reverse ranking is how a customer's balance silently
disappears.

`GC_HELD` (20) is below `GC_REDEEMED` and carries **no evidence**, deliberately. A hold is a
reservation, not a receipt — the same judgement that puts `authorized` (30) below `captured` (50)
in `payment_status`. Treating a hold as settlement is how an order gets marked paid against money
that was never deducted.

Persisted guard attribute: `giftCardStageRank` on the **payment attempt row**, holding the
**rank**, never the name. Condition expression, mirroring
`payment_status.condition_expression`'s shape:
`attribute_not_exists(giftCardStageRank) OR giftCardStageRank < :rank`.

Storing the rank rather than the name is what lets the guard be a single numeric comparison
inside DynamoDB. The *name* is derivable from it and is what every comparison in §3.2 uses, so
the two never both appear in one expression.

### 3.2 Fully paid requires BOTH legs — and absence means not-required

```python
#: The Razorpay leg's two evidence attributes, read through constants so a rename decided in
#: another session (see section 11) is one line here rather than a scatter of literals.
RAZORPAY_EVIDENCE_ATTR = "verifiedProviderPaymentId"   # written by finalization.record_paid
RAZORPAY_VERIFIED_PAISE_ATTR = "verifiedCapturedPaise"  # SEAM-G13; the amount Razorpay confirmed


def is_fully_settled(attempt) -> bool:
    """True only when every leg of the payable total has its own VERIFIED evidence.

    Never raises on a missing attribute. This function gates order completion, so an absent
    key must answer "not settled" rather than propagate a KeyError out of finalization after a
    capture has already been verified -- an exception there would strand a paid customer in an
    unhandled failure instead of a recoverable NEEDS_RECONCILIATION.
    """
    # Leg 1 -- Razorpay. Existing machinery, consulted and not reimplemented.
    if not payment_attempt.may_create_order(attempt):          # status in {PAYMENT_PAID}
        return False
    if not attempt.get(RAZORPAY_EVIDENCE_ATTR):
        return False
    # Leg 2 -- the gift card. Its own stage, its own evidence.
    required = int(attempt.get("giftCardRequiredPaise", 0) or 0)
    if required == 0:
        # ABSENCE IS THE NORMAL CASE. An ordinary Razorpay-only attempt carries no gift-card
        # attribute at all, so there is no second leg and nothing has to have been written.
        # A GC_HELD / GC_REDEEMED stage with required == 0 is a contradiction, and it fails
        # closed rather than being treated as a settled no-op.
        return stage(attempt) in (GC_NOT_REQUIRED, GC_UNKNOWN)
    if stage(attempt) != GC_REDEEMED:
        return False
    if not attempt.get("giftCardTransactionId"):               # OUR transaction id
        return False
    redeemed = int(attempt.get("giftCardRedeemedPaise", 0) or 0)
    if redeemed != required:
        return False
    # The closure: the two legs must account for the whole frozen payable, and the Razorpay
    # term is the amount the PROVIDER confirmed -- not the amount we asked for.
    verified = attempt.get(RAZORPAY_VERIFIED_PAISE_ATTR)
    if verified is None:
        return False          # unverifiable, therefore not settled. Never an exception.
    return int(verified) + redeemed == int(attempt["amountPaise"])
```

**Correction to revision 1 (closes HIGH-1).** The earlier version read
`stage_rank(attempt) >= GC_NOT_REQUIRED_RANK` in the `required == 0` branch. An ordinary attempt
carries no gift-card attribute, `stage_rank` is therefore 0, and `0 >= 10` is False — so **every
non-gift-card order would have been not-fully-settled**, and since SEAM-G5 gates order completion
on this function, the whole checkout would have halted once wired. The ranks are unchanged;
`GC_NOT_REQUIRED` stays at 10 for rows that carry it explicitly. What changed is that the common
path is a membership test including `GC_UNKNOWN`, so **no write is required on the common path at
all**. Test 56 asserts an attempt dict holding only the Razorpay attributes is fully settled.

**A partially-settled order can never be marked fully paid on the Razorpay leg alone.** That is
the property this function exists to make structural: when `giftCardRequiredPaise > 0`, a verified
Razorpay capture is necessary and *not sufficient*, and the second condition cannot be satisfied
without our own redemption transaction id existing in our own table.

The amount checks matter as much as the stage check. A stage of `GC_REDEEMED` with a short
`giftCardRedeemedPaise` is a partially-settled order wearing a settled label.

#### The closure now compares a VERIFIED capture, not an intended one (closes HIGH-2, HIGH-3 and MEDIUM-16 together)

Revision 2's final line was `int(attempt["razorpayChargedPaise"]) + required == payable`, and it
had three separate problems that turn out to be one problem:

- **HIGH-3: it proved nothing about Razorpay.** `razorpayChargedPaise` and
  `giftCardRequiredPaise` are both written at checkout, by the same code, in the same request,
  from the same split. Their sum re-deriving the payable proves the split was internally
  consistent when written — arithmetic, not evidence. The gift-card leg was correctly evidenced
  by `giftCardTransactionId`; the Razorpay leg's *amount* was asserted.
- **HIGH-2: the attribute it read had no permitted writer.** §6.5's table enumerates the
  attributes `advance()` may write and `razorpayChargedPaise` is not among them; §7.3 declares
  that evidence set **closed**, so the only named writer could not write it. And the access was a
  bracket subscript, so a gift-card attempt missing it raised `KeyError` **inside finalization,
  after a verified capture** — an unspecified failure in the one function that decides whether an
  order is paid.
- **MEDIUM-16: its stated justification was false.** Revision 2 said `amountPaise` "is already
  covered by `quoteHash` on the attempt row". Measured, `quoteHash` is **not on the attempt row**:
  `checkout/handler.py` puts `quoteHash=snapshot.snapshot_hash` into `extra`, and `extra` is
  passed to `order_keys.allocate_payment_reference`, which stores it on the **`PAYREF#` row in
  the commerce keys table**. The attempt's hash attribute is `snapshotHash`, written only by
  `initiation.reserve` (`snapshotHash=fingerprint(snapshot)`) — a different producer hashing a
  different object — and read by `finalization.accept_paid`. `_create` writes no hash to the
  attempt at all. So nothing bound `amountPaise` on the row either.

**One change fixes all three: read the verified figure.** The only amount verification that exists
in this tree compares a provider readback against something stored:

```
website_checkout.py:430   captured, provider_payment_id, amount_paise, currency = verify_capture(...)
website_checkout.py:434   if amount_paise != stored_amount or currency != stored_currency:
website_checkout.py:436       return CallbackResult(status=CALLBACK_BINDING_MISMATCH)
razorpay-webhook/handler.py:952   if provider_paise != intent_paise:        # NOT a checkout path
```

> **The webhook comparison is on the PARTNER WALLET TOP-UP path, not a checkout path (resolves
> R4-N2).** Revision 3 cited it at line 947 and offered it, beside `website_checkout.py`, as one of
> only **two** amount verifications in the tree — which makes the flow it sits on load-bearing rather
> than incidental. Measured: it is at **952**, and the branch it guards logs
> `partner_wallet_topup_amount_mismatch` with `'stage': 'wallet_topup'`, comparing the provider's
> capture against the amount a **wallet top-up** was created for.
>
> So the honest count is: **one amount verification exists on a checkout path** — `website_checkout`'s
> `verify_capture` comparison — and the second is the same discipline applied to a different flow,
> cited as precedent for the shape rather than as coverage of checkout. That strengthens the argument
> for SEAM-G13 rather than weakening it: there is **no** amount verification on the in-WhatsApp
> checkout path at all, and `checkout/handler.py::_create` is one of the attempt producers §8 lists.

Neither value reaches the attempt row. **SEAM-G13** closes that: `finalization.record_paid`
already writes `verifiedProviderPaymentId` in a single conditional `UpdateExpression`, and the
same expression carries `verifiedCapturedPaise` beside it — one attribute, one seam, written at
the only moment a capture amount is known to be authoritative:

```python
# finalization.record_paid, SEAM-G13: one added assignment and one added parameter
def record_paid(attempts, attempt, provider_payment_id, captured_paise):
    UpdateExpression='SET #s = :paid, ..., verifiedProviderPaymentId = :provider, '
                     'verifiedCapturedPaise = :captured'
```

> **WHO PRODUCES `captured_paise`, stated — revision 3 specified the parameter and not its producer
> (resolves R4-M1).** `record_paid`'s only caller is
> `accept_paid(*, attempts, orders, keys, attempt, outcome)`, and **no captured-amount field on
> `outcome` was named anywhere in revision 3**. So the entire HIGH-3 resolution — the verified figure
> both legs close against — had no specified producer at the point it enters the row, which is the one
> place it has to come from.
>
> **`outcome` gains `verifiedCapturedPaise`**, written by the caller from the **same `razorpay_verify`
> readback that produced `outcome['providerPaymentId']`**. Concretely: `website_checkout.py:430`'s
> `amount_paise` on the website path, or the webhook's `provider_paise` on a webhook-driven path. The
> two are one fact read at one instant, which is exactly why they travel together and why neither is
> re-derived later.
>
> **`record_paid` REFUSES a call carrying a provider id without an amount.** Not a default, not a
> zero, not a `None` written through — a raise. The failure mode being closed is specific: a caller
> that passes the provider id and omits the amount writes `verifiedProviderPaymentId` and leaves
> `verifiedCapturedPaise` absent, and `is_fully_settled` then reads `verified is None` and returns
> `False` **forever** on a genuinely paid order. That is a silently stuck order rather than a loud
> one, so it fails at the write instead.
>
> `gift_card_settlement` reads both through `RAZORPAY_EVIDENCE_ATTR` and
> `RAZORPAY_VERIFIED_PAISE_ATTR`, so if another session renames either attribute this document's
> dependency is **one line**, not a scatter of literals. The rename fallback is in §11's table.

Three properties follow, and each is the point:

1. **The two legs now carry symmetric evidence.** `verifiedProviderPaymentId` +
   `verifiedCapturedPaise` on one side, `giftCardTransactionId` + `giftCardRedeemedPaise` on the
   other. Neither side is asserted.
2. **`razorpayChargedPaise` is no longer read by any settlement decision**, so HIGH-2's
   "attribute with no permitted writer" simply dissolves. It survives as a checkout-time audit
   record — *what we asked the gateway for* — written on the attempt dict by the checkout
   producer beside `attempt["checkoutMode"]` (§6.5), and compared against
   `verifiedCapturedPaise` by reconciliation rather than by this function. A disagreement between
   them is a real finding and §6.5 gives it a metric.
3. **The missing-attribute case is specified, not incidental.** `verified is None` returns
   `False`. An unverifiable order is not a settled order, and it is not an exception either.

The compounding MEDIUM-16 identified is therefore also closed: with the verified capture on the
row, the binding no longer depends on a hash at all. The number being checked is the one the
provider reported, so tampering with the stored split cannot make it agree — reduce
`razorpayChargedPaise` and nothing reads it; reduce `giftCardRequiredPaise` and `redeemed !=
required` fails; reduce `amountPaise` and the sum fails against the real capture.

Test 83 drives a tampered `redeemAmount` through both gates. Test 83a asserts `is_fully_settled`
returns `False` rather than raising when `verifiedCapturedPaise` is absent, and test 83b asserts
the same for an absent `amountPaise`.

### 3.3 Where it sits relative to the Razorpay leg

Ordering is fixed and is not symmetric:

1. **Hold** the gift-card balance at checkout initiation (`GC_HELD`), before the gateway is
   addressed. A hold is reversible; a capture is not. Holding first means a card whose balance has
   since been spent elsewhere refuses the checkout *before* the customer is charged for the
   remainder.
2. **Razorpay captures `payNowPaise`** and is verified by the existing, untouched machinery, which
   takes `PROVIDERPAYMENT#<txn>` and reaches `PAYMENT_PAID`.
3. **Redeem** the held balance (`GC_REDEEMED`), recording our own transaction id. Only now is
   `is_fully_settled` capable of returning True.
4. Order creation and writeback proceed as they already do.

Step 3 after step 2 is deliberate. If the gateway fails, the hold is released and nothing was
deducted. If step 3 fails after a verified capture, the order is `NEEDS_RECONCILIATION` with the
hold intact and the customer's card untouched — recoverable by replay, because the redemption is
idempotent. The opposite order would deduct from a card for a payment that then failed, which
needs a void to undo and is the case Wix's own `/v1/void` exists for.

### 3.4 Idempotency: one redemption per (code, purchase) — keyed on the PAYMENT ATTEMPT

**Revision 3 re-keys this again.** The claim row is:

    GCORDER#<codeHash>#<paymentAttemptId>

Revision 1 keyed it on `orderId`, which HIGH-4 correctly rejected because our `orderId` and
`RedeemRequest.orderId` are two different namespaces. Revision 2 moved it to `referenceId` and
justified that with two claims. **Both are wrong, and neither was in the review — they surfaced
from reading `website_checkout.py` while closing HIGH-1.**

**Wrong claim 1: that `referenceId` is one thing.** It is two, depending on which producer built
the attempt:

```
checkout/handler.py::_create          reference_id = order_keys.allocate_payment_reference(...)
                                      -> "WD-PAY-" + 14 CSPRNG symbols
website_checkout.py::_bind_and_ready  payment_attempt.build(..., reference_id=gateway_order_id, ...)
                                      -> the RAZORPAY gateway order id
```

So on the website path — the path both documents declare the active architecture —
`attempt["referenceId"]` **is the Razorpay order id**. That is fatal for a hold key, because
§3.3 step 1 requires the hold to be taken *before* the gateway is addressed, and the gateway
order id does not exist until after. A hold keyed on it could only ever be taken too late.

**Wrong claim 2: that it is "stable across retries of the same basket".** It is not, on either
path. `_create` mints a fresh `allocate_payment_reference` on every call, so a customer who
retries gets a new `WD-PAY-`. The website path is the *more* stable of the two, and only because
`reserve_checkout_request_key` collapses concurrent clicks onto a stored `paymentAttemptId`.

**`paymentAttemptId` satisfies every requirement the claim key actually has**, and it is minted
in the same place on both producers — before any external call:

| Requirement | `paymentAttemptId` |
|---|---|
| exists **before** the gateway is addressed, so the hold can precede the charge | `payment_attempt.new_payment_attempt_id()` is the first thing both producers mint: `checkout/handler.py` at step 3, `website_checkout.py` at step 3 **before** `reserve_checkout_request_key` |
| collapses concurrent clicks onto one purchase | on the website path `reserve_checkout_request_key` returns the existing reservation's `paymentAttemptId` on a lost race, and `prepare_checkout` adopts it |
| reachable from the finalization path | `attempt["paymentAttemptId"]` is the `Key` of every `update_item` in `finalization.record_paid` and `_stage` |
| already the key `advance()` writes by | `advance(attempts, *, attempt_id, ...)` — so the ledger claim and the stage attributes share one identifier and need no join |
| safe to log in full | a UUIDv7, documented in `payment_attempt.new_payment_attempt_id` as *"Internal identifier. UUIDv7, never shown to a customer"* — opaque, not a secret, not a phone number |

The last row matters as much as the first: because the gift-card code can never be logged, the
correlation id has to be something else, and this one is already in every log line finalization
writes.

**What a retry on a new attempt means, stated rather than hand-waved.** A second checkout of the
same basket mints a new `paymentAttemptId`, so it is a *different* claim key — the claim does not
make it idempotent. Two things make it safe anyway, and they are the right two:

1. **The hold refuses it.** The first attempt's `GCHOLD#<codeHash>#<paymentAttemptId>` is still
   live, so the second attempt's hold fails with `HELD_BY_ANOTHER_PURCHASE` (§7.4) and the
   checkout refuses before anything is charged. Hold expiry handles the abandoned case.
2. **Only one attempt can ever reach a verified capture for one basket.** Redemption happens
   *after* capture (§3.3 step 3), and the existing untouched machinery already guarantees one
   capture settles at most one order — `PROVIDERPAYMENT#<txn>` is a one-time claim and
   `ORDERNO#` is reserved conditionally. A second redemption would require a second real
   payment, which is a second purchase and *should* deduct again.

So the claim row makes a **replay** idempotent, and the hold plus the single-capture guarantee
make a **retry** safe. Revision 2 attributed both jobs to the claim key, which is why it needed
a stability property no identifier on this path has.

A Wix-originated call still needs resolving, and the pointer row is unchanged in purpose:
`GCWIXORDER#<wixOrderId> → paymentAttemptId`, written at writeback time, since the
`WIX_ORDER_CREATED` stage already carries `wixOrderId`
(`finalization._stage(..., 'WIX_ORDER_CREATED', wixOrderId=wix['wixOrderId'])`) — SEAM-G10.

The claim is written with `ConditionExpression: attribute_not_exists(giftCardKey)` **before** the
balance is decremented, and it carries the `transactionId` of the redemption that won.

- A duplicate redeem for the same `(codeHash, paymentAttemptId)` loses the conditional put, reads
  the winning row, and returns **that same `transactionId`** with the balance untouched.
- **A Wix `/v1/redeem` refuses rather than deducts.** If any `GCHOLD#<codeHash>#*` or
  `GCORDER#<codeHash>#*` row exists for that card, the SPI returns the documented
  `AlreadyRedeemed` (409, `ALREADY_EXISTS`, `applicationCode: ALREADY_REDEEMED`). This is stricter
  than idempotency and deliberately so: §1.3 predicts Wix never calls this endpoint, so a refusal
  costs nothing real, and it removes the two-namespace double-spend entirely rather than relying on
  a pointer row having already been written. The pointer row still exists, because it is what lets
  a *void* arriving by transaction id be reconciled back to a purchase.

  Note this refusal is **why the two-namespace problem stays closed under the re-key**. Wix's
  `orderId` and our `paymentAttemptId` are no more comparable than Wix's `orderId` and our
  `orderId` were, so the guard cannot be a shared claim key under any naming. It has to be the
  existence check, and the existence check is keyed on the **card** (`GCHOLD#<codeHash>#*`),
  which is the one thing both sides agree on.
- A `/v1/redeem` for a card with **no** hold and no claim is honoured and recorded with
  `source: "WIX_SPI"`, because refusing it would make the plugin non-conforming in the one
  scenario where Wix legitimately owns the flow.

The balance decrement is a single atomic `UpdateExpression: ADD balancePaise :neg` guarded by
`ConditionExpression: balancePaise >= :amount`. A read-then-write would let two concurrent
redemptions both pass a `balance >= amount` check and overdraw the card.

---

## 4. Amounts, and the two cases this release refuses

### 4.1 The split, with a floor on the Razorpay leg

```
RAZORPAY_MIN_LEG_PAISE = 100        # Razorpay's documented minimum order amount; see below

wixCollectionPaise = Money.from_wix(cartSummary["priceSummary"]["total"]["amount"]).paise
quote              = compute_quote(wixCollectionPaise)              # FULL collection, §2

# DECISION (HIGH-4): the gift card funds the SUPPLY only, never the convenience fee.
# The cap is against the WIX cart total, because Wix is the only thing that can redeem it.
# DEFINED EXACTLY ONCE, in gift_card_store.redeem_cap (R4-H4 / DECISION 10). Both the §7.5
# validator and this split call that one function; neither restates the arithmetic.
redeemCap           = gift_card_store.redeem_cap(balance_paise=balancePaise,
                                                 wix_collection_paise=wixCollectionPaise)
#                   == min(balancePaise, wixCollectionPaise - RAZORPAY_MIN_LEG_PAISE)
giftCardRedeemPaise = requestedRedeemPaise if given else redeemCap
payNowPaise         = quote.total_payable_paise - giftCardRedeemPaise
#                   == (wixCollectionPaise - giftCardRedeemPaise)   <- remaining supply
#                    + quote.convenience_fee_paise                  <- always Razorpay's
#                    + quote.convenience_gst_paise                  <- always Razorpay's
```

#### The gift card funds the supply only (closes HIGH-4) — and `redeem_cap` is now defined ONCE (resolves R4-H4)

> **R4-H4: revision 3 fixed this definition here and then contradicted it in §7.5.** §4.1 capped
> against the Wix collection total; §7.5 — **the table a coder implements input validation from** —
> said `min(balance, payable - 100)`. `payable` exceeds `wixCollectionPaise` by the convenience fee
> and its GST, so §7.5 **admitted a redemption Wix cannot apply**: §4.2 identity 1 then fails and the
> checkout refuses *after the request has reached Wix*. That is the exact defect §4.1 says it removed,
> reintroduced one section later by the document that removed it.
>
> **Resolution: one definition, in code, with two callers.**
>
> ```python
> # gift_card_store.py
> RAZORPAY_MIN_LEG_PAISE = 100
>
> def redeem_cap(*, balance_paise: int, wix_collection_paise: int) -> int:
>     return min(balance_paise, wix_collection_paise - RAZORPAY_MIN_LEG_PAISE)
> ```
>
> §7.5's parenthetical is replaced by a reference to this function, and **a test asserts the
> validator and the split both call that one function** rather than both computing the same
> expression — because two correct copies of an expression is how this finding happened.

Revision 2 set `redeemCap = min(balancePaise, quote.total_payable_paise - RAZORPAY_MIN_LEG_PAISE)`
and, three sections later, required
`cartSummary.paymentSummary.giftCards[0].redeemAmount == giftCardRedeemPaise` to hold or the
checkout fails closed. **Those two cannot both be satisfied**, and §12.2 item 4 asserted the
opposite of what the code would do.

The reason is that the convenience fee does not exist on the Wix cart. It reaches Wix only at
`Create Order`, as `additionalFees[]` (coupon document §2.3). So `quote.total_payable_paise`
exceeds the Wix cart total by the fee and its GST — 102950 against 100000 in §2's example — while
Wix can only apply a gift card against **its own** total. A redemption of 102000 paise sits
inside revision 2's `redeemCap` of 102850, above the Wix total of 100000, and Wix reports at most
what it could apply. The identity then fails and the checkout refuses — exactly the case §12.2
item 4 claimed the design permitted.

**Chosen: option (a), the gift card funds the supply only.** Three reasons, in order of weight:

1. **It makes the reconciliation identity exactly right rather than approximately right.** With
   `giftCardRedeemPaise <= wixCollectionPaise - 100`, Wix can always apply the full requested
   amount, so `redeemAmount == giftCardRedeemPaise` is a true equality and a disagreement is a
   real fault worth failing closed on. Under option (b) the identity has to become a `min(...)`
   plus a second identity bounding the fee-funded remainder, and a fail-closed comparison whose
   two sides are allowed to differ is a weaker instrument.
2. **The convenience fee is our charge, not part of the supply**, and a voucher is consideration
   for the supply (§2). Tendering a gift card against our own service fee is a different
   transaction from tendering it against the goods, and the receipt would have to say so.
3. **It keeps the Razorpay leg carrying part of the supply, not merely our fee.** That preserves
   §4.4's substance: the authoritative provider readback is evidence about the *purchase*, not
   about a 2.5% surcharge on it.

The cost, stated: a customer holding a card worth more than the cart cannot spend the surplus on
the fee, and will see a small Razorpay charge they might have expected the card to cover. That is
the trade, and §12.2 item 4 now records the answer as **no** rather than yes.

**The floor is applied against the Wix collection total**, not the payable, which is what makes
`redeemCap` and the identity agree. One consequence worth naming: because the fee leg always
remains on Razorpay, `payNowPaise` is now `>= 100 + fee + gst` whenever a card is applied, so a
full-cover-of-the-payable request is **unrepresentable by construction** rather than merely
refused. §4.4's explicit checks are retained anyway, as the backstop against a Wix view we did
not predict.

The floor is still needed separately, for a small cart: at a collection of 300 paise the fee is
8 and its GST is 1, so a redemption at `redeemCap` leaves `100 + 8 + 1` — fine — but an
arbitrary `requestedRedeemPaise` could still leave a sub-100 remainder, which §7.5 refuses with
`GIFT_CARD_LEAVES_UNCHARGEABLE_REMAINDER` before the hold is taken.

Boundary tests: 96 at `redeemCap` (accepted), 97 at `redeemCap + 1` (refused), 97a at
`wixCollectionPaise` and 97b at `wixCollectionPaise + 1` (both refused, before Wix is consulted)
— the last two being the pair HIGH-4 asked for by name, since that is where revision 2's cap and
identity diverged.

**`RAZORPAY_MIN_LEG_PAISE = 100`, with a citation (closes MEDIUM-13).** Razorpay's Orders Create
reference documents the failure verbatim under *"The amount must be at least INR 1.00"*: *"The
amount specified is less than the minimum amount. Currency subunits, such as paise (in the case of
INR), should always be greater than 100. Solution: Enter an amount equal to or greater than the
minimum amount, that is 100."* — with `Code: 400`, and the error body
`{"error": {"code": "BAD_REQUEST_ERROR", "description": "The amount must be at least INR 1.00",
"source": "business", "step": "payment_initiation", "reason": "input_validation_failed",
"field": "amount"}}`. https://razorpay.com/docs/api/orders/create/

Without the floor, a gift card could leave a 1-paise Razorpay leg that the gateway rejects at
`payment_initiation` — *after* the hold was taken and the quote frozen, which is the worst place
for it. Refusing before the hold turns a mid-flight gateway rejection into a clean pre-hold
refusal with nothing to unwind.

**`redeemCap` expresses the release's actual limit (closes MEDIUM-17 from the first pass).**
Revision 1 set `redeemCap = min(balancePaise, quote.total_payable_paise)`, which admitted a
request exactly equal to the total — the one case §4.4 exists to refuse — while also insisting a
value above the cap is "refused, never clamped". Subtracting the floor makes the cap and the
refusal agree; revision 3 additionally changes *which total* the floor is subtracted from, per
HIGH-4 above. §4.4's `requiresPaymentAfterGiftCard` check stays as the fail-closed backstop
against a Wix view we did not predict. The boundary tests are **96** and **97**, not 85 and 86 —
test 85 is `test_nothing_here_writes_the_razorpay_machinery` (closes NIT-21, which caught this
stale cross-reference).

`requestedRedeemPaise` is a customer choice, carried to Wix as `GiftCardInput.redeemAmount` (a
decimal **string**, §1.2). It is validated as integer paise, `0 < v <= redeemCap`. A request above
the cap is refused with `GIFT_CARD_REDEEM_ABOVE_CAP`, never silently clamped: silently clamping
means the figure the customer agreed to is not the figure applied. A request that would leave
`0 < payNowPaise < RAZORPAY_MIN_LEG_PAISE` is refused with
`GIFT_CARD_LEAVES_UNCHARGEABLE_REMAINDER` before the hold is taken.

### 4.2 Reconciliation against Wix, and the snapshot binding

Wix computes its own view, and the two must agree before anything is charged:

**Every identity is in integer paise, with the converter written on every Wix term (closes
MEDIUM-11).** Revision 2 wrote `giftCards[0].redeemAmount == giftCardRedeemPaise`, comparing a
`ConvertedMoney` **object** against an `int`, and
`Money.from_wix(payNow.amount).paise + giftCardRedeemPaise == cartSummary.priceSummary.total`,
comparing paise against a `ConvertedMoney`. Both are always-false; neither would have failed
closed, they would have failed *always*. `ConvertedMoney.amount` is a decimal **string**
(`format: DECIMAL_VALUE`, §1.2), so `Money.from_wix` is required on every one, and applying it is
also what proves the field was a string:

```python
payment = cartSummary["paymentSummary"]
prices  = cartSummary["priceSummary"]

wixCollectionPaise = Money.from_wix(prices["total"]["amount"]).paise
wixAppliedPaise    = Money.from_wix(payment["giftCards"][0]["redeemAmount"]["amount"]).paise
wixPayNowPaise     = Money.from_wix(payment["payNow"]["amount"]).paise

# 1. Wix applied exactly what we asked for. An exact equality, which is only sound because
#    HIGH-4 caps the request at the Wix total; it would be unsatisfiable otherwise.
wixAppliedPaise == giftCardRedeemPaise

# 2. Wix's own arithmetic closes against Wix's own total.
wixPayNowPaise + giftCardRedeemPaise == wixCollectionPaise

# 3. Wix agrees a further payment is due, and agrees on its size.
payment["requiresPaymentAfterGiftCard"] is True
wixPayNowPaise == wixCollectionPaise - giftCardRedeemPaise      # redundant with 2, asserted anyway

# 4. OUR arithmetic closes against OUR payable, which includes the fee Wix cannot see.
payNowPaise + giftCardRedeemPaise == quote.total_payable_paise

# 5. The remaining Razorpay leg is chargeable.
payNowPaise >= RAZORPAY_MIN_LEG_PAISE

# 6. The fee is entirely on the Razorpay leg (HIGH-4's decision, asserted not assumed).
payNowPaise - wixPayNowPaise == quote.convenience_fee_paise + quote.convenience_gst_paise
```

A disagreement on any line **fails closed** and the checkout refuses, per R6.2 — a one-paise
mismatch against the authoritative total must refuse the order rather than charge an amount
nobody computed.

Identities 2 and 4 use different totals and both are correct: Wix's `payNow` is against Wix's
collection total, which excludes our convenience fee, while our `payNowPaise` is against the full
payable, which includes it. Identity 6 is what pins the difference between them to exactly the
fee and its GST — under HIGH-4's decision the gift card never funds the fee, so that difference is
a constant of the quote rather than something that varies with the redemption. Revision 2 said the
fee was "funded by whichever leg has room", which is the sentence HIGH-4 removes.

**The gift-card leg must not sit outside the anti-tamper binding (closes MEDIUM-8).**
`purchase_intent.build_intent` freezes the quote into a `QuoteSnapshot` whose `snapshot_hash`
covers customer, site, cart id, cart revision, items, address, delivery and the rounded quote
components, and it asserts
`quote.collection_before_convenience_paise == calculated["amountPaise"]` as integer equality.
`giftCardRedeemPaise` is computed *after* that and is in no hashed field, so without a decision the
one number that decides how much Razorpay collects would be the only amount on the path with no
snapshot binding.

Two options were available: fold a `giftCard` component into the snapshot inputs, or require
finalization to re-derive the split from the frozen quote. **Chosen: re-derive at finalization.**
Folding it in would mean `build_snapshot`'s payload gaining a field, and `build_snapshot` lives in
`checkout_pricing.py`, which is read-only here — so option one is a cross-workstream edit to the
module this design most wants to leave alone. Re-derivation needs nothing but our own code and
one added attribute (SEAM-G13):

> `is_fully_settled` re-derives `verifiedCapturedPaise + giftCardRedeemedPaise ==
> int(attempt["amountPaise"])`, where `verifiedCapturedPaise` is the amount **Razorpay's own
> readback reported** and `giftCardRedeemedPaise` is the amount **our ledger actually moved**.

**Correction to revision 2's justification (closes MEDIUM-16).** Revision 2 wrote that
`amountPaise` "is already covered by `quoteHash` on the attempt row", and made that the sole
reason for preferring re-derivation. Measured, `quoteHash` is **not on the attempt row at all**:

```
checkout/handler.py   extra.update(... quoteHash=snapshot.snapshot_hash ...)
                      reference_id = order_keys.allocate_payment_reference(..., extra=extra)
                      -> allocate_payment_reference stores `extra` on the PAYREF# row in the
                         commerce keys table, NOT on the attempt
initiation.py:69      snapshotHash=fingerprint(snapshot)        <- a DIFFERENT producer,
                                                                   hashing a DIFFERENT object
finalization.py:55    if ... not attempt.get('snapshotHash')    <- the only hash read off an attempt
```

So `_create` writes no hash to the attempt; the attempt's hash attribute is `snapshotHash`, and
only `initiation.reserve` writes it. Revision 2's binding did not exist.

**The resolution does not need it to.** With `verifiedCapturedPaise` on the row, the number being
checked is the one the provider reported, so no hash is required to bind the split after it is
written — the provider's own readback is the binding. That is strictly stronger than a hash over
our own intent, which is what MEDIUM-16 meant by noting the two findings compound: revision 2 had
neither a hash on the attempt **nor** a verified capture amount, so nothing bound the split at
all.

A tampered `redeemAmount` therefore cannot reach a settled order by either route: the §4.2
reconciliation refuses it before the hold, and if the split were altered after the quote was
frozen, `is_fully_settled` fails against the real capture. Test 83 drives it through both gates
and asserts a refusal at the earlier one and `False` at the later one.

### 4.3 Only one gift card

`PaymentSummary.giftCards` is documented *"Only one gift card is supported today"*, and the Cart V2
introduction says *"Carts currently support a single coupon and a single gift card at a time.
Attempting to add a second returns an error."* We enforce one and refuse a second with
`GiftCardAlreadyExistsErrorData`'s semantics rather than discovering the Wix limit at runtime.

### 4.4 A gift card may NOT cover the whole total in this release

If `giftCardRedeemPaise == quote.total_payable_paise`, there is no Razorpay capture, and therefore
**no provider readback at all** — the entire authoritative verification path this system has is
Razorpay's. An order settled wholly on our own ledger, verified only by our own write, is a
different trust model and is out of scope here.

So this release refuses it, surfacing `GIFT_CARD_COVERS_FULL_TOTAL`. The refusal has two
independent triggers and that redundancy is the point:

1. `redeemCap` (§4.1) makes a full-cover request unrepresentable, refused with
   `GIFT_CARD_REDEEM_ABOVE_CAP` before Wix is consulted.
2. `paymentSummary.requiresPaymentAfterGiftCard is not True` refuses, as the fail-closed backstop
   against a Wix view we did not predict. **Absence is treated as `False` and therefore refuses**
   (closes part of MEDIUM-9): a cart summary that does not carry the field has not told us there is
   a Razorpay leg, and inferring one from `payNow` alone would be exactly the kind of guess R6.2
   forbids. `cart_v2.py` also records that Wix *"omits the payment gateway order id entirely when
   a gift card covers the whole total"*, which is corroboration, not the detector.

To lift it the owner must decide what authoritatively verifies a wholly self-settled order. That
is a trust decision, not an implementation detail, and it is named in §12.

### 4.5 Partial payment: giftCards only. The other two stay shut

`cart_v2.calculate` currently refuses all three of `giftCards`, `memberships` and
`subscriptionCharges` in one check, then requires `payNow == totalAfterGiftCards == total`.
**Only `giftCards` is permitted by this design.** Memberships and subscription charges remain
refused, for their own untouched reasons: each would be a further non-Razorpay rail with no
verification story, and a subscription additionally implies recurring collection, which no part of
this architecture is built for.

The narrowing is **SEAM-G1** (§10) because `cart_v2.py` is owned elsewhere. The required change is
precisely: drop `giftCards` from that tuple, keep `memberships` and `subscriptionCharges`, and
replace the `payNow`/`totalAfterGiftCards` equality with the §4.2 identities. Do **not** open the
gate for the other two. Test 87 pins it.
---

## 5. DECISION 4 — SPI authentication is Wix's documented JWT, and the body IS the token

The endpoint is called **by Wix**, so there is no shared secret we hand out and no signature
scheme of our own. Wix documents exactly one model, and it is implemented verbatim. Quoted from
the self-managed service-plugin REST guide:

> It's important to note before getting started that your implementation must match the API
> specification exactly as documented. This ensures that as a service provider, Wix can use your
> response in its flow. This integration includes the request envelope and signature validation as
> follows:
>
> **Request envelope.** Each request that your endpoint receives is wrapped in an envelope with
> metadata and signed. The payload that your endpoint receives is in JSON web token (JWT) format,
> with the following structure:
>
> ```json
> {
>   "data": {
>     "request": {/*as specified in the service plugin reference*/},
>     "metadata": {/*as explained below*/}
>   },
>   "aud": "<your application's appId>",
>   "iss": "wix.com",
>   "iat": <issue timestamp>,
>   "exp": <expiration timestamp>
> }
> ```
>
> **Validating request signatures.** As explained above, the request payload is a signed JWT. To
> avoid an attack where a malicious 3rd party is sending you requests pretending to come from Wix,
> you must verify the JWT, as follows:
> - Verify the JWT signature using your public key from your app's dashboard.
> - Verify that the `aud` claim matches your application ID.
> - Verify that the `iss` claim is set to `wix.com`.
> - Verify that the `iat` claim is set to a timestamp *before* the current timestamp on your server.
> - Verify that the `exp` claim is set to a timestamp *after* the current timestamp on your server.
>
> We recommend that you use a standard library to parse and validate the JWT.
>
> — https://dev.wix.com/docs/build-apps/develop-your-app/frameworks/self-hosting/supported-extensions/backend-extensions/add-self-hosted-service-plugin-extensions-with-rest

The same page's envelope attribute list, verbatim: `requestId` (*"Unique identifier of the
request. You may print this ID to your logs to help with future debugging and easier correlation
with Wix's logs."*), `instanceId`, `currency` (ISO 4217), `languages` (`"en-US"` form), and
`identity` with `identityType ∈ {ANONYMOUS_VISITOR, MEMBER, WIX_USER, APP}` plus
`anonymousVisitorId` / `memberId` / `wixUserId` / `appId`.

**Two corrections to revision 1, both measured.**

First, **the SPI request object is at `data.request`, not at the token root.** Revision 1 described
an envelope of `{request, metadata}` and attributed it to a
`wix.gift.cards.provider.api.v1.GiftCardProvider.RedeemEnvelope` component. No such component
exists in the fetched service schema — the schema's components are
`wix.common.spi.Context`, `wix.common.spi.Context.IdentificationData`,
`...IdentificationData.id` and `...IdentityType`. So the envelope shape comes from the REST guide
quoted above, which nests both under `data`, and `metadata`'s shape is `wix.common.spi.Context`
from the service schema. A verifier that looked for `request` at the root would read `None` on
every live call.

```
<JWT payload>
  data
    request   : GetBalanceRequest | RedeemRequest | VoidRequest     (§1.1)
    metadata  : wix.common.spi.Context
  aud  : our appId
  iss  : "wix.com"
  iat  : int
  exp  : int

wix.common.spi.Context
  requestId   StringValue
  currency    StringValue
  identity    Context.IdentificationData { identityType, + oneOf anonymousVisitorId |
                                           memberId | wixUserId | appId }
  languages   array of string
  instanceId  StringValue
```

Second, **the raw request body IS the JWT (closes MEDIUM-18).** The introduction article's own
example shows it unambiguously — and the example is the **app-install instance-id callback**
(`POST /wix-spi/account-ids`), **not** a Get Balance, Redeem or Void call (citation corrected per
R4-M4) — a `POST` whose `Content-Type` is `plain/text` and whose `-d` argument is a bare `eyJ...`
token:

> ```curl
> $ curl -X POST https://ext-server.com/wix-spi/account-ids
> -H 'Content-Type: plain/text'
> -d 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpbnN0YW5jZUlkIjoiMDQ0NjY3ZjQtYzEzZi00NmMyLTg1MDYtZGU5ZTQyMjkzODk2In0...'
> ```
> Decodes into: `{ "instanceId": "044667f4-c13f-46c2-8506-de9e42293896" }`

So the signature becomes `verify(raw_body, *, headers, now)` — body first, because the body is the
token. Stated once, unambiguously:

> **The raw request body is the JWT.** `headers` is **never** a source of the token, and
> **`Content-Type` is never branched on at all** (R4-M4). An `Authorization` header is ignored
> entirely. API Gateway's `isBase64Encoded` flag is honoured and the body base64-decoded **before**
> any JWT parsing, because a binary-media-type route would otherwise present a double-encoded token.
> The **three-base64url-segment check is the real discriminator**, and it is applied to whatever the
> body is.

> **THE `Content-Type` REJECTION IS DROPPED (resolves R4-M4), and dropping it is the fail-closed
> choice rather than the lax one.** Revision 3 returned 401 unless `Content-Type` was
> `application/jwt`, `text/plain` or `plain/text`. Measured: the **only** `Content-Type: plain/text`
> occurrence on the fetched introduction page is the **app-install instance-id callback** quoted above,
> and the self-managed REST guide — which documents the envelope and all five claim checks in full —
> **says nothing about `Content-Type`**. So the allowlist was assembled from one example of a
> *different* endpoint.
>
> **If Wix sends `application/json`, revision 3's verifier refuses every live call.** That is
> fail-closed in form and **feature-dead** in substance: the endpoint would answer nothing, the
> gift-card integration would never work, and §5's claim to implement Wix's model *verbatim* would be
> false — because the model as documented contains no such check. A 401 on an undocumented header
> value is not caution; it is a guess, enforced.
>
> What is kept is everything that actually authenticates: `isBase64Encoded` honoured **first**, the
> three-segment check as the discriminator, the signature verified against the app's public key, the
> algorithm allowlist, and all five claim checks. Nothing about the security posture changes — a body
> that is not a signed JWT from Wix is still refused, under every declared type. The header question
> moves to **owner item 12.1.4**, beside the `alg` question, to be answered from a **real token**
> rather than from an example of another endpoint.
>
> Test 2 is re-pointed accordingly:
> `test_a_body_that_is_not_three_segments_is_refused_whatever_the_content_type`, parametrised over
> `application/json`, `application/jwt`, `text/plain`, `plain/text` and a **missing** header, asserting
> the declared type **never decides the outcome** in either direction.

Test 4 presents a valid JWT in an `Authorization` header with a non-JWT body and asserts a
rejection, so the ambiguity cannot be reintroduced by a later "helpful" fallback.

### 5.1 Enforcement, in order, fail-closed at every step

`gift_card_spi_auth.verify(raw_body, *, headers, now) -> Context`

1. Honour `isBase64Encoded` **first**. Then reject a body that is not three base64url segments
   separated by dots, before any decoding of claims. **`Content-Type` is not read and not branched
   on** (R4-M4) — the three-segment check is the discriminator, applied to whatever arrived.
2. Verify the signature with the app's **public key**, fetched by reference from Secrets Manager
   (`wecare/wix/giftcard-spi` → `public_key`), read **lazily at request time**. A module-scope read
   caches for the life of the execution environment, so a key rotation would not take effect until
   every warm sandbox recycled — the exact defect fixed in `payments/razorpay-webhook` on
   2026-09-19 and re-confirmed by `scripts/verify_razorpay_secret_path.py`. Same mistake, same
   avoidance.
3. `aud == <our Wix application id>`, compared explicitly against the configured value. An absent
   or multi-valued `aud` is rejected rather than coerced.
4. `iss == "wix.com"`, exact string.
5. `iat <= now + CLOCK_SKEW` and `exp > now - CLOCK_SKEW`, with `CLOCK_SKEW = 60` seconds. Skew is
   bounded and symmetric; a missing `iat` or `exp` is rejected, never defaulted.
6. Only then is `data.metadata` parsed as a `Context` and `metadata.instanceId` checked against the
   installed instance, and `data.request` handed to the method handler.

**Algorithm handling.** The key is an app **public** key from the Wix dashboard, so the algorithm
family is asymmetric. The verifier accepts only `RS256`, `RS384` and `RS512`, and refuses
`alg: none` and every HMAC algorithm outright — accepting the token's own `alg` is the classic JWT
key-confusion attack, and an HMAC `alg` with an RSA public key as the secret is its textbook form.
**Unverified:** Wix does not name the exact algorithm on any fetched page. It is therefore read
once from the real token header at registration time (§12.1 step 4) and pinned to a single value in
configuration; until then the three-member allowlist is the fail-closed position.

Failure returns **401 with an empty body**. No error detail, because the caller is either Wix
(which does not need it) or an attacker (who must not get it).

#### 5.1.1 The verifier's library and its layer (closes HIGH-6)

Revision 2 said *"A standard library does the parsing, per Wix's recommendation — nothing here
hand-rolls base64 or signature verification."* **Python's standard library cannot verify an RSA
signature**, so that sentence named no implementation for the only security control on an
internet-facing route with no API Gateway authorizer. Worse, the function would have been
**rejected before it ever deployed**: `scripts/deploy_all_lambdas.py` resolves each function's
layer contents from its live configuration and validates every top-level import against the
package plus those layers, failing with

```
scripts/deploy_all_lambdas.py:570   f"{arcname}:{lineno} imports '{root}', not in package or layers"
```

and recording at line 441 that *"several of these functions rely entirely on layers for PIL /
cryptography"*. A new function has **no layers attached at all** until a provisioner attaches
them, because the gate reads `current.get("Layers")` off the live function.

**Chosen: `cryptography`, via the layer this account already has.** Measured live:

```
$ aws lambda get-function-configuration --function-name wecare-whatsapp-business-api \
      --query 'Layers[].Arn' --output text
arn:aws:lambda:us-east-1:775261844268:layer:cryptography-python312:1
```

That is the same layer `amplify/functions/messaging/whatsapp-business-api/handler.py` relies on
for its own RSA work (`from cryptography.hazmat.primitives.asymmetric.padding import OAEP, MGF1`
and three more at lines 3372–3375), so the capability is already proven on this runtime in this
account.

Rejected: **PyJWT pinned with `[crypto]`**. It is the more ergonomic library and it would still
depend on `cryptography` underneath, so it buys a convenience API at the cost of a second
packaged dependency, a second version to pin, and a new layer to build and maintain. `cryptography`
alone is one already-live layer and zero new supply-chain surface. The ergonomics gap is small
because the verifier is deliberately narrow — it accepts three algorithms and five claims, and
§5.1 enumerates every check — so there is little for a JWT library to abstract that we are not
specifying by hand anyway.

What the verifier uses from it, and what it does not hand-roll:

```python
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
from cryptography.exceptions import InvalidSignature
# base64url segment splitting and padding: base64 + json, stdlib, on the ENCODED form only.
# The signature check itself is public_key.verify(...), never a comparison we write.
```

`base64.urlsafe_b64decode` and `json.loads` are stdlib and are used on the encoded segments, which
is the part the stdlib genuinely covers; the sentence revision 2 wrote is true of the *parsing*
and false of the *verification*, and the split is now explicit.

**The layer attachment is a provisioning step, not an assumption.**
`scripts/provision_gift_cards_roles.py` attaches it when it creates
`wecare-wix-giftcard-spi`, and it appears in §12.3's deploy order ahead of the first
`deploy_all_lambdas.py` run:

```
aws lambda update-function-configuration \
    --function-name wecare-wix-giftcard-spi \
    --layers arn:aws:lambda:us-east-1:775261844268:layer:cryptography-python312:1
```

The ARN is pinned to **version 1**, deliberately: a layer version is immutable, so pinning means
the verifier's crypto implementation cannot change under it without a deliberate edit here. A
floating reference would let a layer republish alter signature verification on a payment route
with no code change and no review.

Test 110 asserts the SPI handler's top-level imports are covered by the declared layer set, so
the deploy gate is not the first place a missing layer is discovered; test 111 asserts the
provisioner names that exact versioned ARN.

### 5.2 Why the route is `AuthorizationType=NONE`, and why that is not a hole

The SPI route carries no API Gateway authorizer, necessarily: Wix presents its own JWT, not a
Cognito token. This is the same posture `00-current-owner-overrides.md` already describes —
*"Provider webhooks remain publicly reachable where required, protected using provider signature
verification"* — and the same note applies: gateway configuration alone cannot distinguish an
intentionally public signed webhook from an accidentally public API.

What makes it safe is that verification is **the first thing the handler does**, before the body is
interpreted and before any table is touched, and tests 10 and 11 assert that ordering rather than
trusting it. With WAF removed by owner decision on 2026-09-28, handler-level verification plus
`lambda_utils/rate_limit.py` plus stage/route throttling is the entire filter in front of this
route. That is stated plainly rather than assumed, because there is no per-IP layer behind it any
more.

### 5.3 The code never appears in a URL

All three SPI methods are `POST` with the code in the JSON body. Our own customer-facing apply
endpoint is likewise `POST` with a body. **No gift-card code may ever appear in a path segment, a
query string, a redirect, or a log line** — a bearer value in a URL lands in access logs, in
`Referer` headers and in browser history. This is enforced by shape (no route template takes a
code) and by test 33, not by convention.

Worth noting as corroboration rather than as our rule: Wix's own Model B2 `Get Gift Card` puts the
code **in the path** (`POST /ecom/v1/gift-cards/{code}`). We do not call it, and if that ever
changes it is a decision to be taken knowingly rather than inherited.

---

## 6. Data model

    stack-wecare-digital-GiftCardsTable
      partition key:  giftCardKey (S)     no sort key
      billing:        PAY_PER_REQUEST
      PITR:           ENABLED
      TTL:            DISABLED, asserted in --verify
      SSE:            SSEType=KMS, KMSMasterKeyId=alias/wecare-gift-cards   <- CUSTOMER-MANAGED

#### Encryption with a customer-managed KMS key (DECISION 6 — new ground in this repo)

Neither design document mentioned `SSESpecification`, and this is **new ground**: measured across
`scripts/`, there is **no `SSESpecification` on any `provision_*.py` and no `CreateKey` call
anywhere**, so every existing table runs on the AWS-owned default key. This table does not, and the
reason is the same one that keeps TTL off: the rows are a **liability ledger**, the only place a
customer's balance of record exists.

```python
SSESpecification={"Enabled": True, "SSEType": "KMS",
                  "KMSMasterKeyId": "alias/wecare-gift-cards"}
```

Both roles (§10.1) additionally get `kms:Decrypt` and `kms:GenerateDataKey` on the key, **conditioned
on `kms:ViaService = dynamodb.us-east-1.amazonaws.com`** — so the grant lets DynamoDB decrypt rows on
their behalf and does **not** let either function use the key for anything else.

Three details that are decisions rather than boilerplate:

- **The alias, not the ARN, is what the provisioner and the policy agree on.** A CMK's ARN is not
  known until the key exists, so hard-coding one would mean either a dated constant in the script or
  a two-pass apply. `alias/wecare-gift-cards` is stable and resolvable by both.
- **`provision_gift_cards_table.py` REFUSES to create the table before the alias resolves.** A table
  created on the default key cannot be moved to a CMK afterwards without a restore, so the ordering
  is enforced rather than documented.
- **Creating the key is a POINTWISE OWNER CONFIRMATION**, per `maintenance-reporting.md`, which lists
  KMS create/delete among the operations requiring per-item approval. It is behind `--apply`, nothing
  in this work has run it, and it appears in §12.2 as an owner item. A KMS key also carries a standing
  monthly cost, which is part of what the owner is approving.

A test asserts both halves offline — the `SSESpecification` literal in the provisioner and the
`kms:ViaService` condition in each role policy.

`GiftCard` → `GiftCardsTable` follows `check_data_model_drift.py`'s default pluralise-and-append
rule, so the physical name is right. **But the table still needs a drift allowance**, because
`amplify/data/resource.ts` declares no `GiftCard` model and `check_data_model_drift.py` compares
declared models against live tables — so an undeclared live table lands in
`undeclared_tables_unexpected` and `--gate` exits non-zero. Revision 1 named `EXPLICIT_TABLE` and
`PHANTOM_ALLOWED`, which are the wrong lists (closes MEDIUM-12).

The `UNDECLARED_ALLOWED` entry for `GiftCardsTable` is quoted verbatim in
`coupons-20261001.md` §4 and **that document owns the single edit** adding both entries, so one
file is edited once by one session. This document depends on it and asserts it through that
document's test 57 rather than duplicating either the edit or the test.

**TTL disabled, and here it is stronger than a convention.** A gift-card row is a *liability* — a
balance we owe a customer. An expiring row is a disappearing debt. Expiry of the card is a field
(`expiresAtMs`) that changes what is *permitted*; it never removes what is *owed*.

### 6.1 The code is bearer value, so it is never the key

The partition key is derived from the code, never the code itself:

```
codeHash = HMAC-SHA256(pepper, NFKC(code).upper()).hexdigest()
```

An HMAC with a pepper, not a bare SHA-256, and the reason is the measured contract: the code is
`minLength 8, maxLength 20`. An 8-character code over a small alphabet is inside brute-force range
for a plain hash, so a leaked table would expose live balances. The pepper lives in Secrets
Manager (`wecare/wix/giftcard-spi` → `code_pepper`), read lazily at request time, referenced by
secret id and never on a command line.

This is the deliberate opposite of the coupon design, where the code *is* the partition key
because a coupon code is broadcast marketing material. The contrast is pinned by a test in both
documents so neither gets "harmonised" into the other.

**Masking.** Logs carry `codeLast4` only, rendered as `****1234`. The code never appears in full,
not in a log, not in an exception message, not in a report. Wix's own `GiftCard.obfuscatedCode`
does the same thing on its side, with the documented example form `"****-****-****-1234"`.
Correlation in logs uses `giftCardId` (ours, a UUIDv7, not secret), `referenceId` (ours, explicitly
loggable in full per `whatsapp-payments-india-reference.md`), and the SPI's `metadata.requestId` —
Wix explicitly offers that last one for log correlation, which is why no masked-value guessing is
needed.

### 6.2 No float, at the entry point

The SPI sends amounts as JSON **numbers** (`"amount": 50.00` in the documented sample flow).
Python's `json.loads` produces a `float` for `12.34` by default, which would put a float on the
payment path before a single line of our logic ran.

```python
claims = json.loads(jwt_payload_segment, parse_float=Decimal)   # MANDATORY
request = claims["data"]["request"]
amount_paise = money.Money.from_wix(_exact_decimal_string(request["amount"])).paise
```

`parse_float=Decimal` is not optional and is asserted by test 24, which patches `float` to raise.
`_exact_decimal_string` renders the `Decimal` at exactly two places and refuses a value with more
precision than paise — a third decimal is a request for a fraction of a paise, which is refused
rather than rounded, because `Money.from_wix` itself demands
`[0-9]{1,14}(?:\.[0-9]{1,2})?` and would otherwise raise with a less useful message. Outbound,
`Money.to_wix()` produces the exact string for the **Cart V2** path, and the SPI response renders a
JSON `number` from the same integer paise by `int`/`%02d` composition with no float constructed.

### 6.3 Row types

```
GIFTCARD#<codeHash>                        the card: balance, status, expiry, ACTIVE HOLD
GCID#<giftCardId>                          pointer -> {codeHash, codeLast4}, for GET by OUR id
GCORDER#<codeHash>#<paymentAttemptId>      idempotency claim, carries the winning transactionId
GCWIXORDER#<wixOrderId>                    pointer -> paymentAttemptId, at WIX_ORDER_CREATED
GCTXN#<codeHash>#<transactionId>           the transaction record (REDEEM or VOID)
GCTXNID#<transactionId>                    reverse index -> {codeHash, paymentAttemptId}   (R4-H6)
GCHOLD#<codeHash>#<paymentAttemptId>       AUDIT ONLY: the hold as it was taken (R4-H3)
```

`GCTXNID#<transactionId>` exists solely because `VoidRequest` carries no `code`. Without it, a
documented request would be unanswerable. It is a pointer row, written in the same request that
creates the transaction, and never deleted.

> **`GCTXNID#` now points to `{codeHash, paymentAttemptId}`, not to `codeHash` alone, and that makes
> `GC_VOIDED` reachable (resolves R4-H6 / DECISION 9).** §8.4 assigns the `GC_VOIDED` stage write to
> `wecare-wix-giftcard-spi` and §10.1 grants it `UpdateItem` on `PaymentAttemptsTable` for exactly
> that — **but `advance()` requires an `attempt_id` and nothing on the void path could produce one.**
> `VoidRequest` carries **only** a `transactionId` (measured: no code, no orderId); this pointer
> resolved to a `codeHash` only; and `GCTXN#`'s attribute list still carried revision 2's
> `referenceId` with **no `paymentAttemptId` anywhere**. Reaching it by prefix-scanning
> `GCORDER#<codeHash>#*` is barred by R4-H3. So the IAM grant was written for an uncomposable call and
> the stage would never have been written at all.
>
> Three changes, together: `GCTXN#<codeHash>#<transactionId>` **gains `paymentAttemptId`**;
> `GCTXNID#<transactionId>` points to **both**; and `referenceId` on `GCTXN#` is demoted to
> **"correlation only, never a key"**, which is what completes the §3.4 re-key. A void carrying only a
> transaction id then resolves **both** the card and the attempt in **two exact-key `GetItem`s**, and
> a test drives exactly that: a void with nothing but a `transactionId` writes `GC_VOIDED` through
> `advance()`.

> **`GCHOLD#` is an AUDIT row and is never read to make a decision (R4-H3 / DECISION 5).** The hold
> *existence fact* lives on `GIFTCARD#<codeHash>` as `activeHoldAttemptId` / `activeHoldPaise` /
> `activeHoldExpiresAtMs` (§6.4), because finding a hold by key **prefix** is not implementable here:
> the table is one partition attribute with no sort key, `Scan` is denied, and a `Query` needs
> partition-key **equality** — `GCHOLD#<hash>#attempt-1` and `GCHOLD#<hash>#attempt-2` are *distinct
> partition keys*. §7.4's rule that `/v1/redeem` refuses "whenever any `GCHOLD#<codeHash>#*` or
> `GCORDER#<codeHash>#*` row exists" therefore had no implementation; it is now a **single exact-key
> `GetItem`** on the card row. This also repairs §3.4's safety argument for keying the claim on
> `paymentAttemptId`, which rested on "the hold refuses it" and so depended on finding the hold.

> **`GCID#<giftCardId>` is a SEVENTH row type that revision 3 did not have, and it is needed by a
> route revision 3 specified.** `GET /gift-cards/{giftCardId}` (§7.2) resolves a card by **our** id,
> and the only alternatives are a `Scan` (denied) or a second GSI — and a GSI is **eventually
> consistent**, so it cannot back a staff read of a balance that has just moved. A pointer row is the
> same device `GCTXNID#` already is, and keeps every access exact-key. It carries `codeHash` and
> `codeLast4` only, so it is not a second place the code lives.

`GCWIXORDER#<wixOrderId>` is the second pointer row. It is what lets a Wix-originated call about a
Wix order GUID be resolved to the purchase our own claim is keyed on. It is written at writeback
time, when `wixOrderId` first exists (SEAM-G10).

`GCHOLD#` and `GCORDER#` are keyed on `paymentAttemptId` — **not** `cartId`, **not** `orderId`,
and **not** `referenceId`, each for its own measured reason (§3.4). So the hold, the claim, the
stage attributes and the attempt row itself all share one identifier, and `advance()` already
takes it as `attempt_id`, which means no join exists to get wrong.

### 6.4 `GIFTCARD#<codeHash>` attributes

| Attribute | Type | Notes |
|---|---|---|
| `giftCardKey` | S | `GIFTCARD#<codeHash>` |
| `giftCardId` | S | UUIDv7 from `identifiers.new_uuid7`, ours. Returned as the SPI's `externalId` |
| `codeLast4` | S | the only part of the code stored in clear, for support |
| `pinHash` | S | HMAC of the PIN if issued; absent if none. Never the PIN |
| `initialValuePaise` | N int | `0 < v <= 99_999_999_999` — see below |
| `balancePaise` | N int | atomic `ADD`, guarded by `balancePaise >= :amount`; same ceiling |
| `currency` | S | `"INR"`, compared explicitly, never inferred from an amount |
| `status` | S | `ACTIVE` / `DISABLED` (sparse GSI key) |
| `activeHoldAttemptId` | S | **R4-H3 / DECISION 5.** The payment attempt currently holding this card. Absent when nothing holds it. **The only thing `/v1/redeem`'s refusal reads** |
| `activeHoldPaise` | N int | **R4-H3 / DECISION 5.** How much that hold reserves |
| `activeHoldExpiresAtMs` | N int | **R4-H3 / DECISION 5.** Epoch **milliseconds**. A hold past this instant is void and may be taken over |
| `activeClaimAttemptId` | S | A **claim** (`GCORDER#`) is not a hold and never lapses, so it needs its own attribute. `_decrement` sets this **and** fills `activeHoldAttemptId` through `if_not_exists`, so §7.4's "one exact-key `GetItem` reading `activeHoldAttemptId`" stays literally true while a claim reserves unconditionally and a hold only until its expiry. `reserved_by(card, now_ms=...)` is the one reader |
| `issuedAtMs` / `expiresAtMs` | N int | epoch milliseconds, matching Wix's convention |
| `issuedToContactId` | S | optional |
| `sourceOrderId` | S | the order that bought this card, if any |
| `policyVersion` | S | `giftcard-policy-2026-10-01` |
| `createdAt` / `updatedAt` | N int | epoch seconds |
| `createdBy` | S | staff subject id |

**The value ceiling is the SPI's, not `money.py`'s (closes MEDIUM-14).** Revision 1 capped
`initialValuePaise` at `9007199254740991`, `money.py`'s bound. But `GetBalanceResponse.balance` and
`RedeemResponse.remainingBalance` are both `maximum: 999999999.99`, so a card issued above that
**could not be reported to Wix at all** without violating the schema this document insists must be
matched exactly. The cap is therefore:

```
initialValuePaise : integer paise, 0 < v <= 99_999_999_999      # == 999999999.99, the SPI maximum
balancePaise      : the same ceiling asserted on every credit, not only at issuance
```

`money.py`'s `9007199254740991` remains the outer type bound — nothing exceeds it — but the
binding constraint is the SPI's. Tests 51 and 52 sit at `99_999_999_999` (accepted) and
`100_000_000_000` (refused).

`balancePaise` is the authority. `GetBalanceResponse.balance` is rendered from it; nothing reads a
balance from Wix.

### 6.5 `GCTXN#`, `GCORDER#` and the attempt-level attributes

`GCTXN#<codeHash>#<transactionId>`: `transactionId` (ours, 1–100 chars per the schema, generated
with `secrets`), **`paymentAttemptId` (R4-H6 / DECISION 9 — the attribute that makes `GC_VOIDED`
reachable)**, `kind` (`REDEEM` / `VOID`), `amountPaise` (int), `balanceAfterPaise` (int),
`referenceId` (**correlation only, never a key** — demoted per DECISION 9; it was revision 2's key),
`wixOrderId` (when known), `voidedBy` (the void transaction id, set when reversed), `credited`
(bool — written `False` by the same conditional update that latches `voidedBy`, set `True` only
after the balance has come back; it is what makes a STALLED void completable instead of permanently
refused), `creditedAt`, `voidBalanceAfterPaise`, `createdAt`, `source` (`OURS` / `WIX_SPI`).

`credited` is sound in one direction only: it can never claim a credit landed when it did not, but
`False` covers both "the credit never ran" and "the credit ran and this write was throttled". So it
is **not** what makes the void safe — the credit additionally writes `appliedVoid#<voidTransactionId>`
on the CARD row, inside the same `UpdateItem` as `ADD balancePaise`, under
`attribute_not_exists`. One item, one commit, so a retry that re-drives on the strength of
`credited: False` loses a condition rather than handing the balance back twice. The redemption
path carries the identical device as `appliedClaim#<paymentAttemptId>` on the decrement, for the
same reason: `GCORDER#`'s `settled` is also on a second item. `_drop_applied_marker` removes each
marker once its flag has landed, so the card row stays bounded by in-flight moves rather than by
their lifetime count.

`source` distinguishes our own finalization redemption from one Wix asked for. **§1.3 predicts
`WIX_SPI` should never appear**, so its appearance is the detector for that prediction being wrong.
Revision 1 called it "a signal worth alarming on" without naming anything (NIT-19); named now:

| | |
|---|---|
| Log event | `logger.warning(json.dumps({"event": "gift_card_wix_spi_redemption", ...}))` |
| Metric | `WecareGiftCards / WixSpiRedemption`, EMF from the SPI handler, unit Count |
| Alarm | `wecare-gift-card-wix-spi-redemption`, `Sum >= 1` over 5 minutes, 1 datapoint, routed to the same SNS topic the account's 41 existing alarms use |
| Provisioned by | `scripts/provision_gift_cards_roles.py --alarms` |

A single occurrence is actionable, which is why the threshold is 1 rather than a rate.

`GCORDER#<codeHash>#<paymentAttemptId>`: `transactionId`, `amountPaise`, `claimedAt`,
`referenceId` (recorded for correlation, never used as a key), `wixOrderId` (backfilled at
writeback), and **`settled: bool`**. Written with `attribute_not_exists(giftCardKey)` **before** the
balance moves.

> **Why the claim carries `settled` (an implementation fact neither revision had).** The claim is
> written **unsettled** and marked settled by the decrement. Without the flag, an `InsufficientFunds`
> failure between the two would leave a **permanent** claim reporting a redemption that never moved
> money — and the claim cannot be deleted, because test 60 bans deleting it. A retry re-drives the
> decrement under the **same** `transactionId`. A replay presenting a **different** amount for the same
> claim key raises `REDEEM_AMOUNT_CONFLICT` rather than honouring either figure.
>
> **The decrement does NOT gate on the claim.** It gates on balance and status only, because two
> genuinely different purchases of one card must each deduct — that is §9.1's test 53,
> `test_two_different_payment_attempts_each_deduct_once`. The `AlreadyRedeemed` refusal is a narrower
> rule with a different owner (the SPI handler, via `reserved_by`), and folding it into the store would
> make a customer's second purchase refuse.

**Attempt-level attributes, and who writes each one.** Seven attributes live on the
`PaymentAttemptsTable` row rather than on the gift-card table. The table is exhaustive, and the
`advance()` column is the **closed** evidence set §7.3 enumerates:

| Attribute | Written by | When | Read by |
|---|---|---|---|
| `giftCardStageRank` | `advance()` — every call | each stage change | `stage()`, `stage_rank()`, the guard |
| `giftCardRequiredPaise` | `advance(..., stage=GC_HELD, ...)` | at the hold, SEAM-G4 | `is_fully_settled` |
| `giftCardCodeHash` | `advance(..., stage=GC_HELD, ...)` | at the hold | the redemption, to resolve the card |
| `giftCardRedeemedPaise` | `advance(..., stage=GC_REDEEMED, ...)` | after our redemption | `is_fully_settled` |
| `giftCardTransactionId` | `advance(..., stage=GC_REDEEMED, ...)` | after our redemption | `is_fully_settled` |
| `verifiedCapturedPaise` | **`finalization.record_paid`** (SEAM-G13) — **not** `advance()` | when the capture readback is authoritative | `is_fully_settled` |
| `razorpayChargedPaise` | **the checkout producer**, on the attempt dict before `put_item`, beside `attempt["checkoutMode"]` (§8.1) | at checkout | **reconciliation only**; no settlement decision reads it |

Three things this table settles, each of which was a finding:

- **`verifiedCapturedPaise` is outside `advance()`'s closed set on purpose.** It is the Razorpay
  leg's evidence, and the Razorpay leg is not this module's to write — §7.3 and test 85 forbid
  this module touching `record_paid` at all. It belongs in the same conditional
  `UpdateExpression` that writes `verifiedProviderPaymentId`, because the two are the same fact
  recorded at the same instant, and splitting them across two writes would admit a row carrying
  one without the other.
- **`razorpayChargedPaise` is read by nothing that decides anything (closes HIGH-2).** Revision 2
  had `is_fully_settled` read it while this table and §7.3's closed set both forbade writing it,
  and the read was a bracket subscript so an absent attribute raised `KeyError` inside
  finalization after a verified capture. It is now an audit record only: *what we asked the
  gateway for*, against which `verifiedCapturedPaise` is *what the gateway gave*. A disagreement
  is a genuine finding and gets its own metric below.
- **`advance()`'s evidence set is exactly four keys** — `giftCardRequiredPaise`,
  `giftCardCodeHash`, `giftCardRedeemedPaise`, `giftCardTransactionId` — plus `giftCardStageRank`
  which it always writes. Anything else raises (§7.3). Revision 1 declared the attributes and the
  `condition_expression()` guard but named no writer, no call site and no permission, so the
  forward-only guard the whole §3 ladder rests on was never applied to a row.

**The charged-versus-captured disagreement detector.** Because both figures now exist on the row,
a mismatch is observable rather than theoretical, and it means either a gateway anomaly or a
tampered split:

| | |
|---|---|
| Log event | `logger.warning(json.dumps({"event": "gift_card_charge_amount_disagreement", ...}))` with both figures in paise, the `paymentAttemptId`, and no code |
| Metric | `WecareGiftCards / ChargedVsCapturedMismatch`, EMF, unit Count |
| Alarm | `wecare-gift-card-charge-mismatch`, `Sum >= 1` over 5 minutes, same SNS topic as the account's existing alarms |
| Provisioned by | `scripts/provision_gift_cards_roles.py --alarms` |

Amounts in paise are not a disclosure and are what makes the line useful —
`payment_status.entity_summary` already draws that line the same way.

### 6.6 Index

    status-index   HASH status, RANGE createdAt

Sparse: only card rows carry `status`, so transactions, claims, holds and pointer rows never enter
it. Serves the staff view of active cards and outstanding liability. `createdAt` keeps the query
bounded to a window rather than reading an entire low-cardinality status partition — the same
reasoning as `status-index` on PaymentAttemptsTable.
---

## 7. Lambda surface

Two new functions, authored but **not deployed**.

```
amplify/functions/ecommerce/gift-cards/handler.py          NEW  staff + customer routes
amplify/functions/ecommerce/wix-giftcard-spi/handler.py    NEW  the three SPI endpoints
amplify/functions/shared/lambda_utils/ecommerce/gift_card_store.py        NEW
amplify/functions/shared/lambda_utils/ecommerce/gift_card_settlement.py   NEW  the §3 ladder
amplify/functions/shared/lambda_utils/ecommerce/gift_card_spi_auth.py     NEW  the §5 JWT
```

They are **two** functions, not one, because they have different callers, different auth and
different blast radius. The SPI function is internet-facing with no API Gateway authorizer and
needs only `GetItem`/`UpdateItem`/`PutItem`/`Query`. Folding the staff create surface into the same
function would put card *issuance* behind a route reachable by anyone who can reach Wix's caller.

Every module takes injected dependencies (table resource, request callable, clock) and holds no
boto3 client, matching `cart_v2.py` and `payment_attempt.py`, so all of it is testable offline.

### 7.1 SPI routes — called by Wix

| Route | Verifies | Returns |
|---|---|---|
| `POST /wix-giftcards/v1/balance` | §5 JWT | `{balance, currencyCode, externalId}` |
| `POST /wix-giftcards/v1/redeem` | §5 JWT | `{remainingBalance, currencyCode, transactionId}` |
| `POST /wix-giftcards/v1/void` | §5 JWT | `{remainingBalance, currencyCode}` |

Response shapes are exactly the documented schemas and nothing more — no extra field, because the
guidance says a response not matching the specification will not be handled correctly.
`externalId` is `giftCardId`, never the code and never anything derived from it.

**`deploymentUri` host (closes NIT-21).** Registration uses the **execute-api hostname of the
account's single HTTP API `zllr9lrg7j`, stage `prod`**:

    https://zllr9lrg7j.execute-api.us-east-1.amazonaws.com/prod/wix-giftcards/

so Wix appends `v1/balance`, `v1/redeem`, `v1/void`. Reasons, stated because the choice is
one-way-ish:

- The account has **no API Gateway custom domain** — `docs/execution/aws-inventory.json` records no
  `DomainName` for any API, and the apex `wecare.digital/api/*` path is an Amplify-side rewrite
  serving browsers, not a server-to-server front door. Routing Wix's calls through the Amplify CDN
  would add a hop and a cache layer we do not control in front of a signed, non-idempotent
  endpoint.
- `provision_checkout.py` records that there is no `$default` stage, so the `/prod` segment is
  mandatory on the raw host. Omitting it is a silent 404 at Wix's save-time validation.
- The cost is recorded: **a later move to a custom domain means re-registering with Wix**, not
  editing a route. If the owner would rather pay that cost now than later, §12.1 step 3 is where to
  decide it.

### 7.2 Our own routes

| Route | Identity | Purpose |
|---|---|---|
| `POST /gift-cards` | staff | Issue a card. Generates the code, returns it **once**. |
| `GET /gift-cards/{giftCardId}` | staff | By id. Never by code, never a code in the response. |
| `GET /gift-cards` | staff | List by `status`, with outstanding liability. |
| `POST /gift-cards/{giftCardId}/disable` | staff | `status=DISABLED`. Never deletes. |
| `POST /gift-cards/balance` | customer session | `{code, pin?}` in the **body**. Balance only. **Reserves nothing.** |

**FIVE routes, not seven (resolves R4-M5).** `POST /gift-cards/hold` and `POST /gift-cards/release`
are **removed**. The reason is not tidiness; revision 3's surface was internally contradictory and
every way of resolving it was wrong:

- §8.4 attributes **every** `GC_HELD` write to the checkout function, and §10.1 gives
  `wecare-gift-cards-role` **no `UpdateItem` on `PaymentAttemptsTable`**. So either the route takes a
  hold **without writing the stage** — leaving `giftCardRequiredPaise` unwritten, so
  `is_fully_settled` reads `required == 0` and **marks a gift-card order settled on the Razorpay leg
  alone**, which is the exact failure DECISION 3 exists to prevent — or it writes the stage and **IAM
  denies it**.
- Underneath both: **a customer session has no `paymentAttemptId` before checkout mints one**, and
  `GCHOLD#` is keyed on it (§3.4). There is nothing for a customer-initiated hold to be keyed on.

**The hold is taken only by the checkout producer, inside the request that mints the
`paymentAttemptId`** (SEAM-G4 / SEAM-G14). The customer-facing surface is `POST /gift-cards/balance`
only, which reserves nothing and therefore cannot strand a balance. Test 45's route enumeration pins
five, so a hold route cannot reappear without a design change.

No route takes a code in a path or query (§5.3). There is no `DELETE` — a disabled card retains
its liability record.

Code generation uses `secrets`, never `random`. `lambda-snapstart-deploy.md` records why: with
SnapStart on, a snapshot freezes the `random` PRNG state and every restored environment produces
the same sequence. SnapStart is currently `ApplyOn: None` on all 65 functions, but a gift-card code
is the exact class of value that must never repeat, `core/url-shortener/handler.py` already sets
the precedent, and `order_keys.mint_payment_reference` carries its own note on the same hazard.
Codes are 16 characters from a Crockford-style alphabet, inside the SPI's 8–20 bound.

### 7.3 `gift_card_settlement` — the public surface

```
# constants -- string stage VALUES, and a separate rank map (MEDIUM-12, §3.1)
GC_UNKNOWN / GC_NOT_REQUIRED / GC_HELD / GC_REDEEMED / GC_VOIDED  : str
STAGE_RANK : Dict[str, int]                      # GC_UNKNOWN deliberately absent -> rank 0
RAZORPAY_EVIDENCE_ATTR / RAZORPAY_VERIFIED_PAISE_ATTR : str        # §3.2, §11 fallbacks

stage(attempt) -> str                            # a VALUE, or GC_UNKNOWN
stage_rank(attempt) -> int                       # STAGE_RANK.get(stage(attempt), 0)
condition_expression() -> str                    # the forward-only guard

advance(attempts, *, attempt_id, stage, **evidence) -> dict
    # ONE conditional UpdateItem on PaymentAttemptsTable, using condition_expression().
    # Sets giftCardStageRank = STAGE_RANK[stage] plus the named evidence attributes.
    # Evidence keys are a CLOSED set: giftCardRequiredPaise, giftCardCodeHash,
    # giftCardRedeemedPaise, giftCardTransactionId. Anything else raises.
    # NOT in the set: verifiedCapturedPaise -- that is the Razorpay leg's evidence and belongs
    # to finalization.record_paid (SEAM-G13); nor razorpayChargedPaise, written at checkout.
    # Raises StageRegressed on ConditionalCheckFailedException -- a backward move is an
    # error to surface, not a no-op to swallow.

hold(table, *, code_hash, attempt_id, amount_paise, expires_at) -> dict
release(table, *, code_hash, attempt_id) -> dict
redeem(table, *, code_hash, attempt_id, amount_paise, source) -> dict
                                                 # idempotent on (code_hash, attempt_id), §3.4
void(table, *, transaction_id) -> dict           # resolves the card via GCTXNID#
resolve_attempt(table, *, wix_order_id) -> str   # via GCWIXORDER#, for a Wix-originated call
is_fully_settled(attempt) -> bool                # §3.2, requires BOTH legs, never raises
```

`advance()` is the writer HIGH-2 found missing. Two properties are load-bearing:

- **It is a conditional `UpdateItem`, never a read-then-write.** The guard is
  `condition_expression()`, so two concurrent writers cannot both advance the stage and a late
  `GC_REDEEMED` cannot overwrite a `GC_VOIDED`. Test 61 asserts the call carries a
  `ConditionExpression` and that no `get_item` precedes it.
- **The evidence key set is closed.** An open `**fields` writer on a payment attempt row is how an
  unrelated attribute gets written by accident; `finalization._stage` takes arbitrary fields and is
  trusted because it is one module, but `advance` is called from two functions, so the set is
  enumerated and anything else raises.

- **`verifiedCapturedPaise` is explicitly excluded from the evidence set**, and that exclusion is
  load-bearing rather than an oversight. This module must not write the Razorpay leg's evidence:
  test 85 asserts by AST that nothing here references `record_paid`, `PROVIDERPAYMENT#`,
  `payment_attempt.transition` or `razorpay_verify`. The attribute is written by
  `finalization.record_paid` under SEAM-G13, in the same conditional expression as
  `verifiedProviderPaymentId`.

`redeem` returns `{"transactionId": ..., "remainingBalancePaise": ..., "committed": bool}`.
`committed` is `False` on a replay, with the original `transactionId` — that is the idempotency
contract, and it is what our finalization path receives. A Wix `/v1/redeem` for a card that already
holds any `GCHOLD#`/`GCORDER#` row does not reach `redeem` at all; the handler refuses with
`AlreadyRedeemed` first (§3.4).

Nothing in this module touches `razorpay_verify`, `PROVIDERPAYMENT#`, `payment_attempt.transition`
or `finalization.record_paid`. The Razorpay leg is read through `payment_attempt`'s existing
predicates (`may_create_order`, which is exactly `status in {PAYMENT_PAID}`) and never written
here. Test 76 asserts it by AST.

### 7.4 Error handling, per operation

| Operation | Failure | Recoverable | Caller receives | Logged |
|---|---|---|---|---|
| any SPI call | body is not a three-segment JWT | no | **401, empty body** — under **every** declared `Content-Type`, including `application/json` (R4-M4) | WARN, no body content |
| any SPI call | bad signature / `alg: none` / HMAC alg | no | 401, empty body | WARN, `requestId` only if parseable |
| any SPI call | `aud` / `iss` mismatch | no | 401, empty body | WARN |
| any SPI call | `exp` past or `iat` future beyond skew | no | 401, empty body | WARN |
| any SPI call | `instanceId` not the installed instance | no | 401, empty body | WARN |
| any SPI call | `currencyCode` absent | yes | `MissingCurrency` 428 | INFO |
| Get Balance | code unknown | n/a | `GiftCardNotFound` 404 | INFO, `codeLast4` only |
| Get Balance | `status == DISABLED` | n/a | `GiftCardDisabled` 428 | INFO |
| Get Balance | past `expiresAtMs` | n/a | `GiftCardExpired` 428 | INFO |
| Redeem | `currencyCode != "INR"` | no | `CurrencyNotSupported` 400 | INFO |
| Redeem | any `GCHOLD#`/`GCORDER#` exists for the card | no | **`AlreadyRedeemed` 409** | ERROR + the §6.5 metric |
| Redeem | no hold, no claim, balance condition fails | yes | `InsufficientFunds` 428 | INFO |
| Redeem | no hold, no claim, honoured | n/a | 200, `source: WIX_SPI` | WARN + the §6.5 metric |
| Redeem | amount has sub-paise precision | no | 400 | INFO |
| Redeem | amount above `99_999_999_999` paise | no | 400 | INFO |
| Void | `GCTXNID#` missing | n/a | `TransactionNotFound` 404 | INFO |
| Void | `voidedBy` latched and `credited` not explicitly `False` | yes | `AlreadyVoided` 409 | INFO |
| Void | `voidedBy` latched with `credited: False` | n/a | **completed by the retry** under the latched void id, 200 | INFO |
| Void | latch lost to a concurrent void still in flight | yes | `AlreadyVoided` 409 | INFO |
| our `redeem` at finalization | claim put fails non-conditionally | **fatal, must not proceed** | raises; stage stays `GC_HELD` | ERROR, `type(exc).__name__` |
| our `redeem` at finalization | succeeds, `advance()` write fails | yes | `NEEDS_RECONCILIATION` | ERROR |
| `advance()` | `ConditionalCheckFailedException` | depends on caller | raises `StageRegressed` | ERROR |
| `hold` | balance insufficient | yes | 409 `INSUFFICIENT_BALANCE` | INFO |
| `hold` | held by another purchase | yes | 409 `HELD_BY_ANOTHER_PURCHASE` | INFO |
| `hold` | would leave `0 < payNow < 100` paise | no | 409 `GIFT_CARD_LEAVES_UNCHARGEABLE_REMAINDER` | INFO |
| `hold` | would cover the whole payable | no | 409 `GIFT_CARD_COVERS_FULL_TOTAL` | INFO |
| quote reconciliation (§4.2) | any identity fails | **no, fail closed** | 409, nothing charged | ERROR, amounts in paise |

Amounts in paise are not a disclosure and are needed to reconcile — `payment_status.entity_summary`
already draws that line the same way, and `referenceId` is loggable in full by the same standard.
Exception text is logged only where our own code built the message from known-safe parts;
otherwise `type(exc).__name__`. A secret must not appear in a logging *expression* at all, not
merely in its output: CodeQL (`py/clear-text-logging-sensitive-data`) tracks taint across function
boundaries and has already failed this build twice on `core/site-language/handler.py` over a
ternary on a key's truthiness. So the pepper, the public key and the raw code never appear in any
expression a logger consumes, and the alert is never suppressed.

### 7.5 Validation of every external input

| Input | Rule | On failure |
|---|---|---|
| `Content-Type` | **NOT VALIDATED, and never branched on (R4-M4).** Any declared type is parsed as a JWT | — |
| raw body | three base64url segments; `isBase64Encoded` honoured first. **This is the real discriminator** | 401 empty body |
| JWT | §5.1, every claim, asymmetric alg allowlist only | 401 empty body |
| `code` (SPI) | required, 8–20 chars per schema, `^[A-Za-z0-9-]+$`, NFKC-normalised | `GiftCardNotFound` 404 — a malformed code is not a different answer from an unknown one |
| `code` (ours) | same, body only, never path or query | 400 |
| `pin` | optional, ≤ 50 chars; compared by HMAC in constant time | `GiftCardNotFound` 404 |
| `amount` (SPI) | required, `Decimal` via `parse_float`, `0 < v ≤ 999999999.99`, ≤ 2 decimals | 400 |
| `orderId` (SPI) | required on redeem, GUID; resolved via `GCWIXORDER#`, never used as a claim key | 400 |
| `currencyCode` | required, `"INR"`, compared explicitly | `MissingCurrency` / `CurrencyNotSupported` |
| `locationId` | optional, ≤ 50 chars; accepted and ignored — single-location seller | — |
| `appInstanceId` | deprecated; accepted, never required, never trusted for identity — identity comes from the JWT | — |
| `transactionId` | required on void, 1–100 chars | 400 |
| `initialValuePaise` | staff issue: integer paise, **`0 < v ≤ 99_999_999_999`** (the SPI maximum, §6.4) | 400; floats and bools refused by type |
| any credit to `balancePaise` | the same ceiling, asserted on every credit, not only at issuance | 400 |
| `requestedRedeemPaise` | integer paise, `0 < v ≤ redeemCap` where **`redeemCap = gift_card_store.redeem_cap(balance_paise=…, wix_collection_paise=…)`** — the single definition in §4.1, **never** restated here (R4-H4) | 400 `GIFT_CARD_REDEEM_ABOVE_CAP`, never clamped |
| resulting `payNowPaise` | `>= RAZORPAY_MIN_LEG_PAISE` (100) when non-zero | 409 `GIFT_CARD_LEAVES_UNCHARGEABLE_REMAINDER` |
| `expiresAtMs` | optional, integer, `> issuedAtMs` | 400 |

Returning `GiftCardNotFound` for a malformed code, a wrong PIN and an unknown code alike is
deliberate: three distinct answers would turn the endpoint into a code-validity oracle.

### 7.6 Invariants and who owns them

| Invariant | Owner | Why there |
|---|---|---|
| balance never negative | `ConditionExpression: balancePaise >= :amount` on an atomic `ADD` | the only layer where concurrent redemptions serialise |
| balance never exceeds the SPI maximum | validation on issuance **and** every credit | a balance we cannot report is a balance we cannot honour (§6.4) |
| one redemption per (code, purchase) | conditional `GCORDER#<codeHash>#<paymentAttemptId>` put, before the decrement | must survive replay, and `paymentAttemptId` is the only id that exists before the gateway is addressed on **both** producers (§3.4) |
| a Wix redeem cannot double-spend | `/v1/redeem` refuses when any hold or claim exists | the two `orderId` namespaces differ, so refusal is the only sound guard (§3.4) |
| a transaction is resolvable by id alone | `GCTXNID#` pointer row | `VoidRequest` carries no code (§1.1) |
| a Wix order resolves to a purchase | `GCWIXORDER#` pointer row | written at `WIX_ORDER_CREATED` |
| a void cannot be undone by a replayed redeem | `GC_VOIDED` (60) > `GC_REDEEMED` (50), enforced by `advance`'s `ConditionExpression` | same judgement as `refunded` > `captured` |
| the stage never moves backwards | `gift_card_settlement.advance` only | a read-then-write loses the race (§7.3) |
| fully paid requires **both** legs | `gift_card_settlement.is_fully_settled` | §3.2; the Razorpay leg alone is never sufficient |
| absence of a gift card means not-required | `is_fully_settled`'s `required == 0` branch | the common path must need no write (§3.2) |
| `payNow + giftCardRedeem == total_payable` | the §4.2 reconciliation before the hold, **and** re-derived in `is_fully_settled` | R6.2, and it is the only amount outside `snapshotHash` (§4.2) |
| the Razorpay leg is chargeable | `RAZORPAY_MIN_LEG_PAISE` in `redeemCap` and in validation | the gateway refuses below 100 paise (§4.1) |
| fee basis is the **full** collection | `compute_quote` called before the split | §2; GST treats a voucher as consideration |
| no float anywhere | `parse_float=Decimal` + integer paise | R6.1, and the entry point is the risk |
| the code never leaves in clear | HMAC as key, `codeLast4` in logs, body-only routes | bearer value |
| Wix is never the balance authority | nothing reads a balance from Wix | Model A (§1) |

---

## 8. Where the gift-card leg plugs into the live checkout

**There are FOUR attempt producers in this tree, not one — and not three (closes HIGH-1; count
corrected per R4-M3).** Revision 2 named only the in-WhatsApp one, while both documents open by
declaring *"payment is Razorpay Standard Checkout on our own site"* the active architecture — and
the module that implements **that** was absent from the design entirely: not owned, not read-only,
not a seam. Revision 3 found it and then stated the total as **three**, labelled "measured". It is
four. Measured by enumerating every `payment_attempt.build(` call site in the tree:

| # | Producer | File:line of `payment_attempt.build(` | Builds the attempt with | Status here |
|---|---|---|---|---|
| 1 | in-WhatsApp `order_details` | `amplify/functions/ecommerce/checkout/handler.py::_create` **:519** | `reference_id=order_keys.allocate_payment_reference(...)` → `WD-PAY-…` | **in scope**, §8.2, SEAM-G8 |
| 2 | **website Razorpay Standard Checkout** | `.../ecommerce/website_checkout.py::prepare_checkout` **:279** (the `amount_paise=` kwarg at 281) | `reference_id=gateway_order_id` → the Razorpay order id | **in scope**, §8.1, SEAM-G14 |
| 3 | snapshot reservation | `.../ecommerce/initiation.py::reserve` **:63** | `amount_paise=int(snapshot['amountPaise'])` | **out of scope**, §8.3, with a reason |
| 4 | **blog contribution** | `.../ecommerce/blog_contribution.py::prepare_contribution` **:355** (function at 213) | its own contribution amount; its docstring calls itself a **sibling of `website_checkout`** | **out of scope**, §8.5, with a reason |

> **R4-M3, and why an off-by-one here is not a nit.** Revision 3's single largest finding was a
> **missed producer** — the website path, which is the active architecture. An enumeration that is
> still short by one is *the same defect, one instance smaller*, and it is presented with the same
> word, "measured". Producer 4's own docstring identifies it as a sibling of the module revision 3
> had just finished adding, which is the strongest available hint that an enumeration stopping at
> three was not an enumeration. The count is now derived from the call sites rather than from the
> narrative, and §8.5 declares producer 4 out of scope **explicitly**, in the shape of §8.3, so the
> omission is a decision rather than an oversight.

As revision 2 stood, a gift card applied on the website path would never have reduced the gateway
amount, and the callback would then have refused the capture — the feature dead rather than
dangerous, which is the *good* case. The bad case is a coder resolving it the obvious way, which
§8.1 exists to foreclose.

### 8.1 The website path — `website_checkout.py` (SEAM-G14)

This module says in its own docstring that it is the website path, and
`purchase_intent.py`'s docstring names it as the production consumer of a `QuoteSnapshot`. Three
lines matter, and they are three *different* numbers once a gift card exists:

```
website_checkout.py:192   payable = quote.as_payable_money()
website_checkout.py:193   amount_paise = payable.paise                     # the FULL payable
website_checkout.py:203   extra={"snapshotHash": ..., "amountPaise": amount_paise}   # THE BINDING
website_checkout.py:231   order = create_order(amount_paise=amount_paise, receipt=receipt, ...)
website_checkout.py:265   order_keys.bind_gateway_order(..., amount_paise=amount_paise, ...)
website_checkout.py:281   attempt = payment_attempt.build(..., amount_paise=amount_paise, ...)
website_checkout.py:407   stored_amount = int(binding.get("amountPaise") or 0)
website_checkout.py:430   captured, provider_payment_id, amount_paise, currency = verify_capture(...)
website_checkout.py:434   if amount_paise != stored_amount or currency != stored_currency:
website_checkout.py:436       return CallbackResult(status=CALLBACK_BINDING_MISMATCH)
```

**The split for this path, stated so the obvious wrong answers are closed off:**

| What | Carries | Why |
|---|---|---|
| `create_order(amount_paise=…)` (line 231) | **`payNowPaise`** | it is the amount Razorpay must actually collect |
| `bind_gateway_order(amount_paise=…)` (line 265) | **`payNowPaise`** | line 434 compares the capture against this; it must be the charged figure or every capture is a `BINDING_MISMATCH` |
| `reserve_checkout_request_key(extra={"amountPaise": …})` (line 203) | **`payNowPaise`** | same binding, written earlier on the same value; the two must not disagree |
| `payment_attempt.build(amount_paise=…)` (line 281) | **the FULL payable** | `attempt["amountPaise"]` is what `is_fully_settled` closes both legs against (§3.2) and what the Wix order must show (§2) |
| `attempt["razorpayChargedPaise"]` | **`payNowPaise`** | the audit record of what we asked the gateway for, set beside `attempt["checkoutMode"]` at line 282 |
| **`_browser_options(amount_paise=…)`** (defined 128, called 288-289) | **`payNowPaise`** | **R4-M2.** It becomes `options["amountPaise"]` at **line 145** — the figure Razorpay Standard Checkout **presents to the browser**. The payable here would show the customer a price they are not being charged and hand Razorpay a second, larger amount in the same flow |
| **`_recover_ambiguous_create(amount_paise=…)`** (defined 328, called 236 with the value at 239; forwards at 344) | **`payNowPaise`** | **R4-M2.** It is the recovery path for a `create_order` whose outcome is unknown; it re-finds the order by receipt and re-binds it. If it re-binds at the payable, recovery writes a binding that line 434 will refuse — so the one path that exists to rescue a payment would break it |
| **`_ready_from_binding`** (295, reads `binding["amountPaise"]` at 302) | **NOTHING — NEEDS NO CHANGE** | **R4-M2, stated so its absence is DELIBERATE.** It reads the amount back **off the binding**, which row 3 already set to `payNowPaise`. Changing it would either double-apply the split or reintroduce the payable on the resume path. The correct edit here is **no edit**, and saying so is the point: an unlisted consumer reads as an oversight |

> **Why these three rows exist (R4-M2).** `amount_paise` appears **18 times** in
> `website_checkout.py` and revision 3's table named **five**. The gap is not cosmetic, because the
> two obvious implementation strategies fail in opposite directions:
> - a coder who **reassigns the local `amount_paise`** to `payNowPaise` satisfies all five original
>   rows and **silently changes the other three** — including `payment_attempt.build` at 281, which
>   must stay the payable, so `is_fully_settled` loses the figure it closes against;
> - a coder who **introduces a second variable** must decide each of the remaining thirteen
>   occurrences unaided, with no statement of intent to check against.
>
> Enumerating every consumer — **including the one that must not change** — is what makes the split
> checkable rather than inferable. Test 112 is extended with
> `options["amountPaise"] == payNowPaise`.

So the binding and the gateway carry the **charged** figure while the attempt carries the
**payable**. Both wrong answers are now unrepresentable rather than merely discouraged:

- reduce only the gateway amount and leave the binding at the payable → line 434 refuses every
  capture;
- reduce both the gateway amount and the attempt's `amountPaise` → the attempt no longer knows
  the payable, so `is_fully_settled`'s closure has nothing to close against and a gift-card order
  would read as fully settled on the Razorpay leg alone, which is the one failure DECISION 3
  exists to prevent.

`intent_fingerprint` (line 108) hashes `str(quote.total_payable_paise)` among its components. It
is therefore unaffected by the split and needs no change — which is the correct behaviour: the
*intent* is the full payable, and a resumed click with the same intent should resume onto the same
gateway order. A gift card changing mid-flight changes the quote, which changes the fingerprint,
which is already rejected as `INTENT_CHANGED`.

The hold is taken **after** `attempt_id` is minted (**line 199**, corrected from 198 per R4-N2) and
**before** `create_order` (line 231), which is exactly §3.3's required ordering and is possible only
because the key is `paymentAttemptId` (§3.4).

Test 112 asserts, on one simulated website checkout:
`binding["amountPaise"] == payNowPaise` **and**
`attempt["amountPaise"] == quote.total_payable_paise` **and**
`attempt["razorpayChargedPaise"] == payNowPaise` **and**
`options["amountPaise"] == payNowPaise` (R4-M2 — the figure the browser is shown).

### 8.2 The in-WhatsApp path — `checkout/handler.py::_create` (SEAM-G8)

`compute_quote` has a production caller here, which revision 1 denied and revision 2 corrected:

```
amplify/functions/ecommerce/checkout/handler.py
  _v2_snapshot(identity, line_items)
      -> customer_cart.CustomerCart(...).ensure(identity, requested)
      -> purchase_intent.prepare_delivery(adapter, cart_id, owned)
      -> purchase_intent.build_intent(adapter, ..., quote_fn=compute_quote)   # the quote
  _create(identity, body, origin)
      snapshot, item_summary = _v2_snapshot(identity, line_items)
      amount_paise = snapshot.quote.total_payable_paise        # <-- THE INSERTION POINT
      ...
      extra = {... "amountPaise": amount_paise ...}
      reference_id = order_keys.allocate_payment_reference(_keys_table(), ..., extra=extra)
      attempt = payment_attempt.build(..., amount_paise=amount_paise, ...)
```

The change needed at that line is exactly:

1. after `_v2_snapshot` returns, if a gift card is applied: compute `giftCardRedeemPaise` and
   `payNowPaise` per §4.1, run the §4.2 reconciliation, and refuse the checkout on any failure.
   This happens **before** the hold and before `allocate_payment_reference`;
2. take the hold through `gift_card_settlement.hold(..., attempt_id=attempt_id, ...)`. Note what
   the §3.4 re-key buys here: `attempt_id` is minted at the top of step 3 in `_create`, *before*
   `allocate_payment_reference`, so the hold no longer has to wait for the reference to be minted
   and the ordering is the same on both producers;
3. put `payNowPaise` in `extra["amountPaise"]` and in the WhatsApp payment request, keep
   **`attempt["amountPaise"]` as the FULL payable**, and set
   `attempt["razorpayChargedPaise"] = payNowPaise` beside `attempt["checkoutMode"]`;
4. call `gift_card_settlement.advance(attempts, attempt_id=..., stage=GC_HELD,
   giftCardRequiredPaise=giftCardRedeemPaise, giftCardCodeHash=...)`.

Point 3 is the subtle one and is stated explicitly because getting it backwards is a silent
under-charge: `attempt["amountPaise"]` is what `finalization.accept_paid` reads, and per §2 the
Wix order must show the **full** taxable value. The gateway amount is a different number. The
same split, with the same reasoning, applies to the website path (§8.1) — and the fact that it
has to be stated twice for two producers is the reason HIGH-1 mattered.

This is **SEAM-G8**. The file is **clean** at HEAD; it is a seam because the brief assigns it to
another session (§11), not because of its git state.

### 8.3 `initiation.reserve` — out of scope, with a reason

`initiation.py::reserve` is a third producer: it builds an attempt with
`amount_paise=int(snapshot['amountPaise'])` and writes `snapshotHash=fingerprint(snapshot)`. It is
**declared out of scope for the gift-card split**, on three grounds:

1. **It is untracked in git and has no caller in `amplify/`** (§11), so there is no live path
   through it to break and no production behaviour to preserve.
2. **It consumes a pre-computed `snapshot['amountPaise']` rather than a `CheckoutQuote`**, so it
   has no `quote.convenience_fee_paise` to split against. Making it gift-card-aware means
   deciding what its snapshot dict should carry, which is a decision for whoever lands it.
3. It is gated on `CHECKOUT_INITIATION_ENABLED`, which this change does not enable.

**The consequence is named rather than left implicit:** if `reserve` becomes a live producer
later, a gift card applied through it will behave as revision 2's design did on the website path
— the gateway amount unreduced — so whoever wires it must apply §8.1's split table. Test 113
asserts `initiation.reserve` writes no gift-card attribute, so the omission stays deliberate and
visible instead of becoming a silent gap.

### 8.4 The executing function for every write

| Stage / attribute write | Executing function | Tables touched |
|---|---|---|
| `GC_HELD` — in-WhatsApp | `wecare-checkout` (`checkout/handler.py::_create`) | PaymentAttemptsTable, GiftCardsTable |
| `GC_HELD` — website | whichever function calls `website_checkout.prepare_checkout` | PaymentAttemptsTable, GiftCardsTable |
| `GC_REDEEMED` | whichever function runs `finalization.accept_paid` | PaymentAttemptsTable, GiftCardsTable |
| `verifiedCapturedPaise` | the same function, inside `record_paid` (SEAM-G13) | PaymentAttemptsTable |
| `GC_VOIDED` | `wecare-wix-giftcard-spi` (`/v1/void`) and the release path | PaymentAttemptsTable, GiftCardsTable |

`wecare-checkout-role` already grants `GetItem, PutItem, UpdateItem` on exactly
`stack-wecare-digital-PaymentAttemptsTable` and `stack-wecare-digital-WixOrderIds`
(`scripts/provision_checkout.py` lines 391–400, where `COMMERCE_KEYS_TABLE =
"stack-wecare-digital-WixOrderIds"`). What it lacks is access to `GiftCardsTable`, which
SEAM-G9 grants additively. The SPI function needs `UpdateItem` on PaymentAttemptsTable too, and
§10.1 grants it explicitly rather than assuming it.

**Which function hosts `website_checkout.prepare_checkout` cannot be answered from the tree.**
The module is handler-free by design, and no handler in `amplify/functions/` calls it yet. That
is owner item 12.2.9, alongside the existing "which function finalizes" question, and the two
may well have the same answer.

### 8.5 `blog_contribution.prepare_contribution` — out of scope, with a reason (new in revision 4, R4-M3)

The fourth attempt producer, written in the shape of §8.3 so the two omissions are judged by the same
standard. `amplify/functions/shared/lambda_utils/ecommerce/blog_contribution.py::prepare_contribution`
(function at line 213) builds an attempt at **line 355**, and its own docstring calls it a **sibling
of `website_checkout`** — which is precisely why it cannot be left unmentioned: a reader who has just
read §8.1 will reasonably expect the sibling to get the same treatment.

**It is declared out of scope for the gift-card split, on one decisive ground and two supporting
ones:**

1. **A contribution flow has no Wix cart, so there is no `wixCollectionPaise` to cap a redemption
   against.** This is structural, not a scheduling choice. §4.1's cap is
   `min(balance_paise, wix_collection_paise - RAZORPAY_MIN_LEG_PAISE)`, and R4-H4 exists precisely to
   stop that cap being taken against anything other than the Wix collection total. A contribution has
   a contribution amount and **no Wix supply line at all**, so there is no second figure; capping
   against the contribution amount would be inventing a rule for a flow nobody has designed gift cards
   into. **A gift card is a liability** — spending one against an undefined cap spends real money on an
   unspecified path.
2. **§4.2's six reconciliation identities are all stated against a Wix cart summary.** With no cart
   summary there is nothing to reconcile, so the refusal that protects every other path would not run.
3. **It is a different product decision.** Whether a gift card may fund a blog contribution at all is
   an owner question (is a contribution a purchase?), not an implementation gap.

**The consequence, named rather than left implicit:** a gift card must never reach this producer. It
cannot today, because nothing in the contribution path reads a gift-card code — and **test 113b
asserts `prepare_contribution` writes no gift-card attribute**, which is what keeps that true. If
contributions are later meant to accept gift cards, the work is to define the cap for a flow with no
Wix collection total, and only then to apply §8.1's split table.

---

## 9. Testability and the test list

Unit-testable offline, with no AWS and no network: the §5 JWT verification (an RSA keypair
generated in the fixture), the §3 ladder and `is_fully_settled`, every amount conversion, the §4.2
reconciliation identities, every documented error mapping, and all input validation. Every module
takes injected dependencies, so this is the bulk of the surface.

Integration-testable with a local DynamoDB: the conditional-write invariants — the balance floor,
the `GCORDER#` claim, `GCTXNID#` and `GCWIXORDER#` resolution, hold expiry, and `advance()`'s
forward-only guard — because they are properties of the database engine and a mock that returns
what it is told proves nothing about them.

Not testable without owner action: whether Wix actually calls `/v1/balance` with the envelope as
documented, which signing algorithm it uses, and whether `Add Gift Card` + `Calculate Cart` produce
the `paymentSummary` §4.2 expects. All three need the SPI registered (§12.1) and are recorded as
such rather than asserted.

### 9.1 Test list

`tests/test_gift_card_spi_auth.py` — **decision 4**

1. `test_a_body_that_is_not_a_jwt_is_refused` — 401, empty body.
2. `test_a_content_type_that_is_not_jwt_or_text_is_refused`.
3. `test_a_base64_encoded_api_gateway_body_is_decoded_before_parsing` — `isBase64Encoded: True`.
4. **`test_a_jwt_in_an_authorization_header_with_a_non_jwt_body_is_refused`** — the body is the
   only token source; closes MEDIUM-18 against a later "helpful" header fallback.
5. `test_the_spi_request_object_is_read_from_data_request` — a payload with `request` at the root
   and nothing under `data` is refused; pins revision 2's envelope correction.
6. `test_the_metadata_is_read_from_data_metadata_as_a_context`.
7. `test_a_signature_from_the_wrong_key_is_refused`.
8. `test_alg_none_is_refused` — the classic confusion attack.
9. `test_an_hmac_alg_with_the_public_key_as_secret_is_refused` — the key-confusion form.
10. `test_the_token_cannot_choose_its_own_algorithm` — only RS256/384/512 accepted.
11. `test_an_aud_that_is_not_our_app_id_is_refused`, and a multi-valued `aud` is refused.
12. `test_an_iss_other_than_wix_com_is_refused` — exact string.
13. `test_an_expired_spi_token_is_refused` and `test_an_spi_iat_in_the_future_is_refused` — ±60s
    skew. Prefixed because `tests/test_customer_auth_and_throttle.py:92` already owns the
    unprefixed name for a Cognito token, and two identically named failures in one report are
    ambiguous about which auth path broke.
14. `test_a_missing_iat_or_exp_is_refused_not_defaulted`.
15. `test_an_instance_id_that_is_not_the_installed_instance_is_refused`.
16. `test_verification_happens_before_the_body_is_interpreted` — the store is a spy; zero calls on
    a bad token.
17. `test_verification_happens_before_any_table_access` — pins the ordering §5.2 relies on.
18. `test_a_failure_returns_no_error_detail` — body is empty for every rejection.
19. `test_the_public_key_is_read_lazily_per_request_not_at_import` — the 2026-09-19 defect class.
20. `test_the_public_key_and_pepper_never_appear_in_a_logging_expression` — AST walk of every
    `logger.*` argument, transitively through local helpers.
21. `test_the_envelope_metadata_request_id_is_the_log_correlator` — Wix offers it for exactly this.

`tests/test_gift_card_spi_contract.py`

22. `test_the_three_documented_paths_are_served` — `v1/balance`, `v1/redeem`, `v1/void`.
23. `test_no_fourth_spi_path_exists`.
24. `test_get_balance_returns_exactly_balance_currency_and_external_id` — no extra field.
25. `test_redeem_returns_exactly_remaining_balance_currency_and_transaction_id`.
26. `test_void_returns_exactly_remaining_balance_and_currency`.
27. `test_external_id_is_the_gift_card_id_never_the_code`.
28. `test_every_documented_error_maps_to_its_documented_status` — the full §1.1 table,
    parametrised on `(name, applicationCode, httpCode)`. **All nine rows are now parametrisable**:
    `AlreadyVoided`'s `applicationCode` is `ALREADY_VOIDED`, transcribed from the Void page's
    `errors[]` in §1.1 (closes MEDIUM-10's first half).
28a. **`test_an_error_body_carries_exactly_name_and_application_code`** — the body is exactly
    those two keys, flat, with no third key and no invented wrapper. §1.1.1 establishes that Wix
    publishes **no** error-response schema (`responses` declares only `200` on all three
    methods), so this test pins our minimal choice and makes the diff one function wide if Wix
    later publishes an envelope. Closes MEDIUM-10's second half, by measurement rather than
    invention.
28b. **`test_the_spi_error_name_is_the_spi_error_data_name_not_the_wix_error_class`** — we
    return `AlreadyVoided`, never `AlreadyVoidedWixError`. Both strings appear on the docs page
    and confusing them puts the wrong value in the right place.
29. `test_a_malformed_code_answers_not_found_not_bad_request` — no validity oracle.
30. `test_a_wrong_pin_is_indistinguishable_from_an_unknown_code`.
31. `test_amount_is_parsed_as_decimal_never_float` — patches `float` to raise.
32. `test_a_sub_paise_amount_is_refused_rather_than_rounded` — `12.345`.
33. `test_the_balance_response_renders_a_json_number_without_constructing_a_float`.
34. `test_a_non_inr_currency_is_refused_with_currency_not_supported`.
35. `test_the_deprecated_app_instance_id_is_never_used_for_identity` — identity is the JWT.
36. `test_location_id_is_accepted_and_ignored`.
37. **`test_a_wix_redeem_for_a_card_with_a_hold_is_already_redeemed`** — closes HIGH-4's first
    half: a `/v1/redeem` carrying a **Wix order GUID** against a card holding a
    `GCHOLD#<codeHash>#<paymentAttemptId>` row returns 409 `AlreadyRedeemed` and deducts nothing.
38. **`test_a_wix_redeem_for_an_already_claimed_card_deducts_nothing`** — the same against a
    `GCORDER#` claim, with the balance asserted unchanged before and after. This is the test the
    review asked for by name.
39. `test_a_wix_redeem_with_no_hold_and_no_claim_is_honoured_and_marked_wix_spi` — the conforming
    path, so the refusal above is narrow rather than a blanket rejection.
40. `test_a_wix_order_id_resolves_to_our_reference_through_the_pointer_row` — `GCWIXORDER#`.
41. `test_a_void_arriving_by_transaction_id_reconciles_to_the_purchase`.

`tests/test_gift_card_store.py`

42. `test_the_partition_key_is_an_hmac_not_the_code` — the code is absent from every key.
43. `test_the_code_is_never_stored_in_clear` — only `codeLast4`.
44. `test_logs_carry_only_the_last_four_digits` — AST + runtime capture.
45. `test_no_route_accepts_a_code_in_a_path_or_query` — enumerates route templates.
46. `test_a_coupon_code_may_be_logged_but_a_gift_card_code_may_not` — pins the deliberate
    asymmetry against the coupon design so neither is "harmonised".
47. `test_the_balance_cannot_go_negative_under_concurrency` — two redemptions, one fails.
48. `test_the_balance_floor_is_a_condition_expression_not_a_read_then_write`.
49. **`test_a_second_redeem_for_the_same_payment_attempt_returns_the_same_transaction_id`** — §3.4.
    Renamed per R4-M7: the claim is keyed on `paymentAttemptId`, and "reference" was revision 2's key.
50. **`test_a_second_redeem_for_the_same_payment_attempt_does_not_move_the_balance`** — renamed, R4-M7.
51. **`test_the_issuance_ceiling_is_the_spi_maximum`** — `99_999_999_999` paise accepted; closes
    MEDIUM-14's lower boundary.
52. **`test_a_value_above_the_spi_maximum_is_refused`** — `100_000_000_000` paise refused, at
    issuance **and** on a later credit.
53. **`test_two_different_payment_attempts_each_deduct_once`** — renamed, R4-M7. Two genuinely
    different purchases of one card must **each** deduct, which is why `_decrement` does not gate on
    the claim (§6.5).
54. `test_the_claim_is_written_before_the_balance_moves` — call ordering; replay safety.
55. `test_a_void_resolves_the_card_from_the_transaction_id_alone` — the `GCTXNID#` row, because
    `VoidRequest` has no code.
56. `test_a_void_returns_the_balance_to_the_card`.
57. `test_a_second_void_is_already_voided` — 409.
58. `test_a_hold_past_its_expiry_does_not_block_another_purchase`.
59. `test_a_disabled_card_cannot_be_redeemed` and `test_an_expired_card_cannot_be_redeemed`.
60. `test_nothing_in_the_store_deletes_a_card_a_transaction_or_a_pointer_row` — enumerates delete
    sites; holds only.
61. `test_a_card_row_carries_no_ttl_attribute` — an expiring liability.
62. `test_the_code_is_generated_with_secrets_not_random` — AST; the SnapStart PRNG hazard.
63. `test_the_generated_code_is_within_the_spi_length_bounds` — 8 ≤ len ≤ 20.
64. `test_integer_paise_only` — floats and bools refused by type at every entry.

`tests/test_gift_card_two_leg_finalization.py` — **decision 3**

65. `test_a_verified_razorpay_capture_alone_is_not_fully_settled` — the headline property.
    `giftCardRequiredPaise > 0`, Razorpay leg `PAYMENT_PAID` with a verified provider id,
    gift-card stage `GC_HELD` → `is_fully_settled` is **False**.
66. `test_fully_settled_needs_our_own_redemption_transaction_id` — stage `GC_REDEEMED` but no
    `giftCardTransactionId` → False.
67. `test_a_short_redeemed_amount_is_not_fully_settled` — `giftCardRedeemedPaise < required`
    with stage `GC_REDEEMED` → False.
68. `test_both_legs_present_is_fully_settled` → True.
69. **`test_an_attempt_with_only_razorpay_attributes_is_fully_settled`** — the dict carries
    `status`, `verifiedProviderPaymentId`, `amountPaise`, `razorpayChargedPaise` and **no
    gift-card key at all** → True. Closes HIGH-1; this is the test that would have caught it.
70. `test_an_explicit_gc_not_required_stage_is_also_fully_settled` — the other half of the
    `required == 0` branch.
71. `test_a_held_stage_with_nothing_required_fails_closed` — the contradiction case.
72. `test_the_gift_card_leg_alone_is_never_fully_settled` — no Razorpay evidence → False.
73. `test_the_stage_ladder_is_forward_only` — every backward transition refused.
74. `test_a_void_outranks_a_redeem_so_a_replayed_redeem_cannot_unvoid` — the §3.1 ranking.
75. `test_a_hold_carries_no_evidence_and_never_counts_as_settlement`.
76. `test_an_unknown_stage_ranks_zero_and_overwrites_nothing`.
77. **`test_advance_is_a_conditional_update_not_a_read_then_write`** — asserts the call passes
    `ConditionExpression` equal to `condition_expression()` and that no `get_item` precedes it;
    closes HIGH-2's correctness half.
78. **`test_advance_refuses_an_evidence_key_outside_the_closed_set`**.
79. **`test_advance_raises_stage_regressed_on_a_conditional_failure`** — a backward move surfaces
    rather than silently no-opping.
80. **`test_the_hold_is_taken_after_the_attempt_id_is_minted_and_before_the_gateway`** — §8 ordering.
    **Renamed per R4-M7, and the old name was not merely stale but UNSATISFIABLE.** §3.4 establishes
    that on the website path `referenceId` **is** the Razorpay gateway order id, so "after the
    reference is minted and before the gateway" asks for an ordering that cannot exist there — the
    reference does not exist until the gateway has been called. The new name states the property that
    is true on **both** producers, which is exactly what the §3.4 re-key bought.
81. `test_the_redemption_happens_after_capture_is_verified` — §3.3 ordering.
82. `test_a_failed_gateway_releases_the_hold_and_deducts_nothing`.
83. **`test_a_tampered_redeem_amount_cannot_reach_a_settled_order`** — drives a `redeemAmount`
    altered after the quote was frozen through both gates and asserts the §4.2 reconciliation
    refuses it pre-hold **and** `is_fully_settled` returns False post-hoc. Asserts against
    **`verifiedCapturedPaise`**, the provider-confirmed figure, not the intended
    `razorpayChargedPaise` (closes HIGH-3).
83a. **`test_an_absent_verified_capture_amount_is_not_settled_and_does_not_raise`** — an attempt
    with `giftCardRequiredPaise > 0`, a full `GC_REDEEMED` stage, and **no**
    `verifiedCapturedPaise` returns `False`. Closes HIGH-2's unspecified failure mode: revision 2
    read the attribute with a bracket subscript, so this case raised `KeyError` inside
    finalization **after** a verified capture.
83b. `test_an_absent_amount_paise_is_not_settled_and_does_not_raise` — the same property for the
    payable, since `is_fully_settled` gates order completion and must never throw.
83c. **`test_a_short_verified_capture_is_not_settled_even_when_both_stages_look_right`** — the
    Razorpay readback reports less than `payNowPaise`; both legs' stages and ids are present and
    correct; `is_fully_settled` is `False`. This is the property revision 2's closure could not
    detect, because it compared two numbers written by the same code in the same request.
83d. **`test_the_settlement_decision_never_reads_the_intended_gateway_figure`** — AST: no
    reference to `razorpayChargedPaise` inside `is_fully_settled`. Pins §6.5's division of the
    two attributes so a later "simplification" cannot put the intended figure back in the
    closure.
84. `test_a_redemption_failure_after_capture_lands_in_needs_reconciliation` — never "paid".
85. `test_nothing_here_writes_the_razorpay_machinery` — AST: no reference to
    `PROVIDERPAYMENT#`, `record_paid`, `payment_attempt.transition` or `razorpay_verify`.
86. `test_the_attempt_keeps_the_full_payable_as_amount_paise` — pins §8 point 3, so the Wix order
    cannot be recorded short.

`tests/test_gift_card_amounts_and_gst.py` — **decision 2**

87. `test_the_convenience_fee_is_computed_on_the_full_collection_total` — the §2 worked example:
    fee `2500`, GST `450`, not `1574`/`283`.
88. `test_the_gift_card_does_not_enter_the_quote` — `compute_quote` receives the full collection.
89. `test_pay_now_plus_gift_card_equals_the_total_payable` — exactly, in paise.
90. `test_the_quote_still_reconciles` — `collection + fee + gst == total`.
91. `test_a_gift_card_is_a_tender_line_not_a_discount_line` — the receipt projection.
92. `test_a_one_paise_disagreement_with_wix_fails_closed` — R6.2; nothing charged.
93. `test_wix_pay_now_is_reconciled_against_both_totals` — the two §4.2 identities.
94. `test_requires_payment_after_gift_card_false_refuses_the_checkout` — §4.4 full cover.
95. **`test_an_absent_requires_payment_after_gift_card_also_refuses`** — absence is `False`;
    closes MEDIUM-9's third part, and it is why the existing
    `test_a_gift_card_that_covers_the_whole_total_is_still_refused` fixture (which does not set
    the field) still refuses after SEAM-G1.
96. **`test_a_redeem_at_the_cap_is_accepted`** —
    `redeemCap = min(balance, wixCollectionPaise - 100)`, the HIGH-4 cap.
97. **`test_a_redeem_above_the_cap_is_refused_not_clamped`** — `redeemCap + 1`.
97a. **`test_a_redeem_equal_to_the_wix_collection_total_is_refused_before_wix_is_consulted`** —
    `wixCollectionPaise`. One of the two boundaries HIGH-4 asked for by name: under revision 2's
    cap this value was *inside* `redeemCap` and *above* what Wix could apply, so the §4.2 identity
    would have refused it after the request reached Wix. Now it is refused by our own cap, with
    the Wix adapter a spy asserting zero calls.
97b. **`test_a_redeem_above_the_wix_collection_total_is_refused`** — `wixCollectionPaise + 1`;
    the other boundary.
97c. **`test_the_convenience_fee_is_never_funded_by_the_gift_card`** — HIGH-4's decision as a
    property rather than a cap: for every accepted redemption,
    `payNowPaise - wixPayNowPaise == quote.convenience_fee_paise + quote.convenience_gst_paise`
    (§4.2 identity 6). Parametrised across a range of balances including one far exceeding the
    cart total.
98. **`test_a_remainder_below_the_razorpay_minimum_is_refused_before_the_hold`** — a split leaving
    1–99 paise refuses with `GIFT_CARD_LEAVES_UNCHARGEABLE_REMAINDER`, and the hold is never
    taken; closes MEDIUM-13.
99. `test_only_one_gift_card_is_accepted` — Wix's documented limit, enforced by us.
100. `test_memberships_and_subscription_charges_are_still_refused` — **decision 5**; only
     `giftCards` opened.

`tests/test_gift_cards_iam_and_table.py`

101. `test_the_spi_function_has_its_own_role` — not the shared fleet role.
102. `test_each_policy_names_only_the_two_expected_table_arns` — GiftCardsTable (+ its index) and
     PaymentAttemptsTable; closes HIGH-2's permission half.
103. `test_no_policy_has_scan_or_a_wildcard_action`.
104. `test_the_spi_role_cannot_issue_a_card` — issuance is the other function.
105. `test_the_spi_role_has_no_delete_item`.
106. `test_no_wildcard_was_added_to_the_shared_lambda_role` — **decision 6**.
107. **`test_the_checkout_role_gains_only_the_gift_cards_table`** — the additive statement on
     `wecare-checkout-role`.
107a. **`test_the_iam_simulation_covers_every_action_the_checkout_policy_grants`** — SEAM-G9's
     second half: every `dynamodb:*` action in `provision_checkout.py`'s policy is a subset of
     `_SIMULATED_ACTIONS`, and every table ARN in the policy appears in the simulated `tables`
     list. Closes MEDIUM-18 from this side. Shares its subject with the coupon document's test
     52a — both seams change the same two lists — so whichever lands second extends the
     assertion rather than duplicating the test.
108. `test_the_provisioner_asserts_ttl_disabled_and_pitr_enabled`.
109. `test_the_wix_spi_redemption_alarm_exists_with_a_threshold_of_one` — the §6.5 alarm.
109a. `test_the_charge_mismatch_alarm_exists_with_a_threshold_of_one` — the §6.5
     charged-versus-captured detector, which only exists because both figures are now on the row.
110. **`test_the_spi_handlers_top_level_imports_are_covered_by_its_layers`** — resolves every
     top-level import in `wix-giftcard-spi/handler.py` and `gift_card_spi_auth.py` against the
     package plus the declared layer set, the same way `deploy_all_lambdas.py` does. Closes
     HIGH-6's failure mode: the deploy gate must not be the first place a missing
     `cryptography` layer is discovered.
111. **`test_the_provisioner_attaches_the_pinned_cryptography_layer`** — asserts
     `provision_gift_cards_roles.py` names
     `arn:aws:lambda:us-east-1:775261844268:layer:cryptography-python312:1` exactly, **version
     pinned**, so a republished layer cannot change signature verification on a payment route
     with no code change.
112. **`test_the_website_checkout_split_binds_the_charged_amount_and_the_payable_separately`** —
     one simulated website checkout; asserts `binding["amountPaise"] == payNowPaise`,
     `attempt["amountPaise"] == quote.total_payable_paise` and
     `attempt["razorpayChargedPaise"] == payNowPaise`, **and `options["amountPaise"] == payNowPaise`**
     (R4-M2 — the figure the browser is shown). Closes HIGH-1, and it is the test that
     catches both obvious wrong resolutions of it (§8.1).
113. **`test_the_initiation_reserve_path_writes_no_gift_card_attribute`** — pins §8.3's
     out-of-scope decision as deliberate and visible rather than a silent gap.
113b. **`test_the_blog_contribution_path_writes_no_gift_card_attribute`** — the same gate for the
     **fourth** attempt producer, §8.5 (R4-M3). Not pending: it is a gate, and it must keep passing.
114. **`test_no_recorded_payment_exceeds_the_verified_capture_for_its_transaction_id`** — the
     overstatement MEDIUM-15 identified: `record_external_payment` receives
     `verifiedCapturedPaise`, never `attempt["amountPaise"]`.
115. **`test_the_gift_card_tender_claims_a_different_effect_key_from_the_razorpay_payment`** —
     `WIX_GIFT_CARD_TENDER` versus `WIX_PAYMENT`, and that `WIX_GIFT_CARD_TENDER` is in
     `side_effect_guard.KNOWN_EFFECTS`, without which the claim is refused.

**Depended on, not duplicated:** `coupons-20261001.md` test 57 asserts
`"GiftCardsTable" in check_data_model_drift.UNDECLARED_ALLOWED`. That document owns the edit and
the test; this one does not repeat either (closes MEDIUM-10/MEDIUM-12 without a double edit).

Both new handlers are added to **`RAW_SCAN_ONLY_FILES`**, not `CONSULTING_FILES`, in
`tests/test_payment_vocabulary_at_decision_points.py`. Neither has a payment-status decision — the
gift-card ladder is its own module — so the AST ban on a raw `'captured'` comparison applies while
the import assertion does not. `coupons-20261001.md` §9 owns that edit and quotes the exact
three-entry list, including `ecommerce/wix-giftcard-spi/handler.py`.
---

## 10. Scoped IAM, owned files, and cross-workstream seams

### 10.1 Scoped IAM (closes HIGH-5)

Revision 2 specified **no IAM at all** for either new function, while asserting in §13 that "the
role spec" granted various permissions and shipping seven tests (101–107) asserting properties of
policies the design never wrote down. The coupon document had a full §6; this is the matching
section, and it is written out so a provisioner and its tests can be written from the document.

Both roles are created by `scripts/provision_gift_cards_roles.py` (owned here). **Neither is
`wecare-digital-lambda-role`**, the shared fleet role, and no statement is added to it — a
widening there would grant all 65 functions access to a liability ledger. Test 106 asserts it.

```
role:   wecare-gift-cards-role                     (for wecare-gift-cards)
trust:  lambda.amazonaws.com
        Condition: StringEquals { aws:SourceAccount: "775261844268" }
policy: wecare-gift-cards-table
  dynamodb:GetItem, PutItem, UpdateItem, Query, DeleteItem
    on arn:aws:dynamodb:us-east-1:775261844268:table/stack-wecare-digital-GiftCardsTable
    and        .../table/stack-wecare-digital-GiftCardsTable/index/status-index
  secretsmanager:GetSecretValue
    on arn:aws:secretsmanager:us-east-1:775261844268:secret:wecare/wix/giftcard-spi-*
  logs:CreateLogStream, logs:PutLogEvents on its own log group
```

```
role:   wecare-wix-giftcard-spi-role               (for wecare-wix-giftcard-spi)
trust:  lambda.amazonaws.com
        Condition: StringEquals { aws:SourceAccount: "775261844268" }
policy: wecare-wix-giftcard-spi-tables
  dynamodb:GetItem, PutItem, UpdateItem, Query
    on arn:aws:dynamodb:us-east-1:775261844268:table/stack-wecare-digital-GiftCardsTable
    and        .../table/stack-wecare-digital-GiftCardsTable/index/status-index
  dynamodb:UpdateItem                              # the GC_VOIDED write, §8.4
    on arn:aws:dynamodb:us-east-1:775261844268:table/stack-wecare-digital-PaymentAttemptsTable
  secretsmanager:GetSecretValue
    on arn:aws:secretsmanager:us-east-1:775261844268:secret:wecare/wix/giftcard-spi-*
  logs:CreateLogStream, logs:PutLogEvents on its own log group
layers: arn:aws:lambda:us-east-1:775261844268:layer:cryptography-python312:1   (§5.1.1)
```

The differences between the two are the whole point of having two, and each is deliberate:

| | `wecare-gift-cards` | `wecare-wix-giftcard-spi` | Why |
|---|---|---|---|
| `dynamodb:DeleteItem` | **yes** | **no** | only the staff/customer function releases a `GCHOLD#` row; the SPI has no reason to delete anything, and a card, transaction or pointer row is never deleted by either (test 60) |
| `UpdateItem` on PaymentAttemptsTable | **no** | **yes** | the SPI writes `GC_VOIDED` through `advance()`; issuance never touches a payment attempt |
| reachable by Wix | no | **yes**, no authorizer | which is exactly why issuance is not in this function (§7) |

Neither policy has `dynamodb:Scan`, `dynamodb:*`, `dynamodb:DeleteTable`, `Action: "*"`, or
`Resource: "*"`. No `Query` on PaymentAttemptsTable: both functions reach an attempt only by its
exact `paymentAttemptId`.

**Why the SPI role cannot issue a card, enforced twice.** The IAM grant is identical for
`PutItem` on `GiftCardsTable` in both roles, because the SPI must write `GCTXN#`, `GCTXNID#` and
`GCORDER#` rows — so IAM alone cannot distinguish issuance from a transaction record. The
guarantee is therefore structural rather than permissive: issuance lives in `gift_card_store`'s
`issue()`, which is called only from `wecare-gift-cards`' handler, and the SPI handler has no code
path to it. Test 104 asserts it by AST, and the table-level separation is stated here so nobody
later reads "both can PutItem" as a finding.

**One secret, both functions.** `wecare/wix/giftcard-spi` carries `public_key`, `app_id`,
`instance_id` and `code_pepper` (§12.1 step 5). Both functions need `code_pepper` to derive
`codeHash`; only the SPI needs `public_key`. Splitting it into two secrets was considered and
rejected: the pepper is the field both need, so a split would mean two secrets with overlapping
contents and two rotation procedures. The ARN pattern ends `-*` because Secrets Manager appends a
six-character suffix to every secret ARN, and a pattern without it matches nothing.

Read **lazily at request time**, never at module scope. `whatsapp-payments-india-reference.md`
records why: a module-scope read caches for the life of the execution environment, so a rotation
does not take effect until every warm sandbox recycles — the defect fixed in
`payments/razorpay-webhook` on 2026-09-19. Test 19 asserts it.

`secretsmanager get-secret-value` and `batch-get-secret-value` are never called from a shell or
from `aws___run_script`; the grant above is for the **function at runtime**, which is the only
place a secret value is permitted to exist.

### 10.2 Owned files — new files only

```
amplify/functions/ecommerce/gift-cards/handler.py
amplify/functions/ecommerce/wix-giftcard-spi/handler.py
amplify/functions/shared/lambda_utils/ecommerce/gift_card_store.py
amplify/functions/shared/lambda_utils/ecommerce/gift_card_settlement.py
amplify/functions/shared/lambda_utils/ecommerce/gift_card_spi_auth.py
scripts/provision_gift_cards_table.py
scripts/provision_gift_cards_roles.py
scripts/provision_gift_card_routes.py          # RENAMED from ..._gift_card_spi_routes.py (R4-N3)
tests/test_gift_card_spi_auth.py
tests/test_gift_card_spi_contract.py
tests/test_gift_card_store.py
tests/test_gift_card_two_leg_finalization.py
tests/test_gift_card_amounts_and_gst.py
tests/test_gift_cards_iam_and_table.py
tests/fixtures/wix_spi_get_balance_jwt_payload.json
tests/fixtures/wix_spi_redeem_jwt_payload.json
tests/fixtures/wix_spi_void_jwt_payload.json
tests/fixtures/wix_cart_v2_gift_card_partial.json
```

> **One exception to "edits no shared file", and it is R4-H5's.** `scripts/provision_checkout.py`
> **was** edited, under DECISION 7, because SEAM-G9's three parts cannot be split without breaking the
> script's own `--verify` gate. It is the only file outside the list above that this work touched, and
> it was done in one visit covering both new table ARNs. The three **gate** files below are still
> edited exclusively by the coupon document's owner.

**This document edits no other shared file.** All **three** gate edits are owned exclusively by
`coupons-20261001.md` §8 and are *dependencies* here: the two `UNDECLARED_ALLOWED` entries, the
`RAW_SCAN_ONLY_FILES` list, and — new in revision 3 — the three `Spec(...)` entries in
`scripts/deploy_all_lambdas.py`, **two of which are this document's functions**
(`wecare-gift-cards`, `wecare-wix-giftcard-spi`). They are quoted verbatim there, including
`provisioned_by`, and asserted by that document's test 65. One file, one session, one commit, per
the workspace's multi-session rule 3b.

That assignment is worth stating plainly rather than burying: without those registry entries
§12.3's `deploy_all_lambdas.py wecare-gift-cards wecare-wix-giftcard-spi` is a no-op, because the
script deploys from an explicit `SPECS` list and a name absent from it is not deployable. So this
document's deploy sequence has a hard dependency on the coupon document's edit, and the
dependency runs that way round because the registry is one shared file and rule 3b says one
session edits it.

### 10.3 Read-only, never edited

`cart_v2.py`, `customer_cart.py`, `wix_ecom.py`, `wix_writeback.py`, `checkout_pricing.py`,
`purchase_intent.py`, `money.py`, `payment_status.py`, `payment_attempt.py`, `order_keys.py`,
`identifiers.py`, `finalization.py`, `initiation.py`, `side_effect_guard.py`, `meta_version.py`,
`whatsapp_types.py`, `wix_ecom.py`, `ecommerce/wix_writeback.py`,
`amplify/functions/ecommerce/wix-store/handler.py`,
`amplify/functions/ecommerce/checkout/handler.py`, `packages/config/vendorVersions.ts`,
`scripts/meta_webhook_control_plane.py`, `config/lambda-env-manifest.json`,
`scripts/check_data_model_drift.py`,
`tests/test_payment_vocabulary_at_decision_points.py`,
`tests/test_wix_cart_v2_coupons_and_stock.py`.

> **`scripts/provision_checkout.py` was on this list and has been REMOVED from it (R4-H5).** The
> three parts of SEAM-G9 cannot be split across sessions without breaking the script's own `--verify`
> gate, so DECISION 7 assigns the file to this work in one visit. It landed; the coupon document's
> §5.2.1 holds the detail. `amplify/functions/ecommerce/checkout/handler.py` stays read-only.
>
> `check_data_model_drift.py` and `test_payment_vocabulary_at_decision_points.py` remain read-only
> **to this document** — they are edited exactly once, by `coupons-20261001.md`'s owner (§10.2).

### 10.4 Seams

| id | Seam | Exact function / line | Who |
|---|---|---|---|
| **SEAM-G1** | Narrow the partial-payment refusal to `memberships` + `subscriptionCharges`; permit `giftCards`; replace the `payNow == totalAfterGiftCards == total` equality with the §4.2 identities, treating an absent `requiresPaymentAfterGiftCard` as `False`. **Do not open the other two.** | `cart_v2.CartV2.calculate`, the `if any(payment.get(key) for key in (...))` check and the `for field in ("payNow", "totalAfterGiftCards")` loop | cart_v2 owner |
| **SEAM-G2** | Add `add_gift_card` / `remove_gift_card` to the adapter, with `{"giftCard": {"code": ..., "redeemAmount": {"amount": Money.to_wix()}}}` and `{"giftCardId": ...}` on removal. `cart_v2.py` deliberately has neither today. | `cart_v2.CartV2` | cart_v2 owner |
| **SEAM-G3** | Surface `coupons[0].id` and `giftCards[0].id` on the payable cart projection so a customer can remove either — both removals require the id. `_not_payable` already returns `coupons`, and `calculate`'s return dict **does** carry both ids (it returns `"cart": deepcopy(cart)`, and `cart["coupons"]` holds `{id, code}`); they are **not surfaced on the payable projection** the cart view is built from (closes NIT-19 — revision 2 said "returns neither id", which was wrong; the seam stands for the narrower reason). | `cart_v2.CartV2.calculate`'s payable projection | cart_v2 owner |
| **SEAM-G4** | Take the hold after `attempt_id` is minted and before the attempt is stored; write `GC_HELD` through `advance()`. Keyed on `paymentAttemptId` (§3.4), so it no longer has to wait for `allocate_payment_reference`. | `amplify/functions/ecommerce/checkout/handler.py::_create`, between `attempt_id = payment_attempt.new_payment_attempt_id()` and `_attempts_table().put_item` | checkout workstream |
| **SEAM-G5** | Call `gift_card_settlement.redeem` after capture is verified, write `GC_REDEEMED` through `advance()`, and gate order completion on `is_fully_settled` rather than on the Razorpay leg alone. Target today is `finalization.accept_paid` between `record_paid` and `_stage(..., 'INTERNAL_ORDER_CREATED')`; **that function is untracked and has zero callers** (§11), so the fallback applies. | `finalization.accept_paid` | finalization owner |
| **SEAM-G6** | The Wix order payload must carry the gift card as a tender record and the convenience fee as `additionalFees[]`, so `Money.from_wix(order["priceSummary"]["total"]["amount"]).paise == quote.total_payable_paise == verifiedCapturedPaise + giftCardRedeemedPaise` — the **verified** figures, per revision 3's HIGH-3. **This is the same single invariant stated in `coupons-20261001.md` §2.3**, with the gift-card term zero when no card is applied. | the builder of `attempt['wixOrderPayload']` | checkout workstream |
| **SEAM-G7** | The Wix order's payment records. **Two parts**, and revision 2 stated the failure backwards. See the detail below (closes MEDIUM-15). | `wix_writeback.record_external_payment`; `side_effect_guard.KNOWN_EFFECTS` | wix_writeback owner |
| **SEAM-G8** | Insert the §4.1 split at `amount_paise = snapshot.quote.total_payable_paise`, keeping `attempt["amountPaise"]` as the **full payable** and storing the gateway figure as `razorpayChargedPaise`. Four numbered steps in §8.2. | `amplify/functions/ecommerce/checkout/handler.py::_create` | checkout workstream |
| **SEAM-G9** | ✅ **LANDED 2026-10-02 — no longer a seam.** **THREE parts, not two** (R4-H5). (a) a second DynamoDB statement, `Sid: CouponAndGiftCardRedemption`, granting `GetItem, PutItem, UpdateItem, DeleteItem` on the `GiftCardsTable` **and** `CouponsTable` ARNs, additively, on a per-function role — never the shared fleet role. (b) `_SIMULATED_ACTIONS` gains `dynamodb:DeleteItem` and the simulated `tables` list gains both new ARNs. (c) `_EXPECTED_DENY` plus the verdict loop re-keyed on `(EvalActionName, EvalResourceName)` — without which a **correctly** provisioned role fails its own `--verify`, because `DeleteItem` allowed on two tables and implicitly denied on two aggregates to a non-`{"allowed"}` set under the old per-action key. **Both tables landed in ONE visit**, so the "whichever seam lands second adds only its ARN" ordering hazard never arose. Tests 107 and 107a now pass (107's mark removed; 107a never carried one — see §13). | `scripts/provision_checkout.py`, current anchors: constants `:132-133`, statement `:407` with ARNs `:418-419`, `_SIMULATED_ACTIONS` `:683`, `_EXPECTED_DENY` `:696`, `tables` `:821-824`, verdict key `:848`. **Re-derive rather than trust these** — the revision-3 numbers (661 / 785) were one off (R4-N2 corrects them to 662 / 785) and have since moved outright | **this work** (DECISION 7) |
| **SEAM-G10** | `GCWIXORDER#<wixOrderId> → paymentAttemptId` must be written when `wixOrderId` first exists. | `finalization.accept_paid`, at the `_stage(..., 'WIX_ORDER_CREATED', wixOrderId=...)` call | finalization owner |
| **SEAM-G13** | `finalization.record_paid` must write **`verifiedCapturedPaise`** beside `verifiedProviderPaymentId`, in the same conditional `UpdateExpression`, taking the amount from the provider readback that justified the call. One added parameter, one added assignment. **Its PRODUCER is now specified (R4-M1):** `outcome` gains `verifiedCapturedPaise`, written by the caller from the **same `razorpay_verify` readback that produced `outcome['providerPaymentId']`** (`website_checkout.py:430`'s `amount_paise`, or the webhook's `provider_paise`) — and **`record_paid` REFUSES a call carrying a provider id without an amount**, because writing the id alone leaves `is_fully_settled` returning `False` forever on a genuinely paid order. Without this seam every gift-card order reads as not-settled; `is_fully_settled` returns `False` and never raises. Rename fallback in §11's table. | `finalization.record_paid` — the `UpdateExpression='SET #s = :paid, ... verifiedProviderPaymentId = :provider'` string and its `ExpressionAttributeValues`; and `accept_paid`'s `outcome` dict | finalization owner |
| **SEAM-G14** | The **website** Razorpay Standard Checkout producer. Apply §8.1's split table — **eight rows, not five** (R4-M2): `payNowPaise` to `create_order`, to `bind_gateway_order`, to the request-key `extra`, to **`_browser_options`** (reaching `options['amountPaise']` at line 145) and to **`_recover_ambiguous_create`**; the **full payable** to `payment_attempt.build`; `payNowPaise` to `attempt["razorpayChargedPaise"]`; and **`_ready_from_binding` NEEDS NO CHANGE** because it reads the amount back off the binding — stated so its absence is deliberate. Take the hold between the `attempt_id` mint (**line 199**, corrected from 198 per R4-N2) and `create_order` (line 231). | `amplify/functions/shared/lambda_utils/ecommerce/website_checkout.py::prepare_checkout`, `_bind_and_ready`, `_browser_options` (128/145), `_recover_ambiguous_create` (328, called 236/239, forwards 344) and `_ready_from_binding` (295/302); lines 193, 199, 203, 231, 265, 281, 288-289 | website-checkout owner |
| **SEAM-G11** | `config/lambda-env-manifest.json` needs `GIFT_CARDS_TABLE`, `WIX_GIFTCARD_SPI_SECRET`, `WIX_GIFTCARD_APP_ID` and `WIX_GIFTCARD_INSTANCE_ID` for both functions. | the manifest | manifest owner |
| **SEAM-G12** | Three existing tests become wrong by construction once SEAM-G1/G2 land. See the table below. | `tests/test_wix_cart_v2_coupons_and_stock.py` | cart_v2 owner |

The earlier SEAM-G8 ("`compute_quote` has no production caller") is **replaced**: the caller exists
(§8), so the seam is now the insertion point rather than the absence of one.

#### SEAM-G7 in detail — the exposure is an OVERSTATED payment, not a short one (closes MEDIUM-15)

Revision 2 wrote: *"With a gift card the Razorpay capture is only part of the total, so a second
tender record is needed **or the Wix order shows a short payment**."* Measured, the failure runs
the other way:

```python
finalization.py:89   wix_writeback.record_external_payment(keys, wix_ecom._request,
finalization.py:91       provider_transaction_id=provider_id, amount_paise=int(attempt['amountPaise']))
```

and §8 point 3 **mandates** that `attempt['amountPaise']` stay the full payable. So the Wix order
would record a payment of the **full payable**, attributed to a Razorpay transaction that captured
only `payNowPaise`. That is an overstated provider payment — a misstatement of provider evidence
on the order Wix keeps, and the opposite of what revision 2 described. Getting the direction
backwards matters because it changes who is harmed: a short payment is a bookkeeping gap, an
overstated one is a record claiming Razorpay collected money it did not.

**Part (a): the recorded Razorpay payment is the verified capture.** `record_external_payment`
receives `verifiedCapturedPaise`, not `attempt['amountPaise']`:

```python
# SEAM-G7(a)
wix_writeback.record_external_payment(keys, wix_ecom._request, ...,
    provider_transaction_id=provider_id,
    amount_paise=int(attempt[RAZORPAY_VERIFIED_PAISE_ATTR]))
```

This is also why `verifiedCapturedPaise` is the right attribute to have added rather than reusing
`razorpayChargedPaise`: the figure attributed to a provider transaction must be the figure that
provider confirmed. On a coupon-only order with no gift card the two are equal, so nothing changes
on the existing path — the value is simply now sourced from the readback.

`record_external_payment`'s own readback already enforces the match, which is what makes this
checkable rather than merely intended:

```python
wix_writeback.py:283   matching = [p for p in payments if
                           (p.get("regularPaymentDetails") or {}).get("providerTransactionId") == provider_transaction_id
                           and p.get("status") == "APPROVED"
                           and Money.from_wix((p.get("amount") or {}).get("amount")).paise == amount_paise]
wix_writeback.py:287   if transactions.get("orderId") != wix_order_id or len(matching) != 1:
                           raise WixWritebackPending("Wix payment response requires reconciliation")
```

**Part (b): the gift-card tender needs its own effect key, and that is itself an edit.** A second
record cannot be added under the existing key. Measured:

```python
wix_writeback.py:253   binding = {"providerTransactionId": ..., "wixOrderId": ...,
                                  "amountPaise": ..., "currency": ...}
wix_writeback.py:256   existing = side_effect_guard.resolve(table, order_id=order_id,
                                  effect=side_effect_guard.WIX_PAYMENT, ...)
#                      (the call opens at 255; its arguments, including order_id, are on 256)
wix_writeback.py:258       if existing.get("result") != binding:
wix_writeback.py:259           raise WixWritebackPending("recorded payment binding differs; readback required")
```

*Line citations corrected per R4-N2: the `resolve` call's arguments are at **256** and the raise at
**259**.*

One `WIX_PAYMENT` claim per `order_id`, bound to those four fields, and a later call presenting a
different binding **raises**. So a gift-card tender record presented under `WIX_PAYMENT` would be
read as a contradicting retry of the Razorpay payment and would refuse.

The new effect is `WIX_GIFT_CARD_TENDER`, and declaring it is a third edit in this seam:

```python
# side_effect_guard.py
WIX_GIFT_CARD_TENDER = "wix_gift_card_tender"
KNOWN_EFFECTS = frozenset({WIX_ORDER, WIX_PAYMENT, WIX_CART_COMPLETED, RECEIPT, CONFIRMATION,
                           WIX_GIFT_CARD_TENDER})
```

`KNOWN_EFFECTS` is a `frozenset` and `side_effect_guard.claim` validates against it, so the
constant must be added there or the claim is refused. The precedent is in the file's own comment
on `WIX_CART_COMPLETED`: *"Its own effect rather than folded into `WIX_ORDER` because it is a
separate remote call"* — which is exactly the situation here, a second `add-payment` call with a
different tender.

One more detail the seam must carry: `record_external_payment` hard-codes
`"paymentMethodName": {"buyerLanguageName": "Razorpay via WhatsApp"}`, which is wrong for a gift
card on two counts. So the gift-card tender needs either a parameter for that field or a sibling
function. **Chosen: a sibling**, `record_gift_card_tender`, because the existing function's
`providerTransactionId`/`offlinePayment: False` shape describes a gateway payment and a gift card
is not one — bending one function to mean both is how `paymentMethodName` came to be hard-coded in
the first place.

Test 114 asserts no single recorded payment exceeds the verified capture for its provider
transaction id, and test 115 asserts the two records claim **different** effect keys so neither
can refuse the other.

#### SEAM-G12 in detail — the existing tests this invalidates (closes MEDIUM-9)

`tests/test_wix_cart_v2_coupons_and_stock.py` belongs to the cart_v2 workstream. Three of its
tests are hard refusals that SEAM-G1/G2 make fail by construction, and revision 1 enumerated none
of them:

| Existing test | Line | What it asserts today | Intended new state |
|---|---|---|---|
| `test_the_adapter_has_no_gift_card_methods_at_all` | 215 | `CartV2` has no `add_gift_card` / `addGiftCard` / `remove_gift_card` / `gift_card` attribute, **and** the strings `/add-gift-card` and `/remove-gift-card` do not appear in `cart_v2.py` | **Deleted.** SEAM-G2 adds exactly those methods and endpoints, so the test is a statement of the old decision, not of a property worth keeping. Replaced by tests 99 and 100 here, which pin what *is* still refused. |
| `test_a_gift_card_on_the_cart_is_refused_rather_than_part_paid` | 228 | a `paymentSummary.giftCards` entry raises `CartContractError` | **Inverted.** A gift card with `requiresPaymentAfterGiftCard: True` and a reconciling `payNow` must now pass; a gift card that fails any §4.2 identity must still raise. |
| `test_a_gift_card_that_covers_the_whole_total_is_still_refused` | 242 | sets `payNow` and `totalAfterGiftCards` to `"0"` and does **not** set `requiresPaymentAfterGiftCard` | **Re-fixtured, but it already passes.** §4.4 makes absence mean `False`, so the existing fixture still refuses — which is why absence-is-False is the right rule and not merely a convenience. The fixture should additionally gain an explicit `requiresPaymentAfterGiftCard: False` variant, so the refusal is pinned on the documented field rather than on absence alone. Test 95 here covers the absent form. |

`test_memberships_and_subscription_charges_are_refused_on_the_same_grounds` (line 262) must
**keep passing unchanged**. It is the test that proves SEAM-G1 narrowed the gate rather than
opening it, and test 100 here asserts the same property from the gift-card side.

---

## 11. Repo-state dependencies, recorded because the seams attach to files not in HEAD

**Re-measured 2026-10-02** (closes MEDIUM-17; dated rather than pinned to a commit id per R4-N1 —
revisions 2 and 3 both pinned this to a commit id that was already stale at review time and drifted
again during the build, so **no commit id is reproduced here**. Every conclusion below survived the
drift; only the id was ever wrong. **Re-derive repo state; do not trust a commit id quoted in a
document.**):

```
$ git status --short
 M .kiro/steering/META-BETA-REQUEST-EMAIL.md
?? .agents/tasks/wix-coupons-giftcards-20261001/
?? AGENTS.md
?? amplify/functions/shared/lambda_utils/ecommerce/finalization.py
?? amplify/functions/shared/lambda_utils/ecommerce/initiation.py
?? scripts/retired_url_equity.py
```

- `finalization.py` and `initiation.py` are **untracked** in git — unchanged and still true.
- `finalization.accept_paid` has **zero callers** anywhere in `amplify/` — unchanged.
- `website_checkout.py` is tracked and clean, and **no handler in `amplify/functions/` calls
  `prepare_checkout`**, so SEAM-G14 attaches to a module with no live caller either.
- **Correction:** revision 2 said `cart_v2.py`, `customer_cart.py` and `checkout/handler.py` were
  *"modified in the working tree by concurrent sessions"*. All three are **clean**. The claim was
  false, and it was also the wrong test — **ownership is about an owner, not about a dirty
  working tree.** A clean file is not an unowned file. Every seam above is a seam because the
  brief assigns the file to another session, which is the evidence that survives a commit.
- `verifiedProviderPaymentId`, which §3.2 reads as the Razorpay leg's evidence, exists only in that
  untracked `finalization.py` (written by `record_paid`), and a parallel design
  (`.agents/tasks/payment-integrity-closure-2026-10-01/design.md`) is deciding whether that
  attribute keeps its name. `verifiedCapturedPaise` (SEAM-G13) would be added to the same
  `UpdateExpression`, so it inherits the same uncertainty and the same fallback.

**Fallbacks, so this design does not depend on names it does not own:**

| If | Then |
|---|---|
| `accept_paid` is renamed or replaced | SEAM-G5 and SEAM-G10 move to whichever function performs the internal-order write. `gift_card_settlement.redeem` is idempotent on `(codeHash, paymentAttemptId)`, so it is safe at any point that runs after capture is verified, and `paymentAttemptId` is the `Key` of every attempt write already. Nothing in the module changes. |
| `verifiedProviderPaymentId` is renamed | `is_fully_settled` reads it through the module-level constant `RAZORPAY_EVIDENCE_ATTR`, so the rename is one line here. The *property* asserted — that the Razorpay leg carries its own verified provider evidence — is what tests 65–68 pin, not the attribute name. |
| `verifiedCapturedPaise` is renamed, or SEAM-G13 is satisfied some other way | `is_fully_settled` reads it through `RAZORPAY_VERIFIED_PAISE_ATTR`, so the rename is one line. The property tests 83/83a pin is that the closure compares a **provider-verified** amount; any attribute carrying that fact satisfies it. If the payment-integrity workstream puts the verified amount somewhere other than the attempt row, SEAM-G13 becomes a read from wherever that is, and only the accessor changes. |
| `record_paid` cannot take an added parameter | SEAM-G13 falls back to a second conditional `UpdateItem` from the same caller, guarded on `status = PAYMENT_PAID` the way `_stage` already is. Weaker — it admits a row with the provider id and no amount — which is precisely why `is_fully_settled` returns `False` on the absent case rather than raising. |
| `razorpayChargedPaise` is not the chosen name for the gateway figure | Nothing in the settlement decision reads it (§6.5), so only the §6.5 reconciliation metric is affected. This is strictly less load-bearing than in revision 2, where it was in the closure. |

Neither fallback is speculative tidiness: both attributes are being decided in another session this
week, and a design that hard-codes a name it does not own becomes wrong without anyone editing it.

---

## 12. Owner actions still required

### 12.1 Register the SPI with Wix — the blocking one

Not done in this change, and it cannot be: it requires the Wix Studio workspace. Steps transcribed
from the introduction article's REST tab and the self-managed service-plugin REST guide:
https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/payments/gift-cards/gift-cards-service-plugin/introduction
https://dev.wix.com/docs/build-apps/develop-your-app/frameworks/self-hosting/supported-extensions/backend-extensions/add-self-hosted-service-plugin-extensions-with-rest

1. Select an app from the **Custom Apps** page in the Wix Studio workspace (or create one).
2. Go to **Extensions**, click **+ Create Extension**, find **Gift Cards Provider**, click
   **+ Create**.
3. In the JSON editor set `deploymentUri` to
   `https://zllr9lrg7j.execute-api.us-east-1.amazonaws.com/prod/wix-giftcards/` — the base URI
   only; Wix appends `v1/balance`, `v1/redeem`, `v1/void`. Optionally set `componentName`.
   **Save.** (Decide here whether to accept the execute-api host or stand up a custom domain first
   — §7.1 states the trade.)
4. From the app's dashboard, click **Webhooks → Get Public Key** and record the **public key** used
   to sign service-plugin JWTs. From the app's OAuth page record the **app ID**. Record the
   **instance ID**, which arrives as a JWT on the install callback — the introduction's example
   shows the callback body decoding to `{"instanceId": "044667f4-..."}`.
   **While you have a real token, record TWO things from it (item 12.1.4):**
   - **its header's `alg`**, so §5.1's three-member allowlist can be narrowed to one; and
   - **the request's `Content-Type`** (R4-M4). Revision 3 refused every request whose declared type
     was outside `{application/jwt, text/plain, plain/text}` — an allowlist assembled from one example
     of a *different* endpoint (the install callback), with nothing in the service-plugin REST guide
     mentioning the header at all. If Wix sends `application/json` that verifier answers nothing, so
     the check is **dropped** and the question moved here, to be answered from a real token rather
     than from a guess. Recording it costs one glance and would let a future revision add the check
     on evidence; **not** recording it is fine, because the three-segment-plus-signature check is
     what actually authenticates.
5. Store the public key, the app id, the instance id and a freshly generated code pepper in
   Secrets Manager as `wecare/wix/giftcard-spi` (`public_key`, `app_id`, `instance_id`,
   `code_pepper`). Values must be entered by a mechanism that never puts them on a command line —
   `secret-handling.md` is the rule and the 2026-09-19 incident is why.
6. Confirm the site has the app installed. The eCommerce Gift Card API introduction notes there is
   currently no way to block installation on sites without the third-party app installed, so
   installation must be verified rather than assumed.
7. **Ask Wix for the SPI error-response body shape.** §1.1.1 establishes by measurement that the
   OpenAPI `responses` object for all three methods declares **only `200`** — no error schema is
   published anywhere, on the method pages or in either guide — while the service-plugin guidance
   insists the implementation must match the specification exactly. We honour the documented HTTP
   status exactly and return a minimal body of `{"name": ..., "applicationCode": ...}`, which is
   `spiErrorData`'s own two fields. This is a Developer Preview question and the right person to
   answer it is Wix. Until answered it is the one part of this contract taken on a reasoned guess,
   and §1.1.1 says so rather than implying the body is specified.

Until step 3, `Add Gift Card` cannot value a card and no gift card can affect any total. Until
step 5, the SPI endpoint refuses every request — which is the correct fail-closed posture for an
unconfigured verifier.

### 12.2 Decisions only the owner can take

1. **Gift-card expiry policy.** Under Indian law an expiry on a prepaid voucher is a liability
   question. `expiresAtMs` is optional and the default is no expiry, which is the conservative
   choice; a non-null default is an owner decision.
2. **Whether a gift card may cover 100% of the payable** (§4.4). Currently refused, because such
   an order has no Razorpay readback and therefore no authoritative verification. Lifting it needs
   a decision about what verifies a wholly self-settled order.
3. **The Razorpay minimum-leg behaviour** (§4.1). This design **refuses** a split that would leave
   1–99 paise on the Razorpay leg. The alternative — round the redeem *down* so the remainder
   clears 100 paise — changes what the customer asked for by up to 99 paise without telling them,
   which is why it is a decision rather than a default. `RAZORPAY_MIN_LEG_PAISE = 100` is cited to
   Razorpay's own Orders Create reference and should be re-confirmed before go-live.
4. **Whether a gift card may fund the convenience fee. The design says NO** — corrected in
   revision 3 (HIGH-4). Revision 2 said it let the card fund the fee, and that was wrong in two
   ways: the reconciliation identity would have refused it, and the two statements contradicted
   each other. The gift card funds the **supply only**; the fee and its GST are always on the
   Razorpay leg, and `redeemCap` is capped against the **Wix collection total** rather than the
   payable (§4.1). The owner decision that remains is whether to accept the customer-visible
   consequence: someone holding a card worth more than the cart cannot spend the surplus on the
   fee and will see a small Razorpay charge. Reversing it means adopting option (b) — a `min(...)`
   in identity 1, a second identity bounding the fee-funded remainder, and a two-component tender
   record on the Wix order — which is a materially weaker reconciliation and is why it was not
   chosen.
5. **PIN policy.** The schema supports `pin` on balance and redeem. Supported and optional here; a
   mandatory PIN is an owner decision.
6. **GST treatment confirmation with the accountant.** §2 treats a voucher as consideration, so
   the taxable supply stays at full value. This is the standard treatment and is implemented, but
   it is the assumption the whole fee basis rests on, so it is named rather than buried.
7. **Enable `WIX_CART_V2_ENABLED`.** Nothing here reaches production without it: the entire
   gift-card split lives on the Cart V2 branch of `checkout/handler.py`. This design does not
   change the flag.
8. **Confirm which function finalizes** — `wecare-checkout` or `wecare-razorpay-webhook` — so
   SEAM-G9 grants the `GiftCardsTable` statement to the right role, and SEAM-G13 lands in the
   right place. `accept_paid` has zero callers, so this cannot be answered from the tree.
9. **Confirm which function hosts `website_checkout.prepare_checkout`** (§8.4). The module is
   handler-free and nothing in `amplify/functions/` calls it, so SEAM-G14's owning function cannot
   be read off the tree either. It may well have the same answer as item 8. This matters for IAM:
   whichever function it is needs the `GiftCardsTable` grant of SEAM-G9, because that is where the
   website path's hold is taken.
10. **Decide whether the gift card funds the convenience fee** — item 4 above, now a `no` with a
    named cost rather than an unexamined `yes`.
11. **⚠️ POINTWISE CONFIRMATION — create the customer-managed KMS key `alias/wecare-gift-cards`**
    (§6, DECISION 6). `maintenance-reporting.md` lists KMS create/delete among the operations
    requiring **per-item** approval, so this is not covered by the standing grant and is not bundled
    with the rest of the deploy. What is being approved: a new CMK in `us-east-1`, an alias pointing
    at it, a standing monthly key charge, and both gift-card roles gaining `kms:Decrypt` +
    `kms:GenerateDataKey` on it **conditioned on `kms:ViaService = dynamodb.us-east-1.amazonaws.com`**.
    It is behind `--apply` and nothing in this work has run it.
    **Why it is not optional and not deferrable:** a DynamoDB table cannot be moved from the
    AWS-owned default key to a CMK after creation without a restore, and this table is the **only**
    place a customer's gift-card balance of record exists. `provision_gift_cards_table.py` therefore
    **refuses to create the table before the alias resolves**. No other provisioner in this repo
    creates a CMK, so there is no precedent to inherit — which is why it is raised as its own item.

### 12.3 Deploy

**Depends on the coupon document's `deploy_all_lambdas.py` registry edit (§10.2).** ✅ **That edit has
LANDED** — all three names resolve under `deploy_all_lambdas.py --list` and each carries a non-empty
`provisioned_by`, so the fourth command is no longer a no-op.

> **NOTHING BELOW HAS BEEN RUN.** Every provisioner defaults to a dry run and requires `--apply`. No
> KMS key, no table, no role, no alarm, no route and no function exists. Step 1 additionally needs the
> **pointwise owner confirmation** for creating the customer-managed KMS key (§6, DECISION 6, and
> §12.2 item 11).

```
# 1. storage
python scripts/provision_gift_cards_table.py      --apply   # table + status-index, PITR on, TTL off

# 2. the two least-privilege roles (§10.1), the cryptography layer (§5.1.1) and the alarms (§6.5)
python scripts/provision_gift_cards_roles.py      --apply --alarms
#      creates wecare-gift-cards-role and wecare-wix-giftcard-spi-role
#      attaches arn:aws:lambda:us-east-1:775261844268:layer:cryptography-python312:1
#               to wecare-wix-giftcard-spi
#      creates wecare-gift-card-wix-spi-redemption and wecare-gift-card-charge-mismatch

# 3. EIGHT routes: the three SPI routes plus our own FIVE (R4-M5 removed hold and release)
#    RENAMED from provision_gift_card_spi_routes.py per R4-N3: one script creates all eight
#    across both integrations, and only three of them are SPI.
python scripts/provision_gift_card_routes.py      --apply

# 4. code
python scripts/deploy_all_lambdas.py wecare-gift-cards wecare-wix-giftcard-spi

# 5. the live alias, then publish-and-move
python scripts/provision_live_alias.py            --apply
python scripts/snapstart_publish.py wecare-gift-cards wecare-wix-giftcard-spi
```

**The layer must be attached before step 4, not after.** `deploy_all_lambdas.py` validates every
top-level import against the package plus the function's **live** layer list and refuses an import
it cannot resolve (`"imports '<root>', not in package or layers"`, line 570). The SPI handler
imports `cryptography`, so a step-4 run against a function with no layer attached fails the gate
rather than deploying something broken — which is the gate working, but only if the ordering here
is followed.

**Neither function is live until a version is published and the `live` alias moves**, per
`lambda-snapstart-deploy.md`. `snapstart_publish.py` discovers its targets **by looking for the
alias**, so the alias must exist first or the publisher simply will not see the function.
**`scripts/provision_live_alias.py` is the script that creates it** (closes NIT-22) — the same
file `lambda-snapstart-deploy.md` records as the reason the alias count drifts on its own, since
provisioning an alias immediately moves a function onto the publish-and-move path.
`deploy_all_lambdas.py` calls `snapstart_publish.py` itself at the end, so step 5's second command
is only needed for a hand deploy.

The SPI route must be reachable at `deploymentUri` **before** step 12.1.3, or Wix's save-time
validation has nothing to reach. So the full order is: this section, then §12.1.

No flag is enabled by this change. `WIX_CART_V2_ENABLED` / `CHECKOUT_INITIATION_ENABLED` and every
live-send and initiation flag stay exactly as they are.

---

## 13. Responses to the design reviews

> **EVERY FINDING ID IS PREFIXED BY REVIEW ROUND FROM HERE ON (resolves R4-N6).** Before this change
> `HIGH-1`..`HIGH-6`, `MEDIUM-10`, `MEDIUM-11`, `MEDIUM-13` and `MEDIUM-17` each denoted one thing in
> one table and a **different** thing in the next — **inside the same section of the same file**. A
> reader following a cross-reference could land on the wrong finding and conclude the opposite of what
> was decided. The prefix names the document revision the round produced:
>
> | Prefix | Review round | Produced | Table |
> |---|---|---|---|
> | `R4-` | reviewed 2026-10-02 · 6 HIGH / 8 MEDIUM / 6 NIT | **revision 4, this document** | §13.0 |
> | `R3-` | reviewed 2026-10-01 · 6 HIGH / 12 MEDIUM / 4 NIT | revision 3 | §13.1 |
> | `R2-` | the first round | revision 2 | §13.2 |
>
> The original unprefixed spelling is kept in brackets, so an old cross-reference still resolves.

### 13.0 The revision-3 review (`R4-`) — the round this revision answers

`design-review.json`, verdict `CHANGES_REQUESTED`, **6 HIGH / 8 MEDIUM / 6 NIT, reviewed 2026-10-02**.
Findings whose subject is this document are resolved **in** it; the coupon-only ones are marked and
answered in `coupons-20261001.md` §12.0. **Every resolution is APPLIED here, not merely recorded.**

| id | Finding | Resolution, and where it is applied |
|---|---|---|
| **R4-H1** (HIGH-1) | Decision 1 rejects `appliedDiscounts`, but `Place Order` is never called so nothing transports the coupon onto the order. | Coupon document. **Accepted** — "(a) for the arithmetic, (b) for transport". SEAM-G6 restates the same single invariant, so it inherits the widening: the order payload carries **both** writable terms. | `coupons-20261001.md` §2; §10.4 SEAM-G6 |
| **R4-H2** (HIGH-2) | `Create Order`'s `priceSummary` is documented `readOnly`, so identities asserted on the **sent** payload assert a discarded field. **Also hits SEAM-G6**, which restates the invariant. | **Accepted.** SEAM-G6's invariant is read on the Create Order **RESPONSE**, not on the payload we send; only `additionalFees[]` and `appliedDiscounts[]` are asserted outbound. The coupon document's §2.3 carries the split identity block and both documents point at the one copy. | §10.4 SEAM-G6; `coupons-20261001.md` §2.3 |
| **R4-H3** (HIGH-3) | `/v1/redeem` "refuses whenever any `GCHOLD#<codeHash>#*` or `GCORDER#<codeHash>#*` row exists", hold-expiry handling, and the coupon `HELD_BY_ANOTHER_CART` verdict all need a **key-prefix** lookup. The table is one partition attribute with `Scan` denied and a `Query` needs partition-key **equality**, so none is implementable. The `order_keys` precedent does not transfer (zero query calls there). This also removes §3.4's safety argument for keying the claim on `paymentAttemptId`, which rested on "the hold refuses it". | **Accepted; DECISION 5.** `GIFTCARD#<codeHash>` gains `activeHoldAttemptId` / `activeHoldPaise` / `activeHoldExpiresAtMs` (plus `activeClaimAttemptId`, because a claim is not a hold and never lapses); `hold()` is **one** conditional `UpdateItem` with the three-branch condition; `GCHOLD#` rows survive as **audit only**. §7.4's refusal becomes a **single exact-key `GetItem`**. A sort key and a GSI are both rejected with reasons (the GSI decisively: eventually consistent, so it cannot gate money). `GCID#<giftCardId>` is added because §7.2's GET-by-our-id has the same problem. An access-pattern enumeration test pins exact-key-or-`status-index`, zero `scan`. | §6.3, §6.4, §7.4, §3.4 |
| **R4-H4** (HIGH-4) | `redeemCap` is defined **twice and differently** — §4.1 caps against the Wix collection total, §7.5 (the table a coder implements validation from) says `min(balance, payable - 100)`. `payable` exceeds the Wix total by the fee and GST, so §7.5 admits a redemption Wix cannot apply, §4.2 identity 1 then fails, and the checkout refuses **after the request reached Wix** — reintroducing the exact defect §4.1 removed. | **Accepted; defined exactly ONCE** as `gift_card_store.redeem_cap(*, balance_paise, wix_collection_paise) -> min(balance_paise, wix_collection_paise - RAZORPAY_MIN_LEG_PAISE)`. §7.5's parenthetical is **replaced by a reference** to that function, and a test asserts the validator and the split both **call** it rather than both restating the expression — because two correct copies of one expression is how this happened. | §4.1, §7.5 |
| **R4-H5** (HIGH-5) | The SEAM-G9 edit breaks the provisioner's own `--verify` gate: the verdict aggregates per action across resources, so `DeleteItem` allowed on the new tables and implicitly denied on the old ones fails a **correctly** provisioned role. Test 107a asserts a per-resource verdict the script never retains. | **Accepted; THREE parts, and they LANDED together.** Part (c) adds `_EXPECTED_DENY` and re-keys the verdict on `(EvalActionName, EvalResourceName)`. Both table ARNs went in on one visit, so the ordering hazard SEAM-G9 warned about never arose. `ConditionCheckItem` is aggregated and judged once (its question was never per-table). `provision_checkout.py` leaves §10.3's read-only list. | §10.4 SEAM-G9; `coupons-20261001.md` §5.2.1 |
| **R4-H6** (HIGH-6) | §8.4 assigns the `GC_VOIDED` write to the SPI and §10.1 grants it `UpdateItem` on `PaymentAttemptsTable` for it, **but nothing on the void path can produce an `attempt_id`**: `VoidRequest` carries only `transactionId`, `GCTXNID#` mapped to `codeHash` alone, and `GCTXN#` still carried revision 2's `referenceId` with no `paymentAttemptId`. The prefix-scan route is barred by R4-H3. So the grant is for an unreachable call and the stage is never written. | **Accepted; DECISION 9.** `GCTXN#<codeHash>#<transactionId>` **gains `paymentAttemptId`**; `GCTXNID#<transactionId>` points to **`{codeHash, paymentAttemptId}`**; `referenceId` on `GCTXN#` is demoted to **correlation only, never a key**, completing the §3.4 re-key. A void carrying only a transaction id resolves **both** in two exact-key `GetItem`s, and a test drives exactly that case through `advance()`. | §6.3, §6.5, §7.3, §8.4 |
| **R4-M1** (MEDIUM-1) | SEAM-G13 adds `captured_paise` to `record_paid`, but its only caller is `accept_paid(..., outcome)` and **no captured-amount field on `outcome` is named anywhere**. The whole HIGH-3 resolution has no specified producer at the point it enters the row. | **Accepted; stated in SEAM-G13.** `outcome` gains `verifiedCapturedPaise`, written by the caller from the **same `razorpay_verify` readback that produced `outcome['providerPaymentId']`** (`website_checkout.py:430`'s `amount_paise`, or the webhook's `provider_paise`), and **`record_paid` refuses a call carrying a provider id without an amount** — writing the id alone would leave a paid order reading not-settled forever. The rename fallback is in §11's table. | §3.2, §10.4 SEAM-G13, §11 |
| **R4-M2** (MEDIUM-2) | `amount_paise` appears **18 times** in `website_checkout.py`; the split table names **five**. Three unlisted consumers are load-bearing: `_browser_options` (→ `options['amountPaise']`), `_recover_ambiguous_create`, and `_ready_from_binding`. | **Accepted; three rows added, including the one that must NOT change.** `_browser_options` carries `payNowPaise` (it is the figure the browser is shown); `_recover_ambiguous_create` carries `payNowPaise` (it re-binds, and a payable re-binding would break the one recovery path); `_ready_from_binding` **reads the binding, so NEEDS NO CHANGE** — stated so its absence is deliberate rather than an oversight. The two failure modes are named: reassigning the local satisfies five rows and silently changes three; adding a second variable leaves thirteen occurrences to decide unaided. Test 112 gains `options['amountPaise'] == payNowPaise`. | §8.1, §10.4 SEAM-G14, test 112 |
| **R4-M3** (MEDIUM-3) | §8 says "THREE attempt producers … measured". There are **four**: `checkout/handler.py:519`, `website_checkout.py:279`, `initiation.py:63` and `blog_contribution.py:355`, whose own docstring calls it a sibling of `website_checkout`. Revision 3's largest finding was a missed producer; an enumeration short by one is the same defect smaller. | **Accepted; corrected to FOUR**, derived from the `payment_attempt.build(` call sites rather than from the narrative, with each line number given. New **§8.5** declares `blog_contribution.prepare_contribution` out of scope in the shape of §8.3 — decisively because **a contribution flow has no Wix cart, so no `wixCollectionPaise` exists to cap a redemption against**, and R4-H4 exists precisely to stop that cap being taken against anything else. **Test 113b** asserts it writes no gift-card attribute. | §8, §8.5, test 113b |
| **R4-M4** (MEDIUM-4) | The verifier 401s unless `Content-Type` is `application/jwt`, `text/plain` or `plain/text`. The only `plain/text` occurrence on the fetched page is the **app-install** callback, not a gift-card call, and the REST guide documents the envelope and five claim checks and says **nothing** about `Content-Type`. If Wix sends `application/json` the verifier refuses every live call — fail-closed in form, **feature-dead** in substance, and §5's "verbatim" claim would be false. | **Accepted; the rejection is DROPPED.** The body is parsed as a JWT regardless of declared type; `isBase64Encoded` is still honoured **first**; the **three-segment check is the real discriminator**; `Authorization` is still ignored (test 4 kept). The header question moves to **owner item 12.1.4** beside the `alg` ("while you have a real token, record the request's `Content-Type`"), and the citation is corrected to say the `plain/text` example is the **install callback**. Test 2 becomes `test_a_body_that_is_not_three_segments_is_refused_whatever_the_content_type`, parametrised over five header values including a missing one. | §5, §5.1, §7.4, §7.5, §12.1.4 |
| **R4-M5** (MEDIUM-5) | §7.2 exposes `POST /gift-cards/hold` while §8.4 attributes every `GC_HELD` write to the checkout function and §10.1 gives `wecare-gift-cards-role` no `UpdateItem` on `PaymentAttemptsTable`. Either the route takes a hold without the stage — leaving `giftCardRequiredPaise` unwritten so `is_fully_settled` reads `required == 0` and settles a gift-card order on the Razorpay leg alone — or IAM denies it. Underneath: a customer session has no `paymentAttemptId`, and `GCHOLD#` is keyed on it. | **Accepted; hold and release REMOVED. §7.2 is FIVE routes.** The hold is taken **only** by the checkout producer, inside the request that mints the `paymentAttemptId` (SEAM-G4 / SEAM-G14). The customer surface is `POST /gift-cards/balance` only, which reserves nothing. Test 45's route enumeration pins five. | §7.2, §8.4, §10.1, test 45 |
| **R4-M6** (MEDIUM-6) | `commit_redemption` deletes a hold keyed on `cartId` without taking `cart_id`. | Coupon document. **Accepted** — `cart_id` added to the signature; the finalizer already has it. | `coupons-20261001.md` §5.2 |
| **R4-M7** (MEDIUM-7) | Test 80 is `..._after_the_reference_is_minted_...`, which is **unsatisfiable** on the website path because §3.4 establishes `referenceId` **is** the gateway order id there. Tests 49, 50 and 53 carry the same stale vocabulary for a claim now keyed on `paymentAttemptId`. | **Accepted; all four renamed** to the property true on **both** producers: 80 → `test_the_hold_is_taken_after_the_attempt_id_is_minted_and_before_the_gateway`; 49 / 50 → `..._for_the_same_payment_attempt_...`; 53 → `test_two_different_payment_attempts_each_deduct_once`. The note that 80's old form was unsatisfiable, not merely stale, is kept beside it. | §9.1 tests 49, 50, 53, 80 |
| **R4-M8** (MEDIUM-8) | `AdditionalFee`'s schema **leads** with `price` ("Additional fee's price."), `PriceSummary.totalAdditionalFees` is what Wix sums into its read-only total, and nothing documents which field that sum derives from. Omitting `price` is the likeliest way for the identity to come back short **by exactly the fee**. | **Accepted; all three price fields sent** on SEAM-G6's payload too: `price` and `priceAfterTax` = fee + GST, `priceBeforeTax` = fee. Test 48 in the coupon suite asserts `totalAdditionalFees` on the response. `name` maxLength 50, `code` maxLength 100; both fit. | §10.4 SEAM-G6; `coupons-20261001.md` §2.3 |
| **R4-N1** (NIT-1) | Both documents pinned their repo-state measurement to a commit id that was not the tree's actual head. Every conclusion survived; only the id was wrong. | **Accepted; the id is replaced by the DATE, and no commit id is reproduced anywhere in this document.** §11 says **re-measured 2026-10-02** and carries the instruction to re-derive repo state rather than trust a quoted id — a commit id in a document drifts by construction, and this one drifted twice. | §11, §13 headers |
| **R4-N2** (NIT-2) | Six drifted line citations, and the webhook comparison's **flow** is misattributed. | **Accepted; all six corrected and annotated.** In this document: `wix_writeback` resolve/raise **256/259**; `website_checkout`'s `attempt_id` mint **199**; razorpay-webhook's `provider_paise != intent_paise` **952** — **and it sits on the PARTNER WALLET TOP-UP path** (`'stage': 'wallet_topup'`), not a checkout path, which matters because §3.2 offered it as one of only **two** amount verifications in the tree. The honest count is therefore **one** on a checkout path, which **strengthens** the case for SEAM-G13. `_SIMULATED_ACTIONS` **662** (was 661) — and since moved to 683 by the landed edit. | §3.2, §8.1, §10.4, §11 |
| **R4-N3** (NIT-3) | The `wecare-gift-cards` Spec's `provisioned_by` omits its route script while §12.3 says one creates the routes; and `provision_gift_card_spi_routes.py` creating mostly non-SPI routes misleads. | **Accepted on both counts.** The registry entry gains the route script; the script is **renamed** to `provision_gift_card_routes.py`; and §12.3 step 3 now says **eight** routes (three SPI plus our five) under the new name. | §12.3; `coupons-20261001.md` §8 |
| **R4-N4** (NIT-4) | The quoted "a single coupon and a single gift card" is asymmetric with the embedded schema: `coupons` is `maxItems 1` but **`giftCards` is `maxItems 5`**. | **Accepted; recorded beside the quotation** in the coupon document, with the discrepancy named so a later reader does not conclude the page was misread. **Enforcing one remains correct** on our own grounds: §4.2 closes against a **single** `giftCardRedeemedPaise` term and §4.1 caps **one** card against one collection total; five would need a per-card ladder and an ordering rule for which absorbs the remainder — undesigned, untested, and spending real liability. | `coupons-20261001.md` §1.2; §4.1, §4.2 |
| **R4-N5** (NIT-5) | The per-customer guard references an optional `limitPerCustomer`, so the expression is undefined with no limit. | Coupon document. **Accepted** — no condition is applied and the row is **still incremented for audit**. | `coupons-20261001.md` §4.3 |
| **R4-N6** (NIT-6) | Ten ids each denote two different things inside one section. | **Accepted; every id is revision-prefixed** (`R2-`, `R3-`, `R4-`), with the original spelling in brackets and the scheme stated above. | §13, §13.0, §13.1, §13.2 |

### 13.1 The revision-2 review (`R3-`) — answered in revision 3, retained

`design-review.json` as it then stood, verdict `CHANGES_REQUESTED`, 6 HIGH / 12 MEDIUM / 4 NIT,
**reviewed 2026-10-01**. Findings addressed to this document, in order. Findings addressed only to
the coupon document are answered there. Every repository claim was re-measured; the four
`dev.wix.com` pages behind `R3-M10` were re-fetched.

| id | Response | Where |
|---|---|---|
| **R3-H1** (HIGH-1) | **Accepted; the omission was the largest hole in revision 2** — **and the enumeration it produced was itself short by one; see R4-M3, which makes it FOUR.** New §8 opens with the measurement: there are three attempt producers, and the one revision 2 named is the in-WhatsApp path while both documents declare the **website** path the active architecture. `website_checkout.py` is now a named seam (**SEAM-G14**) with its six load-bearing lines (193, 203, 231, 265, 281, and the 407/434/436 callback comparison), and §8.1 gives the split as a five-row table: `payNowPaise` to `create_order`, to `bind_gateway_order` and to the request-key `extra`; the **full payable** to `payment_attempt.build`; `payNowPaise` to `razorpayChargedPaise`. Both obvious wrong resolutions are named and shown to be unrepresentable. `initiation.reserve` is declared **out of scope** with three reasons and a test (113) pinning the omission. `intent_fingerprint` is confirmed unaffected. Test 112 is the assertion the review asked for. | §8, §8.1, §8.3, §10 SEAM-G14, tests 112–113 |
| **R3-H2** (HIGH-2) | **Accepted, and resolved by removing the read rather than adding a writer.** `razorpayChargedPaise` is no longer read by `is_fully_settled` at all, so an attribute with no permitted writer is no longer in the settlement decision. It survives as a checkout-time audit record with a named writer (the checkout producer, on the attempt dict beside `attempt["checkoutMode"]`) and a named purpose (reconciliation against the verified figure, with its own metric and alarm). §6.5's table is now **seven** attributes with a `Read by` column, and `advance()`'s closed set is restated with the two exclusions explained. The absent case is specified: `return False`, never an exception — test 83a. | §3.2, §6.5, §7.3, §8.1, tests 83a, 83d |
| **R3-H3** (HIGH-3) | **Accepted; this was the sharpest finding and it reshaped DECISION 3.** The closure now reads **`verifiedCapturedPaise`** — the amount Razorpay's own readback reported — instead of `razorpayChargedPaise`, the figure we wrote at checkout. **SEAM-G13** adds it to `finalization.record_paid`'s existing conditional `UpdateExpression`, beside `verifiedProviderPaymentId`, because the two are one fact recorded at one instant. The two legs now carry symmetric evidence: provider id + verified amount against our transaction id + redeemed amount. §3.2 shows the only two amount verifications that exist in the tree (`website_checkout.py:434`, `razorpay-webhook/handler.py:`**`952`** — **corrected from 947, and on the partner wallet top-up path rather than a checkout path, per R4-N2**) and that neither value previously reached the attempt row. Added to §11's fallback table with two fallbacks. Test 83 asserts against the verified figure; 83c is the short-capture case revision 2 could not detect. | §3.2, §10 SEAM-G13, §11, tests 83, 83c |
| **R3-H4** (HIGH-4) | **Accepted; the two statements contradicted each other and §12.2.4 asserted the wrong one.** Chosen **option (a): the gift card funds the supply only.** `redeemCap = min(balancePaise, wixCollectionPaise - RAZORPAY_MIN_LEG_PAISE)` — capped against the **Wix** total, which is the only total Wix can redeem against — so identity 1 becomes a true exact equality rather than needing a `min(...)`. Three reasons given, in weight order, with option (b)'s weaker reconciliation as the deciding one. §12.2 item 4 flips to **no**, with the customer-visible cost stated. A new identity 6 asserts the fee is always on the Razorpay leg, so the decision is a tested property rather than a convention. Full payable cover is now **unrepresentable by construction**; §4.4's checks are retained as the backstop. Boundary tests 96, 97, 97a (`wixCollectionPaise`), 97b (`+1`) and 97c. | §4.1, §4.2, §4.4, §12.2.4, tests 96–97c |
| **R3-H5** (HIGH-5) | **Accepted; revision 2 specified no IAM and then asserted a spec that did not exist.** New **§10.1** mirrors the coupon document's §6 for **both** functions: `wecare-gift-cards-role` and `wecare-wix-giftcard-spi-role`, each with its trust policy and `aws:SourceAccount` condition, action list, table and index ARNs, the `wecare/wix/giftcard-spi-*` secret ARN pattern (with the reason for the `-*`), and an explicit "no `Scan`, no `dynamodb:*`, no wildcard". A difference table explains each asymmetry: `DeleteItem` on one role only, `UpdateItem` on PaymentAttemptsTable on the other. It also states plainly what IAM **cannot** enforce — both roles need `PutItem` on the same table, so "the SPI cannot issue a card" is structural and asserted by AST (test 104), not permissive. Neither role is `wecare-digital-lambda-role` (test 106). | §10.1, tests 101–107 |
| **R3-H6** (HIGH-6) | **Accepted; the stated approach could not have run and would have been rejected before deploying.** New **§5.1.1** names `cryptography` via the live, measured layer `arn:aws:lambda:us-east-1:775261844268:layer:cryptography-python312:1` — read off `wecare-whatsapp-business-api`, which uses it for its own RSA work at handler lines 3372–3375. PyJWT`[crypto]` is rejected with a reason (it depends on `cryptography` anyway, so it buys an API for a second pinned dependency and a new layer). The revision-2 sentence is corrected rather than deleted: the stdlib **does** do the base64/JSON parsing, and **cannot** do the signature verification, and the split is now explicit. Attachment is a named provisioner step placed **before** step 4 of §12.3, with the reason: `deploy_all_lambdas.py` resolves layers from the live config and refuses an unresolvable import (line 570). The ARN is **version-pinned** so a republished layer cannot alter signature verification silently. Tests 110 and 111. | §5.1.1, §12.3, tests 110–111 |
| **R3-M10** (MEDIUM-10) | **Accepted, and re-fetching produced a harder answer than the finding expected.** `AlreadyVoided`'s `applicationCode` is **`ALREADY_VOIDED`**, transcribed verbatim from the Void page's `errors[]` along with `name: AlreadyVoidedWixError` and `errorSchemaName` — so all nine rows are parametrisable and test 28 is writable. On the body envelope: **there is nothing to cite.** New §1.1.1 records the measurement — the OpenAPI `responses` object declares **only `200`** on all three methods, with no error schema and no `$ref` to one, and `applicationError` / a `details` envelope appear nowhere on the method pages or in either guide. So the error rows are annotations, not a response contract. We honour the documented status exactly and return a minimal `{"name", "applicationCode"}` body — `spiErrorData`'s own two fields — with every wrapper alternative rejected as an invention, and the question raised as owner item 12.1.7. Tests 28, 28a, 28b. | §1.1, §1.1.1, §12.1.7, tests 28–28b |
| **R3-M11** (MEDIUM-11) | **Accepted; the identities were always-false, not merely loosely typed.** Every §4.2 identity is restated in integer paise with `Money.from_wix(...).paise` on each Wix term, and the three intermediate values (`wixCollectionPaise`, `wixAppliedPaise`, `wixPayNowPaise`) are named once and reused so no comparison carries a bare subscript. Applying `Money.from_wix` is noted as also proving the field was a string, since it requires one. | §4.2 |
| **R3-M12** (MEDIUM-12) | **Accepted; the comparisons in §3.2 would have been silently always-true.** §3.1 now declares string stage **values** (`GC_REDEEMED = "GC_REDEEMED"`) and a separate `STAGE_RANK: Dict[str, int]`, mirroring `payment_status.py`'s string values plus `STATUS_RANK` (line 108) and `rank()` (line 203). `GC_UNKNOWN` is deliberately **absent** from `STAGE_RANK` so `stage_rank` returns 0 through the `.get` default — the same construction and the same reason as `payment_status.rank`. §3.2 compares values; the persisted `giftCardStageRank` holds the **rank** and never the name, so the two never appear in one expression. §7.3 publishes both plus the constants. | §3.1, §3.2, §7.3 |
| **R3-M13** (MEDIUM-13) | **Accepted, assigned to the coupon document.** All three `Spec(...)` entries live in `coupons-20261001.md` §8, quoted verbatim with `provisioned_by`, and asserted by its test 65 — **two of the three are this document's functions**, so §10.2 states the dependency explicitly and §12.3 opens by naming it: without that edit the deploy command is a no-op. One shared file, one session, per rule 3b. | §10.2, §12.3 |
| **R3-M15** (MEDIUM-15) | **Accepted; the seam stated the failure backwards and missed the guard.** The exposure is an **overstated** provider payment, not a short one: `accept_paid` passes `int(attempt['amountPaise'])`, which §8 mandates stay the full payable, so Wix would record the full payable against a transaction that captured only `payNowPaise`. Part (a): `record_external_payment` receives `verifiedCapturedPaise`. Part (b): the gift-card tender needs its own effect key, which is itself an edit — `KNOWN_EFFECTS` is a `frozenset` validated by `claim`, so `WIX_GIFT_CARD_TENDER` must be declared there, with the file's own `WIX_CART_COMPLETED` comment as the precedent. A third detail the review did not reach: `record_external_payment` hard-codes `paymentMethodName: "Razorpay via WhatsApp"`, so the tender gets a **sibling function** rather than a parameter, with a reason. Tests 114 and 115. | §10 SEAM-G7 detail, tests 114–115 |
| **R3-M16** (MEDIUM-16) | **Accepted; the justification was false and it was the sole justification.** §4.2 now prints the measurement: `checkout/handler.py` puts `quoteHash` into `extra`, which `allocate_payment_reference` stores on the **`PAYREF#` row in the commerce keys table**; the attempt's hash is `snapshotHash`, written only by `initiation.reserve` and read by `accept_paid`; `_create` writes no hash to the attempt. So revision 2's binding did not exist. The compounding the review named is closed by HIGH-3 rather than by adding a hash: with the provider's verified amount on the row, the readback **is** the binding, which is stronger than a hash over our own intent. | §4.2 |
| **R3-M17** (MEDIUM-17) | **Accepted; the claim was false and the test was the wrong test.** §11 re-prints `git status --short`, re-measured 2026-10-02 (the commit id revision 3 quoted here is dropped per R4-N1): `cart_v2.py`, `customer_cart.py` and `checkout/handler.py` are **clean**. The untracked/zero-caller facts about `finalization.py` and `initiation.py` are re-confirmed, and `website_checkout.py` is added as tracked, clean, and with no caller in `amplify/functions/`. The deeper point is stated: **ownership is about an owner, not a dirty working tree** — a clean file is not an unowned file — so every seam is re-grounded on the brief's assignment, which survives a commit. | §11, §8.2 |
| **R3-M18** (MEDIUM-18) | **Accepted, and superseded by R4-H5, which found a THIRD part.** SEAM-G9 gains the grant plus `_SIMULATED_ACTIONS` with `dynamodb:DeleteItem` and the simulated `tables` list with the new ARN — or the script whose job is verifying this role never measures the statement it wrote. Coordinated with the coupon document's SEAM-C3b, which changes the same two lists. (The line numbers revision 3 quoted here, 661 and 785, were already one off and have since moved outright — **the seam has LANDED**; §10.4 carries the current anchors. The "whichever lands second adds only its ARN" coordination never ran, because both ARNs went in on one visit.) Test 107a. | §10.4 SEAM-G9, test 107a |
| **R3-N19** (NIT-19) | **Accepted.** SEAM-G3's justification is restated as "**not surfaced on the payable projection**" rather than "returns neither id" — `calculate` returns `"cart": deepcopy(cart)` and `cart["coupons"]` carries `{id, code}`. The seam stands for the narrower reason. | §10 SEAM-G3 |
| **R3-N21** (NIT-21) | **Accepted.** §4.1's cross-reference is corrected from "tests 85 and 86" to **96 and 97**; test 85 is `test_nothing_here_writes_the_razorpay_machinery`. | §4.1 |
| **R3-N22** (NIT-22) | **Accepted.** §12.3 is now a full ordered command block naming **`scripts/provision_live_alias.py`**, with the reason the alias must exist before `snapstart_publish.py` (the publisher discovers targets by looking for it) and a note that `deploy_all_lambdas.py` invokes the publisher itself. The coupon document's §11 item 7 has the same block. | §12.3 |

### 13.2 The first review round (`R2-`) — answered in revision 2, retained

A different round from §13.1's. The original spelling is in brackets so an old cross-reference still
resolves, but the prefix is what disambiguates: `R2-H3` and `R3-H3` are **different findings** that
revision 3 spelled identically, inside this same section.


| id | Response | Where |
|---|---|---|
| **R2-H1** (HIGH-1, rev 1) | **Accepted; the defect was real and would have halted every checkout.** `is_fully_settled`'s `required == 0` branch is now `stage(attempt) in (GC_NOT_REQUIRED, GC_UNKNOWN)`, so absence means not-required and the common path needs **no write at all**. `GC_NOT_REQUIRED` stays at rank 10 for rows that carry it. A `GC_HELD`/`GC_REDEEMED` stage with `required == 0` is a contradiction and fails closed. Test 69 is the test that would have caught it. | §3.2, tests 69–71 |
| **R2-H2** (HIGH-2, rev 1) | **Superseded in part by revision 3's HIGH-2.** `advance()` stands as described, but the clause claiming a role spec existed was the thing rev-2 HIGH-5 caught: §10.1 now writes both roles out. `advance(attempts, *, attempt_id, stage, **evidence)` is added to the published surface: one conditional `UpdateItem` on `PaymentAttemptsTable` using `condition_expression()`, with a **closed** evidence key set. §6.5 tabulates which attribute is written by which stage; §8 names the executing function per stage; §10 (SEAM-G9) and the role spec grant `dynamodb:UpdateItem` on `table/stack-wecare-digital-PaymentAttemptsTable` to every function that calls it. Tests 77–79 and 102. | §6.5, §7.3, §8, §10, tests 77–79/102 |
| **R2-H3** (HIGH-3, rev 1) | **Stands, now with the spec it asserted.** Option (a): `wecare-checkout-role` — a **per-function** role, not the shared fleet role — gains `GetItem, PutItem, UpdateItem, DeleteItem` on the `GiftCardsTable` ARN additively, so the §10 "no wildcard on the shared role" objection does not apply. Option (b), a synchronous `lambda:InvokeFunction` from finalization, was rejected because it inserts a network call between a verified capture and a completed order. Added as SEAM-G9 with an owner and test 107; which role is the finalizer is owner item 12.2.8. | §7.3, §8, §10, §12.2, test 107 |
| **R2-H4** (HIGH-4, rev 1) | **Stands in substance, re-keyed again in revision 3 (§3.4): `referenceId` is the Razorpay gateway order id on the website path and is not stable across retries on either, so the key is now `paymentAttemptId`.** The namespace argument is unchanged and correct: §1.3 now says so explicitly: our `orderId` is a local UUIDv7 and `RedeemRequest.orderId` is a Wix GUID, so the two claim keys could never collide. The claim is re-keyed on `GCORDER#<codeHash>#<referenceId>`; a `GCWIXORDER#<wixOrderId> → referenceId` pointer is written at `WIX_ORDER_CREATED` (SEAM-G10); and `/v1/redeem` **refuses with `AlreadyRedeemed` (409)** whenever any `GCHOLD#`/`GCORDER#` exists for the card rather than deducting. Tests 37 and 38, the second being the Wix-GUID-against-already-redeemed case the review asked for by name. | §1.3, §3.4, §6.3, §7.4, tests 37–41 |
| **R2-M7** (MEDIUM-7) | **Accepted; the claim was wrong.** §8 is a new section naming `checkout/handler.py::_v2_snapshot` and the `amount_paise = snapshot.quote.total_payable_paise` assignment in `_create` as the insertion point, with four numbered steps and the subtlety that `attempt["amountPaise"]` must keep the **full payable**. The old SEAM-G8 is replaced rather than deleted, because unlike the coupon case there *is* work to do here. The file is added to the read-only list and to the seam table. Enabling the flag is owner item 12.2.7. | §8, §10, §12.2 |
| **R2-M8** (MEDIUM-8, rev 1) | **Superseded by revision 3's HIGH-3 and MEDIUM-16.** The choice of re-derivation over folding a `giftCard` component into the snapshot stands; the closure's terms and its `quoteHash` justification do not — the hash is on the PAYREF row, and the closure now reads `verifiedCapturedPaise`. Original response: Of the two options the review offered, re-derivation at finalization is chosen over folding a `giftCard` component into the snapshot, because `build_snapshot` lives in read-only `checkout_pricing.py`. `is_fully_settled` now re-derives `razorpayChargedPaise + giftCardRequiredPaise == int(attempt["amountPaise"])`, which is itself covered by `quoteHash`. Test 83 drives a tampered `redeemAmount` through both the pre-hold reconciliation and the post-hoc check. | §3.2, §4.2, test 83 |
| **R2-M9** (MEDIUM-9) | **Addressed.** SEAM-G12 is a new seam row with a per-test table: `test_the_adapter_has_no_gift_card_methods_at_all` (line 215) **deleted**, `test_a_gift_card_on_the_cart_is_refused_rather_than_part_paid` (228) **inverted**, `test_a_gift_card_that_covers_the_whole_total_is_still_refused` (242) **re-fixtured but already passing**, and `test_memberships_and_subscription_charges_are_refused_on_the_same_grounds` (262) **unchanged**. The file is noted as the cart_v2 workstream's. §4.4 states that an absent `requiresPaymentAfterGiftCard` is treated as `False` and refuses, which is why the existing fixture survives; test 95 pins it. | §4.4, §10, test 95 |
| **R2-M10** (MEDIUM-10) | **Addressed.** This document now edits **no** shared file. Both gate edits are assigned exclusively to `coupons-20261001.md` §8, which quotes the exact three-entry `RAW_SCAN_ONLY_FILES` list (including `ecommerce/wix-giftcard-spi/handler.py`, so the count is 3 and not ambiguous) and the two `UNDECLARED_ALLOWED` entries. | §9.1 closing note, §10 |
| **R2-M11** (MEDIUM-11) | **Addressed by the split**, owned by the coupon document. Both handlers join `RAW_SCAN_ONLY_FILES`, which parametrises only `test_no_decision_compares_a_payment_word_raw`; neither joins `CONSULTING_FILES`, so no unused `payment_status` import is forced. | §9.1 closing note |
| **R2-M12** (MEDIUM-12) | **Accepted; the claim named the wrong lists.** §6 now records that the physical name is right but the table still needs an `UNDECLARED_ALLOWED` entry because `amplify/data/resource.ts` declares no `GiftCard` model. The entry is quoted verbatim in the coupon document, which owns the edit; this document depends on its test 57 rather than duplicating it. Old test 84 is gone. | §6 |
| **R2-M13** (MEDIUM-13) | **Addressed with a citation.** `RAZORPAY_MIN_LEG_PAISE = 100`, sourced to Razorpay's Orders Create reference (*"Currency subunits, such as paise (in the case of INR), should always be greater than 100... that is 100"*, HTTP 400, `step: payment_initiation`). It enters `redeemCap`, the §7.5 validation table as `GIFT_CARD_LEAVES_UNCHARGEABLE_REMAINDER`, and owner item 12.2.3 as a refuse-vs-round-down decision. Test 98. | §4.1, §7.4, §7.5, §12.2, test 98 |
| **R2-M14** (MEDIUM-14) | **Accepted.** `initialValuePaise` and every credit to `balancePaise` are capped at `99_999_999_999` paise — `999999999.99`, the SPI maximum for `GetBalanceResponse.balance` and `RedeemResponse.remainingBalance` — with the reason stated: a balance we cannot report is a balance we cannot honour. `money.py`'s `9007199254740991` remains the outer type bound only. Boundary tests 51 and 52. | §6.4, §7.5, tests 51–52 |
| **R2-M16** (MEDIUM-16, rev 1) | **Stands; the terms were renamed in revision 3.** SEAM-G6 states the identical invariant to `coupons-20261001.md` §2.3, now with the verified figures `verifiedCapturedPaise + giftCardRedeemedPaise` on the right-hand side and `Money.from_wix` on the Wix term. One producer, one invariant. | §10 SEAM-G6 |
| **R2-M17** (MEDIUM-17, rev 1) | **Superseded by revision 3's HIGH-4**, which caps against the Wix collection total instead, because the payable includes a fee Wix cannot redeem against. Original response: `redeemCap = min(balancePaise, quote.total_payable_paise - RAZORPAY_MIN_LEG_PAISE)`, so the cap and §4.4's refusal no longer contradict each other, and §4.4's `requiresPaymentAfterGiftCard` check is retained explicitly as the fail-closed backstop. Boundary tests 96 and 97 at `redeemCap` and `redeemCap + 1`. | §4.1, §4.4, tests 96–97 |
| **R2-M18** (MEDIUM-18) | **Addressed, and a second error found while fixing it.** The signature is now `verify(raw_body, *, headers, now)`: **the raw body IS the JWT**, evidenced by the introduction's own `curl` with `Content-Type: plain/text` and a bare `eyJ...` payload; `headers` is never a token source; an `Authorization` header is ignored; `isBase64Encoded` is honoured before decoding. (**The `Content-Type` rejection this row introduced is DROPPED by R4-M4** — the allowlist came from one example of a different endpoint, and the three-segment check is the real discriminator.) Test 4 is the header-token/non-JWT-body rejection. Separately, revision 1 placed `request`/`metadata` at the **token root** and attributed them to a `RedeemEnvelope` component that does not exist in the fetched schema — they are under **`data`**, per the REST guide, with `metadata` typed `wix.common.spi.Context`. Test 5 pins it. | §5, §5.1, tests 4–6 |
| **R2-N19** (NIT-19) | **Addressed.** The `source: "WIX_SPI"` signal now names its log event (`gift_card_wix_spi_redemption`), its EMF metric (`WecareGiftCards / WixSpiRedemption`), its alarm (`wecare-gift-card-wix-spi-redemption`, `Sum >= 1` over 5 minutes, routed to the same SNS topic as the account's existing alarms) and its provisioner flag. Threshold is 1 because a single occurrence is actionable. Test 109. | §6.5, §12.3, test 109 |
| **R2-N21** (NIT-21) | **Addressed.** `deploymentUri` is the execute-api hostname of the single HTTP API `zllr9lrg7j`, stage `prod`, written out in full, with three reasons (no API Gateway custom domain exists in the account; the apex `/api/*` path is an Amplify browser rewrite, not a server-to-server front door; `/prod` is mandatory because there is no `$default` stage) and the cost stated — a later host change means re-registering with Wix. Raised at §12.1 step 3 so the owner can pay it now instead. | §7.1, §12.1 |
| **R2-N22** (NIT-22) | **Addressed by citing them properly.** The Model B companions are now a table with verb, path and per-method slug, read from the live service schemas rather than an index page, split into the two distinct APIs that were previously conflated: the Wix Gift Cards app API (`/gift-cards/v1/gift-cards`, 8 methods) and the eCommerce host API (`/ecom/v1/gift-cards`, 3 methods). Neither is wired. | §1 |

Review items accepted without a document change, recorded so the reasoning is not lost:

- **Unverified item 9** (the whole SPI contract is in Developer Preview; whether Wix calls
  `/v1/balance` with the documented envelope cannot be tested without registration). Retained and
  strengthened — the preamble now cites `maturity: BETA` from the service schema as well as the
  page banner, and §9 names the signing algorithm as a third thing that cannot be known until
  registration.
- **Unverified item 11** (stale repo state). §11 is a new section recording the untracked files, the
  zero callers, the concurrent modifications, and a fallback table for each name this design does
  not own.
- **Unverified item 12** (Razorpay's minimum). Now verified and cited; see MEDIUM-13.
- **Verified assumptions 5–10, 12, 14, 17, 19, 20, 21, 22** were confirmed correct by the review
  and are unchanged.

---

## 14. Constraints this design is bound by

- Integer INR paise only; no float anywhere. `json.loads(payload, parse_float=Decimal)` at the SPI
  entry point is mandatory and tested by patching `float` to raise. The SPI amount is a JSON
  `number`; Cart V2's `redeemAmount.amount` is a decimal **string**; both are handled by their own
  converter (§6.2).
- Payment status decisions go through `payment_status.py`; the raw literal `'captured'` at a
  decision point is AST-banned. Both new handlers join `RAW_SCAN_ONLY_FILES`, not
  `CONSULTING_FILES` (§9.1).
- A gift-card code is **bearer value**: HMAC-with-pepper derived key, `codeLast4` in logs, never in
  full, never in a URL, path or query string.
- No credential value in any command, argv, log or logging expression. CodeQL tracks taint across
  functions, so the pepper and public key never appear in an expression a logger consumes, and the
  alert is never suppressed.
- `secretsmanager get-secret-value` / `batch-get-secret-value` are never called from a shell or
  from `aws___run_script`. Secrets are referenced by id and read lazily at request time inside the
  function.
- The existing `razorpay_verify` / `PROVIDERPAYMENT#` machinery is **untouched**. The gift-card leg
  is a separate module with its own ladder, its own evidence and its own claim (test 85).
- `memberships` and `subscriptionCharges` stay refused. Only `giftCards` is opened (test 100).
- New Lambdas are **authored, not deployed**. The SPI is **not registered** with Wix in this
  change. No IAM role, table, route, alarm or **KMS key** is created here — every provisioner
  defaults to a dry run and requires `--apply`.
- The gift-card table carries a **customer-managed KMS key** (DECISION 6), and creating it is a
  pointwise owner confirmation (§12.2 item 11). No TTL on a money table, ever: a liability must not
  expire silently.
- One active architecture: website Razorpay Standard Checkout. No Wix-native PSP, no Velo backend,
  no `submitEvent` bridge, no second checkout mode. `Place Order` ("This endpoint may charge the
  customer") and `Get Checkout URL` are never called.
- `/stores/v3`, `/site-media/v1` and `/members/v1` are untouched.
- No WAF, Security Hub, DNS, MX, MTA-STS, SPF, DMARC or Cognito change.

---

## 15. Related

- **`docs/execution/coupons-giftcards-build-20261001.md` — the build handoff. READ IT FIRST if you are
  picking this up cold.** Every plan item with its final status, the complete seam register with each
  seam's owner, exact anchor and `xfail(strict=True)` test, the owner-action list including the KMS
  pointwise confirmation, the unrun deploy order, and the `seo-tools-deploy.yml` CI warning.
- `docs/execution/coupons-20261001.md` — the companion document. A coupon is a **discount** and its code is **not**
  secret; both are the deliberate inverse of this design, and tests in both pin the asymmetry. It
  owns the **three** shared-gate edits this document depends on — including the
  `deploy_all_lambdas.py` registry entries for **both** of this document's functions, without
  which §12.3's deploy command does nothing.
- `.kiro/steering/whatsapp-payments-india-reference.md` — integer paise, fail-closed amount
  comparison, resolve-before-generate, `reference_id` being loggable in full, and the lazy-secret-
  read defect fixed 2026-09-19.
- `.kiro/steering/secret-handling.md` — why a secret must not appear in a logging expression at all.
- `.kiro/steering/lambda-snapstart-deploy.md` — the `live` alias rule, and why `secrets` is used
  over `random`.
- `.kiro/steering/00-current-owner-overrides.md` — WAF is removed, so handler-level verification is
  the only filter in front of this public route.
