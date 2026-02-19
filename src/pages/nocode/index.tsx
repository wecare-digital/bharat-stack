/**
 * NoCode Page - Public landing page
 * URL: https://base.wecare.digital/nocode
 */
import React, { useEffect, useState } from 'react';
import Head from 'next/head';

const LOGO_URL = 'https://app.wecare.digital/stream/media/m/wecare-digital.png';

const features = [
  { icon: '🔗', title: 'Visual Workflow Builder', desc: 'Drag-and-drop automations for WhatsApp, SMS, Email and Voice — no code required' },
  { icon: '🤖', title: 'AI-Powered Triggers', desc: 'Set up intelligent triggers based on customer behavior, keywords and payment events' },
  { icon: '📊', title: 'Live Dashboards', desc: 'Real-time analytics and reporting that update as your workflows run' },
  { icon: '🔌', title: 'One-Click Integrations', desc: 'Connect Razorpay, Wix, Google Sheets, Shopify and 100+ apps instantly' },
  { icon: '📱', title: 'Template Studio', desc: 'Design WhatsApp templates with rich media, buttons and carousels visually' },
  { icon: '⚡', title: 'Instant Deploy', desc: 'Go live in seconds — no build steps, no servers, no DevOps' },
];

const NoCodePage: React.FC = () => {
  const [visible, setVisible] = useState<Set<string>>(new Set());
  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => entries.forEach((e) => { if (e.isIntersecting) setVisible((p) => new Set([...p, e.target.id])); }),
      { threshold: 0.1 }
    );
    document.querySelectorAll('.anim').forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, []);
  const show = (id: string) => visible.has(id);

  return (
    <>
      <Head>
        <title>NoCode Platform | WECARE.DIGITAL</title>
        <meta name="description" content="Build powerful WhatsApp automations, workflows and integrations without writing code. Visual builder for multi-channel customer engagement." />
        <meta property="og:title" content="NoCode Platform | WECARE.DIGITAL" />
        <meta property="og:description" content="Build powerful WhatsApp automations without writing code." />
        <meta property="og:image" content={LOGO_URL} />
        <meta property="og:url" content="https://base.wecare.digital/nocode" />
        <link rel="canonical" href="https://base.wecare.digital/nocode" />
      </Head>
      <div className="nc-page">
        <header className="nc-hdr">
          <div className="nc-hdr-in">
            <a href="/" className="nc-logo">
              <img src={LOGO_URL} alt="WECARE.DIGITAL" className="nc-logo-img" />
              <div className="nc-logo-text">
                <span className="nc-logo-main">WECARE</span>
                <span className="nc-logo-sub">.DIGITAL</span>
              </div>
            </a>
          </div>
        </header>

        <section className={`nc-hero anim ${show('nc-hero') ? 'show' : ''}`} id="nc-hero">
          <div className="nc-badge">NoCode</div>
          <h1>Build without<br/>writing code</h1>
          <p>Create powerful WhatsApp automations, payment flows and multi-channel campaigns with our visual builder. No developers needed.</p>
        </section>

        <section className={`nc-features anim ${show('nc-feat') ? 'show' : ''}`} id="nc-feat">
          <div className="nc-grid">
            {features.map((f, i) => (
              <div key={i} className="nc-card">
                <div className="nc-card-icon">{f.icon}</div>
                <h3>{f.title}</h3>
                <p>{f.desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section className={`nc-cta anim ${show('nc-cta') ? 'show' : ''}`} id="nc-cta">
          <h2>Start building today</h2>
          <p>No credit card required. Free tier available.</p>
          <a href="/access" className="nc-btn">Get Started</a>
        </section>

        <footer className="nc-ftr">
          <a href="/">← Back to Home</a>
          <a href="/carbon">Carbon →</a>
        </footer>

        <style jsx>{`
          .nc-page{min-height:100vh;background:#fff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1a1a1a;overflow-x:hidden}
          .nc-hdr{position:fixed;top:0;left:0;right:0;z-index:100;background:rgba(255,255,255,.97);backdrop-filter:blur(20px)}
          .nc-hdr-in{max-width:1100px;margin:0 auto;padding:16px 24px;display:flex;align-items:center}
          .nc-logo{display:flex;align-items:center;gap:3px;text-decoration:none}
          .nc-logo-img{width:56px;height:56px;border-radius:12px}
          .nc-logo-text{display:flex;flex-direction:column}
          .nc-logo-main{font-size:24px;font-weight:800;color:#1a1a1a;line-height:1.1}
          .nc-logo-sub{font-size:14px;font-weight:600;color:#6b7280;line-height:1}
          .anim{opacity:0;transform:translateY(30px);transition:all .7s cubic-bezier(.16,1,.3,1)}
          .anim.show{opacity:1;transform:translateY(0)}
          .nc-hero{padding:140px 24px 60px;max-width:700px;margin:0 auto;text-align:center}
          .nc-badge{display:inline-block;padding:6px 16px;background:#ecfdf5;color:#059669;border-radius:20px;font-size:14px;font-weight:600;margin-bottom:20px}
          .nc-hero h1{font-size:52px;font-weight:700;line-height:1.1;margin:0 0 20px;letter-spacing:-1.5px}
          .nc-hero p{font-size:20px;color:#6b7280;line-height:1.6;margin:0}
          .nc-features{padding:40px 24px 60px}
          .nc-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;max-width:1100px;margin:0 auto}
          .nc-card{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:28px 24px;transition:all .25s}
          .nc-card:hover{border-color:#10b981;box-shadow:0 4px 16px rgba(16,185,129,.1);transform:translateY(-2px)}
          .nc-card-icon{font-size:32px;margin-bottom:14px}
          .nc-card h3{font-size:18px;font-weight:600;margin:0 0 8px;color:#1a1a1a}
          .nc-card p{font-size:15px;color:#6b7280;margin:0;line-height:1.6}
          .nc-cta{padding:60px 24px;text-align:center}
          .nc-cta h2{font-size:38px;font-weight:700;margin:0 0 12px;letter-spacing:-1px}
          .nc-cta p{font-size:18px;color:#6b7280;margin:0 0 24px}
          .nc-btn{display:inline-block;padding:14px 36px;background:#1a1a1a;color:#fff;border-radius:12px;text-decoration:none;font-size:16px;font-weight:600;transition:all .2s}
          .nc-btn:hover{background:#333}
          .nc-ftr{max-width:1100px;margin:0 auto;padding:24px;display:flex;justify-content:space-between}
          .nc-ftr a{font-size:15px;color:#6b7280;text-decoration:none;font-weight:500;transition:color .2s}
          .nc-ftr a:hover{color:#059669}
          @media(max-width:767px){
            .nc-hero{padding:120px 20px 44px}
            .nc-hero h1{font-size:38px}
            .nc-hero p{font-size:18px}
            .nc-grid{grid-template-columns:1fr;gap:14px}
            .nc-cta h2{font-size:30px}
          }
        `}</style>
      </div>
    </>
  );
};

export default NoCodePage;
