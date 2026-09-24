'use strict';

/**
 * Chromium resolution for the browser harness.
 *
 * NEVER HARDCODE THE REVISION. This sandbox ships Chromium under
 * /opt/playwright/chromium-<rev>/, not the ~/.cache/ms-playwright path Playwright
 * looks in by default, AND THE REVISION CHANGES ACROSS SANDBOX RESETS. Harnesses
 * pinned to `chromium-1243` all died with "executable doesn't exist" on a box that
 * had `chromium-1232` sitting right there. That failure reads like a broken harness
 * rather than a relocated browser, and it cost a full debugging round - which is the
 * entire reason this file exists instead of a string literal at each call site.
 *
 * We depend on playwright-core, not playwright, on purpose: playwright-core never
 * tries to download a browser. It drives whatever binary it is handed via
 * executablePath, which is exactly the arrangement we want when the binary is
 * already on disk and its revision is not ours to choose.
 *
 * Resolution order, first hit wins:
 *   1. CHROME env var          - explicit override, always respected
 *   2. /opt/playwright         - this sandbox, highest chromium-* revision
 *   3. ~/.cache/ms-playwright  - a normal Playwright install
 *   4. system chrome/chromium  - a developer laptop
 *
 * On total failure it THROWS naming every path it searched. It must never return
 * undefined: launch() would then report a misleading "executable doesn't exist" for
 * a path nobody chose, which is the confusing failure this module is built to avoid.
 */

const fs = require( 'fs' );
const os = require( 'os' );
const path = require( 'path' );

/**
 * Chromium dirs expose the binary at one of two relative paths depending on build
 * flavour. chrome-linux64 is the current layout; chrome-linux is the older one. The
 * headless_shell builds are accepted too but ranked below a full chrome, because a
 * headless shell cannot report layout for anything that needs a real compositor.
 */
const BINARY_SUBPATHS = [
  path.join( 'chrome-linux64', 'chrome' ),
  path.join( 'chrome-linux', 'chrome' ),
  path.join( 'chrome-linux64', 'headless_shell' ),
  path.join( 'chrome-linux', 'headless_shell' ),
];

const SYSTEM_CANDIDATES = [
  '/usr/bin/google-chrome',
  '/usr/bin/chromium-browser',
  '/usr/bin/chromium',
  '/snap/bin/chromium',
];

function isExecutableFile( p ) {
  try {
    if ( !fs.statSync( p ).isFile() ) return false;
    fs.accessSync( p, fs.constants.X_OK );
    return true;
  } catch {
    return false;
  }
}

/**
 * Highest-numbered chromium-* under a root. Sorted NUMERICALLY, not
 * lexicographically: a string sort puts "chromium-999" above "chromium-1232", which
 * would pick a stale build on any box that happened to hold both.
 */
function scanRevisionRoot( root, searched ) {
  searched.push( root );
  let entries;
  try {
    entries = fs.readdirSync( root );
  } catch {
    return null;
  }

  const revisions = entries
    .map( name => {
      const m = /^chromium(?:_headless_shell)?-(\d+)$/.exec( name );
      return m ? { name, rev: Number( m[ 1 ] ), headless: name.includes( 'headless_shell' ) } : null;
    } )
    .filter( Boolean )
    // Prefer a full chrome over a headless shell at the same revision, then newest first.
    .sort( ( a, b ) => ( b.rev - a.rev ) || ( Number( a.headless ) - Number( b.headless ) ) );

  for ( const { name } of revisions ) {
    for ( const sub of BINARY_SUBPATHS ) {
      const candidate = path.join( root, name, sub );
      if ( isExecutableFile( candidate ) ) return candidate;
    }
  }
  return null;
}

function resolveChrome() {
  const searched = [];

  if ( process.env.CHROME ) {
    searched.push( `$CHROME=${process.env.CHROME}` );
    if ( isExecutableFile( process.env.CHROME ) ) return process.env.CHROME;
  }

  for ( const root of [ '/opt/playwright', path.join( os.homedir(), '.cache', 'ms-playwright' ) ] ) {
    const found = scanRevisionRoot( root, searched );
    if ( found ) return found;
  }

  for ( const candidate of SYSTEM_CANDIDATES ) {
    searched.push( candidate );
    if ( isExecutableFile( candidate ) ) return candidate;
  }

  throw new Error(
    'No Chromium executable found. Searched:\n  ' + searched.join( '\n  ' ) +
    '\nSet CHROME=/path/to/chrome, or install one with:\n' +
    '  cd tools/browser && npx playwright install chromium'
  );
}

/** Launch a headless Chromium. Callers own closing it. */
async function launch( opts = {} ) {
  const { chromium } = require( 'playwright-core' );
  return chromium.launch( {
    executablePath: resolveChrome(),
    // --no-sandbox: this container runs as root, where Chromium's setuid sandbox
    // refuses to start at all. --disable-dev-shm-usage: /dev/shm is small here and
    // the renderer crashes on larger pages without it.
    args: [ '--no-sandbox', '--disable-dev-shm-usage' ],
    ...opts,
  } );
}

module.exports = { resolveChrome, launch };
