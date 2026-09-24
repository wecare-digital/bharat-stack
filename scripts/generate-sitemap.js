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

const routes = findHtmlFiles( OUT_DIR );
const postRoutes = routes.filter( route => route.startsWith( '/post/' ) );

/**
 * REFUSE to write a sitemap with no blog posts in it.
 *
 * Observed on 2026-09-24, twice in a row on this machine: one build emitted 125
 * URLs with 109 post pages, the next emitted 16 with none, from an unchanged
 * tree. The blog is not in the repository - `/post/[slug]` calls
 * listPublicBlogPosts() in getStaticPaths, which fetches
 * api.wecare.digital/seo-tools/blog-public at build time and, on ANY failure,
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
    '    curl -s https://api.wecare.digital/seo-tools/blog-public | head -c 200\n\n' +
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
