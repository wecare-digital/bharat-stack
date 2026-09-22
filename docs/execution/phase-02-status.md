# Phase 2 — direct Meta WhatsApp ingress and message lifecycle

Status: **⚠️ COMPLETE WITH ONE ITEM WAITING ON THE OWNER** · Date: 2026-09-21
Commits `582b609f`, `2067f408`, plus the closing pass below. Deployed and
live-verified except the handset QA, which needs a QA number only the owner can
nominate.

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

**One gap still open.** The timeout-guard DLQ path stores `{'messages': [...]}`,
which `wa_internal_event.parse()` rejects, so replaying one of those does nothing.
The record-level path is fixed; this one needs the surrounding `value` context to
rebuild a valid entry.

## Closing pass — the three items that were left open

Two were the gaps recorded above. Chasing the second one found a third problem that
was considerably worse than either.

### Live-send lockdown (was: flag does not exist)

`lambda_utils/live_smoke.py` implements `WA_LIVE_SMOKE_TEST` + `WA_QA_RECIPIENT`.

It is a **lockdown, not a permission**, and the direction is the whole design. Off
— the production state — changes nothing. On, the sender refuses every recipient
except `WA_QA_RECIPIENT`. Read the other way round, flag *enables* sending, the
guard's failure mode becomes "send to anyone" and the flag has to be on in
production for normal traffic, which makes it useless as a test switch. Smoke mode
with no QA recipient configured blocks **everything**, so a half-configured switch
yields zero sends immediately rather than an open window.

Enforced twice on purpose. The handler returns `403` right after recipient
resolution, ahead of the typing indicator, the `block_users` branch and every send
branch — so in smoke mode a non-QA handset sees no message, no blue ticks and no
"typing…" bubble. `_send_direct_api` repeats the check at the wire, and that one is
the guarantee: a branch added later that forgets the first still cannot reach a
customer. `blockUsers` gets its own check, being an arbitrary list rather than the
resolved recipient.

Consequence to keep in view: turning this on in production halts customer
messaging. Correct direction for a safety switch to fail, but it is why both
variables are confirmed **absent** on `wecare-outbound-whatsapp:19`.

### Replay window (was: fails open on a malformed timestamp)

`_validate_webhook_timestamp` wrapped its whole traversal in one
`except (ValueError, TypeError)` that returned `True`, commented "fail open on parse
errors — don't block legitimate events". Two consequences:

1. Corrupting the timestamp bypassed the 5-minute window completely. A replayer
   holding a captured signature-valid payload only had to make the field
   unparsable. A replay guard the replayer can switch off is not a replay guard.
2. Because the `try` wrapped the traversal rather than a single parse, one malformed
   value aborted the loop — so a payload with a malformed timestamp in entry 1 and a
   genuinely stale one in entry 2 was accepted without the stale one being examined.

Each timestamp is now judged independently: **absent** allowed (Meta really does
omit it), **unreadable** rejected, **stale** rejected, **far-future** rejected
beyond one window of clock skew, since a future stamp never expires and would let
one captured event replay forever.

The first draft of this fix was a net regression and the RED proof caught it:
tolerating unexpected container shapes by *skipping* them turned a noisy
AttributeError/500 into a silent accept for `calls` as an object wrapping a stale
timestamp. Unwalkable containers are now rejected, and `calls` as a single object is
read as one call.

Proof, old code loaded straight out of git next to the new:

```text
case                                            OLD             NEW
corrupted timestamp (the replay bypass)    ACCEPTED        rejected
corrupt entry hides a stale entry          ACCEPTED        rejected
calls as an object wrapping a stale ts     AttributeError  rejected
entry as an object, not a list             AttributeError  rejected
far-future timestamp (never expires)       ACCEPTED        rejected
body is None                               AttributeError  rejected
genuinely absent (must stay allowed)       ACCEPTED        ACCEPTED
fresh (must stay allowed)                  ACCEPTED        ACCEPTED
empty body (must stay allowed)             ACCEPTED        ACCEPTED
```

### `SEC-ROUTE-009` — three unauthenticated routes that could stop or hijack all inbound WhatsApp

Severity **CRITICAL**. Found while checking the second gap; not in the brief.

The second verifier turned out to have **zero call sites** — so its fail-open was a
trap rather than a live hole. The live hole was next door.
`wecare-whatsapp-business-api` was deployed with
`AUTH_SKIP_PATHS="/wa-business/webhooks,/wa-business/flow-data"`, and `require_auth`
matched with `skip.strip() in path`, a bare substring test. `/wa-business/webhooks`
is **not** a Meta callback despite the name and the code comment claiming it
"authenticates via verify token". It is the management surface for Meta's
`subscribed_apps` API:

| Verb | Effect, reachable with no credential |
|---|---|
| `DELETE` | unsubscribes the WABA from **every** webhook field — all inbound WhatsApp message delivery stops, silently |
| `POST` | forwards `override_callback_uri` straight to Meta — repoints production inbound webhooks at a caller-chosen URL |
| `GET` | lists the WABA's subscriptions |

Two loose matchers in series made it worse: the function also serves
`ANY /wa-business/{proxy+}`, so `/wa-business/webhooks-anything` satisfied the
substring skip and then satisfied the handler's own `elif '/webhooks' in path`
dispatch.

Measured unauthenticated against production before the fix, with no `wabaId` so the
probe could not act:

```text
GET /wa-business/webhooks  -> 400 {"error": "wabaId required"}   past auth
GET /wa-business/profile   -> 401 {"error": "No authorization token provided"}
```

Fixed in three places, because any one alone leaves the shape of the bug:

- `AUTH_SKIP_PATHS` narrowed to `/wa-business/flow-data` — live and in
  `config/lambda-env-manifest.json`, so the next env deploy cannot reopen it.
- `middleware.path_is_exempt` matches exact-or-child-segment, never substring.
- The dead verifier now delegates to `lambda_utils/meta_signature` and fails closed.
  It is retained rather than deleted because it is cited in the security checklist
  and is the correct guard for any Meta callback added to this function later.

Only `/wa-business/flow-data` remains exempt, and it genuinely self-authenticates:
the payload is RSA+AES-GCM encrypted, so only a caller holding our public key can
produce something we can decrypt. Verified still working — a junk payload returns
Meta's specified `421 Decryption failed`, not a `401`.

Live after the fix, now permanent probes in the gate:

```text
GET    /wa-business/webhooks            -> 401   (was 400)
POST   /wa-business/webhooks            -> 401
DELETE /wa-business/webhooks            -> 401
GET    /wa-business/webhooks-anything   -> 401   the substring near-miss
POST   /wa-business/flow-data           -> 421   still exempt, still working
```

### Closing-pass evidence

Gates: python **1470** (was 1351), provider policy **8/8**, route audit 326 routes
/ **0 OPEN**, live auth probes **17/17** (was 12/12).

Deployed: `outbound-whatsapp` v19 (rollback 18), `whatsapp-calling` v14
(rollback 13), `whatsapp-business-api` v32 (rollback 31, env changed before the
publish so the version carries the narrowed skip list).

`AUTH_SKIP_PATHS` was confirmed to be set on exactly **one** of the 58 functions
before changing the matcher, so the blast radius of the stricter rule is one
function and four routes — all four verified live.

**Legacy arm retirement.** `parse()` reports the shape it saw. Once
`shapes` shows no `legacy-sns` for a full DLQ retention period, the legacy arm and
its tests can go.
