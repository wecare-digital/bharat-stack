# Findings — ratify redirects as data, assert the property

Branch `fix/routing-test-design`, rebased onto `origin/stack` at **`53f3ac2b`**
("Feat/public primary cta standardization (#190)"). Not pushed. The branch tip SHA is reported
in the step output rather than here, because this file is committed *in* that commit and cannot
name it without being amended into a lie.

`origin/stack` has now moved **four** times during this task — worktrees share `refs/`, so
another session's fetch advances it underneath this one: `a4144896` → `8c46b132` → `1c847107`
→ `53f3ac2b`. The branch was rebased and the gates re-run on each, which is the whole reason
the result below is a delta against a measured baseline rather than a total.

Files committed:

| Path | What |
|---|---|
| `tests/test_url_host_routing_rules.py` | rewritten; `RATIFIED_REDIRECTS` allowlist as data, 7 → **13** tests |
| `tests/test_legacy_redirect_rollback_snapshot.py` | one body changed, name preserved |
| `docs/execution/change-authority-matrix.md` | two appended rows, no existing row edited |
| `.agents/tasks/routing-test-design-20261002/{plan,findings,routing-review}.md`, `review.json` | the audit trail the matrix rows cite — **round 2 fix, see F1** |

**No production file changed.** `git diff origin/stack --stat -- scripts/ amplify/ src/ config/
public/ docs/execution/snapshots/` is empty, so `scripts/provision_legacy_redirects.py` is
byte-identical to the remote. No `--apply`, no `--verify`, no boto3 or Amplify call, no alias
moved, no flag changed.

---

## Round 2 — the three review findings, and what each fix cost

Review: `routing-review.md`, verdict `CHANGES_REQUESTED`. One blocking, two not.

### F1 (blocking) — the evidence was not in the commit

The round-1 matrix row ended "Full table in
`.agents/tasks/routing-test-design-20261002/findings.md`" and that file was **untracked**. A
durable audit row citing a path that does not exist in the repository is worse than a row with
no citation: it reads as evidenced. The repo already tracks 83 artefacts under `.agents/`,
including `findings.md` and `plan.md` for eight other tasks, so this was an omission rather
than a convention.

Fixed by committing all four artefacts — `plan.md`, this file, `routing-review.md` and
`review.json`. `.agents/` is not gitignored (`git check-ignore` exits 1 on the path), so
nothing had to change for them to be trackable.

### F2 — two by-name negatives sat after the set-equality

```
# before                                   # after
assert client.written == approved+rewrites  assert not any(... '/obsolete-login-fixture' ...)
assert approved[0] == removals[0]           assert all("/workspace" not in r["target"] ...)
assert not any(... '/obsolete-login-...')   assert approved[0] == removals[0]
assert all("/workspace" not in ...)         assert client.written == approved + rewrites
```

The round-1 commit message claimed by-name negatives sit before *every* set-equality. In
`test_owner_policy_preserves_rewrites_without_restoring_legacy_destinations` two of them did
not. The expressions are byte-unchanged; only their position moved, and `approved[0] ==
removals[0]` moved with them on the same reasoning — every assertion that can name the
offending rule now runs before the one that can only print a list diff.

This is not cosmetic, and M16/M16b below is the measurement. In the compound case the reviewer
predicted — a reordering defect *plus* a ratified reinstatement of the legacy login forwarding
— the old order fails on `At index 0 diff: {'source': '/api/<*>' ...}` and **never reports that
a customer URL is resolving into `/workspace/` again**. The new order fails on the named
assertion at line 195 and says so.

### F3 — passthrough shadowing compared raw string prefixes

`source.startswith(PASSTHROUGH_PREFIXES)` plus `passthrough.startswith(stem)` rejected
`/getting-started`, `/api-docs`, `/mcp-legacy` and `/r`, none of which can match an Amplify
passthrough pattern. An Amplify source is matched **as given, not normalised** — that is the
documented reason both `/zip` and `/zip/` have to be declared — so `/getting-started` cannot
match `/get/<*>`, `/get` or `/get/`. The owner retires and renames product pages as routine
work, so reddening on one of those spellings is the same failure class this redesign exists to
end, in smaller form.

Replaced with `_patterns_overlap(a, b)`, which asks the real question — can one request path
match both patterns — by splitting each pattern into its literal prefix and whether it
wildcards:

| | exact `b` | wildcard `b` (prefix `Lb`) |
|---|---|---|
| **exact `a`** | `a == b` | `a.startswith(Lb)` |
| **wildcard `a`** (prefix `La`) | `b.startswith(La)` | `La.startswith(Lb) or Lb.startswith(La)` |

`<*>` is read as matching any suffix, which is the conservative direction: it makes overlap
*easier* to detect, so the guard fails closed. The forward and reverse branches collapse into
one assertion that names the offending pair.

Three consequences worth recording:

1. **The passthrough set is now derived from the provisioner, not from a tuple.**
   `_is_passthrough()` is `not _is_redirect(rule) and source != "/<*>"` — the provisioner's own
   `is_ours()` classification, inverted. A rewrite added later is protected without anybody
   editing the test. The hand-kept list survives as `CRITICAL_PASSTHROUGHS`, a **coverage
   floor** recording what each of the four load-bearing rewrites carries, pinned by a new test
   (M15 kills it).
2. **The catch-all skip was tightened from `source == "/<*>"` to `rule == CATCH_ALL`.** The
   source-only form would have waved through a redirect-status `/<*>` rule, which shadows the
   entire site. The `assert stem` line that claimed to cover this was unreachable — it sat
   *after* the skip, so for the only input that could trigger it the test had already
   `continue`d. The property it claimed is now actually enforced, and is asserted by example
   (`("/<*>", "/api/<*>")` in the MUST OVERLAP table).
3. **Two tests added**, both for logic F3 introduced:
   `test_pattern_overlap_is_segment_aware_in_both_directions` (9 must-not-overlap pairs, 5
   must-overlap) and `test_the_critical_passthroughs_survive_the_write`.

---

## The design change (round 1, unchanged)

The guard asserted **how many** redirects exist. The owner adds and removes redirects as
ordinary product work, so that pin broke three times in one day, in both directions:

| | What happened |
|---|---|
| `c7afae00` | Landed a 540-line guard whose assertions were written around exactly one sanctioned redirect |
| `da78ef68` | Purging retired customer-link sources, deleted **420 of those lines** (38 insertions / 420 deletions), leaving a 2.8 KB stub. A **removal** took the guard out |
| `bb1cf39b` | Correctly declared `/zip -> /shipments/` and `/zip/ -> /shipments/` for the owner's product rename, taking `desired_redirects()` from 1 rule to 3. **Five** tests went red on a correct production change. An **addition** broke it |

A guard that reddens on every legitimate product change trains people to ignore it, and then
to delete it — which is literally what happened at step 2.

### What replaced it

`RATIFIED_REDIRECTS` is a `dict` held as data, keyed on the whole `(source, target, status)`
triple and valued by the instruction that sanctioned the entry. Keying on the triple means a
silently **retargeted** or **status-downgraded** redirect is caught too, not just a new source.
Insertion order is the expected array order, so one structure serves both the membership check
and the ordering check. Precedent: `UNDECLARED_ALLOWED` in `scripts/check_data_model_drift.py`,
pinned by `test_both_new_tables_are_allowed_in_the_drift_gate_with_a_reason`.

Adding or retiring a redirect is **one dict entry**. Mutation M2 proves that claim rather than
asserting it.

### The retired set is derived, not typed

The 2026-10-02 purge rewrote the retired public path to the literal
`[retired public path ef531503]` **inside the committed pre-change evidence itself**
(`docs/execution/snapshots/retired-url-rules-before-20261002.json`). A hand-typed `/access`
negative assertion would therefore match nothing in the fixture it reads: it would **pass while
proving nothing** — the same defect class as an assertion placed after a set-equality.
Re-typing `/access` would also reverse the owner's purge order on the exact string they asked
be removed.

`_retired_sources()` computes the set from the snapshot, and every caller asserts it is
**non-empty before** asserting absence. Vacuity is a test failure (M6), not a silent pass.

### Snapshot-against-snapshot became reconciliation

`test_saved_pre_removal_configuration_reconciles_to_post_removal_snapshot` asserted one
committed file reproduced another byte for byte. That is a property of two files, not of the
provisioner. Reconciling the 12-rule pre-change array now yields **11** rules while the
committed `after` file holds **9**, and editing that file to 11 would fabricate evidence for a
write that has not happened (`bb1cf39b`: "NOT APPLIED - THIS IS SOURCE ONLY"). The replacement,
`test_the_pre_change_array_reconciles_to_the_ratified_set_with_every_passthrough_preserved`,
computes its expectation from the provisioner and never reads `after`.

### Names that were lies, renamed to the property

| Was | Now |
|---|---|
| `test_only_host_canonicalisation_is_an_explicit_redirect` | `test_every_emitted_redirect_is_ratified_and_every_ratified_redirect_is_emitted` |
| `test_converged_configuration_is_not_rewritten` | `test_applying_the_policy_twice_writes_once` |
| `test_unknown_redirect_removed_without_touching_proxy_rules` | `test_an_unratified_redirect_is_dropped_and_no_passthrough_is_disturbed` |
| `test_saved_pre_removal_configuration_reconciles_to_post_removal_snapshot` | `test_the_pre_change_array_reconciles_to_the_ratified_set_with_every_passthrough_preserved` |
| `test_no_path_redirects_shadow_api_or_staff_pages` | `test_no_ratified_redirect_can_shadow_a_passthrough_or_target_the_staff_tree` |
| `test_missing_page_rule_stays_last` | `test_the_catch_all_is_last_and_unique_in_the_snapshot_and_in_the_write` |

`test_owner_policy_preserves_rewrites_without_restoring_legacy_destinations` was **not**
renamed. It contains no count, already names a property, and a durable audit row cites it by
name.

### Preserved deliberately

Negative assertions **by name, before** every set-equality — now true in both files, see F2.
Host rule first. Passthrough rules preserved in order, derived through the provisioner's own
`is_ours()` rather than compared to a snapshot. Catch-all last and unique. The `/workspace`
target ban. Non-overlap in **both** directions. `apply()` driven from a pre-removal array in
every test that inspects a write, with `client.written is not None` **asserted** rather than
assumed.

---

## Mutation results

Each mutation was reverted immediately. On the committed tree
`git diff origin/stack --stat -- scripts/ amplify/ src/ config/ public/
docs/execution/snapshots/` is empty, so no production file was left mutated.

**Re-measured in round 2** (against the rewritten tests):

| # | Mutation | Killed | Observed failure |
|---|---|---|---|
| M1 | Emit an unratified `/mutation-probe` 301 from `desired_redirects()` | `test_every_emitted_redirect_is_ratified_and_every_ratified_redirect_is_emitted` | "the provisioner emits redirects that nothing in this repo sanctions: 301 /mutation-probe -> /" |
| M5 | Drop `"302"` from the provisioner's `REDIRECT_STATUSES`, so the retired rules are preserved into the write | reconciliation test (**named**), rollback test (**named**), `test_an_unratified_redirect_is_dropped...`, `test_the_redirect_status_set_matches_the_provisioner` | "apply() preserved retired forwarding for `'[retired public path ef531503]'`" and "legacy redirect `'/obsolete-login-fixture/<*>'` was written to the app" |
| M12 | **M5 plus both named negative loops deleted** | reconciliation test **PASSES**; rollback test fails only on the opaque list diff at line 196 | See below — the result that justifies the design |
| M13 | **Invert** both named negatives on a clean tree (`not in` → `in`, `not any` → `any`) | reconciliation test, rollback test | Reachability, directly: both assertions execute |
| M8 | Ratify **and** emit `/api/legacy` 301 | shadowing guard | "redirect /api/legacy overlaps runtime rewrite(s) \['/api/<\*>'\] ... a shadowing rule is a payment outage" |
| M9 | Ratify **and** emit `/ap<*>` 301 | shadowing guard | Same message naming `/api/<*>` — the reverse direction still fires after the F3 rewrite |
| M14 | Revert `_patterns_overlap` to the round-1 raw-prefix comparison | `test_pattern_overlap_is_segment_aware_in_both_directions` | "/getting-started is reported as shadowing /get/<\*>, but an Amplify source is matched as given rather than normalised, so it cannot" |
| M15 | `apply()` drops the `/api/<*>` rewrite while preserving the rest | `test_the_critical_passthroughs_survive_the_write`, plus the two order-preservation equalities | "the /api/<\*> rewrite is gone from the reconciled array - it carries every provider webhook, including POST /api/razorpay-webhook" |
| M16 | **Compound**: `apply()` reorders its output (M10) **and** emits `/obsolete-login-fixture/<*> -> /workspace/...` 302 (M11) | rollback test, at the **named** `/obsolete-login-fixture` assertion, line 195 | The F2 fix measured — see below |
| M16b | M16 with the two negatives moved back below the equality, i.e. the pre-F2 arrangement | rollback test, at the **equality**, line 195 | "At index 0 diff: {'source': '/api/<\*>' ...}". The staff-tree reinstatement is never reported |

**Carried over from round 1**, consistent with the rewritten code but not re-run in round 2:
M2 (ratify the probe with one line → all tests pass, the one-line-ratification claim), M3
(ratified but not emitted → same test, reverse branch), M4 (empty ratification reason →
`test_every_ratified_redirect_records_why_it_is_sanctioned`), M6 (`_retired_sources` forced
empty → the anti-vacuity assert), M7 (reconciliation driven from `after` → fires earlier than
predicted, on the anti-vacuity assert), M7b (converged input → "apply() short-circuited").
M10 and M11 were re-run in round 2 only as components of M16.

### M12 is the result worth keeping

With the named negative loop deleted, the reconciliation test **passes on a tree where a
retired public path is live again**. The set-equality derives its expectation through the same
`is_ours()` the mutation broke, so both sides of the comparison move together and the equality
cannot see the reinstatement.

So the by-name assertions are not a friendlier error message for something the equality already
catches — **they are the only thing that catches it.** M13 confirms from the other side that
they actually execute. M8 and M9 add the point again: a redirect that is ratified *and* emitted
still fails the shadowing guard, so ratification buys no exemption from the payment-outage
check.

### M16/M16b is the result that justifies F2

Same defect, two assertion orderings, two different failure reports:

```
F2 fix in place   → tests/..._rollback_snapshot.py:195
                    assert not True
                    where True = any(r['source'].startswith('/obsolete-login-fixture') ...)

pre-F2 ordering   → tests/..._rollback_snapshot.py:195
                    At index 0 diff: {'source': '/api/<*>', ...} != {'source': 'https://www...'}
```

Both fail, so CI is red either way. The difference is what the engineer reading the log learns:
in the second case, that an array is in the wrong order; in the first, that a customer URL is
resolving into the staff workspace again. The reviewer's compound case was hypothetical when
raised and is measured here.

### Two mutations did not fail where round 1 predicted

Recorded rather than smoothed over.

- **M7** was predicted to fail on "apply() short-circuited". It fails on the **anti-vacuity
  assert** instead, which runs earlier: `after` holds no retired redirect, so
  `_retired_sources` returns empty and the test stops before `apply()`. **M7b** was added to
  isolate the write-path guard.
- **M11** was predicted to fail on the derived retired check as well as the `/workspace` ban. It
  does not, and this is inherent to a derived set: ratifying a source removes it from
  `_retired_sources`, so the derived loop stops naming it. The **hand-named** literals are what
  catch it. **Derivation covers unratified reinstatement; the named literals cover ratified
  reinstatement. Both are needed** — which is why F2 moved them where they can run.

---

## Gates

Rebased onto `origin/stack` at `53f3ac2b` **before** the final run.

**Targeted delta** — the two files, measured on a clean detached worktree at `origin/stack`
versus this branch:

```
origin/stack  53f3ac2b :  11 collected,  5 failed,  6 passed
this branch            :  17 collected,  0 failed, 17 passed
```

The 5 named failures `bb1cf39b` introduced now pass:
`test_only_host_canonicalisation_is_an_explicit_redirect`,
`test_converged_configuration_is_not_rewritten`,
`test_unknown_redirect_removed_without_touching_proxy_rules`,
`test_saved_pre_removal_configuration_reconciles_to_post_removal_snapshot` and
`test_owner_policy_preserves_rewrites_without_restoring_legacy_destinations`.
**+6 net new tests** — `test_url_host_routing_rules.py` goes 7 → 13, the rollback file stays
at 4.

**Full suite**, `/Users/wecaredigital/wecare-store/.venv/bin/python -m pytest -q` from the
worktree root:

```
baseline, clean worktree at 53f3ac2b :  6 failed, 6792 passed, 1 skipped, 7 xfailed
this branch                          :  1 failed, 6803 passed, 1 skipped, 7 xfailed
```

The one remaining failure is `tests/test_blog_ledger.py::test_the_committed_ledger_if_present
_reconciles` and it is **upstream, not mine** — proven by parity, not asserted: the clean
detached worktree at `53f3ac2b`, carrying none of my commits, fails the identical test, and the
same measurement held at `8c46b132` and `1c847107`. Its inputs are byte-identical to the remote
in my tree.

Deliberately reported as a **delta**, not a repository-wide total, per the 2026-10-02 correction
row in the change-authority matrix: an absolute pass count goes stale the moment another session
pushes, and `origin/stack` moved four times during this task alone.

---

## Found but not fixed

1. **`test_the_committed_ledger_if_present_reconciles` is red on `origin/stack`.** Five articles
   in `content/conversations/batches/CONV-332-002.json` have no ledger row, so their source
   provenance is unrecorded. Introduced by `8c46b132`, still red at `53f3ac2b`. Out of scope
   here (test-only brief, different workstream) and it belongs to whoever owns the Conversations
   publishing work. Flagging it because it means `origin/stack` is **not** currently green.
2. **The `after` snapshot is stale as a description of intent, and deliberately left alone.**
   `amplify-custom-rules-after-url-host-cleanup-20261001.json` holds 9 rules; reconciling the
   pre-change array yields 11. It is measured live state and `--apply` has not run since `/zip`
   was declared, so refreshing it would fabricate evidence for a write that has not happened.
   Whoever runs `--apply` should refresh it **then** — and at that point
   `test_the_two_committed_snapshots_differ_only_in_redirect_rules` and
   `test_the_host_rule_is_first_and_carries_no_path` will still hold, because both assert
   properties rather than a byte-for-byte match.
3. **`verify()` compares live rules to `desired_redirects()` for exact equality**, so it reports
   FAIL on the current live app until `--apply` runs. The provisioner's own docstring says this
   is the expected pre-apply state. Not a defect; noted so a future reader does not treat that
   FAIL as drift.
4. **The provisioner was checked against the brief's stop condition and is correct.** A rename
   needs a 301, both URL forms need declaring because an Amplify source pattern is matched as
   given rather than normalised, and the target needs its trailing slash or `/shipments` would
   itself redirect before resolving. `apply()` snapshots before writing, refuses without exactly
   one `404-200` catch-all, and preserves non-redirects in order. No change was made or needed.
5. **`_patterns_overlap` reads `<*>` as matching any suffix, and that is an assumption.** It is
   the conservative one — it makes overlap easier to detect, so the guard fails closed — and the
   only place it could bite is a hypothetical mid-segment wildcard like `/zip<*>`, which would
   be reported as overlapping `/zipper`. Nothing in the live array or the ratified set uses that
   shape. If Amplify is ever confirmed to treat `<*>` as single-segment, the predicate gets
   stricter, not looser, so no assertion in this file would start passing wrongly.
6. **`.scratch/round1_test_url_host_routing_rules.py` was used as a reference and not
   committed.** `.scratch/` is gitignored (`.gitignore:133`). It carries the round-1 `/access`
   literals, which is exactly what the derived-set design exists to avoid reintroducing.
