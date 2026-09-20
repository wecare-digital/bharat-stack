# Running multiple sessions and agents at once

Adopted 2026-09-20 after measuring this workspace with three warm sessions live.
Covers how concurrency actually behaves here, why permissions are wide open, and
the rules that keep parallel work from destroying itself.

## What is and is not isolated

Local sessions share **everything on disk** and isolate **only conversation
context**. Measured, not assumed:

| Shared across sessions | Isolated per session |
|---|---|
| working tree, git index, `HEAD` | conversation history, context window |
| the `.venv`, `node_modules`, build output | checkpoint set |
| AWS credentials and live AWS resources | spec task state |
| steering, hooks, MCP servers | |

There is no per-session staging area and no merge step. Outcomes converge by
last-writer-wins on each file.

**Checkpoints are the sharp edge.** A session only snapshots files *its own* file
tools touched. If session A reverts a turn, edits session B made to the same file
are discarded with no record that it happened. Git is the only shared source of
truth between sessions, which is why tree-wide git commands are the dangerous
ones and why a hook refuses them.

True isolation requires a cloud session (server-side clone, up to 10 concurrent,
but no Supervised mode and no checkpoints) or a separate checkout. A second local
session in the same folder is not isolation.

## Permissions are deliberately wide, and that is the safer configuration

`~/.kiro/workspace-roots/df7bb16a63efe7f7/permissions.yaml` holds **six** wildcard
rules: `shell`, `fs_read`, `fs_write`, `web_search`, `web_fetch`, `mcp`. It
replaced 156 accumulated "Always allow" entries on 2026-09-20.

This is not a relaxation of security, it is a different control surface, and it is
a net reduction in leak risk:

- The old list contained 12 artifacts that could never match a real program
  (`$G *`, `break *`, `check *`, `": *"`) and 6 literal one-off command strings.
  Those literals are the **exact mechanism** that wrote four live credentials into
  this file on 2026-09-19: "Always allow" records the whole command string, secret
  included, permanently. `match: ['*']` cannot do that. Six lines that never grow
  and never embed command text.
- It had no `fs_read`/`fs_write` rule at all, so every edit prompted, and
  `web_fetch` was pinned to 9 domains with `mcp` pinned to 3 tools. Those gaps are
  what stalled long runs: the agent hit command 157 and stopped dead.

Safety moved from *prompts* to *guards*. Prompting is a poor control for
unattended work: it blocks the 999 safe commands and relies on a tired human to
catch the one bad one. Three PreToolUse hooks **deny without asking**, which is
what makes them compatible with blanket allow:

| Hook | Refuses |
|---|---|
| `block-inline-secrets` | issuer-shaped credentials anywhere in a command |
| `block-broad-git-staging` | `git add .` / `-A` / `-u`, `git commit -a`, bare `git stash` |
| `block-catastrophic` | `rm` on `/`, `$HOME`, `~/.aws`, `~/.ssh`, `~/.kiro`, repo root; destruction of the retained plaintext source; `chmod` widening; disk writes; `aws secretsmanager get-secret-value` |

`block-catastrophic` additionally *asks* before destructive AWS deletes, because
`maintenance-reporting` already requires pointwise confirmation for those.

**Removing a hook removes the justification for the permissions file.** Do not
disable one to get past a block. Read the message and take the alternative it
names. `apply_unattended_permissions.py` refuses to write the policy to a
workspace missing these hooks unless forced.

## Rules for concurrent work

1. **Assign file ownership before starting.** State each session's owned paths in
   its prompt. Two sessions must never own the same file. If they would, sequence
   them instead.
2. **One committer.** Nominate a single session to run `git add` / `commit` /
   `push`. Others leave changes in the tree and report. Concurrent pushes to
   `stack` race and the loser gets a non-fast-forward.
3. **Stage by explicit path, always.** `git add <paths>`, never `.` or `-A`. On
   2026-09-20 a tree-wide stage would have swept four files belonging to another
   session into an unrelated commit.
4. **Check before you stage.** `git status --short` plus
   `python scripts/session_map.py`. If a modified file is not yours, leave it.
5. **A spec belongs to one session.** `~/.kiro/spec-sessions/<hash>.json` maps one
   spec to one session id. Driving the same spec from a second session forks the
   task state. Resume the owning session instead.
6. **Commit before fanning out.** Untracked work plus a new parallel session is
   how unrelated changes end up in one commit.

## How many can actually run

`python scripts/session_map.py` prints the live answer. On this Mac (Mac17,3, 10
logical cores, 16 GB) it reports **3**, and CPU is the binding constraint, not RAM
— the Kiro tree already held 3.05 GB across 19 processes at load 3.95. Going past
that makes every session slower rather than finishing more work.

## Doing it

**Same repo, parallel sessions.** Open extra sessions with `+` in the chat panel,
or use Agent Focus Mode, which is the surface built for parallel sessions with
per-session status and an attention bell for approval asks. Give each one disjoint
paths.

**Different project.** `kiro -n /path/to/other/project` opens it in a new window
with its own sessions. Permissions are per workspace root, so grant the new
project the same policy with:

    python scripts/apply_unattended_permissions.py --root /path/to/other/project

Copy `.kiro/hooks/` and `.kiro/agents/` across first; the script will refuse
otherwise, which is the point.

**Headless fan-out.** `kiro-cli chat --no-interactive --agent <name> "<prompt>"`
runs a session with no TTY, one process per invocation, and honours `cwd` — so the
same command shape covers one repo or several. `--trust-tools=` narrows the
toolset when a worker should not need everything.

**One big goal, many items.** Use the `fleet-lead` agent. It writes the work-item
list to `.kiro/work/<slug>/plan.md` **before** starting, quotes the acceptance
criteria verbatim, dispatches a `fleet-worker` per item with an explicit owned-path
list, verifies each item itself rather than trusting the worker's claim, and
commits per item by path. The plan living on disk is the point: a fifteen-item run
does not degrade at the tail, because the requirements are re-read rather than
remembered, and an interrupted or autocompacted run resumes from the file.

## Inspecting and repairing

    python scripts/session_map.py                  # who is live, where, and capacity
    python scripts/session_map.py --json
    python scripts/session_map.py --stale-locks     # dead locks, exit 1 if any
    python scripts/apply_unattended_permissions.py --list
    python scripts/repair_kirocrew_paths.py --verify

KiroCrew was first run from its disk image, so 27 recorded paths pointed at
`/Volumes/KiroCrew` after the image was ejected, leaving a dangling
`~/.local/bin/kirocrew` and every `kirocrew-*` agent unable to load its prompt.
Repaired 2026-09-20 to `/Applications/KiroCrew.app`, where the backend was
installed all along. Still outstanding: the four `pptx-maker` vendor prompts under
`~/.kiro/crew/apps/pptx-maker/data/vendor/` are genuinely absent rather than
mis-pathed, so that app needs reinstalling to load.
