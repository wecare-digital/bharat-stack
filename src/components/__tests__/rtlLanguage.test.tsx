import { describe, expect, it } from 'vitest';
import { isRtlLanguage } from '../SupportWidget';

/**
 * THE FAILURE THIS PINS. Translating into Arabic produced correct Arabic words in a
 * left-to-right document. With `dir` left at ltr the paragraph direction is wrong, so a
 * full stop ending an Arabic sentence renders at the LEFT edge of the line - reported from
 * the live site as a period sitting at the start of every footer line. The words were
 * right; the writing system was not.
 *
 * rtlcheck.js covers the CSS consequences of a mirrored document. This covers the decision
 * that puts the document into that state, which rtlcheck deliberately does not exercise
 * because it sets `dir` directly rather than going through a live /translate call.
 */
describe( 'isRtlLanguage', () => {
  it( 'detects every right-to-left script in the provider catalogue', () => {
    // Arabic, Persian, Hebrew, Urdu, Pashto, Sindhi - the six the provider can return.
    for ( const code of [ 'ar', 'fa', 'he', 'ur', 'ps', 'sd' ] ) {
      expect( isRtlLanguage( code ), code ).toBe( true );
    }
  } );

  it( 'leaves left-to-right languages alone, including the Indic ones', () => {
    // The Indic languages are the product's primary audience and every one of them is LTR.
    // A false positive here would mirror the entire site for a Hindi reader.
    for ( const code of [ 'en', 'hi', 'bn', 'ta', 'te', 'mr', 'gu', 'kn', 'ml', 'pa',
      'fr', 'es', 'zh', 'ja', 'ko', 'ru', 'tr', 'vi' ] ) {
      expect( isRtlLanguage( code ), code ).toBe( false );
    }
  } );

  it( 'resolves a regional form through its base subtag', () => {
    // Dari arrives from the provider as fa-AF. Matching the whole code would miss it and
    // leave an RTL language rendering left-to-right - the original defect, narrowed to one
    // language instead of six.
    expect( isRtlLanguage( 'fa-AF' ) ).toBe( true );
    expect( isRtlLanguage( 'ar-AE' ) ).toBe( true );
    expect( isRtlLanguage( 'fa_AF' ) ).toBe( true );
    expect( isRtlLanguage( 'AR' ) ).toBe( true );
    // ...without matching a longer code that merely starts with the same letters.
    expect( isRtlLanguage( 'arn' ) ).toBe( false );
    expect( isRtlLanguage( 'hea' ) ).toBe( false );
  } );

  it( 'stays within the language set the BUILD mirrors on', () => {
    /**
     * THE COUPLING THIS PINS, WHICH IS INVISIBLE IN THE SOURCE. We write logical properties
     * (`inset-inline-end`, `padding-inline-start`). The shipped CSS contains NONE of them:
     * Lightning CSS downlevels each one for the browserslist targets into a pair of rules
     * keyed on :lang() --
     *
     *   .wc-langbar:not(:is(:lang(ar),:lang(he), ...)){left:auto;right:20px}
     *   .wc-langbar:is(:lang(ar),:lang(he), ...)){left:20px;right:auto}
     *
     * -- so in production the MIRRORING IS DRIVEN BY `lang`, while the bidi algorithm is
     * driven by `dir`. Set one without the other and you get half a mirror: correct Arabic
     * word order in boxes that never moved, or moved boxes holding left-to-right text.
     *
     * Consequence for this function: every code it calls RTL must appear in Lightning's set,
     * or we would flip `dir` for a language whose boxes stay put. The reverse gap is recorded
     * below rather than closed, because it is not reachable through the provider.
     */
    const LIGHTNINGCSS_RTL = new Set( [ 'ae', 'ar', 'arc', 'bcc', 'bqi', 'ckb', 'dv', 'fa',
      'glk', 'he', 'ku', 'mzn', 'nqo', 'pnb', 'ps', 'sd', 'ug', 'ur', 'yi' ] );

    for ( const code of [ 'ar', 'fa', 'he', 'ur', 'ps', 'sd' ] ) {
      expect( isRtlLanguage( code ), `${code} must be in the set the build mirrors on` ).toBe( true );
      expect( LIGHTNINGCSS_RTL.has( code ), `${code} missing from LightningCSS RTL set` ).toBe( true );
    }

    // THE KNOWN GAP, stated rather than implied. Lightning mirrors these and we do not, so a
    // page in one of them would get mirrored boxes with ltr text. The test below proves none
    // is reachable; this only records that the divergence exists.
    const MIRRORED_BUT_NOT_FLIPPED = [ 'ae', 'arc', 'bcc', 'bqi', 'ckb', 'dv', 'glk', 'ku',
      'mzn', 'nqo', 'pnb', 'ug', 'yi' ];
    for ( const code of MIRRORED_BUT_NOT_FLIPPED ) {
      expect( isRtlLanguage( code ), `${code} is a known, unreachable gap` ).toBe( false );
    }
  } );

  it( 'covers every RTL language the LIVE catalogue actually offers, with nothing left over', () => {
    /**
     * THE ASSERTION THAT TURNS A HAND-WAVE INTO A PROOF. The gap above was first written as
     * "none of these is offered by the provider", which was an assumption. This reads the
     * captured response from GET /site-language/languages and checks it.
     *
     * The fixture is real, not authored: docs/execution/language-catalogue.json holds the
     * live body, 76 entries. Re-capture it with
     *   curl -s https://api.wecare.digital/site-language/languages
     * and this test will fail the moment the catalogue gains a right-to-left language this
     * function does not know about - which is the only way the divergence above becomes a
     * defect.
     */
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const catalogue = require( '../../../docs/execution/language-catalogue.json' );
    const LIGHTNINGCSS_RTL = new Set( [ 'ae', 'ar', 'arc', 'bcc', 'bqi', 'ckb', 'dv', 'fa',
      'glk', 'he', 'ku', 'mzn', 'nqo', 'pnb', 'ps', 'sd', 'ug', 'ur', 'yi' ] );
    const base = ( c: string ) => c.toLowerCase().split( /[-_]/ )[ 0 ];

    const offered: string[] = catalogue.languages.map( ( l: { code: string } ) => l.code );
    expect( offered.length ).toBeGreaterThan( 60 );

    // Every offered language the BUILD would mirror must be one this function flips. An
    // empty result here is the whole point: no reachable language gets mirrored boxes
    // wrapped around left-to-right text.
    const mirroredByBuildButNotByUs = offered.filter(
      c => LIGHTNINGCSS_RTL.has( base( c ) ) && !isRtlLanguage( c ) );
    expect( mirroredByBuildButNotByUs ).toEqual( [] );

    // And the converse: every offered RTL language is detected. Listed explicitly so the
    // failure names the language rather than a count.
    const offeredRtl = offered.filter( c => LIGHTNINGCSS_RTL.has( base( c ) ) );
    expect( offeredRtl.sort() ).toEqual( [ 'ar', 'fa', 'fa-AF', 'he', 'ps', 'ur' ] );
    for ( const code of offeredRtl ) expect( isRtlLanguage( code ), code ).toBe( true );

    // Dari is the reason base-subtag matching exists: it is offered as a regional code and
    // is NOT one of the four variants the picker trims, so it reaches a real visitor.
    expect( offered ).toContain( 'fa-AF' );
  } );

  it( 'treats a missing or malformed code as left-to-right', () => {
    // The safe default: a page that fails to mirror is readable, a page mirrored by
    // accident is not.
    for ( const code of [ '', '-', '_', 'auto' ] ) {
      expect( isRtlLanguage( code as string ), JSON.stringify( code ) ).toBe( false );
    }
  } );
} );
