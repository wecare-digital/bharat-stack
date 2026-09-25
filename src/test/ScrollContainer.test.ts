import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * GUARDS THE ONE CSS PAIR THAT PUTS A BLANK SCREEN AT THE END OF EVERY PAGE.
 *
 * Layout.css used to declare `html, body { height: 100%; overflow-y: auto }`. Those two
 * properties, on BOTH elements, create two nested scroll containers: body is capped at one
 * viewport while holding two or three viewports of content, so the page scrolls inside
 * body - and html keeps a separate leftover scroll range stacked on top, containing
 * nothing.
 *
 * Measured on the home page before the fix:
 *   320x568   html scrolled 623px past the end, footer pushed off the TOP of the screen
 *   390x844   196px of blank white below the footer
 *   1440x900  0px - correct, purely because html's leftover range computes to 0 at that
 *             height, which is why this survived review for so long
 *
 * WHY A SOURCE TEST WHEN uicheck.js ALREADY MEASURES IT. uicheck needs a built export and
 * a browser, so it runs once per CI job; this runs on every `vitest` in under a
 * millisecond and names the exact declaration to delete. The browser check proves the
 * behaviour, this one catches the edit.
 *
 * THE SECOND ASSERTION IS THE SUBTLE ONE. `overflow-x: hidden` on body is enough to
 * recreate the bug on its own, with no `height` anywhere: per spec, when one axis is
 * `hidden` the other computes from `visible` to `auto`, so body becomes a scroll container
 * again. Someone re-adding a horizontal guard "harmlessly" to body is the most likely way
 * this regresses, and it would not mention height at all.
 */

const CSS_PATH = path.join( process.cwd(), 'src', 'styles', 'Layout.css' );
const css = fs.readFileSync( CSS_PATH, 'utf8' );

/** The declarations inside a top-level rule whose selector matches exactly. */
const declarationsFor = ( selector: string ): string => {
  // Anchored at a line start so `body {` does not also match `.ft-footer body {` or
  // `html, body {`. Comments are stripped first: this file explains the bug in prose that
  // necessarily contains the very declarations being searched for.
  const withoutComments = css.replace( /\/\*[\s\S]*?\*\//g, '' );
  const pattern = new RegExp( `^${selector.replace( /[.*+?^${}()|[\]\\]/g, '\\$&' )}\\s*\\{([^}]*)\\}`, 'm' );
  const match = pattern.exec( withoutComments );
  return match ? match[ 1 ] : '';
};

describe( 'page scroll container', () => {
  it( 'finds the html and body rules to check', () => {
    // Anti-vacuous guard. If these rules are renamed or moved to another stylesheet, the
    // assertions below would pass against empty strings - a gate protecting nothing.
    expect( declarationsFor( 'html' ), 'no top-level `html {` rule found in Layout.css' ).toContain( 'overflow-x' );
    expect( declarationsFor( 'body' ), 'no top-level `body {` rule found in Layout.css' ).toContain( 'min-height' );
  } );

  it( 'never caps body at one viewport', () => {
    const body = declarationsFor( 'body' );
    expect(
      /(^|[\s;])height\s*:\s*100%/.test( body ),
      'body must not set `height: 100%`. That is what capped the body box at one viewport '
      + 'and sent the rest of the page into a nested scroller, putting 196px of blank white '
      + 'below the footer on a 390px phone and 623px on a 320px one. Use `min-height: 100vh` '
      + 'so a short page still fills the screen without constraining a long one.'
    ).toBe( false );

    expect( body, 'body should keep min-height so short pages still fill the screen' ).toMatch( /min-height\s*:\s*100vh/ );
  } );

  it( 'never makes body a second scroll container', () => {
    const body = declarationsFor( 'body' );
    for ( const property of [ 'overflow', 'overflow-x', 'overflow-y' ] ) {
      expect(
        new RegExp( `(^|[\\s;])${property}\\s*:` ).test( body ),
        `body must not set \`${property}\`. Any of these makes body a scroll container: when `
        + 'one axis is hidden or auto, the other computes from visible to auto. That is the '
        + 'two-scroller bug, and it comes back with no mention of height. The horizontal '
        + 'guard belongs on html, where the same computation correctly makes the DOCUMENT '
        + 'the scroller.'
      ).toBe( false );
    }
  } );

  it( 'keeps the horizontal guard on html, which is the one scroller', () => {
    expect( declarationsFor( 'html' ) ).toMatch( /overflow-x\s*:\s*hidden/ );
  } );

  it( 'does not double the safe-area insets', () => {
    // They were on html AND body, so a notched device inside the Capacitor shell got twice
    // the top inset. Invisible in a desktop browser, where every inset resolves to 0.
    const html = declarationsFor( 'html' );
    const body = declarationsFor( 'body' );
    expect(
      /safe-area-inset/.test( html ) && /safe-area-inset/.test( body ),
      'safe-area insets are applied on html AND body, which doubles them on a notched '
      + 'device. Keep them on body only.'
    ).toBe( false );
    expect( body, 'body should carry the safe-area insets' ).toMatch( /safe-area-inset/ );
  } );
} );

describe( 'overlay scroll locking', () => {
  /**
   * The paired half of the fix. Moving the scroll container silently breaks every overlay
   * that froze the page by setting `overflow: hidden` on body - the overlay opens, looks
   * correct, and the page keeps scrolling behind it. There is no error and nothing to see
   * in a screenshot, which is exactly why it is pinned here.
   */
  const OVERLAYS = [
    'src/components/ui/Modal.tsx',
    'src/components/ui/KeyboardShortcuts.tsx',
  ];

  /**
   * Strip comments before asserting absence.
   *
   * This failed on first run, and on the right thing: both components now carry a comment
   * explaining why they no longer set body overflow, and that explanation necessarily
   * contains the exact string being searched for. A negative assertion that fires on the
   * note recording the fix is worse than no assertion - it punishes documenting the
   * decision. The assertion below also pins the ASSIGNMENT form rather than the bare
   * expression, so prose mentioning the property in passing cannot trip it either.
   */
  const code = ( file: string ): string =>
    fs.readFileSync( path.join( process.cwd(), file ), 'utf8' )
      .replace( /\/\*[\s\S]*?\*\//g, '' )
      .replace( /^\s*\/\/.*$/gm, '' );

  it( 'locks through the shared helper, not body overflow', () => {
    for ( const file of OVERLAYS ) {
      const source = code( file );
      expect( source, `${file} must import the shared scroll lock` ).toContain( "from '../../lib/scrollLock'" );
      expect( source, `${file} must call lockScroll()` ).toContain( 'lockScroll()' );
      expect(
        /document\.body\.style\.overflow\s*=/.test( source ),
        `${file} still assigns document.body.style.overflow directly. The page scrolls inside `
        + 'the DOCUMENT, not inside body, so that locks nothing and fails silently. Use '
        + 'lockScroll()/unlockScroll() from src/lib/scrollLock.ts.'
      ).toBe( false );
    }
  } );

  it( 'sets both elements, so a future change of scroller cannot break it again', () => {
    const helper = fs.readFileSync( path.join( process.cwd(), 'src', 'lib', 'scrollLock.ts' ), 'utf8' );
    expect( helper ).toContain( 'document.documentElement' );
    expect( helper ).toContain( 'document.body' );
    // Cleared, not overwritten: writing a literal back would replace whatever the
    // stylesheet says, and on body `overflow-x: visible` is part of how it became a
    // scroll container in the first place.
    expect( helper ).toContain( "style.overflow = ''" );
  } );
} );
