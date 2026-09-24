# Work plan — information-architecture consolidation

Durable state for an unattended run. **This file is the source of truth, not the
conversation.** If the session is interrupted, the next one reads this and resumes at
the first item that is not `DONE`.

Repo `/Users/wecaredigital/wecare-store` · branch `stack` · account `775261844268`

## Owner decisions taken (2026-09-24)

1. Consolidate the duplicate clusters — **yes**.
2. `/access/security` stays reachable in the sidebar — **yes**.
3. Build the plan/approval/receipt path so agent writes can be enabled — **yes**.
4. Also in scope: Task, Payments, Invoice-engine records, Forms.
5. **Calls is a filter inside the Inbox, not a sidebar entry.** `/dm/calls` is already a
   filtered view of the same `MessagesTable`; the Inbox already has `voice` in its
   `CHANNEL` map, renders voice notes with an audio player, and has `voice` in its
   channel dropdown. Call *configuration* (`/dm/voice`, `/dm/voice-in`) goes behind
   the gear.

## The governing principle

**Sidebar = streams you work in daily. Gear = things you configure once.**

## Measurements this plan rests on

Taken 2026-09-24, not estimated:

| Fact | Value |
|---|---|
| nav top-level / entries / unique paths / broken | 11 / 95 / 88 / **0** |
| WhatsApp sub-pages as a share of the nav | **30 of 88 (34%)** |
| admin routes already orphaned from the nav | **22** |
| `rcs/inbox` vs `ses/inbox` identical lines | **196 of 273** |
| `rcs/campaign` vs `ses/campaign` identical lines | **95 of ~131** |
| the four logs pages | **971 lines over one table** |
| canonical message store | ONE `stack-wecare-digital-MessagesTable`, `channel` column |
| nav paths with no link anywhere else | **21 of 88** |
| routes rendering with no shell at all | **15** |

Consolidation needs **no data migration** — every channel already lives in one table,
and the per-channel pages are already embedded tabs with an `embedded` prop.

## Hard constraints

- Never enable `PSTN_BROWSER_ROUTING_ENABLED`, `WA_LIVE_SMOKE_TEST`, or any live-send
  flag. Browser calling stays off, so Calls-in-Inbox means see and hear, not dial.
- Agent APPLY tools stay refused until the approval path genuinely exists. No flag
  that merely turns them on.
- Every gate green before each commit: `pytest -q`, `npm run typecheck`,
  `npx vitest run`, `npm run build`, `check_design_drift.py --gate`,
  `check_ui_labels.py --gate`, `check-provider-policy.sh`.
- Commit by explicit path. Never `git add .`.
- Do not stage `.kiro/specs/plivo-api-control-plane-fix/*` — another session owns them.

## Sequencing rule that must not be broken

The palette had to work **before** the sidebar shrinks, because the restructure deletes
the sidebar search box that does the job today. That is done (`6651e29d`): the palette is
derived from `getAllNavItems()` and no longer loops the renderer on keystroke.

Likewise the 15 shell-less pages must be wrapped **before** the sidebar shrinks, or they
become dead ends with no sidebar, no breadcrumb and no back link.

## Items

Status: `TODO` · `IN_PROGRESS` · `DONE` · `BLOCKED`

### A1 — One logs view, not four · DONE
Survivor `dm/logs` now takes a `channel` preset (prop or `?channel=`) and absorbed
**every** capability of the three it replaced: contact-name resolution, failure-reason
breakdown, CSV export, pagination and WhatsApp error decoding from `whatsapp/logs`, plus
row delete from `ses/logs`. Hubs embed it: RCS `channel="rcs"`, Email `channel="email"`,
WhatsApp settings `channel="whatsapp"`. `forms/logs` and `link/logs` stubs deleted.
WhatsApp error decoding stays WhatsApp-only — `describeWaError` maps Meta codes, and
showing a Meta explanation beside an SES bounce would invent a cause.
`dm/logs` (319) + `dm/ses/logs` (268) + `dm/whatsapp/logs` (265) + `dm/rcs/logs` (119).
All four call the same `api.listMessages`; they differ only in a channel filter and a
column set. Keep `dm/logs` as the survivor with per-channel column presets. Retire
`forms/logs` and `link/logs` — both are `ComingSoon` stubs with no reads.

### A2 — One campaign view, not four · DONE
`rcs/campaign` and `ses/campaign` deleted; both hubs' Campaign tab now embeds
`dm/broadcast`, which already sends all four channels. `whatsapp/campaign` KEPT — it has
WhatsApp-template-specific send UI and is embedded by `whatsapp/settings`; retiring it
would have lost function rather than duplication.
`dm/broadcast` (220) is already the multi-channel superset with `pickChannel()` and
`eligible()`. `rcs/campaign` (132) makes **no send call at all**. Campaign history in all
three channel pages is synthesised client-side by filtering `listMessages` for a
`campaignId` — there is no campaigns table, so merging is merging a derived view.

### A3 — Retire `rcs/inbox` and `ses/inbox` · DONE
Both deleted. `dm/inbox` gained a `channel` preset; the hubs embed it. The preset is
deliberately NOT a lock here (unlike logs) because a conversation legitimately spans
channels. Also removes the odd `listRcsMessages` path that reached the canonical table
via `POST /rcs/send {action:'list'}`.
Superseded by `dm/inbox`, which reads and writes both channels. Both are already absent
from the nav. Removes the odd `listRcsMessages` path that reaches the canonical table
through `POST /rcs/send {action:'list'}` instead of `GET /messages?channel=RCS`.

### A4 — Calls becomes an Inbox filter · DONE
`dm/calls` deleted. Nav entry is now `/dm/inbox?channel=voice`; `dm/channels` link
repointed. The dial button in the inbox stays disabled and labelled — browser routing is
off and stays off, so this is see-and-hear, not dial.
Retire `/dm/calls` (159 lines, same table). Keep the dial button disabled and labelled.

### B1 — Wrap the shell-less routes · DONE
**15 → 3**, and the three that remain are correct: `/access` (the sign-in page, no shell
by design) and `/admin` + `/forms` (redirects that return `null`). Five of the original 15
had already gone with the A-item deletions.

Six wrapped in `MaybeLayout` by a mechanical transform — the existing component renamed
to `<Name>Body`, a thin wrapper added as the new default export — so **not one line of
JSX** inside 2,121 lines of markup was touched. `MaybeLayout` renders children bare when
`embedded`, so every hub that embeds them is unaffected.

Three of the six declared an `embedded` prop and then ignored it completely
(`auto-response`, `scripts`, `ai-agent`), which is the tell that the standalone case was
never exercised.

`/seo/InstructionsContent` was not wrapped — it is a content **component** that happened
to sit under `src/pages/`, so Next was publishing it as a 292-line chrome-less route.
Moved to `src/components/seo/`, both importers repointed, and confirmed absent from the
export. Wrapping it would have blessed a route that should not exist.

### C1 — New navigation config + settings gear · TODO
Sidebar: Inbox · Contacts · Payments · Tasks · Forms · Sign-in & MFA (+ Orders, owner
leaning sidebar). Everything else behind the gear, findable by `Ctrl+K`.

### D1 — Plan / approval / receipt path for agent writes · TODO
The 8 `CLASS_APPLY` tools stay refused until this exists. `plans.py` and `receipts.py`
already exist from phase 6.2. Needs: plan hash, an operator approval step, a recorded
receipt, and only then enablement.

### D2 — Fix the agent UI truth gap · TODO
`InternalChatTab`'s `TOOLS_LIST` advertises **30 tools including all 8 the backend always
refuses** (`Send WhatsApp`, `Delete Contact`, `Clear All Data`, `Create Invoice`). Same
defect class the label gate exists to catch.

### E1 — Task, Payments, Invoice records, Forms responses · TODO
`/task` is a 33-line `ComingSoon` stub. The others need record views.
