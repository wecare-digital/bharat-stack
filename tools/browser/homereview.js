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
// The header's mega-menu is sized max-height:calc(100vh - 320px) with the mobile override
// gated on max-width:767px - so any window WIDER than 767 but short falls back to the desktop
// rule. Measured at 844x390, a landscape phone: a 70px-tall menu holding 700px of content.
// HDRJSX is replaced with the HEADER's own styled-jsx hash, which is a different hash from
// the home page's.
const HEADER_FIX_CSS = `
  /* Anchor to the header instead of a magic 320, and use dvh so mobile browser chrome is
     accounted for - the same unit fix index.tsx already made for .home-shell. 140 = the
     108px header plus 32px of air, both nameable. */
  .nav-menuHDRJSX{max-height:calc(100dvh - 140px)}
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
    // The header is a separate component, so styled-jsx gives it its own scoping class.
    const hdrHash = ( /class="([^"]*\bjsx-[a-z0-9]+)\b/.exec( harvest.header ) || [] )[ 1 ]
      ?.split( /\s+/ ).find( c => c.startsWith( 'jsx-' ) );
    if ( !hdrHash ) throw new Error( 'could not read the styled-jsx scoping class from the harvested header' );
    const scopeHdr = css => css.replace( /HDRJSX/g, `.${hdrHash}` );

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
<p class="cap" style="font-size:16px">The original as it ships today, then the same band with
the three fixes — both at <b>actual size</b>, 1280 and 390, nothing scaled down. <b>They are
meant to look identical:</b> the fixes only repair states you cannot see in a normal screenshot.</p>

<div class="bar"><div class="in">
  <label><input type="checkbox" id="tRotate" checked> run the rotation</label>
  <label><input type="checkbox" id="tNotes"> show written notes</label>
  <span class="mut sm">no CTA, no price — this band says what the page is about · source unchanged</span>
</div></div>

<!-- ============== ORIGINAL, 1:1 ============== -->
<section class="band">
  <div class="bhead"><span class="tag" style="background:#44546a;color:#fff">ORIGINAL</span>
    <h2>As it ships today — desktop 1280, actual size</h2>
    <span class="sel">unmodified: no fixes applied</span></div>
  <div class="step"><div data-panel="origD"></div></div>
</section>

<section class="band">
  <div class="bhead"><span class="tag" style="background:#44546a;color:#fff">ORIGINAL</span>
    <h2>As it ships today — phone 390, actual size</h2>
    <span class="sel">unmodified: no fixes applied</span></div>
  <div class="step"><div data-panel="origM"></div></div>
</section>

<!-- ============== WITH THE FIXES, 1:1 ============== -->
<section class="band">
  <div class="bhead"><span class="tag">FIXED</span><h2>With the three fixes — desktop 1280, actual size</h2></div>
  <div class="step"><div data-panel="finalD"></div></div>
</section>

<section class="band">
  <div class="bhead"><span class="tag">FIXED</span><h2>With the three fixes — phone 390, actual size</h2></div>
  <div class="step"><div data-panel="finalM"></div></div>
</section>

<!-- ============== HEADER / MENU ============== -->
<section class="band">
  <div class="bhead"><span class="tag" style="background:#44546a;color:#fff">ORIGINAL</span>
    <h2>Header menu open — desktop 1280, actual size</h2>
    <span class="sel">shared chrome, every public page · unmodified</span></div>
  <div class="step">
    <p class="cap">This is fine. The header's keyboard and screen-reader wiring is already
    correct — <code>aria-expanded</code> on the trigger, Escape closes from anywhere, an outside
    click dismisses, focus returns to the trigger, and the closed menu is
    <code>visibility:hidden</code> so its 20 links are not in the tab order.</p>
    <div data-panel="hdrOpenD"></div>
  </div>
</section>

<section class="band">
  <div class="bhead"><span class="tag">HEADER FIX</span><span class="sev s-m">MED</span>
    <h2>Landscape phone — the menu collapses to a sliver</h2></div>
  <div class="step">
    <p class="cap"><b>At 844×390 the menu is 70 px tall and holds 700 px of content — 10.6x
    its own height.</b> Twenty links in a sliver. Both panels are 1:1 at 844×390.</p>
    <div data-panel="hdrLand"></div>
    <details class="why" data-note><summary>why / the code</summary><div class="inner">
      <p>The menu is <code>max-height:calc(100vh - 320px)</code>, and the mobile override that
      repositions it is gated on <code>@media(max-width:767px)</code>. So any window
      <em>wider</em> than 767 but short falls back to the desktop rule — a landscape phone, or a
      short desktop window. Measured across nine viewports:</p>
      <table>
        <tr><th>Viewport</th><th class="n">menu</th><th class="n">content</th><th>verdict</th></tr>
        <tr><td>390×844 portrait</td><td class="n">358×536</td><td class="n">1028px</td><td>scrolls, usable</td></tr>
        <tr><td>1280×900 desktop</td><td class="n">760×403</td><td class="n">399px</td><td>fits</td></tr>
        <tr><td><strong>844×390 landscape</strong></td><td class="n"><strong>588×70</strong></td><td class="n"><strong>700 px</strong></td><td><strong>unusable</strong></td></tr>
      </table>
      <p style="margin-top:10px">Also <code>100vh</code>, not <code>100dvh</code> — the exact unit
      defect <code>index.tsx</code> already fixed for <code>.home-shell</code>, still present in the
      shared chrome. And 320 corresponds to nothing nameable, which is the same magic-number family
      as the 108/96 header heights.</p>
      <pre><code>/* anchor to the header, and use dvh: 140 = the 108px header + 32px of air */
.nav-menu{max-height:calc(100dvh - 140px)}</code></pre>
    </div></details>
  </div>
</section>

<!-- ============== WHAT CHANGED ============== -->
<section class="band">
  <div class="bhead"><span class="tag">CHANGES</span><h2>Three repairs — one line each</h2></div>

  <div class="step">
    <p class="cap"><span class="sev s-h">A</span> &nbsp;<b>The word is missing entirely without
    JavaScript, and for ~200ms on every single load.</b></p>
    <div data-panel="fixA"></div>
    <details class="why" data-note><summary>why / the code</summary><div class="inner">
      <p><code>cycleW</code> starts <code>null</code>, so the first render writes no inline width.
      <code>.home-cycle</code> is <code>overflow:hidden</code> and all four words are
      <code>position:absolute</code>, so they add nothing to its intrinsic width — it computes to
      <strong>0px</strong> and clips the word away. Measured on a normal load, JS working, local
      server, no network: <strong>4 painted frames, ~200ms</strong>.</p>
      <pre><code>.home-cycle{width:max-content}   /* resting width, needs no JS */
.home-cyc-word.on{
  position:static;      /* the visible word sits in flow, so the pill has a width */
  display:inline-block; /* NOT optional - see below */
}</code></pre>
      <p class="sm" style="margin-top:10px"><strong><code>display:inline-block</code> is
      load-bearing, and measuring this mock is what caught it.</strong> <code>position:static</code>
      alone makes the span a non-replaced <em>inline</em> box, whose <code>offsetWidth</code> is 0 —
      so the existing effect would write <code>width:0px</code> over <code>max-content</code> and the
      pill would collapse on every load <em>with</em> JavaScript, turning a 200ms flash into a
      permanent one.</p>
    </div></details>
  </div>

  <div class="step">
    <p class="cap"><span class="sev s-h">B</span> &nbsp;<b>Resize with reduced motion on and the word
    stays cut — ${clipped} px, ${Math.round( 100 * clipped / needW )}% of it — for good.</b></p>
    <div data-panel="fixB"></div>
    <details class="why" data-note><summary>why / the code</summary><div class="inner">
      <p>Width is measured in an effect keyed on the word index alone; there is no resize listener.
      The font is <code>clamp(36px,4.3vw,60px)</code>, so width is a function of viewport width. On a
      normal load a stale value self-heals at the next 2400ms tick; under reduced motion the interval
      never starts, so it is final. Reproduced here by writing the <strong>${staleW} px</strong> width
      measured at 390 onto a 1280 frame, where the word needs <strong>${needW} px</strong>.</p>
      <pre><code>const ro = new ResizeObserver( measure );   // not window.resize: this also
if ( markRef.current ) ro.observe( markRef.current );  // catches a webfont swap
return () =&gt; ro.disconnect();</code></pre>
    </div></details>
  </div>

  <div class="step">
    <p class="cap"><span class="sev s-m">C</span> &nbsp;<b>Reduced motion can park a white shutter
    over the tint — latent today, one edit away from live.</b></p>
    <div data-panel="fixC"></div>
    <details class="why" data-note><summary>why / the code</summary><div class="inner">
      <p>The reduced-motion block sets the shutter to <code>scaleX(1)</code> — the <em>start</em>
      state — under a comment saying it settles the pill into its resting state, which is
      <code>scaleX(0)</code>. The dot's sibling rule is correct, so it is a slip. It is overridden
      today only because <code>.home-layout.show .home-mark::before</code> scores
      <strong>(0,2,1)</strong> against this rule's <strong>(0,1,1)</strong>.</p>
      <pre><code>@media(prefers-reduced-motion:reduce){
  .home-mark::before{transform:scaleX(0)}   /* was scaleX(1) */
}</code></pre>
    </div></details>
  </div>
</section>

<!-- ============== PROOF ============== -->
<section class="band">
  <div class="bhead"><span class="tag">PROOF</span><h2>Nothing visible changed</h2></div>
  <div class="step">
    <p class="cap">Normal load, side by side. Measured: pill 280px both, h1 ${d.h1.h} px both at 1280 and
    ${m.h1.h} px both at 390 — so the reflow pin and the 2400ms page-jump guard still hold.</p>
    <div data-panel="proof"></div>
  </div>
</section>

<!-- ============== REST ============== -->
<section class="band">
  <div class="bhead"><span class="tag">REST</span><h2>Housekeeping, and two calls for you</h2></div>
  <div class="step">
    <p class="cap"><b>No visual change, same commit:</b> permanent <code>will-change:width</code>;
    a <code>max-width:${d.h1.max}</code> on the h1 that never binds; the h1's raw text repeating the word
    set five times; nine stale comments.</p>
    <p class="cap"><b>Your call, not mocked:</b> the ${( WORDS.length * 2.4 ).toFixed( 1 )}s rotation that cannot be paused, and
    ${d.blank} px of blank above the first word.</p>
    <details class="why" data-note><summary>detail</summary><div class="inner">
      <ul style="margin-top:0">
        <li><code>will-change:width</code> should be set shortly before a transition and released
        after; left on it holds compositing resources for the page's life, and under reduced motion
        there is no transition to hint at. Not applied in the panels — a performance judgement.</li>
        <li><code>max-width:${d.h1.max}</code> never binds: <code>.home-hero</code> is
        <code>align-items:flex-start</code>, so the h1 shrink-wraps to ${d.h1.w} px at 1280.</li>
        <li>The h1's raw text — screen readers are correct, but a naive extractor reads:
        <div class="readout">${esc( d.h1.text )}</div></li>
        <li>Comments contradict the band in nine places, two measurable: the header says
        <code>climate tech</code> is 290px with an 83px spread across five words;
        <code>animcheck</code> measures <strong>298px</strong> and <strong>22px</strong> across four.</li>
        <li>Rotation: WCAG 2.2.2 covers content moving automatically past five seconds. Hover+focus
        pausing adds no furniture; a strict reading wants a user-operable control, which is furniture
        in a band meant to carry none.</li>
        <li>The ${d.blank} px was tuned around the deleted lime brand badge. Purely cosmetic.</li>
      </ul>
      <p class="sm mut">Deferred until this band is signed off: the other three bands, the sitewide
      schema problems, and propagating this band to the remaining public pages.</p>
    </div></details>
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
const HFIX  = ${J( scopeHdr( HEADER_FIX_CSS ) )};
const HEADER= ${J( harvest.header )};
const H1    = ${J( harvest.h1 )};
const SUB   = ${J( harvest.sub )};
const HEROC = ${J( harvest.heroCls )};
const LAYC  = ${J( harvest.layoutCls )};
const SHELLC= ${J( harvest.shellCls )};
const WORDS = ${J( WORDS )};
const STALE = ${staleW};

// The rotation on index.tsx's own constants - 2400ms, an inline px width on .home-cycle via
// offsetWidth (the same property the real effect reads), the .on class moving between words.
// Reimplemented rather than taken from the bundle: a static panel has no React to hydrate.
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
    + (o.menuOpen ? 'var nm=document.querySelector(".nav-menu");if(nm)nm.classList.add("open");'
        + 'var tg=document.querySelector(".nav-trigger");if(tg)tg.setAttribute("aria-expanded","true");' : '')
    + '})();';
}

function frameDoc( o ){
  var extra = (o.fix ? FIX : '') + (o.hfix ? HFIX : '')
    + (o.reduced === 'before' ? RED_B : '') + (o.reduced === 'after' ? RED_A : '');
  var script = o.noJs ? '' : '<scr' + 'ipt>' + boot(o) + '</scr' + 'ipt>';
  return '<!doctype html><meta charset="utf-8">'
    + '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
    + '<style>html,body{margin:0}' + CSS + extra + '</style>'
    + HEADER
    + '<main class="' + SHELLC + '"><div class="' + LAYC.replace(/\\bshow\\b/,'').trim() + '">'
    + '<div class="' + HEROC + '">' + H1 + SUB + '</div>'
    + '</div></main>'
    + script;
}

// scale 1 = actual size. Anything smaller is only used for the small comparison strips.
function shot( o, w, h, scale ){
  var vw = Math.round(w*scale), vh = Math.round(h*scale);
  return '<div class="shot" style="width:'+vw+'px;height:'+vh+'px">'
    + '<iframe scrolling="no" title="preview" style="width:'+w+'px;height:'+h+'px;transform:scale('+scale+')" '
    + 'srcdoc="' + frameDoc(o).replace(/"/g,'&quot;') + '"></iframe></div>';
}
function labelled( lab, cls, o, w, h, scale ){
  return '<div class="cmpcol"><span class="collab '+cls+'">'+lab+'</span>' + shot(o,w,h,scale) + '</div>';
}

function build(){
  var rot = document.getElementById('tRotate').checked;

  // The original, actual size, nothing applied.
  document.querySelector('[data-panel="origD"]').innerHTML =
    shot({ rotate:rot }, 1280, 470, 1);
  document.querySelector('[data-panel="origM"]').innerHTML =
    shot({ rotate:rot }, 390, 420, 1);

  // The same band with the three fixes, actual size.
  document.querySelector('[data-panel="finalD"]').innerHTML =
    shot({ rotate:rot, fix:true }, 1280, 470, 1);   // 470 = the band's real extent (hero ends at 399) plus air
  document.querySelector('[data-panel="finalM"]').innerHTML =
    shot({ rotate:rot, fix:true }, 390, 420, 1);    // hero ends at 342 on a phone

  // Header: the menu open, at actual size.
  document.querySelector('[data-panel="hdrOpenD"]').innerHTML =
    // 900, a real viewport height, NOT a crop: the iframe's height IS 100vh inside it, and
    // the menu is sized max-height:calc(100vh - 320px). A 640px panel would have shown a
    // 320px menu where the live page shows 580px - the panel would misreport the design.
    shot({ rotate:false, menuOpen:true }, 1280, 900, 1);
  // The landscape-phone failure, before and after, both 1:1 at 844x390.
  document.querySelector('[data-panel="hdrLand"]').innerHTML = '<div class="cmp">'
    + labelled('before — 70px of menu','c-b',{ rotate:false, menuOpen:true }, 844, 390, 1)
    + labelled('after — anchored to the header','c-a',{ rotate:false, menuOpen:true, hfix:true }, 844, 390, 1)
    + '</div>';

  // Small comparison strips - desktop only, enough to read the pill.
  var SW = 1280, SH = 340, SC = 0.55;
  document.querySelector('[data-panel="fixA"]').innerHTML = '<div class="cmp">'
    + labelled('before — no word','c-b',{ noJs:true }, SW,SH,SC)
    + labelled('after','c-a',{ noJs:true, fix:true }, SW,SH,SC) + '</div>';

  document.querySelector('[data-panel="fixB"]').innerHTML = '<div class="cmp">'
    + labelled('before — cut off','c-b',{ rotate:false, stale:true }, SW,SH,SC)
    + labelled('after','c-a',{ rotate:false, fix:true }, SW,SH,SC) + '</div>';

  document.querySelector('[data-panel="fixC"]').innerHTML = '<div class="cmp">'
    + labelled('before — white pill','c-b',{ rotate:false, reduced:'before', noShow:true }, SW,SH,SC)
    + labelled('after','c-a',{ rotate:false, reduced:'after', fix:true, noShow:true }, SW,SH,SC) + '</div>';

  document.querySelector('[data-panel="proof"]').innerHTML = '<div class="cmp">'
    + labelled('today','c-b',{ rotate:rot }, SW,SH,SC)
    + labelled('with the fixes','c-a',{ rotate:rot, fix:true }, SW,SH,SC) + '</div>';
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
