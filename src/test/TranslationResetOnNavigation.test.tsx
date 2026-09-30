/**
 * A translated page must not survive a client-side navigation half-translated.
 *
 * THE REPORTED DEFECT, with a screenshot of a post page in Arabic: translate a page, click
 * through to another post, and the chrome stays Arabic - "شارك", "أقدم", "أحدث" - while every
 * post title renders in English, the document still lays out right-to-left, and the language
 * control still claims AR.
 *
 * Four separate things persist across a Next.js route change, and each one had to be undone:
 *
 *   1. Text nodes in the SHARED CHROME. Header, footer, share row and the widget itself are not
 *      re-rendered by a route change, so their nodes keep the translated values while the body
 *      arrives fresh from React in English.
 *   2. `document.documentElement.lang`.
 *   3. `document.documentElement.dir` - it lives on <html>, outside React, so right-to-left
 *      layout outlived the Arabic text it was for.
 *   4. `originals.current`, the Map of node -> original English. After a navigation its keys are
 *      detached nodes from the previous page. That is the stale cache in the report: dead keys
 *      pinned in a Map, and a restore() that could not reach the nodes that needed restoring.
 *
 * Asserted against the MODULE SOURCE rather than by driving the component. Translating requires
 * the /languages catalogue and the /translate endpoint, and a test that mocked both would be
 * asserting its own mocks; what needs pinning is that the reset exists, that it is wired to the
 * route event, and that it undoes all four things. rtlLanguage.test.tsx already covers the
 * direction logic itself.
 */
import { describe, expect, it } from 'vitest';
import fs from 'fs';
import path from 'path';

const SOURCE = fs.readFileSync(
  path.resolve( __dirname, '..', 'components', 'SupportWidget.tsx' ), 'utf8',
);

/** The body of the reset effect, so a match cannot come from the prose above it. */
const resetEffect = (): string => {
  const start = SOURCE.indexOf( 'const resetToEnglish' );
  expect( start, 'the reset handler is gone - a navigation will leave the page half translated' )
    .toBeGreaterThan( -1 );
  return SOURCE.slice( start, SOURCE.indexOf( '};', start ) );
};

describe( 'translation resets on client-side navigation', () => {
  it( 'is wired to routeChangeStart and cleans the listener up', () => {
    expect( SOURCE ).toContain( "import { useRouter } from 'next/router'" );
    expect( SOURCE ).toContain( "events.on( 'routeChangeStart', resetToEnglish )" );
    // Removed on unmount, or a remount stacks a second handler on the same router.
    expect( SOURCE ).toContain( "events.off( 'routeChangeStart', resetToEnglish )" );
  } );

  it( 'resets on START rather than COMPLETE, so no frame shows translated chrome', () => {
    /*
     * At routeChangeStart the previous page's body nodes are still attached, so restore()
     * reaches all of them and English is in place before the new page paints. At
     * routeChangeComplete the chrome would flash translated text first.
     */
    expect( SOURCE ).not.toContain( "on( 'routeChangeComplete', resetToEnglish )" );
  } );

  it( 'undoes all four things that survive a route change', () => {
    const body = resetEffect();
    // 1. the chrome's translated text nodes
    expect( body, 'text nodes not restored' ).toContain( 'restore()' );
    // 2. the stale cache of detached nodes from the previous page
    expect( body, 'originals not cleared - the Map grows by one page per navigation' )
      .toContain( 'originals.current = null' );
    // 3. lang
    expect( body ).toContain( "document.documentElement.lang = 'en'" );
    // 4. dir, which is the one the screenshot showed most plainly
    expect( body, 'direction not reset - English would keep running right-to-left' )
      .toContain( "applyDirection( 'en' )" );
    // And the control must agree with the page it is describing.
    expect( body, 'the language control would still claim the old language' )
      .toContain( "setCurrent( 'en' )" );
  } );

  it( 'reads the router defensively so a routerless mount cannot throw', () => {
    // _app.tsx always provides one, but this component is also mounted directly by tests.
    expect( SOURCE ).toContain( 'const events = router?.events;' );
    expect( SOURCE ).toContain( 'if ( !events ) return;' );
  } );

  it( 'still does not persist the chosen language', () => {
    /*
     * The fix must not become "remember it and re-translate", which is the behaviour a removed
     * localStorage key used to have: translation is billed per character, so auto-translating
     * every subsequent page spends money nobody asked to spend. Reset is the documented resting
     * state, and this is what stops the next edit quietly reintroducing persistence.
     */
    const withoutComments = SOURCE
      .replace( /\/\*[\s\S]*?\*\//g, '' )
      .split( '\n' ).map( line => line.split( '//' )[ 0 ] ).join( '\n' );
    expect( withoutComments ).not.toContain( 'localStorage' );
    expect( withoutComments ).not.toContain( 'sessionStorage' );
  } );
} );
