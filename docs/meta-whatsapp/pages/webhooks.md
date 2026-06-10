# Build Spec — Webhooks

Meta refs: /webhooks/overview, /webhooks/reference/messages

## Architecture (this repo)
Meta → **AWS End User Messaging (Social/WhatsApp)** → SNS topic → `wecare-inbound-whatsapp`.
- GET verify (`hub.challenge`/`hub.verify_token`) and X-Hub-Signature-256 validation are handled by the AWS-managed integration. No custom public webhook endpoint is exposed for verification.

## Handled webhook fields (inbound handler)
messages, statuses, message_template_status_update, phone_number_quality_update, account_update, user_id_update (BSUID), business_username_update, user_preferences, group_* events.

## Resilience
dedup, timeout-guard (re-queues remaining messages to DLQ), per-message try/except, DLQ `stack-wecare-digital-inbound-dlq`.

## Status
Built/present. Idempotency: PARTIAL_FIXED (add explicit message-id dedup table if duplicates seen). Live re-test pending QA inbound.
