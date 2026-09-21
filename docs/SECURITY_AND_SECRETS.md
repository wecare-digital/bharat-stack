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
- Inbound webhooks validate `X-Hub-Signature-256` over the **raw** body, before any
  JSON parsing, against either WABA app secret. One implementation:
  `lambda_utils/meta_signature`.
- **Fails closed in every case**, including when no secret is configured. Corrected
  2026-09-21: this section previously described a "configurable fail-open only when
  no secret is configured (dev)", and `whatsapp-business-api` did exactly that. A
  verifier that trusts everything the moment its key is missing inverts its own
  purpose — an unreadable secret or a renamed field silently disables verification
  in production instead of making noise. There is no fail-open path and no switch
  to enable one.
- Replay window: 300s, judged per timestamp. Absent is allowed (Meta omits it on
  some event shapes); unreadable and far-future are rejected.

## Authentication exemptions (`AUTH_SKIP_PATHS`)
- Exactly one function sets it: `wecare-whatsapp-business-api`, value
  `/wa-business/flow-data`. That endpoint self-authenticates by RSA decryption.
- An endpoint qualifies only if it **proves** caller authenticity by itself — RSA
  decryption, or an HMAC signature the handler verifies. Sounding like a callback is
  not sufficient. `/wa-business/webhooks` was exempt until 2026-09-21 on the stated
  grounds that it "authenticates via verify token"; it is the management surface for
  Meta's `subscribed_apps` API and nothing authenticated it.
- Matching is exact-or-child-segment (`lambda_utils.middleware.path_is_exempt`), not
  substring. The function also serves `ANY /wa-business/{proxy+}`, so a substring
  test let `/wa-business/webhooks-anything` inherit the exemption.
- Verified live by `scripts/verify_public_webhook_auth.py --gate`.

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
