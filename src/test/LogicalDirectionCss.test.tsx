import { describe, expect, it } from 'vitest';
import fs from 'fs';
import path from 'path';

/**
 * NO PHYSICAL DIRECTION PROPERTIES IN THE SHIPPED STYLESHEETS.
 *
 * WHY A STATIC CHECK AND NOT A BROWSER ONE. rtlcheck.js measures the rendered page and is the
 * better instrument wherever it can reach. It cannot reach the INSIDE of an authenticated
 * view: next.config.js exports static HTML, so every dashboard route ships an auth shell and
 * the real tables, forms and side panels never render. That left a genuine hole - 216 physical
 * declarations across these files, on surfaces no gate could load - and the honest answer was
 * "needs a signed-in session".
 *
 * It does not, for this particular claim. Whether a rule names a physical edge is a property
 * of the TEXT, not of the render. If no stylesheet contains margin-left, padding-right,
 * border-left or a left/right inset, then there is nothing direction-specific left in them to
 * break, on any surface, signed in or not. That is a weaker statement than "the dashboard
 * looks right in Arabic" - it says nothing about whether the design reads well - but it is the
 * whole of the mechanical question, and it needs no session.
 *
 * WHAT IS NOT COVERED, deliberately:
 *   - styled-jsx blocks inside .tsx components. Those are measured by rtlcheck.js on 125
 *     routes at six viewports, which is the stronger check, and several of them keep physical
 *     properties ON PURPOSE - see the specificity note below and the dir="ltr" terminal.
 *   - border-radius corners. They are two-axis (border-top-left-radius), and a wrong mapping
 *     is worse than none, so they are out of scope rather than silently converted.
 *   - float, which does not appear in these files.
 */
describe( 'stylesheets are direction-agnostic', () => {
  const STYLES = path.join( __dirname, '..', 'styles' );

  /**
   * THE ONE ALLOWED EXCEPTION, named with its reason rather than hidden behind a loose regex.
   *
   * Pages.css .contact-info sets margin-left both in the base rule AND inside a media query.
   * Converting the base to margin-inline-start makes Lightning CSS rewrite it into a
   * :not(:is(:lang(...))) / :is(:lang(...)) pair; :lang() is a pseudo-class, so the compiled
   * base selector gains a specificity class and BEATS the plain media-query override. That is
   * not theory - it is what put the language pill at right:20px where the media query asked
   * for 16px, twice, until the inset was moved into a custom property. The same repair is
   * available here and is not worth the churn for one rule on a dashboard panel, so it stays
   * physical and stays listed.
   */
  const ALLOWED = [
    { file: 'Pages.css', selectorHint: 'contact-info', prop: 'margin-left' },
  ];

  const PHYSICAL = [
    'margin-left', 'margin-right',
    'padding-left', 'padding-right',
    'border-left', 'border-right',
    'border-left-width', 'border-right-width',
    'border-left-color', 'border-right-color',
    'border-left-style', 'border-right-style',
  ];

  function cssFiles (): string[] {
    return fs.readdirSync( STYLES ).filter( f => f.endsWith( '.css' ) ).sort();
  }

  /** Declarations naming a physical edge, with the rule they sit in. */
  function offenders ( css: string ): Array<{ line: number; prop: string; rule: string }> {
    const out: Array<{ line: number; prop: string; rule: string }> = [];
    const lines = css.split( /\r?\n/ );
    let rule = '';
    for ( let i = 0; i < lines.length; i++ ) {
      const line = lines[ i ];
      // Track the most recent selector so a failure can name the rule, not just a line.
      const open = /([^{}]+)\{/.exec( line );
      if ( open ) rule = open[ 1 ].trim().replace( /\s+/g, ' ' ).slice( -60 );

      const stripped = line.replace( /\/\*[\s\S]*?\*\//g, '' );
      // EVERY declaration on the line, not the first. Minified and hand-packed rules put
      // several on one line - `position:absolute;left:0` is the common shape - and a single
      // exec() stops at `position`, so the inset that matters is never seen. The detector's
      // own test caught this, which is the reason that test exists.
      for ( const d of stripped.matchAll( /(?:^|[;{]|\s)([a-z-]+)\s*:\s*([^;}]*)/g ) ) {
        const prop = d[ 1 ];
        const value = ( d[ 2 ] || '' ).trim();
        // `left` and `right` are also VALUES (float:left, text-align:left,
        // background-position:left top). This arm only fires where one is the PROPERTY.
        if ( PHYSICAL.includes( prop ) || prop === 'left' || prop === 'right' ) {
          out.push( { line: i + 1, prop, rule } );
        }
        // text-align:left / :right are direction assumptions too - start/end exist for them.
        if ( prop === 'text-align' && /^(left|right)\b/.test( value ) ) {
          out.push( { line: i + 1, prop: 'text-align:physical', rule } );
        }
      }
    }
    return out;
  }

  it( 'has no physical direction properties left, except the one named exception', () => {
    const failures: string[] = [];
    for ( const file of cssFiles() ) {
      const css = fs.readFileSync( path.join( STYLES, file ), 'utf8' );
      for ( const o of offenders( css ) ) {
        const excused = ALLOWED.some( a =>
          a.file === file && a.prop === o.prop && o.rule.includes( a.selectorHint ) );
        if ( !excused ) failures.push( `${file}:${o.line}  ${o.prop}  in "${o.rule}"` );
      }
    }
    expect( failures, 'use the logical equivalent: margin-inline-start, padding-inline-end, inset-inline-start, text-align:start' ).toEqual( [] );
  } );

  it( 'detects a physical property, so a silent pass cannot be mistaken for proof', () => {
    // The scanner is tested before it is trusted. A regex that matched nothing would pass the
    // sweep above on every file forever and get cited as evidence.
    expect( offenders( '.a{margin-left:4px}' ).map( o => o.prop ) ).toEqual( [ 'margin-left' ] );
    expect( offenders( '.a{inset-inline-start:4px}' ) ).toEqual( [] );
    expect( offenders( '.a{position:absolute;left:0}' ).map( o => o.prop ) ).toEqual( [ 'left' ] );
    expect( offenders( '.a{text-align:left}' ).map( o => o.prop ) ).toEqual( [ 'text-align:physical' ] );
    expect( offenders( '.a{text-align:start}' ) ).toEqual( [] );
    // `left` as a VALUE must not be reported - only as a property.
    expect( offenders( '.a{float:left}' ) ).toEqual( [] );
    expect( offenders( '.a{background-position:left top}' ) ).toEqual( [] );
    // A commented-out declaration is not a declaration.
    expect( offenders( '.a{/* margin-left:4px */}' ) ).toEqual( [] );
  } );

  it( 'still covers every stylesheet, so a renamed file cannot slip the check', () => {
    const files = cssFiles();
    expect( files.length ).toBeGreaterThanOrEqual( 8 );
    for ( const expected of [ 'Layout.css', 'Pages.css', 'Dashboard.css', 'inner-pages.css', 'inner-ux.css' ] ) {
      expect( files, `${expected} is one of the sheets this check exists for` ).toContain( expected );
    }
  } );
} );
