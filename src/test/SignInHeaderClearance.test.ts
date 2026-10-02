import { existsSync, readFileSync } from 'fs';
import { join } from 'path';
import { describe, expect, it } from 'vitest';

/**
 * THE SIGN-IN FIELDS MUST NOT BE REVEALED BEHIND THE FIXED HEADER.
 *
 * WHAT WAS WRONG. Header.tsx renders `position:fixed` at 108px (96px below 768px), and nothing
 * gave the document or these controls any clearance for it. When the browser reveals a form
 * control - on focus, on autofocus, or as part of refusing an empty `required` field - it scrolls
 * that control to the top of the scrollport, and the top of the scrollport is UNDER the header.
 * Measured in Chrome against this export before the fix: the WhatsApp number field landed 36.1px
 * behind the header at 320x568 and 50px behind it at 390x400 (the height a phone has left with
 * its keyboard up), so the shopper could not see the number they were typing.
 *
 * WHY THIS TEST READS THE BUILD AND NOT THE SOURCE. A scroll offset only exists where there is
 * layout, and jsdom has none - it does not scroll, does not lay out, and reports every computed
 * length as its unresolved input. A source-string assertion would pass on a declaration that
 * could never reach the element, which is precisely the failure mode the pill's scoping bug had.
 * So this asserts the two properties that actually have to hold in the shipped artifact:
 *
 *   1. the clearance is at least the header's own height, at both header heights; and
 *   2. the selector carrying it can REACH the element - styled-jsx scopes by hash, and a rule
 *      whose hash is absent from the element's class list is inert however correct it looks.
 *
 * Property (2) is not theoretical here. `2f742ec6` fixed a shipped defect of exactly that shape
 * in PillButton, where correct CSS never matched its own markup.
 *
 * WHY scroll-margin ON THE CONTROLS AND NOT scroll-padding ON THE DOCUMENT. LegalDocument and
 * ContactLocation already carry their own `scroll-margin-top` for this header. Scroll padding on
 * the scrollport ADDS to scroll margin on the target, so a document-level inset would silently
 * double their anchor clearance. Both were measured in Chrome; this is the one that fixes the
 * fields without changing anything else.
 */

const PAGE = join( process.cwd(), 'out', 'account', 'sign-in', 'index.html' );

/** The header's own measured heights, from Header.tsx: .hdr-in height 108px, 96px below 768px. */
const HEADER_DESKTOP = 108;
const HEADER_MOBILE = 96;

/** Every `<style>` body the page inlines, concatenated. */
function inlinedCss ( html: string ): string {
  return ( html.match( /<style[^>]*>([\s\S]*?)<\/style>/g ) || [] )
    .map( block => block.replace( /^<style[^>]*>/, '' ).replace( /<\/style>$/, '' ) )
    .join( '\n' );
}

/**
 * Every `scroll-margin-top` declared for `selector`, with the styled-jsx hash each rule was
 * written against, and whether that rule sits inside a max-width media query.
 */
function clearanceRules ( css: string, selector: string ): Array<{ px: number; hash: string; maxWidth: number | null }> {
  const out: Array<{ px: number; hash: string; maxWidth: number | null }> = [];
  const pattern = new RegExp( `\\${selector}\\.(jsx-[a-z0-9]+)\\{([^}]*)\\}`, 'g' );
  let m: RegExpExecArray | null;
  while ( ( m = pattern.exec( css ) ) !== null ) {
    const value = /scroll-margin-top:\s*(\d+)px/.exec( m[ 2 ] );
    if ( !value ) continue;
    // Which media query, if any, this rule is nested in. Found by walking back to the nearest
    // preceding @media and checking no intervening `}` closed it - cheaper and more honest than
    // half-parsing CSS, and it fails loudly rather than guessing if the shape changes.
    const before = css.slice( 0, m.index );
    const lastMedia = before.lastIndexOf( '@media' );
    let maxWidth: number | null = null;
    if ( lastMedia !== -1 ) {
      const query = css.slice( lastMedia, m.index );
      const bound = /max-width:\s*(\d+)px/.exec( query );
      if ( bound && !/\}\s*\}/.test( query.slice( query.indexOf( '{' ) ) ) ) maxWidth = Number( bound[ 1 ] );
    }
    out.push( { px: Number( value[ 1 ] ), hash: m[ 1 ], maxWidth } );
  }
  return out;
}

/** The styled-jsx hashes actually stamped on the element carrying `className`. */
function hashesOnElement ( html: string, className: string ): string[] {
  const hashes = new Set<string>();
  for ( const attr of html.match( /class="[^"]*"/g ) || [] ) {
    const classes = attr.slice( 7, -1 ).split( /\s+/ );
    if ( !classes.includes( className ) ) continue;
    classes.filter( c => c.startsWith( 'jsx-' ) ).forEach( c => hashes.add( c ) );
  }
  return [ ...hashes ];
}

/** Every styled-jsx hash this page stamps on anything at all. */
function hashesOnPage ( html: string ): string[] {
  const hashes = new Set<string>();
  for ( const attr of html.match( /class="[^"]*"/g ) || [] ) {
    attr.slice( 7, -1 ).split( /\s+/ ).filter( c => c.startsWith( 'jsx-' ) ).forEach( c => hashes.add( c ) );
  }
  return [ ...hashes ];
}

const present = existsSync( PAGE );

describe.skipIf( !present )( 'the sign-in fields clear the fixed header when revealed', () => {
  if ( !present ) return;
  const html = readFileSync( PAGE, 'utf8' );
  const css = inlinedCss( html );

  // `.pf-num` is the WhatsApp number segment (PhoneField); `.si-input` is the OTP code field.
  // Both are controls the browser reveals, and both used to be revealed behind the header.
  for ( const selector of [ '.pf-num', '.si-input' ] ) {
    describe( selector, () => {
      it( 'declares a clearance for both header heights', () => {
        const rules = clearanceRules( css, selector );
        expect( rules.length, `${selector} ships no scroll-margin-top at all` ).toBeGreaterThan( 0 );

        // The unscoped rule applies at every width, so it must clear the TALLER header.
        const wide = rules.filter( r => r.maxWidth === null );
        expect( wide.length, `${selector} has no width-independent clearance` ).toBeGreaterThan( 0 );
        for ( const r of wide ) expect( r.px ).toBeGreaterThanOrEqual( HEADER_DESKTOP );

        // Below 768px the header is 96px, and a rule in that query overrides the one above - so
        // whatever it narrows to must still clear the SHORTER header. This is the assertion that
        // catches a mobile override written as 0, or as a value copied from the wrong header.
        for ( const r of rules.filter( r => r.maxWidth !== null && r.maxWidth <= 767 ) ) {
          expect( r.px, `${selector} clearance inside max-width:${r.maxWidth}px` ).toBeGreaterThanOrEqual( HEADER_MOBILE );
        }
      } );

      it( 'carries a hash that can reach the element it targets', () => {
        const className = selector.slice( 1 );
        const onElement = hashesOnElement( html, className );
        /*
         * TWO CASES, AND THE WEAKER ONE IS NAMED RATHER THAN HIDDEN.
         *
         * `.pf-num` is in the initial render, so the rule's hash must be on that very element -
         * the full guarantee.
         *
         * `.si-input` is NOT: it dresses the OTP code field, which only exists once the shopper
         * has asked for a code, and the static export is the phone phase. There is no element to
         * compare against, so the check narrows to "the hash is one this page actually stamps",
         * which still catches the failure that matters - a rule orphaned to a scope the page
         * never emits - while being honest that it cannot prove reachability on an element that
         * is not in the artifact. Writing the stronger assertion here would be a test that looks
         * tighter and fails for the wrong reason.
         */
        const reachable = onElement.length > 0 ? onElement : hashesOnPage( html );
        const scope = onElement.length > 0 ? `the ${className} element` : 'this page';
        expect( reachable.length, 'the export stamps no styled-jsx hashes at all' ).toBeGreaterThan( 0 );
        for ( const rule of clearanceRules( css, selector ) ) {
          expect( reachable, `${selector}{scroll-margin-top:${rule.px}px} is written against ${rule.hash}, which ${scope} does not carry` )
            .toContain( rule.hash );
        }
      } );
    } );
  }
} );

// A skip that says what to run, so this never passes quietly on a tree with no build.
describe.skipIf( present )( 'the sign-in header clearance check needs a build', () => {
  it( 'is skipped until out/account/sign-in/index.html exists', () => {
    console.warn( 'skipped: run `node scripts/generate-public-pages.js && npx next build --webpack` first' );
    expect( present ).toBe( false );
  } );
} );
