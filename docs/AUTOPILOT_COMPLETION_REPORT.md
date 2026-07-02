# WECARE.DIGITAL — Autopilot Completion Report

**Session goal:** complete P0–P4 autonomously. **Principle applied:** execute everything
safe/additive/verifiable; stage (with ready-to-run runbooks) anything destructive or
high-blast-radius that cannot be visually verified while unattended. Nothing that could break
live traffic was fired blind. S3 versioning + KMS rotation remain de-scoped (owner decision).

---

## ✅ EXECUTED & VERIFIED THIS SESSION (live)

### P0 — closed
- **`RateLimitTable` TTL enabled** on attr `lastUpdatedAt` (now+86400 epoch). 0 rows purged
  (table transient, all values future-dated). Rate-limit data is ephemeral + fails-open → safe.
  Script: `scripts/_enable_ratelimit_ttl.py`.
- All prior P0 monitoring already live (API Gateway, EventBridge, DynamoDB, Lambda/SQS).

### P1 — observability layer (all additive, verifiable, zero risk)
Added 11 alarms + 1 dashboard (`scripts/_create_p1_observability.py`):
- `wecare-bulk-dlq-depth` — **closed a real gap** (bulk DLQ was unmonitored)
- `wecare-queue-age-bulk` — stuck-backlog detection (oldest msg > 15m)
- `wecare-lambda-throttles` — account-wide Lambda throttling
- `wecare-lambda-errors-*` — error alarms on 8 revenue/message-critical fns
  (razorpay-webhook, payu-webhook, scheduled-messages, bulk-worker, service-api,
  whatsapp-business-api, billing, invoice-engine)
- **Dashboard `wecare-platform-health`** — API 5xx/latency, Lambda errors/throttles,
  SQS DLQ depths, EventBridge failures, DynamoDB throttles in one view.

### Code hygiene
- Dead `ADMIN_ACTION_LOG_TABLE` constant removed (commit `126ce97`). Zero runtime impact
  (constant was never read) → no Lambda redeploy required.

---

## 📊 LIVE ALARM INVENTORY — 39 total → all page `one@wecare.digital` (confirmed)

| Group | Count | Notes |
|---|---|---|
| DynamoDB throttle (per-table) | 14 | hot tables |
| DynamoDB user-errors (account) | 1 | |
| API Gateway 5xx + p99 latency | 4 | both HTTP APIs |
| EventBridge FailedInvocations | 2 | both scheduler rules |
| EventBridge DLQ depth | 1 | new DLQ |
| Lambda errors (inbound/outbound + 8 critical) | 10 | |
| Lambda throttles (account) | 1 | new |
| SQS DLQ depth (inbound/outbound/bulk/eventbridge) | 4 | bulk was a gap, now closed |
| SQS queue-age (bulk) | 1 | new |
| SNS delivery failures | 1 | |
| SIP cert expiry | 1 | |
Plus the **Amplify build-failure EventBridge rule** (ENABLED).

---

## 🟡 STAGED — P1 safe-deploy (needs a maintenance window; NOT fired unattended)

**Why staged:** these repoint or version live invocation paths. A wrong alias/canary switch
can break live traffic; must be watched.

### Lambda versions + `live` alias + CodeDeploy canary w/ auto-rollback
Runbook (per critical function):
1. `aws lambda publish-version --function-name <fn>`
2. `aws lambda create-alias --function-name <fn> --name live --function-version <n>`
3. Repoint the API Gateway/SQS/EventBridge integration ARN → the `:live` alias ARN.
4. Create CodeDeploy app + deployment group (`Canary10Percent5Minutes`) with an
   alarm rollback on the function's `wecare-lambda-errors-<fn>` alarm.
> Do the 8 critical fns first. Verify each alias serves traffic before adding canary.

### Auto-remediation Lambda (DLQ redrive)
Prepared design (build + test in a window before enabling — auto-redrive risks poison-loops):
- Lambda subscribed to the alarm SNS topic; on `*-dlq-depth` ALARM, `StartMessageMoveTask`
  from DLQ → source with a **max-receive guard** so poison messages don't loop.

### Synthetics canary
- Needs: artifacts S3 bucket + IAM role + endpoint. Webhook-health GET every 5m is safe;
  admin-login canary needs a stored credential (Secrets Manager). Not created unattended
  (touches live endpoints + creates IAM).

### Cognito Advanced Security (threat protection)
- Optional/paid, single admin user. Enable to **AUDIT** mode (logs, never blocks logins):
  `aws cognito-idp update-user-pool --user-pool-id <id> --user-pool-add-ons AdvancedSecurityMode=AUDIT`
- Left as owner decision (billing change).

---

## 🟠 STAGED — P2 structural (high blast radius; supervised only)

### DynamoDB consolidation (~61 → ~35–40 tables)
- **NOT a delete job.** "Empty" tables have live writers. Requires: pick the canonical
  `Messages` timeline schema → dual-write from handlers → backfill copy → cutover reads →
  retire old table after a soak. Per-table migration scripts + verification required.
- Do **after** handler refactor; never drop a table with a writer.

### Frontend de-duplication (~120 → ~70–80 pages)
- Retire per-channel `inbox`/`campaign`/`logs` in favour of unified `dm/*` — **only after**
  confirming `dm/*` fully covers each channel + updating nav + adding redirects for indexed URLs.
- **Stub pages kept intentionally** (`carbon`, `nocode`, `task`, `studio`, `test-agent`):
  they're "Coming Soon" placeholders; `studio` has a canonical SEO URL. Deleting live routes
  blind risks nav breakage + 404s on indexed URLs. Remove only with redirect + sitemap update.

### Lambda → IaC (`cdk import`)
- Bring the 54 Python Lambdas under Amplify/CDK. **Blocked locally:** `ampx sandbox`/
  `pipeline-deploy` need Docker (absent) + run only in CI. Path: enable Docker on a CI runner,
  `cdk import` with a zero-replacement diff gate, then `ampx pipeline-deploy` via GitHub Actions.
- Confirmed safe context: backend uses **referenceAuth** (points at existing Cognito, no
  duplicate pool) and **no CFN backend stack exists** — live app runs on the standalone
  `stack-wecare-digital-*` tables + Python Lambdas.

---

## 🔵 P3/P4 — product roadmap (features, not defects) — see `gap_remediation_plan.md`
CI/CD + staging env, Embedded Signup, Marketing Messages API, CSW timer, Meta analytics
dashboards, Template Quality dashboard, OTP service, GDPR deletion endpoint, conversion
tracking. These are build efforts requiring product decisions, not autonomous infra fixes.

---

## Residual notes
- **2 critical vulns** = bundled `fast-xml-parser` in `@aws-amplify/graphql-api-construct`
  (build-time only, unreachable by `overrides`). Clears when Amplify ships an updated construct.
- Repo clean, HEAD = `origin/stack`, Amplify build **#509 SUCCEED**.
- All boto3 tooling is idempotent and re-runnable in `scripts/`.
