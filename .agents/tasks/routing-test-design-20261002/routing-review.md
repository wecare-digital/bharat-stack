# Redirect ratification as data in the URL-routing guard

`fix/routing-test-design` at `240f2bc9` replaces a redirect guard that asserted **how many**
redirects exist with one that asserts **which redirects are sanctioned and why**.
`RATIFIED_REDIRECTS` is a dict in `tests/test_url_host_routing_rules.py` keyed on the whole
`(source, target, status)` triple and valued by the instruction that authorised each entry, so a
retarget or a status downgrade needs ratifying just as a new source does. The guard broke three
times in one day in both directions - a removal deleted 420 lines of it, then a correct
`/zip -> /shipments/` rename reddened five tests - and the redesign addresses the class rather
than the instance. The structural invariants the brief asked to preserve are all still asserted,
and two are stronger than before: passthrough order is derived through the provisioner's own
`is_ours()` instead of compared to a snapshot, and the shadowing check runs on what `apply()`
writes rather than on a committed file that predates the sanctioned redirect.

Watch for: the mutation evidence and the matrix row both cite
`.agents/tasks/routing-test-design-20261002/findings.md`, and that file is **untracked** - the
commit carries three files, and the repo tracks 83 other `.agents/` artefacts including eight
other `findings.md` (confirmed). The commit message claims by-name negatives sit before *every*
set-equality; two of them in the rollback test sit after it (confirmed). The new passthrough
shadowing check compares raw string prefixes, so `/getting-started` is rejected as shadowing
`/get/<*>` (confirmed).

**Verdict**: NEEDS_CHANGES

## High-level view

The allowlist is genuinely data. Each of the three entries carries a multi-sentence reason,
`test_every_ratified_redirect_records_why_it_is_sanctioned` refuses a reason under 40 characters,
and insertion order doubles as the expected array order so one structure serves both the
membership check and the ordering check. Mutation M2 demonstrates the one-line claim rather than
asserting it: a probe redirect plus one dict entry and all 15 tests pass.

The retired-source check is derived from the committed pre-change snapshot rather than typed, and
the reason is specific. The 2026-10-02 purge rewrote the retired path to the literal
`[retired public path ef531503]` *inside that snapshot*, so a hand-typed `/access` assertion would
match nothing in the fixture it reads and would pass while proving nothing. `_retired_sources()`
computes the set and every caller asserts it non-empty first, so vacuity is a failure.

M12 is the result that justifies the by-name design. With the named negative loop deleted, the
reconciliation test **passes** on a tree where a retired public path is live again, because the
set-equality derives its expectation through the same `is_ours()` the mutation broke - both sides
move together. The named loops are not a friendlier message for something the equality already
catches; they are the only thing that catches it.

Two by-name negatives were not moved. In `test_owner_policy_preserves_rewrites_without_restoring_legacy_destinations`
the new derived loop sits before the equality as intended, but the preserved
`/obsolete-login-fixture` and `/workspace` assertions remain after it at lines 191-192. They were
kept byte-unchanged on purpose, and in the M11 scenario they do still run because that equality is
self-consistent - but M10 shows an equality in this area that fails first, and the commit message
states a stronger claim than the code supports.

The shadowing guard is stronger than what it replaced and over-strict in a narrow way. The
comparison is `str.startswith`, not segment-aware, so a future `/getting-started` or
`/mcp-legacy` redirect reddens the gate without being able to shadow anything. That is the same
failure mode this change exists to eliminate, in smaller form. It fails closed.

The production surface is untouched: zero changes under `scripts/`, `amplify/`, `src/`, `config/`,
`public/` or `docs/execution/snapshots/`, and `provision_legacy_redirects.py` is byte-identical to
the remote. What is missing from the commit is the evidence, not the restraint - the matrix row
points at a findings file that is not in git.

<details>
<summary>Issues (3)</summary>

1. **Mutation evidence is not in the commit** — `findings.md` and `plan.md` under
   `.agents/tasks/routing-test-design-20261002/` are untracked, while the committed
   change-authority row says "Full table in
   `.agents/tasks/routing-test-design-20261002/findings.md`". Stage both (plus this review and
   `review.json`) so the durable row cites a path that exists in the repository.
2. **Two by-name negatives sit after the set-equality** —
   `tests/test_legacy_redirect_rollback_snapshot.py:191-192` keeps the `/obsolete-login-fixture`
   and `/workspace` assertions after `assert client.written == approved + rewrites` on line 189.
   Move them above line 189, or drop the commit message's claim that by-name negatives precede
   every set-equality.
3. **Passthrough shadowing uses a raw string prefix** —
   `source.startswith(PASSTHROUGH_PREFIXES)` and `passthrough.startswith(stem)` in
   `test_no_ratified_redirect_can_shadow_a_passthrough_or_target_the_staff_tree` reject
   `/getting-started`, `/api-docs`, `/mcp-legacy` and `/r`, none of which can match an Amplify
   passthrough pattern. Compare on segment boundaries (prefix, or prefix + `/`).

</details>

<details>
<summary>Details</summary>

## From a count pin to a ratified set

Keying on `(source, target, status)` is what makes this a guard rather than a source inventory:
`/zip -> /elsewhere/` and `/zip -> /shipments/` at 302 are both unratified, so a silent retarget
or a 301-to-302 downgrade needs ratifying like a new rule. Both directions are asserted, and the
messages name the offending rules:

```python
unratified = [r for r in emitted if _rule_key(r) not in RATIFIED_REDIRECTS]
missing    = [r for r in RATIFIED_RULES if r not in emitted]
...
assert emitted == RATIFIED_RULES, "emitted redirects differ from the ratified set in ORDER"
```

The ratified-but-unemitted direction matters more than it looks: a sanctioned redirect quietly
disappearing means inbound links start 404ing, which is the failure `/zip` was declared to fix.

Against the two reference tests, the standard is met by different means.
`test_meta_version.py` scans a tree because its subject is eleven files; here the subject is one
function, so the invariant is asserted against `desired_redirects()` directly.
`test_payment_vocabulary_at_decision_points.py` pairs a data set with a test pinning the data
set's own scope (`test_paid_is_deliberately_not_in_the_forbidden_set`), and
`test_every_ratified_redirect_records_why_it_is_sanctioned` plays that role - a gate satisfiable
with `""` is a gate somebody switches off.

The allowlist's scope claim holds: the provisioner is the only emitter of explicit redirects.
`scripts/deploy_mcp_server.py` is the other writer of `customRules` and its `HOSTING_RULES` are
both `200` rewrites; there is no `public/_redirects` and no `redirects` block in the Next config.

## Why the derived retired set cannot be replaced by the equality

The reconciliation test's expectation is
`RATIFIED_RULES + [r for r in before if not redirects.is_ours(r)]`, and `is_ours()` is the
provisioner's own classifier. M5 breaks that classifier (drops `"302"` from `REDIRECT_STATUSES`),
so the retired rules are preserved into the write *and* into the expectation simultaneously - the
equality cannot see them. `_retired_sources()` reads the test module's own `REDIRECT_STATUSES`
copy, which is independent of that mutation and separately pinned by
`test_the_redirect_status_set_matches_the_provisioner`. M12 is M5 with the named loops deleted,
and the test passes: a kill the coder could not get, recorded rather than smoothed over.

Against the real pre-change snapshot the derived set resolves to the three
`[retired public path ef531503]` forms at 302, so the absence assertion is not vacuous, and the
anti-vacuity assert is itself pinned by M6.

## Two by-name negatives were left after the equality

```
183:    for source in sorted(retired):          # derived, named, correctly placed
189:    assert client.written == approved + rewrites
191:    assert not any(r['source'].startswith('/obsolete-login-fixture') for r in approved)
192:    assert all("/workspace" not in r["target"] for r in approved)
```

The findings doc explains why these two were kept byte-unchanged: M11 showed that ratifying a
source removes it from the derived set, so a *ratified* reinstatement is caught only by the
hand-named literals. That reasoning is an argument for moving them up, not for leaving them
downstream of an equality. In M11 itself they do run, because `client.written` and
`approved + rewrites` both derive from `approved` and the equality holds regardless of its
contents. M10 is the counter-case: a reordering mutation fails the equality first, so in a
compound reorder-plus-reinstate the only assertions that can see the reinstatement never execute.

The commit message says "PRESERVED DELIBERATELY: negative assertions BY NAME placed BEFORE every
set-equality", and the module docstring calls an assertion after a set-equality "the same defect
class" as a vacuous one. Code and record disagree.

## The shadowing check over-rejects

The premise change is right and the old test was a time bomb - it asserted no rule in the `after`
snapshot is a path redirect, which held only because that snapshot predates `/zip` and `--apply`
has not run. Running on `apply()`'s output in both directions is the stronger property, and the
reverse stem branch catches what ordering never could (`/ap<*>` swallowing `/api/<*>`).

Both branches compare raw string prefixes. Measured:

```
/getting-started   forward_reject=True   reverse_hits=[]
/api-docs          forward_reject=True   reverse_hits=[]
/mcp-legacy        forward_reject=True   reverse_hits=[]
/r                 forward_reject=False  reverse_hits=['/r/<*>']
/zip               forward_reject=False  reverse_hits=[]
```

An Amplify source pattern is matched as given rather than normalised - the file's own `/zip/`
entry says so, and it is why both `/zip` forms are declared. By that same rule
`/getting-started` cannot match `/get/<*>` and `/r` cannot match `/r/<*>`. The owner retires and
renames product pages as routine work, so one of these is a plausible next entry, and it would
redden a gate written to stop reddening on legitimate product change. `/r/` already carries its
trailing slash; `/api`, `/get` and `/mcp` do not. The fix is a segment-aware comparison.

## apply() is exercised, and reconciliation replaced file-reproduces-file

Every test that inspects a write drives `apply()` from the 12-rule pre-change array and asserts
`client.written is not None` with a message naming the failure ("apply() short-circuited - the
write path was not exercised"). M7b isolates that guard by feeding a converged array while
keeping `retired` derived from `before` - which is also the honest record of M7 firing earlier
than predicted, on the anti-vacuity assert instead.

`test_the_pre_change_array_reconciles_to_the_ratified_set_with_every_passthrough_preserved`
computes its expectation from the provisioner and never opens the `after` file. The arithmetic
checks out against the real snapshots: 12 rules in, 3 ratified redirects plus 8 preserved
non-redirects out, against 9 in the committed `after` file. Editing that file to 11 would
fabricate evidence for a write that has not happened; the findings doc flags its staleness as
disclosed-and-deliberate rather than quietly refreshing it.
`test_the_two_committed_snapshots_differ_only_in_redirect_rules` and
`test_the_host_rule_is_first_and_carries_no_path` both survive a future `--apply` refresh because
they assert properties.

## Scope and record

The commit is three files. `git diff` against the base for `scripts/`, `amplify/`, `src/`,
`config/`, `public/` and `docs/execution/snapshots/` is empty. No `--apply`, no Amplify call, no
alias move, no flag change - consistent with the A1_LOCAL class the matrix row claims.

The commit message does the cross-session job: it names the two files it does not own, states the
orchestrator authorisation, lists the three recurrences with their SHAs, says what was *not*
reverted (provisioner byte-unchanged, both committed snapshots untouched), and explains why
`test_owner_policy_preserves_rewrites_without_restoring_legacy_destinations` keeps its name - a
durable audit row cites it. I grepped the six old test names across the tree: nothing in `docs/`,
CI or source cites a renamed test as a live target.

What the record is missing is its own evidence. The matrix row ends "Full table in
`.agents/tasks/routing-test-design-20261002/findings.md`", and that file is untracked along with
`plan.md`. The repo tracks 83 files under `.agents/`, including `findings.md` and `plan.md` for
eight other tasks, so this is an omission rather than a convention.

## Base is not green, and that is disclosed

The branch is rebased onto `origin/stack` at `1c847107`, where
`test_blog_ledger.py::test_the_committed_ledger_if_present_reconciles` fails. The findings doc
establishes by parity - a clean detached worktree at the same SHA failing the identical test, with
the inputs byte-identical to the remote - that it is upstream, introduced by `8c46b132`, and
belongs to the Conversations publishing workstream. Out of scope here, and flagged rather than
absorbed into this change's result.

## Verification I ran

One narrow spot-check, per the brief: `tests/test_url_host_routing_rules.py` alone, reporting
`11 passed in 0.26s`. That confirms the allowlist matches `desired_redirects()` as committed and
that the module-scoped provisioner fixture collects cleanly under per-test `monkeypatch`. The
remaining mutation claims I checked by reading the code against the real snapshots rather than
re-running them - M3, M5, M6, M7b, M8, M9, M10, M11 and M12 are each consistent with the
provisioner's `apply()` shape and the fixture contents.

</details>

<details>
<summary>File map</summary>

- `tests/test_url_host_routing_rules.py` — rewritten; `RATIFIED_REDIRECTS` allowlist as data, 7 -> 11 tests, derived retired set, both shadowing directions asserted on `apply()`'s output
- `tests/test_legacy_redirect_rollback_snapshot.py` — one body changed; `assert approved == [removals[0]]` count pin deleted, derived-and-named retired check added before the equality, test name preserved
- `docs/execution/change-authority-matrix.md` — one appended row, no existing row edited

Full diff: `git -C /Users/wecaredigital/wecare-store/.worktrees/routing-tests diff 1c847107..240f2bc9`

Untracked, referenced by the committed row but not in the commit:
`.agents/tasks/routing-test-design-20261002/findings.md`, `plan.md`

</details>
