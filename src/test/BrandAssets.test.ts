import fs from 'fs';
import path from 'path';
import { describe, expect, it } from 'vitest';

/**
 * The brand assets, and which slot each one is allowed in.
 *
 * WHY THIS TEST EXISTS
 * --------------------
 * One file was doing three jobs and was the wrong file for two of them. `wecaredigital.png`
 * fed og:image, twitter:image, apple-touch-icon, the schema.org Organization logo AND both PWA
 * manifest icons. Measured from the live object in s3://wecare-digital-get/o/stream/media/m/:
 *
 *   wecaredigital.png    1080x1080  PNG colour-type 6 (RGBA)  68.4% FULLY TRANSPARENT
 *                        corner and centre both rgba(0,0,0,0), and the mark itself is black
 *   wecare-digital.png   1080x1080  0% transparent, white ground
 *   wd-brand-16x9.png    1440x810   PNG colour-type 2 (RGB) — no alpha channel at all
 *
 * THE FAILURE MODE IS INVISIBLE FROM INSIDE THE PAGE, which is exactly why it needs a test.
 * og:image and apple-touch-icon are composited by someone else's renderer, and neither
 * guarantees a light backdrop — Apple has flattened apple-touch-icon alpha to black since
 * iOS 7, and link-preview renderers flatten to black or to their own surface colour. A black
 * mark on a flattened black ground is an invisible logo. Every check that looks at our own
 * HTML passes while the shared link renders as a black square.
 *
 * So the rule is a rule about ALPHA, not about filenames: any asset handed to a renderer we do
 * not control must be opaque. `wecaredigital.png` is not banned from the repo — it is the
 * correct asset for an <img> on our own known-white page. It is banned from these five slots.
 *
 * The second half is shape. twitter:card is `summary_large_image`, and a 1:1 image in that slot
 * is centre-cropped — it cut the top and bottom off the mark. og:image:width/height also
 * declared 512x512 while the file was 1080x1080, so the hint crawlers use to reserve layout
 * was wrong even about the wrong asset.
 */

const ROOT = path.join( __dirname, '..', '..' );
const APP = fs.readFileSync( path.join( ROOT, 'src', 'pages', '_app.tsx' ), 'utf8' );
const SEO = fs.readFileSync( path.join( ROOT, 'src', 'components', 'SEO.tsx' ), 'utf8' );
const MANIFEST = JSON.parse( fs.readFileSync( path.join( ROOT, 'public', 'manifest.json' ), 'utf8' ) );
const SW = fs.readFileSync( path.join( ROOT, 'public', 'sw.js' ), 'utf8' );

/**
 * Comments stripped before the "is this asset used?" checks.
 *
 * The first version of this test failed on its own subject matter: both files now carry a
 * measurement table that NAMES `wecaredigital.png` to explain why it is banned, and a
 * substring search cannot tell an explanation from a usage. Stripping comments is the honest
 * fix — a rule against using an asset must not also be a rule against documenting it, or the
 * next person removes the note to make the suite green.
 */
const stripComments = ( source: string ): string => source
  .replace( /\/\*[\s\S]*?\*\//g, '' )
  .replace( /^\s*\/\/.*$/gm, '' )
  .replace( /\{\s*\/\*[\s\S]*?\*\/\s*\}/g, '' );

const APP_CODE = stripComments( APP );
const SEO_CODE = stripComments( SEO );

/** The one asset that is 68.4% transparent. Never hand this to an external renderer. */
const TRANSPARENT = 'wecaredigital.png';
const OPAQUE_SQUARE = 'wecare-digital.png';
const SOCIAL_CARD = 'wd-brand-16x9.png';
const MEDIA_BASE = 'https://wecare.digital/get/o/stream/media/m';

describe( 'Brand assets', () => {
  it( 'serves every asset from the canonical media folder', () => {
    /*
     * s3://wecare-digital-get/o/stream/media/m/ is the canonical location since the
     * app.wecare.digital merge (docs/media-bucket-merge.md), reached over HTTPS as
     * /get/o/stream/media/m/ through CloudFront E2GP22R4BIFGQ3. The old host is deliberately
     * still alive - 61 objects under public/wa-tpl/ are named by WhatsApp templates Meta has
     * already approved - so this asserts the ASSETS here moved, not that the host is gone.
     */
    for ( const source of [ APP_CODE, SEO_CODE ] ) {
      const urls = [ ...source.matchAll( /https:\/\/[^'"`\s)]*stream\/media\/m\/[^'"`\s)]+/g ) ].map( m => m[ 0 ] );
      for ( const url of urls ) expect( url.startsWith( MEDIA_BASE ) ).toBe( true );
    }
    expect( APP ).toContain( `const MEDIA_BASE = '${MEDIA_BASE}'` );
    for ( const icon of MANIFEST.icons ) expect( icon.src.startsWith( MEDIA_BASE ) ).toBe( true );
  } );

  it( 'never hands the 68%-transparent mark to a renderer we do not control', () => {
    /*
     * THE CORE ASSERTION, and the list is every slot where someone else's compositor decides
     * the backdrop: og:image, twitter:image, apple-touch-icon, the schema Organization logo,
     * the PWA manifest icons, and the service worker's notification icon and badge.
     *
     * THE SERVICE WORKER IS THE ONE THAT NEARLY GOT MISSED. A notification is painted by the
     * OPERATING SYSTEM's shade, which on Android and on Windows is usually dark - so it is the
     * same "black mark flattened onto black" failure as the link preview, in a place that
     * looks nothing like SEO and lives in a file no HTML audit reads.
     *
     * WHAT IS DELIBERATELY NOT BANNED: the five in-page uses - BrandLockup, Layout's sidebar,
     * FloatingAgent, the grahak-os preload and the push-composer preview. Those render on our
     * own known-white surfaces, where transparency is the CORRECT choice and an opaque white
     * square would show as a visible tile. The rule is about who composites the alpha, not
     * about the filename, and a rule stated as "never use this file" would have wrongly
     * rewritten all five.
     */
    expect( APP_CODE ).not.toContain( TRANSPARENT );
    expect( SEO_CODE ).not.toContain( TRANSPARENT );
    expect( JSON.stringify( MANIFEST ) ).not.toContain( TRANSPARENT );
    expect( stripComments( SW ) ).not.toContain( TRANSPARENT );
    expect( stripComments( SW ) ).toContain( `${MEDIA_BASE}/${OPAQUE_SQUARE}` );
    // And the ban is documented where someone editing these constants will read it, so the
    // next person does not "simplify" three assets back down to one.
    expect( APP ).toContain( 'FULLY TRANSPARENT' );
  } );

  it( 'leaves the transparent mark in place for surfaces this repo paints itself', () => {
    /*
     * The counterpart to the rule above, asserted so a later sweep does not "finish the job"
     * by replacing these too. On a white page the transparent mark is right and the opaque
     * square would render as a visible white tile behind the logo.
     */
    const inPage = [
      [ 'src/components/BrandLockup.tsx', 'the public header lockup' ],
      [ 'src/components/Layout.tsx', 'the dashboard sidebar' ],
      [ 'src/components/FloatingAgent.tsx', 'the floating agent avatar' ],
    ] as const;
    for ( const [ file ] of inPage ) {
      const source = fs.readFileSync( path.join( ROOT, file ), 'utf8' );
      expect( source ).toContain( `${MEDIA_BASE}/${TRANSPARENT}` );
    }
  } );

  it( 'uses the 16:9 card for link previews, because the card type is summary_large_image', () => {
    expect( APP ).toContain( 'name="twitter:card" content="summary_large_image"' );
    expect( APP ).toContain( `const SOCIAL_CARD_URL = \`\${MEDIA_BASE}/${SOCIAL_CARD}\`` );
    // Both og and twitter point at it, and nothing else does.
    expect( APP ).toContain( 'property="og:image" key="og:image" content={ SOCIAL_CARD_URL }' );
    expect( APP ).toContain( 'name="twitter:image" content={ SOCIAL_CARD_URL }' );
    expect( SEO ).toContain( `${MEDIA_BASE}/${SOCIAL_CARD}` );
  } );

  it( 'declares the social card at its real pixel size, not a remembered one', () => {
    /*
     * These were 512x512 against a 1080x1080 file. Crawlers use the hint to reserve layout
     * before fetching, so a wrong value is worse than an absent one - and being wrong by a
     * factor of two went unnoticed for as long as nobody compared it to the object.
     */
    expect( APP ).toContain( "const SOCIAL_CARD_W = '1440'" );
    expect( APP ).toContain( "const SOCIAL_CARD_H = '810'" );
    expect( APP ).toContain( 'content={ SOCIAL_CARD_W }' );
    expect( APP ).toContain( 'content={ SOCIAL_CARD_H }' );
    // And the ratio stays inside the 2:1..1:1 band the platforms accept.
    const ratio = 1440 / 810;
    expect( ratio ).toBeGreaterThan( 1 );
    expect( ratio ).toBeLessThan( 2 );
  } );

  it( 'keeps the square opaque logo for icons and structured data', () => {
    expect( APP ).toContain( `const LOGO_URL = \`\${MEDIA_BASE}/${OPAQUE_SQUARE}\`` );
    expect( APP ).toContain( 'rel="apple-touch-icon" href={ LOGO_URL }' );
    // Organization.logo stays square: Google renders it in the knowledge panel and wants the
    // logo, not a banner. The fix there was opacity, not shape.
    expect( APP ).toContain( '"logo": LOGO_URL' );
  } );

  it( 'does not claim the icon is maskable, and does not lie about its size', () => {
    /*
     * TWO SEPARATE MANIFEST DEFECTS, both from the same copy-paste. The two entries pointed at
     * ONE 1080x1080 file while declaring "192x192" and "512x512" - neither true - so a browser
     * picking by declared size got a 1080px image either way and two entries described one
     * asset. And both said `purpose: "any maskable"`. A maskable icon must fill its whole
     * canvas with the important content inside a 80% safe circle, because the platform crops it
     * to whatever shape it likes; a transparent logo declared maskable gets an undefined
     * background and a cropped mark. One honest entry replaces two wrong ones.
     */
    expect( MANIFEST.icons ).toHaveLength( 1 );
    const [ icon ] = MANIFEST.icons;
    expect( icon.sizes ).toBe( '1080x1080' );
    expect( icon.purpose ).toBe( 'any' );
    expect( icon.purpose ).not.toContain( 'maskable' );
    expect( icon.src ).toContain( OPAQUE_SQUARE );
  } );

  it( 'points manifest shortcuts at the canonical workspace URLs rather than a redirect', () => {
    /*
     * These were /dashboard, /dm and /contacts - the pre-/workspace/ paths. All three still
     * resolve, verified live at 301 to /workspace/dashboard/, /workspace/engage/ and
     * /workspace/contacts/, so this was a hop rather than a break. A launcher shortcut is a
     * cold start though, and the redirect is a round trip before any HTML arrives. /dm also
     * landed on /workspace/engage/ rather than the inbox, so "Messages" opened a section index.
     */
    const urls = MANIFEST.shortcuts.map( ( s: { url: string } ) => s.url );
    expect( urls ).toEqual( [ '/workspace/dashboard/', '/workspace/engage/inbox/', '/workspace/contacts/' ] );
    // trailingSlash:true - a shortcut without the slash takes another redirect.
    for ( const url of urls ) expect( url.endsWith( '/' ) ).toBe( true );
  } );

  it( 'leaves the BIMI svg alone, because DNS points at it under p=reject', () => {
    /*
     * default._bimi.wecare.digital carries
     *   l=https://wecare.digital/get/o/stream/media/m/wecare-digital.svg
     * A BIMI record aimed at a missing logo degrades SILENTLY - no bounce, no error, the
     * branding just stops appearing - so renaming this asset breaks inbox branding with
     * nothing anywhere to notice. DNS first, verify, then this. Asserted so a tidy-up that
     * renames it has to read this comment.
     */
    expect( APP ).toContain( 'const LOGO_SVG_URL = `${MEDIA_BASE}/wecare-digital.svg`' );
  } );
} );
