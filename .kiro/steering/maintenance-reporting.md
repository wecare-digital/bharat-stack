---
inclusion: always
---

# Maintenance reporting, confirmation and status tracking

Operative rules for any maintenance, upgrade or deployment run in this workspace.
Adopted 2026-09-19 (master-prompt sections 81-104).

## Status vocabulary

Every tracked task carries exactly one:

`✅ COMPLETE` · `🟡 IN PROGRESS` · `⏳ PENDING` · `⚠️ NEEDS CONFIRMATION` ·
`❌ FAILED` · `⛔ BLOCKED` · `➖ NOT REQUIRED`

**COMPLETE means the intended result was verified.** A command exiting 0 is not
evidence of success. If it could not be verified, it is not COMPLETE.

Track at minimum: Homebrew, core CLI, Node, Python, Go, Rust, Java, .NET,
PostgreSQL, FFmpeg, Docker, AWS CLI, SAM, CDK, Terraform, kubectl, Helm, Office,
Kiro, KiroCrew, Autopilot, Kiro permissions, AWS auth, Secrets Manager,
credential rotation, local + S3 encrypted backup, git secret scan, dependency
updates, lint, typecheck, tests, build, local function audit, Lambda migration,
commits, push, Lambda deployment, versions, aliases, smoke tests, CloudWatch,
CI/CD, git optimisation, disk cleanup, final verification.

## Required sections

Every checkpoint reports: **COMPLETED · IN PROGRESS · PENDING · FAILED/BLOCKED ·
GAPS FOUND · IMPROVEMENTS REQUIRED · CONFIRMATIONS**.

- **COMPLETED** — task, status, what changed, verification, files changed, AWS
  resources changed, commit, result.
- **PENDING** — task, reason, dependency, can-continue-automatically, confirmation
  required, next action. Distinguish: waiting on an automated step vs a user
  confirmation vs MFA/browser auth vs an error vs Kiro/macOS security.
- **GAPS** — gap, severity, impact, current state, desired state, recommended
  improvement, automatic fix possible, confirmation needed. Severity is one of
  `CRITICAL HIGH MEDIUM LOW INFORMATIONAL`. **Do not exaggerate severity.**
- **IMPROVEMENTS** — kept separate from failures. An improvement works today but
  could be better. Priority `P0` security/production critical, `P1` important,
  `P2` worthwhile, `P3` optional.
- **BEFORE / AFTER / CHANGE** wherever measurable. **Never invent a before value**
  — use snapshot data or state that it was not measured.

## Confirmation queue

Routine safe work stays automatic. When confirmation is needed, never bundle
unrelated risky actions into one vague question. Use a numbered queue, each with:
why, exact effect, resource affected, local files affected, git effect, rollback,
risk, recommended choice. Accept `YES 1`, `YES 1,2,4`, `NO 3`, `SKIP 5`,
`YES ALL SAFE ITEMS`. Never require the user to retype commands.

**Requires pointwise confirmation:** Mac password changes · unexpected sudo ·
rotating or revoking a live production credential · IAM create/delete/widen ·
account-level security · KMS create/delete · deleting a secret, bucket, Lambda,
database, queue or topic · destructive Terraform/CloudFormation/CDK · force push ·
history rewrite · deleting unique user files · deleting Docker volumes · shifting
production traffic on uncertain smoke tests.

**Does not require confirmation:** `brew update`, dependency install, lint, tests,
build, safe commit, normal push to an authorised branch, `sam build`, `cdk synth`,
`terraform plan`, AWS read operations, status reports, safe cache cleanup.

Before production deployment, show one **PRODUCTION DEPLOYMENT CHECKPOINT**
(account, region, role, branch, commit, functions to deploy / unchanged / blocked,
secrets status, tests, build, infra diff, destructive changes, rollback version,
estimated downtime) and ask once. **Do not invent prior approval.**

Before revoking each old credential, show a **CREDENTIAL ROTATION CHECKPOINT** per
provider (new credential stored / tested / app updated / Lambda updated / backup
updated / old still active) and ask per provider. Never display either value.

## Reports

Generate with `python scripts/maintenance_report.py` (add `--s3` to sync).

Local: `~/.local/share/kiro-maintenance-reports/<project>/<timestamp>/` holding
`maintenance-report.txt` and `maintenance-report.json`, plus a refreshed
`LATEST-maintenance-report.*` pointer. **Historical reports are never
overwritten** — each run gets its own timestamped directory.

S3: `s3://<bucket>/maintenance-reports/<project>/<timestamp>/` with **SSE-KMS**,
never public. If AWS auth is unavailable, keep the local report current and set
`AWS report synchronization: PENDING`, then upload once auth returns.

**Reports may contain:** account id, region, role ARN, function names/ARNs/versions,
deployment status, secret names and ARNs, rotation *status*, commit hashes, SDK
versions, test results, resource names, timestamps, and error messages carrying no
secrets.

**Reports must never contain:** passwords, tokens, API keys, secret access keys,
private keys, session tokens, or raw Secrets Manager values. The generator
enforces this — it refuses to write when credential-shaped material is detected.

## Final output

Close with: what is complete · pending · failed · blocked · all gaps · all
improvements · every AWS change · every git change · every Lambda deployed · every
rotation status · local report confirmation · S3 report confirmation · and only the
remaining pointwise confirmations. Then the completion matrix (System, Homebrew,
SDKs, Kiro, Security, Secrets, AWS Auth, Lambda, Git, CI/CD, Office, Disk).

Final result is exactly one of:

`✅ COMPLETE — ALL REQUIRED WORK VERIFIED` ·
`⚠️ COMPLETE WITH IMPROVEMENTS` · `⚠️ WAITING FOR CONFIRMATION` ·
`⚠️ PARTIAL` · `❌ BLOCKED`

**Never say "everything is complete" while the matrix holds an important pending or
failed item.** Do not hide unfinished work because the main deployment succeeded.

After an approval, continue automatically from that point and do not re-ask about
identical scope. Record confirmation id, decision, timestamp, action, result —
never a secret value.
