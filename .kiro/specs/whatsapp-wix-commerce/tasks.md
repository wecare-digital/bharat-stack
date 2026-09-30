# Implementation plan

## Owner architecture decision — 2026-10-01

Use the existing self-managed Next.js/AWS headless application. WhatsApp/Razorpay collects payment externally; create the internal order and Wix order only after authoritative verification, then record the external payment without charging again. Velo and external PSP onboarding are not dependencies. Retain admin-only Cognito and WhatsApp-only receipts. Historical provider configuration claims below require live verification. See `docs/execution/headless-checkout-20261001.md` for the current partial audit and implementation gaps.

Payment safety before wiring: reject unbound provider payments; enforce customer ownership before duplicate shortcuts; accept exact DynamoDB Decimal integers but no float coercion; pending/unknown is never retryable; prevent competing number assignments and repeating ambiguous Wix writes.


Derived from [`requirements.md`](requirements.md) and [`design.md`](design.md).

---

## ⚠️ PRODUCTION GATE — payment config RESTORED by owner (2026-09-30), credential load still owner-pending

A probe on 2026-09-30 returned `GET /2094615664435155/payment_configurations -> HTTP 200, ZERO
configurations`, and the earlier text below was written against that empty state. **The owner has
since restored the configurations in WhatsApp Manager and reported them Active** on both WABAs.
Recorded from the owner's dashboard readout, not re-probed by this session — a live
`payment_readiness.evaluate()` should be run to confirm before the first real send:

| Config | WABA | Type | Value | Status |
|---|---|---|---|---|
| `WECAREDIGITAL` | `2094615664435155` | payment_gateway (razorpay) | MID `acc_TTFSyolquKEZEy` | Active |
| `WECAREUPI` | `2094615664435155` | upi | `wecaredigitalbh511413.rzp@rxairtel` | Active |
| `WECAREDIGITAL` | `2513394156072604` | payment_gateway (razorpay) | MID `acc_TTFSyolquKEZEy` | Active |
| `WECAREUPI` | `2513394156072604` | upi | `wecaredigitalbh511413.rzp@rxairtel` | Active |

MCC `7392`, purpose code `03` on all four. No application code created these; they are owner
work. `payment_readiness.py` still refuses if a live readback disagrees.

**Both readiness conflicts are RESOLVED, and the resolution reversed the repo's earlier guess:**

- **Razorpay MID** is `acc_TTFSyolquKEZEy` (the value Meta reports as the config's `provider_mid`).
  The repo had assumed `acc_HDfub6wOfQybuH` — that was the stale env value and the webhook
  `account_id`, not what the configuration points at. `config/lambda-env-manifest.json` and
  `payment_readiness.py` corrected; the manifest env is **not yet pushed live** — it rides with the
  credential-load step.
- **UPI VPA** is `wecaredigitalbh511413.rzp@rxairtel` (the `constants.ts` fallback was right).
  Live env `wecaredigital83.rzp@icici` was stale and is corrected in the manifest.

**Still owner-pending, so no live payment yet:** the Razorpay live key + secret and the Wix admin
token must be (re)loaded into Secrets Manager via the owner-run helpers
(`set_wix_credential.py --verify`, `refresh_secret_consumers.py`, `check_secrets_live.py`). Both
were disclosed in a chat transcript on 2026-09-30 and must be **rotated**, not merely stored.

**Not blocked by this gate**, and therefore the work that proceeds: customer identity, phone and
email verification, the address model, the checkout UI, the authoritative Wix total, the payment
attempt model, payment history, the post-paid order architecture and the receipt architecture.

**Phase 0 is complete and Phase 1 is startable. Phases 6 onward are blocked on R0** — the
Wix credential does not exist in AWS, so no Wix contract can be verified. Tasks are ordered
so that everything genuinely doable while R0 is open comes first, rather than stalling the
whole plan behind one owner action.

Each task states the requirement it satisfies and how it is verified. Per R18, a command
exiting zero is not verification.

---

## Phase 0 — Read-only capability discovery ✅ COMPLETE

- [x] 0.1 Measure the live fleet: runtimes, HTTP APIs, aliases, secret inventory
  - Verified: 64/64 `python3.12`; 1 HTTP API `zllr9lrg7j`; 25 secrets
- [x] 0.2 Establish the Wix credential state without reading any value
  - Verified: `wecare/wix/headless-api-key` exists with `versionCount: 0`, no `AWSCURRENT`
- [x] 0.3 Confirm no Wix credential is recoverable from an authorized location
  - Verified: 0 `IST.`-prefixed tokens in the maintenance source; retired `wecare/wix-api-key` absent
- [x] 0.4 Verify vendor documentation baselines
  - Verified: Wix `client_credentials` recommended; `nodejs24.x` GA; Meta payments-India surface
- [x] 0.5 Correct `scripts/set_wix_credential.py`
  - Secret name fixed; OAuth client-secret storage and verification added; `--status` now
    reports `holdsValue`
- [x] 0.6 Produce the capability matrix → `docs/compatibility.md`

---

## Phase 1 — Version compatibility layer (startable now, no Wix dependency)

- [x] 1.1 Single-source the Meta Graph version
  - **It was 11 module constants and 5 URL literals, not 7 and 3** — plus three more the
    new test found on its first run (`ai-generate-response`, `partner-onboarding`,
    `partner-token-refresh` read the env var under local names `api_version` /
    `API_VERSION`, invisible to a grep for the canonical name), and `meta_client.py` as a
    twelfth opinion. All 19 now import `lambda_utils/meta_version.py`
  - _Requirements: R1.1, R1.2_
  - Verified: `tests/test_meta_version.py` — 18 tests asserting no local declaration and
    no URL literal anywhere under `amplify/functions`, plus agreement with
    `config/vendor-versions.json`. Whole fleet deployed (62 functions, 0 stale files)
- [x] 1.2 Fail startup on a malformed version
  - Raises `MetaVersionError` at **import**, not at request time: a bad value otherwise
    surfaces as a Graph 400 about an unknown path, which reads like an application bug
  - **Absent and empty are deliberately different** — absent means no opinion and the
    pinned default applies; `META_API_VERSION=""` means someone configured it and got it
    wrong, most likely an unresolved deploy-template substitution, and silently defaulting
    would hide exactly that
  - _Requirements: R1.3_ · Verified: parametrised over `v25`, `25.0`, `latest`, `v25.0.1`,
    `""`, `v.0`, `vv25.0`, `v25.00`, `V25.0`
- [ ] 1.3 Write the compatibility manifest and version checker
  - Record `nodejs24.x` as available-and-rejected with the D1 reason, so the decision is
    revisited rather than forgotten
  - _Requirements: R1.4_
- [x] 1.4 Unify the payment status vocabulary
  - `payment_status.py` documents `paid` vs `captured` disagreement across three tables;
    choose one and make each legacy mapping explicit
  - **Done 2026-09-30.** The module already held the mapping; the gap was that nobody
    consulted it. Every payment *decision* now routes through `canonical()`/`rank()`:
    `invoice-engine`, `inbound-whatsapp-handler`, `outbound-whatsapp`,
    `whatsapp-business-api` (+ `flows/track_request`), `secure-files/razorpay_orders`.
    Three raw comparisons were failing dangerously — a paid invoice was cancellable, a
    Meta-confirmed capture was recorded `REJECTED_MISMATCH`, and a paying customer was
    told the payment failed.
  - Scope boundaries, both pinned by tests: `InvoicesTable.status` is a document lifecycle
    and stays literal; renderers (badge colour, PDF stamp) are not decisions. Only
    `captured` is banned as a raw literal, since `paid` is legitimately shared with the
    lifecycle vocabulary.
  - _Requirements: R15, R7.8_ · _Verify:_ `tests/test_payment_vocabulary_at_decision_points.py`
    (53 tests: 5 decision points parameterised over every measured spelling, an AST gate on
    raw `captured` comparisons, an import assertion per handler, and a test pinning why
    `paid` is deliberately excluded). 5201 pytest passed. Deployed: invoice-engine v38,
    inbound v65, outbound v43, business-api v55, secure-files v21.
- [x] 1.5 Fill `.kiro/steering/whatsapp-payments-india-reference.md`
  - Was 0 bytes while carrying `inclusion: always`, which is worse than absent: it occupied
    a slot that reads as "the payments rules are written down". Now holds the one-gateway
    rule and the Razorpay secret path, the two payment configurations being
    non-interchangeable, MCC 7392 / purpose code 03, integer-paise money with the reason
    the fail-closed comparison needs it, and the four `reference_id` rules
  - Deliberately does **not** reproduce the two configuration names — a dated constant in
    steering is what `00-current-owner-overrides.md` forbids quoting
  - _Requirements: R1, R6_

## Phase 2 — Identity subsystem ✅ COMPLETE (re-timed for order-after-payment)

**R2 was reversed on 2026-09-30.** The original 2.1-2.4 asked for an order number reserved as
part of building the payment request; that is now prohibited. The conditional-reservation
mechanism was kept and re-pointed, not thrown away.

- [x] 2.1 Conditional reservation under `ORDERNO#<number>`, written before the number is returned
  - Retargeted to the 12-character public number. `reserve_public_order_number` in
    `lambda_utils/ecommerce/order_keys.py`
  - _Requirements: R2.6, R2.7_
- [x] 2.2 Make the failure path fail closed
  - `_get_or_create_wd_order_number` returned an **unstored** number on DynamoDB failure. It
    also was never idempotent: the reuse check was `startswith('WD-ORD-')` but the generator
    emits a SPACE at index 6, so every call regenerated and overwrote the mapping — and
    `_enrich_order` calls it per order per listing
  - _Requirements: R2.8_ · Verified: fault-injection test asserting no identifier escapes
- [x] 2.3 Split the payment reference from the order identity
  - `allocate_order_identity` **removed**, not deprecated. `PAYREF#` binds a reference to a
    payment attempt and holds no order fields; `PAYMENTATTEMPT#` and `PROVIDERPAYMENT#` are
    claimed only after verified capture
  - _Requirements: R2.1, R2.4, R2.5_
- [x] 2.4 Stop truncating the Meta reference
  - `_sanitize_reference_id` ended with `result[:35]`. Truncating a join key maps two references
    onto one string, so two orders reconcile against one payment. Outbound now raises and
    refuses an order number outright; inbound returns an already-valid reference byte-for-byte,
    since Meta's `reference_id` is case sensitive and permits dots
  - _Requirements: R2.2_
- [x] 2.5 Identifier test suite
  - 10,000 reservations with zero duplicates; duplicate webhook; one provider payment across two
    attempts; loser burns no number; crash between claim and reserve is recoverable; every
    non-paid state has zero orders; retry lineage via `retryOf`
  - _Requirements: R2.3, R2.9-R2.14_ · 83 tests in `test_order_keys.py` +
    `test_reference_id_never_truncated.py`
- [x] 2.6 UUIDv7 and ULID primitives
  - `lambda_utils/identifiers.py`. Nothing in the fleet minted either, and `uuid.uuid7` does not
    exist in CPython 3.12
  - _Requirements: R2 identifier table_

## Phase 3 — Idempotency hardening (startable now)

- [ ] 3.1 Reuse `WebhookDedup` + existing idempotency primitives; add no parallel table
  - _Requirements: R4.3_
- [ ] 3.2 Replace any read-then-write uniqueness with conditional writes / transactions
  - _Requirements: R4.1_
- [ ] 3.3 Per-side-effect guards for Wix order, payment record, billing document, confirmation
  - _Requirements: R4.2_ · _Verify: replay the same event 5× and assert each side effect once_

## Phase 4 — Meta webhook ingestion (startable now)

- [ ] 4.1 `GET` verification against `hub.verify_token`
  - _Requirements: R3.1_
- [ ] 4.2 `POST` raw-body HMAC-SHA256 with timing-safe comparison
  - _Requirements: R3.2_ · _Verify: valid signature accepted, tampered body rejected, and a
    test that the raw body is used rather than a re-serialized one_
- [ ] 4.3 Validate, normalize, claim idempotency, enqueue, fast ACK
  - _Requirements: R3.4, R3.5_
- [ ] 4.4 `WebhookSignatureFailed` metric and alarm
  - _Requirements: R3.3, R17.2_

## Phase 5 — Infrastructure (startable now)

- [ ] 5.1 Message queue, payment queue, both DLQs, encryption at rest
  - _Requirements: R17.3_
- [ ] 5.2 New single-table entities and the four admin GSIs
  - _Requirements: R13, R12.2_
- [ ] 5.3 Private billing-document bucket, no public access, KMS
  - _Requirements: R10.2, R10.3_
- [ ] 5.4 Per-function least-privilege roles; distinguish `bucket` from `bucket/*`
  - _Requirements: R16.6_
- [ ] 5.5 Add routes to the existing HTTP API `zllr9lrg7j`
  - _Requirements: D6_ · _Verify: `cdk diff` / IaC validation clean, no second API created_

---

## ✅ R0 GATE — CLEARED 2026-09-26

- [x] R0.1 Owner supplied the Wix Headless admin API key
- [x] R0.2 Stored without argv exposure; staging file shredded
- [x] R0.3 `--status` → `holdsValue: true`, `versionCount: 1`
- [x] R0.4 `WIX_API_KEY_SECRET` pointer set on `wecare-wix-store`
- [x] R0.5 `WIX_CREDENTIALS_DISABLED` cleared; v22 published, `live` alias moved from v21
- [x] R0.6 Catalog version re-measured: **V3 confirmed live**, 7 products, 1 category
- [x] R0.7 Live proof: `wecare-wix-store:live` returned real products
- [x] R0.8 Encrypted local + S3 recovery copies refreshed and verified
- [ ] R0.9 **Rotate the key** — it was pasted into a chat transcript
- [x] R0.10 **Confirm the site id** in the Wix dashboard before Phase 8 writes an order
  - Owner-confirmed 2026-09-30: Headless Site ID `fcd82f0c-9572-49c7-acfb-88fb05042ece`
    (Wix account `15f02319-40ff-4288-b8e6-69c791adae5e`, headless client id
    `197cd718-e4ec-4e2e-b380-46c297eb18a2`). This is the id the repo already configures, so the
    write-back path may target it once enabled.
- [x] R0.11 Probe installed apps and Invoices/Receipts availability
  - **2026-10-01** (`scripts/probe_wix_capabilities.py`, public client id, no secret):
    `wixStores` INSTALLED, `wixEcommerce` INSTALLED (admin scope), `wixBlog` INSTALLED,
    `wixInvoices` **NOT AVAILABLE**, `checkoutRedirect` REACHABLE, Cart **V2** route LIVE
    (`/ecom/v2/carts/{id}` → 404 CART_NOT_FOUND). Site resolves to `xout.wecare.digital`,
    7 products.
- [ ] R0.12 Migrate to the `client_credentials` grant, then drop the API key field

Everything below requires R0 closed.

## Phase 6 — Wix authentication

- [ ] 6.1 `wixAuth`: `client_credentials` exchange, per-sandbox token cache, refresh margin
  - _Requirements: R0.1, D2_
- [ ] 6.2 Single 401-triggered refresh-and-retry
  - _Requirements: D2_ · _Verify: test that a revoked token self-heals once, not in a loop_
- [ ] 6.3 Keep the API-key path as fallback until client credentials are proven live
- [ ] 6.4 Remove the API-key path and delete the field from the secret

## Phase 7 — Catalog

- [x] 7.1 Confirm the site's catalog version, then bind the adapter to it
  - **CATALOG_V3 confirmed live 2026-10-01** (`scripts/probe_wix_capabilities.py`: stores/v1
    → `501 UNIMPLEMENTED`, stores/v3 responds). The adapter already calls V3.
  - _Requirements: R5.1_
- [ ] 7.2 Search, query, get product, get variant, check inventory
  - Read paths largely exist in `wix-store/handler.py` (`/stores/v3/products/*`, inventory).
    Confirm the variant/`catalogReference` fields needed to add a V2 line item are surfaced.
- [ ] 7.3 Reject any client-supplied price
  - _Requirements: R5.2_ · _Verify: test that a tampered client price is ignored_

## Phase 8 — Cart (Wix Cart V2)

**Revised 2026-10-01 for Cart V2.** Cart V1/Checkout V1 are removed by Wix on 2027-02-01;
`/ecom/v2/carts` confirmed live. There is no "create checkout" step — the cart is the
checkout, the authoritative total is **Calculate Cart**, and an order exists only after
payment (Phase 10/11). This is an in-chat flow; the Wix checkout page is not used. See D7.

- [ ] 8.1 Backend cart keyed on phone, with the Wix cart id + revision and a TTL
  - `USER#<phone> / CART#ACTIVE`; the customer never holds a Wix identifier
  - _Requirements: R5.3, R5.5_
- [ ] 8.2 Cart V2 adapter in `wix-store`: create cart, add / update / remove line items
      (`catalogReference {appId, catalogItemId, options.variantId}`), Calculate Cart for the
      authoritative total and price verification token, read `summary.violations`
  - _Requirements: R5.4_ · _Verify: contract test against the live V2 boundary (read/calc
    only) before any order-writing call_
- [ ] 8.3 Integer-minor-unit money type; no float arithmetic anywhere in the path
  - _Requirements: R6.1_ · _Verify: test asserting no float in the money path_

## Phase 9 — WhatsApp payment request

- [ ] 9.1 Build `order_details` from a live Wix **Calculate Cart** (`summary.priceSummary`),
      carrying the price verification token forward to order creation
  - _Requirements: R6.5_
- [ ] 9.2 Enforce exact total equality against the Wix Calculate-Cart total; reject on any
      difference
  - _Requirements: R6.2, R6.3_ · _Verify: one-paise mismatch is rejected_
- [ ] 9.3 Explicit currency comparison
  - _Requirements: R6.4_
- [ ] 9.4 Reuse the existing `_build_payment_settings`; do not reimplement
  - _Requirements: D1_

## Phase 10 — Reconciliation

- [ ] 10.1 Ordered pipeline exactly as `design.md` specifies (Cart V2: authoritative total
      from Calculate Cart, order from the bound cart)
  - _Requirements: R7.1_
- [ ] 10.2 Create-or-resolve Wix order once from the bound Wix cart, guarded by
      `WIXORDER#<id>` (V2 `Place Order` or create + `Mark Cart As Completed`)
  - _Requirements: R7.2_
- [ ] 10.3 Await Wix payment reconciliation with bounded backoff
  - _Requirements: R7.6_
- [ ] 10.4 Recoverable failure state; never lose a paid order
  - _Requirements: R7.7_
- [ ] 10.5 Fail closed on amount or currency mismatch
  - _Requirements: R7.8_

## Phase 11 — Wix order creation and external payment record (Cart V2)

**Settle the exact V2 order-creation call here**, against the live admin contract: `Place
Order` with the payment marked external, versus create the order and `Mark Cart As
Completed`. This is the first phase that writes to the live site, and no order-writing call
runs until 11.2's enumeration test passes.

- [ ] 11.1 Record the externally collected payment against the created order (external
      payment, not a collection)
  - _Requirements: R7.3_
- [ ] 11.2 Assert no reachable Wix V2 call can charge again
  - _Requirements: R7.4_ · _Verify: an explicit test enumerating every Wix call this path can
    make and asserting none collects payment_
- [ ] 11.3 Unique `providerTransactionId`
  - _Requirements: R7.5_
- [ ] 11.4 Determine and document the inventory strategy; prove single decrement
  - _Requirements: R8.1, R8.2, R8.3_ · _Verify: stock before/after a full order is −1, not −2_
- [ ] 11.5 Handle insufficient stock, concurrency, preorder, backorder, multi-location,
      and paid-but-out-of-stock
  - _Requirements: R8.4, R8.5_

## Phase 12 — Billing documents

**`WIX-INVOICE-001` resolved 2026-09-28: not a blocker.** `wixInvoices` is NOT AVAILABLE
and `invoicesV2` 404s — both re-confirmed live — but R9.3 is conditional and its condition
is false, and R9.2 is *unreachable* rather than merely satisfied. The document is issued
by `payments/invoice-engine`, which already sequences numbers, renders PDF/PNG and logs
delivery. See the resolution note under R9 in `requirements.md`.

- [ ] 12.1 `billingDocumentService`: issue through `invoice-engine`; keep the
      order-linked-Wix-document reuse branch behind a capability probe so it becomes
      reachable if the Invoices app is ever installed
  - _Requirements: R9.3_ · _Verify: probe reports `wixInvoices NOT AVAILABLE` and the
    reuse branch is not taken; `billingDocumentType == 'SELF_ISSUED'`_
- [ ] 12.2 Never create a standalone Wix invoice
  - _Requirements: R9.2_ · _Verify: test asserting no standalone-invoice call is reachable_
- [ ] 12.3 Exactly one document per order across retries
  - _Requirements: R9.4_
- [ ] 12.4 Persist the full document field set
  - _Requirements: R9.5_
- [ ] 12.5 Retryable generation without duplication
  - _Requirements: R9.6_

## Phase 13 — Delivery and fulfillment

- [ ] 13.1 Confirmation from `+919330994400` with the full field set
  - _Requirements: R10.1_
- [ ] 13.2 Proxy or short-lived signed URL; never a permanent Wix URL
  - _Requirements: R10.2, R10.3_ · _Verify: the issued link expires_
- [ ] 13.3 Guarded retry with no duplicate customer-visible message
  - _Requirements: R10.4_
- [ ] 13.4 Fulfillment consumption, timeline append, optional `order_status` update
  - _Requirements: R14.1, R14.2, R14.3_
- [ ] 13.5 Restrict live sends to the QA recipient until separately authorized
  - _Requirements: R10.5_

## Phase 14 — Customer tracking page

- [ ] 14.1 256-bit CSPRNG token; `secrets`, never `random`
  - _Requirements: R11.2_
- [ ] 14.2 Store only the hash
  - _Requirements: R11.3_
- [ ] 14.3 Validate in Lambda; the static export cannot validate
  - _Requirements: R11.6_
- [ ] 14.4 Indistinguishable response for invalid, expired and non-existent
  - _Requirements: R11.4_ · _Verify: identical status and body across all three_
- [ ] 14.5 Order number alone grants nothing
  - _Requirements: R11.1_
- [ ] 14.6 Render the full field set and timeline
  - _Requirements: R11.5_

## Phase 15 — Admin surface

- [ ] 15.1 Authenticated admin routes, MFA for privileged production admins
  - _Requirements: R12.1_
- [ ] 15.2 Consolidated order detail with every identifier and the full timeline
  - _Requirements: R12.2_
- [ ] 15.3 Retry reconciliation / confirmation / billing document, regenerate link,
      inspect DLQ reason and sanitized webhook metadata
  - _Requirements: R12.3_
- [ ] 15.4 Every operation idempotent
  - _Requirements: R12.4_ · _Verify: double-click each retry, assert one effect_
- [ ] 15.5 No debugging endpoint in production
  - _Requirements: R12.5_
- [ ] 15.6 Per-handler auth assertion, not inferred from `AuthorizationType`
  - _Requirements: R12.6_
- [ ] 15.7 Version health page and authenticated machine endpoint
  - _Requirements: R1.4_

## Phase 16 — Timeline

- [ ] 16.1 Append-only writes; no update or delete path
  - _Requirements: R13.1_ · _Verify: IAM denies `UpdateItem`/`DeleteItem` on event items_
- [ ] 16.2 Timestamp, actor, source, correlation ids on every event
  - _Requirements: R13.2_
- [ ] 16.3 One timeline, filtered for the customer view
  - _Requirements: R13.3_

## Phase 17 — Observability

- [ ] 17.1 Structured logs with the full correlation id set
  - _Requirements: R17.1_
- [ ] 17.2 All metrics from R17.2
- [ ] 17.3 Alarms on DLQ depth and reconciliation failure
  - _Requirements: R17.3_
- [ ] 17.4 Phone masking, and disambiguate `…0044` by direction/channel/delivery id rather
      than widening the mask
  - _Requirements: R17.4_

## Phase 18 — Security review

- [ ] 18.1 A named control for every threat in R16
- [ ] 18.2 No secret in the browser bundle
  - _Requirements: R16.1_ · _Verify: `scripts/verify_public_bundle_secrets.py`_
- [ ] 18.3 No secret in a log **expression**, including a ternary on truthiness or a derived
      boolean; taint crosses function boundaries
  - _Requirements: R16.2_ · _Verify: CodeQL `py/clear-text-logging-sensitive-data` clean,
    with no suppression_
- [ ] 18.4 Lazy per-request secret loading, never at import scope
  - _Requirements: R16.4_
- [ ] 18.5 Short-lived tracking tokens; no card number or CVV anywhere
  - _Requirements: R16.5, R16.7_

## Phase 19 — Tests

- [ ] 19.1 Backend: order numbers, Meta signature, payment states, Wix contracts,
      reconciliation paths, billing single-generation
  - _Requirements: R18.3_
- [ ] 19.2 Frontend: browsing, cart, checkout status, valid/invalid token, payment
      pending/success/failure, invoice available, shipment, refund
- [ ] 19.3 Admin: auth, search, detail, payment detail, timeline, reconciliation retry,
      invoice regeneration, DLQ visibility, permissions
- [ ] 19.4 Contract tests at both vendor boundaries
  - _Requirements: R18.3_

## Phase 20 — CI/CD

- [ ] 20.1 Lint, typecheck, tests, IaC validation as deployment gates
  - _Requirements: R18.1, R18.2_
- [ ] 20.2 Pinned dependencies and committed lockfiles; no floating `latest`
- [ ] 20.3 Version-drift detection that opens a PR and never auto-deploys
  - _Requirements: R1.5_
- [ ] 20.4 Enforce publish-version-and-move-alias in the deploy path
  - _Requirements: R18.4_ · _Verify: a `$LATEST`-only change does not reach the `live` alias_

## Phase 21 — Production readiness

- [ ] 21.1 Re-run full discovery; refresh `docs/compatibility.md` rather than trusting it
- [ ] 21.2 End-to-end test to the QA recipient only
- [ ] 21.3 Confirm `+919330994400` connection state — `inbound-whatsapp-handler:7309`
      currently says disconnected
- [ ] 21.4 Rollback version captured before each function deploy
- [ ] 21.5 Production deployment checkpoint with account, region, commit, functions,
      secrets, tests, infra diff, rollback version
- [ ] 21.6 Post-deploy smoke tests and alarm verification
