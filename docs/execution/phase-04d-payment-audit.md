# Phase 4d — Razorpay and Meta India payment audit

Read-only against both providers. No live charge, no capture, no refund, no payment
configuration mutation. All changes are code.

## What the live account actually holds

Measured 2026-09-23, `us-east-1`, account `775261844268`.

| Table | Rows | PITR | TTL |
|---|---|---|---|
| `PaymentsTable` | **0** | ENABLED | off |
| `InvoicesTable` | **0** | ENABLED | off |
| `OrderTable` | **0** | ENABLED | off |
| `FlowSubmissionTable` | **0** | ENABLED | off |
| `RazorpayWebhookLogTable` | **607** | ENABLED | 180d on `expiresAt` |

All 607 logged events are `payment.downtime.started` (327) / `payment.downtime.resolved`
(280), covering 339 distinct downtimes across netbanking (424), UPI (171) and card (12).

**No payment has ever been captured through this webhook.** So there is nothing to
reconcile in the sense of mismatched rows: zero payments, zero invoices, and a webhook log
containing only Razorpay platform-downtime notices. Every money-path defect below is
latent, and the two that are *proven* are proven on downtime — the only live traffic.

That the money tables are empty is also why these fixes ship with no migration.

## Finding 1 — the dedup key silently dropped real events. PROVEN

`CloudWatch /aws/lambda/wecare-razorpay-webhook`, 4 days to 2026-09-23:

| Measure | Value |
|---|---|
| events received | 3030 |
| claimed as duplicates | 1495 |
| dedup keys delivered more than once | 1347 |
| of those, keys whose deliveries carried **different bodies** | **19** |
| distinct events silently dropped (lower bound) | **59** |

The key was `account_id:event_type:created_at`, upgraded to `{entity_id}:{event_type}`
**only when `payload.payment.entity` existed**. Refund, dispute, settlement, payout,
`order.paid`, `invoice.*`, `payment_link.*` and downtime all carry their entity under a
different key, so every one of them used the coarse form.

Razorpay emits one downtime per bank, and banks fail together, so `created_at` is not a
discriminator. One key — `acc_HDfub6wOfQybuH:payment.downtime.started:1790100905` — was
delivered 6 times with two distinct body sizes while our endpoint returned 200 each time.
Different body means different event, so those were distinct downtimes collapsed into one.

Severity: **HIGH**. It is data loss, not a retry being handled. Had a refund and a second
refund of the same payment landed in one second, one would have vanished.

**Fixed.** `payment_status.dedup_key` derives the key from whichever of 17 entity
containers is present. Retries still collapse (`test_a_retry_of_the_same_event_still_collapses`).

## Finding 2 — `_handle_downtime` read a key that does not exist. PROVEN

The entity arrives as `{"payment.downtime": {"entity": {...}}}` — a literal dot in the key.
The handler read `event_data.get('downtime')`, then fell back to
`event_data.get('payment', {}).get('downtime', {})`. Neither key exists.

CloudWatch confirms every one of the 607 events logged `method: ""`, `instrument: "{}"`.
The method, affected bank, severity and scheduled flag — the entire actionable content of a
downtime notice — were discarded on the only payment traffic this account receives.

`_handle_dispute` had the identical defect (`payment.dispute`). No dispute has arrived, so
it was never exercised, but it would have logged an empty dispute for a contested payment.

`_log_webhook_event` shared the root cause: it read only `payload.payment.entity`, so all
607 audit rows stored `amount: 0`, a `status` inferred from the event-type suffix, and **no
entity id at all** — the reconciliation table could not identify which downtime a row was.

Severity: **HIGH** for downtime (exercised 607 times), **MEDIUM** for dispute (latent).

**Fixed.** All three use `payment_status.extract_entity` / `entity_summary`. The audit row
now carries `entityKey` and `entityId`, and `paymentId` is only populated from a genuine
payment entity so `paymentId-index` does not start returning non-payments.

## Finding 3 — payment status was not monotonic, and a redelivery erased refunds

`_store_payment_record` was an unconditional `put_item` of a freshly built record. A
`put_item` replaces the whole item, and that record contains no refund attributes. So a
redelivered `payment.captured` arriving after `refund.processed` both reset the status to
`captured` **and erased `refundId` and `refundAmount`**. The row then read as money kept
when the money had been returned, and nothing reported it.

This is the same defect already fixed for WhatsApp (`wa_status`) and RCS (`rcs_status`),
on the one domain where a backward transition is a financial misstatement.

Severity: **HIGH**, latent (0 rows).

**Fixed.** `payment_status` ladder, persisted as `paymentStatusRank`, enforced as a
`ConditionExpression`:

```
created 10 · pending 20 · authorized 30 · failed 40 · captured 50 · refunded 60 · disputed 70
```

`authorized` sits below `failed` so a stale hold cannot mask a failed capture. `failed`
sits below `captured` so a failed attempt followed by a successful one ends captured.
`refunded` outranks `captured`, which is what makes the erasure impossible. A refused write
logs `payment_status_not_applied` at info — expected, not a fault.

## Finding 4 — one row, two money units

`_store_payment_record` wrote `amount` in paise. `_handle_refund` wrote `refundAmount` in
**rupees** on that same row, with no field name saying which. A reconciliation comparing
them would have been wrong by 100x and nothing would have caught it.

Severity: **MEDIUM**, latent.

**Fixed.** `refundAmountPaise`, via `payment_status.paise` which raises rather than
returning 0 — a silent zero on a refund amount is a reconciliation error that looks like a
successful write.

## Finding 5 — a duplicate invoice consumed a GST sequence number

`create_invoice` deduped with a **table scan**, then a `put_item` whose
`ConditionExpression='attribute_not_exists(invoiceId)'` could never fire because
`invoiceId` was a fresh `uuid4`. A DynamoDB scan is eventually consistent, and two writers
invoke this for the same payment (`razorpay-webhook` and `inbound-whatsapp-handler`), so
both could scan, both miss, and both insert.

`_get_next_invoice_number` *is* atomic, so the loser burned a real sequential number out of
the GST series. A gap in that series is a compliance artifact, not untidy data.

Severity: **HIGH**, latent (0 invoices).

**Fixed.** `invoiceId` is derived from `(referenceId, paymentId)`, and a minimal row is
claimed **before** the sequence is touched, so a losing racer never increments it. The
lost-claim path returns the existing invoice with `deduplicated: true`.

## Finding 6 — a magnitude heuristic guessing a money unit

`payments-read._normalize_payment` computed
`amount_rupees = amount / 100 if amount > 1000 else amount`. That is wrong below ₹10 in
both directions: 500 paise (₹5) reported as ₹500, 999 paise (₹9.99) as ₹999. A magnitude
test cannot recover a unit that was not recorded.

The value was computed and never used, so no response was affected.

Severity: **LOW**, dead code — but one edit from live.

**Fixed.** Removed. The response now carries `amountPaise` (integer) and `amountRupees`
(string, so it cannot be summed by accident). `amountInRupees` is retained and derived from
paise because `src/pages/dm/commerce` reads it; dropping it would have made that page fall
back to `amount` and render ₹250000 for a ₹2500 payment. That page now prefers
`amountRupees`.

## Verified as already correct

- **Razorpay signature.** Raw-body HMAC-SHA256, `hmac.compare_digest`, verified *before*
  `json.loads` so no re-serialisation can break it, and **enforced** — the caller returns
  401. A missing secret returns False, so it fails closed. Secret read lazily from
  `wecare/razorpay-webhook`.`webhook_secret`, never at import, so a rotation takes effect
  without a redeploy.
- **Refund initiation does not exist.** No Razorpay refund endpoint or SDK refund call
  anywhere in `amplify/`. `test_nothing_in_the_tree_can_initiate_a_refund` now asserts it
  continuously. `lambda_utils/audit.py` listing `payment.refund` as an auditable action is
  a control, not a capability, and is asserted separately.
- **Duplicate customer confirmation** is already prevented:
  `_inbound_order_status_enabled()` defaults OFF so `razorpay-webhook` is the sole sender of
  `order_status`.
- `payment.failed` cannot un-pay a paid invoice — its membership test excludes `captured`.

## Gaps left open, with reasons

| Gap | Severity | Why not now |
|---|---|---|
| Meta payment verification defaults to trusting the webhook (`payment_verified = True`), and skips the Payment Lookup entirely when `paymentConfigName` is empty | MEDIUM | Tightening it to fail-closed changes live payment acceptance behaviour. Needs a deliberate decision, and there is no payment traffic to validate against. |
| `_mark_invoice_paid_by_phone_and_amount` picks an invoice by table scan plus `abs(total - rupees) < 0.02` float tolerance | MEDIUM | Reachable only when `referenceId` recovery has already failed. Replacing it needs a real reconciliation design, not a patch. |
| Five different status vocabularies across five tables | MEDIUM | `payment_status.canonical()` now maps all of them on read. Rewriting what each table *stores* is a migration, and with 0 rows it is cheap — but it touches the admin surface and the frontend, so it belongs with Phase 4f. |
| `InvoicesTable.status` document lifecycle (`created/sent/paid/cancelled`) has no rank guard | LOW | It is a different axis from whether money moved, and the money axis is now guarded. |
| GST tax split `cgst = tax/2` loses a half-paise on an odd tax | LOW | Float rupees throughout the invoice engine; correcting it is an invoice-engine rewrite. |
| `_get_next_invoice_number` returns `WD-PAY-TEMP-<uuid>` on sequence failure, injecting a non-sequential number into the GST series | MEDIUM | Should fail the request instead. Behaviour change on an error path with no live traffic to observe. |

## Evidence

- Tests: `tests/test_payment_status.py`, 59 assertions. RED replay against `HEAD~1`:
  **15 of 17 wiring checks fail pre-fix**.
- Suite 1974 → 2035 passed. `tsc --noEmit` clean. Provider policy 8/8. Webhook auth gate
  17/17. Deploy packaging validated for all three functions.
