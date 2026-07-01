# Consolidated Frontend Report — WECARE.DIGITAL

Single source of truth for the frontend: home page, pages inventory, stubs, duplication, a11y,
build/deploy (IaC), and a phased roadmap. Consolidates: FRONTEND_FULL_AUDIT + FRONTEND_DUPLICATION_AUDIT.
Next.js 16.2 (static export) · Amplify Hosting app `d22dm4b0jn71jw` · branch `stack`.

---
## 1. Build / deploy (IaC & pipeline)
- **Static export** (`output: export`) → no SSR/middleware at runtime (neutralizes the Next SSR CVE).
- **Amplify Hosting** builds on push to `stack` (`amplify.yml`: `npm install --legacy-peer-deps` → `next build`). Uses `npm install`, **not** `npm ci` (bundled aws-cdk deps make `npm ci` fail — by design).
- **`turbopack.root` pinned**; `next-env.d.ts` gitignored.
- **Gaps:** no **Amplify build-failure alarm** (add EventBridge rule → SNS); consider **branch protection** on `stack`.

## 2. Home / public landing (`index.tsx`)
Substantial, SEO-rich, mobile-optimized — but real gaps:
1. **No functional CTA** (no Get Started / Login / Sign Up); hero + CTA are headings only.
2. **No header nav, no footer** on the public page — no login path, no legal/contact links.
3. **Fake review schema** (`aggregateRating 4.8/150`) → SEO penalty risk.
4. **`foundingDate 2020`** but business is 2026 — inaccurate structured data.
5. `api.wecare.digital/v1` examples (verify exists); vague stat placeholders; dead `<button>` pills.

## 3. Pages inventory (~120 routes)
- **~79 linked** in the sidebar (`src/config/navigation.ts`); rest reached via `dm/channels` hub or orphaned.
- **Stub / "Coming Soon" shipped as routes:** `task` (in sidebar w/ "Soon"), `nocode`, `studio`, `carbon`, `sustainability`, `contact-test`. → remove or feature-flag.
- **Real, well-built:** `store` (Wix CRUD), `dm/channels` (hub), `dm/inbox` (unified), `dm/whatsapp/*`, `seo/*`, `pay/*`, `service/*`, `contacts`, `forms`, `link`.
- **Genuinely orphaned (remove after link-check):** `admin/`, `dashboard/admin` (redirect), `dashboard/cors-settings`, `dashboard/order-notifications`, `dm/orders`, `dm/whatsapp/scripts`, `seo/pages-manager` (dup), `crm/`, `contact-test`.

## 4. Duplication (channel-by-channel + unified layer never retired)
Inbox ×4 (`dm/inbox` vs `whatsapp/rcs/ses` inboxes) · Campaign ×4 · Logs ×4 · Templates ×3 · Usernames ×2
(`waba-usernames` vs `bsuid`) · Flows ×4 · SEO management ×6 · Contacts ×3.
Root cause: **no shared channel abstraction** + unified `dm/*` added on top without deleting originals.
Target **~120 → ~70–80** pages.

## 5. Bugs & accessibility
- **`store` status colors:** PAID and NOT_PAID render the **same** `#1a3a2a` (copy-paste bug) — indistinguishable; also color-only status (a11y).
- **`store` fetch errors** only `console.error`'d — no user toast on failure.
- **Inline hex styles** instead of `design-tokens` → inconsistent, contrast risk.
- Landing: dead `<button>`s, no skip-link, decorative spans without `aria-hidden`.

## 6. Phased roadmap (autopilot-safe vs gated)
### Phase 1 — safe / high value
1a. Home: add CTAs + header nav + footer (login/legal). *(gated: real UI change, but low risk)*
1b. Remove fake review schema + fix `foundingDate`. *(autopilot-safe)*
1c. De-list/remove the 6 stub pages (or feature-flag). *(autopilot-safe)*
1d. Fix `store` status-color bug + add fetch-error toast. *(autopilot-safe)*
1e. Add Amplify build-failure alarm (IaC). *(autopilot-safe, additive)*

### Phase 2 — consolidation (maintainability)
2a. Retire per-channel inbox/campaign/logs → unified `dm/*`; update `dm/channels` links.
2b. Merge SEO management variants into one tabbed manager; delete `seo/pages-manager`.
2c. Remove orphaned pages (§3) after confirming no deep links.

### Phase 3 — structural quality
3a. **Shared channel component** (`<ChannelInbox channel=…>` / `<ChannelLogs>`) so channels never re-fork.
3b. **Design-token adoption** (replace ad-hoc inline hex → WCAG-safe contrast + theming).
3c. Consistent **fetch-error → toast** pattern across all list/detail pages.

## 7. Autopilot guidance
- **Autopilot OK:** 1b, 1c, 1d, 1e (schema fix, stub removal, bug fix, additive alarm) — low risk, verifiable by build.
- **Supervised:** 1a (home redesign), Phase 2 (page retirement — confirm no deep links first), Phase 3 (refactors).

## 8. Recommended order
Phase 1 (this week; start home CTA/header/footer + fake-schema removal) → Phase 2 consolidation (inbox/logs/campaign trio first) → Phase 3 shared component + tokens.
