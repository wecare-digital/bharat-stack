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
import fs from 'node:fs';
import path from 'node:path';
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

/**
 * KNOWN GAP, measured 2026-10-01 by the convergence step — two of the six values this
 * function can return have NO exported page, so they answer 404 live:
 *
 *     GET https://wecare.digital/checkout/  -> 404      GET https://wecare.digital/account/  -> 404
 *
 * `src/pages/checkout/` holds only `status.tsx` and `success.tsx`; `src/pages/account/` holds
 * only `sign-in.tsx`. Neither directory has an `index`, and `output: 'export'` emits a page
 * only where a source file exists, so there is nothing for `/checkout/` or `/account/` to hit
 * but the `/<*>` -> `/404.html` catch-all.
 *
 * WHY THIS IS PINNED RATHER THAN FIXED. The allowlist was specified verbatim by the task plan
 * (section 2 step 1) and FEAT-001 implemented it faithfully; the mismatch is between that list
 * and the live page inventory, which only became visible once both halves of the task were
 * measured together. Narrowing the list and building the two pages are BOTH product decisions,
 * and `src/pages/account/**` belongs to another workstream that this change may not edit. The
 * function is also still dormant — nothing outside this test imports it — so the gap cannot
 * reach a customer today. It would reach one the moment the one-line wiring in section 7 of
 * `docs/execution/url-host-matrix-20261001.md` is applied, which is exactly why it is recorded
 * there as a precondition rather than left for that owner to discover.
 *
 * This asserts the CURRENT measured truth so the discrepancy cannot ship silently. When it is
 * resolved, INVERT this test — do not delete it: either the two entries leave `ALLOWED` (then
 * assert they fall back to `/cart/`), or the two pages land (then assert the directory has an
 * index). The same convention as
 * `tests/test_url_host_routing_rules.py::test_the_provisioner_would_strip_the_host_rule_KNOWN_HAZARD`.
 */
describe( 'safeLocalReturnPath — accepted destinations that do not resolve (KNOWN GAP)', () => {
  const PAGES_DIR = path.join( process.cwd(), 'src', 'pages' );

  /** A destination resolves only if `output: 'export'` has a source file to emit for it. */
  const pageExists = ( segment: string ): boolean =>
    fs.existsSync( path.join( PAGES_DIR, segment, 'index.tsx' ) )
    || fs.existsSync( path.join( PAGES_DIR, `${segment}.tsx` ) );

  it( 'confirms the four resolvable destinations really do have a page', () => {
    // `/` is `src/pages/index.tsx`. If one of these ever stops existing, the validator would
    // start handing out a 404 for a destination this test currently vouches for.
    expect( fs.existsSync( path.join( PAGES_DIR, 'index.tsx' ) ), '/ must have an exported page' ).toBe( true );
    for ( const segment of [ 'cart', 'orders', 'shop' ] ) {
      expect( pageExists( segment ), `/${segment}/ must have an exported page` ).toBe( true );
    }
  } );

  it( 'records that /checkout/ and /account/ are accepted but have no page (invert when fixed)', () => {
    expect( pageExists( 'checkout' ) ).toBe( false );
    expect( pageExists( 'account' ) ).toBe( false );

    // Accepted today regardless, which is the gap itself: the function vouches for a value
    // that cannot be navigated to.
    expect( safeLocalReturnPath( '/checkout/' ) ).toBe( '/checkout/' );
    expect( safeLocalReturnPath( '/account/' ) ).toBe( '/account/' );
  } );

  it( 'has no production caller, which is what bounds the gap', () => {
    // Read as text rather than imported: importing a page module executes Amplify.configure.
    // If this ever fails, the section 7 wiring has landed and the two rows above became
    // customer-reachable — at which point the gap is live, not latent.
    const SELF = [ path.join( 'src', 'lib', 'safeReturnPath.ts' ), path.join( 'src', 'test', 'SafeReturnPath.test.ts' ) ];
    const walk = ( dir: string ): string[] => fs.readdirSync( dir, { withFileTypes: true } ).flatMap( ( entry ) => {
      const full = path.join( dir, entry.name );
      if ( entry.isDirectory() ) return walk( full );
      return /\.tsx?$/.test( entry.name ) ? [ full ] : [];
    } );
    const callers = walk( path.join( process.cwd(), 'src' ) )
      .map( ( full ) => path.relative( process.cwd(), full ) )
      .filter( ( rel ) => !SELF.includes( rel ) )
      .filter( ( rel ) => fs.readFileSync( path.join( process.cwd(), rel ), 'utf8' ).includes( 'safeLocalReturnPath' ) );
    expect( callers, `safeLocalReturnPath now has caller(s): ${callers.join( ', ' )}` ).toEqual( [] );
  } );
} );
