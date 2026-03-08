import React from 'react';

const LOGO_URL = 'https://app.wecare.digital/stream/media/m/wecaredigital.png';

const Header: React.FC = () => (
  <header className="hdr">
    <div className="hdr-in">
      <div className="logo-nav">
        <a href="/" className="logo">
          <img src={LOGO_URL} alt="WECARE.DIGITAL" className="logo-img" />
        </a>
        <div className="nav-dropdown">
          <button className="nav-trigger"><span className="nav-arrow">▼</span></button>
          <div className="nav-menu">
            <a href="/" className="nav-item">CRM</a>
            <a href="/studio" className="nav-item">Studio</a>
            <a href="/sustainability" className="nav-item">Sustainability</a>
            <a href="/access" className="nav-item">Sign in</a>
          </div>
        </div>
      </div>
    </div>
    <style jsx>{`
      .hdr{position:fixed;top:0;left:0;right:0;z-index:1001;background:rgba(255,255,255,.97);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)}
      .hdr-in{max-width:1300px;margin:0 auto;padding:16px 24px;display:flex;align-items:center}
      .logo{display:flex;align-items:center;text-decoration:none}
      .logo-nav{display:flex;align-items:center;gap:4px}
      .logo-img{width:64px;height:64px;border-radius:14px;flex-shrink:0;display:block;object-fit:contain}
      .nav-dropdown{position:relative}
      .nav-trigger{background:none;border:none;cursor:pointer;padding:4px;margin:0;font-family:inherit;transition:all .25s;display:flex;align-items:center;line-height:1}
      .nav-trigger:hover .nav-arrow{color:#059669}
      .nav-arrow{font-size:14px;transition:all .2s;color:#6b7280}
      .nav-dropdown:hover .nav-arrow{transform:rotate(180deg);color:#059669}
      .nav-menu{position:absolute;top:100%;left:0;background:#fff;border:2px solid #e5e7eb;border-radius:12px;padding:8px 0;min-width:180px;opacity:0;visibility:hidden;transform:translateY(4px);transition:all .2s;box-shadow:0 4px 12px rgba(0,0,0,0.08)}
      .nav-dropdown:hover .nav-menu{opacity:1;visibility:visible;transform:translateY(0)}
      .nav-item{display:block;padding:10px 20px;font-size:21px;font-weight:500;color:#6b7280;text-decoration:none;transition:all .25s}
      .nav-item:hover{color:#059669;background:#ecfdf5}
    `}</style>
  </header>
);

export default Header;
