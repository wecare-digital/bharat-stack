# Sample CloudWatch Logs — AWS EUM Social Reference Implementation

Sample log output for phones `919154321112` and `919513745550` across all event types.
Timestamps use epoch seconds; `requestId` is the Lambda invocation ID.

---

## 1. Inbound Handler Logs

### 1.1 Lambda Start
```json
{"event": "inbound_start", "records": 1, "requestId": "a1b2c3d4-5678-90ab-cdef-111111111111"}
```

### 1.2 Text Message from 919154321112
```json
{"event": "msg_stored", "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479", "type": "text", "sender": "919154321112", "phone": "phone-number-id-5e020cecd221429996f6ae721cc42206", "content": "Hi, I need help with my order", "requestId": "a1b2c3d4-5678-90ab-cdef-111111111111"}
{"event": "auto_react_sent", "waId": "wamid.HBgLOTE5MTU0MzIxMTEyFQIAERgSQzJGMDFBNjI3RjQ5RTc2AA==", "recipient": "919154321112", "requestId": "a1b2c3d4-5678-90ab-cdef-111111111111"}
{"event": "read_receipt_sent", "waId": "wamid.HBgLOTE5MTU0MzIxMTEyFQIAERgSQzJGMDFBNjI3RjQ5RTc2AA==", "recipient": "919154321112", "requestId": "a1b2c3d4-5678-90ab-cdef-111111111111"}
```

### 1.3 Image Message from 919513745550
```json
{"event": "msg_stored", "id": "8a3b4c5d-6e7f-4890-ab12-cd34ef567890", "type": "image", "sender": "919513745550", "phone": "phone-number-id-5e020cecd221429996f6ae721cc42206", "content": "Here is the screenshot", "requestId": "a1b2c3d4-5678-90ab-cdef-222222222222"}
```

### 1.4 Document Message from 919154321112
```json
{"event": "msg_stored", "id": "1a2b3c4d-5e6f-7890-abcd-ef1234567890", "type": "document", "sender": "919154321112", "phone": "phone-number-id-5e020cecd221429996f6ae721cc42206", "content": "invoice-2026-feb.pdf", "requestId": "a1b2c3d4-5678-90ab-cdef-333333333333"}
```

### 1.5 Location Message from 919513745550
```json
{"event": "msg_stored", "id": "2b3c4d5e-6f70-8901-bcde-f12345678901", "type": "location", "sender": "919513745550", "phone": "phone-number-id-5e020cecd221429996f6ae721cc42206", "content": "[Location: 22.5726, 88.3639]", "requestId": "a1b2c3d4-5678-90ab-cdef-444444444444"}
```

### 1.6 Reaction from 919154321112
```json
{"event": "msg_stored", "id": "3c4d5e6f-7081-9012-cdef-123456789012", "type": "reaction", "sender": "919154321112", "phone": "phone-number-id-5e020cecd221429996f6ae721cc42206", "content": "👍", "requestId": "a1b2c3d4-5678-90ab-cdef-555555555555"}
```

### 1.7 Interactive Button Reply from 919513745550
```json
{"event": "msg_stored", "id": "4d5e6f70-8192-0123-def0-234567890123", "type": "interactive", "sender": "919513745550", "phone": "phone-number-id-5e020cecd221429996f6ae721cc42206", "content": "Yes, confirm order", "requestId": "a1b2c3d4-5678-90ab-cdef-666666666666"}
```

### 1.8 Interactive List Reply from 919154321112
```json
{"event": "msg_stored", "id": "5e6f7081-9203-1234-ef01-345678901234", "type": "interactive", "sender": "919154321112", "phone": "phone-number-id-5e020cecd221429996f6ae721cc42206", "content": "Premium Plan", "requestId": "a1b2c3d4-5678-90ab-cdef-777777777777"}
```

### 1.9 Flow (nfm_reply) from 919513745550
```json
{"event": "msg_stored", "id": "6f708192-0314-2345-f012-456789012345", "type": "interactive", "sender": "919513745550", "phone": "phone-number-id-5e020cecd221429996f6ae721cc42206", "content": "[Flow: {\"screen\":\"SUMMARY\",\"name\":\"Rahul\",\"email\":\"[email]\"}]", "requestId": "a1b2c3d4-5678-90ab-cdef-888888888888"}
```

### 1.10 Order Message from 919154321112
```json
{"event": "msg_stored", "id": "70819203-1425-3456-0123-567890123456", "type": "order", "sender": "919154321112", "phone": "phone-number-id-5e020cecd221429996f6ae721cc42206", "content": "[Order]", "requestId": "a1b2c3d4-5678-90ab-cdef-999999999999"}
```

### 1.11 Unsupported Message from 919513745550
```json
{"event": "msg_stored", "id": "81920314-2536-4567-1234-678901234567", "type": "unsupported", "sender": "919513745550", "phone": "phone-number-id-5e020cecd221429996f6ae721cc42206", "content": "[Unsupported: poll message type not supported in this version]", "requestId": "a1b2c3d4-5678-90ab-cdef-aaaaaaaaaaaa"}
```

### 1.12 Referral (Click-to-WhatsApp Ad) from 919154321112
```json
{"event": "msg_stored", "id": "92031425-3647-5678-2345-789012345678", "type": "referral", "sender": "919154321112", "phone": "phone-number-id-5e020cecd221429996f6ae721cc42206", "content": "[Referral: ad] Summer Sale 50% Off", "requestId": "a1b2c3d4-5678-90ab-cdef-bbbbbbbbbbbb"}
```

### 1.13 Ad Click from 919513745550
```json
{"event": "msg_stored", "id": "03142536-4758-6789-3456-890123456789", "type": "ad_click", "sender": "919513745550", "phone": "phone-number-id-5e020cecd221429996f6ae721cc42206", "content": "[Ad Click: https://fb.com/ads/123456]", "requestId": "a1b2c3d4-5678-90ab-cdef-cccccccccccc"}
```

### 1.14 Product Inquiry from 919154321112
```json
{"event": "msg_stored", "id": "14253647-5869-7890-4567-901234567890", "type": "product_inquiry", "sender": "919154321112", "phone": "phone-number-id-5e020cecd221429996f6ae721cc42206", "content": "[Product: catalog-wecare-001/SKU-PREMIUM-100]", "requestId": "a1b2c3d4-5678-90ab-cdef-dddddddddddd"}
```

### 1.15 Poll Response from 919513745550
```json
{"event": "msg_stored", "id": "25364758-6970-8901-5678-012345678901", "type": "poll", "sender": "919513745550", "phone": "phone-number-id-5e020cecd221429996f6ae721cc42206", "content": "[Poll: Which plan do you prefer?]", "requestId": "a1b2c3d4-5678-90ab-cdef-eeeeeeeeeeee"}
```

### 1.16 System Message (Number Change)
```json
{"event": "msg_stored", "id": "36475869-7081-9012-6789-123456789012", "type": "system", "sender": "919154321112", "phone": "phone-number-id-5e020cecd221429996f6ae721cc42206", "content": "919154321112 changed their phone number to a new number", "requestId": "a1b2c3d4-5678-90ab-cdef-ffffffffffff"}
```

### 1.17 Request Welcome (Conversation Start)
```json
{"event": "msg_stored", "id": "47586970-8192-0123-7890-234567890123", "type": "request_welcome", "sender": "919513745550", "phone": "phone-number-id-5e020cecd221429996f6ae721cc42206", "content": "[User requested to start conversation]", "requestId": "b1b2c3d4-5678-90ab-cdef-111111111111"}
```

### 1.18 Ephemeral (Disappearing Message)
```json
{"event": "msg_stored", "id": "58697081-9203-1234-8901-345678901234", "type": "ephemeral", "sender": "919154321112", "phone": "phone-number-id-5e020cecd221429996f6ae721cc42206", "content": "[Disappearing Message]", "requestId": "b1b2c3d4-5678-90ab-cdef-222222222222"}
```

### 1.19 Contact Created (First Message from New User)
```json
{"event": "contact_created", "id": "c9d8e7f6-5a4b-3c2d-1e0f-abcdef123456", "phone": "919154321112"}
{"event": "contact_created", "id": "d8e7f6a5-4b3c-2d1e-0fab-cdef12345678", "phone": "919513745550"}
```

### 1.20 Idempotency Dedup Skip
```json
{"event": "dedup_skip", "id": "wamid.HBgLOTE5MTU0MzIxMTEyFQIAERgSQzJGMDFBNjI3RjQ5RTc2AA=="}
```

---

## 2. Status Update Logs

### 2.1 Delivery Status — sent → delivered → read
```json
{"event": "status_update", "waId": "wamid.HBgLOTE5MTU0MzIxMTEyFQIAEhgWM0VCMEZBRTYyMjdGNDlFNzYwAA==", "status": "sent", "recipient": "919154321112", "requestId": "c1c2c3c4-5678-90ab-cdef-111111111111"}
{"event": "status_update", "waId": "wamid.HBgLOTE5MTU0MzIxMTEyFQIAEhgWM0VCMEZBRTYyMjdGNDlFNzYwAA==", "status": "delivered", "recipient": "919154321112", "requestId": "c1c2c3c4-5678-90ab-cdef-222222222222"}
{"event": "status_update", "waId": "wamid.HBgLOTE5MTU0MzIxMTEyFQIAEhgWM0VCMEZBRTYyMjdGNDlFNzYwAA==", "status": "read", "recipient": "919154321112", "requestId": "c1c2c3c4-5678-90ab-cdef-333333333333"}
```

### 2.2 Delivery Failed
```json
{"event": "status_update", "waId": "wamid.HBgLOTE5NTEzNzQ1NTUwFQIAEhgWM0VCMEZBRTYyMjdGNDlFNzYwAA==", "status": "failed", "recipient": "919513745550", "requestId": "c1c2c3c4-5678-90ab-cdef-444444444444"}
```

### 2.3 Status No Match (Outbound Record Not Found)
```json
{"event": "status_no_match", "waId": "wamid.UNKNOWN_MSG_ID", "status": "delivered", "recipient": "919154321112", "requestId": "c1c2c3c4-5678-90ab-cdef-555555555555"}
```

### 2.4 Payment Captured
```json
{"event": "payment_status", "refId": "order-ref-001", "status": "captured", "amount": 500.0, "currency": "INR", "requestId": "c1c2c3c4-5678-90ab-cdef-666666666666"}
```

### 2.5 Payment Failed
```json
{"event": "payment_status", "refId": "order-ref-002", "status": "failed", "amount": 250.0, "currency": "INR", "requestId": "c1c2c3c4-5678-90ab-cdef-777777777777"}
```

---

## 3. Webhook Field Logs (Non-Message)

### 3.1 Template Status Update
```json
{"event": "template_status", "name": "hello_world", "status": "APPROVED", "requestId": "d1d2d3d4-5678-90ab-cdef-111111111111"}
{"event": "template_status", "name": "payment_reminder", "status": "REJECTED", "requestId": "d1d2d3d4-5678-90ab-cdef-222222222222"}
{"event": "template_status", "name": "order_update", "status": "PAUSED", "requestId": "d1d2d3d4-5678-90ab-cdef-333333333333"}
```

### 3.2 Phone Number Quality Update
```json
{"event": "phone_quality", "data": {"current_limit": "TIER_1K", "display_phone_number": "919330994400", "event": "FLAGGED", "restriction_info": [{"restriction_type": "RESTRICTED_BIZ_INITIATED"}]}, "requestId": "d1d2d3d4-5678-90ab-cdef-444444444444"}
```

### 3.3 Account Update
```json
{"event": "account_update", "data": {"phone_number": "919330994400", "event": "VERIFIED_ACCOUNT", "ban_info": {"waba_ban_state": ["SCHEDULE_FOR_DISABLE"]}}, "requestId": "d1d2d3d4-5678-90ab-cdef-555555555555"}
```

---

## 4. Outbound Handler Logs

### 4.1 Text Message to 919154321112
```json
{"event": "outbound_start", "sendMode": "LIVE", "requestId": "e1e2e3e4-5678-90ab-cdef-111111111111"}
{"event": "text_sent", "messageId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "waId": "wamid.HBgLOTE5MTU0MzIxMTEyFQIAEhgWM0VCMEZBRTYyMjdGNDlFNzYwAA==", "requestId": "e1e2e3e4-5678-90ab-cdef-111111111111"}
```

### 4.2 Template Message to 919513745550
```json
{"event": "outbound_start", "sendMode": "LIVE", "requestId": "e1e2e3e4-5678-90ab-cdef-222222222222"}
{"event": "template_sent", "messageId": "b2c3d4e5-f6a7-8901-bcde-f12345678901", "waId": "wamid.HBgLOTE5NTEzNzQ1NTUwFQIAEhgWM0VCMEZBRTYyMjdGNDlFNzYwAA==", "template": "payment_reminder", "requestId": "e1e2e3e4-5678-90ab-cdef-222222222222"}
```

### 4.3 Media (Image) to 919154321112
```json
{"event": "outbound_start", "sendMode": "LIVE", "requestId": "e1e2e3e4-5678-90ab-cdef-333333333333"}
{"event": "media_sent", "messageId": "c3d4e5f6-a7b8-9012-cdef-123456789012", "waId": "wamid.HBgLOTE5MTU0MzIxMTEyFQIAEhgWM0VCMEZBRTYyMjdGNDlFNzYwAA==", "mediaType": "image", "requestId": "e1e2e3e4-5678-90ab-cdef-333333333333"}
```

### 4.4 Interactive List to 919513745550
```json
{"event": "outbound_start", "sendMode": "LIVE", "requestId": "e1e2e3e4-5678-90ab-cdef-444444444444"}
{"event": "interactive_sent", "messageId": "d4e5f6a7-b8c9-0123-def0-234567890123", "waId": "wamid.HBgLOTE5NTEzNzQ1NTUwFQIAEhgWM0VCMEZBRTYyMjdGNDlFNzYwAA==", "type": "list", "requestId": "e1e2e3e4-5678-90ab-cdef-444444444444"}
```

### 4.5 Reaction to 919154321112
```json
{"event": "outbound_start", "sendMode": "LIVE", "requestId": "e1e2e3e4-5678-90ab-cdef-555555555555"}
{"event": "reaction_sent", "messageId": "e5f6a7b8-c9d0-1234-ef01-345678901234", "waId": "wamid.HBgLOTE5MTU0MzIxMTEyFQIAEhgWM0VCMEZBRTYyMjdGNDlFNzYwAA==", "emoji": "✅", "requestId": "e1e2e3e4-5678-90ab-cdef-555555555555"}
```

### 4.6 Order Status (Payment Confirmation) to 919513745550
```json
{"event": "outbound_start", "sendMode": "LIVE", "requestId": "e1e2e3e4-5678-90ab-cdef-666666666666"}
{"event": "order_status_sent", "messageId": "f6a7b8c9-d0e1-2345-f012-456789012345", "waId": "wamid.HBgLOTE5NTEzNzQ1NTUwFQIAEhgWM0VCMEZBRTYyMjdGNDlFNzYwAA==", "status": "completed", "requestId": "e1e2e3e4-5678-90ab-cdef-666666666666"}
```

### 4.7 Location to 919154321112
```json
{"event": "outbound_start", "sendMode": "LIVE", "requestId": "e1e2e3e4-5678-90ab-cdef-777777777777"}
{"event": "location_sent", "messageId": "a7b8c9d0-e1f2-3456-0123-567890123456", "waId": "wamid.HBgLOTE5MTU0MzIxMTEyFQIAEhgWM0VCMEZBRTYyMjdGNDlFNzYwAA==", "requestId": "e1e2e3e4-5678-90ab-cdef-777777777777"}
```

### 4.8 Contacts (vCard) to 919513745550
```json
{"event": "outbound_start", "sendMode": "LIVE", "requestId": "e1e2e3e4-5678-90ab-cdef-888888888888"}
{"event": "contacts_sent", "messageId": "b8c9d0e1-f2a3-4567-1234-678901234567", "waId": "wamid.HBgLOTE5NTEzNzQ1NTUwFQIAEhgWM0VCMEZBRTYyMjdGNDlFNzYwAA==", "count": 2, "requestId": "e1e2e3e4-5678-90ab-cdef-888888888888"}
```

### 4.9 DRY_RUN Mode
```json
{"event": "outbound_start", "sendMode": "DRY_RUN", "requestId": "e1e2e3e4-5678-90ab-cdef-999999999999"}
{"event": "dry_run", "messageId": "c9d0e1f2-a3b4-5678-2345-789012345678", "recipientPhone": "919154321112", "body": {"recipientPhone": "919154321112", "content": "Test message"}, "requestId": "e1e2e3e4-5678-90ab-cdef-999999999999"}
```

---

## 5. Error Logs

### 5.1 Inbound — Message Processing Error
```json
{"event": "msg_error", "id": "wamid.CORRUPT_MSG", "error": "KeyError: 'text'", "requestId": "f1f2f3f4-5678-90ab-cdef-111111111111"}
```

### 5.2 Inbound — Record-Level Error (Sent to DLQ)
```json
{"event": "record_error", "error": "JSONDecodeError: Expecting value: line 1 column 1 (char 0)", "requestId": "f1f2f3f4-5678-90ab-cdef-222222222222"}
```

### 5.3 Inbound — Media Download Failure
```json
{"event": "media_dl_error", "mediaId": "media_expired_abc123", "error": "An error occurred (ResourceNotFoundException) when calling the GetWhatsAppMessageMedia operation: Media not found", "requestId": "f1f2f3f4-5678-90ab-cdef-333333333333"}
```

### 5.4 Inbound — Auto-Reaction Failure
```json
{"event": "auto_react_fail", "error": "An error occurred (ThrottledRequestException) when calling the SendWhatsAppMessage operation: Rate exceeded", "requestId": "f1f2f3f4-5678-90ab-cdef-444444444444"}
```

### 5.5 Inbound — Read Receipt Failure
```json
{"event": "read_receipt_fail", "error": "An error occurred (ThrottledRequestException) when calling the SendWhatsAppMessage operation: Rate exceeded", "requestId": "f1f2f3f4-5678-90ab-cdef-555555555555"}
```

### 5.6 Outbound — Invalid JSON
```json
{"event": "outbound_invalid_json", "requestId": "f1f2f3f4-5678-90ab-cdef-666666666666"}
```

### 5.7 Outbound — SocialMessaging API Error
```json
{"event": "social_messaging_error", "code": "ThrottledRequestException", "message": "Rate exceeded", "requestId": "f1f2f3f4-5678-90ab-cdef-777777777777"}
```

### 5.8 Outbound — Store Record Failure
```json
{"event": "store_record_fail", "messageId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "error": "An error occurred (ProvisionedThroughputExceededException)"}
```

### 5.9 Outbound — Contact Lookup Failure
```json
{"event": "contact_lookup_fail", "contactId": "nonexistent-contact-id", "error": "An error occurred (ResourceNotFoundException)"}
```

### 5.10 Outbound — Unhandled Exception
```json
{"event": "outbound_error", "error": "unexpected keyword argument 'invalid_param'", "requestId": "f1f2f3f4-5678-90ab-cdef-888888888888"}
```

---

## 6. Shared Social Client Logs

### 6.1 Send Message Success
```
send_message success: phoneId=phone-number-id-5e020cecd221429996f6ae721cc42206 messageId=wamid.HBgLOTE5MTU0MzIxMTEyFQIAEhgWM0VCMEZBRTYyMjdGNDlFNzYwAA==
```

### 6.2 Upload Media Success
```
upload_media success: phoneId=phone-number-id-5e020cecd221429996f6ae721cc42206 mediaId=media_uploaded_xyz789
```

### 6.3 Download Media Success
```
download_media success: mediaId=media123abc s3=app.wecare.digital/whatsapp-media/whatsapp-media-incoming/media123abc/
```

### 6.4 Throttle + Retry
```
WARNING - Throttled, retry in 1.0s (attempt 1)
WARNING - Throttled, retry in 2.0s (attempt 2)
send_message success: phoneId=phone-number-id-5e020cecd221429996f6ae721cc42206 messageId=wamid.RETRY_SUCCESS
```

---

## 7. Lambda Completion

### 7.1 Inbound Done (Success)
```json
{"event": "inbound_done", "processed": 3, "errors": 0, "requestId": "a1b2c3d4-5678-90ab-cdef-111111111111"}
```

### 7.2 Inbound Done (Partial Failure)
```json
{"event": "inbound_done", "processed": 2, "errors": 1, "requestId": "a1b2c3d4-5678-90ab-cdef-222222222222"}
```
