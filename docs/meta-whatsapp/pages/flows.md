# Build Spec — WhatsApp Flows

Meta refs: /flows, /flows/guides (reference, flowsapi, flowswebhooks, lifecycle, whatsapp-business-encryption, healthmonitoring, testingdebugging, bestpractices)

## Repo mapping
- Backend: `whatsapp-business-api/handler.py` + `flows/` module + `service_api.py`.
- Routes: `POST /wa-business/flows`, `PUT /wa-business/flows`, `POST /wa-business/flows/publish`, `POST /wa-business/flows/deprecate`, `POST /wa-business/flow-clone`, `GET /wa-business/flow-registry`, `GET /wa-business/flow-submissions`, `GET /wa-business/flow-version-health`, `POST /wa-business/flow-data` (data exchange).
- Encryption: RSA private key `wecare/flow-private-key` (request decrypt / response encrypt).
- Storage: `FlowRegistryTable`, `FlowSubmissionTable`, `FlowLogTable` (TTL).
- Frontend: `flows.tsx`, `flow-hub.tsx`, `flow-responses.tsx`.

## Flag
`WA_FLOWS_ENABLED=true`. Health monitoring + JSON validation: PARTIAL.

## Status
FEATURE_FLAGGED_META_GATED. Live verify needs a published Flow + QA recipient completing it on a phone.
