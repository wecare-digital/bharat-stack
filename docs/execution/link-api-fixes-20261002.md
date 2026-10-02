# Live link/API fixes — 2026-10-02

## Outcome

The three actionable findings are fixed in production in AWS account 775261844268, us-east-1.

1. Removed HTTP API zllr9lrg7j route `GET /{code}` (previous route hf5g6q1), which incorrectly routed arbitrary one-segment API paths through the shortener. Retained `GET /r/{code}` (nnllqhh). The prod stage auto-deploys. Updated the IaC declaration to use `/r/{code}`, removed the obsolete public auth exemption, and changed the URL-matrix regression expectations to 404.
2. Changed the WhatsApp business API environment setting `WIX_SITE_URL` to `https://wecare.digital`, preserving every other environment variable. Scanned every Python file in the live version 60 package and found zero consumers of this environment key. Its prior Velo HTTP fallback has already been removed. Recorded the canonical source patch in amplify/infra/whatsapp-business-api-environment.json.
3. Removed the obsolete `https://admin.wecare.digital` Origin header from the direct order lookup invocation. The receiving Wix handler calls require_auth; its middleware recognizes an internal invocation by the absence of gateway apiId/domainName/sourceIp. IAM controls the direct Lambda invocation. A browser Origin is only CORS input and is unnecessary here. No authentication bypass or receiving-function change was added.

## Deployment evidence

`wecare-whatsapp-business-api:live` now selects version **61**, State Active, LastUpdateStatus Successful. Its WIX_SITE_URL is the canonical apex. The deployed ZIP was made from the existing version 60 package, replacing **only flows/orders.py**; all other entry bytes were checked unchanged. The updated flows/orders.py exactly matches the committed source.

- CodeSha256: `rmzfLkYxOeRepo02c39cn56fbi6WX1LZ/ZT6AOil0q8=`
- ZIP SHA-256: `ae6cdf2e463139e45ea68d36737f5c9f9e9f6e2e965f52d9fd94fa00e8a5d2af`
- Artifact: `s3://cdk-hnb659fds-assets-775261844268-us-east-1/link-api-fix-20261002/whatsapp-after.zip`
- API route inventory after fix: 364 routes; root GET catch-all absent; canonical short-link route retained.

## Live verification

| Request | Observed result |
|---|---|
| `/api/definitely-no-route` | 404, application/json, `{"message":"Not Found"}`, no redirect |
| `/api/definitely/no/route` | 404, application/json, `{"message":"Not Found"}`, no redirect |
| `/api/wa` | 404 JSON, confirming short codes do not leak into API root |
| `/r/wa` | 302 to the established WhatsApp entry destination; redirect was not followed |
| `/r/zz-no-such-code-probe` | 302 to `https://wecare.digital/contact/` |
| `/api/wix-store/orders` without auth | 401 JSON, no authorization token provided |
| `/account/sign-in/` | 200 HTML |
| `/checkout/status/` | 200 HTML |
| `/checkout/success/` | 200 HTML |
| `/shop/` | 200 HTML |
| `https://www.wecare.digital/shop/` | 301 to `https://wecare.digital/shop/` |

Focused regression suite: **92 passed**, including captured order-flow invocation and internal-versus-gateway authentication behavior. TypeScript typecheck and diff whitespace checks passed. Focused tests were repeated against the exact isolated checkout based on current origin/stack before pushing. No frontend bundle was changed.

## Rollback and scope

Before-state: docs/execution/snapshots/link-api-before-fix-20261002.json. Restore `live` to retained Lambda version 60 to restore its previous code and environment. Recreate `GET /{code}` with Target integrations/5sm0t1s and AuthorizationType NONE to undo the route retirement; prod auto-deploys. Revert the source commit normally if needed.

No DNS record, hostname association, certificate, email tracking/SIP setting, or public page was changed. Existing www redirects remain operational. `/checkout/` and `/sign-in/` remain unadvertised diagnostic paths; the real customer routes are listed above. These checks verify routing and authentication rejection. They do not establish OTP delivery, payment completion, receipt authorization, or completion of a customer's order flow. No customer message, OTP, payment, or provider mutation was performed.
