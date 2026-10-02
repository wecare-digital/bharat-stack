# `stack` divergence triage — 2026-10-02

Read-only investigation. Nothing in this repository was modified except this file.
Repository: `/Users/wecaredigital/wecare-store`, branch `stack`.

---

## 0. The ref moved three times during this investigation — read this first

This ran against a live, concurrently-edited checkout, and the answer changed underneath it twice.
Because `origin/stack` is a moving target, **every measurement below is anchored to a pinned SHA,
not to the ref name.** The operative state is:

```
HEAD        = 716cd4ce3d8bd7cfcdc60488376cc36c9e17649a
origin/stack= 9b2ca5a73d0b5889181e5c460f49054667d4f852
merge base  = c6fd53dc7ccdcdcdf7039cfaf95f624c08911756   "Merge remote-tracking branch 'origin/stack' into stack"
```

The trajectory, recorded because it is itself the most actionable finding:

| State | `HEAD` | `origin/stack` | `rev-list --left-right --count` | Merge forecast |
|---|---|---|---|---|
| Brief, as written | `f2c799cf` | `87d2c626` | 41 / 6 (5 listed) | not stated |
| My first measurement | `f2c799cf` | `e287edc7` | **43 / 6** | **clean** |
| Mid-investigation — another session committed | **`716cd4ce`** | `e287edc7` | **43 / 7** | **4 add/add conflicts** |
| Final — that session pushed | `716cd4ce` | **`9b2ca5a7`** | **44 / 7** | **clean** |

```
$ git rev-list --left-right --count 9b2ca5a7...716cd4ce
44	7
```

So the brief's `87d2c626` is now five commits back, its "41 behind" is 44, it listed 5 of what were
then 6 local commits, and a seventh has since appeared and been pushed. **Any plan built on a
snapshot of this divergence must re-measure immediately before it runs.** §8 step 0 exists for that.

```
$ git log --oneline 9b2ca5a7..716cd4ce
716cd4ce (HEAD -> stack) fix: let one role delete a coupon hold without letting it delete the evidence
f2c799cf feat: make a gift card bearer value and settle it as its own evidenced leg
6e1a4178 Leave one Razorpay merchant account named as current, and retire the other
7a0c122c feat: issue coupons from our own table and let Wix do the only discount arithmetic
e61a49c4 Revert the duplicate Razorpay MID purge, keeping the one already on origin/stack
57f5b505 Leave one Razorpay account named as current, and retire the other
0bec35da Fix the manifest _variables self-count after adding the Cart V2 flag
```

---

## 1. Headline verdict

**No — essentially no unique committed work is at risk. One 244-line document is the entire
exposure.**

All seven local-only commits are now represented on `origin/stack`: four are byte-identical patches
already upstream under different hashes, two are a commit plus its own exact revert that cancel to
nothing, and the seventh contributes a single new file. Of the 50 files local `HEAD` changed since
the merge base, **47 are byte-identical to `origin/stack`**. Only three still differ, and on two of
those three **upstream is the one that is ahead**:

```
$ for f in $(git diff --name-only c6fd53dc HEAD); do git diff --numstat 9b2ca5a7..HEAD -- "$f"; done
1	1	config/lambda-env-manifest.json                        # upstream ahead
244	0	docs/execution/razorpay-account-purge-20261002.md       # LOCAL ONLY — the entire exposure
1	1	src/pages/workspace/dashboard/system-architecture.tsx   # upstream ahead
```

The single piece of genuinely local-only committed content in the whole divergence is
`docs/execution/razorpay-account-purge-20261002.md` — 244 lines, 15,341 bytes, no code, referenced
by nothing upstream. A `git reset --hard origin/stack` would destroy exactly that and nothing else
committed.

Two qualifications that change what to *do* about it:

- **This was briefly false.** For a window during this investigation, local commit `716cd4ce` was
  genuinely unique — 10 files, 388 insertions, including a money-safety IAM gate. Its owning session
  then pushed it as `9b2ca5a7`. Had the reset happened in that window it would have destroyed real
  work. The safety of a reset here is a property of a moving ref, not a stable fact.
- **A merge is cheaper than a reset and loses nothing.** `merge-tree` reports it conflict-free, and
  it preserves the one document for free. The only thing standing in the way is one dirty file
  belonging to another session (§7).

**Recommendation: merge. Details and commands in §8.**

---

## 2. Per-commit classification

`git cherry` is the most direct instrument, and it agrees with the patch-id analysis:

```
$ git cherry -v 9b2ca5a7 716cd4ce
- 0bec35da0d476c23ed7adc2d192f8300195a39ec Fix the manifest _variables self-count after adding the Cart V2 flag
+ 57f5b5052391a0eb300a1f6fa8ad079a155e26c8 Leave one Razorpay account named as current, and retire the other
+ e61a49c4c7ca358b1691b3ec1ac71f57618a8cd6 Revert the duplicate Razorpay MID purge, keeping the one already on origin/stack
- 7a0c122c695f9e09b4d452d4076aa5dd1d234ddd feat: issue coupons from our own table and let Wix do the only discount arithmetic
+ 6e1a4178508ca70cc211c4faaed22d268f409289 Leave one Razorpay merchant account named as current, and retire the other
- f2c799cf2ab349ccd68b411e5d9c7c828ddfa2c7 feat: make a gift card bearer value and settle it as its own evidenced leg
- 716cd4ce3d8bd7cfcdc60488376cc36c9e17649a fix: let one role delete a coupon hold without letting it delete the evidence

$ git cherry 9b2ca5a7 716cd4ce | cut -c1 | sort | uniq -c
   3 +
   4 -
```

`-` means git found an equivalent change upstream; `+` means it did not. The three `+` marks are not
three pieces of unique work — two annihilate each other and the third is 90% duplicate.

| # | SHA | Subject | Verdict | Upstream equivalent | Evidence |
|---|---|---|---|---|---|
| 1 | `0bec35da` | Fix the manifest `_variables` self-count after adding the Cart V2 flag | **DUPLICATED-UPSTREAM** | `f4d7f8c8` | `cherry` → `-`; patch-id `7ee8097c…` both sides; `diff <(git show 0bec35da --format="") <(git show f4d7f8c8 --format="")` empty; message byte-identical |
| 2 | `57f5b505` | Leave one Razorpay account named as current, and retire the other | **SUPERSEDED**, and locally self-cancelled | superseded upstream by `863c6ebd` + `27a3fb5d` + `aa4b1c99`; annihilated locally by `e61a49c4` | `git rev-parse 57f5b505^^{tree} e61a49c4^{tree}` → both `987fe741…`; `git diff --stat 57f5b505^ e61a49c4` empty |
| 3 | `e61a49c4` | Revert the duplicate Razorpay MID purge… | **SUPERSEDED** — the annihilating half of #2 | n/a; a pure revert of `57f5b505` | same tree-identity proof |
| 4 | `7a0c122c` | feat: issue coupons from our own table… | **DUPLICATED-UPSTREAM** | `06aa748c` | patch-id `7c30f16f…` both sides; patch text byte-identical; same 15-file set; message byte-identical |
| 5 | `6e1a4178` | Leave one Razorpay merchant account named as current… | **PARTIALLY-DUPLICATED** — 9 of 10 files already upstream, 1 file unique | `863c6ebd`, `27a3fb5d`, `aa4b1c99`, `800106aa` | per-file `git diff --numstat 9b2ca5a7..HEAD` — see §6 |
| 6 | `f2c799cf` | feat: make a gift card bearer value… | **DUPLICATED-UPSTREAM** | `c3818638` | patch-id `e99cd508…` both sides; patch text byte-identical; message byte-identical |
| 7 | `716cd4ce` | fix: let one role delete a coupon hold without letting it delete the evidence | **DUPLICATED-UPSTREAM** — but was UNIQUE for part of this investigation | `9b2ca5a7` | patch-id `b335ee82…` both sides; patch text byte-identical; message byte-identical. `cherry` reported `+` against `e287edc7` and `-` against `9b2ca5a7` |

### Patch-id table (the cherry-pick / rebase fingerprint)

```
local                                          upstream
0bec35da  7ee8097c77c0b5cec16677dad47089d260b827ff   f4d7f8c8  7ee8097c77c0b5cec16677dad47089d260b827ff   MATCH
7a0c122c  7c30f16faa79d33786cf6d43da141992f5f39e4e   06aa748c  7c30f16faa79d33786cf6d43da141992f5f39e4e   MATCH
f2c799cf  e99cd508f88930b78ef546b14268e9b6c49973fd   c3818638  e99cd508f88930b78ef546b14268e9b6c49973fd   MATCH
716cd4ce  b335ee82f4fa6e5ca7199dc24b66b1a6a1f01614   9b2ca5a7  b335ee82f4fa6e5ca7199dc24b66b1a6a1f01614   MATCH
57f5b505  a92dd7ec718991dcb735452f584d4f015b3695c1   no match (see §6)
e61a49c4  d77e84bac57ab9a23bb18e19dacb9c4d52f232ce   reverse patch of 57f5b505 — reverse patches never share a patch-id
6e1a4178  ba8c4924b89a500e695872059bae7dfff45882db   no match (see §6)
```

All four matched pairs have byte-identical commit messages and identical author dates — e.g. both
`7a0c122c` and `06aa748c` are `2026-10-02 09:37:00 +0530 WECARE.DIGITAL`. These are the same commit
content landing twice through two paths, which is the race `multi-session-parallel-agents.md`
describes. `716cd4ce`/`9b2ca5a7` is the same shape, observed live.

### The three non-upstream commits exist nowhere else

```
$ git branch -a --contains 6e1a4178     → * stack
$ git branch -a --contains 57f5b505     → * stack
$ git worktree list
/Users/wecaredigital/wecare-store                                      716cd4ce [stack]
/Users/wecaredigital/Documents/Codex/2026-10-02/re/work/stack-link-fix 3b8f6b06 [codex/link-api-fix-20261002]
/Users/wecaredigital/wecare-store/.scratch/checkout-completion-review  4a09a9fa (detached HEAD)
/Users/wecaredigital/wecare-store/.scratch/workspace-mcp-build         e1db5d62 (detached HEAD)

$ git merge-base --is-ancestor 4a09a9fa origin/stack  → YES
$ git merge-base --is-ancestor e1db5d62 origin/stack  → YES
```

No remote branch and no other worktree holds them; both other worktrees sit at commits already
reachable from upstream. Local `stack` is the only copy, so a reset is the end of the one document
they carry.

---

## 3. Net file-level delta between the two tips

```
$ git diff --stat 9b2ca5a7..HEAD | tail -1
 61 files changed, 677 insertions(+), 5517 deletions(-)
```

That headline mostly measures how far local is **behind**, not what local holds. The honest
decomposition asks what each side changed since the merge base:

```
$ git diff --name-only c6fd53dc HEAD      | wc -l        →   50    # files local changed
$ git diff --name-only c6fd53dc 9b2ca5a7  | wc -l        →  107    # files upstream changed
$ # of local's 50, how many are byte-identical to upstream:
                                                             47
```

The three that differ:

| File | `numstat` of `9b2ca5a7..HEAD` | Which side is ahead | Why |
|---|---|---|---|
| `docs/execution/razorpay-account-purge-20261002.md` | `244  0` | **local ahead** — the only unique committed content | added by `6e1a4178`; `git grep razorpay-account-purge-20261002 origin/stack` returns nothing |
| `config/lambda-env-manifest.json` | `1  1` | **upstream ahead** | both sides made the identical `_variables: 399→401` fix; upstream additionally has `WIX_SITE_URL: https://www.wecare.digital → https://wecare.digital` from `e1db5d62`, which local lacks |
| `src/pages/workspace/dashboard/system-architecture.tsx` | `1  1` | **upstream ahead** | both sides carry the identical `[retired Razorpay account]` redaction at line 392; upstream additionally repoints the BOT_MENU gift-card CTA `/gift-card → /perks/` via `e1339b60` |

Nothing is *conflicting* in the data-loss sense. The remaining 58 entries in
`git diff --stat 9b2ca5a7..HEAD` are files local never touched since the base — local is purely
behind on them. That set includes work named in the original user request: the `GET /{code}` route
retirement in `amplify/link-resources.ts`, the `flows/orders.py` Origin-header removal,
`docs/execution/link-api-fixes-20261002.md` and
`docs/execution/snapshots/link-api-before-fix-20261002.json`, all present upstream and **absent
locally**.

One inversion worth stating plainly, because it is the opposite of the intuition: the
`config/lambda-env-manifest.json` `WIX_SITE_URL` alignment described in the user request's closing
paragraph is **on `origin/stack` and missing from local `HEAD`**. Local still carries the `www.`
value. Reconciling gains that correction; it is not at risk.

---

## 4. Merge conflict forecast

Computed in memory. No merge, index write or working-tree touch.

```
$ git merge-tree --write-tree --messages HEAD 9b2ca5a7
d507e2adb9df6c67c94bd6249baef22d81a957e1
Auto-merging config/lambda-env-manifest.json
Auto-merging src/pages/workspace/dashboard/system-architecture.tsx
exit=0
```

**No conflicts.** A bare result-tree OID, two `Auto-merging` lines, exit 0. The only two files
needing a textual merge auto-resolve, because the overlapping hunks are byte-identical on both sides
and the non-identical hunks sit in different line regions:

- `config/lambda-env-manifest.json` — both sides changed line 5 identically; upstream alone changed
  line ~486.
- `system-architecture.tsx` — both sides changed the line-392 comment identically; upstream alone
  changed line 649.

### The conflict that appeared and then vanished, because it is a real hazard

For the middle window of this investigation — `HEAD = 716cd4ce`, `origin/stack = e287edc7` — the same
command reported **four add/add conflicts**:

```
$ git merge-tree --write-tree --messages HEAD e287edc7
6b3b6645f81606858c580b76c7a5f0991714da50
...
CONFLICT (add/add): Merge conflict in tests/test_coupon_logging_and_vocabulary.py
CONFLICT (add/add): Merge conflict in tests/test_coupons_iam_and_table.py
CONFLICT (add/add): Merge conflict in tests/test_coupons_routes_and_registry.py
CONFLICT (add/add): Merge conflict in tests/test_gift_cards_iam_and_table.py
exit=1
```

The mechanism matters even though the conflicts are gone, because it will recur. Those four paths
are **absent from the merge base** and were added independently on both sides by the duplicated
coupon and gift-card commits:

| Path | in merge base | `e287edc7` blob | blob as added locally (`f2c799cf`) | local `716cd4ce` blob |
|---|---|---|---|---|
| `test_coupon_logging_and_vocabulary.py` | NO | `239cc77d` | `239cc77d` — same | `90a7ce14` |
| `test_coupons_iam_and_table.py` | NO | `611bfeaa` | `611bfeaa` — same | `53f30313` |
| `test_coupons_routes_and_registry.py` | NO | `d55eacb6` | `d55eacb6` — same | `51e19494` |
| `test_gift_cards_iam_and_table.py` | NO | `5b99ad50` | `5b99ad50` — same | `61e45760` |

An add/add path has no common ancestor for git to three-way merge against, so the instant one side
modified its copy (`716cd4ce`), the merge conflicted — even though the content was identical
beforehand. **That is the concrete cost of the duplicate commits**, and it stays latent on every
other file the duplicated commits added: 15 coupon files and 18 gift-card files, 33 paths, all
add/add with no base. Any future divergence on any of them conflicts rather than resolving. The
conflicts cleared only because the owning session pushed `716cd4ce` as `9b2ca5a7`, re-synchronising
both sides.

### The real blocker is not a conflict

`git merge` will still **refuse to start**, because `origin/stack` rewrites
`.kiro/steering/META-BETA-REQUEST-EMAIL.md` while another session holds it modified-unstaged, and
git will not overwrite a dirty tracked file:

```
$ git diff --numstat -- .kiro/steering/META-BETA-REQUEST-EMAIL.md
18	0	.kiro/steering/META-BETA-REQUEST-EMAIL.md          # local, uncommitted
$ git diff --numstat c6fd53dc 9b2ca5a7 -- .kiro/steering/META-BETA-REQUEST-EMAIL.md
2	2	.kiro/steering/META-BETA-REQUEST-EMAIL.md          # upstream, committed
```

A working-tree precondition, not a content conflict. The two edits sit in different line regions
(local `+18` at lines 6–23; upstream at lines 49/51), so the merge resolves both cleanly once that
file is committed or reverted by its owner.
`.agents/tasks/razorpay-account-purge-20261002/review.md` identifies the same blocker independently.

---

## 5. The coupon duplication, in detail

Local `7a0c122c` and upstream `06aa748c` are **the same patch**. Neither is more complete; there is
no divergence to adjudicate.

```
$ diff <(git show 7a0c122c --format="") <(git show 06aa748c --format="")
(no output)
$ diff <(git show --name-only --format="" 7a0c122c) <(git show --name-only --format="" 06aa748c)
(no output)

patch-id, both sides: 7c30f16faa79d33786cf6d43da141992f5f39e4e
commit message:       byte-identical
author date:          2026-10-02 09:37:00 +0530, both
```

15 files, 5,648 insertions, **0 deletions** on both sides — pure addition, which is why there was no
divergence surface to begin with, and also why all 15 paths are add/add relative to the merge base:

```
amplify/functions/ecommerce/coupons/handler.py                   435 +++
amplify/functions/shared/lambda_utils/ecommerce/coupon_store.py  926 ++++
amplify/functions/shared/lambda_utils/ecommerce/wix_coupons.py   330 ++
scripts/provision_coupons_role.py                                290 ++
scripts/provision_coupons_routes.py                              292 ++
scripts/provision_coupons_table.py                               239 ++
tests/coupon_fake_dynamo.py                                      339 ++
tests/fixtures/wix_cart_v2_coupon_applied_v2_shape.json          290 ++
tests/fixtures/wix_coupon_get_response.json                       21 +
tests/test_coupon_logging_and_vocabulary.py                      217 ++
tests/test_coupon_reconciliation.py                              466 +++
tests/test_coupon_store.py                                       698 ++++
tests/test_coupons_iam_and_table.py                              353 ++
tests/test_coupons_routes_and_registry.py                        296 ++
tests/test_wix_coupons_contract.py                               456 +++
```

The gift-card pair behaves identically: `f2c799cf` and `c3818638` are byte-identical patches
(18 files, 8,807 insertions, 0 deletions), identical messages, identical author dates. Upstream then
adds one follow-up local lacks — `e287edc7` "docs(gift-cards): record the FEAT-002 landing and its
seo-tools rollback", contributing
`docs/execution/snapshots/seo-tools-rollback-giftcards-20261002.json`.

So for both features `origin/stack` holds everything local holds plus a documentation commit — and
the duplication is the direct cause of the add/add hazard in §4.

---

## 6. The Razorpay MID sequence, reconstructed

Three local commits, chronologically:

**`57f5b505` (iteration 1 — 11 files, +1101/−52).** Purged the retired merchant account
`acc_HDfub6wOfQybuH` and its paired retired VPA from current source: both handlers,
`payment_readiness.py`, `docs/compatibility.md`, `.kiro/specs/whatsapp-wix-commerce/tasks.md`, the
dashboard component, two test files, one new test, plus a 621-line `plan.md` and a 312-line evidence
doc.

**`e61a49c4` (11 files, +52/−1101).** An **exact, total revert** — tree-identical, not approximately
so:

```
$ git rev-parse 57f5b505^^{tree} e61a49c4^{tree}
987fe7415f9894833d12bf1ae89434bcc077de38
987fe7415f9894833d12bf1ae89434bcc077de38
$ git diff --stat 57f5b505^ e61a49c4
(no output)
```

Its subject gives the reason: a concurrent session had already landed the same purge on
`origin/stack`, and two independent rewrites of the same prose turned the merge into eight manual
conflict resolutions. The pair contributes **exactly zero** to local `HEAD`. One side effect, noted
in the review: the revert also deleted the task's own `plan.md`, never restored.

**`6e1a4178` (iteration 2 — 10 files, +294/−20).** Re-landed the purge by a deliberately different
method: rather than re-authoring it, the session adopted `origin/stack`'s **byte-identical content**
for nine authorized paths (`git checkout origin/stack -- <paths>`, per
`.agents/tasks/razorpay-account-purge-20261002/review.md`), specifically so the eventual merge would
auto-resolve. A normal merge was impossible for the same reason it still is — the dirty
`META-BETA-REQUEST-EMAIL.md` — and stash, reset and committing another session's work are all
prohibited here.

That choice is why the net effect is so small. Byte-identical adoption cannot differ from upstream
afterwards, and it does not:

```
SAME-AS-UPSTREAM  .kiro/specs/whatsapp-wix-commerce/tasks.md
SAME-AS-UPSTREAM  amplify/functions/messaging/partner-onboarding/handler.py
SAME-AS-UPSTREAM  amplify/functions/messaging/whatsapp-business-api/handler.py
SAME-AS-UPSTREAM  amplify/functions/shared/lambda_utils/payment_readiness.py
SAME-AS-UPSTREAM  docs/compatibility.md
DIFFERS  244  0   docs/execution/razorpay-account-purge-20261002.md
DIFFERS  1    1   src/pages/workspace/dashboard/system-architecture.tsx
SAME-AS-UPSTREAM  tests/test_partner_razorpay_canonical_secret.py
SAME-AS-UPSTREAM  tests/test_payment_readiness.py
SAME-AS-UPSTREAM  tests/test_payment_status.py
```

And of the two that differ, `system-architecture.tsx` differs because **upstream is ahead**, not
local:

```
$ git diff 9b2ca5a7..HEAD -- src/pages/workspace/dashboard/system-architecture.tsx
-  { row: 6, ... action: 'CTA link → wecare.digital/perks/' },      # origin/stack
+  { row: 6, ... action: 'CTA link → wecare.digital/gift-card' },   # local HEAD

$ git log --oneline -S"wecare.digital/perks/" origin/stack -- src/pages/workspace/dashboard/system-architecture.tsx
e1339b60 fix: repoint active customer-facing CTAs off dead/redirecting old URLs
```

The redaction `6e1a4178` made at line 392 (`acc_HDfub6wOfQybuH` → `[retired Razorpay account]`) is
already upstream, which is why it is absent from the net diff.

### Net effect of the whole sequence relative to `origin/stack`

**One new file and nothing else:** `docs/execution/razorpay-account-purge-20261002.md`, 244 lines,
15,341 bytes (`git cat-file -s`). Every code, test, spec and other-documentation change in the
sequence is already upstream via `863c6ebd`, `27a3fb5d`, `aa4b1c99` and `800106aa`.

That document is worth keeping, and a merge preserves it for free. Its distinctive content, which I
read and could not find upstream:

- A per-hit justification table for the surviving `acc_HDfub6wOfQybuH` occurrences, and the explicit
  record of the **one declined cross-session seam** —
  `.kiro/steering/META-BETA-REQUEST-EMAIL.md:49,51` still names the retired merchant account in a
  draft email to Meta, with a named unblock (merge once the owning session commits) rather than an
  edit.
- A **money-safety coverage reduction**, stated rather than hidden: the MID-mismatch guard is kept,
  but its wrong-account fixture is now the synthetic `acc_RETIRED_FIXTURE`, so the narrow regression
  proof that *this specific* retired account would be refused is gone.
- The **owner-gated live-environment half**, described and explicitly not run, including why
  `scripts/set_lambda_env_flag.py` is mandatory and a raw
  `update-function-configuration --environment Variables={...}` is not an acceptable substitute — it
  replaces the whole variable map, the same replace-not-patch shape that wiped three Cognito
  `CUSTOM_AUTH` triggers on 2026-09-28.

Upstream's `docs/execution/razorpay-mid-vpa-purge-20261002.md` covers the complementary half (live
v60 deploy, release ZIP SHA, alias move) and repeats the `set_lambda_env_flag.py` reasoning, but
carries none of the three items above. Upstream's own doc says the local checkpoint is superseded:
*"Remote stack already contains the complete current purge and live deployment commit 27a3fb5d, so
the pasted version-59/pending-VPA checkpoint is superseded."* That is true of the **code**. It is not
true of the declined-seam and coverage-reduction records, which exist only in the local file.

---

## 7. Uncommitted third-party work

**This category largely resolved itself during the investigation.** Ten of the eleven modified
tracked files became commit `716cd4ce`, which was then pushed as `9b2ca5a7`. First and final
readings:

```
# first reading
 M .kiro/steering/META-BETA-REQUEST-EMAIL.md
 M scripts/check_data_model_drift.py
 M scripts/deploy_all_lambdas.py
 M scripts/provision_checkout.py
 M tests/test_coupon_logging_and_vocabulary.py
 M tests/test_coupons_iam_and_table.py
 M tests/test_coupons_routes_and_registry.py
 M tests/test_deploy_map_provisioning.py
 M tests/test_gift_cards_iam_and_table.py
 M tests/test_payment_vocabulary_at_decision_points.py
 M tests/test_provision_checkout_contract.py
$ git diff --stat   →  11 files changed, 406 insertions(+), 82 deletions(-)

# final reading
$ git status --short
 M .kiro/steering/META-BETA-REQUEST-EMAIL.md
?? .agents/tasks/razorpay-account-purge-20261002/
?? .agents/tasks/stack-divergence-triage-20261002/     # this report
?? .agents/tasks/wix-coupons-giftcards-20261001/
?? AGENTS.md
?? amplify/functions/shared/lambda_utils/ecommerce/finalization.py
?? amplify/functions/shared/lambda_utils/ecommerce/initiation.py
?? docs/execution/coupons-20261001.md
?? docs/execution/gift-cards-service-plugin-20261001.md
?? docs/execution/snapshots/staff-pool-mfa-before-20261002.json
?? scripts/retired_url_equity.py
$ git diff --cached --stat   →  (empty; index clean)
```

`716cd4ce` is 10 files / 388 insertions / 82 deletions; the 18-line difference from the 406 measured
earlier is `META-BETA-REQUEST-EMAIL.md`, correctly left out of that commit. Two new untracked
documents appeared (`docs/execution/coupons-20261001.md`,
`docs/execution/gift-cards-service-plugin-20261001.md`), and the brief's reported `.worktrees/`
appeared, vanished and reappeared across my readings.

Worth recording what `716cd4ce` contains, since it was the unique work for part of this
investigation and is now the upstream tip. Its commit message describes a trap it closes: the IAM
verify gate was re-keyed from per-action onto `(action, resource)` against an explicit
`_EXPECTED_DENY`, so `wecare-checkout-role` can be granted `DeleteItem` on the coupon and gift-card
hold tables while remaining **provably refused** `DeleteItem` on the payment-attempt and reservation
tables, where a row is the evidence that no charge became an order. Under the old per-action
aggregate *"a correctly provisioned role would have been reported as broken, and the only way to
quiet it would have been to widen the role."* That is now safely upstream.

What still constrains the options:

1. **`.kiro/steering/META-BETA-REQUEST-EMAIL.md` is still dirty**, `+18` lines at lines 6–23 (an
   editor's note about MCC 4722 vs live 7392, and PayU retirement). Upstream changes lines 49/51 of
   the same file (`2 2`). Non-overlapping, so a merge resolves both — but **`git merge` cannot start**
   until its owner commits or reverts it. This one file is the only thing blocking reconciliation.
2. **Untracked payment-path source is uncommitted and unbacked.**
   `amplify/functions/shared/lambda_utils/ecommerce/finalization.py` and `initiation.py`, 8 KB each,
   exist nowhere but this working tree. They survive `reset --hard`, which leaves untracked files
   alone, but `git clean` would take them — and `git clean` is prohibited here regardless.
3. **Checkpoints do not protect any of this.** Per `multi-session-parallel-agents.md`, a session only
   snapshots files its own file tools touched, so a turn revert in one session silently discards
   another's edits to the same file. Git is the only shared source of truth, which is exactly why
   tree-wide operations are the dangerous ones.

---

## 8. Recommendation

**Option (b): merge `origin/stack` into local `stack`, then push.** Do not reset.

Reasoning, in the order the evidence forces it:

- **Reset (a) would work today and is still the wrong choice.** It is *nearly* safe — only the
  244-line evidence document is lost — but that document is the sole record of a declined
  cross-session seam, a money-safety coverage reduction, and an owner-gated live-environment step.
  Those are exactly what `maintenance-reporting.md` exists to preserve. And the safety margin is a
  property of a ref that moved three times in one investigation: for a window during this very
  triage, a reset would have destroyed `716cd4ce`'s 388 lines including a money-safety IAM gate. A
  plan whose safety depends on nobody having committed in the last few minutes is the wrong plan.
- **Merging costs nothing.** `merge-tree` reports it conflict-free with exit 0, it keeps the
  document, and it pulls in the 58 files local is behind on — including the `WIX_SITE_URL` apex
  alignment from the original user request that local currently lacks.
- **Cherry-picking (c) is strictly worse here.** The only thing worth picking is one documentation
  file, and extracting it needs `git show > file` plus a commit — more steps than a merge, while
  discarding the upstream catch-up the checkout needs anyway.
- **Merging does leave the duplicated commits in history.** Coupons, gift cards, the manifest fix and
  the IAM gate will each appear twice under two hashes with identical content. That is cosmetically
  unfortunate and functionally harmless, and the only way to remove it is a history rewrite, which is
  permanently prohibited in this repository. Recording it, as this report does, is the correct
  outcome.
- **One thing to carry forward regardless of the choice:** 33 add/add paths (15 coupon, 18 gift-card)
  have no merge base, so any future divergence on them conflicts instead of resolving. §4 shows that
  hazard firing once already. Keeping the two sides synchronised is what keeps it quiet.

### Preconditions — all must hold before any command runs

1. The owner of `.kiro/steering/META-BETA-REQUEST-EMAIL.md` has **committed or reverted** it. The
   merge cannot start otherwise. Per `multi-session-parallel-agents.md` rule 3b, that session should
   use `git commit --only .kiro/steering/META-BETA-REQUEST-EMAIL.md`.
2. **One committer.** The session owning these commits performs the merge; others leave the tree
   alone for its duration.
3. **Re-measure first.** Non-negotiable here. Step 0 below.

### Commands — written out, **NOT executed by me**

Step 0 — re-measure, and read each output before continuing:

```
git -C /Users/wecaredigital/wecare-store fetch origin stack
git -C /Users/wecaredigital/wecare-store status --short
git -C /Users/wecaredigital/wecare-store rev-list --left-right --count origin/stack...HEAD
git -C /Users/wecaredigital/wecare-store cherry -v origin/stack HEAD
git -C /Users/wecaredigital/wecare-store merge-tree --write-tree --messages HEAD origin/stack
```

If `cherry` shows a `+` on a commit this report classified as duplicated, or `merge-tree` reports a
conflict, **stop and re-triage** — the state has moved again, exactly as it did three times here.

Step 1 — merge, only once `META-BETA-REQUEST-EMAIL.md` is clean:

```
git -C /Users/wecaredigital/wecare-store merge origin/stack
```

Step 2 — if conflicts appear despite step 0 (they will be `add/add` on the coupon/gift-card paths),
resolve by taking local **only after confirming** upstream's blob is not ahead:

```
cd /Users/wecaredigital/wecare-store
git log --oneline $(git merge-base HEAD origin/stack)..origin/stack -- <conflicting path>
# empty output ⇒ upstream added it and never changed it ⇒ local is a superset ⇒ --ours is safe
git checkout --ours <conflicting paths> && git add <conflicting paths>
grep -rn '^<<<<<<<\|^=======\|^>>>>>>>' <conflicting paths>      # must print nothing
```

Step 3 — verify before completing. `716cd4ce`'s own message records
`6744 passed, 1 skipped, 7 xfailed, 0 failed`, so that is the bar:

```
python -m pytest tests/ -q
npx tsc --noEmit
```

Step 4 — complete and confirm, then push:

```
git -C /Users/wecaredigital/wecare-store commit --no-edit
git -C /Users/wecaredigital/wecare-store diff --stat origin/stack..HEAD   # expect only the razorpay doc
git -C /Users/wecaredigital/wecare-store push origin stack
```

**If `META-BETA-REQUEST-EMAIL.md` cannot be cleaned soon**, the correct interim action is
**nothing**. Local `stack` sitting 7 ahead / 44 behind is harmless provided nobody pushes. The one
hard constraint — stated independently in
`.agents/tasks/razorpay-account-purge-20261002/review.md` — is **do not push before merging**: a push
of these seven would put duplicate coupon, gift-card, manifest and IAM-gate commits on the remote
permanently, and removing them afterwards would require the history rewrite this repository forbids.

No history rewrite and no force push appears in any step above, and neither is ever an option here.

---

## 9. What I could not determine

Stated as unknowns rather than guessed:

1. **Whether the merge result builds or passes tests.** `merge-tree` proves a tree can be computed
   without conflict; it says nothing about whether the result compiles, or how `716cd4ce`'s changes
   to `scripts/provision_checkout.py` interact with the 107 files upstream changed. I ran no build
   and no test — both write caches and artifacts, which the read-only constraint forbids. The
   `6744 passed` figure in §8 step 3 is quoted from `716cd4ce`'s commit message, **not measured by
   me**. Unverified.
2. **Whether the 244-line document's live-environment claims are still true.** It describes
   `wecare-whatsapp-business-api:live` at version 60 with the retained MID/VPA pair; the user request
   describes version 61. I made no AWS call, so I cannot say which version the alias selects now or
   what its `RAZORPAY_MID` / `RAZORPAY_UPI_ID` hold. The document's own review flags the same gap
   (finding 3). Unverified.
3. **Who owns which files.** I inferred session ownership from the brief and from subject matter
   (coupons, gift cards, checkout provisioning, matching untracked
   `.agents/tasks/wix-coupons-giftcards-20261001/`). I ran no session-mapping command. Ownership is
   an inference; the file list is a measurement.
4. **Why the commits landed twice.** Byte-identical patches, messages and author dates prove the same
   content landed through two paths, but git cannot tell me whether one session pushed while another
   committed locally, or whether a push came from a different worktree. I watched it happen once
   live, for `716cd4ce`/`9b2ca5a7`, but even there I only observed the result. The mechanism is
   inference; the duplication is measured.
5. **Whether `origin/stack` rewriting six Class C immutable-history files is acceptable.**
   `.agents/tasks/razorpay-account-purge-20261002/review.md` raises this as unflagged: upstream
   substitutes `[retired Razorpay account]` into audit documents including a measured dedup key
   (`acc_HDfub6wOfQybuH:payment.downtime.started:1790100905`), so an audit record of a measurement no
   longer contains the thing measured. I confirmed the substitutions exist upstream, but whether to
   accept them is an owner policy decision no evidence can settle, and it is outside my remit.
6. **Whether anything changed after my final measurement.** Given three movements during one
   investigation, assume it has. Step 0 exists for that reason.

### One correction to my own work, since it bears on trust in the numbers

An intermediate draft of this report quoted three aggregate figures — the `git diff --stat` totals
and the 48/35 file split — that I had **extrapolated from an earlier measurement rather than run
after `HEAD` moved**. I caught it on verification and re-measured. Every number in the final text
above is the output of a command run against the pinned SHAs `716cd4ce` and `9b2ca5a7`. The lesson
generalises to anyone acting on this: against a checkout this volatile, a derived number is wrong
within minutes.

---

*Investigation performed read-only. No `add`, `commit`, `merge`, `rebase`, `cherry-pick`, `reset`,
`checkout <branch>`, `switch`, `stash`, `clean`, `push` or `worktree add` was run. Only `log`,
`show`, `diff`, `cherry`, `patch-id`, `merge-tree`, `rev-list`, `rev-parse`, `merge-base`,
`for-each-ref`, `branch --contains`, `worktree list`, `cat-file`, `ls`, `du`, `grep` and `status`.
The sole file written is this report.*
