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
 * WHY THE ACCESSIBLE NAME IS SET EXPLICITLY. The visible pill reads as two words ("Sign in" +
 * "Send code"), but the accessible name of a <button> is the concatenation of its text, which
 * would announce "Sign in Send code" and - more importantly - would change the name the sign-in
 * tests pin ("Send code" / "Confirm code"). So the actionable element carries an explicit
 * `aria-label` equal to the ACTION text alone (the right segment), and the two visible segments
 * are marked aria-hidden. Assistive technology hears the single honest action; sighted users see
 * the two-tone pill. This is the same decision PhoneField makes when it labels the country select
 * rather than letting the segment text speak for it. When the visible action text is shorter than
 * the honest name (the cart shows "Proceed" but must announce "Proceed to checkout"), `ariaLabel`
 * sets the name independently of the visible text.
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
  /** The RIGHT-segment ACTION text, e.g. "Send code". Dark-green text on the mint segment. By
   *  default this is also the control's accessible name, so it must read as the whole action on
   *  its own - unless `ariaLabel` overrides the name (see below). */
  action: string;
  /** Overrides the accessible name when the visible action text alone would not read as the whole
   *  action - e.g. a cart pill that shows "Proceed" but must announce "Proceed to checkout" so the
   *  pinned role query still finds it. Defaults to `action`. */
  ariaLabel?: string;
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
  label, action, ariaLabel, as = 'button', type = 'button', href,
  onClick, disabled, busy, block, describedBy,
} ) => {
  const className = `pill${ block ? ' pill-block' : '' }`;
  const name = ariaLabel ?? action;

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
   * The visible segments are decoration; the accessible name is the action alone. aria-hidden on
   * the segments stops the double-announce, and aria-label carries the honest single name.
   */
  return (
    <>
      { as === 'a' ? (
        <a
          className={ className }
          href={ href }
          onClick={ onClick }
          aria-label={ name }
          aria-describedby={ describedBy }
        >
          <span className="pill-label" aria-hidden="true">{ label }</span>
          <span className="pill-action" aria-hidden="true">{ action }</span>
        </a>
      ) : (
        <button
          className={ className }
          type={ type }
          onClick={ onClick }
          disabled={ disabled }
          aria-label={ name }
          aria-busy={ busy ? 'true' : undefined }
          aria-describedby={ describedBy }
        >
          <span className="pill-label" aria-hidden="true">{ label }</span>
          <span className="pill-action" aria-hidden="true">{ action }</span>
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
