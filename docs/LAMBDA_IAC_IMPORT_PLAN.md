# Lambda → IaC Import Plan (54 Python functions)

**Status:** PLAN ONLY — do not execute the import/deploy steps until reviewed and a maintenance
window is scheduled. Getting this wrong can **replace or delete live messaging Lambdas**.

## Problem
`backend.ts` states: *"Lambda functions (42+ Python functions) are deployed separately and already
exist in AWS. They are not managed by Amplify Gen 2."* They ship via `scripts/_deploy_everything.py`
(`boto3 update_function_code`). Consequences: no IaC, no PR gate, no atomic rollback, drift risk,
split-brain with the Amplify-managed frontend/data/auth/storage.

## Why this is high-risk
- The 54 functions already exist with fixed physical names (`wecare-*`). If CDK creates functions
  with the same names → **CREATE fails** (name conflict). If CDK is told to manage them but logical
  IDs / properties don't match exactly → a deploy can **replace (delete+recreate)** them, dropping
  event source mappings, permissions, env vars, and causing messaging downtime.
- Many have wiring not visible in the handler dirs: API Gateway integrations, EventBridge rules,
  SQS event source mappings, DynamoDB streams, SNS, IAM roles, reserved concurrency, layers.

## Options (recommended order)

### Option A — Adopt via `cdk import` (no recreate) — RECOMMENDED
Bring existing functions under CDK control **without** recreating them.
1. In `backend.ts`, define each function with a custom CDK construct whose properties EXACTLY match
   the live function (runtime `python3.12`, handler, memory, timeout, env, role ARN, architecture).
   Use `aws lambda get-function` to capture the exact current config first (script below).
2. Run `ampx sandbox` or a CDK app in **import** mode (`cdk import`) so CloudFormation adopts the
   existing physical resources by name instead of creating them.
3. Verify the CDK diff is **empty** (no replacements) before any `pipeline-deploy`.
4. Migrate one low-risk function first (e.g., `wecare-media-cleanup`), confirm, then batch the rest.

### Option B — Keep script deploy, add guardrails (fastest, lowest risk)
If full IaC is deferred, harden the current script:
- Tag every function on deploy (`git-sha`, `deployed-at`) for traceability/rollback.
- Store the previous version + publish a Lambda version/alias so rollback = alias flip.
- Add a `--dry-run` and a post-deploy smoke test to `_deploy_everything.py`.

### Option C — Rewrite as Amplify `defineFunction` — NOT recommended now
Gen2 `defineFunction` targets Node/TS; these are Python with bespoke wiring. High churn, low payoff.

## Pre-work: capture live config (safe, read-only)
Run this to snapshot every function's exact configuration before writing any CDK:
```
aws lambda list-functions --query "Functions[?starts_with(FunctionName,'wecare-')].FunctionName" --output text \
 | tr '\t' '\n' | while read f; do aws lambda get-function-configuration --function-name "$f" > "iac_snapshot/$f.json"; done
```
Also capture: event source mappings (`aws lambda list-event-source-mappings`), API GW integrations,
EventBridge rules/targets, and each function's IAM role policy — these must be represented in CDK too.

## Gate before deploy
- `cdk diff` shows **zero replacements/deletions** for all `wecare-*` functions.
- Do it in a maintenance window with the current `_deploy_everything.py` ready as rollback.
- Migrate incrementally (1 → few → rest), verifying webhooks/messaging after each batch.

## Decision needed
Confirm **Option A** (full adopt-via-import) or **Option B** (guardrails only). On your go, next step is
the read-only config snapshot (above) — still no changes to live infra.
