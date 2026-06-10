# Build Spec — Templates

Meta refs: /templates/overview, /templates/components, /templates/guides/template-categorization, /cloud-api/reference/messages

## Contract (verified live against WABA 1)
- List: `GET /{WABA_ID}/message_templates?fields=name,status,category,language,components,id`
- Send: `POST /{PHONE_ID}/messages` type=template with `language.code`, ordered components `header → body → button`.
- Media header at SEND time requires a header parameter (`link` or media `id`); the approval-time `example.header_handle` is NOT reusable.

## Repo mapping
- Backend list/CRUD: `whatsapp-templates/handler.py`.
- Send builder: `outbound-whatsapp/handler.py` `_build_message_payload` (body, OTP/auth button, payment order_details, media header).
- Frontend: `TemplateSender.tsx` (list, vars, media-header upload, manual recipient), `templates.tsx` (admin CRUD).

## Status
- List/preview/language: IMPROVED_AND_TESTED (live invoke confirms `components`+`language`).
- Media-header send + new-number send: BUILT (this session); live send pending QA.
