/**
 * Home Page - WECARE.DIGITAL Landing
 * WhatsApp Business API Platform
 * Mobile & Tablet Optimized
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
        <title>Base CRM by WECARE.DIGITAL - WhatsApp Business API Platform | Multi-Channel Messaging CRM</title>
        <meta name="description" content="Enterprise WhatsApp Business API platform for India. Send bulk WhatsApp messages, SMS, Email & Voice. AI-powered CRM with Razorpay payments. Connect with 2B+ users. Free trial available." />
        <meta name="keywords" content="WhatsApp Business API, WhatsApp CRM, bulk WhatsApp messaging, WhatsApp marketing India, business messaging platform, SMS API India, email marketing, voice calls API, Razorpay WhatsApp payments, customer engagement platform, multi-channel CRM, WhatsApp automation, WhatsApp chatbot, business communication, enterprise messaging, WhatsApp templates, promotional messages, transactional messages, OTP WhatsApp, order notifications" />
        <meta property="og:type" content="website" />
        <meta property="og:url" content="https://base.wecare.digital/" />
        <meta property="og:title" content="Base CRM - WhatsApp Business API Platform | WECARE.DIGITAL" />
        <meta property="og:description" content="Enterprise WhatsApp Business API platform. Send bulk messages, payments & automate customer engagement with AI. Trusted by businesses across India." />
        <meta property="og:image" content="https://auth.wecare.digital/stream/media/m/wecare-digital.png" />
        <meta property="og:site_name" content="Base CRM by WECARE.DIGITAL" />
        <meta property="og:locale" content="en_IN" />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:url" content="https://base.wecare.digital/" />
        <meta name="twitter:title" content="Base CRM - WhatsApp Business API Platform" />
        <meta name="twitter:description" content="Enterprise WhatsApp Business API platform. Multi-channel messaging CRM with AI automation." />
        <meta name="twitter:image" content="https://auth.wecare.digital/stream/media/m/wecare-digital.png" />
        <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1" />
        <meta name="googlebot" content="index, follow" />
        <meta name="author" content="WECARE.DIGITAL" />
        <meta name="publisher" content="WECARE.DIGITAL" />
        <meta name="copyright" content="WECARE.DIGITAL" />
        <meta name="language" content="English" />
        <meta name="geo.region" content="IN" />
        <meta name="geo.placename" content="India" />
        <link rel="canonical" href="https://base.wecare.digital/" />
        <meta name="theme-color" content="#25d366" />
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="default" />
        <meta name="apple-mobile-web-app-title" content="Base CRM" />
        <meta name="application-name" content="Base CRM" />
        <meta name="format-detection" content="telephone=no" />
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
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
            <h2>Every touchpoint<br/>One seamless experience</h2>
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
              <p className="api-desc">The complete platform for enterprise brands to acquire, convert, and retain customers across every channel—powered by AI that understands your business and unifies customer data into a single view to drive personalized experiences, targeted campaigns, and intelligent automation.</p>
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

        <section className={`capabilities anim ${show('capabilities') ? 'show' : ''}`} id="capabilities">
          <div className="section-header">
            <h2>Everything you need<br/>to grow customer relationships</h2>
            <p>AI-powered lifecycle management that delivers results</p>
          </div>
          <div className="capabilities-grid">
            <div className="capability-card">
              <h3>Customer Data Platform</h3>
              <p>Every signal, unified and current</p>
            </div>
            <div className="capability-card">
              <h3>Custom Data Modeling</h3>
              <p>Objects and segments for your business</p>
            </div>
            <div className="capability-card">
              <h3>Multichannel Orchestration</h3>
              <p>Reach customers anywhere</p>
            </div>
            <div className="capability-card">
              <h3>Smart Personalization</h3>
              <p>Marketing that runs itself</p>
            </div>
            <div className="capability-card">
              <h3>Enterprise Infrastructure</h3>
              <p>APIs and security that scale</p>
            </div>
            <div className="capability-card">
              <h3>Predictive Analytics</h3>
              <p>See revenue before it happens</p>
            </div>
          </div>
        </section>

        <section className={`cta-section anim ${show('cta') ? 'show' : ''}`} id="cta">
          <h2>Transform your customer<br/>experience with Base CRM</h2>
        </section>

        <footer className="ftr">
          <div className="ftr-in">
            <a href="https://www.wecare.digital/contact" className="ftr-contact">Contact us</a>
          </div>
        </footer>

        <style jsx>{`
          /* ========== BASE STYLES ========== */
          .page{min-height:100vh;background:#fff;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1a1a1a;overflow-x:hidden}
          
          /* Header */
          .hdr{position:fixed;top:0;left:0;right:0;z-index:100;background:rgba(255,255,255,.97);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px)}
          .hdr-in{max-width:1200px;margin:0 auto;padding:16px 24px;display:flex;align-items:center}
          .logo{display:flex;align-items:center;gap:10px}
          .logo-text{display:flex;flex-direction:column;justify-content:center}
          .logo-main{font-size:22px;font-weight:800;color:#1a1a1a;letter-spacing:-0.5px;line-height:1.1}
          .logo-sub{font-size:12px;font-weight:600;color:#6b7280;line-height:1;margin-top:2px}
          .logo-img{width:48px;height:48px;border-radius:12px}
          
          /* Animations */
          .anim{opacity:0;transform:translateY(30px);transition:all .7s cubic-bezier(.16,1,.3,1)}
          .anim.show{opacity:1;transform:translateY(0)}
          
          /* Hero Section */
          .hero{padding:140px 24px 80px;max-width:1300px;margin:0 auto}
          .hero-content{display:grid;grid-template-columns:1fr 1.4fr;gap:60px;align-items:center}
          .hero-left h1{font-size:48px;font-weight:700;line-height:1.08;margin:0 0 24px;letter-spacing:-1.5px;color:#1a1a1a}
          .hero-left p{font-size:19px;color:#6b7280;line-height:1.6;margin:0 0 32px;max-width:440px}
          .hero-stats{display:flex;gap:12px;flex-wrap:wrap}
          .stat{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:18px 22px;min-width:110px}
          .stat span{display:block;font-size:26px;font-weight:800;color:#1a1a1a;letter-spacing:-0.5px}
          .stat small{font-size:13px;color:#6b7280;margin-top:4px;display:block;font-weight:500}
          
          /* Hero Right - Mockup */
          .hero-right{display:flex;justify-content:center}
          .mockup-wrapper{position:relative;width:100%;max-width:580px;aspect-ratio:1.1;background:#fff;border-radius:28px;padding:24px}
          .phone{position:absolute;left:24px;top:20px;width:55%;max-width:300px;background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 20px 50px rgba(0,0,0,.12)}
          .phone-header{background:#075e54;padding:12px 14px;display:flex;align-items:center;gap:10px}
          .back-arrow{color:#fff;font-size:20px}
          .avatar{width:40px;height:40px;background:#25d366;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:16px}
          .contact-info{flex:1;display:flex;flex-direction:column}
          .contact-name{color:#fff;font-size:15px;font-weight:600}
          .contact-status{color:rgba(255,255,255,.7);font-size:11px}
          .verified-badge{width:22px;height:22px;background:#25d366;border-radius:50%}
          .chat-area{background:#e8efe5;padding:14px 12px;min-height:280px;display:flex;flex-direction:column;gap:8px}
          .msg{max-width:80%;padding:10px 12px;border-radius:8px;font-size:14px;line-height:1.45;color:#000}
          .msg.received{background:#fff;align-self:flex-start;border-top-left-radius:3px}
          .msg.sent{background:#d9fdd3;align-self:flex-end;border-top-right-radius:3px}
          .msg.sent.left-msg{align-self:flex-start !important;border-top-left-radius:3px;border-top-right-radius:8px}
          .msg p{margin:0}
          .msg-time{font-size:10px;color:#667781;display:block;text-align:right;margin-top:3px}
          .typing-indicator{background:#fff;padding:10px 14px;border-radius:8px;align-self:flex-start;display:flex;gap:4px}
          .typing-indicator span{width:7px;height:7px;background:#90949c;border-radius:50%;animation:bounce 1.4s infinite}
          .typing-indicator span:nth-child(2){animation-delay:.2s}
          .typing-indicator span:nth-child(3){animation-delay:.4s}
          @keyframes bounce{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-3px)}}

          /* Code Box */
          .code-box{position:absolute;right:16px;bottom:20px;width:58%;max-width:340px;background:#1e293b;border-radius:14px;overflow:hidden;box-shadow:0 20px 50px rgba(0,0,0,.2)}
          .code-header{display:flex;align-items:center;padding:10px 14px;background:#0f172a}
          .dots{display:flex;gap:5px}
          .dot-red,.dot-yellow,.dot-green{width:10px;height:10px;border-radius:50%}
          .dot-red{background:#ff5f57}
          .dot-yellow{background:#febc2e}
          .dot-green{background:#28c840}
          .file-name{margin-left:auto;font-size:12px;color:#64748b}
          .code-body{margin:0;padding:14px;font-family:'SF Mono',Monaco,Consolas,monospace;font-size:12px;line-height:1.55;color:#e2e8f0;overflow-x:auto}
          
          /* Section Header */
          .section-header{text-align:center;margin:0 auto 48px;max-width:600px;padding:0 16px;display:flex;flex-direction:column;align-items:center}
          .section-header h2{font-size:42px;font-weight:700;line-height:1.15;margin:0 0 16px;color:#1a1a1a;letter-spacing:-1px;text-align:center;width:100%}
          .section-header p{font-size:18px;color:#6b7280;line-height:1.6;margin:0;text-align:center;width:100%}
          
          /* Touchpoint Section */
          .touchpoint{padding:100px 24px;background:#fff}
          .usecase-pills{display:flex;justify-content:center;gap:12px;flex-wrap:wrap;max-width:700px;margin:0 auto}
          .pill{padding:14px 28px;border:2px solid #e5e7eb;background:#fff;border-radius:50px;font-size:15px;font-weight:600;cursor:default;transition:all .25s;color:#4b5563}
          .pill:hover{border-color:#25d366;color:#25d366;transform:translateY(-2px)}
          
          /* API Section */
          .api{padding:100px 24px;background:#fff}
          .api-grid{display:grid;grid-template-columns:1fr 1fr;gap:60px;max-width:1100px;margin:0 auto;align-items:center}
          .api-info h2{font-size:38px;font-weight:700;color:#1a1a1a;margin:0 0 20px;line-height:1.15;letter-spacing:-1px}
          .api-desc{font-size:18px;color:#6b7280;line-height:1.7;margin:0}
          .api-demo{background:#1e293b;border-radius:16px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,.12)}
          .code-tabs{display:flex;gap:6px;padding:14px 16px;background:#0f172a}
          .tab{padding:10px 20px;border:none;border-radius:8px;font-size:14px;font-weight:600;color:#64748b;background:transparent;cursor:pointer;transition:all .2s}
          .tab:hover{color:#e2e8f0}
          .tab.active{background:#25d366;color:#fff}
          .code-block{margin:0;padding:20px;font-family:'SF Mono',Monaco,Consolas,monospace;font-size:13px;line-height:1.65;color:#e2e8f0;overflow-x:auto;white-space:pre}
          
          /* Capabilities Section */
          .capabilities{padding:100px 24px;background:#fff}
          .capabilities .section-header{margin-bottom:64px}
          .capabilities-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:48px 56px;max-width:960px;margin:0 auto}
          .capability-card h3{font-size:17px;font-weight:700;color:#1a1a1a;margin:0 0 8px}
          .capability-card p{font-size:15px;color:#6b7280;margin:0;line-height:1.55}
          
          /* CTA Section */
          .cta-section{padding:100px 24px;text-align:center;background:#fff}
          .cta-section h2{font-size:42px;font-weight:700;color:#1a1a1a;line-height:1.15;max-width:550px;margin:0 auto;letter-spacing:-1px}
          
          /* Footer */
          .ftr{padding:24px;padding-bottom:calc(24px + env(safe-area-inset-bottom));background:#fff}
          .ftr-in{max-width:1200px;margin:0 auto;display:flex;justify-content:flex-start}
          .ftr-contact{font-size:15px;color:#6b7280;text-decoration:none;font-weight:500}
          .ftr-contact:hover{color:#1a1a1a}

          /* ========== TABLET (768px - 1024px) ========== */
          @media(max-width:1024px){
            .hdr-in{padding:14px 20px}
            .logo-img{width:44px;height:44px}
            .logo-main{font-size:20px}
            .logo-sub{font-size:11px}
            
            .hero{padding:110px 20px 60px}
            .hero-content{grid-template-columns:1fr;gap:40px;text-align:center}
            .hero-left h1{font-size:40px;letter-spacing:-1px;max-width:600px;margin:0 auto 20px}
            .hero-left p{font-size:18px;max-width:520px;margin:0 auto 28px}
            .hero-stats{justify-content:center;gap:12px}
            .stat{padding:16px 20px;min-width:100px}
            .stat span{font-size:24px}
            .stat small{font-size:12px}
            
            .mockup-wrapper{max-width:480px;aspect-ratio:1.15;margin:0 auto;padding:20px}
            .phone{left:16px;top:16px;width:52%}
            .code-box{right:12px;bottom:16px;width:55%}
            
            .section-header h2{font-size:36px}
            .section-header p{font-size:17px}
            
            .touchpoint{padding:80px 20px}
            .usecase-pills{gap:10px}
            .pill{padding:12px 24px;font-size:14px}
            
            .api{padding:80px 20px}
            .api-grid{grid-template-columns:1fr;gap:36px;text-align:left}
            .api-info h2{font-size:34px}
            .api-desc{font-size:17px;max-width:560px;margin:0;text-align:left}
            .api-demo{max-width:560px;margin:0}
            .code-tabs{justify-content:flex-start}
            .code-block{text-align:left}
            
            .capabilities{padding:80px 20px}
            .capabilities-grid{grid-template-columns:repeat(2,1fr);gap:40px 48px}
            
            .cta-section{padding:80px 20px}
            .cta-section h2{font-size:36px}
          }

          /* ========== MOBILE LANDSCAPE & SMALL TABLETS (481px - 767px) ========== */
          @media(max-width:767px){
            .hdr-in{padding:12px 16px}
            .logo{gap:8px}
            .logo-img{width:40px;height:40px;border-radius:10px}
            .logo-main{font-size:18px}
            .logo-sub{font-size:10px}
            
            .hero{padding:calc(90px + env(safe-area-inset-top)) 16px 48px}
            .hero-content{display:flex;flex-direction:column;gap:32px}
            .hero-right{order:-1}
            .hero-left{text-align:left;order:1}
            .hero-left h1{font-size:32px;letter-spacing:-0.5px;margin:0 0 16px;line-height:1.12;max-width:100%}
            .hero-left p{font-size:16px;line-height:1.55;margin:0 0 24px;max-width:100%}
            .hero-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
            .stat{background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:16px 12px;text-align:center;min-width:0}
            .stat span{font-size:22px;font-weight:800}
            .stat small{font-size:11px;margin-top:4px;line-height:1.3}
            
            .mockup-wrapper{display:flex;flex-direction:column;gap:14px;width:100%;aspect-ratio:auto;padding:16px;background:#fff;border-radius:20px}
            .phone{position:relative;left:auto;top:auto;width:100%;max-width:100%;margin:0;border-radius:16px}
            .phone-header{padding:10px 12px;gap:8px}
            .avatar{width:36px;height:36px;font-size:14px}
            .contact-name{font-size:14px}
            .contact-status{font-size:10px}
            .verified-badge{width:20px;height:20px}
            .chat-area{min-height:180px;padding:12px 10px;gap:6px}
            .msg{font-size:13px;padding:9px 11px;max-width:85%}
            .typing-indicator{padding:8px 12px}
            .typing-indicator span{width:6px;height:6px}
            
            .code-box{position:relative;right:auto;bottom:auto;width:100%;max-width:100%;margin:0;border-radius:14px}
            .code-header{padding:10px 12px}
            .dots{gap:4px}
            .dot-red,.dot-yellow,.dot-green{width:9px;height:9px}
            .file-name{font-size:11px}
            .code-body{font-size:11px;padding:12px;line-height:1.5}
            
            .section-header{margin-bottom:32px;padding:0 16px;text-align:center}
            .section-header h2{font-size:28px;margin-bottom:12px;line-height:1.18;text-align:center}
            .section-header p{font-size:15px;line-height:1.55;text-align:center}
            
            .touchpoint{padding:56px 16px}
            .usecase-pills{justify-content:flex-start;gap:8px;overflow-x:auto;-webkit-overflow-scrolling:touch;flex-wrap:nowrap;padding-bottom:8px;margin:0 -16px;padding-left:16px;padding-right:16px;scrollbar-width:none;-ms-overflow-style:none}
            .usecase-pills::-webkit-scrollbar{display:none}
            .pill{padding:11px 20px;font-size:13px;flex-shrink:0;white-space:nowrap}
            
            .api{padding:56px 16px}
            .api-grid{gap:28px}
            .api-info{text-align:left}
            .api-info h2{font-size:28px;margin-bottom:12px}
            .api-desc{font-size:15px;line-height:1.6;max-width:100%;text-align:left}
            .api-demo{border-radius:14px}
            .code-tabs{padding:12px;gap:6px;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none;-ms-overflow-style:none;justify-content:flex-start}
            .code-tabs::-webkit-scrollbar{display:none}
            .tab{padding:9px 16px;font-size:13px;white-space:nowrap;flex-shrink:0}
            .code-block{font-size:11px;padding:14px;min-height:140px;text-align:left}
            
            .capabilities{padding:56px 16px}
            .capabilities .section-header{margin-bottom:32px}
            .capabilities-grid{grid-template-columns:1fr 1fr;gap:28px 20px}
            .capability-card h3{font-size:15px;margin-bottom:6px}
            .capability-card p{font-size:13px;line-height:1.5}
            
            .cta-section{padding:56px 16px}
            .cta-section h2{font-size:28px;line-height:1.2}
            
            .ftr{padding:20px 16px;padding-bottom:calc(20px + env(safe-area-inset-bottom))}
            .ftr-contact{font-size:14px}
          }

          /* ========== MOBILE PORTRAIT (up to 480px) ========== */
          @media(max-width:480px){
            .hero{padding:calc(85px + env(safe-area-inset-top)) 14px 40px}
            .hero-left h1{font-size:28px;line-height:1.15}
            .hero-left p{font-size:15px}
            .hero-stats{grid-template-columns:repeat(3,1fr);gap:8px}
            .stat{padding:14px 8px;border-radius:12px}
            .stat span{font-size:18px}
            .stat small{font-size:10px}
            
            .mockup-wrapper{padding:12px;border-radius:16px;gap:12px}
            .phone{border-radius:14px}
            .phone-header{padding:8px 10px}
            .avatar{width:32px;height:32px;font-size:13px}
            .contact-name{font-size:13px}
            .chat-area{min-height:160px;padding:10px 8px}
            .msg{font-size:12px;padding:8px 10px}
            
            .code-box{border-radius:12px}
            .code-body{font-size:10px;padding:10px}
            
            .section-header h2{font-size:24px}
            .section-header p{font-size:14px}
            
            .touchpoint{padding:48px 14px}
            .pill{padding:10px 18px;font-size:12px}
            
            .api{padding:48px 14px}
            .api-info h2{font-size:24px}
            .api-desc{font-size:14px}
            .code-block{font-size:10px;padding:12px}
            
            .capabilities{padding:48px 14px}
            .capabilities-grid{grid-template-columns:1fr;gap:24px}
            .capability-card h3{font-size:16px}
            .capability-card p{font-size:14px}
            
            .cta-section{padding:48px 14px}
            .cta-section h2{font-size:24px}
          }
          
          /* ========== VERY SMALL SCREENS (up to 360px) ========== */
          @media(max-width:360px){
            .hdr-in{padding:10px 12px}
            .logo-img{width:36px;height:36px}
            .logo-main{font-size:16px}
            .logo-sub{font-size:9px}
            
            .hero{padding:calc(80px + env(safe-area-inset-top)) 12px 36px}
            .hero-left h1{font-size:24px}
            .hero-left p{font-size:14px}
            .hero-stats{gap:6px}
            .stat{padding:12px 6px}
            .stat span{font-size:16px}
            .stat small{font-size:9px}
            
            .section-header h2{font-size:22px}
            .section-header p{font-size:13px}
            
            .api-info h2{font-size:22px}
            .cta-section h2{font-size:22px}
          }
          
          /* ========== LANDSCAPE ORIENTATION FIX ========== */
          @media(max-height:500px) and (orientation:landscape){
            .hero{padding:100px 24px 40px}
            .hero-content{flex-direction:row;gap:24px}
            .hero-right{order:0;flex:1}
            .hero-left{order:0;flex:1;text-align:left}
            .mockup-wrapper{max-height:280px;aspect-ratio:auto}
            .phone{max-width:200px}
            .code-box{max-width:220px}
            .chat-area{min-height:140px}
          }
          
          /* ========== REDUCED MOTION ========== */
          @media(prefers-reduced-motion:reduce){
            .anim{transition:none}
            .typing-indicator span{animation:none}
            .pill{transition:none}
          }
        `}</style>
      </div>
    </>
  );
};

export default HomePage;
