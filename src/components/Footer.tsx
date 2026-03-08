import React from 'react';

const Footer: React.FC = () => (
  <footer className="ftr">
    <div className="ftr-in">
      <a href="https://www.wecare.digital/contact">Contact us</a>
    </div>
    <style jsx>{`
      .ftr{padding:24px;padding-bottom:calc(24px + env(safe-area-inset-bottom));background:#fff}
      .ftr-in{max-width:1300px;margin:0 auto;display:flex;justify-content:flex-start}
      .ftr a{font-size:21px;color:#6b7280;text-decoration:none;font-weight:500;transition:all .25s}
      .ftr a:hover{color:#059669}
      @media(max-width:767px){
        .ftr{padding:28px 20px;padding-bottom:calc(28px + env(safe-area-inset-bottom))}
        .ftr a{font-size:24px}
      }
      @media(max-width:480px){
        .ftr a{font-size:22px}
      }
      @media(max-width:360px){
        .ftr a{font-size:19px}
      }
    `}</style>
  </footer>
);

export default Footer;
