/**
 * VayuLok public product page
 * Bharat Air Intelligence, by Bharat Stack
 *
 * DELIBERATELY SPARSE. The structure, routing, type ladder and palette are
 * finished; the product copy is not, because nothing in this repository describes
 * what VayuLok does. Writing capability claims, data sources or coverage numbers
 * here would be inventing them, and this page is public. The two strings that came
 * from the owner - the badge and the closing mark - are the only product claims
 * present, and the rest of the canvas is ready for approved copy.
 *
 * The same reasoning left src/pages/index.tsx a scaffold, and a test pins it that
 * way until the design is decided.
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
        <section className="vl-hero">
          {/* Same component as the Grahak OS hero and the home page, so the three
              pills cannot drift apart. Wrapper carries the spacing because
              styled-jsx cannot style a composite component from here. */}
          <div className="vl-eyebrow">
            <BrandBadge label="VayuLok by Bharat Stack" />
          </div>

          <h1 className="vl-head">VayuLok</h1>

          {/* Owner's own words only. Everything beyond this line needs approved
              copy - see the note at the top of the file. */}
          <p className="vl-lede">Air intelligence for Bharat, built on the Bharat Stack.</p>
        </section>

        {/* Approved copy lands here. The canvas below is intentionally empty rather
            than filled with placeholder marketing, so nothing unverified ships. */}

        <section className="vl-closer" aria-label="Bharat Air Intelligence">
          <p className="vl-mark">Bharat Air Intelligence</p>
        </section>
      </div>
    </main>

    <style jsx>{`
      /* Header is fixed at 108px, 96px under 767px - the same offsets the home
         page uses, so the two public shells start at the same place. */
      .vl-shell{min-height:calc(100vh - 69px);padding-top:108px;box-sizing:border-box;background:#fff}
      .vl-layout{width:100%;max-width:1300px;margin:0 auto;padding:80px 24px 96px;box-sizing:border-box;display:flex;flex-direction:column;gap:96px}

      .vl-hero{display:flex;flex-direction:column;align-items:flex-start}
      /* Spacing only. The badge paints itself inside BrandBadge. */
      .vl-eyebrow{margin:0 0 20px}

      /* Type ladder, straight from the design contract. h1 is 600 and the section
         level is 700 - heavier than the h1 - which is notion's inversion and is
         intentional. Do not "correct" it. */
      .vl-head{font-size:clamp(36px,4.3vw,60px);font-weight:600;line-height:1.04;letter-spacing:-2.2px;color:rgba(0,0,0,.95);margin:0 0 24px}
      /* The single body level: 20px / 400 / 1.4 / -.125px. There is exactly one on
         a public page, so do not add a second size here. */
      .vl-lede{font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;color:rgba(0,0,0,.898);margin:0;max-width:520px}

      .vl-closer{display:flex;justify-content:flex-start}
      /* Section level, matching .section-header h2 and .gos-closer-head on the
         Grahak OS page so the two closers read as one family. */
      .vl-mark{font-size:clamp(32px,4.2vw,54px);font-weight:700;line-height:1.04;letter-spacing:-1.875px;color:rgba(0,0,0,.95);margin:0}

      @media(max-width:1024px){
        .vl-layout{gap:80px}
      }
      @media(max-width:767px){
        .vl-shell{min-height:calc(100vh - 85px);padding-top:96px}
        .vl-layout{padding:48px 20px 64px;gap:64px}
        .vl-head{letter-spacing:-1.2px;line-height:1.1}
        .vl-mark{letter-spacing:-1.4px;line-height:1.1}
      }
      @media(max-width:480px){
        .vl-layout{padding:40px 16px 56px}
        .vl-head{letter-spacing:-.8px}
      }
    `}</style>
  </>
);

export default VayuLokPage;
