# Deep audit (READ-ONLY) — 2026-10-01, second pass

**Produced** 2026-10-01 against AWS account `775261844268` / `us-east-1` and source at
HEAD `8807db0e`. **Re-audit of** `.agents/tasks/section68-current-state-audit-20261001.md`
(produced at HEAD `c082d586`), which was read in full first.

**Changes made: NONE.** No source edit, no stage, no commit, no push, no AWS mutation, no deploy,
no provider/Meta/Razorpay/Wix mutation. Every AWS observation is metadata-only. No
`secretsmanager get-secret-value` / `batch-get-secret-value` in any spelling. No credential on any
command line. No value appears in this file. Working tree and index verified unchanged at the end
(`git diff --cached --name-only` empty; the seven modified and nine untracked paths are another
session's and were left exactly as found).

---

## Summary answer, first

1. **The single most important new finding is live and user-visible: the public cart and sign-in
   pages are serving HTTP 200 while the APIs they call return HTTP 404.** Commits `940a5886` /
   `545bcfcf` shipped `src/pages/cart.tsx` and `src/pages/account/sign-in.tsx`; they are in the
   static build output and live now. `cart.tsx:47` posts to `{API_BASE}/ecommerce/checkout` and
   `sign-in.tsx:44` posts to `{API_BASE}/auth/customer-registration`. Neither route exists among the
   359 live routes, and neither backing Lambda exists. Measured: `/cart/` → 200,
   `/account/sign-in/` → 200, `/api/ecommerce/checkout` → **404**,
   `/api/auth/customer-registration` → **404**. **HIGH.** The prior audit's G1/G2 were latent; they
   are now reachable by a real shopper.

2. **The working tree is red and HEAD is green, and the difference is exactly the in-flight
   payment work.** Working tree: **20 failed, 5550 passed, 1 skipped**. The same suite run against a
   clean export of HEAD `8807db0e`: **5568 passed, 2 failed** — and both of those two are artifacts
   of running outside a git checkout, not defects. So HEAD is effectively green and all 20 failures
   are caused by the uncommitted modifications to `razorpay-webhook/handler.py` +
   `order_creation.py` and the two untracked new modules `finalization.py` / `initiation.py`.
   **HIGH, but it is another session's open work, not a landed regression.**

3. **One of those 20 is the project's own vocabulary gate firing correctly.**
   `tests/test_payment_vocabulary_at_decision_points.py` reports
   `payments/razorpay-webhook/handler.py` line **595** comparing `'captured'` raw, inside the new
   uncommitted `_verify_legacy_invoice_capture`. The same AST walk over HEAD's version of that file
   returns **NONE**. This is precisely the banned literal and the dangerous direction the
   `whatsapp-payments-india-reference` steering describes. **MEDIUM** — the failure mode is
   fail-closed (a `paid` reading would raise `CaptureUnresolved` and leave an invoice unpaid), not
   fail-open.

4. **Build and browser checks are healthy.** `npm run build` exit **0**. Six of seven browser
   checks passed first time; `rtlcheck` exited 1 on a Playwright `page.goto` 60 s timeout at
   `/workspace/seo/blog-production/review/` after 1012 clean routes, and a clean re-run passed
   **7423/7423** over 1241 routes. Flake, not an RTL defect. `tsc --noEmit` clean, `vitest` 586/586.

5. **Nothing in the live footprint moved.** 66 Lambdas (fully paginated), 359 routes, **0**
   authorizers — all identical to the prior audit. The three expected-but-absent functions are
   still absent. `CustomersTable` and `wecare/otp/pepper` still do not exist. The four payment
   tables are still at COUNT 0.

6. **The live-vs-manifest Razorpay MID/UPI disagreement is unchanged.** Live
   `wecare-whatsapp-business-api` still carries `RAZORPAY_MID=[retired Razorpay account]` and
   `RAZORPAY_UPI_ID=[retired UPI VPA]`; the manifest still holds the other pair. Still
   blocked on the owner's provider readback (prior audit item 20-D). **HIGH.**

7. **Of the four "already fixed" payment-path items, three are still fixed and one is being
   actively changed.** `allocate_order_identity` still absent, reference validation still raises,
   the three `ecommerce/checkout` wiring defects all still present verbatim. The fourth —
   no `OrderTable` row from a verified capture — **is still true at HEAD** but is the thing the
   uncommitted `finalization.accept_paid` is written to close.

8. **One genuine improvement since the prior audit:** the deep scanner now reports **0** credential
   occurrences in the working tree (was 1), cleared by `e795f496`. Git history is unchanged at 80
   occurrences across the same six values, correctly not allowlisted.

---

## Evidence, question by question

### Q1 — Git HEAD, origin parity, status, commits since `c082d586`

```
git -C /Users/wecaredigital/wecare-store rev-parse HEAD         8807db0ea5669b298256762f857434060310b136
git -C /Users/wecaredigital/wecare-store rev-parse origin/stack 8807db0ea5669b298256762f857434060310b136
```

Local and `origin/stack` agree; `git status -sb` → `## stack...origin/stack` with no ahead/behind.
**HEAD moved 7 commits since the prior audit** (`git rev-list --count c082d586..HEAD` → 7):

| Commit | Subject |
|---|---|
| `8807db0e` | Merge remote-tracking branch 'origin/stack' into stack |
| `18681011` | Remove retired Wix PSP and Velo payment prototypes |
| `545bcfcf` | Conversations publishing (#165) |
| `ccafcd73` | Phase 1: gate payment.captured side effects on verified reconciliation (C1) + sanitize callback logs (A17) (#164) |
| `940a5886` | Wire /shop/ to the authenticated Cart V2 checkout path (payment stays disabled) (#163) |
| `e795f496` | Record secret exposure on AWS secrets; clear live Plivo credential from working tree |
| `6a5d6e9e` | Fix the sys.modules pollution that failed 281 blog tests in the full suite (#162) |

`git diff --stat c082d586..HEAD` → 38 files, +5823 / −2882. The deletions are the retired
`integrations/wix-psp/` and `integrations/wix-velo-payment/` trees (including the 1756-line
`KIRO-IMPLEMENTATION-PROMPT.md` the prior audit cited at :534-552 and :570-576 — **those citations
no longer resolve**). The additions are `src/lib/cart.ts`, `src/pages/cart.tsx`,
`src/pages/account/sign-in.tsx`, `tests/test_razorpay_webhook_captured_gating.py` (444 lines) and
frontend tests.

`git status --short` at audit time, **untouched** (another session's, per
`multi-session-parallel-agents` rule 4):

```
 M .kiro/specs/whatsapp-wix-commerce/design.md
 M .kiro/specs/whatsapp-wix-commerce/requirements.md
 M .kiro/specs/whatsapp-wix-commerce/tasks.md
 M .kiro/steering/META-BETA-REQUEST-EMAIL.md
 M amplify/functions/payments/razorpay-webhook/handler.py
 M amplify/functions/shared/lambda_utils/ecommerce/order_creation.py
 M docs/execution/change-authority-matrix.md
?? .agents/
?? AGENTS.md
?? amplify/functions/shared/lambda_utils/ecommerce/finalization.py
?? amplify/functions/shared/lambda_utils/ecommerce/initiation.py
?? docs/execution/checkout-c1-c7-closure-matrix-20261001.md
?? docs/execution/checkout-consolidation-findings-20261001.md
?? docs/execution/first-deep-audit-20261001-codex.md
?? docs/execution/webhook-signature-verification-pattern-20261001.md
?? scripts/retired_url_equity.py
```

The index was **clean on arrival and clean on exit** — worth recording explicitly, because
`multi-session-parallel-agents` rule 3b exists because of an index that was already dirty.

### Q2 — Build and browser checks

Node resolved to `/Users/wecaredigital/bin/node`, **v24.21.0**. No nvm involved.

`npm run build`, exit code captured on its own (`echo "BUILD_EXIT=$?"` written to a file by the
build subshell, not chained onto the command):

```
BUILD_EXIT=0
```

Tail of the log: sitemap 1407 URLs (1400/1407 dated, 7 `/shop/*` pages carry no `lastmod` because
git cannot date their source — the build states this rather than inventing a date), blog search
index 1321 posts / 460 kB, `llms.txt` 24 pages + 1321 articles.

| Check | Exit | Tail line |
|---|---:|---|
| `animcheck` | 0 | `18/18 assertions passed` |
| `uicheck` | 0 | `96/96 assertions passed` |
| `typecheck` (browser) | 0 | `3/3 assertions passed` |
| `seocheck` | 0 | `11/11 assertions passed` |
| `translatecheck` | 0 | `PASS - the brand name is protected on every route` |
| `devicecheck` | 0 | `345/345 route×posture combinations clean` |
| `rtlcheck` | **1** | `}` (a dumped `TimeoutError` object) |
| `rtlcheck` **re-run** | **0** | `7423/7423 assertions passed` |

The `rtlcheck` failure in full:

```
page.goto: Timeout 60000ms exceeded.
  - navigating to "http://127.0.0.1:51551/workspace/seo/blog-production/review/", waiting until "load"
    at gotoStable (tools/browser/lib/browser.js:228:26)
    at tools/browser/rtlcheck.js:347:13 { name: 'TimeoutError' }
```

1012 routes had already reported `ok` with `ovf: 0` and `asym: 0`. The immediate clean re-run
covered 1241 routes and 7423 assertions. `grep -c "blog-production/review"` over the
`devicecheck`/`uicheck`/`animcheck` logs returns 0 — that route is only in `rtlcheck`'s (much
larger) route list, so no other check corroborates or contradicts it. Classified **LOW**: a
navigation timeout under back-to-back browser-check load, with the caveat that it is the one route
with no second observer.

Also run, beyond the brief: `npm run typecheck` (`tsc --noEmit`) clean; `npm test` (vitest)
**42 files / 586 tests passed**.

### Q3 — Live Lambda count and the three absent functions

`lambda ListFunctions`, **fully paginated** — `len(Functions)` = **66**, unchanged from the prior
audit. The prior audit's caveat holds and is worth repeating: an un-paginated CLI call returned 50.

| Expected by source | Live |
|---|---|
| `wecare-checkout` | **absent** |
| `wecare-customer-registration` | **absent** |
| `wecare-email-verification` | **absent** |

`ListAliases` across all 66 (sequential batches, **0 errors**): **59** have a `live` alias; the 7
without are exactly the set `lambda-snapstart-deploy.md` names — `wecare-ad-attribution`,
`wecare-docs-scraper`, `wecare-get-miss-redirect`, `wecare-partner-token-refresh`,
`wecare-seo-tools`, `wecare-sla-engine`, `wecare-url-shortener`.

Rollback targets, re-measured (`live` alias → version), unchanged from the prior audit except
`wecare-payments-read` which the prior audit did not list:

| Function | `live` |
|---|---:|
| `wecare-razorpay-webhook` | 45 |
| `wecare-whatsapp-business-api` | 57 |
| `wecare-outbound-whatsapp` | 43 |
| `wecare-inbound-whatsapp` | 66 |
| `wecare-customer-whatsapp-auth` | 10 |
| `wecare-wix-store` | 31 |
| `wecare-invoice-engine` | 39 |
| `wecare-secure-files` | 21 |
| `wecare-payments-read` | 24 |

`SnapStart.ApplyOn = None` / `OptimizationStatus = Off` on every function configuration read.

### Q4 — HTTP API `zllr9lrg7j`

`GetRoutes` with `MaxResults=1000`, `NextToken` **absent** → **359** routes. `GetAuthorizers` →
**0**. Both identical to the prior audit.

Substring sweep over all 359 route keys:

| Substring | Matching routes |
|---|---|
| `ecommerce` | **none** |
| `checkout` | **none** |
| `cart` | **none** |
| `register` | **none** |
| `customer` | `GET /wa-business/flow-customer-journey` only |
| `auth` | `POST /auth/validate` only |
| `wix-store` | `GET /wix-store/{proxy+}`, `POST /wix-store/{proxy+}` |

So the answer to "does any `/checkout`, `/wix-store/cart` or customer-registration route now exist"
is **no**. Cart V2 would reach `wecare-wix-store` through the existing `{proxy+}`, but
`WIX_CART_V2_ENABLED` is **absent** from that function's live env, so `wix-store/handler.py:371`
returns `503 CART_UNAVAILABLE`.

### Q5 — DynamoDB counts (`Scan`, `Select=COUNT`, `ConsistentRead=true`)

| Table | COUNT | Prior audit | Δ |
|---|---:|---:|---|
| `stack-wecare-digital-PaymentsTable` | **0** | 0 | — |
| `stack-wecare-digital-InvoicesTable` | **0** | 0 | — |
| `stack-wecare-digital-OrderTable` | **0** | 0 | — |
| `stack-wecare-digital-WixOrderIds` | **0** | 0 | — |
| `stack-wecare-digital-CustomersTable` | **`ResourceNotFoundException`** | absent | **still absent** |
| `stack-wecare-digital-PaymentAttemptsTable` | 0 | 0 | — |
| `stack-wecare-digital-RazorpayWebhookLogTable` | 154 | 154 | — |
| `stack-wecare-digital-WebhookDedup` | 240 | 230 | +10 (TTL'd lease, expected) |
| `stack-wecare-digital-InvoiceSequenceTable` | 0 | 0 | — |
| `stack-wecare-digital-ContactsTable` | 20 | 19 | +1 |

No money has moved through the commerce path. Every payment-path gap below is **latent**, which is
why none is rated CRITICAL.

### Q6 — Secrets (metadata only)

`ListSecrets --include-planned-deletion` → **32** secrets (prior audit: 31).

`wecare/otp/pepper` — **still does not exist** (`ResourceNotFoundException` on `DescribeSecret`).

| Secret | Stages | Versions | Last changed | Last accessed |
|---|---|---:|---|---|
| `wecare/razorpay/api` | `AWSCURRENT`, `AWSPREVIOUS` | 2 | 2026-09-19 | 2026-10-01 |
| `wecare/razorpay-webhook` | `AWSCURRENT` | 1 | **2026-09-30T22:58:35Z** | 2026-09-30 |
| `wecare/wix/headless-api-key` | `AWSCURRENT` | 1 | 2026-09-26 | 2026-09-30 |

`wecare/razorpay-webhook`'s `LastChangedDate` moved from 2026-07-02 to 2026-09-30 **while
`versionCount` stayed at 1** — so no new secret version was created. The change is metadata: commit
`e795f496` attached exposure tags. Read for the record (tag values, not secret values):

| Secret | `ExposedFields` | `ExposureStatus` | `RotationDue` |
|---|---|---|---|
| `wecare/razorpay-webhook` | `webhook_secret.69blobs` | `git-history-and-working-tree` | `project-close.owner-action` |
| `wecare/plivo` | `auth_token.and.sip_auth_credential_uuid.3blobs` | `git-history-and-working-tree` | `project-close.owner-action` |
| `wecare/plivo/api` | `auth_token.3blobs` | `git-history-and-working-tree` | `project-close.owner-action` |
| `wecare/meta-system-user-token` | `client_token.and.client_token_waba2.1blob` | `git-history-and-working-tree` | `project-close.owner-action` |

This is a real improvement in record-keeping — the exposure is now recorded on the resource itself,
not only in a steering file. One nit: `ExposureStatus` says `git-history-and-working-tree` on all
four, but the scanner now reports working-tree occurrences = **0**. The working-tree half of that
tag is stale. **INFORMATIONAL.**

**Scheduled-deletion set — unchanged, and left alone:** `wecare/airtel-iq`, `wecare/airtel/c2c`,
`wecare/airtel/obd`, `wecare/airtel/sms`, `wecare/sinch/sms`. All five are prohibited-provider
surfaces. Per `01-standing-authorization`, an already-scheduled deletion may complete; none was
cancelled, and no new deletion was scheduled.

**The 32nd secret is new:** `wecare/integrations/owner-input-20261001`, created
2026-10-01T02:33:03Z, tags `Application` / `ManagedBy` / `Purpose`. `scan_repo_secrets.py` reports
it holds **28 fields, 4 credential-classed**. Its value was not read and must not be. Flagged
**INFORMATIONAL** simply because it appeared between the two audits and is not mentioned in any
steering file or spec; if it is the owner's credential-load drop for the Razorpay/Wix items
(prior audit blocker 20-C), that should be written down somewhere, because an undocumented secret
holding four credentials is a secret nobody will remember to retire.

### Q7 — The live-vs-manifest Razorpay MID/UPI disagreement: **still present**

`GetFunctionConfiguration wecare-whatsapp-business-api`, non-secret env keys only:

```
RAZORPAY_MID      [retired Razorpay account]
RAZORPAY_UPI_ID   [retired UPI VPA]
PAYMENT_WABA_ID   2094615664435155
LastModified      2026-09-30T11:02:22.000+0000
```

`config/lambda-env-manifest.json:466-467` still holds `acc_TTFSyolquKEZEy` /
`wecaredigitalbh511413.rzp@rxairtel`. **Unchanged and unresolved.** `LastModified` predates all
seven new commits, so nothing has been pushed to this function's configuration.

Also still live and still unexplained: `wecare-secure-files` carries `WA_PAY_TEMPLATE=wecare_pay`
while the repo's last recorded live template read (`payment_readiness.py:415`, 2026-09-30) says
WABA `2094615664435155` held only `wecare_otp`. **UNVERIFIED** — see the UNVERIFIED table.

### Q8 — The four "already fixed" payment-path items, re-checked at current source

**8a. `allocate_order_identity` — still absent. CONFIRMED.**
`grep -rn 'allocate_order_identity' --include='*.py' --include='*.md' --include='*.ts'` returns no
definition and no call. The only live-code hit is the reverse-direction assertion
`tests/test_order_keys.py:296`: `assert not hasattr(order_keys, 'allocate_order_identity')`.
Remaining hits are prose in `.agents/tasks/*`. Note the prior audit's citation
`integrations/wix-velo-payment/KIRO-IMPLEMENTATION-PROMPT.md:832-838` is **gone** — that tree was
deleted by `18681011`.

**8b. Reference validation raises rather than truncates — still true. CONFIRMED.**
`order_keys.py:190` `def assert_valid_meta_reference_id`. `outbound-whatsapp/handler.py:2834`
`class ReferenceIdTooLong(ValueError)`, raised at **2897** and **2945**; the docstring at **2854**
still records that the function "used to end with `if len(result) > 35: result = result[:35]`".
No `[:35]` slice exists in either handler. `inbound-whatsapp-handler/handler.py:3145` retains
`_sanitize_reference_id` for inbound lookup/display only.

**8c. The paid path creates order IDENTITY but writes no `OrderTable` business row — still true
at HEAD. CONFIRMED, with an important qualifier.**

At HEAD `8807db0e`, `git show HEAD:amplify/functions/payments/razorpay-webhook/handler.py | grep
-n 'ORDERS_TABLE\|OrderTable\|finalization\|accept_paid'` returns **one hit, and it is a comment**
(line 437, "`OrderTable` held zero rows when it was written"). Same for
`order_creation.py` — no `persist_paid`, no `orders` parameter. `OrderTable` COUNT is 0. **G7 is
open at HEAD.**

In the **uncommitted working tree** it is being closed. `handler.py:618` now reads
`orders=dynamodb.Table(os.environ.get('ORDERS_TABLE', 'stack-wecare-digital-OrderTable'))`, passed
to the new untracked `lambda_utils/ecommerce/finalization.accept_paid`, which does
`orders.put_item(Item=order, ConditionExpression='attribute_not_exists(orderId)')` and then stages
`INTERNAL_ORDER_CREATED` on the attempt. `finalization.py` and `initiation.py` are **untracked**
(`git ls-files --error-unmatch` → "did not match any file(s) known to git"), so none of this is
committed, none is deployed, and the 20 test failings in Q2/§Tests all sit inside it.

**8d. The three `ecommerce/checkout` wiring defects — all three still present. CONFIRMED.**

| Defect | Evidence now |
|---|---|
| Readiness asks an unimplemented path | `ecommerce/checkout/handler.py:129` `"path": "/wa-business/payment-config/raw"`. `whatsapp-business-api/handler.py` routes exactly two payment-config branches: `6101 elif '/payment-config/check' in path` and `6119 elif '/payment-config' in path`. There is no `raw` branch. `/payment-config/raw` matches 6119, whose first two lines are `phone_id = params.get('phoneId') or body.get('phoneId')` / `if not phone_id: return _resp(400, {'error': 'phoneId required'})`. Readiness can therefore never reach `PAYMENT_READY`. **HIGH** |
| Checkout V1 vs Cart V2 price authority | `checkout/handler.py:226` `checkout = wix_ecom.create_checkout(line_items)`, `:231` `amount_paise = wix_ecom.authoritative_total_paise(checkout)` — still Checkout V1 (`POST /ecom/v1/checkouts`). `cart_v2.py` / `customer_cart.py` remain the selected model. The new untracked `initiation.py` contains no `create_checkout` / `cart_v2` / `customer_cart` reference, so it does not resolve this. **MEDIUM** |
| Stale live MID | See Q7 — unchanged. **HIGH** |

### Q9 — Secret scanners

Both were feasible. Per `secret-handling`, the deeper scanner is authoritative for the history
verdict and the narrower healthcheck is not.

`.venv/bin/python scripts/scan_repo_secrets.py` (exit 1 = "credential material found", as designed):

```
2. working tree
  1520 file(s) scanned, 0 credential occurrence(s)
3. git history (every blob ever committed)
  LEAK  wecare/meta-system-user-token:client_token          1 blob    d3907404 0a01933d
  LEAK  wecare/meta-system-user-token:client_token_waba2    1 blob    d3907404 0a01933d
  LEAK  wecare/plivo:auth_token                             3 blobs   12c97747 8f2b6823
  LEAK  wecare/plivo:sip_auth_credential_uuid               3 blobs   e795f496 c665c596 12c97747 f2f0a788
  LEAK  wecare/plivo/api:auth_token                         3 blobs   12c97747 8f2b6823
  LEAK  wecare/razorpay-webhook:webhook_secret             69 blobs   adfaaa8c 514ec02c d3907404 fb838fb1 8f4329dd 48959f81 92097f8c
  10113 blobs scanned, 444 MB, 80 credential occurrence(s)
working tree credential occurrences : 0
git history credential occurrences  : 80
issuer-shaped strings in tree       : 2   (both placeholders, neither in Secrets Manager)
```

**Change since the prior audit: working-tree occurrences 1 → 0.** `e795f496` removed the live
`wecare/plivo:sip_auth_credential_uuid` from the committed
`docs/execution/snapshots/plivo-application-before-api-path.json`, and now appears in the
`sip_auth_credential_uuid` commit list as the removing commit. Git history is unchanged at 80
across the same six values, correctly **not** allowlisted. Blob count grew 10,149 → 10,113 in the
scanner's own accounting (443 → 444 MB) — the drop is the deleted `wix-velo-payment` tree no longer
being reachable from any ref the scanner walks for the working-tree phase; the history figure is
the one that matters and is stable.

`.venv/bin/python scripts/txt_source_healthcheck.py` (needs the `.venv` interpreter — system
`python3` has no `boto3`):

```
File exists:   YES (45125 bytes)   Permissions: 600 OK   Owner: wecaredigital expected
Git tracked:   NO (correct)   Inside project dir: NO (correct)   iCloud/Dropbox: NO (correct)
AUTHORIZED RETAINED PLAINTEXT SOURCE : 1
UNEXPECTED PLAINTEXT SECRET COPIES   : 0
SHAPE-ONLY PLACEHOLDER MATCHES       : 7  (not leaks)
REAL VALUES IN GIT OBJECT DATABASE   : 1
```

Synchronization matrix: Razorpay / OpenAI / Google / Plivo all `SYNCHRONIZED`; local and S3
encrypted DR backups `VERIFIED`; final deletion `DEFERRED UNTIL PROJECT-CLOSE CONFIRMATION`. The
retained source is **intentional retention, not a failed task**, per `plaintext-source-policy`.
No value was printed by either tool or by this report.

### Tests — the full picture

Working tree, `.venv/bin/python -m pytest tests/ -q`:

```
20 failed, 5550 passed, 1 skipped in 54.03s
```

Clean export of HEAD (`git archive HEAD | tar -x -C $(mktemp -d)`, run outside the repo, then
removed):

```
2 failed, 5568 passed, 1 skipped in 56.66s
```

Both HEAD failures are export artifacts, not defects:
`test_codeql_triage_classifier.py::TestStalenessGuard::test_an_uncommitted_file_is_stale_regardless_of_commit`
and `test_plivo_control_plane.py::test_snapshot_records_provenance` (`§26 requires git_commit`,
empty because the export is not a git checkout). The focused 14-file payment/commerce subset:
**520 passed, 0 failed at HEAD** vs **500 passed, 20 failed in the working tree**.

The 20, and their single root cause — the uncommitted `_load_attempt` now requires fields the
fixtures do not supply, so every path returns `PROVIDER_UNAVAILABLE`:

```
ERROR order_creation.py:139 {"outcome":"PROVIDER_UNAVAILABLE","reason":"could not load the payment attempt: KeyError"}
ERROR handler.py:493       {"alert":"PAID_BUT_NO_ORDER","outcome":"PROVIDER_UNAVAILABLE",...}
assert result['outcome'] == 'ORDER_CREATED'
E  AssertionError: assert 'PROVIDER_UNAVAILABLE' == 'ORDER_CREATED'
```

| File | Failures |
|---|---:|
| `test_razorpay_webhook_captured_gating.py` | 12 |
| `test_razorpay_webhook_order_creation.py` | 6 |
| `test_order_creation.py::test_reconciliation_cannot_charge_the_customer` | 1 |
| `test_payment_vocabulary_at_decision_points.py` (razorpay-webhook / payment_status) | 1 |

**The direction matters and is reassuring:** every failure lands on
`PROVIDER_UNAVAILABLE` + `needsHuman` + the `PAID_BUT_NO_ORDER` alert. The in-flight code refuses
orders it cannot verify; it does not mint unverified ones. `test_reconciliation_cannot_charge_the_customer`
(the §46 allowlist that proves reconciliation cannot collect money) fails for the same
fixture reason, not because a money-movement call was added — but it is the one failure that should
be re-read carefully before this work lands, because it is the test whose whole job is to notice a
new outbound call.

The raw-literal finding, with both sides measured:

```
working tree, handler.py:595
    if (actual.get('id') != payment_id or actual.get('status') != 'captured'
AST walk over HEAD's copy of the same file
    HEAD offenders: NONE
```

Line 595 sits in the new uncommitted `_verify_legacy_invoice_capture`. Per
`whatsapp-payments-india-reference`, `captured` is banned as a raw literal specifically because
`!= 'captured'` is the comparison that misses `paid`. In practice Razorpay's Payments API reports
`captured` and `paid` is an Order-level word, so a live miss is unlikely — but the gate is a gate,
it is failing, and the fix is one call to `payment_status.canonical()`.

---

## New or changed gaps

Severity per `maintenance-reporting.md`. Nothing is rated CRITICAL: all four payment tables are at
COUNT 0, so no money has moved and every payment-path gap is latent. The one gap that is **not**
latent is N1, because a real visitor can reach it today.

| # | Gap | Severity | Observed | Required |
|---|---|---|---|---|
| **N1** | **Public cart + sign-in pages are live and their APIs 404** | **HIGH** | `/cart/` 200, `/account/sign-in/` 200, `/api/ecommerce/checkout` **404**, `/api/auth/customer-registration` **404**; `cart.tsx:47`, `sign-in.tsx:44`; `out/cart`, `out/account/sign-in` present in the build | Either provision + route the two Lambdas (prior G1/G2), or gate the two pages behind a flag / `noindex` + a plain "not yet available" state until the backend exists. Do not ship a dead button on a commerce page |
| **N2** | Working tree fails 20 tests that pass at HEAD | **HIGH** | 20 failed / 5550 passed vs 5568 passed at HEAD; all 20 in the uncommitted payment path | Owning session completes `finalization.py` / `initiation.py` and updates the fixtures. **Do not commit the tree in this state** — and under rule 3b, whoever commits must use `git commit --only <paths>` because the tree holds three sessions' worth of files |
| **N3** | `handler.py:595` compares `'captured'` raw (uncommitted) | **MEDIUM** | `test_payment_vocabulary_at_decision_points` offender at 595; HEAD clean | Route through `payment_status.canonical()` |
| **N4** | `rtlcheck` timed out once on `/workspace/seo/blog-production/review/` | **LOW** | first run exit 1 at 60 s `page.goto`; re-run 7423/7423 | Watch it. If it recurs, that route is the only one with no second observer in any other check |
| **N5** | New secret `wecare/integrations/owner-input-20261001` is undocumented | **INFORMATIONAL** | created 2026-10-01T02:33Z; 28 fields, 4 credential-classed; no mention in steering or specs | Record what it is and when it retires. Value must not be read |
| **N6** | Exposure tags say `git-history-and-working-tree`; the tree is now clean | **INFORMATIONAL** | scanner: working tree 0 occurrences | Narrow the tag to `git-history` on the four secrets, at the owner's convenience |

### Prior-audit gaps re-checked

| Prior | Status now |
|---|---|
| G1 three functions absent | **unchanged** — and now reachable from a live page (N1) |
| G2 no checkout/cart/registration routes | **unchanged** — 359 routes, zero matches |
| G3 `CustomersTable` absent | **unchanged** |
| G4 `wecare/otp/pepper` absent | **unchanged** |
| G5 `/payment-config/raw` → 400 | **unchanged**, verbatim |
| G6 live MID/VPA stale | **unchanged**; function `LastModified` predates all 7 commits |
| G7 no `OrderTable` row from a verified capture | **still true at HEAD**; being closed in the uncommitted tree |
| G8 checkout prices from Wix V1 | **unchanged** |
| G9 Cart V2 off in production | **unchanged** (`WIX_CART_V2_ENABLED` absent) — intended |
| G10 `custom:customer_id` not on the pool schema | not re-read this pass; no reason to think it moved |
| G11 `wecare_pay` named live but unevidenced at Meta | **unchanged**; still UNVERIFIED |
| G12 `docs/compatibility.md` stale MID/VPA weighting | not re-read; unchanged in `git diff c082d586..HEAD` |
| G13 steering says 361 routes | **unchanged** — `00-current-owner-overrides.md:73,75` still say 361; live is 359 |
| G14 `tasks.md` says the Wix credential does not exist | `tasks.md` is modified in the working tree; the stale claim may be being fixed there. Not asserted either way |
| G15 "12-character" error text | unchanged, cosmetic |
| G16 no per-IP layer in front of public OTP | **unchanged**, and N1 sharpens it: the sign-in page is live, so the first real OTP traffic will arrive before `otp_throttle` has a deployed front door to run in |

### Additional steering drift

| Steering claim | Live | Severity |
|---|---|---|
| `00-current-owner-overrides.md:73,75` — 361 routes / 361 `NONE` | **359 / 359** | LOW |
| `lambda-snapstart-deploy.md:23` — "58 of 65 functions have a `live` alias" | **59 of 66**; the 7-without list is still exactly right | LOW |
| `secret-handling.md:59` — "Working tree, 2026-10-01: `sip_auth_credential_uuid` appears once in `docs/execution/snapshots/plivo-application-before-api-path.json`" | working tree now **0** occurrences; cleared by `e795f496` | LOW |

All three are dated snapshots that the execution rule in `00-current-owner-overrides.md` already
tells readers to re-derive rather than quote, so each is a documentation correction, not a defect.

---

## UNVERIFIED, and the exact read that would close each

| Item | Why it cannot be closed read-only here | The one read that closes it |
|---|---|---|
| Live Meta payment-configuration inventory (the repo's two contradictory 2026-09-30 claims) | Needs the system-user token; a token must never enter a command line | One `payment_readiness.evaluate()` run, or `GET /{waba}/payment_configurations`, executed where the token stays out of argv |
| Whether `wecare_pay` exists and is APPROVED | same | `GET /2094615664435155/message_templates`, same constraint |
| Live WABA / sender health for `+919330994400` | same | `GET /{phone_number_id}?fields=...` |
| Authoritative Razorpay MID and UPI VPA | Only evidence is an owner dashboard readout in `tasks.md`; `payment_readiness` deliberately refuses to pick a winner from a file | Owner reads the gateway MID and VPA off the live configuration, or authorises the Graph read above |
| Which SES DKIM selector is actually signed with | Needs the `s=` value from a real sent message | Read `DKIM-Signature` on one SES-sent message |
| Whether `custom:customer_id` can be added to the customer pool | Not re-read this pass; and any pool write must go through `scripts/cognito_pool_safe_update.py` because `UpdateUserPool` is a full replace | `DescribeUserPool` → `SchemaAttributes` |

---

## Recommendations (nothing implemented)

Ordered by what a real visitor can hit today.

1. **Decide N1 before anything else, because it is the only live-facing gap.** Two honest options:
   provision `wecare-checkout` + `wecare-customer-registration` with their routes (prior G1/G2,
   which also needs G3 `CustomersTable` and G4 `wecare/otp/pepper`, and G4 is owner work); or make
   `/cart/` and `/account/sign-in/` render an explicit "not available yet" state and `noindex` them
   until the backend lands. Shipping the pages ahead of the API is the kind of thing that is
   invisible in CI and obvious to a customer.
2. **Let the owning session finish N2 before any commit touches the tree.** The index is clean
   right now, which is the good case; under rule 3b the commit must still be
   `git commit --only <paths> -F <message-file>` because three sessions' files are present.
3. **Fix N3 while in there** — one `payment_status.canonical()` call at `handler.py:595`.
4. **G5 is ours, not the owner's, and it structurally blocks readiness.** Either add a `raw`
   branch to `whatsapp-business-api` before the `elif '/payment-config' in path` catch-all, or
   point checkout at `/payment-config/check` and parse `gatewayChecks`. Until this is fixed,
   `PAYMENT_READY` is unreachable no matter what the owner confirms about MID or configurations.
5. **G6 still has no safe target.** Do not push the manifest MID/VPA on the strength of a dashboard
   readout. When a readback exists, the push also needs
   `scripts/refresh_secret_consumers.py` + a republish, because a warm sandbox serves the old pair.
6. **Correct the three dated steering counts** (359 routes, 59/66 live aliases, working-tree
   scanner now 0) and narrow the four `ExposureStatus` tags. Low value individually; collectively
   these are what make the next audit cheaper.
7. **Leave the five scheduled secret deletions, the retained plaintext source, and the 80 history
   occurrences exactly as they are.** Rotation is owner-only and deferred to project close, and
   scrubbing history before rotating is theatre.

---

## Method and limitations

**Live reads used, all read-only:** `git rev-parse`, `status --short`, `log`, `diff --stat`,
`show`, `ls-files`, `archive`; `lambda ListFunctions` (paginated), `GetFunctionConfiguration`,
`ListAliases`; `apigatewayv2 GetRoutes` (paginated), `GetAuthorizers`;
`dynamodb Scan (Select=COUNT, ConsistentRead=true)`; `secretsmanager ListSecrets`,
`DescribeSecret`; four unauthenticated `curl -I`-equivalent GETs against the public site.

**Never run:** `secretsmanager get-secret-value` / `batch-get-secret-value` in any spelling; any
Meta Graph, Razorpay, or Wix API call; any Lambda `Invoke`; any write, publish, alias move, or
delete; any `git add` / `commit` / `push` / `stash`. No credential appeared in any command line.
No POST was sent to any endpoint.

**One temporary artifact, outside the repo and removed.** HEAD was exported with
`git archive HEAD | tar -x -C $(mktemp -d /tmp/audit-head.XXXXXX)` so the test suite could be run
against committed source without touching the working tree. `git archive` does not mutate the
repository, the export lived under `/tmp`, and it was deleted (`rm -rf`, verified absent). This is
what makes the "HEAD green / tree red" claim a measurement rather than an inference.

**Historical evidence is labelled as historical.** Where this report cites the prior audit's
figures or a dated reading (the 2026-09-30 zero-configuration probe, the 2026-09-30 template read),
it is cited as a dated reading, not as current live state.
