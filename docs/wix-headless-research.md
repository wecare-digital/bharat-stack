# Wix Headless, self-hosted — findings

Research task 08. Written 2026-09-23. **No code changed for this.**

The question was whether WECARE.DIGITAL should move to Wix Headless with a
self-hosted frontend. Short answer: **it would fix the single worst thing about the
current setup and would not fix the second worst, and one hard constraint decides
whether it is viable at all.** Details below, grounded in what this repo actually does
today rather than in the general case.

## Where we already are

This is not a greenfield decision — the repo is already a partial headless client:

| Surface | What it does | Files |
|---|---|---|
| Wix REST API | Products, orders, collections, inventory, site-media upload | `amplify/functions/ecommerce/wix-store/handler.py` |
| Wix Blog API | Creates and patches draft posts, writes `seoData.tags` | `scripts/wix-blog-schema-api/` |
| SEO tooling | Reads and rewrites page SEO | `amplify/functions/operations/seo-tools/wix.py` |
| Velo code | 36 files of in-platform backend/frontend code | `store/src/`, `shared/wix-velo/` |
| Next.js store page | Renders our own store UI against those APIs | `src/pages/store/index.tsx` |

Auth today is an **API key** from Secrets Manager (`wecare/wix-api-key`) plus
`WIX_SITE_ID` / `WIX_ACCOUNT_ID` — `handler.py:38-80`.

> **Superseded.** This paragraph used to name the site as
> `c17b0e20-d96d-4fa1-b05c-bc97c04b4ac5`, sourced from `store/wix.config.json`. That file no
> longer exists in the repo, and that id belongs to the **retired editor site**. The headless
> site is `fcd82f0c-9572-49c7-acfb-88fb05042ece`, supplied by the owner. The single source of
> truth is [`src/config/wix.ts`](../src/config/wix.ts) — prefer it over this research note,
> which is a point-in-time document.

So "should we go headless" is really **"should we finish going headless, and retire
the Velo layer"**.

## The one constraint that decides it: checkout

**You cannot build your own checkout.** Wix requires a redirect to a Wix-hosted
checkout page via the Redirects API — this is stated directly in their own headless
docs, not inferred:

- [Redirect Using the JS SDK](https://dev.wix.com/docs/go-headless/business-solutions/wix-hosted-pages/redirect-using-the-js-sdk) — taking advantage of Wix checkout requires redirecting to a Wix-hosted page.
- [About Wix-Hosted Pages](https://dev.wix.com/docs/go-headless/business-solutions/wix-hosted-pages/about-wix-hosted-pages) — flows needing a UI, such as checkout or booking, are offered as Wix-hosted pages instead of ones you build.
- [Wix Site Migration to a Headless Project](https://dev.wix.com/docs/go-headless/self-managed-headless/get-started/migrate-from-an-existing-wix-site/about-wix-site-migration-to-a-headless-project) — during those flows the served domain becomes a Wix subdomain, e.g. `checkout.example.com`.

Consequences that matter to us specifically:

1. **The visitor leaves our domain mid-purchase.** It can be dressed as
   `checkout.wecare.digital` via [a custom subdomain](https://dev.wix.com/docs/go-headless/business-solutions/wix-hosted-pages/set-a-domain-for-wix-hosted-pages), but it is a different origin and a different page we do not control.
2. **Every return URL must be pre-registered** as an allowed redirect domain
   ([docs](https://dev.wix.com/docs/go-headless/getting-started/setup/manage-urls/allowed-redirect-domains)), so preview deploys and branch URLs need managing.
3. **A misconfigured subdomain silently breaks payment.** A community thread shows a
   redirected-domain assignment forwarding to the primary domain instead of serving
   the checkout ([forum](https://forum.wixstudio.com/t/ticketing-payment-headless-website-invalid-redirect/79718/2)).
4. It caps how far the Grahak OS conversational-commerce idea can go — an in-WhatsApp
   purchase still has to hand off to a Wix page.

An independent review frames this as the platform's defining trait rather than a gap:
a closed hosted SaaS where checkout is a locked component and catalogue caps apply per
plan ([swell.is, Nov 2025](https://www.swell.is/content/wix-ecommerce-limitations)).
Treat the catalogue-cap claim as needing verification against our actual plan — we
have 6 products, so it is not currently binding either way.

**If owning checkout is a requirement, stop here — Wix Headless cannot do it.**

## What it would genuinely fix: SEO

This is the strong argument for moving, and it comes from our own audit rather than
from Wix. `seo/audit/wix-api-capability-map.md` records that across the site:

- Blog posts (108) — full SEO control via API ✅
- Dynamic/router pages — full control via Velo ✅
- **Static pages (37) — no API at all.** Title, description, JSON-LD, canonical, OG,
  robots: every one is manual, per page, in the Wix dashboard.
- **Products (6) — no JSON-LD API.** Dashboard SEO panel only.
- **Collections, categories, tags, homepage, booking pages — no API.** All manual.

That is a large, permanent, manual burden, and it is the thing a self-hosted frontend
removes completely: we would own `<head>` for every page in Next.js, where this repo
already has `SEO.tsx`, JSON-LD blocks in `_app.tsx`, a generated sitemap and a
canonical convention. The 37 static pages stop being dashboard work.

**One important caveat, and it cuts the other way.** Wix's own path comparison says
that on the self-managed route you create the client and set up auth yourself, and
**extensions and built-in SEO support are not available**
([Choose Your Development Path](https://dev.wix.com/docs/go-headless/get-started/choose-your-development-path)).
Read that carefully: it means Wix stops *helping* with SEO, not that SEO becomes
impossible. For us that is the point — their help is what we cannot reach by API. For
a team without a frontend that owns `<head>`, it would be a downgrade.

## What it would not fix

- **The dependency vulnerabilities.** `store/` reports **7 findings (1 critical, 4
  high, 2 low)** and the handoff already records that they all come from `@wix/cli`
  with `1.1.247` the latest published version — nothing to upgrade to. Going headless
  *self-managed* would let us delete the `@wix/cli` dev dependency along with the Velo
  project, which removes those 7 findings by removing the package. That is a real
  benefit, but it comes from retiring Velo, not from Headless itself.
- **The Velo rewrite cost.** 36 files under `store/src/` and `shared/wix-velo/`,
  including convenience-fee logic, order-number handling and event hooks, would have
  to be reimplemented as Lambdas. That is the bulk of the migration effort and none of
  it is mechanical.

## Cost

Wix's own material states Headless is free to connect, with no per-feature charge, no
API fees and no enterprise tier, and a CMS with no content cap
([pricing post](https://www.wix.com/blog/how-much-does-wix-headless-cost),
[Headless overview](https://www.wix.com/blog/wix-headless)). They also advertise SOC 2
Type II, HIPAA and GDPR compliance ([Go Headless docs](https://dev.wix.com/docs/go-headless)).

**These are vendor claims on vendor domains and should be confirmed against the actual
account before being used in a decision.** "Free to connect" plainly does not mean the
underlying Stores/Bookings plan is free, and payment processing fees are separate.

*Content on this page was rephrased from the linked sources for compliance with
licensing restrictions.*

## Recommendation

**Finish the headless migration for content and SEO. Keep Wix checkout. Retire Velo
last, or not at all.**

Sequenced so each step stands alone:

1. **Confirm the checkout constraint is acceptable.** Owner decision, and everything
   else depends on it. If not acceptable, this whole direction is dead and the real
   question becomes which commerce platform replaces Wix.
2. **Move auth from API key to OAuth/visitor tokens** where a browser is involved. An
   API key is an account-level credential and must never reach a client; it is
   correctly server-side today in `handler.py`, and that property must not be lost
   when a frontend starts calling Wix directly.
3. **Take over `<head>` for the 37 static pages** by rendering them from Next.js. This
   is the highest-value step and is independent of checkout and of Velo.
4. **Register `checkout.wecare.digital`** as the Wix-hosted-pages domain and add every
   environment's return URL to allowed redirect domains.
5. **Only then** consider porting the 36 Velo files, which is what unlocks deleting
   `@wix/cli` and its 7 findings.

## Open questions for the owner

1. Is leaving `wecare.digital` for checkout acceptable, even as
   `checkout.wecare.digital`?
2. Does the current Wix plan have a catalogue cap, and what is it? 6 products today,
   but it constrains the roadmap.
3. Should Grahak OS ever take payment in-conversation? If yes, Wix checkout is a
   ceiling and this should be designed around now rather than later.
4. Is the 37-page manual SEO burden currently being paid by someone, and how often?
   That number is the actual return on step 3.
