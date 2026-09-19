# Plivo PSTN and Browser Calling Migration Design

Date: 2026-09-19
Status: Approved design; implementation not yet authorized by this document

## Objective

Replace the active Airtel voice and SMS implementation and all Sinch SMS paths with a provider-safe communications architecture. Plivo owns PSTN voice and browser calling, AWS End User Messaging owns SMS, Sinch is restricted to India RCS, AWS owns non-India RCS, and Meta continues to own WhatsApp messaging and WhatsApp Calling through the existing Lightsail Asterisk server.

This design deliberately separates Plivo PSTN/browser calling from Meta WhatsApp Calling. The Lightsail Asterisk instance must remain because it terminates Meta WhatsApp Calling at `sip.wecare.digital:5061`; it is not part of the Plivo browser softphone path.

## Authoritative Provider Matrix

| Capability | Approved provider and route |
|---|---|
| PSTN voice | Plivo Voice API, XML and Browser SDK |
| India SMS (`+91`) | AWS End User Messaging in `ap-south-1`, approved DLT template required |
| Non-India SMS | AWS End User Messaging in the configured regional deployment, default `us-east-1` |
| India RCS | Sinch RCS only |
| Non-India RCS | AWS End User Messaging RCS |
| WhatsApp messaging | Meta directly |
| WhatsApp Calling | Meta to `sip.wecare.digital:5061` to Lightsail Asterisk |
| Airtel | Discontinued from active runtime, infrastructure, UI, IAM, secrets, scripts and monitoring |
| Sinch SMS | Prohibited |
| Sinch Voice or WhatsApp | Prohibited |
| Plivo SMS | Prohibited |

Historical Airtel call and message records remain read-only until they are exported, checksummed, retained according to policy, and separately approved for deletion. Removing a provider from active use must not destroy audit history.

## Existing Plivo Invariants

The repository's Plivo API/SDK reconciliation tooling, not the Plivo console, is the control-plane source of truth. Preserve these known resources and protected fields unless an explicit production plan is approved:

- Application ID `12775976954213184`, name `WECARE-WHATSAPP-IVR`
- Application SIP URI `sip:12775976954213184@app.plivo.com`
- Number `+91 80 3183 0030`
- Endpoint alias `WECARE-WhatsApp-IVR-SIP`
- Endpoint SIP URI `sip:wecarewaivr203331794466262@phone.plivo.com`
- `default_endpoint_app=true`
- Existing answer, fallback and hangup URL methods remain `POST`
- Current number-to-application binding remains unchanged until a separately reviewed production cutover

All control-plane changes require snapshot, redacted plan, dry run, protected-field validation, apply, readback verification, drift detection and rollback instructions. Number routing is a high-risk operation and is never changed as a side effect of deploying code.

## Target Voice Architecture

### PSTN and browser agents

```text
PSTN caller
  -> Plivo number +91 80 3183 0030
  -> Plivo application
  -> signed POST /plivo/answer
  -> feature-flagged Plivo XML <Dial><User>...</User></Dial>
  -> authenticated Plivo Browser SDK agent
  -> signed dial/event/hangup callbacks
  -> provider-neutral call event store and operational UI
```

The existing greeting-and-hangup response remains the safe default while `PSTN_BROWSER_ROUTING_ENABLED=false`. Browser routing is enabled only after staging validation and explicit cutover approval.

Outbound browser calls use the authenticated Browser SDK endpoint and Plivo PSTN. Each billed leg is recorded separately. Do not route Plivo calls through Asterisk merely to reuse the WhatsApp infrastructure.

### WhatsApp Calling

```text
WhatsApp caller
  -> Meta WhatsApp Calling
  -> TLS SIP sip.wecare.digital:5061
  -> Lightsail Asterisk
  -> existing WhatsApp call flow
```

Do not insert Plivo, Sinch or Airtel into this flow, and do not delete Lightsail/Asterisk.

## Connected-Call Notifications

The server-side Plivo `<Dial callbackUrl>` with `DialAction=connected` is authoritative. The Browser SDK `onCallConnected` event is not authoritative for outbound answer state because it can occur while the remote destination is still ringing.

For each real connected call:

1. Validate the Plivo V3 webhook signature against the exact public URL and unmodified request parameters/body.
2. Normalize `CallUUID`, A-leg and B-leg identifiers and caller number.
3. Atomically claim one idempotency key per notification channel. A representative form is `plivo-connected:{CallUUID}:{channel}:v1`.
4. If the idempotency store is unavailable, fail closed and return a retryable `5xx`; never send first and record later.
5. Send AWS SMS independently:
   - `+91`: `ap-south-1`, approved DLT entity/template/sender metadata required.
   - Other countries: configured regional sender, default `us-east-1`.
6. Send RCS independently:
   - Eligible `+91`: Sinch RCS.
   - Eligible non-India: AWS End User Messaging RCS.
   - Record an explicit ineligible/unsupported status when RCS cannot be sent.
7. Persist attempt count, provider request ID, delivery state, timestamps and sanitized error category for each channel.
8. Return success only after durable claim and dispatch state are recorded. Retries resume unfinished channels without duplicating completed ones.

Hangup callbacks must never trigger the connected notification. SMS failure must not suppress RCS, and RCS failure must not duplicate or suppress SMS.

## Browser SDK Design

- Pin stable `plivo-browser-sdk` version `2.2.21`; do not use a floating CDN or beta release.
- Generate short-lived Plivo JWTs only on the server. Use a five-minute default lifetime and never exceed 24 hours.
- Do not expose Auth ID, Auth Token, signing secrets or long-lived endpoint credentials to the browser.
- Allocate a unique Plivo endpoint identity per concurrently signed-in browser session so incoming calls are deterministic.
- Select `south_asia` where supported and verify the account/number region before production rollout.
- Support one active answered call per client. Define behavior for a second incoming or outbound attempt.
- Implement sign-in/token refresh, ready/offline state, incoming call, answer, reject, outgoing call, cancel, mute/unmute, DTMF, hangup, reconnect, device/microphone selection where supported, and actionable error states.
- Display browser/network readiness using documented quality thresholds. Budget at least 50 Kbps in each direction; flag jitter over 30 ms or RTT over 300 ms as poor.
- Treat mobile browser support as limited. Do not build on deprecated Plivo mobile SDKs; include them only as a migration warning in the developer reference.
- Reconcile security headers: `next.config.js` already allows `microphone=(self)`, while `amplify.yml` currently disables the microphone. Deployment must emit `Permissions-Policy: camera=(), microphone=(self), geolocation=()` and verify the live response header.

## Backend and Data Boundaries

Public provider callback routes include answer, fallback, hangup, dial events, general call events and stream events. They require signature verification or an explicitly documented bootstrap token where Plivo does not sign. They are rate-limited, schema-validated, idempotent and auditable.

Authenticated internal APIs include browser token issuance, agent presence, call lists/details, outbound initiation and controls, recordings, analytics and read-only resource/drift inspection. Cognito authentication and server-side Admin/Operator/Partner/Viewer authorization are mandatory; hiding controls in the frontend is not authorization. Apply or control-plane mutation endpoints are Admin-only, require a reviewed plan identifier and must be disabled by default in production.

Use provider-neutral records:

- `PstnCall`: provider IDs, direction, parties, agent/session, state, A/B legs, timestamps, billable durations, rates/cost, hangup cause, recording reference, quality and retention metadata.
- `PstnCallEvent`: normalized lifecycle event plus sanitized raw-event reference and dedup key.
- `PstnAgentPresence`: endpoint/session, readiness, availability and heartbeat expiry.
- `PstnNotificationDelivery`: call/channel idempotency, eligibility, attempts, provider message ID and delivery state.
- `PstnFlowVersion`: immutable routing/IVR configuration revisions with author, diff and activation state.
- `PstnRecordingAudit`: access, playback, export and deletion events.
- `ProviderDriftSnapshot`: desired/actual redacted state, differences and reconciliation status.

Existing `AirtelSMS`, `AirtelC2C` and provider-specific CDR data must be exposed through read-only compatibility/import views until retention decisions are complete. Do not silently relabel legacy Airtel events as Plivo events.

## Internal Product Information Architecture

Add `Messages > PSTN Voice` with these routes:

- `/dm/pstn`: overview, Browser Softphone, incoming queue, agent availability, active/recent calls and connected-notification status.
- `/dm/pstn/calls`: All, Incoming, Outgoing, Active, Failed, CDR, Hangup Causes and Notification Status.
- `/dm/pstn/flows`: call routing, IVR, input collection, audio output, recording, audio streaming, XML preview and version history.
- `/dm/pstn/collaboration`: conferences, multi-party calls, participants, history and permitted controls.
- `/dm/pstn/resources`: application, number, browser endpoints, SIP resources, trunks, verified caller IDs, webhooks and drift status.
- `/dm/pstn/recordings`: recordings, storage, retention and audit.
- `/dm/pstn/analytics`: volume, answer rate, duration, agent metrics, quality, failures, cost estimates, notifications and health.
- `/dm/pstn/troubleshooting`: live diagnostics, call failures, hangup causes, browser readiness, webhook/signature health, network and drift.
- `/dm/pstn/compliance`: India, US, consent, DLT, retention, geo permissions and audit.
- `/dm/pstn/developer`: API/XML references, Browser SDK, callbacks, SDK version, tutorials and migration guides.
- `/dm/pstn/settings`: general, agents, Browser SDK, routing, notifications, security, webhooks, number, costs and feature flags.

Redirect `/dm/voice` to `/dm/pstn` and `/dm/voice-in` to `/dm/pstn/calls`. Build on the existing `PageShell`, navigation configuration and UI primitives. Use real APIs with honest loading, empty, unavailable and error states; do not use fabricated production metrics.

## Plivo Feature Coverage

The internal developer and operations pages must cover the requested Plivo information architecture: core concepts, callbacks/webhooks, US and India compliance, security, call features, analytics; Calls, Audio Streams, Multiparty Calls, Conferences, Endpoints, Recordings and Verified Caller IDs APIs; XML overview, routing, input, audio output, conference, multi-party, record and streaming; Browser SDK and mobile-deprecation guidance; failures and hangup causes; inbound/outbound, IVR, recording, conferencing, routing and Raspberry Pi tutorials; Twilio migration and both SDK-upgrade guides.

Tutorials, Raspberry Pi, AI-coding-agent guidance and migration material are reference content, not fake live capabilities. Audio streaming must use `wss://`, an allowlisted destination, validated status callback, conservative PCM defaults and explicit bidirectional constraints. Never accept an arbitrary stream URL that creates an SSRF path.

India capacity must show and alarm on account-specific limits. Until verified otherwise, treat 50 concurrent calls and 2 CPS as defaults, warn at 80%, and surface Plivo error 5030 / Zentrunk 5190. India SIP media anchoring requirements mean the current US-hosted Asterisk must not be proposed as an Indian Plivo trunk endpoint.

Cost views separate estimates from actual CDR charges and show both legs. Seed estimates from current public India pricing only with an as-of date: PSTN ₹0.38/minute, Browser/WebRTC ₹0.25/minute, number ₹200/month and 30-second pulse. Never present estimates as invoices. Plivo-native WhatsApp is out of scope.

## Removal and Migration Rules

Inventory every Airtel and prohibited Sinch SMS reference before deleting. Remove active Lambdas, API routes, UI tabs, API clients, registry entries, IAM grants, proxy port `8899`, deploy scripts, alarms, runtime environment variables and secrets only after dependency checks. Remove provider choices from current runtime UI while retaining clearly labeled legacy history.

Consolidate SMS behind one AWS End User Messaging adapter with explicit region and DLT routing. Restrict the Sinch client and credentials to the India RCS module. Add compile-time/lint/policy tests that reject Airtel runtime identifiers, Sinch SMS/Voice/WhatsApp use and Plivo SMS use.

The current provider policy scan reports 160 findings and the CI workflow incorrectly expects failure. Reduce findings to zero, then change the workflow from `--expect-fail` to a real blocking gate. Add a general CI workflow for frontend tests/typecheck, Python tests, provider policy, dependency/security checks and infrastructure synthesis/validation.

## Delivery Stages and Production Gates

1. Capture inventory, architecture decision records, baselines and rollback plans; add regression tests before behavior changes.
2. Complete the AWS SMS adapter and India/non-India/DLT tests.
3. Eliminate Sinch SMS and isolate Sinch to India RCS.
4. Remove Airtel active voice/SMS paths while preserving historical data.
5. Make Plivo callbacks/resources declarative, close fail-open diagnostics, add inspect/plan/apply and scheduled drift checks.
6. Add provider-neutral models and APIs.
7. Add the Browser SDK softphone behind a disabled feature flag and fix deployed microphone policy.
8. Add exactly-once connected SMS/RCS orchestration and delivery observability.
9. Build all internal PSTN pages and redirects.
10. Run staging call matrices, security/compliance checks, load/rate tests and rollback exercises.
11. Present a redacted production cutover plan. Do not change the live number binding or enable browser routing without explicit approval.
12. After monitored cutover, remove verified unused secrets/resources and complete documentation reconciliation.

External provider approvals or unavailable credentials are reported as `WAITING_FOR_PROVIDER` with an owner and exact unblock action; they are not reported as complete.

## Verification and Definition of Done

The pre-change baseline is 883 passing Python tests, 29 passing frontend tests across seven files, and a passing TypeScript typecheck. Preserve or improve it.

Acceptance requires:

- Zero provider-policy findings and a blocking CI gate.
- No active Airtel code/resource/secret/IAM/UI/proxy route, with legacy audit data retained.
- No Sinch SMS, Sinch Voice/WhatsApp or Plivo SMS call sites or credentials.
- Correct AWS SMS routing and mandatory India DLT validation.
- Correct RCS provider selection and per-channel idempotency.
- Valid Plivo V3 signature tests, replay tests and fail-closed store-failure tests.
- Browser token, incoming, outgoing, rejection, cancellation, DTMF, mute, hangup, reconnect, expired-token and concurrency tests.
- Verified deployed microphone policy and supported-browser readiness checks.
- Answer/fallback/hangup/dial/stream callback contract tests and call-state transition tests.
- Role/tenant authorization tests for every internal API and destructive control.
- Redacted drift detection and protected-field regression tests.
- No automatic number-routing mutation or production flag activation.
- Documentation matches runtime and contains no unresolved placeholder presented as completed work.

Implementation reporting must list changed files, migrations, resources removed/retained, test results, policy results, drift output, security checks, cost assumptions, manual provider actions, rollback commands and every pending production approval.
