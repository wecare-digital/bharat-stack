/**
 * Grahak OS public product page
 * Customer engagement platform by WECARE.DIGITAL
 */

import React, { useEffect, useRef, useState } from 'react';
import Head from 'next/head';

const GrahakOsPage: React.FC = () => {
  const [visible, setVisible] = useState<Set<string>>(new Set());
  const [activeCode, setActiveCode] = useState(0);

  // Hero headline cycles the channel in the lime pill, the way notion.com
  // rotates the highlighted verb. Width is measured so the pill resizes
  // smoothly instead of snapping between "WhatsApp" and "SMS".
  // Each channel carries its own pill tint AND a matching dot, mirroring the
  // notion.com treatment measured from their hero: the pill is a pale tint and
  // the leading dot is a saturated version of the same hue, both swapping with
  // the word (e.g. pill rgb(230,243,254) with dot rgb(9,127,232)).
  const cycleWords = [
    { word: 'WhatsApp', tint: '#e0f7c8', dot: '#3da35a' },
    { word: 'SMS', tint: '#dbeafe', dot: '#2563eb' },
    { word: 'Email', tint: '#fef3c7', dot: '#f0a818' },
    { word: 'Voice', tint: '#ede9fe', dot: '#9849e8' },
  ];
  const [cycleIndex, setCycleIndex] = useState(0);
  const [heroWidth, setHeroWidth] = useState<number | null>(null);
  const heroRefs = useRef<(HTMLSpanElement | null)[]>([]);

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const id = window.setInterval(
      () => setCycleIndex(i => (i + 1) % cycleWords.length),
      2400
    );
    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const el = heroRefs.current[cycleIndex];
    if (el) setHeroWidth(el.offsetWidth);
  }, [cycleIndex]);

  // NOTE: the rotating pill markup must be written INLINE in the returned JSX.
  // styled-jsx only attaches its scoping class to elements it can statically see
  // in the return tree - extracting this into a variable silently drops every
  // style, which renders the words stacked inline with no pill.
  
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
    { title: 'Customer Data Platform', desc: 'One profile across every channel', icon: "data:image/svg+xml,%3csvg width='100%25' height='100%25' xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3e%3cg fill='none' stroke='%23333333' stroke-miterlimit='10' stroke-width='1.5' data-name='roll brush'%3e%3cpath d='M22.51 4.36c0 .87-1.38 1.63-3.58 2.16a30.8 30.8 0 0 1-7 .72 31 31 0 0 1-7-.72C2.79 6 1.41 5.23 1.41 4.36c0-1.59 4.73-2.87 10.59-2.87s10.51 1.28 10.51 2.87Z'/%3e%3cpath d='M22.51 4.36V12c0 .86-1.38 1.63-3.58 2.15a30.2 30.2 0 0 1-7 .72 30.3 30.3 0 0 1-7-.72C2.79 13.67 1.41 12.9 1.41 12V4.36C1.41 5.23 2.79 6 5 6.52a31 31 0 0 0 7 .72 30.8 30.8 0 0 0 7-.72c2.13-.52 3.51-1.29 3.51-2.16Z'/%3e%3cpath d='M22.51 12v7.67c0 .86-1.38 1.63-3.58 2.16a30.8 30.8 0 0 1-7 .72 31 31 0 0 1-7-.72c-2.19-.53-3.57-1.3-3.57-2.16V12c0 .86 1.38 1.63 3.57 2.15a30.3 30.3 0 0 0 7 .72 30.2 30.2 0 0 0 7-.72c2.2-.48 3.58-1.25 3.58-2.15ZM11 11.08h1.92m1.91 0h1.92m-9.59 0h1.92M11 18.75h1.92m1.91 0h1.92m-9.59 0h1.92'/%3e%3c/g%3e%3c/svg%3e" },
    { title: 'Custom Data Modeling', desc: 'Model customers, events and business objects', icon: "data:image/svg+xml,%3csvg width='100%25' height='100%25' xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24'%3e%3cpath stroke='%23333333' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M14 20a2 2 0 1 1-4 0m4 0a2 2 0 0 0-2-2m2 2h7m-11 0a2 2 0 0 1 2-2m-2 2H3m9-2v-4m9-9c0 1.657-4.03 3-9 3S3 6.657 3 5m18 0c0-1.657-4.03-3-9-3S3 3.343 3 5m18 0v6c0 1.66-4 3-9 3M3 5v6c0 1.66 4 3 9 3'/%3e%3c/svg%3e" },
    { title: 'Multichannel Orchestration', desc: 'Coordinate WhatsApp, SMS, Email and Voice', icon: "data:image/svg+xml,%3csvg width='100%25' height='100%25' xmlns='http://www.w3.org/2000/svg' data-name='Layer 1' viewBox='0 0 24 24'%3e%3cpath fill='none' stroke='%23333333' stroke-miterlimit='10' stroke-width='1.5' d='M7.23 10.14H1.5v5.72m14.32-9.54L12 2.5 8.18 6.32M12 2.5v21'/%3e%3cpath fill='none' stroke='%23333333' stroke-miterlimit='10' stroke-width='1.5' d='m1.5 10.14 5.56 5.56a3.82 3.82 0 0 1 1.12 2.7v5.1m8.59-13.36h5.73v5.72'/%3e%3cpath fill='none' stroke='%23333333' stroke-miterlimit='10' stroke-width='1.5' d='m22.5 10.14-5.56 5.56a3.82 3.82 0 0 0-1.12 2.7v5.1'/%3e%3c/svg%3e" },
    { title: 'Smart Personalization', desc: 'Trigger messages from customer behavior', icon: "data:image/svg+xml,%3csvg width='100%25' height='100%25' xmlns='http://www.w3.org/2000/svg' fill='%23333333' viewBox='0 0 16 16'%3e%3cpath d='M9 5a3 3 0 1 1-6 0 3 3 0 0 1 6 0m-9 8c0 1 1 1 1 1h10s1 0 1-1-1-4-6-4-6 3-6 4m13.5-8.09c1.387-1.425 4.855 1.07 0 4.277-4.854-3.207-1.387-5.702 0-4.276Z'/%3e%3c/svg%3e" },
    { title: 'Enterprise Infrastructure', desc: 'Secure APIs built to scale', icon: "data:image/svg+xml,%3csvg width='100%25' height='100%25' xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24'%3e%3cpath stroke='%23333333' stroke-linecap='round' stroke-linejoin='round' stroke-width='1.5' d='M13 2 3 14h9l-1 8 10-12h-9l1-8Z'/%3e%3c/svg%3e" },
    { title: 'Predictive Analytics', desc: 'Turn engagement signals into actionable insights', icon: "data:image/svg+xml,%3csvg width='100%25' height='100%25' xmlns='http://www.w3.org/2000/svg' fill='none' stroke-width='1.5' viewBox='0 0 24 24'%3e%3cpath stroke='%23333333' stroke-linecap='round' stroke-linejoin='round' d='m21 19.452-9-6.61m0 0V3m0 9.843-9 6.609m17.438-2.742L21 19.452 18.188 20M9.75 5.194 12 3l2.25 2.194M5.813 20 3 19.452l.563-2.742'/%3e%3c/svg%3e" },
  ];

  return (
    <>
      <Head>
        <title>Grahak OS by WECARE.DIGITAL - Customer Engagement Platform</title>
        <meta name="description" content="Grahak OS is the customer engagement product in Bharat Stack by WECARE.DIGITAL, unifying WhatsApp, SMS, Email, Voice, automation and customer data in one experience." />
        <meta name="keywords" content="WhatsApp Business API, WhatsApp CRM, bulk WhatsApp messaging, WhatsApp marketing India, business messaging platform, SMS API India, email marketing, voice calls API, Razorpay WhatsApp payments, customer engagement platform, multi-channel CRM, WhatsApp automation, WhatsApp chatbot, business communication, enterprise messaging, WhatsApp templates, promotional messages, transactional messages, OTP WhatsApp, order notifications" />
        <meta property="og:type" content="website" />
        <meta property="og:url" content="https://stack.wecare.digital/grahak-os/" />
        <meta property="og:title" content="Grahak OS - Customer Engagement Platform | WECARE.DIGITAL" />
        <meta property="og:description" content="Enterprise WhatsApp Business API platform. Send bulk messages, payments & automate customer engagement with AI. Trusted by businesses across India." />
        <meta property="og:image" content="https://app.wecare.digital/stream/media/m/wecaredigital.png" />
        <meta property="og:site_name" content="Bharat Stack by WECARE.DIGITAL" />
        <meta property="og:locale" content="en_IN" />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:url" content="https://stack.wecare.digital/grahak-os/" />
        <meta name="twitter:title" content="Grahak OS - Customer Engagement Platform" />
        <meta name="twitter:description" content="Enterprise WhatsApp Business API platform. Multi-channel messaging CRM with AI automation." />
        <meta name="twitter:image" content="https://app.wecare.digital/stream/media/m/wecaredigital.png" />
        <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1" />
        <meta name="googlebot" content="index, follow" />
        <meta name="author" content="WECARE.DIGITAL" />
        <meta name="publisher" content="WECARE.DIGITAL" />
        <meta name="copyright" content="WECARE.DIGITAL" />
        <meta name="language" content="English" />
        <meta name="geo.region" content="IN" />
        <meta name="geo.placename" content="India" />
        <link rel="canonical" href="https://stack.wecare.digital/grahak-os/" />
        <meta name="theme-color" content="#000000" />
        <meta name="mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="default" />
        <meta name="apple-mobile-web-app-title" content="Grahak OS" />
        <meta name="application-name" content="Grahak OS" />
        <meta name="format-detection" content="telephone=no" />
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
        
        {/* Preload critical images for faster loading */}
        <link rel="preload" href="https://app.wecare.digital/stream/media/m/wecaredigital.png" as="image" />
        <link rel="preconnect" href="https://img.icons8.com" />
        <link rel="dns-prefetch" href="https://img.icons8.com" />
        
        {/* Structured Data - Organization */}
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({
          "@context": "https://schema.org",
          "@type": "Organization",
          "name": "WECARE.DIGITAL",
          "alternateName": "Bharat Stack",
          "url": "https://wecare.digital",
          "logo": "https://app.wecare.digital/stream/media/m/wecaredigital.png",
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
          "name": "Grahak OS by WECARE.DIGITAL",
          "applicationCategory": "BusinessApplication",
          "operatingSystem": "Web Browser",
          "offers": { "@type": "Offer", "price": "0", "priceCurrency": "INR" },
          "description": "Customer engagement product in Bharat Stack with WhatsApp Business API, SMS, Email, Voice, customer data and AI automation.",
          "featureList": ["WhatsApp Business API", "Bulk Messaging", "SMS API", "Email Marketing", "Voice Calls", "Razorpay Payments", "AI Responses", "Analytics"],
        })}} />
        
        {/* Structured Data - FAQ */}
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({
          "@context": "https://schema.org",
          "@type": "FAQPage",
          "mainEntity": [
            { "@type": "Question", "name": "What is Grahak OS?", "acceptedAnswer": { "@type": "Answer", "text": "Grahak OS is the customer engagement product in Bharat Stack, unifying customer data and multi-channel communication across WhatsApp, SMS, Email, and Voice." }},
            { "@type": "Question", "name": "How to send bulk WhatsApp messages?", "acceptedAnswer": { "@type": "Answer", "text": "Upload contacts, create templates, and send promotional or transactional messages to thousands of customers via WhatsApp Business API." }},
            { "@type": "Question", "name": "Does it support WhatsApp payments?", "acceptedAnswer": { "@type": "Answer", "text": "Yes, Grahak OS supports payment workflows through the existing Bharat Stack integrations." }}
          ]
        })}} />
        
        {/* Structured Data - WebSite with SearchAction */}
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({
          "@context": "https://schema.org",
          "@type": "WebSite",
          "name": "Grahak OS by WECARE.DIGITAL",
          "url": "https://stack.wecare.digital/grahak-os/",
          "potentialAction": { "@type": "SearchAction", "target": "https://stack.wecare.digital/contacts?q={search_term_string}", "query-input": "required name=search_term_string" }
        })}} />
      </Head>
      
      <div className="page">

        <section className={`hero anim ${show('hero') ? 'show' : ''}`} id="hero">
          <div className="hero-content">
            <div className="hero-left">
              <h1>
                Reach customers<br />across{ ' ' }
                <span
                  className="hero-mark"
                  style={ { background: cycleWords[cycleIndex].tint } }
                >
                  <i
                    className="hero-mark-dot"
                    style={ { background: cycleWords[cycleIndex].dot } }
                    aria-hidden="true"
                  />
                  <span
                    className="hero-cycle"
                    style={ heroWidth ? { width: `${heroWidth}px` } : undefined }
                  >
                    <span className="sr-only">{ cycleWords.map(c => c.word).join(', ') }</span>
                    { cycleWords.map((c, i) => (
                      <span
                        key={ c.word }
                        ref={ el => { heroRefs.current[i] = el; } }
                        className={ `hero-cyc-word ${i === cycleIndex ? 'on' : ''}`.trim() }
                        aria-hidden="true"
                      >{ c.word }</span>
                    )) }
                  </span>
                </span>
              </h1>
              <p>One platform for customer data, messaging, automation, and campaigns&mdash;keeping every customer conversation connected through WhatsApp, SMS, Email, and Voice.</p>
              <p className="hero-sub">Turn your WhatsApp number into your #1 revenue channel with Grahak OS.</p>
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
                    {/* Order is load-bearing, not arbitrary. The code panel laps the
                        phone's lower-right corner, so anything RIGHT-aligned low in
                        the thread disappears behind it. Both sent bubbles therefore
                        sit at the top, and the lapped band below holds only the
                        received bubble and the typing dots, which are left-aligned
                        and clear the panel.
                        The reference design solved this by left-aligning the lower
                        sent bubbles instead - which put two business replies on the
                        customer's side of the thread. This keeps the composition and
                        the WhatsApp semantics. Verified by measuring bubble rects
                        against the panel rect, not by eye. */}
                    <div className="msg sent"><p>Hi! Your order #WD-ORD-87A6G has been shipped</p><span className="msg-time">10:30</span></div>
                    <div className="msg sent"><p>Track here: wecare.digital/track</p><span className="msg-time">10:30</span></div>
                    <div className="msg received"><p>When will it arrive?</p><span className="msg-time">10:31</span></div>
                    <div className="msg received"><p>Can I change the delivery address?</p><span className="msg-time">10:32</span></div>
                    <div className="typing-indicator"><span></span><span></span><span></span></div>
                  </div>
                </div>
                <div className="code-box">
                  <div className="code-header">
                    <div className="dots"><span className="dot-red"></span><span className="dot-yellow"></span><span className="dot-green"></span></div>
                    <span className="file-name">send_message.py</span>
                  </div>
                  {/* The full, real call - not an abbreviation. An earlier pass cut
                      this down to fit a 248px panel, which lost the assignment, the
                      API version and the auth header, so it stopped looking like
                      code someone would actually ship. The panel is now ~340px and
                      the longest line here (36 chars) fits without wrapping. */}
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

        {/*
          Full-bleed tint pattern: touchpoint and capabilities sit on a #fafafa
          canvas that has to reach both window edges, so the 1300px measure moves
          off the section and onto .pp-inner while the section itself goes 100vw
          with a centring negative margin. Every class this pattern introduces is
          pp- prefixed on purpose: src/styles/*.css (loaded globally by _app.tsx)
          declares unscoped rules for generic names like .pill / .stat / .phone,
          and styled-jsx does not shield the page from those. As with the hero
          pill, the markup stays inline in the return - styled-jsx only scopes
          what it can statically see there.
        */}

        <section className={`touchpoint anim ${show('touchpoint') ? 'show' : ''}`} id="touchpoint">
          <div className="pp-inner">
            <div className="section-header">
              <h2>Every touchpoint<br/>One seamless experience</h2>
              <p>Engage, support, and convert customers across their entire journey - from first contact to lasting loyalty</p>
            </div>
            <div className="usecase-pills">
              {useCases.map((title, i) => (
                <span key={i} className="pp-pill">{title}</span>
              ))}
            </div>
          </div>
        </section>

        <section className={`api anim ${show('api') ? 'show' : ''}`} id="api">
          <div className="api-grid">
            <div className="api-info">
              <h2>Built for your stack</h2>
              <p className="api-desc">Use Grahak OS through its own customer engagement workspace or connect your stack through secure APIs for messaging, customer data, automation and campaigns.</p>
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
          <div className="pp-inner">
            <div className="section-header">
              <h2>Everything you need<br/>to grow customer relationships</h2>
              <p>AI-powered lifecycle management that delivers results</p>
            </div>
            <div className="capabilities-grid">
              {capabilities.map((cap, i) => (
                <div key={i} className="capability-card">
                  {/* same six icons, recoloured to the dark green in the palette */}
                  <div className="cap-icon"><img src={cap.icon.replace(/%23333333/g, '%231a3a2a')} alt={cap.title} loading="lazy" /></div>
                  <h3>{cap.title}</h3>
                  <p>{cap.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className={`why-section anim ${show('why') ? 'show' : ''}`} id="why">
          <div className="section-header">
            <h2>Why Grahak OS</h2>
            <p>One operating layer for customer engagement, built around data, orchestration and every channel your customers use.</p>
          </div>
          <div className="why-grid">
            <div className="why-item"><strong>Unified customer data</strong><span>Bring customer context together across conversations, events and channels.</span></div>
            <div className="why-item"><strong>Intelligent orchestration</strong><span>Coordinate journeys, automation and campaigns from one engagement layer.</span></div>
            <div className="why-item"><strong>Every channel in one platform</strong><span>Connect WhatsApp, SMS, Email and Voice without fragmenting the customer experience.</span></div>
          </div>
        </section>

        <section className={`trust-strip anim ${show('trust-strip') ? 'show' : ''}`} id="trust-strip" aria-label="Trusted by Meta">
          <div className="trust-grid">
            <div className="trust-card">
              <div className="trust-logo">
                <img className="trust-mark meta-mark" src="https://app.wecare.digital/stream/media/m/meta-icon.svg" alt="Meta" loading="lazy" />
                <span className="trust-wordmark">Meta</span>
              </div>
              <div className="trust-divider" />
              <span className="trust-caption">Meta Tech Partner</span>
            </div>
            <div className="trust-content">
              <span className="trust-badge">OFFICIAL META TECH PARTNER</span>
              <h2 className="trust-heading">Trusted by Meta</h2>
              <p className="trust-subtext">Customer engagement across WhatsApp, SMS, Email &amp; Voice — powered by Grahak OS.</p>
              <div className="trust-pills">
                <span className="pill">WhatsApp</span>
                <span className="pill">SMS</span>
                <span className="pill">Email</span>
                <span className="pill">Voice</span>
              </div>
            </div>
          </div>
        </section>

        <section className={`gos-closer anim ${show('gos-closer') ? 'show' : ''}`} id="gos-closer">
          <h2 className="gos-closer-head">Transform customer engagement with Grahak OS</h2>
        </section>


        <style jsx>{`
          /* ========== BASE STYLES ========== */
          .page{min-height:100vh;background:#fff;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1a1a1a;overflow-x:hidden}
          
          /* Animations */
          .anim{opacity:0;transform:translateY(30px);transition:all .7s cubic-bezier(.16,1,.3,1)}
          .anim.show{opacity:1;transform:translateY(0)}
          
          /* Hero Section */
          .hero{padding:140px 24px 80px;max-width:1300px;margin:0 auto}
          /* Left column gets the extra room: the display type is large and the
             headline must hold to two lines ("Reach customers" / "across <pill>")
             so the rotating pill always lands on the last line without reflowing
             the line above it. */
          /* align-items:start, not center. The mockup column is taller than the
             copy column, and centring lifted its top edge ~70px above the copy -
             far enough to slide under the 108px fixed header, which clipped the
             phone's title bar. Starting both columns at the hero's top padding
             keeps the mockup clear of the header at every width. */
          .hero-content{display:grid;grid-template-columns:1fr 1fr;gap:56px;align-items:start}
          /* 60px cap is deliberate: at 64px "across <WhatsApp pill>" needs ~562px
             of the 564px column, so the pill wrapped to a third line. 60px leaves
             ~35px of slack so the headline holds two lines on every channel. */
          /* The row is start-aligned so the taller mockup clears the fixed header,
             but that left ~100px of empty column under the shorter copy. Centring
             just the copy fixes the imbalance without moving the mockup. */
          .hero-left{align-self:center}
          .hero-left h1{font-size:clamp(36px,4.3vw,60px);font-weight:600;line-height:1.04;margin:0 0 24px;letter-spacing:-2.2px;color:rgba(0,0,0,.95)}
          /* Lede plus a muted supporting line. Two paragraphs rather than one long
             run-on: it reads better and gives the left column enough vertical mass
             to sit against the mockup opposite (which was 221px taller). Measures
             are capped so each wraps to a comfortable 2-3 lines. */
          /* Text colours measured from notion.com rather than picked off a grey
             ramp: their hero subtext is rgba(0,0,0,.898) at 20px and their
             secondary copy rgba(0,0,0,.54). The previous #9ca3af sat far lighter
             than anything they use for body text, which is why it read washed out. */
          /* Body copy matches notion.com exactly. Measured from their hero subtext:
             Inter 400 at 20px, line-height 28px (1.4), letter-spacing -0.125px,
             colour rgba(0,0,0,.898). The previous rule used line-height 1.6 and no
             tracking, which is why it still read differently from theirs even once
             the colour matched. */
          /* Measure set in px, not ch: Inter's "0" is ~12.6px at 20px, so 38ch
             resolved to 479px - nearly the full column - which is why the copy
             still looked like it ran edge to edge. 400px holds a comfortable
             ~60-70 characters per line and wraps to more lines, which also closes
             part of the height difference against the mockup column. */
          .hero-left p{font-size:20px;color:rgba(0,0,0,.898);line-height:1.4;letter-spacing:-.125px;font-weight:400;margin:0 0 18px;max-width:400px}
          .hero-left p.hero-sub{font-size:20px;color:rgba(0,0,0,.898);line-height:1.4;letter-spacing:-.125px;font-weight:400;margin:0;max-width:400px}

          /* Rotating channel pill in the hero headline (Notion-style). The lime
             tint is a pseudo-element so it can wipe in from the left without
             reflowing the sentence, and each word is absolutely stacked so
             swapping causes no reflow - the measured width animates instead. */
          /* Fully-rounded pill whose tint transitions with the word, matching the
             notion.com treatment (radius 9999px, transition on the colour). The
             tint itself is set inline per word; the reveal wipe lives on ::before. */
          .hero-mark{
            position:relative;display:inline-block;white-space:nowrap;
            padding:.02em .3em .02em .22em;
            border-radius:9999px;
            background:#e0f7c8;
            transition:background-color .52s cubic-bezier(.16,1,.3,1);
          }
          .hero-mark::before{
            content:'';position:absolute;inset:0;
            background:#fff;border-radius:9999px;
            transform:scaleX(1);transform-origin:right center;
            transition:transform .78s cubic-bezier(.16,1,.3,1) .18s;
            z-index:0;
          }
          .hero.show .hero-mark::before{transform:scaleX(0)}
          .hero-mark-dot{
            position:relative;z-index:1;
            /* 0.33em matches notion.com's ratio (32px dot against a 96px h1).
               Tight 0.1em gap - at 0.2em the dot read as detached from the word. */
            display:inline-block;width:.33em;height:.33em;
            background:#d1f470;border-radius:50%;
            margin-right:.18em;vertical-align:.14em;
            transform:scale(0);
            transition:transform .5s cubic-bezier(.34,1.56,.64,1) .72s;
          }
          .hero.show .hero-mark-dot{transform:scale(1)}
          .hero-cycle{
            position:relative;z-index:1;
            display:inline-block;
            height:1.06em;line-height:1.06em;
            vertical-align:baseline;
            overflow:hidden;
            transition:width .52s cubic-bezier(.16,1,.3,1);
            will-change:width;
          }
          .hero-cyc-word{
            position:absolute;left:0;top:0;
            white-space:nowrap;
            opacity:0;
            transform:translateY(.42em);
            transition:opacity .42s cubic-bezier(.16,1,.3,1),transform .42s cubic-bezier(.16,1,.3,1);
          }
          .hero-cyc-word.on{opacity:1;transform:translateY(0)}
          .sr-only{
            position:absolute;width:1px;height:1px;padding:0;margin:-1px;
            overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0;
          }
          @media(prefers-reduced-motion:reduce){
            .hero-mark::before,.hero-mark-dot{transition:none}
            .hero-mark::before{transform:scaleX(1)}
            .hero-mark-dot{transform:scale(1)}
            .hero-cycle{transition:none}
            .hero-cyc-word{transition:none}
          }
          
          /* Trusted by Meta section */
          .trust-strip{max-width:1300px;margin:0 auto 28px;padding:20px 24px 0}
          .trust-grid{display:grid;grid-template-columns:1fr 1fr;gap:40px;align-items:center}
          .trust-card{border:2px solid #d1f470;background:#fbfff0;border-radius:20px;padding:48px 36px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:26px;width:100%;max-width:430px;margin:0 auto;box-sizing:border-box}
          .trust-logo{display:flex;align-items:center;gap:14px}
          .trust-mark{width:52px;height:52px;flex:0 0 auto;object-fit:contain}
          .trust-wordmark{font-size:36px;font-weight:800;letter-spacing:-1px;color:#1a3a2a}
          .trust-divider{width:100%;height:1px;background:#d1f470}
          .trust-caption{font-size:22px;font-weight:700;line-height:1.27;letter-spacing:-.25px;color:#000;text-align:center}
          .trust-content{display:flex;flex-direction:column;align-items:flex-start;gap:16px;min-width:0}

          /* ===== Closing statement (Notion-style display type + motion) ===== */
          .gos-closer{max-width:1100px;margin:0 auto;padding:96px 24px 112px;display:flex;justify-content:center}
          .gos-closer-head{
            font-size:clamp(38px,6vw,84px);
            font-weight:600;
            letter-spacing:-3px;
            line-height:1.06;
            color:rgba(0,0,0,.95);
            text-align:center;
            margin:0;
            max-width:960px;
          }
          .trust-badge{display:inline-block;background:#d1f470;color:#1a3a2a;font-size:12px;font-weight:700;letter-spacing:.6px;text-transform:uppercase;padding:7px 16px;border-radius:50px}
          .trust-heading{font-size:clamp(32px,4.2vw,54px);font-weight:700;line-height:1.04;letter-spacing:-1.875px;color:rgba(0,0,0,.95);margin:0}
          .trust-subtext{font-size:20px;color:rgba(0,0,0,.898);line-height:1.4;letter-spacing:-.125px;font-weight:400;margin:0}
          .trust-pills{display:flex;flex-wrap:wrap;gap:12px}

          /* Hero Right - Mockup */
          .hero-right{display:flex;justify-content:center}
          /* The phone's content is ~458px tall, so the wrapper is sized from that
             rather than a ratio that would crop it. */
          /* These three heights are solved together, not tuned by eye. The panel is
             anchored bottom:0, so panelTop = wrapperHeight - panelHeight(277).
             Constraints:
               1. panelTop must clear the bottom of the lowest RIGHT-aligned bubble
                  (~300px) or the panel eats its text  -> wrapperHeight >= 577
               2. the panel should overhang the phone by only ~20px, as in the
                  reference -> phoneBottom ~= wrapperHeight - 20 -> phone ~= 542
                  -> chat-area min-height 480 (phone = 62 header + 480)
             Hence 590 / 480. Shrinking the wrapper to 540 in an earlier pass moved
             the panel UP and swallowed a whole bubble - the opposite of the fix. */
          .mockup-wrapper{position:relative;width:100%;max-width:580px;min-height:590px;background:#fff;border-radius:28px;padding:28px 24px 24px}
          /* The two panels OVERLAP on purpose - the code panel laps the phone's
             lower-right corner, which is the whole composition. 56% + 60% = 116%
             of the wrapper, so the lap is ~16%.
             History worth keeping: an earlier pass set these to 50%/44%, which
             left a visible gap and read as two unrelated cards sitting side by
             side. Before that, 55%/58% lapped so far that the panel covered the
             message column and hid bubble text. 16% is the band that laps the
             corner without eating a message.
             top:28px, not 8px. At 8px the phone sat flush with the wrapper's top
             edge, so its dark title bar ran under the fixed header and read as
             clipped. */
          .phone{position:absolute;left:0;top:28px;width:56%;max-width:320px;background:#fff;border-radius:20px;overflow:hidden;box-shadow:0 20px 50px rgba(0,0,0,.12)}
          .phone-header{background:#1a3a2a;padding:12px 14px;display:flex;align-items:center;gap:10px}
          .back-arrow{color:#fff;font-size:20px}
          .avatar{width:40px;height:40px;background:#1a3a2a;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;font-size:16px}
          .contact-info{flex:1;display:flex;flex-direction:column}
          .contact-name{color:#fff;font-size:17px;font-weight:600}
          .contact-status{color:rgba(255,255,255,.7);font-size:13px}
          .verified-badge{width:22px;height:22px;background:#1a3a2a;border-radius:50%}
          .chat-area{background:#ece5dd;padding:16px 14px;min-height:480px;display:flex;flex-direction:column;gap:9px}
          .msg{max-width:82%;padding:10px 13px;border-radius:8px;font-size:17px;line-height:1.42;color:#000}
          /* Received bubbles are capped narrower than sent ones. They sit low in the
             thread, inside the band the code panel laps, and at 82% they grew past
             the panel's left edge and got clipped on their RIGHT - which looks like
             a rendering fault rather than a deliberate overlap. 66% keeps them clear
             of it. */
          .msg.received{background:#fff;align-self:flex-start;max-width:66%;border-top-left-radius:3px}
          .msg.sent{background:#d1f470;align-self:flex-end;border-top-right-radius:3px}
          /* Every sent bubble sits on the right. Two of them previously carried a
             left-msg override that forced them to flex-start, so outgoing messages
             appeared on both sides of the same thread. */
          .msg p{margin:0}
          .msg-time{font-size:12px;color:#667781;display:block;text-align:right;margin-top:3px}
          .typing-indicator{background:#fff;padding:10px 14px;border-radius:8px;align-self:flex-start;display:flex;gap:4px}
          .typing-indicator span{width:7px;height:7px;background:#1a3a2a;border-radius:50%;animation:bounce 1.4s infinite}
          .typing-indicator span:nth-child(2){background:#86b817;animation-delay:.2s}
          .typing-indicator span:nth-child(3){background:#c3e85a;animation-delay:.4s}
          @keyframes bounce{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-3px)}}

          /* Code Box */
          /* Pure black, not slate. The panel reads as a terminal against the warm
             chat beige, and the slate #1e293b muddied that contrast. */
          .code-box{position:absolute;right:0;bottom:0;width:60%;max-width:340px;background:#000;border-radius:14px;overflow:hidden;box-shadow:0 20px 50px rgba(0,0,0,.2)}
          .code-header{display:flex;align-items:center;padding:10px 14px;background:#000}
          .dots{display:flex;gap:5px}
          .dot-red,.dot-yellow,.dot-green{width:10px;height:10px;border-radius:50%}
          .dot-red{background:#ff5f57}
          .dot-yellow{background:#febc2e}
          .dot-green{background:#28c840}
          .file-name{margin-left:auto;font-size:15px;color:#fff}
          /* pre-wrap rather than pre: at narrower viewports the panel shrinks and
             the longest lines were cut off mid-token behind overflow:auto, with no
             visible scrollbar to reveal them. NOTE: no backticks in comments here -
             this whole block is a template literal and a backtick ends it. */
          /* The hairline outline is the detail that makes this read as an editor
             pane rather than a flat dark rectangle. Both this and .code-box are
             #000, so the rounded corners of the two simply coincide and only the
             stroke shows. */
          .code-body{margin:0;padding:15px 16px;border:1.5px solid rgba(255,255,255,.92);border-radius:14px;background:#000;font-family:'SF Mono',Monaco,Consolas,monospace;font-size:14px;line-height:1.6;color:#fff;white-space:pre-wrap;overflow-wrap:break-word}
          
          /* Section Header */
          .section-header{text-align:center;margin:0 auto 32px;max-width:700px;padding:0 24px;display:flex;flex-direction:column;align-items:center}
          .section-header h2{font-size:clamp(32px,4.2vw,54px);font-weight:700;line-height:1.04;letter-spacing:-1.875px;color:rgba(0,0,0,.95);margin:0 0 14px;text-align:center;width:100%;white-space:pre-line}
          .section-header p{font-size:20px;color:rgba(0,0,0,.898);line-height:1.4;letter-spacing:-.125px;font-weight:400;margin:0;text-align:center;width:100%}
          
          /* Touchpoint Section */
          .touchpoint{padding:60px 24px;max-width:1300px;margin:0 auto;background:#fff}
          .usecase-pills{display:flex;justify-content:center;gap:12px;flex-wrap:wrap;max-width:700px;margin:0 auto}
          .pill{padding:14px 28px;border:2px solid #e5e7eb;background:#fff;border-radius:50px;font-size:var(--text-base);font-weight:600;cursor:default;transition:all .25s;color:#4b5563}
          .pill:hover{border-color:#d1f470;color:#1a3a2a;background:#fbfff0;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}
          
          /* API Section */
          .api{padding:60px 24px;max-width:1300px;margin:0 auto;background:#fff}
          .api-grid{display:grid;grid-template-columns:1fr 1fr;gap:60px;max-width:1100px;margin:0 auto;align-items:center}
          .api-info h2{font-size:clamp(32px,4.2vw,54px);font-weight:700;line-height:1.04;letter-spacing:-1.875px;color:rgba(0,0,0,.95);margin:0 0 20px}
          .api-desc{font-size:20px;color:rgba(0,0,0,.898);line-height:1.4;letter-spacing:-.125px;font-weight:400;margin:0}
          .api-demo{background:#1e293b;border-radius:16px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,.12)}
          .code-tabs{display:flex;gap:6px;padding:14px 16px;background:#0f172a}
          .tab{padding:10px 20px;border:none;border-radius:8px;font-size:15px;font-weight:600;color:#94a3b8;background:transparent;cursor:pointer;transition:all .2s}
          .tab:hover{color:#fff}
          .tab.active{background:#d1f470;color:#1a3a2a}
          .code-block{margin:0;padding:20px;font-family:'SF Mono',Monaco,Consolas,monospace;font-size:15px;line-height:1.65;color:#e2e8f0;overflow-x:auto;white-space:pre}
          
          /* Capabilities Section - Card Grid */
          .capabilities{padding:60px 24px;max-width:1300px;margin:0 auto;background:#fff}
          .capabilities .section-header{margin-bottom:40px}
          .capabilities-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;max-width:1100px;margin:0 auto}
          .capability-card{background:#fff;border:2px solid #e5e7eb;border-radius:16px;padding:28px 24px;transition:all .25s;cursor:default}
          .capability-card:hover{border-color:#d1f470;color:#1a3a2a;background:#fbfff0;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}
          .cap-icon{width:52px;height:52px;background:#fff;border:1px solid #e5e7eb;border-radius:12px;display:flex;align-items:center;justify-content:center;margin-bottom:20px;padding:10px}
          .cap-icon img{width:100%;height:100%;object-fit:contain}
          .capability-card h3{font-size:22px;font-weight:700;line-height:1.27;letter-spacing:-.25px;color:#000;margin:0 0 10px}
          .capability-card:hover h3{color:#1a3a2a}
          .capability-card p{font-size:20px;color:rgba(0,0,0,.898);line-height:1.4;letter-spacing:-.125px;font-weight:400;margin:0}
          
          /* Why sits on plain white between the two grey canvases; borders and
             body text use the shared hairline/muted pair, not near-miss greens. */
          .why-section{padding:60px 24px;background:#fff}
          .why-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;max-width:1100px;margin:0 auto}
          .why-item{background:#fff;border:1px solid #e5e7eb;border-radius:16px;padding:24px;display:flex;flex-direction:column;gap:8px}
          .why-item strong{font-size:22px;font-weight:700;line-height:1.27;letter-spacing:-.25px;color:#000}
          .why-item span{font-size:20px;color:rgba(0,0,0,.898);line-height:1.4;letter-spacing:-.125px;font-weight:400}

          /* ========== TABLET (768px - 1024px) ========== */
          @media(max-width:1024px){
            
            .hero{padding:110px 20px 60px}
            .hero-content{grid-template-columns:1fr;gap:40px;text-align:left}
            .hero-left h1{letter-spacing:-1.8px;max-width:760px;margin:0 0 20px}
            .hero-left p{max-width:520px;margin:0 0 28px}
            
            .mockup-wrapper{max-width:480px;aspect-ratio:1.15;margin:0;padding:20px}
            .phone{left:16px;top:16px;width:52%}
            .code-box{right:auto;left:12px;bottom:16px;width:55%}
            
            .section-header{padding:0 20px}
            
            .trust-strip{padding:16px 20px 0}
            .trust-grid{grid-template-columns:1fr;gap:28px}
            .trust-content{align-items:flex-start}

            .touchpoint{padding:50px 20px}
            .usecase-pills{gap:10px}
            .pill{padding:12px 22px;font-size:14px}
            
            .api{padding:50px 20px}
            .api-grid{grid-template-columns:1fr;gap:36px;text-align:left}
            .api-info h2{text-align:left}
            .api-desc{max-width:100%;text-align:left}
            .api-demo{max-width:500px;margin:0}
            
            .capabilities{padding:50px 20px}
            .capabilities-grid{grid-template-columns:repeat(2,1fr);gap:16px}
            .capability-card{padding:24px 20px}
            .cap-icon{width:40px;height:40px;font-size:18px;margin-bottom:16px}
            
            .why-section{padding:50px 20px}
            .why-grid{grid-template-columns:1fr}
          }

          /* ========== MOBILE (up to 767px) ========== */
          @media(max-width:767px){
            
            .hero{padding:calc(115px + env(safe-area-inset-top)) 20px 50px}
            .hero-content{display:flex;flex-direction:column;gap:32px;text-align:left;align-items:flex-start}
            .hero-right{order:-1;width:100%;display:flex;justify-content:center}
            .hero-left{text-align:left;order:1}
            .hero-left h1{letter-spacing:-1.2px;margin:0 0 20px;line-height:1.1;max-width:100%;text-align:left}
            .hero-left p{margin:0 0 16px;max-width:100%;text-align:left}
            
            .trust-strip{margin:0 auto 20px;padding:16px 20px 0}
            .trust-grid{grid-template-columns:1fr;gap:24px}
            .trust-card{padding:36px 24px;gap:20px;max-width:100%}
            .trust-mark{width:46px;height:46px}
            .trust-wordmark{font-size:32px}
            .trust-pills{gap:10px}

            .mockup-wrapper{display:flex;flex-direction:column;gap:14px;width:100%;max-width:380px;margin:8px auto 0;aspect-ratio:auto;padding:16px;background:#fff;border-radius:16px;border:2px solid #e5e7eb;align-items:flex-start;transition:all .25s;cursor:default}
            .mockup-wrapper:hover{border-color:#d1f470;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}
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
            .code-header{padding:14px 16px}
            .dots{gap:6px}
            .dot-red,.dot-yellow,.dot-green{width:12px;height:12px}
            .file-name{font-size:15px}
            .code-body{font-size:15px;padding:16px;line-height:1.6;text-align:left}
            
            .section-header{margin-bottom:28px;padding:0 20px;text-align:center}
            .section-header h2{margin-bottom:12px;line-height:1.15;text-align:center}
            .section-header p{text-align:center}
            
            .touchpoint{padding:44px 20px}
            .usecase-pills{justify-content:center;gap:12px;flex-wrap:wrap;padding:0;margin:0}
            .pill{padding:14px 26px;font-size:20px}
            
            .api{padding:44px 20px}
            .api-grid{gap:36px;text-align:left}
            .api-info{text-align:left}
            .api-info h2{margin-bottom:16px;text-align:left}
            .api-desc{max-width:100%;text-align:left}
            .api-demo{border-radius:14px;max-width:100%;margin:0}
            .code-tabs{padding:16px;gap:10px;justify-content:flex-start;flex-wrap:wrap}
            .tab{padding:14px 24px;font-size:18px}
            .code-block{font-size:14px;padding:18px;min-height:auto;text-align:left;white-space:pre-wrap;word-break:break-word;overflow-x:visible;line-height:1.7}
            
            .capabilities{padding:44px 20px}
            .capabilities .section-header{margin-bottom:24px}
            .capabilities-grid{grid-template-columns:repeat(2,1fr);gap:14px}
            .capability-card{padding:22px 18px;border-radius:14px;text-align:left}
            .cap-icon{width:50px;height:50px;margin-bottom:16px;border-radius:12px;padding:10px}
            .capability-card h3{margin-bottom:8px;text-align:left}
            .capability-card p{text-align:left}
            
            .why-section{padding:44px 20px}
            .why-item{padding:20px}
          }

          /* ========== SMALL MOBILE (up to 480px) ========== */
          @media(max-width:480px){
            
            .hero{padding:calc(85px + env(safe-area-inset-top)) 16px 44px}
            .hero-left h1{letter-spacing:-1px;line-height:1.12}
            
            .section-header{padding:0 16px}
            .trust-strip{padding:16px 16px 0}
            .trust-card{padding:30px 20px}
            .trust-mark{width:42px;height:42px}
            .gos-closer{padding:64px 20px 76px}
            .gos-closer-head{letter-spacing:-1.4px;line-height:1.1}
            .trust-wordmark{font-size:30px}

            .mockup-wrapper{padding:14px;border-radius:14px;gap:12px;max-width:100%}
            .phone{border-radius:14px}
            .phone-header{padding:12px 14px}
            .avatar{width:38px;height:38px;font-size:16px}
            .contact-name{font-size:17px}
            .chat-area{min-height:170px;padding:12px 10px}
            .msg{font-size:16px;padding:10px 12px}
            
            .code-box{border-radius:12px}
            .code-body{font-size:14px;padding:14px}
            
            .touchpoint{padding:36px 16px}
            .usecase-pills{gap:10px}
            .pill{padding:12px 20px;font-size:18px}
            
            .api{padding:36px 16px}
            .api-info h2{text-align:left}
            .api-desc{text-align:left}
            .code-tabs{gap:8px;padding:14px}
            .tab{padding:12px 20px;font-size:17px}
            .code-block{font-size:14px;padding:16px;min-height:auto;text-align:left;white-space:pre-wrap;word-break:break-word;overflow-x:visible;line-height:1.65}
            
            .capabilities{padding:36px 16px}
            .capabilities-grid{grid-template-columns:1fr;gap:12px}
            .capability-card{padding:20px 18px;border-radius:12px;text-align:left}
            .cap-icon{width:48px;height:48px;margin-bottom:14px;padding:9px}
            .capability-card h3{text-align:left}
            .capability-card p{text-align:left}
            
          }
          
          /* ========== VERY SMALL SCREENS (up to 360px) ========== */
          @media(max-width:360px){
            
            .hero{padding:calc(80px + env(safe-area-inset-top)) 14px 36px}
            .hero-left h1{letter-spacing:-.8px}
            
            .pill{padding:12px 18px;font-size:17px}
          }
          
          /* ========== LANDSCAPE ORIENTATION FIX ========== */
          @media(max-height:500px) and (orientation:landscape){
            .hero{padding:90px 24px 40px}
            .hero-content{flex-direction:row;gap:24px;text-align:left}
            .hero-right{order:0;flex:1}
            .hero-left{order:0;flex:1;text-align:left}
            .hero-left h1{margin:0 0 16px}
            .hero-left p{margin:0 0 20px}
            .mockup-wrapper{max-height:260px;aspect-ratio:auto;max-width:100%}
            .phone{max-width:180px}
            .code-box{max-width:200px}
            .chat-area{min-height:120px}
          }

          /* ========== TYPOGRAPHY CONTRACT ========== */
          /* One responsive type hierarchy, declared after the legacy breakpoint
             rules so a single clamp() governs each size at every width. The hero
             h1 and p are intentionally absent: their base rule is the contract. */
          .section-header h2{font-size:clamp(32px,4.2vw,54px);line-height:1.04;letter-spacing:-1.875px}
          .section-header p{font-size:20px;line-height:1.4;letter-spacing:-.125px}
          .pill{font-size:var(--text-base)}
          .api-info h2{font-size:clamp(32px,4.2vw,54px);line-height:1.04;letter-spacing:-1.875px}
          .api-desc{font-size:20px;line-height:1.4;letter-spacing:-.125px}
          .tab{font-size:15px}
          .capability-card h3{font-size:22px;line-height:1.27;letter-spacing:-.25px}
          .capability-card p{font-size:20px;line-height:1.4;letter-spacing:-.125px}
          
          /* ========== REDUCED MOTION ========== */
          @media(prefers-reduced-motion:reduce){
            .anim{transition:none}
            .typing-indicator span{animation:none}
            .pill{transition:none}
          }

          /* ========== FULL-BLEED SECTIONS (pp-*) ==========
             The grey canvases have to reach both window edges, so the 1300px
             measure moves off the section and onto .pp-inner: 100vw plus a
             centring negative margin makes the tint exactly window.innerWidth
             wide, where a plain background would stop short of each edge.
             .page already clips overflow-x, so this adds no horizontal scroll.
             Everything here is pp- prefixed because the globally imported
             src/styles/*.css declares unscoped rules for generic names like
             .pill / .stat / .phone / .chat-area that styled-jsx cannot shield
             the page from; the id selectors beat the shared section classes
             regardless of source order. */
          #touchpoint,#capabilities{max-width:none;width:100vw;margin-left:calc(50% - 50vw);background:#fafafa}
          .pp-inner{max-width:1300px;margin:0 auto}

          /* Use-case pills as spans, since they carry no handler. Same paint as
             .pill; inline-flex restores the centring a button gets for free. */
          .pp-pill{display:inline-flex;align-items:center;justify-content:center;min-height:32px;padding:14px 28px;border:2px solid #e5e7eb;background:#fff;border-radius:50px;font-size:var(--text-base);font-weight:600;cursor:default;transition:all .25s;color:#4b5563}
          .pp-pill:hover{border-color:#d1f470;color:#1a3a2a;background:#fbfff0;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}

          @media(max-width:1024px){
            .pp-pill{padding:12px 22px}
          }
          @media(max-width:767px){
            .pp-pill{padding:14px 26px}
          }
          @media(max-width:480px){
            .pp-pill{padding:12px 20px}
          }
          @media(max-width:360px){
            .pp-pill{padding:12px 18px}
          }
          @media(prefers-reduced-motion:reduce){
            .pp-pill{transition:none}
          }
        `}</style>
      </div>
    </>
  );
};

export default GrahakOsPage;
