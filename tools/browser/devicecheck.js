'use strict';

/**
 * devicecheck - every public route against the full device matrix, including the foldable
 * postures that width-only testing cannot reach.
 *
 * WHY THIS EXISTS SEPARATELY FROM pageaudit.js. pageaudit sweeps all 124 routes at three
 * widths, which is the right trade for a census. It cannot see the failure mode that only
 * appears when a viewport is WIDE AND SHORT - rare on a phone or a laptop, and the normal
 * shape of a folded-landscape device. That case produced a menu with a computed max-height of
 * ZERO at 653x280 and 40px at 880x360, on a page where every other check was green.
 *
 * WHAT IT ASSERTS, per route per posture:
 *   - no horizontal overflow
 *   - the top section's h1 is present and inside the viewport
 *   - with the menu open: it is at least 120px tall and does not run off the bottom
 *   - every tap target in the header is at least 44px
 *
 * Run:  node tools/browser/devicecheck.js
 *       node tools/browser/devicecheck.js /contact/ /terms/
 */

const { target } = require( './lib/serve' );
const { launch, gotoStable } = require( './lib/browser' );

const ROUTES = [ '/', '/grahak-os/', '/vayulok/', '/bharat-rx/', '/contact/', '/my-order/',
  '/terms/', '/privacy/', '/anew/', '/clear-closure/', '/dastavez/', '/elsewhere/',
  '/expo-week/', '/niji-setu/', '/ritual-guru/', '/404/', '/blog/', '/get/' ];

// CSS pixels. DevTools presets where one exists, marked approx where modelled.
const DEVICES = [
  { n: 'Fold folded',        w: 280,  h: 653 },
  { n: 'Fold folded land',   w: 653,  h: 280 },   // wide AND short
  { n: 'ZFold cover',        w: 344,  h: 882 },
  { n: 'ZFold cover land',   w: 882,  h: 344 },   // wide AND short
  { n: 'ZFold unfolded',     w: 904,  h: 1084 },
  { n: 'ZFlip',              w: 360,  h: 880 },
  { n: 'ZFlip land',         w: 880,  h: 360 },   // wide AND short
  { n: 'Pixel Fold inner',   w: 841,  h: 1010 },
  { n: 'Surface Duo',        w: 540,  h: 720 },
  { n: 'Surface Duo land',   w: 720,  h: 540 },
  { n: 'Zenbook Fold',       w: 853,  h: 1280 },
  { n: 'phone 320',          w: 320,  h: 844 },
  { n: 'phone 390',          w: 390,  h: 844 },
  { n: 'desktop 1280',       w: 1280, h: 900 },
  { n: 'desktop 1920',       w: 1920, h: 1080 },
];

const PROBE = () => {
  const vw = window.innerWidth, vh = window.innerHeight;
  const h1 = document.querySelector( 'h1' );
  const menu = document.querySelector( '.nav-menu' );
  const r = el => el.getBoundingClientRect();
  const targets = Array.from( document.querySelectorAll( 'header a[href], header button' ) )
    .map( el => ( { el, b: r( el ) } ) )
    .filter( x => x.b.width > 0 && x.b.height > 0 )
    .filter( x => { const cs = getComputedStyle( x.el ); return cs.visibility !== 'hidden' && +cs.opacity !== 0; } );
  const small = targets.filter( x => x.b.height < 44 ).map( x => {
    const cls = ( x.el.className || '' ).toString().split( /\s+/ ).filter( c => c && !c.startsWith( 'jsx-' ) )[ 0 ] || x.el.tagName;
    return `${cls}:${Math.round( x.b.height )}px`;
  } );
  return {
    overflow: document.documentElement.scrollWidth - vw,
    h1: h1 ? { w: Math.round( r( h1 ).width ), right: Math.round( r( h1 ).right ), top: Math.round( r( h1 ).top ) } : null,
    h1Fits: h1 ? r( h1 ).right <= vw + 1 : null,
    menu: menu ? {
      h: Math.round( r( menu ).height ),
      offBottom: Math.max( 0, Math.round( r( menu ).bottom - vh ) ),
      content: menu.scrollHeight,
    } : null,
    smallTargets: small,
  };
};

( async () => {
  const args = process.argv.slice( 2 ).filter( a => a.startsWith( '/' ) );
  const routes = args.length ? args : ROUTES;
  const t = await target();
  const browser = await launch();
  let fail = 0, checks = 0;
  const failures = [];

  try {
    console.log( `devicecheck - ${routes.length} routes × ${DEVICES.length} postures = ${routes.length * DEVICES.length} combinations\n` );
    for ( const d of DEVICES ) {
      const ctx = await browser.newContext( { viewport: { width: d.w, height: d.h } } );
      const page = await ctx.newPage();
      const bad = [];
      for ( const route of routes ) {
        try {
          await gotoStable( page, `${t.base}${route}`, { settle: 120 } );
          // open the menu where there is one - the wide-and-short failure needs it open
          await page.click( '.nav-trigger', { timeout: 1200 } ).catch( () => {} );
          await page.waitForTimeout( 160 );
          const x = await page.evaluate( PROBE );
          checks++;
          const problems = [];
          if ( x.overflow > 0 ) problems.push( `overflow ${x.overflow}px` );
          if ( x.h1Fits === false ) problems.push( `h1 ${x.h1.right}>${d.w}` );
          if ( x.menu && x.menu.h > 0 && x.menu.h < 120 ) problems.push( `menu ${x.menu.h}px for ${x.menu.content}px` );
          if ( x.menu && x.menu.offBottom > 0 ) problems.push( `menu +${x.menu.offBottom}px off-bottom` );
          if ( x.smallTargets.length ) problems.push( `tap<44: ${x.smallTargets.join( ',' )}` );
          if ( problems.length ) { bad.push( `${route} — ${problems.join( ' · ' )}` ); fail++; }
        } catch ( e ) {
          bad.push( `${route} — ERROR ${e.message.slice( 0, 50 )}` ); fail++;
        }
      }
      const label = `${d.n} ${d.w}×${d.h}`.padEnd( 28 );
      if ( bad.length ) {
        console.log( `  FAIL ${label} ${bad.length}/${routes.length}` );
        bad.forEach( b => console.log( `         ${b}` ) );
        failures.push( ...bad.map( b => `${d.n} ${d.w}×${d.h}: ${b}` ) );
      } else {
        console.log( `  ok   ${label} ${routes.length}/${routes.length}` );
      }
      await ctx.close();
    }
    console.log( `\n${checks - fail}/${checks} route×posture combinations clean` );
    if ( failures.length ) { console.log( '\nfailures:' ); failures.forEach( f => console.log( '  ' + f ) ); }
    process.exitCode = fail ? 1 : 0;
  } finally {
    await browser.close();
    if ( t.close ) await t.close();
  }
} )().catch( e => { console.error( e ); process.exit( 1 ); } );
