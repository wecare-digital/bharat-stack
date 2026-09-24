'use strict';

/**
 * The target under test - a static server over out/, or an origin you already have.
 *
 * WHY DUAL MODE. next.config.js only sets output:'export' when NODE_ENV is
 * production, so `out/` is pre-generated HTML while `next dev` is a live server that
 * compiles per route. Those are two different renders, and a suite that only ever ran
 * against `out/` has not tested what a developer sees locally. Every harness here
 * takes its origin from target() so the same assertions run against either:
 *
 *   node animcheck.js            # against out/ (the production export)
 *   BASE=http://localhost:3000 node animcheck.js
 *
 * With no BASE it boots its own server - background servers are blocked in this
 * sandbox, so each run owns one and closes it. With BASE set it starts nothing.
 *
 * TRAILING SLASH. next.config.js sets trailingSlash:true, so the export writes
 * out/contact/index.html and the canonical URL is /contact/. A request for /contact
 * would 404 against a naive static server, and a harness would report a blank page
 * rather than a routing detail. This resolves both spellings.
 */

const fs = require( 'fs' );
const http = require( 'http' );
const path = require( 'path' );

const OUT_DIR = path.resolve( __dirname, '..', '..', '..', 'out' );

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.txt': 'text/plain; charset=utf-8',
  '.xml': 'application/xml; charset=utf-8',
  '.map': 'application/json; charset=utf-8',
};

/**
 * Candidate files for a URL path, in order. The bare-path -> /index.html step is the
 * trailingSlash accommodation; the plain file step is what serves /_next assets.
 */
function candidates( urlPath ) {
  const clean = urlPath.replace( /\/+$/, '' );
  const list = [];
  if ( clean === '' ) {
    list.push( path.join( OUT_DIR, 'index.html' ) );
  } else {
    list.push( path.join( OUT_DIR, clean ) );
    list.push( path.join( OUT_DIR, clean, 'index.html' ) );
    list.push( path.join( OUT_DIR, `${clean}.html` ) );
  }
  return list;
}

function serveFile( res, file ) {
  const body = fs.readFileSync( file );
  res.writeHead( 200, {
    'content-type': MIME[ path.extname( file ).toLowerCase() ] || 'application/octet-stream',
    'content-length': body.length,
    // The export is immutable per build and these runs are short; caching only
    // hides edits between a rebuild and a re-measure.
    'cache-control': 'no-store',
  } );
  res.end( body );
}

function createServer() {
  return http.createServer( ( req, res ) => {
    let urlPath;
    try {
      urlPath = decodeURIComponent( new URL( req.url, 'http://localhost' ).pathname );
    } catch {
      res.writeHead( 400 ); res.end( 'bad url' ); return;
    }

    // Containment check before any read: a harness server still must not serve
    // paths that escape out/ via ../ segments.
    for ( const file of candidates( urlPath ) ) {
      const resolved = path.resolve( file );
      if ( resolved !== OUT_DIR && !resolved.startsWith( OUT_DIR + path.sep ) ) continue;
      try {
        if ( fs.statSync( resolved ).isFile() ) { serveFile( res, resolved ); return; }
      } catch { /* try the next candidate */ }
    }

    // Serve the exported 404 page so a wrong path still renders something a harness
    // can assert on, while keeping the status honest.
    const notFound = path.join( OUT_DIR, '404.html' );
    if ( fs.existsSync( notFound ) ) {
      const body = fs.readFileSync( notFound );
      res.writeHead( 404, { 'content-type': MIME[ '.html' ], 'content-length': body.length } );
      res.end( body );
      return;
    }
    res.writeHead( 404 ); res.end( 'not found' );
  } );
}

/**
 * Resolve the origin to test.
 * @returns {Promise<{ base: string, mode: 'BASE'|'out', close: () => Promise<void> }>}
 */
async function target() {
  if ( process.env.BASE ) {
    const base = process.env.BASE.replace( /\/+$/, '' );
    return { base, mode: 'BASE', close: async () => {} };
  }

  if ( !fs.existsSync( OUT_DIR ) ) {
    throw new Error(
      `No export found at ${OUT_DIR}.\nRun \`npm run build\` first, or point the ` +
      'harness at a running dev server with BASE=http://localhost:3000'
    );
  }

  const server = createServer();
  // Port 0 lets the OS pick a free port. A fixed port collides with a dev server
  // that is already running, and the collision surfaces as a harness timeout.
  await new Promise( ( resolve, reject ) => {
    server.once( 'error', reject );
    server.listen( 0, '127.0.0.1', resolve );
  } );

  const { port } = server.address();
  return {
    base: `http://127.0.0.1:${port}`,
    mode: 'out',
    close: () => new Promise( resolve => server.close( () => resolve() ) ),
  };
}

module.exports = { target, OUT_DIR };
