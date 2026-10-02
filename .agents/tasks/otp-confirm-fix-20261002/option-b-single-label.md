# Option B — single-label pill on `/account/sign-in` (NOT APPLIED)

This is the WCAG 2.5.3 fix described in `findings.md` §9, option B. It was implemented, tested
green in a real browser, and then **deliberately reverted before committing** because it changes
what the owner sees and would re-diverge `/account/sign-in` from `/get`, which `2f742ec6` had just
unified onto the identical two-segment pill on owner instruction.

It is recorded here so the decision is actionable rather than theoretical. **Do not apply it
without the owner's answer.**

Measured when it was applied: single mint segment, `textContent` exactly `Confirm code`,
`aria-label` equal to it, segment correctly scoped, `display:flex`,
`background-color:rgb(95,227,176)`, `color:rgb(26,58,42)`, `font-weight:700`,
`border-radius:999px`, no overflow at 320/360/1280 px, `transition:none` under
`prefers-reduced-motion: reduce`. `/get` and the cart were unaffected because both pass a `label`.

---

## 1. `src/components/PillButton.tsx`

Make `label` optional:

```diff
-  /** The static LEFT-segment label, e.g. "Sign in". White text on the dark-green segment. */
-  label: string;
+  /**
+   * The static LEFT-segment label, e.g. "Sign in". White text on the dark-green segment.
+   *
+   * OPTIONAL. Omitting it renders a SINGLE full-radius action segment, so the visible text
+   * equals the accessible name (WCAG 2.5.3 Label in Name). Omit it for a control whose action
+   * already reads as the whole action; pass it where the label is not a duplicate of the
+   * action, as /get ("Collect", "Pay") and the cart ("Checkout") do.
+   */
+  label?: string;
```

Derive the solo flag and mark the class:

```diff
 } ) => {
-  const className = `pill${ block ? ' pill-block' : '' }`;
+  const solo = !label;
+  const className = `pill${ block ? ' pill-block' : '' }${ solo ? ' pill-solo' : '' }`;
   const name = ariaLabel ?? action;
```

Guard the label span in **both** branches — keeping the segments inline, so `2f742ec6`'s scoping
fix and both its anti-re-hoist guards remain intact. Note each branch still contains one literal
`className="pill-label"`, so their `toHaveLength( 2 )` source guard continues to pass:

```diff
-          <span className="pill-label" aria-hidden="true">{ label }</span>
+          { !solo && <span className="pill-label" aria-hidden="true">{ label }</span> }
           <span className="pill-action" aria-hidden="true">{ action }</span>
```

Add the solo radius rule inside the existing `<style jsx>` block, after `.pill-action`:

```css
/* SINGLE-LABEL MODE. One segment, so there is no divider to draw and both ends take the full
   pill radius. The owner's two-tone edge survives: the 2px #1a3a2a border is on .pill and the
   mint surface is this segment. */
.pill-solo .pill-action{
  border-inline-start:0;
  border-start-start-radius:999px;border-end-start-radius:999px;
}
```

## 2. `src/pages/account/sign-in.tsx`

Drop `label="Sign in"` from both CTAs, leaving everything else as it is:

```diff
               <PillButton
                 as="button"
                 type="submit"
-                label="Sign in"
                 action={ busy ? 'Sending…' : 'Send code' }
```

```diff
               <PillButton
                 as="button"
                 type="submit"
-                label="Sign in"
                 action={ busy ? 'Checking…' : 'Confirm code' }
```

**Do not add an `ariaLabel` here.** Passing `ariaLabel="Send code"` alongside
`action="Sending…"` makes the accessible name stop containing the visible text while busy, which
is the same 2.5.3 failure this option exists to fix. Omitting it keeps name == visible text in
both states and preserves the current behaviour exactly.

## 3. Tests that would need to follow

- `src/test/SignInMessages.test.tsx` — the two `names the … button by its action alone` cases
  tighten to assert exactly one segment and `textContent === 'Confirm code'` / `'Send code'`.
- `src/test/PillButton.test.tsx` — add solo-mode cases (one segment, name == visible text,
  `.pill-solo` applied) and keep `2f742ec6`'s two guards untouched; its
  `renders both segments with the action as the accessible name` case already passes an explicit
  `label`, so it keeps passing unchanged.
- `src/test/PillButtonBuildScope.test.ts` — its second case asserts both `pill-label` and
  `pill-action` are present and hashed on `/account/sign-in`. Under option B that page has no
  `pill-label`, so the per-segment loop must either move to a page that still has one (`/get/`)
  or treat an absent segment as not-applicable. The generic first case needs no change.
- `src/test/GetPage.test.tsx`, `src/test/CartCheckout.test.tsx` — unaffected; both pass a `label`.

## 4. Why option C may be preferable

Option C — drop `aria-hidden` from `pill-label`, drop `aria-label`, and let the accessible name
become "Sign in Confirm code" — fixes the same 2.5.3 defect **everywhere** (sign-in, cart, `/get`)
with **no visual change at all**. Its cost is that it renames every pill, so
`getByRole('button', { name: 'Confirm code' })` and the equivalent queries in `AccountSignIn`,
`SignInMessages`, `CartCheckout`, `GetPage` and `PillButton` tests all have to change. Those names
are pinned deliberately, so it is a visible contract change rather than a silent one — but it
preserves the owner's design, which option B does not.
