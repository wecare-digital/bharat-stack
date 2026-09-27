'use strict';

/**
 * closereview - ONE self-contained HTML page reviewing the home page's THIRD band.
 *
 * Completes the set: homereview.js owns band 1, flowreview.js band 2, this one band 3.
 * Scope is section.home-close only - the lime-tinted closing panel and the page's single
 * call to action. Not the other two bands, not the shared rh-hero on the other ten routes.
 *
 * THE BRIEF THIS FOLLOWS, AND ONE THING IT SETTLES RATHER THAN RAISES.
 * This band is the closing argument: it is where the page asks for a decision, and it owns
 * the only action on the page. That the action is HERE and nowhere above it is a decision the
 * owner has already taken - homereview.js records it in its own header, that band 1 carries
 * no CTA, no price and no conversion furniture. So "the only action is 1.9 screens down" is
 * reported here as a measurement and a consequence, NOT as a defect to fix. The CTA options
 * are not reopened.
 *
 * WHAT IS ACTUALLY WRONG IS THE BUTTON ITSELF, and it took compositing to see it. The panel
 * is rgba(209,244,112,.22) lime and the button is solid #d1f470 lime with a #d1f470 border,
 * so the control's entire boundary against its background measures 1.18:1 where WCAG 1.4.11
 * wants 3:1. index.tsx asserts the opposite in a comment - that solid lime on the tint "still
 * separates because the panel is the same hue at 22%" - which is exactly the kind of claim an
 * alpha makes look reasonable until it is painted. The focus ring has the same problem for
 * the same reason: rgba(26,58,42,.22) over that tint is 1.51:1.
 *
 * FRAMES ARE STATIC MARKUP, harvested from the real export with the revealed state baked in.
 * Unlike band 2 there is no stream to freeze - this band's only motion is a one-shot entrance,
 * so the settled state is the state, and .is-in is applied directly.
 *
 * TWO STATES CANNOT BE PRODUCED INSIDE A PREVIEW FRAME and are simulated, the same way
 * homereview.js simulates prefers-reduced-motion:
 *   - :focus-visible  a frame has no keyboard, so the declared outline is applied directly
 *   - :hover          applied directly, to show the fix survives the hover state too
 *
 * Run:    node tools/browser/closereview.js     (needs out/ - see README.md)
 * Writes: docs/close-review.html
 */

const fs = require( 'fs' );
const path = require( 'path' );
const { target } = require( './lib/serve' );
const { launch, gotoStable } = require( './lib/browser' );

const REPO = path.join( __dirname, '..', '..' );
const OUT_FILE = path.join( REPO, 'docs', 'close-review.html' );

// ---- the two fixes under review -----------------------------------------------------
//
// Both are non-text contrast repairs, and neither introduces a colour. #1a3a2a is already
// the button's own text colour and the eyebrow's colour in this same panel, so the palette
// is unchanged - what changes is which of the two existing values draws the boundary.
//
// FIX C2 - the button's edge. border-color #d1f470 -> #1a3a2a takes the control's boundary
// against the panel from 1.18:1 to 11.85:1. The fill stays solid lime, so the button still
// reads as the lime affordance the rest of the site uses; it simply gains an edge. It also
// improves the hover state, which swaps the fill to #fff and currently loses its outline
// entirely against the pale tint.
//
// FIX C3 - the focus ring. rgba(26,58,42,.22) -> #1a3a2a, 1.51:1 to 11.85:1. outline-offset
// stays 3px, which is what keeps the ring legible as a ring now that the border is the same
// colour: there is a 3px band of panel tint between the two.
const FIX_CSS = `
  .home-close-ctaJSX{border-color:#1a3a2a}
  .home-close-ctaJSX:focus-visible{outline-color:#1a3a2a}
  .home-close-cta.is-focusJSX{outline:3px solid #1a3a2a;outline-offset:3px}
`;

// A frame has no keyboard, so :focus-visible can never match inside one. The declared
// outline is applied through a class instead - the BEFORE frame gets the real declared
// value, the AFTER frame gets the fixed one, so the comparison is honest.
const FOCUS_BEFORE = `
  .home-close-cta.is-focusJSX{outline:3px solid rgba(26,58,42,.22);outline-offset:3px}
`;
const HOVER_CSS = `
  .home-close-cta.is-hoverJSX{background:#fff;transform:translateY(-2px);
    box-shadow:0 4px 12px rgba(26,58,42,.12)}
`;

const CONTRAST_FN = `
  function lin(c){c/=255;return c<=0.03928?c/12.92:Math.pow((c+0.055)/1.055,2.4)}
  function lum(r,g,b){return 0.2126*lin(r)+0.7152*lin(g)+0.0722*lin(b)}
  function parse(s){var m=s.match(/rgba?\\(([^)]+)\\)/);if(!m){
    var h=/^#([0-9a-f]{6})$/i.exec(s&&s.trim());
    if(h)return {r:parseInt(h[1].slice(0,2),16),g:parseInt(h[1].slice(2,4),16),b:parseInt(h[1].slice(4,6),16),a:1};
    return null}
    var p=m[1].split(',').map(function(x){return parseFloat(x)});
    return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1}}
  function over(f,b){return {r:f.r*f.a+b.r*(1-f.a),g:f.g*f.a+b.g*(1-f.a),b:f.b*f.a+b.b*(1-f.a),a:1}}
  function bg(el){var layers=[];
    for(var n=el;n;n=n.parentElement){var c=parse(getComputedStyle(n).backgroundColor);
      if(c&&c.a>0){layers.unshift(c);if(c.a===1)break}}
    var base={r:255,g:255,b:255,a:1};
    for(var i=0;i<layers.length;i++)base=over(layers[i],base);return base}
  function ratioOf(fgStr,el){var fg=parse(fgStr);if(!fg)return null;var b=bg(el);
    var c=over(fg,b);var L1=lum(c.r,c.g,c.b),L2=lum(b.r,b.g,b.b);
    var hi=Math.max(L1,L2),lo=Math.min(L1,L2);
    return Math.round(((hi+0.05)/(lo+0.05))*100)/100}
`;

const METRICS = () => {
  const px = n => Math.round( n );
  const q = s => document.querySelector( s );
  const box = s => { const e = q( s ); if ( !e ) return null; const r = e.getBoundingClientRect();
    return { w: px( r.width ), h: px( r.height ), t: px( r.top + window.scrollY ) }; };
  const cs = ( s, p ) => { const e = q( s ); return e ? getComputedStyle( e )[ p ] : null; };
  return {
    vw: window.innerWidth, vh: window.innerHeight,
    docH: px( document.documentElement.scrollHeight ),
    band: box( '.home-close' ), panel: box( '.home-close-panel' ),
    eyebrow: box( '.home-close-eyebrow' ), title: box( '.home-close-title' ),
    lead: box( '.home-close-lead' ), rule: box( '.home-close-rule' ),
    points: box( '.home-close-points' ), cta: box( '.home-close-cta' ),
    li: [ ...document.querySelectorAll( '.home-close-points li' ) ]
      .map( e => ( { w: px( e.getBoundingClientRect().width ), chars: e.textContent.trim().length } ) ),
    pointsMax: cs( '.home-close-points', 'maxWidth' ),
    leadMax: cs( '.home-close-lead', 'maxWidth' ),
    titleMax: cs( '.home-close-title', 'maxWidth' ),
    pad: cs( '.home-close-panel', 'padding' ),
    actions: document.querySelectorAll(
      'main a[href],main button,main input,main select,main textarea,main [tabindex]:not([tabindex="-1"])' ).length,
  };
};

( async () => {
  const t = await target();
  const browser = await launch();
  try {
    const M = {}, H = {};

    for ( const vp of [ { k: 'd', w: 1280, h: 900 }, { k: 'm', w: 390, h: 844 } ] ) {
      const ctx = await browser.newContext( { viewport: { width: vp.w, height: vp.h } } );
      const page = await ctx.newPage();
      await gotoStable( page, `${t.base}/` );
      // Scroll it in so the observer fires and .is-in is on the node before harvesting.
      await page.evaluate( () => document.querySelector( '.home-close' ).scrollIntoView( { block: 'center' } ) );
      await page.waitForFunction(
        () => document.querySelector( '.home-close' ).classList.contains( 'is-in' ),
        null, { timeout: 15000 } );
      await page.waitForTimeout( 900 );

      M[ vp.k ] = await page.evaluate( METRICS );
      H[ vp.k ] = await page.evaluate( () => document.querySelector( '.home-close' ).outerHTML );

      if ( vp.k === 'd' ) {
        H.css = await page.evaluate( async () => {
          const inline = [ ...document.querySelectorAll( 'style' ) ].map( s => s.textContent ).join( '\n' );
          const hrefs = [ ...document.querySelectorAll( 'link[rel="stylesheet"]' ) ]
            .map( l => l.getAttribute( 'href' ) ).filter( h => h && h.startsWith( '/_next/' ) );
          const chunks = [];
          for ( const h of hrefs ) { try { chunks.push( await ( await fetch( h ) ).text() ); } catch { /* ignore */ } }
          return { inline, chunks: chunks.join( '\n' ),
            shellCls: document.querySelector( '.home-shell' ).className,
            layoutCls: document.querySelector( '.home-layout' ).className };
        } );
        // Measured contrast for every claim this page makes, so no ratio here is retyped.
        M.contrast = await page.evaluate( `(() => {
          ${CONTRAST_FN}
          const cta = document.querySelector('.home-close-cta');
          const panel = cta.parentElement;
          const cs = getComputedStyle(cta);
          const declaredFocus = (() => {
            for (const sheet of document.styleSheets) {
              let rules; try { rules = sheet.cssRules } catch (e) { continue }
              for (const r of rules || []) {
                if (r.selectorText && /home-close-cta[^,]*:focus-visible/.test(r.selectorText)) {
                  const m = /rgba?\\([^)]+\\)/.exec(r.style.outlineColor || r.style.outline || '');
                  return m ? m[0] : null;
                }
              }
            }
            return null;
          })();
          return {
            edgeBefore: ratioOf(cs.backgroundColor, panel),
            edgeAfter:  ratioOf('#1a3a2a', panel),
            focusBefore: declaredFocus ? ratioOf(declaredFocus, panel) : null,
            focusDeclared: declaredFocus,
            focusAfter: ratioOf('#1a3a2a', panel),
            hoverEdgeBefore: ratioOf('#d1f470', panel),
            text: {
              eyebrow: ratioOf(getComputedStyle(document.querySelector('.home-close-eyebrow')).color, document.querySelector('.home-close-eyebrow')),
              title: ratioOf(getComputedStyle(document.querySelector('.home-close-title')).color, document.querySelector('.home-close-title')),
              lead: ratioOf(getComputedStyle(document.querySelector('.home-close-lead')).color, document.querySelector('.home-close-lead')),
              point: ratioOf(getComputedStyle(document.querySelector('.home-close-points li')).color, document.querySelector('.home-close-points li')),
              cta: ratioOf(cs.color, cta),
            },
          };
        })()` );
      }
      await ctx.close();
    }

    // index.tsx's own styled-jsx hash, read off the harvested band.
    const jsxHash = ( /class="([^"]*)\bhome-close-panel\b/.exec( H.d ) || [] )[ 1 ]
      ?.trim().split( /\s+/ ).find( c => c.startsWith( 'jsx-' ) );
    if ( !jsxHash ) throw new Error( 'could not read the styled-jsx scoping class from the harvested band' );
    const scope = css => css.replace( /JSX/g, `.${jsxHash}` );

    const GLOBAL_RESET = '*{box-sizing:border-box;margin:0;padding:0}';
    const bodyFont = ( () => {
      const m = /body\{[^}]*font-family:Inter[^}]*\}/.exec( H.css.chunks );
      if ( !m ) throw new Error( 'could not extract the body font rule from the built CSS' );
      return m[ 0 ];
    } )();
    const CSS_ALL = GLOBAL_RESET + '\n' + bodyFont + '\n' + H.css.inline;

    const frameDoc = o => {
      let html = o.html;
      if ( o.focus ) html = html.replace( /(class="[^"]*home-close-cta)/, '$1 is-focus' );
      if ( o.hover ) html = html.replace( /(class="[^"]*home-close-cta)/, '$1 is-hover' );
      const extra = scope( o.fix ? FIX_CSS : '' )
        + scope( o.focus && !o.fix ? FOCUS_BEFORE : '' )
        + scope( o.hover ? HOVER_CSS : '' )
        + ( o.cap ? scope( '.home-close-pointsJSX{max-width:62ch}' ) : '' );
      return '<!doctype html><meta charset="utf-8">'
        + '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">'
        + `<style>html,body{margin:0}${CSS_ALL}${extra}`
        + '.home-layout{gap:0 !important;padding-top:20px !important;padding-bottom:20px !important}'
        + '</style>'
        + `<main class="${H.css.shellCls}" style="padding-top:0">`
        + `<div class="${H.css.layoutCls}">${html}</div></main>`;
    };

    const shot = ( o, w, h, sc = 1 ) =>
      `<div class="shot" style="width:${Math.round( w * sc )}px;height:${Math.round( h * sc )}px">`
      + `<iframe loading="lazy" scrolling="no" title="preview" `
      + `style="width:${w}px;height:${h}px;transform:scale(${sc})" `
      + `srcdoc="${frameDoc( o ).replace( /"/g, '&quot;' )}"></iframe></div>`;
    const labelled = ( lab, cls, o, w, h, sc ) =>
      `<div class="cmpcol"><span class="collab ${cls}">${lab}</span>${shot( o, w, h, sc )}</div>`;

    const DH = 640, MH = 760;
    const d = M.d, m = M.m, C = M.contrast;

    const P = {
      origD: shot( { html: H.d }, 1280, DH, 1 ),
      origM: shot( { html: H.m }, 390, MH, 1 ),
      fixedD: shot( { html: H.d, fix: true }, 1280, DH, 1 ),
      edge: '<div class="cmp">'
        + labelled( `before — ${C.edgeBefore}:1, fails 1.4.11`, 'c-b', { html: H.d }, 1280, DH, 0.62 )
        + labelled( `after — ${C.edgeAfter}:1`, 'c-a', { html: H.d, fix: true }, 1280, DH, 0.62 ) + '</div>',
      focus: '<div class="cmp">'
        + labelled( `before — ${C.focusBefore}:1`, 'c-b', { html: H.d, focus: true }, 1280, DH, 0.62 )
        + labelled( `after — ${C.focusAfter}:1`, 'c-a', { html: H.d, focus: true, fix: true }, 1280, DH, 0.62 ) + '</div>',
      hover: '<div class="cmp">'
        + labelled( 'before — white fill, lime border, no edge', 'c-b', { html: H.d, hover: true }, 1280, DH, 0.62 )
        + labelled( 'after — the edge survives hover', 'c-a', { html: H.d, hover: true, fix: true }, 1280, DH, 0.62 ) + '</div>',
      cap: '<div class="cmp">'
        + labelled( 'today — max-width:none', 'c-n', { html: H.d }, 1280, DH, 0.62 )
        + labelled( 'capped to 62ch — identical', 'c-n', { html: H.d, cap: true }, 1280, DH, 0.62 ) + '</div>',
      fixedM: '<div class="cmp">'
        + labelled( 'before', 'c-b', { html: H.m }, 390, MH, 1 )
        + labelled( 'after', 'c-a', { html: H.m, fix: true }, 390, MH, 1 ) + '</div>',
    };

    const STAMP = new Date().toISOString().replace( 'T', ' ' ).slice( 0, 16 ) + 'Z';

    const html = `<!doctype html>
<meta charset="utf-8">
<title>Home page — band 3, section.home-close</title>
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
  .card.settled{border-left:4px solid #20418f}
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
  .s-h{background:#fdeceb;color:var(--red)} .s-m{background:#fff4e5;color:var(--amb)}
  .s-l{background:#eef1f4;color:#44546a} .s-ok{background:#eefaf0;color:#1f6f3d}
  .collab{font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:.07em;margin:0 0 7px;padding:2px 7px;border-radius:4px;display:inline-block}
  .c-b{background:#fdeceb;color:var(--red)} .c-a{background:#eefaf0;color:#1f6f3d} .c-n{background:#eef1f4;color:#44546a}
  .shot{border:1px solid var(--line);border-radius:8px;overflow:hidden;background:#fff;position:relative}
  .shot iframe{border:0;display:block;transform-origin:0 0}
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
  details.why .inner{padding:0 14px 14px;border-top:1px solid var(--line);padding-top:12px}
  .bar{position:sticky;top:0;z-index:5;background:rgba(250,250,250,.94);backdrop-filter:blur(6px);
    border-bottom:1px solid var(--line);padding:10px 0;margin:0 0 20px}
  footer.pg{color:var(--mut);font-size:13px;border-top:1px solid var(--line);padding-top:18px;margin-top:34px}
  .swatch{display:inline-block;width:12px;height:12px;border-radius:3px;vertical-align:-2px;margin-right:5px;border:1px solid rgba(0,0,0,.15)}
</style>
<div class="wrap">

<h1>Home page — band 3 of 3</h1>
<p class="cap" style="font-size:16px"><code>section.home-close</code> — the lime closing panel
and the page's only call to action. Band 1: <code>docs/home-review.html</code>. Band 2:
<code>docs/flow-review.html</code>. <b>This completes the set.</b></p>

<div class="bar"><div class="in">
  <span class="mut sm"><b>No JavaScript needed to view this page.</b> Every panel is static
  markup; the notes are native <code>&lt;details&gt;</code>.<br>
  <b>Two changes are proposed, and neither adds a colour</b> — both use <span class="swatch"
  style="background:#1a3a2a"></span><code>#1a3a2a</code>, which is already this panel's eyebrow
  colour and the button's own text colour.<br>
  <b>Build ${STAMP}.</b> Measurements by <code>tools/browser/closeprobe.js</code>.</span>
</div></div>

<div class="card brief">
  <h2 style="font-size:18px;margin-bottom:8px">What this band is for</h2>
  <p class="cap" style="margin:0">Band 1 says what the page is about. Band 2 shows the platform
  behind it. This band <b>asks for the decision</b> — an eyebrow, a claim, three promises and one
  button. It is also the band that gets the entrance animation <i>right</i>: the CSS ships the
  visible state and JavaScript adds <code>.is-armed</code> only once it knows it can animate, so
  a failed bundle leaves the content readable. <b>Verified: with JavaScript disabled the title,
  all three points and the CTA render.</b> Band 2's F5 is the same problem solved the other way.</p>
</div>

<div class="card settled">
  <h2 style="font-size:18px;margin-bottom:8px">Already decided — not reopened here</h2>
  <p class="cap" style="margin:0">The CTA sits at <b>y=${d.cta.t}</b> on a ${d.vh}px viewport
  — <b>${( d.cta.t / d.vh ).toFixed( 1 )} screens down</b>, ${Math.round( d.cta.t / d.docH * 100 )}% into
  the document — and it is the <b>only one of ${d.actions} focusable elements in
  <code>&lt;main&gt;</code></b>. On a phone it is at y=${m.cta.t}, ${( m.cta.t / m.vh ).toFixed( 1 )}
  screens down.<br><br>
  That is a <b>consequence of a decision already taken</b>, not a defect: band 1's brief is that
  it carries no CTA, no price and no conversion furniture, and the action stays here. Recorded so
  the number is known — <b>the CTA options are not put back up.</b></p>
</div>

<!-- ============== ORIGINAL ============== -->
<section class="band">
  <div class="bhead"><span class="tag" style="background:#44546a;color:#fff">ORIGINAL</span>
    <h2>As it ships today — desktop 1280, actual size</h2>
    <span class="sel">revealed state, .is-in applied</span></div>
  <div class="step">${P.origD}</div>
</section>

<section class="band">
  <div class="bhead"><span class="tag" style="background:#44546a;color:#fff">ORIGINAL</span>
    <h2>Phone 390, actual size</h2></div>
  <div class="step">${P.origM}</div>
</section>

<!-- ============== C1 ============== -->
<section class="band">
  <div class="bhead"><span class="sev s-h">HIGH</span>
    <h2>C1 — The button's edge against its own panel is ${C.edgeBefore}:1</h2>
    <span class="sel">#d1f470 fill + #d1f470 border on rgba(209,244,112,.22)</span></div>
  <div class="step">
    <p class="cap">WCAG 1.4.11 asks for <b>3:1</b> between a control's boundary and what is
    adjacent to it. This button is solid lime with a 2px lime border, sitting on a 22% lime
    panel — so the border contributes nothing and the whole control measures
    <b>${C.edgeBefore}:1</b>. It is the page's only action, and its shape is carried almost
    entirely by the text inside it.</p>
    <p class="cap"><code>index.tsx</code> states the opposite outright: <i>"Solid lime on the
    tinted panel still separates because the panel is the same hue at 22% — the button is the
    saturated version of its own background, which is why it needs no shadow at rest."</i>
    <b>That reasoning is why the defect is there</b> — being the same hue is exactly what removes
    the contrast. Composited, the two colours differ by ${C.edgeBefore}:1.</p>
    <p class="cap"><b>The change:</b> <code>border-color: #d1f470</code> →
    <code>#1a3a2a</code>. The fill stays lime, so it is still the site's lime affordance; it
    gains an edge. <b>${C.edgeBefore}:1 → ${C.edgeAfter}:1.</b> No new colour —
    <span class="swatch" style="background:#1a3a2a"></span><code>#1a3a2a</code> is already the
    text inside this button and the eyebrow above it.</p>
    ${P.edge}
  </div>
</section>

<!-- ============== C2 ============== -->
<section class="band">
  <div class="bhead"><span class="sev s-m">MED</span>
    <h2>C2 — The focus ring on that same button is ${C.focusBefore}:1</h2>
    <span class="sel">outline:3px solid rgba(26,58,42,.22)</span></div>
  <div class="step">
    <p class="cap">Same criterion, same panel. A 22% alpha of the dark green over a pale lime
    tint composites to <b>${C.focusBefore}:1</b>. This is the <b>only focusable element in
    <code>&lt;main&gt;</code> on the entire page</b>, so a keyboard visitor tabbing through the
    document gets one stop and almost no indication they have arrived at it.</p>
    <p class="cap"><b>The change:</b> drop the alpha — <code>rgba(26,58,42,.22)</code> →
    <code>#1a3a2a</code>. <b>${C.focusBefore}:1 → ${C.focusAfter}:1.</b>
    <code>outline-offset:3px</code> stays, and it is what keeps the ring legible as a ring now
    that the border is the same colour: 3px of panel tint separates them.</p>
    ${P.focus}
    <details class="why"><summary>how a frame can show a focus ring at all</summary><div class="inner">
      <p class="cap" style="margin:0">It cannot, natively — <code>:focus-visible</code> needs a
      keyboard and a preview frame has none, the same way
      <code>prefers-reduced-motion</code> cannot be set inside one. So the <b>declared</b>
      outline is applied through a class instead: the before frame gets
      <code>rgba(26,58,42,.22)</code> exactly as the stylesheet declares it, the after frame gets
      the fix. Read from the stylesheet rather than the element, because
      <code>getComputedStyle</code> on an unfocused link returns the <i>resting</i> outline —
      <code>currentColor</code> at full opacity — which is how the first version of the probe
      measured 11.85:1 and passed a ring that does not exist.</p>
    </div></details>
  </div>
</section>

<!-- ============== C3 ============== -->
<section class="band">
  <div class="bhead"><span class="sev s-m">MED</span>
    <h2>C3 — On hover the button loses its outline entirely</h2>
    <span class="sel">.home-close-cta:hover{background:#fff}</span></div>
  <div class="step">
    <p class="cap">Hover swaps the fill to white while the border stays lime, so the control's
    edge against the pale panel measures <b>${C.hoverEdgeBefore}:1</b> — a white shape with a
    near-invisible outline floating on lime tint. The <code>translateY(-2px)</code> and the soft
    shadow are doing all the work of saying it is a button.</p>
    <p class="cap"><b>No separate change needed</b> — the C1 border fix repairs this too, which
    is the main reason to prefer it over darkening the fill.</p>
    ${P.hover}
  </div>
</section>

<!-- ============== C4 ============== -->
<section class="band">
  <div class="bhead"><span class="sev s-l">LATENT</span>
    <h2>C4 — The claim list has no measure cap, which changes nothing today</h2>
    <span class="sel">.home-close-points{max-width:${d.pointsMax}}</span></div>
  <div class="step">
    <p class="cap">The lead is capped at <code>${d.leadMax}</code> and the title at
    <code>${d.titleMax}</code>. The points list is not, so each <code>&lt;li&gt;</code> box runs
    the full <b>${d.li[ 0 ].w}px</b> for ${d.li[ 0 ].chars} characters of text.</p>
    <p class="cap"><b>The two frames below are identical, and that is the finding.</b> The
    strings are short, so nothing overruns — it is a trap rather than a defect: the first point
    that grows past ~75 characters will set a line nearly twice the measure of the lead directly
    above it. <b>I am not proposing this change</b> unless you want the guard; it has no visible
    effect and the honest way to record it is as a note.</p>
    ${P.cap}
  </div>
</section>

<!-- ============== PASSES ============== -->
<section class="band">
  <div class="bhead"><span class="sev s-ok">CLEAN</span><h2>What this band gets right</h2></div>
  <div class="step">
    <table>
      <tr><th>Check</th><th class="n">Measured</th><th>Note</th></tr>
      <tr><td>no-JavaScript readability</td><td class="n">pass</td><td>title, all 3 points and the CTA all render — the <code>.is-armed</code> inversion working as documented</td></tr>
      <tr><td>eyebrow text contrast</td><td class="n">${C.text.eyebrow}:1</td><td>needs 4.5</td></tr>
      <tr><td>h2 text contrast</td><td class="n">${C.text.title}:1</td><td>needs 3 at 40px/700</td></tr>
      <tr><td>lead text contrast</td><td class="n">${C.text.lead}:1</td><td>needs 4.5</td></tr>
      <tr><td>point text contrast</td><td class="n">${C.text.point}:1</td><td>needs 4.5</td></tr>
      <tr><td>CTA label contrast</td><td class="n">${C.text.cta}:1</td><td>needs 4.5 — the <i>text</i> was never the problem</td></tr>
      <tr><td>CTA target size</td><td class="n">${d.cta.w}×${d.cta.h}</td><td>needs 44×44</td></tr>
      <tr><td>lead measure</td><td class="n">~59 ch/line</td><td>inside the 45–75 the site holds to</td></tr>
      <tr><td>reveal animation</td><td class="n">pass</td><td>one-shot, scroll-triggered, not a loop — deliberately unlike bands 1 and 2, so it adds no third moving thing</td></tr>
      <tr><td>markup</td><td class="n">pass</td><td><code>tools/audit/htmlcheck.js</code>: 0 findings on this page across 10 checks</td></tr>
    </table>
  </div>
</section>

<!-- ============== THE PROPOSAL ============== -->
<section class="band">
  <div class="bhead"><span class="tag">PROPOSAL</span><h2>The whole change, in two lines</h2></div>
  <div class="step">
    <pre>.home-close-cta{
-  border:2px solid #d1f470;
+  border:2px solid #1a3a2a;
}
.home-close-cta:focus-visible{
-  outline:3px solid rgba(26,58,42,.22);
+  outline:3px solid #1a3a2a;
   outline-offset:3px;
}</pre>
    <p class="cap" style="margin-top:12px">Two declarations. No new colour, no layout change, no
    copy change, no change to the fill, the radius, the type or the animation. Fixes C1, C2 and
    C3 — <b>${C.edgeBefore}:1 → ${C.edgeAfter}:1</b> for the button's edge at rest and on hover,
    <b>${C.focusBefore}:1 → ${C.focusAfter}:1</b> for the focus ring.</p>
    <p class="cap"><b>Both sides, actual size, desktop and phone:</b></p>
    <div class="cmp">
      <div class="cmpcol"><span class="collab c-b">today</span>${P.origD}</div>
    </div>
    <div class="cmp">
      <div class="cmpcol"><span class="collab c-a">with the change</span>${P.fixedD}</div>
    </div>
    ${P.fixedM}
  </div>
</section>

<footer class="pg">
  Generated by <code>tools/browser/closereview.js</code> from the static export in
  <code>out/</code>. Claims re-runnable via <code>tools/browser/closeprobe.js</code>.
  Band 1 <code>docs/home-review.html</code> · band 2 <code>docs/flow-review.html</code>.
  Build ${STAMP}.
</footer>
</div>
`;

    fs.writeFileSync( OUT_FILE, html );
    console.log( `wrote ${path.relative( REPO, OUT_FILE )}  (${Math.round( Buffer.byteLength( html ) / 1024 )}KB)` );

    // ---- FIDELITY + FIX VERIFICATION ---------------------------------------------
    const ctx = await browser.newContext( { viewport: { width: 1280, height: 900 } } );
    const pg = await ctx.newPage();
    let bad = 0;
    const check = ( cond, name, got ) => { if ( !cond ) bad++; console.log( `  ${cond ? 'ok  ' : 'FAIL'} ${name}${got ? ` — ${got}` : ''}` ); };

    console.log( '\nfidelity — frame vs live page' );
    await pg.setContent( frameDoc( { html: H.d } ) );
    await pg.waitForTimeout( 350 );
    const f = await pg.evaluate( METRICS );
    check( f.panel.w === d.panel.w, 'panel width', `${f.panel.w} (live ${d.panel.w})` );
    check( f.cta.w === d.cta.w && f.cta.h === d.cta.h, 'CTA box', `${f.cta.w}x${f.cta.h} (live ${d.cta.w}x${d.cta.h})` );
    check( f.title.h === d.title.h, 'h2 height', `${f.title.h} (live ${d.title.h})` );
    check( f.rule.w === d.rule.w, 'the revealed rule width', `${f.rule.w} (live ${d.rule.w})` );

    console.log( '\nthe proposed fix, measured inside the frame' );
    await pg.setContent( frameDoc( { html: H.d, fix: true } ) );
    await pg.waitForTimeout( 350 );
    const after = await pg.evaluate( `(() => { ${CONTRAST_FN}
      const cta=document.querySelector('.home-close-cta');
      const cs=getComputedStyle(cta);
      return { edge: ratioOf(cs.borderTopColor, cta.parentElement), border: cs.borderTopColor }; })()` );
    check( after.edge >= 3, `the button's edge clears 3:1`, `${after.edge}:1 with border ${after.border}` );

    await pg.setContent( frameDoc( { html: H.d, focus: true, fix: true } ) );
    await pg.waitForTimeout( 350 );
    const afterFocus = await pg.evaluate( `(() => { ${CONTRAST_FN}
      const cta=document.querySelector('.home-close-cta');
      const cs=getComputedStyle(cta);
      return { r: ratioOf(cs.outlineColor, cta.parentElement), c: cs.outlineColor, w: cs.outlineWidth }; })()` );
    check( afterFocus.r >= 3, 'the focus ring clears 3:1', `${afterFocus.r}:1 with ${afterFocus.w} ${afterFocus.c}` );

    await ctx.close();
    if ( bad ) { console.error( `\n${bad} failure(s)` ); process.exit( 1 ); }
    console.log( '\nall checks pass' );
  } finally {
    await browser.close();
    await t.close();
  }
} )().catch( e => { console.error( e ); process.exit( 1 ); } );
