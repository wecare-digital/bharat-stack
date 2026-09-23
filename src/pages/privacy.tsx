import React from 'react';
import Head from 'next/head';
import RotatingHero, { type CycleWord } from '../components/RotatingHero';
import LegalDocument from '../components/LegalDocument';
import { PRIVACY_SECTIONS, PRIVACY_INTRO, PRIVACY_UPDATED } from '../content/legal/privacy';

/**
 * /privacy — Privacy Policy.
 *
 * NOW IN THE MENU. It was deliberately unlinked while the text was a placeholder; the
 * owner has since asked for it to be listed, and with the real policy in place that is
 * the right call - a privacy policy nobody can find from the site is close to useless,
 * and app stores and payment providers expect a discoverable link.
 *
 * ROUTING: '/privacy' is in the EXACT-MATCH allowlist in _app.tsx. Without that entry
 * this renders an empty body with HTTP 200. trailingSlash means the URL is /privacy/.
 *
 * THE PLACEHOLDER IS GONE. This carries the owner's real published policy - 24 sections
 * plus the sub-clauses of 3 and 10 - ported from the Wix page by parsing it rather than
 * retyping it. src/content/legal/privacy.ts records exactly what was and was not
 * changed: structure and navigation only, never a representation about data handling.
 *
 * noindex was removed with the placeholder. A privacy policy should be indexable.
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

const PrivacyPage: React.FC = () => (
  <>
    <Head>
      <title>Privacy Policy — WECARE.DIGITAL</title>
      <meta
        name="description"
        content="How WECARE.DIGITAL collects, uses, stores, shares and protects personal data — what we collect, why, who it is shared with, how long we keep it, and your rights."
      />
      <link rel="canonical" key="canonical" href="https://wecare.digital/privacy/" />
    </Head>
    <RotatingHero
      ariaLabel="Privacy policy"
      badgeLabel="Legal Stuff — WECARE.DIGITAL"
      frame="Your data, your"
      words={ CYCLE_WORDS }
      sub="What we collect, why we collect it, and how to ask us to change or delete it."
    >
      <LegalDocument
        sections={ PRIVACY_SECTIONS }
        intro={ PRIVACY_INTRO }
        updated={ PRIVACY_UPDATED }
        notice={ <>
          To ask what data we hold, to correct it, or to have it deleted, write to
          {' '}<a href="mailto:one@wecare.digital">one@wecare.digital</a>. We may ask for
          information to verify who you are before acting on a request.
        </> }
      />
    </RotatingHero>
  </>
);

export default PrivacyPage;
