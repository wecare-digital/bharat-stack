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

/**
 * FLATTEN AN rgba() ONTO WHAT IS BEHIND IT.
 *
 * getComputedStyle().backgroundColor returns the AUTHORED value, alpha included -
 * "rgba(37, 99, 235, 0.2)" - not the colour a reader's eye receives. hex() above keeps the
 * first three numbers and discards the alpha, so measuring contrast against its output compares
 * text to the hue at FULL strength rather than to the 20% wash actually painted.
 *
 * That is not a rounding difference, it inverts the verdict. White on messaging lime measured
 * 1.24:1 against #d1f470 and fails hard; against the real chip, lime at 20% over the panel's
 * black, it is 13.55:1 and is the most legible thing on the row. This function is the difference
 * between a probe that measures the design and one that fails it for a reason that is not real.
 */
const flatten = ( rgba, baseHex = '#000000' ) => {
  const m = String( rgba ).match( /[\d.]+/g );
  if ( !m ) return String( rgba );
  const a = m.length > 3 ? Number( m[ 3 ] ) : 1;
  const base = [ 1, 3, 5 ].map( i => parseInt( baseHex.substr( i, 2 ), 16 ) );
  return '#' + m.slice( 0, 3 )
    .map( ( n, i ) => Math.round( Number( n ) * a + base[ i ] * ( 1 - a ) ) )
    .map( v => v.toString( 16 ).padStart( 2, '0' ) ).join( '' );
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
          svcBg: svc ? getComputedStyle( svc ).backgroundColor : null,
          svcBorder: svc ? getComputedStyle( svc ).borderTopColor : null,
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

    /*
     * ASSERTS OPTION A, rather than narrating whatever the panel happens to do.
     *
     * This block has now been wrong twice, in opposite directions, and both times because it
     * described a previous design instead of enforcing the current one. It printed "the two
     * disagree on the same line" unconditionally, which was a real finding while the pill was
     * lime on all eight and a false alarm the moment the pill took its own hue. It then printed
     * "N name(s) leave white", which went stale the moment option A kept every name white. A
     * probe that keeps reporting a fixed defect teaches its reader to skip the output, which is
     * worse than having no probe.
     *
     * So the invariants are stated as assertions. Option A is: hue on the dot and the chip,
     * never on prose. If someone recolours a name later, this fails and says why.
     */
    assert( distinctDots.length >= 4,
      `dots carry ${distinctDots.length} distinct hues: ${distinctDots.join( ' ' )}` );

    /*
     * THE PILL LABEL IS WHITE AND ITS CHIP CARRIES THE HUE. This assertion used to require the
     * label itself to carry five hues, which was the design until it was measured properly:
     * at 11.5px, blue cleared the 4.5:1 floor by 0.01 and purple by 0.06, and the owner
     * reported `auth` as unreadable. The floor is written for ~16px text. So hue moved to the
     * chip's fill and border, where there is no legibility floor at all.
     */
    const nonWhitePills = steps.filter( s => hex( s.svcColor ) !== '#ffffff' );
    assert( nonWhitePills.length === 0,
      `all ${steps.length} pill labels are #ffffff`,
      nonWhitePills.length
        ? `${nonWhitePills.map( s => `${s.service} is ${hex( s.svcColor )}` ).join( ', ' )}. `
          + 'A hue on 11.5px text cleared 4.5:1 by hundredths and read as murky - see the note '
          + 'on .wt-svc. Hue belongs on the chip, not the letters.'
        : '' );

    const distinctPillBgs = [ ...new Set( steps.map( s => flatten( s.svcBg ) ) ) ];
    assert( distinctPillBgs.length >= 4,
      `pill chips carry ${distinctPillBgs.length} distinct fills: ${distinctPillBgs.join( ' ' )}`,
      distinctPillBgs.length < 4
        ? 'the chip fill is what identifies the service now - one fill means .wt-svc lost rgba(var(--rgb),.20)'
        : '' );

    const nonWhite = steps.filter( s => hex( s.nameColor ) !== '#ffffff' );
    assert( nonWhite.length === 0,
      `all ${steps.length} step names are #ffffff at 21:1 (option A)`,
      nonWhite.length
        ? `${nonWhite.map( s => `row ${s.i} is ${hex( s.nameColor )}` ).join( ', ' )}. `
          + 'Option A keeps hue off prose: on a sentence a hue reads as a severity, which is why '
          + 'amber on "A provider failed, nobody noticed" was rejected. See docs/step-review.md.'
        : '' );

    /*
     * 7:1, NOT 4.5:1, and the higher bar is the entire point of the change. This label is
     * 11.5px; the 4.5:1 floor assumes roughly 16px. Holding small text to the AA minimum is how
     * the previous palette passed every gate and still could not be read, so the floor here is
     * AAA and the measurement is against the chip's REAL painted background rather than a
     * recomputed tint.
     */
    const pillRatio = s => Number( ratio( hex( s.svcColor ), flatten( s.svcBg, '#000000' ) ) );
    const pillFloor = steps.filter( s => pillRatio( s ) < 7 );
    assert( pillFloor.length === 0,
      `every pill label clears 7:1 on its own chip (11.5px text, AAA not AA)`,
      pillFloor.map( s => `${s.service} ${pillRatio( s ).toFixed( 2 )}:1` ).join( ', ' ) );
    const worst = steps.map( s => ( { s, r: pillRatio( s ) } ) ).sort( ( a, b ) => a.r - b.r )[ 0 ];
    console.log( `  note  lowest pill contrast is ${worst.s.service} at ${worst.r.toFixed( 2 )}:1 on ${flatten( worst.s.svcBg )} (chip flattened onto #000)` );

    console.log( `  note  ${recoloured.length} of ${steps.length} rows carry .is-complete; it is a state hook with no paint of its own` );
    for ( const s of recoloured ) {
      console.log( `        row ${s.i} "${s.label}": name ${hex( s.nameColor )} = ${ratio( hex( s.nameColor ), '#000000' )}:1, pill ${hex( s.svcColor )}, tick takes the hue` );
    }

    /* ---------------- 2. the loop, and the control that legitimises it ---------------- */
    console.log( '\n2. WORKFLOW TERMINAL - continuous loop and its pause control' );

    /*
     * The panel played once and held for a while, and it looped before that. The original loop
     * was removed for two reasons, and this asserts that neither came back with it:
     *
     *   1. WCAG 2.2.2 - motion over five seconds must be pausable. A cycle is ~15.8s, so the
     *      control is not optional. It also must be OUTSIDE the aria-hidden window subtree,
     *      because a focusable node in there is in the tab order and absent from the a11y tree.
     *   2. The panel emptied itself. The old reset rewound `shown` to 0, leaving one 26px line
     *      in a 551px box. The row count must therefore never fall once it has reached eight.
     */
    const control = await page.evaluate( () => {
      const btn = document.querySelector( '.wt-play' );
      if ( !btn ) return null;
      const win = document.querySelector( '.wt-window' );
      return {
        exists: true,
        label: btn.textContent.trim(),
        tag: btn.tagName,
        insideAriaHidden: !!( win && win.contains( btn ) ),
        ariaPressed: btn.getAttribute( 'aria-pressed' ),
      };
    } );
    assert( control && control.exists, 'a pause control exists (WCAG 2.2.2 for a ~15.8s cycle)' );
    if ( control ) {
      assert( control.tag === 'BUTTON', `the control is a real <button> (${control.tag})` );
      assert( !control.insideAriaHidden,
        'the control is OUTSIDE the aria-hidden window subtree',
        control.insideAriaHidden
          ? 'a focusable node inside aria-hidden is reachable by keyboard and announced as nothing'
          : '' );
    }

    // Watch the row count and the settle frontier for long enough to catch a restart.
    const watched = await page.evaluate( () => new Promise( resolve => {
      const samples = [];
      const t0 = performance.now();
      const tick = setInterval( () => {
        const rows = document.querySelectorAll( '.wt-step' );
        let frontier = -1;
        rows.forEach( ( r, i ) => { if ( r.classList.contains( 'is-done' ) ) frontier = i; } );
        samples.push( { t: Math.round( performance.now() - t0 ), rows: rows.length, frontier } );
        if ( performance.now() - t0 > 34000 ) { clearInterval( tick ); resolve( samples ); }
      }, 250 );
    } ) );

    const maxRows = Math.max( ...watched.map( s => s.rows ) );
    const afterFull = watched.filter( s => s.rows >= maxRows );
    const minAfterFull = Math.min( ...afterFull.map( s => s.rows ) );
    assert( maxRows === 8, `all 8 rows mount (${maxRows})` );
    assert( minAfterFull === 8,
      'the row count never falls once all 8 have mounted - the panel never empties',
      minAfterFull < 8 ? `dropped to ${minAfterFull} rows, which is the old reset defect` : '' );

    // A restart shows up as the settle frontier going BACKWARDS.
    let rewinds = 0;
    for ( let i = 1; i < watched.length; i++ ) {
      if ( watched[ i ].frontier < watched[ i - 1 ].frontier ) rewinds++;
    }
    assert( rewinds >= 1,
      `the sequence restarts - settle frontier rewound ${rewinds}x in 34s`,
      rewinds === 0 ? 'no restart seen; the panel is still one-shot' : '' );

    // Pausing must stop it. Press, then confirm the frontier stops moving.
    await page.click( '.wt-play' );
    const paused = await page.evaluate( () => new Promise( resolve => {
      const read = () => {
        let f = -1;
        document.querySelectorAll( '.wt-step' ).forEach( ( r, i ) => { if ( r.classList.contains( 'is-done' ) ) f = i; } );
        return f;
      };
      const seen = new Set();
      const t0 = performance.now();
      const tick = setInterval( () => {
        seen.add( read() );
        if ( performance.now() - t0 > 6000 ) {
          clearInterval( tick );
          const anims = [ ...document.querySelectorAll( '.wt-step.is-running .wt-dot' ) ]
            .flatMap( d => ( d.getAnimations ? d.getAnimations() : [] ) )
            .map( a => a.playState );
          resolve( { frontiers: [ ...seen ], pulsing: anims } );
        }
      }, 250 );
    } ) );
    assert( paused.frontiers.length <= 1,
      `paused: the sequence stops advancing (frontier held at ${paused.frontiers.join( ',' )})`,
      paused.frontiers.length > 1 ? 'it kept stepping after pause' : '' );
    assert( paused.pulsing.length === 0,
      'paused: the dot pulse stops too, not just the timers',
      paused.pulsing.length ? `${paused.pulsing.length} pulse animation(s) still ${paused.pulsing.join( ',' )}` : '' );

    // Leave it playing so later sections see the normal state.
    await page.click( '.wt-play' );

    /* ---------------- 3. footer tagline replay ---------------- */
    console.log( '\n3. FOOTER TAGLINE - replay on hover and click' );

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
