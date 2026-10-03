# Wix contract verification transcript — 2026-10-02

Design `.agents/tasks/wix-coupon-giftcard-sample-20261002/design.md` revision 8, §3.0 and §3.0.1.
This is implementation step 0: the four verdict-carrying facts are re-measured **before any code
is written**, and §3.0's HALT rule is applied to the result.

**Verdict: no halt.** V1, V2, V3 and V4 all agree with the design. The non-verdict rows measured
alongside them also agree, so nothing was corrected in place.

Fetched with `curl -sSL` against the markdown rendition (`.md` appended), which is the form that
works today. **The pre-revision-5 URL set under `/docs/api-reference/ecom/...` now 404s and
returns a ~4 MB schema-free JavaScript shell** — a re-run against the old form reads *absent* when
the fact is *present*, which is why the URL form used is recorded per fetch below rather than
left implicit.

## Fetches

| # | URL in the form used | HTTP | Bytes |
|---|---|---:|---:|
| 1 | `https://dev.wix.com/docs/api-reference/business-solutions/coupons/coupons/create-a-coupon.md` | HTTP 200 | 24306 |
| 2 | `https://dev.wix.com/docs/api-reference/business-solutions/coupons/coupons/query-coupons.md` | HTTP 200 | 15406 |
| 2b | `https://dev.wix.com/docs/api-reference/business-solutions/coupons/coupons/filter-and-sort.md` | HTTP 200 | 2400 |
| 3 | `https://dev.wix.com/docs/api-reference/business-solutions/gift-cards/gift-cards/create-gift-card.md` | HTTP 200 | 21610 |
| 4 | `https://dev.wix.com/docs/api-reference/business-solutions/gift-cards/gift-cards/query-gift-cards.md` | HTTP 200 | 20909 |

Five pages, five `HTTP 200` lines, one per fetch.

## V1 — `idempotencyKey` is ABSENT from `CreateCouponRequest` — **confirmed**

Carries the coupon verdict **(B)**. This row is an **absence**, so the command is written to make
the absence the visible result: a count, not an unremarked silence.

```
$ curl -sSL "$CP/create-a-coupon.md" | grep -c idempotencyKey
0
$ echo $?            # grep's own status, recorded because 0 matches is exit 1
1
```

`0` occurrences across 24306 bytes. The finding **is** the zero count, and `grep` exiting `1` is
the evidence that it searched and found nothing rather than failing to search.

Schema fragment from the same page, showing what Create Coupon *does* take, so the absence is
read against a page that was genuinely parsed:

```
 URL: https://www.wixapis.com/stores/v2/coupons
 Method: POST
 name: moneyOffAmount | type: number | description: Discount as a fixed amount.
 name: startTime | type: string | description: Coupon valid from this date and time, in
   milliseconds. For example, `"1554066000000"`. | validation: minimum 1000000000000, format int64
```

Two non-verdict facts our adapter depends on, both unchanged: `moneyOffAmount` is a JSON
**number** (so `wix_coupons._rupees` emitting an `int` is right, and a decimal string would be the
wrong JSON type), and `startTime` is a **quoted** string-encoded int64 (so Wix's string convention
demonstrably does not extend to the money fields).

## V2 — `Query Coupons`' `filter` is typed `string` — **confirmed**

```
$ curl -sSL "$CP/query-coupons.md" | grep -o 'name: filter | type: [a-z]*'
name: filter | type: string
name: filter | type: string
```

```
 URL: https://www.wixapis.com/stores/v2/coupons/query
 Method: POST
 - name: filter | type: string | description: Filter string (e.g., when {"expired":"true"},
     expired coupons will be returned).
 - name: sort | type: string | description: Sort string.
```

A `string`, not an object — so a coupon query is a double-encoded JSON string, unlike the
gift-card query's real JSON object. Two occurrences because the page documents the REST and SDK
shapes separately and both agree.

## V2b — the clause that did NOT survive: the coupon operator map exists — **confirmed present**

§3.0's row V2 carried a second clause, *"with no operator map"*, which `filter-and-sort.md`
contradicts. Recorded rather than quietly fixed, because it is close to the verdict line:

```
$ curl -sSL "$CP/filter-and-sort.md" | grep 'specification.code'
| specification.code |$eq,$ne,$hasSome,$contains,$startsWith|Allowed|
```

So coupons **can** be filtered by code. It does not move verdict (B), which rests on V1 — the
missing `idempotencyKey` — and §1.3.1 already re-ran the coupon verdict against this evidence.
What it does mean is that `coupon_store` is kept for **idempotency**, not for read-by-code, and
the plan's framing says exactly that.

## V3 — `idempotencyKey` is PRESENT on `CreateGiftCardRequest` — **confirmed**

Carries the gift-card verdict **(A)**.

```
$ curl -sSL "$GC/create-gift-card.md" | grep -o 'name: idempotencyKey.*maxLength 100'
name: idempotencyKey | type: idempotencyKey | description: Unique identifier to prevent duplicate
  gift card creation. Use this to safely retry gift card creation requests. | validation:
  minLength 1, maxLength 100
name: idempotencyKey | type: string | description: Unique identifier to prevent duplicate gift
  card creation. Use this to safely retry gift card creation requests. | validation: minLength 1,
  maxLength 100
```

Present, with its bounds, and it is a **sibling of `giftCard`** in the REST body rather than a
field inside it (line 63 of the rendition sits at the `param name:` indentation, alongside
`param name: giftCard` at line 41). `MAX_IDEMPOTENCY_KEY = 100` and the `1 <= len <= 100`
refusal both follow from this row; an empty key is a refusal, not a "no idempotency" fallback.

## V4 — the `code` operator map is PRESENT on `Query Gift Cards` — **confirmed**

Carries verdict (A) and §2.5's resolve-before-create.

```
$ curl -sSL "$GC/query-gift-cards.md" | grep -o 'field: code | operators: [^|]*'
field: code | operators: $eq, $ne, $in, $exists, $gt, $gte, $lt, $lte, $startsWith
field: code | operators: $eq, $ne, $in, $exists, $gt, $gte, $lt, $lte, $startsWith
```

`$eq` on `code` is documented, so read-by-full-code is a contract rather than a hope. That is the
capability coupons lack and it is why the two verdicts differ.

```
 URL: https://www.wixapis.com/gift-cards/v1/gift-cards/query
 Method: POST
```

## (5) The two reads a resolve hit returns — **confirmed on the Query response**

```
$ curl -sSL "$GC/query-gift-cards.md" | grep -o 'name: \(balance\|currency\|codeSuffix\) |[^|]*'
name: balance | type: Amount | description: Current available balance that can be spent.
  Decreases when the gift card is used for purchases and increases with refunds.
name: codeSuffix | type: string | description: Last 4 characters of the gift card code for
  search and identification purposes.
name: currency | type: string | description: Three-letter currency code in ISO 4217 format.
  For example, `"USD"`, `"EUR"`.
```

`balance` is on the **Query** response, so the resolve path is **one request, not two** — §2.4
Group C's call counts stand. `codeSuffix` is a dedicated read-only field:

```
name: codeSuffix | type: string | ... | read-only: true | validation: minLength 4, maxLength 4
```

Exactly four characters, which is why `codeLast4` reads `codeSuffix` and refuses with
`CODE_SUFFIX_MISSING` rather than falling back to slicing the obfuscated bearer code.

## (6) The required-parameter list — **confirmed, `source` included**

```
$ curl -sSL "$GC/create-gift-card.md" | grep -o 'Required parameters:.*'
Required parameters:  giftCard, giftCard.initialValue, giftCard.initialValue.amount,
  giftCard.currency, giftCard.source
Required parameters:  giftCard, giftCard.initialValue, giftCard.initialValue.amount,
  giftCard.currency, giftCard.source
```

`giftCard.source` is **required**, which is where it was hiding behind revision 4's ellipsis. So
`source` is sent on every create and is not optional on our side either.

## Non-verdict rows measured alongside, all agreeing with the design

| Fact | Measured fragment | Design row |
|---|---|---|
| `code` length bounds | `name: code \| type: string \| ... \| validation: minLength 8, maxLength 20, immutable` | `MIN/MAX_CODE_LENGTH = 8, 20`; our 20-character code sits at the ceiling |
| the returned `code` is obfuscated | *"The `code` field contains the **obfuscated** gift card code, for example, `****-****-****-4444`. Only the returned code is obfuscated. You can still find a gift card by filtering `code` with the full code."* | why `codeSuffix` is read instead of parsed, and why `find_by_code` filters on the full code |
| create returns the clear code | `name: giftCard \| type: GiftCard \| description: Created gift card with the full code visible and unobfuscated. The full code isn't retrievable with the other methods.` | the create response is the **only** place the clear code exists; §16's inherited line item |
| `Amount.amount` | `type: string \| ... decimal string. For example, "10.50"` , `validation: format DECIMAL_VALUE, decimalValue {"gte":"0","maxScale":2}` | `Money.to_wix()` / `Money.from_wix()`; two decimal places, no float |
| `initialValue` | `type: Amount \| required: true \| validation: immutable` | sent on every create |
| `source` enum | `ORDER: Gift card was purchased through an order.` / `MANUAL: Gift card was created manually via API.` | `SOURCE_MANUAL` only; `ORDER` is narrowed out as a provenance claim |
| `expirationDate` | `type: string \| validation: format date-time, immutable` | the Wix key `expiration_iso` maps to; passed through unparsed |
| `disabledDate` | `type: string \| read-only: true \| validation: format date-time` | `disabled = bool(... .get("disabledDate"))`; there is no separate status field |
| `notificationInfo` | `type: NotificationInfo \| description: Email notification settings including recipient, sender, and delivery options.` | writable and **deliberately never sent** — it is a live customer email |
| no Wix-side maximum on `initialValue` | `decimalValue {"gte":"0","maxScale":2}` and nothing more | `MAX_INITIAL_VALUE_PAISE` is **borrowed from the SPI**, not measured from Wix |

## The one limitation of this source, stated so an absence is not over-read

The markdown rendition renders **no `Errors` section for any method**, measured across all five
pages. So `Create Coupon`'s `errors: []` and `Create Gift Card`'s `SITE_IS_NOT_PREMIUM` are
**neither confirmed nor contradicted here**. They are not carried as measured facts by this
transcript. Nothing in the implementation branches on either: `wix_coupons` special-cases no
status because it cannot, and `wix_gift_cards` likewise reduces every non-2xx to the one
`WixEcomError` that `wix_ecom._request` produces.

## What this transcript does not prove

It proves the **documented contract**. It does not prove that this site's API key, with its
current scopes, on an India/INR premium plan, accepts these shapes — that is §0.1 condition 3, it
needs one owner-run live call, and a live Wix write is a standing refusal for the agent. See
`.agents/tasks/wix-coupon-giftcard-sample-20261002/findings.md`.
