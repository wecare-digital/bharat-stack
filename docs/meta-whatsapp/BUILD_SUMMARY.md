# Build Summary — This Session

## Built / changed (verified by typecheck + live invoke where noted)

### 1. Template list returns full data (root-cause fix) — DEPLOYED + VERIFIED
- `amplify/functions/messaging/whatsapp-templates/handler.py` `_list_templates`
- Now returns `id, name, status, category, language, components` (+ legacy aliases). Previously only `metaTemplateId/templateName/templateStatus` → frontend got `components: []` (blank preview) and wrong `en_US` language (send rejected).
- **Verified live** via direct Lambda invoke: response now includes `components` and `language: "en"` for `wecare_pdf`, `wd_order`, etc.

### 2. Template media headers (image/video/document) — DEPLOYED
- `amplify/functions/messaging/outbound-whatsapp/handler.py`
- Accepts `headerMedia` (public link OR S3 key), `headerType`, `headerFilename`; resolves S3 key → WhatsApp media id via `_upload_media`; injects the header component first (Meta order). Threaded through `handler → _handle_live_send → _build_message_payload`.
- `src/components/TemplateSender.tsx` detects a media header and shows an Upload (image/video/document) + URL control; blocks send until provided.

### 3. Send template to a NEW / unsaved number — FRONTEND (this session)
- `src/components/TemplateSender.tsx` — `enableManualRecipient` mode: phone-number input, validation (>=10 digits incl. country code), passes `recipientPhone`.
- `src/pages/dm/whatsapp/inbox.tsx` — "✉️ New template message" button in the contacts sidebar (visible with no contact selected) opens the sender in manual mode.
- Backend already supports this: `_get_or_create_contact_by_phone` auto-creates the contact; message then appears in the inbox.

### 4. Env + docs
- `.env.local.example` — added the full WhatsApp/Meta variable + feature-flag block.
- `docs/meta-whatsapp/*` — this doc set.

## Deploy status
- **Backend Lambdas** (`wecare-whatsapp-templates`, `wecare-outbound-whatsapp`): deployed via `scripts/deploy_all.ps1` mechanism (`update-function-code`) — LastModified 2026-06-10, verified.
- **Frontend** (`TemplateSender`, `inbox`): deploys via Amplify on push to `stack` branch.

## Not done (honest)
- Full recursive crawl of every nested Meta docs page into `pages/` — only a representative subset created.
- Live send/flow/payment/media smoke tests — blocked, no `WA_QA_RECIPIENT`.
- Per-Lambda IAM least-privilege tightening — documented, not changed.
