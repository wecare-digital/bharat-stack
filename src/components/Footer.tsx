import React from 'react';
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
 */
const Footer: React.FC = () => (
  <footer className="ft-footer">
    <div className="ft-in">
      <div className="ft-grid">
        <div className="ft-brand">
          <BrandLockup />
          <p className="ft-tagline">Trusted everyday services for Bharat</p>
        </div>

        {/* Links out to the company site. It was a bare span, so the one place on every
            public page that names WECARE.DIGITAL was not clickable. External and
            cross-origin, hence rel="noopener" - and a plain anchor rather than next/link
            because this leaves the app entirely. */}
        <a className="ft-mark" href="https://wecare.digital" rel="noopener noreferrer">WECARE.DIGITAL</a>
      </div>
    </div>

    <style jsx>{`
      /* No divider rules anywhere: navigation lives in the header dropdown and
         contact is handled by the floating widget, so the footer is reduced to a
         brand signature. The bottom padding keeps the safe-area inset the
         Capacitor iOS/Android shells depend on. */
      .ft-footer{background:#fff;padding:64px 0 40px;padding-bottom:calc(40px + env(safe-area-inset-bottom))}
      .ft-in{max-width:1300px;margin:0 auto;padding:0 24px}

      .ft-grid{display:flex;align-items:flex-end;justify-content:space-between;gap:32px;flex-wrap:wrap}

      .ft-brand{display:flex;flex-direction:column;align-items:flex-start;gap:16px;min-width:0}
      .ft-tagline{font-size:15px;line-height:1.6;color:#9ca3af;margin:0;max-width:320px}

      /* No underline in either state, by request - it previously appeared on hover.
         That leaves colour as the only hover signal, which is fine for a standalone
         mark, but colour alone is NOT an adequate keyboard focus indicator. So
         :focus-visible is split out of the hover rule and gets a real ring rather
         than inheriting a style that no longer draws anything. The ring reuses the
         outline the language widget already uses instead of inventing a second one. */
      /* Hover is the site's lime TRANSIENT tint - rgba(209,244,112,.22) behind
         #1a3a2a type - not a colour change and not the full-strength #d1f470 fill.
         The contract defines exactly three lime treatments and assigns that .22 tint
         to transient state rather than identity; it is what .nav-item and
         .nav-trigger already do on hover, so this link now answers to the same
         gesture as the rest of the site instead of inventing a fourth treatment.
         Full-strength lime is reserved for our own standing surfaces (BrandBadge,
         .msg.sent, .tab.active) and would have made a hovered footer link look like
         a permanent badge.
         Padding and radius exist so the tint has a shape to fill - without them a
         background on an inline anchor crops tight to the glyphs and reads as a
         highlighter smear. Negative margin keeps the text optically aligned with the
         grid edge despite that padding.
         Base colour moved off #6b7280, a legacy Tailwind grey, onto the palette's
         muted value rgba(0,0,0,.54) - the same value the contract already pins for
         pill labels after #4b5563 was retired for reading cooler than the neutral
         text beside it. */
      .ft-mark{font-size:14px;color:rgba(0,0,0,.54);text-decoration:none;padding:6px 10px;margin:-6px -10px;border-radius:8px;transition:background-color .2s,color .2s}
      .ft-mark:hover{background:rgba(209,244,112,.22);color:#1a3a2a}
      .ft-mark:focus-visible{background:rgba(209,244,112,.22);color:#1a3a2a;outline:3px solid rgba(26,58,42,.22);outline-offset:2px}

      /* Account wraps onto the next row before the columns get too narrow. */
      @media(max-width:1024px){
        .ft-footer{padding-top:56px}
      }
      @media(max-width:767px){
        .ft-footer{padding-top:48px}
        .ft-in{padding:0 20px}
        .ft-grid{flex-direction:column;align-items:flex-start;gap:24px}
      }
    `}</style>
  </footer>
);

export default Footer;
