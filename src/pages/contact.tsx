import React from 'react';
import Head from 'next/head';
import RotatingHero, { type CycleWord } from '../components/RotatingHero';

/**
 * /contact — the Selfservice entry point.
 *
 * ROUTING: _app.tsx keeps an EXACT-MATCH public route allowlist. '/contact' must be
 * registered there or this page renders an empty body with HTTP 200 - a 404 that does
 * not look like one. next.config.js also sets trailingSlash, so the URL is /contact/.
 *
 * Note the neighbouring routes this is NOT: /contacts is the authenticated CRM
 * contact list and /contact-test is an older public test page. Three similar names,
 * three different things - do not consolidate them without checking the allowlist and
 * the dashboard nav.
 *
 * The rotation carries the five Selfservice actions, which is the owner's request and
 * also does useful work: it tells a visitor what this page is for before they read a
 * word of body copy.
 */

// Phrased as verbs so every variant completes the frame as a sentence, and kept within
// two characters of each other - 14 to 16 - because the pill animates to each word's
// MEASURED width and a short outlier makes it lurch. "Drop Docs" became "drop
// documents" for exactly that reason: at 9 characters it was a 7-character outlier
// against "submit a request".
//
// Tints and dots are reused verbatim from the Grahak OS hero and the VayuLok
// rotation. No new colours. Order alternates cool and warm so the change always
// registers.
const CYCLE_WORDS: CycleWord[] = [
  { word: 'submit a request', tint: '#dbeafe', dot: '#2563eb' },
  { word: 'amend a request', tint: '#fef3c7', dot: '#f0a818' },
  { word: 'track a request', tint: '#e0f7c8', dot: '#3da35a' },
  { word: 'drop documents', tint: '#ede9fe', dot: '#9849e8' },
  { word: 'leave a review', tint: '#fee2e2', dot: '#dc2626' },
];

const ContactPage: React.FC = () => (
  <>
    <Head>
      <title>Contact — WECARE.DIGITAL</title>
      <meta
        name="description"
        content="Submit a request, amend or track an existing one, drop documents, or leave a review."
      />
      <link rel="canonical" key="canonical" href="https://wecare.digital/contact/" />
    </Head>
    <RotatingHero
      ariaLabel="Contact WECARE.DIGITAL"
      badgeLabel="Selfservice by WECARE.DIGITAL"
      frame="You can"
      words={ CYCLE_WORDS }
      sub="Every request is tracked end to end, with transparent pricing and one place to check where things stand."
    />
  </>
);

export default ContactPage;
