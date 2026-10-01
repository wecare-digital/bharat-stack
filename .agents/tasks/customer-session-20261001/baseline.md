# Customer session + OTP hardening — BASELINE (setup only, no implementation)

**Produced** 2026-10-01, Asia/Kolkata. **Changes made to the product: NONE.** No source edit, no
stage, no commit, no push, no deploy, no AWS mutation. Every AWS observation below is a READ
(`sts get-caller-identity`, `cognito-idp list-user-pool-clients`, `describe-user-pool-client` with a
narrowed `--query`, `describe-user-pool` with a narrowed `--query`). No secret value was read and
none appears here or in any command that produced this file. The only file written is this note.

---

## 1. AWS identity — CONFIRMED

| Field | Observed |
|---|---|
| Account | **775261844268** |
| ARN | `arn:aws:iam::775261844268:user/wecare-admin` |
| UserId | `AIDA3JAJU6MWDGITV2A7L` |
| Region (`aws configure get region`) | **us-east-1** |
| `AWS_PROFILE` | **wecare-prod** |

Key-based auth, no browser login, no account switch. Matches `aws-agent-rules.md` exactly.

Interpreter for every Python invocation in this task: `/Users/wecaredigital/wecare-store/.venv/bin/python`
(bare `python` is not on PATH; the system `python3` has no `boto3`).

## 2. Artifact directory

`/Users/wecaredigital/wecare-store/.agents/tasks/customer-session-20261001/` — created (`mkdir -p`).
`.agents/` as a whole is **untracked** in git (see §3), so nothing in here is a commit candidate.

## 3. Git state at setup — HEAD and foreign ownership

```
branch        stack
HEAD          f7304eba16c76cd7beb5f6076e68709fd014340c
```

`git status --short` as found. **Everything in this list belongs to another concurrent session and
must be left exactly as-is** (`multi-session-parallel-agents` rules 4 and 3b):

| State | Path | Treat as |
|---|---|---|
| ` M` | `.kiro/specs/whatsapp-wix-commerce/design.md` | FOREIGN |
| ` M` | `.kiro/specs/whatsapp-wix-commerce/requirements.md` | FOREIGN |
| ` M` | `.kiro/specs/whatsapp-wix-commerce/tasks.md` | FOREIGN |
| ` M` | `.kiro/steering/META-BETA-REQUEST-EMAIL.md` | FOREIGN |
| ` M` | `amplify/functions/payments/razorpay-webhook/handler.py` | FOREIGN + explicit DO-NOT-TOUCH |
| ` M` | `amplify/functions/shared/lambda_utils/ecommerce/order_creation.py` | FOREIGN + explicit DO-NOT-TOUCH |
| ` M` | `docs/execution/change-authority-matrix.md` | FOREIGN (append-only ledger; coordinate, do not rewrite) |
| `??` | `.agents/` | ours for this note; shared dir, write only under our own task folder |
| `??` | `AGENTS.md` | FOREIGN |
| `??` | `amplify/functions/shared/lambda_utils/ecommerce/finalization.py` | FOREIGN + DO-NOT-TOUCH |
| `??` | `amplify/functions/shared/lambda_utils/ecommerce/initiation.py` | FOREIGN + DO-NOT-TOUCH |
| `??` | `docs/execution/checkout-c1-c7-closure-matrix-20261001.md` | FOREIGN + explicit DO-NOT-TOUCH |
| `??` | `docs/execution/checkout-consolidation-findings-20261001.md` | FOREIGN |
| `??` | `docs/execution/first-deep-audit-20261001-codex.md` | FOREIGN (read-only evidence) |
| `??` | `docs/execution/webhook-signature-verification-pattern-20261001.md` | FOREIGN |
| `??` | `scripts/retired_url_equity.py` | FOREIGN |
| `??` | `.kiro/settings/mcp.json.*.bak` (6 files) | FOREIGN tooling backups |

**The tree moved during this setup step, which is direct evidence another session is live right
now.** A re-check minutes later added ` M package.json`, ` M package-lock.json` and `?? vendor/` —
almost certainly the Material ESM dependency work from §14 of the handoff. All three are FOREIGN.
Re-read `git status --short` immediately before any stage, and never assume this list is current.

**The index was clean on arrival** (no first-column entries). That is worth recording because rule
3b exists precisely because of an index that was already dirty. It can go dirty at any moment, so
every commit in this task MUST be:

```
git add <new paths only> && git commit --only <all our paths> -F <message-file>
```

`--only` is **not optional** here: seven foreign modified files plus eleven foreign untracked files
are sitting in a shared tree.

## 4. Owned paths for this whole task

Nothing outside this list may be edited by any step of this task:

- `amplify/functions/auth/**`
- a NEW customer-session Lambda under `amplify/functions/auth/`, its IaC under `amplify/`, and its
  route-provisioning script under `scripts/`
- `src/lib/customerAuth.ts` and new session client code under `src/lib/`
- `src/pages/account/**`
- `src/components/PhoneField.tsx` and `src/lib/dialCodes.ts` — **extend the PR #175 divided-field
  baseline, never regress it** (see §7)
- tests under `src/test/` and `tests/`
- exactly ONE evidence doc: `docs/execution/customer-session-closure-20261001.md`

### DO NOT TOUCH (other sessions own these)

`amplify/functions/payments/**` · `amplify/functions/shared/lambda_utils/ecommerce/**` ·
`amplify/functions/shared/lambda_utils/integrations/razorpay_verify.py` ·
`amplify/functions/ecommerce/checkout/handler.py` · `src/pages/404.tsx` · `_routes.json` ·
`src/components/HeaderCart.tsx` · `docs/execution/checkout-c1-c7-closure-matrix-20261001.md`

Note the overlap hazard: `amplify/functions/shared/lambda_utils/ecommerce/**` is forbidden, and the
customer-session work will want `lambda_utils.customer_auth` / `lambda_utils.otp_throttle` — those
are **not** under `ecommerce/`, so they are reachable, but `rate_limit.py` and friends are shared by
the whole fleet and any change there is a fleet-wide blast radius. Prefer additive new modules.

## 5. Live Cognito customer client — observed, READ-ONLY

Pool `us-east-1_46ULYuukt` (`WECARE.DIGITAL-CUSTOMERS`) has exactly **one** app client:

```
ClientId   4avmt9n4gpmkvkdk88qbtit33o
ClientName wecare-customer-whatsapp-otp
```

(The full `describe-user-pool-client` call was refused by the `block-catastrophic` guard because it
can return `ClientSecret` in cleartext. It was re-run with an explicit `--query` projection that
excludes it. That is the correct way to read a client here.)

**Effective configured lifetimes, with units stated — this is the part later steps must design
against, not guess at:**

| Field | Value | Unit | Effective |
|---|---|---|---|
| `AccessTokenValidity` | 60 | `minutes` | **60 minutes** |
| `IdTokenValidity` | 60 | `minutes` | **60 minutes** |
| `RefreshTokenValidity` | 30 | `days` | **30 days** |
| `AuthSessionValidity` | 10 | minutes (fixed unit) | 10 minutes — the CUSTOM_AUTH challenge window |

| Field | Value | Consequence |
|---|---|---|
| `ExplicitAuthFlows` | `ALLOW_CUSTOM_AUTH`, `ALLOW_REFRESH_TOKEN_AUTH` | **Refresh is already permitted.** No `UpdateUserPoolClient` is needed to enable remembered login. |
| `EnableTokenRevocation` | **true** | A refresh token can be revoked server-side — so "sign out everywhere" is implementable. |
| `PreventUserExistenceErrors` | `ENABLED` | Unknown numbers still get a masked challenge; the `registered` flag in the trigger is the only signal. |
| `EnablePropagateAdditionalUserContextData` | **false** | No client IP / user-agent reaches advanced security or the triggers. Per-IP limiting is structurally unavailable in the trigger. |
| `CallbackURLs`, `AllowedOAuthFlows`, `SupportedIdentityProviders` | **null** | No hosted UI / OAuth. Everything is raw `InitiateAuth` / `RespondToAuthChallenge` from the browser. |
| `ReadAttributes`, `WriteAttributes` | null | Defaults. |

Pool-level, same read:

| Field | Value |
|---|---|
| `DeviceConfiguration` | **null** — **device remembering is OFF**, so `DEVICE_SRP_AUTH` / remembered-device suppression is not available |
| `MfaConfiguration` | `OFF` |
| `UsernameAttributes` | `["phone_number"]` |
| `AdminCreateUserConfig.AllowAdminCreateUserOnly` | **true** (self-signup closed) |
| `LambdaConfig` Define/Create/Verify AuthChallenge | all three → `arn:aws:lambda:us-east-1:775261844268:function:wecare-customer-whatsapp-auth:live` |

No rotation state exists to report: there is no client secret rotation concept here, and
`describe` shows a single client with no OAuth config. **No mutation was attempted.** Any future
pool change must go through `scripts/cognito_pool_safe_update.py` — `UpdateUserPool` is a full
replace and silently wiped these three triggers once already (2026-09-28).

## 6. Facts from the three evidence docs — all marked RE-VERIFY, none trusted

These are dated claims from `.agents/tasks/section68-current-state-audit-20261001.md` (HEAD
`c082d586`), `.agents/tasks/deep-audit-20261001b.md` (HEAD `8807db0e`) and
`docs/execution/first-deep-audit-20261001-codex.md`. HEAD is now `f7304eba`, so **every one must be
re-measured before it is relied on.**

| # | Claim | Why it matters to this task | Re-verify by |
|---|---|---|---|
| R1 | `wecare-customer-registration` and `wecare-email-verification` **do not exist in AWS** | the sign-in page already posts to `/auth/customer-registration` | `GetFunctionConfiguration` on both names |
| R2 | **Zero** API routes match `auth` except `POST /auth/validate`; 359 routes, **0 authorizers** | our new session Lambda needs a route, and there is no gateway authorizer to lean on | `GetRoutes` + `GetAuthorizers` on `zllr9lrg7j` |
| R3 | `/account/sign-in/` returns **200 live** while `/api/auth/customer-registration` returns **404** | a real shopper can reach a dead register path today — the single highest-impact finding | HTTP probe of both |
| R4 | `stack-wecare-digital-CustomersTable` **does not exist** | registration + profile ownership has no store | `DescribeTable` |
| R5 | Secret `wecare/otp/pepper` **does not exist** (`OTP_PEPPER_SECRET_ID` default) | OTP hashing has no pepper | `DescribeSecret` metadata only |
| R6 | Pool schema lacks `custom:customer_id`, yet `customer-registration/handler.py` stamps it | would fail at provision time; schema attrs cannot be added after creation | narrowed `describe-user-pool` on `SchemaAttributes` |
| R7 | Live OTP-role policy **allows `UpdateItem` but denies `PutItem`** — and `_consume_send_budget` uses `put_item` on window rollover | the fail-closed send throttle would **refuse every send** after a window roll | `iam simulate-principal-policy` (READ) |
| R8 | Same-phone registration creates **two** customer IDs; an unauthenticated verified-email fixture stamps a body-selected customer | these are the session/ownership defects this task exists to close | re-run the offline reproductions |
| R9 | Working tree had **20 failing tests** vs a green HEAD, all inside the foreign payment work | our gate must separate our failures from theirs | `pytest tests/ -q` now, plus the focused subset |
| R10 | `OTP_PROBE_TABLE` / `OTP_SEND_TABLE` default to `stack-wecare-digital-DownloadGrantsTable` | an OTP counter living in the downloads table is surprising; confirm the live env | `GetFunctionConfiguration wecare-customer-whatsapp-auth` |
| R11 | `wecare-customer-whatsapp-auth` `live` alias was at version 10 | rollback target for any deploy (not in this task's scope) | `GetAlias` |
| R12 | Steering counts (361 routes, 58/65 aliases) are stale snapshots | do not quote them | the execution rule: re-derive |

## 7. Source of record, read today

### `src/lib/customerAuth.ts`
Raw Cognito IDP REST from the browser — no SDK, no credentials, `GenerateSecret: false` so no
`SECRET_HASH`. `requestOtp` → `InitiateAuth` `CUSTOM_AUTH`; `submitOtp` → `RespondToAuthChallenge`,
returning `null` (not throwing) when the code was wrong but attempts remain.

**The gap this task is about, stated plainly:** it stores **only the access token**, in
`sessionStorage`, under `wecare.customer.accessToken` / `wecare.customer.expiresAt`, with a 30-second
early-expiry grace. It **never captures `RefreshToken` or `IdToken`** and there is no
`REFRESH_TOKEN_AUTH` call anywhere in `src/` or `amplify/functions/auth/` (grepped: zero hits). So:

- the session dies at 60 minutes with no renewal, mid-checkout;
- it dies when the tab closes (deliberate, documented, and the right default for a shared browser);
- the 30-day refresh token the client is already configured to issue is **discarded unused**.

`normaliseMobile()` infers `+91` for ten digits starting 6-9 and its docblock forbids divergence from
the backend's normalisation byte-for-byte. `customer-whatsapp-auth/handler.py::_normalise_phone`
implements the identical rule (digits-only, same 6-9 prefix, same 10..15 length bound) — they agree
today. **Any change to either is a two-sided change.**

### `src/components/PhoneField.tsx` + `src/lib/dialCodes.ts` — the PR #175 baseline to EXTEND
One divided field: a `<select>` country-code segment and a `tel-national` `<input>`, inside a single
10px-radius outlined container, 52px min-height, `border-inline-end` hairline divider, **per-segment
inset focus rings** (`outline-offset:-3px`) because two focusable controls in one box cannot share
one ring without failing WCAG 2.4.7. `aria-label="Country code"` on the select, with the documented
cost that attribute text is not translated by the support widget's text-node walker. No red for the
invalid state, on standing owner instruction. 20 dial codes, India first, `DEFAULT_DIAL_CODE='+91'`
as a **visible** default rather than an inference. **Do not regress any of this**, and note that
`src/pages/workspace/contacts/index.tsx` imports `DIAL_CODES` too, so the list is shared.

### `src/pages/account/sign-in.tsx` (567 lines)
The only file under `src/pages/account/`. Composes the dial code ahead of `normaliseMobile` so there
is nothing left to infer; rejects a contradictory pasted prefix rather than concatenating; routes an
unregistered number to `POST /auth/customer-registration` (`request` then `verify`) and then makes
the shopper complete a **second**, Cognito-issued code — registration never returns a session
credential. Carries the owner's verbatim `MSG` table, including `NOT_ON_WHATSAPP` defined-but-unused
until Meta's recipient-not-found code is surfaced. Registered in the `_app.tsx` `isPublic` chain,
`noindex`, inherits Header/Footer centrally.

### `amplify/functions/auth/**` — four handlers, no new ones
`customer-whatsapp-auth/handler.py` (389) · `customer-registration/handler.py` (406) ·
`email-verification/handler.py` (287) · `cognito-custom-message/handler.py` (279).

`customer-whatsapp-auth` is the one that matters most. Two **separate** per-phone counters in
`stack-wecare-digital-DownloadGrantsTable` under distinct key prefixes, failing in deliberately
opposite directions:

| Counter | Key | Window / cap | Direction |
|---|---|---|---|
| probe (unregistered reveal) | `otpprobe#<digits>` | 3600s / 5 | **fails OPEN** — a DynamoDB blip must not lock a customer out |
| send (registered numbers) | `otpsend#<digits>` | 3600s / 5 | **fails CLOSED** — it guards a real handset and real money |

Over the send budget, the challenge is still issued and only the outbound message is suppressed, so
the limit is invisible from outside and cannot itself be probed. `registered` is `true` / `false` /
`unknown`, the last being the throttled answer. `userName` is read **top-level** (reading it from
`request` yielded `''` and silently skipped the budget — a fixed bug worth not reintroducing).
Fails closed when `custom:partner_waba_id != META_WABA_ID`. `MAX_ATTEMPTS=3`, `OTP_TTL_SECONDS=600`,
constant-time compare, OTP never logged.

**R7 is the live threat to this design:** if `PutItem` is genuinely denied to the function's role,
the fail-closed rollover path raises `OtpSendThrottled` on every window roll and **silently stops
sending OTPs**. Verify before building on it.

## 8. Standing constraints restated for later steps

No deploy. No AWS mutation (reads only). No `update-user-pool` / `update-user-pool-client` in any
form. No `secretsmanager get-secret-value` in any spelling. No credential on a command line, in a
log, or in a report. No live send — QA recipient `+918100640044` is nominated but a monetary or
message test needs its own authorized scope, and `WA_LIVE_SMOKE_TEST` is a lockdown, not a
permission. Single branch `stack`; no fetch, reset, rebase, stash, force push or history rewrite.
`captured` must never appear as a raw string literal at a decision point — route through
`lambda_utils/payment_status.py` (pinned by `tests/test_payment_vocabulary_at_decision_points.py`,
which walks the AST, not the text).

---

## Open question for the design phase

**How long should a remembered customer session last, and where is the refresh token allowed to
live?** The client already permits `ALLOW_REFRESH_TOKEN_AUTH`, already issues a **30-day** refresh
token, and already has `EnableTokenRevocation: true` — so the capability is live and unused. But
`customerAuth.ts` deliberately chose `sessionStorage` so a shared or public browser keeps nothing
after the tab closes, and persisting a 30-day refresh token to `localStorage` reverses exactly that
decision for a phone-keyed account with **no MFA** and **no device remembering**. The alternatives
are materially different products: (a) keep it in-memory and accept re-OTP on every tab; (b)
`localStorage` refresh with explicit "remember me" consent plus a visible sign-out that calls
`RevokeToken`; or (c) move the refresh token out of JavaScript's reach entirely behind the new
customer-session Lambda as an `HttpOnly; Secure; SameSite` cookie, which is the only option that
survives an XSS on this origin — and the only one that needs a backend, a route, and a CSRF story.
That is a product and security decision with a visible shopper-facing consequence, so it belongs to
the owner, not to the implementation loop.
