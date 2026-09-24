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

### C1 — New navigation config + settings gear · DONE
Sidebar is now **8 top-level streams**: Inbox (with six channel-filter children,
including Calls) · Contacts · Broadcast · Payments · Service Ops · Store · Forms · Tasks.
The 30-item WhatsApp branch is gone from the sidebar entirely — a test asserts zero
`/dm/whatsapp*` paths remain in it.

Everything else lives in `settingsConfig`, six labelled and hinted groups opened by a
gear above the sidebar footer. `SettingsGear` is a panel, not a route: a `/settings` page
would be one more destination to navigate to before navigating, and would need its own
shell, breadcrumb and a decision about the page you were on.

**Reachability is the invariant, and it is tested.** `getAllNavItems()` walks BOTH trees
and is the single source the command palette uses, so:

| | before | after |
|---|---|---|
| unique destinations reachable | 87 | **95** |
| lost | — | **1**, `/dm`, which was re-added once found to be a real 160-line page |
| newly reachable (were orphaned) | — | **9** incl. `cors-settings`, `ai-agent`, `scripts`, `forms/create` |

Three independent routes to every settings page: the gear panel, `Ctrl+K`, and the
sidebar search box — deliberate redundancy, because for the 21 orphans navigation is the
only way in.

`/access/security` is first in the account group, and a test pins that: it cannot be
reached any other way and Cognito will not let anyone enrol TOTP on the operator's behalf.

One subtlety the tests caught: the Inbox children are one page with six query strings, so
active-state matching had to strip `?…` before comparing. Without it the sidebar
highlighted nothing on the page you were looking at.

### D1 — Plan / approval / receipt path for agent writes · DONE (enablement withheld)
**The approval path is complete end to end. Enablement is deliberately NOT thrown.**

Items 1–3 below are now done; item 4 is a **refusal**, not a pending task — see the
closing note in this section.

`plans.py` (plan hash, canonical arguments, staleness) and `receipts.py` already existed
from phase 6.2. The missing third — a human saying yes to *one exact intent* — is now
`lambda_utils/agent/approvals.py`, with 37 tests.

Properties, each because its absence has a named failure:

| Property | Failure it prevents |
|---|---|
| bound to a `plan_hash` | an approval scoped to a *tool* is a standing licence to send |
| single use, consumed atomically | otherwise one yes is a replay token for a thousand sends |
| short lived (900s default) | "yes, message this customer" is not true tomorrow |
| approver must be a named human | `agent`/`model`/`system` rejected — the model must not approve its own send |
| fails closed on every error | a broken store, an unreadable clock and a hash mismatch all refuse |
| in-memory default store | a Lambda's memory cannot outlive the request, so an unwired deployment applies **nothing** |

`assert_may_apply` runs the catalog gate **first**, so a disabled tool reports "switched
off" rather than "unapproved" — otherwise somebody hunts the wrong problem.

**After this an APPLY is refused for two independent reasons: the catalog still disables
it, AND there is no approval.** Both must change, separately and deliberately. A test
asserts no APPLY tool became enabled and that no plausible environment variable can
promote one.

#### 1 — Storage, so an approval outlives the request that created it · DONE

`stack-wecare-digital-AgentApprovalsTable`, partition key `planHash`, no sort key — an
approval is identified by the intent it authorises and the plan hash *is* that intent, so
one row per intent means the single-use condition has exactly one thing to test.
`PAY_PER_REQUEST` (approvals come from a human clicking a button; provisioned capacity
would pay a baseline for an idle table). **PITR on**, because this is the record of who
authorised a customer-facing send.

`DynamoApprovalStore.consume` is one conditional `update_item`:

    SET consumedAt = :now
    IF  attribute_not_exists(consumedAt) AND expiresAt > :now

A read-then-write loses the race, and losing it means one approval spending twice — which
is the whole point of single use. `ConditionalCheckFailedException` is therefore the
*correct answer*, not an error to log: it becomes `None` and the caller refuses.

**TTL is housekeeping, not the control.** DynamoDB's TTL deletion is documented as taking
up to 48 hours, so an expired approval would stay spendable for two days if TTL were
doing the enforcing. `expiresAt > :now` in the condition is what enforces it.

IaC: `scripts/provision_agent_approvals_table.py`, idempotent, `--dry-run` / `--verify`.
`--verify` also asserts that **zero** APPLY tools are enabled, so the table can never be
mistaken for a switch. No IAM change was needed — the live role already scopes DynamoDB to
`table/stack-wecare-digital-*`, confirmed by reading the account rather than the IaC.

#### 1b — `drafts.py`, because the client cannot hold the arguments · DONE

Not in the original list, and necessary: `describe_plan` masks the recipient to `...0044`
and omits the message body, so the browser never has the real arguments — and a hash over
masked values would collapse two different recipients into one plan.

Two ways out, one acceptable:

* send the full arguments to the client and have it echo them back on approve — undoes the
  redaction, and lets a client display one intent while approving another;
* keep the plan server-side and let the client refer to it **by hash**.

`drafts.py` is the second. Drafts share the approvals table under a `draft#` key prefix; a
plan hash is hex, so the keyspaces cannot collide and `DynamoApprovalStore` reads the bare
hash. `load()` rebuilds through `build_plan` and refuses if the row does not hash to its
own key — so an altered row cannot authorise a different send.

The cost is stated rather than skipped: a draft holds the **full** canonical arguments,
because that is the only form the hash can be recomputed from. So the table holds a
recipient and a message body at rest, with PITR on. Bounded by a 3600s TTL (deliberately
longer than the 900s approval TTL, so a still-valid approval cannot point at a vanished
draft), by only APPLY tools being drafted, and by nothing reading a draft except the
approve path.

#### 2 — Admin-gated approve route · DONE

`POST /ai/approvals` and `POST /ai/approvals/status` on `zllr9lrg7j`, both on the existing
`jkhxmog` integration (same `:live` alias).

Separate route keys rather than another field in the `/ai/generate` body: that route needs
a signed-in user, this one needs **Admin with an enrolled second factor**, and one handler
entry point serving two privilege levels means one `require_auth` call trying to express
both — where the looser one wins by default.

The approver comes from the verified token, never the body. Path matching is on **segment
boundaries**: `/ai/approvalsX` and `/ai/approvals-anything` do not match, because the
substring form of that test is what let `/wa-business/webhooks-anything` skip
authentication entirely.

Code was deployed **before** the routes existed — a route pointing at a handler that
cannot serve it is a live 4xx. `v13 → v14 → v15`; rollback `--function-version 14`.

Verified live. The ladder matters: `404` route absent · `500` alias invoke permission
missing (this once produced a silent outage with no Lambda log line at all) · **`401`
handler reached and refused — the pass** · `200` the gate is broken. Both routes 401,
`/ai/generate` still 401, and CloudWatch on v15 logs
`approval_auth_refused` / `AGENT_APPROVAL_UNAUTHORIZED` with no traceback, which is also
the proof that `use_dynamo_store()` runs at import.

#### 3 — Approval UI in the chat panel · DONE

A refusal previously went back into the conversation as a tool result and **only the
model's prose escaped** — so an operator saw the agent's narration of what it wanted to do,
precisely the thing not to trust, and had nothing concrete to act on. `plan_sink` collects
each refused-and-drafted plan during the loop and `pendingPlans` returns them with
arguments already redacted.

The panel is **amber**. Green would say "done" and red "something broke"; a withheld action
is neither. Its heading states in words that approving does not send. `stillDisabled` is
read from the response and never hardcoded, so it cannot keep claiming "nothing was sent"
on the day an apply is enabled. Last turn's plans are cleared rather than accumulated. A
plan whose draft write failed is `approvable: false` and never offered, so no button
appears that would always refuse.

#### 4 — Enablement · REFUSED, not pending

This is not an item awaiting a checkpoint. `01-standing-authorization.md` lists
"Enabling `PSTN_BROWSER_ROUTING_ENABLED` or any live-send flag" under **"Still
prohibited — never done, and never asked about either"**, so it generates no prompt and no
confirmation queue entry.

What the completed path changes is only this: an apply is now refused for **one** reason
(the catalog disables every APPLY tool) where before it was refused for two. The
machinery a future enablement would need exists and is tested, which was the point — the
worst time to design an approval system is the moment somebody wants a send turned on.

### D2 — Fix the agent UI truth gap · DONE
Measured precisely: the internal surface has **30** catalog entries — **12 READ enabled,
18 APPLY refused** — and the UI listed all 30 with `enabledTools` seeded to all of them,
so the panel read "Tool Capabilities (30/30)" and offered an **Enable All** toggle that was
cosmetic for 18 of them. `governance.py` states there is deliberately no flag to enable an
APPLY tool.

Now: each row carries `cls` and `refused` mirrored from the catalog; the counter is
denominated in the available set with the refusal count stated; **Enable All** can only
select available tools; and a refused tool renders as a labelled `REFUSED` chip with no
checkbox — because a control implies it can be switched on, and it cannot.

Shown rather than hidden, deliberately: knowing a capability exists and is withheld on
purpose is exactly what someone needs before asking the agent to send something.

`tests/test_agent_ui_truth.py` (27 tests) parses the TSX and compares it to the Python
catalog entry by entry — ids, class, and `refused` as the exact inverse of `enabled`. It
also guards the guard: if any APPLY tool is ever enabled without the approval path, that
test fails too.

### E1 — Task, Payments, Invoice records, Forms responses · DONE
Each built on data that **already exists**, and the investigation mattered more than the
building.

**`/task` — there is no tasks backend in this repository.** No `TasksTable`, no task API,
nothing. The old 33-line `ComingSoon` promised six features: create/assign, priorities,
deadlines, progress, collaboration, templates, reminders — five had nothing behind them.
Building that screen would have been fabrication, the same defect as the agent panel
advertising 18 refused tools.

What does exist is `conversation-meta`: `status` (open/pending/resolved), `assignee`,
`tags`, `notes`, already written by the inbox on every conversation, and
`GET /inbox/meta` returns all of it. So Tasks is that work queue. It states on screen
that priorities, due dates, templates and reminders are **not stored anywhere yet** —
absent rather than rendered as an empty column implying the field exists and is unset.

**`/pay/records`** over `listInvoicesEngine` — full GST breakdown, delivery log per
invoice via `getInvoiceDeliveryLog`. **Read-only deliberately**: `cancelInvoice`,
`deleteInvoice` and `updateInvoiceEngine` all exist in the API and none is wired, because
`deleteInvoice` takes an `adjustSequence` flag — a mis-click could renumber a statutory
GST series. Totals are summed from each invoice's **stored** total, never recomputed from
line items: the invoice is the record, and a second calculation is a second answer that
disagrees the first time a rounding rule changes.

**`/forms/responses`** over `listSubmitRequests`. Sorted **oldest unpaid first**, not by
recency, because a recency sort buries exactly the rows that need attention and an
unactioned request is a customer who paid and heard nothing. `isExpired` and `daysOld` are
server-computed and called out rather than left as columns to notice.
`resendSubmitRequestPayment` is deliberately not wired — it messages a customer about
money.

Phone numbers show the last four digits on both record screens, matching every log site in
the codebase. Typecheck caught two fields I had invented on `InvoiceDeliveryLog`
(`type`, `sentAt`); the real shape is `timestamp`, `channel`, `toNumber`, `status`,
`error`.

Nav: Invoice records added under Payments, Responses added **first** under Forms, and the
`Soon` badge removed from Tasks because it is no longer a stub.
