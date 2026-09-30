# WECARE.DIGITAL Velo payment-provider handoff

Prepared 2026-09-30. This package contains Velo source and local tests, not a deployed gateway. Use the accompanying revised Kiro prompt to implement its AWS bridge in the existing application. The bridge endpoints, hosted session, durable outbox, and provider verification are required dependencies, not services included in this package.

## What is implemented

- WECARE.DIGITAL hosted payment method configuration.
- Account connection, payment creation and refund adapters.
- Positive integer paise validation and INR enforcement.
- Fixed merchant/account binding and exact HTTPS origin checks.
- Stable transaction/refund idempotency keys passed to AWS.
- Backend-only secret loading and bounded bridge response wait.
- HMAC-authenticated callback; status is retrieved from AWS rather than accepted in callback data.
- Mapping verified capture/refund/terminal payment records into Wix submitEvent payloads.
- Callback orchestration tests covering forged/duplicate notifications, busy leases, unknown state, Wix failures and lost ACKs.
- Payment initiation disabled by default through `initiationEnabled`; callback reconciliation and refunds remain independent.

## Deploying to the existing Wix site

1. Confirm the target site's supported Velo workflow. The connected site inventory reported WECARE.DIGITAL as Editorless with Velo enabled; that alone does not prove its payment-plugin installation path is available. Do not migrate or create another site to bypass this check.
2. In the supported Wix site development environment, add a **Payment** service plugin named `wecare`. Populate its generated config and handler files with `velo-service-plugin/wecare-config.js` and `velo-service-plugin/wecare.js`. This is not an ECOM_PAYMENT_SETTINGS CLI extension.
3. Add the five files in `backend/wecare/`. Keep them backend-only, not `.web.js` or public files.
4. Merge the callback imports/export from `backend/http-functions.js` into the existing HTTP functions file. Preserve existing endpoints.
5. Implement the authenticated AWS bridge operations from sections 74–76 of the revised prompt in existing services. Never point the connector at a guessed live endpoint.
6. Set Wix secret `WECARE_WIX_BRIDGE_CONFIG` using the exact field definitions in section 73. No production credentials are supplied. The merchant ID must come from Wix Payments evidence, not the site ID.
7. Validate Velo imports, crypto availability and Secrets API response in the actual site runtime. Use actual Wix callback fixtures to verify schemas, refund timing and order-reference resolution.
8. Publish the tested plugin, then connect WECARE.DIGITAL through Wix Accept Payments using its WECARE account ID. Connect only after the bridge validates its merchant/account binding. A connected account is not payment readiness.
9. Configure AWS's notification destination to the published site's `/_functions/wecarePaymentEvent`. Test HMAC verification, durable lease/ACK recovery and stable-event replay before live use.
10. Verify the entire payment/refund flow and current Meta/Razorpay readiness before live activation. Audit Wix purchase emails to preserve WhatsApp-only confirmations.

## Important boundaries

The plugin uses Wix's hostedPage flow, so payment processing requires a hosted handoff. It does not embed custom card fields in Wix checkout. Razorpay remains the processor specified in the supplied prompt; no alternative provider or direct-payment fallback has been added.

Native Wix checkout provides a payment-order reference before capture. AWS must resolve its documented commerce-order mapping rather than assuming options.order._id equals an eCommerce order ID. Do not create another Wix order or externally record the same capture after submitEvent.

Only internal WECARE paid-order identity is delayed until verified capture. Wix may retain unpaid artifacts. The revised prompt explicitly corrects the earlier blanket zero-Wix-orders claim.

Refund adapter success requires REFUNDED_VERIFIED. An accepted/processing refund returns a generic non-success response and must be reconciled asynchronously under the same wixRefundId. The intended asynchronous behavior must be tested in Wix before release; this bundle does not claim that lifecycle has been validated.

The eight-second bridge wait does not cancel an in-flight mutation. AWS must persist idempotency state before calling a provider and recover ambiguous responses. A five-minute signature window does not prevent replay by itself: AWS durable event leases/ACKs and monotonic transaction state are mandatory. A crash after submitEvent and before ACK is an ambiguous remote outcome; prove replay/readback behavior in Wix before activation.

## Local validation

Run `npm test` in this directory. The package has no npm dependencies for local tests; Wix platform imports are supplied by the Wix runtime. Local tests exercise pure adapter/security logic with simulated bridge responses. They do not prove AWS deployment, live provider readiness, Velo compilation or an actual charge/refund.

See TEST-RESULTS.txt for the captured local run. No live provider mutation, financial transaction or site publication was performed when preparing this package.

## Official references

- [Velo payment-provider tutorial](https://dev.wix.com/docs/develop-websites/articles/code-tutorials/wix-pay/tutorial-payment-provider-service-plugin)
- [Wix submitEvent](https://dev.wix.com/docs/velo/apis/wix-payment-provider-backend/submit-event)
- [Wix reason codes](https://dev.wix.com/docs/api-reference/business-management/payments/payment-service-provider-service-plugin/reason-codes)

## Deployment inspection — 2026-09-30

The live Wix connector confirmed site fcd82f0c-9572-49c7-acfb-88fb05042ece is Editorless, with Velo flag enabled and Stores Catalog V3. The authenticated dashboard exposed Developer Tools for logs, monitoring, secrets and triggered emails. Website Overview exposed no Edit Site action; Site Actions offered rename, transfer, invite, duplicate and trash. No code editor or service-plugin installer was exposed. The inspected repository's docs/wix-headless.md says its previous Velo project was removed.

This proves that the checked dashboard does not expose the required installation workflow; it is not a claim that every Wix Headless project categorically lacks all backend extension mechanisms. No supported Velo deployment target has been established for this specific site. An existing compatible Wix Editor/Studio site or a Wix-supported way to attach the plugin to this project is needed before installation. Do not silently create a second site or migrate the production project.

The AWS bridge has not been implemented or deployed by this Velo source package. It cannot process payments merely by installing these files. This boundary remains explicit in the revised prompt.
