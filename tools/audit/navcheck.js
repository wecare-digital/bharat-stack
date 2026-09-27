'use strict';

/**
 * navcheck - the workspace navigation against the routes the build actually emits.
 *
 * WHY THIS IS SEPARATE FROM routegraph.js. routegraph reads hrefs out of the rendered
 * HTML, and every /workspace/ page ships ZERO /workspace/ hrefs: the shell is rendered on
 * the client behind an auth gate, so the sidebar exists in no static document. Measured on
 * out/workspace/engage/index.html - 0 matches for href="/workspace. routegraph therefore
 * reports all 105 workspace routes as orphans, which is true of the crawlable graph and
 * says nothing about whether an operator can reach them.
 *
 * So the workspace's real reachability question is a SOURCE question - is the route in
 * src/config/navigation.ts - and that is what this checks. The two scripts together cover
 * the site: routegraph owns the public graph, navcheck owns the authenticated one.
 *
 * WHY THE PATHS ARE REGEX-EXTRACTED rather than imported. navigation.ts is TypeScript and
 * the app is type:module; importing it needs a transpile step, and a transpile in an audit
 * script is a dependency that can break independently of the thing being audited. Every
 * path in that file is written as a `path: '...'` literal - 113 of them - so a regex sees
 * all of them, including any a hand-maintained list would drift from.
 *
 * QUERY STRINGS ARE FILTERS, NOT ROUTES. '/workspace/engage/inbox?channel=rcs' is the inbox
 * with a selector pre-set; it resolves to the inbox page. Stripped before comparison, and
 * counted separately so the report does not claim five missing pages that are one page.
 *
 * Run: node tools/audit/navcheck.js        (needs out/ - npm run build)
 */

const fs = require( 'fs' );
const path = require( 'path' );

const REPO = path.join( __dirname, '..', '..' );
const OUT = path.join( REPO, 'out' );
const NAV = path.join( REPO, 'src', 'config', 'navigation.ts' );

if ( !fs.existsSync( OUT ) ) { console.error( 'out/ not found - run npm run build' ); process.exit( 2 ); }

/* ---------- emitted workspace routes ---------- */

function walk( dir, acc = [] ) {
  for ( const e of fs.readdirSync( dir, { withFileTypes: true } ) ) {
    const p = path.join( dir, e.name );
    if ( e.isDirectory() ) walk( p, acc );
    else if ( e.name === 'index.html' ) acc.push( p );
  }
  return acc;
}

const emitted = new Set(
  walk( path.join( OUT, 'workspace' ) ).map( f => {
    const r = '/' + path.relative( OUT, f ).split( path.sep ).join( '/' );
    return r.slice( 0, -'index.html'.length ).replace( /\/$/, '' );
  } )
);

/* ---------- paths declared in navigation.ts ---------- */

const src = fs.readFileSync( NAV, 'utf8' );
const declared = new Map(); // route (no query) -> Set(raw declaration)
const withQuery = [];

for ( const m of src.matchAll( /path:\s*'([^']+)'/g ) ) {
  const raw = m[ 1 ];
  if ( raw.includes( '?' ) ) withQuery.push( raw );
  const base = raw.split( '?' )[ 0 ].replace( /\/$/, '' );
  if ( !declared.has( base ) ) declared.set( base, new Set() );
  declared.get( base ).add( raw );
}

/* Labels, so a report line names the thing rather than only its path. */
const labelOf = new Map();
for ( const m of src.matchAll( /path:\s*'([^']+)'\s*,\s*label:\s*'([^']+)'/g ) ) {
  labelOf.set( m[ 1 ].split( '?' )[ 0 ].replace( /\/$/, '' ), m[ 2 ] );
}

/* ---------- compare ---------- */

const navMissing = [ ...declared.keys() ]
  .filter( r => r.startsWith( '/workspace' ) )
  .filter( r => !emitted.has( r ) )
  .sort();

const notInNav = [ ...emitted ]
  .filter( r => !declared.has( r ) )
  .sort();

/* A literal dynamic-route segment emitted as a real directory. */
const literalDynamic = [ ...emitted ].filter( r => r.includes( '[' ) ).sort();

/* ---------- report ---------- */

const h = s => console.log( `\n=== ${s} ===` );

h( 'COUNTS' );
console.log( `  workspace pages emitted      ${emitted.size}` );
console.log( `  distinct paths in navigation ${declared.size}  (${withQuery.length} of them query-string filters)` );

h( `NAV POINTS AT A PAGE THAT IS NOT BUILT (${navMissing.length})` );
if ( !navMissing.length ) console.log( '  none' );
for ( const r of navMissing ) console.log( `  ${r}${labelOf.has( r ) ? `   "${labelOf.get( r )}"` : ''}` );

h( `PAGE IS BUILT BUT ABSENT FROM navigation.ts (${notInNav.length})` );
if ( !notInNav.length ) console.log( '  none' );
for ( const r of notInNav ) console.log( `  ${r}` );

h( `LITERAL DYNAMIC SEGMENT SERVED AS A PAGE (${literalDynamic.length})` );
if ( !literalDynamic.length ) console.log( '  none' );
for ( const r of literalDynamic ) console.log( `  ${r}   <- a real 200 at a URL containing brackets` );

h( 'QUERY-STRING NAV ENTRIES (filters, not pages)' );
for ( const q of withQuery ) console.log( `  ${q}` );

const fail = navMissing.length + notInNav.length + literalDynamic.length;
console.log( `\n${fail ? `${fail} finding(s)` : 'ok: navigation and build agree'}` );
