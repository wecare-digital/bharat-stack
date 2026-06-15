# Unification Roadmap — "Unify Everything"

What's already unified, and the full list of what else can be — with UX approach, effort, risk.

---

## ✅ Already unified (done)

| Area | What | Where |
|---|---|---|
| **Messages store** | One canonical `MessagesTable`, all channels write to it | backend |
| **Contacts** | One `ContactsTable` shared by every channel | backend |
| **Unified Inbox** | Conversation-grouped, cross-channel threads + **inline reply** per channel | `/dm/inbox` |
| **Channels hub** | One launcher for all channels + cross-channel tools | `/dm/channels` |
| **Broadcast** | One composer → channel → audience (opt-in filtered) → message → send w/ progress | `/dm/broadcast` |
| **Delivery Report** | Cross-channel logs with channel/status badges | `/dm/logs` |
| **Calls in timeline** | Voice/WhatsApp calls as breadcrumbs in the unified view | breadcrumb rows |
| **Service Ops** | WhatsApp-Flow cluster (orders, bookings, docs…) in one hub | `/dm/service-ops` |

---

## 🔜 What else can be unified (prioritized)

### Tier 1 — high value, low risk (frontend-mostly)

**1. Unified Broadcast / Campaign composer** ✅ DONE — `/dm/broadcast`
Pick channel → opt-in-filtered audience → message (WhatsApp template / SMS / RCS / Email) → send
with live progress, over the existing send Lambdas.

**2. Unified Templates / Content Library** ✅ DONE — `/dm/content`
WhatsApp + RCS templates aggregated into one searchable, channel-filterable list (status,
category, language, preview) with create deep-links. SMS DLT/email bodies can be added next.

**3. Unified Channel Settings**
Today: WhatsApp has a 17-tab settings hub; SMS/RCS/Email/Voice/Push configs are inline + scattered.
Unify: a Settings home with a section per channel + shared settings (sender identities, opt-in/consent,
quiet hours, retry policy). Use the launcher pattern (link into each), not deep nesting. **Effort: M · Risk: low.**

**4. Cross-channel Search (Ctrl-K)**
Search contacts · messages · orders · templates · pages from one palette (a palette already exists).
Backend: query `MessagesTable` (channel-index) + Contacts; thin search endpoint or client-side. **Effort: M · Risk: low.**

**5. Unified Scheduling view**
`scheduled-messages` Lambda is already cross-channel — just needs one "Scheduled" surface listing all
pending sends across channels with edit/cancel. **Effort: S · Risk: low.**

### Tier 2 — high value, medium effort

**6. Unified Automation / Auto-response rules**
Today: WhatsApp keyword + AI auto-reply only. Unify into a rules engine: trigger (keyword/intent/channel)
→ action (reply/template/route/AI) across all channels. Reuse `ai-generate-response`. **Effort: L · Risk: med.**

**7. Unified Calls view** ✅ DONE — `/dm/calls`
One call log reading the canonical `channel=voice` breadcrumbs (AWS + Airtel CDR + WhatsApp
Calling), with provider/direction/duration/status filters + recording links.

**8. AI Assist gateway (cross-cutting)**
One `POST /ai/assist { task, context }` over `ai-generate-response` (Bedrock). Every page calls the same API:
reply suggestions, summarize thread, classify/sentiment, translate, "why failures spiked", draft template,
NL contact segments, extract tasks. All logged to `AIInteraction`. **Effort: L · Risk: med.**

**9. Contact 360 timeline**
On a contact: unified activity feed (messages + calls + orders + payments + invoices) from one query.
Reuses `MessagesTable` (contactId-index) + payments + service-ops tables. **Effort: M · Risk: low.**

### Tier 3 — platform / future-proofing

**10. Unified analytics dashboard** — cross-channel volume, delivery rate, response time, cost-per-channel.
**11. Unified consent/opt-in ledger** — one place for per-contact channel consent (compliance).
**12. Unified cost & usage** — per-channel spend (Meta/Pinpoint/Airtel/Sinch/SES) in one view.
**13. Routing / failover** — "send via best channel" (RCS→SMS fallback already exists; generalize).

---

## Backend convergence still open (separate track)
- `WhatsAppInbound/Outbound` retained as WhatsApp's specialized store (template analytics, invoicing,
  bulk, ad-attribution). Could be fully folded into canonical later by enriching the dual-write +
  repointing those 4 readers — deliberate, separately-tested change.

---

## Suggested build order
1. Unified Channel Settings (#3) — completes the "settings not unified" gap.
2. Unified Broadcast (#1) + Content Library (#2) — biggest day-to-day operator win.
3. Unified Calls view (#7) + Contact 360 (#9).
4. AI Assist gateway (#8) + Automation rules (#6).
5. Search (#4), Scheduling (#5), analytics/consent/cost (#10–13).

Everything in Tier 1 is frontend-mostly and low-risk (same launcher/hub + embedded-page patterns
already proven by the Unified Inbox, Channels hub, and Service Ops).
