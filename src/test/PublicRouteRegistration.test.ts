import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * GUARDS THE ONE MISTAKE THAT SHIPS A LOGIN WALL TO THE PUBLIC.
 *
 * Header and Footer are rendered ONCE, centrally, in _app.tsx - but only inside
 * `if ( isPublic )`. `isPublic` is an EXACT-MATCH allowlist, so creating a file under
 * src/pages is NOT enough to make a page public. A route that is missing from the
 * allowlist falls through to the authenticated branch and renders the STAFF SIGN-IN
 * SCREEN at HTTP 200 - no header, no footer, no page. _app.tsx calls this "a 404 that
 * does not look like one", and records that it reached the live site exactly that way
 * when the file-collection page was at /files.
 *
 * Nothing caught that until somebody loaded the URL. These tests do, at build time.
 *
 * WHY ROOT-LEVEL FILES ONLY. Authenticated surfaces live in directories
 * (dm/, dashboard/, pay/, seo/, service/, ...), while a new marketing or customer-facing
 * page is created as src/pages/<name>.tsx. Scanning the root is therefore the check with
 * signal and no false alarms; a directory-wide scan would flag the entire dashboard.
 * If a root-level page is ever deliberately authenticated, add it to
 * INTENTIONALLY_NOT_PUBLIC below with the reason, so the exemption is a decision on the
 * record rather than a silently passing test.
 *
 * THESE READ SOURCE AS TEXT rather than importing _app.tsx. Importing it would execute
 * Amplify.configure and the analytics side-effects at module scope, and the values being
 * asserted are literals in the file, not runtime exports. It is the same technique
 * GrahakOsPage.test.tsx and BottomNav.test.tsx already use.
 */

const PAGES_DIR = path.join( process.cwd(), 'src', 'pages' );
const APP_PATH = path.join( PAGES_DIR, '_app.tsx' );
const SITEMAP_PATH = path.join( process.cwd(), 'scripts', 'generate-sitemap.js' );

/** Root-level pages that are deliberately NOT public. Empty today - keep it that way. */
const INTENTIONALLY_NOT_PUBLIC: Record<string, string> = {};

const appSource = fs.readFileSync( APP_PATH, 'utf8' );

/**
 * The routes _app.tsx treats as public, assembled the same two ways the component does:
 * the keys of PUBLIC_PAGE_META, plus the bare `router.pathname === '...'` comparisons in
 * the isPublic chain (which is how '/', '/contact-test' and '/get' qualify).
 */
const readAllowlist = (): Set<string> => {
  const metaStart = appSource.indexOf( 'const PUBLIC_PAGE_META' );
  expect( metaStart, 'PUBLIC_PAGE_META not found in _app.tsx - this guard needs updating' ).toBeGreaterThan( -1 );
  // The map ends at the declaration that follows it; slice to the next top-level `const`
  // so a route added at the bottom of the map is still seen.
  const metaEnd = appSource.indexOf( '\nconst ', metaStart + 10 );
  const metaBlock = appSource.slice( metaStart, metaEnd === -1 ? undefined : metaEnd );
  const metaRoutes = Array.from( metaBlock.matchAll( /^\s*'(\/[a-z0-9-]+)'\s*:/gm ) ).map( m => m[ 1 ] );

  const gateStart = appSource.indexOf( 'const isPublic' );
  expect( gateStart, 'isPublic not found in _app.tsx - this guard needs updating' ).toBeGreaterThan( -1 );
  const gateBlock = appSource.slice( gateStart, appSource.indexOf( ';', gateStart ) );
  const literalRoutes = Array.from( gateBlock.matchAll( /router\.pathname === '([^']+)'/g ) ).map( m => m[ 1 ] );

  return new Set( [ ...metaRoutes, ...literalRoutes ] );
};

/** Route a root-level page file resolves to. index.tsx is the root itself. */
const routeForFile = ( file: string ): string =>
  file === 'index.tsx' ? '/' : `/${file.replace( /\.tsx$/, '' )}`;

const rootPageFiles = fs.readdirSync( PAGES_DIR )
  .filter( entry => entry.endsWith( '.tsx' ) && !entry.startsWith( '_' ) )
  .sort();

describe( 'public route registration', () => {
  it( 'finds root-level page files to check', () => {
    // A sanity check on the scan itself. If a refactor moves every page into a directory
    // this drops to zero and the assertions below would pass vacuously - the exact
    // failure mode of a gate that protects nothing.
    expect( rootPageFiles.length ).toBeGreaterThan( 5 );
    expect( rootPageFiles ).toContain( 'index.tsx' );
  } );

  it( 'registers every root-level page in the isPublic allowlist', () => {
    const allowlist = readAllowlist();
    const unregistered = rootPageFiles
      .map( file => ( { file, route: routeForFile( file ) } ) )
      .filter( ( { file, route } ) =>
        !allowlist.has( route ) && !( file in INTENTIONALLY_NOT_PUBLIC )
      );

    expect(
      unregistered.map( u => `${u.file} -> ${u.route}` ),
      'These pages exist but are NOT in the isPublic allowlist in _app.tsx, so they render '
      + 'the staff sign-in screen at HTTP 200 instead of the page - with no header and no '
      + 'footer. Add each route to PUBLIC_PAGE_META (marketing pages, which also gets it '
      + 'structured data and a sitemap entry) or to the router.pathname chain in isPublic '
      + '(public but non-marketing, as /get does).'
    ).toEqual( [] );
  } );

  it( 'keeps the allowlist free of routes that have no page file', () => {
    // The mirror of the test above. A route left in the allowlist after its page is
    // deleted advertises structured data, and possibly a sitemap entry, for a URL that
    // 404s - which is how /faq and /studio came to be listed long after deletion.
    const allowlist = readAllowlist();
    const rootRoutes = new Set( rootPageFiles.map( routeForFile ) );
    // Directory-backed public routes. These resolve to <dir>/index.tsx rather than a
    // root-level file, so they are checked against the directory instead.
    const dirBacked = Array.from( allowlist ).filter( route => {
      const dir = path.join( PAGES_DIR, route.replace( /^\//, '' ) );
      return route !== '/' && fs.existsSync( dir ) && fs.statSync( dir ).isDirectory();
    } );

    const orphaned = Array.from( allowlist ).filter( route =>
      !rootRoutes.has( route )
      && !dirBacked.includes( route )
      // Dynamic and content routes are matched by pattern, not by a literal file name.
      && !route.startsWith( '/post' )
      && !route.startsWith( '/blog' )
    );

    expect(
      orphaned,
      'These routes are in the _app.tsx public allowlist but have no page file, so they '
      + 'are advertised (structured data, and possibly the sitemap) while returning 404.'
    ).toEqual( [] );
  } );

  it( 'keeps PUBLIC_PAGE_META and the sitemap allowlist in step', () => {
    // generate-sitemap.js carries its own explicit allowlist and its comment requires the
    // two to match: "a route missing there renders an empty body with HTTP 200, so
    // advertising it here without it there would put blank pages in front of a crawler."
    // The reverse - a marketing page that renders but is never submitted - is the silent
    // half, and is what this asserts.
    //
    // NOT a two-way equality: the sitemap deliberately carries /blog, and /get and
    // /contact-test are deliberately public WITHOUT being in the sitemap.
    const sitemapSource = fs.readFileSync( SITEMAP_PATH, 'utf8' );
    const exactStart = sitemapSource.indexOf( 'PUBLIC_EXACT' );
    expect( exactStart, 'PUBLIC_EXACT not found in generate-sitemap.js' ).toBeGreaterThan( -1 );
    const exactBlock = sitemapSource.slice( exactStart, sitemapSource.indexOf( '] )', exactStart ) );
    const sitemapRoutes = new Set(
      Array.from( exactBlock.matchAll( /'(\/[a-z0-9-]*)'/g ) ).map( m => m[ 1 ] )
    );

    const metaStart = appSource.indexOf( 'const PUBLIC_PAGE_META' );
    const metaEnd = appSource.indexOf( '\nconst ', metaStart + 10 );
    const metaBlock = appSource.slice( metaStart, metaEnd === -1 ? undefined : metaEnd );
    const metaRoutes = Array.from( metaBlock.matchAll( /^\s*'(\/[a-z0-9-]+)'\s*:/gm ) ).map( m => m[ 1 ] );

    const missingFromSitemap = metaRoutes.filter( route => !sitemapRoutes.has( route ) );

    expect(
      missingFromSitemap,
      'These marketing routes are in PUBLIC_PAGE_META but missing from PUBLIC_EXACT in '
      + 'scripts/generate-sitemap.js, so they render for visitors but are never submitted '
      + 'to search engines.'
    ).toEqual( [] );
  } );
} );
