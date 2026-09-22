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
| 12 | 2026-09-21 | Rewrite `scripts/audit_route_auth.py`: discover all HTTP APIs, fix handler-name mapping, split DANGLING from UNRESOLVED, add `--strict`/`--json` | local | `A1_LOCAL` | yes | owner blanket (`YES` all items) | UNRESOLVED 4 → 0; found 3 routes never previously scanned |
| 13 | 2026-09-21 | Add `lambda_utils/sinch_signature.py`, `lambda_utils/meta_signature.py`, guards in `rcs-dlr` and `inbound-whatsapp`, 35 tests | local | `A1_LOCAL` | yes | owner blanket | RED proof: pre-fix returned 200 and processed a forged report; post-fix 401 |
| 14 | 2026-09-21 | Add `scripts/check_secret_fields_present.py` (presence booleans only) | local | `A1_LOCAL` | yes | owner blanket | `wecare/sinch/rcs` has no `webhook_secret` |
| 15 | 2026-09-21 | Commit `384c3572`, push `4baf4236..5b89a1b6` to `stack` | remote | `A2_REMOTE_CODE` | revert | owner blanket | Non-force; 1207 tests, policy 8/8 |
| 16 | 2026-09-21 | `apply_unattended_permissions.py --user`: replace 23 literal path entries with directory scopes | `~/.kiro/settings/permissions.yaml` | `A1_LOCAL` | yes, backup written | owner instruction | 0 literal entries; six capabilities |
| 17 | 2026-09-21 | Deploy `wecare-rcs-dlr`: update code, publish v7, move `live` 6 → 7 | Lambda | `A3_PRODUCTION` | yes | owner blanket | live v7 `55FQyp+dAcVm…`, `Active`, sha == `$LATEST`. Rollback: `update-alias … --function-version 6` |
| 18 | 2026-09-21 | Deploy `wecare-inbound-whatsapp`: update code, publish v38, move `live` 37 → 38 | Lambda | `A3_PRODUCTION` | yes | owner blanket | First attempt failed `InvalidSignatureException` (clock skew, nothing applied — verified live still v37); retry succeeded. live v38 `5fjOzD6fOr6q…`, `Active`. Rollback: `--function-version 37` |
| 19 | 2026-09-21 | Live probe of both ingresses, unauthenticated, post-fix | production HTTP | `A3_PRODUCTION` | n/a, inert | owner blanket | 4/4 as expected: 401, 401, 503, 200 |
| 20 | 2026-09-21 | Delete 5 dangling routes + 2 integrations | API Gateway | `A4_DESTRUCTIVE` | yes, via manifest | owner blanket, manifest exported first | 332 → 327 routes; 0 dangling. See `docs/prohibited-provider-retirement.md` |

| 21 | 2026-09-21 | Triage 32 weak-marker routes by reading every handler's actual auth path | repo | `A0_READ` | n/a | standing grant | All 7 handlers had zero `require_auth`; 30 routes genuinely open |
| 22 | 2026-09-21 | Apply `require_auth` to 7 handlers; per-route in url-shortener; 38 tests | local | `A1_LOCAL` | yes | standing grant | Gate proven: guard removal fails 3 tests; seeded route flagged OPEN |
| 23 | 2026-09-21 | Retire weak markers from the audit default; add `EXPECTED_PUBLIC_ROUTES` with reasons; add shared-verifier strong markers | local | `A1_LOCAL` | yes | standing grant | Default run now equals the old `--strict`; `--lenient` reproduces the old baseline |
| 24 | 2026-09-21 | Add `.github/workflows/route-auth.yml` (blocking source gate + scheduled live gate) | repo | `A1_LOCAL` | yes | standing grant | Also puts the full 1245-test suite in CI for the first time |
| 25 | 2026-09-21 | Drop `standalone=True` for both url-shortener specs in `deploy_all_lambdas.py` | local | `A1_LOCAL` | yes | standing grant | Required because the handler now imports `lambda_utils`; import kept lazy so redirects pay nothing |
| 26 | 2026-09-21 | Commit `bbd8c7a1` | local | `A1_LOCAL` | revert | standing grant | 1245 tests, policy 8/8 |
| 27 | 2026-09-21 | Deploy 8 functions: code, publish version, move `live` | Lambda | `A3_PRODUCTION` | yes | standing grant | media-cleanup v8, voice-in-c2c v8, voice-in-obd v8, ai-generate-response v8, bulk-worker v8, product-image-gen v9, stack-wecare-url-shortener v4, wecare-url-shortener `$LATEST`. All `Active`, sha == `$LATEST` |
| 28 | 2026-09-21 | Live probe of 12 routes, unauthenticated | production HTTP | `A3_PRODUCTION` | n/a, reads only | standing grant | 12/12 as expected. `POST /media/cleanup` deliberately not probed: no read method, and a broken guard would have deleted media |

| 29 | 2026-09-21 | Add `lambda_utils/live_smoke.py` and wire the lockdown into `outbound-whatsapp` (403 at the handler, refusal at the wire, per-user check on `blockUsers`); 33 tests | local | `A1_LOCAL` | yes | standing grant | RED proof: with the wire guard neutralised the same call reaches the Graph request. Both env vars confirmed **absent** in production, so the lockdown is inert |
| 30 | 2026-09-21 | Deploy `wecare-outbound-whatsapp`: code, publish v19, move `live` 18 → 19 | Lambda | `A3_PRODUCTION` | yes | standing grant | live v19 `AP2PadnMhIJ6…`, `Active`, `LastUpdateStatus=Successful`. `WA_LIVE_SMOKE_TEST`/`WA_QA_RECIPIENT` absent on the published version. Rollback: `update-alias … --function-version 18` |
| 31 | 2026-09-21 | Rewrite `_validate_webhook_timestamp` in `whatsapp-calling`: per-timestamp verdicts, reject unreadable / far-future / unwalkable shapes, keep absent allowed; 62 tests | local | `A1_LOCAL` | yes | standing grant | RED proof against the previous commit's code loaded side by side: 3 fail-open holes closed, 4 AttributeError/500 paths turned into clean rejections, 3 must-stay-allowed cases unchanged. First draft was a net regression (silent accept for `calls` as an object) and the proof caught it |
| 32 | 2026-09-21 | Deploy `wecare-whatsapp-calling`: code, publish v14, move `live` 13 → 14 | Lambda | `A3_PRODUCTION` | yes | standing grant | live v14 `wUYUAbtsK2wy…`, `Active`. Rollback: `--function-version 13` |
| 33 | 2026-09-21 | Read `AUTH_SKIP_PATHS` across all 58 functions before changing the matcher | AWS | `A0_READ` | n/a | standing grant | Exactly **one** setter: `wecare-whatsapp-business-api`. 0 errors across 58 `GetFunctionConfiguration` calls, so the blast radius of a stricter rule is one function |
| 34 | 2026-09-21 | Unauthenticated probe of `GET /wa-business/webhooks` **before** the fix | production HTTP | `A0_READ` | n/a, inert | standing grant | **400 "wabaId required"** — past auth, inside the handler — against **401** for `GET /wa-business/profile`. No `wabaId` sent, so no Graph call was possible |
| 35 | 2026-09-21 | Tighten `middleware.path_is_exempt` to exact-or-child-segment matching, stage-normalized; replace the substring test | local shared module | `A1_LOCAL` | yes | standing grant | 32 tests. `/wa-business/webhooks-anything` no longer inherits the exemption; internal invokes and OPTIONS still exempt |
| 36 | 2026-09-21 | Narrow `AUTH_SKIP_PATHS` on `wecare-whatsapp-business-api` to `/wa-business/flow-data` — live env **and** `config/lambda-env-manifest.json` | Lambda config + IaC | `A3_PRODUCTION` | yes | standing grant, tightens security | Other 17 env keys unchanged (asserted by key-set comparison). Env updated **before** the publish so v32 carries it. Rollback command recorded |
| 37 | 2026-09-21 | Replace the dead fail-open verifier in `whatsapp-business-api` with `meta_signature`; invert the test that pinned the fail-open | local | `A1_LOCAL` | yes | standing grant | Verifier had **zero** call sites, so its fail-open was a trap rather than a live hole. `tests/test_business_api.py::test_no_secret_fails_open` → `test_no_secret_fails_closed` |
| 38 | 2026-09-21 | Deploy `wecare-whatsapp-business-api`: code, publish v32, move `live` 31 → 32 | Lambda | `A3_PRODUCTION` | yes | standing grant | live v32 `MWYHMqWrjIjd…`, `Active`. Rollback: `--function-version 31` plus the env rollback in row 36 |
| 39 | 2026-09-21 | Unauthenticated probe of 7 routes **after** the fix, plus 4 new permanent gate probes | production HTTP | `A3_PRODUCTION` | n/a, inert | standing grant | `GET/POST/DELETE /wa-business/webhooks` and the substring near-miss all **401**; `POST /wa-business/flow-data` still **421 Decryption failed**, so the one legitimate exemption still works. Gate now **17/17** |

## Not exercised

- No credential was read, written, rotated or revoked.
- No `GetSecretValue` from a shell or from `aws___run_script`.
- No WhatsApp registration, WABA, number or subscription was touched.
- No secret deletion scheduled or cancelled.
- No force push, no history rewrite, no broad staging.
- No live customer message or call was sent.
- `PSTN_BROWSER_ROUTING_ENABLED` and `PSTN_CONNECTED_NOTIFICATIONS_ENABLED`
  remain `false`.
