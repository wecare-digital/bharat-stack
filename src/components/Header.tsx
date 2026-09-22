import React, { useState } from 'react';
import { useRouter } from 'next/router';
import BrandLockup from './BrandLockup';

interface HeaderProps {
  homeBrand?: boolean;
}

const Header: React.FC<HeaderProps> = ( { homeBrand = false } ) => {
  const [ open, setOpen ] = useState( false );
  const router = useRouter();
  const isHome = router.pathname === '/';
  const isGrahakOs = router.pathname === '/grahak-os';

  return (
    <header className={ `hdr ${homeBrand ? 'hdr-home' : ''}`.trim() }>
      <div className="hdr-in">
        <div className="logo-nav">
          <a href="/" className="logo" aria-label="Bharat Stack home">
            <BrandLockup />
          </a>
          <div className="nav-dropdown">
            <button
              type="button"
              className="nav-trigger"
              aria-label="Open navigation"
              aria-expanded={ open }
              onClick={ () => setOpen( value => !value ) }
            >
              <span className="nav-arrow" aria-hidden="true" />
            </button>
            <nav className={ `nav-menu ${open ? 'open' : ''}` } aria-label="Public navigation">
              <a href="/" className={ `nav-item ${isHome ? 'active' : ''}`.trim() } aria-current={ isHome ? 'page' : undefined }>Home</a>
              <a href="/grahak-os/" className={ `nav-item ${isGrahakOs ? 'active' : ''}`.trim() } aria-current={ isGrahakOs ? 'page' : undefined }>Grahak OS</a>
              <a href="/access" className="nav-item">Sign in</a>
            </nav>
          </div>
        </div>
      </div>
      <style jsx>{`
        .hdr{position:fixed;top:0;left:0;right:0;z-index:1001;background:rgba(255,255,255,.97);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)}
        .hdr-in{max-width:1300px;margin:0 auto;padding:18px 24px;display:flex;align-items:center;box-sizing:border-box;height:108px}
        .logo{display:flex;align-items:center;text-decoration:none}
        .logo-nav{display:flex;align-items:center;gap:10px}
        .nav-dropdown{position:relative}
        .nav-trigger{min-width:46px;min-height:46px;background:none;border:0;border-radius:10px;cursor:pointer;padding:8px;display:flex;align-items:center;justify-content:center}
        .nav-trigger:hover,.nav-trigger:focus-visible{background:rgba(209,244,112,.22);outline:none}
        .nav-trigger:focus-visible{box-shadow:0 0 0 3px rgba(26,58,42,.2)}
        .nav-trigger[aria-expanded='true']{background:rgba(209,244,112,.22)}
        .nav-arrow{width:7px;height:7px;box-sizing:border-box;margin:0;border-right:2px solid #1a3a2a;border-bottom:2px solid #1a3a2a;transform:translateY(-2px) rotate(45deg);transition:transform .2s}
        .nav-trigger[aria-expanded='true'] .nav-arrow{transform:translateY(2px) rotate(225deg)}
        .nav-menu{position:absolute;top:calc(100% + 4px);left:0;background:#fff;border:1px solid #d1f470;border-radius:10px;padding:10px 0;min-width:216px;opacity:0;visibility:hidden;transform:translateY(4px);transition:all .2s;box-shadow:0 8px 28px rgba(0,0,0,.10)}
        .nav-dropdown:hover .nav-menu,.nav-dropdown:focus-within .nav-menu,.nav-menu.open{opacity:1;visibility:visible;transform:translateY(0)}
        /* 15px/46px was undersized against a 108px header and a 24px brand lockup,
           and it sat below the 16-17px the global .nav-item rules use for the same
           control elsewhere. 17px on a 54px row also clears the 44px minimum touch
           target with room to spare. min-width went with it so "Grahak OS" cannot
           end up near the padding at the larger size. */
        /* Sized in two passes, and the first one was wrong in a way worth recording:
           the row went to 54px while the type only went to 17px, so the box grew
           proportionally more than the glyphs and the text read SMALLER than before
           rather than larger. 19px puts the type-to-row ratio at ~2.8, near the
           2.5-ish a notion-style menu sits at, and keeps a deliberate step down from
           the 24px brand lockup instead of near-matching it.
           Nothing global was fighting this: the styled-jsx rule carries a jsx class,
           so it beats Layout.css's plain .nav-item on specificity, and
           inner-pages.css's .layout .nav-item block is empty and out of scope for the
           public header anyway. */
        .nav-item{display:flex;align-items:center;min-height:54px;padding:0 22px;font-size:19px;font-weight:600;color:#1a3a2a;text-decoration:none}
        .nav-item:hover,.nav-item:focus-visible,.nav-item.active{background:rgba(209,244,112,.22);outline:none}
        .nav-item.active{font-weight:800}
        /* The .nav-item override here is NOT redundant with the base rule: Layout.css
           declares .nav-item inside its own mobile media queries at 16px and 17px, and
           it is imported globally by _app.tsx. This keeps the public header's size its
           own decision at the breakpoint where those rules switch on. */
        @media(max-width:767px){.hdr-in{height:96px;padding:14px 16px}.logo-nav{gap:8px}.nav-item{font-size:19px;min-height:56px}}
      `}</style>
    </header>
  );
};

export default Header;
