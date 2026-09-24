/**
 * RetiredUrl - a published URL that was deleted, kept answering.
 *
 * WHY THIS EXISTS. Commit a8d6a6c2 (#20) removed /selfservice and /product-page/*. Those
 * addresses had already gone out to customers: amplify/functions/ai/ai-generate-response
 * uses /selfservice as the "Start Now" / "Book Slot" / "Upload Now" button URL on outbound
 * WhatsApp messages, and there are 99 references to it and 27 to /product-page/partner-up
 * still in this repo. Repointing those handlers only fixes future sends - a message already
 * delivered cannot be recalled, so the URL has to resolve for as long as those messages
 * exist in people's chat history. Today it 301s to the trailing-slash form and then 404s.
 *
 * WHY NOT A REAL 301. That is the correct fix and it is not available here:
 * next.config.js sets output:'export' in production, and Next's `redirects` config is
 * ignored by a static export. Amplify Hosting redirects are console-managed, so they
 * cannot be committed. This component is the fix that ships with the code; a CDN-level
 * 301 should still be added and would make this obsolete.
 *
 * THREE LAYERS, because each one fails in a different situation:
 *   1. meta refresh 0  - works with JavaScript disabled, and Google treats a zero-delay
 *                        refresh as a redirect rather than as content.
 *   2. router.replace  - instant for anyone with JS, and `replace` rather than `push` so
 *                        the dead URL does not sit in history where Back would re-enter it.
 *   3. a visible link  - the honest fallback. If both of the above are blocked the reader
 *                        still sees where to go instead of a blank page.
 *
 * robots is noindex,follow: noindex keeps a contentless stub out of the index, follow lets
 * a crawler pass through to the destination. rel=canonical names the successor so any
 * signal attached to the old address consolidates there. These routes are deliberately
 * absent from scripts/generate-sitemap.js - a sitemap should not invite a crawler to a
 * page whose only purpose is to leave - and absent from PUBLIC_PAGE_META, which would
 * otherwise emit a WebPage entity advertising a stub as a destination. They are listed in
 * RETIRED_ROUTES in _app.tsx, which is what makes them render instead of shipping an empty
 * body with HTTP 200.
 */

import { useEffect } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

const SITE = 'https://wecare.digital';

interface RetiredUrlProps {
  /** Canonical destination, with the trailing slash next.config.js requires. */
  to: string;
  /** What the old address was, in the reader's terms - not the path. */
  was: string;
}

export default function RetiredUrl( { to, was }: RetiredUrlProps ) {
  const router = useRouter();

  useEffect( () => {
    // replace, not push: the retired URL must not stay in session history, or Back
    // lands the reader straight back on it and bounces them forward again.
    router.replace( to );
  }, [ router, to ] );

  return (
    <>
      <Head>
        {/* This page owns its whole head. _app.tsx suppresses the sitewide Head for
            RETIRED_ROUTES, so there is nothing here to collide with and no key needed. */}
        <title>Moved | WECARE.DIGITAL</title>
        <meta name="robots" content="noindex, follow" />
        <meta httpEquiv="refresh" content={ `0;url=${to}` } />
        <link rel="canonical" href={ `${SITE}${to}` } />
      </Head>
      <main className="ru">
        <p className="ru-eyebrow">Moved</p>
        <h1 className="ru-h1">{ was } is now here.</h1>
        <p className="ru-lead">
          Taking you there now. If nothing happens, use the link below.
        </p>
        <a className="ru-cta" href={ to }>Continue</a>
        <style jsx>{ `
          /* Sized to sit inside the public shell's 108px header offset without fighting
             it, and centred because there is nothing else on the page to align to. */
          .ru{
            max-width:640px;margin:0 auto;padding:96px 24px 120px;
            font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
            text-align:center;
          }
          /* The site's documented eyebrow rung: 12px/700/.08em uppercase. */
          .ru-eyebrow{
            margin:0 0 14px;font-size:12px;font-weight:700;
            letter-spacing:.08em;text-transform:uppercase;color:#1a3a2a;
          }
          /* The shared section rung - clamp(28px,3.2vw,40px)/700/1.08/-1.2px - rather than
             a hero size. This is a notice, not a landing page. */
          .ru-h1{
            margin:0 0 16px;
            font-size:clamp(28px,3.2vw,40px);font-weight:700;line-height:1.08;
            letter-spacing:-1.2px;color:rgba(0,0,0,.95);
          }
          /* The one body level: 20px/400/1.4/-.125px. */
          .ru-lead{
            margin:0 0 32px;
            font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;
            color:rgba(0,0,0,.898);
          }
          /* Same lime pill as .home-close-cta, including the 52px min-height. */
          .ru-cta{
            display:inline-flex;align-items:center;min-height:52px;
            padding:0 28px;border:2px solid #d1f470;border-radius:50px;
            background:#d1f470;color:#1a3a2a;font-size:17px;font-weight:600;
            text-decoration:none;transition:background-color .2s,box-shadow .2s,transform .2s;
          }
          .ru-cta:hover{background:#fff;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}
          .ru-cta:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:3px}
          @media(prefers-reduced-motion:reduce){
            .ru-cta,.ru-cta:hover{transition:none;transform:none}
          }
        ` }</style>
      </main>
    </>
  );
}
