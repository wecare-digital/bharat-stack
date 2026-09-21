---
inclusion: always
---

# Standing authorization — run unattended, do not queue confirmations

Adopted 2026-09-21 by explicit owner instruction. This file ranks immediately
below `00-current-owner-overrides.md` and **overrides the confirmation-queue
requirements in `maintenance-reporting.md`** wherever the two conflict.

The owner's instruction was: stop asking, run unattended, auto-approve.

## The default is PROCEED

Do not publish a numbered confirmation queue for work that falls inside the
standing grant below. Do not ask "shall I continue" between phases. Do not wait
for `YES n`. Execute, verify, and report what was done afterwards.

Reporting requirements are unchanged: every action still lands in
`docs/execution/change-authority-matrix.md` with its class, target, evidence and
rollback, and the phase status tables are still produced. **Unattended means no
prompt, not no record.**

## Standing grant — act without asking

| Class | Scope | Conditions that make it automatic |
|---|---|---|
| `A0_READ` | All repository, AWS, GitHub and provider reads; logs, metrics, schemas, docs, health queries | Always |
| `A1_LOCAL` | Source, tests, docs, IaC authoring, generated inventories, feature-flag-gated implementation | Always. Preserve files owned by another session |
| `A2_REMOTE_CODE` | `git add <explicit paths>`, commit, `git push origin stack` | Non-force, branch `stack`, paths named individually, gates green |
| `A3_PRODUCTION` | `update-function-code`, publish version, move a `live` alias | Function is not one of the protected-path exceptions below; rollback version captured first; focused tests green on the exact tree |
| `A3_PRODUCTION` | Create or update API Gateway routes, integrations, authorizers; create DynamoDB tables, queues, IAM policies, alarms, dashboards | Change is additive or tightens security; IaC updated in the same change |
| `A3_PRODUCTION` | Amplify build-spec and header changes, build triggers | App `d22dm4b0jn71jw`; config snapshotted first |
| `A3_PRODUCTION` | Flag changes that **only tighten** security or keep a risky feature off | Never use this to enable `PSTN_BROWSER_ROUTING_ENABLED` or a live-send path |
| `A3_PRODUCTION` | Safe live verification: unauthenticated probe of a route **after** its auth fix is deployed, expecting rejection | Probe must be inert on success-path side effects |
| `A4_DESTRUCTIVE` | Delete an API route or integration whose **target Lambda does not exist** | Export the route + integration JSON to `docs/prohibited-provider-retirement.md` first |
| `A4_DESTRUCTIVE` | Delete a retired-provider surface already proven absent at runtime: stale IaC declarations, dead scripts, obsolete env keys, unreferenced UI mappings | Zero live invocations proven; rollback path recorded |
| `A4_DESTRUCTIVE` | Delete an obsolete table, queue or alarm after migration | Export/snapshot with checksum, readers/writers proven zero, restore procedure written |
| `A4_DESTRUCTIVE` | Let an already-scheduled secret deletion complete | Only the six already scheduled; never cancel, never schedule a new one |

Live QA sends and calls are authorized **only** to an owner-supplied QA
recipient. Absent one, use fixtures and record the requirement as
`WAITING_FOR_OWNER` rather than sending to a real customer.

## Still prohibited — never done, and never asked about either

These are not confirmation gates. They are refusals, so they generate no prompt:

- Deleting, deregistering, re-registering, migrating or offboarding a WhatsApp
  number, WABA, phone-number ID or business portfolio. Requesting fresh OTPs or
  changing a two-step PIN.
- Rotating, revoking, replacing or reading any provider credential value. The
  exposed families stay `MANUAL_OWNER_ACTION`.
- `secretsmanager get-secret-value` / `batch-get-secret-value` from a shell or
  from `aws___run_script`, in any spelling.
- Putting a credential on a command line, in argv, in a log, or in a report.
- Force push, history rewrite, `git add .` / `-A` / `-u`, bare `git stash`.
- Deleting `~/aws-new-keys-SAVE-THEN-DELETE.txt` or any protected path in
  `block_catastrophic.py`.
- Enabling Security Hub.
- Activating ad spend, changing budgets or bids, publishing an ad, a Play
  release, a Wix site or a public business profile.
- Payment capture, refund or payment-configuration mutation.
- Enabling `PSTN_BROWSER_ROUTING_ENABLED` or any live-send flag.
- Using PayU, Airtel messaging, Sinch SMS/Voice/WhatsApp, or Plivo SMS.
- Disabling a deny guard to get past a block.

Anything genuinely outside both lists: pick the reversible option, do it, and
report it. Only stop when a provider or the owner holds the only key — a missing
OAuth redirect URI, a credential only the owner can replace, a QA recipient only
the owner can nominate. Name the exact unblock action and carry on with
everything else.

## The guards stay

`block-inline-secrets`, `block-broad-git-staging` and `block-catastrophic` remain
enabled. They **deny** rather than prompt, which is precisely what makes blanket
allow defensible — safety moved from asking a tired human to a rule that cannot
be talked around. Removing one removes the justification for the wildcard
permissions file.

`block-catastrophic` still returns `ask` for the sixteen AWS delete operations in
its `DESTRUCTIVE_AWS` table (delete-secret, delete-function, delete-alias,
delete-table, delete-stack, delete-bucket, IAM and KMS deletes, and similar).
Those are the few actions where a wrong call cannot be undone from the repo, and
that table deliberately does **not** include API route or integration deletion,
so the retirement work in the standing grant runs without a prompt.

## Two permission files, not one — the gap that caused the interruptions

The per-workspace file grants `fs_read`/`fs_write` **for the workspace root**.
Any path outside a registered root falls through to the **user-level** file:

    ~/.kiro/workspace-roots/df7bb16a63efe7f7/permissions.yaml   the project
    ~/.kiro/settings/permissions.yaml                            everything else

On 2026-09-21 an unattended run was interrupted roughly once per step. The
project file was already fully wildcarded and every deny hook passed silently on
the command shapes in use — measured directly against
`scripts/block_catastrophic.py`, including `apigatewayv2 delete-route` and
`lambda update-function-code`, all of which returned pass. The prompts were
coming from the agent writing scratch output to `/tmp` and reading `~/.kiro`
config: both outside the root, so each **new filename** prompted, and 23 literal
path entries had accumulated in the user-level file from the approval clicks.

Both halves are now fixed:

1. `scripts/apply_unattended_permissions.py --user` writes the user-level file
   with the same six capabilities, scoped to scratch space and `~/.kiro`, so
   there are no literal filenames left to grow.
2. Scratch output belongs in `.scratch/` inside the workspace (gitignored), not
   `/tmp`. Prefer it for every throwaway file; it needs no permission at all.

`$HOME` is deliberately **not** wildcarded for writes. `block-catastrophic`
guards `~/.aws`, `~/.ssh` and the retained plaintext credential source on the
shell and MCP routes, but its matcher does not cover the file-write tools, so a
blanket `$HOME` write rule would open an unguarded path to exactly those files.

## Verified state, 2026-09-21

    python scripts/apply_unattended_permissions.py --list

    df7bb16a63efe7f7  /Users/wecaredigital/wecare-store
                      47 lines, 9 entries
                      ['shell', 'fs_read', 'fs_write', 'web_search', 'web_fetch', 'mcp']
                      hooks present=3/3

    user-level: 61 lines, 19 match entries
                ['shell', 'fs_read', 'fs_write', 'web_search', 'web_fetch', 'mcp']
                (was 28 lines / 23 literal path entries / fs_read+fs_write only)

`--list` now also reports the user-level file and warns when its match-entry
count suggests literals are accumulating again.

A new workspace needs both:

    python scripts/apply_unattended_permissions.py --root /path/to/project --user

Copy `.kiro/hooks/` and `.kiro/agents/` there first; the script refuses a
workspace missing the guards, which is the point.

**Already-open sessions keep the old policy.** Reload the Kiro window once after
this change, or the prompts continue for the rest of the current session.
