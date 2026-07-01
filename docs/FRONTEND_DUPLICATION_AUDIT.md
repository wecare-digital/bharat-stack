# Frontend Page Duplication Audit

~120 route pages under `src/pages` (+15 API routes). The app was built **channel-by-channel**
(WhatsApp, RCS, SES/email, SMS, Voice) each with its own inbox/campaign/logs/templates, THEN a
unified `dm/*` layer was added that partially supersedes the per-channel pages — but the old ones
were never removed. That's the core duplication.

## Duplicate clusters (same function repeated)
| Function | Pages | Canonical | Redundant (candidates to retire) |
|---|---|---|---|
| Inbox | `dm/inbox`, `dm/whatsapp/inbox`, `dm/rcs/inbox`, `dm/ses/inbox` | `dm/inbox` (cross-channel) | the 3 per-channel inboxes |
| Campaign/Broadcast | `dm/broadcast`, `dm/whatsapp/campaign`, `dm/rcs/campaign`, `dm/ses/campaign` | `dm/broadcast` | the 3 per-channel campaign pages |
| Logs | `dm/logs`, `dm/whatsapp/logs`, `dm/rcs/logs`, `dm/ses/logs` | `dm/logs` | the 3 per-channel logs |
| Templates | `dm/whatsapp/templates`, `dm/whatsapp/template-builder`, `dm/rcs/templates` | one templates page w/ channel filter | duplicates |
| Send/test | `dm/whatsapp/send-test`, `dm/rcs/send` | fold into inbox/broadcast | both |
| Usernames/BSUID | `dashboard/waba-usernames`, `dm/whatsapp/bsuid` | one | the other (flagged earlier) |
| Channel landing | `dm/whatsapp`, `dm/rcs`, `dm/ses`, `dm/sms`, `dm/voice` indexes | `dm/channels` | per-channel landings if `dm/channels` covers them |
| Contacts | `contacts/`, `dm/contact-360`, `crm/` | `dm/contact-360` | `contacts/`, `crm/` (overlap) |
| Admin/Dashboard | `dashboard/index`, `dashboard/admin`, `admin/` | `dashboard/` | `admin/` |
| FAQ | `faq` (root), `dm/faq` | `dm/faq` | root `faq` (or keep as public) |
| Voice/Calls | `dm/calls`, `dm/voice`, `dm/voice-in`, `dm/whatsapp/calling` | consolidate to `dm/calls` | overlap |
| WhatsApp Flows | `dm/whatsapp/flow-hub`, `flows`, `flow-publish`, `flow-responses` | one flows hub w/ tabs | 3 split pages |
| SEO management | `seo/pages`, `seo/pages-manager`, `seo/site-pages`, `seo/system-pages`, `seo/product-pages`, `seo/blog-manager` | `seo/pages-manager` (tabs) | the near-duplicate page-type variants |

## Likely-dead / test / demo pages (verify, then remove)
`contact-test`, `dm/whatsapp/scripts`, `dm/whatsapp/migration`, `dm/whatsapp/send-test`,
`nocode`, `studio`, `carbon`, `sustainability`, `task`, `store` (if not linked in nav).

## Root causes
1. **No shared channel abstraction** — each channel reimplemented inbox/campaign/logs instead of one
   component parameterized by `channel`.
2. **Unified `dm/*` layer added on top** without deleting the per-channel originals (dead but shipped).
3. **SEO tool grew page-per-view** instead of one tabbed manager.

## Impact
- Larger bundle + build time, more surface to maintain/secure, inconsistent UX, and exactly the kind of
  drift you saw with usernames (two pages, one stale).

## Consolidation target (rough)
~120 → **~70–80** route pages by: retiring per-channel inbox/campaign/logs in favor of the unified
`dm/*` equivalents, merging the SEO page-type variants into the tabbed manager, and removing dead/demo
pages. Each retirement is: confirm nav no longer links it → confirm unified page covers the function →
delete + redirect.

## Method to finalize (evidence-based, before deleting anything)
1. Map the nav/router: which of these pages are actually linked/reachable.
2. For each redundant page, diff its features vs the canonical to ensure no unique capability is lost.
3. Retire in batches with redirects; keep git history for rollback.
