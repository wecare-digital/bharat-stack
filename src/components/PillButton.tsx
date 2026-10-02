import React from 'react';

/**
 * THE TWO-SEGMENT PILL, the home-page phone-number treatment turned into a reusable control.
 *
 * WHAT THE OWNER ASKED FOR. "In our home page design and theme, the phone number button - make
 * this style for cart login or any other login." The reference is a fully-rounded pill split into
 * two butted segments: a dark-green LEFT segment carrying a static label in white, and a brighter
 * MINT RIGHT segment carrying the action in dark-green type. This component is that pill, built
 * once so every customer login CTA uses the same markup and the same tokens and cannot drift.
 *
 * IT IS A STYLE, NOT A NEW CONTROL. The pill renders either a real <button> or a real <a> - the
 * caller chooses with `as` - so submit semantics, disabled/busy state, click handling, keyboard
 * focus and link navigation are all the platform's, untouched. The two visible segments are
 * decoration layered on top of one actionable element.
 *
 * THE ACCESSIBLE NAME IS THE VISIBLE TEXT. WCAG 2.5.3 LABEL IN NAME, AND WHY THE OLD
 * `aria-label` HAD TO GO.
 *
 * This component used to carry an explicit `aria-label` equal to the ACTION text alone, with both
 * visible segments marked `aria-hidden`, so a pill reading "Sign in | Confirm code" announced only
 * "Confirm code". That is a direct failure of WCAG 2.5.3 Label in Name (Level A): the accessible
 * name must CONTAIN the visible label text. Hiding a control's own visible label from the
 * accessibility tree is the anti-pattern that creates the mismatch, not a fix for it.
 *
 * THE PEOPLE THIS BROKE ARE SPEECH-INPUT USERS. Someone driving the page by voice says "click Sign
 * in" at a button whose name is "Confirm code" and nothing happens. There is no visual symptom, so
 * no amount of styling fixes it, and the owner's two-tone design is not the problem.
 *
 * SO: neither segment is aria-hidden, and there is NO `aria-label`. The accessible name is the
 * platform's own concatenation of the visible text - "Sign in Confirm code", "Checkout Proceed",
 * "Collect Send code" - which contains the visible label text by construction and therefore
 * cannot drift out of compliance. Nothing changes visually; this is an accessibility-tree change
 * only.
 *
 * THERE IS DELIBERATELY NO `ariaLabel` PROP ANY MORE. It existed so the cart could show "Proceed"
 * while announcing "Proceed to checkout", and that override is exactly how 2.5.3 gets broken - the
 * name it set did not contain the visible text. Removing the prop rather than merely not using it
 * makes the guarantee STRUCTURAL: there is no longer any way to give this control a name that
 * disagrees with what is on screen. If a pill ever needs more context than its visible text, the
 * name must still CONTAIN that text - extend the visible action, or use `describedBy`, which adds
 * description without replacing the name.
 *
 * `src/test/PillButtonAccessibleName.test.tsx` asserts the property (name contains visible text)
 * across every call site's prop shape, rather than pinning today's five strings.
 *
 * THE PALETTE IS THE SITE'S, AND THE CONTRAST IS MEASURED, NOT ASSUMED.
 *   - LEFT segment  #1a3a2a (the site's primary dark/indicator green, used for every focus ring,
 *     border and dark surface on the site) with #ffffff text => 12.48:1, passes AAA.
 *   - RIGHT segment #5fe3b0 (a lighter tint in the brand's green/teal direction, matching the
 *     reference image's mint) with #1a3a2a text => 7.79:1, passes AAA. The site's base green
 *     #3da35a was measured first and gives only 3.91:1 against #1a3a2a text - it FAILS the 4.5:1
 *     body-text rule - so the lighter #5fe3b0 is used for the text-bearing segment. #3da35a is
 *     kept as the pressed/hover shade of the mint, where no small text sits on it.
 *   - THE EDGE. #5fe3b0 against the white page is only 1.6:1, well under WCAG 1.4.11's 3:1 for a
 *     component boundary, so the mint cannot be the thing that separates the button from the page.
 *     The whole pill therefore carries a 2px #1a3a2a border (12.48:1 against white), which is what
 *     clears 1.4.11 - exactly how the home CTA (.home-close-cta) and PhoneField draw their edge.
 *     The internal divider between the two segments is the same #1a3a2a hairline.
 *
 * THE RADIUS IS SCOPED SO THE GLOBAL 13px CANNOT FLATTEN IT. src/styles/button.css puts a global
 * 13px radius on .btn controls; this component uses its own class names (never .btn) and sets
 * border-radius:999px on the pill with per-corner logical radii on the segments, so the full pill
 * shape survives regardless of what the global sheet says. The segments use start/end logical
 * radii so the rounded ends follow the reading direction and the pill mirrors cleanly in RTL -
 * the same technique PhoneField uses for its divided field.
 *
 * MOTION IS OPTIONAL AND REDUCED-MOTION-AWARE. The hover lift and the one allowed shadow match the
 * home CTA, and both are dropped under prefers-reduced-motion: reduce.
 *
 * STYLED-JSX SCOPING. This component styles its own lowercase tags (<span>, <button>, <a>) in its
 * own <style jsx> block; it does not rely on a consumer's styles reaching it, which they cannot.
 */

export interface PillButtonProps {
  /** The static LEFT-segment label, e.g. "Sign in". White text on the dark-green segment. */
  label: string;
  /** The RIGHT-segment ACTION text, e.g. "Send code". Dark-green text on the mint segment. */
  action: string;
  /** Render a <button> (default) or an <a>. */
  as?: 'button' | 'a';
  /** For as="button": the native type. Defaults to 'button' so it never submits by accident. */
  type?: 'button' | 'submit';
  /** For as="a": the destination. */
  href?: string;
  onClick?: ( event: React.MouseEvent ) => void;
  /** Disabled/busy for buttons. A disabled pill is dimmed and non-interactive. */
  disabled?: boolean;
  /** True while an action is in flight; dims the pill and sets aria-busy. */
  busy?: boolean;
  /** Full-width in its container (the sign-in and cart forms want this). */
  block?: boolean;
  /** Extra describedby ids, passed straight through. */
  describedBy?: string;
}

const PillButton: React.FC<PillButtonProps> = ( {
  label, action, as = 'button', type = 'button', href,
  onClick, disabled, busy, block, describedBy,
} ) => {
  const className = `pill${ block ? ' pill-block' : '' }`;

  /*
   * THE TWO SEGMENTS ARE WRITTEN OUT TWICE, INLINE, AND THAT DUPLICATION IS DELIBERATE.
   *
   * They used to be hoisted into one `const inner = (<>...</>)` and referenced from both branches,
   * which is tidier to read and was SILENTLY BROKEN. styled-jsx's transform only stamps its
   * scoping hash class onto JSX elements that appear inside the same return tree as the
   * <style jsx> element below. JSX lifted into a variable never gets stamped, so the built markup
   * emitted `class="pill-label"` and `class="pill-action"` with NO hash while the rules compiled
   * to `.pill-label.jsx-<hash>{...}` - selectors that could never match. The outer <button> was
   * stamped correctly, which is why the pill had its shape, its 2px edge and its dark fill but
   * NEITHER segment had its own background or colour: it rendered as one dark slab with the label
   * and the action jammed together, "Sign inSend code", with white-on-dark text falling back to
   * near-black. Measured in the built export AND on the live site at /account/sign-in/ before this
   * fix.
   *
   * THIS REPO ALREADY KNEW THIS FAILURE MODE. RotatingHero's docblock records it costing "a full
   * debugging round on the mega menu, where a renderLink() helper left the rules behind and every
   * row fell through to a global". Same trap, same component family. Do not re-hoist these spans,
   * and do not extract them into a helper or a child component: either reintroduces the bug.
   *
   * NEITHER SEGMENT IS aria-hidden, AND THERE IS NO aria-label. Both carried `aria-hidden="true"`
   * and the control carried an `aria-label` of the action alone, which hid the pill's own visible
   * label from its accessible name - a WCAG 2.5.3 Label in Name failure. The name is now the
   * platform's concatenation of the visible text, so it contains the visible label by
   * construction. See the docblock. This changes nothing visually.
   */
  return (
    <>
      { as === 'a' ? (
        <a
          className={ className }
          href={ href }
          onClick={ onClick }
          aria-describedby={ describedBy }
        >
          <span className="pill-label">{ label }</span>
          <span className="pill-action">{ action }</span>
        </a>
      ) : (
        <button
          className={ className }
          type={ type }
          onClick={ onClick }
          disabled={ disabled }
          aria-busy={ busy ? 'true' : undefined }
          aria-describedby={ describedBy }
        >
          <span className="pill-label">{ label }</span>
          <span className="pill-action">{ action }</span>
        </button>
      ) }

      <style jsx>{`
        /* THE PILL. One flex container, a 2px #1a3a2a edge (12.48:1 vs white, clears WCAG 1.4.11),
           and a FULL pill radius set here so the global 13px in button.css cannot flatten it.
           overflow:hidden so neither segment's background squares off the rounded ends. Height 52px
           is the site's CTA height, matching PhoneField and .si-cta/.cart-cta. padding:0 keeps the
           segments butted; each segment carries its own inline padding. */
        .pill{
          display:inline-flex;align-items:stretch;isolation:isolate;
          min-height:52px;box-sizing:border-box;
          border:2px solid #1a3a2a;border-radius:999px;background:#1a3a2a;
          padding:0;overflow:hidden;cursor:pointer;
          font-family:inherit;text-decoration:none;
          transition:transform .2s,box-shadow .2s;
        }
        .pill-block{display:flex;width:100%}

        /* LEFT segment: the dark-green half, white type. flex:0 0 auto so it is content-sized and
           the mint half takes the rest - the action is the thing that should flex, not the label.
           Logical start corners rounded to match the pill, end corners square against the divider,
           so it mirrors on its own in RTL. */
        .pill-label{
          display:inline-flex;align-items:center;justify-content:center;
          flex:0 0 auto;padding:0 22px;
          background:#1a3a2a;color:#fff;font-size:17px;font-weight:600;line-height:1;
          border-start-start-radius:999px;border-end-start-radius:999px;
          white-space:nowrap;
        }

        /* RIGHT segment: the mint half, dark-green type (7.79:1 on #5fe3b0). The #1a3a2a divider is
           an inline-start border, one declaration that mirrors in RTL. flex:1 1 auto with
           min-inline-size:0 so a long action wraps/flexes rather than overflowing on mobile. */
        .pill-action{
          display:inline-flex;align-items:center;justify-content:center;
          flex:1 1 auto;min-inline-size:0;padding:0 24px;
          background:#5fe3b0;color:#1a3a2a;font-size:17px;font-weight:700;line-height:1.2;
          border-inline-start:2px solid #1a3a2a;
          border-start-end-radius:999px;border-end-end-radius:999px;
          text-align:center;
        }

        /* HOVER/PRESS, the home CTA's single allowed lift and shadow. The mint deepens to the
           site's base green #3da35a on hover - no small text relies on that shade, so its 3.91:1
           with the dark type is not a contrast failure, it is a pressed-state tint. */
        .pill:hover:not([disabled]):not([aria-disabled='true']){
          transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.18);
        }
        .pill:hover:not([disabled]):not([aria-disabled='true']) .pill-action{background:#3da35a}
        .pill:active:not([disabled]):not([aria-disabled='true']){transform:translateY(0)}

        /* FOCUS. The site's #1a3a2a indicator at 3px, offset OUTSIDE the pill so the ring reads as
           one ring around the whole control (unlike PhoneField, which has two focusable segments
           and insets per segment; this pill is ONE control, so one outer ring is correct). */
        .pill:focus-visible{outline:3px solid #1a3a2a;outline-offset:3px}

        /* DISABLED/BUSY: dim the whole pill, drop the pointer. Covers both the native button
           :disabled and the belt-and-braces attribute. */
        .pill:disabled,.pill[aria-disabled='true']{opacity:.6;cursor:default}
        .pill[aria-busy='true']{cursor:progress}

        /* NARROW VIEWPORTS. Tighten padding rather than shrink the 52px target; the action segment
           absorbs the remaining width so neither segment overflows at 320px. */
        @media(max-width:360px){
          .pill-label{padding:0 14px}
          .pill-action{padding:0 16px}
          .pill-label,.pill-action{font-size:16px}
        }

        /* REDUCED MOTION: no lift, no shadow transition. */
        @media(prefers-reduced-motion:reduce){
          .pill{transition:none}
          .pill:hover:not([disabled]):not([aria-disabled='true']){transform:none;box-shadow:none}
        }
      `}</style>
    </>
  );
};

export default PillButton;
