/**
 * MOCK / PREVIEW PAGE — NOT PUBLIC, NOT INDEXED.
 *
 * This route exists ONLY so design options can be seen in a real browser before any
 * change is applied to the live public pages. It is deliberately:
 *   - absent from the isPublic allowlist in _app.tsx  (so it is not a public route)
 *   - absent from the sitemap allowlist in scripts/generate-sitemap.js
 *   - absent from the header mega-menu
 *   - marked <meta name="robots" content="noindex,nofollow">
 *
 * Because it is NOT in the isPublic allowlist, _app.tsx renders it behind the
 * Authenticator — you will be asked to sign in to view it, which is exactly what we
 * want for an internal preview: no anonymous visitor can reach it.
 *
 * WHAT IT SHOWS: the home page's closing-band list (and the flow list beside it) are
 * the elements that currently mismatch — section 2's list bodies are grey
 * (rgba(0,0,0,.54)) while section 3's list items are dark green (#1a3a2a). This page
 * renders the SAME list three ways so a single option can be chosen. Nothing here is
 * wired to the real pages; picking an option is a conversation, not a deploy.
 *
 * DELETE THIS FILE once the design is finalized.
 */
import React from 'react';
import Head from 'next/head';

interface PageProps { signOut?: () => void; user?: any }

// The three closing-band list items, verbatim from src/pages/index.tsx today.
const CLOSE_POINTS = [
  'Know the price before you commit.',
  'Tell us once. We remember the context.',
  'See where everything stands.',
];

// The three flow beats, verbatim from src/pages/index.tsx today.
const FLOW_BEATS = [
  { strong: 'Pick up where you left off.', body: 'What you’ve already shared stays connected, so the next thing you need isn’t a fresh start.' },
  { strong: 'Updates find you.', body: 'Updates reach you wherever you already are.' },
  { strong: 'Follow-ups happen automatically.', body: 'If something fails or needs chasing, we chase it. You don’t have to.' },
];

const MockHome: React.FC<PageProps> = () => {
  return (
    <>
      <Head>
        <title>MOCK — home design options (internal)</title>
        <meta name="robots" content="noindex,nofollow" />
      </Head>
      <main className="mk-shell">
        <div className="mk-wrap">
          <header className="mk-top">
            <span className="mk-tag">INTERNAL PREVIEW · not a public page</span>
            <h1 className="mk-h1">Home page — closing-band list options</h1>
            <p className="mk-note">
              The two lists on the home page use different body colours today. Below, the
              same list is shown three ways. Tell me the letter (A / B / C) you want, and
              I&apos;ll apply only that one to the real page.
            </p>
          </header>

          {/* ============================================================= */}
          {/* CURRENT — what the live home page renders right now.          */}
          {/* ============================================================= */}
          <section className="mk-block mk-current">
            <div className="mk-label">CURRENT (live today) — the mismatch</div>
            <div className="mk-two">
              <div className="mk-col">
                <div className="mk-sub">Section 2 — flow list</div>
                <ul className="mk-flow">
                  { FLOW_BEATS.map( b => (
                    <li key={ b.strong }>
                      <strong>{ b.strong }</strong>
                      <span className="c-grey">{ b.body }</span>
                    </li>
                  ) ) }
                </ul>
                <p className="mk-hint">body colour: grey rgba(0,0,0,.54)</p>
              </div>
              <div className="mk-col">
                <div className="mk-sub">Section 3 — closing list</div>
                <ul className="mk-close">
                  { CLOSE_POINTS.map( p => (
                    <li key={ p } className="c-green">{ p }</li>
                  ) ) }
                </ul>
                <p className="mk-hint">item colour: green #1a3a2a</p>
              </div>
            </div>
          </section>

          {/* ============================================================= */}
          {/* OPTION A — both lists on neutral body colour .898             */}
          {/* ============================================================= */}
          <section className="mk-block">
            <div className="mk-label">OPTION A — unify to neutral body <b>rgba(0,0,0,.898)</b></div>
            <div className="mk-two">
              <div className="mk-col">
                <div className="mk-sub">Section 2 — flow list</div>
                <ul className="mk-flow">
                  { FLOW_BEATS.map( b => (
                    <li key={ b.strong }>
                      <strong>{ b.strong }</strong>
                      <span className="c-898">{ b.body }</span>
                    </li>
                  ) ) }
                </ul>
              </div>
              <div className="mk-col">
                <div className="mk-sub">Section 3 — closing list</div>
                <ul className="mk-close">
                  { CLOSE_POINTS.map( p => (
                    <li key={ p } className="c-898">{ p }</li>
                  ) ) }
                </ul>
              </div>
            </div>
            <p className="mk-hint">Both lists read as the same body text. Neutral, calm, matches the leads above each section.</p>
          </section>

          {/* ============================================================= */}
          {/* OPTION B — both lists on brand green #1a3a2a                  */}
          {/* ============================================================= */}
          <section className="mk-block">
            <div className="mk-label">OPTION B — unify to brand green <b>#1a3a2a</b></div>
            <div className="mk-two">
              <div className="mk-col">
                <div className="mk-sub">Section 2 — flow list</div>
                <ul className="mk-flow">
                  { FLOW_BEATS.map( b => (
                    <li key={ b.strong }>
                      <strong>{ b.strong }</strong>
                      <span className="c-green">{ b.body }</span>
                    </li>
                  ) ) }
                </ul>
              </div>
              <div className="mk-col">
                <div className="mk-sub">Section 3 — closing list</div>
                <ul className="mk-close">
                  { CLOSE_POINTS.map( p => (
                    <li key={ p } className="c-green">{ p }</li>
                  ) ) }
                </ul>
              </div>
            </div>
            <p className="mk-hint">Both lists read as brand-green claims. Stronger, more on-brand, but heavier on the eye.</p>
          </section>

          {/* ============================================================= */}
          {/* OPTION C — both lists on muted grey .54                       */}
          {/* ============================================================= */}
          <section className="mk-block">
            <div className="mk-label">OPTION C — unify to muted grey <b>rgba(0,0,0,.54)</b></div>
            <div className="mk-two">
              <div className="mk-col">
                <div className="mk-sub">Section 2 — flow list</div>
                <ul className="mk-flow">
                  { FLOW_BEATS.map( b => (
                    <li key={ b.strong }>
                      <strong>{ b.strong }</strong>
                      <span className="c-grey">{ b.body }</span>
                    </li>
                  ) ) }
                </ul>
              </div>
              <div className="mk-col">
                <div className="mk-sub">Section 3 — closing list</div>
                <ul className="mk-close">
                  { CLOSE_POINTS.map( p => (
                    <li key={ p } className="c-grey">{ p }</li>
                  ) ) }
                </ul>
              </div>
            </div>
            <p className="mk-hint">Both lists read as quiet, secondary text. Lightest option — recedes the most.</p>
          </section>
        </div>
      </main>

      <style jsx>{`
        .mk-shell{
          min-height:100vh;padding:120px 24px 80px;background:#fff;
          font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
          color:#1a1a1a;
        }
        .mk-wrap{max-width:1000px;margin:0 auto;display:flex;flex-direction:column;gap:40px}

        .mk-top{display:flex;flex-direction:column;gap:12px}
        .mk-tag{align-self:flex-start;padding:6px 12px;border-radius:9999px;background:#fef3c7;color:#78350f;font-size:12px;font-weight:700;letter-spacing:.04em}
        .mk-h1{margin:0;font-size:clamp(28px,3.2vw,40px);font-weight:700;line-height:1.08;letter-spacing:-1.2px;color:rgba(0,0,0,.95)}
        .mk-note{margin:0;max-width:60ch;font-size:18px;line-height:1.5;color:rgba(0,0,0,.7)}

        .mk-block{border:1px solid #e5e7eb;border-radius:16px;padding:28px}
        .mk-current{border-color:#f0a818;background:#fffdf7}
        .mk-label{font-size:13px;font-weight:700;letter-spacing:.04em;color:#1a3a2a;margin-bottom:20px;text-transform:uppercase}
        .mk-label b{color:#000}

        .mk-two{display:grid;grid-template-columns:1fr 1fr;gap:32px}
        .mk-col{min-width:0}
        .mk-sub{font-size:12px;font-weight:600;color:rgba(0,0,0,.42);margin-bottom:14px;letter-spacing:.03em}

        /* Flow list — same shape as .home-flow-list on the real page. */
        .mk-flow{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:18px}
        .mk-flow li{padding-left:18px;border-left:3px solid #d1f470}
        .mk-flow strong{display:block;margin:0 0 6px;font-size:20px;font-weight:700;letter-spacing:-.25px;line-height:1.27;color:#000}
        .mk-flow span{display:block;font-size:17px;font-weight:400;line-height:1.4;letter-spacing:-.125px}

        /* Closing list — same shape as .home-close-points on the real page. */
        .mk-close{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:12px}
        .mk-close li{position:relative;padding-left:26px;font-size:17px;font-weight:400;line-height:1.4;letter-spacing:-.125px}
        .mk-close li::before{content:'';position:absolute;left:2px;top:6px;width:11px;height:6px;border-left:2.5px solid #1a3a2a;border-bottom:2.5px solid #1a3a2a;transform:rotate(-45deg)}

        /* The three colour treatments under test. */
        .c-grey{color:rgba(0,0,0,.54)}
        .c-898{color:rgba(0,0,0,.898)}
        .c-green{color:#1a3a2a}

        .mk-hint{margin:18px 0 0;font-size:14px;color:rgba(0,0,0,.54);line-height:1.5}

        @media(max-width:767px){
          .mk-two{grid-template-columns:1fr;gap:24px}
          .mk-shell{padding:100px 16px 60px}
        }
      `}</style>
    </>
  );
};

export default MockHome;
