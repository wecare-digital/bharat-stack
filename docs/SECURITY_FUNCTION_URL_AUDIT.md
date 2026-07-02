# Security Audit — Public Lambda Function URLs

Triggered while evaluating the Lambda alias work. Audited all 55 functions
(`scripts/_audit_function_urls.py`). **4 functions expose a public Function URL
(`AuthType=NONE`); 0 use IAM auth.** Each must authenticate callers in-code.

## Findings

| Function | Mechanism | Status | Action |
|---|---|---|---|
| `wecare-razorpay-webhook` | HMAC-SHA256, `compare_digest`, **fail-closed**, secret set (15) | ✅ Secure | none |
| `wecare-payu-webhook` | sha512 reverse-hash, salt set (32) | ⚠️ **Fixed** | was fail-**open** if salt unset → now fail-closed |
| `wecare-ai-generate-response` | ~~none~~ → **AWS_IAM** | ✅ **Resolved** | URL locked to IAM; anonymous blocked |
| `wecare-voice-in-cdr` | **none** | 🟠 Open | see below |

## Usage evidence (CloudWatch `UrlRequestCount`, 30 days)
All 4 Function URLs show **0 requests in 30 days** (`scripts/_check_url_usage.py`). Combined
with the payment webhooks having API Gateway routes and the AI function's callers using boto3
`invoke()`, the public URLs are unused leftovers — the real entry points are API Gateway / internal invoke.

## Resolved this pass
- **`payu-webhook` fail-open → fail-closed** (`_verify_payu_hash`): now returns `False` when
  `PAYU_MERCHANT_SALT` is missing. 10/10 payments tests pass.
- **`ai-generate-response` URL locked to `AWS_IAM`** (`scripts/_lockdown_ai_url.py`). Was public
  `NONE` → Bedrock cost-abuse exposure. Confirmed safe: 0 URL requests in 30d, and its only
  callers (IVR engine `ivr_engine.py`, `inbound-whatsapp-handler`) invoke it via boto3
  `lambda.invoke()` (action `lambda:InvokeFunction`), which is unaffected by URL auth. Reversible.

## Open findings (require caller/dashboard verification — NOT changed blind)

### 🟠 payment webhook URLs (`razorpay-webhook`, `payu-webhook`) — redundant leftovers
- Both invoked via **API Gateway** (`zllr9lrg7j`) in practice; their Function URLs show 0 requests
  in 30d → almost certainly redundant. **Do NOT remove blind** — first confirm the Razorpay/PayU
  dashboards POST to the API Gateway route (not the Function URL). Then delete the URLs.

### 🟠 `wecare-voice-in-cdr` — unknown external caller
- Public URL, no signature/token/source check. Anyone can POST fabricated call records.
- Source `handler.py` not locatable in the repo under this name → also a possible **IaC drift**
  data point (part of the "54 Lambdas outside IaC" gap).
- **Recommended:** verify the telecom provider's signature or restrict to their source IP range /
  a shared secret. Coordinate with the CDR provider before changing.

## Note
Also consider making PayU's hash compare constant-time (`hmac.compare_digest`) — minor
timing-hardening, low priority.
