'use strict';

/**
 * blogcheck - after splitting one 834-post page into 35, is every post still listed?
 *
 * WHY THIS IS THE CHECK THAT MATTERS. /blog/ used to be a single document containing every
 * published post, so "is every post linked?" was true by construction and needed no test. The
 * split made it a property of arithmetic - a page size, a slice offset, a getStaticPaths range
 * - and arithmetic can be off by one silently. A post that falls between page 12 and page 13
 * is still at its own URL, still in the sitemap, and reachable from nothing. Nobody would
 * notice from looking at the pages, because each one is 24 cards whether it is the right 24 or
 * not.
 *
 * So this reads the EXPORT, not the source, and reconciles four numbers that must agree:
 *
 *   1. every /post/ page emitted            <- the corpus
 *   2. every post linked from an index page  <- what a reader and a crawler can find
 *   3. every post in the sitemap             <- what is advertised
 *   4. every post in search-index.json       <- what search can return
 *
 * ONE INDEX PAGE PER POST, EXACTLY. Listed twice means two pages show the same card, which is
 * a slice overlap; listed zero times means it is lost. Both are reported with the slug, not a
 * count, because a count tells you something is wrong and a slug tells you where.
 *
 * Run: node tools/audit/blogcheck.js        (needs out/ - npm run build)
 */

const fs = require( 'fs' );
const path = require( 'path' );

const REPO = path.join( __dirname, '..', '..' );
const OUT = path.join( REPO, 'out' );

if ( !fs.existsSync( OUT ) ) { console.error( 'out/ not found - run npm run build' ); process.exit( 2 ); }

const results = [];
const ok = ( name, detail ) => results.push( { pass: true, name, detail } );
const bad = ( name, detail ) => results.push( { pass: false, name, detail } );
const note = ( name, detail ) => results.push( { note: true, name, detail } );

/* ---------- the corpus: every emitted /post/ page ---------- */

const postDir = path.join( OUT, 'post' );
const emittedPosts = fs.existsSync( postDir )
  ? fs.readdirSync( postDir, { withFileTypes: true } )
    .filter( e => e.isDirectory() && fs.existsSync( path.join( postDir, e.name, 'index.html' ) ) )
    .map( e => e.name )
  : [];

/* ---------- the index pages: /blog/ plus /blog/page/N ---------- */

const indexPages = [ { label: '/blog/', file: path.join( OUT, 'blog', 'index.html' ) } ];
const pageRoot = path.join( OUT, 'blog', 'page' );
if ( fs.existsSync( pageRoot ) ) {
  for ( const entry of fs.readdirSync( pageRoot ) ) {
    const file = path.join( pageRoot, entry, 'index.html' );
    if ( fs.existsSync( file ) ) indexPages.push( { label: `/blog/page/${entry}/`, file, n: Number( entry ) } );
  }
}
indexPages.sort( ( a, b ) => ( a.n || 1 ) - ( b.n || 1 ) );

/*
 * Slugs linked from each index page, read from the CARD MARKUP only.
 *
 * Scoped to href="/post/<slug>/" inside the rendered HTML, which on these pages appears only
 * in a card heading - but __NEXT_DATA__ also carries every slug in this page's props, and a
 * naive whole-file scan would count those too and report every page as listing its own 24
 * twice. Matching the href attribute rather than the bare string is what separates the two.
 */
const linkedBy = new Map(); // slug -> [page label]
for ( const page of indexPages ) {
  const html = fs.readFileSync( page.file, 'utf8' );
  const seen = new Set();
  for ( const m of html.matchAll( /href="\/post\/([^"/]+)\/?"/g ) ) seen.add( m[ 1 ] );
  for ( const slug of seen ) {
    if ( !linkedBy.has( slug ) ) linkedBy.set( slug, [] );
    linkedBy.get( slug ).push( page.label );
  }
  note( `${page.label} lists`, `${seen.size} post(s)` );
}

/* ---------- sitemap and search index ---------- */

const sitemapPath = path.join( OUT, 'sitemap.xml' );
const sitemap = fs.existsSync( sitemapPath ) ? fs.readFileSync( sitemapPath, 'utf8' ) : '';
const sitemapPosts = new Set( [ ...sitemap.matchAll( /\/post\/([^<\/]+)\//g ) ].map( m => m[ 1 ] ) );
const sitemapIndexPages = [ ...sitemap.matchAll( /\/blog\/page\/(\d+)\//g ) ].map( m => Number( m[ 1 ] ) );

const searchPath = path.join( OUT, 'blog', 'search-index.json' );
let searchSlugs = new Set();
let searchKb = 0;
if ( fs.existsSync( searchPath ) ) {
  searchKb = Math.round( fs.statSync( searchPath ).size / 1024 );
  try {
    const body = JSON.parse( fs.readFileSync( searchPath, 'utf8' ) );
    searchSlugs = new Set( ( body.posts || [] ).map( p => p.slug ) );
  } catch { /* reported below as a shape failure */ }
}

/* ---------- reconcile ---------- */

note( 'posts emitted', String( emittedPosts.length ) );
note( 'index pages emitted', `${indexPages.length} (1 + ${indexPages.length - 1})` );

const unlisted = emittedPosts.filter( s => !linkedBy.has( s ) );
const listedTwice = [ ...linkedBy.entries() ].filter( ( [ , pages ] ) => pages.length > 1 );
const listedButNotEmitted = [ ...linkedBy.keys() ].filter( s => !emittedPosts.includes( s ) );

if ( unlisted.length === 0 ) ok( 'every post is listed on an index page', `all ${emittedPosts.length}` );
else bad( 'every post is listed on an index page', `${unlisted.length} unreachable: ${unlisted.slice( 0, 5 ).join( ', ' )}${unlisted.length > 5 ? ' …' : ''}` );

if ( listedTwice.length === 0 ) ok( 'no post is listed on two index pages', 'no slice overlap' );
else bad( 'no post is listed on two index pages', listedTwice.slice( 0, 4 ).map( ( [ s, p ] ) => `${s} on ${p.join( ' + ' )}` ).join( '; ' ) );

if ( listedButNotEmitted.length === 0 ) ok( 'no index page links a post that was not built', 'none' );
else bad( 'no index page links a post that was not built', listedButNotEmitted.slice( 0, 5 ).join( ', ' ) );

/* Sitemap: the posts AND the index pages. Before the split there was one index URL to
 * advertise; now 810 of 834 posts are listed only on pages 2-35, so those pages being in the
 * sitemap is what keeps most of the corpus crawlable. */
const missingFromSitemap = emittedPosts.filter( s => !sitemapPosts.has( s ) );
if ( missingFromSitemap.length === 0 ) ok( 'every post is in the sitemap', `${sitemapPosts.size} post URLs` );
else bad( 'every post is in the sitemap', `${missingFromSitemap.length} missing` );

const expectedIndexPages = indexPages.filter( p => p.n ).map( p => p.n ).sort( ( a, b ) => a - b );
const missingIndexPages = expectedIndexPages.filter( n => !sitemapIndexPages.includes( n ) );
if ( missingIndexPages.length === 0 ) ok( 'every paginated index page is in the sitemap', `pages 2-${Math.max( ...expectedIndexPages, 1 )}` );
else bad( 'every paginated index page is in the sitemap', `missing: ${missingIndexPages.join( ', ' )}` );

/* Page 1 must NOT be advertised twice. /blog/page/1/ would be the same 24 cards at a second
 * self-canonical URL. */
if ( !sitemapIndexPages.includes( 1 ) && !fs.existsSync( path.join( pageRoot, '1' ) ) ) {
  ok( 'page 1 exists only at /blog/', 'no /blog/page/1/ emitted or advertised' );
} else {
  bad( 'page 1 exists only at /blog/', '/blog/page/1/ is a duplicate of /blog/' );
}

/* Search index: it is the ONLY thing that can still search the whole corpus. */
if ( searchSlugs.size === 0 ) {
  bad( 'search index covers the corpus', 'missing or empty - search would fall back to one page' );
} else {
  const missingFromSearch = emittedPosts.filter( s => !searchSlugs.has( s ) );
  if ( missingFromSearch.length === 0 ) ok( 'search index covers every post', `${searchSlugs.size} posts, ${searchKb} kB` );
  else bad( 'search index covers every post', `${missingFromSearch.length} not searchable` );
}

/*
 * THE PAYLOAD CEILING, which is the defect this whole split was for. Next warns above 128 kB
 * and /blog/ measured 842 kB. Asserted rather than printed: a later change that widened
 * BlogCard back out would put it straight back over, and the build warning is easy to scroll
 * past.
 */
for ( const page of indexPages.slice( 0, 2 ) ) {
  const html = fs.readFileSync( page.file, 'utf8' );
  const m = html.match( /<script id="__NEXT_DATA__"[^>]*>([\s\S]*?)<\/script>/ );
  const kb = Math.round( ( m ? m[ 1 ].length : 0 ) / 1024 );
  if ( kb < 128 ) ok( `${page.label} props under Next's 128 kB warning`, `${kb} kB` );
  else bad( `${page.label} props under Next's 128 kB warning`, `${kb} kB - the warning is back` );
}

/* ---------- report ---------- */

console.log( '' );
for ( const r of results ) {
  const tag = r.note ? 'note' : r.pass ? 'ok  ' : 'FAIL';
  // Only the first two and last two "lists" notes, or 35 lines of them bury the assertions.
  if ( r.note && / lists$/.test( r.name ) ) continue;
  console.log( `  ${tag}  ${r.name.padEnd( 48 )} ${r.detail}` );
}
const perPage = results.filter( r => r.note && / lists$/.test( r.name ) );
if ( perPage.length ) {
  const counts = perPage.map( r => parseInt( r.detail, 10 ) );
  console.log( `  note  ${'cards per index page'.padEnd( 48 )} ${Math.min( ...counts )}-${Math.max( ...counts )} across ${perPage.length} pages, ${counts.reduce( ( a, c ) => a + c, 0 )} total` );
}

const fails = results.filter( r => r.pass === false ).length;
const oks = results.filter( r => r.pass === true ).length;
console.log( `\n${oks} ok, ${fails} FAIL\n` );
process.exit( fails ? 1 : 0 );
