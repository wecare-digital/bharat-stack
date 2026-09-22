# Notification retirement manifest

Required by the brief before any old notification surface is deleted: exact physical
IDs, ownership, dependencies, archive location, migrated counts, disabled triggers,
delete status and rollback.

Opened 2026-09-21 (Phase 3). **Nothing live has been deleted.** Phase 3 built the
replacement and rewired the compliant producer; the destructive steps belong to
Phase 9 and each needs its own A4 gate.

## What was measured first

CloudWatch Logs Insights, 14 days to 2026-09-21. This is the whole basis for every
disposition below, because the brief's own baseline table was stale and because
"looks unused" is not evidence.

| Producer | Trigger | Firings / 14d | Compliant? |
|---|---|---:|---|
| `plivo-answer` `plivo_post_call_sms_queued` | **hangup** | **32** | no |
| `plivo-answer` `plivo_dial_event` | `DialAction=connected` | **0** | yes |
| `whatsapp-calling` `call_event` (any) | Meta call webhook | **0** | n/a |
| `whatsapp-calling` `call_wa_template_sent` | `connect` (call setup) | **0** | no |
| `whatsapp-calling` `disconnect_sms_triggered` | `terminate` | **0** | no |
| `whatsapp-calling` `post_call_sent` | Asterisk `post_call_sip` | **0** | no |
| `voice-in-c2c` CDR notifications | CDR ingest | **0** | no |
| `voice-in-obd` CDR notifications | CDR ingest | **0** | no |

Sanity checks that make those zeros trustworthy rather than an empty log group:
`wecare-whatsapp-calling` produced **12,180** log lines in the window (1,397
`webhook_received`, 1,396 message forwards to the inbound handler, 14 cert checks);
`wecare-plivo-answer` produced 458 lines including 31 `plivo_hangup` and 10
`plivo_answer`; `voice-in-c2c` 63 lines; `voice-in-obd` 50 lines.

**The finding that mattered:** the only connected-call notification reaching real
customers was triggered by **hangup**, and the one compliant path had never run.

## Dead on arrival — the v1 claim store

`stack-wecare-digital-PstnNotificationDelivery`

| Field | Value |
|---|---|
| Physical table | **never existed.** Absent from all 66 live tables |
| Declared in | `amplify/backend.ts` (TTL_CONFIG), `amplify/data/resource.ts` (model), `lambda_utils/pstn/claims.py` (`CLAIM_TABLE` default), `lambda_utils/pstn/keys.py` (docstring) |
| Readers / writers | `pstn/claims.py` only, via `claim()`, `record_attempt()`, `get()` |
| Consequence | every claim raised `ClaimStoreUnavailable`; `/plivo/dial-events` answered 503 and sent nothing |
| Archive required | **none** — there is no data. This is why `suppression.py` reads `WebhookDedup` instead |
| Migrated count | 0 rows, because 0 rows ever existed |
| Disposition | declarations **deleted** 2026-09-21 per `NOTIF-STORE-001`; not materialised |
| Rollback | `git revert` of the commit; the table never existed, so there is nothing to restore |

Verified by `scripts/audit_data_model_drift.py`: before, `MISSING` listed
`stack-wecare-digital-PstnNotificationDelivery … named by lambda_utils/pstn/claims.py`.
After, it is absent from every category.

## Deleted from source in Phase 3

| Path | Why it could go now | Rollback |
|---|---|---|
| `lambda_utils/pstn/notifications.py` | superseded by `lambda_utils/notifications`; provably non-functional (claim table absent, 0 firings) | `git revert` |
| `lambda_utils/pstn/claims.py` | existed only to back the above against a table that never existed | `git revert` |
| `lambda_utils/pstn/keys.py` | v1 key derivation; v2 lives in `notifications/keys.py`, which retains `legacy_v1_*` for suppression | `git revert` |
| `tests/test_pstn_connected_notifications.py` | subject deleted; every behaviour re-asserted in `tests/test_notifications_domain.py` | `git revert` |
| `tests/test_pstn_claims.py` | subject deleted; fail-closed contract re-asserted in `TestStoreFailsClosed` | `git revert` |
| `plivo-answer._dispatch_notification` | sent SMS synchronously inside the signed webhook and left RCS permanently `PENDING` for a worker that was never built | `git revert` |

No AWS resource was deleted for any of these.

## Still live, retirement deferred to Phase 9

### `plivo-answer` post-call SMS — the one with real traffic

| Field | Value |
|---|---|
| Trigger | `/plivo/hangup` and the `/plivo/answer` hangup pass — **prohibited** by the brief |
| Volume | 32 sends in 14 days |
| Idempotency | `WebhookDedup` key `<CallUUID>:postcall`, **fails open** on a store error |
| Flag | `POST_CALL_SMS_ENABLED`, deployed **`true`** on `wecare-plivo-answer:11` |
| Why still on | it is the only follow-up customers actually receive. Silencing it before the replacement is enabled removes a real customer touchpoint and delivers nothing in its place |
| Changed in Phase 3 | recipient now resolved by `_external_party()` — direction-aware, and refuses a business number. Previously passed `params['From']` regardless of direction |
| Retirement precondition | `PSTN_CONNECTED_NOTIFICATIONS_ENABLED=true` with a watermark set, QA round trip passed, then flip `POST_CALL_SMS_ENABLED=false` and observe |
| Rollback | set `POST_CALL_SMS_ENABLED=true`; `aws lambda update-alias --function-name wecare-plivo-answer --name live --function-version 10` |

### `stack-wecare-digital-CallNotificationsTable`

| Field | Value |
|---|---|
| Status | **live**, in the account |
| Writers | exactly one: `whatsapp-calling/_send_call_whatsapp_notification`, unconditional `put_item` |
| Readers | **zero** anywhere in the repo |
| Nature | a log, not a claim. `whatsappWaba1: 'sent'` is hardcoded regardless of outcome, and the unconditional put overwrites on a duplicate webhook |
| TTL | writes a `ttl` attribute but has no entry in `backend.ts` TTL_CONFIG, so the attribute is likely inert |
| Archive required | yes — snapshot + checksum before deletion, even though its only writer has fired 0 times in 14 days |
| Disposition | Phase 9, A4 gate. Not touched in Phase 3 |

### `whatsapp-calling` producers (4) and `voice-in` CDR producers (2)

All six fired **0** times in 14 days, so gating them off is provably zero-impact on
live traffic — but they are not Phase 3's deliverable, and the brief puts executable
retirement in Phase 9 behind a manifest. Recorded here; unchanged in Phase 3.

Dead code found alongside them, with **no call site anywhere**:
`_send_incoming_call_sms`, `_send_ivr_menu`, `_sms_sent_recently`. The last is the
read half of a suppression window whose writes still happen, so that window has never
functioned.

## Suppression and the cutover watermark

The v1 → v2 key change would re-notify anyone already served, so
`notifications/suppression.py` gates on two things:

1. `NOTIF_CUTOVER_WATERMARK` — calls connecting before it are never notified.
   **Absent in production**, and absent means *suppress everything*, so an operator
   who enables the domain without setting it gets zero sends rather than a backfill.
2. The legacy ledger — `WebhookDedup` key `<canonicalCallId>:postcall`, which is where
   those 32 real sends recorded themselves. An unreadable ledger also suppresses.

`PstnNotificationDelivery` is deliberately **not** consulted: it has no rows, so a
check against it would be a check against an empty set — worse than useless, because
it would look like due diligence.

## Reconciliation of AWS against IaC

Created by `scripts/provision_notification_domain.py`, read back by its `--verify`:

| Resource | Keys | Indexes | TTL | PITR |
|---|---|---|---|---|
| `…-NotificationEvents` | `eventClaimKey` | `canonicalCallId-index` | `expiresAt` | enabled |
| `…-NotificationDeliveries` | `deliveryId` | `eventClaimKey-index`, `state-createdAt-index` | `expiresAt` | enabled |
| `…-NotificationAttempts` | `attemptId` | `deliveryId-at-index` | `expiresAt` | enabled |
| `…-NotificationOutbox` | `jobId` | `status-availableAt-index` | `expiresAt` | enabled |
| `…-notification-queue` | — | redrive → dlq, maxReceiveCount 3 | retention 1d, visibility 300s | — |
| `…-notification-dlq` | — | — | retention 7d | — |

Live table count 66 → **70**. All four at **0 rows**; queue depth **0**. PITR is
enabled on all four because the brief requires a restorable snapshot before retiring
any notification table, and requires restoring notification state without duplicate
sends as a disaster-recovery exercise — neither is possible without it.

`--verify` also cross-checks `store.LEASE_SECONDS` against the queue's
`VisibilityTimeout` (both 300s). They must agree: a visibility timeout shorter than
the lease redelivers a message whose lease is still held, and a lease shorter than the
timeout lets a second worker take a job the first is still running. Either way the
channel sends twice.

## Not done, and deliberately

- No broad delete by naming pattern.
- No secret deleted, cancelled or rescheduled.
- No WhatsApp number, WABA, phone-number id or subscription touched.
- `CallNotificationsTable` retained pending its Phase 9 archive.
- The outbox **worker** is not built yet: the domain claims and publishes, and with the
  flag off it does neither. Building the worker is the remainder of Phase 3.
