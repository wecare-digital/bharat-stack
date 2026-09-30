# Headless checkout implementation audit — 2026-10-01

Owner selected the attached headless WhatsApp/Razorpay flow. The Velo and external PSP prototypes are inactive and are not deployment dependencies.

Live read-only AWS audit: account 775261844268, us-east-1; 66 Lambda functions; 359 API routes, all gateway AuthorizationType NONE (handler auth must still be evaluated); customer pool admin-only, deletion protection ACTIVE, three CUSTOM_AUTH triggers point at customer-whatsapp-auth:live; SES domain verified with DKIM SUCCESS. PaymentsTable, InvoicesTable, OrderTable and WixOrderIds scans each count zero. Wix store live version 31 targets fcd82f0c-9572-49c7-acfb-88fb05042ece; write-back flags unset. CommerceKeys is absent; the code correctly defaults to existing WixOrderIds, so no new table is needed for identity claims. Audit collected 2026-09-30 21:41 UTC / 2026-10-01 03:11 IST.

No current Meta, Razorpay or template readiness read was performed. Historical attachment values are not activation evidence. The AWS connector needs reauthentication; the authorized local wecare-prod CLI profile succeeded.

Initial checkout gaps: registration was in progress in another session and has since been committed. This change implements the customer cart route described below. Paid-order code still needs the complete commerce-order materialization and Wix/receipt/confirmation pipeline. Concurrent checkout/UI scaffolding is preserved and excluded from this change; its V1 integration must be migrated before activation.

Defects found before wiring: provider lookup ignores reference binding; reconciliation accepts float truncation on provider amounts, rejects DynamoDB Decimal integers, checks customer ownership after its duplicate shortcut, allows not-captured to imply retry, and may adopt another attempt's funded order. Order numbering can be overwritten concurrently. Wix writeback may repeat a pending create call and marks incomplete responses successful. Add Payments payload uses fields absent from the current API schema.

Work for this change: repair these integrity defects and verify with offline fault/race tests. Keep all live payment/send flags disabled. No claim of full checkout completion, production deployment or current payment readiness. Rollback is revert this source change; no external mutation required.


## Cart V2 implementation and evidence

Source: `amplify/functions/shared/lambda_utils/ecommerce/cart_v2.py`, `customer_cart.py`,
`money.py`, with customer-only routing in `ecommerce/wix-store/handler.py`.

- GET/POST `/wix-store/cart` verifies the Cognito customer session before accessing Wix.
  Caller-supplied phone, customer ID, Wix cart ID and prices are rejected. Commands are
  create, get, add, quantity, remove, calculate. Mutations require UUID `requestId`.
- Existing WixOrderIds is reused with `CUSTOMERCART#<phone>` and durable command records.
  Conditional locks serialize each cart. Ambiguous remote writes are not repeated; they
  require readback. Expiry is logical (30 days cart, 5 minutes quote), never table TTL.
- Catalog V3 references always include its app ID and variant ID. Calculate Cart refreshes
  the cart and checks currencies, full quantity availability, violations, catalog-only
  items, full immediate payment, line totals, components and final integer-paise total.
  Demo carts, split/deferred/subscription payments and price overrides cannot be paid.
- The private snapshot stores wixCartId, cartRevision, purchaseFlowId, calculationId and
  the opaque priceVerificationToken. No new wixCheckoutId is introduced. The token is
  not a Create Order price lock; later paid-order mapping must explicitly verify the snapshot.
- Deployment keeps WIX_CART_V2_ENABLED absent/false. Cart and order flags were not changed.
  Order writes also require the exact owner-confirmed site ID and release contract
  WIX_CART_V2_WRITE_CONTRACT=cart-v2-external-v1, in addition to existing write flags.

Live Wix evidence: 2026-10-01 03:24–03:26 IST, site
fcd82f0c-9572-49c7-acfb-88fb05042ece. The current-cart read returned `{}`. A single
isolated demo cart de4d6a89-e575-4c51-b930-aec2adbd8b80 was then created, populated with
one existing Kiosk variant, read and calculated. It remains a nonpayable demo fixture.
Returned total: INR 24999.00 / 2499900 paise. Returned blocking errors:
MISSING_DELIVERY_ADDRESS and MISSING_DELIVERY_METHOD. No customer information was added,
no order was created, no payment was collected, and no WhatsApp message was sent.
`tests/fixtures/wix_cart_v2_live_demo.json` retains the response shape with the price token
and creator identity redacted. This validates populated Cart V2 shapes, not a payable order.

Validation command: Python 3.12 pytest on test_cart_v2, test_wix_origin_leak, test_wix_domain,
test_order_creation, test_order_keys, test_wix_writeback, test_razorpay_webhook_order_creation,
test_razorpay_binding, test_payment_attempt, test_customer_auth_and_throttle and
test_side_effect_guard. Fault tests cover old-request replay, concurrent writers, uncertain
remote success, ownership, Decimal minor units, missing capture bindings and wrong-site gates.

Remaining activation work: wire verified customer shipping/billing and delivery selection;
wire WhatsApp initiation to a fresh server-owned V2 calculation; populate provider payment/order
bindings from a trusted initiation response or authenticated Meta lookup; prove the full
Create Order payload, payment readback, cart completion and exactly-once inventory behavior.
Do not use Place Order. No payment/send flags, AWS code, IAM, or aliases were deployed here.

Rollback: revert this source commit while leaving all feature flags off. The isolated
nonpayable demo fixture carries no financial state and is not a customer cart.

Sources: [Cart V2](https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/introduction),
[Calculate Cart](https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/purchase-flow/cart-v2/calculate-cart),
[Catalog V3 references](https://dev.wix.com/docs/api-reference/business-solutions/stores/catalog-v3/e-commerce-integration),
[Add Payments](https://dev.wix.com/docs/api-reference/business-solutions/e-commerce/orders/order-transactions/add-payments).

Focused regression result: **382 passed** on Python 3.12. `git diff --check` passed.
