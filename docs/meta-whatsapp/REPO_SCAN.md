# Repo Scan — WhatsApp Surface

## Deployed Lambdas (WhatsApp-relevant, of 51 `wecare-*`)
- `wecare-inbound-whatsapp` — SNS-triggered inbound processing (`messaging/inbound-whatsapp-handler/handler.py` + `modules/`)
- `wecare-outbound-whatsapp` — all outbound sends (text/media/template/interactive/reaction/typing)
- `wecare-whatsapp-templates` — template list/create/update/delete vs Graph API
- `wecare-whatsapp-template-management` — advanced template ops
- `wecare-whatsapp-business-api` — flows, profile, groups, orders, faq, reviews, appointments (`/wa-business/*`) + `flows/` + `service_api.py`
- `wecare-whatsapp-calling` — calling (`WhatsAppCallingTable`)
- `wecare-whatsapp-voice` — TTS voice notes (Polly)
- `wecare-waba-management` — WABA/media/tags/conversational-components
- `wecare-media-cleanup` — daily S3 media cleanup (EventBridge `rate(1 day)`)
- `wecare-template-analytics` — template send/delivery tracking

## API routes (HTTP API `wecare-digital-api`, all in-handler auth)
Webhook/public: `POST /whatsapp/inbound`, `GET|POST /wa-business/webhooks`, `POST /wa-business/flow-data`
Admin (require_auth): `GET|POST /whatsapp/send`, `/whatsapp/templates*`, `/waba/media`, `/wa-business/flows*`, `/wa-business/profile`, `/wa-business/groups*`, etc.

## DynamoDB (WhatsApp)
`WhatsAppInboundTable` (PITR on), `WhatsAppOutboundTable` (PITR on), `WhatsAppCallingTable` (PITR off), `WhatsAppGroupTable`, `WhatsAppVoiceTable`, `FlowRegistryTable` (PITR on), `FlowSubmissionTable` (PITR on), `FlowLogTable` (TTL on), `MediaFilesTable` (PITR on), `TemplateAnalyticsTable`, `SystemConfigTable`, `CatalogCacheTable`.

## Secrets Manager
`wecare/meta-system-user-token`, `wecare/meta-app-secret`, `wecare/flow-private-key` (all present; token + flow key accessed today).

## SQS
`stack-wecare-digital-inbound-dlq`, `-outbound-dlq`, `-bulk-queue`, `-bulk-dlq`.

## Frontend (Next.js)
`src/pages/dm/whatsapp/` — `inbox.tsx`, `templates.tsx`, `campaign.tsx`, `flows.tsx`, `flow-hub.tsx`, `flow-responses.tsx`, `groups.tsx`, `calling.tsx`, `interactive-lists.tsx`, `business-profile.tsx`, `waba-dashboard.tsx`, `webhooks.tsx`.
Components: `TemplateSender.tsx`, `InteractiveMessageComposer.tsx`, `RichTextEditor.tsx`.
API client: `src/api/client.ts` (`listTemplates`, `sendWhatsAppTemplateMessage`, `sendWhatsAppMessage`, `uploadMediaForSend`, `sendTypingIndicator`, flows/groups helpers).

## Deploy reality
- Frontend → Amplify app `d22dm4b0jn71jw`, branch `stack` (build spec `amplify.yml`, frontend only).
- Lambdas → `scripts/deploy_all.ps1` (`aws lambda update-function-code`). NOT auto-deployed by Amplify. `backend.ts` documents this explicitly.
