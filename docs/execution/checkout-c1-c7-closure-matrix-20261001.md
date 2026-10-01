# Checkout collision closure matrix — C1–C7 + C3b

**Created 2026-10-01 by Phase A. Every item is OPEN. Phase A documents; it closes nothing.**

This is the tracking artifact for the eight confirmed collisions in the headless checkout path.
Later phases update the Status column here as they close each item — do not record a closure in a
new document.

Evidence base, with file:line citations for every row:
[`checkout-consolidation-findings-20261001.md`](checkout-consolidation-findings-20261001.md).
Line numbers below are current at HEAD `6a5d6e9ea6fe0097bf246a34ab6138c6919935d7` and will drift;
re-derive them rather than trusting them.

Owner architecture decision: one active checkout = **standalone Wix Headless + AWS +
WhatsApp/Razorpay**. See `.kiro/specs/whatsapp-wix-commerce/design.md` **D8**.

## The matrix

| # | Finding (one line) | Status | Code location(s) | Owning phase | Evidence |
|---|---|---|---|---|---|
| **C1** | `_create_order_for_captured_payment` is called for effect only — its return value is never bound, so the invoice, GST document, Meta Purchase conversion and `order_status` message all fire whether or not an order exists | 🔴 **OPEN** | `amplify/functions/payments/razorpay-webhook/handler.py:663-664` (unbound call), `:667-673`, `:676`, `:681` (ungated side effects); callee declared `-> Dict` at `:431-432`, returns at `:505` / `:517`; classification `amplify/functions/shared/lambda_utils/ecommerce/order_creation.py:70-73` (`NO_ORDER_OUTCOMES`), `:105-107` (`needs_human`) | **B** | [C1](checkout-consolidation-findings-20261001.md) |
| **C2** | A competing master prompt declared `WIX_NATIVE_PROVIDER` "the new checkout path" and claimed to supersede the current plan. **No dual-mode router was ever built in runtime code** — the contradiction was documentation-only | 🔴 **OPEN** | Deleted in Phase A: `integrations/wix-velo-payment/KIRO-IMPLEMENTATION-PROMPT.md:15,659,755,968,969,1079,1089,1093,1431,1457,1465,1564,1607,1679`, `integrations/wix-velo-payment/INSTALLATION.md:14,35,41,52`, `backend/http-functions.js:8`, `backend/wecare/notifications.js:5,29`. Surviving runtime label (correct, leave alone): `amplify/functions/ecommerce/checkout/handler.py:75,261,275` `CHECKOUT_MODE = "WIX_HEADLESS"` | **B** | [C2](checkout-consolidation-findings-20261001.md) |
| **C3** | `_send_order_details` posts to `/wa-business/messages/send/interactive-payment`, which the business-API dispatcher answers **404** — every suffix test fails, so the checkout returns `502 SEND_FAILED` | 🔴 **OPEN** | `amplify/functions/ecommerce/checkout/handler.py:363-377` (the invented path), `:386` (the `<300` check); dispatcher `amplify/functions/messaging/whatsapp-business-api/handler.py:5799`, `_route_send_message` at `:2179-2199` | **C** | [C3](checkout-consolidation-findings-20261001.md) |
| **C3b** | **New in this investigation.** The readiness readback posts `/wa-business/payment-config/raw` with `wabaId`; the dispatcher substring-matches `/payment-config` and demands `phoneId`, answering **400**. `payment_readiness` maps any `error` to `META_UNAVAILABLE`, so **the readiness gate can never pass** and checkout returns `409 payment_unavailable` before it ever reaches the send | 🔴 **OPEN** | `amplify/functions/ecommerce/checkout/handler.py:121-129`; dispatcher `amplify/functions/messaging/whatsapp-business-api/handler.py:6101-6125`; `amplify/functions/shared/lambda_utils/payment_readiness.py:258-259`. The route that **does** exist and does take `wabaId`: `GET /wa-business/payment-config/check` (handler `:6101`, `_check_payment_gateway`) | **C** | [C3](checkout-consolidation-findings-20261001.md) — "The readiness readback — new finding" |
| **C4** | Nothing anywhere in the tree ever **writes** `providerPaymentId` or `providerOrderId`. The verifier requires one of them, so every real capture raises `RazorpayUnavailable` → `PROVIDER_UNAVAILABLE`. A hard deadlock, not a gap | 🔴 **OPEN** | Requirement: `amplify/functions/shared/lambda_utils/integrations/razorpay_verify.py:159-178`. Non-writers: `ecommerce/payment_attempt.py:165-179` (`build`, no provider fields), `:279-282` (`transition`, only if a caller passes them); `ecommerce/checkout/handler.py:276-277` (calls `transition` with neither kwarg), `:258-263` (`PAYREF#` row, no provider fields), `:396-419` (`_mark_request_sent`); reader `payments/razorpay-webhook/handler.py:465-473`. Catch site `ecommerce/order_creation.py:223-227` | **C** | [C4](checkout-consolidation-findings-20261001.md) |
| **C5** | Checkout uses `wix_ecom.create_checkout` → `POST /ecom/v1/checkouts` (**Checkout V1**) and stores `wixCheckoutId` — the exact artifact design D4 says does not exist, on the API version Wix removes 2027-02-01. Cart V2 is wired only into `wix-store`; the two paths never meet, so there is **no cart-to-checkout handoff** | 🔴 **OPEN** | `amplify/functions/ecommerce/checkout/handler.py:225-236`; `amplify/functions/shared/lambda_utils/wix_ecom.py:139-157`. Cart V2 lives at `amplify/functions/ecommerce/wix-store/handler.py:363-364` and `shared/lambda_utils/ecommerce/customer_cart.py:15`, gated off at `wix-store/handler.py:370-371` (`WIX_CART_V2_ENABLED`, unset live). Contradicts `.kiro/specs/whatsapp-wix-commerce/design.md:90-93` (D4) and `:88` (D7) | **D** | [C5](checkout-consolidation-findings-20261001.md) |
| **C6** | The status contract is broken at both ends: nothing ever persists `PAYMENT_PAID` to `PaymentAttemptsTable`, and the status endpoint never resolves an order number — while the UI requires **both** before it will redirect. The customer waits five minutes on "Confirming your payment" and then a dead screen | 🔴 **OPEN** | Producer: `shared/lambda_utils/ecommerce/order_creation.py:266-267` (local dict only); constant/set/branch at `ecommerce/payment_attempt.py:67`, `:74`, `:268-269`. Endpoint: `ecommerce/checkout/handler.py:329-331` (no `order_number=` passed), defaulting at `payment_attempt.py:291`, `:307`, `:313-315`. UI: `src/pages/checkout/status.tsx:69-74`, `:125-131`, `:76-81`, `:53`, `:47`; contract stated at `src/pages/checkout/success.tsx:4` | **E** | [C6](checkout-consolidation-findings-20261001.md) |
| **C7** | Deployment reality: **no `wecare-checkout` function exists** and there are **zero `/ecommerce/*` routes** on API `zllr9lrg7j`. `wecare-wix-store:live` v31 contains none of the ecommerce modules; four more are deployed at older revisions than HEAD; live `RAZORPAY_MID` and `RAZORPAY_UPI_ID` are stale | 🔴 **OPEN** | `GetFunctionConfiguration wecare-checkout` → `ResourceNotFoundException`. API `zllr9lrg7j`: 359 routes, `NextToken: null`, 0 `/ecommerce/*`, 0 `/messages/send/*`. `config/lambda-env-manifest.json` has no `checkout` entry. Provisioner `scripts/provision_checkout.py:223`, `:269-271`. Packaging `scripts/deploy_all_lambdas.py:383-402` (bundled, not layered) | **E** | [C7](checkout-consolidation-findings-20261001.md) |

## Status vocabulary for this matrix

`🔴 OPEN` · `🟡 IN PROGRESS` · `✅ CLOSED` (fix landed **and** verified — a passing test is not
closure for an item whose finding is that tests cannot see the seam) · `⛔ BLOCKED`
(name the blocker and the exact unblock) · `➖ SUPERSEDED`.

**Closing a row requires the same standard of evidence that opened it.** Every one of these eight
was confirmed by reading code and, for C7, by reading live AWS. A row moves to `✅ CLOSED` with a
citation of comparable weight, not with an assertion.

## Two things to read before working any row

**C1 + C4 together are the dangerous combination, and they are why this matrix exists.** The
missing binding (C4) makes reconciliation return `PROVIDER_UNAVAILABLE`, which sits in
`NO_ORDER_OUTCOMES` and therefore reports `needs_human = False`; C1 then discards the result
anyway. The net behaviour: money is taken, the invoice is marked paid, the GST invoice is generated
and sent on WhatsApp, a Meta Purchase conversion fires, the customer is told the order is
confirmed — and **no order exists**, logged as a `warning`. The one failure this domain must never
have silently is currently wired to be silent. `OrderTable` holding 0 items is the only reason it
has not happened.

**The four functional breaks are in series, so fixing one alone changes nothing observable.** The
order is C3b (readiness readback) → C3 (payment send) → C4 (provider binding) → C6 (status and
order number). A green test run is not evidence against any of them: 236 checkout tests pass
because each stub sits exactly where production breaks — the verifier is replaced with
`lambda _r: (True, TXN, AMOUNT, 'INR')`, and the checkout test's fake Lambda answers `200` for any
path containing `payment-config` and `200` for the send, so it cannot distinguish a real route from
an invented one.

## Phase ownership

| Phase | Owns | Items |
|---|---|---|
| **A** | Documentation and safe deletion. Retire the prototypes, neutralize the competing prompt, reconcile the specs, publish this matrix | none closed — A is the phase that wrote this file |
| **B** | Consume the reconciliation outcome at the call site; correct the outcome classification so a structural verification failure alarms instead of reporting "no money moved" | C1, C2 |
| **C** | Point the two invented routes at real ones; make something write the provider binding before the webhook needs it | C3, C3b, C4 |
| **D** | Migrate checkout onto the Cart V2 boundary; retire `wixCheckoutId` and the V1 call | C5 |
| **E** | Close the status loop; provision the function, the routes and the corrected environment | C6, C7 |

Phase A changed no runtime code, called no AWS mutation, and deployed nothing. The deletions it
performed are recorded in
[`change-authority-matrix.md`](change-authority-matrix.md) under
"2026-10-01 — Phase A: checkout consolidation, documentation and prototype retirement".
