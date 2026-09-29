import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

/**
 * GUARDS A DRIFT THAT WOULD ONLY SHOW UP AT INGESTION TIME.
 *
 * `blog-studio.tsx` lets an operator pick a category and an article class, and exports
 * them into a work order. `scripts/blog_quality_v2.py` owns the authoritative lists, and
 * `blog_ingest.read_work_order` refuses a work order naming a category the gate does not
 * accept.
 *
 * So if the page gains a third category and the Python does not, the operator selects it,
 * spends an afternoon assembling an order, and the ingestion refuses every row in it. The
 * lists cannot be shared across the language boundary without a build step, so this test
 * is the seam: it reads the Python source as text and asserts the page agrees.
 *
 * Reading source as text rather than importing is the same technique
 * PublicRouteRegistration.test.ts uses, and for the same reason - the values under test
 * are literals in the file.
 */
const ROOT = process.cwd();
const PAGE = path.join( ROOT, 'src', 'pages', 'workspace', 'seo', 'blog-studio.tsx' );
const GATE = path.join( ROOT, 'scripts', 'blog_quality_v2.py' );

const pageSource = fs.readFileSync( PAGE, 'utf8' );
const gateSource = fs.readFileSync( GATE, 'utf8' );

/** Pull a `const NAME = [ 'a', 'b' ] as const;` list out of the TSX. */
const tsList = ( name: string ): string[] => {
  const match = pageSource.match( new RegExp( `const ${ name } = \\[([^\\]]*)\\]` ) );
  if ( !match ) throw new Error( `${ name } not found in blog-studio.tsx` );
  return Array.from( match[ 1 ].matchAll( /'([^']+)'/g ) ).map( ( m ) => m[ 1 ] );
};

/** Pull a `NAME: Tuple[str, ...] = ("a", "b")` or `NAME = ("a", "b")` list out of the Python. */
const pyList = ( name: string ): string[] => {
  const match = gateSource.match(
    new RegExp( `^${ name }(?:\\s*:[^=]*)?\\s*=\\s*\\(([\\s\\S]*?)\\)`, 'm' ) );
  if ( !match ) throw new Error( `${ name } not found in blog_quality_v2.py` );
  return Array.from( match[ 1 ].matchAll( /"([^"]+)"/g ) ).map( ( m ) => m[ 1 ] );
};

describe( 'Blog Studio agrees with the quality gate', () => {
  it( 'offers exactly the categories the gate accepts', () => {
    expect( tsList( 'CATEGORIES' ).slice().sort() ).toEqual( pyList( 'CATEGORIES' ).slice().sort() );
  } );

  it( 'offers exactly the article classes the gate accepts', () => {
    expect( tsList( 'ARTICLE_CLASSES' ).slice().sort() )
      .toEqual( pyList( 'ARTICLE_CLASSES' ).slice().sort() );
  } );

  it( 'names the same machine-decided gates', () => {
    expect( tsList( 'MACHINE_GATES' ) ).toEqual( pyList( 'MACHINE_GATES' ) );
  } );

  it( 'names the same human-only gates', () => {
    expect( tsList( 'HUMAN_GATES' ) ).toEqual( pyList( 'HUMAN_GATES' ) );
  } );

  it( 'still has exactly two categories', () => {
    // Not a style preference. `/blog/` serves whichever category sorts first
    // alphabetically (src/lib/blog-index-props.ts), and every other category needs its own
    // /blog/topic/<slug>/ stream registered. A third category is a routing change, not a
    // dropdown change, so it should not be possible to add one here alone.
    expect( tsList( 'CATEGORIES' ) ).toHaveLength( 2 );
  } );
} );

describe( 'Blog Studio is an authenticated surface', () => {
  it( 'renders inside the dashboard Layout', () => {
    // PublicRouteRegistration.test.ts reads the Layout import to decide whether a route is
    // public in shape. Losing it here would make this page look like a public route that
    // was never added to the allowlist, which renders the staff sign-in screen at HTTP 200.
    expect( pageSource ).toMatch( /import Layout from '[^']*components\/Layout'/ );
  } );

  it( 'is marked noindex', () => {
    expect( pageSource ).toContain( 'noindex' );
  } );

  it( 'does not claim to upload anything', () => {
    // There is no blog-source ingest backend. A button that appears to upload and silently
    // does nothing is the worst available outcome, so the page must not imply one.
    expect( pageSource ).not.toMatch( /fetch\(|authFetch|seoToolsFetch/ );
  } );

  it( 'reaches the ledger through the build, not through a request', () => {
    expect( pageSource ).toContain( 'getStaticProps' );
    expect( pageSource ).toContain( 'content' );
  } );
} );

describe( 'the ingestion pipeline cannot self-certify', () => {
  it( 'draft records are created as SOURCE_REVIEW', () => {
    const ingest = fs.readFileSync( path.join( ROOT, 'scripts', 'blog_ingest.py' ), 'utf8' );
    expect( ingest ).toContain( '"status": "SOURCE_REVIEW"' );
  } );

  it( 'the draft builder never writes a gate object or a sourceReviewedFully flag', () => {
    const ingest = fs.readFileSync( path.join( ROOT, 'scripts', 'blog_ingest.py' ), 'utf8' );
    const builder = ingest.slice( ingest.indexOf( 'def draft_record' ),
      ingest.indexOf( 'def build_drafts' ) );
    expect( builder ).not.toMatch( /"gate"\s*:/ );
    expect( builder ).not.toMatch( /"sourceReviewedFully"\s*:/ );
  } );

  it( 'the gate holds a record without human verdicts at EDITORIAL_QA', () => {
    expect( gateSource ).toContain( 'return "EDITORIAL_QA"' );
  } );
} );
