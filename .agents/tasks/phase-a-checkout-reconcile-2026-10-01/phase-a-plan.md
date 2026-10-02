# Phase A — checkout reconcile: investigation report and implementation plan

**Produced** 2026-09-30T22:46Z → 2026-10-01 (UTC), READ-ONLY. No source, spec, doc, CI or
AWS mutation was made in this step. No secret value was read: every Secrets Manager
observation is `DescribeSecret` metadata, and no credential appears in this file.

**Authority for this phase (owner decision):** Standalone Wix Headless + AWS +
WhatsApp/Razorpay ONLY. Velo, the Wix-native payment-provider plugin, external PSP
onboarding, the `submitEvent` bridge, and any dual-mode / native-vs-headless router are
REMOVED from the active implementation. ONE active design, ONE production checkout path.
This supersedes all earlier dual-mode prompts and the Velo prompt's claim that native
checkout is the new architecture.

**Evidence precedence used throughout:** current provider/AWS read > current source >
dated docs > comments. Historical values are labelled as historical and never presented
as current live state.

---

## 0. ⛔ READ FIRST — a concurrent session is already executing Phase A

Discovered at the end of this investigation, by `git status --short` re-read immediately
before handing off. **This changes who may edit what, and it is the single most important
fact in this document.** Measured, not inferred:

| Evidence | Observation |
|---|---|
| `git status --short` | 3 spec files `M`, `docs/execution/change-authority-matrix.md` `M`, **18 prototype files `D ` — first column, i.e. STAGED** |
| `git diff --numstat` | `design.md` +32/−2, `requirements.md` +1/−1, `tasks.md` +109/−7, `change-authority-matrix.md` +10/−0 |
| `requirements.md:5` now reads | *"Velo and external/native PSP onboarding are **abandoned, not deferred** — one active architecture only; see design.md D8"* |
| New untracked artifacts | `docs/execution/checkout-c1-c7-closure-matrix-20261001.md` (72 lines), `checkout-consolidation-findings-20261001.md` (884 lines), `first-deep-audit-20261001-codex.md` (54), `webhook-signature-verification-pattern-20261001.md` (98) |

So another session has **already** written the owner-decision paragraph, added a `D8`
decision to `design.md`, appended ~109 lines to `tasks.md`, appended a matrix row to
`change-authority-matrix.md`, staged the deletion of both prototype trees, and published
its own **C1–C7 + C3b closure matrix**.

### 0.1 Why this cannot simply be worked around

- **`multi-session-parallel-agents` rule 5:** *a spec belongs to one session.* Driving
  `.kiro/specs/whatsapp-wix-commerce/` from a second session forks the task state. It
  already has: there are now two C1–C7 matrices, this plan's §3 and
  `docs/execution/checkout-c1-c7-closure-matrix-20261001.md`, and they **disagree on phase
  assignment** (see §7.2).
- **Rule 3b, proved twice in this repo and unrepairable:** the index is **already dirty with
  another session's staged deletions**. Any `git commit` from this workflow that is not
  `--only` will absorb all 18 deletions under this phase's message. Both prior occurrences
  were pushed before being noticed and were *not* repaired, because a history rewrite is
  prohibited and the cost exceeded a misleading subject line.
- **`01-standing-authorization`, class `A1_LOCAL`:** the grant is "Always. **Preserve files
  owned by another session**." Every file my §5.3/§5.4 edit plan targets is now owned by that
  session.

### 0.2 What this step therefore did, and did not do

**Did:** all read-only investigation, independently. §1 (re-derived numbers), §2 (dependency
inventory), §3 (C1–C7 location map at `6a5d6e9e`) and §4 (stale-claim map) were produced
from my own AWS reads, greps and file reads *before* the concurrent work was visible, so they
are an **independent second measurement** rather than a restatement. §7 reconciles them
against the concurrent artifacts and finds one concrete citation error worth fixing.

**Did not:** edit, stage, unstage, revert or commit anything outside
`.agents/tasks/phase-a-checkout-reconcile-2026-10-01/`. The staged deletions were left
exactly as found.

### 0.3 The decision only the owner can make

Rule 5's remedy is "resume the owning session instead", and this workflow is not that
session. **§5.3 and §5.4 of this plan must not be executed as written** while that session's
work is uncommitted. §7 gives the non-conflicting alternative. The owner's options are set
out in §7.4.

---

## 1. Re-derived current state

Every row below was measured in this step unless marked UNKNOWN. Dates are UTC.

### 1.1 Git

| Item | Value | How |
|---|---|---|
| `HEAD` | **`6a5d6e9ea6fe0097bf246a34ab6138c6919935d7`** | `git rev-parse HEAD`, 2026-09-30T22:46Z |
| `origin/stack` | **`6a5d6e9ea6fe0097bf246a34ab6138c6919935d7`** | `git rev-parse origin/stack` — local and remote agree |
| Branch | `stack` | single-branch workflow per `git-workflow` steering |
| Subject at HEAD | *"Fix the sys.modules pollution that failed 281 blog tests in the full suite (#162)"* | `git log -1` |

**The two SHAs quoted in earlier prompts are both stale, and the delta matters.**
`c082d586` (the companion audit's HEAD) → `6a5d6e9e` is **one commit touching one file**,
`tests/conftest.py`, +25/−3. Verified with `git log --stat c082d586..HEAD`. So every
*source* observation in `section68-current-state-audit-20261001.md` still holds byte-for-byte
at HEAD, and the line numbers in this plan were re-derived at `6a5d6e9e` regardless.

Working tree at measurement time, left untouched (another session's work, per
`multi-session-parallel-agents` rule 4):

```
 M .kiro/steering/META-BETA-REQUEST-EMAIL.md
?? .agents/
?? scripts/retired_url_equity.py
```

`.agents/` is untracked. Confirm before the first commit whether it is gitignored; if it
is not, the phase artifacts must be added deliberately by explicit path or deliberately
left untracked. Do not resolve this with `git add .`.

### 1.2 AWS — live reads, account `775261844268` / `us-east-1` / profile `wecare-prod`

| Item | Re-derived value | Method / caveat |
|---|---:|---|
| HTTP API routes on `zllr9lrg7j` | **359** | `get-routes --max-results 1000`; `NextToken` **null**, so this is the complete set |
| Routes with `AuthorizationType=NONE` | **359 of 359** | same call, `Items[].AuthorizationType` tallied — a single value, `NONE` |
| API Gateway authorizers | **0** | `get-authorizers`, `length(Items)` |
| Live Lambda functions | **66** | `list-functions`, paginated (`Functions[].FunctionName` counted) |
| — unpaginated same call | 50 then 16 | **Recorded as a trap:** `--query 'length(Functions)'` printed `50` and `16` on two pages. Any Lambda count that does not state it paginated is untrustworthy here |
| `stack-wecare-digital-PaymentAttemptsTable` | **0** | `scan --select COUNT --consistent-read`, `LastEvaluatedKey` null |
| `stack-wecare-digital-PaymentsTable` | **0** | same |
| `stack-wecare-digital-InvoicesTable` | **0** | same |
| `stack-wecare-digital-OrderTable` | **0** | same |
| `stack-wecare-digital-WixOrderIds` | **0** | same — this is the physical commerce-keys table |
| `wecare-checkout` | **ABSENT** (`ResourceNotFoundException`) | `get-function-configuration` |
| `wecare-customer-registration` | **ABSENT** | same |
| `wecare-email-verification` | **ABSENT** | same |
| `wecare-razorpay-webhook` | present | same |
| `wecare-wix-store` | present | same |
| Routes matching `checkout` / `cart` / `registration` | **0** | `get-routes` filtered on `RouteKey` |
| `stack-wecare-digital-CustomersTable` | **ABSENT** | `describe-table` → `ResourceNotFoundException` |
| Secret `wecare/otp/pepper` | **ABSENT** | `describe-secret` → `ResourceNotFoundException` |
| Secret `wecare/wix/headless-api-key` | **PRESENT**, 1 version stage | `describe-secret` metadata only, no value read |

**359 is authoritative and retires 361.** All five payment-path tables are empty, so **no
live-data migration is required and no money has moved through this path** — every
payment-path defect below is latent rather than realised.

### 1.3 Explicitly UNKNOWN — must not be converted into PASS or FAIL

| Item | Why it is UNKNOWN |
|---|---|
| Whether `WECAREDIGITAL` / `WECAREUPI` are presently **Active** at Meta | needs `GET /{waba}/payment_configurations`, which needs the system-user token; a token must never enter a command line (`secret-handling`). Repo holds two contradictory 2026-09-30 claims — `payment_readiness.py` records HTTP 200 / **zero** configurations, `tasks.md:17-28` records the owner restoring four Active. Neither was re-probed here |
| Authoritative Razorpay **MID** | only evidence is an owner dashboard readout. Provider readback required. See §4 |
| Authoritative **UPI VPA** | same |
| Whether `wecare_pay` exists/APPROVED at Meta | needs a live template read. `payment_readiness.py:415` records the WABA holding only `wecare_otp` on 2026-09-30, while `wecare-secure-files` carries `WA_PAY_TEMPLATE=wecare_pay` live |
| Live WABA / sender health | Meta Graph read, same token constraint |
| Whether Meta's `provider_mid` semantics equal the Razorpay `account_id` seen in webhooks | **owner-blocked.** Do NOT assert these are the same field without a provider readback |
| Wix site/dashboard state beyond `WIX_SITE_ID` | needs an authenticated Wix dashboard |

### 1.4 Reconciliation with the companion audit

`/Users/wecaredigital/wecare-store/.agents/tasks/section68-current-state-audit-20261001.md`
was read in full. It **corroborates** every number I re-derived: 359 routes / 359 `NONE` /
0 authorizers, 66 Lambdas (with the same pagination warning), all five tables at zero, the
three absent front-door functions, absent `CustomersTable`, absent `wecare/otp/pepper`,
present `wecare/wix/headless-api-key`. **No disagreement found.** Where it and this plan
differ it is only in HEAD (`c082d586` vs `6a5d6e9e`, one test-only commit apart). Its `G1`–`G16`
gap list and `A`–`E` owner-blocker list are treated as corroborating input, not as authority;
my re-derived numbers govern.

---

## 2. Dependency inventory for prototype retirement

### 2.1 The two trees

| Tree | Tracked files | Package name | Test command | CI coverage |
|---|---:|---|---|---|
| `integrations/wix-velo-payment` | **14** | `wecare-wix-velo-handoff` (private, `type: module`) | `node --test tests/*.test.js` → **42 pass** (re-run in this step) | **none** |
| `integrations/wix-psp` | **4** | `wecare-wix-psp-auth` (private, `type: module`) | `node --test tests/*.test.js` → **16 pass** (re-run in this step) | **none** |

File list, from `git ls-files integrations/`:

```
integrations/wix-psp/README.md
integrations/wix-psp/package.json
integrations/wix-psp/request-auth.js
integrations/wix-psp/tests/request-auth.test.js
integrations/wix-velo-payment/DEPLOYMENT-STATUS.md
integrations/wix-velo-payment/INSTALLATION.md
integrations/wix-velo-payment/KIRO-IMPLEMENTATION-PROMPT.md
integrations/wix-velo-payment/TEST-RESULTS.txt
integrations/wix-velo-payment/backend/http-functions.js
integrations/wix-velo-payment/backend/wecare/core.js
integrations/wix-velo-payment/backend/wecare/notifications.js
integrations/wix-velo-payment/backend/wecare/runtime.js
integrations/wix-velo-payment/backend/wecare/security.js
integrations/wix-velo-payment/package.json
integrations/wix-velo-payment/tests/adapter.test.js
integrations/wix-velo-payment/tests/notifications.test.js
integrations/wix-velo-payment/velo-service-plugin/wecare-config.js
integrations/wix-velo-payment/velo-service-plugin/wecare.js
```

### 2.2 Proof that nothing deployed imports them — by grep, not git history

| Probe | Result |
|---|---|
| `git grep -F 'wix-velo-payment'` outside `integrations/` | **2 hits, both documentation** (`docs/execution/change-authority-matrix.md:531,534`) |
| `git grep -F 'wix-psp'` outside `integrations/` | **0 hits** |
| `git grep -F 'WIX_NATIVE_PROVIDER'` tree-wide | **0 hits** — the token does not exist in this repo at all |
| `git grep -F 'submitEvent'` outside `integrations/` | **0 hits** (the only use is `integrations/wix-velo-payment/backend/http-functions.js:8`) |
| `git grep -F 'native-mode' / 'NATIVE_MODE' / 'nativeCheckout'` tree-wide | **0 hits** |
| `git grep -F 'wix_psp' / 'wix_velo'` tree-wide | **0 hits** |
| `git grep -F 'CHECKOUT_MODE'` | **3 hits, all headless** — `ecommerce/checkout/handler.py:75` (`CHECKOUT_MODE = "WIX_HEADLESS"`), `:261`, `:275`. This is C2's provenance field, not a mode router |
| `git grep 'integrations' -- .github/` | **0 hits** — no CI job references the directory |
| `git grep 'integrations' -- scripts/deploy_all_lambdas.py` | **0 hits** — not in the deploy map (`SPECS`) |
| `grep 'WIX_NATIVE\|VELO\|PSP\|SUBMIT_EVENT' config/lambda-env-manifest.json` | **0 hits** — no env key |
| `package.json` `workspaces` | **`None`** — the two packages are not npm workspaces; nothing installs or builds them |
| `vitest.config.ts` `include` | `[ 'src/**/*.{test,spec}.{ts,tsx}' ]` — **the 58 node tests are invisible to `npm test`** |
| `pytest.ini` `testpaths` | `tests`, `amplify/functions` — no Python touches `integrations/` |
| `scripts/check-provider-policy.sh` `SCAN_DIRS` | `amplify/functions`, `src` only (lines 53-56) — the provider-policy gate does not scan `integrations/` |

**Conclusion: zero deployed consumers, zero CI consumers, zero env keys, zero UI entries.**
Retirement is a pure deletion plus two documentation edits.

### 2.3 Two non-obvious couplings found — neither blocks removal, both must be stated

1. **ESLint DOES lint these files.** `eslint.config.mjs` does not ignore `integrations/`, and
   `npx eslint integrations` was run in this step: **0 problems**. So the files are currently
   clean under the repo linter and deletion cannot break `npm run lint`.
2. **CodeQL DOES scan these files.** `.github/workflows/codeql.yml` analyses
   `javascript-typescript` repository-wide with `build-mode: none`. `eslint.config.mjs` carries
   an explicit, load-bearing warning about exactly this case: a previously vendored Wix
   headless example tree was ESLint/tsc-excluded but *still* raised a high-severity CodeQL
   alert that blocked a PR on code nobody built. Deleting these files therefore **reduces**
   scan surface — the opposite of a risk — but do not re-add a blanket ignore for any future
   reference tree.

### 2.4 Per-match classification

| # | Match | file:line | Class | Action |
|---|---|---|---|---|
| D1 | The 14 Velo files | `integrations/wix-velo-payment/**` | **obsolete instruction/code** | **REMOVE.** `git rm` the whole directory |
| D2 | The 4 PSP files | `integrations/wix-psp/**` | **obsolete instruction/code** | **REMOVE.** `git rm` the whole directory |
| D3 | *"Target: integrations/wix-velo-payment (new isolated source package)"* | `docs/execution/change-authority-matrix.md:531` | **evidence — legitimate audit record** | **KEEP.** Append a new dated retirement row; never edit or delete a historical matrix row |
| D4 | *"Rollback: remove only the newly added integrations/wix-velo-payment directory…"* | `docs/execution/change-authority-matrix.md:534` | **evidence** | **KEEP** (same reason). Note the irony worth recording: this line is the retirement's own pre-authorised rollback |
| D5 | *"2026-10-01 A2_REMOTE_CODE … Package tests: 42 passed …"* | `docs/execution/change-authority-matrix.md:536` | **evidence** | **KEEP** |
| D6 | *"external PSP Digest authentication module and 16 offline tests; onboarding eligibility explicitly unresolved…"* | `docs/execution/change-authority-matrix.md:538` | **evidence** | **KEEP** |
| D7 | *"Velo and external PSP onboarding are not dependencies"* | `.kiro/specs/whatsapp-wix-commerce/{requirements,design,tasks}.md:5` | **active consumer — understated** | **UPDATE.** "not dependencies" is weaker than the owner decision. Must read: removed from the active implementation, and the prototype source is deleted. See §5 FEAT-001 |
| D8 | *"The Velo and external PSP prototypes are inactive and are not deployment dependencies."* | `docs/execution/headless-checkout-20261001.md:3` | **active consumer** | **UPDATE** to past tense with the retirement date, since the prototypes will no longer exist |
| D9 | *"posture as the Velo adapter's `initiationEnabled=false`"* | `amplify/functions/ecommerce/checkout/handler.py:38` | **active consumer — dangling analogy** | **UPDATE.** A comment in deployed-path source that points at a deleted tree. Rewrite to state the posture directly without naming the adapter |
| D10 | *"Headless WhatsApp/Razorpay, not the (set-aside) Velo provider."* | `amplify/functions/ecommerce/checkout/handler.py:74` | **active consumer** | **UPDATE.** "set-aside" becomes "removed"; keep the sentence's real job, which is explaining why `checkoutMode` exists |
| D11 | *"No Wix Editor or Velo runtime is required."* | `amplify/functions/ecommerce/wix-store/handler.py:9` | **unrelated legitimate statement** | **KEEP.** A true statement about the headless adapter; does not reference the prototype |
| D12 | *"the Velo widget…"* | `amplify/functions/core/site-language/handler.py:372` | **unrelated** | **KEEP.** About HTML escaping in a translation widget |
| D13 | Velo/Wix-site reconciliation rows | `bw-crm.md:913,1226,1261,1282,1745,1761,1878,1901,2003,2044,2101,2155` | **historical master-prompt prose** | **KEEP, and see §4 item S9.** `bw-crm.md` is the master prompt; do not rewrite it in this phase. Its Velo-reconciliation instructions are superseded but it is not always-on injected |
| D14 | *"Wix-generated communication … and Velo source drift"* | `.kiro/work/phases-5-10/plan.md:637` | **historical plan** | **KEEP.** A completed fleet-lead plan; an artifact of a past run |
| D15 | *"a different PSP handle"* | `amplify/functions/messaging/whatsapp-business-api/handler.py:3166` | **unrelated** | **KEEP.** "PSP handle" here means the UPI VPA suffix, nothing to do with the Wix PSP path |
| D16 | *"different PSP suffix"* | `docs/compatibility.md:89` | **unrelated** (same sense) | **KEEP** (but see S5/S6 — that file needs date-labelling for other reasons) |
| D17 | `"psp"` in the redaction key list | `amplify/functions/shared/lambda_utils/payment_status.py:393` | **unrelated, security-relevant** | **KEEP.** It is an `entity_summary` exclusion key |
| D18 | `docs/deleted-routes-*.json`, `docs/retirement-exports/*`, `snapshots/apigw-*` containing `integrations/<id>` | various | **unrelated — false positives** | **KEEP.** `integrations/<id>` is API Gateway's *integration target* syntax, not this directory |

### 2.5 Reusable utilities living only inside these trees

I inspected every source file. **Nothing requires extraction, and that conclusion is
deliberate rather than convenient** — three of the four candidates already have a stronger
twin inside `lambda_utils`:

| Candidate | Lives at | Verdict | Reason |
|---|---|---|---|
| `paise(value)` — integer minor-unit validator | `wix-velo-payment/backend/wecare/core.js:8` | **DO NOT extract** | `lambda_utils/ecommerce/money.positive_paise` already does this, is stricter (rejects `float`/`bool`/`str`, accepts DynamoDB `Decimal` without rounding) and is test-pinned by `test_order_creation.py`. Porting JS would create a second money authority, which R6.1 exists to prevent |
| `identifier(value)` — `^[A-Za-z0-9_.:-]{1,160}$` | `core.js:5` | **DO NOT extract** | `order_keys.assert_valid_meta_reference_id` (`^[A-Za-z0-9._-]{1,35}$`, raises) is the repo's identifier authority and is narrower on purpose — Meta's limit is 35. A 160-char validator would be a regression |
| `verifyNotification` — HMAC-SHA256 + 300 s window + `timingSafeEqual` | `backend/wecare/security.js:3` | **DO NOT extract** | The Python fleet already does raw-body HMAC with timing-safe comparison on the Razorpay and Meta webhooks (`razorpay-webhook.handler` verifies before anything else). This is a JS reimplementation of a solved problem |
| `verifyWixRequest` — Wix PSP Digest JWT, RS256, operator-pinned public key | `wix-psp/request-auth.js:6` | **DO NOT extract** | It verifies requests *from Wix's PSP platform*, which the owner decision removes. It has no consumer in a headless architecture. Genuinely well-built (raw-body-before-parse, never trusts the JWT header's key) — record that in the cleanup manifest so its quality is not the reason someone resurrects it |
| `notificationHandler` / `runtime` / `wecare.js` / `wecare-config.js` / `http-functions.js` | Velo tree | **DO NOT extract** | All four import Wix-runtime-only modules (`wix-secrets-backend.v2`, `wix-auth`, `wix-fetch`, `wix-http-functions`, `wix-payment-provider-backend`). They cannot execute outside a Velo site |

**Net: no file moves to `amplify/functions/shared/lambda_utils/` before deletion.** The
cleanup manifest must state that explicitly with these reasons, so the absence of an
extraction step reads as a decision rather than an omission.

### 2.6 What deletion costs

- **58 passing offline node tests** (42 + 16), re-run in this step. They were never in CI
  (`vitest.config.ts` includes `src/**` only; no workflow runs `node --test`). Record the
  final pass counts in the cleanup manifest as the last measurement before removal.
- **`KIRO-IMPLEMENTATION-PROMPT.md` is the source of the stale-claims checklist**
  (lines 1500-1516) and of the C1-C7 conflict statements (534-576, 832-838, 1417, 1509-1511,
  1579). Its content must be migrated into the canonical spec + this plan's §3/§4 **before**
  the file is deleted. That ordering is why FEAT-001 precedes FEAT-002 in §5.
- **Rollback** is `git revert` of the deletion commit. The trees are in history at `acdad528`
  (Velo) and `aaddd882` (PSP). No history rewrite — prohibited.

### 2.7 Superseded master prompt / duplicate plan carrying an always-on inclusion

Measured: front matter of all 21 files in `.kiro/steering/`.

**Always-on** (`inclusion: always`, or no key at all): `00-current-owner-overrides.md`,
`01-standing-authorization.md`, `02-qa-recipient.md`, `aws-agent-rules.md`,
`blog-production-s3.md`, `email-auth-dns.md`, `git-workflow.md`,
`lambda-snapstart-deploy.md`, `maintenance-reporting.md`,
`multi-session-parallel-agents.md` (**no inclusion key — defaults to always**),
`plaintext-source-policy.md`, `secret-handling.md`,
`whatsapp-payments-india-reference.md`.
**Conditional:** `03-sinch-rcs-india-only.md` (`auto`), `grahak-os-design.md` (`fileMatch`).
**Manual:** `AIRTEL-IQ-SMS-REPLY-EMAIL.md`, `FLOW-MANAGEMENT-ARCHITECTURE.md`,
`META-BETA-REQUEST-EMAIL.md`, `PAYMENT-AUDIT-REPORT.md`, `whatsapp-groups-reference.md`.

**Finding: no superseded master prompt or duplicate plan is itself always-on.** The Velo
prompt is not steering; `bw-crm.md` and `PAYMENT-AUDIT-REPORT.md` are not injected. Three
things are still worth flagging, and none of them is "delete a steering file":

| Flag | Detail | Recommended action in this phase |
|---|---|---|
| F1 | `bw-crm.md` (2,217 lines, repo root) is **authoritative by reference from always-on steering** — `00-current-owner-overrides.md:7` says it overrides it, `maintenance-reporting.md` cites "master-prompt sections 81-104". It carries dated Velo-reconciliation instructions (D13) and the `acc_TTFSyolquKEZEy` / MCC-purpose rows (`:212,213,1164,1165`) | **Do not rewrite.** Add one dated note to the decision record stating that `bw-crm.md`'s Velo/native-checkout reconciliation instructions are superseded by the 2026-10-01 owner decision, and that its provider rows are historical. Editing the master prompt is out of scope for Phase A |
| F2 | `00-current-owner-overrides.md:73,75` states **361** routes in both rows. The same file's execution rule says "Do NOT trust dated AWS/GitHub counts" and "Do not quote counts from this file" | **Correct to 359 with the measurement date**, keeping the drift table's shape. This is the one always-on file carrying a number this phase re-derived. Low severity, high blast radius, because it is injected into every session |
| F3 | `docs/tasks.md` is a **second, competing tasks document** with its own authority table naming `docs/spec.md` as "authoritative requirements (`FR-*`, `TR-*`)" and three session owners — while `.kiro/specs/whatsapp-wix-commerce/` is the canonical spec this phase edits | **Add one authority pointer** at the top of `docs/tasks.md` naming `.kiro/specs/whatsapp-wix-commerce/` as canonical for the checkout path, so a reader cannot pick the wrong plan. Do not delete it; it holds live status rows (e.g. `:66`, see S8) |

---

## 3. C1–C7 location map — current tree at `6a5d6e9e`

Every file:line below was re-derived in this step. The brief's line numbers came from an
older SHA and are superseded by these. **No fix is implemented here.** "Closing phase" is
the phase that lands the fix; Phase A only records, reconciles the spec, and removes the
prototypes.

### C1 — the reconciliation result is computed and then ignored

| | |
|---|---|
| Site | `amplify/functions/payments/razorpay-webhook/handler.py` |
| Definition | `_create_order_for_captured_payment` at **:431**; `_load_attempt` at **:460**; `order_creation.reconcile_payment` call at **:476**; result logged at **:485**; `PAID_BUT_NO_ORDER` ERROR at **:499**; `return outcome.as_dict()` at **:503** |
| The defect | **:664** — `_create_order_for_captured_payment(payment, reference_id, request_id)`. The return value is **discarded**. Execution then continues unconditionally: `_mark_invoice_paid_by_reference` **:668** (else `_mark_invoice_paid_by_phone_and_amount` **:673**), `_post_payment_handler` **:676** (GST invoice + image + WhatsApp send), `_log_ctwa_purchase` **:681** (Meta Conversions Purchase), and the `order_status` customer message from **:683** onward |
| Why it matters | The function's own docstring (**:431-447**) says it deliberately does not perform downstream side effects "which are separately guarded so that a failure in the last one does not re-run the first". At **:664** nothing reads `has_order` / `needs_human` / `outcome`, so a `PAID_BUT_NO_ORDER` still produces a GST invoice, a Purchase conversion and an `order_status` message telling the customer about an order that does not exist. The guard exists; nothing consults it |
| Also note | `_handle_payment_captured` (**:574**) short-circuits before all of this for `notes.purpose == 'wallet_topup'` and `'secure_file_download'`. Those returns are correct and must not be disturbed |
| Required fix | Bind the outcome (`outcome = _create_order_for_captured_payment(...)`) and branch on it. On `needs_human` the downstream side effects must not claim an order: no customer-facing "order confirmed" message, no Purchase conversion keyed to a nonexistent order. Invoice-only flows (no `PAYREF#` row → `outcome` is a documented no-op) must keep behaving exactly as today — `test_a_payment_with_no_attempt_creates_nothing_and_does_not_error` pins that and must stay green |
| Closing phase | **Phase C** (payment-path correctness) |

### C2 — contradictory native-vs-headless plans

| | |
|---|---|
| Sites | `.kiro/specs/whatsapp-wix-commerce/requirements.md:5`, `design.md:5`, `tasks.md:5` (identical paragraph: *"Velo and external PSP onboarding are not dependencies"*) |
| | `integrations/wix-velo-payment/KIRO-IMPLEMENTATION-PROMPT.md` — the "supersedes" claim, plus its conflict statements at **:534-552** (MID), **:570-576** (VPA), **:832-838** (`allocate_order_identity`), **:1417**, **:1509-1511**, **:1579** |
| | `integrations/wix-velo-payment/DEPLOYMENT-STATUS.md:21` — asserts the MID correction is *reversed* relative to `payment_readiness.py` |
| | `integrations/wix-psp/README.md` — the external-PSP onboarding path, eligibility explicitly unknown |
| | `docs/execution/headless-checkout-20261001.md:3` |
| | `amplify/functions/ecommerce/checkout/handler.py:38` and **:74** (comments referencing the Velo adapter) |
| Withdrawn | The Velo prompt's `WIX_NATIVE_PROVIDER` "supersedes" claim. **The token `WIX_NATIVE_PROVIDER` does not exist anywhere in the tree** (0 grep hits) — the claim was never implemented, only asserted |
| `WIX_HEADLESS` stays | `amplify/functions/ecommerce/checkout/handler.py:75` `CHECKOUT_MODE = "WIX_HEADLESS"`, written to the `PAYREF#` row at **:261** and to the attempt at **:275**. Keep it as an **immutable provenance field** — it records which flow created a row, which is exactly what makes a later audit possible. It is **not** a mode switch: there is no second value and no router reads it |
| Required fix | One active design. Strengthen the three spec paragraphs from "not dependencies" to "removed from the active implementation, prototype source deleted, single production checkout path". Delete the prototype trees. Rewrite the two `checkout/handler.py` comments so deployed source stops referring to a deleted tree |
| Closing phase | **Phase A** (this phase) |

### C3 — checkout calls a route that does not exist

| | |
|---|---|
| Caller | `amplify/functions/ecommerce/checkout/handler.py:355` `def _send_order_details`, invoked at **:301**; the path is set at **:367** — `"/wa-business/messages/send/interactive-payment"` |
| Dispatcher | `amplify/functions/messaging/whatsapp-business-api/handler.py:5799` routes `'/messages/send/' in path` into `_route_send_message` at **:2179** |
| The 404 | `_route_send_message` handles exactly: `/text` (:2181), `/template` (:2183), `/media` (:2185), `/interactive` (:2187), `/flow` (:2189), `[retired public path 44011e36]` (:2191), `/location` (:2193), `/product`\|`/products` (:2195), `/request-contact-info` (:2197). There is **no `interactive-payment` branch**, so it falls to **:2199** — `return _resp(404, {'error': f'Unknown send path: {path}'})` |
| Consequence | `_send_order_details` reads `statusCode` and returns `False` for any `>= 300`, so the send silently fails and the attempt never reaches `PAYMENT_REQUEST_SENT` (`_mark_request_sent`, **:394**). Latent only because `CHECKOUT_INITIATION_ENABLED` is off by default and `wecare-checkout` is not deployed |
| Note the near-miss | `/interactive` **does** exist and would match a naive `endswith` change — do not "fix" this by loosening the matcher, or an `interactive-payment` body would be dispatched to the generic pass-through builder |
| Where the real builder lives | `amplify/functions/messaging/outbound-whatsapp/handler.py:418` `_build_payment_settings`. Spec task 9.4 requires reusing it. `whatsapp-business-api` owns the inbound decrypted `order_details` flow (`:4349`, `:4665-4768`) but not an outbound `order_details` send on this path |
| Required fix | Decide **one** owner for the outbound `order_details` send and make the caller and the dispatcher agree. Either add an `interactive-payment` branch to `_route_send_message` that delegates to the existing `_build_payment_settings` path, or repoint `_send_order_details` at whatever route already reaches it. Do not reimplement `_build_payment_settings` (R: spec 9.4) |
| Closing phase | **Phase B** (wiring the front door) |

### C4 — `razorpay_verify` requires a binding that initiation never persists

| | |
|---|---|
| Verifier | `amplify/functions/shared/lambda_utils/integrations/razorpay_verify.py:159` `verifier_for_event`. Inside `verify`: **:175** reads `attempt['providerPaymentId']`, **:176** reads `attempt['providerOrderId']`, **:177-178** `if not bound_payment and not bound_order: raise RazorpayUnavailable("payment attempt has no verified provider binding")` |
| Loader | `amplify/functions/payments/razorpay-webhook/handler.py:460` `_load_attempt` projects exactly six fields off the `PAYREF#` row, including `providerPaymentId` (**:469**) and `providerOrderId` (**:470**) |
| Initiation | `amplify/functions/ecommerce/checkout/handler.py:257` `order_keys.allocate_payment_reference(..., extra={...})` — the `extra` dict at **:259-262** carries `customerId`, `amountPaise`, `currency`, `wixCheckoutId`, `checkoutMode`. **Neither `providerPaymentId` nor `providerOrderId` is written**, at initiation or anywhere else |
| Consequence | Every checkout-originated capture raises at **:178**, `reconcile_payment` maps it to `PROVIDER_UNAVAILABLE`, and the outcome is paid-but-blocked. This is the **correct fail-closed direction** — the module docstring says "A webhook must not supply its own binding" — but as wired it is a guaranteed block, not a guard |
| The authoritative-record split, to be documented | **`PAYREF#<referenceId>` in the commerce-keys table is authoritative for reconciliation.** Physical table: `stack-wecare-digital-WixOrderIds`, via `order_keys.commerce_keys_table_name()` → `COMMERCE_KEYS_TABLE` → `WIX_ORDER_IDS_TABLE`. It is what `_load_attempt` reads, and the webhook deliberately never reads amount/currency from the event body. **`stack-wecare-digital-PaymentAttemptsTable` is authoritative for the customer-facing lifecycle** — `status`, rank, retry eligibility, history row. `checkout._create` writes BOTH: the `PAYREF#` row at **:257** and the attempt row at **:278** (`put_item` with `attribute_not_exists(paymentAttemptId)`). Two rows, two purposes, one write path. Nothing currently reconciles them after the fact, which is the C6 half of the same seam |
| Required fix | Persist the provider binding onto the `PAYREF#` row from an **authenticated** source — payment initiation or the Meta Payment Lookup API — never from the unverified webhook body. Then keep the raise at **:178** as the backstop it was written to be. Record the PAYREF-vs-PaymentAttempts split in `design.md` so the next reader does not add a third store |
| Closing phase | **Phase C**; the split is documented in **Phase A** (`design.md`) |

### C5 — checkout prices from Wix Checkout V1 and never uses the Cart V2 adapter

| | |
|---|---|
| V1 call | `amplify/functions/ecommerce/checkout/handler.py:226` `checkout = wix_ecom.create_checkout(line_items)`; currency at **:227**; **:231** `amount_paise = wix_ecom.authoritative_total_paise(checkout)`; `wix_checkout_id` captured at **:239** and stored at **:261** (`"wixCheckoutId": wix_checkout_id`) |
| Underlying endpoint | `lambda_utils/integrations/wix_ecom.py:153` → `POST /ecom/v1/checkouts` |
| The Cart V2 adapter | `lambda_utils/ecommerce/cart_v2.py` (`CartV2`, `catalog_item`, `identifier`) and `lambda_utils/ecommerce/customer_cart.py` (`CustomerCart`, `CartBusy`, `CartMissing`) |
| Its only consumer | `amplify/functions/ecommerce/wix-store/handler.py:361` `_customer_cart`, importing at **:363-364**, dispatched from **:272**. Gated: returns `503 CART_UNAVAILABLE` unless `WIX_CART_V2_ENABLED == 'true'`, and that key is **absent** from live `wecare-wix-store` env |
| Grep result | Outside `cart_v2.py` itself, `cart_v2` / `customer_cart` appear only in `wix-store/handler.py` and `tests/test_cart_v2.py`. **`ecommerce/checkout` imports neither** |
| Consequence | Two price authorities for one purchase. V1 computes the total the customer is asked to pay; V2 is the owner-selected model and the one the spec's Phase 8/9 tasks are written against (`tasks.md:253-268`, `9.1` requires a live **Calculate Cart** `summary.priceSummary`). An amount that comes from V1 and is later compared against a V2 recalculation is a fail-closed mismatch on every order |
| Required fix | Migrate `_create` onto a server-owned Cart V2 calculation, keep integer paise end-to-end, and carry the V2 cart id + revision on the `PAYREF#` row instead of (or alongside, explicitly versioned) `wixCheckoutId`. Do not enable `WIX_CART_V2_ENABLED` as part of the migration — flag changes that turn on a payment path are out of scope |
| Closing phase | **Phase D** (Wix authority migration) |

### C6 — the success path is disconnected in three places at once

| | |
|---|---|
| (a) Nothing persists `PAYMENT_PAID` | `lambda_utils/ecommerce/order_creation.py:266-267` calls `payment_attempt.may_create_order({**attempt, "status": payment_attempt.PAYMENT_PAID})` — the paid state is **synthesised in memory** for the eligibility check. `order_creation.py` contains **no `update_item` and no `put_item` at all** (grep: zero hits), and `razorpay-webhook/handler.py` never touches `PaymentAttemptsTable` (its `update_item` calls at :957, :1023, :1130, :1321, :1451, :1665 are all Invoices/Payments/Contacts). So the attempt row stays at `PAYMENT_READINESS_CHECKED` or `PAYMENT_REQUEST_SENT` forever |
| (b) The status endpoint cannot return an order number | `amplify/functions/ecommerce/checkout/handler.py:349` `entry = payment_attempt.payment_history_entry(owned)` — called with **no `order_number=` argument**. `payment_attempt.py:291` signature is `payment_history_entry(attempt, *, order_number: str = "")`, and **:311** sets `"orderNumber": order_number if (settled and order_number) else None`, with **:315-318** stripping it again when not settled. With no argument the field is **always `None`** |
| (c) The page requires both | `src/pages/checkout/status.tsx:69` `viewFor(status, orderNumber)`; **:71-74** `PAYMENT_PAID` without an order number → `'finalizing'`; **:129** redirects to `/checkout/success/` only when `status === 'PAYMENT_PAID'` **and** `attempt.orderNumber` is truthy |
| Consequence | A verified, reconciled, correctly-numbered order leaves the customer on the `finalizing` screen indefinitely. There is no code path by which the three conditions can all become true. Note the design is otherwise right: `payment_history_entry`'s defensive strip and `viewFor`'s `unavailable` default both refuse to claim success — the failure mode is a permanent holding screen, **not** a false confirmation, and the fix must preserve that property |
| Required fix | Persist the attempt transition to `PAYMENT_PAID` using the existing monotonic guard (`payment_attempt.condition_expression()`, the same shape `_mark_request_sent` uses at `checkout/handler.py:399-404`) so a late webhook cannot move it backwards; resolve the order number from the claim rows (`order_keys.resolve_order_for_payment` / `resolve_order_for_provider_payment`) and pass it into `payment_history_entry(owned, order_number=...)`; leave `status.tsx` unchanged, because its contract is already correct |
| Closing phase | **Phase C** (a and b). No frontend change required |

### C7 — the newest shared write-back functions have no production caller

| | |
|---|---|
| `lambda_utils/ecommerce/wix_writeback.py` (290 lines) | Public surface: `is_enabled` (**:104**), `create_wix_order` (**:160**), `record_external_payment` (**:201**). **Callers outside the module: `tests/test_wix_writeback.py` only.** Module documents itself as "INERT until switched on" |
| `lambda_utils/ecommerce/side_effect_guard.py` (201 lines) | Public surface: `claim` (**:103**), `confirm` (**:134**), `resolve` (**:164**), `is_done` (**:180**). **Callers outside the module: `tests/test_side_effect_guard.py` only** |
| `lambda_utils/receipt_links.py` (154 lines) | **Does have a production caller** — `amplify/functions/payments/invoice-engine/handler.py:1135-1136` uses `receipt_links.signed_url`, and `tests/test_invoice_assets_are_gated.py:116` pins it. Correct the brief's grouping: receipt links are wired, the two above are not |
| Deployment gap | `wecare-checkout` **does not exist in AWS** (`ResourceNotFoundException`, re-derived). Nor do `wecare-customer-registration` or `wecare-email-verification`. All three are declared in `scripts/deploy_all_lambdas.py::SPECS` with `provisioned_by` scripts (`provision_checkout.py`, `provision_customer_registration.py`, `provision_email_verification.py`), so **first creation belongs to those provisioners, not to `deploy_all_lambdas.py`** |
| Route gap | **0** routes on `zllr9lrg7j` match `checkout`, `cart` or `registration` (re-derived). `stack-wecare-digital-PaymentAttemptsTable` has **0** items, which is the consistent consequence |
| Classification | **Deployment / wiring gap, not a design gap.** The modules are complete and test-pinned; nothing invokes them and the function that would is not deployed |
| Required fix | Provision `wecare-checkout` (+ table and secret prerequisites: `CustomersTable` ABSENT, `wecare/otp/pepper` ABSENT), create additive routes and integrations with IaC updated in the same change, then publish and move the `live` alias per `lambda-snapstart-deploy`. Wire `side_effect_guard` around each post-paid effect and `wix_writeback` behind its own flag, which stays **off** |
| Closing phase | **Phase E** (provision, route, deploy). Keep every write-back and live-send flag off |

### C1–C7 closing-phase summary

| Finding | Primary site | Closing phase |
|---|---|---|
| C1 result ignored | `payments/razorpay-webhook/handler.py:664` | C |
| C2 contradictory plans | 3 spec files `:5`; prototype trees; `checkout/handler.py:38,74` | **A** |
| C3 nonexistent route | `ecommerce/checkout/handler.py:367` ↔ `whatsapp-business-api/handler.py:2199` | B |
| C4 missing provider binding | `razorpay_verify.py:177-178` ↔ `checkout/handler.py:259-262` | C (split documented in A) |
| C5 V1 vs Cart V2 | `checkout/handler.py:226,231,261` | D |
| C6 success disconnected | `order_creation.py:267`; `checkout/handler.py:349`; `status.tsx:129` | C |
| C7 no production callers / undeployed | `wix_writeback.py`, `side_effect_guard.py`; absent `wecare-checkout` | E |

---

## 4. Stale claims — where they are, so the implementer can correct and date them

Correction style is fixed by the brief and by `docs/current-environment.md`'s existing
practice: **preserve the original dated evidence and add the label**, e.g.
`HISTORICALLY VERIFIED 2026-08-23 — NOT CURRENT`. Never delete a dated measurement.

### S1 — "route count is 361"

| file:line | Nature |
|---|---|
| `.kiro/steering/00-current-owner-overrides.md:73` | always-on steering drift table, "HTTP API routes ... 361" |
| `.kiro/steering/00-current-owner-overrides.md:75` | same table, "Routes reporting `AuthorizationType=NONE` ... 361" |
| `docs/BACKEND_FULL_AUDIT.md:8` | "1 HTTP API (`zllr9lrg7j`, 361 routes)" |
| `docs/current-environment.md:68` | "**361 routes, 0 authorizers, 361 × `AuthorizationType=NONE`**" |
| `docs/current-environment.md:87` | "rediscover: **routes are 361, not 332**" |
| `docs/current-environment.md:210` | **already self-corrected** — "The **361** figure recorded in this file is superseded: a paginated read returns **359**." KEEP as the model for the other sites |
| `docs/current-environment.md:362` | gap row G8, "361 routes, 0 authorizers, all `NONE`" |
| `docs/design.md:20` | "**361 routes, 0 authorizers, every route `AuthorizationType=NONE`.**" |
| `docs/design.md:593` | mermaid node label "361 routes, 0 authorizers, stage prod" |
| `docs/execution/aws-inventory-findings.md:22,24,310,441` | inventory deltas and the `HIGH` finding, "**361 of 361**" |
| `docs/execution/evidence-index.md:53` | `EV-0041`, dated 2026-09-25 — **evidence row, label rather than edit** |
| `docs/execution/phase-05-status.md:30,41` | `SEC-ROUTE-001` / `PROV-POLICY-001`, "361 routes, 0 OPEN" — **dated evidence, label** |
| `docs/execution/requirement-registry.md:95` | `PROV-GATE-001`, "passes over 361 routes" — **dated evidence, label** |
| `integrations/wix-velo-payment/KIRO-IMPLEMENTATION-PROMPT.md:1501` | removed with the tree |
| Current truth | **359**, paginated, `NextToken` null, measured 2026-10-01. `AuthorizationType=NONE` on **359/359**, **0** authorizers |

Distinguish two cases and handle them differently: a **live-state statement** (`00-current-owner-overrides.md`, `docs/current-environment.md:68,87,362`, `docs/design.md:20,593`, `docs/BACKEND_FULL_AUDIT.md:8`) must be corrected to 359 with the date; a **dated evidence row** (`evidence-index.md`, `phase-05-status.md`, `requirement-registry.md`, `aws-inventory-findings.md`) must keep its number and gain the "NOT CURRENT" label, because rewriting it destroys the audit trail.

### S2 — "`WECAREDIGITAL` / `WECAREUPI` are active because a constant exists"

| file:line | Nature |
|---|---|
| `amplify/functions/messaging/outbound-whatsapp/handler.py:377-389` | **the primary site.** :378 "WABA: 2094615664435155 — Active, Direct API"; :379 "— active, Direct API"; :380 "Both use the same Razorpay MID acc_TTFSyolquKEZEy \| MCC: 7392 \| Purpose: 03"; :383 "Verified live via Graph API /{waba}/payment_configurations on **2026-08-23**"; :387-388 name both configs as present |
| `amplify/functions/messaging/outbound-whatsapp/handler.py:390` | `VALID_PAYMENT_CONFIGS = {'WECAREDIGITAL', 'WECAREUPI'}`; `:394` `DEFAULT_PAYMENT_CONFIG = 'WECAREDIGITAL'`; `:396-400` `PHONE_PAYMENT_CONFIG` |
| `.kiro/specs/whatsapp-wix-commerce/tasks.md:17-28` | the four-row "Active" table, explicitly *"Recorded from the owner's dashboard readout, not re-probed"* |
| `.kiro/specs/whatsapp-wix-commerce/requirements.md:56-57` | statement 8, "The Meta payment configuration is currently absent" — **the opposite claim, in the same spec set** |
| `amplify/functions/messaging/whatsapp-business-api/handler.py:3169-3173` | `_DECLARED_CONFIGS` — **already correct**: `status: 'local_only'`, no hardcoded MID/VPA fallback, with :3155-3168 explaining why. KEEP as the model |
| `docs/compatibility.md:46` | already labelled "⛔ **NOT currently present**" — KEEP |
| Required correction | The **constant must stay** (config names must match Meta exactly, and `payment_readiness` is the gate). What must change is the **comment block at :377-389**: relabel as `HISTORICALLY VERIFIED 2026-08-23 — NOT CURRENT`, and state that presence of a name in this set proves nothing about Meta, per `payment_readiness.py`'s own rule that no name in a file yields readiness. `tasks.md:17-28` must be relabelled as an unverified owner readout, and reconciled against `requirements.md` statement 8 so the spec does not assert both |

### S3 — "`wecare_pay` is live/approved"

| file:line | Nature |
|---|---|
| `amplify/functions/core/secure-files/whatsapp_delivery.py:6` | header comment listing `wecare_pay UTILITY [IMAGE, BODY, FOOTER, BUTTONS(ORDER_DETAILS)]` |
| `amplify/functions/core/secure-files/whatsapp_delivery.py:54` | `PAY_TEMPLATE = os.environ.get("WA_PAY_TEMPLATE", "wecare_pay")` — the **default**, i.e. it applies even with no env key |
| `amplify/functions/core/secure-files/whatsapp_delivery.py:125,171` | send path and body-variable assumptions |
| `amplify/functions/payments/invoice-engine/handler.py:2217,2223-2224` | *"ALWAYS use checkout button template (wecare_pay) for ALL payments"* |
| `amplify/functions/messaging/outbound-whatsapp/handler.py:1235,1334` | language and header-image assumptions |
| `config/lambda-env-manifest.json:356` | `"WA_PAY_TEMPLATE": "wecare_pay"` |
| `docs/SECURE-FILE-SHARING.md:60,204,208,226` | documented as the primary paid-delivery template |
| `src/api/client.ts` / `src/pages/get.tsx` | UI references (per the companion audit) |
| `amplify/functions/shared/lambda_utils/payment_readiness.py:415` | the contradicting dated live read: the WABA held only `wecare_otp` on 2026-09-30 |
| `docs/current-environment.md:181,192` | already labelled "⛔ **HISTORICALLY VERIFIED — NOT CURRENT**" — KEEP as the model |
| Required correction | Label each "is approved / always use" claim as unverified pending a live template read, and cross-reference `payment_readiness.py:415`. **Do not submit, create or modify a template** — that is a standing refusal. This is `WAITING_FOR_OWNER` |

### S4 — "`acc_TTFSyolquKEZEy` is current"

| file:line | Class |
|---|---|
| `config/lambda-env-manifest.json:466` | declared, **not deployed** |
| `tests/test_payment_readiness.py:23,25` | test-pinned as authoritative, "owner-confirmed 2026-09-30" |
| `amplify/functions/shared/lambda_utils/payment_readiness.py:24,27,33` | current prose, explicitly self-correcting |
| `amplify/functions/messaging/outbound-whatsapp/handler.py:380,387` | **comment asserting it as live-verified 2026-08-23** → label |
| `.kiro/specs/whatsapp-wix-commerce/tasks.md:24,26,34` | owner dashboard readout, not re-probed |
| `bw-crm.md:212,1164` | historical master-prompt prose |
| `docs/compatibility.md:46,81` | historical prose; `:81` still weights it "weak — no live artefact", a weighting the 2026-09-30 owner confirmation reversed |
| `docs/protected-resource-register.md:89`, `docs/whatsapp-experience-structure.md:378` | historical registers |
| `integrations/wix-velo-payment/KIRO-IMPLEMENTATION-PROMPT.md:552`, `DEPLOYMENT-STATUS.md:21` | removed with the tree |

### S5 — "`[retired Razorpay account]` is current" (the runtime value)

| file:line | Class |
|---|---|
| **live Lambda env** `wecare-whatsapp-business-api.RAZORPAY_MID` | **CURRENT LIVE CONFIG**, and the repo classifies it STALE |
| `docs/compatibility.md:80` | "strong — this is the account that talks to us" — **the reversed weighting; the main stale-prose site** |
| `docs/execution/phase-04d-payment-audit.md:46` | dated evidence: the `account_id` in real webhook payloads → label, do not edit |
| `tests/test_payment_status.py:41` | webhook fixture `"account_id": "[retired Razorpay account]"` → **KEEP**, it is a fixture of a real payload |
| `tests/test_payment_readiness.py:79-84` | pinned as the **mismatch** fixture asserting `RAZORPAY_MID_MISMATCH` → KEEP |
| `.kiro/steering/META-BETA-REQUEST-EMAIL.md:49,51` | **another session's modified file.** Do NOT edit in this phase |
| `src/pages/workspace/dashboard/system-architecture.tsx:395` | already records the pair as retired — KEEP |

**Owner-blocked, and the boundary is exact.** Runtime evidence shows `[retired Razorpay account]`;
the owner readout says `acc_TTFSyolquKEZEy`. Record both with their evidence and dates.
**Do not assert that Meta's `provider_mid` and Razorpay's webhook `account_id` are the same
field** without a provider readback — they may legitimately differ, and
`payment_readiness.py` deliberately refuses to pick a winner from a file.
`WAITING_FOR_OWNER`, unblock action: a provider readback of MID and VPA.

### S6 — "`wecaredigitalbh511413.rzp@rxairtel` is current" / the `@icici` pair

| file:line | Class |
|---|---|
| `config/lambda-env-manifest.json:467` | declared, not deployed |
| `amplify/functions/shared/lambda_utils/payment_readiness.py:44-47` | current prose, "AUTHORITATIVE" |
| `src/config/constants.ts:105` | `upiVpa: 'wecaredigitalbh511413.rzp@rxairtel'` — **live UI value**, used to build `upi://pay?pa=` deep links |
| `src/pages/workspace/dashboard/system-architecture.tsx:397` | dashboard display value |
| `amplify/functions/messaging/outbound-whatsapp/handler.py:388` | 2026-08-23 comment → label |
| `.kiro/specs/whatsapp-wix-commerce/tasks.md:25,27,39` | owner readout |
| `bw-crm.md:213,1165`, `docs/protected-resource-register.md:90` | historical; both correctly note `rxairtel` is a payment address, **not** an Airtel messaging dependency |
| `docs/compatibility.md:87-89` | states the conflict as unresolved |
| live env `wecare-whatsapp-business-api.RAZORPAY_UPI_ID` | `[retired UPI VPA]` — the value actually sent |
| `docs/prohibited-provider-retirement.md:69`, `bw-crm.md:31` | **HARD RULE: never globally replace the text `airtel`.** The VPA must stay byte-for-byte |
| Risk, quoted from `payment_readiness.py` | *"A stale VPA does not error — it silently collects elsewhere"* |

Same owner-block as S5. Label, do not choose.

### S7 — "Phone 1 is disconnected"

| file:line | State |
|---|---|
| `amplify/functions/messaging/inbound-whatsapp-handler/handler.py:7706` | **already fixed** — the comment now reads "The dead `if False:` branch that used to sit here…". A tree-wide grep for `if False` in that handler returns only this line |
| `docs/compatibility.md:44` | records the correction: the comment "was **stale and wrong**"; sender `LIVE` re-measured 2026-09-30, quality GREEN |
| `docs/current-environment.md:226` | records the contradiction correctly |
| `docs/tasks.md:66` | **STALE TASK ROW** — task `0.12` "Remove the stale `if False: # Phone 1 DISCONNECTED` branch" is `⏳ PENDING` and cites `inbound-whatsapp-handler:7309`. The branch is **already gone** and the line number no longer applies |
| `integrations/wix-velo-payment/KIRO-IMPLEMENTATION-PROMPT.md:1510` | removed with the tree |
| Required correction | Mark `docs/tasks.md:66` `✅ COMPLETE` with the evidence (`handler.py:7706`, `docs/compatibility.md:44`) and the date. This is the cheapest correction in the list and the only one that is purely a status flip |

### S8 — "payment reference can be transformed/truncated"

| file:line | State |
|---|---|
| `integrations/wix-velo-payment/KIRO-IMPLEMENTATION-PROMPT.md:885,1417,1511,1579` | the claim and its checklist entry — removed with the tree |
| `lambda_utils/ecommerce/order_keys.py:190` | **already fixed** — `assert_valid_meta_reference_id` validates `^[A-Za-z0-9._-]{1,35}$` and **raises**; docstring states "Rejecting is the only safe response" |
| `messaging/outbound-whatsapp/handler.py:2845` | `_sanitize_reference_id` is now **validate-or-fail**: returns canonical byte-for-byte, raises `ReferenceIdTooLong` over 35, raises if handed a WD order number (checked *before* the pass-through), and the old unconditional `.upper()` is gone because Meta's `reference_id` is case-sensitive. Call sites :1060, :1254, :2025 |
| `messaging/inbound-whatsapp-handler/handler.py:3145` | inbound **lookup/display** normalisation only — not a send path |
| `.kiro/specs/whatsapp-wix-commerce/requirements.md:48,203` | states the correct rule |
| `.kiro/specs/whatsapp-wix-commerce/tasks.md:153-164` | task 2.4 `[x]`, pinned by `tests/test_reference_id_never_truncated.py` |
| Required correction | No code change. When the prototype tree is deleted, record in the cleanup manifest that this checklist item was **already satisfied at deletion time**, with the pinning test named — otherwise the claim's disappearance looks like the claim being dropped |

### S9 — "order identity should exist before paid state"

| file:line | State |
|---|---|
| `integrations/wix-velo-payment/KIRO-IMPLEMENTATION-PROMPT.md:832-838` | §34 "SPLIT `allocate_order_identity()`" and *"binds a Meta reference to an order number before payment"* — removed with the tree |
| `lambda_utils/ecommerce/order_keys.py:12-15` | **already fixed** — `allocate_order_identity` is **gone, not deprecated**, with the docstring explaining that "a deprecated function that reserves an order number is a function someone calls" |
| `tests/test_order_keys.py:296` | `assert not hasattr(order_keys, 'allocate_order_identity')` — the reverse direction is pinned |
| `.kiro/specs/whatsapp-wix-commerce/requirements.md:44-53` | statements 4 and 6 state the correct rule |
| `.kiro/specs/whatsapp-wix-commerce/tasks.md:148-152` | task 2.3 `[x]` |
| Required correction | No code change. Same cleanup-manifest note as S8 |

### S10 — spec-internal stale claims found while mapping (not in the brief's list, but in scope)

| file:line | Claim | Current truth |
|---|---|---|
| `.kiro/specs/whatsapp-wix-commerce/tasks.md:51-52` | *"Phases 6 onward are blocked on R0 — the Wix credential does not exist in AWS"* | **Stale.** `wecare/wix/headless-api-key` exists with 1 version stage, re-derived 2026-10-01. R0 is no longer a Phase-6 blocker. Note `requirements.md:85` already says "R0 ✅ RESOLVED 2026-09-26", so `tasks.md` contradicts its own spec set |
| `.kiro/specs/whatsapp-wix-commerce/requirements.md:56-57` | statement 8, *"The Meta payment configuration is currently absent"* | **UNKNOWN**, not absent — see §1.3. Must be relabelled as the 2026-09-30 reading with the owner's contradicting readout beside it |
| `.kiro/specs/whatsapp-wix-commerce/requirements.md:102-113` | R0 carried-forward items: the Wix key "must be rotated"; site-id discrepancy unresolved | Keep. Both remain `WAITING_FOR_OWNER`; rotation is a standing refusal for the agent |

---

## 5. Ordered edit plan for the implementer

### 5.0 Non-negotiable invariants — these bound every item below

Carried from the brief and from the requirement set already pinned by tests. An edit that
weakens any of these is wrong even if it makes a check pass.

1. **An order exists only after a provider readback confirms capture.** A webhook is a
   trigger to verify, never proof. (`requirements.md` statements 4, 6; `test_order_creation`)
2. **A failed, cancelled, expired or pending payment creates zero orders**, zero order
   numbers, zero Wix orders, zero receipts.
3. **Money is integer paise, everywhere. No float arithmetic in the payment path.** A one-paise
   mismatch **fails closed**. Currency is compared **explicitly**, before amount.
4. **`reference_id` is minted once from `secrets`, reserved before use, and sent byte-for-byte.**
   Never truncated, prefixed, re-cased or repaired. Over-long **raises**.
5. **Exactly one order per provider payment.** Redelivery creates no second order; a crash
   between claiming and numbering is finished on re-entry without a second id.
6. **Reconciliation cannot charge the customer.** The permitted Wix calls are an enumerated
   allowlist (`test_reconciliation_cannot_charge_the_customer`); no permitted call moves money.
7. **Payment readiness is provider-driven.** No constant and no env var may enable payment;
   `BLOCKING_STATES` is an explicit enumeration so a new state cannot become permissive by
   omission.
8. **Payment state decisions go through `lambda_utils/payment_status.py`.** `captured` is banned
   as a raw literal at decision points, enforced by an **AST** walk
   (`test_payment_vocabulary_at_decision_points.py`). `InvoicesTable.status` is a *document
   lifecycle* and deliberately NOT this vocabulary — do not canonicalise it.
9. **Razorpay is the only gateway.** PayU is retired permanently. Its secret is gone.
10. **India rules:** MCC `7392`, purpose code `03`, `INR` only, paise as integers, DLT template
    `ivr-default` for SMS.
11. **Every live-send and write-back flag stays off:** `CHECKOUT_INITIATION_ENABLED`,
    `WIX_CART_V2_ENABLED`, `WA_LIVE_SMOKE_TEST`, `PSTN_BROWSER_ROUTING_ENABLED`,
    `wix_writeback` enablement. Enabling one is a standing refusal.
12. **No payment capture, refund, or payment-configuration mutation. No Meta template
    creation/submission. No WhatsApp number migration or deregistration. No credential value
    read, rotated or placed on a command line. No `get-secret-value` in any spelling.**
13. **`wecaredigitalbh511413.rzp@rxairtel` is byte-for-byte protected.** Never globally replace
    the text `airtel`.
14. **Git:** branch `stack` only, non-force, no history rewrite, no `git add .`/`-A`/`-u`, no
    `git commit -a`, no bare `git stash`.

### 5.1 Task-state vocabulary — use these, and only these

Per `docs/execution/requirement-registry.md:9-10`:
`DISCOVERED` · `CODE_COMPLETE` · `TESTED` · `PUSHED` · `DEPLOYED` · `LIVE_VERIFIED` ·
`WAITING_FOR_OWNER` · `WAITING_FOR_PROVIDER` · `BLOCKED`.

Per `maintenance-reporting.md`, status reporting uses:
`✅ COMPLETE` · `🟡 IN PROGRESS` · `⏳ PENDING` · `⚠️ NEEDS CONFIRMATION` · `❌ FAILED` ·
`⛔ BLOCKED` · `➖ NOT REQUIRED`. **COMPLETE means the intended result was verified; a command
exiting 0 is not evidence of success.** Severity is one of
`CRITICAL HIGH MEDIUM LOW INFORMATIONAL` and must not be exaggerated.

Phase A's own honest state, to be carried into the final report: the C1/C3/C4/C5/C6/C7 fixes
are `DISCOVERED` (this phase records them; B–E close them). C2 reaches `CODE_COMPLETE` →
`TESTED` → `PUSHED` within this phase. S3, S5, S6 and the config-active question remain
`WAITING_FOR_OWNER`.

### 5.2 Before anything else — capture baselines

- [ ] **0. Capture the pre-edit baselines that the verification steps compare against.**
      Nothing is edited in this item. Record the numbers in
      `.agents/tasks/phase-a-checkout-reconcile-2026-10-01/baseline.md`.
      Run, from the repo root:
      `git rev-parse HEAD`;
      `git status --short`;
      `.venv/bin/python -m pytest -q 2>&1 | tail -5` (full suite — the pass count is the
      baseline; `pytest.ini` `testpaths` = `tests`, `amplify/functions`);
      `npm run lint 2>&1 | tail -5`;
      `npm run typecheck`;
      `npm test 2>&1 | tail -5` (vitest, `src/**` only);
      `(cd integrations/wix-velo-payment && node --test tests/*.test.js 2>&1 | tail -8)`;
      `(cd integrations/wix-psp && node --test tests/*.test.js 2>&1 | tail -8)`.
      **Measured in this planning step, for cross-check:** focused commerce suite
      (`tests/test_order_keys.py test_order_creation.py test_payment_attempt.py
      test_payment_readiness.py test_razorpay_webhook_order_creation.py test_checkout_handler.py
      test_cart_v2.py test_payment_vocabulary_at_decision_points.py
      test_reference_id_never_truncated.py`) = **394 passed**; `npx eslint integrations` = **0
      problems**; Velo node tests = **42 pass**; PSP node tests = **16 pass**.
      Files: `.agents/tasks/phase-a-checkout-reconcile-2026-10-01/baseline.md`
      Verify: the file exists and every command's output is recorded, including the full-suite
      pass count. If a gate is already red at baseline, record it as pre-existing and do not
      attribute it to this phase.

### 5.3 FEAT-001 — reconcile the canonical spec and the documentation (do this FIRST)

> ⛔ **SUPERSEDED BY §0 AND §7 while the concurrent session's work is uncommitted.** Items 1–14
> below were written before that work was visible and target files another session now owns.
> They are retained because they are the correct plan **if** the owner reassigns Phase A to this
> workflow (§7.4 option B) or **after** that session's commit lands, at which point each item
> becomes a verify-or-close step rather than an edit. Do not execute them as written today.


This must precede the deletions, because
`integrations/wix-velo-payment/KIRO-IMPLEMENTATION-PROMPT.md` is the source of the
stale-claims checklist (§4) and the C1–C7 conflict statements. Migrate, then delete.

- [ ] **1. Rewrite the shared owner-decision paragraph in all three canonical spec files.**
      Replace the identical line 5 in each. It currently says Velo and external PSP onboarding
      "are not dependencies", which is weaker than the owner decision. It must state: standalone
      Wix Headless + AWS + WhatsApp/Razorpay only; Velo, the Wix-native payment-provider plugin,
      external PSP onboarding, the `submitEvent` bridge and any dual-mode / native-vs-headless
      router are **removed from the active implementation**; the prototype source is deleted
      (name the retirement date); ONE active design and ONE production checkout path; this
      supersedes all earlier dual-mode prompts and the Velo prompt's "supersedes" claim, which is
      **withdrawn**. Add that `WIX_HEADLESS` (`ecommerce/checkout/handler.py:75`) remains as an
      **immutable provenance field**, not a mode switch. Keep the existing pointer to
      `docs/execution/headless-checkout-20261001.md`.
      Files: `.kiro/specs/whatsapp-wix-commerce/requirements.md`,
      `.kiro/specs/whatsapp-wix-commerce/design.md`,
      `.kiro/specs/whatsapp-wix-commerce/tasks.md`
      Verify: `.venv/bin/python -m pytest -q` — pass count equals baseline (no test reads these
      files; the gate is that nothing regressed). Plus `git diff --check` clean.

- [ ] **2. Correct the spec-internal stale claims (S10) so the spec set stops contradicting
      itself.** In `tasks.md`, relabel the four-row "Active" configuration table at :17-28 as an
      **unverified owner dashboard readout** with the contradicting `payment_readiness.py:415`
      / module-docstring zero-configuration reading cited beside it and both dates preserved;
      correct :51-52 (`Phases 6 onward are blocked on R0 — the Wix credential does not exist in
      AWS`) to record that `wecare/wix/headless-api-key` **exists** with one version stage,
      re-derived 2026-10-01, so R0 is no longer a Phase-6 blocker — matching `requirements.md:85`
      which already says R0 is RESOLVED. In `requirements.md`, relabel statement 8 (:56-57) from
      "is currently absent" to the dated 2026-09-30 reading with the owner readout beside it, and
      keep statement 9 (provider-driven readiness) exactly as written because it is the rule that
      makes the ambiguity safe. Do **not** delete any date.
      Files: `.kiro/specs/whatsapp-wix-commerce/tasks.md`,
      `.kiro/specs/whatsapp-wix-commerce/requirements.md`
      Verify: `.venv/bin/python -m pytest -q` equals baseline; `git diff --check` clean.

- [ ] **3. Add the C1–C7 closure matrix to `tasks.md` as a new dated section.** One row per
      finding, each carrying: finding id, one-line statement, **current** file:line (copy from
      §3 of this plan — they were re-derived at `6a5d6e9e`), required fix, closing phase (B/C/D/E,
      with C2 = A), task state from §5.1, and the pinning test where one exists. Do not renumber
      or restate existing Phase 0–10 tasks; append. Include the C4 **PAYREF-vs-PaymentAttempts
      authority split** as an explicit row and the C7 correction that `receipt_links` **does**
      have a production caller (`payments/invoice-engine/handler.py:1135-1136`) while
      `wix_writeback` and `side_effect_guard` do not.
      Files: `.kiro/specs/whatsapp-wix-commerce/tasks.md`
      Verify: `.venv/bin/python -m pytest -q` equals baseline. Cross-read every file:line in the
      matrix against the tree (`git grep -n` on the quoted symbol) and confirm each resolves —
      a stale line number in the closure matrix would reproduce the exact defect this phase
      exists to fix.

- [ ] **4. Document the two identifier stores in `design.md`.** Under the existing
      `## Data model` / `## Identifier algorithm` sections, record that **`PAYREF#<referenceId>`
      in the commerce-keys table (physically `stack-wecare-digital-WixOrderIds`, via
      `order_keys.commerce_keys_table_name()`) is authoritative for reconciliation** — it is what
      `razorpay-webhook.handler._load_attempt` (:460) reads, and the webhook deliberately never
      takes amount or currency from the event body — while **`stack-wecare-digital-PaymentAttemptsTable`
      is authoritative for the customer-facing lifecycle** (status, rank, retry eligibility,
      history row). State that `checkout._create` writes both (`:257` and `:278`) and that no
      third store may be introduced. Also record the C4 consequence: the provider binding
      (`providerPaymentId` / `providerOrderId`) must be persisted onto the `PAYREF#` row from an
      authenticated source, never from the webhook body, and that `razorpay_verify.py:177-178`
      stays as the backstop.
      Files: `.kiro/specs/whatsapp-wix-commerce/design.md`
      Verify: `.venv/bin/python -m pytest -q` equals baseline; `git diff --check` clean.

- [ ] **5. Date-label the "361 routes" live-state claims and leave the dated evidence rows
      alone.** Correct to **359** with the 2026-10-01 measurement date, noting `NextToken` null
      and 0 authorizers, at: `.kiro/steering/00-current-owner-overrides.md:73,75`;
      `docs/BACKEND_FULL_AUDIT.md:8`; `docs/current-environment.md:68,87,362`;
      `docs/design.md:20,593`. Add `HISTORICALLY VERIFIED <date> — NOT CURRENT` **without
      changing the number** at: `docs/execution/aws-inventory-findings.md:22,24,310,441`;
      `docs/execution/evidence-index.md:53`; `docs/execution/phase-05-status.md:30,41`;
      `docs/execution/requirement-registry.md:95`. Leave
      `docs/current-environment.md:210` as-is — it is already the correct model. Take care in
      `00-current-owner-overrides.md`: it is **always-on steering injected into every session**,
      so keep its own "do not quote counts from this file" instruction intact and present the
      correction as a dated drift row.
      Files: as listed above
      Verify: `.venv/bin/python -m pytest -q` equals baseline; `npm run lint` equals baseline;
      `git grep -n '361' -- docs/ .kiro/steering/` — every surviving hit must sit next to a
      `NOT CURRENT` label or be an unrelated number (e.g.
      `docs/current-communications-architecture.md:172`, `data/resource.ts:361-389`).

- [ ] **6. Date-label the payment-configuration, MID, VPA and template claims. Do not choose a
      winner.** Relabel the comment block at
      `amplify/functions/messaging/outbound-whatsapp/handler.py:377-389` as
      `HISTORICALLY VERIFIED 2026-08-23 — NOT CURRENT`, and add that presence of a name in
      `VALID_PAYMENT_CONFIGS` (:390) proves nothing about Meta — the gate is
      `lambda_utils/payment_readiness.py`. **Keep the constant and every config name
      byte-for-byte**: Meta requires exact matches, and `_DECLARED_CONFIGS`
      (`whatsapp-business-api/handler.py:3169-3173`) is the model for how to say `local_only`
      honestly. Reverse the stale evidence weighting in `docs/compatibility.md:80-81,87-89`,
      preserving both dated readings and stating that the authoritative pair is
      **provider-readback-pending**. Label the `wecare_pay` claims
      (`core/secure-files/whatsapp_delivery.py:6,54`;
      `payments/invoice-engine/handler.py:2217,2223-2224`;
      `docs/SECURE-FILE-SHARING.md:60,204,208,226`) as unverified pending a live template read,
      cross-referencing `payment_readiness.py:415`.
      **Change no value:** not `RAZORPAY_MID`, not `RAZORPAY_UPI_ID`, not `WA_PAY_TEMPLATE`, not
      `config/lambda-env-manifest.json`, not `src/config/constants.ts:105`, and not
      `.kiro/steering/META-BETA-REQUEST-EMAIL.md` (another session's modified file). Never
      globally replace the text `airtel`.
      Files: `amplify/functions/messaging/outbound-whatsapp/handler.py`,
      `amplify/functions/core/secure-files/whatsapp_delivery.py`,
      `amplify/functions/payments/invoice-engine/handler.py`, `docs/compatibility.md`,
      `docs/SECURE-FILE-SHARING.md`
      Verify: `.venv/bin/python -m pytest -q` equals baseline — in particular
      `tests/test_payment_readiness.py`, `tests/test_payment_status.py` and
      `tests/test_payment_vocabulary_at_decision_points.py` must stay green (the last walks the
      AST, so a comment mentioning `captured` is safe, but confirm rather than assume). Then
      `scripts/check-provider-policy.sh` and `git grep -c 'rxairtel' -- src/ config/ amplify/` —
      the VPA count must be unchanged.

- [ ] **7. Fix the two deployed-source comments that point at a tree about to be deleted, and
      flip the one already-satisfied task row.** In
      `amplify/functions/ecommerce/checkout/handler.py`, rewrite :38 (the
      `initiationEnabled=false` analogy to the Velo adapter) to state the fail-closed posture
      directly, and :74 ("not the (set-aside) Velo provider") to say the prototype is removed
      while keeping the sentence's real job — explaining why `checkoutMode` exists as provenance.
      In `docs/execution/headless-checkout-20261001.md:3`, move the prototype sentence to past
      tense with the retirement date. In `docs/tasks.md:66`, mark task `0.12` `✅ COMPLETE` with
      evidence (`inbound-whatsapp-handler/handler.py:7706`, `docs/compatibility.md:44`) and note
      the cited line `7309` no longer applies. Add one authority pointer at the top of
      `docs/tasks.md` naming `.kiro/specs/whatsapp-wix-commerce/` as canonical for the checkout
      path (flag F3).
      Files: `amplify/functions/ecommerce/checkout/handler.py`,
      `docs/execution/headless-checkout-20261001.md`, `docs/tasks.md`
      Verify: `.venv/bin/python -m pytest tests/test_checkout_handler.py -q` passes, then the
      full `.venv/bin/python -m pytest -q` equals baseline. `git diff` on `handler.py` must show
      **comment lines only** — no executable line may change in this item.

- [ ] **8. Write the decision record.** One dated document capturing: the owner decision
      verbatim in substance; what it withdraws (Velo, native provider plugin, external PSP
      onboarding, `submitEvent` bridge, dual-mode router, the `WIX_NATIVE_PROVIDER` "supersedes"
      claim — noting the token never existed in the tree); what is retained and why
      (`WIX_HEADLESS` as immutable provenance; `VALID_PAYMENT_CONFIGS` because Meta needs exact
      names; the `rxairtel` VPA byte-for-byte); the flag F1 note that `bw-crm.md`'s
      Velo/native-checkout reconciliation instructions are superseded by this decision and its
      provider rows are historical, while explicitly stating that the master prompt is **not**
      rewritten in this phase; and the rollback path (`git revert`; prototype trees recoverable
      at `acdad528` and `aaddd882`; no history rewrite).
      Files: `.agents/tasks/phase-a-checkout-reconcile-2026-10-01/decision-record.md`
      Verify: the file exists, names both prototype commits, and every claim in it resolves
      against the tree (`git cat-file -t acdad528`, `git cat-file -t aaddd882` both return
      `commit`).

- [ ] **9. Write the collision-audit evidence copy.**
      *Assumption recorded, because the brief does not define the term:* this is read as the
      **identifier-collision safety audit** for the payment path — the one body of evidence that
      Phase A must preserve before the prototype prompt (which restates §33/§34 of the old plan)
      is deleted. If the intended subject was different, this artifact is additive and harmless.
      Copy, with file:line citations: the collision arithmetic in
      `lambda_utils/ecommerce/order_keys.py:100,115-119` (6 symbols ≈29.4 bits, 8 ≈39.3, 12 ≈58.9,
      and why the minted `WD-ORD-`+8 form is 15 characters rather than the legacy bare 12); the
      three regeneration sites `:406` (payment reference), `:447` (public order number), `:661`
      (order number) and the rule that a collision is never *wrong* because the conditional
      reservation refuses it and regenerates; the "never return an unreserved identifier"
      principle and its pinning test `tests/test_order_keys.py:397`; the absence proof
      `tests/test_order_keys.py:296` (`allocate_order_identity` gone); and the cosmetic defect that
      `record_order_number_on_claim`'s `ValueError` still says "12-character" while validating via
      `is_public_order_number` (INFORMATIONAL, no fix in this phase).
      Files: `.agents/tasks/phase-a-checkout-reconcile-2026-10-01/collision-audit-evidence.md`
      Verify: every cited line resolves — `.venv/bin/python -m pytest tests/test_order_keys.py -q`
      passes, and `git grep -n 'collision' -- amplify/functions/shared/lambda_utils/ecommerce/order_keys.py`
      returns the quoted lines.

- [ ] **10. Commit FEAT-001 by explicit path, with `--only`.** The working tree holds another
      session's modification (`.kiro/steering/META-BETA-REQUEST-EMAIL.md`) and an untracked file
      (`scripts/retired_url_equity.py`), so `multi-session-parallel-agents` rule 3b applies and
      `--only` is **not optional**. Re-read `git status --short` as a separate command, *not*
      chained, and confirm no listed path belongs to another session before staging. New files
      need `git add` first because `--only` rejects an untracked pathspec:
      `git add <new artifact paths> && git commit --only <all paths> -F <message-file>`.
      Then `git push origin stack` (non-force, branch `stack`, no new remote branch).
      Files: only those touched in items 1–9
      Verify: `git show --stat HEAD` lists **exactly** the intended paths and nothing else;
      `git status --short` still shows the other session's `M` and `??` entries untouched.

### 5.4 FEAT-002 — retire the prototype trees (do this SECOND)

Depends on FEAT-001: the checklist and conflict statements must already be migrated.

- [ ] **11. Re-verify zero consumers immediately before deleting.** Another session may have
      added a reference since this plan was written. Run, and require the stated result:
      `git grep -F 'wix-velo-payment' -- . ':!integrations/' ':!docs/execution/change-authority-matrix.md'`
      → **0 hits**; `git grep -F 'wix-psp' -- . ':!integrations/'` → **0 hits**;
      `git grep -F 'WIX_NATIVE_PROVIDER'` → 0; `git grep -F 'submitEvent' -- . ':!integrations/'`
      → 0; `git grep 'integrations' -- .github/ scripts/deploy_all_lambdas.py config/lambda-env-manifest.json`
      → 0. If any returns a hit, stop and classify it before deleting.
      Files: none (read-only)
      Verify: all five probes return the stated counts, recorded in the cleanup manifest.

- [ ] **12. Write the cleanup manifest, then delete both trees.** The manifest must precede the
      deletion in the same commit and must record: the 18 tracked files by path; the final test
      measurements (Velo **42 pass**, PSP **16 pass**, `npx eslint integrations` **0 problems**,
      all re-run in item 11's step); that the 58 node tests were **never in CI**
      (`vitest.config.ts` includes `src/**` only; no workflow runs `node --test`; `package.json`
      has no `workspaces`); the §2.5 extraction decision — **nothing extracted**, with the
      per-candidate reason, including that `wix-psp/request-auth.js` is well-built and that its
      quality is not a reason to resurrect it; that CodeQL scanned these files repository-wide
      and deletion **reduces** scan surface, with the `eslint.config.mjs` warning against
      re-adding a blanket ignore for any future reference tree; that the S8 and S9 checklist items
      were **already satisfied at deletion time** with their pinning tests named
      (`tests/test_reference_id_never_truncated.py`, `tests/test_order_keys.py:296`); and the
      rollback (`git revert`; trees recoverable at `acdad528` / `aaddd882`; **no history
      rewrite**). Then `git rm -r integrations/wix-velo-payment integrations/wix-psp`.
      Files: `.agents/tasks/phase-a-checkout-reconcile-2026-10-01/cleanup-manifest.md`;
      delete `integrations/wix-velo-payment/**` (14 files),
      `integrations/wix-psp/**` (4 files)
      Verify: `npm run lint` — **0 errors**, warning count equal to baseline (the directory was
      linted, so this proves removal broke nothing); `npm run typecheck` clean; `npm test`
      (vitest) equals baseline; `.venv/bin/python -m pytest -q` equals baseline;
      `git ls-files integrations/` → **empty**; `git status --short` shows 18 `D` entries and no
      other deletion.

- [ ] **13. Append the retirement row to the change-authority matrix. Do not edit rows 528-538.**
      Add a new dated section recording: class (`A4_DESTRUCTIVE` for the deletion, `A1_LOCAL` for
      the documentation), the owner decision as authority, the exact paths removed, the zero-consumer
      proof from item 11 with its five probe results, the gates re-run with their numbers, and the
      rollback. Note explicitly that rows **531 and 534** — the original integration entry and its
      pre-authorised rollback line ("remove only the newly added
      `integrations/wix-velo-payment` directory") — are **preserved as evidence** and were the
      pre-authorisation this retirement executes.
      Files: `docs/execution/change-authority-matrix.md`
      Verify: `git diff docs/execution/change-authority-matrix.md` shows **additions only** — zero
      deletions and zero modifications to existing lines (`git diff --numstat` must show `0`
      deletions for this file).

- [ ] **14. Commit FEAT-002 by explicit path with `--only`, then push.** Same rule-3b discipline as
      item 10: re-read `git status --short` unchained, `git add` any new artifact, then
      `git commit --only <paths> -F <message-file>`, then `git push origin stack`.
      Files: only those touched in items 11–13, plus the 18 deletions
      Verify: `git show --stat HEAD` lists exactly the 18 deletions plus the manifest and the
      matrix, and nothing else; the other session's `M`/`??` entries are still present and
      untouched.

### 5.5 Final report

- [ ] **15. Produce the Phase A closing report.** Sections required by
      `maintenance-reporting.md`: **COMPLETED · IN PROGRESS · PENDING · FAILED/BLOCKED · GAPS
      FOUND · IMPROVEMENTS REQUIRED · CONFIRMATIONS**, with BEFORE/AFTER/CHANGE wherever
      measurable and **no invented before-values**. Must state: the re-derived HEAD and the new
      HEAD after both commits; the current-state table from §1 with its UTC date; the C1–C7
      closure matrix with closing phases; every stale claim corrected or labelled, with the ones
      deliberately left as `WAITING_FOR_OWNER` (S3 template, S5 MID, S6 VPA, the
      configuration-active question) named individually; the 18 files removed and the 58 node
      tests lost with their last measurement; **zero AWS mutations, zero Lambda deployments, zero
      alias moves, zero flag changes, zero provider mutations, zero credential reads**; and the
      gate results against baseline. Final result must be exactly one of
      `✅ COMPLETE — ALL REQUIRED WORK VERIFIED` · `⚠️ COMPLETE WITH IMPROVEMENTS` ·
      `⚠️ WAITING FOR CONFIRMATION` · `⚠️ PARTIAL` · `❌ BLOCKED`. Given the owner-blocked items
      this will be `⚠️ COMPLETE WITH IMPROVEMENTS` or `⚠️ PARTIAL`; **do not report
      `✅ COMPLETE` while `WAITING_FOR_OWNER` rows stand.**
      Files: `.agents/tasks/phase-a-checkout-reconcile-2026-10-01/phase-a-report.md`
      Verify: every number in the report traces to a command recorded in `baseline.md` or to §1
      of this plan; the full gate set (`.venv/bin/python -m pytest -q`, `npm run lint`,
      `npm run typecheck`, `npm test`, `scripts/check-provider-policy.sh`,
      `python scripts/check_design_drift.py --gate`, `git diff --check`) is re-run and recorded
      with its final numbers.

### 5.6 Explicitly out of scope for Phase A

Recorded so the implementer does not drift into them: any C1, C3, C4, C5, C6 or C7 **code
fix**; provisioning `wecare-checkout` / `CustomersTable` / `wecare/otp/pepper`; creating any
API route or integration; any `update-function-code`, version publish or `live` alias move;
pushing `config/lambda-env-manifest.json` values to live env; enabling any flag; any Meta,
Razorpay or Wix mutation; rewriting `bw-crm.md`; deleting `docs/tasks.md`; touching
`.kiro/steering/META-BETA-REQUEST-EMAIL.md`.

### 5.7 UNKNOWN and WAITING_FOR_OWNER carried out of Phase A

| Id | Item | Unblock action (owner only) |
|---|---|---|
| `WAITING_FOR_OWNER` A | Canonical Meta payment configuration name per WABA, and whether the four are presently Active | Owner runs `payment_readiness.evaluate()` or reads `GET /{waba}/payment_configurations`, and states the exact `configuration_name` per WABA |
| `WAITING_FOR_OWNER` B | Canonical payment template name and its APPROVED status (`wecare_pay` vs `wecare_otp`) | Owner confirms from WhatsApp Manager, or confirms all sends stay inside the 24-hour service window |
| `WAITING_FOR_OWNER` C | Razorpay live key + secret and the Wix admin token must be **rotated**, not merely stored (both disclosed in a transcript 2026-09-30) | Owner runs `set_wix_credential.py --verify`, `refresh_secret_consumers.py`, `check_secrets_live.py` |
| `WAITING_FOR_OWNER` D | Provider readback of MID and VPA. Until it exists, S4/S5/S6 have no safe target and the live-env pair must not be changed | Owner reads the gateway MID and UPI VPA off the live configurations, or authorises a Graph read with the token kept out of argv |
| `WAITING_FOR_OWNER` E | MCC `7392` (business services) vs purpose code `03` (supplied as Travel) — a compliance mismatch, not an implementation default (`bw-crm.md:212`) | Provider/business confirmation |
| `UNKNOWN` F | Whether Meta's `provider_mid` and Razorpay's webhook `account_id` are the same field | Provider readback. **Do not assert equality without it** |
| `UNKNOWN` G | Which SES DKIM selector is actually signed with | Read `s=` from a real sent message |
| `UNKNOWN` H | Wix site/dashboard state beyond `WIX_SITE_ID`, and the R0 site-id discrepancy (`requirements.md:113`) | Authenticated Wix dashboard |

---

## 6. Method and limitations

**Live reads used, all read-only:** `git rev-parse`, `git status --short`, `git log`,
`git log --stat`, `git ls-files`, `git grep`; `apigatewayv2 get-routes`, `get-authorizers`;
`lambda list-functions`, `get-function-configuration`; `dynamodb scan (Select=COUNT,
ConsistentRead)`, `describe-table`; `secretsmanager describe-secret`.

**Never run:** `secretsmanager get-secret-value` / `batch-get-secret-value` in any spelling;
any Meta Graph, Razorpay or Wix API call; any Lambda `Invoke`; any write, publish, alias move
or delete; `aws login` / `aws sso login`. No credential appeared in any command line. No file
outside `.agents/tasks/phase-a-checkout-reconcile-2026-10-01/` was created or modified.

**Tests run in this step:** the focused commerce suite (394 passed, 1.18 s) and both prototype
node suites (42 and 16 passed), via `.venv/bin/python` 3.12.14 and `node --test`. The system
`python3` at `/Applications/Xcode.app/...` has no `pytest`; use `.venv/bin/python`. The **full**
pytest suite was **not** run here — that is item 0's job, and the baseline must come from the
implementer's own run rather than from a number quoted in a document.

**Historical evidence is labelled as historical throughout.** Where a dated measurement is
cited (the 2026-08-23 configuration verification, the 2026-09-30 zero-configuration probe, the
2026-09-30 template read), it is cited as a dated reading and never as current live state.




