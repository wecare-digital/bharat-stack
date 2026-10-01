# URL and host matrix — 2026-10-01

Measured against AWS account `775261844268` (`wecare-prod`, `us-east-1`), Amplify app
`d22dm4b0jn71jw` branch `stack`, and the live public site. Every `before` and `after` value in
this document was probed. Where something could not be measured it says so rather than
estimating.

Companion records: `docs/execution/url-redirect-removal-20261001.md` (the owner's removal, a
different session), `.agents/tasks/url-host-cleanup/plan.md` (the investigation this task was
planned from).

---

## 0. What changed, and the plan it replaced

**Two separate changes landed on the Amplify rule array on 2026-10-01, in this order.**

| # | Change | Rules | Who |
|---|---|---:|---|
| 1 | Owner instruction *"delete all url redirects now"* — every custom redirect removed, all rewrites and the 404 fallback preserved | **146 → 8** | another session, see `url-redirect-removal-20261001.md` |
| 2 | Host canonicalisation `https://www.wecare.digital` → `https://wecare.digital` restored, 301 | **8 → 9** | this task |

**The plan this task started from is SUPERSEDED, and the reason is worth stating plainly
rather than quietly dropping.** It was written to convert 15 legacy top-level prefixes from
`301 → /workspace/<prefix>` into `302 → /`. The defect was real and measured: 14 of the 15
terminated on the **staff Authenticator shell at HTTP 200** — a customer who typed `/contacts`,
which sits next to the genuine public `/contact/`, was handed a staff login — and `/settings`
301d to a `/workspace/settings/` page that 404s.

Change 1 closed that defect by deletion instead. All 15 now terminate at **404** on the
`/<*>` → `/404.html` catch-all. A `302 → /` is no longer needed to close it, and adding 45
custom redirects back would contradict the owner's instruction. So the conversion was not
implemented, and the planned assertions are recorded as superseded in
`tests/test_url_host_routing_rules.py` rather than deleted.

**Only change 2 was made by this task: one rule.** It was not in the original plan. It
repairs an unintended side effect of change 1 — with the www → apex 301 gone,
`https://www.wecare.digital/` and every path under it served the entire site at **200**, so
the site was reachable under two hostnames with identical content. That is
host-canonicalisation loss, not redirect cleanup. Measured before restoring:
`https://www.wecare.digital/` 200, `https://www.wecare.digital/shop/` 200.

### The live rule array now, in full (9 rules)

| # | source | target | status |
|---:|---|---|---|
| 0 | `https://www.wecare.digital` | `https://wecare.digital` | 301 |
| 1 | `/get` | `/get/index.html` | 200 |
| 2 | `/get/` | `/get/index.html` | 200 |
| 3 | `/get/<*>` | `https://d1kf2rchz7yras.cloudfront.net/<*>` | 200 |
| 4 | `/r/<*>` | `https://zllr9lrg7j.execute-api.us-east-1.amazonaws.com/prod/r/<*>` | 200 |
| 5 | `/api/<*>` | `https://zllr9lrg7j.execute-api.us-east-1.amazonaws.com/prod/<*>` | 200 |
| 6 | `/mcp` | `…/prod/mcp` | 200 |
| 7 | `/mcp/` | `…/prod/mcp` | 200 |
| 8 | `/<*>` | `/404.html` | 404-200 |

Applied at **2026-10-01T08:59:52Z** (`2026-10-01T14:29:52+05:30`). Readback confirmed 9 rules,
first rule the host canonicalisation, last rule the 404-200 fallback, **+1 added / −0 removed /
0 reordered** (diffed, not assumed).

### Propagation, measured — and why one attempt would have given the wrong answer

An Amplify custom-rule change reaches the CDN without a rebuild, but it is not instant and it
does not evict what the edge already holds. **~25 minutes after applying**, `GET` on
`https://www.wecare.digital/` correctly returned `301` with `x-cache: Miss from cloudfront`,
while **`HEAD` on the same URL returned `200` with `x-cache: Hit from cloudfront` and
`age: 1501`** — a cached object from before the change. The apex home page carries
`cache-control: public, max-age=0, s-maxage=31536000`, a one-year shared cache, which is what
let a stale 200 sit at an edge; a cache-busting query string did not shift it either, because
the distribution's cache key ignores the query string for static objects.

It resolved on its own. Re-measured shortly afterwards and five consecutive times: `HEAD` and
`GET` both return `301` on `/` and `/shop/`, every attempt `x-cache: Miss`, apex steady at
`200`. **No invalidation was created** — the GET path, which is what a crawler and a browser
navigation use, was correct throughout, and the stale entry expired without intervention.

Recorded because the first reading looked like a failed change and was not one. This is the
re-probe-rather-than-conclude rule earning its place rather than being quoted.

Structural properties that hold and are pinned by `tests/test_url_host_routing_rules.py`: no
rule targets `/workspace/**`; all seven passthrough rewrites precede every redirect; the
catch-all is last and keeps `404-200`; the host rule's source and target are **bare origins
with no path**, which is what makes Amplify carry the request path across.

---

## 1. The matrix

85 rows, probed by `scripts/probe_url_host_matrix.py`, exit 0. Only the **terminal** status in
a chain is judged: `trailingSlash: true` means an extensionless path always 301s to add the
slash first, so a first-hop reading calls `/admin` "301, fine" whether the chain ends on a 404
or on a staff login at 200. Chains are walked with a seen-set, so a loop is a hard failure
rather than two individually-correct status codes.

| # | Request | before (measured) | after (measured) | verdict |
|---|---|---|---|---|
| 1 | `https://wecare.digital/` | 200 | 200 | unchanged |
| 2 | `https://www.wecare.digital/` | **200 — duplicate host** | **301 → apex `/`, terminal 200** | **repaired** |
| 3 | `https://www.wecare.digital/shop/` | **200 — duplicate host** | **301 → apex `/shop/`, terminal 200** | **repaired, path preserved** |
| 4 | `https://www.wecare.digital/blog/` | 200 — duplicate host | 301 → apex `/blog/`, 200 | repaired |
| 5 | `http://wecare.digital/` | 301 → https | 301 → https, terminal 200 | unchanged |
| 6 | `/definitely-not-a-page` | 301 → `…/` → 404 | same | unchanged |
| 7 | `/definitely-not-a-page/` | 404, `"page":"/404"`, `noindex`, canonical `/` | same, all three asserted in the body | unchanged — **404, not 200** |
| 8 | `/404/` | 200 | 200 | unchanged |
| 9–23 | `/dm/ /engage/ /dashboard/ /contacts/ /commerce/ /pay/ /forms/ /service/ /docs/ /seo/ /admin/ /link/ /task/ /settings/` **+ `/access/`, see 23a** | **301 → `/workspace/…` → 200 Authenticator shell** (`/settings/` → 404) | **404, every one** | **defect closed by the owner's removal, not by this task's 302** |
| **23a** | **`/access/`, `/access`, `/access/anything/deep`** | **301 → `/workspace/access/` → 200 staff shell** | **302 → `https://wecare.digital/` → 200 home** | **superseded 15:54 IST — now the planned CONVERT destination, §5.5** |
| 24–38 | the same 15 in bare form (`/dm`, `/admin`, …) | 301 → slash → staff shell | 301 → slash → **404** (`/access` → 302 → home) | closed |
| 39 | `/dm/calls` | 301 → `/workspace/engage/inbox/?channel=voice` | 301 → slash → **404** | closed |
| 40 | `/admin/anything/deep` | 301 → `/workspace/admin/anything/deep` | 301 → slash → **404** | closed |
| 41–57 | `/swdhya/ /no-fault/ /legal-stuff/ /legal-stuffs/ /faq/ /my-order/ /expoweek/ /ritual-store/ /swdhya-store/ /request-tracking/ /rx-slot/ /bring-friends/ /home/ /open-possibility/ /product-page/partner/ /selfservice/ /track/` | 301 → live targets | **404, every one** | **owner-retired — see §3, this is the intended end state** |
| 58 | `/workspace/` | 200 Authenticator shell, `Disallow` in robots | 200 | **unchanged — staff entry, neither hidden nor opened** |
| 59 | `/workspace/access/` | 200 | 200 | unchanged |
| 60 | `/account/sign-in/` | 200 | 200 | unchanged — customer auth |
| 61–72 | `/ /shop/ /cart/ /orders/ /blog/ /contact/ /checkout/status/ /grahak-os/ /vayulok/ /terms/ /anew/ /clear-closure/` | 200 | 200 | unchanged |
| 73 | `POST /api/razorpay-webhook` | **401** | **401** | unchanged — signature rejection, not a page |
| 74 | `POST /api/auth/validate` | 401 | 401 | unchanged |
| 75 | `POST /api/payments/webhook` | 404 | 404 | unchanged |
| 76 | `POST /api/wa-business/webhooks` | not in the plan; measured **401** | 401 | unchanged |
| 77 | `GET /api/webhook/sinch-rcs` | 200 | 200 | unchanged |
| 78 | `GET /mcp` | 405 | 405 | unchanged |
| 79 | `POST /mcp` | 400 | 400 | unchanged |
| 80 | `GET /get/o/stream/media/m/wecare-digital.png` | 200 | 200 | unchanged |
| 81 | `GET /r/zzznotacode` | 302 → `/contact/` | 302 → `/contact/` → 200, one hop | unchanged |
| 82 | `GET /api/definitely-no-route` | 302 → `/contact/` | same | unchanged — **open finding, §5** |
| 83 | `https://shop.wecare.digital/` | no address; TLS alert 40 at the CF IP | no TCP connection (status 0) | unchanged — **gap, §4** |
| 84 | `https://xout.wecare.digital/` | 404 (Wix) | 404 | unchanged — out of scope, §4 |
| 85 | `https://mta-sts.wecare.digital/` | 403 at `/` | 403 | **must not change** — email auth is fail-closed |

Two measurements that were not in the plan and are recorded because they were taken:
`GET /api/webhook/sinch-dlr` = **404** and `POST /api/voice-cdr-webhook` = **404**. Both are
API-side routing answers reached through the intact `/api/<*>` rewrite, not hosting failures.

---

## 2. Consumer inventory for the 15 legacy prefixes

Taken **before** any rule change was contemplated, because a blanket purge of a redirect map
is forbidden and because a redirect with a real external consumer must not be converted on
the strength of its target alone. The classification is now of historical interest only —
change 1 deleted all 15 — but it is the evidence that the deletion damaged no consumer, so it
is recorded rather than dropped.

| prefix | rules it owned in the 146-rule array | every target was | in live sitemap (1,407 `<loc>`) | in `llms.txt` | in `robots.txt` | approved provider artefact | search impressions | class |
|---|---:|---|---:|---:|---|---|---:|---|
| `/dm` | 19 | `/workspace/engage/**` | 0 | 0 | no | no | **0** | CONVERT |
| `/engage` | 19 | `/workspace/engage/**` | 0 | 0 | no | no | **0** | CONVERT |
| `/dashboard` | 3 | `/workspace/dashboard/` | 0 | 0 | no | no | **0** | CONVERT |
| `/contacts` | 3 | `/workspace/contacts/` | 0 | 0 | no | no | **0** | CONVERT |
| `/commerce` | 3 | `/workspace/commerce/` | 0 | 0 | no | no | **0** | CONVERT |
| `/pay` | 3 | `/workspace/pay/` | 0 | 0 | no | no | **0** | CONVERT |
| `/forms` | 3 | `/workspace/forms/` | 0 | 0 | no | no | **0** | CONVERT |
| `/service` | 3 | `/workspace/service/` | 0 | 0 | no | no | **0** | CONVERT |
| `/docs` | 3 | `/workspace/docs/` | 0 | 0 | no | no | **0** | CONVERT |
| `/seo` | 3 | `/workspace/seo/` | 0 | 0 | no | no | **0** | CONVERT |
| `/admin` | 3 | `/workspace/admin/` | 0 | 0 | no | no | **0** | CONVERT (owner-named) |
| `/access` | 3 | `/workspace/access/` | 0 | 0 | no | no | **0** | CONVERT (owner-named) |
| `/link` | 5 | `/workspace/link/` | 0 | 0 | no | no | **0** | CONVERT |
| `/task` | 3 | `/workspace/task/` | 0 | 0 | no | no | **0** | CONVERT |
| `/settings` | 3 | `/workspace/settings/` | 0 | 0 | no | no | **0** | CONVERT |

75 of the 138 removed rules belonged to these 15. **Every target, without exception, was under
`/workspace/`** — read from the committed 146-rule snapshot, not inferred.

`robots.txt` carries exactly two `Disallow` lines, `/api/` and `/workspace/`; none of the 15
has a rule of its own. Its own comment records why: all fourteen authenticated families
nested under `/workspace/` on 2026-09-26 and their individual lines were removed, because *a
Disallow for a route that does not exist implies the route does*.

**Search impressions measured, not assumed absent.**
`.venv/bin/python scripts/retired_url_equity.py --json` authenticated and ran over the maximum
window across both Search Console properties (13,756 recoverable impressions in total, 0
errors). **None of the 15 prefixes appears in the report at all** — zero impressions each.
That is the expected shape: they are `Disallow`ed staff paths that were never in a sitemap.
This is a real zero from a successful measurement, not an unrunnable tool reported as zero.

**No approved provider artefact names any of the 15.** The two paths frozen inside approved
provider templates are `/selfservice` and `/track`, and neither is in this set — see §3, where
they matter a great deal.

---

## 3. The legacy content map: owner-retired, and the one consequence that needs an owner's eyes

This task was instructed to leave the legacy content/SEO map alone and to probe that every
entry still redirected. **It does not, and that is correct**: change 1 removed those rules
under the owner's explicit instruction, and `url-redirect-removal-20261001.md` records the
decision. All 17 sources are measured at 404 above. They are **not** restored here, and
restoring one would need a new owner instruction.

What the removal costs, measured so the decision is informed rather than invisible. Figures
are that Search Console property's own, over its full retained window:

| retired source | former target | impressions | clicks |
|---|---|---:|---:|
| `/selfservice` | `/submit-request/` | **1,128** | 4 |
| `/swdhya` | `/anew/` | 531 | 3 |
| `/no-fault` | `/clear-closure/` | 499 | 1 |
| `/legal-stuff` | `/terms/` | 379 | 0 |
| `/expoweek` | `/expo-week/` | 292 | 1 |
| `/legal-stuffs` | `/terms/` | 241 | 1 |
| `/ritual-store` | `/ritual-guru/` | 226 | 0 |
| `/swdhya-store` | `/anew/` | 212 | 1 |
| `/request-tracking` | `/orders/` | 201 | 2 |
| `/rx-slot` | `/bharat-rx/` | 188 | 3 |
| `/bring-friends` | `/refer-and-earn/` | 132 | 0 |
| `/faq` | `/contact/` | 127 | 4 |
| `/home` | `/` | 8 | 0 |
| | **subtotal** | **4,164** | **20** |

A 404 drops the URL from the index cleanly, which is a legitimate outcome — it discards the
accumulated signal instead of consolidating it onto the replacement page. That is the trade
the owner made.

### ⚠️ OWNER-DECISION ITEM 1 — `/selfservice` and `/track` are printed inside approved provider templates

These two are not ordinary retired aliases and they carry the largest single impression count
in the table. `/selfservice` is printed in the body of **DLT-approved SMS template
`ivr-default`** (registration `1007277993798259629`) as "Submit your request here: …", and in
the body of **nine approved Sinch RCS templates** including `rcsmenu`, the only one any code
sends. `/track` is in approved `wecare_order_update`.

An approved DLT body must match its registration character for character and **cannot be
edited**; an approved RCS body cannot be edited in place either. So for these two a redirect
was not a courtesy to bookmarks — it was the **only repair that exists**. They now answer 404,
which means a recipient who follows the link in a message we already sent, or send today,
reaches the missing-page document.

The removal document acknowledges this ("their old links now use missing-page behavior under
the owner's override"), so it is an accepted consequence rather than an oversight. It is
raised here because it is the one row where the cost lands on a message already in a
customer's hand rather than on a search ranking. **Reversing it is two rules and needs one
owner instruction:** `/selfservice` → `/submit-request/` and `/track` → `/orders/`, both
targets measured 200 today.

---

## 4. Domain and subdomain coverage

| Fact | Evidence |
|---|---|
| Route 53 zone `Z03939753QJGZ6ZD6BXO8` holds 30 record sets, **zero wildcards** | `list-resource-record-sets` |
| `shop` / `stack` / `app.wecare.digital` have **no address** | authoritative `ns-402.awsdns-50.com` answers NOERROR with no A/AAAA (NODATA) |
| The certificate **does** cover one label | `openssl s_client -servername wecare.digital` → `CN=wecare.digital`, SAN `wecare.digital, *.wecare.digital`, `notAfter=Mar 11 23:59:59 2027` |
| CloudFront **refuses the TLS handshake** for an unregistered host | `--resolve shop.wecare.digital:443:54.192.151.105` → `ssl_verify_result=1`; `openssl -servername shop.wecare.digital` → **TLS alert 40 handshake_failure**, "no peer certificate available". Apex through the same IP: 200 |
| Amplify registers exactly **two** subdomains | `get-domain-association`: one with no `prefix` key (branch `stack`), one `prefix: "www"`. `enableAutoSubDomain: false`, `autoSubDomainCreationPatterns: null` |

**So the gap is not a certificate gap. It is an alias/association + DNS gap**, and this task
did not close it.

### ⚠️ OWNER-DECISION ITEM 2 — wildcard subdomain coverage, NOT done

Making an unused owned subdomain land on home requires **both** of:

1. **Amplify** — add subdomain `{prefix: "*", branchName: "stack"}` via
   `update-domain-association`. AWS supports this; the prefix must be an asterisk alone, and
   partial (`*domain.example.com`) and middle (`subdomain.*.example.com`) wildcards are not
   allowed. *(Content rephrased for compliance with licensing restrictions —
   [Setting up wildcard subdomains](https://docs.aws.amazon.com/amplify/latest/userguide/wildcard-subdomain-support.html).)*
2. **Route 53** — a `*.wecare.digital` A + AAAA alias to the Amplify distribution. Additive;
   removes no existing record and touches none of MX / `_mta-sts` TXT / SPF / DMARC / DKIM /
   TLS-RPT.

**Blast radius, which is why it was written up instead of executed.** Step 1 mutates the live
domain association that currently serves the canonical home page, and can move the domain out
of `AVAILABLE` while it re-provisions — the association serving the very page this work exists
to protect. Step 2 **without** step 1 is worse than doing nothing: every mistyped subdomain
would resolve to a host CloudFront refuses at TLS, replacing today's clean no-address with a
handshake failure. Both are outside this task's authority (`amplify update-domain-association`
and DNS changes are prohibited for it), so neither was attempted.

**The genuine coverage limit: `*.wecare.digital` matches ONE label.** `a.b.wecare.digital` is
not covered. Adding a second-label host needs a new SAN, i.e. a re-requested ACM certificate
re-associated on **both** consumers of `f75d0db0-d476-443a-b787-96c4931862d2` — the Amplify
app **and** CloudFront `E1SZBXLQ4XNLJ7`, which is the MTA-STS policy endpoint under
`mode: enforce`. A failure there makes senders refuse inbound mail. Not this task's authority,
and not a change to make casually at any time.

**Two second-label hosts already exist and already miss the goal:**
`xout.wecare.digital` → Wix (`pointing.wixdns.net`), HTTP **404**, and
`www.xout.wecare.digital` → 301 → `xout.wecare.digital` → 404. Repointing them means editing
hosted-zone records for a legacy Wix surface and registering the hosts on Amplify.
**Out of scope — reported, not touched.**

`src/pages/404.tsx` already records the client-side half of this correctly and was left
as-is: a request to a subdomain that does not exist never reaches the application at all. It
fails at DNS or at the CDN before any of our HTML or JavaScript runs, so no page-level change
can address it.

---

## 5. Findings recorded, deliberately not changed

### 5.1 `_routes.json` has no consumer and is byte-identical

`_routes.json` is a 361-entry JSON array of API Gateway route keys. Grepped across the tree,
the only references are prose in four markdown/source comments; every script that needs routes
calls `apigatewayv2 get_routes` live. It is a **committed inventory snapshot, not a hosting
router** — Cloudflare's `_routes.json` convention does not apply, nothing reads it at build or
request time. Editing it cannot change any HTTP behaviour, and as a bare JSON array it cannot
carry an explanatory comment either. **Left byte-identical** (`git diff --stat _routes.json`
empty).

### 5.2 An unknown single-segment API path answers 302 → `/contact/`

```
GET https://wecare.digital/api/definitely-no-route                      302 -> /contact/
GET https://zllr9lrg7j.execute-api.../prod/definitely-no-route          302 -> /contact/
```

Cause: the HTTP API's single-segment catch-all `GET /{code}` — the short-link reader,
`stack-wecare-url-shortener` — answers a miss with a 302 to `/contact/`. That is inside a
Lambda under `amplify/functions/**`, **owned by another workstream and not touched here**. It
is not home-page HTML and not a loop, so it does not regress anything; but an unknown API path
returning a page redirect rather than JSON is worth an owner's note.
`scripts/probe_url_host_matrix.py` asserts it at its measured value so a change to it becomes
visible rather than silent.

### 5.3 `public/sw.js:180` — needs-verification-during-implementation

The service worker's push-click default destination is `/workspace/dashboard/`. **Still not
reproduced as a customer-reachable path**: it is a push-notification destination for a staff
feature, not a navigation link, and changing it could break staff push with no customer
benefit. Recorded, not changed. Closing it needs evidence that a customer can receive that
push.

### 5.4 Four unowned stale catch-all comments

The catch-all has been `/<*>` → `/404.html` at `404-200` since 2026-09-28, but five source
comments still described the older `/index.html` target. The one owned file was corrected:

```
src/pages/404.tsx:14                         CORRECTED in this change
src/pages/_app.tsx:938, 999, 1098            NOT owned — follow-up for its owner
src/pages/workspace/commerce/catalog.tsx:28  NOT owned — follow-up for its owner
```

Correcting a comment is a zero-behaviour change, but `_app.tsx` is heavily shared and outside
this task's owned paths, so the four are handed off rather than edited. The `404.tsx`
correction keeps the old reading as dated in-place history and adds what the removal changed:
with 138 redirects gone, that page is now the destination for ~150 legacy aliases rather than
a long-tail safety net.

### ⚠️ 5.5 OWNER-DECISION ITEM 3 — `provision_legacy_redirects.py --apply` will delete the host rule

## ✅ 5.5 RESOLVED — `--apply` no longer deletes the host rule (was OWNER-DECISION ITEM 3)

**Closed 2026-10-01 at ~15:54 IST, by another session, while this task was converging.** The
owner choices below were not needed; option (a) was taken.

What the hazard was, kept because the failure mode is worth remembering: the rewritten
provisioner's `is_ours()` claimed any rule whose status was in `{301,302,307,308,404}`. The
host-canonicalisation rule is a **301**, so `--apply` **removed it** — silently restoring the
duplicate-host state in which the whole site answered 200 under `www` — and `--verify` reported
`FAIL: custom redirect rules remain` and exited 1 while the rule was live. Both were measured
doing exactly that. It was left unfixed because the fix meant editing a file another session
owned and had uncommitted, plus that session's own test.

**What changed, measured not assumed.** That session rewrote `desired_redirects()` to emit the
rule rather than merely spare it, which is the stronger fix: `--apply` now **rebuilds** host
canonicalisation, so the rule is restored if it ever goes missing instead of only surviving.
Its docstring now reads "Only www canonicalisation and the retired `/access` entry point may
redirect." They also applied it to production.

| | before (this task's §0 state) | after (measured 15:55 IST) |
|---|---|---|
| live `customRules` | **9** | **12** |
| `provision_legacy_redirects.py` (no flag) | exit **1** — "1 redirects to remove" | exit **0** — "4 redirects to reconcile" |
| `provision_legacy_redirects.py --verify` | exit **1** — `FAIL: custom redirect rules remain` | exit **0** — `Verified: only approved home/access redirects remain` |
| `GET /access/` | 404 | **302 → `https://wecare.digital/`**, terminal 200 |
| `GET /workspace/access/` | 200 staff shell | **200, unchanged** — staff entry unaffected |

The three new rules are `/access`, `/access/` and `/access/<*>` → the canonical home at **302**.
That is the destination **this task's own plan asked for** (`/access` was a CONVERT prefix,
target `/` at 302, by explicit owner instruction), so the net effect is that the planned end
state landed via config-as-code. The 404 recorded in §1 for `/access` was the stale middle
state left by the redirect removal, not the goal.

**Re-verified after their production write**, because three new rules in front of the rewrites
could have shadowed a webhook: every must-not-break row still measures its expected value —
`POST /api/razorpay-webhook` 401, `POST /api/auth/validate` 401, `GET /mcp` 405, `POST /mcp`
400, `/get/o/…png` 200, `www /shop/` 301 → apex `/shop/`. No shadowing.

Two tests in this task's file were stale as a result and were **inverted rather than deleted**,
as their own docstrings instructed:

- `test_the_provisioner_would_strip_the_host_rule_KNOWN_HAZARD` →
  `test_the_provisioner_now_PRESERVES_the_host_rule`, which asserts the rule survives `--apply`,
  is **first** in the array, and that every `/api`, `/get`, `/r` and `/mcp` rewrite is preserved
  in order.
- `test_the_provisioner_still_converges_to_zero_redirects` →
  `test_the_provisioner_emits_only_the_two_sanctioned_exceptions`, which pins the approved set
  **exactly**, so a third entry fails as loudly as the second one did, and asserts no sanctioned
  rule targets `/workspace`.

`scripts/probe_url_host_matrix.py` grew the `/access` rows from 2 to 3 and now asserts them on
the **terminal URL** rather than the status alone — 200 by itself cannot distinguish the
canonical home from the staff Authenticator shell, and the shell is the thing these rows exist
to forbid.

---

## 6. Obsolete public links in the application

Audited `Header.tsx`, `Footer.tsx`, `BottomNav.tsx`, `SupportWidget.tsx`, `PageTopBand.tsx`,
`src/content/**`, the generated `llms.txt` / `sitemap.xml`, and `robots.txt`.

| Finding | Location | Outcome |
|---|---|---|
| `Header.tsx` — 15 public hrefs, all public pages | — | clean, no change |
| `Footer.tsx` — one href, `/` | — | clean, no change |
| `llms.txt` / `sitemap.xml` (1,407 `<loc>`) | — | clean; the only `access`/`sign-in` hits are blog slugs and a prose line saying `/workspace/` is out of bounds |
| **"Dashboard" button → `/workspace/dashboard`** | `src/components/ErrorBoundary.tsx:38,72` | **fixed** → `/`, relabelled "Home". It is mounted inside the `if ( isPublic )` branch of `_app.tsx`, so a customer hitting a render error on any public page was offered a button into the staff login |
| **PWA shortcuts → `/workspace/dashboard/`, `/workspace/engage/inbox/`, `/workspace/contacts/`** | `public/manifest.json` | **fixed** — the whole `shortcuts` key removed. These were the OS long-press menu entries for anyone installing the public site |
| `Layout.tsx:276` "Sign in" → `/workspace/access` | — | **not public** — `Layout`/`MaybeLayout` has zero importers outside `src/pages/workspace/`. Workspace-only chrome, left alone |
| `SearchModal.tsx:50-51`, `ui/Breadcrumbs.tsx` workspace paths | — | **not public** — imported only by `Layout.tsx`. Left alone |
| `public/sw.js:180` | — | needs-verification, §5.3 |

Guarded against regression by `src/test/PublicWorkspaceLinks.test.ts`, which also asserts the
assumption the three exemptions rest on: that no page outside `src/pages/workspace/**` imports
`Layout`, `MaybeLayout`, `SearchModal` or `ui/Breadcrumbs`.

`/workspace/` itself still returns 200 with the Authenticator shell and is `Disallow`ed in
robots.txt. **That is the legitimate staff entry and it is unchanged** — hiding a link is not
access control, and this work does not touch authorization.

---

## 7. Handoff: the return-path validator needs one line in a file this task may not edit

`src/lib/safeReturnPath.ts` and `src/test/SafeReturnPath.test.ts` are implemented and green.
`src/pages/account/sign-in.tsx` is owned by the **`src/pages/account/**` workstream** and was
not touched, so the validator has **no production caller yet**.

The two gaps it closes are real and were measured against the current regex
`/^\/[a-zA-Z0-9/_-]*\/?$/`:

| input | current regex | consequence |
|---|---|---|
| `//evil` | **accepted** — every character is in the class | protocol-relative; the browser reads `evil` as the HOST |
| `/workspace/access` | **accepted** | sends a customer to a staff destination after sign-in |

**Ready to apply, verbatim.** In `returnPathFromUrl()` (currently `sign-in.tsx:170-175`),
replace line 174:

```ts
return /^\/[a-zA-Z0-9/_-]*\/?$/.test( raw ) ? raw : '/cart/';
```

with:

```ts
return safeLocalReturnPath( raw );
```

and add the import alongside the other `src/lib` imports:

```ts
import { safeLocalReturnPath } from '../../lib/safeReturnPath';
```

The line above it and the `typeof window === 'undefined'` early return both stay —
`safeLocalReturnPath` accepts `null`/`undefined`/`''` and returns `'/cart/'`, so the `.trim()`
and `|| ''` become belt-and-braces rather than load-bearing. **Also replace the comment on
line 173** ("Only same-site absolute paths, so this can never be turned into an open
redirect") — that is the claim the two rows above falsify.

**Two behaviour changes the `account/**` owner must accept first:** (1) a local path outside
the allowlist (e.g. `/blog/`) now returns `/cart/` rather than being honoured; (2) an
unslashed accepted path is normalised (`/cart` → `/cart/`) rather than returned as typed.

### ⚠️ OWNER-DECISION ITEM 4 — two allowlisted destinations have no page, measured 2026-10-01

Found by the convergence step, by probing every value the validator can return against the
live site rather than reading the list. **Two of the six answer 404:**

| returnable value | live (measured) | page source |
|---|---|---|
| `/` | 200 | `src/pages/index.tsx` |
| `/cart/` | 200 | `src/pages/cart.tsx` |
| `/orders/` | 200 | `src/pages/orders.tsx` |
| `/shop/` | 200 | `src/pages/shop/index.tsx` |
| **`/checkout/`** | **404** | **none** — `src/pages/checkout/` holds only `status.tsx` and `success.tsx` |
| **`/account/`** | **404** | **none** — `src/pages/account/` holds only `sign-in.tsx` |

`output: 'export'` emits a page only where a source file exists, so neither has anything to hit
but the `/<*>` → `/404.html` catch-all. This is **not** a security defect — both are local,
on-allowlist paths — but it defeats the module's stated contract: it "returns the value to use",
and two of those values cannot be navigated to.

**Why it is recorded rather than fixed.** The allowlist was specified verbatim by the task plan
(§2 step 1) and FEAT-001 implemented it faithfully; the mismatch is between that list and the
page inventory, and it only became visible once both halves of the task were measured together.
The two candidate resolutions — narrow `ALLOWED`, or ship the two missing pages — are both
product decisions, and `src/pages/account/**` is this other workstream's to edit. **Nothing
outside its own test imports the function**, so the gap cannot reach a customer today; it
reaches one the moment the wiring above is applied. Hence: a precondition on that wiring, not a
discovery left for the person doing it.

Pinned by `src/test/SafeReturnPath.test.ts` →
`'safeLocalReturnPath — accepted destinations that do not resolve (KNOWN GAP)'`, which asserts
the current measured truth, including a test that **fails as soon as a production caller
appears**. Same convention as §5.5: when it is resolved, **invert the test, do not delete it**.

---

## 8. Rollback

**Amplify exposes no ETag** for `get-app`/`update-app` — unlike `cloudfront
update-distribution`, there is no concurrency token to present, so the committed snapshot plus
the script's own timestamped `.scratch/` artefact are the whole safety net. Recorded here
rather than inventing a token.

`update-app` is a **full replace** of `customRules`. Any rollback must start from a fresh
`get-app`, never from a stale in-memory array, or a concurrent session's rules are silently
dropped.

To undo **only this task's change** (remove the host-canonicalisation rule, returning to the
8-rule post-removal state):

```
aws amplify update-app --app-id d22dm4b0jn71jw --region us-east-1 \
  --custom-rules file://docs/execution/snapshots/amplify-custom-rules-before-url-host-cleanup-20261001.json
```

The post-change array is committed alongside it as
`docs/execution/snapshots/amplify-custom-rules-after-url-host-cleanup-20261001.json` (9 rules),
so before and after are both on disk and diffable.

**Do not** restore `amplify-custom-rules-before-owner-removal-20261001.json` (146 rules) to
undo this change — that reverses the owner's removal as well, recreating every retired alias,
and needs a new owner instruction. **Do not** restore
`amplify-custom-rules-before-8.4.json`; it holds the three rules the app had on 2026-09-24 and
restoring it would delete the `/mcp`, `/get/<*>` and `/api/<*>` passthroughs — a far larger
outage than anything it could revert.

---

## 9. Verification run on the exact tree

| Gate | Result |
|---|---|
| `npm run typecheck` | exit 0 |
| `npm run lint` | exit 0 — **0 errors**, 188 warnings, all pre-existing (the repo baseline is "errors 0"; the count did not move) |
| `npx vitest run` | exit 0 — 47 files, **674 tests passed** |
| `npm run build` | exit 0 — static export succeeded; `out/404/index.html` present (36,567 bytes); `out/sitemap.xml` holds **1,407 `<loc>`**, unchanged; 1,400/1,407 dated across 9 distinct days |
| `pytest tests/test_url_host_routing_rules.py tests/test_legacy_redirect_rollback_snapshot.py -q` | **14 passed** |
| `scripts/probe_url_host_matrix.py` | **85 rows, 0 failed, exit 0**, no loops |
| `scripts/retired_url_probe.py` | **exit 0** — no retired URL answers 200. Worth noting: this pre-existing guard holds `"https://www.wecare.digital/": "www must 301 to the apex"`, so between the removal and this change it was **failing** on that row (a 200 classifies as `STILL-LIVE`, exit 1). It is green again now. Independent confirmation that the host rule was genuinely missing, from a file this task did not write |
| `scripts/provision_legacy_redirects.py` (no flag) | exit 1 — reports `9 rules; 1 redirects to remove` naming the host rule, §5.5 |
| `scripts/provision_legacy_redirects.py --verify` | **exit 1 by design** — `FAIL: custom redirect rules remain`, naming the host rule, §5.5 |
| `git diff --stat _routes.json` | empty |

Measured values are recorded in the matrix in §1 rather than repeated here. A command exiting
0 is not evidence of success, which is why every row of §1 carries a probed status rather than
an expectation — and why the two non-zero exits above are reported as predicted behaviour with
their cause, instead of being quietly omitted.

**No DNS record, ACM certificate, CloudFront distribution, domain association, WAF or Security
Hub setting was created, modified or deleted.** No secret value was read; no credential appears
in any command or log in this record. The only production write was the single `update-app`
documented in §0.

### 9.1 Convergence re-run — independent cross-FEAT confirmation, 2026-10-01

The whole gate set was re-run on the merged tree, and the must-not-break set was re-measured
with `curl` rather than with the task's own probe harness, so a bug in that harness could not
vouch for itself. **Every row matched.**

| Gate | Convergence result |
|---|---|
| `npm run typecheck` | exit 0 |
| `npm run lint` | exit 0 — 0 errors, 188 warnings, count unmoved |
| `npx vitest run` | exit 0 — 47 files, **677 tests** (674 + the 3 KNOWN GAP tests in §7) |
| `npm run build` | exit 0 — `out/404/index.html` present, `out/sitemap.xml` **1,407 `<loc>`** |
| `pytest …routing_rules …rollback_snapshot -q` | **14 passed** |
| `scripts/probe_url_host_matrix.py --json` | **probed 86, failed 0**, exit 0 (85 → 86: the third `/access` wildcard row, §5.5) |
| `scripts/retired_url_probe.py` | exit 0 — 24 rows, 21 `OK-gone` + 3 `OK-redirect`, none still live |
| `scripts/provision_legacy_redirects.py` / `--verify` | **exit 0 / exit 0** — both were exit 1 earlier in this same run; the §5.5 hazard was fixed mid-convergence and `--verify` now reports `Verified: only approved home/access redirects remain` |
| `git diff --stat _routes.json` | empty |

Independently re-measured with `curl` (not via the harness):
`POST /api/razorpay-webhook` **401** · `POST /api/auth/validate` **401** ·
`POST /api/payments/webhook` **404** · `GET /api/webhook/sinch-rcs` **200** ·
`GET /mcp` **405** · `POST /mcp` **400** ·
`GET /get/o/stream/media/m/wecare-digital.png` **200** ·
`GET /definitely-not-a-page/` **404** carrying `"page":"/404"` and `robots: noindex, follow` ·
`https://www.wecare.digital/shop/` **301 → `https://wecare.digital/shop/`**, terminal **200**,
path preserved · `/workspace/` **200** with the Authenticator shell (`data-amplify`,
`authenticator` markers present in the body) · `/account/sign-in/` **200** ·
`/shop/ /cart/ /orders/ /blog/ /404/` all **200**.

One seam was found between the two features and is recorded as **§7 OWNER-DECISION ITEM 4** —
two allowlisted post-sign-in destinations have no exported page. Nothing else in either feature
conflicted: FEAT-002's correction to `src/pages/404.tsx` left FEAT-001's
`NotFoundFallback.test.ts` assertions intact, and FEAT-001's `ErrorBoundary` repoint to `/`
lands on a page measured at **200**.

### 9.2 The tree moved during this run, and that is why the numbers above differ from §0

Worth recording as a shared-tree fact rather than hidden behind a final green result. The first
pass of this convergence run measured 9 live rules, `pytest … -q` **14 passed**, and the two
provisioner exits at **1**. Forty minutes later, with no edit of mine in between, the same
pytest command reported **2 failed** — another session had rewritten
`scripts/provision_legacy_redirects.py` (mtime 15:54:03) and applied it to production.

The two failures were the task's own cross-file alarms firing exactly as designed: one because
`desired_redirects()` stopped returning `[]`, the other because the KNOWN HAZARD it pinned had
been fixed. Neither was a regression, and the fix for both was written into their own
docstrings in advance — **invert, do not delete**. That is the whole argument for pinning a
known defect with a named test instead of a comment: a comment would have been silently
outdated, and a deleted test would have left the reconciliation unverified.

The lesson for the next reader: **re-measure, do not re-use.** Every count in §0 is timestamped
for this reason, and §1 carries probed statuses rather than expectations.
