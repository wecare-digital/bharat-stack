# AWS inventory findings — 2026-09-26

Backlog item 1. Companion to the machine-generated `aws-inventory.json` /
`aws-inventory.md` (regenerate: `python scripts/aws_account_inventory.py`).
This file carries the judgement the generator cannot: **what is reusable, what
is a defect, and which backlog items the measurement just moved.**

Scope: account `775261844268`, identity `user/wecare-admin`, `us-east-1`
(+ `ap-south-1` for SES). Fourteen service families enumerated.
**Collector errors: 0**, so the counts below are authoritative rather than
partial. Secrets were read as metadata only; no secret value was retrieved.

## Every dated count in steering is now superseded

`00-current-owner-overrides.md` carried a baseline snapshot and instructed that
it be rediscovered rather than trusted. Rediscovered:

| Item | Dated snapshot | Measured 2026-09-26 | Direction |
|---|---:|---:|---|
| Lambda functions | 58 | **65** | +7 |
| HTTP APIs | 2 | **1** | −1 (only `zllr9lrg7j`) |
| HTTP API routes | 332 | **361** | +29 |
| API Gateway authorizers | 0 | **0** | unchanged |
| Routes `AuthorizationType=NONE` | 332 | **361** | +29 |
| Regional WAF WebACLs | 0 | **1** | +1 |
| CloudFront-scope WAF WebACLs | not measured | **1** | new |
| Cognito MFA | OFF | **OPTIONAL** (admin pool) | improved |
| GuardDuty detectors | 0 | not re-measured this run | — |
| Security Hub | not subscribed | not re-measured (excluded by owner) | — |

The "2 HTTP APIs" figure was wrong or has since been reduced to one. There is a
single HTTP API, `zllr9lrg7j` / `wecare-digital-api`, stage `prod`, and zero
REST APIs.

## Reusable — do not provision these again

### The unified notification service already has its entire data layer

This is the most consequential finding. Backlog item 4 is described as one of the
biggest unresolved production risks, and its infrastructure is **already built,
correctly shaped, and completely unused**:

| Table | Hash key | GSIs | TTL | PITR | Items |
|---|---|---:|---|---|---:|
| `stack-wecare-digital-NotificationEvents` | `eventClaimKey` | 1 | ENABLED | ENABLED | **0** |
| `stack-wecare-digital-NotificationOutbox` | `jobId` | 1 | ENABLED | ENABLED | **0** |
| `stack-wecare-digital-NotificationDeliveries` | `deliveryId` | 2 | ENABLED | ENABLED | **0** |
| `stack-wecare-digital-NotificationAttempts` | `attemptId` | 1 | ENABLED | ENABLED | **0** |

All four are tagged `domain=notifications, phase=3`. The key design maps
one-to-one onto item 4's requirements: `eventClaimKey` is the parent
connected-call event's idempotency claim, `NotificationOutbox` is the
transactional outbox, `NotificationDeliveries` gives independent per-channel
(WhatsApp/SMS/RCS) delivery rows, and `NotificationAttempts` carries lease/retry
state. Transport exists too — `stack-wecare-digital-notification-queue` with
redrive to `stack-wecare-digital-notification-dlq` at `maxReceiveCount=3`.

Supporting idempotency primitives are live and in use, not empty:
`stack-wecare-digital-WebhookDedup` (`eventId`, 241 items) and
`stack-wecare-digital-RateLimitTable` (`id`, 12 items).

**Consequence: item 4 is an application-code and wiring task, not a provisioning
task.** The migration target for item 5 is also visible —
`stack-wecare-digital-CallNotificationsTable`, keyed on bare `callId` with 0
items, is the older single-table shape the canonical domain replaces.

### Other reusable infrastructure

- **SES for item 39** — `one@wecare.digital` is verified with DKIM `SUCCESS`,
  in an account with production access and a 50,000/day quota in `us-east-1`.
  Configuration set `wecare-digital` exists. No new identity needed.
  Note `ap-south-1` SES is **still sandboxed** (`production_access=False`,
  200/day) — do not send customer email from that region.
- **Cognito for items 28–48** — `us-east-1_46ULYuukt`
  (`WECARE.DIGITAL-CUSTOMERS`) already carries client
  `wecare-customer-whatsapp-otp` and all three custom-auth triggers
  (`DefineAuthChallenge`, `CreateAuthChallenge`, `VerifyAuthChallengeResponse`).
  The passwordless WhatsApp-OTP scaffolding is provisioned; ≈1 user means it is
  not yet carrying real registrations.
- **Cognito RBAC for item 114** — admin pool `us-east-1_cSx0RHCIR` already has
  groups `Admin`, `Operator`, `Partner`, `Viewer`.
- **WAF rule sets for the item 114/WAF target** — two ACLs exist with real rules,
  so the authoring work is done (see the defect below about where they point).
- **DLQ capacity** — 8 queues, 5 of them DLQs, every non-DLQ queue has a redrive
  policy. No new queue needed for item 4.

## Defects found by measurement

### D1 · Two DLQ alarms can never fire, and the notification DLQ has none

`HIGH`. The alarms reference a `base-wecare-digital-` queue-name prefix that no
longer exists; the real queues use `stack-wecare-digital-`:

| Alarm | Watches queue | Queue exists? |
|---|---|---|
| `wecare-inbound-dlq-depth` | `base-wecare-digital-inbound-dlq` | **no** |
| `wecare-outbound-dlq-depth` | `base-wecare-digital-outbound-dlq` | **no** |

So three DLQs are effectively unmonitored:
`stack-wecare-digital-inbound-dlq`, `stack-wecare-digital-outbound-dlq`, and
`stack-wecare-digital-notification-dlq` (which never had an alarm at all).
Inbound and outbound are the WhatsApp message paths, and the notification DLQ is
the one item 4 depends on. All three are currently empty, so nothing has been
lost yet — but a failure there would be silent.

This is why the alarm count looked healthy: 42 alarms, 0 in `ALARM`, 0
`INSUFFICIENT_DATA`, 0 without an action. A stale dimension produces a
permanently green alarm, which reads as success. Directly relevant to item 214.

### D2 · `wecare-cognito-waf` protects nothing

`MEDIUM`. Regional ACL, default action `Allow`, three real rules
(`auth-rate-limit-per-ip`, `AWSManagedRulesAmazonIpReputationList`,
`AWSManagedRulesCommonRuleSet`) — and `list_resources_for_web_acl` returns an
empty list. It is associated with no resource.

The CloudFront-scope ACL is the opposite, and the distinction matters because
CloudFront-scope associations cannot be read from the WAF API. Asked directly,
the Amplify app reports `wafStatus: ASSOCIATION_SUCCESS` for
`wecare-amplify-waf` (4 rules, adds `AWSManagedRulesKnownBadInputsRuleSet`).
**So the public web app is protected and the Cognito/API surface is not.** The
owner-override target "WAF must be implemented and live-verified" is half met.

The three CloudFront distributions in this account
(`E1SZBXLQ4XNLJ7` mta-sts, `E2GP22R4BIFGQ3` wecare-digital-get,
`ERCXSFDL0VM8X` app.wecare.digital) all report no web ACL; the Amplify-managed
distribution is not among them, which is why the app-side query was necessary.

### D3 · No declarative source reproduces production infrastructure

`HIGH` for items 196, 218–225 and 226. `stack-wecare-digital-` is a **naming
prefix, not a CloudFormation stack**. Evidence:

- 7 CloudFormation stacks exist in total (including every non-active status):
  `CDKToolkit`, five `wecare-elevenlabs-*`, and `wecare-temp-code-inspector`.
- Zero stacks named `amplify-*` or `stack-wecare*`.
- `wecare-contacts` carries **no tags at all** — no
  `aws:cloudformation:stack-name`.

The 65 Lambdas, 79 DynamoDB tables and 8 queues were created imperatively by the
scripts in `scripts/`. The `amplify/` tree is source-of-truth for function
**code**, deployed by `scripts/deploy_all_lambdas.py` via
`update-function-code`; the Amplify app `d22dm4b0jn71jw` is frontend hosting
only (`platform=WEB`, 23 custom rules). No `cdk synth` or `terraform plan`
reproduces the account, so item 196 cannot be satisfied by validating the
existing `amplify/` definitions, and the DR drills in items 218–225 must be
written against scripts plus Lambda alias rollback rather than stack rollback.

`wecare-temp-code-inspector` and the five `wecare-elevenlabs-*` stacks are
leftovers and belong in item 226's cleanup scope.

### D4 · API-Gateway-level authorization is still entirely absent

`HIGH`, item 6. All **361 of 361** routes report `AuthorizationType=NONE` and
the API has **0 authorizers**. The route count grew by 29 against the dated
snapshot, so the surface widened while authorization stayed at zero. Per
steering this must be read carefully — handler-level authentication and provider
signature verification may well exist — but there is no gateway-level control on
any route, so item 6's "separate intentionally public signed webhooks from
accidentally public APIs" cannot be answered from gateway configuration alone
and requires the handler-level audit.

### D5 · Lambda alias coverage drifted again, as predicted

`INFORMATIONAL`. 58 of 65 functions have a `live` alias. The 7 without, where
`$LATEST` reaches production directly: `wecare-ad-attribution`,
`wecare-docs-scraper`, `wecare-get-miss-redirect`,
`wecare-partner-token-refresh`, `wecare-seo-tools`, `wecare-sla-engine`,
`wecare-url-shortener`.

`lambda-snapstart-deploy.md` records 56/6 then 53/9 and warns the ratio drifts as
aliases are provisioned. It is now 58/7. Three of the seven
(`docs-scraper`, `get-miss-redirect`, `seo-tools`) are documented deliberate
exceptions. The other four are not yet explained.

SnapStart remains `None` on all 65 functions, confirming that steering file's
correction. Runtime is `python3.12` on 64 of 65; the exception is
`wecare-docs-scraper` (`PackageType=Image`).

### D6 · 67 of 79 DynamoDB tables are empty

`INFORMATIONAL`, feeds items 227 and 234. Empty is not the same as unused — a
cache or a table behind an unreleased feature is legitimately empty — but 85% of
the table estate holding nothing is the measurement item 227 needs. 12 tables
lack point-in-time recovery; most are caches (`CatalogCacheTable`,
`SiteLanguageCache`, `WixProductsCache`, `WixOrdersCache`), but
`SecureFilesTable`, `DownloadGrantsTable`, `PstnSoftphoneSessions`,
`WhatsAppPhonesTable`, `FlowDraftTable`, `WebhookDedup` and `RateLimitTable`
also lack it.

## Provider retirement — exact recovery-window evidence

From CloudTrail `DeleteSecret` events (60-day lookback), which gives the precise
dates items 8–12 require:

| Secret | Deleted | Window | Permanent deletion | State today |
|---|---|---:|---|---|
| `wecare/payu` | 2026-08-26 10:10:20Z | 30d | **2026-09-25 10:10:20Z** | ✅ **permanently gone** |
| `wecare/airtel-iq` | 2026-09-20 01:46:18Z | 30d | 2026-10-20 01:46:18Z | ⏳ recoverable |
| `wecare/airtel/c2c` | 2026-09-20 01:46:18Z | 30d | 2026-10-20 01:46:18Z | ⏳ recoverable |
| `wecare/airtel/obd` | 2026-09-20 01:46:18Z | 30d | 2026-10-20 01:46:18Z | ⏳ recoverable |
| `wecare/airtel/sms` | 2026-09-20 01:46:19Z | 30d | 2026-10-20 01:46:19Z | ⏳ recoverable |
| `wecare/sinch/sms` | 2026-09-20 01:46:19Z | 30d | 2026-10-20 01:46:19Z | ⏳ recoverable |
| `wecare/elevenlabs` | 2026-09-20 08:50:01Z | force | 2026-09-20 08:50:01Z | ✅ gone (forced) |
| `wecare/wix-api-key` | 2026-09-23 02:36:45Z | force | 2026-09-23 02:36:45Z | ✅ gone (forced) |

**Item 8's secret-layer requirement is now provable and met.** `ListSecrets`
with `IncludePlannedDeletion=True` returns 31 secrets and **zero** matching
`payu`. Its 30-day window expired 2026-09-25, one day before this measurement,
so `wecare/payu` is permanently deleted and unrecoverable. Razorpay remains,
as `wecare/razorpay/api` and `wecare/razorpay-webhook`.

This also reconciles the "six already scheduled" figure in standing
authorization: five provider secrets plus `wecare/elevenlabs`, which was
subsequently force-deleted, leaving five scheduled.

**Items 9, 10, 11 and 12 cannot yet claim permanent deletion.** The four Airtel
secrets and `wecare/sinch/sms` stay recoverable until **2026-10-20**. Per
standing authorization these are to be left to complete — never cancelled, never
rescheduled. `wecare/sinch/rcs` is present and untouched, which is correct: item
11 retires Sinch SMS only.

## Healthy, no action needed

- **S3** — all 6 buckets encrypted (3 `aws:kms`, 3 `AES256`), full public-access
  block on every one, no public bucket policy, versioning on 5 of 6
  (`wecare-digital-mta-sts` is the exception and holds only the public MTA-STS
  policy document).
- **CloudWatch logs** — 81 log groups, **zero without a retention policy**,
  0.16 GB stored total.
- **Route 53** — single zone `wecare.digital.` (`Z03939753QJGZ6ZD6BXO8`), 42
  records, exactly one MX, 7 TXT. Consistent with the fail-closed email posture;
  nothing in this inventory touched it.
- **EventBridge** — 6 rules, all `ENABLED`, no disabled rules. Two of the four
  scheduled rules have a target DLQ (`media-cleanup`, `scheduled-messages`); the
  other two (`docs-scraper-daily`, `partner-token-refresh-daily`) do not, which
  is a minor gap rather than a defect.
- **Amplify `stack` branch** — production, auto-build on, three most recent jobs
  all `SUCCEED`, latest job 896 at commit `5653a12a0f5a` (2026-09-26 03:05Z).

## What this changes in the backlog

| Item | Effect of this measurement |
|---|---|
| 1 | Complete. `aws-inventory.{json,md}` + this file are the deliverable; regenerable in ~150s with 0 errors. |
| 4 | Re-scoped from "build the notification service" to "write the code against four already-correct tables and an existing queue/DLQ pair". |
| 5 | Migration source identified: `CallNotificationsTable` (`callId`, 0 items). |
| 6 | Quantified: 361/361 `NONE`, 0 authorizers. Gateway config alone cannot classify the routes; needs the handler audit. |
| 8 | Secret layer **closed** with exact expiry evidence. Source/IaC/UI scan still outstanding. |
| 9–12 | Blocked on the 2026-10-20 window expiry, by design. Exact ARNs and dates now recorded. |
| 39 | SES layer satisfied in `us-east-1`; `ap-south-1` is sandboxed and must not be used for customer email. |
| 113/114 | Admin MFA is `OPTIONAL` not `OFF`; RBAC groups already exist. |
| 196/218–225 | Must be designed against imperative scripts — no stack reproduces production. |
| 214 | Three unmonitored DLQs and two permanently-green stale alarms (D1). |
| 226/227/234 | Baseline captured: 7 stacks (6 stale), 67 empty tables. |

## Reproducing this

    python scripts/aws_account_inventory.py            # all 14 families, ~150s
    python scripts/aws_account_inventory.py --only lambda,api_gateway
    python scripts/aws_account_inventory.py --json-only

The collector counts its own failures and reports `error_count`; a non-zero
count marks the inventory PARTIAL. This is deliberate — an earlier alias census
read 34/28 instead of 53/9 because failed API calls were silently treated as
"resource absent". Treat any run with `error_count > 0` as unusable for
decisions.
