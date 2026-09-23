# Work plan — master-prompt phases 5 to 10

Durable state for an unattended run. **This file is the source of truth, not the
conversation.** If a session is interrupted — autocompacted, the Mac sleeps, the window
closes — the next session reads this file and resumes at the first item that is not `DONE`.
That is the whole reason it exists: a fifteen-item run degrades at the tail when the
requirements are remembered rather than re-read.

Repo: `/Users/wecaredigital/wecare-store` · branch `stack` · account `775261844268`
us-east-1

## How to resume

```
cd /Users/wecaredigital/wecare-store
git fetch -q origin && git -c core.editor=true rebase --autostash origin/stack
.venv/bin/python -m pytest -q | tail -3
cat .kiro/work/phases-5-10/plan.md      # this file: find the first non-DONE item
```

Per-item loop, every time:

1. Rediscover live state for that item — never trust a dated count in `bw-crm.md`.
2. Write failing tests first where the behaviour is testable.
3. Implement. Keep new capability behind a flag that defaults off.
4. Gates: `pytest -q` · `npm run typecheck` · `bash scripts/check-provider-policy.sh` ·
   `.venv/bin/python scripts/verify_public_webhook_auth.py --gate` ·
   `.venv/bin/python scripts/audit_route_auth.py --gate`
5. Deploy affected functions: `.venv/bin/python scripts/deploy_all_lambdas.py <fn>` —
   this publishes a version and moves the `live` alias, which is mandatory because the API
   invokes the alias.
6. Live-verify. Record the rollback version **before** deploying.
7. Commit by explicit path, push to `stack`, mark the item `DONE` here in the same commit.

## Standing constraints

Never, in any item:

- Enable `PSTN_BROWSER_ROUTING_ENABLED`, `WA_LIVE_SMOKE_TEST`,
  `PSTN_CONNECTED_NOTIFICATIONS_ENABLED`, or any live-send flag.
- Rotate, read or replace a provider credential. No `secretsmanager get-secret-value`.
- Put a credential on a command line or in a log.
- `git add .` / `-A` / `-u`, bare `git stash`, force push, history rewrite.
- Delete or re-register a WhatsApp number, WABA, phone-number id, or the protected Plivo
  identifiers `+918031830030` / app `12775976954213184` / endpoint `543585900967411`.
- Use PayU, Airtel messaging, Sinch SMS/Voice/WhatsApp, or Plivo SMS.
- Enable Security Hub.
- Sinch RCS is **India only** — see `.kiro/steering/03-sinch-rcs-india-only.md`.

Live QA sends go only to the owner-nominated QA recipient `+918100640044`, and only when a
send is separately authorised. Otherwise use fixtures and record `WAITING_FOR_OWNER`.

## Items

Status is one of `TODO` · `IN_PROGRESS` · `DONE` · `BLOCKED` · `WAITING_FOR_OWNER`.

---

### 5.1 — Plivo softphone: token route, session state, leg distinction · DONE

Commit `921a1417`. `lambda_utils/pstn/softphone.py` + `messaging/pstn-softphone`.
5 routes live, all 401 unauthenticated, browser routing OFF, 58 tests.
Table `PstnSoftphoneSessions` ACTIVE with TTL.

### 5.2 — Plivo callback authentication audit · DONE

Live `wecare-plivo-answer` v14. The premise — "a token nothing checks" — turned out to be
wrong: verification is real. Per route, measured:

| Route | Gate | Verdict |
|---|---|---|
| `POST /plivo/hangup` | V3 signature **required** | verified |
| `POST /plivo/events` | V3 signature **required** | verified |
| `POST /plivo/dial-events` | V3 signature **required** | verified |
| `POST /plivo/answer` | signature when present, else `?token=` | verified, side effects need ≥ `TRUST_TOKEN` |
| `POST /plivo/fallback` | signature when present, else `?token=` | verified |

`answer` and `fallback` cannot require a signature: Plivo does not sign `answer_url`
fetches, so rejecting an unsigned one drops every real call. The privilege is split instead
— XML is served at `TRUST_NONE`, the `CallStatus=completed` SMS pass is not.

Both secrets show `LastAccessedDate` 2026-09-23, so the gate is live rather than silently
degraded to `unverified_no_token_configured`.

**The token does not leak.** Stage `prod` logs `$context.path`, which excludes the query
string, and no handler log site emits the value — only the mechanism name `'token'`.

Two defects found and fixed:

- `qs.get('token') == token` — short-circuits at the first differing byte, in the same file
  whose signature verifier documents why that is wrong. Now `_token_matches` with
  `hmac.compare_digest`, both sides encoded (`compare_digest` raises `TypeError` on a
  non-ASCII str, and a 500 on `/plivo/answer` is a non-XML body, so the caller hears
  silence instead of a clean hangup).
- Unknown path fell through to `(_route_answer, False)`. That is what concealed the
  stage-prefix incident — `/prod/plivo/hangup` "worked" by returning `<Play>` to a hangup
  callback, re-answering a terminated call. Now a 404, refused before `_verify_provider`.

Live: `/plivo/status` → 404 (was 200 + `<Play>`); all five real paths still reach their auth
layer, none 404. 37 tests in `tests/test_plivo_routes.py`.

### 5.3 — PSTN call/event model: provision or retire · TODO

`PstnCall`, `PstnCallEvent`, `PstnAgentPresence`, `PstnFlowVersion`, `PstnRecordingAudit`
are declared in `amplify/data/resource.ts` and **absent from the account**; no Python
references them. Decide per model: provision it because something will write it, or delete
the declaration because nothing will. Do not leave five phantom declarations.

`VoiceCDRTable` holds 36 real rows — that is the live call record today. Check whether any
status write there is unconditional, the way `wa_status` / `rcs_status` / `payment_status`
were.

### 5.4 — Softphone device matrix, contract-level · TODO

Desktop/mobile/Capacitor matrix. Without browser routing enabled there is no live call to
place, so cover what is testable: token TTL and refresh scheduling, `onLoginFailed` code
mapping, reconnect resolving to the same endpoint, and the WebView/WKWebView constraint
that `getUserMedia` needs a secure context. Record the live-call matrix as
`WAITING_FOR_OWNER` with the exact unblock.

### 6.1 — Strip the action group's ungoverned powers · TODO

`ai/agent-action-group` can currently send directly, scan whole tables, delete data, and
report placeholder success. The brief requires all four removed. Route its useful actions
through one deterministic query/command service.

### 6.2 — Versioned READ/PLAN/APPLY tool catalog · TODO

Deploy READ and status tools first, then PLAN/dry-run. **Every APPLY tool stays disabled.**
Immutable plan hashes, idempotency, receipts, audit, kill switches.

### 6.3 — Internal dashboard chatbot on the shared plane · TODO

Must stay useful with remote ChatGPT/Claude/Kiro clients disconnected. Context resolution,
capability discovery, typed task planning, approval preview, durable progress, final
receipts linking to canonical records.

### 6.4 — Reconcile the live Bedrock agent/alias/prepared state · TODO

Rediscover the agent, alias and prepared state; find and fix stale ids.

### 7.1 — Shared integration registry + sync/metric boundary · TODO

Server-side adapters: Google Ads, GA4, Search Console, GBP, Play Reporting, Bing Webmaster,
Meta Ads/CTWA, Wix. READ only, and only where owner access exists — otherwise fixtures plus
`WAITING_FOR_OWNER`. Record scopes, ownership, quota, freshness, provider request ids.
Do not modify any credential.

### 7.2 — Refactor the Meta Ads/attribution and Wix monoliths · TODO

Into query/plan/apply or adapter/domain/job boundaries. Remove interactive scans, browser
token/provider calls, and Wix secret env fallbacks. Route Wix-generated communication
through the shared notification system. **Preserve the existing production Wix site** and
reconcile Velo source drift without creating or publishing a site.

### 7.3 — Growth and Commerce module homes behind flags · TODO

Separately routed inner pages, real backend state, connected-service tutorials,
error/stale/quota states. Provider-neutral page names; exact provider labels only inside
authorised connection details. AI may READ and PLAN; growth/storefront APPLY stays disabled.

### 8.1 — Eight module homes · TODO

Home, Communications, Customers, Commerce, Growth, Service Operations, Platform Operations,
Settings. Separately routed, lazy-loaded inner pages.

**Communications exposes exactly three**: Common Inbox, WhatsApp Business, Business Calling.

### 8.2 — productVocabulary + CI label scan · TODO

Versioned provider-neutral vocabulary across navigation, headings, empty/error states,
breadcrumbs, search, help. Exact provider/resource names only in authorised Technical
Details. Add a CI scan that **fails** on prohibited infrastructure labels in ordinary UI.

### 8.3 — Adaptive navigation + design tokens · TODO

Phone bottom bar, foldable recomposition, tablet rail/sidebar, desktop sidebar. Light-only
Material 3-derived tokens, exact 13px rectangular radius. Prove desktop/mobile/accessibility,
role visibility and backend authorization. Preserve working capability before retiring any
duplicate page.

### 8.4 — Legacy redirects and refresh-safe deep links · TODO

Every retired route redirects; deep links survive a refresh.

### 9.1 — Retire the old notification/Airtel/Sinch-SMS/AWS-Social paths · TODO

Exact manifests, rollback evidence, drain/archive/migrate first. Prove zero live
invocations before deleting anything.

### 9.2 — Route/dependency cleanup and bundle optimization · TODO

Before/after bytes, measured not estimated. 49 Dependabot alerts outstanding (1 critical,
20+ high) — triage them here.

### 9.3 — Native packaging · WAITING_FOR_OWNER

APK/AAB/IPA and signing are **POST-PROJECT** per `.kiro/steering/00-current-owner-overrides.md`
and cannot block closure. The web app must stay WebView/WKWebView-ready, which 8.3 covers.

### 10.1 — Admin MFA · TODO

Required target per the owner overrides (not a blocking gate, but the work stands).
Cognito MFA is currently OFF on pool WECARE.DIGITAL.

### 10.2 — WAF · TODO

Required target. 0 regional WebACLs today. Implement and live-verify.

### 10.3 — Production deployment checkpoint + closure report · TODO

Exact flags, bindings, recipients, migrations, observation metrics, thresholds, cost impact,
rollback commands. Monitor callbacks/notifications/receipts/alarms/Actions/Amplify to
terminal state. Then the final completion/gap/improvement report and the phase-result table.

## Carried-forward gaps

Open, each with a reason, from earlier phases. Fold into the item that touches them.

| Gap | From | Severity |
|---|---|---|
| Meta payment verification defaults `payment_verified = True`, skips lookup when `paymentConfigName` empty | 4d | MEDIUM |
| Invoice phone+amount fallback matches on a float tolerance `< 0.02` | 4d | MEDIUM |
| Five payment vocabularies still coexist in **storage** (`canonical()` maps on read only) | 4d | MEDIUM |
| Invoice sequence failure injects `WD-PAY-TEMP-` into the GST series | 4d | MEDIUM |
| `whatsapp-business-api._save_flow_submission` — 4th Flow writer, different schema, still unguarded; check reachability | 4c | MEDIUM |
| `_handle_flow_data` returns HTTP 200 on a routing exception | 4c | MEDIUM |
| `wecare/sinch/rcs` has no `webhook_secret`; 17 callbacks refused in 30d | RCS | MEDIUM |
| 559 of 730 RCS sends fail — recipients not RCS-capable, not an integration defect | RCS | INFORMATIONAL |
| `rcsmenu` template id/version `UNVERIFIED` | RCS | LOW |
| Google redirect URI + `contacts.readonly` consent scope | 4e | WAITING_FOR_OWNER |
| Truecaller callback registration on developer.truecaller.com | 4e | WAITING_FOR_OWNER |
| 49 Dependabot alerts (1 critical, 20+ high) | — | HIGH |
