/**
 * VayuLok public product page
 * Bharat Air Intelligence, by Bharat Stack
 *
 * DELIBERATELY CLEAR. The page is the tag and the line beneath it, nothing else.
 * That is the owner's call, and it also happens to be the honest one: nothing in
 * this repository describes what VayuLok does - no features, no data sources, no
 * coverage, not even an internal doc - so any capability copy here would be
 * invented, on a public page. The two strings present both came from the owner.
 *
 * src/pages/index.tsx is a scaffold on the same principle, with a test pinning it
 * blank until its design is decided.
 *
 * "Bharat Air Intelligence" is the h1 rather than a tagline because it is now the
 * page's only heading, and a public page needs exactly one.
 *
 * ROUTING: _app.tsx keeps an EXACT-MATCH public route allowlist. '/vayulok' is
 * registered there. Without that entry this page would render an empty body with
 * HTTP 200 - a 404 that does not look like one. next.config.js also sets
 * trailingSlash, so the URL is /vayulok/ with the slash.
 *
 * Every class is vl- prefixed, following pp- on the Grahak OS page and ft- in the
 * Footer. The globally imported src/styles/*.css declares unscoped rules for
 * generic names, and styled-jsx does not shield a page from those.
 */

import React from 'react';
import Head from 'next/head';
import BrandBadge from '../../components/BrandBadge';

const VayuLokPage: React.FC = () => (
  <>
    <Head>
      <title>VayuLok by Bharat Stack</title>
      <meta name="description" content="VayuLok - Bharat Air Intelligence, by Bharat Stack." />
      <link rel="canonical" href="https://stack.wecare.digital/vayulok/" />
    </Head>

    <main className="vl-shell" aria-label="VayuLok">
      <div className="vl-layout">
        {/* Same component as the Grahak OS hero and the home page, so the three
            pills cannot drift apart. The wrapper carries the spacing because
            styled-jsx cannot style a composite component from here. */}
        <div className="vl-eyebrow">
          <BrandBadge label="VayuLok by Bharat Stack" />
        </div>

        <h1 className="vl-head">Bharat Air Intelligence</h1>
      </div>
    </main>

    <style jsx>{`
      /* Header is fixed at 108px, 96px under 767px - the same offsets the home
         page uses, so the two public shells start at the same place. */
      .vl-shell{min-height:calc(100vh - 69px);padding-top:108px;box-sizing:border-box;background:#fff}
      /* No flex gap here: the only gap that exists is the one under the badge, and
         .vl-eyebrow owns it. A column gap would apply to nothing and quietly
         mislead whoever adds the second element. */
      .vl-layout{width:100%;max-width:1300px;margin:0 auto;padding:80px 24px 96px;box-sizing:border-box}

      /* Spacing only. The badge paints itself inside BrandBadge. */
      .vl-eyebrow{margin:0 0 20px}

      /* Hero h1 level from the design contract: 600 weight, not the heavier 700 the
         section level uses. That inversion - section headings heavier than the h1 -
         is notion's and is intentional, so do not "correct" it here. */
      .vl-head{font-size:clamp(36px,4.3vw,60px);font-weight:600;line-height:1.04;letter-spacing:-2.2px;color:rgba(0,0,0,.95);margin:0;max-width:900px}

      @media(max-width:767px){
        .vl-shell{min-height:calc(100vh - 85px);padding-top:96px}
        .vl-layout{padding:48px 20px 64px}
        .vl-head{letter-spacing:-1.2px;line-height:1.1}
      }
      @media(max-width:480px){
        .vl-layout{padding:40px 16px 56px}
        .vl-head{letter-spacing:-.8px}
      }
    `}</style>
  </>
);

export default VayuLokPage;
