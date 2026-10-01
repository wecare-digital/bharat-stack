# Design review — backend-owned customer session + OTP/identity hardening

**Reviewed** 2026-10-01, Asia/Kolkata. **Pass 4.** Document under review:
`.agents/tasks/customer-session-20261001/design.md` (2,481 lines), against
`.agents/tasks/customer-session-20261001/baseline.md`.

**Verdict: CHANGES_REQUESTED — 4 HIGH, 4 MEDIUM, 3 NIT.**

**Method.** This is a review of the document and its stated assumptions. No build was run, no test
suite was run, and **no AWS call was made** — so every AWS-derived claim (M1–M16) carries forward
unverified from its earlier read, as the design itself says. What *was* done is a read of the source
each claim cites. The pass-3 source measurements M17–M24 were re-checked line by line and **all
eight hold** (see Verified Assumptions). The findings below are therefore not re-litigation of
earlier passes: three of the four HIGHs are seams the document has not looked at yet — the frontend
pages that actually call the cookie-authenticated endpoints, the cache posture of the session
response, and the write half of the C-12 grant — and the fourth is a delegation it believes closes an
inference that it does not close.

No secret value was read, printed, or placed on a command line.
`secretsmanager get-secret-value` / `batch-get-secret-value` were not called in any spelling.

**On the blocking list in the review brief.** The crux (§2) is resolved with an explicit, justified
same-origin decision resting on a measured live rewrite (M1), with the cross-origin alternative
rejected on the record and P1 gating the unmeasurable part. No token goes near `localStorage` or
`sessionStorage`. CSRF is server-side on every cookie-authenticated mutation including the two
unedited handlers. The cookie is `__Host-` on the canonical host and the staff app is kept out by
three non-cookie controls. Both clocks are server-side and the absolute deadline is pinned three
ways. Rotation is handled with `GetTokensFromRefreshToken` plus a symmetric drift fallback. A 5xx is
explicitly not a logout. No mutation derives from a body-selected id. Phone ownership is reserved
atomically. The `PutItem` send-counter finding is present with a code fix and a narrow, dedicated-role
C-2. `X-Forwarded-For` stays untrusted. PR #175 is extended additively with no red states and no SMS
fallback. No deploy, pool mutation, WAF, Security Hub or DNS change is proposed. **None of the
brief's enumerated blockers fired.** The findings below are independent of that list.

---

## Findings

### 1. HIGH — `require_explicit_e164` does not make the `+91` inference unreachable, and the failure sends a stranger an OTP

**Where.** §9.2 (`require_explicit_e164`'s docstring and the surrounding prose), §16 assumption 9's
neighbourhood, T-19.

**The claim.** §9.2: *"The session function's `/customer/session/challenge` calls
`require_explicit_e164` **before** `normalize_phone`. So the length inference inside
`normalize_phone` still exists for its existing callers and is **unreachable from the new door**."*
And the docstring: *"Delegates the final shape to identity.normalize_phone AFTER the explicit prefix
has been proven."*

**Why it is wrong.** The inference is not keyed on whether a prefix was typed. Read
`identity/customer.py`:

```python
_INDIAN_MOBILE_RE = re.compile(r"^[6-9]\d{9}$")      # line 50
...
digits = re.sub(r"\D", "", text)                      # the "+" is gone by here
if digits.startswith("00"): digits = digits[2:]
if digits.startswith("0"):  digits = digits.lstrip("0")
if _INDIAN_MOBILE_RE.match(digits):
    digits = default_country + digits                 # line 132 — fires on DIGITS
```

`require_explicit_e164` proves the prefix, strips it, and hands over a digit string. Any explicitly
coded international number whose **total** digit count is 10 and whose first digit is 6–9 matches
`_INDIAN_MOBILE_RE` and gets `91` prepended. That is not a corner case: Singapore is country code
`+65` with an 8-digit national number, so a shopper who deliberately selects `+65` in the PR #175
dial-code segment and types `9123 4567` composes `+6591234567`, and the server stores
**`+916591234567`**.

Consequences, in order of severity:

- The `customer_phone_ownership` OTP is sent over WhatsApp to **`+916591234567` — a different,
  real Indian subscriber** who has nothing to do with the request. That is an unsolicited message to
  an uninvolved third party, which is the one outbound-messaging outcome this repo's rules are most
  insistent about.
- The Singapore shopper can never complete sign-in; the failure is invisible to them because the
  masked `destination` ends in the digits they typed.
- If anyone ever does complete that challenge, §8.1's **permanent, never-deleted**
  `PHONE#+916591234567` reservation is minted against a number nobody involved owns.
- Other affected code-length combinations exist wherever `cc + national == 10` digits and the code
  starts 6–9 (`+65`, `+64` short forms, `+7` short forms, and similar).

The client agrees with the server on the wrong answer — `customerAuth.normaliseMobile` has the same
rule — so §9.2's byte-for-byte-agreement note is satisfied and still produces a wrong number. T-19 as
written cannot catch it: it asserts `+919876543210` and `00919876543210` are accepted, bare
`9876543210` is refused, and that `normalize_phone` is unmodified. None of those is the failing case.

**Concrete fix.** Neutralise the inference at the call site without editing the shared function —
`normalize_phone` already takes the keyword:

```python
def require_explicit_e164(raw: str) -> str:
    text = str(raw or "").strip()
    if not re.match(r"^(\+|00)", text):
        raise ExplicitCountryCodeRequired("country code must be stated, never inferred")
    # default_country="" disables the ten-digit +91 inference WITHOUT touching the shared
    # function: `digits = "" + digits` is a no-op, the already-prefixed branch then matches
    # on the unchanged digits, and the 10..15 bound still applies. Verified against
    # identity/customer.py lines 120-150.
    return identity.customer.normalize_phone(text, default_country="")
```

Trace both directions before accepting it: `"6591234567"` → regex matches → `digits` unchanged →
`startswith("")` is True and `_INDIAN_MOBILE_RE.match(digits[0:])` matches → returns
`"+6591234567"`. `"919876543210"` → 12 digits, first regex misses → `startswith("")` True,
`match(digits[0:])` misses → `10 <= 12 <= 15` → `"+919876543210"`. Both correct, no shared-module
edit, and the delegate still owns the 10–15 bound and still raises `InvalidPhoneNumber`.

T-19 must gain the case that fails today: `require_explicit_e164("+6591234567") == "+6591234567"`,
plus an assertion that the returned value's digits are byte-identical to the composed input's digits
for a table of explicit codes (`+65`, `+971`, `+44`, `+1`, `+91`), which is the property rather than
one spelling of it.

---

### 2. HIGH — §12 step 7 breaks the only two customer pages that call the cookie-authenticated endpoints, and neither is in scope

**Where.** §12 steps 5–7, §11.2's `src/lib/customerAuth.ts` row, §11.1's `customerSession.ts` row.

The design's rollout rests on "step 7 is reversible by turning the flag off, because step 5's Bearer
branch is still live". That is true of the *backend*. It is not true of the frontend, because two
pages gate on a `sessionStorage` token that step 7 stops writing:

| File | Line | What it does |
|---|---|---|
| `src/pages/cart.tsx` | 149 | `const session = getSession()`; if null → `window.location.assign(SIGN_IN_PATH)`. Otherwise `POST CHECKOUT_URL` with `Authorization: Bearer ${session.accessToken}` and `{action:'create', lineItems}` |
| `src/pages/checkout/status.tsx` | 159 | `const session = getSession()`; if null → `setView('unavailable')` and stop polling. Otherwise `POST CHECKOUT_STATUS_URL` with the same Bearer header |

After step 7, `getSession()` returns `null` for every shopper, because the cookie is the credential
and nothing writes `wecare.customer.accessToken` any more. So:

- **every "Checkout" click on `/cart/` redirects a fully signed-in shopper to `/account/sign-in`**,
  where §12 step 6's own logic will find them already signed in and bounce them back to the cart —
  a loop with no error and no log;
- **`/checkout/status/` reports `unavailable` for every in-flight payment** and stops polling, which
  is the screen that owns the honest copy for an attempt that may have taken money.

And even if `getSession()` were made to return something, both requests are mutating `POST`s that
carry **no `X-WD-CSRF`**, so §4.6's method-derived gate answers `403 CSRF_REQUIRED` — which §6.4
deliberately keeps out of `requiresReauth`, and which `cart.tsx` does not handle (it branches only on
`401`). That is precisely the "cart that silently refuses to change with no recovery path" outcome
§2's P1 part (c) was added to prevent, arriving from the frontend instead of from a stripped header.

Neither file appears in §11.2's changed list, in §11.1's created list, or in baseline §4's owned
paths. `src/lib/customerAuth.ts`'s blast-radius cell names "`sign-in.tsx`, `checkout/status.tsx`" and
**omits `cart.tsx` entirely**, so the one page that initiates checkout is unaccounted for. T-25 does
not name `src/test/CartCheckout.test.tsx`, which exists and pins this exact behaviour (it stubs
`customerAuth.getSession` in nine places).

**Concrete fix** — pick one and write it down, because the two have different owners:

1. **Preferred, and it keeps the file boundary intact.** Keep `getSession()` working as a *shim*
   rather than a storage read: add `customerSession.hasSession()` and have `customerAuth.getSession`
   return a non-null sentinel `{accessToken: '', expiresAt: <session expiry>}` when the cookie flag
   is on, **and** route both pages' `fetch` through `customerSession.apiFetch` so the CSRF header is
   attached. That still requires editing `cart.tsx` and `status.tsx`, so it is a coordination item,
   not a local change.
2. **If those two files cannot be touched this run**, then step 7 is not reachable and must say so:
   add **C-13 — `cart.tsx` and `checkout/status.tsx` must move onto `customerSession.apiFetch`
   before §12 step 7**, owned by the checkout session, with step 7 gated on it exactly as step 5 is
   gated on C-12 at step 4a. Add `src/test/CartCheckout.test.tsx` and a cookie-mode case to T-25.

Either way, §12 step 6's "nothing changes for shoppers — unconditionally" must stop implying that
step 7 is equally benign. It is the step with the largest shopper-visible blast radius in the
document and it currently has no gate.

---

### 3. HIGH — the session response carries no cache directives, and it contains the CSRF token

**Where.** §3's endpoint table (`GET /customer/session` returns `csrfToken`), §4.2's "Nothing from
Cognito is ever sent to the browser" paragraph, §4.6's `Path=/` cache-trade subsection, §12's
`--verify` list, T-27.

`GET /customer/session` returns `{authenticated, customerId, displayPhone, csrfToken, expiresAt,
remembered}`. The design builds every response through `lambda_utils/response.py:cors_response`
(stated in §4.6 and §11.3), and that function emits exactly three headers:

```python
headers = {'Content-Type': 'application/json',
           'Access-Control-Allow-Origin': allowed,
           'Access-Control-Allow-Headers': ..., 'Access-Control-Allow-Methods': ...}
```

**No `Cache-Control`, no `Pragma`, no `Vary`.** The whole point of §2 is that this response travels
back through a CloudFront-fronted Amplify rewrite. §4.6 already recognises that the distribution's
treatment of cookies is unknown and folds an `x-cache` measurement into
`--verify-cookie-transport` — but it measures the *HTML* side and never asks the question from the
API side. The two bad outcomes are symmetric and both are live:

- if the distribution caches `/api/*` and does **not** vary on `Cookie`, a cached
  `GET /api/customer/session` can serve **one shopper's `customerId`, masked phone and live CSRF
  token to another viewer** — a cross-customer disclosure *and* a handed-over Gate 1 token;
- if it caches and the first fill was anonymous, every signed-in shopper gets a cached `401`, which
  reads as a broken session with no server-side evidence.

This is the same omission class the document holds up as its own cautionary tale: a correct design
with one missing directive, failing silently through infrastructure nobody measured.

**Concrete fix.** `response.py` is DO-NOT-TOUCH and shared, so add the headers where `_denied`
already augments the dict — one builder, both the success and the refusal path:

```python
# lambda_utils/customer_session.py
_NO_STORE = {"Cache-Control": "no-store, no-cache, must-revalidate, private",
             "Pragma": "no-cache", "Vary": "Cookie, Origin"}

def _respond(event, status, body, *, clear=False):
    """EVERY response from the session function, success or refusal.

    cors_response() emits no cache directives (response.py:47-80) and this body carries the
    CSRF token, so a shared cache MUST be told not to keep it. response.py is fleet-shared and
    DO-NOT-TOUCH, so the headers are added here - the same reason _denied() adds `cookies`.
    """
    response = cors_response(status, body, extract_origin(event))
    response["headers"].update(_NO_STORE)
    if clear:
        response["cookies"] = [clear_cookie_header()]
    return response
```

Then: `_denied` delegates to `_respond`; T-11 extends to assert `Cache-Control` contains `no-store`
on **all eight** routes; `--verify` adds "the live `GET /api/customer/session` 401 carries
`Cache-Control: no-store`" alongside its existing no-`Access-Control-Allow-Credentials` assertion;
and `--verify-cookie-transport` records `x-cache` for `/api/customer/session` as well as for HTML,
with a documented FAIL when two requests carrying different cookies produce the same `x-cache: Hit`.

---

### 4. HIGH — C-12 grants 63+ functions unconditional write access to the table the design calls "the authority for every ownership check"

**Where.** §11.1.1 (the two-roles paragraph), §13 C-12, §4.2's custody-split argument, §10.2's
invariant table, §12 step 4a.

The split in §4.2 is the right architecture and M15 justifies it. But the grant it hands the foreign
roles is read **and write**, unconditioned:

> `wecare-digital-lambda-role` (the shared fleet role, M15) and `wecare-checkout-role` (M16) each
> receive `dynamodb:GetItem` **and** `dynamodb:UpdateItem` on `CustomerSessionIndexTable` only …
> That is the whole point of the §4.2 split: **the grant that must be wide leaks nothing**, and the
> grant that would leak is narrow.

"Leaks nothing" is a confidentiality claim and it is true. The integrity claim is missing and it is
false. `CustomerSessionIndexTable` holds `customerId`, `poolId`, `csrfTokenHash`,
`absoluteExpiresAt`, `revokedAt` and `tokenSource` — and §4.2 and §10.2 both say that row is what
authorises the request. An unconditioned `UpdateItem` on it, held by the role shared by the entire
fleet, means **any** of those functions can:

- rewrite `customerId` on a live session row, pointing an authenticated session at a different
  customer — the exact IDOR that `authorize_resource` exists to prevent, one layer below it;
- clear `revokedAt`, resurrecting a signed-out or killed session, which defeats the "our own kill
  switch has no latency" mitigation §7.2 leans on to justify the ≤60-minute revocation window;
- extend `absoluteExpiresAt`, breaking the invariant §5.2 pins three ways — note that all three
  enforcement mechanisms live in the session function, so none of them sees a write from elsewhere;
- overwrite `csrfTokenHash`, turning Gate 1 into a gate whose server state an unrelated function
  chooses.

§12 step 4a's gate asserts the positives (`GetItem`, `UpdateItem` allowed) and the two
confidentiality negatives (table 1, the CMK denied). It has no negative for the write surface, so a
passing gate is consistent with all four outcomes above.

The design's own standard applies here and it is quotable from §10.2: *"the only layer that holds
against a role… An application-level convention cannot bind a different function."* The convention
that the fleet role only ever touches two timestamp attributes is exactly such a convention.

**Concrete fix — option (b) is the one I would take.**

- **(a) Bound the grant to the two attributes** with DynamoDB fine-grained access control on the
  C-12 statement: `"Condition": {"ForAllValues:StringEquals": {"dynamodb:Attributes":
  ["sessionIdHash","idleExpiresAt","lastSeenAt"]}, "StringEquals": {"dynamodb:ReturnValues":
  "NONE"}}`. I have **not** verified this condition shape against current DynamoDB FGAC behaviour for
  `UpdateItem` in this account — it is documented but it must be proven by
  `iam simulate-principal-policy` on a disallowed attribute before it is relied on, and a condition
  that silently does nothing is worse than no condition.
- **(b) Remove the shared write entirely.** Grant the two foreign roles `dynamodb:GetItem` **only**,
  and let the idle clock be advanced solely by the session function. The cost is that a shopper who
  spends six days entirely inside the cart without a single `GET /customer/session` idles out — which
  is the failure pass-3 finding 5 identified. It is cheaply avoided: `customerSession.ts` already
  holds one in-flight `GET /customer/session` per tab (§6.1), so specify that the client pings it on
  a bounded interval (for example, on page show and at most every 30 minutes), which keeps the clock
  honest with **zero** foreign write access. This also deletes the §4.2 co-write exemption and
  restores the simpler invariant.

Whichever is chosen, §12 step 4a must gain the negative that proves it: under (a), the fleet role is
**denied** `UpdateItem` when `dynamodb:Attributes` includes `customerId`; under (b), the fleet role is
**denied** `UpdateItem` on `CustomerSessionIndexTable` outright. And §11.1.1's "the grant that must be
wide leaks nothing" must be rewritten to say what the grant can and cannot do, since the sentence as
written is the reason this went unexamined for three passes.

---

### 5. MEDIUM — where the Cognito `Session` lives is specified two ways, and its deletion has no granted permission

**Where.** §4.2 table 1 (`cognitoAuthSession`), §8.8 step 5, §10.1's `challengeHandle` note,
§11.1.1 row 8.

Three statements that cannot all be true:

| Section | Says |
|---|---|
| §4.2 table 1 | `cognitoAuthSession` S — *"the provider `Session` string during a challenge only; **deleted on completion** (§10.1)"* — on `CustomerSessionsTable` |
| §8.8 step 4/5 | *"store the provider `Session` on an **`otp#` row**"*, then *"load the `otp#` row by handle"* |
| §10.1 | *"the session function stores the Cognito `Session` on a short-lived row (**`otp#` namespace, 10-minute TTL** matching `AuthSessionValidity`)"* |

§4.2's placement is impossible: during a challenge there is no `CustomerSessionsTable` row at all —
§8.8 step 7 creates it after the code verifies, which is the ordering property T-29 is built to
assert. So a reader implementing §4.2 would either write a pre-session row in table 1 (destroying the
"nothing is created before the phone is proven" property) or discover the contradiction at coding
time and guess.

The `otp#` reading is the right one, and it exposes a second gap. `otp#` rows live in
`DownloadGrantsTable` (the `otp_throttle` / `otp_challenge` home, M9), where §11.1.1 grants
`GetItem`, `PutItem`, `UpdateItem` and **no `DeleteItem`**. "Deleted on completion" is therefore
either not implementable or silently becomes something else. This is the M19 shape again, in the same
row of the same table, found by the same question.

**Concrete fix.** Delete the `cognitoAuthSession` line from §4.2 table 1 and state in §8.8 step 4
that the provider `Session` lives **only** on the `otp#` row. Then pick the completion mechanism
explicitly and make `REQUIRED_PERMISSIONS` match it:

- if the row is removed: add `("dynamodb:DeleteItem", "<DownloadGrantsTable arn>")` to
  `REQUIRED_PERMISSIONS` with the comment naming §8.8 step 6;
- if the attribute is stripped and the row left to TTL: specify
  `UpdateExpression="REMOVE cognitoAuthSession SET consumed = :true"` with
  `ConditionExpression="consumed = :false"`, which the granted `UpdateItem` already covers, and say
  that TTL reaps the husk.

T-29 should assert that after a completed `/customer/session`, no stored row holds the provider
`Session` string — the property, not one spelling of it.

---

### 6. MEDIUM — the new-customer WhatsApp send is the primary flow and is specified in four words

**Where.** §8.8 step 3 (*"send that code over WhatsApp ourselves"*), §11.1.1's
`lambda:InvokeFunction` row, §10's `WhatsApp send failed` row, M20.

M20 is cited only for *which* ARN to grant. The source it cites specifies a great deal more, all of
it load-bearing (`customer-registration/handler.py::_send_code`):

```python
body = {"to": _wa_destination(e164), "phoneId": META_PHONE_NUMBER_ID,
        "templateName": OTP_TEMPLATE_NAME, "language": OTP_TEMPLATE_LANGUAGE,
        "components": [{"type": "body", "parameters": [{"type": "text", "text": code}]},
                       {"type": "button", "sub_type": "url", "index": "0",
                        "parameters": [{"type": "text", "text": code}]}]}
invoke_event = {"httpMethod": "POST",
                "path": "/wa-business/messages/send/template", "body": json.dumps(body)}
```

and the docstring records a verified-against-the-live-WABA constraint: the `wecare_otp`
**AUTHENTICATION** template must use a `url` button, **not** `copy_code`, because Meta rejects
`copy_code` on an AUTHENTICATION template. A business-initiated message to a brand-new number has no
open 24-hour window, so a free-form send fails outright — an implementer who writes this from the
design text alone will produce a send that cannot work and will see it as `502 send_failed`, which §9.3
has already decided must **not** be reported as "not a WhatsApp number". The new-customer branch is
the *primary* new-shopper path in this design, and it would be dead on arrival.

Five environment keys are implied and none is named in `expected_environment()`'s description:
`SENDER_FUNCTION`, `META_PHONE_NUMBER_ID`, `OTP_TEMPLATE_NAME`, `OTP_TEMPLATE_LANGUAGE`, and the
synthetic route path.

**Concrete fix.** Name one reuse point rather than a second copy, matching the discipline the
steering applies to `_build_payment_settings`: extract `_send_code` into
`lambda_utils/comms/whatsapp_otp.py::send_otp_template(e164, code, *, invoke)` — a new additive
shared module under owned paths — and have **both** `customer-registration` and the session function
call it, so the Meta-verified component shape has exactly one home. Add the five keys to
`expected_environment()` and to `--verify`. Add a test to T-29 asserting the invoke payload's
`templateName`, `language`, both component entries and `sub_type == "url"` (never `copy_code`), driven
against a fake Lambda client, since that constraint is a provider fact a refactor cannot rediscover.

---

### 7. MEDIUM — the copy contract names the wrong source of record, the wrong count, and an existing test it will break

**Where.** §9.3 (*"Already present in `sign-in.tsx`'s `MSG` table"*), T-16, §11.2's
`src/test/AccountSignIn.test.tsx` row, T-25.

What the tree actually holds:

- the approved strings live in **`src/lib/signInMessages.ts`**, not in `sign-in.tsx`. The page's
  `MSG` object is a re-export (`MISSING_CODE: signInMessages.MISSING_CODE`, and so on), and its own
  comment says so: *"SOURCED FROM ../../lib/signInMessages, which holds all seven section-6 strings
  verbatim in one auditable place. This page no longer re-types the copy."*
- there are **eight** exported strings, and `SECTION_6_MESSAGES` is a seven-element array that
  **includes `MISSING_CODE`** (`'Include your country code, like +91.'`) and **excludes
  `NOT_ON_WHATSAPP`**. §9.3's table lists seven rows plus the hint and does not mention
  `MISSING_CODE` anywhere in the document.
- `MISSING_CODE` is in exactly the state §9.3 goes to such lengths to describe for
  `NOT_ON_WHATSAPP`: present, approved, deliberately unreachable because the divided field always
  carries a code, kept so the next person finds the sanctioned wording instead of inventing one.
  Omitting it from the design's copy table is how it gets deleted as dead code.
- **`src/test/SignInMessages.test.tsx` already pins all of this**, and it asserts against the page's
  *source text*: `expect(SIGN_IN_SOURCE).toContain("import * as signInMessages from
  '../../lib/signInMessages'")` and, per key, `expect(SIGN_IN_SOURCE).toContain(\`signInMessages.${key}\`)`,
  plus the no-red `.si-error` block and
  `expect([...SECTION_6_MESSAGES]).not.toContain(NOT_ON_WHATSAPP)`.

§11.2 rewrites `sign-in.tsx` to drop the register/two-code branch. That rewrite has to keep every
`signInMessages.<KEY>` reference and the `.si-error` CSS block intact or `SignInMessages.test.tsx`
fails — and that file is named nowhere in the design: not in §11.2, not in T-16, not in T-25's list.
T-16 instead specifies "the seven live `MSG` strings byte-exact" in a *different* file, which both
duplicates an existing contract and states it with the wrong count against the wrong source.

**Concrete fix.** In §9.3, name `src/lib/signInMessages.ts` as the authority, add a `MISSING_CODE`
row with its unreachable-by-construction status beside `NOT_ON_WHATSAPP`, and note that
`SECTION_6_MESSAGES` is seven **including** `MISSING_CODE`. In §11.2, add
`src/test/SignInMessages.test.tsx` with the constraint spelled out: the one-code rewrite must preserve
every `signInMessages.<KEY>` reference and the `.si-error` block. Re-scope T-16 to *extend*
`SignInMessages.test.tsx` (add "no code path renders `NOT_ON_WHATSAPP`" and "no code path renders
`MISSING_CODE`") rather than re-pin the strings in `AccountSignIn.test.tsx`. Add both files to T-25.

---

### 8. MEDIUM — `challengeHandle` is now ours to mint, and is still validated as if it were Cognito's

**Where.** §10.1's validation table, §8.8 step 5, §10.1's closing note.

The handle changed owner in this design — *"the browser never sees it: the session function stores
the Cognito `Session` on a short-lived row and hands the browser an **opaque handle**"* — but its
validation rule did not: *"opaque server-issued string ≤ 4096 chars"*.

The design applies the opposite discipline to the cookie one row above, and explains why in a
sentence that applies here verbatim: *"The cookie charset check before any table read matters: it
turns a malformed or injected cookie into a zero-cost rejection rather than a DynamoDB request, which
removes a trivial amplification vector on a public endpoint with no WAF in front of it."*
`POST /customer/session` is unauthenticated, is the busiest unauthenticated route in the feature, and
`challengeHandle` is its only lookup key — so a 4 KB-tolerant opaque string is a free DynamoDB
request per attempt on a no-WAF API.

Three things the handle's row also needs stated, because step 5 depends on all of them and none is
specified: it must carry the **normalized phone** (step 6b passes `subject=e164` to
`otp_challenge.verify`, and taking the phone from the request body instead would let a caller pair
someone else's handle with their own number), the **branch** that issued it, and a **single-use**
marker so one handle cannot drive repeated `RespondToAuthChallenge` attempts outside Cognito's
`MAX_ATTEMPTS`.

**Concrete fix.** In §10.1: `challengeHandle` — *"exactly 43 chars, `[A-Za-z0-9_-]` only
(`secrets.token_urlsafe(32)`, minted by us); anything else is `400` **without a table read**, the same
rule and the same reason as the cookie."* In §8.8 step 4, state the row's attributes:
`{handleHash, normalizedPhone, branch ∈ {cognito, phone_ownership}, cognitoAuthSession?, consumed,
expiresAtEpoch}` keyed on `sha256(handle)` for the same reason table 1 is keyed on the hash of the
session id, with `normalizedPhone` read **from the row and never from the body**. Add that assertion
to T-29.

---

### 9. NIT — stale line reference for `checkout`'s `require_customer` call

§3, §4.6 and §11.2 all cite `ecommerce/checkout/handler.py:196`. The call is at **:229**
(`identity, denied = customer_auth.require_customer(event)`); line 196 is inside `_body`. `wix-store`'s
`:368` is correct. Two of the three citations are in the paragraphs that justify the method-derived
CSRF gate, so the wrong line is in the places a reviewer will check first. Update all three to
`:229`, or cite the function name rather than the line, since the tree moves under another session.

---

### 10. NIT — the KMS statement names an alias where it needs a key ARN

§11.1.1 gives the resource as *"the CMK behind `alias/wecare-customer-sessions`"*. An alias ARN is not
a reliable resource for `kms:Decrypt`/`kms:GenerateDataKey` in an identity policy, and the key ARN is
not knowable until `provision_customer_session.py` creates the key. State it explicitly: the script
resolves the key ARN from its own `CreateKey` response (or `DescribeKey` on the alias) and writes the
**key ARN** into both the policy document and `REQUIRED_PERMISSIONS`, never the alias — so the
`--verify` simulation and the live grant cannot disagree about which resource was meant.

---

### 11. NIT — `/customer/session/echo` is an unauthenticated POST with no stated limits and an optional retirement

§3 and §2 P1. The echo route exists to answer one question once, yet it is an unauthenticated `POST`
on an API with no WAF, with no throttle named, and `--retire-echo` is described as something the
provisioning script *can* do. Add three sentences: it performs **no** table read and **no** write
(the §4.6 `Path=/` and P1 measurements need nothing stored); it is subject to the same per-IP
`otp_throttle` axis as `/challenge`; and `--retire-echo` is **mandatory** at §12 step 8 rather than
optional, with `--verify` asserting the route returns `404` once retired. The response shape itself is
already right — booleans plus one four-value enum, no cookie value, no `Origin` value.

---

## Verified Assumptions

Re-checked against the committed tree by reading the cited source. All of these hold as the design
states them.

| Design claim | Checked | Result |
|---|---|---|
| M17 — `_digest` is called for **both** the subject and the code digest | `otp_challenge.py:144`, `:254`, `:318` | **Holds.** `_digest(pepper,"subject",purpose,subject)` and `_digest(pepper,"code",purpose,subject,code)`. §8.3's "thread `*extra` into both" is necessary and correctly stated |
| M18 — the cart partition key **is** the E.164 phone | `ecommerce/customer_cart.py:46`, `:48` | **Holds.** `re.fullmatch(r"\+[1-9][0-9]{7,14}", identity.phone or "")` then `"CUSTOMERCART#" + identity.phone`. `normalizedPhone` on the resolution record is required |
| M19 — `otp_challenge.issue` creates its row with `put_item` | `otp_challenge.py:270` | **Holds.** `dynamodb:PutItem` on `DownloadGrantsTable` is genuinely required |
| M20 — the only non-trigger WhatsApp send path | `customer-registration/handler.py:94`, `:187`; `customer-whatsapp-auth/handler.py:37`, `:225` | **Holds.** `SENDER_FUNCTION` defaults to `wecare-whatsapp-business-api:live` in both, invoked via `_lambda_client().invoke` (see finding 6 for what else that site specifies) |
| M21 — the email send path | `email-verification/handler.py:108` (`boto3.client("sesv2")`) | **Holds.** SESv2, so `ses:SendEmail` against identity **and** configuration set is the right shape |
| M22 — the challenge answer is unreachable outside the trigger | `customer-whatsapp-auth/handler.py:270` writes only `event["response"]["privateChallengeParameters"]`; `:367` reads it back in verify; no `ClientMetadata`/`clientMetadata` anywhere in that handler | **Holds.** Pass-2's "server-held answer" was indeed unimplementable, and §8.8.0's tokenless first session is the correct response. The `SUPPRESS_SEND` deletion is right: `ClientMetadata` on an unauthenticated `InitiateAuth` is attacker-writable |
| M23 — three source facts | `customer_auth.py:84` `__slots__ = ("customer_id","phone","subject")`; `identity/customer.py:147` `10 <= len(digits) <= 15`; `PhoneField.tsx:134` `required` on the `tel-national` input, `:106` `aria-label="Country code"` on the `<select>` with no `required` | **All three hold.** `CustomerSession` needing its own `__slots__` is a real constraint, the 10–15 bound is right, and §9.2's corrected `required` prose matches the file. (The 10–15 bound's *reachability* is finding 1 — the bound itself is correctly stated) |
| M24 — the provisioning shape | `customer-registration/handler.py:293-300` `admin_create_user(..., MessageAction="SUPPRESS")` then `admin_set_user_password`; `:290` stamps `custom:customer_id` | **Holds**, including the already-correct message suppression — the new flow needs no trigger change to stay silent |
| `require_customer` returns `(identity, None)` / `(None, response)` | `customer_auth.py:199-221` | **Holds.** §4.6's snippet composes correctly on the existing shape |
| `authenticate` raises only `CustomerNotAuthenticated` on every failure, including a missing `custom:customer_id` | `customer_auth.py:136-172` | **Holds**, and this is what makes "Bearer first, then cookie" safe: no Bearer failure mode escapes past the `except` into the caller, so a valid cookie is always reached |
| `cors_response` has no `cookies` key, so payload-2.0 `Set-Cookie` must be added by the caller | `response.py:66-80` | **Holds.** `_denied`'s augmentation is necessary. (It also has no cache directives — finding 3) |
| `cors_headers` always emits ACAO, falling back to `ALLOWED_ORIGINS[0]` | `response.py:47-62` | **Holds**, so §4.6's corrected cross-origin mechanism (`AllowCredentials: false`, not ACAO suppression) is the right one |
| only two handlers call `require_customer` | repo-wide grep: `wix-store/handler.py:368`, `checkout/handler.py:229` | **Holds** (modulo the line number, finding 9). No third function silently needs the C-12 grant |
| `API_BASE` is a default, not a hardcode | `src/config/constants.ts:20` `process.env.NEXT_PUBLIC_API_BASE \|\| 'https://wecare.digital/api'` | **Holds.** §2's build/test/lazy-runtime triple and the "must not throw at module evaluation" rule are the right response |
| `otp_throttle` does not consult `X-Forwarded-For`; `DEFAULT_IP_MAX` is 20; `_consume` uses `put_item` on rollover | `otp_throttle.py:62`, `:79-83`, `:133`, `:159` | **Holds.** The §8.6 rollover fix applies to the identical shape in both places, and §8.7's refusal to trust the forwarded header is correct |
| the hint copy exists verbatim | `sign-in.tsx:454` `Pick your country code, then the number WhatsApp is on.` | **Holds** |
| the CustomersTable phone GSI name | `customer-registration/handler.py:218` defaults `CUSTOMERS_PHONE_INDEX` to `normalizedPhone-index`; `provision_customer_registration.py:56` agrees | **Holds.** §11.1.1's index ARN is right. (One docstring at `:210` says `PhoneIndex` — the code does not) |
| the cookie is on the canonical customer host and is not *shared* with the staff app | §4.4's three controls | **Acceptable.** `__Host-` forces `Path=/` on a single origin, so attachment to staff `/api/*` requests is unavoidable; the design correctly says cookie scope is not the control and keeps `middleware.require_auth` cookie-free with an AST test plus a pool-id refusal on the row. No finding |

---

## Unverified / Wrong Assumptions

**Wrong, and corrected above:**

| # | Assumption | Status |
|---|---|---|
| W1 | §9.2: "the length inference inside `normalize_phone` … is **unreachable from the new door**" | **WRONG.** The inference keys on the digit string, not on whether a prefix was typed. Finding 1 |
| W2 | §12 steps 5–7: the rollout is reversible and step 7 is just a flag | **INCOMPLETE and wrong in effect.** `cart.tsx:149` and `checkout/status.tsx:159` gate on `getSession()` and send no CSRF header; neither is in scope. Finding 2 |
| W3 | §11.1.1: "the grant that must be wide **leaks nothing**" | **TRUE for confidentiality, FALSE for integrity.** Unconditioned `UpdateItem` on the authorisation-authority table, held by the fleet role. Finding 4 |
| W4 | §4.2 table 1: `cognitoAuthSession` lives on `CustomerSessionsTable`, "deleted on completion" | **CONTRADICTS §8.8/§10.1** (no table-1 row exists during a challenge) and has no granted `DeleteItem`. Finding 5 |
| W5 | §9.3: the approved copy is "already present in `sign-in.tsx`'s `MSG` table", seven strings | **WRONG source and wrong count.** `src/lib/signInMessages.ts`, eight exports, `SECTION_6_MESSAGES` is seven **including** `MISSING_CODE`, already pinned by `src/test/SignInMessages.test.tsx`. Finding 7 |
| W6 | §3/§4.6/§11.2: `ecommerce/checkout/handler.py:196` | **WRONG line.** `:229`. Finding 9 |

**Unproven, correctly labelled by the design, and unchanged by this review:**

| # | Assumption | Status |
|---|---|---|
| U1 | **P1** — the Amplify rewrite is cookie-transparent, and at least one of `Sec-Fetch-Site` / `Origin` survives it | Still unproven, still correctly gated at §12 step 3 before anything depends on it, and the four-row verdict table including the one degraded mode is the right shape. Finding 3 adds a third thing the same step must measure (API-side cacheability), which is a *gap in the probe*, not a new assumption |
| U2 | **M1–M16** — every AWS-derived fact (the `/api/<*>` rewrite, `AllowCredentials: false`, payload format 2.0, `RefreshTokenRotation: null`, the `PutItem` implicitDeny, the three absent tables/secret, `wix-store` on the shared fleet role, the absent `wecare-checkout`) | **Not re-verified by this review — no AWS call was made.** Each still rests on its pass-1 or pass-2 read with its date attached. M1, M5, M7, M10, M12 and M15 are the six that decide the architecture; if any has drifted, the sections resting on it must be re-derived rather than re-read |
| U3 | **R2, R3, R6, R9, R11, R12** — route/authorizer counts, live page probes, pool `SchemaAttributes`, the test baseline, the `live` alias version, steering counts | Still deliberately not re-measured. R6 (`custom:customer_id`) is correctly promoted to a blocking read at §12 step 0 with the owner decision in C-1, and the design correctly states what it does if the attribute is absent |
| U4 | **C-7** — Meta's recipient-not-found classification that would earn `NOT_ON_WHATSAPP` | Still unverified against a live Graph response, still unwired, and the design is right not to guess it. Finding 7 only asks that `MISSING_CODE` be given the same explicit treatment |
| U5 | DynamoDB FGAC `dynamodb:Attributes` conditions on `UpdateItem` | **Introduced by me in finding 4 option (a) and NOT verified in this account.** It must be proven by simulation before it is relied on; option (b), removing the shared write, needs no unverified mechanism and is the safer choice |

---

## Verdict

4 HIGH + 4 MEDIUM blocking findings → **CHANGES_REQUESTED**.

The architecture is not what needs changing. The crux decision, the two-table custody split, the
verify-first ordering, the tokenless first session, the dual server-side clocks, the terminal
allowlist and the method-derived CSRF gate all survive this pass unchallenged, and the pass-3 source
measurements all hold. What the findings have in common is the **edge of the specified system**: the
frontend pages that actually call these endpoints, the CDN that carries the responses, the write half
of a grant described only by what it reads, and a delegation trusted to enforce something it never
looked at. Four of the eight are in files the document does not name.

Findings 1, 2, 3 and 4 need a decision each (and 2 and 4 need a named gate, as C-12 already has
one); 5, 6, 7 and 8 are specification work in sections that already exist. None requires rethinking
§2 or §4.2.
