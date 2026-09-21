# Change authority matrix

## Classes

| Class | Scope | Required behavior |
|---|---|---|
| `A0_READ` | Repo / AWS / provider / GitHub read-only, logs, metrics, schemas, docs, safe health queries | Proceed; redact; record evidence |
| `A1_LOCAL` | Local source/docs/tests, reversible flag-gated implementation, generated inventories, non-secret config examples | Proceed inside the active phase; preserve unrelated edits |
| `A2_REMOTE_CODE` | Push reviewed commits, observe CI — only when the phase contract authorizes it | Verify branch/SHA, no force push; a push is not a deployment |
| `A3_PRODUCTION` | Lambda/API/Amplify/IaC/database/provider deployment, repo settings, production message/call/test, live ad/payment action, number binding, store upload | Explicit owner approval for the exact target **and** rollback, immediately before acting |
| `A4_DESTRUCTIVE` | Delete route/function/table/secret/subscription; cancel scheduled deletion; irreversible migration; WhatsApp registration change | Exact inventory, backup/restore proof, dependency proof, explicit owner approval. Protected WhatsApp removal stays prohibited |

Always prohibited: exposing or inlining credentials; force push; broad recursive
delete; guessing identifiers; cross-WABA fallback; deregistering a WhatsApp
number; PayU / Airtel comms / Sinch SMS-Voice-WhatsApp / Plivo SMS; making an
IDE or MCP server a production dependency; weakening auth, signature or consent
checks to make a test pass.

## Operations log

| # | Date | Operation | Target | Class | Reversible | Approver | Result |
|---|---|---|---|---|---|---|---|
| 1 | 2026-09-21 | `git rev-parse` / `status` / `log` | local repo | `A0_READ` | n/a | none needed | HEAD `4baf4236`, local == `origin/stack`, 28 commits past the brief's snapshot |
| 2 | 2026-09-21 | `sts:GetCallerIdentity` | account | `A0_READ` | n/a | none needed | `775261844268` / `user/wecare-admin` |
| 3 | 2026-09-21 | `lambda:ListFunctions` + `ListAliases` ×58 | Lambda fleet | `A0_READ` | n/a | none needed | 58 functions, 49 with `live`, errorTotal 0 |
| 4 | 2026-09-21 | `apigatewayv2:GetApis/GetRoutes/GetIntegrations/GetStages/GetAuthorizers` | both HTTP APIs | `A0_READ` | n/a | none needed | 332 routes, 0 authorizers, 5 dangling routes found |
| 5 | 2026-09-21 | `dynamodb:ListTables` | tables | `A0_READ` | n/a | none needed | 66 tables |
| 6 | 2026-09-21 | `secretsmanager:ListSecrets` (**names only**) | secrets | `A0_READ` | n/a | none needed | 31 entries; 6 scheduled for deletion. **No `GetSecretValue` call was made** |
| 7 | 2026-09-21 | `cognito-idp:ListUserPools/GetUserPoolMfaConfig/ListUserPoolClients` | user pool | `A0_READ` | n/a | none needed | `us-east-1_cSx0RHCIR`, MFA `OFF` |
| 8 | 2026-09-21 | `wafv2:ListWebACLs` ×2, `guardduty:ListDetectors`, `amplify:ListApps` | security/hosting | `A0_READ` | n/a | none needed | 0 WebACLs, 0 detectors, app `d22dm4b0jn71jw` |
| 9 | 2026-09-21 | `scripts/audit_route_auth.py` (read-only) | route auth | `A0_READ` | n/a | none needed | 2 OPEN, 4 unresolved, second API unscanned |
| 10 | 2026-09-21 | Local source reads (`rcs-dlr`, `inbound-whatsapp-handler`, notification producers) | repo | `A0_READ` | n/a | none needed | Two unauthenticated ingresses confirmed from source |
| 11 | 2026-09-21 | Write Phase 0 artifacts under `docs/` | local files | `A1_LOCAL` | yes | none needed | 8 files created; nothing staged or committed |

## Pending approvals

See the confirmation queue in `docs/kiro-handoff.md`. Nothing in classes
`A2`–`A4` has been exercised.
