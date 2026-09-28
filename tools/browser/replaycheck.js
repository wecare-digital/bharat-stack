'use strict';

/**
 * REPLAYCHECK - the two shipped changes the owner reports as "not showing".
 *
 * Both were committed and merged. Both are present in the CSS. The report is still
 * correct, and this harness exists to say WHY in numbers rather than argue about it.
 *
 * WHAT IT MEASURES
 *
 * 1. THE TERMINAL STEP COLOURS. Per step: the --dot custom property, the painted dot,
 *    the .wt-svc pill text, the .wt-name text, and whether the row carries .is-complete.
 *    The claim under test is not "is the CSS there" - it is "how many rows visibly
 *    change". .wt-name.is-complete is gated on step.complete, which is true for exactly
 *    one of the eight steps in STEPS, so the rule can be perfectly correct and still
 *    recolour a single line. Printing all eight side by side is the only way to see that.
 *
 * 2. THE FOOTER TAGLINE REPLAY on hover and on click. Uses getAnimations() for ground
 *    truth - an animation either exists on the element with a playState or it does not -
 *    and ALSO samples background-position over time, because an animation that is
 *    "running" while parked behind a 420ms delay looks identical to one that never
 *    started if you only glance at playState. The delay is the specific suspicion: a
 *    hover shorter than the delay produces literally no movement.
 *
 * Reports, never fails on the perception findings: "one row changed" is a design fact
 * for the owner to rule on, not a regression. It DOES fail if a replay produces no
 * animation at all, because that would be a broken feature.
 *
 * Run: node tools/browser/replaycheck.js   (or BASE=http://localhost:3000 ...)
 */

const { launch, gotoStable } = require( './lib/browser' );
const { target } = require( './lib/serve' );

const hex = ( rgb ) => {
  const m = String( rgb ).match( /\d+/g );
  if ( !m ) return String( rgb );
  return '#' + m.slice( 0, 3 ).map( n => Number( n ).toString( 16 ).padStart( 2, '0' ) ).join( '' );
};
const lum = h => {
  const c = [ 1, 3, 5 ].map( i => parseInt( h.substr( i, 2 ), 16 ) / 255 )
    .map( v => ( v <= 0.03928 ? v / 12.92 : Math.pow( ( v + 0.055 ) / 1.055, 2.4 ) ) );
  return 0.2126 * c[ 0 ] + 0.7152 * c[ 1 ] + 0.0722 * c[ 2 ];
};
const ratio = ( a, b ) => {
  const [ hi, lo ] = [ lum( a ), lum( b ) ].sort( ( x, y ) => y - x );
  return ( ( hi + 0.05 ) / ( lo + 0.05 ) ).toFixed( 2 );
};

let failures = 0;
const assert = ( cond, label, detail ) => {
  if ( cond ) { console.log( `  ok    ${label}` ); } else {
    failures++;
    console.log( `  FAIL  ${label}` );
    if ( detail ) console.log( `        ${detail}` );
  }
};

async function main() {
  const t = await target();
  const browser = await launch();
  console.log( `replaycheck - ${t.mode === 'BASE' ? `BASE ${t.base}` : `static export (out/) on ${t.base}`}\n` );

  try {
    const context = await browser.newContext( { viewport: { width: 1280, height: 900 } } );
    const page = await context.newPage();
    await gotoStable( page, `${t.base}/` );

    /* ---------------- 1. terminal step colours ---------------- */
    console.log( '1. WORKFLOW TERMINAL - step colours as painted' );

    await page.evaluate( () => {
      const el = document.querySelector( '.wt-step' );
      if ( el ) el.scrollIntoView( { block: 'center' } );
    } );
    // The stream reveals steps on a timer and then settles them. Wait for all eight, then
    // for the settle pass, rather than guessing a single sleep.
    await page.waitForFunction(
      () => document.querySelectorAll( '.wt-step' ).length >= 8,
      null, { timeout: 20000 }
    ).catch( () => {} );
    await page.waitForTimeout( 6000 );

    const steps = await page.evaluate( () => {
      return [ ...document.querySelectorAll( '.wt-step' ) ].map( ( el, i ) => {
        const cs = getComputedStyle( el );
        const dot = el.querySelector( '.wt-dot' );
        const svc = el.querySelector( '.wt-svc' );
        const name = el.querySelector( '.wt-name' );
        const tick = el.querySelector( '.wt-tick' );
        return {
          i: i + 1,
          service: svc ? svc.textContent.trim() : '?',
          label: name ? name.textContent.trim().replace( /^✓\s*/, '' ) : '?',
          dotVar: cs.getPropertyValue( '--dot' ).trim(),
          dotPaint: dot ? getComputedStyle( dot ).backgroundColor : null,
          svcColor: svc ? getComputedStyle( svc ).color : null,
          nameColor: name ? getComputedStyle( name ).color : null,
          complete: name ? name.classList.contains( 'is-complete' ) : false,
          hasTick: !!tick,
        };
      } );
    } );

    console.log( '   #  service     --dot     dot painted  pill text   name text   complete' );
    for ( const s of steps ) {
      console.log(
        '   ' + String( s.i ).padEnd( 3 )
        + s.service.padEnd( 12 )
        + s.dotVar.padEnd( 10 )
        + hex( s.dotPaint ).padEnd( 13 )
        + hex( s.svcColor ).padEnd( 12 )
        + hex( s.nameColor ).padEnd( 12 )
        + ( s.complete ? 'yes' : '-' )
      );
    }

    const distinctDots = [ ...new Set( steps.map( s => hex( s.dotPaint ) ) ) ];
    const distinctPills = [ ...new Set( steps.map( s => hex( s.svcColor ) ) ) ];
    const distinctNames = [ ...new Set( steps.map( s => hex( s.nameColor ) ) ) ];
    const recoloured = steps.filter( s => s.complete );

    console.log( '' );
    assert( distinctDots.length >= 4,
      `dots carry ${distinctDots.length} distinct hues: ${distinctDots.join( ' ' )}` );
    console.log( `  note  pill text takes ${distinctPills.length} colour(s): ${distinctPills.join( ' ' )}` );
    console.log( `  note  name text takes ${distinctNames.length} colour(s): ${distinctNames.join( ' ' )}` );
    console.log( `  note  ${recoloured.length} of ${steps.length} rows carry .is-complete, so ${recoloured.length} name(s) leave white` );
    if ( recoloured.length ) {
      for ( const s of recoloured ) {
        console.log( `        row ${s.i} "${s.label}": name ${hex( s.nameColor )} on #000 = ${ratio( hex( s.nameColor ), '#000000' )}:1` );
        console.log( `        that row's pill is still ${hex( s.svcColor )} - the two disagree on the same line` );
      }
    }

    /* ---------------- 2. footer tagline replay ---------------- */
    console.log( '\n2. FOOTER TAGLINE - replay on hover and click' );

    await page.evaluate( () => window.scrollTo( 0, document.body.scrollHeight ) );
    await page.waitForTimeout( 400 );

    const armed = await page.evaluate( () => {
      const tag = document.querySelector( '.ft-tagline' );
      return tag ? { armed: tag.classList.contains( 'is-armed' ), in: tag.classList.contains( 'is-in' ) } : null;
    } );
    assert( armed && armed.armed, `tagline is armed (is-armed=${armed && armed.armed})` );
    assert( armed && armed.in, `tagline is in view (is-in=${armed && armed.in})` );

    // Let the scroll-triggered run finish so any later movement is provably the replay.
    await page.waitForTimeout( 2200 );

    // Sampler: records background-position and animation state every 50ms.
    const installSampler = () => page.evaluate( () => {
      const tag = document.querySelector( '.ft-tagline' );
      window.__samples = [];
      const t0 = performance.now();
      window.__stop = setInterval( () => {
        const anims = tag.getAnimations ? tag.getAnimations() : [];
        window.__samples.push( {
          t: Math.round( performance.now() - t0 ),
          pos: getComputedStyle( tag ).backgroundPositionX,
          anims: anims.map( a => `${a.animationName || '?'}:${a.playState}` ).join( ',' ),
        } );
      }, 50 );
    } );
    const readSamples = () => page.evaluate( () => {
      clearInterval( window.__stop );
      return window.__samples;
    } );

    const summarise = ( label, samples ) => {
      const positions = [ ...new Set( samples.map( s => s.pos ) ) ];
      const moved = positions.length > 1;
      const anims = [ ...new Set( samples.map( s => s.anims ).filter( Boolean ) ) ];
      // First sample whose position differs from the resting value = perceived start.
      const rest = samples[ 0 ] ? samples[ 0 ].pos : null;
      const firstMove = samples.find( s => s.pos !== rest );
      assert( moved, `${label}: background-position moves (${positions.length} distinct values)`,
        moved ? '' : `parked at ${rest} for the whole ${samples[ samples.length - 1 ].t}ms window` );
      console.log( `        animation states seen: ${anims.join( ' | ' ) || 'none'}` );
      if ( firstMove ) {
        /*
         * THE DEAD-TIME ASSERTION, which is the one that would have caught the original
         * report. The stylesheet's 0.42s entrance delay applied to pointer replays too, so
         * the first frame of movement landed at +500ms and any hover shorter than that
         * showed nothing at all. replaySweep now pins animation-delay to 0s on the pointer
         * path. 250ms is the budget: comfortably above the 50ms sampler granularity, far
         * below a delay a reader would read as "broken".
         */
        assert( firstMove.t <= 250,
          `${label}: movement starts within 250ms (+${firstMove.t}ms)`,
          firstMove.t > 250
            ? `${firstMove.t}ms of dead time after the gesture - a shorter ${label} shows nothing. `
              + 'Check animation-delay is cleared on the pointer path in replaySweep.'
            : '' );
        console.log( `        first movement at +${firstMove.t}ms after the trigger` );
      }
      console.log( `        travel: ${positions.slice( 0, 6 ).join( ' -> ' )}${positions.length > 6 ? ' -> ...' : ''}` );
    };

    // --- hover ---
    await page.mouse.move( 5, 5 );
    await page.waitForTimeout( 200 );
    await installSampler();
    await page.hover( '.ft-tagline' );
    await page.waitForTimeout( 2000 );
    summarise( 'hover', await readSamples() );

    // --- click ---
    await page.mouse.move( 5, 5 );
    await page.waitForTimeout( 600 );
    await installSampler();
    await page.click( '.ft-tagline' );
    await page.waitForTimeout( 2000 );
    summarise( 'click', await readSamples() );

    // --- how long is the whole gesture, and is the dark band ever actually over the text ---
    const timing = await page.evaluate( () => {
      const tag = document.querySelector( '.ft-tagline' );
      const cs = getComputedStyle( tag );
      return {
        duration: cs.animationDuration,
        delay: cs.animationDelay,
        name: cs.animationName,
        fill: cs.animationFillMode,
        cursor: cs.cursor,
      };
    } );
    console.log( `\n  note  animation ${timing.name} ${timing.duration} delay ${timing.delay} fill ${timing.fill}` );
    console.log( `  note  cursor on the tagline is "${timing.cursor}" (deliberate: no href, no false affordance)` );

    await context.close();
  } finally {
    await browser.close();
    await t.close();
  }

  console.log( failures ? `\n${failures} FAILED` : '\nall assertions passed' );
  if ( failures ) process.exit( 1 );
}

main().catch( err => { console.error( err ); process.exit( 1 ); } );
