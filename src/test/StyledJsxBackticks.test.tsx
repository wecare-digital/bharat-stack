import { describe, expect, it } from 'vitest';
import fs from 'fs';
import path from 'path';

/**
 * A BACKTICK INSIDE A styled-jsx CSS BLOCK CLOSES THE TEMPLATE LITERAL.
 *
 * This cost three separate build failures in one session. Writing CSS documentation inside
 * those blocks is normal in this codebase - they carry long comments explaining why a rule
 * exists - and the moment such a comment quotes a property name in backticks, as Markdown
 * habit suggests, the literal ends early and everything after it is parsed as JSX.
 *
 * The failure is badly misleading. It reports as
 *   TS1381: Unexpected token. Did you mean ... ?
 * pointing at the closing brace of an unrelated rule HUNDREDS OF LINES BELOW the real cause,
 * so it reads as malformed JSX rather than one stray character in a comment. Worse,
 * `npm run build` fails at the type-check step, so a harness run straight afterwards
 * silently measures the PREVIOUS export - a green gate on stale output. That happened twice.
 *
 * Catching it is a lexical check: no browser, no render, milliseconds.
 */

/** A styled-jsx opener, as a pattern. Built from parts so this file cannot match itself. */
const OPENER = new RegExp( '<style\\s+jsx(\\s+global)?\\s*>\\s*\\{\\s*' + String.fromCharCode( 96 ) );
/** The terminator: a backtick, then }</style>. */
const CLOSER = new RegExp( String.fromCharCode( 96 ) + '\\s*\\}\\s*</style>' );
const BACKTICK = String.fromCharCode( 96 );

/**
 * Line numbers holding a backtick between a styled-jsx opener and its terminator.
 * Takes content rather than a path so the detector itself can be tested.
 */
export function strayBackticks ( content: string ): number[] {
  const lines = content.split( /\r?\n/ );
  const bad: number[] = [];
  let inBlock = false;
  for ( let i = 0; i < lines.length; i++ ) {
    const line = lines[ i ];
    if ( !inBlock ) {
      if ( OPENER.test( line ) ) inBlock = true;
      continue;
    }
    if ( CLOSER.test( line ) ) { inBlock = false; continue; }
    if ( line.includes( BACKTICK ) ) bad.push( i + 1 );
  }
  return bad;
}

describe( 'styled-jsx template literals', () => {
  const SRC = path.join( __dirname, '..' );
  const SELF = path.resolve( __filename );

  function walk ( dir: string, out: string[] = [] ): string[] {
    for ( const entry of fs.readdirSync( dir, { withFileTypes: true } ) ) {
      const p = path.join( dir, entry.name );
      if ( entry.isDirectory() ) {
        if ( entry.name === 'node_modules' ) continue;
        walk( p, out );
      } else if ( /\.tsx$/.test( entry.name ) ) {
        out.push( p );
      }
    }
    return out;
  }

  it( 'detects a stray backtick, and does not cry wolf on a clean block', () => {
    // THE DETECTOR IS TESTED BEFORE IT IS TRUSTED. A scanner that silently matched nothing
    // would pass the sweep below on every file forever and read as proof.
    const open = '<style jsx>{' + BACKTICK;
    const close = BACKTICK + '}</style>';

    const clean = [ 'render(', open, '  .a{color:red}', '  /* a plain comment */', close, ')' ].join( '\n' );
    expect( strayBackticks( clean ) ).toEqual( [] );

    const dirty = [ 'render(', open, '  /* see ' + BACKTICK + 'top' + BACKTICK + ' */', '  .a{color:red}', close, ')' ].join( '\n' );
    expect( strayBackticks( dirty ) ).toEqual( [ 3 ] );

    // Backticks OUTSIDE a block are ordinary template literals and must not be reported.
    const outside = [ 'const x = ' + BACKTICK + 'hi' + BACKTICK + ';', open, '  .a{color:red}', close ].join( '\n' );
    expect( strayBackticks( outside ) ).toEqual( [] );
  } );

  it( 'finds none in src, so no CSS block ends early', () => {
    const offenders: string[] = [];
    for ( const file of walk( SRC ) ) {
      // Skip this file: its own examples contain the very thing it looks for.
      if ( path.resolve( file ) === SELF ) continue;
      const lines = strayBackticks( fs.readFileSync( file, 'utf8' ) );
      if ( lines.length ) offenders.push( `${path.relative( SRC, file )} line(s) ${lines.join( ', ' )}` );
    }
    expect( offenders, 'a backtick inside a styled-jsx block closes the literal early' ).toEqual( [] );
  } );
} );
