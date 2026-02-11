# AWS Account Migration Reference — AUTOPILOT

> Migration from old account `809904170947` to new account `775261844268`
> Region: `us-east-1` | Scan date: February 10, 2026
> All steps executed via CLI by Kiro — no manual console work needed

---

## New Account Current Status

### Already Set Up

| Resource | Details |
|----------|---------|
| Route 53 | `wecare.digital` hosted zone (`Z03939753QJGZ6ZD6BXO8`, 14 records) |
| SES | `wecare.digital` + `wecare-digital.awsapps.com` verified |
| SNS | `base-wecare-digital` topic (`arn:aws:sns:us-east-1:775261844268:base-wecare-digital`) |
| S3 | `app.wecare.digital` bucket (`/dev/`, `/stream/` folders) |
| EUM WABA 1 | WECARE.DIGITAL — `waba-e47d916f3c7a47e1a34a19653893dd4b` — +91 93309 94400 — GREEN |
| EUM WABA 2 | Manish Agarwal — `waba-dbe343f210204752b74c80a0a59631a6` — +91 99033 00044 — GREEN |
| Pinpoint Toll-Free | `+18444891209` (`phone-8b753d69919447bf93e21e35e2363d09`) — PENDING registration |
| Pinpoint Protect | `protect-b137924dfb934c32b1d10c28b737d08c` (account default) |

### Created by Kiro (Autopilot)

| Resource | Details | Status |
|----------|---------|--------|
| IAM Lambda Role | `wecare-digital-lambda-role` (`AROA3JAJU6MWMHI4VOYL7`) | ✅ |
| Lambda Functions | 35 functions deployed (Python 3.12, 256MB, 30s timeout) | ✅ |
| DynamoDB Tables | 22 tables (PAY_PER_REQUEST billing) | ✅ |
| API Gateway HTTP API | `zllr9lrg7j` — 52 routes, prod stage (auto-deploy) | ✅ |
| API Gateway Custom Domain | `api.wecare.digital` → `d-3ogtrxenof.execute-api.us-east-1.amazonaws.com` | ✅ |
| ACM Certificate (wildcard) | `*.wecare.digital` — `f75d0db0-d476-443a-b787-96c4931862d2` (ISSUED) | ✅ |
| ACM Certificate (api) | `api.wecare.digital` — `e9462a0a-9d6a-496f-b1f2-257067908e75` (validating) | ✅ |
| Route 53 `api.wecare.digital` | A record alias → API Gateway | ✅ |
| SQS Queues | 4 queues (inbound-dlq, bulk-dlq, bulk-queue, outbound-dlq) | ✅ |
| Secrets Manager | 4 secrets (meta-whatsapp-token, meta-app-secret, airtel-iq, razorpay) | ✅ |
| SES | `one@wecare.digital` verification sent | ✅ |
| Bedrock Internal KB | `D0JU8Q7IQS` (ACTIVE) | ✅ |
| Bedrock External KB | `LYMQLKZNY7` (ACTIVE) | ✅ |
| Bedrock Internal Agent | `QIEEHEBTZO` / Alias `ASCBD7YPUT` | ✅ |
| Bedrock External Agent | `Z4YAK0ZLBO` / Alias `WANPKHQGIB` | ✅ |
| OpenSearch Serverless | `wecare-digital-vectors` (`v3gg4phewwr94mshuda8`) | ✅ |
| S3 Folder Structure | stream/media, gen-ai, whatsapp-media, voice | ✅ |

### Still Pending

| Resource | Notes |
|----------|-------|
| Cognito User Pool | Needs Amplify deploy or manual creation |
| Pinpoint Voice Pool | Toll-free `+18444891209` still PENDING registration |
| Secrets Manager values | Need actual Meta token, Airtel key, Razorpay creds |
| SES email verification | User must click verification link for `one@wecare.digital` |
| Static assets (logos, etc.) | Upload to `s3://app.wecare.digital/stream/media/m/` |

---

## Old → New ID Mapping

| What | Old Value | New Value |
|------|-----------|-----------|
| AWS Account | `809904170947` | `775261844268` |
| S3 Bucket (media) | `auth.wecare.digital` | `app.wecare.digital` |
| S3 Bucket (reports) | `stream.wecare.digital` | `app.wecare.digital` (use `/stream/` prefix) |
| WABA 1 (WECARE.DIGITAL) | `waba-df9aa4e4946a40b59e269a4f41633ca1` | `waba-e47d916f3c7a47e1a34a19653893dd4b` |
| WABA 2 (Manish Agarwal) | `waba-6cab7a36990c4aeeba314ebe5cd1ec39` | `waba-dbe343f210204752b74c80a0a59631a6` |
| Phone ID 1 (WECARE.DIGITAL) | `phone-number-id-2ff05755631b41f29151c0573b7a4e2a` | `phone-number-id-5e020cecd221429996f6ae721cc42206` |
| Phone ID 2 (Manish Agarwal) | `phone-number-id-66d2d11e0aea4f14a3a0df30ec5e3bc6` | `phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c` |
| Meta Phone ID 1 (WECARE.DIGITAL) | `1065003613352032` | `960395407161423` |
| Meta Phone ID 2 (Manish Agarwal) | `1065809899939064` | `997428863451102` |
| Meta WABA ID 1 (WECARE.DIGITAL) | `1728153881476046` | `1912405516040025` |
| Meta WABA ID 2 (Manish Agarwal) | `761651636983279` | `1633959101297902` |
| Toll-Free Number | `+18334061352` | `+18444891209` |
| Pinpoint Phone ID | (old) | `phone-8b753d69919447bf93e21e35e2363d09` |
| Pinpoint Long Code | `+18313877455` | TBD (not yet provisioned) |
| Protect Config | `protect-321c6e19e2ee427bbb9c0daa9a7080ac` | `protect-b137924dfb934c32b1d10c28b737d08c` |
| Pinpoint Pool | `pool-6fbf5a5f390d4eeeaa7dbae39d78933e` | TBD (auto-created by Kiro) |
| API Gateway | `k4vqzmi07b` | `zllr9lrg7j` → custom domain `https://api.wecare.digital` ✅ |
| Cognito User Pool | `us-east-1_CC9u1fYh6` | TBD (after Amplify deploy) |
| Cognito App Client | `5na5ba2pbpanm36138jdcd9gck` | TBD (after Amplify deploy) |
| Cognito Identity Pool | `us-east-1:ef6b783a-f0c5-4d2f-925d-9460e6a733ce` | TBD (after Amplify deploy) |
| Cognito SSO Domain | `sso.wecare.digital` | TBD (reconfigure after deploy) |
| AppSync URL | `gvvw6q62urciljnrbsahsrxdzi.appsync-api...` | TBD (auto-generated) |
| Amplify App ID | `dtiq7il2x5c5g` | TBD (after hosting setup) |
| Bedrock Internal Agent | `TJAZR473IJ` | `QIEEHEBTZO` ✅ |
| Bedrock Internal Alias | `O4U1HF2MSX` | `ASCBD7YPUT` ✅ |
| Bedrock Internal KB | `7IWHVB0ZXQ` | `D0JU8Q7IQS` ✅ |
| Bedrock External Agent | `JDXIOU2UR9` | `Z4YAK0ZLBO` ✅ |
| Bedrock External Alias | `AQVQPGYXRR` | `WANPKHQGIB` ✅ |
| Bedrock External KB | `CTH8DH3RXY` | `LYMQLKZNY7` ✅ |
| OpenSearch Collection | (old) | `v3gg4phewwr94mshuda8` ✅ |
| Google Analytics | `G-S3G6REP6Q7` | Same (no change) |
| Meta App ID | `891766673609917` | Same (no change, Meta-side) |
| Razorpay Webhook Secret | `b@c4mk9t9Z8qLq3` | Same or rotate |

---

## S3 Bucket Structure (`app.wecare.digital`)

```
app.wecare.digital/
├── stream/
│   ├── media/m/                     ← Logos, favicons, images
│   ├── media/ivr/                   ← IVR audio files
│   ├── code/                        ← Widget JS files
│   └── reports/                     ← Bulk job reports
├── whatsapp-media/
│   ├── whatsapp-media-incoming/     ← Inbound WhatsApp media
│   ├── whatsapp-media-outgoing/     ← Outbound WhatsApp media
│   └── template-headers/            ← Template media
├── voice/                           ← Voice recordings
└── dev/                             ← Dev assets
```

---

## Webhook URLs (Custom Domain: `api.wecare.digital`)

| Purpose | Old URL | New URL |
|---------|---------|---------|
| API Base | `https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod` | `https://api.wecare.digital` |
| WhatsApp Inbound | `.../prod/whatsapp-inbound` | `https://api.wecare.digital/whatsapp-inbound` |
| WhatsApp Calling | `.../prod/whatsapp-calling` | `https://api.wecare.digital/whatsapp-calling` |
| Razorpay Webhook | `.../prod/razorpay-webhook` | `https://api.wecare.digital/razorpay-webhook` |
| Airtel SMS In | `.../prod/sms-in/airtel` | `https://api.wecare.digital/sms-in/airtel` |
| Voice CDR Webhook | `.../prod/voice-cdr-webhook` | `https://api.wecare.digital/voice-cdr-webhook` |
| Voice CDR Read | `.../prod/voice-cdr-read` | `https://api.wecare.digital/voice-cdr-read` |
| Voice C2C | `.../prod/voice-in/c2c` | `https://api.wecare.digital/voice-in/c2c` |
| Voice OBD | `.../prod/voice-in/obd` | `https://api.wecare.digital/voice-in/obd` |
| SMS AWS | `.../prod/sms-aws/*` | `https://api.wecare.digital/sms-aws/*` |
| Voice AWS | `.../prod/voice-aws/*` | `https://api.wecare.digital/voice-aws/*` |
| Contacts | `.../prod/contacts` | `https://api.wecare.digital/contacts` |
| Messages | `.../prod/messages` | `https://api.wecare.digital/messages` |
| AI | `.../prod/ai/*` | `https://api.wecare.digital/ai/*` |
| Templates | `.../prod/templates/*` | `https://api.wecare.digital/templates/*` |
| WABA | `.../prod/waba/*` | `https://api.wecare.digital/waba/*` |
| Billing | `.../prod/billing` | `https://api.wecare.digital/billing` |

---

## Naming Convention

| Resource Type | Pattern | Example |
|--------------|---------|---------|
| DynamoDB Tables | `base-wecare-digital-{Name}Table` | `base-wecare-digital-ContactsTable` |
| Lambda Functions | `wecare-{function-name}` | `wecare-inbound-whatsapp-handler` |
| SQS Queues | `base-wecare-digital-{purpose}` | `base-wecare-digital-bulk-queue` |
| SNS Topics | `base-wecare-digital` | Already exists |
| S3 Bucket | `app.wecare.digital` | Already exists |
| IAM Roles | `wecare-digital-lambda-role` | Auto-created |
| Secrets | `wecare/{service}/{key}` | `wecare/meta-system-user-token` |
| CloudWatch NS | `WECARE.DIGITAL` | Same |
| API Domain | `api.wecare.digital` | Auto-created |

---

## Autopilot Execution Plan — Step by Step

### Phase 1: Update Codebase (Kiro runs)

Kiro replaces all hardcoded old-account values in the codebase:

| Find | Replace | Files Affected |
|------|---------|---------------|
| `809904170947` | `775261844268` | ~10 files (IAM policies, scripts, dashboard, README) |
| `auth.wecare.digital` | `app.wecare.digital` | ~18 files (storage, policies, handlers, frontend) |
| `stream.wecare.digital` | `app.wecare.digital` | ~3 files (reports bucket) |
| `waba-df9aa4e4946a40b59e269a4f41633ca1` | `waba-e47d916f3c7a47e1a34a19653893dd4b` | ~5 files |
| `waba-6cab7a36990c4aeeba314ebe5cd1ec39` | `waba-dbe343f210204752b74c80a0a59631a6` | ~5 files |
| `phone-number-id-2ff05755631b41f29151c0573b7a4e2a` | `phone-number-id-5e020cecd221429996f6ae721cc42206` | ~11 files |
| `phone-number-id-66d2d11e0aea4f14a3a0df30ec5e3bc6` | `phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c` | ~11 files |
| `1065003613352032` | `960395407161423` | ~2 files (Meta phone IDs) |
| `1065809899939064` | `997428863451102` | ~2 files |
| `1728153881476046` | `1912405516040025` | ~3 files (Meta WABA IDs) |
| `761651636983279` | `1633959101297902` | ~3 files |
| `+18334061352` | `+18444891209` | ~2 files (toll-free) |
| `protect-321c6e19e2ee427bbb9c0daa9a7080ac` | `protect-b137924dfb934c32b1d10c28b737d08c` | ~2 files |
| `k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod` | `api.wecare.digital` | ~15 files |
| `k4vqzmi07b` (API ID in scripts) | TBD (new API ID) | ~4 scripts |

---

### Phase 2: Amplify Deploy (Kiro runs)

```
npx ampx sandbox
```

This auto-creates:
- Cognito User Pool + App Client + Identity Pool
- 17 DynamoDB Tables
- AppSync GraphQL API
- S3 Storage (Amplify-managed)
- 4 SQS Queues
- CloudWatch Dashboard + 2 Alarms
- IAM Roles for Amplify

After deploy, Kiro reads the new IDs from `amplify_outputs.json` and updates:
- `src/pages/_app.tsx` — Cognito IDs
- `amplify/functions/shared/config.ts` — COGNITO_CONFIG
- `amplify/iam-policies.ts` — Cognito ARN
- `README.md`

---

### Phase 3: IAM Lambda Role (Kiro runs)

```powershell
# Create IAM role for Lambda functions
aws iam create-role --role-name wecare-digital-lambda-role --assume-role-policy-document '{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "lambda.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}'

# Attach managed policies
aws iam attach-role-policy --role-name wecare-digital-lambda-role --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

# Attach inline policy with all permissions (DynamoDB, S3, SQS, SNS, SES, Bedrock, Cognito, etc.)
aws iam put-role-policy --role-name wecare-digital-lambda-role --policy-name wecare-lambda-permissions --policy-document file://scripts/policy-update.json
```

---

### Phase 4: Deploy All Lambda Functions (Kiro runs — loop)

35 Lambda functions deployed via CLI. Each function:
1. Zip the `handler.py` file
2. `aws lambda create-function` with role, env vars, runtime Python 3.12
3. Add resource-based policy for API Gateway invoke

Lambda functions to deploy:

| # | Function Name | Source Path | Timeout | Memory |
|---|--------------|-------------|---------|--------|
| 1 | `wecare-contacts-create` | `amplify/functions/core/contacts-create/` | 30s | 256MB |
| 2 | `wecare-contacts-read` | `amplify/functions/core/contacts-read/` | 30s | 256MB |
| 3 | `wecare-contacts-update` | `amplify/functions/core/contacts-update/` | 30s | 256MB |
| 4 | `wecare-contacts-delete` | `amplify/functions/core/contacts-delete/` | 30s | 256MB |
| 5 | `wecare-contacts-search` | `amplify/functions/core/contacts-search/` | 30s | 256MB |
| 6 | `wecare-messages-read` | `amplify/functions/core/messages-read/` | 30s | 256MB |
| 7 | `wecare-messages-delete` | `amplify/functions/core/messages-delete/` | 30s | 256MB |
| 8 | `wecare-inbound-whatsapp-handler` | `amplify/functions/messaging/inbound-whatsapp-handler/` | 60s | 512MB |
| 9 | `wecare-outbound-whatsapp` | `amplify/functions/messaging/outbound-whatsapp/` | 60s | 512MB |
| 10 | `wecare-outbound-sms` | `amplify/functions/messaging/outbound-sms/` | 30s | 256MB |
| 11 | `wecare-outbound-email` | `amplify/functions/messaging/outbound-email/` | 30s | 256MB |
| 12 | `wecare-scheduled-messages` | `amplify/functions/messaging/scheduled-messages/` | 60s | 256MB |
| 13 | `wecare-sms-aws` | `amplify/functions/messaging/sms-aws/` | 30s | 256MB |
| 14 | `wecare-voice-aws` | `amplify/functions/messaging/voice-aws/` | 30s | 256MB |
| 15 | `wecare-voice-cdr-read` | `amplify/functions/messaging/voice-cdr-read/` | 30s | 256MB |
| 16 | `wecare-sms-in-airtel` | `amplify/functions/messaging/sms-in/airtel/` | 30s | 256MB |
| 17 | `wecare-voice-in-c2c` | `amplify/functions/messaging/voice-in/c2c/` | 30s | 256MB |
| 18 | `wecare-voice-in-obd` | `amplify/functions/messaging/voice-in/obd/` | 30s | 256MB |
| 19 | `wecare-voice-in-cdr` | `amplify/functions/messaging/voice-in/cdr/` | 30s | 256MB |
| 20 | `wecare-whatsapp-calling` | `amplify/functions/messaging/whatsapp-calling/` | 30s | 256MB |
| 21 | `wecare-whatsapp-voice` | `amplify/functions/messaging/whatsapp-voice/` | 30s | 256MB |
| 22 | `wecare-whatsapp-template-management` | `amplify/functions/messaging/whatsapp-template-management/` | 30s | 256MB |
| 23 | `wecare-template-analytics` | `amplify/functions/messaging/template-analytics/` | 30s | 256MB |
| 24 | `wecare-waba-management` | `amplify/functions/messaging/waba-management/` | 30s | 256MB |
| 25 | `wecare-whatsapp-business-api` | `amplify/functions/messaging/whatsapp-business-api/` | 30s | 256MB |
| 26 | `wecare-ai-generate-response` | `amplify/functions/ai/ai-generate-response/` | 60s | 512MB |
| 27 | `wecare-ai-query-kb` | `amplify/functions/ai/ai-query-kb/` | 30s | 256MB |
| 28 | `wecare-ai-config-management` | `amplify/functions/ai/ai-config-management/` | 30s | 256MB |
| 29 | `wecare-agent-action-group` | `amplify/functions/ai/agent-action-group/` | 30s | 256MB |
| 30 | `wecare-billing` | `amplify/functions/operations/billing/` | 30s | 256MB |
| 31 | `wecare-bulk-job-create` | `amplify/functions/operations/bulk-job-create/` | 30s | 256MB |
| 32 | `wecare-bulk-job-control` | `amplify/functions/operations/bulk-job-control/` | 30s | 256MB |
| 33 | `wecare-dlq-replay` | `amplify/functions/operations/dlq-replay/` | 60s | 256MB |
| 34 | `wecare-razorpay-webhook` | `amplify/functions/payments/razorpay-webhook/` | 30s | 256MB |
| 35 | `wecare-payments-read` | `amplify/functions/payments/payments-read/` | 30s | 256MB |

---

### Phase 5: API Gateway + Custom Domain (Kiro runs)

```powershell
# Step 1: Create HTTP API
aws apigatewayv2 create-api --name wecare-digital-api --protocol-type HTTP

# Step 2: Create default stage with auto-deploy
aws apigatewayv2 create-stage --api-id {NEW_API_ID} --stage-name prod --auto-deploy

# Step 3: Request ACM certificate for api.wecare.digital
aws acm request-certificate --domain-name api.wecare.digital --validation-method DNS

# Step 4: Add DNS validation record to Route 53
aws route53 change-resource-record-sets --hosted-zone-id Z03939753QJGZ6ZD6BXO8 --change-batch '{...}'

# Step 5: Wait for certificate validation
aws acm wait certificate-validated --certificate-arn {CERT_ARN}

# Step 6: Create custom domain name
aws apigatewayv2 create-domain-name --domain-name api.wecare.digital --domain-name-configurations CertificateArn={CERT_ARN}

# Step 7: Create API mapping
aws apigatewayv2 create-api-mapping --domain-name api.wecare.digital --api-id {NEW_API_ID} --stage prod

# Step 8: Add Route 53 A record (alias to API Gateway domain)
aws route53 change-resource-record-sets --hosted-zone-id Z03939753QJGZ6ZD6BXO8 --change-batch '{...}'
```

Then create all routes + Lambda integrations:

| Method | Route | Lambda Function |
|--------|-------|----------------|
| POST | `/contacts` | `wecare-contacts-create` |
| GET | `/contacts` | `wecare-contacts-read` |
| PUT | `/contacts` | `wecare-contacts-update` |
| DELETE | `/contacts` | `wecare-contacts-delete` |
| GET | `/contacts/search` | `wecare-contacts-search` |
| GET | `/messages` | `wecare-messages-read` |
| DELETE | `/messages` | `wecare-messages-delete` |
| ANY | `/whatsapp-inbound` | `wecare-inbound-whatsapp-handler` |
| POST | `/whatsapp/send` | `wecare-outbound-whatsapp` |
| POST | `/sms/send` | `wecare-outbound-sms` |
| POST | `/email/send` | `wecare-outbound-email` |
| ANY | `/sms-aws/{proxy+}` | `wecare-sms-aws` |
| ANY | `/voice-aws/{proxy+}` | `wecare-voice-aws` |
| ANY | `/voice-cdr-webhook` | `wecare-voice-in-cdr` |
| GET | `/voice-cdr` | `wecare-voice-cdr-read` |
| ANY | `/sms-in/airtel` | `wecare-sms-in-airtel` |
| ANY | `/voice-in/c2c` | `wecare-voice-in-c2c` |
| ANY | `/voice-in/obd` | `wecare-voice-in-obd` |
| ANY | `/whatsapp-calling` | `wecare-whatsapp-calling` |
| ANY | `/whatsapp-voice/{proxy+}` | `wecare-whatsapp-voice` |
| ANY | `/templates/{proxy+}` | `wecare-whatsapp-template-management` |
| GET | `/templates/analytics` | `wecare-template-analytics` |
| ANY | `/waba/{proxy+}` | `wecare-waba-management` |
| ANY | `/wa-business/{proxy+}` | `wecare-whatsapp-business-api` |
| ANY | `/ai/generate` | `wecare-ai-generate-response` |
| ANY | `/ai/query` | `wecare-ai-query-kb` |
| ANY | `/ai/config` | `wecare-ai-config-management` |
| GET | `/billing` | `wecare-billing` |
| POST | `/bulk/create` | `wecare-bulk-job-create` |
| ANY | `/bulk/control` | `wecare-bulk-job-control` |
| POST | `/dlq/replay` | `wecare-dlq-replay` |
| POST | `/razorpay-webhook` | `wecare-razorpay-webhook` |
| GET | `/payments` | `wecare-payments-read` |
| POST | `/scheduled-messages` | `wecare-scheduled-messages` |

---

### Phase 6: Secrets Manager (Kiro runs)

```powershell
# Secret 1: Meta System User Token (you provide the value)
aws secretsmanager create-secret --name wecare/meta-system-user-token --secret-string "{TOKEN_VALUE}" --region us-east-1

# Secret 2: Meta App Secret (you provide the value)
aws secretsmanager create-secret --name wecare/meta-app-secret --secret-string "{APP_SECRET_VALUE}" --region us-east-1

# Secret 3: Airtel IQ Credentials (you provide the values)
aws secretsmanager create-secret --name wecare/airtel/api-key --secret-string '{"apiKey":"...","appId":"..."}' --region us-east-1
```

> **User input needed:** Provide the 3 secret values before this step runs.

---

### Phase 7: Pinpoint Voice Pool (Kiro runs)

```powershell
# Create voice pool
aws pinpoint-sms-voice-v2 create-pool --origination-identity phone-8b753d69919447bf93e21e35e2363d09 --iso-country-code US --message-type TRANSACTIONAL --region us-east-1

# Enable international sending
aws pinpoint-sms-voice-v2 update-phone-number --phone-number-id phone-8b753d69919447bf93e21e35e2363d09 --international-sending-enabled --region us-east-1
```

---

### Phase 8: Bedrock Knowledge Bases + Agents (Kiro runs)

```powershell
# Step 1: Create OpenSearch Serverless collection for vector store
aws opensearchserverless create-collection --name wecare-digital-vectors --type VECTORSEARCH

# Step 2: Create Internal KB (admin tasks)
aws bedrock-agent create-knowledge-base --name wecare-digital-internal-kb --role-arn {KB_ROLE_ARN} --knowledge-base-configuration '{...}' --storage-configuration '{...}'

# Step 3: Create External KB (WhatsApp auto-reply)
aws bedrock-agent create-knowledge-base --name wecare-digital-external-kb --role-arn {KB_ROLE_ARN} --knowledge-base-configuration '{...}' --storage-configuration '{...}'

# Step 4: Create Internal Agent (FloatingAgent admin)
aws bedrock-agent create-agent --agent-name wecare-digital-internal-agent --foundation-model amazon.nova-lite-v1:0 --instruction "..." --agent-resource-role-arn {AGENT_ROLE_ARN}

# Step 5: Create External Agent (WhatsApp auto-reply)
aws bedrock-agent create-agent --agent-name wecare-digital-external-agent --foundation-model amazon.nova-lite-v1:0 --instruction "..." --agent-resource-role-arn {AGENT_ROLE_ARN}

# Step 6: Create agent aliases
aws bedrock-agent create-agent-alias --agent-id {INTERNAL_AGENT_ID} --agent-alias-name prod
aws bedrock-agent create-agent-alias --agent-id {EXTERNAL_AGENT_ID} --agent-alias-name prod
```

After creation, Kiro updates all Bedrock IDs in the codebase.

---

### Phase 9: SES Email Verification (Kiro runs)

```powershell
aws ses verify-email-identity --email-address one@wecare.digital --region us-east-1
```

> **User action:** Click the verification link sent to `one@wecare.digital`.

---

### Phase 10: Upload Static Assets to S3 (Kiro runs)

```powershell
# Upload logos, favicons, IVR audio, widget JS from old bucket or local
# These need to be provided or copied from old account
aws s3 sync ./assets/ s3://app.wecare.digital/stream/ --region us-east-1
```

> **User input needed:** Provide the static assets (logos, IVR audio, widget JS) or access to old S3 bucket to copy.

---

### Phase 11: Final Codebase Update (Kiro runs)

After all resources are created, Kiro updates remaining TBD values:
- New API Gateway ID in deploy scripts
- New Cognito IDs in frontend + backend config
- New Bedrock Agent/KB IDs in all files
- New Pinpoint Pool ID
- New AppSync URL
- Update `amplify_outputs.json` references

---

## Hardcoded Values — Files to Update

### 1. Account ID `809904170947` → `775261844268`

- `amplify/iam-policies.ts` — All IAM policy ARNs
- `amplify/backend-resources.ts` — SNS topic ARN
- `amplify/monitoring/alarms.ts` — Alarm SNS ARNs
- `amplify/functions/shared/utils/metrics.py` — SNS fallback ARN
- `scripts/deploy-wa-business-api.ps1` — ACCOUNT_ID variable
- `scripts/deploy-whatsapp-calling.ps1` — ACCOUNT variable
- `scripts/deploy-whatsapp-voice.ps1` — ACCOUNT_ID variable
- `scripts/policy-update.json` — All ARNs
- `src/pages/dashboard/index.tsx` — AWS_RESOURCES map (all accountId fields + ARNs)
- `README.md` — Account reference

### 2. S3 Bucket `auth.wecare.digital` → `app.wecare.digital`

- `amplify/storage/resource.ts`
- `amplify/iam-policies.ts`
- `amplify/functions/core/messages-read/resource.ts`
- `amplify/functions/messaging/whatsapp-template-management/resource.ts`
- `amplify/functions/messaging/whatsapp-voice/handler.py`
- `amplify/functions/messaging/whatsapp-calling/handler.py`
- `amplify/functions/messaging/whatsapp-calling/resource.ts`
- `scripts/deploy-whatsapp-voice.ps1`
- `scripts/deploy-whatsapp-calling.ps1`
- `scripts/policy-update.json`
- `src/pages/_app.tsx` — Logo, favicon, widget URLs
- `src/pages/index.tsx` — OG images, logo, widget script
- `src/pages/dashboard/index.tsx` — S3 ARN, references
- `src/pages/dm/whatsapp/calling.tsx` — IVR URL, S3 resource
- `src/pages/dm/whatsapp/[waId].tsx` — Media URL fallback
- `src/components/FloatingAgent.tsx` — Logo URL
- `src/components/Layout.tsx` — Sidebar logo
- `src/components/SEO.tsx` — DEFAULT_IMAGE

### 3. API Gateway → `api.wecare.digital`

- `src/config/constants.ts` — API_BASE
- `src/components/FloatingAgent.tsx` — API_BASE
- `src/pages/dashboard/index.tsx` — API_BASE + all webhook URLs + Airtel reference
- `src/pages/dm/whatsapp/calling.tsx` — WEBHOOK_CONFIG, API_BASE
- `src/pages/dm/whatsapp/webhooks.tsx` — Webhook URLs
- `src/pages/dm/sms/index.tsx` — API_BASE fallback
- `src/pages/dm/voice/index.tsx` — API_BASE fallback
- `src/pages/dm/voice-in/index.tsx` — API_BASE fallback
- `scripts/deploy-wa-business-api.ps1` — API_ID
- `scripts/deploy-whatsapp-calling.ps1` — API_ID
- `scripts/deploy-whatsapp-voice.ps1` — API_ID
- `scripts/test-voice-api.ps1` — Base URL
- `amplify/functions/payments/razorpay-webhook/handler.py` — Docstring
- `amplify/functions/operations/dlq-replay/resource.ts` — SQS URLs

### 4. WABA IDs

- `src/pages/dm/whatsapp/templates.tsx` — WABA_OPTIONS
- `src/api/client.ts` — WABA_IDS mapping
- `amplify/functions/messaging/whatsapp-template-management/handler.py` — DEFAULT_WABA_ID
- `amplify/iam-policies.ts` — Social messaging ARNs
- `README.md`

### 5. Phone Number IDs

- `src/config/constants.ts` — PAYMENT_CONFIG, WHATSAPP_PHONES
- `src/pages/dm/whatsapp/calling.tsx` — PHONE_NUMBERS
- `src/api/client.ts` — Channel status
- `amplify/functions/shared/config.ts` — WHATSAPP_CONFIG
- `amplify/functions/shared/utils/validator.py` — WHATSAPP_ALLOWLIST
- `amplify/functions/messaging/whatsapp-calling/handler.py`
- `amplify/functions/messaging/whatsapp-calling/resource.ts`
- `amplify/functions/messaging/whatsapp-voice/handler.py`
- `amplify/functions/messaging/whatsapp-voice/resource.ts`
- `amplify/functions/messaging/inbound-whatsapp-handler/resource.ts`
- `scripts/deploy-whatsapp-voice.ps1`

### 6. Meta WABA IDs + Phone IDs

- `src/pages/dm/whatsapp/calling.tsx` — metaId fields
- `src/pages/dashboard/index.tsx` — WABA details
- `README.md`

### 7. Cognito IDs (updated after Amplify deploy)

- `src/pages/_app.tsx` — userPoolId, userPoolClientId, identityPoolId
- `amplify/functions/shared/config.ts` — COGNITO_CONFIG
- `amplify/iam-policies.ts` — Cognito ARN
- `amplify/auth/resource.ts` — Comments
- `amplify_outputs.json` — Auto-generated
- `README.md`

### 8. Bedrock IDs (updated after Kiro creates agents/KBs)

- `src/components/FloatingAgent.tsx` — INTERNAL_AGENT_ID, INTERNAL_AGENT_ALIAS, INTERNAL_KB_ID
- `src/pages/dashboard/index.tsx` — DEFAULT_AI_CONFIG
- `src/pages/dm/whatsapp/ai-config.tsx` — External agent display
- `src/api/client.ts` — AI_CONFIG, channel status
- `amplify/functions/shared/config.ts` — BEDROCK_CONFIG
- `amplify/functions/ai/ai-generate-response/handler.py`
- `amplify/functions/ai/ai-query-kb/handler.py`
- `amplify/functions/ai/ai-query-kb/resource.ts`
- `amplify/functions/ai/agent-action-group/handler.py`
- `amplify/functions/ai/agent-action-group/resource.ts`

### 9. Pinpoint Resources (updated after Kiro creates pool)

- `src/pages/dashboard/index.tsx` — Pool ID, protect config, phone numbers
- `src/api/client.ts` — poolId
- `amplify/iam-policies.ts` — Pool ARN

### 10. SQS Queue URLs (account ID auto-updated in Phase 1)

- `amplify/functions/operations/dlq-replay/resource.ts`
- `amplify/functions/operations/bulk-job-create/resource.ts`
- `amplify/functions/operations/bulk-job-control/resource.ts`
- `amplify/iam-policies.ts`

---

## Migration Checklist

### Pre-Deploy
- [x] Create new AWS account (`775261844268`)
- [x] Configure AWS CLI credentials
- [x] Migrate domain `wecare.digital` to new account
- [x] Link WABAs in AWS EUM (2 WABAs, 2 phone numbers)
- [x] Provision Pinpoint toll-free number
- [ ] Phase 1: Kiro updates codebase with all known new values

### Amplify Deploy
- [ ] Phase 2: Kiro runs `npx ampx sandbox`
- [ ] Phase 2: Kiro reads new Cognito/AppSync IDs and updates codebase

### Infrastructure (all Kiro autopilot)
- [ ] Phase 3: Kiro creates IAM Lambda role + attaches policies
- [ ] Phase 4: Kiro deploys all 35 Lambda functions via CLI
- [ ] Phase 5: Kiro creates API Gateway HTTP API
- [ ] Phase 5: Kiro requests ACM certificate for `api.wecare.digital`
- [ ] Phase 5: Kiro adds DNS validation record
- [ ] Phase 5: Kiro creates custom domain + API mapping
- [ ] Phase 5: Kiro creates all routes + Lambda integrations
- [ ] Phase 5: Kiro adds Route 53 A record for `api.wecare.digital`
- [ ] Phase 6: Kiro creates Secrets Manager entries (user provides values)
- [ ] Phase 7: Kiro creates Pinpoint voice pool
- [x] Phase 8: Kiro creates Bedrock KBs + Agents ✅
- [ ] Phase 9: Kiro triggers SES email verification

### User Actions Required
- [ ] Provide Meta System User Token value (for Secrets Manager)
- [ ] Provide Meta App Secret value (for Secrets Manager)
- [ ] Provide Airtel IQ credentials (for Secrets Manager)
- [ ] Click SES verification email for `one@wecare.digital`
- [ ] Provide static assets (logos, IVR audio, widget JS) or old S3 access
- [ ] Update Meta Dashboard webhook URLs to `https://api.wecare.digital/whatsapp-calling`
- [ ] Update Razorpay Dashboard webhook URL to `https://api.wecare.digital/razorpay-webhook`
- [ ] Update Airtel Dashboard webhook URLs

### Final
- [ ] Phase 10: Kiro uploads static assets to S3
- [ ] Phase 11: Kiro updates all remaining TBD values in codebase
- [ ] Test all endpoints
