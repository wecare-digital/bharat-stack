'use strict';

/**
 * footerprobe - does the footer tagline entrance actually play, and does a reader see it?
 *
 * WHY THIS EXISTS. The owner reported the "Trusted everyday services for Bharat" entrance
 * as "not showing" twice, and twice the answer given was that the CSS is live. It is: the
 * deployed stylesheet carries .ft-tagline.is-armed and .is-in with a 0.52s transition, and
 * curl finds them. But "the rule shipped" and "a person sees it" are different claims, and
 * only the first one had been checked. Asserting the second one without measuring it is how
 * a report ends up arguing with the person looking at the page.
 *
 * WHAT IT MEASURES
 *   - the classes arrive: .is-armed from the effect, then .is-in from the observer
 *   - WHETHER THE ARMED STATE WAS EVER PAINTED. The effect adds .is-armed after first
 *     paint. If the footer is already on screen, .is-armed and .is-in can land inside one
 *     frame, the browser has no start state to transition from, and the reveal is skipped
 *     outright. That failure looks exactly like "not showing", and no amount of reading the
 *     stylesheet reveals it.
 *   - how many frames sit mid-fade, which separates a fade from a snap
 *   - how far the line travels, in px. This is the perception question rather than the
 *     correctness one: a 6px rise on a 15px line is near the floor of what gets noticed.
 *
 * Run: node tools/browser/footerprobe.js          (needs out/ - npm run build)
 *      BASE=http://localhost:3000 node tools/browser/footerprobe.js
 */

const { target } = require( './lib/serve' );
const { launch, gotoStable } = require( './lib/browser' );

const results = [];
const ok = ( name, detail ) => results.push( { pass: true, name, detail } );
const bad = ( name, detail ) => results.push( { pass: false, name, detail } );
const note = ( name, detail ) => results.push( { note: true, name, detail } );

const VIEWPORTS = [
  { width: 1280, height: 800, label: 'desktop 1280' },
  { width: 390, height: 844, label: 'phone 390' },
];

( async () => {
  const t = await target();
  const browser = await launch();

  try {
    for ( const vp of VIEWPORTS ) {
      const page = await browser.newPage( { viewport: { width: vp.width, height: vp.height } } );

      /* Instrument before any page script runs. One sample per frame for ~4s: a transition
       * that plays leaves a spread of opacities, one that never starts leaves two values. */
      await page.addInitScript( () => {
        window.__frames = [];
        const tick = () => {
          const el = document.querySelector( '.ft-tagline' );
          if ( el ) {
            window.__frames.push( {
              o: Number( getComputedStyle( el ).opacity ),
              armed: el.classList.contains( 'is-armed' ),
              in: el.classList.contains( 'is-in' ),
            } );
          }
          if ( window.__frames.length < 260 ) requestAnimationFrame( tick );
        };
        requestAnimationFrame( tick );
      } );

      await gotoStable( page, `${t.base}/` );

      const present = await page.$( '.ft-tagline' );
      if ( !present ) { bad( `${vp.label}: .ft-tagline present`, 'not found' ); await page.close(); continue; }

      const inViewAtLoad = await page.evaluate( () => {
        const r = document.querySelector( '.ft-dash' ).getBoundingClientRect();
        return r.top < window.innerHeight && r.bottom > 0;
      } );
      note( `${vp.label}: footer on screen at load`, String( inViewAtLoad ) );

      /* Arrive at the footer the way a reader does. */
      await page.evaluate( () => document.querySelector( '.ft-dash' ).scrollIntoView( { block: 'center' } ) );
      // 2600ms: the rise is 560ms and the colour sweep runs 420-1570ms, so this samples the
      // SETTLED state rather than a frame mid-animation. 1400ms caught the sweep still moving,
      // which made the end-position assertion pass on a value that was not the end.
      await page.waitForTimeout( 2600 );

      const state = await page.evaluate( () => {
        const el = document.querySelector( '.ft-tagline' );
        const dash = document.querySelector( '.ft-dash' );
        return {
          armed: el.classList.contains( 'is-armed' ),
          in: el.classList.contains( 'is-in' ),
          opacity: Number( getComputedStyle( el ).opacity ),
          dashArmed: dash.classList.contains( 'is-armed' ),
          dashIn: dash.classList.contains( 'is-in' ),
        };
      } );
      const frames = await page.evaluate( () => window.__frames );

      if ( state.armed ) ok( `${vp.label}: tagline armed by JS`, '.is-armed added' );
      else bad( `${vp.label}: tagline armed by JS`, 'the effect never ran - nothing to reveal' );

      if ( state.in ) ok( `${vp.label}: tagline revealed`, '.is-in added' );
      else bad( `${vp.label}: tagline revealed`, 'observer never fired - the line is stuck at opacity 0' );

      if ( state.opacity > 0.99 ) ok( `${vp.label}: tagline ends readable`, `opacity ${state.opacity}` );
      else bad( `${vp.label}: tagline ends readable`, `opacity ${state.opacity} - it did not finish` );

      if ( state.dashIn ) ok( `${vp.label}: dash revealed`, '.is-in added' );
      else bad( `${vp.label}: dash revealed`, 'the lime dash never drew' );

      /* The frame evidence. */
      const armedOnly = frames.filter( f => f.armed && !f.in ).length;
      const midFade = frames.filter( f => f.o > 0.02 && f.o < 0.98 ).length;
      note( `${vp.label}: frames sampled`, String( frames.length ) );

      if ( armedOnly >= 1 ) ok( `${vp.label}: start state was painted`, `${armedOnly} frame(s) hidden before .is-in` );
      else bad( `${vp.label}: start state was painted`, '.is-armed and .is-in landed in one frame - no start state to animate from, so the reveal is SKIPPED and the line simply appears' );

      if ( midFade >= 3 ) ok( `${vp.label}: it fades rather than snaps`, `${midFade} frames between transparent and opaque` );
      else bad( `${vp.label}: it fades rather than snaps`, `${midFade} mid-fade frame(s)` );

      /* Travel, measured off the real computed transform.
       *
       * THE TRANSITION HAS TO BE SUPPRESSED FIRST. Dropping .is-in and reading the rect
       * straight after returns the RESTING position, because the transform is mid-transition
       * and has not moved yet - the first version of this check reported 0.0px at both widths
       * and that was the harness measuring itself, not the page. transition:none makes the
       * armed transform apply in the same frame. */
      const travel = await page.evaluate( () => {
        const el = document.querySelector( '.ft-tagline' );
        const prev = el.style.transition;
        el.style.transition = 'none';
        const rest = el.getBoundingClientRect().top;
        el.classList.remove( 'is-in' );
        void el.offsetHeight;
        const start = el.getBoundingClientRect().top;
        el.classList.add( 'is-in' );
        void el.offsetHeight;
        el.style.transition = prev;
        return Math.abs( start - rest );
      } );
      /*
       * ASSERTED, not just printed. 6px over 520ms was the shipped value and the owner could
       * not see it; the frame counts above were all green at the time, which is what makes
       * this the load-bearing number. 12px is the floor, so a tidy-up cannot shrink the rise
       * back to something that technically animates and practically does not.
       */
      if ( travel >= 12 ) ok( `${vp.label}: the rise is big enough to see`, `${travel.toFixed( 1 )}px` );
      else bad( `${vp.label}: the rise is big enough to see`, `${travel.toFixed( 1 )}px - under the 12px floor; it plays but a reader does not notice it` );

      /*
       * THE COLOUR SWEEP, and the thing about it that can hide the entire line.
       *
       * background-clip:text works by making the text transparent and painting a gradient
       * through it, so the gradient MUST still cover the element once the animation settles. A
       * background percentage positions the image at p x (elementWidth - imageWidth); the image
       * is 300% wide, so the origin is -2W x p, and only p between 0% and 100% covers the
       * element at all. The first version of this animation ended at -40%, putting the origin
       * at +0.8W - which left the first four fifths of the line with no gradient behind
       * transparent text. An invisible tagline, permanently, after the sweep finished.
       *
       * It passed every obvious check: the darkest rendered pixel was identical either way,
       * because the fragment that WAS painted carried the right colour. Counting ink pixels in
       * a screenshot of the line is what exposed it - 165 against 822 for the same sentence.
       */
      /*
       * WAIT AGAIN, because the travel measurement above perturbs the thing being measured: it
       * removes .is-in to read the armed position and puts it back, which RESTARTS the colour
       * sweep from its first keyframe. Without this the next two checks sampled a line 200ms
       * into a fresh 420ms delay and reported background-position 100% as "the end" - a value
       * that happens to satisfy the assertion for the wrong reason, which is worse than failing.
       * 1900ms clears the 420ms delay plus the 1150ms run.
       */
      await page.waitForTimeout( 1900 );

      const sweep = await page.evaluate( () => {
        const el = document.querySelector( '.ft-tagline' );
        const cs = getComputedStyle( el );
        const width = el.getBoundingClientRect().width;
        const raw = cs.backgroundPosition;
        return {
          hasGradient: /gradient/.test( cs.backgroundImage ),
          clipsToText: /text/.test( cs.webkitBackgroundClip || cs.backgroundClip || '' ),
          endPct: /%/.test( raw ) ? parseFloat( raw ) : ( width ? ( parseFloat( raw ) / ( -2 * width ) ) * 100 : NaN ),
        };
      } );

      if ( sweep.hasGradient && sweep.clipsToText ) ok( `${vp.label}: the colour sweep is applied`, 'gradient clipped to the text' );
      else bad( `${vp.label}: the colour sweep is applied`, `gradient=${sweep.hasGradient} clip-to-text=${sweep.clipsToText}` );

      if ( sweep.endPct >= -0.5 && sweep.endPct <= 100.5 ) {
        ok( `${vp.label}: the sweep settles covering the whole line`, `background-position ${sweep.endPct.toFixed( 1 )}%` );
      } else {
        bad( `${vp.label}: the sweep settles covering the whole line`, `background-position ${sweep.endPct.toFixed( 1 )}% - outside 0..100%, so part of the line has no gradient behind transparent text and is INVISIBLE` );
      }

      /*
       * AND THE RENDERED RESULT, because the position being in range is the mechanism and this
       * is the outcome. Counts glyph pixels in a screenshot of the settled line: if the
       * gradient does not cover it, most of the ink is simply missing. 600 is a floor measured
       * against 822 on the real sentence at both widths - loose enough to survive a font
       * change, tight enough that the -40% bug (165) fails it.
       */
      /*
       * AND THE RENDERED RESULT, because the position being in range is the MECHANISM and this
       * is the OUTCOME. Screenshot the settled line and count its glyph pixels: if the gradient
       * does not cover the box, most of the ink is simply absent while every computed style
       * still looks correct. That is precisely how the -40% bug survived a first review.
       */
      const shot = await ( await page.$( '.ft-tagline' ) ).screenshot();
      const inkPixels = await page.evaluate( async ( dataUrl ) => {
        const img = new Image();
        img.src = dataUrl;
        await img.decode();
        const canvas = document.createElement( 'canvas' );
        canvas.width = img.width; canvas.height = img.height;
        const ctx = canvas.getContext( '2d' );
        ctx.drawImage( img, 0, 0 );
        const data = ctx.getImageData( 0, 0, img.width, img.height ).data;
        let n = 0;
        // 200 of 255 separates glyph pixels and their antialiasing from the white ground.
        for ( let i = 0; i < data.length; i += 4 ) {
          if ( ( data[ i ] + data[ i + 1 ] + data[ i + 2 ] ) / 3 < 200 ) n++;
        }
        return n;
      }, 'data:image/png;base64,' + shot.toString( 'base64' ) );

      /* 600 is a floor measured against 822 on the real sentence at both widths: loose enough
       * to survive a font or copy change, tight enough that the -40% bug's 165 fails it. */
      if ( inkPixels >= 600 ) ok( `${vp.label}: the whole line is actually painted`, `${inkPixels} glyph pixels` );
      else bad( `${vp.label}: the whole line is actually painted`, `${inkPixels} glyph pixels - the gradient is not covering the box, so part of the line is invisible behind transparent text` );

      await page.close();
    }
  } finally {
    await browser.close();
    await t.close();
  }

  console.log( `\ntarget: ${t.base} (${t.mode})\n` );
  for ( const r of results ) {
    const tag = r.note ? 'note' : r.pass ? 'ok  ' : 'FAIL';
    console.log( `  ${tag}  ${r.name.padEnd( 42 )} ${r.detail}` );
  }
  const fails = results.filter( r => r.pass === false ).length;
  const oks = results.filter( r => r.pass === true ).length;
  console.log( `\n${oks} ok, ${fails} FAIL\n` );
  process.exit( fails ? 1 : 0 );
} )();
