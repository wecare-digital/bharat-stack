# Design — WhatsApp + Wix Headless conversational commerce

Derived from [`requirements.md`](requirements.md) and the Phase 0 findings in
[`docs/compatibility.md`](../../../docs/compatibility.md). Nothing here may be implemented
while R0 (Wix credential) is open, because every Wix contract below is unverified against
the live site.

## Decision record

Six decisions where this design deliberately departs from the prompt.

### D1 — Extend the Python fleet; do not introduce a Node.js API

The prompt specifies `nodejs24.x` + CDK v2 + TypeScript + Powertools for TypeScript. That
runtime is GA and would be right for a greenfield build. It is wrong here.

The fleet is 64 of 64 `python3.12`, deployed by `scripts/deploy_all_lambdas.py`, which
validates that every top-level import resolves inside the package or an attached layer, and
then publishes a version and moves the `live` alias. A Node.js function would need a second
packaging path, a second dependency tree, a second Powertools, and would sit outside the
import validator and the alias publisher — the two mechanisms that currently stop broken
code and stale code reaching production.

The payment path also already exists in Python: `_build_payment_settings`, the
`order_details` and checkout-template senders, `order_status` confirmation, and the payment
lookup call. Reimplementing it in TypeScript would mean two implementations of Meta's
payment payload, and the second one would be the untested one.

**Decision.** New handlers are `python3.12`, using the existing shared layer, deployer and
alias model. Powertools for Python where it adds value. `nodejs24.x` is recorded in the
compatibility manifest as *available and rejected, with reason*, so the choice is revisited
deliberately rather than forgotten.

**Cost accepted.** Loses the prompt's TypeScript-everywhere symmetry and Zod. Zod is
replaced by explicit schema validation in the existing `shared/lambda_utils/validation.py`.

### D2 — OAuth `client_credentials`, with the API key as a migration fallback

Wix documents client credentials as the recommended way to authorize headless admin
operations. The current code uses a permanent admin API key sent raw in `Authorization`.

**Decision.** `wixAuth` mints a short-lived access token from `client_id` + `client_secret`,
caches it in the execution environment, and refreshes on a safety margin before expiry. The
secret holds both fields so the migration can store and verify the new mechanism before the
API key is removed. `scripts/set_wix_credential.py` already supports both and preserves
whichever field it was not given.

Token caching is per execution environment, not per module import — same reasoning as the
secret loader. A 401 from Wix invalidates the cached token and triggers exactly one refresh
and retry, so a mid-lifetime revocation self-heals instead of failing every request until
the sandbox recycles.

### D3 — Keep the homegrown invoice engine; use Wix receipts only if the site offers them

The prompt asks for Wix Invoices v4 / Receipts v1. This repo has `payments/invoice-engine`
with `Invoice`, `InvoiceItem`, `InvoiceAsset`, `InvoiceDeliveryLog` and `InvoiceSequence` —
including a per-financial-year statutory sequence, GSTIN, HSN codes and GST rates. Wix
Invoices does not model Indian GST compliance, and a standalone Wix invoice can carry its
own payment flow, which is precisely the duplicate-payable-order hazard the prompt warns
about in §17.

**Decision.** The billing document is produced by the existing invoice engine and is the
system of record for statutory numbering. `billingDocumentService` first checks whether Wix
produced an **order-linked** document and reuses it for reconciliation display if so. No
standalone Wix invoice is ever created. Whether Wix Receipts is available to this site is
`BLOCKED` pending R0 and does not change the decision.

### D4 — Backend-managed cart keyed to phone

A WhatsApp customer has no browser session, so Wix's visitor-scoped `currentCart` has no
carrier. Combined with the frontend being a static export — no middleware, no server — there
is nowhere to hold a visitor token client-side safely.

**Decision.** The cart is owned by the backend and keyed on the customer's phone. Wix cart
id and revision are stored server-side; the customer never holds a Wix identifier.

### D5 — Reuse the existing order number format, add the missing uniqueness reservation

`_generate_wd_order_number` produces `WD-ORD - <UUID8> - <DD-MM-YYYY> - <HH:MM:SS> - IST`,
and the admin UI, `Order.shortId`, dropdown formatting and `docs/order-centric-architecture.md`
all depend on it. Replacing it with `WC-<DATE>-<ULID>` would break live surfaces for no
correctness gain — a UUID8 plus a reservation is as collision-safe as a ULID plus a
reservation.

What the current implementation lacks is the reservation itself. `_get_or_create_wd_order_number`
does read-then-write, and its exception path returns an **unstored** number, which is the
one case where a duplicate is most likely. That is the defect to fix, not the format.

**Decision.** Keep the format. Add the `ORDERNO#<number> / UNIQUE` conditional reservation,
and make the failure path fail closed rather than return an unreserved number.

### D6 — One HTTP API, existing routes extended

One HTTP API exists (`zllr9lrg7j`). New routes are added to it rather than standing up a
second API, so authorizer posture, WAF association and custom domain remain single-sourced.

---

## Architecture

```
WhatsApp  ──►  HTTP API zllr9lrg7j  ──►  whatsappWebhook (fast ACK)
                                              │  verify signature (raw body, HMAC-SHA256,
                                              │  timing-safe) → validate → claim
                                              │  idempotency → enqueue → 200
                                              ▼
                            ┌────────── SQS message queue ──────────┐
                            │                                       │
                            ▼                                       ▼
                    messageProcessor                        SQS payment queue
                            │                                       │
              Wix catalog / cart / checkout                         ▼
              WhatsApp sends                          paymentReconciliation
              DynamoDB state                                        │
                                                    ┌───────────────┴───────────────┐
                                                    │ compare currency + amount      │
                                                    │ resolve reference_id → order   │
                                                    │ create/resolve Wix order ONCE  │
                                                    │ record external payment        │
                                                    │ await Wix PAID reconciliation  │
                                                    │ generate billing document      │
                                                    │ send confirmation              │
                                                    └───────────────┬───────────────┘
                                                                    ▼
                                                        DLQ on exhausted retries
```

Fulfillment runs on its own path: a Wix fulfillment event updates state, appends a timeline
event, refreshes the tracking page and optionally sends a WhatsApp `order_status` update.

**Why the split queue.** Message traffic is chatty and cheap to reprocess. Payment traffic
is rare and expensive to get wrong. Separate queues let payment reconciliation have its own
concurrency limit, its own retry policy, its own DLQ and its own alarm, and stop a catalog
browsing spike from delaying a capture.

---

## Data model

Single-table additions alongside the existing `Order`, `Payment`, `WixOrdersCache`,
`WixOrderId`, `WebhookDedup` and invoice tables. The existing tables are not restructured —
`Order` is already the order-centric record and is read by live admin UI.

| PK | SK | Purpose |
|---|---|---|
| `ORDER#<commerceOrderId>` | `METADATA` | order record and current state |
| `ORDER#<commerceOrderId>` | `EVENT#<ts>#<eventId>` | append-only timeline |
| `ORDERNO#<commerceOrderNumber>` | `UNIQUE` | **uniqueness reservation** |
| `REFERENCE#<metaReferenceId>` | `ORDER` | Meta reference → order |
| `CHECKOUT#<wixCheckoutId>` | `ORDER` | checkout → order |
| `WIXORDER#<wixOrderId>` | `ORDER` | Wix order → order, prevents a second Wix order |
| `PAYMENT#<providerTransactionId>` | `METADATA` | provider transaction uniqueness |
| `TRACKING#<tokenHash>` | `ORDER` | tracking token → order |
| `USER#<phone>` | `CART#ACTIVE` | backend-managed cart, with TTL |
| `IDEMPOTENCY#<eventId>` | `EVENT` | webhook dedupe, with TTL |

Every mapping row above exists so that a duplicate inbound event resolves to an existing
order instead of creating one. GSIs are added only for admin queries that exist: by
creation date, by payment status, by reconciliation status, by fulfillment status.

---

## Order number algorithm

```
candidate  = WD-ORD - <UUID8> - <DD-MM-YYYY> - <HH:MM:SS> - IST
reserve    = PutItem  PK=ORDERNO#<candidate>  SK=UNIQUE
             ConditionExpression: attribute_not_exists(PK)

ConditionalCheckFailed  →  regenerate, retry, bounded attempts
any other error         →  FAIL CLOSED, return no number
exhausted attempts      →  FAIL CLOSED, alarm
```

The reservation is written **before** the number is returned to any caller. Order creation
then uses `TransactWriteItems` to write the order metadata and the reference/checkout
mappings together, so a partially-created order is not observable.

Idempotent re-entry is a lookup, not a generation: given a Meta `reference_id`, resolve
`REFERENCE#<id>` first and return the existing order if present. Generation happens only
when no mapping exists.

---

## State machine

```
CART_ACTIVE → CHECKOUT_CREATED → PAYMENT_REQUESTED → PAYMENT_PENDING
   → PAYMENT_CONFIRMED → WIX_ORDER_PENDING → WIX_ORDER_CREATED
   → WIX_PAYMENT_PENDING → WIX_PAYMENT_CONFIRMED
   → BILLING_DOCUMENT_PENDING → BILLING_DOCUMENT_READY
   → CONFIRMED → FULFILLMENT_PENDING → SHIPPED → DELIVERED

side exits: CANCELLED · REFUNDED · RECONCILIATION_FAILED
```

Transitions are applied with `ConditionExpression` on the current state, so a concurrent or
replayed worker attempting the same transition fails harmlessly rather than double-applying
its side effect. `RECONCILIATION_FAILED` is recoverable: a staff retry re-enters at the
last confirmed state, never at the beginning.

**Status vocabulary must be unified.** `payment_status.py` records that `InvoicesTable` and
`OrderTable` say `paid` where `PaymentsTable` says `captured`, and that `PaymentsTable`
currently holds zero rows. A reconciliation built on top of two vocabularies will produce
disagreeing dashboards. One vocabulary is chosen and the mapping to each legacy table is
explicit and single-sourced.

---

## Reconciliation

Ordered, and the order is the design:

1. Verify Meta signature on the raw body.
2. Claim the idempotency key. An already-claimed key returns the existing outcome.
3. Resolve `reference_id` → order. No mapping means no order; do not create one from a
   payment event.
4. Load the authoritative Wix checkout. Compare currency, then amount in minor units, then
   customer. Any mismatch fails closed.
5. Create or resolve the Wix order **once**, guarded by `WIXORDER#<id>`.
6. Record the externally collected payment via Order Transactions. This records; it does
   not collect. No Wix call that could charge again is reachable from this path.
7. Wait for Wix to reconcile payment state. Poll with backoff; do not assume.
8. Generate the billing document, guarded so exactly one exists.
9. Send the customer confirmation, guarded against duplicate customer-visible messages.

Steps 5-9 each carry their own guard, so a retry that failed at step 7 does not redo 5 or 6.

**Warm-sandbox caveat.** A function caches its secrets on first use, so replacing a value in
Secrets Manager does not change what a warm sandbox serves. Publishing a new version has no
warm environments; `scripts/refresh_secret_consumers.py` exists for exactly this and must be
run after any credential change, with `scripts/check_secrets_live.py` confirming the provider
accepts the new value.

---

## Billing document flow

```
payment confirmed AND Wix reconciled
        │
        ▼
does Wix hold an ORDER-LINKED document?  ── yes ──► record its ids, reuse for display
        │ no
        ▼
invoice-engine generates the statutory document (per-FY sequence, GSTIN, HSN)
        │
        ▼
persist ids + status ──► deliver ──► record sentAt / viewedAt
```

A standalone Wix invoice is never created, because it can carry its own payment flow and
would risk a second payable order. Delivery never exposes a permanent Wix URL: the document
is proxied through an authenticated API, or copied to a private S3 object and served by a
short-lived signed URL.

---

## Tracking security

The frontend is a static export, so it has no server and cannot validate anything. All token
handling is in Lambda.

- Token is 256 bits from a CSPRNG. `secrets` / `os.urandom`, never `random`.
- Only a hash is stored, under `TRACKING#<tokenHash>`. The plaintext token exists only in
  the link sent to the customer.
- An invalid token and a token for a non-existent order return the same response, so the
  endpoint is not an order-existence oracle.
- The order number alone grants nothing.

---

## Error matrix

| Condition | Response | Retry | Customer sees | Alarm |
|---|---|---|---|---|
| Bad webhook signature | reject, do not enqueue | no | nothing | yes |
| Duplicate webhook | ACK, no side effect | no | nothing | metric only |
| Amount or currency mismatch | fail closed | no | payment under review | yes |
| Wix unavailable pre-payment | fail request | yes | try again shortly | on sustained |
| Wix unavailable post-capture | `RECONCILIATION_FAILED`, order preserved | yes, staff-retryable | payment received, order confirming | yes |
| Wix order already exists | resolve, continue | n/a | nothing unusual | metric only |
| Stock gone after capture | fail closed, refund path | no | staff contact + refund | yes |
| Billing document fails | order stays confirmed | yes | confirmation without document link | yes |
| Confirmation send fails | retry, guarded | yes | delayed message | on exhaustion |
| DLQ non-empty | — | staff | nothing | yes |

The distinction that matters: a failure **before** capture may fail the customer's request;
a failure **after** capture may never lose the order and may never charge again.

---

## IAM

Per-function least privilege, no shared role:

- `whatsappWebhook` — `sqs:SendMessage` on its two queues, conditional `dynamodb:PutItem`
  on the idempotency table, read on the Meta app-secret secret. No Wix access at all.
- `messageProcessor` — read on the Wix credential secret, read/write on cart and order
  items, `lambda:InvokeFunction` on the sender.
- `paymentReconciliation` — read on Wix and Meta secrets, read/write on order, payment,
  timeline and mapping items, write to the billing bucket.
- Admin API — read on order/payment/timeline; write only through the named retry
  operations.

Bucket policies distinguish `arn:...:bucket` from `arn:...:bucket/*`. Conditional
`aws:SourceAccount` / `aws:SourceArn` on any service trust policy created.

---

## Retry strategy

| Layer | Policy |
|---|---|
| SQS message queue | 3 receives, exponential backoff, then DLQ |
| SQS payment queue | 5 receives, longer visibility timeout, then DLQ with alarm |
| Wix API | bounded retry on 5xx and 429; never on 4xx except a single 401 token refresh |
| Meta API | honour the documented retry flag per error code; `131056` pair rate limit backs off 4^n |
| Wix payment-state poll | bounded backoff, then `RECONCILIATION_FAILED` rather than indefinite wait |
| Staff retry | idempotent, re-enters at last confirmed state |

Batch processing reports partial failures so one bad message does not fail its whole batch.

---

## Open questions requiring R0

Each is a real unknown, not a formality:

1. Is the site's Stores catalog actually V3? The code calls V3; the site has not confirmed.
2. Are Wix Invoices and Receipts available to this site, and does Wix produce an
   order-linked document for an externally collected payment?
3. Which inventory adjustment does the chosen order-creation strategy perform, and does it
   require a manual decrement? R8 cannot be closed until this is measured.
4. Does the Wix cart/checkout contract match the shapes assumed here?
5. Is `+919330994400` connected? `inbound-whatsapp-handler:7309` says disconnected.
