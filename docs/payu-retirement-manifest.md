# PayU retirement manifest — final

Backlog item 8, with the evidence item 12 requires: exact ARN/ID, readers and
writers, backups, checksums, observation period, recovery-window expiry and final
absence proof.

**Status: RETIRED. Razorpay is the only payment gateway.**

Closed 2026-09-26 against account `775261844268` / `us-east-1`. Every absence
claim below is a measurement, not an assumption — regenerate with
`python scripts/aws_account_inventory.py`.

## Recovery window — expired

| Field | Value |
|---|---|
| Secret | `wecare/payu` |
| `DeleteSecret` called | 2026-08-26 10:10:20Z |
| `recoveryWindowInDays` | 30 |
| `forceDeleteWithoutRecovery` | not used |
| Permanent deletion | **2026-09-25 10:10:20Z** |
| Verified absent | 2026-09-26, `ListSecrets` with `IncludePlannedDeletion=True` returns 31 secrets, **zero** matching `payu` |

Source: CloudTrail `DeleteSecret` lookup over a 60-day window. The window expired
one day before this manifest was written, so the secret is unrecoverable. This is
why the claim is "permanently gone" rather than "scheduled for deletion" — the
five Airtel and Sinch-SMS secrets are still in the second state until 2026-10-20.

**No backup was taken, deliberately.** A retired gateway's credentials are not
disaster-recovery material; retaining them would keep a live-credential liability
for a provider that must never be re-enabled. The value was never read during any
part of this retirement.

## AWS surface — absence measured, not assumed

| Resource | Expected | Measured 2026-09-26 |
|---|---|---|
| Lambda `wecare-payu-webhook` | gone | absent from all 65 functions |
| Route `/webhook/payu` | gone | absent from all 361 routes on `zllr9lrg7j` |
| Table `stack-wecare-digital-PayUWebhookLogTable` | gone | absent from all 79 tables |
| Secret `wecare/payu` | gone | absent (see above) |
| CloudFormation | no declaration | no stack declares it; `stack-wecare-digital-` is a name prefix, not a stack |

### Alarms deleted 2026-09-26

Two alarms outlived the Lambda they watched, and both read `OK` **because** their
target was absent — a metric for a nonexistent resource never reports.

| Alarm | Dimension | Metric | State when deleted |
|---|---|---|---|
| `wecare-lambda-errors-wecare-payu-webhook` | `FunctionName=wecare-payu-webhook` | `Errors` Sum > 3 | `OK` |
| `wecare-url-hit-wecare-payu-webhook` | `FunctionName=wecare-payu-webhook` | `UrlRequestCount` Sum > 0 | `OK` |

The second was a deliberate tripwire meant to catch anyone still calling the
retired webhook. It could not have fired. That is worse than having no tripwire,
because it answered "is anyone using PayU?" with a confident no.

Rollback export, definitions complete enough to recreate either alarm:

    .scratch/payu-alarms-before-20260926.json
    sha256  54f85f4e4269685acc72657606776c6e7ed428a5effd9ebd9af58667739d348a
    3632 bytes

### Environment variables removed 2026-09-26

`wecare-whatsapp-business-api` still carried `PAYU_MID` and `PAYU_UPI_ID` in its
deployed environment. **No code read them** — verified across the function
package and the whole repository: no `os.environ`/`getenv` reference to either
name exists, and `handler.py:3135` is a comment recording their removal from the
code on 2026-08-23. Dead configuration, not a live dependency.

| | before | after |
|---|---|---|
| env var count | 18 | 16 |
| version published | v41 | **v42**, alias moved |
| `CodeSha256` v41 vs v42 | `awFhkrrSlqI7ONyc…` | **identical** |

The identical code hash is the point: this was a configuration-only change, so
nothing about message handling moved. Exactly two keys were removed and none
added. A version was published and the `live` alias moved, per the deploy rule —
`$LATEST` does not reach production for a function with a `live` alias.

**The alias has since moved to v43**, published 2026-09-26 05:11Z by another
session's code deploy (`auto-publish by _snapstart_publish.py`, a different
`CodeSha256`). v43 carries 16 env keys and no PayU keys, so the removal survived
the concurrent deploy — environment variables are function-level state that each
new version snapshots, which is exactly why this change did not need to race the
code deploy.

**Rollback — not an alias move.** Reverting to v41 would also revert that
session's code. To restore only the two variables:

    aws lambda update-function-configuration \
      --function-name wecare-whatsapp-business-api \
      --environment '{"Variables":{ ...all 16 current keys..., \
        "PAYU_MID":"<value>","PAYU_UPI_ID":"<value>" }}'
    # then publish a version and move the live alias

The two values were not written to disk. That function's environment is known to
hold a real token, so dumping it would have recreated the original
credential-leak incident. They are recoverable from git history if ever needed,
which they should not be.

### Retained: one log group, self-expiring

    /aws/lambda/wecare-payu-webhook    8,084 bytes, 90-day retention
    last event 2026-07-17T08:38:41Z  ->  auto-expires ~2026-10-15

Not deleted. These are payment-gateway logs, so discarding them early is a worse
default than letting retention do it, and it removes itself in under three weeks
without any action. **Observation period:** the function has had no invocation
since 2026-07-17, 71 days before closure.

## Recreation paths — checked and closed

This is the part item 8 asks for, and the answer is that only one candidate was
real and it was not what it looked like.

| Candidate | Verdict |
|---|---|
| `config/lambda-env-manifest.json` listing `PAYU_MID`/`PAYU_UPI_ID` | **Not a recreation path.** `scripts/env_manifest.py` never deploys — it records live state so drift shows in a diff. The manifest is a mirror, so the order is remove-from-AWS-then-re-export, never the reverse. Re-exported after the change; `env_manifest.py` reports `IN SYNC`, 0 differences across 65 functions. |
| `amplify/functions/payments/payu-webhook/` | Directory does not exist. The tree holds three payment functions: `invoice-engine`, `payments-read`, `razorpay-webhook`. |
| IaC declaring the table or function | None. `amplify/backend.ts:74` and `amplify/data/resource.ts:1006` are tombstone comments recording the removal. |
| `scripts/deploy_all_lambdas.py` function map | No PayU entry. |
| Dashboard UI offering PayU as active | Removed, see below. |

## Source changes

### Removed — presented PayU as live

| File | What went |
|---|---|
| `src/pages/dashboard/index.tsx` | The whole **PayU Webhook section**, 290 lines: live OAuth and payment-link endpoints (`accounts.payu.in`, `oneapi.payu.in`, plus a UAT token URL), the webhook URL, the Lambda name and a `merchantId: YOUR_PAYU_MID` request template. Also the `PayUWebhookLogTable` entry, the `payu_webhook_log` data source and its two id lists, and two phone descriptions reading "Razorpay + PayU + UPI". |
| `src/pages/dashboard/lambda-functions.tsx` | `wecare-payu-webhook` listed with `status: 'active'`. |
| `src/pages/dashboard/system-architecture.tsx` | `PayUWebhookLog` table row, `payu-webhook` function row, a second `status: 'active'` entry, the `l-payu` repo entry, five `PAYU_*  (hardcoded)` risk-register rows for files that no longer exist, and the `PayU UPI VPA (hardcoded)` row. Corrected counts: payment functions 4 → 3, `amplify/functions/payments/` "4 dirs" → "3 dirs". |
| `src/pages/dashboard/code-repo.tsx` | `lambda-payu`, pointing at a handler path that does not exist. |
| `src/components/dashboard/tabs/InfraTab.tsx` | The `wecare-payu-webhook` function record, the `PayUWebhookLogTable` record, and `wecare-payu-webhook` from the `usedBy` lists of `PaymentsTable` and `InvoicesTable`. |

Every one of these was an operator-facing claim that a deleted resource was live.
These files are **authorised technical surfaces** under
`scripts/check_ui_labels.py`, so naming infrastructure there is allowed by policy
— which is precisely why the gate passed while the content was wrong. The defect
was accuracy, not labelling.

### Corrected — stale enumerations

- `src/api/client.ts:4795` — `preferredGateway` doc comment no longer offers
  `'payu'` as a value.
- `amplify/data/resource.ts:1017` — `// whatsapp, razorpay, payu` → `// whatsapp, razorpay`.
- `amplify/functions/shared/lambda_utils/webhook_dedup.py:5` — docstring no
  longer lists PayU as a webhook consumer.

### Retained deliberately

Four categories of PayU mention remain, and each is load-bearing. Deleting them
would make recreation *more* likely, not less:

1. **Guards.** `scripts/check_provider_policy_live.py` has
   `RETIRED = ("payu", "airtel", "elevenlabs")`, and
   `scripts/check_ui_labels.py:118` flags `\b(Airtel|PayU|Pinpoint)\b` in
   ordinary UI as `high`. These are the enforcement; removing the name disables
   the check.
2. **The sanctioned historical label.** `src/lib/productVocabulary.ts` exports
   `historicalProvider.payu = 'PayU (historical)'`. Its own comment explains it
   is "the only place a retired provider name is correct in ordinary UI" and that
   "the marker is required — the CI gate keys on it".
3. **Tombstones.** Dated comments in `amplify/backend.ts`,
   `amplify/data/resource.ts`, `outbound-whatsapp/handler.py`,
   `whatsapp-business-api/handler.py`, `system-cleanup/handler.py`,
   `src/pages/pay/flow/index.tsx`, and the replacement comment left in
   `dashboard/index.tsx`. Each says what was removed, when, and why.
4. **Remediation history.** The `R2`, `R3b`, `R4`, `R21`, `I1`, `I2` records in
   `system-architecture.tsx`. These document past credential exposures and their
   fixes; erasing them erases the security record.

`docs/`, `.kiro/steering/` and `bw-crm.md` also retain PayU references as
history and are out of scope for a code cleanup.

## Verification

| Check | Result |
|---|---|
| `pytest -q` | **3498 passed** |
| `npx tsc --noEmit` | clean — also proves the 290-line JSX removal is balanced |
| `npm run build` | succeeded, 642-URL sitemap generated |
| `scripts/check_provider_policy_live.py` | exit 0 — 361 routes across 4 pages, no untracked violations |
| `scripts/check_ui_labels.py` | exit 0 — 231 ordinary UI files, 15 authorised surfaces skipped |
| `scripts/env_manifest.py` | `IN SYNC`, 0 differences, 65 functions / 361 variables |
| live alias re-read after a concurrent deploy | v43, 16 env keys, **no PayU keys** |
| `scripts/aws_account_inventory.py` | 0 collector errors; no PayU Lambda, route, table or secret |

Pre-existing `react/no-unescaped-entities` lint errors remain in
`dashboard/index.tsx` and `system-architecture.tsx` on lines not touched here
(853, 1247, 2055, 2834). They are unrelated to this change and belong to backlog
item 184.

## Rollback

Only two changes are reversible, and neither should be reversed:

    # env vars — re-add via update-function-configuration, then publish and move
    # the alias. Do NOT roll the alias back to v41: another session's code deploy
    # landed at v43 and v41 predates it.

    # alarms, from the checksummed export above
    aws cloudwatch put-metric-alarm --cli-input-json \
      file://.scratch/payu-alarms-before-20260926.json   # one object at a time

    # source
    git revert <commit>

The secret cannot be restored: its recovery window expired 2026-09-25. Re-enabling
PayU would require new credentials from the provider and a new Meta payment
configuration on a WABA, which is prohibited by
`.kiro/steering/01-standing-authorization.md`.
