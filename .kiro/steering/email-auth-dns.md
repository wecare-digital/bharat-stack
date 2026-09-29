---
inclusion: always
---

# Email authentication is fail-closed - read before touching MX or adding a sender

`wecare.digital` runs two **fail-closed** email policies. Under both, a
misconfiguration causes mail to be **rejected outright**, not filtered into
spam. There is no soft-fail state to catch mistakes.

## Current posture

| Control | Value | Failure mode if broken |
|---|---|---|
| DMARC | `p=reject; sp=reject` (relaxed alignment) | unaligned outbound mail hard-bounces |
| MTA-STS | `mode: enforce`, `max_age: 604800` | senders refuse to deliver inbound mail |
| SPF | `include:_spf.google.com sendgrid.net amazonses.com -all`, 4/10 lookups | permerror if lookups exceed 10 |
| MX | `smtp.google.com` (Google Workspace, single MX) | must match MTA-STS `mx:` |
| TLS-RPT | `smtp-tls-reports@wecare.digital` | loss of TLS failure telemetry |
| DMARC rua | `dmarc-reports@wecare.digital` | loss of alignment telemetry |

Route 53 hosted zone: `Z03939753QJGZ6ZD6BXO8` (account `775261844268`).
MTA-STS policy lives in S3 bucket `wecare-digital-mta-sts` at
`.well-known/mta-sts.txt`, served via CloudFront `E1SZBXLQ4XNLJ7`.

**Certificates consolidated 2026-09-29.** That distribution used to carry a
dedicated single-name cert for `mta-sts.wecare.digital`
(`28d87ed5-42e0-478a-…`, since deleted). It now shares the one cert this account
has left:

| | |
|---|---|
| ARN | `arn:aws:acm:us-east-1:775261844268:certificate/f75d0db0-d476-443a-b787-96c4931862d2` |
| Names | `wecare.digital` **and** `*.wecare.digital` |
| Expires | 2027-03-12, `RenewalEligibility: ELIGIBLE`, Amazon-issued |
| Used by | Amplify domain `wecare.digital` (app `d22dm4b0jn71jw`) **and** CloudFront `E1SZBXLQ4XNLJ7` |

The wildcard SAN is what makes this safe: `mta-sts.wecare.digital` is a
single-label subdomain, so `*.wecare.digital` matches it. No IaC declares a
certificate — `amplify/link-resources.ts` dropped its `aws-certificatemanager`
import when `r.wecare.digital` was retired — so the ARN lives only on the live
resources and in this table.

Two consequences worth knowing before touching TLS here:

- **Renewal is now a single shared blast radius.** If that cert ever fails to
  renew, it takes the public site *and* the MTA-STS policy endpoint with it, and
  under `mode: enforce` the second failure means senders refuse inbound mail.
  Watch the one expiry rather than two.
- **A wildcard does not cover a second label.** `*.wecare.digital` matches
  `mta-sts.wecare.digital` but **not** `a.b.wecare.digital`. Adding a
  two-label host needs a new SAN, not a reuse of this cert.

## Rules

1. **Verify before and after any change to the above.** Run:
   ```
   powershell -File scripts/verify-email-auth.ps1
   ```
   Exit code 0 means safe. Non-zero means do not proceed.

   **This does not run on the current Mac.** Neither `pwsh` nor `powershell` is
   on `PATH`, so the one gate this file calls mandatory is unrunnable here, and
   pretending otherwise is worse than knowing. Until it is ported, the checks
   that actually matter have to be reproduced by hand — and a hand-rolled
   substitute is not equivalent, because it will not catch what nobody thought
   to re-type. The critical ones are: exactly one SPF, one DMARC, one
   `_mta-sts`, one TLS-RPT record; every live `MX` covered by a policy `mx:`
   line; and the policy fetching over HTTPS at **200** with `text/plain` and a
   **verifying** chain (`curl -w '%{ssl_verify_result}'` must be `0`, and
   `openssl s_client -verify_return_error` must report return code 0). A TLS
   change is not verified by a 200 alone — `curl` will happily report 200 on a
   chain it was never asked to validate strictly.

2. **Changing MX requires 7 days of lead time.** Senders cache the MTA-STS
   policy for `max_age` (604800s). Update the policy's `mx:` lines and bump the
   `_mta-sts` TXT `id` **at least 7 days before** the MX actually changes.
   Applies to leaving Google Workspace and to inserting a filtering gateway
   (Mimecast, Proofpoint, a WorkMail migration). Changing MX first and the
   policy afterwards bounces all inbound mail for up to a week, and no
   subsequent DNS edit can shorten that window.

3. **A new sending service must have DKIM live before its first send.** Under
   `p=reject` an unaligned message bounces rather than landing in spam. Publish
   the DKIM record, confirm it resolves, then enable sending.

4. **Never set `aspf=s`.** Wix/SendGrid sends with envelope-from
   `sg.wecare.digital` against header From `wecare.digital`. Only relaxed SPF
   alignment lets that pass. Strict alignment would break that path immediately.

5. **Exactly one SPF record and exactly one DMARC record.** Two SPF records is
   an RFC 7208 permerror. Two DMARC records makes RFC 7489 s6.6.3 treat the
   domain as having **no** DMARC policy at all, silently disabling enforcement.

6. **Any MTA-STS policy edit needs three steps, not one.** Update the S3 object,
   bump the `_mta-sts` TXT `id`, then invalidate
   `/.well-known/mta-sts.txt` on CloudFront. Skipping the id bump means senders
   keep honouring the cached policy.

7. **Adding an SPF `include:` needs a lookup budget check.** 4 of 10 are used.
   `_spf.ascendbywix.com` alone costs 8 and would push the record into
   permerror. Wix does not need an SPF include, because `sg.wecare.digital` is a
   CNAME into SendGrid and serves its own SPF.

## Known anomaly - Amazon SES DKIM

SES lists three Easy DKIM tokens as current, but AWS publishes a public key for
only one of them at `*.dkim.amazonses.com`:

```
v5w4wexbfyum54omlfe7l6ayada7j2nq  key published
cv4zuam4avmurrtes4etpikvkkbkxect  no key at AWS authoritative NS
mopqbzjxtouvnrv23lnfspfxxt2kiqpa  no key at AWS authoritative NS
```

All three CNAMEs are present and correct in Route 53; the gap is on the AWS
side. SES signs with one selector per message, so one published key is
sufficient and `Status: SUCCESS`. **Unverified:** which selector SES actually
uses. Confirm by reading `s=` in the `DKIM-Signature` of a real SES-sent
message. If it names a token with no published key, SES mail is hard-bouncing
under `p=reject` and DKIM must be rotated.

Do not rotate SES DKIM casually while `p=reject` is live - during propagation
mail can fail closed.

## Rollback

- **DMARC** - one Route 53 record, effective in ~5 min at the 300s TTL.
- **MTA-STS** - S3 write plus id bump plus invalidation, but senders honour the
  cached policy for up to `max_age`. Reducing `max_age` does not shorten an
  already-cached entry. This is the slow one; treat enforce changes as
  effectively one-way for a week.
- **Viewer certificate on `E1SZBXLQ4XNLJ7`** - there is **no rollback to the old
  cert**, because the owner deleted it from the console minutes after the swap
  released it, and ACM deletion is not reversible. Recovery means requesting a
  fresh cert for the name and re-validating, roughly 5 to 30 minutes on DNS
  validation while the record is already in the zone. Not a concern in practice:
  the wildcard covers the name and the shared cert is what both consumers
  already use. `cloudfront update-distribution` is a **full replace** — it needs
  the entire `DistributionConfig` plus a matching `ETag`, so any rollback must
  start from a fresh `get-distribution-config`, not from a stale snapshot.
  Pre-change config is committed at
  `docs/execution/snapshots/cloudfront-E1SZBXLQ4XNLJ7-before-certswap-20260929.json`
  (`ETag E23ZP02F085DFQ`).
