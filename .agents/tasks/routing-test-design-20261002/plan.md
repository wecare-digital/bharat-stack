# Implementation Plan — ratify redirects as data, assert the property

Worktree: `/Users/wecaredigital/wecare-store/.worktrees/routing-tests`
Branch: `fix/routing-test-design` at `a4144896` (== `origin/stack`), clean tree.
Interpreter: `/Users/wecaredigital/wecare-store/.venv/bin/python` (bare `python` is not on PATH;
`conftest.py` refuses anything older than 3.12 with a `UsageError`).

Two files change. Nothing else. No production file, no snapshot, no provisioner behaviour.

---

## What was measured before planning

```
.venv/bin/python -m pytest tests/test_url_host_routing_rules.py \
                           tests/test_legacy_redirect_rollback_snapshot.py -q
→ 5 failed, 6 passed
```

`desired_redirects()` now emits **three** rules (`provision_legacy_redirects.py:40-85`):
`https://www.wecare.digital → https://wecare.digital` (301), `/zip → /shipments/` (301),
`/zip/ → /shipments/` (301). The five failures are all the same shape: a test that pins the
emitted set, or an array derived from it, to a hard-coded expectation of one rule.

### Five findings that change the design. Read these before writing code.

**F1 — the round-1 guard is gone from the tree.** `c7afae00` landed a 540-line
`tests/test_url_host_routing_rules.py` carrying `RETIRED_ACCESS_SOURCES`, the ordered negative
assertions, the passthrough non-overlap property, the `/workspace` ban and the bare-origin host
check. `da78ef68` ("purge obsolete customer link sources and Wix page inventory") deleted
**420 of those lines** (`git show --stat da78ef68 -- tests/test_url_host_routing_rules.py`
reports `38 insertions(+), 420 deletions(-)`). HEAD holds a 2.8 KB stub. So this task is not
only "make the allowlist data" — the preserved-property list in the brief has to be **restored**,
not merely kept. The round-1 text is recoverable with
`git show c7afae00:tests/test_url_host_routing_rules.py` and is already saved at
`.scratch/round1_test_url_host_routing_rules.py` (gitignored scratch, do not commit it).

**F2 — a hard-coded `/access` negative assertion would be VACUOUS, and `/access` must not be
re-typed.** The purge rewrote the retired source to the literal `[retired public path ef531503]`
inside the committed pre-change evidence itself:

```
docs/execution/snapshots/retired-url-rules-before-20261002.json
  {"source": "[retired public path ef531503]",      "target": ".../?from=access", "status": "302"}
  {"source": "[retired public path ef531503]/",     ...}
  {"source": "[retired public path ef531503]/<*>",  ...}
```

`docs/execution/retired-url-forwarding-removal-20261002.md` and `tests/test_module_homes.py:146`
carry the same redaction. Round 1's `RETIRED_ACCESS_SOURCES = ("/access", "/access/",
"/access/<*>")` asserted against that fixture would never match anything, so it would pass while
proving nothing — the same defect class as an assertion placed after an equality. **Derive the
retired set from the snapshot** instead of re-typing it, and guard the derivation against
emptiness. Do not reintroduce the `/access` literal; that reverses the owner's purge order.

**F3 — `test_no_path_redirects_shadow_api_or_staff_pages` passes today and is a time bomb.** It
asserts no rule in the committed `after` snapshot is a path redirect. `/zip` **is** a sanctioned
path redirect; the test survives only because the snapshot predates it and `--apply` has not run
(`bb1cf39b`: "NOT APPLIED - THIS IS SOURCE ONLY"). It fails the moment anyone applies the policy
and refreshes the snapshot. It encodes the identical wrong premise and is in scope.

**F4 — the `after` snapshot can no longer be the expected output, and must not be edited.**
`amplify-custom-rules-after-url-host-cleanup-20261001.json` is 9 rules and is *measured live
state*. Reconciling the 12-rule pre-change array now yields **11** rules (3 ratified + 8
non-redirects). Rewriting that snapshot to 11 would fabricate evidence for a write that has not
happened. The reconciliation test must compute its expectation from the provisioner, and relate
to the snapshot only through properties that survive a redirect being added.

**F5 — the rollback test's name must NOT be renamed.**
`test_owner_policy_preserves_rewrites_without_restoring_legacy_destinations` contains no count,
already names a property, and is cited by name in a durable audit row at
`docs/execution/change-authority-matrix.md:875`. Its *body* is wrong (`assert approved ==
[removals[0]]`); the name is not.

---

## Design decisions

**D1 — the allowlist is a `dict` keyed on the whole rule, valued by the reason.** Matching the
in-repo precedent `UNDECLARED_ALLOWED` in `scripts/check_data_model_drift.py`, pinned by
`tests/test_coupons_iam_and_table.py::test_both_new_tables_are_allowed_in_the_drift_gate_with_a_reason`
— which asserts the reason is non-empty and names its owner, because "a gate that fires on a
decision already taken is a gate somebody switches off".

```python
RATIFIED_REDIRECTS: dict[tuple[str, str, str], str] = {
    ("https://www.wecare.digital", "https://wecare.digital", "301"):
        "Host canonicalisation, restored 2026-10-01T08:59:52Z. Source and target are bare "
        "origins with no path, which is what makes Amplify carry the request path across - "
        "measured, www /shop/ -> apex /shop/, not apex home. Evidence: "
        "docs/execution/url-host-matrix-20261001.md.",
    ("/zip", "/shipments/", "301"):
        "RENAMED, not retired. bb1cf39b: the owner retired the product name Zip on 2026-10-02 "
        "and the page moved to /shipments/ with content unchanged. retired_url_equity.py: a 404 "
        "is correct for a page deleted because it was wrong and WRONG for a page that was "
        "replaced, because it discards link equity. Measured before: /zip 301 -> /zip/ -> 404, "
        "a redirect chain ending in a dead end.",
    ("/zip/", "/shipments/", "301"):
        "The canonical form under next.config trailingSlash. Both forms are declared because "
        "an Amplify source pattern is matched as given, not normalised, and links in the wild "
        "carry both - declaring one leaves the other 404ing. Target keeps its trailing slash "
        "because /shipments would itself redirect before resolving. 301 not 302: only a "
        "permanent redirect consolidates ranking.",
}
```

Keyed on the full `(source, target, status)` triple so a silently retargeted or downgraded
redirect is caught too, not just a new source. Insertion order is the expected array order
(dicts are ordered), so one structure serves both the set check and the order check.
`RATIFIED_RULES = [dict(zip(("source", "target", "status"), k)) for k in RATIFIED_REDIRECTS]`.

Adding or removing a redirect is then **one dict entry**, with the instruction that sanctioned
it recorded next to it. That is the whole point of the exercise.

**D2 — the retired set is derived, then named.** `_retired_sources(before)` =
`{sources of redirects in the pre-change array} − {ratified sources}`. The test asserts the
derived set is **non-empty** before using it (anti-vacuity), then asserts each member absent
**by name**, in a loop, with the source in the failure message. This satisfies "asserted BY NAME"
without hard-coding a spelling the purge has already changed once (F2), and it keeps working
when the next removal lands.

**D3 — the allowlist lives only in `tests/test_url_host_routing_rules.py`.** One owner, no
duplication, no cross-module import. The rollback-snapshot test asserts only properties it can
derive from its own fixtures (its `removals` list is its own data), so it never needs the
allowlist. Rejected alternatives: duplicating it in both files (drift — the exact failure mode
this task exists to end); a new `tests/ratified_redirects.py` helper (`pytest.ini` sets
`--import-mode=importlib` and `tests/conftest.py` adds only `amplify/functions/shared` to
`sys.path`, so a bare `import` would not resolve and the fix would need a sys.path edit to
support a data constant).

**D4 — no skip gate.** Round 1's `_require_converged_provisioner()` skipped when the provisioner
had not converged. It has (`WWW_CANONICAL` is emitted). A skip that can never fire is dead code;
one that can fire hides failures. Replace it with a positive assertion that the host rule is
emitted — the same precondition stated as a requirement.

**D5 — the provisioner's own `is_ours` classifies, wherever it is in scope.** Round 1's note
holds: deriving the expectation through `redirects.is_ours` asserts the policy rather than a
hard-coded slice that stops meaning anything when a rule moves. Keep a module-level
`REDIRECT_STATUSES` for the two pure-snapshot tests that have no provisioner in scope, and add
one cheap test asserting it equals `redirects.REDIRECT_STATUSES` so the two cannot drift.

**D6 — the provisioner is right; the tests are wrong.** Checked against the brief's stop
condition. `desired_redirects()` is correct (a rename needs a 301, both URL forms need declaring,
the target needs its trailing slash); `apply()` is correct (snapshot before write, catch-all
refusal, non-redirects preserved in order); `is_ours()` correctly excludes the `404-200`
catch-all. Nothing in `scripts/provision_legacy_redirects.py` changes.

---

## Plan

- [ ] 1. Add the allowlist, the derivation helpers and the module docstring to
      `tests/test_url_host_routing_rules.py`.
      Define `RATIFIED_REDIRECTS` and `RATIFIED_RULES` exactly as in D1; keep `WWW_CANONICAL`,
      `CATCH_ALL`, `REDIRECT_STATUSES` and restore `PASSTHROUGH_PREFIXES = ("/api", "/get",
      "/r/", "/mcp")` from `c7afae00`. Add `_is_redirect`, `_is_passthrough`,
      `_rule_key(rule)` and `_retired_sources(rules)`. Replace the one-line docstring with the
      WHY: that this file pins the *shape* of the Amplify array and the *ratification* of its
      redirects, not a count — pinning the count failed twice in two days, once on a removal
      (`c7afae00`) and once on an addition (`bb1cf39b`), and a guard that reddens on every
      legitimate change trains people to ignore it. Cite `tests/test_meta_version.py`
      ("a count in a document goes stale, a grep does not") as the precedent, and record F2:
      the retired set is derived rather than typed, because the literal it would name has been
      redacted out of the very snapshot the assertion reads.
      Promote the `redirects` fixture to `scope="module"` and register it in `sys.modules`,
      matching `tests/test_legacy_redirect_rollback_snapshot.py:57-65`. Rename the `rules`
      fixture to `after` and add a `before` fixture reading
      `docs/execution/snapshots/retired-url-rules-before-20261002.json`.
      Files: `tests/test_url_host_routing_rules.py`
      Verify: `.venv/bin/python -m pytest tests/test_url_host_routing_rules.py -q --co` collects
      without error (import-time only; failures are expected until item 5).

- [ ] 2. Replace `test_only_host_canonicalisation_is_an_explicit_redirect` with
      `test_every_emitted_redirect_is_ratified_and_every_ratified_redirect_is_emitted`.
      Body, in this order: assert `WWW_CANONICAL in emitted` (D4); then **by name**, each
      unratified emitted rule — `unratified = [r for r in emitted if _rule_key(r) not in
      RATIFIED_REDIRECTS]`, asserted empty with each offending source in the message and the
      remedy spelled out ("add one entry to RATIFIED_REDIRECTS recording the instruction that
      sanctioned it"); then the reverse, each ratified rule not emitted (an allowlist is not a
      one-way sink — a ratified redirect the provisioner stopped emitting is drift too); then
      `emitted == RATIFIED_RULES` for exact order. The two by-name loops sit **before** the
      equality deliberately: the equality catches the same thing with a message a reader has to
      decode, and an assertion placed after it could never run.
      Files: `tests/test_url_host_routing_rules.py`
      Verify: part of item 5's run.

- [ ] 3. Add `test_every_ratified_redirect_records_why_it_is_sanctioned`.
      For each entry assert the reason is non-empty after `.strip()` and is longer than a token
      (≥ 40 chars), so an entry cannot be ratified with `""` or `"ok"` while passing the
      membership check. Mirrors
      `test_both_new_tables_are_allowed_in_the_drift_gate_with_a_reason`.
      Files: `tests/test_url_host_routing_rules.py`
      Verify: part of item 5's run.

- [ ] 4. Rewrite the three remaining failing tests in that file, renaming each to its property.
      - `test_converged_configuration_is_not_rewritten` →
        **`test_applying_the_policy_twice_writes_once`**. The old body fed the `after` snapshot
        and expected no write; that snapshot is no longer converged (F4), which is why it fails.
        New body: `apply(client, before)` writes; feed `client.written` back through a second
        `apply()` and assert the second call returns 0 and writes nothing. That asserts
        idempotence from whatever the current ratified set is, with no snapshot dependency.
      - `test_unknown_redirect_removed_without_touching_proxy_rules` →
        **`test_an_unratified_redirect_is_dropped_and_no_passthrough_is_disturbed`**. Prepend
        `{"source": "/unratified-fixture", "target": "/", "status": "302"}` to `before`, apply,
        assert `client.written is not None`, assert `/unratified-fixture` absent **by name**,
        then assert `[r for r in client.written if not redirects.is_ours(r)] == [r for r in
        before if not redirects.is_ours(r)]` — every passthrough preserved, in order, derived
        through the provisioner's own classifier rather than compared to a snapshot.
      - `test_saved_pre_removal_configuration_reconciles_to_post_removal_snapshot` →
        **`test_the_pre_change_array_reconciles_to_the_ratified_set_with_every_passthrough_preserved`**.
        This is the snapshot-vs-snapshot test becoming a reconciliation test. Body in order:
        `retired = _retired_sources(before)`; `assert retired, "the fixture holds no retired
        redirect, so removal is unproven"` (anti-vacuity, D2); apply from `before`;
        `assert client.written is not None, "apply() short-circuited - the write path was not
        exercised"` (the brief's apply()-must-write requirement, asserted rather than assumed);
        then the by-name negative loop over `sorted(retired)`; then
        `assert client.written == RATIFIED_RULES + [r for r in before if not
        redirects.is_ours(r)]`; then `client.written[0] == WWW_CANONICAL` and
        `client.written[-1] == CATCH_ALL`. The committed `after` snapshot is **not** the expected
        output and is not read here.
      Files: `tests/test_url_host_routing_rules.py`
      Verify: part of item 5's run.

- [ ] 5. Restore the round-1 structural invariants lost in `da78ef68`, and defuse F3.
      - `test_no_path_redirects_shadow_api_or_staff_pages` →
        **`test_no_ratified_redirect_can_shadow_a_passthrough_or_target_the_staff_tree`**,
        asserted against the array `apply()` writes rather than the committed snapshot. Restore
        round 1's non-overlap check in **both** directions: no redirect source starts with a
        passthrough prefix, and no passthrough starts with a redirect's stem
        (`source.removesuffix("<*>").rstrip("/")`, with an empty stem rejected outright). Skip
        the host rule (its source is an origin, not a path) and the `/<*>` catch-all. Add back
        `assert not target.startswith("/workspace")` for every rule. Non-overlap, not ordering:
        the live array had the retired 302s at indexes 1-3 *ahead* of all seven passthroughs, so
        ordering was never the true guarantee (`docs/execution/url-host-matrix-20261001.md:122`).
      - `test_missing_page_rule_stays_last` →
        **`test_the_catch_all_is_last_and_unique_in_the_snapshot_and_in_the_write`**, asserting
        on both `after` and `client.written`.
      - New **`test_the_host_rule_is_first_and_carries_no_path`**: `after[0] == WWW_CANONICAL`,
        and source and target are bare `https://` origins with exactly two `/` — a path on the
        source would collapse every www URL onto the apex home page, which is worse than the
        duplicate-content state the rule was restored to fix.
      - New **`test_the_two_committed_snapshots_differ_only_in_redirect_rules`**: the non-redirect
        rules of `before` and `after` are equal and in the same order. This is round 1's
        `test_the_only_difference_is_the_host_canonicalisation_rule` generalised so it states the
        property (the removal touched only redirects) instead of naming the one rule that moved.
      - New **`test_the_redirect_status_set_matches_the_provisioner`**: local `REDIRECT_STATUSES`
        `==` `redirects.REDIRECT_STATUSES` (D5).
      - Leave `test_both_mcp_forms_proxy_to_one_backend` unchanged.
      Do **not** re-type round 1's `SUPERSEDED_CONVERT_PREFIXES` 15-prefix list. Several of those
      literals are purge targets; the derived retired set covers the same ground without
      reintroducing one.
      Files: `tests/test_url_host_routing_rules.py`
      Verify: `.venv/bin/python -m pytest tests/test_url_host_routing_rules.py -q` — 0 failed.

- [ ] 6. Fix the body of
      `test_owner_policy_preserves_rewrites_without_restoring_legacy_destinations` in
      `tests/test_legacy_redirect_rollback_snapshot.py`. **Do not rename it** (F5).
      Delete only `assert approved == [removals[0]]` — the count pin, and the sole failing line.
      Replace it with the property, derived from the test's own fixture data so no allowlist
      import is needed: `retired = {r["source"] for r in removals} - {r["source"] for r in
      approved}`; `assert retired` (anti-vacuity); then a by-name loop asserting each member is
      absent from `approved` **and** from `client.written`, placed **before** the existing
      `client.written == approved + rewrites` equality. Keep `approved[0] == removals[0]`, the
      `/obsolete-login-fixture` check, the `/workspace` target ban and the converged-idempotence
      tail exactly as they are. Add a dated in-place note to the docstring explaining that the
      count pin went because the owner adds and removes redirects as ordinary product work, and
      that the exact ratified set is owned by `tests/test_url_host_routing_rules.py` —
      cross-referenced, not duplicated.
      Files: `tests/test_legacy_redirect_rollback_snapshot.py`
      Verify: `.venv/bin/python -m pytest tests/test_legacy_redirect_rollback_snapshot.py -q` —
      4 passed.

- [ ] 7. Run the mutation experiments in the next section, in order. Each is a temporary edit
      that must be reverted immediately with `git checkout --` before the next one. Record the
      observed failure line for each in
      `.agents/tasks/routing-test-design-20261002/mutation-evidence.md`. An experiment that does
      **not** fail as predicted means the rewrite is not load-bearing — fix the test, not the
      experiment.
      Files: `.agents/tasks/routing-test-design-20261002/mutation-evidence.md` (new)
      Verify: all nine predictions observed; then
      `git -C /Users/wecaredigital/wecare-store/.worktrees/routing-tests diff --stat -- scripts/ amplify/ src/ docs/ config/`
      is **empty**, proving no production file was left mutated.

- [ ] 8. Run the full suite the way CI runs it and compare against a baseline from the same tree.
      Capture the baseline **first**, on a stashless clean copy of the two test files
      (`git stash push -- tests/test_url_host_routing_rules.py
      tests/test_legacy_redirect_rollback_snapshot.py`, record, `git stash pop`) — or simply use
      the five failure names already recorded at
      `docs/execution/change-authority-matrix.md:875`, which measured this exact set on
      `origin/stack`. Report the **delta**, not a repository-wide total: that row records the
      lesson that an absolute pass count in a durable record goes stale the moment anyone else
      pushes.
      Files: none
      Verify: `.venv/bin/python -m pytest -q 2>&1 | tail -5` — the five named failures are gone
      and no new failure name appears.

- [ ] 9. Commit the two test files, and only them, with `--only`.
      `git -C <worktree> commit --only tests/test_url_host_routing_rules.py
      tests/test_legacy_redirect_rollback_snapshot.py -F <message-file>`. `--only` is not
      optional here: the index is shared across sessions and a chained `add && commit` has twice
      absorbed another session's staged files under an unrelated subject line. Do not push.
      Delete `.scratch/round1_test_url_host_routing_rules.py` first — it is scratch, and
      committing it would reintroduce the round-1 `/access` literals that F2 exists to avoid.
      Files: none (commit only)
      Verify: `git show --stat HEAD` lists exactly two paths; `git status --short` shows no
      staged production file.

- [ ] 10. Append one row to `docs/execution/change-authority-matrix.md` (class `A1_LOCAL`, target
      the two test files, rollback `git revert`, evidence the mutation table and the delta from
      item 8). **Only if** `git status --short -- docs/execution/change-authority-matrix.md` is
      clean; that file is shared and another session may hold uncommitted lines in it. If it is
      dirty, skip the edit and report the row text in the step output instead. Do not edit any
      existing row and do not touch any file under `docs/execution/snapshots/`.
      Files: `docs/execution/change-authority-matrix.md`
      Verify: `git diff --stat -- docs/` shows one file, additions only
      (`git diff --numstat -- docs/execution/change-authority-matrix.md` reports 0 deletions).

---

## Mutation experiments

Run from the worktree root. `PY=/Users/wecaredigital/wecare-store/.venv/bin/python`,
`T="tests/test_url_host_routing_rules.py tests/test_legacy_redirect_rollback_snapshot.py"`.
Revert after **every** one: `git checkout -- scripts/provision_legacy_redirects.py` (or the test
file named).

| # | Temporary edit | Command | Must fail | Proves |
|---|---|---|---|---|
| M1 | Append `{"source": "/mutation-probe", "target": "/", "status": "301"}` to `desired_redirects()`'s returned list | `$PY -m pytest $T -q` | `..._every_ratified_redirect_is_emitted` naming `/mutation-probe` as unratified | an unratified redirect still fails — the property worth keeping survived the rewrite |
| M2 | Keep M1 **and** add `("/mutation-probe", "/", "301"): "mutation experiment M2"` to `RATIFIED_REDIRECTS` | `$PY -m pytest $T -q` | **nothing** — all pass | ratification is genuinely a one-line change. This is the design claim; if it needs more than one line the design failed |
| M3 | Revert M1/M2. Delete `/zip/` from `desired_redirects()`, leave its allowlist entry | `$PY -m pytest $T -q` | the same test, naming `/zip/` as ratified-but-not-emitted | the allowlist is not a one-way sink; silent removal of a sanctioned redirect is drift too |
| M4 | Ratify an entry with an empty reason: `("/x", "/", "301"): ""`, and emit it | `$PY -m pytest $T -q` | `test_every_ratified_redirect_records_why_it_is_sanctioned` | an entry cannot be waved through with no recorded instruction |
| M5 | In `is_ours()`, drop `"302"` from `REDIRECT_STATUSES` so the retired rules are treated as not-ours and preserved | `$PY -m pytest $T -q` | `..._reconciles_to_the_ratified_set...` naming `[retired public path ef531503]` in the by-name loop, **before** any equality message | the negative assertions run, and they are not vacuous (F2) |
| M6 | In the reconciliation test only, replace `_retired_sources(before)` with `set()` | `$PY -m pytest tests/test_url_host_routing_rules.py -q` | the anti-vacuity assert: "the fixture holds no retired redirect, so removal is unproven" | round 1's exact defect is now caught by the test itself rather than by a reviewer |
| M7 | In the reconciliation test only, drive from the `after` fixture instead of `before` | `$PY -m pytest tests/test_url_host_routing_rules.py -q` | "apply() short-circuited - the write path was not exercised" | `apply()` is genuinely exercising its write path, not reporting "policy is current" |
| M8 | Ratify **and** emit `{"source": "/api/legacy", "target": "/", "status": "301"}` | `$PY -m pytest $T -q` | `..._can_shadow_a_passthrough...` on the forward branch | ratification does not buy an exemption from the payment-outage guard — `POST /api/razorpay-webhook` is a live delivery address |
| M9 | Ratify **and** emit `{"source": "/ap<*>", "target": "/", "status": "301"}` | `$PY -m pytest $T -q` | the same test, on the reverse (stem-prefix) branch | the reverse direction is covered: a source that does not *start with* a passthrough prefix can still swallow one |

Two more, cheap and worth doing because each pins a structural invariant that round 1 had and
HEAD does not:

| # | Temporary edit | Must fail |
|---|---|---|
| M10 | In `apply()`, build `new_rules` as `[non-ours] + desired_redirects()` so the catch-all is no longer last and the host rule is no longer first | `..._catch_all_is_last...` and the host-first assertion in `..._reconciles_to_the_ratified_set...` |
| M11 | Make `desired_redirects()` emit `{"source": "/obsolete-login-fixture/<*>", "target": "/workspace/obsolete-login-fixture/<*>", "status": "302"}` | `test_owner_policy_preserves_rewrites_without_restoring_legacy_destinations` on both its by-name retired check and its `/workspace` target ban |

M11 is the one that proves item 6 is load-bearing rather than just shorter.

---

## Guardrails for the implementer

- **Stop condition.** If you conclude `scripts/provision_legacy_redirects.py` is wrong rather
  than the tests, do not change it. Report the finding. D6 records why it is believed correct.
- No `--apply`, no `--verify`, no `boto3` call, no Amplify call, no alias move, no flag change.
  Every test drives the provisioner through a stub client that `apply()` takes as an argument.
- Do not edit, refresh or add anything under `docs/execution/snapshots/`. Those files are
  measured live state and the live array has not been written since the /zip rules were declared
  (F4).
- Do not reintroduce the `/access` literal, or any `[retired public path ...]` source, as a
  hand-typed constant. Derive it (F2, D2).
- Negative assertions go **before** set-equality assertions, every time. Round 1 shipped them
  after, where they could never run.
- Correct a rationale in place with a date; do not delete one. Both files are long-docstring
  files by convention and that convention is load-bearing here — the reason this guard keeps
  breaking is that nobody wrote down why it was pinned to a count.
- Do not pin an absolute repository-wide pass count anywhere in a docstring, a commit message or
  the matrix row. State the delta and the parity measurement
  (`docs/execution/change-authority-matrix.md:875`).

## Open assumption

Items 2-5 land ten tests in `tests/test_url_host_routing_rules.py` (seven reworked or kept, three
new) against seven today, so the targeted run should collect fourteen across both files. The gate
is **0 failed**, not that number — if you consolidate two of the new structural tests into one,
that is fine and does not need re-planning.
