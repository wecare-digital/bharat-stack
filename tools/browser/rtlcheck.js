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

/** The public surfaces a visitor can reach and translate. */
const DEFAULT_ROUTES = [ '/', '/grahak-os/', '/vayulok/', '/bharat-rx/', '/contact/', '/my-order/',
  '/terms/', '/privacy/', '/anew/', '/clear-closure/', '/dastavez/', '/elsewhere/',
  '/expo-week/', '/niji-setu/', '/ritual-guru/', '/404/', '/blog/', '/get/' ];

/* Viewports chosen for direction, not for breadth: one desktop, one phone, and one
   wide-and-short posture, because a mirrored absolute inset is most visible where the axis
   is tightest. devicecheck owns the full matrix. */
const VIEWPORTS = [
  { n: 'desktop', w: 1280, h: 900 },
  { n: 'phone', w: 390, h: 844 },
  { n: 'short', w: 880, h: 360 },
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

  return {
    dirAttr: de.getAttribute( 'dir' ) || '(unset)',
    computedDir: getComputedStyle( body ).direction,
    overflow,
    vw,
    header: rect( header ),
    widget: rect( widget ),
    strays: strays.slice( 0, 6 ),
  };
};

( async () => {
  const routes = process.argv.slice( 2 ).length ? process.argv.slice( 2 ) : DEFAULT_ROUTES;
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

      const line = ( a && b && c && d && e ) ? 'ok  ' : 'FAIL';
      console.log( `  ${line} ${r.padEnd( 18 )} dir:${rtl.computedDir} ovf:${String( rtl.overflow ).padStart( 3 )}`
        + ` widget ltr:${ltr.widget ? ltr.widget.l : 'n/a'}->rtl:${rtl.widget ? rtl.widget.l : 'n/a'}`
        + ( rtl.strays.length ? '  strays: ' + rtl.strays.map( s => s.sel ).join( ',' ) : '' ) );
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
