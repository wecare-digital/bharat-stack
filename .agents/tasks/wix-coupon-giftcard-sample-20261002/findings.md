# Findings — Wix coupon + gift card sample

Implementation of `design.md` revision 8 against `plan.md`, in worktree
`wix-coupon-giftcard-sample-20261002` on branch `wix-coupon-giftcard-sample-20261002`, based on
`stack` at `32b632e3`. Three commits: `2ec1b7f1` the feature, `d7ef5583` and `4b4a889b` the two
review-fix iterations. Code review verdict **APPROVED** (`code-review.json`), two INFORMATIONAL
observations carried forward, nothing blocking.

**No credential value appears in this file.** The only credential reference is the secret *name*
`wecare/wix/headless-api-key`. No gift-card code, no idempotency key and no shared digest fragment
appears in clear anywhere below — the coupon code does, in full, and §3 says why that is correct.

Companion documents: `verification.md` (what was run and what it reported), `design.md` rev 8 (the
full analysis), `wix-native-decision-memo.md` (the one-page owner view),
`docs/execution/wix-contract-verification-20261002.md` (the four contract verdict rows).

---

## 1. The two original HIGH resolutions

Both HIGHs came from the first design review (`design-review.json`, `counts.HIGH = 2`). Both are
resolved in source, and the second re-review confirmed all 13 of that pass's findings resolved
against the tree rather than against the design's own dispositions.

### H1 — the gift-card code is now HMAC-keyed under the existing `code_pepper`

**The defect.** The design derived the gift-card code as an *unkeyed* function of `reference_id`.
This repository's standing payments rule states `reference_id` is not a secret and may be logged in
full — and it is, deliberately, as the correlation id that lets a payment log line be traced with no
masked field. So the clear bearer-value code was recoverable from any payment log, and every other
bearer-value control in the design (one expression, reduced to last four, nothing to log with,
renderer masking) was defeated by the derivation itself.

**The fix, as built.** `wix_gift_cards.card_code(*, reference_id, pepper)` is keyed:

```python
mac = hmac.new(pepper.encode("utf-8"),
               CODE_DOMAIN_TAG + reference_id.encode("utf-8"), sha256)
return ("WDGC" + mac.hexdigest()[:16]).upper()
```

Four properties worth reading deliberately:

- **The pepper is the one that already exists.** `wecare/wix/giftcard-spi:code_pepper` — the same
  field `gift_card_store.code_hash` HMACs under, with `PEPPER_FIELD = "code_pepper"` already in the
  store and already granted to both gift-card roles by `scripts/provision_gift_cards_roles.py`. No
  new secret, no new field, no new grant. One key, two purposes, **domain-separated** by
  `CODE_DOMAIN_TAG` so the two derivations cannot collide.
- **It is read by reference, at request time.** The adapter takes the pepper as a parameter and
  holds no client; `wix_gift_cards.py` imports nothing that leaves the process and reads no secret
  itself. It refuses outright — `WixGiftCardError("A_PEPPER_IS_REQUIRED")` — rather than falling
  back to an unkeyed derivation.
- **Determinism survives, which is what resolve-before-create needs.** The pepper is fixed per
  environment, so the derivation is still stable across retries. The one case where it is not is a
  pepper rotation, and that case is covered by `idempotency_key` being deliberately
  **rotation-invariant**: it stays unkeyed, because an idempotency key is not bearer value — Wix
  answers a replayed key with the card the reference already identifies — and an unkeyed key is
  what stops a post-rotation replay minting a second card.
- **20 characters, Wix's documented maximum.** 16 hex digits is 64 bits of margin where the
  original 12 would have been 48, and Wix permits the extra four at no cost.

**Pinned by.** `test_the_keyed_code_is_not_recoverable_from_a_logged_reference_id` asserts the
property in **both** directions, and asserts the positive line — that the unkeyed `demo_code`
**fails** that same test — which is what makes the two negative assertions capable of failing at
all. The old unkeyed derivation survives only as `demo_code`, renamed so the name states why it is
demo-only, and fenced by `test_no_file_under_amplify_references_the_demo_only_derivation`, an AST
walk over `ast.Attribute`, `ast.Name` and `ast.ImportFrom` (deliberately not over
`FunctionDef.name`, so the defining module needs no exemption).

**Carried forward, from the review (I2).** `demo_code`'s docstring names the digest fragment shared
between `demo_code` and `idempotency_key` for the default demo reference, so that one demo code is
reconstructable from source. That is consistent with `demo_code` being non-bearer and nothing is
spendable — no real card exists and the transport is stubbed unconditionally — but read the fence
correctly: it is a **reference** gate, not secrecy. It stops production calling the function. It
cannot make the value secret.

### H2 — the vacuous AST assertion is replaced by a runtime-asserted item-shape gate

**The defect.** The design proposed extending the AST reach-enumeration test with an `elif` arm
asserting that the rendered `transact_write_items` call contains both `TableName` and `Key`. Read
from the tree, that gate uses `ast.unparse(node)` on the **call** node, and the items are assembled
in separate assignments, so the call renders as

```
table.meta.client.transact_write_items(TransactItems=[card_item, claim_item])
```

which contains neither string. The assertion would have **failed against correct post-fix code** —
the same shape as an earlier revision's finding — and the natural repair is to delete the arm,
which would leave the module's only balance-moving write invisible to the one test that enumerates
reach.

**The fix, as built: the two halves are split, and each says which half it owns.**

*Runtime half* — `assert_transaction_items_are_exact_key_updates(store)` in
`tests/test_gift_card_store.py`, where the item **contents** actually exist. For every recorded
transaction it asserts each item's key set is exactly `{"Update"}` (which is what forbids a later
`Put`, `Delete` or `ConditionCheck` arriving without a design change), a non-empty `TableName`, a
non-empty `Key`, and **no** `IndexName`. Two deliberate details:

- it reads `calls` (the **attempt** log), not `applied` (the **outcome** log), so a *cancelled*
  attempt is still shape-checked — and the concurrency test is the caller that exercises that
  choice, since its recording contains thread B's cancelled transaction;
- it **refuses an empty recording first**, so it can never pass vacuously. A helper that passes
  vacuously is worse than no helper: it reports a guarantee it never checked.

*AST half* — `test_the_transaction_has_exactly_one_call_site_and_two_callers`, presence and
location only. Exactly one `transact_write_items` call in the module; its owning `FunctionDef` is
`_transact_with_retry`, so the bounded retry, the jitter and the injected sleeper exist once rather
than per committer; and `_transact_with_retry`'s callers are exactly
`{_commit_redemption, _commit_void}`. That third fact needs its own `ast.Name` predicate, because
the pre-existing gate finds only attribute calls. The test's own docstring states that nothing here
`ast.unparse`s the transaction call looking for `TableName`/`Key`, and why — so neither half is
later deleted as redundant.

The pre-existing `test_every_dynamodb_access_is_an_exact_key_operation_or_the_status_index_query` is
otherwise unchanged: zero `scan`, exactly one `query`, on `status-index`, owned by `list_by_status`.

---

## 2. Open-MEDIUM and NIT dispositions

Three MEDIUMs and four NITs were open from the second design review (`design-review2.json`,
`counts: {high: 0, medium: 3, nit: 4}`). All seven are disposed of below. The design is **frozen at
revision 8**, so the rule applied is: a NIT asking for an edit to the frozen design document is
*dropped with a note*; a NIT correcting a fact an implementer acts on is *applied in code*.

### MEDIUM 1 — `FakeTable.arm_failure` could not express "fail the same operation twice" → **fixed with a real mechanism**

`_fail_if_armed` consumed the arm with `self.fail_on.pop(operation, None)`, so two `arm_failure`
calls before two operations produced **one** failure, and the test's second `pytest.raises` then
failed against **correct** code. `arm_failure(operation, exc, *, times=1)` now holds a decrementing
counter, popping only at `remaining <= 1`, so "armed twice" produces two genuine failures.

`times=` was chosen over re-arming between the two `void()` calls because it keeps the arming
visible **at the arming site** rather than hiding a re-arm in the middle of a test body, and it
makes the test's own narrative literally true. The default keeps all seven importers of the fake
unaffected — proved by the 315-pass baseline staying 315 immediately after the fake was edited and
before anything else changed. The citation the design got wrong is recorded in the docstring: the
`pop` is in **`_fail_if_armed`**, not in `arm_failure`.

Exercised by `test_a_void_credit_that_fails_twice_still_returns_the_balance_exactly_once`, which
arms `times=2` and asserts the balance is untouched after **each** of the two failures.

### MEDIUM 2 — `_committer_of` / `_is_balance_move` were named in the design and absent from the tree → **implemented**

Both now live in `tests/test_gift_card_store.py` beside
`assert_transaction_items_are_exact_key_updates`, and are imported **by name** from
`tests/test_gift_card_redeem_concurrency.py`:

```python
def _is_balance_move(call: tuple) -> bool      # matches update_item OR transact_write_items
def _committer_of(kwargs: dict) -> str         # "redeem" | "void", RAISES otherwise
def _committers(store: FakeTable) -> set
```

`_committer_of` **raises `AssertionError`** for a transaction that moves no balance rather than
returning a sentinel. A sentinel would be silently absorbed into a set comparison, so a third kind
of transaction appearing on this path would pass unnoticed — the opposite of what a committer-set
assertion is for.

`_is_balance_move` reads `UpdateExpression` **text** in both representations, so one predicate
reads both logs and it does not latch on `_record_balance_after`'s `SET #observed`. Matching only
`update_item` would have silently stopped matching anything the moment the money moved into a
transaction, which is the failure mode it exists to avoid.

The "neither committer is silently missing" property is measured **two** independent ways, so it
does not rest on the helper alone: structurally by
`test_the_transaction_has_exactly_one_call_site_and_two_callers` (§1 H2), and at runtime by the
committer-set assertions on all six callers (§2 MEDIUM 3).

### MEDIUM 3 — §5.5's stale "one definition, four callers" → **the authoritative six-row table is followed**

Taking the stale sentence literally would leave two transaction-driving tests unchecked while §7
reported item shape as runtime-covered by six. The six callers, each asserting `seen >= 1` or
`seen >= 2` plus a committer set and **no literal transaction total**:

| Caller | Assertion | Committers |
|---|---|---|
| `test_a_second_redeem_for_the_same_payment_attempt_does_not_move_the_balance` | `seen >= 1` | `{"redeem"}` |
| `test_the_settle_and_the_balance_move_are_one_commit` | `seen >= 1` | `{"redeem"}` |
| `test_the_credit_and_the_credited_flag_are_one_commit` | `seen >= 2` | `{"redeem","void"}` |
| `test_a_void_whose_credit_failed_is_completed_by_a_retry_not_refused` | `seen >= 2` | `{"redeem","void"}` |
| `test_a_void_credit_that_fails_twice_still_returns_the_balance_exactly_once` | `seen >= 2` | `{"redeem","void"}` |
| `test_two_concurrent_redeems_for_one_payment_attempt_debit_once` | `seen >= 2` | `{"redeem"}` |

Checked mechanically: `grep -nE 'seen == [0-9]'` is **empty** across `tests/` (no literal
transaction total survived), and the helper name appears **7** times in the file — the definition,
five in-file callers and one docstring reference. `seen >= n` rather than `seen == n` is the point:
a count is not the property, and a literal total is the instrument that broke in the first place.

### The four NITs

| NIT | Disposition |
|---|---|
| **4** — §16's stale "four transaction-driving tests" lacks the superseded annotation its neighbours carry | **Dropped**, design frozen at rev 8. Superseded in effect rather than in prose: the implementation follows §5.5's numbered **six**-row table, and six callers assert it |
| **5** — §8's Modified row dates its own previous count to the wrong revision ("revision 8" for what was revision 7's seven updates) | **Dropped**, design frozen. A dating error in a changelog row changes no code |
| **6** — three §5.5 line citations off by two or three | **Applied.** Re-measured in this worktree at `32b632e3`: the `:neg == -40000` comparison is at `:289` (the design said `:286`, which is `assert len(decrements) == 1`); the floor test spans `:276-294`, not `:274-290`; the SPI exact-action assertion is at `:295` and covers `AdvanceGiftCardStageOnAPaymentAttempt` on **PaymentAttemptsTable**, not the ledger — which is why `test_the_ledger_statements_grant_exactly_what_the_store_needs_and_no_more` was added. Both substantive claims underneath those citations were correct |
| **7** — `_CreditThrottles` / `_MarkerWriteFails` caller fates unstated | **Applied.** Both fault injectors are **deleted**, with their call sites mapped: `_CreditThrottles` (`:631`) was used only at `:675` and `:714`, both rewritten to arm the transaction, so it lost **both** callers; `_MarkerWriteFails` (`:394`) was used at `:440` and `:745` (both retired-and-replaced) and `:478` (rewritten to be driven by a settled claim), so it lost **all three**. A fault injector with no caller misleads the next reader exactly as a constant with no caller does |

### And the two findings from the code-review passes, for completeness

| # | Severity | Finding | Fix |
|---|---|---|---|
| M4 | MEDIUM, blocking | the demo cited `test_the_aws_refusal_hook_is_armed_before_the_first_leg` as the measurement of its containment-time arming, and that test existed nowhere in the tree | the cited test is **implemented** under exactly that name at `tests/test_demo_coupon_giftcard_sample.py:116` — fixed the right way round, by writing the test rather than deleting the citation. A mutation run (`verification.md` §0b) shows the pre-existing containment test staying **green** on the mutant while the new one fails `assert 0 == 1` |
| L4 | LOW | the coupon idempotency docstring justified `coupon_store` with "no `idempotencyKey` **and no read-by-code**", contradicting row V2b of this change's own contract transcript | the docstring now rests on the `idempotencyKey` absence alone and states that read-by-code is deliberately **not** part of the rationale, citing V2b. `plan.md`'s two remaining stale copies are **named** in `verification.md` rather than quietly edited — the plan is the dated artefact the build was run from |

Earlier code-review iteration (M1–M3, L1–L3) is tabulated in `verification.md` §0a: the
tautological AWS-call count, the unrestored `urlopen`, the hooks outliving the session, the
disclosed idempotency key, the fetch count, and `credit()`'s lost `once_key` rationale.

---

## 3. What was built — coupon = Option B, gift cards = Wix-native, as the code actually does it

Two verdicts, and the asymmetry between them is the whole decision.

| Feature | Decision | The one measured fact it rests on |
|---|---|---|
| **Coupons** | **(B)** — Wix does the discount arithmetic; we keep a small issuance ledger | Wix's `Create Coupon` has **no `idempotencyKey`** and **no read-by-code** |
| **Gift cards** | **Wix-native** — Wix is the balance authority | `Create Gift Card` **has** a server-side `idempotencyKey`, and `Query Gift Cards` documents **`$eq` on `code`** |

### Coupons, Option B, as built

- **Wix is the arithmetic authority. Nothing in our code computes a discount.** The handler composes
  a `specification` and posts it; Wix applies it.
- **Our ledger is a recovery mechanism, not an authority.** Because `Create Coupon` has no
  idempotency key and no way to look a coupon up by the code we chose, a successful create whose
  response is lost would leave a live Wix coupon whose id we cannot recover. `coupon_store.claim`'s
  conditional put on `COUPON#<codeUpper>` **is** that recovery: a replay loses the claim, issues no
  second Wix create, and keeps the id the first attempt recorded.
- **Convergence means "no second coupon", not "the replay returns the existing one".** The replay
  test drives `handler.handler` rather than `_create`, so it measures the status a caller actually
  gets: **409 `CODE_ALREADY_EXISTS`**, the row keeping the first attempt's `wixCouponId`, **one**
  create on the wire, **one** definition row.
- **The mirror state is explicit.** The row is written `wixMirrorState = PENDING_WIX` and moved to
  `MIRRORED` by `mark_mirrored` once Wix answers. The handler answers **201** on a mirrored row and
  **202** on a row still `PENDING_WIX` — every Wix failure of every status leaves the row
  `PENDING_WIX` and answers 202, and `evaluate` refuses a `PENDING_WIX` coupon.
- **`validate` answers a verdict, never an amount.** `ELIGIBLE` / `UNKNOWN_CODE` / `NOT_ACTIVE` /
  `NOT_STARTED` / `EXPIRED` / `USAGE_LIMIT_REACHED` and the rest. That is a security boundary rather
  than a style choice: an endpoint that returned a figure would become a number a browser could
  quote.
- **Money shape on the Wix side is measured, not assumed.** Coupon money fields are JSON **ints in
  whole rupees** (`moneyOffAmount: 123456` for ₹1,23,456.00, by `//`), while `startTime` in the same
  body is a **quoted** string-encoded int64 — which is exactly why the string convention
  demonstrably does not extend to the money fields. `_whole_rupee_paise` refuses a paise amount that
  is not a whole number of rupees (the demo exits `2` on `--coupon-money-off-paise 12345`).
- **The coupon code prints in full, deliberately.** It is broadcast marketing material. It is not
  bearer value in the gift-card sense: it carries a usage limit, a per-customer limit and a
  minimum-subtotal floor, and Wix enforces all three.

### Gift cards, Wix-native, as built

`amplify/functions/shared/lambda_utils/ecommerce/wix_gift_cards.py` — four calls, an injected
request callable, **no logger, no `logging` import, no `print(`** (asserted by AST, because the
paragraph explaining the rule necessarily contains the word), no client, no secret read, and
**deliberately unwired**: nothing under `amplify/` imports it.

- **Wix owns the balance.** `balance` is `readOnly` on Wix's side — we could not move it if we
  tried. Redemption is a Wix-side event; our resolve path **reads** it.
- **Resolve-before-create consumes exactly ONE create.** Enforced two ways: the typed transport
  queue (`query(miss) → create → query(hit)`, refused at pop time on a method/URL mismatch) and a
  direct count of `POST`s to the create endpoint `== 1`. A replay **re-derives** both identifiers
  from the reference and lands on the same card.
- **Integer paise cross the decimal-string boundary with no float.** `Money(250050).to_wix() ==
  "2500.50"` and back with `type(...) is int`; `Money.from_wix("999.75").paise == 99975`;
  `Money.from_wix(10.0)` **raises**. The only float literal anywhere in the five new or changed
  Python files is `0.05` in `_transact_with_retry`'s backoff jitter; the five `float` identifiers are
  `Callable[[float], None]` annotations on the injected sleeper; every `/` in the demo is `pathlib`.
- **`codeLast4` reads Wix's own `codeSuffix`** and refuses with `CODE_SUFFIX_MISSING` rather than
  slicing the obfuscated bearer code. `create` never returns a clear code to its caller.
- **`source: "MANUAL"`**, required by Wix and measured; `ORDER` is narrowed out as a false
  provenance claim. **`notificationInfo` is never sent**, because it triggers a Wix-sent email,
  which is a live customer send.
- **The query filter is a real JSON object** (`{"code": {"$eq": ...}}`), unlike the coupon query's
  double-encoded string. Balance and currency come off the **query** response, so the resolve path
  is one request.

### And the third leg: our own gift-card store, kept with its concurrency fix

`gift_card_store.redeem()` and `void()` now commit on a **two-item `TransactWriteItems`**, so each
balance move and the flag recording it commit together. Comparing the new card item against
`_decrement` at `32b632e3`, every pre-existing predicate survives — `attribute_exists`,
`balancePaise >= :amount`, `#status = :active` — and only `attribute_not_exists(#applied)` moved,
onto the claim item as `settled = :false`. That is the guarantee getting **stronger** rather than
relocated: the old marker could only be written after the money had moved; the new condition commits
with it.

One real defect was found by the concurrency test during implementation and fixed: the committer
returned a bare balance on the lost-race branch, so both racing callers answered `committed: True`
— the money moved once but two callers each claimed to have moved it. It now returns
`(balance, committed)` and the loser takes the replay branch, writing no second `GCTXN#` row.

Why that fix lands rather than being retired by deletion is §6.

### Loyalty and referral — out of scope, by decision

Both are present on the connected Wix site. Neither is in this build: no seam, no stub, no mention
in code. There is no live loyalty or rewards programme, and nothing here invents points or balances.

---

## 4. The demo transcript, as produced

```
$ .venv/bin/python scripts/demo_coupon_giftcard_sample.py --no-colour
```

Exit code **0**, 100 lines. Runnable with zero AWS and zero Wix access. The Wix HTTP boundary is
stubbed at `urllib.request.urlopen`, so every request below is the one `wix_ecom._request` really
composed — headers, `json.dumps` with no custom encoder, the lot.

Re-run for this report and diffed line by line against the previously recorded transcript: **100
lines against 100**, and the only differences are the **three** per-run identifiers — leg 1's
`couponId`, leg 3's `giftCardId` (and therefore its derived code mask) and leg 3's `transactionId`,
each a fresh ULID from `secrets`. Every amount, payload, state and claim is byte-identical. What is
pasted below is this run.

Read four things in it deliberately:

- the **coupon code prints in full** (`WDSAMPLE10`) because it is broadcast marketing material;
- the **gift-card code never does** — `****8FA8` in the summary, in the create body and in the query
  filter, in both directions;
- the **idempotency key is masked too** (`****311d`), and the reason is specific rather than
  cautious. An idempotency key is not bearer value and production could print it in full, because
  production's `card_code` is HMAC-keyed and shares nothing with it. But leg 2 derives its code with
  the unkeyed `demo_code`, and **both expose the same sha256 digest of the same reference**, so a
  clear key would hand over the masked code by stripping decoration and upper-casing. An earlier
  transcript printed it in full, which made "no clear bearer-value code" true of the string and
  false of the information. The `(70 ch)` length is still reported, because that is the fact a
  reviewer needs about Wix's 100-character ceiling and it discloses nothing;
- the credential appears only as the **secret name**, `wecare/wix/headless-api-key`.

```
WIX COUPON + GIFT CARD SAMPLE                              OFFLINE
Wix HTTP boundary: STUBBED at urllib.request.urlopen. No live Wix call.

-- LEG 1 . COUPON ----------------------------------------------
  this is how it works today
  driver           coupons/handler._create (production composition)
  created_by       demo-operator  (event['_auth']['username'])
  our claim        COUPON#WDSAMPLE10  (conditional put, won)
  couponId         01a0fee4-5520-74f2-9d64-4dada729a20d
  discount         MONEY_OFF 12345600 paise  = INR 123,456.00
  minimum          500000 paise  = INR 5,000.00
  currency         INR  (compared explicitly)
  arithmetic       WIX (we never compute a discount)

  -> POST https://www.wixapis.com/stores/v2/coupons
     Accept: application/json
     Authorization: <redacted - wecare/wix/headless-api-key>
     Content-type: application/json
     Wix-site-id: fcd82f0c-9572-49c7-acfb-88fb05042ece
     {
       "specification": {
         "name": "Sample money off",
         "code": "WDSAMPLE10",
         "startTime": "1719390501000",
         "moneyOffAmount": 123456,
         "minimumSubtotal": 5000,
         "usageLimit": 10,
         "limitPerCustomer": 1,
         "limitedToOneItem": false
       }
     }
  <- 200 {"id": "abeb638b-f9f4-4bb8-8fe7-2319504df6d9"}
  handler answer   201  (202 would mean PENDING_WIX)
  our row          wixMirrorState PENDING_WIX -> MIRRORED
  eligibility      ELIGIBLE  (a verdict, never an amount)
  create calls     1

-- LEG 2 . GIFT CARD, WIX-NATIVE -------------------------------
  CHOSEN: contract under verification (retirement gate condition 3)
  reference        wd-gc-sample-2026-10-02  (the ONLY input)
  code             ****8FA8  = demo_code(reference_id) - DEMO-ONLY, UNKEYED
                   20 chars, Wix's maximum - same length production sends
  production uses  card_code(reference_id, pepper) - HMAC-keyed under wecare/wix/giftcard-spi:code_pepper, domain-tagged
  idem key         ****311d  (70 ch)
                   unkeyed on purpose: not bearer value, and rotation-invariant
                   MASKED here anyway: THIS leg's demo_code is the same unkeyed digest,
                   so a clear key would yield the masked code. card_code is HMAC-keyed.
  derived          deterministic in its inputs - no clock, no counter, no secrets

  -> POST https://www.wixapis.com/gift-cards/v1/gift-cards
     Accept: application/json
     Authorization: <redacted - wecare/wix/headless-api-key>
     Content-type: application/json
     Wix-site-id: fcd82f0c-9572-49c7-acfb-88fb05042ece
     {
       "giftCard": {
         "initialValue": {
           "amount": "2500.50"
         },
         "currency": "INR",
         "source": "MANUAL",
         "code": "****8FA8"
       },
       "idempotencyKey": "****311d"
     }
  <- 200 giftCardId 1d752091-8c2e-4c3f-9f1a-7b0d5e4a2c66  codeSuffix 8FA8  balance 250050 paise  = INR 2,500.50
     resolved=False  disabled=False  expirationDate None
     codeLast4: Wix's own codeSuffix, never a parse of the obfuscated code
     replay: identifiers RE-DERIVED -> 1 create call total, same giftCardId, resolved=True

  -> POST .../gift-cards/v1/gift-cards/query
     {
       "query": {
         "filter": {
           "code": {
             "$eq": "****8FA8"
           }
         }
       }
     }
     ^ a real JSON object, unlike the coupon query's double-encoded string
  <- after a WIX-side redemption: 99975 paise  = INR 999.75
     balance and currency come off the QUERY response, so the resolve path is ONE request
     redemption is WIX (balance is readOnly; we could not move it if we tried)
     store of ours in this leg: NONE

-- LEG 3 . GIFT CARD, OURS -------------------------------------
  CURRENT: would be removed under the Wix-native decision
  issued           giftCardId 018bcfe5-6800-7d8d-8a19-30a74a603463   code ****BDXJ  (HMAC key, pepper read BY REFERENCE in production)
    balance        250050 paise  = INR 2,500.50
  redeem           150075 paise, attempt demo-attempt-1
    transactionId  01M3ZE8NZZP5GEK24QR46DZQSF  (ULID, secrets-backed)
    balance after  99975 paise  = INR 999.75
  replay           same attempt -> committed=False, balance 99975 paise unchanged
  concurrent       2 threads, same attempt -> 1 debit (tests/test_gift_card_redeem_concurrency.py)

no AWS:  secretsmanager client built = NO    AWS API calls attempted = 0
         clients are constructed at handler import; the refusing before-send hook was ARMED
         BEFORE leg 1 and unregistered after, so an attempted call raises and fails the run
3 legs, 0 contract mismatches
```

### What the transcript demonstrates, line by line

| Transcript line | The property it shows |
|---|---|
| `driver coupons/handler._create (production composition)` | the body was composed by production code, not assembled by the demo |
| `created_by demo-operator` | taken from `event["_auth"]["username"]`, exactly as production does |
| `our claim COUPON#WDSAMPLE10 (conditional put, won)` | Option B's recovery mechanism, exercised rather than described |
| `"moneyOffAmount": 123456` | a JSON **int** in whole rupees, by `//` — Wix's coupon money fields are numbers |
| `"startTime": "1719390501000"` | a **quoted** string-encoded int64 in the same body, which is why the string convention demonstrably does not extend to the money fields |
| `handler answer 201` | a `202` would mean `PENDING_WIX`, which `evaluate` refuses |
| `eligibility ELIGIBLE` | a verdict, never an amount |
| `create calls 1` | one create on the wire for the coupon leg |
| `"amount": "2500.50"` | a decimal **string**, two places — integer paise `250050` crossing the Wix boundary with no float |
| `"source": "MANUAL"` | required by Wix, measured; `ORDER` is narrowed out as a false provenance claim |
| no `orderInfo`, no `notificationInfo` | the latter triggers a Wix-sent email, which is a live customer send |
| `replay: identifiers RE-DERIVED -> 1 create call total` | the replay recomputes both identifiers from the reference and still lands on one card |
| `codeLast4: Wix's own codeSuffix` | never a parse of the obfuscated bearer code |
| `$eq` on a real JSON object | unlike the coupon query's double-encoded **string** filter |
| `after a WIX-side redemption: 99975 paise` | **a redemption and the resulting balance**, read off the **query** response, so the resolve path is one request. ₹2,500.50 less ₹1,500.75 = ₹999.75, in integer paise throughout |
| `redemption is WIX (balance is readOnly)` | we could not move it if we tried — that is the authority boundary |
| `store of ours in this leg: NONE` | leg 2 touches no table of ours |
| leg 3 `redeem 150075 paise … balance after 99975 paise` | **our** store's redemption and resulting balance, the same arithmetic on the same amounts, so the two authorities are directly comparable |
| leg 3 `replay … committed=False, balance unchanged` | our own store's idempotency on `(codeHash, paymentAttemptId)` |
| leg 3 `concurrent 2 threads, same attempt -> 1 debit` | the `TransactWriteItems` fix, measured |
| `idem key ****311d` | masked even though a key is not bearer value, because **this** leg's code is the unkeyed digest of the same reference — see the four reading notes above |
| `AWS API calls attempted = 0` | enforced by a refusing `before-send` hook **armed before leg 1**, which raises a `BaseException` out of the leg; the count is corroboration, not the gate |

### Disclosure, measured rather than asserted

Counted **in-process** rather than through a shell pipeline, deliberately: the values being searched
for are derived at runtime, and putting any of them on a command line is exactly what
`secret-handling.md` forbids. The probe computes them, captures stdout and counts, printing only
counts.

```
--json       exit=0 clear_code=0 clear_key=0 shared_digest_lower=0 shared_digest_upper=0 issuer_hits=0 chars=4084
--no-colour  exit=0 clear_code=0 clear_key=0 shared_digest_lower=0 shared_digest_upper=0 issuer_hits=0 chars=4617
```

`issuer_hits` covers `rzp_live_ sk- AIza ghp_ xoxb- AKIA ASIA sk_live_ ksk_ "PRIVATE KEY"` and the
fixture placeholder. The code review re-verified the same property against **this file**: no
`demo_code`, no idempotency key, neither casing of the shared digest fragment, no full digest, no
issuer-shaped token, no placeholder API key and no demo pepper literal — the credential appears
only as the name `wecare/wix/headless-api-key`.

### Two claims the transcript deliberately does not make

It does not print `boto3 imported = NO`, because that is **false** once the coupon handler is
imported: it pulls in `middleware` and `rate_limit`, each of which builds a client at import. The
honest claims are the two that are true — **no Secrets Manager client was built**, and **no AWS call
was attempted**. A false structural claim in the one artifact whose purpose is to be trusted is
worse than no claim.

And one claim that was previously stronger than the fact, corrected in the code rather than in the
prose. An earlier run printed `AWS API calls attempted = 0` from a function that created the counter
and registered the hook in the **same call**, invoked after all three legs had finished — so the `0`
was true by construction and the line beneath it was false for the run it described. The hook is now
armed inside `_install_containment()` before leg 1 and unregistered in a `finally`,
`_count_aws_calls()` is a read, and an attempted call arrives as an `UnexpectedAwsCall` in `main()`'s
handler, which prints `CONTRACT FAILURE` and exits `1`. A call that would leave the process **fails**
the demo rather than being tallied afterwards. Both the enforcement and the *moment of arming* are
themselves mutation-tested (`verification.md` §10 and §0b).

---

## 5. Test counts against the known baseline

Interpreter throughout: `/Users/wecaredigital/wecare-store/.venv/bin/python` (3.12.14). The worktree
has no `.venv` of its own; the one that satisfies `conftest.py` lives in the parent checkout, and a
bare `python3` is not a valid baseline.

### The known baseline — NOT this change's regressions

| File | Pre-existing failures |
|---|---:|
| `tests/test_url_host_routing_rules.py` | 4 |
| `tests/test_legacy_redirect_rollback_snapshot.py` | 1 |
| **Total** | **5** |

Confirmed present both before and after. `wecare/google-maps-server:api_key` is an **expired,
unrelated secret** and is ignored — it is not a finding of this change and no rotation is proposed
here.

### Full pytest, re-run for this report

```
$ .venv/bin/python -m pytest -q
5 failed, 6882 passed, 1 skipped, 7 xfailed in 60.63s

FAILED tests/test_legacy_redirect_rollback_snapshot.py::test_owner_policy_preserves_rewrites_without_restoring_legacy_destinations
FAILED tests/test_url_host_routing_rules.py::test_only_host_canonicalisation_is_an_explicit_redirect
FAILED tests/test_url_host_routing_rules.py::test_converged_configuration_is_not_rewritten
FAILED tests/test_url_host_routing_rules.py::test_unknown_redirect_removed_without_touching_proxy_rules
FAILED tests/test_url_host_routing_rules.py::test_saved_pre_removal_configuration_reconciles_to_post_removal_snapshot
```

**Exactly the 5 known failures, in exactly the 2 known files. No sixth failure, so this change
introduced no regression.**

| Run | Passed | Failed | Note |
|---|---:|---:|---|
| Original implementation pass | 6,878 | 5 | baseline failures only |
| First review-fix pass (`d7ef5583`) | 6,881 | 5 | `+3` — the AWS-enforcement mutation test, the global-restoration test, the idempotency-key disclosure test |
| Second review-fix pass (`4b4a889b`) | 6,882 | 5 | `+1` — M4's `test_the_aws_refusal_hook_is_armed_before_the_first_leg` |
| **This report's re-run** | **6,882** | **5** | unchanged; same 5 failures, same 2 files |

### The design §7 focused set, re-run for this report

```
$ .venv/bin/python -m pytest tests/test_wix_coupon_giftcard_sample.py \
    tests/test_demo_coupon_giftcard_sample.py tests/test_gift_card_redeem_concurrency.py \
    tests/test_gift_card_store.py tests/test_gift_card_two_leg_finalization.py \
    tests/test_gift_card_spi_contract.py tests/test_gift_card_amounts_and_gst.py \
    tests/test_gift_cards_iam_and_table.py tests/test_wix_coupons_contract.py \
    tests/test_coupon_store.py tests/test_coupon_reconciliation.py \
    tests/test_payment_vocabulary_at_decision_points.py -q
457 passed, 7 xfailed in 2.25s
```

Reconciled against the pre-edit baseline measured in this worktree at `32b632e3` — **315 passed, 7
xfailed** over 8 files — the focused set is **457 passed, 7 xfailed** over 12 files. The 142
additional passes are this change's new tests (58 harness + 20 demo + 4 concurrency) plus the 3
structural tests and 1 IAM test added to existing files; the 7 xfailed are **unmoved**.

### TypeScript, recorded rather than re-run

`npm ci` first (the worktree had no `node_modules` at all, which is a worktree-environment gap
rather than a regression — "vitest was not run" and "vitest could not be run" are different
statements), then `npm run build` **before** `npx vitest run`, in that order, because vitest depends
on the `out/` artifact:

```
$ npm run build      exit 0   (sitemap 1,411 URLs; blog index 1,323 posts)
$ npx vitest run     65 files passed, 812 passed, 1 skipped
```

**No `.ts`/`.tsx`/`.js`/`src/**` file is in this change's footprint** —
`git status --short -- src '*.ts' '*.tsx' '*.js'` is empty — so this is a whole-repo gate rather
than a test of anything changed here.

### The concurrency gate is live, not vacuous

Post-fix, run five times in a row to confirm the schedule is **forced** rather than timed: `4 passed`
each time. Pre-fix, the original store was loaded straight out of git
(`git show 32b632e3:...gift_card_store.py`) into a separate module and driven through the identical
forced schedule — same three `threading.Event`s, same two-override latching subclass, same amounts:

```
PRE-FIX store (32b632e3):
  balancePaise         = 200000   (post-fix asserts 350000)
  balance moves tried  = 2
  balance moves landed = 2        (post-fix asserts 1)
  committed=True count = 2        (post-fix asserts 1)
  errors               = {}
VERDICT: FAILS pre-fix as required
```

A card worth 500000 paise, redeemed 150000 twice under **one** `paymentAttemptId`, ended at 200000
instead of 350000, and both callers reported `committed: True`. That is the double debit.

---

## 6. Retire-or-stopped: **STOPPED**. The gift-card backend was NOT retired, and the concurrency fix is kept intact

**Outcome: STOP note. The Wix-native path is proven against Wix's documented contract, and that is
not the same thing as proven against Wix's live API on this site. The retirement does not land.**

The owner's instruction was to retire our gift-card backend in source **only if the demo proves
Wix-native works against Wix's real API contract**, and otherwise to stop and report the gap. Here is
the gap, stated precisely rather than as a hedge.

### The gate, measured

| Condition | Who satisfies it | State |
|---|---|---|
| 1 — the Wix Gift Cards app is installed | owner, dashboard | ✅ answered YES 2026-10-02 |
| 2 — our shapes match the documented contract; integer paise survive the decimal boundary; resolve-before-create consumes one create | **this change** | ✅ delivered — 74 harness/demo tests, demo exit 0, 3 legs, 0 mismatches |
| 3 — **one owner-run live verification on the real site** | **owner only** — a live Wix write is a standing refusal for the agent | ⏳ **OPEN** |

### What IS proven

| Claim | How |
|---|---|
| The four verdict-carrying contract facts hold today | **Five** fetches of the live `dev.wix.com` markdown rendition (pages 1, 2, 2b, 3, 4), recorded with URL form, HTTP status, byte size and extracted schema fragment in `docs/execution/wix-contract-verification-20261002.md`. V1, V2, V3, V4 all **confirmed**; no HALT triggered |
| Our request shapes match that contract byte-for-byte | `tests/test_wix_coupon_giftcard_sample.py` Groups A and C compare the **whole** body, not a subset, against the documented dict; the two optional keys are asserted **absent rather than null** |
| Integer paise survive the decimal-string boundary | `Money(250050).to_wix() == "2500.50"` and back with `type(...) is int`; `Money.from_wix("999.75").paise == 99975`; `Money.from_wix(10.0)` raises |
| Resolve-before-create consumes exactly ONE create | Enforced two ways: the typed transport queue (`query(miss) → create → query(hit)`, refused at pop time on a method/URL mismatch) and a direct count of `POST`s to the create endpoint `== 1` |
| The gift-card code is not recoverable from a logged `reference_id` | `test_the_keyed_code_is_not_recoverable_from_a_logged_reference_id`, asserted in **both** directions, plus the positive line proving the unkeyed `demo_code` **fails** that same test — which is what makes the first two capable of failing at all |
| Nothing touched AWS | `wix_ecom._secrets is None` after every run, corroborated from outside the demo; `boto3` sabotaged in `sys.modules` to raise a `BaseException` on any attribute access; a refusing `before-send` hook **armed before leg 1 and unregistered after**, so an attempted call raises out of the leg and the run exits `1`. **0** AWS API calls attempted, and the enforcement is itself mutation-measured |

### What is NOT proven, and cannot be from here

**A stubbed demo cannot prove the live API accepts our key, our shape and our fractional-INR amounts
on this site.** Three specific ways condition 3 could still fail, none of which this design can
anticipate:

1. **Scope.** The API key's grant may not include the gift-card service.
   `SCOPE.DC-ECOM-MEGA.MANAGE-ECOM` is broad, and whether it reaches `/gift-cards/v1/gift-cards` is
   unmeasured. A `403`-class refusal here is **a scope grant to obtain, not a negative answer**.
2. **Region and plan.** The Gift Cards app is installed (owner, 2026-10-02) but the create path
   documents a premium-plan dependency, and the markdown rendition renders **no `Errors` section for
   any method** — measured across all five pages — so `SITE_IS_NOT_PREMIUM` is neither confirmed nor
   contradicted by this evidence. It is not carried as a measured fact.
3. **Response shape on an India/INR site.** Every fixture here is built from the documented example.
   What this site actually returns for a **20-character unhyphenated code** is genuinely unmeasured:
   the obfuscated `code` is documented through one hyphen-grouped example (`****-****-****-4444`).
   That is why `codeLast4` reads Wix's own `codeSuffix` and **refuses** with `CODE_SUFFIX_MISSING`
   rather than falling back to slicing bearer value — but the refusal is a safe failure, not a proof
   that the field arrives.

### So the backend stays, whole rather than half-removed

**Deleted: nothing.** `gift_card_store.py`, both handlers
(`ecommerce/gift-cards/handler.py`, `ecommerce/wix-giftcard-spi/handler.py`), all three provisioners,
the `wecare-gift-cards` and `wecare-wix-giftcard-spi` deploy-registry entries, the route definitions
and their tests are intact, and `tests/test_gift_card_store.py` passes — which is what proves the
backend is whole rather than partially dismantled. The Wix-native adapter is **unwired**: nothing
under `amplify/` imports `wix_gift_cards`, and nothing references `demo_code` outside the defining
module, both confirmed independently by the code review.

### And therefore the `TransactWriteItems` optimistic-concurrency fix LANDS, intact

The `redeem()` concurrent double-debit was **HIGH as a source defect** — two redemptions under one
`paymentAttemptId` would silently debit stored value twice and leave a self-consistent ledger,
measured at 200000 paise where 350000 is correct — **and it never reached a customer**, because
nothing was ever deployed (§7 re-derives that). Dropping the first half understates the defect;
dropping the second overstates the incident.

It is **fixed in source in this change**, with its gate runtime-asserted rather than vacuous (§5).
Shipping a known concurrent double-debit on the strength of an intention to delete the code later is
not available.

**If the backend is ever retired, `redeem()`'s concurrent double-debit becomes retired-by-deletion
rather than fixed** — and the never-reached-a-customer half travels with it.

### Two line items the eventual wiring change inherits

**(a) The recording rule must be re-derived against a REAL clear code.** Offline, every gift-card
code is a fixture placeholder, which is why `WixTransport` records request bodies verbatim and why
that is safe today. The moment the adapter is wired to a live Wix response that stops being true: a
real `CreateGiftCardResponse` carries a real clear code — it is the *only* place the clear code
exists, measured — so capture-time redaction of the body, or no recording of it at all, has to be
decided before the first live call. Inheriting a "recording is harmless" conclusion from an offline
harness is how bearer value ends up in a log.

**(b) `card_code`'s return value lives entirely in code this design does not author.** The module has
nothing to log with and `create` never returns a clear code — both true, and both statements about
the *module*. The production clear code will not come from a Wix response at all; it will come from
the caller calling `card_code` itself, because the caller is the thing that holds the pepper. So the
wiring change must state and test, in its own document, that the value **never** reaches a log line
at any level or in any spelling (CodeQL tracks taint across function boundaries and has already
failed this build twice on a value reduced to a boolean), **never** reaches an exception message,
**never** appears in a staff, admin or reconciliation surface — `codeLast4` is what those get, which
is why `create` returns it — and is **never persisted in clear**.

**The order of operations, because getting it wrong is the only way this goes badly.** Wire the
Wix-native adapter in **before** deleting our store, never after. A retirement that lands first
leaves the product with no gift cards at all if the replacement then fails its first real call.

### Carried forward from the code review (INFORMATIONAL, non-blocking)

**I1 — residual settled-without-ledger window in `redeem`.** If the two-item transaction commits and
the `GCTXN#`/`GCTXNID#` puts then fail, a retry reads the settled claim, answers from the replay
branch and returns without writing them. `void()` resolves exclusively through
`GCTXNID#<transactionId>` and raises `TransactionNotFound` with no row, so the balance cannot be
returned through this layer while the SPI has already answered Wix with that transactionId.
**Pre-existing in kind** — the same gap existed between `_mark_settled` and the ledger puts at
`32b632e3` — and this change **removes the other window** (money moved, claim unsettled) outright
rather than adding one. `_record_balance_after` is one new best-effort `UpdateItem` inside it. No
action required for this change; worth a recovery path when the SPI void surface is next touched.

**I2 — `demo_code`'s docstring publishes its own output for the default demo reference.** See §1 H1.

---

## 7. Owner go-live checklist

### Re-derived against the live account, not quoted

Read-only enumeration of account `775261844268` / `us-east-1`, 2026-10-02:

| Surface | Measured | Gift-card / coupon presence |
|---|---:|---|
| Lambda functions | 69 total | **0** — no `wecare-gift-cards`, no `wecare-wix-giftcard-spi`, no `wecare-coupons` |
| DynamoDB tables | 82 total | **0** — no `stack-wecare-digital-GiftCardsTable`, no `stack-wecare-digital-CouponsTable` |
| HTTP API routes (`zllr9lrg7j`) | 364 total | **0** — the only `/ecommerce/*` routes live are `POST /ecommerce/checkout`, `POST /ecommerce/checkout/status`, `POST /ecommerce/customer-session` |
| `wecare-checkout` environment | 9 keys | the payment gate flag is **absent**, so charging stays off |

So **nothing in this feature exists in AWS**, which is also what makes the `redeem()` defect a source
defect that never reached a customer. Re-derive this table before acting on it rather than quoting
it; it is a dated snapshot by design.

### What the owner must provision, per surface

| Surface | What | Script | State |
|---|---|---|---|
| **Function** | `wecare-coupons` | `scripts/deploy_all_lambdas.py wecare-coupons` | ⏳ not deployed |
| **Function** | `wecare-gift-cards` | `scripts/deploy_all_lambdas.py wecare-gift-cards` | ⏳ not deployed — **and held by the §6 STOP**: do not deploy our store if the Wix-native path is to replace it |
| **Function** | `wecare-wix-giftcard-spi` | `scripts/deploy_all_lambdas.py wecare-wix-giftcard-spi` | ⏳ not deployed — same hold |
| **Table** | `stack-wecare-digital-CouponsTable` | `scripts/provision_coupons_table.py` | ⏳ absent |
| **Table** | `stack-wecare-digital-GiftCardsTable` | `scripts/provision_gift_cards_table.py` | ⏳ absent — same hold |
| **Role** | coupon + gift-card inline policies (incl. `code_pepper` read by reference) | `scripts/provision_coupons_role.py`, `scripts/provision_gift_cards_roles.py` | ⏳ not applied |
| **Route** | `POST /coupons`, `GET /coupons/{code}`, `GET /coupons`, `POST /coupons/{code}/deactivate`, `POST /coupons/validate`, `POST /coupons/hold`, `POST /coupons/release` | `scripts/provision_coupons_routes.py` | ⏳ absent |
| **Route** | `POST /gift-cards`, `GET /gift-cards/{giftCardId}`, `GET /gift-cards`, `POST /gift-cards/{giftCardId}/disable`, `POST /gift-cards/balance` | `scripts/provision_gift_card_routes.py` | ⏳ absent — same hold |
| **Route** | the three SPI methods `POST /wix-giftcards/v1/{balance,redeem,void}` — deliberately **not** a `{proxy+}` | `scripts/provision_gift_card_routes.py` | ⏳ absent — same hold |
| **Flag** | **there is no coupon or gift-card feature flag, by design.** Nothing in either handler reads an `*_ENABLED` variable; the surface is gated by the routes existing at all | — | ➖ not applicable |
| **Flag** | the payment gate on `wecare-checkout` — measured **absent**, so checkout cannot charge | — | ⛔ stays OFF until finalization + Wix order reconciliation + the missing checkout routes are green |

Two notes that matter when these land. No route takes a **code** in a path or a query, deliberately:
a bearer value in a URL lands in access logs, in `Referer` headers and in browser history. The staff
reads take our own `giftCardId`; the customer route takes `{code, pin?}` in the **body**. And
**every one of these functions needs the publish-and-move step** after `update-function-code` — a
`live` alias is what the HTTP API integration invokes, so `$LATEST` alone does not reach production.

### Can one owner-run Wix call create a real sample without a deploy? **Yes.**

Both creates are plain HTTPS calls to `www.wixapis.com` authenticated by the headless API key. They
need **no Lambda, no table, no route and no flag** — none of the rows above. The gift-card create is
additionally idempotent server-side on `idempotencyKey`, so a replay cannot mint a second card.

What that one call would and would not settle:

- it **clears gate condition 3** for gift cards: whether the live site accepts our key, our shape and
  our fractional-INR amounts, which is precisely what the stubbed demo cannot prove;
- it creates a **real coupon** and a **real gift card** on the connected site, so it is a live write
  and therefore **owner-only** — a live Wix write is a standing refusal for the agent;
- it does **not** make the feature usable by a customer. That still needs the function, table, route
  and (for checkout) the payment gate above.

The sequence, in one line: the `count` read first, then
**create → replay-the-same-key → query-by-full-code**, against the live site, **by reference** through
`asm-exec` with `{{resolve:secretsmanager:wecare/wix/headless-api-key:SecretString:...}}` — never with
a value on a command line. **A `403`-class refusal is a scope grant to obtain, not a negative
answer.** Record the response shape for a 20-character unhyphenated code, because that is the third
unmeasured item in §6.

Then the retirement is a **separate** change, and it wires the Wix-native adapter in **before**
deleting our store.

### Prohibitions observed in this change

| Prohibition | Evidence |
|---|---|
| no deploy | no `update-function-code`, no `publish-version`, no alias move |
| no provisioning | `git status --short scripts/` clean apart from the new demo script; no `--apply` on anything |
| no live Wix write | the only network calls are five `curl` GETs of `dev.wix.com` documentation, plus the read-only AWS enumeration in this section. No coupon created, no gift card created, no app install, no config change |
| no secret read | no `get-secret-value` / `batch-get-secret-value` in any spelling. Secrets appear only as **names**: `wecare/wix/headless-api-key`, `wecare/wix/giftcard-spi`, field `code_pepper` |
| integer paise / explicit INR / no floats | `Decimal(str())` where a DynamoDB number re-enters arithmetic; `//` and `Money` elsewhere; `currency == "INR"` compared **explicitly and first**; `float` absent by AST from the money path; `_marshal` refuses a `float`, a `Decimal` and a `bool`-as-amount by exact type and is pinned byte-for-byte against `TypeSerializer` |
| no live sends | no messaging, no SMS, no WhatsApp, no email. `notificationInfo` is deliberately never sent precisely because it would be one |
| no destructive git | staged by explicit path with `git commit --only`; no `git add .`/`-A`/`-u`, no bare `stash`, no `clean`, no force push, no history rewrite; **not** rebased onto or fast-forwarded to `stack`. The branch is left for owner review |
| stayed inside this worktree | every path absolute under the worktree; `.worktrees/direct-razorpay-20261002` untouched; `ecommerce/checkout/handler.py`, `payment_readiness.py`, `payments/razorpay-webhook/handler.py` and everything under `amplify/functions/messaging/` untouched; `amplify/functions/ecommerce/coupons/handler.py` **driven, not modified** |
