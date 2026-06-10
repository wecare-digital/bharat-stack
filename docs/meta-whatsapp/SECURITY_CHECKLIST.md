# WhatsApp Security Checklist

| Control | Status | Notes |
|---------|--------|-------|
| Webhook GET verify | ✅ AWS-managed | AWS End User Messaging validates `hub.verify_token` before SNS publish |
| Webhook X-Hub signature | ✅ AWS-managed | Inbound arrives via SNS from the managed integration, not a public POST |
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
