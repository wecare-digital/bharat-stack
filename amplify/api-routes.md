# WECARE.DIGITAL API Routes

API Gateway: `https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod`

## Status: ✅ ALL ROUTES WIRED AND TESTED

## Contacts API
| Method | Route | Lambda Handler | Status |
|--------|-------|----------------|--------|
| GET | /contacts | wecare-contacts-read | ✅ Active |
| GET | /contacts/{contactId} | wecare-contacts-read | ✅ Active |
| POST | /contacts | wecare-contacts-create | ✅ Active |
| PUT | /contacts/{contactId} | wecare-contacts-update | ✅ Active |
| DELETE | /contacts/{contactId} | wecare-contacts-delete | ✅ Active |
| GET | /contacts/search | wecare-contacts-search | ✅ Active |

## Messages API
| Method | Route | Lambda Handler | Status |
|--------|-------|----------------|--------|
| GET | /messages | wecare-messages-read | ✅ Active |
| GET | /messages/{messageId} | wecare-messages-read | ✅ Active |
| DELETE | /messages/{messageId} | wecare-messages-delete | ✅ Active |

## WhatsApp API
| Method | Route | Lambda Handler | Status |
|--------|-------|----------------|--------|
| POST | /whatsapp/send | wecare-outbound-whatsapp | ✅ Active |
| GET | /whatsapp/templates | wecare-whatsapp-template-management | ✅ Active |
| GET | /whatsapp/templates/{templateId} | wecare-whatsapp-template-management | ✅ Active |

## SMS API
| Method | Route | Lambda Handler | Status |
|--------|-------|----------------|--------|
| POST | /sms/send | wecare-outbound-sms | ✅ WIRED & TESTED |

## AWS SMS API (us-east-1)
| Method | Route | Lambda Handler | Status |
|--------|-------|----------------|--------|
| GET | /sms-aws/messages | wecare-sms-aws | 🆕 NEW |
| GET | /sms-aws/messages/{messageId} | wecare-sms-aws | 🆕 NEW |
| POST | /sms-aws/send | wecare-sms-aws | 🆕 NEW |

### AWS SMS API Usage
POST /sms-aws/send sends via Amazon Pinpoint/SNS:
```json
{
  "phoneNumber": "+14155551234",
  "content": "Your verification code is 123456",
  "messageType": "TRANSACTIONAL",
  "senderId": "WECARE"
}
```
Message Types: `TRANSACTIONAL`, `PROMOTIONAL`

### Airtel IQ SMS API (DLT Compliant)
POST /sms/send with `provider: "airtel"` sends via Airtel IQ:
```json
{
  "phoneNumber": "9876543210",
  "content": "Your OTP is 123456",
  "provider": "airtel",
  "messageType": "SERVICE_IMPLICIT",
  "dltTemplateId": "1234567890123456789",
  "sourceAddress": "WECARE",
  "otp": true,
  "apiVersion": "v4"
}
```
Message Types: `PROMOTIONAL`, `TRANSACTIONAL`, `SERVICE_IMPLICIT`, `SERVICE_EXPLICIT`
API Versions: `v4` (standard), `v5` (content moderation), `v6` (enhanced response)

## Email API
| Method | Route | Lambda Handler | Status |
|--------|-------|----------------|--------|
| POST | /email/send | wecare-outbound-email | ✅ WIRED & TESTED |

## Voice Calls API
| Method | Route | Lambda Handler | Status |
|--------|-------|----------------|--------|
| GET | /voice/calls | wecare-voice-calls | ✅ WIRED & TESTED |
| GET | /voice/calls/{callId} | wecare-voice-calls | ✅ WIRED & TESTED |
| POST | /voice/call | wecare-voice-calls | ✅ WIRED & TESTED |

## AWS Voice API (us-east-1)
| Method | Route | Lambda Handler | Status |
|--------|-------|----------------|--------|
| GET | /voice-aws/calls | wecare-voice-aws | 🆕 NEW |
| GET | /voice-aws/calls/{callId} | wecare-voice-aws | 🆕 NEW |
| POST | /voice-aws/call | wecare-voice-aws | 🆕 NEW |

### AWS Voice API Usage
POST /voice-aws/call initiates a call via Amazon Connect:
```json
{
  "phoneNumber": "+14155551234",
  "callType": "tts",
  "messageText": "Hello, this is a test call from WECARE.",
  "voiceId": "Joanna"
}
```
Call Types: `tts` (text-to-speech), `audio` (play audio URL)
Voice IDs: Any Amazon Polly voice (Joanna, Matthew, Amy, etc.)

### Click-to-Call (C2C) via Airtel CCP
POST /voice/call with `callType: "c2c"` initiates a Click-to-Call:
```json
{
  "callType": "c2c",
  "fromNumber": "9876543210",  // Agent number (called first)
  "toNumber": "9123456789",    // Customer number (patched in)
  "enableRecording": true
}
```
Response: `{ "callId": "...", "correlationId": "...", "status": "initiated" }`

## Airtel Voice CDR API
| Method | Route | Lambda Handler | Status |
|--------|-------|----------------|--------|
| POST | /voice-cdr-webhook | wecare-voice-cdr-webhook | ✅ Active |
| GET | /voice-cdr-read | wecare-voice-cdr-read | ✅ Active |

### Airtel CDR Configuration
- Inbound Number: +91 9319767034
- Email: voice@wecare.digital
- Webhook URL: `https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod/voice-cdr-webhook`
- DynamoDB Table: `base-wecare-digital-VoiceCDRTable`

## Bulk Jobs API
| Method | Route | Lambda Handler | Status |
|--------|-------|----------------|--------|
| GET | /bulk/jobs | wecare-bulk-job-create | ✅ WIRED & TESTED |
| GET | /bulk/jobs/{jobId} | wecare-bulk-job-create | ✅ WIRED & TESTED |
| POST | /bulk/jobs | wecare-bulk-job-create | ✅ WIRED & TESTED |
| PUT | /bulk/jobs/{jobId} | wecare-bulk-job-control | ✅ Active |
| DELETE | /bulk/jobs/{jobId} | wecare-bulk-job-control | ✅ Active |

## Payments API
| Method | Route | Lambda Handler | Status |
|--------|-------|----------------|--------|
| GET | /payments | wecare-payments-read | ✅ WIRED & TESTED |
| GET | /payments/{paymentId} | wecare-payments-read | ✅ WIRED & TESTED |
| POST | /razorpay-webhook | wecare-razorpay-webhook | ✅ Active |

## Templates API
| Method | Route | Lambda Handler | Status |
|--------|-------|----------------|--------|
| GET | /templates | wecare-whatsapp-template-management | ✅ Active |
| GET | /templates/{templateId} | wecare-whatsapp-template-management | ✅ Active |
| POST | /templates | wecare-whatsapp-template-management | ✅ Active |
| POST | /templates/from-library | wecare-whatsapp-template-management | ✅ Active |
| PUT | /templates/{templateId} | wecare-whatsapp-template-management | ✅ Active |
| DELETE | /templates/{templateName} | wecare-whatsapp-template-management | ✅ Active |
| GET | /templates/library | wecare-whatsapp-template-management | ✅ Active |
| POST | /templates/media | wecare-whatsapp-template-management | ✅ Active |
| POST | /templates/carousel | wecare-whatsapp-template-management | ✅ Active |
| POST | /templates/carousel-media | wecare-whatsapp-template-management | ✅ Active |

## WABA Management API
| Method | Route | Lambda Handler | Status |
|--------|-------|----------------|--------|
| GET | /waba | wecare-waba-management | ✅ Active |
| GET | /waba/{wabaId} | wecare-waba-management | ✅ Active |
| GET | /waba/phone/{phoneNumberId} | wecare-waba-management | ✅ Active |
| GET | /waba/events | wecare-waba-management | ✅ Active |
| DELETE | /waba/media/{mediaId} | wecare-waba-management | ✅ Active |

## AI API
| Method | Route | Lambda Handler | Status |
|--------|-------|----------------|--------|
| POST | /ai/generate | wecare-ai-generate-response | ✅ Active |
| GET | /ai/query | wecare-ai-query-kb | ✅ Active |
| GET | /ai/config | wecare-ai-config-management | ✅ Active |
| PUT | /ai/config | wecare-ai-config-management | ✅ Active |
| GET | /ai/prompts | wecare-ai-config-management | ✅ Active |
| GET | /ai/prompts/{lang} | wecare-ai-config-management | ✅ Active |
| PUT | /ai/prompts/{lang} | wecare-ai-config-management | ✅ Active |
| GET | /ai/interactions | wecare-ai-config-management | ✅ Active |
| GET | /ai/stats | wecare-ai-config-management | ✅ Active |
| GET | /ai/internal/config | wecare-ai-config-management | ✅ Active |
| PUT | /ai/internal/config | wecare-ai-config-management | ✅ Active |

## Billing API
| Method | Route | Lambda Handler | Status |
|--------|-------|----------------|--------|
| GET | /billing | wecare-billing | ✅ Active |

## Operations API
| Method | Route | Lambda Handler | Status |
|--------|-------|----------------|--------|
| GET | /dlq | wecare-dlq-replay | ✅ Active |
| POST | /dlq/replay | wecare-dlq-replay | ✅ Active |

## Scheduled Messages API
| Method | Route | Lambda Handler | Status |
|--------|-------|----------------|--------|
| GET | /scheduled | wecare-scheduled-messages | ✅ Active |
| POST | /scheduled | wecare-scheduled-messages | ✅ Active |
| DELETE | /scheduled/{scheduleId} | wecare-scheduled-messages | ✅ Active |

## Template Analytics API
| Method | Route | Lambda Handler | Status |
|--------|-------|----------------|--------|
| GET | /analytics/templates | wecare-template-analytics | ✅ Active |

---

## Lambda Functions Summary

### Existing (17 functions)
1. wecare-contacts-read
2. wecare-contacts-create
3. wecare-contacts-update
4. wecare-contacts-delete
5. wecare-contacts-search
6. wecare-messages-read
7. wecare-messages-delete
8. wecare-outbound-whatsapp
9. wecare-ai-generate-response
10. wecare-ai-query-kb
11. wecare-ai-config-management
12. wecare-agent-action-group
13. wecare-billing
14. wecare-template-analytics
15. wecare-scheduled-messages
16. wecare-waba-management
17. wecare-inbound-whatsapp-handler
18. wecare-whatsapp-template-management
19. wecare-bulk-job-control
20. wecare-razorpay-webhook
21. wecare-dlq-replay

### New Functions (9 functions)
1. wecare-outbound-sms - SMS sending via AWS SNS/Pinpoint or Airtel
2. wecare-outbound-email - Email sending via Amazon SES
3. wecare-voice-calls - Voice call management (make/list/get calls)
4. wecare-bulk-job-create - Bulk job creation and listing
5. wecare-payments-read - Payment records listing
6. wecare-voice-cdr-webhook - Airtel Voice CDR webhook receiver
7. wecare-voice-cdr-read - Read Airtel Voice CDR records
8. wecare-voice-aws - AWS Voice calls via Amazon Connect (us-east-1)
9. wecare-sms-aws - AWS SMS via Amazon Pinpoint/SNS (us-east-1)

---

## Bedrock AI Configuration

### Internal Agent (FloatingAgent - Admin Tasks)
- Agent ID: `TJAZR473IJ`
- Agent Alias: `O4U1HF2MSX`
- Knowledge Base ID: `7IWHVB0ZXQ`
- Model: `amazon.nova-lite-v1:0`

### External Agent (WhatsApp Auto-Reply - Customer Facing)
- Agent ID: `JDXIOU2UR9`
- Agent Alias: `AQVQPGYXRR`
- Knowledge Base ID: `CTH8DH3RXY`
- Model: `amazon.nova-lite-v1:0`
