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

const PUBLIC_EXACT = new Set( [
  '/',
  '/blog',
  '/faq',
  '/grahak-os',
  '/partners',
  '/vayulok',
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
const sitemapXml = generateSitemap( routes );
fs.writeFileSync( OUTPUT_FILE, sitemapXml, 'utf-8' );
console.log( `Public sitemap: ${routes.length} URLs -> ${OUTPUT_FILE}` );
