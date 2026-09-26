'use strict';

/**
 * pageaudit - one sweep over every built route, answering four questions that were
 * previously only answered for the home page:
 *
 *   1. STRUCTURE. Does the route carry the shared chrome - header, footer, support widget -
 *      and does it have a top section after the header (an h1 inside main)? A page with no
 *      top section has nothing telling a visitor what it is.
 *
 *   2. TRANSLATION COVERAGE. Reimplements SupportWidget's collectTextNodes filter exactly
 *      and reports, per route, how many text nodes it would translate and how many it would
 *      skip - with the reason. Attribute text (placeholder, aria-label, title, alt) is
 *      counted separately because the walker only touches text NODES, so none of it is ever
 *      translated at all.
 *
 *   3. AUTH SHELL. Dashboard routes render an Authenticator in the static export, so their
 *      real content is not present. Detected and reported rather than silently scored.
 *
 *   4. OVERFLOW. Horizontal overflow at a narrow phone, a folded-landscape foldable and a
 *      desktop width. Horizontal scroll on a text page is the cheapest possible signal that
 *      a layout does not survive a viewport.
 *
 * WHY ONE SCRIPT. These four need the same 125 page loads. Splitting them would quadruple
 * the run for no extra information.
 *
 * Run:  node tools/browser/pageaudit.js            # all non-blog routes
 *       node tools/browser/pageaudit.js --public   # the 15 public routes only
 *       node tools/browser/pageaudit.js /contact/ /terms/
 * Writes docs/execution/page-audit.json alongside the console table.
 */

const fs = require( 'fs' );
const path = require( 'path' );
const { target, OUT_DIR } = require( './lib/serve' );
const { launch } = require( './lib/browser' );

const REPO = path.join( __dirname, '..', '..' );
const OUT_JSON = path.join( REPO, 'docs', 'execution', 'page-audit.json' );

// The 15 routes _app.tsx treats as public, plus the two it names directly.
const PUBLIC = [ '/', '/grahak-os/', '/vayulok/', '/bharat-rx/', '/contact/', '/my-order/',
  '/terms/', '/privacy/', '/anew/', '/clear-closure/', '/dastavez/', '/elsewhere/',
  '/expo-week/', '/niji-setu/', '/ritual-guru/' ];

function discover () {
  const routes = [];
  const walk = dir => {
    for ( const e of fs.readdirSync( dir, { withFileTypes: true } ) ) {
      const p = path.join( dir, e.name );
      if ( e.isDirectory() ) {
        if ( e.name === 'post' || e.name === '_next' ) continue;
        walk( p );
      } else if ( e.name.endsWith( '.html' ) ) {
        let r = '/' + path.relative( OUT_DIR, p ).replace( /\\/g, '/' );
        r = r.replace( /index\.html$/, '' ).replace( /\.html$/, '/' );
        if ( !routes.includes( r ) ) routes.push( r );
      }
    }
  };
  walk( OUT_DIR );
  return routes.sort();
}

const PROBE = () => {
  const SKIP_TAGS = new Set( [ 'SCRIPT', 'STYLE', 'NOSCRIPT', 'IFRAME', 'SVG', 'CANVAS', 'VIDEO',
    'AUDIO', 'INPUT', 'TEXTAREA', 'SELECT', 'OPTION', 'CODE', 'PRE', 'HEAD', 'META', 'LINK' ] );
  const root = document.body;

  // --- translation coverage: SupportWidget's filter, reimplemented ---
  const skipped = {};
  let translated = 0;
  const walker = document.createTreeWalker( root, NodeFilter.SHOW_TEXT );
  let n = walker.nextNode();
  const samples = {};
  while ( n ) {
    const v = ( n.nodeValue || '' ).trim();
    if ( v.length >= 2 && /[A-Za-z\u0900-\u0DFF\u0600-\u06FF]/.test( v ) ) {
      let el = n.parentElement, why = null;
      while ( el ) {
        // data-wc-translate is the opt-in that beats aria-hidden - nearest flag wins, exactly
        // as SupportWidget's walker does it. Without this the census reports the rotating
        // words as skipped after they have been fixed, which would make the gate lie.
        if ( el.dataset && el.dataset.wcTranslate === 'true' ) break;
        if ( SKIP_TAGS.has( el.tagName ) ) { why = 'tag:' + el.tagName; break; }
        if ( el.dataset && el.dataset.wcNoTranslate === 'true' ) { why = 'data-wc-no-translate'; break; }
        if ( el.getAttribute( 'aria-hidden' ) === 'true' ) { why = 'aria-hidden'; break; }
        if ( el === root ) break;
        el = el.parentElement;
      }
      if ( why ) {
        skipped[ why ] = ( skipped[ why ] || 0 ) + 1;
        if ( !samples[ why ] ) samples[ why ] = v.slice( 0, 40 );
      } else translated++;
    }
    n = walker.nextNode();
  }

  // --- attribute text: the walker cannot reach any of this ---
  const attrs = { placeholder: 0, 'aria-label': 0, title: 0, alt: 0 };
  for ( const el of document.querySelectorAll( '[placeholder],[aria-label],[title],[alt]' ) ) {
    for ( const a of Object.keys( attrs ) ) {
      const val = el.getAttribute( a );
      if ( val && val.trim().length >= 2 && /[A-Za-z]/.test( val ) ) attrs[ a ]++;
    }
  }

  // --- structure ---
  const main = document.querySelector( 'main' );
  const header = document.querySelector( 'header' );
  const footer = document.querySelector( 'footer' ) || document.querySelector( '[class*="ft-footer"]' );
  const widget = document.querySelector( '.wc-langbar' ) || document.querySelector( '[class*="wc-lang"]' );
  const h1s = Array.from( document.querySelectorAll( 'h1' ) );
  const visible = el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const firstH1 = h1s.find( visible );
  const authShell = !!document.querySelector( '[data-amplify-authenticator], .amplify-authenticator' )
    || /sign in|signin/i.test( ( document.querySelector( 'button' )?.textContent || '' ) );

  return {
    translated, skipped, samples, attrs,
    attrTotal: Object.values( attrs ).reduce( ( a, b ) => a + b, 0 ),
    header: !!header, footer: !!footer, widget: !!widget, main: !!main,
    h1Count: h1s.length,
    h1Text: firstH1 ? firstH1.textContent.replace( /\s+/g, ' ' ).trim().slice( 0, 46 ) : null,
    // a top section = a visible h1 inside main, above the fold
    topSection: !!( firstH1 && main && main.contains( firstH1 )
      && firstH1.getBoundingClientRect().top < window.innerHeight ),
    authShell,
    overflow: document.documentElement.scrollWidth - window.innerWidth,
  };
};

( async () => {
  const args = process.argv.slice( 2 );
  const t = await target();
  const browser = await launch();
  let routes = args.filter( a => a.startsWith( '/' ) );
  if ( !routes.length ) routes = args.includes( '--public' ) ? PUBLIC : discover();

  const VPS = [
    { k: 'phone', w: 320, h: 844 },
    { k: 'fold', w: 653, h: 280 },   // Galaxy Fold, folded, landscape - wide AND short
    { k: 'desk', w: 1280, h: 900 },
  ];

  const results = [];
  try {
    console.log( `pageaudit - ${routes.length} routes × ${VPS.length} viewports on ${t.base}\n` );
    for ( const vp of VPS ) {
      const ctx = await browser.newContext( { viewport: { width: vp.w, height: vp.h } } );
      const page = await ctx.newPage();
      for ( const r of routes ) {
        let rec = results.find( x => x.route === r );
        if ( !rec ) { rec = { route: r, vp: {} }; results.push( rec ); }
        try {
          const res = await page.goto( `${t.base}${r}`, { waitUntil: 'load', timeout: 20000 } );
          await page.waitForTimeout( 250 );
          const data = await page.evaluate( PROBE );
          rec.status = res ? res.status() : null;
          rec.vp[ vp.k ] = { overflow: data.overflow, topSection: data.topSection };
          if ( vp.k === 'desk' ) Object.assign( rec, data );
        } catch ( e ) {
          rec.vp[ vp.k ] = { error: e.message.slice( 0, 60 ) };
        }
      }
      await ctx.close();
      console.log( `  swept ${vp.k} (${vp.w}×${vp.h})` );
    }

    // ---------------- report ----------------
    const pub = r => PUBLIC.includes( r.route );
    const line = r => {
      const sk = Object.entries( r.skipped || {} ).map( ( [ k, v ] ) => `${k}:${v}` ).join( ' ' );
      const ovf = VPS.map( v => ( r.vp[ v.k ]?.overflow ?? '?' ) ).join( '/' );
      return `${r.route.padEnd( 34 ).slice( 0, 34 )} ${String( r.status ).padStart( 3 )} `
        + `${r.header ? 'H' : '-'}${r.footer ? 'F' : '-'}${r.widget ? 'W' : '-'} `
        + `${r.topSection ? 'top' : 'NONE'.padEnd( 3 )} h1:${String( r.h1Count ).padStart( 2 )} `
        + `tr:${String( r.translated ).padStart( 4 )} attr:${String( r.attrTotal ).padStart( 3 )} `
        + `ovf:${ovf.padEnd( 8 )} ${r.authShell ? 'AUTH ' : ''}${sk}`;
    };

    console.log( '\n=== PUBLIC ROUTES ===' );
    console.log( 'route                              st  HFW top  h1  translatable  attr  overflow(320/653/1280)  skips' );
    results.filter( pub ).forEach( r => console.log( line( r ) ) );

    console.log( '\n=== EVERYTHING ELSE (inner + orphaned) ===' );
    const others = results.filter( r => !pub( r ) );
    others.forEach( r => console.log( line( r ) ) );

    console.log( '\n=== SUMMARY ===' );
    const noTop = results.filter( r => !r.topSection && !r.authShell );
    const noChrome = results.filter( r => !r.header || !r.footer || !r.widget );
    const overflowing = results.filter( r => VPS.some( v => ( r.vp[ v.k ]?.overflow || 0 ) > 0 ) );
    const withSkips = results.filter( r => Object.keys( r.skipped || {} ).length );
    const auth = results.filter( r => r.authShell );
    const skipTotals = {};
    for ( const r of results ) for ( const [ k, v ] of Object.entries( r.skipped || {} ) ) skipTotals[ k ] = ( skipTotals[ k ] || 0 ) + v;
    const attrTotal = results.reduce( ( a, r ) => a + ( r.attrTotal || 0 ), 0 );

    console.log( `routes swept                : ${results.length}` );
    console.log( `auth shell (no real content): ${auth.length}` );
    console.log( `missing header/footer/widget: ${noChrome.length}` );
    console.log( `NO top section after header : ${noTop.length}` );
    console.log( `horizontal overflow somewhere: ${overflowing.length}${overflowing.length ? ' -> ' + overflowing.slice( 0, 8 ).map( r => r.route ).join( ', ' ) : ''}` );
    console.log( `routes with skipped text     : ${withSkips.length}` );
    console.log( `skip reasons (nodes)         : ${Object.entries( skipTotals ).map( ( [ k, v ] ) => `${k}=${v}` ).join( ' · ' ) || 'none'}` );
    console.log( `attribute strings, never translated by the walker: ${attrTotal}` );

    fs.mkdirSync( path.dirname( OUT_JSON ), { recursive: true } );
    fs.writeFileSync( OUT_JSON, JSON.stringify( { generated: new Date().toISOString(), routes: results }, null, 1 ) );
    console.log( `\nwrote ${path.relative( REPO, OUT_JSON )}` );
  } finally {
    await browser.close();
    if ( t.close ) await t.close();
  }
} )().catch( e => { console.error( e ); process.exit( 1 ); } );
