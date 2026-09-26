'use strict';

/**
 * homereview - ONE self-contained HTML page reviewing the home page's TOP SECTION only.
 *
 * SCOPE, DELIBERATELY NARROW. The top band of the home page, and inside it only the fixes
 * that need no design decision - the three defects. Nothing else is in here: not the two
 * judgement calls, not the other three bands, not the sitewide schema, and not the
 * propagation to the other public pages. Those are listed at the end so they are not lost,
 * but they are out of scope until this band is signed off.
 *
 * THE BRIEF THIS FOLLOWS. The top band's job is to say what the page is about. No call to
 * action, no price, no conversion furniture - the action stays in the closing band where it
 * already is. The band is chrome shared by every public page; only the words, the rotation
 * and the sub-line change per page. So "nothing actionable above the fold" is a DECISION,
 * not a defect, and the CTA options previously put up here are withdrawn.
 *
 * WHAT MAKES THIS TRUSTWORTHY. The CSS, the markup and every measurement are extracted from
 * the real static export at generation time, so the mock cannot drift from the page the way
 * a hand-pasted copy does. Panels are real documents at 1280 and 390, only visually scaled,
 * so clamp(36px,4.3vw,60px) resolves exactly as it would at that viewport. They are live:
 * the pill rotates and focus rings appear. No images.
 *
 * HOW THE "BEFORE" STATES ARE REPRODUCED, deterministically rather than by luck:
 *   - no JavaScript   the boot script is omitted, which is the real condition
 *   - reduced motion  the rules inside @media(prefers-reduced-motion) are applied directly,
 *                     because a preference cannot be set inside a preview frame
 *   - the stale width the width measured at 390 is written onto a 1280-wide frame, which is
 *                     exactly what the missing resize listener leaves behind
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

// ---- derived: the rotating words, parsed from source --------------------------
const src = fs.readFileSync( path.join( REPO, 'src', 'pages', 'index.tsx' ), 'utf8' );
const cb = /const CYCLE_WORDS = \[([\s\S]*?)\];/.exec( src );
if ( !cb ) throw new Error( 'could not parse CYCLE_WORDS from src/pages/index.tsx' );
const WORDS = [ ...cb[ 1 ].matchAll( /word:\s*'([^']+)',\s*tint:\s*'([^']+)',\s*dot:\s*'([^']+)'/g ) ]
  .map( m => ( { word: m[ 1 ], tint: m[ 2 ], dot: m[ 3 ] } ) );
if ( !WORDS.length ) throw new Error( 'CYCLE_WORDS parsed empty' );

// ---- the two fixes under review: the only original code in this file ---------
// Both are defect repairs with no design content. In the settled, happy-path state they
// change nothing a visitor sees - which is the point, and which the last panel proves.
// `JSX` is replaced with the page's real styled-jsx hash class before injection. Without
// it these rules are a class short of the ones they must override - styled-jsx compiles
// `.home-mark::before` to `.home-mark.jsx-HASH::before`, which is (0,2,1) - and the mock
// would show a fix that silently does not apply. Written in-source the hash is added
// automatically, so this is a mock concern only. Found by measuring the panels rather
// than by reading them.
const FIX_CSS = `
  /* ===== FIX A - the pill is sized by CSS, so it is never empty =====
     The active word returns to normal flow, which gives .home-cycle a real intrinsic
     width; the inactive words stay absolute so they still stack in the same place.
     width:max-content is the resting value. JavaScript still writes an explicit px
     width over it, which is what animates - so the glide is unchanged, and the
     first-paint and no-JS states show the word instead of nothing.

     display:inline-block IS LOAD-BEARING, and it is the whole reason this fix was
     measured before being written. position:static alone turns the span back into a
     non-replaced INLINE box, and offsetWidth/scrollWidth are 0 for those - so the
     existing measuring effect would write width:0px over max-content and the pill
     would collapse on every load WITH JavaScript, turning a 200ms flash into a
     permanent one. inline-block keeps it in flow and keeps it measurable. */
  .home-cycleJSX{width:max-content}
  .home-cyc-word.onJSX{position:static;display:inline-block}

  /* ===== FIX C - the reduced-motion resting state is the shutter GONE, not covering =====
     Was scaleX(1), which is the START state: a white panel over the tint. Inert today
     only because .home-layout.show out-specifies it, which is not a thing to rely on. */
  .home-markJSX::before{transform:scaleX(0)}
`;
// Simulates what @media(prefers-reduced-motion:reduce) does, since a preference cannot
// be set inside a preview frame.
const REDUCED_BEFORE = `
  .home-markJSX::before,.home-mark-dotJSX{transition:none}
  .home-markJSX::before{transform:scaleX(1)}
  .home-mark-dotJSX{transform:scale(1)}
  .home-cycleJSX,.home-cyc-wordJSX{transition:none}
`;
const REDUCED_AFTER = REDUCED_BEFORE.replace( 'scaleX(1)}', 'scaleX(0)}' );

const METRICS = () => {
  const px = n => Math.round( n );
  const q = s => document.querySelector( s );
  const box = el => { if ( !el ) return null; const b = el.getBoundingClientRect(); return { t: px( b.top ), l: px( b.left ), w: px( b.width ), h: px( b.height ), b: px( b.bottom ) }; };
  const st = ( el, p ) => ( el ? getComputedStyle( el )[ p ] : null );
  const vis = el => { for ( let n = el; n; n = n.parentElement ) { const c = getComputedStyle( n ); if ( c.visibility === 'hidden' || c.display === 'none' || +c.opacity === 0 ) return false; } return true; };
  const SEL = 'a[href],button,input,select,textarea,[role="button"],[tabindex]:not([tabindex="-1"])';
  const hdr = q( 'header' ), hero = q( '.home-hero' ), layout = q( '.home-layout' ),
    h1 = q( '.home-head' ), line = q( '.home-head-line' ), sub = q( '.home-sub' ),
    mark = q( '.home-mark' ), dot = q( '.home-mark-dot' ), cyc = q( '.home-cycle' ),
    flow = q( '.home-flow' );
  return {
    vw: window.innerWidth, vh: window.innerHeight,
    contentWidth: layout ? px( layout.getBoundingClientRect().width - parseFloat( st( layout, 'paddingLeft' ) ) * 2 ) : null,
    header: { ...box( hdr ), pos: st( hdr, 'position' ) },
    padTop: st( layout, 'paddingTop' ), gap: st( layout, 'gap' ),
    hero: box( hero ),
    h1: { ...box( h1 ), font: st( h1, 'fontSize' ), weight: st( h1, 'fontWeight' ), lh: st( h1, 'lineHeight' ),
      ls: st( h1, 'letterSpacing' ), max: st( h1, 'maxWidth' ), text: h1 ? h1.textContent.replace( /\s+/g, ' ' ).trim() : '' },
    line: box( line ), mark: box( mark ), dot: box( dot ), cycle: box( cyc ),
    sub: { ...box( sub ), font: st( sub, 'fontSize' ), lh: st( sub, 'lineHeight' ), max: st( sub, 'maxWidth' ),
      chars: sub ? sub.textContent.trim().length : 0, text: sub ? sub.textContent.replace( /\s+/g, ' ' ).trim() : '' },
    flowTop: flow ? box( flow ).t : null,
    blank: h1 && hdr ? px( h1.getBoundingClientRect().top - hdr.getBoundingClientRect().bottom ) : null,
    actions: hero ? Array.from( hero.querySelectorAll( SEL ) ).filter( vis ).length : 0,
  };
};

( async () => {
  const t = await target();
  const browser = await launch();
  try {
    const M = {};
    let harvest = null;
    for ( const vp of [ { k: 'd', w: 1280, h: 900 }, { k: 'm', w: 390, h: 844 } ] ) {
      const ctx = await browser.newContext( { viewport: { width: vp.w, height: vp.h } } );
      const page = await ctx.newPage();
      await gotoStable( page, `${t.base}/` );
      await page.waitForTimeout( 1400 );
      M[ vp.k ] = await page.evaluate( METRICS );
      if ( vp.k === 'd' ) {
        harvest = await page.evaluate( async () => {
          const inline = Array.from( document.querySelectorAll( 'style' ) ).map( s => s.textContent ).join( '\n' );
          const hrefs = Array.from( document.querySelectorAll( 'link[rel="stylesheet"]' ) )
            .map( l => l.getAttribute( 'href' ) ).filter( h => h && h.startsWith( '/_next/' ) );
          const chunks = [];
          for ( const h of hrefs ) { try { chunks.push( await ( await fetch( h ) ).text() ); } catch { /* ignore */ } }
          // HARVEST THE PRE-HYDRATION SHAPE. By now the measuring effect has written an
          // inline width onto .home-cycle; copying it would bake the fixed state in and make
          // the no-JS panel a lie, since a sized pill is the one thing that never happens
          // without JS. The inline background on .home-mark is kept - that one really is
          // server-rendered and is present in out/index.html.
          const o = s => {
            const el = document.querySelector( s );
            if ( !el ) return '';
            const c = el.cloneNode( true );
            c.querySelectorAll( '.home-cycle' ).forEach( n => n.style.removeProperty( 'width' ) );
            return c.outerHTML;
          };
          const cls = s => document.querySelector( s )?.className || '';
          return {
            inline, chunks: chunks.join( '\n' ),
            header: o( 'header' ), h1: o( '.home-head' ), sub: o( '.home-sub' ),
            heroCls: cls( '.home-hero' ), layoutCls: cls( '.home-layout' ), shellCls: cls( '.home-shell' ),
          };
        } );
      }
      await ctx.close();
    }
    if ( !harvest || !harvest.h1 ) throw new Error( 'failed to harvest from out/' );

    // The styled-jsx scoping class, read off the harvested markup. Injected rules must
    // carry it or they lose the specificity contest against the page's own compiled rules
    // and the mock shows a fix that never applied.
    const jsxHash = ( /class="([^"]*\bjsx-[a-z0-9]+)\b/.exec( harvest.h1 ) || [] )[ 1 ]
      ?.split( /\s+/ ).find( c => c.startsWith( 'jsx-' ) );
    if ( !jsxHash ) throw new Error( 'could not read the styled-jsx scoping class from the harvested h1' );
    const scope = css => css.replace( /JSX/g, `.${jsxHash}` );

    const J = o => JSON.stringify( o );
    const d = M.d, m = M.m;
    const staleW = m.cycle.w, needW = d.cycle.w;
    const clipped = needW - staleW;
    const esc = s => String( s ).replace( /&/g, '&amp;' ).replace( /</g, '&lt;' ).replace( />/g, '&gt;' );

    const html = `<!doctype html>
<meta charset="utf-8">
<title>Home page — top section: the three defect fixes</title>
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
  h3{font-size:16.5px;font-weight:700;letter-spacing:-.2px;margin:0}
  p{margin:0 0 10px}
  .lede{font-size:18px;max-width:80ch}
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
  .steplab{display:inline-block;font-size:11px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;padding:3px 9px;border-radius:5px;margin:0 0 12px}
  .l-orig{background:#eef1f4;color:#44546a} .l-fix{background:#eaf4ea;color:#1f6f3d}
  .l-proof{background:var(--lime);color:var(--grn)} .l-open{background:#fff4e5;color:var(--amb)}
  table{border-collapse:collapse;width:100%;font-size:13.5px;margin:6px 0 0}
  th,td{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
  th{background:#f7f7f7;font-weight:600}
  td.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
  ol,ul{margin:6px 0 10px;padding-left:20px} li{margin:5px 0}
  .sev{display:inline-block;font-size:10.5px;font-weight:800;padding:2px 7px;border-radius:4px;flex:none}
  .s-h{background:#fdeceb;color:var(--red)} .s-m{background:#fff4e5;color:var(--amb)} .s-l{background:#eef1f4;color:#44546a}
  .ba{display:flex;gap:20px;flex-wrap:wrap;align-items:flex-start;margin:12px 0 0}
  .col{flex:none}
  .collab{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.07em;margin:0 0 7px;padding:2px 7px;border-radius:4px;display:inline-block}
  .c-b{background:#fdeceb;color:var(--red)} .c-a{background:#eefaf0;color:#1f6f3d}
  .shot{border:1px solid var(--line);border-radius:8px;overflow:hidden;background:#fff;position:relative}
  .shot iframe{border:0;display:block;transform-origin:0 0}
  .readout{font-family:ui-monospace,Menlo,monospace;font-size:12px;background:#f6f6f6;border:1px solid var(--line);
    border-radius:6px;padding:8px 10px;margin:8px 0 0;white-space:pre-wrap;word-break:break-word}
  .ctl{display:flex;gap:18px;flex-wrap:wrap;align-items:center;font-size:14px;margin:12px 0 0}
  .ctl label{display:inline-flex;gap:7px;align-items:center;cursor:pointer}
  footer.pg{color:var(--mut);font-size:13px;border-top:1px solid var(--line);padding-top:18px;margin-top:34px}
  /* ---- design-first comparison layout ---- */
  .cmp{display:flex;gap:18px;flex-wrap:wrap;align-items:flex-start;margin:0 0 14px}
  .cmpcol{flex:none}
  .cap{font-size:14px;color:var(--mut);margin:0 0 14px;max-width:110ch}
  .cap b{color:var(--ink)}
  details.why{border:1px solid var(--line);border-radius:9px;background:#fcfcfc;margin:14px 0 0}
  details.why>summary{cursor:pointer;padding:10px 14px;font-size:13px;font-weight:700;color:#44546a;
    list-style:none;display:flex;gap:8px;align-items:center}
  details.why>summary::-webkit-details-marker{display:none}
  details.why>summary::before{content:'▸';font-size:11px}
  details.why[open]>summary::before{content:'▾'}
  details.why>summary:hover{color:var(--ink)}
  details.why .inner{padding:0 14px 14px;border-top:1px solid var(--line);margin-top:0;padding-top:12px}
  .bar{position:sticky;top:0;z-index:5;background:rgba(250,250,250,.94);backdrop-filter:blur(6px);
    border-bottom:1px solid var(--line);padding:10px 0;margin:0 0 20px}
  .bar .in{display:flex;gap:20px;flex-wrap:wrap;align-items:center;font-size:14px}
</style>
<div class="wrap">

<h1>Home page — top band</h1>
<p class="cap" style="font-size:16px"><b>Three defects, each shown before and after.</b> Every
panel is the real page at a real width — 1280 and 390 — running live. Written notes are folded
away behind “why / the code” so the design is what you see first.</p>

<div class="bar"><div class="in">
  <label><input type="checkbox" id="tRotate" checked> run the rotation</label>
  <label><input type="checkbox" id="tNotes"> show all written notes</label>
  <span class="mut sm">scope: top band only · no CTA, no price — this band says what the page is
  about · nothing has been changed in the source</span>
</div></div>

<!-- ===================== ORIGINAL ===================== -->
<section class="band">
  <div class="bhead"><span class="tag">NOW</span><h2>As it ships today</h2>
    <span class="sel">header + .home-hero</span></div>
  <div class="step">
    <div data-panel="orig"></div>
    <details class="why" data-note><summary>measurements</summary><div class="inner">
      <table>
        <tr><th>What</th><th class="n">1280×900</th><th class="n">390×844</th><th>Notes</th></tr>
        <tr><td>Fixed header — shared chrome</td><td class="n">${d.header.h} px</td><td class="n">${m.header.h} px</td><td><code>position:${d.header.pos}</code></td></tr>
        <tr><td>Blank above the first word</td><td class="n">${d.blank} px</td><td class="n">${m.blank} px</td><td><code>.home-layout</code> padding-top ${d.padTop}</td></tr>
        <tr><td>h1 — frame line + pill line</td><td class="n">${d.h1.w}×${d.h1.h}</td><td class="n">${m.h1.w}×${m.h1.h}</td><td>${d.h1.font} / ${d.h1.weight} / lh ${d.h1.lh} / ls ${d.h1.ls}</td></tr>
        <tr><td>Rotating pill</td><td class="n">${d.mark.w}×${d.mark.h}</td><td class="n">${m.mark.w}×${m.mark.h}</td><td>dot ${d.dot.w} px, word box ${d.cycle.w} / ${m.cycle.w} px</td></tr>
        <tr><td>Sub-line — the per-page sentence</td><td class="n">${d.sub.w}×${d.sub.h}</td><td class="n">${m.sub.w}×${m.sub.h}</td><td>${d.sub.font}, ${d.sub.chars} chars, max ${d.sub.max}</td></tr>
        <tr><td>Whole band</td><td class="n">${d.hero.w}×${d.hero.h}</td><td class="n">${m.hero.w}×${m.hero.h}</td><td>measure ${d.contentWidth} px; next band at y=${d.flowTop}</td></tr>
        <tr><td>Actions in the band</td><td class="n">${d.actions}</td><td class="n">${m.actions}</td><td><strong>by design</strong></td></tr>
      </table>
      <p class="sm mut" style="margin-top:10px">Rotation: ${WORDS.map( w => `<code>${w.word}</code>` ).join( ' · ' )}, every 2400ms.</p>
    </div></details>
  </div>
</section>

<!-- ===================== FIX A ===================== -->
<section class="band">
  <div class="bhead"><span class="tag">A</span><span class="sev s-h">HIGH</span>
    <h2>The word is missing on every load</h2></div>
  <div class="step">
    <p class="cap">The pill renders <b>empty</b> — the headline reads “Everyday AI, built for” with
    nothing after it. ~200ms on every normal load, and <b>permanently without JavaScript</b>, which
    is the state shown here.</p>
    <div data-panel="fixA"></div>
    <details class="why" data-note><summary>why / the code</summary><div class="inner">
      <p><code>cycleW</code> starts <code>null</code>, so the first render writes no inline width.
      <code>.home-cycle</code> is <code>overflow:hidden</code> and all four words inside are
      <code>position:absolute</code>, so they add nothing to its intrinsic width — it computes to
      <strong>0px</strong> and clips the word away. Measured on a normal load with JS working, local
      server, no network: <strong>4 painted frames, ~200ms</strong>. Behind real hydration, longer.</p>
      <p>Fix — make CSS responsible for the resting width. The active word returns to flow so the
      pill has an intrinsic width; the others stay absolute and keep stacking. JS still writes a px
      width over it, so <strong>the glide is unchanged</strong>.</p>
      <pre><code>.home-cycle{width:max-content}   /* resting width, needs no JS */
.home-cyc-word.on{
  position:static;      /* the visible word sits in flow, so the pill has a width */
  display:inline-block; /* NOT optional - see below */
}</code></pre>
      <p class="sm" style="margin-top:10px"><strong><code>display:inline-block</code> is
      load-bearing, and measuring this mock is what caught it.</strong> <code>position:static</code>
      alone turns the span back into a non-replaced <em>inline</em> box, and <code>offsetWidth</code>
      is 0 for those — so the existing measuring effect would write <code>width:0px</code> over
      <code>max-content</code> and the pill would collapse on every load <em>with</em> JavaScript,
      turning a 200ms flash into a permanent one.</p>
    </div></details>
  </div>
</section>

<!-- ===================== FIX B ===================== -->
<section class="band">
  <div class="bhead"><span class="tag">B</span><span class="sev s-h">HIGH</span>
    <h2>Resize with reduced motion, and the word stays cut</h2></div>
  <div class="step">
    <p class="cap">The pill keeps the width it measured at the old viewport, so
    <code>overflow:hidden</code> cuts the word — <b>${clipped} px, ${Math.round( 100 * clipped / needW )}% of “consumers”</b> — and under
    <code>prefers-reduced-motion</code> nothing ever re-measures, so it never recovers. Rotating a
    phone is the everyday trigger.</p>
    <div data-panel="fixB"></div>
    <details class="why" data-note><summary>why / the code</summary><div class="inner">
      <p>Width is measured in an effect keyed on the word index alone — there is no resize listener.
      The font is <code>clamp(36px,4.3vw,60px)</code>, so every word's width is a function of
      viewport width. On a normal load a stale width self-heals at the next 2400ms tick; under
      reduced motion the interval never starts, so the stale value is final. Reproduced here
      deterministically: the <strong>${staleW} px</strong> width measured at 390 written onto a
      1280-wide frame, where the word needs <strong>${needW} px</strong>.</p>
      <pre><code>useEffect( () =&gt; {
  const measure = () =&gt; {
    const el = wordRefs.current[ cycleIndex ];
    if ( el ) setCycleW( el.offsetWidth );
  };
  measure();
  // A ResizeObserver on the pill rather than a window.resize listener: it also
  // catches a webfont swap and any container change, which a viewport listener
  // misses entirely - and a font swap is exactly what moves these numbers.
  const ro = new ResizeObserver( measure );
  if ( markRef.current ) ro.observe( markRef.current );
  return () =&gt; ro.disconnect();
}, [ cycleIndex ] );</code></pre>
    </div></details>
  </div>
</section>

<!-- ===================== FIX C ===================== -->
<section class="band">
  <div class="bhead"><span class="tag">C</span><span class="sev s-m">MED</span>
    <h2>Reduced motion can leave a white pill</h2></div>
  <div class="step">
    <p class="cap">The reduced-motion rule parks the entrance shutter <b>covering</b> the tint
    instead of clear of it. It does not bite today — but only by an accident of specificity, so any
    edit to the neighbouring rule exposes it. Shown here with that accident removed.</p>
    <div data-panel="fixC"></div>
    <details class="why" data-note><summary>why / the code</summary><div class="inner">
      <p>The block sets the shutter to <code>scaleX(1)</code> — the <em>start</em> state, a white
      panel over the tint — under a comment saying it settles the pill into its resting state. The
      resting state is <code>scaleX(0)</code>, and the sibling rule for the dot is correct, which
      makes this a slip rather than a misunderstanding. It is currently overridden because
      <code>.home-layout.show .home-mark::before</code> scores <strong>(0,2,1)</strong> against this
      rule's <strong>(0,1,1)</strong>, and a media query adds no specificity.</p>
      <pre><code>@media(prefers-reduced-motion:reduce){
  .home-mark::before{transform:scaleX(0)}   /* was scaleX(1) */
}</code></pre>
      <p class="sm" style="margin-top:8px"><code>HomePage.test.tsx</code> asserts only that the media
      block exists, so it passes either way. Worth tightening to assert the value.</p>
    </div></details>
  </div>
</section>

<!-- ===================== PROOF ===================== -->
<section class="band">
  <div class="bhead"><span class="tag">PROOF</span><h2>Normal load — the design must not change</h2></div>
  <div class="step">
    <p class="cap">All three fixes applied, JavaScript running, motion allowed — how almost everyone
    sees the page. <b>These two must be indistinguishable.</b> Measured: pill 280px both, h1 ${d.h1.h} px
    both at 1280 and ${m.h1.h} px both at 390.</p>
    <div data-panel="proof"></div>
    <details class="why" data-note><summary>what this protects</summary><div class="inner">
      <p>The h1 height is what <code>animcheck.js</code> pins across 21 viewports and a live
      rotation — it is the 2400ms page-jump guard. Unchanged, so that gate still holds. The gate
      <code>homeprobe.js</code> goes from <strong>5/12</strong> to <strong>9/12</strong>; the three
      still red are the closing band's invisible tab stop and the two calls below.</p>
    </div></details>
  </div>
</section>

<!-- ===================== REST ===================== -->
<section class="band">
  <div class="bhead"><span class="tag">REST</span><h2>Nothing to look at, and two calls for you</h2></div>
  <div class="step">
    <details class="why" data-note><summary>three with no visual change — same commit</summary><div class="inner">
      <ul style="margin-top:0">
        <li><strong><code>will-change:width</code> is permanent</strong> on <code>.home-cycle</code>.
        It should be set shortly before a transition and released after; left on it holds compositing
        resources for the life of the page, and under reduced motion there is no transition to hint
        at. <span class="mut">Not applied in the panels — a performance judgement, so listed rather
        than assumed.</span></li>
        <li><strong><code>max-width:${d.h1.max}</code> on the h1 never binds.</strong>
        <code>.home-hero</code> is <code>align-items:flex-start</code>, so the h1 shrink-wraps to
        ${d.h1.w} px at 1280. A dead declaration that reads like a live constraint.</li>
        <li><strong>The h1's raw text repeats the word set five times</strong>, with no space after
        “for”. Screen readers are correct — the animated copies carry <code>aria-hidden</code> and
        the sr-only span supplies one clean list — but a naive extractor reads:
        <div class="readout">${esc( d.h1.text )}</div></li>
      </ul>
      <p>The band's comments also contradict the band in nine places, two measurable: the header says
      <code>climate tech</code> is 290px and lists a fifth word with an 83px spread, where
      <code>animcheck</code> measures <strong>298px</strong> across four words with a
      <strong>22px</strong> spread. Full list in <code>docs/home-design-audit-20260926.md</code>.</p>
    </div></details>
    <details class="why" data-note><summary>two judgements — deliberately not mocked</summary><div class="inner">
      <ol style="margin-top:0">
        <li><strong>The rotation runs ${( WORDS.length * 2.4 ).toFixed( 1 )}s and cannot be paused.</strong> WCAG 2.2.2 applies to
        content moving automatically for over five seconds. Pausing on hover and focus covers pointer
        and keyboard and adds no furniture; a strict reading wants a user-operable control, which
        <em>is</em> furniture in a band meant to carry none.</li>
        <li><strong>${d.blank} px of blank above the first word</strong> — padding tuned around the lime
        brand badge that used to sit here and has been deleted. Purely cosmetic.</li>
      </ol>
      <p class="sm mut">Say the word on either and I will mock it the same way.</p>
    </div></details>
    <p class="sm mut" style="margin-top:12px">Deferred until this band is signed off: the other three
    bands, the sitewide schema problems, and propagating this band to the remaining public pages.</p>
  </div>
</section>

<footer class="pg">
  Re-generate: <code>node tools/browser/homereview.js</code> ·
  Gate: <code>node tools/browser/homeprobe.js</code> ·
  Findings: <code>docs/home-design-audit-20260926.md</code><br>
  Fonts load from Google; everything else here is self-contained. No images.
</footer>
</div>

<script>
const CSS   = ${J( harvest.inline + '\n' + harvest.chunks )};
const FIX   = ${J( scope( FIX_CSS ) )};
const RED_B = ${J( scope( REDUCED_BEFORE ) )};
const RED_A = ${J( scope( REDUCED_AFTER ) )};
const HEADER= ${J( harvest.header )};
const H1    = ${J( harvest.h1 )};
const SUB   = ${J( harvest.sub )};
const HEROC = ${J( harvest.heroCls )};
const LAYC  = ${J( harvest.layoutCls )};
const SHELLC= ${J( harvest.shellCls )};
const WORDS = ${J( WORDS )};
const STALE = ${staleW};

// The rotation on index.tsx's own constants - 2400ms, an inline px width on .home-cycle, the
// .on class moving between the words. Reimplemented rather than taken from the bundle,
// because a static preview panel has no React to hydrate.
function boot( o ){
  return '(function(){var w=' + JSON.stringify(WORDS) + ';var i=0;'
    + 'var c=document.querySelector(".home-cycle"),m=document.querySelector(".home-mark"),'
    + 'd=document.querySelector(".home-mark-dot"),it=document.querySelectorAll(".home-cyc-word");'
    + 'if(!it.length)return;'
    + 'function p(){for(var k=0;k<it.length;k++)it[k].classList.toggle("on",k===i);'
    + (o.stale ? 'if(c)c.style.width=' + STALE + '+"px";'
               : 'if(c&&it[i])c.style.width=it[i].offsetWidth+"px";')
    + 'if(m)m.style.background=w[i].tint;if(d)d.style.background=w[i].dot;}'
    + 'p();'
    + (o.noShow ? '' : 'var L=document.querySelector(".home-layout");if(L)L.classList.add("show");')
    + (o.rotate && !o.stale ? 'setInterval(function(){i=(i+1)%w.length;p();},2400);' : '')
    + '})();';
}

function frameDoc( body, o ){
  var extra = (o.fix ? FIX : '')
    + (o.reduced === 'before' ? RED_B : '') + (o.reduced === 'after' ? RED_A : '');
  var script = o.noJs ? '' : '<scr' + 'ipt>' + boot(o) + '</scr' + 'ipt>';
  return '<!doctype html><meta charset="utf-8">'
    + '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
    + '<style>html,body{margin:0}' + CSS + extra + '</style>'
    + HEADER
    + '<main class="' + SHELLC + '"><div class="' + LAYC.replace(/\\bshow\\b/,'').trim() + '">'
    + body + '</div></main>'
    + script;
}

function hero(){ return '<div class="' + HEROC + '">' + H1 + SUB + '</div>'; }

var W = { d:{label:'desktop 1280', w:1280, scale:0.56}, m:{label:'phone 390', w:390, scale:0.82} };

function shot( o, size, h ){
  var s = W[size], vw = Math.round(s.w*s.scale), vh = Math.round(h*s.scale);
  return '<div class="shot" style="width:'+vw+'px;height:'+vh+'px">'
    + '<iframe scrolling="no" title="preview" style="width:'+s.w+'px;height:'+h+'px;transform:scale('+s.scale+')" '
    + 'srcdoc="' + frameDoc(hero(), o).replace(/"/g,'&quot;') + '"></iframe></div>';
}

// One labelled column.
function col( lab, cls, o, size, h ){
  return '<div class="cmpcol"><span class="collab '+cls+'">'+lab+'</span>' + shot(o,size,h) + '</div>';
}
// Before and after, side by side, at both widths. Desktop row then phone row.
function compare( ob, oa, labB, labA, hd, hm ){
  return '<div class="cmp">' + col(labB,'c-b',ob,'d',hd) + col(labA,'c-a',oa,'d',hd) + '</div>'
       + '<div class="cmp">' + col(labB,'c-b',ob,'m',hm) + col(labA,'c-a',oa,'m',hm) + '</div>';
}
// A single state, at both widths.
function single( o, hd, hm ){
  return '<div class="cmp">' + col('desktop 1280','c-a',o,'d',hd)
       + col('phone 390','c-a',o,'m',hm) + '</div>';
}

function build(){
  var rot = document.getElementById('tRotate').checked;

  document.querySelector('[data-panel="orig"]').innerHTML = single({ rotate:rot }, 560, 660);

  document.querySelector('[data-panel="fixA"]').innerHTML =
    compare({ noJs:true }, { noJs:true, fix:true }, 'before — no word', 'after — word present', 430, 520);

  document.querySelector('[data-panel="fixB"]').innerHTML =
    compare({ rotate:false, stale:true }, { rotate:false, fix:true },
            'before — cut off', 'after — full word', 430, 520);

  document.querySelector('[data-panel="fixC"]').innerHTML =
    compare({ rotate:false, reduced:'before', noShow:true }, { rotate:false, reduced:'after', fix:true, noShow:true },
            'before — white pill', 'after — tint visible', 430, 520);

  document.querySelector('[data-panel="proof"]').innerHTML =
    compare({ rotate:rot }, { rotate:rot, fix:true }, 'before — today', 'after — fixed', 560, 660);
}

document.getElementById('tRotate').addEventListener('change', build);
document.getElementById('tNotes').addEventListener('change', function(e){
  document.querySelectorAll('details[data-note]').forEach(function(d){ d.open = e.target.checked; });
});
build();
</script>
`;

    fs.mkdirSync( path.dirname( OUT_FILE ), { recursive: true } );
    fs.writeFileSync( OUT_FILE, html );
    console.log( `wrote ${path.relative( REPO, OUT_FILE )}  (${( fs.statSync( OUT_FILE ).size / 1024 ).toFixed( 0 )} KB)` );
    console.log( `  scope: top band only, fixes A + B + C` );
    console.log( `  h1 ${d.h1.h}px @1280 / ${m.h1.h}px @390 · actions in band: ${d.actions}` );
    console.log( `  stale-width demo: ${staleW}px onto a frame needing ${needW}px (${clipped}px clipped)` );
    console.log( `  deferred: other bands, sitewide schema, propagation` );
  } finally {
    await browser.close();
    if ( t.close ) await t.close();
  }
} )().catch( e => { console.error( e ); process.exit( 1 ); } );
