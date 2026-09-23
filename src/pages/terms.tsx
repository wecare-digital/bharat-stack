import React from 'react';
import Head from 'next/head';
import RotatingHero, { type CycleWord } from '../components/RotatingHero';
import LegalDocument from '../components/LegalDocument';
import { TERMS_SECTIONS, TERMS_INTRO, TERMS_UPDATED } from '../content/legal/terms';

/**
 * /terms — Terms of Service.
 *
 * ROUTING: '/terms' must be in the EXACT-MATCH allowlist in _app.tsx or this renders an
 * empty body with HTTP 200. trailingSlash means the URL is /terms/.
 *
 * THE PLACEHOLDER IS GONE. This now carries the owner's real published document, all 45
 * sections plus the 12 sub-clauses of section 14, ported from the Wix page by parsing it
 * rather than retyping it. See src/content/legal/terms.ts for exactly what was and was
 * not changed - structure and navigation only, never the wording of a clause.
 *
 * noindex was also removed with the placeholder. It existed because an indexed empty
 * legal page is the document a regulator or a payment provider gets pointed at; that
 * reasoning no longer applies to a complete one, and terms of service should be
 * findable.
 */

// "Terms of service / payment / refunds / delivery" - all four complete the frame, and
// all are 7 or 8 characters so the pill barely moves. Tints reused verbatim.
const CYCLE_WORDS: CycleWord[] = [
  { word: 'service', tint: '#dbeafe', dot: '#2563eb' },
  { word: 'payment', tint: '#fef3c7', dot: '#f0a818' },
  { word: 'refunds', tint: '#e0f7c8', dot: '#3da35a' },
  { word: 'delivery', tint: '#ede9fe', dot: '#9849e8' },
];

const TermsPage: React.FC = () => (
  <>
    <Head>
      <title>Terms of Service — WECARE.DIGITAL</title>
      <meta
        name="description"
        content="The agreement between you and WECARE.DIGITAL when you use our services: orders, payments, refunds, delivery, professional services and dispute resolution."
      />
      <link rel="canonical" key="canonical" href="https://stack.wecare.digital/terms/" />
    </Head>
    <RotatingHero
      ariaLabel="Terms of service"
      badgeLabel="Legal Stuff — WECARE.DIGITAL"
      frame="Terms of"
      words={ CYCLE_WORDS }
      sub="The agreement between you and WECARE.DIGITAL when you use our services."
    >
      <LegalDocument
        sections={ TERMS_SECTIONS }
        intro={ TERMS_INTRO }
        updated={ TERMS_UPDATED }
        notice={ <>
          These Terms are a summary of the agreement in force and are provided for
          information. They are not legal advice. For a question about how a clause
          applies to you, contact us at <a href="mailto:one@wecare.digital">one@wecare.digital</a>.
        </> }
      />
    </RotatingHero>
  </>
);

export default TermsPage;
