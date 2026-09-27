'use strict';

/**
 * closeprobe - the home page's THIRD band, section.home-close, measured as claims.
 *
 * Third in the set: homeprobe.js owns band 1, flowprobe.js band 2, this one band 3. Same
 * contract - every line is an assertion, and failures are the open findings rather than a
 * broken harness.
 *
 * WHAT THIS BAND IS: the closing argument. A lime-tinted panel holding an eyebrow, an h2, a
 * lead, a rule that draws itself on scroll, three claim lines with CSS-drawn ticks, and the
 * page's ONLY call to action.
 *
 * FOUR THINGS THAT NEEDED A BROWSER:
 *
 *   1. THE FOCUS RING'S CONTRAST. outline:3px solid rgba(26,58,42,.22) sits on a lime-tinted
 *      panel. WCAG 1.4.11 wants 3:1 for a focus indicator against what surrounds it, and a
 *      .22 alpha over a pale tint cannot be judged from the source - it has to be composited.
 *
 *   2. WHERE THE ONLY ACTION IS. The page has one link inside <main>. Its distance below the
 *      fold is the whole of finding M5 in the band-1 audit, and it is THIS band's element.
 *
 *   3. THE MEASURE OF EACH TEXT BLOCK. The lead is capped at 62ch. The eyebrow, the h2 and
 *      the three points are not all capped, and a 1232px panel will happily run a line to
 *      1126px. Only layout can say which ones actually do.
 *
 *   4. WHETHER THE REVEAL IS SAFE. The .is-armed inversion is the one thing this band gets
 *      right that band 2 does not, so it is worth asserting rather than assuming: with no
 *      JavaScript every element must still be visible.
 *
 * Run: node tools/browser/closeprobe.js        (needs out/ - see README.md)
 */

const { target } = require( './lib/serve' );
const { launch, gotoStable } = require( './lib/browser' );

let pass = 0, fail = 0;
const ok = ( cond, name, detail ) => {
  if ( cond ) pass++; else fail++;
  console.log( `  ${cond ? 'ok  ' : 'FAIL'} ${name}${detail ? ` — ${detail}` : ''}` );
};

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
  function ratioOf(fgStr,el){var fg=parse(fgStr);if(!fg)return null;var b=bg(el);
    var c=over(fg,b);var L1=lum(c.r,c.g,c.b),L2=lum(b.r,b.g,b.b);
    var hi=Math.max(L1,L2),lo=Math.min(L1,L2);
    return Math.round(((hi+0.05)/(lo+0.05))*100)/100}
  function ratio(el){return ratioOf(getComputedStyle(el).color,el)}
`;

( async () => {
  const t = await target();
  const browser = await launch();
  const ctx = await browser.newContext( { viewport: { width: 1280, height: 900 } } );
  const page = await ctx.newPage();
  await gotoStable( page, `${t.base}/` );
  // Scroll it in so .is-in has fired and the revealed state is what gets measured.
  await page.evaluate( () => document.querySelector( '.home-close' ).scrollIntoView( { block: 'center' } ) );
  await page.waitForTimeout( 1200 );

  console.log( '\nsection.home-close — band 3 of 3\n' );

  console.log( 'LAYOUT AND MEASURE' );
  const L = await page.evaluate( () => {
    const b = s => { const e = document.querySelector( s ); if ( !e ) return null;
      const r = e.getBoundingClientRect();
      return { w: Math.round( r.width ), h: Math.round( r.height ), t: Math.round( r.top + window.scrollY ) }; };
    const cs = ( s, p ) => { const e = document.querySelector( s ); return e ? getComputedStyle( e )[ p ] : null; };
    // Longest rendered line per block, in characters - the thing a max-width is for.
    const measure = s => {
      const e = document.querySelector( s );
      if ( !e ) return null;
      const txt = e.textContent.replace( /\s+/g, ' ' ).trim();
      const r = document.createRange();
      r.selectNodeContents( e );
      const lines = r.getClientRects().length;
      return { chars: txt.length, lines, w: Math.round( e.getBoundingClientRect().width ) };
    };
    return {
      band: b( '.home-close' ), panel: b( '.home-close-panel' ),
      eyebrow: b( '.home-close-eyebrow' ), title: b( '.home-close-title' ),
      lead: b( '.home-close-lead' ), rule: b( '.home-close-rule' ),
      points: b( '.home-close-points' ), cta: b( '.home-close-cta' ),
      li: [ ...document.querySelectorAll( '.home-close-points li' ) ].map( e => ( {
        w: Math.round( e.getBoundingClientRect().width ),
        chars: e.textContent.trim().length,
      } ) ),
      maxw: {
        eyebrow: cs( '.home-close-eyebrow', 'maxWidth' ),
        title: cs( '.home-close-title', 'maxWidth' ),
        lead: cs( '.home-close-lead', 'maxWidth' ),
        points: cs( '.home-close-points', 'maxWidth' ),
      },
      m: { title: measure( '.home-close-title' ), lead: measure( '.home-close-lead' ) },
      armed: document.querySelector( '.home-close' ).className.includes( 'is-armed' ),
      shownIn: document.querySelector( '.home-close' ).className.includes( 'is-in' ),
      ctaOutline: cs( '.home-close-cta', 'outlineColor' ),
      innerW: ( () => { const p = document.querySelector( '.home-close-panel' );
        return Math.round( p.getBoundingClientRect().width - parseFloat( getComputedStyle( p ).paddingLeft ) * 2 ); } )(),
      docH: Math.round( document.documentElement.scrollHeight ),
    };
  } );

  ok( L.armed && L.shownIn, 'the reveal has armed and played', `is-armed=${L.armed} is-in=${L.shownIn}` );
  ok( L.rule.w > 100, 'the lime rule has drawn itself across', `${L.rule.w}px of ${L.innerW}px` );

  // The measure of each block. 45-75 characters is the range the rest of the site holds to.
  const CH = 75;
  ok( L.m.lead.chars / L.m.lead.lines <= CH, 'the lead sits inside a readable measure',
    `${L.m.lead.chars} chars over ${L.m.lead.lines} lines = ~${Math.round( L.m.lead.chars / L.m.lead.lines )}/line, max-width ${L.maxw.lead}` );
  ok( L.maxw.points !== 'none', 'the claim list is capped to a measure',
    `max-width:${L.maxw.points} — each li runs the full ${L.li[ 0 ].w}px for ${L.li[ 0 ].chars} characters` );

  console.log( '\nTHE PAGE\'S ONLY ACTION' );
  const A = await page.evaluate( () => {
    const main = document.querySelector( 'main' );
    const links = [ ...main.querySelectorAll( 'a[href],button,input,select,textarea,[tabindex]:not([tabindex="-1"])' ) ];
    const cta = document.querySelector( '.home-close-cta' );
    const r = cta.getBoundingClientRect();
    return { count: links.length, top: Math.round( r.top + window.scrollY ),
      w: Math.round( r.width ), h: Math.round( r.height ),
      docH: Math.round( document.documentElement.scrollHeight ), vh: window.innerHeight };
  } );
  ok( A.count > 1, 'the page offers more than one action', `${A.count} focusable element in <main>` );
  ok( A.top < A.vh, 'the action is above the fold',
    `at y=${A.top} with a ${A.vh}px viewport — ${Math.round( A.top / A.vh * 100 )}% of a screen down, ` +
    `${Math.round( A.top / A.docH * 100 )}% into the document` );
  ok( A.w >= 44 && A.h >= 44, 'the CTA meets the 44x44 target size', `${A.w}x${A.h}` );

  console.log( '\nCONTRAST (composited over the lime tint)' );
  const C = await page.evaluate( `(() => {
    ${CONTRAST_FN}
    const out = {};
    for (const [k,s] of Object.entries({eyebrow:'.home-close-eyebrow',title:'.home-close-title',
        lead:'.home-close-lead',point:'.home-close-points li',cta:'.home-close-cta'})) {
      const el = document.querySelector(s);
      if (!el) continue;
      const cs = getComputedStyle(el);
      const fs = parseFloat(cs.fontSize), fw = parseInt(cs.fontWeight,10)||400;
      out[k] = { fs, fw, ratio: ratio(el), need: (fs>=24||(fs>=18.66&&fw>=700)) ? 3 : 4.5 };
    }
    // The focus ring is a non-text indicator: 1.4.11 wants 3:1 against ADJACENT colours,
    // which here is the lime panel it sits on, not the page white.
    //
    // READ OUT OF THE STYLESHEET, NOT OFF THE ELEMENT. getComputedStyle on an unfocused
    // link returns the RESTING outline - which is currentColor, i.e. #1a3a2a at full
    // opacity - so the first version of this measured 11.85:1 and passed a ring that does
    // not exist. The declared value is rgba(26,58,42,.22) inside a :focus-visible rule, and
    // that rule is only in the cascade while focused. Programmatic .focus() does not
    // reliably set :focus-visible either, so the rule text is the honest source.
    const cta = document.querySelector('.home-close-cta');
    const cs = getComputedStyle(cta);
    const focusRule = (() => {
      for (const sheet of document.styleSheets) {
        let rules; try { rules = sheet.cssRules } catch (e) { continue }
        for (const r of rules || []) {
          if (r.selectorText && /home-close-cta[^,]*:focus-visible/.test(r.selectorText)) {
            return r.style.outline || (r.style.outlineWidth + ' ' + r.style.outlineStyle + ' ' + r.style.outlineColor);
          }
        }
      }
      return null;
    })();
    const declared = focusRule && /rgba?\\([^)]+\\)|#[0-9a-f]{3,8}/i.exec(focusRule);
    out.focus = { rule: focusRule, color: declared ? declared[0] : cs.outlineColor,
      ratio: ratioOf(declared ? declared[0] : cs.outlineColor, cta.parentElement), need: 3 };
    // And the button's own edge against the panel behind it.
    out.ctaEdge = { color: cs.backgroundColor,
      ratio: ratioOf(cs.backgroundColor, cta.parentElement), need: 3 };
    return out;
  })()` );
  for ( const k of [ 'eyebrow', 'title', 'lead', 'point', 'cta' ] ) {
    const c = C[ k ]; if ( !c ) continue;
    ok( c.ratio >= c.need, `.home-close-${k} ${c.fs}px/${c.fw}`, `${c.ratio}:1 (needs ${c.need}:1)` );
  }
  ok( C.focus.ratio >= 3, `the focus ring is visible (WCAG 1.4.11)`,
    `declared "${C.focus.rule || '(no :focus-visible rule found)'}" → ${C.focus.color} ` +
    `= ${C.focus.ratio}:1 against the panel it sits on (needs 3:1)` );
  ok( C.ctaEdge.ratio >= 3, 'the CTA fill is distinguishable from the panel (WCAG 1.4.11)',
    `${C.ctaEdge.ratio}:1 (needs 3:1) — solid lime on a 22% lime tint` );

  console.log( '\nTHE NO-JAVASCRIPT STATE — the thing this band gets right' );
  const noJsCtx = await browser.newContext( { viewport: { width: 1280, height: 900 }, javaScriptEnabled: false } );
  const njs = await noJsCtx.newPage();
  await njs.goto( `${t.base}/`, { waitUntil: 'load' } );
  const N = await njs.evaluate( () => {
    const vis = s => { const e = document.querySelector( s ); if ( !e ) return false;
      const c = getComputedStyle( e ); const r = e.getBoundingClientRect();
      return c.display !== 'none' && c.visibility !== 'hidden' && +c.opacity > 0 && r.height > 0; };
    return { armed: document.querySelector( '.home-close' ).className.includes( 'is-armed' ),
      title: vis( '.home-close-title' ), points: vis( '.home-close-points li' ),
      cta: vis( '.home-close-cta' ), rule: vis( '.home-close-rule' ) };
  } );
  await noJsCtx.close();
  ok( !N.armed, 'no JavaScript means the band never arms', `is-armed=${N.armed}` );
  ok( N.title && N.points && N.cta, 'every element is readable with no JavaScript',
    `title=${N.title} points=${N.points} cta=${N.cta}` );

  console.log( '\nPHONE 390' );
  const mctx = await browser.newContext( { viewport: { width: 390, height: 844 } } );
  const mp = await mctx.newPage();
  await gotoStable( mp, `${t.base}/` );
  await mp.evaluate( () => document.querySelector( '.home-close' ).scrollIntoView( { block: 'center' } ) );
  await mp.waitForTimeout( 1200 );
  const Mm = await mp.evaluate( () => {
    const cta = document.querySelector( '.home-close-cta' );
    const r = cta.getBoundingClientRect();
    const panel = document.querySelector( '.home-close-panel' ).getBoundingClientRect();
    return { ctaTop: Math.round( r.top + window.scrollY ), ctaW: Math.round( r.width ), ctaH: Math.round( r.height ),
      panelW: Math.round( panel.width ), docH: Math.round( document.documentElement.scrollHeight ), vh: window.innerHeight };
  } );
  await mctx.close();
  ok( Mm.ctaTop < Mm.vh, 'the action is above the fold on a phone',
    `at y=${Mm.ctaTop} with an ${Mm.vh}px viewport — ${( Mm.ctaTop / Mm.vh ).toFixed( 1 )} screens down` );
  ok( Mm.ctaW >= Mm.panelW * 0.6, 'the CTA uses the panel width on a phone',
    `${Mm.ctaW}px button in a ${Mm.panelW}px panel — ${Math.round( Mm.ctaW / Mm.panelW * 100 )}%` );

  await ctx.close();
  await browser.close();
  await t.close();

  console.log( `\n${pass} ok, ${fail} FAIL` );
  console.log( 'Failures are the open findings for this band, not a broken harness.' );
} )().catch( e => { console.error( e ); process.exit( 1 ); } );
