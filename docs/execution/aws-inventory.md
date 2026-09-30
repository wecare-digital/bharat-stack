# AWS account inventory

Generated 2026-09-30T22:45:19.256384+00:00 · account `775261844268` · `us-east-1` (+ ap-south-1) · regenerate with `python scripts/aws_account_inventory.py`

This file supersedes every dated resource count in the steering files. Machine-readable companion: `aws-inventory.json`. Secret **names** and metadata are recorded; no secret value is ever read. Lambda environment variable **names** are recorded, values never are.

Collector errors: **0** (a non-zero count makes this inventory PARTIAL, not authoritative).

## Headline counts

| Resource | Count |
|---|---:|
| Lambda functions | 66 |
| — with a `live` alias | 59 |
| HTTP APIs | 1 |
| REST APIs | 0 |
| HTTP API routes | 359 |
| API authorizers | 0 |
| Routes with AuthorizationType=NONE | 359 |
| DynamoDB tables | 80 |
| SQS queues | 10 |
| EventBridge rules | 6 |
| EventBridge Scheduler schedules | 1 |
| Secrets Manager secrets | 31 |
| — scheduled for deletion | 5 |
| Cognito user pools | 2 |
| S3 buckets | 6 |
| CloudFront distributions | 2 |
| WAF web ACLs (regional) | 0 |
| WAF web ACLs (CloudFront) | 0 |
| Route 53 hosted zones | 1 |
| CloudWatch alarms | 66 |
| CloudWatch log groups | 82 |
| CloudFormation stacks | 1 |
| Amplify apps | 1 |

## Lambda

Runtimes: {'python3.12': 65, None: 1}  ·  package types: {'Zip': 65, 'Image': 1}

SnapStart: {'None': 66}

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

- **zllr9lrg7j** `wecare-digital-api` — 359 routes, 0 authorizers, stages: ['prod']

Routes with an authorizer attached: **0**

## DynamoDB

Empty tables (64): `stack-wecare-digital-AIInteractionsTable`, `stack-wecare-digital-AIProviderPolicyTable`, `stack-wecare-digital-AdClickAttributionTable`, `stack-wecare-digital-AgentApprovalsTable`, `stack-wecare-digital-AmendmentHistoryTable`, `stack-wecare-digital-AppointmentTable`, `stack-wecare-digital-AutomationRulesTable`, `stack-wecare-digital-BulkJobsTable`, `stack-wecare-digital-BulkRecipientsTable`, `stack-wecare-digital-CallNotificationsTable`, `stack-wecare-digital-CatalogCacheTable`, `stack-wecare-digital-ConversationHistoryTable`, `stack-wecare-digital-ConversationMetaTable`, `stack-wecare-digital-CrmActivities`, `stack-wecare-digital-CrmLeads`, `stack-wecare-digital-CrmOpportunities`, `stack-wecare-digital-CrmPipelines`, `stack-wecare-digital-CrmStages`, `stack-wecare-digital-DLQMessagesTable`, `stack-wecare-digital-DLTTemplates`, `stack-wecare-digital-DocumentHistoryTable`, `stack-wecare-digital-DownloadGrantsTable`, `stack-wecare-digital-EnterpriseAssistTable`, `stack-wecare-digital-FaqTable`, `stack-wecare-digital-FlowDraftTable`, `stack-wecare-digital-FlowLogTable`, `stack-wecare-digital-FlowRegistryTable`, `stack-wecare-digital-FlowSubmissionTable`, `stack-wecare-digital-InvoiceAssetsTable`, `stack-wecare-digital-InvoiceDeliveryLogTable`, `stack-wecare-digital-InvoiceItemsTable`, `stack-wecare-digital-InvoiceSequenceTable`, `stack-wecare-digital-InvoicesTable`, `stack-wecare-digital-MediaFilesTable`, `stack-wecare-digital-NotificationAttempts`, `stack-wecare-digital-NotificationDeliveries`, `stack-wecare-digital-NotificationEvents`, `stack-wecare-digital-NotificationOutbox`, `stack-wecare-digital-OBDCampaigns`, `stack-wecare-digital-OrderTable`, `stack-wecare-digital-PartnerLedger`, `stack-wecare-digital-PartnerWallet`, `stack-wecare-digital-PaymentAttemptsTable`, `stack-wecare-digital-PaymentsTable`, `stack-wecare-digital-PstnSoftphoneSessions`, `stack-wecare-digital-PushTokensTable`, `stack-wecare-digital-RequestStatusHistoryTable`, `stack-wecare-digital-ReviewTable`, `stack-wecare-digital-RxSlotTable`, `stack-wecare-digital-ScheduledMessagesTable`, `stack-wecare-digital-SecureFilesTable`, `stack-wecare-digital-SmsOutboundTable`, `stack-wecare-digital-SubmitRequestsTable`, `stack-wecare-digital-TemplateAnalyticsTable`, `stack-wecare-digital-UsersTable`, `stack-wecare-digital-VoiceAwsTable`, `stack-wecare-digital-VoiceCalls`, `stack-wecare-digital-WhatsAppCallingTable`, `stack-wecare-digital-WhatsAppGroupTable`, `stack-wecare-digital-WhatsAppPhonesTable`, `stack-wecare-digital-WhatsAppVoiceTable`, `stack-wecare-digital-WixOrderIds`, `stack-wecare-digital-WixOrdersCache`, `stack-wecare-digital-WixProductsCache`

Without point-in-time recovery (7): `stack-wecare-digital-CatalogCacheTable`, `stack-wecare-digital-PstnSoftphoneSessions`, `stack-wecare-digital-RateLimitTable`, `stack-wecare-digital-SiteLanguageCache`, `stack-wecare-digital-WebhookDedup`, `stack-wecare-digital-WixOrdersCache`, `stack-wecare-digital-WixProductsCache`

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
| `wecare-blog-ingest` | 0 | 0 | `wecare-blog-ingest-dlq` | 3 |
| `wecare-blog-ingest-dlq` | 0 | 0 | — | — |
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

EventBridge Scheduler schedules: 1 ['wecare-seo-freshness-daily']

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
| `wecare/config/webhook-registry` | 2026-09-29 | no | — |
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

- `us-east-1_46ULYuukt` **WECARE.DIGITAL-CUSTOMERS** — users≈1, MFA=OFF, advanced_security=None, deletion_protection=ACTIVE
  - clients: ['wecare-customer-whatsapp-otp']
  - groups: ['Partner']
  - lambda triggers: ['CreateAuthChallenge', 'DefineAuthChallenge', 'VerifyAuthChallengeResponse']
- `us-east-1_cSx0RHCIR` **WECARE.DIGITAL** — users≈1, MFA=OPTIONAL, advanced_security=None, deletion_protection=ACTIVE
  - clients: ['stack-wecare-digital-web']
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
| `cdk-hnb659fds-assets-775261844268-us-east-1` | us-east-1 | aws:kms | yes | Enabled | no |
| `wecare-cloudtrail-775261844268` | us-east-1 | AES256 | **no** | Enabled | no |
| `wecare-credential-backups-775261844268` | us-east-1 | aws:kms | yes | Enabled | no |
| `wecare-digital-get` | us-east-1 | AES256 | yes | Suspended | no |
| `wecare-digital-mta-sts` | us-east-1 | AES256 | yes | — | no |
| `wecare-maintenance-reports-775261844268` | us-east-1 | aws:kms | yes | Enabled | no |

## CloudFront

- `E1SZBXLQ4XNLJ7` djbi65ldve9va.cloudfront.net aliases=['mta-sts.wecare.digital'] status=Deployed enabled=True web_acl=**none**
  - origins: ['wecare-digital-mta-sts.s3.us-east-1.amazonaws.com']
- `E2GP22R4BIFGQ3` d1kf2rchz7yras.cloudfront.net aliases=[] status=Deployed enabled=True web_acl=**none**
  - origins: ['wecare-digital-get.s3.us-east-1.amazonaws.com']

## WAF

- **REGIONAL**: 0 web ACLs
- **CLOUDFRONT**: 0 web ACLs

## Route 53

- `wecare.digital.` (Z03939753QJGZ6ZD6BXO8) — 30 records, MX=True, types={'CNAME': 15, 'TXT': 7, 'A': 3, 'AAAA': 2, 'MX': 1, 'NS': 1, 'SOA': 1}

## CloudWatch

- alarms: 66 (composite 0)
- in ALARM: (none)
- INSUFFICIENT_DATA: 0
- alarms with no action: 0
- dashboards: ['wecare-platform-health']
- log groups: 82, stored 0.57 GB
- log groups with no retention: 0

## IaC

CloudFormation stacks:

- `CDKToolkit` CREATE_COMPLETE updated=2026-02-11 drift=NOT_CHECKED

Amplify:

- `d22dm4b0jn71jw` **wecare.digital** platform=WEB custom_rules=146 repo=https://github.com/wecare-digital/wecare-digital
  - branch `stack` stage=PRODUCTION auto_build=True
    - job 1160 SUCCEED commit `6a5d6e9ea6fe` 2026-09-30T22:20:54
    - job 1159 SUCCEED commit `c082d5867240` 2026-09-30T22:16:25
    - job 1158 SUCCEED commit `394d8e39da97` 2026-09-30T22:11:58

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

- `d22dm4b0jn71jw` → NOT_ASSOCIATED ['']

