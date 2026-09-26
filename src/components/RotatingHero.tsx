import React, { useEffect, useRef, useState } from 'react';
import BrandBadge from './BrandBadge';

/**
 * The Home hero — badge, rotating headline pill, one body line — as a reusable,
 * SELF-STYLING component.
 *
 * WHY SELF-STYLING: styled-jsx does not scope composite components. A parent's
 * <style jsx> cannot reach in here, so a consumer passing className or relying on
 * its own rules would get unstyled markup. That is the documented pattern for
 * BrandBadge, BrandLockup and AuthBrand, and it is the only arrangement that works.
 * The consumer owns nothing but the props.
 *
 * WHY A COMPONENT AT ALL, given the sibling warning on the Home page that the
 * rotating markup "MUST stay inline in this return tree": that warning is about
 * lifting markup OUT of a page's own return while leaving the styles behind in the
 * page's <style jsx>. Moving the markup AND its styles together into a component that
 * styles itself is the supported case. The distinction cost a full debugging round on
 * the mega menu, where a renderLink() helper left the rules behind and every row fell
 * through to a global - so it is worth being exact about.
 *
 * Contact, Terms, Privacy, Bharat Rx and My Order all use this. Home, VayuLok and
 * Grahak OS still carry their own inline copies, because their tests pin their class
 * names and CSS strings - so there are FOUR implementations of this hero in the repo
 * (rh-, home-, vl-, hero-), not two. The animation constants here are identical to
 * theirs by construction, and `node tools/browser/animcheck.js` asserts that all four
 * surfaces share the same computed transitions so the family cannot silently drift
 * apart. Measured identical as of this commit:
 *   pill width  0.52s cubic-bezier(.16,1,.3,1)
 *   word        0.42s opacity + transform, same easing
 *   tint        0.52s background-color, same easing
 *   dot         0.5s cubic-bezier(.34,1.56,.64,1) with a .72s delay
 *
 * ANIMATION CONSTANTS - do not retune one surface alone:
 *   2400ms interval, cubic-bezier(.16,1,.3,1) for the wipe and the width glide,
 *   cubic-bezier(.34,1.56,.64,1) .72s for the dot pop, .33em dot with a .18em gap.
 *
 * WORD LENGTH IS LAYOUT. The pill animates to each word's MEASURED width, so the
 * spread between shortest and longest is how far the line's tail travels every tick.
 * The pill sits on its own line here (.rh-head-line is display:block), which makes the
 * headline's line count independent of word width - that was a real defect on Home,
 * where "reflection" pushed the h1 from 75px to 138px at 1440px and the page below
 * jumped 63px every 2400ms. Keep a set within ~2-4 characters anyway, and re-run
 * `node tools/browser/animcheck.js` after changing one.
 *
 * THAT GUARANTEE IS WHY THIS COMPONENT IS THE ONE TO REUSE. The two inline copies that
 * put the pill inline mid-sentence instead - /vayulok/ ("Bharat <pill> Intelligence")
 * and /grahak-os/ ("across <pill>") - still reflow at narrow widths: measured at 320px,
 * VayuLok's h1 is 126px on Weather/Forecast/Heatmap and 87px on Air/Pollen/Solar, and
 * Grahak OS is 168px on WhatsApp against 128px on SMS/Email/Voice. Every surface built
 * on THIS component measures constant at all 21 viewports. Migrating those two pages
 * here is the fix, but it changes their hero line structure, so it is an owner call.
 */

export interface CycleWord {
  word: string;
  /** Pale pill fill. */
  tint: string;
  /** Saturated dot of the same hue. */
  dot: string;
}

interface RotatingHeroProps {
  /** Lime brand pill above the headline. */
  badgeLabel: string;
  /** Fixed text on the first headline line. The pill takes the second. */
  frame: string;
  words: CycleWord[];
  /** The single body line under the headline. Optional. */
  sub?: React.ReactNode;
  /** Accessible name for the <main> landmark. */
  ariaLabel: string;
  /** Extra content below the hero, inside the page measure. */
  children?: React.ReactNode;
}

const RotatingHero: React.FC<RotatingHeroProps> = ( { badgeLabel, frame, words, sub, ariaLabel, children } ) => {
  const [ cycleIndex, setCycleIndex ] = useState( 0 );
  const [ cycleW, setCycleW ] = useState<number | null>( null );
  const wordRefs = useRef<( HTMLSpanElement | null )[]>( [] );
  const [ shown, setShown ] = useState( false );

  useEffect( () => {
    const id = window.setTimeout( () => setShown( true ), 60 );
    return () => window.clearTimeout( id );
  }, [] );

  useEffect( () => {
    // typeof guard as well as the call: jsdom does not implement matchMedia and
    // THROWS rather than returning undefined, which crashed every Home test at once
    // against a green build until src/test/setup.ts stubbed it. A component used by
    // several pages should not depend on that stub existing.
    if ( typeof window.matchMedia === 'function'
      && window.matchMedia( '(prefers-reduced-motion: reduce)' ).matches ) return undefined;
    const id = window.setInterval( () => setCycleIndex( i => ( i + 1 ) % words.length ), 2400 );
    return () => window.clearInterval( id );
  }, [ words.length ] );

  useEffect( () => {
    const el = wordRefs.current[ cycleIndex ];
    if ( el ) setCycleW( el.offsetWidth );
  }, [ cycleIndex ] );

  const active = words.length ? cycleIndex % words.length : 0;

  return (
    <main className="rh-shell" aria-label={ ariaLabel }>
      <div className={ `rh-layout ${shown ? 'show' : ''}`.trim() }>
        <div className="rh-hero">
          {/* Wrapper carries the spacing. BrandBadge paints itself - styled-jsx
              cannot reach into it from here either. */}
          <div className="rh-eyebrow">
            <BrandBadge label={ badgeLabel } />
          </div>

          <h1 className="rh-head">
            <span className="rh-head-line">{ frame }</span>
            <span className="rh-mark" style={ { background: words[ active ]?.tint } }>
              <i className="rh-mark-dot" style={ { background: words[ active ]?.dot } } aria-hidden="true" />
              <span className="rh-cycle" style={ cycleW ? { width: `${cycleW}px` } : undefined }>
                {/* The rotation is visual only: screen readers get the list once and
                    every animated copy is hidden from them. */}
                <span className="rh-sr-only">{ words.map( w => w.word ).join( ', ' ) }</span>
                { words.map( ( w, i ) => (
                  <span
                    key={ w.word }
                    ref={ el => { wordRefs.current[ i ] = el; } }
                    className={ `rh-cyc-word ${i === active ? 'on' : ''}`.trim() }
                      data-wc-translate="true"
                    aria-hidden="true"
                  >{ w.word }</span>
                ) ) }
              </span>
            </span>
          </h1>

          { sub && <p className="rh-sub">{ sub }</p> }
        </div>

        { children }
      </div>

      <style jsx>{`
        /* Font stack declared, not inherited. Measured: these pages render in Inter
           only because @aws-amplify/ui-react's styles.css sets a font-family on body
           that happens to start with Inter - the public pages' typeface was a side
           effect of an auth library's stylesheet. --font-sans in Pages.css has no
           Inter in it, so nothing would have fallen back correctly. */
        .rh-shell{
          min-height:calc(100vh - 69px);
          padding-top:108px;
          box-sizing:border-box;
          background:#fff;
          font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
          color:#1a1a1a;
        }
        .rh-layout{
          width:100%;max-width:1300px;margin:0 auto;
          padding:80px 24px 96px;box-sizing:border-box;
          display:flex;flex-direction:column;gap:96px;
        }
        /* align-items:flex-start replaces an align-self on the badge: without it the
           flex default stretches the pill to the full 1300px measure. */
        .rh-hero{display:flex;flex-direction:column;align-items:flex-start}
        .rh-eyebrow{margin:0 0 20px}

        /* Hero h1 rung: 600, LIGHTER than the 700 section level. That inversion is
           notion's and is intentional - the same guard sits on .vl-head and
           .hero-left h1. Do not "correct" it. */
        .rh-head{
          font-size:clamp(36px,4.3vw,60px);font-weight:600;line-height:1.04;
          /* TRACKING IN em, NOT px. A fixed px value against a fluid clamp() font means the
             OPTICAL tightness changes with the viewport: measured across the breakpoints it ran
             -2.22% to -6.11% of the font size, a 2.75x spread, worst at 768-820px where the font
             is still on its 36px floor while the tracking was chosen for 60px. -0.04em is -4% at
             every size, and it lets both media-query overrides go - restating it per breakpoint
             is what caused the spread. index.tsx fixed this; these three copies had not. */
          letter-spacing:-0.04em;color:rgba(0,0,0,.95);margin:0;max-width:900px;
        }
        /* Blocks, so the frame and the pill never share a line. This is what makes the
           h1's height independent of which word is showing. */
        .rh-head-line{display:block}

        .rh-mark{
          position:relative;display:inline-block;white-space:nowrap;margin-top:.08em;
          padding:.02em .3em .02em .22em;border-radius:9999px;background:#e0f7c8;
          transition:background-color .52s cubic-bezier(.16,1,.3,1);
        }
        /* White shutter, wiping off to the left on entrance so the tint fills in
           rather than switching on. */
        .rh-mark::before{
          content:'';position:absolute;inset:0;background:#fff;border-radius:9999px;
          transform:scaleX(1);transform-origin:right center;
          transition:transform .78s cubic-bezier(.16,1,.3,1) .18s;z-index:0;
        }
        .rh-layout.show .rh-mark::before{transform:scaleX(0)}
        /* .33em matches the dot-to-headline ratio measured on notion.com; the tight
           .18em gap keeps it reading as attached to the word. */
        .rh-mark-dot{
          position:relative;z-index:1;display:inline-block;width:.33em;height:.33em;
          background:#3da35a;border-radius:50%;margin-right:.18em;vertical-align:.14em;
          transform:scale(0);transition:transform .5s cubic-bezier(.34,1.56,.64,1) .72s;
        }
        .rh-layout.show .rh-mark-dot{transform:scale(1)}
        /* Width animates from the measured word so the pill glides instead of
           snapping. overflow:hidden clips the outgoing word as it slides. */
        /* PORTED FROM THE HOME BAND. Four implementations of this hero exist and every one
           carried the same defects; see docs/home-design-audit-20260926.md.

           width:max-content is the RESTING width. cycleW starts null, so the first render
           writes no inline width - and with every word absolutely positioned this box had no
           intrinsic width at all. It computed to 0px and overflow:hidden clipped the word
           away: ~200ms on every load, permanently with no JavaScript. JS still writes an
           explicit px width over this, which is what animates, so the glide is unchanged. */
        .rh-cycle{
          width:max-content;
          position:relative;z-index:1;display:inline-block;
          height:1.06em;line-height:1.06em;vertical-align:baseline;overflow:hidden;
          transition:width .52s cubic-bezier(.16,1,.3,1);will-change:width;
        }
        .rh-cyc-word{
          position:absolute;left:0;top:0;white-space:nowrap;opacity:0;
          transform:translateY(.42em);
          transition:opacity .42s cubic-bezier(.16,1,.3,1),transform .42s cubic-bezier(.16,1,.3,1);
        }
        /* The ACTIVE word returns to flow, which is what gives the box above a real
           intrinsic width. The inactive words stay absolute and keep stacking.

           display:inline-block IS LOAD-BEARING: position:static alone makes this a
           non-replaced inline box whose offsetWidth is 0, so the measuring effect would
           write width:0px over max-content and the pill would collapse on every load WITH
           JavaScript - a 200ms flash turned permanent. */
        .rh-cyc-word.on{opacity:1;transform:translateY(0);position:static;display:inline-block}
        .rh-sr-only{
          position:absolute;width:1px;height:1px;padding:0;margin:-1px;
          overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0;
        }

        /* The single body rung the contract allows: 20px/400/1.4/-.125px at
           rgba(0,0,0,.898). 560px rather than the headline's 900px, because at 20px a
           900px measure runs to ~110 characters a line, well past the 45-75 the rest
           of the site holds to. text-wrap:balance evens the two lines instead of
           leaving one word orphaned; it is pure progressive enhancement, so it needs
           no @supports guard. */
        .rh-sub{
          font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;
          color:rgba(0,0,0,.898);margin:24px 0 0;max-width:560px;text-wrap:balance;
        }

        @media(max-width:767px){
          .rh-shell{min-height:calc(100vh - 85px);padding-top:96px}
          .rh-layout{padding:48px 16px 64px;gap:64px}
          .rh-head{line-height:1.1}
        }
        /* 320px OVERFLOWED BY 11px, and the cause is content rather than layout.
           /contact/ rotates "amend a request" - 279px at the 36px clamp floor - and the pill
           adds ~19px of padding, so the h1 measured 315px inside a 288px measure. Nothing was
           wrong with the box; the widest phrase simply does not fit a 320px screen at 36px.
           32px brings it to ~265px. Scoped to 400px so no other width is retuned, and left as
           a font step rather than clipping the pill, which is the defect this hero was just
           fixed for. */
        @media(max-width:400px){
          .rh-head{font-size:32px}
        }
        /* 280px - Galaxy Fold, folded - still overflowed 7px at 32px, so the step needed a
           second rung rather than a bigger guess. Derived instead of tried: the widest phrase
           on /contact/ is "amend a request" at 279px on the 36px floor, and the pill adds
           ~0.52em of padding, so required width is 279*(F/36) + 0.52F = 8.27F. A 280px
           viewport leaves 248px of measure, giving F <= 30.0px. 28px carries margin for a
           longer phrase being added later, and 280px is the narrowest device that ships. */
        @media(max-width:340px){
          .rh-head{font-size:28px}
        }
        @media(max-width:480px){
        }

        /* The rotation is already stopped in JS; this settles the pill so nothing is
           left mid-transition. */
        @media(prefers-reduced-motion:reduce){
          .rh-mark::before,.rh-mark-dot{transition:none}
          /* scaleX(0) is the RESTING state. scaleX(1) is the START state - a white
             shutter covering the tint - which is what this used to set. It never bit only
             because .rh-layout.show out-specifies it (0,2,1 vs 0,1,1). */
          .rh-mark::before{transform:scaleX(0)}
          .rh-mark-dot{transform:scale(1)}
          .rh-cycle{transition:none}
          .rh-cyc-word{transition:none}
        }
      `}</style>
    </main>
  );
};

export default RotatingHero;
