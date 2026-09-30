# External Wix PSP integration — 2026-10-01

## Implemented

`request-auth.js` verifies the external PSP Digest JWT with a pinned RSA public key, RS256, expiration/issue time and SHA256 over exact request bytes. Sixteen offline tests pass. This is an isolated Node module, not deployed to the existing Python Lambda and not a functioning payment gateway.

## Required business clarification

The official application at https://www.wix-providerplatform.com/ asks whether the applicant holds a PSP license, uses white-label processing or acquiring partners. WECARE's own Razorpay merchant account is not evidence of such an arrangement. Eligibility and approval are unknown. Do not submit claims of licensing, white-label rights, PCI status, transaction volume or third-party merchants without owner-provided facts.

Owner must clarify: own merchant only; authorized processor/white-label arrangement; or existing Wix PSP approval. If already approved, identify the approved app and onboarding reference. The existing app is 6cbf8eaf-264d-495a-bde1-d63d016d58a9.

## Draft technical description for owner review — not submitted

WECARE.DIGITAL seeks to offer a branded hosted payment option in Wix native checkout while retaining its existing Next.js frontend and AWS backend. Razorpay would remain the underlying processor. The proposed integration would validate Wix-signed requests, bind each payment to a Wix transaction, preserve idempotency, verify provider capture before reporting success, and reconcile refunds and asynchronous notifications. Please confirm whether a single merchant using its own Razorpay account is eligible, or whether an approved PSP/white-label partnership is required.

## Missing before deployment

Wix approval and PSP extension access; approved merchant/processor relationship; pinned Wix app public key; PSP OAuth permissions for Submit Event; request/response conformance for connect, transaction and refund; durable idempotency and notification delivery; hosted payment handoff; customer identity association; implemented Razorpay/Meta operations; platform and sandbox certification. The Velo adapter's AWS bridge remains unimplemented. No credentials, routes, provider settings, application submission, payment requests or charges were changed.

## References

- https://dev.wix.com/docs/api-reference/business-management/payments/payment-service-provider-service-plugin/introduction
- https://dev.wix.com/docs/api-reference/business-management/payments/payment-service-provider-service-plugin/validate-endpoint-requests
- https://github.com/wix-incubator/payment-spi-sample/blob/master/jwt-validation.mjs
