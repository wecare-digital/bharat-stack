# Round 2: APPROVED — and the narrative document was destroyed by the orchestrator

## What happened

`review.json` and `routing-review.md` in this directory record **round 1**
(`CHANGES_REQUESTED`, 3 findings). They are the versions committed in `9273e6d1`.

Round 2 ran after that commit and returned **APPROVED** with 4 non-blocking findings,
writing a fresh `review.json` and a ~15 KB `routing-review.md` to this directory as
untracked files. The orchestrator then deleted both while clearing a blocked
fast-forward.

The deletion was not an accident of judgement; it was an accident of **shell
construction**. The command verified the three untracked files against `origin/stack` and
removed them in the same `&&` chain:

```
for f in ...; do ... IDENTICAL / DIFFERS ... done && git checkout -- ... && rm -f <the three files> && git merge --ff-only ...
```

The comparison printed `findings.md IDENTICAL`, `review.json DIFFERS`,
`routing-review.md DIFFERS` — and then the `rm` ran regardless, because a printed
result cannot gate a later link in a chain. Two files known to differ were deleted one
line after being reported as differing.

This is the same failure mode `.kiro/steering/multi-session-parallel-agents.md` records
about `git add` and `git commit`: "the chaining actively hid it: `git status --short` was
the first link in the `&&` chain, so its output scrolled past and the commit happened in
the same breath. Reading it was structurally impossible." The rule there was written for
staging. It generalises: **never chain a check and a destructive action.** Either branch
on the check inside the script, or run them as two calls.

`rm` on an untracked file leaves nothing for git to recover. The round-2 narrative is
gone and is not reconstructible.

## What is known about the round-2 verdict, and on what evidence

The verdict itself survives in the run notification: **APPROVED, 0 blocking, 4
non-blocking.** That is hearsay rather than an artifact, so it is not relied on alone.
The substance was re-verified directly against the tree, and that verification is what
this record rests on:

| Round-1 finding | Status, measured on the merged tree |
|---|---|
| **F1 (blocking)** — the matrix row cited `findings.md`, which was untracked, so a durable audit row pointed at a path not in the repository | Closed. All four artefacts (`findings.md`, `plan.md`, `review.json`, `routing-review.md`) report `TRACKED` under `git ls-files --error-unmatch`. |
| **F2** — the `/obsolete-login-fixture` and `/workspace` negatives sat *after* the set-equality, contradicting the commit message's claim that by-name negatives precede every equality | Closed, and more strongly than asked. `assert approved == [removals[0]]` was **deleted** (the test body records why at line 141), so there is no equality left for them to follow — the by-name negatives at lines 195-196 *are* the assertion. |
| **F3** — the shadowing check compared raw string prefixes, rejecting `/getting-started`, `/api-docs`, `/mcp-legacy` and `/r`: a narrow return of the reddening-on-legitimate-change problem this work existed to end | Closed. `str.startswith` replaced by `_patterns_overlap()` with a documented rationale and a reverse branch for `/ap<*>` swallowing `/api/<*>`, pinned by `test_pattern_overlap_is_segment_aware_in_both_directions`. |

Independent of the review: `tests/test_url_host_routing_rules.py` and
`tests/test_legacy_redirect_rollback_snapshot.py` report **17 passed**, the five failures
named in the brief are gone, and
`git diff --stat origin/stack -- scripts/ amplify/ src/ config/ public/ docs/execution/snapshots/`
is **empty**, so no production file moved.

## What is genuinely lost

The round-2 document's four non-blocking findings. Their count is known; their content is
not. If any of them identified a real weakness, that weakness is now unrecorded — which is
the actual cost here, and the reason this file exists rather than a silent re-run. A
re-review would produce a fresh document but not the same one, and would not tell anyone
that a record was destroyed.

Nothing in the shipped change set depends on the lost document. The code it approved is
in `origin/stack` and independently verified above.
