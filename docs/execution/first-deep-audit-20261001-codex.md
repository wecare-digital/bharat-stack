# First deep checkout audit — 2026-10-01 IST

Dated evidence only. The supplied owner decision selects standalone Wix Headless + existing AWS + WhatsApp/Razorpay. The previous collision audit's dual-mode recommendation is superseded; its original observations remain historical evidence. Normative requirements/design/tasks remain owned by `.kiro/specs/whatsapp-wix-commerce/`.

## Result

**NOT READY for live checkout. C1–C7 remain OPEN.** The audit records 24 findings: 19 P1 and 5 P2. No implementation cleanup, deployment, payment, refund, customer send, credential-value read, or live-send flag change was performed. One nonpayable existing demo-cart calculation ran with `refreshCart:false`; it creates no order/payment and may emit a cart-calculated event.

Full report and machine-readable evidence are retained in the requesting Codex chat's outputs directory:

`/Users/wecaredigital/Documents/Codex/2026-10-01/wix-plugin-wix-openai-curated-remote/outputs/`

- `WECARE-DEEP-AUDIT-2026-10-01.md`
- `DEEP-AUDIT-EVIDENCE.json`
- `OFFLINE-REPRODUCTIONS.json`
- `CLEANUP-MANIFEST.json`
- `CLEANUP-DEPENDENCY-INVENTORY.txt`
- `AUDIT-TEST-RESULTS.xml`

## Provenance and fresh inventory

- Initial local `stack`: `c082d5867240b819c6c26af4ab668575440868f9`. Final local HEAD advanced concurrently to `6a5d6e9ea6fe0097bf246a34ab6138c6919935d7`; this audit did not merge or change application source.
- GitHub `stack`: `6a5d6e9ea6fe0097bf246a34ab6138c6919935d7`; only `tests/conftest.py` changed between them. Commerce source is identical. No merge/reset performed.
- AWS Core connector requires reauthentication. Authorized existing `wecare-prod` CLI/boto3 access confirmed account `775261844268`, region `us-east-1`.
- Focused AWS inventory completed `2026-09-30T22:41:52Z` (2026-10-01 04:11 IST): 66 functions; 359 routes; no checkout, registration or email-verification Lambda. No checkout/customer/cart routes found in the relevant route inventory.
- Live versions: Wix-store 31; Razorpay-webhook 45; WhatsApp-business-api 57; customer-whatsapp-auth 10; outbound-whatsapp 43; inbound-whatsapp 66; invoice-engine 39; payments-read 24.
- Consistent count scans: PaymentAttemptsTable, PaymentsTable, OrderTable, WixOrderIds and InvoicesTable each zero. No historical-provider/data-migration waiver follows.
- Site `fcd82f0c-9572-49c7-acfb-88fb05042ece` confirmed by Wix connector: WECARE.DIGITAL, published, Editorless, Velo enabled, INR, Asia/Kolkata, Catalog V3. Existing site confirmation R0.10 retained.
- Wix default/PENDING/REJECTED searches returned zero, no next page. INITIALIZED coverage remains UNKNOWN; official Search Orders never returns that state.
- Existing demo Cart V2 GET/calculation resolves, revision 4, INR 24999.00, with missing delivery address/method errors. Not a payable quote or write/inventory proof.
- Fresh deployed payment diagnostic reports zero active configs; WECAREDIGITAL/WECAREUPI are local_only. Raw successful Meta response omitted: direct account/provider binding remains unverified.
- Customer pool remains admin-only with CUSTOM_AUTH triggers and deletion protection. Schema lacks `custom:customer_id`; no customer-named table found; OTP pepper secret metadata returns ResourceNotFoundException.
- Live OTP-role policy simulation allows UpdateItem but denies PutItem used on send-counter rollover.
- Wix/Razorpay AWSCURRENT secret metadata present; no credential values read. SES domain sending verified, DKIM SUCCESS; no mail sent.

## Reproductions and additional findings

Offline local and downloaded live-v45 callbacks continued invoice/attribution paths after a NOT_PAID reconciliation outcome. Local and live-v57 sender dispatchers returned 404 for checkout's interactive-payment path. Fresh inert live GET invocation for checkout's `/payment-config/raw` returned 400 `phoneId required`.

Offline reproductions also show: repeated same-intent request creates two attempts; initiation disabled still creates attempts; paid status drops a stored order number; `_mark_request_sent` omits required `:rank`; same-phone registration creates two customer IDs; unauthenticated verified-email fixture stamps a body-selected customer. All external effects were spies/fixtures; the email reproduction tests downstream ownership with OTP verification stubbed successful, not an OTP bypass.

Remaining source gaps include trusted provider binding/reference-index consistency, profile prerequisites, client-ID pin, service-window/template readiness, full paid-order materialization, staged Wix writeback, receipt/notification orchestration, owned success/history/tracking, mirror-loop protection, recovery, package/config/IAM contracts and privacy-safe callback logs. Full finding IDs and pinned code links are in the report.

## Validation and cleanup scope

Focused offline Python 3.12 suite: **652 passed**, 0 failures/errors/skips, 20 modules. `npm run typecheck` passed. Existing mocks bypass important integration boundaries and one disabled-initiation test asserts behavior superseded by the owner requirement; passes are not full-flow evidence.

Cleanup inventory covers 18 tracked prototype files and 55 matching dependency/reference lines. No files were removed. Proposed prototype retirement still requires dependency/reuse checks and confirmation of unique uncommitted ownership. Own-site Wix native extension deployment remains UNKNOWN; Velo enabled or installed-app lists do not prove it absent. Preserve original audit evidence, provider resources, legitimate invoice/manual/sync writers and unrelated concurrent changes.

Direct Razorpay account/transaction verification, current template approval, production Wix write/cart-completion/inventory contract, browser/accessibility flows, receipt privacy/delivery and complete crash-boundary recovery remain NOT VERIFIED. GitHub connector status/workflow results were empty; no CI pass inferred. No live payment was attempted.

Audit rollback: remove this new dated record and requesting chat outputs if no longer wanted. Production was not changed. Any later implementation rollback must preserve verified paid evidence/reconciliation and disable new initiation first.

Final concurrency check also found unrelated `.agents/`, secret-handling steering, account-inventory and checkout-consolidation evidence changes. They were preserved. The live-v45 verifier lacks the stored-binding parameter required by current source; that protection is not deployed. Concurrent secret-exposure documentation was not independently reproduced; no credential-value scanner was run.
