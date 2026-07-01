# Frontend Full Audit — gaps & improvements (fresh, complete)

Supersedes the structural-only `FRONTEND_DUPLICATION_AUDIT.md`. Covers the home/public pages,
per-page completeness (real vs stub vs mock), reachability, accessibility, and improvements.
~120 route pages under `src/pages`.

## A. Home / public landing (`src/pages/index.tsx`) — was skipped before
Substantial, SEO-rich, mobile-optimized marketing page. But real gaps:
1. **No functional CTAs** — the hero and `.cta-section` are headings only; there is **no Get Started / Login / Sign Up / Book Demo button anywhere**. A landing page with zero conversion action.
2. **No header nav and no footer** on the public page — no logo bar, no login link, no company/legal/privacy/contact links. Users can't navigate or reach the app.
3. **Fake review schema** — hardcoded `aggregateRating 4.8 / ratingCount 150` in JSON-LD. Google can penalize/ignore fake review markup. Remove or make real.
4. **`foundingDate: 2020`** in Organization schema, but the business/account is 2026. Inaccurate structured data.
5. **Marketing API examples** reference `api.wecare.digital/v1/...` — verify that public API exists, else it's misleading.
6. **Vague stat placeholders** — "B+ Users reachable", "Fast", "Secure" (not real numbers).
7. **Fake interactivity** — usecase "pills" are `<button>` with `cursor:default` and no handler; should be real filters or `<span>`.

Other public pages: `faq.tsx` (root, not in nav), `studio`, `carbon`, `sustainability`, `nocode` — see stubs below.

## B. Stub / "Coming Soon" / placeholder pages (shipped but not real)
Confirmed by reading source:
| Page | Evidence |
|---|---|
| `task/` | renders `<ComingSoon>` component |
| `nocode/` | `<EmptyState … "coming soon">` |
| `studio/` | static "Coming soon" text |
| `carbon/` | `<EmptyState … "coming soon">` |
| `sustainability/` | (same pattern — verify) |
| `contact-test/` | test/dev page, not production |
→ These ship as real routes and (`task`) appear in the sidebar with a "Soon" badge. **Recommendation:** remove from build/nav until real, or gate behind a feature flag. Shipping empty routes hurts UX and SEO.

## C. Real, well-built pages (leave them)
`index` (home, needs CTA fixes), `store/` (full Wix CRUD — products/orders/collections/bulk),
`dm/channels/` (clean launcher hub), `dm/inbox` (unified cross-channel), `dm/whatsapp/*` (deep feature set),
`seo/*` (functional tools), `pay/*`, `service/*`, `contacts/`, `forms/`, `link/`. These use the shared
`Layout`, `Tabs`, `Table`, `EmptyState`, `Spinner`, toast, and `api/client.ts` — good consistency.

## D. Reachability (corrected)
- `dm/channels` is a launcher hub that links to `/dm/logs` (unified), `/dm/rcs/send`, `/dm/ses/inbox`, etc.
  So the per-channel subpages and `dm/logs` ARE reachable via the hub (not fully orphaned) — but they're
  **still duplicates** of the unified `dm/inbox` / `dm/broadcast` / `dm/logs`.
- **Genuinely orphaned** (not in nav, not linked from channels hub) → verify/remove: `admin/` (root),
  `dashboard/admin` (redirect only), `dashboard/cors-settings`, `dashboard/order-notifications`,
  `dm/orders`, `dm/whatsapp/scripts`, `seo/pages-manager` (dup of `seo/pages`), `crm/`, `contact-test`,
  root `faq` (unless intentionally public).

## E. Duplication (from the structural audit, still open)
Inbox ×4, Campaign ×4, Logs ×4, Templates ×3, Usernames ×2, Flows ×4, SEO management ×6, Contacts ×3.
Root cause: channel-by-channel build + a unified `dm/*` layer added on top without retiring originals.
Target ~120 → ~70–80 pages.

## F. Accessibility & UX gaps (cross-cutting)
- **Landing page**: interactive `<button>`s with no action + `cursor:default` (confuse screen readers / keyboard users); no skip-link; decorative empty `<span>` badges without `aria-hidden`.
- **Inline styles everywhere** (store, channels use big inline style objects) — no theming/contrast tokens consistently; harder to guarantee WCAG contrast. `design-tokens`/`colors` exists but isn't used uniformly.
- **Color-only status** — order/payment statuses in `store` use color to convey meaning (and several map to the same `#1a3a2a`), no text/icon differentiation → fails color-contrast/again color-only guidance. Note: several status colors are identical (a bug — PAID/NOT_PAID both `#1a3a2a`).
- **Loading/empty states**: good in `store`/`channels` (Spinner + EmptyState); verify consistency across all list pages.
- **Error handling**: `store` swallows errors to `console.error` (no user-facing toast on fetch failure) — should surface via toast context.

## G. Prioritized action list
### P0 (quick, high value)
1. **Home page CTAs + header/footer** — add Login/Get-Started buttons, a top nav, and a footer with legal links. Biggest conversion + navigation gap.
2. **Remove fake review schema** + fix `foundingDate` on the landing (SEO risk).
3. **De-list / remove stub pages** (`task`, `nocode`, `studio`, `carbon`, `sustainability`, `contact-test`) or feature-flag them.
4. **Fix status-color bug** in `store` (PAID/NOT_PAID rendered same color).

### P1 (consolidation — the maintainability win)
5. Retire per-channel inbox/campaign/logs in favor of unified `dm/*`; update `dm/channels` links accordingly.
6. Merge SEO management page variants into one tabbed manager; delete `seo/pages-manager` dup.
7. Remove genuinely-orphaned pages (section D) after confirming no deep links.

### P2 (structural quality)
8. **Shared channel component**: one `<ChannelInbox channel=…>` / `<ChannelLogs>` so channels never re-fork.
9. **Design-token adoption**: replace ad-hoc inline hex with `design-tokens` for WCAG-safe contrast + theming.
10. **Consistent fetch error → toast** pattern across all list/detail pages.

## Top 10 findings (summary)
1. Landing has **no CTA / login / header / footer** — can't convert or navigate.
2. **Fake `aggregateRating` schema** on landing — SEO penalty risk.
3. **6 stub "coming soon" pages** shipped as routes (`task` even in the sidebar).
4. `store` **status colors identical** for PAID/NOT_PAID (bug) + errors only logged, not toasted.
5. Massive **channel duplication** (inbox/campaign/logs ×4 each).
6. **SEO section** has ~6 near-duplicate management pages.
7. **Orphaned pages** (`admin`, `crm`, `dm/orders`, `seo/pages-manager`, `cors-settings`, …).
8. **Inline styles over design tokens** → inconsistent, contrast risk.
9. `foundingDate 2020` inaccurate structured data.
10. No **shared channel abstraction** → duplication will keep recurring.
