import { describe, expect, it } from 'vitest';
import { execFileSync } from 'child_process';
import fs from 'fs';
import path from 'path';

/**
 * EVERY SCRIPT UNDER tools/ MUST AT LEAST PARSE.
 *
 * WHY THIS EXISTS, and it is a mistake I made twice in one session in two different files.
 *
 * The harnesses in tools/ are plain .js and are NOT covered by `tsc --noEmit`, which only
 * sees the typed source under src/. So a syntax error in a harness is invisible to every
 * gate this repo runs: the type check passes, the build passes, the test suite passes, and
 * the harness itself simply never executes.
 *
 * The concrete failure. tools/browser/stepreview.js builds a Markdown document inside a JS
 * template literal. Writing a property name in backticks - `queue` - as Markdown habit
 * suggests, closes the literal and makes the file unparseable. That is the SAME trap
 * src/test/StyledJsxBackticks.test.tsx guards for inside styled-jsx CSS blocks, in a place
 * that guard does not look.
 *
 * WHAT MADE IT EXPENSIVE was not the typo, it was that the crash was inaudible. The
 * generator was run as `node stepreview.js 2>&1 | tail -3 && npx tsc --noEmit`, so the stack
 * trace was truncated to its last two lines - "at node:internal/main/run_main_module" and a
 * version string - and read as noise belonging to the type check that followed. The document
 * on disk stayed at its previous revision and was committed and described to the owner as
 * containing a section it did not contain. A generator that fails silently is worse than one
 * that fails loudly, because its output looks plausible and stale.
 *
 * `node --check` parses without executing: no browser, no network, no side effects, and it
 * catches any syntax error rather than only this one. Milliseconds per file.
 */

const REPO = path.join( __dirname, '..', '..' );
const TOOLS = path.join( REPO, 'tools' );

function walk ( dir: string, out: string[] = [] ): string[] {
  if ( !fs.existsSync( dir ) ) return out;
  for ( const entry of fs.readdirSync( dir, { withFileTypes: true } ) ) {
    const p = path.join( dir, entry.name );
    if ( entry.isDirectory() ) {
      // node_modules is vendored dependencies, not ours to vouch for.
      if ( entry.name === 'node_modules' ) continue;
      walk( p, out );
    } else if ( /\.(js|cjs|mjs)$/.test( entry.name ) ) {
      out.push( p );
    }
  }
  return out;
}

describe( 'tools/ scripts parse', () => {
  const files = walk( TOOLS );

  it( 'finds harness scripts to check', () => {
    // Guards the guard: a walk that silently returns nothing would make every assertion
    // below vacuously true, which is the failure mode of a test that tests a glob.
    expect( files.length ).toBeGreaterThan( 10 );
  } );

  it.each( files.map( f => [ path.relative( REPO, f ), f ] ) )(
    '%s parses',
    ( rel, abs ) => {
      let error: string | null = null;
      try {
        execFileSync( process.execPath, [ '--check', abs ], { stdio: 'pipe' } );
      } catch ( e ) {
        const err = e as { stderr?: Buffer; message?: string };
        error = err.stderr?.toString() || err.message || 'unknown';
      }
      expect(
        error,
        `${rel} does not parse. If this mentions an unexpected identifier, check for an `
        + 'unescaped backtick inside a template literal - Markdown habit puts them in '
        + 'generated documentation and they close the literal.'
      ).toBeNull();
    }
  );
} );
