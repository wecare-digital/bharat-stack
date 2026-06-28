# WhatsApp Flows Implementation

First-class Flows support across backend (`amplify/functions/messaging/whatsapp-business-api`)
and UI (`src/pages/dm/whatsapp/flow-hub.tsx`, `flows.tsx`, `flow-responses.tsx`).

## Flow lifecycle
`DRAFT → PUBLISHED → DEPRECATED` (plus `BLOCKED`, `UNKNOWN`).
- DRAFT is editable. Published flows/assets are **immutable** — to change a published
  flow, clone it and publish a new version.
- Do not route new customers to DEPRECATED flows.
- Do not publish while `validation_errors` exist or `health_status` blocks sending.

## FlowRegistry (DynamoDB, `amplify/data/resource.ts`)
Core: `flowId, flowCode, flowName, flowType, flowVersion, dataApiVersion, wabaId,
status, category, requiresPayment, paymentAmount, paymentConfigName, screenConfig,
contactMapping, dataFetchers, submissionPrefix, endpointUri, publishedAt`.
Extended (Part 4 A): `categories, healthStatusJson, validationErrorsJson, previewUrl,
previewExpiresAt, lastSyncedAt, lastPublishedAt, lastDeprecatedAt, clonedFromFlowId,
migrationBatchId, dataChannelUri, jsonVersion, applicationId`.

## Flow JSON upload (assets)
`POST /wa-business/flows/assets` → multipart `asset_type=FLOW_JSON`, file `flow.json`.
JSON is validated **locally** (version/screens present, parseable) before upload;
Meta `validation_errors` are parsed and returned. Published assets are immutable.

## Validation errors
Returned from create/asset/sync; surfaced in the UI via `ValidationErrorList` with
screen/component context where Meta provides it. A `flow_validation_error` SystemEvent
is raised.

## Preview
`POST /wa-business/flows/preview` returns a `preview_url` with an expiry. UI shows
expiry and offers regenerate/invalidate (`FlowPreviewCard`).

## Publish checklist (UI gate before publish)
DRAFT · JSON uploaded · no validation errors · endpoint URI set (if dynamic) · data
exchange encryption configured · health allows send · WABA can send · payment config
valid (if payment) · contact mapping safe · no PII logging · preview tested.

## Deprecate / clone / migrate
- Deprecate: `POST /wa-business/flows/deprecate` (raises `flow_deprecated`).
- Clone: `/flow-clone` copies registry config to a new WABA/flow id (`flow_cloned`).
- Migrate: `POST /wa-business/flows/migrate` → Meta `migrate_flows` (`flow_migrated`).
- Sync: `POST /wa-business/flows/sync` reconciles Meta → FlowRegistry (status,
  categories, validation errors, health, `lastSyncedAt`; raises `flow_health_blocked`
  when blocked).

## Flow Data Exchange (encryption)
Endpoint receives `encrypted_flow_data` + `encrypted_aes_key` + `initial_vector`.
RSA-decrypt the AES key with the configured private key, AES-GCM decrypt the payload,
route by `action`/`screen`/`flow_token`/`data`, return an **encrypted** response.
Handles `ping`, `INIT`, `data_exchange`, `navigate`, `back`, `complete`, error cases.
Never log encrypted payloads or decrypted PII — masked metadata + `FlowLog` only.

## FlowSubmission & FlowDraft
- `FlowSubmission`: completed submissions (form data, payment tracking, lifecycle
  status, submission number).
- `FlowDraft`: interrupted flows (`{phone}#{flowCode}` key, 7-day TTL) for resume.
- `FlowLog`: per-screen audit trail (90-day TTL), masked snapshots.

## Payments after flow
When `requiresPayment`, after completion the handler sends a native payment
(`preferredGateway` / `paymentConfigName`) and tracks `paymentStatus` on the submission.

## Customer journey
`/flow-customer-journey` aggregates inbound/outbound messages, flows opened/completed,
payments, orders, and notes for a contact timeline.
