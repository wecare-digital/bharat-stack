/**
 * TEMPORARY DESIGN MOCK — WhatsApp Business visual language
 * Route: /grahak-os/mock-whatsapp/
 *
 * Standalone design exploration of the Grahak OS product page rendered in the
 * visual language measured from business.whatsapp.com: dominant dark forest
 * green canvas (#103529), bright mint display type (#4ade80), left-aligned
 * hero with a chat mockup on the right, pale mint (#dff5e1) accent bands
 * alternating with the dark sections, ~12px radii and bright green buttons.
 *
 * Content is identical to src/pages/grahak-os/index.tsx — only the visual
 * language differs. Do not link this page from navigation; it is noindex.
 *
 * FONT NOTE: WhatsApp ships a proprietary typeface ("WhatsApp Sans Var") that
 * cannot be licensed or self-hosted here, so this mock uses Inter (already
 * loaded globally as --font-sans). Weight and tracking are tuned to approximate
 * the original.
 *
 * TWO IMPLEMENTATION NOTES
 * 1. Every element lives inside this single component function on purpose.
 *    `<style jsx>` is scoped per component, so factoring markup into child
 *    components would silently drop all of these styles.
 * 2. Every class name carries an `mw-` prefix. The repo's global stylesheets
 *    (src/styles/*.css, imported in _app.tsx) define unscoped rules for
 *    generic names like `.chat-area`, `.contact-name`, `.btn-primary` and
 *    `.stat-label`; those leak in and win on properties this file does not
 *    redeclare. The prefix keeps the mock isolated from that cascade.
 */

import React from 'react';
import Head from 'next/head';

const MockWhatsAppPage: React.FC = () => {
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

  // Four-point-star "sparkle" accent, drawn inline so nothing external loads.
  const sparkle = (
    <svg viewBox="0 0 100 100" aria-hidden="true" focusable="false">
      <path
        d="M50 0 C54 34 66 46 100 50 C66 54 54 66 50 100 C46 66 34 54 0 50 C34 46 46 34 50 0 Z"
        fill="#4ade80"
      />
    </svg>
  );

  return (
    <>
      <Head>
        <title>Mock — WhatsApp style | Grahak OS design exploration</title>
        <meta name="robots" content="noindex" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="description" content="Temporary design mock of the Grahak OS page in a WhatsApp Business-inspired visual language." />
      </Head>

      <div className="mw-page">
        <div className="mw-banner">MOCK — WHATSAPP STYLE</div>

        {/* ---------- HERO (dark forest green, two columns) ---------- */}
        <section className="mw-hero" id="hero">
          <div className="mw-hero-inner">
            <div className="mw-hero-copy">
              <span className="mw-eyebrow">Grahak OS by WECARE.DIGITAL</span>
              <h1>Reach customers across WhatsApp, SMS, Email &amp; Voice</h1>
              <p className="mw-lede">
                Grahak OS unifies customer data, messaging, automation and campaigns in one customer engagement platform.
              </p>
              <div className="mw-hero-actions">
                <button type="button" className="mw-cta-solid">Get started</button>
                <button type="button" className="mw-cta-line">Talk to sales</button>
              </div>
              <div className="mw-stats">
                <div className="mw-stat">
                  <span className="mw-stat-num">4 Channels</span>
                  <span className="mw-stat-cap">WhatsApp, SMS, Email, Voice</span>
                </div>
                <div className="mw-stat">
                  <span className="mw-stat-num">Fast</span>
                  <span className="mw-stat-cap">Onboarding</span>
                </div>
                <div className="mw-stat">
                  <span className="mw-stat-num">Secure</span>
                  <span className="mw-stat-cap">APIs &amp; customer engagement</span>
                </div>
              </div>
            </div>

            <div className="mw-hero-visual">
              <span className="mw-star mw-star-a">{ sparkle }</span>
              <span className="mw-star mw-star-b">{ sparkle }</span>
              <span className="mw-star mw-star-c">{ sparkle }</span>

              <div className="mw-phone">
                <div className="mw-phone-bar">
                  <div className="mw-phone-avatar">W</div>
                  <div className="mw-phone-who">
                    <span className="mw-phone-name">WECARE.DIGITAL</span>
                    <span className="mw-phone-state">online</span>
                  </div>
                  <span className="mw-phone-tick" aria-hidden="true" />
                </div>
                <div className="mw-chat">
                  <div className="mw-bubble mw-out">
                    <p>Hi! Your order #WD-ORD-87A6G has been shipped</p>
                    <span className="mw-stamp">10:30</span>
                  </div>
                  <div className="mw-bubble mw-in">
                    <p>When will it arrive?</p>
                    <span className="mw-stamp">10:31</span>
                  </div>
                  <div className="mw-bubble mw-out">
                    <p>Tomorrow by 6 PM</p>
                    <span className="mw-stamp">10:31</span>
                  </div>
                  <div className="mw-bubble mw-out">
                    <p>Track here: wecare.digital/track</p>
                    <span className="mw-stamp">10:32</span>
                  </div>
                  <div className="mw-typing" aria-hidden="true">
                    <span /><span /><span />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ---------- USE CASES (pale mint band) ---------- */}
        <section className="mw-band-mint mw-usecases" id="usecases">
          <div className="mw-wrap">
            <div className="mw-head">
              <h2>Every touchpoint<br />One seamless experience</h2>
              <p>Engage, support, and convert customers across their entire journey — from first contact to lasting loyalty</p>
            </div>
            <div className="mw-grid">
              { useCases.map( ( item ) => (
                <div className="mw-card mw-card-light" key={ item.title }>
                  <span className="mw-card-star" aria-hidden="true">{ sparkle }</span>
                  <h3>{ item.title }</h3>
                  <p>{ item.desc }</p>
                </div>
              ) ) }
            </div>
          </div>
        </section>

        {/* ---------- API (dark) ---------- */}
        <section className="mw-band-dark mw-api" id="api">
          <div className="mw-wrap mw-api-grid">
            <div className="mw-api-copy">
              <h2>Built for your stack</h2>
              <p>
                Use Grahak OS through its own customer engagement workspace or connect your stack through
                secure APIs for messaging, customer data, automation and campaigns.
              </p>
              <button type="button" className="mw-cta-solid">Read the API docs</button>
            </div>
            <div className="mw-code">
              <div className="mw-code-top">
                <span className="mw-code-lang">Python</span>
                <span className="mw-code-name">send_message.py</span>
              </div>
              <pre className="mw-code-pre">{ pythonExample }</pre>
            </div>
          </div>
        </section>

        {/* ---------- CAPABILITIES (dark, lighter green cards) ---------- */}
        <section className="mw-band-dark mw-capabilities" id="capabilities">
          <div className="mw-wrap">
            <div className="mw-head">
              <h2>Everything you need<br />to grow customer relationships</h2>
              <p>AI-powered lifecycle management that delivers results</p>
            </div>
            <div className="mw-grid">
              { capabilities.map( ( cap ) => (
                <div className="mw-card mw-card-deep" key={ cap.title }>
                  <span className="mw-card-star" aria-hidden="true">{ sparkle }</span>
                  <h3>{ cap.title }</h3>
                  <p>{ cap.desc }</p>
                </div>
              ) ) }
            </div>
          </div>
        </section>

        {/* ---------- TRUST (pale mint band) ---------- */}
        <section className="mw-band-mint mw-trust" id="trust" aria-label="Trusted by Meta">
          <div className="mw-wrap mw-trust-grid">
            <div className="mw-trust-copy">
              <span className="mw-trust-badge">OFFICIAL META TECH PARTNER</span>
              <h2>Trusted by Meta</h2>
              <p className="mw-trust-sub">
                Customer engagement across WhatsApp, SMS, Email &amp; Voice — powered by Grahak OS.
              </p>
              <div className="mw-trust-pills">
                { channels.map( ( channel ) => (
                  <span className="mw-chip" key={ channel }>{ channel }</span>
                ) ) }
              </div>
            </div>
            <div className="mw-trust-card">
              { /* eslint-disable-next-line @next/next/no-img-element */ }
              <img
                className="mw-trust-mark"
                src="https://app.wecare.digital/stream/media/m/meta-icon.svg"
                alt="Meta"
                width={ 52 }
                height={ 52 }
                loading="lazy"
              />
              <span className="mw-trust-word">Meta</span>
              <span className="mw-trust-rule" />
              <span className="mw-trust-cap">Meta Tech Partner</span>
            </div>
          </div>
        </section>

        {/* ---------- CTA (dark) ---------- */}
        <section className="mw-band-dark mw-cta" id="cta">
          <div className="mw-wrap mw-cta-inner">
            <span className="mw-star mw-star-cta">{ sparkle }</span>
            <h2>Transform customer engagement with Grahak OS</h2>
            <p>One operating layer for customer data, orchestration and every channel your customers use.</p>
            <button type="button" className="mw-cta-solid">Get started</button>
          </div>
        </section>

        <style jsx>{ `
          /* ===== WhatsApp Business language: dark forest green + bright mint =====
             Inter stands in for the proprietary WhatsApp Sans Var. */
          .mw-page{
            background:#103529;
            color:#ffffff;
            font-family:var(--font-sans,'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif);
            -webkit-font-smoothing:antialiased;
            overflow-x:hidden;
          }

          /* Temp identifier badge. Sits above the global fixed Header
             (z-index 1001) so the mock is named from the very top. */
          .mw-banner{
            position:fixed;top:10px;left:50%;transform:translateX(-50%);
            z-index:1002;
            background:#25d366;color:#0b241b;
            font-size:11px;font-weight:700;letter-spacing:1.2px;
            padding:7px 15px;border-radius:50px;
            white-space:nowrap;pointer-events:none;
          }

          .mw-wrap{max-width:1200px;margin:0 auto;width:100%}

          /* ===== Alternating bands ===== */
          .mw-band-dark{background:#103529;color:#ffffff}
          .mw-band-mint{background:#dff5e1;color:#103529}

          /* ===== HERO ===== */
          .mw-hero{
            background:#103529;
            /* global fixed Header is 108px desktop — stay clear of it */
            padding:150px 24px 96px;
          }
          .mw-hero-inner{
            max-width:1200px;margin:0 auto;
            display:grid;grid-template-columns:1.12fr .88fr;
            gap:52px;align-items:center;
          }
          .mw-hero-copy{text-align:left}
          .mw-eyebrow{
            display:inline-block;
            font-size:12px;font-weight:700;letter-spacing:1.4px;text-transform:uppercase;
            color:#4ade80;margin-bottom:20px;
          }
          .mw-hero h1{
            font-size:clamp(44px,6vw,76px);
            font-weight:700;
            line-height:1.05;
            letter-spacing:-1.8px;
            color:#4ade80;
            margin:0 0 24px;
            text-align:left;
          }
          .mw-lede{
            font-size:clamp(17px,1.5vw,20px);
            line-height:1.6;
            color:rgba(255,255,255,.88);
            margin:0 0 32px;max-width:540px;
          }
          .mw-hero-actions{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:40px}

          .mw-cta-solid{
            background:#25d366;color:#ffffff;
            border:none;border-radius:50px;
            font-size:15px;font-weight:700;
            padding:15px 30px;cursor:pointer;
            font-family:inherit;text-transform:none;letter-spacing:normal;
            transition:filter .18s ease;
          }
          .mw-cta-solid:hover{filter:brightness(1.06)}
          .mw-cta-line{
            background:transparent;color:#ffffff;
            border:1.5px solid rgba(255,255,255,.55);border-radius:50px;
            font-size:15px;font-weight:700;
            padding:15px 30px;cursor:pointer;
            font-family:inherit;text-transform:none;letter-spacing:normal;
            transition:border-color .18s ease,background .18s ease;
          }
          .mw-cta-line:hover{border-color:#4ade80;background:rgba(74,222,128,.1)}

          .mw-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;max-width:560px}
          .mw-stat{
            background:#17402f;
            border:1px solid rgba(74,222,128,.28);
            border-radius:12px;padding:16px 18px;
            display:flex;flex-direction:column;gap:5px;
          }
          .mw-stat-num{
            font-size:20px;font-weight:700;color:#4ade80;
            letter-spacing:-.4px;white-space:nowrap;text-transform:none;
          }
          .mw-stat-cap{
            font-size:13px;line-height:1.4;color:rgba(255,255,255,.75);
            text-transform:none;letter-spacing:normal;
          }

          /* ===== HERO VISUAL: CSS chat mockup + inline SVG sparkles ===== */
          .mw-hero-visual{
            position:relative;display:flex;
            justify-content:center;align-items:center;min-height:460px;
          }
          .mw-star{position:absolute;display:block;pointer-events:none;z-index:2}
          .mw-star :global(svg){width:100%;height:100%;display:block}
          .mw-star-a{width:64px;height:64px;top:8px;right:16px}
          .mw-star-b{width:34px;height:34px;top:96px;right:0}
          .mw-star-c{width:46px;height:46px;bottom:26px;left:4px}

          .mw-phone{
            position:relative;z-index:1;
            width:100%;max-width:340px;
            background:#ffffff;
            border-radius:12px;
            overflow:hidden;
            box-shadow:0 26px 60px rgba(0,0,0,.4);
          }
          .mw-phone-bar{
            background:#17402f;
            padding:13px 15px;
            display:flex;align-items:center;gap:11px;
          }
          .mw-phone-avatar{
            width:40px;height:40px;border-radius:50%;
            background:#25d366;color:#ffffff;
            display:flex;align-items:center;justify-content:center;
            font-weight:700;font-size:16px;flex:0 0 auto;
          }
          .mw-phone-who{flex:1;display:flex;flex-direction:column;min-width:0}
          .mw-phone-name{color:#ffffff;font-size:16px;font-weight:600;text-transform:none}
          .mw-phone-state{color:#4ade80;font-size:13px;text-transform:none}
          .mw-phone-tick{
            width:20px;height:20px;border-radius:50%;
            background:#4ade80;flex:0 0 auto;display:block;
          }
          .mw-chat{
            background:#ece5dd;
            padding:16px 13px;
            min-height:330px;
            display:flex;flex-direction:column;gap:9px;
          }
          .mw-bubble{
            max-width:82%;padding:9px 12px;border-radius:10px;
            font-size:14px;line-height:1.45;color:#0b141a;
          }
          .mw-bubble p{margin:0}
          .mw-in{background:#ffffff;align-self:flex-start;border-top-left-radius:3px}
          .mw-out{background:#d9fdd3;align-self:flex-end;border-top-right-radius:3px}
          .mw-stamp{font-size:11px;color:#667781;display:block;text-align:right;margin-top:3px}
          .mw-typing{
            background:#ffffff;padding:11px 14px;border-radius:10px;
            align-self:flex-start;display:flex;gap:4px;
          }
          .mw-typing span{
            width:7px;height:7px;border-radius:50%;background:#25d366;display:block;
            animation:mwbounce 1.4s infinite;
          }
          .mw-typing span:nth-child(2){animation-delay:.2s}
          .mw-typing span:nth-child(3){animation-delay:.4s}
          @keyframes mwbounce{0%,60%,100%{transform:translateY(0)}30%{transform:translateY(-3px)}}

          /* ===== SECTION SHELL ===== */
          .mw-usecases,.mw-api,.mw-capabilities,.mw-trust,.mw-cta{padding:104px 24px}
          .mw-head{max-width:760px;margin:0 0 52px}
          .mw-head h2{
            font-size:clamp(34px,4.2vw,54px);
            font-weight:700;line-height:1.08;letter-spacing:-1.4px;
            margin:0 0 16px;text-align:left;
          }
          .mw-head p{
            font-size:clamp(17px,1.4vw,19px);line-height:1.6;margin:0;max-width:640px;
          }
          .mw-band-mint .mw-head h2{color:#103529}
          .mw-band-mint .mw-head p{color:rgba(16,53,41,.78)}
          .mw-band-dark .mw-head h2{color:#4ade80}
          .mw-band-dark .mw-head p{color:rgba(255,255,255,.82)}

          /* ===== CARD GRID (use cases on mint, capabilities on dark) ===== */
          .mw-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}
          .mw-card{
            border-radius:12px;padding:30px 26px 34px;
            display:flex;flex-direction:column;
          }
          .mw-card-star{width:26px;height:26px;display:block;margin-bottom:20px}
          .mw-card-star :global(svg){width:100%;height:100%;display:block}
          .mw-card h3{font-size:19px;font-weight:700;margin:0 0 9px;line-height:1.3}
          .mw-card p{font-size:15px;line-height:1.6;margin:0}

          .mw-card-light{background:#ffffff;border:1px solid rgba(16,53,41,.12)}
          .mw-card-light h3{color:#103529}
          .mw-card-light p{color:rgba(16,53,41,.75)}

          .mw-card-deep{background:#17402f;border:1px solid rgba(74,222,128,.22)}
          .mw-card-deep h3{color:#ffffff}
          .mw-card-deep p{color:rgba(255,255,255,.78)}

          /* ===== API ===== */
          .mw-api-grid{display:grid;grid-template-columns:1fr 1fr;gap:52px;align-items:center}
          .mw-api-copy h2{
            font-size:clamp(32px,3.6vw,48px);font-weight:700;line-height:1.1;
            letter-spacing:-1.2px;color:#4ade80;margin:0 0 18px;text-align:left;
          }
          .mw-api-copy p{
            font-size:clamp(17px,1.4vw,19px);line-height:1.65;
            color:rgba(255,255,255,.82);margin:0 0 28px;
          }
          .mw-code{
            background:#0b241b;
            border:1px solid rgba(74,222,128,.24);
            border-radius:12px;overflow:hidden;
          }
          .mw-code-top{
            display:flex;align-items:center;gap:12px;
            padding:13px 18px;background:#17402f;
            border-bottom:1px solid rgba(74,222,128,.2);
          }
          .mw-code-lang{
            font-size:12px;font-weight:700;letter-spacing:.5px;
            color:#0b241b;background:#4ade80;
            padding:4px 12px;border-radius:50px;
          }
          .mw-code-name{
            margin-left:auto;font-size:13px;color:rgba(255,255,255,.62);
            font-family:'SF Mono',Monaco,Consolas,monospace;
          }
          .mw-code-pre{
            margin:0;padding:22px;
            font-family:'SF Mono',Monaco,Consolas,monospace;
            font-size:14px;line-height:1.7;
            color:#d9fdd3;overflow-x:auto;white-space:pre;
          }

          /* ===== TRUST (on mint) ===== */
          .mw-trust-grid{display:grid;grid-template-columns:1fr 1fr;gap:48px;align-items:center}
          .mw-trust-copy{display:flex;flex-direction:column;align-items:flex-start}
          .mw-trust-badge{
            display:inline-block;background:#103529;color:#4ade80;
            font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;
            padding:8px 16px;border-radius:50px;margin-bottom:20px;
          }
          .mw-trust h2{
            font-size:clamp(34px,4.2vw,54px);font-weight:700;line-height:1.08;
            letter-spacing:-1.4px;color:#103529;margin:0 0 16px;text-align:left;
          }
          .mw-trust-sub{
            font-size:clamp(17px,1.4vw,19px);line-height:1.6;
            color:rgba(16,53,41,.78);margin:0 0 28px;max-width:520px;
          }
          .mw-trust-pills{display:flex;flex-wrap:wrap;gap:10px}
          .mw-chip{
            background:#ffffff;border:1px solid rgba(16,53,41,.14);
            border-radius:50px;padding:10px 20px;
            font-size:14px;font-weight:600;color:#103529;text-transform:none;
          }
          .mw-trust-card{
            background:#103529;border:1px solid rgba(74,222,128,.3);
            border-radius:12px;padding:44px 36px;
            display:flex;flex-direction:column;align-items:center;gap:18px;
            width:100%;max-width:400px;margin:0 auto;
          }
          /* The hosted Meta mark is a dark glyph, so it needs a light tile to
             stay legible on the dark green trust card. */
          .mw-trust-mark{
            width:52px;height:52px;object-fit:contain;
            background:#ffffff;padding:9px;border-radius:12px;
            box-sizing:content-box;
          }
          .mw-trust-word{font-size:32px;font-weight:700;letter-spacing:-1px;color:#ffffff}
          .mw-trust-rule{width:100%;height:1px;background:rgba(74,222,128,.32);display:block}
          .mw-trust-cap{font-size:16px;font-weight:600;color:#4ade80;text-transform:none}

          /* ===== CTA ===== */
          .mw-cta{padding:110px 24px 126px}
          .mw-cta-inner{
            display:flex;flex-direction:column;align-items:flex-start;
            max-width:900px;margin:0 auto;
          }
          .mw-star-cta{width:52px;height:52px;position:static;margin-bottom:24px}
          .mw-cta h2{
            font-size:clamp(34px,4.6vw,60px);font-weight:700;line-height:1.06;
            letter-spacing:-1.6px;color:#4ade80;margin:0 0 18px;max-width:820px;text-align:left;
          }
          .mw-cta p{
            font-size:clamp(17px,1.4vw,19px);line-height:1.6;
            color:rgba(255,255,255,.85);margin:0 0 32px;max-width:600px;
          }

          /* ===== RESPONSIVE ===== */
          @media(max-width:1024px){
            .mw-hero{padding:130px 20px 76px}
            .mw-hero-inner{grid-template-columns:1fr;gap:48px}
            .mw-hero-visual{min-height:0;justify-content:flex-start}
            .mw-star-a{right:auto;left:300px;top:0}
            .mw-star-b{right:auto;left:356px;top:84px}
            .mw-star-c{left:auto;right:30px;bottom:10px}
            .mw-usecases,.mw-api,.mw-capabilities,.mw-trust,.mw-cta{padding:76px 20px}
            .mw-api-grid,.mw-trust-grid{grid-template-columns:1fr;gap:36px}
            .mw-trust-card{margin:0}
            .mw-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
            .mw-head{margin-bottom:40px}
          }
          @media(max-width:767px){
            .mw-hero{padding:126px 20px 64px}
            .mw-stats{grid-template-columns:1fr;max-width:100%}
            .mw-grid{grid-template-columns:1fr}
            .mw-hero-visual{justify-content:center}
            .mw-star{display:none}
            .mw-code-pre{font-size:13px}
            .mw-banner{font-size:10px;padding:6px 12px}
          }
        ` }</style>
      </div>
    </>
  );
};

export default MockWhatsAppPage;
