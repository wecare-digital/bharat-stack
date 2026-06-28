# Security & Secrets

## Secrets storage
- Meta credentials live in AWS Secrets Manager at `wecare/meta-system-user-token`
  (`access_token`, `app_secret`, and optional `*_waba2` variants).
- Lambdas load secrets at runtime and cache in memory; secrets are **never** placed
  in code, env vars, or logs.
- IAM: only functions in the `whatsapp` / `secrets` policy groups
  (`amplify/iam-policies.ts`) can read `wecare/*`.

## appsecret_proof
Every Meta Graph call includes `appsecret_proof = HMAC_SHA256(access_token, app_secret)`.
The proof and token are masked in logs (`lambda_utils/masking.py`).

## Webhook signature verification
- Inbound webhooks validate `X-Hub-Signature-256` against the app secret before
  processing (`_verify_webhook_signature`).
- Fails closed when a signature is present and wrong; configurable fail-open only
  when no secret is configured (dev).

## Masking (logs + UI)
`lambda_utils/masking.py` redacts on the way to logs:
- **Full redaction:** authorization, access_token, app_secret, verify_token,
  `encrypted_flow_data`, `encrypted_aes_key`, `initial_vector`, private keys, passwords.
- **Partial mask:** phone numbers, WA IDs, payment references.
- UI mirrors this: `MaskedPhone`, `MaskedWaId`, `SecretField` (reveal is opt-in /
  admin-only). Tokens and app secrets are never rendered in full.

## Flow Data Exchange encryption
WhatsApp Flows endpoints receive `encrypted_flow_data` + `encrypted_aes_key` +
`initial_vector`. The handler RSA-decrypts the AES key with the configured private
key, then AES-GCM decrypts the payload. Decrypted PII is never logged — only masked
metadata. See `WHATSAPP_FLOWS_IMPLEMENTATION.md`.

## SSRF protection
Link-preview / URL fetch paths validate scheme/host and avoid following redirects to
internal addresses.

## Secret rotation (summary — see RUNBOOK.md)
- Rotate Meta token / app secret / webhook verify token in Secrets Manager; caches
  clear on next cold start (or redeploy to force).
- All write/rotation actions are audited (`lambda_utils/audit.py`) and may raise a
  `SystemEvent` (e.g. `token_rotation_reminder`).

## SystemEvents (security-relevant)
`webhook_signature_failure`, `meta_api_failure_spike`, `token_rotation_reminder`,
`flow_health_blocked` are recorded to the SystemEvent table for the Alerts UI.
