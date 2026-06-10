# Meta WhatsApp — Build & Coverage Docs

Honest scope note: this doc set is grounded in a **real deep scan of this repository** (51 deployed `wecare-*` Lambdas, the live API routes, the WhatsApp handlers, the inbox frontend) performed during the audit/build session. It is **not** a full recursive re-crawl of every nested Meta docs page — where a Meta page was consulted live it is cited; otherwise the mapping is repo→feature based on existing prior crawl artifacts in the repo root (`whatsapp_api_master_consolidated.md`, `docs_tree.md`, `feature_to_code_traceability.json`).

## Files
| File | Purpose |
|------|---------|
| `REPO_SCAN.md` | What exists in the repo per WhatsApp feature, with file evidence |
| `FEATURE_BUILD_MATRIX.md` | Every required feature + status label + evidence |
| `BUILD_SUMMARY.md` | What was actually built/changed in this session |
| `SECURITY_CHECKLIST.md` | Webhook signature, auth, secrets, idempotency |
| `LIVE_SMOKE_TEST_PLAN.md` | Gated live send battery (needs `WA_QA_RECIPIENT`) |
| `ENVIRONMENT_VARIABLES.md` | Env + Secrets Manager contract |
| `META_GATED_FEATURES.md` | Flags for Payments/Calling/Groups/Marketing |
| `ON_PREM_SUNSET_NOTE.md` | On-Premises API sunset status for this repo |
| `pages/` | Per-topic Meta build specs (representative subset) |

## Status labels
`BUILT_AND_TESTED` · `IMPROVED_AND_TESTED` · `PARTIAL_FIXED` · `FEATURE_FLAGGED_META_GATED` · `MOCKED_ONLY_WAITING_FOR_CREDENTIALS` · `BLOCKED_BY_META_PERMISSION` · `DEPRECATED_NOT_BUILT` · `NOT_APPLICABLE`

## Architecture (verified)
- **Inbound:** Meta → AWS End User Messaging (Social/WhatsApp) → SNS → `wecare-inbound-whatsapp`. GET verify + X-Hub signature are handled by the AWS-managed integration.
- **Outbound:** `wecare-outbound-whatsapp` → Meta Graph API `v25.0` (with `appsecret_proof`).
- **Templates:** `wecare-whatsapp-templates` (CRUD/list against Graph API).
- **Two WABAs:** WABA 1 `2094615664435155` (+91 93309 94400), WABA 2 `2513394156072604` (+91 99033 00044).
- **Lambda deploy:** NOT via Amplify (frontend only). Python Lambdas deploy via `scripts/deploy_all.ps1` (`aws lambda update-function-code`).
