/**
 * VayuLok public product page
 * Bharat Air Intelligence, by WECARE.DIGITAL
 *
 * DELIBERATELY CLEAR. The page is the tag and the rotating line beneath it, nothing
 * else. That is the owner's call, and it also happens to be the honest one: nothing
 * in this repository describes what VayuLok does beyond the capabilities the rotating
 * words name, so any further copy here would be invented, on a public page.
 *
 * THE ROTATING WORDS, AND WHICH OF THEM ARE BACKED TODAY.
 *
 * Air, Weather, Forecast and Solar each name an endpoint that
 * shared/wix-velo/backend/google-services.web.js already calls - checked against that
 * file rather than taken from a doc:
 *
 *   Air       airquality.googleapis.com/v1/currentConditions:lookup
 *   Weather   weather.googleapis.com/v1/currentConditions:lookup
 *   Forecast  weather.googleapis.com/v1/forecast/days:lookup
 *   Solar     solar.googleapis.com/v1/buildingInsights:findClosest
 *
 * Heatmap and Pollen are ROADMAP, added at the owner's request. Both are real Google
 * APIs, neither is wired here yet:
 *
 *   Pollen    pollen.googleapis.com/v1/forecast:lookup                 (unused)
 *   Heatmap   airquality .../mapTypes/{type}/heatmapTiles/{z}/{x}/{y}  (unused)
 *
 * Heatmap is also the one word in the set that is a VIEW rather than a subject, so it
 * reads oddly in the slot - "Bharat Heatmap Intelligence" parses as intelligence
 * about heatmaps rather than a heatmap of intelligence. Kept because it was asked
 * for; "Pollution" or dropping it are the alternatives if that grates on screen.
 *
 * So the rotation is no longer a pure statement of what is built. When the two
 * endpoints land, delete this caveat.
 *
 * Mechanism is lifted from the Grahak OS hero so the two pages animate identically:
 * measured width so the pill resizes instead of snapping, a pale tint with a
 * saturated dot of the same hue swapping with the word, and the same easing and
 * 2400ms interval. The four tint/dot pairs are reused verbatim from that page - no
 * new colours were introduced for this page, and the hues map cleanly onto the
 * subjects (green air, blue weather, purple forecast, amber solar).
 *
 * ROUTING: _app.tsx keeps an EXACT-MATCH public route allowlist. '/vayulok' is
 * registered there. Without that entry this page would render an empty body with
 * HTTP 200 - a 404 that does not look like one. next.config.js also sets
 * trailingSlash, so the URL is /vayulok/ with the slash.
 *
 * The rotating markup MUST stay inline in the return tree. styled-jsx only attaches
 * its scoping class to elements it can statically see there, so lifting the pill into
 * a variable or a child component silently drops every style and the words render
 * stacked with no pill. This is documented on the Grahak OS hero after it happened.
 *
 * Every class is vl- prefixed, following pp- on the Grahak OS page and ft- in the
 * Footer. The globally imported src/styles/*.css declares unscoped rules for generic
 * names, and styled-jsx does not shield a page from those.
 */

import React, { useEffect, useRef, useState } from 'react';
import Head from 'next/head';
import BrandBadge from '../../components/BrandBadge';

const VayuLokPage: React.FC = () => {
  // Order is hue rhythm as much as grouping. Air + Pollen are what is in the air,
  // Weather + Forecast are conditions, Solar is the adjacent service, Heatmap is the
  // view rather than a subject. Sequencing them this way leaves only one adjacent
  // warm pair (Solar -> Heatmap); the obvious logical order stacked amber, red and
  // yellow consecutively and the pill stopped feeling like it was changing.
  //
  // The first four tint/dot pairs are reused verbatim from the Grahak OS hero. The
  // last two are new, and follow that system's construction rule rather than being
  // picked freely: a pale tint with a saturated dot of the SAME hue, at roughly the
  // 100/600 relationship the existing four use. Reusing one of the four for Heatmap
  // or Pollen was the alternative, but every existing pair is hue-matched to its
  // subject and doubling up would have broken exactly that.
  // Red for Heatmap because the map reads as heat; yellow for Pollen for the obvious
  // reason. Neither touches the brand palette - like the Grahak OS channel tints,
  // these are a per-subject system that sits outside it by design.
  const cycleWords = [
    { word: 'Air', tint: '#e0f7c8', dot: '#3da35a' },
    { word: 'Pollen', tint: '#fef9c3', dot: '#ca8a04' },
    { word: 'Weather', tint: '#dbeafe', dot: '#2563eb' },
    { word: 'Forecast', tint: '#ede9fe', dot: '#9849e8' },
    { word: 'Solar', tint: '#fef3c7', dot: '#f0a818' },
    { word: 'Heatmap', tint: '#fee2e2', dot: '#dc2626' },
  ];
  const [ cycleIndex, setCycleIndex ] = useState( 0 );
  const [ cycleW, setCycleW ] = useState<number | null>( null );
  const wordRefs = useRef<( HTMLSpanElement | null )[]>( [] );
  const [ shown, setShown ] = useState( false );

  useEffect( () => {
    // The entrance wipe and the dot pop are one-shot, so this does not need an
    // observer the way the Grahak OS page's multiple sections do.
    const id = window.setTimeout( () => setShown( true ), 60 );
    return () => window.clearTimeout( id );
  }, [] );

  useEffect( () => {
    if ( window.matchMedia( '(prefers-reduced-motion: reduce)' ).matches ) return;
    const id = window.setInterval(
      () => setCycleIndex( i => ( i + 1 ) % cycleWords.length ),
      2400
    );
    return () => window.clearInterval( id );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [] );

  useEffect( () => {
    const el = wordRefs.current[ cycleIndex ];
    if ( el ) setCycleW( el.offsetWidth );
  }, [ cycleIndex ] );

  return (
    <>
      <Head>
        <title>VayuLok by WECARE.DIGITAL</title>
        <meta name="description" content="VayuLok - Bharat Air Intelligence, by WECARE.DIGITAL." />
        <link rel="canonical" key="canonical" href="https://stack.wecare.digital/vayulok/" />
      </Head>

      <main className="vl-shell" aria-label="VayuLok">
        <div className={ `vl-layout ${shown ? 'show' : ''}`.trim() }>
          {/* Same component as the Grahak OS hero and the home page, so the three
              pills cannot drift apart. The wrapper carries the spacing because
              styled-jsx cannot style a composite component from here. */}
          <div className="vl-eyebrow">
            <BrandBadge label="VayuLok by WECARE.DIGITAL" />
          </div>

          <h1 className="vl-head">
            Bharat{ ' ' }
            <span
              className="vl-mark"
              style={ { background: cycleWords[ cycleIndex ].tint } }
            >
              <i
                className="vl-mark-dot"
                style={ { background: cycleWords[ cycleIndex ].dot } }
                aria-hidden="true"
              />
              <span
                className="vl-cycle"
                style={ cycleW ? { width: `${cycleW}px` } : undefined }
              >
                {/* The rotation is visual only, so screen readers get the full list
                    once and every animated copy is hidden from them. */}
                <span className="vl-sr-only">{ cycleWords.map( c => c.word ).join( ', ' ) }</span>
                { cycleWords.map( ( c, i ) => (
                  <span
                    key={ c.word }
                    ref={ el => { wordRefs.current[ i ] = el; } }
                    className={ `vl-cyc-word ${i === cycleIndex ? 'on' : ''}`.trim() }
                    aria-hidden="true"
                  >{ c.word }</span>
                ) ) }
              </span>
            </span>{ ' ' }
            Intelligence
          </h1>
        </div>
      </main>

      <style jsx>{`
        /* Header is fixed at 108px, 96px under 767px - the same offsets the home
           page uses, so the two public shells start at the same place.
           The font stack is declared rather than inherited, matching .page on
           /grahak-os/ and .home-shell. This page did already render in Inter, but
           only via the body rule in @aws-amplify/ui-react's styles.css - so the
           typeface of a public marketing page depended on an auth library's CSS
           import order. Pages.css's --font-sans has no Inter in it, so nothing here
           would have fallen back to the right face. */
        .vl-shell{min-height:calc(100vh - 69px);padding-top:108px;box-sizing:border-box;background:#fff;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#1a1a1a}
        /* No flex gap: the only gap in the page is under the badge and .vl-eyebrow
           owns it. A column gap would apply to nothing and quietly mislead whoever
           adds the second element. */
        .vl-layout{width:100%;max-width:1300px;margin:0 auto;padding:80px 24px 96px;box-sizing:border-box}

        /* Spacing only. The badge paints itself inside BrandBadge. */
        .vl-eyebrow{margin:0 0 20px}

        /* Hero h1 level from the design contract: 600 weight, not the heavier 700
           the section level uses. That inversion - section headings heavier than the
           h1 - is notion's and is intentional, so do not "correct" it here. */
        .vl-head{font-size:clamp(36px,4.3vw,60px);font-weight:600;line-height:1.04;letter-spacing:-2.2px;color:rgba(0,0,0,.95);margin:0;max-width:900px}

        /* Rotating pill. Same geometry, easing and timings as .hero-mark on the
           Grahak OS page - em-based so it tracks the clamp() headline at every width. */
        .vl-mark{
          position:relative;display:inline-block;white-space:nowrap;
          padding:.02em .3em .02em .22em;
          border-radius:9999px;
          background:#e0f7c8;
          transition:background-color .52s cubic-bezier(.16,1,.3,1);
        }
        /* White shutter that wipes off to the left on entrance, so the tint appears
           to fill in rather than simply switching on. */
        .vl-mark::before{
          content:'';position:absolute;inset:0;
          background:#fff;border-radius:9999px;
          transform:scaleX(1);transform-origin:right center;
          transition:transform .78s cubic-bezier(.16,1,.3,1) .18s;
          z-index:0;
        }
        .vl-layout.show .vl-mark::before{transform:scaleX(0)}
        /* .33em matches the dot-to-headline ratio measured on notion.com; the tight
           .18em gap keeps it reading as attached to the word. */
        .vl-mark-dot{
          position:relative;z-index:1;
          display:inline-block;width:.33em;height:.33em;
          background:#3da35a;border-radius:50%;
          margin-right:.18em;vertical-align:.14em;
          transform:scale(0);
          transition:transform .5s cubic-bezier(.34,1.56,.64,1) .72s;
        }
        .vl-layout.show .vl-mark-dot{transform:scale(1)}
        /* Width is animated from the measured word so the pill glides between "Air"
           and "Forecast" instead of snapping. overflow:hidden is what clips the
           outgoing word as it slides. */
        .vl-cycle{
          position:relative;z-index:1;
          display:inline-block;
          height:1.06em;line-height:1.06em;
          vertical-align:baseline;
          overflow:hidden;
          transition:width .52s cubic-bezier(.16,1,.3,1);
          will-change:width;
        }
        .vl-cyc-word{
          position:absolute;left:0;top:0;
          white-space:nowrap;
          opacity:0;
          transform:translateY(.42em);
          transition:opacity .42s cubic-bezier(.16,1,.3,1),transform .42s cubic-bezier(.16,1,.3,1);
        }
        .vl-cyc-word.on{opacity:1;transform:translateY(0)}
        .vl-sr-only{
          position:absolute;width:1px;height:1px;padding:0;margin:-1px;
          overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0;
        }

        @media(max-width:767px){
          .vl-shell{min-height:calc(100vh - 85px);padding-top:96px}
          .vl-layout{padding:48px 20px 64px}
          .vl-head{letter-spacing:-1.2px;line-height:1.1}
        }
        @media(max-width:480px){
          .vl-layout{padding:40px 16px 56px}
          .vl-head{letter-spacing:-.8px}
        }

        /* The rotation itself is already disabled in JS; this settles the pill into
           its resting state so nothing is mid-transition. */
        @media(prefers-reduced-motion:reduce){
          .vl-mark::before,.vl-mark-dot{transition:none}
          .vl-mark::before{transform:scaleX(1)}
          .vl-mark-dot{transform:scale(1)}
          .vl-cycle{transition:none}
          .vl-cyc-word{transition:none}
        }
      `}</style>
    </>
  );
};

export default VayuLokPage;
