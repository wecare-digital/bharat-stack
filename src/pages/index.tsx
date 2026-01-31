/**
 * Home Page - WECARE.DIGITAL Landing
 * WhatsApp Business API Platform
 */

import React, { useEffect, useState } from 'react';
import Head from 'next/head';

const HomePage: React.FC = () => {
  const [visible, setVisible] = useState<Set<string>>(new Set());
  const [activeCode, setActiveCode] = useState(0);
  
  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => entries.forEach((e) => {
        if (e.isIntersecting) setVisible((p) => new Set([...p, e.target.id]));
      }),
      { threshold: 0.1 }
    );
    document.querySelectorAll('.anim').forEach((el) => obs.observe(el));
    return () => obs.disconnect();
  }, []);

  const show = (id: string) => visible.has(id);

  const useCases = ['Promotional', 'Transactional', 'Appointments', 'OTPs', 'Orders', 'Surveys'];

  const codeExamples = [
    { lang: 'Python', code: "import requests\n\nresponse = requests.post(\n    \"https://api.wecare.digital/v1/messages\",\n    headers={\"Authorization\": \"Bearer API_KEY\"},\n    json={\"to\": \"+919330994400\", \"type\": \"template\"}\n)" },
    { lang: 'JavaScript', code: "const response = await fetch(\n    \"https://api.wecare.digital/v1/messages\",\n    {\n        method: \"POST\",\n        headers: {\"Authorization\": \"Bearer API_KEY\"},\n        body: JSON.stringify({to: \"+919330994400\"})\n    }\n);" },
    { lang: 'cURL', code: "curl -X POST \\\n    \"https://api.wecare.digital/v1/messages\" \\\n    -H \"Authorization: Bearer API_KEY\" \\\n    -d '{\"to\": \"+919330994400\"}'" },
  ];


  return (
    <>
      <Head>
        <title>Base CRM by WECARE.DIGITAL - WhatsApp Business API Platform</title>
        <meta name="description" content="Connect with 2B+ users on WhatsApp. Multi-channel messaging CRM platform." />
      </Head>
      <div className="page">
        <header className="hdr">
          <div className="hdr-in">
            <div className="logo">
              <img src="https://auth.wecare.digital/stream/media/m/wecare-digital.png" alt="Base CRM" className="logo-img" />
              <div className="logo-text"><span className="logo-main">Base CRM</span><span className="logo-sub">by WECARE.DIGITAL</span></div>
            </div>
          </div>
        </header>

        <section className={`hero anim ${show('hero') ? 'show' : ''}`} id="hero">
          <div className="hero-content">
            <div className="hero-left">
              <h1>Reach more customers wherever they are, whatever they're on</h1>
              <p>Engage them on every channel, in every scenario – from our platform or your stack.</p>
              <div className="hero-stats">
                <div className="stat"><span>B+</span><small>Users reachable</small></div>
                <div className="stat"><span>Fast</span><small>Onboarding</small></div>
                <div className="stat"><span>Secure</span><small>Trusted channel</small></div>
              </div>
            </div>
            <div className="hero-right">
              <div className="mockup-wrapper">
                <div className="phone">
                  <div className="phone-header">
                    <span className="back-arrow"></span>
                    <div className="avatar">W</div>
                    <div className="contact-info">
                      <span className="contact-name">WECARE.DIGITAL</span>
                      <span className="contact-status">online</span>
                    </div>
                    <div className="verified-badge"></div>
                  </div>
                  <div className="chat-area">
                    <div className="msg sent"><p>Hi! Your order #WDSR87A6G has been shipped </p><span className="msg-time">10:30</span></div>
                    <div className="msg received"><p>When will it arrive?</p><span className="msg-time">10:31</span></div>
                    <div className="msg sent left-msg"><p>Tomorrow by 6 PM</p><span className="msg-time">10:31</span></div>
                    <div className="msg sent left-msg"><p>Track here: wecare.digital/track</p><span className="msg-time">10:32</span></div>
                    <div className="typing-indicator"><span></span><span></span><span></span></div>
                  </div>
                </div>
                <div className="code-box">
                  <div className="code-header">
                    <div className="dots"><span className="dot-red"></span><span className="dot-yellow"></span><span className="dot-green"></span></div>
                    <span className="file-name">send_message.py</span>
                  </div>
                  <pre className="code-body">{`response = requests.post(
  "api.wecare.digital/v1/send",
  json={
    "to": "+919330994400",
    "type": "text",
    "message": "Your OTP: 847291"
  },
  headers={"Authorization": api_key}
)`}</pre>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className={`touchpoint anim ${show('touchpoint') ? 'show' : ''}`} id="touchpoint">
          <div className="section-header">
            <h2>Every touchpoint, One seamless experience</h2>
            <p>Engage, support, and convert customers across their entire journey — from first contact to lasting loyalty</p>
          </div>
          <div className="usecase-pills">
            {useCases.map((title, i) => (
              <button key={i} className="pill">{title}</button>
            ))}
          </div>
        </section>

        <section className={`api anim ${show('api') ? 'show' : ''}`} id="api">
          <div className="api-grid">
            <div className="api-info">
              <h2>Built for the AI era.</h2>
              <p className="api-desc">The all-in-one platform for enterprise brands to acquire, convert, and retain customers across every channel—powered by AI that truly understands your business.</p>
              
            </div>
            <div className="api-demo">
              <div className="code-tabs">
                {codeExamples.map((c, i) => (
                  <button key={i} className={`tab ${activeCode === i ? 'active' : ''}`} onClick={() => setActiveCode(i)}>{c.lang}</button>
                ))}
              </div>
              <pre className="code-block">{codeExamples[activeCode].code}</pre>
            </div>
          </div>
        </section>


        <footer className="ftr">
          <div className="ftr-in">
            <a href="https://www.wecare.digital/contact" className="ftr-contact">Contact us</a>
            </div>
        </footer>
        <style jsx>{`
          .page{min-height:100vh;background:#fff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1a1a1a}
          .hdr{position:fixed;top:0;left:0;right:0;z-index:100;background:rgba(255,255,255,.97);backdrop-filter:blur(20px)}
          .hdr-in{max-width:1200px;margin:0 auto;padding:16px 24px;display:flex;align-items:center}
          .logo{display:flex;align-items:center;gap:7px}.logo-text{display:flex;flex-direction:column;justify-content:center;height:52px;text-align:left}.logo-main{font-size:24px;font-weight:800;color:#1a1a1a;letter-spacing:-0.3px;line-height:1}.logo-sub{font-size:13px;font-weight:600;color:#6b7280;line-height:1;margin-top:4px}
          .logo-img{width:52px;height:52px;border-radius:10px}
          .anim{opacity:0;transform:translateY(40px);transition:all .8s cubic-bezier(.16,1,.3,1)}
          .anim.show{opacity:1;transform:translateY(0)}
          .hero{padding:140px 24px 80px;max-width:1300px;margin:0 auto}
          .hero-content{display:grid;grid-template-columns:1fr 1.5fr;gap:40px;align-items:center}
          .hero-left h1{font-size:46px;font-weight:700;line-height:1.1;margin:0 0 20px;letter-spacing:-2px}
          .hero-left p{font-size:20px;color:#6b7280;line-height:1.5;margin:0 0 30px;max-width:420px}
          .hero-stats{display:flex;gap:16px}
          .stat{background:#f8faf9;border:1px solid #eaeaea;border-radius:16px;padding:16px 20px}
          .stat span{display:block;font-size:24px;font-weight:700}
          .stat small{font-size:14px;color:#6b7280}
          .hero-right{display:flex;justify-content:center}
          .mockup-wrapper{position:relative;width:620px;height:560px;background:#e8f5f0;border-radius:32px;padding:40px}
          .phone{position:absolute;left:40px;top:30px;width:340px;background:#d4ddd4;border-radius:24px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.08);z-index:1}
          .phone-header{background:#075e54;padding:14px 16px;display:flex;align-items:center;gap:12px}
          .back-arrow{color:#fff;font-size:22px}
          .avatar{width:44px;height:44px;background:#25d366;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:18px}
          .contact-info{flex:1;display:flex;flex-direction:column}
          .contact-name{color:#fff;font-size:17px;font-weight:600}
          .contact-status{color:rgba(255,255,255,.75);font-size:12px}
          .verified-badge{width:24px;height:24px;background:#25d366;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-size:12px}
          .chat-area{background:#e8efe5;padding:18px 14px;min-height:400px;display:flex;flex-direction:column;gap:10px}
          .msg{max-width:75%;padding:10px 14px;border-radius:10px;font-size:15px;line-height:1.5;color:#000}
          .msg.received{background:#fff;align-self:flex-start;border-top-left-radius:4px}
          .msg.sent{background:#d9fdd3;align-self:flex-end;border-top-right-radius:4px}
          .msg.sent.left-msg{max-width:55%;align-self:flex-start !important;border-top-left-radius:4px;border-top-right-radius:10px}
          .msg p{margin:0;color:#000}
          .msg-time{font-size:10px;color:#667781;display:block;text-align:right;margin-top:4px}
          .typing-indicator{background:#fff;padding:12px 16px;border-radius:10px;align-self:flex-start;display:flex;gap:4px}
          .typing-indicator span{width:8px;height:8px;background:#90949c;border-radius:50%;animation:bounce 1.4s infinite}
          .typing-indicator span:nth-child(2){animation-delay:.2s}
          .typing-indicator span:nth-child(3){animation-delay:.4s}
          @keyframes bounce{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-3px)}}
          .code-box{position:absolute;right:20px;bottom:40px;width:380px;background:#3d4654;border-radius:16px;overflow:hidden;box-shadow:0 25px 70px rgba(0,0,0,.18);z-index:2}
          .code-header{display:flex;align-items:center;padding:12px 16px;background:#2d3440}
          .dots{display:flex;gap:6px}
          .dot-red,.dot-yellow,.dot-green{width:12px;height:12px;border-radius:50%}
          .dot-red{background:#ff5f57}
          .dot-yellow{background:#febc2e}
          .dot-green{background:#28c840}
          .file-name{margin-left:auto;font-size:13px;color:#9ca3af}
          .code-body{margin:0;padding:18px;font-family:'SF Mono',Monaco,monospace;font-size:13px;line-height:1.6;color:#e5e7eb}
          .logos{padding:50px 24px;background:#fff;text-align:center}
          .logos-title{font-size:15px;color:#6b7280;margin:0 0 30px;font-weight:500}
          .logos-row{display:flex;justify-content:center;gap:40px;flex-wrap:wrap;max-width:900px;margin:0 auto}
          .logo-item{font-size:16px;font-weight:600;color:#9ca3af;padding:12px 20px}
          .section-header{text-align:center;max-width:800px;margin:0 auto 40px}
          .section-header h2{font-size:40px;font-weight:700;line-height:1.3;margin:0 0 40px;color:#1a1a1a}
          .section-header p{font-size:20px;color:#6b7280;line-height:1.6;margin:0}
          .touchpoint{padding:100px 24px;background:#fff}
          .usecase-pills{display:flex;justify-content:center;gap:12px;flex-wrap:wrap}
          .pill{padding:14px 28px;border:2px solid #e5e7eb;background:#fff;border-radius:50px;font-size:15px;font-weight:600;cursor:default;transition:all .2s;color:#4b5563}
          .pill:hover{border-color:#25d366;color:#25d366}
          .api{padding:100px 24px;background:#fff}
          .api-grid{display:grid;grid-template-columns:1fr 1fr;gap:60px;max-width:1200px;margin:0 auto;align-items:center}
          .api-info h2{font-size:36px;font-weight:700;color:#1a1a1a;margin:0 0 20px;line-height:1.2}
          .api-desc{font-size:20px;color:#6b7280;line-height:1.7;margin:0 0 30px;max-width:480px}
          .api-features{list-style:none;padding:0;margin:0}
          .api-features li{display:flex;align-items:center;gap:12px;font-size:16px;color:#4b5563;padding:10px 0}
          .check{color:#25d366;font-weight:700}
          .api-demo{background:#1e293b;border-radius:16px;overflow:hidden}
          .code-tabs{display:flex;gap:4px;padding:16px;background:#0f172a;border-bottom:1px solid #334155}
          .tab{padding:10px 20px;border:none;border-radius:8px;font-size:14px;font-weight:600;color:#9ca3af;background:transparent;cursor:pointer;transition:all .2s}
          .tab:hover{color:#fff}
          .tab.active{background:#25d366;color:#fff}
          .code-block{margin:0;padding:24px;font-family:'SF Mono',Monaco,Consolas,monospace;font-size:13px;line-height:1.7;color:#e5e7eb;overflow-x:auto;white-space:pre}
          .integrations{padding:100px 24px;background:#f8f9fa}
          .integrations-grid{display:grid;grid-template-columns:repeat(6,1fr);gap:16px;max-width:900px;margin:0 auto}
          .integration-card{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:24px;text-align:center;font-size:15px;font-weight:600;color:#4b5563;transition:all .2s}
          .integration-card:hover{border-color:#25d366;transform:translateY(-2px)}
          .stories{padding:100px 24px;background:#fff}
          .stories-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;max-width:1100px;margin:0 auto}
          .story-card{background:#f8f9fa;border-radius:20px;padding:36px;transition:all .3s}
          .story-card:hover{transform:translateY(-4px);box-shadow:0 16px 48px rgba(0,0,0,.08)}
          .story-brand{font-size:13px;font-weight:600;color:#25d366;text-transform:uppercase;letter-spacing:1px;margin-bottom:20px}
          .story-stat{margin-bottom:20px}
          .stat-num{display:block;font-size:48px;font-weight:800;color:#1a1a1a;line-height:1}
          .stat-label{font-size:16px;color:#6b7280}
          .story-desc{font-size:16px;font-weight:600;color:#1a1a1a;margin:0 0 8px}
          .story-extra{font-size:14px;color:#9ca3af;margin:0}
          .cta{padding:80px 24px;background:#1a1a2e}
          .cta-content{text-align:center;max-width:700px;margin:0 auto}
          .cta-content h2{font-size:36px;font-weight:700;color:#fff;margin:0 0 16px}
          .cta-content p{font-size:18px;color:#9ca3af;margin:0}
          .channels{padding:80px 24px;background:#fff}
          .channels-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:20px;max-width:1000px;margin:0 auto}
          .channel-card{background:#f8f9fa;border-radius:16px;padding:32px 24px;text-align:center;transition:all .3s}
          .channel-card:hover{transform:translateY(-4px);box-shadow:0 12px 40px rgba(0,0,0,.08)}
          .channel-icon{font-size:40px;margin-bottom:16px}
          .channel-card h3{font-size:17px;font-weight:700;margin:0 0 8px;color:#1a1a1a}
          .channel-card p{font-size:14px;color:#6b7280;margin:0}
          .ftr{padding:24px;padding-bottom:calc(24px + env(safe-area-inset-bottom));background:#fff}
          .ftr-in{max-width:1200px;margin:0 auto;display:flex;justify-content:flex-start;align-items:center}
          .ftr-contact{font-size:16px;color:#9ca3af;text-decoration:none}
          
          @media(max-width:1024px){.hero-content,.api-grid{grid-template-columns:1fr;text-align:center}.hero-left p{margin:0 auto 30px}.hero-stats{justify-content:center}.mockup-wrapper{width:100%;max-width:500px;height:auto;min-height:520px;margin:0 auto}.phone{position:relative;left:auto;top:auto;width:100%;max-width:300px;margin:0 auto 20px}.code-box{position:relative;right:auto;bottom:auto;width:100%;max-width:340px;margin:0 auto}.stories-grid,.channels-grid{grid-template-columns:repeat(2,1fr)}.integrations-grid{grid-template-columns:repeat(3,1fr)}}
          
          
        @media(max-width:767px){.hdr-in{padding:12px 16px}.logo{gap:5px}.logo-img{width:40px;height:40px}.logo-text{height:40px}.logo-main{font-size:18px}.logo-sub{font-size:10px;margin-top:2px}.hero{padding:calc(90px + env(safe-area-inset-top)) 16px 50px}.hero-content{display:flex;flex-direction:column;gap:28px}.hero-right{order:-1}.hero-left{text-align:left;order:1}.hero-left h1{font-size:26px;letter-spacing:-0.5px;margin:0 0 14px;line-height:1.2}.hero-left p{font-size:15px;line-height:1.6;margin:0 0 20px;color:#6b7280}.hero-stats{display:flex;gap:8px;justify-content:space-between}.stat{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:12px 8px;flex:1;min-width:0;text-align:center}.stat span{font-size:18px;font-weight:700}.stat small{font-size:10px;margin-top:2px}.mockup-wrapper{display:flex;flex-direction:column;gap:12px;width:100%;height:auto;min-height:auto;padding:14px;background:#e8f5f0;border-radius:16px}.phone{position:relative;left:auto;top:auto;width:100%;max-width:100%;margin:0;border-radius:14px}.chat-area{min-height:180px;padding:10px}.msg{font-size:13px;padding:8px 10px}.code-box{position:relative;right:auto;bottom:auto;width:100%;max-width:100%;margin:0;border-radius:10px}.code-header{padding:8px 12px}.code-body{font-size:10px;padding:12px;line-height:1.5}.section-header{text-align:center;padding:0;margin-bottom:28px}.section-header h2{font-size:24px;margin-bottom:24px}.section-header p{font-size:14px}.touchpoint{padding:40px 16px}.usecase-pills{justify-content:flex-start;gap:8px;overflow-x:auto;-webkit-overflow-scrolling:touch;flex-wrap:nowrap;padding-bottom:8px}.pill{padding:10px 16px;font-size:12px;flex-shrink:0}.api{padding:40px 16px}.api-grid{gap:20px}.api-info{text-align:left}.api-info h2{font-size:24px;margin-bottom:12px}.api-desc{font-size:14px}.api-demo{border-radius:12px}.code-tabs{display:flex;justify-content:flex-start;gap:6px;padding:10px 12px;overflow-x:auto;-webkit-overflow-scrolling:touch;flex-wrap:nowrap}.tab{padding:8px 14px;font-size:12px;white-space:nowrap;flex-shrink:0}.code-block{font-size:10px;padding:14px;min-height:140px;overflow-x:auto;-webkit-overflow-scrolling:touch}.ftr{padding:16px;padding-bottom:calc(16px + env(safe-area-inset-bottom));background:#fff}.ftr-contact{font-size:13px}}`}</style>
      </div>
    </>
  );
};

export default HomePage;
