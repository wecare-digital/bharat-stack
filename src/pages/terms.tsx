import React from 'react';
import Head from 'next/head';
import RotatingHero, { type CycleWord } from '../components/RotatingHero';

/**
 * /terms — Terms of service.
 *
 * ROUTING: '/terms' must be in the EXACT-MATCH allowlist in _app.tsx or this renders
 * an empty body with HTTP 200. trailingSlash means the URL is /terms/.
 *
 * THE LEGAL TEXT IS DELIBERATELY NOT WRITTEN. This page ships the hero and a marked
 * placeholder, and nothing more. Drafting terms of service is a legal act with
 * consequences for refunds, liability and jurisdiction, and inventing plausible
 * clauses would produce a document that looks authoritative and binds nobody -
 * actively worse than an obvious gap. The copy has to come from the owner or their
 * counsel; drop it into LEGAL_SECTIONS below and the placeholder disappears.
 */

// "Terms of service / payment / refunds / delivery" - all four complete the frame, and
// all are 7 or 8 characters so the pill barely moves. Tints reused verbatim.
const CYCLE_WORDS: CycleWord[] = [
  { word: 'service', tint: '#dbeafe', dot: '#2563eb' },
  { word: 'payment', tint: '#fef3c7', dot: '#f0a818' },
  { word: 'refunds', tint: '#e0f7c8', dot: '#3da35a' },
  { word: 'delivery', tint: '#ede9fe', dot: '#9849e8' },
];

/** Populate with the approved text. Empty renders the pending notice. */
const LEGAL_SECTIONS: Array<{ heading: string; body: string }> = [];

const TermsPage: React.FC = () => (
  <>
    <Head>
      <title>Terms — WECARE.DIGITAL</title>
      <meta name="description" content="Terms of service for WECARE.DIGITAL." />
      <link rel="canonical" href="https://stack.wecare.digital/terms/" />
      {/* Not indexed while the text is a placeholder. An indexed empty terms page is
          worse than no terms page: it is the document a customer or a payment provider
          would be pointed at. Remove this when LEGAL_SECTIONS is filled. */}
      { !LEGAL_SECTIONS.length && <meta name="robots" content="noindex,nofollow" /> }
    </Head>
    <RotatingHero
      ariaLabel="Terms of service"
      badgeLabel="Legal — WECARE.DIGITAL"
      frame="Terms of"
      words={ CYCLE_WORDS }
      sub="The agreement between you and WECARE.DIGITAL when you use our services."
    >
      <section className="lg-body" aria-label="Terms of service">
        { LEGAL_SECTIONS.length
          ? LEGAL_SECTIONS.map( section => (
            <div key={ section.heading } className="lg-section">
              <h2 className="lg-heading">{ section.heading }</h2>
              <p className="lg-text">{ section.body }</p>
            </div>
          ) )
          : (
            <div className="lg-pending">
              <h2 className="lg-heading">Not published yet</h2>
              <p className="lg-text">
                These terms are being prepared and are not in force. Nothing on this
                page forms an agreement. For anything urgent, reach us through the
                Selfservice portal.
              </p>
            </div>
          ) }
        <style jsx>{`
          /* lg- prefixed. The globally imported src/styles/*.css declares unscoped
             rules for generic names, and styled-jsx does not shield a page from them.
             Section h2 is the contract's 700 rung - HEAVIER than the hero h1's 600.
             That inversion is intentional across the whole site. */
          .lg-body{max-width:700px;display:flex;flex-direction:column;gap:32px}
          .lg-section,.lg-pending{display:flex;flex-direction:column;gap:12px}
          .lg-heading{
            font-size:clamp(28px,3.2vw,40px);font-weight:700;line-height:1.08;
            letter-spacing:-1.2px;color:rgba(0,0,0,.95);margin:0;
          }
          /* The one body level: 20px/400/1.4/-.125px. */
          .lg-text{
            font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;
            color:rgba(0,0,0,.898);margin:0;
          }
        `}</style>
      </section>
    </RotatingHero>
  </>
);

export default TermsPage;
