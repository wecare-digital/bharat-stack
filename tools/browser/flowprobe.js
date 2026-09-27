'use strict';

/**
 * flowprobe - the home page's SECOND band, section.home-flow, measured as claims.
 *
 * The companion to homeprobe.js, which owns the top band. Same contract: every line of
 * output is an assertion that either holds or does not, so a finding about this band is
 * re-runnable rather than re-argued. It is expected to FAIL while findings are open - the
 * failures are the record of what is still outstanding.
 *
 * WHAT THIS BAND IS: a two-column grid. Left, a 1fr column holding WorkflowTerminal - a
 * 650px black panel that streams eight fake service steps on timers. Right, a fixed 380px
 * sticky column with the section heading, a lead and three beats.
 *
 * THE THREE THINGS THAT NEEDED A BROWSER, and could not be read off the source:
 *
 *   1. HOW LONG THE PANEL IS EMPTY. The stream is gated on IntersectionObserver at 0.25
 *      and starts 600ms after it fires, so at first paint .wt-space is a 551px void holding
 *      one 26px line. Source can tell you the delay exists; only a clock can tell you the
 *      panel is 96% empty while it runs.
 *
 *   2. THAT IT PLAYS ONCE. This started as a measurement of the LOOP period - 15.8s, restart
 *      edge to restart edge - which failed WCAG 2.2.2: content moving automatically for over
 *      five seconds with no pause, stop or hide, and a panel that reset itself to 95% empty
 *      on every cycle. The sequence now plays once and holds, so the assertion is inverted:
 *      it watches for a restart that must not come. Proving an absence needs a bounded
 *      window, so it watches for 18s - longer than the cycle it replaced, so a surviving
 *      loop cannot hide inside it.
 *
 *   3. CONTRAST INSIDE THE PANEL. Every colour in there is a white alpha over #000 or over
 *      the #3b271a title bar. An alpha is not a colour until it is composited, so the ratio
 *      cannot be looked up - it has to be computed from what the pixel actually became.
 *      Done here with the WCAG formula against the real composited parent background.
 *
 * Run: node tools/browser/flowprobe.js        (needs out/ - see README.md)
 */

const { target } = require( './lib/serve' );
const { launch, gotoStable } = require( './lib/browser' );

let pass = 0, fail = 0;
const rows = [];
const ok = ( cond, name, detail ) => {
  rows.push( { cond, name, detail } );
  if ( cond ) pass++; else fail++;
  console.log( `  ${cond ? 'ok  ' : 'FAIL'} ${name}${detail ? ` — ${detail}` : ''}` );
};

/** The WCAG contrast helpers, run in the page so they read composited pixels. */
const CONTRAST_FN = `
  function lin(c){c/=255;return c<=0.03928?c/12.92:Math.pow((c+0.055)/1.055,2.4)}
  function lum(r,g,b){return 0.2126*lin(r)+0.7152*lin(g)+0.0722*lin(b)}
  function parse(s){var m=s.match(/rgba?\\(([^)]+)\\)/);if(!m)return null;
    var p=m[1].split(',').map(function(x){return parseFloat(x)});
    return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1}}
  function over(f,b){return {r:f.r*f.a+b.r*(1-f.a),g:f.g*f.a+b.g*(1-f.a),b:f.b*f.a+b.b*(1-f.a),a:1}}
  /**
   * The backdrop a text colour composites onto.
   *
   * STARTS AT THE ELEMENT ITSELF, AND THAT WAS THE BUG THIS REPLACES. The first version
   * walked up from the element and returned the first background with any alpha - which
   * for .wt-svc is its OWN rgba(209,244,112,.14). So it compared lime text against
   * un-composited lime and reported 1:1, a defect that does not exist. An element's own
   * translucent background is part of its backdrop, not its foreground.
   *
   * STACKS EVERY TRANSLUCENT LAYER, rather than stopping at the first one. .wt-svc sits on
   * .wt-step on .wt-space on .wt-window, and two of those are translucent; taking only the
   * nearest would still be wrong, just less wrong. Collected outermost-first, then
   * composited downwards, which is the order a browser paints them.
   */
  function bg(el){
    var layers=[];
    for(var n=el;n;n=n.parentElement){
      var c=parse(getComputedStyle(n).backgroundColor);
      if(c&&c.a>0){layers.unshift(c);if(c.a===1)break}
    }
    var base={r:255,g:255,b:255,a:1};
    for(var i=0;i<layers.length;i++)base=over(layers[i],base);
    return base}
  function ratio(el){var fg=parse(getComputedStyle(el).color);if(!fg)return null;var b=bg(el);
    var c=over(fg,b);
    var L1=lum(c.r,c.g,c.b),L2=lum(b.r,b.g,b.b);
    var hi=Math.max(L1,L2),lo=Math.min(L1,L2);
    return Math.round(((hi+0.05)/(lo+0.05))*100)/100}
`;

( async () => {
  const t = await target();
  const browser = await launch();
  const ctx = await browser.newContext( { viewport: { width: 1280, height: 900 } } );
  const page = await ctx.newPage();
  await gotoStable( page, `${t.base}/` );

  console.log( '\nsection.home-flow — band 2 of 3\n' );

  // ---------------------------------------------------------------- layout
  console.log( 'LAYOUT' );
  const L = await page.evaluate( () => {
    const b = s => { const e = document.querySelector( s ); if ( !e ) return null;
      const r = e.getBoundingClientRect();
      return { w: Math.round( r.width ), h: Math.round( r.height ), t: Math.round( r.top + window.scrollY ) }; };
    const cs = ( s, p ) => { const e = document.querySelector( s ); return e ? getComputedStyle( e )[ p ] : null; };
    return {
      flow: b( '.home-flow' ), panel: b( '.home-flow-panel' ), copy: b( '.home-flow-copy' ),
      win: b( '.wt-window' ), space: b( '.wt-space' ), bar: b( '.wt-bar' ), foot: b( '.wt-foot' ),
      cols: cs( '.home-flow', 'gridTemplateColumns' ), gap: cs( '.home-flow', 'gap' ),
      copyPos: cs( '.home-flow-copy', 'position' ), copyTop: cs( '.home-flow-copy', 'top' ),
      spaceOverflow: cs( '.wt-space', 'overflowY' ),
      spaceHidden: document.querySelector( '.wt-window' )?.getAttribute( 'aria-hidden' ),
      spaceTabbable: !!document.querySelector( '.wt-space' )?.hasAttribute( 'tabindex' ),
      h2: cs( '.home-flow-title', 'fontSize' ) + '/' + cs( '.home-flow-title', 'fontWeight' ),
      h1: cs( '.home-head', 'fontSize' ) + '/' + cs( '.home-head', 'fontWeight' ),
      focusable: document.querySelectorAll( '.home-flow a[href],.home-flow button,.home-flow [tabindex]' ).length,
    };
  } );

  ok( L.cols === '808px 380px', 'grid is 1fr + a fixed 380px copy column', L.cols );
  ok( L.win.h === 650, 'the terminal panel is 650px tall', `${L.win.w}x${L.win.h}` );
  ok( L.copy.h < L.win.h, 'the copy column is shorter than the panel',
    `copy ${L.copy.h}px vs panel ${L.win.h}px — ${L.win.h - L.copy.h}px of sticky travel` );
  ok( L.copyPos === 'sticky' && L.copyTop === '128px', 'the copy column is sticky at 128px',
    `${L.copyPos} top:${L.copyTop}` );
  ok( L.focusable === 0, 'nothing in this band is focusable', `${L.focusable} focusable` );
  ok( L.spaceHidden === 'true', 'the terminal window is aria-hidden', String( L.spaceHidden ) );
  ok( !( L.spaceOverflow === 'auto' && !L.spaceTabbable ),
    'the scrollable stream is reachable by keyboard (WCAG 2.1.1)',
    `overflow-y:${L.spaceOverflow}, tabindex absent — a scroll region no keyboard can scroll` );

  // ------------------------------------------------------- the empty panel
  console.log( '\nTHE PANEL AT FIRST PAINT' );
  const fresh = await ctx.newPage();
  await fresh.goto( `${t.base}/`, { waitUntil: 'load' } );
  const atPaint = await fresh.evaluate( () => {
    const sp = document.querySelector( '.wt-space' );
    const steps = document.querySelectorAll( '.wt-step' );
    const used = [ ...sp.children ].reduce( ( a, c ) => a + c.getBoundingClientRect().height, 0 );
    return { h: Math.round( sp.getBoundingClientRect().height ), steps: steps.length, used: Math.round( used ) };
  } );
  ok( atPaint.steps > 0, 'the stream has content at first paint',
    `${atPaint.steps} steps — ${atPaint.used}px of ${atPaint.h}px used, ` +
    `${Math.round( ( 1 - atPaint.used / atPaint.h ) * 100 )}% of the panel is empty` );

  // Sample how the fill grows, so "empty" is a curve rather than one unlucky frame.
  const samples = [];
  for ( const ms of [ 0, 600, 1200, 2400, 4800, 8000, 12500, 13000 ] ) {
    await fresh.waitForTimeout( ms - ( samples.length ? samples[ samples.length - 1 ].ms : 0 ) );
    samples.push( { ms, ...await fresh.evaluate( () => {
      const sp = document.querySelector( '.wt-space' );
      const used = [ ...sp.children ].reduce( ( a, c ) => a + c.getBoundingClientRect().height, 0 );
      return { steps: document.querySelectorAll( '.wt-step' ).length, used: Math.round( used ),
        foot: document.querySelector( '.wt-foot-right' )?.textContent || '' };
    } ) } );
  }
  console.log( '\n  fill over time (panel inner height ' + atPaint.h + 'px)' );
  console.log( '    t(ms)  steps  used px  % filled  footer' );
  for ( const s of samples ) {
    console.log( `    ${String( s.ms ).padStart( 5 )}  ${String( s.steps ).padStart( 5 )}` +
      `  ${String( s.used ).padStart( 7 )}  ${String( Math.round( s.used / atPaint.h * 100 ) ).padStart( 7 )}%  ${s.foot}` );
  }

  // --------------------------------------------------------- the loop period
  //
  // MEASURED RESTART-TO-RESTART, ON A PAGE THAT IS ALREADY MID-CYCLE.
  // The first version started its clock on a page that had been open for 13 seconds - the
  // fill samples above - so the stream was already finished, and it reported "complete at
  // 100ms": the time to NOTICE the end state, not the time to reach it. Timing a loop from
  // an arbitrary point in that loop cannot give its period.
  // So this waits for a restart edge first, uses THAT as t0, and measures to the next one.
  // The number then means one full cycle regardless of when observation began.
  // ---------------------------------------------------- one-shot, not a loop
  //
  // THIS ASSERTION IS INVERTED FROM HOW IT STARTED, because the behaviour it described was
  // fixed rather than accepted. It used to measure the loop period - 15.8s, restart edge to
  // restart edge - and fail on WCAG 2.2.2: content moving automatically for over five seconds
  // with no pause, stop or hide. It also meant the panel reset to 95% empty every cycle.
  //
  // The sequence now plays once and holds, so the correct assertion is the opposite one: that
  // no restart happens. Watching for an absence needs a bounded window, so this waits for
  // completion and then watches for longer than one old cycle (15.8s) - if the loop were still
  // there, it would restart inside that window and be caught.
  console.log( '\nONE-SHOT, NOT A LOOP' );
  const once = await fresh.evaluate( () => new Promise( resolve => {
    const steps = () => document.querySelectorAll( '.wt-step' ).length;
    const state = () => document.querySelector( '.wt-foot-left' )?.textContent.trim();
    const t0 = performance.now();
    let completedAt = null;
    const iv = setInterval( () => {
      if ( completedAt === null && steps() === 8 && state() === 'complete' ) {
        completedAt = performance.now() - t0;
      }
      // A restart is the step list emptying out again, which is what the old reset did.
      if ( completedAt !== null && steps() < 8 ) {
        clearInterval( iv );
        resolve( { restarted: true, completedAt: Math.round( completedAt ),
          restartedAt: Math.round( performance.now() - t0 ) } );
      }
    }, 100 );
    // 18s: longer than the 15.8s cycle this replaced, so a surviving loop cannot hide.
    setTimeout( () => {
      clearInterval( iv );
      resolve( { restarted: false, completedAt: completedAt === null ? null : Math.round( completedAt ),
        steps: steps(), state: state(), watched: 18000 } );
    }, 18000 );
  } ) );
  // The offset is measured from when THIS watcher started, not from page load - the fill
  // sampling above has already run ~13s on the same page, so completion is normally already
  // reached by the time the watch begins. Saying "all 8 steps at ~0.1s" would read as a
  // streaming time, which it is not; the fill curve above is where the real ~12.5s is.
  ok( once.completedAt !== null, 'the sequence reaches completion',
    once.completedAt === null ? 'never completed inside 18s'
      : once.completedAt < 500 ? 'already complete when the watch began — see the fill curve above for the real timing'
        : `all 8 steps ${( once.completedAt / 1000 ).toFixed( 1 )}s into the watch window` );
  ok( !once.restarted, 'it plays once and holds — no loop (WCAG 2.2.2)',
    once.restarted
      ? `restarted at ${( once.restartedAt / 1000 ).toFixed( 1 )}s — the loop is still there`
      : `still "${once.state}" with ${once.steps}/8 steps after watching ${once.watched / 1000}s, ` +
        'longer than the 15.8s cycle this replaced' );

  await fresh.close();

  // ------------------------------------------------------------- contrast
  //
  // WAIT FOR THE WHOLE STREAM FIRST. Chips, lanes and checks only exist once the steps
  // carrying them have arrived, and the first version measured too early and printed
  // "not rendered yet" for four of the fourteen selectors - which reads as a harness that
  // cannot see them rather than a stream that had not got there. The completion state is
  // held for 3.2s before the reset, which is a wide enough window to measure inside.
  console.log( '\nCONTRAST INSIDE THE PANEL (WCAG 1.4.3, composited)' );
  await page.waitForFunction(
    () => document.querySelectorAll( '.wt-step' ).length === 8
      && document.querySelector( '.wt-lane' ) && document.querySelector( '.wt-chip' ),
    null, { timeout: 40000 }
  );
  const contrast = await page.evaluate( `(() => {
    ${CONTRAST_FN}
    const out = [];
    const SEL = ['.wt-bar-title','.wt-bar-state','.wt-request','.wt-desc','.wt-time','.wt-infra',
      '.wt-chip','.wt-svc','.wt-lane-name','.wt-lane-detail','.wt-check','.wt-foot-left','.wt-foot-right','.wt-name'];
    for (const s of SEL) {
      const el = document.querySelector(s);
      if (!el) { out.push({ sel:s, missing:true }); continue; }
      const cs = getComputedStyle(el);
      const fs = parseFloat(cs.fontSize), fw = parseInt(cs.fontWeight,10) || 400;
      const large = fs >= 24 || (fs >= 18.66 && fw >= 700);
      out.push({ sel:s, fs, fw, ratio: ratio(el), need: large ? 3 : 4.5 });
    }
    return out;
  })()` );
  for ( const c of contrast ) {
    if ( c.missing ) { console.log( `  --   ${c.sel} — not rendered yet (stream had not reached it)` ); continue; }
    ok( c.ratio >= c.need, `${c.sel} ${c.fs}px/${c.fw}`, `${c.ratio}:1 (needs ${c.need}:1)` );
  }

  await ctx.close();
  await browser.close();
  await t.close();

  console.log( `\n${pass} ok, ${fail} FAIL` );
  console.log( 'Failures are the open findings for this band, not a broken harness.' );
} )().catch( e => { console.error( e ); process.exit( 1 ); } );
