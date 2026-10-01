/**
 * There is no 404 page. A mismatched URL goes to the home page.
 *
 * WHY THIS FILE STILL EXISTS IF THERE IS NO 404 PAGE. Two reasons, and neither is
 * decoration.
 *
 * First, the file is what stops Next shipping its own. With no src/pages/404.tsx the export
 * emitted Next's built-in shell - 6.8KB whose entire content is "404 This page could not be
 * found", with no header, no footer, no widget, no brand and ZERO links. A visitor who
 * mistyped a URL landed in a dead end with nothing to click. Deleting this file does not
 * remove a 404 page; it restores that one.
 *
 * Second, the CDN rule does not send a mismatched path home at all - THIS page does.
 *
 * CORRECTED IN PLACE 2026-10-01, measured against the live Amplify app (d22dm4b0jn71jw)
 * rather than read from a script. The paragraph here used to say: "Amplify's last rule is
 * `/<*>` -> `/index.html` with status 404-200, so a mistyped PATH already renders the home
 * page." Both halves were stale. The rule's TARGET changed to `/404.html` on 2026-09-28 (gap
 * SEO-404-001) precisely so that a mistyped URL receives THIS page's head - the `noindex` and
 * the canonical below - instead of the home page's. So the live behaviour is: a mistyped path
 * stays at the address the visitor typed, returns HTTP 404, and is served THIS document.
 * Nothing on the CDN renders the home page for it. Measured 2026-10-01:
 * `/definitely-not-a-page/` -> 404 carrying `"page":"/404"`.
 *
 * That makes the redirect below load-bearing rather than a long-tail safety net, and MORE so
 * since 2026-10-01: on that date the owner retired every custom redirect, taking the live rule
 * count from 146 to 8, so the ~150 legacy aliases that used to 301 to a real page now arrive
 * here instead - /swdhya/, /no-fault/, /legal-stuff/, /faq/, /my-order/ and the 15 former
 * top-level workspace prefixes among them, all measured at 404 on 2026-10-01. The one rule
 * deliberately kept is the host canonicalisation `https://www.wecare.digital` ->
 * `https://wecare.digital` at 301, which preserves the path and so never reaches this page.
 * See docs/execution/url-host-matrix-20261001.md for the measured rule array, and
 * docs/execution/url-redirect-removal-20261001.md for the removal itself.
 *
 * The cases the CDN rule genuinely cannot reach are unchanged: a direct request for /404/
 * itself, and any host or shell that resolves its own not-found document - including the
 * Capacitor WebView. This page covers those too.
 *
 * router.replace, NOT push: a redirect must not leave an entry in the history stack, or the
 * back button returns the visitor to the dead URL they were just rescued from and bounces
 * them forward again.
 *
 * WHAT RENDERS IN THE MEANTIME is a deliberate choice rather than a blank. The redirect needs
 * one tick of JavaScript, and with JavaScript unavailable it never runs at all - so the
 * markup below is the no-JS fallback, and it is a real link rather than a message about
 * being redirected. It also means the page is never empty: it is on the isPublic allowlist,
 * so it arrives with the header, the footer and the support widget already around it.
 *
 * A NOTE ON SUBDOMAINS, since the instruction covered them: a request to a subdomain that
 * does not exist never reaches this application. It fails at DNS, or at the CDN, before any
 * JavaScript or HTML of ours is involved. Sending wrong subdomains to the home page is a
 * Route 53 / Amplify domain-management change and cannot be done from this repository.
 */
import React, { useEffect } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

const NotFoundRedirect: React.FC = () => {
  const router = useRouter();

  useEffect( () => {
    void router.replace( '/' );
  }, [ router ] );

  return (
    <>
      <Head>
        <title>WECARE.DIGITAL</title>
        {/* noindex, follow. The page is a waypoint, so it should never be indexed - but the
            link out of it leads back into the site and there is no reason to stop a crawler
            using it. The canonical points at the destination, not at this URL, and overrides
            _app.tsx's computed one because next/head dedupes by key. */}
        <meta name="robots" content="noindex, follow" />
        <link rel="canonical" key="canonical" href="https://wecare.digital/" />
      </Head>

      <main className="nf-shell">
        <div className="nf-in">
          <p className="nf-sub">Taking you to the home page.</p>
          {/* A full document load, deliberately. This is the escape hatch from a route that
              does not exist, so the router's own state is the thing least worth trusting;
              and on a static export the anchor works with no JavaScript at all, which is
              the one property a 404 page should never give up. */}
          {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
          <a className="nf-cta" href="/">Go to WECARE.DIGITAL</a>
        </div>

        <style jsx>{`
          /* padding-top clears the fixed header - 108px, and 96px below 768px, the same two
             values the home page carries. min-height uses dvh after vh so a phone browser
             sizes this to the viewport it actually shows rather than the one it would show
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
          .nf-sub{margin:0 0 24px;font-size:18px;line-height:1.5;color:rgba(0,0,0,.6)}
          /* The lime pill, matching .home-close-cta, so the one action here looks like the
             one action on the home page. */
          .nf-cta{
            display:inline-flex;align-items:center;justify-content:center;
            min-height:52px;padding:0 28px;
            background:#d1f470;border:2px solid #d1f470;border-radius:50px;
            color:#1a3a2a;font-size:17px;font-weight:600;text-decoration:none;
            transition:background-color .2s,transform .2s;
          }
          .nf-cta:hover{background:#fff;transform:translateY(-1px)}
          .nf-cta:focus-visible{outline:3px solid #1a3a2a;outline-offset:3px}

          @media(max-width:767px){
            .nf-shell{padding-top:96px}
            .nf-in{padding:40px 16px 64px}
          }
          @media(prefers-reduced-motion:reduce){.nf-cta{transition:none}}
        `}</style>
      </main>
    </>
  );
};

export default NotFoundRedirect;
