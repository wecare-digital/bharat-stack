# Resilience & Self-Healing Blueprint

Goal: factored, manageable, low-risk stack that **detects errors**, **notifies**, **auto-recovers**,
and is **restorable** when something breaks. Assessed against the live account.

## What already exists (good — keep)
- **DLQs + redrive:** inbound/bulk/outbound DLQs; `bulk-queue → bulk-dlq` (maxReceiveCount 3); `dlq-replay` Lambda.
- **Alarms:** account-wide Lambda errors (>25/5m) + throttles (>10); per-DLQ depth (>10); bulk-queue stuck (age>15m); per-Lambda error alarms for 17 critical functions → all publish to SNS `stack-wecare-digital`.
- **Dashboard**, **90-day log retention** on all Lambda log groups, **WAF** (cost-gated).
- **DynamoDB PITR: ENABLED** on key tables (Contacts, Messages, Invoices, Payments, Order, Users, WA In/Out) → restore up to 35 days.

## Gaps (ranked)
| # | Gap | Impact | Fix |
|---|---|---|---|
| 1 | **No human subscriber on alarm topic** (only a Lambda) | Alarms fire, nobody is told | Subscribe email/SMS/Slack to the SNS topic |
| 2 | **No auto-rollback on bad deploy** | A bad `_deploy_everything.py` push stays live until manual revert | Lambda versions+aliases + CodeDeploy canary w/ auto-rollback on error alarm |
| 3 | **No DynamoDB alarms** | Throttles / system errors invisible | Alarms on `ThrottledRequests`, `SystemErrors`, `UserErrors` |
| 4 | **No API Gateway alarms** | 5xx / latency spikes invisible | Alarms on 5xx count + p99 latency per API |
| 5 | **No proactive health check** | Failures found only after they happen | CloudWatch Synthetics canary on webhook + admin login |
| 6 | **Auto-remediation is partial** | DLQ drain / restarts are manual | Alarm → EventBridge → remediation Lambda (auto-redrive, etc.) |
| 7 | **54 Lambdas outside IaC** | Config drift, no rollback, no review | `cdk import` adopt (see LAMBDA_IAC_IMPORT_PLAN.md) |
| 8 | **No Amplify build-failure notification** | Broken frontend deploy unnoticed | EventBridge rule on Amplify job FAILED → SNS |
| 9 | **No drift detection** | Silent config drift (like the TTL bug) | AWS Config rules / scheduled verifier (`_verify_ddb_ttl.py` pattern) |

## "In case it breaks → how it auto-fixes" (target model)
- **Bad code deploy** → alias shifts traffic via CodeDeploy canary; error alarm trips → **automatic rollback** to previous version (no human).
- **Message/webhook processing failure** → retried, then lands in **SQS DLQ** → `dlq-replay` reprocesses (make it alarm-triggered for auto-drain).
- **Accidental data delete/corruption** → **PITR restore** to any point in last 35 days.
- **Throughput spike / throttle** → DynamoDB **PAY_PER_REQUEST** (verify) + Lambda reserved concurrency; throttle alarm notifies.
- **Endpoint down** → **Synthetics canary** alarm → notify (+ optional auto-action).
- **Drift** (config ≠ reality) → scheduled verifier + AWS Config → alarm.

## Final steps (prioritized, each independently shippable)

### P0 — do now (minutes, low-risk, huge value)
1. **Wire human notification.** Subscribe an email/SMS (and/or Slack via chatbot) to SNS `stack-wecare-digital`.
   Confirm what `wecare-inbound-whatsapp` does as a subscriber (looks accidental — verify/clean up).
2. **Add DynamoDB alarms** (per critical table): `ThrottledRequests`, `SystemErrors`, `UserErrors` → SNS.
3. **Add API Gateway alarms**: 5xx count + p99 latency per HTTP API → SNS.
4. **Add Amplify build-failure rule**: EventBridge (`Amplify Deployment Status` = FAILED) → SNS.

### P1 — near-term (safe deploys + auto-heal)
5. **Safe Lambda deploys:** publish versions + `live` alias per function; deploy via CodeDeploy canary
   (10% → 100%) with **auto-rollback** on the function's error alarm. Replaces blind `update_function_code`.
6. **Auto-remediation Lambda:** alarm → EventBridge → remediation (auto-redrive DLQ when depth high;
   re-trigger stuck bulk queue). Formalize the existing alarm→Lambda wiring here.
7. **Synthetics canary:** 1 canary hitting the webhook health path + admin login every 5 min → alarm.

### P2 — structural (manageability, drift-proof)
8. **IaC adoption:** `cdk import` the 54 Lambdas + tables + queues + rules (zero-replacement diff gate);
   move deploys to `ampx pipeline-deploy` with PR review. (Consolidate tables first — see AWS_CONSOLIDATION_AUDIT.md.)
9. **Drift detection:** schedule `_verify_ddb_ttl.py`-style checks (TTL, table names, config) + AWS Config rules.
10. **Verify DynamoDB billing = PAY_PER_REQUEST** on all tables (throttle-free under spikes).

### Sequencing
P0 (this week) → P1 (safe-deploy + auto-heal) → P2 (with the table consolidation, then IaC).
P0 items are all additive CloudWatch/SNS config — **no risk to running services**. P1/P2 change the
deploy path and should go through a maintenance window.

## What is genuinely low-risk to automate vs must stay gated
- **Low-risk / automate freely:** alarms, notifications, dashboards, canaries, DLQ auto-redrive, PITR, log retention, drift checks.
- **Gated (needs review/window):** Lambda alias+CodeDeploy cutover, `cdk import` adoption, table consolidation/migration, any table deletion.
