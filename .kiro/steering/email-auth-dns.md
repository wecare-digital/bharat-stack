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
`.well-known/mta-sts.txt`, served via CloudFront `E1SZBXLQ4XNLJ7` behind
ACM cert for `mta-sts.wecare.digital`.

## Rules

1. **Verify before and after any change to the above.** Run:
   ```
   powershell -File scripts/verify-email-auth.ps1
   ```
   Exit code 0 means safe. Non-zero means do not proceed.

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
