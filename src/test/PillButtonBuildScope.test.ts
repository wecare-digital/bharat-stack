import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

/**
 * STYLED-JSX SCOPING, CHECKED AGAINST THE BUILT HTML - the only layer where it is observable.
 *
 * WHY THIS FILE EXISTS. On 2026-10-02 the sign-in and cart CTAs shipped to production with both
 * pill segments COMPLETELY UNSTYLED, rendering as the run-together "Sign inConfirm code" the
 * owner reported. The cause was that PillButton hoisted its two <span> segments into an
 * intermediate variable, and styled-jsx only attaches its scope class to JSX in the tree it
 * transforms. Measured in the real build output at the time:
 *
 *   CSS shipped     .pill-label.jsx-69f2e5793ae0f718{...}  .pill-action.jsx-69f2e5793ae0f718{...}
 *   markup shipped  <span class="pill-label">              <span class="pill-action">
 *   the button      <button class="jsx-69f2e5793ae0f718 pill">   <-- correctly scoped
 *
 * The selectors could never match. Chrome reported display:block, background-color:rgba(0,0,0,0),
 * padding:0px and font-weight:400 on each segment.
 *
 * THE FIX ITSELF IS NOT MINE. It landed upstream in 2f742ec6, which inlined the segments into
 * both the <a> and <button> branches and added two SOURCE-LEVEL guards in PillButton.test.tsx
 * against re-hoisting. This file is the complement to those guards, not a duplicate of them:
 * they assert the shape of the code, this asserts the OUTCOME in the built artifact. The
 * distinction matters because the source guards enumerate the spellings they know about
 * (`const inner`, `const segments`, `function renderSegments`), so a fourth way of lifting the
 * JSX out of the return tree - a child component, a `.map`, a render prop - would pass them and
 * still ship unstyled. This assertion cannot be evaded that way, because it reads what the
 * browser actually gets.
 *
 * WHY NO OTHER TEST COULD CATCH IT. vitest does not run the styled-jsx transform at all, so
 * `<style jsx>` renders as a plain <style> with UNSCOPED selectors. jsdom therefore sees
 * selectors that WOULD match, and PillButton.test.tsx says as much ("the colours are the browser
 * harness's job"). A unit test cannot observe this class of failure even in principle, so the
 * assertion has to happen against the artifact the browser actually loads.
 *
 * WHAT IT ASSERTS. For every element in the built page whose class list contains a `pill*` class
 * that the page's own inlined CSS scopes, the element must carry the matching `jsx-*` hash. That
 * is the property - "the selector can reach the element" - rather than any particular hash, which
 * changes whenever the CSS does.
 *
 * It SKIPS with an explicit message when `out/` is absent, so it never silently passes.
 */

const OUT = join( __dirname, '..', '..', 'out' );
const PAGE = join( OUT, 'account', 'sign-in', 'index.html' );
const BUILD_HINT = 'run `node scripts/generate-public-pages.js && npx next build --webpack` '
  + 'first (Turbopack cannot resolve `next` through the worktree symlink, so --webpack is required)';

/** The `pill*` class names styled-jsx scoped in this page's inlined CSS, with their hashes. */
function scopedPillClasses ( html: string ): Map<string, Set<string>> {
  const scoped = new Map<string, Set<string>>();
  // e.g. `.pill-action.jsx-69f2e5793ae0f718` - the class, then the scope hash.
  for ( const match of html.matchAll( /\.(pill[\w-]*)\.(jsx-[0-9a-f]+)/g ) ) {
    const [ , className, hash ] = match;
    if ( !scoped.has( className ) ) scoped.set( className, new Set() );
    scoped.get( className )!.add( hash );
  }
  return scoped;
}

/** Every `class="..."` value in the page that mentions a pill class. */
function pillClassAttributes ( html: string ): string[] {
  return [ ...html.matchAll( /class="([^"]*)"/g ) ]
    .map( m => m[ 1 ] )
    .filter( value => /\bpill[\w-]*\b/.test( value ) );
}

describe( 'the built pill markup carries the scope hash its CSS requires', () => {
  const present = existsSync( PAGE );
  const run = present ? it : it.skip;

  it( 'has a built page to inspect', () => {
    expect( present, `${ PAGE } is missing - ${ BUILD_HINT }` ).toBe( true );
  } );

  run( 'scopes every pill class that appears in the markup', () => {
    const html = readFileSync( PAGE, 'utf8' );
    const scoped = scopedPillClasses( html );
    expect( scoped.size,
      'no scoped .pill* selectors found in the built CSS - the component may have been renamed' )
      .toBeGreaterThan( 0 );

    const unscoped: string[] = [];
    for ( const value of pillClassAttributes( html ) ) {
      const classes = value.split( /\s+/ ).filter( Boolean );
      const hashes = new Set( classes.filter( c => c.startsWith( 'jsx-' ) ) );
      for ( const className of classes ) {
        const required = scoped.get( className );
        if ( !required ) continue;   // not a styled-jsx-scoped pill class
        // The element must carry at least one of the hashes its selector was written with.
        if ( ![ ...required ].some( hash => hashes.has( hash ) ) ) {
          unscoped.push( `${ className } on class="${ value }" `
            + `(CSS requires one of ${ [ ...required ].join( ', ' ) })` );
        }
      }
    }

    expect( unscoped,
      'these elements carry a pill class whose CSS selector is scoped, but the element has no '
      + 'matching jsx-* hash, so the selector cannot match and the element ships UNSTYLED. This '
      + 'is the "Sign inConfirm code" defect. Check that the segments are written inline inside '
      + "the component's returned JSX rather than hoisted into a variable." )
      .toEqual( [] );
  } );

  run( 'scopes the sign-in pill label specifically, not just the outer control', () => {
    const html = readFileSync( PAGE, 'utf8' );
    // The phone phase ships in the static HTML, so "Send code" is the observable action.
    expect( html ).toContain( 'Send code' );

    // Narrowed to the two segment classes, so this still fails if only the OUTER control is
    // scoped - which is exactly how the defect presented: the <button> carried the hash and
    // kept its shape and dark fill, while neither segment got its background or colour.
    // ONE SEGMENT NOW. The owner retired the two-tone pill on 2026-10-02, so there is a single
    // lime surface with one .pill-action label; .pill-label is no longer rendered. The guard is
    // unchanged in substance - it still fails if only the OUTER control carries the hash, which is
    // exactly how the original defect presented.
    for ( const segment of [ 'pill-action' ] as const ) {
      const attrs = [ ...html.matchAll( /class="([^"]*)"/g ) ]
        .map( m => m[ 1 ] )
        .filter( value => value.split( /\s+/ ).includes( segment ) );
      expect( attrs.length, `no element carries .${ segment } in the built page` )
        .toBeGreaterThan( 0 );
      for ( const value of attrs ) {
        expect( value, `.${ segment } shipped with no jsx-* scope hash, so its rules cannot `
          + 'match and it renders unstyled' ).toMatch( /\bjsx-[0-9a-f]+\b/ );
      }
    }
  } );
} );
