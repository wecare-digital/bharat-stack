# AWS End User Messaging Social — Production Reference Implementation

**Date**: 2026-02-11
**Architecture**: WhatsApp ↔ AWS EUM Social ↔ SNS → Lambda → DynamoDB
**Constraints**: NO SAM / NO CloudFormation / NO CDK / NO Amazon Connect / NO direct Meta Graph API
**Language**: Python 3.12 + boto3 (socialmessaging client)
**Region**: us-east-1 | Account: 775261844268

---

## Table of Contents

1. [Checklists (A/B/C)](#1-checklists)
2. [Mapping Tables (A/B) + Event Crosswalk (C)](#2-mapping-tables)
3. [Architecture](#3-architecture)
4. [Resource List & Naming](#4-resource-list)
5. [Provisioning Scripts (AWS CLI)](#5-provisioning)
6. [Application Code](#6-application-code)
7. [Event Destination Setup](#7-event-destination-setup)
8. [Testing & Replay Tool](#8-testing)
9. [Operational Runbooks](#9-runbooks)

---

## 1. Checklists

### Checklist A — AWS Track Completeness (Implementation Checklist)

All items sourced from crawled AWS EUM Social User Guide + API Reference (21 API operations).

#### A1. Onboarding / Linking WABA + Phone Numbers

| # | Step | API / Console | Status | Notes |
|---|------|--------------|--------|-------|
| 1 | Create or link WABA via AWS console | `AssociateWhatsAppBusinessAccount` (POST /v1/whatsapp/signup) | ✅ DONE | Console-only signup flow; uses `signupCallback` or `setupFinalization` |
| 2 | Complete Meta Embedded Signup | Console redirect to Meta | ✅ DONE | 2 WABAs linked |
| 3 | Register phone numbers with 2FA PIN | Part of `setupFinalization.phoneNumbers[].twoFactorPin` | ✅ DONE | 2 phone numbers registered |
| 4 | Verify WABA registration status = COMPLETE | `GetLinkedWhatsAppBusinessAccount` | ✅ DONE | Both WABAs COMPLETE |
| 5 | Confirm enableSending = true | `GetLinkedWhatsAppBusinessAccount` response | ✅ DONE | Both enabled |
| 6 | Confirm enableReceiving = true | `GetLinkedWhatsAppBusinessAccount` response | ✅ DONE | Both enabled |

#### A2. Listing / Getting WABAs and Phone Numbers

| # | Operation | API | Status | Implementation |
|---|-----------|-----|--------|----------------|
| 1 | List all linked WABAs | `ListLinkedWhatsAppBusinessAccounts` (GET /v1/whatsapp/waba/list) | ✅ | `wecare-waba-management` Lambda |
| 2 | Get WABA details | `GetLinkedWhatsAppBusinessAccount` (GET /v1/whatsapp/waba/details?id=) | ✅ | `wecare-waba-management` Lambda |
| 3 | Get phone number details | `GetLinkedWhatsAppBusinessAccountPhoneNumber` (GET /v1/whatsapp/waba/phone/details?id=) | ✅ | `wecare-waba-management` Lambda |

#### A3. Event Destination Configuration

| # | Operation | API | Status | Implementation |
|---|-----------|-----|--------|----------------|
| 1 | Configure SNS event destination | `PutWhatsAppBusinessAccountEventDestinations` (PUT /v1/whatsapp/waba/eventdestinations) | ✅ | Both WABAs → SNS topic `base-wecare-digital` |
| 2 | SNS topic policy allows `social-messaging.amazonaws.com` publish | SNS topic policy | ✅ | Policy configured |
| 3 | IAM role for event destination | `roleArn` in event destination config | ✅ | Service-linked role |

#### A4. Sending Messages (All Supported Types)

| # | Type | API | Status | Implementation |
|---|------|-----|--------|----------------|
| 1 | Text messages | `SendWhatsAppMessage` (POST /v1/whatsapp/send) | ✅ | `wecare-outbound-whatsapp` |
| 2 | Template messages | `SendWhatsAppMessage` with template payload | ✅ | `wecare-outbound-whatsapp` |
| 3 | Media messages (image/video/audio/document/sticker) | `PostWhatsAppMessageMedia` + `SendWhatsAppMessage` | ✅ | Upload to S3 → PostMedia → Send |
| 4 | Interactive messages (buttons, lists, CTA URL) | `SendWhatsAppMessage` with interactive payload | ✅ | `wecare-outbound-whatsapp` |
| 5 | Location messages | `SendWhatsAppMessage` with location payload | ✅ | Supported via message blob |
| 6 | Reaction messages | `SendWhatsAppMessage` with reaction payload | ✅ | `wecare-outbound-whatsapp` |
| 7 | Read receipts | `SendWhatsAppMessage` with status=read payload | ✅ | `wecare-inbound-whatsapp` auto-sends |
| 8 | Payment order_details | `SendWhatsAppMessage` with interactive order_details | ✅ | Razorpay UPI integration |
| 9 | Payment order_status | `SendWhatsAppMessage` with interactive order_status | ✅ | Payment confirmation flow |
| 10 | WhatsApp Flows | `SendWhatsAppMessage` with flow payload | ✅ | Supported via message blob |

#### A5. Receiving Inbound Messages + Statuses/Events

| # | Event Type | Delivery Path | Status | Implementation |
|---|-----------|--------------|--------|----------------|
| 1 | Inbound text/media/location/contacts/reaction/interactive/button/order/system messages | SNS → Lambda | ✅ | 18 message types handled |
| 2 | Delivery statuses (sent/delivered/read/failed) | SNS → Lambda | ✅ | DynamoDB status updates |
| 3 | Payment statuses (pending/captured/failed) | SNS → Lambda | ✅ | Auto-sends order_status reply |
| 4 | Template status updates (approved/rejected/paused) | SNS → Lambda | ✅ | Logged to CloudWatch |
| 5 | Phone number quality updates | SNS → Lambda | ✅ | Logged to CloudWatch |
| 6 | Account updates (messaging limits) | SNS → Lambda | ✅ | Logged to CloudWatch |

#### A6. Templates + Template Media Flows

| # | Operation | IAM Action | Status | Notes |
|---|-----------|-----------|--------|-------|
| 1 | Create template | `social-messaging:CreateMessageTemplate` | ✅ IAM granted | Via console or SDK |
| 2 | Get template | `social-messaging:GetMessageTemplate` | ✅ IAM granted | |
| 3 | Delete template | `social-messaging:DeleteMessageTemplate` | ✅ IAM granted | |
| 4 | List templates | `social-messaging:ListMessageTemplates` | ✅ IAM granted | |
| 5 | Update template | `social-messaging:UpdateMessageTemplate` | ✅ IAM granted | |
| 6 | Submit template for review | `social-messaging:SubmitMessageTemplateForReview` | ✅ IAM granted | |
| 7 | Get template preview | `social-messaging:GetMessageTemplatePreview` | ✅ IAM granted | |
| 8 | Template media upload | `PostWhatsAppMessageMedia` (S3 → WhatsApp) | ✅ | S3 source required |

#### A7. Media Operations

| # | Operation | API | Status | Implementation |
|---|-----------|-----|--------|----------------|
| 1 | Upload media | `PostWhatsAppMessageMedia` (POST /v1/whatsapp/media) | ✅ | S3 source → mediaId |
| 2 | Download media | `GetWhatsAppMessageMedia` (POST /v1/whatsapp/media/get) | ✅ | mediaId → S3 destination |
| 3 | Delete media | `DeleteWhatsAppMessageMedia` (DELETE /v1/whatsapp/media) | ✅ | Via WABA management Lambda |

#### A8. Cleanup / Disassociation

| # | Operation | API | Status | Notes |
|---|-----------|-----|--------|-------|
| 1 | Disassociate WABA | `DisassociateWhatsAppBusinessAccount` (DELETE /v1/whatsapp/waba/disassociate?id=) | ✅ Available | Not used in production |

#### A9. Tagging

| # | Operation | API | Status |
|---|-----------|-----|--------|
| 1 | Tag resource | `TagResource` (POST /v1/tags/tag-resource) | ✅ Available |
| 2 | Untag resource | `UntagResource` (DELETE /v1/tags/untag-resource) | ✅ Available |
| 3 | List tags | `ListTagsForResource` (GET /v1/tags/list) | ✅ Available |

#### A10. Required AWS Resources & Permissions

| # | Resource | Purpose | Status |
|---|----------|---------|--------|
| 1 | SNS Standard Topic | Event destination for WABA events | ✅ `base-wecare-digital` |
| 2 | SNS Topic Policy | Allow `social-messaging.amazonaws.com` to publish | ✅ Configured |
| 3 | Lambda (inbound) | Process SNS events | ✅ `wecare-inbound-whatsapp` |
| 4 | Lambda (outbound) | Send messages via EUM Social | ✅ `wecare-outbound-whatsapp` |
| 5 | Lambda (WABA mgmt) | WABA/phone/media/tag management | ✅ `wecare-waba-management` |
| 6 | IAM Role | Lambda execution + EUM Social + DynamoDB + S3 + SQS + CloudWatch | ✅ `wecare-digital-lambda-role` |
| 7 | DynamoDB Tables | Messages, contacts, media, config, idempotency | ✅ 22 tables |
| 8 | S3 Bucket | Media storage (inbound/outbound) | ✅ `app.wecare.digital` |
| 9 | SQS DLQ | Failed message retry | ✅ `base-wecare-digital-inbound-dlq` |
| 10 | CloudWatch Alarms | Error rate, DLQ depth | ✅ Configured |
| 11 | Secrets Manager | Meta tokens, API keys | ✅ 4 secrets |
| 12 | CloudWatch Log Groups | Lambda logs with retention | ✅ All Lambdas |


### Checklist B — WhatsApp Capability Checklist (Meta Docs-Derived)

Sourced from Meta developer documentation links 5–12. These define the full WhatsApp Business Platform capability set.

#### B1. Calling (Meta docs link 5, 6)

| # | Capability | Setup Requirements | Constraints | Event Types |
|---|-----------|-------------------|-------------|-------------|
| 1 | Inbound calls (user → business) | Enable calling in WABA settings; subscribe to `calls` webhook field | Requires WebRTC or SIP for media; HTTPS for signaling | `call_received`, `call_accepted`, `call_ended` |
| 2 | Outbound calls (business → user) | Request call permission first; user must grant permission | Permission-based; cannot cold-call | `call_permission_request`, `call_permission_granted` |
| 3 | Call signaling (SDP offer/answer) | WebRTC or SIP endpoint required | Real-time; latency-sensitive | SDP exchange via Graph API |
| 4 | Call recording | Not available via API | Meta policy restriction | N/A |

#### B2. Business Profile (Meta docs link 7)

| # | Capability | Setup Requirements | Constraints |
|---|-----------|-------------------|-------------|
| 1 | Get business profile | GET `/{PHONE}/whatsapp_business_profile` | Read-only fields: verified_name |
| 2 | Update business profile | POST `/{PHONE}/whatsapp_business_profile` | Fields: about, address, description, email, profile_picture_url, websites, vertical |
| 3 | Profile picture upload | Upload via media endpoint, set URL | Max 640x640, JPEG/PNG |

#### B3. Webhooks Event Model (Meta docs link 8)

| # | Event Category | Webhook Fields | Key Event Types |
|---|---------------|---------------|-----------------|
| 1 | Messages | `messages` | text, image, video, audio, document, sticker, location, contacts, reaction, interactive, button, order, system, unsupported, request_welcome, ephemeral |
| 2 | Statuses | `messages` | sent, delivered, read, failed |
| 3 | Payment statuses | `messages` | payment.pending, payment.captured, payment.failed |
| 4 | Template status | `message_template_status_update` | APPROVED, REJECTED, PAUSED, DISABLED |
| 5 | Phone quality | `phone_number_quality_update` | GREEN, YELLOW, RED, FLAGGED |
| 6 | Account updates | `account_update` | messaging_limit_change, restriction |
| 7 | Calls | `calls` | call_received, call_accepted, call_ended, call_permission_request |
| 8 | Security | `security` | code_verification_status |

#### B4. Groups (Meta docs link 9)

| # | Capability | Setup Requirements | Constraints |
|---|-----------|-------------------|-------------|
| 1 | Create group | POST `/{PHONE}/groups` | Business-initiated; max 1024 participants |
| 2 | Add/remove participants | POST `/{GROUP_ID}/participants` | Admin permissions required |
| 3 | Send group messages | POST `/{PHONE}/messages` with group context | Same message types as 1:1 |
| 4 | Group admin management | POST `/{GROUP_ID}/admins` | Promote/demote participants |
| 5 | Group settings | PATCH `/{GROUP_ID}` | Name, description, icon, permissions |
| 6 | Leave group | DELETE `/{GROUP_ID}/participants` | Business leaves group |

#### B5. Payments — India Track (Meta docs link 10)

| # | Capability | Setup Requirements | Constraints |
|---|-----------|-------------------|-------------|
| 1 | Send order_details (invoice) | Payment gateway integration (Razorpay/PayU/etc.) | India only; UPI required; MCC code needed |
| 2 | Receive payment status webhooks | Subscribe to payment status events | pending → captured/failed flow |
| 3 | Send order_status (confirmation) | After payment captured/failed | Must reference original order reference_id |
| 4 | UPI Intent flow | Generate UPI intent link from payment gateway | tr value from UPI payment intent |
| 5 | Payment configuration | Register payment config with Meta | WABA-level config; requires business verification |

#### B6. Interactive List Messages (Meta docs link 11)

| # | Capability | Constraints |
|---|-----------|-------------|
| 1 | List messages | Max 10 sections, max 10 rows per section |
| 2 | Section headers | Optional; max 24 chars |
| 3 | Row titles | Required; max 24 chars |
| 4 | Row descriptions | Optional; max 72 chars |
| 5 | Button text | Required; max 20 chars |
| 6 | Header (text only) | Optional; max 60 chars |
| 7 | Body text | Required; max 1024 chars |
| 8 | Footer text | Optional; max 60 chars |

#### B7. WhatsApp Flows (Meta docs link 12)

| # | Capability | Setup Requirements | Constraints |
|---|-----------|-------------------|-------------|
| 1 | Create Flow | Flows API: POST `/{WABA_ID}/flows` | JSON-based screen definitions |
| 2 | Update Flow | Flows API: POST `/{FLOW_ID}/assets` | Upload JSON flow definition |
| 3 | Publish Flow | POST `/{FLOW_ID}/publish` | Must pass validation |
| 4 | Send Flow message | Interactive message type=flow | Within 24h window or via template |
| 5 | Receive Flow response | Webhook: interactive.nfm_reply.response_json | JSON response from completed flow |
| 6 | Flow categories | SIGN_UP, SIGN_IN, APPOINTMENT_BOOKING, LEAD_GENERATION, CONTACT_US, CUSTOMER_SUPPORT, SURVEY, OTHER | Category affects review process |
| 7 | Flow endpoints | Business-hosted HTTPS endpoint for dynamic data | Must respond within 10 seconds |

---

### Checklist C — Coverage & Gaps (AWS EUM Social-Only Feasibility)

| # | WhatsApp Capability (Meta) | Supported via AWS EUM Social? | AWS API/Console Flow | Gaps / Business Impact | AWS-Only Alternatives |
|---|---------------------------|------------------------------|---------------------|----------------------|----------------------|
| **C1** | **Text/Media/Template/Interactive messaging** | **YES** | `SendWhatsAppMessage` — message blob passes through WhatsApp Message object directly | None — full parity | N/A |
| **C2** | **Inbound message reception** | **YES** | SNS event destination → Lambda subscription | None — all 18 message types received | N/A |
| **C3** | **Delivery/read statuses** | **YES** | SNS event destination (same topic) | None | N/A |
| **C4** | **Media upload/download/delete** | **YES** | `PostWhatsAppMessageMedia`, `GetWhatsAppMessageMedia`, `DeleteWhatsAppMessageMedia` | None — S3 integration built-in | N/A |
| **C5** | **Template CRUD** | **YES** | 8 IAM actions: Create/Get/List/Delete/Update/Submit/Preview MessageTemplate | None — full CRUD via SDK | N/A |
| **C6** | **WABA management** | **YES** | Associate/Disassociate/Get/List WABA + GetPhoneNumber | None | N/A |
| **C7** | **Event destination config** | **YES** | `PutWhatsAppBusinessAccountEventDestinations` | SNS only (no SQS/EventBridge direct) | N/A |
| **C8** | **Tagging** | **YES** | Tag/Untag/ListTags | None | N/A |
| **C9** | **Payments (order_details/order_status)** | **YES** | Via `SendWhatsAppMessage` message blob — order_details and order_status are interactive message types | None — passes through as message payload | N/A |
| **C10** | **Interactive lists/buttons/CTA/flows** | **YES** | Via `SendWhatsAppMessage` message blob | None — all interactive types pass through | N/A |
| **C11** | **Reactions** | **YES** | Via `SendWhatsAppMessage` with reaction payload | None | N/A |
| **C12** | **Read receipts** | **YES** | Via `SendWhatsAppMessage` with status=read payload | None | N/A |
| **C13** | **WhatsApp Calling** | **NO** | Not available via AWS EUM Social API | **HIGH IMPACT**: No calling API operations in AWS EUM Social. Calling requires direct Meta Graph API integration with WebRTC/SIP signaling. | Existing workaround: Direct Meta Graph API webhook handler (`wecare-whatsapp-calling` Lambda) — this is outside the AWS EUM Social-only scope |
| **C14** | **Business Profile management** | **NO** | Not available via AWS EUM Social API | **LOW IMPACT**: Cannot programmatically get/update business profile (about, description, address, websites, profile picture). Must use Meta Business Suite console. | Use Meta Business Suite UI for profile updates |
| **C15** | **Groups** | **NO** | Not available via AWS EUM Social API | **MEDIUM IMPACT**: Cannot create/manage WhatsApp groups programmatically. No group messaging support. | No AWS-only alternative; requires direct Meta Graph API |
| **C16** | **Flows management (create/update/publish)** | **NO** | Not available via AWS EUM Social API | **LOW IMPACT**: Cannot create/manage Flows via AWS. However, sending Flow messages IS supported (via SendWhatsAppMessage). Flows must be created in Meta Business Suite or via direct Flows API. | Create Flows in Meta Business Suite; send via AWS EUM Social |
| **C17** | **Phone number register/deregister** | **PARTIAL** | Registration happens during `AssociateWhatsAppBusinessAccount` setup. No standalone register/deregister API. | **LOW IMPACT**: Cannot programmatically register new phone numbers post-setup | Use AWS console for phone number changes |
| **C18** | **Webhook signature verification** | **YES (automatic)** | AWS EUM Social handles Meta webhook verification internally; SNS messages are signed by AWS | None — more secure than direct Meta webhooks | N/A |
| **C19** | **Template status/quality/account webhooks** | **YES** | Delivered via same SNS event destination | None — all webhook fields forwarded | N/A |
| **C20** | **Payment configuration setup** | **NO** | Not available via AWS EUM Social API | **LOW IMPACT**: Payment config (MCC code, UPI setup) must be done in Meta Business Suite. Sending/receiving payment messages IS supported. | Configure payments in Meta Business Suite |

**Summary**: 15/20 capabilities fully supported, 1 partial, 4 not supported via AWS EUM Social-only.
The 4 gaps (Calling, Business Profile, Groups, Flows management) require direct Meta Graph API access if needed.


---

## 2. Mapping Tables

### Table A — AWS Mapping Table

| AWS Doc Concept / API Object | AWS Resource(s) | Code Module(s) | DynamoDB Item(s) | Notes / Constraints |
|------------------------------|-----------------|----------------|-------------------|---------------------|
| `SendWhatsAppMessage` | Lambda `wecare-outbound-whatsapp` + IAM `social-messaging:SendWhatsAppMessage` | `lambdas/outbound_sender/handler.py` → `_handle_live_send()` | WhatsAppOutboundTable: `{id, contactId, recipientPhone, content, messageType, status, whatsappMessageId, phoneNumberId, timestamp, expiresAt}` | Message blob is base64-encoded WhatsApp Message object; max 2MB; metaApiVersion required (v20.0) |
| `GetWhatsAppMessageMedia` | Lambda + S3 `app.wecare.digital` + IAM `social-messaging:GetWhatsAppMessageMedia` | `lambdas/inbound_handler/handler.py` → `_download_media()` | MediaFilesTable: `{fileId, messageId, s3Key, contentType, whatsappMediaId, fileSize}` | Requires either `destinationS3File` or `destinationS3PresignedUrl`; media stored at `whatsapp-media/whatsapp-media-incoming/{phone}/{date}/{mediaId}.{ext}` |
| `PostWhatsAppMessageMedia` | Lambda + S3 + IAM `social-messaging:PostWhatsAppMessageMedia` | `lambdas/outbound_sender/handler.py` → `_upload_media()` | MediaFilesTable (outbound record) | Requires either `sourceS3File` or `sourceS3PresignedUrl`; returns `mediaId` for use in SendWhatsAppMessage |
| `DeleteWhatsAppMessageMedia` | Lambda + IAM `social-messaging:DeleteWhatsAppMessageMedia` | `lambdas/waba_management/handler.py` → `_delete_media()` | — | Also delete from S3 separately if stored there |
| `AssociateWhatsAppBusinessAccount` | AWS Console (signup flow) | N/A (console-only) | — | Uses `setupFinalization` with WABA ID, phone numbers, 2FA PIN, event destinations; or `signupCallback` with access token |
| `DisassociateWhatsAppBusinessAccount` | AWS Console or CLI | `lambdas/waba_management/handler.py` (available) | — | Removes WABA link; does not delete Meta-side resources |
| `GetLinkedWhatsAppBusinessAccount` | Lambda + IAM | `lambdas/waba_management/handler.py` → `_get_waba_details()` | — (read-only) | Returns: arn, id, wabaId, wabaName, phoneNumbers[], eventDestinations[], registrationStatus, enableSending, enableReceiving, linkDate |
| `GetLinkedWhatsAppBusinessAccountPhoneNumber` | Lambda + IAM | `lambdas/waba_management/handler.py` → `_get_phone_number_details()` | — (read-only) | Returns: phoneNumberId, phoneNumber, displayPhoneNumber, displayPhoneNumberName, metaPhoneNumberId, qualityRating, dataLocalizationRegion |
| `ListLinkedWhatsAppBusinessAccounts` | Lambda + IAM | `lambdas/waba_management/handler.py` → `_list_wabas()` | — (read-only) | Paginated: maxResults (1-100), nextToken |
| `PutWhatsAppBusinessAccountEventDestinations` | SNS Topic + IAM Role + Lambda | `lambdas/waba_management/handler.py` → `_configure_event_destinations()` | — | Max 1 event destination per WABA; eventDestinationArn = SNS topic ARN; roleArn = IAM role for publishing |
| `TagResource` / `UntagResource` / `ListTagsForResource` | Lambda + IAM | `lambdas/waba_management/handler.py` | — | Tags on WABA or phone number ARNs |
| SNS Topic (event destination) | `arn:aws:sns:us-east-1:775261844268:base-wecare-digital` | SNS subscription → Lambda | — | Standard topic (not FIFO); topic policy must allow `social-messaging.amazonaws.com` to `sns:Publish` |
| SNS → Lambda subscription | Lambda trigger | `lambdas/inbound_handler/handler.py` | — | Raw message delivery; Lambda concurrency controls recommended |
| SQS DLQ | `base-wecare-digital-inbound-dlq` | `lambdas/dlq_replay/handler.py` | DLQMessagesTable (optional) | 7-day retention; manual or scheduled replay |
| CloudWatch Alarms | Lambda error rate + DLQ depth | `infra/cli-scripts/create-alarms.sh` | — | SNS notification on alarm |

### Table B — WhatsApp Capability Table (Meta → AWS Feasibility)

| WhatsApp Capability (Meta Docs) | Required Events/Data | AWS EUM Social Equivalent | Gaps | Notes |
|--------------------------------|---------------------|--------------------------|------|-------|
| Send text message | POST /{PHONE}/messages `{type:"text", text:{body:"..."}}` | `SendWhatsAppMessage` — message blob contains full WhatsApp Message object | None | Max 4096 chars |
| Send image/video/audio/document/sticker | POST /{PHONE}/messages with media object containing mediaId | `PostWhatsAppMessageMedia` (upload) + `SendWhatsAppMessage` (send) | None | S3 required for upload source |
| Send template message | POST /{PHONE}/messages `{type:"template", template:{name, language, components}}` | `SendWhatsAppMessage` — template payload in message blob | None | Template must be APPROVED by Meta |
| Send interactive (buttons/list/CTA/flow) | POST /{PHONE}/messages `{type:"interactive", interactive:{...}}` | `SendWhatsAppMessage` — interactive payload in message blob | None | All interactive types pass through |
| Send reaction | POST /{PHONE}/messages `{type:"reaction", reaction:{message_id, emoji}}` | `SendWhatsAppMessage` — reaction payload in message blob | None | Empty emoji = remove reaction |
| Send read receipt | POST /{PHONE}/messages `{messaging_product:"whatsapp", status:"read", message_id:"wamid.xxx"}` | `SendWhatsAppMessage` — status payload in message blob | None | |
| Send location | POST /{PHONE}/messages `{type:"location", location:{latitude, longitude, name, address}}` | `SendWhatsAppMessage` — location payload in message blob | None | |
| Send contacts | POST /{PHONE}/messages `{type:"contacts", contacts:[...]}` | `SendWhatsAppMessage` — contacts payload in message blob | None | |
| Send order_details (payment) | POST /{PHONE}/messages `{type:"interactive", interactive:{type:"order_details",...}}` | `SendWhatsAppMessage` — order_details in message blob | None | India only; requires payment config |
| Send order_status | POST /{PHONE}/messages `{type:"interactive", interactive:{type:"order_status",...}}` | `SendWhatsAppMessage` — order_status in message blob | None | |
| Receive inbound messages | Webhook: `messages` field | SNS event destination → Lambda | None | AWS wraps Meta webhook in envelope |
| Receive delivery statuses | Webhook: `messages` field (statuses array) | SNS event destination → Lambda | None | sent/delivered/read/failed |
| Receive payment statuses | Webhook: `messages` field (statuses with type=payment) | SNS event destination → Lambda | None | pending/captured/failed |
| Template status updates | Webhook: `message_template_status_update` field | SNS event destination → Lambda | None | APPROVED/REJECTED/PAUSED/DISABLED |
| Phone quality updates | Webhook: `phone_number_quality_update` field | SNS event destination → Lambda | None | GREEN/YELLOW/RED/FLAGGED |
| Account updates | Webhook: `account_update` field | SNS event destination → Lambda | None | Messaging limit changes |
| Upload media | POST /{PHONE}/media | `PostWhatsAppMessageMedia` | None | S3 source required |
| Download media | GET /{MEDIA_ID} | `GetWhatsAppMessageMedia` | None | S3 destination required |
| Delete media | DELETE /{MEDIA_ID} | `DeleteWhatsAppMessageMedia` | None | |
| Template CRUD | POST/GET/DELETE /{WABA}/message_templates | 8 IAM actions for template management | None | Full CRUD via SDK |
| WhatsApp Calling | Webhook: `calls` field; POST /{PHONE}/calls | **NOT AVAILABLE** | Full gap | Requires direct Meta Graph API + WebRTC/SIP |
| Business Profile get/update | GET/POST /{PHONE}/whatsapp_business_profile | **NOT AVAILABLE** | Full gap | Use Meta Business Suite |
| Groups CRUD | POST /{PHONE}/groups, /{GROUP}/participants | **NOT AVAILABLE** | Full gap | Requires direct Meta Graph API |
| Flows management (create/publish) | POST /{WABA}/flows, /{FLOW}/publish | **NOT AVAILABLE** (sending flows IS supported) | Partial gap | Create in Meta Business Suite; send via AWS |
| Phone register/deregister | POST /{PHONE}/register, /deregister | **PARTIAL** — done during WABA association | Minor gap | Use AWS console |

### Table C — Event Crosswalk (Meta Webhook → AWS SNS → Internal Model)

| Meta Webhook Event Concept | Meta Payload Location | AWS SNS Event Payload | Normalized Internal Event Model |
|---------------------------|----------------------|----------------------|-------------------------------|
| **Inbound text message** | `entry[].changes[].value.messages[]{type:"text"}` | `{context:{MetaWabaIds,MetaPhoneNumberIds}, whatsAppWebhookEntry:"{...}", messageId, message_timestamp}` | `{eventType:"INBOUND_MESSAGE", messageType:"text", content:text.body, senderPhone, senderName, receivingPhone, awsPhoneNumberId, whatsappMessageId, wabaId, timestamp}` |
| **Inbound media message** | `entry[].changes[].value.messages[]{type:"image/video/audio/document/sticker"}` | Same envelope; media object in whatsAppWebhookEntry | `{eventType:"INBOUND_MESSAGE", messageType:"image", content:caption, mediaId, mimeType, s3Key, fileSize, senderPhone, ...}` |
| **Inbound location** | `entry[].changes[].value.messages[]{type:"location"}` | Same envelope | `{eventType:"INBOUND_MESSAGE", messageType:"location", content:"[Location: lat, lng]", latitude, longitude, locationName, locationAddress, ...}` |
| **Inbound contacts** | `entry[].changes[].value.messages[]{type:"contacts"}` | Same envelope | `{eventType:"INBOUND_MESSAGE", messageType:"contacts", content:"[Contact Card]", contactCards:[...], ...}` |
| **Inbound reaction** | `entry[].changes[].value.messages[]{type:"reaction"}` | Same envelope | `{eventType:"INBOUND_MESSAGE", messageType:"reaction", content:emoji, reactionMessageId, reactionEmoji, ...}` |
| **Inbound interactive reply** | `entry[].changes[].value.messages[]{type:"interactive"}` | Same envelope | `{eventType:"INBOUND_MESSAGE", messageType:"interactive", interactiveType:"button_reply/list_reply/nfm_reply", content:title/response_json, ...}` |
| **Inbound button (quick reply)** | `entry[].changes[].value.messages[]{type:"button"}` | Same envelope | `{eventType:"INBOUND_MESSAGE", messageType:"button", content:button.text, buttonPayload, ...}` |
| **Inbound order** | `entry[].changes[].value.messages[]{type:"order"}` | Same envelope | `{eventType:"INBOUND_MESSAGE", messageType:"order", content:"[Order]", orderData:{catalogId, productItems}, ...}` |
| **Inbound system** | `entry[].changes[].value.messages[]{type:"system"}` | Same envelope | `{eventType:"INBOUND_MESSAGE", messageType:"system", content:system.body, systemType, ...}` |
| **Delivery status: sent** | `entry[].changes[].value.statuses[]{status:"sent"}` | Same envelope | `{eventType:"STATUS_UPDATE", status:"sent", whatsappMessageId, recipientPhone, timestamp}` |
| **Delivery status: delivered** | `entry[].changes[].value.statuses[]{status:"delivered"}` | Same envelope | `{eventType:"STATUS_UPDATE", status:"delivered", whatsappMessageId, recipientPhone, timestamp}` |
| **Delivery status: read** | `entry[].changes[].value.statuses[]{status:"read"}` | Same envelope | `{eventType:"STATUS_UPDATE", status:"read", whatsappMessageId, recipientPhone, timestamp}` |
| **Delivery status: failed** | `entry[].changes[].value.statuses[]{status:"failed"}` | Same envelope; includes `errors[]` | `{eventType:"STATUS_UPDATE", status:"failed", whatsappMessageId, recipientPhone, errorCode, errorTitle, errorDetails, timestamp}` |
| **Payment status** | `entry[].changes[].value.statuses[]{type:"payment"}` | Same envelope | `{eventType:"PAYMENT_STATUS", paymentStatus:"pending/captured/failed", referenceId, amount, currency, ...}` |
| **Template status update** | `entry[].changes[]{field:"message_template_status_update"}` | Same envelope | `{eventType:"TEMPLATE_STATUS", templateName, templateId, newStatus:"APPROVED/REJECTED/PAUSED", reason, ...}` |
| **Phone quality update** | `entry[].changes[]{field:"phone_number_quality_update"}` | Same envelope | `{eventType:"PHONE_QUALITY", phoneNumberId, currentQuality:"GREEN/YELLOW/RED", ...}` |
| **Account update** | `entry[].changes[]{field:"account_update"}` | Same envelope | `{eventType:"ACCOUNT_UPDATE", updateType, banInfo, restrictionInfo, ...}` |


---

## 3. Architecture

### 3.1 Architecture Diagram (Mermaid)

```mermaid
graph TB
    subgraph "External"
        WA[WhatsApp Users]
        META[Meta Cloud API v20.0]
    end

    subgraph "AWS End User Messaging Social"
        EUM[AWS EUM Social Service]
    end

    subgraph "AWS Account 775261844268 — us-east-1"
        subgraph "Inbound Flow"
            SNS[SNS Topic<br/>base-wecare-digital]
            INB[Lambda: wecare-inbound-whatsapp<br/>Python 3.12 / 512MB / 60s]
            DLQ_SQS[SQS DLQ<br/>inbound-dlq]
            REPLAY[Lambda: wecare-dlq-replay]
        end

        subgraph "Outbound Flow"
            APIGW[API Gateway HTTP API<br/>api.wecare.digital]
            OUT[Lambda: wecare-outbound-whatsapp<br/>Python 3.12 / 256MB / 30s]
        end

        subgraph "WABA Management"
            WABA_MGT[Lambda: wecare-waba-management]
        end

        subgraph "Storage"
            DDB_IN[DynamoDB: WhatsAppInboundTable]
            DDB_OUT[DynamoDB: WhatsAppOutboundTable]
            DDB_CONTACTS[DynamoDB: ContactsTable]
            DDB_MEDIA[DynamoDB: MediaFilesTable]
            DDB_CONFIG[DynamoDB: SystemConfigTable]
            DDB_IDEMP[DynamoDB: IdempotencyTable<br/>TTL-based dedup]
            S3[S3: app.wecare.digital<br/>whatsapp-media/]
        end

        subgraph "Observability"
            CW[CloudWatch Logs + Metrics<br/>Namespace: WECARE.DIGITAL]
            ALARMS[CloudWatch Alarms<br/>Error Rate + DLQ Depth]
            ALARM_SNS[SNS Alarm Topic]
        end

        subgraph "Security"
            SM[Secrets Manager<br/>meta-whatsapp-token]
            IAM[IAM Role<br/>wecare-digital-lambda-role]
        end
    end

    WA <-->|Messages| META
    META <-->|Webhook + API| EUM
    EUM -->|Publish events| SNS
    EUM <--|SendWhatsAppMessage<br/>Get/Post/DeleteMedia| OUT
    EUM <--|WABA/Phone/Tag ops| WABA_MGT

    SNS -->|Subscription| INB
    SNS -->|On failure| DLQ_SQS
    DLQ_SQS -->|Replay| REPLAY
    REPLAY -->|Re-publish| SNS

    INB -->|Store messages| DDB_IN
    INB -->|Update contacts| DDB_CONTACTS
    INB -->|Download media| S3
    INB -->|Store media refs| DDB_MEDIA
    INB -->|Check dedup| DDB_IDEMP
    INB -->|Auto-react/read receipt| OUT
    INB -->|On error| DLQ_SQS

    APIGW -->|Route| OUT
    OUT -->|Store messages| DDB_OUT
    OUT -->|Upload media| S3
    OUT -->|Read contacts| DDB_CONTACTS
    OUT -->|Read config| DDB_CONFIG

    WABA_MGT -->|Read/write config| DDB_CONFIG

    INB -->|Logs + Metrics| CW
    OUT -->|Logs + Metrics| CW
    CW -->|Threshold breach| ALARMS
    ALARMS -->|Notify| ALARM_SNS

    OUT -->|Get secrets| SM
    INB -->|Assume role| IAM
    OUT -->|Assume role| IAM
```

### 3.2 Data Flow Summary

```
INBOUND:
  WhatsApp User → Meta → AWS EUM Social → SNS (base-wecare-digital)
    → Lambda (wecare-inbound-whatsapp)
      → Parse SNS envelope → Extract whatsAppWebhookEntry
      → Normalize event (messages/statuses/template/quality/account)
      → Dedup check (whatsappMessageId)
      → Store in DynamoDB (WhatsAppInboundTable)
      → Download media to S3 (if applicable)
      → Update contact (ContactsTable)
      → Auto-react + read receipt (invoke outbound Lambda)
      → AI automation (if enabled in SystemConfigTable)
    → On failure: SQS DLQ → manual/scheduled replay

OUTBOUND:
  API Gateway (api.wecare.digital) → Lambda (wecare-outbound-whatsapp)
    → Validate request (contact, phone, rate limit, content length)
    → Upload media to WhatsApp (PostWhatsAppMessageMedia) if needed
    → Build WhatsApp Message object (text/template/interactive/reaction/etc.)
    → Call SendWhatsAppMessage (AWS EUM Social)
    → Store in DynamoDB (WhatsAppOutboundTable)
    → Emit CloudWatch metric
    → Return messageId to caller
```

---

## 4. Resource List & Naming Conventions

| # | Resource Type | Name / Identifier | ARN Pattern | Purpose |
|---|--------------|-------------------|-------------|---------|
| 1 | SNS Topic (Standard) | `base-wecare-digital` | `arn:aws:sns:us-east-1:775261844268:base-wecare-digital` | WABA event destination |
| 2 | Lambda (Inbound) | `wecare-inbound-whatsapp` | `arn:aws:lambda:us-east-1:775261844268:function:wecare-inbound-whatsapp` | Process SNS events |
| 3 | Lambda (Outbound) | `wecare-outbound-whatsapp` | `arn:aws:lambda:us-east-1:775261844268:function:wecare-outbound-whatsapp` | Send messages |
| 4 | Lambda (WABA Mgmt) | `wecare-waba-management` | `arn:aws:lambda:us-east-1:775261844268:function:wecare-waba-management` | WABA/phone/media/tag ops |
| 5 | Lambda (DLQ Replay) | `wecare-dlq-replay` | `arn:aws:lambda:us-east-1:775261844268:function:wecare-dlq-replay` | Replay failed messages |
| 6 | IAM Role | `wecare-digital-lambda-role` | `arn:aws:iam::775261844268:role/wecare-digital-lambda-role` | Lambda execution role |
| 7 | DynamoDB | `base-wecare-digital-WhatsAppInboundTable` | PK: `id` (UUID), GSI: `whatsappMessageId-index` | Inbound messages |
| 8 | DynamoDB | `base-wecare-digital-WhatsAppOutboundTable` | PK: `id` (UUID) | Outbound messages |
| 9 | DynamoDB | `base-wecare-digital-ContactsTable` | PK: `id` (UUID), GSI: `phone-index` | Contacts |
| 10 | DynamoDB | `base-wecare-digital-MediaFilesTable` | PK: `fileId` (UUID) | Media file references |
| 11 | DynamoDB | `base-wecare-digital-SystemConfigTable` | PK: `configKey` | System configuration |
| 12 | DynamoDB | `base-wecare-digital-IdempotencyTable` | PK: `eventId`, TTL: `expiresAt` | Deduplication (30-day TTL) |
| 13 | S3 Bucket | `app.wecare.digital` | `arn:aws:s3:::app.wecare.digital` | Media storage |
| 14 | S3 Prefix (inbound) | `whatsapp-media/whatsapp-media-incoming/` | — | Inbound media files |
| 15 | S3 Prefix (outbound) | `whatsapp-media/whatsapp-media-outgoing/` | — | Outbound media files |
| 16 | SQS Queue (DLQ) | `base-wecare-digital-inbound-dlq` | `arn:aws:sqs:us-east-1:775261844268:base-wecare-digital-inbound-dlq` | Failed message retry |
| 17 | SQS Queue (Outbound DLQ) | `base-wecare-digital-outbound-dlq` | `arn:aws:sqs:us-east-1:775261844268:base-wecare-digital-outbound-dlq` | Outbound failures |
| 18 | Secrets Manager | `wecare/meta-system-user-token` | — | Meta access tokens (dual WABA) |
| 19 | CloudWatch Log Group | `/aws/lambda/wecare-inbound-whatsapp` | — | 30-day retention |
| 20 | CloudWatch Log Group | `/aws/lambda/wecare-outbound-whatsapp` | — | 30-day retention |
| 21 | CloudWatch Alarm | `wecare-lambda-error-rate` | — | Lambda error rate > 1% |
| 22 | CloudWatch Alarm | `wecare-dlq-depth` | — | DLQ depth > 10 messages |
| 23 | API Gateway HTTP API | `zllr9lrg7j` / `api.wecare.digital` | — | Outbound API endpoint |
| 24 | WABA 1 | `waba-e47d916f3c7a47e1a34a19653893dd4b` | — | WECARE.DIGITAL (+91 93309 94400) |
| 25 | WABA 2 | `waba-dbe343f210204752b74c80a0a59631a6` | — | Manish Agarwal (+91 99033 00044) |
| 26 | Phone Number 1 | `phone-number-id-5e020cecd221429996f6ae721cc42206` | — | +91 93309 94400 |
| 27 | Phone Number 2 | `phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c` | — | +91 99033 00044 |


---

## 5. Provisioning Scripts (AWS CLI — NO SAM/CloudFormation/CDK)

### 5.1 SNS Topic + Topic Policy

```bash
#!/bin/bash
# infra/cli-scripts/create-sns-topic.sh
set -euo pipefail

REGION="us-east-1"
ACCOUNT_ID="775261844268"
TOPIC_NAME="base-wecare-digital"
TOPIC_ARN="arn:aws:sns:${REGION}:${ACCOUNT_ID}:${TOPIC_NAME}"

# Create SNS standard topic (idempotent — returns existing ARN if exists)
aws sns create-topic \
  --name "${TOPIC_NAME}" \
  --region "${REGION}" \
  --output text --query 'TopicArn'

# Set topic policy to allow AWS EUM Social to publish
aws sns set-topic-attributes \
  --topic-arn "${TOPIC_ARN}" \
  --attribute-name Policy \
  --attribute-value '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "AllowEUMSocialPublish",
        "Effect": "Allow",
        "Principal": {
          "Service": "social-messaging.amazonaws.com"
        },
        "Action": "sns:Publish",
        "Resource": "'"${TOPIC_ARN}"'",
        "Condition": {
          "StringEquals": {
            "aws:SourceAccount": "'"${ACCOUNT_ID}"'"
          }
        }
      }
    ]
  }' \
  --region "${REGION}"

echo "SNS topic ${TOPIC_ARN} created with EUM Social publish policy"
```

### 5.2 DynamoDB Tables

```bash
#!/bin/bash
# infra/cli-scripts/create-dynamodb-tables.sh
set -euo pipefail

REGION="us-east-1"
PREFIX="base-wecare-digital"

# MessagesTable (Inbound) — PK: id, GSI: whatsappMessageId-index
aws dynamodb create-table \
  --table-name "${PREFIX}-WhatsAppInboundTable" \
  --attribute-definitions \
    AttributeName=id,AttributeType=S \
    AttributeName=whatsappMessageId,AttributeType=S \
    AttributeName=contactId,AttributeType=S \
    AttributeName=timestamp,AttributeType=N \
  --key-schema AttributeName=id,KeyType=HASH \
  --global-secondary-indexes \
    '[{"IndexName":"whatsappMessageId-index","KeySchema":[{"AttributeName":"whatsappMessageId","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"}},
      {"IndexName":"contactId-timestamp-index","KeySchema":[{"AttributeName":"contactId","KeyType":"HASH"},{"AttributeName":"timestamp","KeyType":"RANGE"}],"Projection":{"ProjectionType":"ALL"}}]' \
  --billing-mode PAY_PER_REQUEST \
  --region "${REGION}" 2>/dev/null || echo "Table already exists"

# MessagesTable (Outbound) — PK: id
aws dynamodb create-table \
  --table-name "${PREFIX}-WhatsAppOutboundTable" \
  --attribute-definitions \
    AttributeName=id,AttributeType=S \
    AttributeName=contactId,AttributeType=S \
    AttributeName=timestamp,AttributeType=N \
  --key-schema AttributeName=id,KeyType=HASH \
  --global-secondary-indexes \
    '[{"IndexName":"contactId-timestamp-index","KeySchema":[{"AttributeName":"contactId","KeyType":"HASH"},{"AttributeName":"timestamp","KeyType":"RANGE"}],"Projection":{"ProjectionType":"ALL"}}]' \
  --billing-mode PAY_PER_REQUEST \
  --region "${REGION}" 2>/dev/null || echo "Table already exists"

# ContactsTable — PK: id, GSI: phone-index
aws dynamodb create-table \
  --table-name "${PREFIX}-ContactsTable" \
  --attribute-definitions \
    AttributeName=id,AttributeType=S \
    AttributeName=phone,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --global-secondary-indexes \
    '[{"IndexName":"phone-index","KeySchema":[{"AttributeName":"phone","KeyType":"HASH"}],"Projection":{"ProjectionType":"ALL"}}]' \
  --billing-mode PAY_PER_REQUEST \
  --region "${REGION}" 2>/dev/null || echo "Table already exists"

# IdempotencyTable — PK: eventId, TTL on expiresAt
aws dynamodb create-table \
  --table-name "${PREFIX}-IdempotencyTable" \
  --attribute-definitions \
    AttributeName=eventId,AttributeType=S \
  --key-schema AttributeName=eventId,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "${REGION}" 2>/dev/null || echo "Table already exists"

aws dynamodb update-time-to-live \
  --table-name "${PREFIX}-IdempotencyTable" \
  --time-to-live-specification "Enabled=true,AttributeName=expiresAt" \
  --region "${REGION}" 2>/dev/null || echo "TTL already enabled"

# Enable TTL on message tables (expiresAt attribute)
aws dynamodb update-time-to-live \
  --table-name "${PREFIX}-WhatsAppInboundTable" \
  --time-to-live-specification "Enabled=true,AttributeName=expiresAt" \
  --region "${REGION}" 2>/dev/null || echo "TTL already enabled"

aws dynamodb update-time-to-live \
  --table-name "${PREFIX}-WhatsAppOutboundTable" \
  --time-to-live-specification "Enabled=true,AttributeName=expiresAt" \
  --region "${REGION}" 2>/dev/null || echo "TTL already enabled"

# MediaFilesTable — PK: fileId
aws dynamodb create-table \
  --table-name "${PREFIX}-MediaFilesTable" \
  --attribute-definitions \
    AttributeName=fileId,AttributeType=S \
  --key-schema AttributeName=fileId,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "${REGION}" 2>/dev/null || echo "Table already exists"

# SystemConfigTable — PK: configKey
aws dynamodb create-table \
  --table-name "${PREFIX}-SystemConfigTable" \
  --attribute-definitions \
    AttributeName=configKey,AttributeType=S \
  --key-schema AttributeName=configKey,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "${REGION}" 2>/dev/null || echo "Table already exists"

echo "All DynamoDB tables created"
```

### 5.3 IAM Role + Policies (Least Privilege)

```bash
#!/bin/bash
# infra/cli-scripts/create-iam-role.sh
set -euo pipefail

REGION="us-east-1"
ACCOUNT_ID="775261844268"
ROLE_NAME="wecare-digital-lambda-role"

# Create Lambda execution role
aws iam create-role \
  --role-name "${ROLE_NAME}" \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }' 2>/dev/null || echo "Role already exists"

# Attach basic Lambda execution
aws iam attach-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"

# Create inline policy for EUM Social + DynamoDB + S3 + SQS + Secrets
aws iam put-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-name "wecare-digital-lambda-policy" \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "SocialMessagingFull",
        "Effect": "Allow",
        "Action": [
          "social-messaging:SendWhatsAppMessage",
          "social-messaging:GetWhatsAppMessageMedia",
          "social-messaging:PostWhatsAppMessageMedia",
          "social-messaging:DeleteWhatsAppMessageMedia",
          "social-messaging:GetLinkedWhatsAppBusinessAccount",
          "social-messaging:GetLinkedWhatsAppBusinessAccountPhoneNumber",
          "social-messaging:ListLinkedWhatsAppBusinessAccounts",
          "social-messaging:PutWhatsAppBusinessAccountEventDestinations",
          "social-messaging:AssociateWhatsAppBusinessAccount",
          "social-messaging:DisassociateWhatsAppBusinessAccount",
          "social-messaging:TagResource",
          "social-messaging:UntagResource",
          "social-messaging:ListTagsForResource",
          "social-messaging:CreateMessageTemplate",
          "social-messaging:GetMessageTemplate",
          "social-messaging:ListMessageTemplates",
          "social-messaging:DeleteMessageTemplate",
          "social-messaging:UpdateMessageTemplate",
          "social-messaging:SubmitMessageTemplateForReview",
          "social-messaging:GetMessageTemplatePreview",
          "social-messaging:GetWhatsAppBusinessAccountEventDestinations"
        ],
        "Resource": "*"
      },
      {
        "Sid": "DynamoDBAccess",
        "Effect": "Allow",
        "Action": [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem"
        ],
        "Resource": [
          "arn:aws:dynamodb:us-east-1:'"${ACCOUNT_ID}"':table/base-wecare-digital-*",
          "arn:aws:dynamodb:us-east-1:'"${ACCOUNT_ID}"':table/base-wecare-digital-*/index/*"
        ]
      },
      {
        "Sid": "S3MediaAccess",
        "Effect": "Allow",
        "Action": [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ],
        "Resource": [
          "arn:aws:s3:::app.wecare.digital",
          "arn:aws:s3:::app.wecare.digital/whatsapp-media/*"
        ]
      },
      {
        "Sid": "SQSAccess",
        "Effect": "Allow",
        "Action": [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes"
        ],
        "Resource": "arn:aws:sqs:us-east-1:'"${ACCOUNT_ID}"':base-wecare-digital-*"
      },
      {
        "Sid": "SNSPublish",
        "Effect": "Allow",
        "Action": ["sns:Publish"],
        "Resource": "arn:aws:sns:us-east-1:'"${ACCOUNT_ID}"':base-wecare-digital"
      },
      {
        "Sid": "SecretsManagerRead",
        "Effect": "Allow",
        "Action": ["secretsmanager:GetSecretValue"],
        "Resource": "arn:aws:secretsmanager:us-east-1:'"${ACCOUNT_ID}"':secret:wecare/*"
      },
      {
        "Sid": "CloudWatchMetrics",
        "Effect": "Allow",
        "Action": ["cloudwatch:PutMetricData"],
        "Resource": "*",
        "Condition": {
          "StringEquals": {"cloudwatch:namespace": "WECARE.DIGITAL"}
        }
      },
      {
        "Sid": "LambdaInvoke",
        "Effect": "Allow",
        "Action": ["lambda:InvokeFunction"],
        "Resource": "arn:aws:lambda:us-east-1:'"${ACCOUNT_ID}"':function:wecare-*"
      }
    ]
  }'

echo "IAM role ${ROLE_NAME} created with least-privilege policy"
```

### 5.4 Lambda Functions (Zip-Based Deployment)

```bash
#!/bin/bash
# infra/cli-scripts/deploy-lambdas.sh
set -euo pipefail

REGION="us-east-1"
ACCOUNT_ID="775261844268"
ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/wecare-digital-lambda-role"
RUNTIME="python3.12"
SNS_TOPIC_ARN="arn:aws:sns:${REGION}:${ACCOUNT_ID}:base-wecare-digital"

# Package inbound handler — zip from lambdas/ root so shared/ imports work
cd lambdas
zip -r /tmp/inbound_handler.zip inbound_handler/handler.py inbound_handler/__init__.py shared/ -x '*.pyc' '*__pycache__*'
cd ..

# Deploy inbound handler
aws lambda create-function \
  --function-name "wecare-inbound-whatsapp" \
  --runtime "${RUNTIME}" \
  --handler "inbound_handler.handler.handler" \
  --role "${ROLE_ARN}" \
  --zip-file "fileb:///tmp/inbound_handler.zip" \
  --timeout 60 \
  --memory-size 512 \
  --environment "Variables={
    LOG_LEVEL=INFO,
    SEND_MODE=LIVE,
    CONTACTS_TABLE=base-wecare-digital-ContactsTable,
    MESSAGES_TABLE=base-wecare-digital-WhatsAppInboundTable,
    MEDIA_FILES_TABLE=base-wecare-digital-MediaFilesTable,
    SYSTEM_CONFIG_TABLE=base-wecare-digital-SystemConfigTable,
    IDEMPOTENCY_TABLE=base-wecare-digital-IdempotencyTable,
    MEDIA_BUCKET=app.wecare.digital,
    MEDIA_INBOUND_PREFIX=whatsapp-media/whatsapp-media-incoming/,
    INBOUND_DLQ_URL=https://sqs.us-east-1.amazonaws.com/${ACCOUNT_ID}/base-wecare-digital-inbound-dlq,
    OUTBOUND_WHATSAPP_FUNCTION=wecare-outbound-whatsapp,
    WHATSAPP_PHONE_NUMBER_ID_1=phone-number-id-5e020cecd221429996f6ae721cc42206,
    WHATSAPP_PHONE_NUMBER_ID_2=phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c
  }" \
  --region "${REGION}" 2>/dev/null || \
aws lambda update-function-code \
  --function-name "wecare-inbound-whatsapp" \
  --zip-file "fileb:///tmp/inbound_handler.zip" \
  --region "${REGION}"

# Subscribe inbound Lambda to SNS topic
aws sns subscribe \
  --topic-arn "${SNS_TOPIC_ARN}" \
  --protocol lambda \
  --notification-endpoint "arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:wecare-inbound-whatsapp" \
  --region "${REGION}"

# Grant SNS permission to invoke Lambda
aws lambda add-permission \
  --function-name "wecare-inbound-whatsapp" \
  --statement-id "sns-invoke" \
  --action "lambda:InvokeFunction" \
  --principal "sns.amazonaws.com" \
  --source-arn "${SNS_TOPIC_ARN}" \
  --region "${REGION}" 2>/dev/null || echo "Permission already exists"

# Package outbound handler — zip from lambdas/ root so shared/ imports work
cd lambdas
zip -r /tmp/outbound_sender.zip outbound_sender/handler.py outbound_sender/__init__.py shared/ -x '*.pyc' '*__pycache__*'
cd ..

# Deploy outbound handler
aws lambda create-function \
  --function-name "wecare-outbound-whatsapp" \
  --runtime "${RUNTIME}" \
  --handler "outbound_sender.handler.handler" \
  --role "${ROLE_ARN}" \
  --zip-file "fileb:///tmp/outbound_sender.zip" \
  --timeout 30 \
  --memory-size 256 \
  --environment "Variables={
    LOG_LEVEL=INFO,
    SEND_MODE=LIVE,
    CONTACTS_TABLE=base-wecare-digital-ContactsTable,
    MESSAGES_TABLE=base-wecare-digital-WhatsAppOutboundTable,
    MEDIA_FILES_TABLE=base-wecare-digital-MediaFilesTable,
    RATE_LIMIT_TABLE=base-wecare-digital-RateLimitTable,
    MEDIA_BUCKET=app.wecare.digital,
    MEDIA_OUTBOUND_PREFIX=whatsapp-media/whatsapp-media-outgoing/,
    WHATSAPP_PHONE_NUMBER_ID_1=phone-number-id-5e020cecd221429996f6ae721cc42206,
    WHATSAPP_PHONE_NUMBER_ID_2=phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c
  }" \
  --region "${REGION}" 2>/dev/null || \
aws lambda update-function-code \
  --function-name "wecare-outbound-whatsapp" \
  --zip-file "fileb:///tmp/outbound_sender.zip" \
  --region "${REGION}"

echo "Lambda functions deployed and SNS subscription created"
```

### 5.5 SQS DLQ + CloudWatch Alarms

```bash
#!/bin/bash
# infra/cli-scripts/create-dlq-alarms.sh
set -euo pipefail

REGION="us-east-1"
ACCOUNT_ID="775261844268"
ALARM_TOPIC="arn:aws:sns:${REGION}:${ACCOUNT_ID}:base-wecare-digital"

# Create inbound DLQ
aws sqs create-queue \
  --queue-name "base-wecare-digital-inbound-dlq" \
  --attributes '{
    "VisibilityTimeout": "300",
    "MessageRetentionPeriod": "604800"
  }' \
  --region "${REGION}" 2>/dev/null || echo "Queue already exists"

# Create outbound DLQ
aws sqs create-queue \
  --queue-name "base-wecare-digital-outbound-dlq" \
  --attributes '{
    "VisibilityTimeout": "300",
    "MessageRetentionPeriod": "604800"
  }' \
  --region "${REGION}" 2>/dev/null || echo "Queue already exists"

# CloudWatch Alarm: Lambda error rate
aws cloudwatch put-metric-alarm \
  --alarm-name "wecare-lambda-error-rate" \
  --alarm-description "Lambda error rate exceeds 1%" \
  --metric-name "Errors" \
  --namespace "AWS/Lambda" \
  --statistic "Average" \
  --period 300 \
  --evaluation-periods 2 \
  --threshold 0.01 \
  --comparison-operator "GreaterThanThreshold" \
  --treat-missing-data "notBreaching" \
  --alarm-actions "${ALARM_TOPIC}" \
  --region "${REGION}"

# CloudWatch Alarm: DLQ depth
aws cloudwatch put-metric-alarm \
  --alarm-name "wecare-dlq-depth" \
  --alarm-description "DLQ depth exceeds 10 messages" \
  --metric-name "ApproximateNumberOfMessagesVisible" \
  --namespace "AWS/SQS" \
  --dimensions "Name=QueueName,Value=base-wecare-digital-inbound-dlq" \
  --statistic "Maximum" \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 10 \
  --comparison-operator "GreaterThanThreshold" \
  --treat-missing-data "notBreaching" \
  --alarm-actions "${ALARM_TOPIC}" \
  --region "${REGION}"

echo "DLQ queues and CloudWatch alarms created"
```

### 5.6 Log Groups + Retention

```bash
#!/bin/bash
# infra/cli-scripts/create-log-groups.sh
set -euo pipefail

REGION="us-east-1"
RETENTION_DAYS=30

for FUNC in wecare-inbound-whatsapp wecare-outbound-whatsapp wecare-waba-management wecare-dlq-replay; do
  aws logs create-log-group \
    --log-group-name "/aws/lambda/${FUNC}" \
    --region "${REGION}" 2>/dev/null || echo "Log group exists: ${FUNC}"

  aws logs put-retention-policy \
    --log-group-name "/aws/lambda/${FUNC}" \
    --retention-in-days "${RETENTION_DAYS}" \
    --region "${REGION}"
done

echo "Log groups created with ${RETENTION_DAYS}-day retention"
```

### 5.7 Manual Steps (Unavoidable)

| # | Step | Where | Why Manual |
|---|------|-------|-----------|
| 1 | Link WABA to AWS account | AWS EUM Social Console → "Create WhatsApp Business Account" | `AssociateWhatsAppBusinessAccount` is console-only (requires Meta Embedded Signup redirect) |
| 2 | Complete Meta Embedded Signup | Meta popup during AWS console flow | OAuth redirect to Meta for WABA authorization |
| 3 | Register phone numbers with 2FA PIN | Part of console signup flow | PIN entry required during setup |
| 4 | Verify Meta Business | Meta Business Suite → Settings → Business Verification | Meta-side verification process |
| 5 | Configure payment settings | Meta Business Suite → WhatsApp → Payment Settings | Payment config (MCC, UPI) is Meta-side only |
| 6 | Create WhatsApp Flows | Meta Business Suite → WhatsApp → Flows | Flow creation not available via AWS EUM Social |
| 7 | Update business profile | Meta Business Suite → WhatsApp → Business Profile | Profile management not available via AWS EUM Social |
| 8 | Store Meta access token in Secrets Manager | AWS Console or CLI: `aws secretsmanager put-secret-value` | Token obtained from Meta Business Suite |


---

## 6. Application Code

### 6.1 Repository Structure

```
/
├── infra/
│   └── cli-scripts/
│       ├── create-sns-topic.sh
│       ├── create-dynamodb-tables.sh
│       ├── create-iam-role.sh
│       ├── deploy-lambdas.sh
│       ├── create-dlq-alarms.sh
│       ├── create-log-groups.sh
│       └── configure-event-destination.sh
├── lambdas/
│   ├── inbound_handler/
│   │   └── handler.py
│   ├── outbound_sender/
│   │   └── handler.py
│   └── shared/
│       ├── __init__.py
│       ├── social_client.py      # SocialMessaging client wrapper
│       ├── validation.py         # E.164, required fields
│       ├── storage.py            # DynamoDB CRUD + TTL
│       ├── config.py             # Env vars + Parameter Store
│       └── event_model.py        # Normalized internal event schema
├── tests/
│   ├── fixtures/
│   │   ├── sns_inbound_text.json
│   │   ├── sns_inbound_media.json
│   │   ├── sns_status_delivered.json
│   │   ├── sns_template_status.json
│   │   └── sns_payment_captured.json
│   ├── test_inbound_handler.py
│   ├── test_outbound_sender.py
│   └── test_event_model.py
├── tools/
│   └── replay/
│       └── replay_local.py       # Local replay tool
└── README.md
```

### 6.2 Shared Libraries

#### shared/config.py — Environment + Config

```python
"""
Centralized configuration. All values from environment variables.
"""
import os

# AWS
REGION = os.environ.get('AWS_REGION', 'us-east-1')
ACCOUNT_ID = '775261844268'

# DynamoDB Tables
CONTACTS_TABLE = os.environ.get('CONTACTS_TABLE', 'base-wecare-digital-ContactsTable')
MESSAGES_INBOUND_TABLE = os.environ.get('MESSAGES_TABLE', 'base-wecare-digital-WhatsAppInboundTable')
MESSAGES_OUTBOUND_TABLE = os.environ.get('MESSAGES_OUTBOUND_TABLE', 'base-wecare-digital-WhatsAppOutboundTable')
MEDIA_FILES_TABLE = os.environ.get('MEDIA_FILES_TABLE', 'base-wecare-digital-MediaFilesTable')
IDEMPOTENCY_TABLE = os.environ.get('IDEMPOTENCY_TABLE', 'base-wecare-digital-IdempotencyTable')
SYSTEM_CONFIG_TABLE = os.environ.get('SYSTEM_CONFIG_TABLE', 'base-wecare-digital-SystemConfigTable')

# S3
MEDIA_BUCKET = os.environ.get('MEDIA_BUCKET', 'app.wecare.digital')
MEDIA_INBOUND_PREFIX = os.environ.get('MEDIA_INBOUND_PREFIX', 'whatsapp-media/whatsapp-media-incoming/')
MEDIA_OUTBOUND_PREFIX = os.environ.get('MEDIA_OUTBOUND_PREFIX', 'whatsapp-media/whatsapp-media-outgoing/')

# SNS / SQS
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', f'arn:aws:sns:{REGION}:{ACCOUNT_ID}:base-wecare-digital')
INBOUND_DLQ_URL = os.environ.get('INBOUND_DLQ_URL', '')

# WhatsApp Phone Number IDs
PHONE_NUMBER_ID_1 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_1', 'phone-number-id-5e020cecd221429996f6ae721cc42206')
PHONE_NUMBER_ID_2 = os.environ.get('WHATSAPP_PHONE_NUMBER_ID_2', 'phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c')

# WABA IDs
WABA_ID_1 = os.environ.get('WABA_ID_1', 'waba-e47d916f3c7a47e1a34a19653893dd4b')
WABA_ID_2 = os.environ.get('WABA_ID_2', 'waba-dbe343f210204752b74c80a0a59631a6')

# Meta API
META_API_VERSION = os.environ.get('META_API_VERSION', 'v20.0')

# Operational
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
SEND_MODE = os.environ.get('SEND_MODE', 'LIVE')  # LIVE or DRY_RUN
RATE_LIMIT_PER_SECOND = int(os.environ.get('RATE_LIMIT_PER_SECOND', '80'))
MESSAGE_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days
IDEMPOTENCY_TTL_SECONDS = 30 * 24 * 60 * 60  # 30 days
```

#### shared/social_client.py — SocialMessaging Client Wrapper

```python
"""
AWS EUM Social client wrapper with retries, backoff, throttling, and error normalization.
"""
import json
import time
import logging
import base64
import boto3
from botocore.exceptions import ClientError
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Retry config
MAX_RETRIES = 3
BASE_DELAY = 1.0  # seconds
MAX_DELAY = 10.0

_client = None

def get_client():
    global _client
    if _client is None:
        _client = boto3.client('socialmessaging', region_name='us-east-1')
    return _client


def send_message(phone_number_id: str, message_payload: dict, meta_api_version: str = 'v20.0') -> Dict[str, Any]:
    """
    Send a WhatsApp message via AWS EUM Social.
    message_payload: WhatsApp Message object (dict) — will be JSON-encoded and base64-encoded.
    Returns: {'messageId': str} on success.
    Raises: SocialMessagingError on failure after retries.
    """
    client = get_client()
    message_bytes = json.dumps(message_payload).encode('utf-8')

    for attempt in range(MAX_RETRIES):
        try:
            response = client.send_whatsapp_message(
                originationPhoneNumberId=phone_number_id,
                message=message_bytes,
                metaApiVersion=meta_api_version
            )
            return {'messageId': response.get('messageId', '')}
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ThrottledRequestException' and attempt < MAX_RETRIES - 1:
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                logger.warning(f"Throttled, retrying in {delay}s (attempt {attempt + 1})")
                time.sleep(delay)
                continue
            raise SocialMessagingError(
                code=error_code,
                message=e.response['Error'].get('Message', str(e)),
                http_status=e.response['ResponseMetadata'].get('HTTPStatusCode', 500)
            )


def download_media(media_id: str, phone_number_id: str, s3_bucket: str, s3_key: str) -> Dict[str, Any]:
    """Download media from WhatsApp to S3."""
    client = get_client()
    for attempt in range(MAX_RETRIES):
        try:
            response = client.get_whatsapp_message_media(
                mediaId=media_id,
                originationPhoneNumberId=phone_number_id,
                destinationS3File={'bucketName': s3_bucket, 'key': s3_key}
            )
            return {'fileSize': response.get('fileSize'), 'mimeType': response.get('mimeType')}
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ThrottledRequestException' and attempt < MAX_RETRIES - 1:
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                time.sleep(delay)
                continue
            raise SocialMessagingError(code=error_code, message=str(e))


def upload_media(phone_number_id: str, s3_bucket: str, s3_key: str) -> str:
    """Upload media from S3 to WhatsApp. Returns mediaId."""
    client = get_client()
    for attempt in range(MAX_RETRIES):
        try:
            response = client.post_whatsapp_message_media(
                originationPhoneNumberId=phone_number_id,
                sourceS3File={'bucketName': s3_bucket, 'key': s3_key}
            )
            return response.get('mediaId', '')
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ThrottledRequestException' and attempt < MAX_RETRIES - 1:
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                time.sleep(delay)
                continue
            raise SocialMessagingError(code=error_code, message=str(e))


def delete_media(media_id: str, phone_number_id: str) -> bool:
    """Delete media from WhatsApp servers."""
    client = get_client()
    try:
        response = client.delete_whatsapp_message_media(
            mediaId=media_id,
            originationPhoneNumberId=phone_number_id
        )
        return response.get('success', False)
    except ClientError as e:
        raise SocialMessagingError(code=e.response['Error']['Code'], message=str(e))


class SocialMessagingError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 500):
        self.code = code
        self.message = message
        self.http_status = http_status
        super().__init__(f"[{code}] {message}")
```

#### shared/validation.py — Input Validation

```python
"""Validation utilities for phone numbers and required fields."""
import re

E164_PATTERN = re.compile(r'^\+?[1-9]\d{1,14}$')
PHONE_NUMBER_ID_PATTERN = re.compile(r'^phone-number-id-[0-9a-f]{32}$')
WABA_ID_PATTERN = re.compile(r'^waba-[0-9a-f]{32}$')
MAX_TEXT_LENGTH = 4096


def validate_e164(phone: str) -> bool:
    """Validate E.164 phone number format."""
    cleaned = phone.replace(' ', '').replace('-', '')
    return bool(E164_PATTERN.match(cleaned))


def normalize_phone(phone: str) -> str:
    """Normalize phone to digits only (no + prefix for DynamoDB keys)."""
    return re.sub(r'[^\d]', '', phone)


def validate_phone_number_id(phone_id: str) -> bool:
    return bool(PHONE_NUMBER_ID_PATTERN.match(phone_id))


def validate_waba_id(waba_id: str) -> bool:
    return bool(WABA_ID_PATTERN.match(waba_id))


def validate_text_content(content: str) -> tuple:
    """Returns (is_valid, error_message)."""
    if not content:
        return True, None  # Empty is OK for media-only messages
    if len(content) > MAX_TEXT_LENGTH:
        return False, f'Content exceeds {MAX_TEXT_LENGTH} characters'
    return True, None
```

#### shared/storage.py — DynamoDB CRUD

```python
"""DynamoDB storage layer with TTL support."""
import time
import uuid
import boto3
from decimal import Decimal
from typing import Dict, Any, Optional, List
from .config import (
    REGION, MESSAGES_INBOUND_TABLE, MESSAGES_OUTBOUND_TABLE,
    CONTACTS_TABLE, MEDIA_FILES_TABLE, IDEMPOTENCY_TABLE,
    MESSAGE_TTL_SECONDS, IDEMPOTENCY_TTL_SECONDS
)

dynamodb = boto3.resource('dynamodb', region_name=REGION)


def store_inbound_message(message: Dict[str, Any]) -> str:
    """Store inbound message. Returns message ID."""
    table = dynamodb.Table(MESSAGES_INBOUND_TABLE)
    msg_id = message.get('id', str(uuid.uuid4()))
    now = int(time.time())
    item = {
        'id': msg_id,
        'timestamp': now,
        'expiresAt': now + MESSAGE_TTL_SECONDS,
        **{k: _to_decimal(v) for k, v in message.items()}
    }
    table.put_item(Item=item)
    return msg_id


def store_outbound_message(message: Dict[str, Any]) -> str:
    """Store outbound message. Returns message ID."""
    table = dynamodb.Table(MESSAGES_OUTBOUND_TABLE)
    msg_id = message.get('id', str(uuid.uuid4()))
    now = int(time.time())
    item = {
        'id': msg_id,
        'timestamp': now,
        'expiresAt': now + MESSAGE_TTL_SECONDS,
        **{k: _to_decimal(v) for k, v in message.items()}
    }
    table.put_item(Item=item)
    return msg_id


def check_idempotency(event_id: str) -> bool:
    """Returns True if event already processed (duplicate)."""
    table = dynamodb.Table(IDEMPOTENCY_TABLE)
    try:
        response = table.get_item(Key={'eventId': event_id})
        return 'Item' in response
    except Exception:
        return False


def mark_processed(event_id: str):
    """Mark event as processed for idempotency."""
    table = dynamodb.Table(IDEMPOTENCY_TABLE)
    table.put_item(Item={
        'eventId': event_id,
        'processedAt': int(time.time()),
        'expiresAt': int(time.time()) + IDEMPOTENCY_TTL_SECONDS
    })


def upsert_contact(phone: str, name: str = '', **kwargs) -> str:
    """Create or update contact by phone. Returns contact ID."""
    table = dynamodb.Table(CONTACTS_TABLE)
    # Check if contact exists by phone
    response = table.query(
        IndexName='phone-index',
        KeyConditionExpression='phone = :phone',
        ExpressionAttributeValues={':phone': phone},
        Limit=1
    )
    if response.get('Items'):
        contact = response['Items'][0]
        contact_id = contact['id']
        update_expr = 'SET lastInboundMessageAt = :ts'
        expr_values = {':ts': int(time.time())}
        if name:
            update_expr += ', #n = :name'
            expr_values[':name'] = name
            table.update_item(
                Key={'id': contact_id},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values,
                ExpressionAttributeNames={'#n': 'name'} if name else {}
            )
        else:
            table.update_item(
                Key={'id': contact_id},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values
            )
        return contact_id
    else:
        contact_id = str(uuid.uuid4())
        table.put_item(Item={
            'id': contact_id,
            'phone': phone,
            'name': name or '',
            'createdAt': int(time.time()),
            'lastInboundMessageAt': int(time.time()),
            **{k: _to_decimal(v) for k, v in kwargs.items()}
        })
        return contact_id


def update_message_status(message_id: str, status: str, table_name: str = None):
    """Update message status (sent/delivered/read/failed)."""
    tbl = table_name or MESSAGES_INBOUND_TABLE
    table = dynamodb.Table(tbl)
    table.update_item(
        Key={'id': message_id},
        UpdateExpression='SET #s = :status, statusUpdatedAt = :ts',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':status': status, ':ts': int(time.time())}
    )


def _to_decimal(val):
    """Convert floats to Decimal for DynamoDB."""
    if isinstance(val, float):
        return Decimal(str(val))
    if isinstance(val, dict):
        return {k: _to_decimal(v) for k, v in val.items()}
    if isinstance(val, list):
        return [_to_decimal(v) for v in val]
    return val
```

#### shared/event_model.py — Normalized Internal Event Schema

```python
"""
Normalized internal event model used across inbound/outbound records.
Canonical schema for all WhatsApp events processed through AWS EUM Social.
"""
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List


@dataclass
class NormalizedEvent:
    """Canonical event model for all WhatsApp events."""
    # Core identifiers
    eventType: str  # INBOUND_MESSAGE, STATUS_UPDATE, PAYMENT_STATUS, TEMPLATE_STATUS, PHONE_QUALITY, ACCOUNT_UPDATE
    eventId: str  # Unique event ID (AWS messageId or generated UUID)
    whatsappMessageId: str = ''  # wamid.xxx

    # Message fields (for INBOUND_MESSAGE)
    messageType: str = ''  # text, image, video, audio, document, sticker, location, contacts, reaction, interactive, button, order, system, unsupported, request_welcome, ephemeral
    content: str = ''  # Extracted text content
    senderPhone: str = ''
    senderName: str = ''
    receivingPhone: str = ''
    awsPhoneNumberId: str = ''
    wabaId: str = ''

    # Media fields
    mediaId: str = ''
    mimeType: str = ''
    s3Key: str = ''
    fileSize: int = 0
    mediaCaption: str = ''

    # Interactive fields
    interactiveType: str = ''  # button_reply, list_reply, nfm_reply
    interactiveData: Dict[str, Any] = field(default_factory=dict)

    # Location fields
    latitude: float = 0.0
    longitude: float = 0.0
    locationName: str = ''
    locationAddress: str = ''

    # Reaction fields
    reactionMessageId: str = ''
    reactionEmoji: str = ''

    # Status fields (for STATUS_UPDATE)
    status: str = ''  # sent, delivered, read, failed
    recipientPhone: str = ''
    errorCode: str = ''
    errorTitle: str = ''
    errorDetails: str = ''

    # Payment fields (for PAYMENT_STATUS)
    paymentStatus: str = ''  # pending, captured, failed
    referenceId: str = ''
    amount: str = ''
    currency: str = ''

    # Template status fields
    templateName: str = ''
    templateId: str = ''
    newStatus: str = ''
    reason: str = ''

    # Metadata
    timestamp: int = 0
    rawPayload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict, excluding empty/default values."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v and v != 0 and v != 0.0}
```

### 6.3 Inbound Handler (Reference — Key Functions)

The existing `amplify/functions/messaging/inbound-whatsapp-handler/handler.py` is the production implementation. Key flow:

```python
# Simplified reference — actual implementation is in the existing handler
def handler(event, context):
    for record in event.get('Records', []):
        sns_message = json.loads(record['Sns']['Message'])
        
        # 1. Extract AWS EUM Social envelope
        context_data = sns_message.get('context', {})
        webhook_entry = json.loads(sns_message.get('whatsAppWebhookEntry', '{}'))
        aws_message_id = sns_message.get('messageId', str(uuid.uuid4()))
        
        # 2. Process each change
        for change in webhook_entry.get('changes', []):
            value = change.get('value', {})
            
            # 3. Process messages (18 types)
            for message in value.get('messages', []):
                wa_msg_id = message.get('id', '')
                if check_idempotency(wa_msg_id):
                    continue  # Dedup
                
                normalized = normalize_inbound_message(message, value.get('metadata', {}))
                store_inbound_message(normalized.to_dict())
                mark_processed(wa_msg_id)
                
                # Download media if applicable
                if message.get('type') in ('image', 'video', 'audio', 'document', 'sticker'):
                    download_media(...)
                
                # Auto-react + read receipt
                send_auto_reaction(...)
                send_read_receipt(...)
            
            # 4. Process statuses
            for status in value.get('statuses', []):
                update_message_status(...)
            
            # 5. Process non-message events
            field = change.get('field', '')
            if field == 'message_template_status_update':
                process_template_status(...)
            elif field == 'phone_number_quality_update':
                process_phone_quality(...)
            elif field == 'account_update':
                process_account_update(...)
```

### 6.4 Outbound Sender (Reference — Key Functions)

The existing `amplify/functions/messaging/outbound-whatsapp/handler.py` is the production implementation. Key flow:

```python
# Simplified reference — actual implementation is in the existing handler
def handler(event, context):
    body = json.loads(event.get('body', '{}'))
    
    # 1. Validate request
    contact = get_contact(body.get('contactId'))
    phone_number_id = body.get('phoneNumberId', PHONE_NUMBER_ID_1)
    
    # 2. Check rate limit
    if not check_rate_limit(phone_number_id):
        return error_response(429, 'Rate limit exceeded')
    
    # 3. Build WhatsApp Message object based on type
    if body.get('isTemplate'):
        message_payload = build_template_message(body)
    elif body.get('isInteractive'):
        message_payload = build_interactive_message(body)
    elif body.get('isReaction'):
        message_payload = build_reaction_message(body)
    elif body.get('mediaFile'):
        media_id = upload_media(phone_number_id, s3_bucket, s3_key)
        message_payload = build_media_message(body, media_id)
    else:
        message_payload = build_text_message(body)
    
    # 4. Send via AWS EUM Social
    result = send_message(phone_number_id, message_payload, META_API_VERSION)
    
    # 5. Store outbound record
    store_outbound_message({...})
    
    # 6. Emit metric
    emit_delivery_metric('success')
    
    return success_response(result)
```


---

## 7. Event Destination Setup (SNS ONLY)

### 7.1 Configure WABA Event Destination

```bash
#!/bin/bash
# infra/cli-scripts/configure-event-destination.sh
set -euo pipefail

REGION="us-east-1"
ACCOUNT_ID="775261844268"
SNS_TOPIC_ARN="arn:aws:sns:${REGION}:${ACCOUNT_ID}:base-wecare-digital"

# WABA IDs
WABA_1="waba-e47d916f3c7a47e1a34a19653893dd4b"
WABA_2="waba-dbe343f210204752b74c80a0a59631a6"

# Note: AWS EUM Social uses a service-linked role for SNS publishing.
# The roleArn in the event destination config is the service-linked role
# that AWS creates automatically. If you need to specify it explicitly:
EVENT_DEST_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/aws-service-role/social-messaging.amazonaws.com/AWSServiceRoleForSocialMessaging"

# Configure event destination for WABA 1
aws social-messaging put-whatsapp-business-account-event-destinations \
  --id "${WABA_1}" \
  --event-destinations "[{\"eventDestinationArn\":\"${SNS_TOPIC_ARN}\",\"roleArn\":\"${EVENT_DEST_ROLE_ARN}\"}]" \
  --region "${REGION}"

echo "Event destination configured for WABA 1: ${WABA_1} → ${SNS_TOPIC_ARN}"

# Configure event destination for WABA 2
aws social-messaging put-whatsapp-business-account-event-destinations \
  --id "${WABA_2}" \
  --event-destinations "[{\"eventDestinationArn\":\"${SNS_TOPIC_ARN}\",\"roleArn\":\"${EVENT_DEST_ROLE_ARN}\"}]" \
  --region "${REGION}"

echo "Event destination configured for WABA 2: ${WABA_2} → ${SNS_TOPIC_ARN}"

# Verify configuration
echo "Verifying WABA 1..."
aws social-messaging get-linked-whatsapp-business-account \
  --id "${WABA_1}" \
  --query 'account.eventDestinations' \
  --region "${REGION}"

echo "Verifying WABA 2..."
aws social-messaging get-linked-whatsapp-business-account \
  --id "${WABA_2}" \
  --query 'account.eventDestinations' \
  --region "${REGION}"
```

### 7.2 SNS Topic Policy (Required for EUM Social Publishing)

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowEUMSocialPublish",
      "Effect": "Allow",
      "Principal": {
        "Service": "social-messaging.amazonaws.com"
      },
      "Action": "sns:Publish",
      "Resource": "arn:aws:sns:us-east-1:775261844268:base-wecare-digital",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "775261844268"
        }
      }
    }
  ]
}
```

### 7.3 IAM Permissions Reference (Complete)

#### Social Messaging API Calls

| IAM Action | API Operation | Used By |
|-----------|--------------|---------|
| `social-messaging:SendWhatsAppMessage` | POST /v1/whatsapp/send | Outbound Lambda |
| `social-messaging:GetWhatsAppMessageMedia` | POST /v1/whatsapp/media/get | Inbound Lambda |
| `social-messaging:PostWhatsAppMessageMedia` | POST /v1/whatsapp/media | Outbound Lambda |
| `social-messaging:DeleteWhatsAppMessageMedia` | DELETE /v1/whatsapp/media | WABA Mgmt Lambda |
| `social-messaging:GetLinkedWhatsAppBusinessAccount` | GET /v1/whatsapp/waba/details | WABA Mgmt Lambda |
| `social-messaging:GetLinkedWhatsAppBusinessAccountPhoneNumber` | GET /v1/whatsapp/waba/phone/details | WABA Mgmt Lambda |
| `social-messaging:ListLinkedWhatsAppBusinessAccounts` | GET /v1/whatsapp/waba/list | WABA Mgmt Lambda |
| `social-messaging:PutWhatsAppBusinessAccountEventDestinations` | PUT /v1/whatsapp/waba/eventdestinations | Setup script |
| `social-messaging:AssociateWhatsAppBusinessAccount` | POST /v1/whatsapp/signup | Console only |
| `social-messaging:DisassociateWhatsAppBusinessAccount` | DELETE /v1/whatsapp/waba/disassociate | WABA Mgmt Lambda |
| `social-messaging:TagResource` | POST /v1/tags/tag-resource | WABA Mgmt Lambda |
| `social-messaging:UntagResource` | DELETE /v1/tags/untag-resource | WABA Mgmt Lambda |
| `social-messaging:ListTagsForResource` | GET /v1/tags/list | WABA Mgmt Lambda |
| `social-messaging:CreateMessageTemplate` | Template CRUD | WABA Mgmt Lambda |
| `social-messaging:GetMessageTemplate` | Template CRUD | WABA Mgmt Lambda |
| `social-messaging:ListMessageTemplates` | Template CRUD | WABA Mgmt Lambda |
| `social-messaging:DeleteMessageTemplate` | Template CRUD | WABA Mgmt Lambda |
| `social-messaging:UpdateMessageTemplate` | Template CRUD | WABA Mgmt Lambda |
| `social-messaging:SubmitMessageTemplateForReview` | Template CRUD | WABA Mgmt Lambda |
| `social-messaging:GetMessageTemplatePreview` | Template CRUD | WABA Mgmt Lambda |
| `social-messaging:GetWhatsAppBusinessAccountEventDestinations` | Read event config | WABA Mgmt Lambda |

#### SNS Publish/Subscribe Path

| IAM Action | Resource | Used By |
|-----------|----------|---------|
| `sns:Publish` | `arn:aws:sns:us-east-1:775261844268:base-wecare-digital` | DLQ Replay Lambda, EUM Social (via topic policy) |
| `sns:Subscribe` | Same topic | Setup script (Lambda subscription) |

#### DynamoDB Read/Write

| IAM Action | Resource | Used By |
|-----------|----------|---------|
| `dynamodb:GetItem`, `PutItem`, `UpdateItem`, `DeleteItem`, `Query`, `Scan`, `BatchGetItem`, `BatchWriteItem` | `arn:aws:dynamodb:us-east-1:775261844268:table/base-wecare-digital-*` and `/index/*` | All Lambdas |

#### S3 Access

| IAM Action | Resource | Used By |
|-----------|----------|---------|
| `s3:GetObject`, `PutObject`, `DeleteObject` | `arn:aws:s3:::app.wecare.digital/whatsapp-media/*` | Inbound + Outbound Lambdas |
| `s3:ListBucket` | `arn:aws:s3:::app.wecare.digital` | Media dedup check |

#### KMS (Only if encryption enabled)

| IAM Action | Resource | When Needed |
|-----------|----------|-------------|
| `kms:Decrypt`, `kms:GenerateDataKey` | KMS key ARN | If SNS topic or DynamoDB tables use CMK encryption |

---

## 8. Testing & Replay Tool

### 8.1 Test Fixtures

#### tests/fixtures/sns_inbound_text.json

```json
{
  "Records": [
    {
      "EventSource": "aws:sns",
      "Sns": {
        "MessageId": "test-msg-001",
        "Message": "{\"context\":{\"MetaWabaIds\":[\"1912405516040025\"],\"MetaPhoneNumberIds\":[\"960395407161423\"]},\"whatsAppWebhookEntry\":\"{\\\"id\\\":\\\"1912405516040025\\\",\\\"changes\\\":[{\\\"value\\\":{\\\"messaging_product\\\":\\\"whatsapp\\\",\\\"metadata\\\":{\\\"display_phone_number\\\":\\\"919330994400\\\",\\\"phone_number_id\\\":\\\"960395407161423\\\"},\\\"contacts\\\":[{\\\"profile\\\":{\\\"name\\\":\\\"Test User\\\"},\\\"wa_id\\\":\\\"919876543210\\\"}],\\\"messages\\\":[{\\\"from\\\":\\\"919876543210\\\",\\\"id\\\":\\\"wamid.test123\\\",\\\"timestamp\\\":\\\"1707600000\\\",\\\"text\\\":{\\\"body\\\":\\\"Hello from test\\\"},\\\"type\\\":\\\"text\\\"}]},\\\"field\\\":\\\"messages\\\"}]}\",\"aws_account_id\":\"775261844268\",\"message_timestamp\":\"2026-02-11T12:00:00.000Z\",\"messageId\":\"test-uuid-001\"}"
      }
    }
  ]
}
```

#### tests/fixtures/sns_status_delivered.json

```json
{
  "Records": [
    {
      "EventSource": "aws:sns",
      "Sns": {
        "MessageId": "test-status-001",
        "Message": "{\"context\":{\"MetaWabaIds\":[\"1912405516040025\"],\"MetaPhoneNumberIds\":[\"960395407161423\"]},\"whatsAppWebhookEntry\":\"{\\\"id\\\":\\\"1912405516040025\\\",\\\"changes\\\":[{\\\"value\\\":{\\\"messaging_product\\\":\\\"whatsapp\\\",\\\"metadata\\\":{\\\"display_phone_number\\\":\\\"919330994400\\\",\\\"phone_number_id\\\":\\\"960395407161423\\\"},\\\"statuses\\\":[{\\\"id\\\":\\\"wamid.outbound123\\\",\\\"status\\\":\\\"delivered\\\",\\\"timestamp\\\":\\\"1707600100\\\",\\\"recipient_id\\\":\\\"919876543210\\\"}]},\\\"field\\\":\\\"messages\\\"}]}\",\"aws_account_id\":\"775261844268\",\"message_timestamp\":\"2026-02-11T12:01:00.000Z\",\"messageId\":\"test-uuid-002\"}"
      }
    }
  ]
}
```

#### tests/fixtures/sns_payment_captured.json

```json
{
  "Records": [
    {
      "EventSource": "aws:sns",
      "Sns": {
        "MessageId": "test-payment-001",
        "Message": "{\"context\":{\"MetaWabaIds\":[\"1912405516040025\"],\"MetaPhoneNumberIds\":[\"960395407161423\"]},\"whatsAppWebhookEntry\":\"{\\\"id\\\":\\\"1912405516040025\\\",\\\"changes\\\":[{\\\"value\\\":{\\\"messaging_product\\\":\\\"whatsapp\\\",\\\"metadata\\\":{\\\"display_phone_number\\\":\\\"919330994400\\\",\\\"phone_number_id\\\":\\\"960395407161423\\\"},\\\"statuses\\\":[{\\\"id\\\":\\\"wamid.payment123\\\",\\\"status\\\":\\\"captured\\\",\\\"type\\\":\\\"payment\\\",\\\"timestamp\\\":\\\"1707600200\\\",\\\"recipient_id\\\":\\\"919876543210\\\",\\\"payment\\\":{\\\"reference_id\\\":\\\"order-ref-001\\\",\\\"amount\\\":{\\\"value\\\":50000,\\\"offset\\\":100},\\\"currency\\\":\\\"INR\\\",\\\"transaction\\\":{\\\"id\\\":\\\"txn-001\\\",\\\"type\\\":\\\"upi\\\",\\\"status\\\":\\\"success\\\"}}}]},\\\"field\\\":\\\"messages\\\"}]}\",\"aws_account_id\":\"775261844268\",\"message_timestamp\":\"2026-02-11T12:02:00.000Z\",\"messageId\":\"test-uuid-003\"}"
      }
    }
  ]
}
```

### 8.2 Unit Test Example

```python
# tests/test_inbound_handler.py
import json
import pytest
from unittest.mock import patch, MagicMock

# Load fixture
def load_fixture(name):
    with open(f'tests/fixtures/{name}', 'r') as f:
        return json.load(f)


class TestInboundHandler:
    """Test SNS event parsing and normalization."""

    def test_parse_sns_envelope(self):
        """Verify AWS EUM Social SNS envelope is correctly parsed."""
        event = load_fixture('sns_inbound_text.json')
        record = event['Records'][0]
        sns_message = json.loads(record['Sns']['Message'])

        assert 'context' in sns_message
        assert 'whatsAppWebhookEntry' in sns_message
        assert sns_message['aws_account_id'] == '775261844268'

        context = sns_message['context']
        assert '1912405516040025' in context['MetaWabaIds']

    def test_parse_webhook_entry(self):
        """Verify whatsAppWebhookEntry JSON string is correctly decoded."""
        event = load_fixture('sns_inbound_text.json')
        sns_message = json.loads(event['Records'][0]['Sns']['Message'])
        webhook_entry = json.loads(sns_message['whatsAppWebhookEntry'])

        changes = webhook_entry.get('changes', [])
        assert len(changes) == 1

        value = changes[0]['value']
        messages = value.get('messages', [])
        assert len(messages) == 1
        assert messages[0]['type'] == 'text'
        assert messages[0]['text']['body'] == 'Hello from test'
        assert messages[0]['from'] == '919876543210'

    def test_extract_contacts_info(self):
        """Verify sender profile name extraction from contacts array."""
        event = load_fixture('sns_inbound_text.json')
        sns_message = json.loads(event['Records'][0]['Sns']['Message'])
        webhook_entry = json.loads(sns_message['whatsAppWebhookEntry'])
        value = webhook_entry['changes'][0]['value']

        contacts = value.get('contacts', [])
        assert len(contacts) == 1
        assert contacts[0]['profile']['name'] == 'Test User'
        assert contacts[0]['wa_id'] == '919876543210'

    def test_parse_delivery_status(self):
        """Verify delivery status event parsing."""
        event = load_fixture('sns_status_delivered.json')
        sns_message = json.loads(event['Records'][0]['Sns']['Message'])
        webhook_entry = json.loads(sns_message['whatsAppWebhookEntry'])
        value = webhook_entry['changes'][0]['value']

        statuses = value.get('statuses', [])
        assert len(statuses) == 1
        assert statuses[0]['status'] == 'delivered'
        assert statuses[0]['recipient_id'] == '919876543210'

    def test_parse_payment_status(self):
        """Verify payment captured event parsing."""
        event = load_fixture('sns_payment_captured.json')
        sns_message = json.loads(event['Records'][0]['Sns']['Message'])
        webhook_entry = json.loads(sns_message['whatsAppWebhookEntry'])
        value = webhook_entry['changes'][0]['value']

        statuses = value.get('statuses', [])
        assert len(statuses) == 1
        assert statuses[0]['status'] == 'captured'
        assert statuses[0]['type'] == 'payment'
        assert statuses[0]['payment']['reference_id'] == 'order-ref-001'
```

### 8.3 Local Replay Tool

```python
#!/usr/bin/env python3
"""
tools/replay/replay_local.py

Local replay tool: ingest saved SNS event JSON → normalize → write to DynamoDB.
Usage: python replay_local.py <fixture_file.json> [--dry-run]
"""
import sys
import json
import argparse
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# Add parent to path for shared imports
sys.path.insert(0, '../../lambdas')


def replay_event(fixture_path: str, dry_run: bool = False):
    """Replay a saved SNS event fixture through the inbound handler."""
    with open(fixture_path, 'r') as f:
        event = json.load(f)

    record_count = len(event.get('Records', []))
    logger.info(f"Replaying {record_count} record(s) from {fixture_path}")

    for i, record in enumerate(event.get('Records', [])):
        sns_message = json.loads(record.get('Sns', {}).get('Message', '{}'))
        webhook_entry = json.loads(sns_message.get('whatsAppWebhookEntry', '{}'))

        for change in webhook_entry.get('changes', []):
            value = change.get('value', {})
            messages = value.get('messages', [])
            statuses = value.get('statuses', [])

            for msg in messages:
                logger.info(f"  Message: type={msg.get('type')}, from={msg.get('from')}, id={msg.get('id')}")
                if msg.get('type') == 'text':
                    logger.info(f"    Content: {msg.get('text', {}).get('body', '')[:100]}")

                if not dry_run:
                    from shared.storage import store_inbound_message, mark_processed
                    from shared.event_model import NormalizedEvent
                    normalized = NormalizedEvent(
                        eventType='INBOUND_MESSAGE',
                        eventId=sns_message.get('messageId', ''),
                        whatsappMessageId=msg.get('id', ''),
                        messageType=msg.get('type', ''),
                        content=_extract_content(msg),
                        senderPhone=msg.get('from', ''),
                        timestamp=int(msg.get('timestamp', 0))
                    )
                    store_inbound_message(normalized.to_dict())
                    mark_processed(msg.get('id', ''))
                    logger.info(f"    → Stored in DynamoDB")

            for status in statuses:
                logger.info(f"  Status: {status.get('status')}, id={status.get('id')}")

    logger.info(f"Replay complete: {record_count} record(s) processed")


def _extract_content(message: dict) -> str:
    msg_type = message.get('type', '')
    if msg_type == 'text':
        return message.get('text', {}).get('body', '')
    elif msg_type in ('image', 'video', 'document'):
        return message.get(msg_type, {}).get('caption', f'[{msg_type.title()}]')
    elif msg_type == 'location':
        loc = message.get('location', {})
        return f"[Location: {loc.get('latitude')}, {loc.get('longitude')}]"
    elif msg_type == 'reaction':
        return message.get('reaction', {}).get('emoji', '')
    return f'[{msg_type}]'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Replay SNS event fixtures locally')
    parser.add_argument('fixture', help='Path to SNS event JSON fixture file')
    parser.add_argument('--dry-run', action='store_true', help='Parse only, do not write to DynamoDB')
    args = parser.parse_args()
    replay_event(args.fixture, args.dry_run)
```

---

## 9. Operational Runbooks

### 9.1 Throttling / Backoff Strategy

| Layer | Throttle Source | Strategy | Config |
|-------|----------------|----------|--------|
| AWS EUM Social API | `ThrottledRequestException` (HTTP 429) | Exponential backoff: 1s → 2s → 4s (max 10s), 3 retries | `social_client.py` MAX_RETRIES=3 |
| WhatsApp rate limit | 80 msg/sec (Tier 1) | Token bucket rate limiter per phone number ID | `RateLimitTable` with TTL |
| SNS delivery | SNS retry policy | 3 immediate retries → DLQ | SNS subscription config |
| DynamoDB | `ProvisionedThroughputExceededException` | PAY_PER_REQUEST mode (auto-scaling) | Table billing mode |

### 9.2 DLQ Handling + Redrive

```
1. Monitor: CloudWatch alarm "wecare-dlq-depth" fires when > 10 messages
2. Investigate: Check CloudWatch Logs for the inbound Lambda around the failure time
3. Fix: Address root cause (code bug, permission issue, DynamoDB throttle)
4. Redrive: Invoke wecare-dlq-replay Lambda (manual or EventBridge schedule)
   - Reads up to 10 messages from DLQ
   - Re-publishes original SNS message to topic
   - Deletes from DLQ on success
5. Verify: Check DLQ depth returns to 0
```

### 9.3 Alarm Recommendations

| Alarm | Metric | Threshold | Period | Action |
|-------|--------|-----------|--------|--------|
| Lambda error rate | AWS/Lambda Errors (Average) | > 1% | 5 min, 2 periods | SNS notification |
| DLQ depth | AWS/SQS ApproximateNumberOfMessagesVisible | > 10 | 5 min, 1 period | SNS notification |
| Lambda throttles | AWS/Lambda Throttles (Sum) | > 0 | 5 min, 1 period | SNS notification |
| SNS delivery failures | AWS/SNS NumberOfNotificationsFailed | > 0 | 5 min, 2 periods | SNS notification |
| DynamoDB throttles | AWS/DynamoDB ThrottledRequests | > 0 | 5 min, 2 periods | SNS notification |
| Lambda duration | AWS/Lambda Duration (p99) | > 50000 ms | 5 min, 3 periods | SNS notification |
| Custom: Message delivery | WECARE.DIGITAL/MessagesFailed | > 5 | 5 min, 1 period | SNS notification |

### 9.4 Security Notes

1. **Least privilege IAM**: Lambda role has only the permissions listed in Section 7.3. No `*` resource wildcards except for CloudWatch PutMetricData (namespaced).
2. **Secrets management**: Meta access tokens stored in Secrets Manager (`wecare/meta-system-user-token`), not environment variables. Cached in Lambda memory with rotation support.
3. **SNS topic policy**: Restricted to `social-messaging.amazonaws.com` with `aws:SourceAccount` condition — prevents cross-account injection.
4. **PII minimization**: Phone numbers stored as digits only. Profile names stored for display but not indexed. Message content has 30-day TTL auto-deletion.
5. **Encryption**: DynamoDB uses AWS-managed encryption at rest. S3 uses SSE-S3. SNS uses default encryption. Enable CMK if required by compliance.
6. **No direct Meta API calls**: All WhatsApp communication goes through AWS EUM Social, which handles Meta authentication, webhook verification, and API versioning.

### 9.5 Troubleshooting Runbook

| # | Symptom | Likely Cause | Fix |
|---|---------|-------------|-----|
| 1 | No inbound messages arriving | Event destination not configured or SNS topic policy missing | Run `configure-event-destination.sh`; verify topic policy allows `social-messaging.amazonaws.com` |
| 2 | `AccessDeniedException` on SendWhatsAppMessage | Missing IAM permission | Add `social-messaging:SendWhatsAppMessage` to Lambda role |
| 3 | `AccessDeniedByMetaException` | Meta token expired or insufficient permissions | Rotate token in Secrets Manager; verify Meta system user has `whatsapp_business_messaging` permission |
| 4 | `ResourceNotFoundException` on send | Invalid phone number ID or WABA not linked | Verify phone number ID format (`phone-number-id-xxx`); check WABA status with `GetLinkedWhatsAppBusinessAccount` |
| 5 | `DependencyException` (HTTP 502) | Meta API temporarily unavailable | Retry with backoff; check Meta status page |
| 6 | Messages sent but no delivery status | Event destination not receiving statuses | Verify `enableReceiving=true` on WABA; check SNS subscription is active |
| 7 | Media download fails | S3 bucket policy or IAM permission issue | Verify Lambda role has `s3:PutObject` on `app.wecare.digital/whatsapp-media/*` |
| 8 | Duplicate messages processed | Idempotency table not working | Check `IdempotencyTable` exists with TTL enabled; verify `eventId` key format |
| 9 | DLQ growing | Lambda processing errors | Check CloudWatch Logs for error details; common: JSON parse errors, DynamoDB write failures |
| 10 | Rate limit errors (429) | Exceeding 80 msg/sec | Implement queue-based sending; increase tier via Meta Business Suite |
| 11 | Template message rejected | Template not approved or wrong parameters | Verify template status via `GetMessageTemplate`; check parameter count matches template |
| 12 | Payment status not received | Payment webhook not configured | Verify payment config in Meta Business Suite; check SNS topic receives payment events |

---

## Appendix: AWS EUM Social API Operations — Complete Reference

| # | Operation | Method | Path | Request Body | Response | Notes |
|---|-----------|--------|------|-------------|----------|-------|
| 1 | SendWhatsAppMessage | POST | /v1/whatsapp/send | `{message: blob, metaApiVersion: string, originationPhoneNumberId: string}` | `{messageId: string}` | message is base64-encoded WhatsApp Message object; max 2MB |
| 2 | GetWhatsAppMessageMedia | POST | /v1/whatsapp/media/get | `{mediaId, originationPhoneNumberId, destinationS3File?, destinationS3PresignedUrl?, metadataOnly?}` | `{fileSize: long, mimeType: string}` | Use either S3File or PresignedUrl |
| 3 | PostWhatsAppMessageMedia | POST | /v1/whatsapp/media | `{originationPhoneNumberId, sourceS3File?, sourceS3PresignedUrl?}` | `{mediaId: string}` | Use either S3File or PresignedUrl |
| 4 | DeleteWhatsAppMessageMedia | DELETE | /v1/whatsapp/media | Query: mediaId, originationPhoneNumberId | `{success: boolean}` | Also delete from S3 separately |
| 5 | AssociateWhatsAppBusinessAccount | POST | /v1/whatsapp/signup | `{setupFinalization?, signupCallback?}` | `{signupCallbackResult?, statusCode}` | Console-only signup flow |
| 6 | DisassociateWhatsAppBusinessAccount | DELETE | /v1/whatsapp/waba/disassociate | Query: id | HTTP 200 empty | Removes WABA link |
| 7 | GetLinkedWhatsAppBusinessAccount | GET | /v1/whatsapp/waba/details | Query: id | `{account: {...}}` | Returns full WABA details + phone numbers |
| 8 | GetLinkedWhatsAppBusinessAccountPhoneNumber | GET | /v1/whatsapp/waba/phone/details | Query: id | `{linkedWhatsAppBusinessAccountId, phoneNumber: {...}}` | Returns phone details + quality |
| 9 | ListLinkedWhatsAppBusinessAccounts | GET | /v1/whatsapp/waba/list | Query: maxResults?, nextToken? | `{linkedAccounts: [...], nextToken?}` | Paginated; max 100 per page |
| 10 | PutWhatsAppBusinessAccountEventDestinations | PUT | /v1/whatsapp/waba/eventdestinations | `{id, eventDestinations: [{eventDestinationArn, roleArn}]}` | HTTP 200 empty | Max 1 event destination per WABA |
| 11 | TagResource | POST | /v1/tags/tag-resource | `{resourceArn, tags: [{key, value}]}` | `{statusCode}` | |
| 12 | UntagResource | DELETE | /v1/tags/untag-resource | Query: resourceArn, tagKeys | `{statusCode}` | |
| 13 | ListTagsForResource | GET | /v1/tags/list | Query: resourceArn | `{tags: [{key, value}]}` | |
| 14-21 | Template CRUD (8 operations) | Various | Various | Various | Various | CreateMessageTemplate, GetMessageTemplate, ListMessageTemplates, DeleteMessageTemplate, UpdateMessageTemplate, SubmitMessageTemplateForReview, GetMessageTemplatePreview, GetWhatsAppBusinessAccountEventDestinations |

---

*Document generated 2026-02-11. Sources: AWS EUM Social User Guide + API Reference (21 operations crawled), Meta WhatsApp Business Platform docs (links 5-12 crawled for capability requirements). No SAM/CloudFormation/CDK artifacts. All implementation via AWS CLI + SDK.*
