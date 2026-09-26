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
    // page in one of them would get mirrored boxes with ltr text. None is offered by the
    // translation provider, which is the only reason this is acceptable. If the catalogue
    // ever grows one of them, this list is where the fix starts.
    const MIRRORED_BUT_NOT_FLIPPED = [ 'ae', 'arc', 'bcc', 'bqi', 'ckb', 'dv', 'glk', 'ku',
      'mzn', 'nqo', 'pnb', 'ug', 'yi' ];
    for ( const code of MIRRORED_BUT_NOT_FLIPPED ) {
      expect( isRtlLanguage( code ), `${code} is a known, unreachable gap` ).toBe( false );
    }
  } );

  it( 'treats a missing or malformed code as left-to-right', () => {
    // The safe default: a page that fails to mirror is readable, a page mirrored by
    // accident is not.
    for ( const code of [ '', '-', '_', 'auto' ] ) {
      expect( isRtlLanguage( code as string ), JSON.stringify( code ) ).toBe( false );
    }
  } );
} );
