/**
 * The 404 page.
 *
 * WHY THIS FILE EXISTS. There was no 404.tsx, so the export shipped Next's built-in one:
 * 6.8KB whose entire visible content is "404 This page could not be found." No header, no
 * footer, no support widget, no brand, and no link anywhere. A visitor who mistyped a URL
 * or followed a dead link landed in a dead end with no way back into the site and no way to
 * reach anyone. It was the only exported page in the whole build with none of the three
 * common pieces on it.
 *
 * IT IS REGISTERED IN isPublic, which is what actually fixes it. Header, Footer and
 * SupportWidget are mounted once in _app.tsx inside `if ( isPublic )`, so a page gets all
 * three by being on that list and by no other means. `/404` is added as a bare literal
 * rather than to PUBLIC_PAGE_META on purpose: META entries acquire WebPage structured data
 * and a sitemap entry, and advertising a 404 to a crawler is the opposite of the intent.
 *
 * HOW A 404 ACTUALLY REACHES A VISITOR HERE. Amplify's last rewrite rule sends unmatched
 * paths to /index.html with status 404-200, so most mistyped URLs render the home page with
 * a 404 status rather than this file. This page is what serves when that rule does not
 * apply - a direct request for /404/, and any host or shell that resolves its own not-found
 * document, including the Capacitor WebView. It has to stand on its own for that reason.
 *
 * noindex IS SET HERE AND MATTERS. The public branch of _app.tsx adds sitewide SEO to every
 * page on the list, including a canonical. next/head dedupes by key and a page's Head is
 * processed after _app's, so the robots tag below is additive and the canonical is
 * overridden rather than duplicated.
 */
import React from 'react';
import Head from 'next/head';

const NotFoundPage: React.FC = () => (
  <>
    <Head>
      <title>Page not found — WECARE.DIGITAL</title>
      <meta name="robots" content="noindex, follow" />
      {/* follow, not nofollow: the links out of this page lead back into the site, and
          there is no reason to stop a crawler using them. */}
      <link rel="canonical" key="canonical" href="https://wecare.digital/" />
    </Head>

    <main className="nf-shell">
      <div className="nf-in">
        <p className="nf-code" aria-hidden="true">404</p>
        <h1 className="nf-head">This page isn&rsquo;t here.</h1>
        <p className="nf-sub">
          The link may be old, or the address may have a typo in it. Everything else is
          still where you left it.
        </p>

        {/* Plain <a>, not next/link, for the reason recorded on the home page's CTA:
            styled-jsx only scopes lowercase DOM tags, so a capitalised component receives
            an unscoped class name and renders unstyled. On a trailingSlash export both
            resolve identically. */}
        <div className="nf-acts">
          <a className="nf-cta" href="/">Back to the home page</a>
          <a className="nf-alt" href="/contact/">Tell us what you were looking for</a>
        </div>
      </div>

      <style jsx>{`
        /* padding-top clears the fixed header, which is 108px and 96px below 768px - the
           same two values .home-shell carries. min-height uses dvh after vh so a phone
           browser sizes this to the viewport it actually shows, not the one it would show
           with the chrome hidden. */
        .nf-shell{
          min-height:100vh;
          min-height:100dvh;
          padding-top:108px;
          box-sizing:border-box;
          background:#fff;
          font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
          color:#1a1a1a;
          display:flex;
          align-items:center;
        }
        .nf-in{width:100%;max-width:1300px;margin:0 auto;padding:64px 24px 96px;box-sizing:border-box}

        /* The numeral is decoration, hence aria-hidden: the h1 already says what happened,
           and a screen reader announcing "404" before it adds nothing a visitor can use. */
        .nf-code{
          margin:0 0 10px;
          font-size:13px;font-weight:700;letter-spacing:.14em;
          color:#1a3a2a;
        }
        /* Same rung as the other public h1s: 600, lighter than the 700 section level, and
           tracking in em so it stays proportional as the size changes. */
        .nf-head{
          margin:0;
          font-size:clamp(32px,3.6vw,48px);
          font-weight:600;
          line-height:1.06;
          letter-spacing:-0.04em;
          color:rgba(0,0,0,.95);
          max-width:760px;
        }
        .nf-sub{
          margin:20px 0 0;
          font-size:18px;line-height:1.5;
          color:rgba(0,0,0,.6);
          max-width:520px;
        }

        .nf-acts{display:flex;flex-wrap:wrap;align-items:center;gap:14px 20px;margin:32px 0 0}
        /* The lime pill, matching .home-close-cta so the one action on this page looks like
           the one action on the home page. */
        .nf-cta{
          display:inline-flex;align-items:center;justify-content:center;
          min-height:52px;padding:0 28px;
          background:#d1f470;border:2px solid #d1f470;border-radius:50px;
          color:#1a3a2a;font-size:17px;font-weight:600;text-decoration:none;
          transition:background-color .2s,transform .2s;
        }
        .nf-cta:hover{background:#fff;transform:translateY(-1px)}
        .nf-cta:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:3px}

        /* The secondary action is a text link with the same lime underline sweep the footer
           tagline and the header menu rows use, so the three surfaces share one gesture. */
        .nf-alt{
          position:relative;
          color:rgba(0,0,0,.6);font-size:16px;text-decoration:none;
          transition:color .2s;
        }
        .nf-alt::after{
          content:'';position:absolute;left:0;right:0;bottom:-3px;height:2px;
          background:#d1f470;
          transform:scaleX(0);transform-origin:left center;
          transition:transform .2s cubic-bezier(.16,1,.3,1);
        }
        .nf-alt:hover{color:#1a3a2a}
        .nf-alt:hover::after{transform:scaleX(1)}
        .nf-alt:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:3px;border-radius:4px}

        @media(max-width:767px){
          .nf-shell{padding-top:96px}
          .nf-in{padding:40px 16px 64px}
          .nf-sub{font-size:17px}
        }
        @media(prefers-reduced-motion:reduce){
          .nf-cta,.nf-alt,.nf-alt::after{transition:none}
        }
      `}</style>
    </main>
  </>
);

export default NotFoundPage;
