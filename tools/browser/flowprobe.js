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
 *   2. THE LOOP PERIOD. dwell() is keyed off what each step CONTAINS, not its index, so the
 *      total is a sum over the STEPS array plus eight inter-step gaps plus the hold and the
 *      restart. That is derivable by hand and was - but WCAG 2.2.2 turns on whether it
 *      exceeds five seconds and whether it can be paused, so it is worth measuring rather
 *      than arithmetic on a comment.
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
  console.log( '\nTHE LOOP' );
  const loop = await fresh.evaluate( () => new Promise( resolve => {
    // The footer's own label is the component's signal - 'complete' at the end, reverting
    // to 'running' on restart - rather than a guess about its internals.
    const state = () => document.querySelector( '.wt-foot-left' )?.textContent.trim();
    const steps = () => document.querySelectorAll( '.wt-step' ).length;
    let t0 = null, completeAt = null, prev = state();
    const iv = setInterval( () => {
      const s = state(), n = steps();
      // A restart edge: 'complete' -> 'running' with the list emptied back out.
      if ( prev === 'complete' && s === 'running' && n <= 1 ) {
        if ( t0 === null ) { t0 = performance.now(); }
        else {
          clearInterval( iv );
          resolve( { period: Math.round( performance.now() - t0 ),
            toComplete: completeAt === null ? null : Math.round( completeAt - t0 ) } );
          return;
        }
      }
      if ( t0 !== null && s === 'complete' && completeAt === null ) completeAt = performance.now();
      prev = s;
    }, 50 );
    setTimeout( () => { clearInterval( iv ); resolve( { timedOut: true } ); }, 60000 );
  } ) );
  ok( false, 'the stream loops forever with no pause control (WCAG 2.2.2)',
    loop.timedOut
      ? 'could not observe two restart edges inside 60s'
      : `one cycle is ${( loop.period / 1000 ).toFixed( 1 )}s ` +
        `(${( loop.toComplete / 1000 ).toFixed( 1 )}s streaming, ${( ( loop.period - loop.toComplete ) / 1000 ).toFixed( 1 )}s holding, then it empties) ` +
        '— auto-starts, runs over 5s, offers no pause, stop or hide' );
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
