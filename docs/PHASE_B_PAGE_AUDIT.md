# Phase B — Inner Page Audit & Design-Token Rollout Plan

> Deep scan of all inner pages under `src/pages/`. Purpose: group pages, identify
> consolidation (tabbed hubs) and deprecation candidates, and sequence the
> design-token migration by effort.
>
> **Effort signal:** `hex` = count of hardcoded `#rrggbb` colors in the file (these
> must move to `design-tokens.ts` / `var(--token)`). `lines` = file size.
> Foundation already shipped: `src/lib/design-tokens.ts` + `src/styles/tokens.css` v4.

## Summary

- **~97 page files** scanned (`src/pages/**/*.tsx`).
- **Already token-clean / low effort:** most pages use shared CSS classes; ~40 have <10 hardcoded colors.
- **Consolidation opportunities:** RCS, Email (SES), SEO, Link, Forms, Service, and some Dashboard pages can collapse into tabbed hubs using the existing `PageShell` pattern (as WhatsApp Settings already does with 17 tabs).
- **Deprecation candidates:** 1 dead duplicate (`[waId].tsx`, 1609 lines), 1 likely test page (`contact-test`), 4 redirects, 5 coming-soon stubs, 1 removed-feature notice.

---

## 1. Page groups (current information architecture)

### A. Dashboard & Admin
| Page | lines | hex | Notes |
|---|---|---|---|
| `dashboard/index` | 3873 | 596 | ⚠️ Largest page + highest hex. Top migration target. Likely should split into tab components. |
| `dashboard/system-architecture` | 1780 | 48 | "Control Center". Big but low hex. |
| `dashboard/wa-auto-response` | 861 | 65 | |
| `dashboard/lambda-functions` | 300 | 69 | |
| `dashboard/waba-usernames` | 373 | 4 | Fold into Control Center tab. |
| `dashboard/order-notifications` | 248 | 14 | Fold into Control Center tab. |
| `dashboard/cors-settings` | 164 | 16 | Fold into Control Center tab. |
| `dashboard/code-repo` | 234 | 28 | |
| `dashboard/design-reference` | 1628 | 168 | hex is intentional (color swatches); already imports tokens. |
| `dashboard/admin` → redirect | 12 | 0 | Redirect to system-architecture. Keep. |
| `admin/index` → redirect | 11 | 0 | Redirect. Keep. |

### B. WhatsApp (already well-consolidated ✅)
- `dm/whatsapp/index` (24) → renders `inbox`.
- `dm/whatsapp/inbox` (1831, hex 30) — standalone, largely token-clean (we've been working here).
- `dm/whatsapp/settings` (177) — **hub** embedding 17 tabs via `PageShell`: waba-dashboard, templates, welcome, campaign, logs, interactive-lists, flows, calling, groups, business-profile, webhooks, ai-config, auto-response, scripts, flow-responses, flow-hub, migration.
- Heavy sub-pages to migrate: `templates` (2179/60), `calling` (1909/296), `waba-dashboard` (1025/33), `flow-hub` (626/127).
- `dm/whatsapp/ai-config` (42) — **removed feature** notice (kept as tab). Consider hiding.
- `dm/whatsapp/[waId]` (1609) — ❌ **DEAD** duplicate of inbox (no inbound links). Delete after porting its MediaRecorder voice-note recorder into `inbox`.

### C. Other messaging channels
| Channel | Pages | Recommendation |
|---|---|---|
| SMS | `dm/sms` (813/68) | Standalone; migrate. |
| Voice | `dm/voice` (348/51), `dm/voice-in` (1048/131) | Consider a Voice hub (outbound + inbound/OBD tabs). |
| Email (SES) | `ses/index` (45), `ses/inbox` (263/19), `ses/campaign` (132), `ses/logs` (268/55) | **Consolidate** into an Email hub (Inbox + Campaign + Logs tabs). |
| RCS | `rcs/index` (51), `rcs/inbox` (273/16), `rcs/campaign` (133), `rcs/send` (116/17), `rcs/logs` (119/7), `rcs/templates` (207/24) | **Consolidate** into an RCS hub (Inbox + Send + Campaign + Templates + Logs tabs). |
| Push | `dm/push` (460/56) | Standalone; migrate. |
| Logs | `dm/logs` (313/27) | Cross-channel logs; keep. |

### D. Commerce & operations

> **Backend-verified (deep scan):** the pages below split into TWO distinct backends.
> Do **not** merge Orders into Store — they are different systems that merely share the word "orders".

**D1. Service Operations — ONE backend (`wecare-whatsapp-business-api`, all `/wa-business/*`, WhatsApp-Flow driven).**
The `/dm/orders` page is the **orchestrator**: its detail panel aggregates flow submissions + documents + tracking + status history. The others are flow submission types tied to it. → Group as one cluster with **Orders as the landing page**.

| Page | API base | lines/hex |
|---|---|---|
| `dm/orders` (hub) | `/wa-business/orders` | 524/73 |
| `service/submit-request` | `/wa-business/service`, `/submit-requests` | 300/29 |
| `service/track-request` | `/wa-business/...` | 238/51 |
| `service/amend-request` | `/wa-business/...` | 257/36 |
| `service/index` | — | 57 |
| `dm/appointments` | `/wa-business/appointments` | 185/29 |
| `dm/rx-slots` | `/wa-business/rx-slots` | 165/19 |
| `dm/documents` (Drop Docs) | `/wa-business/documents` | 286/33 |
| `dm/enterprise` | `/wa-business/enterprise-assist` | 205/39 |
| `dm/reviews` | `/wa-business/reviews` | 187/21 |
| `dm/whatsapp/flow-hub`, `flow-responses` | `/wa-business/flows`, `/flow-data` | 626/127, 373/37 |

**D2. Store — SEPARATE backend (`/wix-store`, Wix e-commerce). Already an internal hub.**
| Page | Contains | lines/hex |
|---|---|---|
| `store/index` | Products + **Wix Orders** + Collections (internal tabs) | 941/159 |

**D3. Pay / Contacts (independent backends).**
| Pay | `pay/index` (36), `pay/flow` (841/27), `pay/link` (284/19) |
| Contacts | `contacts/index` (1408/203) — ⚠️ high hex, standalone |

**D4. FAQ** — `dm/faq` (170/8): admin FAQ management (own backend `/faq`), standalone.

### E. Tools & platform
| Group | Pages |
|---|---|
| Access | `access/index` (52/2) — auth/access landing |
| Link | `link/index` (324/17), `link/create` (33), `link/logs` (33) → **hub candidate** |
| Forms | `forms/index` (18), `forms/create` (35), `forms/logs` (33), `forms/selfservice` (221/22) → **hub candidate** |

### F. SEO (17 pages — biggest flat group, strongest consolidation case)
| Page | lines | hex |
|---|---|---|
| `seo/index` | 119 | 10 |
| `seo/pages` | 124 | 11 |
| `seo/pages-manager` | 749 | 218 |
| `seo/site-pages` | 93 | 23 |
| `seo/product-pages` | 212 | 96 |
| `seo/system-pages` | 207 | 91 |
| `seo/blog-manager` | 362 | 112 |
| `seo/issues` | 91 | 11 |
| `seo/analytics` | 78 | 5 |
| `seo/tracking` | 47 | 6 |
| `seo/schema` | 48 | 6 |
| `seo/properties` | 70 | 4 |
| `seo/sitemaps` | 54 | 2 |
| `seo/tools` | 459 | 4 |
| `seo/system-pages` (dup concept) | — | — |
| `seo/InstructionsContent` | 290 | 12 (component, not a route) |
| `seo/page/[id]` | 194 | — |

⚠️ **Duplication flag:** `pages` vs `pages-manager` vs `site-pages` vs `product-pages` vs `system-pages` overlap conceptually. Recommend a single **SEO hub** with tabs: Dashboard · Content (pages/site/product/system/blog) · Technical (schema/sitemaps/properties/tracking) · Issues · Tools · Analytics.

### G. Deprecation / stub pages
| Page | lines | Type | Action |
|---|---|---|---|
| `dm/whatsapp/[waId]` | 1609 | Dead duplicate | **Delete** (port voice recorder first) |
| `contact-test/index` | 197 | Test page | Verify → **delete** if test-only |
| `crm/index` | 10 | Redirect → `/` | Keep |
| `admin/index` | 11 | Redirect | Keep |
| `dashboard/admin` | 12 | Redirect | Keep |
| `docs/index` | 17 | Redirect → drop-docs | Keep |
| `nocode/index` | 15 | Coming-soon | Keep / hide from nav |
| `carbon/index` | 15 | Coming-soon | Keep / hide |
| `studio/index` | 24 | Coming-soon (public) | Keep |
| `sustainability/index` | 24 | Coming-soon (public) | Keep |
| `task/index` | 33 | Coming-soon (badge: Soon) | Keep |
| `dm/whatsapp/ai-config` | 42 | Removed-feature notice | Hide tab |

---

## 2. Consolidation plan (fewer, tabbed hubs)

Use the existing `PageShell` + `embedded` pattern (see `dm/whatsapp/settings.tsx`).

| New hub | Absorbs | Net page reduction |
|---|---|---|
| **Service Operations** (`/dm/orders` as landing) | Orders + Service(submit/track/amend) + Appointments + RX Slots + Drop Docs + Enterprise + Reviews + Flow Hub/Data — all one `/wa-business` backend | 6 top-level items → 1 cluster |
| **Email hub** (`/dm/ses`) | ses inbox + campaign + logs | 4 → 1 hub + inbox |
| **RCS hub** (`/dm/rcs`) | rcs inbox + send + campaign + templates + logs | 6 → 1 hub + inbox |
| **SEO hub** (`/seo`) | 13 SEO routes → grouped tabs | 13 → ~6 tab groups |
| **Link hub** (`/link`) | link create + logs | 3 → 1 |
| **Forms hub** (`/forms`) | forms create + logs + selfservice | 4 → 1 |
| **Control Center** (`/dashboard/system-architecture`) | cors-settings + order-notifications + waba-usernames | +3 tabs |
| **Voice hub** (`/dm/voice`) | voice + voice-in | 2 → 1 |

> **Store stays separate** (`/wix-store` backend) — it is already an internal Products/Orders/Collections hub. Its "Orders" are Wix e-commerce orders, distinct from the `/wa-business` Service Orders above.

Result: ~97 → roughly **55–60 effective destinations**, with consistent navigation.

---

## 3. Migration effort tiers (design-token rollout)

- **Tier 0 — Delete/skip (~12 pages):** redirects, coming-soon stubs, dead `[waId]`, removed `ai-config`, `contact-test`. No token work.
- **Tier 1 — Trivial (hex 0–10, ~35 pages):** mostly already use shared classes. Quick find-replace of stray hex.
- **Tier 2 — Medium (hex 11–60 or 300–800 lines, ~25 pages):** e.g. push, sms, orders, voice, service-*, ses/logs, rcs/*, seo content pages.
- **Tier 3 — Heavy (hex >60 or >800 lines, ~12 pages):** `dashboard/index` (596), `calling` (296), `pages-manager` (218), `contacts` (203), `store` (159), `voice-in` (131), `flow-hub` (127), `blog-manager` (112), `product-pages` (96), `system-pages` (91), `templates`, `wa-auto-response`.

---

## 4. Recommended execution order

1. **Tier 0 cleanup** — delete dead/test pages (after porting voice recorder), hide removed tabs. Lowers surface area before migrating.
2. **High-traffic Tier 3 first** — `dashboard/index`, `contacts` (most-seen), then `templates`, `calling`.
3. **Consolidate channels** — Email & RCS hubs (also reduces duplicate styling).
4. **SEO hub** — biggest structural win.
5. **Sweep Tiers 1–2** by group (Pay, Booking, Service, Forms, Link, Store, Orders…).
6. **Login/auth** styling pass (`access` + Cognito Authenticator theme in `_app`).

> Public marketing/home pages are intentionally **out of scope** (kept separate).

---

## 5. FINAL information architecture (grounded in backend namespaces)

Each group annotated with the backend API namespace / Lambda it actually calls
(verified in `src/api/client.ts`).

```
WECARE.DIGITAL — Admin  (Layout + design-tokens)
│
├─ Dashboard                              [core lambdas + config]
│     Overview · Control Center (+ CORS, Order-Notifs, WABA-Usernames tabs)
│     · Code Repo · Auto Response · Design Reference
│
├─ ★ WHATSAPP  — one system  (Lambdas: outbound-whatsapp, whatsapp-template-management,
│   │            inbound-whatsapp-handler, whatsapp-business-api, whatsapp-voice, whatsapp-calling)
│   │
│   ├─ Inbox                  /dm/whatsapp            /whatsapp/* , /messages
│   │
│   ├─ Business Settings (hub) /dm/whatsapp/settings  (PageShell — 17 tabs, already built ✅)
│   │     Auto-Response · Bot Menu · Scripts · Campaign · Templates · List Msgs ·
│   │     Flows · Flows Hub · Flow Data · Welcome · Calling · Groups · Logs ·
│   │     Profile · Webhooks · WABA · Migration
│   │
│   └─ Service Operations (hub) — /wa-business/*  (flow-driven; Orders orchestrates)
│         Orders (landing)  /wa-business/orders
│         Service Requests  Submit · Track · Amend · Submissions   /wa-business/service
│         Bookings          Appointments · RX Slots                /wa-business/appointments,/rx-slots
│         Drop Docs         /wa-business/documents
│         Enterprise        /wa-business/enterprise-assist
│         Reviews           /wa-business/reviews
│         FAQ               /wa-business/faq
│
├─ Other Channels
│   ├─ Email (SES)     /email/*           → hub: Inbox · Campaign · Logs
│   ├─ RCS             /rcs/*             → hub: Inbox · Send · Campaign · Templates · Logs
│   ├─ Voice           /whatsapp-voice, /voice-aws, /voice-in → hub: Outbound · Voice-In (OBD)
│   ├─ SMS             /sms-aws/*
│   ├─ Push            (push lambda)
│   └─ Logs (all)      /messages
│
├─ Commerce
│   ├─ Store     /wix-store    (Products · Wix Orders · Collections — internal hub)
│   ├─ Catalog   /catalog      (WhatsApp commerce catalog)
│   └─ Pay       /invoices, /payments   (Overview · Pay Flow · Pay Link)
│
├─ Contacts     /contacts
│
├─ Platform
│   ├─ Access    /access
│   ├─ Link      /link    → hub: Links · Create · Logs
│   ├─ Forms     /forms   → hub: Builder · Create · Logs · Self-Service
│   └─ SEO       /seo     → hub: Dashboard · Content · Technical · Issues · Tools · Analytics
│
└─ Hidden (coming-soon): Task · No-Code · Carbon · Studio · Sustainability
```

> **WhatsApp is now one top-level system** with three areas: **Inbox** (live chat),
> **Business Settings** (the 17-tab config hub), and **Service Operations** (the
> `/wa-business` flow-driven order/service/booking/docs/enterprise/reviews/FAQ cluster).
> All of it is served by the WhatsApp family of Lambdas. Other channels (SMS, Email,
> RCS, Voice, Push) sit separately under **Other Channels**.

### Final delete / hide decision
| Item | Action | Reason |
|---|---|---|
| `dm/whatsapp/[waId].tsx` | **DELETE** (port voice recorder into inbox first) | Dead 1609-line duplicate of inbox; zero inbound links |
| `contact-test/index.tsx` | **DELETE** (after confirming test-only) | Leftover test page |
| `dm/whatsapp/ai-config.tsx` | **DELETE** + remove its tab/import from `settings.tsx` | Feature permanently removed |
| `crm`, `admin`, `dashboard/admin`, `docs` redirects | **KEEP** | Real redirect targets |
| `task`, `nocode`, `carbon`, `studio`, `sustainability` | **KEEP, hidden** | Coming-soon placeholders |

Net: **3 files deleted**, 1 tab removed; everything else consolidated via tabs.

---

## 6. How the Design Reference is maintained during Phase B

`/dashboard/design-reference` is the **living source of truth** and already consumes
`src/lib/design-tokens.ts` (which mirrors `src/styles/tokens.css`).

**Governance rules for every page conversion:**
1. **Tokens only.** A converted page may use *only* `design-tokens.ts` values / `var(--token)` and the documented shared components (`Button`, `Table`, `Modal`, `Pagination`, `EmptyState`, `Spinner`, `Tabs`, `PageShell`, `status-pill`, `InfoTooltip`). No raw hex, no ad-hoc spacing.
2. **Reference-first.** If a page needs a pattern not yet in the reference, it is added to `design-reference.tsx` **first** (with tokens), then used. The reference never lags the codebase.
3. **Definition of done per page:** hardcoded-hex count → ~0; renders correctly at mobile widths + Capacitor; keyboard focus + status colors via tokens; verified with `tsc` + build.
4. **Guard (to add):** a `check-hardcoded-colors` script that scans `src/pages/**` for `#rrggbb` and reports per-file counts — used to measure progress and prevent regressions (can be wired into CI / a pre-commit hook).
5. **Tracking:** the effort tiers in §3 double as the progress tracker (hex count is the metric); update this doc as pages reach ~0.

---

## 7. WhatsApp system — page-file map

Every `.tsx` that belongs to the unified WhatsApp system, and where it lives.

```
WHATSAPP  (one top-level system)
│
├─ INBOX
│   src/pages/dm/whatsapp/index.tsx        → renders inbox (keep)
│   src/pages/dm/whatsapp/inbox.tsx        → the inbox UI (standalone)
│   src/pages/dm/whatsapp/[waId].tsx       → ❌ DELETE (dead duplicate; port voice recorder first)
│
├─ BUSINESS SETTINGS  (host: src/pages/dm/whatsapp/settings.tsx — PageShell tabs)
│   ├─ auto-response.tsx        (Auto-Response)
│   ├─ (Bot Menu — inline in settings.tsx)
│   ├─ scripts.tsx              (Scripts)
│   ├─ campaign.tsx             (Campaign)
│   ├─ templates.tsx            (Templates)        ⚠️ heavy 2179/60
│   ├─ interactive-lists.tsx    (List Msgs)
│   ├─ flows.tsx                (Flows)
│   ├─ flow-hub.tsx             (Flows Hub)        ⚠️ 626/127
│   ├─ flow-responses.tsx       (Flow Data)
│   ├─ welcome.tsx              (Welcome)
│   ├─ ai-config.tsx            ❌ DELETE + remove tab (feature removed)
│   ├─ calling.tsx              (Calling)          ⚠️ heavy 1909/296
│   ├─ groups.tsx               (Groups)
│   ├─ logs.tsx                 (Logs — Delivery Report ✅ done)
│   ├─ business-profile.tsx     (Profile)
│   ├─ webhooks.tsx             (Webhooks)
│   ├─ waba-dashboard.tsx       (WABA)             ⚠️ 1025/33
│   └─ migration.tsx            (Migration)
│
└─ SERVICE OPERATIONS  (/wa-business/* — new hub, Orders as landing)
    ├─ src/pages/dm/orders/index.tsx              (Orders — orchestrator) 524/73
    ├─ src/pages/service/index.tsx                (Service landing)
    ├─ src/pages/service/submit-request.tsx       (Submit)
    ├─ src/pages/service/track-request.tsx        (Track)
    ├─ src/pages/service/amend-request.tsx        (Amend)
    ├─ src/pages/dm/appointments/index.tsx        (Bookings · Appointments)
    ├─ src/pages/dm/rx-slots/index.tsx            (Bookings · RX Slots)
    ├─ src/pages/dm/documents/index.tsx           (Drop Docs)
    ├─ src/pages/dm/enterprise/index.tsx          (Enterprise)
    ├─ src/pages/dm/reviews/index.tsx             (Reviews)
    └─ src/pages/dm/faq/index.tsx                 (FAQ)   /wa-business/faq
```

**Build approach for the WhatsApp system:**
- Inbox + Business Settings already share the `settings.tsx` PageShell hub — keep.
- Create a **Service Operations** PageShell hub (same pattern) hosting Orders + Service + Bookings + Docs + Enterprise + Reviews + FAQ as tabs, with **Orders as the default tab** (it already aggregates submissions/docs/tracking).
- Nav: collapse the 6 scattered top-level entries (Orders, Service, Booking, Drop Docs, Enterprise, Reviews, FAQ) into one **WhatsApp → Service Operations** entry.

---

## 8. REBUILT IA (supersedes §5) — Unified Inbox + WhatsApp system + Task

User direction: (a) make a **single Unified Inbox** across WhatsApp + SMS + Email + RCS + Voice;
(b) Service Operations stays **part of WhatsApp**; (c) **Task** = build a real Notion-style
task page (list/board + calendar + reminders), not hidden; (d) Studio / Sustainability /
No-Code / Carbon are **public website pages — out of admin scope, do not touch**.

```
WECARE.DIGITAL — Admin
│
├─ 📥 Inbox (UNIFIED)        — WhatsApp · SMS · Email · RCS · Voice
│      One conversation list with a channel filter; shared Contacts; reply in-channel.
│      ⚙ Requires backend work (see note below).
│
├─ ★ WhatsApp  (business system)
│   ├─ Business Settings (hub) /dm/whatsapp/settings — 17 tabs ✅
│   └─ Service Operations (hub) /wa-business/* — Orders(landing) · Service Requests ·
│         Bookings(Appointments/RX) · Drop Docs · Enterprise · Reviews · FAQ
│
├─ Channels (sending tools: config · campaign · templates · logs)
│   ├─ SMS  /sms-aws      ├─ Email /email   ├─ RCS /rcs   ├─ Voice /whatsapp-voice,/voice-aws,/voice-in   └─ Push
│      (conversations surface in the Unified Inbox; these pages keep send/campaign/config)
│
├─ Commerce       Store(/wix-store) · Catalog(/catalog) · Pay(/invoices,/payments)
├─ Contacts       /contacts
├─ ✅ Task (BUILD) Notion-style: list/board + calendar view + due dates + time reminders
├─ Dashboard      Overview · Control Center · Code Repo · Auto Response · Design Reference
├─ Platform       Access · Link(hub) · Forms(hub) · SEO(hub)
│
└─ Public website (NOT admin — untouched):  Studio · Sustainability · No-Code · Carbon
```

### ⚙ Unified Inbox — backend reality (must-build)
`messages-read` currently reads **only** the two WhatsApp tables. Each other channel has its
own table:

| Channel | Table |
|---|---|
| WhatsApp | `WhatsAppInboundTable`, `WhatsAppOutboundTable` |
| SMS | `SmsAwsTable` |
| Voice | `VoiceAwsTable` |
| RCS | `RcsMessagesTable` |
| Email (SES) | `MessagesTable` |

**Options to power the Unified Inbox:**
- **A (recommended): read-time aggregation.** Extend `messages-read` (or add `/inbox/unified`)
  to scan all five tables, normalise to one shape (`{id, channel, direction, contactId,
  content, status, timestamp, mediaUrl}`), merge + sort. No data migration; each channel keeps
  its own store. Cost: more scans — mitigate with per-table `contactId` GSIs + time-window limit.
- **B: dual-write.** Each channel also writes a normalised row to the WhatsApp tables with a
  `channel` field. Simplest reads, but touches every send path + needs backfill. Higher risk.

→ Recommend **A**. New endpoint `GET /inbox?contactId=&channels=&limit=`; the inbox UI gets a
channel filter (All / WhatsApp / SMS / Email / RCS / Voice) and a per-message channel badge.

### ✅ Task page (build)
- UI: `src/pages/task/index.tsx` — list/board toggle + month calendar + task drawer.
- Backend: new `TasksTable` (id, title, notes, status, dueAt, remindAt, assignee, tags, ttl)
  + a Tasks CRUD Lambda (`/tasks`).
- Reminders: reuse the existing **scheduled-messages** Lambda / EventBridge to fire a reminder
  at `remindAt` (WhatsApp/email to the assignee). Mirrors the existing scheduling pattern.

### Revised delete/hide (unchanged from §5 core)
- DELETE: `dm/whatsapp/[waId].tsx`, `dm/whatsapp/ai-config.tsx` (+ tab), `contact-test/index.tsx`.
- KEEP redirects (crm/admin/dashboard-admin/docs).
- Studio/Sustainability/No-Code/Carbon → **public site, leave as-is** (no longer "hidden admin stubs").

### ⚙ Unified Inbox — CORRECTED recommendation (after schema deep-check)

The `WhatsAppInbound/Outbound` tables are **generic message tables** (PK=`id` uuid, a
`channel` discriminator field, a `contactId-index` GSI). RCS is already wired to them
(`MESSAGES_TABLE=WhatsAppOutboundTable`). So all channels **can share them**.

Record-shape gaps to close per channel (SMS/Voice/RCS/Email `_store`):
- add `channel` (`sms`/`voice`/`rcs`/`email`) and `timestamp` (Decimal epoch — read sorts by it)
- lowercase `direction` (`outbound`) and `status` (`sent`/`failed`) to match WhatsApp
- keep channel extras (Voice `duration`/`callType`, SMS `providerMessageId`) as extra attrs

**Recommended approach = dual-write (supersedes Option A read-aggregation):**
- **Phase 1 (zero risk):** each channel ALSO writes a normalized row to the shared
  Inbound/Outbound tables (its own table stays untouched). Unified Inbox reads the shared
  tables via `contactId-index` + `channel` filter — works immediately; existing per-channel
  pages keep working.
- **Phase 2 (optional):** repoint per-channel list pages to the shared tables, backfill old
  rows, retire separate tables.

Caveats: outbound-only channels need their inbound webhooks to write too; Voice = calls
(`messageType:'call'`); historical rows need a one-time backfill for the unified view.
Table rename ("Message*" instead of "WhatsApp*") is cosmetic — keep names to avoid migration.
