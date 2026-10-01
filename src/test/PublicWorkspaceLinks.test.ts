import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * NO PUBLIC SURFACE MAY OFFER A CUSTOMER A DOOR INTO THE STAFF WORKSPACE.
 *
 * Two real instances were found on 2026-10-01 and both are fixed; this file is what stops
 * them coming back, because neither was caught by anything:
 *
 *   1. `src/components/ErrorBoundary.tsx` offered a button labelled "Dashboard" pointing at
 *      `/workspace/dashboard`. The component is mounted inside the `if ( isPublic )` branch
 *      of `src/pages/_app.tsx`, so the audience for that button was customers hitting a
 *      render error on a public page - cart, checkout, shop, a blog post.
 *   2. `public/manifest.json` declared three PWA `shortcuts` at `/workspace/dashboard/`,
 *      `/workspace/engage/inbox/` and `/workspace/contacts/`. That is the OS long-press
 *      menu for anyone who installs the public site.
 *
 * THIS IS NOT ACCESS CONTROL, and must not be mistaken for it. `/workspace/` still answers
 * 200 with the Cognito Authenticator shell and is `Disallow:`ed in robots.txt - that is the
 * legitimate staff entrance and it is untouched. Hiding a link does not protect anything.
 * What this guards is the opposite failure: a customer being SENT somewhere useless to them.
 *
 * READS SOURCE AS TEXT rather than importing, following src/test/PublicRouteRegistration.test.ts.
 * Importing _app.tsx would execute Amplify.configure and the analytics side effects at module
 * scope, and the values asserted here are literals in the files anyway.
 */

const ROOT = process.cwd();
const read = ( rel: string ): string => fs.readFileSync( path.join( ROOT, rel ), 'utf8' );

/**
 * Files that DO contain workspace destinations and are deliberately left alone. Named with a
 * reason each, so every exemption is a decision on the record rather than a silent gap - the
 * same discipline INTENTIONALLY_NOT_PUBLIC uses in PublicRouteRegistration.test.ts.
 */
const INTENTIONALLY_WORKSPACE_ONLY: Record<string, string> = {
  'src/components/Layout.tsx':
    'the authenticated dashboard shell. Imported by zero pages outside src/pages/workspace/** '
    + '(verified), so its "Sign in" -> /workspace/access is staff chrome, not a public link.',
  'src/components/SearchModal.tsx':
    'imported only by Layout.tsx, so it is reachable only from inside the workspace. Its '
    + 'default paths are workspace sections.',
  'src/components/ui/Breadcrumbs.tsx':
    'workspace-only breadcrumb trail rooted at /workspace/dashboard. No public importer.',
  'public/sw.js':
    'line ~180 is the default DESTINATION for a staff push notification click, not a '
    + 'navigation link rendered to anyone. Recorded as needs-verification rather than '
    + 'changed: repointing it could break staff push with no customer benefit.',
};

/** Destinations a public component must never link to. */
const FORBIDDEN_TARGETS = [ '/workspace', '/admin', '/access', 'sign-in' ];

/**
 * Every href VALUE in a source file, from both shapes this codebase uses: the JSX attribute
 * `href="..."` and the navigation-data property `href: '...'`.
 *
 * Deliberately NOT a substring search over the whole file. Header.tsx and Footer.tsx both
 * discuss `/access`, `/workspace/forms/` and sign-in at length in their comments - recording
 * that the staff login was REMOVED from the public header - and a substring check would fail
 * on the explanation of the fix rather than on the defect.
 */
const hrefValues = ( source: string ): string[] => [
  ...Array.from( source.matchAll( /href=["']([^"']*)["']/g ) ).map( m => m[ 1 ] ),
  ...Array.from( source.matchAll( /href:\s*['"]([^'"]*)['"]/g ) ).map( m => m[ 1 ] ),
];

describe( 'public components link to no staff destination', () => {
  it( 'has no /workspace string anywhere in ErrorBoundary.tsx', () => {
    // A substring check IS right for this one: the component is small, it is mounted on every
    // public page, and after the fix there is no legitimate reason for the token to appear -
    // not in a target, not in a label, not in a comment that could be copied into a target.
    expect(
      read( 'src/components/ErrorBoundary.tsx' ),
      'ErrorBoundary renders on every PUBLIC page (inside the isPublic branch of _app.tsx). '
      + 'A /workspace target here is an escape hatch that lands a customer on the staff login.'
    ).not.toContain( '/workspace' );
  } );

  it( 'keeps the ErrorBoundary secondary button labelled Home', () => {
    const source = read( 'src/components/ErrorBoundary.tsx' );
    expect( source ).toContain( '>Home</button>' );
    expect( source ).not.toContain( '>Dashboard</button>' );
    expect( source ).toContain( "window.location.href = '/'" );
  } );

  it( 'exposes no workspace URL in the public web app manifest', () => {
    const manifest = JSON.parse( read( 'public/manifest.json' ) ) as Record<string, unknown>;

    const offenders: string[] = [];
    const walk = ( value: unknown, trail: string ): void => {
      if ( typeof value === 'string' ) {
        if ( value.startsWith( '/workspace' ) ) offenders.push( `${trail} = ${value}` );
        return;
      }
      if ( Array.isArray( value ) ) {
        value.forEach( ( item, i ) => walk( item, `${trail}[${i}]` ) );
        return;
      }
      if ( value && typeof value === 'object' ) {
        for ( const [ k, v ] of Object.entries( value ) ) walk( v, `${trail}.${k}` );
      }
    };
    walk( manifest, 'manifest' );

    expect(
      offenders,
      'public/manifest.json is the manifest for the PUBLIC site. A /workspace value here '
      + 'becomes an OS launcher shortcut or start_url into the staff Cognito login for every '
      + 'customer who installs wecare.digital.'
    ).toEqual( [] );
  } );

  it( 'keeps Header and Footer free of staff hrefs', () => {
    const offenders: string[] = [];
    for ( const file of [ 'src/components/Header.tsx', 'src/components/Footer.tsx' ] ) {
      for ( const href of hrefValues( read( file ) ) ) {
        const hit = FORBIDDEN_TARGETS.find( target => href.includes( target ) );
        if ( hit ) offenders.push( `${file}: href ${href} contains ${hit}` );
      }
    }

    expect(
      offenders,
      'Header and Footer are mounted centrally on every public page AND on the sign-in '
      + 'screen. Header.tsx already records why the staff "Sign in" row was removed from it; '
      + 'this asserts it stays removed.'
    ).toEqual( [] );
  } );

  it( 'names every workspace-only exemption with its reason', () => {
    // A guard whose exemption list has drifted out of existence protects nothing, so the
    // exempted files must still be there and must still carry a reason.
    for ( const [ file, reason ] of Object.entries( INTENTIONALLY_WORKSPACE_ONLY ) ) {
      expect( fs.existsSync( path.join( ROOT, file ) ), `${file} is exempted but missing` )
        .toBe( true );
      expect( reason.length, `${file} needs a real reason, not a placeholder` )
        .toBeGreaterThan( 20 );
    }
  } );

  it( 'keeps the workspace-only chrome out of public pages', () => {
    /*
     * The assumption the first three exemptions rest on, asserted rather than trusted:
     * Layout, SearchModal and Breadcrumbs are imported ONLY from src/pages/workspace/** (plus
     * each other and the test tree). The moment a public page imports one, its workspace links
     * become public links and the exemption above silently becomes wrong.
     */
    const offenders: string[] = [];
    const walk = ( dir: string ): void => {
      for ( const entry of fs.readdirSync( dir, { withFileTypes: true } ) ) {
        const full = path.join( dir, entry.name );
        if ( entry.isDirectory() ) {
          if ( entry.name !== 'workspace' && entry.name !== 'api' ) walk( full );
        } else if ( entry.name.endsWith( '.tsx' ) ) {
          const source = fs.readFileSync( full, 'utf8' );
          if ( /from\s+'[^']*components\/(Layout|MaybeLayout|SearchModal|ui\/Breadcrumbs)'/.test( source ) ) {
            offenders.push( path.relative( ROOT, full ) );
          }
        }
      }
    };
    walk( path.join( ROOT, 'src', 'pages' ) );

    expect(
      offenders,
      'These pages are outside src/pages/workspace/** but import workspace-only chrome. '
      + 'INTENTIONALLY_WORKSPACE_ONLY in this file exempts Layout/SearchModal/Breadcrumbs '
      + 'from the staff-link check precisely because no public page imports them.'
    ).toEqual( [] );
  } );
} );
