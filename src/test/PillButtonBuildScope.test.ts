import { existsSync, readFileSync, statSync } from 'node:fs';
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
 * THE PILL IS ONE SEGMENT NOW, so read the history above as history. `1c847107` retired the
 * two-tone treatment on owner instruction: the control is a single lime surface carrying one
 * `.pill-action` label, and `.pill-label` is not rendered anywhere. The scoping property is
 * unchanged by that - it is per class, not per segment count - and the defect this file exists to
 * catch is still reachable with one segment, because the failure was the OUTER control being
 * stamped while the span inside it was not.
 *
 * HOW IT BEHAVES WITHOUT A BUILD, stated precisely because the first version of this docblock
 * did not match the code and a review caught it. There are FOUR states, not two:
 *
 *   no `out/` at all          every case SKIPS, with the build command in the skipped title.
 *   `out/` but no page        every case FAILS. A build ran and did not emit this page, which is
 *                             a real defect rather than a missing prerequisite.
 *   the page is STALE         every case SKIPS, naming the source that is newer. See below.
 *   the page is current       every case RUNS.
 *
 * The first state is why the presence check is not a plain `it` asserting `existsSync`. This is
 * the ONLY test in the suite that reads build output, and a build is not a prerequisite of any
 * other test, so `npx vitest run` on a fresh clone must not go red over an artifact nobody asked
 * for. It still never silently passes: a skip is reported as a skip, and the reason travels in
 * the test title. CI is unaffected either way - `.github/workflows/build-test.yml` runs
 * `npm run build` before `npx vitest run` and `next.config.js` sets `output: 'export'`, so the
 * page always exists there and all cases run.
 *
 * THE STALE STATE IS THE ONE THAT MATTERS MOST, and it was missing until a review named it. A
 * gate of `existsSync( OUT )` alone cannot tell a current export from a leftover one, so a
 * left-behind `out/` from an earlier tree would have every assertion here run against HTML that
 * need not correspond to the source being tested - and this is the single test whose entire value
 * is "read what the browser actually gets". It would then pass or fail on the wrong artifact,
 * silently. This workstream was bitten by exactly that class of error one commit earlier, when a
 * Lambda was built from a 40-commit-stale tree and a local verify said OK.
 *
 * So the page's mtime is compared against the sources that produce its pill markup (see SOURCES),
 * and a page older than any of them SKIPS rather than FAILS. Skip, because a stale artifact is no
 * evidence either way - exactly like no artifact - whereas failing would turn `npx vitest run`
 * red for anyone who edits a component without rebuilding, which is the normal case and the way
 * an inconvenient test gets deleted. CI cannot reach this state: `build-test.yml` builds
 * immediately before vitest, and a failed build stops the job before the tests run.
 */

const OUT = join( __dirname, '..', '..', 'out' );
const PAGE = join( OUT, 'account', 'sign-in', 'index.html' );
const BUILD_HINT = 'run `node scripts/generate-public-pages.js && npx next build --webpack` '
  + 'first (Turbopack cannot resolve `next` through the worktree symlink, so --webpack is required)';

/**
 * The sources whose output this file reads, for the staleness comparison. DELIBERATELY NARROW:
 * only the two files that decide this page's pill markup and its scoped CSS. Widening it to all
 * of `src/` would call the build stale after an edit that cannot change the assertion, and a
 * staleness check that cries wolf gets the whole test skipped permanently, which is worse than
 * not having one. A git checkout rewrites the mtime of every file it changes, so a branch switch
 * after a build correctly reads as stale here.
 */
const SOURCES = [
  join( __dirname, '..', 'components', 'PillButton.tsx' ),
  join( __dirname, '..', 'pages', 'account', 'sign-in.tsx' ),
];

/** The newest source mtime and which file carried it, or null when none can be read. */
function newestSource (): { path: string; at: number } | null {
  let newest: { path: string; at: number } | null = null;
  for ( const path of SOURCES ) {
    if ( !existsSync( path ) ) continue;
    const at = statSync( path ).mtimeMs;
    if ( !newest || at > newest.at ) newest = { path, at };
  }
  return newest;
}

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

/**
 * The built page, or a named assertion failure. Reading it directly would throw a bare ENOENT
 * in the `out/`-exists-but-page-missing case, which says nothing about why.
 */
function readPage (): string {
  expect( existsSync( PAGE ),
    `${ PAGE } is missing even though out/ exists - the export ran and did not emit this page. `
    + `Re-run: ${ BUILD_HINT }` ).toBe( true );
  return readFileSync( PAGE, 'utf8' );
}

describe( 'the built pill markup carries the scope hash its CSS requires', () => {
  const built = existsSync( OUT );
  const source = newestSource();
  const pageBuiltAt = existsSync( PAGE ) ? statSync( PAGE ).mtimeMs : 0;
  /*
   * STALE, not merely present. `pageBuiltAt > 0` because the page-missing case is a FAILURE and
   * must not be diverted into a skip: a zero mtime would otherwise look older than every source.
   */
  const stale = pageBuiltAt > 0 && !!source && source.at > pageBuiltAt;

  /*
   * Skip when NO build exists and when the build is STALE; fail when a build exists but omitted
   * this page. Those are three different facts and collapsing any pair of them would either turn
   * a broken export green, turn a fresh clone red, or - the one a review caught - assert against
   * an artifact from a different tree and report the verdict as if it were about this one. The
   * skipped title carries the reason and the build command, because vitest reports a skipped test
   * by name and that is the only place a reader will look.
   */
  const skipReason = !built
    ? `no build: ${ BUILD_HINT }`
    : stale
      ? `stale build: ${ source!.path } is newer than ${ PAGE } by `
        + `${ Math.round( ( source!.at - pageBuiltAt ) / 1000 ) }s, so the export does not `
        + `correspond to this source - ${ BUILD_HINT }`
      : null;

  const run: typeof it = skipReason === null
    ? it
    : ( ( name: string, fn: Parameters<typeof it>[ 1 ] ) =>
        it.skip( `${ name } [${ skipReason }]`, fn ) ) as typeof it;

  run( 'emitted the page this file inspects', () => {
    readPage();
  } );

  run( 'scopes every pill class that appears in the markup', () => {
    const html = readPage();
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
    const html = readPage();
    // The phone phase ships in the static HTML, so "Send code" is the observable action.
    expect( html ).toContain( 'Send code' );

    /*
     * Narrowed to the LABEL's own class, so this still fails if only the OUTER control is scoped -
     * which is exactly how the defect presented: the <button> carried the hash and kept its shape
     * and dark fill, while the label inside got neither background nor colour.
     *
     * ONE SEGMENT, NOT TWO. The owner retired the two-tone pill in 1c847107 (2026-10-02), so the
     * control is a single lime surface carrying one .pill-action label and `.pill-label` is no
     * longer rendered at all. The loop is kept as a loop rather than inlined because the property
     * is per-class, not per-component: a second segment returning would be added here, and the
     * list is the one place to add it.
     */
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
