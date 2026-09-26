# AWS account inventory

Generated 2026-09-26T06:08:00.092204+00:00 · account `775261844268` · `us-east-1` (+ ap-south-1) · regenerate with `python scripts/aws_account_inventory.py`

This file supersedes every dated resource count in the steering files. Machine-readable companion: `aws-inventory.json`. Secret **names** and metadata are recorded; no secret value is ever read. Lambda environment variable **names** are recorded, values never are.

Collector errors: **0** (a non-zero count makes this inventory PARTIAL, not authoritative).

## Headline counts

| Resource | Count |
|---|---:|
| Lambda functions | 65 |
| — with a `live` alias | 58 |
| HTTP APIs | 1 |
| REST APIs | 0 |
| HTTP API routes | 361 |
| API authorizers | 0 |
| Routes with AuthorizationType=NONE | 361 |
| DynamoDB tables | 79 |
| SQS queues | 8 |
| EventBridge rules | 6 |
| EventBridge Scheduler schedules | 0 |
| Secrets Manager secrets | 31 |
| — scheduled for deletion | 5 |
| Cognito user pools | 2 |
| S3 buckets | 6 |
| CloudFront distributions | 3 |
| WAF web ACLs (regional) | 1 |
| WAF web ACLs (CloudFront) | 1 |
| Route 53 hosted zones | 1 |
| CloudWatch alarms | 41 |
| CloudWatch log groups | 81 |
| CloudFormation stacks | 7 |
| Amplify apps | 1 |

## Lambda

Runtimes: {'python3.12': 64, None: 1}  ·  package types: {'Zip': 64, 'Image': 1}

SnapStart: {'None': 65}

Alias read errors: 0

**Without a `live` alias (7)** — `$LATEST` reaches production directly for these:

- `wecare-ad-attribution`
- `wecare-docs-scraper`
- `wecare-get-miss-redirect`
- `wecare-partner-token-refresh`
- `wecare-seo-tools`
- `wecare-sla-engine`
- `wecare-url-shortener`

## API Gateway

- **zllr9lrg7j** `wecare-digital-api` — 361 routes, 0 authorizers, stages: ['prod']

Routes with an authorizer attached: **0**

## DynamoDB

Empty tables (65): `stack-wecare-digital-AIInteractionsTable`, `stack-wecare-digital-AIProviderPolicyTable`, `stack-wecare-digital-AdClickAttributionTable`, `stack-wecare-digital-AgentApprovalsTable`, `stack-wecare-digital-AmendmentHistoryTable`, `stack-wecare-digital-AppointmentTable`, `stack-wecare-digital-AutomationRulesTable`, `stack-wecare-digital-BulkJobsTable`, `stack-wecare-digital-BulkRecipientsTable`, `stack-wecare-digital-CallNotificationsTable`, `stack-wecare-digital-CatalogCacheTable`, `stack-wecare-digital-ConversationHistoryTable`, `stack-wecare-digital-ConversationMetaTable`, `stack-wecare-digital-CrmActivities`, `stack-wecare-digital-CrmLeads`, `stack-wecare-digital-CrmOpportunities`, `stack-wecare-digital-CrmPipelines`, `stack-wecare-digital-CrmStages`, `stack-wecare-digital-DLQMessagesTable`, `stack-wecare-digital-DLTTemplates`, `stack-wecare-digital-DocumentHistoryTable`, `stack-wecare-digital-DocumentTable`, `stack-wecare-digital-DownloadGrantsTable`, `stack-wecare-digital-EnterpriseAssistTable`, `stack-wecare-digital-FaqTable`, `stack-wecare-digital-FlowDraftTable`, `stack-wecare-digital-FlowLogTable`, `stack-wecare-digital-FlowRegistryTable`, `stack-wecare-digital-FlowSubmissionTable`, `stack-wecare-digital-InvoiceAssetsTable`, `stack-wecare-digital-InvoiceDeliveryLogTable`, `stack-wecare-digital-InvoiceItemsTable`, `stack-wecare-digital-InvoiceSequenceTable`, `stack-wecare-digital-InvoicesTable`, `stack-wecare-digital-MediaFilesTable`, `stack-wecare-digital-NotificationAttempts`, `stack-wecare-digital-NotificationDeliveries`, `stack-wecare-digital-NotificationEvents`, `stack-wecare-digital-NotificationOutbox`, `stack-wecare-digital-OBDCampaigns`, `stack-wecare-digital-OrderTable`, `stack-wecare-digital-PartnerLedger`, `stack-wecare-digital-PartnerWallet`, `stack-wecare-digital-PaymentsTable`, `stack-wecare-digital-PstnSoftphoneSessions`, `stack-wecare-digital-PushTokensTable`, `stack-wecare-digital-RequestStatusHistoryTable`, `stack-wecare-digital-ReviewTable`, `stack-wecare-digital-RxSlotTable`, `stack-wecare-digital-ScheduledMessagesTable`, `stack-wecare-digital-SecureFilesTable`, `stack-wecare-digital-SeoToolsTable`, `stack-wecare-digital-SmsOutboundTable`, `stack-wecare-digital-SubmitRequestsTable`, `stack-wecare-digital-TemplateAnalyticsTable`, `stack-wecare-digital-UsersTable`, `stack-wecare-digital-VoiceAwsTable`, `stack-wecare-digital-VoiceCalls`, `stack-wecare-digital-WhatsAppCallingTable`, `stack-wecare-digital-WhatsAppGroupTable`, `stack-wecare-digital-WhatsAppPhonesTable`, `stack-wecare-digital-WhatsAppVoiceTable`, `stack-wecare-digital-WixOrderIds`, `stack-wecare-digital-WixOrdersCache`, `stack-wecare-digital-WixProductsCache`

Without point-in-time recovery (12): `stack-wecare-digital-CatalogCacheTable`, `stack-wecare-digital-DLQMessagesTable`, `stack-wecare-digital-DownloadGrantsTable`, `stack-wecare-digital-FlowDraftTable`, `stack-wecare-digital-PstnSoftphoneSessions`, `stack-wecare-digital-RateLimitTable`, `stack-wecare-digital-SecureFilesTable`, `stack-wecare-digital-SiteLanguageCache`, `stack-wecare-digital-WebhookDedup`, `stack-wecare-digital-WhatsAppPhonesTable`, `stack-wecare-digital-WixOrdersCache`, `stack-wecare-digital-WixProductsCache`

With streams (1): `stack-wecare-digital-VoiceCDRTable`

## SQS

| Queue | visible | in flight | DLQ target | maxReceive |
|---|---:|---:|---|---:|
| `stack-wecare-digital-bulk-dlq` | 0 | 0 | — | — |
| `stack-wecare-digital-bulk-queue` | 0 | 0 | `stack-wecare-digital-bulk-dlq` | 3 |
| `stack-wecare-digital-inbound-dlq` | 0 | 0 | — | — |
| `stack-wecare-digital-notification-dlq` | 0 | 0 | — | — |
| `stack-wecare-digital-notification-queue` | 0 | 0 | `stack-wecare-digital-notification-dlq` | 3 |
| `stack-wecare-digital-outbound-dlq` | 0 | 0 | — | — |
| `wecare-eventbridge-dlq` | 0 | 0 | — | — |
| `wecare-lambda-async-dlq` | 0 | 0 | — | — |

Queues with no redrive policy and not DLQ-named: (none)

## EventBridge

- bus `default` — 6 rules
  - `AWSUserNotificationsManagedRule-adi3lsr` ENABLED pattern -> no target [no-dlq]
  - `wecare-amplify-build-failed` ENABLED pattern -> stack-wecare-digital [no-dlq]
  - `wecare-docs-scraper-daily` ENABLED rate(1 day) -> wecare-docs-scraper [no-dlq]
  - `wecare-media-cleanup-daily` ENABLED rate(1 day) -> wecare-media-cleanup [dlq]
  - `wecare-partner-token-refresh-daily` ENABLED rate(1 day) -> wecare-partner-token-refresh [no-dlq]
  - `wecare-scheduled-messages-trigger` ENABLED rate(5 minutes) -> wecare-scheduled-messages [dlq]

EventBridge Scheduler schedules: 0 []

Disabled rules: (none)

## Secrets Manager

Metadata only. No value was read.

| Secret | last changed | rotation | scheduled deletion |
|---|---|---|---|
| `wecare/ads/account-registry` | 2026-09-18 | no | — |
| `wecare/agent-connector-token` | 2026-07-20 | no | — |
| `wecare/airtel-iq` | 2026-09-20 | no | 2026-09-20 |
| `wecare/airtel/c2c` | 2026-09-20 | no | 2026-09-20 |
| `wecare/airtel/obd` | 2026-09-20 | no | 2026-09-20 |
| `wecare/airtel/sms` | 2026-09-20 | no | 2026-09-20 |
| `wecare/aws/iam-access-keys` | 2026-09-18 | no | — |
| `wecare/backup/recovery-passphrase` | 2026-09-19 | no | — |
| `wecare/bing/api` | 2026-09-18 | no | — |
| `wecare/config/webhook-registry` | 2026-09-19 | no | — |
| `wecare/flow-private-key` | 2026-02-23 | no | — |
| `wecare/github-connection` | 2026-09-18 | no | — |
| `wecare/github-pat` | 2026-08-26 | no | — |
| `wecare/google-api-key` | 2026-09-18 | no | — |
| `wecare/google-maps` | 2026-09-18 | no | — |
| `wecare/google-maps-server` | 2026-09-26 | no | — |
| `wecare/google/ads` | 2026-09-17 | no | — |
| `wecare/google/cloud` | 2026-09-19 | no | — |
| `wecare/meta-system-user-token` | 2026-09-20 | no | — |
| `wecare/meta/payments` | 2026-09-18 | no | — |
| `wecare/openai/api` | 2026-09-18 | no | — |
| `wecare/plivo` | 2026-09-19 | no | — |
| `wecare/plivo-answer` | 2026-09-19 | no | — |
| `wecare/plivo/api` | 2026-09-18 | no | — |
| `wecare/razorpay-webhook` | 2026-07-02 | no | — |
| `wecare/razorpay/api` | 2026-09-19 | no | — |
| `wecare/seo/google-oauth` | 2026-09-19 | no | — |
| `wecare/sinch/rcs` | 2026-05-05 | no | — |
| `wecare/sinch/sms` | 2026-09-20 | no | 2026-09-20 |
| `wecare/truecaller` | 2026-09-19 | no | — |
| `wecare/wix/headless-api-key` | 2026-09-26 | no | — |

## Cognito

- `us-east-1_46ULYuukt` **WECARE.DIGITAL-CUSTOMERS** — users≈1, MFA=OFF, advanced_security=None, deletion_protection=INACTIVE
  - clients: ['wecare-customer-whatsapp-otp']
  - groups: ['Partner']
  - lambda triggers: ['CreateAuthChallenge', 'DefineAuthChallenge', 'VerifyAuthChallengeResponse']
- `us-east-1_cSx0RHCIR` **WECARE.DIGITAL** — users≈1, MFA=OPTIONAL, advanced_security=None, deletion_protection=ACTIVE
  - clients: ['stack-wecare-digital-web', 'WECARE.DIGITAL']
  - groups: ['Admin', 'Operator', 'Partner', 'Viewer']
  - lambda triggers: ['CustomMessage']

Identity pools: 1

## SES

### us-east-1 — production_access=True, sending=True, quota={'Max24HourSend': 50000.0, 'MaxSendRate': 14.0, 'SentLast24Hours': 0.0}

- `one@wecare.digital` (EMAIL_ADDRESS) verified=True dkim=SUCCESS/True mail_from=None/None
- `wecare.digital` (DOMAIN) verified=True dkim=SUCCESS/True mail_from=None/None

Configuration sets: ['wecare-digital']

### ap-south-1 — production_access=False, sending=True, quota={'Max24HourSend': 200.0, 'MaxSendRate': 1.0, 'SentLast24Hours': 0.0}


Configuration sets: []

## S3

| Bucket | region | encryption | PAB all | versioning | public policy |
|---|---|---|---|---|---|
| `app.wecare.digital` | us-east-1 | AES256 | yes | Enabled | no |
| `cdk-hnb659fds-assets-775261844268-us-east-1` | us-east-1 | aws:kms | yes | Enabled | no |
| `wecare-credential-backups-775261844268` | us-east-1 | aws:kms | yes | Enabled | no |
| `wecare-digital-get` | us-east-1 | AES256 | yes | Enabled | no |
| `wecare-digital-mta-sts` | us-east-1 | AES256 | yes | — | no |
| `wecare-maintenance-reports-775261844268` | us-east-1 | aws:kms | yes | Enabled | no |

## CloudFront

- `E1SZBXLQ4XNLJ7` djbi65ldve9va.cloudfront.net aliases=['mta-sts.wecare.digital'] status=Deployed enabled=True web_acl=**none**
  - origins: ['wecare-digital-mta-sts.s3.us-east-1.amazonaws.com']
- `E2GP22R4BIFGQ3` d1kf2rchz7yras.cloudfront.net aliases=[] status=Deployed enabled=True web_acl=**none**
  - origins: ['wecare-digital-get.s3.us-east-1.amazonaws.com']
- `ERCXSFDL0VM8X` d1c2t5x9nvib1v.cloudfront.net aliases=['app.wecare.digital'] status=Deployed enabled=True web_acl=**none**
  - origins: ['app.wecare.digital.s3.us-east-1.amazonaws.com']

## WAF

- **REGIONAL**: 1 web ACLs
  - `wecare-cognito-waf` associated: ['arn:aws:cognito-idp:us-east-1:775261844268:userpool/us-east-1_46ULYuukt', 'arn:aws:cognito-idp:us-east-1:775261844268:userpool/us-east-1_cSx0RHCIR']
- **CLOUDFRONT**: 1 web ACLs
  - `wecare-amplify-waf` associated: []

## Route 53

- `wecare.digital.` (Z03939753QJGZ6ZD6BXO8) — 41 records, MX=True, types={'CNAME': 21, 'A': 7, 'TXT': 7, 'AAAA': 3, 'MX': 1, 'NS': 1, 'SOA': 1}

## CloudWatch

- alarms: 41 (composite 0)
- in ALARM: (none)
- INSUFFICIENT_DATA: 0
- alarms with no action: 0
- dashboards: ['wecare-platform-health']
- log groups: 81, stored 0.16 GB
- log groups with no retention: 0

## IaC

CloudFormation stacks:

- `CDKToolkit` CREATE_COMPLETE updated=2026-02-11 drift=NOT_CHECKED
- `wecare-elevenlabs-call-hooks` UPDATE_COMPLETE updated=2026-09-19 drift=NOT_CHECKED
- `wecare-elevenlabs-init` CREATE_COMPLETE updated=2026-09-19 drift=NOT_CHECKED
- `wecare-elevenlabs-mcp` UPDATE_COMPLETE updated=2026-09-19 drift=NOT_CHECKED
- `wecare-elevenlabs-mcp-enable` UPDATE_COMPLETE updated=2026-09-19 drift=NOT_CHECKED
- `wecare-elevenlabs-postcall-sms` CREATE_COMPLETE updated=2026-09-19 drift=NOT_CHECKED
- `wecare-temp-code-inspector` CREATE_COMPLETE updated=2026-09-19 drift=NOT_CHECKED

Amplify:

- `d22dm4b0jn71jw` **wecare.digital** platform=WEB custom_rules=23 repo=https://github.com/wecare-digital/bharat-stack
  - branch `chatgpt/grahak-os-color-unify-20260918` stage=DEVELOPMENT auto_build=False
    - job 3 SUCCEED commit `HEAD` 2026-09-18T11:31:52
    - job 2 FAILED commit `HEAD` 2026-09-18T11:23:06
    - job 1 FAILED commit `HEAD` 2026-09-18T11:18:14
  - branch `chatgpt/grahak-os-final-polish-20260918` stage=DEVELOPMENT auto_build=False
    - job 2 SUCCEED commit `HEAD` 2026-09-18T06:09:27
    - job 1 FAILED commit `HEAD` 2026-09-18T06:00:01
  - branch `chatgpt/grahak-os-five-fixes-20260918` stage=DEVELOPMENT auto_build=False
    - job 2 SUCCEED commit `HEAD` 2026-09-18T08:17:44
    - job 1 FAILED commit `HEAD` 2026-09-18T07:55:52
  - branch `chatgpt/grahak-os-route-header-20260917` stage=DEVELOPMENT auto_build=False
    - job 2 SUCCEED commit `HEAD` 2026-09-18T00:35:05
    - job 1 FAILED commit `HEAD` 2026-09-18T00:24:30
  - branch `chatgpt/grahak-os-trust-strip-20260918` stage=DEVELOPMENT auto_build=False
    - job 4 SUCCEED commit `HEAD` 2026-09-18T02:50:23
    - job 3 FAILED commit `HEAD` 2026-09-18T02:43:09
    - job 2 SUCCEED commit `HEAD` 2026-09-18T02:33:01
  - branch `chatgpt/grahak-os-widgets-footer-20260918` stage=DEVELOPMENT auto_build=False
    - job 2 SUCCEED commit `HEAD` 2026-09-18T04:37:39
    - job 1 FAILED commit `HEAD` 2026-09-18T04:07:09
  - branch `chatgpt/meta-icon-s3-20260918` stage=DEVELOPMENT auto_build=False
    - job 2 SUCCEED commit `HEAD` 2026-09-18T10:17:18
    - job 1 FAILED commit `HEAD` 2026-09-18T10:08:45
  - branch `chatgpt/meta-icon-s3-latest-20260918` stage=DEVELOPMENT auto_build=False
    - job 1 SUCCEED commit `HEAD` 2026-09-18T10:25:29
  - branch `stack` stage=PRODUCTION auto_build=True
    - job 910 SUCCEED commit `9b5d9aefb8e3` 2026-09-26T06:06:50
    - job 909 SUCCEED commit `df5ea8348bc0` 2026-09-26T05:59:57
    - job 908 SUCCEED commit `869760f7d167` 2026-09-26T05:52:06

## Cross-service checks

Defects that are invisible in any single service listing.

**DLQs with no CloudWatch alarm (0)** — messages can pile up unobserved:

- `(none)`

**Alarms watching a queue that does not exist (0)** — these can never fire:

- queue `(none)` watched by []

**Alarms whose dimension names a resource that does not exist (0)** — same class, across every enumerable dimension:

- `(none)` watched by []

**Regional WAF web ACLs associated with nothing (0)**:

- `(none)`

Amplify WAF association (CloudFront-scope ACLs cannot be queried from the WAF side, so the app is asked directly):

- `d22dm4b0jn71jw` → ASSOCIATION_SUCCESS ['wecare-amplify-waf', 'b4d41adc-d1ad-4639-9403-00e7df7b3741']

