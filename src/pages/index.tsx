/**
 * Stack Hub - Product Selector
 * URL: https://stack.wecare.digital/
 * Redirects users to the right product: CRM, Studio, or Sustainability
 */

import React from 'react';
import Head from 'next/head';

const LOGO_URL = 'https://app.wecare.digital/stream/media/m/wecaredigital.png';

const products = [
  {
    title: 'CRM',
    desc: 'WhatsApp Business API, multi-channel messaging, payments and AI automation',
    href: '/crm',
    icon: "data:image/svg+xml,%3csvg width='100%25' height='100%25' xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3e%3cg fill='none' stroke='%23333333' stroke-miterlimit='10' stroke-width='1.5' data-name='roll brush'%3e%3cpath d='M22.51 4.36c0 .87-1.38 1.63-3.58 2.16a30.8 30.8 0 0 1-7 .72 31 31 0 0 1-7-.72C2.79 6 1.41 5.23 1.41 4.36c0-1.59 4.73-2.87 10.59-2.87s10.51 1.28 10.51 2.87Z'/%3e%3cpath d='M22.51 4.36V12c0 .86-1.38 1.63-3.58 2.15a30.2 30.2 0 0 1-7 .72 30.3 30.3 0 0 1-7-.72C2.79 13.67 1.41 12.9 1.41 12V4.36'/%3e%3cpath d='M22.51 12v7.67c0 .86-1.38 1.63-3.58 2.16a30.8 30.8 0 0 1-7 .72 31 31 0 0 1-7-.72c-2.19-.53-3.57-1.3-3.57-2.16V12'/%3e%3c/g%3e%3c/svg%3e",
  },
  {
    title: 'Studio',
    desc: 'Visual workflow builder for WhatsApp automations, no code required',
    href: '/studio',
    icon: "data:image/svg+xml,%3csvg width='100%25' height='100%25' xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24'%3e%3cpath stroke='%23333333' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='m17 17 5-5-5-5M7 7l-5 5 5 5m7-14-4 18'/%3e%3c/svg%3e",
  },
  {
    title: 'Sustainability',
    desc: 'Track, reduce and offset your digital carbon footprint',
    href: '/sustainability',
    icon: "data:image/svg+xml,%3csvg width='100%25' height='100%25' xmlns='http://www.w3.org/2000/svg' data-name='Layer 1' viewBox='0 0 24 24'%3e%3cpath fill='none' stroke='%23333333' stroke-miterlimit='10' stroke-width='1.5' d='M16.64 19.09a5.43 5.43 0 0 1-4.16 2.08h-1a7.4 7.4 0 0 1-5.07-2.08C1 12 12 2 12 2l5 7.45a8.29 8.29 0 0 1-.36 9.64ZM11.97 9.3V23m-3.65-8.22 3.65 3.65m2.74-6.39-2.74 2.74'/%3e%3c/svg%3e",
  },
];

const HubPage: React.FC = () => (
  <>
    <Head>
      <title>WECARE.DIGITAL Stack</title>
      <meta name="description" content="WECARE.DIGITAL product suite — CRM, Studio, and Sustainability tools for enterprise customer engagement." />
      <meta property="og:title" content="WECARE.DIGITAL Stack" />
      <meta property="og:description" content="Enterprise tools for customer engagement, automation, and sustainability." />
      <meta property="og:image" content={LOGO_URL} />
      <meta property="og:url" content="https://stack.wecare.digital/" />
      <link rel="canonical" href="https://stack.wecare.digital/" />
      <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
    </Head>
    <div className="pg">
      <header className="hdr">
        <div className="hdr-in">
          <div className="logo">
            <img src={LOGO_URL} alt="WECARE.DIGITAL" className="logo-img" />
            <div className="logo-text">
              <span className="logo-main">Stack</span>
              <a href="https://www.wecare.digital" className="logo-sub" target="_blank" rel="noopener noreferrer">by WECARE.DIGITAL</a>
            </div>
          </div>
        </div>
      </header>

      <section className="hero">
        <h1>Pick your product</h1>
        <p>Everything you need to engage customers, automate workflows, and build sustainably.</p>
      </section>

      <section className="products">
        <div className="grid">
          {products.map((p, i) => (
            <a key={i} href={p.href} className="card">
              <div className="card-icon"><img src={p.icon} alt={p.title} /></div>
              <h3>{p.title}</h3>
              <p>{p.desc}</p>
              <span className="arrow">→</span>
            </a>
          ))}
        </div>
      </section>

      <footer className="ftr">
        <div className="ftr-in">
          <a href="https://www.wecare.digital/contact">Contact us</a>
        </div>
      </footer>

      <style jsx>{`
        .pg{min-height:100vh;background:#fff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1a1a1a;overflow-x:hidden}
        .hdr{position:fixed;top:0;left:0;right:0;z-index:100;background:rgba(255,255,255,.97);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)}
        .hdr-in{max-width:1200px;margin:0 auto;padding:20px 24px;display:flex;align-items:center}
        .logo{display:flex;align-items:center;gap:10px}
        .logo-img{width:72px;height:72px;border-radius:14px;flex-shrink:0;display:block;object-fit:contain;margin-top:-4px}
        .logo-text{display:flex;flex-direction:column;justify-content:center}
        .logo-main{font-size:38px;font-weight:800;color:#1a1a1a;letter-spacing:-0.5px;line-height:1.15}
        .logo-sub{font-size:19px;font-weight:600;color:#6b7280;line-height:1.15;margin-top:4px;text-decoration:none;transition:color .25s}
        .logo-sub:hover{color:#059669}
        .hero{padding:160px 24px 40px;max-width:700px;margin:0 auto;text-align:center}
        .hero h1{font-size:48px;font-weight:700;line-height:1.08;margin:0 0 16px;letter-spacing:-1.5px}
        .hero p{font-size:21px;color:#6b7280;line-height:1.6;margin:0}
        .products{padding:40px 24px 60px}
        .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;max-width:1100px;margin:0 auto}
        .card{background:#fff;border:2px solid #e5e7eb;border-radius:16px;padding:28px 24px;text-decoration:none;color:#1a1a1a;transition:all .25s;cursor:pointer;display:block;position:relative}
        .card:hover{border-color:#059669;transform:translateY(-2px);box-shadow:0 4px 12px rgba(16,185,129,0.2)}
        .card-icon{width:52px;height:52px;background:#fff;border:2px solid #e5e7eb;border-radius:12px;display:flex;align-items:center;justify-content:center;margin-bottom:20px;padding:10px}
        .card-icon img{width:100%;height:100%;object-fit:contain}
        .card h3{font-size:24px;font-weight:700;margin:0 0 8px}
        .card p{font-size:17px;color:#6b7280;margin:0;line-height:1.5}
        .arrow{position:absolute;bottom:24px;right:24px;font-size:20px;color:#059669;opacity:0;transition:all .25s}
        .card:hover .arrow{opacity:1}
        .ftr{padding:24px;padding-bottom:calc(24px + env(safe-area-inset-bottom))}
        .ftr-in{max-width:1200px;margin:0 auto;display:flex;justify-content:flex-start}
        .ftr a{font-size:17px;color:#6b7280;text-decoration:none;font-weight:500;transition:color .25s}
        .ftr a:hover{color:#059669}

        @media(max-width:767px){
          .hdr-in{padding:12px 16px}
          .logo-img{width:64px;height:64px;border-radius:12px}
          .logo-main{font-size:28px}
          .logo-sub{font-size:15px}
          .hero{padding:calc(110px + env(safe-area-inset-top)) 20px 32px}
          .hero h1{font-size:38px;letter-spacing:-0.5px}
          .hero p{font-size:20px}
          .products{padding:24px 20px 44px}
          .grid{grid-template-columns:1fr;gap:14px}
          .card{padding:22px 18px}
          .card h3{font-size:22px}
          .card p{font-size:18px}
          .arrow{opacity:1}
          .ftr{padding:28px 20px;padding-bottom:calc(28px + env(safe-area-inset-bottom))}
        }

        @media(max-width:480px){
          .logo-img{width:56px;height:56px;border-radius:11px}
          .logo-main{font-size:26px}
          .logo-sub{font-size:13px}
          .hero h1{font-size:32px}
          .hero p{font-size:18px}
        }
      `}</style>
    </div>
  </>
);

export default HubPage;