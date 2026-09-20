# Bugfix Requirements Document

## Introduction

Seven defect conditions were reported against the Plivo control plane and the SMS
provider path. Before writing this document the live Plivo account and the live
HTTP API were read through their APIs, and the repository's existing Plivo assets
were reviewed. That measurement changes the scope materially, so it is stated
here rather than discovered later.

**Three reported conditions are no longer present.** Read back from Plivo API
truth on 2026-09-19, application `12775976954213184` reports
`fallback_answer_url = https://api.wecare.digital/plivo/fallback`,
`hangup_url = https://api.wecare.digital/plivo/hangup`, all methods POST, and
`default_endpoint_app = true`. A plan run reports zero fields would change. The
four webhook routes exist on the live HTTP API, each bound to the function's
`live` alias. A control plane service, a reconcile CLI, a V3 signature validator
cross-checked against the official SDK, and 174 passing tests already exist.
Reported BUG 3 (wrong fallback and hangup URLs), reported BUG 4 (success inferred
from HTTP status), and the active breach in reported BUG 2 (`default_endpoint_app`
false) are therefore **already remediated**. This document does not restate them
as live defects, because claiming a defect that measurement contradicts would
make every other claim in it untrustworthy.

**What remains is different in kind, and in two places worse than reported.** The
guards that protect the Plivo invariants exist but nothing runs them: no pipeline
executes the test suite, and no schedule executes a reconcile, so a change made
outside the control plane is detected only if a human happens to look. The
webhook routes exist only as live configuration with no declarative definition, so
the corrected URL state is not reproducible. Provider authentication accepts an
unsigned answer-style fetch outright when the diagnostic token is unconfigured,
which is weaker than the reported token-only posture rather than stronger than it.
And the SMS path is untouched: `POST /sms/send` is live, reachable from the
dashboard, and still defaults to the Airtel IQ proxy with a Sinch fallback, while
the CI provider gate is deliberately configured to invert its own result so the
pipeline reports success with 160 violations present.

Impact. The Plivo voice path is currently correct but unprotected, so the
regression that already happened once can recur silently. The SMS path actively
violates the `channel == SMS` implies `provider == AWS_END_USER_MESSAGING`
invariant on every Indian send.

Nothing in this document authorises a number routing cutover, a Zentrunk
mutation, a Meta SIP change, or a Lightsail deletion.

### Confirmation of the findings above

The findings in this section were reviewed and **confirmed as valid and matching
the repository**. They are not re-opened below: the provider gate at 160
violations across six rules; Airtel SMS, Airtel voice, C2C, OBD and proxy code
reachable; Sinch SMS still available as sender and fallback; the dashboard still
reaching the deprecated `/sms/send`; CI running the gate with `--expect-fail` so
violations still produce a green job; no CI workflow running the full frontend
and Python suites; Plivo application URLs and protected fields correct but
scheduled drift detection and declarative webhook-route definitions missing; and
the answer route able to treat an unsigned request as verified when its
diagnostic token is unconfigured. The three conditions measured as already
remediated stay remediated and are not restated as defects.

### Scope expansion — Airtel voice is now in scope

The provider routing target is now fixed and authoritative. Every row is a
requirement, not a preference.

| Traffic | Provider |
|---|---|
| PSTN voice | Plivo Voice + Plivo Browser SDK |
| Normal SMS to +91 | AWS End User Messaging, `ap-south-1`, approved DLT template **required** |
| Normal SMS outside India | AWS End User Messaging, configured region, default `us-east-1` |
| India RCS | Sinch RCS only |
| Non-India RCS | AWS End User Messaging RCS |
| WhatsApp messaging | Meta Cloud API |
| WhatsApp Calling | Meta → `sip.wecare.digital:5061` → Lightsail Asterisk |

Prohibited entirely: **Airtel** in all forms · **Sinch SMS** · **Sinch Voice** ·
**Sinch WhatsApp** · **Plivo SMS** · **SNS SMS** · **legacy Pinpoint SMS**.

**Hard rule, stated separately because the current code violates it:** there must
be no automatic fallback from AWS SMS to Sinch SMS, Airtel or Plivo. It carries
its own defect clause (1.14), its own expected clause (2.14) and its own
acceptance test (T26).

Because Airtel voice is now in scope, **confirmation `[PP-SPLIT-001]` in
`design.md` is resolved by scope expansion.** That confirmation proposed
splitting `airtel-runtime` into a gating SMS rule and a tracked voice rule with a
pinned baseline of 40, on the reasoning that zero was unreachable while Airtel
voice sat outside scope. Zero across all six rules is now reachable, so the rule
split, the baseline file and the `--mode baseline` staging step it introduced are
no longer needed. The design decision is superseded, not merely deferred.

### New requirement — notify on call connect, not after hangup

A notification must be produced at the moment a PSTN call connects, on a
**server-side signed Plivo `<Dial callbackUrl>` event where `DialAction =
connected`**, not on a Browser SDK client event. Two channels fire from it: an
AWS End User Messaging SMS, and RCS routed by destination. The provider semantics
behind this are cited under *Verified Provider Semantics* below, including the
points that change the design: the callback expects no XML in response, and Plivo
retries any webhook that does not return HTTP 200.

The current code is wrong on trigger, on isolation and on eligibility, and the
sharpest problem is structural: a single claim guards two independent effects, so
failure isolation and no-duplicate-on-retry cannot both hold. That is clause
1.16, and it is the reason the new design needs separate per-channel jobs rather
than an extra branch inside the existing one.

### Scope observation

Stated plainly rather than buried. This document now spans five different kinds of
work: a control-plane fix, a provider migration, a greenfield Plivo Browser SDK
softphone, greenfield AWS RCS, and an eleven-page operator surface of roughly
eighty tabs. The bugfix clauses in sections 1, 2 and 3 remain the defect-driven
core. The Browser SDK, AWS RCS and the page hierarchy are net-new capability and
may warrant their own spec, so **the fix must not be blocked behind the feature
work.** Clauses 2.30 through 2.34 are marked where they are requirements without
a paired measured defect.

`design.md` was written against the pre-expansion scope and is now substantially
stale — its Airtel-voice-out-of-scope reasoning, its `[PP-SPLIT-001]` staging
sequence and its phase ordering all predate this update. It must be re-run.

## Bug Analysis

### Current Behavior (Defect)

Control plane completeness — the service and CLI do not cover the required surface.

1.1 WHEN an operator needs a single Zentrunk trunk by identifier THEN the system offers only a list-all discovery call and provides no single-trunk read, so a trunk cannot be inspected without retrieving and filtering the whole collection.

1.2 WHEN an operator invokes the control plane CLI THEN the system exposes flag-based verbs only and provides no dedicated number inspect, endpoint inspect or trunk inspect command, so those resources can be read only as a side effect of the combined inspect output.

1.3 WHEN an approved number routing cutover is to be executed THEN the system provides no apply command at the operator surface, so the only route to the guarded apply operation is to write ad-hoc code against the service.

Guard enforcement — the protections exist but nothing executes them.

1.4 WHEN the application is changed outside the control plane, by console edit, ad-hoc API call or third-party tool THEN the system detects a resulting `default_endpoint_app` regression only if a human later chooses to run an inspect, because no schedule, hook or pipeline performs a reconciliation.

1.5 WHEN a change is pushed that breaks the `default_endpoint_app` guard, the read-back verifier or the signature validator THEN no automated pipeline executes the test suite that covers them, so the regression reaches the default branch unreported.

1.6 WHEN the Plivo webhook configuration is rebuilt from the repository THEN the system has no declarative definition for the fallback, hangup and events routes, so the corrected URL state depends on live configuration that the repository cannot recreate or diff.

Provider authentication — the answer-style gate fails open.

1.7 WHEN an unsigned answer-style fetch arrives and no diagnostic token is configured THEN the system accepts the request as verified, so provider identity is not established by any mechanism at all.

1.8 WHEN a callback arrives carrying only the main-account signature header and the account has acquired a subaccount THEN the system validates it against the subaccount token because no main-account token is supplied to the verifier, so a genuine callback is rejected.

SMS provider path — the deprecated proxy is still the active route.

1.9 WHEN an SMS send is requested through the live `/sms/send` route THEN the system defaults to the Airtel IQ proxy path rather than AWS End User Messaging.

1.10 WHEN that route detects an Indian recipient THEN the system attempts Airtel first and falls back to Sinch, so `channel == SMS` does not imply `provider == AWS_END_USER_MESSAGING`.

1.11 WHEN the dashboard sends an SMS THEN it calls that same route, so the deprecated path is reachable by a normal user action and not only by legacy code.

Deprecated provider removal — prohibited paths remain active and the gate is disarmed.

1.12 WHEN the provider policy gate runs THEN it reports 160 violations across six rules, covering Airtel runtime code, the Airtel SMS proxy, the Sinch SMS sender, Sinch transport outside the approved India RCS paths, legacy non-End-User-Messaging AWS SMS transports, and SMS paths assigning a non-AWS provider literal.

1.13 WHEN that gate runs in CI THEN it is configured to invert its own result, so the pipeline reports success while every one of those violations is still present.

Automatic fallback to a prohibited provider — recorded separately from 1.10 because it is a distinct mechanism with its own failure mode.

1.14 WHEN a send on the AWS End User Messaging path fails THEN the system falls back automatically to a prohibited provider, Sinch SMS generally and Airtel first on the Indian path, so prohibited traffic can leave the platform with no human decision, no approval and no gate, purely as a consequence of an upstream error.

Connected-call notification — wrong trigger, one claim for two effects, wrong eligibility.

1.15 WHEN a Plivo call connects to the answering party THEN the system sends nothing at that moment, because notification is triggered by `CallStatus == 'completed'` at the answer-hangup pass (`amplify/functions/messaging/plivo-answer/handler.py:358`) and on the hangup route (`:390`), which is after the call has ended rather than when it connected.

1.16 WHEN the post-call path runs THEN a single claim, `_claim_once(call_uuid, 'postcall')`, guards both the CDR persist and the SMS leg (`plivo-answer/handler.py:358`, `:390`). One claim covering two independent effects cannot deliver independent failure isolation and no-duplicate-on-retry at the same time: a failed SMS leaves the claim taken, so the retry is suppressed, and a second channel has no claim of its own to hold. This is a structural defect, not a tuning problem.

1.17 WHEN the caller is not an Indian number THEN `_send_post_call_sms` returns early with `reason='non_indian_caller'` (`plivo-answer/handler.py:283`), so no notification is sent outside +91 at all. Note that the provider is already correct on this leg — `SMS_FUNCTION` defaults to `wecare-sms-aws:live` (`:71`) — so the defect is eligibility, isolation and trigger point, not the provider.

1.18 WHEN a notification is attempted THEN the system records no per-channel state, so PENDING, SENT, FAILED and SKIPPED cannot be distinguished per channel, and a transient error cannot be told apart from a permanent DLT, destination or permission error.

1.19 WHEN Plivo redelivers a callback because the endpoint did not return HTTP 200 THEN the system has no per-channel idempotency key, so duplicate suppression rests entirely on the single shared `postcall` claim described in 1.16.

1.20 WHEN an RCS notification is required on the Plivo path THEN none is sent. `send_rcs_ivr_notification` is invoked only from `whatsapp-calling/handler.py:710` and `:997`, `voice-in/cdr/handler.py:1155`, `voice-in/c2c/handler.py:1038` and `voice-in/obd/handler.py:1717`, and never from `plivo-answer`.

1.21 WHEN RCS is required for a non-Indian recipient THEN no implementation exists to send it: `docs/current-communications-architecture.md` records no AWS RCS provider, no `social-messaging` client and no RCS capability resolution, so every RCS message today is Sinch and only ever reaches an Indian number. `docs/provider-inventory.md` marks agent and pool registration as NEW and provider-approval gated.

1.22 WHEN the Airtel voice handlers are removed as scoped THEN the only RCS notification trigger is destroyed with them, because three of the five call sites in 1.20 (`voice-in/cdr`, `voice-in/c2c`, `voice-in/obd`) are Airtel voice handlers slated for deletion. The coupling is present in the code today and forces an ordering constraint on the removal.

Prohibited surfaces still deployed — previously counted only in aggregate by 1.12.

1.23 WHEN Airtel voice is invoked THEN it still runs: three Lambdas (`voice-in/c2c`, `voice-in/obd`, `voice-in/cdr`), four DynamoDB models (`AirtelC2C`, `VoiceCDR`, `OBDCampaign`, `AirtelSMS`) and four webhook endpoints, per `docs/migration-plan.md:347`, plus the Airtel-backed `outbound-voice` path.

1.24 WHEN SMS leaves the platform through the deprecated route THEN it can still traverse the port 8899 proxy, referenced at `sms-in/airtel/handler.py:90,99,122`, `outbound-sms/handler.py:51-52`, `whatsapp-calling/handler.py:1329`, `voice-in/cdr/handler.py:1304`, `scripts/check-provider-policy.sh:115`, `src/pages/dashboard/index.tsx:2619-2622` and steering file `.kiro/steering/AIRTEL-IQ-SMS-REPLY-EMAIL.md`, so `SMS_PROXY_URL` and its firewall opening remain live infrastructure rather than dead configuration.

1.25 WHEN an operator uses the UI THEN prohibited providers remain selectable: `/dm/voice-in` is Airtel-specific, `/dm/sms` carries Airtel and Sinch SMS tabs, and dashboard and architecture pages still present Airtel sections.

1.26 WHEN the removal scope is derived from the Airtel handler list THEN `voice-in/cdr` appears removable in full, but `VoiceCDRTable` is also the table `plivo-answer._persist_cdr` writes and the table `voice-cdr-read` serves, so a literal removal of that handler and its model breaks the CDR behaviour preserved by clause 3.9.

PSTN operator surface — split, incomplete, and about to lose a route.

1.27 WHEN an operator works on PSTN voice THEN the surface is split across `/dm/voice` and `/dm/voice-in`, the second of which is Airtel-specific, so removing Airtel leaves a dead route with no destination for its links.

1.28 WHEN an agent needs to place or take a PSTN call from the browser THEN no softphone exists: the repository contains no Plivo Browser SDK integration of any kind, no endpoint registration, no JWT login and no call-control surface. This is greenfield, measured as absent rather than assumed.

1.29 WHEN an operator needs to see connected-notification status, per-channel delivery outcome, provider drift status, hangup-cause distribution, recording access audit, browser and network readiness, or India and United States compliance posture THEN none of it is surfaced anywhere.

### Expected Behavior (Correct)

Control plane completeness.

2.1 WHEN an operator needs a single Zentrunk trunk by identifier THEN the system SHALL provide a single-trunk read that returns that trunk's discovery fields, read-only, without mutating it.

2.2 WHEN an operator invokes the control plane CLI THEN the system SHALL provide the full required command surface, including dedicated inspect commands for the application, the number, the endpoint and trunks, and a plan command for each mutable resource.

2.3 WHEN an approved number routing cutover is to be executed THEN the system SHALL provide a route-apply command that refuses to act without an explicit production approval flag, reports the before and after binding, and is never invoked by an ordinary backend deployment.

Guard enforcement.

2.4 WHEN the application is changed outside the control plane THEN the system SHALL detect the drift without human initiation, and SHALL report the exact field, current value, expected value and protected status of every divergence.

2.5 WHEN a change is pushed that breaks the `default_endpoint_app` guard, the read-back verifier or the signature validator THEN an automated pipeline SHALL execute the covering tests and SHALL fail, so the regression cannot reach the default branch silently.

2.6 WHEN the Plivo webhook configuration is rebuilt from the repository THEN the system SHALL define the answer, fallback, hangup and events routes declaratively, so the corrected URL state is reproducible and any divergence from live configuration is detectable.

Provider authentication.

2.7 WHEN an unsigned answer-style fetch arrives and no diagnostic token is configured THEN the system SHALL NOT report the request as verified, and SHALL make the unverified state explicit and alertable rather than treating absent configuration as permission.

2.8 WHEN a callback arrives carrying only the main-account signature header THEN the system SHALL validate it against the main-account token, so the mechanism remains correct if a subaccount is ever added.

SMS provider path.

2.9 WHEN an SMS send is requested through the live `/sms/send` route THEN the system SHALL send it through the SMS service and its AWS provider to AWS End User Messaging.

2.10 WHEN that route detects an Indian recipient THEN the system SHALL route to ap-south-1 and SHALL require an approved DLT template, with no Airtel attempt and no Sinch fallback, so `channel == SMS` implies `provider == AWS_END_USER_MESSAGING`; for any other market it SHALL route to the configured region, defaulting to us-east-1.

2.11 WHEN the dashboard sends an SMS THEN it SHALL reach AWS End User Messaging by the same single path, with no deprecated route reachable by any user action.

Deprecated provider removal.

2.12 WHEN the provider policy gate runs THEN it SHALL report zero violations, with Airtel SMS, Sinch SMS, Sinch Voice, Sinch WhatsApp, Plivo normal SMS and legacy non-End-User-Messaging AWS SMS transports absent from runtime code.

2.13 WHEN that gate runs in CI THEN it SHALL gate for real rather than inverting its result, so a reintroduced prohibited provider fails the pipeline.

### Unchanged Behavior (Regression Prevention)

Plivo resources that are currently correct and must stay correct.

3.1 WHEN any part of this fix is applied THEN the system SHALL CONTINUE TO report `default_endpoint_app` as true on application 12775976954213184.

3.2 WHEN any part of this fix is applied THEN the system SHALL CONTINUE TO bind number +918031830030 to the WECARE-WHATSAPP-IVR voice application, unchanged.

3.3 WHEN any part of this fix is applied THEN the system SHALL CONTINUE TO leave SIP endpoint WECARE-WhatsApp-IVR-SIP untouched, with its password unrotated and its application assignment unchanged.

3.4 WHEN SIP resources are reported THEN the system SHALL CONTINUE TO model the application SIP URI and the endpoint SIP URI as two distinct objects and SHALL CONTINUE TO never substitute one for the other.

3.5 WHEN application SIP is reported THEN the system SHALL CONTINUE TO verify it from API state rather than inferring it from the predictable URI format.

3.6 WHEN the protected field set is evaluated THEN the system SHALL CONTINUE TO leave application id, application name, `default_endpoint_app`, `default_number_app`, `enabled`, `public_uri`, `sip_uri`, `sip_auth_type`, `credential_uuid`, `ip_acl_uuid` and the subaccount relationship unchanged unless explicitly instructed.

3.7 WHEN Zentrunk is accessed THEN the system SHALL CONTINUE TO discover only, and SHALL CONTINUE TO create and mutate no production trunk outside an approved migration.

Route behaviour that is currently correct.

3.8 WHEN a genuine unsigned answer-style fetch arrives with a valid diagnostic token THEN the system SHALL CONTINUE TO serve the IVR, because Plivo does not sign answer_url fetches and requiring a signature there would drop every call.

3.9 WHEN a hangup callback arrives THEN the system SHALL CONTINUE TO require a valid signature, SHALL CONTINUE TO persist final CDR state, SHALL CONTINUE TO deduplicate by call identifier, SHALL CONTINUE TO return a 2xx, and SHALL CONTINUE TO never return the answer IVR.

3.10 WHEN a fallback request arrives THEN the system SHALL CONTINUE TO record the primary answer failure, return emergency XML that depends on no external media asset, and terminate cleanly.

3.11 WHEN an answer request is rejected THEN the system SHALL CONTINUE TO respond with XML rather than JSON, so the caller hears a clean hangup instead of silence.

3.12 WHEN a request arrives with an API Gateway stage prefix on its path THEN the system SHALL CONTINUE TO strip it for both routing and signature reconstruction, driven by the stage name rather than a hardcoded value.

3.13 WHEN a rejection is returned THEN the system SHALL CONTINUE TO withhold which check failed.

3.14 WHEN a signed callback arrives on a route that carries a side effect THEN the system SHALL CONTINUE TO accept a valid signature, reject an invalid signature, reject a tampered request and reject an unsigned request.

Safety properties of the control plane.

3.15 WHEN a control plane command is invoked without an explicit mutation flag THEN the system SHALL CONTINUE TO plan only and write nothing.

3.16 WHEN an update is applied THEN the system SHALL CONTINUE TO re-fetch the persisted object, compare the complete protected state, fail the deployment on any unexpected field change, attempt rollback, and report the exact diff.

3.17 WHEN Plivo state is reported THEN the system SHALL CONTINUE TO derive every line from live API state, and SHALL CONTINUE TO report per field the current value, the target value, whether it changes and whether it is protected.

3.18 WHEN a snapshot or report is written THEN the system SHALL CONTINUE TO record timestamp, resource type, resource id, current configuration, planned changes, git commit and environment, and SHALL CONTINUE TO contain no auth token, SIP password or other secret value.

3.19 WHEN Plivo credentials are needed THEN the system SHALL CONTINUE TO resolve them by reference at request time, never at module import, never from a command line, and never into a printed line or an artifact.

3.20 WHEN a URL carrying the diagnostic token is compared or reported THEN the system SHALL CONTINUE TO compare by path and represent the token only by fingerprint.

Adjacent production paths that are explicitly out of scope.

3.21 WHEN this fix is applied THEN Meta WhatsApp Calling SHALL CONTINUE TO route to sip.wecare.digital:5061 on the existing Lightsail Asterisk path, unchanged.

3.22 WHEN this fix is applied THEN Lightsail SHALL CONTINUE TO exist, because the Meta SIP path still requires it, notwithstanding removal of the Airtel SMS proxy usage.


3.24 WHEN Sinch is used for India RCS THEN the system SHALL CONTINUE TO send that traffic through the approved RCS path, which remains permitted.

3.25 WHEN Plivo is used for voice, SIP and IVR THEN the system SHALL CONTINUE TO do so, and SHALL CONTINUE TO never use Plivo for SMS.

3.26 WHEN an Indian SMS is sent through the AWS path THEN the system SHALL CONTINUE TO attach the registered entity id and sender id and SHALL CONTINUE TO refuse a send that lacks an approved DLT template.

3.27 WHEN a non-Indian SMS is sent THEN the system SHALL CONTINUE TO pin the origination identity to the registered number rather than allowing the simulator to be selected.

## Bug Condition and Properties

Two independent bug conditions are in play. They are kept separate because they
have different blast radii and different approval requirements.

### Condition A — an unguarded Plivo control plane

```pascal
FUNCTION isBugCondition_A(X)
  INPUT:  X of type PlivoControlPlaneRequest
  OUTPUT: boolean

  // A Plivo state change or state read that no automated guard observes,
  // or a required control-plane operation that does not exist.
  RETURN (X.mutates_plivo_state AND NOT X.observed_by_automated_guard)
      OR (X.required_operation AND NOT X.operation_exists)
      OR (X.route_configuration AND NOT X.declared_in_repository)
END FUNCTION
```

```pascal
// Property: Fix Checking - guarded, complete, reproducible control plane
FOR ALL X WHERE isBugCondition_A(X) DO
  result ← controlPlane'(X)
  ASSERT result.operation_exists
     AND result.dry_run_is_default
     AND result.mutation_requires_explicit_flag
     AND result.read_back_verified
     AND result.protected_fields_unchanged
     AND result.reported_from_live_api_state
     AND result.guard_runs_without_human_initiation
END FOR
```

### Condition B — SMS not resolving to AWS End User Messaging

```pascal
FUNCTION isBugCondition_B(X)
  INPUT:  X of type OutboundMessage
  OUTPUT: boolean

  RETURN X.channel = SMS
     AND X.resolved_provider ≠ AWS_END_USER_MESSAGING
END FUNCTION
```

```pascal
// Property: Fix Checking - the SMS provider invariant
FOR ALL X WHERE isBugCondition_B(X) DO
  result ← smsService'(X)
  ASSERT result.provider = AWS_END_USER_MESSAGING
     AND result.region = (X.is_india ? "ap-south-1" : configured_region_or_us_east_1)
     AND (NOT X.is_india OR result.dlt_template_approved)
     AND NOT reachable(AIRTEL_SMS) AND NOT reachable(SINCH_SMS)
     AND NOT reachable(PLIVO_SMS)  AND NOT reachable(LEGACY_AWS_SMS_TRANSPORT)
END FOR
```

### Preservation goal

```pascal
// Property: Preservation Checking
FOR ALL X WHERE NOT isBugCondition_A(X) AND NOT isBugCondition_B(X) DO
  ASSERT F(X) = F'(X)
END FOR
```

Concretely, the preserved set includes every clause in section 3: the number
binding, the SIP endpoint, the two distinct SIP objects, the protected field set,
answer and fallback accepting unsigned fetches, hangup requiring a signature and
never returning the IVR, dry run as the default, the Meta Lightsail SIP path, the
existing ElevenLabs configuration, Sinch India RCS, Plivo voice, and the Indian
DLT gate.

## Acceptance Criteria

Verifiable by test or by a live API read. Not by a console screenshot.

### Automated tests

| # | Test | Verifies |
|---|------|----------|
| T1 | application read | 3.17 |
| T2 | application update planning emits current / target / change / protected per field | 3.17 |
| T3 | `default_endpoint_app` preserved through an apply | 3.1 |
| T4 | unexpected field change detected and reported as a diff | 3.16 |
| T5 | read-back verification; HTTP 202 alone is not success | 3.16 |
| T6 | number read | 2.2 |
| T7 | number routing guard refuses without explicit approval | 2.3 |
| T8 | endpoint read locates by username or alias, never by position | 2.2, 3.3 |
| T9 | application SIP and endpoint SIP never conflated | 3.4, 3.5 |
| T10 | single-trunk read returns discovery fields and mutates nothing | 2.1, 3.7 |
| T11 | Zentrunk discovery reports per-collection status without raising | 3.7 |
| T12 | dry run never mutates | 3.15 |
| T13 | production apply requires an explicit flag | 2.3, 3.15 |
| T14 | V3 signature: valid accepted | 3.14 |
| T15 | V3 signature: invalid rejected | 3.14 |
| T16 | V3 signature: tampered request rejected | 3.14 |
| T17 | V3 signature: unsigned request rejected on side-effect routes | 3.14 |
| T18 | main-account signature header validated with the main-account token | 2.8 |
| T19 | unconfigured token does not yield a verified verdict | 2.7 |
| T20 | unsigned answer-style fetch with a valid token still serves the IVR | 3.8 |
| T21 | SMS provider invariant: `channel == SMS` implies AWS End User Messaging | 2.9, 2.10 |
| T22 | India routes to ap-south-1 and requires DLT; other markets to configured region | 2.10, 3.26 |
| T23 | no Airtel, Sinch SMS, Plivo SMS or legacy AWS SMS transport reachable | 2.11, 2.12 |
| T24 | snapshot contains no secret value | 3.18 |
| T25 | webhook route definitions in the repository match live configuration | 2.6 |

### Gates

- The provider policy gate reports zero violations and runs in real gating mode, not inverted. (2.12, 2.13)
- An automated pipeline executes the test suite and fails on regression. (2.5)
- A reconciliation runs without human initiation and reports drift. (2.4)

### Live state report, read from the API

```
PLIVO APPLICATION 12775976954213184 WECARE-WHATSAPP-IVR
  Answer                                           PASS
  Fallback                                         PASS
  Hangup                                           PASS
  default_endpoint_app true                        PASS
  Number binding +918031830030 unchanged           PASS
  SIP Endpoint WECARE-WhatsApp-IVR-SIP unchanged    PASS
  Application SIP verified                         PASS / WARNING
  Zentrunk discovered                              PASS
  ElevenLabs production routing                    NOT CHANGED
  Meta routing                                     NOT CHANGED
```

## Out of Scope

Each item is excluded deliberately, not overlooked.

- Number routing cutover of +918031830030 to a Zentrunk. A production cutover requiring its own plan, its own apply command and explicit production approval. Existing routing stays while the Plivo IVR works, Meta remains on Lightsail and ElevenLabs is under test.
- Creating or mutating any production Zentrunk. Discovery only.
- Any ElevenLabs change. It already exists and is not recreated. A working webhook does not prove the SIP route works; a live cutover would first require verification of India-resident SIP deployment, Plivo India routing requirements, trunk hostname, signalling, media, TLS, SRTP where applicable, codec compatibility, a real test call, the post-call webhook and CDR persistence.
- Any Meta SIP change. Production stays Meta WhatsApp Calling to sip.wecare.digital:5061 on Lightsail Asterisk. Meta direct to Plivo is a future experiment, never a completion requirement.
- Deleting Lightsail. Still required for the Meta SIP path.
- Obtaining a Sinch SMS OAuth token. Sinch SMS is deprecated and its inability to send is irrelevant to the target architecture.
- Rotating the SIP endpoint password or changing its application assignment.
