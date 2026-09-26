#!/usr/bin/env node
/**
 * Generate the PUBLIC sitemap for www.wecare.digital from the static export.
 *
 * The repository contains many authenticated dashboard pages under the same
 * static export. They must never be emitted into the public sitemap.
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath( import.meta.url );
const __dirname = path.dirname( __filename );

const SITE_URL = 'https://wecare.digital';
const OUT_DIR = path.join( __dirname, '..', 'out' );
const OUTPUT_FILE = path.join( OUT_DIR, 'sitemap.xml' );

// EXPLICIT ALLOWLIST, deliberately - the export also contains the authenticated
// dashboard, so scanning for every index.html would leak those into a public sitemap.
// Anything added here must be a real public route AND in the isPublic allowlist in
// _app.tsx, or it will 200 with an empty body.
//
// /faq and /partners were removed: both pages were deleted on owner instruction, so
// those entries described URLs that no longer build. /terms and /privacy carry real
// published documents now and are indexable, so they belong here.
const PUBLIC_EXACT = new Set( [
  '/',
  '/bharat-rx',
  '/blog',
  '/contact',
  '/grahak-os',
  '/my-order',
  '/privacy',
  '/terms',
  '/vayulok',
  // The seven product pages. These must stay in step with PUBLIC_PAGE_META in _app.tsx:
  // a route missing there renders an empty body with HTTP 200, so advertising it here
  // without it there would put blank pages in front of a crawler.
  '/clear-closure',
  '/dastavez',
  '/elsewhere',
  '/expo-week',
  // Renamed '/swdhya' -> '/open-possibility' -> '/anew'. Alphabetical, so it moved to the
  // top of this group.
  '/anew',
  '/niji-setu',
  '/ritual-guru',
] );
const PUBLIC_PREFIXES = [ '/post/' ];

function normalizeRoute ( base ) {
  if ( !base ) return '/';
  const route = base.startsWith( '/' ) ? base : '/' + base;
  return route.replace( /\/+$/, '' ) || '/';
}

function isPublicRoute ( route ) {
  return PUBLIC_EXACT.has( route ) || PUBLIC_PREFIXES.some( prefix => route.startsWith( prefix ) );
}

function findHtmlFiles ( dir, base = '' ) {
  const urls = [];
  if ( !fs.existsSync( dir ) ) return urls;

  const entries = fs.readdirSync( dir, { withFileTypes: true } );
  for ( const entry of entries )
  {
    const fullPath = path.join( dir, entry.name );
    const urlPath = base + '/' + entry.name;

    if ( entry.isDirectory() )
    {
      if ( entry.name.startsWith( '_' ) || entry.name.startsWith( '.' ) || entry.name === 'node_modules' ) continue;
      urls.push( ...findHtmlFiles( fullPath, urlPath ) );
    }
    else if ( entry.name === 'index.html' )
    {
      const route = normalizeRoute( base );
      if ( isPublicRoute( route ) ) urls.push( route );
    }
  }
  return urls;
}

function generateSitemap ( routes ) {
  const today = new Date().toISOString().split( 'T' )[ 0 ];
  const unique = [ ...new Set( routes ) ].sort();
  const entries = unique.map( route => {
    const pathname = route === '/' ? '/' : route + '/';
    return `  <url>
    <loc>${SITE_URL}${pathname}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>${route.startsWith( '/post/' ) ? 'monthly' : 'weekly'}</changefreq>
    <priority>${route === '/' ? '1.0' : route === '/blog' ? '0.8' : '0.7'}</priority>
  </url>`;
  } ).join( '\n' );

  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${entries}
</urlset>`;
}

/**
 * Two consistency checks the allowlist cannot make on its own.
 *
 * 1. AN ALLOWLIST ENTRY THAT DOES NOT EXIST IN THE EXPORT IS DROPPED SILENTLY.
 *    findHtmlFiles only emits routes it actually finds, which is the safe direction —
 *    but it means renaming or deleting a public page leaves a dead entry here and the
 *    sitemap just gets quietly shorter. '/swdhya' -> '/open-possibility' -> '/anew'
 *    already happened once. Warn, do not fail: a legitimately removed page should not
 *    block a deploy, it should be noticed.
 *
 * 2. A URL CANNOT BE IN THE SITEMAP AND DISALLOWED IN robots.txt AT THE SAME TIME.
 *    That pair tells a crawler to index a page and not to fetch it, and Search Console
 *    reports it as "Indexed, though blocked by robots.txt". The dashboard lives in the
 *    same static export as the marketing pages and is held out of the index by robots
 *    alone, so a single wrong allowlist entry is all it takes to advertise an
 *    authenticated route. This one FAILS the build, because it can only be a mistake.
 */
function robotsDisallows () {
  // Next copies public/robots.txt into the export; prefer the built copy, since that is
  // what will actually be served.
  for ( const candidate of [ path.join( OUT_DIR, 'robots.txt' ),
                             path.join( __dirname, '..', 'public', 'robots.txt' ) ] )
  {
    if ( !fs.existsSync( candidate ) ) continue;
    return fs.readFileSync( candidate, 'utf-8' )
      .split( '\n' )
      .filter( line => /^\s*disallow\s*:/i.test( line ) )
      .map( line => line.split( ':' ).slice( 1 ).join( ':' ).trim() )
      .filter( Boolean );
  }
  return [];
}

const routes = findHtmlFiles( OUT_DIR );
const postRoutes = routes.filter( route => route.startsWith( '/post/' ) );

const missing = [ ...PUBLIC_EXACT ].filter( route => !routes.includes( route ) );
if ( missing.length > 0 )
{
  console.warn(
    `\nSITEMAP WARNING: ${missing.length} allowlisted route(s) were not found in the export:\n`
    + missing.map( route => `    ${route}` ).join( '\n' )
    + '\n  Either the page was removed (delete it from PUBLIC_EXACT) or the build did not\n'
    + '  emit it (which is the serious case, and silent until now).\n'
  );
}

const disallows = robotsDisallows();
const contradicted = routes
  .map( route => ( { route, pathname: route === '/' ? '/' : route + '/' } ) )
  .filter( ( { pathname } ) => disallows.some(
    rule => rule !== '/' && pathname.startsWith( rule )
  ) );
if ( contradicted.length > 0 )
{
  console.error(
    `\nSITEMAP REFUSED: ${contradicted.length} URL(s) are both allowlisted here and`
    + ' Disallowed in robots.txt:\n'
    + contradicted.map( ( { route, pathname } ) => `    ${route}  (blocked by a rule matching ${pathname})` ).join( '\n' )
    + '\n\n  A crawler told to index a page it may not fetch reports it as "Indexed,\n'
    + '  though blocked by robots.txt". Remove the route from PUBLIC_EXACT if it is\n'
    + '  authenticated, or remove the Disallow if it is genuinely public.\n'
  );
  process.exit( 1 );
}

/**
 * REFUSE to write a sitemap with no blog posts in it.
 *
 * Observed on 2026-09-24, twice in a row on this machine: one build emitted 125
 * URLs with 109 post pages, the next emitted 16 with none, from an unchanged
 * tree. The blog is not in the repository - `/post/[slug]` calls
 * listPublicBlogPosts() in getStaticPaths, which fetches
 * wecare.digital/api/seo-tools/blog-public at build time and, on ANY failure,
 * returns [] from a bare catch. So a two-second network blip produces zero blog
 * pages, an empty paths array, a 16-URL sitemap, and `next build` exiting 0.
 * Amplify would then deploy it and 109 live, indexed pages would vanish with no
 * error anywhere - and it would present later as an unexplained ranking drop
 * rather than as a failed build.
 *
 * The endpoint was verified healthy at the time (HTTP 200, 109 posts, ~2s, three
 * consecutive calls), and the live sitemap still had all 125, so nothing bad had
 * shipped. This guard is so that stays true.
 *
 * Checked here rather than by making listPublicBlogPosts() throw, because that
 * function also runs in the browser, where returning [] for an unreachable API is
 * the right behaviour - an empty blog list beats a crashed page. The build wants
 * the opposite. Asserting on the OUTCOME keeps both.
 *
 * Deliberately a floor of 1, not a percentage of some remembered total: the
 * failure mode is all-or-nothing, so 0 is the only value that is always wrong.
 * ALLOW_EMPTY_BLOG=1 exists for a genuinely offline build, and has to be typed on
 * purpose.
 */
if ( postRoutes.length === 0 && process.env.ALLOW_EMPTY_BLOG !== '1' )
{
  console.error(
    '\nSITEMAP REFUSED: 0 blog post pages were exported.\n' +
    `  public routes found: ${routes.length}\n` +
    '  /post/ pages found: 0\n\n' +
    '  getStaticPaths for /post/[slug] fetches the blog list at build time and\n' +
    '  swallows failures, so this is almost certainly a transient fetch error\n' +
    '  rather than an empty blog. Re-run the build. Confirm the API first with:\n' +
    '    curl -s https://wecare.digital/api/seo-tools/blog-public | head -c 200\n\n' +
    '  Writing this sitemap would drop every published post from the index.\n' +
    '  If the blog really is empty, set ALLOW_EMPTY_BLOG=1 deliberately.\n'
  );
  process.exit( 1 );
}

const sitemapXml = generateSitemap( routes );
fs.writeFileSync( OUTPUT_FILE, sitemapXml, 'utf-8' );
console.log(
  `Public sitemap: ${routes.length} URLs `
  + `(${postRoutes.length} blog posts) -> ${OUTPUT_FILE}`
);
