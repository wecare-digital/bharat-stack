# Phase 2 — direct Meta WhatsApp ingress and message lifecycle

Status: **⚠️ COMPLETE WITH ONE ITEM WAITING ON THE OWNER** · Date: 2026-09-21
Commits `582b609f`, `2067f408`. Deployed and live-verified except the handset QA.

## What was wrong

Phase 2 was not a greenfield build. The ingress already worked; the lifecycle
around it did not, in four specific ways, none of which had any test coverage.

**Status webhooks could move backward.** `_process_status` applied every status
with an unconditional `SET #status = :status`. Meta guarantees neither ordering nor
exactly-once delivery, so the last webhook to arrive won whatever it said. A late
`sent` overwrote `read` — the message reappears as unread. A re-delivered `failed`
overwrote `delivered` — a delivered message shows as failed, and the inbox tooltip
invents a reason for it.

**The row claimed `sent` from the send response.** Four call sites persisted
`status='sent'` the moment Meta returned 200. That response carries a message id
and at most `message_status: "accepted"` — never `sent`. So the row manufactured a
delivery signal from an acknowledgement, and it *masked* the ordering bug, because
the row was never in a state that a real `sent` webhook would advance.

**The 24-hour window was skippable.** The check only ran when a contact row with an
`id` existed, so a send to a bare phone number skipped it — precisely the case most
likely to be outside the window, since there is no record of the customer ever
messaging us. Meta then rejected it with 131047 after we had already decided it was
allowed.

**The internal boundary was a fossil.** The ingress forwarded to the worker inside
a synthetic SNS envelope from an architecture that no longer exists: no topic
subscription in IaC or in the live event-source mappings, and no linked WABA on the
account. It cost a double JSON encode, pointed every reader at a topic that was
never there, and left the boundary untyped — which is why `dlq-replay` stores a
payload it never rebuilds into the shape the worker parsed.

## What changed

| Area | Change |
|---|---|
| Status ordering | `lambda_utils/wa_status.py` ranks the lifecycle; the write carries `statusRank` and an atomic `ConditionExpression`, so concurrent webhooks cannot both pass. Refused transitions log `status_out_of_order_skipped` instead of failing silently |
| Initial status | `WA_INITIAL_STATUS = 'accepted'`. The HTTP response still reports `sent`, deliberately — three frontend call sites use it as a success boolean, and "the API accepted it" is true |
| 24-hour window | Fails closed when there is no contact record; logs `hasContactRecord` so the two cases stay distinguishable |
| Error classification | `graph_errors` wired in — it existed, had ten tests, and was imported by **zero** handlers. Now captures `error_subcode`, `fbtrace_id` and transient-vs-permanent, preferring the per-code `retry` flag that `META_MESSAGE_ERRORS` already carried and nothing read |
| Redaction | Six log sites recorded a customer's phone in cleartext. `mask_phone` was imported in that module and never called once. This function's log group has no retention policy |
| Internal contract | `lambda_utils/wa_internal_event.py`. Flat, typed, entry as a dict. Consumer deployed **before** producer; both shapes accepted while in-flight events and DLQ payloads drain |
| Stage prefix | One implementation in `lambda_utils/http_path.py`, including the bare `/{stage}` case that only url-shortener handled. Three call sites, zero hand-rolled copies |
| Docs | `webhooks.md` and `SECURITY_CHECKLIST.md` claimed GET verification and signature checking were "AWS-managed". That is how an auditor concludes signature checking is somebody else's job — close to how `/whatsapp/inbound` came to accept unsigned webhooks |
| Frontend | `accepted` tick class, dimmer than `sent`, so the new state reads as the weaker claim it is |

## Evidence

Gates: python **1351**, frontend **29**, typecheck clean, provider policy **8/8**,
route audit 326 routes / **0 OPEN**, live auth probes **12/12**, zero Lambda errors.

Deployed, all `Active` with live sha matching `$LATEST`: `inbound-whatsapp` v40,
`whatsapp-calling` v13, `outbound-whatsapp` v18, `stack-wecare-url-shortener` v5.

The internal contract was verified on the live alias with three inert probes — an
entry with no changes, so the loop body iterates nothing:

```text
typed        -> 200  itemCount 1  shapes ["typed"]       processed 0
legacy-sns   -> 200  itemCount 1  shapes ["legacy-sns"]  processed 0
unrecognised -> 200  itemCount 0  inbound_unrecognised_event  no crash
```

CloudWatch also shows a production invocation at 08:08:09, minutes before the
cutover, still on the old `recordCount` log line — so real traffic was using the
legacy shape right up to the deploy, which is why the compatibility arm exists.

## Not done, and why

**Handset QA is `WAITING_FOR_OWNER`.** The brief's exit criterion is one controlled
handset → webhook → inbox → reply → final `wamid` round trip. That needs a QA
recipient the owner nominates; sending to a real customer to prove our own
deployment is not acceptable. Unblock: nominate a number, then
`WA_LIVE_SMOKE_TEST` and `WA_QA_RECIPIENT` — neither of which exists in source yet,
tracked in the feature-flag register.

**Three known gaps, recorded rather than half-fixed:**

- The timeout-guard DLQ path still stores `{'messages': [...]}`, which
  `wa_internal_event.parse()` rejects, so replaying one of those does nothing. The
  record-level path is fixed; this one needs the surrounding `value` context to
  rebuild a valid entry.
- `whatsapp-business-api` carries a **second** webhook verifier that fails **open**
  when no secret is configured (`tests/test_business_api.py:43-46` pins that
  behaviour). The calling handler fails closed. Two implementations, opposite
  defaults.
- `_validate_webhook_timestamp` fails **open** on a malformed timestamp, so a
  replay guard can be bypassed with an unparsable value.

**Legacy arm retirement.** `parse()` reports the shape it saw. Once
`shapes` shows no `legacy-sns` for a full DLQ retention period, the legacy arm and
its tests can go.
