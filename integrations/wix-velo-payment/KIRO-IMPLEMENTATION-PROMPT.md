# WECARE.DIGITAL — KIRO IMPLEMENTATION PROMPT: WIX VELO PAYMENT PROVIDER

Work inside:

`wecare-digital/wecare-digital`

branch:

`stack`

This is an existing production architecture.

Deliver a WECARE.DIGITAL payment option inside native Wix checkout using a Velo Payment Provider service plugin. Reuse Razorpay as the underlying processor and the existing Meta/WhatsApp payment flow. “Own gateway” means the branded WECARE orchestration layer; it does not replace the processor or authorize a new payment processor.

This document supersedes the earlier pasted prompt. The new checkout path is WIX_NATIVE_PROVIDER. Do not build a replacement checkout page or a parallel AWS application. A minimal hosted payment handoff/status screen is necessary because the Velo plugin supports hostedPage; reuse the existing public frontend for it.

Evidence status: infrastructure values below were supplied by the owner in a document dated 2026-09-30. They were NOT independently reverified while preparing this handoff. Re-read live state before changing infrastructure. Treat “verified/current/live” in inherited baseline sections as owner-supplied dated claims, not a fresh audit. Do not overwrite a newer live result with this document.

Implementation handoff: use the accompanying wecare-wix-payment source bundle. Its local adapter tests pass; Wix runtime, AWS bridge, site installation, Meta readiness and end-to-end payment tests remain to be completed in the real project. Bridge operations in this document are a NEW INTERNAL CONTRACT, not existing or Wix REST endpoints.

Do NOT create a parallel application or duplicate implementation.

Reuse and repair the existing:

- AWS infrastructure
- Cognito
- WhatsApp/Meta integration
- Razorpay integration
- Wix commerce adapter
- webhook idempotency
- invoice engine
- SES
- DynamoDB tables
- customer auth
- public-page design system.

---

# 1. FIRST PRINCIPLE

Do not trust comments, constants, old steering files or historical compatibility documents when they conflict with current live infrastructure.

Evidence precedence:

1. current live provider/API read
2. current AWS live state
3. current production Lambda environment
4. current source code
5. dated documentation
6. comments/historical notes.

Historical evidence must never be represented as current live state.

---

# 2. READ THESE FILES FIRST

Before changing source, inspect:

1. `.kiro/steering/`
2. `.kiro/steering/aws-agent-rules.md`
3. `.kiro/steering/whatsapp-payments-india-reference.md`
4. `.kiro/steering/PAYMENT-AUDIT-REPORT.md`
5. `.kiro/specs/whatsapp-wix-commerce/requirements.md`
6. `.kiro/specs/whatsapp-wix-commerce/design.md`
7. `.kiro/specs/whatsapp-wix-commerce/tasks.md`
8. `docs/spec.md`
9. `docs/design.md`
10. `docs/tasks.md`
11. `docs/current-environment.md`
12. `docs/current-environment-addendum.md`
13. `docs/compatibility.md`
14. `docs/operations.md`
15. `docs/wix-headless.md`
16. `docs/execution/aws-inventory.md`
17. `docs/execution/phase-04d-payment-audit.md`
18. `config/lambda-env-manifest.json`
19. `src/pages/index.tsx`
20. `.kiro/skills/new-public-page/SKILL.md`
21. customer WhatsApp auth Lambda
22. outbound WhatsApp Lambda
23. inbound WhatsApp Lambda
24. WhatsApp business API Lambda
25. Razorpay webhook
26. invoice engine
27. Wix Store Lambda
28. `lambda_utils/ecommerce/order_keys.py`
29. `payment_status.py`
30. existing webhook/idempotency utilities
31. tests created by commit `dc7d409a`.

---

# 3. VERIFIED LIVE AWS BASELINE — 2026-09-30

Treat the following as the owner-supplied 2026-09-30 baseline; reverify before implementation.

AWS account:

`775261844268`

Primary region:

`us-east-1`

Current Lambda inventory:

approximately 66 functions at the time of verification.

HTTP API:

`zllr9lrg7j`

Name:

`wecare-digital-api`

Current route count:

`359`

Current API Gateway authorization:

`359 / 359 AuthorizationType=NONE`

Therefore every customer-sensitive endpoint must enforce authentication and authorization in the application/Lambda layer unless a separate authorizer is deliberately introduced.

Do not hardcode either 359 or 361 as a fresh live route count; re-read it.

---

# 4. VERIFIED CUSTOMER COGNITO STATE

Customer pool:

`us-east-1_46ULYuukt`

Name:

`WECARE.DIGITAL-CUSTOMERS`

Verified current state:

`AllowAdminCreateUserOnly = true`

Deletion protection:

`ACTIVE`

MFA:

`OFF`

Estimated current users:

`1`

All three CUSTOM_AUTH triggers currently point to:

`wecare-customer-whatsapp-auth:live`

for:

- DefineAuthChallenge
- CreateAuthChallenge
- VerifyAuthChallengeResponse.

This is deliberate architecture.

## DO NOT ENABLE PUBLIC COGNITO SELF-SIGNUP.

Public walk-up checkout must not call Cognito `SignUp` directly.

---

# 5. WALK-UP CUSTOMER REGISTRATION ARCHITECTURE

Because Cognito remains admin-only, build a trusted registration front door.

Correct flow:

website
→ registration API
→ source-IP available
→ phone normalization
→ rate limiting
→ WhatsApp OTP
→ verify OTP
→ create/resolve immutable WECARE customer
→ backend/admin-provision Cognito user when required
→ establish CUSTOM_AUTH/customer session.

The browser must never be allowed to directly provision arbitrary Cognito users.

---

# 6. IP RATE LIMITING

The Cognito custom-auth trigger does not receive a trustworthy source IP.

Therefore per-IP OTP limiting cannot live solely inside:

`wecare-customer-whatsapp-auth`

Implement IP throttling at the HTTP registration/OTP front door.

Use both:

- per-IP rate limits
- per-phone rate limits.

Cognito trigger remains responsible for challenge logic, not edge/IP enforcement.

WAF is currently not part of the required architecture.

---

# 7. VERIFIED EMPTY COMMERCE/PAYMENT TABLES

Live DynamoDB scans currently return:

`stack-wecare-digital-PaymentsTable = 0`

`stack-wecare-digital-InvoicesTable = 0`

`stack-wecare-digital-OrderTable = 0`

`stack-wecare-digital-WixOrderIds = 0`

This is important.

The supplied dated snapshot suggests no migration then. Recheck live records and existing writers before concluding that no migration is needed now.

---

# 8. EXISTING ORDER WRITERS

Do not incorrectly conclude that OrderTable has no writers anywhere.

Existing code contains:

- manual-order creation
- service API order writes
- Wix synchronization/order mirroring.

However:

## THE CURRENT WHATSAPP/RAZORPAY PAYMENT PATH DOES NOT CREATE THE NEW CHECKOUT ORDER WE REQUIRE.

It currently focuses on:

- payment records
- invoice state
- GST invoice generation
- payment notifications.

Therefore:

`paid transaction → commerce order`

is a new payment-path capability, not a migration/refactor of existing live payment orders.

---

# 9. VERIFIED SES STATE

Email sender:

`one@wecare.digital`

is currently verified for sending.

DKIM:

`SUCCESS`

Signing:

enabled.

Use SESv2.

Configuration set:

`wecare-digital`

Verified configuration includes:

- TLS required
- reputation metrics enabled
- shared sending pool
- suppression on bounce
- suppression on complaint.

Email verification work is NOT blocked by Meta Payments.

---

# 10. PRIMARY WHATSAPP IDENTITY

Primary customer sender:

`+919330994400`

Phone Number ID:

`1016149501586345`

WABA:

`2094615664435155`

Use the existing sender.

Do not mutate, deregister or migrate it.

Stale comments claiming Phone 1 is disconnected must be removed/corrected.

---

# 11. VERIFIED OTP TEMPLATE

Current live template read for WABA:

`2094615664435155`

returned:

`wecare_otp`

Status:

`APPROVED`

Category:

`AUTHENTICATION`

Language:

`en`

Continue using this template for phone verification.

---

# 12. PAYMENT TEMPLATE LIVE REALITY

A current live template read returned only:

`wecare_otp`

It did NOT return:

`wecare_pay`

Therefore existing repository statements claiming:

`wecare_pay = APPROVED/live`

must be treated as stale until a current Meta read proves otherwise.

Do not attempt to send an absent template.

---

# 13. WHATSAPP CUSTOMER-SERVICE WINDOW

Never infer an open 24-hour customer-service window from sending an authentication template, delivering an OTP, or the customer entering the OTP on the website. Use the latest qualifying inbound customer WhatsApp message and current Meta policy as evidence.

Within an independently verified open window, use the current supported interactive payment/order_details mechanism if permitted. Outside it, require an approved payment template containing the supported ORDER_DETAILS button. Read current Meta documentation; do not invent fields.

Apply the same window/template check to delayed receipts and confirmations. Missing messaging readiness must queue the confirmation, never undo a captured payment or offer Pay Again.

Creating/submitting Meta templates remains an owner-authorized external action.

---

# 14. META PAYMENT DOCUMENTATION

Use the current official Meta WhatsApp Payments India documentation:

`https://developers.facebook.com/documentation/business-messaging/whatsapp/payments/payments-in/overview`

Follow its current linked documentation for:

- gateways
- Razorpay
- `order_details`
- payment configurations
- configuration_name
- `reference_id`
- status
- payment lookup
- webhook events
- errors
- templates
- customer-service-window behavior
- reconciliation.

Do not implement request fields from memory.

---

# 15. VERIFIED PAYMENT-CONFIG BLOCKER

A live invocation of:

`/wa-business/payment-config/check`

for:

`2094615664435155`

currently returns:

`WECAREDIGITAL`

status:

`local_only`

`canReceivePayments = false`

and:

`WECAREUPI`

status:

`local_only`

`canReceivePayments = false`

Total local configs:

`2`

Active configs:

`0`

The current application therefore CANNOT initiate a reliable Meta gateway payment.

---

# 16. LOCAL CONSTANT != META CONFIGURATION

The following names exist locally:

`WECAREDIGITAL`

`WECAREUPI`

That does NOT mean Meta currently has those configurations.

Runtime code must never infer payment readiness from local constants.

Payment readiness requires a current Meta provider read.

---

# 17. LEGACY PAYMENT CONFIG NAMES

Repository history also contains:

`WECARE-RAZOR-PAY`

`Razorpay_ManishAgarwal`

and older PayU configuration names.

These are historical.

Do not fall back to them.

Do not automatically restore them.

---

# 18. OWNER MUST CHOOSE CANONICAL META PAYMENT CONFIG

Before Meta configuration is recreated, produce a concise owner decision sheet.

Required decision:

Canonical Razorpay gateway configuration name.

Do not guess it.

Example candidates may include:

`WECAREDIGITAL`

or a newly approved canonical name.

But no configuration mutation is allowed until the owner selects the exact name.

Once selected:

the same exact name must be reflected in:

- Meta
- production configuration
- readiness checker
- tests
- documentation.

---

# 19. DO NOT AUTOMATICALLY CREATE META PAYMENT CONFIG

Creating/restoring a WhatsApp payment configuration is a Meta administrative mutation.

Owner performs it through:

WhatsApp Manager
→ Payments.

Kiro may:

- inspect
- validate
- report
- disable payment
- provide exact setup requirements.

Kiro must not silently create/change the payment configuration.

---

# 20. RAZORPAY CURRENT RUNTIME IDENTITY

Current production Lambda environment reports:

`RAZORPAY_MID = acc_HDfub6wOfQybuH`

Current real Razorpay webhook examples also carry:

`account_id = acc_HDfub6wOfQybuH`

This is stronger evidence than historical prose.

However do not simply assume Meta `provider_mid` is identical without verifying the restored Meta configuration.

---

# 21. STALE MID

Repository prose/comments still claim:

`acc_TTFSyolquKEZEy`

as the Razorpay MID/provider_mid.

Do not treat this as current truth.

Classify it as:

`HISTORICAL / UNVERIFIED`

until provider readback proves its meaning.

Remove or annotate misleading comments.

---

# 22. UPI VPA CONFLICT

Current production Lambda environment reports:

`wecaredigital83.rzp@icici`

Historical code/comments report:

`wecaredigitalbh511413.rzp@rxairtel`

Do not choose either blindly.

Determine first whether the final architecture even requires a separate UPI VPA configuration in addition to Razorpay gateway integration.

If not required:

remove the unnecessary parallel UPI-config assumption.

If required:

owner/provider live evidence must determine the current VPA.

---

# 23. RAZORPAY ONLY

The intended gateway is:

RAZORPAY.

Do not restore PayU.

Do not add another gateway abstraction solely for theoretical flexibility.

---

# 24. PAYMENT READINESS SERVICE

Implement one authoritative payment-readiness gate.

Example states:

`PAYMENT_READY`

`META_PAYMENT_CONFIG_MISSING`

`META_PAYMENT_CONFIG_INACTIVE`

`META_PAYMENT_CONFIG_WABA_MISMATCH`

`META_PAYMENT_TEMPLATE_REQUIRED`

`META_PAYMENT_TEMPLATE_MISSING`

`RAZORPAY_ACCOUNT_UNVERIFIED`

`RAZORPAY_MID_MISMATCH`

`META_UNAVAILABLE`

`RAZORPAY_UNAVAILABLE`

`PAYMENT_CONFIGURATION_UNVERIFIED`

Payment CTA is enabled only when the applicable requirements are satisfied.

---

# 25. NO DEFAULT CONFIG FALLBACK

Existing code currently has behavior equivalent to:

unknown config
→ warning
→ fallback to `WECAREDIGITAL`.

REMOVE THIS PAYMENT BEHAVIOR.

For payments:

unknown configuration
→ FAIL CLOSED.

No silent fallback.

No guessed configuration_name.

---

# 26. CUSTOMER JOURNEY WITH NATIVE WIX CHECKOUT

homepage → trusted registration → WhatsApp OTP → verified phone → immutable customer/session → name → SES email OTP → verified email → addresses → cart → native Wix checkout → WECARE.DIGITAL payment option → Velo createTransaction → AWS readiness and customer binding → durable PaymentAttempt → hosted handoff/status screen → WhatsApp/Meta/Razorpay payment → authoritative verification → submitEvent to Wix → bind native Wix commerce order → create internal paid WECARE order → receipt → WhatsApp confirmation → Wix return URL / status.

Native checkout must not bypass WECARE customer verification. Bind checkout/transaction to an authenticated immutable customer server-side, and enforce this in the bridge before creating the attempt. Never treat billing phone/email or Wix buyerId alone as proof of WECARE ownership. The Velo adapter deliberately does not send browser identity claims or copy PII into bridge payloads; the bridge resolves it from trusted associations.

The hosted screen is a payment handoff, not a second cart/checkout. It cannot choose amount, account, return URLs or payment status.

---

# 27. CUSTOMER IDENTITY

Permanent identity:

`CUS_<ULID>`

or the already-approved equivalent.

Customer identity is immutable.

Phone and email are mutable verified attributes.

Fields include:

- customerId
- firstName
- lastName
- fullName
- normalizedPhone
- phoneVerifiedAt
- normalizedEmail
- emailVerifiedAt
- billing address
- shipping address
- createdAt
- updatedAt.

---

# 28. EMAIL OTP

Use:

`one@wecare.digital`

through SESv2.

Use configuration set:

`wecare-digital`.

Implement branded email OTP.

Do not send purchase confirmation email.

Email is for verification/security/account flows.

---

# 29. FINAL PURCHASE CONFIRMATION CHANNEL

Final order/payment confirmation:

WHATSAPP ONLY.

Receipt delivery:

WHATSAPP.

Website only reflects status and essential order information.

---

# 30. CORE INTERNAL ORDER RULE

NO INTERNAL WECARE COMMERCE ORDER, public WECARE order number, receipt or fulfillment exists until payment is authoritatively verified PAID.

Native Wix checkout controls its own checkout/order/payment records. A Wix-supplied order reference may already exist when createTransaction is invoked. It is not the internal paid WECARE order. Do not promise “zero Wix orders before payment” for this integration.

Audit the actual Wix business-solution order lifecycle and distinguish payment-provider order reference from the eCommerce order ID. Do not assume they are interchangeable or use undocumented lookup fields. Persist the verified mapping separately.

If absolutely zero unpaid Wix records is a business requirement, report the incompatibility and keep native integration disabled; do not silently reintroduce a custom checkout.

---

# 31. PAYMENT ATTEMPT ENTITY

Before payment, create a:

`PaymentAttempt`

not an order.

Suggested fields:

- paymentAttemptId
- customerId
- cartId
- checkoutMode = WIX_NATIVE_PROVIDER
- wixCheckoutId (when available)
- wixMerchantId
- wixTransactionId
- wixPaymentOrderId (options.order._id; not assumed to be eCommerce ID)
- wixCommerceOrderId (resolved by documented API/event)
- referenceId
- amountPaise
- currency
- configurationName
- provider
- attemptNumber
- retryOf
- status
- providerPaymentId
- providerOrderId
- createdAt
- updatedAt
- paidAt
- failedAt
- failureCode
- failureReason.

Use UUIDv7 or approved equivalent for:

`paymentAttemptId`.

---

# 32. META REFERENCE_ID

`reference_id`

is the payment join key.

It is NOT:

- order number
- customer ID
- email
- phone
- invoice number.

Generate it server-side using `secrets`.

Use current Meta constraints.

Currently documented:

maximum 35 characters.

Allowed charset:

`A-Z a-z 0-9 _ - .`

---

# 33. KEEP dc7d409a

Preserve the security work from:

`dc7d409a`

including:

- conditional order-number reservation
- fail-closed DynamoDB behavior
- uniqueness
- use of `secrets`
- Meta-compatible reference validation
- collision handling
- no unstored number escape.

Do not revert those protections.

---

# 34. SPLIT allocate_order_identity()

Current:

`allocate_order_identity()`

binds a Meta reference to an order number before payment.

That violates the new business model.

Refactor into separate responsibilities.

Before payment:

`mint_payment_reference()`

`reserve_payment_reference()`

`resolve_payment_reference()`

After authoritative PAID:

`create_order_uuid()`

`reserve_public_order_number()`

`bind_paid_attempt_to_order()`

Reuse the safe reservation primitives.

---

# 35. REMOVE REFERENCE MUTATION

Existing payment send paths still use:

`_sanitize_reference_id()`

Do not mutate a join key immediately before sending.

New rule:

mint valid reference once
→ store it
→ validate it
→ send it byte-for-byte.

If invalid:

FAIL CLOSED.

Do not:

- truncate
- strip
- prefix-rewrite
- transform
- "repair"

the canonical reference after reservation.

---

# 36. LEGACY SANITIZER

Legacy sanitization may remain only where required for reading/displaying historical records.

It must not operate on new canonical payment-attempt reference IDs.

Add regression tests ensuring payment-send functions receive the exact reference stored on PaymentAttempt.

---

# 37. AUTHORITATIVE PAYMENT STATE

Webhook success alone is not proof.

A payment-success event is a trigger for verification.

Verify with authoritative provider lookup.

Before creating order confirm:

- payment exists
- status paid/captured
- merchant/account correct
- reference matches
- customer/payment attempt matches
- INR
- exact paise amount
- no conflicting internal paid-order mapping; preserve the supplied native Wix order association.

---

# 38. PAYMENT STATE MACHINE

Example:

`CREATED`

→ `PAYMENT_READINESS_CHECKED`

→ `PAYMENT_REQUEST_SENT`

→ `PAYMENT_PENDING`

then:

`PAYMENT_PAID`

or:

`PAYMENT_FAILED`

or:

`PAYMENT_CANCELLED`

or:

`PAYMENT_EXPIRED`.

Only:

`PAYMENT_PAID`

can create an order.

---

# 39. PAID ORDER FINALIZATION

After authoritative PAID:

1. Atomically claim provider payment ID and paymentAttemptId using existing DynamoDB conditional/transactional primitives.
2. Persist paid status and a durable outbox entry for Wix transaction approval.
3. Notify Velo; Velo obtains a leased, verified event from AWS and calls submitEvent.
4. Resolve and bind the native Wix eCommerce order through documented IDs/events. Never call create-order for WIX_NATIVE_PROVIDER.
5. Create exactly one internal WECARE order and unique 12-character public number after PAID, with a durable retryable association to the native Wix order.
6. Reuse invoice engine for one receipt, then send one logical WhatsApp confirmation after association/receipt readiness.

DynamoDB, Wix and WhatsApp cannot be one distributed transaction. Use an outbox/saga with explicit stage checkpoints and reconciliation. “Exactly one” describes durable business artifacts; callback delivery is at least once. Ambiguous remote timeouts must be reconciled before retries that could duplicate side effects.

---

# 40. INTERNAL ORDER ID

Use:

UUIDv7

or existing approved UUID equivalent.

Field:

`orderId`

Never expose it as primary customer-facing number.

---

# 41. PUBLIC ORDER NUMBER

Generate only after PAID.

Exactly:

12 characters.

Requirements:

- uppercase
- URL-safe
- high entropy
- non-sequential
- no PII
- not a timestamp
- conditional uniqueness
- immutable.

Recommended alphabet excludes:

`0 O 1 I L`.

Example:

`7KMP4X9Q2DTR`

---

# 42. FAILED PAYMENT

Failed/cancelled/expired attempts remain in payment history with their attempt ID and immutable reference. They have no internal WECARE orderId, WECARE orderNumber, receipt, fulfillment or final purchase confirmation.

Wix may retain an unpaid order/payment artifact. Preserve and reconcile it; do not delete it to pretend the earlier zero-Wix-order invariant still holds. Never mirror an unpaid native Wix record as a paid internal order.

---

# 43. RETRY

For definitively failed/cancelled/expired payment:

create NEW PaymentAttempt.

Set:

`retryOf = previousPaymentAttemptId`.

Generate NEW reference_id.

Recalculate Wix checkout.

Do not reuse stale totals.

Pending payment must NOT create another attempt automatically.

Paid payment must NEVER show a Pay Again action.

---

# 44. AUTHORITATIVE WIX CHECKOUT

Wix/backend is authoritative for:

- items
- variant
- quantity
- price
- discount
- shipping
- tax
- fees
- total
- inventory.

Never trust browser financial data.

Use integer paise.

₹0.01 mismatch:

FAIL CLOSED.

---

# 45. WIX ORDER OWNERSHIP

WIX_NATIVE_PROVIDER is the new path. Wix owns creation/lifecycle of its native commerce order. The bridge associates the paid attempt with that existing order; it never creates a second Wix order.

Keep legacy headless/external payment code isolated by an explicit checkoutMode if it must remain for existing callers. Only that independently supported legacy mode may retain after-payment Wix order creation. It is not a fallback when native checkout fails.

A paid attempt maps to one internal paid order and one resolved native Wix commerce order. Retry attempts for the same Wix order require an order-level active-payment lock and duplicate-capture reconciliation.

---

# 46. REPORT PAYMENT THROUGH THE PROVIDER PLUGIN

For WIX_NATIVE_PROVIDER, use wix-payment-provider-backend.submitEvent to update the existing Wix transaction after authoritative provider verification. Do not also record the same capture via the external Order Transactions recording path. Do not charge through Wix Pay APIs during reconciliation.

Payment browser redirects, hosted-screen success callbacks and unsigned webhook bodies are never proof. Report success only from a provider-verified durable AWS event. Verify merchant, amount, INR, canonical reference and transaction/attempt mapping.

Refunds use refundTransaction, durable wixRefundId deduplication, provider lookup, and submitEvent for final verified completion. A pending refund is not a successful refund. Test async refund behavior in Wix before activation; the supplied adapter fails closed for non-final refund responses.

---

# 47. WEBSITE STATES

Processing:

`Confirming your payment`

`We're securely checking your payment status. This page will update automatically.`

Paid but order still finalizing:

`Payment received`

`We're creating your order now. Do not pay again.`

Success:

`Payment successful`

`Your order has been created. We've sent your confirmation and receipt to WhatsApp.`

Failure:

`Payment wasn't completed`

`No order was created.`

Retry:

only after authoritative failed/cancelled/expired status.

---

# 48. WEBSITE SUCCESS PAGE

Route:

`/checkout/success`

or repository-approved equivalent.

May display:

- success indicator
- 12-character order number
- amount
- Track Order
- Continue Shopping.

Full final confirmation/receipt remains WhatsApp-oriented.

---

# 49. RECEIPT

Generate exactly one receipt for exactly one successfully paid order.

Include where applicable:

- WECARE.DIGITAL
- order number
- receipt number
- dates
- customer
- billing address
- shipping address
- products
- quantity
- prices
- subtotal
- discounts
- shipping
- GST/tax
- total INR
- payment method
- safe transaction reference
- support email
- support WhatsApp.

Use existing billing/invoice engine where appropriate.

Do not create a second payable invoice.

---

# 50. WHATSAPP CONFIRMATION

Send from:

`+919330994400`

after:

- PAID verification
- order creation
- Wix association
- receipt generation.

Suggested heading:

`Payment confirmed`

Include:

- first name
- 12-character order number
- amount
- item summary
- status
- receipt
- tracking.

Send exactly once.

---

# 51. PAYMENT HISTORY VS ORDER HISTORY

Payment history contains:

- successful attempts
- failed attempts
- cancelled attempts
- expired attempts.

Order history contains:

ONLY actual paid orders.

A failed payment entry must explicitly say:

`Payment failed — no order created`

and must not show an order number.

---

# 52. API AUTHORIZATION

Because API Gateway currently has 359 routes and no gateway authorizers, every sensitive customer endpoint must authorize at handler/service level.

Never authorize using only:

orderNumber

paymentAttemptId

customerId supplied in request

receipt ID.

Authority comes from authenticated customer session.

Prevent IDOR.

---

# 53. SECURITY

Threat-model and test:

- forged Meta webhook
- forged Razorpay webhook
- replay
- duplicate webhook
- provider mismatch
- MID mismatch
- missing Meta config
- wrong configuration_name
- wrong WABA
- stale config fallback
- amount tampering
- currency mismatch
- one-paise mismatch
- cart tampering
- duplicate payment
- duplicate order
- duplicate Wix order
- duplicate receipt
- duplicate confirmation
- order number collision
- OTP brute force
- IP abuse
- phone enumeration
- email enumeration
- session theft
- IDOR
- receipt enumeration
- secret leakage
- PII logging.

---

# 54. NEVER LOG

Never log:

- OTP
- OTP hash/pepper
- Meta token
- Razorpay key secret
- Wix credential
- AWS credentials
- bearer tokens
- full customer phone
- full customer email
- sensitive payment data.

---

# 55. LIVE PAYMENT READINESS REQUIREMENTS

Before enabling live payment, all must be true:

1. primary WABA verified
2. primary phone verified
3. sender GREEN/healthy
4. correct service-window logic
5. approved payment template exists if needed outside 24h
6. Meta payment configuration exists
7. exact configuration_name known
8. configuration belongs to WABA `2094615664435155`
9. Razorpay is provider
10. Meta provider identity reconciles to actual Razorpay account
11. current Razorpay credentials verified
12. checkout total authoritative
13. payment-reference contract tests pass.

Until a new provider read proves readiness, this gate must return NOT READY.

---

# 56. EXTERNAL OWNER ACTIONS

Current owner-side blockers are:

## A. Choose canonical payment configuration

Decide exact Meta configuration name and Razorpay mapping.

Then create/restore it in WhatsApp Manager → Payments.

## B. Approve payment template if required outside 24h

Current live template inventory only proves:

`wecare_otp`.

Create/approve the chosen order_details payment template if outside-window payment is a supported requirement.

Do not block unrelated engineering work while waiting for these.

---

# 57. UNBLOCKED WORK TO START NOW

Proceed immediately with:

1. spec corrections
2. customer identity model
3. public registration front door
4. per-IP/per-phone rate limiting
5. WhatsApp OTP
6. admin-side Cognito provisioning
7. customer session flow
8. SESv2 email OTP
9. billing address
10. shipping address
11. native checkout integration and hosted payment handoff
12. Wix authoritative checkout
13. PaymentAttempt model
14. canonical payment reference implementation
15. payment readiness gate
16. payment history
17. split `order_keys`
18. paid-only internal order creation and native Wix order association
19. 12-char public order number
20. success/failure/finalizing UI
21. receipt
22. WhatsApp confirmation
23. tests.

---

# 58. TEST — LIVE CONFIG ABSENT

native Wix checkout → WECARE option → bridge readiness → no verified active Meta configuration → error/unavailable response → no PaymentAttempt and no Meta order_details → no internal order/receipt/confirmation.

A Wix technical transaction/order record may already exist; never claim zero Wix records. Native Wix controls visibility of connected payment methods. Server-side refusal must work even if Wix still displays the option. Verify available supported controls for hiding/disabling the provider; do not promise an unsupported per-customer disabled CTA.

---

# 59. TEST — CUSTOMER REGISTRATION

Test:

- new number
- existing number
- normalized E.164
- per-phone limit
- per-IP limit
- wrong OTP
- expired OTP
- used OTP
- concurrent OTP
- resend
- enumeration resistance
- backend Cognito provisioning
- no direct browser Cognito signup required.

---

# 60. TEST — REFERENCE ID

Test:

- <= current Meta maximum
- allowed charset
- cryptographically minted
- reserved before use
- exact stored value sent
- never truncated
- never altered
- delivery retry uses same reference
- genuine payment retry uses new reference
- duplicate reference rejected.

---

# 61. TEST — ORDER INVARIANTS

PENDING / FAILED / CANCELLED / EXPIRED → zero internal paid WECARE orders and zero WECARE public order numbers.
PAID verified → one internal paid order associated with the native Wix commerce order.
Duplicate paid event and concurrent reconciliation → still one internal order, one mapping and one logical receipt/confirmation.

Assert no create-Wix-order and no external-record-payment call occurs for WIX_NATIVE_PROVIDER. Assert native unpaid Wix records are never imported as internal paid orders. Test two Wix transaction IDs against the same commerce order and recovery after a late capture.

---

# 62. TEST — DATA IDENTIFIERS

Successful paid order:

one internal UUID

one unique 12-char public number.

Failed payment:

no order UUID

no public order number.

DynamoDB outage:

no identifier may escape without durable reservation.

---

# 63. TEST — POST-PAYMENT

Successful native-provider path: verified capture → Wix submitEvent → native Wix order association → internal WECARE order → receipt → WhatsApp confirmation → success.

Failure: no internal order, receipt, fulfillment or final confirmation. Provider refund verification is separate from capture verification. Test partial/full refunds, duplicate Wix refunds, ambiguous timeout and cumulative over-refund prevention.

---

# 64. E2E SUCCESS

homepage → trusted registration → WhatsApp OTP → customer session → name/email → SES OTP → addresses/cart → native Wix checkout → WECARE.DIGITAL → Velo → bridge → readiness → PaymentAttempt → hosted handoff → WhatsApp payment → provider PAID lookup → outbox → Velo submitEvent → resolve native Wix order → internal UUID/public number → receipt → WhatsApp confirmation → Wix return URL → tracking.

Use a test/sandbox path supported by every participating provider. Never call mock tests proof of live payment readiness.

---

# 65. E2E FAILURE

native checkout → PaymentAttempt → hosted handoff → authoritative failed/cancelled/expired → report correct Wix terminal status → payment history → zero internal orders/receipts → safe retry with new attempt/reference.

Pending or unknown after timeout: preserve existing attempt and reconcile; do not create a replacement charge. Closing the browser does not prove provider cancellation. Late capture must be reconciled without prompting payment again.

---

# 66. CROSS-BROWSER / ACCESSIBILITY

Run:

- Chromium
- WebKit
- Firefox
- mobile widths
- tablet
- desktop
- keyboard navigation
- screen reader behavior
- OTP paste
- status announcements
- reduced motion
- contrast
- error focus.

---

# 67. UPDATE STALE DOCUMENTATION

Correct documentation that currently claims:

- 361 routes
- payment configs are active
- `WECAREDIGITAL` is current merely because constant exists
- `WECAREUPI` is current merely because constant exists
- `wecare_pay` is live/approved
- `acc_TTFSyolquKEZEy` is currently verified
- `wecaredigitalbh511413.rzp@rxairtel` is current
- Phone 1 is disconnected
- payment reference can be transformed/truncated
- order identity should exist before paid state.

Preserve historical dates instead of deleting evidence.

Use labels such as:

`HISTORICALLY VERIFIED 2026-08-23 — NOT CURRENT`

where useful.

---

# 68. FIRST KIRO OUTPUT

Before source edits, produce a current implementation audit containing:

1. Git HEAD
2. AWS account/region
3. live Lambda count
4. API route count
5. API auth posture
6. customer Cognito state
7. CUSTOM_AUTH trigger state
8. SES state
9. Dynamo table counts
10. WABA/sender state
11. live template inventory
12. live payment-config inventory
13. Razorpay runtime evidence
14. MID conflicts
15. VPA conflicts
16. payment-reference defects
17. existing order writers
18. current payment path
19. changes required
20. owner-only blockers
21. tests
22. rollback strategy.

---

# 69. SPEC UPDATE

Update requirements, design and tasks before repository implementation. State:

- Cognito public signup stays disabled; registration uses trusted front door.
- WECARE.DIGITAL is a Velo payment-provider option in native Wix checkout.
- Razorpay remains the underlying processor; Meta/WhatsApp payment requirements remain enforced.
- hostedPage requires a hosted payment handoff; no embedded custom card fields are promised.
- PaymentAttempt exists before payment; Meta reference belongs to it and is immutable.
- Internal WECARE order identity exists only after authoritative PAID.
- Wix owns native order lifecycle; unpaid Wix records may exist.
- Native provider uses submitEvent, never duplicate order creation/external payment recording.
- Readiness is based on live provider evidence, never constants.
- OTP delivery alone does not open a customer-service window.
- WhatsApp-only final receipts/confirmation must account for native Wix notification settings and messaging templates.
- Dated baseline claims must be reverified, not repeated as fresh live evidence.

---

# 70. FINAL ACCEPTANCE CRITERIA

1. Existing registration, Cognito admin provisioning, per-IP/per-phone throttling, WhatsApp OTP, SES email OTP and customer authorization work.
2. Native Wix checkout displays the WECARE provider on the actual target site and invokes the Velo handlers.
3. Velo is installed through a supported site workflow; editorless-site compatibility is proven.
4. Bridge authenticates every request and binds configured site, merchant, account, customer and transaction.
5. Payment readiness is live-driven; missing/unverified configuration refuses initiation without a new attempt.
6. Canonical reference is reserved, immutable, never truncated, and exact throughout Meta/provider lookups.
7. Pending/failed attempts create zero internal orders, numbers, receipts or fulfillment.
8. Verified paid attempt creates exactly one internal paid order and native Wix association.
9. Native path never creates a duplicate Wix order, records capture twice or charges again.
10. Duplicate/reordered callbacks, provider timeout, DynamoDB outage and recovery cannot double-charge or double-finalize.
11. Refunds are idempotent and cannot exceed verified captured balance; pending is never reported refunded.
12. Receipts and logical WhatsApp confirmations are deduplicated with durable outbox/reconciliation.
13. No purchase-confirmation email from either AWS or Wix; audit Wix built-in notifications/automations explicitly.
14. Customer API IDOR, signed callback, wrong merchant/amount/currency, one-paise and secret-leak tests pass.
15. Browser/mobile/accessibility testing covers registration, native-to-hosted handoff, status and return.
16. Paid-but-finalizing never offers Pay Again; unknown status never becomes retryable merely on timeout.
17. No credentials in source/frontend/logs. Secrets stay in Wix Secrets Manager/AWS secrets.
18. All live provider prerequisites, supported Wix install/runtime checks, callback delivery/replay behavior and end-to-end tests pass before activation.
19. Status report separates source complete, bridge deployed, Velo installed, provider connected, sandbox tested and live enabled.
20. Keep live initiation disabled while the supplied missing Meta configuration remains unverified/unresolved.

---

# 71. FINAL ARCHITECTURE

```text
CUSTOMER → VERIFIED WECARE SESSION → NATIVE WIX CHECKOUT
  → WECARE.DIGITAL (Velo hostedPage payment provider)
  → AUTHENTICATED AWS BRIDGE → LIVE READINESS
  → PAYMENT ATTEMPT + IMMUTABLE META REFERENCE
  → HOSTED HANDOFF → WHATSAPP / RAZORPAY
  → AUTHORITATIVE CAPTURE LOOKUP
  → DURABLE OUTBOX → SIGNED VELO NOTIFICATION
  → WIX submitEvent → NATIVE WIX ORDER ASSOCIATION
  → INTERNAL PAID WECARE ORDER + 12-CHAR NUMBER
  → RECEIPT → WHATSAPP CONFIRMATION → STATUS / TRACKING
```

Failed/unknown payments create no internal paid order. Native Wix records are handled according to Wix lifecycle. No duplicate Wix order or second payment recording is permitted.

---

# 72. VELO SOURCE AND INSTALLATION

Use accompanying files:

- `velo-service-plugin/wecare-config.js`: payment option and connection field.
- `velo-service-plugin/wecare.js`: the three Wix payment-provider handlers.
- `backend/wecare/core.js`: validation, response mapping and verified event mapping.
- `backend/wecare/runtime.js`: backend-only secret configuration and AWS transport.
- `backend/wecare/security.js`: HMAC validation of exact notification bytes.
- `backend/wecare/notifications.js`: callback claim/submit/ack orchestration.
- `backend/http-functions.js`: merge callback export into the site's existing file.
- `tests/adapter.test.js`: local contract/security tests; these do not test the Wix runtime.

Create the Payment service plugin named `wecare` using Wix's supported site workflow, then populate the generated files. Payment Provider is NOT the CLI ECOM_PAYMENT_SETTINGS service plugin; do not substitute it. Do not create a Wix CLI application merely to satisfy a scaffolding workflow intended for a different extension.

The live connector lookup confirmed Editorless, Velo enabled and Catalog V3. A dashboard inspection on 2026-09-30 found Developer Tools exposing logs, monitoring, secrets and triggered emails, but no Velo code editor or service-plugin installer; Website Overview had no Edit Site action. The existing repository explicitly states its previous Velo project was deleted. No supported installation target is currently established. Confirm an existing compatible Wix site/runtime before installation. If it does not, report the exact supported deployment gap and preserve the code; do not create/migrate a site or claim installation. No App Market distribution is included.

# 73. SECRET CONFIGURATION

Create one backend secret `WECARE_WIX_BRIDGE_CONFIG`, containing JSON with:

- `initiationEnabled`: defaults to false; set true only after deployment and end-to-end readiness checks. This switch does not disable callback reconciliation or refunds.
- `merchantId`: the actual Wix Payments merchant ID, not guessed from the site ID.
- `accountId`: WECARE bridge account identifier, verified server-side.
- `bridgeBaseUrl`: exact HTTPS prefix on the existing AWS API, no trailing slash/query.
- `bridgeToken`: independent high-entropy server credential, at least 32 characters.
- `callbackKey`: separate high-entropy HMAC key, at least 32 characters.
- `hostedOrigins`: exact HTTPS origins for the existing WECARE hosted handoff.
- `returnOrigins`: exact Wix return origins verified in actual callback fixtures.

Never accept bridge URLs or origins from customer requests. Restrict bridge credentials to one site/merchant/account. Do not use the Razorpay secret as the bridge token or callback HMAC key. Do not paste secrets in chat or commit them. Rotate through the existing secret management process.

# 74. AWS BRIDGE CONTRACT — IMPLEMENT IN EXISTING SERVICES

All operations are POST JSON under configured bridgeBaseUrl. These are proposed internal operations, not asserted deployed routes. Every operation authenticates the bearer token at the Lambda layer and enforces the configured merchant/account scope. Reuse existing handlers and tables; adapt paths in runtime.js if existing equivalent routes are found.

`connect`: request `{wixMerchantId, accountId}`. Validate merchant binding and account access; return `{connected:true, accountId}`. Connection does not mean Meta payment readiness.

`create-transaction`: request `{wixMerchantId, accountId, wixTransactionId, wixOrderId, amountPaise, currency, returnUrls, idempotencyKey}`. Here wixOrderId is the Wix payment-provider order reference. Resolve its actual commerce association by supported APIs. Read authoritative commerce totals/inventory; verify customer session binding and live Meta/Razorpay readiness BEFORE reserving a PaymentAttempt. Return `{ready:true, wixTransactionId, wixOrderId, accountId, amountPaise, currency, pluginTransactionId, redirectUrl}` only after durable reservation. pluginTransactionId is the stable PaymentAttempt identifier. redirectUrl points to an opaque, scoped, expiring hosted session. No success status is returned at creation.

`refund-transaction`: request `{wixMerchantId, accountId, wixTransactionId, pluginTransactionId, wixRefundId, amountPaise, idempotencyKey}`. Resolve original captured payment and credentials server-side, enforce remaining refundable balance under concurrency, persist reservation before provider call, reuse current refund integration. Return bound identifiers plus `pluginRefundId` and `status: REFUNDED_VERIFIED` only after authoritative completion. For pending/unknown return a non-final result; the supplied Velo adapter refuses to claim success. Reconcile asynchronously using the same refund IDs and test Wix's pending/refund callback behavior before activation.

`claim-notification`: request `{eventId, wixMerchantId, accountId}`. Authenticate then atomically claim an outbox lease. Reply `{eventId,state:ACKED}` for completed delivery; `{eventId,state:CLAIMED,leaseToken,record}` for a durable lease. Busy/unavailable gives a retryable non-2xx response. The stored record includes `verified:true`, scope IDs, currency, amountPaise, kind, status, wixTransactionId, pluginTransactionId; refunds also include wixRefundId/pluginRefundId. Resolve fields from stored payment state; never trust notification-body status or arbitrary record IDs.

`ack-notification`: request `{eventId,leaseToken,wixMerchantId,accountId}`. Conditionally acknowledge the matching active lease and reply `{eventId,state:ACKED}`. A crash after Wix accepts but before ACK creates an ambiguous delivery; reconcile Wix status and use stable transaction/refund IDs. Prove Wix replay semantics in integration tests rather than assuming exactly-once network delivery.

# 75. DURABLE IDENTITY AND RETRY CONTRACT

Deduplicate create calls by merchantId+wixTransactionId. Store a canonical request digest covering order, INR amount and return URLs: same key/different digest is a conflict. Lost responses resume the stored attempt, never start another charge. An eight-second Velo timeout does not cancel a provider-side request.

Also lock by resolved commerce order/customer checkout to prevent a second Wix transaction from charging an active/paid order. Recheck stock and price before initiation, snapshot the accepted amount, and define stock reservation/expiry. A captured payment with later inventory failure needs explicit refund/manual resolution, not another charge.

Reuse the existing DynamoDB reservation/idempotency utilities. Lease/outbox state must be durable across Lambda restarts. Never rely on in-memory deduplication. Once paid, older failure events cannot downgrade it. Late capture must be handled as financial truth even if an earlier local timeout occurred. Multiple actual captures require refund/reconciliation and never duplicate fulfillment.

# 76. CALLBACK DELIVERY CONTRACT

AWS POSTs to the published Wix HTTP function `/_functions/wecarePaymentEvent` using the actual verified site origin.

Raw UTF-8 JSON body contains only `{"eventId":"durable-outbox-event-id"}`.
Headers: `x-wecare-timestamp` is epoch seconds; `x-wecare-signature` is lowercase hex HMAC-SHA256(callbackKey, timestamp + "." + exactRawBody).

Velo rejects signatures older/newer than five minutes and bodies over 8192 bytes. AWS signs each retry freshly but keeps eventId stable. HMAC authentication does not itself deduplicate; the durable claim/ACK protocol does. Rate-limit callback traffic at the supported edge/handler layer, bound provider/bridge timeouts and redact logs.

Only AWS performs Meta/Razorpay signature checks and authoritative provider lookup. Velo retrieves the stored verified event from AWS before submitEvent. Never create an unauthenticated “mark paid” endpoint. Ignore customer-supplied success flags and amount/status query strings.

# 77. HOSTED PAYMENT HANDOFF

Reuse existing WECARE public frontend. It may display Pay securely on WhatsApp and pending/paid/finalizing/failure states, with an expiring opaque session bound server-side to the verified customer and PaymentAttempt. Do not expose long-lived tokens, PII or prices as authority in URLs. Establish a scoped session safely and prevent IDOR/session fixation.

Use the immutable Wix return URLs captured server-side. Browser return is navigation only, not proof. Payment success, cancel and pending redirects must correspond to authoritative state. A browser close/cancel intent does not override a captured or still-pending provider payment.

# 78. NOTIFICATION AND EMAIL COMPATIBILITY

Preserve WhatsApp-only purchase receipt/confirmation and SES email for verification/security. Audit Wix's built-in order confirmation emails and automations; suppress duplicate purchase emails through supported controls. If Wix cannot meet this requirement in the selected setup, explicitly report it before live activation. Do not claim the AWS email rule automatically controls Wix emails.

Deduplicate receipts by internal paid order. For WhatsApp send timeouts, use durable send state/provider message reconciliation; do not claim a distributed exactly-once guarantee without evidence. Queue messages when the window is closed until a permitted approved template is available.

# 79. VALIDATION AND RELEASE

Run local bundle tests with `npm test`. Then validate Velo imports, built-in crypto support, Secrets API response, HTTP function response, handler error payloads, callback replay, pending/refund semantics and plugin registration in the actual Wix environment. Local Node tests are not Wix build/deployment proof.

Test bridge credential rejection, wrong merchant/account, authoritative amount mismatch, missing Meta config, customer association, replay, concurrent lease, lost ACK, late capture, partial refunds, over-refund, and two transaction IDs for one commerce order. Add a no-network live-charge guard to automated tests.

Deployment order: existing AWS bridge and durable outbox (disabled for initiation) → hosted handoff → Velo callback and plugin → restricted test merchant → provider setup/readiness → end-to-end test → deliberate live activation. Do not mutate Meta configs/templates or enable real payments silently. Keep existing production services and unrelated handlers working.

Rollback: disable new initiation first; preserve callbacks, refund handling and reconciliation for in-flight funds. Never delete PaymentAttempts/mappings or roll back paid state. Record deployed versions and restore prior routing safely.

# 80. OFFICIAL REFERENCES

- Velo integration: https://dev.wix.com/docs/develop-websites/articles/code-tutorials/wix-pay/tutorial-payment-provider-service-plugin
- Create transaction: https://dev.wix.com/docs/velo/events-service-plugins/payments/service-plugins/wix-payments/payment-provider/create-transaction
- Connect account: https://dev.wix.com/docs/velo/events-service-plugins/payments/service-plugins/wix-payments/payment-provider/connect-account
- Refund: https://dev.wix.com/docs/velo/events-service-plugins/payments/service-plugins/wix-payments/payment-provider/refund-transaction
- Event updates: https://dev.wix.com/docs/velo/apis/wix-payment-provider-backend/submit-event
- Reason codes: https://dev.wix.com/docs/api-reference/business-management/payments/payment-service-provider-service-plugin/reason-codes
- Secrets: https://dev.wix.com/docs/velo/apis/wix-secrets-backend-v2/secrets/get-secret-value
- WhatsApp policy: https://business.whatsapp.com/policy
- Meta India payment docs: https://developers.facebook.com/documentation/business-messaging/whatsapp/payments/payments-in/overview

Re-read current official schemas before implementing backend provider calls. Do not infer missing request fields from examples. Record which claims were verified from docs, from repository inspection, from mocks, from sandbox and from live production.


## 81. Verified deployment target and current repository correction


The Velo source is implemented and locally tested, but is not deployed or active.

## Verified account surfaces

- Existing site: WECARE.DIGITAL, fcd82f0c-9572-49c7-acfb-88fb05042ece. Connected site reports Editorless. Dashboard exposes no Velo editor or Payment service-plugin installation workflow.
- Existing custom app: WECARE.DIGITAL, 6cbf8eaf-264d-495a-bde1-d63d016d58a9, released version 3.0, one installation. Its sole listed extension is the self-managed WECARE Dashboard Page.
- Inspected the app's Create Extension catalog. Payment Provider is absent. Ecom Payment Settings is present, but is a different integration and must not be substituted.
- Wix's official PSP introduction requires business-development onboarding before PSP integration: https://dev.wix.com/docs/api-reference/business-management/payments/payment-service-provider-service-plugin/introduction
- The external PSP path is distinct from this Velo package and needs Wix-approved app capabilities and request authentication. Do not present these Velo modules as a deployable external PSP server.

## Work remaining

A supported site Velo runtime or Wix-approved PSP onboarding must establish the deployment target. No site migration, additional site, app release, provider onboarding submission, payment configuration change, or live charge/refund was performed.

The AWS bridge, hosted session, DynamoDB idempotency/outbox and end-to-end provider reconciliation remain unimplemented dependencies of the adapter. Local tests simulate them. Backend work must not invent a customer identity mapping from payment email/phone or assume a Wix payment order reference equals an eCommerce order ID.

## Current repository correction

The repository payment_readiness module contains a newer owner correction naming acc_TTFSyolquKEZEy as authoritative and acc_HDfub6wOfQybuH as stale evidence. The attachment states the reverse. Treat both as historical evidence until current Meta/Razorpay reads verify the binding. Do not overwrite current configuration from the attachment.

## Source integration

The source package was copied into integrations/wix-velo-payment in the existing /Users/wecaredigital/wecare-store repository on stack. The isolated package test command is npm test from that directory. It does not participate in the Next.js frontend build and contains no credentials.


## 2026-10-01 — Headless compatibility recheck

This repository is self-managed Next.js/AWS headless; docs/wix-headless.md explicitly records no Velo runtime and deletion of the old CLI/Velo project. A Git push of this package does not deploy Velo.

Wix-managed headless does support hosted backend code through its CLI, but is a different development path. That general capability does not establish support for this site-specific Velo Payment service plugin. The official plugin tutorial requires a site Code sidebar Payment plugin and publication. No supported direct deployment path exists in the inspected current project.

Sources:
- https://dev.wix.com/docs/overview/backend-services/backend-development-on-wix
- https://dev.wix.com/docs/develop-websites/articles/code-tutorials/wix-pay/tutorial-payment-provider-service-plugin

Retain this package as inactive integration source. Do not claim it executes in AWS or Wix without the appropriate runtime, implemented bridge and platform validation.
