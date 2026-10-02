# Customer WhatsApp OTP confirm outage — review iteration 4

`fix/otp-confirm` at `4c45eed9` is **1 ahead / 0 behind** `origin/stack` (`53f3ac2b`), and
`git merge-tree --write-tree --name-only HEAD origin/stack` emits a tree hash with no conflict
lines — iteration 3's one blocking finding is closed. The remaining delta is four paths and
**zero production source**: `git diff origin/stack --name-only -- src/components src/pages src/lib
amplify` is empty. Everything substantive (the `customer_auth` `sub` derivation, the `submitOtp`
degrade, option C, then upstream's retirement of the two-tone pill) is already in `origin/stack`,
and the server fix is deployed shared-layer-first — `wecare-customer-session` v5→v6,
`wecare-checkout` v4→v5, `wecare-wix-store` v33→v34, recorded in `a4144896` by another session.

Watch for: nothing blocking. Three carried or new non-blockers — `sign-in.tsx` still passes a
`label` the component silently drops, and its call-site comments still describe a two-segment pill
that no longer exists (confirmed, upstream's, not in this delta); the build-scope test's `run`
helper is cast `as typeof it`, which type-checks `run.each` and would crash at runtime (confirmed);
and the live OTP round trip still needs one handset (confirmed, correctly not attempted).

**Verdict**: APPROVED

## High-level view

The root cause is proven by measurement, and I am reading the coder's evidence rather than
re-running it. `customer_auth.authenticate()` read `custom:customer_id`, which `DescribeUserPool`
shows is absent from pool `us-east-1_46ULYuukt`'s schema — the pool's only custom attribute is
`custom:partner_waba_id` — so the read returned `''` for every token ever issued. Four
`{"event":"customer_auth_no_customer_id"}` WARNING lines at 02:44:00.283Z, 02:45:11.732Z,
05:33:55.013Z and 06:02:13.625Z on the `[5]` alias streams are the owner's own confirm attempts,
and `CustomerSessionsTable` at 0 items shows the exchange had never once succeeded.

The reproduction is a real browser with the simulation boundary stated: Chrome 154 headless over
CDP against the real `next build --webpack` export, with exactly three responses intercepted via
`Fetch.fulfillRequest` — Cognito `InitiateAuth`, Cognito `RespondToAuthChallenge`, and
`POST /api/ecommerce/customer-session` at 401 or 200 — because a genuine code needs the owner's
handset. The classifier ambiguity the brief flagged is settled by reverting the client fix and
re-running, not by reading: pre-fix renders exactly `Try again shortly.` and stays on
`/account/sign-in/`, and the only non-200 in the flow is the 401, so
`messageForVerifyRejection`'s `status >= 500` branch cannot have fired and the name-based catch-all
in `messageForAuthError` did.

Iteration 3's three actionable findings are closed with measurement rather than argument. The
conflict was rebased and resolved as directed, with both wrong resolutions measured (0
`.pill-label` elements in the built page, 1 `.pill-action`, against a first case on `origin/stack`
that is a plain `it` asserting `existsSync`). The stale-`out/` gate became four states and fired
for real on this tree — the rebase left `out/` at 14:55 against sources at 15:16, so three
assertions that would have run green against markup from the retired two-segment component skipped
with the gap named. The 2.5.3 ordering clause is now driven by a genuinely two-segment control.

Defect 2's final shape is upstream's and the branch says so. `2f742ec6` fixed the styled-jsx
scoping that produced the run-together rendering; `1c847107` then retired the two-tone pill on
owner instruction. The confirm button is one `.pill-action` span, and `SignInMessages.test.tsx`
pins it exactly — `getByRole('button', { name: 'Confirm code' })` with no `aria-label`, so the name
*is* the visible text and that exact pin is the non-concatenation assertion the brief asked for,
backed by `.pill-label` being null and `.pill-action` textContent being exactly `Confirm code`.

The deliberate structures are intact. `MSG` at `sign-in.tsx:98` still sources all seven section-6
strings from `lib/signInMessages` with `NOT_ON_WHATSAPP` present and unwired, and all three of
`messageForAuthError`, `messageForVerifyRejection` and `messageForHttpStatus` survive.
`SignInMessages.test.tsx` keeps the approved-table pin in order and count, the per-constant
assertions, and the source-level check that the page imports by name and references every key.

Hard constraints hold trivially here, because the delta touches no production code and no
infrastructure: no live-send flag, no `update-user-pool` or `add-custom-attributes`, no credential
access, no deploy, no published version, no alias moved, and no `***`-masked value added anywhere
in the code diff.

The pre-existing Python failures are reported separately, now six rather than five, and I verified
the attribution rather than accepting it: `git diff origin/stack` across
`test_url_host_routing_rules.py`, `test_legacy_redirect_rollback_snapshot.py`,
`test_blog_ledger.py`, both provisioner scripts, `provision_missing_ui_routes.py` and
`link-resources.ts` produces no output, so every failing test and every subject it exercises is
byte-identical to upstream. The sixth arrived with the rebase, from `8c46b132` adding two
Conversations batch files without their `ledger.json` rows — a real upstream gap, five published
articles with no provenance row, correctly recorded and not fixed.

<details>
<summary>Issues (4)</summary>

1. **Dead `label` prop and stale call-site comments in `sign-in.tsx`** — both call sites still pass
   `label="Sign in"`, which `PillButton` destructures at line 128 and never renders, and the
   comments above them still read "THE TWO-SEGMENT PILL ... The LEFT segment is the static 'Sign
   in' label". Upstream's, not in this delta, but it tells the next reader of the confirm button
   that the pill has a shape it does not. Drop the prop at the call sites or rewrite the two
   comments.
2. **`run` is cast `as typeof it`** — `PillButtonBuildScope.test.ts` asserts an arrow function is
   the whole `it` object, so `run.each(...)` or `run.only(...)` would type-check and crash at
   runtime. Type it as a call signature instead of asserting the full interface.
3. **Ordering coverage is on a synthetic fixture, not the component** — the new two-segment cases
   render a raw `<button>` because `PillButton` can no longer express either failing shape, so they
   prove the predicate rather than the component. Correct given the constraint and documented, but
   if a second segment ever returns, nothing asserts the component's own name ordering.
4. **No live OTP round trip** — `InitiateAuth`, `RespondToAuthChallenge` and the session endpoint
   are all canned, so the deployed path has never run end to end with a real code. Owner work: one
   handset sign-in on `+918100640044` after Amplify carries the frontend commit, disambiguating the
   masked `…0044` on direction, channel or the `wecare-customer-whatsapp-auth` delivery id.

</details>

<details>
<summary>Details</summary>

### The conflict resolution, verified against the tree rather than the narrative

`git merge-tree --write-tree --name-only HEAD origin/stack` returns `265e13b498…` and nothing else,
so the blocking finding is genuinely closed rather than deferred. The resolution landed on the side
iteration 3 directed, and both halves are present in the file: upstream's narrowed loop and title,

```ts
run( 'scopes the sign-in pill label specifically, not just the outer control', () => {
  const html = readPage();
  expect( html ).toContain( 'Send code' );
  for ( const segment of [ 'pill-action' ] as const ) {
```

and the branch's `readPage()` helper, which turns the `out/`-exists-but-page-missing case into a
named assertion instead of a bare `ENOENT`. The contradictory pair of comments left behind by the
two independent edits is collapsed into one that states there is a single segment and why the loop
is still a loop. The docblock's "FOUR states, not two" table now matches the code, which is the
specific mismatch iteration 2's finding 5 was about.

The `run` indirection is where the one new nit sits:

```ts
const run: typeof it = skipReason === null
  ? it
  : ( ( name: string, fn: Parameters<typeof it>[ 1 ] ) =>
      it.skip( `${ name } [${ skipReason }]`, fn ) ) as typeof it;
```

The assertion claims a two-argument arrow is the full `it` callable-with-properties. Nothing in the
file uses `run.each` or `run.only`, so it is inert today, and `tsc --noEmit` passes precisely
because the cast suppresses the structural check that would have caught a later `run.each`. A
narrower type — the call signature alone — keeps the same ergonomics without the lie.

### The staleness gate earns its keep, and the evidence is that it fired

The gate distinguishes three facts that were previously one:

```ts
const built = existsSync( OUT );
const pageBuiltAt = existsSync( PAGE ) ? statSync( PAGE ).mtimeMs : 0;
const stale = pageBuiltAt > 0 && !!source && source.at > pageBuiltAt;
```

The `pageBuiltAt > 0` guard is the load-bearing part and the comment says why: a zero mtime would
read as older than every source, diverting the page-missing **failure** into a **skip** and turning
a broken export green. `SOURCES` is deliberately two files — `PillButton.tsx` and `sign-in.tsx` —
and that narrowness was then tested in the only way that counts: the second rebase onto `53f3ac2b`
rewrote ten page files, git left those two mtimes alone, and the check correctly did not fire. A
list spanning `src/` would have skipped three real assertions over a border colour on `/orders`.

Staleness skips rather than fails, which is the right direction for the reason recorded in the
docblock — a stale artifact is no evidence either way, and a test that goes red whenever someone
edits a component without rebuilding is a test that gets deleted. CI cannot reach the state because
`build-test.yml` builds immediately before vitest.

### The ordering cases are not vacuous, and the revert check is what shows it

`containsAllInOrder` was hoisted to module scope and curried so it can be driven with more than one
segment. The two negatives are the historical defect's exact shape rather than invented strings — an
`aria-label` disagreeing with the visible segments, which is the only way a real control's name can
hold the right words in the wrong order:

```tsx
const TwoSegments: React.FC<{ name?: string }> = ( { name } ) => (
  <button aria-label={ name }>
    <span>Sign in</span>
    <span>Confirm code</span>
  </button>
);
```

`aria-label="Confirm code Sign in"` contains both visible words, so a containment check ignoring
order would pass it; the cursor walk refuses it. Neutralising the cursor
(`indexOf( segment, cursor )` → `indexOf( segment, 0 )`) fails **exactly one** of seventeen cases,
which both proves the new case is load-bearing and confirms iteration 3's reading that the other
sixteen — the ten call sites included — cannot detect the loss of ordering at all.

`CALL_SITES` keeping its inert `label` props is the better of the two options iteration 3 offered.
The list's contract is "every prop shape in the codebase", every real call site still passes
`label`, and stripping it would stop the file mirroring the thing it claims to mirror and stop
covering the shape a regression would arrive in. The docblock now records that `label` is
accepted-but-unrendered, which is the fact a reader needs.

That leaves one honest gap: the subject of the ordering cases is a hand-written `<button>`, not
`PillButton`, because the component exposes no way to produce either failing shape any more —
`ariaLabel` was removed and the second segment is gone, and the file asserts both of those
absences. So the ordering clause is proven of the predicate and of Testing Library's name
computation, not of the component. Given the constraint that is the only available measurement, and
it is better than leaving the branch unexecuted, but it is worth naming rather than reading the
seventeen-case count as seventeen cases about the pill.

### The refresh-owner test, carried unchanged from iteration 3

Reviewed and accepted last pass; one thing re-checked here. The test hardcodes
`victim_sub = 'sub-1234'` with a comment claiming that is what `REAL_POOL_ATTRIBUTES` carries, and
the fixture does carry exactly that, so the pairing against `sub-9999` genuinely crosses two
identities. The guard it pins now compares one value twice —
`proven.customer_id != identity.customer_id or proven.subject != identity.subject`, both reading
the `sub` since the outage fix made it the single authority — which is why asserting the behaviour
mattered more than the redundancy suggested.

### Dead prop, stale prose

`PillButton` destructures `label` at line 128 and renders only `action` in both branches.
`sign-in.tsx` still passes `label="Sign in"` at both call sites, under comments describing the
retired shape in detail — "the LEFT segment is the static 'Sign in' label", "Same two-segment pill.
The right segment carries 'Confirm code'". The behaviour is right and the documentation describes a
component that no longer exists, in the exact file a reader opens to understand the reported
`Sign inConfirm code` symptom. On `origin/stack` and outside this delta, so recorded rather than
charged to this work.

</details>

<details>
<summary>File map</summary>

Branch delta, `origin/stack..4c45eed9` (4 files, +1153/−57):

- `src/test/PillButtonBuildScope.test.ts` — conflict resolved onto upstream's one-segment loop;
  four-state gate adding stale-build detection by mtime against two named sources; `readPage()`
  helper; docblock rewritten so nothing claims two segments.
- `src/test/PillButtonAccessibleName.test.tsx` — `containsAllInOrder` hoisted and curried; three
  new cases driving the ordering clause through a genuinely two-segment control; `CALL_SITES`
  deliberately unchanged, with the accepted-but-unrendered `label` recorded in the docblock.
- `tests/test_customer_session_endpoint.py` — refresh-owner regression test, 58 lines, unchanged
  from iteration 3.
- `.agents/tasks/otp-confirm-fix-20261002/findings.md` — §14 per-finding disposition, §14.5 browser
  re-verification on both rebase bases, §14.6 gates, §14.7 the six upstream failures, §14.9 what
  remains.

Already in `origin/stack`, reviewed in earlier iterations and re-checked here as context: the auth
fix (`customer_auth.py`, `customer-session/handler.py`, `customer-registration/handler.py`,
`identity/registration.py`, `src/lib/customerAuth.ts`), option C, `2f742ec6` (styled-jsx scoping),
`1c847107` (two-tone pill retired on owner instruction), `a4144896` (the shared-layer deploy
record).

Diff commands: `git -C /Users/wecaredigital/wecare-store/.worktrees/otp-fix diff origin/stack` for
the delta; `git show 3ce4936b` for the auth fix as it landed.

</details>
