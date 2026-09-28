'use strict';

/**
 * flowreview - ONE self-contained HTML page reviewing the home page's SECOND band.
 *
 * SCOPE, DELIBERATELY NARROW, the same way homereview.js is narrow about the first band.
 * section.home-flow only: the 650px WorkflowTerminal panel on the left and the 380px sticky
 * copy column on the right. Not band 1 (homereview.js owns it), not band 3, not the shared
 * rh-hero on the other ten routes. Each gets its own page when this one is signed off.
 *
 * THE BRIEF THIS FOLLOWS. This band's job is to explain the platform claim the hero makes:
 * many services, one foundation. The terminal is the evidence and the copy column is the
 * argument. So the panel existing at all is a DECISION, not a defect - what is in scope is
 * whether it does its job in the states a visitor actually meets.
 *
 * HOW THE FRAMES ARE BUILT, AND WHY THEY ARE SNAPSHOTS RATHER THAN A RE-IMPLEMENTATION.
 * homereview.js re-implements the pill rotation in ~15 lines of vanilla JS, because that
 * rotation is a class toggle and a width. This panel is 8 steps on chained timeouts with
 * per-step dwell, an IntersectionObserver gate, parallel lanes and a footer that changes
 * label - re-implementing it would be ~150 lines of copied logic that can drift from
 * WorkflowTerminal.tsx silently, which is the exact failure mode the harness README warns
 * about for copied CSS.
 *
 * So instead the real page is driven in Chromium and its DOM is captured at four instants:
 *
 *   t=0ms      what a visitor sees on arrival - the panel before the stream starts
 *   t=600ms    the first step landing
 *   t=4800ms   the moment the content passes the panel's own height
 *   t=12500ms  completion, with the early steps scrolled out of reach
 *
 * Every frame is therefore a REAL rendered state, frozen - not an approximation of one. The
 * cost is that the frames do not animate; the benefit is they cannot lie. Timings come from
 * flowprobe.js, which measures them, so they are not guesses either.
 *
 * Run:    node tools/browser/flowreview.js     (needs out/ - see README.md)
 * Writes: docs/flow-review.html
 */

const fs = require( 'fs' );
const path = require( 'path' );
const { target } = require( './lib/serve' );
const { launch, gotoStable } = require( './lib/browser' );

const REPO = path.join( __dirname, '..', '..' );
const OUT_FILE = path.join( REPO, 'docs', 'flow-review.html' );

/**
 * The instants the band is captured at, expressed as STATES rather than timestamps.
 *
 * WHY NOT FIXED ms OFFSETS, which is what this replaces. The stream's clock does not start on
 * navigation - it starts when the IntersectionObserver fires, which is at load on a 1280
 * viewport (the band is already 405px visible) but only on scroll at 390 (the panel sits at
 * 982 behind an 844px viewport). So "t=4800ms" means two different points in the sequence at
 * the two widths, and a frame captured by sleeping 4800ms would carry a caption that is true
 * of one panel and false of the other.
 *
 * Polling for the condition removes the ambiguity: every frame is the state it claims to be,
 * at every width, however long that took to arrive. The measured timings still appear in the
 * page copy - they come from flowprobe.js, which times the loop properly - but they are quoted
 * as findings rather than used as capture triggers.
 */
const MOMENTS = [
  { k: 't0', label: 'on arrival', arrival: true },
  { k: 'first', label: 'first step lands',
    when: () => document.querySelectorAll( '.wt-step' ).length >= 1 },
  { k: 'overflow', label: 'content outgrows the panel',
    when: () => { const s = document.querySelector( '.wt-space' );
      return s && s.scrollHeight > s.clientHeight; } },
  { k: 'complete', label: 'complete',
    when: () => document.querySelectorAll( '.wt-step' ).length === 8
      && document.querySelector( '.wt-foot-left' )?.textContent.trim() === 'complete' },
];

// ---- the one fix under review: the only original CSS in this file ------------------
//
// A contrast repair with no design content. .wt-infra carries the line that makes the
// band's actual claim - "# dynamodb · single-table · on-demand capacity", the shared
// foundation named in each step - and it is the one colour in the panel below AA.
//
// rgba(255,255,255,.44) composites to 4.25:1 on #000 against the 4.5:1 it needs at
// 12.5px/400. .50 measures 5.28:1. Deliberately NOT .62: that is .wt-desc's value, and
// the infra line is meant to read as substrate beneath the description rather than level
// with it. .50 is the smallest step that clears AA while keeping that order intact.
//
// WTJSX is replaced with WorkflowTerminal's own styled-jsx hash, which is a DIFFERENT hash
// from the home page's - the component self-styles, so it gets its own scope. Without the
// class the rule is one specificity step short of the compiled .wt-infra.jsx-HASH and the
// mock would show a fix that never applied.
const INFRA_FIX_CSS = `
  .wt-infraWTJSX{color:rgba(255,255,255,.50)}
`;

// THE FIX HAS LANDED, SO "BEFORE" IS NOW THE SIMULATED STATE - THE DIRECTION IS INVERTED.
//
// While the defect was live, a frame with no injected CSS showed the defect and FIX_CSS
// produced the "after". WorkflowTerminal.tsx now ships .50, so an un-injected frame shows the
// FIXED state, and leaving the page as it was would have labelled the repaired panel "before -
// 4.25:1, fails AA" - a mock asserting a defect that no longer exists.
//
// So the old value is restored explicitly for the before frames, the same technique the focus
// ring already needed in closereview.js. The page stays a truthful record of what changed
// rather than becoming a claim about the present.
const INFRA_PRE_FIX_CSS = `
  .wt-infraWTJSX{color:rgba(255,255,255,.44)}
`;

/** WCAG contrast, computed in-page so it reads composited pixels. Same helper as flowprobe. */
const CONTRAST_FN = `
  function lin(c){c/=255;return c<=0.03928?c/12.92:Math.pow((c+0.055)/1.055,2.4)}
  function lum(r,g,b){return 0.2126*lin(r)+0.7152*lin(g)+0.0722*lin(b)}
  function parse(s){var m=s.match(/rgba?\\(([^)]+)\\)/);if(!m)return null;
    var p=m[1].split(',').map(function(x){return parseFloat(x)});
    return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1}}
  function over(f,b){return {r:f.r*f.a+b.r*(1-f.a),g:f.g*f.a+b.g*(1-f.a),b:f.b*f.a+b.b*(1-f.a),a:1}}
  function bg(el){var layers=[];
    for(var n=el;n;n=n.parentElement){var c=parse(getComputedStyle(n).backgroundColor);
      if(c&&c.a>0){layers.unshift(c);if(c.a===1)break}}
    var base={r:255,g:255,b:255,a:1};
    for(var i=0;i<layers.length;i++)base=over(layers[i],base);return base}
  function ratio(el){var fg=parse(getComputedStyle(el).color);if(!fg)return null;var b=bg(el);
    var c=over(fg,b);var L1=lum(c.r,c.g,c.b),L2=lum(b.r,b.g,b.b);
    var hi=Math.max(L1,L2),lo=Math.min(L1,L2);
    return Math.round(((hi+0.05)/(lo+0.05))*100)/100}
`;

const METRICS = () => {
  const px = n => Math.round( n );
  const q = s => document.querySelector( s );
  const box = el => { if ( !el ) return null; const b = el.getBoundingClientRect();
    return { t: px( b.top + window.scrollY ), w: px( b.width ), h: px( b.height ) }; };
  const st = ( el, p ) => ( el ? getComputedStyle( el )[ p ] : null );
  const space = q( '.wt-space' );
  return {
    vw: window.innerWidth,
    // Needed to decide whether the band is above the fold at load, which is what determines
    // whether the IntersectionObserver has fired and therefore what "arrival" looks like.
    vh: window.innerHeight,
    flow: box( q( '.home-flow' ) ),
    panel: box( q( '.home-flow-panel' ) ),
    copy: box( q( '.home-flow-copy' ) ),
    win: box( q( '.wt-window' ) ),
    space: box( space ),
    cols: st( q( '.home-flow' ), 'gridTemplateColumns' ),
    gap: st( q( '.home-flow' ), 'gap' ),
    copyPos: st( q( '.home-flow-copy' ), 'position' ),
    copyTop: st( q( '.home-flow-copy' ), 'top' ),
    h2: st( q( '.home-flow-title' ), 'fontSize' ) + '/' + st( q( '.home-flow-title' ), 'fontWeight' ),
    steps: document.querySelectorAll( '.wt-step' ).length,
    streamed: space ? px( [ ...space.children ].reduce( ( a, c ) => a + c.getBoundingClientRect().height, 0 ) ) : 0,
    scrollTop: space ? px( space.scrollTop ) : 0,
    scrollH: space ? px( space.scrollHeight ) : 0,
    // HOW MANY STEPS ARE ACTUALLY OUT OF SIGHT, counted rather than asserted. An earlier
    // draft of the review page claimed "4 of the 8" from the pixel arithmetic; a step is only
    // hidden if its whole box is past the visible edge, which is a different question from how
    // much total height overflowed. Counted against the scroll container's own viewport.
    hidden: space ? ( () => {
      const top = space.getBoundingClientRect().top;
      return [ ...space.querySelectorAll( '.wt-step' ) ]
        .filter( s => s.getBoundingClientRect().bottom <= top ).length;
    } )() : 0,
    partial: space ? ( () => {
      const r = space.getBoundingClientRect();
      return [ ...space.querySelectorAll( '.wt-step' ) ].filter( s => {
        const b = s.getBoundingClientRect();
        return b.bottom > r.top && b.top < r.top;
      } ).length;
    } )() : 0,
  };
};

( async () => {
  const t = await target();
  const browser = await launch();
  try {
    const M = {}, SNAP = {};

    for ( const vp of [ { k: 'd', w: 1280, h: 900 }, { k: 'm', w: 390, h: 844 } ] ) {
      const ctx = await browser.newContext( { viewport: { width: vp.w, height: vp.h } } );
      const page = await ctx.newPage();

      // ---- t=0 IS CAPTURED ON ITS OWN FAST NAVIGATION ----------------------------
      //
      // It cannot be taken from the timed run below, and that is not a detail. gotoStable
      // waits for `load` and then for document.fonts.ready plus a 250ms settle - correct for
      // measuring, because text metrics move when Inter swaps in - but on a 1280 viewport the
      // band is already 405px visible at load, so the IntersectionObserver has fired and the
      // 600ms start timer has run by the time that settle finishes. The first attempt asserted
      // t0 was empty and found one step already streaming.
      //
      // So arrival gets a navigation that waits for `load` and nothing else, and is read on the
      // next tick. That is the real first-paint state, and it is the one a visitor meets.
      await page.goto( `${t.base}/`, { waitUntil: 'load' } );
      SNAP[ vp.k ] = { t0: await page.evaluate( () => {
        const c = document.querySelector( '.home-flow' ).cloneNode( true );
        const cs = c.querySelector( '.wt-space' );
        if ( cs ) cs.setAttribute( 'data-scrolltop', '0' );
        return c.outerHTML;
      } ) };
      M[ `${vp.k}_t0` ] = await page.evaluate( METRICS );

      // ---- the timed sequence, on a settled page ---------------------------------
      await gotoStable( page, `${t.base}/` );

      // SCROLL THE BAND INTO VIEW BEFORE THE CLOCK STARTS, AT BOTH WIDTHS.
      //
      // The stream is gated on an IntersectionObserver at threshold 0.25, so it only runs
      // once a quarter of the panel is on screen. At 1280 that is already true on load - the
      // band spans 495-1145 in a 900px viewport, so 405px of a 650px panel is visible and the
      // observer fires without help. At 390 it is not: the panel sits at 982-1542 behind an
      // 844px viewport, so ZERO pixels of it are visible and the stream never starts at all.
      //
      // The first version of this captured without scrolling, and the phone frame labelled
      // "t=12500ms, complete" showed an empty panel - a frame asserting a state it was not in.
      // Caught by asserting step counts inside the emitted iframes, not by looking at it.
      //
      // Scrolling first is also the honest reproduction: a phone visitor reaches this band by
      // scrolling to it, which is the moment their 15.8s begins. It changes nothing at 1280.
      await page.evaluate( () => {
        document.querySelector( '.home-flow' ).scrollIntoView( { block: 'center' } );
      } );
      await page.waitForTimeout( 150 );

      for ( const mo of MOMENTS.filter( x => !x.arrival ) ) {
        await page.waitForFunction( mo.when, null, { timeout: 40000 } );
        SNAP[ vp.k ][ mo.k ] = await page.evaluate( () => {
          const el = document.querySelector( '.home-flow' );
          const c = el.cloneNode( true );
          // Carry the live scrollTop across as an inline offset. A cloned node loses scroll
          // position, and scroll position is the whole point of the t=12500 frame - without
          // it the snapshot would show the stream from the top, i.e. show content that a
          // visitor at that instant cannot see, and hide the finding.
          const live = el.querySelector( '.wt-space' );
          const cs = c.querySelector( '.wt-space' );
          if ( live && cs ) cs.setAttribute( 'data-scrolltop', String( Math.round( live.scrollTop ) ) );
          return c.outerHTML;
        } );
        M[ `${vp.k}_${mo.k}` ] = await page.evaluate( METRICS );
      }

      // ASSERT EACH SNAPSHOT IS IN THE STATE ITS LABEL CLAIMS.
      // This is the check that caught the phone frame showing an empty panel under a
      // "complete" label. A mock whose captions do not match its pixels is worse than no
      // mock, so the generator refuses to write the file rather than emit one.
      const counts = {
        t0: M[ `${vp.k}_t0` ].steps,
        first: M[ `${vp.k}_first` ].steps,
        overflow: M[ `${vp.k}_overflow` ].steps,
        complete: M[ `${vp.k}_complete` ].steps,
      };
      // WHAT ARRIVAL LOOKS LIKE DEPENDS ON WHETHER THE PANEL IS ON SCREEN, AND THE TWO
      // VIEWPORTS GENUINELY DIFFER.
      //
      // The stream is gated on an IntersectionObserver at threshold 0.25, so it starts when a
      // quarter of the panel is visible - not on load. At 1280 the band spans 495-1145 in a
      // 900px viewport, so it is already visible and the first step lands on arrival. At 390
      // the panel sits at 982 behind an 844px viewport: nothing of it is on screen, the
      // observer has not fired, and arrival is legitimately an empty panel until the visitor
      // scrolls down to it.
      //
      // This assertion originally read `t0 !== 0`, which was right while a 600ms delay sat in
      // front of step 0. Removing that delay made the desktop case 1 step and broke it - the
      // check doing its job. Rewriting it as a flat `=== 1` then broke the phone case for the
      // opposite reason. So the expectation is derived from whether the band is above the fold
      // at load, which is the thing that actually decides it.
      // THE PANEL'S POSITION, NOT THE BAND'S, AND THE REAL 0.25 THRESHOLD.
      // Using the band was wrong at 390: it reports top 406, comfortably above an 844px fold,
      // because the copy column is ordered first there (order:-1) and the band starts with it.
      // The observer is attached to the terminal, which at that width sits at 982 - off screen.
      // So the fraction of the PANEL visible at load is what decides this, compared against
      // the same 0.25 the component uses.
      const mt = M[ `${vp.k}_t0` ];
      const visible = Math.max( 0, Math.min( mt.panel.t + mt.panel.h, mt.vh ) - mt.panel.t );
      const frac = visible / mt.panel.h;
      const expectT0 = frac >= 0.25 ? 1 : 0;
      if ( counts.t0 !== expectT0 ) {
        throw new Error( `${vp.k} t0 should hold ${expectT0} step(s): ${Math.round( frac * 100 )}% of the `
          + `panel is visible at load (top ${mt.panel.t}, height ${mt.panel.h}, viewport ${mt.vh}) `
          + `against the observer's 25% threshold - but it has ${counts.t0}` );
      }
      if ( counts.first < 1 ) throw new Error( `${vp.k} first should have the first step, has ${counts.first}` );
      if ( counts.complete !== 8 ) {
        throw new Error( `${vp.k} complete should be complete with 8 steps, has ${counts.complete} `
          + '- the IntersectionObserver gate probably never fired, so the band was never scrolled into view' );
      }
      if ( !( counts.overflow > counts.first && counts.overflow < counts.complete ) ) {
        throw new Error( `${vp.k} overflow should be mid-stream, has ${counts.overflow}` );
      }

      if ( vp.k === 'd' ) {
        SNAP.css = await page.evaluate( async () => {
          const inline = [ ...document.querySelectorAll( 'style' ) ].map( s => s.textContent ).join( '\n' );
          const hrefs = [ ...document.querySelectorAll( 'link[rel="stylesheet"]' ) ]
            .map( l => l.getAttribute( 'href' ) ).filter( h => h && h.startsWith( '/_next/' ) );
          const chunks = [];
          for ( const h of hrefs ) { try { chunks.push( await ( await fetch( h ) ).text() ); } catch { /* ignore */ } }
          return { inline, chunks: chunks.join( '\n' ),
            shellCls: document.querySelector( '.home-shell' )?.className || '',
            layoutCls: document.querySelector( '.home-layout' )?.className || '' };
        } );
      }
      await ctx.close();
    }

    if ( !SNAP.d || !SNAP.d.complete ) throw new Error( 'failed to harvest the band from out/' );

    // WorkflowTerminal's own scoping class. Read off the harvested markup rather than the
    // page's, because the component self-styles and therefore has a different hash from
    // index.tsx's block - injecting with the wrong one loses the specificity contest.
    //
    // MATCHED ON THE CLASS LIST, NOT ON THE TAG. The obvious version anchors to
    // `<section class="..wt-wrap..">` and never matches: outerHTML serialises attributes in
    // DOM order, not JSX order, so the real output is
    // `<section aria-labelledby=".." class="jsx-… home-flow">` and the class attribute is not
    // where the tag pattern expects it. Keying off `wt-wrap` inside a class attribute has no
    // such dependency, and the home page's own hash (on .home-flow) cannot be picked up by
    // accident because the two never share an attribute.
    const wtHash = ( /class="([^"]*)\bwt-wrap\b/.exec( SNAP.d.complete ) || [] )[ 1 ]
      ?.trim().split( /\s+/ ).find( c => c.startsWith( 'jsx-' ) );
    if ( !wtHash ) throw new Error( 'could not read WorkflowTerminal\'s styled-jsx scoping class' );
    const scopeWt = css => css.replace( /WTJSX/g, `.${wtHash}` );

    // The global reset and the body font rule, extracted rather than retyped - the same two
    // things homereview.js found it could not drop. The 514KB of chunks is Amplify UI and
    // the dashboard stylesheets, which this band never touches; the fidelity check at the
    // end asserts the frames still measure what the live page measures.
    const GLOBAL_RESET = '*{box-sizing:border-box;margin:0;padding:0}';
    const bodyFont = ( () => {
      const m = /body\{[^}]*font-family:Inter[^}]*\}/.exec( SNAP.css.chunks );
      if ( !m ) throw new Error( 'could not extract the body font rule from the built CSS' );
      return m[ 0 ];
    } )();
    const CSS_ALL = GLOBAL_RESET + '\n' + bodyFont + '\n' + SNAP.css.inline;

    // Restores each frozen panel's scroll offset. Three lines, and the only script in a
    // frame - everything else is static markup, so the page renders with scripts off.
    const SCROLL_JS = '<script>document.querySelectorAll("[data-scrolltop]").forEach('
      + 'function(e){e.scrollTop=+e.getAttribute("data-scrolltop")});<\/script>';

    const frameDoc = o => {
      const extra = ( o.fix ? scopeWt( INFRA_FIX_CSS ) : '' )
        + ( o.preFix ? scopeWt( INFRA_PRE_FIX_CSS ) : '' )
        + ( o.noSticky ? '.home-flow-copy{position:static !important}' : '' );
      return '<!doctype html><meta charset="utf-8">'
        + '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
        + `<style>html,body{margin:0}${CSS_ALL}${extra}`
        // The band is the subject, so the layout's 96px section gaps are not wanted here -
        // they would add 192px of empty page to every frame. Padding is kept: it is what
        // sets the band's own measure.
        + '.home-layout{gap:0 !important;padding-top:24px !important;padding-bottom:24px !important}'
        + '</style>'
        + `<main class="${SNAP.css.shellCls}" style="padding-top:0">`
        + `<div class="${SNAP.css.layoutCls}">${o.html}</div></main>`
        + ( o.noJs ? '' : SCROLL_JS );
    };

    const shot = ( o, w, h, sc = 1 ) =>
      `<div class="shot" style="width:${Math.round( w * sc )}px;height:${Math.round( h * sc )}px">`
      + `<iframe loading="lazy" scrolling="no" title="preview" `
      + `style="width:${w}px;height:${h}px;transform:scale(${sc})" `
      + `srcdoc="${frameDoc( o ).replace( /"/g, '&quot;' )}"></iframe></div>`;
    // THE SCALE IS PART OF THE LABEL, and leaving it out was a real defect in this page.
    //
    // Frames are scaled down so several fit side by side, and the four-state strip used
    // scale(0.5). That renders this band's 20px body copy at 10px on screen - while
    // close-review.html shows band 3's identical 20px rung at scale(1). Comparing type
    // across the two pages therefore suggested band 2 used a smaller font size than band 3,
    // which is false: measured on the live site and locally, at 320/390/768/1280, both are
    // font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px - the same
    // declaration. The mock invented a discrepancy the page does not have, and someone
    // reasonably asked for a font size to be "matched" that already matched.
    //
    // So every frame below 1:1 now says so on its own label. A reviewer can still compare
    // across pages; they can just see when they are not comparing like with like.
    const labelled = ( lab, cls, o, w, h, sc ) =>
      `<div class="cmpcol"><span class="collab ${cls}">${lab}</span>`
      + ( sc < 1 ? `<span class="scale">shown at ${Math.round( sc * 100 )}% — type is not to size</span>` : '' )
      + `${shot( o, w, h, sc )}</div>`;

    const DH = 740, MH = 1240;
    const P = {
      // ORIGINAL — the four real states, desktop, at actual size.
      moments: '<div class="cmp">' + MOMENTS.map( mo =>
        labelled( mo.label, mo.arrival ? 'c-b' : 'c-n',
          { html: SNAP.d[ mo.k ] }, 1280, DH, 0.5 ) ).join( '' ) + '</div>',
      arrivalD: shot( { html: SNAP.d.t0 }, 1280, DH, 1 ),
      completeD: shot( { html: SNAP.d.complete }, 1280, DH, 1 ),
      arrivalM: shot( { html: SNAP.m.t0 }, 390, MH, 1 ),
      completeM: shot( { html: SNAP.m.complete }, 390, MH, 1 ),
      infra: '<div class="cmp">'
        + labelled( 'was — 4.25:1, failed AA', 'c-b', { html: SNAP.d.complete, preFix: true }, 1280, DH, 1 )
        + labelled( 'now — 5.28:1, shipping', 'c-a', { html: SNAP.d.complete }, 1280, DH, 1 )
        + '</div>',
      sticky: '<div class="cmp">'
        + labelled( 'sticky — as it ships', 'c-n', { html: SNAP.d.complete }, 1280, DH, 0.62 )
        + labelled( 'static — sticky removed', 'c-n', { html: SNAP.d.complete, noSticky: true }, 1280, DH, 0.62 )
        + '</div>',
      nojs: '<div class="cmp">'
        + labelled( 'no JavaScript — the panel a crawler and a failed bundle get', 'c-b',
          { html: SNAP.d.t0, noJs: true }, 1280, DH, 0.62 ) + '</div>',
    };

    const STAMP = new Date().toISOString().replace( 'T', ' ' ).slice( 0, 16 ) + 'Z';
    const d0 = M.d_t0, d12 = M.d_complete, m0 = M.m_t0, m12 = M.m_complete;
    // MEASURED, NOT THE OLD HARDCODED 26. That literal was the height of the single request
    // line the panel used to arrive with; the first step now lands immediately, so arrival is
    // taller and the figure had to come from the capture instead of a constant that was only
    // true before the fix.
    const emptyPct = Math.round( ( 1 - d0.streamed / d0.space.h ) * 100 );
    const overflowPct = Math.round( d12.scrollH / d12.space.h * 100 );

    const html = `<!doctype html>
<meta charset="utf-8">
<title>Home page — band 2, section.home-flow</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root{--ink:#1a1a1a;--mut:rgba(0,0,0,.55);--lime:#d1f470;--grn:#1a3a2a;--line:#e3e3e3;--red:#b42318;--amb:#a05a00}
  *{box-sizing:border-box}
  body{margin:0;background:#fafafa;color:var(--ink);font-size:15px;line-height:1.55;
    font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
  .wrap{max-width:1560px;margin:0 auto;padding:30px 22px 110px}
  h1{font-size:clamp(28px,3.2vw,40px);font-weight:700;line-height:1.08;letter-spacing:-1.2px;margin:0 0 10px}
  h2{font-size:24px;font-weight:700;letter-spacing:-.4px;margin:0}
  p{margin:0 0 10px}
  .mut{color:var(--mut)} .sm{font-size:13.5px}
  code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.87em;background:#f0f0f0;padding:1px 5px;border-radius:4px}
  pre{background:#f6f6f6;border:1px solid var(--line);border-radius:8px;padding:13px;overflow:auto;font-size:12.5px;line-height:1.5;margin:8px 0 0}
  .card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:0 0 22px}
  .card.brief{border-left:4px solid var(--lime)}
  .card.scope{border-left:4px solid #20418f}
  section.band{margin:0 0 26px;background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden}
  .bhead{padding:17px 22px;border-bottom:1px solid var(--line);display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}
  .tag{display:inline-flex;align-items:center;justify-content:center;padding:3px 9px;border-radius:6px;
    background:var(--grn);color:var(--lime);font-weight:800;font-size:12px;letter-spacing:.06em;flex:none}
  .sel{font-size:13px;color:var(--mut);font-family:ui-monospace,Menlo,monospace}
  .step{padding:19px 22px;border-top:1px solid #f0f0f0}
  table{border-collapse:collapse;width:100%;font-size:13.5px;margin:6px 0 0}
  th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
  th{background:#f7f7f7;font-weight:600}
  td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
  ol,ul{margin:6px 0 10px;padding-left:20px} li{margin:5px 0}
  .sev{display:inline-block;font-size:10.5px;font-weight:800;padding:2px 7px;border-radius:4px;flex:none}
  .s-h{background:#fdeceb;color:var(--red)} .s-m{background:#fff4e5;color:var(--amb)} .s-l{background:#eef1f4;color:#44546a}
  .s-ok{background:#eefaf0;color:#1f6f3d}
  .collab{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.07em;margin:0 0 7px;padding:2px 7px;border-radius:4px;display:inline-block}
  .c-b{background:#fdeceb;color:var(--red)} .c-a{background:#eefaf0;color:#1f6f3d} .c-n{background:#eef1f4;color:#44546a}
  .shot{border:1px solid var(--line);border-radius:8px;overflow:hidden;background:#fff;position:relative}
  .shot iframe{border:0;display:block;transform-origin:0 0}
  .cmp{display:flex;gap:18px;flex-wrap:wrap;align-items:flex-start;margin:0 0 14px}
  .cmpcol{flex:none}
  .scale{display:block;font-size:10.5px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;
    color:var(--amb);background:#fff4e5;border-radius:4px;padding:2px 7px;margin:0 0 6px}
  .cap{font-size:14px;color:var(--mut);margin:0 0 14px;max-width:110ch}
  .cap b{color:var(--ink)}
  details.why{border:1px solid var(--line);border-radius:9px;background:#fcfcfc;margin:14px 0 0}
  details.why>summary{cursor:pointer;padding:10px 14px;font-size:13px;font-weight:700;color:#44546a;
    list-style:none;display:flex;gap:8px;align-items:center}
  details.why>summary::-webkit-details-marker{display:none}
  details.why>summary::before{content:'▸';font-size:11px}
  details.why[open]>summary::before{content:'▾'}
  details.why .inner{padding:0 14px 14px;border-top:1px solid var(--line);padding-top:12px}
  .bar{position:sticky;top:0;z-index:5;background:rgba(250,250,250,.94);backdrop-filter:blur(6px);
    border-bottom:1px solid var(--line);padding:10px 0;margin:0 0 20px}
  footer.pg{color:var(--mut);font-size:13px;border-top:1px solid var(--line);padding-top:18px;margin-top:34px}
</style>
<div class="wrap">

<h1>Home page — band 2 of 3</h1>
<p class="cap" style="font-size:16px"><code>section.home-flow</code> — the 650px terminal panel
and the 380px sticky copy column beside it. Band 1 has its own page
(<code>docs/home-review.html</code>); band 3 and the shared <code>rh-hero</code> follow when
this one is signed off.</p>

<div class="bar"><div class="in">
  <span class="mut sm"><b>No JavaScript needed to view this page.</b> Every panel is static
  markup and the notes are native <code>&lt;details&gt;</code>.<br>
  <b>Every frame is a real rendered state, frozen</b> — the live page was driven in Chromium and
  its DOM captured when each state was reached, not after a fixed delay. Nothing here is a
  re-implementation, so no frame can drift from <code>WorkflowTerminal.tsx</code>.<br>
  <b>Build ${STAMP}.</b> Timings come from <code>tools/browser/flowprobe.js</code>.</span>
</div></div>

<div class="card brief">
  <h2 style="font-size:18px;margin-bottom:8px">What this band is for</h2>
  <p class="cap" style="margin:0">The hero claims <b>everyday AI, built for four domains</b>.
  This band is where that claim gets its evidence: the terminal shows many services on one
  foundation, and the copy column says what that buys a customer. <b>So the panel existing is a
  decision, not a defect.</b> What follows is only about whether it does that job in the states
  a visitor actually meets.</p>
</div>

<!-- ============== ORIGINAL ============== -->
<section class="band">
  <div class="bhead"><span class="tag" style="background:#44546a;color:#fff">ORIGINAL</span>
    <h2>The four states, desktop 1280</h2>
    <span class="sel">unmodified · 50% scale so all four fit side by side</span></div>
  <div class="step">
    <p class="cap">The band changes shape completely over one 15.8s cycle. Left to right: what a
    visitor sees on arrival, the first step landing, the moment the stream outgrows its own box,
    and completion. <b>Then it empties and starts again.</b></p>
    ${P.moments}
  </div>
</section>

<section class="band">
  <div class="bhead"><span class="tag" style="background:#44546a;color:#fff">ORIGINAL</span>
    <h2>On arrival — desktop 1280, actual size</h2>
    <span class="sel">t=0ms · ${d0.space.h}px panel, 26px of content</span></div>
  <div class="step">${P.arrivalD}</div>
</section>

<section class="band">
  <div class="bhead"><span class="tag" style="background:#44546a;color:#fff">ORIGINAL</span>
    <h2>Complete — desktop 1280, actual size</h2>
    <span class="sel">${d12.scrollH}px of content in a ${d12.space.h}px box, scrolled to ${d12.scrollTop}px · reached after a measured 12.6s</span></div>
  <div class="step">${P.completeD}</div>
</section>

<section class="band">
  <div class="bhead"><span class="tag" style="background:#44546a;color:#fff">ORIGINAL</span>
    <h2>Phone 390 — on arrival, then complete</h2>
    <span class="sel">one column · copy first (order:-1), panel below</span></div>
  <div class="step"><div class="cmp">
    <div class="cmpcol"><span class="collab c-b">t=0ms</span>${P.arrivalM}</div>
    <div class="cmpcol"><span class="collab c-n">t=12500ms</span>${P.completeM}</div>
  </div></div>
</section>

<!-- ============== MEASURED ============== -->
<section class="band">
  <div class="bhead"><span class="tag">MEASURED</span><h2>The band, in numbers</h2></div>
  <div class="step">
    <table>
      <tr><th>Property</th><th class="n">1280</th><th class="n">390</th><th>Note</th></tr>
      <tr><td>band</td><td class="n">${d0.flow.w}×${d0.flow.h}</td><td class="n">${m0.flow.w}×${m0.flow.h}</td><td>grid <code>${d0.cols}</code>, gap ${d0.gap}</td></tr>
      <tr><td>terminal panel</td><td class="n">${d0.win.w}×${d0.win.h}</td><td class="n">${m0.win.w}×${m0.win.h}</td><td>fixed height, <code>overflow:hidden</code></td></tr>
      <tr><td>scroll area <code>.wt-space</code></td><td class="n">${d0.space.w}×${d0.space.h}</td><td class="n">${m0.space.w}×${m0.space.h}</td><td>the box the stream runs inside</td></tr>
      <tr><td>copy column</td><td class="n">${d0.copy.w}×${d0.copy.h}</td><td class="n">${m0.copy.w}×${m0.copy.h}</td><td><code>${d0.copyPos}</code>, top <code>${d0.copyTop}</code></td></tr>
      <tr><td>content at t=0</td><td class="n">26px</td><td class="n">26px</td><td><b>${emptyPct}% of the panel empty</b></td></tr>
      <tr><td>content at t=12500</td><td class="n">${d12.scrollH}px</td><td class="n">${m12.scrollH}px</td><td><b>${overflowPct}% of the box</b></td></tr>
      <tr><td>section h2</td><td class="n">${d0.h2}</td><td class="n">${m0.h2}</td><td>heavier than the hero h1's 600 — the site's documented inversion</td></tr>
    </table>
  </div>
</section>

<!-- ============== F1 ============== -->
<section class="band">
  <div class="bhead"><span class="sev s-m">IMPROVED</span><h2>F1 — The panel no longer empties itself, but it still starts mostly empty</h2>
    <span class="sel">.wt-space</span></div>
  <div class="step">
    <p class="cap">The terminal is ${d0.win.h}px tall — the biggest single thing on a 2090px
    page. <b>Two of the three causes are fixed.</b> The 600ms delay before the first step is gone,
    so arrival now shows one step rather than nothing: <b>${emptyPct}% empty instead of 95%</b>.
    And the sequence no longer resets — it used to drop back to a single line every 15.8s, so the
    empty state recurred for as long as you stayed on the page. It now happens once.</p>
    <p class="cap"><b>What is still true:</b> the first thing a visitor sees is a 650px panel with
    one line in it, filling over ~12.5s. Making it start fuller means seeding several steps, which
    weakens the "watch it happen" idea — still a decision, still listed at the end.</p>
    <details class="why"><summary>the measurement</summary><div class="inner">
      <pre>node tools/browser/flowprobe.js   (re-measured after the fix)

  fill over time (panel inner height ${d0.space.h}px)
    t(ms)  steps  used px  % filled
        0      1      137       25%   &lt;- was 0 steps / 5%
      600      1      137       25%
     1200      2      289       52%
     2400      3      460       83%
     4800      4      651      118%
     8000      6      915      166%
    12500      8     1264      229%

  and then it HOLDS. It used to reset to 1 line here and repeat,
  every 15.8s, for as long as the panel stayed on screen.</pre>
    </div></details>
  </div>
</section>

<!-- ============== F2 ============== -->
<section class="band">
  <div class="bhead"><span class="sev s-h">STILL OPEN</span><h2>F2 — By the end, ${d12.hidden} of the 8 steps have scrolled out and cannot be recovered</h2>
    <span class="sel">.wt-space · overflow-y:auto · aria-hidden</span></div>
  <div class="step">
    <p class="cap">At completion <b>${d12.scrollH}px of content sits in a ${d12.space.h}px box</b> —
    ${overflowPct}% — and the component auto-scrolls to follow the newest step
    (<code>parentElement.scrollTop = scrollHeight</code>). The frame above, scrolled to
    ${d12.scrollTop}px exactly as the live page is, is the proof: <b>${d12.hidden} steps are
    entirely above the visible edge</b>${d12.partial ? ` and ${d12.partial} more is cut in half` : ''}.
    On the phone frame it is ${m12.hidden} of 8.</p>
    <p class="cap">Counted, not inferred from the overflow arithmetic: a step is only hidden when
    its whole box is past the edge, which is a different question from how much total height
    overflowed.</p>
    <p class="cap">Nobody can scroll back to them. The scroll container is
    <code>aria-hidden="true"</code> with no <code>tabindex</code>, so <b>it is not reachable by
    keyboard</b> (WCAG 2.1.1) and not exposed to assistive tech at all. A mouse user can wheel
    over it — and then the next step auto-scrolls them away again. So the panel streams four
    steps that no visitor can read, and the parallel-lanes step is the one carrying the band's
    strongest claim.</p>
    <details class="why"><summary>why the frame can show this at all</summary><div class="inner">
      <p class="cap" style="margin:0">A cloned DOM node loses its scroll position, and scroll
      position <i>is</i> this finding — a snapshot taken without it would show the stream from
      the top, i.e. show content the visitor cannot see and hide the defect. So the live
      <code>scrollTop</code> is carried across as <code>data-scrolltop</code> and restored by the
      one three-line script in each frame.</p>
    </div></details>
  </div>
</section>

<!-- ============== F3 ============== -->
<section class="band">
  <div class="bhead"><span class="sev s-ok">FIXED</span><h2>F3 — <code>.wt-infra</code> failed AA, and it is the line carrying the band's claim</h2>
    <span class="sel">was rgba(255,255,255,.44) → 4.25:1 · now .50 → 5.28:1</span></div>
  <div class="step">
    <p class="cap">Every colour in this panel is a white alpha over <code>#000</code>, and an
    alpha is not a colour until it is composited — so these ratios are computed from the painted
    pixel, not looked up. Thirteen of the fourteen text styles passed. The one that did not was
    the <code>#</code> comment line naming the shared infrastructure in each step — which is
    precisely the line that makes the band's argument.</p>
    <p class="cap"><b>Fixed: <code>.44</code> → <code>.50</code>, and nothing else.</b>
    Deliberately not <code>.62</code>: that is <code>.wt-desc</code>'s value, and the infra line
    is meant to read as substrate <i>beneath</i> the description rather than level with it.
    <code>.50</code> is the smallest step that clears AA and keeps that order. <b>All fourteen
    now pass</b> — the left frame below restores the old value so the comparison still means
    something; the right frame is what ships.</p>
    ${P.infra}
    <details class="why"><summary>the full contrast table</summary><div class="inner">
      <pre>.wt-request      15px/400   21.00:1  ok
.wt-name         15px/600   21.00:1  ok
.wt-chip         12px/400   15.90:1  ok
.wt-lane-name  12.5px/600   19.78:1  ok
.wt-svc        11.5px/400   13.08:1  ok
.wt-bar-title    13px/400    8.03:1  ok
.wt-desc       13.5px/400    7.85:1  ok
.wt-check      12.5px/400    7.85:1  ok
.wt-lane-detail  12px/400    6.07:1  ok
.wt-foot-left    12px/400    6.06:1  ok
.wt-foot-right   12px/400    6.06:1  ok
.wt-bar-state    12px/400    5.77:1  ok
.wt-time         12px/400    4.58:1  ok   (4.5 needed — 0.08 of margin)
.wt-infra      12.5px/400    5.28:1  ok   (was 4.25:1 - FIXED)</pre>
      <p class="cap" style="margin:8px 0 0"><code>.wt-time</code> passes by 0.08. It is not a
      finding today, but any future dimming of it fails.</p>
    </div></details>
  </div>
</section>

<!-- ============== F4 ============== -->
<section class="band">
  <div class="bhead"><span class="sev s-l">LOW</span><h2>F4 — The sticky copy column has ${d0.win.h - d0.copy.h}px of travel</h2>
    <span class="sel">.home-flow-copy{position:sticky;top:128px}</span></div>
  <div class="step">
    <p class="cap">The copy column is ${d0.copy.h}px inside a ${d0.win.h}px band, so sticky can
    hold it for <b>${d0.win.h - d0.copy.h}px of scroll and no more</b> before the band's bottom
    edge pushes it out. Below 1024px the rule is switched off entirely
    (<code>position:static;order:-1</code>). The two frames are near-identical, which is the
    point — this is ~${d0.win.h - d0.copy.h}px of behaviour and a <code>top:128px</code> magic
    number that has to track the header height.</p>
    ${P.sticky}
  </div>
</section>

<!-- ============== F5 ============== -->
<section class="band">
  <div class="bhead"><span class="sev s-m">MED</span><h2>F5 — With no JavaScript the band is a black rectangle</h2>
    <span class="sel">the crawler and failed-bundle state</span></div>
  <div class="step">
    <p class="cap">The stream is rendered by React state, so without it the panel is chrome and
    one line. The copy column is unaffected — it is static markup — so the band still <i>says</i>
    its thing; what is lost is all of the evidence for it. Worth knowing because band 3
    deliberately solved this exact problem the other way round, with the
    <code>.is-armed</code> pattern: it ships the final state and lets JavaScript hide it.</p>
    ${P.nojs}
  </div>
</section>

<!-- ============== DECISIONS ============== -->
<section class="band">
  <div class="bhead"><span class="tag" style="background:#20418f;color:#fff">DECISIONS</span>
    <h2>Not mine to take</h2></div>
  <div class="step">
    <p class="cap">F3 is the only finding here with a fix that carries no design content, which
    is why it is the only one with an “after” frame. The rest change what the band says:</p>
    <table>
      <tr><th>#</th><th>The question</th><th>Why it is a decision</th></tr>
      <tr><td>F1</td><td>Should the panel ship already populated?</td>
        <td><b>Partly done.</b> The 600ms dead start and the 15.8s reset are gone, so arrival is
        one step rather than none and the empty state no longer recurs. Seeding <i>several</i>
        steps is what remains, and that weakens the “watch it happen” idea.</td></tr>
      <tr><td>F2</td><td>Eight steps, or fewer that fit?</td>
        <td>${d12.scrollH}px does not fit ${d12.space.h}px. Either the panel grows, the steps get
        shorter, or four of them are cut. All three change the argument.</td></tr>
      <tr><td>F2</td><td><s>Should the stream be pausable?</s> <b>Resolved</b></td>
        <td>WCAG 2.2.2 applies to content moving automatically for over 5s; this ran 15.8s on a
        loop with no pause, stop or hide. <b>It now plays once and holds</b>, which is the
        conformant answer that adds no furniture to the page — and it matches what the closing
        band already does for the same stated reason. <b>The rotating headline in band 1 still
        has this exposure</b> at 9.6s, and is now the only one left.</td></tr>
      <tr><td>F4</td><td>Keep sticky for ${d0.win.h - d0.copy.h}px?</td>
        <td>Dropping it removes a magic number; keeping it is a real if small effect.</td></tr>
      <tr><td>F5</td><td>Should the no-JS state carry the steps?</td>
        <td>Band 3's <code>.is-armed</code> pattern is the in-repo precedent for doing so.</td></tr>
    </table>
  </div>
</section>

<footer class="pg">
  Generated by <code>tools/browser/flowreview.js</code> from the static export in
  <code>out/</code>. Measurements by <code>tools/browser/flowprobe.js</code>.
  Band 1: <code>docs/home-review.html</code>. Build ${STAMP}.
</footer>
</div>
`;

    fs.writeFileSync( OUT_FILE, html );
    const kb = Math.round( Buffer.byteLength( html ) / 1024 );
    console.log( `wrote ${path.relative( REPO, OUT_FILE )}  (${kb}KB)` );

    // ---- FIDELITY CHECK ----------------------------------------------------------
    // The frames drop 514KB of built chunks, so this asserts the band still measures what
    // the live page measures. If a global rule ever does matter these numbers move and this
    // fails, rather than the mock quietly becoming a different design.
    const ctx = await browser.newContext( { viewport: { width: 1280, height: 900 } } );
    const pg = await ctx.newPage();
    await pg.setContent( frameDoc( { html: SNAP.d.complete } ) );
    await pg.waitForTimeout( 400 );
    const f = await pg.evaluate( METRICS );
    // The stylesheet goes in through Playwright's own API rather than by building a
    // `document.createElement('style')` call inside an interpolated source string.
    // `JSON.stringify` was already correct escaping, but `js/bad-code-sanitization`
    // objects to constructing code from a value at all, and addStyleTag removes the
    // construction instead of escaping it better. What is still interpolated below is
    // CONTRAST_FN, a module constant with no data flowing into it, which is the shared
    // pattern the other three harnesses use.
    await pg.addStyleTag( { content: scopeWt( INFRA_FIX_CSS ) } );
    const fixed = await pg.evaluate( `(() => { ${CONTRAST_FN}
      return ratio(document.querySelector('.wt-infra')); })()` );
    await ctx.close();

    const checks = [
      [ 'panel width', f.win.w, d12.win.w ],
      [ 'panel height', f.win.h, d12.win.h ],
      [ 'copy column width', f.copy.w, d12.copy.w ],
      [ 'scroll area height', f.space.h, d12.space.h ],
      [ 'grid columns', f.cols, d12.cols ],
    ];
    let bad = 0;
    console.log( '\nfidelity — frame vs live page' );
    for ( const [ name, got, want ] of checks ) {
      const okk = String( got ) === String( want );
      if ( !okk ) bad++;
      console.log( `  ${okk ? 'ok  ' : 'FAIL'} ${name}: ${got}${okk ? '' : ` (live ${want})`}` );
    }
    console.log( `  ${fixed >= 4.5 ? 'ok  ' : 'FAIL'} the F3 fix measures ${fixed}:1 in the frame (needs 4.5:1)` );
    if ( fixed < 4.5 ) bad++;
    if ( bad ) { console.error( `\n${bad} fidelity failure(s) — the mock does not match the page` ); process.exit( 1 ); }
    console.log( '\nall fidelity checks pass' );
  } finally {
    await browser.close();
    await t.close();
  }
} )().catch( e => { console.error( e ); process.exit( 1 ); } );
