# Security Audit — Public Lambda Function URLs

Triggered while evaluating the Lambda alias work. Audited all 55 functions
(`scripts/_audit_function_urls.py`). **4 functions expose a public Function URL
(`AuthType=NONE`); 0 use IAM auth.** Each must authenticate callers in-code.

## Findings

| Function | Mechanism | Status | Action |
|---|---|---|---|
| `wecare-razorpay-webhook` | HMAC-SHA256, `compare_digest`, **fail-closed**, secret set (15) | ✅ Secure | none |
| `wecare-payu-webhook` | sha512 reverse-hash, salt set (32) | ⚠️ **Fixed** | was fail-**open** if salt unset → now fail-closed |
| `wecare-ai-generate-response` | **none** | 🔴 Open | see below |
| `wecare-voice-in-cdr` | **none** | 🟠 Open | see below |

## Fixed this pass
- **`payu-webhook` fail-open → fail-closed** (`_verify_payu_hash`): previously returned
  `True` (accept) when `PAYU_MERCHANT_SALT` was missing. Now returns `False`. Salt is
  currently set in prod so the branch wasn't reachable, but this is correct defense-in-depth
  matching the Razorpay handler. 10/10 payments tests pass. **Needs redeploy to take effect**
  (low urgency — inactive branch in prod).

## Open findings (require caller coordination — NOT safe to change blind)

### 🔴 `wecare-ai-generate-response` — Bedrock cost-abuse exposure
- Public URL, no caller auth. Anyone with the URL can invoke Amazon Nova Pro on the account.
- Input length is capped (2000) and tool-use is rate-limited per `sessionId`, but the caller
  supplies `sessionId`, so the limit is trivially bypassed.
- **Recommended:** put it behind API Gateway with a usage plan/API key, OR add a shared-secret
  header check, OR restrict the Function URL to `AWS_IAM` and have callers sign. Requires
  knowing the caller (frontend chat widget?) to avoid breakage. Add a per-source-IP or global
  request-rate alarm in the interim.

### 🟠 `wecare-voice-in-cdr` — forged-CDR / data-integrity exposure
- Public URL, no signature/token/source check. Anyone can POST fabricated call records.
- Source `handler.py` not locatable in the repo under this name → also a possible **IaC drift**
  data point (part of the "54 Lambdas outside IaC" gap).
- **Recommended:** verify the telecom provider's signature or restrict to their source IP range /
  a shared secret. Coordinate with the CDR provider before changing.

## Note
Also consider making PayU's hash compare constant-time (`hmac.compare_digest`) — minor
timing-hardening, low priority.
