# AWS Cost Control

How WECARE.DIGITAL keeps the Amplify Gen 2 backend cheap and predictable. Optional
paid services are **off by default** and gated behind feature flags read by
`amplify/functions/shared/lambda_utils/cost_flags.py` (`is_enabled()` / `all_flags()`).

## Current resources in the repo

| Resource | Where | Required? | Cost risk | Notes |
|---|---|---|---|---|
| Lambda (Python) | `amplify/functions/**` | Required | Low | Pay-per-invoke |
| DynamoDB tables | `amplify/data/resource.ts` | Required | Low | `PAY_PER_REQUEST` (on-demand) |
| AppSync / Data | `amplify/data/resource.ts` | Required | Low | userPool auth |
| Cognito | `amplify/auth/resource.ts` | Required | Low | Admin auth |
| S3 | `amplify/storage/resource.ts` (`app.wecare.digital`) | Required | Low | Media + assets; add lifecycle rules |
| SQS / DLQ | `amplify/backend-resources.ts` | Required where present | Low | Inbound/outbound/bulk DLQs |
| CloudWatch Logs | `backend-resources.ts` | Required | Low | 3-month retention |
| CloudWatch Alarms (critical) | `backend-resources.ts` | Required | Low | Errors on critical Lambdas |
| **WAF (WebhookWAF)** | `backend-resources.ts` | Optional | **Medium** | See WAF section below |

## Optional resources — feature flags

Each is disabled unless its env flag is `true` (see `cost_flags.py`).

| Flag | Service | Cost risk | Enable when | Disable / safer alternative |
|---|---|---|---|---|
| `ENABLE_WAF` | AWS WAF v2 | Medium | Under active webhook abuse / DDoS | Use Lambda-side rate limiting + signature checks |
| `ENABLE_CLOUDFRONT` | CloudFront | Medium | Global static caching needed | Serve via Amplify hosting / S3 directly |
| `ENABLE_STEP_FUNCTIONS` | Step Functions | Medium | Long multi-step orchestration | Chained Lambda + DynamoDB state |
| `ENABLE_ATHENA_ANALYTICS` | Athena | High | Ad-hoc SQL over large logs | Pre-aggregate in DynamoDB / CloudWatch |
| `ENABLE_GLUE` | Glue | High | ETL catalog needed | CSV import scripts |
| `ENABLE_TEXTRACT_IMPORT` | Textract | High | OCR of pricing PDFs | **CSV import first** |
| `ENABLE_BEDROCK_ASSIST` | Bedrock | High | AI assist explicitly wanted | Keep disabled; never send PII |
| `ENABLE_XRAY` | X-Ray | Medium | Deep tracing during incident | CloudWatch logs + structured logging |
| `ENABLE_ADVANCED_CLOUDWATCH_DASHBOARD` | CW dashboards / metric filters | Medium | Ops review period | Basic alarms only |
| `ENABLE_RAW_WEBHOOK_ARCHIVE` | S3 raw payload archive | Medium | Debugging webhook issues | Masked metadata logs only |

## WAF (why it is treated as optional)

`backend-resources.ts` currently creates a `WebhookWAF` (`wafv2.CfnWebACL`) with a
rate-limit rule for webhook endpoints. WAF has an hourly + per-request cost.

- **Current deployed behavior:** the WAF is created and associated with webhook
  endpoints (rate limiting).
- **Policy:** future WAF creation/config changes must be wrapped with `ENABLE_WAF`.
  Do **not** delete the WAF blindly — removing it on a live deploy drops webhook
  rate-limiting. Coordinate before flipping the flag off.
- **Cost risk:** Medium (Web ACL hourly + per-request). Safer alternative:
  Lambda-side rate limiting (`lambda_utils/rate_limit.py`) + HMAC signature
  verification, which already run regardless of WAF.
- **Local build:** the build must not depend on WAF being present.

## Standing cost notes

- **DynamoDB:** all tables use `PAY_PER_REQUEST`; no provisioned capacity.
- **CloudWatch retention:** log groups default to 3 months; do not raise without reason.
- **S3 lifecycle:** add expiry rules for `stack/whatsapp-media/downloads/` and
  `resumable/` staging keys; raw archives (if ever enabled) must have lifecycle + encryption.
- **Bedrock / Textract / Athena:** highest cost; keep disabled. Never send PII to
  Bedrock; add redaction before enabling.

## When to enable / disable
Enable a paid resource only for a defined need and time window; disable immediately
after. The UI Cost Controls page surfaces `all_flags()` and warns before enabling.
