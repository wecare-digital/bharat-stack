import React from 'react';
import Head from 'next/head';
import RotatingHero, { type CycleWord } from '../components/RotatingHero';

/**
 * /bharat-rx — the Bharat Rx product page.
 *
 * WHY THIS EXISTS: Bharat Rx was moved into the Products column of the mega menu but had
 * no page, so the row pointed at the generic Selfservice landing page. A product listed
 * beside Grahak OS and VayuLok and then landing somewhere unrelated is worse than not
 * listing it.
 *
 * ROUTING: '/bharat-rx' must be in the EXACT-MATCH allowlist in _app.tsx or this renders
 * an empty body with HTTP 200. trailingSlash means the URL is /bharat-rx/.
 *
 * COPY IS DELIBERATELY NON-COMMITTAL ABOUT CLINICAL CLAIMS. Nothing here states what Rx
 * dispenses, diagnoses or advises, because I do not know what the product actually does
 * and a health-adjacent product page is the wrong place to guess. It describes the shape
 * of the service - a request, a professional, a record - which is what the Terms already
 * support in sections 8 and 17. Replace this with the real proposition; it is marked and
 * easy to find.
 *
 * NO PRODUCT SCHEMA, ON PURPOSE. Grahak OS carries SoftwareApplication because it is a
 * real, describable product with a feature list. Marking this up the same way while the
 * copy is provisional would put claims into structured data that the page does not make -
 * and Google's guidelines require structured data to represent the page's actual content.
 * _app.tsx gives it a WebPage plus a breadcrumb, which is accurate.
 */

// All four words are 8 to 10 characters, so the pill barely travels. Tints and dots are
// reused verbatim from the Grahak OS hero - no new colours.
const CYCLE_WORDS: CycleWord[] = [
  { word: 'medicines', tint: '#e0f7c8', dot: '#3da35a' },
  { word: 'consults', tint: '#dbeafe', dot: '#2563eb' },
  { word: 'reminders', tint: '#fef3c7', dot: '#f0a818' },
  { word: 'records', tint: '#ede9fe', dot: '#9849e8' },
];

const SELFSERVICE = 'https://www.wecare.digital/selfservice';

const BharatRxPage: React.FC = () => (
  <>
    <Head>
      <title>Bharat Rx — WECARE.DIGITAL</title>
      <meta
        name="description"
        content="Bharat Rx by WECARE.DIGITAL — request medicines, consults, reminders and records in one place, with every request tracked end to end."
      />
      <link rel="canonical" key="canonical" href="https://wecare.digital/bharat-rx/" />
    </Head>
    <RotatingHero
      ariaLabel="Bharat Rx"
      badgeLabel="Bharat Rx by WECARE.DIGITAL"
      frame="One place for"
      words={ CYCLE_WORDS }
      sub="Requests go to a qualified professional, and every one is tracked end to end with transparent pricing."
    >
      <section className="brx" aria-label="About Bharat Rx">
        <h2 className="brx-h2">How it works</h2>
        <ol className="brx-steps">
          <li className="brx-step">
            <span className="brx-step-n">1</span>
            <div>
              <strong className="brx-step-t">Send a request</strong>
              <p className="brx-p">Describe what you need and attach anything relevant — a prescription, a photograph, a previous record.</p>
            </div>
          </li>
          <li className="brx-step">
            <span className="brx-step-n">2</span>
            <div>
              <strong className="brx-step-t">A professional reviews it</strong>
              <p className="brx-p">Requests that need a qualified opinion get one. What that involves depends on the request, and is set out in section 17 of the Terms.</p>
            </div>
          </li>
          <li className="brx-step">
            <span className="brx-step-n">3</span>
            <div>
              <strong className="brx-step-t">Track it to completion</strong>
              <p className="brx-p">Status, changes and history stay in one place, alongside every other request you have made.</p>
            </div>
          </li>
        </ol>

        <a className="brx-cta" href={ SELFSERVICE }>Start a request</a>

        {/* Health-adjacent service, so the boundary is stated on the page rather than left
            to the Terms. This is not a medical disclaimer written by me - it points at
            the owner's own clauses and says plainly what the page is not. */}
        <p className="brx-note">
          Bharat Rx coordinates requests and records. It is not a substitute for
          professional medical advice, diagnosis or treatment, and nothing on this page is
          advice. In an emergency, contact local emergency services.
        </p>

        <style jsx>{`
          /* brx- prefixed. The globally imported src/styles/*.css declares unscoped rules
             for generic names and styled-jsx does not shield a page from them. */
          .brx{max-width:700px}
          /* Section h2 is the contract's 700 rung - HEAVIER than the hero h1's 600. That
             inversion is intentional across the site. */
          .brx-h2{
            font-size:clamp(28px,3.2vw,40px);font-weight:700;line-height:1.08;
            letter-spacing:-1.2px;color:rgba(0,0,0,.95);margin:0 0 22px;
          }
          .brx-steps{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:20px}
          .brx-step{display:flex;gap:16px;align-items:flex-start}
          /* The .22 lime tint: the contract's transient/quiet treatment, right for a
             counter that labels rather than acts. Full-strength lime is reserved for the
             single call to action below. */
          .brx-step-n{
            flex:0 0 auto;width:34px;height:34px;border-radius:50%;
            display:grid;place-items:center;
            background:rgba(209,244,112,.22);color:#1a3a2a;
            font-size:15px;font-weight:700;
          }
          /* Card-heading rung: 22px/700/-.25px/#000, same as .pp-strip-title. */
          .brx-step-t{display:block;margin:5px 0 6px;font-size:22px;font-weight:700;line-height:1.27;letter-spacing:-.25px;color:#000}
          /* The one body level: 20px/400/1.4/-.125px. */
          .brx-p{font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;color:rgba(0,0,0,.898);margin:0}
          /* Full-strength #d1f470 with #1a3a2a type - the contract's own-surface pairing,
             and 2px because the hairline rule is that 2px means hoverable. */
          .brx-cta{
            display:inline-flex;align-items:center;min-height:52px;margin-top:30px;
            padding:0 26px;border:2px solid #d1f470;border-radius:50px;
            background:#d1f470;color:#1a3a2a;font-size:17px;font-weight:600;text-decoration:none;
            transition:background-color .2s,transform .2s,box-shadow .2s;
          }
          .brx-cta:hover{background:#fff;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}
          .brx-cta:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:3px}
          /* Static 1px hairline, per the rule: 1px static, 2px hoverable. */
          .brx-note{
            margin:34px 0 0;padding:16px 18px;border:1px solid #e5e7eb;border-radius:12px;
            font-size:16px;line-height:1.55;color:rgba(0,0,0,.54);
          }
          @media(max-width:767px){
            .brx-p{font-size:18px}
            .brx-step-t{font-size:20px}
          }
        `}</style>
      </section>
    </RotatingHero>
  </>
);

export default BharatRxPage;
