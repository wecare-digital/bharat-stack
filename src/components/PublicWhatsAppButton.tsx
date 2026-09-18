import React from 'react';

const WHATSAPP_URL = 'https://wa.me/919903300044?text=Hi%20WECARE.DIGITAL';

const PublicWhatsAppButton: React.FC = () => (
  <a
    className="public-wa"
    href={ WHATSAPP_URL }
    target="_blank"
    rel="noopener noreferrer"
    aria-label="Chat with WECARE.DIGITAL on WhatsApp"
  >
    <svg viewBox="0 0 32 32" aria-hidden="true">
      <path d="M16 4.3c-6.5 0-11.7 5-11.7 11.2 0 2 .6 3.9 1.6 5.5L4 27.7l6.9-1.8c1.6.8 3.3 1.2 5.1 1.2 6.5 0 11.7-5 11.7-11.2S22.5 4.3 16 4.3Z" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M11.2 10.7c.4-.7.7-.8 1.1-.8h.5c.3 0 .5.1.7.5l1.2 2.7c.1.3.1.6-.1.9l-.9 1.1c-.2.2-.2.5-.1.8.9 1.8 2.4 3.2 4.2 4.1.3.1.6.1.8-.1l1.1-.9c.3-.2.6-.2.9-.1l2.6 1.2c.4.2.5.4.5.7 0 1.1-.4 2-1.2 2.7-.7.6-1.7.8-2.7.6-2.5-.6-5-2-7.1-4.1-2.1-2.1-3.5-4.6-4.1-7.1-.2-1 .1-2 .7-2.7.6-.7 1.2-1 1.9-1.1" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
    <style jsx>{`
      .public-wa{position:fixed;right:16px;bottom:calc(18px + env(safe-area-inset-bottom));z-index:899;width:54px;height:54px;border-radius:50%;display:grid;place-items:center;background:#25d366;color:#fff;text-decoration:none;box-shadow:0 8px 22px rgba(7,94,84,.28);transition:transform .2s,box-shadow .2s,background .2s}
      .public-wa:hover{background:#20bd5a;transform:translateY(-2px);box-shadow:0 10px 26px rgba(7,94,84,.34)}
      .public-wa:focus-visible{outline:3px solid rgba(37,211,102,.32);outline-offset:3px}
      .public-wa svg{width:30px;height:30px}
      @media(max-width:600px){.public-wa{right:12px;width:52px;height:52px}}
      @media print{.public-wa{display:none}}
    `}</style>
  </a>
);

export default PublicWhatsAppButton;
