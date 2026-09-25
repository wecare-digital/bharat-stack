import React, { useEffect, useRef } from 'react';
import BrandLockup from './BrandLockup';

/**
 * Global site footer, rendered by _app.tsx on every public page and around the
 * sign-in form. Two constraints shape it:
 *
 * 1. All markup stays inline in the return tree. styled-jsx only attaches its
 *    scoping class to elements it can statically see there, so lifting a column
 *    into a variable or a child component would silently drop every style.
 * 2. Every class is ft- prefixed and the old `ftr` class is gone. The globally
 *    imported src/styles/*.css declares unscoped rules for generic names -
 *    including `.layout ~ .ftr{position:fixed}`, which would turn a footer this
 *    tall into an overlay pinned across the viewport.
 *
 * WHAT THIS FOOTER DELIBERATELY DOES NOT CONTAIN, all on owner instruction:
 *  - No Terms / Privacy / Contact links. Those live in the header dropdown, and
 *    repeating them here would duplicate navigation rather than add anything.
 *  - No copyright or year line. A dated "(c) 2026" reads as stale the moment the
 *    year turns, and nothing here needs it.
 *  - No social icons. The company has no social accounts, so an icon row would
 *    point at profiles that do not exist.
 *  - Nothing on the right-hand side at all. It previously held a text link reading
 *    "WECARE.DIGITAL" pointing at https://wecare.digital - which was both a second
 *    copy of the name already set in the lockup on the left, and, on this site, a
 *    link to the page you were already on. Removed rather than replaced.
 */
const Footer: React.FC = () => {
  const dashRef = useRef<HTMLElement | null>( null );

  /**
   * The lime dash draws itself in WHEN IT COMES INTO VIEW, not on page load.
   *
   * The footer sits below the fold on every page, so a load-time CSS animation would
   * play to an empty viewport and be finished before anyone scrolled down to it - the
   * same trap the home page's closing rule documents.
   *
   * THE ANIMATION IS OPT-IN, NOT OPT-OUT, and that inversion is the important part. The
   * CSS below ships the FINAL state (the dash fully drawn). This effect adds .is-armed to
   * hide the start state only once it knows it can animate, then .is-in to play it. So no
   * JS, no IntersectionObserver, or reduced motion all leave the dash simply visible
   * instead of stuck at scaleX(0) - an entrance effect must never be the reason something
   * cannot be seen.
   *
   * classList rather than state, deliberately: this is a visual side-effect that does not
   * change what React renders, so driving the node directly avoids a re-render on scroll.
   */
  useEffect( () => {
    const el = dashRef.current;
    if ( !el ) return undefined;
    if ( typeof IntersectionObserver === 'undefined' ) return undefined;
    if ( window.matchMedia( '(prefers-reduced-motion: reduce)' ).matches ) return undefined;

    el.classList.add( 'is-armed' );
    const io = new IntersectionObserver(
      entries => {
        if ( entries.some( e => e.isIntersecting ) ) {
          el.classList.add( 'is-in' );
          io.disconnect(); // One-shot: an entrance, not a scroll effect.
        }
      },
      { threshold: 0.6 }
    );
    io.observe( el );
    return () => io.disconnect();
  }, [] );

  return (
  <footer className="ft-footer">
    <div className="ft-in">
      <div className="ft-grid">
        <div className="ft-brand">
          {/* THE LOCKUP IS THE LINK HOME, and it is `compact`.
              Both are corrections. It used to be a bare <BrandLockup /> - not clickable -
              while the redundant text copy of the name on the right WAS a link, so the
              footer made the wrong element interactive. And it rendered at the header's
              full 60px/23px scale, so the footer signature was exactly as large as the
              page's primary brand; `compact` steps it to 44px/18px, same shape, clear
              hierarchy.
              A plain <a> rather than next/link: styled-jsx does not scope capitalised
              components, and on a trailingSlash export '/' resolves the same either way. */}
          <a className="ft-home" href="/" aria-label="WECARE.DIGITAL home">
            <BrandLockup compact />
          </a>
          {/* The tagline carries a hover, on owner instruction: the lime underline sweeps
              in from the left, which is the same gesture the header's menu rows use, so
              the two surfaces answer to one visual language.
              IT IS NOT A LINK, deliberately. There is no destination the owner has
              approved for it, and inventing one would mean a hover that promises a click
              and lands somewhere arbitrary. cursor stays default for that reason. If it
              should become a link later, wrap it in an <a> and the sweep still applies. */}
          <p className="ft-tagline">Trusted everyday services for Bharat</p>

          {/* The brand dash. Purely decorative, hence aria-hidden and a <span> rather than
              an <hr> - it separates nothing and announcing it would be noise. It is the
              same motif as .home-close-rule on the home page and .wt-lane-bar in the
              workflow panel: a short lime rule, drawn with transform so the reveal is
              compositor-only. Chosen over the alternative of three coloured dots because
              those would have imported the home page's per-subject hues (which carry
              meaning there and none here) and read as a status light.

              IT USED TO SIT IN THE RIGHT-HAND COLUMN, and that was wrong twice over.
              The instruction for this footer was that the right side be blank, and the
              dash was the only thing in it - so the right side was not blank, it held the
              one decorative element on the page. And the bottom-right corner is where the
              fixed support pill lives, so the two shared a space: measured at the end of
              the page, the pill covered 34px of the 56px dash at 1440 and hid it
              ENTIRELY at 768. On phones it cleared by as little as 8px, which flipped to
              an overlap on a taller device.

              Moved inside .ft-brand it closes the brand block it belongs to, the right
              side is genuinely empty, and the collision cannot recur at any width because
              the two objects no longer share a column. */}
          <span className="ft-dash" ref={ dashRef } aria-hidden="true" />
        </div>
      </div>
    </div>

    <style jsx>{`
      /* A hairline above the footer. Without it the footer background is the same #fff as
         the page with nothing between them, so the brand block read as loose content at
         the bottom of the last section rather than as a footer. #eef0e6 is the faint
         warm-neutral the nav dividers use, not a grey that would sit colder than the
         palette.
         The bottom padding keeps the safe-area inset the Capacitor iOS/Android shells
         depend on. */
      .ft-footer{background:#fff;border-top:1px solid #eef0e6;padding:56px 0 40px;padding-bottom:calc(40px + env(safe-area-inset-bottom))}
      .ft-in{max-width:1300px;margin:0 auto;padding:0 24px}

      /* Left-aligned with nothing opposite it, by instruction. Kept as a flex row rather
         than collapsed to a block so that adding a right-hand element later needs no
         structural change.
         justify-content is flex-start, NOT space-between. With space-between and a single
         child nothing moves, but the moment a second element is added it would be flung to
         the right edge - which is the bottom-right corner the fixed support pill occupies,
         and exactly how the dash came to be hidden behind it. Anything added opposite the
         brand needs to clear that corner deliberately rather than inherit a collision. */
      .ft-grid{display:flex;align-items:flex-end;justify-content:flex-start;gap:32px;flex-wrap:wrap}

      .ft-brand{display:flex;flex-direction:column;align-items:flex-start;gap:14px;min-width:0}

      /* inline-flex, not block: a block anchor would stretch to the full measure and give
         the lockup a click target running the width of the page. */
      .ft-home{display:inline-flex;text-decoration:none;border-radius:10px}
      .ft-home:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:3px}

      /* THE TAGLINE'S COLOUR WAS OFF-PALETTE. It was #9ca3af, a legacy Tailwind grey, which
         rendered the one brand statement on the page as the lightest text in the footer -
         it read as disabled rather than quiet. rgba(0,0,0,.54) is the palette's muted
         value, and is what this file's own notes already recorded as the replacement for
         that family of greys.
         inline-block so the swept underline can span exactly the text, and position
         relative so the ::after anchors to it. */
      .ft-tagline{
        position:relative;display:inline-block;
        font-size:15px;line-height:1.6;color:rgba(0,0,0,.54);
        margin:0;max-width:340px;
        transition:color .2s;
      }
      /* The sweep. transform:scaleX is compositor-only, so it cannot cause layout on any
         frame the way animating width would; transform-origin:left makes it draw from the
         left edge. Same .2s and same easing as the header's row sweep. */
      .ft-tagline::after{
        content:'';position:absolute;left:0;right:0;bottom:-3px;height:2px;
        background:#d1f470;
        transform:scaleX(0);transform-origin:left center;
        transition:transform .2s cubic-bezier(.16,1,.3,1);
      }
      .ft-tagline:hover{color:#1a3a2a}
      .ft-tagline:hover::after{transform:scaleX(1)}

      /* THE LIME DASH. 56x3px, matching .home-close-rule's 3px lime rule.
         READ THE .is-armed PATTERN BEFORE CHANGING THIS: the default below is the FINAL,
         visible state. .is-armed is added by JavaScript only once it has confirmed it can
         animate, and that is what hides the start state; .is-in then plays the reveal. The
         effect is therefore additive and the dash is never invisible for lack of JS.
         transform:scaleX is the whole animation - compositor-only, so it cannot cause
         layout on any frame the way animating width would. transform-origin:left makes it
         grow from the left edge. align-self keeps it on the tagline's baseline row rather
         than stretched by the flex parent. */
      /* align-self is gone, and its absence is the fix. It was flex-end, which in the old
         right-hand position pinned the dash to the right edge - and below 768px, where
         .ft-grid becomes a column with align-items:flex-start, align-self OVERRODE that and
         kept the dash on the right anyway. That is why the collision with the pill was not
         a desktop-only problem: the dash shared the pill's column at all fourteen widths
         and only vertical distance saved the smaller phones. Inside .ft-brand, with no
         align-self, it simply starts where the lockup and tagline start.
         margin-top sits on top of .ft-brand's 14px gap, so the dash closes the block 18px
         under the tagline - far enough not to be mistaken for the tagline's own hover
         underline, which is lime too and only 2px tall. */
      .ft-dash{
        display:block;
        width:56px;height:3px;margin-top:4px;
        background:#d1f470;border-radius:2px;
        transform-origin:left center;
        transition:transform .62s cubic-bezier(.22,.61,.36,1);
      }
      .ft-dash.is-armed{transform:scaleX(0)}
      .ft-dash.is-armed.is-in{transform:scaleX(1)}

      @media(prefers-reduced-motion:reduce){
        .ft-tagline,.ft-tagline::after{transition:none}
        /* Belt and braces. The effect already never arms under reduced motion, so this is
           the guard for the case where the preference changes after arming, when the class
           is already on the node. It kills the movement without hiding the dash. */
        .ft-dash{transition:none}
        .ft-dash.is-armed{transform:scaleX(1)}
      }

      @media(max-width:1024px){
        .ft-footer{padding-top:48px}
      }
      @media(max-width:767px){
        .ft-footer{padding-top:40px}
        .ft-in{padding:0 20px}
        .ft-grid{flex-direction:column;align-items:flex-start;gap:24px}
      }
    `}</style>
  </footer>
  );
};

export default Footer;
