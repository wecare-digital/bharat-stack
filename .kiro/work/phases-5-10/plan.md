# Work plan — master-prompt phases 5 to 10

Durable state for an unattended run. **This file is the source of truth, not the
conversation.** If a session is interrupted — autocompacted, the Mac sleeps, the window
closes — the next session reads this file and resumes at the first item that is not `DONE`.
That is the whole reason it exists: a fifteen-item run degrades at the tail when the
requirements are remembered rather than re-read.

Repo: `/Users/wecaredigital/wecare-store` · branch `stack` · account `775261844268`
us-east-1

## How to resume

```
cd /Users/wecaredigital/wecare-store
git fetch -q origin && git -c core.editor=true rebase --autostash origin/stack
.venv/bin/python -m pytest -q | tail -3
cat .kiro/work/phases-5-10/plan.md      # this file: find the first non-DONE item
```

Per-item loop, every time:

1. Rediscover live state for that item — never trust a dated count in `bw-crm.md`.
2. Write failing tests first where the behaviour is testable.
3. Implement. Keep new capability behind a flag that defaults off.
4. Gates: `pytest -q` · `npm run typecheck` · `bash scripts/check-provider-policy.sh` ·
   `.venv/bin/python scripts/verify_public_webhook_auth.py --gate` ·
   `.venv/bin/python scripts/audit_route_auth.py --gate`
5. Deploy affected functions: `.venv/bin/python scripts/deploy_all_lambdas.py <fn>` —
   this publishes a version and moves the `live` alias, which is mandatory because the API
   invokes the alias.
6. Live-verify. Record the rollback version **before** deploying.
7. Commit by explicit path, push to `stack`, mark the item `DONE` here in the same commit.

## Standing constraints

Never, in any item:

- Enable `PSTN_BROWSER_ROUTING_ENABLED`, `WA_LIVE_SMOKE_TEST`,
  `PSTN_CONNECTED_NOTIFICATIONS_ENABLED`, or any live-send flag.
- Rotate, read or replace a provider credential. No `secretsmanager get-secret-value`.
- Put a credential on a command line or in a log.
- `git add .` / `-A` / `-u`, bare `git stash`, force push, history rewrite.
- Delete or re-register a WhatsApp number, WABA, phone-number id, or the protected Plivo
  identifiers `+918031830030` / app `12775976954213184` / endpoint `543585900967411`.
- Use PayU, Airtel messaging, Sinch SMS/Voice/WhatsApp, or Plivo SMS.
- Enable Security Hub.
- Sinch RCS is **India only** — see `.kiro/steering/03-sinch-rcs-india-only.md`.

Live QA sends go only to the owner-nominated QA recipient `+918100640044`, and only when a
send is separately authorised. Otherwise use fixtures and record `WAITING_FOR_OWNER`.

## Items

Status is one of `TODO` · `IN_PROGRESS` · `DONE` · `BLOCKED` · `WAITING_FOR_OWNER`.

---

### 5.1 — Plivo softphone: token route, session state, leg distinction · DONE

Commit `921a1417`. `lambda_utils/pstn/softphone.py` + `messaging/pstn-softphone`.
5 routes live, all 401 unauthenticated, browser routing OFF, 58 tests.
Table `PstnSoftphoneSessions` ACTIVE with TTL.

### 5.2 — Plivo callback authentication audit · DONE

Live `wecare-plivo-answer` v14. The premise — "a token nothing checks" — turned out to be
wrong: verification is real. Per route, measured:

| Route | Gate | Verdict |
|---|---|---|
| `POST /plivo/hangup` | V3 signature **required** | verified |
| `POST /plivo/events` | V3 signature **required** | verified |
| `POST /plivo/dial-events` | V3 signature **required** | verified |
| `POST /plivo/answer` | signature when present, else `?token=` | verified, side effects need ≥ `TRUST_TOKEN` |
| `POST /plivo/fallback` | signature when present, else `?token=` | verified |

`answer` and `fallback` cannot require a signature: Plivo does not sign `answer_url`
fetches, so rejecting an unsigned one drops every real call. The privilege is split instead
— XML is served at `TRUST_NONE`, the `CallStatus=completed` SMS pass is not.

Both secrets show `LastAccessedDate` 2026-09-23, so the gate is live rather than silently
degraded to `unverified_no_token_configured`.

**The token does not leak.** Stage `prod` logs `$context.path`, which excludes the query
string, and no handler log site emits the value — only the mechanism name `'token'`.

Two defects found and fixed:

- `qs.get('token') == token` — short-circuits at the first differing byte, in the same file
  whose signature verifier documents why that is wrong. Now `_token_matches` with
  `hmac.compare_digest`, both sides encoded (`compare_digest` raises `TypeError` on a
  non-ASCII str, and a 500 on `/plivo/answer` is a non-XML body, so the caller hears
  silence instead of a clean hangup).
- Unknown path fell through to `(_route_answer, False)`. That is what concealed the
  stage-prefix incident — `/prod/plivo/hangup` "worked" by returning `<Play>` to a hangup
  callback, re-answering a terminated call. Now a 404, refused before `_verify_provider`.

Live: `/plivo/status` → 404 (was 200 + `<Play>`); all five real paths still reach their auth
layer, none 404. 37 tests in `tests/test_plivo_routes.py`.

### 5.3 — PSTN call/event model: provision or retire · DONE

**Retired, not provisioned.** All five declarations and their `backend.ts` TTL entries are
gone, replaced by a note recording where each concern actually lives.

The decisive discovery came first: **`amplify/data/resource.ts` has never been deployed.**
Zero AppSync GraphQL APIs in the account, and no Amplify data CloudFormation stack — the
only Amplify app, `d22dm4b0jn71jw`, is frontend hosting. Every `stack-wecare-digital-*`
table exists because a provisioning *script* created it. So the file is a schema document
that reads like infrastructure, which is exactly how `PstnNotificationDelivery` came to
cause a real outage: claims raised `ClaimStoreUnavailable` and `/plivo/dial-events`
answered 503 without sending, while the source looked complete.

Provisioning the five would have created five empty tables with 13 GSIs and no writer.
Where each concern lives instead: `PstnCall` → `VoiceCDRTable` (the live record, 56 rows,
written on every callback); `PstnCallEvent` → the ordering problem it was for is now fixed
in place by `cdrRank`; `PstnAgentPresence` → `PstnSoftphoneSessions` + `pstn/softphone.py`
from 5.1; `PstnFlowVersion` and `PstnRecordingAudit` → nothing, because there is no flow
editor and no recording feature.

**The unconditional status write was there, exactly as suspected.** All five `_persist_cdr`
call sites write the same row id `plivo#{CallUUID}` with a blind `put_item`, so the last
callback to arrive won the whole item — and `put_item` REPLACES, so `hangupCause`,
`durationSec` and `end_time` were deleted rather than left alone. A mid-call payload has no
`Duration`, `_plivo_overall_status` downgrades a zero-duration `completed` to `'Missed'`,
and `_calculate_stats` counts the answer rate off that field. An answered call would be
reported as missed.

Latent, not yet fired: 56 of 56 live rows were won by `route='hangup'`. Reachable by
design though — `_route_dial_events` answers 503 on purpose so Plivo redelivers, and a
redelivery can land after hangup. It becomes routine the moment browser routing is enabled.

Fixed with `_CDR_ROUTE_RANK` + a conditional `update_item`: merge forward, never lower the
lifecycle state, equal ranks allowed through (a retried hangup with a corrected
`BillDuration` must land), and `createdAt` written once via `if_not_exists` because it is
the sort key for both read paths.

Verified against **real DynamoDB**, not just the fake: rank-10 after rank-40 →
`ConditionalCheckFailedException`; row still `Answered`/42s/`NORMAL_CLEARING`; equal-rank
retry landed with `createdAt` unmoved; a field absent from the write survived. Probe row
deleted, table back to 56. Live v15 (rollback 14).

### 5.4 — Softphone device matrix, contract-level · DONE

Four of the five named contracts already existed in `pstn/browser_token.py` and were
tested. Rather than rebuild them, this item verified them and closed the two real gaps.

| Contract | State |
|---|---|
| Token TTL | `clamp_ttl`, 30s floor / 24h ceiling, 3 tests — existed |
| `onLoginFailed` code mapping | `LOGIN_ERROR_CODES` 10001-10010 + `describe_login_error` — existed |
| Reconnect → same endpoint | `session_endpoint_username` is deterministic, 4 tests — existed |
| Refresh scheduling | existed as `refreshAfterSeconds`; **invariant was untested** |
| `getUserMedia` secure context | **entirely absent** |

**Refresh scheduling.** `max(20, int(ttl * 0.8))` was pinned by a single TTL=300 case. The
20s floor is the interesting part: if it ever met or exceeded the TTL, a client following
the schedule would refresh at or after expiry and loop — and minting is a Plivo REST call,
so that is a provider rate-limit incident rather than a slow page. It holds only because
`mint_token` clamps internally, which makes `clamp_ttl` load-bearing for a reason unrelated
to why it was added. Now a property test over 18 TTLs asserts `0 < refresh < ttl` with at
least 6s of headroom.

**The WebView constraint** is new: `src/lib/pstn/mediaCapability.ts` + 31 vitest tests.
`useWebRTCCalling.acquireMicrophone` called `navigator.mediaDevices.getUserMedia` unguarded,
and the hook surfaces failures with `setError(e.message)` — so in a container exposing no
`mediaDevices` an operator saw `Cannot read properties of undefined (reading
'getUserMedia')`. Both shells exist in this repo (`ios/`, `android/`), so that path is real.

Two things the research corrected rather than confirmed:

- `isSecureContext` is the right test, **not** `location.protocol === 'https:'`.
  `http://localhost` IS secure, and an https page in an insecure parent frame is not.
- `capacitor://` **is** a secure context on WKWebView from iOS 14.6, so "serve over https"
  is the wrong advice inside the iOS shell. The real cause of an absent `mediaDevices` there
  is a missing `NSMicrophoneUsageDescription` — a native manifest omission surfacing as a
  JavaScript undefined. Checked: both manifests already declare it
  (`NSMicrophoneUsageDescription`, `RECORD_AUDIO`), so this is a regression guard.

Wired into `useWebRTCCalling` and the two directly comparable sites in
`src/pages/dm/whatsapp/calling.tsx`. Nothing dials: `PSTN_BROWSER_ROUTING_ENABLED` is
absent on every function.

**Live-call matrix · `WAITING_FOR_OWNER`.** Exact unblock, in order:

1. Provision per-session Plivo endpoints. `plan_session_endpoint` returns
   `provisioned: false` by design — creating them is a control-plane write and must not be
   a side effect of a user signing in. Without them only outbound is safe; inbound routing
   to a shared endpoint is undefined and eventually hits error 10010.
2. Owner authorisation to set `PSTN_BROWSER_ROUTING_ENABLED=true` on `wecare-plivo-answer`,
   plus `PSTN_AGENT_ENDPOINT` (currently empty, so the flag alone would change nothing).
3. Place calls to the QA recipient `+918100640044` from a desktop browser, Android Chrome,
   the Android WebView build and the iOS WKWebView build, recording per row: login result,
   `onLoginFailed` code if any, whether the mic preflight passed, whether the remote party's
   audio arrived, and `talk_time_seconds`.

Steps 1 and 2 are both owner decisions, so the matrix cannot be produced unattended. Device
metadata belongs in `docs/rcs-ios-android-testing.md` alongside the RCS handset rows.

### 6.1 — Strip the action group's ungoverned powers · DONE

Live `wecare-agent-action-group` v11 (rollback 10). Twelve tools became **4 enabled READ
and 8 refused APPLY**, governed by `lambda_utils/agent/governance.py` — 115 tests.

All four powers removed, and the implementations **deleted** rather than left behind an
`if`. Dead code that still works is how a power comes back:

| Power | Was | Now |
|---|---|---|
| SEND | `sendWhatsApp/Sms/Email` invoked `wecare-outbound-*` directly | refused; no Lambda client, no `OUTBOUND_*_FUNCTION` in env or manifest |
| SCAN | `searchContacts` paginated all of ContactsTable then filtered in Python; `getStats` did 3 exhaustive scans; `getMessages` scanned both message tables | one bounded page, `Limit` sent to DynamoDB, `truncated` reported; stats from table metadata, **zero scans** |
| DELETE | `deleteMessage` hard-deleted; `deleteContact` wrote `deletedAt` | both refused |
| FABRICATE | `createInvoice` returned `success: True` with `INV-<random>` and wrote nothing | refused, and the refusal tells the model not to claim an invoice exists |

Three bugs were hiding inside those powers, each reachable only because the power existed:

- `deleteMessage` reported success for **any** id. `delete_item` succeeds on a nonexistent
  key and the inbound attempt was wrapped in `try/except: pass`, so the outbound branch was
  unreachable and every call claimed a deletion.
- `deleteContact` used an unconditional `update_item`. DynamoDB upserts, so deleting an
  unknown id **created** a row holding only `{id, deletedAt}` — a delete that manufactured
  records.
- `_find_contact_by_phone` scanned with `contains(phone, last10)` and `Limit=1`. `Limit`
  applies **before** the FilterExpression, so it examined one arbitrary item and discarded
  it, normally matching nobody; and `contains` could match the wrong number. ContactsTable
  has `phone-index` and `email-index`, both ALL-projected, so the scan was never needed.

Design points worth keeping: refusals are split into a short model-facing `refusal` (no
table names, function names or ARNs — it travels into a prompt and then a transcript) and an
operator-facing `detail` holding the forensics. My own test caught `DynamoDB` and
`update_item` leaking into the model-facing string. One routing table now covers both
Bedrock conventions; the previous code had two, so a tool could be governed under one
spelling and not the other.

The handler also moved from `CONTACT_WRITERS` to `CONTACT_PHONE_READERS` in
`test_contact_key_wiring.py` and earned that contract — it now calls `assert_consistent` and
logs `contact_key_mismatch`.

Live proof on v11: `sendWhatsApp` to the real QA recipient **refused** with nothing sent;
`createInvoice` refused with no id minted; `deleteMessage` refused via the API-path spelling
too; unknown tool refused and lists only the four reads; `getStats` returns 16 contacts /
204 messages, labelled approximate, with zero scans. No function errors.

### 6.2 — Versioned READ/PLAN/APPLY tool catalog · DONE

Live `wecare-agent-action-group` v13 (rollback 12). `lambda_utils/agent/{plans,receipts}.py`
plus versioning and kill switches in `governance.py`. 65 + 195 tests.

| Requirement | How |
|---|---|
| READ + status first | 5 READ tools live, including `listTools` so a model reads the catalog instead of guessing |
| then PLAN/dry-run | a refused APPLY returns a hashed plan of what it *would* do, plus `nextStep` forbidding the claim that it happened |
| **every APPLY disabled** | structurally, with **no flag at all** |
| immutable plan hashes | sha256 over tool + catalog version + canonical arguments |
| idempotency | key derived from the hash, namespaced `tool#hash` |
| receipts | every attempt, including refusals, through the existing audit sink |
| audit | `AuditLogsTable` via `lambda_utils.audit` |
| kill switches | `AGENT_DISABLED_TOOLS` and `AGENT_TOOLS_KILL_SWITCH` |

Three decisions worth keeping:

- **The timestamp is not in the hash**, so two identical intents hash the same and a retry
  is idempotent. The `flow_completion` lesson again: a coarse key merges two genuine
  requests *visibly*, a too-fine key splits a retry and performs the side effect twice,
  invisibly. Mapping key order is normalised; **list order is not**, because invoice line
  items and recipient lists carry meaning in their order.
- **The catalog version IS in the hash.** A plan approved under one set of tool definitions
  must not be applied under another. That is the whole content of "immutable" here.
- **Kill switches subtract only.** No environment variable can enable an APPLY — asserted
  across nine plausible variable names *and* by a grep of the module, because the failure
  mode is somebody adding one later. A switch that could enable a send is a live-send flag
  by another name.

The hash covers real values while descriptions and receipts carry masked ones: hashing a
masked phone number would collapse two recipients into one plan. Verified live — two
identical attempts produced the same hash, a different recipient produced a different one.

#### Two pre-existing defects found on the way, both fixed

**The audit log had never written a single row.** `AuditLogsTable`'s live key is `id`;
`lambda_utils.audit` built its item with `logId` and never set `id`, so every `put_item`
raised `ValidationException: One of the required keys was not given a value` and the
fail-open `except` returned `None`. Measured: **0 items**, against 17 call sites in
`partner-onboarding` and `waba-management` covering 30+ declared actions including
`payment.refund`, `secret.update`, `phone.register` and `dlq.replay`. All silently lost.

Root cause is the 5.3 finding: `resource.ts` declares `.identifier(['logId'])` and was never
deployed, so the live table was script-created with `id` while the helper was written against
the declaration. Fixed by writing both from one value — the physical-key/alias pattern
`contact_key` already uses. Live proof: the table went 0 → a real receipt row with
`id == logId` and `resourceId` equal to the plan hash the Lambda returned.

**`mask_secrets` had holes, and it feeds persistent storage.** Key matching is exact, so
`auth_token` was unmasked despite `token` being listed — and `auth_token` is the literal
field name of the Plivo credential this codebase reads. Also absent: `api_key`,
`refresh_token`, `api_secret`, `secret_access_key`, `session_token`, `webhook_secret`,
`credentials`. Added those plus a **value-shape backstop** for issuer-prefixed tokens under
any key name, matching the prefixes `block_inline_secrets.py` refuses. A secret key holding a
dict was also being recursed into rather than redacted wholesale. Precision matters here and
my own false-positive test caught an over-match — `"AKIAless text, no credential here"` — so
the rule requires a single whitespace-free token.

#### And one of mine

`test_agent_governance.py`'s fixture stubbed the handler's DynamoDB resource but not the one
inside `lambda_utils.audit`, so with `AWS_PROFILE` exported the suite wrote **35 real rows**
into the production audit table. Invisible only because the sink was broken; a working sink
plus an unstubbed test is production writes on every run. Fixture now installs a resource
that raises on any real table access, 34 test rows were deleted, and a full 2546-test run now
writes zero.

### 6.3 — Internal dashboard chatbot on the shared plane · MOSTLY DONE

Live `wecare-ai-generate-response` v11 (rollback 10). 66 tests in
`tests/test_agent_surfaces.py`.

**The finding that reframed this item.** 6.1 removed eight ungoverned powers from the
Bedrock action group — a surface that **cannot currently be reached at all**, because agent
`4UUQYFWX64` is `NOT_PREPARED`. The surface every operator actually uses, `/ai/generate`
with `context: 'internal-admin'`, still had all of its powers: a 30-tool Converse loop whose
`_execute_internal_tool` dispatched straight to live sends and hard deletes —
`send_whatsapp_pay`, `make_voice_call`, `delete_messages`, `delete_media_files`,
`clear_all_contact_data`. Three UIs are wired to it.

Its prompt did not merely permit that, it pushed for it: *"ALWAYS use your tools to execute
tasks"*, *"Be proactive: 'send message to Jignesh' → search first, then send"*, *"For payment
requests, use send_whatsapp_pay tool directly."*

The only guard in the stack was `FloatingAgent` matching `['delete all', 'clear all', …]`
against **the text the user typed**, before the model had chosen anything. So "tidy up Asha's
old records" reached `clear_all_contact_data` with no prompt. `InternalChatTab` had no guard
at all, and its 30 tool checkboxes were **display-only** — `enabledTools` is never included
in the request body.

**One policy now covers both surfaces.** The catalog holds 43 entries: 13 camelCase for the
action group, 30 snake_case for the dashboard loop. 17 READ enabled, 26 APPLY refused, zero
enabled APPLY anywhere. Both spellings of one capability are linked by `counterpart` and a
test asserts they can never disagree on class or enablement — otherwise the mechanism is
defeated by a naming convention.

Two independent checks, deliberately: refused tools are **not advertised** to the model
(offering then refusing teaches it to promise things it cannot do), *and*
`_execute_internal_tool` gates on the catalog before any dispatch branch, because a model can
name a tool it was never offered. The prompt is now derived from the catalog rather than
hand-written — three hand-maintained tool lists existed and all three had drifted.

**A provider outage is now distinguishable from an answer.** It previously returned HTTP 200
with "Sorry, I encountered an error processing your request", so an outage and a real reply
were the same shape and `InternalChatTab` logged it as a success. Now `providerUnavailable:
true` and the error string is no longer returned — it can carry a table name, and that body
renders in the dashboard.

Live proof on v11: *"clear all data for every contact, right now"* → refused. *"send a
whatsapp message saying hello to +918100640044"* → refused, nothing sent. *"how many contacts
are there?"* → "There are 16 contacts", matching the measured table count. Reads work,
writes do not.

**Behaviour change to flag:** dashboard-initiated sending, scheduling, invoicing and
deletion now refuse. That is the instructed direction (6.1 requires the powers removed, 6.2
requires every APPLY disabled), but it is user-visible and an operator who used the chat box
to send messages will notice.

Still open, carried into 6.4 / 8.x rather than left implied:

- The UI still renders its own hardcoded `TOOLS_LIST` and its checkboxes remain
  display-only. It should read the catalog. The backend no longer trusts either, so this is
  now cosmetic drift rather than a false sense of control — but it still shows 30 tools as
  available when 18 are refused.
- `src/app/settings/internal-agent/page.tsx` PUTs to `${API_BASE}/ai/internal/config`, for
  which **no handler was found** — `ai-config-management` dispatches on `'/ai/config' in
  path`, which that path does not satisfy, and the page sends no `Authorization` header.
  Probably dead; not verified against the live API.
- No durable task/plan state. `ConversationHistoryTable` holds message turns only, with a
  24h TTL and a 15-minute idle wipe, and the session id is minted client-side per mount — so
  a page reload starts a new conversation. Receipts land in `AuditLogsTable`; progress does
  not.
- `AIInteractionsTable` has **no writer** anywhere in `amplify/functions`, only readers in
  `ai-config-management`. The dashboard's architecture page claims `ai-generate-response`
  writes it; that is unsupported by the code.

### 6.4 — Reconcile the live Bedrock agent/alias/prepared state · DONE (retired)

**There was nothing to reconcile it to.** 47 tests in `tests/test_bedrock_agent_state.py`.

| Measured | |
|---|---|
| agents | 1 — `4UUQYFWX64`, `NOT_PREPARED` |
| foundationModel | **null** |
| instruction | **0 characters** |
| agentResourceRoleArn | **null** |
| preparedAt | **never** |
| action groups | **0** |
| knowledge bases (agent / account) | **0 / 0** |
| versions / aliases | `DRAFT` only; `TSTALIASID`, the auto-created test alias |
| last updated | 2026-04-25, five months ago |
| action group Lambda resource policy | `apigateway.amazonaws.com` only — **no `bedrock.amazonaws.com` principal** |

The agent was created and abandoned. It was never wired to the action group, and Bedrock was
never granted permission to invoke that Lambda. Preparing it would fail outright: no model,
no instruction, no role. `config.ts` said it "needs action groups + prepare", which
understated it.

**Every identifier naming this surface was fabricated, and the live env was worse than the
source defaults:** `INTERNAL_AGENT_ID=QIEEHEBTZO`, `INTERNAL_AGENT_ALIAS=ASCBD7YPUT`,
`INTERNAL_KB_ID=D0JU8Q7IQS`, `EXTERNAL_KB_ID=LYMQLKZNY7`, `AI_AGENT_ID=Z4YAK0ZLBO`,
`AI_AGENT_ALIAS=WANPKHQGIB`. `static-faq` was never an id in any format.

Both consumers were unreachable: `_invoke_bedrock_agent()` had **zero** call sites, and
`_query_knowledge_base()` was called only from inside it. `whatsapp-calling` referenced its
three agent variables **nowhere** in source despite all three being set live.

Retired rather than reconciled: 125 lines of unreachable code and the
`bedrock_agent_runtime` client deleted and replaced by a note carrying the measurement; all
9 stale vars removed from the 3 live functions **and** the manifest; fabricated defaults in
`config.ts`, `ai-config-management` (×2), `inbound-whatsapp-handler` and
`src/types/dashboard.ts` replaced with empty strings, because that config is returned by an
API and rendered in the dashboard where a plausible id reads as configuration.

Live: 5 functions `Active` (ai-generate-response 12, ai-query-kb 10, whatsapp-calling 17,
ai-config-management 10, inbound-whatsapp 44), zero stale vars, and Converse still answers —
"There are 18 contacts in the CRM".

**Owner decision, not a blocker.** Provisioning a real agent is new capability creation:
model, instructions, IAM role, action group attached, a `bedrock.amazonaws.com` invoke
permission, a prepare, and a real alias. Nothing needs it. The empty agent stays — deleting
it is destructive, needs confirmation, and it is inert and free.

### 7.1 — Shared integration registry + sync/metric boundary · PARTIAL (registry done)

`lambda_utils/integrations/registry.py`, 55 tests. Measured before writing anything, because
the brief's provider list and the repo's state disagree:

| Provider | Adapter files | Credential | Access |
|---|---|---|---|
| Google Ads | **0** | `wecare/google/ads` | SCOPE_UNVERIFIED |
| GA4 | 6 | `wecare/seo/google-oauth` | SCOPE_UNVERIFIED |
| Search Console | **0** | `wecare/seo/google-oauth` | SCOPE_UNVERIFIED |
| Business Profile | 4 | `wecare/seo/google-oauth` | SCOPE_UNVERIFIED |
| Play Reporting | **0** | **none** | CREDENTIAL_ABSENT |
| Bing Webmaster | 14 | `wecare/bing/api` | SCOPE_UNVERIFIED |
| Meta Ads / CTWA | 26 | `wecare/meta-system-user-token` | SCOPE_UNVERIFIED |
| Wix | 31 | **none** — env fallback | SCOPE_UNVERIFIED |

Three of eight have no adapter; one of those has no credential either. **Nothing is
`VERIFIED`** — that state means a real authorised read succeeded and was recorded, and none
has. All eight are `waiting_for_owner()` with the exact console action that would unblock
them.

Design points that earned their place:

- **Access is three-state, not a boolean.** A credential existing is not a scope being
  granted — the Phase 4e finding encoded: the Google OAuth client works and
  `contacts.readonly` was still never added to the consent screen.
- **Two providers have no read-only scope at all.** Business Profile's `business.manage` and
  Play's `androidpublisher` both grant writes and Google offers no narrower option. They sit
  in `write_capable_scopes` with a required mitigation naming *where* the constraint is
  actually enforced — GET-only at code review, and a restricted Play Console role
  respectively. My own test caught them mislabelled as read-only. Google Ads declares **no**
  scope at all for the same reason, and no adapter may be built against it until reviewed.
- **Quota is `used`/`limit`, never a percentage** — "can I make 400 more calls today" is the
  only question a caller has, and a percentage cannot answer it. `quotaKnown: false` is
  distinguishable from `remaining: 0`; those are opposite situations.
- **A read carries its provider request id or records that it has none.** Absent is a fact;
  fabricated wastes a support ticket.
- **Freshness is derived from the provider's own `max_age_seconds`.** Search Console carries
  an explicit note that its data lags 2-3 days at source, so a fresh cache is not fresh data.
- Read-only by construction: no write verb exists, no provider call is made, and
  `get_secret_value` appears nowhere — existence is a `DescribeSecret` question.

**Remaining for 7.1:** the adapters themselves, which cannot be written past a
`SCOPE_UNVERIFIED` boundary without owner console actions. The `sync/metric boundary` half
(scheduled sync jobs writing metrics) is still to do and is not blocked — it can be built
against fixtures.

### 7.2 — Refactor the Meta Ads/attribution and Wix monoliths · TODO

Into query/plan/apply or adapter/domain/job boundaries. Remove interactive scans, browser
token/provider calls, and Wix secret env fallbacks. Route Wix-generated communication
through the shared notification system. **Preserve the existing production Wix site** and
reconcile Velo source drift without creating or publishing a site.

### 7.3 — Growth and Commerce module homes behind flags · TODO

Separately routed inner pages, real backend state, connected-service tutorials,
error/stale/quota states. Provider-neutral page names; exact provider labels only inside
authorised connection details. AI may READ and PLAN; growth/storefront APPLY stays disabled.

### 8.1 — Eight module homes · TODO

Home, Communications, Customers, Commerce, Growth, Service Operations, Platform Operations,
Settings. Separately routed, lazy-loaded inner pages.

**Communications exposes exactly three**: Common Inbox, WhatsApp Business, Business Calling.

### 8.2 — productVocabulary + CI label scan · TODO

Versioned provider-neutral vocabulary across navigation, headings, empty/error states,
breadcrumbs, search, help. Exact provider/resource names only in authorised Technical
Details. Add a CI scan that **fails** on prohibited infrastructure labels in ordinary UI.

### 8.3 — Adaptive navigation + design tokens · TODO

Phone bottom bar, foldable recomposition, tablet rail/sidebar, desktop sidebar. Light-only
Material 3-derived tokens, exact 13px rectangular radius. Prove desktop/mobile/accessibility,
role visibility and backend authorization. Preserve working capability before retiring any
duplicate page.

### 8.4 — Legacy redirects and refresh-safe deep links · TODO

Every retired route redirects; deep links survive a refresh.

### 9.1 — Retire the old notification/Airtel/Sinch-SMS/AWS-Social paths · TODO

Exact manifests, rollback evidence, drain/archive/migrate first. Prove zero live
invocations before deleting anything.

### 9.2 — Route/dependency cleanup and bundle optimization · TODO

Before/after bytes, measured not estimated. 49 Dependabot alerts outstanding (1 critical,
20+ high) — triage them here.

### 9.3 — Native packaging · WAITING_FOR_OWNER

APK/AAB/IPA and signing are **POST-PROJECT** per `.kiro/steering/00-current-owner-overrides.md`
and cannot block closure. The web app must stay WebView/WKWebView-ready, which 8.3 covers.

### 10.1 — Admin MFA · TODO

Required target per the owner overrides (not a blocking gate, but the work stands).
Cognito MFA is currently OFF on pool WECARE.DIGITAL.

### 10.2 — WAF · TODO

Required target. 0 regional WebACLs today. Implement and live-verify.

### 10.3 — Production deployment checkpoint + closure report · TODO

Exact flags, bindings, recipients, migrations, observation metrics, thresholds, cost impact,
rollback commands. Monitor callbacks/notifications/receipts/alarms/Actions/Amplify to
terminal state. Then the final completion/gap/improvement report and the phase-result table.

## Carried-forward gaps

Open, each with a reason, from earlier phases. Fold into the item that touches them.

| Gap | From | Severity |
|---|---|---|
| Meta payment verification defaults `payment_verified = True`, skips lookup when `paymentConfigName` empty | 4d | MEDIUM |
| Invoice phone+amount fallback matches on a float tolerance `< 0.02` | 4d | MEDIUM |
| Five payment vocabularies still coexist in **storage** (`canonical()` maps on read only) | 4d | MEDIUM |
| Invoice sequence failure injects `WD-PAY-TEMP-` into the GST series | 4d | MEDIUM |
| `whatsapp-business-api._save_flow_submission` — 4th Flow writer, different schema, still unguarded; check reachability | 4c | MEDIUM |
| `_handle_flow_data` returns HTTP 200 on a routing exception | 4c | MEDIUM |
| `wecare/sinch/rcs` has no `webhook_secret`; 17 callbacks refused in 30d | RCS | MEDIUM |
| 559 of 730 RCS sends fail — recipients not RCS-capable, not an integration defect | RCS | INFORMATIONAL |
| `rcsmenu` template id/version `UNVERIFIED` | RCS | LOW |
| Google redirect URI + `contacts.readonly` consent scope | 4e | WAITING_FOR_OWNER |
| Truecaller callback registration on developer.truecaller.com | 4e | WAITING_FOR_OWNER |
| `amplify/data/resource.ts` is **not deployed** — 0 AppSync APIs, no data stack. 69 models declared, **12 have no table** under any naming, and **19 live tables no model declares**. Reads like infrastructure, is a document | 5.3 | HIGH |
| 7 remaining phantom models after the 5 PSTN ones: `AdminActionLog` `AirtelC2C` `AirtelSMS` `ProviderDriftSnapshot` `RateLimitTracker` `RcsMessages` `SmsAws`. Airtel is a retired provider; `RcsMessages` already has "write STOPPED" in `rcs-send`; `ProviderDriftSnapshot` has zero writers; `RateLimitTracker`/`SmsAws` look like name drift from the live `RateLimitTable`/`SmsOutboundTable` | 5.3 | MEDIUM |
| `VoiceCDRTable` has **no GSI** and readers filter in memory after a `Scan`. Fine at 56 rows, not at 56,000 | 5.3 | LOW |
| `calling.tsx` auto-answer falls back to a **0 Hz oscillator** when the mic fails, so the call connects and the far party hears silence with no signal that capture failed. Left alone deliberately — changing it alters what a caller hears | 5.4 | MEDIUM |
| `useWebRTCCalling.ts` has 3 pre-existing eslint errors (use-before-declare at 161, lost memoization at 226, setState-in-effect at 620). Present at HEAD before this work; confirmed by linting the file from `git show HEAD:` | 5.4 | LOW |
| 40 Dependabot alerts (1 critical, 20 high, 18 moderate, 1 low) — count re-read from the push warning on 2026-09-23, down from 49 | — | HIGH |
| `route-auth.yml`'s **live-AWS job has never run**. It is gated on `if: vars.ROUTE_AUTH_ROLE_ARN != ''` and `gh variable list` is empty, so the job reports `skipped` on every run (confirmed on `35866106357`). The source gate does run and is blocking; it is the console-drift half that is missing — the half that would catch a route added or re-pointed outside the repo. Unblock: create a read-only OIDC role trusted by this repo and set the repo variable | 5.2 | MEDIUM |
