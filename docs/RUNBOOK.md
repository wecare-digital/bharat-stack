# WECARE.DIGITAL — Operational Runbook

**Last Updated:** 2026-03-20  
**AWS Account:** 775261844268 | Region: us-east-1

---

## 1. Architecture Overview

- Frontend: Next.js on Amplify Hosting
- Backend: 44+ Python Lambda functions (deployed separately, not Amplify-managed)
- Database: 41 DynamoDB tables (PAY_PER_REQUEST)
- Messaging: AWS End User Messaging Social (WhatsApp), Pinpoint (SMS/Voice)
- AI: Amazon Bedrock (Nova Lite), Amazon Polly (TTS)
- Payments: Razorpay + PayU webhooks
- Monitoring: CloudWatch Dashboard + Alarms + SNS

## 2. Critical Lambda Functions

| Function | Purpose | DLQ |
|----------|---------|-----|
| wecare-inbound-whatsapp | Process inbound WhatsApp via SNS | stack-wecare-digital-inbound-dlq |
| wecare-outbound-whatsapp | Send WhatsApp messages via Meta Direct API | stack-wecare-digital-outbound-dlq |
| wecare-whatsapp-calling | Handle WhatsApp voice/video calls | N/A |
| wecare-razorpay-webhook | Process Razorpay payment events | N/A |
| wecare-bulk-worker | Process bulk message queue | stack-wecare-digital-bulk-dlq |

## 3. Common Failure Scenarios

### 3.1 Inbound Messages Not Processing

**Symptoms:** Messages not appearing in inbox, DLQ depth alarm firing.

**Diagnosis:**
1. Check CloudWatch Logs: `/aws/lambda/wecare-inbound-whatsapp`
2. Check DLQ depth: `stack-wecare-digital-inbound-dlq` in SQS console
3. Check SNS subscription: Verify Lambda is subscribed to the WhatsApp SNS topic

**Resolution:**
- If Lambda errors: Check error logs, fix code, redeploy
- If DLQ filling: Run DLQ replay via `wecare-dlq-replay` Lambda
- If SNS disconnected: Re-subscribe Lambda to SNS topic

### 3.2 Outbound Messages Failing

**Symptoms:** Messages stuck in PENDING, error rate alarm firing.

**Diagnosis:**
1. Check CloudWatch Logs: `/aws/lambda/wecare-outbound-whatsapp`
2. Look for Meta error codes (131xxx) in logs
3. Check rate limit tracker in DynamoDB `RateLimitTracker` table

**Resolution:**
- Error 131047 (window expired): Send template message instead of free-form
- Error 131056 (pair rate limit): Wait for exponential backoff (4^X seconds)
- Error 131048 (spam): Review message quality, reduce marketing volume
- Error 132001 (template not found): Verify template name and language code

### 3.3 Payment Webhook Failures

**Symptoms:** Payments captured in Razorpay but not reflected in app.

**Diagnosis:**
1. Check CloudWatch Logs: `/aws/lambda/wecare-razorpay-webhook`
2. Verify webhook signature validation in logs
3. Check Payment table in DynamoDB

**Resolution:**
- If signature mismatch: Verify Razorpay webhook secret in Secrets Manager
- If Lambda timeout: Increase timeout (currently 30s)
- Manual reconciliation: Query Razorpay API and update Payment table

### 3.4 WhatsApp Calling Issues

**Symptoms:** Calls not connecting, SDP errors, 138xxx error codes.

**Diagnosis:**
1. Check CloudWatch Logs: `/aws/lambda/wecare-whatsapp-calling`
2. Look for META_CALLING_ERRORS codes in logs
3. Check WhatsAppCalling table for call status

**Resolution:**
- Error 138000: Enable calling on phone number via Meta Business Manager
- Error 138006: Send call_permission_request before outbound call
- Error 138007: Check SDP answer generation speed (timeout)
- Error 138012: Daily outbound call limit (100) reached — wait 24h

### 3.5 DLQ Replay

**Steps:**
1. Navigate to Lambda console → `wecare-dlq-replay`
2. Invoke with: `{"queueName": "stack-wecare-digital-inbound-dlq", "maxMessages": 10}`
3. Monitor CloudWatch logs for replay results
4. Verify messages processed in WhatsAppInbound table

## 4. Monitoring & Alerting

### CloudWatch Dashboard
- Name: `WECARE-DIGITAL-Dashboard`
- Widgets: Message delivery by channel, DLQ depth, Lambda errors

### Alarms
| Alarm | Threshold | Action |
|-------|-----------|--------|
| wecare-lambda-error-rate | >1% over 10min | SNS → stack-wecare-digital |
| wecare-dlq-depth | >10 messages | SNS → stack-wecare-digital |
| wecare-inbound-whatsapp-errors | >5 errors/5min | SNS → stack-wecare-digital |
| wecare-outbound-whatsapp-errors | >5 errors/5min | SNS → stack-wecare-digital |
| wecare-whatsapp-calling-errors | >5 errors/5min | SNS → stack-wecare-digital |
| wecare-razorpay-webhook-errors | >5 errors/5min | SNS → stack-wecare-digital |
| wecare-bulk-worker-errors | >5 errors/5min | SNS → stack-wecare-digital |

## 5. DynamoDB TTL Configuration

TTL is enabled on 18 tables via CDK overrides in `amplify/backend.ts`:
- Messages: 30 days (expiresAt)
- DLQMessages: 7 days (expiresAt)
- AuditLogs: 180 days (expiresAt)
- RateLimitTrackers: 24 hours (lastUpdatedAt)
- Voice/SMS tables: 90 days (expiresAt)
- WebhookDedup: configurable (ttl)
- SystemEvent: configurable (ttl)
- CatalogCache: configurable (ttl)
- AdClickAttribution: configurable (ttl)

## 6. Security Checklist

- [x] X-Hub-Signature-256 verification on all webhook handlers
- [x] Webhook timestamp validation (5-minute replay window)
- [x] PII redaction utility (mask_phone, redact_pii) in all handlers
- [x] appsecret_proof on all Meta Graph API calls
- [x] Razorpay webhook signature verification (HMAC-SHA256)
- [x] WAF protection on webhook endpoints (rate limiting + AWS managed rules)
- [x] CloudWatch log retention (90 days)
- [x] Per-Lambda error rate alarms on critical functions
- [x] DynamoDB IAM scoped to stack-wecare-digital-* tables + indexes

## 7. Deployment

Lambda functions are deployed separately (not managed by Amplify Gen 2).

**Deploy a single Lambda:**
```bash
# Package and deploy (example for outbound-whatsapp)
cd amplify/functions/messaging/outbound-whatsapp
zip -r handler.zip handler.py
aws lambda update-function-code --function-name wecare-outbound-whatsapp --zip-file fileb://handler.zip
```

**Deploy shared utils:**
```bash
cd amplify/functions/shared
zip -r layer.zip lambda_utils/
aws lambda publish-layer-version --layer-name wecare-lambda-utils --zip-file fileb://layer.zip
```

## 8. Dual WABA Configuration

| Property | WABA 1 | WABA 2 |
|----------|--------|--------|
| Meta WABA ID | 2094615664435155 | 2513394156072604 |
| Phone Meta ID | 960395407161423 | 997428863451102 |
| Phone Direct API ID | phone-number-id-waba1-direct-1016149501586345 | phone-number-id-waba-t-direct-1055232054343117 |
| Display Phone | +91 9330994400 | +91 9903300044 |
| Token Secret Key | access_token | access_token_waba2 |
| App Secret Key | app_secret | app_secret_waba2 |

## 9. Emergency Contacts

- AWS Support: via AWS Console (Business Support plan)
- Meta Business Support: business.facebook.com/help
- Razorpay Support: dashboard.razorpay.com/support
