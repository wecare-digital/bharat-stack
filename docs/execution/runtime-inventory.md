# Runtime inventory

Generated 2026-09-21T07:28:20+00:00 · `us-east-1` · regenerate with `python scripts/generate_runtime_inventory.py`

Machine-readable companion: `runtime-inventory.json`. Environment variable
**names** are recorded, values never are.

| Count | |
|---|---:|
| Lambda functions | 58 |
| with a `live` alias | 49 |
| HTTP APIs | 1 |
| Routes | 326 |
| DynamoDB tables | 66 |

## Anomalies

Each list is a question to answer, not automatically a defect.

### Live functions absent from the deploy map — cannot be patched by the standard path

- `wecare-docs-scraper` — **expected**: PackageType=Image; ships via .github/workflows/docs-scraper-deploy.yml
- `wecare-seo-tools` — **expected**: different in-zip layout; scripts/deploy_seo_tools.py owns it with its table and IAM policy

Every entry above is a documented exception.

### Functions with routes but no `live` alias — `$LATEST` reaches production directly

- `wecare-marketing-ads`
- `wecare-partner-onboarding`
- `wecare-seo-tools`

### Routes whose integration is unqualified — bypasses the version/alias model

- `zllr9lrg7j OPTIONS /partners/billing/settings -> wecare-partner-onboarding`
- `zllr9lrg7j OPTIONS /partners/billing/analytics -> wecare-partner-onboarding`
- `zllr9lrg7j OPTIONS /partners/send -> wecare-partner-onboarding`
- `zllr9lrg7j GET /partners/billing/analytics -> wecare-partner-onboarding`
- `zllr9lrg7j GET /partners/messages -> wecare-partner-onboarding`
- `zllr9lrg7j GET /partners/tenants -> wecare-partner-onboarding`
- `zllr9lrg7j POST /partners/billing/topup -> wecare-partner-onboarding`
- `zllr9lrg7j DELETE /partners/tenants -> wecare-partner-onboarding`
- `zllr9lrg7j OPTIONS /partners/embedded-signup -> wecare-partner-onboarding`
- `zllr9lrg7j POST /partners/billing/settings -> wecare-partner-onboarding`
- `zllr9lrg7j GET /partners/me -> wecare-partner-onboarding`
- `zllr9lrg7j OPTIONS /partners/messages -> wecare-partner-onboarding`
- `zllr9lrg7j OPTIONS /marketing-ads -> wecare-marketing-ads`
- `zllr9lrg7j POST /partners/billing/topup-order -> wecare-partner-onboarding`
- `zllr9lrg7j POST /partners/send -> wecare-partner-onboarding`
- `zllr9lrg7j OPTIONS /partners/me -> wecare-partner-onboarding`
- `zllr9lrg7j ANY /seo-tools -> wecare-seo-tools`
- `zllr9lrg7j OPTIONS /partners/billing/topup-order -> wecare-partner-onboarding`
- `zllr9lrg7j ANY /seo-tools/{proxy+} -> wecare-seo-tools`
- `zllr9lrg7j OPTIONS /partners/tenants -> wecare-partner-onboarding`
- `zllr9lrg7j GET /partners/billing -> wecare-partner-onboarding`
- `zllr9lrg7j OPTIONS /partners/billing -> wecare-partner-onboarding`
- `zllr9lrg7j POST /partners/embedded-signup -> wecare-partner-onboarding`
- `zllr9lrg7j OPTIONS /partners/billing/topup -> wecare-partner-onboarding`
- `zllr9lrg7j ANY /marketing-ads -> wecare-marketing-ads`

### Routes pointing at a function that does not exist

(none)

### Functions with errors in 7 days

(none)

### Zero invocations in 7 days — candidates for retirement review

(none)

### No route, no event source, no traffic — strongest retirement candidates

(none)

### Log groups with no retention — unbounded cost and data retention

- `wecare-ad-attribution`
- `wecare-catalog-management`
- `wecare-meta-analytics`
- `wecare-plivo-answer`
- `wecare-push-notifications`
- `wecare-seo-tools`
- `wecare-service-api`
- `wecare-site-language`
- `wecare-sla-engine`

### Route paths no frontend file mentions — provider webhook, internal, or dead

- `/agent-tool`
- `/bulk/worker`
- `/contacts/search`
- `/inbox/meta/{conversationId}/note`
- `/invoices/from-payment`
- `/invoices/next-sequence`
- `/invoices/send-pending-by-phone`
- `/invoices/{invoiceId}/cancel`
- `/invoices/{invoiceId}/delivery-log`
- `/invoices/{invoiceId}/generate-image`
- `/invoices/{invoiceId}/generate-pdf`
- `/invoices/{invoiceId}/remark`
- `/invoices/{invoiceId}/send-payment-link`
- `/invoices/{invoiceId}/send-whatsapp`
- `/media/cleanup`
- `/payments/webhook`
- `/plivo/answer`
- `/plivo/dial-events`
- `/plivo/events`
- `/plivo/fallback`
- `/plivo/hangup`
- `/site-language/languages`
- `/site-language/translate`
- `/site-language/tts`
- `/site-language/voices`
- `/sms-aws/templates`
- `/voice-aws/send`
- `/voice-in/c2c/clear-logs`
- `/voice-in/obd/clear-logs`
- `/voice-in/obd/create`
- `/voice-in/obd/tts`
- `/voice-in/obd/upload-audio`
- `/voice-in/obd/upload-csv`
- `/wa-business/appointments`
- `/wa-business/appointments/{appointmentId}`
- `/wa-business/assigned-users`
- `/wa-business/assigned-wabas`
- `/wa-business/bot`
- `/wa-business/calling-settings`
- `/wa-business/catalog-flow-map`
- `/wa-business/conversational-automation`
- `/wa-business/direct-send`
- `/wa-business/direct-send/samples`
- `/wa-business/direct-send/templates`
- `/wa-business/documents`
- `/wa-business/documents/{documentId}`
- `/wa-business/documents/{documentId}/download`
- `/wa-business/enterprise-assist`
- `/wa-business/enterprise-assist/{caseId}`
- `/wa-business/faq`
- `/wa-business/faq/{faqId}`
- `/wa-business/flow-clone`
- `/wa-business/flow-customer-journey`
- `/wa-business/flow-data`
- `/wa-business/flow-sla-check`
- `/wa-business/flow-submissions/export`
- `/wa-business/flow-submissions/stats`
- `/wa-business/flow-submissions/update-status`
- `/wa-business/flows`
- `/wa-business/flows/deprecate`
- `/wa-business/flows/preview`
- `/wa-business/flows/publish`
- `/wa-business/groups`
- `/wa-business/groups/participants`
- `/wa-business/groups/send`
- `/wa-business/interactive-list`
- `/wa-business/marketing-message`
- `/wa-business/mm-onboarding-status`
- `/wa-business/orders/sync`
- `/wa-business/orders/{orderId}/submissions`
- `/wa-business/payment-config/check`
- `/wa-business/phone-settings`
- `/wa-business/profile`
- `/wa-business/reviews`
- `/wa-business/reviews/{reviewId}`
- `/wa-business/rx-slots`
- `/wa-business/rx-slots/{slotId}`
- `/wa-business/schedules`
- `/wa-business/service/amend`
- `/wa-business/service/drafts`
- `/wa-business/service/drafts/{flowCode}`
- `/wa-business/service/history`
- `/wa-business/service/submit`
- `/wa-business/service/track/{orderId}`
- `/wa-business/throughput`
- `/wa-business/username`
- `/wa-business/username/suggestions`
- `/wa-business/webhooks`
- `/waba/{wabaId}/events`
- `/webhook/sinch-rcs`
- `/whatsapp/business-api`
- `/whatsapp/inbound`
- `/whatsapp/template-management`
- `/whatsapp/voice`
- `/{code}`
