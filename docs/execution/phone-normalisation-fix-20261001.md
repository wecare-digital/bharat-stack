# Phone normalisation, session cache headers and a shared-role over-grant — 2026-10-01

Three findings from the 2026-10-01 audit of the customer sign-in and checkout path. Two are fixed
in source and tests here; the third is measured, evidenced and left for owner approval because it
is a production IAM change on a role 62 Lambda functions depend on.

| # | Finding | Status |
|---|---|---|
| 1 | `normalize_phone` prepended the India country code to an already-complete foreign number | ✅ COMPLETE |
| 2 | Session and OTP responses carried no `Cache-Control` | ✅ COMPLETE (two handlers) · ⏳ PENDING (one deployed handler not in this tree) |
| 3 | `wecare-digital-lambda-role` grants `UpdateItem`/`DeleteItem` on the customer session table to 62 functions | ⚠️ NEEDS CONFIRMATION — severity HIGH, **no IAM write attempted** |

**No deploy was performed.** No `update-function-code`, no version publish, no alias move. The live
`wecare-customer-whatsapp-auth` and `wecare-customer-session` functions stay on their current code.
Every AWS interaction recorded here is a read.

**Phone numbers in this document are masked to the last four digits**, per the repo's logging rule.
The complete case tables live in `tests/test_phone_country_code_preservation.py`, where they are test
fixtures rather than a document that gets copied around. Where a digit *count* carries the meaning,
the count is stated instead of the digits.

---

## Finding 1 — the India default was applied to numbers that already had a country code

Commit `456b5716` on `stack`, 7 files, +870/-19. Not pushed.

### What the defect was

`amplify/functions/shared/lambda_utils/identity/customer.py::normalize_phone` stripped every
non-digit — including the `+` — before it did any country-code detection. `_INDIAN_MOBILE_RE`
(`^[6-9]\d{9}$`) then matched any 10-digit string starting 6-9, and `DEFAULT_COUNTRY_CODE = '91'`
was prepended to it. A complete Singapore, New Zealand, Thai or 10-digit UAE number is exactly that
shape.

The consequence is not a cosmetic one. Uniqueness is enforced on the normalised value, so:

1. the OTP went to an unrelated Indian subscriber who never asked for it;
2. the real customer could never sign in, because the number they own was never the number stored;
3. the **wrong identity was reserved** — a `CUS_<ULID>` row and a Cognito username keyed to a
   stranger's number.

It was reachable from shipped UI: `src/lib/dialCodes.ts` offers +65 and ten other codes that each
have a digit count at which the corruption fires.

### Reproduction, before and after (masked)

Measured with `./.venv/bin/python`, `amplify/functions/shared` on the path.

| Input (masked) | Total digits | `normalize_phone` (legacy) | `normalize_phone_preserving_country` (new) |
|---|---:|---|---|
| `+65 ···4567` Singapore | 10 | `+91` + all 10 → **wrong country** | `+65` preserved ✅ |
| `0065 ···4567` Singapore via `00` | 10 | `+91` + all 10 → **wrong country** | `+65` preserved ✅ |
| `+65(····)4567` with separators | 10 | **wrong country** | `+65` preserved ✅ |
| `+64 ···1234` New Zealand | 10 | **wrong country** | `+64` preserved ✅ |
| `+66 ···3456` Thailand | 10 | **wrong country** | `+66` preserved ✅ |
| `+971 ···2345` UAE, 10-digit form | 10 | **wrong country** | `+971` preserved ✅ |
| `+971 ···4567` UAE, 12-digit form | 12 | correct (misses the trap) | correct |
| `+1 ···2671` US | 11 | correct | correct |
| `+44 ···3456` UK | 12 | correct | correct |
| `+91 ···4400` India | 12 | correct | correct |
| `+91 0···4400` India with a trunk zero | 13 | **stuck trunk zero**, 13 digits out | one zero stripped, 12 digits ✅ |
| `0091 ···4400` India via `00` | 12 | correct | correct |
| bare national digits, no code | 10 | silently assumed Indian | **rejected** (`MissingCountryCode`) |
| `0093···4400` read as `00` + country `93` | 10 | assumed Indian | `+93` preserved — **not** `+91` |

The rule is exact: the legacy function corrupts when `len(country_code + national) == 10` and the
first digit is 6-9. `+971` is therefore not "safe"; only its 12-digit spelling is.

Two rows that the plan did not list and are worth recording:

- `normalize_phone` on an Indian number written with a trunk zero leaves the zero stuck, producing
  a 13-digit value. The strict function strips exactly one. Both behaviours are frozen in the
  snapshot test.
- `00` is read as the international prefix per E.123/E.164 even when what follows looks Indian, so
  `0093…` resolves to country code **93**, not 91. Deliberate: inferring otherwise is the defect
  wearing a different coat.

### The fix: additive, never a modification

`normalize_phone` is **byte-identical**. The diff for `customer.py` is `+120 / -0` — zero deleted
lines, which is the strongest available form of "purely additive". It still has eight non-entry-point
callers and its lenient behaviour is correct for them.

Added beside it:

```
class MissingCountryCode(InvalidPhoneNumber)        # -> InvalidPhoneNumber -> ValueError
def normalize_phone_preserving_country(raw) -> str  # returns '+<digits>'
```

Both exported from `__all__`. There is deliberately **no** `default_country` keyword: accepting one
would reopen the inference the function exists to remove.

The order of operations is the whole fix. The `+` / `00` marker decision happens on the trimmed
original text, after a separator-tolerant compaction (`[\s\-().]` only, which matches neither `+`
nor a digit) and **before** any `\D` strip. A wrapper around `normalize_phone` cannot work: by the
time it sees a result, the marker is gone and `0065…` has already been collapsed. `MissingCountryCode`
subclassing `InvalidPhoneNumber` is load-bearing rather than tidy — the existing
`except customer_identity.InvalidPhoneNumber` clauses at the call sites absorb the new rejection with
zero control-flow change.

Validation rules: no leading zero in the remainder (no country code starts with zero); `8 <= digits
<= 15`; a trunk zero stripped **only** for `91`. Every other country gets no trunk handling, because
we do not know their rules. Documented consequence: a UK number written with its trunk zero comes
out with the zero intact and the provider rejects it — a visible failure, which is strictly better
than a silent delivery to a stranger.

### Two implementations, and why the duplication is correct

`amplify/functions/auth/customer-whatsapp-auth/handler.py::_normalise_phone` is an independently
written second copy of the same defect, reached by the sign-in OTP destination, the masked
destination shown to the browser, and the per-phone throttle key.

It **cannot** import the fix. `scripts/deploy_all_lambdas.py:174` declares that function
`standalone=True` and the deployed function has `Layers: null`, so `lambda_utils` is not in its
package. Adding an import would mean a packaging change to a live Cognito trigger. It was therefore
fixed in place, and a drift-agreement test asserts
`trigger._normalise_phone(row) == normalize_phone_preserving_country(row).lstrip('+')` for every row
of the table above. The handler still imports nothing from `lambda_utils`, asserted by an AST test.

The two fixes are **coupled**. The trigger's bug is latent today only because
`_provision_login` writes the already-corrupted value as the Cognito username, so the pool cannot
currently hold a foreign number. Fixing registration alone would make it live.

One deliberate divergence from the plan at that site: the trigger's length bound was widened from
`10 <= digits <= 15` to `8 <= digits <= 15` to match the canonical implementation. A tighter bound at
sign-in than at registration is the same class of harm — a customer could register with an 8 or
9 digit E.164 number and then never be able to sign in. The pool is `AllowAdminCreateUserOnly`, so a
wider accept opens nothing.

### Entry points wired — and the ones deliberately not

Four call sites, all customer-facing doors:

| Wired | Why |
|---|---|
| `identity/registration.py::begin` | where the OTP destination is chosen |
| `identity/registration.py::complete` | where the identity is reserved |
| `auth/customer-whatsapp-auth/handler.py::_normalise_phone` | the sign-in OTP destination (second copy) |
| `auth/email-verification/handler.py` throttle axis | the raw phone was the throttle key |

The email-verification change is a throttle-key normalisation only. One number written spaced and
the same number written unspaced previously got two separate buckets, so respacing bought a fresh
budget — a free evasion of the per-phone limit. It
**never** returns 400 on phone shape — the phone is optional on that endpoint, so an unparseable
value falls back to the normalised email as the throttle subject.

Deliberately untouched: `build_customer`, `validation.py::normalize_phone` and its five messaging
callers, `outbound-whatsapp::_normalize_phone_number`, `sinch_rcs::_normalize_phone`,
`ecommerce/checkout`, `ecommerce/customer_cart`, `ecommerce/initiation`, `identity/address.py`,
`core/crm`. These handle numbers that are already stored or already E.164, or are operator-facing
rather than customer-facing; tightening them would reject existing data without fixing any
misdelivery.

### Contract change at the registration door — flagged, not discovered later

**A bare national number is now refused at the registration and sign-in doors.** This is a behaviour
change, taken deliberately for three checkable reasons: the owner handoff asks for it;
`src/components/PhoneField.tsx` always emits a dial code, so no real UI state produces a bare
number — only a direct API caller does; and the approved copy for the state already exists in
`src/lib/signInMessages.ts::MISSING_CODE`. No `src/` file was edited.

Test coverage moved rather than dropped: the one-counter parametrize kept its three explicit-code
spellings and lost the two bare ones, and a new sibling test asserts those two bare spellings now
return `INVALID_PHONE`, consume no throttle budget, send nothing and write nothing. A matching
HTTP-level test was added at the handler.

---

## Finding 2 — a session or OTP response could be cached and replayed to another customer

### The defect

`lambda_utils/response.py::cors_headers` sets `Content-Type` and three CORS headers and **no**
`Cache-Control`. These responses do not reach the browser directly either: the Amplify `/api/<*>`
rewrite serves them with status 200, so a shared cache sits in front of them.

`customer_session.SessionView.csrf_token` is a per-session secret that a handler returns in a
response **body**. A cache that stored one customer's session response and replayed it to another
would hand over that customer's CSRF token — and that token is precisely what `build_set_cookie`'s
deliberate `SameSite=Lax` choice relies on to guard the mutations Lax still permits. Losing its
secrecy does not weaken the defence, it removes it.

### Fix sites (all owned, all source-only)

| Site | Change |
|---|---|
| `lambda_utils/customer_session.py` | `NO_STORE_HEADERS = {'Cache-Control': 'no-store', 'Pragma': 'no-cache'}` and `harden_session_headers(headers=None)`, both exported from `__all__`, in the existing cookie-assembly section |
| `auth/customer-registration/handler.py` | a local `_no_store()` wrapper applied to **every** return path: `_request`, `_verify`, the handler-level 500, the 502 `send_failed`, and the OPTIONS preflight |
| `auth/email-verification/handler.py` | the same, on all twelve return paths including the `otp_throttle.throttled_response` 429, which is built by `otp_throttle` rather than `cors_response` |

`Pragma: no-cache` is included because that is the pair the repo already emits at
`edge/get-miss-redirect/handler.py:83`; `ai/mcp/handler.py:568` and `core/site-language/handler.py:198`
use `no-store` alone. The stricter existing pattern was copied.

**`lambda_utils/response.py` is unmodified, deliberately.** `core/contacts/handler.py:285` removed
`Cache-Control` there on purpose, so a blanket header in the shared builder would override a
considered decision in an unrelated handler. The contract lives beside the session it protects and
each owning handler opts in. A test pins this: `response.py` must contain no `Cache-Control`.

### Cross-workstream precondition — checked, holds

This change adds **response** headers only. It does not enable `assert_csrf` on any route and adds
no required request header, so `src/pages/cart.tsx` (~line 149) and `src/pages/checkout/status.tsx`
(~line 159), which gate on `getSession()` and send no CSRF header, cannot break. No `src/` file was
modified; `npx tsc --noEmit` is clean and the three UI contract suites pass unchanged.

### ⏳ PENDING — the deployed `wecare-customer-session` handler

`wecare-customer-session` is live on its own role `wecare-customer-sessions-Role-An9RPVcLOdkj`.
**Its handler source does not exist in this tree** — another workstream owns it — so it could not be
fixed here. It is the one handler that will actually return a `csrfToken`, which makes it the highest-
value site for this header.

Exact change required, for whoever owns it:

```python
from lambda_utils.customer_session import harden_session_headers
...
response["headers"] = harden_session_headers(response.get("headers") or {})
```

applied to every return path, including the sign-out and the 503 refresh-unavailable paths. A
forward-looking tripwire in `tests/test_session_response_is_not_cacheable.py` fails the build if any
`amplify/functions/**/handler.py` ever returns a body with a `csrfToken` key without calling
`harden_session_headers`. It matches nothing today, and it has a positive control so it cannot pass
vacuously.

---

## Finding 3 — ⚠️ NEEDS CONFIRMATION (severity HIGH) — shared-role over-grant on the session table

**No IAM write was attempted.** The three commands below are reads. No `put-role-policy`, no
`create-policy`, no `delete-role-policy`.

### Evidence

| Measurement | Result |
|---|---|
| Table | `stack-wecare-digital-CustomerSessionsTable`, **ACTIVE**, HASH `sidHash` |
| Granting policy | inline `wecare-digital-lambda-permissions` on `wecare-digital-lambda-role`, Sid `DynamoDB` |
| Actions granted | GetItem, PutItem, **UpdateItem**, **DeleteItem**, Query, Scan, BatchGetItem, BatchWriteItem, DescribeTable |
| Resource | `arn:aws:dynamodb:us-east-1:775261844268:table/stack-wecare-digital-*` and `…/index/*` |
| Condition | **none** |
| Functions on that role | **62 of 68** |
| Functions referencing the session table | **0** of those 62 |

### Command output, re-measured 2026-10-01 (reads only)

Command 1 — the grant on the shared role:

```
dynamodb:UpdateItem  allowed  role_wecare-digital-lambda-role_wecare-digital-lambda-permissions
dynamodb:DeleteItem  allowed  role_wecare-digital-lambda-role_wecare-digital-lambda-permissions
dynamodb:PutItem     allowed  role_wecare-digital-lambda-role_wecare-digital-lambda-permissions
dynamodb:GetItem     allowed  role_wecare-digital-lambda-role_wecare-digital-lambda-permissions
```

Command 2 — the legitimate custodian's own role, confirming it does not depend on the shared grant:

```
dynamodb:UpdateItem  allowed  role_wecare-customer-sessions-Role-An9RPVcLOdkj_CustomerSessionCustody
dynamodb:DeleteItem  allowed  role_wecare-customer-sessions-Role-An9RPVcLOdkj_CustomerSessionCustody
dynamodb:PutItem     allowed  role_wecare-customer-sessions-Role-An9RPVcLOdkj_CustomerSessionCustody
dynamodb:GetItem     allowed  role_wecare-customer-sessions-Role-An9RPVcLOdkj_CustomerSessionCustody
```

That is the decisive point: `wecare-customer-session` is separately and sufficiently granted by
`CustomerSessionCustody` on its own role, so removing the shared role's path to this table takes
nothing away from the function that legitimately owns the data.

Command 3 — the statement text, `aws iam get-role-policy --role-name wecare-digital-lambda-role
--policy-name wecare-digital-lambda-permissions`, Sid `DynamoDB`, verbatim:

```json
{
  "Sid": "DynamoDB",
  "Effect": "Allow",
  "Action": [
    "dynamodb:GetItem",
    "dynamodb:PutItem",
    "dynamodb:UpdateItem",
    "dynamodb:DeleteItem",
    "dynamodb:Query",
    "dynamodb:Scan",
    "dynamodb:BatchGetItem",
    "dynamodb:BatchWriteItem",
    "dynamodb:DescribeTable"
  ],
  "Resource": [
    "arn:aws:dynamodb:us-east-1:775261844268:table/stack-wecare-digital-*",
    "arn:aws:dynamodb:us-east-1:775261844268:table/stack-wecare-digital-*/index/*"
  ]
}
```

The policy's other statements, untouched and listed for completeness: `CloudWatchLogs`, `S3Access`,
`WhatsApp`, `PinpointSMSVoice`, `SES`, `SQS`, `SNS`, `Bedrock`, `SecretsManager`,
`CloudWatchMetrics`, `Polly`, `HealthAndAdvisor`.

### The item for approval

- **Impact.** 62 functions can delete or rewrite any customer session row. Concretely, a bug or a
  compromise in any one of them could revoke every remembered login, or alter `absoluteExpiresAt`
  and extend a session past the 30-day cap the session module enforces in code — the one rule the
  requirement is explicit about. Session rows hold no token (only a Secrets Manager reference), so
  this is an integrity and availability exposure, not a credential disclosure.
- **Current state.** `allowed` for all four mutating actions from the shared role, with no condition.
- **Desired state.** Only `wecare-customer-sessions-Role-An9RPVcLOdkj` can mutate that table.
- **Measured blast radius of the change: zero.** None of the 62 functions references the table.
- **Recommended option — a NEW inline policy containing an explicit `Deny`.** An explicit Deny
  overrides any Allow, leaves the existing `DynamoDB` statement and the ~61 other tables untouched,
  and is removable in one call.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyCustomerSessionMutationFromSharedRole",
      "Effect": "Deny",
      "Action": [
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:BatchWriteItem"
      ],
      "Resource": [
        "arn:aws:dynamodb:us-east-1:775261844268:table/stack-wecare-digital-CustomerSessionsTable",
        "arn:aws:dynamodb:us-east-1:775261844268:table/stack-wecare-digital-CustomerSessionsTable/index/*"
      ]
    }
  ]
}
```

- **Rejected alternative.** Narrowing the existing `stack-wecare-digital-*` wildcard to an explicit
  table list. It changes the grant for all 62 functions in order to fix one table, and any table
  omitted from the list breaks its function silently at runtime. Not recommended.
- **Rollback.** `aws iam delete-role-policy --role-name wecare-digital-lambda-role --policy-name
  wecare-digital-session-table-deny`. One call, immediate, no data effect.
- **Verification after approval** — the same read used as evidence above, expecting
  `explicitDeny` on the three mutating actions and `allowed` unchanged on `GetItem`:

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::775261844268:role/wecare-digital-lambda-role \
  --action-names dynamodb:UpdateItem dynamodb:DeleteItem dynamodb:PutItem dynamodb:GetItem \
  --resource-arns arn:aws:dynamodb:us-east-1:775261844268:table/stack-wecare-digital-CustomerSessionsTable \
  --output json
```

Awaiting an explicit owner decision. **Not applied.**

---

## Verification

```
./.venv/bin/python -m pytest tests/test_phone_country_code_preservation.py -q     94 passed
./.venv/bin/python -m pytest tests/test_session_response_is_not_cacheable.py -q   21 passed
./.venv/bin/python -m pytest tests/ -q                            5897 passed, 1 skipped
npx tsc --noEmit                                                  clean
npx vitest run SignInMessages / AccountSignIn / CartCheckout       3 files, 40 tests passed
git diff --stat -- src/ amplify/.../lambda_utils/response.py       empty
```

Baseline before this work was 5875 Python tests passing; the measured 93-test
(`test_customer_identity` + `test_customer_session`) group is unchanged.

| Gate | Result |
|---|---|
| Deploy | ➖ NOT REQUIRED — explicitly out of scope; source, tests and this doc only |
| AWS writes | ➖ NOT REQUIRED — three reads, nothing mutated |
| Secrets Manager reads | ➖ NOT REQUIRED — none performed, in any spelling |
| `src/` modified | ➖ NOT REQUIRED — none |
| Finding 3 applied | ⚠️ NEEDS CONFIRMATION — deliberately not applied |

**Overall: ⚠️ COMPLETE WITH IMPROVEMENTS.** Findings 1 and 2 are fixed in source and pinned by
tests. Two items remain outside this task's authority: the `wecare-customer-session` handler's
no-store headers (another workstream's source) and the Finding 3 IAM change (owner approval).
Neither is deployed, because nothing in this change is deployed.

## Related

- `.agents/tasks/phone-normalisation-fix-20261001/plan.md` — the design, the entry-point
  justification and the full test list
- `tests/test_phone_country_code_preservation.py` — the complete case tables, the frozen legacy
  snapshot and the drift-agreement test
- `tests/test_session_response_is_not_cacheable.py` — the per-return-path guard and the `csrfToken`
  tripwire
- `.kiro/steering/lambda-snapstart-deploy.md` — why none of this is live until a version is
  published and the `live` alias moves
