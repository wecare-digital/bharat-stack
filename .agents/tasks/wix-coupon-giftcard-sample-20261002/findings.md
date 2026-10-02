# Findings — Wix coupon + gift card sample

Implementation of `design.md` revision 8 against `plan.md`, in worktree
`wix-coupon-giftcard-sample-20261002` on branch `wix-coupon-giftcard-sample-20261002`, based on
`stack` at `32b632e3`.

Two deliverables live here: the **real demo transcript**, pasted below as it was produced, and
the **STOP note** on the gift-card retirement. What was run and what it reported is in
`verification.md`; the one-page owner view is in `wix-native-decision-memo.md`.

## STOP — the gift-card backend retirement is NOT performed

**Verdict: the Wix-native path is proven against Wix's documented contract, and that is not the
same thing as proven against Wix's live API on this site. The retirement does not land.**

The owner's instruction was to retire our gift-card backend in source **only if the demo proves
Wix-native works against Wix's real API contract**, and otherwise to stop and report the gap.
Here is the gap, stated precisely rather than as a hedge.

### What IS proven

| Claim | How |
|---|---|
| The four verdict-carrying contract facts hold today | **Five** fetches of the live `dev.wix.com` markdown rendition (pages 1, 2, 2b, 3, 4), recorded with URL form, HTTP status, byte size and extracted schema fragment in `docs/execution/wix-contract-verification-20261002.md`. V1, V2, V3, V4 all **confirmed**; no HALT triggered |
| Our request shapes match that contract byte-for-byte | `tests/test_wix_coupon_giftcard_sample.py` Groups A and C compare the **whole** body, not a subset, against the documented dict; the two optional keys are asserted **absent rather than null** |
| Integer paise survive the decimal-string boundary | `Money(250050).to_wix() == "2500.50"` and back with `type(...) is int`; `Money.from_wix("999.75").paise == 99975`; `Money.from_wix(10.0)` raises |
| Resolve-before-create consumes exactly ONE create | Enforced two ways: the typed transport queue (`query(miss) → create → query(hit)`, refused at pop time on a method/URL mismatch) and a direct count of `POST`s to the create endpoint `== 1` |
| The gift-card code is not recoverable from a logged `reference_id` | `test_the_keyed_code_is_not_recoverable_from_a_logged_reference_id`, asserted in **both** directions, plus the positive line proving the unkeyed `demo_code` **fails** that same test — which is what makes the first two capable of failing at all |
| Nothing touched AWS | `wix_ecom._secrets is None` after every run, corroborated from outside the demo; `boto3` sabotaged in `sys.modules` to raise a `BaseException` on any attribute access; a refusing `before-send` hook **armed before leg 1 and unregistered after**, so an attempted call raises out of the leg and the run exits `1`. **0** AWS API calls attempted. The enforcement is itself measured: with the arming neutralised, a leg that emits `before-send` yields exit `0` and count `0` — see `verification.md` §10 |

### What is NOT proven, and cannot be from here

**A stubbed demo cannot prove the live API accepts our key, our shape and our fractional-INR
amounts on this site.** Three specific ways condition 3 could still fail, none of which this
design can anticipate:

1. **Scope.** The API key's grant may not include the gift-card service.
   `SCOPE.DC-ECOM-MEGA.MANAGE-ECOM` is broad, and whether it reaches
   `/gift-cards/v1/gift-cards` is unmeasured. A `403`-class refusal here is **a scope grant to
   obtain, not a negative answer**.
2. **Region and plan.** The Gift Cards app is installed (owner, 2026-10-02) but the create path
   documents a premium-plan dependency, and the markdown rendition renders **no `Errors` section
   for any method** — measured across all five pages — so `SITE_IS_NOT_PREMIUM` is neither
   confirmed nor contradicted by this evidence. It is not carried as a measured fact.
3. **Response shape on an India/INR site.** Every fixture here is built from the documented
   example. What this site actually returns for a **20-character unhyphenated code** is genuinely
   unmeasured: the obfuscated `code` is documented through one hyphen-grouped example
   (`****-****-****-4444`). That is why `codeLast4` reads Wix's own `codeSuffix` and **refuses**
   with `CODE_SUFFIX_MISSING` rather than falling back to slicing bearer value — but the refusal
   is a safe failure, not a proof that the field arrives.

**So the backend stays in place.** Nothing was deleted: `gift_card_store.py`, both handlers, all
three provisioners, the deploy-registry entries, the routes and their tests are intact, and
`tests/test_gift_card_store.py` passes — which is what proves the backend is whole rather than
half-removed.

**And therefore the TransactWriteItems optimistic-concurrency fix LANDS.** It is kept with its
gate **runtime-asserted, not vacuous**: the pre-fix store was loaded from git at `32b632e3` and
driven through the identical forced schedule, and it reported

```
PRE-FIX store (32b632e3):
  balancePaise         = 200000   (post-fix asserts 350000)
  balance moves tried  = 2
  balance moves landed = 2        (post-fix asserts 1)
  committed=True count = 2        (post-fix asserts 1)
VERDICT: FAILS pre-fix as required
```

Shipping a known concurrent double-debit on the strength of an intention to delete the code later
is not available. **If the backend is ever retired, the `redeem()` concurrent double-debit becomes
retired-by-deletion rather than fixed** — and the other half travels with it: it was HIGH as a
source defect and **it never reached a customer**, because nothing was ever deployed.

**The exact unblock action, one line:** the owner runs the `count` read, then
create → replay-the-same-key → query-by-full-code against the live site, by reference through
`asm-exec`. Then the retirement is a separate change, and it **wires the Wix-native adapter in
before deleting our store, never after**.

## The demo transcript, as produced

`python scripts/demo_coupon_giftcard_sample.py --no-colour`, exit code **0**. Runnable with zero
AWS and zero Wix access. The Wix HTTP boundary is stubbed at `urllib.request.urlopen`, so every
request below is the one `wix_ecom._request` really composed — headers, `json.dumps` with no
custom encoder, the lot.

Re-run in the second review iteration and diffed line by line against what is recorded here: 100
lines against 100, and the only differences are the **three** per-run identifiers — leg 1's
`couponId`, leg 3's `giftCardId` (and therefore its derived code mask) and leg 3's
`transactionId`, each a fresh ULID from `secrets`. Every amount, payload, state and claim below
is byte-identical, so the transcript is left as produced rather than churned for three ids.

Read three things in it deliberately:

- the **coupon code prints in full** (`WDSAMPLE10`) because it is broadcast marketing material;
- the **gift-card code never does** — `****8FA8` in the summary, in the create body and in the
  query filter, in both directions;
- the **idempotency key is masked too** (`****311d`), and the reason is specific rather than
  cautious. An idempotency key is not bearer value and production could print it in full, because
  production's `card_code` is HMAC-keyed and shares nothing with it. But leg 2 derives its code
  with the unkeyed `demo_code`, and **both expose the same sha256 digest of the same reference**,
  so a clear key would hand over the masked code by stripping decoration and upper-casing. The
  earlier transcript printed it in full, which made "no clear bearer-value code" true of the
  string and false of the information. The `(70 ch)` length is still reported, because that is
  the fact a reviewer needs about Wix's 100-character ceiling;
- the credential appears only as the **secret name**, `wecare/wix/headless-api-key`.

```
WIX COUPON + GIFT CARD SAMPLE                              OFFLINE
Wix HTTP boundary: STUBBED at urllib.request.urlopen. No live Wix call.

-- LEG 1 . COUPON ----------------------------------------------
  this is how it works today
  driver           coupons/handler._create (production composition)
  created_by       demo-operator  (event['_auth']['username'])
  our claim        COUPON#WDSAMPLE10  (conditional put, won)
  couponId         01a0fd7b-dbe0-71f0-9e4c-290efc432347
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
  issued           giftCardId 018bcfe5-6800-740a-bcb4-c28dc61487b4   code ****BR2J  (HMAC key, pepper read BY REFERENCE in production)
    balance        250050 paise  = INR 2,500.50
  redeem           150075 paise, attempt demo-attempt-1
    transactionId  01M3YQQQBR9H8FE1FW052K5BAA  (ULID, secrets-backed)
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
| `"moneyOffAmount": 123456` | a JSON **int** in whole rupees, by `//` — Wix's coupon money fields are numbers |
| `"startTime": "1719390501000"` | a **quoted** string-encoded int64 in the same body, which is why the string convention demonstrably does not extend to the money fields |
| `handler answer 201` | a `202` would mean `PENDING_WIX`, which `evaluate` refuses |
| `eligibility ELIGIBLE` | a verdict, never an amount |
| `"amount": "2500.50"` | a decimal **string**, two places — integer paise `250050` crossing the Wix boundary with no float |
| `"source": "MANUAL"` | required by Wix, measured; `ORDER` is narrowed out as a false provenance claim |
| no `orderInfo`, no `notificationInfo` | the latter triggers a Wix-sent email, which is a live customer send |
| `replay: identifiers RE-DERIVED -> 1 create call total` | the replay recomputes both identifiers from the reference and still lands on one card |
| `codeLast4: Wix's own codeSuffix` | never a parse of the obfuscated bearer code |
| `$eq` on a real JSON object | unlike the coupon query's double-encoded **string** filter |
| `after a WIX-side redemption: 99975 paise` | read off the **query** response, so the resolve path is one request |
| `redemption is WIX (balance is readOnly)` | we could not move it if we tried — that is the authority boundary |
| `store of ours in this leg: NONE` | leg 2 touches no table of ours |
| leg 3 `replay ... committed=False, balance unchanged` | our own store's idempotency on `(codeHash, paymentAttemptId)` |
| `idem key ****311d` | masked even though a key is not bearer value, because **this** leg's code is the unkeyed digest of the same reference — see the three reading notes above |
| `AWS API calls attempted = 0` | enforced by a refusing `before-send` hook **armed before leg 1**, which raises a `BaseException` out of the leg; the count is corroboration, not the gate |

Note what the transcript deliberately does **not** claim. It does not print `boto3 imported = NO`,
because that is false once the coupon handler is imported — it pulls in `middleware` and
`rate_limit`, each of which builds a client at import. The honest claims are the two that are
true: **no Secrets Manager client was built**, and **no AWS call was attempted**. A false
structural claim in the one artifact whose purpose is to be trusted is worse than no claim.

And one claim that was previously stronger than the fact, now corrected in the code rather than in
the prose. The earlier run printed `AWS API calls attempted = 0` from a function that created the
counter and registered the hook in the **same call**, invoked after all three legs had finished, so
the `0` was true by construction: no leg call could have been refused, and the line beneath it was
false for the run it described. The hook is now armed inside `_install_containment()` before leg 1
and unregistered in a `finally`, `_count_aws_calls()` is a read, and an attempted call arrives as
an `UnexpectedAwsCall` in `main()`'s handler — which prints `CONTRACT FAILURE` and exits `1`.
That is design §4.3's wording honoured: a call that would leave the process **fails** the demo
rather than being tallied afterwards.
