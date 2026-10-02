/**
 * Unknown paths retain the owner's home fallback. Retired staff and legacy URLs
 * stay on this unavailable page instead, with the CDN's HTTP 404 and no automatic
 * navigation. Current public pages and /workspace routes resolve before this page.
 */
import React, { useEffect } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

export const RETIRED_PATH_PREFIXES = [
  '/access', '/dm', '/engage', '/dashboard', '/contacts', '/commerce', '/pay',
  '/forms', '/service', '/docs', '/seo', '/admin', '/link', '/task', '/settings',
  '/swdhya', '/no-fault', '/legal-stuff', '/legal-stuffs', '/faq', '/my-order',
  '/expoweek', '/ritual-store', '/swdhya-store', '/request-tracking', '/rx-slot',
  '/bring-friends', '/home', '/open-possibility', '/product-page/partner',
  '/selfservice', '/track',
];

const NotFoundRedirect: React.FC = () => {
  const router = useRouter();

  useEffect( () => {
    // Match whole path segments, so /contacts never blocks the public /contact page.
    let requestedPath = window.location.pathname;
    try { requestedPath = decodeURIComponent( requestedPath ); } catch { /* Keep the raw path. */ }
    requestedPath = requestedPath.toLowerCase();
    if ( RETIRED_PATH_PREFIXES.some( prefix =>
      requestedPath === prefix || requestedPath.startsWith( `${prefix}/` )
    ) ) return;
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
          <p className="nf-sub">This page is unavailable.</p>
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
