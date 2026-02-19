/**
 * Carbon Page - Public landing page
 * URL: https://base.wecare.digital/carbon
 */
import React, { useEffect, useState } from 'react';
import Head from 'next/head';

const LOGO_URL = 'https://app.wecare.digital/stream/media/m/wecare-digital.png';

const pillars = [
  { icon: '📉', title: 'Measure', desc: 'Automatic carbon footprint tracking for every WhatsApp message, SMS, email and API call your business sends' },
  { icon: '♻️', title: 'Reduce', desc: 'Smart batching, message deduplication and off-peak scheduling to minimize energy consumption' },
  { icon: '🌳', title: 'Offset', desc: 'Verified carbon credits from reforestation and renewable energy projects across India' },
  { icon: '📊', title: 'Report', desc: 'ESG-ready sustainability reports with per-campaign and per-channel carbon breakdowns' },
];

const stats = [
  { value: '0.2g', label: 'CO₂ per WhatsApp message' },
  { value: '4g', label: 'CO₂ per email with attachment' },
  { value: '50g', label: 'CO₂ per SMS (network overhead)' },
];

const CarbonPage: React.FC = () => {
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
        <title>Carbon | WECARE.DIGITAL</title>
        <meta name="description" content="Track, reduce and offset your digital carbon footprint. ESG-ready sustainability reporting for every message your business sends." />
        <meta property="og:title" content="Carbon | WECARE.DIGITAL" />
        <meta property="og:description" content="Track and offset your digital carbon footprint with every message." />
        <meta property="og:image" content={LOGO_URL} />
        <meta property="og:url" content="https://base.wecare.digital/carbon" />
        <link rel="canonical" href="https://base.wecare.digital/carbon" />
      </Head>
      <div className="cb-page">
        <header className="cb-hdr">
          <div className="cb-hdr-in">
            <a href="/" className="cb-logo">
              <img src={LOGO_URL} alt="WECARE.DIGITAL" className="cb-logo-img" />
              <div className="cb-logo-text">
                <span className="cb-logo-main">WECARE</span>
                <span className="cb-logo-sub">.DIGITAL</span>
              </div>
            </a>
          </div>
        </header>

        <section className={`cb-hero anim ${show('cb-hero') ? 'show' : ''}`} id="cb-hero">
          <div className="cb-badge">Carbon</div>
          <h1>Messaging that<br/>cares for the planet</h1>
          <p>Every message has a carbon cost. We help you measure it, reduce it, and offset what remains.</p>
        </section>

        <section className={`cb-stats anim ${show('cb-stats') ? 'show' : ''}`} id="cb-stats">
          <div className="cb-stats-grid">
            {stats.map((s, i) => (
              <div key={i} className="cb-stat">
                <span className="cb-stat-val">{s.value}</span>
                <span className="cb-stat-label">{s.label}</span>
              </div>
            ))}
          </div>
        </section>

        <section className={`cb-pillars anim ${show('cb-pill') ? 'show' : ''}`} id="cb-pill">
          <div className="cb-grid">
            {pillars.map((p, i) => (
              <div key={i} className="cb-card">
                <div className="cb-card-icon">{p.icon}</div>
                <h3>{p.title}</h3>
                <p>{p.desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section className={`cb-cta anim ${show('cb-cta') ? 'show' : ''}`} id="cb-cta">
          <h2>Go carbon-conscious today</h2>
          <p>Built into every Base CRM plan. No extra cost.</p>
          <a href="/access" className="cb-btn">Get Started</a>
        </section>

        <footer className="cb-ftr">
          <a href="/">← Back to Home</a>
          <a href="/nocode">NoCode →</a>
        </footer>

        <style jsx>{`
          .cb-page{min-height:100vh;background:#fff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1a1a1a;overflow-x:hidden}
          .cb-hdr{position:fixed;top:0;left:0;right:0;z-index:100;background:rgba(255,255,255,.97);backdrop-filter:blur(20px)}
          .cb-hdr-in{max-width:1100px;margin:0 auto;padding:16px 24px;display:flex;align-items:center}
          .cb-logo{display:flex;align-items:center;gap:3px;text-decoration:none}
          .cb-logo-img{width:56px;height:56px;border-radius:12px}
          .cb-logo-text{display:flex;flex-direction:column}
          .cb-logo-main{font-size:24px;font-weight:800;color:#1a1a1a;line-height:1.1}
          .cb-logo-sub{font-size:14px;font-weight:600;color:#6b7280;line-height:1}
          .anim{opacity:0;transform:translateY(30px);transition:all .7s cubic-bezier(.16,1,.3,1)}
          .anim.show{opacity:1;transform:translateY(0)}
          .cb-hero{padding:140px 24px 60px;max-width:700px;margin:0 auto;text-align:center}
          .cb-badge{display:inline-block;padding:6px 16px;background:#ecfdf5;color:#059669;border-radius:20px;font-size:14px;font-weight:600;margin-bottom:20px}
          .cb-hero h1{font-size:52px;font-weight:700;line-height:1.1;margin:0 0 20px;letter-spacing:-1.5px}
          .cb-hero p{font-size:20px;color:#6b7280;line-height:1.6;margin:0}
          .cb-stats{padding:0 24px 40px}
          .cb-stats-grid{display:flex;justify-content:center;gap:20px;max-width:800px;margin:0 auto;flex-wrap:wrap}
          .cb-stat{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:16px;padding:24px 28px;text-align:center;min-width:180px;flex:1}
          .cb-stat-val{display:block;font-size:32px;font-weight:800;color:#059669;letter-spacing:-0.5px}
          .cb-stat-label{display:block;font-size:14px;color:#6b7280;margin-top:6px}
          .cb-pillars{padding:40px 24px 60px}
          .cb-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:20px;max-width:900px;margin:0 auto}
          .cb-card{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:28px 24px;transition:all .25s}
          .cb-card:hover{border-color:#10b981;box-shadow:0 4px 16px rgba(16,185,129,.1);transform:translateY(-2px)}
          .cb-card-icon{font-size:32px;margin-bottom:14px}
          .cb-card h3{font-size:20px;font-weight:600;margin:0 0 8px;color:#1a1a1a}
          .cb-card p{font-size:15px;color:#6b7280;margin:0;line-height:1.6}
          .cb-cta{padding:60px 24px;text-align:center}
          .cb-cta h2{font-size:38px;font-weight:700;margin:0 0 12px;letter-spacing:-1px}
          .cb-cta p{font-size:18px;color:#6b7280;margin:0 0 24px}
          .cb-btn{display:inline-block;padding:14px 36px;background:#1a1a1a;color:#fff;border-radius:12px;text-decoration:none;font-size:16px;font-weight:600;transition:all .2s}
          .cb-btn:hover{background:#333}
          .cb-ftr{max-width:1100px;margin:0 auto;padding:24px;display:flex;justify-content:space-between}
          .cb-ftr a{font-size:15px;color:#6b7280;text-decoration:none;font-weight:500;transition:color .2s}
          .cb-ftr a:hover{color:#059669}
          @media(max-width:767px){
            .cb-hero{padding:120px 20px 44px}
            .cb-hero h1{font-size:38px}
            .cb-hero p{font-size:18px}
            .cb-stats-grid{flex-direction:column;gap:12px}
            .cb-stat{min-width:auto}
            .cb-grid{grid-template-columns:1fr;gap:14px}
            .cb-cta h2{font-size:30px}
          }
        `}</style>
      </div>
    </>
  );
};

export default CarbonPage;
