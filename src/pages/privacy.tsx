import React from 'react';
import Head from 'next/head';
import RotatingHero, { type CycleWord } from '../components/RotatingHero';

/**
 * /privacy — privacy policy.
 *
 * DELIBERATELY NOT IN THE NAV. The owner asked for this page to exist without a menu
 * entry, so it is absent from COLUMNS in Header.tsx on purpose - do not "fix" that by
 * adding it. It is still in the EXACT-MATCH allowlist in _app.tsx, which is what makes
 * it reachable at all: without that entry it would render an empty body with HTTP 200.
 * trailingSlash means the URL is /privacy/.
 *
 * Unlinked is not the same as private. Anyone with the URL can read it, and it is in
 * the static export. The noindex below is what keeps it out of search while the text
 * is a placeholder.
 *
 * THE POLICY TEXT IS DELIBERATELY NOT WRITTEN, for the same reason as /terms. A
 * privacy policy makes representations about what data is collected, where it is
 * stored and who it is shared with - this repo alone touches Cognito, DynamoDB, S3,
 * Secrets Manager, Google Translate, Amazon Polly, Meta and Wix. Inventing that
 * inventory would be a false statement of fact, not a draft. Fill POLICY_SECTIONS
 * with approved text and the placeholder disappears.
 */

// "Your data, your choice / control / consent / rights" - all four complete the frame,
// all 6 to 7 characters so the pill barely moves. Tints reused verbatim from the
// Grahak OS hero; no new colours.
const CYCLE_WORDS: CycleWord[] = [
  { word: 'choice', tint: '#dbeafe', dot: '#2563eb' },
  { word: 'control', tint: '#fef3c7', dot: '#f0a818' },
  { word: 'consent', tint: '#e0f7c8', dot: '#3da35a' },
  { word: 'rights', tint: '#ede9fe', dot: '#9849e8' },
];

/** Populate with the approved text. Empty renders the pending notice. */
const POLICY_SECTIONS: Array<{ heading: string; body: string }> = [];

const PrivacyPage: React.FC = () => (
  <>
    <Head>
      <title>Privacy — WECARE.DIGITAL</title>
      <meta name="description" content="How WECARE.DIGITAL handles your data." />
      <link rel="canonical" key="canonical" href="https://stack.wecare.digital/privacy/" />
      {/* noindex while the text is a placeholder. An indexed empty privacy policy is
          the document a regulator or an app store would be pointed at. Remove this
          when POLICY_SECTIONS is filled. */}
      { !POLICY_SECTIONS.length && <meta name="robots" content="noindex,nofollow" /> }
    </Head>
    <RotatingHero
      ariaLabel="Privacy policy"
      badgeLabel="Legal — WECARE.DIGITAL"
      frame="Your data, your"
      words={ CYCLE_WORDS }
      sub="What we collect, why we collect it, and how to ask us to change or delete it."
    >
      <section className="lg-body" aria-label="Privacy policy">
        { POLICY_SECTIONS.length
          ? POLICY_SECTIONS.map( section => (
            <div key={ section.heading } className="lg-section">
              <h2 className="lg-heading">{ section.heading }</h2>
              <p className="lg-text">{ section.body }</p>
            </div>
          ) )
          : (
            <div className="lg-pending">
              <h2 className="lg-heading">Not published yet</h2>
              <p className="lg-text">
                This policy is being prepared and does not yet describe our data
                handling. It makes no representations. For a data request in the
                meantime, reach us through the Selfservice portal.
              </p>
            </div>
          ) }
        <style jsx>{`
          /* lg- prefixed, matching /terms. Section h2 is the contract's 700 rung,
             heavier than the hero h1's 600 - intentional across the site. */
          .lg-body{max-width:700px;display:flex;flex-direction:column;gap:32px}
          .lg-section,.lg-pending{display:flex;flex-direction:column;gap:12px}
          .lg-heading{
            font-size:clamp(28px,3.2vw,40px);font-weight:700;line-height:1.08;
            letter-spacing:-1.2px;color:rgba(0,0,0,.95);margin:0;
          }
          .lg-text{
            font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;
            color:rgba(0,0,0,.898);margin:0;
          }
        `}</style>
      </section>
    </RotatingHero>
  </>
);

export default PrivacyPage;
