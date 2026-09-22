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

        <span className="ft-mark">WECARE.DIGITAL</span>
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

      .ft-mark{font-size:14px;color:#6b7280}

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
