# Coupon + gift-card redemption (Section 2) provisioning runbook (2026-10-01)

> STATUS: BLOCKED-ON-ENVIRONMENT. Not executed.
>
> This document is a runbook only. Nothing in it has been run. The sandbox has
> no AWS credentials: `aws sts get-caller-identity` fails, there is no `~/.aws`
> and no `wecare-prod` profile; there is no live Wix tenant and no live Razorpay
> account reachable from here. Every live operation below (concrete provider
> binding, route wiring, IAM, alias move, live monetary test) is reported
> BLOCKED-ON-ENVIRONMENT and must be run by an authorized operator once
> credentials arrive through the sandbox environment, never from a key pasted
> into chat.
>
> This is the Section 2 sibling of
> `docs/execution/website-checkout-provisioning-runbook-2026-10-01.md` and
> `docs/execution/blog-contribution-provisioning-runbook-2026-10-01.md`. The
> coupon + gift-card redemption authority reuses the SAME `wecare-checkout`
> function, the SAME disabled initiation gate, the SAME commerce-keys table and
> the SAME authoritative Razorpay verify/webhook path as the website checkout, so
> most of the groundwork is already covered by those runbooks. This document only
> adds what is specific to Section 2: the abstract redemption-provider seam, the
> `/ecommerce/redemption` route the cart UI calls, and the gift-card reservation
> namespaces.

## Scope and safety rules (read before anything)

- **Account / profile / region:** account `775261844268`, profile `wecare-prod`,
  region `us-east-1`. Every command below assumes
  `--profile wecare-prod --region us-east-1`.
- **A chat-pasted AWS key must never be used, stored or echoed.** The only
  acceptable credential source is the sandbox environment / a configured
  `wecare-prod` profile.
- **Secrets are referenced, never read.** Never call
  `secretsmanager get-secret-value`, never print a secret value. The Razorpay
  API secret (`wecare/razorpay/api`) is referenced by ARN only; it is the SAME
  secret the website checkout already uses. A concrete coupon/gift-card provider
  credential (whatever is chosen at binding time) is referenced the same way.
- **The initiation gate stays DISABLED.** No step here sets
  `CHECKOUT_INITIATION_ENABLED`, and the readiness inputs
  `EXPECTED_CONFIGURATION_NAME` / `EXPECTED_PROVIDER_MID` remain empty. With the
  gate off, both the REDUCED Razorpay payable after a redemption AND a
  zero-remaining (fully gift-card-covered) order are gated: no gateway order, no
  payable attempt, `PAYMENT_INITIATION_DISABLED`. A redemption can never reach a
  live charge until an authorized operator deliberately turns the gate on, and no
  constant in the code can force it on. A zero-remaining order still settles only
  through the authoritative verification path - it never auto-completes from
  browser state.
- **The browser never controls the trusted amount.** Coupon validation and
  discounts, and gift-card balances, are decided by the server/provider in
  integer paise. The cart UI sends a code + action and renders only what the
  server returns. A browser-calculated discount is never trusted anywhere.
- **No third-party provider name in customer-facing UI.** The provider seam is
  abstract; no vendor name ('Gift Up'/'GiftUp'/etc.) appears in the cart UI or
  any customer-facing surface. Whatever concrete provider is bound stays behind
  the seam.
- **`cart_v2`'s blanket rejection is RETAINED.** The standalone
  `cart_v2.CartV2.calculate` contract still raises `CartContractError` on any
  `paymentSummary.giftCards` / split / deferred payment. The secure replacement
  does NOT weaken it: Wix never collects a gift card for us; the server computes
  `authoritative Wix total - verified redemption = Razorpay payable` after an
  authoritative provider balance readback. See `redemption.py` module docstring.
- **Git workflow (this task):** the owner override commits all work to the
  already-checked-out branch `feature/customer-experience-upgrade`, explicit-path
  staging only, no push and no PR (the orchestrator pushes).

### How to confirm the environment blocker is cleared

Run this first. Until it prints the expected account, every section stays
blocked:

```sh
aws sts get-caller-identity --profile wecare-prod --region us-east-1
# expect: "Account": "775261844268"
```

---

## Section 1: bind a concrete redemption provider behind the abstract seam

The redemption authority is handler-free business logic in
`amplify/functions/shared/lambda_utils/ecommerce/redemption.py`
(`apply_coupon` / `verify_gift_card` / `build_payable` / `reserve_redemption` /
`release_redemption` / `commit_redemption` / `refund_redemption` /
`reconcile_reservation`), tested offline exactly like `website_checkout.py`. It
depends on an abstract `RedemptionProvider` protocol with two methods:

- `validate_coupon(code, collection_before_discount_paise, cart_ref) -> CouponAuthority`
- `read_gift_card(code, cart_ref) -> GiftCardAuthority`

Both return server-authoritative integer-paise results and typed reasons
(`APPLIED` / `INVALID` / `EXPIRED` / `INELIGIBLE` / `INSUFFICIENT_BALANCE`). No
vendor-specific code lives in `redemption.py`; the concrete provider is chosen
and bound HERE at wiring time, without touching the money arithmetic, the gate
or the UI.

### Deciding the provider (open question, deferred by design)

Two bindings are possible and the seam supports either:

1. **Wix Headless native.** Wix exposes a coupons API (apply/calculate a coupon
   `code` against a cart/checkout and read the resulting discount) and a
   gift-cards API (resolve a gift-card `code`/number to its remaining balance and
   currency). A Wix-native binding would:
   - For a coupon: call the Wix cart/checkout calculate with the coupon applied
     and read the authoritative discount, converting Wix's decimal amount to
     integer paise via `lambda_utils/ecommerce/money.py` (`Money.from_wix`) at the
     boundary, exactly as `cart_v2` already converts Wix amounts. Return a
     `CouponAuthority(valid=True, reason=APPLIED, discount_paise=...)`, or a typed
     invalid/expired/ineligible when Wix rejects the code.
   - For a gift card: resolve the card to its balance and currency and return
     `GiftCardAuthority(usable=True, reason=APPLIED, balance_paise=...)`.
   - **Verify the exact current Wix REST shapes against the official docs**
     (dev.wix.com, eCommerce coupons and gift-cards) before coding the binding;
     the shapes are versioned and must be read live. Record the exact endpoints,
     scopes and the decimal->paise conversion in a follow-up note.
2. **Third-party system.** A third-party coupon/gift-card provider would
   implement the SAME two methods against that system's API. Its credential is
   stored in Secrets Manager and referenced by ARN only. **Its name must never
   reach the customer-facing UI** - the seam keeps it invisible.

> The choice is deferred intentionally (the task's open question). The code does
> not presume either; it models the authority as server/Wix-authoritative. The
> binding is a single new class implementing `RedemptionProvider`, injected into
> whatever handler wires `/ecommerce/redemption`.

### What the binding must guarantee (regardless of vendor)

- Convert every provider decimal amount to integer paise at the boundary; never
  float; reject fractional paise (reuse `money.py`).
- Treat the browser value as a request only. The code is sent to the provider;
  the discount / balance comes back from the provider. A browser-supplied amount
  is never read.
- Map the provider's own errors to the typed reasons; never surface a provider
  body string or vendor name to the browser.

---

## Section 2: the `/ecommerce/redemption` route on `wecare-checkout`

The cart UI (`src/pages/cart.tsx`, `RedemptionPanel`) POSTs
`{kind, action, code}` to `${NEXT_PUBLIC_API_BASE}/ecommerce/redemption` where
`kind` is `coupon` or `giftCard` and `action` is `apply` or `remove`. The
response is the browser-safe projection the UI renders:
`{state, couponReason|giftCardReason, discountPaise, giftCardAppliedPaise,
remainingPayablePaise}`. No amount is ever sent by the browser.

The handler that owns this route (to be added inside the EXISTING
`wecare-checkout` function, alongside the website checkout and contribution
handlers) must:

1. Resolve the proven customer session and the live authoritative cart total via
   the retained `cart_v2` / `checkout_pricing` path (coupon discount feeds the
   collection BEFORE the fee/GST calculator; gift-card redemption subtracts from
   the FINAL calculator total AFTER fee/GST). See the `redemption.py` module
   docstring for the exact split.
2. Call `redemption.apply_coupon` / `redemption.verify_gift_card` with the bound
   provider. For a gift card, `redemption.reserve_redemption` takes the atomic,
   double-spend-safe reservation keyed to the payment attempt.
3. AND the `CHECKOUT_INITIATION_ENABLED` env gate with readiness exactly as
   `checkout/handler.py` does. With the gate off, return
   `PAYMENT_INITIATION_DISABLED` (the UI shows the honest unavailable state);
   never create a gateway order. The reduced/zero payable only reaches the gated
   `website_checkout.prepare_checkout` when the gate is on.
4. Return ONLY the browser-safe projection; never a provider body, a secret, a
   vendor name, or the raw card/coupon code.

Rediscover the current HTTP API id every time (never reuse a stale id):

```sh
aws apigatewayv2 get-apis --profile wecare-prod --region us-east-1 \
  --query "Items[?Name=='wecare-http-api'].ApiId" --output text
# then add POST /ecommerce/redemption -> wecare-checkout:live, mirroring the
# existing /ecommerce/checkout and /ecommerce/contribution integrations.
```

---

## Section 3: gift-card reservation storage (no new table)

The gift-card reservation / rollback / commit lives in the EXISTING commerce-keys
table (`stack-wecare-digital-WixOrderIds`, partition key `orderId`) under three
new logical namespaces minted by `order_keys.py`:

- `GIFTCARD#<cardFingerprint>#<paymentAttemptId>` - the atomic per-attempt
  reservation carrying the authoritative integer-paise figures
  (`authoritativeTotalPaise`, `redemptionPaise`, `razorpayPayablePaise`), state
  `RESERVED` / `RELEASED` / `COMMITTED`.
- `GIFTCARDLOCK#<cardFingerprint>` - the exclusive card-level lock that stops ONE
  card funding TWO live attempts (the cross-attempt double-spend guard), claimed
  conditionally and released when the reservation is released/refunded. An O(1)
  conditional write, NOT a table scan.
- `GIFTCARDCOMMIT#<paymentId|attempt-marker>` - the payment-id-keyed one-time
  commit claim, so one Razorpay capture (or one zero-remaining order) commits a
  redemption exactly once across webhook/callback redeliveries.

No table is created or altered: these are logical key prefixes in the table that
already exists for the website checkout. The card code is never stored - only its
SHA-256 fingerprint keys the rows (`redemption.card_fingerprint`).

### Reconciliation and refunds

- A failed Razorpay leg after a reservation RELEASES it
  (`redemption.release_redemption`), freeing the card lock so the balance is not
  stranded.
- A captured payment COMMITS the redemption exactly once
  (`redemption.commit_redemption`).
- A refund RELEASES a committed redemption back to the card
  (`redemption.refund_redemption`, reason `REFUNDED`); the provider-side balance
  credit is the concrete binding's job (Wix gift-cards credit API or the
  third-party equivalent). The authoritative intent to restore is recorded in the
  reservation row.
- Reconciliation re-derives the figures from the STORED reservation row
  (`redemption.reconcile_reservation`), never from anything the browser relayed,
  mirroring the webhook notes-not-authority rule used by BLOG_CONTRIBUTION and
  partner_billing.topup.

---

## Section 4: IAM (least privilege, reuse the existing role)

No new IAM is required beyond what the website checkout already has: the
redemption handler reads/writes the SAME commerce-keys table and references the
SAME Razorpay secret by ARN. If the concrete provider binding needs a NEW secret
(a third-party API credential), add a single `secretsmanager:GetSecretValue`
statement scoped to that one secret ARN on the EXISTING `wecare-checkout` role -
nothing broader. Record the exact ARN here when the provider is chosen.

---

## Section 5: the no-live-charge verification (gate stays off)

With the gate OFF (the default), confirm the honest posture end to end WITHOUT a
live charge:

- A coupon/gift-card apply returns `PAYMENT_INITIATION_DISABLED`; the cart UI
  shows "Discounts and gift cards are not available right now." and offers no way
  to transact.
- No gateway order exists for any attempt; `order_keys.resolve_gateway_order`
  returns `None`.
- A gift-card reservation may be recorded (it carries no money and no gateway
  order), but no capture and no commit occur while the gate is off.

Turning the gate ON for a deliberate, authorized live monetary test is the SAME
procedure as the website-checkout runbook's live-test section and inherits all of
its safety rules. It is BLOCKED-ON-ENVIRONMENT here and must not be executed from
this sandbox.

---

## Status summary

| Step | State |
| --- | --- |
| `redemption.py` seam + arithmetic + reservation/rollback/commit/refund | DONE (source + tests) |
| `order_keys.py` `GIFTCARD#` / `GIFTCARDLOCK#` / `GIFTCARDCOMMIT#` | DONE (source + tests) |
| Cart coupon + gift-card UI (gated, honest, no vendor name) | DONE (source + vitest) |
| Concrete provider binding (Wix-native or third-party) | BLOCKED-ON-ENVIRONMENT (no live Wix/provider) |
| `/ecommerce/redemption` route + IAM | BLOCKED-ON-ENVIRONMENT (no AWS creds) |
| Live monetary test | BLOCKED-ON-ENVIRONMENT (gate stays off) |
