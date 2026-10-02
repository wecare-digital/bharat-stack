# Implementation Plan — phone normalisation fix (2026-10-01)

Branch `stack`. Python is `./.venv/bin/python`. No deploy, no push, no fetch/reset/rebase/stash.
AWS reads only.

---

## 0. What the exploration established (read this before planning anything else)

### 0.1 There are TWO `normalize_phone` functions and only one is defective

The brief's "21 referencing files" conflates them. Measured:

| Function | Contract | Importing files in `amplify/` |
|---|---|---|
| `lambda_utils/identity/customer.py::normalize_phone` | E.164 **with** `+` | **8** — the defective one |
| `lambda_utils/validation.py::normalize_phone` | digits only, **no** `+` | 5 (`contacts`, `sms-aws`, `voice-aws`, `whatsapp-voice`, `inbound-whatsapp-handler`) |

Plus two more private duplicates with unrelated contracts:
`outbound-whatsapp::_normalize_phone_number`, `sinch_rcs::_normalize_phone`.

Only the `identity/customer.py` one is in scope. Its real call sites:

```
identity/registration.py:145   begin()      <- OTP request front door      WIRE
identity/registration.py:217   complete()   <- OTP verify + identity write  WIRE
identity/customer.py:232       build_customer()                            DO NOT WIRE
```

### 0.2 Reproduced live with the real module (`./.venv/bin/python`, `amplify/functions/shared` on path)

```
+6591234567      -> +916591234567    WRONG  Singapore -> India
+65 9123 4567    -> +916591234567    WRONG
+65(9123)4567    -> +916591234567    WRONG
0065 9123 4567   -> +916591234567    WRONG  the `00` path corrupts too
+6421234567      -> +916421234567    WRONG  New Zealand
+6689123456      -> +916689123456    WRONG  Thailand
+9715012345      -> +919715012345    WRONG  10-digit UAE form
+971501234567    -> +971501234567    correct (12 digits, misses the trap)
+14155552671     -> +14155552671     correct
+447911123456    -> +447911123456    correct
+919330994400    -> +919330994400    correct
```

The rule is exact: corruption fires when `len(country_code + national) == 10` **and** the first
digit is 6-9. `+971` is therefore not "safe" — only its 12-digit spelling is.

`0065 9123 4567` is the decisive case for the fix design: the `00` international prefix is
stripped at `customer.py:135` *before* `_INDIAN_MOBILE_RE` runs, so a wrapper that branches on
`+` alone still corrupts it.

### 0.3 It is reachable from the shipped UI

`src/lib/dialCodes.ts` offers **+65 Singapore**, +60, +61, +62, +63, +7, +81, +82, +86, +966,
+971 — every one of those has a digit-count at which it corrupts. This is a live path, not a
hypothetical.

### 0.4 A SECOND independent copy of the same bug, and it cannot import the fix

`amplify/functions/auth/customer-whatsapp-auth/handler.py:172-179`:

```python
def _normalise_phone(phone: str) -> str:
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if len(digits) == 10 and digits[:1] in "6789":
        digits = "91" + digits
```

Same defect, independently written. It is reached by `_send_otp` (the sign-in OTP destination),
`_mask_phone` (the masked destination shown to the browser), and `_consume_send_budget` (the
per-phone throttle key).

**Today it is latent**, because `_provision_login` writes `Username=e164` from the *already
corrupted* value, so the pool cannot currently hold a foreign number. **Fixing registration
without fixing this makes it live**: a correctly-registered Singapore customer's sign-in OTP
would be sent to an unrelated Indian subscriber. The two fixes are coupled and must land
together.

**It cannot import `lambda_utils`.** `scripts/deploy_all_lambdas.py:174` declares it
`standalone=True`, documented as "handler.py only. Used where the handler imports nothing from
lambda_utils", and the deployed function has `Layers: null`. Adding an import would require
changing the deploy map — not an owned path, and a packaging change to a live Cognito trigger.
So the fix is applied **in place**, with a test pinning the two implementations to one shared
case table so they cannot drift.

### 0.5 Finding 2 — the session module has no HTTP response builder, and the deployed handler is not ours

- `lambda_utils/response.py::cors_headers` sets `Content-Type` and three CORS headers. **No
  `Cache-Control`.** `response.py` is NOT an owned path, and `core/contacts/handler.py:285`
  deliberately removed `Cache-Control` — a blanket change there would be wrong.
- `customer_session.py` (committed `5a1f0431`) builds the session row, `SessionView.csrf_token`
  and the `Set-Cookie`. It has no response builder and **no handler imports it**
  (`tests/test_checkout_package_completeness.py:42` records this: "ships ahead").
- `wecare-customer-session` **is deployed** (own role `wecare-customer-sessions-Role-An9RPVcLOdkj`,
  `LastModified 2026-10-01T13:25Z`), but its handler source does not exist in this tree. Another
  workstream owns it. We cannot fix it; we supply the helper and report it.

### 0.6 Finding 3 — measured, live, and confirmed over-granted

| Measurement | Result |
|---|---|
| Table | `stack-wecare-digital-CustomerSessionsTable` **ACTIVE**, HASH `sidHash`, created 2026-10-01T18:54 IST |
| Granting policy | inline `wecare-digital-lambda-permissions` on `wecare-digital-lambda-role`, Sid `DynamoDB` |
| Actions | GetItem, PutItem, **UpdateItem**, **DeleteItem**, Query, Scan, BatchGetItem, BatchWriteItem, DescribeTable |
| Resource | `arn:aws:dynamodb:us-east-1:775261844268:table/stack-wecare-digital-*` and `/index/*` |
| Condition | **none** |
| Functions on that role | **62 of 68** |
| Functions referencing the session table | **0** of those 62 (`wecare-pstn-softphone` -> `PstnSoftphoneSessions`, `wecare-ai-generate-response` -> timeout ints; both unrelated) |

`simulate-principal-policy` returns `allowed` for UpdateItem / DeleteItem / PutItem / GetItem on
the table, matched statement
`role_wecare-digital-lambda-role_wecare-digital-lambda-permissions`.

So the over-grant is real and currently live. Narrowing is **provably unused** but still a
production IAM change on a role 62 functions depend on, so it is an owner-approval report item,
not a change this task applies.

### 0.7 Green baseline, measured now

```
./.venv/bin/python -m pytest tests/test_customer_identity.py tests/test_customer_session.py -q
  -> 93 passed
./.venv/bin/python -m pytest tests/test_registration.py tests/test_customer_registration_handler.py \
     tests/test_customer_whatsapp_auth.py tests/test_email_verification_handler.py -q
  -> 73 passed
```

---

## 1. Design decisions

### 1.1 The additive function

```python
class MissingCountryCode(InvalidPhoneNumber):
    """No explicit country code was supplied, and this entry point will not guess one."""


def normalize_phone_preserving_country(raw: Any) -> str:
    """E.164 that honours the country code the caller actually wrote. Never infers one."""
```

Lives in `identity/customer.py`, added to `__all__`. `normalize_phone` is **not touched**.

**Name.** Says what it guarantees rather than where it is used, so the difference is legible at a
call site sitting next to `normalize_phone`. (The superseded design's `require_explicit_e164`
describes the precondition, not the behaviour, and does not hint that the default country is
suppressed — which is the whole point.)

**`MissingCountryCode` subclasses `InvalidPhoneNumber`, which subclasses `ValueError`.** This is
load-bearing, not tidiness: `registration.begin` and `registration.complete` already wrap the
call in `except customer_identity.InvalidPhoneNumber`, and the trigger's callers already catch
`ValueError`. The new rejection therefore flows into the existing `INVALID_PHONE` outcome and the
existing trigger error paths with **zero handler control-flow changes**.

### 1.2 The no-country-code decision: REJECT

Input carrying no `+` and no `00` raises `MissingCountryCode`.

Three reasons, each checkable:

1. Owner handoff §6 asks for bare national digits to be rejected at the customer entry point.
2. `src/components/PhoneField.tsx` always emits a dial code from `DIAL_CODES`, so no real UI
   state produces a bare national number — only a direct API caller does.
3. The approved copy for this state already exists and is already documented as reachable-by-
   nobody: `src/lib/signInMessages.ts::MISSING_CODE = 'Include your country code, like +91.'`.
   **We do not edit that file** (not owned, and the server change does not make the string
   UI-reachable — PhoneField still always sends a code).

Delegating instead was rejected: delegation leaves the +91 inference live for any non-PhoneField
caller at a customer entry point, which is the defect wearing a wrapper.

### 1.3 The pre-strip branch (the part the superseded design got wrong)

The marker decision happens on the **original trimmed text**, before any `re.sub(r"\D", "", …)`:

```python
text = str(raw or "").strip()
if not text:
    raise InvalidPhoneNumber("phone number is required")

# Separator-tolerant, but NOT digit-stripping: the `+` / `00` must survive this step,
# because re.sub(r"\D","",text) is precisely what destroys it.
compact = re.sub(r"[\s\-().]", "", text)

if compact.startswith("+"):
    rest = compact[1:]
elif compact.startswith("00"):
    rest = compact[2:]
else:
    raise MissingCountryCode("a country code is required; expected +<code> or 00<code>")
```

Then, and only then, `digits = re.sub(r"\D", "", rest)`, with:

- `DEFAULT_COUNTRY_CODE` **never** prepended. `_INDIAN_MOBILE_RE` **never** consulted.
- a leading `0` in `rest` rejected — no country code begins with zero.
- length validated `8 <= len(digits) <= 15` (E.164 max 15; 8 is the shortest real E.164).
- trunk zero handled **only for `91`**: if `digits` starts `91` and the next digit is `0`,
  strip exactly one zero. Every other country gets no trunk handling, because we do not know
  their rules and inventing one is Finding 1 in a new coat. Consequence, deliberate and
  documented: `+44 07911 123456` yields `+4407911123456`, which the provider rejects — a visible
  failure, not a silent misdelivery to a stranger.
- `00` is read as the international prefix per E.123/E.164 even when what follows looks like a
  bare Indian number. `009330994400` therefore yields `+9330994400` (country code 93), **not**
  `+919330994400`. This is a real divergence from `normalize_phone`'s lenient reading and must be
  pinned by a test with the reason in the docstring: reading `00` as "maybe a country code, maybe
  not" is the ambiguity that produced the defect.

### 1.4 Entry points to wire — and why only these

| # | Site | Why |
|---|---|---|
| 1 | `identity/registration.py::begin` | The OTP request door. Raw browser input, and the throttle + challenge are keyed on the normalised value. |
| 2 | `identity/registration.py::complete` | **Reserves the identity.** Writes `normalizedPhone` and `Username=e164` into Cognito. This is where the wrong identity gets locked in. |
| 3 | `auth/customer-whatsapp-auth/handler.py::_normalise_phone` | The sign-in OTP **destination**, the masked destination, and the per-phone send budget. Coupled to #1/#2 per §0.4. Fixed in place (standalone packaging). |
| 4 | `auth/email-verification/handler.py:201` throttle axis | `throttle_subject = str(body.get("phone") or email)` passes the raw phone as a throttle key, so `+65 9123 4567` and `+6591234567` are two buckets (evasion), and under the lenient function they would collapse onto an unrelated Indian number's bucket. |

**Not wired, with the reason:**

- `customer.py::build_customer` — called from CRM/admin paths and from tests with bare Indian
  digits. Changing it changes behaviour for callers that are not customer entry points.
- `validation.py::normalize_phone` + its 5 messaging callers — a **different function** with a
  different contract (digits, no `+`), fed by provider webhooks and stored CRM records, not
  customer free text.
- `outbound-whatsapp::_normalize_phone_number`, `sinch_rcs::_normalize_phone` — outbound send
  side, fed from already-stored records.
- `ecommerce/checkout`, `ecommerce/customer_cart`, `ecommerce/initiation`, `identity/address.py`,
  `core/crm` — all downstream of a resolved customer; they consume an already-normalised value.

### 1.5 Known breaking test change at the registration door (flagged, not discovered later)

`tests/test_registration.py:30` sets `PHONE = '9330994400'` — bare digits — and line 125
parametrizes `test_every_spelling_reaches_one_counter` with `['9330994400', '+919330994400',
'09330994400', '0091 9330994400', '+91 93309 94400']`.

Under decision 1.2 the two bare spellings become rejections. The migration is small because the
suite uses the constant:

- `PHONE` becomes `'+919330994400'`; the `'9000000001'` literals at lines 166, 179, 332 become
  `'+919000000001'`.
- `test_every_spelling_reaches_one_counter` keeps the three explicit-code spellings (all three
  still reach one counter — `0091 9330994400` is handled by the `00` branch) and loses the two
  bare ones.
- A **new sibling test** asserts those two bare spellings now return `INVALID_PHONE` and consume
  no budget, so the removed coverage is replaced rather than dropped.

Do not loosen any existing assertion to make this pass.

### 1.6 Finding 2 response sites

Added to `customer_session.py`, in its existing "cookie assembly" section:

```python
NO_STORE_HEADERS = {"Cache-Control": "no-store", "Pragma": "no-cache"}

def harden_session_headers(headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Merge the no-store pair into `headers`. Mandatory on any response carrying a
    csrfToken, a session id, or a session-bound deadline."""
```

`Pragma: no-cache` is included because that is the pair the repo already uses
(`edge/get-miss-redirect/handler.py:83`); `ai/mcp/handler.py:568` and
`core/site-language/handler.py:198` use `no-store` alone. Matching the stricter existing pattern.

Applied at, all owned:

1. `customer_session.py` — the constant + helper + a docstring paragraph on the CDN reasoning
   (the Amplify `/api/<*>` status-200 rewrite means a shared cache sits in front of these).
2. `auth/customer-registration/handler.py` — every return path (`_request`, `_verify`, the
   `handler` error path, and `options_response`). A local `_reply`-adjacent wrapper that merges
   `NO_STORE_HEADERS` into the `cors_response` result; **do not modify `response.py`**.
3. `auth/email-verification/handler.py` — same treatment on every return path.

Reported, not fixed: the deployed `wecare-customer-session` handler (source not in this tree).
The report names `harden_session_headers` as the exact call to add.

**Cross-workstream precondition — checked, no STOP needed.** `src/pages/cart.tsx:~149` and
`src/pages/checkout/status.tsx:~159` gate on `getSession()` and send no CSRF header. This change
adds **response** headers only; it does not enable `assert_csrf` on any route and adds no required
request header, so neither page can break. If an implementer finds themselves about to call
`assert_csrf` anywhere, that is out of scope: stop and report.

### 1.7 Finding 3 — report only

No IAM write. Produce evidence + the exact proposed statement. Recommended option, for the owner
to approve or refuse: a **new** inline policy on `wecare-digital-lambda-role` containing an
explicit `Deny` on the session table ARN for the four mutating actions. An explicit Deny
overrides any Allow, leaves the existing `DynamoDB` statement and the other ~61 tables untouched,
and measured blast radius is zero (§0.6). The alternative — narrowing the existing
`stack-wecare-digital-*` wildcard — is rejected as a recommendation because it changes the grant
for all 62 functions to fix one table.

---

## 2. Implementation items

- [ ] 1. Add `MissingCountryCode` and `normalize_phone_preserving_country` to
      `amplify/functions/shared/lambda_utils/identity/customer.py`, additively, per §1.1-§1.3.
      Export both from `__all__`. Do not alter `normalize_phone`, `DEFAULT_COUNTRY_CODE`,
      `_INDIAN_MOBILE_RE`, or any existing line. The docstring must state: the reject decision
      and why, the pre-strip branch and why a post-hoc wrapper cannot work, the `91`-only trunk
      rule and the `+44 07911…` consequence, and the `00` reading with the `009330994400` ->
      `+9330994400` example.
      Files: `amplify/functions/shared/lambda_utils/identity/customer.py`
      Verify: `./.venv/bin/python -m pytest tests/test_customer_identity.py -q` — 93 still pass,
      nothing changed yet.

- [ ] 2. Write `tests/test_phone_country_code_preservation.py` covering the full Finding 1 list
      in §3. Must fail against item 1 only where item 3/4/5 are still unwired, and must pass for
      every pure-function case.
      Files: `tests/test_phone_country_code_preservation.py`
      Verify: `./.venv/bin/python -m pytest tests/test_phone_country_code_preservation.py -q` —
      the pure-function classes pass; note which wiring cases are expected-failing.

- [ ] 3. Wire `registration.begin` and `registration.complete` to
      `normalize_phone_preserving_country`. Keep the `except customer_identity.InvalidPhoneNumber`
      clauses exactly as they are (§1.1 is why they still catch). Add a comment at each site
      naming the defect and why this door is strict while `normalize_phone` is not.
      Files: `amplify/functions/shared/lambda_utils/identity/registration.py`
      Verify: `./.venv/bin/python -m pytest tests/test_registration.py -q` — expect the §1.5
      failures and nothing else.

- [ ] 4. Migrate `tests/test_registration.py` and `tests/test_customer_registration_handler.py`
      per §1.5: explicit-E.164 constants, trim the two bare spellings from the one-counter
      parametrize, add the new rejection test. Do not weaken any assertion.
      Files: `tests/test_registration.py`, `tests/test_customer_registration_handler.py`
      Verify: `./.venv/bin/python -m pytest tests/test_registration.py tests/test_customer_registration_handler.py -q`
      — all pass.

- [ ] 5. Fix `_normalise_phone` in `amplify/functions/auth/customer-whatsapp-auth/handler.py`
      **in place**, applying the §1.3 pre-strip branch and returning digits only (no `+`). Keep
      it raising `ValueError`. Add a comment stating the standalone-packaging reason for the
      duplication (`deploy_all_lambdas.py:174`, `Layers: null`) and pointing at
      `normalize_phone_preserving_country` as the canonical implementation. Confirm the handler
      still imports nothing from `lambda_utils`.
      Files: `amplify/functions/auth/customer-whatsapp-auth/handler.py`
      Verify: `./.venv/bin/python -m pytest tests/test_customer_whatsapp_auth.py tests/test_phone_country_code_preservation.py -q`
      — all pass, including the drift-agreement test.

- [ ] 6. Normalise the email-verification throttle axis per §1.4 #4: try
      `normalize_phone_preserving_country(body.get("phone"))` for the throttle subject, fall back
      to the normalised email when it raises, and **never** return 400 on phone shape (the phone
      is optional on that endpoint).
      Files: `amplify/functions/auth/email-verification/handler.py`
      Verify: `./.venv/bin/python -m pytest tests/test_email_verification_handler.py tests/test_phone_country_code_preservation.py -q`
      — all pass.

- [ ] 7. Add `NO_STORE_HEADERS` and `harden_session_headers` to
      `amplify/functions/shared/lambda_utils/customer_session.py` per §1.6, exported from
      `__all__`, with the CDN reasoning in the docstring.
      Files: `amplify/functions/shared/lambda_utils/customer_session.py`
      Verify: `./.venv/bin/python -m pytest tests/test_customer_session.py -q` — all pass.

- [ ] 8. Apply the no-store pair to every response returned by `customer-registration` and
      `email-verification`, via a local wrapper. Do not touch `lambda_utils/response.py`.
      Files: `amplify/functions/auth/customer-registration/handler.py`,
      `amplify/functions/auth/email-verification/handler.py`
      Verify: `./.venv/bin/python -m pytest tests/test_session_response_is_not_cacheable.py tests/test_customer_registration_handler.py tests/test_email_verification_handler.py -q`
      — all pass.

- [ ] 9. Write `tests/test_session_response_is_not_cacheable.py`: `harden_session_headers`
      produces both headers and preserves what it is given; every `customer-registration` and
      `email-verification` return path carries `Cache-Control: no-store`; and a guard asserting
      no response body carrying a `csrfToken` key can be built without the header.
      Files: `tests/test_session_response_is_not_cacheable.py`
      Verify: as item 8.

- [ ] 10. Run the Finding 3 measurements in §4 and capture the output. AWS reads only. No
      `iam put-role-policy`, no `iam create-policy`.
      Files: none (output feeds item 11)
      Verify: the three commands in §4 return `allowed` / the policy document / the function
      inventory, with no write attempted.

- [ ] 11. Write `docs/execution/phone-normalisation-fix-20261001.md` — the one dated doc. Record:
      the Finding 1 reproduction table before and after; the two implementations and why they are
      duplicated; the entry points wired and the ones deliberately not, with reasons; the §1.5
      contract change at the registration door; the Finding 2 sites plus the
      `wecare-customer-session` report item; and Finding 3 as an owner-approval item with the
      §0.6 evidence, the §4 command output, and the proposed Deny statement verbatim. Status
      vocabulary per `maintenance-reporting`. No credential value, no full phone number.
      Files: `docs/execution/phone-normalisation-fix-20261001.md`
      Verify: `./.venv/bin/python -m pytest tests/ -q -k "phone or session or registration or customer_identity or whatsapp_auth or email_verification"`
      — all pass; then the full-suite check in §5.

---

## 3. Required test list — Finding 1

### 3.1 Country code preserved (the reproduction table, inverted)

Every row calls `normalize_phone_preserving_country` and asserts the exact output:

| Input | Expected |
|---|---|
| `+6591234567` | `+6591234567` |
| `+65 9123 4567` | `+6591234567` |
| `+65(9123)4567` | `+6591234567` |
| `  +65-9123-4567  ` | `+6591234567` |
| `0065 9123 4567` | `+6591234567` |
| `+6421234567` | `+6421234567` |
| `+6689123456` | `+6689123456` |
| `+9715012345` | `+9715012345` |
| `+971501234567` | `+971501234567` |
| `+14155552671` | `+14155552671` |
| `+447911123456` | `+447911123456` |
| `+919330994400` | `+919330994400` |
| `0091 9330994400` | `+919330994400` |
| `+91 93309-94400` | `+919330994400` |
| `+91 09330994400` | `+919330994400` (the `91`-only trunk rule) |

Plus an explicit **non-India trunk** row: `+44 07911 123456` -> `+4407911123456`, with the
comment that this is the documented deliberate outcome, not an oversight.

Plus the `00` reading row: `009330994400` -> `+9330994400` (**not** `+919330994400`).

### 3.2 Byte-identical proof for `normalize_phone` (the legacy function, untouched)

A frozen snapshot over the full case table, asserting the exact strings measured in §0.2 and the
existing contract:

```
9330994400      -> +919330994400
09330994400     -> +919330994400
0093309 94400   -> +919330994400
0919330994400   -> +919330994400
+91 93309-94400 -> +919330994400
919330994400    -> +919330994400
+971501234567   -> +971501234567
+14155552671    -> +14155552671
+447911123456   -> +447911123456
+60123456789    -> +60123456789
+81312345678    -> +81312345678
+966512345678   -> +966512345678
```

This test must fail loudly if anyone later edits `normalize_phone`. It deliberately also records
the *corrupting* legacy outputs (`+6591234567 -> +916591234567`, `0065 9123 4567 ->
+916591234567`, `+9715012345 -> +919715012345`) as the documented legacy behaviour, with a
comment that these are why the strict function exists and that the legacy value is retained for
its 8 non-entry-point callers.

### 3.3 No-country-code rejection

`9330994400`, `09330994400`, `93309 94400`, `9000000001`, `''`, `'   '`, `None`, `12`, `abc`
each raise. Assert the exception is `MissingCountryCode` for the bare-digit cases (and that it
`isinstance` of both `InvalidPhoneNumber` and `ValueError`, which is what keeps the existing
handler `except` clauses working).

### 3.4 The anti-delegation test — fails if the function is ever refactored to delegate

```python
def test_the_strict_function_never_routes_through_the_inferring_one(monkeypatch):
    def tripwire(*a, **k):
        raise AssertionError('normalize_phone must not be reachable from the strict path')
    monkeypatch.setattr(customer, 'normalize_phone', tripwire)
    assert customer.normalize_phone_preserving_country('+6591234567') == '+6591234567'
    assert customer.normalize_phone_preserving_country('0065 9123 4567') == '+6591234567'
```

Both inputs are required: the `+` case and the `00` case exercise the two branches a careless
wrapper would collapse.

Secondary structural guard, mirroring `tests/test_payment_vocabulary_at_decision_points.py`'s
AST-walk pattern: parse `customer.py`, locate the `normalize_phone_preserving_country` FunctionDef,
and assert its body contains no `Call` to `normalize_phone` and no reference to
`DEFAULT_COUNTRY_CODE` or `_INDIAN_MOBILE_RE`. Walk the **AST**, not the text, because the
docstring necessarily names all three.

### 3.5 Entry-point wiring

- `registration.begin(raw_phone='+6591234567', …)` -> the injected `send_code` fixture receives
  exactly `+6591234567`; assert `+916591234567` appears nowhere in the fixture's recorded calls.
- `registration.complete(raw_phone='+6591234567', …)` -> the `create_customer` fixture is called
  with `+6591234567`, and the `provision_login` fixture receives `+6591234567` as the username.
  This is the identity-reservation proof.
- `registration.begin(raw_phone='9330994400')` -> `INVALID_PHONE`, no challenge issued, no
  throttle budget consumed (the §1.5 replacement test).
- `registration.begin` with the three explicit-code spellings -> one counter (the preserved half
  of `test_every_spelling_reaches_one_counter`).
- Trigger: `_normalise_phone('+6591234567') == '6591234567'`; `_normalise_phone('+919330994400')
  == '919330994400'`; `_mask_phone('+6591234567')` ends `4567` and contains no `91` prefix.
- **Drift-agreement test:** for every row in §3.1, assert
  `trigger._normalise_phone(row) == module.normalize_phone_preserving_country(row).lstrip('+')`.
  This is what keeps the two implementations from diverging, given they cannot share code.
- email-verification: `+65 9123 4567` and `+6591234567` produce the **same** throttle subject; an
  unparseable phone falls back to the email subject and returns 200/429, never 400.

### 3.6 Secret and log safety

Follow the existing scan pattern at `tests/test_customer_session.py:336`: assert no new logging
expression in the touched files interpolates a phone number, an OTP, or a secret — including
reduced to a boolean or a ternary — and that exception logging uses `type(exc).__name__`. Assert
no full phone number appears in any response body built by the touched handlers.

---

## 4. Finding 3 — the exact commands to run

AWS reads only. All three are read operations; none mutates.

```bash
# 1. The grant, with the statement that produces it. This is the evidence, not policy JSON alone.
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::775261844268:role/wecare-digital-lambda-role \
  --action-names dynamodb:UpdateItem dynamodb:DeleteItem dynamodb:PutItem dynamodb:GetItem \
  --resource-arns arn:aws:dynamodb:us-east-1:775261844268:table/stack-wecare-digital-CustomerSessionsTable \
  --output json

# 2. The same four actions against the session function's OWN role, to show the legitimate
#    custodian is already separately granted and does not depend on the shared role.
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::775261844268:role/wecare-customer-sessions-Role-An9RPVcLOdkj \
  --action-names dynamodb:UpdateItem dynamodb:DeleteItem dynamodb:PutItem dynamodb:GetItem \
  --resource-arns arn:aws:dynamodb:us-east-1:775261844268:table/stack-wecare-digital-CustomerSessionsTable \
  --output json

# 3. The statement text, for the report's proposed-change section.
aws iam get-role-policy --role-name wecare-digital-lambda-role \
  --policy-name wecare-digital-lambda-permissions --output json
```

Expected from (1): four `allowed`, matched statement
`role_wecare-digital-lambda-role_wecare-digital-lambda-permissions` — already measured, re-run to
timestamp it in the doc.

Record in the doc: the 62/68 role count, the zero functions referencing the table, and the
proposed Deny statement verbatim, as
`⚠️ NEEDS CONFIRMATION` with severity `HIGH`, impact, current state, desired state, rollback
(delete the added inline policy), and the simulate command to verify after approval. **Do not
apply it.**

---

## 5. Final verification

```bash
cd /Users/wecaredigital/wecare-store
./.venv/bin/python -m pytest tests/ -q                 # full Python suite
npx tsc --noEmit                                       # no TS touched, but prove it
npx vitest run src/test/SignInMessages.test.tsx src/test/AccountSignIn.test.tsx \
                src/test/CartCheckout.test.tsx          # the UI contract is unregressed
```

No `npm run build` is required: no file under `src/` is modified. If the implementer finds a
reason to touch `src/`, that is a scope change — stop and report.

---

## 6. Constraints restated for the implementer

- No deploy. No `update-function-code`, no version publish, no alias move. The fix is source +
  tests + one doc. `wecare-customer-whatsapp-auth` and `wecare-customer-session` are live and
  stay on their current code.
- No `secretsmanager get-secret-value` / `batch-get-secret-value` in any spelling. Secrets by id,
  read lazily at request time. `customer-registration/handler.py::_pepper()` already does this
  correctly — leave it alone.
- No credential, OTP, or token in a command, argv, log line, or any logging expression — not
  reduced to a boolean or a ternary. CodeQL tracks taint across function boundaries.
- Phone numbers masked to last 4 in logs. Do not widen. `+918100640044` shares last-4 with a
  business number; disambiguate on direction/channel, never on the masked suffix.
- No OTP, message, or call to a real number. Fixtures only. No live-send flag. Do not enable
  `CHECKOUT_INITIATION_ENABLED` or any initiation gate.
- Do not touch Cognito. `UpdateUserPool` is a full replace. If a pool or app-client change looks
  necessary, report it.
- Do not recreate WAF, enable Security Hub, or change DNS/MX/MTA-STS/SPF/DMARC.
- Do not touch: `scripts/provision_checkout.py`, `config/lambda-env-manifest.json`,
  `scripts/probe_url_host_matrix.py`, `docs/execution/url-host-matrix-20261001.md`,
  `tests/test_url_host_routing_rules.py`, `src/pages/404.tsx`, anything under
  `docs/execution/snapshots/`, `scripts/deploy_all_lambdas.py`,
  `amplify/functions/shared/lambda_utils/response.py`, `src/lib/signInMessages.ts`,
  `src/lib/dialCodes.ts`, `src/components/PhoneField.tsx`.
- Git: `git commit --only <paths>` with the paths named. The index is shared with other sessions
  and was dirty at planning time (`order_creation.py`, `checkout.json`,
  `scripts/provision_checkout.py` and two test files all modified by another workstream). `--only`
  is not optional here. Never push.
