/**
 * TEMPORARY DESIGN MOCK — Notion visual language
 * Route: /grahak-os/mock-notion/
 *
 * Standalone design exploration of the Grahak OS product page rendered in the
 * visual language measured from notion.com: pure white canvas, near-monochrome
 * palette, very large tightly-tracked centered display type, one soft lime
 * accent, small radii (4-8px) and generous vertical whitespace.
 *
 * Content is identical to src/pages/grahak-os/index.tsx — only the visual
 * language differs. Do not link this page from navigation; it is noindex.
 *
 * TWO IMPLEMENTATION NOTES
 * 1. Every element lives inside this single component function on purpose.
 *    `<style jsx>` is scoped per component, so factoring markup into child
 *    components would silently drop all of these styles.
 * 2. Every class name carries an `mn-` prefix. The repo's global stylesheets
 *    (src/styles/*.css, imported in _app.tsx) define unscoped rules for
 *    generic names like `.stat-label`, `.btn-primary`, `.sep` and `.pill`;
 *    those leak in and win on properties this file does not redeclare (an
 *    unprefixed `.stat-label` here inherited `text-transform:uppercase`).
 *    The prefix keeps the mock isolated from that cascade.
 */

import React from 'react';
import Head from 'next/head';

const MockNotionPage: React.FC = () => {
  const useCases = [
    { title: 'Promotional', desc: 'Campaigns that land where customers already are' },
    { title: 'Transactional', desc: 'Receipts, alerts and confirmations in real time' },
    { title: 'Appointments', desc: 'Reminders that cut no-shows' },
    { title: 'OTPs', desc: 'Verification delivered in seconds' },
    { title: 'Orders', desc: 'Status updates from checkout to doorstep' },
    { title: 'Surveys', desc: 'Feedback collected in the conversation' },
  ];

  const capabilities = [
    { title: 'Customer Data Platform', desc: 'One profile across every channel' },
    { title: 'Custom Data Modeling', desc: 'Model customers, events and business objects' },
    { title: 'Multichannel Orchestration', desc: 'Coordinate WhatsApp, SMS, Email and Voice' },
    { title: 'Smart Personalization', desc: 'Trigger messages from customer behavior' },
    { title: 'Enterprise Infrastructure', desc: 'Secure APIs built to scale' },
    { title: 'Predictive Analytics', desc: 'Turn engagement signals into actionable insights' },
  ];

  const pythonExample = `import requests

response = requests.post(
  "https://api.wecare.digital/v1/messages",
  headers={
    "Authorization": "Bearer API_KEY"
  },
  json={
    "to": "+919330994400",
    "type": "template"
  }
)`;

  const channels = [ 'WhatsApp', 'SMS', 'Email', 'Voice' ];

  return (
    <>
      <Head>
        <title>Mock — Notion style | Grahak OS design exploration</title>
        <meta name="robots" content="noindex" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="description" content="Temporary design mock of the Grahak OS page in a Notion-inspired visual language." />
      </Head>

      <div className="mn-page">
        <div className="mn-banner">MOCK — NOTION STYLE</div>

        {/* ---------- HERO ---------- */}
        <section className="mn-hero" id="hero">
          <span className="mn-eyebrow">Grahak OS by WECARE.DIGITAL</span>
          <h1>
            Reach customers across{ ' ' }
            <span className="mn-highlight"><i className="mn-word-dot" aria-hidden="true" />WhatsApp</span>, SMS, Email &amp; Voice
          </h1>
          <p className="mn-lede">
            Grahak OS unifies customer data, messaging, automation and campaigns in one customer engagement platform.
          </p>
          <div className="mn-hero-actions">
            <button type="button" className="mn-cta-solid">Get started</button>
            <button type="button" className="mn-cta-quiet">Request a demo</button>
          </div>

          <div className="mn-stats">
            <div className="mn-stat">
              <span className="mn-stat-num">4 Channels</span>
              <span className="mn-stat-cap">WhatsApp, SMS, Email, Voice</span>
            </div>
            <div className="mn-stat">
              <span className="mn-stat-num">Fast</span>
              <span className="mn-stat-cap">Onboarding</span>
            </div>
            <div className="mn-stat">
              <span className="mn-stat-num">Secure</span>
              <span className="mn-stat-cap">APIs &amp; customer engagement</span>
            </div>
          </div>

          {/* Monochrome "logo wall" row — plain gray text with dot separators,
              the way Notion sets its client logos. */}
          <div className="mn-wall" aria-label="Channels">
            { channels.map( ( channel, i ) => (
              <React.Fragment key={ channel }>
                { i > 0 && <span className="mn-wall-sep" aria-hidden="true" /> }
                <span className="mn-wall-word">{ channel }</span>
              </React.Fragment>
            ) ) }
          </div>
        </section>

        {/* ---------- USE CASES ---------- */}
        <section className="mn-usecases" id="usecases">
          <div className="mn-head">
            <h2>Every touchpoint<br />One seamless experience</h2>
            <p>Engage, support, and convert customers across their entire journey — from first contact to lasting loyalty</p>
          </div>

          <div className="mn-wall mn-wall-tight" aria-label="Use cases">
            { useCases.map( ( item, i ) => (
              <React.Fragment key={ item.title }>
                { i > 0 && <span className="mn-wall-sep" aria-hidden="true" /> }
                <span className="mn-wall-word">{ item.title }</span>
              </React.Fragment>
            ) ) }
          </div>

          <div className="mn-grid">
            { useCases.map( ( item ) => (
              <div className="mn-card" key={ item.title }>
                <span className="mn-bullet" aria-hidden="true" />
                <h3>{ item.title }</h3>
                <p>{ item.desc }</p>
              </div>
            ) ) }
          </div>
        </section>

        {/* ---------- API ---------- */}
        <section className="mn-api" id="api">
          <div className="mn-head">
            <h2>Built for your stack</h2>
            <p>
              Use Grahak OS through its own customer engagement workspace or connect your stack through
              secure APIs for messaging, customer data, automation and campaigns.
            </p>
          </div>

          <div className="mn-code">
            <div className="mn-code-top">
              <span className="mn-code-lang">Python</span>
              <span className="mn-code-name">send_message.py</span>
            </div>
            <pre className="mn-code-pre">{ pythonExample }</pre>
          </div>
        </section>

        {/* ---------- CAPABILITIES ---------- */}
        <section className="mn-capabilities" id="capabilities">
          <div className="mn-head">
            <h2>Everything you need<br />to grow customer relationships</h2>
            <p>AI-powered lifecycle management that delivers results</p>
          </div>

          <div className="mn-grid">
            { capabilities.map( ( cap ) => (
              <div className="mn-card" key={ cap.title }>
                <span className="mn-bullet" aria-hidden="true" />
                <h3>{ cap.title }</h3>
                <p>{ cap.desc }</p>
              </div>
            ) ) }
          </div>
        </section>

        {/* ---------- TRUST ---------- */}
        <section className="mn-trust" id="trust" aria-label="Trusted by Meta">
          <span className="mn-trust-badge">OFFICIAL META TECH PARTNER</span>
          <h2>Trusted by Meta</h2>
          <p className="mn-trust-sub">
            Customer engagement across WhatsApp, SMS, Email &amp; Voice — powered by Grahak OS.
          </p>

          <div className="mn-trust-card">
            { /* eslint-disable-next-line @next/next/no-img-element */ }
            <img
              className="mn-trust-mark"
              src="https://app.wecare.digital/stream/media/m/meta-icon.svg"
              alt="Meta"
              width={ 44 }
              height={ 44 }
              loading="lazy"
            />
            <span className="mn-trust-word">Meta</span>
            <span className="mn-trust-rule" />
            <span className="mn-trust-cap">Meta Tech Partner</span>
          </div>

          <div className="mn-trust-pills">
            { channels.map( ( channel ) => (
              <span className="mn-chip" key={ channel }>{ channel }</span>
            ) ) }
          </div>
        </section>

        {/* ---------- CTA ---------- */}
        <section className="mn-cta" id="cta">
          <h2>Transform customer engagement with Grahak OS</h2>
          <p>One operating layer for customer data, orchestration and every channel your customers use.</p>
          <button type="button" className="mn-cta-solid">Get started</button>
        </section>

        <style jsx>{ `
          /* ===== Notion language: pure white, near-monochrome, one lime accent ===== */
          .mn-page{
            background:#ffffff;
            color:rgba(0,0,0,.95);
            font-family:var(--font-sans,'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif);
            -webkit-font-smoothing:antialiased;
            overflow-x:hidden;
          }

          /* Temp identifier badge. Sits above the global fixed Header
             (z-index 1001) so the mock is named from the very top. */
          .mn-banner{
            position:fixed;top:10px;left:50%;transform:translateX(-50%);
            z-index:1002;
            background:#111111;color:#ffffff;
            font-size:11px;font-weight:600;letter-spacing:1.2px;
            padding:7px 13px;border-radius:4px;
            white-space:nowrap;pointer-events:none;
          }

          /* ===== HERO ===== */
          .mn-hero{
            /* global fixed Header is 108px desktop — stay clear of it */
            padding:150px 24px 110px;
            max-width:1020px;margin:0 auto;
            text-align:center;
            display:flex;flex-direction:column;align-items:center;
          }
          .mn-eyebrow{
            display:inline-block;
            font-size:13px;font-weight:600;letter-spacing:.9px;text-transform:uppercase;
            color:#9ca3af;margin-bottom:26px;
          }
          .mn-hero h1{
            font-size:clamp(48px,7vw,96px);
            font-weight:600;
            letter-spacing:-4.6px;
            line-height:1.03;
            color:rgba(0,0,0,.95);
            margin:0 0 28px;
            max-width:960px;
            text-align:center;
          }
          /* Signature Notion move: one word wrapped in a soft lime pill with a dot */
          .mn-highlight{
            display:inline-block;
            background:#eaf9c0;
            border-radius:14px;
            padding:0 .22em 0 .16em;
            white-space:nowrap;
          }
          .mn-word-dot{
            display:inline-block;
            width:.28em;height:.28em;
            background:#d1f470;
            border-radius:50%;
            margin-right:.22em;
            vertical-align:.18em;
          }
          .mn-lede{
            font-size:clamp(18px,1.6vw,20px);
            line-height:1.55;
            color:#6b7280;
            margin:0 0 36px;
            max-width:660px;
            text-align:center;
          }
          .mn-hero-actions{display:flex;gap:12px;flex-wrap:wrap;justify-content:center;margin-bottom:64px}

          .mn-cta-solid{
            background:#d1f470;color:#1a3a2a;
            border:none;border-radius:8px;
            font-size:15px;font-weight:600;
            padding:13px 22px;cursor:pointer;
            font-family:inherit;text-transform:none;letter-spacing:normal;
            transition:filter .18s ease;
          }
          .mn-cta-solid:hover{filter:brightness(.96)}
          .mn-cta-quiet{
            background:#ffffff;color:rgba(0,0,0,.8);
            border:1px solid #e5e7eb;border-radius:8px;
            font-size:15px;font-weight:600;
            padding:13px 22px;cursor:pointer;
            font-family:inherit;text-transform:none;letter-spacing:normal;
            transition:border-color .18s ease;
          }
          .mn-cta-quiet:hover{border-color:#d1d5db}

          .mn-stats{
            display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
            gap:16px;width:100%;max-width:820px;
          }
          .mn-stat{
            border:1px solid #e5e7eb;border-radius:6px;
            padding:26px 22px;
            display:flex;flex-direction:column;gap:6px;align-items:center;
            background:#ffffff;
          }
          .mn-stat-num{
            font-size:22px;font-weight:600;letter-spacing:-.6px;
            color:rgba(0,0,0,.95);white-space:nowrap;text-transform:none;
          }
          .mn-stat-cap{
            font-size:14px;color:#9ca3af;line-height:1.4;
            text-align:center;text-transform:none;letter-spacing:normal;
          }

          /* Grayscale logo-wall row, dot separated — monochrome by design */
          .mn-wall{
            display:flex;align-items:center;justify-content:center;
            flex-wrap:wrap;gap:14px;
            margin-top:56px;
          }
          .mn-wall-tight{margin:0 0 64px}
          .mn-wall-word{
            font-size:15px;font-weight:500;letter-spacing:.3px;
            color:#9ca3af;text-transform:none;
          }
          .mn-wall-sep{
            width:4px;height:4px;border-radius:50%;
            background:#d1d5db;display:inline-block;
          }

          /* ===== SECTION SHELL ===== */
          .mn-usecases,.mn-api,.mn-capabilities,.mn-trust,.mn-cta{
            background:#ffffff;
            max-width:1080px;margin:0 auto;
            padding:110px 24px;
            display:flex;flex-direction:column;align-items:center;
          }
          .mn-head{
            max-width:760px;text-align:center;
            display:flex;flex-direction:column;align-items:center;
            margin-bottom:56px;
          }
          .mn-head h2{
            font-size:clamp(34px,4.4vw,58px);
            font-weight:600;letter-spacing:-2.4px;line-height:1.08;
            color:rgba(0,0,0,.95);margin:0 0 18px;
            text-align:center;
          }
          .mn-head p{
            font-size:clamp(18px,1.5vw,20px);
            line-height:1.55;color:#6b7280;margin:0;text-align:center;
          }

          /* ===== 3-COLUMN CARD GRID (use cases + capabilities) ===== */
          .mn-grid{
            display:grid;grid-template-columns:repeat(3,minmax(0,1fr));
            gap:18px;width:100%;
          }
          .mn-card{
            border:1px solid #e5e7eb;border-radius:8px;
            padding:34px 30px 38px;
            background:#ffffff;
            display:flex;flex-direction:column;
            transition:border-color .18s ease;
          }
          .mn-card:hover{border-color:#d1d5db}
          .mn-bullet{
            width:10px;height:10px;border-radius:50%;
            background:#d1f470;display:block;margin-bottom:24px;
          }
          .mn-card h3{
            font-size:18px;font-weight:600;letter-spacing:-.4px;
            color:rgba(0,0,0,.95);margin:0 0 10px;line-height:1.3;
          }
          .mn-card p{
            font-size:15px;line-height:1.6;color:#6b7280;margin:0;
          }

          /* ===== CODE BLOCK (light theme to match the restraint) ===== */
          .mn-code{
            width:100%;max-width:760px;
            background:#fafafa;
            border:1px solid #e5e7eb;border-radius:8px;
            overflow:hidden;
          }
          .mn-code-top{
            display:flex;align-items:center;gap:12px;
            padding:12px 18px;
            border-bottom:1px solid #e5e7eb;
            background:#ffffff;
          }
          .mn-code-lang{
            font-size:12px;font-weight:600;letter-spacing:.4px;
            color:#1a3a2a;background:#eaf9c0;
            padding:4px 10px;border-radius:4px;
          }
          .mn-code-name{
            margin-left:auto;font-size:13px;color:#9ca3af;
            font-family:'SF Mono',Monaco,Consolas,monospace;
          }
          .mn-code-pre{
            margin:0;padding:24px 22px;
            font-family:'SF Mono',Monaco,Consolas,monospace;
            font-size:14px;line-height:1.7;
            color:#111827;
            background:#fafafa;
            overflow-x:auto;white-space:pre;
          }

          /* ===== TRUST ===== */
          .mn-trust-badge{
            display:inline-block;
            background:#eaf9c0;color:#1a3a2a;
            font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase;
            padding:7px 14px;border-radius:4px;margin-bottom:24px;
          }
          .mn-trust h2{
            font-size:clamp(34px,4.4vw,58px);
            font-weight:600;letter-spacing:-2.4px;line-height:1.08;
            color:rgba(0,0,0,.95);margin:0 0 18px;text-align:center;
          }
          .mn-trust-sub{
            font-size:clamp(18px,1.5vw,20px);line-height:1.55;
            color:#6b7280;margin:0 0 44px;max-width:640px;text-align:center;
          }
          .mn-trust-card{
            border:1px solid #e5e7eb;border-radius:8px;
            padding:40px 44px;
            display:flex;flex-direction:column;align-items:center;gap:18px;
            background:#ffffff;width:100%;max-width:400px;
          }
          .mn-trust-mark{width:44px;height:44px;object-fit:contain}
          .mn-trust-word{
            font-size:30px;font-weight:600;letter-spacing:-1.2px;
            color:rgba(0,0,0,.95);
          }
          .mn-trust-rule{width:100%;height:1px;background:#e5e7eb;display:block}
          .mn-trust-cap{font-size:15px;font-weight:500;color:#6b7280;text-transform:none}
          .mn-trust-pills{display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin-top:36px}
          .mn-chip{
            border:1px solid #e5e7eb;border-radius:6px;
            padding:9px 18px;font-size:14px;font-weight:500;color:#6b7280;
            background:#ffffff;text-transform:none;
          }

          /* ===== CTA ===== */
          .mn-cta{padding:110px 24px 130px;text-align:center}
          .mn-cta h2{
            font-size:clamp(34px,4.6vw,62px);
            font-weight:600;letter-spacing:-2.6px;line-height:1.06;
            color:rgba(0,0,0,.95);margin:0 0 20px;max-width:840px;text-align:center;
          }
          .mn-cta p{
            font-size:clamp(18px,1.5vw,20px);line-height:1.55;
            color:#6b7280;margin:0 0 32px;max-width:600px;text-align:center;
          }

          /* ===== RESPONSIVE ===== */
          @media(max-width:1024px){
            .mn-hero{padding:132px 20px 90px}
            .mn-hero h1{letter-spacing:-2.6px}
            .mn-usecases,.mn-api,.mn-capabilities,.mn-trust,.mn-cta{padding:80px 20px}
            .mn-cta{padding:80px 20px 100px}
            .mn-head h2,.mn-trust h2,.mn-cta h2{letter-spacing:-1.6px}
            .mn-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
          }
          @media(max-width:767px){
            .mn-hero{padding:128px 20px 72px}
            .mn-hero h1{letter-spacing:-1.6px;line-height:1.08}
            .mn-stats{grid-template-columns:1fr}
            .mn-grid{grid-template-columns:1fr}
            .mn-head{margin-bottom:40px}
            .mn-code-pre{font-size:13px}
            .mn-banner{font-size:10px;padding:6px 10px}
          }
        ` }</style>
      </div>
    </>
  );
};

export default MockNotionPage;
