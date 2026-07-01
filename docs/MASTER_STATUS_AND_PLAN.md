# WECARE.DIGITAL — Master Status & Plan (final report)

Consolidated report of the audit/upgrade work. Single source of truth. Excludes (per owner):
**S3 versioning** and **KMS key rotation** — deliberately NOT needed.

---
## 1. Platform snapshot
- **Amplify Gen 2** (not Gen 1) — `defineBackend`, `ampx`, `amplify_outputs.json`.
- **Frontend:** Next.js 16.2.x, static export (`output: export`), deployed via Amplify Hosting (app `d22dm4b0jn71jw`, branch `stack`). Builds #490–#496 green.
- **Backend:** ~61 DynamoDB tables, 54 Python Lambdas (`python3.12`), 4 SQS queues, 1 Cognito pool, 3 EventBridge rules, 11 secrets, 2 S3 buckets, HTTP API Gateways.
- **Lambdas deploy OUTSIDE IaC** via `scripts/_deploy_everything.py` (the main structural gap).

## 2. DONE & shipped this cycle
| Area | Outcome |
|---|---|
| WhatsApp usernames | Live username shown on both consoles; send-by-BSUID for username-adopters; delete buttons removed; config synced (`wecare.digital`, `manishagarwal`). Deployed. |
| Dependencies | All bumped to latest via GH Actions clean-regen; committed lock; **vulns 82 → 46** (high-sev cut ~66%). 2 residual criticals are bundled aws-cdk build-time deps (unreachable by overrides). Deployed. |
| Critical vuln | `fast-xml-parser` override `5.3.4` (pinned-vulnerable) → `5.9.3`. Live. |
| DynamoDB TTL | Was silently OFF on 19 tables (backend.ts override failed). **Enabled on 17 tables (1→19); 0 rows purged** (all future-dated). Dangerous `RateLimitTracker→lastUpdatedAt` mapping removed from `backend.ts`. |
| Recovery | Confirmed **DynamoDB PITR ENABLED** on all key tables (35-day restore). |
| Alerts | `one@wecare.digital` subscribed to alarm SNS (**pending email confirmation**). |
| Hygiene | `next-env.d.ts` untracked+gitignored; `turbopack.root` pinned; merged branch deleted. |
| Docs | Consolidation audit, resilience blueprint, Lambda IaC plan, frontend duplication audit — all in `docs/`. |

## 3. Outstanding work (prioritized; S3 versioning & KMS rotation excluded)

### P0 — additive, no risk to live traffic
1. **Confirm the SNS email** (click link in `one@wecare.digital`) — alerts are dead until then.
2. **DynamoDB alarms** — `ThrottledRequests`, `SystemErrors`, `UserErrors` on critical tables.
3. **API Gateway alarms** — 5xx + p99 latency per HTTP API.
4. **Amplify build-failure alarm** — EventBridge (job FAILED) → SNS.
5. **EventBridge target DLQ + `FailedInvocations` alarm** — stop silent scheduler misses.
   > Best practice: add these in `amplify/backend-resources.ts` (IaC), deploy via `ampx pipeline-deploy`. Avoid console-created alarms (drift).

### P1 — safe deploys + self-healing (maintenance window)
6. **Lambda versions + `live` alias + CodeDeploy canary w/ auto-rollback** on error alarm.
7. **Auto-remediation Lambda** — alarm → EventBridge → auto-redrive DLQ / restart stuck queue.
8. **Synthetics canary** — webhook health + admin login every 5 min.
9. **Cognito hardening** — Advanced Security + MFA policy + deletion protection + scheduled user export (DR).

### P2 — structural (the three big initiatives)
10. **DynamoDB consolidation** (~61 → ~35–40): unify per-channel message/log tables into the already-partial
    `Messages` timeline; merge caches, payment webhook logs, invoice sub-tables. NOTE: "empty" tables are NOT
    dead (they have writers) — reduce via schema refactor, never by dropping empty tables.
11. **Frontend de-duplication** (~120 → ~70–80 pages): retire per-channel inbox/campaign/logs in favor of the
    unified `dm/*` pages; merge SEO page variants; remove dead/demo pages.
12. **Lambda → IaC** (`cdk import`, zero-replacement diff gate) + `ampx pipeline-deploy` with PR review;
    fixes drift, rollback, review-gate for the 54 functions.

## 4. Recommended sequence
1. **P0 this week** (all additive, in IaC). Confirm email first.
2. **Frontend de-dup** next — lowest risk of the big three, immediate maintainability win (`dm/*` already supersedes the per-channel pages). Start with inbox/logs/campaign trio.
3. **DynamoDB consolidation** — needs schema decision + handler refactor; data-loss acceptable eases migration.
4. **Lambda IaC + safe-deploy (P1)** last — highest blast radius; do in a window once tables are consolidated.

## 5. Explicitly de-scoped (owner decision)
- S3 versioning — not needed.
- KMS key rotation — not needed.

## Reference docs
`AWS_CONSOLIDATION_AUDIT.md` · `RESILIENCE_BLUEPRINT.md` · `LAMBDA_IAC_IMPORT_PLAN.md` ·
`FRONTEND_DUPLICATION_AUDIT.md` · `UPGRADE_TO_LATEST.md`. Helper scripts in `scripts/`:
`_verify_ddb_ttl.py`, `_fix_ddb_ttl.py`, `_check_resilience.py`, `_check_oba_status.py`, `_audit_aws_runtimes.py`, `_deep_aws_audit.py`.
