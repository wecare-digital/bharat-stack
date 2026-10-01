# URL, workspace-link and home-fallback cleanup — implementation plan

Written 2026-10-01 after a live investigation of the repo and of AWS account 775261844268
(`wecare-prod`, `us-east-1`). Every claim below is measured; where it is not, it says
`needs-verification-during-implementation`.

---

## 0. Findings that change the plan (read before implementing)

### 0.1 `_routes.json` has NO consumer. It is not a router.

`/Users/wecaredigital/wecare-store/_routes.json` is a 361-entry JSON array of API Gateway
route keys (`"POST /razorpay-webhook"`, `"GET /{code}"`, …). Grepped across the whole tree:
the only references are **prose in four markdown/source comments**. Every script that needs
routes calls `apigatewayv2 get_routes` live (`audit_route_auth.py`, `aws_account_inventory.py`,
`deploy_mcp_server.py`, …). `change-authority-matrix.md` entry 193 records it being
hand-regenerated from the live API.

So it is a **committed inventory snapshot**, not a hosting/CDN router. Cloudflare's
`_routes.json` convention does not apply here — nothing reads it at build or request time.

**Consequence: editing `_routes.json` cannot change any HTTP behaviour.** It is also a bare
JSON array, so it cannot carry an explanatory comment. The plan therefore leaves it
**byte-identical** and records the finding in the matrix document. Do not invent a routing
role for it.

### 0.2 The only host/path layer available is the Amplify app's `customRules`

- Production is `output: 'export'` (`next.config.js`), so **no Next server, no middleware,
  and `next.config.js` `redirects`/`headers` are inert in production**.
- Amplify app `d22dm4b0jn71jw`, branch `stack`, serves domain `wecare.digital` via
  Amplify-managed CloudFront `d2av2go6w170k.cloudfront.net`. **146 custom rules live**
  (measured 2026-10-01).
- `scripts/provision_legacy_redirects.py` is the config-as-code owner of those rules. It
  rebuilds the array as `domain + desired_redirects() + middle + catch_all` and refuses to
  run if the `/<*>` catch-all is missing. **A live rule change that is not also made in this
  script is self-reverting** — the script's own docstring records that failure mode twice.
- The two other CloudFront distributions are irrelevant to customer URLs and must not be
  touched: `E1SZBXLQ4XNLJ7` has the single alias `mta-sts.wecare.digital` (MTA-STS policy
  endpoint, `mode: enforce`), `E2GP22R4BIFGQ3` has **no alias at all** and is reached only
  through the Amplify `/get/<*>` rewrite.

### 0.3 THE DEFECT: 15 legacy top-level redirects push customers into the staff login

`RENAMED_PREFIXES` in `provision_legacy_redirects.py` emits three rules per prefix
(`/x`, `/x/`, `/x/<*>`) plus one-hop rules. Probed live, all 15 behave like this:

| typed path | hop 1 | final | staff Authenticator shell in body? |
|---|---|---|---|
| `/dm/` `/engage/` | 301 → `/workspace/engage/` | 200 | **yes** |
| `/dashboard/` | 301 → `/workspace/dashboard/` | 200 | **yes** |
| `/contacts/` | 301 → `/workspace/contacts/` | 200 | **yes** |
| `/commerce/` | 301 → `/workspace/commerce/` | 200 | **yes** |
| `/pay/` | 301 → `/workspace/pay/` | 200 | **yes** |
| `/forms/` | 301 → `/workspace/forms/` | 200 | **yes** |
| `/service/` | 301 → `/workspace/service/` | 200 | **yes** |
| `/docs/` | 301 → `/workspace/docs/` | 200 | **yes** |
| `/seo/` | 301 → `/workspace/seo/` | 200 | **yes** |
| `/admin/` | 301 → `/workspace/admin/` | 200 | **yes** |
| `/access/` | 301 → `/workspace/access/` | 200 | **yes** |
| `/link/` | 301 → `/workspace/link/` | 200 | **yes** |
| `/task/` | 301 → `/workspace/task/` | 200 | **yes** |
| `/settings/` | 301 → `/workspace/settings/` | **404** | no (redirect to a dead page) |

Several are plausible mistyped CUSTOMER paths — `/contacts` next to the real public
`/contact/`, plus `/docs`, `/service`, `/pay`, `/link`, `/settings`. This is exactly the
brief's "legacy redirect rules that send CUSTOMERS to workspace/staff/admin access or login
surfaces". `/settings` is additionally broken for staff: it 301s to a page that 404s.

### 0.4 The unknown-path fallback already works and must NOT be turned into a 200

Measured:

```
/definitely-not-a-page   301 -> /definitely-not-a-page/      (trailingSlash normalisation)
/definitely-not-a-page/  404  body = /404.html, "page":"/404"
                              <meta name="robots" content="noindex, follow">
                              <link rel="canonical" href="https://wecare.digital/">
/404/                    200  (the exported page itself; client-side replace to /)
```

`src/pages/404.tsx` then `router.replace('/')` with a **literal** `'/'` — no path, query or
fragment is forwarded, which already satisfies the drop-untrusted-input requirement. The
404 status is **correct and load-bearing**: it is what stops the fallback becoming an
indexable home clone under every invalid URL. `provision_legacy_redirects.py` documents why
`/<*>` must stay `404-200` and must not become `200`/`301`/`302` (a non-404 status matches
unconditionally and would shadow all ~123 exported pages).

**Do not change the catch-all.** It is already `/<*>` → `/404.html` `404-200`.

### 0.5 Valid routes are currently AFTER 145 redirect rules — a payment-delivery hazard

Provider webhooks are registered at **`https://wecare.digital/api/...`** (grepped:
`/api/razorpay-webhook`, `/api/webhook/sinch-rcs`, `/api/webhook/sinch-dlr`,
`/api/wa-business/webhooks`, `/api/voice-cdr-webhook`). They therefore traverse the Amplify
`/api/<*>` rewrite, which sits at index **140 of 146**, after every redirect.

Measured, and these are the semantics that must survive:

```
POST /api/razorpay-webhook   401   (signature rejection — meaningful status, not a page)
POST /api/auth/validate      401
POST /api/payments/webhook    404
GET  /api/webhook/sinch-rcs   200
GET  /mcp                     405      POST /mcp  400
GET  /get/o/stream/media/m/wecare-digital.png   200
GET  /r/zzznotacode           302 -> /contact/
```

No redirect source overlaps `/api`, `/get`, `/r` or `/mcp` today, so nothing is broken
*yet* — but the ordering gives no guarantee. The brief requires valid routes BEFORE the
fallback; this plan moves the four passthrough rewrites ahead of the redirect block and
adds a test that asserts it.

### 0.6 Pre-existing, NOT in owned scope: unknown API path → 302 to a page

```
GET  https://wecare.digital/api/definitely-no-route   302 -> https://wecare.digital/contact/
GET  https://zllr9lrg7j.execute-api.../prod/definitely-no-route  302 -> .../contact/
```

Cause: the HTTP API's single-segment catch-all `GET /{code}` (the short-link reader,
`stack-wecare-url-shortener`) answers a miss with a 302 to `/contact/`. That is inside a
Lambda under `amplify/functions/**`, which is **DO NOT TOUCH**. It is not home-page HTML and
it is not a loop, so it does not regress the brief — but it does mean an unknown
single-segment API path returns a page redirect rather than JSON. **Record it in the matrix
as an open finding owned by another workstream. Do not change it here.**

### 0.7 Subdomain coverage gap — stated exactly, not overstated

Measured facts:

| Fact | Evidence |
|---|---|
| Route 53 zone `Z03939753QJGZ6ZD6BXO8` holds **30** record sets, **zero wildcards** | `list-resource-record-sets` |
| `shop/stack/app.wecare.digital` have **no address** | authoritative `ns-402.awsdns-50.com` answers NOERROR with no A/AAAA data (NODATA) and SOA in authority |
| The cert Amplify presents **does** cover one label | `openssl s_client -servername wecare.digital` → `CN=wecare.digital`, SAN `wecare.digital, *.wecare.digital`, `notAfter=Mar 11 23:59:59 2027` |
| CloudFront **refuses the TLS handshake** for an unregistered host | `--resolve shop.wecare.digital:443:54.192.151.105` → `ssl_verify_result=1`; `openssl -servername shop.wecare.digital` → **TLS alert 40 handshake_failure, "no peer certificate available"**. Apex through the same IP: 200 |
| Amplify registers exactly **two** subdomains | `get-domain-association`: one with no `prefix` key (branch `stack`), one `prefix: "www"`. `enableAutoSubDomain: false`, `autoSubDomainCreationPatterns: null` |

So the gap is **not a certificate gap**. It is an **alias/association + DNS gap**, and making
an unused owned subdomain land on home needs all of:

1. **Amplify**: add subdomain `{prefix: "*", branchName: "stack"}` via
   `update-domain-association`. AWS supports this —
   [Setting up wildcard subdomains](https://docs.aws.amazon.com/amplify/latest/userguide/wildcard-subdomain-support.html)
   requires the prefix be an asterisk alone, forbids partial (`*domain.example.com`) and
   middle (`subdomain.*.example.com`) wildcards. *(Content rephrased for compliance with
   licensing restrictions.)* This mutates the live domain association that currently serves
   the canonical home and can move the domain out of `AVAILABLE` while it re-provisions.
2. **Route 53**: a `*.wecare.digital` A + AAAA alias to the Amplify distribution. Additive
   (no existing record removed), and it touches **none** of MX / `_mta-sts` TXT / SPF /
   DMARC / DKIM / TLS-RPT.
3. Nothing in ACM, **for one label only**.

**The genuine coverage gap: `*.wecare.digital` matches one label, so `a.b.wecare.digital`
is NOT covered.** Adding a second-label host needs a new SAN, i.e. a re-requested ACM
certificate, re-associated on **both** consumers of `f75d0db0-d476-443a-b787-96c4931862d2`
— the Amplify app **and** CloudFront `E1SZBXLQ4XNLJ7`, which is the MTA-STS policy endpoint
under `mode: enforce`. A failure there makes senders refuse inbound mail. That is outside
this task's authority.

Two second-label hosts already exist and already fail the goal:
`xout.wecare.digital` → Wix (`pointing.wixdns.net`), HTTP **404**; and
`www.xout.wecare.digital` → 301 → `xout.wecare.digital` → 404. Repointing them means
editing hosted-zone records for a legacy Wix surface and registering the hosts on Amplify.
**Out of scope — report, do not touch.**

**Decision: do item 1 and 2 as a written, owner-decision item in the matrix document; do
NOT execute them.** Rationale: step 1 is a full-domain-association mutation whose blast
radius is the canonical home this task exists to protect, and step 2 without step 1 makes
every typo'd subdomain resolve to a host CloudFront will refuse at TLS — a worse outcome
than today's clean no-address. The plan's eligible routing work is the path layer.

### 0.8 Obsolete PUBLIC workspace destinations actually found in the app

Audited `Header.tsx`, `Footer.tsx`, `BottomNav.tsx`, `SupportWidget.tsx`, `PageTopBand.tsx`,
`src/content/**`, the generated `llms.txt`/`sitemap.xml`, `robots.txt`:

| Finding | Location | Verdict |
|---|---|---|
| `Header.tsx` — 15 public hrefs, all public pages | — | **clean, no change** |
| `Footer.tsx` — one href, `/` | — | **clean, no change** |
| Live `llms.txt` / `sitemap.xml` (1,407 `<loc>`) | — | **clean** — the only `access`/`sign-in` hits are blog slugs and a prose line saying `/workspace/` is out of bounds |
| **"Dashboard" button → `/workspace/dashboard`** | `src/components/ErrorBoundary.tsx:38,72` | **OBSOLETE PUBLIC BUTTON.** `ErrorBoundary` is mounted inside the `if ( isPublic )` branch of `_app.tsx:1088`, so a customer who hits a render error on any public page is offered a button labelled "Dashboard" that lands them on the staff login |
| **PWA shortcuts → `/workspace/dashboard/`, `/workspace/engage/inbox/`, `/workspace/contacts/`** | `public/manifest.json:27,33,39` | **OBSOLETE PUBLIC MENU.** These are the OS long-press menu entries for anyone who installs the site |
| `Layout.tsx:276` "Sign in" → `/workspace/access` | — | **not public.** `Layout`/`MaybeLayout` is imported by **zero** pages outside `src/pages/workspace/`. Workspace-only chrome — leave it |
| `SearchModal.tsx:50-51` workspace default paths | — | **not public.** Imported only by `Layout.tsx`. Leave it |
| `Breadcrumbs.tsx` `/workspace/dashboard` | — | **not public.** Workspace-only. Leave it |
| `public/sw.js:180` push-click default `/workspace/dashboard/` | — | `needs-verification-during-implementation`. It is a push-notification destination for a staff feature, not a navigation link. **Record, do not change** — changing it could break staff push with no customer benefit |

`/workspace/` itself returns **200 with the Authenticator shell** and is `Disallow:`ed in
`robots.txt`. That is the legitimate existing staff entry. **It stays exactly as it is** —
hiding a link is not access control, and this task does not touch authorization.

### 0.9 The return-path validator, and an owned-path conflict to flag

`src/pages/account/sign-in.tsx:173` is the only `return`-parameter reader in the tree
(`src/pages/cart.tsx:62` is the only producer: `'/account/sign-in/?return=/cart/'`):

```ts
const raw = String( new URLSearchParams( window.location.search ).get( 'return' ) || '' ).trim();
return /^\/[a-zA-Z0-9/_-]*\/?$/.test( raw ) ? raw : '/cart/';
```

Assessed against the brief's requirements:

| Attack | Current regex | Verdict |
|---|---|---|
| `https://evil.example/` | `:` `.` not in class | rejected ✅ |
| `//evil.example` | `.` not in class | rejected ✅ |
| **`//evil`** | all chars in class | **ACCEPTED — protocol-relative, browser reads host `evil`** ❌ |
| `/\evil.example` | `\` not in class | rejected ✅ |
| `%2f%2fevil.example` | `%` not in class | rejected ✅ |
| `/cart/?x=1`, `/cart/#f` | `?` `#` not in class | rejected (falls back to `/cart/`) ✅ |
| **`/workspace/access`** | all chars in class | **ACCEPTED — a staff destination** ❌ |

Two real gaps: `//host` with no dot, and no allowlist (any local path shape passes, including
`/workspace/...`).

**Owned-path conflict, stated openly:** `src/pages/account/**` is on the DO NOT TOUCH list,
so the implementation must **not** edit `sign-in.tsx`. The plan therefore ships the validator
as a **new standalone module plus tests** and writes the one-line wiring into the matrix
document as a handoff to the `account/**` owner. Creating `src/lib/safeReturnPath.ts` is the
one deliberate extension beyond the literal owned-path list; it is a new file that no other
workstream reads, so it is cheap to reject. `src/lib/customerAuth.ts` and
`src/lib/dialCodes.ts` are not touched.

### 0.10 Constraint refinement from the refreshed owner handoff (§17), received mid-planning

Four points, each reconciled against what was measured above. **These override anything
earlier in this document that conflicts.**

**(1) The legacy SEO/content redirect map is NOT a cleanup target.** `/swdhya`, `/no-fault`,
`/legal-stuff` and every other verified legacy content redirect stay. Reconciled: those live
in the `RETIRED`, `RETIRED_TREES` and `FROZEN_EXTERNAL` dicts, which this plan never touched —
only `RENAMED_PREFIXES` changes. No conflict. But the handoff adds a requirement this plan did
not have: **inventory each redirect's real consumer before removing it**, so the 15-prefix
change becomes evidence-led per prefix rather than uniform. See the new step 8a.

**(2) The catch-all is `/<*>` → `/404.html` at `404-200`, not the `/index.html` rule that
stale source comments still describe.** Independently confirmed here (§0.2, §0.4) by reading
the live rule array and by probe: an unknown path stays at the requested URL and returns 404.
The stale commentary is real and still in the tree — five sites:

```
src/pages/404.tsx:14                        OWNED — correct it
src/pages/_app.tsx:938, 999, 1098           NOT owned — record as a follow-up
src/pages/workspace/commerce/catalog.tsx:28 NOT owned — record as a follow-up
```

New step 8b corrects the owned one and logs the other four for their owners. Correcting a
comment in `_app.tsx` would be a zero-behaviour change, but the file is outside the owned-path
list and heavily shared, so it is handed off rather than edited.

**(3) `/access/` → `/workspace/access/` is explicitly confirmed as a cleanup target.** Already
row 18 of the §3 matrix and in the 15. No change needed, now named by the owner.

**(4) The frontend is already deployed: Amplify job 1179, commit 43b26d4a, SUCCEED at
2026-10-01T14:04:19+05:30** (verified via `list-jobs`). Treat the rule change as production:
snapshot first, 302 during rollout, measured before/after probes. **One correction to the
handoff's wording:** custom rules are CloudFront-layer configuration applied by
`amplify update-app`; they do **not** wait for the next build job. So the change goes live
within propagation time of `--apply`, not on the next deploy. That makes it *more* urgent to
have the snapshot on disk first, not less. `needs-verification-during-implementation`: measure
the actual propagation delay and record it.

---

## 1. Design decisions

**D0 — per-prefix consumer inventory gates the change (§0.10 item 1).** Each of the 15
prefixes is classified from evidence before its rule is altered. The legacy content/SEO map
(`RETIRED`, `RETIRED_TREES`, `FROZEN_EXTERNAL`) is out of scope entirely and is not to be
touched; `/access` and `/admin` are confirmed targets. A prefix is only converted once its
inventory shows no non-staff consumer that a 302 to home would damage.

**D1 — a legacy prefix that passes the inventory becomes `302 → /`, not a deletion.** A 302 guarantees the
customer lands on the canonical home with no JavaScript, is reversible per the brief's
rollout rule, and drops the untrusted path entirely (the target is a literal `/`, so no
path, query or fragment is forwarded). <!-- CORRECTED IN PLACE 2026-10-01, third convergence
pass: the parenthesis above is HALF FALSE and was never probed when it was written. The PATH is
dropped, as claimed. The QUERY is NOT - Amplify appends the incoming query string to the redirect
target: `/access/?next=https://evil.example` -> `302` -> `https://wecare.digital/?next=https://evil.example`,
measured. A fragment is never transmitted by a client, so it cannot be probed and is not claimed
either way. The effect is inert - the `Location` host is a fixed literal so it cannot redirect
anyone off-site, and neither `src/pages/index.tsx` nor `src/pages/_app.tsx` reads
`location.search`, `URLSearchParams` or `router.query` - but it diverges from the requirement's
wording and from the other two routes home, which do drop everything. Now pinned on the exact
terminal URL by three harness rows and written up in url-host-matrix-20261001.md §1.4. The old
reading is kept rather than edited away because it is why those rows exist. --> Deleting them instead would let them fall to the
`404-200` catch-all, which only reaches home via client-side JS. `/workspace/**` sources
(rules 5–22, already staff-internal) keep their existing 301s.

**D2 — passthrough rewrites move ahead of the redirect block.** `apply()` becomes
`domain + passthrough + desired_redirects() + middle + catch_all`, where `passthrough` is
the four rules whose source starts `/api`, `/get`, `/r` or `/mcp`. Security-tightening and
additive: it makes it structurally impossible for a page redirect to shadow a payment
webhook, media object or MCP endpoint.

**D3 — the catch-all is untouched.** `/<*>` → `/404.html` `404-200` is already correct
(§0.4). Changing the status would shadow the whole site; changing it to 200 would create the
indexable home clone the brief forbids.

**D4 — `_routes.json` stays byte-identical** (§0.1). It has no consumer; the finding is
documented instead.

**D5 — no DNS, no ACM, no `update-domain-association`, no WAF, no Security Hub.** §0.7
explains why, with the exact gap. Email records are not approached.

**D6 — the validator is an allowlist, not a denylist.** Reject by default; accept only a
recognized set of local customer return paths. Allowlist design in §FEAT-001 step 2.

---

## 2. Ordered implementation

- [ ] **1. Add `src/lib/safeReturnPath.ts` — a reject-by-default local return-path validator.**
      Export `safeLocalReturnPath( raw: string | null | undefined ): string` returning a
      member of the allowlist or the `'/cart/'` default. Allowlist exactly:
      `/cart/`, `/checkout/`, `/orders/`, `/shop/`, `/account/`, `/` — each matched after
      normalisation, with and without a trailing slash. Reject, in this order, before any
      match: anything not starting with a single `/`; a second leading `/` or `\` (blocks
      `//evil`, `//evil.example`, `/\evil`); any `\`, whitespace, control character, `%`,
      `?`, `#`, `:`, or `..` segment (blocks double-encoding, CRLF and traversal); and any
      path whose first segment is `workspace`, `admin`, `access`, `dashboard`, `dm`,
      `engage`, `settings`, `task`, `seo`, `commerce`, `pay`, `forms`, `service`, `contacts`
      or `docs`. Do **not** URL-decode the input — decoding is what turns `%2f%2f` into a
      bypass; compare the raw string and reject `%` outright. Mirror the returns-the-value
      shape of `safeHttpHref` in `src/lib/randomToken.ts` (it returns what to use, not a
      boolean, precisely so a caller cannot validate one string and use another).
      Files: `src/lib/safeReturnPath.ts`
      Verify: `npx vitest run src/test/SafeReturnPath.test.ts` — passes after step 2.

- [ ] **2. Add `src/test/SafeReturnPath.test.ts` pinning every rejection case.**
      Cover, as explicit cases: `https://evil.example/`, `//evil.example`, **`//evil`**,
      `///evil`, `/\evil.example`, `\\evil.example`, `%2f%2fevil.example`,
      `%252f%252fevil`, `/cart/%0d%0aSet-Cookie:x`, `/cart/\t`, `/../etc/passwd`,
      `/cart/../workspace/access`, `javascript:alert(1)`, `data:text/html,x`,
      `/workspace/access`, `/workspace/dashboard/`, `/admin/`, `/dashboard/`,
      `mailto:a@b`, `''`, `null`, `undefined` — each must return `'/cart/'`. Accepted
      cases: `/cart/`, `/cart`, `/checkout/`, `/orders/`, `/shop/`, `/account/`, `/`.
      Add one case asserting an accepted value never carries a query or fragment.
      Files: `src/test/SafeReturnPath.test.ts`
      Verify: `npx vitest run src/test/SafeReturnPath.test.ts` — all cases pass.

- [ ] **3. Repoint the public ErrorBoundary escape button from the staff dashboard to home.**
      In `src/components/ErrorBoundary.tsx`, change `handleGoHome` to
      `window.location.href = '/';` and relabel the button at line 72 from `Dashboard` to
      `Home`. Keep `handleReload` and the component API unchanged. A full document load is
      correct here — the React tree has already failed, so the router is the least
      trustworthy thing available (same reasoning `src/pages/404.tsx` records for its
      anchor).
      Files: `src/components/ErrorBoundary.tsx`
      Verify: `npx vitest run` and `npm run typecheck` — both clean; no test asserts the old
      label (grep `src/test` for `handleGoHome`/`Dashboard` before editing to confirm).

- [ ] **4. Remove the three workspace PWA shortcuts from the public web app manifest.**
      In `public/manifest.json`, delete the `shortcuts` entries targeting
      `/workspace/dashboard/`, `/workspace/engage/inbox/` and `/workspace/contacts/`. If
      that empties `shortcuts`, remove the key rather than leaving `[]`. Leave every other
      manifest field (name, icons, `start_url`, `display`, theme colours) untouched.
      Files: `public/manifest.json`
      Verify: `node -e "JSON.parse(require('fs').readFileSync('public/manifest.json','utf8'))"`
      exits 0, and `npx vitest run` stays green.

- [ ] **5. Add `src/test/PublicWorkspaceLinks.test.ts` — a source-text guard against
      regression.** Follow the read-source-as-text technique of
      `src/test/PublicRouteRegistration.test.ts` (importing `_app.tsx` would execute
      `Amplify.configure`). Assert: (a) `src/components/ErrorBoundary.tsx` contains no
      `/workspace` string; (b) `public/manifest.json`, parsed, contains no value starting
      `/workspace`; (c) `src/components/Header.tsx` and `src/components/Footer.tsx` contain
      no `/workspace`, `/admin`, `/access` or `sign-in` href. Add an
      `INTENTIONALLY_WORKSPACE_ONLY` map naming `Layout.tsx`, `SearchModal.tsx`,
      `Breadcrumbs.tsx` and `public/sw.js` with the one-line reason each is exempt, so the
      exemptions are decisions on the record rather than silent gaps.
      Files: `src/test/PublicWorkspaceLinks.test.ts`
      Verify: `npx vitest run src/test/PublicWorkspaceLinks.test.ts` — passes.

- [ ] **6. Add a `src/pages/404.tsx` contract test.** Assert from source text that the page
      calls `router.replace` with a **literal** `'/'` (not a template, not a variable, so no
      path/query/fragment can ever be forwarded), carries
      `<meta name="robots" content="noindex, follow">`, and sets
      `rel="canonical"` to `https://wecare.digital/`. This pins §0.4's measured live
      behaviour so a future edit cannot quietly start forwarding untrusted input.
      `src/pages/404.tsx` itself needs **no change** — record that it was read and verified.
      Files: `src/test/NotFoundFallback.test.ts`
      Verify: `npx vitest run src/test/NotFoundFallback.test.ts` — passes.

- [ ] **7. Snapshot the live Amplify custom rules into the committed snapshots directory.**
      Write the exact current array to
      `docs/execution/snapshots/amplify-custom-rules-before-url-host-cleanup-20261001.json`
      via `aws amplify get-app --app-id d22dm4b0jn71jw --region us-east-1 --query
      'app.customRules'`. Record in the file's sibling matrix document: 146 rules,
      retrieval timestamp, and that **Amplify exposes no ETag** for `get-app`/`update-app`
      (unlike `cloudfront update-distribution`) — so the snapshot plus the script's own
      timestamped `.scratch/amplify-custom-rules-before-<ts>.json` are the rollback, and the
      rollback procedure is `update-app --custom-rules file://<snapshot>`.
      Files: `docs/execution/snapshots/amplify-custom-rules-before-url-host-cleanup-20261001.json`
      Verify: the file parses as JSON and has length 146;
      `python tests/test_legacy_redirect_rollback_snapshot.py` equivalent via
      `.venv/bin/python -m pytest tests/test_legacy_redirect_rollback_snapshot.py -q` still
      passes (it pins that the script snapshots **before** `update_app`).

- [ ] **8a. Inventory the real consumer of each of the 15 legacy prefixes BEFORE changing any
      of them** (§0.10 item 1 — the owner forbids a blanket purge of the legacy redirect map).
      For each of `/dm /engage /dashboard /contacts /commerce /pay /forms /service /docs /seo
      /admin /access /link /task /settings`, record in a table: (i) does the path appear in
      `out/sitemap.xml`, `public/robots.txt`, `out/llms.txt` or the MCP catalogue; (ii) does
      any approved provider artefact name it — cross-check `FROZEN_EXTERNAL` in
      `provision_legacy_redirects.py` and `stack-wecare-digital-DLTTemplates`, because a DLT or
      RCS body cannot be edited and a redirect is the only repair available there; (iii) search
      impressions, measured with `.venv/bin/python scripts/retired_url_equity.py --json` across
      BOTH Search Console properties over the maximum window (the apex property has no backfill;
      the 480-day www history is where the equity lives — that script's docstring records a
      40x under-report from using a 90-day window); (iv) in-repo references outside
      `src/pages/workspace/**`. Classify each as CONVERT (staff-only destination, no non-staff
      consumer), KEEP (a real external consumer a 302 to home would damage), or
      NEEDS-OWNER. `/access` and `/admin` are CONVERT by explicit owner instruction. If
      `retired_url_equity.py` cannot authenticate, say so and classify from (i), (ii) and (iv)
      alone rather than guessing — do not treat an unrunnable measurement as a zero.
      **Do not touch `RETIRED`, `RETIRED_TREES` or `FROZEN_EXTERNAL`** — `/swdhya`,
      `/no-fault`, `/legal-stuff`, `/faq`, `/my-order`, `/product-page/<*>`, `/selfservice`,
      `/track` and the rest of the content map are preserved verbatim.
      Files: the inventory table goes into `docs/execution/url-host-matrix-20261001.md`
      Verify: every one of the 15 rows carries a classification with its evidence; the probe
      harness in step 11 asserts that every `RETIRED`/`FROZEN_EXTERNAL` source still redirects
      to its existing live target.

- [ ] **8b. Correct the stale catch-all commentary in the one owned file** (§0.10 item 2).
      `src/pages/404.tsx:14` states the last Amplify rule is `/<*>` → `/index.html`; it is
      `/404.html`, which is precisely why this page's `noindex` and canonical now reach a
      mistyped URL. Rewrite that paragraph with the measured 2026-10-01 state and keep the old
      reading as corrected-in-place history rather than deleting it. Record the four
      unowned sites (`src/pages/_app.tsx:938,999,1098` and
      `src/pages/workspace/commerce/catalog.tsx:28`) in the matrix document as follow-ups for
      their owners — do **not** edit them.
      Files: `src/pages/404.tsx`
      Verify: `npx vitest run src/test/NotFoundFallback.test.ts` still passes (the test pins
      behaviour, not prose), `npm run typecheck` clean.

- [ ] **8. Change `scripts/provision_legacy_redirects.py` so every CONVERT prefix from step 8a
      lands on home instead of the staff login.** Introduce
      `OBSOLETE_PUBLIC_WORKSPACE_PREFIXES: tuple[str, ...]` holding the CONVERT keys from step
      8a and move them out of `RENAMED_PREFIXES`. Any prefix classified KEEP or NEEDS-OWNER
      stays in `RENAMED_PREFIXES` untouched, with a dated comment naming the evidence that kept
      it there. Emit, per CONVERT prefix,
      `{'source': p, 'target': '/', 'status': '302'}`,
      `{'source': p + '/', 'target': '/', 'status': '302'}` and
      `{'source': f'{p}/<*>', 'target': '/', 'status': '302'}`, and **stop emitting** the
      one-hop `/dm/calls`-style rules for those prefixes. Extend `is_ours()` so every source
      shape it used to own — `p`, `p/`, `p/<*>` and the one-hop forms — is still claimed, or
      `apply()` will preserve the old 301s in `middle` and the change will not stick (the
      docstring records this exact bug happening twice). Add `'/'` to
      `LIVE_TARGET_PREFIXES` so `_targets_dead_prefix` does not judge the new rules dead on
      sight. Replace the `RENAMED_PREFIXES` docstring block with a dated note recording:
      the measured defect (14 of 15 ended on the Authenticator shell at 200, `/settings`
      on a 404), that 302 was chosen for reversibility per the brief, and that staff
      bookmarks to the old prefixes now land on home while the real entry `/workspace/**`
      is unchanged.
      Files: `scripts/provision_legacy_redirects.py`
      Verify: `.venv/bin/python scripts/provision_legacy_redirects.py` (no flag, read-only)
      reports exactly the 45 new rules as missing and lists no unexpected removals;
      `.venv/bin/python -m pytest tests/test_legacy_redirect_rollback_snapshot.py -q` passes.

- [ ] **9. Reorder `apply()` so the four passthrough rewrites precede every redirect.**
      In `provision_legacy_redirects.py::apply`, partition `keep` into
      `passthrough` (source starts with `/api`, `/get`, `/r/` or `/mcp`) and the remaining
      `middle`, and build `domain + passthrough + desired_redirects() + middle + catch_all`.
      Add a guard that raises before `update_app` if any rule in `desired_redirects()` has a
      source that could match `/api/`, `/get/`, `/r/` or `/mcp` — a payment webhook is
      delivered through `/api/<*>` (§0.5), so shadowing it is a payment outage, not a
      cosmetic bug.
      Files: `scripts/provision_legacy_redirects.py`
      Verify: `.venv/bin/python -m pytest tests/test_legacy_redirect_rollback_snapshot.py -q`
      passes, and the read-only run prints the four passthrough rules positioned above the
      redirect block.

- [ ] **10. Add `tests/test_url_host_routing_rules.py` — a pytest guard on the rule array.**
      Load `provision_legacy_redirects.py` by `importlib` (the pattern
      `tests/test_legacy_redirect_rollback_snapshot.py` already uses) and assert against the
      array `apply()` would write, using the committed snapshot from step 7 as the "live"
      input and a stub client: (a) no rule targets a path starting `/workspace`; (b) each of
      the 15 prefixes and its `/<*>` form targets `/` at `302`; (c) `/api/<*>`, `/get/<*>`,
      `/r/<*>` and `/mcp` all appear at a lower index than every `301`/`302` redirect;
      (d) the last rule is `/<*>` → `/404.html` `404-200`; (e) the first rule is the
      `https://www.wecare.digital` → `https://wecare.digital` 301. No AWS call.
      Files: `tests/test_url_host_routing_rules.py`
      Verify: `.venv/bin/python -m pytest tests/test_url_host_routing_rules.py -q` — passes.

- [ ] **11. Add `scripts/probe_url_host_matrix.py` — the before/after probe harness.**
      Model it on `scripts/retired_url_probe.py` (same no-redirect opener, same thread pool,
      same verdict-per-row shape) and on the terminal-status lesson already learned in
      `scripts/retired_url_equity.py`: `trailingSlash: true` means an extensionless path
      always 301s first, so **only the last status in the chain means anything**. Probe the
      §3 matrix rows, emit `--json` and a human table, and exit non-zero on any row whose
      measured outcome differs from its expectation. Build on
      `scripts/retired_url_equity.py` by importing nothing from it but reusing its
      `_one_hop`/`probe` chain-following design; leave that file otherwise unchanged (it is
      an untracked draft from another session and is not this task's to rewrite). Read-only:
      no AWS write, no secret read, HTTP GET only.
      Files: `scripts/probe_url_host_matrix.py`
      Verify: `.venv/bin/python scripts/probe_url_host_matrix.py --json` runs clean against
      the live site and reports every row; before step 12 it must FAIL on the 15 prefix rows
      (that failure is the reproduction of the defect) and PASS on them after.

- [ ] **12. Apply the rule change to the live Amplify app and confirm.**
      Run `.venv/bin/python scripts/provision_legacy_redirects.py --apply`. It writes its own
      timestamped rollback to `.scratch/` before calling `update_app` (pinned by
      `tests/test_legacy_redirect_rollback_snapshot.py`). Then
      `.venv/bin/python scripts/provision_legacy_redirects.py --verify` and
      `.venv/bin/python scripts/retired_url_probe.py` — the second guards that no retired
      public URL started answering 200. Amplify custom-rule changes take effect at the CDN
      without a rebuild; allow for propagation and re-probe rather than concluding from one
      attempt.
      Files: none (live AWS write, snapshot from step 7 is the rollback)
      Verify: `.venv/bin/python scripts/probe_url_host_matrix.py` exits 0 with every §3
      after-row matching, **and** these must be unchanged from §0.5:
      `POST /api/razorpay-webhook` 401, `POST /api/auth/validate` 401, `GET /mcp` 405,
      `POST /mcp` 400, `GET /get/o/stream/media/m/wecare-digital.png` 200,
      `GET /definitely-not-a-page/` 404 with `"page":"/404"`,
      `https://www.wecare.digital/shop/` 301 → `https://wecare.digital/shop/`.

- [ ] **13. Write `docs/execution/url-host-matrix-20261001.md`.**
      Must contain: the §3 matrix with measured before AND after values (no invented before
      values — every one in this plan is measured and may be quoted); the domain-coverage
      inventory from §0.7 including the TLS alert 40 evidence and the one-label-only
      certificate limit; the exact subdomain work NOT done and why (the Amplify
      `update-domain-association` blast radius and the Route 53 wildcard dependency),
      framed as an owner-decision item; the `_routes.json` no-consumer finding from §0.1;
      the §0.6 unknown-API-route finding marked as owned by another workstream; the
      `public/sw.js` item marked `needs-verification-during-implementation`; the ready-to-apply
      one-line wiring handoff for `src/pages/account/sign-in.tsx` (replace
      `returnPathFromUrl`'s regex branch with
      `safeLocalReturnPath( new URLSearchParams( window.location.search ).get( 'return' ) )`),
      naming `src/pages/account/**` as the owning workstream; and the rollback procedure
      (`aws amplify update-app --app-id d22dm4b0jn71jw --custom-rules
      file://docs/execution/snapshots/amplify-custom-rules-before-url-host-cleanup-20261001.json`,
      plus the note that Amplify exposes no ETag).
      Files: `docs/execution/url-host-matrix-20261001.md`
      Verify: every matrix row has a measured before and after value; no row says "expected"
      without a probe behind it.

- [ ] **14. Full gate run, then commit by explicit path with `--only`.**
      Run `npm run typecheck`, `npm run lint`, `npx vitest run`, `npm run build` (which also
      runs `generate-public-pages`, `generate-sitemap`, `generate-blog-search-index` and
      `generate-llms-txt`, so it is the real export check), and
      `.venv/bin/python -m pytest tests/test_legacy_redirect_rollback_snapshot.py
      tests/test_url_host_routing_rules.py -q`. Confirm `out/404/index.html` still exists in
      the export and `out/sitemap.xml` still has 1,407 `<loc>` entries (or explain any
      change). The working tree holds another session's modified files
      (`amplify/functions/payments/razorpay-webhook/handler.py`,
      `amplify/functions/shared/lambda_utils/ecommerce/**`,
      `.kiro/specs/whatsapp-wix-commerce/**`, `docs/execution/change-authority-matrix.md`
      and several untracked docs) — **the index may already be dirty with work that is not
      ours**, so commit with
      `git add <new files> && git commit --only <all owned paths> -F <message-file>` on
      branch `stack`. Never `git add .`/`-A`, never `--amend`, no force push.
      Files: none
      Verify: all five gates exit 0; `git show --stat HEAD` lists only owned paths.

---

## 3. URL / host matrix rows to probe

`before` is measured 2026-10-01. `after` is the required outcome.

| # | Request | before | after (required) |
|---|---|---|---|
| 1 | `https://wecare.digital/` | 200 | 200 (unchanged) |
| 2 | `https://www.wecare.digital/` | 301 → apex `/` | unchanged |
| 3 | `https://www.wecare.digital/shop/` | 301 → apex `/shop/` | unchanged (path preserved) |
| 4 | `https://wecare.digital/definitely-not-a-page` | 301 → `…/` | unchanged |
| 5 | `https://wecare.digital/definitely-not-a-page/` | 404, `"page":"/404"`, noindex, canonical `/` | unchanged — **404, not 200** |
| 6 | `/404/` | 200 (exported page, client replace to `/`) | unchanged |
| 7–20 | `/dm/ /engage/ /dashboard/ /contacts/ /commerce/ /pay/ /forms/ /service/ /docs/ /seo/ /admin/ /access/ /link/ /task/` | 301 → `/workspace/…` → 200 **Authenticator shell** | **302 → `/`** for every CONVERT prefix from step 8a; a KEEP or NEEDS-OWNER prefix stays 301 and its row records why. `/access/` and `/admin/` are CONVERT by owner instruction |
| 21 | `/settings/` | 301 → `/workspace/settings/` → 404 | **302 → `/`** if CONVERT (it currently redirects to a page that does not exist) |
| 22 | `/dm/calls` | 301 → `/workspace/engage/inbox/?channel=voice` | **302 → `/`** if `/dm` is CONVERT |
| 23 | `/admin/anything/deep` | 301 → `/workspace/admin/anything/deep` | **302 → `/`** |
| 24 | `/workspace/` | 200 Authenticator shell, `Disallow` in robots | **unchanged — staff entry, not hidden, not opened** |
| 25 | `/workspace/access/` | 200 | unchanged |
| 26 | `/workspace/engage/calls` | 301 → `/workspace/engage/inbox/?channel=voice` | unchanged (staff-internal) |
| 27 | `/account/sign-in/` | 200 | unchanged |
| 28 | `/shop/` `/cart/` `/orders/` `/blog/` `/get/` `/grahak-os/` `/vayulok/` `/dastavez/` `/elsewhere/` `/hunar/` `/niji-setu/` | 200 | unchanged |
| 29 | `POST /api/razorpay-webhook` | **401** | **unchanged 401** |
| 30 | `POST /api/auth/validate` | 401 | unchanged |
| 31 | `POST /api/payments/webhook` | 404 | unchanged |
| 32 | `GET /api/webhook/sinch-rcs` | 200 | unchanged |
| 33 | `GET /mcp` / `POST /mcp` | 405 / 400 | unchanged |
| 34 | `GET /get/o/stream/media/m/wecare-digital.png` | 200 | unchanged |
| 35 | `GET /r/zzznotacode` | 302 → `/contact/` | unchanged (short-link miss) |
| 36 | `GET /api/definitely-no-route` | 302 → `/contact/` | unchanged — **finding, another workstream owns it (§0.6)** |
| 37 | `/selfservice` `/track` | 301 → `/submit-request/` `/orders/` | unchanged (DLT/RCS frozen links) |
| 38 | **Every `RETIRED` / `RETIRED_TREES` / `FROZEN_EXTERNAL` source** — `/swdhya` `/no-fault` `/legal-stuff` `/legal-stuffs` `/faq` `/my-order` `/expoweek` `/ritual-store` `/swdhya-store` `/request-tracking` `/rx-slot` `/bring-friends` `/home` `/open-possibility` `/product-page/partner` `/selfservice` `/track` | 301 → live targets | **unchanged — the legacy content/SEO map is explicitly NOT a cleanup target (§0.10 item 1). Probe every one; any that stops redirecting is a failure** |
| 39 | `https://shop.wecare.digital/` | no address; TLS alert 40 at the CF IP | unchanged — gap documented, §0.7 |
| 40 | `https://xout.wecare.digital/` | 404 (Wix) | unchanged — out of scope, §0.7 |
| 41 | `https://www.xout.wecare.digital/` | 301 → `xout…` → 404 | unchanged — second-label, no cert coverage |
| 42 | `https://mta-sts.wecare.digital/` | 403 at `/`; policy path untouched | **must not change** |

Loop check for every 302 row: target is the literal `/`, which answers 200, so one hop and
no loop. Assert it in the probe script rather than assuming it.

---

## 4. Commands

```
npm run typecheck
npm run lint
npx vitest run
npm run build
.venv/bin/python -m pytest tests/test_legacy_redirect_rollback_snapshot.py tests/test_url_host_routing_rules.py -q
.venv/bin/python scripts/provision_legacy_redirects.py            # read-only report
.venv/bin/python scripts/provision_legacy_redirects.py --apply    # live write, after gates
.venv/bin/python scripts/provision_legacy_redirects.py --verify
.venv/bin/python scripts/retired_url_probe.py
.venv/bin/python scripts/probe_url_host_matrix.py --json
```

`python` is not on PATH — always `.venv/bin/python`. Node is v24.21.0, `node_modules` present.

---

## 5. needs-verification-during-implementation

1. **`public/sw.js:180`** push-click default `/workspace/dashboard/`. Read, not reproduced as
   a customer-facing path. Record; do not change without evidence a customer can reach it.
2. **Amplify apex subdomain `prefix` field.** `get-domain-association` returns the apex entry
   with **no `prefix` key** and `dnsRecord: "* CNAME d2av2go6w170k.cloudfront.net"`. Whether
   that renders prefix `""` or a registered `*` could not be settled from the API. It does not
   change the plan: TLS alert 40 for `shop.wecare.digital` proves no wildcard host is served
   today, and no `*` record exists in Route 53. Re-read before any subdomain work.
3. **Route 53 NODATA vs NXDOMAIN** for absent names. The authoritative server answers NOERROR
   with no data. Unusual, and not load-bearing — either way there is no address and no TCP
   connection (curl exit, `http_code=000`).
4. **Whether any staff workflow depends on a short prefix bookmark.** Not knowable from the
   repo. The brief orders the change; `/workspace/**` remains the entry. Flag in the matrix
   doc so the owner can object cheaply.
5. **Propagation time for an Amplify custom-rule change.** Not measured here. Re-probe rather
   than concluding from a single post-apply attempt.
