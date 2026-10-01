# Backend-owned customer session + identity/OTP hardening — TECHNICAL DESIGN

**Written** 2026-10-01, Asia/Kolkata. **Pass 3 — REVISION.** `design-review.json` was present
(verdict `CHANGES_REQUESTED`, pass 3, 3 HIGH / 7 MEDIUM / 3 NIT), so this document resolves every
one of its thirteen findings. §18 lists each finding and what was done about it; §17 keeps the
pass-2 responses so the history is readable.

The pass-3 changes are concentrated where the review said they were: **the new-customer branch of
§8.8 and the IAM that has to carry it.** Finding 1 had no implementable mechanism, and closing it
changed the architecture of a first session — a first session is now **tokenless**, minted from our
own verified phone-ownership challenge, and the `SUPPRESS_SEND` client-metadata flag pass 2
introduced is **deleted** rather than secured, because an attacker-writable trust channel on an
unauthenticated API is not worth defending. Findings 2 and 3 added three missing IAM actions and
changed `--verify`'s contract from "every statement in the policy" to "every (action, resource) pair
the handler can reach", which is the only version of that check that can catch the next omission.

**Status: DESIGN ONLY. Nothing in this document has been built, deployed or mutated.** Every AWS
call made while writing it was a read. No secret value was read, printed, or placed on a command
line. `secretsmanager get-secret-value` / `batch-get-secret-value` were not called in any spelling.

Baseline: `.agents/tasks/customer-session-20261001/baseline.md`.
Review: `.agents/tasks/customer-session-20261001/design-review.md`.

> **Reading convention for "finding N".** There have been two review passes and they number
> independently, so a bare `finding N` in the body is scoped by the measurement it cites:
> **a passage citing M19–M24 is a pass-3 finding**, and one citing only M1–M18 (or no `M` at all) is a
> pass-2 finding. §18 is the authoritative map for pass 3 and §17 for pass 2; where a pass-2 passage
> was later superseded, the §17 row says so rather than being silently edited.
HEAD at pass-1 authoring `f7304eba16c76cd7beb5f6076e68709fd014340c`; at pass-2 review `25eace2039…`;
at pass-2 revision `2ec84830bd629015e5e356cc26231d7dd5594765`, branch `stack`. The tree has moved
several commits under another session throughout; the foreign-file list in baseline §3 is already
stale and §15.10's re-read-before-staging rule is what covers that, not this header.

---

## 0. Re-measured facts this design is built on

The baseline marked twelve claims RE-VERIFY. The ones this design depends on were re-measured
today, read-only, and the results below are what the design is built against. Anything not
re-measured is named as such and is not load-bearing.

| # | Measured today | Result | Consequence here |
|---|---|---|---|
| M1 | `amplify get-app d22dm4b0jn71jw --query app.customRules` | 146 rules; one is `"/api/<*>" -> "https://zllr9lrg7j.execute-api.us-east-1.amazonaws.com/prod/<*>"` status **200** | **The same-origin API path is already live.** This is the single most important finding and it decides the crux in §2 |
| M2 | `POST https://wecare.digital/api/auth/validate`, no auth header | `401 {"error":"No authorization token provided"}`, response carries `apigw-requestid` | The proxy reaches API Gateway and returns the origin's own non-standard response headers to the viewer |
| M3 | Same, with `authorization: Bearer not-a-real-token` | `401 {"error":"Invalid or expired token"}` — a **different** handler branch | The proxy forwards the `Authorization` **request** header end to end. Arbitrary request headers survive the rewrite |
| M4 | `OPTIONS` through the proxy | `204`, `access-control-allow-origin: https://wecare.digital`, **no** `access-control-allow-credentials` | Gateway CORS exists but is credential-less. Irrelevant on the same-origin path (no CORS applies); relevant to the rejected alternative |
| M5 | `get-api zllr9lrg7j` | `CorsConfiguration.AllowCredentials: **false**`, `AllowHeaders` has no CSRF header, `ProtocolType: HTTP` | A credentialed cross-origin design would need a gateway-level CORS mutation. The chosen design needs none |
| M6 | `get-integrations zllr9lrg7j` | every integration `AWS_PROXY`, `PayloadFormatVersion: **2.0**` | The response `cookies: []` key and the request `event["cookies"]` list are both available. No `multiValueHeaders` workaround needed |
| M7 | `describe-user-pool-client` (narrowed projection, `ClientSecret` excluded) | `RefreshTokenRotation: **null**`, `ExplicitAuthFlows: [ALLOW_CUSTOM_AUTH, ALLOW_REFRESH_TOKEN_AUTH]`, `EnableTokenRevocation: true`, Access/Id **60 minutes**, Refresh **30 days**, `AuthSession 10 min`, `PreventUserExistenceErrors: ENABLED`, `EnablePropagateAdditionalUserContextData: false`, no OAuth/callback config | **Rotation is OFF**, so `REFRESH_TOKEN_AUTH` is the correct and supported flow and `GetTokensFromRefreshToken` is *not* required today. **No app-client change is needed for any of this design.** |
| M8 | `get-function-configuration` on three names | `wecare-customer-registration`, `wecare-email-verification` and `wecare-customer-session` all `ResourceNotFoundException` | R1 confirmed. The registration handler in source is **not deployed**, and the new function name is free |
| M9 | `get-function-configuration wecare-customer-whatsapp-auth` | role `wecare-customer-whatsapp-auth-role`; env has **no** `OTP_PROBE_TABLE`/`OTP_SEND_TABLE`, so both default to `stack-wecare-digital-DownloadGrantsTable` | R10 confirmed: the OTP counters live in the downloads table |
| M10 | `iam simulate-principal-policy` on that role against that table | `PutItem` **implicitDeny**, `UpdateItem` allowed, `GetItem` implicitDeny, `Query` implicitDeny | **R7 confirmed as a live defect.** See §8.6 |
| M11 | `get-role-policy wecare-otp-probe-counter` | one statement, `dynamodb:UpdateItem` only, on that one table | The role is **dedicated**, not the shared fleet role. A narrow addition here has no fleet blast radius |
| M12 | `describe-table` / `describe-secret` | `stack-wecare-digital-CustomersTable` **absent**; `wecare/otp/pepper` **absent**; `stack-wecare-digital-CustomerSessionsTable` absent | R4 and R5 confirmed. Both are preconditions for anything in §8 to function once deployed |
| M13 | `dig api.wecare.digital`, `dig app.wecare.digital` | both empty | No API subdomain exists. The cross-origin alternative in §2 would need a DNS change, which is prohibited for this run |
| M14 | repo grep for `Set-Cookie`, `document.cookie`, `credentials:'include'` | zero hits in `amplify/functions/**` and `src/**` (one unrelated string in a test fixture) | This is greenfield. No existing cookie behaviour can be regressed, and no live endpoint exists to measure cookie transport against — see precondition **P1** |

### Measured during this revision (pass 2), all reads

| # | Measured | Result | Consequence here |
|---|---|---|---|
| **M15** | `lambda get-function-configuration wecare-wix-store --query Role` | `arn:aws:iam::775261844268:role/**wecare-digital-lambda-role**` — the **shared fleet role** | **This is the measurement that decides §4.2.** `wix-store` is one of the two handlers that must resolve a cookie, and it runs on the role shared by the whole fleet. Granting that role `GetItem` + `kms:Decrypt` on a table holding refresh tokens would hand every function in the account read access to every customer's 30-day credential. Pass 1's "the only principal with both is `wecare-customer-session-role`" was not merely optimistic, it was unachievable. The custody split in §4.2 is therefore **mandatory, not preferred** |
| **M16** | `lambda list-functions` filtered for `checkout` | `wecare-checkout` is **absent**; `scripts/provision_checkout.py:49` sets `ROLE_NAME = "wecare-checkout-role"` | The second cookie-resolving handler is not deployed yet and will arrive on its **own dedicated** role. So the two consumers of `resolve` sit on two different roles, neither of them the session role — confirming review finding 3 from both sides |
| **M17** | source read of `otp_challenge._digest` call sites | `_digest(pepper, "subject", purpose, subject)` and `_digest(pepper, "code", purpose, subject, code)` — the code digest already passes four parts | The `*extra` passthrough in finding 9 must reach **both** digests or a key and its code digest would disagree. §8.3 now specifies both |
| **M18** | source read of `ecommerce/customer_cart.py:_key` | `re.fullmatch(r"\+[1-9][0-9]{7,14}", identity.phone or "")` then `"CUSTOMERCART#" + identity.phone` | The cart partition key **is** the E.164 phone. Finding 2 confirmed: a cookie-derived identity with `phone=""` breaks the cart, so `normalizedPhone` must be on the resolution record |

### Measured during this revision (pass 3) — all SOURCE reads, no AWS call

Pass 3's findings were all about the seam between this design and existing code, so the checks are
reads of that code. **No AWS call was made in this pass**, so M1–M18 still carry their earlier dates.

| # | Measured | Result | Consequence here |
|---|---|---|---|
| **M19** | `otp_challenge.py` — how `issue` creates its row | `table.put_item(Item=item)` at **line 270** | **`dynamodb:PutItem` is required** on the throttle/challenge table. Pass 2's "No `PutItem`" was wrong and would have failed the unknown-number branch on its first call (§11.1.1, finding 2) |
| **M20** | the only non-trigger WhatsApp send path | `customer-registration/handler.py:94` `SENDER_FUNCTION = "wecare-whatsapp-business-api:live"`, invoked at `:187`; identical pair at `customer-whatsapp-auth/handler.py:37`, `:225` | **`lambda:InvokeFunction` on that one alias is required.** `identity/registration.py::begin` takes `send_code` injected and invokes nothing itself, so there is no alternative path (§11.1.1, finding 3) |
| **M21** | the email send path | `email-verification/handler.py:108` `boto3.client("sesv2")`; `comms/verification_email.py:279` `send_email(FromEmailAddress="WECARE.DIGITAL <one@wecare.digital>", ConfigurationSetName="wecare-digital")`, both overridable by env (`VERIFICATION_EMAIL_SENDER`, `SES_CONFIGURATION_SET`) | **`ses:SendEmail` is required**, on the identity **and** the configuration set, because SESv2 authorises a send that names a configuration set against both resources (§11.1.1, finding 3) |
| **M22** | `_create_auth_challenge` in `customer-whatsapp-auth/handler.py` | the code is generated at `:267` and written only to `event["response"]["privateChallengeParameters"]["answer"]` at `:270-273`. Cognito delivers private challenge parameters **only** to `VerifyAuthChallengeResponse`. `grep clientMetadata` in that handler: **zero hits** | **Pass 2's "server-held answer" was unimplementable.** It is replaced by a tokenless first session (§8.8 step 6b.iv) and `SUPPRESS_SEND` is deleted (finding 1) |
| **M23** | `customer_auth.py:84`; `identity/customer.py:147`; `PhoneField.tsx:134` vs `:106` | `CustomerIdentity.__slots__ = ("customer_id","phone","subject")`; `normalize_phone` accepts **`10 <= len(digits) <= 15`** and otherwise raises `InvalidPhoneNumber`; `required` is on the `tel-national` **`<input>`**, not on the `<select>` | drives findings 7, 12 and 13: a subclass with its own `__slots__` (§4.2), a **10–15** digit bound with the delegate's exception mapped (§9.2, §10), and corrected prose about `required` (§9.2) |
| **M24** | `customer-registration/handler.py::_provision_login` | `admin_create_user(..., MessageAction="SUPPRESS")` then `admin_set_user_password(Permanent=True)`; `UsernameExistsException` → `admin_update_user_attributes` | the provisioning shape §8.8 step 6b.iii reuses, including the already-correct message suppression — so the new flow needs no trigger change to stay silent (finding 1) |

**Not re-measured, and therefore not relied on:** R2 (route/authorizer counts), R3 (live page
probes), R6 (pool `SchemaAttributes`), R9 (test-suite baseline), R11 (`live` alias version), R12
(steering counts). **R6 is promoted** by this revision: finding 4 showed it is blocking for a *new*
customer's first sign-in, not merely for `customer-registration` deployment, so §7.1 C-1 is now a
blocking precondition and §12 reads `SchemaAttributes` before step 2. The review did not re-run
M1–M14 either, so every conclusion resting on M1, M5, M7, M10 or M12 still rests on a pass-1 read.

---

## 1. Overview

Today a customer session is **one Cognito access token in `sessionStorage`**
(`src/lib/customerAuth.ts`). It dies at 60 minutes with no renewal, dies when the tab closes, and
the 30-day refresh token the app client is already configured to issue is captured nowhere and
discarded. Every customer-facing backend check is a `Bearer` token read by
`lambda_utils.customer_auth`, and there is no gateway authorizer behind it.

This design moves custody of the Cognito tokens to the backend and gives the browser an **opaque
session id in a `__Host-` prefixed, `Secure`, `HttpOnly`, host-only cookie**. One new Lambda,
`wecare-customer-session`, owns the cookie, the session record, the refresh cycle and CSRF. Two
new shared modules make the session readable by the customer endpoints that already exist, without
editing those handlers. The Cognito `CUSTOM_AUTH` WhatsApp-OTP flow is unchanged as the *proof of
phone ownership*; what changes is who holds the resulting tokens and for how long.

Alongside that, the identity defects the baseline exists to close are fixed: one phone can no
longer mint two customer ids, no mutation is derived from a body-selected customer id, email
ownership is proven against the authenticated session rather than asserted, and the OTP send
counter stops silently refusing every send after a window roll.

**Technology stack, locked by this document:** Python 3.12 Lambda (zip, no container, no layer —
the shared `lambda_utils` tree is packaged, exactly as `provision_customer_registration.py` does
it); `boto3` only, no new runtime dependency; DynamoDB `PAY_PER_REQUEST` with a customer-managed
KMS key and TTL; API Gateway HTTP API `zllr9lrg7j` payload format 2.0; frontend React 19 / Next 16
static export with `styled-jsx`, `fetch`, no new npm dependency, no state library. Provisioning is
a boto3 script in `scripts/`, matching the eleven existing `provision_*.py` scripts; there is no
CDK or CloudFormation in this part of the repo and this design does not introduce one.

---

## 2. THE CRUX — same-origin BFF, decided

**Decision: the session lives on the existing SAME-ORIGIN path `https://wecare.digital/api/*`.
The deliberate credentialed cross-origin architecture is REJECTED.**

### Why this is available at all

The premise that a static export has no same-origin backend is **false for this app**, and M1 is
why. Amplify Hosting app `d22dm4b0jn71jw` already carries a status-200 rewrite:

```
/api/<*>  ->  https://zllr9lrg7j.execute-api.us-east-1.amazonaws.com/prod/<*>
```

`src/config/constants.ts:20` resolves `API_BASE` to `https://wecare.digital/api`, and every
customer-facing call in `src/` already goes through it. The browser's origin for an API call is
therefore `https://wecare.digital` — identical to the document origin. A `Set-Cookie` with no
`Domain` attribute on a response to `https://wecare.digital/api/...` becomes a **host-only cookie
for `wecare.digital`**, because the browser scopes the cookie by the URL it requested, not by
whatever host the reverse proxy spoke to.

**One correction from the review, and the imprecision was load-bearing.** Pass 1 said `constants.ts`
"hardcodes" that value. It does not:

```ts
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://wecare.digital/api';
```

It is a **default**, `output:'export'` inlines every `NEXT_PUBLIC_*` value into a JS chunk at build
time (`amplify.yml:48`), and the same pattern is repeated in at least eight more files. So the
same-origin premise this whole design rests on is one Amplify environment variable away from being
false — and setting `NEXT_PUBLIC_API_BASE` to the `execute-api` host is a plausible one-line "fix" for
some future CORS complaint. The consequence would be silent: every cookie becomes third-party, Safari
drops it, shoppers are signed out, and **nothing logs an error anywhere**. That is exactly the failure
class this section rejected the cross-origin architecture to avoid, arriving through the back door.

So the premise is made to fail loudly instead:

1. `src/lib/customerSession.ts` derives its base from **`window.location.origin + '/api'`**, not from
   `API_BASE`. The session client cannot be relocated by an env var at all.
2. The invariant `new URL(API_BASE, location.href).origin === location.origin` is checked in three
   places, and **none of them is module evaluation** — see the next subsection, which is review
   finding 10 and corrects pass 2 on this point.
3. T-10 gains a vitest case that fails when `NEXT_PUBLIC_API_BASE` resolves cross-origin, so the
   premise is pinned by the suite and not only by this paragraph.

#### Where the invariant is checked, and why NOT at module load

Pass 2 said the session client "asserts at module load … and throws if not". That is the wrong place,
and the review was right that it inverts the failure it is trying to prevent. `src/lib/customerSession.ts`
is a **statically imported** module of `/account/sign-in`, and a module that throws during evaluation
takes the importing page down — in a static export that is a blank or error-boundary render. So a
mis-set `NEXT_PUBLIC_API_BASE` would destroy the **only page that can recover from it**, including the
`customerAuth` Bearer path that §12 step 6 and step 7's rollback both depend on, for a cookie feature
that may well be switched **off**. The guard would convert a cookie-transport problem into a total loss
of sign-in.

It is also checked in the wrong era: the value is inlined at **build** time (`output:'export'`,
`amplify.yml:48`), so the useful moment to fail is the build, not the thousandth page view.

> **`src/lib/customerSession.ts` MUST NOT throw during module evaluation, under any input.** That is a
> hard rule on the file, asserted by T-10 (import the module with a cross-origin
> `NEXT_PUBLIC_API_BASE` and assert the import itself resolves).

The three checks, in order of when they fire:

| When | Mechanism | On failure |
|---|---|---|
| build | a `prebuild` check in `package.json`'s script chain — **note `package.json` is FOREIGN (§11.3)**, so if it cannot be edited this check ships as `scripts/check_same_origin_api_base.py` wired into the existing test gate instead, and §11.1 lists both | `npm run build` (or the gate) **fails**. This is the hard stop |
| test | T-10, vitest | the suite fails |
| runtime | evaluated **lazily on first use**, memoised, logged **once** | every exported function returns a typed `{ ok: false, code: 'ORIGIN_MISCONFIGURED' }`; nothing is sent, no cookie is attempted, and `customerAuth`'s Bearer path serves the page unaffected |

`ORIGIN_MISCONFIGURED` is deliberately **not** in `requiresReauth`'s set (§6.4), so a misconfiguration
shows `MSG.TRY_LATER` and never starts an OTP. The single log line is
`{"event":"session_origin_misconfigured"}` with **no URL, no origin value and no env value** — an
origin is not a secret, but a log that echoes build configuration back is a habit this repo has already
paid for, and the event name is sufficient to diagnose it.

This is what makes §12 step 6's "nothing changes for shoppers" true **unconditionally** rather than
true-if-the-env-var-is-right, which is in turn what makes the step reversible.

Assumption 2 in §16 is restated accordingly: the premise is the rewrite **and** an unset or same-origin
`NEXT_PUBLIC_API_BASE`, not the rewrite alone.

So the static export does not need to set the cookie. It never does. The server sets it, through a
proxy that M2/M3 prove is transparent to the origin's own request and response headers.

### Why the alternative is rejected

A credentialed cross-origin design would talk to
`https://zllr9lrg7j.execute-api.us-east-1.amazonaws.com` directly. Four reasons that is the worse
architecture here, in descending order of weight:

1. **The cookie would be third-party.** `execute-api.us-east-1.amazonaws.com` and `wecare.digital`
   are different registrable domains, so the cookie needs `SameSite=None; Secure` and is a
   cross-site cookie. Safari blocks those outright under ITP, and Chrome's third-party cookie
   posture is not something a payment flow should be betting on. A large share of this store's
   traffic is mobile Safari in India. This alone is disqualifying.
2. **It needs a gateway CORS mutation.** M5 measured `AllowCredentials: false` on the shared HTTP
   API, with no CSRF header in `AllowHeaders`. Flipping `AllowCredentials` to `true` on an API
   whose 359+ routes report `AuthorizationType=NONE` widens the credentialed surface of **every**
   route, not just ours — for a session only one route needs.
3. **The naturally-same-site version needs DNS.** `api.wecare.digital` would be same-site (so no
   ITP problem) and is the architecture I would otherwise reach for — but M13 shows it does not
   exist, and standing it up means an ACM certificate, an API Gateway custom domain and a Route 53
   record. **DNS changes are prohibited for this run.** It is reported in §13, not built.
4. `__Host-` cookies would still work cross-origin, but nothing else about that path is simpler,
   and the frontend would need `credentials: 'include'` on every call plus a preflight on every
   mutation (M4 shows preflights are already 600s-cached but credential-less).

Same-origin additionally buys three things worth naming: **no CORS at all** on the session
endpoints (so no `Access-Control-Allow-Credentials`, no origin echo, no `Vary: Origin` subtleties
to get wrong), **`SameSite=Lax` works** (see §4.3), and `Sec-Fetch-Site: same-origin` becomes a
usable second CSRF gate.

### P1 — the one precondition, and it is a measurement, not an assumption

M14 found no cookie anywhere in this repo, which means **no live endpoint exists against which
cookie transport through the Amplify rewrite can be measured today**. What is proven is M3: the
proxy forwards `Authorization`, a request header it has no reason to treat specially, and returns
the origin's `apigw-requestid`. `Cookie` and `Set-Cookie` are the two headers a CDN is most likely
to special-case, so extrapolating from M3 would be exactly the kind of confident guess this
repository keeps paying for.

So it is a named gate:

> **P1.** Before the cookie becomes the only customer credential, prove end to end through
> `https://wecare.digital/api/...` that (a) a `Set-Cookie` emitted by the Lambda reaches the
> browser with its attributes intact, (b) the browser's `Cookie` header reaches the Lambda, and
> (c) **at least one of `Sec-Fetch-Site` and `Origin` reaches the Lambda intact on a same-origin
> `POST`** — because CSRF Gate 2 (§4.6) fails closed on exactly those two headers.

Part (c) is review finding 8, and leaving it out of P1 was the same mistake P1 exists to prevent.
`Sec-Fetch-Site` is in precisely the position `Cookie` is in: a browser-added request header that an
Amplify-managed distribution may or may not forward to a rewrite origin. If it does not arrive and
Gate 2 is unchanged, **every** mutating cookie request answers `403 CSRF_REQUIRED` — which §6.4
deliberately does *not* route to sign-in, so the shopper gets a cart that silently refuses to change
with no recovery path. That is a worse outcome than the cookie failure P1 was written to catch, and
pass 2 did not measure it.

P1 is implemented as `scripts/provision_customer_session.py --verify-cookie-transport`, which
`POST`s to `/customer/session/echo` — a route that exists only to answer "did the round trip keep
what the gates need". It returns **booleans and one enumerated string, never a value**:

```json
{"setCookieAttempted": true, "cookiePresent": true,
 "secFetchSitePresent": true, "secFetchSiteValue": "same-origin",
 "secFetchModePresent": true, "originPresent": true}
```

`secFetchSiteValue` is echoed because it is a fixed four-value enum (`same-origin`, `same-site`,
`cross-site`, `none`) and the gate's whole decision is which one arrived; it is not caller-supplied
data in any useful sense. **No cookie value, no cookie name list beyond `__Host-wd_cs`, and no
`Origin` value** appear in the response — `originPresent` is a boolean, and whether the value is
correct is decided server-side and reported as a boolean too.

**The P1 verdict, and the one degraded mode that is allowed:**

| Measured | Verdict |
|---|---|
| cookie round-trips **and** `Sec-Fetch-Site: same-origin` arrives | **PASS.** Gate 2 as specified in §4.6 |
| cookie round-trips, `Sec-Fetch-Site` stripped, `Origin` arrives | **PASS, DEGRADED.** Gate 2 becomes Origin-only: `Origin` must be **present** and exactly `https://wecare.digital`. Gate 1 is unchanged and still mandatory. Recorded in the evidence doc as a **measured degradation**, not a preference, and T-04 drives this configuration too |
| cookie round-trips, **neither** header arrives | **FAIL.** Gate 2 is unimplementable through the rewrite. Do **not** ship §12 step 7 on Gate 1 alone — apply the C-3 contingency |
| cookie does not round-trip | **FAIL.** C-3 contingency |

It cannot run in this task because it needs the function deployed, and deployment is out of scope.
The rollout order in §12 therefore puts P1 **before** the step that stops the frontend writing a
token to `sessionStorage`, so a P1 failure costs nothing shipped.

**If P1 fails**, the contingency is the `api.wecare.digital` same-site custom domain from
rejected-reason 3, which needs a DNS record and owner sign-off. It is reported in §13 and is **not
implemented, not scripted and not scheduled** by this design. No fallback that puts a refresh token
or an access token into `localStorage`/`sessionStorage` is acceptable, and none is offered.

### One consequence worth stating before it surprises someone

`wecare.digital` serves both the customer storefront and the `/workspace/*` staff app from one
origin. A host-only cookie on that host is therefore attached to `/api/*` requests made by the
staff app too. **Cookie scope is not the control that keeps the two sessions apart** — §4.4 is.

---

## 3. Shape of the thing

```
browser (static export, wecare.digital)
  │  fetch('/api/customer/session', {method:'POST', ...})   same-origin, no CORS
  │  Cookie: __Host-wd_cs=<opaque 43-char id>               set by the server only
  ▼
Amplify Hosting rewrite  /api/<*> -> HTTP API zllr9lrg7j /prod/<*>    (M1)
  ▼
wecare-customer-session:live          ← the ONLY function that can read a Cognito token
  ├── CustomerSessionsTable       (SSE-KMS CMK)   CREDENTIAL custody. Session role ONLY
  ├── CustomerSessionIndexTable   (SSE AWS-owned) TOKEN-FREE resolution record. Readable wider
  ├── Cognito  InitiateAuth / RespondToAuthChallenge / REFRESH_TOKEN_AUTH / RevokeToken
  └── CustomersTable                              identity + phone ownership

other customer endpoints (ecommerce/checkout, ecommerce/wix-store — DO NOT TOUCH)
  └── lambda_utils.customer_auth.require_customer(event)
        ├── 1. Bearer token  (existing behaviour, unchanged)
        └── 2. NEW: session cookie -> customer_session.require_session(
                                          event, mutating=<from method>,
                                          can_refresh=False)        ← ONE entry point
                 reads CustomerSessionIndexTable ONLY. No token, no kms:Decrypt,
                 no refresh (can_refresh=False skips step 8, §8.2), and the CSRF
                 gate is applied HERE (§4.6) because these two handlers are
                 DO-NOT-TOUCH and cannot opt in.
```

**One entry point, one capability flag — review finding 4.** Pass 2 named `customer_session.resolve`
in this diagram and `customer_session.require_session` in §4.6's snippet, while §8.2 made
`require_session` perform step 8 (refresh). Inside `checkout`/`wix-store` a refresh is impossible —
those roles hold neither table 1 nor the CMK (§4.2) — so an implementer taking the §8.2 reading would
have produced an `AccessDeniedException`, hence a `503`, for **every** signed-in shopper whose access
token happened to be inside the 5-minute skew window. Three defensible readings, two of which break
the cart. So the capability is explicit in the signature rather than implied by the caller:

```python
def require_session(event, *, mutating: bool, sensitive: bool = False,
                    can_refresh: bool = False):
    """Steps 1-9 of design §8.2, returning (CustomerSession, None) or (None, response).

    can_refresh=False is the SHARED cookie branch (ecommerce/checkout, ecommerce/wix-store).
    It reads the RESOLUTION table only, so **step 8 is SKIPPED**: an accessTokenExpiresAt in
    the past is NOT an error there. Authorisation comes from the row (§7.2), and those roles
    hold neither CustomerSessionsTable nor the CMK (§4.2) - attempting a refresh would be an
    AccessDeniedException, i.e. a 503 on an ordinary cart request.

    can_refresh=True is the session function alone, which owns both tables and the key.
    """
```

`resolve` survives as the **inner** read used by `require_session` and by nothing else outside the
module; no caller calls it directly, and the diagram above is the authority. T-30 drives the shared
branch with `accessTokenExpiresAt` in the past and asserts **no table-1 access is attempted** and the
request proceeds with `200`, not `503`.

The second branch is the whole reason the existing handlers need no edit — but "no edit" is a claim
about *those two files*, not about the surrounding system, and pass 1 overstated it in three ways
that the review caught. All three are now closed and all three cost something:

| What pass 1 claimed | What it costs to actually hold |
|---|---|
| the cookie branch needs no CSRF cooperation from the caller | true only because `require_customer` now derives `mutating` from the HTTP method itself (§4.6) |
| the cookie branch is a drop-in for `CustomerIdentity` | true only because the resolution record carries `normalizedPhone` (§4.2), since `customer_cart` keys the cart on it (M18) |
| only the session role can read a session | true only because credential custody and cookie resolution are **two tables** (§4.2), since `wix-store` runs on the shared fleet role (M15) |

`customer_auth.py` is a shared layer module and is *not* under the forbidden
`lambda_utils/ecommerce/**` subtree, so an additive change there is in scope; the blast radius is
named and bounded in §11.

### Endpoints

All under the same-origin prefix. Route keys on `zllr9lrg7j`, all integrating
`wecare-customer-session:live`.

| Route | Auth | Mutating | Purpose |
|---|---|---|---|
| `POST /customer/session/challenge` | none | yes (throttle) | start phone verification: `require_explicit_e164` → throttle → **known number:** `InitiateAuth CUSTOM_AUTH`; **unknown number:** our own `otp_challenge` under purpose `customer_phone_ownership`. One opaque answer either way (§9.3). **Creates nothing** (§8.8) |
| `POST /customer/session` | challenge handle + code | yes | answer the code; for an unknown number, verify-then-provision in that order (§8.8); create the session, `Set-Cookie`, return CSRF token |
| `GET /customer/session` | cookie | no | who am I; returns `{authenticated, customerId, displayPhone, csrfToken, expiresAt, remembered}` |
| `POST /customer/session/refresh` | cookie + CSRF | yes | explicit renewal; normally unnecessary (§6 renews inline) |
| `DELETE /customer/session` | cookie + CSRF | yes | sign out: `RevokeToken`, delete record, clear cookie |
| `POST /customer/session/echo` | cookie optional | no | **P1 transport probe only.** Reports *presence booleans* for `cookie`, `sec-fetch-site`, `sec-fetch-mode` and `origin`, plus the enumerated `sec-fetch-site` value. Never a cookie value, never an `Origin` value (§2 P1) |
| `POST /customer/email` | cookie + CSRF | yes | request/verify email ownership for the owning session (§8.3) |
| `POST /customer/profile` | cookie + CSRF | yes | name/profile mutation on the owning session (§8.2) |

`POST /customer/session/echo` is deliberately a route rather than a flag on `GET /customer/session`,
so it can be deleted outright once P1 passes without touching a route the app depends on. The
provisioning script's `--retire-echo` mode removes it.

---

## 4. Session identity

### 4.1 The cookie

```
Set-Cookie: __Host-wd_cs=<43 chars base64url>; Path=/; Secure; HttpOnly; SameSite=Lax
            [; Max-Age=2505600]            only when "remember me" was chosen
```

Attribute by attribute, with the reason, because every one of these is a decision:

- **`__Host-` prefix.** The browser refuses to store a `__Host-` cookie that carries a `Domain`
  attribute, or that is not `Secure`, or whose `Path` is not `/`. That makes host-only **enforced
  by the browser rather than promised by the server**, and — the part that matters here — it means
  **a sibling subdomain cannot shadow or overwrite it**. That is not a theoretical concern in this
  account: three hostnames have already been retired (`stack.`, `app.`, `r.`), and a dangling
  record is the classic route to a subdomain takeover that sets `Domain=wecare.digital` cookies.
  The task asks for the canonical customer host only; `__Host-` is the mechanism that actually
  delivers it.
- **`Path=/`** is forced by `__Host-`. The trade this loses is real and is recorded in §4.6.
- **`Secure`** — HSTS is live (`max-age=31536000`), so there is no plaintext path to protect.
- **`HttpOnly`** — the reason the whole design exists. An XSS on this origin cannot read the
  session id. It can still *act* as the customer while the page is open, which no cookie attribute
  fixes; what it cannot do is exfiltrate a 30-day credential.
- **`SameSite=Lax`** — see §4.3.
- **No `Expires` by default.** Absent `Max-Age`, this is a browser-session cookie: it dies with the
  browser. "Remember me" adds `Max-Age` equal to the remaining absolute lifetime (§5.4).
- **Name `wd_cs`**, five characters, no customer data, no version. `__Host-wd_cs` reads as
  "WECARE.DIGITAL customer session" and nothing else.

### 4.2 The value, and what is stored where

The cookie value is `secrets.token_urlsafe(32)` — 256 bits of entropy, 43 URL-safe characters.
Opaque: it encodes nothing, so it cannot be parsed, forged or downgraded, and it carries no
customer id, phone, or expiry to be tampered with.

**The table is keyed on `sha256(session_id)`, not on the session id.** A dump of the sessions table
must not yield usable session ids, exactly as `otp_challenge` refuses to store a code. No pepper is
used and that is deliberate rather than lazy: a 256-bit random value is not guessable, so the hash
has nothing to defend against offline search, and introducing a pepper would add a Secrets Manager
dependency on the hot read path for no gain. (`otp_challenge` needs a pepper because a six-digit
code has only a million candidates. Different problem, different answer.)

#### Two tables, because custody and resolution are different jobs

This is the change the review's finding 3 forced, and M15 is why it is not negotiable. The two
handlers that must resolve a cookie are `ecommerce/wix-store`, which runs on the **shared fleet
role** `wecare-digital-lambda-role` (M15), and `ecommerce/checkout`, which will run on its own
`wecare-checkout-role` (M16). DynamoDB SSE-KMS encrypts the **whole item**, so any principal that
can `GetItem` a row holding `refreshTokenEnc` must hold `kms:Decrypt` and can therefore read the
token. Granting that to the fleet role would give all 65 functions read access to every live 30-day
customer credential — which is the precise opposite of the reason for moving tokens off the browser.
Withholding it makes the cookie branch return `AccessDeniedException` inside those two functions.

Pass 1 asserted a single-custodian property it could not have. So:

**Table 1 — `stack-wecare-digital-CustomerSessionsTable`. CREDENTIAL CUSTODY.**
SSE with the customer-managed key `alias/wecare-customer-sessions`. Readable and writable by
**`wecare-customer-session-role` and nothing else** — and that sentence is now true, because nothing
else needs to read it.

| Attribute | Type | Notes |
|---|---|---|
| `sessionIdHash` | S | **partition key.** `sha256(session_id).hexdigest()` |
| `customerId` | S | `CUS_<ULID>` |
| `cognitoSub` | S | audit and provider-side correlation |
| `normalizedPhone` | S | E.164, from the verified challenge. Needed for refresh-time correlation and as the source for table 2 |
| `tokenSource` | S | **`"cognito"` or `"phone_ownership"`.** Explicit, not inferred from the absence of a token field, because every refresh, sign-out and step-up branches on it (§8.8 step 6b.iv). A row with `tokenSource="phone_ownership"` is a **legal tokenless session** |
| `refreshTokenEnc` | S | the Cognito refresh token. **Absent when `tokenSource="phone_ownership"`** |
| `refreshTokenPrevEnc` / `refreshTokenPrevUntil` | S / N | the 60s rotation grace pair (§6.2); absent while rotation is off |
| `accessTokenEnc` | S | the current Cognito access token. **Absent when `tokenSource="phone_ownership"`** |
| `accessTokenExpiresAt` | N | epoch seconds, from `ExpiresIn` at issue. Absent on a tokenless session |
| `cognitoAuthSession` | S | the provider `Session` string during a challenge only; deleted on completion (§10.1) |
| `refreshLockUntil` | N | single-flight lease (§6.1) |
| `refreshGeneration` | N | monotonic, bumped on every successful refresh |
| `createdAt` · `absoluteExpiresAt` · `revokedAt` · `expiresAt` | N | co-written with table 2 in one transaction |
| `idleExpiresAt` · `lastSeenAt` | N | **a NON-AUTHORITATIVE MIRROR.** Table 2 owns the idle clock (see below). Refreshed opportunistically on the session function's own writes and **never compared against table 2** |

GSI `customerId-index` (HASH `customerId`, RANGE `createdAt`) so "sign out everywhere" is a query
rather than a scan. `PAY_PER_REQUEST`. Point-in-time recovery **off**: the table holds only live
credentials with a 30-day ceiling, and a PITR snapshot would be a restorable copy of every refresh
token in flight — the opposite of what PITR is for on `PaymentAttemptsTable`.

**Table 2 — `stack-wecare-digital-CustomerSessionIndexTable`. TOKEN-FREE RESOLUTION.**
SSE with the **AWS-owned** key, because there is no credential in it to protect with a CMK and a CMK
here would re-create the very grant it exists to avoid.

| Attribute | Type | Notes |
|---|---|---|
| `sessionIdHash` | S | **partition key.** The same `sha256(session_id)` |
| `customerId` | S | the authority for every ownership check |
| `normalizedPhone` | S | E.164. **Present because `ecommerce/customer_cart._key` partitions the cart on it** (M18) and `checkout` sends the WhatsApp handoff to it. Without it a cookie shopper arrives with `phone=""`, fails the `fullmatch`, and the cart answers `422 CART_VALIDATION_FAILED` — the first thing a signed-in shopper would touch |
| `poolId` | S | the staff-pool refusal of §4.4 |
| `csrfTokenHash` | S | `sha256(csrf)`; the plaintext is returned once and never stored |
| `absoluteExpiresAt` · `revokedAt` | N | co-written with table 1, so every expiry verdict is reachable without table 1 |
| `idleExpiresAt` · `lastSeenAt` | N | **OWNED HERE.** The authoritative idle clock (see below) |
| `tokenSource` | S | `"cognito"` or `"phone_ownership"`. Carried so a resolver can tell a tokenless session from a stale-token one without reading table 1. **Not a credential and not a secret** |
| `accessTokenExpiresAt` | N | **the timestamp only, never the token.** Lets a resolver see staleness and decide per §7.2 |
| `remembered` | BOOL | |
| `lastVerifiedAt` | N | the step-up window of §8.5 |
| `expiresAt` | N | **TTL attribute**, `absoluteExpiresAt + 86400` |

**No access token, no refresh token, no `cognitoSub`, no `cognitoAuthSession`, ever.** Asserted by a
test that enumerates the attribute names the writer may emit for this table (§14, T-28), so a future
"just add the sub, it's only an identifier" cannot land quietly.

#### The co-write invariant, with the one exemption it must have

Pass 2 claimed flatly that "the two rows can never diverge, because every create, rotate,
refresh-clock, revoke and delete writes both in one `TransactWriteItems`". Review finding 5 showed
that is contradicted by the only write the foreign roles are granted at all: `wecare-digital-lambda-role`
and `wecare-checkout-role` get `UpdateItem` on **table 2 only**, precisely so they can advance the idle
clock — which diverges the rows by construction on every cart request. Worse, pass 2 called table 1
"the writer" of the clocks without saying which copy an expiry verdict reads, so a shopper active for
six days **entirely inside the cart** would have been logged out at table 1's untouched 7-day deadline
despite continuous use. T-06 and T-28 would not have noticed: one asserts `absoluteExpiresAt` is
identical in both tables, the other asserts the transactional co-write.

So the exemption is named rather than implied:

> **`idleExpiresAt` and `lastSeenAt` are OWNED BY TABLE 2** and are the two attributes **exempt** from
> the co-write invariant, because the resolving roles can write only table 2. **Every** expiry verdict —
> including the session function's own, which could read either — reads the idle clock from **table 2**.
> Table 1's copy is a non-authoritative mirror, refreshed opportunistically on the session function's
> own writes, and it is **never compared against table 2**. Every other attribute stays co-written in
> one `TransactWriteItems`.

Restated as the invariant: the two rows **cannot diverge on any attribute an expiry or authorisation
decision reads, except the idle clock, which has a single owner.** The attributes that must stay
identical are `customerId`, `normalizedPhone`, `poolId`, `absoluteExpiresAt`, `revokedAt`,
`csrfTokenHash` and `tokenSource`. A table-2-only change to any of **those** is divergence and a bug;
a table-2-only idle advance is normal operation. T-28 asserts both directions.

A transaction is the right tool for the co-written set precisely because there is nothing to adopt on
failure — unlike the phone reservation in §8.1, where the loser must be able to read what the winner
wrote. Divergence in that set is the only failure mode that would matter (a live credential row with no
resolution row is unusable; a resolution row with no credential row would authorise a session whose
tokens are gone), and an all-or-nothing write removes it.

**What this costs, stated rather than discovered later.** `resolve` inside `checkout`/`wix-store`
reads table 2 only, so it **cannot refresh**. A request that finds `accessTokenExpiresAt` in the past
therefore **proceeds on the row's authority** — not on the token's — which §7.2 already permits and
explains: authorisation comes from our record, written after Cognito validated a `CUSTOM_AUTH`
challenge, and provider re-validation happens on the session function's own refresh cycle. It does
**not** return `401`. A 401 there would log a shopper out mid-cart for a stale copy of a token the
handler never uses, which is the §6.3 failure mode wearing a different hat. The two alternatives the
review listed are rejected on the record: an internal `lambda:InvokeFunction` hop adds a synchronous
Lambda call and a new outage mode to every customer request; application-level envelope encryption
re-introduces key handling, a blob format and a `Decrypt` call in our own code, all of which SSE-KMS
exists to avoid.

**Token confidentiality on table 1.** Table-level SSE with a customer-managed KMS key, not
application-level envelope encryption: the IAM boundary and the crypto boundary become the same
boundary, and there is no key material, no ciphertext format and no `Decrypt` call of ours to get
wrong. The `_Enc` suffix records that property; it does not imply the handler encrypts anything
itself. Note the IAM consequence that §11.1 now spells out: a **write** to a CMK-encrypted table
needs `kms:GenerateDataKey` as well as `kms:Decrypt`.

**Nothing from Cognito is ever sent to the browser.** `GET /customer/session` returns
`customerId`, a masked `displayPhone` (last four only, matching every other log and UI site in this
repo), the CSRF token, `expiresAt` and `remembered`. No access token, no id token, no refresh
token, **and no `normalizedPhone`** — in any response, in any shape, ever. Asserted by a test that
walks every response body recursively (§14, T-11).

#### One type across the seam: `CustomerSession(CustomerIdentity)`

Review finding 7, and pass 2's two statements could not both be true of one object. §4.2 said
`resolve` returns a `customer_auth.CustomerIdentity`; §8.5 read `session.lastVerifiedAt`. M23 confirms
`CustomerIdentity` declares `__slots__ = ("customer_id", "phone", "subject")`, so attaching a session
field to an instance raises `AttributeError` at runtime — the ambiguity was not stylistic.

The compatibility is made **structural** rather than incidental:

```python
# lambda_utils/customer_session.py
class CustomerSession(customer_auth.CustomerIdentity):
    """What the cookie branch returns, everywhere. IS-A CustomerIdentity so the two unedited
    handlers (checkout:196, wix-store:368) and authorize_resource() keep working untouched,
    with .phone carrying normalizedPhone (M18) and .subject deliberately '' (below).

    Its own __slots__ is REQUIRED, not tidiness: CustomerIdentity defines __slots__, so a
    session field cannot be attached to a plain instance (M23).
    """
    __slots__ = ("session_id_hash", "last_verified_at", "remembered", "token_source",
                 "absolute_expires_at", "idle_expires_at", "csrf_token_hash")
```

Both `resolve` and `require_session` return a `CustomerSession`, and nothing else is returned from
either. T-20 asserts `isinstance(identity, customer_auth.CustomerIdentity)` so the IS-A property is
pinned by a test rather than by this paragraph.

**Naming convention, fixed in one direction per layer**, because pass 2 mixed the two and the review
had to guess: **DynamoDB attribute names are `camelCase`** (`lastVerifiedAt`, `absoluteExpiresAt`,
`tokenSource`) and **Python attributes are `snake_case`** (`last_verified_at`, `absolute_expires_at`,
`token_source`). The mapping happens exactly once, in the `CustomerSession` constructor. Every
`session.*` read in this document means the Python spelling; every bare attribute name in a table of
record fields means the DynamoDB spelling.

`subject` is empty on the cookie branch. Checked: `customer_auth` uses `subject` only in
`CustomerIdentity.__repr__`, and no consumer under `ecommerce/` reads it — `owns()` and
`authorize_resource` compare `customer_id` alone. Stated here so an empty string is a documented
property rather than a surprise, and T-20 asserts no authorisation decision reads it.

### 4.3 SameSite, and the checkout journey it has to survive

**`SameSite=Lax`.** `Strict` would drop the cookie on any inbound navigation from another site —
including a WhatsApp message link, which is how a meaningful share of this store's traffic arrives,
so the shopper would land signed-out on a page they were signed in on a second earlier. `None`
requires `Secure` plus cross-site exposure for no benefit on a same-origin design.

The known `Lax` trap is a **cross-site top-level POST**: those do not carry `Lax` cookies. Razorpay's
redirect-style flow does exactly that — a top-level `POST` back to a callback URL. So the design
pins an invariant:

> **No cookie-authenticated endpoint is ever the direct target of a cross-site top-level POST or a
> provider callback.**

Payment verification is keyed on `reference_id` and verified server-side against Razorpay; it does
not and must not consult the session cookie. The shopper's return lands on a *page*, and that page
re-establishes context with a same-origin `GET /customer/session` — a same-site subresource request,
which `Lax` permits. Enforced structurally: the session function owns only the eight routes in §3,
none of which is a provider callback, and `tests/test_customer_session_cookie_contract.py` asserts
that no route owned by this function appears in any provider callback or redirect configuration.

**And to be explicit, because it is the single most load-bearing sentence in this document: a valid
session is NOT payment verification.** It proves who is asking. Whether money moved is decided only
by Razorpay readback through `lambda_utils/payment_status.py`, in code this design does not touch.

### 4.4 Keeping the customer session away from the staff app

One origin, two apps, so the cookie is attached to staff `/api/*` calls as well. Three independent
controls, none of which is cookie scope:

1. **`lambda_utils.middleware.require_auth` never learns about cookies.** The cookie branch is
   added to `customer_auth` only. A staff endpoint reading `require_auth` cannot be authenticated
   by a customer cookie because the code path does not exist. Pinned by a test that greps the AST
   of `middleware.py` for any cookie read (§14, T-12) — AST, not text, following the precedent of
   `tests/test_payment_vocabulary_at_decision_points.py`.
2. **Pool binding on the record.** Every session row stores the issuing pool id and
   `customer_session.resolve` refuses a row whose pool is not `us-east-1_46ULYuukt`. The staff pool
   `us-east-1_cSx0RHCIR` can therefore never produce a usable customer session, even if a future
   caller passes a staff token into the create path.
3. **`customer_auth`'s existing issuer pin is retained**, unmodified, on the Bearer branch. The
   cookie branch gets the equivalent check from (2).

### 4.5 Cart data stays away from credentials

The cart is already `localStorage` under `wecare.cart.v1` (`src/lib/cart.ts`), and its own docblock
says why: a list of catalogue references is not sensitive. That stays exactly as it is.

The rules this design adds: the session cookie carries **no** cart data; the session record carries
**no** cart data; and the cart module gains no awareness of the session. `src/lib/customerSession.ts`
must not import `src/lib/cart.ts` and vice versa, asserted statically (§14, T-13). On sign-out the
credential is destroyed and the cart is **preserved** — a shopper signing out of a shared browser
has not asked to lose their basket, and PR #163/#164's "do not clear the cart merely because an
attempt was created" improvement is the same principle one step earlier.

`lastSeenAt` is written at most once per 60 seconds, which keeps a per-request write off the hot
path. It is a coarse "is this session live" signal, not an analytics trail, and it carries no IP and
no user agent — there is nothing in the record that would turn it into a tracking log.

### 4.6 CSRF — mandatory on every cookie-authenticated mutation

#### The gate lives in the cookie branch, not in the caller

This is review finding 1, and it was a real hole rather than a wording problem.
`customer_auth.require_customer(event)` takes **no** `mutating` argument, and both
`ecommerce/checkout/handler.py:196` and `ecommerce/wix-store/handler.py:368` (inside `_customer_cart`,
which accepts `POST` cart mutations) call exactly that one function and nothing else. Both files are
DO-NOT-TOUCH, so neither can be edited to pass `mutating=True`. Pass 1 declared CSRF "mandatory on
every cookie-authenticated mutation" and then specified an integration in which the two busiest
cookie-authenticated mutations in the app had no CSRF gate at all. `SameSite=Lax` does not cover it:
a sibling subdomain is **same-site** for `SameSite` purposes, which is the threat `__Host-` was chosen
for in §4.1, and `AllowCredentials: false` is a cross-origin control, not a same-site one.

The fix is to put the decision where no caller cooperation is needed — derive it from the request:

```python
def require_customer(event):
    # 1. Bearer branch, unchanged. Still GetUser + issuer pin.
    try:
        return authenticate(event), None
    except CustomerNotAuthenticated:
        pass

    # 2. Cookie branch. A cookie is a CSRF-bearing credential, so the gate is applied HERE and
    #    NOT by the caller: ecommerce/checkout/handler.py and ecommerce/wix-store/handler.py are
    #    DO-NOT-TOUCH and cannot opt in. Deriving `mutating` from the HTTP method is what makes
    #    those two unedited handlers safe.
    #    can_refresh=False because this runs INSIDE checkout/wix-store, whose roles hold neither
    #    CustomerSessionsTable nor the CMK (§4.2). A refresh attempt there is AccessDenied, i.e.
    #    a 503 on an ordinary cart request. Step 8 of §8.2 is skipped; the row authorises (§7.2).
    from lambda_utils import customer_session
    http = ((event.get("requestContext") or {}).get("http") or {})
    method = str(http.get("method") or event.get("httpMethod") or "").upper()
    mutating = method not in ("GET", "HEAD", "OPTIONS")
    return customer_session.require_session(event, mutating=mutating, can_refresh=False)
```

The method read handles both payload shapes for the same reason `bearer_token` lowercases headers:
v1 and v2 do not agree, and a read that works in one and silently fails in the other is how a gate
becomes decorative. An unreadable method yields `""`, which is **not** in the exempt tuple, so it is
treated as mutating — the safe direction. T-04 drives both handlers with a valid cookie and no
`X-WD-CSRF` and asserts **403**.

Two gates, both server-side, both required. Either alone has a documented failure mode.

**Gate 1 — session-bound double submit.** On session creation the server mints
`csrf = secrets.token_urlsafe(32)`, stores `sha256(csrf)` on the session row, and returns the
plaintext in the JSON body. Every mutating request must carry it in `X-WD-CSRF`. The server
compares `sha256(header)` to `csrfTokenHash` with `hmac.compare_digest`.

This is stronger than classic double-submit because the comparison is against **server state**, not
against a second cookie an attacker on a sibling subdomain could plant. There is deliberately **no
JS-readable CSRF cookie**: a new tab bootstraps by calling `GET /customer/session`, which is safe,
idempotent, and unreadable cross-origin. One fewer cookie, one fewer thing to shadow.

**The mechanism for that unreadability, corrected.** Pass 1 said the function "emits no
`Access-Control-Allow-Origin` for a foreign origin and sets `Vary: Origin`". It cannot do either, for
two independent reasons the review verified. First, `CorsConfiguration` is set on `zllr9lrg7j` (M5)
and **an HTTP API overrides CORS headers returned by the integration** when CORS is configured at the
gateway — M4 already observed the gateway answering `access-control-allow-origin: https://wecare.digital`
on a route this design does not own. Second, `lambda_utils/response.py:cors_headers` does the opposite
of what pass 1 described anyway: it **always** emits ACAO, falling back to
`ALLOWED_ORIGINS[0] = 'https://wecare.digital'` for an unknown origin, and `require_customer` builds
its 401 through it.

The protection does hold, by a different mechanism:

> `GET /customer/session` is unreadable cross-origin because the HTTP API's `CorsConfiguration` has
> **`AllowCredentials: false`** (M5), so no `Access-Control-Allow-Credentials` is ever returned and the
> browser discards a credentialed cross-origin response regardless of ACAO. Gateway CORS also
> **overrides** integration CORS headers on an HTTP API, so the session function must not be written
> as though it can suppress ACAO, echo an origin or add `Vary: Origin`. It cannot. This is a second,
> independent reason not to flip `AllowCredentials` to `true` (C-3): doing so would simultaneously
> widen 359+ routes and remove this control.

`--verify` asserts the measurable half of that: a response from `GET /api/customer/session` carries
**no** `Access-Control-Allow-Credentials` header (§14, T-27).

**Gate 2 — fetch metadata.** Gate 2 exists because Gate 1 alone fails if the token ever leaks through
a log or a referrer; Gate 1 exists because Gate 2 alone fails on a browser that omits the metadata.

Pass 2 specified Gate 2 two ways — §4.6 said "a request with neither header present is refused",
§10.1's table marked `Origin` "optional" — and the review was right that the disagreement matters,
because the two readings differ on whether `Origin` alone is sufficient. **It is**, and here is the
single rule, in one place, with `Sec-Fetch-Site`'s survival through the rewrite treated as the
*measured* input it is (§2 P1 part (c)) rather than as an assumption:

> **Gate 2, FULL configuration** (`P1` reports `secFetchSitePresent: true`):
> a mutation is refused unless `Sec-Fetch-Site == "same-origin"`; **and** if `Origin` is present it
> must equal `https://wecare.digital` exactly. `Origin` absent is acceptable here, because
> `Sec-Fetch-Site` already carried the verdict.
>
> **Gate 2, DEGRADED configuration** (`P1` reports `secFetchSitePresent: false`,
> `originPresent: true`): a mutation is refused unless `Origin` is **present** and equals
> `https://wecare.digital` exactly. `Sec-Fetch-Site` is not consulted, because it never arrives.
> Gate 1 is unchanged and still mandatory.
>
> **Neither header arrives:** Gate 2 is unimplementable through the rewrite. **Do not ship §12 step 7
> with Gate 1 alone** — apply the C-3 contingency.

The configuration is a single env value, `CSRF_FETCH_METADATA_MODE` ∈ `{full, origin_only}`, set from
the P1 measurement and defaulting to `full`. It is a measured degradation recorded in the evidence doc,
**not a preference**, and `--verify` asserts the live value matches what `--verify-cookie-transport`
observed. T-04 drives **both** configurations, including the case the degraded mode must still refuse:
a mutation with `Origin` absent entirely.

Why `Origin`-alone is genuinely sufficient in the degraded mode: `Origin` is set by the browser and is
not settable from page JavaScript, so a cross-site form post or `fetch` from `evil.example` carries
`Origin: https://evil.example` and is refused. What it loses relative to `Sec-Fetch-Site` is the
*same-site-but-not-same-origin* distinction — a sibling subdomain's `Origin` is not
`https://wecare.digital`, so it is still refused; the real loss is only the `same-site` label itself,
which Gate 1 covers because `csrfTokenHash` lives in server state a sibling host cannot read or plant.

A failed CSRF check returns **403 `{"error":"CSRF_REQUIRED"}`** and **does not** clear the session.
Clearing on CSRF failure would hand anyone an unauthenticated logout gadget. It is logged as
`{"event":"csrf_rejected","gate":1|2}` with no token, no header value, no cookie.

#### `GET` is exempt, and it is NOT side-effect-free. Say so

Pass 1 claimed both that `GET` "must stay side-effect-free" and, two sentences later, that
`GET /customer/session` advances two attributes. The behaviour is right; the claim was wrong, and the
review was right to refuse to let the next reader pick a side.

> `GET` and `OPTIONS` are exempt from CSRF. `GET /customer/session` is **not** side-effect-free: it
> advances `idleExpiresAt` and `lastSeenAt`. That is deliberate — idle expiry has to track real use or
> it is not an idle clock — and it is safe within a stated bound. `SameSite=Lax` **does** send the
> cookie on a cross-site top-level `GET` navigation, so a link a victim clicks can refresh their idle
> clock without their knowledge. All that achieves is *extending* an idle clock which is itself
> bounded by `absoluteExpiresAt`, a field no request extends (§5.2). The request writes nothing else,
> authorises nothing, reads no token, and **can create nothing**.

#### Clearing the cookie from a 401 raised inside an unedited handler

Review finding 7, and it would have failed silently. `lambda_utils/response.py:cors_response` returns
`{'statusCode', 'headers', 'body'}` and has no `cookies` key, while HTTP API payload format 2.0 (M6)
carries `Set-Cookie` in a **top-level `cookies` list**. `require_customer` builds its 401 through
`cors_response`, and `checkout`/`wix-store` return that object verbatim — so every "clear cookie" on a
terminal rejection raised inside those two functions would not have happened, and a dead cookie would
be replayed on every subsequent request forever. `response.py` is DO-NOT-TOUCH (shared by the fleet),
so the augmentation lives in the new module instead:

```python
# lambda_utils/customer_session.py
def _denied(event, code: str, *, clear: bool) -> Dict[str, Any]:
    """The 401/403 for a refused cookie session, with the Set-Cookie payload-2.0 needs.

    cors_response() returns no `cookies` key and response.py is shared by the whole fleet, so the
    top-level list payload format 2.0 requires for Set-Cookie (M6) is added HERE. Without this,
    a clear-cookie decision taken inside an unedited handler is a no-op and the dead cookie is
    replayed indefinitely.
    """
    from lambda_utils.response import cors_response, extract_origin
    response = cors_response(
        401 if code != "CSRF_REQUIRED" else 403,
        {"error": code, "message": "Please verify your WhatsApp number to continue."},
        extract_origin(event))
    if clear:
        response["cookies"] = [clear_cookie_header()]
    return response
```

`clear` is `False` for `CSRF_REQUIRED` and `REAUTH_REQUIRED` and `True` for every terminal rejection
in §8.2 steps 2–6. T-04 and T-05 assert that every clear path returns a response whose `cookies[0]`
is the `Max-Age=0` `__Host-wd_cs` header, and that a CSRF failure returns one with **no** `cookies`
key at all.

**The `Path=/` cache trade, stated.** Because `__Host-` forces `Path=/`, the cookie is attached to
static document and asset requests as well as `/api/*`. If Amplify's distribution varies its cache
key on `Cookie`, signed-in shoppers lose edge cache hits on HTML and JS. This is **the same question
as P1** from the other side — a distribution that forwards cookies to the `/api/*` origin is a
distribution that sees them on `/**` too — so it is measured in the same step: `--verify-cookie-transport`
also records `x-cache` on a signed-in HTML fetch versus an anonymous one. If hit rate measurably
degrades, the documented remedy is to drop the `__Host-` prefix and use `Path=/api` with an explicit
`Domain`-less `Set-Cookie`, trading browser-enforced host-only for narrower attachment. That is a
real trade with a measured trigger, not a preference.

**And the trade is bigger than attachment breadth.** Taking that fallback reinstates the
subdomain-shadowing exposure §4.1 names, because host-only reverts to a *server promise* rather than a
*browser rule*: a `Domain=wecare.digital` cookie set from a taken-over sibling host can then shadow
ours, which `__Host-` makes impossible. So if the fallback is taken it must be paired with a check
that no retired hostname (`stack.`, `app.`, `r.`) holds a dangling DNS record. That check is a Route 53
**read**; it changes nothing and is not a DNS mutation.

## 5. Lifetimes — validated against the live client, not assumed

M7 is the whole basis of this section. The numbers are read from the live app client, with units.

| Provider constraint (measured M7) | Value |
|---|---|
| `AccessTokenValidity` | 60 **minutes** |
| `IdTokenValidity` | 60 **minutes** |
| `RefreshTokenValidity` | 30 **days** |
| `AuthSessionValidity` | 10 minutes (the `CUSTOM_AUTH` challenge window) |
| `EnableTokenRevocation` | `true` |
| `RefreshTokenRotation` | `null` (off) |
| `DeviceConfiguration` (pool) | `null` — **device remembering is unavailable** |
| `MfaConfiguration` (pool) | `OFF` |

### 5.1 The ceiling is the provider's, so ours sits below it

A Cognito refresh token is valid 30 days **from issuance**, and with rotation off (M7) it is not
re-issued by a refresh — so the deadline is fixed at sign-in and no amount of activity moves it.

Setting our absolute session lifetime to the same 30 days would mean the *provider* ends the session,
at an instant we did not choose, surfacing as an opaque `NotAuthorizedException` on a refresh. So:

> **Absolute remembered lifetime = 29 days (2,505,600 s). One day below the provider's 30.**

The margin exists so **we** are always the party that ends a session, deterministically, with a
logged reason and a clean "please sign in again", rather than discovering it from a provider
rejection. The task asked for "~30-day"; 29 days is that requirement implemented against the
measured constraint instead of colliding with it.

### 5.2 Absolute expiry is never extended

`absoluteExpiresAt = createdAt + 2505600`, written once at creation and **never updated by any code
path**. A refresh renews the access token and advances the idle clock; it does not touch this field.
Enforced three ways, because "never extended" is the kind of invariant that erodes:

1. The refresh update expression does not mention `absoluteExpiresAt`.
2. Every refresh is conditional on `absoluteExpiresAt > :now`, so a refresh attempted past the
   deadline fails at DynamoDB rather than relying on a prior read.
3. `tests/test_customer_session_lifetimes.py` drives 40 simulated refreshes across 29 days and
   asserts the field is byte-identical to its creation value and that refresh 41, past the deadline,
   is refused (§14, T-06).

Re-authenticating with a fresh OTP creates a **new** session row with a new id (§8.4) and a new
29-day clock. That is the only way the deadline moves, and it required proving the phone again.

### 5.3 Idle expiry, server-side

`idleExpiresAt = now + 604800` (7 days), advanced on every successful authenticated request,
including `GET /customer/session`. Both clocks are checked server-side on **every** read, before
anything else:

```
revokedAt present                      -> 401 terminal, clear cookie
now >= absoluteExpiresAt               -> 401 terminal, clear cookie, delete row
now >= idleExpiresAt                   -> 401 terminal, clear cookie, delete row
```

The cookie's `Max-Age` is a hint to the browser and is not trusted for anything. A cookie replayed
after either deadline is refused by the server. TTL on the table is set to
`absoluteExpiresAt + 86400` — one day *past* the deadline, deliberately, because DynamoDB TTL
deletion is best-effort and can lag by hours; the row must outlive the session so the expiry verdict
comes from an explicit comparison rather than from a row that happens to be gone. (Same reasoning as
`otp_throttle`'s "rate-limit state must outlive the thing it protects", for the same reason.)

### 5.4 Shared device vs remembered browser

One boolean at sign-in, `remember`, from a checkbox that **defaults to OFF**.

**Changed in this revision, and it is a decision rather than a tweak.** Pass 1 defaulted it on for a
conversion argument. The review was right that the combination — a 29-day persistent credential, on a
phone-keyed account, with `MfaConfiguration: OFF` and `DeviceConfiguration: null` (both measured, M7),
in a market where shared handsets are common — is an owner decision and must not arrive as an
implementation default. `HttpOnly` answers the XSS-exfiltration half of the baseline's open question;
it does not answer "someone else picks up the phone".

Defaulting **off** is also not a regression against today, which is the detail that settles it. Today
`customerAuth.ts` uses `sessionStorage`, which dies with the **tab**. `remember: false` issues a cookie
with no `Max-Age`, which dies with the **browser** — so it survives tab closes and in-journey
navigation and is strictly better than the status quo, while opting in to 29 days stays one visible
checkbox away. Reversible in either direction, which is the right property for a default nobody has
signed off yet.

**C-11** in §13 records the owner decision needed to flip it on, and T-01 asserts the checkbox's
default state so it cannot drift silently.

| `remember` | Cookie | Server record |
|---|---|---|
| `true` | `Max-Age` = remaining absolute lifetime | identical |
| `false` | **no `Max-Age`** → browser-session cookie | identical, `remembered: false` |

The server-side lifetimes are the **same** in both cases, and that is the point: the non-persistent
option changes only how long the *browser* keeps the cookie, so choosing it on a shared machine does
not weaken, shorten or otherwise degrade the remembered flow for anyone else, and does not need a
second code path. A shopper who picks "don't remember me" and then closes the browser leaves a row
that idles out in 7 days and is TTL-reaped; nothing is leaked because the cookie is gone.

`DeviceConfiguration` being `null` (M7) means Cognito's own remembered-device machinery is
unavailable, so "remembered browser" is **our** cookie and nothing else. No `DEVICE_SRP_AUTH`, no
remembered-device OTP suppression. Stated because it is tempting to assume Cognito is helping here;
it is not.

### 5.5 Sign-out

`DELETE /customer/session` with a valid cookie and CSRF:

1. `RevokeToken` against Cognito with the stored refresh token (available because
   `EnableTokenRevocation: true`, M7). Revocation invalidates the refresh token **and** every access
   token minted from it. **Skipped when `tokenSource == "phone_ownership"`**: there is no token, so
   step 1 is a no-op and the row deletion in step 2 *is* the whole sign-out. Skipping is logged as
   `{"event":"signout_no_provider_token"}` so a surprising absence on a `cognito` row is still
   visible, rather than being silently indistinguishable from the tokenless case.
2. Delete the session row.
3. `Set-Cookie: __Host-wd_cs=; Path=/; Secure; HttpOnly; SameSite=Lax; Max-Age=0`.
4. Return `204`. Cart and any resume state are untouched (§4.5).

Order matters: revoke first, so a failure at step 1 leaves a row we still know about rather than an
orphaned live refresh token with no record. If step 1 fails, steps 2–4 still run, the row is written
with `revokedAt` instead of deleted, and `{"event":"signout_revoke_failed","error":"<ExcType>"}` is
logged — the local session is dead either way, and a retry sweep can re-attempt the provider call.

"Sign out everywhere" is a query on `customerId-index` plus the same sequence per row. It is
designed here but has no UI this run (§13), because adding one needs a new page route and §11
explains why no new route is in scope.

---

## 6. Refresh behaviour

Inline, not scheduled. Every authenticated request resolves the session and, if
`accessTokenExpiresAt - now < 300` (5 minutes' skew, the same shape as the existing 30-second grace
in `customerAuth.getSession`, widened because a server-side renewal is cheap and a mid-checkout 401
is not), renews before proceeding.

### 6.1 Single flight, per session, server-coordinated

The coordination point is the session row, so it holds across tabs, across devices and across
concurrent Lambda sandboxes — a client-side lock would not.

```
UpdateItem  Key={sessionIdHash}
            SET refreshLockUntil = :lease          (:lease = now + 15)
            ConditionExpression  refreshLockUntil < :now AND absoluteExpiresAt > :now
```

- Winner refreshes, writes the new tokens, bumps `refreshGeneration`, clears the lease.
- Loser gets `ConditionalCheckFailedException` and **waits for the winner** rather than refreshing:
  re-read the row with a bounded poll (up to 4 attempts, 250 ms apart, 1 s ceiling). If
  `refreshGeneration` advanced, use the new access token. If the lease expired without the
  generation moving, the winner died; try to take the lease once.
- The 15-second lease is longer than a Cognito `InitiateAuth` round trip and far shorter than any
  Lambda timeout, so a crashed holder self-heals.
- **Cross-tab on the client** needs nothing extra. The cookie is shared by every tab and the browser
  serialises nothing, so two tabs may both call the API; the server-side lease is what makes that
  harmless. `src/lib/customerSession.ts` additionally keeps one in-flight `GET /customer/session`
  promise per tab (a module-level promise, the standard single-flight idiom) so a page with four
  components asking "am I signed in" issues one request.

### 6.2 Rotation grace, designed now, inert today

Rotation is **off** (M7), so today `REFRESH_TOKEN_AUTH` is the correct and supported flow and the
refresh token is stable. The design still routes every refresh through one function so the day
rotation is enabled is a one-place change:

```python
def _refresh(client, client_id, refresh_token, *, rotation_enabled):
    if rotation_enabled:
        # GetTokensFromRefreshToken. REFRESH_TOKEN_AUTH is INCOMPATIBLE with rotation
        # and must not be called in this branch.
        ...
    return client.initiate_auth(AuthFlow="REFRESH_TOKEN_AUTH", ...)
```

#### Where `rotation_enabled` comes from, and the drift it must survive

Pass 2 read it from env `COGNITO_REFRESH_ROTATION` and nothing else. Review finding 9 showed that is a
hand-maintained duplicate of provider state with **no reconciliation in either direction**, and the
failure is severe and silent: if `RefreshTokenRotation` is ever enabled on the app client (an owner
action this design correctly keeps out of scope, not an impossible one) and the env var does not change
in the same breath, `REFRESH_TOKEN_AUTH` starts returning `NotAuthorizedException` — which §6.3's
allowlist calls **terminal**. Every customer with a live session would be logged out at their next
refresh, inside 60 minutes, with `revokedAt` written. That is §6.3's own failure class arriving through
configuration, and §6.3's safe-by-default property does not help, because this exception is *on* the
allowlist by design.

Both halves of the review's remedy are taken, because they are cheap and they close different holes.

**(1) One retry across the API boundary before concluding terminal.** A rotation mismatch is
indistinguishable from a real rejection by exception type alone, so it is distinguished by *trying the
other API*:

```python
def _refresh(client, client_id, refresh_token, *, rotation_enabled):
    """One call, one fallback. The fallback exists because `rotation_enabled` can be WRONG, and
    being wrong must not log every customer out (§6.3). A rotation mismatch and a genuine
    rejection are the same exception, so the only way to tell them apart is to try the other API.
    """
    primary, fallback = ((_rotated, _legacy) if rotation_enabled else (_legacy, _rotated))
    try:
        return primary(client, client_id, refresh_token)
    except client.exceptions.NotAuthorizedException:
        tokens = fallback(client, client_id, refresh_token)   # raises -> genuinely terminal
        print(json.dumps({"event": "refresh_rotation_drift",
                          "expected_rotation": rotation_enabled}))   # no token, no id
        return tokens
```

`_legacy` is `initiate_auth(AuthFlow="REFRESH_TOKEN_AUTH", …)`; `_rotated` is
`get_tokens_from_refresh_token(…)`. **Only a second failure is terminal.** The fallback is attempted
exactly once per request and is not retried, so a genuinely revoked token costs one extra provider call
and then expires the session as it should. T-09 asserts **both** directions of the drift and that the
fallback is not attempted twice.

**(2) A cached provider read, off the hot path.** `rotation_enabled` is resolved from
`DescribeUserPoolClient`, cached in module state for **300 seconds**, with the env var as the fallback
when that call fails. One provider call per sandbox per five minutes is not a per-request cost, and it
removes the duplicate rather than merely surviving it. This adds `cognito-idp:DescribeUserPoolClient`
on the customer pool ARN to §11.1.1 — a **read**, and the one Cognito call this design makes about
configuration rather than about a user.

Two details that keep it honest. The cached read must never fail a request: a
`DescribeUserPoolClient` error falls back to the env value and logs `{"event":"rotation_state_unknown"}`
with no client id. And the response is **projected**, never stored or logged whole — a
`DescribeUserPoolClient` response can contain `ClientSecret`, which is exactly why the baseline's own
read of it was blocked and had to be re-run with a narrowed `--query`. The handler reads
`UserPoolClient.RefreshTokenRotation.Feature` and discards the rest **without binding it to a name**,
so no secret-bearing object is ever in a local variable that could reach a log.

Finally, `--verify` asserts the live `RefreshTokenRotation` state matches
`expected_environment()["COGNITO_REFRESH_ROTATION"]` and **fails** if not. It is a read, and it turns
configuration drift into a deploy-time error instead of a production logout.

#### A tokenless session is never refreshed, and that is not an error

A first session has `tokenSource == "phone_ownership"` and holds no Cognito token at all (§8.8 step
6b.iv). For such a session, **refresh is not due** — there is nothing to renew — so step 8 of §8.2 is a
no-op, not a failure, and not a reason to clear a cookie. Concretely:

```
tokenSource == "phone_ownership"  ->  refresh SKIPPED. No provider call, no lease, no 503.
                                       Authorisation is the row (§7.2); expiry is §5.3.
```

This must be an explicit branch and not an accident of `refreshTokenEnc` being missing, because
"missing refresh token" would otherwise read as corruption and could plausibly be coded as terminal —
which would log out every brand-new customer within an hour of their first sign-in. T-31 asserts a
tokenless session survives 40 simulated requests across 29 days with **zero** provider calls and is
expired only by the §5.3 clocks.

Grace handling, which only has teeth once rotation is on: when a rotated flow returns a **new**
refresh token, the previous one stays usable inside the provider's rotation grace window, so a loser
that already read the old token is not stranded. Our side mirrors it by keeping `refreshTokenPrevEnc`
and `refreshTokenPrevUntil` for 60 seconds after a rotation, and retrying once with the previous
token if the current one is rejected within that window. Written now because retrofitting it after
enabling rotation means debugging intermittent logouts in production.

### 6.3 An outage is not a logout. This is the most important rule in §6

| Refresh failure | Terminal? | Behaviour |
|---|---|---|
| `NotAuthorizedException` / `UserNotFoundException` / `UserNotConfirmedException` | **yes** | revoke intent recorded, row marked `revokedAt`, cookie cleared, `401 SESSION_EXPIRED` |
| `TooManyRequestsException`, `LimitExceededException` | no | up to 2 retries, exponential backoff with jitter (200 ms, 600 ms), then `503 TEMPORARILY_UNAVAILABLE`, **session kept** |
| `InternalErrorException`, any 5xx, `EndpointConnectionError`, timeout, DNS failure | no | same as above, **session kept** |
| DynamoDB unavailable while reading the session | no | `503`, **session kept**, cookie untouched |
| lease contention (§6.1) | no | wait, then proceed |

Only the first row clears a cookie. A generic 5xx, an offline browser or a Cognito outage returns
`503` with `Retry-After: 5`, and the client shows `MSG.TRY_LATER` — **it does not route to sign-in and
does not start an OTP.** The failure mode being designed out is the OTP loop: a provider blip that
clears the session, sends the shopper to sign-in, which calls Cognito, which is still down, which
fails, repeatedly, each iteration costing a WhatsApp message.

Enforced structurally rather than by discipline: there is exactly one function,
`_is_terminal(exc) -> bool`, whose allowlist is the four Cognito exception names in row 1. Every
cookie-clearing path goes through it, and `tests/test_customer_session_refresh.py` feeds it a matrix
of 14 failure shapes and asserts that exactly four are terminal (§14, T-07). A new exception type is
non-terminal by default, which is the safe direction.

### 6.4 When the shopper must do an OTP

**Only these four:**

1. no session cookie, or no row for it (first visit, new browser, new device);
2. a session that is expired (idle or absolute) or revoked;
3. an explicit sign-out followed by a sign-in;
4. a defined sensitive step: changing the phone number of record, or changing the email of record
   (§8.5).

Everything else — a 503, a network drop, a slow refresh, a lease wait, an ordinary checkout, adding
an address, a payment retry — must **not** trigger one. Asserted as a property: the client
`customerSession.ts` has a single `requiresReauth(status, code)` predicate returning true only for
`401` with `{"error":"SESSION_EXPIRED"}` or `{"error":"VERIFICATION_REQUIRED"}`, and
`src/test/CustomerSessionReauth.test.ts` enumerates every status the API can return and asserts
exactly those produce a sign-in redirect (§14, T-14).

## 7. Cognito specifics, and the change this design does NOT make

**No app-client change is required.** That is the headline from M7 and it is worth stating plainly
because it removes the riskiest step from the plan: `ALLOW_REFRESH_TOKEN_AUTH` is already present,
`EnableTokenRevocation` is already `true`, the refresh token is already 30 days, and rotation is off
so `REFRESH_TOKEN_AUTH` is the correct flow. Remembered login, silent renewal and revocable
sign-out are all implementable against the client **exactly as it is configured today**.

All three `CUSTOM_AUTH` triggers stay pointed at
`arn:...:function:wecare-customer-whatsapp-auth:live`, unchanged. `AuthSessionValidity` stays 10
minutes. `PreventUserExistenceErrors` stays `ENABLED`. `AllowAdminCreateUserOnly` stays `true`.

### 7.1 Pool mutation is OUT OF SCOPE. Here is the exact change, reported not performed

`UpdateUserPool` is a **full replace** and has already silently wiped these three triggers and
opened self-signup once (2026-09-28). So:

- **Nothing in this design calls `update-user-pool` or `update-user-pool-client`, in any spelling.**
- If a pool change is ever authorised, it goes through
  `python scripts/cognito_pool_safe_update.py --pool-id us-east-1_46ULYuukt --set <Field>=<Value> --apply`
  and the IaC is updated in the same change.

The one pool change this design would need, and does not make:

> **C-1 — `custom:customer_id` schema attribute.** R6 (unverified, deliberately not re-measured here
> because it needs a `SchemaAttributes` projection that belongs to the implementation step) claims the
> customer pool schema lacks `custom:customer_id`, while both `customer-registration/handler.py` and
> `lambda_utils/customer_auth.authenticate` require it. **Cognito custom attributes cannot be added
> after pool creation.** If R6 holds, the attribute cannot be created at all and the binding must move
> off the pool and onto `CustomersTable` (see §8.1, which is why the session row stores `customerId`
> itself rather than reading it from a token claim on every request). Exact action required:
> `aws cognito-idp describe-user-pool --user-pool-id us-east-1_46ULYuukt --query 'UserPool.SchemaAttributes[?starts_with(Name, `custom:`)].Name'`
> — a **read** — and then an owner decision.
>
> **Promoted to BLOCKING by this revision.** Pass 1 called C-1 "not blocking for this design" because
> §8.1 makes `CustomersTable` the authority for `customerId`. The review showed that reasoning covers
> *authorisation* and not *provisioning*: `_provision_login` stamps `custom:customer_id` on
> `AdminCreateUser`, so if the attribute cannot exist then a **new** customer cannot be given a Cognito
> login at all, and §8.8's first-time sign-in cannot be built. Returning-customer sign-in, refresh,
> CSRF, lifetimes and every §8 identity fix are unaffected and remain independent of it. So C-1 is
> **blocking for new-customer sign-in only**, it is read (not mutated) at §12 step 0, and §8.8 states
> what the design does if the attribute is absent: drop the attribute from the provisioning call and
> let `CustomersTable` carry the binding alone, which costs the Bearer branch of
> `customer_auth.authenticate` — that branch requires the claim and refuses a session without it. That
> consequence is why this is an owner decision and not a code choice.

### 7.2 Why authorization does not call Cognito per request

`customer_auth.authenticate` currently calls `GetUser` on every protected request. For the cookie
branch that would mean a provider round trip per page view, a provider rate limit on our own
checkout, and a provider outage becoming a site outage.

So the cookie branch authorises from **our** session row: `customerId` and `cognitoSub` were written
at sign-in, after a WhatsApp OTP to the number of record was verified.

**Precision pass 2 did not have, and finding 1 forces.** *Which* party checked that OTP depends on
`tokenSource`, and the sentence has to say so rather than claiming Cognito always did:

| `tokenSource` | Who validated the code | Provider re-validation |
|---|---|---|
| `"cognito"` | Cognito, via a `CUSTOM_AUTH` challenge answered through `RespondToAuthChallenge` | on the refresh cycle, at most 60 minutes apart; a terminal rejection kills the session (§6.3) |
| `"phone_ownership"` | **us**, via `otp_challenge.verify` under purpose `customer_phone_ownership` — the same six-digit code, to the same handset, over the same WhatsApp sender, with the same pepper, TTL, attempt cap and single-use condition | **none, by construction.** There is no token to re-validate. The session is bounded only by §5.3's clocks and by `revokedAt` |

The second row is a genuine difference and is stated rather than smoothed over: a tokenless session
cannot be ended by disabling the Cognito user. It can be ended by our own `revokedAt`, by either clock,
or by sign-out. The exposure is bounded three ways: it applies **only to a customer's very first
session**, it ends the moment that session does (every subsequent sign-in is the `cognito` branch,
because the user now exists), and the proof of identity behind it is not weaker — it is the identical
WhatsApp OTP, checked by the module this repo already trusts for email ownership and download grants.
A step-up to any sensitive operation also upgrades the session to `cognito` (§8.5), so the three
operations that most need provider-backed identity cannot be reached from a tokenless session without
first acquiring a token.

The honest cost: **revocation latency is bounded by the access-token lifetime, up to 60 minutes.**
Disabling a Cognito user does not instantly kill a live session; it kills it at the next refresh.
Mitigations, all present: explicit sign-out is immediate; `revokedAt` on our row is immediate and is
checked on every read, so our own kill switch has no latency; and a **sensitive step performs a live
provider check** rather than trusting the row (§8.5). For a storefront with no MFA and a 60-minute
token, that is the right trade, and it is recorded here so nobody discovers it during an incident.

The Bearer branch is unchanged — it still calls `GetUser` and still pins the issuer. Both branches
coexist for the whole rollout, which is what makes §12 reversible.

---

## 8. Identity and ownership — findings A5–A10, A16

### 8.1 A5 — one phone must not mint two customer ids

**The defect, in the committed source.** `customer-registration/handler.py::_create_customer` writes:

```python
record = {"customerId": identity.new_customer_id(), ...}
_customers_table().put_item(Item=record,
    ConditionExpression="attribute_not_exists(customerId)")
```

The condition guards **the freshly minted random id**, which by construction never exists. So it
always succeeds, and two concurrent verifications of the same phone produce **two** customer ids —
the `_resolve_customer` GSI read in front of it is eventually consistent and cannot close the race.
The comment claiming "the create is itself conditional" is describing a guarantee the expression does
not provide.

**The fix: reserve the phone, then create the customer.** A two-item sequence, in this order, in
`lambda_utils/identity/phone_ownership.py` (new, additive):

```
1. PutItem  CustomersTable
            Item={customerId: "PHONE#<e164>", ownerCustomerId: <new id>, createdAt: now}
            ConditionExpression="attribute_not_exists(customerId)"
   success -> this caller owns the phone, proceed to 2
   ConditionalCheckFailedException -> somebody else owns it; GetItem the reservation
                                     (strongly consistent) and ADOPT ownerCustomerId.
                                     Never create.
2. PutItem  CustomersTable  Item={customerId: <id from 1>, normalizedPhone: <e164>, ...}
            ConditionExpression="attribute_not_exists(customerId)"
```

Why this works where the original did not: the condition now guards a key **derived from the phone**,
so it is the same key for both racers and exactly one wins. Why a reservation item rather than a
`TransactWriteItems`: the reservation must be readable and adoptable by the loser, and a transaction
that fails gives the loser nothing to adopt — it would retry into the same race. The `PHONE#` prefix
in the same table follows the `REFERENCE#` / `ORDERNO#` resolve-before-generate pattern already
established for orders, so there is one idiom in this codebase rather than two.

Crash safety: a crash between 1 and 2 leaves a reservation with no customer row. The next
verification adopts the reserved id and step 2's conditional create completes it. The orphan window
is self-healing and cannot produce a second id. A reservation is **never deleted** — the whole point
is that it is permanent.

`normalizedPhone-index` stays, for lookup only, never for uniqueness: a GSI is eventually consistent
and cannot enforce a constraint. (`provision_payment_attempts_table.py` already records exactly this
reasoning for `referenceId-index`; same rule, stated again because it is the rule that was broken.)

### 8.2 A6/A7/A16 — every mutation derives from the authenticated owned session

**The rule: `customerId` is never read from a request body, a query string, a path parameter or a
header. It comes from the resolved session and from nowhere else.**

`POST /customer/profile` and `POST /customer/email` take **no** `customerId` field. If one is present
the request is refused `400 UNEXPECTED_FIELD` rather than ignored — ignoring it leaves a client
believing it works and invites the next developer to honour it. The id used for the write is
`session.customer_id`.

The shape check `identity.assert_customer_id` stays where it is and keeps its docstring's warning:
shape is not authorisation. For any read of an existing record, `customer_auth.authorize_resource`
remains the gate, with its deliberate collapsing of "not found" and "not yours" into one 401 so the
endpoint is not an existence oracle.

Checked on **every** protected operation, in this order, before any handler logic:

```
1. cookie present                       else 401 VERIFICATION_REQUIRED
2. row exists for sha256(cookie)        else 401 SESSION_EXPIRED  + clear cookie
3. row.poolId == customer pool          else 401 SESSION_EXPIRED  + clear cookie
4. revokedAt absent                     else 401 SESSION_EXPIRED  + clear cookie
5. now < absoluteExpiresAt              else 401 SESSION_EXPIRED  + clear cookie + delete row
6. now < idleExpiresAt                  else 401 SESSION_EXPIRED  + clear cookie + delete row
7. mutation? -> CSRF gates 1 and 2      else 403 CSRF_REQUIRED    (cookie NOT cleared)
8. can_refresh ONLY, and only when tokenSource == "cognito":
       access token fresh, else refresh (§6; a non-terminal failure is 503, session kept)
   can_refresh=False  -> SKIPPED entirely. A stale accessTokenExpiresAt is NOT an error (§4.2)
   tokenSource == "phone_ownership" -> SKIPPED entirely. Nothing to renew (§6.2)
9. sensitive step? -> recent verification + live provider check   else 401 REAUTH_REQUIRED
10. resource read? -> authorize_resource(session, record)
```

One function, `customer_session.require_session(event, *, mutating: bool, sensitive: bool = False,
can_refresh: bool = False)`, performs 1–9 and returns `(CustomerSession, None)` or `(None, response)` —
the same shape `customer_auth.require_customer` already returns, so a handler reads identically either
way. **Step 8 is the one conditional step**, and the two conditions are independent: `can_refresh=False`
is about *where the code is running* (§4.2, finding 4), `tokenSource` is about *what the session holds*
(§6.2, finding 1). Step 9's live provider check is likewise reachable only with a token, which §8.5
resolves. A handler
that forgets the call cannot accidentally half-authorise, because there is no other way to obtain a
`customerId`.

### 8.3 A8 — email ownership is proven, not asserted

**The defect.** `email-verification/handler.py::_verify` ends with
`_mark_email_verified(body.get("customerId"))`. The endpoint requires **no session** (documented as
deliberate), so anyone who can verify a code for an address they control can stamp `emailVerifiedAt`
on **any** customer id they can guess or enumerate. The code checks `is_customer_id()` — shape, not
ownership — and `CUS_<ULID>` is time-sortable, which makes enumeration cheaper than random.

**The fix, in three parts:**

1. **The challenge binds both facts — as separate parts, not a pre-joined string.** `otp_challenge`
   HMACs over `"\x1f".join(parts)` and `_digest`'s docstring states the precondition outright: *"The
   separator cannot occur in any part."* Pass 1 set `subject = f"{session.customer_id}\x1f{email}"`,
   which pushes the separator *inside* a part and cancels the exact guarantee the helper is built on.
   The review found no constructible collision given fixed-width `CUS_<ULID>` ids — so this was latent,
   not exploitable — but a structural guarantee that this design elsewhere insists on holding "by
   construction rather than by a check someone might forget" cannot be quietly suspended here.

   The fix is additive and keeps every existing two-argument caller working. `challenge_key`, `issue`
   and `verify` gain a `*extra` passthrough, and the parts reach `_digest` as parts:

   ```python
   # lambda_utils/otp_challenge.py
   def challenge_key(pepper: str, purpose: str, subject: str, *extra: str) -> str:
       """The table key for one (purpose, subject[, ...]) tuple. Contains no plaintext subject.

       Extra parts are passed to _digest as SEPARATE parts and are never joined into `subject`:
       the \\x1f separator's entire guarantee is that it cannot occur inside a part, so
       pre-joining would reintroduce the collision it exists to prevent.
       """
       if not purpose or not subject:
           raise ValueError("purpose and subject are required")
       return KEY_PREFIX + _digest(pepper, "subject", purpose, subject, *extra)[:40]
   ```

   `issue` and `verify` take the same `*extra` and must thread it into **both** digests — the key
   digest *and* the code digest `_digest(pepper, "code", purpose, subject, code)` at lines 254 and 318
   (M17). Threading one and not the other produces a key that is found and a code that never matches,
   which reads as "wrong code" forever. The call site becomes
   `challenge_key(pepper, "customer_email_ownership", session.customer_id, email)`.

   A code minted for one session then cannot verify for another, and a code minted for one address
   cannot verify another address. The existing `email_verification` purpose is left alone, so no
   outstanding challenge is invalidated, and the two-argument form is unchanged for every current
   caller. T-18 adds the collision case: two different `(customer_id, email)` pairs whose naive
   concatenation would coincide must produce different keys **and** different code digests.
2. **The route is cookie-authenticated.** `POST /customer/email` goes through
   `require_session(mutating=True)`. The customer id for the stamp is `session.customer_id`. A
   `customerId` in the body is refused.
3. **The old handler's unauthenticated stamp path is removed**, not merely bypassed. `_mark_email_verified`
   loses its `customer_id` parameter and the `CUSTOMERS_TABLE` write, becoming verify-only; the stamp
   moves to the session function where a session exists. `amplify/functions/auth/email-verification/`
   is in owned paths, and the function is **not deployed** (M8), so this costs no migration.

Email ownership also gets an **address-level reservation**, same mechanism as §8.1 with key
`EMAIL#<normalized>`, so two customers cannot both hold one verified address. On a conditional
failure the response is the same opaque `INVALID_OR_EXPIRED` the module already returns for every
other failure — "that address belongs to someone else" is an enumeration oracle and must not be said.

`normalize_email` is reused unchanged, including its deliberate refusal to strip dots and `+tags`.

### 8.4 A9 — rotate the session id after auth and after a privilege or identity change

Session fixation defence. The session id is rotated — a **new** `secrets.token_urlsafe(32)`, a new
row, the old row deleted in the same request, a fresh `Set-Cookie` — at exactly these points:

| Event | Rotate | Also |
|---|---|---|
| successful OTP sign-in | yes — the row is created here, so the id a visitor arrived with can never become an authenticated id | new CSRF token |
| phone of record changed | yes | new CSRF token; all **other** sessions for the customer revoked |
| email of record changed | yes | new CSRF token |
| step up to a sensitive operation | yes | new CSRF token |
| ordinary refresh | **no** | the id is already unguessable and rotating it per hour would race across tabs for no gain |
| sign-out | n/a | row deleted, cookie cleared |

The CSRF token is rotated with the id, always: a stale CSRF token bound to a dead row would fail
Gate 1 and look like a bug. The client re-reads both with `GET /customer/session` after any flow that
rotates, and `src/lib/customerSession.ts` does this automatically on any `409 SESSION_ROTATED`.

### 8.5 A10 — recent verification for identity change, without an OTP on ordinary checkout

A **sensitive step** is: change the phone of record, change the email of record, or revoke other
sessions. Nothing else. Explicitly **not** sensitive: checkout, address entry, payment initiation,
payment retry, order lookup, receipt download — none of those may demand an OTP, which is the whole
point of having a 29-day session.

A sensitive step requires `now - session.last_verified_at <= 600` (10 minutes), where the record's
`lastVerifiedAt` is set **only** by a completed OTP challenge. Outside that window the response is
`401 {"error":"REAUTH_REQUIRED"}`, the client runs one OTP, and `lastVerifiedAt` is refreshed on the
rotated session. 10 minutes matches `AuthSessionValidity` (M7), so the step-up window and the
provider's challenge window agree instead of one outliving the other.

A sensitive step **also** performs a live `GetUser` against Cognito with the stored access token, so
a disabled or deleted user cannot complete one inside the ≤60-minute revocation window of §7.2. This
is the one place the provider is on the request path, and it is the one place that is worth it.

**On a tokenless session there is no access token to present, so the step-up is stronger instead of
weaker.** A `tokenSource == "phone_ownership"` session reaching step 9 is refused with
`401 REAUTH_REQUIRED` **unconditionally** — `session.last_verified_at` is not consulted, because the point of the
live check is provider-backed liveness and the row cannot supply it. The client then runs one OTP, and
that OTP goes through the **Cognito `CUSTOM_AUTH`** flow, because by this point the user exists (it was
created in §8.8 step 6b.iii). Completing it yields real tokens, so the rotated session (§8.4) is written
with `tokenSource="cognito"`, a fresh `lastVerifiedAt`, and the step proceeds with the live `GetUser`
available.

The sequence is worth stating plainly because it is the mechanism that bounds §7.2's tokenless
exposure:

```
tokenless session + sensitive step
  -> 401 REAUTH_REQUIRED          (always; no 600s grace applies)
  -> one Cognito CUSTOM_AUTH OTP  (the user exists now)
  -> rotate: new id, new CSRF, tokenSource="cognito", tokens stored
  -> live GetUser, then the sensitive step runs
```

So a tokenless session can never perform a phone change, an email change or a revoke-others, and the
upgrade is a side effect of the step-up the shopper was going to do anyway — no extra prompt, no second
code, and one fewer long-lived tokenless session. T-22 drives this path and asserts the post-step-up row
is `cognito`. T-31 asserts a tokenless session is refused the sensitive step even **inside** the 600s
window, which is the case a naive `lastVerifiedAt`-only check would wrongly allow.

### 8.6 A10 — the OTP pepper reference, and the PutItem-denied send-counter rollover

**Finding, re-measured and confirmed (M10/M11).** The role `wecare-customer-whatsapp-auth-role`
carries exactly one DynamoDB permission, `dynamodb:UpdateItem`. `PutItem` is `implicitDeny`.
`_consume_send_budget` in `customer-whatsapp-auth/handler.py` uses `put_item` on window rollover and
**fails closed**:

```python
if now - started >= SEND_WINDOW_SECONDS:
    try:
        _probe_table().put_item(Item={...})          # DENIED, every time
    except Exception as exc:
        raise OtpSendThrottled("send budget could not be rolled") from exc
```

Consequence: the first send after any one-hour window boundary raises `OtpSendThrottled`, and the
caller's handler **suppresses the message while still issuing the challenge** — so the customer sees
"code sent", waits, and no code ever arrives. No error reaches the browser. This is a live,
silent, total OTP outage on a rolled window, and it is not hypothetical: the IAM simulation says so.

**The fix is in the code, not in IAM.** Replace the rollover `put_item` with a conditional
`update_item` that is already permitted:

```python
table.update_item(
    Key={"grantId": f"otpsend#{digits}"},
    UpdateExpression=("SET sends = :one, windowStartedAt = :now, expiresAt = :exp"),
    ConditionExpression="attribute_not_exists(windowStartedAt) OR windowStartedAt <= :cutoff",
    ExpressionAttributeValues={":one": 1, ":now": now, ":exp": now + SEND_WINDOW_SECONDS,
                               ":cutoff": now - SEND_WINDOW_SECONDS},
)
```

`SET sends = :one` rather than `ADD`, because this is a reset. The condition makes the roll
idempotent and race-safe: two concurrent rollovers, one wins, the loser's
`ConditionalCheckFailedException` means somebody already rolled the window — which is success, not
failure, so it is caught and treated as rolled rather than raising `OtpSendThrottled`. **Fail-closed
is preserved for every genuine storage error**; only the "already rolled" condition is treated as
benign, and `tests/test_customer_whatsapp_auth.py` gains a case asserting that a real
`ProvisionedThroughputExceededException` still raises (§14, T-03).

Preferring the code fix has a second benefit: `otp_throttle._consume` has the **identical** pattern
(`table.put_item` on window roll, fail-closed) and is used by the two HTTP OTP doors. Fixing the
shape in both places removes the defect class rather than one instance. `otp_throttle.py` is a shared
module and is not under `ecommerce/`; its only importers are the two auth handlers and the new
session function, so the blast radius is inside owned paths.

**The `otpprobe#` counter is deliberately left alone, and here is why that is not an oversight.**
`_probe_budget_exhausted` (`customer-whatsapp-auth/handler.py:112`) does
`ADD probes :one SET expiresAt = if_not_exists(expiresAt, :exp)` with **no `windowStartedAt` and no
rollover at all** — it relies entirely on TTL, which `otp_throttle`'s own module docstring and §5.3
both argue is best-effort and can lag by hours. So the probe window can stay over budget past its
nominal hour. The difference from the send counter is the failure direction: the probe counter **fails
open**, so a lagged window weakens the enumeration budget rather than locking anyone out. It is
therefore a weaker limit, not an outage, and it is **out of scope for this change** — named here so the
next reader does not assume both counters received the same treatment. If it is ever tightened, the
same conditional `update_item` shape above applies unchanged.

**The IAM change is REPORTED, not performed, and is not needed if the code fix lands:**

> **C-2** — if a future caller genuinely needs `PutItem`, add exactly that action to the existing
> inline policy `wecare-otp-probe-counter` on `wecare-customer-whatsapp-auth-role`, resource
> `arn:aws:dynamodb:us-east-1:775261844268:table/stack-wecare-digital-DownloadGrantsTable`. **No
> wildcard, no second resource, and not on the shared fleet role** — M11 confirms this role is
> dedicated to this one function, which is what makes the addition narrow. The design does not make
> this change because the code fix removes the need for it, and a permission that is not needed
> should not be granted.

**The pepper reference, re-checked.** `OTP_PEPPER_SECRET_ID` defaults to `wecare/otp/pepper`
(both OTP handlers). M12 confirms **the secret does not exist**. Both handlers read it lazily at
request time through `boto3` inside the Lambda, which is the correct pattern — the prohibition is on
shell/CLI retrieval and on values on a command line, not on a function reading its own secret. Two
things follow:

- The reference is correct and is left as-is. The read stays lazy; a module-scope read would freeze
  the value into a warm sandbox and survive a rotation.
- **Precondition P2:** the secret must exist before either OTP door can function.
  `provision_email_verification.py` owns its creation. This design does **not** create it, does not
  read it, and does not name a value. The new session function needs it too (for §8.3), so its role
  grants `secretsmanager:GetSecretValue` on `arn:...:secret:wecare/otp/pepper-*` and nothing else,
  and `--verify` asserts the secret has a current version without reading it (`describe-secret`,
  metadata only — the same check `provision_customer_registration.py` already performs).

### 8.7 OTP expiry, replay protection, and throttling on a trustworthy IP

**Expiry and replay are already correct in `otp_challenge` and must be preserved**: TTL via
`expiresAtEpoch`, attempt cap, resend cooldown, resend window, and single-use enforced by a
`ConditionExpression="consumed = :false"` so two simultaneous submissions of one correct code cannot
both succeed. The new session flow uses that module and adds nothing of its own. A `NO_CHALLENGE`,
`EXPIRED`, `ALREADY_USED`, `CODE_INCORRECT` and `ATTEMPTS_EXHAUSTED` keep collapsing to one public
answer.

The Cognito `CUSTOM_AUTH` path has its own expiry (`expiresAt` in `privateChallengeParameters`,
checked in `_verify_auth_challenge`) and `MAX_ATTEMPTS=3` via `DefineAuthChallenge`. Unchanged.

**Client IP.** `otp_throttle.source_ip` reads `requestContext.http.sourceIp` then
`requestContext.identity.sourceIp`, and its docstring already states that `X-Forwarded-For` is
deliberately not consulted. That is the correct rule and this design **keeps it**, with one
measured wrinkle that must be written down:

> Requests arrive through the Amplify/CloudFront rewrite (M1), so `requestContext.http.sourceIp` is
> the **CloudFront edge node**, not the shopper. Per-IP throttling therefore buckets many shoppers
> into few buckets, which makes the IP axis **weaker than it reads** — it still bounds a single
> origin hammering one edge, but it will not isolate one abuser from an edge's worth of legitimate
> traffic.

The response is explicitly **not** to start trusting `X-Forwarded-For`: a client-supplied header can
be rotated per request, which defeats the limit entirely, and with **no WAF in this account** there is
nothing in front that would strip or normalise it. Instead:

- the **per-phone** axis is treated as the primary control, because it is the axis that protects the
  person whose handset rings and it is unaffected by the proxy;
- the per-IP axis is kept, with its limit **raised** from 20 to 60 per hour to reflect that a bucket is
  now an edge rather than a household, so it bounds a flood without locking out a city;
- `DEFAULT_IP_MAX`'s docstring records why the number moved, so it is not "tuned" back later by
  someone reading it as a household limit;
- a third axis is added for the session function only: per-`customerId`, from the **session**, which
  cannot be spoofed at all and is the strongest axis available for any authenticated OTP (the
  sensitive-step step-up in §8.5).

`EnablePropagateAdditionalUserContextData` is `false` (M7), so no client context reaches the Cognito
triggers and the trigger-side per-IP limiting remains structurally impossible. Unchanged, and now
recorded with its reason in one place.

### 8.8 A new number: VERIFY FIRST, PROVISION SECOND

Review finding 4. Pass 1 said two incompatible things — §3 said `/challenge` does "`InitiateAuth
CUSTOM_AUTH` (or registration OTP)" while §9.3 promised the server "provisions the login and issues
**one** Cognito challenge" — and the second one, taken literally, is a hole. Cognito cannot issue a
challenge to a user that does not exist, so "one Cognito code for a new number" means
`AdminCreateUser` runs **from an unauthenticated request, before any proof that the caller holds the
phone**. That would:

- convert `AllowAdminCreateUserOnly: true` (M7) from closed self-signup into open self-signup behind
  our own endpoint;
- mint `PHONE#<e164>` reservations — which §8.1 says are **never deleted** — for numbers nobody owns;
- do both with **no WAF** in the account and an IP axis that §8.7 admits is an edge node, not a
  shopper.

So the order is inverted. The shopper still types exactly **one** code; what changes is which code it
is and when anything is created.

```
POST /customer/session/challenge          (unauthenticated)
  1. require_explicit_e164(phone)                                     §9.2
  2. otp_throttle: per-phone (primary) and per-IP (coarse)            §8.7
  3. AdminGetUser(pool, e164)    ← the ONE Cognito call here, and it CREATES NOTHING
       exists  -> InitiateAuth CUSTOM_AUTH; the trigger sends the code; store the
                  provider `Session` on an otp# row; return an opaque handle
       absent  -> otp_challenge.issue(purpose="customer_phone_ownership", subject=e164)
                  send that code over WhatsApp ourselves; return an opaque handle
  4. return 200 {"status":"code_sent","expiresInSeconds":N}  — IDENTICAL in both branches
```

```
POST /customer/session        {challengeHandle, code, remember}
  5. load the otp# row by handle; it records which branch issued the code. The BROWSER
     never learns which, and cannot choose: the branch is server state, not a parameter
  6a. existing user  -> RespondToAuthChallenge -> tokens
  6b. new user       -> otp_challenge.verify(purpose="customer_phone_ownership", ...)
        FAILS  -> 401 {"status":"invalid_code"}; NOTHING has been created. Stop
        PASSES -> and only now, in this order:
          i.   phone_ownership.reserve_phone(e164)      conditional PutItem, §8.1
          ii.  create the CustomersTable row            conditional PutItem, §8.1
          iii. AdminCreateUser(MessageAction="SUPPRESS") + AdminSetUserPassword   §8.8.1
               -> read cognitoSub from the AdminCreateUser response
          iv.  NO Cognito authentication call at all. Mint a TOKENLESS session:
               tokenSource="phone_ownership", no refreshTokenEnc, no accessTokenEnc
  7. create the session (both tables, one TransactWriteItems), Set-Cookie, return CSRF
```

#### 8.8.0 Step 6b.iv — why the first session is TOKENLESS

This is review finding 1, and pass 2 was not merely imprecise here, it specified something that
**cannot be built**. Pass 2 said step 6b.iv does `InitiateAuth CUSTOM_AUTH` then
`RespondToAuthChallenge` "with a **SERVER-HELD answer**". M22 is the measurement that kills it: the code
is generated inside `_create_auth_challenge` and written **only** to
`event["response"]["privateChallengeParameters"]["answer"]`, which Cognito delivers **only** to
`VerifyAuthChallengeResponse`. No handler other than the trigger can read it, nothing writes the
plaintext anywhere else, and the trigger reads no `clientMetadata` today (zero grep hits). The session
function is the `InitiateAuth` caller and therefore has no way to learn the answer it must supply.

**And the one-line fix is worse than the gap.** The obvious close is to let the caller pass the intended
answer, or a "trust me" marker, in `ClientMetadata`, and have `CreateAuthChallenge` honour it.
`InitiateAuth` is an **unauthenticated** API on a client with `GenerateSecret: false` — a browser can
pass exactly the same `ClientMetadata` the session function would. Any trigger that takes its answer, or
a skip-verification signal, from that channel converts the entire WhatsApp OTP flow into "state the code
you want to use". Pass 2 introduced a `SUPPRESS_SEND` client-metadata flag on this exact trigger without
noting that the channel is attacker-writable, which is precisely how that lands by accident.

**Decision: remedy (b). The first session carries no Cognito token. `SUPPRESS_SEND` is DELETED, not
secured.** The review's remedy (a) — `AdminInitiateAuth`/`AdminRespondToAuthChallenge` plus a
CMK-encrypted 120-second escrow of the plaintext answer, readable only by the session role — is
implementable and is rejected on three grounds, in descending weight:

1. **It still needs an attacker-writable flag.** A `CUSTOM_AUTH` trigger receives no indication whether
   it was invoked through the admin API or the public one, so `SUPPRESS_SEND` would remain settable by
   any browser. Remedy (a) can bound what the flag *does* (suppress our own message, write an escrow row
   the caller cannot read) but it cannot remove the channel, and a flag on this trigger is a permanent
   invitation to grow a second meaning.
2. **It creates a new plaintext-OTP store.** The escrow row holds a live code in a DynamoDB table. This
   repo's existing discipline is the opposite — `otp_challenge` stores a **peppered digest** and refuses
   to keep a code at all. Adding a table that does keep one, to work around an API shape, trades a clean
   invariant for a 120-second window.
3. **It changes a trigger whose regression breaks all customer sign-in.** `customer-whatsapp-auth:live`
   is wired to all three `CUSTOM_AUTH` triggers. Remedy (b) needs **no change to that handler at all**
   beyond the §8.6 rollover fix it was already getting.

Remedy (b)'s cost is one new legal session state, and it is paid explicitly rather than left implicit —
which is the part pass 2 got wrong by omission. Every section that touches it now says so:

| Section | What a tokenless session means there |
|---|---|
| §4.2 | `tokenSource` is an explicit attribute on **both** tables, `"cognito"` or `"phone_ownership"`. `refreshTokenEnc`/`accessTokenEnc`/`accessTokenExpiresAt` are absent |
| §6.2 | refresh is **skipped**, not failed. No provider call, no lease, no 503, never terminal |
| §7.2 | authorisation rests on **our** verified `customer_phone_ownership` challenge; there is no provider re-validation, and the exposure's three bounds are stated |
| §8.5 | a sensitive step is refused **unconditionally** and the step-up **upgrades** the session to `cognito` |
| §5.5 | `RevokeToken` is skipped; row deletion is the whole sign-out |
| §14 | T-30, T-31 and an extended T-29 pin all of the above |

**The state is transient by construction.** It exists only for a customer's first session. Every later
sign-in takes the known-number branch, because `AdminGetUser` now finds the user, so it is a Cognito
`CUSTOM_AUTH` session with tokens. A step-up upgrades it sooner. Nothing refreshes it into permanence.

**And the one-code promise is now literally true**, which it was not in pass 2: the shopper answers
exactly one code, and for a new number there is no second provider round trip at all — not an invisible
one, not a suppressed one. §9.3 is corrected accordingly.

#### The ordering property, and what happens to `customer-registration`

**Nothing is created before verification.** That is the whole property, and it is enforced by
ordering rather than by a check: there is no code path in which `reserve_phone`, a `CustomersTable`
write or `AdminCreateUser` is reachable before `otp_challenge.verify` has returned success.
`tests/test_customer_session_identity.py` asserts it the only way that is meaningful — by driving
`/challenge` and a **failing** `/session` against fakes and asserting the reservation table, the
customers table and the Cognito fake all received **zero** writes (§14, T-29).

**What happens to `customer-registration`.** It stops being on the sign-in path. §9.3 already removes
the client-side two-code branch; this revision states the server-side consequence plainly: the
reservation primitive of §8.1 is called by **the session function**, and
`customer-registration/handler.py` is changed to call the same primitive only so the two cannot
diverge if it is ever deployed. It remains undeployed (M8) and no route points at it. It is not
orphaned-and-ignored; it is orphaned-and-pinned by `tests/test_customer_registration_handler.py`
staying green.

#### 8.8.1 The Cognito admin calls, and the IAM they need

`InitiateAuth`, `RespondToAuthChallenge`, `GetUser`, `RevokeToken` and `GetTokensFromRefreshToken` are
unauthenticated-caller APIs and need **no** IAM. These four do, and pass 1 never listed them — §11.1's
table now carries them. **`AdminInitiateAuth` and `AdminRespondToAuthChallenge` are deliberately NOT
granted**, and that absence is load-bearing: they were remedy (a)'s requirement in §8.8.0, which this
design rejected, and granting them would make an authentication-bypass-shaped implementation reachable
from the role.

| Action | Resource | Why |
|---|---|---|
| `cognito-idp:AdminGetUser` | the customer pool ARN | the branch decision at step 3. A read |
| `cognito-idp:AdminCreateUser` | the customer pool ARN | step 6b.iii, **only after verification** |
| `cognito-idp:AdminSetUserPassword` | the customer pool ARN | step 6b.iii; the pool is OTP-keyed, so the password exists only to satisfy the API and is `secrets.token_urlsafe(32)`, never logged, never stored, never returned |
| `cognito-idp:AdminUpdateUserAttributes` | the customer pool ARN | stamping `custom:customer_id` (subject to C-1) and `custom:partner_waba_id`, which `customer-whatsapp-auth` fails closed without |

All four are scoped to `arn:aws:cognito-idp:us-east-1:775261844268:userpool/us-east-1_46ULYuukt` and
to no other resource. `AdminDeleteUser` is **not** granted: nothing in this design deletes a Cognito
user, and a self-healing orphan (§8.1) is preferable to a delete path that could be driven.

**`AdminGetUser` is not an enumeration oracle**, because its result never reaches the client: both
branches of step 4 return the identical body, identical status and identical shape (§9.3, T-23). The
oracle `PreventUserExistenceErrors: ENABLED` exists to close stays closed, and the server now knows
something the browser does not — which is the correct direction for that knowledge to flow.

## 9. Phone input and the copy contract

### 9.1 EXTEND the PR #175 divided field. Do not regress it

`src/components/PhoneField.tsx` is the baseline: one outlined container, 52px min-height, 10px radius,
a `<select>` code segment with `aria-label="Country code"`, a `tel-national` `<input>` number segment,
a `border-inline-end` hairline divider, **per-segment inset focus rings** (`outline-offset:-3px`,
because two focusable controls in one box cannot share one ring without failing WCAG 2.4.7), logical
per-corner radii so it mirrors in RTL, and **no red** for the invalid state.

**Forbidden, explicitly:** restoring a single combined input; adding a locale- or
`Intl.DateTimeFormat`-inferring country selector; adding a flag-emoji selector; changing the divider
to a separate element; moving to a container-level `:focus-within` ring; introducing any red.
`src/pages/workspace/contacts/index.tsx` imports `DIAL_CODES` too, so `src/lib/dialCodes.ts` is a
shared list — entries may be **added**, never removed or reordered away from India-first.

**What is added, and only this:**

| Addition | Where | Why |
|---|---|---|
| `onBlur` handler prop (optional) | `PhoneField.tsx` | lets the page validate on blur instead of only on submit; no visual change |
| `autoComplete="tel-country-code"` on the select | `PhoneField.tsx` | the select currently has none, so a browser cannot fill the code half of a stored `tel`; the number half already has `tel-national` |
| `aria-busy` passthrough | `PhoneField.tsx` | the field is disabled during a send; `aria-busy` names why |
| `DIAL_CODES` unchanged | `dialCodes.ts` | nothing to add for this work |

`DEFAULT_DIAL_CODE = '+91'` stays a **visible editable default**, never an inference. The select is
**always submitted** — a `<select>` carrying a default cannot be empty, so it needs no `required`
attribute and **does not have one.** M23 confirms `required` sits on the `tel-national` `<input>`
(`PhoneField.tsx:134`) and not on the `<select>` (`:106`). Pass 2's prose asserted the attribute existed
on the select; the behaviour was already right and the sentence was wrong, so the sentence changed and
**no attribute is added** — adding one would be a PR #175 regression dressed as a fix. T-15 asserts this
exact split (`required` on the number segment, absent on the code segment) because it is the only guard
against someone "tidying" it in either direction.

### 9.2 The validation rule, and where it is enforced

| Input | Rule | On failure |
|---|---|---|
| dial code segment | one of `DIAL_CODES`; always present, no `required` attribute needed | cannot fail — a `<select>` with a default always has a value |
| composed value, **client** side | **10–15 digits after composition**, counting the country code (M23 — the same bound the server delegate enforces, so the two cannot disagree) | `MSG.BAD_NUMBER` |
| pasted `+…` or `00…` in the number segment | the **typed** code wins over the selector; strip the prefix, then leading zeros | composed as typed |
| bare national digits with **no** explicit code anywhere | **REJECTED** | `MSG.BAD_NUMBER` |
| composed value, **server** side | E.164, explicit country code required, then the delegate's **10–15 digits** | `400 {"status":"invalid_phone"}` → `MSG.BAD_NUMBER`, for the prefix check **and** for the delegate's `InvalidPhoneNumber` (§10) |

`composeE164` in `sign-in.tsx` already implements the client half, including the deliberate refusal to
concatenate a contradictory pasted prefix. Unchanged.

**The server half is new and is the part that matters**, because the browser is not a trust boundary.
`identity.customer.normalize_phone` currently infers `+91` for any ten digits beginning 6–9 — that is
inferring a country from **length**, which the requirement forbids. It is **not changed**: it is
imported by the foreign `ecommerce/` work and by `secure-files`, and a two-sided normalisation change
is how a customer signs in and owns nothing. Instead, a new additive module:

```python
# lambda_utils/identity/phone_input.py            NEW, additive, no existing caller affected
def require_explicit_e164(raw: str) -> str:
    """E.164 with an EXPLICIT country code. Bare national digits are refused.

    Accepts '+<cc><national>' and '00<cc><national>'. Refuses a value whose country code was
    not stated, because inferring one from length is how a Dubai number becomes an Indian one
    silently. Delegates the final shape to identity.normalize_phone AFTER the explicit prefix
    has been proven, so the two agree on the result and only the entry condition differs.

    The DELEGATE owns the length bound: normalize_phone accepts 10..15 digits and raises
    InvalidPhoneNumber outside that (identity/customer.py:147, M23). This function does not
    restate the bound - a second copy of a number is a second thing to get wrong - and its
    caller MUST catch InvalidPhoneNumber, which is the delegate's refusal and not an
    unexpected fault (§10).
    """
```

**The bound is 10–15 digits after composition, and the delegate's exception is part of the contract.**
Pass 2's tables said "4–15", which review finding 12 showed is narrower than the code it delegates to in
the direction that matters: `+12345` satisfies every rule pass 2 stated and is **rejected** by
`normalize_phone` with `InvalidPhoneNumber`, an exception pass 2's error table never mentioned — so it
would have fallen through to the generic `500 INTERNAL_ERROR` instead of the user-fixable `400`. §10 now
maps it explicitly, and both tables state 10–15.

The session function's `/customer/session/challenge` calls `require_explicit_e164` **before**
`normalize_phone`. So the length inference inside `normalize_phone` still exists for its existing
callers and is unreachable from the new door, which is the smallest change that satisfies the
requirement without a fleet-wide normalisation edit.

**`customerAuth.normaliseMobile`'s docblock must say what is now true in one direction only.** The
function still does `digits.length === 10 && /^[6-9]/ ? '91'+digits : digits`, and it is **exported**,
so a docblock forbidding client/server divergence while the server door forbids the inference is a
docblock describing a rule that no longer holds symmetrically. The stricter server rule can only
reject input the client would also reject, so nothing breaks — but the note has to be accurate or the
next reader will either "fix" the client to match or add a caller that depends on the inference. The
exact addition:

```
 * The public sign-in door additionally requires an EXPLICIT country code server-side
 * (identity.phone_input.require_explicit_e164). The ten-digit `91` inference below is retained
 * for existing callers and is unreachable from the divided PhoneField, which always submits a
 * code. Do not add a new caller that depends on the inference.
```

### 9.3 The copy, verbatim

Already present in `sign-in.tsx`'s `MSG` table and **not to be reworded**. The exact strings:

| Key | String | Shown when |
|---|---|---|
| hint | `Pick your country code, then the number WhatsApp is on.` | always, under the field |
| `BAD_NUMBER` | `Enter a valid number.` | client validation, or `400 invalid_phone` |
| `CHECK_NUMBER` | `Couldn’t send a code. Check your number.` | `502` / `send_failed` — delivery failed, cause unknown |
| `TRY_LATER` | `Try again shortly.` | any `5xx` that is not a send failure; offline; `503` |
| `BAD_CODE` | `Check your code.` | wrong code, attempts remain |
| `CODE_EXPIRED` | `Code expired. Send a new one.` | challenge dead / `NotAuthorized` / `410` |
| `RATE_LIMITED` | `Wait before trying again.` | `429` on either axis |
| `NOT_ON_WHATSAPP` | `Use a WhatsApp number.` | **only** on a reliable provider-confirmed unsupported-destination signal — see below |

Note the typographic apostrophe in `Couldn’t` (U+2019); it is in the source as `\u2019` and must stay.

**`Use a WhatsApp number.` stays unused until the evidence exists.** A `502`, a timeout, or
`{"status":"send_failed"}` is **not** evidence: that path covers a genuinely unreachable destination
**and** a transient Meta failure, indistinguishably. Asserting the first is a confident wrong answer
about our own outage every time the second is the cause. The signal that would earn it is Meta's
recipient-not-found error surfaced by the backend — concretely, `_send_otp`/`_send_code` would have to
classify the Graph error and return a distinct `{"status":"unsupported_destination"}`. That
classification is **not** built here: `lambda_utils/graph_errors.py` exists and would be the place,
but the mapping is unverified against a live Graph response and this design will not guess it. So the
string stays defined and unreachable, with its comment, and `src/test/AccountSignIn.test.tsx` gains an
assertion that no code path renders it (§14, T-16) — which is the one way to keep an approved wording
available without letting someone wire it to the wrong condition.

**Never reveal whether a customer is registered.** The new door answers identically for a known and an
unknown number: same status, same body shape, same latency class. `PreventUserExistenceErrors` is
`ENABLED` (M7) and the `registered` flag the existing trigger returns is **not** propagated by the new
session endpoint — the branch that exists today in `sign-in.tsx` (route an unregistered number through
the registration front door) moves **server-side** into `/customer/session/challenge`, which decides
registered-vs-new itself and returns one opaque `{"status":"code_sent","expiresInSeconds":N}` either
way. That removes the enumeration oracle *and* the two-code user experience in one change.

**The shopper answers exactly one code. Which code it is differs, and §8.8 is the authority on that.**
Pass 1 wrote "the server provisions the login and issues one Cognito challenge", which the review
correctly read as provisioning a Cognito user from an unauthenticated request before any proof of phone
ownership. It does not. For a known number the single code is Cognito's `CUSTOM_AUTH` code; for an
unknown number it is our own `otp_challenge` code under purpose `customer_phone_ownership`, and the
Cognito user, the `PHONE#` reservation and the customer row come into existence **only after** that code
verifies. From the browser's side the two branches are indistinguishable, which is both the privacy
property and the user-experience one.

**Corrected in pass 3.** Pass 2 ended that paragraph with "the second, Cognito-side round trip for a new
customer is server-to-server and invisible". There **is no second round trip.** M22 showed it was
unimplementable and §8.8.0 replaces it: a new customer's first session is tokenless, minted from the
`customer_phone_ownership` challenge our own code verified, and no Cognito authentication call is made at
all. One code, one verification, one session — and nothing suppressed, so there is no path by which a
shopper receives a WhatsApp message they did not ask for.

**No red states.** Errors render in the existing `.si-error` treatment — lime state tint
`rgba(209,244,112,.22)`, 4px `#d1f470` inline-start edge, `#1a3a2a` text at weight 700, `role="alert"`,
plus `aria-invalid` and `aria-describedby` on the field. Homepage palette only: `#1a1a1a`, `#1a3a2a`,
`#d1f470`, `#e5e7eb`, `rgba(0,0,0,.898)`, `rgba(0,0,0,.54)`. No new hex value is introduced.

**No SMS fallback, anywhere.** WhatsApp is the only OTP channel. India DLT registration, the
`ap-south-1` sender and `ivr-default` are irrelevant here and must not be reached for; a failed
WhatsApp send is a retry, never a channel switch.

---

## 10. Error handling, per operation

Every row states the condition, whether it is recoverable, what the caller receives, and what is
logged. "Logged" always means metadata only — `type(exc).__name__`, an event name, counts. **No
phone, no email, no code, no token, no cookie value, no customer id in any log line.**

| Operation | Failure | Recoverable | Caller receives | Logged at |
|---|---|---|---|---|
| `POST /challenge` | phone fails `require_explicit_e164`'s **explicit-prefix** check | yes, user | `400 {"status":"invalid_phone"}` | INFO `otp_invalid_phone` |
| | **`InvalidPhoneNumber` raised by the `normalize_phone` delegate** (fewer than 10 or more than 15 digits after composition, M23) | yes, user | **the same** `400 {"status":"invalid_phone"}` → `MSG.BAD_NUMBER`. It is a user-fixable refusal, **not** a fault, so it must not reach the generic `500` | INFO `otp_invalid_phone`, **type name only** |
| | per-phone or per-IP throttle hit | yes, wait | `429 {"status":"too_many_requests","retryAfterSeconds":N}` — axis **not** named | WARN `otp_throttled` + axis |
| | throttle store unreadable | no | `503 TEMPORARILY_UNAVAILABLE` — **fails closed**, no send | ERROR, type only |
| | resend cooldown / resend limit | yes, wait | `429` as above | INFO |
| | Cognito `InitiateAuth` 5xx or timeout | yes | `503` + `Retry-After: 5` | ERROR, type only |
| | WhatsApp send failed | yes | `502 {"status":"send_failed"}` → `MSG.CHECK_NUMBER` | ERROR, type only, **never** the number |
| | pepper secret absent (P2) | no | `503 TEMPORARILY_UNAVAILABLE` | ERROR `otp_pepper_unavailable`, **no value, no boolean about a value** |
| | `AdminGetUser` fails (not `UserNotFoundException`) | yes | `503` + `Retry-After: 5`. **Never** fall through to the new-number branch on an ambiguous error — that would provision on a provider blip | ERROR, type only |
| | `AdminGetUser` returns `UserNotFoundException` | n/a | the new-number branch; still `200 {"status":"code_sent",…}`, **identical body** (§9.3) | INFO, no number, no `registered` flag |
| `POST /session` | code wrong / expired / used / never issued | yes | **one** `401 {"status":"invalid_code"}` | INFO + real outcome, server-side only |
| | attempts exhausted | yes, new code | `401` as above | INFO |
| | phone reservation race lost | n/a | adopt the existing customer, **continue** | INFO `phone_owner_adopted` |
| | `CustomersTable` write fails | no | `503` | ERROR, type only |
| | the two-table `TransactWriteItems` fails (incl. `TransactionCanceledException`) | no | `503`, **no cookie set** | ERROR, type only. All-or-nothing, so neither row exists and there is nothing to clean up (§4.2) |
| | code verified but a later provisioning step fails (§8.8 steps 6b.i–iv) | no | `503` | ERROR, type only. The reservation is self-healing and is **never** deleted (§8.1); the next attempt adopts it |
| any cookie op | no cookie | n/a | `401 VERIFICATION_REQUIRED` | none (ordinary) |
| | unknown / revoked / expired row | no | `401 SESSION_EXPIRED` + clear cookie | INFO `session_rejected` + reason |
| | wrong pool on row | no | `401 SESSION_EXPIRED` + clear cookie | WARN `session_wrong_pool` |
| | CSRF gate 1 or 2 fails | yes, re-read | `403 CSRF_REQUIRED`, **cookie kept** | WARN `csrf_rejected` + gate number |
| | sensitive step, stale verification | yes, one OTP | `401 REAUTH_REQUIRED` | INFO |
| | id rotated mid-flight | yes, retry | `409 SESSION_ROTATED` | INFO |
| refresh | terminal Cognito rejection (4 names) | no | `401 SESSION_EXPIRED` + clear cookie | INFO `session_terminal` + type |
| | throttle / 5xx / network / timeout | **yes** | `503` + `Retry-After: 5`, **session kept** | WARN, type only |
| | lease contention | yes | transparent; bounded wait then proceed | DEBUG |
| | DynamoDB unreadable | yes | `503`, **session kept, cookie untouched** | ERROR, type only |
| `DELETE /session` | `RevokeToken` fails | partially | `204` anyway; row marked `revokedAt` | WARN `signout_revoke_failed` + type |
| `POST /email` | address fails `normalize_email` | yes | `400 INVALID_EMAIL` | INFO |
| | `EMAIL#` reservation held by another customer | no | **opaque** `400 {"status":"INVALID_OR_EXPIRED"}` | WARN `email_owned_elsewhere` |
| | SES send fails | yes | `502 SEND_FAILED` | ERROR, type only |
| | body contains `customerId` | no | `400 UNEXPECTED_FIELD` | WARN `body_customer_id_rejected` |
| any | unhandled exception | no | `500 {"error":"INTERNAL_ERROR"}` | ERROR, `type(exc).__name__` **only** |

**Exception messages are never logged**, only types — a provider error message can echo a phone
number or a token back. The one exception permitted is a message this code constructed itself from
known-safe parts, and there are none in this design.

### 10.1 Validation of every external input

| Field | Required | Type / limits | On failure |
|---|---|---|---|
| `__Host-wd_cs` cookie | for cookie routes | exactly 43 chars, `[A-Za-z0-9_-]` only; anything else is treated as absent **without a table read** | `401 VERIFICATION_REQUIRED` |
| `X-WD-CSRF` | for mutations | 43 chars, same charset; compared by `hmac.compare_digest` against the stored hash | `403 CSRF_REQUIRED` |
| `Sec-Fetch-Site` | for mutations, **in Gate 2 `full` mode only** | must be `same-origin`. Not consulted in `origin_only` mode (§4.6) | `403 CSRF_REQUIRED` |
| `Origin` | **`full` mode: optional** (if present must equal `https://wecare.digital`). **`origin_only` mode: REQUIRED** and must equal it exactly | the single rule lives in §4.6; this row restates it rather than defining it | `403 CSRF_REQUIRED` |
| body | yes | JSON object ≤ **4 KB**; non-object or unparseable is `{}` | `400` |
| `phone` | `/challenge` | `require_explicit_e164`: explicit country code, then the delegate's **10–15 digits after composition** (M23) | `400 invalid_phone` for both the prefix check and the delegate's `InvalidPhoneNumber` |
| `code` | `/session` | 6 digits exactly, `str.isdigit()`, compared in constant time | `400 CODE_REQUIRED` / `401 invalid_code` |
| `challengeHandle` | `/session` | opaque server-issued string ≤ 4096 chars; the Cognito `Session` is held **server-side**, never returned to the browser | `400` |
| `remember` | optional | strict boolean; any other value is `false` | coerced, not rejected |
| `email` | `/customer/email` | `normalize_email`, ≤ 254 chars | `400 INVALID_EMAIL` |
| `firstName` / `lastName` | `/customer/profile` | `normalize_name`, ≤ 100 chars, case and script preserved | `400 INVALID_NAME` |
| `customerId` anywhere | **must be absent** | — | `400 UNEXPECTED_FIELD` |

The cookie charset check before any table read matters: it turns a malformed or injected cookie into a
zero-cost rejection rather than a DynamoDB request, which removes a trivial amplification vector on a
public endpoint with no WAF in front of it.

**`challengeHandle` deserves its own note.** Today `src/lib/customerAuth.ts` receives Cognito's
`Session` string and sends it back. Under this design the browser never sees it: the session function
stores the Cognito `Session` on a short-lived row (`otp#` namespace, 10-minute TTL matching
`AuthSessionValidity`) and hands the browser an opaque handle. One less provider artefact in the
client, and the challenge cannot be resumed from another browser.

### 10.2 Invariants and the layer that owns each

| Invariant | Owner | Why that layer |
|---|---|---|
| one customer id per normalised phone | **DynamoDB conditional write** on `PHONE#<e164>` | the only layer where concurrent racers serialise; a GSI read and an application check both lose the race |
| **one customer per verified email address** | **DynamoDB conditional write** on `EMAIL#<normalized>` | same. Corrected in pass 3 (finding 11): a write keyed on the *address* bounds customers per address, and places **no** bound on addresses per customer. §8.3's prose always had this right. If a per-customer bound is ever wanted it needs a different key — a per-customer attribute or a `CUSTOMEREMAIL#<customerId>` row — and the `EMAIL#` row does not provide it |
| `absoluteExpiresAt` never extended | **DynamoDB condition** + the update expression omitting it + a test | three layers because this is the invariant most likely to be "helpfully" relaxed |
| a code verifies once | **`otp_challenge.verify`'s** `ConditionExpression="consumed = :false"` | already correct; preserved |
| `customerId` never from a request | **`customer_session.require_session`** as the only source of a `customerId` | removing the alternative is stronger than checking for it |
| no Cognito token reaches the browser | **the session handler's response builder** (one function), plus a response-walking test | one choke point is auditable; a convention is not |
| no Cognito token reaches **another Lambda** | **IAM + the two-table split** (§4.2): the resolution table contains no token, and only the session role can read the credential table or the CMK | the only layer that holds against a *role*, which is the actual threat once `wix-store` runs on the shared fleet role (M15). An application-level convention cannot bind a different function |
| the two session rows never diverge **on `customerId`, `normalizedPhone`, `poolId`, `absoluteExpiresAt`, `revokedAt`, `csrfTokenHash` or `tokenSource`** | **one `TransactWriteItems`** per create/rotate/revoke | all-or-nothing is the only mechanism that removes the divergence case entirely rather than narrowing its window |
| the idle clock has **exactly one owner**, table 2 | **table ownership + IAM**: only table 2 is writable by the resolving roles, and every expiry verdict reads it from there | the foreign roles can write table 2 and only table 2, so a shared-ownership idle clock diverges by construction and would expire an actively-shopping customer at table 1's untouched deadline (§4.2, finding 5) |
| every cookie-authenticated mutation is CSRF-gated | **`customer_auth.require_customer`'s cookie branch**, deriving `mutating` from the HTTP method | the two busiest cookie-authenticated mutations are DO-NOT-TOUCH and cannot opt in, so the gate must not need their cooperation (§4.6) |
| nothing is created before a phone is proven | **the ordering in §8.8**: no write is reachable before `otp_challenge.verify` succeeds | removing the path is stronger than guarding it; T-29 asserts zero writes on a failed code |
| a customer cookie never authorises staff | **`middleware.require_auth` has no cookie code**, asserted by an AST test | absence is the control |
| session ≠ payment verification | **`payment_status.py`** and the payments handlers, untouched here | out of this function's reach by construction |
| no secret in a log expression | **code review + CodeQL** `py/clear-text-logging-sensitive-data` | CodeQL tracks taint across function boundaries; a boolean derived from a secret still fails, and must |

## 11. Files — created, changed, and forbidden

### 11.1 Created

| Path | What |
|---|---|
| `amplify/functions/auth/customer-session/handler.py` | the eight routes of §3; the only cookie-aware handler |
| `amplify/functions/shared/lambda_utils/customer_session.py` | the `CustomerSession(CustomerIdentity)` type (§4.2); `create`, `resolve`, `require_session`, `refresh`, `rotate`, `revoke`, `clear_cookie`, `_denied`; the cookie serialiser and the CSRF gates. Storage-agnostic, table injected, **no boto3 import at module scope**, so it is testable with no AWS |
| `amplify/functions/shared/lambda_utils/identity/phone_ownership.py` | the `PHONE#` / `EMAIL#` reservation primitives of §8.1 and §8.3 |
| `amplify/functions/shared/lambda_utils/identity/phone_input.py` | `require_explicit_e164` (§9.2) |
| `scripts/provision_customer_session.py` | role + inline policy, KMS key + alias, **both** session tables, log group, function, `live` alias, routes, Lambda permission; `--dry-run`, `--verify`, `--verify-cookie-transport`, `--retire-echo`. It carries **`REQUIRED_PERMISSIONS: list[tuple[str, str]]`** as data — the single source for both the policy document it writes and the pairs `--verify` simulates (§11.1.1), which is what makes a missing action a verifier failure rather than a production one |
| `src/lib/customerSession.ts` | the browser client: `getSession`, `startChallenge`, `completeChallenge`, `signOut`, `apiFetch` (CSRF header + 401/409 handling), per-tab single-flight. **Stores nothing** in `localStorage` or `sessionStorage`. Derives its base from `window.location.origin + '/api'`. Checks the same-origin invariant **lazily on first use**, memoised, logged once, returning a typed `ORIGIN_MISCONFIGURED` result — and **must not throw during module evaluation under any input** (§2, finding 10) |
| `scripts/check_same_origin_api_base.py` | the build-time half of the §2 invariant: fails when the resolved `NEXT_PUBLIC_API_BASE` is cross-origin. Wired as a `prebuild` step **if** `package.json` is editable; `package.json` is FOREIGN (§11.3), so if it is not, this runs inside the existing test gate instead. Either way the hard stop exists before a chunk is produced |
| `tests/test_customer_session_cookie_contract.py` | §14 T-01, T-02, T-11, T-12, **T-28** |
| `tests/test_customer_session_lifetimes.py` | T-05, T-06 |
| `tests/test_customer_session_refresh.py` | T-07, T-08, T-09, **T-31** |
| `tests/test_customer_session_csrf.py` | T-04, **T-30** |
| `tests/test_phone_ownership_reservation.py` | T-17, T-18 |
| `tests/test_phone_input_explicit_code.py` | T-19 |
| `src/test/CustomerSessionClient.test.ts` | T-10, T-13 |
| `src/test/CustomerSessionReauth.test.ts` | T-14 |
| `src/test/PhoneField.test.tsx` | **T-15.** No `PhoneField` test file exists today, which is why the PR #175 regression the task explicitly forbids had nothing stopping it |
| `tests/test_customer_session_identity.py` | **T-20, T-21, T-22, T-23, T-29** |
| `tests/test_no_sensitive_logging.py` | **T-24.** The AST sweep over §11.2's changed-file list, so CodeQL is the second line of defence and not the first |
| `docs/execution/customer-session-closure-20261001.md` | the one evidence doc the baseline allows |

Six tests had no owning file in pass 1 (review finding 11). The three files above close that; T-28 joins
`test_customer_session_cookie_contract.py`. Every test in §14 now names a file, and §14 states which.

#### 11.1.1 The session role's inline policy, enumerated

Pass 1 was precise about what `wecare-customer-session-role` must **not** have and silent about what it
must have, and M10 is a live outage in this very account caused by exactly one missing DynamoDB action.
So the policy is specified statement by statement. No wildcards in any resource, no second resource on
any statement.

| Action(s) | Resource | Why |
|---|---|---|
| `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` | `arn:aws:logs:us-east-1:775261844268:log-group:/aws/lambda/wecare-customer-session:*` | the function cannot report a failure otherwise, which is how a 500 with no log happens |
| `dynamodb:GetItem`, `PutItem`, `UpdateItem`, `DeleteItem` | `…:table/stack-wecare-digital-CustomerSessionsTable` | credential custody (§4.2 table 1) |
| `dynamodb:Query` | `…:table/stack-wecare-digital-CustomerSessionsTable/index/customerId-index` | "sign out everywhere" (§5.5). A separate statement because a table ARN does **not** cover its index |
| `dynamodb:GetItem`, `PutItem`, `UpdateItem`, `DeleteItem` | `…:table/stack-wecare-digital-CustomerSessionIndexTable` | resolution record (§4.2 table 2) |
| `kms:Decrypt`, **`kms:GenerateDataKey`** | the CMK behind `alias/wecare-customer-sessions` | `Decrypt` alone cannot **write** to a CMK-encrypted table. Omitting `GenerateDataKey` is the M10-shaped failure for this design: every read works and every write fails |
| `dynamodb:GetItem`, `PutItem`, `UpdateItem` | `…:table/stack-wecare-digital-CustomersTable` | identity, phone/email reservations (§8.1, §8.3). No `DeleteItem`: a reservation is never deleted |
| `dynamodb:Query` | `…:table/stack-wecare-digital-CustomersTable/index/normalizedPhone-index` | lookup only, never uniqueness (§8.1) |
| `dynamodb:GetItem`, `UpdateItem`, **`PutItem`** | `…:table/stack-wecare-digital-DownloadGrantsTable` | the `otp_throttle` and `otp_challenge` rows for the new door. **`PutItem` is REQUIRED**: `otp_challenge.issue` creates its row with `table.put_item` (M19, `otp_challenge.py:270`), which the unknown-number branch (§8.8 step 3), the email-ownership challenge (§8.3) and the `otp#` challenge-handle rows (§10.1) all go through. Pass 2 wrote "**No `PutItem`** — the §8.6 code fix removes the need", and that justification was simply wrong: §8.6 removes a *send-counter rollover* `put_item`, which has nothing to do with `issue`. The three flows above would each have failed `AccessDenied` on their first call, surfacing as the indistinguishable `503` of §10's "throttle store unreadable" row — the exact M10 shape this document cites as its cautionary tale. **C-2 is unaffected and stays unexercised**: it is a grant on a *different* role (`wecare-customer-whatsapp-auth-role`), and the §8.6 code fix does remove the need for *that* one |
| `secretsmanager:GetSecretValue` | `arn:aws:secretsmanager:us-east-1:775261844268:secret:wecare/otp/pepper-*` | the pepper, read **lazily at request time inside the Lambda** (§15.2). The `-*` suffix is the six-character version suffix Secrets Manager appends, not a widening |
| `cognito-idp:AdminGetUser`, `AdminCreateUser`, `AdminSetUserPassword`, `AdminUpdateUserAttributes` | `arn:aws:cognito-idp:us-east-1:775261844268:userpool/us-east-1_46ULYuukt` | §8.8.1. **No `AdminDeleteUser`**, no `AdminDisableUser`, no `AdminInitiateAuth`, no `AdminRespondToAuthChallenge` (§8.8.0 rejected the remedy that needed them), and not the staff pool |
| **`cognito-idp:DescribeUserPoolClient`** | the same customer pool ARN | §6.2 resolves `rotation_enabled` from the live client, cached 300s in module state, env var as fallback. A **read**. The response is projected to `RefreshTokenRotation.Feature` and never bound to a name or logged, because a `DescribeUserPoolClient` response can carry `ClientSecret` — which is why the baseline's own read of it was blocked and had to be narrowed |
| **`lambda:InvokeFunction`** | `arn:aws:lambda:us-east-1:775261844268:function:**wecare-whatsapp-business-api:live**` | **the only WhatsApp send path available to a non-trigger handler** (M20: `customer-registration/handler.py:94`, `:187`; `identity/registration.py::begin` takes `send_code` injected and invokes nothing itself). §8.8 step 3's unknown-number branch sends its own code, so without this the primary new-customer flow fails at the send. **Qualified ARN — the `live` alias, not `$LATEST`, and no other function** |
| **`ses:SendEmail`** | two resources on this one statement: `arn:aws:ses:us-east-1:775261844268:identity/one@wecare.digital` **and** `arn:aws:ses:us-east-1:775261844268:configuration-set/wecare-digital` | `POST /customer/email` sends the address-ownership code (M21: `email-verification/handler.py:108` → `comms/verification_email.py:279`). **SESv2 authorises a send that names a configuration set against both the identity and the configuration set**, so one resource is not enough and this is the one statement in the policy with two — named here so it does not read as a drift. Both are overridable by env (`VERIFICATION_EMAIL_SENDER`, `SES_CONFIGURATION_SET`), so `expected_environment()` pins them and `--verify` simulates the ARNs it actually configures, not these literals |

Deliberately **absent**, and each absence is load-bearing: `dynamodb:Scan` anywhere;
`dynamodb:DeleteItem` on `CustomersTable`; `kms:*` on any other key; `cognito-idp:*` on
`us-east-1_cSx0RHCIR` (the staff pool); `cognito-idp:AdminInitiateAuth` and
`AdminRespondToAuthChallenge` on **any** pool (§8.8.0); `secretsmanager:*` on any other secret;
**`lambda:InvokeFunction` on anything other than the WhatsApp sender alias** — note the wording, because
pass 2's blanket "`lambda:InvokeFunction` on anything" read as a prohibition on what the policy now has
to grant; `ses:*` beyond `SendEmail`, and `ses:SendRawEmail` in particular; `iam:PassRole`.

**The sender function's resource policy.** A same-account `lambda:InvokeFunction` is authorised by the
caller's identity policy alone — a resource-based policy on the target is additive and its absence does
not deny. So **no statement needs to be added to `wecare-whatsapp-business-api`**, and nothing about its
`live` alias changes. That is a verdict, not an assumption: §12 step 2 records it by reading
`lambda get-policy --function-name wecare-whatsapp-business-api --qualifier live` and confirming no
statement *restricts* invocation to a principal list that would exclude the new role. A read, and the
answer is written down either way.

The two **other** roles that touch this feature get one grant each and nothing more:
`wecare-digital-lambda-role` (the shared fleet role, M15) and `wecare-checkout-role` (M16) each receive
`dynamodb:GetItem` **and** `dynamodb:UpdateItem` on `CustomerSessionIndexTable` only — `GetItem` to
resolve, `UpdateItem` to advance `idleExpiresAt`/`lastSeenAt` — and **no** access to
`CustomerSessionsTable` and **no** grant on the CMK. That is the whole point of the §4.2 split: the
grant that must be wide leaks nothing, and the grant that would leak is narrow. Both are additive
statements on existing roles and both are **reported, not performed** by this design (§13, C-12).

#### `--verify`'s contract, changed: every reachable PAIR, not every written statement

Pass 2 said `--verify` "simulates **every statement above**". Review finding 2 showed that is
structurally unable to catch the class of bug it exists for: an **omitted** action is not a statement, so
the simulation is green and the live function is dead. Two of pass 3's three HIGH findings were exactly
that, in a policy written to be checkable.

So the contract is inverted:

> `--verify` simulates **every `(action, resource)` pair the handler can reach**, not every statement the
> policy happens to contain. The pair list lives **in the provisioning script as data** —
> `REQUIRED_PERMISSIONS: list[tuple[str, str]]` — and is the single source for both the policy document
> it writes and the simulation it runs. A code path that needs a new action therefore fails the
> **verifier** rather than production, because the pair has to be added to the list for the policy to
> contain it at all.

Concretely the list carries, at minimum, every pair in the table above plus the three that pass 2 omitted:
`dynamodb:PutItem` on `DownloadGrantsTable` (M19), `lambda:InvokeFunction` on the sender alias (M20), and
`ses:SendEmail` on the identity and the configuration set (M21). Each entry carries a one-line comment
naming the code path that reaches it, so the list is auditable against the handler rather than being a
second thing to keep in sync by memory.

`iam simulate-principal-policy` (a read) runs the whole list and fails on **any** `implicitDeny` — the
method that found M10 in the first place. It also asserts the **negatives**, which are what prove the
§4.2 boundary held rather than merely being intended:

| Simulation | Expected | Why |
|---|---|---|
| fleet role → `dynamodb:GetItem` on `CustomerSessionsTable` | **denied** | the credential table must stay single-custodian (M15) |
| fleet role → `kms:Decrypt` on the CMK | **denied** | same, from the key side |
| fleet role → `dynamodb:GetItem`, `UpdateItem` on `CustomerSessionIndexTable` | **allowed** | the C-12 positives, gated at §12 step 4a (finding 6) |
| `wecare-checkout-role` → the same four | same four verdicts | if the role does not exist yet (M16), that is **NOT** a pass — see §12 step 4a |

A policy that passes the positives and fails a negative is worse than one that fails loudly, because it
looks finished. And a verifier that only checks the positives it was told about, as pass 2's did, is
worse still: it looks finished *and* it is silent.

### 11.2 Changed

| Path | Change | Blast radius |
|---|---|---|
| `amplify/functions/shared/lambda_utils/customer_auth.py` | **additive** cookie branch in `require_customer`: Bearer first (unchanged), then a **method-derived `mutating`** flag and an explicit **`can_refresh=False`** into `customer_session.require_session` (§3, §4.6), which applies the CSRF gate on the callers' behalf and performs no refresh inside those two functions. `authenticate`, `authorize_resource`, `bearer_token`, the issuer pin and every exception type are untouched | imported by `ecommerce/checkout/handler.py:196` and `ecommerce/wix-store/handler.py:368` (both DO-NOT-TOUCH, both **unedited**), `ecommerce/initiation.py` and `ecommerce/customer_cart.py` (import only `authorize_resource`, unaffected). **"Unedited" is not "unaffected":** they gain a CSRF gate they do not call (§4.6), an `identity.phone` sourced from `normalizedPhone` (§4.2, M18) and an `identity.subject` of `""`. Gate: `tests/test_customer_auth_and_throttle.py`, `tests/test_cart_v2.py`, `tests/test_checkout_handler.py` must stay green, plus T-04's two-handler CSRF sweep and a `customer_cart.cart_key` case driven from a cookie-derived identity |
| `amplify/functions/shared/lambda_utils/otp_challenge.py` | **additive `*extra`** passthrough on `challenge_key`, `issue` and `verify`, threaded into **both** digests (§8.3, M17). Every existing two-argument call is byte-identical in behaviour | importers: the two auth handlers, `identity/registration.py`, the new session function. Gate: `tests/test_otp_challenge.py` must stay green unchanged — if it needs editing, the change was not additive |
| ~~`customer-whatsapp-auth/handler.py` — a `SUPPRESS_SEND` client-metadata flag~~ | **WITHDRAWN in pass 3.** §8.8.0 removed the need and the reason: `ClientMetadata` on `InitiateAuth` is **attacker-writable** (unauthenticated API, `GenerateSecret: false`), so any flag the trigger honours is a channel a browser can drive. The tokenless first session needs no suppression, so the flag is deleted rather than defended. **The trigger's only pass-3 change is the §8.6 rollover fix** | one fewer change to the handler wired to all three `CUSTOM_AUTH` triggers |
| `amplify/functions/shared/lambda_utils/otp_throttle.py` | rollover `put_item` → conditional `update_item` (§8.6); `DEFAULT_IP_MAX` 20 → 60 with the reason in the docstring (§8.7); fail-closed preserved | importers: the two auth handlers + the new function. Gate: `tests/test_otp_throttle.py` |
| `amplify/functions/auth/customer-whatsapp-auth/handler.py` | `_consume_send_budget` rollover fix (§8.6). Nothing else — triggers, WABA fail-closed, `MAX_ATTEMPTS`, the top-level `userName` read, the probe counter and the send-suppression posture all unchanged | one function. Gate: `tests/test_customer_whatsapp_auth.py` |
| `amplify/functions/auth/email-verification/handler.py` | remove the unauthenticated body-selected stamp (§8.3); `_mark_email_verified` becomes verify-only | **not deployed** (M8), so no migration |
| `amplify/functions/auth/customer-registration/handler.py` | `_create_customer` → `phone_ownership.reserve_phone` (§8.1), so it cannot diverge from the session function's copy of the same rule. It is **off the sign-in path** entirely after §8.8 and no route points at it | **not deployed** (M8). Orphaned-and-pinned rather than orphaned-and-ignored: `tests/test_customer_registration_handler.py` stays green |
| `src/components/PhoneField.tsx` | three additive props/attributes only (§9.1). No CSS value, no structural change | `sign-in.tsx`, `workspace/contacts` |
| `src/lib/customerAuth.ts` | **deprecate, do not delete.** `storeSession`/`getSession`/`clearSession` keep working behind `NEXT_PUBLIC_CUSTOMER_SESSION_COOKIE`; `requestOtp`/`submitOtp` retained for the rollback path; `normaliseMobile`'s **code** unchanged, its **docblock** corrected to state that the inference is true in one direction only and that no new caller may depend on it (§9.2) | `sign-in.tsx`, `checkout/status.tsx` |
| `src/pages/account/sign-in.tsx` | call `customerSession` behind the flag; drop the client-side register/two-code branch now that the server does it in one (§9.3); `MSG` strings **unchanged** | one page |
| `src/test/AccountSignIn.test.tsx` | extend for the one-code path and T-16 | — |

`src/lib/dialCodes.ts` is listed in owned paths and needs **no change**; it is named here so the next
reader knows that was checked rather than skipped.

### 11.3 DO NOT TOUCH

Carried from the baseline, plus what this design adds:

```
amplify/functions/payments/**
amplify/functions/shared/lambda_utils/ecommerce/**        (incl. the untracked initiation.py,
                                                           finalization.py, order_creation.py)
amplify/functions/shared/lambda_utils/integrations/razorpay_verify.py
amplify/functions/ecommerce/checkout/handler.py
amplify/functions/shared/lambda_utils/payment_status.py
amplify/functions/shared/lambda_utils/middleware.py       ← must stay cookie-unaware (§4.4)
amplify/functions/shared/lambda_utils/response.py         ← shared CORS. The session function
                                                           CANNOT write its own CORS headers:
                                                           gateway CORS overrides integration
                                                           headers (§4.6). It builds responses
                                                           through cors_response and AUGMENTS the
                                                           returned dict with a top-level
                                                           `cookies` list in its own _denied()
                                                           helper — no edit here
amplify/functions/shared/lambda_utils/rate_limit.py       ← fleet-wide fail-open primitive
amplify/functions/shared/lambda_utils/identity/customer.py ← normalize_phone must not change (§9.2)
src/pages/_app.tsx                                        ← see below
src/pages/404.tsx   _routes.json   src/components/HeaderCart.tsx
src/lib/cart.ts                                           ← cart stays credential-free (§4.5)
config/lambda-env-manifest.json                           ← records LIVE env; nothing is deployed
.kiro/specs/whatsapp-wix-commerce/**
docs/execution/checkout-c1-c7-closure-matrix-20261001.md
docs/execution/change-authority-matrix.md                 ← append-only; coordinate, never rewrite
package.json  package-lock.json  vendor/                  ← foreign (Material ESM work)
```

**`_app.tsx` is the binding constraint on the UI.** Its `isPublic` chain is an exact-match allowlist,
so a new page route renders an empty body with HTTP 200 unless it is added there — and that file is
outside owned paths. Therefore **this design adds no new page route.** `/account/sign-in` is already
listed; everything customer-session-facing goes there, into `src/lib/`, or into
`src/components/PhoneField.tsx`. Account-management surfaces (session list, sign out everywhere,
profile page) are deferred to §13 for exactly this reason, not because they are unimportant.

`config/lambda-env-manifest.json` records the **live** environment of deployed functions and is
updated at deploy time. Since this design deploys nothing, leaving it untouched is correct and
conveniently keeps the change set inside owned paths. The new function's expected env lives in
`provision_customer_session.py::expected_environment()`, exactly as
`provision_customer_registration.py` already does.

---

## 12. Rollout order, and why it is reversible at every step

Nothing below is executed by this design. It is the order the implementation and deployment steps must
follow, and it exists because the one unverifiable assumption (P1) has to be proven before anything
depends on it.

| # | Step | Reversible by |
|---|---|---|
| **0** | **Read** `UserPool.SchemaAttributes` for `custom:customer_id` (C-1). If absent, take the owner decision in §7.1 **before** step 2, because §8.8's new-customer branch depends on it. Returning-customer sign-in does not | a read; nothing to reverse |
| 1 | Land all code, all tests, IaC and the provisioning script. Deploy nothing | it is source only |
| 2 | `provision_customer_session.py --dry-run`, then run it: KMS key, **both** tables, role + the §11.1.1 policy, function, `live` alias, routes. Also **read** `lambda get-policy --function-name wecare-whatsapp-business-api --qualifier live` and record whether any statement restricts invocation in a way that excludes the new role (expected: none; §11.1.1) | the script's `--verify`; routes and function are additive and deletable |
| 3 | `--verify` and `--verify-cookie-transport`. **P1 GATE**, now including part (c): at least one of `Sec-Fetch-Site` and `Origin` must arrive on a same-origin `POST` (§2). Set `CSRF_FETCH_METADATA_MODE` from the result. Also record the signed-in vs anonymous `x-cache` comparison (§4.6) | read-only |
| 4 | **If P1 fails: stop.** Report the `api.wecare.digital` contingency (§13 C-3). Do not proceed | nothing shipped |
| **4a** | **C-12 GATE — four simulations, all reads.** Confirm `wecare-digital-lambda-role` and `wecare-checkout-role` are **allowed** `dynamodb:GetItem` and `dynamodb:UpdateItem` on `CustomerSessionIndexTable`, and still **denied** `GetItem` on `CustomerSessionsTable` and `kms:Decrypt` on the CMK. **If the positives are absent, do NOT run step 5.** The gate must distinguish three outcomes: *allowed* (proceed), *denied* (C-12 not granted — stop), and **`NoSuchEntity`** (the role does not exist; M16 says `wecare-checkout` is not deployed, so for that role only this is a **PASS-WITH-NOTE** recorded in the evidence doc, and C-12 must be re-gated when the function is provisioned — `provision_checkout.py:49` already names the role). For `wecare-digital-lambda-role`, which certainly exists, `NoSuchEntity` is a **FAIL** | a read; nothing to reverse |
| 5 | Deploy the `customer_auth` cookie branch to the customer endpoints that need it, Bearer still primary | `update-function-code` + `snapstart_publish.py` back to the prior version; the branch is additive and dormant without a cookie |
| 6 | Ship the frontend with `NEXT_PUBLIC_CUSTOMER_SESSION_COOKIE` **off**. **Nothing changes for shoppers — unconditionally**, because `customerSession.ts` cannot throw at module load (§2, finding 10) | the flag |
| 7 | Turn the flag on. `sessionStorage` writing stops; the cookie becomes the credential | turn the flag off — step 5's Bearer branch is still live, so the old path still works |
| 8 | After a clean window, `--retire-echo` and delete the dead `customerAuth` storage functions | separate commit |

Every deployed function behind the `live` alias needs `update-function-code` → publish → move the
alias, or the API keeps serving old code. `scripts/deploy_all_lambdas.py` calls `snapstart_publish.py`
itself; a hand deploy must run it. The rollback version is captured before each move.

`provision_customer_session.py --verify` asserts, with no secret value read:

- **both** tables exist; `CustomerSessionsTable` has `customerId-index` and TTL on `expiresAt` and SSE
  with the customer-managed key; `CustomerSessionIndexTable` has TTL on `expiresAt` and SSE with the
  AWS-owned key (a CMK here would be the wrong answer — §4.2);
- **every `(action, resource)` pair in `REQUIRED_PERMISSIONS`** passes `iam simulate-principal-policy`,
  failing on any `implicitDeny` — the method that found M10, now driven from the reachable-pair list
  rather than from the written statements (§11.1.1) — *and* the four negatives/positives of step 4a pass.
  `kms:GenerateDataKey` is checked explicitly, because without it every read works and every write fails;
  `dynamodb:PutItem` on `DownloadGrantsTable`, `lambda:InvokeFunction` on the sender alias and
  `ses:SendEmail` on both SES resources are checked explicitly, because they are the three pass-2 omissions;
- the live `RefreshTokenRotation` state on client `4avmt9n4gpmkvkdk88qbtit33o` matches
  `expected_environment()["COGNITO_REFRESH_ROTATION"]`, and **fails** if not (§6.2) — a read, projected so
  `ClientSecret` is never fetched into a variable;
- `CSRF_FETCH_METADATA_MODE` matches what `--verify-cookie-transport` observed (§4.6);
- the pepper secret has a current version (`describe-secret`, **metadata only**);
- the eight routes exist and the Lambda permission covers them (the 500-with-no-log failure mode
  `provision_agent_approval_routes.py` documents);
- an unauthenticated probe of `GET /api/customer/session` returns **401** — that is the pass. `404`
  means no route, `500` means a missing permission, and `200` means the gate is broken;
- that same response carries **no** `Access-Control-Allow-Credentials` header (§4.6).

---

## 13. Reported, not performed

| Id | Item | Why it is not done here | Exact unblock |
|---|---|---|---|
| **C-1** | `custom:customer_id` pool schema attribute (R6) | pool mutation is out of scope; Cognito cannot add a custom attribute after creation, so if it is absent the answer is an architecture change, not a command | read `SchemaAttributes`, then an owner decision. §8.1 already makes `CustomersTable` the authority, so this blocks `customer-registration` deployment only |
| **C-2** | `dynamodb:PutItem` on `wecare-otp-probe-counter` | the §8.6 code fix removes the need; an unneeded permission should not be granted | if ever needed: that one action, that one table ARN, that dedicated role. No wildcard, not the shared fleet role |
| **C-3** | `api.wecare.digital` same-site custom domain | needs a Route 53 record, and **DNS changes are prohibited** for this run. Only relevant if P1 fails | owner approval + ACM cert + API Gateway custom domain + one DNS record. Would also need gateway CORS `AllowCredentials: true`, which widens 359+ routes and needs its own review |
| **C-4** | `wecare/otp/pepper` secret creation (P2) | `provision_email_verification.py` owns it; this design must not create or read a secret | run that script's provisioning path. Metadata-only verification is already wired into `--verify` |
| **C-5** | `stack-wecare-digital-CustomersTable` (M12: absent) | no script in the repo creates it; `provision_customer_registration.py` and `provision_email_verification.py` both only reference it | a `provision_customers_table.py` following `provision_payment_attempts_table.py`'s shape, with `normalizedPhone-index`. Needed before §8.1 can run live |
| **C-6** | Account-management UI: session list, "sign out everywhere", profile page | each needs a new page route, and `_app.tsx`'s `isPublic` allowlist is outside owned paths (§11.3) | one additive line per route in `_app.tsx`, by the session that owns that file |
| **C-7** | `Use a WhatsApp number.` wired to real evidence | needs Meta's recipient-not-found code classified and surfaced; the mapping is unverified against a live Graph response and this design will not guess it | classify in `lambda_utils/graph_errors.py` against a captured live error, return `{"status":"unsupported_destination"}`, then flip T-16 |
| **C-8** | Capacitor / WebView customer app | `webDir: 'out'` bundles the export locally, so a native shell's origin is `capacitor://localhost` and the cookie would be third-party. Native packaging is POST-PROJECT | either `server.url = 'https://wecare.digital'` so the WebView is same-origin, or a separate bearer path for the native shell. A decision for the native project, not this one |
| **C-9** | Revocation latency ≤ 60 minutes (§7.2) | a deliberate trade, not a defect | if it ever needs to be zero: a `revokedAt` fan-out on the `customerId-index` driven by a Cognito post-authentication or admin-disable hook |
| **C-10** | Per-IP throttling is coarse behind CloudFront (§8.7) | trusting `X-Forwarded-For` would be worse, and there is **no WAF** to normalise it | CloudFront-added `CloudFront-Viewer-Address` would be trustworthy, but the Amplify-managed distribution's origin-request policy is not ours to set. Revisit only with C-3 |
| **C-11** | **`remember` default.** §5.4 now defaults it **off**; turning it on by default means a 29-day persistent credential on a phone-keyed account with `MfaConfiguration: OFF` and `DeviceConfiguration: null` (M7), in a market with shared handsets | it is an owner decision with a visible shopper-facing consequence, and the baseline's open question records it as such. A conversion argument is not sufficient authority to default it on | an explicit owner decision, **required before §12 step 7** (the step that makes the cookie the credential). Flipping it is a one-line change to the checkbox default plus the T-01 assertion. Defaulting off is still better than today's `sessionStorage`, so there is no pressure to decide early |
| **C-12** | One additive IAM statement each on `wecare-digital-lambda-role` (M15) and `wecare-checkout-role` (M16): `dynamodb:GetItem` + `UpdateItem` on `CustomerSessionIndexTable` only | an IAM change on a **shared** role, so it needs its own authorisation even though it is additive and narrow. The design deliberately made this the grant that leaks nothing (§4.2) rather than one that would | the two actions, that one table ARN, no CMK grant, no `CustomerSessionsTable` grant. **GATED at §12 step 4a** (finding 6): without the positives granted, step 7 makes **every** signed-in cart and checkout request a `503` with no sign-in path out, and the rollback is a flag rather than anything quick — so the gate blocks step 5, not step 7. `wecare-checkout-role` **may not exist yet** (M16), so the gate distinguishes *denied* from `NoSuchEntity` and treats only the latter, and only for that role, as pass-with-note. `--verify`'s negative simulations are what prove the boundary held |

## 14. Test matrix

Unit unless marked. **Integration** here means "drives the real handler against a fake table and a
fake Cognito client", not "calls AWS" — nothing in this suite makes a network call, which is what lets
it run on the exact tree. **Live** means it can only run after deployment and is therefore a
`--verify` mode on the provisioning script, not a pytest case.

**Every test names its owning file.** Pass 1 left six unassigned (review finding 11); the column is now
mandatory and §11.1 creates the three files that were missing.

| Id | Requirement | Component under test | File | Kind | Asserts |
|---|---|---|---|---|---|
| T-01 | cookie attributes + the `remember` default | `customer_session.cookie_header`; the sign-in checkbox | `test_customer_session_cookie_contract.py`; `AccountSignIn.test.tsx` | unit | `__Host-` prefix, `Path=/`, `Secure`, `HttpOnly`, `SameSite=Lax`, **no `Domain`**; `Max-Age` present iff `remember`; **and the checkbox defaults to unchecked** (§5.4, C-11) so the default cannot drift |
| T-02 | opaque id, hashed at rest | `customer_session.create` | `test_customer_session_cookie_contract.py` | unit | id is 43 chars of `[A-Za-z0-9_-]`; both table keys are `sha256(id)`; the raw id appears in **no** stored attribute in **either** table |
| T-03 | send-counter rollover (§8.6) | `customer-whatsapp-auth._consume_send_budget` + `otp_throttle._consume` | `test_customer_whatsapp_auth.py` (existing) | unit | a rolled window succeeds with **`update_item` only, never `put_item`**; a lost conditional race is treated as rolled; a genuine `ProvisionedThroughputExceededException` still raises (fail-closed preserved) |
| T-04 | CSRF on every mutation, **including the two unedited handlers**, in **both** Gate 2 configurations | `customer_session.require_session`; `customer_auth.require_customer`; `ecommerce/checkout` and `wix-store._customer_cart` driven end to end | `test_customer_session_csrf.py` | unit + integration | a table-driven sweep of all eight session routes: every mutating one refuses without `X-WD-CSRF`; `GET`/`OPTIONS` exempt. **Then the whole sweep runs twice, once per `CSRF_FETCH_METADATA_MODE`** (§4.6, finding 8): in `full`, `Sec-Fetch-Site: cross-site` is refused and an absent `Origin` is accepted; in `origin_only`, an **absent** `Origin` is refused, a foreign `Origin` is refused, and an absent `Sec-Fetch-Site` is accepted. **Then both DO-NOT-TOUCH handlers are driven with a valid cookie, a mutating method and no `X-WD-CSRF` and must answer 403** (§4.6, pass-2 finding 1). A CSRF failure is 403, carries **no `cookies` key**, and does not clear the session |
| T-05 | idle + absolute enforced server-side; clear-cookie actually clears | `customer_session.resolve`, `_denied` | `test_customer_session_lifetimes.py` | unit | a cookie replayed past `idleExpiresAt` and past `absoluteExpiresAt` is refused even with a browser-valid cookie; **every clear path returns a response whose `cookies[0]` is the `Max-Age=0 __Host-wd_cs` header** (§4.6, finding 7) |
| T-06 | **a refresh never extends the absolute deadline** | `customer_session.refresh` | `test_customer_session_lifetimes.py` | unit | 40 refreshes across 29 simulated days leave `absoluteExpiresAt` byte-identical **in both tables**; refresh 41 past the deadline is refused by the condition |
| T-07 | an outage is not a logout | `customer_session._is_terminal` + `refresh` | `test_customer_session_refresh.py` | unit | 14 failure shapes; **exactly 4** are terminal; the other 10 return 503 with the session intact and the cookie untouched; an unknown exception type defaults to non-terminal |
| T-08 | single flight | `customer_session.refresh` | `test_customer_session_refresh.py` | integration | two concurrent refreshes against one fake table produce **one** provider call; the loser observes the advanced `refreshGeneration`; an expired lease is retakeable |
| T-09 | rotation readiness **and rotation-config drift** | `customer_session._refresh`, `_rotation_enabled` | `test_customer_session_refresh.py` | unit | with `rotation_enabled=False` the **primary** call is `REFRESH_TOKEN_AUTH`; with `True` it is `GetTokensFromRefreshToken`; the 60s previous-token grace is honoured once. **Then both drift directions** (§6.2, finding 9): `rotation_enabled=False` + `NotAuthorizedException` → one `GetTokensFromRefreshToken` fallback → **request served**, `refresh_rotation_drift` logged, `revokedAt` **not** written; `rotation_enabled=True` + rejection → one `REFRESH_TOKEN_AUTH` fallback, same outcome; **a second failure is terminal**; and the fallback is attempted **exactly once**, never retried. Plus: a `DescribeUserPoolClient` failure falls back to the env value and does not fail the request |
| T-10 | the browser stores nothing, **cannot be relocated cross-origin, and cannot take sign-in down** | `src/lib/customerSession.ts`; `check_same_origin_api_base.py` | `CustomerSessionClient.test.ts` | unit (vitest) | a full sign-in → refresh → sign-out cycle against a mocked `fetch` leaves `localStorage` and `sessionStorage` **empty**; no `document.cookie` write anywhere in the module. Then the three-way §2 invariant (finding 10): **importing the module with a cross-origin `NEXT_PUBLIC_API_BASE` must RESOLVE, not throw**; first use then returns `{ok:false, code:'ORIGIN_MISCONFIGURED'}`, logs **once**, attempts **no** `fetch`; and the build-time checker **fails** on the same value — so the suite pins that the loud failure is at build and the quiet one is at runtime, not the other way round |
| T-11 | no Cognito token or phone ever leaves the server | the session handler | `test_customer_session_cookie_contract.py` | integration | every response body of all eight routes is walked recursively; no value matches a JWT shape (`^eyJ`); the keys `accessToken`, `idToken`, `refreshToken`, `Session` are absent; **and `normalizedPhone` never appears in any body — only a masked `displayPhone`** (§4.2, finding 2) |
| T-12 | staff app isolation | `middleware.py`; `customer_session.resolve` | `test_customer_session_cookie_contract.py` | unit, **AST** | the AST of `require_auth` and its module contains **no** read of `cookies`, `Cookie` or `__Host-`; and a session row carrying the staff pool id is refused by `resolve` |
| T-13 | cart vs credential separation | `src/lib/customerSession.ts`, `src/lib/cart.ts` | `CustomerSessionClient.test.ts` | unit (vitest), static | neither module imports the other; the session record builder emits no cart key; sign-out leaves `wecare.cart.v1` **present** |
| T-14 | OTP only when §6.4 says | `src/lib/customerSession.ts` | `CustomerSessionReauth.test.ts` | unit (vitest) | every status the API can return (200, 400, 401×3 codes, 403, 409, 429, 500, 502, 503, network error) is enumerated; **only** `401 SESSION_EXPIRED` and `401 VERIFICATION_REQUIRED` route to sign-in |
| T-15 | divided phone field preserved | `PhoneField.tsx` | **`src/test/PhoneField.test.tsx`** (new — none existed) | unit (vitest) | two focusable segments inside one container; per-segment `outline-offset:-3px`; `border-inline-end` divider; `aria-label="Country code"`; `DEFAULT_DIAL_CODE` visible on first paint; **no red token and no combined single input**; no locale-inferring selector; the new `autoComplete="tel-country-code"` present; **and `required` present on the number `<input>` and ABSENT on the code `<select>`** (M23, finding 13) — asserted in both directions so neither is "tidied" later |
| T-16 | copy contract | `sign-in.tsx` | `AccountSignIn.test.tsx` (existing) | unit (vitest) | the seven live `MSG` strings byte-exact including `\u2019`; the hint string byte-exact; **no code path renders `NOT_ON_WHATSAPP`** |
| T-17 | **one phone, one customer id** | `identity/phone_ownership.reserve_phone` | `test_phone_ownership_reservation.py` | integration | two concurrent reservations for one normalised phone: exactly one creates, the other **adopts**; one `customerId` results. Includes the crash-between-steps case and asserts self-healing |
| T-18 | one verified email per customer; **the separator invariant holds** | `identity/phone_ownership.reserve_email`; `otp_challenge.challenge_key` | `test_phone_ownership_reservation.py` | integration + unit | a second customer claiming a verified address gets the **opaque** `INVALID_OR_EXPIRED`, never "belongs to someone else"; **and two `(customer_id, email)` pairs whose naive `\x1f` concatenation would coincide produce different keys AND different code digests** (§8.3, finding 9) |
| T-19 | explicit country code required | `identity/phone_input.require_explicit_e164` | `test_phone_input_explicit_code.py` | unit | `+919876543210` and `00919876543210` accepted; bare `9876543210` **refused**; `identity.customer.normalize_phone` is unmodified (asserted by calling it directly and checking the ten-digit inference still fires) |
| T-20 | no body-selected customer id; `subject` authorises nothing; **the returned type IS-A `CustomerIdentity`** | the session handler + `email-verification`; `customer_auth`; `customer_session.CustomerSession` | **`test_customer_session_identity.py`** (new) | integration | a `customerId` in any body is `400 UNEXPECTED_FIELD`; the stamp uses the session's id; the old unauthenticated stamp path **no longer exists**; **and no authorisation decision reads `identity.subject`**, which is `""` on the cookie branch (§4.2). Plus `assert isinstance(identity, customer_auth.CustomerIdentity)` on what both `resolve` and `require_session` return, and that the session-only fields are readable — which is only true because `CustomerSession` declares its own `__slots__` (M23, finding 7) |
| T-21 | id rotation | `customer_session.rotate` | **`test_customer_session_identity.py`** | unit | sign-in, phone change, email change and step-up each produce a new id **and** a new CSRF token, and delete the old rows **in both tables** in the same request; an ordinary refresh does **not** rotate |
| T-22 | step-up window, **and the tokenless upgrade** | `require_session(sensitive=True)` | **`test_customer_session_identity.py`** | integration | on a `cognito` session: within 600s of `lastVerifiedAt` it passes; outside it returns `401 REAUTH_REQUIRED`; an ordinary checkout-shaped call with `sensitive=False` **never** demands reauth. **On a `phone_ownership` session it returns `401 REAUTH_REQUIRED` even INSIDE the 600s window**, and completing the Cognito OTP rotates to a row with `tokenSource="cognito"`, tokens stored, and the live `GetUser` then performed (§8.5, finding 1) |
| T-23 | enumeration resistance | `/customer/session/challenge` | **`test_customer_session_identity.py`** | integration | a registered and an unregistered number produce identical status, identical body keys and identical body values except `expiresInSeconds`; the `registered` flag is absent from every response; the `AdminGetUser` result is not observable from any field or status |
| T-24 | nothing sensitive is logged | all new/changed Python | **`tests/test_no_sensitive_logging.py`** (new) | unit, **AST** | every `logger.*` / `print` call in §11.2's changed-file list is parsed; the argument expression may not reference a name in `{code, otp, token, accessToken, refreshToken, pepper, phone, email, session_id, csrf}`, **including inside a ternary or a boolean coercion** — the lesson from the two CodeQL failures |
| T-25 | existing gates stay green | the repository | the named files | regression | `tests/test_customer_auth_and_throttle.py`, `test_otp_throttle.py`, `test_otp_challenge.py`, `test_customer_whatsapp_auth.py`, `test_customer_registration_handler.py`, `test_customer_identity.py`, `test_cart_v2.py`, `test_checkout_handler.py`, `test_route_auth_enforcement.py`, `test_payment_vocabulary_at_decision_points.py`, plus `npx tsc --noEmit`, `npx vitest --run`, `npm run build`. **`test_otp_challenge.py` must pass unedited** — if the `*extra` change needs it modified, the change was not additive |
| T-26 | P1 cookie transport | the Amplify rewrite | `--verify-cookie-transport` | **live** | a `Set-Cookie` emitted by the Lambda reaches the client with attributes intact; the returned `Cookie` reaches the Lambda; signed-in vs anonymous `x-cache` recorded. **No cookie value printed** |
| T-27 | route + permission wiring, the CORS mechanism, **and the full permission matrix** | `zllr9lrg7j`; the three IAM roles; the app client | `--verify` | **live** | the routes exist; the alias permission covers them; an unauthenticated `GET /api/customer/session` returns **401** (404 ⇒ no route, 500 ⇒ missing permission, 200 ⇒ the gate is broken); **the response carries no `Access-Control-Allow-Credentials`** (§4.6, pass-2 finding 5); **every `(action, resource)` pair in `REQUIRED_PERMISSIONS` simulates `allowed`** — not merely every written statement (finding 2) — and the four step-4a verdicts hold; `RefreshTokenRotation` matches the env (finding 9); `CSRF_FETCH_METADATA_MODE` matches the measurement (finding 8) |
| T-28 | the resolution table holds no credential, **and the idle clock has one owner** | the two-table writer | `test_customer_session_cookie_contract.py` | unit | the attribute-name set the writer may emit for `CustomerSessionIndexTable` is enumerated and **excludes** `refreshTokenEnc`, `accessTokenEnc`, `cognitoSub` and `cognitoAuthSession` (`tokenSource` **is** permitted and is not a credential); a create/rotate/revoke writes **both** tables in one `TransactWriteItems`. **Then divergence is asserted in both directions** (§4.2, finding 5): a **table-2-only idle advance is LEGAL** and must not be flagged, while a table-2-only change to `customerId`, `normalizedPhone`, `poolId`, `absoluteExpiresAt`, `revokedAt`, `csrfTokenHash` or `tokenSource` **is** divergence; and every expiry verdict in the module reads `idleExpiresAt` from table 2, asserted by driving a resolve with the two copies deliberately disagreeing and checking which one decided |
| T-29 | **nothing is created before the code verifies, and no second provider call is made** | `/customer/session` new-number branch | **`test_customer_session_identity.py`** | integration | `/challenge` for an unknown number followed by a **failing** `/session` leaves the reservation table, `CustomersTable` and the Cognito fake with **zero** writes; only a passing code reaches `reserve_phone` → customer row → `AdminCreateUser`, in that order (§8.8, pass-2 finding 4). **Extended in pass 3:** on the passing path the Cognito fake records `AdminCreateUser` + `AdminSetUserPassword` and **no** `InitiateAuth`, **no** `RespondToAuthChallenge`, **no** `AdminInitiateAuth`, and **no second WhatsApp send**; the created row has `tokenSource="phone_ownership"` with `refreshTokenEnc`/`accessTokenEnc` **absent**; and the string `SUPPRESS_SEND` appears nowhere in `amplify/` (a text assertion, since the point is that the flag does not exist) |
| **T-30** | **the shared cookie branch never refreshes** | `customer_auth.require_customer` → `require_session(can_refresh=False)` driven inside `ecommerce/checkout` and `wix-store` | `test_customer_session_csrf.py` | integration | with `accessTokenExpiresAt` in the **past** and a valid cookie, both handlers answer **200**, not 503; the table-1 fake records **zero** reads; no `kms:Decrypt` is attempted; no provider call is made. Then the same request against the session function with `can_refresh=True` **does** refresh (§3, §4.2, finding 4) |
| **T-31** | **a tokenless session is legal, inert and bounded** | `customer_session.refresh`, `require_session`, `revoke` | `test_customer_session_refresh.py` | unit + integration | a `tokenSource="phone_ownership"` row survives 40 simulated requests across 29 days with **zero** provider calls, is never marked `revokedAt` by a refresh path, and is expired **only** by the §5.3 clocks; a sensitive step on it is `401 REAUTH_REQUIRED` even inside the 600s window; sign-out attempts **no** `RevokeToken` and still deletes both rows (§8.8.0, finding 1) |

T-25's baseline matters: the baseline recorded 20 failing tests in the working tree, **all inside the
foreign payment work**. The gate for this task is the focused subset above plus "the foreign failure
count did not grow", measured before and after. A green claim that does not separate our failures from
theirs is worthless.

Interpreter for every pytest invocation: `/Users/wecaredigital/wecare-store/.venv/bin/python`. Bare
`python3` has no `boto3` and `conftest.py` refuses anything below 3.12.

---

## 15. Hard constraints this design obeys, restated as rules the implementation must keep

1. **No credential value on a command line, in argv, in an environment assignment, in a log line, or
   in any logging expression** — not reduced to a boolean, not inside a ternary. CodeQL's
   `py/clear-text-logging-sensitive-data` tracks taint across function boundaries and has already
   failed this build twice on exactly that pattern. T-24 enforces it in-repo so CodeQL is the second
   line, not the first. Do not suppress the alert; remove the log or derive the value from something
   that never touched the secret.
2. **Never call `secretsmanager get-secret-value` or `batch-get-secret-value`** from a shell, a script
   or an MCP tool. Secrets are referenced **by id** and read **lazily at request time inside the
   Lambda** (`wecare/otp/pepper`). A module-scope read would freeze the value into a warm sandbox and
   survive a rotation. Verification of the secret uses `describe-secret` metadata only.
3. **No token, session id, OTP or CSRF token in a URL, a query string, a fragment, a redirect target or
   a log.** The session id travels only in the `Cookie` header; the CSRF token only in a response body
   and the `X-WD-CSRF` request header; the Cognito `Session` never leaves the server (§10.1).
4. **No deployment.** No `update-function-code`, no `publish-version`, no alias move, no table create,
   no KMS key create, no route create. §12 is the order those steps must follow when they are
   separately authorised.
5. **No WAF**, in either scope, and its absence is not reported as a gap to close. **Security Hub stays
   excluded.** §8.7's IP reasoning is written for a world with no WAF because that is the world.
6. **No MX, MTA-STS or DNS change.** This is why C-3 is reported rather than built.
7. **No pool or app-client mutation.** No `update-user-pool`, no `update-user-pool-client`, in any
   spelling. M7 proves none is needed. If one is ever authorised it goes through
   `scripts/cognito_pool_safe_update.py` and updates IaC in the same change, because `UpdateUserPool`
   is a full replace that has already wiped these three triggers once.
8. **No live send.** No OTP to a real handset. `+918100640044` is nominated but a message test needs
   its own authorised scope, and `WA_LIVE_SMOKE_TEST` is a lockdown, not a permission. Every test in
   §14 uses fixtures.
9. **No payment capture, refund or payment-configuration mutation**, and `captured` never appears as a
   raw string literal at a decision point — payment state is read through
   `lambda_utils/payment_status.py`, which this design does not touch.
10. **Foreign work is preserved.** `git status --short` is re-read immediately before any stage; new
    files are `git add`ed by name and then
    `git commit --only <all our paths> -F <message-file>`, because the index is shared and `--only` is
    the only thing that bounds a commit regardless of what another session staged. Never `git add .`,
    `-A`, `-u`, never a bare `git stash`, never a reset, rebase, force push or history rewrite. Branch
    `stack`, single branch.
11. **One evidence doc**, `docs/execution/customer-session-closure-20261001.md`. Append to
    `docs/execution/change-authority-matrix.md` only; never rewrite it.

---

## 16. Assumptions, stated so the review can attack them

1. **P1 holds** — the Amplify rewrite is cookie-transparent. Measured as far as is possible without a
   deploy (M2, M3 prove request- and response-header transparency for `Authorization` and
   `apigw-requestid`), **unproven for `Cookie`/`Set-Cookie`**, gated in §12 step 3 before anything
   depends on it. This is the largest open risk in the design and it is deliberately placed where a
   failure costs nothing shipped.
2. **The same-origin premise is the rewrite AND a same-origin `NEXT_PUBLIC_API_BASE`** — not the
   rewrite alone. Restated in this revision (review finding 8). The `/api/<*>` rule is one of 146
   `customRules` on a shared Amplify app, and if it were removed every customer-facing call already
   breaks, so this design adds no new dependency there — it only raises the cost of removing it. The
   *second* half is the newly-named risk: `API_BASE` is `process.env.NEXT_PUBLIC_API_BASE || '…'`
   inlined at build time, so setting that variable to the `execute-api` host would silently make every
   cookie third-party. §2 makes the session client derive its base from `window.location.origin` and
   check the invariant at **build time (hard fail), test time, and lazily at first use (typed refusal,
   never a throw)** — corrected in pass 3, because pass 2's module-load throw would have taken sign-in
   down for a cookie feature that may be switched off. T-10 pins all three.
3. **Rotation stays off** until someone turns it on. The design is rotation-ready (T-09) and reads the
   state from env rather than from a per-request provider call, so enabling it is a config change plus
   a flag, not a rewrite.
4. **R6 is unresolved, and it is now blocking for one specific flow.** §8.1 makes `CustomersTable` the
   authority for `customerId`, so *authorisation* is independent of whether `custom:customer_id` can
   exist on the pool. *Provisioning* is not: §8.8 stamps the attribute on `AdminCreateUser`, so if the
   attribute cannot exist a **new** customer cannot be given a Cognito login. Returning-customer
   sign-in, refresh, CSRF, lifetimes and every §8 identity fix are unaffected. §12 step 0 reads
   `SchemaAttributes` before anything is provisioned, and C-1 carries the owner decision. If R6 is
   wrong and the attribute is present, nothing here changes.
5. **The sensitive-step set is exactly three operations** (§8.5). If the owner wants, say, address
   changes to be sensitive, that is a one-line change to a predicate — but it must be a decision, not
   a drift, because every addition is an extra OTP in a shopper's path.
6. **`remember` defaults to OFF** (changed in this revision, review finding 12). The 29-day persistent
   option is one visible checkbox away and changes nothing server-side (§5.4). Defaulting it **on** is
   an owner decision tracked as C-11 and required before §12 step 7, not an implementation default.
   Defaulting off is still better than today's `sessionStorage`, so nothing is under time pressure.
7. **29 days, not 30** (§5.1). If the owner reads "~30-day" as literal, the alternative is accepting a
   provider-timed logout on the final day. The margin is the better engineering answer and is stated as
   a decision rather than an approximation.
8. **The two-table split is the right cost** (§4.2, review finding 3). It buys a credential boundary that
   survives `wix-store` running on the shared fleet role (M15), and it costs a second DynamoDB table, a
   `TransactWriteItems` on every session write, and the inability to refresh from inside
   `checkout`/`wix-store`. The last of those is handled by §7.2's "authorise from the row", which was
   already the design's position. If a future reader prefers the single-table version, the thing to
   re-measure first is M15 — the answer changes only if those handlers move to dedicated roles.
9. **`identity.subject` is empty on the cookie branch.** Verified today: `customer_auth` reads it only in
   `__repr__`, and no module under `lambda_utils/ecommerce/` or `amplify/functions/ecommerce/` reads it
   at all. If something starts needing a real `sub`, the honest fix is a provider-side lookup in the
   session function, **not** copying `cognitoSub` into the resolution table.
10. **A tokenless first session is an acceptable trade** (§8.8.0, added in pass 3). The assumption being
   made is that "our own WhatsApp OTP, verified by `otp_challenge`" is identity proof of the same strength
   as "the same WhatsApp OTP, verified by Cognito's `CUSTOM_AUTH` trigger" — same code length, same
   channel, same handset, same pepper, same TTL, same attempt cap, same single-use condition. What is
   genuinely given up is **provider-side revocation for that one session**: disabling the Cognito user
   does not end it. The three bounds are stated in §7.2 (first session only; every later sign-in is
   `cognito`; a sensitive step upgrades it), our own `revokedAt` still ends it instantly, and both clocks
   still apply. The alternative — a plaintext-OTP escrow plus an attacker-writable `ClientMetadata` flag
   on the trigger wired to all three `CUSTOM_AUTH` hooks — is a worse trade, and §8.8.0 says why in full.
   If a future reader disagrees, the thing to change is **not** the escrow: it is to make the pool's
   `ADMIN_USER_PASSWORD_AUTH` flow available, which is an app-client mutation and therefore out of scope
   here.
11. **`Sec-Fetch-Site` may not survive the rewrite** (§2 P1 part (c), §4.6). Pass 2 assumed it would and
   never measured it. The degraded Origin-only mode is specified, tested and gated, so the assumption is
   no longer load-bearing — but which mode ships is **unknown until P1 runs**, and that is deliberately a
   measurement rather than a preference.







---

## 17. Responses to the PASS-2 design review (historical — kept for the audit trail)

Verdict under review: `CHANGES_REQUESTED`, 4 HIGH / 8 MEDIUM / 3 NIT, reviewed at `25eace2039…`.

> **SUPERSEDED IN PART by §18.** Row 4 below says the new-customer flow's Cognito completion "is
> server-to-server so the shopper still types one code". Pass 3's finding 1 proved that mechanism does
> not exist (M22), and §8.8.0 replaced it with a tokenless first session. The *property* row 4 claims —
> verify first, provision second, nothing created before the code verifies, one code for the human — is
> intact and is now simpler. Read row 4 for the ordering decision and §8.8.0 for how the session is
> actually minted.
>
> Row **10** is also superseded in part: it says `--verify` "simulates every statement **and** two
> negatives". Pass 3's finding 2 showed that contract cannot catch an **omitted** action, so §11.1.1 now
> simulates every reachable `(action, resource)` **pair** and asserts four verdicts, not two. Rows 3, 5
> and 8 are tightened by §18 findings 5, 8 and 10 respectively.

**Every finding is ADDRESSED. None is backlogged and none is declined.** Where the review offered a
choice of remedies, the one taken is named with its reason, and where a remedy had a cost that cost is
written into the design rather than absorbed quietly.

The review's own closing observation shaped the order of work: findings 1, 2 and 3 are one root cause —
the integration seam with the two DO-NOT-TOUCH handlers was specified from this design's abstractions
instead of from those handlers' source — so 3 was resolved first and 1 and 2 fell out of the result.

| # | Sev | Finding | Resolution | Where |
|---|---|---|---|---|
| 1 | HIGH | cookie-authenticated mutations on `checkout`/`wix-store` had no CSRF gate | **Fixed as recommended.** `require_customer`'s cookie branch derives `mutating` from the HTTP method and applies the gate itself, so the two unedited handlers are covered without caller cooperation. An unreadable method is treated as mutating. T-04 now drives both handlers with a cookie and no `X-WD-CSRF` and asserts 403 | §4.6 opening, §11.2, T-04 |
| 2 | HIGH | `CustomerIdentity.phone` is the cart partition key and was absent from the session record | **Fixed as recommended**, and re-measured as M18. `normalizedPhone` is on both tables; `resolve` returns a real `CustomerIdentity`; it is **never** in a response body (T-11). The pass-1 "no edit" claim is replaced by an explicit table of what the unedited handlers nonetheless inherit | §4.2, §3, §11.2, T-11 |
| 3 | HIGH | the cookie branch needed `GetItem` + `kms:Decrypt` from roles that must never have it | **Fixed with remedy (a), the custody split**, and the choice is now forced rather than preferred: M15 measured `wecare-wix-store` running on the **shared fleet role**, so the alternative was never "a wider grant", it was "all 65 functions can read every refresh token". Credential custody and resolution are two tables, written in one `TransactWriteItems`. Remedies (b) internal invoke and (c) envelope encryption are rejected on the record with reasons. The stated consequence — no inline refresh inside `checkout`/`wix-store`, proceed on the row's authority per §7.2 — is written down, as the review asked | §4.2, §3, §11.1.1, §13 C-12, T-28 |
| 4 | HIGH | the unregistered-number path was specified two ways and its dependencies called non-blocking | **Fixed with remedy (a), verify-first-provision-second.** New §8.8 specifies it step by step: `AdminGetUser` decides the branch and creates nothing; an unknown number gets our own `customer_phone_ownership` code; the `PHONE#` reservation, the customer row and `AdminCreateUser` are reachable **only after** that code verifies; the Cognito completion is server-to-server so the shopper still types one code. C-1 promoted to blocking for new-customer sign-in with §12 step 0 reading `SchemaAttributes` first. The four Cognito admin actions are enumerated. `customer-registration` is explicitly off the sign-in path and pinned rather than orphaned. Remedy (b) provision-first is declined for the reason the review gave: no WAF, coarse IP axis | §8.8, §8.8.1, §7.1 C-1, §9.3, §12, T-29 |
| 5 | MED | the §4.6 cross-origin mechanism was wrong | **Fixed as recommended.** `AllowCredentials: false` is named as the mechanism; gateway CORS overriding integration headers is recorded as a second reason not to flip it; the claim that the function emits no ACAO or sets `Vary: Origin` is removed. `--verify` asserts no `Access-Control-Allow-Credentials` on the live response | §4.6, T-27 |
| 6 | MED | `GET` declared side-effect-free then specified to write | **Fixed as recommended**, keeping the behaviour and dropping the false claim, with the `Lax` top-level-navigation consequence and the `absoluteExpiresAt` bound stated | §4.6 |
| 7 | MED | clearing the cookie from a 401 raised inside an unedited handler was impossible via `cors_response` | **Fixed as recommended.** A `_denied()` helper in `customer_session.py` augments the `cors_response` dict with a top-level `cookies` list; no `response.py` edit. `clear` is `False` for CSRF and reauth, `True` for terminal rejections. T-05 asserts the clear header; T-04 asserts a CSRF failure emits no `cookies` key | §4.6, §11.3, T-04, T-05 |
| 8 | MED | the same-origin premise rested on a build-time env var | **Fixed with all three recommended parts.** The session client derives from `window.location.origin + '/api'` **and** asserts `API_BASE` is same-origin at module load; T-10 fails on a cross-origin value; assumption 2 is restated as the rewrite **and** a same-origin env var. The pass-1 word "hardcodes" is corrected to what the file actually says | §2, §11.1, §16.2, T-10 |
| 9 | MED | the email subject violated `_digest`'s separator invariant | **Fixed as recommended**, with one addition the review's snippet did not cover: M17 shows `_digest` is called for the **code** digest as well, so `*extra` must thread into both or the key is found and the code never matches. T-18 gains the collision case | §8.3, M17, T-18 |
| 10 | MED | the new role's IAM was never enumerated | **Fixed as recommended.** §11.1.1 is a statement-by-statement table with no wildcards, including `kms:GenerateDataKey` (a write to a CMK table needs it) and the Cognito admin actions from finding 4, plus an explicit absent-and-why list. `--verify` simulates every statement **and** two negatives — the fleet role must be denied the credential table and the CMK | §11.1.1, §12, T-27 |
| 11 | MED | six tests had no owning file | **Fixed as recommended.** `src/test/PhoneField.test.tsx`, `tests/test_customer_session_identity.py` and `tests/test_no_sensitive_logging.py` are created; §14 now carries a mandatory File column and every test names one. Two tests were added beyond the review's list (T-28, T-29) for findings 3 and 4 | §11.1, §14 |
| 12 | MED | `remember` defaulted on, presented as a default rather than an owner decision | **Fixed by taking the first option: the default is now OFF**, with C-11 recording the owner decision needed to turn it on and T-01 asserting the default so it cannot drift. The deciding argument is that `remember: false` is a browser-session cookie, which already outlives today's per-tab `sessionStorage` — so the conservative default is not a regression and nothing is under pressure to decide early | §5.4, §13 C-11, §16.6, T-01 |
| 13 | NIT | the `__Host-`/`Path=/api` cache fallback changes the threat model | **Fixed as recommended.** The fallback now states that it reverts host-only from a browser rule to a server promise, reinstating the subdomain-shadowing exposure, and must be paired with a Route 53 **read** confirming no retired hostname has a dangling record | §4.6 |
| 14 | NIT | `normaliseMobile`'s inference left in the client while the server forbids it | **Fixed as recommended**, with the exact docblock text quoted so it cannot be paraphrased into something weaker | §9.2, §11.2 |
| 15 | NIT | the probe counter has no window rollover at all | **Fixed by naming it**, which the review said was sufficient: `otpprobe#` is deliberately TTL-only and **fails open**, so a lagged window weakens the enumeration budget rather than causing an outage, and it is out of scope for this change | §8.6 |

### Where the review's "Unverified / Wrong Assumptions" table now stands

U1, U2, U3, U4, U5, U6, U7, U8, U9, U10 are all corrected in the text above. U11 (the M1–M14 AWS reads
were not re-verified by the review) and U13 (R2/R3/R9/R11/R12 were deliberately not re-measured) remain
**open and unchanged**, and this revision does not pretend otherwise: M15–M18 add four new reads, R6 is
promoted to a gated read at §12 step 0, and everything else still rests on the pass-1 measurement with
its date attached. U12 (P1, the cookie-transport assumption) is still unproven, still correctly labelled,
and still gated at §12 step 3 before anything depends on it — which is the posture the review endorsed.

### What the pass-2 revision did NOT change, deliberately

The crux decision (§2, same-origin BFF) stands and the review did not contest it. No token goes near
`localStorage` or `sessionStorage`, and no fallback that would put one there is offered. The absolute
deadline is still pinned three ways. `_is_terminal`'s four-name allowlist still makes an outage
non-terminal by default. `X-Forwarded-For` is still untrusted. PR #175 is still extended additively with
no red states and no SMS fallback. No deploy, no pool mutation, no app-client mutation, no WAF, no
Security Hub, no DNS or MTA-STS change is proposed anywhere in this document, and §15 restates all of
those as rules the implementation must keep.

---

## 18. Responses to the pass-3 design review

Verdict under review: `CHANGES_REQUESTED`, pass 3, **3 HIGH / 7 MEDIUM / 3 NIT**.
**Every finding is ADDRESSED. None is backlogged and none is declined.** One finding (1) is resolved by
the review's remedy **(b)** rather than **(a)**, and the reasoning for choosing it — including why (a) is
not merely more expensive but structurally worse — is written into §8.8.0 rather than left in this table.

The review's diagnosis of where the problems were is worth repeating because it was accurate: all three
HIGHs were in **the new-customer branch of §8.8 and the IAM meant to carry it**, and two of them were the
M10 shape this document cites as its own cautionary tale — an enumerated, wildcard-free policy missing one
action a code path needs, in a verifier structurally unable to notice. That second part is why the fix is
not "add two rows": `--verify`'s contract changed.

| # | Sev | Finding | Resolution | Where |
|---|---|---|---|---|
| 1 | HIGH | §8.8 step 6b.iv's "server-held answer" is unimplementable, and the obvious implementation is an authentication bypass | **Fixed with remedy (b), and the attack surface is REDUCED rather than defended.** M22 confirms the answer lives only in `privateChallengeParameters`, reachable only by `VerifyAuthChallengeResponse`. A first session is now **tokenless** (`tokenSource="phone_ownership"`), minted from the `customer_phone_ownership` code our own `otp_challenge` verified, with **no Cognito authentication call at all**. The `SUPPRESS_SEND` client-metadata flag is **deleted**, not secured, because `ClientMetadata` on an unauthenticated `InitiateAuth` is attacker-writable and a trigger that honours any flag is a permanent invitation. Remedy (a) is rejected on the record for three reasons: it still needs that flag (a `CUSTOM_AUTH` trigger cannot tell the admin API from the public one), it creates a plaintext-OTP store in a codebase whose discipline is peppered digests, and it changes the handler wired to all three triggers. The cost — one new legal session state — is paid explicitly in six sections rather than left implicit, and §7.2 states the one real loss (no provider-side revocation for that one session) with its three bounds | **§8.8.0** (new), §8.8 step 6b, §4.2 `tokenSource`, §6.2, §7.2, §8.5, §5.5, §9.3, §8.8.1, §11.2 (withdrawal), §16.10, **T-29 extended, T-31 new** |
| 2 | HIGH | the session role is denied `dynamodb:PutItem` and `otp_challenge.issue` is a `put_item` | **Fixed as recommended, plus the structural half.** M19 confirms `otp_challenge.py:270`. `PutItem` on `DownloadGrantsTable` is added, and pass 2's justification — "the §8.6 fix removes the need" — is corrected rather than reworded: §8.6 removes a *send-counter rollover* `put_item` on a *different role*, which is why **C-2 is genuinely unaffected** and stays unexercised. The second half matters more: `--verify`'s contract is changed from "simulate every statement in the policy" to **"simulate every `(action, resource)` pair the handler can reach"**, with the pair list carried **in the provisioning script as data** (`REQUIRED_PERMISSIONS`) and used to generate *both* the policy and the simulation — so a new code path fails the verifier instead of production | §11.1.1 row 8 + the new `--verify` contract subsection, §12, §13 C-2, T-27 |
| 3 | HIGH | the enumerated policy omits both send paths the design specifies | **Fixed as recommended, keeping the sends in the session function.** M20 and M21 pin both paths. Added: `lambda:InvokeFunction` on `wecare-whatsapp-business-api:**live**` (qualified alias only, no other function) and `ses:SendEmail` on **two** resources — the identity `one@wecare.digital` and the configuration set `wecare-digital` — because SESv2 authorises a send naming a configuration set against both, which is flagged as the one two-resource statement so it does not read as drift. The absence sentence is rewritten to "`lambda:InvokeFunction` on anything **other than** the WhatsApp sender alias". The **alternative is declined** with its reason: moving the sends back into the undeployed handlers costs a hop and two deployments and contradicts §8.3's "the stamp moves to the session function". The sender's resource policy question is answered — a same-account invoke needs no statement there — and §12 step 2 records it as a `get-policy` **read** so it is evidenced rather than assumed | §11.1.1 (two new rows + absence rewrite), §12 step 2 |
| 4 | MED | the shared cookie branch is named as two different functions and one cannot run where it is called | **Fixed as recommended, exactly.** One entry point, `require_session(event, *, mutating, sensitive=False, can_refresh=False)`, with the docstring the review drafted. The shared branch passes `can_refresh=False`; the session handler passes `True`. §8.2's step 8 is annotated as conditional on **two** independent grounds (`can_refresh`, and `tokenSource`), and `resolve` is demoted to the module-internal read that nothing outside calls. **T-30 is new**: the shared branch with a past `accessTokenExpiresAt` must answer 200 with zero table-1 reads | §3 (diagram + snippet), §4.6 snippet, §8.2 step 8, §11.2, **T-30** |
| 5 | MED | the "two rows never diverge" invariant is contradicted by the only write the foreign roles have | **Fixed as recommended, with the exemption named and owned.** `idleExpiresAt` and `lastSeenAt` are **owned by table 2** and are the two attributes exempt from the co-write invariant; **every** expiry verdict reads the idle clock from table 2; table 1's copy is a non-authoritative mirror never compared against it. The invariant is restated as "cannot diverge on any attribute an expiry or authorisation decision reads, except the idle clock, which has a single owner", with the co-written set enumerated (`customerId`, `normalizedPhone`, `poolId`, `absoluteExpiresAt`, `revokedAt`, `csrfTokenHash`, `tokenSource`). T-28 now asserts **both** directions, and that the disagreeing-copies case is decided by table 2 | §4.2 (new subsection), §4.2 both record tables, §10.2 (two rows), T-28 |
| 6 | MED | C-12 is a precondition for steps 5 and 7 and is gated nowhere; `--verify` checks only its negatives | **Fixed as recommended.** New **§12 step 4a — C-12 GATE**, four simulations, all reads, blocking **step 5** rather than step 7 because that is where the dependency starts. The positives (`GetItem`, `UpdateItem` on the index table) are now asserted, not only the negatives. The gate distinguishes three outcomes, as the review required: *allowed*, *denied*, and `NoSuchEntity` — which for `wecare-checkout-role` only (M16: not deployed) is a pass-with-note that must be re-gated at provisioning time, and for `wecare-digital-lambda-role` is a **fail** | §12 step 4a (new), §11.1.1 `--verify` table, §13 C-12 |
| 7 | MED | the object across the seam has two incompatible shapes and `__slots__` makes it a runtime error | **Fixed as recommended.** `class CustomerSession(customer_auth.CustomerIdentity)` with its own `__slots__` (required, not tidiness — M23), returned by **both** `resolve` and `require_session`. The naming convention is fixed one-per-layer and stated: DynamoDB attributes `camelCase`, Python attributes `snake_case`, mapped exactly once in the constructor — so §8.5's `session.lastVerifiedAt` becomes `session.last_verified_at` and the document stops mixing them. T-20 gains the `isinstance` assertion | §4.2 (new subsection), §8.2, §8.5, T-20 |
| 8 | MED | CSRF Gate 2 fails closed on two unmeasured headers, and P1 does not probe them | **Fixed as recommended, all parts.** P1 gains **part (c)**: at least one of `Sec-Fetch-Site` and `Origin` must arrive on a same-origin `POST`, and `/customer/session/echo` now reports presence **booleans** for `cookie`, `sec-fetch-site`, `sec-fetch-mode` and `origin` plus the enumerated `sec-fetch-site` value — never a cookie value, never an `Origin` value. A four-row verdict table names the one **degraded** mode (Origin-only, Gate 1 unchanged, recorded as a measured degradation) and the two FAIL cases that trigger C-3 rather than shipping step 7 on Gate 1 alone. The §4.6-vs-§10.1 `Origin`-alone disagreement is **resolved in §4.6 as the single rule**, with §10.1 restating rather than defining it, and the mode is a single env value `--verify` cross-checks. T-04 drives both configurations | §2 P1, §4.6 Gate 2, §10.1 (two rows), §12 step 3, T-04, §16.11 |
| 9 | MED | a rotation config change flips every customer's refresh into a terminal rejection | **Fixed with BOTH halves, as recommended.** (1) One cross-API fallback before concluding terminal, symmetric in both drift directions, attempted exactly once, logging `refresh_rotation_drift` and serving the request. (2) `rotation_enabled` resolved from `DescribeUserPoolClient` cached 300s in module state, env var as fallback on failure, which removes the duplicate rather than surviving it — adding `cognito-idp:DescribeUserPoolClient` to §11.1.1. Two safety details the review did not ask for but which this repo's history demands: a `DescribeUserPoolClient` response can carry `ClientSecret`, so it is projected and never bound to a name or logged; and the fallback-on-failure path logs an event with no client id. `--verify` asserts live rotation state matches the env | §6.2 (new subsection), §11.1.1, §12, T-09 |
| 10 | MED | a module-load `throw` in `customerSession.ts` takes down sign-in even when the cookie flag is off | **Fixed as recommended.** A hard rule is stated on the file — **it must not throw during module evaluation under any input** — and the invariant moves to three places with the loud one at **build** time, where a build-inlined value belongs: a `prebuild`-style `scripts/check_same_origin_api_base.py` (with the §11.3 note that `package.json` is FOREIGN, so it falls back to the test gate), T-10, and a **lazy, memoised, logged-once** runtime check returning a typed `ORIGIN_MISCONFIGURED`. `ORIGIN_MISCONFIGURED` is deliberately outside `requiresReauth`'s set, so a misconfiguration shows `MSG.TRY_LATER` and never starts an OTP. §12 step 6's "nothing changes for shoppers" now holds **unconditionally** | §2 (new subsection), §11.1, §12 step 6, §16.2, T-10 |
| 11 | NIT | §10.2 names the wrong direction of the email invariant | **Fixed as recommended.** The invariant is now "**one customer per verified email address**", with the explicit note that an address-keyed conditional write places **no** bound on addresses per customer and that a per-customer bound would need a different key (a per-customer attribute or a `CUSTOMEREMAIL#<customerId>` row). §8.3's prose already had it right and is unchanged | §10.2 |
| 12 | NIT | the stated digit bound (4–15) is narrower than the delegate's (10–15) and the delegate's exception has no mapping | **Fixed as recommended, both halves.** M23 confirms `normalize_phone` accepts `10 <= len <= 15`. Both tables now state **10–15 digits after composition**, `require_explicit_e164`'s docstring says the **delegate owns the bound** and that its caller must catch `InvalidPhoneNumber`, and §10 maps that exception to `400 {"status":"invalid_phone"}` → `MSG.BAD_NUMBER` with the note that it is a user-fixable refusal and **must not** reach the generic `500` — which is what pass 2 would have done | §9.2 (table + docstring), §10 (new row), §10.1 |
| 13 | NIT | §9.2 asserts the dial-code `<select>` is `required`; it is not, and §9.1 does not add it | **Fixed by correcting the prose and adding NOTHING.** M23 confirms `required` is on the `tel-national` `<input>` (`:134`) and absent on the `<select>` (`:106`). The behaviour was already right, so adding the attribute would be a PR #175 regression dressed as a fix. T-15 asserts the split **in both directions** — present on the number segment, absent on the code segment — since it is the only guard against someone tidying it either way | §9.1, §9.2, T-15 |

### Where the review's "Unverified / Wrong Assumptions" table now stands

U1, U2, U3 and U5 are the HIGHs and finding 8, and all four are corrected above with a fresh source
measurement attached (M19–M23). U4 (P1) is still unproven, still correctly labelled, and **now gated on
three things instead of two** (cookie out, cookie back, and a CSRF header surviving). U6 (M1–M18) and U7
(R2/R3/R6/R9/R11/R12) remain **open and unchanged**: pass 3 made **no AWS call**, so every AWS-derived
claim still rests on its earlier read with its date attached, and pass 3's own measurements are all source
reads. U8 (`Path=/` cache key) is still folded into `--verify-cookie-transport`. U9 (`NOT_ON_WHATSAPP`
evidence) is still unverified and still unwired as C-7.

### What this pass did NOT change, deliberately

The crux (§2, same-origin BFF) stands; the review endorsed it for the third time and nothing in pass 3
touched it. No token goes near `localStorage` or `sessionStorage`. CSRF remains server-side on every
cookie-authenticated mutation, including the two unedited handlers, via the method-derived flag. The
`__Host-` cookie, the dual server-side clocks with the absolute deadline pinned three ways, the
four-name terminal allowlist, the untrusted `X-Forwarded-For`, the atomic phone reservation, the
never-body-selected `customerId`, the two-table custody split and the verify-first ordering are all
unchanged. PR #175 is still extended additively, with no red states, no combined input, no
locale-inferring selector and no SMS fallback. **No deploy, no pool mutation, no app-client mutation, no
WAF, no Security Hub, no DNS or MTA-STS change is proposed anywhere in this document**, no secret value
appears in any command, log or logging expression, `secretsmanager get-secret-value` is called in no
spelling, and §15 restates every one of those as a rule the implementation must keep.
