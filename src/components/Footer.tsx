/* eslint-disable @next/next/no-html-link-for-pages --
 * Plain anchors, matching Header.tsx, which navigates the same public routes the
 * same way. next/link is not usable here for two measured reasons:
 *   - styled-jsx does not attach its scoping class to a composite component, so
 *     <Link className="ft-link"> renders an anchor with no ft-link rule applied
 *     (computed colour fell back to rgb(26,26,26) / 17px / transition:all 0s);
 *   - next.config.js sets trailingSlash:true, so Link rewrites href="/faq" to
 *     "/faq/", which stops matching the hrefs this footer is specified to emit.
 */
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
          <p className="ft-tagline">Customer engagement for Bharat.</p>
        </div>

        <nav className="ft-col" aria-label="Product">
          <span className="ft-head">Product</span>
          <a className="ft-link" href="/grahak-os/">Grahak OS</a>
          <a className="ft-link" href="/faq">FAQ</a>
        </nav>

        <nav className="ft-col" aria-label="Company">
          <span className="ft-head">Company</span>
          <a className="ft-link" href="/partners">Partners</a>
          <a className="ft-link" href="https://www.wecare.digital/contact">Contact us</a>
        </nav>

        <nav className="ft-col" aria-label="Account">
          <span className="ft-head">Account</span>
          <a className="ft-link" href="/access">Sign in</a>
        </nav>

      </div>

      <div className="ft-bottom">
        <span className="ft-copy">© 2026 WECARE.DIGITAL</span>
        <span className="ft-mark">
          <i className="ft-dot" aria-hidden="true" />
          Bharat Stack
        </span>
      </div>
    </div>

    <style jsx>{`
      /* Hairline lid, white canvas. The bottom padding keeps the safe-area
         inset the Capacitor iOS/Android shells depend on. */
      .ft-footer{border-top:1px solid #e5e7eb;background:#fff;padding:64px 0 40px;padding-bottom:calc(40px + env(safe-area-inset-bottom))}
      .ft-in{max-width:1300px;margin:0 auto;padding:0 24px}

      .ft-grid{display:grid;grid-template-columns:2fr 1fr 1fr 1fr;gap:48px}

      .ft-brand{display:flex;flex-direction:column;align-items:flex-start;gap:16px;min-width:0}
      .ft-tagline{font-size:15px;line-height:1.6;color:#9ca3af;margin:0;max-width:280px}

      .ft-col{display:flex;flex-direction:column;align-items:flex-start;min-width:0}
      .ft-head{display:block;font-size:13px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:#9ca3af;margin-bottom:16px;line-height:1.2}
      /* flex + centring so the global a{min-height} touch-target floor (32px,
         44px on mobile) grows the row around the label instead of top-aligning it */
      .ft-link{display:flex;align-items:center;font-size:15px;line-height:1.5;color:#6b7280;text-decoration:none;padding:5px 0;transition:color .2s}
      .ft-link:hover{color:#1a3a2a}

      .ft-bottom{display:flex;align-items:center;justify-content:space-between;gap:16px;margin-top:32px;padding-top:24px;border-top:1px solid #e5e7eb}
      .ft-copy{font-size:14px;color:#9ca3af}
      .ft-mark{display:inline-flex;align-items:center;gap:8px;font-size:14px;color:#6b7280}
      .ft-dot{width:6px;height:6px;border-radius:50%;background:#d1f470;flex:0 0 auto}

      /* Account wraps onto the next row before the columns get too narrow. */
      @media(max-width:1024px){
        .ft-footer{padding-top:56px}
        .ft-grid{grid-template-columns:2fr 1fr 1fr;gap:40px}
      }
      @media(max-width:767px){
        .ft-footer{padding-top:48px}
        .ft-in{padding:0 20px}
        .ft-grid{grid-template-columns:1fr;gap:32px}
        .ft-bottom{flex-direction:column;align-items:flex-start;gap:12px}
      }
      @media(prefers-reduced-motion:reduce){
        .ft-link{transition:none}
      }
    `}</style>
  </footer>
);

export default Footer;
