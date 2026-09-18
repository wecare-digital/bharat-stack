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
              <span className="nav-arrow" aria-hidden="true">▼</span>
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
        .nav-arrow{font-size:15px;color:#1a3a2a;transition:transform .2s}
        .nav-trigger[aria-expanded='true'] .nav-arrow{transform:rotate(180deg)}
        .nav-menu{position:absolute;top:calc(100% + 4px);left:0;background:#fff;border:1px solid #d1f470;border-radius:12px;padding:8px 0;min-width:190px;opacity:0;visibility:hidden;transform:translateY(4px);transition:all .2s;box-shadow:0 8px 28px rgba(0,0,0,.10)}
        .nav-dropdown:hover .nav-menu,.nav-dropdown:focus-within .nav-menu,.nav-menu.open{opacity:1;visibility:visible;transform:translateY(0)}
        .nav-item{display:flex;align-items:center;min-height:46px;padding:0 20px;font-size:20px;font-weight:600;color:#1a3a2a;text-decoration:none}
        .nav-item:hover,.nav-item:focus-visible,.nav-item.active{background:rgba(209,244,112,.22);outline:none}
        .nav-item.active{font-weight:800}
        @media(max-width:767px){.hdr-in{height:96px;padding:14px 16px}.logo-nav{gap:8px}.nav-item{font-size:18px}}
      `}</style>
      <style jsx global>{`
        .page .hero-left h1{font-size:clamp(38px,5.3vw,68px)!important;line-height:1.04!important;letter-spacing:-1.8px!important}
        .page .hero-left p{font-size:clamp(18px,1.7vw,22px)!important;line-height:1.6!important}
        .page .section-header h2{font-size:clamp(32px,4vw,52px)!important;line-height:1.1!important}
        .page .section-header p{font-size:clamp(18px,1.5vw,21px)!important}
        .page .api-info h2{font-size:clamp(32px,3.6vw,46px)!important}
        .page .api-desc{font-size:clamp(18px,1.5vw,21px)!important}
        .page .capability-card h3{font-size:clamp(20px,1.7vw,26px)!important}
        .page .capability-card p{font-size:clamp(17px,1.3vw,20px)!important}
        .page .cta-section h2{font-size:clamp(34px,4.5vw,56px)!important}
        @media(max-width:480px){.page .hero-left h1{font-size:clamp(36px,10vw,44px)!important}.page .section-header h2,.page .api-info h2{font-size:clamp(30px,8.5vw,38px)!important}}
      `}</style>
    </header>
  );
};

export default Header;
