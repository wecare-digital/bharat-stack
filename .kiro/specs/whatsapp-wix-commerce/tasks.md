# Implementation plan

Derived from [`requirements.md`](requirements.md) and [`design.md`](design.md).

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

- [ ] 1.1 Single-source the Meta Graph version
  - Remove the 7 hard-coded `META_API_VERSION` module constants and the 3 URL-embedded
    literals; resolve from one config module
  - _Requirements: R1.1, R1.2_
  - _Verify: `grep -rn 'v2[0-9]\.[0-9]' amplify/functions` returns no request-URL literal_
- [ ] 1.2 Fail startup on a malformed version
  - _Requirements: R1.3_ · _Verify: unit test with `v25`, `25.0`, `latest`_
- [ ] 1.3 Write the compatibility manifest and version checker
  - Record `nodejs24.x` as available-and-rejected with the D1 reason, so the decision is
    revisited rather than forgotten
  - _Requirements: R1.4_
- [ ] 1.4 Unify the payment status vocabulary
  - `payment_status.py` documents `paid` vs `captured` disagreement across three tables;
    choose one and make each legacy mapping explicit
  - _Requirements: R15, R7.8_ · _Verify: test asserting one vocabulary across all three_
- [ ] 1.5 Fill `.kiro/steering/whatsapp-payments-india-reference.md`
  - Currently 0 bytes and always-on. Record the India payments contract, the two payment
    config names, MCC 7392 / purpose code 03, and the `reference_id` rules
  - _Requirements: R1, R6_

## Phase 2 — Unique order subsystem (startable now)

- [ ] 2.1 Add the `ORDERNO#<number> / UNIQUE` conditional reservation
  - _Requirements: R2.3, R2.4_
- [ ] 2.2 Make the failure path fail closed
  - `_get_or_create_wd_order_number`'s exception path currently returns an **unstored**
    number. Remove that path
  - _Requirements: R2.5_ · _Verify: fault-injection test asserting no number on DynamoDB error_
- [ ] 2.3 Resolve-before-generate on `REFERENCE#<metaReferenceId>`
  - _Requirements: R2.6, R2.9_
- [ ] 2.4 Order-number test suite
  - 10,000 generated with zero duplicates; concurrent creation; duplicate Meta event;
    duplicate payment event; retry after timeout; conditional collision; immutability
  - _Requirements: R2.1, R2.7, R2.8_

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
- [ ] R0.10 **Confirm the site id** in the Wix dashboard before Phase 8 writes an order
- [ ] R0.11 Probe installed apps and Invoices/Receipts availability
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

- [ ] 7.1 Confirm the site's catalog version, then bind the adapter to it
  - _Requirements: R5.1_
- [ ] 7.2 Search, query, get product, get variant, check inventory
- [ ] 7.3 Reject any client-supplied price
  - _Requirements: R5.2_ · _Verify: test that a tampered client price is ignored_

## Phase 8 — Cart and checkout

- [ ] 8.1 Backend cart keyed on phone, with revision and TTL
  - _Requirements: R5.3, R5.5_
- [ ] 8.2 Add, update, remove, recalculate, create checkout
  - _Requirements: R5.4_
- [ ] 8.3 Integer-minor-unit money type; no float arithmetic anywhere in the path
  - _Requirements: R6.1_ · _Verify: test asserting no float in the money path_

## Phase 9 — WhatsApp payment request

- [ ] 9.1 Build `order_details` from the live Wix checkout
  - _Requirements: R6.5_
- [ ] 9.2 Enforce exact total equality against the Wix checkout; reject on any difference
  - _Requirements: R6.2, R6.3_ · _Verify: one-paise mismatch is rejected_
- [ ] 9.3 Explicit currency comparison
  - _Requirements: R6.4_
- [ ] 9.4 Reuse the existing `_build_payment_settings`; do not reimplement
  - _Requirements: D1_

## Phase 10 — Reconciliation

- [ ] 10.1 Ordered pipeline exactly as `design.md` specifies
  - _Requirements: R7.1_
- [ ] 10.2 Create-or-resolve Wix order once, guarded by `WIXORDER#<id>`
  - _Requirements: R7.2_
- [ ] 10.3 Await Wix payment reconciliation with bounded backoff
  - _Requirements: R7.6_
- [ ] 10.4 Recoverable failure state; never lose a paid order
  - _Requirements: R7.7_
- [ ] 10.5 Fail closed on amount or currency mismatch
  - _Requirements: R7.8_

## Phase 11 — Wix order transactions

- [ ] 11.1 Record the externally collected payment
  - _Requirements: R7.3_
- [ ] 11.2 Assert no reachable Wix call can charge again
  - _Requirements: R7.4_ · _Verify: an explicit test enumerating the calls this path can make_
- [ ] 11.3 Unique `providerTransactionId`
  - _Requirements: R7.5_
- [ ] 11.4 Determine and document the inventory strategy; prove single decrement
  - _Requirements: R8.1, R8.2, R8.3_ · _Verify: stock before/after a full order is −1, not −2_
- [ ] 11.5 Handle insufficient stock, concurrency, preorder, backorder, multi-location,
      and paid-but-out-of-stock
  - _Requirements: R8.4, R8.5_

## Phase 12 — Billing documents

- [ ] 12.1 `billingDocumentService`: reuse an order-linked Wix document if one exists
  - _Requirements: R9.3_
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
