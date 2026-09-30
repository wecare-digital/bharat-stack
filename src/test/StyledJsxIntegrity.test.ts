import fs from 'fs';
import path from 'path';
import { describe, expect, it } from 'vitest';

/**
 * A STRAY BACKTICK INSIDE A styled-jsx BLOCK, CAUGHT STATICALLY.
 *
 * `.kiro/steering/grahak-os-design.md` has documented this trap for a long time, and it still
 * broke the build three times in one afternoon's work. A `<style jsx>` block is a template
 * literal, so one backtick inside it - including inside a CSS *comment* - terminates the
 * literal early. Everything after it is parsed as JSX, and the compiler reports a brace it
 * cannot match, often hundreds of lines below the actual cause:
 *
 *   src/components/LegalDocument.tsx(250,13): error TS1005: '}' expected.
 *
 * The line it names is not the line with the backtick. That gap between symptom and cause is
 * the whole reason this is worth a test rather than a note: `npx tsc --noEmit` already catches
 * it, but it points at the wrong place, so the loop is "read the error, look at the wrong
 * file, re-read the steering doc, then find it". This test names the file, the line and the
 * surrounding text.
 *
 * All three real occurrences were the same mistake: quoting a CSS property or a shell command
 * inside an explanatory comment, out of ordinary Markdown habit. Write them bare.
 *
 * WHY IT SCANS RATHER THAN LINTS. The repo's ESLint run reports 0 errors and ~177 warnings, so
 * a new warning would be invisible, and this is a build-breaking defect rather than a style
 * preference. A test fails loudly and names the location.
 */

const ROOT = path.join( __dirname, '..', '..' );
const SRC = path.join( ROOT, 'src' );

/** Every .tsx under src/, recursively. */
function tsxFiles ( dir: string, out: string[] = [] ): string[] {
  for ( const entry of fs.readdirSync( dir, { withFileTypes: true } ) ) {
    const full = path.join( dir, entry.name );
    if ( entry.isDirectory() ) tsxFiles( full, out );
    else if ( entry.name.endsWith( '.tsx' ) ) out.push( full );
  }
  return out;
}

interface Stray {
  file: string;
  line: number;
  context: string;
}

/**
 * Find backticks that terminate a styled-jsx block early.
 *
 * The block opens at `<style jsx>{` plus a backtick and is meant to close at a backtick
 * followed by `}</style>`. So the FIRST unescaped backtick after the opener must be the
 * closing one; if it is followed by anything else, it is stray.
 *
 * Both `<style jsx>` and `<style jsx global>` are matched, and the brace may carry whitespace
 * either side, which is why this is a regex rather than an indexOf.
 */
function findStrayBackticks ( source: string, file: string ): Stray[] {
  const strays: Stray[] = [];
  const opener = /<style\s+jsx(?:\s+global)?\s*>\s*\{\s*`/g;
  let match: RegExpExecArray | null;

  while ( ( match = opener.exec( source ) ) !== null ) {
    let i = match.index + match[ 0 ].length;
    while ( i < source.length ) {
      const tick = source.indexOf( '`', i );
      if ( tick === -1 ) break;
      // An escaped backtick is legal inside the literal and is not a terminator.
      if ( source[ tick - 1 ] === '\\' ) { i = tick + 1; continue; }
      // A ${...} interpolation is legal too; this repo's blocks are static, but be correct.
      const after = source.slice( tick, tick + 24 );
      if ( /^`\s*\}\s*<\/style>/.test( after ) ) break;   // the real close
      strays.push( {
        file: path.relative( ROOT, file ),
        line: source.slice( 0, tick ).split( '\n' ).length,
        context: source.slice( Math.max( 0, tick - 60 ), tick + 20 ).replace( /\s+/g, ' ' ).trim(),
      } );
      break;   // one report per block is enough; the first stray is the cause
    }
  }
  return strays;
}

describe( 'styled-jsx blocks are intact', () => {
  const files = tsxFiles( SRC );

  it( 'scans a meaningful number of files', () => {
    // A guard on the guard: a broken walker that finds nothing would pass the real assertion
    // below silently, which is the failure mode this repo's harness README warns about -
    // treat "could not tell" as a failure, never as a pass.
    expect( files.length ).toBeGreaterThan( 50 );
  } );

  it( 'contains no backtick that closes a style block early', () => {
    const strays = files.flatMap( f => findStrayBackticks( fs.readFileSync( f, 'utf8' ), f ) );
    const report = strays
      .map( s => `\n  ${s.file}:${s.line}\n    ...${s.context}` )
      .join( '' );
    expect( strays, `stray backtick(s) inside <style jsx>:${report}\n\nWrite CSS properties and shell commands bare in these comments - a backtick ends the template literal.` )
      .toEqual( [] );
  } );

  it( 'still detects a stray backtick when one is present', () => {
    // The assertion above passes on a clean tree whether or not the walker works, so prove it
    // fires. Both fixtures are the shapes that actually broke the build.
    const inComment = 'const A = () => <style jsx>{ `\n .a{color:red} /* see `outline:none` */\n .b{color:blue}\n` }</style>;';
    const inCss = 'const B = () => <style jsx>{ `\n .a{content:"`"}\n` }</style>;';
    expect( findStrayBackticks( inComment, 'fixture-comment.tsx' ) ).toHaveLength( 1 );
    expect( findStrayBackticks( inCss, 'fixture-css.tsx' ) ).toHaveLength( 1 );

    const clean = 'const C = () => <style jsx>{ `\n .a{color:red} /* see outline:none */\n` }</style>;';
    expect( findStrayBackticks( clean, 'fixture-clean.tsx' ) ).toEqual( [] );
  } );
} );
