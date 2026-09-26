# Current communications architecture (as measured, pre-migration)

Baseline for the Unified Communications Platform migration. Every claim below is
either a `file:line` citation or a live AWS/provider read taken on 2026-09-19.
Where something could not be verified it says so explicitly rather than guessing.

This document describes **what exists today**, not the target. The target is in
`provider-policy.md`; the route from here to there is in `migration-plan.md`.

---

## 1. The headline finding

There is **no provider abstraction layer**. A repo-wide search for
`CommunicationOrchestrator`, `SmsService`, `AwsSmsProvider`, `SmsRegionResolver`,
`RcsCapabilityResolver` and `TextToSpeechService` returns **zero matches**.

Consequently provider choice is made independently, in at least six places, by
inlined country tests against the destination number. There is no single place
that decides "which provider sends this message", which is the root cause of
nearly every inconsistency listed below.

---

## 2. SMS — three senders, three different providers, no shared contract

| Lambda | Provider | Region | Selection |
|---|---|---|---|
| `wecare-sms-aws` | AWS End User Messaging v2 (`pinpoint-sms-voice-v2`) | `us-east-1` + `ap-south-1` | destination country |
| `wecare-sms-in-airtel` | Airtel IQ v5 via a static-IP proxy | n/a (HTTP) | caller picks it explicitly |
| `wecare-outbound-sms` | Airtel IQ → **Sinch SMS** → classic Pinpoint/SNS | `${AWS_REGION}` | destination country, then failure chain |

### 2.1 `wecare-sms-aws` — already most of the target
`amplify/functions/messaging/sms-aws/handler.py`

This function already implements the two-region split the spec asks for:

- clients at `:39` (`us-east-1`) and `:407` (`ap-south-1`, built per request)
- routing by destination, not by caller opt-in: `:314`
  `use_india_region = _is_indian_msisdn(phone_e164) or target_region == 'ap-south-1'`
- TRAI DLT country parameters `IN_ENTITY_ID` / `IN_TEMPLATE_ID` at `:417-424`
- `DryRun` support at `:426-428` — validates identity, DLT and destination
  without delivering, which is exactly what pre-cutover verification needs
- a **hard** DLT gate: `_resolve_dlt_template()` at `:92-110` and the
  `422 MISSING_DLT_TEMPLATE` response at `:316-334`. An Indian send with an
  unmapped template key is refused rather than sent unregistered.
- origination identity pinned to `+18444891209` at `:48-59`, with a comment
  explaining why: the account also owns simulator `+14255556333`, which accepts
  sends and returns a MessageId **without delivering anything**, and both numbers
  sit in the same pool so pinning the pool would not exclude the simulator.

`_format_e164()` at `:479-505` carries a genuinely important correction: the
previous version applied a `+91` default to any 10-digit string, so
`+6581234567` (Singapore, exactly 10 digits in full E.164) became
`+916581234567` — a different, unrelated Indian subscriber — and was then routed
to `ap-south-1` with a DLT template attached. Hong Kong, Denmark, Norway and
Portugal were affected the same way. That was misdelivery, not just misrouting.

**Two real defects remain in this function:**

1. **No delivery-receipt ingestion anywhere in the account.** `_store_message`
   writes `status: 'SENT'` optimistically at send time (`:357-375`) and nothing
   ever updates it. There is no SNS event-destination subscriber, no
   CloudWatch-logs consumer, no `pinpoint-sms-voice-v2` event handler in the
   repo. So AWS SMS delivery state is currently unknowable after submission.
2. ~~The IAM grant is region-pinned.~~ **Resolved — this was a false alarm.**
   `amplify/iam-policies.ts:94-105` scopes `sms-voice:SendTextMessage` to
   `arn:aws:sms-voice:${AWS_REGION}:${ACCOUNT}:*`, which reads as `us-east-1`
   only, while `handler.py:407` builds an `ap-south-1` client. That looked like a
   blocker for India cutover. It is not: `simulate_principal_policy` against the
   **live** role `wecare-digital-lambda-role` returns `ALLOWED` for
   `sms-voice:SendTextMessage` in `us-east-1`, in `ap-south-1`, and on
   `arn:aws:sms-voice:ap-south-1:775261844268:sender-id/WDBEEP/IN`. The deployed
   policy is broader than the IaC snippet implies — the same pattern as
   `wecare-digital-lambda-permissions` granting `wecare/*` for secrets. IaC and
   reality have drifted, which is worth reconciling, but India sending is not
   blocked.

### 2.2 `wecare-sms-in-airtel` — the primary India sender today
`amplify/functions/messaging/sms-in/airtel/handler.py`

Misleadingly named: despite `sms-in`, this is the main **outbound** Airtel
sender, *and* the Airtel DLR receiver, *and* the DLT template registry.

- send `_send_sms()` at `:316-418` → `https://iqmessaging.airtel.in/api/v5/send-sms-cm` (`:385`)
- bulk `_send_bulk_sms()` at `:420-502` → `/conduit/api/v1/send-sms-bulk` (`:473`)
- every call goes through `_call_airtel_via_proxy()` at `:120-176` to
  `SMS_PROXY_URL = 'http://52.3.44.165:8899'` (`:99`) so Airtel sees the
  whitelisted Lightsail IP. 3 retries on 502/503.
- DLR receiver `_handle_dlr_callback()` at `:251-315`
- DLT template registry CRUD at `:504-730` over DynamoDB
  `stack-wecare-digital-DLTTemplates`, seeded from `DEFAULT_DLT_TEMPLATES` (`:667-700`)

**Security defect:** the module docstring contains what appear to be live Airtel
Kong username, password and base64 Basic token in plaintext at `:20-23`, and
repeats the expected secret values at `:49-55`. Runtime reads come from Secrets
Manager `wecare/airtel/sms` (`:97`, `_get_secrets()` `:105-118`), so these
docstring copies are redundant and must be scrubbed regardless of the migration.

### 2.3 `wecare-outbound-sms` — the multi-provider legacy path
`amplify/functions/messaging/outbound-sms/handler.py`

- `provider = body.get('provider','aws')` at `:120` is **overwritten** at
  `:163-168`. Only `provider=='sinch'` from the caller survives; otherwise
  `+91`+12 digits → `airtel`, everything else → `aws`.
- **Sinch SMS fallback** at `:185-194`: if Airtel returns non-success it retries
  via Sinch and rewrites `provider='sinch'`.
- International `_send_aws_sms()` at `:387-433` uses **classic Pinpoint**
  `send_messages` when `PINPOINT_APP_ID` is set, else **SNS** `sns.publish`.
  No DLT, no End User Messaging v2.
- dead code: `_send_airtel_sms()` at `:638-651` has no callers.

### 2.4 Who calls what

| Caller | Target | Citation |
|---|---|---|
| `wecare-plivo-answer` | `wecare-sms-aws:live` | `plivo-answer/handler.py:51,147-200` |
| `wecare-whatsapp-calling` (India) | `wecare-sms-in-airtel` **sync** | `whatsapp-calling/handler.py:1324,1412-1474` |
| `wecare-whatsapp-calling` (India fallback) | `wecare-sms-aws` `region: ap-south-1` | `:1476-1504` |
| `wecare-whatsapp-calling` (intl) | `wecare-sms-aws` | `:1367-1385,1545-1570` |
| `wecare-wix-store` | `wecare-sms-in-airtel` | `ecommerce/wix-store/handler.py:1589` |
| `wecare-voice-in-c2c` | `/sms-in/airtel` or `/sms-aws/send` | `voice-in/c2c/handler.py:1001` |
| `wecare-voice-in-obd` | `/sms-in/airtel` or `/sms-aws/send` | `voice-in/obd/handler.py:1680` |
| `wecare-bulk-worker` | `wecare-outbound-sms` | `operations/bulk-worker/handler.py:156-159` |
| `wecare-agent-action-group` | `wecare-outbound-sms` | `ai/agent-action-group/handler.py:258-290` |
| `wecare-ai-generate-response` | `wecare-outbound-sms` | `ai-generate-response` handler `:4684` |
| frontend `sendSinchSms()` | forces the Sinch branch | `src/api/client.ts:1248-1266` |

A stale comment at `whatsapp-calling/handler.py:1319-1322` says Indian traffic
goes to `wecare-outbound-sms`; the constants at `:1324-1325` say
`wecare-sms-in-airtel`. The constants are what runs.

---

## 3. RCS — Sinch only, India only, one live entry point

`amplify/functions/shared/lambda_utils/sinch_rcs.py`

- gate `is_rcs_enabled()` `:56-58` reads `SINCH_RCS_ENABLED`; set to `'true'` in
  `voice-in/cdr/resource.ts:18`, `voice-in/c2c/resource.ts:23`, `voice-in/obd/resource.ts:23`
- credentials `wecare/sinch/rcs` (`:69`), OAuth password grant with
  `client_id=ipmessaging-client`, token cache + refresh (`:88-182`)
- transport `_send_sinch_message()` `:455-531` →
  `POST https://convapi.aclwhatsapp.com/v1/projects/{projectId}/messages:send`,
  401 re-auth, 502/503 retry
- approved templates `rcsmenu`, `rcsorder`, `waalert` (`:22-25`), Jio, MEDIUM height
- **only `send_rcs_ivr_notification()` (`:316-396`) is actually called.** It
  prefers invoking `wecare-rcs-send` synchronously (`:336-360`), falling back to
  the direct API, then to `card_message`.
- **dead:** `send_rcs_order_notification` (`:399-431`) and `send_rcs_wa_alert`
  (`:434-452`) have no callers. The order path uses Airtel SMS instead
  (`wix-store/handler.py:1589`).

Live callers of `send_rcs_ivr_notification`: `whatsapp-calling/handler.py:710-713`
and `:997-1000`, `voice-in/cdr/handler.py:1155-1158`, `voice-in/c2c/handler.py:1038-1041`.

**There is no AWS RCS implementation of any kind.** No `AwsRcsProvider`, no
`social-messaging` client, no RCS capability resolution. All RCS today is Sinch,
and it is only ever sent to Indian numbers because the only caller path is the
Indian IVR/call-disconnect flow.

---

## 4. Provider split for Sinch — clean, no shared code

| Sinch SMS (to be removed) | Sinch RCS (to be kept) |
|---|---|
| `jumbo.aclgateway.com` | `convapi.aclwhatsapp.com` |
| secret `wecare/sinch/sms` | secret `wecare/sinch/rcs` |
| `outbound-sms/handler.py:258-385` | `lambda_utils/sinch_rcs.py` (whole file) |
| `sms-in/sinch/handler.py` (whole file, `wecare-sinch-dlr`) | `rcs-send/handler.py`, `rcs-dlr/handler.py` |
| `src/api/client.ts:1248-1266` | `data/resource.ts:361-389` `RcsMessages` |
| `iam-policies.ts:395` | `iam-policies.ts:392-393` |

The two share **no code**. The only overlap is the vendor name and a combined
secret listing in `docs/BACKEND_FULL_AUDIT.md:61`. That makes the separation
mechanically straightforward.

---

## 5. India DLT — the same facts duplicated in five places

Entity/PE `1201161991108627443`, sender `WDBEEP` (DLT registration
`1405170900886606599`, REGISTERED, permanent).

| Template key | DLT template id |
|---|---|
| `ivr-default` | `1007277993798259629` |
| `wa-alert` | `1007284579074821763` |
| `wd_order` | `1007723091207562020` |

Held in all of:

1. code map `sms-aws/handler.py:77-82` (env-overridable)
2. constants `outbound-sms/handler.py:55-56`, `sms-in/airtel/handler.py:92-93`,
   `whatsapp-calling/handler.py:1310-1318`
3. DynamoDB registry `stack-wecare-digital-DLTTemplates`, seeded at
   `sms-in/airtel/handler.py:667-700`
4. model defaults `amplify/data/resource.ts:327-328,352-353`
5. UI mirror `src/pages/dm/sms/index.tsx:28-37`

Per-caller pinning: `plivo-answer/handler.py:53-59` (body must match the
approved template **character for character**, asserted by
`tests/test_plivo_answer.py:244-251`), `whatsapp-calling/handler.py:1424-1432`,
`wix-store/handler.py:1570-1580`.

Consolidating these into one source of truth is a prerequisite for the
orchestrator, not an optional tidy-up.

---

## 6. WhatsApp messaging — Meta Cloud API, healthy

- Graph API pinned to `v25.0` across ~20 handlers, usually
  `os.environ.get('META_API_VERSION', 'v25.0')`.
  One deliberate exception: `meta-business-agent/handler.py:235` avoids v26.0
  because it blocked commerce endpoints.
- one secret `wecare/meta-system-user-token`, lazily loaded and cached
  (`whatsapp-calling/handler.py:129-149`), fields `access_token`,
  `access_token_waba2`, `app_secret`, `app_secret_waba2`
- `appsecret_proof` = HMAC-SHA256 of the **access token** keyed by the **app
  secret** — helper at `lambda_utils/appsecret.py`, but
  `whatsapp-calling/handler.py:152-167` and the three `voice-in/*` handlers
  **re-implement it inline**, so the helper is not the single source of truth
- inbound signature verification `_verify_webhook_signature` at
  `whatsapp-calling/handler.py:285-350` plus a 300-second replay guard at `:351-397`
- `WABA2_IDS = set()` at `:91` means the entire `token2`/`app_secret2` dual-token
  branch at `:108-127` is currently **unreachable** — WABA2 migrated to token1

---

## 7. WhatsApp Calling — live on Lightsail Asterisk, not Plivo

Read from Meta via Graph API on 2026-09-19:

| WABA | Number | Phone ID | `calling.status` | `sip.servers[0]` |
|---|---|---|---|---|
| 2094615664435155 WECARE.DIGITAL | +91 93309 94400 | 1016149501586345 | ENABLED | `sip.wecare.digital:5061` |
| 2513394156072604 | +91 99033 00044 | 1055232054343117 | ENABLED | `sip.wecare.digital:5061` |

So **both numbers send the media leg to the Lightsail Asterisk box**, not Plivo.

The two legs of a real call are independent (`scripts/test_call_paths.py:20-45`):

1. **webhook leg** — Meta → `POST /whatsapp` (`wecare-whatsapp-calling`). Works
   today. On disconnect it sends the Airtel SMS and the Sinch RCS notification.
2. **media leg** — Meta → SIP → `sip.wecare.digital` (Asterisk). Asterisk's AGI
   calls back with `{'action':'post_call_sip'}` → `_handle_post_call_sip`
   (`whatsapp-calling/handler.py:861-1004`).

Read/write of Meta calling settings lives only in
`whatsapp-business-api/handler.py`: `_get_calling_settings` `:2530-2553` and
`_update_calling_settings` `:2651-2751`, the latter supporting
`sip: {status, servers:[{hostname, port}]}` at `:2727-2735` and
`srtp_key_exchange_protocol` at `:2737-2740`.

`_redact_sip_credentials` (`:2556-2585`) replaces every `sip_user_password` with
a presence flag plus a truncated SHA-256 fingerprint. Its docstring records that
this endpoint previously leaked a live SIP trunk password into response bodies,
devtools and a session transcript.

---

## 8. Plivo — deployed, wired, but receiving no real traffic

`amplify/functions/messaging/plivo-answer/handler.py` (251 lines)

Returns exactly `<Response><Play>…wav</Play><Hangup/></Response>` (`_ivr_xml`
`:113-121`) with `Content-Type: text/xml` — Plivo ignores a non-XML content type
and the caller hears silence. No `<Speak>`, no TTS; asserted by
`tests/test_plivo_answer.py:99-104`.

Console state (live read 2026-09-19): application `12775976954213184`
`WECARE-WHATSAPP-IVR`, `sip_auth_type='credential'`, SIP endpoint
`wecarewaivr203331794466262` attached, number `918031830030` attached, all three
URLs now carrying `?token=`.

**Only `/plivo/answer` exists.** There is no `/plivo/fallback`, no
`/plivo/hangup`, no `/plivo/events`. The Fallback Answer URL is identical to the
Answer URL, so it provides no fallback — a primary failure is retried against
the identical route and fails identically (`docs/WEBHOOK-INVENTORY.md:81-85`).

**There is no Plivo webhook signature validation anywhere in the repo.** Zero
matches for `X-Plivo-Signature`, `plivo_signature`, `validate_signature`. Plivo
genuinely does not sign `answer_url` fetches, but it *does* sign its callbacks —
and the hangup pass, which is the one that sends SMS, is a callback. HMAC
verification is implemented for Meta and Razorpay, but not Plivo.

---

## 9. The Lightsail box does two unrelated jobs

`wecare-voice-bot`, `52.3.44.165`, Amazon Linux 2023, bundle `micro_3_0`.
No Asterisk/PJSIP config is stored in this repo — zero matches for `pjsip`. The
box is referenced only from outside.

1. **Airtel SMS HTTP proxy on port 8899** — hardcoded default in
   `sms-in/airtel/handler.py:99` and `outbound-sms/handler.py:52`. Verified live:
   `SMS_PROXY_URL` is **not set** as an env var on either
   `wecare-outbound-sms` or `wecare-sms-in-airtel`, so the hardcoded default is
   what runs.
2. **Asterisk serving `sip.wecare.digital`** — the current Meta SIP target, i.e.
   the media leg of every WhatsApp call. Plus a daily cert-expiry cron into
   `_handle_cert_check` (`whatsapp-calling/handler.py:748-806`), publishing
   CloudWatch `Wecare/SIP → CertDaysToExpiry`.

Deleting the box today breaks Airtel SMS in and out, the WhatsApp call media
leg, `_handle_post_call_sip`, and the cert monitor.

**The migration changes this.** Removing Airtel (§2 of the spec) eliminates job
1 outright, leaving only the SIP media leg — which is what the Plivo cutover
replaces. Retiring Lightsail is therefore an *outcome* of this migration, not a
precondition.

---

## 10. Two hazards to carry into the cutover

**Duplicate DLT SMS.** Both legs send a post-call SMS under the *same*
`ivr-default` template from *different* providers:

- `whatsapp-calling._send_disconnect_sms` → Airtel IQ
- `plivo-answer._send_post_call_sms` → `wecare-sms-aws`

`POST_CALL_SMS_ENABLED` is `true` on plivo-answer. Repointing Meta at Plivo
while the webhook leg also sends produces **two SMS per call** to the same
customer under the same registered template. One owner must be chosen before the
repoint (`scripts/test_call_paths.py:31-45`).

**MTA-STS / email is unrelated but fail-closed.** Not touched by this migration;
see `.kiro/steering/email-auth-dns.md` before any DNS work.

---

## 11. Not built at all

| Subsystem | State |
|---|---|
| `CommunicationOrchestrator`, `SmsService`, `AwsSmsProvider`, `SmsRegionResolver` | do not exist |
| `AwsRcsProvider`, `AwsRcsTemplateRenderer`, `RcsCapabilityResolver` | do not exist |
| `SinchRcsTemplateImporter`, internal `RcsTemplate` model | do not exist |
| AWS SMS delivery-receipt ingestion | does not exist |
| Google People API / `GoogleContactsService` | does not exist |
| Google Ads API / `GoogleAdsService` | does not exist |
| `GoogleAuthService` | does not exist (only shell scripts and Meta-CTWA `marketing-ads`) |
| Truecaller verification / `POST /auth/truecaller/callback` | does not exist — only the `wecare/truecaller` secret definition at `scripts/store_provider_secret.py:107-116` |
| `TextToSpeechService` abstraction | does not exist — 4 separate inline Polly implementations |
| `VoiceScriptComposer`, voice-announcement approval flow | do not exist |
| `scripts/check-provider-policy.sh` | does not exist |
| `.env.example` | does not exist (only `.env.local.example`) |

**Existing Polly implementations** that a `TextToSpeechService` must absorb:
`whatsapp-voice/handler.py:282-464` (`/whatsapp-voice/tts`),
`core/site-language/handler.py:332-341` (`/site-language/tts`, discovers voices
at runtime via `describe_voices`), `voice-in/obd/handler.py:555-562`
(`/voice-in/obd/tts`), and `whatsapp-calling/handler.py:2115-2174`
(`_generate_ivr_tts_audio`, voice `Kajal`, neural, mp3).

---

## 12. Deployment and routing reality

Lambdas are **not** deployed by Amplify Gen 2. `amplify/**/resource.ts` files are
documentation plus exported name constants; `amplify/backend.ts` deliberately
does not own them. Deployment is:

1. `scripts/deploy_all_lambdas.py` — zip build + `update_function_code`
   (function→dir map at `:140-168`). It **refuses to create** functions.
2. `scripts/snapstart_publish.py` — publish version, move the `live` alias.

Routes on HTTP API `zllr9lrg7j` (stage `prod`, AutoDeploy, custom domain
`https://api.wecare.digital`) are created imperatively by boto3 scripts. The
canonical pattern is `scripts/register_task12_routes.py` with full rollback.

**Route capacity:** `meta-business-agent/SETUP.md:31-33` records being blocked on
a 300-route cap. Measured live on 2026-09-19: **342 routes**; re-measured
2026-09-26: **361 routes**. So the cap has since been raised and new Plivo
routes are not blocked.

Aliases matter: integrations target `function:live`, so `$LATEST` changes do not
reach production until a version is published and the alias moved
(`.kiro/steering/lambda-snapstart-deploy.md`). **58 of 65** functions have a `live`
alias, re-measured 2026-09-26. The ratio drifts as aliases are provisioned, so
re-derive it rather than quoting this line.

---

## 13. Verification status of this document

| Claim class | How verified |
|---|---|
| Code paths, line numbers, dead code | read directly from the working tree at commit `41dc41c2` |
| Meta calling settings, phone ids, SIP target | live Graph API `GET {phone_id}/settings?fields=calling` |
| Plivo application/number/endpoint/`sip_auth_type` | live Plivo REST API |
| Route count, `SMS_PROXY_URL` unset, alias versions | live AWS CLI |
| Secret ids | live `ListSecrets` (31 secrets) |
| AWS End User Messaging account state, both regions | live `pinpoint-sms-voice-v2` reads, 2026-09-19 — see §14 |
| Deployed IAM vs IaC | live `iam:SimulatePrincipalPolicy` — IaC is narrower than reality |
| **Not verified** | which SES DKIM selector is actually in use |

---

## 14. AWS End User Messaging — measured account state

Read live on 2026-09-19. This settles several things that were previously assumed.

### ap-south-1 (India)

```
sender id      WDBEEP   IN   Promotional,Transactional   Registered=True
registration   IN_SENDER_ID_REGISTRATION   COMPLETE
phone numbers  none
pools          none
opt-out lists  Default
account tier   PRODUCTION
```

No phone numbers or pools is **correct** — India sends by registered sender id,
not by a number. So the India path is fully provisioned.

### us-east-1 (international)

```
+18444891209   TOLL_FREE   ACTIVE   US   TRANSACTIONAL   InternationalSendingEnabled=true
+14255556333   SIMULATOR   ACTIVE   US   TRANSACTIONAL   InternationalSendingEnabled=false
pool           pool-27cc4ee23f1e4225aa71172cbaedbb58   ACTIVE   TRANSACTIONAL
sender ids     none   (correct: the US does not use them)
opt-out lists  Default
protect config protect-b137924dfb934c32b1d10c28b737d08c   AccountDefault=True
account tier   PRODUCTION
```

**The simulator hazard is real and confirmed.** `+14255556333` is
`NumberType: SIMULATOR` and sits in the **same pool** as the real toll-free
number. A simulator accepts a send and returns a `MessageId` without delivering
anything. This is exactly why `ORIGINATION_IDENTITY` must stay pinned and why
pinning the *pool* would not help.

### Spend limits — a hard constraint in both regions

```
TEXT_MESSAGE_MONTHLY_SPEND_LIMIT    enforced 200   max 200
MEDIA_MESSAGE_MONTHLY_SPEND_LIMIT   enforced 200   max 200
RCS_MESSAGE_MONTHLY_SPEND_LIMIT     enforced   1   max   1
VOICE_MESSAGE_MONTHLY_SPEND_LIMIT   enforced   1   max   1
NOTIFY_MESSAGE_MONTHLY_SPEND_LIMIT  enforced   1   max   1
```

`max` equals `enforced` everywhere, so none of these can be raised without an AWS
quota request. **SMS has a $200/month ceiling.** More importantly:

### AWS RCS is not usable yet — three independent blockers

1. `RCS_MESSAGE_MONTHLY_SPEND_LIMIT` is **$1**, with a max of **$1**.
2. **No RCS-capable phone number exists** in either region.
3. Launch registrations are incomplete:

```
us-east-1   US_RCS_LAUNCH_REGISTRATION     CREATED    (x2)
us-east-1   CA_RCS_LAUNCH_REGISTRATION     CREATED
us-east-1   TEST_RCS_LAUNCH_REGISTRATION   COMPLETE   (x2)
ap-south-1  TEST_RCS_LAUNCH_REGISTRATION   COMPLETE
us-east-1   NOTIFY_TIER_UPGRADE_REGISTRATION   REQUIRES_UPDATES
```

Only the **TEST** launch registrations are COMPLETE. The real US and CA ones are
`CREATED`, meaning created but not carried through approval. So §14/§51
(international RCS) is `WAITING_FOR_PROVIDER_APPROVAL` on evidence, not on
assumption, and no non-India RCS traffic can flow until all three are cleared.
