# Kiro handoff

Updated: **2026-09-21**

## Position

| Field | Value |
|---|---|
| Mode | **Unattended.** `.kiro/steering/01-standing-authorization.md` governs; no confirmation queue |
| Phase | Phase 0 complete. Security remediation complete and live. Phase 1 **in progress** |
| Branch | `stack` |
| HEAD | `4095cc68`, pushed |
| HTTP APIs / routes | **1 / 326** (was 2 / 332) |
| Routes OPEN at both layers | **0** (was 30) |
| Lambda errors, 7 days | **0** |
| Gates | 1245 python tests · provider policy 8/8 · route audit 0 OPEN / 0 DANGLING / 0 UNRESOLVED · live probes 12/12 |

## What was done, in order

**The approval problem.** Prompts were not coming from the project policy — that
was already fully wildcarded, and every deny hook passes silently on the command
shapes in use, verified directly against `block_catastrophic.py` including
`delete-route` and `update-function-code`. There are **two** permissions files, and
only the per-workspace one was managed. Scratch output in `/tmp` and reads of
`~/.kiro` fall outside the workspace root, so each new filename prompted, and 23
literal path entries had accumulated in the user-level file. Fixed both halves:
`apply_unattended_permissions.py --user` writes directory scopes, and scratch now
lives in `.scratch/` inside the workspace. `$HOME` is deliberately not wildcarded
for writes, because `block-catastrophic` guards `~/.aws` and `~/.ssh` on the shell
and MCP routes but its matcher does not cover file-write tools.

**Two unauthenticated provider ingresses, closed and live-verified.**
`/webhook/sinch-rcs` verified nothing at all while writing to the canonical message
store and invoking `wecare-rcs-send` with a phone number from the unauthenticated
body. `POST /whatsapp/inbound` accepted unsigned Meta envelopes and honoured
`action=create_invoice` before any authorization. Both now enforce raw-body
signatures through shared verifiers, neither fails open.

**Thirty more open routes.** The route audit's "0 findings" was untrustworthy: it
scanned one of two APIs, mis-mapped handler directories, and accepted
`Authorization`, `api_key`, `verify_token` and `appsecret_proof` as proof of
authentication. Every one of those matches turned out to be a CORS string or an
outbound provider credential, and all seven affected handlers contained zero
`require_auth`. Anonymous callers could delete media from Meta, wipe call and
campaign logs, upload recipient lists, spend model tokens, and mint short links on
a `wecare.digital` host. All now behind `require_auth`, with five routes
allowlisted where authentication is impossible or circular.

**Dead surface removed.** Five dangling routes plus two integrations pointing at
deleted Lambdas, and then the entire second HTTP API: no domain mapped to it, zero
requests in 30 days against 84,301 for the live API, one route duplicating a
correctly-aliased route while pointing at `$LATEST`, and `AllowOrigins ["*"]`.

**Audits that did not exist.** Three now do, each proven against a seeded failure
rather than assumed: route authentication, table-name drift, and the joined runtime
inventory. The full 1245-test suite also runs in CI for the first time.

## Open findings, highest value first

| ID | Finding |
|---|---|
| `DEPLOY-003` | 3 functions serve routes with **no `live` alias** — `partner-onboarding` (21 routes, the partner/tenant control plane including billing top-up), `marketing-ads`, `seo-tools`. All 25 unqualified integrations trace to these. `update-function-code` reaches production instantly with nothing to roll back to |
| `SEC-ROUTE-008` | Destructive routes accept **any** signed-in user, not `Admin`: `clear-logs` ×2, `media-cleanup`, `DELETE /links/{code}`. Needs Cognito group membership read first so tightening cannot lock out the operator |
| `SEC-ROUTE-006` | RCS delivery receipts are still processed unverified, because no `webhook_secret` exists at Sinch. Justified by measurement — 313 of 313 callbacks in 7 days were `MESSAGE_DELIVERY`, zero inbound — and it self-heals the moment the secret exists |
| `NOTIF-STORE-003` | The 65 declared Amplify models and the 66 live tables are two disjoint naming worlds. Until settled, `resource.ts` is not a description of production |
| `SEC-ROUTE-007` | `voice-in/obd` still holds an executable Airtel CDR-callback branch, now behind auth |
| `PROV-AIRTEL-002` | `wecare-voice-in-c2c` still carries `AIRTEL_C2C_TABLE` and `AIRTEL_C2C_SECRET_NAME` in its deployed env |
| `OPS-001` | 9 log groups with no retention |
| `OPS-002` | 95 route paths no frontend file mentions — webhook, internal, or dead |
| new | GitHub reports **48 Dependabot alerts** (1 critical, 26 high, 19 moderate, 2 low). The brief recorded Dependabot as unavailable, so this is a change |

## Waiting on the owner

| Item | Exact unblock action |
|---|---|
| Full RCS verification | Set a webhook secret on the Sinch Conversation API webhook, then store it as `webhook_secret` in `wecare/sinch/rcs`. No code change needed |
| Exposed credentials | Replace the Razorpay / Google Ads / Google OAuth / Google API key / Bing credentials. Kiro will not touch credential values |
| Meta MCP servers | Add `http://localhost:7778/oauth/callback` (DevTools) and `http://localhost:7779/oauth/callback` (WhatsApp Business Tools) to app `2238810740192680` |
| Razorpay MCP | Blocked on the provider: its token endpoint advertises only `client_secret_post` |
| Live QA sends and calls | Nominate a QA recipient. Nothing goes to a real customer without one |
| CI live gate | Set repository variable `ROUTE_AUTH_ROLE_ARN` to a read-only OIDC role. Until then that job skips rather than fails |

## Re-verify anything here

```bash
python scripts/audit_route_auth.py --gate            # 0 OPEN across every HTTP API
python scripts/audit_data_model_drift.py             # table names code uses vs exist
python scripts/generate_runtime_inventory.py         # regenerate the joined inventory
python scripts/verify_public_webhook_auth.py --gate  # 12 live probes
python scripts/apply_unattended_permissions.py --list
.venv/bin/python -m pytest -q                        # 1245
bash scripts/check-provider-policy.sh                # 8/8
```

## Rollback

```bash
aws lambda update-alias --function-name wecare-rcs-dlr            --name live --function-version 7
aws lambda update-alias --function-name wecare-inbound-whatsapp   --name live --function-version 37
aws lambda update-alias --function-name wecare-media-cleanup      --name live --function-version 7
aws lambda update-alias --function-name wecare-voice-in-c2c       --name live --function-version 7
aws lambda update-alias --function-name wecare-voice-in-obd       --name live --function-version 7
aws lambda update-alias --function-name wecare-ai-generate-response --name live --function-version 7
aws lambda update-alias --function-name wecare-bulk-worker        --name live --function-version 7
aws lambda update-alias --function-name wecare-product-image-gen  --name live --function-version 8
aws lambda update-alias --function-name stack-wecare-url-shortener --name live --function-version 3
aws lambda update-alias --function-name wecare-waba-management    --name live --function-version 9
aws lambda update-alias --function-name wecare-rcs-send           --name live --function-version 7
aws lambda update-alias --function-name wecare-messages-read      --name live --function-version 8
```

Route, integration and API restore commands: `docs/prohibited-provider-retirement.md`.
Permissions: `python scripts/apply_unattended_permissions.py --user --restore`.
