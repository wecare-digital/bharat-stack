/**
 * `safeLocalReturnPath` decides where a customer lands after signing in.
 *
 * WHY THESE CASES AND NOT A HAPPY PATH. The regex this module replaces
 * (`src/pages/account/sign-in.tsx`, measured 2026-10-01) passed review while accepting two
 * values that matter, and both are asserted below as named cases rather than folded into a
 * list, so a future loosening names its own victim in the failure output:
 *
 *   - `'//evil'`           protocol-relative; the browser reads `evil` as a HOST, so a
 *                          "local path" check hands the visitor to another origin. Note
 *                          that `'//evil.example'` was rejected by the old regex ONLY
 *                          because `.` was missing from its character class — a
 *                          single-label host needs no dot, so the protection was an
 *                          accident of punctuation.
 *   - `'/workspace/access'` a well-formed local path, and the STAFF Cognito login. No
 *                          character class can express "not that destination"; only an
 *                          allowlist can.
 *
 * Every rejected case asserts the RETURNED STRING is `'/cart/'`, not merely that the input
 * was refused. The function returns the value to navigate to precisely so a caller cannot
 * check one string and use another, so the tests have to assert the value.
 */
import { describe, expect, it } from 'vitest';
import { safeLocalReturnPath } from '../lib/safeReturnPath';

const DEFAULT = '/cart/';

describe( 'safeLocalReturnPath — off-site destinations', () => {
  it( 'rejects an absolute URL', () => {
    expect( safeLocalReturnPath( 'https://evil.example/' ) ).toBe( DEFAULT );
    expect( safeLocalReturnPath( 'http://evil.example/cart/' ) ).toBe( DEFAULT );
  } );

  it( 'rejects a protocol-relative path WITH a dot', () => {
    expect( safeLocalReturnPath( '//evil.example' ) ).toBe( DEFAULT );
  } );

  it( 'rejects a protocol-relative path WITHOUT a dot — the gap in the old regex', () => {
    // A host label does not need a dot. `//evil` is `https://evil/` to a browser, and the
    // character-class check it replaced accepted every character in it.
    expect( safeLocalReturnPath( '//evil' ) ).toBe( DEFAULT );
  } );

  it( 'rejects extra leading slashes', () => {
    expect( safeLocalReturnPath( '///evil' ) ).toBe( DEFAULT );
  } );

  it( 'rejects backslash separators a browser normalises to /', () => {
    expect( safeLocalReturnPath( '/\\evil.example' ) ).toBe( DEFAULT );
    expect( safeLocalReturnPath( '\\\\evil.example' ) ).toBe( DEFAULT );
  } );

  it( 'rejects a non-navigational scheme', () => {
    expect( safeLocalReturnPath( 'javascript:alert(1)' ) ).toBe( DEFAULT );
    expect( safeLocalReturnPath( 'data:text/html,x' ) ).toBe( DEFAULT );
    expect( safeLocalReturnPath( 'mailto:a@b' ) ).toBe( DEFAULT );
  } );
} );

describe( 'safeLocalReturnPath — encoding, injection and traversal', () => {
  it( 'rejects percent-encoding instead of decoding it', () => {
    // The module never decodes, at any depth. `%2f%2f` decodes once to `//`, and
    // `%252f%252f` decodes to `%2f%2f` which decodes again — a decoding validator has to
    // pick a number of rounds and the attacker picks a different one.
    expect( safeLocalReturnPath( '%2f%2fevil.example' ) ).toBe( DEFAULT );
    expect( safeLocalReturnPath( '%252f%252fevil' ) ).toBe( DEFAULT );
    expect( safeLocalReturnPath( '/%2f%2fevil.example' ) ).toBe( DEFAULT );
  } );

  it( 'rejects CRLF and other control characters', () => {
    expect( safeLocalReturnPath( '/cart/%0d%0aSet-Cookie:x' ) ).toBe( DEFAULT );
    expect( safeLocalReturnPath( '/cart/\r\nSet-Cookie:x' ) ).toBe( DEFAULT );
    expect( safeLocalReturnPath( '/cart/\u0000' ) ).toBe( DEFAULT );
  } );

  it( 'rejects whitespace anywhere in the value', () => {
    expect( safeLocalReturnPath( '/cart/\t' ) ).toBe( DEFAULT );
    expect( safeLocalReturnPath( '/ cart/' ) ).toBe( DEFAULT );
    expect( safeLocalReturnPath( ' /cart/' ) ).toBe( DEFAULT );
  } );

  it( 'rejects a traversal segment', () => {
    expect( safeLocalReturnPath( '/../etc/passwd' ) ).toBe( DEFAULT );
    // First segment reads as `cart`, so the staff-segment check alone would miss it.
    expect( safeLocalReturnPath( '/cart/../workspace/access' ) ).toBe( DEFAULT );
  } );
} );

describe( 'safeLocalReturnPath — staff destinations', () => {
  it( 'rejects the staff workspace login', () => {
    expect( safeLocalReturnPath( '/workspace/access' ) ).toBe( DEFAULT );
  } );

  it( 'rejects the rest of the staff tree and its redirect shims', () => {
    for ( const staff of [
      '/workspace/dashboard/',
      '/workspace/',
      '/admin/',
      '/access/',
      '/dashboard/',
      '/settings/',
      '/engage/inbox/',
      '/contacts/',
      '/commerce/',
      '/pay/',
    ] ) {
      expect( safeLocalReturnPath( staff ), `${staff} must not be a customer return path` )
        .toBe( DEFAULT );
    }
  } );

  it( 'rejects a staff segment whatever its casing', () => {
    expect( safeLocalReturnPath( '/WorkSpace/access' ) ).toBe( DEFAULT );
  } );
} );

describe( 'safeLocalReturnPath — absent and malformed input', () => {
  it( 'falls back for an empty, null or undefined value', () => {
    expect( safeLocalReturnPath( '' ) ).toBe( DEFAULT );
    expect( safeLocalReturnPath( null ) ).toBe( DEFAULT );
    expect( safeLocalReturnPath( undefined ) ).toBe( DEFAULT );
  } );

  it( 'falls back for a local path that is simply not an allowed destination', () => {
    // Reject by default is the whole design: a well-formed, harmless, local path that
    // nobody listed still does not pass.
    expect( safeLocalReturnPath( '/blog/' ) ).toBe( DEFAULT );
    expect( safeLocalReturnPath( '/vault/' ) ).toBe( DEFAULT );
  } );
} );

describe( 'safeLocalReturnPath — the accepted set', () => {
  it( 'accepts each customer destination in its slashed form', () => {
    for ( const ok of [ '/cart/', '/checkout/', '/orders/', '/shop/', '/account/', '/' ] ) {
      expect( safeLocalReturnPath( ok ) ).toBe( ok );
    }
  } );

  it( 'normalises the unslashed form rather than rejecting it', () => {
    // `trailingSlash: true`, so the unslashed form would 301 to the slashed one anyway.
    expect( safeLocalReturnPath( '/cart' ) ).toBe( '/cart/' );
    expect( safeLocalReturnPath( '/checkout' ) ).toBe( '/checkout/' );
    expect( safeLocalReturnPath( '/shop' ) ).toBe( '/shop/' );
  } );

  it( 'never returns a value carrying a query string or fragment', () => {
    // The returned value is re-emitted from the normalised allowlist member, so state
    // attached to the input cannot ride along into the navigation.
    for ( const smuggled of [ '/cart/?next=//evil', '/cart/#f', '/cart?x=1', '/shop/#a' ] ) {
      const out = safeLocalReturnPath( smuggled );
      expect( out ).toBe( DEFAULT );
      expect( out ).not.toContain( '?' );
      expect( out ).not.toContain( '#' );
    }
  } );

  it( 'only ever returns a member of the allowed set', () => {
    const allowed = new Set( [ '/cart/', '/checkout/', '/orders/', '/shop/', '/account/', '/' ] );
    const inputs = [
      '/cart', '/cart/', '/', '//evil', '/workspace/access', 'https://evil.example/',
      '%2f%2fevil', '/../x', '', null, undefined, '/blog/', '/cart/#f',
    ];
    for ( const input of inputs ) {
      expect( allowed.has( safeLocalReturnPath( input ) ), `${String( input )} escaped the allowlist` )
        .toBe( true );
    }
  } );
} );
