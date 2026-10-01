import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * THE UNKNOWN-PATH FALLBACK MUST NEVER FORWARD THE PATH IT RESCUED THE VISITOR FROM.
 *
 * `src/pages/404.tsx` needed NO change - it was read and verified against live HTTP on
 * 2026-10-01 and is already correct. This file pins that behaviour so a later edit cannot
 * quietly start forwarding untrusted input, which is the realistic regression: a fallback
 * page is exactly where somebody later thinks "it would be nicer to send them to the path
 * they asked for" and builds `router.replace( \`/${something}\` )`.
 *
 * HOW THE LIVE SURFACE IS LAYERED, because the two halves get confused. The Amplify
 * catch-all rule is `/<*>` -> `/404.html` at status `404-200`: an unknown path stays at the
 * URL the visitor typed and returns HTTP 404 with this document's body. The `router.replace`
 * below is the client-side second half that moves them to home. So this page is the ONLY
 * thing that decides where a mistyped URL lands, and the status code is not ours to assert
 * from here.
 *
 * READS SOURCE AS TEXT rather than rendering. The assertions are about the LITERAL in the
 * source - that the argument is `'/'` and not a template or a variable - and rendering
 * cannot distinguish those: a mounted component that happens to replace with '/' on this
 * input would pass while still being capable of forwarding a different one. It is the same
 * technique src/test/PublicRouteRegistration.test.ts uses, and for the stronger reason here.
 */

const SOURCE = fs.readFileSync(
  path.join( process.cwd(), 'src', 'pages', '404.tsx' ),
  'utf8'
);

describe( 'the 404 fallback redirects to a literal home', () => {
  it( 'calls router.replace with a single-quoted literal /', () => {
    expect( SOURCE ).toMatch( /router\.replace\(\s*'\/'\s*\)/ );
  } );

  it( 'never passes a template literal or a variable to router.replace', () => {
    /*
     * The whole point of the test. A backtick argument can interpolate, and a bare
     * identifier can hold anything - either would let the requested path, its query or its
     * fragment reach the navigation. Collected and reported rather than asserted one at a
     * time so the failure message names the offending call.
     */
    const calls = Array.from( SOURCE.matchAll( /router\.replace\(\s*([^)]*)\)/g ) )
      .map( m => m[ 1 ].trim() );

    expect( calls.length, 'no router.replace call found - this guard needs updating' )
      .toBeGreaterThan( 0 );

    const unsafe = calls.filter( arg => arg !== "'/'" );
    expect(
      unsafe,
      'router.replace on the 404 page must take the literal \'/\'. A template literal or a '
      + 'variable can forward the path, query or fragment the visitor was rescued from, which '
      + 'turns the fallback into an open redirect reachable from any unknown URL.'
    ).toEqual( [] );
  } );

  it( 'uses replace rather than push, so the dead URL leaves no history entry', () => {
    // push would let the back button return the visitor to the dead URL and bounce them
    // forward again. The page records this itself; asserted so it survives an edit.
    expect( SOURCE ).not.toMatch( /router\.push\(/ );
  } );
} );

describe( 'the 404 fallback is never indexed and never canonical', () => {
  it( 'declares noindex, follow', () => {
    // follow, not nofollow: the page is a waypoint, and the one link on it leads back into
    // the site, so there is no reason to stop a crawler using it.
    expect( SOURCE ).toContain( '<meta name="robots" content="noindex, follow" />' );
  } );

  it( 'points its canonical at the destination, not at the dead URL', () => {
    // _app.tsx computes a canonical from the current path. Left alone, that would publish a
    // canonical for every mistyped URL. next/head dedupes by key, so the key="canonical"
    // here is what overrides it - drop the key and the override silently stops working.
    expect( SOURCE ).toContain( 'rel="canonical"' );
    expect( SOURCE ).toContain( 'key="canonical"' );
    expect( SOURCE ).toContain( 'href="https://wecare.digital/"' );
  } );

  it( 'keeps a no-JavaScript escape route to home', () => {
    // The redirect needs a tick of JavaScript and never runs without it, so the markup is
    // the fallback: a real anchor to '/', not a message about being redirected. A full
    // document load is correct here for the same reason ErrorBoundary uses one.
    expect( SOURCE ).toMatch( /<a[^>]*href="\/"/ );
  } );
} );
