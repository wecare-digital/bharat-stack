---
inclusion: always
---

# CURRENT OWNER OVERRIDES — HIGHEST PRIORITY

This file overrides conflicting requirements in the master prompt (`bw-crm.md`)
and in every other steering file. Where this file and any other instruction
disagree, **this file wins**.

## Security decisions

- AWS WAF is **REMOVED**, by owner decision on 2026-09-28, as a cost decision. There
  is no web ACL in this account in either scope. Do not re-create one, and do not
  report its absence as a gap to close — see "WAF is removed" below.
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

**Do not quote counts from this file.** Per the execution rule above, run

    python scripts/aws_account_inventory.py

which enumerates fourteen service families in ~150s and writes
`docs/execution/aws-inventory.json` and `.md`, plus the judgement in
`docs/execution/aws-inventory-findings.md`. It reports its own `error_count`; a
non-zero count means the inventory is PARTIAL and must not be used for
decisions.

Last full enumeration **2026-09-26, 0 collector errors**. What moved against the
previous snapshot, as a record of drift rather than a value to reuse:

| Item | Earlier snapshot | 2026-09-26 |
|---|---:|---:|
| Lambda functions | 58 | 65 |
| — with a `live` alias | — | 58 |
| HTTP APIs | 2 | 1 (`zllr9lrg7j`) |
| HTTP API routes | 332 | 361 |
| API Gateway authorizers | 0 | 0 |
| Routes reporting `AuthorizationType=NONE` | 332 | 361 |
| Regional WAF WebACLs | 0 | 1 on 2026-09-26 → **0 on 2026-09-28, deleted** |
| CloudFront-scope WAF WebACLs | — | 1 on 2026-09-26 → **0 on 2026-09-28, deleted** |
| CloudWatch alarms | — | 41, all routable to a human |
| Cognito pools | WECARE.DIGITAL | 2 (+ WECARE.DIGITAL-CUSTOMERS) |
| Cognito MFA (admin pool) | OFF | OPTIONAL |
| GuardDuty detectors | 0 | not re-measured |
| Security Hub | not subscribed | excluded by owner |

The route surface grew by 29 while authorization stayed at zero, so the gap
widened rather than closed.

## WAF is removed

Deleted 2026-09-28 on owner instruction, as a cost decision. Both web ACLs are gone:

| Deleted | Scope | Was protecting |
|---|---|---|
| `wecare-cognito-waf` | REGIONAL | staff pool `us-east-1_cSx0RHCIR` **and** customer pool `us-east-1_46ULYuukt` |
| `wecare-amplify-waf` | CLOUDFRONT | Amplify app `d22dm4b0jn71jw` (dashboard + public site) |

Verified after deletion: `list_web_acls` returns **0** in both scopes,
`get_web_acl_for_resource` returns nothing for both pool ARNs, and the Amplify app's
`wafConfiguration` is `null`.

**State the cost honestly.** WAF billing was roughly $18/month at list price, but
credits currently absorb it, so the realised saving today is **$0.00**. The saving
only materialises if credits lapse. The protection loss was immediate.

What is now the only request filtering, so nobody assumes WAF still backstops it:
handler-level `require_auth`, provider HMAC verification on webhooks,
`lambda_utils/rate_limit.py`, the per-phone OTP probe counter in the Cognito trigger,
and API Gateway stage/route throttling. There is **no per-IP protection in front of
public customer OTP sign-in any more**, which is a genuine open exposure rather than a
solved one.

Restore path, kept deliberately: `python3 scripts/provision_waf.py --apply`. Prior
state including every rule and association is in
`docs/execution/snapshots/waf-associations-before-delete-20260928.json` and the
`waf-*-before-delete-20260928.json` files beside it. The WAF log groups
`aws-waf-logs-wecare-amplify` and `aws-waf-logs-wecare-cognito` were **retained**.

The measurement caveat below is kept because it will matter again if WAF ever returns,
and because it explains why earlier audits misread the association state.

**Never read a WAF association with `list_resources_for_web_acl` alone.** It
defaults `ResourceType` to `APPLICATION_LOAD_BALANCER`, this account has none, and
it does not enumerate Cognito pools, Amplify apps or CloudFront at all — so a
correctly protected ACL reads as protecting nothing. That false reading has now
been produced twice by two different sessions. Use
`get_web_acl_for_resource(<resource arn>)` per resource, or the app's own
`wafConfiguration` for Amplify.

Interpret `AuthorizationType=NONE` carefully: handler-level authentication and
signature checks may still exist. Gateway configuration alone cannot distinguish
an intentionally public signed webhook from an accidentally public API.

## Required target

- Admin MFA must be implemented and verified.
- ~~WAF must be implemented and live-verified.~~ **Withdrawn 2026-09-28.** WAF is
  removed by owner decision; it is no longer a required target and its absence is
  not a gap to close.
- User APIs must have an explicit authentication strategy.
- Provider webhooks remain publicly reachable where required, protected using
  provider signature verification.
- Security Hub must remain excluded.
- GuardDuty may be evaluated but must not block closure.

Note the deliberate shape of this section: admin MFA is not a *mandatory gate*
inherited from the master prompt, but it **is** a required target here. "Not
MANDATORY" removes the master prompt's blocking semantics; it does not remove the
work. WAF used to be listed the same way and no longer is, because the owner removed
the resource itself rather than downgrading the requirement.

## Provider rules

All provider restrictions and protected-resource rules from the master prompt
remain unchanged.

## Native project

Native work belongs to a separate document:

    99-post-project-android-ios-native.md

It cannot block completion of the main project.
