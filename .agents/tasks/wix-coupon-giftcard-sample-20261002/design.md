# Wix coupon + gift card sample — design, 2026-10-02

Worktree: `/Users/wecaredigital/wecare-store/.worktrees/wix-coupon-giftcard-sample-20261002`
at `32b632e3`. Every repository claim below was read from that tree. Every Wix claim was
fetched live from `dev.wix.com` **today, 2026-10-02**; a representative command per API is
**inlined in §3** so the reader can re-run it rather than trust this document. The full
transcript with page byte sizes **will be written to**
`docs/execution/wix-contract-verification-20261002.md` as the **first step of implementation** —
that file does not exist yet, and §3 says so in the same words rather than citing an artifact a
reader cannot open.

**Revision 2, 2026-10-02.** Revised against `design-review.json` (CHANGES_REQUESTED: 5 HIGH,
11 MEDIUM, 4 NIT). Every HIGH and MEDIUM is resolved in place; the dispositions are listed in
§11. No verdict, no architecture and no decision in §1 changed — the findings were concentrated
in the *mechanisms* that prove the properties, and four of those mechanisms could not have done
the job as first written.

**Revision 3, 2026-10-02 — the owner answered the gift-card gate.** The Wix Gift Card app **is**
installed on the live site, and Wix coupons are present too. Gift cards move from
**(C) Undetermined** to **(A) Wix-native available, and chosen**. The coupon verdict **(B) does
not change** and the reason is in §1.3.2. Retirement of our gift-card backend is now the
direction of travel but is **gated on evidence, not on the dashboard glance** — §0.1 states the
gate, and §5 states what happens to the `redeem()` fix on each side of it. Wix **Loyalty** and
**Referral** were also mentioned and are recorded as **out of scope** in §1.5 rather than absorbed.

**Revision 4, 2026-10-02.** Revised against the second `design-review.json` (CHANGES_REQUESTED:
4 HIGH, 10 MEDIUM, 4 NIT, reviewed at `32b632e3`). Every HIGH and MEDIUM is resolved in place;
the dispositions are in §13. Again no verdict, no architecture and no decision in §1 changed, and
again the findings landed in the mechanisms rather than the decisions — two of which could not
have worked: the concurrency test's central assertion would have **failed against correct
post-fix code**, and the chosen money-marshalling import is **forbidden by an existing AST gate**
this document had not consulted. The void half of §5, which revision 2 took on, is now specified
at the same depth as the redeem half instead of a tenth of it.

**Revision 5, 2026-10-02.** Revised against the third `design-review.json` (CHANGES_REQUESTED:
2 HIGH, 6 MEDIUM, 5 NIT, reviewed at `32b632e3`). Both HIGHs are resolved and every MEDIUM and
NIT is resolved or explicitly dispositioned; the mapping is in §14. Two of the findings were
blocking in the same way revision 4's were — one control was **defeated by its own derivation**
(the gift-card code was recoverable from a log line this repository mandates writing in full), and
one gate would again have **gone red against correct post-fix code**. One further thing happened
during this revision that no finding asked for: §3's four `curl` commands **no longer work**, the
Wix documentation has moved, and re-measuring against the new location contradicted a row this
document had been carrying since revision 1. §3.0 and §3.4 record that, and §1.3.1 re-runs the
coupon verdict rather than editing the row underneath it — which is the halt rule finding 7 asked
for, applied to its own author on the first occasion it bit.

**Revision 6, 2026-10-02.** Revised against `design-review2.json` (CHANGES_REQUESTED: 1 HIGH,
3 MEDIUM, 5 NIT, reviewed at `32b632e3`, with all thirteen prior findings confirmed resolved).
Every finding is resolved; none is backlogged and none is dispositioned away. The mapping is in
§15. No verdict, no architecture and no decision in §1 changed, and the locked decisions were not
relitigated.

The HIGH is the third consecutive review to land on the same mechanism, and it is worth naming
the pattern rather than just fixing the instance: revision 4's gate **failed on correct code**,
revision 5's replacement **passed on any code**, and both were written against the intent of a
test rather than against what the test actually executes. The runtime item-shape helper was sited
in a test that drives no transaction at all — it builds an empty `FakeTable` and calls `scan()` —
so it would have iterated an empty recording, asserted nothing, and let §7 report the only
balance-moving write in the module as shape-checked. It is re-sited onto the tests that
really drive a transaction (**six** of them — revision 6 said four; §5.5 enumerates the list and
revision 8 corrected the count), and it now **refuses an empty recording** so that "nothing was
recorded" is a failure instead of a pass. The accompanying MEDIUM is the other half of the same
mechanism: the AST arm pinned two call sites in two named functions, which the shared bounded
retry §5.3.1 specifies would not produce — so §5.3 now **decides** that `_transact_with_retry` is
the module's only transaction site, and the guard follows the decision instead of guessing at it.

**Revision 7, 2026-10-02.** Revised against the re-review in `design-review2.json`
(CHANGES_REQUESTED: **0 HIGH**, 2 MEDIUM, 4 NIT, reviewed at `32b632e3`, with all thirteen
findings of the first review **and** all nine of the intervening one confirmed resolved against
the tree rather than against this document's dispositions). Every finding is resolved; none is
backlogged and none is dispositioned away. The mapping is in §16. No verdict, no architecture and
no decision in §1 changed, and the locked decisions were not relitigated.

Both HIGH mechanisms are now confirmed closed by the reviewer and **neither recurs**: the
gift-card code is keyed by HMAC under the existing `code_pepper` with a domain tag, and the
access-pattern gate is split so the AST arm asserts presence and location while a runtime helper
over `table.calls` asserts item shape and refuses an empty recording. The two remaining MEDIUMs
are of a milder kind than the three consecutive HIGHs: a parameter whose **path from the test to
the code** was never stated, and a return contract **stated twice with two different key sets**.
Both are now closed the way the pattern above demands — by deciding and writing down the
mechanism, and by making one assertion own the property instead of prose owning it. `redeem()`
and `void()` gain a defaulted keyword-only `sleep`, stated as the additive public signature
change it is; the seven-key return contract has exactly one enumeration and §2.4 Group C asserts
it on **both** branches.

No live Wix write, no deploy, no provisioning, no secret value read. The Wix credential
appears only as the secret **name** `wecare/wix/headless-api-key`; the gift-card code pepper only
as `wecare/wix/giftcard-spi`, field `code_pepper`. The one outbound action this revision took was
a **read** of the public `dev.wix.com` markdown rendition, to re-quote §3.1's five legacy cells in
a syntax the live source can actually produce (finding 5).

**Revision 8, 2026-10-02.** Revised against the re-review in `design-review2.json`
(CHANGES_REQUESTED: **0 HIGH**, 3 MEDIUM, 4 NIT, reviewed at `32b632e3` against revision 7, with
**all thirteen** findings of the first review and **all nine** of the intervening one confirmed
resolved against the tree). Every finding is resolved; none is backlogged and none is
dispositioned away. The mapping is in §17. No verdict, no architecture and no decision in §1
changed, and the locked decisions were not relitigated.

The three MEDIUMs are the same family this document has now repaired five times, and the reviewer
is right to name it rather than treat each as fresh: **a number or a scope written against the
intent of a test rather than against what the test will execute.** This revision closes the family
by removing the three remaining instances of it *and* by removing the thing that keeps producing
them — a literal where a property belongs:

* the runtime helper's expected transaction count was `2` for three void callers that drive **3
  and 4**, because `FakeTable` records an armed-and-failed transaction and `arm_failure` fires
  once. The per-test literal is **deleted** and replaced by `seen >= 2` plus a direct assertion
  that the **set of committers exercised** is `{redeem, void}`, which is the property the count
  was standing in for and which does not drift when a test gains a call. Stating any number first
  required deciding a behaviour §5.3.1 had left ambiguous, and §5.3.1 now decides it: a duplicate
  `void()` **refuses at the pre-read, before any transaction is opened**, which is today's
  behaviour at `gift_card_store.py:1441`. The **same ambiguity sits on the redeem side** — §5.3's
  *"claim already settled"* row — and the review did not reach it; it is decided here the same
  way, because `redeem()` already short-circuits a settled claim at `:1237-1242`;
* two Group C assertions **could not fail against any code**, keyed or unkeyed, because `card_code`
  upper-cases and the two prefixes differ — computed: `demo_code("wd-gc-sample-2026-10-02")` is
  `WDGCB4A4841861208FA8` and is not a substring of the key in any case form. They are rewritten
  onto case-normalised digest **bodies**, with the demo derivation's recoverability asserted
  **positively** so the negative assertion means something;
* §5.6 certified *"nothing divides"* in the same revision in which §5.3 introduced
  `_secrets.randbelow(25) / 1000`. The rule is **scoped** rather than restated: no float may reach
  an **amount**; a retry delay is a duration, and the permission is written down with its reason.

No live Wix write, no deploy, no provisioning, no secret value read, and **no outbound action at
all** in this revision: every finding was closed against the repository, and the three the reviewer
measured (`_CreditThrottles`, `arm_failure`, the `credited` pre-read, the AST gate's node filter,
and the two computed digests) were re-measured here before being acted on.

---

## 0. What the owner asked, and the shape of the answer

The owner's instruction is that coupons and gift cards should be **Wix only** — no backend of
ours — *if that is achievable*. §1 establishes achievability from evidence, separately for each
feature, before anything is designed. The verdicts are not symmetric, and the reason is a
measurable difference between the two Wix APIs rather than a preference:

| Feature | Verdict | One-line reason |
|---|---|---|
| **Coupons** | **(B) Wix-only not available** | `Create Coupon` has **no idempotency key** and **no documented read-by-code**, so an ambiguous create is unrecoverable. Our table is load-bearing. **Unchanged by revision 3** — §1.3.2. |
| **Gift cards** | **(A) Wix-native available, and chosen** | Wix-native gift cards are GA, carry a server-side `idempotencyKey`, are queryable by full code, carry amounts as exact decimal strings, and own `balance` as `readOnly`. The gate — *is the Wix Gift Card app installed on this site* — was answered **YES** by the owner on 2026-10-02. |

Consequences, stated once so the rest of the document is unambiguous:

* **Gift cards: Wix-native is the direction.** §2.5's adapter is the artifact that direction
  needs, and §4's leg 2 is its demonstration.
* **Nothing is deleted in this change.** Retirement of our gift-card backend is the destination,
  not this commit, and §0.1 states the evidence gate it waits behind.
* **The `redeem()` concurrent double-debit fix stays designed and ready** (§5). It is retired
  **by deletion rather than by fixing** *if and when* the retirement clears the gate, and §5.0
  says so in those words so nobody later reads a closed finding as a shipped money bug. Until
  then, any surviving part of our store means the fix stands.
* Coupons keep their table. The owner memo (§6.1) is still produced for (B), and now additionally
  records the gift-card answer.
* The demo (§4) shows both models side by side — that is now a *before and after*, not a choice
  being offered.
* Wix **Loyalty** and **Referral** are out of scope (§1.5).

### 0.1 The retirement gate — what must be true before our gift-card backend is deleted

The owner's answer is **necessary and not sufficient**, and one sentence in the instruction needs
correcting rather than following, because acting on it as written would delete a money backend on
weaker evidence than it sounds like:

> "your demo (HTTP boundary stubbed, asserting the real request/response shapes) is what confirms
> the API behaves as documented on this India/INR site"

A demo whose HTTP boundary is stubbed **cannot** confirm how Wix behaves on this site. It can
only confirm that *our side* composes what the documented contract specifies and parses what the
documented contract returns — which is exactly what §2.4 Group C asserts, and it is worth having.
What it cannot see is a required scope we do not hold, a region or plan constraint, an
undocumented required field, or a response that differs from the published schema. Those live on
the far side of a real call. Conflating the two is how "the demo passed" becomes the justification
for deleting a working backend.

So the gate has three conditions, and all three must hold:

| # | Condition | Who can satisfy it | Status |
|---|---|---|---|
| 1 | The Wix Gift Card app is installed on the site | owner, dashboard | ✅ **answered YES, 2026-10-02** |
| 2 | The harness and demo are green: our request/response shapes match the documented contract, integer paise survive the decimal-string boundary, resolve-before-create consumes one create | this change | ⏳ to be built |
| 3 | **One owner-run live verification on the real site** proves Wix accepts our shape with our key: the `count` read (§6.2), then one `create` → `query`-by-full-code → balance read on a sample card. A `403`-class refusal here is a missing scope, not a negative answer | owner only — a live Wix write is a standing refusal for me | ⏳ open |

**Condition 3 is the one that was missing from the instruction and is the one that matters most**,
because it is the only one that can fail for a reason this document cannot anticipate. If it
surfaces a gap — a scope, a region constraint, a differing response shape — the retirement
**stops** and is reported, per the owner's own instruction, rather than proceeding.

**What makes retirement unusually safe here, measured rather than assumed.** Re-derived live,
2026-10-02, in account `775261844268` / `us-east-1`, 0 errors:

| Probe | Result |
|---|---|
| `lambda list-functions` filtered on `gift` / `coupon` | **empty** |
| `get-function-configuration` for `wecare-gift-cards`, `wecare-wix-giftcard-spi`, `wecare-coupons` | all `ResourceNotFoundException` |
| `describe-table stack-wecare-digital-GiftCardsTable` | `ResourceNotFoundException` |
| `describe-table stack-wecare-digital-CouponsTable` | `ResourceNotFoundException` |
| routes on API `zllr9lrg7j` matching `gift` / `coupon` | **empty** |
| secrets matching `giftcard` | **empty** |

Read precisely, and it changes the risk calculus in two ways:

1. **No gift card has ever been issued by this system**, because there is no table to hold one and
   no function to write one. So retirement cannot strand bearer value — there is no customer
   balance to migrate, which is normally the hardest part of retiring a stored-value backend and
   here is simply absent. Had a single card with a non-zero balance existed, migration would be a
   condition 4 on the gate and would need designing before anything was deleted.
2. **The §5 double-debit defect never reached a customer.** It is a latent source defect, not a
   shipped bug. §5.0 and the final report must say that in those words, because "a money bug was
   found and retired by deletion" reads very differently from "a money bug shipped".

Treat these as a dated snapshot and re-derive before the deletion lands, per
`00-current-owner-overrides.md`. Nothing above is quoted from an earlier run.

---

## 1. Can this be Wix-only? Evidence, then one verdict per feature

### 1.1 The prior decision, and why it does not settle this

The prior design already considered both routes and recorded the choice. Quoted verbatim from
`.agents/tasks/wix-coupons-giftcards-20261001/gift-cards-service-plugin-20261001.md` §1:

> **Chosen: Model A, with the balance of record in our own table.** The owner asked for cards
> created and held in our own table and Lambda; Model B puts the balance inside Wix, which makes
> Wix the authority over money we are responsible for and leaves our own table a cache.

That is decisive in one direction only, and it is the direction that matters here: **Model A was
chosen because of an owner preference, not because Wix forced it.** The same document enumerates
Model B — the Wix-managed route — as a live alternative and says so explicitly:

> Model B is recorded as the alternative and is not wired. If the owner later prefers Wix to hold
> the balance, that is a different design, not a configuration change.

The owner has now reversed that preference. So the existence of `wecare-wix-giftcard-spi` and of
a file named `gift-cards-service-plugin-20261001.md` is **not** evidence that Wix requires a
provider. It is evidence that we chose to *be* the provider. The notification's suspicion is
reasonable and the record answers it.

### 1.2 Gift cards — Wix's two models, re-measured today

**Model A — Gift Cards Service Plugin (SPI). Wix calls us.** Service
`wix.gift.cards.provider.api.v1.GiftCardProvider`. Three `POST` endpoints appended to a
configured `deploymentUri`: `v1/balance`, `v1/redeem`, `v1/void`. Verified today from the live
pages (`.../gift-cards-service-plugin/{get-balance,redeem,void,extension-config}` all HTTP 200);
all three paths, the nine error names and their application codes and HTTP codes match our
implementation exactly (§3.2). This is what `wecare-wix-giftcard-spi` implements.

**Model B1 — the Wix Gift Cards app API. We call Wix. Wix holds the balance.**

    POST   https://www.wixapis.com/gift-cards/v1/gift-cards            create
    POST   https://www.wixapis.com/gift-cards/v1/gift-cards/query      query (filterable)
    POST   https://www.wixapis.com/gift-cards/v1/gift-cards/count      count
    GET    https://www.wixapis.com/gift-cards/v1/gift-cards/{giftCardId}
    POST   https://www.wixapis.com/gift-cards/v1/gift-cards/{giftCardId}/disable
    POST   https://www.wixapis.com/gift-cards/v1/gift-cards/{giftCardId}/send-email

Service `wix.gift_cards.gift_card.v1`, every method `GA`. **This is the Wix-native model the
owner is asking for**, and measured against it, it is better suited to our constraints than the
prior document's summary suggested:

| Property | Measured value, 2026-10-02 | Why it matters here |
|---|---|---|
| `CreateGiftCardRequest.idempotencyKey` | `string`, `minLength 1`, `maxLength 100`, *"Unique identifier to prevent duplicate gift card creation. Use this to safely retry gift card creation requests."* | A **server-side** idempotency guarantee. This is exactly what our `GCORDER#` claim row supplies locally. |
| `giftCard.code` | `8..20` chars, *"can be custom-provided or automatically generated by omitting the field"* | A deterministic code is permitted, so resolve-before-generate is expressible. |
| Code obfuscation | *"The `code` field contains the **obfuscated** gift card code, for example, `****-****-****-4444`... **Only the returned code is obfuscated. You can still find a gift card by filtering `code` with the full code.**"* | Wix enforces our own bearer-value rule at its boundary, **and** read-by-full-code is documented. |
| `CreateGiftCardResponse` | *"Created gift card with the full code visible and unobfuscated. The full code isn't retrievable with the other methods."* | The create response is the **only** place the clear code exists. Design consequence in §4.3. |
| `Query Gift Cards` filter | publishes a per-field operator map including `code: ["$eq","$ne","$in","$exists",...]` | Read-by-code is a **documented** capability, not an inferred one. |
| `Amount.amount` | `type: string`, `format: DECIMAL_VALUE`, `maxScale: 2`, `gte: 0`, e.g. `"10.50"` | A **decimal string**, not a JSON number. `money.Money.to_wix()` / `from_wix()` already produce and parse exactly this, so integer paise survive the boundary with no float (§3.3). |

**And Wix itself names the first-party app as a valid provider.** From the eCommerce Gift Cards
API introduction, fetched today — the three documented ways a site gets a gift card provider:

> For these APIs to function, a gift card provider must be integrated into the site. This
> integration can be achieved by any of the following:
> * Marking your app as **dependent** on Wix Stores, Wix Bookings, or Wix Restaurants...
> * Making your app dependent on a third-party app that implements the Service Plugin...
> * Building your own app that implements the Wix eCommerce Gift Cards Service Plugin.

So an external provider is **one of three** routes, not a requirement. Wix Stores can be the
provider. That answers the notification's structural question: **Wix-native gift cards are not
structurally impossible — they are a GA Wix product.**

#### 1.2.1 The single gate, and why it cannot be read from here

One sentence from `Create Gift Card`'s own *Before you begin*, quoted verbatim:

> * To use the Gift Cards API, the site must have the **Wix Gift Card app** installed.
> * Email delivery features require a **premium site plan**.
> * Gift card codes are obfuscated in all API responses.
> * All monetary amounts must include 2 decimal places maximum precision.
> * Currency codes must follow ISO-4217 alphabetic format...
> * A site supports a maximum of 1 gift card **product**... Creating a second product returns a
>   `GIFT_CARD_PRODUCT_ALREADY_EXISTS` error.

**Two corrections to that quotation, both from revision 5's re-measurement (§3.3).**

The one-product limit **does not constrain this design**, and the bullet as quoted reads as though
it might. The introduction scopes it precisely: the limit is on the *storefront* **gift card
product**, *"managed by a separate API"*, and it offers our exact use case as the alternative in
the same breath — *"create individual gift cards directly with this API and hand them to specific
people instead of selling them in your store"*. We create no product, so the cap is irrelevant
rather than nearly-binding.

And the premium gating is **prose, not a verifiable error name**. Revisions 1-4 said *"the
method's documented error set includes `SITE_IS_NOT_PREMIUM`, so plan gating is real and
machine-observable"*. The markdown source renders no error set for any method (§3.0.1), so that
error name is not re-verifiable from here. What *is* documented is the prerequisite itself:
*"Email delivery features require a premium site plan."* Read precisely, it gates **email
delivery** and nothing else — and §2.5 sends no `notificationInfo`, so this design does not
depend on a premium plan at all. The claim is downgraded rather than deleted because the
prerequisite is real; only its machine-observability was overstated.

Nothing in the fetched documentation imposes an India or INR restriction on this API. `currency`
is any ISO-4217 alphabetic code and is `immutable` per card. Whether the Wix *Gift Card app* is
offered on this site's plan and region is a product fact rather than an API fact, so it is not in
the schema and had to be measured. **It has been: the owner confirmed on 2026-10-02 that the app
is installed on the live site** (§0.1). The caution that produced this paragraph was still the
right one — this site demonstrably lacks some first-party features, `wixInvoices` reports NOT
AVAILABLE — and the lesson survives the answer: availability is measured, never inferred.

I could not measure it myself, and still cannot: reading it requires an authenticated Wix call,
and reading a secret value is a standing refusal. That is why the answer had to come from the
owner, and it is also why condition 3 of the §0.1 gate stays owner-run.

#### 1.2.2 Verdict — gift cards: **(A) Wix-native available, and chosen**

The gate named here in revisions 1 and 2 — *is the Wix Gift Card app installed on this site* —
was answered **YES** by the owner on 2026-10-02, by the cheapest of the two routes below:

1. **Owner, in the Wix dashboard** — Apps → *Installed Apps*, look for **Wix Gift Card**. One
   look, no API, no credential. ✅ **Present.** Wix coupons were confirmed present in the same
   look, which bears on §1.3.2 and not on this verdict.
2. **The equivalent owner-run read**, which is now **not** a gate on the verdict but **is**
   condition 3 of the retirement gate (§0.1), because it tests something the dashboard does not —
   whether *our key* is accepted with *our shape* on *this* site:

   ```
   POST https://www.wixapis.com/gift-cards/v1/gift-cards/count
   ```
   Empty filter body. A `200` with a count proves the API is live and the key carries the scope; a
   `403`-class refusal is a missing scope rather than a negative answer. Call shape and
   credential-by-name handling in §6.2. **Count, not create**, deliberately: it is a read, so it
   cannot write to the live store.

**So the direction is Wix-native, and the deletion still waits.** `gift_card_store.py`,
`GiftCardsTable`, `wecare-gift-cards`, `wecare-wix-giftcard-spi`, their provisioners, IAM, routes
and tests all stay **in this change**. Two independent reasons, and either alone is sufficient:

* conditions 2 and 3 of the §0.1 gate are not yet satisfied, and condition 3 cannot be satisfied
  by me at all;
* a dashboard glance establishes that the *product* exists. It does not establish that the *API
  contract behaves as documented for our key, our shape and our site*, which is the thing the
  retirement actually depends on.

While any part of our store survives, it is the authority for bearer value, so the `redeem()`
concurrent double-debit fix remains designed and ready (§5) — and §5.0 states precisely what
becomes of it on each side of the gate.

§6.4 lists the exact source inventory, so the size of the retirement is visible before it is
taken. The removal itself is still **not designed here**: it is a separate change, and authoring
a deletion of a stored-value backend in the same commit that first demonstrates its replacement
is how a latent money defect gets retired without ever being understood.

### 1.3 Coupons — Wix-native issuance, and the idempotency question

Wix Coupons V2 is already the arithmetic authority and must stay so. From `wix_coupons.py`'s own
module docstring, which is the invariant this design preserves:

> This table owns **issuance**... Wix's `Calculate Cart` owns the **arithmetic**.

So the only question is issuance and uniqueness. Measured today on
`.../coupons/coupons/create-a-coupon` (HTTP 200) and `.../coupons/query-coupons` (HTTP 200):

| Property | Measured value | Consequence |
|---|---|---|
| Server mapping | `URL: https://www.wixapis.com/stores/v2/coupons` (`create-a-coupon.md:50`), plus the `curl -X POST 'https://www.wixapis.com/stores/v2/coupons'` examples at `:91` and `:115`. **The `"sourcePath"`/`"destinationPath"` wording quoted here in revisions 1-5 is legacy, from the pre-404 blob, and returns zero matches in the `.md` rendition — the fact is re-confirmed in the form above (§3.1).** | `/stores/v2/`, not `/ecom/`. Our adapter is correct. |
| `code` | `type: string`, *"Must be unique for all coupons on your site. Max: 20 characters"* | Wix **does** own site-wide uniqueness. |
| Idempotency key | **Absent.** The only occurrence of "Idempotency" anywhere on the page is a left-nav link to `/business-management/payments/payment-service-provider-service-plugin/idempotency` — a different service plugin's article. There is no `idempotencyKey` in `CreateCouponRequest`. | A create cannot be safely retried. |
| Documented errors | Revisions 1-4 read `errors: []` — no failure of any kind, no duplicate-code error. **Revision 5 downgrades this to unverified**: the current documentation source renders no `Errors` section for **any** method (§3.0.1), so an empty search here is a property of the rendition rather than evidence about the API. | A duplicate is **not known to be distinguishable** from a timeout, and nothing available documents one. The practical consequence is identical — there is no documented error to branch on — but the claim is now "no duplicate error is documented" rather than "the error set is empty". V1 is what carries the verdict, and V1 is confirmed directly. |
| `CreateCouponResponse` | `{"id": "..."}` — the id only, not the coupon | A lost response loses the only handle to the coupon. |
| Read by code | **Documented after all — corrected in revision 5.** `Get Coupon` is by `{id}`, and `Query Coupons`' `filter` is a free-form **`string`** whose only *method-page* example is `{"expired":"true"}` — but the API's dedicated `filter-and-sort` article publishes a per-field operator table that **includes `specification.code`** (`$eq,$ne,$hasSome,$contains,$startsWith`). §3.4 has the measurement. | A recovery path from an ambiguous create **does** exist. It does not make the create atomic — see the second-order point below, which anticipated exactly this — so the verdict is re-run in §1.3.1 and stands. |

**State the failure precisely, because the usual summary is wrong.** Our table is *not* what
makes the code unique — Wix is. What our table supplies is **recoverability of the coupon id
after an ambiguous create**:

1. We `POST /stores/v2/coupons`. Wix creates the coupon. The response is lost — a timeout, a
   Lambda freeze, a dropped connection.
2. We retry. Wix now refuses it, because the code is already taken. We receive an undocumented
   non-2xx, which `wix_ecom._request` correctly collapses to a status-only `WixEcomError`.
3. We now hold a coupon that exists in Wix, is live, and whose `id` we do not know. **Revision 5
   correction: we *can* now look it up** — `specification.code` is a documented filter (§3.4) — so
   this step is recoverable by querying rather than only by our own row. What we still cannot do
   is know, at step 2, *whether the refusal was ours*: a non-2xx with no documented duplicate
   error is indistinguishable from a conflict with a coupon somebody created in the dashboard.

`COUPON#<codeUpper>` plus `wixCouponId`/`wixMirrorState` is what makes step 3 survivable without
depending on an undocumented-until-now filter: the row is claimed before the Wix call, the retry
converges on the same row, and `PENDING_WIX` fails closed so the coupon is refused by `evaluate`
until a human resolves it. That is a real guarantee and Wix alone does not offer a substitute.

**The second-order point this document recorded in revision 1 is what carries the verdict now,
and it was written for exactly this contingency:** even if `Query Coupons` *did* honour a `code`
filter, query-then-create is a TOCTOU race, and closing it needs either a server-side idempotency
key (absent, V1, re-confirmed) or a documented duplicate error to branch on (not documented, and
after §3.0.1 not even re-verifiable from the markdown source). So a code filter improves
**recovery**, not **atomicity** — and atomicity is what an issuance ledger is for. The filter
turned out to exist; the sentence that said it would not matter was already in the document, so
the verdict did not have to be guessed at under pressure.

#### 1.3.1 Verdict — coupons: **(B) Wix-only is not available**

Our coupon table is **load-bearing, not redundant**. Keep `coupon_store.py`, `CouponsTable`,
`wecare-coupons`, its provisioners, routes and tests exactly as they are. The architecture is
already the one the owner wants in the part that matters — **Wix does all the discount
arithmetic** — and our table holds only issuance identity, usage counters and holds. It returns a
verdict from a closed vocabulary and never an amount.

**Revision 5: the verdict was RE-RUN, not inherited, and it comes out the same.** §3.4 contradicted
one clause this verdict had been resting on since revision 1 — `Query Coupons` **does** publish a
per-field operator map, and `specification.code` is in it — and §3.0's halt rule says a
verdict-carrying disagreement re-runs §1 rather than editing the row. Re-run from the corrected
evidence:

| Requirement for (A), Wix-only issuance | Evidence after re-measurement | Met? |
|---|---|---|
| a create that can be safely retried | `CreateCouponRequest` has **no `idempotencyKey`** (V1, re-confirmed: `grep -c` returns 0) | **no** |
| a way to distinguish *my duplicate* from *another conflict* | no documented duplicate error; and §3.0.1 establishes the markdown source renders **no** error sets at all, so this is unverifiable rather than merely absent | **no** |
| a way to recover the id after a lost response | `specification.code` **is** a documented filter (§3.4) | **yes — this is the change** |

Two of the three still fail, and they are the two that matter: a recovery path narrows the
consequences of an ambiguous create, it does not prevent one. **So (B) stands, and the stated
reason narrows** — from *"no idempotency key and no read-by-code"* to *"no idempotency key and no
duplicate error, so an issuance ledger of ours is what supplies atomicity"*. That is also exactly
the owner's locked decision: our table is the issuance ledger kept **for idempotency**, and Wix
does the discount arithmetic. The re-measurement reinforces that decision rather than disturbing
it, because the thing Wix newly turns out to offer is the one thing the decision was never
relying on.

**What the correction does change** is §1.3.1's old "single check" and §6.6: the narrowing is now
answered by documentation instead of needing an owner-run probe. Our row **could** shrink toward a
`code → wixCouponId` claim ledger with a thinner mirror-state machine, because a lost `wixCouponId`
is recoverable by query. That is a **follow-up, not part of this change**, for two reasons: it is
a schema change to a table this task does not otherwise touch, and `$hasSome`/`$contains`
semantics on a `specification.code` filter inside a double-encoded JSON string is precisely the
kind of thing to verify against the live API before a reconciliation path depends on it (§6.6).
Either way a table of ours remains, which is why this is (B) and not (C).

A decision memo for the owner is written at
`.agents/tasks/wix-coupon-giftcard-sample-20261002/wix-native-decision-memo.md` — §6.1.

#### 1.3.2 "Coupons are present in Wix too" does not move this verdict, and here is why

The owner confirmed on 2026-10-02 that Wix coupons exist on the site, in the same look that
settled the gift-card gate. It is a reasonable inference that this should push coupons toward (A)
the way it pushed gift cards. It does not, and the asymmetry is measured rather than preferred:

| | Gift cards | Coupons |
|---|---|---|
| What the owner's look established | the **app is installed**, which was the *only* open gate | the **feature exists**, which was never in question |
| What blocks (A) | nothing, now | `CreateCouponRequest` has **no `idempotencyKey`** (V1), and no duplicate error is documented, so a duplicate is indistinguishable from a timeout (§1.3). **Revision 5 removed a third reason that turned out to be false** — a `code` filter *is* documented (§3.4) — and the verdict is unchanged because that reason only ever bore on recovery, not atomicity |
| Nature of the blocker | a **product availability** fact — answerable by looking | an **API capability** fact — not answerable by looking, and unchanged by anything being enabled |

The gift-card gate was *"is this switched on?"*. The coupon gate is *"does this API expose a
primitive that would let a lost response be recovered?"*, and the answer is still no. Enabling a
feature does not add an idempotency key to its create request. So:

* **Coupon issuance stays ours.** `coupon_store.py`, `CouponsTable`, `wecare-coupons`, their
  provisioners, routes and tests are untouched by revision 3.
* **What the owner's confirmation does change** is the *availability* of the Wix coupon surface
  for applying discounts — which was already the design, since §1.4 has Wix doing all the
  arithmetic. It makes §6.5's live sample coupon runnable against a surface known to be present,
  rather than one assumed to be.
* The verdict is revisitable on exactly one event, unchanged from revision 1 and **narrowed by
  revision 5 to the thing that would actually move it**: if Wix ever documents a duplicate-code
  error or an idempotency key on `Create Coupon`, an ambiguous create becomes *unambiguous* and
  coupons move toward (A). §3.0.1's command (1) is written so that re-running it later answers
  that in one line — a count, not a silence. A newly documented *filter* does not move it, which
  is now a measured fact rather than a hypothetical (§3.4).

### 1.4 What is NOT in question

Discount arithmetic is Wix's, today and in every branch above. Nothing in this design computes a
discount, and `wix_coupons.py`'s ban on reading any numeric field off a Wix coupon response stays
(§3.3). The owner's underlying instinct — one system does the money maths — is already satisfied.

### 1.5 Wix Loyalty and Wix Referral — present on the site, OUT OF SCOPE for this build

Recorded here so they are not lost, and recorded *as out of scope* so they are not quietly pulled
in. In the same 2026-10-02 message that answered the gift-card gate, the owner mentioned that
**Loyalty** and **Referral** are also present on the Wix site.

They are **separate Wix products with separate APIs**, not variations of coupons or gift cards:

| Product | What it is | Why it is not a coupon or a gift card |
|---|---|---|
| **Wix Loyalty** | points balances, earning rules, tiers, and redemption of points for rewards | a points balance is an *earned* balance with its own accrual rules. It is not bearer value and not a discount definition |
| **Wix Referral** | referral programs, referred-friend rewards, reward fulfilment | an event-driven reward issuance flow; its output may *be* a coupon, which is exactly the kind of adjacency that invites scope creep |

**Nothing about them is designed, built, measured or assumed in this task.** Specifically: no
adapter, no table, no route, no fixture, no contract verification, and no claim anywhere in this
document about how their APIs behave. I have not fetched their schemas, so this document contains
no evidence about them and must not be read as having any.

Two reasons for the hard line rather than an opportunistic addition:

1. **Each would need its own §1-style evidence pass.** The whole value of §1 is that the verdict
   per feature follows from a measured API property — gift cards cleared because
   `idempotencyKey` exists, coupons did not because it does not. Loyalty and Referral have had no
   such pass, so any design for them here would rest on nothing.
2. **Loyalty is stored value with accrual, which is harder than either feature in this task.**
   A points balance has the same double-move hazard §5 spends its length on, plus earning rules
   and expiry. Bolting it onto a task whose subject is a coupon-and-gift-card sample is how that
   hazard arrives undesigned.

If the owner wants them, that is a **separate workflow** with its own requirements and its own
contract verification. The one thing worth carrying forward is that §5's analysis — an
idempotency fact and a balance on different items cannot be gated by a single-item conditional
write — would apply directly to a loyalty points balance, so that workflow should start from it
rather than rediscover it.

---

## 2. The local harness — real code paths, Wix stubbed at the transport layer only

### 2.1 Where the boundary is, and why it is the only honest place to cut

`wix_ecom._request` (`amplify/functions/shared/lambda_utils/wix_ecom.py`, lines 84-116) is the
single HTTP boundary for every Wix call in this repo. Read from the tree, it does five things we
must not stub past, because each one has already been the subject of a finding.

**Line citations in this document are symbol-first from revision 4 on.** Five of them had drifted
by a few lines against `32b632e3` — all substantively correct, all wrong enough to undermine the
one thing they exist for, which is being checkable. They are re-derived below and in §2.2, §2.3,
§4.3 and §5.5, and where a symbol name carries the same meaning the number is dropped, because a
symbol does not drift.

1. composes `WIX_API_BASE + endpoint` into `url`;
2. builds the header set `Authorization`, `Content-Type`, `Accept`, `wix-site-id`;
3. serialises with a bare `json.dumps(body or {})` — **no custom encoder**, so a `Decimal`
   raises `TypeError` before the request leaves the process;
4. collapses every non-2xx `HTTPError` into one **status-only** `WixEcomError` message;
5. parses with `json.loads(payload)` — **no `parse_float`**, so a Wix JSON number arrives as a
   Python `float`.

Stubbing at `WixCoupons(request=...)` — which is what `tests/test_wix_coupons_contract.py`'s
`Wix` spy does, correctly, for its own purpose — bypasses all five. That spy proves what the
adapter *intends* to send. The harness must additionally prove what actually **goes on the wire**
and what survives coming back. So:

> **The stub replaces `urllib.request.urlopen` and nothing else.** Every line of
> `wix_ecom._request` executes for real.

`_request` does `import urllib.request` *inside* the function body, so a module-level
`monkeypatch.setattr("urllib.request.urlopen", ...)` is in effect by the time the import resolves
to the already-imported module object. No import-order trickery is required.

### 2.2 Keeping AWS out of it

`_request` calls `_api_key()`, which lazily builds a `boto3` Secrets Manager client. The harness
must not allow that and must not need credentials.

`_api_key()` short-circuits on `if "key" in _key_cache` (in `_api_key`, before its `import
boto3`). The harness pre-seeds that cache, reversibly:

```python
monkeypatch.setitem(wix_ecom._key_cache, "key", PLACEHOLDER_API_KEY)
#   "wix-admin-key-PLACEHOLDER-not-a-credential"
```

`monkeypatch.setitem` rather than a direct `wix_ecom._key_cache["key"] = ...`: that dictionary is
a module global and a direct write survives for the life of the pytest process, so a later test
expecting `_api_key()` to take its Secrets Manager branch would silently get the placeholder.
Nothing does today; the leak is free to avoid.

`_api_key()` then returns on its first line. This is **by-reference discipline inverted for a
test**: there is no credential anywhere, so there is nothing to leak.

**How the containment is asserted, and the one claim that had to be dropped.** The obvious
assertion — `assert "boto3" not in sys.modules` — is not sound inside the suite, and the reason
is measured rather than theoretical:

* `sys.modules` is process-global and CI runs a bare `python -m pytest -q` over the whole tree
  (`.github/workflows/route-auth.yml:111`), so another module's import of `boto3` is enough to
  turn it red independently of the code under test;
* worse, it is false *within this very test module*. Group B drives
  `amplify/functions/ecommerce/coupons/handler.py` (§2.4), which imports `middleware` and
  `rate_limit`; both `import boto3` at module scope and **construct a client at import** —
  `middleware.py:24` builds a `cognito-idp` client (its `import boto3` is at `:16`),
  `rate_limit.py:48` a `dynamodb` resource (`import boto3` at `:42`).
  Importing the production handler therefore imports `boto3` before a single assertion runs.

So the harness asserts the fact that actually matters, locally and more strongly:

```python
monkeypatch.setitem(sys.modules, "boto3", _ExplodesOnAttributeAccess())
... drive the harness ...
assert wix_ecom._secrets is None        # no Secrets Manager client was ever constructed
```

**The sabotage raises a `BaseException`, for the same reason `UnexpectedWixCall` does (§2.3).**
This was missed when that reasoning was first written and it is the identical hole:

```python
class _UnexpectedAwsUse(BaseException):
    """Deliberately NOT an Exception. `wix_ecom._request` ends in `except Exception` and
    `coupons/handler._create` catches Exception and answers 202, so an AssertionError from
    here would be reported as a documented success with no AWS call in sight.
    """

class _ExplodesOnAttributeAccess:
    def __getattr__(self, name):
        raise _UnexpectedAwsUse(f"boto3.{name} was reached under the no-AWS harness")
```

One mitigating fact, recorded because it is layout rather than design and should not be relied
on: `_api_key()` is called at `wix_ecom.py:96`, inside the `headers` dict literal, which is
**outside** `_request`'s `try:` at `:103` — so a raise from the key path escapes `_request`
rather than becoming a `WixEcomError`. That is luck, it does not help inside `handler._create`,
and it is not a substitute for the base class above.

The sabotage is installed **after** module import and before any production call. `_api_key()`
does `import boto3` *inside* the function, so it resolves through `sys.modules` and would raise
immediately on `boto3.client(...)` — entering the non-cached branch at all is the failure.
`middleware` and `rate_limit` already hold their own module references bound at their import, so
they are unaffected and the sabotage cannot break them. Client **construction** at import makes
no AWS call; `_secrets is None` is what proves no credential was ever reached for.

The demo runs in its own process, so a `sys.modules` statement *is* sound there — but it is not
*true* there either, for the same transitive reason, so §4.3 replaces it with two facts that are
both true and enforced: no Secrets Manager client was built, and zero AWS API calls were
attempted.

`PLACEHOLDER_API_KEY` is chosen to be obviously inert and to match none of
`scripts/block_inline_secrets.py`'s issuer prefixes (`rzp_live_`, `sk-`, `AIza`, `ghp_`, `xoxb-`,
`AKIA`/`ASIA`, `sk_live_`, `ksk_`, PEM headers). It is a module constant, never an argv value and
never an environment assignment, so no hook and no history can record it as a command string.

### 2.3 `tests/wix_transport_stub.py` — new file

One exception class and one callable class. It is a `urlopen` replacement, so its contract is
`urlopen`'s.

**The refusal must not be an `Exception`, and this is load-bearing rather than fastidious.**
`wix_ecom._request` ends in a bare `except Exception` that converts anything it catches into a
`WixEcomError` (`wix_ecom.py:109-111`; the enclosing `try:` is at `:103`), and
`coupons/handler.py::_create` then catches `Exception`
and answers **202** with a documented-success body (`handler.py:229-233`). An `AssertionError`
raised by this stub is an `Exception`, so it would be laundered first into a transport error and
then into a success — which is precisely the "passing quietly" the stub exists to prevent, and it
would defeat the resolve-before-create property that §2.4 Group C leans on entirely:

```python
class UnexpectedWixCall(BaseException):
    """Deliberately NOT an Exception, so production error handling cannot swallow it.

    `wix_ecom._request` ends in `except Exception` and `coupons/handler._create` catches
    Exception and answers 202. An AssertionError from this stub would therefore be reported
    as a successful, documented outcome. BaseException escapes both.
    """
```

`UnexpectedWixCall` is used for all three stub-side refusals: an empty queue, an argument that is
not a `urllib.request.Request`, and the teardown leftover check. Plain `AssertionError` is kept
only for assertions made *outside* a stubbed call, where nothing is catching.

```python
class WixTransport:
    """Replaces urllib.request.urlopen. Records the REAL request; serves queued responses."""

    def __init__(self) -> None:
        self.requests: list[RecordedRequest] = []
        self._queue: list[Queued] = []

    def expect(self, *, method: str, endpoint: str, status: int = 200,
               body: dict | None = None, raw: bytes | None = None) -> "WixTransport": ...
    def expect_http_error(self, *, method: str, endpoint: str, status: int) -> "WixTransport": ...
    def __call__(self, request, timeout=None): ...
```

**The queue is typed by the call each entry answers, and that is what makes "one create, not two"
enforceable.** Revision 4 described an untyped FIFO of responses and then named its empty-queue
refusal as the mechanism enforcing resolve-before-create. Those two statements cannot both hold,
and the gap is exactly on the property that separates verdict (A) from (B):

> The replay scenario queues **query(miss) → create → query(hit)**. A regression that issues a
> second `POST .../gift-cards` instead of a query pops the queued **query** response, parses it
> happily, and the queue is never empty. The named enforcement does not fire, and the test passes
> while the adapter creates two cards.

So `expect` takes the `method` and `endpoint` it answers, and `__call__` compares them against
the real `Request` before popping:

```python
if (request.get_method(), request.full_url) != (expected.method, WIX_API_BASE + expected.endpoint):
    raise UnexpectedWixCall(
        f"expected {expected.method} {expected.endpoint}, got "
        f"{request.get_method()} {request.full_url}")
```

A mismatch is refused at pop time rather than detected afterwards, so the failure names the wrong
call instead of surfacing as a confusing parse error three lines later. `endpoint` is the
path — the stub prepends `wix_ecom.WIX_API_BASE` itself, so a test cannot accidentally pin a
different host and still match.

**What it records.** A frozen dataclass per call, so an assertion reads like the contract:

| Field | Source | Note |
|---|---|---|
| `method` | `request.get_method()` | `GET`/`POST`/`PATCH`, from the real `Request` |
| `url` | `request.full_url` | the **absolute** URL, so the `/stores/v2/` vs `/ecom/` question is answered on the wire |
| `headers` | `dict(request.header_items())` with `Authorization` replaced by `"<redacted>"` | see below |
| `authorization_present` | `bool` | the *fact*, never the value |
| `body_bytes` | `request.data` | exactly what `json.dumps(...).encode("utf-8")` produced, or `None` for `GET` |
| `body` | `json.loads(body_bytes)` or `None` | convenience; assertions about JSON **types** use `body_bytes` |

**The credential is redacted at capture, not at print.** `RecordedRequest` never holds the
`Authorization` value at all. A test artifact, a pytest failure diff, a `--json` transcript and a
CI log therefore cannot carry it even in principle, and no reviewer has to check whether a
particular print site remembered to mask. The value is a placeholder today; the structure is what
must survive the day somebody points the harness at a real key by accident.

**The rule is asymmetric, and the asymmetry is stated here rather than left to be discovered.**
`RecordedRequest` holds `body_bytes` and `body` **verbatim**, so a gift-card code travelling in a
`find_by_code` filter **is** recorded, and a pytest failure diff would print it. That is
deliberate and it is not a hole, for one reason that has to be true for it to hold:

> **Every gift-card code anywhere in the harness or the demo is a fixture placeholder.** The
> transport is stubbed unconditionally — there is no code path, flag or environment in which a
> real Wix response reaches this process — so no clear code that exists offline is bearer value,
> and recording one discloses nothing. §2.5's earlier claim that a code "must not be recorded"
> was withdrawn in revision 4 as both untrue of this stub and misleading about which rule is
> load-bearing.

The credential is treated differently on purpose: `wix_ecom._key_cache` is a module global that a
future test could seed from Secrets Manager by accident, so a real key *can* arrive in this
process in a way a real gift-card code cannot. Capture-time redaction is therefore where the
credential rule belongs and where it stays. The renderer's code-masking (§4.3) is kept as a
habit for the day the demo is pointed at something real, and is labelled there as **not**
load-bearing offline, so nobody reads it as the thing protecting a secret.

**What it serves.** `expect(...)` queues a response; `__call__` pops the head. The returned object
is a minimal context manager with `.read() -> bytes`, plus `.status` and `.headers`. **Only
`.read()` is touched by `_request`** (`wix_ecom.py:104-105`: `urlopen` at `:104`, `.read()` at
`:105`); `.status` and `.headers` are provided
so a future assertion about a response code has somewhere to read it from, not because anything
consumes them today — said explicitly so a reader looking for the `.status` consumer is not sent
hunting for one. `expect_http_error(method=…, endpoint=…, status=…)` raises a genuine
`urllib.error.HTTPError(url, status, "", {}, None)`, which is what makes assertion 4 above
testable: the resulting `WixEcomError` must carry the status as prose and nothing else.

**Failure modes, all loud:**

| Condition | Behaviour | Why |
|---|---|---|
| queue empty when called | `UnexpectedWixCall` naming method and URL | an unexpected Wix call is a defect, not a default — and `BaseException` is what stops `_request` and `_create` converting it into a 202 |
| **head of queue answers a different call** | `UnexpectedWixCall` naming **expected vs actual** method and endpoint, refused before the response is served | without this the queue is a bag of responses and an extra `POST` silently consumes a queued `GET`/query. This is the row that makes §2.4 Group C's one-create property enforceable rather than incidental |
| queue non-empty at teardown | `UnexpectedWixCall` listing the unconsumed entries | a call we asserted would happen and did not is the more dangerous direction |
| `request` is not a `urllib.request.Request` | `UnexpectedWixCall` | the stub must not silently accept a URL string, which would skip header and body composition |
| `timeout` not `10` | recorded, not refused | `_request` pins it; a test may assert it, the stub does not police it |

### 2.4 What the harness asserts — `tests/test_wix_coupon_giftcard_sample.py` (new)

Grouped by the question each group answers. Every one drives **production** code; none constructs
a payload by hand.

**Which production entry point each group drives, stated before the assertions, because it is not
the same one for every group and the first draft conflated two of them.** Measured at `32b632e3`:
`coupon_store` imports only `money` and `identifiers` (`coupon_store.py:65-71`) — it does **not**
import `wix_coupons`, so `coupon_store.create → WixCoupons.create` is not a call chain that
exists. The claim-row → Wix create → `mark_mirrored` orchestration lives in exactly one place in
the tree: `amplify/functions/ecommerce/coupons/handler.py::_create` (lines 204-236).

| Group | Driven entry point | Level |
|---|---|---|
| A | `coupon_store.create(fake, payload)` then `wix_coupons.WixCoupons(wix_ecom._request).create(definition)` — **two separate production calls**, composed by the test | adapter / wire |
| B | `handler._create(event, origin=...)` — the production owner of the composition | handler |
| C | `wix_gift_cards.WixGiftCards(wix_ecom._request)` | adapter |
| D | static / structural | — |

Group A is deliberately *not* routed through the handler: its subject is what goes on the wire,
and composing the two calls in the test keeps the wire assertions free of handler concerns. The
composition itself is then asserted where it actually lives, in Group B, so no assertion rests on
a chain the tree does not have.

**Driving the handler needs exactly one production function stubbed, and no more.**
`handler._staff` is `middleware.require_auth(event, STAFF_ROLE)` (`handler.py:138-140`):

```python
monkeypatch.setattr(handler, "_staff", lambda event: None)   # authenticated staff
monkeypatch.setattr(handler, "_coupons_table", lambda: fake)
```

`_staff` rather than `middleware.require_auth`, because `handler.middleware` **is** the shared
module object: patching through it mutates the auth module that 58 files under
`amplify/functions/` reference. One narrow stub, reverted at teardown. Authentication is
explicitly not this harness's subject — `tests/test_route_auth_enforcement.py` owns it — so Group
D carries one source assertion that the real `_staff` still calls `middleware.require_auth` with
`STAFF_ROLE`, which is what stops the stub from being able to hide an auth regression.

**Group A — the coupon request we would really send.** Adapter level, assertions on the wire.

| Assertion | Exact expectation |
|---|---|
| method + absolute URL | `POST https://www.wixapis.com/stores/v2/coupons` |
| `/ecom/` absent from the URL | the §1.3 server-mapping finding, asserted on the wire |
| header names, normalised | `{k.lower() for k, _ in request.header_items()} == {"authorization", "content-type", "accept", "wix-site-id"}` |
| header names, exact spelling | one separate assertion on the recorded set `{Authorization, Content-type, Accept, Wix-site-id}`. Note **`Content-type`**: `urllib.request.Request.add_header` applies `str.capitalize()`, which lowercases everything after the first character. Measured on this interpreter, not assumed. Asserting `Content-Type` fails, and that is the kind of failure that gets "fixed" by loosening the assertion rather than by reading why — so the normalised set carries the meaning and this row carries the urllib behaviour, with the reason named in the assertion message |
| `Content-Type` value | `application/json` |
| `Wix-site-id` | equals `wix_ecom.WIX_SITE_ID` |
| `Authorization` | present, value never recorded |
| body, byte-exact | `json.loads(body_bytes)` equals the full expected dict, compared whole — not key by key |
| JSON **types** | `type(parsed["specification"]["moneyOffAmount"]) is int`; `type(parsed["specification"]["startTime"]) is str` |
| no `type` field | `"type" not in parsed["specification"]` (read-only in the schema) |
| percent-off variant | a second definition drives the same path and asserts `type(parsed["specification"]["percentOffRate"]) is int` and `"moneyOffAmount" not in parsed["specification"]` — the two discount kinds are mutually exclusive in one specification, and this is the payload §6.5 hands the owner |

Byte-exact whole-body comparison is deliberate. A per-key check passes while an extra key rides
along, and an extra key in a coupon specification is a different promise to a customer.

**Group B — Wix's real documented responses, handled, and the composition that handles them.**

**The event is specified, because `created_by` is read off it and nothing was supplying it.**
Revision 4 drove `handler._create(event, origin=...)` without saying what `event` was. Read from
the tree, `_create` takes the payload from `_body(event)` — `json.loads(event.get("body") or
"{}")`, refusing a non-dict with `Refused(400, "INVALID_JSON")` — and the creator from
`(event.get("_auth") or {}).get("username")`, which `middleware.require_auth` normally populates.
With `_staff` stubbed to return `None`, nothing populates it, so `created_by` would be `None` on
every harness and demo run. Harmless in itself, but it is a divergence from production in the one
path this design drives *precisely* to avoid divergence. So the harness and the demo both pass:

```python
event = {"body": json.dumps(payload),
         "_auth": {"username": "demo-operator"},
         "headers": {"origin": "https://wecare.digital",
                     "content-type": "application/json"}}
```

The stub supplies `_auth` itself rather than having `_staff` write it, which keeps the stub to one
line and keeps the shape honest: in production `require_auth` writes `_auth` onto the event and
returns `None` on success, so an event that already carries `_auth` plus a `_staff` that returns
`None` is the same state `_create` sees live. `created_by` is therefore `"demo-operator"` on every
run, and the §4.4 transcript shows it.

Rows marked *handler* drive `handler._create`; rows marked *adapter* drive
`WixCoupons(wix_ecom._request)` directly. The split matters: a `WixEcomError` **escapes** at
adapter level and **becomes a 202** at handler level, so the first draft's single row asserting
both at once could not have been true of one call.

**The Served column names queue calls in their full typed form** — `expect(...)` and
`expect_http_error(...)` are both keyword-only in §2.3, so a positional shorthand is a call the
stub would reject. A bare response body in the column (`{"id": "..."}`, `{}`, a fixture name) is
shorthand for `expect(method=…, endpoint=…, body=…)` on that row's own method and endpoint.

| Case | Level | Served | Expected handling |
|---|---|---|---|
| create success | handler | `{"id": "..."}` | `201`; `wixMirrorState` on the row is `MIRRORED` (written by `coupon_store.mark_mirrored`, which the handler calls) |
| create success, numeric echo | adapter | `wix_coupon_get_response_float_amounts.json` | id read; **no numeric field reaches the view or the row** |
| `get` | adapter | the Get fixture | view is exactly `{id, active, type, code}` and holds no `float`. The float-containment half is true **by construction** — `_coupon_view` selects four non-numeric keys — so the row asserts the projection *is* the containment, rather than reporting a discovered property |
| `assert_mirrors`, foreign code | adapter | fixture with `code: "SOMEONEELSES"` | `WixCouponConflict` |
| `assert_mirrors`, case-only difference | adapter | fixture with `code: "save10"` and our id | **not** a conflict |
| create failure 400/409/428/500/502 | adapter | `expect_http_error(method="POST", endpoint="/stores/v2/coupons", status=…)` | `WixEcomError` whose message carries the status as prose and nothing else; it **escapes** to the caller; no mirror state is written |
| create failure 400/409/428/500/502 | handler | `expect_http_error(method="POST", endpoint="/stores/v2/coupons", status=…)` | answer is **`202`**; the row stays `PENDING_WIX`; `coupon_store.evaluate` on that row returns `WIX_MIRROR_INCOMPLETE` |
| deactivate | adapter | `{}` | `PATCH .../{id}` with body exactly `{"specification": {"active": false}}`, no `fieldMask` |

**Two of those rows named the wrong method until revision 4, and an implementer following them
literally would have written a test that cannot fail.** `WixCoupons.get` (`wix_coupons.py:244-252`)
returns `_coupon_view(response)` and raises nothing at all. Both the normalised-code comparison
and **both** `WixCouponConflict` raises live in `assert_mirrors` (`:254-280`) — one for a code
that normalises differently, one for a returned `id` that is not the id we asked about. So the
conflict rows drive `assert_mirrors`, and `get` keeps a row of its own for the projection. Note
that the existing `tests/test_wix_coupons_contract.py` already drives both conflict cases at the
adapter level with an injected callable; this harness's contribution is that they run through the
real `_request` and a real serialised response, not that they are tested at all.

The 409 rows are the ones worth re-reading: together they assert that a Wix duplicate-code
refusal is **not** specially handled at either level, which is the §1.3 unrecoverability finding
made executable.

**The float hazard needs a fixture that contains a float, and the existing one does not.**
`tests/fixtures/wix_coupon_get_response.json`, read from the tree, carries
`"moneyOffAmount": 10`, `"minimumSubtotal": 5000` and `"numberOfUsages": 3` — all JSON integers,
all parsing to Python `int`. There is no `float` anywhere in that parsed payload, so a row
asserting "the `10.0` float still does not reach the row" against it would demonstrate nothing,
and it is the row that justifies not stubbing above `_request` (§2.1 item 5). So a new fixture
is added, `tests/fixtures/wix_coupon_get_response_float_amounts.json` — the same shape with
`"moneyOffAmount": 10.0` and `"minimumSubtotal": 5000.5` — and the hazard is asserted **before**
the containment:

```python
parsed = json.loads(raw)
assert type(parsed["coupon"]["specification"]["moneyOffAmount"]) is float   # the hazard is real
view = wix_coupons.WixCoupons(wix_ecom._request).get(coupon_id)
assert not any(isinstance(v, float) for v in view.values())                # and it is contained
```

The original fixture stays in use, unchanged, for every row that is not about floats.

**Group C — the Wix-native gift-card candidate (new fixtures).** Drives the new
`wix_gift_cards.py` adapter (§2.5) through the same real `_request`.

| Assertion | Exact expectation |
|---|---|
| create | `POST https://www.wixapis.com/gift-cards/v1/gift-cards` |
| body, **byte-exact** | `json.loads(body_bytes)` equals the full dict specified in §2.5, compared **whole** — not key by key — exactly as Group A compares the coupon body, and for the same reason: an extra key in a gift-card create is a different promise. Includes `"source": "MANUAL"` (required by Wix) and asserts `"code"` and `"expirationDate"` are **absent** on the variant that omits them rather than present as `null` |
| amount type | `type(parsed["giftCard"]["initialValue"]["amount"]) is str` and the value is `Money(paise).to_wix()` |
| currency | literally `"INR"`, from an explicit comparison, never inferred |
| **the identifiers are deterministic**, asserted before anything built on them | two independent calls to `wix_gift_cards.idempotency_key(reference_id=R)` return the same string, and `card_code(reference_id=R, pepper=P)` likewise; two different `R`s give two different values; neither function reads a clock, a counter or `secrets`. This row comes **first** because the row below is meaningless without it — see the note after this table |
| **the code is keyed, and is not recoverable from the idempotency key** | `card_code(reference_id=R, pepper=P1) != card_code(reference_id=R, pepper=P2)` for two different peppers — which is the whole of the HMAC claim, stated as a test rather than as prose — **and** the non-recoverability half, asserted on case-normalised digest **bodies** in both directions, with the demo derivation's weakness asserted **positively** in the same breath. See the note below this table: the revision-7 form of this row compared the whole strings and **could not fail**, for keyed *or* unkeyed code |
| **the code is domain-separated from the store's `code_hash`** | `card_code(reference_id=X, pepper=P)` and `gift_card_store.code_hash(X, pepper=P)` are computed for an `X` that is valid as both a reference and a code, and the test asserts the two are unequal. The honest statement of what that pins is in the note below: `card_code` never returns its digest, so the test **recomputes the tagged HMAC** and is therefore pinning the **tag**, not an opaque digest comparison. That is still the property worth having — it is what stops a later "simplification" dropping `CODE_DOMAIN_TAG` — but it is a recomputation, not a black-box check, and revision 7 described it as the latter |
| `demo_code` is unkeyed, and says so | `demo_code(reference_id=R)` equals `("WDGC" + sha256(R).hexdigest()[:16]).upper()` — asserted **positively**, so the test states the weakness rather than leaving it implicit — `len(...) == 20 == MAX_CODE_LENGTH`, so the demo crosses production's length boundary, and `demo_code(reference_id=R) != card_code(reference_id=R, pepper=P)`. Group D owns the guard that no production file references it |
| both derivations sit at Wix's length ceiling | `len(card_code(...)) == len(demo_code(...)) == MAX_CODE_LENGTH == 20`. Asserted rather than commented, because the length is a security margin on bearer value (64 bits of HMAC output, not 48) and a future shortening should have to change a test |
| `card_code` refuses an absent pepper | `pytest.raises(WixGiftCardError)` for `pepper=""` and for `pepper=None`, with `exc.value.code == "A_PEPPER_IS_REQUIRED"` — the **field**, not the message text — and **zero** recorded requests |
| every refusal carries an enumerable code | for each §2.5 validation row: the raised `WixGiftCardError`'s `.code` is in `REFUSAL_CODES`, and `isinstance(exc, RuntimeError)` holds, mirroring `wix_coupons.WixCouponError`. One assertion stops the reason drifting back into the message slot |
| resolve-before-create, **enforced two ways** | (1) the typed queue (§2.3) holds `query(miss) → create → query(hit)`, so a second `POST` to the create endpoint is refused at pop time with `UnexpectedWixCall` naming expected vs actual — a `BaseException`, so it reaches the test instead of becoming a `WixEcomError` and then a 202; (2) the **recording** is counted directly, which does not depend on queue ordering at all: `len([r for r in transport.requests if r.method == "POST" and r.url == wix_ecom.WIX_API_BASE + "/gift-cards/v1/gift-cards"]) == 1`. The count is the named enforcement; the typed queue is what makes the failure legible |
| create response | full clear code is returned by Wix; the adapter returns `codeLast4` **read from `codeSuffix`** and the card id, and **never** the clear code to its caller. A response with no `codeSuffix` raises `WixGiftCardError("CODE_SUFFIX_MISSING")` rather than slicing `code` |
| query by code | `POST /gift-cards/v1/gift-cards/query`, body `{"query": {"filter": {"code": {"$eq": <full code>}}}}` — the filter is a JSON **object** here, unlike the coupon query's free-form string (§3.4) — response obfuscated, `codeSuffix` present, `balance.amount` present and parsed through `Money.from_wix` |
| `find_by_code` **miss** | a fixture whose `giftCards` is `[]` (and one whose `giftCards` key is **absent**, which Wix may send for an empty page): `find_by_code(code) == {}` exactly — not `None`, no raise — and when that fixture feeds a `create`, the recording holds exactly **one** `POST` to the create endpoint. This is the row that makes the miss contract load-bearing in the test as well as in the caller |
| `find_by_code` **multi-match** | a fixture whose `giftCards` holds **two** entries: `pytest.raises(WixGiftCardError)` with `.code == "AMBIGUOUS_CODE"`, and **zero** further recorded requests — so an unhonoured filter costs no create and no money read from an arbitrary row |
| resolve hit onto a **disabled** card | a fixture carrying `disabledDate`: `create` returns `resolved: True`, `disabled: True`, the card's current `balancePaise`, and issues **no** create call. The assertion is that the dead card is *reported*, not that it is refused — refusing would mint a second card for the same reference on the next retry |
| resolve hit carrying an expiry | the same fixture with `expirationDate`: the value is returned **verbatim and unparsed**, and the adapter makes no comparison against any clock |
| **the return key set is identical on both branches, and across both functions** | `set(result) == {"giftCardId", "codeLast4", "balancePaise", "currency", "resolved", "disabled", "expirationDate"}` asserted on a **create** result, on a **resolve-hit** result, **and on a direct `find_by_code` one-hit result** — three subjects, one key list, one assertion helper. The assertion message names the property: *branch-independence — the return shape must not depend on which branch, or which public function, produced it*. The third subject is what makes the row cover the module's other public return: `create`'s resolve branch returns `find_by_code`'s view unchanged, so a key added to one normaliser and not the other is caught here rather than by the first caller to read it. This is the row that enforces §2.5's guarantee instead of stating it, and it is also what stops a future key being added to one path only. Without it the two paths can differ by exactly the two keys that exist to make a dead resolve hit distinguishable from a live create, and every other row in this group still passes |
| fractional round-trip | `Money(250050).to_wix() == "2500.50"`, and `Money.from_wix("2500.50").paise == 250050` with `type(...) is int`. This is the demo's default gift-card value (§4.5), so the boundary §3.3 calls decisive is crossed by the default run rather than only by a special case |
| balance read-back | `Money.from_wix("999.75")` → `99975` paise exactly |

**Why determinism is asserted separately, and why "one create call" was not yet the property that
matters.** `create` takes `code` and `idempotency_key` as **parameters**, so a test that passes
the same two literals twice proves the adapter is idempotent *given identical arguments*. That is
not the dangerous case. The dangerous case is a retry that derives a **fresh** key — a new
invocation, a new request id, a timestamp in the key — and then creates a second card that Wix
considers unrelated. Nothing in the first draft of §2.5 made that impossible, and the only values
anywhere in the document were the demo's two hardcoded literals.

This is the repository's own standing rule on exactly this shape, applied to a different artifact:
an identifier that ties a replay to the thing that already exists **must be stable across
retries**, because a fresh id on retry produces a duplicate paid artifact, and that is the one
failure this domain must never have. §2.5 therefore owns the derivation, and the two rows above
are ordered so the derivation is pinned before the call-count assertion leans on it.

**The non-recoverability assertion, written against the values rather than against the intent —
because revision 7's form could not fail.** Revision 7 asserted that `card_code(...)` is *"not a
prefix, suffix or substring of `idempotency_key(...)`, nor the reverse"*, and named that in §7 as
the proof that the code is not recoverable from a log line. Computed for this document's own
default reference, that assertion is **true of the unkeyed derivation too**:

```
reference_id            wd-gc-sample-2026-10-02
demo_code (UNKEYED)     WDGCB4A4841861208FA8                                  (20 chars)
idempotency_key         wd-gc-b4a4841861208fa8a47ba149ded8cdb1d01d57660fc8a259d336a7b56c5e311d
demo_code in key                 False
demo_code.lower() in key         False        <-- the prefixes differ: "wdgc" vs "wd-gc-"
```

`card_code` returns `("WDGC" + hex).upper()` and `idempotency_key` returns `"wd-gc-" + lowercase
hex`, so the case difference **alone** makes "not a substring" true of *any* implementation. The
row claimed to assert non-recoverability and asserted nothing — the same family as the two gates
revision 5 and revision 6 had to repair, and by this document's own standard a guard that cannot
fail is already deleted and nobody can tell.

The assertion compares the **digest bodies**, case-normalised, and it asserts the weakness
positively as well as the strength negatively:

```python
def _digest_body(value: str) -> str:
    """Strip the decoration, so what is compared is the digest and not the prefix casing."""
    return value.lower().removeprefix("wdgc").removeprefix("wd-gc-")

# the keyed derivation: its digest body must NOT appear in the key's, in either direction
assert _digest_body(card_code(reference_id=R, pepper=P)) not in _digest_body(idempotency_key(reference_id=R))
assert _digest_body(idempotency_key(reference_id=R)) not in _digest_body(card_code(reference_id=R, pepper=P))

# and the demo derivation, which IS recoverable, must FAIL that same test
assert _digest_body(demo_code(reference_id=R)) in _digest_body(idempotency_key(reference_id=R))
```

**The third line is what makes the first two mean something.** It is the mutation test, written
into the suite: it states the defect positively, the way the `demo_code` row already does for the
formula, and it fails the moment someone "simplifies" `card_code` back to an unkeyed digest —
because then line 1 and line 3 contradict each other and one of them must go red. Verified by
computation here: with `R = "wd-gc-sample-2026-10-02"`, `_digest_body(demo_code(...))` is
`b4a4841861208fa8` and `_digest_body(idempotency_key(...))` is
`b4a4841861208fa8a47ba149ded8cdb1d01d57660fc8a259d336a7b56c5e311d`, so line 3 passes today and
line 1 passes only because `card_code` is keyed.

**And the domain-separation row is a recomputation, which is worth saying plainly.** `card_code`
returns `"WDGC" + digest[:16]`, upper-cased; it never returns its digest. So a test cannot compare
two opaque digests — it has to recompute one side. The assertion is therefore either

```python
assert card_code(reference_id=X, pepper=P) != ("WDGC" + gift_card_store.code_hash(X, pepper=P)[:16]).upper()
```

— which pins the **tag**, since without `CODE_DOMAIN_TAG` the two would be equal for this `X` —
or the weaker inequality on the two public return values. The first is the one to write, and the
honest description of it is *"this test fails if the domain tag is removed"*, not *"neither digest
is a substring of the other"*. The property is unchanged and still worth guarding; only the claim
about how it is guarded was wrong.

**No float, proved three ways instead of one.** The first draft monkeypatched `float` to raise
"across the whole conversion path". That does not work and is worth recording so it is not
retried: `json.JSONDecoder.__init__` binds `self.parse_float = parse_float or float` when the
decoder is constructed, and `json.loads` with no arguments uses the module-level
`_default_decoder` built at import, whose C scanner holds that reference. Patching
`builtins.float` afterwards therefore has no effect on `json.loads` — the one place a Wix float
can enter — while risking a mid-test failure in pytest's own machinery that would look like a
defect in the code. Replaced by three checks that each prove something:

1. **Type assertions at the boundaries** — `type(parsed["giftCard"]["initialValue"]["amount"]) is str`
   on the way out, `type(Money.from_wix(amount).paise) is int` on the way back.
2. **An AST gate**: the identifier `float` appears nowhere in
   `lambda_utils/ecommerce/wix_gift_cards.py` or `scripts/demo_coupon_giftcard_sample.py`
   (§4.5 already promised this for the demo; it is extended to the adapter and lives in Group D).
3. **A Wix float is refused, asserted directly**: `with pytest.raises(ValueError): Money.from_wix(10.0)`.
   That holds today — `Money.from_wix` requires `isinstance(amount, str)` matching
   `[0-9]{1,14}(\.[0-9]{1,2})?` (`money.py:21-25`) — so the refusal is a property of the money
   type rather than of a patch.

**Group D — structural guards.**

| Assertion | Why |
|---|---|
| no handler imports `wix_gift_cards` | the adapter must not reach the request path before the §0.1 gate clears. Revision 3 made the direction (A), which makes this guard **more** load-bearing, not less: a settled verdict is exactly when someone wires a module on the strength of the decision rather than the evidence |
| `wix_gift_cards` imports none of `boto3`, `botocore`, `urllib`, `os` | same injected-callable discipline `test_wix_coupons_contract.py` already pins for `wix_coupons`. **The asserted rule is a denylist of the four modules that reach outside the process — it is NOT an allowlist, and must not be implemented as one.** For reference, the module's real import set is `hashlib`, `hmac`, `datetime` and the shared money types: `hashlib`/`hmac` for the §2.5 derivations and `datetime` for the `expiration_iso` parse. None reaches outside anything, so the rule is unaffected. The enumeration is **descriptive**; turning it into an assertion is how a gate goes red on correct code, which this document has had to repair twice |
| `wix_gift_cards` calls none of `get_secret_value`, `batch_get_secret_value`, `client`, `resource` | the structural form of *this module never reads a secret*, copied from `test_gift_card_store.py`'s own gate. The pepper is a required keyword, obtained by the caller — so the module cannot read a secret even by accident, which is what keeps `card_code` compatible with the by-reference rule |
| **no file under `amplify/` references `demo_code`** | AST walk over every `.py` under `amplify/`, asserting the name appears in no `Attribute`, `Name` or `ImportFrom`. `demo_code` is unkeyed and therefore recoverable from a log line; the guard is what makes "demo only" a property rather than a docstring. The demo (`scripts/`) and the harness (`tests/`) may reference it, and both do. **Those three node types are the whole specification, and the reason is not obvious:** `wix_gift_cards.py` is *itself* under `amplify/` and **defines** `demo_code`, so the guard passes only because a `def`'s own name is a plain string attribute of an `ast.FunctionDef` and not a `Name` node. A text grep, or a walk that also inspected `FunctionDef.name`, fails immediately on the defining module — and the repair reached for is to exclude that file, which would also exclude the one file most likely to grow a second reference. Walk the three node types; do not special-case the file |
| `card_code`'s `pepper` parameter is keyword-only and has **no default** | asserted from the AST signature: `pepper` in `args.kwonlyargs` and its `kw_defaults` entry is `None`. A defaulted pepper would silently restore the revision-4 defect under a keyed function's name, and that is exactly the edit a future reader makes to "simplify the call site" |
| `wix_gift_cards` source contains no `logger`, `logging`, `print(` | it handles bearer value; it must have nothing to log with |
| the identifier `float` appears in neither `wix_gift_cards.py` nor `scripts/demo_coupon_giftcard_sample.py` | AST walk, not a text grep, so a comment explaining the rule does not fail the gate. Replaces the inert `float` monkeypatch (Group C) |
| `wix_gift_cards` mentions no clear-code variable in a return | the clear code exists in exactly one expression and is reduced to `last4` in the same function |
| `handler._staff`'s source calls `middleware.require_auth` with `STAFF_ROLE` | Group B stubs `_staff`; this is what stops the stub concealing an auth regression. The real enforcement test is `tests/test_route_auth_enforcement.py` and is not duplicated here |
| `wix_ecom._secrets is None`, under `sys.modules["boto3"]` sabotage | §2.2. The `"boto3" not in sys.modules` form is **not** asserted in the suite — it is false in this very module once the handler is imported, and red in CI regardless of the code under test |

### 2.5 `lambda_utils/ecommerce/wix_gift_cards.py` — new, and deliberately unwired

**Decision, with the alternative stated.** Two places this adapter could live:

* **(i) under the task directory as a prototype** — zero risk of accidental production use, but
  the demo would then exercise code that is not the code a future (A) decision would ship, which
  is precisely the kind of "demo passed, product differed" gap this task exists to close;
* **(ii) in `lambda_utils/ecommerce/` as a pure, unwired module** — it is importable by the
  harness and the demo, it is the artifact a future (A) decision wires up in one line, and it
  ships in **no** Lambda package until some handler imports it, because
  `scripts/deploy_all_lambdas.py` packages per-function sources and validates top-level imports.

**Chosen: (ii)**, with the Group D guard asserting no handler imports it.

**Revision 3: the adapter stays unwired, and the guard stays, even though the direction is now
(A).** This is the one place the owner's answer most invites over-rotation — the verdict is
settled, so why not wire it up? Because wiring is a different act with a different gate. The
adapter being correct is what this change demonstrates; the adapter being *in the request path*
needs §0.1 condition 3 (one owner-run live verification) plus a deploy decision, and a deploy is
a standing refusal here. Wiring it now would also mean our gift-card handlers and the Wix-native
adapter are both live against the same cards, which is a worse state than either end point. The
sequence is: demonstrate (this change) → verify live (owner) → wire and retire (a separate
change, §6.4). The guard is what makes that sequence hold rather than being a good intention: the
module cannot reach production by drift, only by
somebody adding an import and deleting a test.

Shape, modelled line-for-line on `wix_coupons.py` so there is one pattern and not two:

```python
BASE = "/gift-cards/v1/gift-cards"          # NOT /ecom/, NOT /stores/
CURRENCY = "INR"
SOURCE_MANUAL = "MANUAL"                    # Wix REQUIRES giftCard.source; §3.3, measured
MAX_IDEMPOTENCY_KEY = 100
MIN_CODE_LENGTH, MAX_CODE_LENGTH = 8, 20
CODE_SUFFIX_LENGTH = 4                      # Wix's own codeSuffix is minLength 4, maxLength 4
MIN_INITIAL_VALUE_PAISE = 1                 # Wix Money permits 0; a gift card worth nothing is a defect
MAX_INITIAL_VALUE_PAISE = 99_999_999_999    # reused from the SPI; see the note below
CODE_DOMAIN_TAG = b"wix-gc-code:"           # domain separation from gift_card_store.code_hash

class WixGiftCardError(RuntimeError):
    """Input this adapter refuses to send, or a Wix answer it refuses to trust.

    Mirrors `wix_coupons.WixCouponError` IN THE DETAIL THAT MATTERS: a stable, enumerable
    `.code` for a caller to branch on, and the message slot left for prose. Measured at
    `32b632e3`, `WixCouponError` is a `RuntimeError` carrying a class-level
    `code = "WIX_MIRROR_FAILED"`, which `WixCouponConflict` overrides with
    `"WIX_CODE_CONFLICT"` - so the reason is a field, never message text.
    """
    code = "WIX_GIFT_CARD_REFUSED"

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code

#: The closed reason set. Named so a caller can branch and a log can group, and so adding
#: one is a deliberate edit rather than a new string literal.
REFUSAL_CODES = frozenset({
    "A_PEPPER_IS_REQUIRED", "CODE_SUFFIX_MISSING", "AMBIGUOUS_CODE",
    "INVALID_AMOUNT", "INVALID_CURRENCY", "INVALID_CODE", "INVALID_SOURCE",
    "INVALID_IDEMPOTENCY_KEY", "INVALID_EXPIRATION", "INVALID_GIFT_CARD_ID",
})

def idempotency_key(*, reference_id: str) -> str:
    """Deterministic in `reference_id` ALONE, so a retry cannot mint a second key.

    No clock, no counter, no `secrets`. A fresh key on retry is how a replay becomes a
    second gift card, which is the one failure this adapter exists to prevent.

    UNKEYED on purpose, and that is safe HERE: an idempotency key is not bearer value. It
    buys nothing for a holder - Wix answers a replayed key with the card that already
    exists, which is the card the reference already identifies. See `card_code` for why the
    same reasoning does NOT transfer to the code.
    """
    digest = hashlib.sha256(reference_id.encode("utf-8")).hexdigest()
    return ("wd-gc-" + digest)[:MAX_IDEMPOTENCY_KEY]

def card_code(*, reference_id: str, pepper: str) -> str:
    """The production derivation. KEYED, because the code IS bearer value.

    `hmac.new(pepper, CODE_DOMAIN_TAG + reference_id, sha256)`, then "WDGC" + 16 hex,
    upper-cased: exactly 20 characters, which is Wix's documented MAXIMUM. The length sits
    at the ceiling deliberately, because the value is bearer value: 16 hex digits is 64 bits
    of margin where 12 would be 48, and Wix permits the extra four characters at no cost.

    The TAG is domain separation, not decoration. `gift_card_store.code_hash` HMACs under the
    SAME `code_pepper` with the SAME construction over a caller-supplied string (`:442-447`),
    and a key used for two purposes is exactly what a tag exists to make safe. With
    `CODE_DOMAIN_TAG` prefixed to the MESSAGE (never to the output), the two derivations
    cannot collide for ANY input, rather than merely not colliding for the inputs they happen
    to receive today. `code_hash` is the untagged legacy construction and stays as it is:
    retagging it would invalidate every partition key already derived from it, and it is on
    the side of the §0.1 gate that gets deleted.

    The pepper is what makes this safe, and the reason is specific to this repository rather
    than general caution. `reference_id` is NOT a secret here - the standing payments rule
    says it "may be logged in full", and it is, deliberately, as the correlation id that
    lets a payment log line be traced with no masked field. So any UNKEYED function of
    `reference_id` is recoverable by anyone who can read a log line, and a gift-card code
    recovered that way is spendable. Keying it means the log discloses nothing the holder of
    the pepper does not already have.

    Determinism is unaffected: the pepper is fixed per environment, so the derivation is
    still stable across retries, which is what resolve-before-create needs.
    """
    if not isinstance(pepper, str) or not pepper:
        raise WixGiftCardError("A_PEPPER_IS_REQUIRED", "a pepper is required to derive a code")
    mac = hmac.new(pepper.encode("utf-8"),
                   CODE_DOMAIN_TAG + reference_id.encode("utf-8"), sha256)
    return ("WDGC" + mac.hexdigest()[:16]).upper()          # 20 chars == MAX_CODE_LENGTH

def demo_code(*, reference_id: str) -> str:
    """DEMO ONLY. UNKEYED, therefore NOT usable for a real gift card.

    Identical in shape AND LENGTH to `card_code` - 20 characters, Wix's maximum - so the
    demo crosses the same length boundary production will, and derived from `reference_id`
    with no key, so the value it returns is recoverable from any log line carrying the
    reference.
    It is NOT a prefix or a substring of `idempotency_key(reference_id)` - the prefixes and
    the casing differ, "WDGC" against "wd-gc-" - and saying that it is, as revision 7 did,
    understates the problem by pointing at the wrong property. The true and dangerous
    property is that BOTH VALUES EXPOSE THE SAME UNKEYED sha256 DIGEST of the same input, so
    either value yields the other: strip the decoration from one and it is a prefix of the
    stripped other. For "wd-gc-sample-2026-10-02" the shared fragment is b4a4841861208fa8.
    That overlap is tolerated HERE, asserted positively by Group C so the weakness is stated
    rather than implied, and fenced off from production by the Group D guard.

    All of that is acceptable only because every code in the offline harness and demo is a
    fixture placeholder (§2.3) and no live Wix response can reach either process.

    Production must call `card_code(reference_id=..., pepper=...)`. A Group D assertion
    fails if any file under `amplify/` references this function.
    """
    return ("WDGC" + hashlib.sha256(reference_id.encode("utf-8")).hexdigest()[:16]).upper()

class WixGiftCards:
    def __init__(self, request): self.request = request
    def create(self, *, initial_value_paise: int, code: str | None,
               idempotency_key: str, source: str = SOURCE_MANUAL,
               currency: str = CURRENCY,
               expiration_iso: str | None = None) -> dict: ...
    def find_by_code(self, code: str) -> dict: ...          # POST /query, $eq on code
    def get(self, gift_card_id: str) -> dict: ...           # GET /{giftCardId}
    def disable(self, gift_card_id: str) -> None: ...       # POST /{giftCardId}/disable
```

**`find_by_code`'s three return branches, stated rather than left to the implementer**, because
`create` branches on the first of them and §2.4 Group C queues a fixture for each:

```
find_by_code(code) -> dict

    MISS      -> {}        An empty `giftCards` list is NOT an error. It is the signal
                           `create` resolves on, so the empty dict is the contract and a
                           `None` or a raise would both make the resolve path a try/except.

    ONE HIT   -> the SAME SEVEN KEYS `create` returns, with `resolved: True`:
                           {giftCardId, codeLast4, balancePaise, currency, resolved,
                            disabled, expirationDate}
                           Enumerated here rather than pointed at, because this is the other
                           public return in the module and it is the function a caller
                           reaches for directly once the adapter is wired. `resolved` DOES
                           belong on a finder: `create`'s resolve branch returns
                           `find_by_code`'s view unchanged, so one normaliser produces both
                           and the branch-independence assertion in §2.4 Group C covers both
                           functions with one row. A finder with six keys and a creator with
                           seven would need two normalisers and two assertions, which is how
                           the five-versus-seven drift the intervening review caught got in.
                           On this branch `resolved` is ALWAYS `True` - a miss returns `{}`
                           and never a dict with `resolved: False`.

    >1 HIT    -> raise WixGiftCardError("AMBIGUOUS_CODE", "the code filter matched N cards")
                           `code` is unique in Wix, so two matches mean the filter was NOT
                           honoured as documented - which is a live possibility here, since
                           §3.4 records two Wix pages disagreeing about this API's operator
                           map. Reading `giftCards[0]` under those conditions is a money read
                           from an arbitrary row, and refusing is the only safe answer. The
                           caller gets a code it can branch on; nothing is created.
```

**Imports: `hashlib`, `hmac`, `from hashlib import sha256`, and `datetime`.** The Group D rule is
intact and unchanged — still no `boto3`, no `botocore`, no `urllib`, no `os` — because that rule
is a **denylist of the four modules that reach outside the process**, and none of these four
reaches outside anything. `gift_card_store.py` already imports the `hmac`/`sha256` pair for
exactly this purpose (`import hmac`, `from hashlib import sha256`), so that half is one pattern
rather than two.

**`datetime` is in the list because the `expiration_iso` rule needs it, and revisions 1-5 said
"the only imports beyond the shared money types" while specifying a rule that breaks that
sentence.** The two available repairs were to drop the parse (replacing it with an ISO-8601 regex,
which needs `re` and so needs the same edit anyway) or to name the real import list. The second is
chosen: the parse is kept, because an unvalidated string going into a money request body is worse
than one more stdlib import, and the alternative's regex would be a weaker check than
`fromisoformat` for no saving. **The enumeration in this paragraph and in §2.4 Group D is
descriptive; the asserted rule is the denylist.** That distinction is written down because an
implementer who turns "the only imports" into an allowlist assertion gets a test that fails on
correct code — which is the identical shape to the two gates this document has already had to
repair.

**The pepper arrives through the mechanism that already exists, and is not a new secret.**
Measured at `32b632e3`, `gift_card_store.py` already owns the whole apparatus:

| Existing thing | Where | What this adapter reuses |
|---|---|---|
| `SecretReader = Callable[[str], Mapping[str, Any]]` | `gift_card_store.py:367` | the injected-reader type |
| `read_pepper(reader, *, secret_id=SECRET_ID)` | `:389` | the lazy, by-reference read |
| `SECRET_ID = "wecare/wix/giftcard-spi"` | `:104` | the secret **name** |
| `PEPPER_FIELD = "code_pepper"` | `:106` | the field **name** |
| `code_hash(code, *, pepper)` = `hmac.new(pepper.encode("utf-8"), normalised.encode("utf-8"), sha256).hexdigest()` | `:442-447` | the HMAC construction, verbatim |

So the rule is: **`wix_gift_cards` never reads a secret.** It takes `pepper` as a required
keyword and the *caller* obtains it, exactly as `ecommerce/gift-cards/handler.py` already does —
`store.read_pepper(_read_secret, secret_id=SPI_SECRET_ID)` at `:142-143`, called lazily per
request with the comment *"A module-scope read is frozen into a warm sandbox, so a pepper
rotation would not take effect"*. That keeps three properties at once: the module stays pure and
import-free (Group D), the secret stays by-reference (`secret-handling.md`), and a rotation takes
effect on the next request rather than on the next sandbox recycle (`lambda-snapstart-deploy.md`).

**The consequence of rotating the pepper, stated so it is a decision rather than a surprise.**
`card_code` is keyed, so rotating `code_pepper` changes the code every `reference_id` derives.
A card already issued keeps its own code — the code is immutable in Wix and the card is found by
`codeSuffix`/`id` thereafter — but a *replay of an old reference after a rotation* derives a
different code, misses on `find_by_code`, and would create a second card if `idempotencyKey`
did not stop it. It does stop it, because `idempotency_key` is **unkeyed** and therefore
rotation-invariant. That asymmetry is deliberate and is the reason the two derivations do not
share a construction: the code must be unguessable, the idempotency key must be stable forever.
It is also the reason they can no longer be a prefix of one another, which was the defeating
property in revision 4 — one is an HMAC under a secret key, the other a bare digest, so neither
discloses the other.

**Input validation — every rule, and the behaviour on violation.** The constants above declared
bounds and specified nothing about breaching them; that is the gap this table closes. Every check
runs **before** any amount is formatted and before any request is composed, so a refusal costs no
HTTP call:

Every refusal names a code from `REFUSAL_CODES`, so a caller branches on `.code` and a log groups
by it. The message slot carries prose and is never the discriminator.

| Input | Rule | On violation |
|---|---|---|
| `initial_value_paise` | `type(initial_value_paise) is not int` → refuse. **Exact type, not `isinstance`**, because `bool` *is* an `int` in Python and `True` would otherwise be an amount of one paise. Then `MIN_INITIAL_VALUE_PAISE <= v <= MAX_INITIAL_VALUE_PAISE`. The value then goes through `Money(...)` before formatting, and **`Money.__post_init__` is the second gate**: read from the tree it enforces `type(self.paise) is int`, `0 <= paise <= 9007199254740991` and `currency != "INR"` in one condition | `WixGiftCardError("INVALID_AMOUNT")` |
| `currency` | `== CURRENCY`, compared **explicitly and first**, never inferred from the amount | `WixGiftCardError("INVALID_CURRENCY")` |
| `code` | `None` (let Wix generate), or a `str` with `MIN_CODE_LENGTH <= len <= MAX_CODE_LENGTH` | `WixGiftCardError("INVALID_CODE")` |
| `source` | `in {SOURCE_MANUAL}`. Wix's enum is `{ORDER, MANUAL}` and the field is **required and immutable** (§3.3). `ORDER` is narrowed out here rather than merely defaulted away: it means *this card was purchased through an order*, which is a provenance claim, and nothing in this adapter creates a card from an order. Widening it is a deliberate edit with a row to change | `WixGiftCardError("INVALID_SOURCE")` |
| `idempotency_key` | `str`, `1 <= len <= MAX_IDEMPOTENCY_KEY` — Wix documents `minLength 1, maxLength 100`, so an empty key is a refusal and not a "no idempotency" fallback | `WixGiftCardError("INVALID_IDEMPOTENCY_KEY")` |
| `expiration_iso` | `None`, or a `str` that `datetime.datetime.fromisoformat` accepts — which is why `datetime` is in the module's import list (above), and the Group D gate stays a **denylist** so naming it costs nothing. Maps to the Wix key **`expirationDate`** (§3.3, measured: `format date-time`, `immutable`, documented example `"2026-11-11T00:00:00Z"`). Not range-checked: a past expiry is Wix's to reject, and guessing its rule would be inventing a contract. Note `fromisoformat` on 3.12 accepts a trailing `Z`, which the documented example carries | `WixGiftCardError("INVALID_EXPIRATION")` |
| `gift_card_id` (`get`, `disable`) | non-empty `str`; no shape assumption beyond that, since `format: GUID` is Wix's to enforce | `WixGiftCardError("INVALID_GIFT_CARD_ID")` |
| `pepper` (`card_code`) | non-empty `str`, keyword-only, **no default**. A defaulted pepper is an unkeyed code wearing a keyed function's name | `WixGiftCardError("A_PEPPER_IS_REQUIRED")` |

**`money.positive_paise` is deliberately NOT the model for the first row, and revision 4 cited a
function that does not exist.** Both halves of that citation were wrong, measured at `32b632e3`:

* there is no `money.value_paise`. `money.py` defines `positive_paise`; `value_paise` lives in
  `gift_card_store.py:543` — a module `wix_gift_cards` must not depend on, since depending on it
  would import the backend this design is working toward retiring;
* `money.positive_paise` does **not** refuse an integral `Decimal`. Read from the tree it
  explicitly converts one: `if isinstance(value, Decimal): ... value = int(value)`. It refuses a
  `bool` first and a non-integral `Decimal`, but `Decimal("250050")` passes and returns `250050`.

That behaviour is right for `positive_paise`, whose callers read DynamoDB numbers that arrive as
`Decimal`. It is wrong **here**, where every amount is composed in-process and a `Decimal`
reaching this boundary means a caller lost track of its own types. So the rule is stated
standalone and the second gate is named by what it actually enforces, rather than by analogy to a
function with different semantics.

`MAX_INITIAL_VALUE_PAISE` deserves its own sentence, because it is borrowed rather than measured:
**§3.3 records no Wix-side maximum** (`Amount.amount` is `maxScale: 2`, `gte: 0` and nothing
more). The SPI ceiling is reused so that legs 2 and 3 of the demo are bounded identically and
therefore comparable, not because Wix is known to stop there. If a real maximum is ever measured,
it belongs in §3.3 and this constant follows it.

**The request body, pinned field by field, because Group A's standard is byte-exact.** Revision 4
left this under-specified in two ways that a whole-body comparison cannot tolerate: `§4.4`'s
transcript sent `"source": "MANUAL"` which was not a parameter of `create()` and had no
validation row, and `expiration_iso` was a parameter whose Wix key was never named. Both are now
measured (§3.3). The body `create` composes is **exactly** this, and nothing else:

```python
{
  "giftCard": {
    "initialValue": {"amount": Money(initial_value_paise).to_wix()},   # "2500.50"
    "currency": currency,                                             # "INR"
    "source": source,                                                 # "MANUAL"
    **({"code": code} if code is not None else {}),
    **({"expirationDate": expiration_iso} if expiration_iso is not None else {}),
  },
  "idempotencyKey": idempotency_key,
}
```

Three properties of that dict are load-bearing rather than stylistic:

* **`source` is required by Wix**, so it is sent on every create and is not optional on our side
  either. Measured: `Required parameters: giftCard, giftCard.initialValue,
  giftCard.initialValue.amount, giftCard.currency, giftCard.source`. Revision 4's §3.3 row ended
  that list with "`...`", which is where the requirement was hiding.
* **The two optional keys are omitted, not sent as `None`.** A `"code": null` is a different
  request from a request with no `code`, and the documented meaning of *omitting* `code` is
  *Wix generates one* — so sending `null` would be asking for an undocumented behaviour at a
  money boundary. The conditional-merge form above is what makes omission the default.
* **No other key is ever added.** `balance`, `codeSuffix`, `formattedAmount`, `createdDate`,
  `id` and `disabledDate` are all `readOnly` in the schema; `orderInfo` and `notificationInfo`
  are writable and are **deliberately not sent** — `orderInfo` would be a false provenance claim
  and `notificationInfo` triggers a Wix-sent email, which needs a premium plan and is a live
  customer send. §2.4 Group C therefore compares the **whole body** against the dict above, the
  way Group A does, and for the same reason: an extra key in a gift-card create is a different
  promise.

**The return value, and the one key that means two different things.** `create` returns
`{"giftCardId", "codeLast4", "balancePaise", "currency", "resolved", "disabled",
"expirationDate"}`:

* on a genuine create, `balancePaise` is the card's **`initialValue`**;
* on a **resolve hit** (`find_by_code` found the card), it is the card's **current balance**,
  which may already be lower.

Same key, two different facts, and it is a money field — so `resolved: bool` is in the dict and
the docstring says which is which. A caller that needs the distinction must read `resolved`; a
caller that treats `balancePaise` as "what I just issued" is wrong on the replay path, which is
precisely the path this adapter is built to make common.

**`disabled` and `expirationDate` are in the dict because a resolve hit can land on a dead card,
and revisions 1-5 returned one indistinguishably from a live one.** `find_by_code` filters on
`code` alone, §3.3 records that the response carries `disabledDate` and `expirationDate`, and
§2.5 wires `disable()` — so a card issued for reference `R`, later disabled, is found by a replay
of `R`. **The resolve hit is still returned, deliberately**: minting a second card for one
reference is the worse failure, and it is the failure this whole adapter exists to prevent. But
the caller has to be able to tell, so:

* `disabled: bool` = `bool(giftCard.get("disabledDate"))` — derived from Wix's own `readOnly`
  timestamp, not from a separate status field, because there is no separate status field;
* `expirationDate: str | None` = the raw Wix value, passed through unparsed. **This adapter makes
  no expiry decision**: comparing a Wix timestamp against our clock is a decision with a timezone
  and a skew in it, and the authority on whether a Wix card is spendable is Wix. The caller gets
  the fact; Wix enforces the rule.

Both keys are read on **both** paths, so `create`'s return shape does not depend on which branch
produced it. A caller that ignores them is in exactly the position revision 5 left every caller
in, which is why they are keys rather than a sentence.

**The seven keys above are the one authoritative enumeration, and §2.4 Group C enforces it on
both branches.** This is stated because revision 6 enumerated the key set twice — here with seven
keys and again, 60 lines later in the clear-code bullet, with the five that predate `disabled` and
`expirationDate` — and nothing tested the key set on the create path, so an implementer following
the stale copy would have shipped five keys on create and seven on resolve with the whole suite
green. The row added to Group C asserts `set(result)` against this list on a create **and** on a
resolve hit; the clear-code bullet now refers to this enumeration rather than repeating it.

**Where those two values come from, measured rather than assumed.** Revision 4 returned
`balancePaise` from the resolve hit and a `codeLast4` with no stated extraction rule, and §3.3
recorded only the *filter* operator map — a statement about filtering, not about the response. So
the response schema was re-fetched (§3.3). Both reads are available on **both** paths:

| Returned key | Create path reads | Resolve path reads | Measured |
|---|---|---|---|
| `giftCardId` | `giftCard.id` | `giftCards[0].id` | `read-only`, `format GUID`, present in both responses |
| `codeLast4` | `giftCard.codeSuffix` | `giftCards[0].codeSuffix` | `read-only`, *"Last 4 characters of the gift card code"*, `minLength 4, maxLength 4`, present in both responses |
| `balancePaise` | `Money.from_wix(giftCard.initialValue.amount)` | `Money.from_wix(giftCards[0].balance.amount)` | `balance` is type `Amount`, `read-only`, *"Current available balance that can be spent"*, present in the **Query** response, and `Amount.amount` is the decimal string |
| `currency` | `giftCard.currency` | `giftCards[0].currency` | `format CURRENCY`, `immutable`, present in both responses |
| `disabled` | `bool(giftCard.get("disabledDate"))` | `bool(giftCards[0].get("disabledDate"))` | `disabledDate` is `read-only`, `format date-time`, absent while the card is active |
| `expirationDate` | `giftCard.get("expirationDate")` | `giftCards[0].get("expirationDate")` | `format date-time`, `immutable`; passed through unparsed, since this adapter makes no expiry decision |

**`giftCards[0]` is only reachable after the list length has been checked.** The resolve path
reads index 0 of a list that `find_by_code` has already proven holds exactly one entry — zero is a
miss and returns `{}`, two or more raises `AMBIGUOUS_CODE` — so no money field is ever read from
an arbitrary row. That ordering is the point of specifying the three branches above rather than
leaving `[0]` to stand on Wix's uniqueness guarantee, which §3.4 shows this document has already
been wrong about once.

Two consequences, and the first replaces a rule this design would otherwise have had to invent:

* **`codeLast4` is Wix's own `codeSuffix`, never a parse of `code`.** The obfuscated `code` is
  documented only through one example, `****-****-****-4444`, which is hyphen-grouped — and our
  codes are 16 unhyphenated characters, so what Wix returns for *our* shape is genuinely
  unmeasured. It does not matter, because nothing needs to parse it: `codeSuffix` is a dedicated
  read-only field carrying exactly the four characters we want, on both responses, and the
  introduction states the obfuscation shows *"only the last 4 characters"*. The rule is therefore
  **read `codeSuffix`; if it is absent or not exactly four characters, refuse with
  `WixGiftCardError("CODE_SUFFIX_MISSING")`** rather than falling back to slicing `code`. A
  fallback that parses bearer value is the one place a rule must not be lenient.
* **The resolve path needs no second request.** An earlier reading of §3.3 suggested
  `find_by_code` might have to be followed by `get(gift_card_id)` to obtain a balance. It does
  not: `balance` is on the Query response. So the replay path is one request, not two, and §2.4
  Group C's call counts stay as written.

Rules it carries, each traceable to a measured fact:

* **`create` resolves before it generates, and does not rely on Wix's key alone.** When a
  deterministic `code` is supplied, `create` first calls `find_by_code`; a hit returns the
  existing card — **including a disabled or expired one**, with `disabled` / `expirationDate`
  saying so — and issues **no** create call. Only a miss, which is the empty dict and not an
  exception, proceeds to `POST`, carrying
  `idempotencyKey` as the server-side backstop for the window between the two calls. Both layers
  are needed and neither is redundant: the query makes a replay observable **to us** (so the demo
  and the harness can assert "one create call, not two" — §2.4 Group C, §4.4 leg 2), while
  `idempotencyKey` is what actually closes the query-then-create TOCTOU race *inside Wix*. This is
  the guarantee coupons cannot have, for the measured absence in §1.3, and it is why the two
  verdicts differ. **Both layers depend on `code` and `idempotency_key` being deterministic in
  their inputs**, which is why the module owns `idempotency_key()`, `card_code()` and
  `demo_code()` above rather than leaving derivation to each caller: a caller that derives a
  fresh key on retry defeats both layers at once, and `create` cannot detect that it happened.
  Determinism survives keying — the pepper is fixed per environment — and the one case where it
  does not, a pepper rotation, is covered by `idempotency_key` being rotation-invariant.
* **Amounts are `Money(paise).to_wix()`** — a decimal string with exactly two places, which is
  what `format: DECIMAL_VALUE, maxScale: 2` documents. `Money.__post_init__` already refuses
  anything that is not non-negative integer paise in INR, so the type gate is reused rather than
  restated. Reading back is `Money.from_wix(...)`, whose regex refuses anything that is not an
  exact decimal string — so a Wix float can never become a balance.
* **Currency is compared explicitly** against `CURRENCY`, never inferred from the amount, and the
  comparison happens before the amount is formatted.
* **No numeric field is read off a response** — and here, unlike coupons, it does not need to be:
  every money field in this API is a string. That asymmetry is recorded in the module docstring
  because it is the single strongest technical argument for the Wix-native gift-card model, and
  it will otherwise be rediscovered.
* **The clear code is reduced to `last4` in the function that receives it**, and `last4` is now
  Wix's `codeSuffix` rather than a slice of the clear code. `create` is the only place a clear
  code exists, and **the clear code is not among the keys enumerated above**. Nothing else in the
  module can see one. (The key set itself is stated once, in *"The return value, and the one key
  that means two different things"*; this bullet deliberately does not restate it, because
  revision 6 stated it twice and the second copy went stale the moment `disabled` and
  `expirationDate` were added.)
* **The derivation of the code is keyed, and that is a control rather than a nicety.** Every rule
  in this bullet list was defeated in revision 4 by one line: the code was an unkeyed digest of
  `reference_id`, and `reference_id` is logged in full by standing policy. Reducing a value to
  `last4`, redacting it at capture and masking it in a renderer are all worthless if the value
  can be recomputed from a log line. `card_code` closes that, and it is the only one of these
  rules whose absence makes the others ineffective, which is why it is stated here as well as in
  the function's docstring.
* `find_by_code` takes the **full** code because Wix documents that as the filter input, and that
  full code therefore appears in a request body travelling to Wix over TLS. **Revision 4 withdrew
  the sentence that said it must not be recorded**, because `WixTransport` records request bodies
  verbatim and therefore does record it — the document asserted a rule its own stub broke. The
  accurate statement is §2.3's: every code that exists offline is a fixture placeholder, so
  recording one discloses nothing, and the renderer's masking (§4.3) is a habit for real data
  rather than the thing protecting a secret. What the **module** guarantees is narrower and does
  hold: the clear code is never *returned to a caller* and the module has nothing to log with
  (Group D pins both). If this adapter is ever wired to a live Wix response, the transcript rule
  has to be re-derived against a real code, and that is a line item in §6.4's wiring change, not
  an assumption inherited from here.
* No `delete`. Wix has no delete on this API, and `disable` is the documented terminal state —
  the same reasoning `wix_coupons.py` records for not wiring `Delete A Coupon`.

### 2.6 `tests/coupon_fake_dynamo.py` — three additions

Owned by this workstream per the prior plan. All three are required by §5.

1. **A lock, and it is not an implementation detail.** `FakeTable` today evaluates a condition
   and then mutates `self.rows` in separate statements (`update_item` lines 285-290), and CPython
   releases the GIL at bytecode boundaries on a switch interval (`sys.setswitchinterval`, 5 ms by
   default). A method body is therefore freely interruptible, so two threads can both pass
   `attribute_not_exists(#applied)`, or both pass `settled = :false`, and both apply. That cuts
   both ways and both are bad: the new concurrency test could **fail against correct production
   code**, and the pre-fix "2 balance moves" result could appear for a reason that is the fake
   rather than the module. The first draft asserted the opposite ("atomic under the GIL") and was
   wrong.

   ```python
   def __init__(self, key_attr: str = "couponKey", indexes=None,
                name: str = "stack-wecare-digital-FakeTable") -> None:
       self.name = name                 # addition 3; stated here because __init__ had no name
       self._lock = threading.RLock()   # one DynamoDB request = one indivisible evaluate+apply
   ```

   Held for the **entire body** of `put_item`, `get_item`, `update_item`, `delete_item`, `query`
   and `transact_write_items`, condition evaluation included. `RLock` so a transaction built on
   top of the single-item helpers cannot deadlock on itself. **The lock is the thing that models
   DynamoDB's per-item and per-transaction atomicity**, which is what licenses §5.4's claim that
   the interleaving happens between calls, where the real database's is. §5.4's barrier must
   therefore wait **outside** the lock — see the rule stated there, and note that the rule applies
   to **subclass overrides too**, which is where every latch in this suite actually lives:
   `_MarkerWriteFails` and `_CreditThrottles` both override `update_item` and call
   `super().update_item(**kwargs)`. With an `RLock` (not a `Lock`) that re-entry is safe; a
   barrier awaited inside the override while the lock is held would not be. **Both of those
   examples override one method, and §5.4's `_InterleaveAtBalanceMove` must override two** —
   `update_item` *and* `transact_write_items`, since the balance move changes representation
   across the fix — so the await-then-delegate rule has to hold in each of them independently.
   §5.4 states that requirement where the subclass is specified.

   **`applied`, alongside `calls`, and the distinction is the whole point of §5.4.** `calls`
   today is appended **before** the condition is evaluated — read from the tree, `update_item`
   appends at `:275`, the arm-check is at `:280`, and `ConditionExpression` is not evaluated until
   `:285`, raising `FakeClientError` at `:286`. So `calls` is an **attempt** log, and the existing
   suite depends on exactly that meaning (`test_gift_card_store.py:282-286` counts
   balance-moving `update_item` **calls**). It
   does not change. A second list is added:

   ```python
   self.applied: List[Tuple[str, Dict[str, Any]]] = []   # appended only after EVERY condition passed
   ```

   appended inside the locked body, after the last condition has passed and the mutation is
   committed, in `put_item`, `update_item`, `delete_item` and `transact_write_items`. One log says
   *what was tried*, the other says *what landed*. §5.4 asserts both numbers, and without the
   second one its central assertion is unwritable — see finding 1 in §13.

2. **`transact_write_items(TransactItems=[...])`, in the real API shape.** `transact_write_items`
   is a **low-level client** operation: it takes AttributeValue-typed maps, so the fake receives
   `{"Key": {"giftCardKey": {"S": "GIFTCARD#..."}}, "ExpressionAttributeValues": {":neg": {"N": "-150000"}}}`
   and not native values. Both existing transaction call sites in this repo marshal explicitly
   with `TypeSerializer` (`ecommerce/initiation.py:10,79-82`; `notifications/store.py:239`), and
   §5.3 emits **the same wire shape** from its own `_marshal` — hand-written there because
   `gift_card_store.py` may not import `boto3` at all (§5.3) — so the fake must deserialize before
   it can evaluate anything:

   * `from boto3.dynamodb.types import TypeDeserializer` — the faithful inverse of the shape
     production emits, and the direction the gate does not constrain, because this file is in
     `tests/`, where `botocore` is already a dependency. A hand-rolled unmarshaller here would be
     one more thing that can diverge from boto3, and the fake is the side that should be the
     reference rather than the side that is pinned;
   * `{"N": ...}` deserializes to `Decimal`. The fake converts to `int` and **raises** on a
     non-integral value, because production can never produce one — `_marshal` emits `str(int)`
     and refuses anything that is not exactly an `int`, and the `TypeSerializer` it is pinned
     against refuses a `float` outright with `TypeError: Float types are not supported` — so a
     fractional `N` means the test built the item by hand and the fake should say so;
   * it evaluates every item's `ConditionExpression` against current state **first** and applies
     all updates only if every condition holds. On any failure it raises
     `FakeClientError("TransactionCanceledException")` carrying a `CancellationReasons` list whose
     entries are `{"Code": "ConditionalCheckFailed"}` for the items that failed and
     `{"Code": "None"}` for those that did not — the shape §5.3's branch reads — and mutates
     nothing. **`FakeClientError` cannot carry that list as currently constructed**, so its
     signature changes too; read from the tree it takes only a code and builds
     `{"Error": {"Code": code, "Message": code}}`:

     ```python
     def __init__(self, code: str, *, cancellation_reasons: Optional[list] = None) -> None:
         response = {"Error": {"Code": code, "Message": code}}
         if cancellation_reasons is not None:
             response["CancellationReasons"] = cancellation_reasons   # TOP level, per botocore
         super().__init__(response, "FakeOperation")
     ```

     The keyword is optional and defaulted, so every existing `FakeClientError("...")` call site
     is unaffected. `CancellationReasons` sits at the **top level of the response**, a sibling of
     `"Error"` — that placement is the one §5.3's reader must match, and getting it wrong yields
     a silent `[]`;
   * it supports exactly the one item shape §5 uses (`Update` with `ConditionExpression`) and
     **refuses anything else with `UnsupportedFakeOperation(BaseException)`**, not an
     `AssertionError`. Finding 1's reasoning applies here too, and measured in this module rather
     than assumed: the balance move is wrapped in `except Exception` →
     `GiftCardStoreUnavailable` (`gift_card_store.py:1321-1333`, and the same shape at eleven
     other sites), so an `AssertionError` from the fake would surface as a transient-outage error
     and the test author would go looking for a throttle that never happened. A `BaseException`
     reaches the test with the real reason. Only the new transaction path changes; the existing
     fake's `AssertionError`s stay as they are, because other tests drive paths that do not wrap
     them;
   * `arm_failure("transact_write_items", ...)` additionally accepts a cancellation whose reason
     is **`TransactionConflict`**, so §5.3's bounded-retry branch is covered by a test rather than
     asserted in prose.

3. **`.name` and `.meta.client`** — `.name` returns the logical table name, taken from the new
   `name` keyword in addition 1 and defaulting to `"stack-wecare-digital-FakeTable"`; `.meta.client`
   returns the fake itself. This is what lets production code use only the **real** boto3 shape
   (`table.meta.client.transact_write_items(...)` with `TableName=table.name`) with no
   fake-shaped branch in the store. The adaptation belongs in the fake. The default is a
   placeholder, not a claim about the live table: nothing asserts a particular name, and the
   transaction's `TableName` is asserted to be *present and equal to `table.name`*, not to equal
   a literal.

`calls` records `("transact_write_items", {...})` with the item list **as received**, so ordering
stays assertable, the existing `operations()` helper keeps working, and §5.3's integer-paise
assertion can be made on the wire form: every `"N"` in a recorded transaction must match
`^-?[0-9]+$`. `applied` records the same tuple only when the transaction committed. **Stated once
so no reader has to infer it: `calls` is the attempt log and `applied` is the outcome log**, and
the existing suite's attempt-counting assertions keep their current meaning untouched.

---

## 3. Verifying the Wix contract against current public docs — results

Fetched **2026-10-02** from `dev.wix.com`, and **re-fetched later the same day from a different
location**, because the first set of URLs stopped resolving mid-task. §3.0.1 records what moved
and why it matters more than a broken link usually would. The current source is the
documentation's own **markdown rendition** — append `.md` to any `/docs/` URL — which serves the
schema as text with required-parameter lists, validations and operator maps inline. Extraction is
a `grep`, and no unescaping step is needed.

**One representative command per load-bearing fact is inlined in §3.0.1**, so every Wix claim in
this document is checkable at review time rather than only through an artifact.

**The transcript does not exist yet, and writing it is a prerequisite rather than a by-product.**
`docs/execution/wix-contract-verification-20261002.md` (§8) is absent from the worktree, so until
it is written the tables in §3.1-§3.4 are a *report* of measurements whose record is unpublished.
That matters more here than it usually would: the entire (B)/(C)→(A) reasoning rests on a handful
of fetches, and the inlined commands are the only checkable residue. So:

> **Implementation step 0: write the transcript before any code.** It must contain, per fetch,
> the URL **in the form that was used**, the HTTP status, the page byte size, and the **extracted
> schema fragment** — not a summary — for each load-bearing fact. The four that carry a verdict
> are mandatory and are named as V1-V4 in §3.0. An absence is recorded as the command, its empty
> output and its exit status, because "nothing was found" is only evidence if the search is
> visible — and, after §3.0.1, only if the page was actually fetched: a 404 shell also produces
> an empty search.

### 3.0 The re-fetch rule has two halves, and one of them is a HALT

Revisions 1-4 carried one rule: *"if a re-fetch at implementation time disagrees with a row below,
the artifact wins and the row is corrected."* That is right for a dated count and **wrong for the
four facts this section labels mandatory**, because those four *are* the verdicts. Correcting the
row would silently invert §1.2.2 or §1.3.1 while the adapter's resolve-before-create guarantee,
the §0.1 retirement gate and the owner memo carried on asserting the old verdict. §1.3 has the
right shape for coupons — a named revisit trigger — and the gift-card side had no equivalent.

| Row class | On disagreement |
|---|---|
| **Non-verdict** — a length, a path, a format, an example, an operator list that no decision turns on | **corrected in place; the artifact wins.** It is a dated reading, per `00-current-owner-overrides.md` |
| **The four verdict-carrying facts** (below) | **HALT.** Implementation stops, §1's verdict for the affected feature is re-run from the new evidence, and only then is code written. **A row edit is not a sufficient response to a verdict changing** — the memo (§6.1), the §0.1 gate and §2.5's guarantee all have to move with it |

The four, named so there is no argument about which class a row is in:

| # | Fact | Carries |
|---|---|---|
| V1 | `idempotencyKey` is **absent** from `CreateCouponRequest` | coupon verdict (B) |
| V2 | `Query Coupons`' `filter` is typed **`string`** | coupon verdict (B) — and see §3.4, where the *second half* of this row, "with no operator map", did **not** survive re-measurement |
| V3 | `idempotencyKey` is **present** on `CreateGiftCardRequest` | gift-card verdict (A) |
| V4 | the `code` operator map is **present** on `Query Gift Cards` | gift-card verdict (A), and §2.5's resolve-before-create |

**The rule was exercised on the day it was written, and §3.4 records the result.** All four facts
were re-measured on 2026-10-02 against the documentation's new location, and all four hold — so
no halt was triggered. But one *clause* of V2 was contradicted, which is close enough to the line
to be worth writing down rather than quietly fixing: the coupon API does publish a per-field
operator map, in a sibling article the earlier fetches never reached. §1.3.1 re-runs the coupon
verdict against that, rather than editing the row underneath it.

### 3.0.1 The commands below are the ones that work TODAY, and the previous four do not

Revisions 1-4 inlined four `curl` commands against `dev.wix.com/docs/api-reference/ecom/...` and
reported HTTP 200 with an embedded JSON schema blob. **Re-run 2026-10-02, all four return 404**,
and the ~4 MB body they return is the documentation site's JavaScript shell with no schema in it
at all — `grep -c idempotencyKey` over the unescaped body is **0** for the gift-card create page,
which under the old command set would have read as *the idempotency key is absent* and inverted
verdict (A). That is the sharpest possible argument for finding 7's halt rule: the old commands
did not merely stop working, they would have failed **toward a wrong verdict**.

The documentation has moved to `/docs/api-reference/business-solutions/...` and now serves a
**markdown rendition** of any page when `.md` is appended — stated by the pages themselves, which
open with *"Append `.md` to any URL under `https://dev.wix.com/docs/` to get its markdown
version."* That form is a far better evidence source than the old blob: it is the schema as text,
with required-parameter lists, validations and operator maps rendered inline, so an extraction is
a `grep` rather than an unescape-and-hope.

```bash
GC=https://dev.wix.com/docs/api-reference/business-solutions/gift-cards/gift-cards
CP=https://dev.wix.com/docs/api-reference/business-solutions/coupons/coupons

# (1) V1 — Coupons create. The ZERO COUNT *IS* the finding behind verdict (B).
curl -sSL "$CP/create-a-coupon.md" | grep -c idempotencyKey     # expect 0

# (2) V2 — Coupons query. The filter's TYPE. Expect string, not object.
curl -sSL "$CP/query-coupons.md" | grep -o 'name: filter | type: [a-z]*'

# (2b) and the clause that did NOT survive: the coupon operator map exists, elsewhere.
curl -sSL "$CP/filter-and-sort.md" | grep 'specification.code'

# (3) V3 — Gift cards create. Expect idempotencyKey PRESENT, with its bounds.
curl -sSL "$GC/create-gift-card.md" | grep -o 'name: idempotencyKey.*maxLength 100'

# (4) V4 — Gift cards query. Expect the operator map that makes read-by-code documented.
curl -sSL "$GC/query-gift-cards.md" | grep -o 'field: code | operators: [^|]*'

# (5) the two reads §2.5 returns from a resolve hit, which were unmeasured until revision 5.
curl -sSL "$GC/query-gift-cards.md" | grep -o 'name: \(balance\|currency\|codeSuffix\) |[^|]*'

# (6) the required-parameter list, which is where `source` was hiding behind an ellipsis.
curl -sSL "$GC/create-gift-card.md" | grep -o 'Required parameters:.*'
```

Commands (1) and (2) are the **absences** that verdict (B) rests on, so they are written to make
the absence the visible result — a count of `0`, not an unremarked silence. **One limitation of
the markdown rendition, stated because an absence in it is otherwise over-read:** it renders no
`Errors` section for **any** method, measured across all five pages fetched. So the `errors: []`
claim for `Create Coupon` and the `SITE_IS_NOT_PREMIUM` error name for `Create Gift Card` are
**not re-verifiable from this source** — they are neither confirmed nor contradicted. §3.1 and
§3.3 now say that in those words instead of carrying them as measured.

**The transcript (§8) must therefore record the URL form it used**, since the old one is dead and
a future reader re-running a 404 would draw exactly the wrong conclusion.

### 3.1 Coupons V2 — one row corrected, one downgraded, the verdict fact confirmed

*(Titled "no drift" in revisions 1-4. It is no longer true and the heading is corrected rather
than kept, because a reader scanning headings is the reader most likely to act on a stale one.)*

| Claim in our code | Live schema, 2026-10-02 | Verdict |
|---|---|---|
| `BASE = "/stores/v2/coupons"` | `URL: https://www.wixapis.com/stores/v2/coupons` / `Method: POST` (`create-a-coupon.md:50-51`) | **confirmed** |
| `moneyOffAmount` is a JSON number | `name: moneyOffAmount \| type: number` | **confirmed** |
| `percentOffRate` is a JSON number | `name: percentOffRate \| type: number` | **confirmed** |
| `fixedPriceAmount` is a JSON number | `name: fixedPriceAmount \| type: number` | **confirmed** |
| `minimumSubtotal` is a JSON number | `name: minimumSubtotal \| type: number \| … \| validation: format double` (`:60`) | **confirmed** |
| `startTime` / `expirationTime` are **strings** | `name: startTime \| type: string \| … \| validation: minimum 1000000000000, format int64` and the same for `expirationTime` (`:70-71`) | **confirmed** |
| `MAX_CODE_LENGTH = 20` | *"Must be unique for all coupons on your site. Max: 20 characters"* | **confirmed** |
| `usageLimit` / `limitPerCustomer` are int32 | `name: usageLimit \| type: integer \| … \| validation: format int32` and the same for `limitPerCustomer` (`:72-73`) | **confirmed** |
| the create permission (revisions 1-4 quoted it as `permissionsInfo: [{"name":"COUPONS.MANAGE",…}]`) | `## Permission Scopes:` / `Manage Coupons: SCOPE.DC-COUPONS.MANAGE-COUPONS` (`:17-18`). **The `permissionsInfo` and `COUPONS.MANAGE` spellings are legacy, from the pre-404 blob, and return zero matches in the `.md` rendition** — the requirement is re-confirmed in the rendition's own form, see also the dedicated row below | **confirmed, re-quoted** |
| `type` is read-only | marked read-only, derived from the discount field | **confirmed** |
| PATCH is patch semantics | `Update A Coupon` is `PATCH /stores/v2/coupons/{id}` | **confirmed** |
| no idempotency key (**V1**) | **absent** — `grep -c idempotencyKey` over `create-a-coupon.md` returns **0** | **confirmed as absent, re-measured 2026-10-02** |
| `Query Coupons`' `filter` is typed `string` (**V2**, first clause) | `name: filter \| type: string \| description: Filter string (e.g., when {"expired":"true"}, expired coupons will be returned).` | **confirmed** |
| ~~`Query Coupons` publishes no per-field operator map, so `code` is not a documented filter~~ (**V2**, second clause) | **CONTRADICTED.** A sibling article, `coupons/coupons/filter-and-sort.md`, publishes a per-field operator table that includes `specification.code` with `$eq,$ne,$hasSome,$contains,$startsWith` and "Sorting Allowed" | **corrected — see §3.4 and the re-run verdict in §1.3.1** |
| `CreateCouponResponse` | `- name: id \| type: string \| description: GUID of the newly created coupon.` — the id only | **confirmed** |
| permission scope on create | `Manage Coupons: SCOPE.DC-COUPONS.MANAGE-COUPONS` | **confirmed**, and this is the exact scope string open question 2 needs |
| ~~documented errors are `errors: []`~~ | **not re-verifiable from this source.** The markdown rendition renders no `Errors` section for **any** method (measured across five pages), so the absence of errors here is a property of the rendition and not evidence about the API | **unverified — neither confirmed nor contradicted** |

**Every cell above is now quoted in the markdown rendition's own syntax, re-measured 2026-10-02.**
Revisions 1-5 left five wordings in this table that the rendition cannot produce — `$ref
DoubleValue`, `$ref Int64Value`, `$ref Int32Value`, `permissionsInfo: [{…}]` and
`destinationPath` — all of them artefacts of the pre-404 JSON blob. Re-measured against
`create-a-coupon.md` (HTTP 200, 24,306 bytes): `DoubleValue`, `Int64Value`, `Int32Value`,
`permissionsInfo` and `destinationPath` each return **0** matches, while every underlying **fact**
holds in the rendition's own form (the `type:`/`validation:` lines quoted above, `1000000000000`
present, `format double`/`int32`/`int64` present, the endpoint line present, the scope string
present). No fact changed and no verdict moved — this is a provenance repair in the one section
whose entire value is provenance, and it is the same treatment §3.3 already gave the premium-plan
claim. §3.0's halt rule did not fire, because none of the five is a V1-V4 row.

**Findings: one row corrected, one row downgraded to unverified, five rows re-quoted from the
live rendition, V1 and V2's first clause confirmed.** This is no longer "0 drift", and saying so matters: the two previous revisions
reported a clean re-measurement against URLs that **now 404**, and one of the two absences they
reported was partly an artefact of not having reached the article that contradicts it. The
load-bearing absence — V1, no idempotency key — is confirmed directly and is what verdict (B)
actually rests on. §1.3.1 re-runs the verdict with the corrected evidence rather than leaving the
conclusion resting on a withdrawn row.

### 3.2 Gift Cards service plugin (SPI) — no drift

| Claim in `gift_card_store.py` / the SPI handler | Live schema | Verdict |
|---|---|---|
| paths `v1/balance`, `v1/redeem`, `v1/void` | `"/v1/balance"`, `"/v1/redeem"`, `"/v1/void"` on all three pages | **confirmed** |
| base URI is app-configured | `GiftCardProviderConfig` has exactly one property, `deploymentUri`; documented example `{"deploymentUri": "https://my-gift-cards.com/"}` | **confirmed** |
| `code` is `8..20` | `"minLength":8,"maxLength":20` | **confirmed** |
| `transactionId` is `1..100` | `"minLength":1,"maxLength":100` | **confirmed** |
| `MAX_VALUE_PAISE = 99_999_999_999` | `balance`, `remainingBalance`, `amount` all `"maximum":999999999.99` | **confirmed** |
| amounts are JSON **numbers** | `"type":"number"` | **confirmed** |
| nine errors, names and codes | `GiftCardNotFound/GIFT_CARD_NOT_FOUND`, `GiftCardDisabled/GIFT_CARD_DISABLED`, `GiftCardExpired/GIFT_CARD_EXPIRED`, `MissingCurrency/MISSING_CURRENCY`, `InsufficientFunds/INSUFFICIENT_FUNDS`, `AlreadyRedeemed/ALREADY_REDEEMED`, `CurrencyNotSupported/CURRENCY_NOT_SUPPORTED`, `TransactionNotFound/TRANSACTION_NOT_FOUND`, `AlreadyVoided/ALREADY_VOIDED` | **confirmed, all nine** |
| HTTP codes 404/428/428/428/428/409/400/404/409 | identical, and identical across all three methods | **confirmed** |
| outer class is `...WixError`, `spiErrorData.name` is the bare name | `"name":"GiftCardNotFoundWixError"`, `"spiErrorData":{"name":"GiftCardNotFound",...}` | **confirmed** |

**Findings: 0 drift.** `SPI_ERRORS` in `gift_card_store.py` is byte-correct against the live
schema, including the `AlreadyVoided` vs `AlreadyVoidedWixError` distinction its comment warns
about.

### 3.3 Gift Cards app API (B1) — the Wix-native candidate, newly measured

Not previously transcribed at this depth. Everything in §1.2's table is the result, plus:

| Field | Live schema | Design consequence |
|---|---|---|
| `CreateGiftCardRequest.required` | **the full list, no ellipsis:** `giftCard, giftCard.initialValue, giftCard.initialValue.amount, giftCard.currency, giftCard.source` | `code` and `expirationDate` are **optional** → auto-generation is Wix's default and a custom code is our choice. **`source` is REQUIRED**, which earlier revisions hid behind a "`...`"; §2.5 now has it as a validated parameter |
| `giftCard.source` | `type: Source`, `required: true`, `immutable`, `enum: {ORDER, MANUAL}` — *"How the gift card was created"*; `MANUAL` is *"created manually via API"* | §4.4's `"source": "MANUAL"` was right and was under-specified, not wrong. §2.5 narrows the adapter to `MANUAL` and says why `ORDER` is excluded |
| `giftCard.expirationDate` | `type: string`, `format date-time`, `immutable`; documented example `"2026-11-11T00:00:00Z"` | **this is the Wix key `expiration_iso` maps to.** Earlier revisions carried the parameter and never named the key, which a byte-exact body comparison cannot tolerate |
| `giftCard.currency` | `required: true`, `immutable`, `format: CURRENCY` | one currency per card, fixed at creation — matches our INR-only posture |
| `giftCard.balance` | `type: Amount`, `read-only: true`, *"Current available balance that can be spent. Decreases when the gift card is used for purchases and increases with refunds."* | **Wix owns the arithmetic.** Under (A) we could not move a balance even if we wanted to |
| `Amount` | `amount: string, format DECIMAL_VALUE, decimalValue {"gte":"0","maxScale":2}`; plus `formattedAmount: string, read-only, maxLength 20`, e.g. `"$10.50"` | a decimal string, never a JSON number. **`formattedAmount` is never read** — it is a localised display string and parsing money out of it would be inventing a contract |
| `giftCard.id` | `read-only`, `format: GUID` | the stable handle; `code` is bearer value and `id` is not |
| **`giftCard.codeSuffix`** | `read-only: true`, *"Last 4 characters of the gift card code for search and identification purposes"*, `minLength 4, maxLength 4` | **this is where `codeLast4` comes from.** Present on the create response **and** the query response, so no path has to parse the obfuscated `code`. Corroborated by the API introduction: the obfuscation shows *"only the last 4 characters"* |
| `QueryGiftCardsResponse.giftCards[]` | the full `GiftCard`, including `balance`, `currency`, `codeSuffix`, `initialValue`, `expirationDate`, `source`, `createdDate`, `updatedDate`, `disabledDate` | **the resolve-hit path needs one request, not two.** `balance.amount` and `currency` are on the Query response, which earlier revisions had never measured — §3.3 recorded only the filter map, which is a statement about filtering |
| `Query Gift Cards` `query.filter` | `type: object` | **unlike the coupon query's free-form `string`.** So the gift-card filter is real structured JSON, which is why §2.4 Group C can assert `{"code": {"$eq": ...}}` as a nested object |
| `Query Gift Cards` operator map (**V4**) | inline on the method page: `field: code \| operators: $eq, $ne, $in, $exists, $gt, $gte, $lt, $lte, $startsWith`, `codeSuffix` likewise, `balance \| operators: $exists` | read-by-code is documented. **Confirmed, re-measured 2026-10-02** |
| the same map in the dedicated article | `supported-filters-and-sorting.md` gives `balance` as `$eq, $ne, $exists, $in` and Sortable — **not** `$exists` alone | **two Wix pages disagree about `balance`.** Recorded rather than resolved. The design's rule is unaffected and is kept as the conservative reading: **no balance decision is ever made from a query**, because an eventually-consistent filtered read of a money field is the wrong primitive whichever operators exist. Nothing in this change filters on `balance` |
| `CreateGiftCardRequest.idempotencyKey` (**V3**) | `minLength 1, maxLength 100`, *"Unique identifier to prevent duplicate gift card creation. Use this to safely retry gift card creation requests."* | **confirmed present, re-measured 2026-10-02** |
| permission scope | `Manage eCommerce - all permissions: SCOPE.DC-ECOM-MEGA.MANAGE-ECOM` on both create and query | open question 2's gift-card half has an answer, and it is a **broad** scope rather than a gift-card-specific one. Worth the owner knowing before granting it |
| `GIFT_CARD_PRODUCT_ALREADY_EXISTS` / "max 1 gift card product" | the introduction scopes this to the *storefront* **gift card product**, *"managed by a separate API"*, and offers the alternative explicitly: *"create individual gift cards directly with this API and hand them to specific people instead of selling them in your store"* | **the one-product limit does not constrain this design.** §1.2.1 quoted the bullet without that scoping, which reads as a cap on cards. It is a cap on products, and we create none |
| ~~`SITE_IS_NOT_PREMIUM` is in the method's documented error set~~ | **not re-verifiable from this source** — the markdown rendition renders no `Errors` section for any method. The premium requirement **is** documented, as prose in the introduction: *"Email delivery features require a premium site plan"* | downgraded from "a documented, machine-observable error" to "a documented prose prerequisite". It still bears only on Wix-sent card **emails**, which this design does not use — §2.5 sends no `notificationInfo` |

**Finding, MEDIUM, no fix required today:** `giftCard.balance` being `readOnly` means the (A)
architecture has a property our current one does not — we could not corrupt a balance by writing
to it. It is recorded in the memo (§6.1) as an argument *for* (A), since it is the strongest one
and it is not obvious from the owner's framing.

**Finding, LOW:** `Amount.amount` is `maxScale: 2` and `gte: 0`. `Money.to_wix()` emits
`f"{paise // 100}.{paise % 100:02d}"` — always exactly two places, always non-negative by
`Money.__post_init__`. Compatible with no change. Recorded because `maxScale` is a *maximum*, and
a future "tidy" that emitted `"100"` instead of `"100.00"` would still be valid, so the format
must not be asserted anywhere as the *only* acceptable encoding. Confirmed by Wix's own example,
which gives both `"10.50"` and `"100"` as valid encodings of the same field.

### 3.4 The coupon operator map DOES exist, and the halt rule was exercised on itself

Measured 2026-10-02 at
`api-reference/business-solutions/coupons/coupons/filter-and-sort.md` (HTTP 200), a page none of
the earlier fetches reached because it is not the `Query Coupons` method page:

| Field | Documented operators | Sortable |
|---|---|---|
| `id` | `$eq,$ne,$hasSome,$contains,$startsWith` | yes |
| `dateCreated` | `$eq,$ne,$hasSome,$lt,$lte,$gt,$gte` | yes |
| `expired` | `$eq,$ne` | no |
| `specification.active` | `$eq,$ne` | no |
| `specification.name` | `$eq,$ne,$hasSome,$contains,$startsWith` | yes |
| **`specification.code`** | **`$eq,$ne,$hasSome,$contains,$startsWith`** | **yes** |
| `specification.usageLimit` | `$eq,$ne,$hasSome,$contains,$startsWith` | yes |
| `specification.limitedToOneItem` | `$eq,$ne` | no |
| `scope.namespace` / `scope.group.name` / `scope.group.entityId` | `$eq,$ne,$hasSome,$contains,$startsWith` | yes |

So the claim this document carried from revision 1 — *"unlike `Query Gift Cards`, it publishes no
per-field operator map, so `code` is not a documented filter"* — is **false**. It publishes one,
in a sibling article, and `code` is in it.

**This is a verdict-carrying clause, so §3.0's halt rule applies and §1.3.1 re-runs the verdict
rather than this row being quietly edited.** The outcome is that **(B) stands** and the *stated
reason* for it narrows; the reasoning is in §1.3.1 and is not duplicated here.

Three details that matter to anyone acting on the new row, because the obvious reading of it is
slightly wrong in each case:

* **The field is `specification.code`, not `code`.** §1.3.1 and §6.6 previously proposed an
  owner-run query with the filter `{"code":"WDSAMPLE10"}`, which does not name a documented
  field and would most likely match nothing. Both are corrected to `specification.code`.
* **The filter is still a `string`** (V2's first clause, confirmed) — a JSON document carried
  *inside* a string, as Wix's own example shows for `sort`:
  `"sort": "[{\"dateCreated\": \"asc\"}]"`. So the request is
  `{"query": {"filter": "{\"specification.code\": \"WDSAMPLE10\"}"}}`, double-encoded. That is a
  different serialisation from the gift-card query's real JSON object, and `wix_ecom._request`'s
  bare `json.dumps` will happily produce either, so the distinction has to be in the adapter.
* **The operator vocabulary is the older family** — `$hasSome`, `$contains` — not the
  `$in`/`$exists` set the gift-card API publishes. They are different query languages on two
  Wix APIs of different vintages, which is itself a reason not to generalise one API's behaviour
  from the other.

---

## 4. `scripts/demo_coupon_giftcard_sample.py` — the runnable demonstration

### 4.1 What it is for, given the verdicts

The owner's question is architectural, so the demo answers it architecturally. It runs **three
legs** and labels each with its status, so the transcript itself is the comparison:

| Leg | Status shown | What it demonstrates |
|---|---|---|
| **1. Coupon** | `VERIFIED — this is how it works today` | driven through `coupons/handler._create`, the production owner of the composition: our claim row, then the exact Wix `POST /stores/v2/coupons` payload, Wix's response, the mirror flip, and an eligibility verdict. Wix does the arithmetic; the demo prints no **computed** discount. The figure it does print is the coupon's own `moneyOffAmount` as we issued it — a definition we authored, not a result of applying it to a cart. Nothing in the transcript is the output of a discount calculation, and `evaluate` returns `ELIGIBLE`, a verdict from a closed vocabulary, never an amount. |
| **2. Gift card, Wix-native (B1)** | `CHOSEN DIRECTION — contract under verification` | the exact `POST /gift-cards/v1/gift-cards` payload with `idempotencyKey`, the obfuscated-code response, a resolve-before-create replay converging on one card, a Wix-side balance read-back in integer paise. **No store of ours in this leg.** |
| **3. Gift card, ours (SPI model)** | `INCUMBENT — retirement pending the §0.1 gate` | `gift_card_store` issue → balance → redeem → balance, all integer paise, code masked throughout. |

Legs 2 and 3 issue a card of the same value and redeem the same amount, so the two transcripts
are directly comparable and the owner can see what retirement would actually remove.

**Revision 3 changed the labels and not the legs.** Leg 2 is no longer a candidate being weighed
against leg 3 — it is the chosen direction, and the transcript is now a *before and after* rather
than a choice being offered. Leg 3 stays in the demo precisely **because** retirement is pending:
it is the evidence of what is being replaced, and it is also the thing the demo's leg-2 assertions
are compared against. When the §0.1 gate clears and leg 3's subject is deleted, leg 3 goes with
it and the demo becomes two legs. Deleting it earlier would remove the comparison that justifies
the retirement.

### 4.2 Interface

```
python scripts/demo_coupon_giftcard_sample.py [options]

  --help                    argparse, lists everything below
  --leg {coupon,wix-giftcard,our-giftcard,all}   default: all
  --json                    machine-readable transcript on stdout, nothing else
  --no-colour               plain ASCII (also implied when stdout is not a tty)
  --value-paise N           gift-card face value, default 250050 (INR 2,500.50)
  --redeem-paise N          redemption amount, default 150075 (INR 1,500.75)
  --coupon-money-off-paise N  coupon money-off, default 12345600 (INR 123,456.00)
  --coupon-code CODE        default WDSAMPLE10
  --reference-id R          leg 2's single identity input, default wd-gc-sample-2026-10-02;
                            the Wix code and idempotencyKey are DERIVED from it, never passed
                            (code via demo_code, which is UNKEYED — see below)
```

Exit codes: `0` all legs matched their expected contract; `1` a contract assertion failed;
`2` a usage error (argparse). It is therefore a smoke test as well as a demonstration — and
**`main(argv)` returns that code rather than calling `sys.exit` itself**, with
`if __name__ == "__main__": sys.exit(main())` at the bottom, so
`tests/test_demo_coupon_giftcard_sample.py` can run it in-process and assert the contract. That
test is what actually stops the demo rotting; §7 explains why a test was chosen over a workflow
step.

**There is no `--pepper` option, deliberately.** Leg 2 derives its code with
`wix_gift_cards.demo_code(reference_id=...)`, which is **unkeyed and demo-only** (§2.5). A
`--pepper` flag would put a pepper-shaped value on a command line, which is the one thing
`secret-handling.md` forbids outright and which
`.kiro/hooks/block-inline-secrets.json` exists to refuse. The demo prints, beside the derived
code, the one line that keeps the distinction visible:

```
  code       ****8FA8   = demo_code(reference_id)   DEMO-ONLY, UNKEYED, 20 chars
  production uses card_code(reference_id, pepper) — keyed; asserted by Group C
```

Printing both is better than printing the production derivation with a fake pepper: a placeholder
pepper would *look* like the production path while proving nothing about it, and the harness
already asserts the keyed derivation properly (§2.4 Group C). The demo's job here is to show the
request shape, which is identical either way, and to be explicit that its own code is not the
production code.

### 4.3 How it is wired, and the one rule that keeps it honest

**It imports production modules and reimplements nothing — including the composition.**
`coupon_store`, `wix_coupons`, `wix_gift_cards`, `gift_card_store`, `money`, `identifiers` and
`wix_ecom` are all imported, and leg 1 additionally drives
`amplify/functions/ecommerce/coupons/handler._create`, because that is the only place in the tree
where claim-row → Wix create → `mark_mirrored` is composed (`handler.py:204-235`, with the
`except Exception` → 202 at `:229-233`). Re-composing
those three steps in the demo would be the "demo passed, product differed" gap this task exists
to close, so the demo stubs the same single function the harness does — `handler._staff` — and
points `handler._coupons_table` at the `FakeTable`. Nothing else is replaced.

**It uses the same stub and the same fake the tests use.** `sys.path` gains
`amplify/functions/shared` and `tests`, then it imports `WixTransport` from
`tests/wix_transport_stub.py` and `FakeTable` from `tests/coupon_fake_dynamo.py`.

> Decision: one stub, two callers — rather than a private copy inside `scripts/`.
> A private copy is the failure mode this task exists to prevent: the demo would pass against a
> stub that no test constrains, and would drift from the one the assertions describe. Nothing in
> `tests/` ships in a Lambda package, because `deploy_all_lambdas.py` packages per-function
> sources from `amplify/functions/`, so there is no deployment cost to the dependency.

**Zero AWS calls — which is not the same claim as zero `boto3`, and the difference is measured.**
`FakeTable` is in-memory and `wix_ecom._key_cache` is pre-seeded per §2.2, so nothing needs AWS.
But importing the coupon handler imports `middleware` and `rate_limit`, and both `import boto3`
at module scope **and construct a client at import** (`middleware.py:24` a `cognito-idp` client,
`rate_limit.py:48` a `dynamodb` resource). So `boto3 imported = NO` is simply false for this
process once leg 1 drives the handler, and printing it would be a false structural claim in the
one artifact whose purpose is to be trusted.

The demo prints, as its final lines, two facts that are true and **enforced**:

```
no AWS:  secretsmanager client built = NO    AWS API calls attempted = 0
         (boto3 is imported by middleware/rate_limit at handler import; two clients are
          constructed, zero calls are made — construction contacts nothing)
```

* *secretsmanager client built = NO* is `wix_ecom._secrets is None`, plus the
  `sys.modules["boto3"]` sabotage from §2.2 installed before the first leg runs, so any
  lazily-imported `boto3` use would raise rather than be counted.
* *AWS API calls attempted = 0* is enforced, not observed: the demo registers a `before-send`
  handler on the event system of each client that exists in the process
  (`middleware.cognito.meta.events`, `rate_limit.dynamodb.meta.client.meta.events`) which raises
  `UnexpectedAwsCall`. A call that would leave the process fails the demo rather than being
  tallied afterwards.

  ```python
  class UnexpectedAwsCall(BaseException):
      """NOT an Exception, for the §2.3 reason, which applies verbatim here.

      Leg 1 drives `coupons/handler._create`, which catches Exception and answers 202 with a
      documented-success body. An Exception raised by this hook would therefore be logged as
      `coupon_mirror_pending`, answered 202, and the demo would print
      `AWS API calls attempted = 0` while a call had in fact been attempted and swallowed.
      """
  ```

  That is the exact failure shape the previous review's finding 1 removed from the Wix stub, and
  it was left in place here until revision 4. The same base class applies to the
  `sys.modules["boto3"]` sabotage (§2.2).

The demo exits `1` if either fact does not hold.

**Nothing secret is printed, and bearer value is masked at the renderer.** The one renderer that
turns a `RecordedRequest` into transcript text:

* omits `Authorization` entirely (it is already `<redacted>` at capture) and prints
  `Authorization: <redacted — wecare/wix/headless-api-key>` so the reader learns *which* secret
  without seeing it;
* masks any gift-card code to `****` + last four **before** rendering, in both directions. Leg 2
  is the case that matters: `CreateGiftCardResponse` returns the **full, unobfuscated** code —
  Wix's own docs say it is *"the full code visible and unobfuscated"* and that it *"isn't
  retrievable with the other methods"* — so the one place a clear code exists in the whole demo
  is a Wix response body, and the renderer must mask it rather than trust Wix's obfuscation.
  **Offline this masking protects nothing, and saying so is the honest version**: the transport is
  stubbed unconditionally, so every code in the demo comes from a fixture and is a placeholder
  (§2.3). It is kept because the renderer is the right place for the rule to live on the day the
  adapter is wired to a live response, and because a masking habit that only appears when it
  matters is a habit nobody has. It is **not** what makes the demo safe to run or to paste;
* refuses to render a body it cannot classify, rather than printing it. A `KeyError` beats a leak.

A **coupon** code is printed in full, deliberately. It is broadcast marketing material and
`tests/test_coupon_logging_and_vocabulary.py` pins that asymmetry from both sides.

**No payment-state decision.** The demo makes none, so it needs no payment vocabulary and
imports none. If a future revision displays a payment state it must call
`payment_status.canonical(...)`; the raw literal `'captured'` must not appear. Note that
`tests/test_payment_vocabulary_at_decision_points.py` resolves its paths under
`amplify/functions/`, so a file in `scripts/` is **outside** that gate's scan — which is a reason
to be explicit here rather than to assume a guard catches it. No change to that gate is needed or
proposed.

### 4.4 Transcript — exact shape

```
WIX COUPON + GIFT CARD SAMPLE                             2026-10-02  OFFLINE
Wix HTTP boundary: STUBBED at urllib.request.urlopen. No live Wix call.

── LEG 1 · COUPON ─────────────────────── VERIFIED: this is how it works today
driver           coupons/handler._create            (production composition)
created_by       demo-operator                      (event["_auth"]["username"])
our claim        COUPON#WDSAMPLE10                 (conditional put, won)
  couponId       01932... (uuid7)
  discount       MONEY_OFF  12345600 paise          = INR 123,456.00
  minimum        500000 paise                       = INR 5,000.00
  currency       INR                                (compared explicitly)
  arithmetic     WIX                                (we never compute a discount)

→ POST https://www.wixapis.com/stores/v2/coupons
  Authorization: <redacted — wecare/wix/headless-api-key>
  Content-Type: application/json
  Accept: application/json
  Wix-site-id: fcd82f0c-9572-49c7-acfb-88fb05042ece
  {
    "specification": {
      "name": "Sample money off", "code": "WDSAMPLE10",
      "startTime": "1719390501000",          ← string (int64), per schema
      "moneyOffAmount": 123456,              ← JSON int, whole rupees
      "minimumSubtotal": 5000,
      "usageLimit": 10, "limitPerCustomer": 1, "limitedToOneItem": false
    }
  }
← 200 {"id":"abeb638b-f9f4-4bb8-8fe7-2319504df6d9"}
handler answer   201                                (202 would mean PENDING_WIX)
our row          wixMirrorState PENDING_WIX → MIRRORED
eligibility      ELIGIBLE                           (a verdict, never an amount)

── LEG 2 · GIFT CARD, WIX-NATIVE ──── CHOSEN: contract under verification (§0.1)
reference      wd-gc-sample-2026-10-02            (--reference-id; the ONLY input)
  code         ****8FA8    = demo_code(reference_id)     DEMO-ONLY, UNKEYED
               20 chars, Wix's maximum — same length production sends
               production uses card_code(reference_id, pepper) — HMAC-keyed under
               wecare/wix/giftcard-spi:code_pepper, domain-tagged; §2.4 Group C
  idem key     wd-gc-b4a4841861…311d  (70 ch)    = idempotency_key(reference_id)
               unkeyed on purpose: not bearer value, and rotation-invariant
  derived      deterministic in its inputs — no clock, no counter, no secrets
→ POST https://www.wixapis.com/gift-cards/v1/gift-cards
  { "giftCard": { "initialValue": {"amount": "2500.50"},   ← decimal string, 2 places
                  "currency": "INR",                       ← compared explicitly
                  "source": "MANUAL",                      ← REQUIRED by Wix (§3.3)
                  "code": "<20 chars, masked in this transcript>" },
    "idempotencyKey": "wd-gc-b4a4841861208fa8a47ba149ded8cdb1d01d57660fc8a259d336a7b56c5e311d" }
  body compared BYTE-EXACT against §2.5's dict: no notificationInfo (that would be
  a live email on a premium plan), no orderInfo (a false provenance claim)
← 200 giftCardId 1d752091-…  codeSuffix 8FA8  balance 250050 paise  resolved=False
   disabled=False  expirationDate None     ← both returned on BOTH paths, so a
   resolve hit onto a disabled or expired card is reportable rather than silent
   codeLast4 read from Wix's own codeSuffix, never parsed out of the obfuscated code
   replay: identifiers RE-DERIVED from the same reference, not reused from above
        → 1 create call total (counted off transport.requests), same giftCardId,
          resolved=True
→ POST .../gift-cards/v1/gift-cards/query
  { "query": { "filter": { "code": { "$eq": "<full code, masked>" } } } }
                                     ↑ a real JSON object, unlike the coupon
                                       query's double-encoded string (§3.4)
← 200 balance "2500.50" → 250050 paise          (Money.from_wix, no float)
   balance and currency come off the QUERY response — measured §3.3, so the
   resolve path is ONE request, not a query followed by a get
   redemption is WIX's: balance is readOnly; we could not move it if we tried
← after Wix-side redemption of 150075 paise → balance "999.75" → 99975 paise
   store of ours in this leg: NONE
   ceiling: no Wix maximum is documented (§3.3); the SPI ceiling is reused so
            legs 2 and 3 are bounded identically and stay comparable

── LEG 3 · GIFT CARD, OURS ──────────── CURRENT: would be removed under (A)
issued           giftCardId 019325…   code ****0002   (HMAC key, pepper by ref)
  balance        250050 paise                       = INR 2,500.50
redeem           150075 paise, attempt demo-attempt-1
  transactionId  01JB…                              (ULID, secrets-backed)
  balance after  99975 paise                        = INR 999.75
replay           same attempt → committed=False, balance 99975 paise unchanged
concurrent       2 threads, same attempt → 1 debit  (see §5)

no AWS:  secretsmanager client built = NO    AWS API calls attempted = 0
         boto3 is imported by middleware/rate_limit at handler import; 2 clients
         constructed, 0 calls made (a before-send hook would fail the run)
3 legs, 0 contract mismatches
```

### 4.5 Validation of the demo's own inputs

Every input is argv. Rules, with the behaviour on failure:

| Input | Rule | On failure |
|---|---|---|
| `--coupon-money-off-paise` | `int`, `> 0`, **multiple of 100**, default `12345600` | exit `2`. The whole-rupee rule belongs **here and only here**: `wix_coupons._rupees` refuses `paise % coupon_store.PAISE_PER_RUPEE` (`wix_coupons.py:107-117`), so a non-whole-rupee coupon cannot be sent at all |
| `--value-paise` | `int`, `0 < v <= 99_999_999_999`, **any paise**, default `250050` | exit `2`, message naming `gift_card_store.MAX_VALUE_PAISE` as the SPI ceiling. **Leg 2 inherits the same bound deliberately**: §3.3 documents no Wix-side maximum (`Amount.amount` is `maxScale: 2`, `gte: 0`), so the SPI ceiling is reused to keep the two legs bounded identically and therefore comparable — not because Wix is known to stop there. If a real Wix maximum is ever measured it belongs in §3.3, and `wix_gift_cards.MAX_INITIAL_VALUE_PAISE` follows it |
| `--reference-id` | non-empty `str`, `<= 200` chars, default `wd-gc-sample-2026-10-02` | exit `2`. Leg 2's `code` and `idempotencyKey` are **derived** from it by `wix_gift_cards.demo_code` / `idempotency_key`, and the replay re-derives rather than reusing, so the transcript demonstrates the property §2.4 Group C asserts instead of assuming it. `demo_code`, not `card_code`: the production derivation is keyed and there is no pepper on a command line (§4.2) |
| `--redeem-paise` | `int`, `0 < v < value_paise`, residual `>= 100` paise, **any paise**, default `150075` | exit `2`; mirrors `gift_card_store.RAZORPAY_MIN_LEG_PAISE` |
| `--coupon-code` | `coupon_store.normalise_code` | exit `2` with the store's own `INVALID_CODE`; the demo does not define a second code rule |
| `--leg` | argparse `choices` | exit `2` |

**Why the gift-card legs must *not* inherit the whole-rupee rule.** The first draft required
`--value-paise` to be a multiple of 100 and called it "Wix's coupon constraint reused for a
comparable transcript". That constraint is real for **coupons only**, and applying it to gift
cards blocks the very property §3.3 calls "the single strongest technical argument for the
Wix-native gift-card model": Wix gift-card amounts are `DECIMAL_VALUE` with `maxScale: 2`, so
`250050 → "2500.50" → 250050` crossing the boundary with no float is the thing worth
demonstrating. With whole-rupee-only inputs the default run never crosses a fractional-rupee
boundary and leg 2 demonstrates nothing it was built for. The defaults are therefore fractional,
and §2.4 Group C asserts that exact round-trip.

No float is constructed on any path: argparse uses `type=int`, and every conversion is `//`,
`Money`, or `Decimal(str(value))` where a decimal is unavoidable. There is no `float(` in the
file, and a test asserts that by AST.

---

## 5. `gift_card_store.redeem()` — the concurrent double-debit window, and the fix

### 5.0 Status of this section after the owner's answer — fixed, or retired by deletion

Revisions 1 and 2 justified this section with *"the verdict is (C), so our store is still the
authority for bearer value"*. The verdict is now **(A)** (§1.2.2), so the justification has to be
restated rather than inherited. It survives, for a narrower and more precise reason:

**The fix stays designed, specified and ready, and it lands if any part of our gift-card store
survives.** The §0.1 gate has two unsatisfied conditions and one of them (a live owner-run
verification) cannot be satisfied by me at all. Until it clears, `gift_card_store.redeem()` is the
code that would move a balance if anything called it, and shipping a known concurrent double-debit
in that state is not defensible on the strength of an intention to delete it later. A design that
says "we were going to remove it anyway" is how a latent money defect outlives the plan that was
supposed to retire it.

**If the gate clears, the defect is retired by deletion, not fixed.** Said in those words,
because the two outcomes read very differently in a report and only one of them is true:

> The `gift_card_store.redeem()` concurrent double-debit window was **retired by deletion, not
> fixed**. Wix owns the gift-card balance under the (A) architecture, `balance` is `readOnly` to
> us, and the `redeem()` path that contained the window no longer exists. No fix was deployed
> because the code was removed instead.

And the third fact that must travel with those two, re-derived live on 2026-10-02 (§0.1):
**nothing was ever deployed** — no `wecare-gift-cards`, no `wecare-wix-giftcard-spi`, no
`GiftCardsTable`, no routes. So **the defect never reached a customer**. It is a latent source
defect found by reading, not a shipped money bug. A reader who finds "double debit" and
"retired by deletion" in the same report without that sentence will reasonably assume the worse
reading, which is why it is written here and required in §6.4's final-report wording.

The decision tree, so there is no third interpretation:

| State | What happens to §5.3's fix |
|---|---|
| Gate open (today) | **implemented**, with its tests, as designed below |
| Gate clears, full retirement | **not deployed**; the code is deleted and the report says *retired by deletion, not fixed* |
| Gate clears partially — any helper, table or handler of ours survives in the money path | **implemented**. Partial survival is the dangerous state, because the window exists and the plan says it does not |

The analysis, the fix and the tests below are therefore unchanged by revision 3.

### 5.1 The window, exactly

`redeem()` today is: conditional claim put → `_decrement` → `_mark_settled` →
`_drop_applied_marker` → transaction rows. `_decrement` sets `appliedClaim#<attempt>` on the
**card** row under `attribute_not_exists`, in the same `UpdateItem` as the balance move. That is
correct and it is what closes the *sequential retry* window the existing tests cover
(`test_a_redemption_whose_settle_write_failed_debits_the_balance_exactly_once`).

The window that is still open is **concurrent**, and `_drop_applied_marker` is what opens it. The
marker is a lock with a lifetime, and the replay short-circuit (`claim.settled`) is read from a
**different item** at a **different time**:

| | Thread A (attempt `X`) | Thread B (attempt `X`, same) |
|---|---|---|
| t1 | `put` claim — **wins** | |
| t2 | | `put` claim — loses |
| t3 | | `_get(claim)` → `settled: False` → falls through to the decrement |
| t4 | `_decrement`: balance −150000, marker set | |
| t5 | `_mark_settled`: `settled: True` | |
| t6 | `_drop_applied_marker`: **marker removed** | |
| t7 | | `_decrement`: `attribute_not_exists(#applied)` now **passes**, `balancePaise >= :amount` passes → **balance −150000 a second time** |

One `paymentAttemptId`, two debits. `balancePaise >= :amount` prevents an *overdraw*, not a
second deduction while funds remain — the module's own comment says exactly that, and this is the
path where it bites. B then returns `committed: True` with A's `transactionId` and a balance
short by the redemption amount, and the `GCTXN#` row is overwritten with the lower
`balanceAfterPaise`, so the ledger agrees with itself and is wrong.

**Reachability.** Two concurrent invocations with the same `paymentAttemptId` are ordinary: a
Lambda retry while the first invocation is still running, an SQS redelivery, a double-submit, or
a client timeout-and-retry. The existing tests cannot see it because every one of them is
sequential — `_MarkerWriteFails` injects a fault, then the retry runs **after** the first call
has returned, so t3 can never be interleaved before t6.

**Severity: HIGH as a source defect, and it never reached a customer.** It would silently debit a
customer's stored value twice and leave a self-consistent ledger, which is why it is HIGH. It has
harmed nobody, because no gift-card function, table or route exists in the account (§0.1,
re-derived 2026-10-02) — so the severity is about what this code would do if invoked, not about
what it has done. Both halves of that sentence belong in any report of it: dropping the first
understates the defect, dropping the second overstates the incident.

### 5.2 Why the obvious repairs do not work

| Candidate | Why it fails |
|---|---|
| Never drop the marker | The card row grows one attribute per redemption forever, toward DynamoDB's 400 KB item cap. The module documents this: *"a card row that cannot be written is a liability that cannot be paid."* |
| Condition the decrement on `activeClaimAttemptId <> :me` | Already refuted in the code and pinned by `test_a_stalled_redemption_still_debits_once_when_another_purchase_lands_between`: the next attempt's decrement overwrites it. |
| Re-read the claim with `ConsistentRead` just before the decrement | TOCTOU. It narrows t3→t7 and does not close it. |
| Drop the marker only after the transaction rows are written | Still a lifetime. B can arrive after any finite lifetime. |

The common defect is that the idempotency fact (`claim.settled`) and the money
(`card.balancePaise`) live on **different items**, so no single-item conditional write can gate
one on the other. DynamoDB's only cross-item atomic primitive is `TransactWriteItems`.

### 5.3 The fix — one transaction, condition on the claim, move the balance

Replace `_decrement` + `_mark_settled` with one `TransactWriteItems` containing exactly two
`Update` items:

```
Item 1  CARD    GIFTCARD#<codeHash>
        UpdateExpression  ADD balancePaise :neg  SET updatedAt = :at,
                          activeClaimAttemptId = :me,
                          activeHoldAttemptId = if_not_exists(activeHoldAttemptId, :me)
        Condition         attribute_exists(giftCardKey)
                          AND balancePaise >= :amount
                          AND #status = :active

Item 2  CLAIM   GCORDER#<codeHash>#<paymentAttemptId>
        UpdateExpression  SET settled = :true, settledAt = :at
        Condition         attribute_exists(giftCardKey) AND settled = :false
```

**In the real API shape, because `transact_write_items` is a low-level client operation and takes
AttributeValue-typed maps.** Native values (`Key={KEY_ATTRIBUTE: "GIFTCARD#..."}`,
`":neg": -amount`) raise `ParamValidationError`; the first draft specified exactly that and would
not have validated. Both existing transaction call sites in this repo already marshal explicitly
(`ecommerce/initiation.py:10,79-82`; `notifications/store.py:239`), and this one emits the same
wire shape — but **not** by the same means, for the reason immediately below.

**The marshaller is hand-written in the module, and it is not `TypeSerializer`, because an
existing gate forbids the import.** Revision 2 specified
`from boto3.dynamodb.types import TypeSerializer` here. That cannot land:
`tests/test_gift_card_store.py::test_the_store_holds_no_boto3_client_and_reads_no_secret_itself`
(`:1152-1180`) walks the module AST and asserts `"boto3" not in imports`, `"botocore" not in
imports` and `"os" not in imports`. `imports` is built from **every** `ast.Import` and
`ast.ImportFrom` under `ast.walk`, so moving the import inside a function body does not help —
and that test is the structural form of the module's central claim, *this module cannot read a
secret at import even by accident*. Weakening a gate to make a change land is the move this
document refuses everywhere else; it does not get an exception for its own convenience.

Three options were available. **Chosen: hand-marshal the three types this transaction actually
uses, in the module, and pin it against `TypeSerializer` from `tests/`.**

```python
def _marshal(value: Any) -> Dict[str, Any]:
    """The AttributeValue form of the three types this module's transactions carry.

    Hand-written because `boto3.dynamodb.types` may not be imported here - see
    test_the_store_holds_no_boto3_client_and_reads_no_secret_itself. Pinned byte-for-byte
    against TypeSerializer by a test, where botocore is already a dependency.
    """
    if isinstance(value, bool):          # BEFORE int: bool IS an int in Python
        return {"BOOL": value}
    if type(value) is int:               # exact type, so Decimal/float cannot slip through
        return {"N": str(value)}
    if isinstance(value, str):
        return {"S": value}
    raise GiftCardValidationError(
        "UNMARSHALABLE_VALUE", f"cannot marshal {type(value).__name__}")
```

**The two arguments are not interchangeable, which revision 4's one-argument form got wrong.**
`GiftCardError.__init__(code, message="")` sets `self.code = code` and passes `message or code` to
`ValueError`, and `.code` is the **stable, enumerable** field handlers surface — the SPI maps it
through `SPI_ERRORS`. Passing an interpolated message in the `code` slot makes the code vary with
the offending type, so a handler cannot branch on it and a log cannot group by it. Every other
site in the module passes a constant code plus prose, including §5.3.1's own
`GiftCardValidationError("BALANCE_CEILING_EXCEEDED")`.

**`GiftCardValidationError`, not `GiftCardStoreUnavailable`, and the difference is operational.**
`GiftCardStoreUnavailable` is a `RuntimeError` that every caller reads as *transient, retry me*;
an unmarshalable value is a programming error that will recur identically on every retry, so
labelling it retriable turns one defect into a retry storm against a money path. It is also a
"cannot happen" guard rather than an expected branch — `value_paise()` has already refused
non-integer amounts upstream — which is exactly the kind of condition that must fail once,
loudly, and stay failed. `GiftCardValidationError` is a `GiftCardError`/`ValueError`, which is
the non-retriable family.

* **The float refusal is explicit and is the point.** `TypeSerializer` refuses a `float` with
  `TypeError: Float types are not supported`; `_marshal` refuses it by not matching any branch.
  Either way the serialiser is a money gate, and `type(value) is int` additionally refuses a
  `Decimal` and a `bool`-as-amount, which `TypeSerializer` would accept and quietly convert.
* **The equivalence is tested, not asserted.** One test in `tests/` imports
  `boto3.dynamodb.types.TypeSerializer` and asserts `_marshal(v) == TypeSerializer().serialize(v)`
  for the exact value set these transactions carry — every amount sign, `0`, `MAX_VALUE_PAISE`,
  `-MAX_VALUE_PAISE`, both booleans, and the key and status strings — so a divergence from boto3
  is caught in the one place that can see both.
* The two options not taken, and why: **injecting a serializer** (`redeem(..., serialize=None)`)
  keeps the gate intact too, but adds a parameter to a public money function that every caller
  would pass the same value for, and the module's existing injections (`clock`, `SecretReader`)
  exist because those reach **outside the process** — marshalling does not, so it is not the same
  category. **Amending the gate** with a narrow `boto3.dynamodb.types` exemption is the weakest
  option: it trades a one-line structural guarantee for ten lines of code we would otherwise
  write once, and it must not be chosen silently, so it is recorded as rejected rather than
  omitted.

The redeem transaction's card item, then, with `_ser` a module-level alias for `_marshal` so the
expression stays readable:

```python
_ser = _marshal

card_item = {"Update": {
    "TableName": table.name,
    "Key": {KEY_ATTRIBUTE: _ser(PREFIX_CARD + digest)},
    "UpdateExpression": ("ADD balancePaise :neg SET updatedAt = :at, "
                         "activeClaimAttemptId = :me, "
                         "activeHoldAttemptId = if_not_exists(activeHoldAttemptId, :me)"),
    "ConditionExpression": (f"attribute_exists({KEY_ATTRIBUTE}) AND balancePaise >= :amount "
                            "AND #status = :active"),
    "ExpressionAttributeNames": {"#status": STATUS_ATTRIBUTE},
    "ExpressionAttributeValues": {":neg": _ser(-amount), ":amount": _ser(amount),
                                  ":me": _ser(attempt), ":at": _ser(now),
                                  ":active": _ser(STATUS_ACTIVE)},
}}
```

`:neg` is `-amount` where `amount` came from `value_paise()`, so it is an `int` and marshals to
`{"N": "-150000"}` — a **decimal string on the wire**, which is a hop §5.6 now covers explicitly.
Read-back is `int(value["N"])`, never `float(...)` and never a `Decimal` that is then divided.
Measured on this interpreter for the pin above: `TypeSerializer().serialize(-150000)` is
`{'N': '-150000'}`, `serialize(False)` is `{'BOOL': False}`, and `serialize(1.5)` raises
`TypeError: Float types are not supported. Use Decimal types instead.` — so `_marshal` matches
boto3 on every value this path produces and refuses the same thing more strictly.

`settled = :false` on item 2 **is** the idempotency guard, and it now commits in the same
transaction as the money. Thread B at t7 fails that condition, the whole transaction is cancelled,
nothing moves, and B takes the replay branch. The guarantee no longer depends on any marker's
lifetime, so `appliedClaim#` is not needed and `_drop_applied_marker` is not called on this path.

**What this changes in the surrounding code:**

* `_decrement` becomes
  `_commit_redemption(table, digest, claim_row_key, amount, attempt, now, *, sleep=time.sleep)`,
  returning the post-commit balance. The `sleep` keyword is the one `redeem()` threads down to
  `_transact_with_retry` (see the signature-change blockquote below); its void twin
  `_commit_void` carries the same keyword for the same reason.
* `_mark_settled` is **removed entirely**, not merely bypassed: `settled` is written by the
  transaction on the redeem path, and the void note below converts `void()` in the same change,
  which removes `_mark_credited`'s last caller too. Neither helper keeps a caller, so neither is
  kept — a settle helper that still exists invites a future caller to write `settled` outside the
  transaction, which is the exact defect §5.3 closes. This is what the §8 Modified table records.
* `balanceAfterPaise` on the claim row cannot be written inside the transaction, because
  `TransactWriteItems` has no `ReturnValues: ALL_NEW`. It is written by one follow-up
  best-effort `UpdateItem`. Nothing reads it to make a decision — measured: `balanceAfterPaise`
  appears at three sites in `gift_card_store.py` (`:1259`, `:1367`, `:1478`) and all three are
  **writes**. If it fails, the claim is still settled and the money has still moved exactly once.
* **The post-commit balance is customer-visible, so state the invariant rather than a
  reassurance.** Calling it "a report, not a decision" is too weak: `redeem()`'s
  `remainingBalancePaise` is emitted by the SPI as `{"remainingBalance": ...}`
  (`wix-giftcard-spi/handler.py:323`, and `:361` for void), which is the figure Wix shows and
  settles against at checkout — and §5.1 cites exactly this inaccuracy as part of the bug being
  fixed. Replacing `ReturnValues="ALL_NEW"` with a separate read reintroduces a smaller version
  of the same divergence whenever another move interleaves. The invariant, which goes in the
  docstring in these words:

  > `remainingBalancePaise` and `GCTXN#.balanceAfterPaise` are the card's balance **as at the
  > read that followed the commit**, which may already include a later interleaved move. They are
  > observations, not the result of this transaction. `TransactWriteItems` returns no `ALL_NEW`,
  > so an exact post-this-transaction figure is not obtainable. The figure that **is** exact is
  > `amountPaise`, and the authoritative balance is always a fresh consistent read of the card
  > row.

  Two things keep that honest rather than merely written down: a test asserting **no branch reads
  `balanceAfterPaise`** (so it can never become an input to a decision), and the fact that Wix's
  own `/v1/balance` is a separate SPI call, so Wix never has to trust a number carried back on a
  redeem response. The existing contract that no read **precedes** the money move is preserved
  and strengthened: the decision was the condition.
* `APPLIED_CLAIM_PREFIX` loses its only caller. It is **removed** from the module and from
  `__all__`, and the `CARD_ATTRIBUTES` docstring note about claim markers is narrowed to the void
  marker. A constant with no caller misleads the next reader into thinking a guard exists.

**Transaction mechanics.** `TransactWriteItems` is a **client** operation, not a `Table` resource
one. The store resolves it as `table.meta.client.transact_write_items(...)` with
`TableName=table.name` — the real boto3 shape, with no fake-shaped branch. `tests/coupon_fake_dynamo.py`
supplies `.name` and `.meta.client` (§2.6). Two items, well inside the 100-item / 4 MB limits;
cost is 2× WCU on the redeem path only, which is the correct price for not debiting twice.

**Error handling, per failure condition:**

| Condition | Detected as | Recoverable? | Caller receives | Logged |
|---|---|---|---|---|
| balance short | `TransactionCanceledException`; post-read shows `balancePaise < amount` | **yes** — claim stays unsettled, a later top-up plus retry completes under the same `transactionId` | `InsufficientFunds` (SPI `INSUFFICIENT_FUNDS`, 428) | warning, `giftCardId` + `codeLast4` masked |
| card disabled / expired | same, post-read via `assert_spendable` | no | `GiftCardDisabled` / `GiftCardExpired` (428) | warning, masked |
| claim already `settled` | **the pre-read**, with no transaction opened: the conditional claim `_put` loses, the existing claim is read, and `if existing.get("settled")` returns the replay answer (`gift_card_store.py:1237-1242`); or, on a race, the post-cancellation read showing `settled: True` | n/a — **this is the fix firing** | the replay answer: `committed: False`, original `transactionId`, current balance | info |
| card row absent | same; post-read returns nothing | no | `GiftCardNotFound` (404) | warning |
| **transaction conflict** — another transaction is touching the same card row | `TransactionCanceledException` whose `CancellationReasons[].Code` includes `TransactionConflict`, `ThrottlingError` or `ProvisionedThroughputExceeded` | **yes** — bounded retry | after the bound is exhausted, `GiftCardStoreUnavailable` | warning per retry with the attempt number and `type(exc).__name__`; error on exhaustion |
| throttle / outage, not a cancellation | any other client error | retry at the caller | `GiftCardStoreUnavailable` | error, `type(exc).__name__` only |
| `balanceAfterPaise` follow-up fails | swallowed | n/a | success, as it was | nothing |
| **`GCTXN#` record or `GCTXN-ID#` pointer put fails** | whatever `_put` raises | **no** — the claim is already `settled` by the transaction, so a retry takes the replay branch and never re-drives the put | unchanged from today | unchanged from today |

**That last row is not a hole this change opens, and it is listed so nobody reads it as one.**
Both tables in §5.3 and §5.3.1 are exhaustive about the transaction and were silent about the
plain `_put`s that follow it, which invites a reader comparing two otherwise-complete tables to
assume completeness. The state is: post-fix, `settled` is latched **with** the money, so a failed
ledger-row put is never re-driven and the `GCTXN#` row a `void()` resolves by is permanently
absent. Verified from the tree that **this hole already exists pre-fix** once `_mark_settled`
succeeds — the ordering is `_decrement` → `_mark_settled` → the `_put`s, so a put failing after a
successful settle is already unrecoverable today. It is therefore **out of scope for this fix,
recorded so it is not read as introduced by it.** If the §0.1 retirement gate does not clear, it
is a named follow-up: *the ledger row and its pointer should be written inside the transaction, or
re-driven by a reconciler keyed on a settled claim with no `GCTXN#` row.* Under (A) it goes with
the deletion, which is the only reason it is not being fixed here.

**The cancellation branch reads the structured reason codes, and that is not the banned
pattern.** The ban is on parsing an exception's *message*
(`test_no_branch_parses_a_status_out_of_an_exception_message`); `CancellationReasons[].Code` is a
documented response field, in the same class as `response["Error"]["Code"]`, which
`_is_conditional_failure` already reads. The first draft said "detect cancellation by error code
only, then decide from the data", and that cannot reach the right answer for the likeliest
cancellation this fix will ever see: two concurrent transactions on one card row produce
**`TransactionConflict`**, where a data read finds a sufficient balance, an unsettled claim and
an active card — matching **none** of the six decide-from-data rows, and falling through most
naturally to `InsufficientFunds`, which would be a wrong refusal of a valid redemption.

```python
def _is_transaction_cancellation(error: BaseException) -> bool:
    """True only for TransactWriteItems cancellation, however the client spells it."""

def _cancellation_reason_codes(error: BaseException) -> list[str]:
    """The documented CancellationReasons[].Code list, or [] if the shape is absent.

    botocore puts this list at the TOP LEVEL of the response, a sibling of "Error" - NOT
    inside it. Reading it from response["Error"] yields [] on every real cancellation and
    converts the main path of this fix into a 5xx.
    """
    response = getattr(error, "response", None)
    if not isinstance(response, dict):
        return []
    return [str((reason or {}).get("Code") or "")
            for reason in (response.get("CancellationReasons") or [])]
```

**The path matters and the default has to be safe.** The same class of access is already in this
module — `_is_conditional_failure` reads `response["Error"]["Code"]` (`gift_card_store.py:377-384`)
— so a sibling field is not a new kind of coupling, but a wrong path here fails silently rather
than loudly: `[]` matches no branch, falls to "anything else", and answers
`GiftCardStoreUnavailable` for what is in fact a **successful replay detection**. So the fallback
rule is stated and implemented rather than left to the branch order:

> **A cancellation whose reason codes are empty or unrecognised is treated as
> `ConditionalCheckFailed` and decided from the data — never as an outage.** A cancellation is by
> definition a condition outcome unless a reason says otherwise, so the safe default is the
> decide-from-data path, which can still answer `GiftCardStoreUnavailable` if the data supports
> nothing else.

* `ConditionalCheckFailed` present, **or no recognised reason at all** → read the claim row and
  the card row by exact key and decide from the data (the six rows above). Unchanged, and still
  the main path.
* `TransactionConflict` / `ThrottlingError` / `ProvisionedThroughputExceeded` → **bounded
  retry: 2 retries, 3 attempts total.** Delay before retry *n* is `0.05 * 2 ** n` seconds plus
  jitter of `_secrets.randbelow(25) / 1000` — so 50-75 ms then 100-125 ms, worst case ~200 ms
  added, well inside any Lambda timeout on this path. `secrets` rather than `random` because the
  module already imports `secrets as _secrets` and because `random`'s PRNG state is a documented
  SnapStart hazard in this fleet. The sleeper is **injected** (`sleep: Callable[[float], None] =
  time.sleep`, matching the module's existing `clock` injection) so the covering test runs at
  full speed with a no-op.

> **The sleeper's reach is a public signature change, so it is stated rather than implied.**
> `redeem()` and `void()` each gain a keyword-only `sleep: Callable[[float], None] = time.sleep`,
> threaded down to `_transact_with_retry` through the committer exactly as `clock: Clock =
> _default_clock` is threaded today (`gift_card_store.py:1174` for `redeem`, `:1395` for `void`).
> Without this, §7's covering test cannot be written from this document: `_transact_with_retry`,
> `_commit_redemption` and `_commit_void` are all private and reachable only through `redeem()`
> and `void()`, and the exhaustion assertion needs the full `redeem()` path because its second
> half is *the balance did not move*.
>
> **No existing caller passes it.** The only production callers are
> `wix-giftcard-spi/handler.py:310` (`store.redeem(...)`) and `:341` (`store.void(...)`); both are
> unaffected because the parameter is defaulted. So this is an **additive** public signature
> change, and the tests are its only suppliers. It is listed in §8's Modified row beside
> `credit()`'s `once_key` removal, so the module's public surface is described in one place.
>
> The two alternatives were rejected for stated reasons. Monkeypatching `gift_card_store.time.sleep`
> would make the word "injected" and the `clock` parallel wrong in §5.3, §5.3.1 and §7 — a
> parameter nothing ever passes is a default, not an injection. Calling `_transact_with_retry`
> directly from the test puts the balance half of the exhaustion assertion out of reach. The cost
> of the choice taken is a wider diff in a shared money module, which is the same cost `credit()`'s
> `once_key` removal already carries and which §9's ownership check already bounds.

**Decision: the retry is ONE shared wrapper, and it is the only site that opens a transaction.**

```python
def _transact_with_retry(table: Any, items: list, *, sleep: Callable[[float], None] = time.sleep):
    """The ONLY call site of transact_write_items in this module.

    Both committers route through here, so the bounded retry, the jitter and the injected
    sleeper exist once. A cancellation that is not a retryable conflict is re-raised
    unchanged, so the caller's decide-from-data branch is unaffected by this wrapper.
    """
```

**The void committer is named, because the §5.5 AST guard asserts its name.** The void
transaction is assembled in a helper mirroring the redeem side, not inline in `void()`:

```python
def _commit_void(table: Any, digest: str, transaction_key: str, amount: int, now: int,
                 *, sleep: Callable[[float], None] = time.sleep) -> int:
    """The void twin of _commit_redemption. Assembles §5.3.1's two items and
    routes them through _transact_with_retry. Returns the post-commit balance."""
```

Naming it is not cosmetic: §5.5's guard asserts the **names** of `_transact_with_retry`'s two
callers, so leaving the void twin anonymous would leave the implementer choosing between
`{"_commit_redemption", "_commit_void"}` and `{"_commit_redemption", "void"}` — two guards
asserting different things. `_commit_void` is the choice, and it is used in §5.3.1, §5.5, §7 and
§8 rather than the phrase "the void committer".

Both `_commit_redemption` and `_commit_void` call `_transact_with_retry`; neither calls
`table.meta.client.transact_write_items` directly. The alternative — duplicating the loop in both
functions — was considered and rejected: §5.3.1 gives the void path *"the same bounded retry as
redeem, same injected sleeper"*, and two copies of a jittered retry loop is the duplication a
reviewer of the implementation would ask to be factored out, which would then leave the §5.5 gate
pinned to a shape the code no longer has. **Deciding it here is what lets §5.5's AST guard assert
the real structure instead of an assumed one**, and the two have to be decided together — a guard
written against an imagined call-site layout is the failure mode this document has now repaired
twice.
* anything else → `GiftCardStoreUnavailable(f"could not move a gift-card balance: {type(exc).__name__}")`.

**A separate predicate rather than a broadened one.** The first draft extended
`_is_conditional_failure` to also recognise `TransactionCanceledException`. That predicate is
consulted by `_put`, `hold`, `credit`, `disable`, `release` and `_delete_hold`
(`gift_card_store.py:377-385`), none of which opens a transaction, so a broadened answer would
only ever be correct there by accident. `_is_transaction_cancellation` keeps each predicate
answering one question and is the natural home for the reason-code branch. `_is_conditional_failure`
is left exactly as it is.

Coverage: `FakeTable.transact_write_items` can be armed with a cancellation carrying a
`TransactionConflict` reason (§2.6), so the retry branch is exercised by a test rather than
asserted in prose — including the exhaustion path, which must surface
`GiftCardStoreUnavailable` and must **not** move the balance.

**The void path has the identical window** — `credited` is on the transaction row, `appliedVoid#`
is a card-row marker, and `_drop_applied_marker` ends its lifetime.

> Decision: convert `void()` in the same change, using the same two-item transaction (credit the
> card under `balancePaise <= :ceiling`; set `credited = :true` on the voided transaction under
> `credited = :false`). The alternative — fix only `redeem` — leaves the same bug under another
> name in a module whose whole claim is that both strands *"fail and recover identically"*, and a
> half-converted module is harder to reason about than either end state.
>
> **Said explicitly rather than implied, because it is a public signature change:**
> `credit()`'s `once_key` parameter is **removed**, along with the marker branch it selects
> (`gift_card_store.py:951-1015`, where `marker = APPLIED_VOID_PREFIX + _transaction_id(once_key)`
> is built only when `once_key` is given). `credit()` keeps **only** the plain addition, which is
> the correct form for a genuine top-up: two credits of the same size are two different events,
> and nothing should make them idempotent. The void path's idempotency moves into the
> transaction's `credited = :false` condition, so `APPLIED_VOID_PREFIX` loses its last caller and
> goes with it. `void()` at `:1471` is the only caller that passes `once_key` today.
>
> Risk, stated: this widens the diff in a shared module. §9 records the ownership check this
> requires before the edit lands.

#### 5.3.1 The void transaction, specified at the same depth as the redeem one

Revision 2 committed to converting `void()` in the same change and then specified it in one
blockquote — a tenth of the redeem half's detail, for a path with **more** states, not fewer.
That asymmetry is how a second latent money bug survives a change whose whole purpose is to
remove the first. The two items:

```
Item 1  CARD    GIFTCARD#<codeHash>
        UpdateExpression  ADD balancePaise :amount  SET updatedAt = :at
        Condition         attribute_exists(giftCardKey)
                          AND balancePaise <= :ceiling          -- :ceiling = MAX_VALUE_PAISE - amount

Item 2  TXN     GCTXN#<codeHash>#<transactionId>
        UpdateExpression  SET credited = :true, creditedAt = :at
        Condition         attribute_exists(giftCardKey)
                          AND attribute_exists(credited)
                          AND credited = :false
```

**`attribute_exists(credited)` is written explicitly, and is not redundant.** In DynamoDB a bare
`credited = :false` already **fails** when the attribute is absent, so the two conditions accept
the same set — but they are not diagnosable the same way. With `attribute_exists` named, the
post-cancellation read can distinguish *absent* from *`True`* and answer each correctly; without
it, "absent" is indistinguishable from "already credited" in the branch set, matches no row,
and falls through to `GiftCardStoreUnavailable` — so every retry cancels again and a card whose
void predates the flag becomes **permanently un-voidable**. That is the mirror image of the
irreversibility `test_a_void_whose_credit_failed_is_completed_by_a_retry_not_refused` exists to
prevent, and it is the reason `credited` has to be treated as three-valued rather than boolean:

| `credited` | Means | Must |
|---|---|---|
| `False` | `void` latched and the credit has not landed | re-drive the credit |
| `True` | the credit landed | refuse, `AlreadyVoided` |
| **absent** | latched by code that predates the flag | **treat as complete**: refuse, and **do not credit** |

**Decision: a duplicate `void()` refuses at the PRE-READ, before any transaction is opened — and
the same decision applies to a duplicate `redeem()`, symmetrically.** Revisions 2-7 left this
ambiguous on both sides, and it cannot stay ambiguous, because no transaction count can be stated
about any redeem or void test until it is settled — which is what made §5.5's caller counts wrong
rather than merely imprecise. Read from the tree, `void()` already does this:

```python
latched = original.get("voidedBy")
if latched:
    if original.get("credited") is not False:          # gift_card_store.py:1441
        raise AlreadyVoided("this transaction was already voided")
```

`is not False` covers **both** `True` and **absent**, and it raises with **no write at all**. That
behaviour is kept, for two reasons: it is one condition cheaper than opening a conditional
transaction only to have it cancelled, and it is already covered by
`test_a_void_latched_before_the_credited_flag_existed_is_never_re_credited`, which seeds a row with
`credited` popped and asserts `AlreadyVoided` with the balance unmoved — a test this fix must not
need to change.

So the transaction is opened **only** when the pre-read saw `credited is False`, and the two
conditions on item 2 are the **concurrency re-check**, not the primary decision: a second `void()`
that commits between this one's pre-read and its transaction must lose, and `credited = :false` is
what makes it lose. The post-cancellation read then answers which of the three states it landed
in — reachable here only through that race, which is exactly why
`attribute_exists(credited)` is still written explicitly: the diagnosability argument above is
unchanged, and a race is the one route by which the absent case can reach a cancellation at all.

**The redeem path is the same shape, and the review did not reach it — so it is decided here too
rather than left to be found later.** `redeem()` already short-circuits a settled claim before any
money move: the conditional claim `_put` loses, the existing claim is read, and `if
existing.get("settled")` returns the replay answer at `gift_card_store.py:1237-1242` with
`_decrement` never called. §5.3's *"claim already `settled`"* row read as a post-cancellation
outcome, exactly as this section's `credited` row did, and the correction is identical: the
**pre-read** answers the ordinary replay, and `settled = :false` on the transaction is the
**concurrency re-check** that makes a racing second redeem lose. Both tables now say which, and
the two paths are decided the same way — which is what the module's own claim that the two strands
*"fail and recover identically"* requires, and what makes §5.5's caller counts derivable at all.

**Error handling, per failure condition** — the same shape as the redeem table above. The first
two rows are answered by the **pre-read** on the ordinary duplicate-void path and by the
**post-cancellation read** on the racing path; both answer identically, which is the property that
lets one row cover both:

| Condition | Decided by | Recoverable? | Caller receives | Logged |
|---|---|---|---|---|
| `credited` is `True` | the **pre-read** (`:1441`), with **no transaction opened**; or, on a race, the post-cancellation read | n/a — **this is the fix firing** | `AlreadyVoided` (SPI `ALREADY_VOIDED`, 409) | info |
| `credited` is **absent** | the **pre-read**, same branch, same no-write path; or, on a race, the post-cancellation read distinguishing absent from `True` via `attribute_exists(credited)` | n/a | `AlreadyVoided`, and the balance is **not** moved | info, with the absence named so the legacy row is visible in logs |
| ceiling exceeded | the post-cancellation read: `balancePaise + amount > MAX_VALUE_PAISE` | no | `GiftCardValidationError("BALANCE_CEILING_EXCEEDED")` | warning, masked |
| transaction row absent | the pre-read, before anything: nothing at `GCTXN#...` | no | `TransactionNotFound` (SPI `TRANSACTION_NOT_FOUND`, 404) | warning |
| card row absent | the post-cancellation read: nothing at `GIFTCARD#...` | no | `GiftCardNotFound` (404) | warning |
| `TransactionConflict` / throttle / `ProvisionedThroughputExceeded` | — | **yes** — the same bounded retry as redeem, because it is literally the same code: `_commit_redemption` and `_commit_void` both call `_transact_with_retry`, same injected sleeper, supplied by `void(..., sleep=…)` on the same defaulted keyword `redeem()` gains | `GiftCardStoreUnavailable` on exhaustion | warning per retry with `type(exc).__name__`; error on exhaustion |
| empty or unrecognised reason codes | — | — | decided from the data, per the fallback rule above | as the matched row |

The `voidedBy` latch write is unchanged and still **precedes** the transaction, and it is still
the thing that makes a mid-void failure recoverable: the latch records *which void owns this
transaction*, the transaction moves the money and flips the flag together, and a retry under the
same void id re-drives only the part that did not land. What the conversion removes is the
window **between** them, exactly as on the redeem side.

### 5.4 The concurrent test — `tests/test_gift_card_redeem_concurrency.py` (new)

The test must **fail before the fix and pass after**, and it must be genuinely concurrent rather
than a sequenced simulation, because a sequenced simulation is what the existing suite already
has and it is what missed this.

**The barrier must latch on a seam that exists in BOTH code versions.** The first draft latched
inside `_drop_applied_marker` — a helper §5.3 **deletes**. Post-fix nothing would block thread A,
and the test would degrade from a forced interleaving into an unsynchronised race that can pass
for the wrong reason (B completing its entire `redeem` before A even issues its transaction). The
design's own standard would then be met before the fix and not after.

So the barrier is defined on the **property** — "a balance-moving call" — for the same reason
`_is_balance_move` matches either representation:

```python
class _InterleaveAtBalanceMove(FakeTable):
    """Forces the §5.1 schedule by latching on balance MOVES, not on a helper name.

    A balance move is `update_item` carrying `ADD balancePaise` (pre-fix) or
    `transact_write_items` whose items carry the same fragment (post-fix). One mechanism,
    both code versions, forced on every run rather than raced for.

    It overrides BOTH `update_item` AND `transact_write_items` - one for each
    representation - awaiting its latch BEFORE delegating to `super()` in each, so the
    table lock is never held across a wait. Overriding only `update_item`, which is the
    pattern the two existing subclasses in the suite show, latches the pre-fix version and
    silently stops latching anything the moment the fix lands.
    """
```

**Two overrides, not one, and the existing examples are the reason this has to be said.** The
property above is representation-independent, but a subclass is not: `_MarkerWriteFails` and
`_CreditThrottles` each override `update_item` **alone**, so the single-method shape is the one a
reader copies from this suite — and copying it here produces a test that degrades into an
unsynchronised race exactly when the fix it covers is applied, which is the failure this whole
section is built to avoid. Both overrides also have to honour §2.6's rule in full: **await the
latch, then enter `super()`**, never the reverse.

Three `threading.Event`s and no `sleep` anywhere, so the schedule is forced rather than timed:

| Event | Set by | Waited on by |
|---|---|---|
| `claim_written` | the fake, after A's `put_item` on the `GCORDER#` key is applied | the **main thread**, which starts B only then — so A always wins the claim and the roles are not raced for |
| `claim_read` | the fake, after B's `get_item` on the `GCORDER#` key returns | A's **first** balance move, which blocks until B has seen `settled: False` — this is t3 before t4 |
| `a_returned` | the main thread, when A's `redeem()` has returned | B's balance move, which blocks until A's whole redeem is complete — this is t7 after t6, and it is what makes the pre-fix double debit certain rather than likely |

**Three events, two joins, and the main-thread sequence written out** — because the whole test is
an ordering argument and the fourth event contradicted it. Revision 2 listed a shared `done` set
by *each* thread and waited on by the main thread before the assertions, while `a_returned` is
set by the main thread *when A has returned*. The main thread cannot learn "A specifically has
returned" from an event both threads set; it has to join A. So:

```
start A
wait  claim_written          # A owns the claim; roles are not raced for
start B
A.join(5)                    # A's whole redeem is complete
set   a_returned             # releases B's balance move — t7 after t6
B.join(5)
assert ...                   # both threads are finished; nothing is in flight
```

Each `join` carries the 5 s bound, and the test asserts `not thread.is_alive()` after each one,
so a deadlock fails as a deadlock rather than as a confusing assertion about a balance. A
`done` event is not needed at all once the joins carry the ordering.

Threads are named `A` and `B`, and the fake decides which latch applies from
`threading.current_thread().name`. That identity comes from the test, not from the shape of the
production code, which is why the same subclass works unchanged across the fix.

**The barrier waits OUTSIDE the lock, and that constraint is not optional.** §2.6 gives
`FakeTable` an `RLock` held for the whole body of every operation, condition evaluation included,
because that is what models DynamoDB's atomicity. If the barrier blocked while holding it, the
other thread's `get_item` could never return and the test would deadlock into its 5 s timeout. So
each latch is awaited **before** the locked body is entered, and the operation then runs
indivisibly. That is still exactly the interleaving the real database has: interleaving between
calls, atomicity within one.

Walking the pre-fix schedule with this mechanism: A puts the claim and wins → main starts B →
A reaches `_decrement`, waits → B's claim put loses, B reads the claim, `settled: False`, sets
`claim_read` → A applies the decrement and the marker, settles, **drops the marker**, returns →
main sets `a_returned` → B's decrement proceeds: the marker is absent and the balance is still
sufficient, so it **debits a second time**. Two moves, `200000` paise left instead of `350000`.
Post-fix: A's transaction waits the same way, commits balance **and** `settled` together, returns;
B's transaction then fails `settled = :false`, is cancelled, moves nothing, and B takes the replay
branch. One move, `350000`.

**The test's own amounts are load-bearing: the face value must exceed twice the redemption.**
It uses `500000` and `150000` deliberately — `balancePaise >= :amount` is still evaluated on B's
second attempt, so with a value under `2 × redeem` the **balance floor** would refuse the second
debit and the bug would be masked by an unrelated guard. (The demo's fractional defaults in §4.5
exist for a different purpose — the Wix decimal boundary — and are not used here.) A sibling test
asserts the floor still refuses a genuine overdraw, so the two guards stay distinguishable.

**Assertions:**

```python
def test_two_concurrent_redeems_for_one_payment_attempt_debit_once():
    # value 500000, both threads redeem 150000 under attempt "attempt-1"
    assert card["balancePaise"] == 350000                                       # NOT 200000
    assert len([c for c in store.calls   if _is_balance_move(c)]) == 2          # both TRIED
    assert len([c for c in store.applied if _is_balance_move(c)]) == 1          # one LANDED
    assert {r["transactionId"] for r in results} == {one_id}
    assert sum(1 for r in results if r["committed"]) == 1
    assert sum(1 for r in results if not r["committed"]) == 1
    assert store.rows[claim_key]["settled"] is True
    assert not [k for k in card if k.startswith("appliedClaim#")]
```

**Why there are two counts, and why one of them would have failed against correct code.** The
single `store.calls ... == 1` assertion in revision 2 cannot pass post-fix, and this is the worst
possible direction for this particular test to fail. `FakeTable` appends to `calls` **before** it
evaluates the condition (`update_item`: append at `:275`, arm-check `:280`, condition at `:285`,
raise at `:286`), and §2.6 specifies the new `transact_write_items` the same way. So `calls`
counts **attempts**:

| | balance-move *calls* | balance moves *applied* | final balance |
|---|---:|---:|---|
| pre-fix | 2 | 2 | 200000 |
| post-fix | **2** — A commits, B is recorded and then cancelled | 1 | 350000 |

Asserting `calls == 1` therefore reports `2` after the fix and goes red on code that is right.
The design's own standard names the hazard this creates: an assertion that fails for a confusing
reason "gets *fixed* by loosening the assertion rather than by reading why" — and loosening this
one to `<= 2`, or deleting it, removes the only assertion that distinguishes one debit from two
*at the call level*. Hence §2.6's `applied` log and both numbers here: pre-fix reads 2 / 2 /
200000 and fails on the second and third lines; post-fix reads 2 / 1 / 350000 and passes. The
attempt count is worth keeping rather than replacing, because "B tried and was refused" is a
different and stronger statement than "B did not try".

`_is_balance_move` matches a balance move in **either** representation — an `update_item`
containing `ADD balancePaise`, or a `transact_write_items` whose items contain one. The fragment
lives in `UpdateExpression`, which is a plain string in both forms and is untouched by the
`_marshal` marshalling of §5.3, so one predicate reads both without special-casing, and it works
on `calls` and `applied` alike since both hold the same tuple shape. The test expresses the
property rather than one spelling of it.

A sibling asserts the same shape for `void()` — two concurrent voids of one transaction credit
once, both counts asserted the same way — and a third asserts the property that must **not**
regress: two *different* `paymentAttemptId`s still debit twice. A fourth covers §5.3.1's
three-valued `credited`: a transaction row with **no** `credited` attribute is refused with
`AlreadyVoided` and the balance does not move, which is the legacy-row case that would otherwise
be permanently un-voidable.

### 5.5 Existing tests this changes, and the property each must keep

Enumerated per test, in the style `SEAM-C1c` uses in the prior design, because "the suite went
green" is not evidence when the mechanism under test moved.

| Test in `tests/test_gift_card_store.py` | Change | Property preserved |
|---|---|---|
| `test_the_balance_cannot_go_negative_under_concurrency` | none | behavioural only; passes unchanged |
| `test_the_balance_floor_is_a_condition_expression_not_a_read_then_write` | **update** — look for the floor condition inside the `transact_write_items` card item instead of an `update_item`, and index the read-ordering assertion on the `transact_write_items` call rather than on `update_item` | **the floor is a condition on the transaction, and no read precedes the money move.** Not "no read precedes it": post-fix §5.3 adds a balance read *after* the commit for the best-effort `balanceAfterPaise` follow-up, and the existing assertion `"get_item" not in operations[:operations.index("update_item")]` would index on the surviving `update_item` — which is now that follow-up — and so would be asserting the wrong thing about the wrong write. §5.3's prose already states the property correctly; only this row disagreed with it. **Three assertions move, not two** — the enumeration was short by one: the test also holds `decrements[0]["ExpressionAttributeValues"][":neg"] == -40000` (`tests/test_gift_card_store.py:286`), and post-fix `:neg` is marshalled by `_marshal`, so it becomes `{"N": "-40000"}` and the bare integer comparison fails. The repair is to compare the AttributeValue form; the `^-?[0-9]+$` check in §5.6 is what owns the **integer-paise** property at that hop, so this assertion is checking the marshalling, not the money rule. It fails loudly rather than silently, which is why it is a correction to the enumeration and not a change to the fix — but §5.5's own standard is that *"the suite went green" is not evidence*, and an enumeration that is short by one is the thing that makes a green suite misleading |
| `test_a_second_redeem_..._same_transaction_id` | none | passes |
| `test_a_second_redeem_..._does_not_move_the_balance` | **update** — assert no balance move in *either* representation | a replay moves nothing |
| `test_two_different_payment_attempts_each_deduct_once` | none | passes |
| `test_the_claim_is_written_before_the_balance_moves` | **update** — compare the claim `put_item` index against the `transact_write_items` index | claim precedes money |
| `test_the_claim_row_is_settled_by_the_decrement_so_a_short_balance_is_recoverable` | none | on a short balance the transaction cancels, so the claim stays unsettled and a retry completes under the same id |
| `test_a_redemption_whose_settle_write_failed_debits_the_balance_exactly_once` | **retire and replace** | its fault target (`SET settled = :true` as a separate write) no longer exists. Replaced by `test_the_settle_and_the_balance_move_are_one_commit`, which asserts the state it protected against is now **unreachable**: there is no interleaving in which the balance has moved and the claim is unsettled. |
| `test_a_stalled_redemption_still_debits_once_when_another_purchase_lands_between` | **rewrite, same name** | same scenario driven by a *settled* claim and an intervening different purchase, which is the post-fix route to that state. The property — a stalled retry after another purchase does not double-debit — is asserted identically. |
| `test_an_applied_move_marker_does_not_outlive_the_move_it_guards` (`:513`, `:519`) | **update** | now asserts the stronger fact: no `appliedClaim#` or `appliedVoid#` attribute is **ever written**, so it cannot outlive anything. Item-size growth is bounded by construction rather than by a cleanup step. |
| `test_a_void_whose_credited_write_failed_returns_the_balance_exactly_once` (`:762`) | **retire and replace** | the void twin of the redeem row above, retired for the identical reason: its fault target — `_mark_credited` as a **separate write** — ceases to exist. Replaced by `test_the_credit_and_the_credited_flag_are_one_commit`, asserting unreachability: there is no interleaving in which the balance has returned and the transaction is uncredited. |
| `test_a_plain_credit_is_not_made_idempotent_because_two_top_ups_are_two_events` | **update — and it loses half its body, not one assertion** | see the correction below the table |
| `test_a_void_whose_credit_failed_is_completed_by_a_retry_not_refused` | **rewrite, same name** | see the `_CreditThrottles` note below |
| `test_a_void_credit_that_fails_twice_still_returns_the_balance_exactly_once` | **rewrite, same name** | same note; the fault is armed twice |
| `test_a_void_latched_before_the_credited_flag_existed_is_never_re_credited` | **none** — and revision 7's claim that it changes was a consequence of the ambiguity §5.3.1 has now resolved | `credited` **absent** must read as COMPLETE, not as pending. §5.3.1 decides that a latched row whose `credited` is not exactly `False` refuses at the **pre-read** with **no transaction opened**, which is today's behaviour at `gift_card_store.py:1441` — so this test's `pytest.raises(gc.AlreadyVoided)` and its balance assertion both hold unchanged, and the absent-flag case never reaches a transaction on this path. Revision 7 said the row "now asserts the transaction cancelling on `attribute_exists(credited)`", which would have required opening a conditional transaction purely to cancel it on every duplicate void. The condition is still written (it is the **concurrency re-check**, and §5.3.1 argues why naming `attribute_exists` explicitly is still necessary for the racing case), but this test is not what exercises it. **Re-run without edit and it must stay green** |
| `test_the_store_holds_no_boto3_client_and_reads_no_secret_itself` (`:1152`) | **none, and that is the constraint** | the module imports no `boto3`/`botocore`/`os`. This gate is why §5.3 hand-marshals instead of importing `TypeSerializer`. Listed because revision 2's design would have broken it and did not know it existed |
| `test_no_float_is_constructed_anywhere_on_the_store_money_path` (`:1066`) | **none expected; re-run and read** | it monkeypatches `builtins.float` and drives a full redeem/void cycle, so it crosses the new transaction path end to end. `_marshal` constructs no float (`str(int)` only), so it should pass — but it is *affected*, and an affected test that nobody ran is indistinguishable from an unaffected one |
| `test_every_dynamodb_access_is_an_exact_key_operation_or_the_status_index_query` (`:1094`) | **update — split across two guards; see below** | the module's only balance-moving write stays inside the one test that enumerates reach, **and** the test does not fail against correct code |

**The access-pattern gate: two guards, and which one owns which half.** Revision 4 said the gate
gains an `elif` for `transact_write_items` asserting "the rendered call contains both `TableName`
and `Key` and no `IndexName`". **That assertion fails against correct post-fix code**, which is
the identical shape to revision 4's own finding 1, and it was missed for the identical reason —
the assertion was written against the intent rather than against the text the gate actually sees.
Read from the tree, the gate renders the **call** node:

```python
elif operation in exact:
    rendered = ast.unparse(node)                     # the Call, not the enclosing function
    assert "Key=" in rendered or "Item=" in rendered
    assert "IndexName" not in rendered
```

§5.3 builds the items in separate assignments (`card_item = {...}`, `claim_item = {...}`), so the
call renders as:

```
table.meta.client.transact_write_items(TransactItems=[card_item, claim_item])
```

which contains neither `TableName` nor `Key`. The assertion goes red on code that is right, and
the natural repair — deleting the arm — leaves the module's only balance-moving write invisible to
the one test that enumerates reach. Both outcomes are worse than no change.

So the property is split, and **the split is recorded here so neither half is later deleted as
redundant**:

| Guard | Owns | Asserts | Why it owns this half |
|---|---|---|---|
| **AST**, in `test_every_dynamodb_access_is_an_exact_key_operation_or_the_status_index_query` | **presence and location** | exactly **one** `transact_write_items` call in the module; its owning `FunctionDef` is `_transact_with_retry` (§5.3); and `_transact_with_retry` is itself called from exactly two places, `_commit_redemption` and `_commit_void` (§5.3 names both). It does **not** unparse item contents. **The three facts need two different node predicates, and the gate's existing loop supplies only one — see the note below the table** | a static walk can see *that* a call exists and *where*; it cannot see values assembled elsewhere. Keeping it to presence is what makes it true of the implementation §5.3 specifies, and the "no third caller" clause is what stops a new committer opening a transaction without a design change |
| **runtime**, a helper over `table.calls`, called from the tests that actually drive a transaction | **item shape** | for every recorded `transact_write_items`: `TransactItems` is non-empty; every item's key set is exactly `{"Update"}`; every item carries a non-empty `TableName` and a non-empty `Key`; no item carries `IndexName`. **And first, before any of that: that it saw at least one transaction at all** | the contents exist at runtime. `calls` is already the attempt log this design relies on (§2.6), and it records the item list **as received**, so the assertion reads the real request rather than a rendering of the source that produced it |

**The node types, spelled out, because reusing the gate's existing loop for all three facts
produces an empty caller set.** Revision 7 said all three facts are found *"with the same
`FunctionDef`-owner walk the gate already uses for `list_by_status`"*. The owner walk **is**
reusable — read from the tree at `tests/test_gift_card_store.py:1119-1124`, it resolves a call to
its enclosing `FunctionDef` exactly as described. The **call-finding** loop is not: it filters

```python
if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
    continue
```

which finds `table.meta.client.transact_write_items(...)` and **not** `_transact_with_retry(...)`,
because the latter is an `ast.Name` call. An implementer who reuses the existing loop for facts two
and three gets an empty caller set and an assertion that fails on correct code. It fails loudly
rather than vacuously, so it is a smaller hazard than the two this guard has already produced — but
Group D spells out node types for exactly this reason, and this is the guard whose two prior forms
were both unusable, so it gets the same treatment:

* **fact one** (presence) uses the gate's existing `ast.Attribute` filter on `node.func.attr ==
  "transact_write_items"`;
* **facts two and three** need their own predicate:
  `isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id ==
  "_transact_with_retry"`;
* the **`FunctionDef`-owner walk is shared by all three** — that part of revision 7's sentence was
  right, and it is the half worth reusing.

**Where the runtime half runs, and why revision 5's answer was worse than no answer.** Revision 5
said the helper *"lives beside the gate and is called from it, so one test still reports the whole
property"*. Read from the tree, that gate drives **nothing**: its entire runtime section is

```python
    store = table()
    with pytest.raises(AssertionError):
        store.scan()
```

on a fresh empty `FakeTable` (`tests/test_gift_card_store.py:1125-1127`). No issue, no redeem, no
void, so **no `transact_write_items` is ever recorded**, the helper would iterate an empty list,
and every assertion inside it would be skipped. The test goes green, §7 reports the item shape as
runtime-covered, and the module's only balance-moving write has its shape asserted by nothing.

That is the exact mirror of the defect revision 5 fixed, in the worse direction: revision 4's
assertion failed loudly on correct code, which at least gets read; a vacuous guard passes silently
on **any** code, including code that ships a `Put` item or a money write with no `Key`. A guard
that cannot fail is already deleted, and nobody can tell.

So the helper is specified as follows, and both halves of the specification matter:

```python
def assert_transaction_items_are_exact_key_updates(store) -> int:
    """Shape-check every recorded transaction. Returns how many it saw.

    Refuses an empty recording FIRST: a shape assertion over nothing is a pass, and a
    silent pass on a money write is worse than a loud failure on a correct one.
    """
    transactions = [kwargs for name, kwargs in store.calls if name == "transact_write_items"]
    assert transactions, (
        "no transact_write_items was recorded, so this helper asserted nothing - "
        "drive a redeem or a void before calling it")
    for kwargs in transactions:
        items = kwargs["TransactItems"]
        assert items, "a transaction with no items"
        for item in items:
            assert set(item) == {"Update"}, f"only Update items are permitted, got {set(item)}"
            update = item["Update"]
            assert update.get("TableName"), "a transaction item with no TableName"
            assert update.get("Key"), "a transaction item with no Key"
            assert "IndexName" not in update, "a transaction item naming an index"
    return len(transactions)
```

and it is **called from the tests that already drive the transaction**, not from the static gate.

**The caller list is stated once, here, and it is SIX tests.** §7 and §15 cross-reference this
table rather than restating a count; revision 6 and revision 7 managed three different numbers
for the same list (§5.5's table enumerated six, §7 said "four" over an enumeration of five, §15
said "four places"), which is its own small instance of the family this document keeps repairing.

| # | Caller | Drives |
|---|---|---|
| 1 | `test_a_second_redeem_..._does_not_move_the_balance` (§5.5) | one redeem, then a replay answered by the **pre-read** (§5.3.1's decision, redeem half) and so opening **no** second transaction — **1** recorded, not 2 |
| 2 | `test_the_settle_and_the_balance_move_are_one_commit` (§5.5, replaces the retired settle-failure test) | one redeem |
| 3 | `test_the_credit_and_the_credited_flag_are_one_commit` (§5.5, replaces the retired void twin) | a redeem then a void |
| 4 | `test_a_void_whose_credit_failed_is_completed_by_a_retry_not_refused` (§5.5, rewritten) | a redeem, a void that fails, a void that succeeds, a void that refuses |
| 5 | `test_a_void_credit_that_fails_twice_still_returns_the_balance_exactly_once` (§5.5, rewritten) | a redeem, two voids that fail, a void that succeeds |
| 6 | `tests/test_gift_card_redeem_concurrency.py` (§5.4) | two concurrent redeems — the one caller whose recording includes a **cancelled** attempt |

**What each caller asserts, and why it is NOT a literal count.** Revision 6 and revision 7 said
*"the helper's return is `2`"* for callers 3, 4 and 5. Measured against the tree, that is wrong for
two of the three and would **fail against correct post-fix code**:

| Caller | Transactions actually recorded | Why |
|---|---:|---|
| 1 | **1** | one redeem; the replay is answered by the pre-read, as above |
| 2 | **1** | one redeem |
| 3 | **2** | redeem, then void |
| 4 | **3** | redeem; void armed and raising; void succeeding. The fourth `void()` call refuses at the **pre-read** (§5.3.1's decision) and opens no transaction |
| 5 | **4** | redeem; two armed-and-raising voids; one succeeding void |
| 6 | **2** | two concurrent redeems, one of which is **cancelled** and still recorded |

Two measured facts make the failed attempts count, and both are facts this design already relies
on elsewhere. `FakeTable.arm_failure` arms **once** — `self.fail_on.pop(operation, None)` at
`tests/coupon_fake_dynamo.py:246` — so the test's retry is its own second `void()` call rather than
an internal loop, and a bare `FakeClientError("ProvisionedThroughputExceededException")` is **not**
a cancellation, so `_is_transaction_cancellation` is `False` and `_transact_with_retry` re-raises
without looping. And in every operation `calls.append(...)` **precedes** `_fail_if_armed(...)`
(`:253/:255`, `:267/:268`, `:275/:280`), so an armed-and-failed transaction **is** in `calls` —
which is the attempt-log semantics §2.6 depends on and §5.4 asserts against.

So the repair is not to correct `2` to `3` and `4`. A per-test literal is the wrong instrument: it
drifts the moment a test gains a call, and the repair a later implementer reaches for under time
pressure is to delete the count — or the helper call — from the void tests, which is precisely what
this guard was added for. **Assert the property the count was standing in for:**

```python
seen = assert_transaction_items_are_exact_key_updates(store)
assert seen >= 2, "both committers must have been exercised"
assert {_committer_of(kwargs) for name, kwargs in store.calls
        if name == "transact_write_items"} == {"redeem", "void"}
```

`_committer_of` discriminates on the fragment `_is_balance_move` already reads — `ADD balancePaise
:neg` is the redeem committer, `ADD balancePaise :amount` is the void committer — so *"neither
committer is the one that is silently missing"* is asserted **directly** rather than inferred from
a total. Callers 1 and 2 drive one committer only, so they assert `seen >= 1` and a committer set of
`{"redeem"}`; callers 3, 4 and 5 assert `seen >= 2` and `{"redeem", "void"}`; caller 6 asserts
`seen >= 2` with `{"redeem"}`, which is the recording that includes the cancelled attempt. No
literal transaction total appears in any of them.

The static gate keeps **presence and location only**, which is all a static walk can honestly
own. Its existing runtime tail (`store.scan()` raising) stays exactly as it is; nothing is added
to it, because adding a money cycle to a test whose subject is the AST is how the vacuous version
came about.

Two details that keep the helper honest. It asserts against `calls` rather than `applied`, so a
transaction that was **cancelled** is still shape-checked — a malformed item that never commits is
still malformed, and the concurrency test is the caller that exercises exactly that. And the
`{"Update"}`-only assertion is what forbids a `ConditionCheck`, `Put` or `Delete` item arriving
later without a design change, which is the same discipline the `exact` set applies to the
single-item operations.

**Where the helper itself lives:** `tests/test_gift_card_store.py`, beside the other module-level
test helpers (`table`, `issue`, `clock`, `digest_of`, `_markers_on`), and imported by
`tests/test_gift_card_redeem_concurrency.py`. One definition, four callers. A reader looking for
the property finds it named in §7 with its callers listed, which is the legibility revision 5 was
reaching for by putting it in the gate.

**Correction: the plain-credit test loses half its body, and the design's stated edit was not the
edit.** Revision 2 said "only the `_markers_on(...) == []` assertion goes". Read from the tree,
`test_a_plain_credit_is_not_made_idempotent_because_two_top_ups_are_two_events` has **two
halves**, and the second one is five lines that call `credit(..., once_key="void-abc")` twice and
assert the balance moved once. With `once_key` removed those are a `TypeError`, not a stale
assertion. So the real edit is: **the marker assertion and the whole `once_key` half are
deleted**, the test keeps only the plain-credit half, and its name is unchanged.

That leaves a real property homeless, and it has to be rehoused rather than dropped: *the same
logical credit replayed moves the balance once*. It moves from `credit()` to `void()`, which is
correct — `void` is the only caller that ever had a replayable credit — and it is asserted by
`test_the_credit_and_the_credited_flag_are_one_commit`, which must additionally assert that a
**second `void()` of the same transaction credits nothing**. The property changes owner; it does
not disappear.

**The two `_CreditThrottles` void tests break silently, and they are property tests rather than
mechanism tests.** Both inject their fault through `_CreditThrottles`, which overrides
`update_item` and fires only when the expression contains `"ADD balancePaise :amount"` — the
`credit()` call the conversion **removes** from the void path. Post-fix the throttle never fires,
`gc.void(...)` simply succeeds, and the `pytest.raises(gc.GiftCardStoreUnavailable)` in each test
fails. Neither was in revision 2's enumeration, and the first one's own docstring says it "closes
the void path's counterpart of the claim window" — so losing it quietly is precisely what §5.5
exists to prevent.

The rewrite aims the fault at the transaction instead, keeping each name and each property:

| Test | New fault injection | Property preserved verbatim |
|---|---|---|
| `test_a_void_whose_credit_failed_is_completed_by_a_retry_not_refused` | `arm_failure("transact_write_items", FakeClientError("ProvisionedThroughputExceededException"))` | a transient failure **between** the `voidedBy` latch and the money move is **recoverable**: the retry completes under the same void id, the balance returns **exactly once**, and a third call refuses again rather than leaving the void permanently re-drivable |
| `test_a_void_credit_that_fails_twice_still_returns_the_balance_exactly_once` | the same, armed **twice** | recovery that works once is not recovery; the latch is not consumed by a failed attempt |

Note that the throttle must raise something the module converts to
`GiftCardStoreUnavailable` rather than to a conditional failure — the existing class raises a
plain `RuntimeError` for exactly that reason, and a `FakeClientError` carrying a throughput code
has the same effect through `_is_transaction_cancellation` returning `False`. Keeping both tests'
*answers* identical to today's is the check that the rewrite preserved the property rather than
replacing it.

**Why `:762` and the plain-credit test are listed at all.** `gc.APPLIED_CLAIM_PREFIX` / `gc.APPLIED_VOID_PREFIX`
are referenced at five sites owned by four tests (`:453-454`, `:513`, `:519`, `:762`, `:793`),
measured by grep at `32b632e3`. The first draft covered two of the four. Removing the constants
makes the other two fail with `AttributeError` rather than with a readable assertion — the failure
mode most likely to be cleared by deleting the line, which is how a property silently stops being
tested.

Retiring a test is the step most likely to be mistaken for making the build green, so it is
called out once more: the retired test described a window created by a two-write sequence. The
two writes are now one commit. A test asserting that a non-existent second write fails cleanly
would assert nothing, and it is replaced by one asserting unreachability.

**Every file that consumes `gift_card_store` *or* `coupon_fake_dynamo` must be re-run and
triaged**, measured by grep at `32b632e3`. The second half of that list was missing from revision
2: `tests/coupon_fake_dynamo.py` is imported by **seven** test files, and it is gaining a lock, a
new operation, a new constructor keyword and two new attributes — so the three coupon files that
§8 lists as "read-only, not edited" are read-only in the *edit* sense and not in the *risk* sense:

| File | What it consumes | Expected impact |
|---|---|---|
| `tests/test_gift_card_two_leg_finalization.py` | 52 matching lines on `redeem(` / `settled` / the markers | the heaviest consumer. Most assertions are behavioural (split, identity, two-leg totals) and should pass untouched; any that reach for `update_item` with `ADD balancePaise` need the §5.5 treatment |
| `tests/test_gift_card_spi_contract.py` | 3 | behavioural; expect no change |
| `tests/test_gift_card_amounts_and_gst.py` | 2 | arithmetic only; expect no change |
| `tests/test_gift_cards_iam_and_table.py` | — | see the IAM note below |
| `tests/test_coupon_store.py` | `coupon_fake_dynamo` only | **none expected**: the `RLock` is inert for a single-threaded caller, `applied` is additive, and `name` is defaulted. Re-run anyway — "low risk" is a measurement, and this document's standard is to make it |
| `tests/test_coupon_reconciliation.py` | `coupon_fake_dynamo` only | as above |
| `tests/test_wix_coupons_contract.py` | `coupon_fake_dynamo` only | as above |

A surprise in the last three is therefore a **defect in the fake**, not a shrug — which is the
only reason to list them.

The rule applied to each: if the assertion is about **behaviour**, it must pass unchanged, and a
failure is a defect in the fix rather than a test to update. Only assertions that name the
**mechanism** (a specific `update_item`, a specific expression fragment) may be rewritten, and
each rewrite must preserve the property in the same breath.

**No IAM change is needed, and this is worth stating because the instinct is to add one.**
`TransactWriteItems` is authorized through the actions of its items, not through a distinct
action: two `Update` items need `dynamodb:UpdateItem`, which
`scripts/provision_gift_cards_roles.py` already grants on both roles (the `GiftCardLedger`
statement on the own role, `GiftCardLedgerNoDelete` on the SPI).
`dynamodb:ConditionCheckItem` is required only for a `ConditionCheck` item and this transaction
has none. So no provisioner is edited, on AWS semantics alone.

The first draft justified this differently and the justification was wrong: it claimed adding a
`dynamodb:TransactWriteItems` action would break `tests/test_gift_cards_iam_and_table.py:295`,
"which asserts the SPI statement's actions are exactly `["dynamodb:UpdateItem"]`". Read from the
tree, that assertion (at `:293`) covers the `AdvanceGiftCardStageOnAPaymentAttempt` statement on
**PaymentAttemptsTable**, not the gift-card ledger. The ledger statements are **not** pinned to an
exact action list by any test, so the guard named there does not exist and a widened ledger grant
would land silently. Since the pin is cheap and the module now has a documented minimum action
set, one assertion is added to that file: the `GiftCardLedger` and `GiftCardLedgerNoDelete`
statements' action sets are exactly what the store needs, so a future widening has to be
deliberate.

### 5.6 Money rules re-checked against the change

| Rule | Where it holds in the new code |
|---|---|
| integer paise everywhere | `:neg = -amount`, `:amount = amount`, both from `value_paise()`, which refuses floats, bools and fractional `Decimal`s by type |
| **integers survive the serialisation hop** | the one boundary where paise stop being a Python `int`: `_marshal` (§5.3) renders them as `{"N": str(int)}` — a decimal string on the wire — and refuses a `float`, a `Decimal` and a `bool` by `type(value) is int`, which is **stricter** than `TypeSerializer`, and is pinned byte-for-byte against it by a test in `tests/`. Read-back is `int(value["N"])`: never `float(...)`, never a `Decimal` that is then divided. Made executable rather than asserted: the harness checks every `"N"` in a recorded transaction matches `^-?[0-9]+$`, so a stray `.` fails the test at the exact hop where it could appear |
| no float arithmetic **on an amount** | the transaction carries ints; the post-commit read goes through `int(...)` on a DynamoDB `Decimal`; **nothing divides an amount**. The qualifier is load-bearing and is not a softening — see the row below, and the note after this table for why the unqualified version was wrong |
| **a retry delay is a duration, not an amount** | `_transact_with_retry` computes `0.05 * 2 ** n + _secrets.randbelow(25) / 1000` (§5.3), which **is** float arithmetic — `0.05` is a float literal and `int / int` is true division — and is deliberately **permitted**: it is a number of seconds passed to `sleep`, never stored, never compared for equality, never reaching an amount, and never crossing the `_marshal` boundary. The no-float rule in this repository is about **amounts**, because its reason is that a one-paise mismatch must fail closed. `test_no_float_is_constructed_anywhere_on_the_store_money_path` (`:1066`) stays green for a mechanical reason worth knowing rather than assuming: it monkeypatches `builtins.float`, and neither a float **literal** nor `int.__truediv__` calls `builtins.float` |
| `Decimal(str(value))` | only needed where a DynamoDB number re-enters arithmetic; the balance is read as `int(card.get("balancePaise") or 0)`, and a fractional stored value is a data error that `coupons/handler.py::_plain` already refuses rather than truncates — the gift-card handler follows the same shape |
| currency compared explicitly | unchanged: `assert_currency` compares against `CURRENCY == "INR"` and never infers from an amount |
| resolve-before-generate | strengthened: the claim row is still the resolve anchor, and `transactionId` is now re-used from the existing claim in *every* path that reaches the money, not merely in the settled one |
| bearer value never logged | unchanged: every log line carries `giftCardId`, `paymentAttemptId` and `masked(codeLast4)`; `masked()` still raises `CODE_IN_LOG` if handed more than four characters |
| coupon code may be logged | unchanged |
| payment vocabulary | this module makes no payment-state decision and imports no payment word; `'captured'` does not appear. `tests/test_payment_vocabulary_at_decision_points.py` stays green with no edit |

**Why the qualifier was added, stated rather than slipped in.** Revision 7's row read *"nothing
divides"*, unqualified, in the one section whose entire job is to re-check the money rules **against
this change** — while §5.3 of the same revision introduced `_secrets.randbelow(25) / 1000` into
`gift_card_store.py`. In a repository whose standing rule is that no float may appear on the payment
path and that a one-paise mismatch must fail closed, an unscoped certification is a sentence a later
reviewer or implementer will act on, and the action it invites is either a wrong "this change
violates the money rule" rejection or a wrong "floats are fine here" generalisation. Neither is
recoverable from the sentence itself.

Nothing goes red and no amount is involved, which is why this is a documentation defect rather than
a code one: the `builtins.float` gate at `:1066` is a runtime monkeypatch that a float literal does
not trip, and there is **no AST float gate over `gift_card_store.py`** — measured; the AST
assertion this design specifies covers the demo script (§4.5) and the `wix_gift_cards.py` adapter,
neither of which sleeps.

**The alternative was considered and rejected, so the choice is on the record.** The module could be
kept literally float-free by computing the delay in integer milliseconds and dividing only inside
the call argument — `sleep((50 * 2 ** n + _secrets.randbelow(25)) / 1000)`. That still divides; it
only moves the division to the last expression, which buys a true statement about the module at the
cost of a less readable one about the delay. Scoping the rule to **amounts** is the honest version,
because that is what the rule is actually for, and a rule stated more broadly than its reason is a
rule that gets argued with instead of followed.

---

## 6. Owner actions

Nothing in this section is performed by the agent. Live Wix writes, deploys and provisioning are
all standing refusals here; these are the numbered steps an owner takes, with the evidence each
one needs.

### 6.1 The decision memo — `wix-native-decision-memo.md`

Required by verdict (B) for coupons. Short, one page, no new analysis — it restates §1 for a
reader who will not open this document:

1. **Coupons: Wix-only is not available.** `Create Coupon` has no idempotency key and no
   read-by-code, so a create whose response is lost leaves a live Wix coupon whose id we cannot
   recover. Our table supplies that recovery. Wix already does all discount arithmetic, so the
   part the owner cares about is already Wix's.
2. **Gift cards: Wix-native is a real GA option and is probably better than ours** — it carries a
   server-side `idempotencyKey`, it is queryable by full code, its amounts are exact decimal
   strings rather than JSON numbers, and `balance` is `readOnly` so we could not corrupt it.
   **The blocker is cleared: the owner confirmed on 2026-10-02 that the Wix Gift Card app is
   installed**, so gift cards are **(A)** and Wix-native is the direction.
3. **What still has to be true before we delete our backend** — the three-condition §0.1 gate, of
   which only the first is satisfied. The honest sentence for the memo: *a dashboard glance proves
   the product exists; it does not prove the API accepts our key, our shape and our fractional-INR
   amounts on this site, and that is one owner-run call away (§6.2).*
4. **What retirement removes**, §6.4, so the size of the decision is visible before it is taken —
   including that there is nothing to delete in AWS, because none of it was ever deployed.
5. **What is already true in both branches**: Wix does the arithmetic; we never return a discount
   figure to a browser.
6. **Loyalty and Referral are noted and out of scope** (§1.5), so the memo answers the question
   before it is asked rather than leaving the owner to assume they were included.

### 6.2 The live verification — option 1 is already done; option 2 is now the retirement gate

**Option 1 — dashboard, 30 seconds, no credential. ✅ DONE, 2026-10-02.** Wix dashboard →
**Apps → Installed Apps** → **Wix Gift Card** is present, confirmed by the owner, which settled
the §1.2.2 verdict to (A). Still worth noting from the same screen whether the site is on a
premium plan, since Wix's introduction states *"Email delivery features require a premium site
plan"* — that is not needed for the verdict, and it is not needed for this design either, because
§2.5 sends no `notificationInfo`. It is needed only before anyone relies on **Wix emailing a
card**. Revision 5 downgraded this from a named error to a documented prerequisite: §3.0.1
establishes the markdown source renders no error set for any method, so `SITE_IS_NOT_PREMIUM` is
not re-verifiable from here and must not be relied on as a machine-observable signal.

**Option 2 — one owner-run read. Still open, and its role has changed.** It is no longer a check
on the verdict; it is **condition 3 of the §0.1 retirement gate**, because it is the only step
that tests what the dashboard cannot: that *our key* is accepted with *our shape* on *this* site.
A `count`, not a `create`, so it cannot write to the live store:

```
POST https://www.wixapis.com/gift-cards/v1/gift-cards/count
  Authorization: {{resolve:secretsmanager:wecare/wix/headless-api-key:SecretString:apiKey}}
  Content-Type: application/json
  wix-site-id: fcd82f0c-9572-49c7-acfb-88fb05042ece
  {}
```

**The block above is the form to copy, token included** — identical in shape to §6.5 Route A, so
there is no version of this request anywhere in the document that invites pasting a value into an
`Authorization` line. The key lives in Secrets Manager at **`wecare/wix/headless-api-key`**, field
**`apiKey`** (that field name is read from `wix_ecom._api_key`, which tries `apiKey`, then
`value`, then `key`). Per `.kiro/steering/aws-agent-rules.md` the `{{resolve:secretsmanager:...}}`
token is resolved by **`asm-exec`**, so the value never enters a shell command, argv, a log, or
this document. A literal `-H 'Authorization: rzp_…'`-shaped command is what wrote four live
credentials into a permissions file on 2026-09-19, and
`.kiro/hooks/block-inline-secrets.json` blocks that shape.

**Where `asm-exec` comes from, because it is not on `PATH` here — and the exact invocation,
because "a tool that understands it" is not an instruction.** Revision 3 closed this step with
*"either run it through the MCP tool surface, or paste the resolve token into a tool that
understands it"*. That is the one kind of vagueness this checklist cannot afford: the
improvisation it invites happens at a credential boundary, and the failure mode is a live key on
a command line — the exact mechanism that wrote four credentials into a permissions file on
2026-09-19.

Re-measured 2026-10-02: `command -v asm-exec` is empty, so the name is genuinely unavailable, but
**the program exists as a local script** and is what the Razorpay MCP server already wraps itself
in:

```
/Users/wecaredigital/.local/share/razorpay-mcp-server/asm-exec-env.py     mode 0700
```

Its own header documents the contract — *"asm-exec: Resolve `{{resolve:secretsmanager:...}}`
references and run the command. Usage: `asm-exec <command> [args...]`. Resolves dynamic
references in arguments and exported environment variables, then runs the command. Secret values
never return to the calling agent."* — and it accepts an optional `--` separator before the
command, which is how `~/.kiro/settings/mcp.json` invokes it. So the whole step is one command:

```
python3 ~/.local/share/razorpay-mcp-server/asm-exec-env.py -- \
  curl -sS -o /dev/null -w '%{http_code}\n' -X POST \
    https://www.wixapis.com/gift-cards/v1/gift-cards/count \
    -H 'Authorization: {{resolve:secretsmanager:wecare/wix/headless-api-key:SecretString:apiKey}}' \
    -H 'Content-Type: application/json' \
    -H 'wix-site-id: fcd82f0c-9572-49c7-acfb-88fb05042ece' \
    -d '{}'
```

Three properties of that command, each deliberate: the token is a **reference** and
`.kiro/hooks/block-inline-secrets.json` allows exactly this by-reference form; the resolution
happens inside a child process, so the value never enters argv the agent can see, a log, or this
document; and `-o /dev/null -w '%{http_code}'` prints the status and discards the body, so a
response that happens to echo anything cannot land in a terminal transcript. Drop
`-o /dev/null -w` only if the count itself is needed, and read it off the terminal rather than
pasting it anywhere.

**If that invocation does not work, use Option 1 and stop. Do not substitute the value.** Option 1
needs no credential at all and already settled the verdict; the only thing lost is condition 3's
reachability check, which is better deferred than obtained by putting a key on a command line.

Reading it: a `200` with a numeric count means the API is live on this site **and our key reaches
it** → condition 3's first half is satisfied. A `403`-class refusal means the key lacks the Wix
scope, which is a **third answer and not a negative one** — the product is installed either way,
and the unblock is a scope grant rather than a change of direction (§6.5 item 1 is the same gap
for coupons, **though the two scopes are different and the gift-card one is broad**: measured
2026-10-02, coupons need `SCOPE.DC-COUPONS.MANAGE-COUPONS` and gift cards need
`SCOPE.DC-ECOM-MEGA.MANAGE-ECOM` — *"Manage eCommerce - all permissions"* — so a single key
carrying both is carrying more than gift cards alone would require. A premium-plan refusal, if one
is surfaced, would mean **email delivery** is unavailable, not that the API is; this design sends
no `notificationInfo`, so it does not depend on a premium plan.

**Then the second half of condition 3, which the `count` does not cover.** A count of zero proves
reachability and nothing about behaviour. One sample card, owner-run, exercises the three
properties the whole (A) decision rests on:

| Step | Call | What it proves |
|---|---|---|
| a | `POST /gift-cards/v1/gift-cards` with a `code`, `initialValue.amount: "2500.50"`, `currency: "INR"`, **`source: "MANUAL"`** (required — §3.3) and an `idempotencyKey` | that a **fractional INR** amount and a custom code are accepted on this site, and that the response carries the full clear code exactly once |
| b | the **same** request again, same `idempotencyKey` | that Wix's server-side idempotency actually returns the same card rather than creating a second one. This is the property that makes (A) better than (B) and it is currently taken on the documentation's word |
| c | `POST /gift-cards/v1/gift-cards/query` with `{"query": {"filter": {"code": {"$eq": "<full code>"}}}}` — a real JSON object, not a double-encoded string | that read-by-full-code works, and that the response carries **`codeSuffix`** and **`balance.amount`**. Read those two, and record **what Wix actually returns in `code`** for a 16-character unhyphenated custom code — the only documented obfuscation example is hyphen-grouped (`****-****-****-4444`), so our shape's rendering is genuinely unmeasured. **Nothing depends on the answer**, because §2.5 reads `codeSuffix` and never parses `code`; record it so the next reader does not have to wonder, and so a missing `codeSuffix` would surface here rather than in the first wired call |

Step (a) is a **live Wix write**, so it is owner-only and I will not perform it. Keep the returned
card id, and treat the clear code from step (a) as bearer value: it is the one place the full code
exists, so it must not be pasted into a ticket, a chat, this repo, or a log.

**If any step fails or differs from the documented shape, the retirement stops and is reported**,
per the owner's instruction. A differing response shape is not a small thing here: it is the
difference between our adapter being correct and our adapter being correct *about the
documentation*.

### 6.3 If the live verification fails — keep the SPI, and finish it properly

No deletion. The §5 fix is then not conditional at all: it lands as designed, because our store
stays the authority for bearer value. This branch is now the unlikely one, but it is the reason
§5 is still fully specified rather than shortened to a note.

### 6.4 The retirement inventory — what (A) removes, once the §0.1 gate clears

Listed so the owner can size the decision. **The removal is not designed in this document**, on
purpose, and revision 3 does not change that: the verdict being settled is not the same as the
contract being verified, and authoring a deletion of a stored-value backend in the same commit
that first demonstrates its replacement is how a latent money bug gets "retired" without ever
being understood. Source only; no live resource is touched by authoring.

| Kind | Items |
|---|---|
| shared module | `lambda_utils/ecommerce/gift_card_store.py` (1,513 lines), and `gift_card_settlement` if it has no other caller |
| functions | `amplify/functions/ecommerce/gift-cards/handler.py`, `amplify/functions/ecommerce/wix-giftcard-spi/handler.py` |
| deploy registry | the `wecare-gift-cards` and `wecare-wix-giftcard-spi` entries in `scripts/deploy_all_lambdas.py` (lines ~230 and ~241) |
| provisioners | `scripts/provision_gift_cards_table.py`, `provision_gift_cards_roles.py`, `provision_gift_card_routes.py` |
| tests | `tests/test_gift_card_store.py`, the gift-card half of `tests/test_payment_vocabulary_at_decision_points.py`'s `RAW_SCAN_ONLY_FILES`, and the `wix_spi_*_jwt_payload.json` / `wix_cart_v2_gift_card_partial.json` fixtures |
| live resources | **none exist.** Re-derived 2026-10-02 (§0.1): no `wecare-gift-cards`, no `wecare-wix-giftcard-spi`, no `GiftCardsTable`, no matching routes, no `giftcard` secret. So the retirement is a **source-only** change with nothing to delete in the account and no pointwise AWS confirmation to collect. Re-derive before the change lands rather than trusting this row |

**Two line items the wiring change inherits from this one, and the second is the larger of the
two.**

**(a) The recording rule.** Offline, every gift-card code is a fixture placeholder, which is why
§2.3 permits `WixTransport` to record request bodies verbatim. The moment the adapter is wired to
a live Wix response that stops being true: a real `CreateGiftCardResponse` carries a real clear
code, so the transcript and logging rules must be **re-derived against a real code** before the
first live call — capture-time redaction of the body, or no recording of it at all. It is listed
here rather than assumed, because inheriting a "recording is harmless" conclusion from an offline
harness is exactly how bearer value ends up in a log.

**(b) Where `card_code`'s return value may travel — which this design cannot constrain, and must
therefore hand over explicitly.** §2.5 guarantees that `wix_gift_cards` has nothing to log with
(Group D pins no `logger`, no `logging`, no `print(`) and that `create` never returns a clear code
to its caller. Both are true, and both are statements about the **module**. But the production
clear code will not come from a Wix response at all — `create` discards it — it will come from
**the caller calling `card_code` itself**, because the caller is the thing that holds the pepper.
So the entire lifetime of the real bearer value sits in code this design does not author.

The wiring change must therefore state, in its own document and enforced by its own tests, that
`card_code`'s return value:

* **never reaches a log line**, at any level, in any spelling, including as a fragment of an
  f-string that is later logged. The repository's CodeQL rule
  (`py/clear-text-logging-sensitive-data`) tracks taint across function boundaries and has already
  failed this build twice on a value reduced to a boolean, so "it only logs whether a code exists"
  is not a defence;
* **never reaches an exception message.** Log `type(exc).__name__`; construct a message only from
  parts that never touched the code;
* **never appears in a response to anyone but the card's intended holder** — not in a staff view,
  not in an admin listing, not in a reconciliation report. `codeLast4` is what those surfaces get,
  which is why `create` returns it;
* **is never persisted in clear.** If a derived value must be stored, store `code_hash`'s HMAC,
  which is the discipline `gift_card_store` already follows.

Listed here because `wix_gift_cards`' guarantee stops at its own boundary, and a guarantee that
stops where the value starts travelling is the kind that reads as stronger than it is.

**The order of operations, because getting it wrong is the only way this goes badly.** Wire the
Wix-native adapter into the gift-card path **before** deleting our store, not after, and let the
two coexist in source for exactly one change: a retirement that lands first leaves the product
with no gift cards at all if the replacement then fails its first real call. With nothing
deployed (above) that window is theoretical today, which is precisely why the sequence should be
established now while it is cheap.

And the consequence that must be recorded explicitly, in these words, per §5.0: under (A) the §5
double-debit defect is **retired by deletion, not fixed** — and **it never reached a customer**,
because nothing was ever deployed. Both halves belong in the final report. The first stops anyone
reading a closed finding as a patched production bug; the second stops them reading it as a
shipped one.

### 6.5 ONE real sample coupon in live Wix

Two routes. **Neither is performed here.**

**Route A — one owner-run API call, no deploy.** Yes, this is possible, and it is the cheaper
answer:

```
POST https://www.wixapis.com/stores/v2/coupons
  Authorization: {{resolve:secretsmanager:wecare/wix/headless-api-key:SecretString:apiKey}}
  Content-Type: application/json
  Accept: application/json
  wix-site-id: fcd82f0c-9572-49c7-acfb-88fb05042ece

  {"specification": {
     "name": "Sample ten percent off",
     "code": "WDSAMPLE10",
     "startTime": "1727740800000",
     "percentOffRate": 10,
     "minimumSubtotal": 5000,
     "usageLimit": 10,
     "limitPerCustomer": 1,
     "limitedToOneItem": false}}
```

via `asm-exec` so the key is never inline — and see §6.2 for where `asm-exec` comes from, since
it is not on `PATH` in this workspace.

**How this body relates to the demo's, precisely, because "copy what the demo prints" is only
true up to one field.** The demo's coupon leg issues a **money-off** coupon
(`moneyOffAmount`, §4.4), because that is the discount kind that exercises the paise-to-whole-
rupee conversion. The owner's sample above is **percent-off**, so that the code `WDSAMPLE10`
means what it says. Everything else — the URL, the four headers, the `specification` wrapper,
`startTime` as an int64 **string**, the absence of a `type` field, `minimumSubtotal`,
`usageLimit`, `limitPerCustomer`, `limitedToOneItem` — is identical, and
`tests/test_wix_coupon_giftcard_sample.py` Group A asserts **both** discount kinds byte-exactly
(§2.4), so this payload is an asserted shape and not a retyped one.

Three things to know before running it:

1. **It needs the Wix-side scope `COUPONS.MANAGE` ("Manage Coupons").** The current key's scopes
   are not recorded anywhere in this repo — this was already owner action 2 in the prior design
   and is still open. Without it the call fails at Wix and nothing is created, which is the
   fail-closed direction.
2. **It creates a coupon Wix knows about and our table does not.** That is the one state
   `WIX_CODE_CONFLICT` exists for, and §5.3.1 of the prior design establishes it is reachable
   *only* this way. `WDSAMPLE10` is reserved for exactly this, so when the backend is later
   deployed the reconciling step is: create the row with the same code, then
   `coupon_store.mark_mirrored(table, "WDSAMPLE10", <id from this response>)`. Record the returned
   `id` — it is the only handle, and §1.3 is the reason it cannot be looked up again.
3. Keep the response. `{"id": "..."}` is all Wix returns.

**Route B — through our own function.** Numbered, in order, exactly as
`lambda-snapstart-deploy.md` requires:

```
1  python scripts/provision_coupons_table.py              # dry run, no flag needed
2  python scripts/provision_coupons_role.py
3  python scripts/provision_coupons_routes.py
4  python scripts/provision_coupons_table.py   --apply     # table + status-index, PITR on, TTL off
5  python scripts/provision_coupons_role.py    --apply     # wecare-coupons-role
6  python scripts/provision_coupons_routes.py  --apply     # the seven routes
7  python scripts/deploy_all_lambdas.py wecare-coupons
8  python scripts/provision_live_alias.py --apply          # creates the `live` alias
9  python scripts/snapstart_publish.py wecare-coupons      # publish + move the alias
10 POST /coupons  as staff (Operator role), body = the spec above in our own field names
```

Notes that change the outcome:

* Steps 1-3 are **genuine dry runs**. Each script's `--apply` help text reads *"without it this is
  a dry run"*, and the no-flag branch prints `dry run: nothing changed` and returns 0. No
  `--dry-run` flag exists and none should be added.
* The alias must exist **before** step 9: `snapstart_publish.py` discovers targets by looking for
  the `live` alias, so publishing first silently does nothing. Step 7 already calls the publisher
  at the end, so step 9 is only needed for a hand deploy.
* **Does the deployed function's token suffice? Yes, on the AWS side.**
  `scripts/provision_coupons_role.py` already grants `secretsmanager:GetSecretValue` on
  `arn:aws:secretsmanager:us-east-1:<account>:secret:wecare/wix/headless-api-key-*` under the Sid
  `ReadWixApiKey` (line 118), plus the table and index, plus its own log group. So the Lambda can
  read the key by reference at request time. **The open question is the Wix-side scope**, item 1
  above — identical for both routes, because both use the same key.
* Route B's advantage is that the coupon exists in both systems from the start, so there is no
  reconciling step and no `WIX_CODE_CONFLICT`-adjacent state. Route A's advantage is that it
  needs no deploy.
* **Re-measured 2026-10-02 for revision 3, 0 errors:** `wecare-coupons`, `wecare-gift-cards` and
  `wecare-wix-giftcard-spi` all return `ResourceNotFoundException` from
  `get-function-configuration` and do not appear in `list-functions`;
  `stack-wecare-digital-CouponsTable` **and** `stack-wecare-digital-GiftCardsTable` both return
  `ResourceNotFoundException` from `describe-table`; a route scan of API `zllr9lrg7j` for
  `coupon`/`gift` is empty; no secret matches `giftcard`. Read as: **none of this is deployed
  yet**, so Route B is the full 10 steps and not an increment — and, for gift cards, it is why
  §0.1 can say the retirement strands no bearer value. Still a dated snapshot; re-derive it, per
  `00-current-owner-overrides.md`.

### 6.6 Coupon table narrowing — now a documented capability, still a follow-up

**Revision 5 changed this section's standing.** It used to be a probe into whether an
*undocumented* `code` filter happened to work. §3.4 measured that the filter **is documented**:
`specification.code` with `$eq,$ne,$hasSome,$contains,$startsWith`. So the question is no longer
*does this exist* but *does it behave well enough for a reconciliation path to depend on it*, and
the field name in the old command was wrong.

One owner-run read, no write — note **`specification.code`**, and note the filter is a JSON
document carried inside a **string**, which is how Wix's own `sort` example is encoded:

```
POST https://www.wixapis.com/stores/v2/coupons/query
  {"query": {"filter": "{\"specification.code\": \"WDSAMPLE10\"}"}}
```

What each outcome means, which is not symmetric:

* **Returns the one coupon** → the documented filter works as documented. Our row *could* shrink
  toward a `code → wixCouponId` claim ledger with a thinner mirror-state machine, because a lost
  `wixCouponId` becomes recoverable by query rather than only by our own row.
* **Returns everything, or nothing** → the filter is honoured differently from its documentation,
  and the current row shape is required exactly as designed. This is the outcome to expect if the
  double-encoding is wrong, so distinguish *filter ignored* from *filter rejected* by also
  sending a deliberately non-matching code and checking the counts differ.

**It stays a follow-up rather than entering this change**, for two reasons: it is a schema change
to a table this task does not otherwise touch, and `$hasSome`/`$contains` semantics on a
double-encoded filter is exactly the kind of thing to verify live before a money-adjacent
reconciliation path depends on it. Either way a table of ours remains (§1.3.1), so this changes
the size of the answer and not the answer.

---

## 7. Testability

| Concern | Level | How |
|---|---|---|
| Wix request composition (method, URL, headers, body bytes, JSON types) | unit, offline | `WixTransport` over the real `_request`; §2.4 Groups A and C |
| Wix response handling incl. the `json.loads` float hazard | unit, offline | real fixtures through the real parser, including the new float-amount fixture; §2.4 Group B |
| Wix failure handling for every status | unit, offline | `expect_http_error`; the 409 cases pin non-special-casing at both levels |
| the claim → create → `mark_mirrored` composition | unit, offline | `handler._create` driven directly, with only `_staff` and `_coupons_table` stubbed; §2.4 Group B |
| no credential, no AWS | unit, offline | `wix_ecom._secrets is None` under a `sys.modules["boto3"]` sabotage. **Not** `"boto3" not in sys.modules` — §2.2 explains why that is unsound here |
| coupon issuance, holds, counters, verdicts | unit, offline | existing `tests/test_coupon_store.py` — unchanged |
| gift-card concurrency | unit, offline, **threaded** | §5.4; deterministic via three events plus two bounded joins, in a `FakeTable` subclass latching on balance **moves**, so the same mechanism works pre- and post-fix. No `sleep`. Both the attempt count (`calls`) and the applied count (`applied`) are asserted, which is what makes the test discriminate pre-fix from post-fix |
| transaction semantics | unit, offline | `FakeTable.transact_write_items` deserializes the AttributeValue shape, evaluates all conditions before applying any update, and holds the table `RLock` for the whole operation |
| the transaction-conflict retry | unit, offline | `arm_failure` with a `TransactionConflict` cancellation reason, driven through `redeem(..., sleep=lambda _s: None)` and `void(..., sleep=lambda _s: None)` — the defaulted keyword-only parameter §5.3 adds to both; both the retry-then-succeed and the exhaustion path, and the exhaustion case asserts `GiftCardStoreUnavailable` **and** that the balance did not move, which is why the test drives the public function rather than `_transact_with_retry` |
| integer paise at the serialisation boundary | unit, offline | every `"N"` in a recorded transaction matches `^-?[0-9]+$` |
| `_marshal` really is boto3's AttributeValue form | unit, offline | byte-identity against `TypeSerializer().serialize` over the exact value set, asserted from `tests/` so the module keeps its no-`boto3` guarantee (§5.3) |
| the void path's three-valued `credited` | unit, offline | §5.3.1: `False` re-drives, `True` refuses, **absent** refuses without crediting — the last one is the legacy row that would otherwise be permanently un-voidable |
| gift-card identifiers are deterministic | unit, offline | `idempotency_key` / `card_code` / `demo_code` called twice per `reference_id`; different references differ; neither reads a clock (§2.4 Group C) |
| **the gift-card code is keyed, and is not recoverable from a log** | unit, offline + static | `card_code` differs under two peppers; its **case-normalised digest body** does not appear in `idempotency_key(reference_id)`'s in either direction, **and `demo_code`'s does** — the positive line is what makes the negative one capable of failing, and the whole-string form revision 7 specified was true of keyed and unkeyed code alike (§2.4 Group C states the computation); the domain-separation test **recomputes the tagged HMAC**, so what it pins is the presence of `CODE_DOMAIN_TAG` rather than an opaque digest comparison; the code is 20 characters, Wix's maximum, so the HMAC margin is 64 bits rather than 48; it refuses an empty or `None` pepper with `.code == "A_PEPPER_IS_REQUIRED"` and zero recorded requests; and Group D asserts `pepper` is keyword-only with no default, so the defect cannot be reintroduced by a "simplifying" edit |
| `demo_code` cannot reach production | static, AST | an AST walk over every `.py` under `amplify/` asserts the name appears in no `Attribute`, `Name` or `ImportFrom`. **Those three node types, not a text search and not `FunctionDef.name`** — `wix_gift_cards.py` is under `amplify/` and defines the function, so a grep fails on the defining module (§2.4 Group D states why). The demo and the harness may reference it, and both do |
| `find_by_code`'s three branches | unit, offline | a miss returns `{}` and lets exactly one create through; a two-entry response raises `.code == "AMBIGUOUS_CODE"` with zero further requests; a `disabledDate`-bearing response resolves with `disabled: True` and no create (§2.4 Group C) |
| `codeLast4` is Wix's `codeSuffix`, never a parse of the code | unit, offline | the create and query fixtures both carry `codeSuffix`; a fixture with it removed must raise `WixGiftCardError("CODE_SUFFIX_MISSING")` rather than slicing `code` |
| the create body is exactly the specified dict | unit, offline | whole-body comparison (§2.4 Group C), including `source: "MANUAL"` present and `code`/`expirationDate` **absent** rather than `null` on the omitting variant |
| the access pattern still enumerates every reach | static **and** runtime, **in different tests** | the two-guard split in §5.5. **AST**, in the access-pattern gate: exactly one `transact_write_items`, owned by `_transact_with_retry`, called from exactly `_commit_redemption` and `_commit_void`. **Runtime**, `assert_transaction_items_are_exact_key_updates(store)`: item shape, called from the **six** transaction-driving tests §5.5 enumerates in one place (two redeem, three void, plus the concurrency test — §5.5's numbered table is the single source for that list and this row does not restate the count independently of it). Each caller asserts `seen >= 1` or `seen >= 2` **plus the set of committers exercised**, not a literal transaction total: the literal was wrong for two of the void callers, which record 3 and 4, and a total is in any case a proxy for the property *neither committer is the silently missing one*, which the committer set asserts directly. The helper refuses an empty recording, so "no transaction was recorded" is a failure rather than a pass — revision 5 sited it in the gate, which drives nothing, and it would have passed vacuously. Written down so neither half is later deleted as redundant |
| **a transaction is shape-checked even when it was cancelled** | unit, offline, threaded | the helper reads `calls` (the attempt log) and not `applied` (the outcome log), and §5.4's concurrency test is the caller that records a cancelled attempt |
| the demo does not rot | unit, offline, in-process | `tests/test_demo_coupon_giftcard_sample.py` (see the note below this table) |
| adapter input validation | unit, offline | one case per §2.5 row, each asserting `WixGiftCardError`, that `.code` is the row's code and is in `REFUSAL_CODES`, and **zero** recorded requests — so a refusal is proven to cost no HTTP call and to be branchable on a field rather than on message text |
| the demo itself | integration-ish, offline | **`tests/test_demo_coupon_giftcard_sample.py`**, which imports the demo and runs `main(["--json", "--no-colour"])` **in-process** — see the note below. Not a workflow step |
| the adapter cannot go live early | static, AST | no handler imports `wix_gift_cards` |
| live Wix behaviour | **not testable here** | needs the credential and a live write. §6.5 is the owner path, and it is the only one. |

**The demo's anti-rot claim had no enforcer, and now it has one — a test, not a workflow.**
Revisions 1-4 said the demo "is run in CI with `--json`" and that this is what stops it rotting,
and §4.2 leans on the 0/1/2 exit contract. Measured at `32b632e3`: **no workflow under
`.github/workflows/` references `demo_` or `scripts/demo` at all**, the full-suite step is
`python -m pytest -q` (`route-auth.yml:111`), which does not execute `scripts/demo_*.py`, §8
listed no workflow as modified, and §7's own Running line gave the demo as a manual command. The
mechanism did not exist.

Of the two available repairs, **a test is chosen over a workflow step**, and the reason is that it
buys strictly more:

| | a new workflow step | `tests/test_demo_coupon_giftcard_sample.py` |
|---|---|---|
| executed by existing CI | needs a new step and a new file in `§8 Modified` | **yes, already** — `pytest -q` at `route-auth.yml:111` collects it |
| inherits the `boto3` sabotage and the `_key_cache` seeding | **no** — a subprocess starts clean, so the no-AWS proof is the demo's own and nothing independently checks it | **yes** — in-process, so the harness's containment applies to the demo run too |
| failure legibility | an exit code and a scrollback | a named test with an assertion message |

So the test imports the demo the way this repository already imports a script —
`importlib.util.spec_from_file_location`, the pattern `tests/test_provision_checkout_contract.py`
and four others use — installs the §2.2 sabotage and the `_key_cache` seed, calls
`main(["--json", "--no-colour"])`, and asserts:

* the return value is `0`;
* the captured stdout parses as JSON and nothing else was printed (that is `--json`'s contract);
* the transcript reports **three legs** and **zero contract mismatches**;
* `wix_ecom._secrets is None` **after** the run, so the demo's own no-AWS line is corroborated by
  an assertion outside the demo rather than by the demo agreeing with itself.

`main` therefore has to **return** its exit code rather than only calling `sys.exit`, with the
`if __name__ == "__main__": sys.exit(main())` wrapper doing the exiting. That is the one shape
change this finding imposes on §4.2, and it is what makes the exit contract testable at all.

Running: `.venv/bin/python -m pytest tests/test_wix_coupon_giftcard_sample.py
tests/test_demo_coupon_giftcard_sample.py
tests/test_gift_card_redeem_concurrency.py tests/test_gift_card_store.py
tests/test_gift_card_two_leg_finalization.py tests/test_gift_card_spi_contract.py
tests/test_gift_card_amounts_and_gst.py tests/test_gift_cards_iam_and_table.py
tests/test_wix_coupons_contract.py tests/test_coupon_store.py
tests/test_coupon_reconciliation.py
tests/test_payment_vocabulary_at_decision_points.py` — every consumer of either
`gift_card_store` or `coupon_fake_dynamo`, per §5.5 — plus
`.venv/bin/python scripts/demo_coupon_giftcard_sample.py --json >/dev/null`.
`conftest.py` refuses anything below Python 3.12, so the `.venv` interpreter is required and a
bare `python3` is not a valid baseline.

**Hard to test, and said rather than hidden:** that a two-item `TransactWriteItems` behaves in
real DynamoDB exactly as `FakeTable` models it. The fake is a model, and the model is the thing
being trusted. Two places the model is known to need care are now explicit rather than discovered
later: the `RLock` is what supplies atomicity (without it the fake can invent a race the real
database does not have, in either direction — §2.6), and `TransactionConflict` is a real
cancellation reason the fake has to be able to produce or the retry branch is untested (§5.3).
Mitigation beyond that is to keep the fake strict — it raises on any item shape or expression
form it does not implement, so it cannot quietly approve something it did not evaluate — and to
note that the first real exercise of this path is whenever `wecare-gift-cards` is deployed, which
has not happened (§6.5).

---

## 8. Files

**New**

| Path | Purpose |
|---|---|
| `tests/wix_transport_stub.py` | the `urlopen` replacement plus `UnexpectedWixCall(BaseException)`; records real requests with `Authorization` redacted at capture. **`expect(*, method, endpoint, ...)` is typed by the call it answers** and refuses a mismatch at pop time, which is what makes "one create, not two" enforceable (§2.3) |
| `tests/test_wix_coupon_giftcard_sample.py` | the harness, §2.4 Groups A-D |
| `tests/test_gift_card_redeem_concurrency.py` | the concurrent double-debit test, §5.4. Also imports `assert_transaction_items_are_exact_key_updates` from `tests/test_gift_card_store.py` and calls it over a recording that includes a **cancelled** attempt, which is the one caller that exercises the attempt-log-not-outcome-log choice |
| `tests/fixtures/wix_giftcard_create_response.json` | B1 `CreateGiftCardResponse`, full clear code, from the documented example |
| `tests/fixtures/wix_giftcard_query_by_code_response.json` | B1 `QueryGiftCardsResponse`, obfuscated code |
| `tests/fixtures/wix_giftcard_balance_after_redeem.json` | B1 card after a Wix-side redemption |
| `tests/fixtures/wix_giftcard_query_miss_response.json` | `QueryGiftCardsResponse` with `giftCards: []` — the miss `find_by_code` returns `{}` for, and the fixture the one-create assertion needs (§2.4 Group C) |
| `tests/fixtures/wix_giftcard_query_two_matches_response.json` | `giftCards` holding **two** entries, so `AMBIGUOUS_CODE` is asserted against a payload that is actually ambiguous rather than against a mock |
| `tests/fixtures/wix_giftcard_query_disabled_response.json` | one entry carrying `disabledDate` and `expirationDate`, so the resolve-onto-a-dead-card branch is asserted from a real response shape |
| `tests/fixtures/wix_coupon_create_response.json` | `{"id": "..."}`, the id-only create response |
| `tests/fixtures/wix_coupon_get_response_float_amounts.json` | the Get shape with `moneyOffAmount: 10.0` and `minimumSubtotal: 5000.5`, so the `json.loads` float hazard is asserted against a payload that actually contains a float (§2.4 Group B) |
| `amplify/functions/shared/lambda_utils/ecommerce/wix_gift_cards.py` | the B1 adapter; pure, injected request callable, **unwired**. Carries `WixGiftCardError` — a `RuntimeError` with an enumerable `.code` and a `REFUSAL_CODES` set, mirroring `wix_coupons.WixCouponError` — the §2.5 validation table, the byte-exact create body, `find_by_code`'s three specified branches (`{}` on a miss, one hit, `AMBIGUOUS_CODE` on more than one), a return dict carrying `disabled` and `expirationDate` so a resolve hit onto a dead card is reportable, and three derivations: `idempotency_key()` (unkeyed, not bearer value), **`card_code()` (HMAC-keyed under the existing `code_pepper`, domain-separated with `CODE_DOMAIN_TAG`, 20 characters at Wix's ceiling — the production derivation)** and `demo_code()` (unkeyed, demo-only, guarded). Imports `hashlib`, `hmac` and `datetime` beyond the shared money types, and reads no secret — the pepper is a required keyword obtained by the caller |
| `scripts/demo_coupon_giftcard_sample.py` | the runnable demonstration, §4. `main(argv)` **returns** its exit code so the test below can run it in-process |
| `tests/test_demo_coupon_giftcard_sample.py` | **the demo's anti-rot enforcer** (§7). Loads the demo with `importlib.util.spec_from_file_location` — this repository's existing pattern for a script under test — installs the §2.2 `boto3` sabotage and the `_key_cache` seed, runs `main(["--json", "--no-colour"])` in-process, and asserts exit `0`, stdout that parses as JSON and nothing else, three legs, zero contract mismatches, and `wix_ecom._secrets is None` afterwards. Collected by the existing `python -m pytest -q` step at `route-auth.yml:111`, so **no workflow file is modified** |
| `.agents/tasks/wix-coupon-giftcard-sample-20261002/wix-native-decision-memo.md` | the owner memo, §6.1 |
| `docs/execution/wix-contract-verification-20261002.md` | the §3 evidence: per fetch the URL **in the form used**, status, page byte size and the **extracted schema fragment** for each load-bearing fact, including V1 shown as command + zero count. **Written first — implementation step 0**, because §3's tables cite it and it does not exist yet. It must additionally record §3.0.1 — that the pre-revision-5 URL set now 404s and returns a ~4 MB schema-free shell, so a future re-run against the old form reads as *absent* when the fact is *present* |

**Modified**

| Path | Change |
|---|---|
| `amplify/functions/shared/lambda_utils/ecommerce/gift_card_store.py` | §5.3: `redeem` and `void` move to two-item transactions marshalled by a **hand-written `_marshal`** (no `boto3` import — the `:1152` AST gate forbids it); `void`'s transaction conditions on `attribute_exists(credited) AND credited = :false` per §5.3.1; `_mark_settled`/`_mark_credited`/`_drop_applied_marker` and `APPLIED_CLAIM_PREFIX`/`APPLIED_VOID_PREFIX` retired; **`credit()` loses its `once_key` parameter and marker branch, and `redeem()` and `void()` each gain a keyword-only `sleep: Callable[[float], None] = time.sleep` (§5.3) — those are the whole of this change's public signature movement, both additive-or-removing and neither breaking the one production caller, `wix-giftcard-spi/handler.py:310` and `:341`**; new `_is_transaction_cancellation` + `_cancellation_reason_codes` reading `response["CancellationReasons"]` with the unrecognised-reason fallback; `_decrement` renamed `_commit_redemption` and a new `_commit_void` twin (§5.3); and **one new `_transact_with_retry(table, items, *, sleep)` which is the module's ONLY caller of `transact_write_items`** — `_commit_redemption` and `_commit_void` both route through it, which is what the §5.5 AST guard asserts; `_is_conditional_failure` **unchanged** |
| `tests/coupon_fake_dynamo.py` | §2.6: an `RLock` around every operation, an `applied` outcome log beside the existing `calls` attempt log, `transact_write_items` in the AttributeValue shape with an armable `TransactionConflict`, a `name` constructor keyword plus `.name`, `.meta.client`, and `FakeClientError(code, *, cancellation_reasons=None)` placing the list at the response top level. **Shared: seven importers, four gift-card and three coupon** — §9 question 6 names them and the commit discipline they require |
| `tests/test_gift_card_store.py` | §5.5: **six updates, two retire-and-replace, three rewrites, and three re-run without edit** — the count moved from seven updates in revision 8 because §5.3.1's pre-read decision takes the legacy-`credited` test out of the edited set and into the re-run set (the redeem settle-failure test and its void twin are retired; the two `_CreditThrottles` void tests and the stalled-redemption test are rewritten under their own names; the plain-credit test loses its whole `once_key` half; the legacy-`credited` test is **re-run without edit** — §5.3.1's pre-read decision means its `AlreadyVoided` answer and its balance assertion both hold unchanged, correcting revision 7, which had it changing; the access-pattern gate gains a **presence-and-location-only** `transact_write_items` check pinned to `_transact_with_retry` and its two callers — **not** the `ast.unparse` assertion revision 4 specified, which would have failed against correct code, and **not** the runtime helper revision 5 tried to call from it, which would have passed vacuously because that gate drives no transaction; the new module-level helper `assert_transaction_items_are_exact_key_updates(store)` owns item shape and is called from the **six** transaction-driving tests §5.5 enumerates, refusing an empty recording, with each caller asserting a committer **set** rather than a literal transaction count; the balance-floor test's read-ordering assertion re-indexes onto the transaction). **Three tests are re-run without edit and must stay green**: the legacy-`credited` test, the no-`boto3` AST gate (`:1152`) and the no-`float` money-path gate (`:1066`) — the last of which §5.6 now explains in mechanical terms rather than predicting, since a float literal and `int / int` do not call `builtins.float` |
| `tests/test_gift_card_store.py` (new test) | §5.3: `_marshal` is asserted byte-identical to `boto3.dynamodb.types.TypeSerializer().serialize` over the exact value set these transactions carry. Lives in `tests/`, where `botocore` is already a dependency, so the module keeps its import-free guarantee and the equivalence is still measured |
| `tests/test_gift_cards_iam_and_table.py` | §5.5: one added assertion pinning the two gift-card ledger statements' action sets, which no test pinned before |
| `tests/test_gift_card_two_leg_finalization.py` | §5.5: triage only — mechanism-level assertions, if any, get the same treatment; behavioural ones must pass unchanged |

**Read-only, not edited**

`wix_ecom.py` · `money.py` · `identifiers.py` · `coupon_store.py` · `wix_coupons.py` ·
`ecommerce/coupons/handler.py` (**driven** by Group B and demo leg 1, not edited) ·
`ecommerce/gift-cards/handler.py` ·
`ecommerce/wix-giftcard-spi/handler.py` · the three coupon and three gift-card provisioners ·
`scripts/deploy_all_lambdas.py` · `tests/test_payment_vocabulary_at_decision_points.py`

**Read-only but affected — re-run and triaged, not edited.** `tests/test_wix_coupons_contract.py`,
`tests/test_coupon_store.py` and `tests/test_coupon_reconciliation.py` all import
`tests/coupon_fake_dynamo.py`, which **is** being modified. Expected impact is none (§5.5), and
that expectation is written down so a failure reads as a defect in the fake rather than as noise.

**Explicitly out of bounds** — another workflow owns the payment path, a third owns gift-card
edits in the main checkout: `ecommerce/checkout/handler.py` · `payment_readiness.py` ·
`payments/razorpay-webhook/handler.py` · everything under `amplify/functions/messaging/` ·
`.worktrees/direct-razorpay-20261002`.

**Revision 5 adds exactly one file: `tests/test_demo_coupon_giftcard_sample.py`**, and modifies no
workflow. That is the whole material footprint of the third review — everything else it asked for
was a correction to a mechanism already listed here, or a measurement. No file moved between the
New, Modified, Read-only and Out-of-bounds tables.

**Revision 3 adds no file to either table.** The owner's answer changed a verdict, a direction and
three owner-action sections; it did not add code to this change. The gift-card retirement is a
**separate, later change** gated on §0.1, and `wix_gift_cards.py` stays unwired here (§2.5). The
one file whose *content* shifts is `wix-native-decision-memo.md`, which now reports an answered
gate instead of an open question.

**No blockers.** Nothing in this design requires a payment-path change. Measured at `32b632e3`,
the only importers of `gift_card_store` are the two gift-card handlers, the three gift-card
provisioners, `scripts/provision_checkout.py` (one reference) and six test files.
**`ecommerce/checkout/handler.py` does not import it at all**, and neither does the Razorpay
webhook, `payment_readiness.py`, or anything under `amplify/functions/messaging/`. So the §5 fix
does not reach the payment path, and none of those files is edited.

---

## 9. Assumptions and open questions

### Assumptions this design rests on

1. **The Wix site is `fcd82f0c-9572-49c7-acfb-88fb05042ece`** and the admin key is
   `wecare/wix/headless-api-key` field `apiKey`, both read from `wix_ecom.py` defaults. If either
   is overridden by a Lambda environment variable in the live account, the harness assertions
   about `Wix-site-id` are still correct (they compare against `wix_ecom.WIX_SITE_ID`, not a
   literal) but §6.5's call shape would need the live value.
2. **`wix_ecom.py` stays read-only.** Every conversion decision in §2.1 and §3 follows from its
   bare `json.dumps` and `json.loads`. If it ever gains a `Decimal` encoder or a `parse_float`,
   the no-numeric-read rule in `wix_coupons.py` becomes removable and this design's Group B
   assertions become weaker than they should be.
3. **`FakeTable` models `TransactWriteItems` faithfully** for the two-`Update` shape — including
   all-or-nothing application, the `CancellationReasons[].Code` shape, and per-request atomicity
   supplied by the `RLock` (§2.6). This is the single largest piece of trust in §5 and it is named
   in §7 rather than assumed.
4. **Wix enforces coupon-code uniqueness site-wide**, per its own `code` description. §1.3's
   argument is that the *failure is unobservable to us*, not that uniqueness is absent. If Wix
   ever documents a duplicate-code error, the coupon verdict should be revisited — that single
   documented error would make an ambiguous create recoverable and move coupons toward (A).
5. **The demo's placeholder API key is never replaced by a real one.** The redaction is structural
   so that this assumption failing is not a leak, but the assumption is worth writing down.
6. **Python 3.12 via `.venv`.** `conftest.py` raises a `UsageError` below it.
7. **Stubbing `handler._staff` does not weaken the auth guarantee**, because
   `tests/test_route_auth_enforcement.py` owns route authentication and Group D asserts the real
   `_staff` still calls `middleware.require_auth(event, STAFF_ROLE)`. If that enforcement test is
   ever narrowed, this harness's stub becomes a place an auth regression could hide.
8. **Importing a production handler in a test or the demo is acceptable even though it constructs
   two boto3 clients at import** (`middleware.py:24` a `cognito-idp` client, `rate_limit.py:48` a
   `dynamodb` resource). Construction contacts nothing, and the demo enforces zero API calls with
   a `before-send` hook raising a `BaseException` (§4.3). If either module ever makes a call at
   import, the harness and the demo would start needing credentials — that is the signal to
   revisit driving the handler.
9. **`_marshal` and `TypeSerializer` agree on every value this module sends**, asserted rather
   than assumed (§5.3). The assumption that remains is narrower: that these transactions never
   need a type beyond `S`, `N` and `BOOL`. They do not today — the items carry a key string, a
   status string, an attempt id, a timestamp, two integers and two booleans — and `_marshal`
   raises rather than guessing if that ever changes, so the assumption fails loudly.
10. **`asm-exec` is reachable as `~/.local/share/razorpay-mcp-server/asm-exec-env.py`** (§6.2),
    measured 2026-10-02 at mode `0700`. If it is moved or removed, §6.2's Option 2 is unavailable
    and the correct response is to fall back to Option 1, **not** to inline the key.
11. **`wecare/wix/giftcard-spi` field `code_pepper` is the right key for `card_code`.** It is the
    pepper `gift_card_store.code_hash` already derives card keys with, so a card issued under (A)
    and a card key derived under the incumbent model share one secret — which is deliberate while
    both models coexist, and is the reason no new secret is introduced. **If the §0.1 retirement
    clears and the SPI secret is deleted with the rest of the backend, `card_code` loses its
    pepper**, so the retirement change must either keep that secret or move the field to a
    Wix-native secret. It is a line item in §6.4's wiring change, not an afterthought: deleting
    the secret would not break a card already issued (Wix holds the code, and we find cards by
    `codeSuffix` and `id`) but it would break every future derivation.

    **One key, two purposes, so the messages are domain-separated.** `code_hash` HMACs an
    NFKC-upper-cased *code* under this pepper; `card_code` HMACs a *reference id* under it. The
    message spaces differ in practice and nothing structural stopped them overlapping, so
    `card_code` prefixes `CODE_DOMAIN_TAG = b"wix-gc-code:"` to its message (§2.5). That makes a
    collision impossible for **every** input rather than for the inputs we happen to pass, and
    §2.4 Group C asserts it. `code_hash` keeps the untagged construction: retagging it would
    invalidate every partition key already derived from it, for no gain, and it is on the side of
    the §0.1 gate that gets deleted.
12. **The Wix documentation's markdown rendition (`.md`) stays available and stays faithful to the
    HTML schema.** It is the source for every §3 measurement from revision 5 on, because the
    previous URL form 404s (§3.0.1). The known limitation is recorded rather than assumed: it
    renders **no** `Errors` section for any method, so two previously-claimed error facts are now
    marked unverified. If a future fetch needs an error set, it needs a different source, and an
    empty `grep` against this one is not evidence about errors.

### Open questions — owner or provider only

| # | Question | Who can answer | Blocks |
|---|---|---|---|
| 1 | ~~Is the Wix Gift Card app installed on this site?~~ | owner | ✅ **ANSWERED YES, 2026-10-02.** Gift cards are (A). *Is the site premium* remains open but blocks only Wix-sent card emails, not the API |
| 1a | **Does the live API accept our key, our shape and a fractional-INR amount on this site, and is Wix's `idempotencyKey` actually idempotent here?** | owner only — step (a) is a live Wix write | **the retirement**, not the verdict. §0.1 condition 3, procedure in §6.2. This is question 1's successor and it is the one that matters now |
| 2 | Does the Wix admin key carry the two scopes? **Measured 2026-10-02, so the question now names them exactly:** coupons need `Manage Coupons` / `SCOPE.DC-COUPONS.MANAGE-COUPONS`; gift cards need `Manage eCommerce - all permissions` / `SCOPE.DC-ECOM-MEGA.MANAGE-ECOM` — a **broad** scope, not a gift-card-specific one, which the owner should know before granting it | owner / Wix dashboard | §6.5 both routes, and §6.2's read. Already open as prior owner action 2. A `403` on either call is this, not a negative answer |
| 3 | Is the Wix Gift Card app **offered** on this site's plan and region (India / INR)? | Wix / owner | ✅ **moot for availability** — it is installed, so it is offered. Narrowed to one live question: whether an **INR** card with a **fractional** amount is accepted, which is question 1a step (a). Nothing in the fetched schema restricts currency or region |
| 4 | May `WDSAMPLE10` be created in the live Wix store as the sample code? | owner | §6.5. Reserved here, created by nobody |
| 5 | Will coupons ever be created in the **Wix dashboard**, outside this system? | owner | if no, `WIX_CODE_CONFLICT` is unreachable and the policy question behind it disappears |

### Open questions internal to this work

| # | Question | Proposed resolution |
|---|---|---|
| 6 | **Who owns the two shared files right now?** (a) `gift_card_store.py` — the notification says a third session owns gift-card edits in the main checkout. That session's files are in a different working tree, so there is no live collision, but a merge conflict in a 1,513-line money module is a real cost. (b) **`tests/coupon_fake_dynamo.py`**, which revision 4's version of this question omitted and which this change edits just as invasively: an `RLock` around every operation, a new `applied` log, a new `transact_write_items`, a new constructor keyword and two new attributes. Measured at `32b632e3` it is imported by **seven** test files — `test_gift_card_store.py`, `test_gift_card_two_leg_finalization.py`, `test_gift_card_spi_contract.py`, `test_gift_card_amounts_and_gst.py`, `test_coupon_store.py`, `test_coupon_reconciliation.py`, `test_wix_coupons_contract.py` — four gift-card and three coupon. | Confirm ownership of **both** before the §5 edit lands. If the other session is mid-edit in `redeem()` or `void()`, land the **redeem** half alone and file the void half as a named follow-up with the identical fix, rather than contending for the file. **And stage both files the way this workspace requires for a shared file:** explicit paths, and `git commit --only <paths>` rather than a bare `git commit`. The workspace's own rules record two separate occasions on which explicit staging alone was insufficient — the second one because the index was *already dirty with another session's work on arrival*, and `git commit` commits the index — so `--only` is what bounds the commit to these paths regardless of who staged what or when. A new file needs `git add` first, since `--only` resolves pathspecs against files git already knows |
| 7 | Should `void()` be converted in the same change? | **Chosen: yes** (§5.3), because the window is identical and a half-converted module is harder to reason about. Reversible if question 6 says otherwise |
| 8 | Should `wix_gift_cards.py` live in `lambda_utils/ecommerce/` rather than under the task directory? | **Chosen: yes** (§2.5), guarded by an AST test asserting no handler imports it. The alternative — a prototype under the task directory — was rejected because the demo would then exercise code a future (A) decision would not ship. Now that (A) *is* the decision, this reads as the right call for a second reason: the module the demo exercises is the module that gets wired |
| 8a | Should the adapter be **wired** now that gift cards are (A)? | **No** (§2.5, revision 3). Wiring needs §0.1 condition 3 plus a deploy decision, and both are outside this change. Demonstrate → verify live → wire and retire, in that order |
| 9 | Should the demo import test helpers from `tests/`? | **Chosen: yes** (§4.3). One stub and one fake, two callers. Nothing in `tests/` ships in a Lambda package |
| 10 | Does the §3 evidence belong in `docs/execution/`? | Yes. It is dated measurement, and `00-current-owner-overrides.md` requires dated counts to be re-derived rather than quoted — which only works if the derivation is written down |

### What this design deliberately does not do

* It does not design the (A) retirement for gift cards, and revision 3 does not change that even
  though (A) is now the chosen direction. §6.4 sizes it and §0.1 states its gate; authoring it
  before the contract is verified live is how a money defect gets retired without being
  understood, and the owner's instruction says the same thing in its own words.
* It does not wire `wix_gift_cards.py` into any handler (§2.5), and the Group D guard enforces
  that rather than trusting it.
* It does not design, measure or assume anything about **Wix Loyalty or Wix Referral** (§1.5).
* It does not design a Wix-native **coupon** issuance path with no table of ours, because §1.3
  establishes it cannot be made idempotent.
* It does not touch the payment path, the checkout handler, `payment_readiness.py`, the Razorpay
  webhook, or anything under `amplify/functions/messaging/`.
* It does not create, provision, deploy, or write to anything live — no Wix write, no table, no
  route, no IAM, no alias, no secret read, no send.

---

## 10. Consistency pass, 2026-10-02

*Historical, from revision 1.* No `design-review.json` existed at the time, so this was a
self-consistency read rather than a review response. One did arrive afterwards; the response to
it is §11, and where the two sections disagree §11 is later and wins. The five corrections below
all still stand. The document was re-read end to end against the task's own constraints. Five
internal contradictions were found and corrected in place; no verdict, no decision and no
architecture changed. They are recorded rather than silently fixed, because four of the five were
statements that would each have misled an implementer or the owner in a specific way.

| # | Where | The contradiction | Correction |
|---|---|---|---|
| 1 | §6.5 ↔ §4.4 | §6.5 told the owner the live-sample body is "exactly what `--leg coupon` prints". It is not: the demo prints a **money-off** coupon (`moneyOffAmount: 123456`, name *Sample money off*) and §6.5's sample is **percent-off** (`percentOffRate: 10`, name *Sample ten percent off*). An owner copying one into a live Wix store on the strength of that sentence would have created a coupon neither asserted nor intended. | §6.5 now states exactly which single field differs and why, and §2.4 Group A gains a row asserting the **percent-off** variant too, so the sentence's claim — that the payload is an asserted shape — is true of the payload actually handed over. |
| 2 | §5.3 ↔ §8 | "`_mark_settled` is **deleted** for the redeem path … (It remains for nothing — see the void note below.)" is self-contradictory — deleted, yet remaining — and the §8 Modified table says it is retired outright. | §5.3 now says removed entirely, gives the reason (a surviving settle helper invites a future caller to write `settled` outside the transaction, which is the defect §5.3 exists to close), and ties `_mark_credited`'s removal to the void conversion in the same change. §8 was already correct and is unchanged. |
| 3 | §4.1 ↔ §4.4 | §4.1 claimed the demo "never prints a discount figure", while the §4.4 transcript prints `MONEY_OFF 12345600 paise = INR 123,456.00`. | §4.1 now draws the distinction the design actually relies on: no **computed** discount is printed. The figure shown is the coupon definition we authored; `evaluate` still returns a closed-vocabulary verdict and never an amount. The money-arithmetic-is-Wix's invariant is unchanged and is what §1.4 and §3.3 rest on. |
| 4 | §2.5 ↔ §2.4 Group C / §4.4 leg 2 | Group C and the leg-2 transcript both assert a replay consumes **one** create call, but §2.5's `create` described no resolve step, so with a transport stub a second call would simply be a second `POST`. The assertion had nothing in the design to make it true. | §2.5 now specifies resolve-before-generate explicitly: `find_by_code` first when a deterministic code is supplied, `POST` only on a miss, `idempotencyKey` as the server-side backstop for the window between them. Both layers are stated as necessary, with the reason each is insufficient alone. |
| 5 | §2.4 Group C | The resolve-before-create row read as an observation ("consumes one create call") with no stated enforcement mechanism. | Now names the mechanism: the stub queues exactly one create, and a second trips `WixTransport`'s empty-queue refusal (§2.3), so a regression fails loudly instead of passing quietly. *(§11 finding 1 corrects the exception type named here: `UnexpectedWixCall`, a `BaseException`, because an `AssertionError` would have been swallowed by `_request` and answered as a 202.)* |

**Checked and found already consistent** — listed so a later reader knows these were examined
rather than skipped:

* **Transport boundary.** §2.1's "stub replaces `urlopen` and nothing else" holds everywhere; no
  later section stubs `WixCoupons(request=...)` or hand-builds a payload. §2.3, §2.4 and §4.3 all
  drive production functions.
* **Money.** Integer paise throughout; the only `Decimal` is `Decimal(str(value))` where a
  DynamoDB number re-enters arithmetic (§5.6). No `float` on any path. *(Superseded in two
  details by §11: the `float` monkeypatch named here is inert and was replaced by type
  assertions, an AST gate and a direct refusal assertion — finding 7 — and the demo's default
  amounts are now fractional, so the transcript arithmetic is 250050 − 150075 = 99975 paise with
  `"2500.50"` / `"999.75"` as the matching `Money.to_wix()` renderings — finding 14.)*
* **INR.** Compared explicitly in §2.5 and §5.6, never inferred from an amount, in both the
  coupon and gift-card directions.
* **Payment vocabulary.** No section makes a payment-state decision; `payment_status` is the
  named route if one is ever added (§4.3), and §4.3's note that `scripts/` sits outside
  `test_payment_vocabulary_at_decision_points.py`'s scan is consistent with §5.6's claim that the
  gate stays green with no edit. The raw literal `'captured'` appears nowhere in the designed
  code.
* **Bearer value.** The clear gift-card code exists in exactly one expression (§2.5), is reduced
  to `last4` in the same function, is redacted at capture rather than at print (§2.3), and masked
  once in the renderer rather than per call site (§4.3). The coupon-code asymmetry is deliberate
  and pinned from both sides.
* **Verdict coherence.** *(As of revision 1. Gift cards are now (A) — §12 — and the §5 fix is
  justified by §5.0's gate argument instead. Coupons are still (B) and nothing is still deleted,
  so the rest of this bullet stands.)* (B) for coupons and (C) for gift cards were each used
  consistently: nothing is deleted anywhere, the §5 fix is justified by (C) in §5's opening and
  again in §1.2.2,
  and §6.4 sizes the (A) removal without designing it.
* **Concurrency boundary.** §8's out-of-bounds list and §9's question 6 agree; no payment-path,
  checkout, `payment_readiness.py`, webhook or `messaging/` file appears in the New or Modified
  tables.
* **Owner checklist.** §6.1-§6.6 are owner-run only, every credential is by name
  (`wecare/wix/headless-api-key`, field `apiKey`) through `{{resolve:secretsmanager:...}}` and
  `asm-exec`, and no value appears anywhere in the document.

One pre-existing hedge is deliberately left standing rather than resolved: §6.5's deployment
measurements and §1's Wix schema readings are **dated snapshots**, and both already say so and
say to re-derive. Per `00-current-owner-overrides.md` that is the correct state for a dated count,
so it is not a finding.

---

## 11. Response to the first `design-review.json`, 2026-10-02 (revision 2)

Verdict received: **CHANGES_REQUESTED** — 5 HIGH, 11 MEDIUM, 4 NIT, against worktree
`32b632e3`. **All 20 are addressed; none is backlogged and none is ignored.** Every repository
fact the review asserted was re-read from the tree before acting on it, and each one held; where
re-reading produced something the review did not say, that is noted below as *and more so*.

No verdict in §1, no decision in §2.5, §4.3 or §5.3, and no architecture changed. The findings
were concentrated in the mechanisms that prove the properties, which is the right place for a
review to bite: four of those mechanisms could not have worked, one named a call chain that does
not exist, and one API was specified in the wrong shape.

| # | Sev | Disposition | Where |
|---|---|---|---|
| 1 | HIGH | **Fixed.** `UnexpectedWixCall(BaseException)` for all three stub refusals, with the reason — `_request`'s `except Exception` plus `_create`'s 202 — in its docstring. **And more so:** the same swallow exists in `gift_card_store` (`:1321`, plus eleven sibling sites), which wraps the balance move in `except Exception` → `GiftCardStoreUnavailable`. So the fake's new transaction path refuses an unsupported item shape with `UnsupportedFakeOperation(BaseException)` as well, or a shape error would read as a transient outage. | §2.3, §2.4 C, §2.6 |
| 2 | HIGH | **Fixed, taking option (a) *and* (b).** The driven entry point is now named per group: Group A composes `coupon_store.create` and `WixCoupons.create` as two production calls and owns the wire assertions; Group B drives `handler._create` and owns the composition, with the create-failure row split into an adapter row (error escapes) and a handler row (`PENDING_WIX`, 202). Demo leg 1 drives the handler too, so "reimplements nothing" is true of the composition and not only of the modules. | §2.4, §4.1, §4.3 |
| 3 | HIGH | **Fixed.** `TypeSerializer().serialize` on every `Key` and `ExpressionAttributeValue`, `int(value["N"])` on read-back, a §5.6 row for the serialisation hop, and a harness assertion that every `"N"` matches `^-?[0-9]+$`. **And more so:** the fake must deserialize to evaluate anything, so §2.6 now specifies `TypeDeserializer` and a refusal on a non-integral `N`. *(Superseded in one detail by §13 finding 2: the **wire shape is unchanged**, but the module may not import `boto3`, so it is produced by a hand-written `_marshal` pinned byte-identical to `TypeSerializer`. The fake's `TypeDeserializer` is unaffected — it lives in `tests/`.)* | §5.3, §5.6, §2.6 |
| 4 | HIGH | **Fixed, and extended where the proposed fix was incomplete.** The barrier latches on balance **moves**, not on the deleted `_drop_applied_marker`. One latch is not enough to force the schedule, though: four events are specified (`claim_written`, `claim_read`, `a_returned`, `done`), because releasing A on B's read still leaves B's second move unordered against A's marker drop. **And more so:** the test's face value must exceed twice the redemption or the balance floor masks the bug — now stated. *(Superseded in one detail by §13 finding 17: `done` is dropped and the main thread joins A and B instead, which is the same guarantee with one fewer thing to misread.)* | §5.4 |
| 5 | HIGH | **Fixed.** `threading.RLock` held for the whole body of every `FakeTable` operation, with §2.6 saying the lock is what models DynamoDB's atomicity. **And more so:** this collides with finding 4's barrier — blocking inside the lock deadlocks the other thread's `get_item` — so §5.4 states the rule that latches are awaited *outside* the locked body. | §2.6, §5.4 |
| 6 | MEDIUM | **Fixed.** New `tests/fixtures/wix_coupon_get_response_float_amounts.json`; the hazard is asserted (`type(...) is float`) before the containment. Verified from the tree that the existing fixture's numbers are all JSON integers. | §2.4 B, §8 |
| 7 | MEDIUM | **Fixed.** The inert `float` monkeypatch is replaced by boundary type assertions, an AST gate over the adapter and the demo, and `pytest.raises(ValueError)` on `Money.from_wix(10.0)` — which holds, per `money.py:21-25`. | §2.4 C, §2.4 D |
| 8 | MEDIUM | **Fixed.** Normalised lower-case header set carries the meaning; a second assertion pins the exact recorded spelling with `capitalize()` named. Measured on this interpreter: `['Accept', 'Authorization', 'Content-type', 'Wix-site-id']`. | §2.4 A |
| 9 | MEDIUM | **Fixed, and the finding understated it.** `sys.modules["boto3"]` sabotage plus `_secrets is None`. The review cited other test modules; measured here, it is false *within this module* — importing the coupon handler imports `middleware` and `rate_limit`, which `import boto3` **and construct a client** at module scope. So the demo's `boto3 imported = NO` line goes too, replaced by two enforced facts, including a `before-send` hook that fails the run on any AWS call. | §2.2, §2.4 D, §4.3, §4.4 |
| 10 | MEDIUM | **Fixed.** The reassurance is replaced by the invariant, in §5.3 and in the docstring, plus a test that no branch reads `balanceAfterPaise` and a note that Wix's `/v1/balance` is a separate read. Verified: all three `balanceAfterPaise` sites in the module are writes. | §5.3 |
| 11 | MEDIUM | **Fixed.** `:762` added as a retire-and-replace, `:793` as an update, the §8 count corrected to six updates / two retire-and-replace / one rewrite, and `credit()`'s `once_key` removal stated explicitly as a public signature change. *(Both the treatment of `:793` and the count are superseded by §13 findings 3 and 6: the plain-credit test loses a whole half rather than one assertion, three void tests were missing, and the §8 count is now seven updates / two retire-and-replace / three rewrites.)* | §5.5, §5.3, §8 |
| 12 | MEDIUM | **Fixed.** The access-pattern gate gains a `transact_write_items` branch and a §5.5 row, so the module's only balance-moving write stays inside the one test that enumerates reach. | §5.5 |
| 13 | MEDIUM | **Fixed.** `CancellationReasons[].Code` is read — a response field, not an exception message — with `ConditionalCheckFailed` to the decide-from-data path and `TransactionConflict`/`ThrottlingError`/`ProvisionedThroughputExceeded` to a bounded retry: 2 retries, `0.05 * 2**n` plus `_secrets.randbelow(25)` ms jitter, injected sleeper, `GiftCardStoreUnavailable` on exhaustion. The fake can arm the conflict. | §5.3, §2.6 |
| 14 | MEDIUM | **Fixed.** Whole-rupee is scoped to the new `--coupon-money-off-paise`, where `wix_coupons._rupees` requires it; gift-card inputs take any paise and default to `250050` / `150075`, so the default run crosses the fractional boundary §3.3 calls decisive. Group C asserts the round-trip; the §4.4 transcript is updated throughout. | §4.5, §4.2, §4.4, §2.4 C |
| 15 | MEDIUM | **Fixed.** Four verbatim `curl` + extraction commands inlined in §3, including the grep whose non-zero exit **is** the idempotency finding, and §0 reworded to match. The full transcript stays in `docs/execution/wix-contract-verification-20261002.md`. | §0, §3 |
| 16 | MEDIUM | **Fixed.** The justification is now the AWS semantics (two `Update` items need `dynamodb:UpdateItem`; `ConditionCheckItem` only for a `ConditionCheck` item), the wrong citation is corrected in place — `:293` covers the PaymentAttemptsTable statement — and the missing ledger action-set pin is added as one assertion rather than left as a gap. | §5.5, §8 |
| 17 | NIT | **Fixed.** `monkeypatch.setitem(wix_ecom._key_cache, "key", ...)`, with the reason for not mutating the global. | §2.2 |
| 18 | NIT | **Fixed.** §6.2's request block now carries the `{{resolve:secretsmanager:...}}` token inline, identical in form to §6.5 Route A, and both say where `asm-exec` comes from (the workspace MCP server, not `PATH`). | §6.2, §6.5 |
| 19 | NIT | **Fixed.** `.status` and `.headers` are described as provided for future use; only `.read()` is touched by `_request`. | §2.3 |
| 20 | NIT | **Fixed.** A separate `_is_transaction_cancellation`; `_is_conditional_failure` is left exactly as it is, since six non-transactional callers consult it. | §5.3, §8 |

**What the review asked to be kept, and is kept.** The §1 evidence-then-verdict structure with
the asymmetry explained by a measured API difference; §1.3's precision about recoverability rather
than uniqueness; the decision to stub at `urlopen` with its five enumerated reasons; redaction at
capture rather than at print; §5's refusal to design the (A) removal against an undetermined
premise, including the requirement that "retired by deletion, not fixed" appears in the final
report in those words; and §10's recorded self-consistency pass rather than a silent cleanup.

**Scope and prohibitions, re-checked after the revision.** The two new behaviours this revision
introduces — driving `coupons/handler._create`, and the `before-send` hook — are both read-only
and in-process. No file in the out-of-bounds list gained an edit: `ecommerce/checkout/handler.py`,
`payment_readiness.py`, `payments/razorpay-webhook/handler.py`, everything under
`amplify/functions/messaging/` and `.worktrees/direct-razorpay-20261002` are all still untouched,
and `coupons/handler.py` is **driven, not modified**. Still no Wix write, no deploy, no
provisioning, no `get-secret-value`, no credential value anywhere in the document, no live-send
flag, no payment capture, refund or payment-configuration mutation, nothing deleted.

---

## 12. Revision 3 — the owner's answer, and what it did and did not change

The owner answered the one question revision 2 left open, and added one piece of information that
is deliberately **not** acted on. Recorded here as a change record, so a reviewer can see the
delta without re-reading the document.

### 12.1 What changed

| # | Owner statement | What it changed | Where |
|---|---|---|---|
| 1 | The **Wix Gift Card app is installed** on the live site | Gift cards: **(C) Undetermined → (A) Wix-native available, and chosen**. Wix-native is the direction; our backend is to be retired **in source, later, behind a gate** | §0, §1.2.1, §1.2.2, §6.2, §6.4 |
| 2 | Retire our gift-card backend, source only, **but not until the demo proves the Wix path works** | A three-condition retirement gate, with the measured fact that no gift-card resource exists in AWS so nothing can be stranded | §0.1, §6.4 |
| 3 | The `redeem()` fix becomes moot under full retirement — say **retired by deletion, not fixed** | A new §5.0 stating the outcome on each side of the gate, in those words, plus the third fact that completes them: it never reached a customer | §5.0, §5.1, §6.4 |
| 4 | Keep the fix **until** retirement is proven safe; if any part survives, the fix stands | §5.0's decision table, which names partial survival as the dangerous state | §5.0 |
| 5 | **Wix coupons are present too** | Nothing. §1.3.2 records *why* it changes nothing, so the inference is answered rather than ignored | §1.3.2 |
| 6 | **Loyalty and Referral** are present in the Wix site | Nothing is designed. Recorded as explicitly out of scope, with the reason | §1.5 |

### 12.2 The one place I did not follow the instruction as written

The instruction says the demo *"confirms the API behaves as documented on this India/INR site"*.
It cannot. The demo's HTTP boundary is stubbed by design (§2.1), so it confirms **our** side
composes and parses the documented contract; it is blind to a missing scope, a plan or region
constraint, an undocumented required field, or a response that differs from the published schema.

Following that sentence literally would make "the demo passed" sufficient to delete a stored-value
backend, which is the single most consequential wrong turn available in this task. So the
retirement gate has a **third condition** — one owner-run live verification, procedure in §6.2 —
and the instruction's own fallback ("if the demo surfaces a gap, STOP the deletion and report it")
is applied to that call as well as to the demo. The direction is unchanged; the evidence bar is
where the instruction's own caution points rather than where its wording landed.

### 12.3 The 20 review findings are unaffected

Re-checked individually. Revision 3 touches §0, §1, §5.0, §6 and §9 — the verdict and
owner-action layers — while all 20 findings live in the mechanism layer (§2.2-§2.6, §4.3-§4.5,
§5.3-§5.6, §3, §6.2's credential form). Specifically:

* the `UnexpectedWixCall`/`UnsupportedFakeOperation` `BaseException` discipline, the driven-entry-point
  split, explicit marshalling of the transaction (`TypeSerializer` then; `_marshal` emitting the
  identical shape from revision 4 on, per §13 finding 2), the balance-move barrier, the
  `FakeTable` `RLock`, the float fixture,
  the three float proofs, the normalised header set, the `boto3` containment, the
  `remainingBalance` invariant, the four migrated tests, the access-pattern gate, the
  `TransactionConflict` retry, the scoped whole-rupee rule, the inlined §3 commands, the corrected
  IAM justification and the four NITs — **all unchanged and all still required**;
* §5.3-§5.6 are required because §5.0 keeps the fix live until the gate clears, so none of the
  findings that improved the fix is now moot;
* the only cross-reference that moved is §5's opening justification, which was *"the verdict is
  (C)"* and is now §5.0's gate argument. No finding depended on that sentence.

One finding is **strengthened** rather than merely preserved: finding 10's invariant about
`remainingBalancePaise` being an observation rather than a result. Under (A), Wix owns the balance
and `/v1/balance` is a separate read, so "the authoritative balance is always a fresh read" stops
being our discipline and becomes the architecture.

### 12.4 Prohibitions, re-checked against the new material

Revision 3 adds owner-action text and one AWS read set, and no executable change. Confirmed
again: no live Wix write anywhere in this document (the §6.2 sample-card create is marked
owner-only and I have not performed it); **no app installed or configured by me** — the
installation is the owner's dashboard action and is reported, not performed; no deploy, no
provisioning, no `secretsmanager get-secret-value` (the AWS reads in §0.1 are `list-functions`,
`get-function-configuration`, `describe-table`, `get-routes` and `list-secrets` **names only**);
integer paise, explicit INR, no floats; a gift-card code is bearer value and appears nowhere in
clear, including the §6.2 sample-card procedure, which says so explicitly; work stayed in this
worktree, and `.worktrees/direct-razorpay-20261002` and the main checkout were not touched.

---

## 13. Response to the second `design-review.json`, 2026-10-02 (revision 4)

Verdict received: **CHANGES_REQUESTED** — 4 HIGH, 10 MEDIUM, 4 NIT, against worktree
`32b632e3`. **All 18 are addressed; none is backlogged and none is ignored.** Every repository
fact the review asserted was re-read from the tree before acting on it, and every one held. Where
re-reading produced something the review did not say, it is marked *and more so*.

No verdict in §1, no architecture, and no decision in §2.5, §4.3 or §5.3's shape changed. Two
findings were genuinely blocking rather than improving: the test that proves the fix would have
**failed against correct code**, and the mechanism that marshals the money was **forbidden by a
gate this document had not read**.

| # | Sev | Disposition | Where |
|---|---|---|---|
| 1 | HIGH | **Fixed.** `FakeTable` gains an `applied` outcome log appended only after every condition has passed, and §5.4 asserts **both** numbers: `calls == 2` (both threads tried) and `applied == 1` (one landed), plus the balance. §2.6 states in one sentence that `calls` is the attempt log and `applied` the outcome log, so the existing suite's attempt-counting assertions keep their meaning. Verified from the tree: `update_item` appends at `:275` and does not evaluate the condition until `:285`, so the old `calls == 1` would have read `2` post-fix and gone red on correct code. | §2.6, §5.4 |
| 2 | HIGH | **Fixed, taking option (b) and recording (a) and (c) as rejected.** The money is marshalled by a hand-written `_marshal` in the module — ten lines, `S`/`N`/`BOOL`, `type(value) is int` so a `Decimal` or `bool` amount is refused too — pinned **byte-identical to `TypeSerializer`** by a new test in `tests/`, where `botocore` is already a dependency. The `:1152` AST gate therefore stays intact and unweakened. Injection was rejected because marshalling does not reach outside the process, unlike `clock` and `SecretReader`; amending the gate was rejected explicitly rather than silently. `:1152` and the `:1066` float gate are both added to §5.5's list. | §5.3, §5.5, §5.6, §8 |
| 3 | HIGH | **Fixed.** All three void tests added to §5.5. The two `_CreditThrottles` tests are **rewritten under their own names** with the fault aimed at `transact_write_items` instead of the removed `credit()` call, each with its property quoted; the legacy-`credited` test becomes an assertion of §5.3.1's absent-flag branch. **And more so:** the re-run list was incomplete in the other direction too — `coupon_fake_dynamo` is imported by **seven** test files, so the three coupon files §8 calls read-only are now listed with an expected impact of none and a note that a surprise there is a defect in the fake. | §5.5, §8 |
| 4 | HIGH | **Fixed.** New §5.3.1 specifies the void transaction at the redeem half's depth: both items, the condition `attribute_exists(credited) AND credited = :false`, a three-valued table for `credited` (`False` / `True` / **absent**), and a seven-row error table. The absent row is the one that mattered: without `attribute_exists` named, a pre-flag latch matches no branch, every retry cancels, and the card becomes permanently un-voidable. | §5.3.1, §5.4 |
| 5 | MEDIUM | **Fixed.** `_cancellation_reason_codes` reads `error.response["CancellationReasons"]` — top level, sibling of `"Error"` — with the path and the hazard in its docstring, and the stated fallback rule: **empty or unrecognised reason codes are decided from the data, never treated as an outage**, because a cancellation is a condition outcome unless a reason says otherwise. | §5.3 |
| 6 | MEDIUM | **Fixed.** The row said one assertion goes; read from the tree, the test has two halves and the `once_key` half is five lines that become a `TypeError`. §5.5 now says the whole half is deleted, and names where the orphaned property goes: *the same logical credit replayed moves the balance once* changes owner from `credit()` to `void()` and is asserted by `test_the_credit_and_the_credited_flag_are_one_commit`, which must additionally assert a second `void()` credits nothing. | §5.5 |
| 7 | MEDIUM | **Fixed.** Both conflict rows relabelled `assert_mirrors`, which is where the normalised comparison and both `WixCouponConflict` raises live (`wix_coupons.py:254-280`); `get` keeps a row for the `{id, active, type, code}` projection, with the float-containment noted as true **by construction** rather than discovered. | §2.4 B |
| 8 | MEDIUM | **Fixed.** §0 and §3 are in the future tense, and the transcript is promoted to **implementation step 0** with its required contents enumerated — including that an absence is recorded as command + empty output + non-zero exit. §3's tables now cite the artifact instead of standing in for it. | §0, §3, §8 |
| 9 | MEDIUM | **Fixed, taking option (b).** The self-contradiction is removed by withdrawing the "must not be recorded" rule for gift-card codes: `RecordedRequest` records bodies verbatim, every code offline is a fixture placeholder, and the transport is stubbed unconditionally so no real code can arrive. The credential keeps capture-time redaction, and §2.3 states **why the rule is asymmetric** — `_key_cache` is a global a future test could seed from Secrets Manager, so a real key can arrive in this process in a way a real code cannot. The renderer masking is kept and labelled **not load-bearing offline**, with the re-derivation made a line item in §6.4's wiring change. | §2.3, §2.5, §4.3 |
| 10 | MEDIUM | **Fixed.** §2.5 gains `WixGiftCardError` and a six-row validation table covering `initial_value_paise` (`type is int`, `> 0`, through `Money` before formatting), `currency` (compared first), `code` (8..20 or `None`), `idempotency_key` (1..100, empty is a refusal not a fallback), `expiration_iso` and `gift_card_id`, all refusing before any HTTP call — with a §7 row asserting **zero recorded requests** on a refusal. The return asymmetry is stated: `balancePaise` is `initialValue` on create and the **current balance** on a resolve hit, so `resolved: bool` is in the returned dict. | §2.5, §7 |
| 11 | MEDIUM | **Fixed.** The module now owns the derivation — `idempotency_key(reference_id=...)` and `sample_code(reference_id=...)`, deterministic in one input, no clock, no counter — and Group C asserts determinism **before** the one-create row that depends on it. The demo takes `--reference-id` as leg 2's only identity input and **re-derives** on the replay rather than reusing, so the transcript demonstrates the property instead of assuming it. The repository's standing rule on this shape (an identifier must be stable across retries or a retry mints a duplicate) is cited as the reason. | §2.5, §2.4 C, §4.2, §4.4, §4.5 |
| 12 | MEDIUM | **Fixed.** `UnexpectedAwsCall(BaseException)` and `_UnexpectedAwsUse(BaseException)` raised by the `sys.modules["boto3"]` sabotage, each with the one-line reason in its docstring. **And the mitigating layout fact is recorded** as luck rather than design: `_api_key()` is called at `wix_ecom.py:96`, inside the `headers` literal and therefore **outside** `_request`'s `try:` at `:103`, so a raise there escapes rather than becoming a `WixEcomError` — which does not help inside `handler._create`, which is where leg 1 runs. | §2.2, §4.3 |
| 13 | MEDIUM | **Fixed by naming the exact invocation**, since Option 2 **is** §0.1 condition 3 and cannot be deleted. Measured 2026-10-02: `asm-exec` is not on `PATH` but exists as `~/.local/share/razorpay-mcp-server/asm-exec-env.py` (mode `0700`), documents `asm-exec <command> [args...]` with resolution in argv and env, and accepts `--`. §6.2 now carries the one command, with `-o /dev/null -w '%{http_code}'` so no body lands in a transcript, plus the closing rule: **if it does not work, use Option 1 and stop — do not substitute the value.** | §6.2, §9 |
| 14 | MEDIUM | **Fixed.** `FakeTable.__init__` gains `name: str = "stack-wecare-digital-FakeTable"`, stated in §2.6 addition 1 and cross-referenced from addition 3, with the note that nothing asserts a literal name — only that `TableName` equals `table.name`. The three coupon test files are in the re-run list with an expected impact of none, and §2.6 states that the **wait-outside-the-lock** rule applies to subclass overrides too, which is where `_MarkerWriteFails` and `_CreditThrottles` live; `RLock` makes their `super()` re-entry safe. | §2.6, §5.5, §8 |
| 15 | NIT | **Fixed, re-derived against the tree.** `.read()` at `wix_ecom.py:104-105`; the bare `except Exception` at `:109-111` with the `try:` at `:103`; `middleware.py:24` (import at `:16`); `rate_limit.py:48` (import at `:42`); `handler._create` at `:204-235` with its 202 at `:229-233`; `test_gift_card_two_leg_finalization.py` **52** matching lines. §2.1 states the new rule: citations are symbol-first, and a number is dropped wherever a symbol carries the same meaning. | §2.1, §2.2, §2.3, §4.3, §5.5 |
| 16 | NIT | **Fixed.** `FakeClientError(code, *, cancellation_reasons=None)`, placing the list at the response **top level** to match finding 5's read path. The keyword is optional, so every existing call site is unaffected. | §2.6, §8 |
| 17 | NIT | **Fixed.** `done` is gone; three events plus two joins, and the main-thread sequence is written out: `start A → wait claim_written → start B → A.join(5) → set a_returned → B.join(5) → assert`, with `is_alive()` checked after each join so a deadlock fails as a deadlock. | §5.4 |
| 18 | NIT | **Fixed.** One sentence in §4.5 and one line in the §4.4 transcript: no Wix-side maximum is documented, so the SPI ceiling is reused to keep legs 2 and 3 bounded identically and comparable — and if a real bound is ever measured it belongs in §3.3, with `wix_gift_cards.MAX_INITIAL_VALUE_PAISE` following it. | §4.4, §4.5, §2.5 |

**What the review asked to be kept, and is kept.** The §1 evidence-then-verdict structure with the
asymmetry argued from a measured API difference; §1.3's precision about *recoverability* rather
than uniqueness; the transport boundary at `urlopen` with its five enumerated reasons; redaction
at capture for the credential; the one-`TransactWriteItems`-conditioned-on-the-claim fix shape;
§5.4's genuinely-threaded test latching on the **property** rather than on a deleted helper; the
requirement that "retired by deletion, not fixed" and "it never reached a customer" both appear in
the final report; and §7's and §9's refusal to hide that `FakeTable` modelling real
`TransactWriteItems` semantics is the largest piece of trust in §5.

**The owner's coupon decision, received during this revision.** The owner resolved the one
conflict between their own status note and this document by confirming **verdict (B)**: our
coupon table stays the issuance ledger, kept specifically for idempotency, and **Wix does the
discount arithmetic**. That is exactly the hybrid §1.3 and §1.3.2 already specify, so nothing in
the document changes — recorded here so a later reader does not re-open it. Gift cards remain
(A) with retirement gated on §0.1, and the `redeem()` fix stays ready per §5.0.

**Scope and prohibitions, re-checked after revision 4.** The changes are documentation of
mechanism: one hand-written marshaller, two deterministic derivations, one validation table, one
void error table, two logs on a test fake, and a named shell invocation for the owner. No file in
the out-of-bounds list gained an edit — `ecommerce/checkout/handler.py`, `payment_readiness.py`,
`payments/razorpay-webhook/handler.py`, everything under `amplify/functions/messaging/` and
`.worktrees/direct-razorpay-20261002` are untouched — and `coupons/handler.py` is still **driven,
not modified**. No Wix write, no deploy, no provisioning, no `get-secret-value`, no credential
value anywhere in the document (the §6.2 command carries a `{{resolve:secretsmanager:...}}`
reference, which `block-inline-secrets` allows by design), no live-send flag, no payment capture,
refund or payment-configuration mutation, nothing deleted, and no guard weakened — finding 2 was
resolved by writing ten lines rather than by amending the gate that forbade the shortcut.

---

## 14. Resolution of review findings — third `design-review.json`, 2026-10-02 (revision 5)

Verdict received: **CHANGES_REQUESTED** — 2 HIGH, 6 MEDIUM, 5 NIT, against worktree `32b632e3`.
**All 13 are resolved; none is backlogged and none is ignored.** Every repository fact the review
asserted was re-read from the tree before acting on it, and **every one held** — including the two
that were corrections of this document's own measurements. Where re-reading produced something the
review did not say, it is marked *and more so*.

No verdict in §1 changed. No architecture changed. The locked decisions were not relitigated:
coupons stay **Option B** with our table as the issuance ledger kept for idempotency and Wix doing
the arithmetic; gift cards stay **Wix-native (A)** with retirement gated on §0.1; the
`TransactWriteItems` concurrency fix stays until retirement is proven safe; Loyalty and Referral
remain entirely out of scope, and nothing below adds a seam for them.

Two findings were blocking rather than improving, and both in the now-familiar shape — a mechanism
that could not do the job it was named for:

| # | Sev | Disposition | Where |
|---|---|---|---|
| 1 | **HIGH** | **Fixed — the code is now keyed, under the pepper that already exists.** **Superseded in part: the domain tag was added in revision 6 — see §15 finding 6 — and the construction in §2.5 is authoritative. The untagged form below is the pre-revision-6 one and must not be copied.** `card_code(*, reference_id, pepper)` = `hmac.new(pepper.encode("utf-8"), reference_id.encode("utf-8"), sha256)`, reusing `gift_card_store`'s existing mechanism rather than inventing a secret: `SecretReader` (`:367`), `read_pepper` (`:389`), `SECRET_ID = "wecare/wix/giftcard-spi"` (`:104`), `PEPPER_FIELD = "code_pepper"` (`:106`), and the identical `hmac`/`sha256` construction `code_hash` uses (`:442-447`). The adapter **reads no secret** — `pepper` is a required keyword, obtained by the caller exactly as `ecommerce/gift-cards/handler.py:142` already does. `idempotency_key(reference_id)` is unchanged and stays unkeyed, with the reason stated (it is not bearer value, and it must survive a pepper rotation). `sample_code` is renamed **`demo_code`**, documented as demo-only *because* it is unkeyed, and guarded: a Group D AST walk asserts no `.py` under `amplify/` references it. §2.5 carries the confidentiality sentence the finding asked for — `reference_id` is logged in full by standing policy, so an unkeyed function of it is recoverable from a log line. **And more so:** two further holes the finding did not name. (a) The two derivations shared one digest, so the code was recoverable from the key; Group C asserts non-recoverability. **Both halves of this sentence were corrected in revision 8 — see §17 finding 2: the shared digest was never a literal prefix (the prefixes and casing differ), and the whole-string "not a substring" assertion could not fail. §2.4 Group C's digest-body form is authoritative.** (b) Group D asserts `pepper` is **keyword-only with no default**, because a defaulted pepper silently restores the whole defect under a keyed function's name, and that is precisely the edit a later reader makes to tidy a call site. The option of Wix-generated codes (`code=None`) was **not** taken: it would remove `find_by_code` as a resolve step and force Group C's one-create assertion to be re-expressed against Wix's response, which is a weaker property than the one we have | §2.5, §2.4 C, §2.4 D, §4.2, §4.4, §4.5, §8, §9 |
| 2 | **HIGH** | **Fixed — the property is split across two guards, and §5.5 says which owns which half.** The **AST** guard keeps **presence and location only**: exactly two `transact_write_items` calls, one inside `_commit_redemption` and one inside the void committer, found with the same `FunctionDef`-owner walk the gate already uses for `list_by_status`, and it does **not** unparse item contents. A new **runtime** helper over `table.calls` owns the shape: every item's key set is exactly `{"Update"}`, every item carries a non-empty `TableName` and `Key`, no item carries `IndexName`. The finding's diagnosis was verified against the tree first — the gate does `rendered = ast.unparse(node)` on the **Call**, and §5.3 builds the items in separate assignments, so the call renders as `table.meta.client.transact_write_items(TransactItems=[card_item, claim_item])` and contains neither string. §5.5 states the ownership explicitly so neither half is later deleted as redundant. **And more so:** the helper asserts against `calls` rather than `applied`, so a **cancelled** transaction is still shape-checked — a malformed item that never commits is still malformed — and the `{"Update"}`-only assertion is what forbids a `Put`, `Delete` or `ConditionCheck` item arriving later without a design change. **Both halves of this row were corrected in revision 6 — see §15 findings 1 and 2.** The runtime helper was sited in the gate, which drives no transaction, so it would have passed vacuously; and "exactly two calls in two named functions" pinned a call-site layout the shared bounded retry does not produce. The split itself survives; where each half lives and what it asserts did not | §5.5 |
| 3 | MEDIUM | **Fixed, and both halves of the citation were wrong exactly as the review said.** Measured: `money.py` defines `positive_paise` and **no** `value_paise`; `value_paise` is `gift_card_store.py:543`, a module this adapter must not import — doing so would depend on the backend this design works toward retiring. And `positive_paise` does **not** refuse an integral `Decimal`; it converts one (`if isinstance(value, Decimal): ... value = int(value)`). The cross-module citation is dropped. The rule is stated standalone — `type(initial_value_paise) is not int`, with the reason spelled out (`bool` *is* an `int`, so `True` would be one paise) — and `Money.__post_init__` is named as the second gate by what it actually enforces: `type(self.paise) is int`, the range, and `currency != "INR"`, in one condition. One line records that `positive_paise` is deliberately not the model here and why its behaviour is right for *its* callers, which read DynamoDB `Decimal`s | §2.5 |
| 4 | MEDIUM | **Fixed by measurement, and the measurement reversed the finding's expectation in the more useful direction.** `giftCard.source` is not merely writable, it is **required**: `Required parameters: giftCard, giftCard.initialValue, giftCard.initialValue.amount, giftCard.currency, giftCard.source`, `enum {ORDER, MANUAL}`, `immutable`. Revision 4's §3.3 row ended that list with "`...`", which is where the requirement was hiding. So `source: str = SOURCE_MANUAL` is a parameter with a validation row restricted to `{"MANUAL"}`, and the exclusion of `ORDER` is argued rather than defaulted away — it is a provenance claim and nothing here creates a card from an order. The expiry key is named: **`expirationDate`**, `format date-time`, `immutable`, documented example `"2026-11-11T00:00:00Z"`. §2.5 now states **the exact dict** the body must equal, so Group C compares whole-body like Group A, and three properties of it are argued: optional keys are **omitted rather than sent as `null`**, no `readOnly` field is ever sent, and `notificationInfo`/`orderInfo` are writable and deliberately withheld (one triggers a live customer email on a premium plan, the other is a false provenance claim) | §2.5, §2.4 C, §3.3, §4.4 |
| 5 | MEDIUM | **Fixed by measuring the response schemas, and both reads turned out to be available — one of them from a field this design had not noticed.** (a) `QueryGiftCardsResponse.giftCards[]` carries the **full** `GiftCard`, including `balance` (type `Amount`, `read-only`) and `currency`. So the resolve path is **one** request, not the query-then-`get` the finding offered as the fallback, and §3.3 now records the response schema rather than only the filter map. (b) `codeLast4` does not need an extraction rule at all: **`codeSuffix`** is a documented `read-only` field, *"Last 4 characters of the gift card code"*, `minLength 4, maxLength 4`, present on **both** the create and the query responses, corroborated by the introduction's *"showing only the last 4 characters"*. That is strictly better than the proposed "last four after stripping non-alphanumerics", because nothing parses bearer value: the rule is **read `codeSuffix`, and refuse with `WixGiftCardError("CODE_SUFFIX_MISSING")` if it is absent or not four characters** — no fallback to slicing `code`. The obfuscation format for an unhyphenated custom code is therefore left **unmeasured and irrelevant**, which is stated in §2.5 rather than guessed at in §6.2. **And more so:** two Wix pages **disagree** about `balance`'s operator map (`$exists` on the method page; `$eq,$ne,$exists,$in` and Sortable in the dedicated article). Recorded, not resolved, with the conservative rule kept: no balance decision is ever made from a query, which holds under either map | §2.5, §3.3, §2.4 C, §6.2 |
| 6 | MEDIUM | **Fixed.** `expect(*, method, endpoint, status=200, body=None, raw=None)`, and `__call__` compares `(request.get_method(), request.full_url)` against the queued entry **before** popping, refusing a mismatch with `UnexpectedWixCall` naming expected vs actual. §2.3's failure-mode table gains the row, with the finding's scenario in it verbatim: the replay queues `query(miss) → create → query(hit)`, so a second `POST` would otherwise pop a queued **query** response and the named enforcement would never fire. §2.4 Group C now names the **recording count** as the enforcement — `len([r for r in transport.requests if r.method == "POST" and r.url == wix_ecom.WIX_API_BASE + "/gift-cards/v1/gift-cards"]) == 1` — because that assertion does not depend on queue ordering at all, with the typed queue kept as what makes the failure legible rather than as the proof | §2.3, §2.4 C, §8 |
| 7 | MEDIUM | **Fixed — and then immediately exercised on its own author, which is recorded rather than smoothed over.** §3.0 splits the rule: non-verdict rows are corrected in place and the artifact wins; the four verdict-carrying facts are named **V1-V4** and a disagreement **HALTS** implementation and re-runs §1's verdict, with the sentence the finding asked for: *a row edit is not a sufficient response to a verdict changing*. Then all four were re-measured, and two things happened. (a) **The §3 commands no longer work at all** — the documentation moved, the old URLs return 404 with a ~4 MB schema-free shell, and `grep -c idempotencyKey` over it returns **0**, which under the old command set would have read as *absent* and **inverted verdict (A)**. §3.0.1 records that and replaces the commands with the markdown-rendition form that works. (b) **One clause of V2 was contradicted**: the coupon API *does* publish a per-field operator map, in `filter-and-sort.md`, and `specification.code` is in it. So §1.3.1 **re-runs** the coupon verdict from the corrected evidence instead of editing the row underneath it. Outcome: **(B) stands**, two of the three requirements for (A) still fail, and the stated reason narrows from *"no idempotency key and no read-by-code"* to *"no idempotency key and no duplicate error"* — which is also exactly the owner's locked Option B, since the newly-available capability is the one that decision never relied on. §1.3's own revision-1 sentence anticipating this is quoted as what carried the verdict | §3.0, §3.0.1, §3.1, §3.4, §1.3, §1.3.1, §1.3.2, §6.6 |
| 8 | MEDIUM | **Fixed, taking option (a).** Measured first: **no** workflow references `demo_` or `scripts/demo`, and the full-suite step is `python -m pytest -q` (`route-auth.yml:111`), which does not execute a script. New `tests/test_demo_coupon_giftcard_sample.py` loads the demo with `importlib.util.spec_from_file_location` — the pattern `tests/test_provision_checkout_contract.py` and four others already use — and runs `main(["--json", "--no-colour"])` **in-process**, asserting exit `0`, stdout that parses as JSON and nothing else, three legs, zero mismatches, and `wix_ecom._secrets is None` afterwards. §7 states why a test beats a workflow step: it is already collected by existing CI, **and** in-process execution means the demo inherits the §2.2 `boto3` sabotage and `_key_cache` seeding, so the no-AWS claim is corroborated from outside the demo instead of the demo agreeing with itself. The file is in §8 New; **no workflow is modified**. One consequence named in §4.2: `main` must **return** its exit code, with `sys.exit(main())` under the `__main__` guard | §7, §4.2, §8 |
| 9 | NIT | **Fixed.** `GiftCardValidationError("UNMARSHALABLE_VALUE", f"cannot marshal {type(value).__name__}")`, with the reason recorded: `GiftCardError.__init__(code, message="")` sets `self.code = code`, and `.code` is the stable enumerable field the SPI maps through `SPI_ERRORS` — so an interpolated message in the `code` slot makes the code vary with the offending type, which no handler can branch on and no log can group by | §5.3 |
| 10 | NIT | **Fixed, and the review's reading of the tree was confirmed.** The row's property is restated as *"the floor is a condition **on the transaction**, and no read precedes **the money move**"*, and the row now says the assertion re-indexes onto the `transact_write_items` call. The existing assertion is `"get_item" not in operations[:operations.index("update_item")]`, and post-fix the surviving `update_item` is the best-effort `balanceAfterPaise` follow-up that §5.3 adds **after** a balance read — so indexing on it would assert the wrong thing about the wrong write. §5.3's prose was already right; only this row disagreed with it | §5.5 |
| 11 | NIT | **Fixed.** Question 6 now has two parts and names `tests/coupon_fake_dynamo.py` with all **seven** importers listed individually (four gift-card, three coupon), measured at `32b632e3`, alongside what this change does to it — an `RLock`, an `applied` log, a `transact_write_items`, a constructor keyword and two attributes. The commit discipline is stated as the workspace requires it: explicit paths **and `git commit --only <paths>`**, with the reason — the workspace's rules record two separate occasions where explicit staging alone failed, the second because the index was already dirty with another session's work on arrival, and `git commit` commits the index. The `git add`-first caveat for a new file is included, since `--only` resolves pathspecs against files git already knows | §9 |
| 12 | NIT | **Fixed.** §2.4 Group B specifies the event — `{"body": json.dumps(payload), "_auth": {"username": "demo-operator"}, "headers": {...}}` — with the measured reason: `_create` reads the payload through `_body(event)` and the creator from `(event.get("_auth") or {}).get("username")`, so with `_staff` stubbed to return `None` nothing populates it and `created_by` would be `None` on every run. The note the finding asked for is there: the **stub supplies `_auth` itself**, which matches production because `require_auth` writes `_auth` onto the event and returns `None` on success. §4.3 uses the same event and §4.4's transcript now shows `created_by demo-operator` | §2.4 B, §4.3, §4.4 |
| 13 | NIT | **Fixed, with the finding's own verification repeated and confirmed.** §5.3's error table gains the `GCTXN#` record / `GCTXN-ID#` pointer row — not recoverable, because the claim is already `settled` by the transaction so a retry takes the replay branch and never re-drives the put — and a paragraph stating in plain words that **this hole already exists pre-fix** once `_mark_settled` succeeds, so it must not be read as introduced by this change. It is filed as a named follow-up with its shape given (write the ledger row inside the transaction, or reconcile on a settled claim with no `GCTXN#` row), conditional on the §0.1 gate not clearing — under (A) it goes with the deletion, which is the only reason it is not fixed here | §5.3 |

**What the review asked to be kept, and is kept.** The §1 evidence-then-verdict structure with the
asymmetry argued from a measured API difference; §1.3's precision about *recoverability* rather
than uniqueness — now load-bearing in a way it was not, since recoverability turned out to exist
and the verdict had to rest on atomicity instead; the transport boundary at `urlopen` with its five
enumerated reasons; redaction at capture for the credential; `idempotency_key(reference_id)`
exactly as designed; the one-`TransactWriteItems`-conditioned-on-the-claim fix shape; §5.4's
genuinely-threaded test with both the attempt and the applied counts; the requirement that
*"retired by deletion, not fixed"* **and** *"it never reached a customer"* both appear in the final
report; and §7's and §9's refusal to hide that `FakeTable` modelling real `TransactWriteItems`
semantics is the largest piece of trust in §5.

**Scope and prohibitions, re-checked after revision 5.** The material footprint is one new test
file and corrections to mechanisms already listed. No file in the out-of-bounds list gained an
edit — `ecommerce/checkout/handler.py`, `payment_readiness.py`,
`payments/razorpay-webhook/handler.py`, everything under `amplify/functions/messaging/` and
`.worktrees/direct-razorpay-20261002` are untouched — and `coupons/handler.py` is still **driven,
not modified**. No deploy, no provisioning, no live Wix write of any kind (§6.2's sample-card
create is owner-only and was not performed); no `secretsmanager get-secret-value` in any spelling
— the pepper and the API key appear only as secret **names**, `wecare/wix/giftcard-spi:code_pepper`
and `wecare/wix/headless-api-key:apiKey`, and `card_code` takes its pepper as an injected keyword
so the adapter cannot read one; integer paise, explicit INR, no floats, `Decimal(str())` only where
a DynamoDB number re-enters arithmetic; resolve-before-generate on both issuance keys; and the
bearer-value gift-card code is now **keyed**, never returned to a caller, never logged — which is
the one prohibition revision 4 asserted and did not hold. Loyalty and Referral are designed
nowhere. No live-send flag, no payment capture, refund or payment-configuration mutation, nothing
deleted, and no guard weakened: finding 2 was resolved by splitting a gate across two guards rather
than by loosening either one.

---

## 15. Resolution of review findings — `design-review2.json`, 2026-10-02 (revision 6)

Verdict received: **CHANGES_REQUESTED** — 1 HIGH, 3 MEDIUM, 5 NIT, against worktree `32b632e3`,
with the prior review's thirteen findings all confirmed resolved. **All 9 are resolved; none is
backlogged and none is ignored.** Every repository fact the review asserted was re-read from the
tree before acting on it, and **every one held** — including the two that contradicted this
document's own mechanisms. Where re-reading produced something the review did not say, it is
marked *and more so*.

No verdict in §1 changed. No architecture changed. The locked decisions were not relitigated:
coupons stay **Option B** with our table as the issuance ledger kept for idempotency and Wix doing
the arithmetic; gift cards stay **Wix-native (A)** with retirement gated on §0.1 and source-only;
the `TransactWriteItems` concurrency fix stays until retirement is proven safe; Loyalty and
Referral remain entirely out of scope, and nothing below adds a seam for them.

| # | Sev | Disposition | Where |
|---|---|---|---|
| 1 | **HIGH** | **Fixed — the runtime guard is re-sited onto tests that drive a transaction, and it now refuses an empty recording.** The review's diagnosis was verified from the tree first and is exact: `test_every_dynamodb_access_is_an_exact_key_operation_or_the_status_index_query` (`:1094`) has a runtime tail of precisely `store = table()` then `pytest.raises(AssertionError): store.scan()` (`:1125-1127`) on a fresh empty `FakeTable`, so no `transact_write_items` is ever recorded and a helper iterating `table.calls` would have asserted nothing while §7 reported the item shape as covered. `assert_transaction_items_are_exact_key_updates(store)` is now specified in full, **opens with `assert transactions, "no transact_write_items was recorded, so this helper asserted nothing"`**, returns the count it saw, and is called from four places with the count each expects: the two §5.5 redeem tests (`1`), the §5.5 void tests (`2`, so **both committers** are covered and neither can be the silently missing one), and §5.4's concurrency test (which is the caller that exercises a **cancelled** attempt, the reason the helper reads `calls` and not `applied`). **Both halves of that sentence were corrected in revision 8 — see §17 finding 1: the caller list is six tests, not four, and the per-test literal counts were wrong for two of the void callers and are replaced by a committer-set assertion. §5.5's numbered table is authoritative.** The static gate keeps presence and location only, and its existing `scan()` tail is left untouched — deliberately, because adding a money cycle to a test whose subject is the AST is how the vacuous version came about. §5.5's ownership sentence and §7's row are corrected to say where the runtime half actually runs. **And more so:** the helper's location is named (`tests/test_gift_card_store.py`, beside `table`/`issue`/`clock`/`digest_of`) and imported by the concurrency test, so the legibility revision 5 was reaching for by putting it in the gate is kept without the vacuity | §5.5, §7, §8 |
| 2 | MEDIUM | **Fixed by deciding the implementation, not by loosening the guard.** §5.3 now **decides** that `_transact_with_retry(table, items, *, sleep=time.sleep)` is the module's **only** caller of `transact_write_items`, with both committers routing through it, and states why the alternative was rejected: §5.3.1 gives the void path *"the same bounded retry as redeem, same injected sleeper"*, and two copies of a jittered retry loop is exactly the duplication a reviewer of the implementation would ask to be factored out — at which point a guard pinned to "exactly two calls in two named functions" goes red on better code. The AST arm follows the decision: **exactly one** `transact_write_items` call, its owning `FunctionDef` is `_transact_with_retry`, and that name is called from exactly `_commit_redemption` and `_commit_void` (the void committer was unnamed in revision 6; §16 finding 3 names it). **And more so:** the "no third caller" clause is a property the two-call version did not have — a new committer cannot open a transaction without changing the guard. §5.3.1's error row and §8's Modified row name the wrapper, so the structure appears once and is not re-derived | §5.3, §5.3.1, §5.5, §8 |
| 3 | MEDIUM | **Fixed by naming the real import list and keeping the gate a denylist** — option one of the two offered, with the reason stated. The parse is kept, because `datetime.datetime.fromisoformat` is a stronger check than the regex alternative and because the alternative needs `re`, so it required the identical edit for no gain; an unvalidated string going into a money request body was the worse of the two resolutions. `datetime` is added to §2.5's import paragraph, §2.4 Group D's row and §8's New row, all three now agreeing. **And more so:** the Group D row now says in terms that **the enumeration is descriptive and the asserted rule is the denylist**, because the failure the finding anticipated is an implementer turning "the only imports" into an allowlist assertion — which is the same shape as findings 1 and 2 and the third time this document has had to repair it | §2.5, §2.4 D, §8 |
| 4 | MEDIUM | **Fixed — all three branches specified, and the dead-card case is now reportable instead of silent.** `find_by_code` returns `{}` on a miss (stated as the contract, with the reason: a `None` or a raise would make the resolve path a try/except), the single-hit view on one match, and raises `WixGiftCardError("AMBIGUOUS_CODE")` on more than one — with the argument that this is a live possibility rather than a theoretical one, since §3.4 records two Wix pages disagreeing about this API's operator map, so reading `giftCards[0]` under an unhonoured filter is a money read from an arbitrary row. `create`'s return dict gains **`disabled: bool`** (from `bool(disabledDate)`, Wix's own `readOnly` timestamp — there is no separate status field) and **`expirationDate: str \| None`** (raw and unparsed), both read on **both** paths, with the sentence the finding asked for: a resolve hit is returned even when the card is dead, because minting a second card for one reference is the worse failure, and these two keys are what let the caller decide. §2.4 Group C gains four rows (miss → `{}` plus exactly one create; two-entry → raises with zero further requests; `disabledDate` → resolves with `disabled: True`; expiry returned verbatim) and §8 gains the three fixtures they need. **And more so:** the per-key source table now states that `giftCards[0]` is only reachable *after* the length check, so the ordering is the guarantee rather than Wix's uniqueness promise; and the adapter is stated to make **no** expiry decision, because comparing a Wix timestamp against our clock is a decision with a timezone and a skew in it | §2.5, §2.4 C, §7, §8 |
| 5 | NIT | **Fixed — it now mirrors the class it cites in the detail that matters.** `WixGiftCardError(RuntimeError)` with a class-level `code = "WIX_GIFT_CARD_REFUSED"` and `__init__(self, code, message="")` setting `self.code`, verified against the tree: `wix_coupons.WixCouponError` is a `RuntimeError` carrying `code = "WIX_MIRROR_FAILED"`, overridden to `"WIX_CODE_CONFLICT"` on `WixCouponConflict`. Every raise is two-argument. **And more so:** a `REFUSAL_CODES` frozenset enumerates the closed reason set, every row of §2.5's validation table names its code, and §2.4 Group C asserts `.code` membership — so the reason cannot drift back into the message slot, which is the same enumerability property prior finding 9 fixed one layer down in `_marshal` | §2.5, §2.4 C, §7, §8 |
| 6 | NIT | **Fixed with a tag on the message, not on the output.** `CODE_DOMAIN_TAG = b"wix-gc-code:"` is prefixed to `card_code`'s HMAC message, so a collision with `gift_card_store.code_hash` under the shared `code_pepper` is impossible for **every** input rather than for the inputs the two happen to receive. Group C asserts the two differ and that neither underlying digest is a substring of the other. §2.5 and assumption 11 both record that `code_hash` keeps the **untagged legacy** construction, with the reason it is not retagged: every partition key already derived from it would be invalidated, for no gain, and it sits on the side of the §0.1 gate that gets deleted | §2.5, §2.4 C, §9 |
| 7 | NIT | **Fixed — `[:16]`, so the code is exactly 20 characters, at Wix's documented ceiling**, doubling the HMAC margin from 48 to 64 bits at no cost. `demo_code` moves to `[:16]` too, deliberately, so the demo crosses the same length boundary production will rather than exercising a shorter one; §2.4 Group C asserts `len(...) == MAX_CODE_LENGTH == 20` for both, so a future shortening has to change a test. The one sentence the finding asked for is in the docstring: the length sits at the ceiling *because* the value is bearer value. **And more so:** §4.4's transcript is re-derived rather than left stale — `sha256("wd-gc-sample-2026-10-02")[:16]` makes the masked demo code `****8FA8` and the `codeSuffix` `8FA8`, and the body comment now reads `<20 chars, masked>`, so the transcript stays exact instead of carrying the old `[:12]` value | §2.5, §2.4 C, §4.2, §4.4, §7 |
| 8 | NIT | **Fixed — §6.4's line item is now two, and the second is the larger.** (a) keeps the recording rule. (b) states where `card_code`'s **return value** may travel, because the production clear code never comes from a Wix response at all — `create` discards it — it comes from the caller, which is the thing holding the pepper, so the whole lifetime of the real bearer value sits in code this design does not author. The wiring change must enforce: never a log line at any level or in any spelling; never an exception message; never a response to anyone but the card's intended holder (`codeLast4` is what staff and reconciliation surfaces get, which is why `create` returns it); never persisted in clear. **And more so:** the CodeQL constraint is named, because it is the thing that makes "it only logs whether a code exists" not a defence — `py/clear-text-logging-sensitive-data` tracks taint across function boundaries and has already failed this build twice on a secret reduced to a boolean | §6.4 |
| 9 | NIT | **Fixed, with the invisible reason made explicit and §7 aligned to it.** The Group D row now states that `wix_gift_cards.py` is itself under `amplify/` and **defines** `demo_code`, so the guard passes only because a `def`'s own name is a plain string attribute of an `ast.FunctionDef` rather than a `Name` node — which is why the walk names `Attribute`, `Name` and `ImportFrom` and nothing else. §7's looser *"references the name"* wording is replaced with the three node types and the same caveat. **And more so:** the row names the wrong repair as well as the right one — the fix an implementer reaches for after a text grep fails is to exclude the defining file, which would exclude the one file most likely to grow a second reference. Walk the three node types; do not special-case the file | §2.4 D, §7 |

**What the review asked to be kept, and is kept.** Everything it confirmed: the keyed code under
the existing pepper with the injected-reader discipline and no new secret name; `pepper` as a
required keyword-only parameter with no default, asserted from the AST signature; the `demo_code`
rename, its demo-only declaration *because* it is unkeyed, and the AST fence over `amplify/`;
`idempotency_key(reference_id)` unchanged and unkeyed, with the rotation-invariance argument; the
AST arm reduced to presence; `money.positive_paise` reconciled with `Money.__post_init__` named by
what it enforces; the byte-exact create body with `source` narrowed to `{"MANUAL"}` and
`expirationDate` named; `codeSuffix` read rather than `code` parsed, with `CODE_SUFFIX_MISSING` as
a refusal and no fallback; the typed `expect(*, method, endpoint, ...)` queue with the recording
count as the named enforcement; §3.0's halt rule and the record of it firing on its own author;
and `tests/test_demo_coupon_giftcard_sample.py` as the demo's anti-rot enforcer with no workflow
modified.

Also kept, and worth restating because revision 6 touches the sentences around it: the review's
observation that `demo_code` remains derivable from `idempotency_key`, both being bare digests of
the same input. That is still true at `[:16]` and is still deliberately tolerated — §2.5's
docstring now says so in those words — because every offline code is a fixture placeholder and the
Group D guard is what keeps the overlap out of production. The §4.4 transcript is a demonstration
of the request shape, not of the production masking property.

**Scope and prohibitions, re-checked after revision 6.** The material footprint is three new
fixtures, one new named test helper, and corrections to mechanisms already listed; one new
function (`_transact_with_retry`) inside a file already in §8 Modified. No file moved between the
New, Modified, Read-only and Out-of-bounds tables. No file in the out-of-bounds list gained an
edit — `ecommerce/checkout/handler.py`, `payment_readiness.py`,
`payments/razorpay-webhook/handler.py`, everything under `amplify/functions/messaging/` and
`.worktrees/direct-razorpay-20261002` are untouched — and `coupons/handler.py` is still **driven,
not modified**. No deploy, no provisioning, no live Wix write of any kind; no
`secretsmanager get-secret-value` in any spelling — the pepper and the API key appear only as
secret **names**, `wecare/wix/giftcard-spi:code_pepper` and `wecare/wix/headless-api-key:apiKey`,
and `card_code` takes its pepper as an injected keyword so the adapter cannot read one; integer
paise, explicit INR, no floats, `Decimal(str())` only where a DynamoDB number re-enters
arithmetic; resolve-before-generate on both issuance keys, now with the miss branch specified so
the resolve step is a contract rather than an assumption; and the bearer-value gift-card code is
keyed, domain-separated, 20 characters, never returned to a caller, never logged — with §6.4 now
carrying the caller-side obligation the module cannot enforce. Loyalty and Referral are designed
nowhere. No live-send flag, no payment capture, refund or payment-configuration mutation, nothing
deleted, and **no guard weakened**: finding 1 was resolved by making a guard able to fail and
finding 2 by deciding the implementation the guard describes, not by relaxing either.

---

## 16. Resolution of review findings — the re-review in `design-review2.json`, 2026-10-02 (revision 7)

Verdict received: **CHANGES_REQUESTED — 0 HIGH, 2 MEDIUM, 4 NIT**, reviewed at `32b632e3`
against revision 6, with the first review's thirteen findings and the intervening review's nine
**all confirmed resolved against the tree**. **All 6 are resolved; none is backlogged and none is
ignored.** Every repository fact the review asserted was re-read before acting on it and every
one held; the one Wix claim (finding 5) was re-fetched from the live markdown rendition rather
than taken on the review's word. Where re-measuring produced something the review did not say, it
is marked *and more so*.

No verdict in §1 changed. No architecture changed. The locked decisions were not relitigated:
coupons stay **Option B** — our `coupon_store` table is the issuance ledger kept for idempotency,
Wix does the discount arithmetic only; gift cards stay **Wix-native (A)** with retirement
**source-only and gated on §0.1 condition 3**, so the `TransactWriteItems` concurrency fix stays
until retirement is proven safe; **Loyalty and Referral remain entirely out of scope** per §1.5
and nothing below adds a seam for them.

| # | Sev | Disposition | Where |
|---|---|---|---|
| 1 | MEDIUM | **Fixed by taking the first of the three resolutions and writing it in all three places, as the finding asked.** `redeem()` and `void()` each gain a keyword-only `sleep: Callable[[float], None] = time.sleep`, threaded to `_transact_with_retry` through the committer exactly as `clock: Clock = _default_clock` is threaded today — verified in the tree: `redeem` at `gift_card_store.py:1172-1174` and `void` at `:1395` both already carry `clock` as a keyword-only defaulted parameter, so the parallel the design claimed is real and the new parameter is the same shape. §5.3 gains a blockquote stating it **as a public signature change**, which is the treatment `credit()`'s `once_key` removal already gets in the same section; §8's Modified row names it beside that removal, so the module's public surface is still described in one place; and §7's row now names the literal call `redeem(..., sleep=lambda _s: None)` / `void(..., sleep=lambda _s: None)` rather than the property "an injected no-op sleeper". The two rejected routes are recorded with their costs: monkeypatching `gift_card_store.time.sleep` would make "injected" and the `clock` analogy wrong in four places, and calling `_transact_with_retry` directly puts the exhaustion assertion's second half — *the balance did not move* — out of reach. **And more so:** the caller inventory was measured rather than asserted. The finding's suggested wording named "the two gift-card handlers, the three provisioners and `scripts/provision_checkout.py`"; the actual production callers of these two functions are **one file, two lines** — `wix-giftcard-spi/handler.py:310` (`store.redeem`) and `:341` (`store.void`) — and the design says that instead, because an inventory that overstates its own blast radius is the kind of claim a reader stops checking | §5.3, §5.3.1, §7, §8 |
| 2 | MEDIUM | **Fixed by deleting the stale enumeration, not by updating it — one authoritative key list per contract.** The clear-code bullet in §2.5 now carries only its actual subject (*"the clear code is not among the keys enumerated above"*) and says in terms why the list was removed: revision 6 stated the key set twice, and the second copy went stale the moment `disabled` and `expirationDate` were added to close the intervening review's finding 4. The seven-key paragraph is the single source. **And the statement is now enforced rather than made:** §2.4 Group C gains a row asserting `set(result) == {"giftCardId", "codeLast4", "balancePaise", "currency", "resolved", "disabled", "expirationDate"}` on a **create** result **and** on a **resolve-hit** result, with the assertion message naming *branch-independence* as the property. The finding's diagnosis of why this mattered is exactly right and is recorded in §2.5: an implementer following the five-key bullet ships five keys on create and seven on resolve, every other Group C row still passes, and the branch-independence guarantee the dead-card fix rests on is silently false. **And more so:** the row is also the thing that stops a future key being added to one path only, which is the same asymmetry in the other direction | §2.5, §2.4 C |
| 3 | NIT | **Fixed — the void committer is named `_commit_void`, with a signature, mirroring the redeem side.** §5.3 now specifies `_commit_void(table, digest, transaction_key, amount, now, *, sleep=time.sleep)` and states that the void transaction is assembled in that helper rather than inline in `void()` — the question the finding noted was never answered. The name replaces the phrase "the void committer" in §5.3.1's conflict row, §5.5's AST-guard row, §7's access-pattern row and §8's Modified row. The reason is written down where the name is introduced: §5.5's guard asserts the **names** of `_transact_with_retry`'s two callers, so an unnamed twin leaves the implementer choosing between `{"_commit_redemption", "_commit_void"}` and `{"_commit_redemption", "void"}` — two guards asserting different things. §15's row 2 is annotated rather than rewritten, since it is a record of what revision 6 said | §5.3, §5.3.1, §5.5, §7, §8 |
| 4 | NIT | **Fixed, and the review's reading of the tree was re-derived and confirmed.** The row now says **three** assertions move, not two, and names the third: `decrements[0]["ExpressionAttributeValues"][":neg"] == -40000` at `tests/test_gift_card_store.py:286` — read directly, inside the test at `:274-290`, exactly as the finding describes. Post-fix `:neg` passes through `_marshal`, so the value becomes `{"N": "-40000"}` and the bare integer comparison fails; the repair is to compare the AttributeValue form, and the row states that the `^-?[0-9]+$` check in §5.6 is what owns the **integer-paise** property at that hop, so this assertion is checking marshalling rather than the money rule. **And more so:** the row records *why* an under-count matters even when the failure is loud — §5.5's own standard is that *"the suite went green" is not evidence*, and an enumeration short by one is precisely what makes a green suite misleading | §5.5 |
| 5 | NIT | **Fixed by re-quoting, which is the stronger of the two options offered, and the measurement was re-run here rather than inherited.** Fetched `create-a-coupon.md` directly (**HTTP 200, 24,306 bytes**) and re-measured: `DoubleValue`, `Int64Value`, `Int32Value`, `permissionsInfo` and `destinationPath` each return **0** matches — the finding is exact — while every underlying fact holds in the rendition's own syntax. §3.1's cells now quote that syntax with line numbers: `name: minimumSubtotal \| type: number \| … \| validation: format double` (`:60`), `name: startTime \| type: string \| … \| validation: minimum 1000000000000, format int64` (`:70-71`), `name: usageLimit \| … \| validation: format int32` (`:72-73`), `URL: https://www.wixapis.com/stores/v2/coupons` (`:50`), and `## Permission Scopes:` / `Manage Coupons: SCOPE.DC-COUPONS.MANAGE-COUPONS` (`:17-18`). The two legacy wordings that a reader might still look for — `permissionsInfo`/`COUPONS.MANAGE` in §3.1 and `sourcePath`/`destinationPath` in §1.3 — are **marked legacy, from the pre-404 blob, fact re-confirmed from the `.md`**, which is the treatment §3.3 already gave the premium-plan claim. A new paragraph under §3.1's table states the whole repair and states that **§3.0's halt rule did not fire**, because none of the five is a V1-V4 row. No fact changed and no verdict moved — this was provenance, in the one section whose entire value is provenance | §3.1, §1.3 |
| 6 | NIT | **Fixed both ways the finding allowed, because they are cheap and they cover different readers.** The two Group B rows are written out in the typed form — `expect_http_error(method="POST", endpoint="/stores/v2/coupons", status=…)` — **and** a sentence above the table states once that the Served column names queue calls in their full keyword-only form, with a bare response body in the column being shorthand for `expect(method=…, endpoint=…, body=…)` on that row's own method and endpoint. §2.3's prose reference to `expect_http_error(status)` is corrected to the keyword form too, since it was the third positional use and the one a reader meets first | §2.3, §2.4 B |

**What the review asked to be kept, and is kept.** Both confirmed HIGH mechanisms, untouched:
`card_code(*, reference_id, pepper)` as `hmac.new(pepper, CODE_DOMAIN_TAG + reference_id,
sha256)` under the **existing** `wecare/wix/giftcard-spi:code_pepper` with no new secret name,
`pepper` keyword-only with no default and asserted so from the AST signature, `demo_code` renamed
and fenced by the three-node-type AST walk over `amplify/`, `idempotency_key(reference_id)`
unchanged, and the 20-character output sitting at Wix's documented `maxLength 20` ceiling; and the
two-guard split with the AST arm at presence-and-location only and
`assert_transaction_items_are_exact_key_updates(store)` reading `calls` rather than `applied`,
refusing an empty recording, returning its count, and called from the four transaction-driving
tests. Also kept: `money.positive_paise` reconciled with `Money.__post_init__` named by what it
enforces; the byte-exact create body with `source` required and `expirationDate` named;
`codeSuffix` read rather than `code` parsed, with `CODE_SUFFIX_MISSING` and no fallback; the typed
`expect(*, method, endpoint, status=200, body=None, raw=None)` queue with the **recording count**
as the named enforcement; §3.0's halt rule and the record of it firing on its own author; and
`tests/test_demo_coupon_giftcard_sample.py` as the demo's anti-rot enforcer with **no workflow
modified**.

**Scope and prohibitions, re-checked after revision 7.** The material footprint of this revision
is: one additive keyword-only parameter on each of `redeem()` and `void()`, one named helper
(`_commit_void`) that revision 6 already required but did not name, one new Group C assertion row,
one corrected Group B shorthand, one corrected test-change enumeration, and five re-quoted
provenance cells. **No file moved between the New, Modified, Read-only and Out-of-bounds tables,
and no new file is introduced.** No file in the out-of-bounds list gained an edit —
`ecommerce/checkout/handler.py`, `payment_readiness.py`, `payments/razorpay-webhook/handler.py`,
everything under `amplify/functions/messaging/` and `.worktrees/direct-razorpay-20261002` are
untouched — and `coupons/handler.py` is still **driven, not modified**. No deploy, no
provisioning, **no live Wix write of any kind**; no `secretsmanager get-secret-value` in any
spelling — the pepper and the API key appear only as secret **names**; integer paise, explicit
INR, no floats, `Decimal(str())` only where a DynamoDB number re-enters arithmetic;
resolve-before-generate on both issuance keys; and the bearer-value gift-card code stays keyed,
domain-separated, never returned to a caller and never logged in clear. Loyalty and Referral are
designed nowhere. No live-send flag, no payment capture, refund or payment-configuration
mutation, nothing deleted, and **no guard weakened** — finding 2 was resolved by *adding* an
assertion, and finding 1 by widening a public signature so the promised test can exist at all.

---

## 17. Resolution of review findings — the re-review in `design-review2.json`, 2026-10-02 (revision 8)

Verdict received: **CHANGES_REQUESTED — 0 HIGH, 3 MEDIUM, 4 NIT**, reviewed at `32b632e3`
against revision 7, with the first review's thirteen findings, the intervening review's nine and
the preceding re-review's six **all confirmed resolved against the tree**. **All 7 are resolved;
none is backlogged and none is ignored.** Every repository fact the review asserted was re-read
from the tree before acting on it, and **every one held** — including the three that contradicted
this document's own numbers. Where re-measuring produced something the review did not say, it is
marked *and more so*.

No verdict in §1 changed. No architecture changed. The locked decisions were not relitigated:
coupons stay **Option B** — our `coupon_store` table is the issuance ledger kept for idempotency,
Wix does the discount arithmetic only; gift cards stay **Wix-native (A)** with retirement
**source-only and gated on §0.1 condition 3**, so the `TransactWriteItems` concurrency fix stays
until retirement is proven safe; **Loyalty and Referral remain entirely out of scope** per §1.5
and nothing below adds a seam for them.

| # | Sev | Disposition | Where |
|---|---|---|---|
| 1 | MEDIUM | **Fixed by taking the review's "better still" option — the per-test literal is deleted and the property it stood in for is asserted directly — after first deciding the behaviour the count depended on.** Every measured fact was re-verified here. `FakeTable.arm_failure` arms **once** (`fail_on.pop`, `tests/coupon_fake_dynamo.py:246`); `calls.append(...)` precedes `_fail_if_armed(...)` in every operation (`:253/:255`, `:267/:268`, `:275/:280`), so an armed-and-failed transaction **is** recorded; and a bare `FakeClientError("ProvisionedThroughputExceededException")` is not a cancellation, so the retry in each test is the test's own second `void()` call. Counts re-derived: caller 3 → `2`, caller 4 → **`3`**, caller 5 → **`4`**. The 3-vs-4 ambiguity was closed first, because no number could be stated without it: **§5.3.1 now DECIDES that a duplicate `void()` refuses at the pre-read, before any transaction is opened**, which is today's behaviour at `gift_card_store.py:1441` (`if original.get("credited") is not False: raise AlreadyVoided`, with no write), is one conditional write cheaper on every duplicate void, and is what `test_a_void_latched_before_the_credited_flag_existed_is_never_re_credited` already asserts. §5.3.1's error table is re-headed **"Decided by"** and names the pre-read for the `True` and absent rows, with the transaction's two conditions restated as the **concurrency re-check** — which keeps `attribute_exists(credited)`'s diagnosability argument intact, since a race is the one route by which the absent case reaches a cancellation at all. Then the literal went: each caller asserts `seen >= 1` or `seen >= 2` **plus** `{_committer_of(kwargs) …} == {"redeem", "void"}`, discriminated on the `ADD balancePaise :neg` vs `:amount` fragment `_is_balance_move` already reads, so *"neither committer is the silently missing one"* is asserted rather than inferred from a total. The caller enumeration is stated **once**, as a numbered six-row table in §5.5, and §7, §8 and §15 cross-reference it instead of restating a count — the three sections had carried three different numbers (six, "four" over an enumeration of five, and "four places"). **And more so:** the decision has a consequence the finding did not reach. §5.5 and §8 both had the legacy-`credited` test **changing** — "now asserts the transaction cancelling on `attribute_exists(credited)`" — which under the pre-read decision is false and would have had an implementer open a conditional transaction purely to cancel it. That test moves from the edited set to the **re-run-without-edit** set, and §8's count moves from seven updates to six updates plus three re-runs. **And more so, a second time: the identical ambiguity sits on the REDEEM side and the review did not reach it.** §5.3's *"claim already `settled`"* row read as a post-cancellation outcome, but `redeem()` already short-circuits a settled claim before any money move — the conditional claim `_put` loses, the existing claim is read, and `if existing.get("settled")` returns the replay answer at `gift_card_store.py:1237-1242` with `_decrement` never called. Left as it was, the two redeem callers' counts would have been undecidable for exactly the reason the void ones were, and the next review would have found it. Both tables now name the pre-read as the primary decision and the transaction's condition as the **concurrency re-check**, which is also what the module's own claim that the two strands *"fail and recover identically"* requires | §5.3, §5.3.1, §5.5, §7, §8, §15 |
| 2 | MEDIUM | **Fixed by asserting the real property, and by asserting the weakness positively so the strength is capable of failing.** The review's computation was reproduced exactly: for `R = "wd-gc-sample-2026-10-02"`, `demo_code(R)` is `WDGCB4A4841861208FA8` and `idempotency_key(R)` is `wd-gc-b4a4841861208fa8…311d`; `demo_code in key` and `demo_code.lower() in key` are **both `False`**, because `card_code` upper-cases and the prefixes differ (`WDGC` against `wd-gc-`). So revision 7's *"not a prefix, suffix or substring"* row was **true of the unkeyed derivation too** and could not detect the defect it was added for. §2.4 Group C now compares case-normalised digest **bodies** via `_digest_body(v) = v.lower().removeprefix("wdgc").removeprefix("wd-gc-")`, in both directions for `card_code`, **and** asserts `_digest_body(demo_code(R)) in _digest_body(idempotency_key(R))` — the positive line, which is the mutation test written into the suite: unkey `card_code` and lines 1 and 3 contradict each other, so one must go red. The computation is in the document so a reader does not have to take it on trust. The domain-separation row is restated honestly: `card_code` never returns its digest, so the test **recomputes the tagged HMAC** and what it pins is the presence of `CODE_DOMAIN_TAG`, not an opaque digest comparison — and the row says so instead of claiming the stronger thing. The `demo_code` docstring's false sentence is replaced with the true and more dangerous one: *both values expose the same unkeyed sha256 digest of the same input, so either value yields the other*, with the shared fragment named. §7's row is rewritten to match, since §7 was naming the unfalsifiable assertion as proof. **And more so:** the review called this "a redundant guard that cannot fail rather than an unprotected property", and that is right — the keying is genuinely pinned by the two-pepper row, `CODE_DOMAIN_TAG`, and the keyword-only pepper with no default, all of which are untouched. It is fixed anyway and at full length, because this document's standard is that a guard which passes on any code is already deleted and nobody can tell, and because §7 was advertising it | §2.4 C, §2.5, §7, §14 |
| 3 | MEDIUM | **Fixed by scoping the rule to what the rule is for, and by writing the permission down with its reason — not by restating the rule or by hiding the division.** The contradiction is exact: §5.6 certified *"nothing divides"* in the one section that re-checks the money rules **against this change**, while §5.3 of the same revision specified `0.05 * 2 ** n` seconds plus `_secrets.randbelow(25) / 1000` — a float literal and a true division. The existing row becomes **"no float arithmetic on an amount … nothing divides an amount"**, and a new row states the retry delay as a **duration, not an amount**: float arithmetic, deliberately permitted, never stored, never compared for equality, never reaching an amount, never crossing `_marshal`. The mechanical reason the gate stays green is written down rather than predicted — `test_no_float_is_constructed_anywhere_on_the_store_money_path` (`:1066`) monkeypatches `builtins.float`, and neither a float **literal** nor `int.__truediv__` calls it — and the absence of an AST float gate over `gift_card_store.py` is stated, since that is the other thing a reader would otherwise assume is catching this. The integer-millisecond alternative the review offered is recorded as **considered and rejected**, with its cost: it still divides, it only moves the division to the last expression, and it buys a true sentence about the module at the price of a less readable one about the delay. **And more so:** the note says why the unqualified version was actively harmful rather than merely imprecise — it invites either a wrong rejection of this change or a wrong generalisation that floats are fine here, and neither is recoverable from the sentence itself. A rule stated more broadly than its reason is a rule that gets argued with instead of followed | §5.6 |
| 4 | NIT | **Fixed, and the neighbouring convention applied to both halves of the row rather than one.** §14 row 1 gains the superseded annotation at its head — *the domain tag was added in revision 6, see §15 finding 6, and the construction in §2.5 is authoritative; the untagged form below is pre-revision-6 and must not be copied* — in the same form row 2 of that table already carries. **And more so:** the same row's *"and more so (a)"* clause claimed the code was *"a literal **prefix** of the key"*, which finding 2 has just measured to be false in any case form, and that it is guarded by a "not a substring" assertion, which finding 2 has just measured to be unfalsifiable. Both halves are annotated and pointed at §17 finding 2, because a reader who reaches §14 first and copies either sentence inherits the wrong mental model of what the guard proves | §14 |
| 5 | NIT | **Fixed — the node types are spelled out, with the gate's existing filter quoted so the mismatch is visible rather than described.** Verified from the tree: the gate's call-finding loop is `if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)): continue` (`tests/test_gift_card_store.py:1105-1106`), which finds `table.meta.client.transact_write_items(...)` and **not** `_transact_with_retry(...)`, an `ast.Name` call; and the `FunctionDef`-owner walk at `:1119-1124` is reusable exactly as revision 7 claimed. §5.5 now says which predicate owns which fact: fact one uses the existing `ast.Attribute` filter; facts two and three need `isinstance(node.func, ast.Name) and node.func.id == "_transact_with_retry"`; the owner walk is shared by all three. **And more so:** the review's severity reasoning is adopted into the text rather than left in the review — this fails loudly rather than vacuously, which is a smaller hazard than the two forms this guard has already had, but it is *this* guard, and Group D spells out node types for precisely this reason | §5.5 |
| 6 | NIT | **Fixed, and the `resolved` question the finding raised is answered rather than deferred.** `find_by_code`'s one-hit branch now enumerates **the same seven keys** `create` returns, inline in the branch block instead of pointing at a per-key source table. `resolved` **does** belong on a finder, and the reason is structural rather than aesthetic: `create`'s resolve branch returns `find_by_code`'s view unchanged, so one normaliser produces both returns and one assertion can cover both — a six-key finder and a seven-key creator would need two normalisers and two assertions, which is the exact shape of the five-versus-seven drift the preceding re-review caught. The branch also states that `resolved` is **always `True`** here, since a miss returns `{}` and never a dict with `resolved: False`. §2.4 Group C's branch-independence row gains a **third subject** — a direct `find_by_code` one-hit result, beside the create and resolve-hit results — so one row now covers both public functions and its message names the widened property | §2.5, §2.4 C |
| 7 | NIT | **Fixed in both places, and the reason the omission mattered is stated.** §5.4's `_InterleaveAtBalanceMove` docstring now says it overrides **both** `update_item` and `transact_write_items`, awaiting its latch **before** delegating to `super()` in each, so the table lock is never held across a wait; and a paragraph beneath it names why the clause is necessary — `_MarkerWriteFails` and `_CreditThrottles` each override one method, so the single-method shape is the pattern this suite teaches, and copying it here yields a subclass that latches the pre-fix representation and **silently stops latching anything the moment the fix lands**, degrading the test into the unsynchronised race §5.4 exists to avoid. §2.6's lock note gains the matching clause, so the rule and its one two-method consumer are stated together instead of the note implying every latch is single-method | §5.4, §2.6 |

**What the review asked to be kept, and is kept.** Everything it confirmed, untouched: both HIGH
mechanisms — `card_code(*, reference_id, pepper)` as `hmac.new(pepper, CODE_DOMAIN_TAG +
reference_id, sha256)` under the **existing** `wecare/wix/giftcard-spi:code_pepper` with no new
secret name, `pepper` keyword-only with no default and asserted so from the AST signature,
`demo_code` renamed and fenced by the three-node-type AST walk over `amplify/`,
`idempotency_key(reference_id)` unchanged and unkeyed, and the 20-character output at Wix's
documented ceiling; and the two-guard split, with the AST arm at presence-and-location only and
`assert_transaction_items_are_exact_key_updates(store)` reading `calls` rather than `applied`,
refusing an empty recording and returning its count. Also kept: the architecture, the two
verdicts, the transport boundary at `urlopen`, the `TransactWriteItems` fix shape, the shared
`_transact_with_retry` as the module's only transaction site with `_commit_redemption` and
`_commit_void` as its two callers, the owner checklist, `money.positive_paise` reconciled with
`Money.__post_init__` named by what it enforces, the byte-exact create body with `source` required
and `expirationDate` named, `codeSuffix` read rather than `code` parsed with `CODE_SUFFIX_MISSING`
and no fallback, the typed `expect(*, method, endpoint, status=200, body=None, raw=None)` queue
with the **recording count** as the named enforcement, §3.0's halt rule and the record of it firing
on its own author, and `tests/test_demo_coupon_giftcard_sample.py` as the demo's anti-rot enforcer
with **no workflow modified**.

**The family this closes, named once because five revisions is a pattern and not a coincidence.**
Revision 4's gate failed on correct code; revision 5's replacement passed on any code; revision
6's call-site pin described a layout the code would not have; revision 7's expected counts were
written against the intent of three tests rather than what they execute, and two of its
assertions could not fail. Every instance is the same error: **a literal, a count or an absolute
standing in for a property.** The repair this revision makes is not three more literals — it is
the removal of the instrument. Transaction totals are replaced by a committer **set**; the
substring comparison is replaced by a digest-body comparison **with its own mutation test**; and
the absolute "nothing divides" is replaced by a rule **scoped to its reason**. Each of those
survives a test gaining a call, a prefix changing case, or a duration being computed, which the
numbers they replace did not.

**Scope and prohibitions, re-checked after revision 8.** The material footprint is: one decided
behaviour in §5.3.1 (the pre-read refusal, which is today's code and therefore a *documentation*
change, not a code one), one re-headed error table, one numbered caller table replacing three
disagreeing counts, three rewritten Group C assertions, one corrected docstring, two new §5.6
rows plus a rationale note, two node-type predicates spelled out, one enumerated return branch,
one widened Group C subject, two override clauses, and three superseded annotations on historical
rows. **No file moved between the New, Modified, Read-only and Out-of-bounds tables, no new file
is introduced, and one test moved from the edited set to the re-run set** — which makes the
footprint smaller than revision 7's, not larger. No file in the out-of-bounds list gained an edit
— `ecommerce/checkout/handler.py`, `payment_readiness.py`,
`payments/razorpay-webhook/handler.py`, everything under `amplify/functions/messaging/` and
`.worktrees/direct-razorpay-20261002` are untouched — and `coupons/handler.py` is still **driven,
not modified**. No deploy, no provisioning, **no live Wix write of any kind**, and no outbound
request at all this revision; no `secretsmanager get-secret-value` in any spelling — the pepper
and the API key appear only as secret **names**; integer paise, explicit INR, no float on any
amount (the one permitted float is a `sleep` duration, scoped and argued in §5.6),
`Decimal(str())` only where a DynamoDB number re-enters arithmetic; resolve-before-generate on
both issuance keys; and the bearer-value gift-card code stays keyed, domain-separated, never
returned to a caller and never logged in clear. Loyalty and Referral are designed nowhere. No
live-send flag, no payment capture, refund or payment-configuration mutation, nothing deleted,
and **no guard weakened** — findings 1 and 2 were resolved by making two guards *able to fail*,
finding 3 by scoping a rule to its reason rather than relaxing it, and findings 5, 6 and 7 by
stating mechanisms that were previously left to the implementer.
