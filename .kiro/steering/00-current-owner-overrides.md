---
inclusion: always
---

# CURRENT OWNER OVERRIDES — HIGHEST PRIORITY

This file overrides conflicting requirements in the master prompt (`bw-crm.md`)
and in every other steering file. Where this file and any other instruction
disagree, **this file wins**.

## Security decisions

- AWS WAF is **not MANDATORY**.
- Administrator MFA is **not MANDATORY**.
- Security Hub is **EXCLUDED**. Do not enable it.
- GuardDuty is **OPTIONAL** and is not a project completion blocker.

## Project boundary

Android/iOS native packaging and optimization are **POST-PROJECT**.

The main web project may close without:

- APK
- AAB
- IPA
- App Store / Play Store work
- native signing
- native device optimization

The web application must only remain WebView/WKWebView-ready.

## Execution rule

**DO NOT trust dated AWS/GitHub counts in the master prompt.**

Before each phase, rediscover current:

- Git HEAD
- AWS resources
- API routes
- Lambda versions/aliases
- DynamoDB resources
- IAM
- Cognito
- WAF
- provider state

**Never reset to a historical SHA.**

## Current security baseline

Latest read-only verification (a snapshot, not a standing truth — rediscover per
the execution rule above):

| Item | Observed |
|---|---|
| Lambda functions | 58 |
| HTTP APIs | 2 |
| HTTP API routes | 332 |
| API Gateway authorizers | 0 |
| Routes reporting `AuthorizationType=NONE` | 332 |
| Regional WAF WebACLs | 0 |
| Cognito pool | WECARE.DIGITAL |
| Cognito MFA | OFF |
| GuardDuty detectors | 0 |
| Security Hub | not subscribed |

Interpret `AuthorizationType=NONE` carefully: handler-level authentication and
signature checks may still exist.

## Required target

- Admin MFA must be implemented and verified.
- WAF must be implemented and live-verified.
- User APIs must have an explicit authentication strategy.
- Provider webhooks remain publicly reachable where required, protected using
  provider signature verification.
- Security Hub must remain excluded.
- GuardDuty may be evaluated but must not block closure.

Note the deliberate shape of this section: WAF and admin MFA are not *mandatory
gates* inherited from the master prompt, but they **are** required targets here.
"Not MANDATORY" removes the master prompt's blocking semantics; it does not
remove the work.

## Provider rules

All provider restrictions and protected-resource rules from the master prompt
remain unchanged.

## Native project

Native work belongs to a separate document:

    99-post-project-android-ios-native.md

It cannot block completion of the main project.
