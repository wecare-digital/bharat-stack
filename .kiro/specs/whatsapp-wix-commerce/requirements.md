# Requirements — WhatsApp + Wix Headless conversational commerce

Spec-Driven Development artifact. This is the document the prompt calls `spec.md`; it uses
Kiro's canonical spec filename so the spec is drivable from the IDE.

Phase 0 capability discovery is recorded separately in
[`docs/compatibility.md`](../../../docs/compatibility.md) and is a prerequisite for
everything below. Read it first — three of the prompt's stated baselines did not survive
verification.

## Baseline corrections from Phase 0

The prompt supplied baselines to verify at execution time. Verification changed three:

| Prompt baseline | Verified position | Why |
|---|---|---|
| `META_GRAPH_API_VERSION=v26.0` | **`v25.0`**, configurable, upgrade gated behind a contract test | This repo moved off v22.0 to v25.0 and recorded that v26.0 blocked a batch of commerce calls. Adopting v26.0 on a prompt's say-so would regress a known-good path. |
| Astro storefront | **Next.js 16 static export**, already live | A second frontend framework buys nothing and splits the build. Non-goal. |
| Wix permanent API key acceptable | **OAuth `client_credentials` required** | Wix documents client credentials as the recommended mechanism for headless admin operations. The current API-key path is retained only as a migration fallback. |

`nodejs24.x` survived verification: it is GA, LTS to approximately April 2028, and is the
correct choice for new TypeScript functions — at the cost of introducing a second runtime
into a 64/64-Python fleet.

## Goals

Let a customer messaging `+919330994400` browse a Wix catalog, build a cart, pay inside
WhatsApp, and receive exactly one order with exactly one charge, a billing document, and a
tracking link — with a staff-facing view of every order, payment, reconciliation attempt
and shipment.

## Non-goals

- A second frontend framework. The existing Next.js 16 static export is the storefront and
  the admin shell.
- Replacing the homegrown invoice engine. It has five tables, a per-FY statutory sequence
  and GSTIN/HSN fields; Wix Invoices does not.
- Rotating, revoking or reading any provider credential value. `MANUAL_OWNER_ACTION`.
- Any WhatsApp number, WABA, phone-number-ID or business-portfolio mutation. Prohibited.
- Enabling any live-send flag. Prohibited.
- Native app packaging. Post-project.

---

## R0 — Wix credential ✅ RESOLVED 2026-09-26

**Closed.** The owner supplied an admin API key and it is stored, verified and live.

| Step | Evidence |
|---|---|
| Key stored | `sync_pasted_credentials.py`, staging file shredded; `versionCount: 1`, `holdsValue: true` |
| Provider accepts it | `check_secrets_live.py --only wix` → `VALID`, Catalog V3 answered |
| Function pointed at it | `WIX_API_KEY_SECRET` added to `wecare-wix-store` |
| Kill switch cleared | `WIX_CREDENTIALS_DISABLED` removed (`wasDisabled: true` → `false`) |
| Reached production | v22 published, `live` alias moved from v21; rollback `update-alias … --function-version 21` |
| End-to-end proof | Direct invoke of `wecare-wix-store:live` returned 3 real products (Viveka ₹599, Paperwork ₹3499, File Assist ₹6999), all in stock |
| Recovery copies | `secrets_backup.py` refreshed local + S3 SSE-KMS, both verified |

**Catalog V3 is now `LIVE`-verified, not inferred** — 7 products, 1 category via
`/stores/v3/products/query`. This closes the prompt's §0.6.

### ⚠️ Carried forward: this key must be rotated

It was pasted into a chat transcript, so it is in `~/.kiro/logs` and the session history.
`docs/wix-headless.md` records the previous key being burned the same way. Rotation is
owner-only and is the one remaining credential action:

```
python scripts/set_wix_credential.py --verify        # mint new key, store, prove
# then revoke the old key in the Wix dashboard, second, so there is no keyless window
```

### ⚠️ Unresolved: site-id discrepancy

`/site-list/v2/sites/query` reports **exactly one** site on the account:

| Site id | Name | Published | Configured here |
|---|---|---|---|
| `c17b0e20-d96d-4fa1-b05c-bc97c04b4ac5` | WECARE.DIGITAL | `false` | no |
| `fcd82f0c-9572-49c7-acfb-88fb05042ece` | — | — | **yes** (owner-supplied Headless Site ID) |

Both ids return the same 7 products, but category counts differ (1 vs 4), so the
`wix-site-id` header is honoured rather than ignored. The reading consistent with
`docs/wix-headless.md` is that `c17b0e20` is the retired Editor site — unpublished, more
legacy categories — and `fcd82f0c` is the headless project, which `site-list` does not
enumerate.

`fcd82f0c` is retained: the owner named it, the repo and live env agree, and it serves the
catalog. **The owner SHALL confirm in the Wix dashboard which id is the live headless
project before Phase 8 (cart/checkout) writes any order.** Reading a catalog from the wrong
site is recoverable; creating orders against it is not.

### Remaining acceptance criteria (R0 successor work)

1. ✅ The credential SHALL be stored without ever appearing in argv. Met via the staging
   file path, which takes a PATH as its only argument.
2. ⏳ The permanent API key SHALL be replaced by the OAuth `client_credentials` grant via
   `python scripts/set_wix_credential.py --client-secret --verify-oauth`. The API key is
   preserved alongside it so the new mechanism can be proven before the old is dropped.
3. ⚠️ The current key SHALL be rotated, because it was disclosed in a chat transcript.
4. ⚠️ The site id SHALL be confirmed against the Wix dashboard before any order is written.
5. ⏳ Installed apps and Invoices/Receipts availability remain unverified and SHALL NOT be
   reported as available until probed.

**Note for future credential work.** Wix displays an API key or client secret exactly once,
at creation, and there is no read-back API — so a lost value is unrecoverable and a
disclosed value is unfixable except by rotation.

---

## R1 — Configurable vendor versions

**User story.** As a maintainer, I need the Meta Graph version to live in one place so a
version bump is a config change, not a code migration.

Currently `v25.0` reaches the runtime three ways: an env var with a default (9 files), a
hard-coded module constant with no override (7 files), and a literal inside a URL string
(3 files, including the payment-lookup call).

**Acceptance criteria**

1. The system SHALL resolve the Graph version from a single configuration source.
2. No request URL SHALL contain a hard-coded version literal.
3. WHEN the configured version is not of the form `v<major>.<minor>` THEN configuration
   validation SHALL fail at startup.
4. The system SHALL expose configured-vs-latest for Graph version, Lambda runtime, Wix API
   families, Wix catalog version and SDK versions on an authenticated admin surface.
5. A version bump SHALL NOT be deployed to production without a passing contract test.

---

## R2 — Exactly one immutable business order number

**User story.** As the business, I need every order to carry a globally unique,
never-reused, never-changing customer-facing number that survives retries and duplicate
webhooks.

An order-number generator already exists (`WD-ORD - <UUID8> - <DD-MM-YYYY> - <HH:MM:SS> -
IST`) but it has two defects for this purpose: it is **generated per call with no
uniqueness marker**, so a retry produces a different number, and its fallback path returns
an unstored number on DynamoDB failure — the one case where collision protection matters
most.

**Acceptance criteria**

1. The order number SHALL be globally unique, immutable and never reused.
2. It SHALL NOT be derived from phone number alone, nor timestamp alone.
3. WHEN a candidate is generated THEN a uniqueness marker `PK=ORDERNO#<number>`,
   `SK=UNIQUE` SHALL be written with `ConditionExpression: attribute_not_exists(PK)`
   **before** the number is accepted.
4. WHEN that conditional write fails THEN a new candidate SHALL be generated and retried,
   and the existing number SHALL NOT be overwritten.
5. WHEN DynamoDB is unavailable THEN order creation SHALL fail; the system SHALL NOT return
   an unreserved order number.
6. WHEN the same Meta payment notification is delivered more than once THEN all deliveries
   SHALL resolve to the same existing order and the same number.
7. WHEN order creation is retried after a Lambda timeout THEN the number SHALL be unchanged.
8. 10,000 generated numbers SHALL contain no duplicate.
9. The Meta `reference_id` SHALL be a distinct identifier mapped to the order, never the
   order number itself.

---

## R3 — Webhook ingestion integrity

**Acceptance criteria**

1. WHEN a `GET` verification request arrives THEN the system SHALL echo `hub.challenge`
   only after `hub.verify_token` matches.
2. WHEN a `POST` arrives THEN `X-Hub-Signature-256` SHALL be verified against the **raw**
   body using HMAC-SHA256 with a timing-safe comparison.
3. WHEN signature verification fails THEN the payload SHALL be rejected, not enqueued, and
   a `WebhookSignatureFailed` metric SHALL be emitted.
4. The system SHALL validate, normalize, register an idempotency key, enqueue, and
   acknowledge — without waiting for Wix.
5. Acknowledgement SHALL NOT imply reconciliation succeeded.

---

## R4 — Idempotency

**Acceptance criteria**

1. Uniqueness SHALL be enforced by conditional writes or `TransactWriteItems`, never by
   read-then-write.
2. Every externally visible side effect SHALL be retry-safe: at most one Wix order, one
   payment record, one billing document, one customer confirmation per business event.
3. The existing `WebhookDedup` table and the `shared/lambda_utils/idempotency.py` /
   `webhook_dedup.py` primitives SHALL be reused rather than duplicated.
4. WHEN an admin triggers a manual retry THEN it SHALL be idempotent.

---

## R5 — Catalog, cart and checkout

**Acceptance criteria**

1. Product data SHALL come from Wix Stores Catalog V3, subject to R0 confirming the site's
   catalog version.
2. Price SHALL NEVER be taken from a WhatsApp or browser client; it SHALL be read from Wix.
3. The cart SHALL be backend-managed and keyed to the customer's phone, not to a browser
   session — WhatsApp customers have no cookie jar, so `currentCart` semantics do not apply.
4. The system SHALL support add, update quantity, remove, recalculate, and create checkout.
5. WHEN a cart is idle beyond its TTL THEN it SHALL expire without creating an order.

---

## R6 — Money and payment request integrity

**Acceptance criteria**

1. All monetary values SHALL be integer minor units. Floating-point money is prohibited.
2. WHEN a payment request is built THEN `items + tax + shipping + fees − discounts` SHALL
   equal the authoritative Wix checkout total exactly.
3. WHEN the computed total and the Wix checkout total differ by any amount THEN the payment
   request SHALL be rejected and no `order_details` message SHALL be sent.
4. Currency SHALL be compared explicitly, not assumed to be INR.
5. The payment payload SHALL be built from the live Wix checkout, never from cached prices.

---

## R7 — Payment reconciliation

**Acceptance criteria**

1. WHEN Meta reports a confirmed payment THEN the system SHALL verify the signature, check
   idempotency, resolve `reference_id`, load the internal order and the authoritative
   checkout, and compare currency, amount and customer before mutating anything.
2. A Wix order SHALL be created or resolved **exactly once** per business order.
3. The externally collected payment SHALL be recorded against that order via the Wix Order
   Transactions API.
4. The system SHALL NOT call any Wix API that would charge the customer again. Recording a
   payment is not collecting one.
5. `providerTransactionId` SHALL be treated as unique.
6. WHEN Wix has not yet reconciled the payment state THEN the flow SHALL wait and retry
   rather than proceeding.
7. WHEN Wix is unavailable after a captured payment THEN the order SHALL enter a
   recoverable state, SHALL NOT be lost, and SHALL be retryable to completion.
8. WHEN amount or currency mismatch THEN reconciliation SHALL fail closed and raise for
   staff attention; it SHALL NOT silently accept.

---

## R8 — Inventory adjusted once

**Acceptance criteria**

1. Inventory SHALL be decremented exactly once per order.
2. The system SHALL prefer the Wix order lifecycle's own inventory adjustment and SHALL NOT
   also decrement manually unless a documented multi-location flow requires it.
3. The selected strategy SHALL be stated explicitly in `design.md`.
4. The system SHALL handle insufficient stock, concurrent purchase of the last unit,
   preorder, backorder, multi-location inventory, and payment-succeeded-but-stock-gone.
5. WHEN stock is unavailable after capture THEN the customer SHALL NOT be charged twice and
   the case SHALL surface to staff with a refund path.

---

## R9 — Billing document, generated once

**Acceptance criteria**

1. A billing document SHALL be produced only after payment is confirmed **and** Wix
   reconciliation has completed.
2. The system SHALL NOT create a standalone Wix invoice that could produce a second
   payable eCommerce order.
3. WHEN Wix has produced an order-linked document THEN it SHALL be reused rather than
   duplicated.
4. Exactly one billing document SHALL exist per order, across retries.
5. The system SHALL persist `billingDocumentType`, `invoiceId`, `invoiceNumber`,
   `receiptId`, `documentStatus`, `documentUrl`, `generatedAt`, `sentAt`, `viewedAt`.
6. WHEN generation fails THEN it SHALL be retryable without producing a second document.

---

## R10 — Customer notification and document delivery

**Acceptance criteria**

1. Confirmation SHALL be sent from `+919330994400` and SHALL include order number, payment
   confirmation, amount, items, order status, tracking link and billing-document link.
2. A permanent unrestricted Wix document URL SHALL NEVER be exposed.
3. WHEN the Wix document URL is temporary THEN the document SHALL be proxied through an
   authenticated API or copied to a private S3 object served by a short-lived signed URL.
4. WHEN confirmation delivery fails THEN it SHALL be retryable, and retry SHALL NOT produce
   a duplicate customer-visible message for the same event.
5. Live sends SHALL be restricted to the owner-nominated QA recipient until production
   sending is separately authorized.

---

## R11 — Customer tracking page

**Acceptance criteria**

1. Order data SHALL NOT be retrievable using the order number alone.
2. Access SHALL require an opaque 256-bit cryptographically random tracking token.
3. Only a secure representation of the token SHALL be stored; a token SHALL NOT be
   recoverable from storage.
4. WHEN a token is invalid or expired THEN the response SHALL be indistinguishable from a
   token for a non-existent order.
5. The page SHALL display order number, created date, items, quantities, payment status and
   date, billing-document status, fulfillment status, carrier, tracking number, tracking
   link, and the event timeline.
6. Token validation SHALL occur in a Lambda. The frontend is a static export with no
   server, so it cannot validate anything.

---

## R12 — Internal admin surface

**Acceptance criteria**

1. Admin routes SHALL require authentication, with MFA for privileged production
   administrators where practical.
2. The order detail view SHALL show one consolidated record: business order id and number,
   customer, WhatsApp phone, Wix cart/checkout/order ids and number, Meta reference and
   message ids, payment provider and transaction id, payment status, invoice/receipt ids,
   fulfillment id, carrier, tracking number, current state, timestamps, full timeline,
   reconciliation attempts and error history.
3. Staff SHALL be able to retry reconciliation, retry confirmation, retry billing-document
   generation, regenerate a document link, inspect a DLQ reason, and inspect sanitized
   webhook metadata.
4. Every operation exposed SHALL be idempotent.
5. No debugging endpoint SHALL be exposed in production.
6. `AuthorizationType=NONE` on a route SHALL NOT be read as "unauthenticated" — handler
   level auth exists and was observed rejecting an unauthenticated probe. Auth posture
   SHALL be asserted per handler, not inferred from the route.

---

## R13 — Event timeline

**Acceptance criteria**

1. The timeline SHALL be append-only. No event SHALL be mutated or deleted.
2. Each event SHALL carry timestamp, actor, source and correlation ids.
3. The same timeline SHALL back both the customer tracking page and the admin view, with
   the customer view filtered rather than separately computed.

---

## R14 — Fulfillment and shipping

**Acceptance criteria**

1. Fulfillment state SHALL come from the Wix Order Fulfillments API.
2. WHEN fulfillment changes THEN state SHALL be updated, a timeline event appended, the
   tracking page refreshed, and a WhatsApp status update optionally sent.
3. The Meta `order_status` schema SHALL be verified against current documentation before
   sending.

---

## R15 — State machine

**Acceptance criteria**

1. Order state SHALL be explicit and enumerated.
2. Transitions SHALL be applied with conditional writes.
3. An illegal transition SHALL fail safely and SHALL NOT corrupt state.
4. A terminal state SHALL NOT transition further except through an explicit, audited
   staff action.

---

## R16 — Security

Threat model, each requiring a named control in `design.md`: forged webhook, replayed
webhook, duplicate payment, order-number collision, tracking-token guessing, amount
manipulation, currency manipulation, duplicate order, duplicate inventory decrement,
invoice duplication, unauthorized invoice access, PII leakage, leaked Wix client secret,
leaked Meta token, SSRF, XSS, CSRF on admin operations, supply-chain compromise, excessive
IAM permissions.

**Acceptance criteria**

1. No secret SHALL appear in browser JavaScript.
2. No secret SHALL appear in a log line — nor in a logging *expression*, including a
   ternary on a secret's truthiness or a boolean derived from it. Taint is tracked across
   function boundaries and reducing a secret to a bool does not launder it.
3. No secret SHALL appear in a command line, argv, or a maintenance report.
4. Secrets SHALL be read from Secrets Manager at request time, lazily, never at import
   scope — otherwise a rotation does not take effect until every warm sandbox recycles.
5. Card number and CVV SHALL NEVER be stored.
6. IAM SHALL be least-privilege; a bucket ARN SHALL be distinguished from `bucket/*`.
7. Tracking tokens SHALL be short-lived.

---

## R17 — Observability

**Acceptance criteria**

1. Logs SHALL be structured and SHALL carry correlation ids: correlation id, business order
   id and number, Meta message and reference ids, Wix cart/checkout/order ids, provider
   transaction id, invoice/receipt ids, fulfillment id.
2. Metrics SHALL include webhook received / signature failed / duplicate; payment
   requested / captured / failed; order created; duplicate order prevented; Wix and Meta
   API failures; reconciliation retry and failure; billing document generated / failed /
   sent; fulfillment updated; DLQ depth.
3. An alarm SHALL fire on non-zero DLQ depth and on reconciliation failure.
4. Phone numbers SHALL be masked in logs. Note that masking to the last four digits makes
   the QA recipient `…0044` ambiguous with the secondary business number `+919903300044`;
   disambiguation SHALL use direction, channel or delivery id, and masking SHALL NOT be
   widened to resolve it.

---

## R18 — Verification gates

**Acceptance criteria**

1. Lint, typecheck and tests SHALL pass before any deployment.
2. IaC validation SHALL pass before deployment.
3. Contract tests SHALL cover the Meta and Wix integration boundaries.
4. Deployment SHALL follow `update-function-code` → publish version → move the `live`
   alias. A `$LATEST` update alone SHALL NOT be treated as deployed for any function
   carrying a `live` alias.
5. A command exiting zero SHALL NOT be reported as verification of intended behaviour.

---

## Traceability to the prompt's acceptance criteria

The prompt lists 30 criteria in §36. Mapping: 1 → R0/compatibility §2; 2-4 → R1; 5-6 → R0;
7-9 → R2; 10-11 → R7; 12 → R8; 13-14 → R7; 15-16 → R9; 17-19 → R10; 20-21 → R11/R14;
22-24 → R12; 25-26 → R16; 27 → R18; 28 → R1; 29-30 → R18.

Criteria 1, 5 and 6 cannot be satisfied while R0 is open. Criterion 3 is satisfied by
`docs/compatibility.md`, with the correction that the verified version is `v25.0`.
