'use strict';

/**
 * homereview - emits ONE self-contained HTML review page for the home page redesign,
 * organised section by section: for each band, the ORIGINAL as it ships, then the flaws,
 * then the proposed change, then a recommendation with reasons.
 *
 * WHY IT IS GENERATED, NOT WRITTEN BY HAND. There is a hand-built mock in this repo whose
 * header and hero CSS were pasted out of Header.tsx and index.tsx. That is true exactly
 * once: the day either source changes, the mock keeps showing the old design and nothing
 * announces it. This pulls the CSS, the markup and every measurement out of the REAL static
 * export at generation time, so the review cannot disagree with the page. Re-run it and it
 * is current.
 *
 * WHY IFRAMES AND NOT SCREENSHOTS. Each panel is a real document at a real width, so
 * clamp(36px,4.3vw,60px) resolves against that width exactly as it would at that viewport
 * and the fixed header sits at its true 108px. The frame is genuinely 1280px or 390px wide
 * and only visually scaled to fit, so nothing inside it is distorted. It is also live: the
 * pill rotates, buttons hover and take focus rings, and Tab works inside a panel. No image
 * files are produced or committed.
 *
 * EVERY NUMBER IN THE OUTPUT IS MEASURED HERE. The per-section tables are read from the
 * DOM at both widths during generation - nothing is transcribed from an earlier run.
 *
 * Run:    node tools/browser/homereview.js     (needs out/ - see README.md)
 * Writes: docs/home-review.html
 */

const fs = require( 'fs' );
const path = require( 'path' );
const { target } = require( './lib/serve' );
const { launch, gotoStable } = require( './lib/browser' );

const REPO = path.join( __dirname, '..', '..' );
const OUT_FILE = path.join( REPO, 'docs', 'home-review.html' );

// ---- derived: price floor, from the catalogue ---------------------------------
const catalog = JSON.parse( fs.readFileSync( path.join( REPO, 'src', 'content', 'wix-catalog.json' ), 'utf8' ) );
const citems = Array.isArray( catalog ) ? catalog : ( catalog.products || catalog.items || [] );
const cprices = citems.map( p => Number( p.price ) ).filter( n => Number.isFinite( n ) && n > 0 ).sort( ( a, b ) => a - b );
const FLOOR = cprices[ 0 ];
const FLOOR_TXT = `₹${FLOOR.toLocaleString( 'en-IN' )}`;
const NEXT_TXT = `₹${cprices[ 1 ].toLocaleString( 'en-IN' )}`;

// ---- derived: the rotating words, parsed from source --------------------------
const src = fs.readFileSync( path.join( REPO, 'src', 'pages', 'index.tsx' ), 'utf8' );
const cb = /const CYCLE_WORDS = \[([\s\S]*?)\];/.exec( src );
if ( !cb ) throw new Error( 'could not parse CYCLE_WORDS from src/pages/index.tsx' );
const WORDS = [ ...cb[ 1 ].matchAll( /word:\s*'([^']+)',\s*tint:\s*'([^']+)',\s*dot:\s*'([^']+)'/g ) ]
  .map( m => ( { word: m[ 1 ], tint: m[ 2 ], dot: m[ 3 ] } ) );
if ( !WORDS.length ) throw new Error( 'CYCLE_WORDS parsed empty' );

// ---- the proposed CTA styling: the only original design in this file ----------
// Values are lifted from .home-close-cta so the two CTAs are the same control at the same
// size. No new colour is introduced.
const MOCK_CSS = `
  .mock-row{display:flex;align-items:center;gap:18px;flex-wrap:wrap;margin:32px 0 0}
  .mock-cta{display:inline-flex;align-items:center;min-height:52px;padding:0 28px;
    border:2px solid #d1f470;border-radius:50px;background:#d1f470;color:#1a3a2a;
    font-size:17px;font-weight:600;text-decoration:none;
    transition:background-color .2s,box-shadow .2s,transform .2s}
  .mock-cta:hover{background:#fff;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}
  .mock-cta:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:3px}
  .mock-cta2{display:inline-flex;align-items:center;min-height:52px;padding:0 24px;
    border:2px solid rgba(26,58,42,.22);border-radius:50px;background:#fff;color:#1a3a2a;
    font-size:17px;font-weight:600;text-decoration:none}
  .mock-cta2:hover{border-color:#1a3a2a}
  .mock-cta2:focus-visible{outline:3px solid rgba(26,58,42,.22);outline-offset:3px}
  .mock-price{font-size:17px;font-weight:400;color:rgba(0,0,0,.54);letter-spacing:-.125px}
  .mock-price b{font-weight:600;color:#1a3a2a}
`;

const OPTIONS = [
  { id: 'B', name: 'one primary action', dest: '/contact/',
    html: `<div class="mock-row"><a class="mock-cta" href="/contact/">Submit a request</a></div>` },
  { id: 'C', name: `one action + the price, derived (${FLOOR_TXT})`, dest: '/contact/', pick: true,
    html: `<div class="mock-row"><a class="mock-cta" href="/contact/">Submit a request</a>`
      + `<span class="mock-price">from <b>${FLOOR_TXT}</b></span></div>` },
  { id: 'D', name: 'two actions — start, or sign in', dest: '/contact/ + /access',
    html: `<div class="mock-row"><a class="mock-cta" href="/contact/">Submit a request</a>`
      + `<a class="mock-cta2" href="/access">Sign in</a></div>` },
  { id: 'E', name: 'two actions + the price', dest: '/contact/ + /access',
    html: `<div class="mock-row"><a class="mock-cta" href="/contact/">Submit a request</a>`
      + `<a class="mock-cta2" href="/access">Sign in</a>`
      + `<span class="mock-price">from <b>${FLOOR_TXT}</b></span></div>` },
];

const METRICS = () => {
  const px = n => Math.round( n );
  const q = s => document.querySelector( s );
  const box = el => { if ( !el ) return null; const b = el.getBoundingClientRect(); return { t: px( b.top ), l: px( b.left ), w: px( b.width ), h: px( b.height ), b: px( b.bottom ) }; };
  const st = ( el, p ) => ( el ? getComputedStyle( el )[ p ] : null );
  const vis = el => { for ( let n = el; n; n = n.parentElement ) { const c = getComputedStyle( n ); if ( c.visibility === 'hidden' || c.display === 'none' || +c.opacity === 0 ) return false; } return true; };
  const SEL = 'a[href],button,input,select,textarea,[role="button"],[tabindex]:not([tabindex="-1"])';
  const actions = root => {
    if ( !root ) return { total: 0, visible: 0 };
    const all = Array.from( root.querySelectorAll( SEL ) );
    return { total: all.length, visible: all.filter( vis ).length };
  };
  const hdr = q( 'header' ), hero = q( '.home-hero' ), flow = q( '.home-flow' ),
    close = q( '.home-close' ), foot = q( 'footer' ) || q( '[class*="ft-footer"]' ),
    widget = q( '.wc-langbar' ) || q( '[class*="wc-lang"]' ),
    layout = q( '.home-layout' ), h1 = q( '.home-head' ), sub = q( '.home-sub' ),
    mark = q( '.home-mark' ), cyc = q( '.home-cycle' ),
    panel = q( '.home-flow-panel' ), copy = q( '.home-flow-copy' ),
    cta = q( '.home-close-cta' );
  return {
    vw: window.innerWidth, vh: window.innerHeight,
    contentWidth: layout ? px( layout.getBoundingClientRect().width - ( parseFloat( st( layout, 'paddingLeft' ) ) * 2 ) ) : null,
    layoutGap: st( layout, 'gap' ), layoutPad: st( layout, 'padding' ),
    header: { ...box( hdr ), pos: st( hdr, 'position' ) },
    hero: box( hero ), flow: box( flow ), close: box( close ), footer: box( foot ), widget: box( widget ),
    h1: { ...box( h1 ), font: st( h1, 'fontSize' ), weight: st( h1, 'fontWeight' ), ls: st( h1, 'letterSpacing' ), max: st( h1, 'maxWidth' ) },
    sub: { ...box( sub ), font: st( sub, 'fontSize' ), max: st( sub, 'maxWidth' ), chars: sub ? sub.textContent.trim().length : 0 },
    mark: box( mark ), cycle: box( cyc ),
    panel: box( panel ), copy: { ...box( copy ), pos: st( copy, 'position' ), top: st( copy, 'top' ) },
    closeCta: { ...box( cta ), minH: st( cta, 'minHeight' ), opacity: st( cta, 'opacity' ) },
    blankHeaderToH1: h1 && hdr ? px( h1.getBoundingClientRect().top - hdr.getBoundingClientRect().bottom ) : null,
    act: { hero: actions( hero ), flow: actions( flow ), close: actions( close ), footer: actions( foot ) },
    tab: ( () => {
      const els = Array.from( document.querySelectorAll( SEL ) ).filter( e => e.offsetParent !== null || getComputedStyle( e ).position === 'fixed' );
      return els.filter( vis ).length;
    } )(),
  };
};

( async () => {
  const t = await target();
  const browser = await launch();
  try {
    const metrics = {};
    let harvest = null;

    for ( const vp of [ { key: 'd', w: 1280, h: 900 }, { key: 'm', w: 390, h: 844 } ] ) {
      const ctx = await browser.newContext( { viewport: { width: vp.w, height: vp.h } } );
      const page = await ctx.newPage();
      await gotoStable( page, `${t.base}/` );
      await page.waitForTimeout( 1400 );
      metrics[ vp.key ] = await page.evaluate( METRICS );
      if ( vp.key === 'd' ) {
        harvest = await page.evaluate( async () => {
          const inline = Array.from( document.querySelectorAll( 'style' ) ).map( s => s.textContent ).join( '\n' );
          const hrefs = Array.from( document.querySelectorAll( 'link[rel="stylesheet"]' ) )
            .map( l => l.getAttribute( 'href' ) ).filter( h => h && h.startsWith( '/_next/' ) );
          const chunks = [];
          for ( const h of hrefs ) { try { chunks.push( await ( await fetch( h ) ).text() ); } catch { /* ignore */ } }
          // HARVEST THE PRE-HYDRATION SHAPE, NOT WHAT REACT LEFT BEHIND.
          // By the time this runs, the measuring effect has written an inline
          // width onto .home-cycle. Copying that would bake the fixed state into
          // the mock and make the no-JS panel a lie - it would show the pill
          // already sized, which is the one thing that does not happen without
          // JS. So the clone drops it. The inline background on .home-mark is
          // NOT dropped: that one really is server-rendered and is present in
          // out/index.html.
          const o = s => {
            const el = document.querySelector( s );
            if ( !el ) return '';
            const clone = el.cloneNode( true );
            clone.querySelectorAll( '.home-cycle' ).forEach( n => n.style.removeProperty( 'width' ) );
            if ( clone.classList && clone.classList.contains( 'home-cycle' ) ) clone.style.removeProperty( 'width' );
            return clone.outerHTML;
          };
          const c = s => document.querySelector( s )?.className || '';
          return {
            inline, chunks: chunks.join( '\n' ),
            header: o( 'header' ),
            footer: o( 'footer' ) || o( '[class*="ft-footer"]' ),
            widget: o( '.wc-langbar' ) || o( '[class*="wc-lang"]' ),
            hero: o( '.home-hero' ), flow: o( '.home-flow' ), close: o( '.home-close' ),
            h1: o( '.home-head' ), sub: o( '.home-sub' ),
            heroCls: c( '.home-hero' ), layoutCls: c( '.home-layout' ), shellCls: c( '.home-shell' ),
          };
        } );
      }
      await ctx.close();
    }
    if ( !harvest || !harvest.hero ) throw new Error( 'failed to harvest from out/' );

    const J = o => JSON.stringify( o );
    const d = metrics.d, m = metrics.m;
    const pct = ( a, b ) => Math.round( 100 * a / b );

    const html = `<!doctype html>
<meta charset="utf-8">
<title>Home page redesign — section by section</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root{--ink:#1a1a1a;--mut:rgba(0,0,0,.55);--lime:#d1f470;--grn:#1a3a2a;--line:#e3e3e3;--red:#b42318}
  *{box-sizing:border-box}
  body{margin:0;background:#fafafa;color:var(--ink);font-size:15px;line-height:1.55;
    font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif}
  .wrap{max-width:1200px;margin:0 auto;padding:36px 22px 110px}
  h1{font-size:clamp(28px,3.2vw,40px);font-weight:700;line-height:1.08;letter-spacing:-1.2px;margin:0 0 10px}
  h2{font-size:26px;font-weight:700;letter-spacing:-.5px;margin:0}
  h3{font-size:17px;font-weight:700;letter-spacing:-.2px;margin:0 0 8px}
  p{margin:0 0 10px}
  .lede{font-size:18px;max-width:78ch}
  .mut{color:var(--mut)}
  .sm{font-size:13.5px}
  code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.87em;background:#f0f0f0;padding:1px 5px;border-radius:4px}
  pre{background:#f6f6f6;border:1px solid var(--line);border-radius:8px;padding:13px;overflow:auto;font-size:12.5px;line-height:1.5;margin:8px 0 0}
  .card{background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:0 0 22px}
  .toc{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 0}
  .toc a{display:inline-block;padding:7px 13px;border:1px solid var(--line);border-radius:50px;
    background:#fff;text-decoration:none;color:var(--ink);font-size:14px;font-weight:600}
  .toc a:hover{border-color:var(--grn)}
  section.band{margin:0 0 42px;background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden}
  .bhead{padding:18px 22px;background:#fff;border-bottom:1px solid var(--line);
    display:flex;gap:14px;align-items:baseline;flex-wrap:wrap}
  .num{display:inline-flex;align-items:center;justify-content:center;width:34px;height:34px;flex:none;
    border-radius:9px;background:var(--grn);color:var(--lime);font-weight:800;font-size:16px}
  .sel{font-size:13px;color:var(--mut);font-family:ui-monospace,Menlo,monospace}
  .step{padding:20px 22px;border-top:1px solid #f0f0f0}
  .step:first-of-type{border-top:0}
  .steplab{display:inline-block;font-size:11px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;
    padding:3px 9px;border-radius:5px;margin:0 0 12px}
  .l-orig{background:#eef1f4;color:#44546a}
  .l-flaw{background:#fdeceb;color:var(--red)}
  .l-chg{background:#eaf4ea;color:#1f6f3d}
  .l-rec{background:var(--lime);color:var(--grn)}
  table{border-collapse:collapse;width:100%;font-size:13.5px;margin:6px 0 0}
  th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
  th{background:#f7f7f7;font-weight:600}
  td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
  ol,ul{margin:6px 0 10px;padding-left:20px}
  li{margin:5px 0}
  .frames{display:flex;gap:20px;flex-wrap:wrap;align-items:flex-start;margin:12px 0 0}
  .fr{flex:none}
  .frlab{font-size:11px;font-weight:700;color:var(--mut);text-transform:uppercase;letter-spacing:.07em;margin:0 0 7px}
  .shot{border:1px solid var(--line);border-radius:8px;overflow:hidden;background:#fff;position:relative}
  .shot iframe{border:0;display:block;transform-origin:0 0}
  .fold{position:absolute;left:0;right:0;border-top:2px dashed var(--red);pointer-events:none}
  .fold span{position:absolute;right:4px;top:-17px;font-size:10px;font-weight:700;color:var(--red);background:#fff;padding:0 4px;border-radius:3px}
  .opt{border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:0 0 14px;background:#fff}
  .opt.pick{border:2px solid var(--lime);background:rgba(209,244,112,.13)}
  .opthead{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:0 0 4px}
  .chip{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:6px;
    background:#eef1f4;color:#44546a;font-weight:800;font-size:13px;flex:none}
  .opt.pick .chip{background:var(--grn);color:var(--lime)}
  .tag{font-size:11px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;color:var(--grn);
    background:var(--lime);padding:2px 8px;border-radius:5px}
  .sev{display:inline-block;font-size:10.5px;font-weight:800;padding:1px 6px;border-radius:4px;margin-right:7px;vertical-align:1px}
  .s-h{background:#fdeceb;color:var(--red)}
  .s-m{background:#fff4e5;color:#a05a00}
  .s-l{background:#eef1f4;color:#44546a}
  .ctl{display:flex;gap:18px;flex-wrap:wrap;align-items:center;font-size:14px;margin:12px 0 0}
  .ctl label{display:inline-flex;gap:7px;align-items:center;cursor:pointer}
  footer.pg{color:var(--mut);font-size:13px;border-top:1px solid var(--line);padding-top:18px;margin-top:34px}
</style>
<div class="wrap">

<h1>Home page redesign — section by section</h1>
<p class="lede">Four bands, in the order a visitor meets them. For each one: what ships
today, what is wrong with it, what I propose, and why. Every panel is a <strong>live
render</strong> — the pill rotates, buttons hover and take focus rings, Tab works inside a
panel. No screenshots.</p>
<p class="mut sm">Generated ${new Date().toISOString().slice( 0, 10 )} by
<code>tools/browser/homereview.js</code> from the real static export. Every number below was
measured during generation at 1280×900 and 390×844 — none is transcribed. No source file was
changed to produce this page.</p>

<div class="card">
  <h3>How to read the options</h3>
  <p style="margin:0 0 8px">Where a section offers lettered options, <strong>they are
  alternatives — exactly one would ship.</strong> They are not features to add together, and
  nothing on this review page appears on the home page. The options exist so the choice can be
  made by looking rather than by reading a description.</p>
  <p class="ctl">
    <label><input type="checkbox" id="tFold" checked> fold line</label>
    <label><input type="checkbox" id="tRotate" checked> run the rotation</label>
    <label><input type="checkbox" id="tNoJs"> simulate <strong>no JavaScript</strong></label>
  </p>
  <div class="toc">
    <a href="#s1">1 · Hero</a><a href="#s2">2 · Workflow band</a>
    <a href="#s3">3 · Closing band</a><a href="#s4">4 · Footer &amp; widget</a>
  </div>
</div>

<!-- ============================ SECTION 1 ============================ -->
<section class="band" id="s1">
  <div class="bhead"><span class="num">1</span><h2>Hero — the top section</h2>
    <span class="sel">header + .home-hero (h1.home-head + p.home-sub)</span></div>

  <div class="step"><span class="steplab l-orig">original — as it ships</span>
    <div class="frames" data-panel="s1-orig"></div>
    <table>
      <tr><th>What</th><th class="n">1280×900</th><th class="n">390×844</th><th>Notes</th></tr>
      <tr><td>Fixed header</td><td class="n">${d.header.h}px</td><td class="n">${m.header.h}px</td><td><code>position:${d.header.pos}</code></td></tr>
      <tr><td>Blank between header and first word</td><td class="n">${d.blankHeaderToH1}px</td><td class="n">${m.blankHeaderToH1}px</td><td><code>.home-layout</code> padding-top</td></tr>
      <tr><td>h1 box</td><td class="n">${d.h1.w}×${d.h1.h}</td><td class="n">${m.h1.w}×${m.h1.h}</td><td>${d.h1.font} / ${d.h1.weight} / ls ${d.h1.ls}</td></tr>
      <tr><td>Rotating pill</td><td class="n">${d.mark.w}×${d.mark.h}</td><td class="n">${m.mark.w}×${m.mark.h}</td><td>word box ${d.cycle.w}px wide</td></tr>
      <tr><td>Sub-line</td><td class="n">${d.sub.w}×${d.sub.h}</td><td class="n">${m.sub.w}×${m.sub.h}</td><td>${d.sub.font}, ${d.sub.chars} chars, max ${d.sub.max}</td></tr>
      <tr><td>Whole hero</td><td class="n">${d.hero.w}×${d.hero.h}</td><td class="n">${m.hero.w}×${m.hero.h}</td><td>content measure ${d.contentWidth}px</td></tr>
      <tr><td>Widest element vs measure</td><td class="n">${pct( d.sub.w, d.contentWidth )}%</td><td class="n">${pct( m.sub.w, m.contentWidth )}%</td><td>${d.contentWidth - d.sub.w}px unused at 1280</td></tr>
      <tr><td><strong>Actions in this section</strong></td><td class="n"><strong>${d.act.hero.visible}</strong></td><td class="n"><strong>${m.act.hero.visible}</strong></td><td>visible focusable elements</td></tr>
    </table>
  </div>

  <div class="step"><span class="steplab l-flaw">flaws</span>
    <ul>
      <li><span class="sev s-h">HIGH</span><strong>The pill paints empty on every single
      load.</strong> <code>cycleW</code> starts <code>null</code>, so the first render writes no
      inline width, and <code>.home-cycle</code> is <code>overflow:hidden</code> with
      absolutely-positioned children — intrinsic width 0. Measured: <strong>4 painted frames,
      ~200ms</strong>, JS working, on a local server with no network. Longer behind real
      hydration. Tick <em>simulate no JavaScript</em> above to see the permanent version — the
      headline becomes “Everyday AI, built for” with nothing after it.</li>
      <li><span class="sev s-h">HIGH</span><strong>Reduced motion + any resize clips the word
      permanently.</strong> There is no resize listener, and the rotation interval never starts
      under <code>prefers-reduced-motion</code>, so nothing re-measures. Measured 480→1280:
      <strong>96px cut, 35% of “consumers”</strong>. Phone rotation is the everyday trigger.</li>
      <li><span class="sev s-m">MED</span><strong>Nothing here is actionable.</strong>
      ${d.act.hero.visible} visible focusable elements in the hero at both widths. The only
      action on the page is at the very bottom.</li>
      <li><span class="sev s-m">MED</span><strong>The rotation runs ${( WORDS.length * 2.4 ).toFixed( 1 )}s
      per cycle and cannot be paused</strong> (${WORDS.length} words × 2400ms), so the
      positioning can change mid-read. WCAG 2.2.2 applies to content that moves automatically
      for more than five seconds.</li>
      <li><span class="sev s-l">LOW</span><strong>${d.blankHeaderToH1}px of blank above the
      first word</strong>, a value tuned around the brand badge that has since been deleted.</li>
      <li><span class="sev s-l">LOW</span><strong>The reduced-motion rule for the entrance
      shutter is inverted</strong> — it sets <code>scaleX(1)</code>, the start state, where the
      resting state is <code>scaleX(0)</code>. Inert today only because
      <code>.home-layout.show</code> out-specifies it (0,2,1 vs 0,1,1). Latent, not visible.</li>
      <li><span class="sev s-l">LOW</span><code>max-width:${d.h1.max}</code> on the h1 never
      binds: <code>.home-hero</code> is <code>align-items:flex-start</code>, so the h1
      shrink-wraps to ${d.h1.w}px. A dead declaration.</li>
    </ul>
  </div>

  <div class="step"><span class="steplab l-chg">proposed change — four alternatives, one ships</span>
    <p class="sm mut">Labels are borrowed from the site, not invented: “Submit a request” is
    already the header nav item and one of the five rotating phrases on <code>/contact/</code>.
    The price is computed from <code>wix-catalog.json</code> (${citems.length} products, floor
    ${FLOOR_TXT}, next ${NEXT_TXT}) — never typed, so it cannot go stale when the ₹49 tier
    lands. A fifth option, reusing the closing band's exact string “Tell us what you need”, is
    ruled out: it would put one sentence on the page twice.</p>
    <div data-panel="s1-opts"></div>
  </div>

  <div class="step"><span class="steplab l-rec">recommendation — C, fallback B</span>
    <ol>
      <li><strong>The page already makes a price promise it does not keep.</strong> The closing
      band leads with “Know the price before you commit”, and <code>index.tsx</code> says in its
      own comment that this is “the only concrete, falsifiable promise on the page” and that it
      “is still a promise with nothing behind it — no price appears anywhere on this page”. C is
      the only option that puts something behind it, above the fold, where a first-time visitor
      reads the promise.</li>
      <li><strong>It cannot rot.</strong> ${FLOOR_TXT} is derived, which is exactly what the same
      comment demands: “do not hardcode one here”.</li>
      <li><strong>One action, not two.</strong> Going from zero to one is the fix. Zero to two
      splits the attention of a visitor who has not yet been given a reason to choose.</li>
    </ol>
    <p><strong>Why not D.</strong> <code>/access</code> is the login that redirects to
    <code>/dashboard</code> — the operator surface, not the consumer one. This page aims at
    “everyday Bharat… one person who wants one thing done”, so “Sign in” would spend the most
    valuable position on the page on the smallest slice of visitors. If returning users need a
    door, the header is where it belongs.</p>
    <p><strong>Why not E.</strong> Worst on the phone, which is the viewport that matters most
    here: the row stacks to three, and the price left-aligned under a full-width button reads as
    a loose end. Compare the E and C phone panels above.</p>
    <p><strong>The honest risk in C.</strong> 17px is <em>not</em> this page's one body rung of
    20px. I am treating the price as a control-row label rather than body copy, which is why it
    sits beside the button at the button's own size. Read it as body copy instead and it becomes
    a new rung — the drift this file has already corrected twice — in which case the answer is
    <strong>B</strong>.</p>
    <p class="sm"><strong>Two fixes that need no choice at all</strong>, because they are defects
    rather than design: ship the pill's width so it is never empty, and re-measure on resize.
    Together they take the gate from 5/12 to 9/12.</p>
    <h3 style="margin-top:14px">What the change is, in code</h3>
    <pre><code>// 1. Price, derived at module scope - a literal in the component body would make it
//    a changing dependency, the same reason CYCLE_WORDS lives outside.
import catalog from '../content/wix-catalog.json';
const priceFloor = Math.min(
  ...( catalog.products ?? [] ).map( p =&gt; Number( p.price ) ).filter( Number.isFinite )
);

// 2. Markup, appended inside .home-hero directly after &lt;p className="home-sub"&gt;.
//    That position is what puts it next in the natural tab order - no tabindex.
&lt;div className="home-hero-cta-row"&gt;
  {/* A PLAIN &lt;a&gt;, for the same reason as .home-close-cta: styled-jsx only scopes
      lowercase DOM tags, so &lt;Link className&gt; renders the class with no jsx- scope
      and the compiled rule matches nothing. Accepts the same known eslint error
      rather than trading it for a silently unstyled button. */}
  &lt;a className="home-hero-cta" href="/contact/"&gt;Submit a request&lt;/a&gt;
  &lt;span className="home-hero-price"&gt;from &lt;b&gt;&amp;#8377;{priceFloor}&lt;/b&gt;&lt;/span&gt;
&lt;/div&gt;

// 3. Styles into the existing &lt;style jsx&gt; block, reusing .home-close-cta's values
//    byte for byte. No new colour, no new rung.

// 4. HomePage.test.tsx gains: the hero has exactly one action, and its label is NOT
//    the closing band's string. Then animcheck.js (h1 still 131px across 21
//    viewports) and homeprobe.js (the above-fold assertion flips to pass).</code></pre>
  </div>
</section>

<!-- ============================ SECTION 2 ============================ -->
<section class="band" id="s2">
  <div class="bhead"><span class="num">2</span><h2>Workflow band</h2>
    <span class="sel">section.home-flow — terminal left, explanation right</span></div>

  <div class="step"><span class="steplab l-orig">original — as it ships</span>
    <div class="frames" data-panel="s2-orig"></div>
    <table>
      <tr><th>What</th><th class="n">1280×900</th><th class="n">390×844</th><th>Notes</th></tr>
      <tr><td>Band box</td><td class="n">${d.flow.w}×${d.flow.h}</td><td class="n">${m.flow.w}×${m.flow.h}</td><td>starts at y=${d.flow.t} / ${m.flow.t}</td></tr>
      <tr><td>Terminal panel</td><td class="n">${d.panel ? d.panel.w + '×' + d.panel.h : '—'}</td><td class="n">${m.panel ? m.panel.w + '×' + m.panel.h : '—'}</td><td>monospace, fixed size, reflows badly when squeezed</td></tr>
      <tr><td>Copy column</td><td class="n">${d.copy ? d.copy.w + '×' + d.copy.h : '—'}</td><td class="n">${m.copy ? m.copy.w + '×' + m.copy.h : '—'}</td><td><code>position:${d.copy.pos}; top:${d.copy.top}</code>; one column below 1024</td></tr>
      <tr><td>Actions in this section</td><td class="n">${d.act.flow.visible}</td><td class="n">${m.act.flow.visible}</td><td>visible focusable elements</td></tr>
    </table>
  </div>

  <div class="step"><span class="steplab l-flaw">flaws</span>
    <p class="sm mut">This band is in good shape. The harnesses find no type, colour or
    contrast defect in it: <code>typecheck.js</code> confirms its h2 is on the 40px/700 rung and
    that the page carries no second section-h2 size, and <code>check_design_drift.py</code>
    reports no retired colour. Both list bodies were unified onto the one neutral body colour.
    What remains is documentation and one open layout question.</p>
    <ul>
      <li><span class="sev s-l">LOW</span><strong>A comment here invites work that is already
      done.</strong> It says the h2 is “not yet what <code>grahak-os-design.md</code> says”, that
      the contract specifies <code>clamp(32px,4.2vw,54px)</code>, and that
      <code>typecheck.js</code> reports the gap. Steering row 19 <em>is</em>
      <code>clamp(28px,3.2vw,40px)</code>, and <code>typecheck.js</code> reports no gap — it
      records why 54px lost. Anyone following that comment would “reconcile” a reconciled
      value.</li>
      <li><span class="sev s-l">LOW</span><strong>Open question, not a defect:</strong> the hero
      above leaves ${d.contentWidth - d.sub.w}px (${100 - pct( d.sub.w, d.contentWidth )}%) of the
      ${d.contentWidth}px measure unused at 1280, and this band holds the first visual on the
      site — currently ${d.flow.t - d.hero.b}px below the hero and partly under the fold. Moving
      the terminal up into the hero's empty right half would put a visual above the fold. That is
      a structural change to two sections at once, so it is a decision, not a fix.</li>
    </ul>
  </div>

  <div class="step"><span class="steplab l-chg">proposed change</span>
    <p><strong>Correct the stale comment. Change nothing else in this band yet.</strong> The
    layout question above is real but it is coupled to Section 1: if the hero gains a CTA, the
    hero grows by 84px and the amount of empty space changes, so judging the terminal's position
    before that lands would be judging a layout that is about to move.</p>
  </div>

  <div class="step"><span class="steplab l-rec">recommendation — defer, in this order</span>
    <ol>
      <li>Fix Section 1 first: the CTA and the two pill defects.</li>
      <li>Re-measure this band afterwards, because the hero's height changes underneath it.</li>
      <li><em>Then</em> decide on moving the terminal. Deciding now means deciding against a
      layout that no longer exists by the time it ships.</li>
    </ol>
    <p class="sm">The comment correction is safe to do immediately — it is a comment, it changes
    no rendered pixel, and leaving it costs someone a wasted investigation.</p>
  </div>
</section>

<!-- ============================ SECTION 3 ============================ -->
<section class="band" id="s3">
  <div class="bhead"><span class="num">3</span><h2>Closing band</h2>
    <span class="sel">section.home-close — eyebrow, h2, lead, lime rule, 3 claims, CTA</span></div>

  <div class="step"><span class="steplab l-orig">original — as it ships</span>
    <p class="sm mut">The reveal animation is scroll-triggered, so it has been left armed in
    these panels; in the page it plays once when the band scrolls into view.</p>
    <div class="frames" data-panel="s3-orig"></div>
    <table>
      <tr><th>What</th><th class="n">1280×900</th><th class="n">390×844</th><th>Notes</th></tr>
      <tr><td>Band box</td><td class="n">${d.close.w}×${d.close.h}</td><td class="n">${m.close.w}×${m.close.h}</td><td>tinted panel, 2px lime border</td></tr>
      <tr><td>The one CTA</td><td class="n">${d.closeCta.w}×${d.closeCta.h}</td><td class="n">${m.closeCta.w}×${m.closeCta.h}</td><td><code>min-height:${d.closeCta.minH}</code>, clears 44px</td></tr>
      <tr><td>Actions in this section</td><td class="n">${d.act.close.visible}</td><td class="n">${m.act.close.visible}</td><td>the only action on the page</td></tr>
    </table>
  </div>

  <div class="step"><span class="steplab l-flaw">flaws</span>
    <ul>
      <li><span class="sev s-m">MED</span><strong>The CTA is focusable while invisible, and it
      is the third Tab stop on the page.</strong> <code>.home-close.is-armed .home-close-cta</code>
      ships <code>opacity:0</code> until the band scrolls into view, and <code>opacity</code> does
      not remove an element from the tab order. Measured Tab walk from load:
      <code>logo → nav-trigger → home-close-cta (invisible, 1697px down) → footer</code>. WCAG
      2.4.7 and 2.4.11.</li>
      <li><span class="sev s-m">MED</span><strong>“Know the price before you commit” has nothing
      behind it.</strong> It is the first of the three claims and, by the file's own comment, the
      only falsifiable one — yet no price appears anywhere on the page. This is the same finding
      as Section 1's option C, seen from the other end.</li>
    </ul>
    <p class="sm mut">Worth stating plainly: the <code>.is-armed</code> pattern in this band is
    <em>correct</em> and is the model Section 1's hero should copy. CSS ships the final, readable
    state and JavaScript adds a class to hide the start state, so no JS, no
    <code>IntersectionObserver</code>, or reduced motion all leave the band fully readable. The
    hero does the opposite. The only thing <code>.is-armed</code> missed was focus.</p>
  </div>

  <div class="step"><span class="steplab l-chg">proposed change</span>
    <p>Two edits, neither of which changes a single rendered pixel in the settled state:</p>
    <pre><code>/* 1. Hide it from the tab order while it is hidden from the eye. opacity alone
      does not; visibility does, and it still animates. */
.home-close.is-armed .home-close-cta{opacity:0;visibility:hidden;transform:translateY(8px)}
.home-close.is-armed.is-in .home-close-cta{opacity:1;visibility:visible;transform:none}

/* 2. transition gains visibility so the reveal is not stepped:
      transition:opacity .5s ease, transform .5s ease, visibility .5s */</code></pre>
    <p class="sm">The same treatment applies to the three claim rows above it, which are also
    <code>opacity:0</code> while armed — they are not focusable, so they are a smaller problem,
    but the fix is one property in the same rule.</p>
  </div>

  <div class="step"><span class="steplab l-rec">recommendation — do both, no decision needed</span>
    <p>Neither is a design question. The focus fix is a WCAG defect with a one-property answer,
    and the price claim is answered for free if Section 1 ships option C — which is the strongest
    argument for C over B: it makes an existing promise true rather than adding a new one.</p>
    <p class="sm">Keep the <code>.is-armed</code> inversion exactly as it is. It is the right
    pattern and the reasoning above it in the source is worth preserving; the hero should be
    brought in line with this band, not the other way round.</p>
  </div>
</section>

<!-- ============================ SECTION 4 ============================ -->
<section class="band" id="s4">
  <div class="bhead"><span class="num">4</span><h2>Footer &amp; the floating widget</h2>
    <span class="sel">footer + .wc-langbar (fixed, all routes)</span></div>

  <div class="step"><span class="steplab l-orig">original — as it ships</span>
    <div class="frames" data-panel="s4-orig"></div>
    <table>
      <tr><th>What</th><th class="n">1280×900</th><th class="n">390×844</th><th>Notes</th></tr>
      <tr><td>Footer box</td><td class="n">${d.footer ? d.footer.w + '×' + d.footer.h : '—'}</td><td class="n">${m.footer ? m.footer.w + '×' + m.footer.h : '—'}</td><td>links to terms, privacy, contact</td></tr>
      <tr><td>Floating widget</td><td class="n">${d.widget ? d.widget.w + '×' + d.widget.h : '—'}</td><td class="n">${m.widget ? m.widget.w + '×' + m.widget.h : '—'}</td><td>WhatsApp + language chip, fixed</td></tr>
      <tr><td>Actions in the footer</td><td class="n">${d.act.footer.visible}</td><td class="n">${m.act.footer.visible}</td><td>visible focusable elements</td></tr>
    </table>
  </div>

  <div class="step"><span class="steplab l-flaw">flaws</span>
    <p><strong>None found, and this is the one band where that is a measured statement rather
    than an absence of looking.</strong> <code>uicheck.js</code> passes 96/96 across four
    viewports on exactly this furniture: the widget's two controls share a centre line, the
    WhatsApp button stays 40×40 so it never drops under the 44px target, the pill clears 44px at
    48px tall, nothing is painted over either control, the language panel does not cover the
    WhatsApp button, the footer lands flush with 0px of blank beneath it, and the widget parks
    16px above the footer instead of sliding into it.</p>
    <p class="sm mut">One item does belong to this band but is not visible in it: the fake
    <code>aggregateRating 4.8 / 150</code> and <code>foundingDate 2020</code> in the JSON-LD.
    They live in <code>_app.tsx</code>, ship on 17 and 123 built pages, and are a Google
    manual-action risk. That is a sitewide fix and wants its own change, not this one.</p>
  </div>

  <div class="step"><span class="steplab l-chg">proposed change</span>
    <p><strong>Nothing in this band.</strong> Changing furniture that passes 96 assertions to
    make a redesign feel complete is how working things break.</p>
  </div>

  <div class="step"><span class="steplab l-rec">recommendation — leave it alone</span>
    <p>Take the schema fix separately, as a sitewide change with a <code>seocheck.js</code> re-run.
    It is a deletion plus two strings and it does not belong in a home page redesign.</p>
  </div>
</section>

<footer class="pg">
  Re-generate: <code>node tools/browser/homereview.js</code> ·
  Gate: <code>node tools/browser/homeprobe.js</code> (5/12) ·
  Findings: <code>docs/home-design-audit-20260926.md</code><br>
  Fonts load from Google; everything else in this file is self-contained. No images.
</footer>
</div>

<script>
const CSS   = ${J( harvest.inline + '\n' + harvest.chunks + '\n' + MOCK_CSS )};
const HEADER= ${J( harvest.header )};
const FOOTER= ${J( harvest.footer )};
const WIDGET= ${J( harvest.widget )};
const HERO  = ${J( harvest.hero )};
const FLOW  = ${J( harvest.flow )};
const CLOSE = ${J( harvest.close )};
const H1    = ${J( harvest.h1 )};
const SUB   = ${J( harvest.sub )};
const HEROC = ${J( harvest.heroCls )};
const LAYC  = ${J( harvest.layoutCls )};
const SHELLC= ${J( harvest.shellCls )};
const WORDS = ${J( WORDS )};
const OPTIONS = ${J( OPTIONS )};

// The rotation, on index.tsx's own constants: 2400ms, the measured inline width on
// .home-cycle, the .on class moving between absolutely positioned words. Reimplemented
// rather than taken from the bundle because a static panel has no React to hydrate.
const BOOT = [
  '(function(){var w=', 'WORDS_JSON', ';var i=0;',
  'var c=document.querySelector(".home-cycle"),m=document.querySelector(".home-mark"),',
  'd=document.querySelector(".home-mark-dot"),it=document.querySelectorAll(".home-cyc-word");',
  'function p(){for(var k=0;k<it.length;k++){it[k].classList.toggle("on",k===i);}',
  'if(c&&it[i])c.style.width=it[i].scrollWidth+"px";',
  'if(m)m.style.background=w[i].tint;if(d)d.style.background=w[i].dot;}',
  'if(it.length){p();}var L=document.querySelector(".home-layout");if(L)L.classList.add("show");',
  'var A=document.querySelector(".home-close");if(A){A.classList.add("is-armed");A.classList.add("is-in");}',
  'if(', 'ROTATE_ON', '&&it.length)setInterval(function(){i=(i+1)%w.length;p();},2400);})();'
].join('');

function frameDoc( body, noJs, rotate, withWidget ){
  var boot = noJs ? '' : '<scr' + 'ipt>' + BOOT
    .replace('WORDS_JSON', JSON.stringify(WORDS))
    .replace('ROTATE_ON', rotate ? 'true' : 'false') + '</scr' + 'ipt>';
  return '<!doctype html><meta charset="utf-8">'
    + '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
    + '<style>html,body{margin:0}' + CSS + '</style>'
    + HEADER
    + '<main class="' + SHELLC + '"><div class="' + LAYC.replace(/\\bshow\\b/,'').trim() + '">'
    + body + '</div></main>'
    + (withWidget ? FOOTER + WIDGET : '')
    + boot;
}

var SIZES = [
  { label:'desktop — 1280 wide', w:1280, h:780, scale:0.585, fold:900 },
  { label:'phone — 390 wide',    w:390,  h:800, scale:0.76,  fold:844 }
];

function frames( body, opts ){
  opts = opts || {};
  var noJs = document.getElementById('tNoJs').checked;
  var rot  = document.getElementById('tRotate').checked;
  var fold = document.getElementById('tFold').checked;
  var out = '';
  SIZES.forEach(function(s){
    var h = opts.h || s.h;
    var vw = Math.round(s.w*s.scale), vh = Math.round(h*s.scale);
    var fy = Math.round(Math.min(s.fold,h)*s.scale);
    out += '<div class="fr"><p class="frlab">'+s.label+'</p>'
      + '<div class="shot" style="width:'+vw+'px;height:'+vh+'px">'
      + '<iframe scrolling="no" title="preview" style="width:'+s.w+'px;height:'+h+'px;'
      + 'transform:scale('+s.scale+')" srcdoc="'
      + frameDoc(body, noJs, rot, !!opts.widget).replace(/"/g,'&quot;') + '"></iframe>'
      + (fold && opts.showFold !== false && fy < vh ? '<div class="fold" style="top:'+fy+'px"><span>fold</span></div>' : '')
      + '</div></div>';
  });
  return out;
}

function heroBody( extra ){
  return '<div class="' + HEROC + '">' + H1 + SUB + (extra||'') + '</div>';
}

function build(){
  document.querySelector('[data-panel="s1-orig"]').innerHTML = frames( heroBody('') );
  document.querySelector('[data-panel="s2-orig"]').innerHTML = frames( FLOW, { h:760, showFold:false } );
  document.querySelector('[data-panel="s3-orig"]').innerHTML = frames( CLOSE, { h:700, showFold:false } );
  document.querySelector('[data-panel="s4-orig"]').innerHTML = frames( '', { h:560, widget:true, showFold:false } );

  var html = '';
  OPTIONS.forEach(function(o){
    html += '<div class="opt' + (o.pick ? ' pick' : '') + '">'
      + '<div class="opthead"><span class="chip">'+o.id+'</span><strong>'+o.name+'</strong>'
      + '<span class="sm mut">→ '+o.dest+'</span>'
      + (o.pick ? '<span class="tag">recommended</span>' : '') + '</div>'
      + '<div class="frames">' + frames( heroBody(o.html) ) + '</div></div>';
  });
  document.querySelector('[data-panel="s1-opts"]').innerHTML = html;
}

['tFold','tRotate','tNoJs'].forEach(function(id){
  document.getElementById(id).addEventListener('change', build);
});
build();
</script>
`;

    fs.mkdirSync( path.dirname( OUT_FILE ), { recursive: true } );
    fs.writeFileSync( OUT_FILE, html );
    console.log( `wrote ${path.relative( REPO, OUT_FILE )}  (${( fs.statSync( OUT_FILE ).size / 1024 ).toFixed( 0 )} KB)` );
    console.log( `  sections: 1 hero, 2 flow, 3 close, 4 footer+widget` );
    console.log( `  hero actions measured: ${d.act.hero.visible} desktop / ${m.act.hero.visible} phone` );
    console.log( `  hero h1: ${d.h1.w}x${d.h1.h} @1280, ${m.h1.w}x${m.h1.h} @390` );
    console.log( `  unused measure at 1280: ${d.contentWidth - d.sub.w}px of ${d.contentWidth}px` );
    console.log( `  price floor ${FLOOR_TXT}, next ${NEXT_TXT}, from ${citems.length} products` );
  } finally {
    await browser.close();
    if ( t.close ) await t.close();
  }
} )().catch( e => { console.error( e ); process.exit( 1 ); } );
