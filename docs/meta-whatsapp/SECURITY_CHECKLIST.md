# WhatsApp Security Checklist

| Control | Status | Notes |
|---------|--------|-------|
| Webhook GET verify | ✅ ours, fails closed | `whatsapp-calling/_verify_webhook` compares `hub.verify_token` with `hmac.compare_digest` and returns 403 when no token is available. **Not AWS-managed** — this row claimed it was until 2026-09-21; there is no linked WABA and no SNS ingress |
| Webhook X-Hub signature | ✅ ours, fails closed | `whatsapp-calling/_verify_webhook_signature` checks raw-body HMAC-SHA256 against both WABA app secrets and returns 401 on mismatch. `POST /whatsapp/inbound` enforces the same since 2026-09-21; before that it accepted unsigned webhooks, partly because this checklist said signature checking was somebody else's job |
| Status webhook ordering | ✅ | `lambda_utils/wa_status` ranks the lifecycle and the DynamoDB write is guarded by a ConditionExpression, so a late `sent` cannot overwrite `read` |
| Webhook replay window | ✅ | Entries older than 300s rejected; note the timestamp parser fails **open** on a malformed timestamp |
| `appsecret_proof` on Graph calls | ✅ | Computed HMAC-SHA256(token, app_secret) in outbound/inbound handlers |
| Secrets in Secrets Manager (not code) | ✅ | `wecare/meta-system-user-token`, `wecare/meta-app-secret`, `wecare/flow-private-key` |
| Secret values never logged | ✅ | Handlers log message ids/types, not tokens |
| Admin API auth | ✅ (app-layer) | `require_auth` (Cognito JWT + role) enforced in handlers; `api.wecare.digital` returns 401 without token |
| API Gateway authorizer | ⚠️ REVIEW | HTTP API routes are `Auth: NONE` at gateway; auth is enforced in-handler via `require_auth`. Consider a gateway JWT authorizer for defense-in-depth |
| CORS | ⚠️ REVIEW | Gateway `AllowOrigins: *`; handlers echo specific origin. Tighten gateway to known origins |
| Idempotency / dup webhooks | ⚠️ PARTIAL | dedup + DLQ + timeout-guard present; add explicit message-id dedup table if duplicates observed |
| Flow payload encryption | ✅ | RSA private key in `wecare/flow-private-key` |
| Media objects private | ✅ (assumed) | `app.wecare.digital` under `stack/whatsapp-media/`; presigned URLs for read. Confirm public-access-block |
| Live-send gating | ✅ | `WA_LIVE_SMOKE_TEST` + `WA_QA_RECIPIENT` required before any test send |

## Action items
1. Add Cognito JWT authorizer to non-webhook HTTP API routes (defense in depth).
2. Restrict gateway CORS from `*` to app origins.
3. Confirm S3 `public-access-block` + lifecycle on `app.wecare.digital`.
