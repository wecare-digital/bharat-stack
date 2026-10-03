# Wix coupons and gift cards — the decision, in one page

For a reader who will not open the 4,285-line design. No new analysis; everything here is drawn
from `design.md` revision 8 and from what the implementation measured. **No credential value
appears anywhere in this file** — only the secret **names** `wecare/wix/headless-api-key` and
`wecare/wix/giftcard-spi`.

## The two verdicts, and why they differ

| Feature | Decision | The one fact it rests on |
|---|---|---|
| **Coupons** | **(B)** — Wix does the discount arithmetic; we keep a small issuance ledger | Wix's `Create Coupon` has **no `idempotencyKey`** and **no read-by-code**, measured 2026-10-02 |
| **Gift cards** | **(A)** — Wix-native, Wix is the balance authority | `Create Gift Card` **has** a server-side `idempotencyKey`, and `Query Gift Cards` documents **`$eq` on `code`** |

The asymmetry is the whole decision, so it is worth one paragraph rather than a table row.

**Coupons.** If our create request to Wix succeeds and the response is lost, a live Wix coupon now
exists whose id we cannot recover — there is no idempotency key to replay and no way to look it up
by the code we chose. Our own conditional put on `COUPON#<codeUpper>` **is** that recovery: a
replay loses the claim, issues no second Wix create, and keeps the id the first attempt recorded.
That is what `coupon_store` is for. It is **not** for arithmetic — nothing in our code computes a
discount, and `POST /coupons/validate` answers a one-word verdict and never an amount, which is a
security boundary rather than a style choice: a validate endpoint that returned a figure would
become a number a browser could quote.

**Gift cards.** Wix supplies both halves we would otherwise have to build. `idempotencyKey` closes
the create race server-side, `$eq` on the full code makes read-by-code a documented contract, money
is an exact decimal string (`maxScale: 2`) so integer paise cross the boundary with no float, and
`balance` is `readOnly` — we could not move it if we tried. The owner's confirmation on 2026-10-02
that the Wix Gift Cards app is installed cleared the one blocker.

## Retirement gate — evaluated, NOT cleared

The owner's instruction is to retire our gift-card backend in source **only after the demo proves
the Wix-native path works against Wix's real API contract**, and to stop and report if a gap
appears. Here is the gate, measured:

| Condition | Who satisfies it | State |
|---|---|---|
| 1 — the Wix Gift Card app is installed | owner, dashboard | ✅ answered YES 2026-10-02 |
| 2 — our shapes match the documented contract; integer paise survive the decimal boundary; resolve-before-create consumes one create | **this change** | ✅ delivered — 74 harness/demo tests, demo exit 0, 3 legs, 0 mismatches |
| 3 — **one owner-run live verification on the real site** | **owner only** — a live Wix write is a standing refusal for the agent | ⏳ **OPEN** |

**So the deletion does not happen in this change.** Nothing was deleted:
`gift_card_store.py`, both handlers, all three provisioners, the deploy-registry entries, the
routes and their tests are all intact, and `tests/test_gift_card_store.py` passes, which is what
proves the backend is whole rather than half-removed.

The honest sentence from the design, because it is the reason condition 3 cannot be waved through:
*a dashboard glance proves the product exists; it does not prove the API accepts our key, our
shape and our fractional-INR amounts on this site, and that is one owner-run call away.*

**The exact unblock action, in one line:** the owner runs the `count` read, then
create → replay-the-same-key → query-by-full-code against the live site, by reference through
`asm-exec` with `{{resolve:secretsmanager:wecare/wix/headless-api-key:SecretString:...}}` — never
with a value on a command line. **A `403`-class refusal is a scope grant, not a negative answer.**

### What retirement would remove, once condition 3 clears

Listed so the owner can size the decision. **Source only.**

| Kind | Items |
|---|---|
| shared module | `lambda_utils/ecommerce/gift_card_store.py` (now 1,561 lines), and `gift_card_settlement` if it has no other caller |
| functions | `amplify/functions/ecommerce/gift-cards/handler.py`, `amplify/functions/ecommerce/wix-giftcard-spi/handler.py` |
| deploy registry | the `wecare-gift-cards` and `wecare-wix-giftcard-spi` entries in `scripts/deploy_all_lambdas.py` |
| provisioners | `scripts/provision_gift_cards_table.py`, `provision_gift_cards_roles.py`, `provision_gift_card_routes.py` |
| tests | `tests/test_gift_card_store.py`, the new `tests/test_gift_card_redeem_concurrency.py`, the gift-card half of `tests/test_payment_vocabulary_at_decision_points.py`'s `RAW_SCAN_ONLY_FILES`, and the `wix_spi_*_jwt_payload.json` / `wix_cart_v2_gift_card_partial.json` fixtures |
| live resources | **none exist.** No `wecare-gift-cards`, no `wecare-wix-giftcard-spi`, no `GiftCardsTable`, no matching routes. So retirement is source-only with **nothing to delete in AWS** and no pointwise AWS confirmation to collect. Re-derive before the change lands rather than trusting this row |

### Two line items the wiring change inherits

**(a) The recording rule must be re-derived against a REAL clear code.** Offline, every gift-card
code is a fixture placeholder, which is why `WixTransport` records request bodies verbatim and why
that is safe today. The moment the adapter is wired to a live Wix response that stops being true:
a real `CreateGiftCardResponse` carries a real clear code — it is the *only* place the clear code
exists, measured — so capture-time redaction of the body, or no recording of it at all, has to be
decided before the first live call. Inheriting a "recording is harmless" conclusion from an
offline harness is exactly how bearer value ends up in a log.

**(b) `card_code`'s return value lives entirely in code this design does not author.** The module
has nothing to log with — no `logger`, no `logging`, no `print(`, asserted by AST — and `create`
never returns a clear code to its caller. Both are true, and both are statements about the
*module*. But the production clear code will not come from a Wix response at all; it will come
from the caller calling `card_code` itself, because the caller is the thing that holds the pepper.
So the wiring change must state and test, in its own document, that the value **never** reaches a
log line at any level or in any spelling (CodeQL tracks taint across function boundaries and has
already failed this build twice on a value reduced to a boolean), **never** reaches an exception
message, **never** appears in a staff, admin or reconciliation surface — `codeLast4` is what those
get, which is why `create` returns it — and is **never persisted in clear**.

**The order of operations, because getting it wrong is the only way this goes badly.** Wire the
Wix-native adapter in **before** deleting our store, never after. A retirement that lands first
leaves the product with no gift cards at all if the replacement then fails its first real call.

## The §5 defect, both halves in one breath

The concurrent double-debit window in `gift_card_store.redeem()` was **HIGH as a source defect**
— two redemptions under one `paymentAttemptId` would silently debit stored value twice and leave a
self-consistent ledger, measured at 200000 paise where 350000 is correct — **and it never reached
a customer**, because no `wecare-gift-cards`, no `wecare-wix-giftcard-spi`, no `GiftCardsTable`
and no matching route exists in account `775261844268` (re-derived 2026-10-02; re-derive again
rather than quoting that snapshot). Dropping the first understates the defect; dropping the second
overstates the incident.

It is **fixed in source in this change**, not retired by deletion, because the retirement gate did
not clear. Shipping a known concurrent double-debit on the strength of an intention to delete the
code later is not available. If and when condition 3 clears and the backend is retired, the
correct wording becomes: *retired by deletion, not fixed* — and the never-reached-a-customer half
still travels with it.

## What is already true in both branches

- **Wix does the discount arithmetic.** Nothing in our code computes a discount, under either
  verdict.
- **We never return a discount figure to a browser.** `validate` answers a verdict.
- **Money is integer paise, explicit INR, no floats.** Three independent proofs on the gift-card
  path: boundary type assertions, an AST gate on the identifier `float`, and
  `Money.from_wix(10.0)` refusing a float outright.

## Loyalty and Referral — noted and out of scope

Both are present on the connected Wix site. Neither is in this build: no seam, no stub, no mention
in code. There is no live loyalty or rewards programme, and nothing here invents points or
balances. Answering it here so it is not asked.

## Review NIT disposition

The design is frozen at revision 8, so a NIT asking for a design-document edit is **dropped with
a note** rather than applied to a frozen artifact; a NIT correcting a fact an implementer acts on
is **applied in code**.

- **NIT 4** — §16's stale "four transaction-driving tests" lacks a superseded annotation.
  **Dropped**, design frozen. Superseded in effect: the implementation follows §5.5's numbered
  **six-row** caller table, and five in-file callers plus the concurrency test assert it.
- **NIT 5** — §8's Modified row dates its own previous count to the wrong revision. **Dropped**,
  design frozen; a dating error in a changelog row changes no code.
- **NIT 6** — three line citations off by two or three. **Applied.** Re-measured in this worktree
  at `32b632e3`: the `:neg` comparison is at `:289` (the design said `:286`, which is
  `assert len(decrements) == 1`); the floor test spans `:276-294`, not `:274-290`; the existing
  exact-action assertion is at `:295` and covers `AdvanceGiftCardStageOnAPaymentAttempt` on
  **PaymentAttemptsTable**, not the ledger — which is why
  `test_the_ledger_statements_grant_exactly_what_the_store_needs_and_no_more` was added. Both
  substantive claims underneath those citations were correct.
- **NIT 7** — `_CreditThrottles` loses both callers, `_MarkerWriteFails` all three, and neither
  fate was stated. **Applied.** Both classes are deleted, and the call sites are mapped to their
  owning tests in `verification.md`. A fault injector with no caller misleads the next reader
  exactly as a constant with no caller does.

## The three open MEDIUMs

1. **`FakeTable.arm_failure` could not express "fail the same op twice."** `_fail_if_armed`
   consumed the arm with `pop`, so two arms produced one failure and the second `pytest.raises`
   failed against **correct** code. Fixed with a real decrementing `times=` counter, defaulted to
   `1` so every existing call site is untouched. Chosen over re-arming mid-test because it keeps
   the arming visible at the arming site and makes the test's own narrative literally true.
2. **`_committer_of` / `_is_balance_move` were named in the design and absent from the tree.**
   Both are now implemented in `tests/test_gift_card_store.py` with real signatures and imported
   by name from the concurrency suite. `_committer_of` **raises** for a transaction that moves no
   balance rather than returning a sentinel, so a third kind of transaction cannot be absorbed
   silently into a set comparison.
3. **§5.5's stale "one definition, four callers" contradicted its authoritative six-row table.**
   The table is followed. Six callers, each asserting `seen >= 1` or `seen >= 2` plus a committer
   set and **no literal transaction total** — `grep -nE 'seen == [0-9]'` is empty.

## Related

- `design.md` revision 8 — the full analysis
- `docs/execution/wix-contract-verification-20261002.md` — the four verdict rows, re-measured
- `findings.md` — the demo transcript and the STOP note
- `verification.md` — what was run and what it reported
