# Kiro handoff

Updated: **2026-09-21**

## Position

| Field | Value |
|---|---|
| Mode | **Unattended.** `.kiro/steering/01-standing-authorization.md` governs; no confirmation queue |
| Active phase | Phase 0 complete. Security remediation complete and live. Phase 1 discovery is next |
| Branch | `stack` |
| HEAD | `5b89a1b6` pushed; two further commits pending below |
| Deployed this session | `wecare-rcs-dlr` live **v7**, `wecare-inbound-whatsapp` live **v38** |
| Routes | **327** across 2 HTTP APIs (was 332) |
| Live security posture | **0 OPEN**, 0 dangling, 0 unresolved routes |

## What changed

Two unauthenticated production ingresses are closed and verified live.

`/webhook/sinch-rcs` now enforces the Sinch raw-body HMAC
(`rawBody.nonce.timestamp`, base64 HMAC-SHA256, validated before any JSON
parsing) per the official Conversation API callbacks contract. `POST
/whatsapp/inbound` now requires Meta's `X-Hub-Signature-256` for anything
arriving with an API Gateway envelope, and `action=create_invoice` is
internal-invocation only. Neither fails open.

Five dangling routes and their two integrations are gone — `/webhook/sinch-dlr`
(×2, retired Sinch SMS) and `/voice-in/cdr` (×3, retired Airtel CDR ingester),
all pointing at Lambdas that no longer exist. Full export and restore commands
are in `docs/prohibited-provider-retirement.md`.

`scripts/audit_route_auth.py` was rewritten because its "0 findings" could not be
trusted: it scanned one of two APIs and mis-mapped handler directories, so a
public Meta ingress read as "source not resolvable". It now scans every HTTP API,
separates DANGLING from UNRESOLVED, and offers `--strict`/`--json`.

## Live evidence

| Probe | Result |
|---|---|
| `POST /whatsapp/inbound`, unsigned | **401** |
| `POST /whatsapp/inbound`, unsigned `create_invoice` | **401** |
| `POST /webhook/sinch-rcs`, unsigned `MESSAGE_INBOUND` | **503** |
| `GET /webhook/sinch-rcs` | **200** |

Re-runnable: `python scripts/verify_public_webhook_auth.py --gate`

Gates: **1207** python tests pass, provider policy **8/8**, route audit
**0 OPEN / 0 DANGLING / 0 UNRESOLVED**.

## One honest caveat

`wecare/sinch/rcs` contains `app_id, bot_id, password, project_id, username` and
**no `webhook_secret`** — Sinch only signs callbacks when a secret is configured
on the webhook. Enforcing strictly would have 503'd every real callback, so the
deployed posture is measured rather than absolute:

- Measured 7 days to 2026-09-21: **313 of 313** callbacks were `MESSAGE_DELIVERY`.
  Zero `MESSAGE_INBOUND`, zero opt events.
- So `MESSAGE_DELIVERY` is still processed unverified, and every event type that
  writes into the canonical message store or can trigger an outbound send is
  refused with a retryable 503.
- Residual risk: a forged delivery receipt could alter a message's status. No
  injection, no spend, no send.
- There is no flag to remember. The moment a `webhook_secret` exists, everything
  is verified strictly and the interim branch is dead code.

## Waiting on the owner

| Item | Exact unblock action |
|---|---|
| `SEC-ROUTE-006` full RCS verification | Set a webhook secret on the Sinch Conversation API webhook, then store it as `webhook_secret` in `wecare/sinch/rcs`. No code change needed |
| `SEC-CRED-001` exposed credentials | Replace the Razorpay / Google Ads / Google OAuth / Google API key / Bing credentials. Kiro will not touch credential values |
| `MCP-META-001` Meta MCP servers | Add `http://localhost:7778/oauth/callback` (DevTools) and `http://localhost:7779/oauth/callback` (WhatsApp Business Tools) to app `2238810740192680` |
| `MCP-RZP-001` Razorpay MCP | Blocked on the provider: its token endpoint advertises only `client_secret_post` |
| Live QA sends and calls | Nominate a QA recipient. Nothing will be sent to a real customer without one |

## Next, without asking

1. `SEC-ROUTE-005` — triage the 31 routes that pass only on a weak auth marker.
   Several are legitimately public (short-link redirects, `POST /auth/validate`);
   `voice-in/obd`, `voice-in/c2c`, `product-image-gen` and `media-cleanup` need
   real verification. Then enable `audit_route_auth.py --gate` in CI.
2. `DEPLOY-002` — `POST /ai/generate` targets `$LATEST`, not `:live`, bypassing
   the alias model that the other 49 aliased functions rely on.
3. Phase 1 discovery: per-function and per-route inventory joined to IaC,
   permissions, tables, traffic and frontend callers; deployed env values for the
   flag register; provider documentation queues; SDK matrix; cleanup dry-run.
4. `NOTIF-STORE-001` — `PstnNotificationDelivery` is declared in four places with
   no physical table, and `rcs-dlr` defaults `RCS_TABLE` to a table that does not
   exist either. Resolve before Phase 3 designs the notification domain.

New during this session, not yet triaged: GitHub reports **48 Dependabot
vulnerabilities** on the default branch (1 critical, 26 high, 19 moderate, 2 low).
The brief recorded Dependabot as unavailable or disabled, so this is a change.

## Rollback

```bash
aws lambda update-alias --function-name wecare-rcs-dlr          --name live --function-version 6
aws lambda update-alias --function-name wecare-inbound-whatsapp --name live --function-version 37
```

Route and integration restore commands: `docs/prohibited-provider-retirement.md`.
Permissions: `python scripts/apply_unattended_permissions.py --user --restore`.
