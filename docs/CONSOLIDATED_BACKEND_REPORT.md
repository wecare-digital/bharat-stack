# Consolidated Backend Report — WECARE.DIGITAL

Single source of truth for the backend: inventory, gaps, IaC, resilience, consolidation, and a phased
roadmap. Consolidates: BACKEND_FULL_AUDIT, AWS_CONSOLIDATION_AUDIT, RESILIENCE_BLUEPRINT,
LAMBDA_IAC_IMPORT_PLAN, UPGRADE_TO_LATEST. Account `775261844268` · `us-east-1` · **Amplify Gen 2**.

---
## 1. Inventory
| Resource | Count | Notes |
|---|--:|---|
| Lambda functions | 54 | `python3.12`; **deployed outside IaC** via `scripts/_deploy_everything.py` |
| DynamoDB tables | ~61 | TTL now on 19; PITR on key tables; heavy consolidation potential |
| SQS queues | 4 | bulk-queue + 3 DLQs (redrive OK) |
| EventBridge rules | 3 | media-cleanup daily, scheduled-msgs 5-min, AWS health |
| Cognito pools | 1 | `WECARE.DIGITAL` |
| Secrets | 11 | `wecare/*`, all used, no secrets in code |
| S3 buckets | 2 | `app.wecare.digital` + CDK assets |
| API Gateway | HTTP APIs | wa-business / service / url-shortener |

## 2. IaC status (the core structural theme)
- **In IaC (Amplify Gen2 / CDK):** auth (Cognito ref), data (DynamoDB via AppSync), storage (S3), SQS,
  CloudWatch alarms + dashboard, log retention, WAF (cost-gated), push infra, URL-shortener — in
  `amplify/backend.ts` + `backend-resources.ts`. Deploys via `ampx pipeline-deploy`.
- **NOT in IaC:** the **54 Python Lambdas** (shipped by a boto3 script). This is the #1 structural gap:
  no rollback, no PR gate, no drift detection. Plan in §6 / `LAMBDA_IAC_IMPORT_PLAN.md`.
- **Deploy split-brain:** frontend/data via Amplify CI; Lambdas via manual script. Unify under `ampx`.

## 3. Correctness risks (verify first)
**Table naming drift** — code/docs reference names that don't match live tables:
`FAQTable`→`FaqTable`, `AuditLog(Table)`→`AuditLogsTable` (confirmed in `service_api.py`),
`RateLimitTracker`→`RateLimitTable` (backend.ts bug already removed), `OBDCampaignTable`→`OBDCampaigns`,
`AdAttributionTable`→`AdClickAttributionTable`. A wrong env-var default = **silent write failures**.
→ Phase 1 grep verifies each handler's `os.environ.get(...,default)` vs live table.

## 4. Resilience (what exists vs gaps)
**Exists:** DLQs + `dlq-replay`; account-wide + per-Lambda error/throttle alarms; DLQ-depth + stuck-queue
alarms; dashboard; 90-day log retention; **DynamoDB PITR (35-day restore)**; **TTL fixed (19 tables)**;
**email alert to `one@wecare.digital` confirmed**.
**Gaps:** no **DynamoDB** alarms (throttle/system/user); no **API GW** 5xx/latency alarms; **EventBridge**
targets have **no DLQ / FailedInvocations alarm**; no **Lambda versions/aliases** (no instant rollback);
no **auto-remediation** (DLQ drain is manual); Cognito hardening (Advanced Security/MFA/deletion-protection) unverified.
**De-scoped by owner:** S3 versioning, KMS rotation.

## 5. Consolidation (61 → ~35–40 tables)
- Unify per-channel message/log tables into the already-partial `Messages` timeline.
- Merge caches (`CatalogCache`, `WixOrdersCache`, `WixProductsCache`, `WixOrderIds`) → 1 or drop.
- Merge `Razorpay/PayUWebhookLog` → `PaymentWebhookLog` (provider attr).
- **Do NOT delete "empty" tables** — they have active writers (low-traffic, not dead).
- Lambda count is fine; do not over-merge (clean IAM boundaries).

## 6. Phased roadmap (autopilot-safe vs gated)
### Phase 1 — READ-ONLY / ADDITIVE (autopilot-safe)
1a. Verify naming drift (grep env defaults vs live tables).
1b. Verify all tables = PAY_PER_REQUEST.
1c. Add alarms in `backend-resources.ts`: DynamoDB throttle/system/user, API GW 5xx/latency, Amplify build-failed, EventBridge FailedInvocations + target DLQ.
1d. Cognito posture check (read-only).

### Phase 2 — GATED (window)
2a. Fix naming-drift bugs → deploy affected functions.
2b. Lambda versions + `live` alias + CodeDeploy canary auto-rollback.
2c. Auto-remediation (alarm → EventBridge → auto-redrive DLQ).
2d. Cognito hardening.

### Phase 3 — STRUCTURAL (gated, largest)
3a. DynamoDB consolidation (§5) — schema refactor + handler changes (data-loss acceptable eases migration).
3b. **Lambda → IaC via `cdk import`** (zero-replacement `cdk diff` gate) + `ampx pipeline-deploy` + PR review.

### Dependencies (done)
Deps at latest, vulns 82→46, `fast-xml-parser` fixed. Detail in `UPGRADE_TO_LATEST.md`.

## 7. Autopilot guidance
- **Autopilot OK:** Phase 1 (read-only + additive IaC), scheduled drift checks (`_verify_ddb_ttl.py`, `_check_resilience.py`).
- **Supervised + confirm:** Phase 2 & 3 (deploys, alias cutover, table consolidation, `cdk import`) — can delete data / replace live functions.

## 8. Recommended order
Phase 1 (this week) → Phase 2a naming fixes → Phase 2b/2c self-healing → Phase 3a consolidation → Phase 3b Lambda IaC last (highest blast radius).
