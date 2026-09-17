import React from 'react';

const LOGO_URL = 'https://app.wecare.digital/stream/media/m/wecaredigital.png';

interface BrandLockupProps {
  compact?: boolean;
  suffix?: React.ReactNode;
  className?: string;
}

const BrandLockup: React.FC<BrandLockupProps> = ( { className = '' } ) => (
  <span className={ `brand-lockup full ${className}`.trim() }>
    <img src={ LOGO_URL } alt="" aria-hidden="true" />
    <span className="brand-copy">
      <span>Bharat</span>
      <span className="brand-stack">Stack</span>
    </span>
    <style jsx>{ `
      .brand-lockup{display:inline-flex;align-items:center;gap:8px;flex-wrap:nowrap;min-width:0}
      .brand-lockup img{height:46px;width:auto;border-radius:10px;flex-shrink:0;display:block;object-fit:contain}
      .brand-copy{display:flex;flex-direction:column;justify-content:center;line-height:1.15}
      .brand-copy>span{font-size:19px;font-weight:800;color:#1a3a2a;letter-spacing:-.3px}
      .brand-stack{display:flex;align-items:center;gap:2px}
    ` }</style>
  </span>
);

export default BrandLockup;
