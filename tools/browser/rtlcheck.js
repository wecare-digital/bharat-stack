'use strict';

/**
 * rtlcheck - does the site survive being mirrored, and does it declare its direction.
 *
 * WHY THIS IS A SEPARATE GATE. Every other harness here loads a page in its shipped
 * direction, which is left-to-right on all 761 routes. The catalogue served to visitors
 * includes Arabic, Persian, Hebrew, Urdu, Pashto and Sindhi, so right-to-left is a state
 * a real reader reaches by pressing one button - and it was a state no suite entered.
 * pageaudit and devicecheck both pass at every width while the footer renders its full
 * stops at the wrong end of the line.
 *
 * WHAT IT ASSERTS, per route:
 *   1. The served HTML DECLARES dir. An undeclared direction is decided by the user agent,
 *      which is the same class of defect as an undeclared color-scheme.
 *   2. Under dir=rtl there is no horizontal overflow. This is the measurement that catches
 *      a physical margin, padding or inset that did not become logical: a left-anchored
 *      absolute box in a mirrored document pushes the page wider than the viewport.
 *   3. Under dir=rtl the fixed chrome stays on screen - the header bar spans the viewport
 *      and the language widget is fully inside it. The widget was pinned with right:20px,
 *      which in Arabic left it on the side a reader's eye ENDS on, over the text.
 *   4. The body's computed direction actually changes. A guard on the mechanism itself:
 *      if setting the attribute stopped taking effect, every other assertion here would
 *      still pass while proving nothing.
 *
 * HOW RTL IS ENTERED, AND WHY BOTH ATTRIBUTES ARE SET. This sets `lang` AND `dir` together,
 * which is what SupportWidget does in production. Setting only `dir` tests a state no
 * visitor can reach, and the first version of this gate did exactly that - it reported the
 * language widget pinned to the right under rtl and blamed the CSS.
 *
 * THE REASON IS NOT OBVIOUS AND IS WORTH STATING. The build does not ship the logical
 * properties this code is written with. Lightning CSS, which Next uses to minify, downlevels
 * `inset-inline-end:20px` for the configured browser targets into a PAIR OF :lang() RULES:
 *
 *   .wc-langbar:not(:is(:lang(ar),:lang(he), ... )){left:auto;right:20px}
 *   .wc-langbar:is(:lang(ar),:lang(he), ... )){left:20px;right:auto}
 *
 * `inset-inline` appears ZERO times in out/. So in the shipped stylesheet, mirroring is
 * keyed on the LANGUAGE attribute, not on `dir` - and `dir="rtl"` alone flips the bidi
 * algorithm while leaving every box physically where it was. The two attributes are not
 * independent here, and anything that sets one without the other gets half a mirror.
 *
 * Run:  node tools/browser/rtlcheck.js
 *       node tools/browser/rtlcheck.js / /contact/
 */

const { target, OUT_DIR } = require( './lib/serve' );
const { launch, gotoStable } = require( './lib/browser' );
const fs = require( 'fs' );
const path = require( 'path' );

/**
 * EVERY EXPORTED ROUTE, discovered rather than listed - public pages, inner pages and the
 * authenticated dashboard shells alike. An earlier version of this gate hardcoded the 18
 * public routes, which let "the dashboard is unmirrored" be asserted without being measured.
 * The dashboard renders Layout.tsx's own chrome, so it is a different surface, not a
 * variation on the public one.
 *
 * Blog posts are SAMPLED, not swept: 638 of them share one template, so they would multiply
 * runtime by forty and tell us the same thing once. pageaudit owns the full census.
 */
function discoverRoutes () {
  const out = [];
  const posts = [];
  ( function walk ( dir ) {
    for ( const entry of fs.readdirSync( dir, { withFileTypes: true } ) ) {
      const p = path.join( dir, entry.name );
      if ( entry.isDirectory() ) {
        if ( entry.name === '_next' ) continue;
        walk( p );
      } else if ( entry.name === 'index.html' ) {
        let r = '/' + path.relative( OUT_DIR, p ).replace( /\\/g, '/' );
        r = r.replace( /index\.html$/, '' );
        ( /^\/post\//.test( r ) ? posts : out ).push( r === '/' ? '/' : r );
      }
    }
  } )( OUT_DIR );
  return out.sort().concat( posts.sort().slice( 0, 2 ) );
}

/**
 * VIEWPORTS INCLUDING THE FOLDABLE POSTURES, because "wide and short" is where a mirrored
 * absolute inset is most visible and it was the one shape this gate originally skipped -
 * devicecheck covers those postures but only left-to-right, so the combination of mirrored
 * AND short was untested by anything.
 */
const VIEWPORTS = [
  { n: 'desktop', w: 1280, h: 900 },
  { n: 'phone', w: 390, h: 844 },
  { n: 'fold-folded', w: 280, h: 653 },
  { n: 'fold-land', w: 653, h: 280 },   // wide AND short
  { n: 'zflip-land', w: 880, h: 360 },  // wide AND short
  { n: 'zfold-cover-land', w: 882, h: 344 },
];

const PROBE = () => {
  const de = document.documentElement;
  const body = document.body;

  // Overflow is measured against documentElement, matching pageaudit, so a number here is
  // comparable with the ltr number that harness reports.
  const overflow = Math.max( 0, de.scrollWidth - de.clientWidth );

  const vw = de.clientWidth;
  const rect = el => {
    if ( !el ) return null;
    const r = el.getBoundingClientRect();
    return { l: Math.round( r.left ), r: Math.round( r.right ), w: Math.round( r.width ), h: Math.round( r.height ) };
  };

  const header = document.querySelector( 'header.hdr' ) || document.querySelector( 'header' );
  const widget = document.querySelector( '.wc-langbar' );

  // Anything sticking out past either edge. Reported with a selector so a failure names the
  // element rather than only the number.
  const strays = [];
  for ( const el of document.querySelectorAll( 'header, footer, main, .wc-langbar, .nav-menu, section, .home-mark, .home-cycle' ) ) {
    const r = el.getBoundingClientRect();
    if ( r.width === 0 && r.height === 0 ) continue;
    if ( r.right > vw + 1 || r.left < -1 ) {
      strays.push( {
        sel: el.tagName.toLowerCase() + '.' + ( el.className || '' ).split( /\s+/ ).filter( c => !/^jsx-/.test( c ) ).join( '.' ),
        l: Math.round( r.left ), r: Math.round( r.right ),
      } );
    }
  }

  /**
   * MIRROR SYMMETRY, which is the measurement that answers "is it actually mirrored" rather
   * than only "does it overflow". For a correctly mirrored element, its distance from the
   * inline-START edge is the same in both directions: left in ltr equals (viewport - right)
   * in rtl. A physical padding-left, margin-left or border-left that was never made logical
   * shows up as a difference, and nothing else does.
   *
   * THREE CLASSES ARE EXCLUDED, each for a real reason rather than to flatter the number.
   *   - EVERY INLINE-LEVEL BOX, including inline-block and inline-flex. A mirrored paragraph
   *     reflows, and an inline-level box is placed by line layout rather than against its
   *     container's edge, so it legitimately lands somewhere else - measuring it reports the
   *     bidi algorithm working as a fault. inline-block and inline-flex were allowed through
   *     at first, on the theory that a "box" should hold its place; the rotating hero pill and
   *     the brand badge then reported 79-555px of asymmetry for reflowing exactly as they
   *     should. Only block, flex and grid containers have a position defined relative to their
   *     container, which is what this assertion is about.
   *   - Subtrees under an explicit dir attribute. A terminal panel or a code sample is
   *     left-to-right by SYNTAX and is locked with dir="ltr" on purpose; it is supposed to be
   *     asymmetric, and a gate that failed on it would be arguing with the fix.
   *   - Class names that appear MORE THAN ONCE on the page. A mirrored flex row reverses its
   *     children, which is correct mirroring and moves every item's offset - so a row of
   *     cards reports a large difference for doing exactly the right thing. Restricting the
   *     assertion to singletons keeps it on page landmarks, where reordering is not a factor.
   *
   * OFFSETS ARE MEASURED AGAINST document.body, NOT THE VIEWPORT. The vertical scrollbar
   * changes side under rtl, which shifts every viewport-relative coordinate by its width and
   * reported a uniform ~16px asymmetry on every element of every page. Normalising against
   * the body box cancels it, because the scrollbar moves the body too.
   */
  const bodyRect = body.getBoundingClientRect();
  const seen = new Map();
  const rows = [];
  for ( const el of document.querySelectorAll( 'main *, header *, footer *' ) ) {
    const cs = getComputedStyle( el );
    if ( cs.display === 'none' || cs.visibility === 'hidden' ) continue;
    if ( cs.display.startsWith( 'inline' ) ) continue;
    // ...and anything INSIDE an inline-level box, because the whole subtree reflows with its
    // ancestor. The brand mark is a block-level <svg> inside an inline-flex badge: excluding
    // the badge but measuring its icon reported the icon as moving 553px when all that
    // happened was the badge finding a different place on a mirrored line.
    let inlineAncestor = false;
    for ( let a = el.parentElement; a && a !== body; a = a.parentElement ) {
      if ( getComputedStyle( a ).display.startsWith( 'inline' ) ) { inlineAncestor = true; break; }
    }
    if ( inlineAncestor ) continue;
    const locked = el.closest( '[dir]' );
    if ( locked && locked !== document.documentElement ) continue;
    const r = el.getBoundingClientRect();
    if ( r.width < 8 || r.height < 8 ) continue;
    // getAttribute, NOT el.className: on an SVG element className is an SVGAnimatedString, and
    // stringifying it yields the literal "[object SVGAnimatedString]" for every SVG on the
    // page. They then share one key, the singleton filter no longer separates them, and the
    // comparison comes out as hundreds of pixels of nonsense - which is how this first
    // reported 553px of asymmetry on an icon that had not moved.
    const cls = ( el.getAttribute( 'class' ) || '' ).split( /\s+/ ).filter( c => c && !/^jsx-/.test( c ) ).join( '.' );
    if ( !cls ) continue;
    const k = el.tagName.toLowerCase() + '.' + cls;
    seen.set( k, ( seen.get( k ) || 0 ) + 1 );
    rows.push( {
      k,
      start: Math.round( r.left - bodyRect.left ),
      end: Math.round( bodyRect.right - r.right ),
    } );
  }
  const symmetry = rows.filter( row => seen.get( row.k ) === 1 );

  return {
    dirAttr: de.getAttribute( 'dir' ) || '(unset)',
    computedDir: getComputedStyle( body ).direction,
    overflow,
    vw,
    header: rect( header ),
    widget: rect( widget ),
    strays: strays.slice( 0, 6 ),
    symmetry,
  };
};

/**
 * KNOWN ASYMMETRIES, named with their measured cause rather than absorbed into a looser
 * tolerance. A threshold wide enough to swallow these would also swallow a real physical
 * property, so each one is listed and the number stays at 6px.
 *
 * div.contact-info (and its two text children) - 10px, /grahak-os/ phone mock.
 *   Measured child offsets in .phone-header, a flex row with gap:10px and padding:12px 14px:
 *     ltr: back-arrow w=0 @14 | avatar w=40 @24 | contact-info @84 | verified-badge @284
 *     rtl: back-arrow w=0 @14 | avatar w=40 @24 | contact-info @74 | verified-badge @284
 *   Every item agrees except contact-info, and arithmetic says 74 is right: 14 padding + 0 +
 *   10 gap = 24 for the avatar, which is 40 wide and ends at 64, + 10 gap = 74. The ltr value
 *   is 10px larger because .back-arrow is an EMPTY span - <span className="back-arrow" /> with
 *   no content - and Chromium resolves the gap around a zero-width flex item differently by
 *   direction. Not a physical property, and not fixable from CSS: the real defect is the empty
 *   decorative element, which is a content question on that mock and predates this work.
 */
const KNOWN_ASYMMETRIC = new Set( [ 'div.contact-info', 'span.contact-name', 'span.contact-status' ] );

/** Elements whose inline-start offset did not survive mirroring, worst first. */
function asymmetries ( ltr, rtl, tolerance ) {
  const byKey = new Map( rtl.symmetry.map( s => [ s.k, s ] ) );
  const out = [];
  for ( const a of ltr.symmetry ) {
    const b = byKey.get( a.k );
    if ( !b ) continue;
    if ( KNOWN_ASYMMETRIC.has( a.k ) ) continue;
    const d = Math.abs( a.start - b.end );
    if ( d > tolerance ) out.push( { k: a.k, d, ltrStart: a.start, rtlEnd: b.end } );
  }
  return out.sort( ( x, y ) => y.d - x.d );
}

( async () => {
  const routes = process.argv.slice( 2 ).length ? process.argv.slice( 2 ) : discoverRoutes();
  const t = await target();
  const browser = await launch();

  console.log( `rtlcheck - ${t.mode} on ${t.base}` );
  console.log( `${routes.length} routes × ${VIEWPORTS.length} viewports\n` );

  let pass = 0, fail = 0;
  const failures = [];
  const ok = ( cond, label ) => {
    if ( cond ) { pass++; return true; }
    fail++; failures.push( label ); return false;
  };

  // --- 1. the served HTML must declare dir, before any script runs -------------------
  const declared = fs.readFileSync( path.join( OUT_DIR, 'index.html' ), 'utf8' );
  const hasDir = /<html[^>]*\sdir=("|')(ltr|rtl)\1/i.test( declared );
  ok( hasDir, 'the exported HTML declares dir on <html> (found: '
    + ( ( /<html[^>]*>/i.exec( declared ) || [ '' ] )[ 0 ].slice( 0, 90 ) ) + ')' );
  console.log( ( hasDir ? '  ok   ' : '  FAIL ' ) + 'exported <html> declares dir' );

  for ( const v of VIEWPORTS ) {
    const page = await browser.newPage( { viewport: { width: v.w, height: v.h } } );
    console.log( `\n--- ${v.n} ${v.w}×${v.h} ---` );

    for ( const r of routes ) {
      await gotoStable( page, t.base + r );

      // The shipped LTR state, for comparison. Nothing below is meaningful without it: a
      // mirrored page that overflows tells you nothing if the unmirrored one does too.
      const ltr = await page.evaluate( PROBE );

      // Mirror the document exactly as SupportWidget does - lang AND dir - then let layout
      // settle. 'ar' is the reported language and is in Lightning CSS's RTL :lang() set.
      await page.evaluate( () => {
        document.documentElement.lang = 'ar';
        document.documentElement.dir = 'rtl';
      } );
      await page.waitForTimeout( 120 );
      const rtl = await page.evaluate( PROBE );

      const a = ok( rtl.computedDir === 'rtl', `${r} @${v.n}: dir=rtl changes computed direction (got ${rtl.computedDir})` );
      const b = ok( rtl.overflow === 0, `${r} @${v.n}: no horizontal overflow under rtl (got ${rtl.overflow}px, ltr was ${ltr.overflow}px)` );
      const c = ok( !rtl.strays.length, `${r} @${v.n}: nothing crosses the viewport edge under rtl (${rtl.strays.map( s => s.sel + ' l=' + s.l + ' r=' + s.r ).join( ' | ' )})` );
      const d = ok( !rtl.widget || ( rtl.widget.l >= -1 && rtl.widget.r <= rtl.vw + 1 ),
        `${r} @${v.n}: the language widget is fully on screen under rtl (l=${rtl.widget && rtl.widget.l} r=${rtl.widget && rtl.widget.r} vw=${rtl.vw})` );
      // THE MIRROR MUST ACTUALLY HAPPEN. Without this the gate passes on a page that ignored
      // the direction entirely, which is the state it was written to detect. The widget is
      // the cleanest witness: fixed to the viewport, so its inset has nowhere to hide.
      const e = !ltr.widget || !rtl.widget
        ? ( pass++, true )
        : ok( Math.abs( rtl.widget.l - ltr.widget.l ) > 1,
          `${r} @${v.n}: the widget moved when the page mirrored (ltr l=${ltr.widget.l}, rtl l=${rtl.widget.l}) - logical insets compile to :lang() rules, so this fails if lang was not set` );

      // 6px absorbs sub-pixel rounding and scrollbar reservation without hiding a real
      // physical property - the ones this found measured 36px to 726px, not 7px.
      const asym = asymmetries( ltr, rtl, 6 );
      const f = ok( !asym.length,
        `${r} @${v.n}: every block element keeps its inline-start offset when mirrored (${asym.slice( 0, 3 ).map( x => `${x.k} off by ${x.d}px` ).join( ' | ' )})` );

      const line = ( a && b && c && d && e && f ) ? 'ok  ' : 'FAIL';
      console.log( `  ${line} ${r.padEnd( 18 )} dir:${rtl.computedDir} ovf:${String( rtl.overflow ).padStart( 3 )}`
        + ` widget ltr:${ltr.widget ? ltr.widget.l : 'n/a'}->rtl:${rtl.widget ? rtl.widget.l : 'n/a'}`
        + ` asym:${String( asym.length ).padStart( 2 )}`
        + ( rtl.strays.length ? '  strays: ' + rtl.strays.map( s => s.sel ).join( ',' ) : '' )
        + ( asym.length ? '  worst: ' + asym[ 0 ].k + ' ' + asym[ 0 ].d + 'px' : '' ) );
    }
    await page.close();
  }

  await browser.close();
  await t.close();

  console.log( `\n${pass}/${pass + fail} assertions passed` );
  if ( failures.length ) {
    console.log( '\nfailures:' );
    for ( const f of failures ) console.log( '  - ' + f );
  }
  process.exit( fail ? 1 : 0 );
} )().catch( e => { console.error( e ); process.exit( 1 ); } );
