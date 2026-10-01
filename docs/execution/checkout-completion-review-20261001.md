# Checkout completion review - 2026-10-01

This is a new measurement of the latest checkout, not an end-to-end completion claim.
The owner selected website Razorpay Standard Checkout and downloadable receipts;
WhatsApp is retained for verification. The current checkout handler still implements
the legacy in-chat initiator. The website preparation, callback verification,
pricing and receipt modules are tested source but are not yet a connected browser
purchase journey. Payment initiation remains disabled.

## Corrected in this change

- Remembered customer sessions now have an additive CloudFormation-owned backend:
  `wecare-customer-sessions`, `wecare-customer-session:live`, and
  `POST /ecommerce/customer-session`. An opaque Secure/HttpOnly/SameSite cookie
  identifies a server record; refresh tokens remain KMS-encrypted in DynamoDB.
  The browser keeps short access tokens in sessionStorage and a non-credential
  CSRF/expiry hint in localStorage. Persistent sessions have 30-day absolute and
  7-day idle expiry; shared-device sessions use a session cookie. Transient
  refresh failures retain the session instead of asking for a new OTP.
- Cart data survives payment requests and ambiguous network/server failures.
  Only verified payment finalization may clear it. Error text does not claim
  that no charge occurred when the browser cannot know.
- Catalogue lines use Wix's structured catalogue reference and real variant IDs.
  Merchandise requires an explicit fit/size selection. The backend re-reads
  the live product/variant and rejects missing, forged or unavailable choices.
- FAQ/shop/order references and AI service URLs use current canonical paths.
  Customer-facing shop copy no longer displays internal release commentary.
- A focused read-only release check validates rendered header/footer/main/title,
  Shopping Bag destination, default widget, current pages and public navigation.
  The URL/host matrix enforces the wildcard fallback and existing nested Wix
  redirect chain, preserving all current public pages and existing certificates.

## Deployment and rollback

The new session stack reached CREATE_COMPLETE; the table is ACTIVE with KMS,
PITR and TTL. The current live alias points to version 3 (initial provision was version 1). An unauthenticated live
refresh request returned 401 VERIFICATION_REQUIRED with no-store headers and
cleared the cookie. No OTP was sent, no payment was attempted, and no customer
order was created. Before-state metadata and exact versions are recorded in
`snapshots/checkout-completion-before-20261001.json`.

Rollback source with a normal revert. Restore individual pre-change live aliases
from the snapshot. Remove the additive session API route before retiring the
Lambda if rolling back infrastructure; retain the encrypted session table/key
per the CloudFormation deletion policy. Do not delete customer data or issue a
certificate as part of rollback.

## Release blockers

1. Connect the website quote -> Standard Checkout -> signed callback -> captured
   readback -> one order -> owned downloadable receipt handlers and UI. A valid
   signature alone must not imply payment. Duplicate/delayed confirmations must
   converge on one order and one receipt. `/orders/` is currently a contact
   signpost, not an authenticated purchase history. The success page now reads
   the owned payment attempt and requires PAYMENT_PAID plus a server-returned
   order number; URL query values cannot prove payment. The paid-order producer,
   receipt delivery and purchase-history consumer still need connecting before
   the acceptance journey can pass.
2. Confirm accountant-approved HSN/SAC and inclusive/exclusive catalogue pricing.
   Wix manual tax mappings returned an empty list. The catalogue includes apparel
   at INR 1,199, so applying 18% blindly to every product would be unsafe. The
   existing integer-paise calculator applies a 2.5% convenience fee and 18% GST
   on that fee to an already approved collection amount; it does not establish
   supply GST. Seller GSTIN is 19AAFFW7196L1Z8.
3. Owner-controlled QA phone and Razorpay Test Mode are required for live OTP and
   payment acceptance evidence. No inferred business number will be used and
   no live capture/refund or initiation flag will be enabled by this review.
4. After front-end publication, repeat real browser selection/cart/sign-in and
   visual checks. HTTP 200 and static chrome checks alone are not purchase proof.

Official tax reference: https://www.pib.gov.in/FactsheetDetails.aspx?Id=150293&lang=1&reg=6
Official Wix variant contract: https://dev.wix.com/docs/api-reference/business-solutions/stores/catalog-v3/products-v3/get-product

## Verified publication gates

Merged the newer origin/stack return-path fix and deployment evidence without
changing its allowlist. Full merged-tree tests: 5,809 Python tests passed, one
skipped; 692 frontend tests passed in 49 files. Typecheck and production build
passed. The exported 28-page customer navigation/chrome gate passed.

Updated only the reviewed Lambda packages after capturing rollback aliases:
customer-session 1 -> 2; faq-handler 21 -> 22; ai-config-management 23 -> 24;
ai-generate-response 33 -> 34; checkout 1 -> 2. Exact checksums and aliases are
in snapshots/checkout-completion-after-20261001.json. The checkout initiation
flag was not enabled. Existing customer/staff Cognito configuration, provider
credentials, payment configuration and certificates were preserved.

The focused customer export gate is now a required post-build step in both
GitHub build-test and Amplify production publication. Live HTTP matrix: 90
rows, zero mismatches; live customer chrome/navigation: 28 pages, zero failures.
These counts include the documented uncovered nested-host TLS state; they do
not claim that an existing one-label wildcard covers arbitrary nested names.

Session follow-up: CloudFormation update completed, owns the current code key
and published live version 3. Client-description outages return 503/no-store
without clearing a valid session; a revoked exchange token returns 401. Lambda
versions retain their rollback artifacts during CloudFormation replacement.
Focused follow-up checks: 108 backend session/security tests, 86 customer UI
tests and typecheck passed; production build and 28-page export gate passed.

Browser acceptance completed through the sign-in boundary: select merchandise
fit/size, add one, observe Shopping Bag count 1, open cart and proceed to the
required-country-selector WhatsApp sign-in form without sending a code.
The cart now names the selected option and omits internal release commentary.
No payment journey beyond that boundary is claimed.

Final merged-tree checks: 5,811 Python tests passed (one skipped), 697 frontend
tests passed in 50 files, typecheck and production build passed. The customer
export gate passed all 28 pages. New confirmation tests reject URL-only order
numbers, pending payments, absent order numbers and unauthorized attempts; only
a paid owned attempt may show success. The status handoff carries the attempt
id so the success page can perform that ownership check.

At desktop 1440px and mobile 390px, all six customer routes have no horizontal
overflow, headings below their fixed header and a footer/Shopping Bag. The
existing default widget remains present. This measures layout; it does not
replace the blocked OTP/payment acceptance run.
