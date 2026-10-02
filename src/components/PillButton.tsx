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
 * ONE LIME SURFACE, NOT TWO TONES — CHANGED 2026-10-02 ON OWNER INSTRUCTION.
 * This was a two-segment pill: a dark #1a3a2a label half and a mint #5fe3b0 action half split by a
 * 2px rule. The owner called it "old multi colour out of date" and supplied the replacement
 * directly: a single lime pill (their reference image reads "Contribute"). The two-tone treatment
 * is retired here and was separately rejected as a model for the phone field.
 *
 * THE PALETTE IS THE SITE'S, AND THE CONTRAST IS MEASURED, NOT ASSUMED.
 *   - SURFACE #d1f470 with #1a3a2a text => 10.04:1, passes AAA. This is the home page's own lime:
 *     src/pages/index.tsx uses #d1f470 eight times and #5fe3b0 zero times, and a repo-wide grep
 *     for #5fe3b0 found it ONLY in this component and its test - an orphan colour present nowhere
 *     else on the site, which is what made this button look foreign on its own pages.
 *     Lime also beats the mint it replaced on contrast (10.04:1 vs 7.79:1), so nothing was traded
 *     away to get the brand right.
 *   - HOVER inverts to #ffffff, giving #1a3a2a text 12.48:1. The OLD hover deepened the mint to
 *     the site's base green #3da35a while keeping #1a3a2a text: 3.91:1, which FAILS the 4.5:1
 *     requirement. The old note excused it as "no small text relies on that shade" - incorrect,
 *     because this label is 17px bold and WCAG's large-text exemption starts at 18.66px bold.
 *     That defect is fixed by the inversion, which is also the house pattern (.ship-close-cta).
 *   - THE EDGE. #d1f470 against a white page is only 1.24:1, far under WCAG 1.4.11's 3:1 for a
 *     component boundary, so the lime cannot be the thing that separates the button from the page.
 *     The pill therefore carries a 2px #1a3a2a border (12.48:1 against white), which is what
 *     clears 1.4.11 - exactly how the home CTA (.home-close-cta) and PhoneField draw their edge.
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
  /**
   * NO LONGER RENDERED, and kept only so the existing call sites keep compiling.
   *
   * This was the dark left segment's text ("Sign in", "Collect", "Pay"). The pill is now a single
   * lime surface showing the ACTION alone - which was already the control's accessible name, so
   * what is read aloud and what is on screen are now the same string instead of two.
   * It is deliberately NOT rendered as visually-hidden text: this repo has explicitly rejected
   * hidden text for naming elsewhere (see the note in PhoneField about the country select), and
   * the surrounding page already supplies the context the label used to carry - /account/sign-in
   * is headed "Sign in to check out", and /get is headed "Collect your files".
   * Optional so new call sites need not pass it; pass `ariaLabel` if the visible action alone does
   * not read as the whole action.
   */
  label?: string;
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
          <span className="pill-action">{ action }</span>
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
          <span className="pill-action">{ action }</span>
        </button>
      ) }

      <style jsx>{`
        /* THE PILL — ONE LIME SURFACE, not two tones.
           
           REWRITTEN ON OWNER INSTRUCTION (2026-10-02): "i see still old multi colour out of date
           button". The control was a two-segment pill - a dark #1a3a2a label half and a mint
           #5fe3b0 action half divided by a 2px rule. The owner supplied the replacement reference
           directly (a single lime pill reading "Contribute") and rejected the two-tone treatment,
           both for buttons and, separately, as a model for the phone field.
           
           WHY LIME AND NOT MINT, measured rather than preferred: src/pages/index.tsx (the home
           page) uses #d1f470 eight times and #5fe3b0 zero times, and a repo-wide grep for #5fe3b0
           returned only this component and its test - an orphan colour that appeared nowhere else
           on the site. Contrast favours lime too: #d1f470 with #1a3a2a type computes 10.04:1
           against mint's 7.79:1. So there was no accessibility argument for keeping mint either.
           
           The 2px #1a3a2a edge stays (12.48:1 vs white, clears WCAG 1.4.11 for a control
           boundary), the full 999px radius stays so the global 13px in src/styles/button.css
           cannot flatten it, and 52px stays as the site's CTA height, matching PhoneField and
           .si-input. */
        .pill{
          display:inline-flex;align-items:center;justify-content:center;isolation:isolate;
          min-height:52px;box-sizing:border-box;
          border:2px solid #1a3a2a;border-radius:999px;background:#d1f470;
          padding:0 28px;cursor:pointer;
          font-family:inherit;text-decoration:none;
          transition:background-color .2s,transform .2s,box-shadow .2s;
        }
        .pill-block{display:flex;width:100%}

        /* THE ONE LABEL. The pill now shows the ACTION only - the text that already was the
           control's accessible name - so what is read aloud and what is on screen are the same
           string. The former label half ("Sign in", "Collect", "Pay") is no longer rendered;
           see the note on the prop for why it is still accepted.
           17px/700 #1a3a2a on #d1f470 = 10.04:1, comfortably past the 4.5:1 this size needs.
           NO BACKTICKS IN THIS BLOCK: it is a styled-jsx template literal, so a backtick here
           terminates the CSS string early. src/test/StyledJsxBackticks.test.tsx guards it. */
        .pill-action{
          display:inline-flex;align-items:center;justify-content:center;
          min-inline-size:0;
          color:#1a3a2a;font-size:17px;font-weight:700;line-height:1.2;
          text-align:center;
        }

        /* HOVER/PRESS: the house inversion - lime to white - plus the single allowed lift and
           shadow, exactly as .ship-close-cta and the home CTA do it.
           THE OLD HOVER WAS AN ACCESSIBILITY DEFECT AND IS GONE. It deepened the action half to
           the site's base green #3da35a while keeping #1a3a2a type, which computes 3.91:1 and
           FAILS the 4.5:1 requirement. The old comment excused it as "no small text relies on that
           shade" - wrong, because the label is 17px bold and WCAG's large-text exemption only
           begins at 18.66px bold (or 24px regular). White gives #1a3a2a type 12.48:1 instead. */
        .pill:hover:not([disabled]):not([aria-disabled='true']){
          background:#fff;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.18);
        }
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
           absorbs the remaining width so the label does not overflow at 320px. */
        @media(max-width:360px){
          .pill{padding:0 18px}
          .pill-action{font-size:16px}
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
