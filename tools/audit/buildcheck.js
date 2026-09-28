'use strict';

/**
 * buildcheck - did the build actually produce what it is supposed to produce?
 *
 * WHY THIS EXISTS. A build failure was hidden for several commits by this idiom:
 *
 *     npm run build 2>&1 | grep -ciE "^error"      -> printed 0, looked fine
 *
 * The build had failed at the sitemap step. grep counted lines matching a pattern the failure did
 * not happen to match, printed 0, and 0 reads as "no errors". Worse, the pipe discards the exit
 * code: `cmd | grep` reports grep's status, not the build's, so even a hard failure exits 0.
 * `seocheck` eventually caught it with "could not read sitemap.xml", several steps later.
 *
 * COUNTING ERROR LINES IS NOT A BUILD CHECK. The artefacts existing is. This asserts the things a
 * successful build must leave behind, so a missing one fails loudly and immediately instead of
 * surfacing three tools later as something that looks unrelated.
 *
 * Run AFTER npm run build:
 *   npm run build && node tools/audit/buildcheck.js
 * Never `npm run build | grep ...`.
 */

const fs = require( 'fs' );
const path = require( 'path' );

const OUT = path.join( __dirname, '..', '..', 'out' );

const results = [];
const ok = ( name, detail ) => results.push( { pass: true, name, detail } );
const bad = ( name, detail ) => results.push( { pass: false, name, detail } );
const note = ( name, detail ) => results.push( { note: true, name, detail } );

if ( !fs.existsSync( OUT ) ) {
  console.error( '\n  FAIL  out/ does not exist - the build did not run or did not finish.\n' );
  process.exit( 1 );
}

/** Files a finished build must have written. */
const REQUIRED = [
  [ 'index.html', 'the home page' ],
  [ 'sitemap.xml', 'written by scripts/generate-sitemap.js - the step that failed silently' ],
  [ 'robots.txt', 'written alongside the sitemap' ],
  [ '404.html', 'the public 404' ],
  [ path.join( 'blog', 'index.html' ), 'blog page 1' ],
  [ path.join( 'blog', 'search-index.json' ), 'written by scripts/generate-blog-search-index.js' ],
];

for ( const [ rel, why ] of REQUIRED ) {
  const file = path.join( OUT, rel );
  if ( !fs.existsSync( file ) ) {
    bad( rel, `MISSING - ${why}` );
  } else {
    const size = fs.statSync( file ).size;
    if ( size === 0 ) bad( rel, `0 bytes - ${why}` );
    else ok( rel, `${size >= 1024 ? Math.round( size / 1024 ) + ' kB' : size + ' B'}` );
  }
}

/* ---------- the sitemap is the artefact that went missing, so it gets a real assertion ---------- */

const sitemapPath = path.join( OUT, 'sitemap.xml' );
if ( fs.existsSync( sitemapPath ) ) {
  const xml = fs.readFileSync( sitemapPath, 'utf8' );
  const urls = ( xml.match( /<loc>/g ) || [] ).length;
  const posts = ( xml.match( /<loc>[^<]*\/post\//g ) || [] ).length;
  /*
   * A FLOOR, NOT AN EXACT COUNT. generate-sitemap.js already refuses to write a sitemap with zero
   * posts, because a two-second network blip once produced one. This catches the subtler version:
   * a sitemap that wrote but lost most of the corpus. 100 is well under the ~864 live posts and
   * well over anything a partial fetch would produce.
   */
  if ( urls >= 20 ) ok( 'sitemap has URLs', `${urls} total` );
  else bad( 'sitemap has URLs', `only ${urls} - a public sitemap this small means the route scan failed` );

  if ( posts >= 100 ) ok( 'sitemap has the blog corpus', `${posts} post URLs` );
  else bad( 'sitemap has the blog corpus', `only ${posts} post URLs - the blog API likely returned a partial list` );
}

/* ---------- a literal dynamic segment means a getStaticPaths is missing ---------- */

const brackets = [];
( function walk( dir ) {
  for ( const entry of fs.readdirSync( dir, { withFileTypes: true } ) ) {
    if ( entry.name.includes( '[' ) ) brackets.push( path.relative( OUT, path.join( dir, entry.name ) ) );
    if ( entry.isDirectory() ) walk( path.join( dir, entry.name ) );
  }
} )( OUT );

if ( brackets.length === 0 ) {
  ok( 'no literal [param] in the export', 'every dynamic route was prerendered' );
} else {
  /* This shipped once: /workspace/seo/page/[id] served HTTP 200 at %5Bid%5D while every real id
   * 404'd on reload, because the route had no getStaticPaths. */
  bad( 'no literal [param] in the export', `${brackets.length} found: ${brackets.slice( 0, 3 ).join( ', ' )} - a dynamic route is missing getStaticPaths` );
}

/* ---------- Next's own payload warning, asserted rather than scrolled past ---------- */

const payloadPages = [ [ 'index.html', '/' ], [ path.join( 'blog', 'index.html' ), '/blog/' ] ];
for ( const [ rel, label ] of payloadPages ) {
  const file = path.join( OUT, rel );
  if ( !fs.existsSync( file ) ) continue;
  const html = fs.readFileSync( file, 'utf8' );
  const m = html.match( /<script id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/ );
  const kb = Math.round( ( m ? m[ 1 ].length : 0 ) / 1024 );
  /* /blog/ was 842 kB against Next's 128 kB threshold and the warning was printed on every build
   * for weeks. A warning nobody fails on is a warning nobody reads. */
  if ( kb < 128 ) ok( `${label} props under Next's 128 kB threshold`, `${kb} kB` );
  else bad( `${label} props under Next's 128 kB threshold`, `${kb} kB - Next prints a warning for this and it is easy to scroll past` );
}

note( 'how to run this', 'npm run build && node tools/audit/buildcheck.js  (never pipe the build through grep)' );

console.log( '' );
for ( const r of results ) {
  const tag = r.note ? 'note' : r.pass ? 'ok  ' : 'FAIL';
  console.log( `  ${tag}  ${r.name.padEnd( 44 )} ${r.detail}` );
}
const fails = results.filter( r => r.pass === false ).length;
console.log( fails ? `\n${fails} FAIL - the build did not produce a complete export\n` : '\nok: the export is complete\n' );
process.exit( fails ? 1 : 0 );
