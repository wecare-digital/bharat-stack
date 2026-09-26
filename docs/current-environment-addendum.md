# Current environment — addendum from an independent read-only pass

Companion to [`current-environment.md`](current-environment.md) and
[`compatibility.md`](compatibility.md). Measured **2026-09-26** against account
`775261844268` / `us-east-1`, Google project `wecaredigitalbw`, and the live Wix site.

Three Phase 0 documents now exist because three Kiro sessions worked this brief against one
shared working tree. Per `.kiro/steering/multi-session-parallel-agents.md` a spec belongs to
one session — `whatsapp-wix-commerce` is owned by `sess_a140bc76` — so this file **adds
measured facts and does not restate, re-rule or overwrite** either of the other two. It was
written as a separate file rather than appended because `current-environment.md` was
rewritten mid-session by its author, and an append would have been silently lost.

The discovery pass itself changed nothing. One finding was then **fixed** — §2, the
unprotected customer Cognito pool — and that is marked below. No secret value was read at
any point; `get-secret-value` was never called, from any surface.

## Status of the findings in this document

| § | Finding | Status |
|---|---|---|
| 1 | Three `BLOCKED` Wix rows resolvable without a credential | ✅ **RESOLVED** — `scripts/probe_wix_capabilities.py` |
| 1 | Which Wix site the committed id names (gap G2) | ✅ **ANSWERED** — Wix reports the host as `xout.wecare.digital` |
| 1 | Wix's own published/draft *flag* for that site | ⏳ **PENDING** — admin scope only; downgrade G2 to `LOW` |
| 2 | Customer Cognito pool had no web ACL | ✅ **FIXED 2026-09-26** — associated and read back; 8 regression tests |
| 2 | OTP abuse control is per-IP only | ⏳ **PENDING** — spec gap G5, per-phone counter in the handler |
| 2 | HTTP API cannot take a WAF | ⚠️ **DESIGN DECISION REQUIRED** — service limit, not an omission |
| 3 | Blog build fail-open | ➖ **NOT REQUIRED** — already guarded; my `HIGH` rating was wrong |
| 4 | No `ap-south-1` EUM origination identity | ⏳ **PENDING** |
| 4 | `whatsapp-payments-india-reference.md` is 0 bytes | ⏳ **PENDING** — spec task 1.5, owned elsewhere |
| 4 | `scripts/fetch-wix-catalog.js` on the Catalog V1 reader, and unrunnable | ✅ **FIXED 2026-09-26** — ported to V3, credential removed, 20 tests |
| 4 | `scripts/check_secrets_live.py` on the Catalog V1 reader | ⏳ **PENDING** — owned by another session this run |
| 4 | No CSP on the public site | ⏳ **PENDING** |
| 4 | Google key spans browser + server; Places (New) not allowlisted | ⛔ **OWNER-ONLY** — credential work in GCP |

---

## 1. Three `BLOCKED` Wix rows are resolvable today, without the owner minting anything

`current-environment.md` §7 and `compatibility.md` §3 hold catalog version, installed apps
and Invoices availability as `BLOCKED` pending the admin credential. That is correct for
**admin** reads. It is not correct for **capability**, and the distinction matters because
it currently blocks design decisions that do not need to wait.

`WIX_CLIENT_ID` is the public half of the headless OAuth client. Wix exchanges it for an
anonymous **visitor** token with no secret involved — the same thing a page load does. That
is enough to settle all three rows. Reproducible:

```bash
python scripts/probe_wix_capabilities.py          # human-readable
python scripts/probe_wix_capabilities.py --json   # machine-readable
```

| Row | Previously | Measured | Evidence |
|---|---|---|---|
| **Catalog version** | `BLOCKED` | **`CATALOG_V3`** | `POST /stores/v1/products/query` → **HTTP 428**, `applicationError.code = CATALOG_V3_CALLING_CATALOG_V1_API`, message "your site is using CATALOG_V3". Wix states the version itself |
| **Wix Stores** | `BLOCKED` | **INSTALLED** | products, inventory, categories, customizations, brands all `200` on `/stores/v3/*` and `/categories/v1/*` |
| **Wix Blog** | "absent by grep" | **INSTALLED, 571 posts** | `/blog/v3/posts/query` → `metaData.total = 571`; `/blog/v3/categories` → `200` |
| **Wix eCommerce** | `BLOCKED` | **INSTALLED, admin scope required** | `/ecom/v1/carts/current` → `404 OWNED_CART_NOT_FOUND` (app present, no cart yet), `/ecom/v1/orders/search` → `403 READ_ORDER_FORBIDDEN` (app present, scope short) |
| **Wix Invoices** | `BLOCKED` | **NOT AVAILABLE** | `/invoices/v2/invoices` → **404**. Corroborates the existing decision to keep the homegrown 5-table invoice engine |
| **Checkout handoff** | "absent by grep" | **REACHABLE** | `/_api/redirects-api/v1/redirect-session` → `400` listing `ecomCheckout` as a valid session type. Probed with a deliberately invalid payload so nothing was created |

Catalog content is thin: **7 products, 1 category, 3 customizations, 0 brands.** A commerce
launch needs that populated; it is an owner/content task, not engineering.

### Gap G2 (unverified Wix site) is largely answered — Wix names the host itself

`current-environment.md` G2 rates the site id `HIGH` and unverified, on the grounds that
matching a Lambda env var to a committed constant only proves the repo is self-consistent,
not that the id names the published site rather than the draft. That reasoning is sound.
Three measured facts answer most of it:

- The visitor token minted from the committed `WIX_CLIENT_ID` returns **live catalog and
  blog data**, so the client points at a real, content-bearing site.
- Wix's own scope error names the site id: `PERMISSION_DENIED` on `/site-properties/v4`
  reads *"Unauthorized to perform site-settings.view on site
  `fcd82f0c-9572-49c7-acfb-88fb05042ece`"* — the committed `WIX_SITE_ID`. The public client
  and the committed site id belong to each other, measured rather than assumed.
- **Wix reports the site's host as `xout.wecare.digital`.** Every product carries
  `url.url`, which Wix builds from the site's own primary domain. All seven read
  `https://xout.wecare.digital/product-page/<slug>`. The probe now reports this as
  `wixReportedSiteHost`.

That last point is the one that matters. G2's evidence for doubt was that the brief names
the published site's URL as `https://xout.wecare.digital/` and that URL returns **404**.
Wix now independently states that the site behind the committed id *is* the one at
`xout.wecare.digital` — and the other document already measured that DNS for that host
delegates to Wix (`pointing.wixdns.net`). Two sides agree on the identification.

**The 404 is consistent with the architecture, not evidence against the id.** The Wix
Editor site is retired and this repo owns every page; a headless site serves its data over
`wixapis.com` and need not serve HTML at its own domain. A 404 at the Wix-hosted front door
is the expected state, not a mismatch.

What remains open is narrower still: Wix's *own* published/draft flag for this site, which
only `POST /site-list/v2/sites/query` or `/site-properties/v4` returns, both admin-scoped.
Recommend G2 be restated `LOW` / `WIX_PUBLISHED_FLAG_REQUIRES_ADMIN_SCOPE` — the site is
identified; only its status field is unread.

### One correction to offer

`current-environment.md` §7 lists "`WIX_CLIENT_ID` is committed and unused". Committed and
unused **by application code** — accurate. But it is a live, working credential, not dead
configuration, and a visitor session is the documented path for public catalog reads in a
static export. Worth knowing before the design reaches for admin scope where visitor scope
would do.

---

## 2. WAF: the customer-facing pool was the one without protection — now fixed

`current-environment.md` G8 records "no WebACL on `zllr9lrg7j`". Both halves of that need a
correction, and the corrected version is a more serious finding.

| Resource | WebACL before | WebACL now | Measured via |
|---|---|---|---|
| Amplify app `d22dm4b0jn71jw` | `wecare-amplify-waf` | unchanged | `amplify get-app` (`wafStatus: ASSOCIATION_SUCCESS`) |
| Cognito **staff** pool `us-east-1_cSx0RHCIR` | `wecare-cognito-waf` | unchanged | `wafv2 get-web-acl-for-resource` |
| Cognito **customer** pool `us-east-1_46ULYuukt` | **none** | **`wecare-cognito-waf`** | same call, both before and after |
| HTTP API `zllr9lrg7j` | cannot have one | cannot have one | service limit, see below |

**The unprotected pool was the internet-facing one.** `WECARE.DIGITAL-CUSTOMERS` is the
pool this brief puts behind public WhatsApp/email OTP registration; the staff pool is not
internet-facing in the same way, and only the staff pool had an ACL. `scripts/provision_waf.py`
covered one pool, so the gap was invisible to the tool meant to catch it.

**Resolved 2026-09-26.** `scripts/provision_waf.py` now takes a list of resources per ACL
instead of a single one, reports and verifies association **per resource** so a partial
association can no longer read as protected, and associates the customer pool with the
existing regional ACL. Read-back confirms both pools return `wecare-cognito-waf`, and the
Amplify enforcement probe still passes (`GET /` → 200, Log4Shell probe in the query → 403),
so nothing regressed.

One regional ACL protects both pools rather than a second ACL: the rule posture both pools
want is identical, and it avoids another ~$8/month. The cost is coupling — the rate-based
rule aggregates per IP across both pools. Split it when OTP economics demand a tighter,
blocking limit on the customer pool alone.

**This does not close the OTP abuse problem, and should not be read as doing so.** Indian
carriers CGNAT heavily, so a per-IP limit tight enough to stop OTP abuse would refuse real
customers. The rate rule stops a crude single-host flood. The actual control is per-phone
and per-identity in the handler with a persisted send counter — that is spec gap G5, still
open, and still `HIGH`.

**`zllr9lrg7j` cannot be WAF-protected at all.** WAF's protected resource types are
CloudFront, API Gateway **REST**, ALB, AppSync, Cognito user pools, App Runner, Amplify and
Verified Access. `zllr9lrg7j` is apigatewayv2. So the owner's "WAF implemented and
live-verified" target cannot be met for the API by attaching an ACL; it needs a decision —
front the API with CloudFront and attach the CLOUDFRONT-scope ACL, migrate to REST, or
record handler-level controls as the accepted strategy. `scripts/provision_waf.py` already
documents this constraint; `current-environment.md` G8 states it as a gap without noting it
is a service limit rather than an omission.

**A verification trap, recorded because I hit it.** `wafv2 list-resources-for-web-acl`
returns an **empty list** for `wecare-cognito-waf` even with both pools associated — that
call does not enumerate Cognito user pools, Amplify apps or CloudFront. Reading the empty
list as "protects nothing" would be wrong. `get_web_acl_for_resource` per ARN is the
authoritative check.

---

## 3. The blog fail-open is real but already guarded — withdrawing my own finding

I first recorded this as a `HIGH` unmitigated gap. That was wrong, and the correction is
worth more than the original claim.

The fail-open exists exactly as described: `src/lib/public-blog.ts` wraps its `fetch` in
`try { … } catch { return [] }` and also returns `[]` on any non-`ok` response, and
`src/pages/post/[slug].tsx` feeds that into `getStaticPaths` with **`fallback: false`** under
`output: 'export'`. A network blip during a build really does produce zero post pages.

**But the outcome is asserted downstream, and it fails the deploy.**
`scripts/generate-sitemap.js` refuses to write a sitemap when 0 post pages were exported and
exits 1. `package.json` defines `build` as `next build && node scripts/generate-sitemap.js`,
and `amplify.yml` runs `npm run build` — so the guard runs inside the Amplify build and a
non-zero exit fails it. Nothing ships.

The guard also documents the incident that motivated it, on 2026-09-24: one build emitted
125 URLs with 109 post pages, the next emitted 16 with none, from an unchanged tree. And it
explains why it asserts on the **outcome** rather than making `listPublicBlogPosts()` throw:
that function is also safe to call from a browser, where returning `[]` for an unreachable
API beats a crashed page. The build wants the opposite. Asserting on the outcome keeps both.
That is the right call and I am not changing it.

The `ALLOW_EMPTY_BLOG=1` escape hatch has to be typed deliberately.

Measured healthy right now: the endpoint returns `ok: true` with **571 posts**, 0 duplicate
slugs, 0 empty slugs; the live `sitemap.xml` carries **587 URLs = 571 posts + 16 pages**.

Residual risk, stated precisely and **not** inflated: the guard's floor is 1, not a
percentage, on the documented reasoning that the failure mode is all-or-nothing. That
reasoning holds — `listPublicBlogPosts()` performs a single unpaginated fetch of the whole
list, so a truncated-but-non-empty result is not a shape the code can produce. Severity
`LOW`, no action recommended.

### A trap for anyone auditing this repo

The local `out/` directory is a **stale developer artifact** — 520 post pages, built before
the newest 51 posts were published on 2026-09-25. It is not what is deployed. I initially
read `out/` and concluded 51 posts were 404ing in production; fetching the live URLs showed
HTTP 200 with fully rendered content, and the live sitemap carries all 571. **Audit the live
site, not `out/`.**

---

## 4. Smaller measured items not in the other two documents

| Item | Severity | Measured |
|---|---|---|
| **No `ap-south-1` EUM origination identity** | `MEDIUM` | `describe-phone-numbers` in `ap-south-1` returns **empty**; `us-east-1` has `+18444891209` (TOLL_FREE) and `+14255556333` (SIMULATOR). India SMS depends on DLT plus sender registration — verify before relying on India SMS as an OTP fallback |
| **`.kiro/steering/whatsapp-payments-india-reference.md` is 0 bytes** | `LOW` | Injected into every session as an empty rule. Either write it or delete it; an empty steering file is worse than none because it reads as coverage |
| `scripts/check_secrets_live.py:188` uses the Catalog V1 compatibility reader | `MEDIUM` | Calls `stores-reader/v1/products/query`, which still returns `200` on a V3 site, so it fails silently rather than loudly. Left alone this run: another session was editing that file. `scripts/fetch-wix-catalog.js` had the same defect and is now fixed — see §5 |
| No CSP on the public site | `MEDIUM` | `wecare.digital` returns HSTS, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` — and no `Content-Security-Policy` |
| 6 retired-provider CloudFormation stacks | `LOW` | `wecare-elevenlabs-{init,mcp,mcp-enable,call-hooks,postcall-sms}` and `wecare-temp-code-inspector`, all 2026-09-19. Retirement candidates; deletion needs pointwise confirmation |
| 8 stale `chatgpt/*` Amplify branches | `LOW` | Auto-build disabled on all 8; `stack` is the only PRODUCTION branch |
| No CodePipeline or CodeBuild | `INFORMATIONAL` | Both empty. CI/CD is GitHub Actions plus Amplify — so "existing deployment pipelines" means those two, not CodePipeline |
| EventBridge is the only scheduler | `INFORMATIONAL` | 6 rules on `default`; EventBridge Scheduler has 0 schedules |

---

## 5. `scripts/fetch-wix-catalog.js`: ported to Catalog V3, and the credential removed

The script that produces the committed catalog snapshot was on the V1 compatibility reader
**and could not run at all.** It required `WIX_API_KEY` — an account-scoped admin bearer
token — and `wecare/wix/headless-api-key` holds 0 versions. Its own header carried the
deferral: *"mapping those fields without inspecting a real v3 response would be guesswork.
Inspect one v3 payload first, then port slim()."*

A real V3 payload for all seven products was inspected via the visitor token, and the port
is mapped against it rather than against documentation.

**The credential is gone, not relocated.** The header's outstanding TODO said the key
"must come from AWS Secrets Manager". The better answer is that reading seven public
product names and prices needs no admin credential: the public `WIX_CLIENT_ID` mints a
visitor token, which is the scope a storefront page has. Least privilege, and it runs today
with nothing to provision.

**Verified against the previous snapshot, old versus new:**

| Check | Result |
|---|---|
| Products | 7 → 7, same slugs |
| Prices | identical on all 7, numerically **and** as formatted strings (`₹599.00` …) |
| `descriptionHtml` | byte-length identical on all 7 |
| `name`, `visible`, `inStock`, `optionCount`, `mediaCount` | unchanged |
| **`variantCount`** | **was `0` for all 7 — now 1,1,1,10,1,1,1** |
| Secret-shape scan of the output | 0 matches |

**`variantCount` was silently wrong.** The V1 reader did not return the variants array, so
every product recorded zero variants. `merchandise` has ten. A snapshot reporting zero
variants for a ten-variant product is worse than one omitting the field, and nothing in the
old code could have noticed.

Schema changes are not a drop-in and are documented in the script header. The two worth
repeating: `price` is now a **decimal string** because V3 returns money as a string on
purpose and coercing it to a float is a decision nobody made; and `discountedPrice` is
**gone** rather than remapped, because V3's `compareAtPriceRange` is the opposite idea — the
higher struck-through "was" price — so carrying the name forward would invert the meaning at
some future call site.

`tests/test_wix_catalog_snapshot.py` — 20 tests, offline — locks the schema, the V3
endpoint, cursor paging, the field projections V3 omits by default, and the absence of any
credential or tenant identifier in the committed output. Verified RED on a simulated revert
to V1-plus-admin-key, GREEN restored. One of those tests guards the others: the
comment-stripping fixture is itself asserted to leave real code behind, because a substring
is trivially absent from an empty string.

---

## 6. Reproducing everything in this document

```bash
python scripts/probe_wix_capabilities.py      # Wix capability + site host, no credential
python scripts/provision_waf.py --verify      # WAF association, per resource
node   scripts/fetch-wix-catalog.js           # catalog snapshot, no credential
python -m pytest tests/test_waf_coverage.py tests/test_wix_catalog_snapshot.py
python scripts/generate_runtime_inventory.py  # Lambda, routes, tables, traffic
python scripts/session_map.py                 # who else is writing to this tree
aws sts get-caller-identity                   # must report 775261844268
```

Note the blog post count moves: 571 at the first probe, 575 an hour later. The endpoint is
live and content is being added, so treat every count here as a timestamp rather than a
constant — which is what `.kiro/steering/00-current-owner-overrides.md` requires anyway.

The WAF associations, SES state, EUM phone numbers and CloudFormation stacks were read with
plain `boto3` `List*`/`Get*`/`Describe*` calls under profile `wecare-prod`. The Google key
restrictions came from `gcloud services api-keys list`, which returns the restriction set
without returning the key string.
