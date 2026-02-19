/**
 * Carbon Page - Public landing page
 * URL: https://base.wecare.digital/carbon
 */
import React, { useEffect, useState } from 'react';
import Head from 'next/head';

const LOGO_URL = 'https://app.wecare.digital/stream/media/m/wecare-digital.png';
const ICON = "data:image/svg+xml,%3csvg width='100%25' height='100%25' xmlns='http://www.w3.org/2000/svg' data-name='Layer 1' viewBox='0 0 24 24'%3e%3cpath fill='none' stroke='%23664FC2' stroke-miterlimit='10' stroke-width='1.5' d='M16.64 19.09a5.43 5.43 0 0 1-4.16 2.08h-1a7.4 7.4 0 0 1-5.07-2.08C1 12 12 2 12 2l5 7.45a8.29 8.29 0 0 1-.36 9.64ZM11.97 9.3V23m-3.65-8.22 3.65 3.65m2.74-6.39-2.74 2.74'/%3e%3c/svg%3e";

const pillars = [
  { title: 'Measure', desc: 'Automatic carbon footprint tracking for every WhatsApp message, SMS, email and API call your business sends' },
  { title: 'Reduce', desc: 'Smart batching, message deduplication and off-peak scheduling to minimize energy consumption' },
  { title: 'Offset', desc: 'Verified carbon credits from reforestation and renewable energy projects across India' },
  { title: 'Report', desc: 'ESG-ready sustainability reports with per-campaign and per-channel carbon breakdowns' },
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
      <div className="pg">
        <header className="hdr">
          <div className="hdr-in">
            <a href="/" className="logo">
              <img src={LOGO_URL} alt="WECARE.DIGITAL" className="logo-img" />
              <div className="logo-text">
                <span className="logo-main">WECARE</span>
                <span className="logo-sub">.DIGITAL</span>
              </div>
            </a>
          </div>
        </header>

        <section className={`hero anim ${show('hero') ? 'show' : ''}`} id="hero">
          <div className="badge-icon"><img src={ICON} alt="Carbon" /></div>
          <div className="badge">Carbon</div>
          <h1>Messaging that<br/>cares for the planet</h1>
          <p>Every message has a carbon cost. We help you measure it, reduce it, and offset what remains.</p>
        </section>

        <section className={`stats-section anim ${show('stats') ? 'show' : ''}`} id="stats">
          <div className="stats-grid">
            {stats.map((s, i) => (
              <div key={i} className="stat">
                <span>{s.value}</span>
                <small>{s.label}</small>
              </div>
            ))}
          </div>
        </section>

        <section className={`features anim ${show('feat') ? 'show' : ''}`} id="feat">
          <div className="grid">
            {pillars.map((p, i) => (
              <div key={i} className="card">
                <div className="card-icon"><img src={ICON} alt="" /></div>
                <h3>{p.title}</h3>
                <p>{p.desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section className={`cta anim ${show('cta') ? 'show' : ''}`} id="cta">
          <h2>Go carbon-conscious today</h2>
          <p>Built into every Base CRM plan. No extra cost.</p>
          <a href="/access" className="btn">Get Started</a>
        </section>

        <footer className="ftr">
          <div className="ftr-in">
            <a href="/">← Home</a>
            <a href="/nocode">NoCode →</a>
          </div>
        </footer>

        <style jsx>{`
          .pg{min-height:100vh;background:#fff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1a1a1a;overflow-x:hidden}
          .hdr{position:fixed;top:0;left:0;right:0;z-index:100;background:rgba(255,255,255,.97);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)}
          .hdr-in{max-width:1200px;margin:0 auto;padding:16px 24px;display:flex;align-items:center}
          .logo{display:flex;align-items:center;gap:3px;text-decoration:none}
          .logo-img{width:74px;height:74px;border-radius:14px}
          .logo-text{display:flex;flex-direction:column;justify-content:center}
          .logo-main{font-size:32px;font-weight:800;color:#1a1a1a;letter-spacing:-0.5px;line-height:1.1}
          .logo-sub{font-size:17px;font-weight:600;color:#6b7280;line-height:1;margin-top:3px}
          .anim{opacity:0;transform:translateY(30px);transition:all .7s cubic-bezier(.16,1,.3,1)}
          .anim.show{opacity:1;transform:translateY(0)}
          .hero{padding:140px 24px 60px;max-width:700px;margin:0 auto;text-align:center}
          .badge-icon{width:64px;height:64px;margin:0 auto 16px;background:#fff;border:2px solid #e5e7eb;border-radius:14px;display:flex;align-items:center;justify-content:center;padding:14px}
          .badge-icon img{width:100%;height:100%;object-fit:contain}
          .badge{display:inline-block;padding:6px 16px;background:#f3f0ff;color:#664FC2;border-radius:20px;font-size:14px;font-weight:600;margin-bottom:20px}
          .hero h1{font-size:48px;font-weight:700;line-height:1.08;margin:0 0 24px;letter-spacing:-1.5px}
          .hero p{font-size:21px;color:#6b7280;line-height:1.6;margin:0}
          .stats-section{padding:0 24px 40px}
          .stats-grid{display:flex;justify-content:center;gap:12px;max-width:900px;margin:0 auto;flex-wrap:wrap}
          .stat{background:#fff;border:2px solid #e5e7eb;border-radius:16px;padding:18px 22px;min-width:180px;flex:1;text-align:center;transition:all .25s;cursor:default}
          .stat:hover{border-color:#10b981;color:#059669;transform:translateY(-2px);box-shadow:0 4px 12px rgba(16,185,129,0.2)}
          .stat span{display:block;font-size:26px;font-weight:800;color:#1a1a1a;letter-spacing:-0.5px}
          .stat small{font-size:16px;color:#6b7280;margin-top:4px;display:block;font-weight:500}
          .features{padding:40px 24px 60px}
          .grid{display:grid;grid-template-columns:repeat(2,1fr);gap:20px;max-width:1100px;margin:0 auto}
          .card{background:#fff;border:2px solid #e5e7eb;border-radius:16px;padding:28px 24px;transition:all .25s;cursor:default}
          .card:hover{border-color:#10b981;color:#059669;transform:translateY(-2px);box-shadow:0 4px 12px rgba(16,185,129,0.2)}
          .card-icon{width:52px;height:52px;background:#fff;border:2px solid #e5e7eb;border-radius:12px;display:flex;align-items:center;justify-content:center;margin-bottom:20px;padding:10px}
          .card-icon img{width:100%;height:100%;object-fit:contain}
          .card h3{font-size:20px;font-weight:600;margin:0 0 8px;color:#1a1a1a}
          .card p{font-size:21px;color:#6b7280;margin:0;line-height:1.5}
          .cta{padding:60px 24px;text-align:center}
          .cta h2{font-size:42px;font-weight:700;margin:0 0 12px;letter-spacing:-1px;color:#1a1a1a;line-height:1.15}
          .cta p{font-size:21px;color:#6b7280;margin:0 0 24px}
          .btn{display:inline-block;padding:14px 36px;background:#1a1a1a;color:#fff;border-radius:13px;text-decoration:none;font-size:16px;font-weight:600;transition:all .2s}
          .btn:hover{background:#333}
          .ftr{padding:24px;padding-bottom:calc(24px + env(safe-area-inset-bottom));background:#fff}
          .ftr-in{max-width:1200px;margin:0 auto;display:flex;justify-content:space-between}
          .ftr a{font-size:21px;color:#6b7280;text-decoration:none;font-weight:500;transition:all .25s}
          .ftr a:hover{color:#10b981}

          @media(max-width:1024px){
            .hdr-in{padding:14px 20px}
            .logo-img{width:66px;height:66px}
            .logo-main{font-size:28px}
            .logo-sub{font-size:15px}
            .hero{padding:110px 20px 50px}
            .hero h1{font-size:38px;letter-spacing:-1px}
            .hero p{font-size:17px}
            .stats-grid{gap:10px}
            .stat{padding:16px 20px;min-width:140px}
            .stat span{font-size:22px}
            .stat small{font-size:12px}
            .grid{gap:16px}
            .card{padding:24px 20px}
            .card h3{font-size:17px}
            .card p{font-size:14px}
            .cta{padding:50px 20px}
            .cta h2{font-size:34px}
            .cta p{font-size:16px}
          }

          @media(max-width:767px){
            .hdr-in{padding:12px 16px}
            .logo-img{width:66px;height:66px;border-radius:14px}
            .logo-main{font-size:28px}
            .logo-sub{font-size:16px}
            .hero{padding:calc(90px + env(safe-area-inset-top)) 20px 44px}
            .badge-icon{width:56px;height:56px;padding:12px}
            .hero h1{font-size:42px;letter-spacing:-0.5px;line-height:1.12}
            .hero p{font-size:24px;line-height:1.6}
            .stats-section{padding:0 20px 30px}
            .stats-grid{flex-direction:column;gap:12px}
            .stat{min-width:auto;padding:20px 24px;display:flex;align-items:center;gap:12px;text-align:left;border-radius:14px}
            .stat span{font-size:28px;font-weight:800;min-width:70px}
            .stat small{font-size:20px;line-height:1.3;margin:0}
            .features{padding:30px 20px 44px}
            .grid{grid-template-columns:repeat(2,1fr);gap:14px}
            .card{padding:22px 18px;border-radius:14px}
            .card-icon{width:50px;height:50px;margin-bottom:16px;border-radius:12px;padding:10px}
            .card h3{font-size:20px;margin-bottom:8px}
            .card p{font-size:20px;line-height:1.5}
            .cta{padding:44px 20px}
            .cta h2{font-size:34px;line-height:1.2}
            .cta p{font-size:24px}
            .ftr a{font-size:24px}
          }

          @media(max-width:480px){
            .logo-img{width:58px;height:58px;border-radius:12px}
            .logo-main{font-size:26px}
            .logo-sub{font-size:14px}
            .hero h1{font-size:38px;line-height:1.15}
            .hero p{font-size:22px}
            .stat span{font-size:26px;min-width:65px}
            .stat small{font-size:18px}
            .grid{gap:12px}
            .card{padding:20px 16px}
            .card h3{font-size:18px}
            .card p{font-size:18px}
            .cta h2{font-size:30px}
            .cta p{font-size:20px}
            .ftr a{font-size:20px}
          }

          @media(max-width:374px){
            .hero h1{font-size:32px}
            .hero p{font-size:20px}
            .stat span{font-size:22px}
            .stat small{font-size:16px}
            .card h3{font-size:16px}
            .card p{font-size:16px}
            .cta h2{font-size:26px}
            .cta p{font-size:18px}
          }
        `}</style>
      </div>
    </>
  );
};

export default CarbonPage;
