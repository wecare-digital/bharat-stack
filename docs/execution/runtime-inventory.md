# Runtime inventory

Generated 2026-09-24T07:19:14+00:00 · `us-east-1` · regenerate with `python scripts/generate_runtime_inventory.py`

Machine-readable companion: `runtime-inventory.json`. Environment variable
**names** are recorded, values never are.

| Count | |
|---|---:|
| Lambda functions | 62 |
| with a `live` alias | 56 |
| HTTP APIs | 1 |
| Routes | 353 |
| DynamoDB tables | 77 |

## Anomalies

Each list is a question to answer, not automatically a defect.

### Live functions absent from the deploy map — cannot be patched by the standard path

- `wecare-docs-scraper` — **expected**: PackageType=Image; ships via .github/workflows/docs-scraper-deploy.yml
- `wecare-pstn-softphone`
- `wecare-seo-tools` — **expected**: different in-zip layout; scripts/deploy_seo_tools.py owns it with its table and IAM policy

### Functions with routes but no `live` alias — `$LATEST` reaches production directly

- `wecare-docs-scraper`
- `wecare-seo-tools`

### Routes whose integration is unqualified — bypasses the version/alias model

- `zllr9lrg7j POST /docs/scrape -> wecare-docs-scraper`
- `zllr9lrg7j ANY /seo-tools -> wecare-seo-tools`
- `zllr9lrg7j GET /docs/sources -> wecare-docs-scraper`
- `zllr9lrg7j ANY /seo-tools/{proxy+} -> wecare-seo-tools`
- `zllr9lrg7j GET /docs/changelog -> wecare-docs-scraper`
- `zllr9lrg7j POST /docs/sources -> wecare-docs-scraper`

### Routes pointing at a function that does not exist

(none)

### Functions with errors in 7 days

- `wecare-inbound-whatsapp`: 9
- `wecare-seo-tools`: 2

### Zero invocations in 7 days — candidates for retirement review

(none)

### No route, no event source, no traffic — strongest retirement candidates

(none)

### Log groups with no retention — unbounded cost and data retention

(none)

### Route paths no frontend file mentions — provider webhook, internal, or dead

- `/agent-tool`
- `/ai/approvals/status`
- `/bulk/worker`
- `/contacts/search`
- `/crm/activities`
- `/crm/contacts/{contactId}/360`
- `/crm/leads`
- `/crm/leads/{leadId}`
- `/crm/leads/{leadId}/convert`
- `/crm/opportunities`
- `/crm/opportunities/{opportunityId}`
- `/crm/pipelines`
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
- `/pstn/diagnostics`
- `/pstn/session`
- `/pstn/session/events`
- `/pstn/session/presence`
- `/pstn/token`
- `/site-language/languages`
- `/site-language/translate`
- `/site-language/tts`
- `/site-language/voices`
- `/sms-aws/templates`
- `/store/convert-flag`
- `/store/generate-product-image`
- `/store/preview-product-image`
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
