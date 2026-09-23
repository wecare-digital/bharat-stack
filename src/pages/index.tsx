/**
 * Home — the company page.
 *
 * The rotating headline pill is the SAME mechanism as the Grahak OS hero and the
 * VayuLok headline, not a lookalike: identical 2400ms interval, identical easings
 * (.16,1,.3,1 for the wipe and the width glide, .34,1.56,.64,1 for the dot pop),
 * identical white entrance shutter and .33em dot. The three pages are meant to
 * animate as one family, so if you retune one, retune all three.
 *
 * COPY IS PROVISIONAL, and carries the owner's positioning: AI worth having reduces
 * cost and complexity, favours real-world utility over scale, and compounds across
 * domains. The rotation is doing argumentative work rather than decoration - the
 * pill cycling through four unrelated domains is the "across every domain" claim
 * enacted rather than asserted, which is why the headline does not need to say it.
 * The sub-line carries the cost/complexity half. To reword, edit CYCLE_WORDS and
 * .home-sub; nothing else depends on the strings.
 *
 * WORD LENGTH IS A DESIGN CONSTRAINT, not a copy detail, for one measured reason:
 * the pill animates to each word's measured width, so the spread between the
 * shortest and longest word is how far the headline's tail travels on every tick.
 * These four span 196-290px at the 60px cap (~94px). An earlier draft using
 * "Intelligence" spanned 205-310px (~105px).
 *
 * To be precise about what is and is not known: both sets glide rather than snap -
 * sampling shows the width interpolating smoothly in each case - so the shorter
 * spread is a margin-of-safety choice, not the fix for an observed defect. What
 * WOULD be a real defect is the headline reflowing to a second line on the longest
 * word only, which shifts everything below it; animcheck.js measures the h1 height
 * across a full rotation to catch that, and it is constant today.
 *
 * Keep replacements within ~2 characters of each other and re-run that harness.
 *
 * The four tint/dot pairs are reused VERBATIM from the Grahak OS hero - no new
 * colours. Hue maps onto sense the way it does on the other two pages: green for our
 * own domain, blue for communication, purple for intelligence, amber for service.
 * Like the channel tints, this per-subject system sits outside the brand palette by
 * design, which is why lime is absent here.
 *
 * The rotating markup MUST stay inline in this return tree. styled-jsx only attaches
 * its scoping class to elements it can statically see there, so lifting the pill into
 * a variable or a child component silently drops every style and the words render
 * stacked with no pill. That has already happened twice on the other two pages.
 *
 * Classes stay home- prefixed. The globally imported src/styles/*.css declares
 * unscoped rules for generic names and styled-jsx does not shield a page from them.
 */

import React, { useEffect, useRef, useState } from 'react';
import Head from 'next/head';
import BrandBadge from '../components/BrandBadge';

// Module scope, not inside the component: the rotation effect reads .length, and a
// literal declared in the body would make that a changing dependency and force an
// exhaustive-deps suppression the way VayuLok needed one.
// Lowercase: these sit mid-sentence, not at the head of one.
//
// These are the owner's own service domains, from the positioning copy: travel,
// documentation, dispute resolution, rituals, reflection "and more". Two are
// shortened for the pill because the pill's width is layout (see the note above) -
// "documentation" becomes documents and "dispute resolution" becomes disputes. The
// full phrases are not lost; they belong in body copy, not in a rotating slot.
//
// Order is hue rhythm, the consideration VayuLok documents: blue, amber, green,
// purple, red alternates cool and warm on every step except green -> purple, which
// is unavoidable with five words across three cool hues and is the most separated
// of the available cool pairs. Grouping them by meaning instead - the two
// paperwork ones together - put green beside green and the change stopped reading.
//
// Every tint/dot pair is reused VERBATIM from the Grahak OS hero and the VayuLok
// rotation. No new colours. Hue maps onto sense: blue for journeys, amber for the
// warmth of ritual, green for paperwork cleared, purple for reflection, red for
// conflict.
const CYCLE_WORDS = [
  { word: 'travel', tint: '#dbeafe', dot: '#2563eb' },
  { word: 'rituals', tint: '#fef3c7', dot: '#f0a818' },
  { word: 'documents', tint: '#e0f7c8', dot: '#3da35a' },
  { word: 'reflection', tint: '#ede9fe', dot: '#9849e8' },
  { word: 'disputes', tint: '#fee2e2', dot: '#dc2626' },
];

const HomePage: React.FC = () => {
  const [ cycleIndex, setCycleIndex ] = useState( 0 );
  const [ cycleW, setCycleW ] = useState<number | null>( null );
  const wordRefs = useRef<( HTMLSpanElement | null )[]>( [] );
  const [ shown, setShown ] = useState( false );

  useEffect( () => {
    // One-shot entrance, same 60ms beat as VayuLok. No observer: there is a single
    // block above the fold, so there is nothing to reveal on scroll.
    const id = window.setTimeout( () => setShown( true ), 60 );
    return () => window.clearTimeout( id );
  }, [] );

  useEffect( () => {
    if ( window.matchMedia( '(prefers-reduced-motion: reduce)' ).matches ) return;
    const id = window.setInterval(
      () => setCycleIndex( i => ( i + 1 ) % CYCLE_WORDS.length ),
      2400
    );
    return () => window.clearInterval( id );
  }, [] );

  useEffect( () => {
    // Measured, not guessed: "Intelligence" is more than twice the width of
    // "Service", and animating to a measured px value is what makes the pill glide
    // instead of snap.
    const el = wordRefs.current[ cycleIndex ];
    if ( el ) setCycleW( el.offsetWidth );
  }, [ cycleIndex ] );

  return (
    <>
      <Head>
        <title>Bharat Stack by WECARE.DIGITAL</title>
        <meta name="description" content="Bharat Stack by WECARE.DIGITAL." />
        <link rel="canonical" href="https://stack.wecare.digital/" />
      </Head>
      <main className="home-shell" aria-label="Bharat Stack home">
        {/* Same pill as the Grahak OS hero, with the maker line flipped: this page is
            the company, that page is one product of it. */}
        <div className={ `home-layout ${shown ? 'show' : ''}`.trim() }>
          <div className="home-hero">
            <div className="home-eyebrow">
              <BrandBadge label="Bharat Stack by WECARE.DIGITAL" />
            </div>

            {/* The pill sits on its OWN LINE, and that is a correctness fix rather
                than a layout preference.
                Inline after the frame text, the headline's line count depended on
                which word was showing: measured at 1440px, "reflection" pushed the
                h1 from 75px to 138px while the four shorter words fitted one line,
                so every 2400ms the whole page below jumped by 63px. Widening
                max-width only relocates that to a different viewport - with a word
                whose width varies by 156px inside flowing text, some width will
                always split the line for the long word and not the short one.
                Giving the pill its own block makes line count independent of word
                width, so the glide is free to be as wide as it likes. */}
            <h1 className="home-head">
              <span className="home-head-line">Everyday services for</span>
              <span
                className="home-mark"
                style={ { background: CYCLE_WORDS[ cycleIndex ].tint } }
              >
                <i
                  className="home-mark-dot"
                  style={ { background: CYCLE_WORDS[ cycleIndex ].dot } }
                  aria-hidden="true"
                />
                <span
                  className="home-cycle"
                  style={ cycleW ? { width: `${cycleW}px` } : undefined }
                >
                  {/* The rotation is visual only, so screen readers get the full list
                      once and every animated copy is hidden from them. */}
                  <span className="home-sr-only">{ CYCLE_WORDS.map( c => c.word ).join( ', ' ) }</span>
                  { CYCLE_WORDS.map( ( c, i ) => (
                    <span
                      key={ c.word }
                      ref={ el => { wordRefs.current[ i ] = el; } }
                      className={ `home-cyc-word ${i === cycleIndex ? 'on' : ''}`.trim() }
                      aria-hidden="true"
                    >{ c.word }</span>
                  ) ) }
                </span>
              </span>
            </h1>

            {/* The one body level the contract allows: 20px/400/1.4/-.125px at
                rgba(0,0,0,.898). Carries the half of the positioning the headline
                cannot - cost and complexity - while the rotation above carries
                breadth. Deliberately one sentence: a second would put two body
                blocks on a page that has no section rhythm yet. */}
            <p className="home-sub">
              Transparent pricing, guided journeys, and dependable support — on one
              shared foundation.
            </p>
          </div>
        </div>
      </main>
      <style jsx>{`
        /* The font stack is declared here, not inherited. Measured in a browser, this
           page already rendered in Inter - but only because @aws-amplify/ui-react's
           styles.css sets a font-family on body that happens to start with Inter. The
           public pages' typeface was therefore a side effect of an auth library's
           stylesheet, and would have changed silently if that import moved or the
           package bumped. This is the same stack .page declares on /grahak-os/.
           Note --font-sans in Pages.css contains no Inter at all, so that is not a
           fallback that would have caught it. */
        .home-shell{
          min-height:calc(100vh - 69px);
          padding-top:108px;
          box-sizing:border-box;
          background:#fff;
          font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
          color:#1a1a1a;
        }
        /* gap:96px is the SECTION rhythm and stays that even though there is one
           section today - it is what the next block will sit on. The eyebrow-to-
           headline distance is deliberately NOT this gap: it is 20px, owned by
           .home-eyebrow below, matching .hero-eyebrow on Grahak OS and .vl-eyebrow
           on VayuLok. That is why the badge and the headline are wrapped in
           .home-hero rather than being two flex children - as siblings they would
           have been pushed 96px apart. */
        .home-layout{
          width:100%;
          max-width:1300px;
          margin:0 auto;
          padding:80px 24px 96px;
          box-sizing:border-box;
          display:flex;
          flex-direction:column;
          gap:96px;
        }
        /* align-items:flex-start replaces the align-self the eyebrow used to carry.
           Without it the badge is stretched to the full 1300px measure by the flex
           default. It has to be handled on a wrapper rather than passed to the badge:
           styled-jsx does not scope composite components, so anything sent in from
           this page arrives unstyled. */
        .home-hero{
          display:flex;
          flex-direction:column;
          align-items:flex-start;
        }
        .home-eyebrow{
          margin:0 0 20px;
        }
        /* Hero h1 rung from the design contract: 600, which is LIGHTER than the 700
           section level. That inversion is notion's and is intentional - the same
           note guards .vl-head and .hero-left h1. Do not "correct" it. */
        .home-head{
          font-size:clamp(36px,4.3vw,60px);
          font-weight:600;
          line-height:1.04;
          letter-spacing:-2.2px;
          color:rgba(0,0,0,.95);
          margin:0;
          max-width:900px;
        }
        /* The single body rung, matching .hero-left p on Grahak OS exactly. The
           contract allows ONE body level across a page and this is it.
           max-width is 560px rather than the headline's 900px: at 20px the 900px
           measure runs to ~110 characters a line, well past the 45-75 the rest of
           the site holds to. 24px above it is the hero's paragraph gap. */
        .home-sub{
          font-size:20px;
          font-weight:400;
          line-height:1.4;
          letter-spacing:-.125px;
          color:rgba(0,0,0,.898);
          margin:24px 0 0;
          max-width:560px;
          /* At a flat 560px this sentence broke after "over" and left "scale." alone
             on the second line. balance evens the two lines instead of filling the
             first greedily. It is a progressive enhancement - unsupported browsers
             get the greedy break, which is the current behaviour, not a regression -
             so it needs no @supports guard. Only safe because this is a short,
             known-length string; balance is capped at a handful of lines and is the
             wrong tool for flowing body copy. */
          text-wrap:balance;
        }

        /* Rotating pill. Same geometry, easing and timings as .hero-mark on Grahak OS
           and .vl-mark on VayuLok - em-based so it tracks the clamp() headline at
           every width. */
        /* Blocks, so the frame and the pill never share a line. See the note in the
           markup: this is what stops the h1's height depending on which word is
           active. margin-top is the optical gap between the two lines - line-height
           1.04 leaves almost no leading, so without it the pill crowds the text. */
        .home-head-line{display:block}
        .home-mark{
          position:relative;display:inline-block;white-space:nowrap;margin-top:.08em;
          padding:.02em .3em .02em .22em;
          border-radius:9999px;
          background:#e0f7c8;
          transition:background-color .52s cubic-bezier(.16,1,.3,1);
        }
        /* White shutter that wipes off to the left on entrance, so the tint appears
           to fill in rather than simply switching on. */
        .home-mark::before{
          content:'';position:absolute;inset:0;
          background:#fff;border-radius:9999px;
          transform:scaleX(1);transform-origin:right center;
          transition:transform .78s cubic-bezier(.16,1,.3,1) .18s;
          z-index:0;
        }
        .home-layout.show .home-mark::before{transform:scaleX(0)}
        /* .33em matches the dot-to-headline ratio measured on notion.com; the tight
           .18em gap keeps it reading as attached to the word. */
        .home-mark-dot{
          position:relative;z-index:1;
          display:inline-block;width:.33em;height:.33em;
          background:#3da35a;border-radius:50%;
          margin-right:.18em;vertical-align:.14em;
          transform:scale(0);
          transition:transform .5s cubic-bezier(.34,1.56,.64,1) .72s;
        }
        .home-layout.show .home-mark-dot{transform:scale(1)}
        /* Width is animated from the measured word so the pill glides between
           "Service" and "Intelligence" instead of snapping. overflow:hidden is what
           clips the outgoing word as it slides. */
        .home-cycle{
          position:relative;z-index:1;
          display:inline-block;
          height:1.06em;line-height:1.06em;
          vertical-align:baseline;
          overflow:hidden;
          transition:width .52s cubic-bezier(.16,1,.3,1);
          will-change:width;
        }
        .home-cyc-word{
          position:absolute;left:0;top:0;
          white-space:nowrap;
          opacity:0;
          transform:translateY(.42em);
          transition:opacity .42s cubic-bezier(.16,1,.3,1),transform .42s cubic-bezier(.16,1,.3,1);
        }
        .home-cyc-word.on{opacity:1;transform:translateY(0)}
        .home-sr-only{
          position:absolute;width:1px;height:1px;padding:0;margin:-1px;
          overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0;
        }

        @media(max-width:767px){
          .home-shell{min-height:calc(100vh - 85px);padding-top:96px}
          .home-layout{padding:48px 16px 64px;gap:64px}
          .home-head{letter-spacing:-1.2px;line-height:1.1}
        }
        @media(max-width:480px){
          .home-head{letter-spacing:-.8px}
        }

        /* The rotation itself is already disabled in JS; this settles the pill into
           its resting state so nothing is mid-transition. */
        @media(prefers-reduced-motion:reduce){
          .home-mark::before,.home-mark-dot{transition:none}
          .home-mark::before{transform:scaleX(1)}
          .home-mark-dot{transform:scale(1)}
          .home-cycle{transition:none}
          .home-cyc-word{transition:none}
        }
      `}</style>
    </>
  );
};

export default HomePage;
