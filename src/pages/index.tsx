/**
 * Home Page - Base CRM by WECARE.DIGITAL
 * WhatsApp Business API Platform Landing Page
 * Design matching the provided mockup
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
    headers={"Authorization": "Bearer API_KEY"},
    json={"to": "+919330994400", "type": "template"}
)` },
    { lang: 'JavaScript', code: `fetch("https://api.wecare.digital/v1/messages", {
    method: "POST",
    headers: {"Authorization": "Bearer API_KEY"},
    body: JSON.stringify({to: "+919330994400"})
});` },
    { lang: 'cURL', code: `curl -X POST "https://api.wecare.digital/v1/messages" \\
    -H "Authorization: Bearer API_KEY" \\
    -d '{"to": "+919330994400"}'` },
  ];

  const capabilities = [
    { title: 'Customer Data Platform', desc: 'Every signal, unified and current' },
    { title: 'Custom Data Modeling', desc: 'Objects and segments for your business' },
    { title: 'Multichannel Orchestration', desc: 'Reach customers anywhere' },
    { title: 'Smart Personalization', desc: 'Marketing that runs itself' },
    { title: 'Enterprise Infrastructure', desc: 'APIs and security that scale' },
    { title: 'Predictive Analytics', desc: 'See revenue before it happens' },
  ];

  return (
    <>
      <Head>
        <title>Base CRM by WECARE.DIGITAL - WhatsApp Business API Platform</title>
        <meta name="description" content="Enterprise WhatsApp Business API platform for India. Send bulk WhatsApp messages, SMS, Email & Voice." />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="canonical" href="https://base.wecare.digital/" />
      </Head>
      
      <Script src="https://auth.wecare.digital/stream/code/wecare-wa-widget.js" strategy="lazyOnload" />
      
      <div className="page">
        {/* Header */}
        <header className="header">
          <div className="header-inner">
            <div className="logo">
              <img src="https://auth.wecare.digital/stream/media/m/wecare-digital.png" alt="Base CRM" className="logo-img" />
              <div className="logo-text">
                <span className="logo-main">Base CRM</span>
                <span className="logo-sub">by WECARE.DIGITAL</span>
              </div>
            </div>
          </div>
        </header>

        {/* Hero Section */}
        <section className={`hero anim ${show('hero') ? 'show' : ''}`} id="hero">
          <div className="hero-grid">
            <div className="hero-left">
              <h1>Reach more customers wherever they are, whatever they're on</h1>
              <p>Engage them on every channel, in every scenario - from our platform or your stack.</p>
              <div className="hero-stats">
                <div className="stat-card">
                  <span className="stat-value">B+</span>
                  <span className="stat-label">Users reachable</span>
                </div>
                <div className="stat-card">
                  <span className="stat-value">Fast</span>
                  <span className="stat-label">Onboarding</span>
                </div>
                <div className="stat-card">
                  <span className="stat-value">Secure</span>
                  <span className="stat-label">Trusted channel</span>
                </div>
              </div>
            </div>
            
            <div className="hero-right">
              <div className="mockup-container">
                {/* WhatsApp Phone Mockup */}
                <div className="phone-mockup">
                  <div className="phone-notch"></div>
                  <div className="phone-header">
                    <div className="phone-header-left">
                      <span className="back-icon">&#8249;</span>
                      <div className="avatar-circle">W</div>
                      <div className="contact-details">
                        <span className="contact-name">WECARE.DIGITAL</span>
                        <span className="contact-status">online</span>
                      </div>
                    </div>
                    <div className="phone-header-right">
                      <span className="header-icon">&#128249;</span>
                      <span className="header-icon">&#128222;</span>
                      <span className="header-icon">&#8942;</span>
                    </div>
                  </div>
                  <div className="chat-body">
                    <div className="message outgoing">
                      <p>Hi! Your order #WDSR87A6G has been shipped</p>
                      <span className="time">10:30</span>
                    </div>
                    <div className="message incoming">
                      <p>When will it arrive?</p>
                      <span className="time">10:31</span>
                    </div>
                    <div className="message outgoing">
                      <p>Tomorrow by 6 PM</p>
                      <span className="time">10:31</span>
                    </div>
                    <div className="message outgoing">
                      <p>Track here:<br/>wecare.digital/track</p>
                      <span className="time">10:32</span>
                    </div>
                    <div className="typing-dots">
                      <span></span><span></span><span></span>
                    </div>
                  </div>
                  <div className="phone-input">
                    <span className="emoji-icon">&#128512;</span>
                    <input type="text" placeholder="Message" disabled />
                    <span className="attach-icon">&#128206;</span>
                    <span className="camera-icon">&#128247;</span>
                    <div className="mic-btn">&#127908;</div>
                  </div>
                </div>
                
                {/* Code Snippet Box */}
                <div className="code-snippet-box">
                  <pre>{`response = requests.post(
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

        {/* Touchpoint Section */}
        <section className={`touchpoint anim ${show('touchpoint') ? 'show' : ''}`} id="touchpoint">
          <div className="section-center">
            <h2>Every touchpoint<br/>One seamless experience</h2>
            <p>Engage, support, and convert customers across their entire journey - from first contact to lasting loyalty.</p>
          </div>
          <div className="pills-row">
            {useCases.map((uc, i) => (
              <button key={i} className="pill">{uc}</button>
            ))}
          </div>
        </section>

        {/* API Section */}
        <section className={`api-section anim ${show('api') ? 'show' : ''}`} id="api">
          <div className="api-grid">
            <div className="api-text">
              <h2>Built for the AI era.</h2>
              <p>The complete platform for enterprise brands to acquire, convert, and retain customers across every channel-powered by AI that understands your business and unifies customer data into a single view to drive personalized experiences, targeted campaigns, and intelligent automation.</p>
            </div>
            <div className="api-code">
              <div className="code-tabs">
                {codeExamples.map((ex, i) => (
                  <button 
                    key={i} 
                    className={`code-tab ${activeCode === i ? 'active' : ''}`}
                    onClick={() => setActiveCode(i)}
                  >
                    {ex.lang}
                  </button>
                ))}
              </div>
              <pre className="code-content">{codeExamples[activeCode].code}</pre>
            </div>
          </div>
        </section>

        {/* Capabilities Section */}
        <section className={`capabilities anim ${show('capabilities') ? 'show' : ''}`} id="capabilities">
          <div className="section-center">
            <h2>Everything you need<br/>to grow customer relationships</h2>
            <p>AI-powered lifecycle management that delivers results</p>
          </div>
          <div className="capabilities-grid">
            {capabilities.map((cap, i) => (
              <div key={i} className="cap-card">
                <h3>{cap.title}</h3>
                <p>{cap.desc}</p>
              </div>
            ))}
          </div>
        </section>

        {/* CTA Section */}
        <section className={`cta anim ${show('cta') ? 'show' : ''}`} id="cta">
          <h2>Transform your customer<br/>experience with Base CRM</h2>
        </section>

        {/* Footer */}
        <footer className="footer">
          <a href="https://www.wecare.digital/contact">Contact us</a>
        </footer>
      </div>

      <style jsx>{`
        .page {
          min-height: 100vh;
          background: #fff;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          color: #1a1a1a;
        }
        
        /* Header */
        .header {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          z-index: 100;
          background: rgba(255,255,255,0.97);
          backdrop-filter: blur(20px);
        }
        .header-inner {
          max-width: 1200px;
          margin: 0 auto;
          padding: 16px 24px;
          display: flex;
          align-items: center;
        }
        .logo {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .logo-img {
          width: 48px;
          height: 48px;
          border-radius: 12px;
        }
        .logo-text {
          display: flex;
          flex-direction: column;
        }
        .logo-main {
          font-size: 20px;
          font-weight: 700;
          color: #1a1a1a;
        }
        .logo-sub {
          font-size: 12px;
          color: #6b7280;
        }
        
        /* Animations */
        .anim {
          opacity: 0;
          transform: translateY(30px);
          transition: all 0.7s ease;
        }
        .anim.show {
          opacity: 1;
          transform: translateY(0);
        }
        
        /* Hero */
        .hero {
          padding: 120px 24px 60px;
          max-width: 1200px;
          margin: 0 auto;
        }
        .hero-grid {
          display: grid;
          grid-template-columns: 1fr 1.2fr;
          gap: 60px;
          align-items: center;
        }
        .hero-left h1 {
          font-size: 42px;
          font-weight: 700;
          line-height: 1.1;
          margin: 0 0 20px;
          letter-spacing: -1px;
        }
        .hero-left p {
          font-size: 18px;
          color: #6b7280;
          line-height: 1.6;
          margin: 0 0 32px;
        }
        .hero-stats {
          display: flex;
          gap: 12px;
        }
        .stat-card {
          background: #fff;
          border: 1px solid #e5e7eb;
          border-radius: 12px;
          padding: 16px 20px;
          display: flex;
          flex-direction: column;
        }
        .stat-value {
          font-size: 24px;
          font-weight: 700;
        }
        .stat-label {
          font-size: 14px;
          color: #6b7280;
        }
        
        /* Phone Mockup */
        .hero-right {
          display: flex;
          justify-content: center;
        }
        .mockup-container {
          position: relative;
          width: 100%;
          max-width: 500px;
        }
        .phone-mockup {
          width: 280px;
          background: #fff;
          border-radius: 32px;
          overflow: hidden;
          box-shadow: 0 25px 80px rgba(0,0,0,0.15);
          border: 8px solid #1a1a1a;
        }
        .phone-notch {
          width: 120px;
          height: 24px;
          background: #1a1a1a;
          margin: 0 auto;
          border-radius: 0 0 16px 16px;
        }
        .phone-header {
          background: #075e54;
          padding: 10px 12px;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .phone-header-left {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .back-icon {
          color: #fff;
          font-size: 24px;
        }
        .avatar-circle {
          width: 36px;
          height: 36px;
          background: #128c7e;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #fff;
          font-weight: 600;
          font-size: 14px;
        }
        .contact-details {
          display: flex;
          flex-direction: column;
        }
        .contact-name {
          color: #fff;
          font-size: 14px;
          font-weight: 600;
        }
        .contact-status {
          color: rgba(255,255,255,0.8);
          font-size: 11px;
        }
        .phone-header-right {
          display: flex;
          gap: 16px;
        }
        .header-icon {
          color: #fff;
          font-size: 16px;
        }
        .chat-body {
          background: #ece5dd;
          padding: 12px;
          min-height: 280px;
          display: flex;
          flex-direction: column;
          gap: 6px;
        }
        .message {
          max-width: 80%;
          padding: 8px 10px;
          border-radius: 8px;
          font-size: 13px;
          line-height: 1.4;
          position: relative;
        }
        .message p {
          margin: 0;
        }
        .message.outgoing {
          background: #dcf8c6;
          align-self: flex-end;
          border-top-right-radius: 0;
        }
        .message.incoming {
          background: #fff;
          align-self: flex-start;
          border-top-left-radius: 0;
        }
        .time {
          font-size: 10px;
          color: #667781;
          display: block;
          text-align: right;
          margin-top: 2px;
        }
        .typing-dots {
          background: #fff;
          padding: 10px 14px;
          border-radius: 8px;
          align-self: flex-start;
          display: flex;
          gap: 4px;
        }
        .typing-dots span {
          width: 6px;
          height: 6px;
          background: #90949c;
          border-radius: 50%;
          animation: bounce 1.4s infinite;
        }
        .typing-dots span:nth-child(2) { animation-delay: 0.2s; }
        .typing-dots span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes bounce {
          0%, 60%, 100% { transform: translateY(0); }
          30% { transform: translateY(-4px); }
        }
        .phone-input {
          background: #f0f0f0;
          padding: 8px 10px;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .phone-input input {
          flex: 1;
          background: #fff;
          border: none;
          border-radius: 20px;
          padding: 8px 12px;
          font-size: 13px;
        }
        .emoji-icon, .attach-icon, .camera-icon {
          font-size: 18px;
          color: #54656f;
        }
        .mic-btn {
          width: 36px;
          height: 36px;
          background: #00a884;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #fff;
          font-size: 16px;
        }
        
        /* Code Snippet */
        .code-snippet-box {
          position: absolute;
          right: -20px;
          bottom: 40px;
          width: 280px;
          background: #1e293b;
          border-radius: 12px;
          padding: 16px;
          box-shadow: 0 20px 60px rgba(0,0,0,0.2);
        }
        .code-snippet-box pre {
          margin: 0;
          font-family: 'SF Mono', Monaco, Consolas, monospace;
          font-size: 11px;
          line-height: 1.5;
          color: #e2e8f0;
          white-space: pre-wrap;
        }
        
        /* Sections */
        .section-center {
          text-align: center;
          max-width: 600px;
          margin: 0 auto 32px;
        }
        .section-center h2 {
          font-size: 36px;
          font-weight: 700;
          line-height: 1.2;
          margin: 0 0 12px;
          letter-spacing: -0.5px;
        }
        .section-center p {
          font-size: 16px;
          color: #6b7280;
          line-height: 1.6;
          margin: 0;
        }
        
        /* Touchpoint */
        .touchpoint {
          padding: 60px 24px;
        }
        .pills-row {
          display: flex;
          justify-content: center;
          gap: 12px;
          flex-wrap: wrap;
        }
        .pill {
          padding: 12px 24px;
          border: 1px solid #e5e7eb;
          background: #fff;
          border-radius: 50px;
          font-size: 15px;
          font-weight: 500;
          cursor: default;
          transition: all 0.2s;
        }
        .pill:hover {
          border-color: #1a1a1a;
        }
        
        /* API Section */
        .api-section {
          padding: 60px 24px;
        }
        .api-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 48px;
          max-width: 1100px;
          margin: 0 auto;
          align-items: center;
        }
        .api-text h2 {
          font-size: 32px;
          font-weight: 700;
          margin: 0 0 16px;
        }
        .api-text p {
          font-size: 16px;
          color: #6b7280;
          line-height: 1.7;
          margin: 0;
        }
        .api-code {
          background: #1e293b;
          border-radius: 12px;
          overflow: hidden;
        }
        .code-tabs {
          display: flex;
          gap: 4px;
          padding: 12px 16px;
          background: #0f172a;
        }
        .code-tab {
          padding: 8px 16px;
          border: none;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 500;
          color: #94a3b8;
          background: transparent;
          cursor: pointer;
          transition: all 0.2s;
        }
        .code-tab:hover {
          color: #fff;
        }
        .code-tab.active {
          background: #334155;
          color: #fff;
        }
        .code-content {
          margin: 0;
          padding: 20px;
          font-family: 'SF Mono', Monaco, Consolas, monospace;
          font-size: 13px;
          line-height: 1.6;
          color: #e2e8f0;
          overflow-x: auto;
        }
        
        /* Capabilities */
        .capabilities {
          padding: 60px 24px;
        }
        .capabilities-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 20px;
          max-width: 1000px;
          margin: 0 auto;
        }
        .cap-card {
          padding: 24px;
          border: 1px solid #e5e7eb;
          border-radius: 12px;
          transition: all 0.2s;
        }
        .cap-card:hover {
          border-color: #d1d5db;
          box-shadow: 0 4px 12px rgba(0,0,0,0.04);
        }
        .cap-card h3 {
          font-size: 16px;
          font-weight: 600;
          margin: 0 0 6px;
        }
        .cap-card p {
          font-size: 14px;
          color: #6b7280;
          margin: 0;
        }
        
        /* CTA */
        .cta {
          padding: 80px 24px;
          text-align: center;
        }
        .cta h2 {
          font-size: 36px;
          font-weight: 700;
          line-height: 1.2;
          max-width: 500px;
          margin: 0 auto;
        }
        
        /* Footer */
        .footer {
          padding: 24px;
          text-align: left;
        }
        .footer a {
          font-size: 16px;
          color: #6b7280;
          text-decoration: none;
        }
        .footer a:hover {
          color: #1a1a1a;
        }
        
        /* Responsive */
        @media (max-width: 1024px) {
          .hero-grid {
            grid-template-columns: 1fr;
            gap: 40px;
          }
          .hero-left h1 {
            font-size: 36px;
          }
          .mockup-container {
            max-width: 400px;
            margin: 0 auto;
          }
          .code-snippet-box {
            position: relative;
            right: auto;
            bottom: auto;
            width: 100%;
            margin-top: 20px;
          }
          .api-grid {
            grid-template-columns: 1fr;
            gap: 32px;
          }
          .capabilities-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }
        
        @media (max-width: 640px) {
          .hero {
            padding: 100px 16px 40px;
          }
          .hero-left h1 {
            font-size: 28px;
          }
          .hero-stats {
            flex-direction: column;
          }
          .stat-card {
            flex-direction: row;
            align-items: center;
            gap: 12px;
          }
          .phone-mockup {
            width: 100%;
            max-width: 300px;
            margin: 0 auto;
          }
          .section-center h2 {
            font-size: 28px;
          }
          .pills-row {
            gap: 8px;
          }
          .pill {
            padding: 10px 18px;
            font-size: 14px;
          }
          .capabilities-grid {
            grid-template-columns: 1fr 1fr;
            gap: 12px;
          }
          .cap-card {
            padding: 16px;
          }
          .cta h2 {
            font-size: 28px;
          }
        }
      `}</style>
    </>
  );
};

export default HomePage;
