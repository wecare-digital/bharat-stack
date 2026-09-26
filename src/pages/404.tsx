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
 * Second, the CDN rule that sends mismatched paths home does not cover every case. Amplify's
 * last rule is `/<*>` -> `/index.html` with status 404-200 (see
 * scripts/provision_legacy_redirects.py), so a mistyped PATH already renders the home page.
 * What it does not catch is a direct request for /404/ itself, or a host or shell that
 * resolves its own not-found document - including the Capacitor WebView. This page covers
 * those by sending the visitor home itself.
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
          .nf-cta:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:3px}

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
