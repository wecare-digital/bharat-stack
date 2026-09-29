/**
 * `safeHttpHref` decides whether an operator-typed string reaches an `href`.
 *
 * WHY THESE CASES AND NOT A HAPPY PATH. The predicate this replaced passed its own review
 * and still had two defects, both of which are asserted below:
 *
 *   1. It parsed with a base of `https://wecare.digital`, so the URL parser *resolved*
 *      relative input rather than rejecting it, and `//evil.com` came back as
 *      `https://evil.com` — accepted, while the docstring stated that a bare `//host` was
 *      rejected. A test asserting only that `javascript:` is blocked would have passed.
 *   2. It returned a boolean, so the caller checked one string and rendered another (the
 *      raw input). Returning the value to render is what closes that gap, so the tests
 *      assert the returned string, not just truthiness.
 *
 * The scheme cases are the security-relevant ones: an `href` is an execution context for
 * `javascript:` and `data:`, which is what `js/xss-through-dom` flagged on `calling.tsx`.
 */
import { describe, expect, it } from 'vitest';

import { safeHttpHref } from '../lib/randomToken';

describe( 'safeHttpHref — schemes that must never reach an href', () => {
  // Each of these executes or renders when placed in href and clicked.
  it.each( [
    'javascript:alert(1)',
    'JavaScript:alert(1)',
    'javascript:void(document.cookie)',
    'data:text/html,<script>alert(1)</script>',
    'vbscript:msgbox(1)',
    'file:///etc/passwd',
    'blob:https://wecare.digital/1234',
  ] )( 'rejects %s', ( input ) => {
    expect( safeHttpHref( input ) ).toBeNull();
  } );

  it( 'rejects a scheme hidden behind characters a browser strips from a URL', () => {
    // Browsers remove tab and newline before resolving the scheme, so these are live
    // `javascript:` URLs to a browser. The URL parser removes them too, which is why the
    // protocol check still sees them.
    expect( safeHttpHref( 'java\tscript:alert(1)' ) ).toBeNull();
    expect( safeHttpHref( 'java\nscript:alert(1)' ) ).toBeNull();
    expect( safeHttpHref( '  javascript:alert(1)' ) ).toBeNull();
  } );
} );

describe( 'safeHttpHref — relative input is rejected, not resolved', () => {
  it( 'rejects a protocol-relative host, which the previous version accepted', () => {
    // The regression this exists for. With a base URL in the parse, `//evil.com` resolved
    // to `https://evil.com` and passed.
    expect( safeHttpHref( '//evil.com' ) ).toBeNull();
    expect( safeHttpHref( '//evil.com/payload.mp3' ) ).toBeNull();
  } );

  it( 'rejects a site-relative path', () => {
    // Correct for this field specifically: the IVR URL is fetched by a telephony
    // provider, so a path with no host was never usable.
    expect( safeHttpHref( '/audio/welcome.sln16' ) ).toBeNull();
    expect( safeHttpHref( 'welcome.sln16' ) ).toBeNull();
  } );

  it( 'rejects empty and non-string input without throwing', () => {
    expect( safeHttpHref( '' ) ).toBeNull();
    expect( safeHttpHref( undefined as unknown as string ) ).toBeNull();
    expect( safeHttpHref( null as unknown as string ) ).toBeNull();
    expect( safeHttpHref( 42 as unknown as string ) ).toBeNull();
  } );
} );

describe( 'safeHttpHref — accepted URLs come back usable', () => {
  it( 'returns the production default unchanged', () => {
    const live = 'https://wecare.digital/get/o/stream/media/ivr/incoming_welcome.sln16';
    expect( safeHttpHref( live ) ).toBe( live );
  } );

  it( 'accepts http as well as https', () => {
    expect( safeHttpHref( 'http://example.com/a.mp3' ) ).toBe( 'http://example.com/a.mp3' );
  } );

  it( 'preserves port, query and fragment', () => {
    expect( safeHttpHref( 'https://example.com:8443/a.mp3?v=2#t=1' ) )
      .toBe( 'https://example.com:8443/a.mp3?v=2#t=1' );
  } );

  it( 'loses nothing against the parser\'s own serialisation', () => {
    // The scheme is re-emitted as a literal rather than sliced out of the input, so this
    // asserts the rebuild is byte-identical to `href` and not merely close to it.
    for ( const input of [
      'https://example.com',
      'http://user:pw@example.com:81/p/q?a=1&b=2#f',
      'https://example.com/a%20b',
      'https://example.com/a b',
      'HTTPS://Example.COM/A',
    ] ) {
      expect( safeHttpHref( input ) ).toBe( new URL( input ).href );
    }
  } );
} );
