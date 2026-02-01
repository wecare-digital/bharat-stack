/**
 * Home Page - WECARE.DIGITAL Landing
 * WhatsApp Business API Platform
 * Mobile & Tablet Optimized
 */

import React, { useEffect, useState } from 'react';
import Head from 'next/head';
import Script from 'next/script';

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
    { lang: 'Python', code: `import requests

response = requests.post(
  "https://api.wecare.digital/v1/messages",
  headers={
    "Authorization": "Bearer API_KEY"
  },
  json={
    "to": "+919330994400",
    "type": "template"
  }
)` },
    { lang: 'JavaScript', code: `const response = await fetch(
  "https://api.wecare.digital/v1/messages",
  {
    method: "POST",
    headers: {
      "Authorization": "Bearer API_KEY"
    },
    body: JSON.stringify({
      to: "+919330994400"
    })
  }
);` },
    { lang: 'cURL', code: `curl -X POST \\
  "https://api.wecare.digital/v1/messages" \\
  -H "Authorization: Bearer API_KEY" \\
  -d '{"to": "+919330994400"}'` },
  ];

  const capabilities = [
    { title: 'Customer Data Platform', desc: 'Every signal, unified and current', icon: 'https://img.icons8.com/ios/250/000000/database.png' },
    { title: 'Custom Data Modeling', desc: 'Objects and segments for your business', icon: 'https://img.icons8.com/ios/250/000000/layers.png' },
    { title: 'Multichannel Orchestration', desc: 'Reach customers anywhere', icon: 'https://img.icons8.com/ios/250/000000/source-code.png' },
    { title: 'Smart Personalization', desc: 'Marketing that runs itself', icon: 'https://img.icons8.com/ios/250/000000/conference-background-selected.png' },
    { title: 'Enterprise Infrastructure', desc: 'APIs and security that scale', icon: 'https://img.icons8.com/ios/250/000000/lightning-bolt.png' },
    { title: 'Predictive Analytics', desc: 'See revenue before it happens', icon: 'https://img.icons8.com/ios/250/000000/area-chart.png' },
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
        <meta name="theme-color" content="#000000" />
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="default" />
        <meta name="apple-mobile-web-app-title" content="Base CRM" />
        <meta name="application-name" content="Base CRM" />
        <meta name="format-detection" content="telephone=no" />
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
        
        {/* Preload critical images for faster loading */}
        <link rel="preload" href="https://auth.wecare.digital/stream/media/m/wecare-digital.png" as="image" />
        <link rel="preconnect" href="https://img.icons8.com" />
        <link rel="dns-prefetch" href="https://img.icons8.com" />
        
        {/* Structured Data - Organization */}
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({
          "@context": "https://schema.org",
          "@type": "Organization",
          "name": "WECARE.DIGITAL",
          "alternateName": "Base CRM",
          "url": "https://wecare.digital",
          "logo": "https://auth.wecare.digital/stream/media/m/wecare-digital.png",
          "description": "Enterprise WhatsApp Business API platform for multi-channel customer engagement",
          "foundingDate": "2020",
          "sameAs": ["https://www.linkedin.com/company/wecare-digital"],
          "contactPoint": {
            "@type": "ContactPoint",
            "contactType": "customer service",
            "url": "https://www.wecare.digital/contact",
            "availableLanguage": ["English", "Hindi"]
          },
          "address": { "@type": "PostalAddress", "addressCountry": "IN" }
        })}} />
        
        {/* Structured Data - Software Application */}
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({
          "@context": "https://schema.org",
          "@type": "SoftwareApplication",
          "name": "Base CRM by WECARE.DIGITAL",
          "applicationCategory": "BusinessApplication",
          "operatingSystem": "Web Browser",
          "offers": { "@type": "Offer", "price": "0", "priceCurrency": "INR" },
          "description": "Enterprise multi-channel messaging CRM with WhatsApp Business API, SMS, Email, Voice, and AI automation.",
          "featureList": ["WhatsApp Business API", "Bulk Messaging", "SMS API", "Email Marketing", "Voice Calls", "Razorpay Payments", "AI Responses", "Analytics"],
          "aggregateRating": { "@type": "AggregateRating", "ratingValue": "4.8", "ratingCount": "150", "bestRating": "5" }
        })}} />
        
        {/* Structured Data - FAQ */}
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({
          "@context": "https://schema.org",
          "@type": "FAQPage",
          "mainEntity": [
            { "@type": "Question", "name": "What is Base CRM?", "acceptedAnswer": { "@type": "Answer", "text": "Base CRM is an enterprise multi-channel messaging platform integrating WhatsApp Business API, SMS, Email, and Voice for customer engagement." }},
            { "@type": "Question", "name": "How to send bulk WhatsApp messages?", "acceptedAnswer": { "@type": "Answer", "text": "Upload contacts, create templates, and send promotional or transactional messages to thousands of customers via WhatsApp Business API." }},
            { "@type": "Question", "name": "Does it support WhatsApp payments?", "acceptedAnswer": { "@type": "Answer", "text": "Yes, Base CRM integrates with Razorpay for WhatsApp payments with real-time tracking." }}
          ]
        })}} />
        
        {/* Structured Data - WebSite with SearchAction */}
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({
          "@context": "https://schema.org",
          "@type": "WebSite",
          "name": "Base CRM by WECARE.DIGITAL",
          "url": "https://base.wecare.digital",
          "potentialAction": { "@type": "SearchAction", "target": "https://base.wecare.digital/contacts?q={search_term_string}", "query-input": "required name=search_term_string" }
        })}} />
      </Head>
      
      {/* WhatsApp Chat Widget */}
      <Script src="https://auth.wecare.digital/stream/code/wecare-wa-widget.js" strategy="lazyOnload" />
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
            {capabilities.map((cap, i) => (
              <div key={i} className="capability-card">
                <div className="cap-icon"><img src={cap.icon} alt={cap.title} loading="lazy" /></div>
                <h3>{cap.title}</h3>
                <p>{cap.desc}</p>
              </div>
            ))}
          </div>
        </section>

        <section className={`cta-section anim ${show('cta') ? 'show' : ''}`} id="cta">
          <h2>Transform your customer<br/>experience with<br/>Base CRM</h2>
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
          .logo{display:flex;align-items:center;gap:3px}
          .logo-text{display:flex;flex-direction:column;justify-content:center}
          .logo-main{font-size:32px;font-weight:800;color:#1a1a1a;letter-spacing:-0.5px;line-height:1.1}
          .logo-sub{font-size:17px;font-weight:600;color:#6b7280;line-height:1;margin-top:3px}
          .logo-img{width:74px;height:74px;border-radius:14px}
          
          /* Animations */
          .anim{opacity:0;transform:translateY(30px);transition:all .7s cubic-bezier(.16,1,.3,1)}
          .anim.show{opacity:1;transform:translateY(0)}
          
          /* Hero Section */
          .hero{padding:140px 24px 80px;max-width:1300px;margin:0 auto}
          .hero-content{display:grid;grid-template-columns:1fr 1.4fr;gap:60px;align-items:center}
          .hero-left h1{font-size:48px;font-weight:700;line-height:1.08;margin:0 0 24px;letter-spacing:-1.5px;color:#1a1a1a}
          .hero-left p{font-size:21px;color:#6b7280;line-height:1.6;margin:0 0 32px;max-width:440px}
          .hero-stats{display:flex;gap:12px;flex-wrap:wrap}
          .stat{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:18px 22px;min-width:110px}
          .stat span{display:block;font-size:26px;font-weight:800;color:#1a1a1a;letter-spacing:-0.5px}
          .stat small{font-size:16px;color:#6b7280;margin-top:4px;display:block;font-weight:500}
          
          /* Hero Right - Mockup */
          .hero-right{display:flex;justify-content:center}
          .mockup-wrapper{position:relative;width:100%;max-width:580px;aspect-ratio:1.1;background:#fff;border-radius:28px;padding:24px}
          .phone{position:absolute;left:24px;top:20px;width:55%;max-width:300px;background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 20px 50px rgba(0,0,0,.12)}
          .phone-header{background:#075e54;padding:12px 14px;display:flex;align-items:center;gap:10px}
          .back-arrow{color:#fff;font-size:20px}
          .avatar{width:40px;height:40px;background:#128c7e;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:16px}
          .contact-info{flex:1;display:flex;flex-direction:column}
          .contact-name{color:#fff;font-size:17px;font-weight:600}
          .contact-status{color:rgba(255,255,255,.7);font-size:13px}
          .verified-badge{width:22px;height:22px;background:#075e54;border-radius:50%}
          .chat-area{background:#ece5dd;padding:14px 12px;min-height:280px;display:flex;flex-direction:column;gap:8px}
          .msg{max-width:80%;padding:10px 12px;border-radius:8px;font-size:16px;line-height:1.45;color:#000}
          .msg.received{background:#fff;align-self:flex-start;border-top-left-radius:3px}
          .msg.sent{background:#dcf8c6;align-self:flex-end;border-top-right-radius:3px}
          .msg.sent.left-msg{align-self:flex-start !important;border-top-left-radius:3px;border-top-right-radius:8px}
          .msg p{margin:0}
          .msg-time{font-size:12px;color:#667781;display:block;text-align:right;margin-top:3px}
          .typing-indicator{background:#fff;padding:10px 14px;border-radius:8px;align-self:flex-start;display:flex;gap:4px}
          .typing-indicator span{width:7px;height:7px;background:#90949c;border-radius:50%;animation:bounce 1.4s infinite}
          .typing-indicator span:nth-child(2){animation-delay:.2s}
          .typing-indicator span:nth-child(3){animation-delay:.4s}
          @keyframes bounce{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-3px)}}

          /* Code Box */
          .code-box{position:absolute;right:16px;bottom:20px;width:58%;max-width:340px;background:#1e293b;border-radius:14px;overflow:hidden;box-shadow:0 20px 50px rgba(0,0,0,.2)}
          .code-header{display:flex;align-items:center;padding:10px 14px;background:#000}
          .dots{display:flex;gap:5px}
          .dot-red,.dot-yellow,.dot-green{width:10px;height:10px;border-radius:50%}
          .dot-red{background:#ff5f57}
          .dot-yellow{background:#febc2e}
          .dot-green{background:#28c840}
          .file-name{margin-left:auto;font-size:15px;color:#fff}
          .code-body{margin:0;padding:14px;font-family:'SF Mono',Monaco,Consolas,monospace;font-size:15px;line-height:1.55;color:#e2e8f0;overflow-x:auto}
          
          /* Section Header */
          .section-header{text-align:center;margin:0 auto 32px;max-width:700px;padding:0 16px;display:flex;flex-direction:column;align-items:center}
          .section-header h2{font-size:42px;font-weight:700;line-height:1.15;margin:0 0 12px;color:#1a1a1a;letter-spacing:-1px;text-align:center;width:100%;white-space:pre-line}
          .section-header p{font-size:21px;color:#6b7280;line-height:1.6;margin:0;text-align:center;width:100%}
          
          /* Touchpoint Section */
          .touchpoint{padding:60px 24px;background:#fff}
          .usecase-pills{display:flex;justify-content:center;gap:12px;flex-wrap:wrap;max-width:700px;margin:0 auto}
          .pill{padding:14px 28px;border:2px solid #e5e7eb;background:#fff;border-radius:50px;font-size:18px;font-weight:600;cursor:default;transition:all .25s;color:#4b5563}
          .pill:hover{border-color:#10b981;color:#059669;transform:translateY(-2px);box-shadow:0 4px 12px rgba(16,185,129,0.2)}
          
          /* API Section */
          .api{padding:60px 24px;background:#fff}
          .api-grid{display:grid;grid-template-columns:1fr 1fr;gap:60px;max-width:1100px;margin:0 auto;align-items:center}
          .api-info h2{font-size:38px;font-weight:700;color:#1a1a1a;margin:0 0 20px;line-height:1.15;letter-spacing:-1px}
          .api-desc{font-size:21px;color:#6b7280;line-height:1.7;margin:0}
          .api-demo{background:#1e293b;border-radius:16px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,.12)}
          .code-tabs{display:flex;gap:6px;padding:14px 16px;background:#0f172a}
          .tab{padding:10px 20px;border:none;border-radius:8px;font-size:17px;font-weight:600;color:#94a3b8;background:transparent;cursor:pointer;transition:all .2s}
          .tab:hover{color:#fff}
          .tab.active{background:#10b981;color:#fff}
          .code-block{margin:0;padding:20px;font-family:'SF Mono',Monaco,Consolas,monospace;font-size:15px;line-height:1.65;color:#e2e8f0;overflow-x:auto;white-space:pre}
          
          /* Capabilities Section - Card Grid */
          .capabilities{padding:60px 24px;background:#fff}
          .capabilities .section-header{margin-bottom:40px}
          .capabilities-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;max-width:1100px;margin:0 auto}
          .capability-card{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:28px 24px;transition:all .25s}
          .capability-card:hover{border-color:#d1d5db;box-shadow:0 4px 12px rgba(0,0,0,.04)}
          .cap-icon{width:52px;height:52px;background:#fff;border:1px solid #e5e7eb;border-radius:12px;display:flex;align-items:center;justify-content:center;margin-bottom:20px;padding:10px}
          .cap-icon img{width:100%;height:100%;object-fit:contain}
          .capability-card h3{font-size:20px;font-weight:600;color:#1a1a1a;margin:0 0 8px}
          .capability-card p{font-size:21px;color:#6b7280;margin:0;line-height:1.5}
          
          /* CTA Section */
          .cta-section{padding:60px 24px;text-align:center;background:#fff}
          .cta-section h2{font-size:42px;font-weight:700;color:#1a1a1a;line-height:1.15;max-width:550px;margin:0 auto;letter-spacing:-1px}
          
          /* Footer */
          .ftr{padding:24px;padding-bottom:calc(24px + env(safe-area-inset-bottom));background:#fff}
          .ftr-in{max-width:1200px;margin:0 auto;display:flex;justify-content:flex-start}
          .ftr-contact{font-size:21px;color:#6b7280;text-decoration:none;font-weight:500;transition:all .25s}
          .ftr-contact:hover{color:#10b981}

          /* ========== TABLET (768px - 1024px) ========== */
          @media(max-width:1024px){
            .hdr-in{padding:14px 20px}
            .logo-img{width:66px;height:66px}
            .logo-main{font-size:28px}
            .logo-sub{font-size:15px}
            
            .hero{padding:110px 20px 60px}
            .hero-content{grid-template-columns:1fr;gap:40px;text-align:left}
            .hero-left h1{font-size:38px;letter-spacing:-1px;max-width:600px;margin:0 0 20px}
            .hero-left p{font-size:17px;max-width:520px;margin:0 0 28px}
            .hero-stats{justify-content:flex-start;gap:12px}
            .stat{padding:16px 20px;min-width:100px}
            .stat span{font-size:22px}
            .stat small{font-size:12px}
            
            .mockup-wrapper{max-width:480px;aspect-ratio:1.15;margin:0;padding:20px}
            .phone{left:16px;top:16px;width:52%}
            .code-box{right:auto;left:12px;bottom:16px;width:55%}
            
            .section-header h2{font-size:34px}
            .section-header p{font-size:16px}
            
            .touchpoint{padding:50px 20px}
            .usecase-pills{gap:10px}
            .pill{padding:12px 22px;font-size:14px}
            
            .api{padding:50px 20px}
            .api-grid{grid-template-columns:1fr;gap:36px;text-align:left}
            .api-info h2{font-size:32px;text-align:left}
            .api-desc{font-size:16px;max-width:100%;text-align:left}
            .api-demo{max-width:500px;margin:0}
            
            .capabilities{padding:50px 20px}
            .capabilities-grid{grid-template-columns:repeat(2,1fr);gap:16px}
            .capability-card{padding:24px 20px}
            .cap-icon{width:40px;height:40px;font-size:18px;margin-bottom:16px}
            .capability-card h3{font-size:17px}
            .capability-card p{font-size:14px}
            
            .cta-section{padding:50px 20px}
            .cta-section h2{font-size:34px}
          }

          /* ========== MOBILE (up to 767px) ========== */
          @media(max-width:767px){
            .hdr-in{padding:12px 16px}
            .logo{gap:3px}
            .logo-img{width:66px;height:66px;border-radius:14px}
            .logo-main{font-size:28px}
            .logo-sub{font-size:16px}
            
            .hero{padding:calc(90px + env(safe-area-inset-top)) 20px 50px}
            .hero-content{display:flex;flex-direction:column;gap:32px;text-align:left;align-items:flex-start}
            .hero-right{order:-1;width:100%;display:flex;justify-content:flex-start}
            .hero-left{text-align:left;order:1}
            .hero-left h1{font-size:42px;letter-spacing:-0.5px;margin:0 0 20px;line-height:1.12;max-width:100%;text-align:left}
            .hero-left p{font-size:24px;line-height:1.6;margin:0 0 28px;max-width:100%;color:#6b7280;text-align:left}
            .hero-stats{display:flex;flex-direction:column;gap:12px;width:100%}
            .stat{background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:20px 24px;text-align:left;width:100%;display:flex;align-items:center;gap:12px}
            .stat span{font-size:28px;font-weight:800;min-width:70px}
            .stat small{font-size:20px;line-height:1.3;margin:0}
            
            .mockup-wrapper{display:flex;flex-direction:column;gap:14px;width:100%;max-width:380px;margin:0;aspect-ratio:auto;padding:16px;background:#fff;border-radius:20px;border:1px solid #e5e7eb;align-items:flex-start}
            .phone{position:relative;left:auto;top:auto;width:100%;max-width:100%;margin:0;border-radius:16px;box-shadow:0 4px 20px rgba(0,0,0,.08)}
            .phone-header{padding:14px 16px;gap:10px}
            .avatar{width:42px;height:42px;font-size:18px}
            .contact-name{font-size:18px}
            .contact-status{font-size:15px}
            .verified-badge{width:24px;height:24px}
            .chat-area{min-height:200px;padding:14px 12px;gap:10px}
            .msg{font-size:17px;padding:12px 14px;max-width:85%}
            .typing-indicator{padding:12px 16px}
            .typing-indicator span{width:8px;height:8px}
            
            .code-box{position:relative;right:auto;bottom:auto;width:100%;max-width:100%;margin:0;border-radius:14px;box-shadow:0 4px 20px rgba(0,0,0,.1);align-self:flex-start}
            .code-body{text-align:left}
            .code-header{padding:14px 16px}
            .dots{gap:6px}
            .dot-red,.dot-yellow,.dot-green{width:12px;height:12px}
            .file-name{font-size:15px}
            .code-body{font-size:15px;padding:16px;line-height:1.6}
            
            .section-header{margin-bottom:28px;padding:0 20px;text-align:center}
            .section-header h2{font-size:38px;margin-bottom:12px;line-height:1.15;text-align:center}
            .section-header p{font-size:24px;line-height:1.6;text-align:center}
            
            .touchpoint{padding:44px 20px}
            .usecase-pills{justify-content:center;gap:12px;flex-wrap:wrap;padding:0;margin:0}
            .pill{padding:16px 28px;font-size:20px}
            
            .api{padding:44px 20px}
            .api-grid{gap:36px;text-align:left}
            .api-info{text-align:left}
            .api-info h2{font-size:38px;margin-bottom:16px;text-align:left}
            .api-desc{font-size:24px;line-height:1.65;max-width:100%;text-align:left}
            .api-demo{border-radius:14px;max-width:100%;margin:0}
            .code-tabs{padding:16px;gap:10px;justify-content:flex-start;flex-wrap:wrap}
            .tab{padding:14px 24px;font-size:18px}
            .code-block{font-size:14px;padding:18px;min-height:auto;text-align:left;white-space:pre-wrap;word-break:break-word;overflow-x:visible;line-height:1.7}
            
            .capabilities{padding:44px 20px}
            .capabilities .section-header{margin-bottom:24px}
            .capabilities-grid{grid-template-columns:repeat(2,1fr);gap:14px}
            .capability-card{padding:22px 18px;border-radius:14px;text-align:left}
            .cap-icon{width:50px;height:50px;margin-bottom:16px;border-radius:12px;padding:10px}
            .capability-card h3{font-size:20px;margin-bottom:8px;text-align:left}
            .capability-card p{font-size:20px;text-align:left;line-height:1.5}
            
            .cta-section{padding:44px 20px}
            .cta-section h2{font-size:34px;line-height:1.2;max-width:100%}
            
            .ftr{padding:28px 20px;padding-bottom:calc(28px + env(safe-area-inset-bottom))}
            .ftr-contact{font-size:24px}
          }

          /* ========== SMALL MOBILE (up to 480px) ========== */
          @media(max-width:480px){
            .logo-img{width:58px;height:58px;border-radius:12px}
            .logo-main{font-size:26px}
            .logo-sub{font-size:14px}
            
            .hero{padding:calc(85px + env(safe-area-inset-top)) 16px 44px}
            .hero-left h1{font-size:38px;line-height:1.15}
            .hero-left p{font-size:22px}
            .hero-stats{gap:10px}
            .stat{padding:18px 20px;border-radius:12px}
            .stat span{font-size:26px;min-width:65px}
            .stat small{font-size:18px}
            
            .mockup-wrapper{padding:14px;border-radius:18px;gap:12px;max-width:100%}
            .phone{border-radius:14px}
            .phone-header{padding:12px 14px}
            .avatar{width:38px;height:38px;font-size:16px}
            .contact-name{font-size:17px}
            .chat-area{min-height:170px;padding:12px 10px}
            .msg{font-size:16px;padding:10px 12px}
            
            .code-box{border-radius:12px}
            .code-body{font-size:14px;padding:14px}
            
            .section-header h2{font-size:36px}
            .section-header p{font-size:22px}
            
            .touchpoint{padding:36px 16px}
            .usecase-pills{gap:10px}
            .pill{padding:14px 22px;font-size:19px}
            
            .api{padding:36px 16px}
            .api-info h2{font-size:36px;text-align:left}
            .api-desc{font-size:22px;text-align:left}
            .code-tabs{gap:8px;padding:14px}
            .tab{padding:12px 20px;font-size:17px}
            .code-block{font-size:14px;padding:16px;min-height:auto;text-align:left;white-space:pre-wrap;word-break:break-word;overflow-x:visible;line-height:1.65}
            
            .capabilities{padding:36px 16px}
            .capabilities-grid{grid-template-columns:1fr;gap:12px}
            .capability-card{padding:20px 18px;border-radius:12px;text-align:left}
            .cap-icon{width:48px;height:48px;margin-bottom:14px;padding:9px}
            .capability-card h3{font-size:20px;text-align:left}
            .capability-card p{font-size:20px;text-align:left}
            
            .cta-section{padding:36px 16px}
            .cta-section h2{font-size:32px;line-height:1.2;max-width:100%}
            
            .ftr-contact{font-size:22px}
          }
          
          /* ========== VERY SMALL SCREENS (up to 360px) ========== */
          @media(max-width:360px){
            .hdr-in{padding:10px 12px}
            .logo-img{width:54px;height:54px;border-radius:11px}
            .logo-main{font-size:24px}
            .logo-sub{font-size:13px}
            
            .hero{padding:calc(80px + env(safe-area-inset-top)) 14px 36px}
            .hero-left h1{font-size:32px}
            .hero-left p{font-size:19px}
            .hero-stats{gap:8px}
            .stat{padding:14px 16px;min-width:85px}
            .stat span{font-size:22px}
            .stat small{font-size:16px}
            
            .section-header h2{font-size:30px}
            .section-header p{font-size:19px}
            
            .pill{padding:12px 18px;font-size:17px}
            
            .api-info h2{font-size:30px}
            .api-desc{font-size:19px}
            
            .capability-card h3{font-size:18px}
            .capability-card p{font-size:18px}
            
            .cta-section h2{font-size:28px}
            
            .ftr-contact{font-size:19px}
            
            .ftr-contact{font-size:17px}
          }
          
          /* ========== LANDSCAPE ORIENTATION FIX ========== */
          @media(max-height:500px) and (orientation:landscape){
            .hero{padding:90px 24px 40px}
            .hero-content{flex-direction:row;gap:24px;text-align:left}
            .hero-right{order:0;flex:1}
            .hero-left{order:0;flex:1;text-align:left}
            .hero-left h1{margin:0 0 16px}
            .hero-left p{margin:0 0 20px}
            .hero-stats{justify-content:flex-start}
            .mockup-wrapper{max-height:260px;aspect-ratio:auto;max-width:100%}
            .phone{max-width:180px}
            .code-box{max-width:200px}
            .chat-area{min-height:120px}
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
