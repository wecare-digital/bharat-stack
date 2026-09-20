# Plivo API Control Plane Fix — Bugfix Design

## Overview

Thirteen residual defects remain after measurement removed three reported ones.
They fall into six classes, and the classes matter more than the count because
they have different blast radii and different approval requirements.

1. **Control-plane completeness** (1.1–1.3). `PlivoControlPlaneService` has no
   single-trunk read, and `scripts/plivo-reconcile` exposes flag verbs rather
   than the resource/verb surface 2.2 requires, with no operator route to the
   guarded number-routing apply.
2. **Guard execution** (1.4, 1.5). The guards exist and pass. Nothing runs them:
   no workflow in `.github/workflows/` executes pytest, and no schedule executes
   a reconcile.
3. **Route declaration** (1.6). The four webhook routes exist only as live
   configuration. `plivo-answer` has no `resource.ts`, and the HTTP API
   (`zllr9lrg7j`, 345 routes) is not under IaC at all.
4. **Provider gate fails open** (1.7, 1.8). `_verify_provider` returns
   `(True, 'unverified_no_token_configured')` when no diagnostic token is
   configured, and never passes `main_auth_token` to the verifier that already
   accepts it.
5. **SMS provider path** (1.9–1.11). `POST /sms/send` → `wecare-outbound-sms:live`
   still defaults Indian traffic to Airtel with a Sinch fallback. The
   provider-neutral `SmsService` / `AwsSmsProvider` layer already exists and is
   fully tested, but **no Lambda imports it yet**.
6. **Deprecated provider removal and the disarmed gate** (1.12, 1.13). 160
   violations across 6 rules, with `provider-policy.yml` running
   `--expect-fail`, so CI reports success while every violation stands.

The fix strategy is *extension, not replacement*. Every asset the defects need
already exists in some form:

| Asset | State | This fix |
|---|---|---|
| `scripts/plivo_control_plane.py` | 8 reads, plan/apply/verify/rollback | add `get_trunk`, `list_subaccounts`, `drift_report`; split the read core into a shared module |
| `scripts/plivo-reconcile` | 5 flag verbs | add subcommands, keep flags as aliases |
| `amplify/functions/shared/lambda_utils/plivo_signature.py` | V3 + Ma-V3, SDK cross-checked | unchanged; the handler starts passing `main_auth_token` |
| `amplify/functions/shared/lambda_utils/comms/` | `SmsService`, `AwsSmsProvider`, region, DLT, E.164 | unchanged; `outbound-sms` starts importing it |
| Existing tests | measured **883 passing in 5.12 s**; 153 Plivo + 98 SMS-layer | extended, one amended (T19), none deleted |
| `scripts/check-provider-policy.sh` | 6 rules, `--expect-fail` inverts | rule set split, baseline mode, then real gating |

Nothing here changes what a caller hears, what number `+918031830030` is bound
to, or any Plivo protected field. The only production behaviour that changes on
purpose is the SMS transport for Indian sends through `/sms/send`.

**No application code is written in this phase.** This document is the plan.

### Measurement provenance

Every live figure below was read on 2026-09-19 from account `775261844268`,
`us-east-1`, profile `wecare-prod`, via the AWS API — not from a console
screenshot and not from memory.

```
HTTP API zllr9lrg7j                    345 routes, 102 integrations, stage prod (autoDeploy)
POST /plivo/{answer,fallback,hangup,events}  -> wecare-plivo-answer:live
POST /sms/send                          -> wecare-outbound-sms:live
wecare-plivo-answer                     python3.12, 15 s, 256 MB, 0 layers,
                                        role wecare-digital-lambda-role,
                                        SnapStart None/Off, live -> version 7
wecare-outbound-sms                     live -> version 7
EventBridge rules                       6; three on rate(1 day): docs-scraper,
                                        media-cleanup, partner-token-refresh
EventBridge Scheduler schedules         0
CloudWatch alarms                       42
CloudWatch Logs metric filters          4, all named webhook-dedup-error
SNS wecare-alarm-notifications          1 email subscription
IAM OIDC providers                      0
wecare-digital-lambda-role              WECARESecretsReadOnly-20260917 grants
                                        GetSecretValue on wecare/plivo/api;
                                        wecare-digital-lambda-permissions grants
                                        cloudwatch:PutMetricData and sns:Publish
Provider policy gate                    160 violations / 6 rules
pytest                                  883 passed, 5.12 s
tsc --noEmit                            clean
vitest run                              29 passed, 7 files
eslint .                                314 problems, 250 errors  <-- currently RED
```

## Glossary

- **Bug_Condition (C)** — an input for which the system is defective. Two
  independent conditions are in play, `C_A` (unguarded/incomplete/undeclared
  Plivo control plane) and `C_B` (an SMS send that does not resolve to AWS End
  User Messaging).
- **Property (P)** — the required behaviour for inputs satisfying C.
- **Preservation** — for `¬C_A ∧ ¬C_B`, `F(X) = F'(X)`. Concretely every clause
  in bugfix section 3 (3.1–3.27).
- **Protected field** — one of the eleven fields in
  `plivo_control_plane.PROTECTED_FIELDS`, never changed by a reconcile.
- **Critical invariant** — `CRITICAL_INVARIANTS = {"default_endpoint_app": True}`.
  The one field with a known regression history: a partial Application update
  reset it to false on 2026-09-19.
- **Drift** — a difference between live Plivo/API-Gateway state and the
  repository's declared target state, whether or not it is in a protected field.
- **Answer-style fetch** — an `answer_url` or `fallback_answer_url` request.
  Plivo does **not** sign these. Only callbacks carry `X-Plivo-Signature-V3`.
- **`live` alias** — the Lambda alias the HTTP API integrates. `$LATEST` changes
  do not reach production until a version is published and the alias moves
  (`.kiro/steering/lambda-snapstart-deploy.md`). SnapStart is off on all 62
  functions; the alias, not SnapStart, is what makes the publish mandatory.
- **Gating rule** — a provider-policy rule that must read zero and fails CI
  above zero. **Tracked rule** — one with a pinned baseline count, which fails
  if the count rises, and fails when it reaches zero so it can be promoted.
- **`_verify_provider`** — `plivo-answer/handler.py`. Returns `(ok, mechanism)`
  today; becomes a three-state verdict.
- **`SmsService` / `AwsSmsProvider`** — `lambda_utils/comms/sms.py`. The
  provider-neutral contract and its only implementation, `pinpoint-sms-voice-v2`.

## Bug Details

### Bug Condition

Two conditions, restated from the requirements and used verbatim by the tests.

`C_A` holds when a Plivo state change or state read escapes automated
observation, when a required control-plane operation does not exist, or when
route configuration lives only at the provider. `C_B` holds when an SMS send
resolves to any provider other than AWS End User Messaging.

**Formal Specification:**

```
FUNCTION isBugCondition(input)
  INPUT:  input of type PlivoControlPlaneRequest | OutboundMessage
  OUTPUT: boolean

  RETURN isBugCondition_A(input) OR isBugCondition_B(input)
END FUNCTION

FUNCTION isBugCondition_A(X)
  INPUT:  X of type PlivoControlPlaneRequest
  OUTPUT: boolean

  RETURN (X.mutates_plivo_state  AND NOT X.observed_by_automated_guard)
      OR (X.required_operation   AND NOT X.operation_exists)
      OR (X.route_configuration  AND NOT X.declared_in_repository)
      OR (X.is_provider_verification AND X.verdict = VERIFIED
                                     AND NOT X.evidence_established)
END FUNCTION

FUNCTION isBugCondition_B(X)
  INPUT:  X of type OutboundMessage
  OUTPUT: boolean

  RETURN X.channel = SMS
     AND X.resolved_provider != AWS_END_USER_MESSAGING
END FUNCTION
```

The fourth disjunct in `isBugCondition_A` is the one the requirements express as
1.7 and 1.8. A verdict of VERIFIED with no evidence behind it is a control-plane
defect of the same kind as an unobserved mutation: the system asserts a fact it
has not established.

### Examples

Concrete manifestations, each measured rather than supposed.

**1.1 — no single-trunk read.** `PlivoControlPlaneService` exposes `list_trunks()`
only, which walks three Zentrunk collections. Expected: `get_trunk("<id>")`
returns that trunk's `TRUNK_FIELDS` projection. Actual: the caller must retrieve
every trunk and filter in application code.

**1.2 — no dedicated inspect commands.** `./scripts/plivo-reconcile --trunks`
exists; `plivo-reconcile number inspect`, `endpoint inspect`, `trunk inspect`
do not. Expected: a resource/verb surface. Actual: the number and endpoint are
visible only as a side effect of the combined `inspect` snapshot render.

**1.3 — no operator route-apply.** `apply_number_routing_change(target_app_id,
approved=True)` exists in the service and is tested, but no CLI verb reaches it.
Expected: `plivo-reconcile number route-apply --to-trunk <id>
--approve-production-routing`. Actual: the only route to a guarded production
mutation is ad-hoc code, which is the least reviewable option available.

**1.4 — drift invisible until a human looks.** `ListRules` returns 6 EventBridge
rules and none mention Plivo; `ListSchedules` returns 0. Expected: a scheduled
reconcile reporting field / current / expected / protected per divergence.
Actual: a console edit clearing `default_endpoint_app` — the exact regression of
2026-09-19 — is detected only if someone runs `plivo-reconcile`.

**1.5 — no pipeline runs the tests.** `.github/workflows/` holds `codeql.yml`,
`deps-upgrade.yml`, `docs-scraper-deploy.yml`,
`google-workspace-route53-once.yml`, `provider-policy.yml`. `grep -l pytest`
across all five returns nothing. Expected: a push or PR that breaks the
`default_endpoint_app` guard, the read-back verifier or the V3 validator fails a
pipeline. Actual: 883 green tests that nothing executes outside a developer's
shell.

**1.6 — route state not reproducible.** No `resource.ts` under
`amplify/functions/messaging/plivo-answer/`. `scripts/sync_webhook_registry.py`
lists `/plivo/answer` only, and describes its auth as
`optional ?token= (PLIVO_ANSWER_TOKEN); Plivo does not sign answer_url` — stale
since V3 validation landed. Expected: the four routes declared, diffable against
live. Actual: the corrected URL state exists only inside Plivo and inside a live
API Gateway.

**1.7 — the gate fails open.** `plivo-answer/handler.py`:

```python
    token = _get_answer_token()
    if not token:
        return True, 'unverified_no_token_configured'
```

Expected: not VERIFIED, and alertable. Actual: `ok=True`, the caller is served,
and `plivo_request` logs `auth=unverified_no_token_configured` at info level
where no metric, alarm or filter observes it. An absent secret becomes
permission.

**1.8 — main-account token never supplied.** `plivo_signature.verify_request`
signature is `(event, auth_token, main_auth_token="")`; the handler calls
`verify_request(event, auth_token)`. So `ma_token = main_auth_token or
auth_token` resolves to the subaccount token. Benign at 0 subaccounts; a genuine
Ma-V3 callback is rejected the day a subaccount exists.

**1.9/1.10 — Airtel is still the Indian default.** `outbound-sms/handler.py`:

```python
        if body.get('provider') == 'sinch':   provider = 'sinch'
        elif is_indian:                       provider = 'airtel'
        else:                                 provider = 'aws'
```

with a Sinch fallback at lines 185–194 and, for non-India, classic
`pinpoint.send_messages` or `sns.publish`. Expected: every branch resolves to
`pinpoint-sms-voice-v2`. Actual: `channel == SMS` implies AWS on no branch.

**1.11 — reachable from the dashboard.** `src/pages/dm/whatsapp/calling.tsx:625`
picks `/sms/send` for `provider === 'airtel'`; `src/pages/dm/sms/index.tsx:237`
posts `provider: 'sinch'` to the same route; `src/api/client.ts:1261`
`sendSinchSms()` does likewise. A normal button click reaches the deprecated
path.

**1.12/1.13 — 160 violations, reported as success.** Measured per rule:

| Rule | Total | In voice files | Frontend | Backend SMS |
|---|---|---|---|---|
| `airtel-runtime` | 111 | 40 | 12 | 59 |
| `airtel-sms-proxy` | 11 | 1 | 2 | 8 |
| `sinch-sms-sender` | 17 | 0 | 4 | 13 |
| `sinch-outside-rcs` | 3 | 1 | 2 | 0 |
| `legacy-aws-sms` | 9 | 0 | 0 | 9 |
| `sms-provider-literal` | 9 | 0 | 5 | 4 |
| **Total** | **160** | **42** | **25** | **93** |

`provider-policy.yml` runs `./scripts/check-provider-policy.sh --expect-fail
--verbose`, which exits 0 while violations exist. **Edge case that shapes the
design:** 40 of the 111 `airtel-runtime` violations are in
`voice-in/c2c`, `voice-in/obd` and `outbound-voice` — Airtel *voice*, which
`docs/provider-inventory.md` §5.2 and the migration-plan risk register both
declare a separate migration ("three Lambdas, three secrets, four DynamoDB
models, four webhook endpoints"). Requirement 2.12 enumerates only Airtel SMS
yet asks for zero violations. No amount of SMS work reaches zero. D7 resolves
this explicitly rather than by quietly allowlisting.

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**

- Plivo application `12775976954213184` reports `default_endpoint_app = true`,
  `enabled = true`, and all three URLs and methods as they are now (3.1).
- Number `+918031830030` stays bound to WECARE-WHATSAPP-IVR (3.2).
- SIP endpoint `WECARE-WhatsApp-IVR-SIP` is untouched: password unrotated,
  application assignment unchanged (3.3).
- The application SIP URI and the endpoint SIP URI remain two distinct modelled
  objects, never substituted (3.4), with application SIP verified from API state
  rather than inferred from the URI format (3.5).
- All eleven `PROTECTED_FIELDS` remain unchanged (3.6).
- Zentrunk stays discovery-only; no production trunk is created or mutated (3.7).
- A genuine unsigned answer-style fetch **with a valid diagnostic token** still
  serves the IVR (3.8). This is disjoint from the 2.7 condition, which is the
  case where *no token is configured at all*.
- Hangup requires a valid signature, persists final CDR state, dedupes by
  `CallUUID`, returns 2xx and never returns the answer IVR (3.9).
- Fallback records the primary failure and returns `<Speak>`-only emergency XML
  with no external media dependency (3.10).
- A rejected answer request returns XML, not JSON (3.11).
- The API Gateway stage prefix is stripped from `rawPath` for both routing and
  signature reconstruction, driven by `requestContext.stage` (3.12).
- Rejections withhold which check failed (3.13).
- Signed side-effect routes accept valid, reject invalid, tampered and unsigned
  (3.14).
- Dry run is the default; nothing writes without an explicit mutation verb
  (3.15).
- Apply re-fetches, compares the complete protected state, fails on any
  unexpected field change, attempts rollback and reports the exact diff (3.16).
- Reports derive every line from live API state with current / target / change /
  protected per field (3.17).
- Snapshots record provenance and contain no secret (3.18).
- Credentials resolve by reference at request time — never at module import,
  never from a command line, never into a log line or artifact (3.19).
- Token-bearing URLs compare by path and appear only as a fingerprint (3.20).
- Meta WhatsApp Calling keeps routing to `sip.wecare.digital:5061` on Lightsail
  Asterisk (3.21), and the Lightsail instance keeps existing (3.22).
- ElevenLabs phone number, agent, inbound enablement and SIP allowlist are used
  as found, with no recreation and no `0.0.0.0/0` (3.23).
- Sinch India RCS keeps sending through the approved path (3.24).
- Plivo keeps serving voice, SIP and IVR, and is never used for SMS (3.25).
- Indian AWS sends keep attaching the registered entity id and sender id and
  keep refusing a send with no approved DLT template (3.26).
- Non-Indian sends keep the origination identity pinned to `+18444891209`
  rather than letting AWS select the simulator `+14255556333` (3.27).

**Scope:**

Every input outside both bug conditions must be bit-identical. Specifically
unaffected:

- Any Plivo read that already exists (`get_application`, `get_endpoint`,
  `get_number`, `list_trunks`, `verify_application_sip`, `snapshot_current_state`).
- Any signed callback on `/plivo/hangup` or `/plivo/events`.
- Any answer-style fetch presenting a correct diagnostic token.
- Any non-SMS channel: WhatsApp via Meta, RCS via Sinch for India, voice/SIP/IVR
  via Plivo, email via SES.
- Airtel **voice** (C2C, OBD, CDR) — deliberately out of scope, and the reason
  D7 splits the gate rather than forcing it to zero.
- The 44 + 54 existing tests over `lambda_utils/comms` and `sms-aws` DLT. The
  SMS cutover inherits 3.26 and 3.27 from that layer instead of reimplementing
  them; if any of those tests change meaning, the cutover is wrong.

The actual required behaviour for buggy inputs is in Correctness Properties
below. This section is only about what must not move.

## Hypothesized Root Cause

Six causes, one per defect class. Each is a hypothesis to be confirmed or refuted
by the exploratory tests in the Testing Strategy, not an assertion.

1. **The control plane was built to fix one incident, so its surface is the shape
   of that incident** (1.1–1.3). The regression was a partial Application update
   clearing `default_endpoint_app`, so `plivo_control_plane.py` is deep on the
   Application object — plan, apply, read-back, rollback, protected-field diff —
   and thin everywhere else. Zentrunk got `list_trunks()` because discovery was
   the requirement; no single-trunk read was needed to close the incident.
   `plivo-reconcile` grew a flag per task in the order tasks arrived
   (`--dry-run`, `--apply`, `--number-plan`, `--trunks`), which is why there is a
   `--number-plan` but no `number route-apply`: planning was in scope, applying
   was not. The generalisation from "the incident" to "the resource surface"
   never happened.

2. **Guards were written as assertions, not as a running system** (1.4, 1.5).
   The repository has no CI test culture to attach to — `provider-policy.yml` is
   the only quality workflow and it is deliberately inverted. Adding tests to a
   repository with no test pipeline produces exactly this: 883 correct tests with
   no executor. Likewise the reconcile was designed as a command an operator
   invokes, and nothing promoted it to a schedule, because the operator running
   it was present throughout the incident.

3. **The HTTP API is not under IaC, so there was nowhere to declare a route**
   (1.6). 345 routes and 102 integrations on `zllr9lrg7j` are registered by
   imperative scripts (`scripts/register_task12_routes.py` is the pattern).
   `plivo-answer` has no `resource.ts` because `defineFunction` would declare the
   *function*, not the route, and the function already exists with a `live`
   alias — so a partial declaration looked worse than none. The result is that
   the one thing that actually broke (three URLs at the provider) has no
   repository representation at all.

4. **`require_signature=False` was overloaded to mean two different things**
   (1.7). It correctly means "Plivo does not sign this fetch, so absence of a
   signature is not evidence of forgery". It was then also read as "therefore any
   weaker gate, including no gate, is acceptable here". The code path makes that
   visible: the token branch returns `True` with the reason string
   `unverified_no_token_configured` — the author knew it was unverified and
   encoded that in the string, but the return type was a boolean, so there was no
   third state to return. **This is a type problem before it is a security
   problem.** The fix is to give the function the third state it needed.

5. **`main_auth_token` was added to the verifier and forgotten at the call site**
   (1.8). `plivo_signature.verify_request` takes it, documents why Ma-V3 differs,
   and defaults it to `""` with an `or auth_token` fallback that is *correct at
   zero subaccounts*. Because it is correct today, no test failed and no review
   caught it. A defaulted parameter that is benign under current configuration is
   the single most reliable way to ship a latent defect.

6. **The migration was sequenced correctly and then stalled at Stage 2**
   (1.9–1.13). `docs/migration-plan.md` Stage 2 builds the SMS abstraction;
   Stage 3 rewires callers and deletes Airtel and Sinch SMS. Stage 2 is complete:
   `lambda_utils/comms/` exists with 44 passing tests. Stage 3 has not started:
   `grep` shows **no Lambda imports `lambda_utils.comms`**. `--expect-fail` was
   an honest device for that window — it fails when violations reach zero, which
   is a real signal — but it has now been load-bearing long enough that the
   pipeline reports green with 160 violations, which is the failure mode it was
   supposed to avoid. And the rule set it gates was written against
   `docs/provider-policy.md`, **a file that does not exist in the repository**,
   so the one artefact that would adjudicate "does Airtel voice count?" is
   missing.

## Design Decisions

Seven decisions, each with the alternatives considered and the measurement that
settled it.

### D1 — The missing control-plane operations extend the existing service and CLI

**Decision.** Add `get_trunk(trunk_id)` and `list_subaccounts()` to
`PlivoControlPlaneService`. Split the **read-only** half of the service into
`amplify/functions/shared/lambda_utils/plivo_control_plane.py` and leave
`scripts/plivo_control_plane.py` as the mutation-capable superset that imports
it. Convert `scripts/plivo-reconcile` to an argparse **subcommand** surface,
retaining today's flags as deprecated aliases.

Target CLI surface:

```
plivo-reconcile                              # unchanged: full read-only inspect
plivo-reconcile application inspect | plan | apply
plivo-reconcile number      inspect | plan | route-apply --to-application ID
                                                         --to-trunk ID
                                                         --approve-production-routing
plivo-reconcile endpoint    inspect
plivo-reconcile trunk       inspect [TRUNK_ID] | list
plivo-reconcile drift [--json]               # same check the schedule runs
plivo-reconcile routes check                 # D3 manifest vs live
```

Flag aliases retained: `--dry-run` → `application plan`, `--apply` →
`application apply`, `--number-plan` → `number plan`, `--trunks` →
`trunk list`, `--json` on every verb.

**Dry run stays the default** (3.15). `plan` is the default verb for every
mutable resource; a bare `plivo-reconcile` is still the read-only snapshot.
`application apply` is itself the explicit mutation flag, unchanged from today.
`number route-apply` additionally requires `--approve-production-routing`, which
maps to `apply_number_routing_change(approved=True)` — so the production routing
mutation needs two deliberate tokens on the command line, and neither is a
default.

**Why the read/mutate split.** D2 puts the drift detector in a Lambda, which
needs the reads. Packaging the whole service would put `apply_application_update`,
`rollback_application_update` and `apply_number_routing_change` inside a function
invoked by a schedule. Physically removing them from the shared module is a
stronger guarantee than a flag: the scheduled code cannot mutate Plivo because
the methods are not in its import graph. `scripts/plivo_control_plane.py` keeps
re-exporting every existing name, so all 52 tests in
`tests/test_plivo_control_plane.py` and the CLI import unchanged.

**Alternatives considered.**

- *New standalone scripts per resource* (`scripts/plivo_trunks.py` etc.).
  Rejected: duplicates credential loading, `_strip_query`, `_token_fingerprint`
  and `_assert_sanitized` — four places for a secret to leak instead of one.
- *Keep flags, add `--trunk-id` / `--endpoint` / `--number`.* Rejected: 2.2 asks
  for dedicated commands, and flag combinations make mutation ambiguous. Today
  `--apply --number-plan` has undefined precedence; more flags makes that worse.
- *Move the whole service into `lambda_utils/`.* Rejected for the reason above.
- *Leave the CLI alone and document the service API.* Rejected: 1.3's actual harm
  is that the reviewable path does not exist, so operators write ad-hoc code
  against a production mutation. Documentation does not fix that.

**Unverified.** `GET /Zentrunk/Trunk/{trunk_id}/` returning 200 is **not
verified**. The existing comments record that `/Zentrunk/Trunk/` (collection)
returns 200 and that two other spellings 503 or reset, but the single-resource
path was never exercised, and confirming it needs the Plivo credential, which
`aws-agent-rules` forbids reading. `get_trunk` is therefore designed to try the
single-resource GET and, on any non-200, fall back to filtering `list_trunks()`
by `trunk_id`, reporting which path answered in a `source` field. It is correct
either way and it tells the operator which it used.

### D2 — Drift detection is an EventBridge-scheduled Lambda, and pytest runs in GitHub Actions

Two separate mechanisms, because 2.4 and 2.5 are different problems: 2.4 watches
*live provider state*, 2.5 watches *repository changes*.

#### 2.4 — `wecare-plivo-reconcile`, EventBridge `rate(1 hour)`

**Decision.** A new read-only Lambda `wecare-plivo-reconcile`, invoked by a new
EventBridge rule `wecare-plivo-reconcile-hourly`, importing the shared read
module from D1. It emits one structured log line per divergence carrying `field`,
`current`, `expected`, `protected`, `critical`, plus two custom metrics, plus two
alarms into the existing SNS topic.

**Why not GitHub Actions on a schedule.** Measured: `ListOpenIDConnectProviders`
returns **0** in account `775261844268`, and `docs-scraper-deploy.yml` says so in
a comment. So a scheduled workflow would authenticate with the existing static
`secrets.AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — a long-lived key for a
broad IAM identity, held in a third-party CI system, for a job that needs one
secret read and four Plivo GETs. Three further disqualifiers: GitHub disables
scheduled workflows after 60 days of repository inactivity, so the guard stops
silently, which is precisely the failure 2.4 exists to eliminate; a failing
scheduled workflow notifies repository watchers rather than routing into
`wecare-alarm-notifications` where the other 42 alarms land; and a public runner
would need network egress to `api.plivo.com` with no VPC control.

**Why not a Kiro hook.** `.kiro/hooks/block-inline-secrets.json` is the
precedent, and a hook is free. But a hook fires only when a developer has an IDE
session open in this workspace — that is human initiation with extra steps, and
it fails 2.4 by definition. A `SessionStart` hook that *displays the most recent
drift verdict* is a reasonable convenience and is listed as an optional P3
improvement, but it is not the guard.

**Why EventBridge + Lambda wins.**

- Runs in the account that owns the resource, on the schedule pattern already
  used by three rules (`wecare-docs-scraper-daily`, `wecare-media-cleanup-daily`,
  `wecare-partner-token-refresh-daily`).
- Credentials resolve by reference at request time via
  `boto3 secretsmanager get_secret_value(SecretId='wecare/plivo/api')` inside the
  function — never on a command line, never printed (3.19, and
  `.kiro/steering/secret-handling.md`).
- **No IAM change required.** `wecare-digital-lambda-role` already carries
  `WECARESecretsReadOnly-20260917`, which grants `GetSecretValue` +
  `DescribeSecret` on `arn:...secret:wecare/plivo/api-aIEx8b` and `kms:Decrypt`
  on the CMK. `wecare-digital-lambda-permissions` already grants
  `cloudwatch:PutMetricData` and `sns:Publish`. That removes the pointwise IAM
  confirmation the maintenance-reporting steering would otherwise require.
- Cannot expire from inactivity.

**Cadence.** `rate(1 hour)`. Cost is negligible (720 invocations/month, 4 Plivo
GETs each, one Secrets Manager read each). `rate(1 day)` matches the three
existing rules and was the alternative, but the failure this guard exists to
catch — `default_endpoint_app` cleared, which breaks SIP endpoint calling — is
worth 24× the detection speed. If Plivo rate limits ever object, dropping to
`rate(6 hours)` is a one-field rule edit.

**Reporting shape, satisfying 2.4's "exact field, current value, expected value,
protected status".** One log event per divergence:

```json
{"event":"plivo_drift","field":"default_endpoint_app","current":false,
 "expected":true,"protected":true,"critical":true,
 "alert":"PLIVO_DRIFT_CRITICAL_INVARIANT"}
```

Secret safety in that payload is inherited, not reinvented: URL fields go through
`_strip_query` and carry a `_token` fingerprint from `_token_fingerprint` (3.20),
and `_assert_sanitized` runs over the whole report before anything is logged
(3.18). A drift report that leaked the auth token would be worse than no drift
report.

Metrics and alarms, namespace `WECARE.DIGITAL`, mirroring the
`webhook-dedup-error` precedent:

| Metric | Alarm | Threshold |
|---|---|---|
| `PlivoDriftFields` | `wecare-plivo-drift` | Sum > 0 over 1 h, 1 period |
| `PlivoCriticalInvariantBreached` | `wecare-plivo-critical-invariant` | Max ≥ 1 over 1 h, 1 period |
| `PlivoReconcileFailed` | `wecare-plivo-reconcile-failed` | Sum > 0 over 3 h, 1 period |

All three with `TreatMissingData=notBreaching` and `AlarmActions=[
arn:aws:sns:us-east-1:775261844268:wecare-alarm-notifications]` (1 email
subscriber, verified). The third alarm exists because a guard that stops running
must itself be noticed — otherwise `PlivoDriftFields` sitting at zero is
indistinguishable from a dead Lambda.

The Lambda also reports `subaccount_count` from `list_subaccounts()`. When it is
greater than zero **and** `main_auth_token` is unconfigured, that is itself a
drift finding — which is how D5 stays correct by detection rather than by hope.

Creation script: `scripts/create_plivo_drift_alarms.py`, modelled directly on
`scripts/_create_dedup_alarm.py` (idempotent `put_metric_filter` /
`put_metric_alarm` upserts, then a `describe_alarms` read-back). Alarm shape is
also recorded in `amplify/monitoring/alarms.ts` for consistency with the five
alarms already declared there, acknowledging that file is currently descriptive
rather than deployed.

#### 2.5 — `.github/workflows/tests.yml`, pytest only

**Decision.** A new workflow on `pull_request` and `push` to `stack`, plus
`workflow_dispatch`, running Python 3.12, `pip install -r requirements-dev.txt`,
then `pytest` (bare — `pytest.ini` sets `testpaths = tests amplify/functions` and
`--import-mode=importlib`). Plus `npx tsc --noEmit` and `npx vitest run`.
**No AWS credentials**: the suite is fully offline, measured at 883 passed in
5.12 s with the network unused.

**eslint is deliberately excluded.** Measured now: `npx eslint .` reports **314
problems, 250 errors**. Adding it would make the new pipeline red on its first
run for reasons with no connection to this fix — the exact trap the sequencing in
D7 is built to avoid. `tsc --noEmit` is clean and `vitest run` is green (29
tests, 7 files), so both are safe to gate today. eslint gets a separate
non-gating job and a P2 improvement to drive the 250 errors down.

**Alternatives considered.** Running the Python tests inside the existing
`provider-policy.yml` job — rejected, because that workflow's exit semantics are
about to change twice (D7) and coupling the test gate to it would make a test
failure and a policy failure indistinguishable. Amplify build hooks — rejected:
Amplify builds the frontend from `stack` after merge, which is too late to keep a
regression off the default branch.

### D3 — Webhook routes become a manifest, and the diff is part of the drift check

**Decision.** Three artefacts.

1. **`amplify/webhook-routes.json`** — the declarative definition. One entry per
   route: `routeKey`, `function`, `alias`, `path`, `signatureRequired`,
   `providerField`, `configuredAtProvider`.
2. **`scripts/webhook_routes.py`** — loads the manifest and diffs it against live
   in two directions: API Gateway (`GetRoutes` + `GetIntegrations` on
   `zllr9lrg7j`, matching `routeKey` → integration URI ending `:live`) and Plivo
   (`answer_url`, `fallback_answer_url`, `hangup_url` compared by **path only**,
   token by fingerprint). Exposed as `plivo-reconcile routes check` and imported
   by the drift Lambda, so T25 runs hourly and not only on demand.
3. **`amplify/functions/messaging/plivo-answer/resource.ts`** — the function's
   own configuration, matching fleet convention: name `wecare-plivo-answer`,
   runtime python3.12, 15 s, 256 MB, and the environment as measured
   (`DLT_TEMPLATE_KEY`, `IVR_AUDIO_URL`, `POST_CALL_SMS_ENABLED`, `SMS_FUNCTION`)
   plus the new `PLIVO_ANSWER_SECRET_ID`, `PLIVO_API_SECRET_ID`,
   `PLIVO_REQUIRE_ANSWER_TOKEN` (D4) and `VOICE_CDR_TABLE`.

Draft manifest:

```json
{
  "apiId": "zllr9lrg7j",
  "providers": {
    "plivo": {
      "applicationId": "12775976954213184",
      "applicationName": "WECARE-WHATSAPP-IVR",
      "routes": [
        {"routeKey": "POST /plivo/answer",   "function": "wecare-plivo-answer",
         "alias": "live", "path": "/plivo/answer",
         "signatureRequired": false, "providerField": "answer_url",
         "configuredAtProvider": true},
        {"routeKey": "POST /plivo/fallback", "function": "wecare-plivo-answer",
         "alias": "live", "path": "/plivo/fallback",
         "signatureRequired": false, "providerField": "fallback_answer_url",
         "configuredAtProvider": true},
        {"routeKey": "POST /plivo/hangup",   "function": "wecare-plivo-answer",
         "alias": "live", "path": "/plivo/hangup",
         "signatureRequired": true,  "providerField": "hangup_url",
         "configuredAtProvider": true},
        {"routeKey": "POST /plivo/events",   "function": "wecare-plivo-answer",
         "alias": "live", "path": "/plivo/events",
         "signatureRequired": true,  "providerField": null,
         "configuredAtProvider": false,
         "note": "The Plivo Application object has no events URL field. This route is served and signature-gated, but nothing at the provider is currently configured to call it."}
      ]
    }
  }
}
```

That last entry is the reason the manifest is worth having. The Plivo Application
object exposes `answer_url`, `fallback_answer_url`, `hangup_url` and
`message_url` — there is **no events URL**. So `/plivo/events` is a live,
signature-gated route with no provider-side configuration pointing at it. A
checker that asserted four-way parity would either fail forever or be softened
until it meant nothing. Recording `configuredAtProvider: false` with the reason
keeps T25 meaningful and keeps the gap visible instead of implying parity that
does not exist.

**`resource.ts` is not wired into `amplify/backend.ts` in this phase.** That is
deliberate. `wecare-plivo-answer` already exists in the account with a `live`
alias at version 7 and an HTTP API integration; importing it into the Amplify
backend risks Amplify creating a second function or taking ownership of a live
one mid-fix. The file lands as the declared configuration and as the input to a
later, separately confirmed IaC import (`docs/LAMBDA_IAC_IMPORT_PLAN.md` already
scopes that project). Half a step, reversible, and honest about being half a
step.

**`scripts/sync_webhook_registry.py` is repointed at the manifest** instead of
keeping its own hardcoded `WEBHOOKS` list. That list currently names only
`/plivo/answer` and describes its auth as token-only, which has been stale since
V3 validation shipped. Two copies of the same facts is how the first one goes
wrong.

**Alternatives considered.**

- *`resource.ts` alone.* Insufficient: `defineFunction` declares a function, not
  a route, and the routes are what broke.
- *Full CloudFormation or CDK import of `zllr9lrg7j`.* Correct destination,
  wrong time: 345 routes and 102 integrations on a live production API, with an
  existing plan document acknowledging it as its own project. Attempting it
  inside a bugfix is how an outage happens.
- *Extend `scripts/register_task12_routes.py` with the Plivo routes.* Rejected as
  the primary answer: it *creates* routes but has no diff, so it satisfies
  "reproducible" and not "any divergence is detectable". The manifest gives both,
  and a later `--apply` on `webhook_routes.py` can absorb the creation role.

### D4 — The gate closes by gaining a third verdict, not by rejecting more traffic

**Decision.** Replace the boolean return of `_verify_provider` with a three-state
verdict.

```
VERIFIED     a V3 or Ma-V3 signature validated, OR an answer-style fetch
             presented a diagnostic token matching the configured one
UNVERIFIED   an answer-style fetch, unsigned, and NO diagnostic token is
             configured — no evidence of provider identity exists
REJECTED     everything else
```

Route behaviour:

| Route | VERIFIED | UNVERIFIED | REJECTED |
|---|---|---|---|
| `/plivo/answer` | IVR XML 200 | IVR XML 200 **+ alert** | `<Hangup/>` XML 403 |
| `/plivo/fallback` | emergency XML 200 | emergency XML 200 **+ alert** | `<Hangup/>` XML 403 |
| `/plivo/hangup` | CDR + 2xx JSON | unreachable | JSON 401 |
| `/plivo/events` | record + 2xx JSON | unreachable | JSON 401 |

**Why 3.8 is not at risk.** 2.7's condition is *unsigned answer fetch AND no
token configured*. 3.8's condition is *unsigned answer fetch AND a valid token*.
The two are disjoint, so the token path is untouched — it keeps returning
VERIFIED and keeps serving the IVR. UNVERIFIED is reachable only when the
diagnostic secret is absent, which is a configuration fault, not a call.

**Why UNVERIFIED still serves the call.** Rejecting would convert a
configuration fault into a total IVR outage: `wecare/plivo-answer` missing,
rotated, or unreadable by a sandbox that started before it existed would drop
every inbound call. 2.7 does not ask for rejection — it asks that the system
"SHALL NOT report the request as verified, and SHALL make the unverified state
explicit and alertable rather than treating absent configuration as permission."
The defect is the *claim*, and the absence of any consequence. So the fix changes
the claim and adds the consequence.

**What "explicit and alertable" means concretely.** Five specific things, not a
sentiment:

1. **A distinct verdict in the type**, so `UNVERIFIED` cannot be returned through
   the same channel as success. Today the honest string
   `unverified_no_token_configured` travels on `ok=True`, which is what makes it
   invisible.
2. **A dedicated log event at error level**:
   `log_event(logger, 'plivo_provider_unverified', level='error', path=…,
   requestId=…, alert='PLIVO_PROVIDER_UNVERIFIED')` — the same shape as the
   existing `alert='PLIVO_PRIMARY_ANSWER_URL_FAILED'` marker in `_route_fallback`.
3. **A CloudWatch Logs metric filter** `plivo-provider-unverified` on
   `/aws/lambda/wecare-plivo-answer`, pattern `"plivo_provider_unverified"`,
   emitting `WECARE.DIGITAL/PlivoProviderUnverified` — exactly the mechanism the
   four existing `webhook-dedup-error` filters use.
4. **A CloudWatch alarm** `wecare-plivo-provider-unverified`, Sum ≥ 1 over
   5 minutes, `TreatMissingData=notBreaching`, action SNS
   `wecare-alarm-notifications` — the topic with a live email subscriber and 42
   sibling alarms.
5. **A response field nobody can mistake for success**: the `plivo_request` log
   line carries `verified=false` and `auth='unverified'` rather than a mechanism
   name. 3.13 still holds — the *caller* is told nothing about which check
   failed; this is operator-facing telemetry only.

**The fail-closed option stays reachable.** New environment variable
`PLIVO_REQUIRE_ANSWER_TOKEN`, default `false`. Set to `true`, UNVERIFIED becomes
REJECTED. Default preserves 3.8 and availability; the flag lets the operator
tighten deliberately once the secret's stability is established, with no code
change. Rejected alternative: auto-escalating to fail-closed after N alarms — a
security posture that changes itself is unpredictable, and the correct response
to a missing secret is to restore the secret, which the alarm now demands.

**One existing test changes meaning, on purpose.**
`tests/test_plivo_answer.py:155 test_no_token_configured_means_open` asserts the
current fail-open behaviour. It is **amended, not deleted**: the call still
answers (status 200, IVR XML — unchanged), and the new assertions are that the
verdict is `UNVERIFIED` and that `plivo_provider_unverified` was emitted. The
test is renamed `test_no_token_configured_answers_but_is_not_verified`. Flagging
this explicitly so the change is not later mistaken for a regression in the
opposite direction.

### D5 — `main_auth_token` is fetched lazily and passed explicitly, and its absence becomes detectable

**Decision.** Add `_get_plivo_main_auth_token()` to `plivo-answer/handler.py`,
reading field `main_auth_token` from `wecare/plivo/api`, and pass it:

```python
ok, reason = plivo_signature.verify_request(
    event, auth_token, main_auth_token=_get_plivo_main_auth_token())
```

Cached on success only, never at module import — matching `_get_answer_token` and
`_get_plivo_auth_token`, and required by
`.kiro/steering/lambda-snapstart-deploy.md`: a module-scope read is cached for
the life of the execution environment, so a rotation would not take effect until
every warm sandbox recycled.

**No change to `plivo_signature.py`.** It already accepts the parameter,
documents the V3/Ma-V3 distinction, and falls back with
`ma_token = main_auth_token or auth_token`. That fallback is correct at zero
subaccounts and is what makes this benign today. `tests/test_plivo_signature.py:157`
asserts `reason == "ma_v3"`; keeping the contract unchanged keeps that test and
the SDK cross-check intact.

**Observability instead of a contract change.** Rather than adding a
`ma_v3_fallback` reason string (which would break the assertion above and put
configuration knowledge in the wrong module), the *handler* logs
`mainTokenConfigured=<bool>` on the `plivo_request` line — the handler is what
knows whether it supplied a distinct token.

**Correct by detection.** The drift Lambda reads `list_subaccounts()`. When
`subaccount_count > 0` and `main_auth_token` is unset, that is reported as a
drift finding with `field="main_auth_token"`, `current="not configured"`,
`expected="configured (subaccounts present)"`, and it raises
`PlivoDriftFields`. So the day the benign default stops being benign, an alarm
says so — instead of a genuine callback being silently rejected.

**Alternatives considered.** A second secret `wecare/plivo/main` — rejected: one
more secret to rotate and one more IAM grant, for a field that belongs beside
`auth_id` and `auth_token`. An environment variable holding the token — rejected
outright by `.kiro/steering/secret-handling.md`.

**Unverified.** Whether `wecare/plivo/api` already contains a `main_auth_token`
field **cannot be confirmed**: doing so requires reading the secret value, which
`aws-agent-rules` prohibits. `DescribeSecret` shows no keys. The design therefore
handles absence as the expected case: `_get_plivo_main_auth_token()` returns
`''`, the existing `or auth_token` fallback applies, and behaviour is identical
to today. Adding the field is an operator task recorded in the deployment
sequence, not a code prerequisite. Likewise the "0 subaccounts" fact is carried
from the earlier measurement recorded in `plivo_signature.py`'s docstring; it was
**not re-verified in this phase**, for the same reason.

### D6 — `/sms/send` keeps its route and loses its providers

**Decision.** Rewrite `amplify/functions/messaging/outbound-sms/handler.py` as a
thin adapter over `lambda_utils.comms.get_sms_service()`. The route, the request
shape and the response shape stay; every provider branch goes.

Target path, end to end:

```
src/api/client.ts / dashboard
  -> POST https://api.wecare.digital/sms/send
  -> API Gateway zllr9lrg7j  (route unchanged)
  -> wecare-outbound-sms:live  (alias unchanged; new version published)
  -> lambda_utils.comms.get_sms_service()      -> AwsSmsProvider
  -> comms.numbers.to_e164  -> comms.region.resolve
       India      -> ap-south-1, requires_dlt=True
       otherwise  -> AWS_SMS_REGION or us-east-1
  -> comms.dlt.resolve(template_key)           India only; MISSING_DLT_TEMPLATE
                                               refuses the send outright
  -> pinpoint-sms-voice-v2 send_text_message
       OriginationIdentity  India: WDBEEP
                            other: +18444891209   (never the simulator)
       DestinationCountryParameters  India only: IN_ENTITY_ID + IN_TEMPLATE_ID
  -> lambda_utils.message_store.put_message(channel='sms',
                                            provider='aws-end-user-messaging')
```

Everything from `get_sms_service()` down **already exists and is tested** — 44
tests in `tests/test_comms_sms.py`, including the two that encode 3.26 and 3.27:
`test_india_send_without_approved_template_is_refused` and
`test_international_send_pins_origination_identity`. The cutover inherits those
guarantees rather than reimplementing them. That is the entire reason the seam
was built in Stage 2.

**Why keep the route (option b) rather than delete it (option a).**

- *Delete `POST /sms/send` and repoint callers to `POST /sms-aws/send`.*
  Rejected. Deleting a live API Gateway route yields 404 — not a graceful
  failure — for any caller not found by grep, and `/sms/send` is a public
  `api.wecare.digital` path. It is also insufficient: `sms-aws/handler.py` uses
  `pinpoint-sms-voice-v2` but with its own inline DLT logic, not the comms layer,
  so repointing would not satisfy 2.9's "through the SMS service and its AWS
  provider".
- *308 redirect from `/sms/send` to `/sms-aws/send`.* Rejected: POST redirects
  are handled inconsistently by clients, and the deprecated code would still be
  in the repository, so the gate would still count it.
- *Chosen: keep the route, gut the handler.* One deploy makes the invariant true,
  no route change, no 404 risk, and the rollback is a single alias move. It
  removes 46 of the 160 violations from one file plus 7 from its `resource.ts`.

**The `provider` request field is ignored, not rejected.** A caller sending
`provider: 'sinch'` gets a 200 with the AWS result plus
`"providerOverrideIgnored": "sinch"`, and the handler logs
`sms_provider_override_ignored`. Rejecting with 400 would be more pointed, but
ordering decides it: Amplify deploys the frontend automatically on commit to
`stack`, while Lambda deployment is manual (`deploy_all_lambdas.py` +
`snapstart_publish.py`). So either side can land first. Ignoring is safe in both
directions — frontend-first leaves the old handler routing wrongly but working;
Lambda-first leaves the old frontend working and correctly routed. Rejecting
would break the dashboard in the Lambda-first case. The field is deleted from the
frontend in the same phase, and a later commit can tighten to 400 once no caller
sends it.

**`live` alias publish model.** `POST /sms/send` integrates
`...function:wecare-outbound-sms:live`, currently version 7. `update-function-code`
moves `$LATEST` only and changes nothing in production. The deploy must be
`python scripts/deploy_all_lambdas.py wecare-outbound-sms`, which calls
`scripts/snapstart_publish.py` to publish a version, wait for `State=Active` and
move the alias. **Rollback is `aws lambda update-alias --function-name
wecare-outbound-sms --name live --function-version 7`** — instant, no rebuild, no
redeploy. Same model for `wecare-plivo-answer` (also at version 7).

**Preservations that constrain this decision.**

- **3.22 Lightsail stays.** Removing `SMS_PROXY_URL` deletes the Lambda's
  dependency on `52.3.44.165:8899`; it does not touch the instance. The box still
  carries the Meta WhatsApp Calling SIP media leg to
  `sip.wecare.digital:5061` (3.21). No Lightsail action is taken or proposed.
- **3.24 Sinch India RCS stays.** The Sinch *transport* remains in
  `lambda_utils/sinch_rcs.py` and the `rcs-send` / `rcs-dlr` functions, which the
  `sinch-outside-rcs` rule explicitly allows. Only the Sinch **SMS** sender goes.
- **3.25 Plivo never sends SMS.** Unchanged; the `plivo-sms` rule already reads
  `ok`. `plivo-answer` keeps invoking `wecare-sms-aws:live` for the post-call
  follow-up, which is already the AWS path.
- **3.26 / 3.27** are inherited from the comms layer, unmodified.

**Frontend changes** (all measured, all low risk):

| File | Change |
|---|---|
| `src/api/client.ts:1249-1264` | delete `SendSinchSmsRequest` and `sendSinchSms`. **Measured: `sendSinchSms` is exported but called nowhere in `src/`** — a dead export, so deletion has no caller impact |
| `src/pages/dm/sms/index.tsx:215,237,576,697` | repoint the Sinch panel to `sendSmsAws` / `/sms-aws/send`; drop the Sinch provider copy |
| `src/pages/dm/whatsapp/calling.tsx:619-641` | collapse `sendTestSms('airtel'\|'pinpoint')` to one `sendTestSms()` against `/sms-aws/send` |
| `src/components/dashboard/tabs/InfraTab.tsx:69,153-155` · `SystemTab.tsx:137` | update architecture and secret-inventory copy |
| `src/pages/dashboard/index.tsx` (8) · `system-architecture.tsx` (3) · `lambda-functions.tsx` · `order-notifications.tsx:242` | update architecture copy |

`tsc --noEmit` is clean today, so a type error introduced here is unambiguous
signal. The new `tests.yml` runs it on every PR.

### D7 — The gate is re-armed by splitting the rule set, not by forcing a false zero

**The problem, stated plainly.** 2.12 asks for zero violations and enumerates
Airtel **SMS**. The `airtel-runtime` rule prohibits Airtel **entirely**, per a
policy file — `docs/provider-policy.md` — that the script and workflow both cite
and which **does not exist in the repository**. 40 of its 111 violations are
Airtel *voice* in `voice-in/c2c`, `voice-in/obd` and `outbound-voice`, which
`docs/provider-inventory.md` §5.2 titles "Airtel voice — out of SMS scope, still
prohibited" and the migration-plan risk register sizes as a separate migration.
So zero is unreachable inside this scope, and the three available responses are:
allowlist those paths (dishonest — a real regression there would pass), leave
`--expect-fail` (the current failure), or split the rule set.

**Decision. Split, and replace `--expect-fail` with a pinned baseline.**

`scripts/check-provider-policy.sh` gains `--mode baseline|gate` and reads
`scripts/provider-policy-baseline.json`:

- `airtel-runtime` → **`airtel-sms-runtime`** (gating): `iqmessaging.airtel.in`,
  `wecare/airtel-iq`, `wecare/airtel/sms`, `AIRTEL_IQ_`, `AIRTEL_SMS_`,
  `_send_airtel`, `_try_airtel`.
- `airtel-runtime` → **`airtel-voice-runtime`** (tracked, baseline 40):
  `iqvoice.airtel.in`, `openapi.airtel.in`, `wecare/airtel/c2c`,
  `wecare/airtel/obd`, `AIRTEL_C2C_`, `AIRTEL_OBD_`, `AIRTEL_KONG_`,
  `_call_airtel`.
- All other rules stay gating: `airtel-sms-proxy`, `sinch-sms-sender`,
  `sinch-voice-whatsapp`, `sinch-outside-rcs`, `plivo-sms`, `legacy-aws-sms`,
  `sms-provider-literal`.

Semantics:

| Mode | Gating rule | Tracked rule |
|---|---|---|
| `baseline` | fails if count rises above baseline | fails if count rises above baseline; reports (does not fail) at zero |
| `gate` | fails if count > 0 | fails if count rises above baseline; **fails at zero**, to force promotion |

`docs/provider-policy.md` is written as part of this work, because a gate citing
a non-existent policy cannot adjudicate its own scope.

**Why this is not `--expect-fail` with extra steps.** `--expect-fail` inverts the
*whole* result, so a brand-new Airtel SMS sender added today passes CI. Baseline
mode fails on any increase in any rule from the first commit, and the gating
rules flip to absolute zero as soon as they get there. The deferred debt is
40 violations in three named files with a documented owner, reported on every
run, rather than a green tick over 160.

**This departs from the literal text of 2.12** ("zero violations across six
rules"). It needs the user's agreement, or 2.12 needs reading as "zero across the
gating rule set". Recorded as confirmation **[PP-SPLIT-001]** below, not assumed.

**Sequence, designed so the pipeline is never red for an unrelated reason.**

| Step | Change | Gating total after | Tracked after | CI |
|---|---|---|---|---|
| S0 | `tests.yml` lands (pytest + tsc + vitest, no eslint); rule split + baseline replaces `--expect-fail` | 120 (baseline) | 40 (baseline) | green — baseline equals measured present state |
| S1 | `outbound-sms` handler + `resource.ts` rewritten (D6) | 67 | 40 | green — counts only fall |
| S2 | frontend removals (25) | 42 | 40 | green |
| S3a | `whatsapp-calling` Airtel SMS helpers (5); `sms-in/airtel` code references removed, handler returns 410 Gone, route retained (33) | 4 | 40 | green |
| S4 | `legacy-aws-sms` remainder: `INDIA_PINPOINT_APP_ID` in `sms-aws` handler + `resource.ts` (2). **Measured: assigned at line 62 and never read — dead config** | 2 | 40 | green |
| S5 | `sinch-outside-rcs`: the `wecare/sinch/rcs` read at `voice-in/cdr/handler.py:1321` and the duplicate `_is_rcs_enabled()` at `:1306` (migration-plan Stage 4 already calls for this); reword the `52.3.44.165` comment at `:1304` | 0 | 40 | green |
| S6 | `provider-policy.yml` → `--mode gate` | 0 | 40 | green, and now genuinely gating |
| S7 | *deferred, separately confirmed* — delete `wecare-sms-in-airtel`, its route, its tables and `wecare/airtel-iq` / `wecare/airtel/sms` | 0 | 40 | — |
| — | *out of scope* — Airtel voice removal, then promote `airtel-voice-runtime` to gating | 0 | 0 | — |

**S3a deliberately does not delete anything.** Deleting the
`wecare-sms-in-airtel` Lambda, its `POST /sms-in/airtel` route (live, `:live`
alias) and its secrets is a destructive production change requiring pointwise
confirmation under `.kiro/steering/maintenance-reporting.md`. The gate only needs
the *code references* gone, so S3a removes them and leaves the route answering
410 Gone. Inbound Airtel SMS receipt stops at S3a — acceptable and consistent,
because outbound Airtel SMS stops at S1, so there is no Airtel traffic to reply
to. The deletion becomes S7, with its own confirmation. This keeps a destructive
irreversible action out of a step whose purpose is a CI colour change.

## Correctness Properties

Property 1: Bug Condition - Unguarded, incomplete and undeclared Plivo control plane

_For any_ control-plane input where the bug condition holds (`isBugCondition_A`
returns true), the fixed system SHALL provide the operation, SHALL default to dry
run, SHALL require an explicit flag for any mutation and a second explicit
production-approval flag for a number routing cutover, SHALL verify every apply
by reading the persisted object back, SHALL leave every protected field
unchanged, SHALL derive every reported line from live API state, SHALL detect
drift without human initiation and report the exact field, current value,
expected value and protected status of each divergence, SHALL declare the four
webhook routes in the repository such that divergence from live configuration is
detectable, and SHALL NOT return a verified verdict for a request whose provider
identity has not been established.

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8**

Property 2: Preservation - Plivo state and control-plane safety outside the bug condition

_For any_ control-plane input where the bug condition does NOT hold
(`isBugCondition_A` returns false), the fixed system SHALL produce the same
result as the original, preserving `default_endpoint_app = true` on application
12775976954213184, the binding of +918031830030 to WECARE-WHATSAPP-IVR, the
untouched SIP endpoint WECARE-WhatsApp-IVR-SIP, the separation of application SIP
from endpoint SIP, all eleven protected fields, discovery-only Zentrunk access,
dry run as the default, read-back verification with rollback on failure,
per-field current/target/change/protected reporting, secret-free snapshots,
by-reference credential resolution, and path-only comparison of token-bearing
URLs.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.15, 3.16, 3.17, 3.18, 3.19, 3.20**

Property 3: Bug Condition - SMS not resolving to AWS End User Messaging

_For any_ outbound message where the bug condition holds (`isBugCondition_B`
returns true — channel is SMS and the resolved provider is not AWS End User
Messaging), the fixed system SHALL resolve the provider to AWS End User
Messaging, SHALL route an Indian destination to ap-south-1 and refuse the send
without an approved DLT template, SHALL route any other destination to the
configured region defaulting to us-east-1, SHALL make no Airtel attempt and no
Sinch fallback, and SHALL leave no Airtel, Sinch SMS, Plivo SMS or legacy
non-End-User-Messaging AWS SMS transport reachable by any user action or present
in runtime code covered by a gating policy rule.

**Validates: Requirements 2.9, 2.10, 2.11, 2.12, 2.13**

Property 4: Preservation - Non-SMS channels and the Indian DLT gate

_For any_ message where the bug condition does NOT hold (`isBugCondition_B`
returns false), the fixed system SHALL produce the same result as the original,
preserving Meta WhatsApp Calling to sip.wecare.digital:5061 on Lightsail
Asterisk, the continued existence of the Lightsail instance, the ElevenLabs phone
number, agent, inbound enablement and SIP allowlist as found, Sinch as the India
RCS provider, Plivo for voice, SIP and IVR and never for SMS, the registered
entity id and sender id on Indian AWS sends with refusal absent an approved DLT
template, and the origination identity pinned to the registered number rather
than the simulator for non-Indian sends.

**Validates: Requirements 3.21, 3.22, 3.23, 3.24, 3.25, 3.26, 3.27**

Property 5: Preservation - Plivo route behaviour under a closed provider gate

_For any_ inbound Plivo request where the bug condition does NOT hold, the fixed
handler SHALL produce the same caller-visible result as the original, preserving
service of the IVR for a genuine unsigned answer-style fetch bearing a valid
diagnostic token, the signature requirement on hangup with final CDR persistence,
deduplication by call identifier, a 2xx response and no IVR body, the fallback's
record-and-degrade with `<Speak>`-only emergency XML depending on no external
media asset, XML rather than JSON on a rejected answer request, stage-prefix
stripping driven by `requestContext.stage` for both routing and signature
reconstruction, withholding of which check failed, and acceptance of valid but
rejection of invalid, tampered and unsigned requests on signed side-effect
routes.

**Validates: Requirements 3.8, 3.9, 3.10, 3.11, 3.12, 3.13, 3.14**

## Fix Implementation

### Changes Required

Organised by defect class, because the classes deploy independently and carry
different approval requirements. Every path is exact. Every function named exists
today unless marked **NEW**. Line numbers are as measured on 2026-09-19 and are
anchors for the implementer, not contracts.

**No application code is written in this phase.**

#### Class 1 — Control-plane completeness (1.1–1.3 → 2.1, 2.2, 2.3)

**File**: `amplify/functions/shared/lambda_utils/plivo_control_plane.py` — **NEW**

The read-only core, extracted from `scripts/plivo_control_plane.py` so the D2
drift Lambda can import it without carrying a single mutation method.

| Symbol | Origin | Note |
|---|---|---|
| `APP_ID`, `APP_NAME`, `ENDPOINT_USERNAME`, `ENDPOINT_ALIAS`, `NUMBER`, `APPLICATION_SIP_URI`, `ENDPOINT_SIP_URI` | moved | unchanged values |
| `PROTECTED_FIELDS`, `CRITICAL_INVARIANTS`, `CAPTURED_FIELDS`, `TARGET_URLS`, `TARGET_METHODS` | moved | unchanged |
| `_same`, `_strip_query`, `_token_fingerprint`, `_assert_sanitized`, `_git_commit` | moved | the four secret-safety helpers live in exactly one place (3.18, 3.19, 3.20) |
| `PlivoReadService` | **NEW** class | `_load_credentials`, `_call`, `get_application`, `list_applications`, `get_endpoint`, `list_endpoints`, `get_number`, `list_trunks`, `verify_application_sip`, `snapshot_current_state`, `plan_application_update` |
| `get_trunk(trunk_id)` | **NEW** | 2.1. `GET /Zentrunk/Trunk/{id}/`; on any non-200, filter `list_trunks()["trunks"]` by `trunk_id`. Returns the `TRUNK_FIELDS` projection plus `source: "direct" \| "collection"`. Read-only — no POST, no PUT, no DELETE on any Zentrunk path (3.7) |
| `list_subaccounts()` | **NEW** | `GET /Subaccount/`; returns `{count, objects}` with no auth token field. Feeds D5's detection |
| `drift_report()` | **NEW** | 2.4. Returns `{"generated_at", "git_commit", "subaccount_count", "divergences": [...], "route_check": {...}, "ok"}`. One divergence dict per finding: `field`, `current`, `expected`, `protected`, `critical`. Built from `plan_application_update` rows (where `change` is true), `CRITICAL_INVARIANTS` compared against live, the number binding against `APP_ID`, the endpoint's presence and application assignment, the `main_auth_token`/subaccount pair, and `webhook_routes.diff()`. `_assert_sanitized` runs over the whole report before it is returned |

**File**: `scripts/plivo_control_plane.py` — **modified**

Becomes the mutation-capable superset. `from lambda_utils.plivo_control_plane import *`
plus an explicit re-export block, so every name the 52 existing tests and the CLI
import today resolves unchanged. `PlivoControlPlaneService(PlivoReadService)`
retains `apply_application_update`, `verify_post_update_state`,
`rollback_application_update`, `_read_back`, `plan_number_routing_change`,
`apply_number_routing_change`, `read_back_delay`. No behaviour change.

**File**: `scripts/plivo-reconcile` — **modified**

`main()` becomes `argparse` subparsers. New functions: `_cmd_application`,
`_cmd_number`, `_cmd_endpoint`, `_cmd_trunk`, `_cmd_drift`, `_cmd_routes`, and
`_alias_legacy_flags(argv)` which rewrites `--dry-run` → `application plan`,
`--apply` → `application apply`, `--number-plan` → `number plan`, `--trunks` →
`trunk list` before parsing. `inspect()`, `show_plan()`, `line()` and
`_render_trunks()` are reused, not rewritten. New renderers `_render_number`,
`_render_endpoint`, `_render_trunk`, `_render_drift`.

`number route-apply` requires **both** a target (`--to-application` or
`--to-trunk`) and `--approve-production-routing`, prints the before binding, calls
`apply_number_routing_change(approved=True)`, prints the after binding, and exits
non-zero if they are equal. Absent the approval flag it prints the plan and exits
2 without calling the service — so the guard is enforced at the CLI *and* at the
service, and `PlivoError` remains the backstop (2.3, 3.15).

#### Class 2 — Guard execution (1.4, 1.5 → 2.4, 2.5)

**File**: `amplify/functions/operations/plivo-reconcile/handler.py` — **NEW**

```python
def handler(event, context):          # read-only; no mutation import in scope
    report = PlivoReadService().drift_report()
    for d in report["divergences"]:
        log_event(logger, 'plivo_drift', level='error', **d,
                  alert=('PLIVO_DRIFT_CRITICAL_INVARIANT' if d["critical"]
                         else 'PLIVO_DRIFT'))
    _put_metrics(report)              # PlivoDriftFields, PlivoCriticalInvariantBreached
    return {"ok": report["ok"], "divergences": len(report["divergences"])}
```

On an unhandled exception it emits `PlivoReconcileFailed=1` and re-raises, so the
`wecare-plivo-reconcile-failed` alarm fires and Lambda records the error. A guard
that dies quietly is worse than no guard.

**File**: `amplify/functions/operations/plivo-reconcile/resource.ts` — **NEW**.
`defineFunction` name `wecare-plivo-reconcile`, python3.12, 60 s, 256 MB,
environment `PLIVO_API_SECRET_ID=wecare/plivo/api`, `WECARE_API_BASE`,
`PLIVO_SNAPSHOT_DIR` unset (Lambda writes no snapshot; `snapshot_current_state(write=False)`).

**File**: `amplify/backend-resources.ts` — **modified**. One `events.Rule`
`wecare-plivo-reconcile-hourly`, `Schedule.rate(Duration.hours(1))`, target the
function; three `cloudwatch.Alarm` definitions per the D2 table, all actioned to
the existing `alarmTopic`. This file already holds six rules and the alarm
pattern, so this is an addition in an established idiom.

**File**: `scripts/create_plivo_drift_alarms.py` — **NEW**. Idempotent
`put_metric_filter` + `put_metric_alarm` upserts then a `describe_alarms`
read-back, modelled on `scripts/_create_dedup_alarm.py`. Exists because
`backend-resources.ts` is not the deployment path for this account's alarms
today — the four `webhook-dedup-error` filters were created by script.

**File**: `.github/workflows/tests.yml` — **NEW**

```yaml
name: Tests
on: { pull_request: { branches: [stack] }, push: { branches: [stack] }, workflow_dispatch: }
permissions: { contents: read }
jobs:
  python:    # actions/setup-python 3.12 -> pip install -r requirements-dev.txt -> pytest
  typescript:# actions/setup-node .nvmrc -> npm ci -> npx tsc --noEmit -> npx vitest run
  lint:      # npx eslint .   continue-on-error: true   (non-gating, see D2)
```

No AWS credentials in any job. The suite is offline: 883 passed in 5.18 s with the
network unused, re-measured for this document.

#### Class 3 — Route declaration (1.6 → 2.6)

| File | State | Contents |
|---|---|---|
| `amplify/webhook-routes.json` | **NEW** | the D3 manifest verbatim, including `/plivo/events` with `configuredAtProvider: false` and its reason |
| `scripts/webhook_routes.py` | **NEW** | `load()`, `diff_api_gateway()` (`GetRoutes` + `GetIntegrations` on `zllr9lrg7j`, match `routeKey` → integration URI ending `:live`), `diff_provider()` (Plivo URL fields, path-only compare via `_strip_query`, token via `_token_fingerprint`), `diff()` merging both |
| `amplify/functions/messaging/plivo-answer/resource.ts` | **NEW** | declared configuration only; **not** imported into `amplify/backend.ts` in this phase (D3) |
| `scripts/sync_webhook_registry.py` | **modified** | its hardcoded `WEBHOOKS` list, which names only `/plivo/answer` and describes the auth as token-only, is replaced by a read of the manifest |

`diff()` is called by `plivo-reconcile routes check` and by `drift_report()`, so
T25 runs hourly rather than only when asked.

#### Class 4 — Provider gate (1.7, 1.8 → 2.7, 2.8)

**File**: `amplify/functions/messaging/plivo-answer/handler.py`

| Function | Change |
|---|---|
| `_verify_provider` | returns `(verdict, mechanism)` where verdict ∈ `VERIFIED`/`UNVERIFIED`/`REJECTED` (module constants). The `if not token: return True, 'unverified_no_token_configured'` branch becomes `return UNVERIFIED, 'no_token_configured'`. Every other branch keeps its current outcome |
| `_get_plivo_main_auth_token` | **NEW**. `_secret_field(PLIVO_API_SECRET_ID, 'main_auth_token')`, cached on success only, module-global `_plivo_main_auth_token_cache`. Never read at import (`.kiro/steering/lambda-snapstart-deploy.md`) |
| `_verify_provider` → `verify_request` call | gains `main_auth_token=_get_plivo_main_auth_token()` (2.8) |
| `handler` | on `UNVERIFIED`, emits `log_event(..., 'plivo_provider_unverified', level='error', alert='PLIVO_PROVIDER_UNVERIFIED')` then proceeds to the route, unless `PLIVO_REQUIRE_ANSWER_TOKEN` is true, in which case it takes the `REJECTED` path. On `REJECTED`, unchanged: XML 403 for answer/fallback, JSON 401 for hangup/events (3.11, 3.13) |
| `handler`'s `plivo_request` log line | `auth=mechanism` becomes `auth=mechanism, verified=<bool>, mainTokenConfigured=<bool>` |

**File**: `amplify/functions/shared/lambda_utils/plivo_signature.py` — **unchanged**.
It already accepts `main_auth_token`, already documents the V3/Ma-V3 distinction,
and its SDK cross-check and 50 tests stay intact. The defect was at the call site.

**Infrastructure**: metric filter `plivo-provider-unverified` on
`/aws/lambda/wecare-plivo-answer` emitting `WECARE.DIGITAL/PlivoProviderUnverified`,
and alarm `wecare-plivo-provider-unverified` (Sum ≥ 1 / 5 min,
`TreatMissingData=notBreaching`, SNS `wecare-alarm-notifications`). Created by
`scripts/create_plivo_drift_alarms.py` alongside the D2 alarms — one script, one
read-back, four alarms.

#### Class 5 — SMS cutover (1.9–1.11 → 2.9, 2.10, 2.11)

**File**: `amplify/functions/messaging/outbound-sms/handler.py` — **rewritten**

Deleted: `_load_airtel_iq_creds`, `_send_airtel_iq_sms`, `_send_airtel_sms`,
`_load_sinch_sms_creds`, `_send_sinch_sms`, `_send_aws_sms`,
`_clean_phone_for_sms`, and the constants `AIRTEL_IQ_HOST`, `SMS_PROXY_URL`,
`AIRTEL_IQ_ENTITY_ID`, `AIRTEL_IQ_SOURCE_ADDRESS`, `AIRTEL_IQ_SECRET`. That is
roughly 27 KB of handler reduced to an adapter.

Retained: `handler`, `_get_contact`, `_response`, and the opt-in check
(`optInSms` / `allowlistSms`) — it is unrelated to provider choice and removing it
would be a scope breach.

Replaced: `_store_message` delegates to `lambda_utils.message_store.put_message`
with `channel='sms'`, `provider='aws-end-user-messaging'`.

New body of the send step:

```python
from lambda_utils.comms import get_sms_service
result = get_sms_service().send_sms(
    phone, content,
    message_type=body.get('messageType', 'TRANSACTIONAL'),
    dlt_template_key=body.get('dltTemplateKey') or body.get('dltTemplateId', ''),
    override_region=body.get('region', ''))
```

The `provider` request field is read only to log
`sms_provider_override_ignored` and echo `providerOverrideIgnored` in the 200
response (D6). Routing ignores it entirely, so no request body can select a
non-AWS provider.

Region, DLT and origination identity are **not** reimplemented here. They come
from `comms.region.resolve` (India → `ap-south-1`, else `AWS_SMS_REGION_DEFAULT`
→ `us-east-1`), `comms.dlt.resolve` (India refuses without an approved template →
`MISSING_DLT_TEMPLATE`, 3.26) and `comms.sms.ORIGINATION_IDENTITY` (pinned
`+18444891209`, never the simulator `+14255556333`, 3.27). Those 44 tests are the
contract this handler inherits.

**File**: `amplify/functions/messaging/outbound-sms/resource.ts` — **modified**.
Remove `PINPOINT_APP_ID`, `ORIGINATION_NUMBER`, `AIRTEL_IQ_HOST`,
`AIRTEL_IQ_USERNAME`, `AIRTEL_IQ_PASSWORD`, `AIRTEL_IQ_CUSTOMER_ID`,
`AIRTEL_IQ_ENTITY_ID`, `AIRTEL_IQ_SOURCE_ADDRESS`. Add `AWS_SMS_REGION_INDIA`,
`AWS_SMS_REGION_DEFAULT`, `AWS_SMS_DEFAULT_ORIGINATION_IDENTITY`. Keep
`SENDER_ID`, `CONTACTS_TABLE`, `MESSAGES_TABLE`.

**Frontend** — per the D6 table. `src/api/client.ts:1249-1264` (`SendSinchSmsRequest`,
`sendSinchSms` — a dead export, re-verified: the only occurrence in `src/` is its
own definition), `src/pages/dm/sms/index.tsx` (Sinch panel → `sendSmsAws`),
`src/pages/dm/whatsapp/calling.tsx:617-641` (`sendTestSms('airtel'|'pinpoint')` →
one `sendTestSms()` against `/sms-aws/send`), and architecture copy in
`InfraTab.tsx`, `SystemTab.tsx`, `dashboard/index.tsx`,
`system-architecture.tsx`, `lambda-functions.tsx`, `order-notifications.tsx`.

**IAM**: none. `wecare-digital-lambda-role` already carries the EUM v2 send
permission that `wecare-sms-aws` uses, and `wecare-outbound-sms` runs under the
same role. Removing Airtel and Sinch *narrows* what the function reads; no grant
is added. This is the reason no IAM confirmation appears in the queue below.

#### Class 6 — Deprecated provider removal and gate re-arm (1.12, 1.13 → 2.12, 2.13)

| File | State | Change |
|---|---|---|
| `scripts/check-provider-policy.sh` | **modified** | split `airtel-runtime` into gating `airtel-sms-runtime` and tracked `airtel-voice-runtime`; replace `--expect-fail` with `--mode baseline\|gate`; read `provider-policy-baseline.json`; `rule()` gains a `kind` argument |
| `scripts/provider-policy-baseline.json` | **NEW** | pinned per-rule counts; the only file a step in the D7 sequence edits |
| `.github/workflows/provider-policy.yml` | **modified** | `--mode baseline` at S0, `--mode gate` at S6; step summary reports both rule sets |
| `docs/provider-policy.md` | **NEW** | the policy the script and workflow both already cite and which **does not exist**. Without it the gate cannot adjudicate its own scope |
| `amplify/functions/messaging/whatsapp-calling/handler.py` | **modified** | `SMS_LAMBDA_AIRTEL` (:1325), `sms_provider = 'airtel'` (:1355), the `FunctionName=SMS_LAMBDA_AIRTEL` invoke (:1434) → `wecare-sms-aws:live` |
| `amplify/functions/messaging/sms-in/airtel/handler.py` + `resource.ts` | **modified** | 41 measured references removed; handler returns **410 Gone**; the live `POST /sms-in/airtel` route and its `:live` alias are **retained** (deletion is S7, separately confirmed) |
| `amplify/functions/messaging/sms-aws/handler.py:62` + `resource.ts:21` | **modified** | remove `INDIA_PINPOINT_APP_ID` — measured assigned and never read |
| `amplify/functions/messaging/voice-in/cdr/handler.py` | **modified** | the `wecare/sinch/rcs` read (:1321) and duplicate `_is_rcs_enabled()` (:1306) removed per migration-plan Stage 4; the `52.3.44.165` comment (:1304) reworded |

Untouched, deliberately: `lambda_utils/sinch_rcs.py`, `rcs-send`, `rcs-dlr`
(3.24); `voice-in/c2c`, `voice-in/obd`, `outbound-voice` — the 40 tracked Airtel
*voice* violations (out of scope); the Lightsail instance (3.22); every Plivo
voice path (3.25).

### File manifest

23 files: 10 new, 13 modified. No file is deleted.

| # | Path | State | Class |
|---|---|---|---|
| 1 | `amplify/functions/shared/lambda_utils/plivo_control_plane.py` | new | 1 |
| 2 | `scripts/plivo_control_plane.py` | mod | 1 |
| 3 | `scripts/plivo-reconcile` | mod | 1 |
| 4 | `amplify/functions/operations/plivo-reconcile/handler.py` | new | 2 |
| 5 | `amplify/functions/operations/plivo-reconcile/resource.ts` | new | 2 |
| 6 | `amplify/backend-resources.ts` | mod | 2 |
| 7 | `scripts/create_plivo_drift_alarms.py` | new | 2, 4 |
| 8 | `.github/workflows/tests.yml` | new | 2 |
| 9 | `amplify/webhook-routes.json` | new | 3 |
| 10 | `scripts/webhook_routes.py` | new | 3 |
| 11 | `amplify/functions/messaging/plivo-answer/resource.ts` | new | 3 |
| 12 | `scripts/sync_webhook_registry.py` | mod | 3 |
| 13 | `amplify/functions/messaging/plivo-answer/handler.py` | mod | 4 |
| 14 | `amplify/functions/messaging/outbound-sms/handler.py` | mod | 5 |
| 15 | `amplify/functions/messaging/outbound-sms/resource.ts` | mod | 5 |
| 16 | `src/api/client.ts` | mod | 5 |
| 17 | `src/pages/dm/sms/index.tsx` | mod | 5 |
| 18 | `src/pages/dm/whatsapp/calling.tsx` | mod | 5 |
| 19 | `scripts/check-provider-policy.sh` | mod | 6 |
| 20 | `scripts/provider-policy-baseline.json` | new | 6 |
| 21 | `.github/workflows/provider-policy.yml` | mod | 6 |
| 22 | `docs/provider-policy.md` | new | 6 |
| 23 | `amplify/functions/messaging/{whatsapp-calling,sms-in/airtel,sms-aws,voice-in/cdr}` + dashboard copy | mod | 6 |

Plus test files: `tests/test_plivo_control_plane.py`,
`tests/test_plivo_answer.py`, `tests/test_plivo_routes.py`,
`tests/test_plivo_signature.py` extended; `tests/test_outbound_sms_aws.py`,
`tests/test_webhook_routes.py`, `tests/test_plivo_drift.py`,
`tests/test_provider_policy_gate.py` new. `requirements-dev.txt` gains
`hypothesis==6.168.0` (dev-only; the file's own header records that it does not
define the Lambda runtime, so nothing reaches production).

## Testing Strategy

### Validation Approach

Two phases. First surface counterexamples on **unfixed** code, so the root-cause
hypotheses in the previous section are confirmed or refuted before anything is
written. Then verify the fix holds for every buggy input and that nothing outside
the bug conditions moved.

This bugfix has an unusual starting position that shapes the whole strategy: **883
tests already pass**, 153 of them over the Plivo surface and 98 over the SMS
layer. That suite is not something to add to — it *is* the preservation harness.
The single most informative signal available is that all 883 still pass, with
exactly one test amended on purpose and none deleted. Any other change in that
number is a regression until proven otherwise.

Consequently the exploratory phase leans on tests that must **fail today**, and
the preservation phase leans on tests that must **keep passing unchanged**.

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate each defect BEFORE implementing
the fix. Confirm or refute the six root-cause hypotheses. If a hypothesis is
refuted, re-hypothesize before writing code.

**Test Plan**: Write the assertions for the *target* behaviour and run them against
the current tree. Each must fail, and the failure mode is the evidence. For the
three defects that are not expressible as a Python assertion (1.4, 1.5, 1.13)
the counterexample is a measured command output, recorded rather than asserted.

**Test Cases**:

1. **`get_trunk` does not exist** — `hasattr(PlivoControlPlaneService, 'get_trunk')`
   (will fail on unfixed code: `AttributeError`). Confirms hypothesis 1.
2. **`plivo-reconcile number inspect` is not a verb** — invoke with that argv and
   assert exit 0 (will fail: argparse exits 2, `unrecognized arguments`).
3. **`number route-apply` is unreachable from the CLI** — grep the CLI module for
   `apply_number_routing_change` (will fail: zero occurrences, while the service
   method and its approval guard are already tested). Confirms hypothesis 1 —
   planning was in scope, applying was not.
4. **No schedule observes Plivo** — `ListRules` + `ListSchedules`. Measured: 6
   rules, none Plivo; 0 schedules. Confirms hypothesis 2. *Recorded measurement,
   not an assertion.*
5. **No pipeline runs pytest** — `grep -l pytest .github/workflows/*` returns
   nothing across all five workflows. Confirms hypothesis 2. *Recorded.*
6. **No manifest to diff** — assert `amplify/webhook-routes.json` exists (will
   fail: absent), and that `sync_webhook_registry.py` describes `/plivo/answer`
   auth as token-only (will pass, and that passing is the defect — the string is
   stale since V3 landed). Confirms hypothesis 3.
7. **The gate fails open** — `_verify_provider` on an event with no signature and
   `_get_answer_token` monkeypatched to `''`. Assert the verdict is not a success
   value (will fail: returns `(True, 'unverified_no_token_configured')`).
   Confirms hypothesis 4 — and note the reason string already says `unverified`,
   which is the evidence that this is a *type* problem, not an oversight.
8. **`main_auth_token` never reaches the verifier** — patch `verify_request` with a
   recorder, invoke the handler with an Ma-V3 header, assert the recorder saw a
   non-empty `main_auth_token` (will fail: it is `''`, so `ma_token` resolves to
   the subaccount token). Confirms hypothesis 5.
9. **India resolves to Airtel** — call `outbound-sms.handler` with a `+91`
   destination and a stubbed boto3, assert the chosen provider is
   `aws-end-user-messaging` (will fail: `'airtel'`, then Sinch on failure).
   Confirms hypothesis 6.
10. **The dashboard reaches the deprecated route** — assert no file under `src/`
    posts `provider: 'sinch'` or selects `/sms/send` for Airtel (will fail:
    `client.ts:1261`, `dm/sms/index.tsx:237`, `whatsapp/calling.tsx:625`).
11. **The gate reports success with violations present** —
    `./scripts/check-provider-policy.sh --expect-fail; echo $?`. Measured: prints
    `160 finding(s) across 6 rule(s)` and exits **0**. Confirms hypothesis 6.
    *Recorded.*
12. **Edge case, and the one that may refute a hypothesis**: count
    `airtel-runtime` hits that live in *voice* paths. Measured: **40 of 111** in
    `voice-in/c2c`, `voice-in/obd`, `outbound-voice`. If this had come back near
    zero, D7's rule split would be unnecessary complexity and the simple fix —
    drive the rule to zero — would be correct. It did not, so the split stands.

**Expected Counterexamples**:

- Missing attributes and argparse exit 2 for 1.1–1.3 — a surface built to the
  shape of one incident.
- `(True, 'unverified_no_token_configured')` for 1.7 — a boolean return with no
  room for a third state.
- `main_auth_token=''` at the call site for 1.8 — a defaulted parameter that is
  benign at zero subaccounts.
- `provider='airtel'` then `provider='sinch'` for 1.9/1.10 — Stage 3 of the
  migration never started; `grep` confirms no Lambda imports `lambda_utils.comms`.
- Exit code 0 with 160 violations for 1.13 — an inversion that outlived its window.
- Possible causes across the set: a surface generalised from an incident rather
  than a resource model; guards written as assertions with no executor; an
  overloaded boolean; a safe default that hides a latent defect; a correctly
  sequenced migration stalled at Stage 2.

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed
function produces the expected behaviour.

```
FOR ALL X WHERE isBugCondition_A(X) DO
  result := controlPlane'(X)
  ASSERT result.operation_exists
     AND result.dry_run_is_default
     AND result.mutation_requires_explicit_flag
     AND result.read_back_verified
     AND result.protected_fields_unchanged
     AND result.reported_from_live_api_state
     AND result.guard_runs_without_human_initiation
     AND NOT (result.verdict = VERIFIED AND NOT result.evidence_established)
END FOR

FOR ALL X WHERE isBugCondition_B(X) DO
  result := smsService'(X)
  ASSERT result.provider = AWS_END_USER_MESSAGING
     AND result.region = (X.is_india ? "ap-south-1" : configured_region_or_us_east_1)
     AND (NOT X.is_india OR result.dlt_template_approved)
     AND NOT reachable(AIRTEL_SMS) AND NOT reachable(SINCH_SMS)
     AND NOT reachable(PLIVO_SMS)  AND NOT reachable(LEGACY_AWS_SMS_TRANSPORT)
END FOR
```

`guard_runs_without_human_initiation` is the one conjunct no unit test can
establish. It is verified by infrastructure assertions instead: `DescribeRule` on
`wecare-plivo-reconcile-hourly` reports `State=ENABLED` and
`ScheduleExpression=rate(1 hour)`, `DescribeAlarms` reports all four alarms with
the SNS action attached, and a GitHub Actions run of `tests.yml` appears on a PR.
Stated plainly because a design that claimed a unit test covered it would be
wrong.

### Preservation Checking

**Goal**: Verify that for all inputs where neither bug condition holds, the fixed
function produces the same result as the original.

```
FOR ALL X WHERE NOT isBugCondition_A(X) AND NOT isBugCondition_B(X) DO
  ASSERT F(X) = F'(X)
END FOR
```

**Testing Approach**. Three mechanisms, in order of how much they prove:

1. **The existing suite, unchanged.** 883 tests pass today. After the fix, 883 of
   the original assertions must still hold, with exactly one amended
   (`test_no_token_configured_means_open` → `test_no_token_configured_answers_but_is_not_verified`,
   which keeps its status-200 and `<Play>` assertions and adds two) and none
   deleted. For the Plivo control plane and the route handler this is a genuine
   `F(X) = F'(X)` check, because those tests were written against F and the fix
   does not rewrite them.
2. **Property-based testing** where the input domain is too large to enumerate:
   signature validation, E.164 parsing, region resolution and protected-field
   diffing. Generated inputs catch the edge cases a matrix misses, and a
   shrinking counterexample is directly actionable.
3. **Differential testing** for the one rewrite. `outbound-sms/handler.py` is
   replaced, so its old behaviour cannot be preserved by keeping its tests — the
   old behaviour *is* the defect. Preservation there is scoped to the parts that
   are not the defect: request shape, response shape, the opt-in check, the 400 /
   403 / 404 / 500 status contract, and the MessagesTable row shape. Those are
   captured from the unfixed handler first, then asserted against the new one.

**Test Plan**: Observe behaviour on UNFIXED code first, then write tests capturing
it. For the SMS handler this means recording the current response envelope for a
valid send, a missing-content request, a non-opted-in contact and an unknown
contact *before* the rewrite, so the new handler is compared against measured
behaviour rather than remembered behaviour.

**Test Cases**:

1. **Plivo protected fields** — observe that `plan_application_update` reports all
   eleven `PROTECTED_FIELDS` with `change: False`, and that
   `verify_post_update_state` fails on any protected movement. Already covered by
   the 52 existing control-plane tests; verify they pass untouched after the
   read/mutate split (3.1, 3.6, 3.16).
2. **Answer-with-valid-token still serves the IVR** — observe status 200 and
   `<Play>` on unfixed code, assert identical after the verdict change. This is
   the 3.8 guarantee and the single most important preservation test in the set,
   because D4 is the change most capable of dropping calls.
3. **Hangup still requires a signature and never returns the IVR** — observe
   401 unsigned, 2xx JSON signed, no `<Play>` in either; assert identical (3.9,
   3.14).
4. **Fallback still degrades without the media asset** — observe `<Speak>`-only
   emergency XML; assert identical (3.10).
5. **Stage-prefix stripping** — observe `/prod/plivo/hangup` routing and signature
   reconstruction; assert identical (3.12).
6. **Rejection still withholds the reason** — observe the response body carries no
   mechanism name; assert identical (3.13).
7. **SMS request/response envelope** — capture from the unfixed handler, assert
   the new adapter matches for every status path.
8. **India DLT gate and non-India origination pinning** — the two existing comms
   tests `test_india_send_without_approved_template_is_refused` and
   `test_international_send_pins_origination_identity` must pass unchanged. If
   either changes meaning, the cutover is wrong (3.26, 3.27).
9. **Non-SMS channels** — Sinch India RCS, Plivo voice, Meta WhatsApp: assert no
   file under `rcs-send`, `rcs-dlr`, `sinch_rcs.py`, `plivo-answer` (voice paths)
   or the Meta SIP configuration is modified by this change (3.21, 3.24, 3.25).
   A diff-scope assertion, not a behavioural one, because the strongest available
   guarantee is that the code was not touched.

### Acceptance test map — T1 to T25

Every acceptance test from the requirements, with where it lives and what happens
to it. 20 exist; 5 are new; 1 is amended.

| T | Verifies | Location | Action |
|---|---|---|---|
| T1 | 3.17 | `test_plivo_control_plane.py` | exists — must pass unchanged after the read/mutate split |
| T2 | 3.17 | `test_plivo_control_plane.py` | exists — unchanged |
| T3 | 3.1 | `test_plivo_control_plane.py` | exists — unchanged |
| T4 | 3.16 | `test_plivo_control_plane.py` | exists — unchanged |
| T5 | 3.16 | `test_plivo_control_plane.py` | exists — unchanged. `read_back_delay=0` in tests stays |
| T6 | 2.2 | `test_plivo_control_plane.py` | **extended** — add CLI-level `number inspect` |
| T7 | 2.3 | `test_plivo_control_plane.py` | **extended** — add CLI refuses without `--approve-production-routing`, exit 2, service not called |
| T8 | 2.2, 3.3 | `test_plivo_control_plane.py` | **extended** — add CLI `endpoint inspect`; keep by-username-or-alias, never by position |
| T9 | 3.4, 3.5 | `test_plivo_control_plane.py` | exists — unchanged |
| T10 | 2.1, 3.7 | `test_plivo_control_plane.py` | **NEW** — `get_trunk` returns the `TRUNK_FIELDS` projection; asserts `source` is reported; asserts only GET was issued on any `/Zentrunk/` path |
| T11 | 3.7 | `test_plivo_control_plane.py` | exists — unchanged |
| T12 | 3.15 | `test_plivo_control_plane.py` | **extended** — every new subcommand defaults to plan; a recorder asserts zero non-GET calls |
| T13 | 2.3, 3.15 | `test_plivo_control_plane.py` | **extended** — CLI and service both refuse |
| T14 | 3.14 | `test_plivo_signature.py` | exists — unchanged, incl. the SDK cross-check |
| T15 | 3.14 | `test_plivo_signature.py` | exists — unchanged |
| T16 | 3.14 | `test_plivo_signature.py` | exists — unchanged |
| T17 | 3.14 | `test_plivo_routes.py` | exists — unchanged |
| T18 | 2.8 | `test_plivo_signature.py` + `test_plivo_answer.py` | **NEW** — an Ma-V3 header signed with a main token that **differs** from the subaccount token validates. Today's `test_ma_v3_header_is_also_accepted` uses one token for both, so it cannot distinguish the two paths. Plus a handler-level test that `verify_request` received a non-empty `main_auth_token` |
| T19 | 2.7 | `test_plivo_answer.py:155` | **AMENDED** — `test_no_token_configured_means_open` → `test_no_token_configured_answers_but_is_not_verified`. Keeps status 200 and `<Play>`; adds verdict `UNVERIFIED` and `plivo_provider_unverified` emitted. Called out so the change is never mistaken for a regression in the opposite direction |
| T20 | 3.8 | `test_plivo_routes.py:120` | exists — unchanged, and must stay green through D4 |
| T21 | 2.9, 2.10 | `test_outbound_sms_aws.py` | **NEW** — for a matrix of destinations the resolved provider is always `aws-end-user-messaging`; `provider: 'sinch'` in the body is ignored, not honoured |
| T22 | 2.10, 3.26 | `test_outbound_sms_aws.py` | **NEW** at handler level — India → `ap-south-1` + DLT required; other markets → `AWS_SMS_REGION_DEFAULT` → `us-east-1`; override changes region but never drops DLT. The region/DLT logic itself is already covered by 44 comms tests |
| T23 | 2.11, 2.12 | `test_provider_policy_gate.py` | **NEW** — two parts. (a) the gate script exits non-zero in `--mode gate` when a synthetic violation is planted in a temp tree, and zero when clean. (b) an import-graph assertion that `outbound-sms/handler.py` imports `lambda_utils.comms` and references no Airtel, Sinch or legacy-AWS symbol |
| T24 | 3.18 | `test_plivo_control_plane.py` | exists — unchanged. `_assert_sanitized` also runs over `drift_report()` |
| T25 | 2.6 | `test_webhook_routes.py` | **NEW** — the manifest's four routes match a fixtured API Gateway `GetRoutes`/`GetIntegrations` response and a fixtured Plivo application; a divergence in any of routeKey, integration alias, or provider URL path is detected; `/plivo/events` with `configuredAtProvider: false` does not produce a false positive; token compared by fingerprint only |

### Unit Tests

- `get_trunk` — direct path, fallback path, unknown id, and the read-only
  assertion (no non-GET on `/Zentrunk/`).
- `list_subaccounts` — zero, one, and the no-auth-token-in-output assertion.
- `drift_report` — clean state, a single URL divergence, a critical-invariant
  breach, an unbound number, a missing endpoint, `subaccount_count > 0` with no
  `main_auth_token`, and the sanitisation assertion.
- CLI — every subcommand's exit code; legacy flag aliases map correctly;
  `--json` on every verb; `route-apply` without approval exits 2 and calls
  nothing.
- `_verify_provider` — the full verdict matrix: signed/valid, signed/invalid,
  unsigned+token+match, unsigned+token+mismatch, unsigned+no-token,
  signature-required-and-absent, and each with `PLIVO_REQUIRE_ANSWER_TOKEN`
  both false and true.
- `_get_plivo_main_auth_token` — caches on success, does not cache `''`, never
  reads at import.
- `outbound-sms` adapter — each status path; the ignored `provider` field;
  MessagesTable row shape; `dltTemplateId` and `dltTemplateKey` both accepted.
- `webhook_routes.diff` — parity, each single-field divergence, and the
  `configuredAtProvider: false` case.
- Gate script — baseline vs gate semantics for gating and tracked rules,
  including the deliberate "tracked rule fails at zero to force promotion".

### Property-Based Tests

Four properties where the domain is too large to enumerate. `hypothesis==6.168.0`
added to `requirements-dev.txt` — dev-only, and that file's header already records
that it does not define the Lambda runtime, so nothing reaches production. The
existing suite uses `pytest.mark.parametrize` matrices; PBT is added only where
generation earns its keep, not as a wholesale idiom change.

1. **Signature validation is total and faithful.** Generate URLs (with and without
   query strings), parameter maps (scalar, repeated, unicode, empty), and nonces.
   Assert this implementation agrees with
   `plivo.utils.signature_v3.validate_v3_signature` on every input, and that no
   input raises. The four undocumented algorithm details in
   `plivo_signature.py`'s docstring are exactly the kind of thing generation
   catches and a fixed matrix misses.
2. **The SMS provider invariant is unconditional.** Generate arbitrary phone
   strings, message types, template keys and region overrides. Assert the
   resolved provider is `aws-end-user-messaging` for every input that sends at
   all, the region is `ap-south-1` for every Indian number and the configured
   default otherwise, and that no Indian send proceeds without an approved DLT
   template. This is Property 3 stated as a generator — the strongest form of
   `channel == SMS implies provider == AWS_END_USER_MESSAGING` available.
3. **Protected fields are never silently moved.** Generate before/after
   application dicts. Assert `verify_post_update_state` reports `ok=False`
   whenever any of the eleven protected fields differs under `_same`, and
   `ok=True` only when none does. Includes the `None`/`''`/`[]`/`{}` equivalence
   that `_same` exists for — the false positive that once triggered a rollback of
   a correct change.
4. **Snapshots and drift reports never carry a secret.** Generate reports with
   token-bearing URLs, arbitrary field additions and nested structures. Assert
   `_assert_sanitized` rejects anything matching `auth_token`, `password`,
   `secret`, and that every `*_url` field is path-only with the token present
   only as a `sha256:` fingerprint (3.18, 3.20).

### Integration Tests

Run against live AWS and live Plivo, by an operator, at the points marked in the
deployment sequence. Not in CI — CI has no AWS credentials and must stay that way.

1. **Full control-plane read** — `./scripts/plivo-reconcile` and each `inspect`
   subcommand against the live account. Output must match the live state report in
   the requirements: all three URLs PASS, `default_endpoint_app true` PASS, number
   binding unchanged PASS, endpoint unchanged PASS, Zentrunk discovered PASS.
2. **Drift detection end to end** — invoke `wecare-plivo-reconcile` manually,
   confirm zero divergences against current state. Then, in a **scratch copy of
   the report input** rather than on the live application, confirm a seeded
   divergence produces the `plivo_drift` log line with all five fields and raises
   `PlivoDriftFields`. **The live application is not mutated to test the
   detector** — seeding a real `default_endpoint_app=false` to watch the alarm
   fire would breach 3.1 and 3.6 for the sake of a test.
3. **Alarm wiring** — `DescribeAlarms` on all four new alarms; confirm
   `AlarmActions` contains the SNS topic and `TreatMissingData=notBreaching`. Set
   one alarm to ALARM via `SetAlarmState` and confirm the email arrives, then
   reset. This is the only way to prove the notification path, and it is
   non-destructive.
4. **Route manifest vs live** — `plivo-reconcile routes check` against
   `zllr9lrg7j` and the live Plivo application. Zero divergences expected, because
   measurement already showed the URLs correct.
5. **Real inbound call after the D4 deploy** — place a PSTN call to
   +918031830030, confirm the IVR plays, the hangup callback persists a CDR, the
   follow-up SMS arrives, and `plivo_request` logs `verified=true`. This is the
   gate on the plivo-answer alias move. A synthetic event cannot prove it: a real
   SIP call carries SIP headers a fixture does not, which is why the handler
   already logs `sipHeaders`.
6. **Real SMS after the D6 deploy** — one Indian send through `POST /sms/send`
   with an approved DLT template key, one international send, and one Indian send
   with a bogus template key. Expect: delivered from `ap-south-1` with `WDBEEP`;
   delivered from `us-east-1` from `+18444891209`; and `MISSING_DLT_TEMPLATE`
   refused before any provider call. Then `dry_run=True` variants, which validate
   identity and DLT parameters without delivering.
7. **Provider gate in CI** — confirm `tests.yml` runs on a PR and fails on a
   deliberately broken assertion, then confirm `provider-policy.yml` in
   `--mode gate` fails on a planted violation. A gate nobody has seen fail is not
   known to gate.

### What is not covered by an automated test

Stated rather than implied, because the gaps are load-bearing.

- **Delivery confirmation.** `AwsSmsProvider.get_delivery_status` returns
  `UNKNOWN_NO_RECEIPTS` because this account has no EUM v2 event destination. A
  test can assert submission succeeded; nothing can assert delivery. Tracked as
  migration-plan Stage 2 debt, not closed here.
- **`guard_runs_without_human_initiation`** — infrastructure assertion only, as
  stated under Fix Checking.
- **Ma-V3 against a real subaccount** — there are zero subaccounts, so T18 proves
  the mechanism with distinct synthetic tokens. The live path stays unexercised
  until a subaccount exists, which is precisely why D5 makes the condition
  *detectable* rather than merely correct.
- **Airtel voice removal** — out of scope. The 40 tracked violations have a
  pinned baseline and no test drives them to zero.

## Risk and Rollback

One row per change, with its blast radius and the exact rollback. Severity uses
the `.kiro/steering/maintenance-reporting.md` scale and is deliberately not
inflated: most of this work is additive and reversible by a file revert.

| # | Change | Risk if wrong | Severity | Blast radius | Rollback | Reversible |
|---|---|---|---|---|---|---|
| R1 | Extract the read-only core to `lambda_utils/plivo_control_plane.py` | an import moves and the CLI or the 52 tests break | LOW | developer tooling only; no runtime path imports it yet | `git revert`; the re-export block means a partial revert also works | yes, fully |
| R2 | `get_trunk`, `list_subaccounts` | a wrong Zentrunk path returns 404 and the fallback masks it | LOW | read-only; `source` field reports which path answered | revert; `list_trunks` is untouched | yes |
| R3 | CLI subcommands | an operator's existing `--apply` habit breaks | LOW | operator surface | flag aliases are retained precisely so this cannot happen; revert otherwise | yes |
| R4 | `wecare-plivo-reconcile` Lambda + hourly rule | Plivo rate limits, or a noisy alarm | LOW | 720 invocations/month, 4 GETs each, read-only, cannot mutate because the methods are not in its import graph | disable the rule (`DisableRule`), or delete rule + function | yes |
| R5 | Four new CloudWatch alarms | alarm fatigue on the one email subscriber | LOW | one mailbox | `delete-alarms`, or raise the threshold | yes |
| R6 | `.github/workflows/tests.yml` | a flaky or environment-dependent test blocks every PR | MEDIUM | all PRs to `stack` | delete the workflow file, or set `continue-on-error` on the failing job. eslint is excluded for exactly this reason — 250 errors today | yes |
| R7 | `webhook-routes.json` + `webhook_routes.py` | a false-positive divergence in the hourly drift report | LOW | one log line and one metric | revert; `configuredAtProvider: false` on `/plivo/events` is the specific guard against the most likely false positive | yes |
| R8 | `plivo-answer/resource.ts` added, not wired | Amplify later adopts it and creates a second function or takes over a live one | LOW **while unwired** | none in this phase | delete the file. It is deliberately not imported into `amplify/backend.ts` | yes |
| R9 | `_verify_provider` three-state verdict (D4) | **a mistake here drops every inbound call** | **HIGH** | 100% of inbound PSTN and WhatsApp-calling voice traffic through the IVR | `aws lambda update-alias --function-name wecare-plivo-answer --name live --function-version 7` — instant, no rebuild. Version 7 is the current live version, re-verified | yes, seconds |
| R10 | `main_auth_token` passed through (D5) | a malformed secret field breaks V3 validation and hangup callbacks 401 | MEDIUM | hangup and events callbacks; CDRs and the follow-up SMS stop. Answer/fallback unaffected | same alias move to version 7. `_get_plivo_main_auth_token` returning `''` is the designed-for case and preserves today's behaviour exactly | yes, seconds |
| R11 | `outbound-sms` rewritten to the comms layer (D6) | Indian SMS stops if the DLT template map is wrong; international SMS silently vanishes if origination pinning regresses to the simulator | **HIGH** | all SMS through `POST /sms/send` | `aws lambda update-alias --function-name wecare-outbound-sms --name live --function-version 7` — re-verified as current. The DLT gate refuses rather than sends wrong, so the failure mode is a visible refusal, not silent loss | yes, seconds |
| R12 | Frontend Sinch/Airtel removals | a dashboard panel breaks | LOW | one operator-facing page | `git revert`; Amplify redeploys from `stack`. `sendSinchSms` is a dead export — re-verified, its only occurrence in `src/` is its own definition | yes |
| R13 | `sms-in/airtel` handler returns 410 | inbound Airtel SMS receipt stops | LOW | no Airtel traffic exists once R11 lands, so there is nothing to receive | revert the handler; the route and `:live` alias are **retained**, so no route recreation is needed | yes |
| R14 | `whatsapp-calling` repointed to `wecare-sms-aws:live` | the WhatsApp-calling follow-up SMS fails | LOW | one notification path | revert; `wecare-sms-aws:live` is version 10 and already the AWS path used by `plivo-answer` | yes |
| R15 | `INDIA_PINPOINT_APP_ID` removed | a reader exists that grep missed | LOW | none — measured assigned at `sms-aws/handler.py:62` and never read | revert one line in handler and resource | yes |
| R16 | `voice-in/cdr` Sinch RCS read removed | the RCS-enabled check changes behaviour | LOW | one conditional in a CDR handler | revert. `lambda_utils/sinch_rcs.py`, `rcs-send` and `rcs-dlr` are untouched, so 3.24 holds regardless | yes |
| R17 | Gate rule split + baseline mode | a real regression lands in a tracked path and only warns | MEDIUM | CI signal quality | revert the script and baseline file. Baseline mode still fails on any *increase*, which `--expect-fail` does not — so even the failure mode is stronger than today | yes |
| R18 | `provider-policy.yml` → `--mode gate` | CI turns red on an unrelated violation | MEDIUM | all PRs | revert to `--mode baseline`. The D7 sequence exists to make this step land on a measured zero | yes |
| R19 | `hypothesis==6.168.0` in `requirements-dev.txt` | a generated counterexample makes CI non-deterministic | LOW | CI only; never packaged into a Lambda | remove the pin and the PBT files. Pin exactly, and confirm 6.168.0 is the current release at implementation time | yes |

Two rows are HIGH (R9, R11) and both are voice- or SMS-traffic-affecting Lambda
deploys. Both have a sub-minute rollback that is a single alias move to a version
that already exists in the account. That is the whole reason the deployment
sequence below puts them last and alone.

## Deployment Sequence

Ordered so that nothing production-affecting ships before the guards that would
catch it, and so the pipeline is never red for a reason unrelated to the change in
flight. D7's S0–S6 are nested at their correct positions rather than restated.

**Phase 0 — protections first. No production behaviour changes.**

| Step | Action | Verification | Approval |
|---|---|---|---|
| 0.1 | R1–R3: read/mutate split, `get_trunk`, `list_subaccounts`, `drift_report`, CLI subcommands | `pytest` — 883 + new tests pass, none deleted; `./scripts/plivo-reconcile` output identical to before | none (safe) |
| 0.2 | R6: `tests.yml` lands (**D7 S0**, first half) | a PR shows the pytest, tsc and vitest jobs green; the eslint job is present and non-gating | none |
| 0.3 | R17: rule split + `--mode baseline` replaces `--expect-fail` (**D7 S0**, second half) | gate prints 120 gating + 40 tracked against a pinned baseline and exits 0 | **[PP-SPLIT-001]** |
| 0.4 | R7: manifest + `webhook_routes.py` + `plivo-answer/resource.ts` (unwired) | `plivo-reconcile routes check` reports zero divergences against live | none (read-only) |
| 0.5 | R4, R5: drift Lambda, hourly rule, four alarms | `deploy_all_lambdas.py wecare-plivo-reconcile`; manual invoke returns zero divergences; `DescribeRule` ENABLED; `DescribeAlarms` shows all four with the SNS action; `SetAlarmState` on one confirms the email path | none — no IAM change; `wecare-digital-lambda-role` already grants the secret read, `PutMetricData` and `sns:Publish` |

At the end of Phase 0 every guard in 2.4 and 2.5 is running, and no production
behaviour has changed. That ordering is deliberate: the Phase 2 changes are the
ones with a HIGH rating, and they should deploy into an environment that is
already watching.

**Phase 1 — the gate closes. Voice traffic affected; rollback is an alias move.**

| Step | Action | Verification | Approval |
|---|---|---|---|
| 1.1 | Operator adds `main_auth_token` to `wecare/plivo/api` **if the account ever acquires a subaccount**. Not a prerequisite today — absence is the designed-for case | `DescribeSecret` shows the secret exists; the value is never read or printed | **[SECRET-MAIN-001]**, deferred |
| 1.2 | R9, R10: `plivo-answer` three-state verdict + `main_auth_token` passthrough; T19 amended | `pytest` green with T19 renamed and T20 unchanged; `deploy_all_lambdas.py wecare-plivo-answer` then `snapstart_publish.py` publishes a version and moves `live` off 7 | **[DEPLOY-PLIVO-001]** |
| 1.3 | Integration test 5: **a real PSTN call to +918031830030** | IVR plays; CDR persisted; follow-up SMS arrives; `plivo_request` logs `verified=true`; no `plivo_provider_unverified` | gate on 1.4 |
| 1.4 | R4's metric filter + alarm for `PlivoProviderUnverified` confirmed quiet | alarm in OK, not ALARM, after the real call | none |

If 1.3 fails: `update-alias --function-version 7`. The IVR is restored in seconds
and the fix is re-diagnosed offline.

**Phase 2 — the SMS cutover. Rollback is an alias move.**

| Step | Action | Verification | Approval |
|---|---|---|---|
| 2.1 | R11: `outbound-sms` rewritten (**D7 S1**) | `pytest` green incl. new T21–T23; `tsc --noEmit` clean; gating total falls 120 → 67 | **[DEPLOY-SMS-001]** |
| 2.2 | Deploy `wecare-outbound-sms` and publish | `deploy_all_lambdas.py wecare-outbound-sms` → `snapstart_publish.py`; `GetAlias` shows `live` off version 7 | part of 2.1 |
| 2.3 | Integration test 6: one real Indian send, one international, one with a bogus template key | delivered from `ap-south-1` with `WDBEEP`; delivered from `us-east-1` from `+18444891209`; third refused `MISSING_DLT_TEMPLATE` before any provider call | gate on 2.4 |
| 2.4 | R12: frontend removals (**D7 S2**) | Amplify redeploys from `stack`; dashboard SMS panel sends successfully; gating total 67 → 42 | none (low risk, reversible) |
| 2.5 | R13, R14: `whatsapp-calling` repointed, `sms-in/airtel` → 410 (**D7 S3a**) | gating total 42 → 4; route retained, alias retained, nothing deleted | none — no deletion in this step |
| 2.6 | R15: `INDIA_PINPOINT_APP_ID` removed (**D7 S4**) | gating total 4 → 2 | none |
| 2.7 | R16: `voice-in/cdr` Sinch RCS read removed (**D7 S5**) | gating total 2 → 0; `rcs-send`/`rcs-dlr` untouched | none |

The `provider` field being **ignored rather than rejected** is what makes 2.1–2.4
safe in either order. Amplify deploys the frontend automatically on commit to
`stack` while Lambda deployment is manual, so the two sides can land in either
sequence. Ignoring is safe both ways; rejecting with 400 would break the dashboard
in the Lambda-first case.

**Phase 3 — re-arm.**

| Step | Action | Verification | Approval |
|---|---|---|---|
| 3.1 | R18: `provider-policy.yml` → `--mode gate` (**D7 S6**) | gate exits 0 with 0 gating violations and 40 tracked; a planted violation exits non-zero | none — a measured zero, not a forced one |
| 3.2 | `docs/provider-policy.md` written | the gate no longer cites a file that does not exist | none |
| 3.3 | Integration test 7: confirm both workflows fail when they should | a deliberately broken assertion reddens `tests.yml`; a planted violation reddens `provider-policy.yml` | none |

**Deferred, outside this fix.** **D7 S7** — delete `wecare-sms-in-airtel`, its
`POST /sms-in/airtel` route, its tables and the `wecare/airtel-iq` /
`wecare/airtel/sms` secrets. Destructive and irreversible; requires its own
pointwise confirmation and is not bundled here. Airtel **voice** removal, then
promoting `airtel-voice-runtime` from tracked to gating, is a separate migration
with a separate plan.

## Confirmation Queue

Per `.kiro/steering/maintenance-reporting.md`. Routine safe work — the read-only
extensions, the drift Lambda, the alarms, the test workflow, `pytest`, `tsc`,
`vitest`, the gate script, safe commits and a normal push to `stack` — proceeds
without asking. These five need an explicit decision. Respond `YES 1`,
`YES 1,2`, `NO 3`, `SKIP 4`, or `YES ALL SAFE ITEMS`.

**[PP-SPLIT-001] — Split `airtel-runtime` into gating SMS and tracked voice rules.**
*Why*: 2.12 asks for zero violations across six rules, but 40 of the 111
`airtel-runtime` hits are Airtel **voice** in `voice-in/c2c`, `voice-in/obd` and
`outbound-voice` — a separate migration by `docs/provider-inventory.md` §5.2 and
the migration-plan risk register. Zero is unreachable inside this scope.
*Exact effect*: `check-provider-policy.sh` gains `--mode baseline|gate` and a
pinned baseline file; `airtel-runtime` becomes `airtel-sms-runtime` (gating, target
0) and `airtel-voice-runtime` (tracked, baseline 40). Every other rule stays
gating.
*Resources affected*: none — CI configuration and one script.
*Local files*: `scripts/check-provider-policy.sh`,
`scripts/provider-policy-baseline.json` (new), `.github/workflows/provider-policy.yml`,
`docs/provider-policy.md` (new).
*Git effect*: commits to `stack`.
*Rollback*: revert two files. Even mid-flight, baseline mode fails on any increase,
which `--expect-fail` does not.
*Risk*: MEDIUM — CI signal quality, no production effect.
*This departs from the literal text of 2.12.* It needs either your agreement or a
reading of 2.12 as "zero across the gating rule set".
*Recommended*: **YES.** The alternative is allowlisting the voice paths, which
would let a genuine regression there pass silently.

**[DEPLOY-PLIVO-001] — Production deployment checkpoint: `wecare-plivo-answer`.**
| Field | Value |
|---|---|
| Account / region | 775261844268 / us-east-1 |
| Role | `arn:aws:iam::775261844268:user/wecare-admin` (profile `wecare-prod`) |
| Branch / commit | `stack` / recorded at execution |
| Function to deploy | `wecare-plivo-answer` — three-state verdict, `main_auth_token` passthrough |
| Unchanged | all other 61 functions |
| Blocked | none |
| Secrets status | `wecare/plivo/api` read by reference at request time; `main_auth_token` optional, absence is the designed-for case |
| Tests | `pytest` 883+ green, T19 amended, T20 unchanged |
| Build | `deploy_all_lambdas.py --dry-run wecare-plivo-answer` validates imports against the package and its 0 layers |
| Infra diff | + 1 metric filter, + 1 alarm. No IAM change |
| Destructive changes | none |
| Rollback version | **`live` → 7** (re-verified current) |
| Estimated downtime | none expected. Worst case is answer-path rejection, which a real test call detects immediately and the alias move reverses in seconds |
*Risk*: **HIGH** — 100% of inbound IVR voice traffic.
*Recommended*: **YES**, gated on integration test 5 (a real call) before Phase 2
begins.

**[DEPLOY-SMS-001] — Production deployment checkpoint: `wecare-outbound-sms`.**
| Field | Value |
|---|---|
| Account / region | 775261844268 / us-east-1 |
| Function to deploy | `wecare-outbound-sms` — handler rewritten to `lambda_utils.comms` |
| Unchanged | `wecare-sms-aws` (live version 10) keeps serving `/sms-aws/send` |
| Secrets status | `wecare/airtel-iq` and `wecare/sinch/sms` become unread. **Not deleted** — deletion is D7 S7 with its own confirmation |
| Tests | `pytest` green incl. new T21–T23 and the 44 unchanged comms tests carrying 3.26 and 3.27 |
| Infra diff | none. No IAM change — the change narrows what the function reads |
| Destructive changes | none. The route, the alias and both secrets survive |
| Rollback version | **`live` → 7** (re-verified current) |
| Estimated downtime | none. The DLT gate refuses rather than mis-sends, so the failure mode is a visible refusal |
*Risk*: **HIGH** — all SMS through `POST /sms/send`, including the IVR follow-up
reachable from the dashboard.
*Recommended*: **YES**, gated on integration test 6 (three real sends).

**[SECRET-MAIN-001] — Add a `main_auth_token` field to `wecare/plivo/api`.**
*Why*: 2.8 requires Ma-V3 to validate against the main-account token. At zero
subaccounts the existing `main_auth_token or auth_token` fallback is correct, so
this is not needed today.
*Exact effect*: one field added to an existing secret. The value is never read into
context, never printed, never placed on a command line
(`.kiro/steering/secret-handling.md`). Entered by the operator through a hidden
input.
*Rollback*: remove the field; the fallback resumes.
*Risk*: LOW, and **deferred** — raise only if a subaccount is created. The drift
Lambda reports `subaccount_count > 0` with no `main_auth_token` as a divergence,
so the day it matters, an alarm says so.
*Recommended*: **SKIP for now.** Not a blocker for any step above.

**[PBT-DEP-001] — Add `hypothesis==6.168.0` to `requirements-dev.txt`.**
*Why*: Properties 1–4 under Property-Based Tests need generation; the existing
suite is matrix-only.
*Exact effect*: one pinned line in a dev-only file whose header already states it
does not define the Lambda runtime. The deploy scripts bundle only `handler.py`,
`lambda_utils/` and a function's own modules, so it cannot reach a Lambda package.
*Rollback*: remove the pin and the four PBT files.
*Risk*: LOW.
*Note*: 6.168.0 is the latest release I could find; **confirm it is current at
implementation time and pin exactly** rather than using a range.
*Recommended*: **YES.**

No confirmation is requested for IAM changes, secret deletion, resource deletion,
KMS, force push or history rewrite, because this design contains none.

## Status of Unverified Items

Recorded explicitly. Each is either designed around or deferred; none is assumed
away.

| Item | Status | How the design handles it |
|---|---|---|
| `GET /Zentrunk/Trunk/{trunk_id}/` returns 200 | **NOT VERIFIED.** The collection path is confirmed 200; the single-resource path was never exercised. Confirming it needs the Plivo credential, which `aws-agent-rules` forbids reading | `get_trunk` tries the direct GET, falls back to filtering `list_trunks()`, and reports which answered in a `source` field. Correct either way, and it says which it used |
| `wecare/plivo/api` contains a `main_auth_token` field | **CANNOT BE VERIFIED.** Requires reading the secret value, which `aws-agent-rules` prohibits. `DescribeSecret` does not expose keys | Absence is the designed-for case: the getter returns `''`, the existing `or auth_token` fallback applies, behaviour is identical to today. Adding the field is an operator task **[SECRET-MAIN-001]**, not a code prerequisite |
| The account has 0 subaccounts | **CARRIED FORWARD, NOT RE-VERIFIED** in this phase. The figure comes from the earlier measurement recorded in `plivo_signature.py`'s docstring | `list_subaccounts()` re-reads it hourly, and a non-zero count with no `main_auth_token` becomes a drift finding. Correct by detection rather than by assumption |
| Which SES-style selector Plivo signs with, and whether any live callback currently carries only Ma-V3 | **NOT OBSERVED.** No live callback headers were captured in this phase | T18 proves the mechanism with distinct synthetic tokens. The handler logs `mainTokenConfigured` so a real callback's path becomes visible in CloudWatch once traffic flows |
| Whether `hypothesis` 6.168.0 is the current release | **NOT VERIFIED against PyPI at pin time.** Found via web search, not resolved by pip | **[PBT-DEP-001]** requires confirming and pinning exactly at implementation time |
| Whether any caller outside `src/` and `amplify/` posts to `POST /sms/send` | **NOT PROVABLE by grep.** It is a public `api.wecare.digital` path; an external integration could exist | This is the reason D6 keeps the route and guts the handler rather than deleting the route. An unknown caller keeps working and is silently corrected to AWS. Deleting the route would 404 it |
| Whether `eslint`'s 250 errors include any that this change would introduce | **NOT SEPARATED.** The 314 problems / 250 errors were measured as a total, not attributed | eslint is non-gating in `tests.yml` for exactly this reason. Driving it down is a P2 improvement with its own scope |
| Live delivery of any SMS sent through the new path | **UNOBSERVABLE.** No EUM v2 event destination exists in this account | `get_delivery_status` returns `UNKNOWN_NO_RECEIPTS` rather than manufacturing a status. Integration test 6 confirms submission and DLT refusal, not delivery. Tracked as migration-plan Stage 2 debt |
| Phase 1's "174 existing tests" figure | **SUPERSEDED BY MEASUREMENT.** Re-measured for this document: **883 pass in 5.18 s** across the whole suite, of which **153** are Plivo (`test_plivo_control_plane` 52, `test_plivo_signature` 50, `test_plivo_routes` 28, `test_plivo_answer` 23) and **98** are the SMS layer (`test_comms_sms` 44, `test_sms_aws_dlt` 54) | The design plans against the measured 883/153/98. Noted rather than silently corrected, because the requirements document cites 174 |

**Not verified and deliberately not attempted**: any live Plivo mutation, any
Zentrunk write, any number rebinding, any SIP endpoint change, any ElevenLabs or
Meta change, and any Lightsail action. All are out of scope per the requirements,
and none is needed to close any of the thirteen defects.
