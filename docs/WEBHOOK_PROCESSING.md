# Webhook Processing

How inbound Meta webhooks and Flow data-exchange requests are handled.

## 1. Verification (GET)
Meta sends `hub.mode=subscribe&hub.verify_token=...&hub.challenge=...`. The handler
compares the verify token and echoes `hub.challenge` on success.

## 2. Signature validation (POST)
`X-Hub-Signature-256` is verified as `sha256=HMAC_SHA256(rawBody, app_secret)` before
any parsing. Mismatch → reject; a `webhook_signature_failure` SystemEvent is recorded.

## 3. Raw body handling
The **raw** request body (pre-JSON-parse) is used for signature verification.
Base64-encoded bodies (`isBase64Encoded`) are decoded first. Do not re-serialize
before verifying.

## 4. Deduplication
Webhook delivery is at-least-once. A dedupe key (message/event id) is checked against
the `WebhookDedup` table (idempotency helper) so repeated deliveries are ignored.

## 5. Fast 200 ACK
The endpoint acknowledges quickly (200) to avoid Meta retries/backoff, then does
heavier work asynchronously.

## 6. Async / DLQ
Slow work (enrichment, downstream sends) is queued to SQS; failures land in a DLQ.
See `ENABLE_RAW_WEBHOOK_ARCHIVE` for optional raw payload archival.

## 7. Replay
Failed events can be replayed from the DLQ (see RUNBOOK "replay webhook event").
Replays are audited.

## 8. Masking
All logging passes through `mask_secrets`. Phone numbers/WA IDs partially masked;
tokens, encryption material, and decrypted PII fully redacted.

## 9. Pricing category `general_purpose_ai`
Non-template AI-provider messages carry `pricing.category = general_purpose_ai`.
These are captured for analytics/billing (AI Provider Pricing Events) and may raise a
`general_purpose_ai_pricing_seen` SystemEvent. Applies only to AI-provider traffic.

## 10. Flow Data Exchange vs ordinary webhook
A Flow data-exchange POST is **not** an ordinary webhook:
- Body is encrypted (`encrypted_flow_data` / `encrypted_aes_key` / `initial_vector`).
- It must be RSA+AES decrypted, routed by `action`/`screen`/`flow_token`, and answered
  with an **encrypted** response.
- It is handled by the Flows endpoint, not the message webhook path. Never log the
  encrypted payload or decrypted PII — only masked metadata + `FlowLog`.
