# Best-Practices & Gaps Audit

Read-only scan of all 55 functions + APIs (`scripts/_best_practice_audit.py`), plus fixes.

## Findings & status

| Area | Finding | Status |
|---|---|---|
| API Gateway throttling | **None** on either HTTP API | ✅ **Fixed** — 100 rps / 200 burst (generous; only caps abuse/runaway) |
| Log retention | 7 Lambda log groups kept logs **forever** | ✅ **Fixed** — set to 90 days |
| X-Ray tracing | 0/55 functions traced | ⏸️ Recommended (needs `xray:PutTraceSegments` on each role) |
| Reserved concurrency | 0/55 functions | ⏸️ Recommended for payment/critical fns (needs capacity planning — reserving reduces the shared pool) |
| Function async DLQ | 0/55 `DeadLetterConfig` | ℹ️ Mostly N/A — API-Gateway fns are synchronous; event-driven flows already use **SQS DLQs** (alarmed) + EventBridge DLQ |

## Fixed this pass (`scripts/_fix_bestpractice_gaps.py`)
- **API Gateway throttling** on `wecare-api/prod` and `wecare-digital-api/prod`: 100 rps rate,
  200 burst. Well above real usage (admin UI + low-volume webhooks); protects the backend and
  caps cost on a traffic spike or abuse. Reversible.
- **Log retention = 90 days** on 7 groups (automation-rules, conversation-meta, payu-webhook,
  rcs-dlr, rcs-send, sinch-dlr, url-shortener). Stops unbounded CloudWatch storage cost.

## Recommended (needs care / a decision — not applied blind)
- **X-Ray tracing** — enable `TracingConfig=Active` + add `xray:PutTraceSegments` to each
  execution role. Big observability win for a 55-Lambda system; do as a batched, tested change.
- **Reserved concurrency** — reserve a slice for `razorpay-webhook`, `payu-webhook`,
  `inbound-whatsapp-handler` so a spike elsewhere can't starve them; cap `bulk-worker` /
  `ai-generate-response` so they can't exhaust the account pool. Needs a peak-usage review first.
- **Secrets** — some webhook secrets live in Lambda **env vars** (e.g. `RAZORPAY_WEBHOOK_SECRET`,
  `PAYU_MERCHANT_SALT`); Secrets Manager (already used for Meta tokens) is the better pattern.
- **datetime.utcnow()** deprecation across handlers — dedicated tested PR (see completion report).
