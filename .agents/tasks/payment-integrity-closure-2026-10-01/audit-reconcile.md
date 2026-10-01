# Payment-integrity closure — audit and reconciliation

**Produced 2026-10-01 (Asia/Kolkata), READ-ONLY.** No source edit, no stage, no commit, no push,
no AWS mutation, no deploy, no provider call that moves money. Every AWS observation below is
metadata or IAM simulation. No `secretsmanager get-secret-value` in any spelling. No credential
value appears in this file.

**Scope.** The audit foundation for: a captured Razorpay payment may produce exactly ONE paid
internal order and ONE set of purchase side effects, and no unverified, rejected, ambiguous or
unknown event may ever produce a financial side effect.

---

## 0. Baseline, measured

| Item | Value |
|---|---|
| Branch | `stack` |
| HEAD | `f7304eba16c76cd7beb5f6076e68709fd014340c` — "Point the M3 reference at the maintained fork (#177)", 2026-10-01 13:33:15 +0530 |
| AWS | account `775261844268`, `us-east-1`, profile `wecare-prod` |
| `wecare-razorpay-webhook` `live` alias | **v45** |
| Python | `/Users/wecaredigital/wecare-store/.venv/bin/python` (bare `python` not on PATH) |

**HEAD has moved since every evidence document read for this audit.** The closure matrix cites
`6a5d6e9e`, the deep audit cites `8807db0e`. All line numbers below were re-derived at
`f7304eba` plus the uncommitted working tree, and several have drifted materially — see §1.1.

### `git status --short`, verbatim

```
 M .kiro/specs/whatsapp-wix-commerce/design.md
 M .kiro/specs/whatsapp-wix-commerce/requirements.md
 M .kiro/specs/whatsapp-wix-commerce/tasks.md
 M .kiro/steering/META-BETA-REQUEST-EMAIL.md
 M amplify/functions/payments/razorpay-webhook/handler.py
 M amplify/functions/shared/lambda_utils/ecommerce/order_creation.py
 M docs/execution/change-authority-matrix.md
?? .agents/
?? .kiro/settings/mcp.json.backup-1790839713269560000
?? .kiro/settings/mcp.json.before-dcr-20261001T072213227545Z.bak
?? .kiro/settings/mcp.json.before-meta-20261001T065808336775Z.bak
?? .kiro/settings/mcp.json.before-meta-20261001T065944528153Z.bak
?? .kiro/settings/mcp.json.before-meta-20261001T070200671455Z.bak
?? .kiro/settings/mcp.json.before-meta-20261001T071723717644Z.bak
?? AGENTS.md
?? amplify/functions/shared/lambda_utils/ecommerce/finalization.py
?? amplify/functions/shared/lambda_utils/ecommerce/initiation.py
?? docs/execution/checkout-c1-c7-closure-matrix-20261001.md
?? docs/execution/checkout-consolidation-findings-20261001.md
?? docs/execution/first-deep-audit-20261001-codex.md
?? docs/execution/webhook-signature-verification-pattern-20261001.md
?? scripts/retired_url_equity.py
```

**NOTHING IS STAGED.** Every `M` line has a space in column 1. The index was clean on arrival and
is clean now. This matters: `multi-session-parallel-agents` rule 3b exists because a session
inherited a dirty index and swept five foreign files into its commit. A later step must still use
`git commit --only <paths>`, because the tree holds **three** workstreams' files, but it is not
starting from a pre-staged index.

### Ownership of each dirty path

| Path | State | Owned by this task? |
|---|---|---|
| `amplify/functions/payments/razorpay-webhook/handler.py` | modified, unstaged | **YES** |
| `amplify/functions/shared/lambda_utils/ecommerce/order_creation.py` | modified, unstaged | **YES** |
| `amplify/functions/shared/lambda_utils/ecommerce/initiation.py` | untracked | **YES** |
| `amplify/functions/shared/lambda_utils/ecommerce/finalization.py` | untracked | **YES** |
| `.kiro/specs/whatsapp-wix-commerce/{design,requirements,tasks}.md` | modified, unstaged | shared; read for intent, edit only where §4 says required |
| `.kiro/steering/META-BETA-REQUEST-EMAIL.md` | modified, unstaged | **NO** — unrelated workstream |
| `docs/execution/change-authority-matrix.md` | modified, unstaged | **NO** — append-only shared ledger; coordinate, never rewrite |
| `docs/execution/checkout-c1-c7-closure-matrix-20261001.md` | untracked | **NO — explicitly DO NOT TOUCH** |
| `docs/execution/checkout-consolidation-findings-20261001.md` | untracked | **NO** — the evidence base; read-only |
| `docs/execution/{first-deep-audit-20261001-codex,webhook-signature-verification-pattern-20261001}.md` | untracked | **NO** |
| `AGENTS.md`, `scripts/retired_url_equity.py`, `.kiro/settings/mcp.json.*.bak` | untracked | **NO** |
| `.agents/` | untracked | this file lives here |

Paths this task may **never** touch (other workstreams own them):
`amplify/functions/ecommerce/checkout/handler.py`, `amplify/functions/auth/**`,
`src/lib/customerAuth.ts`, `src/pages/**`, `src/components/**`, `_routes.json`,
`docs/execution/checkout-c1-c7-closure-matrix-20261001.md`.

---

## 1. Finding matrix

Status vocabulary, applied per finding. Each state is a strictly weaker claim than the one after
it, and a finding may not be described with a later state until the earlier ones hold.

`MERGED SOURCE` the fix is committed at HEAD · `TESTED` a named test exercises the real seam and
passes · `DEPLOYED` the code is inside the `live` alias package · `LIVE VERIFIED` exercised
against the live provider boundary · `OPEN` not closed · `BLOCKED` name the blocker and the exact
unblock · `SUPERSEDED` the finding no longer describes the code.

An additional state is needed and used, because it is the dominant state of this tree:
**`WORKING TREE ONLY`** — the fix exists in uncommitted/untracked local work, is not at HEAD, is
not deployed, and its tests currently fail.

**One note on the ID scheme, so nobody mis-resolves a citation.** `C1`/`C4` are the closure matrix's
collision ids. `N1`/`N2`/`N3` are the deep audit's new-gap ids. `D1`–`D3` and `D8` are `design.md`
decision records. `R2` and `R3` are `requirements.md` requirement ids and resolve cleanly
(`requirements.md:172` "An order exists only after payment is verified as paid"; `:241` "Webhook
ingestion integrity"). **`R1` does not resolve cleanly** — `requirements.md:151` R1 is "Configurable
vendor versions", which has nothing to do with payment integrity. The row below is keyed `R1/C1` as
the brief named it, and its content is C1. The requirement C1 actually serves is R2 (order only after
verified capture) together with R7.8 (`requirements.md:328-329`, mismatch must fail closed and raise
for staff). Recorded rather than silently re-labelled.

| ID | What it is | Status | Confirmed citations at `f7304eba` + working tree |
|---|---|---|---|
| **R1/C1** | Reconciliation outcome discarded at the call site; invoice / GST / Meta-Purchase / `order_status` fire whether or not an order exists | **WORKING TREE ONLY** — substantially closed in the dirty tree, 0 tests passing on it | `razorpay-webhook/handler.py:702` binds `outcome =`; `:703` routes on outcome; `:704-705` `if not outcome.get('hasOrder'): raise CaptureUnresolved(...)`; `:708` `_persist_commerce_paid`; `:709` `return` — the legacy invoice pipeline at `:712-760` is now unreachable from a commerce reference. Callee returns at `:505` / `:512` |
| **R2** | An order exists only after the provider verifies capture; exactly one order per capture; one provider transaction funds at most one order | **MERGED SOURCE** (ordering + claim logic) / **OPEN** (end-to-end, blocked by C4) | `order_creation.py:144-351` `reconcile_payment`; idempotent shortcut `:203-224` runs **before** the provider call, deliberately; claim/number `:292-351`; `_finish_numbering:354-384`. Spec: `requirements.md` R2 at `:172-234` |
| **R2 — classification** | `PROVIDER_UNAVAILABLE` sat in `NO_ORDER_OUTCOMES`, so a structural verification failure after capture reported `needs_human = False` and logged a warning | **WORKING TREE ONLY** — fixed, untested | `order_creation.py:69-71` `NO_ORDER_OUTCOMES` is now only `{NOT_PAID, ATTEMPT_NOT_PAYABLE}`; new `:76-79` `PAID_BUT_BLOCKED_OUTCOMES` holds `AMOUNT_MISMATCH, CURRENCY_MISMATCH, CUSTOMER_MISMATCH, IDENTITY_UNAVAILABLE, PROVIDER_PAYMENT_CONFLICT, UNKNOWN_REFERENCE, PROVIDER_UNAVAILABLE`; `needs_human` at `:105-107` now reads that set; `_blocked:137-141` escalates to `logger.error` for it; `customer_may_retry:109-117` hard-returns `False` |
| **C4** | Nothing in the tree ever **writes** `providerPaymentId` or `providerOrderId`, yet the verifier requires one, so every real capture raises `RazorpayUnavailable` → `PROVIDER_UNAVAILABLE` | **OPEN — unchanged, and the drafts do not close it** | Requirement: `razorpay_verify.py:159-178`, specifically `:175-178` `bound_payment = attempt.get("providerPaymentId")` / `bound_order = attempt.get("providerOrderId")` / `raise RazorpayUnavailable("payment attempt has no verified provider binding")`. Only producer in the tree: `payment_attempt.transition(..., provider_payment_id=, provider_order_id=)` at `:245-246`, `:279-282`. **Measured: zero callers pass either kwarg** (`grep` over `amplify/ scripts/ tests/`). The two `transition` call sites are `ecommerce/checkout/handler.py:276` and `initiation.py:67`, neither passes them |
| **C4 — the near miss** | `finalization.record_paid` writes the binding under a **different attribute name**, so even a successful paid write does not satisfy the verifier | **OPEN — new, and it is the specific reason C4 looks closed and is not** | `finalization.py:21` writes `verifiedProviderPaymentId = :provider`; `razorpay_verify.py:175` reads `providerPaymentId`. Two names, one fact. `finalization.py:50` then reads `verifiedProviderPaymentId` back, so the loop is internally consistent and externally broken |
| **R3/N3** | A payment decision compares `'captured'` raw, which is the comparison that misses `paid` | **OPEN** — the project's own AST gate is red | `razorpay-webhook/handler.py:595`, inside the new uncommitted `_verify_legacy_invoice_capture` (`:574-600`): `if (actual.get('id') != payment_id or actual.get('status') != 'captured' ...`. Gate: `tests/test_payment_vocabulary_at_decision_points.py:240` `FORBIDDEN_RAW = {"captured"}`, walk at `:260-278`. HEAD's copy of this file has **no** offender |
| **R3/N3 — gate blind spot** | The gate only inspects `ast.Eq`/`ast.NotEq`, so a raw-word decision written as `in (...)` is invisible to it | **OPEN — new** | Gate filter `tests/test_payment_vocabulary_at_decision_points.py:263` `if not any(isinstance(op, (ast.Eq, ast.NotEq)) ...)`. Live blind spot: `invoice-engine/handler.py:766` `if ex_status in ('paid','cancelled') or ex_ps in ('captured','refunded')` — the amount-change guard on `update_invoice`. It misses `disputed`, and the gate cannot see it. `cancel_invoice` at `:2302-2328` is already correct (`pay_status.rank(...) >= STATUS_RANK[CAPTURED]`, `:2322`) |
| **N1** | Public `/cart/` and `/account/sign-in/` serve 200 while the APIs they call 404 | **OPEN — and OUT OF SCOPE for this task** | `src/pages/cart.tsx:47`, `src/pages/account/sign-in.tsx:44`; zero `/ecommerce/*` and zero `/auth/customer-*` routes on API `zllr9lrg7j`. Owned by the frontend/auth workstreams; recorded only so a later step does not claim it |
| **N2** | The working tree fails tests that pass at HEAD | **OPEN — confirmed by direct run** | `.venv/bin/python -m pytest tests/ -q -k "razorpay or order_creation or order_keys or payment_attempt or payment_vocabulary or finalization or initiation or invoice"` → **20 failed, 320 passed**. Breakdown and root cause in §2 |
| **public-order-number** | The spec describes a 12-character order number; the code produces `WD-ORD-` + 8 CSPRNG symbols (15 chars) and keeps a legacy 12-char matcher | **OPEN — spec is stale, code is correct** | Code: `order_keys.py:109` `PUBLIC_ORDER_NUMBER_PREFIX = "WD-ORD-"`, `:128` `ENTROPY = 8`, `:131` `LENGTH = 15`, `:137` alphabet, `:139-142` current regex, `:153-156` legacy 12-char regex still resolves. Spec: `requirements.md:196` ("12 characters") and `:211` ("The 12-character order number SHALL be reserved…"). The original user instruction (PR #159) says preserve `WD-ORD-` + eight, and that historical 12-character numbers must still resolve — so the **spec** is the thing that is wrong |
| **forward-only-stages** | `finalizationStage` has no monotonic guard, so a redelivery or a retry can move an order's finalization state **backwards** | **OPEN — new** | `finalization.py:29-40` `_stage` conditions only on `#s = :paid`; no rank comparison on `finalizationStage`. `accept_paid:76-77` re-stages `INTERNAL_ORDER_CREATED` on **every** delivery, including an idempotent adopt, and `:80-82` / `:93-95` can then set `NEEDS_RECONCILIATION` over a previously reached `EXTERNAL_PAYMENT_RECORDED`. The call path reaches it on every redelivery: `handler.py:703-708` runs `_persist_commerce_paid` whenever `hasOrder` is true, which includes `ORDER_ALREADY_EXISTS` |
| **forward-only-stages — magic rank** | `record_paid` hardcodes the rank value instead of using the project's own monotonic primitive | **OPEN — new, low severity today, latent** | `finalization.py:20` writes `attemptRank = :rank` with `:rank': 100` at `:25`, and its `ConditionExpression` at `:22-23` does **not** include `payment_attempt.condition_expression()` (`payment_attempt.py:120-123`, `RANK_ATTRIBUTE = "attemptRank"` at `:121`). Benign only because `PAYMENT_PAID` is the maximum rank (`payment_attempt.py:104`). It silently diverges the moment `_RANK` changes |
| **D1** | Extend the Python fleet; no Node.js API | **MERGED SOURCE — honoured** | `design.md:23-47`. All owned work is Python in `amplify/functions/`; no new runtime introduced |
| **D2** | Wix OAuth `client_credentials`, API key as migration fallback | **not exercised by this task** | `design.md:48-63`. Touched only through `wix_writeback` → `wix_ecom._request`, which this task must not reach while writeback is disabled |
| **D3** | Keep the homegrown invoice engine; Wix receipts only if the site offers them (it does not — `invoices/v2` → 404) | **MERGED SOURCE — and it is the constraint that shapes `accept_paid`** | `design.md:64-...`, cross-referenced at `:111` and `:514`. `finalization.accept_paid:42-46` docstring: "This never creates a payable invoice." The commerce path must **not** reuse `_post_payment_handler`, which creates one — and in the working tree it does not: `handler.py:709` returns before reaching `:755` |
| **D8** | Velo and the Wix-native PSP path are abandoned; one active architecture; no dual-mode router | **MERGED SOURCE at working tree** (spec diff), prototypes already deleted at HEAD | `design.md` diff adds D8; runtime label `CHECKOUT_MODE = "WIX_HEADLESS"` is provenance, not a switch. `order_creation.py:181-182` and `finalization.py:48` both refuse any other `checkoutMode` |

### 1.1 Line-number drift against the inherited facts

The step brief carried known facts to confirm. Confirmed, with corrected numbers:

| Inherited fact | Status now |
|---|---|
| `_create_order_for_captured_payment` called **for effect only** at `:663-664`, return value never bound | **SUPERSEDED by the working tree.** It is bound at `:702`. The finding was true at HEAD's ancestor and is no longer true locally |
| Ungated side effects at `:667-673`, `:676`, `:681` | **SUPERSEDED locally.** Those effects now sit at `:722-760`, downstream of a `return` at `:709`, reachable only via the legacy branch |
| Callee returns at `order_creation.py:505 / :517` | **DRIFTED.** `order_creation.py` is now 402 lines. The callee is `razorpay-webhook/handler.py`, whose returns are `:505` (`outcome.as_dict()`) and `:512` (`RECONCILIATION_ERROR`) |
| `NO_ORDER_OUTCOMES` at `:70-73` | **DRIFTED and CHANGED.** Now `:69-71`, and its membership is reduced to two outcomes |
| `needs_human` at `:105-107` | **Line-accurate, semantics changed.** Still `:105-107`; now reads `PAID_BUT_BLOCKED_OUTCOMES` |
| `razorpay_verify.py:159-178` requires a provider binding | **CONFIRMED verbatim.** `:159` signature, `:175-178` the requirement and the raise |
| Nothing writes `providerPaymentId` / `providerOrderId` | **CONFIRMED by tree-wide grep.** Only `payment_attempt.transition` can, and no caller asks it to |
| `OrderTable` at 0 rows is the only reason this has not happened | **Not re-measured this pass** (a `Scan ... Select=COUNT` would be a read, but the deep audit measured 0 at `8807db0e` and nothing has deployed since; `wecare-razorpay-webhook:live` is still v45). Treat as unchanged-but-unverified |

---

## 2. N2 in detail — why 20 tests fail, and what it tells the implementer

Measured, not inferred:

| Test file | Failures |
|---|---:|
| `tests/test_razorpay_webhook_captured_gating.py` | 12 |
| `tests/test_razorpay_webhook_order_creation.py` | 6 |
| `tests/test_order_creation.py::test_reconciliation_cannot_charge_the_customer` | 1 |
| `tests/test_payment_vocabulary_at_decision_points.py::...[razorpay-webhook/handler.py-payment_status]` | 1 |

19 of the 20 share one root cause, and it is **architectural, not a fixture typo**:

```
ERROR order_creation.py:139 {"event":"reconciliation_blocked","outcome":"PROVIDER_UNAVAILABLE",
                             "reason":"could not load the payment attempt: KeyError"}
ERROR handler.py:493       {"alert":"PAID_BUT_NO_ORDER","outcome":"PROVIDER_UNAVAILABLE",...}
E  AssertionError: assert 'PROVIDER_UNAVAILABLE' == 'CURRENCY_MISMATCH'
```

The tests encode the **old data model**, in which the authoritative amount and currency live on the
`PAYREF#` index row in the commerce-keys table. `tests/test_razorpay_webhook_order_creation.py:41-46`
seeds exactly that, and `:49-57` patches `dynamodb` so **every** `Table(...)` call returns the one
keys table. The working tree's `_load_attempt` (`handler.py:460-469`) now does a second hop —
`order_keys.resolve_payment_reference` → `PaymentAttemptsTable.get_item(Key={'paymentAttemptId':…})`
— against a fake table keyed on `orderId`, which raises `KeyError`. `initiation.py:75` states the
new rule outright: *"PAYREF is an index only; all authoritative financial fields live on the
attempt."*

So the fixtures must become two-table, with the attempt seeded under `paymentAttemptId`. That is a
required, deliberate change, not a workaround.

**Two things the failures prove about direction, and they are reassuring.** Every failure lands on
`PROVIDER_UNAVAILABLE` + `needsHuman: true` + `PAID_BUT_NO_ORDER`. The in-flight code refuses orders
it cannot verify; it does not mint unverified ones. And the one failure to read most carefully is
`test_reconciliation_cannot_charge_the_customer` — the R7.4 allowlist whose entire job is to notice
a new outbound call. It fails for the same fixture reason, **not** because a money-movement call was
added, but that must be re-confirmed after the fixtures are fixed rather than assumed.

**The tests currently cannot see C4 at all.** `tests/test_razorpay_webhook_order_creation.py:51-52`
patches `razorpay_verify.verifier_for_event` and returns a stub verifier, so the binding requirement
at `razorpay_verify.py:175-178` is never executed. A green suite is therefore not evidence against
C4, by construction.

---

## 3. Reconciliation decision per dirty / untracked file

| File | Decision | Why |
|---|---|---|
| `amplify/functions/payments/razorpay-webhook/handler.py` | **BUILD ON** | The restructure is correct and is the single largest piece of R1/C1 already done: the outcome is bound (`:702`), a missing order fails closed by raising (`:705`), the commerce path returns before the payable-invoice pipeline (`:709`), and the legacy path now demands a stored invoice association plus an authenticated Razorpay read (`:574-600`) instead of inferring one. Keep all of it. Three defects to fix on top: the raw `'captured'` at `:595`; routing on the raw string `UNKNOWN_REFERENCE` at `:703` (§4.3); and `_persist_commerce_paid` re-running on `ORDER_ALREADY_EXISTS` (§4.4) |
| `amplify/functions/shared/lambda_utils/ecommerce/order_creation.py` | **ADOPT AS-IS** | The outcome split into `NO_ORDER_OUTCOMES` / `PAID_BUT_BLOCKED_OUTCOMES` (`:69-79`) is exactly recommendation 3 of the findings report and exactly what makes `needs_human` honest. `customer_may_retry` returning hard `False` (`:109-117`) is correct for a verifier that cannot distinguish authorized from pending. The new `persist_paid` hook (`:150`, `:284-289`) is the right seam: it persists paid state **before** claiming an order id, so a crash between the two is recoverable rather than an order with no paid attempt. No rework identified |
| `amplify/functions/shared/lambda_utils/ecommerce/finalization.py` | **BUILD ON — three specific reworks** | The shape is right: paid state persists separately from recoverable finalization, the order row is written conditionally (`:67`), a conditional-failure adopt re-reads and compares five binding fields (`:69-75`) rather than assuming, and an unavailable Wix contract parks at `NEEDS_RECONCILIATION` instead of losing the paid order (`:80-82`, `:93-95`). Reworks: (1) the attribute-name split — write the binding under the name `razorpay_verify` reads, or make the verifier read this one, but one name only (`:21` vs `razorpay_verify.py:175`); (2) `_stage` needs a forward-only guard (`:29-40`); (3) `record_paid` must use `payment_attempt.condition_expression()` and `payment_attempt.rank(PAYMENT_PAID)` instead of the literal `100` (`:20-25`) |
| `amplify/functions/shared/lambda_utils/ecommerce/initiation.py` | **ADOPT AS-IS as a module; it has ZERO callers and that is the problem** | Measured: no file in `amplify/`, `scripts/` or `tests/` imports it. The content is good — a single `TransactWriteItems` writing request key + `PAYREF#` + attempt atomically (`:82-90`), a `claim_send` durable boundary before any send (`:95-103`), request-key idempotency bound to an intent fingerprint so a reused `requestId` with different contents raises `InitiationConflict` (`:44-45`), and ownership enforced through `authorize_resource` (`:41`, `:49`). Both drafts import cleanly against the real `lambda_utils`. **But its natural caller is `amplify/functions/ecommerce/checkout/handler.py`, which this task must not touch** — see §4.1, which is the central scoping problem of this closure |
| `.kiro/specs/whatsapp-wix-commerce/design.md` | **ADOPT AS-IS** | Adds D8 (one active architecture, Velo/PSP abandoned) and corrects the decision count. Nothing here needs editing for this task |
| `.kiro/specs/whatsapp-wix-commerce/requirements.md` | **ADOPT, then ONE required edit** | The 2026-10-01 header edit is correct. The required edit is the public-order-number drift at `:196` and `:211` — the spec says 12 characters, the shipped format is `WD-ORD-` + 8. Leaving it means the next reader treats correct code as a violation |
| `.kiro/specs/whatsapp-wix-commerce/tasks.md` | **ADOPT AS-IS** | The new status vocabulary (`SOURCE_IMPLEMENTED` → `TESTED_OFFLINE` → `DEPLOYED` → `VERIFIED_READ_ONLY` → `LIVE_PAYMENT_VERIFIED`) is the right instrument and this audit uses a compatible one. Status annotations may need appending once work lands; no correction needed now |
| `.kiro/steering/META-BETA-REQUEST-EMAIL.md`, `docs/execution/change-authority-matrix.md`, the four untracked `docs/execution/*.md`, `AGENTS.md`, `scripts/retired_url_equity.py`, `.kiro/settings/mcp.json.*.bak` | **LEAVE EXACTLY AS FOUND** | Not owned. `change-authority-matrix.md` will need an **appended** entry when work lands; it must not be rewritten, and another session is already modifying it |

---

## 4. What remains, and the decisions a later step has to make

### 4.1 C4 cannot be fully closed inside owned scope by the obvious route

The verifier needs `providerPaymentId` or `providerOrderId` on the attempt **before** the webhook
arrives. The only place that can write it pre-capture is payment initiation, which lives in
`ecommerce/checkout/handler.py` — not owned. `initiation.py` is owned but has no caller.

Two routes, and they are not equivalent:

**(a) Bind inside the webhook, from an authenticated provider read.** Owned end to end, and the
precedent already exists in owned code: `_verify_legacy_invoice_capture` (`handler.py:586-599`)
reads `/payments/<id>` and requires the provider's own `notes.referenceId` to equal the stored
reference before accepting anything. Applying the same shape to the commerce path means the binding
is derived from an authenticated Razorpay response rather than from the webhook body — which is the
property `razorpay_verify`'s docstring (`:14-26`) actually demands. The event's payment id is used
only as a *lookup key*, never as evidence.

**(b) Add a `bind_provider_payment` function to `initiation.py` for the checkout workstream to call
later.** Correct long-term, and it is the shape the verifier docstring describes — but it does not
close C4 now, because nothing calls it, and it makes this closure depend on another workstream.

**Recommendation: do both, (a) as the closure and (b) as the forward path.** (a) is what makes a
real capture produce an order today; (b) is what lets the binding be established at initiation once
checkout is wired, at which point (a) becomes a confirmation rather than the sole source. Whichever
is chosen, **the attribute name must be unified** — today `finalization.py:21` writes
`verifiedProviderPaymentId` and `razorpay_verify.py:175` reads `providerPaymentId`, and that
mismatch alone would keep C4 open even after a binding is written.

### 4.2 `UNKNOWN_REFERENCE` is doing two incompatible jobs

`order_creation.reconcile_payment` returns `UNKNOWN_REFERENCE` for three different facts: no
reference on the event (`:168`), no attempt row for this reference (`:176-181`), and an attempt that
carries no id (`:189`). The handler then uses it as the **legacy-routing signal** at `handler.py:703`.

So "this reference belongs to a legacy invoice, not to commerce" and "this reference IS commerce and
we could not resolve it" are the same value. A lost or lagging `PAYREF#` index row therefore routes a
paid commerce capture into the legacy invoice verifier, which raises
`CaptureUnresolved('UNKNOWN_OR_AMBIGUOUS_INVOICE')`. Fail-closed in effect — no false order is created
— and the `PAID_BUT_NO_ORDER` alert does fire from `order_creation._blocked` because
`UNKNOWN_REFERENCE` is in `PAID_BUT_BLOCKED_OUTCOMES`. But the routing is semantically wrong and it
is the kind of wrong that reads as correct. A distinct outcome (`NOT_A_COMMERCE_REFERENCE`, returned
only when the reference resolves to nothing *and* the event carries a reference at all) separates the
two.

### 4.3 A permanent mismatch currently retries forever

`handler.py:705` raises `CaptureUnresolved` for every non-`hasOrder` outcome. That propagates to the
outer `except Exception` (`:283-287`), which returns **500** and deliberately does not complete the
dedup lease — so Razorpay retries. That is right for `PROVIDER_UNAVAILABLE` or
`IDENTITY_UNAVAILABLE`. It is wrong for `AMOUNT_MISMATCH` and `CURRENCY_MISMATCH`, which can never
resolve: the result is an unbounded retry loop plus one `PAID_BUT_NO_ORDER` alert per delivery.
Decide per outcome whether the correct answer is retry (500, lease open) or record-and-alarm (200,
lease closed, staff queue). The raw audit row is written before any of this
(`_log_webhook_event`, `:148`), so closing the lease loses no evidence.

### 4.4 A redelivery re-enters finalization

`handler.py:703-708` calls `_persist_commerce_paid` whenever `hasOrder` is true, and that includes
`ORDER_ALREADY_EXISTS`. `accept_paid` then re-runs `record_paid`, re-stages `INTERNAL_ORDER_CREATED`
(`finalization.py:76-77`), and — once writeback is enabled — re-enters `create_wix_order`. The order
row itself is safe (`attribute_not_exists(orderId)` at `:67`, with a five-field comparison on
conditional failure at `:69-75`), and `wix_writeback` has its own guards
(`WixWouldCharge`, `WixEndpointNotAllowed`, readback-pending markers). But "exactly ONE set of
purchase side effects" is the stated goal, and re-entry on every redelivery is how a second set
happens. A forward-only `finalizationStage` guard plus an early return when the stage is already at
or past the target is the fix, and it is the same monotonic discipline
`payment_status.should_apply` and `payment_attempt.condition_expression()` already implement
elsewhere in this repo.

### 4.5 Deployment facts a later step must not assume away

- `wecare-razorpay-webhook:live` is **v45**. None of this work is deployed. Per
  `lambda-snapstart-deploy.md`, a payments change is not live until a new version is published and
  the `live` alias moves.
- The live function's environment has **no** `ORDERS_TABLE`, `COMMERCE_KEYS_TABLE`,
  `PAYMENT_ATTEMPTS_TABLE` or `RAZORPAY_SECRET_ID`. Code defaults cover the table names
  (`handler.py:618-619`, `razorpay_verify.py:56`), so this is survivable, but it means the names are
  only in code — add them to `config/lambda-env-manifest.json` rather than relying on a default.
- IAM is adequate and was measured, not assumed. `wecare-digital-lambda-role` grants
  `GetItem/PutItem/UpdateItem/DeleteItem/Query/Scan/BatchGetItem/BatchWriteItem/DescribeTable` on
  `table/stack-wecare-digital-*` and `.../index/*`. `simulate-principal-policy` reports
  `dynamodb:PutItem` **allowed**, `dynamodb:UpdateItem` **allowed**, and
  `dynamodb:ConditionCheckItem` **implicitDeny**. `initiation.reserve` uses three `Put` actions and
  no `ConditionCheck`, so it is authorized today — but **adding a `ConditionCheck` item to that
  transaction would be denied**, and the denial would surface as a transaction failure, not as a
  permissions error anyone was expecting.
- `initiation.py` and `finalization.py` have **zero test files**. `grep -rln` over `tests/` returns
  no file naming either module. Every guard described in §3 for those two modules is currently
  unverified.

---

## 5. Honest status summary

| Claim | Verdict |
|---|---|
| MERGED SOURCE | R2's ordering/claim logic, D1, D3, D8's deletions, `order_keys` number reservation, `razorpay_verify`'s provider-only evidence rule |
| WORKING TREE ONLY | R1/C1 (call-site binding), R2's outcome reclassification, the legacy-capture verifier, `finalization`, `initiation` |
| TESTED | **Nothing in this closure.** 20 relevant tests fail; the ones that pass stub the seam that breaks |
| DEPLOYED | **Nothing.** `live` v45 predates all of it |
| LIVE VERIFIED | **Nothing.** No live payment has been taken through this path, and doing so is outside this instruction's authority |
| OPEN | C4 (+ the attribute-name split), R3/N3 (+ the gate blind spot), public-order-number, forward-only-stages, §4.2, §4.3, §4.4, zero tests on the two new modules |
| BLOCKED | C4's *initiation-side* half — blocker: `ecommerce/checkout/handler.py` is owned by another workstream. Unblock: either route (a) in §4.1 inside the webhook, or a cross-workstream handoff for route (b) |
| SUPERSEDED | The `:663-664` unbound-call citation and the `:667-681` ungated-side-effect citations; `NO_ORDER_OUTCOMES` containing `PROVIDER_UNAVAILABLE`; "`PROVIDER_UNAVAILABLE` reports `needs_human=False`" |

**The one sentence that matters.** The dangerous combination the closure matrix was created for —
money taken, invoice marked paid, GST invoice sent, Meta Purchase fired, customer told the order is
confirmed, no order in existence, logged as a warning — is **no longer reachable in the working
tree**: the outcome is bound, a missing order raises, and the commerce path returns before the
payable-invoice pipeline. What has replaced it is a different and far safer failure: because C4 is
untouched, a real capture reaches `PROVIDER_UNAVAILABLE`, raises `CaptureUnresolved`, returns 500,
leaves the dedup lease open, and emits `PAID_BUT_NO_ORDER` on every retry — paid, no order, loudly.
That is the correct direction and it is not a finished state. `OrderTable` at 0 rows and
`wecare-razorpay-webhook:live` still at v45 mean none of it is live either way.
