# Option C — authorization record

The review flagged, correctly, that option C was applied with no confirmation artifact in
this directory. C renames the accessible name of every pill on the site, so "the owner
approved it" needed to be auditable rather than asserted in a notification. This file is
that record, written by the orchestrator who gave the authorization.

## What was asked

The implementing agent found that `/account/sign-in` still passed `label="Sign in"`
alongside `action="Confirm code"`, so the button's visible text was `Sign in Confirm code`
while its accessible name was `Confirm code` — a **WCAG 2.5.3 Label in Name** mismatch
(Level A). It offered three options and recommended C:

| | |
|---|---|
| **A** | Leave it. The 2.5.3 mismatch stays on sign-in, cart and `/get`. |
| **B** | Single-label mode on sign-in only. Sign-in loses its `Sign in` segment. |
| **C** | Keep both segments; drop `aria-hidden` from the label and drop `aria-label`, so the name becomes the visible text. Zero visual change. |

It had already implemented B, tested it green in a browser, and then **reverted it before
committing** on the grounds that B re-diverges two surfaces `2f742ec6` had just
deliberately converged on owner instruction. The unapplied B diff is preserved beside this
file at `option-b-single-label.md`.

## The decision: C

Authorized by the orchestrator on 2026-10-02. The reasoning, recorded so it can be
disagreed with later rather than reconstructed:

- **B's cost is a product regression, not a code cost.** `2f742ec6` unified `/get` onto
  this same pill with `label="Collect"`/`"Pay"` on explicit owner instruction. Making
  sign-in single-label would re-diverge the two surfaces that commit had just converged,
  and would delete a label the owner's design brief asked for. The agent's instinct to
  revert its own working implementation on those grounds was right.
- **A is not tenable, because 2.5.3 is Level A and its beneficiaries are real.** The
  criterion exists for speech-input users: someone who says "click Sign in" at a button
  whose accessible name is `Confirm code` gets nothing. No amount of visual polish
  compensates for a control that cannot be addressed by the words printed on it.
- **C is the only option that fixes all three surfaces without trading the design.** Zero
  pixels move. That is the entire reason it is worth doing, and the reason condition 4
  below made "zero visual change" a verified requirement rather than an intention.

## Conditions attached, and how each was met

| # | Condition | Outcome |
|---|---|---|
| 1 | Separate commit from the auth fix. Backend needs three Lambdas republished with `live` aliases moved; this ships via Amplify. Different blast radius, different rollback, must not be entangled in a revert of the other. | Met. Auth is `c86e82be`, C is `d171fd10`. Separation verified by diff in both directions. One disclosed exception: `src/test/PillButtonBuildScope.test.ts` sits in the auth commit because it predates C and tests scoping rather than 2.5.3. Test-only, so it cannot affect a Lambda deploy. |
| 2 | Update pinned `getByRole` queries to the new **exact** names. Do not loosen to regex or substring. | Met. Exact strings in `AccountSignIn`, `SignInMessages`, `PublicPageTopBand`, `CartCheckout`, `GetPage`, `PillButton`. `GetPage`'s pre-existing `/Send code/i` was **tightened** to an exact pin. The only predicate matcher left is inside the property test, where "contains" is the criterion itself. |
| 3 | Add a property test asserting the accessible name **contains** the visible text, not just five new literals. | Met. `src/test/PillButtonAccessibleName.test.tsx`, 14 cases over all ten real prop shapes including both busy states, plus structural guards. Revert-checked: restoring `aria-hidden` + `aria-label` fails all 14. |
| 4 | Zero visual change, verified in a browser, not asserted. | Met in Chrome 154. Computed style identical to the pre-C measurement on all three surfaces. No CSS touched. |
| 5 | Leave `2f742ec6`'s anti-re-hoist guards and the build-scope test alone. | Met, byte-unchanged. Their render-side case had only its accessibility-tree expectations inverted, because asserting both segments were `aria-hidden` and the name was the action alone **was** the 2.5.3 failure. |

## On the review's third blocking finding

The review is right that defect 2 **as briefed** was not delivered, and right that the
brief's premise was wrong. The brief asked for a single label and an assertion that the
name is not a concatenation. By the time the work reached that item, two things had
changed:

1. The run-together rendering `Sign inConfirm code` was a **styled-jsx scoping bug**, not a
   two-labels bug, and it was fixed upstream in `2f742ec6`. None of that repair is in this
   branch, correctly — the agent discarded its own equivalent diff.
2. What remained was a genuine but *different* defect: two visible labels against a
   one-label accessible name.

So the brief described the symptom accurately and the cause incorrectly. The orchestrator
settles it here: **C is the delivered and intended outcome.** The concatenation is pinned
deliberately, because after C the concatenation *is* the accessible name and pinning it is
how 2.5.3 stays satisfied. An assertion that the name is not a concatenation would now
assert the violation.

`ariaLabel` was removed as a prop rather than left unused, which was the agent's own call
and is the right one: while it existed, any caller could set a name that disagreed with the
screen, which is exactly how this shipped. Removing it makes the guarantee structural
instead of conventional. The cart was its only user.

## Deployment ordering — carried forward

The review's non-blocking note on this is important and is not a detail. Shipping
`d171fd10` before the shared layer moves would leave sign-in appearing to succeed and then
failing at the store catalogue and checkout, which is a worse experience than today's
honest failure. The auth commit's three Lambdas go first; the frontend follows.
