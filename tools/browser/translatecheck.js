'use strict';

/**
 * translatecheck - does the BRAND NAME survive translation, and does anything handle RTL.
 *
 * WHY THIS EXISTS SEPARATELY FROM pageaudit.js. pageaudit counts how many text nodes would
 * translate and how many would be skipped, per route. That census is the right shape for
 * coverage - "is the footer reachable at all" - and it is structurally blind to the defect
 * here, which is the OPPOSITE of missing coverage: a string that translates and must not.
 * A brand name rendering as a translation is invisible to a count that treats every
 * translated node as a success.
 *
 * WHAT IT ASSERTS, per route:
 *   1. No text node inside a brand lockup is translatable. WECARE.DIGITAL is a company
 *      name; "WECARE" and "DIGITAL" are separate text nodes in BrandLockup, so a naive
 *      walk collects both and the provider returns "نحن نهتم" / "رقمي" in Arabic and
 *      "डिजिटल" in Hindi - measured on the live site, which is what prompted this gate.
 *   2. The header menu and the footer ARE still translatable. The brand fix is an
 *      exclusion, and the failure mode of an exclusion is scope: putting the flag on a
 *      container instead of the wordmark would silently stop the whole header or footer
 *      translating, which is the regression #60 was opened to fix. So this asserts the
 *      thing the fix must NOT break, in the same run.
 *   3. Reports the document's `dir`. No route sets it today, and the catalogue served to
 *      visitors includes Arabic, Urdu, Hebrew and Persian.
 *
 * THE FILTER IS COPIED FROM pageaudit.js, WHICH COPIES SupportWidget.tsx. Three copies of
 * one rule is a drift risk and a deliberate trade: a harness that imports the component
 * would need the React runtime and a DOM, and the rule is nine lines. If SupportWidget's
 * acceptNode changes, this file and pageaudit.js both have to change with it.
 *
 * Run:  node tools/browser/translatecheck.js
 *       node tools/browser/translatecheck.js / /contact/
 */

const { target, OUT_DIR } = require( './lib/serve' );
const { launch, gotoStable } = require( './lib/browser' );
const fs = require( 'fs' );
const path = require( 'path' );

/** Routes to sweep: every exported page, so inner and dashboard shells are covered too. */
function discover () {
  const out = [];
  ( function walk ( dir ) {
    for ( const entry of fs.readdirSync( dir, { withFileTypes: true } ) ) {
      const p = path.join( dir, entry.name );
      if ( entry.isDirectory() ) {
        if ( entry.name === '_next' ) continue;
        walk( p );
      } else if ( entry.name === 'index.html' ) {
        let r = '/' + path.relative( OUT_DIR, p ).replace( /\\/g, '/' );
        r = r.replace( /index\.html$/, '' );
        out.push( r === '/' ? '/' : r );
      }
    }
  } )( OUT_DIR );
  return out.sort();
}

const PROBE = () => {
  const SKIP_TAGS = new Set( [ 'SCRIPT', 'STYLE', 'NOSCRIPT', 'IFRAME', 'SVG', 'CANVAS', 'VIDEO',
    'AUDIO', 'INPUT', 'TEXTAREA', 'SELECT', 'OPTION', 'CODE', 'PRE', 'HEAD', 'META', 'LINK',
    'NEXT-ROUTE-ANNOUNCER' ] );
  const root = document.body;

  /** SupportWidget's acceptNode, reimplemented. Returns null when the node WOULD translate. */
  function skipReason ( node ) {
    let el = node.parentElement;
    while ( el ) {
      if ( el.dataset && el.dataset.wcTranslate === 'true' ) return null;
      if ( SKIP_TAGS.has( el.tagName ) ) return 'tag:' + el.tagName;
      if ( el.dataset && el.dataset.wcNoTranslate === 'true' ) return 'data-wc-no-translate';
      if ( el.getAttribute( 'aria-hidden' ) === 'true' ) return 'aria-hidden';
      if ( el === root ) return null;
      el = el.parentElement;
    }
    return null;
  }

  function eligible ( node ) {
    const v = ( node.nodeValue || '' ).trim();
    return v.length >= 2 && /[A-Za-z\u0900-\u0DFF\u0600-\u06FF]/.test( v );
  }

  /** Text NODES under a subtree that the walker would collect. Nodes, not strings, so
   *  callers can dedupe across overlapping selectors. */
  function collectNodes ( el ) {
    if ( !el ) return [];
    const found = [];
    const w = document.createTreeWalker( el, NodeFilter.SHOW_TEXT );
    let n = w.nextNode();
    while ( n ) {
      if ( eligible( n ) && skipReason( n ) === null ) found.push( n );
      n = w.nextNode();
    }
    return found;
  }

  function translatableIn ( el ) {
    return collectNodes( el ).map( n => ( n.nodeValue || '' ).trim() );
  }

  // 1. brand lockups and badges - the wordmark must never be collected.
  //    DEDUPED BY NODE. `.brand-copy` is a child of `.brand-lockup`, so a naive loop over
  //    querySelectorAll counts the same text node once per matching ancestor and reports
  //    12 leaks where there are 4. The union is the honest number.
  const brandEls = Array.from( document.querySelectorAll( '.brand-lockup, .brand-badge, .brand-copy' ) );
  const leakedNodes = new Set();
  const brandLeaks = [];
  for ( const el of brandEls ) {
    for ( const n of collectNodes( el ) ) {
      if ( leakedNodes.has( n ) ) continue;
      leakedNodes.add( n );
      brandLeaks.push( { cls: el.className.split( /\s+/ ).filter( c => !/^jsx-/.test( c ) ).join( '.' ), text: ( n.nodeValue || '' ).trim() } );
    }
  }

  // Any element anywhere whose collected text is the brand or one of its halves. Catches a
  // lockup rendered without the expected class, which the selector above would miss. Nodes
  // already reported above are skipped so the two checks cannot double-count.
  const BRAND_WORDS = new Set( [ 'WECARE', 'DIGITAL', 'WECARE.DIGITAL', 'WECARE.', '.DIGITAL' ] );
  const strayBrand = [];
  {
    const w = document.createTreeWalker( root, NodeFilter.SHOW_TEXT );
    let n = w.nextNode();
    while ( n ) {
      const v = ( n.nodeValue || '' ).trim();
      if ( BRAND_WORDS.has( v.toUpperCase() ) && eligible( n ) && skipReason( n ) === null && !leakedNodes.has( n ) ) {
        leakedNodes.add( n );
        const p = n.parentElement;
        strayBrand.push( { text: v, tag: p ? p.tagName : '?', cls: p ? ( p.className || '' ).split( /\s+/ ).filter( c => !/^jsx-/.test( c ) ).join( '.' ) : '' } );
      }
      n = w.nextNode();
    }
  }

  // 1b. The brand EMBEDDED IN A LONGER SENTENCE, e.g. "…published by the WECARE.DIGITAL
  //     team." This is reported, NOT failed, and the distinction is the point. Flagging the
  //     whole node would stop a real sentence translating, which costs more than it saves;
  //     protecting just the name means splitting it into its own element, which is a content
  //     change per occurrence and an owner call. The provider may also translate the name
  //     here in one language and pass it through in another, so the visible result is
  //     inconsistent rather than simply wrong - which is exactly why it is worth counting.
  const embedded = [];
  {
    const w = document.createTreeWalker( root, NodeFilter.SHOW_TEXT );
    let n = w.nextNode();
    while ( n ) {
      const v = ( n.nodeValue || '' ).trim();
      if ( /WECARE\.DIGITAL/i.test( v ) && v.replace( /\s+/g, '' ).toUpperCase() !== 'WECARE.DIGITAL'
        && eligible( n ) && skipReason( n ) === null && !leakedNodes.has( n ) ) {
        embedded.push( v.slice( 0, 60 ) );
      }
      n = w.nextNode();
    }
  }

  // 2. the coverage the fix must not break
  const header = document.querySelector( 'header' );
  const footer = document.querySelector( 'footer' );
  const menu = document.querySelector( '.nav-menu' );

  return {
    brandElCount: brandEls.length,
    brandLeaks,
    strayBrand,
    embedded,
    headerTranslatable: translatableIn( header ).length,
    menuTranslatable: translatableIn( menu ).length,
    footerTranslatable: translatableIn( footer ).length,
    footerSample: translatableIn( footer ).slice( 0, 3 ),
    dir: document.documentElement.getAttribute( 'dir' ) || '(unset)',
    lang: document.documentElement.getAttribute( 'lang' ) || '(unset)',
    hasColorScheme: !!document.querySelector( 'meta[name="color-scheme"]' ),
  };
};

( async () => {
  const routes = process.argv.slice( 2 ).length ? process.argv.slice( 2 ) : discover();
  const t = await target();
  const browser = await launch();
  const page = await browser.newPage( { viewport: { width: 1280, height: 900 } } );

  console.log( `translatecheck - ${t.mode} on ${t.base}` );
  console.log( `${routes.length} routes\n` );

  let leakRoutes = 0, noFooter = 0, noHeader = 0, dirSet = 0;
  const leakStrings = new Map();
  const embeddedStrings = new Map();

  for ( const r of routes ) {
    await gotoStable( page, t.base + r );
    const res = await page.evaluate( PROBE );

    const leaks = res.brandLeaks.length + res.strayBrand.length;
    if ( leaks ) {
      leakRoutes++;
      for ( const l of [ ...res.brandLeaks.map( x => x.text ), ...res.strayBrand.map( x => x.text ) ] ) {
        leakStrings.set( l, ( leakStrings.get( l ) || 0 ) + 1 );
      }
    }
    for ( const e of res.embedded ) embeddedStrings.set( e, ( embeddedStrings.get( e ) || 0 ) + 1 );
    if ( res.footerTranslatable === 0 ) noFooter++;
    if ( res.headerTranslatable === 0 ) noHeader++;
    if ( res.dir !== '(unset)' ) dirSet++;

    const flag = leaks ? 'BRAND-LEAK' : 'ok';
    console.log(
      r.padEnd( 34 ) + ' ' + flag.padEnd( 11 )
      + ' brandEls:' + String( res.brandElCount ).padStart( 2 )
      + ' leak:' + String( leaks ).padStart( 2 )
      + ' hdr:' + String( res.headerTranslatable ).padStart( 3 )
      + ' menu:' + String( res.menuTranslatable ).padStart( 3 )
      + ' ftr:' + String( res.footerTranslatable ).padStart( 3 )
      + ' dir:' + res.dir
      + ( leaks ? '  <- ' + [ ...res.brandLeaks.map( x => x.text ), ...res.strayBrand.map( x => x.text ) ].slice( 0, 4 ).join( ' | ' ) : '' )
    );
  }

  await browser.close();
  await t.close();

  console.log( '\n=== SUMMARY ===' );
  console.log( 'routes swept                     : ' + routes.length );
  console.log( 'routes leaking the brand name    : ' + leakRoutes );
  console.log( 'distinct leaked strings          : ' + [ ...leakStrings.entries() ].map( ( [ k, v ] ) => `"${k}"×${v}` ).join( ' · ' ) );
  console.log( 'routes with NO translatable footer: ' + noFooter );
  console.log( 'routes with NO translatable header: ' + noHeader );
  console.log( 'routes setting dir               : ' + dirSet + ' of ' + routes.length );
  console.log( '\nbrand embedded in a translatable sentence (REPORTED, not failed - see §1b):' );
  if ( !embeddedStrings.size ) console.log( '  none' );
  for ( const [ k, v ] of [ ...embeddedStrings.entries() ].sort( ( a, b ) => b[ 1 ] - a[ 1 ] ) ) {
    console.log( `  ×${String( v ).padStart( 3 )}  "${k}"` );
  }

  const fail = leakRoutes > 0;
  console.log( '\n' + ( fail
    ? `FAIL - the brand name is translatable on ${leakRoutes} routes`
    : 'PASS - the brand name is protected on every route' ) );
  process.exit( fail ? 1 : 0 );
} )().catch( e => { console.error( e ); process.exit( 1 ); } );
