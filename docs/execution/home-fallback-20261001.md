# Owner-approved home fallback and access cleanup

The owner explicitly requested unused WECARE subdomains and unknown website links
to land at https://wecare.digital/, and removal of direct /access workspace links.
This instruction supersedes the earlier blanket removal of custom redirects:
canonical www and retired access-to-home redirects are now approved exceptions.

## Implementation

- `amplify/infra/home-fallback.json` provisions a dedicated CloudFront distribution,
  viewer-request redirect function, DNS-validated ACM certificate and encrypted
  private access-log bucket with 30-day retention. It does not modify the existing
  Amplify distribution or the MTA-STS certificate/distribution.
- The function always returns a 302 to the exact https://wecare.digital/ URL. It
  drops the incoming path and query string and sets no-store.
- `scripts/home_fallback_dns.py` declares a guarded cutover for *.wecare.digital,
  xout.wecare.digital and www.xout.wecare.digital, using IPv4/IPv6 aliases. Explicit
  www, email, verification and SIP records remain untouched.
- `scripts/provision_legacy_redirects.py` retains canonical www and three access
  redirects while removing all other legacy custom redirects. Runtime rewrites
  and the unknown-page fallback remain unchanged.
- Public Header/Footer contain no workspace access href. Staff access stays at
  /workspace/access/; hiding public links is not a substitute for authentication.
- The existing 404 document navigates unknown apex website paths home. HTTP status
  remains 404 until JavaScript navigates, with a home link if JavaScript is disabled.

## Authority

| Class | Target | Authorization and rollback |
|---|---|---|
| A0_READ | DNS, Amplify, CloudFront, ACM metadata and live probes | Standing read authorization |
| A1_LOCAL | New IaC, DNS helper, routing provisioner, tests and access comments | Owner request and standing source authorization |
| A3_PRODUCTION | wecare-home-fallback CloudFormation stack, specified three DNS names and access home redirects | Explicit owner instruction; pre-change rules/DNS in snapshots/home-fallback-routing-before-20261001.json |

## Verification

- 16 Python routing/DNS/snapshot tests passed.
- 34 public-workspace-link, not-found and safe-return-path tests passed.
- Typecheck and production static export passed; current public page files retained.
- 12 edge-function execution cases passed: exact home destination and no path/query forwarding.
- Live /access, /access/ and /access/security/ return 302 to home.
- Live /workspace/access/, home, cart and orders return 200.

## Scope limits and rollback

TLS wildcard coverage is one hostname label: *.wecare.digital. The separately
covered existing www.xout.wecare.digital host is also included. Arbitrarily deep
invented names such as a.b.wecare.digital require additional certificate coverage;
they cannot be promised under this wildcard.

The DNS fallback applies to unused address names; explicit DNS nodes for email,
verification and calling services deliberately take precedence. Domains outside
wecare.digital cannot be redirected by this hosted zone. Functional API/MCP,
payment and authentication flow endpoints remain operational.

Rollback DNS with an atomic batch restoring the saved xout/www.xout CNAMEs and
removing only the new wildcard/xout address records. Restore Amplify rules from
the saved snapshot if reversing the access change. Remove DNS associations before
disabling/removing the new distribution; retain logs for their retention period.

Deployment IDs and final probe results are appended after CloudFront readiness
and DNS cutover; infrastructure creation alone is not a verified live redirect.

## Completed deployment

- CloudFormation `wecare-home-fallback`: CREATE_COMPLETE.
- CloudFront `E1ZZ786I3YH65O`, `d27evp2npt2kzr.cloudfront.net`: Deployed.
- Route 53 change `C1002370145M1YU1Y7I7Y`: INSYNC.
- ACM certificate `4953c75b-9cdb-406e-a01d-766bf1dc61bd`: ISSUED, both domain validations SUCCESS.
- Post-change rules and all 35 DNS record sets saved in
  `snapshots/home-fallback-routing-after-20261001.json`.
- Fresh unknown hostname, store and www.xout returned 302 to the exact home URL.
- shop and xout returned the same 302 with normal certificate validation when
  connecting directly to the deployed distribution; the local resolver temporarily
  retained old negative/Wix records from the earlier audit.
- Public home/shop/cart/orders remained 200; the email policy remained 200.
- Live HTML on home/shop/cart/orders/contact contained no workspace/access anchor.

All 28 original DNS record sets outside the two retired Wix CNAMEs were preserved
exactly. Six address aliases and one new certificate-validation record account
for the total changing from 30 to 35 record sets.


## Exact integration-tree checks

The isolated review checkout integrates the already committed public-link cleanup with the latest remote checkout work. Its 16 Python routing tests, 31 public-link/not-found/safe-return tests, typecheck and full static export passed. All 36 live public page URLs returned 200 after DNS cutover. The existing resolver negative cache for shop remains temporary; a fresh unknown name and xout/www.xout pass normal live HTTP probes. shop passes HTTPS with normal certificate validation when connected to the deployed endpoint.
