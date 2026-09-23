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
 * TWO TRACKS: ORDERING AND CONSULTING. The first version described one generic flow -
 * send a request, a professional reviews it, track it - which is a consultation and only a
 * consultation. The owner pointed out that the page said nothing about ordering medicine,
 * which is correct and was the more important of the two jobs: the hero cycles "medicines"
 * first, so a visitor arriving to reorder a prescription was promised that and then shown
 * a booking flow.
 *
 * COPY IS STILL NON-COMMITTAL ABOUT CLINICAL CLAIMS. Nothing here states what Rx
 * diagnoses or advises, because a health-adjacent page is the wrong place to guess.
 *
 * ONE STATEMENT NEEDS CONFIRMING, and it is in the note at the foot of the page:
 * "prescription medicines need a valid prescription and are dispensed by a licensed
 * pharmacy". I did not invent that to fill space - selling prescription medicines in India
 * without one is not lawful, so the page cannot describe an ordering flow and stay silent
 * about it. It is written as the requirement rather than as a claim about a named partner,
 * which is consistent with how Terms sections 5 and 6 already frame third-party sellers
 * and providers. Confirm the fulfilment arrangement and make it specific.
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
        content="Bharat Rx by WECARE.DIGITAL — order medicines from a prescription with delivery and refill reminders, or book a consult. Orders and records stay in one place."
      />
      <link rel="canonical" key="canonical" href="https://wecare.digital/bharat-rx/" />
    </Head>
    <RotatingHero
      ariaLabel="Bharat Rx"
      badgeLabel="Bharat Rx by WECARE.DIGITAL"
      frame="One place for"
      words={ CYCLE_WORDS }
      sub="Order from a prescription and track it to your door, or book a consult — with transparent pricing on both."
    >
      <section className="brx" aria-label="About Bharat Rx">
        {/* TWO TRACKS, because ordering medicine and booking a consult are different jobs
            and the page previously described only the second. The old single list read
            "send a request, a professional reviews it, track it" - which is a consultation
            flow, so a visitor who came to reorder a prescription found nothing that looked
            like their task even though the hero promises medicines first. */}
        <h2 className="brx-h2">Two things you can do here</h2>

        <div className="brx-tracks">
          <div className="brx-track">
            <span className="brx-track-tag">Order medicines</span>
            <ol className="brx-steps">
              <li className="brx-step">
                <span className="brx-step-n">1</span>
                <div>
                  <strong className="brx-step-t">Send your prescription or list</strong>
                  <p className="brx-p">Photograph a prescription, reorder from a past order, or type the items you need.</p>
                </div>
              </li>
              <li className="brx-step">
                <span className="brx-step-n">2</span>
                <div>
                  <strong className="brx-step-t">We confirm price and stock</strong>
                  <p className="brx-p">You see what is available and what it costs — including substitutes — before you pay.</p>
                </div>
              </li>
              <li className="brx-step">
                <span className="brx-step-n">3</span>
                <div>
                  <strong className="brx-step-t">It reaches your door</strong>
                  <p className="brx-p">Track the order to delivery, and set a refill reminder for the ones you take regularly.</p>
                </div>
              </li>
            </ol>
          </div>

          <div className="brx-track">
            <span className="brx-track-tag">Book a consult</span>
            <ol className="brx-steps">
              <li className="brx-step">
                <span className="brx-step-n">1</span>
                <div>
                  <strong className="brx-step-t">Describe what you need</strong>
                  <p className="brx-p">Attach anything relevant — a report, a photograph, a previous record.</p>
                </div>
              </li>
              <li className="brx-step">
                <span className="brx-step-n">2</span>
                <div>
                  <strong className="brx-step-t">A professional reviews it</strong>
                  <p className="brx-p">Requests that need a qualified opinion get one. What that involves is set out in section 17 of the Terms.</p>
                </div>
              </li>
              <li className="brx-step">
                <span className="brx-step-n">3</span>
                <div>
                  <strong className="brx-step-t">Keep the record</strong>
                  <p className="brx-p">Outcomes, prescriptions and history stay in one place, next to your orders.</p>
                </div>
              </li>
            </ol>
          </div>
        </div>

        <a className="brx-cta" href={ SELFSERVICE }>Order medicines or book a consult</a>

        {/* Health-adjacent service, so the boundary is stated on the page rather than left
            to the Terms. This is not a medical disclaimer written by me - it points at
            the owner's own clauses and says plainly what the page is not. */}
        <p className="brx-note">
          Prescription medicines need a valid prescription and are dispensed by a licensed
          pharmacy. Bharat Rx coordinates the order, the consult and the record; it is not a
          substitute for professional medical advice, diagnosis or treatment, and nothing on
          this page is advice. In an emergency, contact local emergency services.
        </p>

        <style jsx>{`
          /* brx- prefixed. The globally imported src/styles/*.css declares unscoped rules
             for generic names and styled-jsx does not shield a page from them. */
          /* Wider than the old 700px because there are two tracks now. Each column still
             lands near 46 characters at 20px, inside the 45-75 measure the site holds to. */
          .brx{max-width:1000px}
          .brx-tracks{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:44px}
          .brx-track{min-width:0}
          /* Labels the track without competing with the step headings: the .22 tint again,
             which is the quiet treatment, not the actionable one. */
          .brx-track-tag{
            display:inline-block;margin:0 0 20px;padding:6px 14px;border-radius:50px;
            background:rgba(209,244,112,.22);color:#1a3a2a;
            font-size:14px;font-weight:700;letter-spacing:.02em;
          }
          @media(max-width:899px){
            .brx-tracks{grid-template-columns:1fr;gap:38px}
          }
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
