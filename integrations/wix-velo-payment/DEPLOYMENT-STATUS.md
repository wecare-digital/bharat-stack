# Wix deployment verification — 2026-09-30

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
