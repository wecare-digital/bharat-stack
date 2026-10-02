# Wix + Razorpay Checkout — current design, revision 4

Status: implementation branch `feat/wix-razorpay-checkout-phases-1-2`. Payment initiation remains OFF.

This document is the current checkout authority for the website path. Where an older checkout,
coupon, or gift-card document disagrees with this file, this file wins for the website checkout.
The design was re-derived on 2026-10-02 from the current WECARE.DIGITAL Wix site and current Wix
REST documentation rather than from the older Checkout V1 / custom gift-card assumptions.

## Architecture

- **Wix Stores Catalog V3 + eCommerce Cart V2** own catalogue, cart, inventory, delivery, supply
  tax, coupons, gift-card calculation, and the commerce/order record.
- **Razorpay Standard Checkout** is the website payment gateway. WECARE never routes a website
  shopper to a Wix-hosted checkout and never uses Wix as the website PSP.
- The browser never supplies a trusted amount. Wix Calculate Cart produces the supply-side total;
  WECARE's central integer-paise calculator adds the convenience fee and GST on that fee.
- A Razorpay result is not paid state until the server verifies the callback binding and reads the
  captured payment from Razorpay.
- After verified capture WECARE creates the external Wix order, records the Razorpay payment with
  Wix Order Transactions Add Payments, settles any Wix-native gift-card leg, and marks the Cart V2
  cart completed. Every external mutation is independently idempotency-guarded.
- `CHECKOUT_INITIATION_ENABLED` stays absent/off until all finalization, routes, IAM and live
  readbacks are verified.

## Current Wix contracts used by this design

### Cart V2

Current Wix Cart V2 is the purchase-flow API. Cart V1 and Checkout V1 are legacy and are not a
source of new request shapes.

- Add Coupon:
  `POST /ecom/v2/carts/{cartId}/add-coupon`
  body `{"coupon":{"code":"..."}}`.
  Source: https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/add-coupon
- Remove Coupon:
  `POST /ecom/v2/carts/{cartId}/remove-coupon`
  body `{"couponId":"..."}`.
  Source: https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/remove-coupon
- Add Gift Card:
  `POST /ecom/v2/carts/{cartId}/add-gift-card`
  body `{"giftCard":{"code":"..."}}` with optional `redeemAmount`.
  Current Wix schema allows one gift card today.
  Source: https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/add-gift-card
- Remove Gift Card:
  `POST /ecom/v2/carts/{cartId}/remove-gift-card`
  body `{"giftCardId":"..."}`.
  Source: https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/remove-gift-card
- Calculate Cart:
  `POST /ecom/v2/carts/{cartId}/calculate` with `{"refreshCart":true}`.
  The bound result supplies `calculationId`, `priceVerificationToken`, `priceSummary`, and
  `paymentSummary`.
  Source: https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/calculate-cart
- Mark Cart As Completed:
  `POST /ecom/v2/carts/{cartId}/mark-cart-as-completed` with the externally-created `orderId`.
  This closes a cart after an order was created externally and does not collect payment.
  Source: https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/mark-cart-as-completed

**Place Order is intentionally not used.** It may collect payment through Wix. Razorpay is the
website gateway, so a payment-collecting Wix endpoint is structurally outside this path.

### Orders and externally collected Razorpay payment

- Create Order:
  `POST /ecom/v1/orders`. This is Wix's current Orders API method for external/manual-system
  orders.
  Source: https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/orders/orders/create-order
- Add Payments:
  `POST /ecom/v1/payments/orders/{orderId}/add-payment`. Wix explicitly states this records a
  payment and **does not charge**. WECARE records only the amount authoritatively verified as
  captured by Razorpay.
  Source: https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/orders/order-transactions/add-payments

## Coupons

Coupons are **Wix-authoritative** for website checkout.

A customer supplies a code only. The server applies that code to the customer's server-owned Cart
V2 cart and Wix decides validity, eligibility and discount amount. The browser can never supply a
discount amount. The discounted Wix `priceSummary.total` is the collection amount fed into
WECARE's convenience-fee/GST calculator.

Older custom coupon-table code may remain for other dormant/admin experiments, but it is not the
website checkout price authority.

## Wix-native gift cards

WECARE.DIGITAL has Wix Gift Cards installed. Website checkout therefore uses Wix-managed gift-card
state, not the older custom DynamoDB balance / Gift Card Service Plugin design.

Cart V2 Add Gift Card is the **quote-time authority**. Calculate Cart returns one
`paymentSummary.giftCards[]` entry today, its `redeemAmount`, `totalAfterGiftCards`,
`payNow`, and `requiresPaymentAfterGiftCard`.

The order total remains:

`Wix collection after coupon + WECARE convenience fee + GST on that fee`.

The Razorpay leg is:

`full order total - Wix-authoritative gift-card redemption`.

A partial Wix gift card therefore never causes the browser to invent a remainder. The server
stores the full order total separately from the Razorpay charge.

For an externally-created Wix order, the gift-card leg is settled with Wix Order Billing Redeem
Gift Card:

`POST /ecom/v1/order-billing/redeem-gift-card`

using the verified order id, gift-card code, authoritative redemption amount and INR. It creates
the Wix gift-card payment transaction and deducts the Wix-managed balance.

Source: https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/orders/order-billing/redeem-gift-card

Gift-card bearer codes are never logged and are never stored in plaintext. A code that must
survive the Razorpay/browser boundary is stored only as KMS ciphertext bound to the payment
attempt, and is erased from the active settlement state after successful redemption.

Refund/rollback uses Wix's transaction/order-billing APIs, never a local balance mutation. A
redeem that must be reversed is reversed against Wix using the provider transaction returned by
Wix; no WECARE table pretends to be the gift-card balance authority.

The older `wecare-wix-giftcard-spi` / custom GiftCardsTable design is superseded for website
checkout by this Wix-native decision. It must not be provisioned merely to make this flow work.

## Money invariants

1. Integer paise only. No float arithmetic.
2. `amountPaise` on the payment attempt is the **full authoritative order total**.
3. `razorpayChargedPaise` is the amount sent to Razorpay after the Wix-native gift-card leg.
4. `verifiedCapturedPaise` is written only from Razorpay's authoritative captured-payment
   readback.
5. Wix Add Payments receives `verifiedCapturedPaise`, never the full order total when a gift
   card funded part of the purchase.
6. The Wix order total must equal
   `verifiedCapturedPaise + wixGiftCardRedeemedPaise`.
7. A callback signature by itself is never paid evidence.
8. A pending/ambiguous external mutation is never blindly repeated.

## Customer identity

Checkout requires the existing authenticated WhatsApp customer session. That session supplies the
verified phone. Checkout then requires first name, last name, and an email verification proof.
The narrow customer-profile backend merges the verified identity into the existing Workspace
Contacts CRM. The staff `/contacts` endpoint remains private.

## Loyalty and referrals

Out of scope. No points, balance, tier, or referral-credit behavior is implied by checkout.

## Activation order

1. Finish code + tests on the feature branch.
2. Provision email verification and customer-profile routes.
3. Provision prepare/verify/redemption routes on the existing checkout Lambda.
4. Deploy branch code with all money/write gates OFF.
5. Verify Wix Cart V2 reads/writes, Razorpay credential readback, IAM, and route auth.
6. Run a controlled no-charge preparation smoke test.
7. Enable Wix writeback only after Create Order / Add Payments / Mark Cart As Completed readbacks
   are attested.
8. Enable `CHECKOUT_INITIATION_ENABLED` only after the full capture-to-Wix-order path is green.
