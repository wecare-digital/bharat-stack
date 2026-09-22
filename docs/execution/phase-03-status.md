# Phase 3 — the fresh connected-call notification domain

Status: **✅ COMPLETE, held behind a disabled flag** · Date: 2026-09-21
Commits `e27b9475`, `65b75a3b`.

## What was actually wrong

Not "the notification subsystem needs rebuilding" in the abstract. Eight producers
existed across four Lambdas, and **seven of them fired on something that is not a
connection**. Measured over 14 days before a line was written:

| Producer | Trigger | Firings | Compliant |
|---|---|---:|---|
| `plivo-answer` post-call SMS | **hangup** | **32** | no |
| `plivo-answer` dial-events | `DialAction=connected` | **0** | yes |
| `whatsapp-calling` wd_menu | `connect` (call setup) | **0** | no |
| `whatsapp-calling` disconnect SMS | `terminate` | **0** | no |
| `whatsapp-calling` post-call reaction | `terminate` | **0** | no |
| `whatsapp-calling` post_call_sip | Asterisk AGI | **0** | no |
| `voice-in-c2c` CDR | CDR ingest | **0** | no |
| `voice-in-obd` CDR | CDR ingest | **0** | no |

Those zeros are trustworthy rather than an empty log group: `wecare-whatsapp-calling`
produced **12,180** lines in the window, of which 1,397 were `webhook_received` and
1,396 were message forwards.

**So the only connected-call notification reaching real customers was triggered by
hangup, and the one correct path had never run once.** Its claim table,
`PstnNotificationDelivery`, was declared in four places and existed in none of the 66
live tables, so every attempt raised `ClaimStoreUnavailable` and the route answered 503.

## Three defects, fixed where each occurred

**Recipient.** `handle_connected` parsed `Direction` and then chose `event.caller`
unconditionally, with a comment asserting `From` is the caller. True inbound; on an
outbound Plivo dial `From` is our own CLI. A connected outbound call would have texted
`+919330994400` — our own number, billed to us, under our own registered DLT sender.
The live hangup path had the identical bug.

Direction is now the rule and a business-number registry is the backstop. Both, because
they fail differently: a wrong `Direction` from the provider defeats the rule but not the
registry, and an unregistered number defeats the registry but not the rule. A missing
`Direction` is a refusal, not a guess — guessing inbound texts our own number on every
outbound call, guessing outbound texts the agent endpoint on every inbound one.

**Durability.** Claim, then dispatch. A crash between the two left a claim nothing
owned; the provider's redelivery found it taken and did nothing, so the notification was
lost silently with no alarm. The RCS channel had that shape *by design* — claimed, logged
`plivo_rcs_deferred`, and no worker was ever built. The claim and the job are now one
`TransactWriteItems`.

**Existence.** Declarations removed from `backend.ts` and `data/resource.ts` per
`NOTIF-STORE-001` rather than materialised. `audit_data_model_drift.py` confirms the name
has left `MISSING` entirely.

## What was built

`lambda_utils/notifications/` — seven modules, each documenting the failure it prevents:
`events` (the normalized `ConnectedCallEvent` and its two adapters), `keys` (v2 parent
and per-channel claims), `policy` (per-channel eligibility, provider, template),
`states` (the ten-state machine), `store` (four tables, atomic claim-plus-publish),
`suppression` (watermark and legacy ledger), `service` (the single entry point),
`worker` (leases, sends, records).

Producers cannot get the trigger wrong because they never touch it:
`service.handle_connected_call(params)` is the whole interface, and the only route to it
for a Plivo callback is the adapter.

### Meta is deliberately not wired up

`from_meta_call_event` refuses every event. The official
`cloud-api/calling/call-events` page was unreachable on 2026-09-21, and the account has
delivered **zero** call events in 14 days. `connect` is call setup and `terminate` is a
disconnect — both named by the brief as non-triggers. The brief forbids inventing a
webhook event, so the allowlist is empty and the reason is recorded in
`events.META_TRIGGER_NOTE`. **Unblock:** read the official schema back, confirm which
state proves remote-party connection, then add that one event.

## Two design bugs the tests caught, not review

**The retry edge.** `LEASED → READY` is deliberately backwards on the ladder. The first
draft applied the rank-forward rule to every transition, so a transient retry was refused
as `out_of_order`. In production that strands every retryable delivery at `LEASED` until
its lease expires, then again, forever, with no terminal state and no alarm. Rank cannot
express "backwards but intended", so the two intended edges are enumerated in
`REWIND_EDGES` — enumerated rather than inferred, because a rule like "any move to READY
is a rewind" would also admit `DELIVERED → READY`, which is losing a delivery
confirmation.

**Sendable is narrower than not-terminal.** After a successful send the delivery is
`ACCEPTED`, which is *not* terminal because `DELIVERED` and `READ` follow it — so a
"not terminal, attempts remaining" check treated an already-sent channel as work to do
and sent it again. With SQS at-least-once that is the normal case, not an edge case.
`SENDABLE_STATES` is now `{PENDING, READY, LEASED}`, excluding `ACCEPTED` because the
provider already has it and `RECONCILIATION_REQUIRED` because it is actionable by a
reconciler, not by the sender.

## The three dispositions

A failed send is not one thing, and the distinction is the difference between a duplicate
and a dropped message:

| Disposition | Meaning | Action |
|---|---|---|
| `RETRY` | definitely not sent — throttled, refused pre-transmission | back to `READY`, bounded backoff |
| `RECONCILE` | **may** have been sent — timeout, reset connection | `RECONCILIATION_REQUIRED`, alarms, nothing resends |
| `PERMANENT` | cannot succeed — bad destination, missing DLT, unapproved template | `FAILED` immediately |

Ambiguity is tested **first**: several ambiguous errors also contain a retryable-looking
word (a `ReadTimeout` against a throttled endpoint), and reading that as a plain retry is
the duplicate-send path.

## Evidence

Provisioned and read back by `scripts/provision_notification_domain.py --verify`:

```text
4 tables ACTIVE, correct keys and GSIs, TTL on expiresAt, PITR enabled, 0 rows
queue + DLQ, redrive maxReceiveCount 3, visibility 300s, depth 0
lease 300s == queue visibility 300s
wecare-notification-worker Active, timeout 120s < lease 300s
event source mapping state Disabled, batch 10, ReportBatchItemFailures
PSTN_CONNECTED_NOTIFICATIONS_ENABLED (absent)
```

Live table count 66 → **70**. Deployed: `wecare-plivo-answer` v10 → **v11**,
`wecare-notification-worker` v1 → **v2**, both Active.

Live probes on `:live`, all inert, no `FunctionError`:

```text
action=status  -> enabled false, suppressesEverything true, watermark 0,
                  verifiedSenders [], metaTriggerNote present
action=sweep   -> {"swept": 0, "reason": "feature_disabled"}   refuses, does not scan
junk event     -> 400, no crash
ghost jobId    -> {"handled": false, "reason": "orphan_job"}    never sent
unsigned POST /plivo/dial-events -> 401   the signature gate still holds
```

Gates: pytest **1648** (1351 at Phase 2 start), typecheck clean, frontend 29, provider
policy 8/8, route audit 326 routes / 0 OPEN / 0 DANGLING / 0 UNRESOLVED, live auth probes
17/17.

## Held off, and why each default is the safe one

| Control | Value | Failure direction |
|---|---|---|
| `PSTN_CONNECTED_NOTIFICATIONS_ENABLED` | **absent** | off means no rows written at all, not merely no sends |
| `NOTIF_CUTOVER_WATERMARK` | **absent** | absent means *suppress everything* — an operator who enables the domain without setting it gets zero sends, not a backfill to every caller in the retention window |
| `NOTIF_WA_VERIFIED_SENDERS` | **empty** | an unverified template yields `SKIPPED`, never a rejected send |
| `SINCH_RCS_ENABLED` | absent | India RCS `SKIPPED/UNSUPPORTED`; never a downgrade to another provider |
| SQS event source mapping | **Disabled** | cutover is an explicit reversible step with its own record |
| `POST_CALL_SMS_ENABLED` (legacy) | **true** | the only follow-up customers actually get; retiring it before the replacement is live removes a real touchpoint and delivers nothing in its place |

## Not done

**The reconciler.** `RECONCILIATION_REQUIRED` rows are recorded and alarmed but nothing
resolves them against the provider yet. That needs a per-provider message-status lookup
(Meta `wamid` status, AWS EUM delivery receipt, Sinch receipt), and it is only reachable
once the domain is enabled. Tracked for Phase 5/10 alongside the dashboards.

**Legacy producer retirement.** Six of the seven prohibited producers fired 0 times, so
gating them off is provably zero-impact — but executable retirement is Phase 9 behind a
manifest with archive and rollback. `docs/notification-retirement-manifest.md` is open
with the measurements, dispositions and preconditions.

**`CallNotificationsTable`** is live with one writer and zero readers. Snapshot and
removal is Phase 9, A4 gate.

**Handset QA** remains `WAITING_FOR_OWNER` — the exit criterion needs a QA recipient the
owner nominates, and the same block applies to Phase 2.
